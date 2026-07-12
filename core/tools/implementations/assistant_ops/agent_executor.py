"""
Agent 调用工具

让智能助手可以把已封装的 Agent 当作完整能力单元直接调用，
而不是总是拆成多个底层工具重新编排。
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Annotated, Any, Dict, List, Optional

from langchain_core.tools import tool

from core.collaboration_runtime import (
    InvocationArtifactRef,
    InvocationPolicy,
    InvocationProvenance,
    InvocationRequest,
    InvocationResult,
    InvocationSourceType,
    InvocationStatus,
    InvocationTargetType,
)
from core.tools.base import register_tool
from core.tools.context import get_current_assistant_thread_id, require_current_user_id

logger = logging.getLogger(__name__)

_ALLOWED_AGENT_CATEGORIES = {"analyst", "researcher", "manager", "risk", "trader"}
_DEFAULT_CALLABLE_SURFACES = {"assistant", "workflow"}


def _latest_trade_date() -> str:
    now = datetime.now()
    if now.weekday() == 5:
        now = now - timedelta(days=1)
    elif now.weekday() == 6:
        now = now - timedelta(days=2)
    return now.strftime("%Y-%m-%d")


def _normalize_text(value: Optional[str]) -> str:
    text = (value or "").strip().lower()
    for token in [" ", "_", "-", "（", "）", "(", ")", "/", "\\"]:
        text = text.replace(token, "")
    return text


def _get_sync_db():
    from app.core.database import get_mongo_db_sync

    return get_mongo_db_sync()


def _is_orphaned_workshop_agent_config(doc: Dict[str, Any], db: Any) -> bool:
    metadata = doc.get("metadata") or {}
    source = str(metadata.get("source") or "").strip().lower()
    if source != "agent_workshop":
        return False

    version_id = str(metadata.get("version_id") or "").strip()
    spec_id = str(metadata.get("spec_id") or "").strip()

    try:
        if version_id and db.agent_versions.find_one({"version_id": version_id}, {"_id": 1}):
            return False
        if spec_id and db.agent_specs.find_one({"spec_id": spec_id}, {"_id": 1}):
            return False
    except Exception as exc:
        logger.warning("[assistant agent executor] 检查工坊 Agent 关联资产失败: %s", exc)
        return False

    return bool(version_id or spec_id)


def _collect_callable_agents() -> List[Dict[str, Any]]:
    from core.agents import get_registry

    entries: Dict[str, Dict[str, Any]] = {}
    registry = get_registry()

    for metadata in registry.list_all():
        category = getattr(metadata.category, "value", str(metadata.category or ""))
        if category not in _ALLOWED_AGENT_CATEGORIES:
            continue
        entries[metadata.id] = {
            "agent_id": metadata.id,
            "name": getattr(metadata, "name", metadata.id),
            "description": getattr(metadata, "description", "") or "",
            "category": category,
            "source": "builtin",
            "output_field": getattr(metadata, "output_field", None),
            "callable_surfaces": list(_DEFAULT_CALLABLE_SURFACES),
        }

    try:
        db = _get_sync_db()
        docs = db.agent_configs.find({"enabled": True}, {"_id": 0})
        for doc in docs:
            agent_id = (doc.get("agent_id") or "").strip()
            if not agent_id:
                continue
            if _is_orphaned_workshop_agent_config(doc, db):
                continue
            category = str(doc.get("category") or "analyst")
            if category not in _ALLOWED_AGENT_CATEGORIES:
                continue
            entries[agent_id] = {
                "agent_id": agent_id,
                "name": doc.get("name") or agent_id,
                "description": doc.get("description") or "",
                "category": category,
                "source": (doc.get("metadata") or {}).get("source") or "agent_config",
                "output_field": doc.get("output_field") or (doc.get("metadata") or {}).get("output_field"),
                "callable_surfaces": list(
                    (doc.get("metadata") or {}).get("callable_surfaces") or _DEFAULT_CALLABLE_SURFACES
                ),
            }
    except Exception as exc:
        logger.warning("[assistant agent executor] 加载 agent_configs 失败: %s", exc)

    return list(entries.values())


def _search_callable_agents(keyword: Optional[str]) -> List[Dict[str, Any]]:
    entries = _collect_callable_agents()
    normalized_keyword = _normalize_text(keyword)
    if not normalized_keyword:
        return sorted(entries, key=lambda item: item["agent_id"])

    matches: List[Dict[str, Any]] = []
    for item in entries:
        haystack = "|".join([
            _normalize_text(item.get("agent_id")),
            _normalize_text(item.get("name")),
            _normalize_text(item.get("description")),
            _normalize_text(item.get("category")),
        ])
        if normalized_keyword in haystack:
            matches.append(item)
    return sorted(matches, key=lambda item: item["agent_id"])


def _resolve_callable_agent(agent_identifier: str) -> Dict[str, Any]:
    entries = _collect_callable_agents()
    normalized_identifier = _normalize_text(agent_identifier)
    if not normalized_identifier:
        raise ValueError("agent_identifier 不能为空")

    exact_matches = [
        item for item in entries
        if normalized_identifier in {
            _normalize_text(item.get("agent_id")),
            _normalize_text(item.get("name")),
        }
    ]
    if len(exact_matches) == 1:
        return exact_matches[0]
    if len(exact_matches) > 1:
        names = "、".join(f"{item['name']}({item['agent_id']})" for item in exact_matches[:5])
        raise ValueError(f"匹配到多个 Agent：{names}。请改用更精确的 agent_id。")

    fuzzy_matches = _search_callable_agents(agent_identifier)
    if len(fuzzy_matches) == 1:
        return fuzzy_matches[0]
    if len(fuzzy_matches) > 1:
        names = "、".join(f"{item['name']}({item['agent_id']})" for item in fuzzy_matches[:5])
        raise ValueError(f"找到多个可能的 Agent：{names}。请明确指定 agent_id。")

    raise ValueError(f"未找到可调用 Agent：{agent_identifier}")


def _ensure_surface_access(agent_entry: Dict[str, Any], surface: str) -> None:
    allowed_surfaces = {
        str(item).strip().lower()
        for item in (agent_entry.get("callable_surfaces") or _DEFAULT_CALLABLE_SURFACES)
        if str(item).strip()
    }
    if surface.strip().lower() not in allowed_surfaces:
        raise ValueError(
            f"Agent {agent_entry.get('agent_id')} 当前不允许从 {surface} 入口直接调用"
        )


def _resolve_assistant_agent_llm(agent_id: str):
    from app.services.simple_analysis_service import get_provider_and_url_by_model_sync
    from core.config.agent_config_manager import AgentConfigManager
    from tradingagents.graph.trading_graph import create_llm_by_provider

    db = _get_sync_db()
    config_doc = db.system_configs.find_one({"is_active": True}, sort=[("version", -1)]) or {}
    default_models = config_doc.get("default_models") or {}
    system_settings = config_doc.get("system_settings") or {}

    target_model = (
        default_models.get("deep_reasoning_model")
        or system_settings.get("deep_reasoning_model")
        or default_models.get("deep_analysis_model")
        or system_settings.get("deep_analysis_model")
        or default_models.get("quick_analysis_model")
        or system_settings.get("quick_analysis_model")
        or config_doc.get("default_llm")
    )
    if not target_model:
        raise RuntimeError("系统未配置可用于 Agent 调用的模型")

    provider_info = get_provider_and_url_by_model_sync(target_model)
    if not provider_info:
        raise RuntimeError(f"无法获取模型 {target_model} 的供应商配置")

    agent_config_manager = AgentConfigManager()
    agent_config_manager.set_database(db)
    agent_config = agent_config_manager.get_agent_config(agent_id) or {}
    execution_config = agent_config.get("config") or {}

    provider = provider_info.get("provider") or "deepseek"
    backend_url = provider_info.get("backend_url")
    api_key = provider_info.get("api_key")
    temperature = float(execution_config.get("temperature", 0.2))
    max_tokens = int(execution_config.get("max_tokens", 4000))
    timeout = int(execution_config.get("timeout", 180))

    llm = create_llm_by_provider(
        provider=provider,
        model=target_model,
        backend_url=backend_url,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
        api_key=api_key,
    )
    return llm, agent_config


def _extract_agent_report(result: Dict[str, Any], preferred_output_field: Optional[str]) -> str:
    candidate_fields = [
        preferred_output_field,
        "final_report",
        "analysis_report",
        "summary",
        "analysis_result",
    ]
    for field_name in candidate_fields:
        if not field_name:
            continue
        value = result.get(field_name)
        if isinstance(value, str) and value.strip():
            return value.strip()

    for value in result.values():
        if isinstance(value, str) and value.strip() and len(value.strip()) > 20:
            return value.strip()
    return "未生成有效分析结果。"


def _sanitize_structured_output(value: Any, max_text_length: int = 4000) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {"raw_result": str(value)[:max_text_length]}

    sanitized: Dict[str, Any] = {}
    for key, item in value.items():
        if isinstance(item, str):
            sanitized[key] = item[:max_text_length]
            continue
        if isinstance(item, (int, float, bool)) or item is None:
            sanitized[key] = item
            continue
        if isinstance(item, list):
            sanitized[key] = item[:20]
            continue
        if isinstance(item, dict):
            sanitized[key] = item
            continue
        sanitized[key] = str(item)[:max_text_length]
    return sanitized


def _build_invocation_request(
    *,
    agent_id: str,
    user_id: str,
    thread_id: Optional[str],
    symbol: Optional[str],
    task_description: Optional[str],
    analysis_date: str,
    market_type: str,
) -> InvocationRequest:
    invocation_id = f"ainv_{uuid.uuid4().hex}"
    return InvocationRequest(
        invocation_id=invocation_id,
        target_type=InvocationTargetType.AGENT,
        target_id=agent_id,
        action="execute",
        payload={
            "symbol": (symbol or "").strip() or None,
            "task_description": (task_description or "").strip() or None,
            "analysis_date": analysis_date,
            "market_type": market_type,
        },
        provenance=InvocationProvenance(
            source_type=InvocationSourceType.ASSISTANT,
            source_id="assistant_ops.execute_callable_agent",
            user_id=user_id,
            session_id=thread_id,
            thread_id=thread_id,
            trigger="assistant_tool",
            metadata={"tool_name": "execute_callable_agent"},
        ),
        policy=InvocationPolicy(
            idempotency_key=invocation_id,
            timeout_seconds=180,
            lane="assistant.agent",
        ),
        metadata={
            "invocation_source": "assistant_ops",
            "root_invocation_id": invocation_id,
            "parent_invocation_id": None,
        },
    )


async def _persist_invocation_record(
    request: InvocationRequest,
    result: InvocationResult,
) -> None:
    from app.core.database import get_mongo_db

    db = get_mongo_db()
    await db.assistant_agent_invocations.update_one(
        {"invocation_id": request.invocation_id},
        {
            "$set": {
                "invocation_id": request.invocation_id,
                "root_invocation_id": request.metadata.get("root_invocation_id") or request.invocation_id,
                "parent_invocation_id": request.metadata.get("parent_invocation_id"),
                "user_id": request.provenance.user_id,
                "thread_id": request.provenance.thread_id,
                "target_type": request.target_type.value,
                "target_id": request.target_id,
                "status": result.status.value,
                "request": request.to_python_dict(),
                "result": result.to_python_dict(),
                "updated_at": datetime.utcnow(),
            },
            "$setOnInsert": {"created_at": datetime.utcnow()},
        },
        upsert=True,
    )


async def _write_invocation_ref_to_thread(
    *,
    request: InvocationRequest,
    result: InvocationResult,
    agent_name: str,
    symbol: Optional[str],
) -> None:
    if not request.policy.visible_to_caller:
        return
    if not request.provenance.thread_id or not request.provenance.user_id:
        return

    from app.core.database import get_mongo_db
    from app.services.intelligent_assistant_service import write_report_back_to_assistant_thread

    artifact = InvocationArtifactRef(
        ref_type="agent_invocation",
        artifact_key=request.invocation_id,
        source_collection="assistant_agent_invocations",
        title=f"Agent调用：{agent_name}",
        symbol=(symbol or "").strip() or None,
        summary=(result.output_text or result.error_message or "")[:300],
        output_field=result.output_field,
        metadata={
            "agent_id": request.target_id,
            "status": result.status.value,
        },
    )

    await write_report_back_to_assistant_thread(
        get_mongo_db(),
        user_id=request.provenance.user_id,
        report_ref=artifact.to_report_ref(status=result.status.value),
        preferred_thread_id=request.provenance.thread_id,
        summary_message=None,
    )


@tool
@register_tool(
    tool_id="list_callable_agents",
    name="列出可调用 Agent",
    description="列出当前智能助手可直接调用的 Agent 完整能力，适用于先查看系统里有哪些可直接调用的估值、研究、风控、复盘类 Agent。",
    category="assistant_ops",
    is_online=True,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["agent", "callable", "list", "query", "assistant_ops", "agent_registry", "agent_capability", "agent_search", "ai_agent", "agent_inventory", "agent_lookup"],
    tool_role_hint="supporting",
    output_shape="text",
    preferred_for=["查看可调用Agent", "Agent能力列表", "Agent搜索", "可用Agent查询"],
    when_to_use="当用户想查看系统中有哪些可直接调用的 Agent、按关键词搜索可用 Agent 能力时使用，通常作为 execute_callable_agent 的前置查询。",
    returns="返回文本列表，包含可调用 Agent 的名称、ID、类别、来源和说明。",
)
async def list_callable_agents(
    keyword: Annotated[Optional[str], "按关键词筛选 Agent，可传估值、复盘、风险、ETF、情绪等；为空则列出全部常用 Agent"] = None,
    max_results: Annotated[int, "最多返回多少个 Agent，默认 12"] = 12,
) -> str:
    """列出当前智能助手可直接调用的完整 Agent 能力。"""
    matches = _search_callable_agents(keyword)
    limit = max(1, min(int(max_results or 12), 30))
    if not matches:
        return "未找到匹配的可调用 Agent。"

    lines = [f"可直接调用的 Agent 共 {len(matches)} 个，以下展示前 {min(limit, len(matches))} 个："]
    for item in matches[:limit]:
        lines.append(
            f"- {item['name']} ({item['agent_id']}) | 类别: {item['category']} | 来源: {item['source']}"
        )
        if item.get("description"):
            lines.append(f"  说明: {item['description'][:120]}")
    return "\n".join(lines)


@tool
@register_tool(
    tool_id="execute_callable_agent",
    name="调用 Agent 完整能力",
    description="直接调用一个已注册或已配置的 Agent 来完成完整任务，适用于估值、研究、复盘、风控等已封装为 Agent 的能力，而不是重新拆成多个底层工具。",
    category="assistant_ops",
    is_online=True,
    auto_register=True,
    timeout_tier="heavy",
    data_source_handling="local_only",
    capability_tags=["agent", "callable", "execute", "invoke", "assistant_ops", "agent_invocation", "agent_execution", "ai_agent", "workflow", "capability_invocation", "agent_call"],
    tool_role_hint="primary",
    output_shape="report",
    preferred_for=["调用Agent能力", "执行完整Agent", "估值分析Agent", "研究Agent调用", "风控Agent调用"],
    when_to_use="当用户想直接调用一个已封装的 Agent 完成估值、研究、复盘、风控等完整任务、而非拆成多个底层工具时使用。",
    returns="返回文本报告，包含调用的 Agent 名称、调用ID、分析对象、分析日期、任务目标和 Agent 生成的完整分析结果。",
)
async def execute_callable_agent(
    agent_identifier: Annotated[str, "Agent 的 ID 或名称，例如 valuation_analyst_v1、股票估值分析师"],
    symbol: Annotated[Optional[str], "股票代码，如 600519、000001；某些 Agent 可为空，但个股类 Agent 建议必传"] = None,
    task_description: Annotated[Optional[str], "本次调用的具体任务目标，例如请给出茅台的 PB/PE/DCF 综合估值结论"] = None,
    analysis_date: Annotated[Optional[str], "分析日期，格式 YYYY-MM-DD；为空则自动使用最近交易日"] = None,
    market_type: Annotated[Optional[str], "市场类型，例如 A股、港股、美股；为空默认 A股"] = None,
) -> str:
    """直接执行一个已封装好的 Agent，让助手把它当作完整能力调用。"""
    from core.api.workflow_api import WorkflowAPI
    from core.config.agent_config_manager import AgentConfigManager
    from core.workflow.engine import WorkflowEngine
    from core.workflow.templates.single_agent_workflow import SingleAgentWorkflow
    from tradingagents.agents.utils.agent_context import AgentContext

    user_id = require_current_user_id()
    resolved = _resolve_callable_agent(agent_identifier)
    _ensure_surface_access(resolved, "assistant")
    effective_date = (analysis_date or "").strip() or _latest_trade_date()
    effective_market_type = (market_type or "").strip() or "A股"
    current_thread_id = (get_current_assistant_thread_id() or "").strip() or None
    invocation_request = _build_invocation_request(
        agent_id=resolved["agent_id"],
        user_id=user_id,
        thread_id=current_thread_id,
        symbol=symbol,
        task_description=task_description,
        analysis_date=effective_date,
        market_type=effective_market_type,
    )
    started_at = datetime.utcnow()

    logger.info(
        "[execute_callable_agent] 开始调用 Agent: agent=%s symbol=%s user_id=%s invocation_id=%s",
        resolved["agent_id"],
        symbol,
        user_id,
        invocation_request.invocation_id,
    )

    llm, agent_config = _resolve_assistant_agent_llm(resolved["agent_id"])

    workflow_def = SingleAgentWorkflow(
        agent_id=resolved["agent_id"],
        config={
            "stock_symbol": symbol or "",
            "analysis_date": effective_date,
            "market_type": effective_market_type,
            "agent_config": agent_config,
        },
    )

    engine = WorkflowEngine(
        legacy_config={},
        task_id=invocation_request.invocation_id,
        llm=llm,
    )
    engine.load(workflow_def)

    ctx = AgentContext(
        user_id=user_id,
        session_id=current_thread_id,
        request_id=invocation_request.invocation_id,
        workflow_id=f"assistant_agent_{resolved['agent_id']}",
        node_id=resolved["agent_id"],
        extra={
            "invocation_source": "assistant_ops",
            "invocation_id": invocation_request.invocation_id,
            "root_invocation_id": invocation_request.metadata.get("root_invocation_id") or invocation_request.invocation_id,
            "parent_invocation_id": invocation_request.metadata.get("parent_invocation_id"),
            "invocation_provenance": invocation_request.provenance.to_python_dict(),
            "invocation_lane": invocation_request.policy.lane,
        },
    )

    inputs: Dict[str, Any] = {
        "stock_symbol": symbol or "",
        "ticker": symbol or "",
        "analysis_date": effective_date,
        "trade_date": effective_date,
        "company_of_interest": symbol or "",
        "market_type": effective_market_type,
        "thread_id": current_thread_id,
        "context": ctx,
        "task_description": (task_description or "").strip(),
        "skip_cache": True,
        "prompt_overrides": {},
    }

    if symbol:
        try:
            workflow_api = WorkflowAPI()
            system_vars = workflow_api._prepare_system_variables(stock_code=symbol, analysis_date=effective_date)
            inputs.update(system_vars)
        except Exception as exc:
            logger.warning("[execute_callable_agent] 准备系统变量失败: %s", exc)

    try:
        result = await engine.execute_async(inputs)

        agent_config_manager = AgentConfigManager()
        agent_config_manager.set_database(_get_sync_db())
        effective_config = agent_config_manager.get_agent_config(resolved["agent_id"]) or agent_config or {}
        preferred_output_field = effective_config.get("output_field") or resolved.get("output_field")
        report = _extract_agent_report(result, preferred_output_field)

        invocation_result = InvocationResult(
            invocation_id=invocation_request.invocation_id,
            target_type=InvocationTargetType.AGENT,
            target_id=resolved["agent_id"],
            status=InvocationStatus.SUCCEEDED,
            started_at=started_at,
            completed_at=datetime.utcnow(),
            output_text=report,
            structured_output=_sanitize_structured_output(result),
            output_field=preferred_output_field,
            artifacts=[
                InvocationArtifactRef(
                    ref_type="agent_invocation",
                    artifact_key=invocation_request.invocation_id,
                    source_collection="assistant_agent_invocations",
                    title=f"Agent调用：{resolved['name']}",
                    symbol=(symbol or "").strip() or None,
                    summary=report[:300],
                    output_field=preferred_output_field,
                )
            ],
            metadata={
                "agent_name": resolved["name"],
                "category": resolved.get("category"),
            },
        )
        await _persist_invocation_record(invocation_request, invocation_result)
        await _write_invocation_ref_to_thread(
            request=invocation_request,
            result=invocation_result,
            agent_name=resolved["name"],
            symbol=symbol,
        )

        return (
            f"已调用 Agent: {resolved['name']} ({resolved['agent_id']})\n"
            f"调用ID: {invocation_request.invocation_id}\n"
            f"分析对象: {symbol or '未指定'}\n"
            f"分析日期: {effective_date}\n"
            f"任务目标: {(task_description or '使用 Agent 默认职责执行').strip()}\n\n"
            f"{report}"
        )
    except Exception as exc:
        invocation_result = InvocationResult(
            invocation_id=invocation_request.invocation_id,
            target_type=InvocationTargetType.AGENT,
            target_id=resolved["agent_id"],
            status=InvocationStatus.FAILED,
            started_at=started_at,
            completed_at=datetime.utcnow(),
            error_message=str(exc),
            metadata={
                "agent_name": resolved["name"],
                "category": resolved.get("category"),
            },
        )
        await _persist_invocation_record(invocation_request, invocation_result)
        logger.exception(
            "[execute_callable_agent] Agent 调用失败: agent=%s invocation_id=%s",
            resolved["agent_id"],
            invocation_request.invocation_id,
        )
        raise