"""
模板调试路由 (v1.0)

⚠️⚠️⚠️ DEPRECATED - v1 调试系统 ⚠️⚠️⚠️
====================================
此路由是 v1.0 调试系统的一部分，已废弃。
- 废弃日期: 2026-06-23
- 移除计划: v4.0 版本（与 v1 Agent 同步移除）

请使用新的调试系统：
- v2 Agent 调试：通过 Agent 工坊测试功能
- 工作流调试：通过 WorkflowEngine 的 debug_mode 参数

注意：此路由仍有前端页面 TemplateDebug.vue 使用，
移除前需要先迁移前端页面或废弃相关功能。
====================================
"""

from datetime import datetime
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field
from app.routers.auth_db import get_current_user
from app.core.database import get_mongo_db
from app.core.permissions import require_pro
from app.services.license_service import LicenseInfo
from tradingagents.agents.utils.agent_context import AgentContext

# 🔥 发出废弃警告
import warnings
warnings.warn(
    "templates_debug router is DEPRECATED (v1.0 debug system). "
    "Please use Agent Workshop test feature or WorkflowEngine debug_mode instead. "
    "This router will be removed in v4.0 along with v1 Agents.",
    DeprecationWarning,
    stacklevel=2
)

router = APIRouter(prefix="/api/templates/debug", tags=["templates-debug"])


def _build_input_contract(metadata: Any) -> List[Dict[str, Any]]:
    inputs = getattr(metadata, "inputs", None) or []
    input_contract: List[Dict[str, Any]] = []

    for item in inputs:
        name = getattr(item, "name", "")
        if not name:
            continue
        source = str(getattr(item, "source", "request") or "request")
        state_field = getattr(item, "state_field", None)
        source_state_fields = getattr(item, "source_state_fields", None) or []
        producer_hint = getattr(item, "producer_hint", None)
        input_contract.append({
            "name": str(name),
            "type": str(getattr(item, "type", "string") or "string"),
            "description": str(getattr(item, "description", "") or ""),
            "required": bool(getattr(item, "required", True)),
            "source": source,
            "state_field": str(state_field or (name if source == "state" else "")),
            "source_state_fields": [str(field) for field in source_state_fields if str(field or "").strip()],
            "producer_hint": str(producer_hint or ""),
        })

    return input_contract


def _build_debug_inputs(metadata: Any) -> List[Dict[str, str]]:
    base_input_names = {
        "ticker",
        "stock_symbol",
        "company_of_interest",
        "analysis_date",
        "trade_date",
        "market_type",
        "context",
        "workflow_id",
    }
    input_contract = _build_input_contract(metadata)
    debug_inputs: List[Dict[str, str]] = []

    state_inputs = [item for item in input_contract if item.get("source") == "state"]
    if state_inputs:
        return [
            {
                "name": str(item.get("name", "")),
                "type": str(item.get("type", "string") or "string"),
                "description": str(item.get("description", "") or ""),
            }
            for item in state_inputs
            if item.get("name")
        ]

    inputs = getattr(metadata, "inputs", None) or []
    for item in inputs:
        name = getattr(item, "name", "")
        if not name or name in base_input_names:
            continue
        debug_inputs.append({
            "name": str(name),
            "type": str(getattr(item, "type", "string") or "string"),
            "description": str(getattr(item, "description", "") or ""),
        })

    return debug_inputs

@router.get("/agents")
async def list_debug_agents():
    """获取所有可用于调试的agents"""
    import logging
    logger = logging.getLogger("webapi")

    try:
        logger.info("开始获取调试agents列表...")
        # v1.0 硬编码的agent类型
        v1_agents = [
            {"id": "market", "name": "市场分析师", "version": "v1.0", "category": "analyst", "maintenance_status": "unmaintained"},
            {"id": "fundamentals", "name": "基本面分析师", "version": "v1.0", "category": "analyst", "maintenance_status": "unmaintained"},
            {"id": "news", "name": "新闻分析师", "version": "v1.0", "category": "analyst", "maintenance_status": "unmaintained"},
            {"id": "social", "name": "社交媒体分析师", "version": "v1.0", "category": "analyst", "maintenance_status": "unmaintained"},
            {"id": "index_analyst", "name": "指数分析师", "version": "v1.0", "category": "analyst", "maintenance_status": "unmaintained"},
            {"id": "sector_analyst", "name": "行业分析师", "version": "v1.0", "category": "analyst", "maintenance_status": "unmaintained"},
        ]

        # v2.0 注册的agents
        v2_agents = []
        try:
            from core.agents import get_registry
            registry = get_registry()

            for metadata in registry.list_all():
                try:
                    # 包含可直接单点调试的 v2 agent 类别
                    category_value = getattr(metadata.category, 'value', str(metadata.category))
                    if category_value in ["analyst", "researcher", "risk", "manager", "trader"]:
                        debug_inputs = _build_debug_inputs(metadata)
                        input_contract = _build_input_contract(metadata)
                        v2_agents.append({
                            "id": metadata.id,
                            "name": metadata.name,
                            "version": "v2.0",
                            "category": category_value,
                            "description": getattr(metadata, 'description', ''),
                            "debug_inputs": debug_inputs,
                            "input_contract": input_contract,
                            "maturity_level": getattr(metadata, 'maturity_level', 'stable'),
                            "input_mode": getattr(metadata, 'input_mode', 'standalone'),
                            "debug_replay_mode": getattr(metadata, 'debug_replay_mode', 'direct'),
                            "maintenance_status": getattr(metadata, 'maintenance_status', 'maintained'),
                            "callable_surfaces": list(getattr(metadata, 'callable_surfaces', []) or []),
                        })
                except Exception as e:
                    logger.warning(f"处理agent metadata失败: {metadata.id if hasattr(metadata, 'id') else 'unknown'}, 错误: {e}")
                    continue
        except Exception as e:
            logger.warning(f"获取v2.0 agents失败: {e}")
            # 如果获取v2.0 agents失败，继续使用空列表

        # 合并并返回
        all_agents = v1_agents + v2_agents
        logger.info(f"成功获取调试agents: v1.0={len(v1_agents)}个, v2.0={len(v2_agents)}个, 总计={len(all_agents)}个")
        return {"success": True, "data": all_agents}

    except Exception as e:
        logger.error(f"获取调试agents失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class DebugLLM(BaseModel):
    provider: str = Field(...)
    model: str = Field(...)
    temperature: float = Field(0.2)  # 股票分析推荐值：0.2-0.3（快速分析），0.1-0.2（深度分析）
    max_tokens: int = Field(2000)
    backend_url: Optional[str] = None
    api_key: Optional[str] = None

class DebugStock(BaseModel):
    symbol: str = Field(...)
    market_type: Optional[str] = None
    analysis_date: Optional[str] = None

class AnalystDebugRequest(BaseModel):
    analyst_type: str = Field(...)
    agent_version: Optional[str] = None
    template_id: Optional[str] = None
    use_current: bool = Field(True)
    is_debug_mode: Optional[bool] = None  # 🔥 前端可传递调试模式标志，如果未传递则使用默认逻辑
    workflow_id: Optional[str] = None  # 🆕 工作流ID（用于加载流程专属提示词）
    llm: DebugLLM
    stock: DebugStock
    dataopts: Optional[Dict[str, Any]] = None
    prompt_overrides: Optional[Dict[str, Any]] = None
    extra_state: Optional[Dict[str, Any]] = None


class WorkflowDebugRequest(BaseModel):
    """工作流调试请求"""
    workflow_id: str = Field(..., description="工作流ID")
    llm: DebugLLM
    stock: DebugStock
    dataopts: Optional[Dict[str, Any]] = None
    prompt_overrides: Optional[Dict[str, Any]] = None


def _serialize_debug_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _serialize_debug_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_serialize_debug_value(item) for item in value]
    return value


def _extract_invocation_summary(doc: Dict[str, Any]) -> str:
    result = doc.get("result") if isinstance(doc.get("result"), dict) else {}
    output_text = result.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()[:300]
    error_message = result.get("error_message")
    if isinstance(error_message, str) and error_message.strip():
        return error_message.strip()[:300]
    structured_output = result.get("structured_output")
    if isinstance(structured_output, dict):
        for key in ("final_report", "analysis_report", "summary", "report"):
            value = structured_output.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()[:300]
    return ""


def _normalize_invocation_doc(source_collection: str, doc: Dict[str, Any]) -> Dict[str, Any]:
    request = doc.get("request") if isinstance(doc.get("request"), dict) else {}
    result = doc.get("result") if isinstance(doc.get("result"), dict) else {}
    provenance = request.get("provenance") if isinstance(request.get("provenance"), dict) else {}
    payload = request.get("payload") if isinstance(request.get("payload"), dict) else {}

    source_type = provenance.get("source_type")
    source_id = provenance.get("source_id")
    workflow_id = doc.get("workflow_id") or provenance.get("workflow_id")
    execution_id = doc.get("execution_id") or provenance.get("session_id")
    thread_id = doc.get("thread_id") or provenance.get("thread_id")
    step_id = doc.get("step_id") or provenance.get("step_id")
    symbol = payload.get("symbol") or payload.get("ticker") or payload.get("stock_symbol")

    return {
        "invocation_id": doc.get("invocation_id"),
        "root_invocation_id": doc.get("root_invocation_id") or request.get("metadata", {}).get("root_invocation_id"),
        "parent_invocation_id": doc.get("parent_invocation_id") or request.get("metadata", {}).get("parent_invocation_id"),
        "source_collection": source_collection,
        "source_type": source_type,
        "source_id": source_id or doc.get("source_agent_id") or workflow_id,
        "target_type": doc.get("target_type") or request.get("target_type"),
        "target_id": doc.get("target_id") or request.get("target_id"),
        "status": doc.get("status") or result.get("status"),
        "user_id": doc.get("user_id") or provenance.get("user_id"),
        "workflow_id": workflow_id,
        "execution_id": execution_id,
        "thread_id": thread_id,
        "step_id": step_id,
        "symbol": symbol,
        "summary": _extract_invocation_summary(doc),
        "output_field": result.get("output_field"),
        "error_message": result.get("error_message"),
        "started_at": _serialize_debug_value(result.get("started_at")),
        "completed_at": _serialize_debug_value(result.get("completed_at")),
        "created_at": _serialize_debug_value(doc.get("created_at")),
        "updated_at": _serialize_debug_value(doc.get("updated_at")),
        "request": _serialize_debug_value(request),
        "result": _serialize_debug_value(result),
    }


def _build_invocation_chain(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    sorted_items = sorted(
        items,
        key=lambda item: item.get("created_at") or item.get("updated_at") or "",
    )
    latest_item = sorted_items[-1] if sorted_items else {}
    root_item = next(
        (item for item in sorted_items if item.get("invocation_id") == item.get("root_invocation_id")),
        sorted_items[0] if sorted_items else {},
    )
    status_counts: Dict[str, int] = {}
    for item in sorted_items:
        status = str(item.get("status") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1

    return {
        "root_invocation_id": root_item.get("root_invocation_id") or root_item.get("invocation_id"),
        "symbol": root_item.get("symbol") or latest_item.get("symbol"),
        "workflow_id": root_item.get("workflow_id") or latest_item.get("workflow_id"),
        "thread_id": root_item.get("thread_id") or latest_item.get("thread_id"),
        "latest_created_at": latest_item.get("created_at") or latest_item.get("updated_at"),
        "summary": latest_item.get("summary") or root_item.get("summary") or "",
        "status_counts": status_counts,
        "items": sorted_items,
        "count": len(sorted_items),
    }


def _group_invocation_chains(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for item in items:
        root_id = item.get("root_invocation_id") or item.get("invocation_id") or "unknown"
        grouped.setdefault(str(root_id), []).append(item)

    chains = [_build_invocation_chain(chain_items) for chain_items in grouped.values()]
    chains.sort(key=lambda chain: chain.get("latest_created_at") or "", reverse=True)
    return chains


def _build_invocation_query(
    *,
    user_id: str,
    target_id: Optional[str],
    status: Optional[str],
    symbol: Optional[str],
    workflow_id: Optional[str],
    execution_id: Optional[str],
    thread_id: Optional[str],
    root_invocation_id: Optional[str],
    source_collection: str,
) -> Dict[str, Any]:
    query: Dict[str, Any] = {"user_id": user_id}

    if target_id:
        query["target_id"] = target_id.strip()
    if status:
        query["status"] = status.strip()
    if symbol:
        query["request.payload.symbol"] = symbol.strip()
    if root_invocation_id:
        query["root_invocation_id"] = root_invocation_id.strip()

    if source_collection == "workflow_agent_invocations":
        if workflow_id:
            query["workflow_id"] = workflow_id.strip()
        if execution_id:
            query["execution_id"] = execution_id.strip()
    elif source_collection == "agent_agent_invocations":
        if workflow_id:
            query["workflow_id"] = workflow_id.strip()
        if execution_id:
            query["execution_id"] = execution_id.strip()
        if thread_id:
            query["thread_id"] = thread_id.strip()
    elif source_collection == "assistant_agent_invocations":
        if thread_id:
            query["thread_id"] = thread_id.strip()

    return query

@router.post("/analyst")
async def debug_analyst(
    req: AnalystDebugRequest,
    user: dict = Depends(get_current_user),
    license: LicenseInfo = Depends(require_pro)  # 高级学员专属功能
):
    try:
        import logging
        logger = logging.getLogger("webapi")

        # 基本参数校验
        # 只有大盘分析师不需要股票代码，其他分析师都需要
        # 板块分析师需要股票代码来分析该股票所属的行业/板块
        needs_symbol = req.analyst_type != "index_analyst"
        if needs_symbol and (not req.stock.symbol or not str(req.stock.symbol).strip()):
            raise HTTPException(status_code=400, detail="stock.symbol 不能为空")
        if not req.llm.model or not str(req.llm.model).strip():
            raise HTTPException(status_code=400, detail="llm.model 不能为空")

        from tradingagents.graph.trading_graph import TradingAgentsGraph
        from tradingagents.default_config import DEFAULT_CONFIG
        from tradingagents.utils.template_client import get_template_client
        from tradingagents.agents.utils.agent_context import AgentContext

        # 🔥 打印调试信息：请求参数
        logger.info("=" * 80)
        logger.info("🔍 [调试接口] 收到请求参数:")
        logger.info(f"   analyst_type: {req.analyst_type}")
        logger.info(f"   llm.provider: {req.llm.provider}")
        logger.info(f"   llm.model: {req.llm.model}")
        logger.info(f"   llm.backend_url: {req.llm.backend_url}")
        logger.info(f"   llm.temperature: {req.llm.temperature}")
        logger.info(f"   llm.max_tokens: {req.llm.max_tokens}")
        logger.info(f"   stock.symbol: {req.stock.symbol}")
        logger.info(f"   stock.analysis_date: {req.stock.analysis_date}")
        logger.info("=" * 80)

        cfg = DEFAULT_CONFIG.copy()
        cfg["llm_provider"] = req.llm.provider

        # 🔥 从数据库获取 backend_url 和 API Key（优先级：前端指定 > 数据库配置 > 默认值）
        if req.llm.backend_url:
            # 如果前端明确指定了 backend_url，使用前端的值
            cfg["backend_url"] = req.llm.backend_url
            logger.info(f"✅ [v1.0调试] 使用前端指定的 backend_url: {cfg['backend_url']}")
        else:
            # 如果前端没有指定，从数据库获取配置（和单股分析一样）
            try:
                from app.services.simple_analysis_service import get_provider_and_url_by_model_sync
                provider_info = get_provider_and_url_by_model_sync(req.llm.model)
                cfg["backend_url"] = provider_info["backend_url"]
                cfg["quick_api_key"] = provider_info.get("api_key")
                cfg["deep_api_key"] = provider_info.get("api_key")
                logger.info(f"✅ [v1.0调试] 从数据库获取配置: backend_url={cfg['backend_url']}, provider={provider_info.get('provider')}")
            except Exception as e:
                logger.warning(f"⚠️ [v1.0调试] 无法从数据库获取配置: {e}，使用默认值")
                # 回退到硬编码的默认值
                provider_urls = {
                    "dashscope": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                    "openai": "https://api.openai.com/v1",
                    "deepseek": "https://api.deepseek.com",
                    "google": "https://generativelanguage.googleapis.com/v1beta",
                    "anthropic": "https://api.anthropic.com",
                    "ollama": "http://localhost:11434",
                }
                cfg["backend_url"] = provider_urls.get(req.llm.provider, cfg.get("backend_url", ""))

        cfg["quick_think_llm"] = req.llm.model
        cfg["deep_think_llm"] = req.llm.model
        
        # 🔥 根据 provider 设置合理的超时时间
        # Ollama 是本地模型，响应可能较慢，需要更长的超时时间
        if req.llm.provider.lower() == "ollama":
            timeout = 300  # Ollama 本地模型：300秒（5分钟）
            logger.info(f"🔧 [v1.0调试] Ollama 本地模型，使用超长超时时间: {timeout}秒")
        else:
            timeout = 180  # 其他云服务：180秒（3分钟）
            logger.info(f"🔧 [v1.0调试] {req.llm.provider} 云服务，使用超时时间: {timeout}秒")
        
        cfg["quick_model_config"] = {
            "max_tokens": req.llm.max_tokens, 
            "temperature": req.llm.temperature,
            "timeout": timeout
        }
        cfg["deep_model_config"] = {
            "max_tokens": req.llm.max_tokens, 
            "temperature": req.llm.temperature,
            "timeout": timeout
        }

        # 🔥 如果前端提供了 API Key，添加到配置中
        if req.llm.api_key:
            cfg["quick_api_key"] = req.llm.api_key
            cfg["deep_api_key"] = req.llm.api_key
            logger.info(f"✅ [调试接口] 使用前端提供的 API Key")
        else:
            logger.info(f"ℹ️ [调试接口] 未提供 API Key，将使用环境变量或数据库配置")

        # 🔥 打印配置信息
        logger.info("=" * 80)
        logger.info("🔍 [调试接口] 最终配置:")
        logger.info(f"   llm_provider: {cfg['llm_provider']}")
        logger.info(f"   backend_url: {cfg['backend_url']}")
        logger.info(f"   quick_think_llm: {cfg['quick_think_llm']}")
        logger.info(f"   deep_think_llm: {cfg['deep_think_llm']}")
        logger.info(f"   quick_model_config: {cfg['quick_model_config']}")
        logger.info(f"   deep_model_config: {cfg['deep_model_config']}")
        logger.info(f"   quick_api_key: {'已配置' if cfg.get('quick_api_key') else '未配置'}")
        logger.info(f"   deep_api_key: {'已配置' if cfg.get('deep_api_key') else '未配置'}")
        logger.info("=" * 80)

        # 🔥 验证 analyst_type 并确定使用的版本
        from core.agents import get_registry
        registry = get_registry()

        # 确定agent版本
        agent_version = "v1.0"  # 默认使用v1.0
        template_version = None

        # 如果指定了template_id，先检查模板版本
        if req.template_id:
            try:
                from app.services.prompt_template_service import PromptTemplateService
                template_service = PromptTemplateService()
                template = await template_service.get_template(req.template_id)
                if template:
                    template_version = getattr(template, 'version', 1)
                    # 根据模板版本确定agent版本
                    if template_version >= 2:
                        agent_version = "v2.0"
                    logger.info(f"🔍 [调试接口] 模板版本: {template_version}, 使用agent版本: {agent_version}")
            except Exception as e:
                logger.warning(f"⚠️ [调试接口] 获取模板版本失败: {e}, 使用默认v1.0")

        # 验证agent类型
        v1_types = [
            "market", "fundamentals", "news", "social", "index_analyst", "sector_analyst",
            "market_analyst", "fundamentals_analyst", "news_analyst", "social_media_analyst"
        ]

        if req.agent_version:
            agent_version = req.agent_version
            logger.info(f"🔍 [调试接口] 使用前端传递的agent_version: {agent_version}")
        elif str(req.analyst_type).endswith("_v2"):
            agent_version = "v2.0"
            logger.info(f"🔍 [调试接口] 根据analyst_type判定为v2.0: {req.analyst_type}")
        elif req.analyst_type in v1_types:
            agent_version = "v1.0"
            logger.info(f"🔍 [调试接口] 使用v1.0 agent类型: {req.analyst_type}")
        elif registry.is_registered(req.analyst_type):
            # v2.0 注册的agent
            agent_version = "v2.0"
            logger.info(f"🔍 [调试接口] 使用v2.0 agent类型: {req.analyst_type}")
        else:
            raise HTTPException(status_code=400, detail=f"invalid analyst_type: {req.analyst_type}")

        # 🔥 创建 AgentContext，包含所有必要参数
        # 调试模式优先级：前端传递的值 > 默认True（调试接口）
        is_debug_mode = req.is_debug_mode if req.is_debug_mode is not None else True

        ctx = AgentContext(
            user_id=str(user["id"]),
            preference_id="neutral",  # 默认使用 neutral 偏好
            session_id=None,
            request_id=None,
            is_debug_mode=is_debug_mode,  # 🔥 优先使用前端传递的值，否则默认为True
            debug_template_id=req.template_id,  # 调试模板ID（可选）
            workflow_id=req.workflow_id  # 🆕 工作流ID（用于加载流程专属提示词）
        )

        # 🔥 打印 AgentContext 信息
        logger.info("=" * 80)
        logger.info("🔍 [调试接口] AgentContext 参数:")
        logger.info(f"   user_id: {ctx.user_id}")
        logger.info(f"   preference_id: {ctx.preference_id}")
        logger.info(f"   session_id: {ctx.session_id}")
        logger.info(f"   request_id: {ctx.request_id}")
        logger.info(f"   is_debug_mode: {ctx.is_debug_mode} (前端传递: {req.is_debug_mode}, 最终值: {is_debug_mode})")
        logger.info(f"   debug_template_id: {ctx.debug_template_id}")
        logger.info(f"   workflow_id: {ctx.workflow_id}")  # 🆕
        logger.info("=" * 80)

        # 🔥 根据agent版本选择不同的执行路径
        logger.info("=" * 80)
        logger.info(f"🔍 [调试接口] 开始调用单个 Agent: {req.analyst_type} (版本: {agent_version})")
        logger.info("=" * 80)

        if str(agent_version).startswith("v2") or str(agent_version).startswith("2."):
            # 使用v2.0的新统一引擎
            return await _debug_v2_agent(req, ctx, cfg, user)
        else:
            # v1.0 旧引擎已停用
            import logging
            logging.getLogger("webapi").warning(
                f"[已停用] v1.0 agent 调试已停用，agent_version={agent_version}"
            )
            raise HTTPException(
                status_code=400,
                detail="[已停用] v1.0 agent 调试已停用，请指定 agent_version='v2'。"
                "详见 docs/99-archive/deprecated-features/legacy-agents-deprecation.md"
            )


    except HTTPException:
        raise
    except Exception as e:
        import logging
        logging.getLogger("webapi").error(f"模板调试接口执行异常: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


async def _debug_v1_agent(req: AnalystDebugRequest, ctx: AgentContext, cfg: dict, user: dict):
    """调试v1.0版本的agent"""
    import logging
    logger = logging.getLogger("webapi")
    logger.info(f"🔍 [v1.0调试] 开始调试v1.0 agent: {req.analyst_type}")

    # 🔥 映射v2.0的agent ID到v1.0的analyst_type
    v2_to_v1_mapping = {
        "fundamentals_analyst": "fundamentals",
        "market_analyst": "market",
        "news_analyst": "news",
        "social_media_analyst": "social",
        "index_analyst": "index_analyst",
        "sector_analyst": "sector_analyst"
    }

    # 如果是v2.0的agent ID，转换为v1.0的analyst_type
    analyst_type_for_graph = v2_to_v1_mapping.get(req.analyst_type, req.analyst_type)
    logger.info(f"🔍 [v1.0调试] 映射后的analyst_type: {analyst_type_for_graph}")

    # 创建 TradingAgentsGraph 以初始化 LLM 和 Toolkit
    from tradingagents.graph.trading_graph import TradingAgentsGraph
    graph_full = TradingAgentsGraph(selected_analysts=[analyst_type_for_graph], config=cfg)

    from tradingagents.agents import (
        create_fundamentals_analyst,
        create_market_analyst,
        create_news_analyst,
        create_social_media_analyst,
        create_index_analyst,
        create_sector_analyst
    )
    from tradingagents.agents.utils.agent_states import AgentState
    from langgraph.graph import StateGraph, START, END

    # 根据 analyst_type 选择对应的 Agent 创建函数
    agent_creators = {
        "fundamentals": create_fundamentals_analyst,
        "market": create_market_analyst,
        "news": create_news_analyst,
        "social": create_social_media_analyst,
        "index_analyst": create_index_analyst,
        "sector_analyst": create_sector_analyst
    }

    creator = agent_creators[analyst_type_for_graph]

    # 创建 Agent 节点
    logger.info(f"📝 [v1.0调试] 创建 {req.analyst_type} Agent 节点...")
    agent_node = creator(llm=graph_full.quick_thinking_llm, toolkit=graph_full.toolkit)

    # 获取对应的工具节点
    logger.info(f"📝 [v1.0调试] 获取 {req.analyst_type} 工具节点...")
    tool_nodes = graph_full._create_tool_nodes()
    tool_node = tool_nodes.get(req.analyst_type)

    if not tool_node:
        raise HTTPException(status_code=400, detail=f"无法获取 {req.analyst_type} 的工具节点")

    # 创建单节点图
    logger.info(f"📝 [v1.0调试] 创建单节点图...")
    workflow = StateGraph(AgentState)
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_node)

    # 添加边
    workflow.add_edge(START, "agent")
    workflow.add_edge("tools", "agent")

    # 添加条件边：如果有工具调用，执行工具；否则结束
    def should_continue(state):
        messages = state.get("messages", [])
        if messages:
            last_message = messages[-1]
            if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
                return "tools"
        return END

    workflow.add_conditional_edges("agent", should_continue)

    # 编译图
    graph = workflow.compile()

    # 创建初始状态
    needs_symbol = req.analyst_type != "index_analyst"
    analysis_date = req.stock.analysis_date or cfg.get("trade_date", "2025-08-20")

    if needs_symbol:
        ticker = str(req.stock.symbol).strip()
    else:
        ticker = "MARKET"  # 大盘分析使用特殊标识

    initial_state = AgentState(
        messages=[],
        company_of_interest=ticker,
        trade_date=analysis_date,
        sender="debug",
        market_report="",
        sentiment_report="",
        news_report="",
        fundamentals_report="",
        index_report="",
        sector_report="",
        market_tool_call_count=0,
        news_tool_call_count=0,
        sentiment_tool_call_count=0,
        fundamentals_tool_call_count=0,
        index_tool_call_count=0,
        sector_tool_call_count=0,
        agent_context=ctx.__dict__
    )

    if req.extra_state:
        initial_state.update(req.extra_state)

    # 🔥 执行图
    # 注意：graph.invoke() 是同步阻塞调用，但对于调试接口来说，这是可以接受的
    # 因为调试接口本身就是同步等待结果的
    logger.info(f"📝 [v1.0调试] 开始执行图...")
    logger.info(f"   - 超时配置: quick={cfg.get('quick_model_config', {}).get('timeout', 'N/A')}s, deep={cfg.get('deep_model_config', {}).get('timeout', 'N/A')}s")
    
    # 🔥 对于 Ollama，使用 run_in_executor 避免阻塞事件循环
    if req.llm.provider.lower() == "ollama":
        import asyncio
        import time
        loop = asyncio.get_event_loop()
        logger.info(f"🔧 [v1.0调试] Ollama 本地模型，使用 run_in_executor 避免阻塞事件循环")
        start_time = time.time()
        try:
            state = await loop.run_in_executor(
                None,
                lambda: graph.invoke(initial_state, config={"recursion_limit": 25})
            )
            elapsed_time = time.time() - start_time
            logger.info(f"✅ [v1.0调试] Ollama 调用成功，耗时: {elapsed_time:.2f}秒")
        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error(f"❌ [v1.0调试] Ollama 调用失败，耗时: {elapsed_time:.2f}秒，错误: {e}")
            raise
    else:
        state = graph.invoke(initial_state, config={"recursion_limit": 25})

    # 提取报告
    report_key_map = {
        "market": "market_report",
        "fundamentals": "fundamentals_report",
        "news": "news_report",
        "social": "sentiment_report",
        "index_analyst": "index_report",
        "sector_analyst": "sector_report"
    }
    report_key = report_key_map[req.analyst_type]

    # 从状态中提取报告
    if isinstance(state, dict):
        report = state.get(report_key, "")
    else:
        report = getattr(state, report_key, "")

    if not report.strip():
        report = "未生成分析报告"

    return await _build_debug_response(req, report)


async def _debug_v2_agent(req: AnalystDebugRequest, ctx: AgentContext, cfg: dict, user: dict):
    """调试v2.0版本的agent"""
    import logging
    logger = logging.getLogger("webapi")
    logger.info(f"🔍 [v2.0调试] 开始调试v2.0 agent: {req.analyst_type}")

    # 🔥 映射v1.0的agent ID到v2.0的ID
    # 如果前端传递的是v1.0的ID，但指定了v2.0版本，我们需要自动映射到v2.0的ID
    v1_to_v2_mapping = {
        "fundamentals_analyst": "fundamentals_analyst_v2",
        "market_analyst": "market_analyst_v2",
        "news_analyst": "news_analyst_v2",
        "social_media_analyst": "social_analyst_v2",
        "social_analyst": "social_analyst_v2",
        "sector_analyst": "sector_analyst_v2",
        "index_analyst": "index_analyst_v2",
        # 简写ID映射
        "fundamentals": "fundamentals_analyst_v2",
        "market": "market_analyst_v2",
        "news": "news_analyst_v2",
        "social": "social_analyst_v2",
    }

    agent_id = v1_to_v2_mapping.get(req.analyst_type, req.analyst_type)
    if agent_id != req.analyst_type:
        logger.info(f"🔄 [v2.0调试] 将Agent ID从 {req.analyst_type} 映射为 {agent_id}")

    try:
        # 使用新的统一引擎
        from core.workflow.engine import WorkflowEngine
        from core.workflow.templates.single_agent_workflow import SingleAgentWorkflow
        from core.agents import get_registry
        from tradingagents.graph.trading_graph import create_llm_by_provider
        from core.config.agent_config_manager import AgentConfigManager
        from core.config.binding_manager import BindingManager
        from app.core.database import get_mongo_db_sync

        # 获取agent注册信息
        registry = get_registry()
        if not registry.is_registered(agent_id):
            raise HTTPException(status_code=400, detail=f"Agent {agent_id} 未注册")

        # 🔥 从数据库获取 Agent 配置（使用同步版本）
        db = get_mongo_db_sync()
        agent_config_manager = AgentConfigManager()
        agent_config_manager.set_database(db)

        agent_config = agent_config_manager.get_agent_config(agent_id)
        if agent_config:
            logger.info(f"✅ [v2.0调试] 从数据库加载 Agent 配置: {agent_id}")
            logger.info(f"   - 启用状态: {agent_config.get('enabled', True)}")
            logger.info(f"   - 执行配置: {agent_config.get('config', {})}")
            logger.info(f"   - 提示词模板: {agent_config.get('prompt_template_type', 'N/A')}/{agent_config.get('prompt_template_name', 'N/A')}")
        else:
            logger.warning(f"⚠️ [v2.0调试] 未找到 Agent 配置，使用默认配置: {agent_id}")
            agent_config = {}

        # 🔥 从 BindingManager 获取绑定的工具
        binding_manager = BindingManager()
        binding_manager.set_database(db)

        tool_ids = binding_manager.get_tools_for_agent(agent_id)
        if tool_ids:
            logger.info(f"✅ [v2.0调试] 从 BindingManager 获取工具: {agent_id} -> {tool_ids}")
        else:
            logger.warning(f"⚠️ [v2.0调试] 未找到绑定的工具: {agent_id}")

        # 创建自定义 LLM（如果提供了配置）
        llm = None
        if req.llm and req.llm.model:
            try:
                # 🔥 从数据库获取 backend_url 和 API Key（优先级：前端指定 > 数据库配置 > 默认值）
                backend_url = None
                api_key = None
                
                if req.llm.backend_url and req.llm.backend_url.strip():
                    # 如果前端明确指定了 backend_url，使用前端的值
                    backend_url = req.llm.backend_url
                    logger.info(f"✅ [v2.0调试] 使用前端指定的 backend_url: {backend_url}")
                else:
                    # 如果前端没有指定，从数据库获取配置（和单股分析一样）
                    try:
                        from app.services.simple_analysis_service import get_provider_and_url_by_model_sync
                        provider_info = get_provider_and_url_by_model_sync(req.llm.model)
                        backend_url = provider_info["backend_url"]
                        api_key = provider_info.get("api_key")
                        logger.info(f"✅ [v2.0调试] 从数据库获取配置: backend_url={backend_url}, provider={provider_info.get('provider')}")
                    except Exception as e:
                        logger.warning(f"⚠️ [v2.0调试] 无法从数据库获取配置: {e}，backend_url 将设为 None")
                
                # 🔥 如果前端传递了 api_key，优先使用前端的值
                if req.llm.api_key:
                    api_key = req.llm.api_key
                    logger.info(f"✅ [v2.0调试] 使用前端指定的 API Key")
                elif not api_key:
                    # 如果数据库也没有获取到，尝试从 ConfigService 获取
                    try:
                        from app.services.config_service import ConfigService
                        config_service = ConfigService()
                        providers = await config_service.get_llm_providers()
                        target_provider = next((p for p in providers if p.name == req.llm.provider), None)
                        
                        if target_provider and target_provider.api_key:
                            api_key = target_provider.api_key
                            logger.info(f"✅ [v2.0调试] 从 ConfigService 获取到 {req.llm.provider} 的 API Key")
                        else:
                            logger.warning(f"⚠️ [v2.0调试] 未找到 {req.llm.provider} 的 API Key 配置")
                    except Exception as e:
                        logger.error(f"❌ [v2.0调试] 获取 API Key 失败: {e}")

                # 🔥 根据 provider 设置合理的超时时间
                # Ollama 是本地模型，响应可能较慢，需要更长的超时时间
                if req.llm.provider.lower() == "ollama":
                    timeout = 300  # Ollama 本地模型：300秒（5分钟）
                    logger.info(f"🔧 [v2.0调试] Ollama 本地模型，使用超长超时时间: {timeout}秒")
                else:
                    timeout = 180  # 其他云服务：180秒（3分钟）
                    logger.info(f"🔧 [v2.0调试] {req.llm.provider} 云服务，使用超时时间: {timeout}秒")
                
                llm = create_llm_by_provider(
                    provider=req.llm.provider,
                    model=req.llm.model,
                    temperature=req.llm.temperature,
                    max_tokens=req.llm.max_tokens,
                    backend_url=backend_url,
                    timeout=timeout,
                    api_key=api_key
                )
                logger.info(f"✅ [v2.0调试] 使用前端传入的 LLM 配置: {req.llm.provider}/{req.llm.model}")
            except Exception as e:
                logger.warning(f"⚠️ [v2.0调试] 创建自定义 LLM 失败: {e}")
                # 如果用户显式指定了 LLM 但创建失败，应该报错
                raise HTTPException(status_code=400, detail=f"无法创建指定的 LLM ({req.llm.provider}/{req.llm.model}): {e}")

        # 创建单agent工作流
        # 🔥 将 Agent 配置传递给工作流
        workflow_def = SingleAgentWorkflow(
            agent_id=agent_id,
            config={
                "stock_symbol": req.stock.symbol,
                "analysis_date": req.stock.analysis_date or "2025-12-16",
                "market_type": req.stock.market_type or "A股",
                # 🔥 传递 Agent 配置（包括执行配置、提示词模板等）
                "agent_config": agent_config
            }
        )

        # 创建工作流引擎
        logger.info(f"🔧 [v2.0调试] 创建工作流引擎...")
        logger.info(f"   - Agent ID: {agent_id}")
        logger.info(f"   - 工作流 ID: {workflow_def.id}")
        logger.info(f"   - 自定义 LLM: {'是' if llm else '否'}")

        engine = WorkflowEngine(legacy_config=cfg, llm=llm)
        engine.load(workflow_def)

        logger.info(f"✅ [v2.0调试] 工作流引擎已加载")

        # 准备输入
        # ⚠️ 注意：v2.0 Agent 需要 ticker 和 trade_date 参数
        inputs = {
            "stock_symbol": req.stock.symbol,
            "ticker": req.stock.symbol,  # 映射为 Agent 需要的参数名
            "analysis_date": req.stock.analysis_date or "2025-12-16",
            "trade_date": req.stock.analysis_date or "2025-12-16",  # 映射为 Agent 需要的参数名
            "company_of_interest": req.stock.symbol,  # 兼容旧字段
            "market_type": req.stock.market_type or "A股",
            "context": ctx,
            "skip_cache": True,  # 🔥 调试模式跳过缓存
            "prompt_overrides": req.prompt_overrides or {}
        }

        if req.extra_state:
            inputs.update(req.extra_state)
        
        # 🔥 准备工作流系统变量（和单股分析一样）
        try:
            from core.api.workflow_api import WorkflowAPI
            workflow_api = WorkflowAPI()
            system_vars = workflow_api._prepare_system_variables(
                stock_code=req.stock.symbol,
                analysis_date=inputs["analysis_date"]
            )
            # 将系统变量合并到 inputs 中
            inputs.update(system_vars)
            logger.info(f"✅ [v2.0调试] 已准备系统变量: {list(system_vars.keys())}")
        except Exception as e:
            logger.warning(f"⚠️ [v2.0调试] 准备系统变量失败: {e}，将使用默认值")

        # 执行工作流
        logger.info(f"=" * 100)
        logger.info(f"📝 [v2.0调试] 开始执行v2.0工作流...")
        logger.info(f"   - 输入参数: {list(inputs.keys())}")
        logger.info(f"   - 股票代码: {req.stock.symbol}")
        logger.info(f"   - 分析日期: {inputs['analysis_date']}")
        logger.info(f"   - LLM Provider: {req.llm.provider}")
        logger.info(f"   - LLM Model: {req.llm.model}")
        logger.info(f"   - 超时时间: {timeout if 'timeout' in locals() else 'N/A'}秒")
        logger.info(f"=" * 100)

        # 🔥 对于 Ollama，使用 asyncio.wait_for 设置总体超时时间
        import asyncio
        if req.llm.provider.lower() == "ollama":
            logger.info(f"🔧 [v2.0调试] Ollama 本地模型，设置总体超时时间: {timeout + 60}秒（LLM超时{timeout}秒 + 额外60秒缓冲）")
            try:
                result = await asyncio.wait_for(
                    engine.execute_async(inputs),
                    timeout=timeout + 60  # LLM超时时间 + 额外60秒缓冲
                )
            except asyncio.TimeoutError:
                logger.error(f"❌ [v2.0调试] 工作流执行超时（超过{timeout + 60}秒）")
                raise HTTPException(
                    status_code=504,
                    detail=f"工作流执行超时（超过{timeout + 60}秒）。Ollama 本地模型响应较慢，请检查模型是否正常运行。"
                )
        else:
            result = await engine.execute_async(inputs)

        logger.info(f"=" * 100)
        logger.info(f"✅ [v2.0调试] 工作流执行完成")
        logger.info(f"   - 返回字段: {list(result.keys()) if isinstance(result, dict) else 'N/A'}")
        if req.llm.provider.lower() == "ollama":
            logger.info(f"   - Ollama 调用成功，耗时在预期范围内")
        logger.info(f"=" * 100)

        # 提取报告
        try:
            metadata = registry.get_metadata(agent_id)
            output_field = None
            if metadata and hasattr(metadata, 'output_field') and getattr(metadata, 'output_field'):
                output_field = getattr(metadata, 'output_field')
            elif metadata and hasattr(metadata, 'outputs') and getattr(metadata, 'outputs'):
                outputs = getattr(metadata, 'outputs')
                if isinstance(outputs, list) and len(outputs) > 0 and hasattr(outputs[0], 'name'):
                    output_field = outputs[0].name
            report_key = output_field or "final_report"
            report = result.get(report_key, "")
            if not isinstance(report, str) or not report.strip():
                report = "未生成分析报告"
        except Exception as e:
            logger.warning(f"⚠️ [v2.0调试] 提取报告失败: {e}")
            report = "未生成分析报告"

        return await _build_debug_response(req, report)

    except Exception as e:
        logger.error(f"❌ [v2.0调试] v2.0调试失败: {e}")
        # 不再回退到 v1.0
        raise HTTPException(status_code=500, detail=f"v2.0调试失败: {e}")


async def _build_debug_response(req: AnalystDebugRequest, report: str):
    """构建调试响应"""
    import logging
    logger = logging.getLogger("webapi")

    # 🔥 获取模板元数据（如果有）
    tpl_meta = {}
    try:
        if req.template_id:
            from app.services.prompt_template_service import PromptTemplateService
            template_service = PromptTemplateService()
            template = await template_service.get_template(req.template_id)
            if template:
                tmp = template.model_dump()
                tpl_meta = {
                    "name": tmp.get("template_name"),
                    "description": tmp.get("remark"),
                    "source": "user" if not tmp.get("is_system") else "system",
                    "template_id": str(tmp.get("id")),
                    "version": tmp.get("version", 1),
                    "agent_type": tmp.get("agent_type"),
                    "agent_name": tmp.get("agent_name"),
                    "preference_type": tmp.get("preference_type"),
                    "status": tmp.get("status")
                }
        else:
            tpl_meta = {}
    except Exception as e:
        logger.warning(f"⚠️ [调试接口] 获取模板元数据失败: {e}")
        tpl_meta = {}

    # 🔥 构建返回数据
    logger.info("=" * 80)
    logger.info("🔍 [调试接口] 返回结果:")
    logger.info(f"   analyst_type: {req.analyst_type}")
    logger.info(f"   symbol: {req.stock.symbol}")
    logger.info(f"   report_length: {len(report) if report else 0}")
    logger.info(f"   template_id: {req.template_id}")
    logger.info("=" * 80)

    return {
        "success": True,
        "data": {
            "analyst_type": req.analyst_type,
            "symbol": req.stock.symbol,
            "analysis_date": req.stock.analysis_date,
            "report": report,
            "report_length": len(report) if report else 0,
            "template": tpl_meta,
            "debug_mode": bool(req.template_id),
            "debug_template_id": req.template_id
        },
        "message": "调试分析完成"
    }


@router.get("/workflows")
async def list_debug_workflows(
    user: dict = Depends(get_current_user),
    license: LicenseInfo = Depends(require_pro)
):
    """
    获取所有可用于调试的工作流

    返回系统内置工作流和用户自定义工作流列表
    """
    import logging
    logger = logging.getLogger("webapi")

    try:
        logger.info("开始获取调试工作流列表...")

        workflows = []

        # 1. 获取系统内置工作流模板
        try:
            from core.api import WorkflowAPI
            api = WorkflowAPI()
            templates = api.get_templates()
            for tpl in templates:
                workflows.append({
                    "id": tpl.get("id"),
                    "name": tpl.get("name"),
                    "description": tpl.get("description", ""),
                    "type": "template",
                    "is_system": True,
                    "tags": tpl.get("tags", [])
                })
        except Exception as e:
            logger.warning(f"获取系统模板失败: {e}")

        # 2. 获取数据库中的工作流定义
        try:
            from app.core.database import get_mongo_db
            db = get_mongo_db()

            # 从 workflow_definitions 获取用户自定义流程
            cursor = db.workflow_definitions.find({"enabled": True})
            for doc in cursor:
                workflow_id = doc.get("workflow_id") or doc.get("id")
                # 避免重复（如果已经在模板中）
                if not any(w["id"] == workflow_id for w in workflows):
                    workflows.append({
                        "id": workflow_id,
                        "name": doc.get("name", workflow_id),
                        "description": doc.get("description", ""),
                        "type": "custom",
                        "is_system": doc.get("is_system", False),
                        "category": doc.get("category", ""),
                        "tags": doc.get("tags", [])
                    })

            # 从 workflows 集合获取（如果有）
            cursor = db.workflows.find({})
            for doc in cursor:
                workflow_id = doc.get("id")
                if workflow_id and not any(w["id"] == workflow_id for w in workflows):
                    workflows.append({
                        "id": workflow_id,
                        "name": doc.get("name", workflow_id),
                        "description": doc.get("description", ""),
                        "type": "custom" if not doc.get("is_template") else "template",
                        "is_system": doc.get("is_system", False),
                        "tags": doc.get("tags", [])
                    })

        except Exception as e:
            logger.warning(f"从数据库获取工作流失败: {e}")

        logger.info(f"成功获取调试工作流: 总计={len(workflows)}个")
        return {"success": True, "data": workflows}

    except Exception as e:
        logger.error(f"获取调试工作流失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/workflow")
async def debug_workflow(
    req: WorkflowDebugRequest,
    user: dict = Depends(get_current_user),
    license: LicenseInfo = Depends(require_pro)
):
    """
    调试完整工作流

    使用统一任务引擎在后台执行，避免长时间占用 API 请求线程/事件循环。
    """
    import asyncio
    import logging

    logger = logging.getLogger("webapi")

    try:
        logger.info("=" * 80)
        logger.info("🔍 [工作流调试] 收到请求参数:")
        logger.info(f"   workflow_id: {req.workflow_id}")
        logger.info(f"   llm.provider: {req.llm.provider}")
        logger.info(f"   llm.model: {req.llm.model}")
        logger.info(f"   stock.symbol: {req.stock.symbol}")
        logger.info("=" * 80)

        from app.models.analysis import AnalysisTaskType
        from app.models.user import PyObjectId
        from app.services.task_analysis_service import get_task_analysis_service
        from core.api import WorkflowAPI
        from tradingagents.utils.stock_utils import StockMarket, StockUtils

        api = WorkflowAPI()
        workflow_dict = api.get(req.workflow_id)
        if not workflow_dict:
            raise HTTPException(status_code=404, detail=f"工作流 {req.workflow_id} 不存在")

        user_id = str(user.get("id") or user.get("user_id") or user.get("_id"))
        symbol = str(req.stock.symbol or "").strip()
        if not symbol:
            raise HTTPException(status_code=400, detail="请提供股票代码")

        if req.stock.market_type:
            market_type = req.stock.market_type
        else:
            market = StockUtils.identify_stock_market(symbol)
            market_type_mapping = {
                StockMarket.CHINA_A: "cn",
                StockMarket.HONG_KONG: "hk",
                StockMarket.US: "us",
                StockMarket.UNKNOWN: "cn",
            }
            market_type = market_type_mapping.get(market, "cn")

        task_params = {
            "symbol": symbol,
            "stock_code": symbol,
            "market_type": market_type,
            "analysis_date": req.stock.analysis_date or datetime.now().strftime("%Y-%m-%d"),
            "research_depth": "标准",
            "quick_analysis_model": req.llm.model,
            "deep_analysis_model": req.llm.model,
            "lookback_days": 30,
            "max_debate_rounds": 3,
            "recursion_limit": 100,
            "skip_cache": True,
            "prompt_overrides": req.prompt_overrides or {},
            "debug_mode": True,
            "debug_llm_provider": req.llm.provider,
            "debug_llm_backend_url": req.llm.backend_url,
            "debug_llm_api_key": req.llm.api_key,
            "debug_llm_temperature": req.llm.temperature,
            "debug_llm_max_tokens": req.llm.max_tokens,
        }
        if req.dataopts:
            task_params.update(req.dataopts)

        task_service = get_task_analysis_service()
        task = await task_service.create_task(
            user_id=PyObjectId(user_id),
            task_type=AnalysisTaskType.STOCK_ANALYSIS,
            task_params=task_params,
            engine_type="workflow",
            preference_type="neutral",
            workflow_id=req.workflow_id,
        )

        background_task = asyncio.create_task(task_service.execute_task(task))

        def _log_background_task_error(done_task: asyncio.Task) -> None:
            try:
                done_task.result()
            except Exception as task_error:
                logger.error(f"❌ [工作流调试] 后台任务执行失败: task_id={task.task_id} - {task_error}")

        background_task.add_done_callback(_log_background_task_error)

        logger.info(f"✅ [工作流调试] 后台任务已创建: task_id={task.task_id}, workflow_id={req.workflow_id}")

        return {
            "success": True,
            "data": {
                "task_id": task.task_id,
                "status": task.status,
                "workflow_id": req.workflow_id,
                "workflow_name": workflow_dict.get("name", req.workflow_id),
                "symbol": symbol,
                "analysis_date": task_params["analysis_date"],
                "message": "工作流调试任务已提交，正在后台执行",
            },
            "message": "工作流调试任务已提交",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [工作流调试] 创建后台任务失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/invocations")
async def list_invocations(
    source_type: Optional[str] = Query(None, description="来源类型: assistant/workflow/agent"),
    target_id: Optional[str] = Query(None, description="目标 Agent ID"),
    root_invocation_id: Optional[str] = Query(None, description="根调用 ID"),
    workflow_id: Optional[str] = Query(None, description="工作流 ID"),
    execution_id: Optional[str] = Query(None, description="执行 ID"),
    thread_id: Optional[str] = Query(None, description="助手线程 ID"),
    symbol: Optional[str] = Query(None, description="股票代码"),
    status: Optional[str] = Query(None, description="调用状态"),
    group_by_root: bool = Query(False, description="是否按 root 调用链分组"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    user: dict = Depends(get_current_user),
    license: LicenseInfo = Depends(require_pro),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """统一查询 Assistant、Workflow、Agent 三类调用记录。"""
    import logging

    logger = logging.getLogger("webapi")

    source_to_collection = {
        "assistant": "assistant_agent_invocations",
        "workflow": "workflow_agent_invocations",
        "agent": "agent_agent_invocations",
    }

    if source_type and source_type not in source_to_collection:
        raise HTTPException(status_code=400, detail="source_type 仅支持 assistant/workflow/agent")

    target_collections: List[str] = (
        [source_to_collection[source_type]]
        if source_type
        else [
            "assistant_agent_invocations",
            "workflow_agent_invocations",
            "agent_agent_invocations",
        ]
    )

    fetch_limit = min(max(page * page_size * (20 if group_by_root else 1), 50 if not group_by_root else 200), 2000 if group_by_root else 200)
    normalized_items: List[Dict[str, Any]] = []
    total = 0
    user_id = str(user["id"])

    try:
        for collection_name in target_collections:
            query = _build_invocation_query(
                user_id=user_id,
                target_id=target_id,
                status=status,
                symbol=symbol,
                workflow_id=workflow_id,
                execution_id=execution_id,
                thread_id=thread_id,
                root_invocation_id=root_invocation_id,
                source_collection=collection_name,
            )
            total += await db[collection_name].count_documents(query)
            docs = await db[collection_name].find(query).sort("created_at", -1).limit(fetch_limit).to_list(length=fetch_limit)
            normalized_items.extend(
                _normalize_invocation_doc(collection_name, doc)
                for doc in docs
            )

        normalized_items.sort(
            key=lambda item: item.get("created_at") or item.get("updated_at") or "",
            reverse=True,
        )

        start_index = (page - 1) * page_size
        end_index = start_index + page_size

        chains: List[Dict[str, Any]] = []
        page_items = normalized_items[start_index:end_index]
        if group_by_root:
            chains = _group_invocation_chains(normalized_items)
            total = len(chains)
            page_chains = chains[start_index:end_index]
            page_items = [item for chain in page_chains for item in chain.get("items", [])]
            chains = page_chains

        logger.info(
            "[调用记录] 查询完成 user_id=%s source_type=%s total=%s page=%s page_size=%s group_by_root=%s",
            user_id,
            source_type or "all",
            total,
            page,
            page_size,
            group_by_root,
        )

        return {
            "success": True,
            "data": {
                "items": page_items,
                "chains": chains,
                "total": total,
                "page": page,
                "page_size": page_size,
                "group_by_root": group_by_root,
                "has_more": end_index < total,
            },
            "message": "调用记录查询成功",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"调用记录查询失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
