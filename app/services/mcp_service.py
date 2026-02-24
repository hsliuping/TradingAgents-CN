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


def _tool_id(server_id: str, tool_name: str) -> str:
    """生成统一的工具 ID"""
    return f"mcp_{server_id}_{tool_name}"


def _register_mcp_tool(server_id: str, tool_meta: Dict, connection_config: Dict) -> None:
    """将单个 MCP 工具注册到 ToolRegistry"""
    from core.tools.registry import get_tool_registry
    from core.tools.mcp.client_manager import get_mcp_client_manager

    registry = get_tool_registry()
    tid = _tool_id(server_id, tool_meta["name"])
    tool_name = tool_meta["name"]

    if registry.has_tool(tid):
        logger.debug(f"MCP 工具已存在，跳过: {tid}")
        return

    manager = get_mcp_client_manager()

    def _executor(**kwargs) -> str:
        """同步执行 MCP 工具"""
        return manager.call_tool(
            config=connection_config,
            tool_name=tool_name,
            arguments=kwargs,
        )

    registry.register_function(
        tool_id=tid,
        func=_executor,
        name=f"[MCP] {tool_meta['name']}",
        category="mcp",
        description=tool_meta.get("description", ""),
        is_online=True,
        override=True,
    )
    logger.info(f"✅ 注册 MCP 工具: {tid}")


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
            "created_at": now,
            "updated_at": now,
        }
        await self._col.insert_one(doc)
        doc.pop("_id", None)
        logger.info(f"创建 MCP 服务器: {server_id}")
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
        allowed = {"name", "description", "transport_type", "connection", "is_enabled"}
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

        # 缓存发现结果
        await self._col.update_one(
            {"server_id": server_id},
            {
                "$set": {
                    "discovered_tools": tools,
                    "status": "active",
                    "last_error": None,
                    "updated_at": _now_iso(),
                }
            },
        )

        # 若已启用，立即注册到 ToolRegistry
        if doc.get("is_enabled", False):
            for tool_meta in tools:
                _register_mcp_tool(server_id, tool_meta, config)

        logger.info(f"发现 {len(tools)} 个 MCP 工具 (server_id={server_id})")
        return {"success": True, "tools": tools, "error": None}

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
            for tool_meta in tools:
                _register_mcp_tool(server_id, tool_meta, config)
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
            for tool_meta in doc.get("discovered_tools", []):
                try:
                    _register_mcp_tool(server_id, tool_meta, config)
                    count += 1
                except Exception as e:
                    logger.warning(f"恢复 MCP 工具失败 ({server_id}/{tool_meta.get('name')}): {e}")
        logger.info(f"✅ 恢复了 {count} 个 MCP 工具")

