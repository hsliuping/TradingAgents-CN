"""Nanobot 友好的 Agent 设计与资源侦察工具。"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Annotated, Any

from langchain_core.tools import tool

from app.core.database import get_mongo_db
from app.core.database import get_mongo_db_sync
from app.models.capability_index import CapabilitySearchHit
from app.models.prompt_template import TemplateContent
from app.services.agent_workshop_service import AgentWorkshopService
from core.agents.factory import AgentFactory
from core.config.binding_manager import BindingManager
from app.services.capability_index_service import CapabilityIndexService
from core.agents.registry import get_registry
from core.tools import get_tool_registry
from core.tools.base import register_tool
from core.tools.context import get_current_assistant_thread_id, require_current_user_id

logger = logging.getLogger(__name__)

_DEFAULT_CALLABLE_SURFACES = ["assistant", "workflow", "agent"]
_GLOBAL_NO_TRADING_ADVICE_POLICY = (
    "全局铁律：所有 Agent 一律禁止输出任何交易建议、买卖/持有判断、仓位建议、"
    "目标价、止损止盈、建仓区间、择时结论和其他操作性指令；只能提供研究结论、"
    "关键依据、风险因素与情景分析。"
)
_OUTPUT_PREVIEW_KEYWORDS = (
    "样式",
    "模板",
    "骨架",
    "预览",
    "输出结构",
    "字段结构",
    "章节",
    "preview",
    "style",
    "format",
    "section",
    "outline",
)
_REPORT_KEYWORDS = (
    "报告",
    "report",
    "输出",
    "result",
)


def _get_collection(db: Any, name: str) -> Any:
    if db is None:
        return None
    collection = getattr(db, name, None)
    if collection is not None:
        return collection
    try:
        return db[name]
    except Exception:
        return None


def _json_response(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def _parse_source_types(raw: str) -> list[str]:
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def _parse_string_list(raw: str) -> list[str]:
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def _utc_now_iso() -> str:
    return datetime.utcnow().isoformat()


def _parse_json_tool_result(raw: str) -> dict[str, Any]:
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {"status": "error", "message": "工具返回不是 JSON 对象"}
    except Exception as exc:
        return {"status": "error", "message": f"工具返回无法解析为 JSON: {exc}", "raw": raw}


def _looks_unspecified(value: str) -> bool:
    text = str(value or "").strip().lower()
    if not text:
        return True
    vague_markers = {
        "不知道",
        "未定",
        "待定",
        "随便",
        "你决定",
        "都可以",
        "暂时没有",
        "none",
        "unknown",
        "tbd",
        "na",
        "n/a",
    }
    return text in vague_markers


def _contains_any_keyword(text: str, keywords: tuple[str, ...]) -> bool:
    lowered = str(text or "").strip().lower()
    if not lowered:
        return False
    return any(keyword in lowered for keyword in keywords)


def _is_stock_analysis_request(*values: str) -> bool:
    keywords = (
        "估值",
        "valuation",
        "股票",
        "a股",
        "stock",
        "pe",
        "pb",
        "peg",
        "ticker",
    )
    return any(_contains_any_keyword(value, keywords) for value in values)


def _is_output_preview_request(*values: str) -> bool:
    text = " ".join(str(value or "").strip().lower() for value in values if str(value or "").strip())
    if not text:
        return False

    if not any(keyword in text for keyword in _REPORT_KEYWORDS):
        return False

    preview_cues = any(keyword in text for keyword in _OUTPUT_PREVIEW_KEYWORDS)
    question_cues = any(
        cue in text
        for cue in (
            "什么样",
            "长什么样",
            "示例",
            "例子",
            "长这样",
            "looks like",
            "example",
        )
    )
    return preview_cues or question_cues


def _is_report_like_request(*values: str) -> bool:
    return any(_contains_any_keyword(value, _REPORT_KEYWORDS) for value in values)


def _humanize_preview_mode(mode: str) -> str:
    normalized = str(mode or "").strip().lower()
    if normalized in {"structure_skeleton", "skeleton", "outline", ""}:
        return "只看结构骨架"
    if normalized in {"placeholder_mock", "mock", "placeholder"}:
        return "允许占位符 mock"
    return str(mode or "未指定").strip() or "未指定"


def _join_display_items(values: list[str], default: str = "未指定") -> str:
    cleaned = [str(value).strip() for value in values if str(value).strip()]
    return "、".join(cleaned) if cleaned else default


def _build_confirmation_template(
    *,
    agent_id: str,
    agent_name: str,
    responsibility: str,
    desired_output_shape: str,
    output_field: str,
    bound_tools: list[str],
    non_goals: list[str],
    valuation_method_scope: str,
    test_strategy: str,
    report_contract: dict[str, Any] | None,
    overwrite_risk: dict[str, Any],
) -> str:
    lines = [
        "请确认下面这份 Agent 生成方案：",
        f"- Agent：{agent_name}（{agent_id}）",
        f"- 单一职责：{responsibility}",
        f"- 输出产物：{desired_output_shape}（output_field={output_field}）",
        f"- 核心工具：{_join_display_items(bound_tools, default='待确认')}",
        f"- 明确不做：{_join_display_items(non_goals, default='待确认')}",
        f"- 方法边界：{str(valuation_method_scope or '未特别限定').strip()}",
        f"- 生成后验证方式：{str(test_strategy or '未指定').strip()}",
    ]

    if report_contract is not None:
        forbidden_items = report_contract.get("forbidden_expansions") or []
        lines.extend([
            "- 报告契约：",
            f"  内容范围：{report_contract.get('content_scope') or '未指定'}",
            f"  样式方式：{_humanize_preview_mode(str(report_contract.get('style_preview_mode') or ''))}",
            f"  预览规则：{report_contract.get('preview_instruction') or '默认只展示结构骨架'}",
            f"  明确排除：{_join_display_items(forbidden_items, default='无')}",
        ])

    overwrite_text = "会覆盖现有配置，需用户明确同意" if overwrite_risk.get("requires_explicit_overwrite") else "不会覆盖现有配置"
    lines.append(f"- 覆盖风险：{overwrite_text}")
    lines.append(
        f"如果以上内容确认无误，请回复：确认生成 {agent_id}；allow_overwrite={'yes' if overwrite_risk.get('requires_explicit_overwrite') else 'no'}"
    )
    return "\n".join(lines)


def _normalize_recommendation_policy(_: str = "") -> str:
    return _GLOBAL_NO_TRADING_ADVICE_POLICY


def _append_trading_guard(text: str) -> str:
    clean_text = str(text or "").strip()
    if not clean_text:
        return _GLOBAL_NO_TRADING_ADVICE_POLICY
    if _GLOBAL_NO_TRADING_ADVICE_POLICY in clean_text:
        return clean_text
    return f"{clean_text}\n\n{_GLOBAL_NO_TRADING_ADVICE_POLICY}"


def _append_trading_guard_constraint(text: str) -> str:
    clean_text = str(text or "").strip()
    if _GLOBAL_NO_TRADING_ADVICE_POLICY in clean_text:
        return clean_text
    if not clean_text:
        return _GLOBAL_NO_TRADING_ADVICE_POLICY
    return f"{clean_text}\n{_GLOBAL_NO_TRADING_ADVICE_POLICY}"


def _match_keyword(keyword: str, *values: Any) -> bool:
    keyword_text = str(keyword or "").strip().lower()
    if not keyword_text:
        return True
    haystack = " ".join(str(value or "") for value in values).lower()
    return keyword_text in haystack


def _format_capability_hit(hit: CapabilitySearchHit) -> dict[str, Any]:
    capability = hit.capability
    return {
        "capability_id": capability.capability_id,
        "registry_tool_id": capability.registry_tool_id,
        "source_type": capability.source_type,
        "category": capability.category,
        "name": capability.name,
        "description": capability.description,
        "when_to_use": capability.when_to_use,
        "when_not_to_use": capability.when_not_to_use,
        "returns": capability.returns,
        "related_tools": capability.related_tools,
        "coverage_terms": capability.coverage_terms,
        "data_source": capability.data_source,
        "bindable": capability.bindable,
        "fc_enabled": capability.fc_enabled,
        "status": capability.status,
        "metadata": capability.metadata,
        "score": round(hit.score, 4),
    }


def _format_agent_metadata(metadata) -> dict[str, Any]:
    return {
        "id": metadata.id,
        "name": metadata.name,
        "description": metadata.description,
        "category": metadata.category,
        "version": metadata.version,
        "maintenance_status": metadata.maintenance_status,
        "callable_surfaces": metadata.callable_surfaces,
        "input_mode": metadata.input_mode,
        "tools": metadata.tools,
        "default_tools": metadata.default_tools,
        "max_tool_calls": metadata.max_tool_calls,
        "depends_on": metadata.depends_on,
        "tags": metadata.tags,
        "inputs": [item.model_dump(mode="json") for item in metadata.inputs],
        "outputs": [item.model_dump(mode="json") for item in metadata.outputs],
        "requires_tools": metadata.requires_tools,
        "output_field": metadata.output_field,
        "report_label": metadata.report_label,
        "node_name": metadata.node_name,
        "execution_order": metadata.execution_order,
    }


def _format_runtime_agent_config(doc: dict[str, Any], bound_tools: list[str], registry_metadata: Any | None) -> dict[str, Any]:
    agent_id = str(doc.get("agent_id") or "").strip()
    config_tools = doc.get("tools") or []
    default_tools = doc.get("default_tools") or []
    runtime_tools = bound_tools or config_tools or default_tools
    runtime_mode = "builtin_override" if registry_metadata is not None else "universal_agent"
    return {
        "agent_id": agent_id,
        "name": doc.get("name") or doc.get("agent_name") or agent_id,
        "description": doc.get("description") or "",
        "output_field": doc.get("output_field") or "analysis_report",
        "runtime_mode": runtime_mode,
        "has_builtin_blueprint": registry_metadata is not None,
        "bound_tools": bound_tools,
        "config_tools": config_tools,
        "default_tools": default_tools,
        "effective_tools": runtime_tools,
        "max_tool_calls": doc.get("max_tool_calls"),
        "status": doc.get("status") or doc.get("metadata", {}).get("status") or "unknown",
        "metadata": doc.get("metadata") or {},
        "updated_at": doc.get("updated_at"),
    }


def _format_agent_spec(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "spec_id": doc.get("spec_id"),
        "name": doc.get("name"),
        "domain": doc.get("domain"),
        "primary_goal": doc.get("primary_goal"),
        "responsibilities": doc.get("responsibilities") or [],
        "status": doc.get("status"),
        "current_version_id": doc.get("current_version_id"),
        "version_count": doc.get("version_count") or 0,
        "owner_user_id": doc.get("owner_user_id") or "",
        "updated_at": doc.get("updated_at"),
    }


def _format_agent_version(doc: dict[str, Any]) -> dict[str, Any]:
    metadata = doc.get("agent_metadata") or {}
    return {
        "version_id": doc.get("version_id"),
        "spec_id": doc.get("spec_id"),
        "version": doc.get("version"),
        "status": doc.get("status"),
        "agent_id": metadata.get("id") or metadata.get("agent_id") or "",
        "agent_name": metadata.get("name") or metadata.get("agent_name") or "",
        "required_tools": doc.get("required_tools") or [],
        "required_capabilities": doc.get("required_capabilities") or doc.get("required_skills") or [],
        "prompt_template_ref": doc.get("prompt_template_ref") or {},
        "updated_at": doc.get("updated_at"),
    }


def _format_prompt_template_record(doc: dict[str, Any]) -> dict[str, Any]:
    content = doc.get("content") or {}
    return {
        "template_id": str(doc.get("_id") or doc.get("id") or ""),
        "agent_type": doc.get("agent_type"),
        "agent_name": doc.get("agent_name"),
        "template_name": doc.get("template_name"),
        "workflow_id": doc.get("workflow_id"),
        "node_id": doc.get("node_id"),
        "status": doc.get("status"),
        "version": doc.get("version"),
        "content_fields": sorted(content.keys()) if isinstance(content, dict) else [],
        "updated_at": doc.get("updated_at"),
    }


async def _inspect_agent_overwrite_risk(db: Any, agent_id: str, status: str = "active") -> dict[str, Any]:
    agent_configs = _get_collection(db, "agent_configs")
    prompt_templates = _get_collection(db, "prompt_templates")
    bindings = _get_collection(db, "tool_agent_bindings")

    existing_config = await agent_configs.find_one({"agent_id": agent_id}) if agent_configs is not None else None
    existing_prompt = await prompt_templates.find_one(
        {"agent_type": "universal", "agent_name": agent_id, "workflow_id": None, "node_id": None, "status": status}
    ) if prompt_templates is not None else None
    existing_binding_count = 0
    if bindings is not None:
        binding_cursor = bindings.find({"agent_id": agent_id, "is_active": {"$ne": False}}, {"_id": 0, "tool_id": 1})
        existing_binding_count = len(await binding_cursor.to_list(length=None))

    return {
        "agent_config_exists": existing_config is not None,
        "prompt_template_exists": existing_prompt is not None,
        "existing_binding_count": existing_binding_count,
        "requires_explicit_overwrite": bool(existing_config or existing_prompt or existing_binding_count),
    }


@tool
@register_tool(
    tool_id="prepare_agent_requirement_intake",
    name="生成 Agent 需求采集提纲",
    description="根据用户的初始创建请求，生成 Nanobot 下一轮应该追问的需求采集提纲，避免在需求仍模糊时直接生成 Agent。",
    category="assistant_ops",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    when_to_use="当用户刚提出创建 Agent 的想法，但职责边界、输出形状、非目标或工具依赖还不清楚时使用。",
    when_not_to_use="当需求已经清晰并且可以直接进入确认稿或生成阶段时，不需要再调用。",
    returns="返回 JSON 字符串，包含已知信息、缺失决策、推荐追问问题，以及是否可以直接进入确认阶段。",
    example="prepare_agent_requirement_intake(user_request='帮我做一个估值分析 agent')",
    related_tools=["prepare_agent_generation_confirmation", "generate_confirmed_candidate_agent"],
)
def prepare_agent_requirement_intake(
    user_request: Annotated[str, "用户原始请求，例如 帮我做一个估值分析 agent"],
    target_responsibility: Annotated[str, "当前已知的单一职责，可留空"] = "",
    desired_output_shape: Annotated[str, "当前已知的输出形状，可留空，如 结构化估值报告"] = "",
    non_goals: Annotated[str, "明确不做什么，可留空，逗号分隔"] = "",
    preferred_tools: Annotated[str, "用户已指定或当前已知的偏好工具，逗号分隔"] = "",
    existing_agent_id: Annotated[str, "如果用户提到要覆盖或延续某个现有 agent，可填现有 agent_id"] = "",
    recommendation_policy: Annotated[str, "是否允许输出交易建议/仓位/价格区间；例如 只做研究不给建议"] = "",
    valuation_method_scope: Annotated[str, "估值方法边界，如 仅PE/PB/PEG，不含DCF 或 综合估值"] = "",
    test_strategy: Annotated[str, "生成后是否允许自动测试；例如 只做配置校验，不跑真实股票样例"] = "",
    preview_mode: Annotated[str, "如果用户在问报告样式，是只看结构骨架，还是允许带占位符示例"] = "",
    report_section_scope: Annotated[str, "报告章节边界，如 仅估值相关章节，不含技术面/交易计划/多空辩论"] = "",
) -> str:
    """生成 Agent 创建前的需求采集提纲。"""
    try:
        clean_request = str(user_request or "").strip()
        if not clean_request:
            return _json_response({"status": "error", "message": "user_request 不能为空"})

        resolved_non_goals = _parse_string_list(non_goals)
        resolved_tools = _parse_string_list(preferred_tools)
        stock_analysis_request = _is_stock_analysis_request(clean_request, target_responsibility, desired_output_shape)
        output_preview_request = _is_output_preview_request(clean_request, desired_output_shape)
        effective_recommendation_policy = _normalize_recommendation_policy(recommendation_policy)

        missing_decisions: list[str] = []
        follow_up_questions: list[str] = []

        if _looks_unspecified(target_responsibility):
            missing_decisions.append("single_responsibility")
            follow_up_questions.append("这个 Agent 的单一职责是什么？请用一句话描述，并说明它最核心的交付物。")

        if _looks_unspecified(desired_output_shape):
            missing_decisions.append("output_shape")
            follow_up_questions.append("你希望它输出什么形状的结果？是自然语言报告、结构化字段，还是两者都要？")

        if not resolved_non_goals:
            missing_decisions.append("non_goals")
            follow_up_questions.append("这个 Agent 明确不做什么？例如不做交易建议、不做仓位决策、不做技术择时。")

        if not resolved_tools:
            missing_decisions.append("tool_preferences")
            follow_up_questions.append("你是否已经知道它必须依赖哪些工具或数据来源？如果没有，可以让我先给出推荐工具集合。")

        if not existing_agent_id.strip():
            missing_decisions.append("creation_mode")
            follow_up_questions.append("这是要创建一个全新 Agent，还是基于已有 Agent 做覆盖/迭代？")

        if output_preview_request and _looks_unspecified(preview_mode):
            missing_decisions.append("preview_mode")
            follow_up_questions.append("你现在问的是报告样式预览。是只看章节骨架/字段模板，还是允许带占位符示例？默认应只给结构骨架，不填充真实内容。")

        if stock_analysis_request and output_preview_request and _looks_unspecified(report_section_scope):
            missing_decisions.append("report_section_scope")
            follow_up_questions.append("这个估值报告样式里只保留估值相关章节，还是还要纳入基本面摘要、方法说明、风险提示？默认不扩展到技术面、交易计划、多空辩论。")

        if stock_analysis_request and _looks_unspecified(valuation_method_scope):
            missing_decisions.append("valuation_method_scope")
            follow_up_questions.append("你希望它使用哪些估值方法？例如仅 PE/PB/PEG，相对估值优先，还是允许扩展到 DCF、情绪、资金面解释？")

        if stock_analysis_request and _looks_unspecified(test_strategy):
            missing_decisions.append("test_strategy")
            follow_up_questions.append("生成完成后你希望它只做配置校验，还是允许我立刻拿真实股票跑一份样例报告？默认更稳妥的是只做配置校验。")

        can_proceed_to_confirmation = len(missing_decisions) == 0
        return _json_response({
            "status": "ok",
            "user_request": clean_request,
            "request_profile": {
                "stock_analysis_request": stock_analysis_request,
                "output_preview_request": output_preview_request,
            },
            "known_context": {
                "target_responsibility": target_responsibility,
                "desired_output_shape": desired_output_shape,
                "non_goals": resolved_non_goals,
                "preferred_tools": resolved_tools,
                "existing_agent_id": existing_agent_id.strip(),
                "recommendation_policy": effective_recommendation_policy,
                "valuation_method_scope": valuation_method_scope,
                "test_strategy": test_strategy,
                "preview_mode": preview_mode,
                "report_section_scope": report_section_scope,
            },
            "missing_decisions": missing_decisions,
            "follow_up_questions": follow_up_questions,
            "can_proceed_to_confirmation": can_proceed_to_confirmation,
            "recommended_next_step": "prepare_agent_generation_confirmation" if can_proceed_to_confirmation else "ask_requirement_questions",
        })
    except Exception as exc:
        logger.error("生成 Agent 需求采集提纲失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"生成 Agent 需求采集提纲失败: {exc}"})


@tool
@register_tool(
    tool_id="prepare_agent_generation_confirmation",
    name="生成 Agent 创建确认稿",
    description="在真正写入数据库前，生成一份精简确认稿，明确职责边界、输出形状、工具绑定和覆盖风险，供用户确认。",
    category="assistant_ops",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    when_to_use="当 Nanobot 已经形成候选 Agent 方案，但还没有拿到用户对职责边界、输出形状和覆盖风险的明确确认时使用。",
    when_not_to_use="不适合直接落库创建 Agent。它只负责生成确认稿。",
    returns="返回 JSON 字符串，包含确认稿、覆盖风险和建议用户确认项。",
    example="prepare_agent_generation_confirmation(agent_id='valuation_candidate_v1', agent_name='估值候选Agent', target_responsibility='输出A股估值结论', tool_ids='get_value_factor_bundle_tool')",
    related_tools=["generate_confirmed_candidate_agent", "create_or_update_runtime_agent_config"],
)
async def prepare_agent_generation_confirmation(
    agent_id: Annotated[str, "候选 Agent ID"],
    agent_name: Annotated[str, "候选 Agent 显示名称"],
    target_responsibility: Annotated[str, "单一职责的一句话描述"],
    tool_ids: Annotated[str, "拟绑定工具 ID，逗号分隔"],
    output_field: Annotated[str, "输出字段名，默认 analysis_report"] = "analysis_report",
    default_tools: Annotated[str, "默认工具 ID，逗号分隔；为空则默认取 tool_ids 前两项"] = "",
    desired_output_shape: Annotated[str, "期望输出形状描述，如 结构化估值报告"] = "结构化估值报告",
    non_goals: Annotated[str, "明确不做什么，逗号分隔"] = "",
    recommendation_policy: Annotated[str, "是否允许输出交易建议/仓位/价格区间；例如 只做研究不给建议"] = "",
    valuation_method_scope: Annotated[str, "估值方法边界，如 仅PE/PB/PEG，不含DCF 或 综合估值"] = "",
    test_strategy: Annotated[str, "生成后是否允许自动测试；例如 只做配置校验，不跑真实股票样例"] = "",
    preview_mode: Annotated[str, "如果用户在问报告样式，是只看结构骨架，还是允许带占位符示例"] = "",
    report_section_scope: Annotated[str, "报告章节边界，如 仅估值相关章节，不含技术面/交易计划/多空辩论"] = "",
    status: Annotated[str, "目标模板状态，默认 active"] = "active",
) -> str:
    """生成 Agent 创建确认稿。"""
    try:
        clean_agent_id = str(agent_id or "").strip()
        clean_agent_name = str(agent_name or "").strip()
        clean_responsibility = str(target_responsibility or "").strip()
        if not clean_agent_id or not clean_agent_name or not clean_responsibility:
            return _json_response({"status": "error", "message": "agent_id、agent_name、target_responsibility 不能为空"})

        resolved_tools = _parse_string_list(tool_ids)
        resolved_default_tools = _parse_string_list(default_tools) or resolved_tools[:2] or list(resolved_tools)
        resolved_non_goals = _parse_string_list(non_goals)
        effective_recommendation_policy = _normalize_recommendation_policy(recommendation_policy)
        output_preview_request = _is_output_preview_request(clean_responsibility, desired_output_shape)
        report_like_request = _is_report_like_request(output_field, desired_output_shape, clean_responsibility)
        if not resolved_tools:
            return _json_response({"status": "error", "message": "至少需要一个拟绑定工具 ID"})

        stock_analysis_request = _is_stock_analysis_request(clean_agent_name, clean_responsibility, desired_output_shape)
        missing_intake_fields: list[str] = []
        if stock_analysis_request and not resolved_non_goals:
            missing_intake_fields.append("non_goals")
        if stock_analysis_request and _looks_unspecified(valuation_method_scope):
            missing_intake_fields.append("valuation_method_scope")
        if stock_analysis_request and _looks_unspecified(test_strategy):
            missing_intake_fields.append("test_strategy")
        if output_preview_request and _looks_unspecified(preview_mode):
            missing_intake_fields.append("preview_mode")
        if stock_analysis_request and output_preview_request and _looks_unspecified(report_section_scope):
            missing_intake_fields.append("report_section_scope")
        if missing_intake_fields:
            return _json_response({
                "status": "needs_requirement_intake",
                "message": "Agent 的需求仍不完整，先补齐非目标、方法边界、测试策略，以及样式预览模式/章节边界后再进入确认。交易建议默认全局禁止，不再作为可选项。",
                "missing_intake_fields": missing_intake_fields,
                "recommended_next_step": "prepare_agent_requirement_intake",
            })

        registry = get_tool_registry()
        missing_tools = [tool_id for tool_id in resolved_tools if registry.get(tool_id) is None]
        if missing_tools:
            return _json_response({"status": "error", "message": f"以下工具未注册: {', '.join(missing_tools)}", "missing_tools": missing_tools})

        db = get_mongo_db()
        overwrite_risk = await _inspect_agent_overwrite_risk(db, clean_agent_id, status=status)
        report_contract = None
        if report_like_request:
            report_contract = {
                "style_preview_mode": preview_mode or "structure_skeleton",
                "content_scope": report_section_scope or "仅限当前已确认职责相关章节，不得自动扩展到未确认模块",
                "preview_instruction": "确认阶段默认只展示章节骨架/字段模板，不填充真实内容；只有用户明确要求时才允许占位符 mock。",
                "forbidden_expansions": [
                    "技术分析",
                    "交易计划",
                    "多空辩论",
                    "目标价或区间",
                    "仓位建议",
                    "其他操作性指令",
                ],
            }
        user_confirmation_template = _build_confirmation_template(
            agent_id=clean_agent_id,
            agent_name=clean_agent_name,
            responsibility=clean_responsibility,
            desired_output_shape=desired_output_shape,
            output_field=output_field,
            bound_tools=resolved_tools,
            non_goals=resolved_non_goals,
            valuation_method_scope=valuation_method_scope,
            test_strategy=test_strategy,
            report_contract=report_contract,
            overwrite_risk=overwrite_risk,
        )
        return _json_response({
            "status": "ok",
            "confirmation_required": True,
            "ready_to_execute": True,
            "confirmation_brief": {
                "target_responsibility": clean_responsibility,
                "proposed_agent_id": clean_agent_id,
                "proposed_agent_name": clean_agent_name,
                "desired_output_shape": desired_output_shape,
                "output_field": output_field,
                "chosen_build_path": "create_universal_agent",
                "bound_tools": resolved_tools,
                "default_tools": resolved_default_tools,
                "non_goals": resolved_non_goals,
                "recommendation_policy": effective_recommendation_policy,
                "valuation_method_scope": valuation_method_scope,
                "test_strategy": test_strategy,
                "report_contract": report_contract,
                "report_contract_display": {
                    "content_scope": report_contract["content_scope"] if report_contract else "不适用",
                    "style_preview_mode": _humanize_preview_mode(str(report_contract["style_preview_mode"])) if report_contract else "不适用",
                    "preview_instruction": report_contract["preview_instruction"] if report_contract else "不适用",
                    "forbidden_expansions": report_contract["forbidden_expansions"] if report_contract else [],
                },
                "preview_mode": preview_mode,
                "report_section_scope": report_section_scope,
                "overwrite_risk": overwrite_risk,
                "user_confirmation_template": user_confirmation_template,
                "required_user_confirmations": [
                    "确认单一职责边界是否准确",
                    "确认输出形状和 output_field 是否符合预期",
                    "如果输出是报告类产物，确认报告内容边界和样式预览方式是否符合预期，且章节范围不要越界",
                    "确认核心工具集合是否合适",
                    "确认非目标和研究边界是否准确，且全局禁止任何交易建议或操作性指令",
                    "确认估值方法边界和生成后测试方式是否准确",
                    "若存在覆盖风险，确认是否允许覆盖现有配置",
                ],
                "suggested_user_reply": f"确认生成 {clean_agent_id}；allow_overwrite={'yes' if overwrite_risk['requires_explicit_overwrite'] else 'no'}",
            },
        })
    except Exception as exc:
        logger.error("生成 Agent 创建确认稿失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"生成 Agent 创建确认稿失败: {exc}"})


@tool
@register_tool(
    tool_id="search_project_capabilities",
    name="搜索项目能力",
    description="轻量搜索当前项目里可复用的工具、skills、外部技能和 MCP 能力，用于 Agent 设计前的资源侦察。",
    category="assistant_ops",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    when_to_use=(
        "当 Nanobot 需要先确认仓库里已有哪类能力，再决定如何设计或创建新 Agent 时使用。"
        "适合按需求关键词搜索，而不是直接猜工具名。"
    ),
    when_not_to_use=(
        "不适合直接执行股票分析，也不适合直接生成最终 Agent 实现。"
        "它只负责资源侦察与能力确认。"
    ),
    returns=(
        "返回 JSON 字符串，包含 capability_id、source_type、category、description、when_to_use、"
        "related_tools、bindable、metadata.parameters 等能力摘要。"
    ),
    example="search_project_capabilities(query='A股估值 行业对比 因子', top_k=8)",
    related_tools=["inspect_agent_blueprints", "get_agent_blueprint_details"],
)
async def search_project_capabilities(
    query: Annotated[str, "能力检索需求，如 A股估值、行业对比、组合复盘、报告生成"],
    top_k: Annotated[int, "返回结果条数，默认 8，最大 20"] = 8,
    bindable_only: Annotated[bool, "是否只返回可直接绑定到 Agent 的能力，默认 true"] = True,
    source_types: Annotated[str, "按能力来源过滤，逗号分隔，如 builtin_tool,skill,mcp_tool"] = "builtin_tool,skill,external_skill,mcp_tool",
) -> str:
    """搜索项目已有能力，供 Nanobot 在创建 Agent 前做资源侦察。"""
    try:
        db = get_mongo_db()
        service = CapabilityIndexService(db)
        hits = await service.search_capabilities(
            query=query,
            top_k=max(1, min(int(top_k), 20)),
            bindable_only=bindable_only,
            source_types=_parse_source_types(source_types),
        )
        return _json_response({
            "query": query,
            "bindable_only": bindable_only,
            "source_types": _parse_source_types(source_types),
            "count": len(hits),
            "results": [_format_capability_hit(hit) for hit in hits],
        })
    except Exception as exc:
        logger.error("搜索项目能力失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"搜索项目能力失败: {exc}"})


@tool
@register_tool(
    tool_id="inspect_runtime_agent_configs",
    name="查看运行时 Agent 配置",
    description="查看数据库中的配置式 Agent 运行时定义，包括 agent_configs 和 tool_agent_bindings，用于判断是否可以直接复用 UniversalAgent 基座。",
    category="assistant_ops",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    when_to_use=(
        "当 Nanobot 需要确认项目里是否已经存在数据库驱动的专用 Agent，"
        "或判断某个能力是否可以通过 UniversalAgent + agent_configs 直接承载时使用。"
    ),
    when_not_to_use="不适合执行 Agent，也不适合搜索通用工具能力；它只看数据库里的运行时 Agent 定义。",
    returns=(
        "返回 JSON 字符串，包含 runtime_mode、effective_tools、output_field、metadata、"
        "以及该配置是否覆盖了内置蓝图。"
    ),
    example="inspect_runtime_agent_configs(keyword='估值', limit=5)",
    related_tools=["inspect_agent_workshop_assets", "inspect_agent_blueprints", "search_project_capabilities"],
)
async def inspect_runtime_agent_configs(
    keyword: Annotated[str, "按 agent_id、名称、描述、metadata 模糊筛选，可留空"] = "",
    limit: Annotated[int, "返回条数，默认 10，最大 20"] = 10,
    include_builtin_overrides: Annotated[bool, "是否包含对内置 Agent 的数据库覆盖配置，默认 true"] = True,
) -> str:
    """查看数据库中的运行时 Agent 配置。"""
    try:
        db = get_mongo_db()
        agent_configs = _get_collection(db, "agent_configs")
        if agent_configs is None:
            return _json_response({"status": "error", "message": "当前数据库中不可用 agent_configs 集合"})

        registry = get_registry()
        capped_limit = max(1, min(int(limit), 20))
        cursor = agent_configs.find({}, {"_id": 0})
        if hasattr(cursor, "sort"):
            cursor = cursor.sort("updated_at", -1)
        docs = await cursor.to_list(length=max(capped_limit * 5, 20))

        bindings_collection = _get_collection(db, "tool_agent_bindings")
        results: list[dict[str, Any]] = []
        for doc in docs:
            agent_id = str(doc.get("agent_id") or "").strip()
            if not agent_id:
                continue
            registry_metadata = registry.get_metadata(agent_id)
            if not include_builtin_overrides and registry_metadata is not None:
                continue

            bound_tools: list[str] = []
            if bindings_collection is not None:
                binding_cursor = bindings_collection.find(
                    {"agent_id": agent_id, "is_active": {"$ne": False}},
                    {"_id": 0, "tool_id": 1, "priority": 1},
                )
                if hasattr(binding_cursor, "sort"):
                    binding_cursor = binding_cursor.sort("priority", 1)
                binding_docs = await binding_cursor.to_list(length=None)
                bound_tools = [str(item.get("tool_id") or "").strip() for item in binding_docs if item.get("tool_id")]

            formatted = _format_runtime_agent_config(doc, bound_tools, registry_metadata)
            if not _match_keyword(
                keyword,
                formatted.get("agent_id"),
                formatted.get("name"),
                formatted.get("description"),
                formatted.get("runtime_mode"),
                formatted.get("effective_tools"),
                formatted.get("metadata"),
            ):
                continue
            results.append(formatted)
            if len(results) >= capped_limit:
                break

        return _json_response({
            "keyword": keyword,
            "include_builtin_overrides": include_builtin_overrides,
            "count": len(results),
            "results": results,
            "design_references": [
                "docs/design/v3.0/ai-workflow-generation.md",
                "docs/design/v3.0/agent-workshop-interface-sequence.md",
                "docs/design/v3.0/implementation-status-report.md",
            ],
        })
    except Exception as exc:
        logger.error("查看运行时 Agent 配置失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"查看运行时 Agent 配置失败: {exc}"})


@tool
@register_tool(
    tool_id="inspect_agent_blueprints",
    name="查看 Agent 蓝图",
    description="查看当前仓库里已注册 Agent 的元数据蓝图，用于为新 Agent 选择最接近的起点。",
    category="assistant_ops",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    when_to_use=(
        "当 Nanobot 需要判断应该复用哪个现有 Agent 模式时使用。"
        "适合先按关键词、分类或维护状态筛选，再决定读哪一个实现。"
    ),
    when_not_to_use="不适合直接输出最终实现代码。它提供的是现有 Agent 的结构化蓝图摘要。",
    returns=(
        "返回 JSON 字符串，包含 agent_id、description、tools、default_tools、inputs、outputs、"
        "callable_surfaces、maintenance_status 等元数据。"
    ),
    example="inspect_agent_blueprints(keyword='估值', category='analyst', limit=5)",
    related_tools=["get_agent_blueprint_details", "search_project_capabilities"],
)
def inspect_agent_blueprints(
    keyword: Annotated[str, "按名称、描述、标签、工具名模糊过滤，可留空"] = "",
    category: Annotated[str, "按 Agent 分类过滤，如 analyst，可留空"] = "",
    limit: Annotated[int, "返回条数，默认 10，最大 20"] = 10,
    maintained_only: Annotated[bool, "是否默认排除已标记 unmaintained 的蓝图"] = True,
) -> str:
    """查看当前项目里可复用的 Agent 蓝图。"""
    try:
        registry = get_registry()
        items = registry.list_all()
        keyword_text = str(keyword or "").strip().lower()
        category_text = str(category or "").strip().lower()
        results: list[dict[str, Any]] = []
        for metadata in items:
            maintenance_status = str(metadata.maintenance_status or "")
            if maintained_only and maintenance_status == "unmaintained":
                continue
            if category_text and str(metadata.category or "").lower() != category_text:
                continue
            if keyword_text:
                haystack = " ".join([
                    str(metadata.id or ""),
                    str(metadata.name or ""),
                    str(metadata.description or ""),
                    " ".join(metadata.tags or []),
                    " ".join(metadata.tools or []),
                ]).lower()
                if keyword_text not in haystack:
                    continue
            results.append(_format_agent_metadata(metadata))
            if len(results) >= max(1, min(int(limit), 20)):
                break
        return _json_response({
            "keyword": keyword,
            "category": category,
            "maintained_only": maintained_only,
            "count": len(results),
            "results": results,
        })
    except Exception as exc:
        logger.error("查看 Agent 蓝图失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"查看 Agent 蓝图失败: {exc}"})


@tool
@register_tool(
    tool_id="get_agent_blueprint_details",
    name="查看 Agent 蓝图详情",
    description="查看单个已注册 Agent 的完整元数据蓝图，用于确认是否适合作为新 Agent 的模板或参考对象。",
    category="assistant_ops",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    when_to_use=(
        "当 Nanobot 已经通过 inspect_agent_blueprints 找到候选 Agent，"
        "需要进一步确认输入输出、默认工具、依赖关系和调用面时使用。"
    ),
    when_not_to_use="不适合用来搜索能力集合；先筛选候选，再看详情。",
    returns="返回 JSON 字符串，包含单个 Agent 的完整元数据详情。",
    example="get_agent_blueprint_details(agent_id='valuation_analyst_v2')",
    related_tools=["inspect_agent_blueprints", "search_project_capabilities"],
)
def get_agent_blueprint_details(
    agent_id: Annotated[str, "已注册 Agent ID，如 valuation_analyst_v2"]
) -> str:
    """查看单个 Agent 蓝图详情。"""
    try:
        registry = get_registry()
        metadata = registry.get_metadata(agent_id)
        if metadata is None:
            return _json_response({"status": "not_found", "message": f"未找到 Agent 蓝图: {agent_id}"})
        return _json_response({
            "status": "ok",
            "agent": _format_agent_metadata(metadata),
            "suggested_reference_files": [
                "core/agents/config.py",
                "core/agents/adapters/",
            ],
        })
    except Exception as exc:
        logger.error("查看 Agent 蓝图详情失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"查看 Agent 蓝图详情失败: {exc}"})


@tool
@register_tool(
    tool_id="inspect_agent_workshop_assets",
    name="查看 Agent 工坊资产",
    description="查看数据库中的 agent_specs 和 agent_versions 摘要，用于确认是否已有可复用的配置式 Agent 规格、版本或提示词资产。",
    category="assistant_ops",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    when_to_use=(
        "当 Nanobot 需要确认是否已有接近需求的 Agent 规格、已构建版本或提示词资产时使用。"
        "适合在决定新建前先看已有配置式资产。"
    ),
    when_not_to_use="不适合做通用工具搜索，也不适合直接发布 Agent；它只汇总工坊资产摘要。",
    returns=(
        "返回 JSON 字符串，包含 spec 摘要、version 摘要、required_tools、required_capabilities、"
        "prompt_template_ref 等信息。"
    ),
    example="inspect_agent_workshop_assets(keyword='估值', limit=5)",
    related_tools=["inspect_runtime_agent_configs", "inspect_agent_blueprints", "search_project_capabilities"],
)
async def inspect_agent_workshop_assets(
    keyword: Annotated[str, "按 spec 名称、目标、version agent_metadata 模糊筛选，可留空"] = "",
    limit: Annotated[int, "每类结果返回条数，默认 10，最大 20"] = 10,
    include_archived: Annotated[bool, "是否包含 archived 状态的 spec/version，默认 false"] = False,
) -> str:
    """查看 Agent 工坊资产摘要。"""
    try:
        db = get_mongo_db()
        specs_collection = _get_collection(db, "agent_specs")
        versions_collection = _get_collection(db, "agent_versions")
        if specs_collection is None or versions_collection is None:
            return _json_response({"status": "error", "message": "当前数据库中不可用 agent_specs 或 agent_versions 集合"})

        capped_limit = max(1, min(int(limit), 20))
        specs_cursor = specs_collection.find({}, {"_id": 0})
        versions_cursor = versions_collection.find({}, {"_id": 0})
        if hasattr(specs_cursor, "sort"):
            specs_cursor = specs_cursor.sort("updated_at", -1)
        if hasattr(versions_cursor, "sort"):
            versions_cursor = versions_cursor.sort("updated_at", -1)

        spec_docs = await specs_cursor.to_list(length=max(capped_limit * 5, 20))
        version_docs = await versions_cursor.to_list(length=max(capped_limit * 5, 20))

        spec_results: list[dict[str, Any]] = []
        for doc in spec_docs:
            if not include_archived and str(doc.get("status") or "") == "archived":
                continue
            formatted = _format_agent_spec(doc)
            if not _match_keyword(
                keyword,
                formatted.get("spec_id"),
                formatted.get("name"),
                formatted.get("domain"),
                formatted.get("primary_goal"),
                formatted.get("responsibilities"),
            ):
                continue
            spec_results.append(formatted)
            if len(spec_results) >= capped_limit:
                break

        version_results: list[dict[str, Any]] = []
        for doc in version_docs:
            if not include_archived and str(doc.get("status") or "") == "archived":
                continue
            formatted = _format_agent_version(doc)
            if not _match_keyword(
                keyword,
                formatted.get("version_id"),
                formatted.get("spec_id"),
                formatted.get("agent_id"),
                formatted.get("agent_name"),
                formatted.get("required_tools"),
                formatted.get("required_capabilities"),
            ):
                continue
            version_results.append(formatted)
            if len(version_results) >= capped_limit:
                break

        return _json_response({
            "keyword": keyword,
            "include_archived": include_archived,
            "spec_count": len(spec_results),
            "version_count": len(version_results),
            "specs": spec_results,
            "versions": version_results,
            "design_references": [
                "docs/design/v3.0/agent-workshop-interface-sequence.md",
                "docs/design/v3.0/implementation-status-report.md",
            ],
        })
    except Exception as exc:
        logger.error("查看 Agent 工坊资产失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"查看 Agent 工坊资产失败: {exc}"})


@tool
@register_tool(
    tool_id="create_or_update_runtime_agent_config",
    name="创建或更新运行时 Agent 配置",
    description="为 Nanobot 创建一个可运行的 UniversalAgent 候选配置，写入 agent_configs，作为最小生成链的第一步。",
    category="assistant_ops",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    when_to_use="当 Nanobot 已经确认要生成一个新的配置式 Agent 候选，并准备把最小运行时定义写入数据库时使用。",
    when_not_to_use="不适合做资源侦察，也不适合直接绑定工具或写提示词模板。",
    returns="返回 JSON 字符串，包含写入后的 agent_configs 摘要。",
    example="create_or_update_runtime_agent_config(agent_id='valuation_candidate_v1', agent_name='估值候选Agent', description='输出估值结论')",
    related_tools=["create_or_update_universal_agent_prompt_template", "bind_agent_tools_and_validate_candidate"],
)
async def create_or_update_runtime_agent_config(
    agent_id: Annotated[str, "运行时 Agent ID，例如 valuation_candidate_v1"],
    agent_name: Annotated[str, "Agent 显示名称"],
    description: Annotated[str, "Agent 的单一职责描述"],
    output_field: Annotated[str, "输出字段名，默认 analysis_report"] = "analysis_report",
    category: Annotated[str, "Agent 分类，默认 analyst"] = "analyst",
    callable_surfaces: Annotated[str, "允许调用入口，逗号分隔，默认 assistant,workflow,agent"] = "assistant,workflow,agent",
    input_mode: Annotated[str, "输入模式，默认 standalone"] = "standalone",
    enabled: Annotated[bool, "是否启用，默认 true"] = True,
) -> str:
    """创建或更新一个配置式运行时 Agent 候选。"""
    try:
        clean_agent_id = str(agent_id or "").strip()
        clean_name = str(agent_name or "").strip()
        clean_description = str(description or "").strip()
        if not clean_agent_id or not clean_name or not clean_description:
            return _json_response({"status": "error", "message": "agent_id、agent_name、description 不能为空"})

        db = get_mongo_db()
        collection = _get_collection(db, "agent_configs")
        if collection is None:
            return _json_response({"status": "error", "message": "当前数据库中不可用 agent_configs 集合"})

        surfaces = _parse_string_list(callable_surfaces) or list(_DEFAULT_CALLABLE_SURFACES)
        existing = await collection.find_one({"agent_id": clean_agent_id}) or {}
        metadata = dict(existing.get("metadata") or {})
        metadata.update({
            "source": metadata.get("source") or "nanobot_generated",
            "callable_surfaces": surfaces,
            "input_mode": input_mode,
            "generation_status": "candidate",
        })

        update_doc = {
            "agent_id": clean_agent_id,
            "name": clean_name,
            "agent_name": clean_name,
            "description": clean_description,
            "output_field": output_field,
            "category": category,
            "enabled": enabled,
            "metadata": metadata,
            "updated_at": _utc_now_iso(),
        }
        if not existing:
            update_doc["created_at"] = _utc_now_iso()

        await collection.update_one({"agent_id": clean_agent_id}, {"$set": update_doc}, upsert=True)
        persisted = await collection.find_one({"agent_id": clean_agent_id}, {"_id": 0}) or update_doc
        return _json_response({
            "status": "ok",
            "action": "updated" if existing else "created",
            "agent": _format_runtime_agent_config(persisted, [], None),
        })
    except Exception as exc:
        logger.error("创建或更新运行时 Agent 配置失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"创建或更新运行时 Agent 配置失败: {exc}"})


@tool
@register_tool(
    tool_id="create_or_update_agent_workshop_draft",
    name="创建或更新 Agent 工坊 Draft",
    description="把 Nanobot 已确认的候选 Agent 同步到 Agent 工坊 Draft 资产层，使其在工坊列表中可见并可继续做版本治理。",
    category="assistant_ops",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    when_to_use="当 Nanobot 已经确认了候选 Agent 的职责、输出和工具范围，希望把它沉淀为 Agent 工坊 Draft 而不是只停留在运行时候选时使用。",
    when_not_to_use="不适合直接做版本发布，也不适合在需求尚未确认时调用。",
    returns="返回 JSON 字符串，包含写入后的 spec_id、session_id 和概览信息。",
    example="create_or_update_agent_workshop_draft(agent_id='valuation_candidate_v1', agent_name='估值候选Agent', target_responsibility='输出A股估值结论')",
    related_tools=["generate_confirmed_candidate_agent", "inspect_agent_workshop_assets", "create_or_update_runtime_agent_config"],
)
async def create_or_update_agent_workshop_draft(
    agent_id: Annotated[str, "候选 Agent ID，例如 valuation_candidate_v1"],
    agent_name: Annotated[str, "Agent 显示名称"],
    target_responsibility: Annotated[str, "单一职责描述"],
    output_field: Annotated[str, "输出字段名，默认 analysis_report"] = "analysis_report",
    tool_ids: Annotated[str, "候选工具 ID，逗号分隔"] = "",
    non_goals: Annotated[str, "非目标列表，逗号分隔"] = "",
    preferred_methods: Annotated[str, "方法范围或偏好，逗号分隔"] = "",
    constraints: Annotated[str, "额外约束，逗号分隔"] = "",
) -> str:
    """将 Nanobot 候选同步为 Agent 工坊 Draft。"""
    try:
        clean_agent_id = str(agent_id or "").strip()
        clean_agent_name = str(agent_name or "").strip()
        clean_responsibility = str(target_responsibility or "").strip()
        if not clean_agent_id or not clean_agent_name or not clean_responsibility:
            return _json_response({"status": "error", "message": "agent_id、agent_name、target_responsibility 不能为空"})

        try:
            user_id = require_current_user_id()
        except RuntimeError:
            user_id = ""
        current_thread_id = (get_current_assistant_thread_id() or "").strip()
        db = get_mongo_db()
        result = await AgentWorkshopService(db=db).create_nanobot_draft(
            agent_id=clean_agent_id,
            agent_name=clean_agent_name,
            target_responsibility=clean_responsibility,
            output_field=output_field,
            tool_ids=_parse_string_list(tool_ids),
            non_goals=_parse_string_list(non_goals),
            preferred_methods=_parse_string_list(preferred_methods),
            constraints=_parse_string_list(constraints),
            owner_user_id=user_id,
            source_thread_id=current_thread_id,
        )
        return _json_response({**result, "status": "ok"})
    except Exception as exc:
        logger.error("创建或更新 Agent 工坊 Draft 失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"创建或更新 Agent 工坊 Draft 失败: {exc}"})


@tool
@register_tool(
    tool_id="create_or_update_universal_agent_prompt_template",
    name="创建或更新 UniversalAgent 提示词模板",
    description="为配置式 UniversalAgent 候选创建或更新默认提示词模板，使运行时能够直接按 agent_id 读取模板。",
    category="assistant_ops",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    when_to_use="当 Nanobot 已决定创建配置式 Agent 候选，并需要让该 Agent 在运行时读取到可用提示词时使用。",
    when_not_to_use="不适合做工具绑定或能力侦察。",
    returns="返回 JSON 字符串，包含写入后的 prompt_templates 摘要。",
    example="create_or_update_universal_agent_prompt_template(agent_id='valuation_candidate_v1', template_name='估值候选模板', system_prompt='你是一名估值分析师')",
    related_tools=["create_or_update_runtime_agent_config", "bind_agent_tools_and_validate_candidate"],
)
async def create_or_update_universal_agent_prompt_template(
    agent_id: Annotated[str, "对应 UniversalAgent 的 agent_id"],
    template_name: Annotated[str, "模板名称"],
    system_prompt: Annotated[str, "系统提示词"],
    user_prompt: Annotated[str, "用户提示词，可为空"] = "",
    tool_guidance: Annotated[str, "工具使用指导"] = "优先使用已绑定工具获取真实数据，不编造，不跳过关键验证。",
    analysis_requirements: Annotated[str, "分析要求"] = "围绕单一职责完成任务，结论清晰，说明关键依据和适用边界。",
    output_format: Annotated[str, "输出格式"] = "请输出结构化结论，并明确核心判断、关键依据、风险提示。",
    constraints: Annotated[str, "约束条件"] = "不要超出该 Agent 的单一职责范围。",
    status: Annotated[str, "模板状态，默认 active"] = "active",
) -> str:
    """创建或更新 UniversalAgent 默认提示词模板。"""
    try:
        clean_agent_id = str(agent_id or "").strip()
        clean_template_name = str(template_name or "").strip()
        clean_system_prompt = _append_trading_guard(system_prompt)
        if not clean_agent_id or not clean_template_name or not clean_system_prompt:
            return _json_response({"status": "error", "message": "agent_id、template_name、system_prompt 不能为空"})

        db = get_mongo_db()
        templates = _get_collection(db, "prompt_templates")
        if templates is None:
            return _json_response({"status": "error", "message": "当前数据库中不可用 prompt_templates 集合"})

        query = {
            "agent_type": "universal",
            "agent_name": clean_agent_id,
            "workflow_id": None,
            "node_id": None,
            "status": status,
        }
        existing = await templates.find_one(query)
        content_model = TemplateContent(
            system_prompt=clean_system_prompt,
            user_prompt=user_prompt,
            tool_guidance=tool_guidance,
            analysis_requirements=analysis_requirements,
            output_format=output_format,
            constraints=_append_trading_guard_constraint(constraints),
        )
        if existing:
            await templates.update_one(
                {"_id": existing.get("_id")},
                {
                    "$set": {
                        "template_name": clean_template_name,
                        "content": content_model.model_dump(),
                        "remark": "nanobot generated candidate template",
                        "status": status,
                        "updated_at": datetime.utcnow(),
                    },
                    "$inc": {"version": 1},
                },
            )
            persisted = await templates.find_one({"_id": existing.get("_id")})
            action = "updated"
        else:
            await templates.insert_one(
                {
                    "agent_type": "universal",
                    "agent_name": clean_agent_id,
                    "template_name": clean_template_name,
                    "workflow_id": None,
                    "node_id": None,
                    "preference_type": None,
                    "content": content_model.model_dump(),
                    "remark": "nanobot generated candidate template",
                    "is_system": True,
                    "created_by": None,
                    "base_template_id": None,
                    "base_version": None,
                    "status": status,
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                    "version": 1,
                }
            )
            persisted = await templates.find_one({"agent_type": "universal", "agent_name": clean_agent_id, "status": status}, sort=[("updated_at", -1)])
            action = "created"

        if persisted is None:
            return _json_response({"status": "error", "message": "提示词模板写入后未能重新读取"})

        agent_configs = _get_collection(db, "agent_configs")
        if agent_configs is not None:
            await agent_configs.update_one(
                {"agent_id": clean_agent_id},
                {
                    "$set": {
                        "updated_at": _utc_now_iso(),
                        "metadata.default_prompt_template_id": str(persisted.get("_id") or ""),
                    }
                },
                upsert=True,
            )

        return _json_response({
            "status": "ok",
            "action": action,
            "template": _format_prompt_template_record(persisted),
        })
    except Exception as exc:
        logger.error("创建或更新 UniversalAgent 提示词模板失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"创建或更新 UniversalAgent 提示词模板失败: {exc}"})


@tool
@register_tool(
    tool_id="bind_agent_tools_and_validate_candidate",
    name="绑定 Agent 工具并校验候选",
    description="为候选 Agent 写入 tool_agent_bindings，并按真实运行时逻辑做一次干运行校验，确认配置式 Agent 已具备最小可运行条件。",
    category="assistant_ops",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    when_to_use="当 Nanobot 已写入 agent_configs 和提示词模板，准备绑定工具并确认候选 Agent 是否能被运行时正常创建时使用。",
    when_not_to_use="不适合用来搜索资源或生成提示词。",
    returns="返回 JSON 字符串，包含绑定后的工具列表、提示词模板存在性和干运行校验结果。",
    example="bind_agent_tools_and_validate_candidate(agent_id='valuation_candidate_v1', tool_ids='get_value_factor_bundle_tool,get_peer_comparison')",
    related_tools=["create_or_update_runtime_agent_config", "create_or_update_universal_agent_prompt_template"],
)
async def bind_agent_tools_and_validate_candidate(
    agent_id: Annotated[str, "候选 Agent ID"],
    tool_ids: Annotated[str, "要绑定的工具 ID，逗号分隔"],
    default_tools: Annotated[str, "默认工具 ID，逗号分隔；为空则复用 tool_ids"] = "",
    max_tool_calls: Annotated[int, "最大工具调用次数，默认 5"] = 5,
    validate_runtime: Annotated[bool, "是否做干运行校验，默认 true"] = True,
) -> str:
    """绑定候选 Agent 工具并执行最小运行时校验。"""
    try:
        clean_agent_id = str(agent_id or "").strip()
        if not clean_agent_id:
            return _json_response({"status": "error", "message": "agent_id 不能为空"})

        resolved_tools = _parse_string_list(tool_ids)
        resolved_default_tools = _parse_string_list(default_tools) or list(resolved_tools)
        if not resolved_tools:
            return _json_response({"status": "error", "message": "至少需要一个工具 ID"})

        registry = get_tool_registry()
        missing_tools = [tool_id for tool_id in resolved_tools if registry.get(tool_id) is None]
        if missing_tools:
            return _json_response({"status": "error", "message": f"以下工具未注册: {', '.join(missing_tools)}", "missing_tools": missing_tools})

        db = get_mongo_db()
        bindings = _get_collection(db, "tool_agent_bindings")
        agent_configs = _get_collection(db, "agent_configs")
        prompt_templates = _get_collection(db, "prompt_templates")
        if bindings is None or agent_configs is None:
            return _json_response({"status": "error", "message": "当前数据库中不可用 tool_agent_bindings 或 agent_configs 集合"})

        await bindings.delete_many({"agent_id": clean_agent_id})
        await bindings.insert_many([
            {
                "agent_id": clean_agent_id,
                "tool_id": tool_id,
                "priority": index + 1,
                "is_active": True,
                "created_at": _utc_now_iso(),
                "updated_at": _utc_now_iso(),
            }
            for index, tool_id in enumerate(resolved_tools)
        ])
        await agent_configs.update_one(
            {"agent_id": clean_agent_id},
            {
                "$set": {
                    "tools": resolved_tools,
                    "default_tools": resolved_default_tools,
                    "max_tool_calls": int(max_tool_calls),
                    "enabled": True,
                    "updated_at": _utc_now_iso(),
                }
            },
            upsert=True,
        )

        prompt_doc = None
        if prompt_templates is not None:
            prompt_doc = await prompt_templates.find_one(
                {"agent_type": "universal", "agent_name": clean_agent_id, "workflow_id": None, "node_id": None, "status": "active"},
                sort=[("updated_at", -1)],
            )

        validation: dict[str, Any] = {
            "prompt_template_found": prompt_doc is not None,
            "prompt_template": _format_prompt_template_record(prompt_doc) if prompt_doc else None,
            "dry_run": None,
        }

        if validate_runtime:
            sync_db = get_mongo_db_sync()
            BindingManager().set_database(sync_db)
            factory = AgentFactory()
            agent = factory.create_with_dynamic_tools(clean_agent_id, llm=None)
            validation["dry_run"] = {
                "instantiated": agent is not None,
                "agent_class": type(agent).__name__,
                "agent_id": getattr(agent, "agent_id", clean_agent_id),
                "loaded_tools": [getattr(tool, "name", str(tool)) for tool in getattr(agent, "_langchain_tools", [])],
                "output_field": getattr(agent, "_output_field", None),
            }

        return _json_response({
            "status": "ok",
            "agent_id": clean_agent_id,
            "bound_tools": resolved_tools,
            "default_tools": resolved_default_tools,
            "validation": validation,
        })
    except Exception as exc:
        logger.error("绑定 Agent 工具并校验候选失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"绑定 Agent 工具并校验候选失败: {exc}"})


@tool
@register_tool(
    tool_id="generate_confirmed_candidate_agent",
    name="确认后生成候选 Agent",
    description="在用户明确确认后，一次性完成配置写入、提示词模板写入、工具绑定和干运行校验。",
    category="assistant_ops",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    when_to_use="当 Nanobot 已完成确认稿并拿到用户明确确认后，用一次调用生成候选 Agent。",
    when_not_to_use="未确认前不要调用；也不适合做资源侦察。",
    returns="返回 JSON 字符串，包含三步写入结果和最终干运行校验结果。",
    example="generate_confirmed_candidate_agent(agent_id='valuation_candidate_v1', agent_name='估值候选Agent', target_responsibility='输出A股估值结论', tool_ids='get_value_factor_bundle_tool', system_prompt='你是一名估值分析师', confirmed=True)",
    related_tools=["prepare_agent_generation_confirmation", "bind_agent_tools_and_validate_candidate"],
)
async def generate_confirmed_candidate_agent(
    agent_id: Annotated[str, "候选 Agent ID"],
    agent_name: Annotated[str, "候选 Agent 显示名称"],
    target_responsibility: Annotated[str, "单一职责的一句话描述"],
    tool_ids: Annotated[str, "拟绑定工具 ID，逗号分隔"],
    system_prompt: Annotated[str, "系统提示词"],
    user_prompt: Annotated[str, "用户提示词，可为空"] = "",
    tool_guidance: Annotated[str, "工具使用指导"] = "优先使用已绑定工具获取真实数据，不编造，不跳过关键验证。",
    analysis_requirements: Annotated[str, "分析要求"] = "围绕单一职责完成任务，结论清晰，说明关键依据和适用边界。",
    output_format: Annotated[str, "输出格式"] = "请输出结构化结论，并明确核心判断、关键依据、风险提示。",
    constraints: Annotated[str, "约束条件"] = "不要超出该 Agent 的单一职责范围。",
    output_field: Annotated[str, "输出字段名，默认 analysis_report"] = "analysis_report",
    template_name: Annotated[str, "模板名称；为空时自动生成"] = "",
    default_tools: Annotated[str, "默认工具 ID，逗号分隔；为空则默认取 tool_ids 前两项"] = "",
    max_tool_calls: Annotated[int, "最大工具调用次数，默认 5"] = 5,
    category: Annotated[str, "Agent 分类，默认 analyst"] = "analyst",
    callable_surfaces: Annotated[str, "允许调用入口，逗号分隔，默认 assistant,workflow,agent"] = "assistant,workflow,agent",
    input_mode: Annotated[str, "输入模式，默认 standalone"] = "standalone",
    enabled: Annotated[bool, "是否启用，默认 true"] = True,
    status: Annotated[str, "模板状态，默认 active"] = "active",
    sync_to_workshop_draft: Annotated[bool, "是否同步创建 Agent 工坊 Draft，默认 true"] = True,
    confirmed: Annotated[bool, "是否已拿到用户明确确认"] = False,
    allow_overwrite: Annotated[bool, "若存在覆盖风险，是否允许覆盖现有配置"] = False,
) -> str:
    """确认后一次性生成候选 Agent。"""
    try:
        if not confirmed:
            return _json_response({
                "status": "error",
                "message": "未拿到用户明确确认，拒绝执行写入。请先生成确认稿并等待用户确认。",
            })

        clean_agent_id = str(agent_id or "").strip()
        clean_agent_name = str(agent_name or "").strip()
        clean_responsibility = str(target_responsibility or "").strip()
        clean_system_prompt = str(system_prompt or "").strip()
        if not clean_agent_id or not clean_agent_name or not clean_responsibility or not clean_system_prompt:
            return _json_response({"status": "error", "message": "agent_id、agent_name、target_responsibility、system_prompt 不能为空"})

        db = get_mongo_db()
        overwrite_risk = await _inspect_agent_overwrite_risk(db, clean_agent_id, status=status)
        if overwrite_risk["requires_explicit_overwrite"] and not allow_overwrite:
            return _json_response({
                "status": "error",
                "message": "目标 Agent 已存在配置、模板或工具绑定，未提供 allow_overwrite=True。",
                "overwrite_risk": overwrite_risk,
            })

        resolved_default_tools = _parse_string_list(default_tools) or _parse_string_list(tool_ids)[:2]
        workshop_result = None
        if sync_to_workshop_draft:
            workshop_result = _parse_json_tool_result(await create_or_update_agent_workshop_draft.ainvoke({
                "agent_id": clean_agent_id,
                "agent_name": clean_agent_name,
                "target_responsibility": clean_responsibility,
                "output_field": output_field,
                "tool_ids": tool_ids,
                "preferred_methods": "",
                "constraints": constraints,
            }))
            if workshop_result.get("status") != "ok":
                return _json_response({"status": "error", "stage": "workshop_draft", "result": workshop_result})

        config_result = _parse_json_tool_result(await create_or_update_runtime_agent_config.ainvoke({
            "agent_id": clean_agent_id,
            "agent_name": clean_agent_name,
            "description": clean_responsibility,
            "output_field": output_field,
            "category": category,
            "callable_surfaces": callable_surfaces,
            "input_mode": input_mode,
            "enabled": enabled,
        }))
        if config_result.get("status") != "ok":
            return _json_response({"status": "error", "stage": "agent_config", "result": config_result})

        prompt_result = _parse_json_tool_result(await create_or_update_universal_agent_prompt_template.ainvoke({
            "agent_id": clean_agent_id,
            "template_name": template_name or f"{clean_agent_name}模板",
            "system_prompt": clean_system_prompt,
            "user_prompt": user_prompt,
            "tool_guidance": tool_guidance,
            "analysis_requirements": analysis_requirements,
            "output_format": output_format,
            "constraints": constraints,
            "status": status,
        }))
        if prompt_result.get("status") != "ok":
            return _json_response({"status": "error", "stage": "prompt_template", "result": prompt_result})

        binding_result = _parse_json_tool_result(await bind_agent_tools_and_validate_candidate.ainvoke({
            "agent_id": clean_agent_id,
            "tool_ids": tool_ids,
            "default_tools": ",".join(resolved_default_tools),
            "max_tool_calls": max_tool_calls,
            "validate_runtime": True,
        }))
        if binding_result.get("status") != "ok":
            return _json_response({"status": "error", "stage": "bindings", "result": binding_result})

        return _json_response({
            "status": "ok",
            "agent_id": clean_agent_id,
            "confirmation": {
                "confirmed": confirmed,
                "allow_overwrite": allow_overwrite,
            },
            "steps": {
                "workshop_draft": workshop_result,
                "agent_config": config_result,
                "prompt_template": prompt_result,
                "bindings_and_validation": binding_result,
            },
            "final_validation": binding_result.get("validation") or {},
        })
    except Exception as exc:
        logger.error("确认后生成候选 Agent 失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"确认后生成候选 Agent 失败: {exc}"})


__all__ = [
    "search_project_capabilities",
    "inspect_runtime_agent_configs",
    "inspect_agent_blueprints",
    "get_agent_blueprint_details",
    "inspect_agent_workshop_assets",
    "prepare_agent_requirement_intake",
    "prepare_agent_generation_confirmation",
    "create_or_update_agent_workshop_draft",
    "create_or_update_runtime_agent_config",
    "create_or_update_universal_agent_prompt_template",
    "bind_agent_tools_and_validate_candidate",
    "generate_confirmed_candidate_agent",
]