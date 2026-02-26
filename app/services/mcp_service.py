"""
MCP 服务业务逻辑层

管理用户配置的 MCP 服务器：CRUD、工具发现、ToolRegistry 注册/注销。

MongoDB 集合: mcp_server_configs
  server_id       str  — 唯一标识（slug 格式）
  name            str  — 显示名称
  description     str
  transport_type  str  — sse | streamable_http | stdio
  connection      dict — 连接参数（url/headers 或 command/args/env）
  discovered_tools list— 最近一次发现的工具列表（缓存）
  is_enabled      bool — 是否启用（控制 ToolRegistry 注册）
  status          str  — active | inactive | error | unknown
  last_error      str | None
  category        str  — datasource | function（默认 function）
  data_mappings   list — 数据源类配置映射（仅 datasource 类有效）
  created_at      str
  updated_at      str
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

COLLECTION = "mcp_server_configs"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sanitize_for_mongo(obj: Any) -> Any:
    """递归替换 $ 前缀键为 _ 前缀，MongoDB 不允许 $ 开头的字段名（如 JSON Schema 的 $schema）"""
    if isinstance(obj, dict):
        return {
            ("_" + k[1:] if k.startswith("$") else k): _sanitize_for_mongo(v)
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_sanitize_for_mongo(x) for x in obj]
    return obj


def _tool_id(server_id: str, tool_name: str) -> str:
    """生成统一的工具 ID"""
    return f"mcp_{server_id}_{tool_name}"


def _extract_output_fields(raw: str) -> List[Dict]:
    """从 MCP 工具返回结果中提取输出字段名、类型和样本值"""
    import json as _json
    fields: Dict[str, Dict] = {}

    def _walk(data, prefix: str = "", depth: int = 0):
        if depth > 3:
            return
        if isinstance(data, list):
            if data:
                _walk(data[0], prefix, depth)
            return
        if isinstance(data, dict):
            for key, val in data.items():
                full_key = f"{prefix}.{key}" if prefix else key
                if isinstance(val, dict):
                    _walk(val, full_key, depth + 1)
                elif isinstance(val, list):
                    if val and isinstance(val[0], dict):
                        _walk(val[0], full_key, depth + 1)
                    else:
                        sample = str(val[:3]) if val else "[]"
                        if full_key not in fields:
                            fields[full_key] = {"name": full_key, "sample": sample[:80], "type": "array"}
                else:
                    t = "boolean" if isinstance(val, bool) else ("number" if isinstance(val, (int, float)) else "string")
                    sample = str(val)[:80] if val is not None else ""
                    if full_key not in fields:
                        fields[full_key] = {"name": full_key, "sample": sample, "type": t}

    try:
        parsed = _json.loads(raw)
        _walk(parsed)
    except Exception:
        return [{"name": "result", "sample": raw[:80], "type": "string"}]
    return list(fields.values())


def _register_mcp_tool(
    server_id: str,
    tool_meta: Dict,
    connection_config: Dict,
    category: str = "function",
    data_mappings: Optional[List[Dict]] = None,
    server_name: str = "",
) -> None:
    """将单个 MCP 工具注册到 ToolRegistry

    Args:
        server_id:        服务器 ID（用于生成 tool_id）
        tool_meta:        工具元数据（name, description, input_schema）
        connection_config: 连接参数（transport_type + connection）
        category:         datasource | function
        data_mappings:    服务器级数据映射列表（datasource 类使用）
        server_name:      服务器名称（写入 audit log / data_source 标识）
    """
    from core.tools.registry import get_tool_registry
    from core.tools.mcp.client_manager import get_mcp_client_manager

    registry = get_tool_registry()
    tid = _tool_id(server_id, tool_meta["name"])
    tool_name = tool_meta["name"]

    if registry.has_tool(tid):
        logger.debug(f"MCP 工具已存在，跳过: {tid}")
        return

    manager = get_mcp_client_manager()

    # 找到本工具对应的 data_mapping 条目（按 tool_name 匹配）
    tool_data_mapping: Optional[Dict] = None
    if category == "datasource" and data_mappings:
        for dm in data_mappings:
            if dm.get("tool_name") == tool_name:
                tool_data_mapping = dm
                break

    _sname = server_name or server_id

    if category == "datasource":
        # 数据源类：调用后通过适配器持久化到 MongoDB，并记录审计日志
        def _executor(**kwargs) -> str:
            """同步执行 MCP 工具（数据源类）"""
            raw = manager.call_tool(
                config=connection_config,
                tool_name=tool_name,
                arguments=kwargs,
            )
            # 持久化
            try:
                from core.tools.mcp.datasource_adapter import get_mcp_datasource_adapter
                adapter = get_mcp_datasource_adapter()
                persisted_to = adapter.adapt_and_persist(
                    raw_result=raw,
                    tool_name=tool_name,
                    data_mapping=tool_data_mapping,
                    server_name=_sname,
                )
            except Exception as e:
                logger.warning(f"[MCP Datasource] 持久化失败 ({tool_name}): {e}")
                persisted_to = None

            # 审计日志（fire-and-forget）
            try:
                from app.services.mcp_audit_service import log_mcp_call_sync
                resp_summary = f"OK, {len(raw)} chars" if raw else "empty"
                log_mcp_call_sync(
                    server_name=_sname,
                    tool_name=tool_name,
                    category="datasource",
                    request_params=kwargs,
                    response_summary=resp_summary,
                    persisted_to=persisted_to,
                )
            except Exception as e:
                logger.warning(f"[MCP Audit] 审计日志写入失败: {e}")

            return raw
    else:
        # 功能类：直接调用并记录审计日志
        def _executor(**kwargs) -> str:
            """同步执行 MCP 工具（功能类）"""
            raw = manager.call_tool(
                config=connection_config,
                tool_name=tool_name,
                arguments=kwargs,
            )
            # 审计日志（fire-and-forget）
            try:
                from app.services.mcp_audit_service import log_mcp_call_sync
                resp_summary = f"OK, {len(raw)} chars" if raw else "empty"
                log_mcp_call_sync(
                    server_name=_sname,
                    tool_name=tool_name,
                    category="function",
                    request_params=kwargs,
                    response_summary=resp_summary,
                )
            except Exception as e:
                logger.warning(f"[MCP Audit] 审计日志写入失败: {e}")

            return raw

    registry.register_function(
        tool_id=tid,
        func=_executor,
        name=f"[MCP] {tool_meta['name']}",
        category="mcp",
        description=tool_meta.get("description", ""),
        is_online=True,
        override=True,
    )
    logger.info(f"✅ 注册 MCP 工具: {tid} (category={category})")


def _unregister_server_tools(server_id: str, discovered_tools: List[Dict]) -> None:
    """从 ToolRegistry 注销指定服务器的所有工具"""
    from core.tools.registry import get_tool_registry

    registry = get_tool_registry()
    for tool_meta in discovered_tools:
        tid = _tool_id(server_id, tool_meta["name"])
        if registry.has_tool(tid):
            registry.unregister(tid)
            logger.info(f"🗑️ 注销 MCP 工具: {tid}")


class MCPService:
    """MCP 服务器配置业务逻辑"""

    def __init__(self, db: AsyncIOMotorDatabase):
        self._db = db

    @property
    def _col(self):
        return self._db[COLLECTION]

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def create_server(self, data: Dict) -> Dict:
        """创建 MCP 服务器配置"""
        server_id = data.get("server_id") or str(uuid.uuid4())[:8]
        now = _now_iso()
        doc = {
            "server_id": server_id,
            "name": data.get("name", server_id),
            "description": data.get("description", ""),
            "transport_type": data.get("transport_type", "sse"),
            "connection": data.get("connection", {}),
            "discovered_tools": [],
            "is_enabled": data.get("is_enabled", False),
            "status": "unknown",
            "last_error": None,
            "category": data.get("category", "function"),
            "data_mappings": data.get("data_mappings", []),
            "created_at": now,
            "updated_at": now,
        }
        await self._col.insert_one(doc)
        doc.pop("_id", None)
        logger.info(f"创建 MCP 服务器: {server_id} (category={doc['category']})")
        return doc

    async def list_servers(self) -> List[Dict]:
        """查询所有 MCP 服务器配置"""
        docs = []
        async for doc in self._col.find({}, {"_id": 0}):
            docs.append(doc)
        return docs

    async def get_server(self, server_id: str) -> Optional[Dict]:
        """查询单个 MCP 服务器"""
        doc = await self._col.find_one({"server_id": server_id}, {"_id": 0})
        return doc

    async def update_server(self, server_id: str, data: Dict) -> Optional[Dict]:
        """更新 MCP 服务器配置"""
        allowed = {"name", "description", "transport_type", "connection", "is_enabled", "category", "data_mappings"}
        update = {k: v for k, v in data.items() if k in allowed}
        if not update:
            return await self.get_server(server_id)
        update["updated_at"] = _now_iso()
        await self._col.update_one({"server_id": server_id}, {"$set": update})
        return await self.get_server(server_id)

    async def delete_server(self, server_id: str) -> bool:
        """删除 MCP 服务器配置并注销工具"""
        doc = await self.get_server(server_id)
        if doc is None:
            return False
        _unregister_server_tools(server_id, doc.get("discovered_tools", []))
        result = await self._col.delete_one({"server_id": server_id})
        return result.deleted_count > 0

    # ------------------------------------------------------------------
    # 连接测试 & 工具发现
    # ------------------------------------------------------------------

    async def test_connection(self, server_id: str) -> Dict:
        """测试 MCP 服务器连接"""
        import asyncio

        doc = await self.get_server(server_id)
        if doc is None:
            return {"success": False, "error": "服务器不存在"}

        config = {"transport_type": doc["transport_type"], "connection": doc["connection"]}

        from core.tools.mcp.client_manager import get_mcp_client_manager

        manager = get_mcp_client_manager()
        # 在线程池中执行（manager 内部使用独立事件循环）
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, manager.test_connection, config)

        # 更新状态
        status = "active" if result["success"] else "error"
        await self._col.update_one(
            {"server_id": server_id},
            {
                "$set": {
                    "status": status,
                    "last_error": result.get("error"),
                    "updated_at": _now_iso(),
                }
            },
        )
        return result

    async def discover_tools(self, server_id: str) -> Dict:
        """发现工具并缓存到数据库，若服务器已启用则同步注册到 ToolRegistry"""
        import asyncio

        doc = await self.get_server(server_id)
        if doc is None:
            return {"success": False, "error": "服务器不存在", "tools": []}

        config = {"transport_type": doc["transport_type"], "connection": doc["connection"]}

        from core.tools.mcp.client_manager import get_mcp_client_manager

        manager = get_mcp_client_manager()
        logger.info(f"MCP discover_tools 开始 (server_id={server_id}, url={config.get('connection', {}).get('url', '')})")
        try:
            loop = asyncio.get_event_loop()
            tools = await loop.run_in_executor(None, manager.discover_tools, config)
        except Exception as e:
            logger.exception(
                f"MCP discover_tools 失败 (server_id={server_id}): {e}"
            )
            await self._col.update_one(
                {"server_id": server_id},
                {"$set": {"status": "error", "last_error": str(e), "updated_at": _now_iso()}},
            )
            return {"success": False, "error": str(e), "tools": []}

        # 缓存发现结果（需 sanitize：MongoDB 不允许 $ 前缀键，如 input_schema.$schema）
        tools_safe = _sanitize_for_mongo(tools)
        await self._col.update_one(
            {"server_id": server_id},
            {
                "$set": {
                    "discovered_tools": tools_safe,
                    "status": "active",
                    "last_error": None,
                    "updated_at": _now_iso(),
                }
            },
        )

        # 若已启用，立即注册到 ToolRegistry
        if doc.get("is_enabled", False):
            _category = doc.get("category", "function")
            _data_mappings = doc.get("data_mappings", [])
            _sname = doc.get("name", server_id)
            for tool_meta in tools:
                _register_mcp_tool(
                    server_id, tool_meta, config,
                    category=_category,
                    data_mappings=_data_mappings,
                    server_name=_sname,
                )

        logger.info(f"发现 {len(tools)} 个 MCP 工具 (server_id={server_id})")
        return {
            "success": True,
            "server_id": server_id,
            "tool_count": len(tools),
            "tools": tools,
            "registered": doc.get("is_enabled", False),
            "error": None,
        }

    # ------------------------------------------------------------------
    # 工具列表 / 探测调用
    # ------------------------------------------------------------------

    async def list_server_tools(self, server_id: str) -> List[Dict]:
        """返回服务器的已发现工具列表（从数据库缓存读取，不重新连接服务器）"""
        doc = await self.get_server(server_id)
        if doc is None:
            return []
        return doc.get("discovered_tools", [])

    async def probe_tool(self, server_id: str, tool_name: str, arguments: Dict) -> Dict:
        """调用 MCP 工具并返回原始结果及自动提取的输出字段"""
        import asyncio

        doc = await self.get_server(server_id)
        if doc is None:
            return {"success": False, "error": "服务器不存在", "detected_fields": []}

        config = {"transport_type": doc["transport_type"], "connection": doc["connection"]}

        from core.tools.mcp.client_manager import get_mcp_client_manager

        manager = get_mcp_client_manager()
        try:
            loop = asyncio.get_event_loop()
            raw = await loop.run_in_executor(
                None, manager.call_tool, config, tool_name, arguments, 30
            )
        except Exception as e:
            logger.warning(f"探测 MCP 工具失败 ({server_id}/{tool_name}): {e}")
            return {"success": False, "error": str(e), "raw_result": "", "detected_fields": []}

        detected = _extract_output_fields(raw)
        return {
            "success": True,
            "tool_name": tool_name,
            "raw_result": raw[:3000],
            "detected_fields": detected,
        }

    # ------------------------------------------------------------------
    # AI 智能字段映射
    # ------------------------------------------------------------------

    def _get_collection_field_descriptions(self, collection_name: str) -> Dict[str, str]:
        """从后端 Pydantic 模型中动态提取字段描述"""
        # 集合名称到 Pydantic 模型的映射
        model_mapping = {
            "market_quotes": "MarketQuotesExtended",
            "stock_basic_info": "StockBasicInfoExtended",
            "stock_daily_quotes": "StockDailyQuote",
            "stock_financial_data": "StockFinancialData",
            "stock_news": "StockNews",
        }

        model_name = model_mapping.get(collection_name)
        if not model_name:
            return {}

        try:
            # 动态导入模型
            from app.models.stock_models import (
                MarketQuotesExtended,
                StockBasicInfoExtended,
                StockDailyQuote,
                StockFinancialData,
                StockNews,
            )

            models = {
                "MarketQuotesExtended": MarketQuotesExtended,
                "StockBasicInfoExtended": StockBasicInfoExtended,
                "StockDailyQuote": StockDailyQuote,
                "StockFinancialData": StockFinancialData,
                "StockNews": StockNews,
            }

            model = models.get(model_name)
            if not model:
                return {}

            # 从 Pydantic 模型的 model_fields 中提取字段描述
            descriptions = {}
            if hasattr(model, "model_fields"):
                for field_name, field_info in model.model_fields.items():
                    # 获取字段的 description
                    if hasattr(field_info, "description") and field_info.description:
                        descriptions[field_name] = field_info.description

            return descriptions
        except Exception as e:
            logger.warning(f"[AI Mapping] 提取模型字段描述失败 ({collection_name}): {e}")
            return {}

    async def ai_suggest_mapping(
        self, server_id: str, tool_name: str, target_collection: str
    ) -> Dict:
        """
        使用 LLM 自动生成 MCP 工具输出字段 → MongoDB 集合字段的映射建议。

        步骤：
        1. 探测工具输出字段（实际调用 MCP 工具，空参数）
        2. 从 discovered_tools 缓存获取工具描述
        3. 采样目标集合现有文档，提取字段名
        4. 调用 LLM 生成映射建议
        """
        import json as _json
        import re

        # 1. 获取服务器配置
        doc = await self.get_server(server_id)
        if doc is None:
            return {"success": False, "error": "服务器不存在", "mappings": []}

        # 2. 从缓存获取工具描述
        tool_desc = ""
        for t in (doc.get("discovered_tools") or []):
            if t["name"] == tool_name:
                tool_desc = t.get("description", "")
                break

        # 3. 探测工具输出字段
        probe_result = await self.probe_tool(server_id, tool_name, {})
        detected_fields: List[Dict] = probe_result.get("detected_fields", [])
        if not probe_result.get("success"):
            logger.warning(f"[AI Mapping] 工具探测失败，将仅凭描述推断: {probe_result.get('error')}")

        # 4. 采样目标集合现有字段
        collection_fields: List[str] = []
        if target_collection:
            try:
                sample_docs = await self._db[target_collection].find(
                    {}, {"_id": 0}
                ).limit(3).to_list(3)
                fields_set: set = set()
                for d in sample_docs:
                    fields_set.update(d.keys())
                collection_fields = sorted(fields_set)
            except Exception as e:
                logger.warning(f"[AI Mapping] 采样集合 {target_collection} 失败: {e}")

        # 获取集合字段的描述信息
        collection_field_descriptions = self._get_collection_field_descriptions(target_collection)

        # 5. 初始化 LLM 客户端
        from app.services.intelligent_assistant_service import get_reasoning_llm_config
        from core.llm import UnifiedLLMClient, Message

        config = await get_reasoning_llm_config(self._db)
        if not config:
            return {"success": False, "error": "未配置 LLM，请先在系统设置中配置大模型", "mappings": []}

        client = UnifiedLLMClient.from_config(config)

        # 6. 构建 Prompt
        fields_info = "\n".join(
            f"  - {f['name']} ({f['type']}): 样本值={f['sample']}"
            for f in detected_fields
        ) or "  （探测失败，请根据工具描述推断字段）"

        collection_info = (
            "  " + "、".join(collection_fields)
            if collection_fields
            else "  （集合为空或不存在，请将 target 与 source 保持一致）"
        )

        prompt = f"""你是一个数据集成专家，请帮我完成 MCP 工具输出字段到 MongoDB 集合字段的映射配置。

## MCP 工具信息
- 工具名称: {tool_name}
- 工具描述: {tool_desc or "（无描述）"}
- 探测到的输出字段:
{fields_info}

## 目标 MongoDB 集合: {target_collection or "（未指定）"}
- 集合现有字段:
{collection_info}

## 输出要求
只返回 JSON，不要有任何其他内容：
{{
  "mappings": [
    {{"source": "MCP输出字段名", "target": "MongoDB目标字段名", "reason": "映射理由（简短）"}}
  ],
  "explanation": "整体映射说明（1-2句话）"
}}

## 映射规则
1. 字段名相同 → 直接映射
2. 语义相近 → 映射（如 close_price → close，stock_code → code）
3. 有现有字段时，优先匹配现有字段名，保持集合字段一致性
4. 集合为空时，target 与 source 保持一致
5. 纯元数据字段（如 _id、__v）可跳过
6. 只返回 JSON，不要 markdown 代码块"""

        # 7. 调用 LLM
        try:
            messages = [Message(role="user", content=prompt)]
            resp = await client.achat(messages, temperature=0.1)
            content = resp.content.strip()

            # 兼容 LLM 可能包裹 markdown 代码块
            match = re.search(r'\{[\s\S]*\}', content)
            if not match:
                return {"success": False, "error": "LLM 返回格式异常，请重试", "mappings": []}

            result = _json.loads(match.group())

            # 构建完整的字段映射列表：包含 AI 建议的映射 + 未映射的字段
            ai_mappings = result.get("mappings", [])
            ai_mapped_sources = {m["source"] for m in ai_mappings}

            # 添加未被 AI 映射的字段（用户可以自己决定是否映射）
            all_mappings = list(ai_mappings)
            for field in detected_fields:
                if field["name"] not in ai_mapped_sources:
                    all_mappings.append({
                        "source": field["name"],
                        "target": "",  # 用户需要自己填写
                        "reason": "未被 AI 映射，请手动配置"
                    })

            return {
                "success": True,
                "mappings": all_mappings,
                "explanation": result.get("explanation", ""),
                "detected_fields": detected_fields,
                "collection_fields": collection_fields,
                "collection_field_descriptions": collection_field_descriptions,
            }
        except _json.JSONDecodeError:
            return {"success": False, "error": "LLM 返回内容无法解析为 JSON，请重试", "mappings": []}
        except Exception as e:
            logger.error(f"[AI Mapping] LLM 调用失败: {e}", exc_info=True)
            return {"success": False, "error": f"AI 调用失败: {str(e)}", "mappings": []}

    # ------------------------------------------------------------------
    # 启用 / 禁用
    # ------------------------------------------------------------------

    async def toggle_server(self, server_id: str, enabled: bool) -> Optional[Dict]:
        """启用或禁用 MCP 服务器（同步影响 ToolRegistry）"""
        doc = await self.get_server(server_id)
        if doc is None:
            return None

        config = {"transport_type": doc["transport_type"], "connection": doc["connection"]}
        tools = doc.get("discovered_tools", [])

        if enabled:
            _category = doc.get("category", "function")
            _data_mappings = doc.get("data_mappings", [])
            _sname = doc.get("name", server_id)
            for tool_meta in tools:
                _register_mcp_tool(
                    server_id, tool_meta, config,
                    category=_category,
                    data_mappings=_data_mappings,
                    server_name=_sname,
                )
        else:
            _unregister_server_tools(server_id, tools)

        await self._col.update_one(
            {"server_id": server_id},
            {"$set": {"is_enabled": enabled, "updated_at": _now_iso()}},
        )
        return await self.get_server(server_id)

    # ------------------------------------------------------------------
    # 应用启动时恢复
    # ------------------------------------------------------------------

    async def restore_enabled_servers(self) -> None:
        """应用启动时，将所有已启用服务器的工具重新注册到 ToolRegistry"""
        count = 0
        async for doc in self._col.find({"is_enabled": True}):
            server_id = doc["server_id"]
            config = {"transport_type": doc["transport_type"], "connection": doc["connection"]}
            _category = doc.get("category", "function")
            _data_mappings = doc.get("data_mappings", [])
            _sname = doc.get("name", server_id)
            for tool_meta in doc.get("discovered_tools", []):
                try:
                    _register_mcp_tool(
                        server_id, tool_meta, config,
                        category=_category,
                        data_mappings=_data_mappings,
                        server_name=_sname,
                    )
                    count += 1
                except Exception as e:
                    logger.warning(f"恢复 MCP 工具失败 ({server_id}/{tool_meta.get('name')}): {e}")
        logger.info(f"✅ 恢复了 {count} 个 MCP 工具")

