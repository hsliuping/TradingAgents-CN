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


def _dedupe_string_list(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return ordered


def _utc_now_iso() -> str:
    return datetime.utcnow().isoformat()


def _parse_json_tool_result(raw: str) -> dict[str, Any]:
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {"status": "error", "message": "工具返回不是 JSON 对象"}
    except Exception as exc:
        return {"status": "error", "message": f"工具返回无法解析为 JSON: {exc}", "raw": raw}


def _parse_optional_json_object(raw: str, field_name: str) -> dict[str, Any]:
    text = str(raw or "").strip()
    if not text:
        return {}
    try:
        data = json.loads(text)
    except Exception as exc:
        raise ValueError(f"{field_name} 不是合法 JSON 对象: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{field_name} 必须是 JSON 对象")
    return data


def _parse_optional_json_list(raw: str, field_name: str) -> list[Any]:
    text = str(raw or "").strip()
    if not text:
        return []
    try:
        data = json.loads(text)
    except Exception as exc:
        raise ValueError(f"{field_name} 不是合法 JSON 数组: {exc}") from exc
    if not isinstance(data, list):
        raise ValueError(f"{field_name} 必须是 JSON 数组")
    return data


def _with_nanobot_review_worker_flags(runtime_result: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if runtime_result is None:
        return None
    payload = dict(runtime_result)
    payload.setdefault("review_worker_mode", "nanobot-assisted")
    payload.setdefault("nanobot_evidence_workers", True)
    return payload


def _has_workshop_runtime_evidence(runtime_result: dict[str, Any] | None) -> bool:
    if not isinstance(runtime_result, dict) or not runtime_result:
        return False
    if str(runtime_result.get("output_text") or "").strip():
        return True
    if str(runtime_result.get("report") or "").strip():
        return True
    if runtime_result.get("output_payload"):
        return True
    if runtime_result.get("raw_result"):
        return True
    if runtime_result.get("tool_trace"):
        return True

    debug_prompt = runtime_result.get("debug_prompt")
    if isinstance(debug_prompt, dict):
        if debug_prompt.get("tool_trace"):
            return True
        if str(debug_prompt.get("system_prompt") or "").strip():
            return True
        if str(debug_prompt.get("user_prompt") or "").strip():
            return True
        if str(debug_prompt.get("output_text") or "").strip():
            return True

    raw_result = runtime_result.get("raw_result")
    if isinstance(raw_result, dict):
        if raw_result.get("tool_trace"):
            return True
        nested_debug_prompt = raw_result.get("__debug_prompt__")
        if isinstance(nested_debug_prompt, dict):
            if nested_debug_prompt.get("tool_trace"):
                return True
            if str(nested_debug_prompt.get("system_prompt") or "").strip():
                return True
            if str(nested_debug_prompt.get("user_prompt") or "").strip():
                return True
            if str(nested_debug_prompt.get("output_text") or "").strip():
                return True
    return False


def _build_tool_stage_event(name: str, status: str, detail: str) -> dict[str, str]:
    return {
        "name": name,
        "status": status,
        "detail": str(detail or "").strip(),
    }


_WORKSHOP_SPEC_COLLECTION = "agent_specs"
_WORKSHOP_SESSION_COLLECTION = "agent_workshop_sessions"
_WORKSHOP_VERSION_COLLECTION = "agent_versions"
_WORKSHOP_EVALUATION_COLLECTION = "agent_evaluations"


def _compute_workshop_phase(
    *,
    feasibility_status: str,
    completeness_score: float,
    version_status: str,
    latest_evaluation_decision: str,
    has_version: bool,
) -> str:
    if feasibility_status == "not-feasible":
        return "blocked"
    if version_status == "active":
        return "published"
    if version_status == "testing" and latest_evaluation_decision == "pass":
        return "publish-ready"
    if latest_evaluation_decision:
        return "evaluation"
    if version_status == "testing":
        return "testing"
    if has_version or (feasibility_status == "feasible" and completeness_score >= 0.75):
        return "generation"
    if feasibility_status == "need-clarification":
        return "confirmation"
    return "requirement-intake"


def _humanize_workshop_phase(phase: str) -> str:
    mapping = {
        "requirement-intake": "需求收集中",
        "confirmation": "待确认",
        "generation": "生成阶段",
        "testing": "真数据测试中",
        "evaluation": "待修正",
        "publish-ready": "待确认发布",
        "published": "已发布",
        "blocked": "不可继续",
    }
    return mapping.get(str(phase or "").strip(), str(phase or "未定义阶段").strip() or "未定义阶段")


async def _resolve_workshop_session_phase_context(db: Any, session_id: str) -> dict[str, Any]:
    sessions = _get_collection(db, _WORKSHOP_SESSION_COLLECTION)
    specs = _get_collection(db, _WORKSHOP_SPEC_COLLECTION)
    versions = _get_collection(db, _WORKSHOP_VERSION_COLLECTION)
    evaluations = _get_collection(db, _WORKSHOP_EVALUATION_COLLECTION)

    clean_session_id = str(session_id or "").strip()
    if not clean_session_id:
        return {"exists": False, "session_id": clean_session_id, "guard_available": False}
    if sessions is None or specs is None or versions is None or evaluations is None:
        return {"exists": False, "session_id": clean_session_id, "guard_available": False}

    session_doc = await sessions.find_one({"session_id": clean_session_id})
    if not session_doc:
        return {"exists": False, "session_id": clean_session_id, "guard_available": True}

    spec_snapshot = _read_mapping_or_attr(session_doc, "current_spec_snapshot", {}) or {}
    spec_id = str(
        session_doc.get("spec_id")
        or _read_mapping_or_attr(spec_snapshot, "spec_id", "")
        or ""
    ).strip()
    spec_doc = await specs.find_one({"spec_id": spec_id}) if spec_id and specs is not None else None

    current_version_id = str(
        (spec_doc or {}).get("current_version_id")
        or _read_mapping_or_attr(spec_snapshot, "current_version_id", "")
        or ""
    ).strip()
    version_doc = await versions.find_one({"version_id": current_version_id}) if current_version_id and versions is not None else None
    latest_evaluation_doc = (
        await evaluations.find_one({"version_id": current_version_id}, sort=[("created_at", -1)])
        if current_version_id and evaluations is not None
        else None
    )

    feasibility_status = str(session_doc.get("feasibility_status") or "").strip().lower()
    try:
        completeness_score = float(session_doc.get("completeness_score") or 0)
    except Exception:
        completeness_score = 0.0
    version_status = str((version_doc or {}).get("status") or "").strip().lower()
    latest_evaluation_decision = str((latest_evaluation_doc or {}).get("decision") or "").strip().lower()
    phase = _compute_workshop_phase(
        feasibility_status=feasibility_status,
        completeness_score=completeness_score,
        version_status=version_status,
        latest_evaluation_decision=latest_evaluation_decision,
        has_version=bool(version_doc),
    )

    return {
        "exists": True,
        "guard_available": True,
        "session_id": clean_session_id,
        "spec_id": spec_id,
        "current_version_id": current_version_id,
        "feasibility_status": feasibility_status,
        "completeness_score": completeness_score,
        "version_status": version_status,
        "latest_evaluation_decision": latest_evaluation_decision,
        "phase": phase,
        "phase_label": _humanize_workshop_phase(phase),
    }


async def _resolve_workshop_version_phase_context(db: Any, version_id: str) -> dict[str, Any]:
    versions = _get_collection(db, _WORKSHOP_VERSION_COLLECTION)
    evaluations = _get_collection(db, _WORKSHOP_EVALUATION_COLLECTION)

    clean_version_id = str(version_id or "").strip()
    if not clean_version_id:
        return {"exists": False, "version_id": clean_version_id, "guard_available": False}
    if versions is None or evaluations is None:
        return {"exists": False, "version_id": clean_version_id, "guard_available": False}

    version_doc = await versions.find_one({"version_id": clean_version_id})
    if not version_doc:
        return {"exists": False, "version_id": clean_version_id, "guard_available": True}

    latest_evaluation_doc = (
        await evaluations.find_one({"version_id": clean_version_id}, sort=[("created_at", -1)])
        if evaluations is not None
        else None
    )
    version_status = str(version_doc.get("status") or "").strip().lower()
    latest_evaluation_decision = str((latest_evaluation_doc or {}).get("decision") or "").strip().lower()
    phase = _compute_workshop_phase(
        feasibility_status="feasible",
        completeness_score=1.0,
        version_status=version_status,
        latest_evaluation_decision=latest_evaluation_decision,
        has_version=True,
    )

    return {
        "exists": True,
        "guard_available": True,
        "version_id": clean_version_id,
        "spec_id": str(version_doc.get("spec_id") or "").strip(),
        "version_status": version_status,
        "latest_evaluation_decision": latest_evaluation_decision,
        "phase": phase,
        "phase_label": _humanize_workshop_phase(phase),
    }


async def _resolve_workshop_draft_target_context(db: Any, agent_id: str, thread_id: str = "") -> dict[str, Any]:
    specs = _get_collection(db, _WORKSHOP_SPEC_COLLECTION)
    versions = _get_collection(db, _WORKSHOP_VERSION_COLLECTION)
    threads = _get_collection(db, "embedded_nanobot_threads")

    clean_agent_id = str(agent_id or "").strip()
    clean_thread_id = str(thread_id or "").strip()
    default_context = {
        "exists": False,
        "guard_available": bool(specs is not None and versions is not None),
        "matched_existing_asset": False,
        "target_kind": "",
        "agent_id": clean_agent_id,
        "thread_id": clean_thread_id,
    }
    if not clean_agent_id:
        return default_context
    if specs is None or versions is None:
        return default_context

    version_doc = await versions.find_one({"version_id": clean_agent_id})
    if version_doc:
        phase_context = await _resolve_workshop_version_phase_context(db, clean_agent_id)
        return {
            **phase_context,
            "matched_existing_asset": True,
            "target_kind": "version_id",
            "agent_id": clean_agent_id,
            "thread_id": clean_thread_id,
        }

    spec_doc = await specs.find_one({"spec_id": clean_agent_id})
    if spec_doc:
        current_version_id = str(spec_doc.get("current_version_id") or "").strip()
        phase_context = {
            "exists": True,
            "guard_available": True,
            "spec_id": clean_agent_id,
            "version_id": current_version_id,
            "version_status": "",
            "latest_evaluation_decision": "",
            "phase": "generation",
            "phase_label": _humanize_workshop_phase("generation"),
        }
        if current_version_id:
            phase_context = await _resolve_workshop_version_phase_context(db, current_version_id)
        return {
            **phase_context,
            "matched_existing_asset": True,
            "target_kind": "spec_id",
            "agent_id": clean_agent_id,
            "thread_id": clean_thread_id,
        }

    if not clean_thread_id or threads is None:
        return default_context

    thread_doc = await threads.find_one({"thread_id": clean_thread_id})
    if thread_doc is None:
        thread_doc = await threads.find_one({"session_key": clean_thread_id})
    thread_context = dict((thread_doc or {}).get("thread_context") or {})
    resolved_spec_id = str(thread_context.get("spec_id") or "").strip()
    resolved_version_id = str(thread_context.get("version_id") or "").strip()
    resolved_version_status = str(thread_context.get("version_status") or "").strip().lower()
    if clean_agent_id not in {resolved_spec_id, resolved_version_id}:
        return default_context

    if resolved_version_id:
        phase_context = await _resolve_workshop_version_phase_context(db, resolved_version_id)
        if phase_context.get("exists"):
            return {
                **phase_context,
                "matched_existing_asset": True,
                "target_kind": "thread_context",
                "agent_id": clean_agent_id,
                "thread_id": clean_thread_id,
                "spec_id": resolved_spec_id or phase_context.get("spec_id"),
            }

    phase = "published" if resolved_version_status == "active" else "generation"
    return {
        "exists": True,
        "guard_available": True,
        "matched_existing_asset": True,
        "target_kind": "thread_context",
        "agent_id": clean_agent_id,
        "thread_id": clean_thread_id,
        "spec_id": resolved_spec_id,
        "version_id": resolved_version_id,
        "version_status": resolved_version_status,
        "latest_evaluation_decision": "",
        "phase": phase,
        "phase_label": _humanize_workshop_phase(phase),
    }


def _build_phase_guard_blocked_response(
    *,
    tool_name: str,
    blocked_code: str,
    message: str,
    next_action: str,
    phase_context: dict[str, Any],
    target_fields: dict[str, Any],
) -> str:
    return _json_response({
        "status": "blocked",
        "blocked_by": "phase_guard",
        "blocked_code": str(blocked_code or "phase_not_ready").strip() or "phase_not_ready",
        "message": message,
        "next_action": next_action,
        "current_phase": phase_context.get("phase"),
        "current_phase_label": phase_context.get("phase_label"),
        "summary": {
            "blocked_code": str(blocked_code or "phase_not_ready").strip() or "phase_not_ready",
            "current_phase": phase_context.get("phase"),
            "current_phase_label": phase_context.get("phase_label"),
            "version_status": phase_context.get("version_status"),
            "latest_evaluation_decision": phase_context.get("latest_evaluation_decision"),
            "feasibility_status": phase_context.get("feasibility_status"),
            "completeness_score": phase_context.get("completeness_score"),
        },
        "_tool_events": [
            _build_tool_stage_event(
                f"{tool_name}.phase_guard",
                "blocked",
                message,
            ),
        ],
        **target_fields,
    })


async def _resolve_workshop_test_llm_payload(
    db: Any,
    temperature: float = 0.2,
    max_tokens: int = 4000,
) -> dict[str, Any]:
    from app.services.intelligent_assistant_service import get_reasoning_llm_config

    config = await get_reasoning_llm_config(db)
    if not config:
        raise ValueError("系统中未找到可用的默认推理模型配置，请先在系统设置中配置大模型。")

    clean_provider = str(getattr(config, "provider", "") or "").strip()
    clean_model = str(
        getattr(config, "model", "")
        or getattr(config, "model_name", "")
        or ""
    ).strip()
    clean_backend_url = str(
        getattr(config, "base_url", "")
        or getattr(config, "api_base", "")
        or ""
    ).strip()
    clean_api_key = str(getattr(config, "api_key", "") or "").strip()

    try:
        temperature = float(getattr(config, "temperature", temperature) or temperature)
    except Exception:
        pass
    try:
        max_tokens = int(getattr(config, "max_tokens", max_tokens) or max_tokens)
    except Exception:
        pass

    if not clean_provider:
        raise ValueError("系统默认推理模型缺少 provider 配置")
    if not clean_model:
        raise ValueError("系统默认推理模型缺少 model 配置")

    return {
        "provider": clean_provider,
        "model": clean_model,
        "temperature": float(temperature),
        "max_tokens": int(max_tokens),
        "backend_url": clean_backend_url or None,
        "api_key": clean_api_key or None,
    }


def _read_mapping_or_attr(value: Any, field: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(field, default)
    return getattr(value, field, default)


async def _sync_linked_workshop_versions(
    db: Any,
    agent_id: str,
    candidate_config: dict[str, Any],
    resolved_tools: list[str],
    resolved_default_tools: list[str],
    max_tool_calls: int,
) -> dict[str, Any]:
    versions = _get_collection(db, "agent_versions")
    if versions is None:
        return {
            "status": "skipped",
            "reason": "agent_versions_unavailable",
            "attempted_version_ids": [],
            "synced_version_ids": [],
            "skipped": [],
        }

    metadata = dict(candidate_config.get("metadata") or {})
    version_candidates = [
        metadata.get("version_id"),
        metadata.get("latest_workshop_version_id"),
        metadata.get("current_version_id"),
    ]
    spec_id = str(metadata.get("spec_id") or "").strip()
    if spec_id:
        specs = _get_collection(db, "agent_specs")
        if specs is not None:
            spec_doc = await specs.find_one({"spec_id": spec_id}, {"current_version_id": 1}) or {}
            version_candidates.append(spec_doc.get("current_version_id"))

    target_version_ids = _dedupe_string_list([str(item or "").strip() for item in version_candidates])
    if not target_version_ids:
        return {
            "status": "not_linked",
            "reason": "no_linked_version",
            "attempted_version_ids": [],
            "synced_version_ids": [],
            "skipped": [],
        }

    synced_version_ids: list[str] = []
    skipped: list[dict[str, str]] = []
    workshop_service = AgentWorkshopService(db=db)

    for version_id in target_version_ids:
        version_doc = await versions.find_one({"version_id": version_id})
        if not version_doc:
            skipped.append({"version_id": version_id, "reason": "version_not_found"})
            continue

        version_status = str(version_doc.get("status") or "").strip().lower()
        if version_status == "active":
            skipped.append({"version_id": version_id, "reason": "version_active"})
            continue

        await workshop_service.sync_version_required_tools(
            version_id=version_id,
            required_tools=list(resolved_tools),
            default_tools=list(resolved_default_tools),
            max_tool_calls=int(max_tool_calls),
        )
        synced_version_ids.append(version_id)

    if synced_version_ids:
        logger.info(
            "已同步候选 Agent %s 的工具绑定到 Agent Workshop 版本: %s",
            agent_id,
            ", ".join(synced_version_ids),
        )

    return {
        "status": "ok" if synced_version_ids else "skipped",
        "reason": None if synced_version_ids else "no_sync_target",
        "attempted_version_ids": target_version_ids,
        "synced_version_ids": synced_version_ids,
        "skipped": skipped,
    }


async def _auto_build_workshop_version_result(session_id: str) -> dict[str, Any]:
    return _parse_json_tool_result(await build_agent_workshop_version.ainvoke({
        "session_id": session_id,
    }))


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
        f"- 生成后运行诊断方式（非正式验收）：{str(test_strategy or '未指定').strip()}",
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


async def _is_orphaned_workshop_runtime_agent(doc: dict[str, Any], db: Any) -> bool:
    metadata = doc.get("metadata") or {}
    source = str(metadata.get("source") or "").strip().lower()
    if source not in {"agent_workshop", "nanobot_generated"}:
        return False

    version_id = str(metadata.get("version_id") or "").strip()
    spec_id = str(metadata.get("spec_id") or "").strip()
    if not version_id and not spec_id:
        return False

    try:
        if version_id:
            version_doc = await _get_collection(db, "agent_versions").find_one({"version_id": version_id}, {"_id": 1})
            if version_doc:
                return False
        if spec_id:
            spec_doc = await _get_collection(db, "agent_specs").find_one({"spec_id": spec_id}, {"_id": 1})
            if spec_doc:
                return False
    except Exception as exc:
        logger.warning("检查工坊运行时 Agent 是否失联失败: %s", exc)
        return False

    return True


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


def _format_prompt_template_detail(doc: dict[str, Any]) -> dict[str, Any]:
    formatted = _format_prompt_template_record(doc)
    content = doc.get("content") or {}
    formatted["content"] = {
        "system_prompt": str(content.get("system_prompt") or "").strip(),
        "user_prompt": str(content.get("user_prompt") or "").strip(),
        "tool_guidance": str(content.get("tool_guidance") or "").strip(),
        "analysis_requirements": str(content.get("analysis_requirements") or "").strip(),
        "output_format": str(content.get("output_format") or "").strip(),
        "constraints": str(content.get("constraints") or "").strip(),
    }
    formatted["remark"] = str(doc.get("remark") or "").strip()
    formatted["is_system"] = bool(doc.get("is_system", False))
    formatted["created_at"] = doc.get("created_at")
    formatted["preference_type"] = doc.get("preference_type")
    return formatted


def _parse_auto_bool(raw: str, default: bool | None = None) -> bool | None:
    text = str(raw or "").strip().lower()
    if not text or text == "auto":
        return default
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default


async def _resolve_effective_prompt_template_payload(
    *,
    agent_type: str,
    agent_name: str,
    preference_id: str = "neutral",
    workflow_id: str = "",
    node_id: str = "",
    is_debug_mode: bool = False,
    debug_template_id: str = "",
    user_id: str = "",
) -> dict[str, Any]:
    clean_agent_type = str(agent_type or "").strip()
    clean_agent_name = str(agent_name or "").strip()
    if not clean_agent_type or not clean_agent_name:
        return {"status": "error", "message": "agent_type 和 agent_name 不能为空"}

    resolved_user_id = str(user_id or "").strip()
    if not resolved_user_id:
        try:
            resolved_user_id = str(require_current_user_id() or "").strip()
        except Exception:
            resolved_user_id = ""

    context = {
        "user_id": resolved_user_id or None,
        "preference_id": str(preference_id or "neutral").strip() or "neutral",
        "workflow_id": str(workflow_id or "").strip() or None,
        "node_id": str(node_id or "").strip() or None,
        "is_debug_mode": bool(is_debug_mode),
        "debug_template_id": str(debug_template_id or "").strip() or None,
    }

    from tradingagents.utils.template_client import get_template_client

    template_client = get_template_client()
    effective = template_client.get_effective_template(
        clean_agent_type,
        clean_agent_name,
        user_id=resolved_user_id or None,
        preference_id=context["preference_id"],
        context=context,
        workflow_id=context["workflow_id"],
        node_id=context["node_id"],
    )
    if not effective:
        return {
            "status": "error",
            "message": "未找到当前生效模板",
            "resolution_input": {
                "agent_type": clean_agent_type,
                "agent_name": clean_agent_name,
                "user_id": resolved_user_id,
                "preference_id": context["preference_id"],
                "workflow_id": context["workflow_id"],
                "node_id": context["node_id"],
                "is_debug_mode": context["is_debug_mode"],
                "debug_template_id": context["debug_template_id"],
            },
        }

    return {
        "status": "ok",
        "resolution_input": {
            "agent_type": clean_agent_type,
            "agent_name": clean_agent_name,
            "user_id": resolved_user_id,
            "preference_id": context["preference_id"],
            "workflow_id": context["workflow_id"],
            "node_id": context["node_id"],
            "is_debug_mode": context["is_debug_mode"],
            "debug_template_id": context["debug_template_id"],
        },
        "template": effective,
    }


async def _resolve_current_thread_effective_template_input(
    *,
    db: Any,
    user_id: str,
    thread_id: str,
    preference_id: str = "neutral",
    workflow_id: str = "",
    node_id: str = "",
    debug_template_id: str = "",
    debug_mode: str = "auto",
    agent_type: str = "",
    agent_name: str = "",
) -> dict[str, Any]:
    clean_user_id = str(user_id or "").strip()
    clean_thread_id = str(thread_id or "").strip()
    if not clean_user_id or not clean_thread_id:
        return {"status": "error", "message": "user_id 和 thread_id 不能为空"}

    threads = _get_collection(db, "embedded_nanobot_threads")
    if threads is None:
        return {"status": "error", "message": "当前数据库中不可用 embedded_nanobot_threads 集合"}

    thread_doc = await threads.find_one({"user_id": clean_user_id, "thread_id": clean_thread_id})
    if thread_doc is None:
        thread_doc = await threads.find_one({"user_id": clean_user_id, "session_key": clean_thread_id})
    if thread_doc is None:
        return {"status": "error", "message": f"未找到 thread_id={clean_thread_id} 对应的 Nanobot 会话"}

    thread_context = dict(thread_doc.get("thread_context") or {})
    channel = str(thread_doc.get("channel") or "embedded").strip() or "embedded"
    resolved_version_id = str(thread_context.get("version_id") or "").strip()
    resolved_spec_id = str(thread_context.get("spec_id") or "").strip()
    resolved_version_status = str(thread_context.get("version_status") or "").strip()
    explicit_workflow_id = str(thread_context.get("workflow_id") or "").strip()
    explicit_node_id = str(thread_context.get("node_id") or "").strip()
    explicit_preference_id = str(thread_context.get("preference_id") or "").strip()
    explicit_debug_template_id = str(thread_context.get("debug_template_id") or "").strip()

    specs = _get_collection(db, "agent_specs")
    versions = _get_collection(db, "agent_versions")
    if not resolved_version_id and resolved_spec_id and specs is not None:
        spec_doc = await specs.find_one({"spec_id": resolved_spec_id}, {"current_version_id": 1}) or {}
        resolved_version_id = str(spec_doc.get("current_version_id") or "").strip()

    version_doc = None
    if resolved_version_id and versions is not None:
        version_doc = await versions.find_one({"version_id": resolved_version_id})

    resolved_agent_type = str(agent_type or "").strip()
    resolved_agent_name = str(agent_name or "").strip()
    if version_doc is not None:
        if not resolved_agent_type:
            resolved_agent_type = "custom_agent"
        if not resolved_agent_name:
            resolved_agent_name = str(version_doc.get("version_id") or resolved_version_id).strip()

    if not resolved_agent_type or not resolved_agent_name:
        return {
            "status": "error",
            "message": "当前线程缺少足够上下文，无法自动推断 agent_type/agent_name；请先让线程进入带版本上下文的状态，或显式传入 agent_type 和 agent_name",
            "thread_context": thread_context,
        }

    template_ref = dict((version_doc or {}).get("prompt_template_ref") or {})
    resolved_debug_template_id = str(debug_template_id or explicit_debug_template_id or template_ref.get("template_id") or "").strip()
    resolved_workflow_id = str(workflow_id or explicit_workflow_id or "").strip()
    if not resolved_workflow_id and resolved_version_id and channel == "agent_workshop":
        resolved_workflow_id = f"agent_workshop_debug_{resolved_version_id}"

    resolved_node_id = str(node_id or explicit_node_id or "").strip()
    requested_preference_id = str(preference_id or "").strip()
    if explicit_preference_id and requested_preference_id in {"", "neutral"}:
        resolved_preference_id = explicit_preference_id
    else:
        resolved_preference_id = requested_preference_id or "neutral"
    explicit_debug_mode = _parse_auto_bool(debug_mode, default=None)
    if explicit_debug_mode is None:
        resolved_is_debug_mode = bool(
            resolved_debug_template_id and (
                channel == "agent_workshop"
                or resolved_version_status.lower() in {"testing", "draft"}
            )
        )
    else:
        resolved_is_debug_mode = explicit_debug_mode

    return {
        "status": "ok",
        "thread_id": str(thread_doc.get("thread_id") or clean_thread_id),
        "session_key": str(thread_doc.get("session_key") or "").strip(),
        "channel": channel,
        "thread_context": thread_context,
        "resolution_input": {
            "agent_type": resolved_agent_type,
            "agent_name": resolved_agent_name,
            "user_id": clean_user_id,
            "preference_id": resolved_preference_id,
            "workflow_id": resolved_workflow_id or None,
            "node_id": resolved_node_id or None,
            "is_debug_mode": resolved_is_debug_mode,
            "debug_template_id": resolved_debug_template_id or None,
        },
        "resolution_source": {
            "resolved_spec_id": resolved_spec_id or None,
            "resolved_version_id": resolved_version_id or None,
            "resolved_version_status": resolved_version_status or None,
            "used_version_doc": bool(version_doc is not None),
            "used_thread_channel": channel,
            "used_explicit_workflow_id": bool(explicit_workflow_id),
            "used_explicit_node_id": bool(explicit_node_id),
            "used_explicit_preference_id": bool(explicit_preference_id),
            "used_explicit_debug_template_id": bool(explicit_debug_template_id),
        },
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
            if await _is_orphaned_workshop_runtime_agent(doc, db):
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
    description="查看数据库中的 agent_specs 和 agent_versions 摘要，支持按关键词、workshop_session_id 或 spec_id/version_id/agent_id 精确核验，用于确认是否已有可复用的配置式 Agent 规格、版本或提示词资产。",
    category="assistant_ops",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    when_to_use=(
        "当 Nanobot 需要确认是否已有接近需求的 Agent 规格、已构建版本或提示词资产时使用。"
        "适合在决定新建前先看已有配置式资产，或在当前线程已知 workshop_session_id/spec_id/version_id 时先做精确核验。"
    ),
    when_not_to_use="不适合做通用工具搜索，也不适合直接发布 Agent；它只汇总工坊资产摘要。",
    returns=(
        "返回 JSON 字符串，包含 spec 摘要、version 摘要、required_tools、required_capabilities、"
        "prompt_template_ref 等信息，以及本次使用或解析后的精确过滤条件。"
    ),
    example="inspect_agent_workshop_assets(workshop_session_id='session_001')",
    related_tools=["inspect_runtime_agent_configs", "inspect_agent_blueprints", "search_project_capabilities"],
)
async def inspect_agent_workshop_assets(
    keyword: Annotated[str, "按 spec 名称、目标、version agent_metadata 模糊筛选，可留空"] = "",
    workshop_session_id: Annotated[str, "按 Agent 工坊 session_id 精确定位当前 spec/version，可留空"] = "",
    spec_id: Annotated[str, "按 spec_id 精确筛选，可留空；适合当前线程已知 spec_id 的场景"] = "",
    version_id: Annotated[str, "按 version_id 精确筛选，可留空；适合当前线程已知 version_id 的场景"] = "",
    agent_id: Annotated[str, "按运行时 agent_id 精确筛选，可留空"] = "",
    limit: Annotated[int, "每类结果返回条数，默认 10，最大 20"] = 10,
    include_archived: Annotated[bool, "是否包含 archived 状态的 spec/version，默认 false"] = False,
) -> str:
    """查看 Agent 工坊资产摘要。"""
    try:
        db = get_mongo_db()
        sessions_collection = _get_collection(db, _WORKSHOP_SESSION_COLLECTION)
        specs_collection = _get_collection(db, "agent_specs")
        versions_collection = _get_collection(db, "agent_versions")
        if specs_collection is None or versions_collection is None:
            return _json_response({"status": "error", "message": "当前数据库中不可用 agent_specs 或 agent_versions 集合"})

        capped_limit = max(1, min(int(limit), 20))
        clean_keyword = str(keyword or "").strip()
        clean_workshop_session_id = str(workshop_session_id or "").strip()
        clean_spec_id = str(spec_id or "").strip()
        clean_version_id = str(version_id or "").strip()
        clean_agent_id = str(agent_id or "").strip()

        resolved_spec_id = clean_spec_id
        resolved_version_id = clean_version_id
        if clean_workshop_session_id:
            if sessions_collection is None:
                return _json_response({
                    "status": "error",
                    "message": "当前数据库中不可用 agent_workshop_sessions 集合，无法按 workshop_session_id 核验",
                })
            session_doc = await sessions_collection.find_one({"session_id": clean_workshop_session_id})
            if session_doc is None:
                return _json_response({
                    "status": "ok",
                    "keyword": clean_keyword,
                    "workshop_session_id": clean_workshop_session_id,
                    "spec_id": clean_spec_id,
                    "version_id": clean_version_id,
                    "agent_id": clean_agent_id,
                    "include_archived": include_archived,
                    "spec_count": 0,
                    "version_count": 0,
                    "specs": [],
                    "versions": [],
                    "message": f"未找到 session_id={clean_workshop_session_id} 对应的 Agent 工坊会话",
                    "design_references": [
                        "docs/design/v3.0/agent-workshop-interface-sequence.md",
                        "docs/design/v3.0/implementation-status-report.md",
                    ],
                })
            spec_snapshot = _read_mapping_or_attr(session_doc, "current_spec_snapshot", {}) or {}
            if not resolved_spec_id:
                resolved_spec_id = str(
                    session_doc.get("spec_id")
                    or _read_mapping_or_attr(spec_snapshot, "spec_id", "")
                    or ""
                ).strip()
            if not resolved_version_id:
                resolved_version_id = str(
                    _read_mapping_or_attr(spec_snapshot, "current_version_id", "")
                    or session_doc.get("current_version_id")
                    or ""
                ).strip()

        resolved_spec_doc = None
        if resolved_spec_id:
            resolved_spec_doc = await specs_collection.find_one({"spec_id": resolved_spec_id})
            if resolved_spec_doc is not None and not resolved_version_id:
                resolved_version_id = str(resolved_spec_doc.get("current_version_id") or "").strip()

        specs_cursor = specs_collection.find({}, {"_id": 0})
        versions_cursor = versions_collection.find({}, {"_id": 0})
        if hasattr(specs_cursor, "sort"):
            specs_cursor = specs_cursor.sort("updated_at", -1)
        if hasattr(versions_cursor, "sort"):
            versions_cursor = versions_cursor.sort("updated_at", -1)

        spec_docs = await specs_cursor.to_list(length=max(capped_limit * 5, 20))
        version_docs = await versions_cursor.to_list(length=max(capped_limit * 5, 20))

        matched_spec_ids_from_versions: set[str] = set()

        spec_results: list[dict[str, Any]] = []
        for doc in spec_docs:
            if not include_archived and str(doc.get("status") or "") == "archived":
                continue
            formatted = _format_agent_spec(doc)
            if resolved_spec_id and str(formatted.get("spec_id") or "").strip() != resolved_spec_id:
                continue
            if not resolved_spec_id and not resolved_version_id and not clean_agent_id and not clean_workshop_session_id and not _match_keyword(
                clean_keyword,
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
            if resolved_spec_id and str(formatted.get("spec_id") or "").strip() != resolved_spec_id:
                continue
            if resolved_version_id and str(formatted.get("version_id") or "").strip() != resolved_version_id:
                continue
            if clean_agent_id and str(formatted.get("agent_id") or "").strip() != clean_agent_id:
                continue
            if not resolved_spec_id and not resolved_version_id and not clean_agent_id and not clean_workshop_session_id and not _match_keyword(
                clean_keyword,
                formatted.get("version_id"),
                formatted.get("spec_id"),
                formatted.get("agent_id"),
                formatted.get("agent_name"),
                formatted.get("required_tools"),
                formatted.get("required_capabilities"),
            ):
                continue
            version_results.append(formatted)
            if formatted.get("spec_id"):
                matched_spec_ids_from_versions.add(str(formatted.get("spec_id")))
            if len(version_results) >= capped_limit:
                break

        if matched_spec_ids_from_versions and not clean_spec_id:
            existing_spec_ids = {str(item.get("spec_id") or "") for item in spec_results}
            for doc in spec_docs:
                if not include_archived and str(doc.get("status") or "") == "archived":
                    continue
                formatted = _format_agent_spec(doc)
                formatted_spec_id = str(formatted.get("spec_id") or "")
                if formatted_spec_id not in matched_spec_ids_from_versions or formatted_spec_id in existing_spec_ids:
                    continue
                spec_results.append(formatted)
                existing_spec_ids.add(formatted_spec_id)
                if len(spec_results) >= capped_limit:
                    break

        return _json_response({
            "keyword": clean_keyword,
            "workshop_session_id": clean_workshop_session_id,
            "spec_id": resolved_spec_id,
            "version_id": resolved_version_id,
            "agent_id": clean_agent_id,
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
    tool_id="inspect_prompt_templates",
    name="查看提示词模板库",
    description="查询数据库中 prompt_templates 集合的模板摘要，支持按 agent_type、agent_name、status 和关键词筛选。",
    category="assistant_ops",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    when_to_use="当需要确认数据库中有哪些提示词模板、某个 Agent 当前绑定了哪些模板，或要为 Nanobot 查模板资产时使用。",
    when_not_to_use="不适合直接修改模板正文；只做读取和筛选。",
    returns="返回 JSON 字符串，包含模板摘要列表。",
    example="inspect_prompt_templates(agent_type='universal', keyword='估值', status='active', limit=10)",
    related_tools=["get_prompt_template_detail", "inspect_agent_workshop_assets", "create_or_update_universal_agent_prompt_template"],
)
async def inspect_prompt_templates(
    agent_type: Annotated[str, "按 agent_type 精确筛选，可留空"] = "",
    agent_name: Annotated[str, "按 agent_name 精确筛选，可留空"] = "",
    status: Annotated[str, "按状态筛选，如 active/draft，可留空"] = "",
    keyword: Annotated[str, "按 template_name、agent_name、remark 模糊筛选，可留空"] = "",
    is_system_only: Annotated[bool, "是否仅查看系统模板，默认 false"] = False,
    limit: Annotated[int, "返回条数，默认 10，最大 50"] = 10,
) -> str:
    """查看数据库中的提示词模板摘要。"""
    try:
        db = get_mongo_db()
        templates = _get_collection(db, "prompt_templates")
        if templates is None:
            return _json_response({"status": "error", "message": "当前数据库中不可用 prompt_templates 集合"})

        capped_limit = max(1, min(int(limit), 50))
        cursor = templates.find({}, {"_id": 1})
        if hasattr(cursor, "sort"):
            cursor = cursor.sort("updated_at", -1)
        docs = await cursor.to_list(length=max(capped_limit * 5, 50))

        clean_agent_type = str(agent_type or "").strip()
        clean_agent_name = str(agent_name or "").strip()
        clean_status = str(status or "").strip()

        results: list[dict[str, Any]] = []
        for doc in docs:
            if clean_agent_type and str(doc.get("agent_type") or "").strip() != clean_agent_type:
                continue
            if clean_agent_name and str(doc.get("agent_name") or "").strip() != clean_agent_name:
                continue
            if clean_status and str(doc.get("status") or "").strip() != clean_status:
                continue
            if is_system_only and not bool(doc.get("is_system", False)):
                continue
            if not _match_keyword(keyword, doc.get("template_name"), doc.get("agent_name"), doc.get("remark"), doc.get("agent_type")):
                continue
            results.append(_format_prompt_template_record(doc))
            if len(results) >= capped_limit:
                break

        return _json_response({
            "status": "ok",
            "count": len(results),
            "filters": {
                "agent_type": clean_agent_type,
                "agent_name": clean_agent_name,
                "status": clean_status,
                "keyword": keyword,
                "is_system_only": is_system_only,
            },
            "templates": results,
        })
    except Exception as exc:
        logger.error("查看提示词模板库失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"查看提示词模板库失败: {exc}"})


@tool
@register_tool(
    tool_id="get_prompt_template_detail",
    name="查看提示词模板详情",
    description="按 template_id 读取数据库中 prompt_templates 的完整模板内容。",
    category="assistant_ops",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    when_to_use="当 Nanobot 已经知道 template_id，需要查看完整 system_prompt、tool_guidance、output_format 等正文时使用。",
    when_not_to_use="不适合模糊搜索模板列表；那种场景应先使用 inspect_prompt_templates。",
    returns="返回 JSON 字符串，包含模板详情和完整 content 字段。",
    example="get_prompt_template_detail(template_id='69cfdf8db1828a17f6b00cfb')",
    related_tools=["inspect_prompt_templates", "create_or_update_universal_agent_prompt_template"],
)
async def get_prompt_template_detail(
    template_id: Annotated[str, "prompt_templates 集合中的 _id 字符串"],
) -> str:
    """查看数据库中单个提示词模板的完整内容。"""
    try:
        clean_template_id = str(template_id or "").strip()
        if not clean_template_id:
            return _json_response({"status": "error", "message": "template_id 不能为空"})

        db = get_mongo_db()
        templates = _get_collection(db, "prompt_templates")
        if templates is None:
            return _json_response({"status": "error", "message": "当前数据库中不可用 prompt_templates 集合"})

        cursor = templates.find({}, {"_id": 1})
        docs = await cursor.to_list(length=500)
        matched = next((doc for doc in docs if str(doc.get("_id") or doc.get("id") or "").strip() == clean_template_id), None)
        if matched is None:
            return _json_response({"status": "error", "message": f"未找到 template_id={clean_template_id} 对应的模板"})

        return _json_response({
            "status": "ok",
            "template": _format_prompt_template_detail(matched),
        })
    except Exception as exc:
        logger.error("查看提示词模板详情失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"查看提示词模板详情失败: {exc}"})


@tool
@register_tool(
    tool_id="get_effective_prompt_template",
    name="获取当前生效提示词模板",
    description="按系统真实优先级解析当前生效模板，支持调试模板、节点专属模板、流程专属模板、用户激活模板和系统默认模板。",
    category="assistant_ops",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    when_to_use="当需要知道当前 Agent 在调试或正式运行时实际会使用哪份模板，而不是只看模板库列表时使用。",
    when_not_to_use="不适合做模板库模糊搜索；那种场景应先使用 inspect_prompt_templates。",
    returns="返回 JSON 字符串，包含当前生效模板内容、来源、template_id、version 以及解析参数。",
    example="get_effective_prompt_template(agent_type='universal', agent_name='valuation_candidate_v1', workflow_id='wf_001', node_id='node_002', is_debug_mode=true, debug_template_id='69cfdf8db1828a17f6b00cfb')",
    related_tools=["inspect_prompt_templates", "get_prompt_template_detail", "create_or_update_universal_agent_prompt_template"],
)
async def get_effective_prompt_template(
    agent_type: Annotated[str, "Agent 类型，如 universal、analysts、researchers"],
    agent_name: Annotated[str, "Agent 名称或运行时 agent_id"],
    preference_id: Annotated[str, "偏好 ID，默认 neutral"] = "neutral",
    workflow_id: Annotated[str, "工作流 ID，可留空"] = "",
    node_id: Annotated[str, "节点 ID，可留空"] = "",
    is_debug_mode: Annotated[bool, "是否按调试模式解析，默认 false"] = False,
    debug_template_id: Annotated[str, "调试模板 ID；调试时可留空或显式指定"] = "",
    user_id: Annotated[str, "用户 ID；不传则默认取当前对话上下文用户"] = "",
) -> str:
    """获取当前会命中的生效提示词模板。"""
    try:
        return _json_response(await _resolve_effective_prompt_template_payload(
            agent_type=agent_type,
            agent_name=agent_name,
            preference_id=preference_id,
            workflow_id=workflow_id,
            node_id=node_id,
            is_debug_mode=is_debug_mode,
            debug_template_id=debug_template_id,
            user_id=user_id,
        ))
    except Exception as exc:
        logger.error("获取当前生效提示词模板失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"获取当前生效提示词模板失败: {exc}"})


@tool
@register_tool(
    tool_id="get_current_thread_effective_prompt_template",
    name="获取当前线程生效提示词模板",
    description="基于当前 Nanobot 线程上下文自动推断当前正在调试或讨论的 Agent 版本，再解析该上下文下实际生效的提示词模板。",
    category="assistant_ops",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    when_to_use="当用户问当前线程里现在实际命中了哪份模板，且上下文已经在当前 Nanobot 会话中时优先使用。",
    when_not_to_use="不适合做模板库浏览；那种场景应先使用 inspect_prompt_templates。",
    returns="返回 JSON 字符串，包含线程上下文、自动推断得到的 resolution_input 和实际生效模板内容。",
    example="get_current_thread_effective_prompt_template()",
    related_tools=["get_effective_prompt_template", "inspect_prompt_templates", "get_prompt_template_detail"],
)
async def get_current_thread_effective_prompt_template(
    preference_id: Annotated[str, "偏好 ID，默认 neutral"] = "neutral",
    workflow_id: Annotated[str, "可显式覆盖自动推断的工作流 ID，可留空"] = "",
    node_id: Annotated[str, "可显式覆盖自动推断的节点 ID，可留空"] = "",
    debug_template_id: Annotated[str, "可显式覆盖自动推断的调试模板 ID，可留空"] = "",
    debug_mode: Annotated[str, "调试模式，支持 auto/true/false，默认 auto"] = "auto",
    user_id: Annotated[str, "用户 ID；不传则默认取当前对话上下文用户"] = "",
    thread_id: Annotated[str, "线程 ID；不传则默认取当前对话上下文线程"] = "",
    agent_type: Annotated[str, "若自动推断失败，可显式指定 agent_type"] = "",
    agent_name: Annotated[str, "若自动推断失败，可显式指定 agent_name"] = "",
) -> str:
    """基于当前 Nanobot 线程自动解析当前生效模板。"""
    try:
        resolved_user_id = str(user_id or "").strip()
        if not resolved_user_id:
            try:
                resolved_user_id = str(require_current_user_id() or "").strip()
            except Exception:
                resolved_user_id = ""

        resolved_thread_id = str(thread_id or "").strip()
        if not resolved_thread_id:
            resolved_thread_id = str(get_current_assistant_thread_id() or "").strip()

        if not resolved_user_id or not resolved_thread_id:
            return _json_response({
                "status": "error",
                "message": "当前上下文缺少 user_id 或 thread_id，无法自动解析当前线程生效模板；请显式传入 thread_id/user_id 或退回使用 get_effective_prompt_template",
            })

        db = get_mongo_db()
        inferred = await _resolve_current_thread_effective_template_input(
            db=db,
            user_id=resolved_user_id,
            thread_id=resolved_thread_id,
            preference_id=preference_id,
            workflow_id=workflow_id,
            node_id=node_id,
            debug_template_id=debug_template_id,
            debug_mode=debug_mode,
            agent_type=agent_type,
            agent_name=agent_name,
        )
        if inferred.get("status") != "ok":
            return _json_response(inferred)

        resolution_input = dict(inferred.get("resolution_input") or {})
        payload = await _resolve_effective_prompt_template_payload(
            agent_type=str(resolution_input.get("agent_type") or ""),
            agent_name=str(resolution_input.get("agent_name") or ""),
            preference_id=str(resolution_input.get("preference_id") or "neutral"),
            workflow_id=str(resolution_input.get("workflow_id") or ""),
            node_id=str(resolution_input.get("node_id") or ""),
            is_debug_mode=bool(resolution_input.get("is_debug_mode")),
            debug_template_id=str(resolution_input.get("debug_template_id") or ""),
            user_id=str(resolution_input.get("user_id") or resolved_user_id),
        )
        return _json_response({
            **payload,
            "thread_id": inferred.get("thread_id"),
            "session_key": inferred.get("session_key"),
            "channel": inferred.get("channel"),
            "thread_context": inferred.get("thread_context") or {},
            "resolution_source": inferred.get("resolution_source") or {},
        })
    except Exception as exc:
        logger.error("获取当前线程生效提示词模板失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"获取当前线程生效提示词模板失败: {exc}"})


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
    workflow_stage: Annotated[str, "工作流阶段，默认 analyst"] = "analyst",
    report_label: Annotated[str, "报告展示标签，可为空"] = "",
    show_in_reports: Annotated[bool, "是否进入工作流报告列表，默认 true"] = True,
    execution_order: Annotated[int, "工作流展示/执行顺序，默认 50"] = 50,
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
            "workflow_stage": workflow_stage,
            "output_field": output_field,
            "report_label": report_label or f"【{clean_name}】",
            "show_in_reports": show_in_reports,
            "execution_order": int(execution_order),
            "generation_status": "candidate",
        })

        update_doc = {
            "agent_id": clean_agent_id,
            "name": clean_name,
            "agent_name": clean_name,
            "description": clean_description,
            "output_field": output_field,
            "workflow_stage": workflow_stage,
            "report_label": report_label or f"【{clean_name}】",
            "node_name": clean_name,
            "execution_order": int(execution_order),
            "show_in_reports": show_in_reports,
            "callable_surfaces": surfaces,
            "category": category,
            "enabled": enabled,
            "metadata": metadata,
            "updated_at": _utc_now_iso(),
        }
        if not existing:
            update_doc["created_at"] = _utc_now_iso()

        await collection.update_one({"agent_id": clean_agent_id}, {"$set": update_doc}, upsert=True)
        persisted = await collection.find_one({"agent_id": clean_agent_id}, {"_id": 0}) or update_doc
        runtime_contract = {
            "agent_id": clean_agent_id,
            "agent_name": clean_name,
            "description": clean_description,
            "output_field": output_field,
            "workflow_stage": workflow_stage,
            "report_label": report_label or f"【{clean_name}】",
            "node_name": clean_name,
            "execution_order": int(execution_order),
            "show_in_reports": show_in_reports,
            "category": category,
            "callable_surfaces": surfaces,
        }
        return _json_response({
            "status": "ok",
            "action": "updated" if existing else "created",
            "agent": _format_runtime_agent_config(persisted, [], None),
            "runtime_contract": runtime_contract,
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
    output_field: Annotated[str, "输出字段名；若留空或给出通用名，系统会自动生成带 agent 语义的专属字段名"] = "analysis_report",
    workflow_stage: Annotated[str, "工作流阶段，默认 analyst"] = "analyst",
    report_label: Annotated[str, "报告展示标签，可为空"] = "",
    show_in_reports: Annotated[bool, "是否进入工作流报告列表，默认 true"] = True,
    execution_order: Annotated[int, "工作流展示/执行顺序，默认 50"] = 50,
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
        draft_target_context = await _resolve_workshop_draft_target_context(
            db,
            clean_agent_id,
            thread_id=current_thread_id,
        )
        if draft_target_context.get("guard_available") and draft_target_context.get("matched_existing_asset"):
            version_status = str(draft_target_context.get("version_status") or "").strip().lower()
            current_phase = str(draft_target_context.get("phase") or "").strip().lower()
            if version_status == "active" or current_phase == "published":
                resolved_version_id = str(draft_target_context.get("version_id") or clean_agent_id).strip()
                resolved_spec_id = str(draft_target_context.get("spec_id") or "").strip()
                return _build_phase_guard_blocked_response(
                    tool_name="create_or_update_agent_workshop_draft",
                    blocked_code="active_version_requires_iteration",
                    message=(
                        "当前目标指向已发布版本；create_or_update_agent_workshop_draft 只适用于新的候选 Draft，"
                        "不能直接拿现有 spec_id 或 version_id 覆盖已发布资产。"
                    ),
                    next_action=(
                        f"请先调用 iterate_agent_workshop_version(version_id='{resolved_version_id}') 创建下一轮，"
                        "再在新会话里继续修改。"
                        if resolved_version_id
                        else "请先 inspect 当前版本并发起 iterate，再在下一轮会话中继续修改。"
                    ),
                    phase_context=draft_target_context,
                    target_fields={
                        "agent_id": clean_agent_id,
                        "spec_id": resolved_spec_id or None,
                        "version_id": resolved_version_id or None,
                    },
                )
        result = await AgentWorkshopService(db=db).create_nanobot_draft(
            agent_id=clean_agent_id,
            agent_name=clean_agent_name,
            target_responsibility=clean_responsibility,
            output_field=output_field,
            tool_ids=_parse_string_list(tool_ids),
            non_goals=_parse_string_list(non_goals),
            preferred_methods=_parse_string_list(preferred_methods),
            constraints=_parse_string_list(constraints),
            runtime_contract={
                "output_field": output_field,
                "workflow_stage": workflow_stage,
                "report_label": report_label,
                "show_in_reports": show_in_reports,
                "execution_order": int(execution_order),
                "category": "analyst" if str(workflow_stage or "").strip().lower() == "analyst" else "researcher",
            },
            prompt_contract={
                "agent_type": "universal",
                "agent_name": clean_agent_id,
                "must_match_universal_agent": True,
            },
            tooling_contract={
                "required_tools": _parse_string_list(tool_ids),
            },
            owner_user_id=user_id,
            source_thread_id=current_thread_id,
        )
        return _json_response({**result, "status": "ok"})
    except Exception as exc:
        logger.error("创建或更新 Agent 工坊 Draft 失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"创建或更新 Agent 工坊 Draft 失败: {exc}"})


@tool
@register_tool(
    tool_id="analyze_agent_workshop_gaps",
    name="执行 Agent 工坊缺口分析",
    description="让 Nanobot 直接触发 Agent 工坊会话的缺口分析阶段，并返回结构化缺口摘要。",
    category="assistant_ops",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    when_to_use="当 Agent 工坊 Draft 已经确认到可以进入缺口分析，且希望继续由 Nanobot 主导后续阶段时使用。",
    when_not_to_use="不适合在还没有有效 session_id 或规格尚未成形时调用。",
    returns="返回 JSON 字符串，包含 session_id、spec_id 与 gap_report 摘要。",
    example="analyze_agent_workshop_gaps(session_id='session_123')",
    related_tools=["generate_agent_workshop_tooling_plan", "build_agent_workshop_version"],
)
async def analyze_agent_workshop_gaps(
    session_id: Annotated[str, "Agent 工坊会话 ID"],
) -> str:
    """执行 Agent 工坊缺口分析并返回结构化结果。"""
    try:
        clean_session_id = str(session_id or "").strip()
        if not clean_session_id:
            return _json_response({"status": "error", "message": "session_id 不能为空"})

        db = get_mongo_db()
        result = await AgentWorkshopService(db=db).analyze_gaps(clean_session_id)
        gap_report = result.get("gap_report") if isinstance(result, dict) else None
        return _json_response({
            "status": "ok",
            "session_id": clean_session_id,
            "spec_id": result.get("spec_id") if isinstance(result, dict) else "",
            "gap_report": gap_report,
            "summary": {
                "existing_tools": len(_read_mapping_or_attr(gap_report, "existing_tools", []) or []),
                "suggested_tools": len(_read_mapping_or_attr(gap_report, "suggested_tools", []) or []),
                "blocking_gaps": len(_read_mapping_or_attr(gap_report, "blocking_gaps", []) or []),
            },
        })
    except Exception as exc:
        logger.error("执行 Agent 工坊缺口分析失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"执行 Agent 工坊缺口分析失败: {exc}"})


@tool
@register_tool(
    tool_id="generate_agent_workshop_tooling_plan",
    name="生成 Agent 工坊工具需求草案",
    description="让 Nanobot 直接触发 Agent 工坊工具需求草案生成，并返回结构化工具计划。",
    category="assistant_ops",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    when_to_use="当缺口分析已经完成，下一步需要产出工具需求草案，且希望保持 Nanobot 为主导入口时使用。",
    when_not_to_use="不适合在 session_id 无效或缺口分析前置状态异常时调用。",
    returns="返回 JSON 字符串，包含 session_id、spec_id 与 tooling_plan。",
    example="generate_agent_workshop_tooling_plan(session_id='session_123')",
    related_tools=["analyze_agent_workshop_gaps", "build_agent_workshop_version"],
)
async def generate_agent_workshop_tooling_plan(
    session_id: Annotated[str, "Agent 工坊会话 ID"],
) -> str:
    """生成 Agent 工坊工具需求草案并返回结构化结果。"""
    try:
        clean_session_id = str(session_id or "").strip()
        if not clean_session_id:
            return _json_response({"status": "error", "message": "session_id 不能为空"})

        db = get_mongo_db()
        result = await AgentWorkshopService(db=db).generate_tooling_plan(clean_session_id)
        tooling_plan = result.get("tooling_plan") if isinstance(result, dict) else None
        missing_capabilities = []
        if isinstance(tooling_plan, dict):
            missing_capabilities = tooling_plan.get("missing_capabilities") or []
        else:
            missing_capabilities = getattr(tooling_plan, "missing_capabilities", []) or []

        return _json_response({
            "status": "ok",
            "session_id": clean_session_id,
            "spec_id": result.get("spec_id") if isinstance(result, dict) else "",
            "tooling_plan": tooling_plan,
            "summary": {
                "missing_capabilities": len(missing_capabilities),
            },
        })
    except Exception as exc:
        logger.error("生成 Agent 工坊工具需求草案失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"生成 Agent 工坊工具需求草案失败: {exc}"})


@tool
@register_tool(
    tool_id="build_agent_workshop_version",
    name="生成 Agent 工坊版本草案",
    description="让 Nanobot 直接触发 Agent 工坊版本草案生成，并返回生成后的版本信息。",
    category="assistant_ops",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    when_to_use="当规格、缺口与工具计划已经足够明确，希望继续由 Nanobot 生成版本草案时使用。",
    when_not_to_use="不适合在 session_id 缺失或规格尚未准备好时调用。",
    returns="返回 JSON 字符串，包含 session_id、spec_id 和 version。",
    example="build_agent_workshop_version(session_id='session_123')",
    related_tools=["analyze_agent_workshop_gaps", "generate_agent_workshop_tooling_plan"],
)
async def build_agent_workshop_version(
    session_id: Annotated[str, "Agent 工坊会话 ID"],
) -> str:
    """生成 Agent 工坊版本草案并返回结构化结果。"""
    try:
        clean_session_id = str(session_id or "").strip()
        if not clean_session_id:
            return _json_response({"status": "error", "message": "session_id 不能为空"})

        db = get_mongo_db()
        phase_context = await _resolve_workshop_session_phase_context(db, clean_session_id)
        if phase_context.get("guard_available") and not phase_context.get("exists"):
            return _json_response({"status": "error", "message": f"会话 {clean_session_id} 不存在"})

        version_status = str(phase_context.get("version_status") or "").strip().lower()
        feasibility_status = str(phase_context.get("feasibility_status") or "").strip().lower()
        completeness_score = float(phase_context.get("completeness_score") or 0)
        if phase_context.get("guard_available") and (feasibility_status != "feasible" or completeness_score < 0.75):
            return _build_phase_guard_blocked_response(
                tool_name="build_agent_workshop_version",
                blocked_code="phase_not_ready",
                message=(
                    f"当前阶段为{phase_context.get('phase_label')}，不能直接补建测试版本；"
                    "请先完成需求澄清并让会话进入可执行状态。"
                ),
                next_action="先补齐待确认点、目标边界、输出格式和验收方式。",
                phase_context=phase_context,
                target_fields={
                    "session_id": clean_session_id,
                    "spec_id": phase_context.get("spec_id"),
                },
            )
        if phase_context.get("guard_available") and version_status and version_status != "draft":
            next_action = "当前已有测试流程在推进，请直接继续真数据测试或发布。"
            if version_status == "active":
                next_action = "当前版本已发布，如需继续优化，请先开始下一轮。"
            return _build_phase_guard_blocked_response(
                tool_name="build_agent_workshop_version",
                blocked_code="active_version_requires_iteration" if version_status == "active" else "version_already_in_progress",
                message=(
                    f"当前阶段为{phase_context.get('phase_label')}，不能再次补建测试版本；"
                    "当前会话已经有可继续推进的版本。"
                ),
                next_action=next_action,
                phase_context=phase_context,
                target_fields={
                    "session_id": clean_session_id,
                    "spec_id": phase_context.get("spec_id"),
                    "current_version_id": phase_context.get("current_version_id"),
                },
            )

        result = await AgentWorkshopService(db=db).build_version(clean_session_id)
        version = result.get("version") if isinstance(result, dict) else None
        return _json_response({
            "status": "ok",
            "session_id": clean_session_id,
            "spec_id": result.get("spec_id") if isinstance(result, dict) else "",
            "version": version,
            "summary": {
                "version_id": _read_mapping_or_attr(version, "version_id", None) if version is not None else None,
                "required_tools": len(_read_mapping_or_attr(version, "required_tools", []) or []) if version is not None else 0,
                "required_capabilities": len(_read_mapping_or_attr(version, "required_capabilities", []) or []) if version is not None else 0,
            },
        })
    except Exception as exc:
        logger.error("生成 Agent 工坊版本草案失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"生成 Agent 工坊版本草案失败: {exc}"})


@tool
@register_tool(
    tool_id="debug_agent_workshop_version",
    name="调试 Agent 工坊版本",
    description="让 Nanobot 对指定 Agent 工坊版本执行一次真实股票样例运行，并返回调试结果；该工具不会自动写入正式评估记录。",
    category="assistant_ops",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    when_to_use="当用户明确要做调试排障、查看最近一次样例输出、诊断 Prompt 或运行时问题时使用。",
    when_not_to_use="不适合替代正式真数据测试、验收、评估落库、发布前确认，或回答为什么版本仍处于 testing。",
    returns="返回 JSON 字符串，包含 version_id、spec_id、report、raw_result 和运行元数据，但不会自动生成 evaluation 记录。",
    example="debug_agent_workshop_version(version_id='spec_x_v1', stock_symbol='600519')",
    related_tools=["run_agent_workshop_real_data_test", "publish_agent_workshop_version"],
)
async def debug_agent_workshop_version(
    version_id: Annotated[str, "Agent 工坊版本 ID"],
    stock_symbol: Annotated[str, "真实股票代码，如 600519"],
    market_type: Annotated[str, "市场类型，默认 A股"] = "A股",
    analysis_date: Annotated[str, "分析日期，格式 YYYY-MM-DD，可为空"] = "",
    user_goal: Annotated[str, "本次测试目标，可为空"] = "",
    prompt_overrides_json: Annotated[str, "Prompt 覆盖 JSON 对象，可为空"] = "",
) -> str:
    """Run a single real-stock debug execution for one workshop version."""
    stage_events: list[dict[str, str]] = []
    try:
        clean_version_id = str(version_id or "").strip()
        clean_symbol = str(stock_symbol or "").strip()
        if not clean_version_id:
            return _json_response({"status": "error", "message": "version_id 不能为空"})
        if not clean_symbol:
            return _json_response({"status": "error", "message": "stock_symbol 不能为空"})

        prompt_overrides = _parse_optional_json_object(prompt_overrides_json, "prompt_overrides_json")

        db = get_mongo_db()
        phase_context = await _resolve_workshop_version_phase_context(db, clean_version_id)
        if phase_context.get("guard_available") and not phase_context.get("exists"):
            return _json_response({"status": "error", "message": f"版本 {clean_version_id} 不存在"})
        if phase_context.get("guard_available"):
            version_status = str(phase_context.get("version_status") or "").strip().lower()
            current_phase = str(phase_context.get("phase") or "").strip().lower()
            allowed_phases = {"testing", "evaluation", "publish-ready"}
            if current_phase not in allowed_phases:
                next_action = "请先让版本进入 testing，再执行调试。"
                blocked_code = "version_not_testing"
                if version_status == "active":
                    blocked_code = "active_version_requires_iteration"
                    next_action = "当前版本已经发布；如需继续优化，请开始下一轮。"
                elif version_status == "archived":
                    blocked_code = "archived_version_blocked"
                    next_action = "已归档版本不能继续调试，请切换到当前 testing 版本。"
                return _build_phase_guard_blocked_response(
                    tool_name="debug_agent_workshop_version",
                    blocked_code=blocked_code,
                    message=(
                        f"当前阶段为{phase_context.get('phase_label')}，不能直接执行调试；"
                        "只有 testing / evaluation / publish-ready 阶段的版本才允许进入调试链路。"
                    ),
                    next_action=next_action,
                    phase_context=phase_context,
                    target_fields={
                        "version_id": clean_version_id,
                        "spec_id": phase_context.get("spec_id"),
                    },
                )

        llm_payload = await _resolve_workshop_test_llm_payload(
            db=db,
        )
        stage_events.append(_build_tool_stage_event(
            "debug_agent_workshop_version.resolve_default_llm",
            "ok",
            f"已解析系统默认推理模型: {llm_payload.get('provider')}/{llm_payload.get('model')}",
        ))
        result = await AgentWorkshopService(db=db).debug_version(
            version_id=clean_version_id,
            llm=llm_payload,
            stock={
                "symbol": clean_symbol,
                "market_type": str(market_type or "A股").strip() or "A股",
                "analysis_date": str(analysis_date or "").strip() or None,
            },
            user_goal=str(user_goal or "").strip(),
            prompt_overrides=prompt_overrides,
        )
        return _json_response({
            "status": "ok",
            **result,
            "summary": {
            "_tool_events": [
                *stage_events,
                _build_tool_stage_event(
                    "debug_agent_workshop_version.debug_version",
                    "ok",
                    f"调试完成: symbol={result.get('symbol') or clean_symbol}, report_length={result.get('report_length')}",
                ),
                _build_tool_stage_event(
                    "debug_agent_workshop_version",
                    "ok",
                    "样例调试已完成",
                ),
            ],
                "version_id": result.get("version_id"),
                "spec_id": result.get("spec_id"),
                "symbol": result.get("symbol"),
                "analysis_date": result.get("analysis_date"),
                "report_length": result.get("report_length"),
            },
        })
    except Exception as exc:
        logger.error("调试 Agent 工坊版本失败: %s", exc, exc_info=True)
        return _json_response({
            "status": "error",
            "message": f"调试 Agent 工坊版本失败: {exc}",
            "failed_stage": "debug_agent_workshop_version",
            "_tool_events": [
                *stage_events,
                _build_tool_stage_event(
                    "debug_agent_workshop_version",
                    "error",
                    f"调试失败: {exc}",
                ),
            ],
        })


@tool
@register_tool(
    tool_id="run_agent_workshop_real_data_test",
    name="执行 Agent 工坊真数据测试",
    description="让 Nanobot 对指定 Agent 工坊版本执行一次真实股票样例测试，并自动记录评估结果到 Agent Workshop。",
    category="assistant_ops",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    when_to_use="当用户要执行真数据测试、正式验收、验证是否通过、查看评估结果、确认发布前 readiness，或排查为什么版本仍停留在 testing 时使用。",
    when_not_to_use="不适合只做样式预览、只讨论方案、只想单步调试 Prompt，或还没有 version_id 时调用。",
    returns="返回 JSON 字符串，包含 debug_result、evaluation、latest_decision 和是否已完成正式落库。",
    example="run_agent_workshop_real_data_test(version_id='spec_x_v1', stock_symbol='600519')",
    related_tools=["debug_agent_workshop_version", "publish_agent_workshop_version"],
)
async def run_agent_workshop_real_data_test(
    version_id: Annotated[str, "Agent 工坊版本 ID"],
    stock_symbol: Annotated[str, "真实股票代码，如 600519"],
    market_type: Annotated[str, "市场类型，默认 A股"] = "A股",
    analysis_date: Annotated[str, "分析日期，格式 YYYY-MM-DD，可为空"] = "",
    user_goal: Annotated[str, "本次测试目标，可为空"] = "",
    user_feedback: Annotated[str, "本次测试补充反馈，可为空"] = "",
    prompt_overrides_json: Annotated[str, "Prompt 覆盖 JSON 对象，可为空"] = "",
) -> str:
    """Execute the official real-data test loop and persist its evaluation."""
    stage_events: list[dict[str, str]] = []
    try:
        clean_version_id = str(version_id or "").strip()
        clean_symbol = str(stock_symbol or "").strip()
        if not clean_version_id:
            return _json_response({"status": "error", "message": "version_id 不能为空"})
        if not clean_symbol:
            return _json_response({"status": "error", "message": "stock_symbol 不能为空"})

        prompt_overrides = _parse_optional_json_object(prompt_overrides_json, "prompt_overrides_json")
        db = get_mongo_db()
        phase_context = await _resolve_workshop_version_phase_context(db, clean_version_id)
        if phase_context.get("guard_available") and not phase_context.get("exists"):
            return _json_response({"status": "error", "message": f"版本 {clean_version_id} 不存在"})
        if phase_context.get("guard_available") and str(phase_context.get("version_status") or "").strip().lower() != "testing":
            next_action = "请先补建测试版本。"
            if phase_context.get("version_status") == "active":
                next_action = "当前版本已发布；如需继续优化，请先开始下一轮。"
            elif phase_context.get("version_status") == "archived":
                next_action = "请切换到当前 testing 版本，或重新开始新一轮生成。"
            return _build_phase_guard_blocked_response(
                tool_name="run_agent_workshop_real_data_test",
                blocked_code=(
                    "active_version_requires_iteration"
                    if phase_context.get("version_status") == "active"
                    else "archived_version_blocked"
                    if phase_context.get("version_status") == "archived"
                    else "version_not_testing"
                ),
                message=(
                    f"当前阶段为{phase_context.get('phase_label')}，不能直接执行真数据测试；"
                    "只有 testing 版本才能进入正式测试链路。"
                ),
                next_action=next_action,
                phase_context=phase_context,
                target_fields={
                    "version_id": clean_version_id,
                    "spec_id": phase_context.get("spec_id"),
                },
            )

        service = AgentWorkshopService(db=db)
        llm_payload = await _resolve_workshop_test_llm_payload(
            db=db,
        )
        stage_events.append(_build_tool_stage_event(
            "run_agent_workshop_real_data_test.resolve_default_llm",
            "ok",
            f"已解析系统默认推理模型: {llm_payload.get('provider')}/{llm_payload.get('model')}",
        ))
        debug_result = await service.debug_version(
            version_id=clean_version_id,
            llm=llm_payload,
            stock={
                "symbol": clean_symbol,
                "market_type": str(market_type or "A股").strip() or "A股",
                "analysis_date": str(analysis_date or "").strip() or None,
            },
            user_goal=str(user_goal or "").strip(),
            prompt_overrides=prompt_overrides,
        )
        stage_events.append(_build_tool_stage_event(
            "run_agent_workshop_real_data_test.debug_version",
            "ok",
            f"样例运行完成: symbol={debug_result.get('symbol') or clean_symbol}, report_length={debug_result.get('report_length')}",
        ))

        debug_prompt = debug_result.get("debug_prompt") if isinstance(debug_result.get("debug_prompt"), dict) else {}
        raw_result = debug_result.get("raw_result") if isinstance(debug_result.get("raw_result"), dict) else {}
        runtime_result_payload = _with_nanobot_review_worker_flags({
            "user_goal": str(user_goal or "").strip(),
            "report": debug_result.get("report") or "",
            "raw_result": raw_result,
            "debug_prompt": debug_prompt,
            "template": debug_result.get("template") or {},
            "metadata": debug_result.get("metadata") or {},
            "symbol": debug_result.get("symbol") or clean_symbol,
            "analysis_date": debug_result.get("analysis_date") or str(analysis_date or "").strip(),
            "output_text": debug_prompt.get("llm_final_response") or debug_result.get("report") or "",
            "output_payload": raw_result,
            "tool_trace": debug_prompt.get("tool_trace") or raw_result.get("tool_trace") or [],
        })

        evaluation_result = await service.evaluate_version(
            clean_version_id,
            evaluation_type="production-review",
            user_feedback=str(user_feedback or "").strip(),
            runtime_result=runtime_result_payload,
        )
        evaluation = evaluation_result.get("evaluation") if isinstance(evaluation_result, dict) else None
        evaluation_decision = _read_mapping_or_attr(evaluation, "decision", None)
        acceptance_passed = evaluation_decision == "pass"
        stage_events.append(_build_tool_stage_event(
            "run_agent_workshop_real_data_test.evaluate_version",
            "ok",
            f"评估已记录: decision={evaluation_decision or 'unknown'}, overall={_read_mapping_or_attr(_read_mapping_or_attr(evaluation, 'scores', {}), 'overall', None)}",
        ))
        return _json_response({
            "status": "ok",
            "test_chain_status": "ok",
            "official_acceptance_decision": evaluation_decision,
            "official_acceptance_passed": acceptance_passed,
            "version_id": clean_version_id,
            "spec_id": debug_result.get("spec_id"),
            "debug_result": debug_result,
            "evaluation": evaluation,
            "_tool_events": [
                *stage_events,
                _build_tool_stage_event(
                    "run_agent_workshop_real_data_test",
                    "ok",
                    "真数据测试与评估落库已完成",
                ),
            ],
            "summary": {
                "symbol": debug_result.get("symbol"),
                "analysis_date": debug_result.get("analysis_date"),
                "report_length": debug_result.get("report_length"),
                "decision": evaluation_decision,
                "overall_score": _read_mapping_or_attr(_read_mapping_or_attr(evaluation, "scores", {}), "overall", None),
                "recorded_in_workshop": bool(_read_mapping_or_attr(evaluation, "evaluation_id", None)),
                "official_acceptance_passed": acceptance_passed,
            },
            "message": (
                "真数据测试链路已执行并完成评估落库；最新官方验收结论为 pass，版本现已进入待确认发布状态，必须由用户手动确认后才能正式发布。"
                if acceptance_passed
                else f"真数据测试链路已执行并完成评估落库；但最新官方验收结论为 {evaluation_decision or 'unknown'}，当前不能视为通过。"
            ),
        })
    except Exception as exc:
        logger.error("执行 Agent 工坊真数据测试失败: %s", exc, exc_info=True)
        failed_stage = "run_agent_workshop_real_data_test.evaluate_version" if any(event.get("name") == "run_agent_workshop_real_data_test.debug_version" for event in stage_events) else "run_agent_workshop_real_data_test.debug_version"
        return _json_response({
            "status": "error",
            "message": f"执行 Agent 工坊真数据测试失败: {exc}",
            "failed_stage": failed_stage,
            "_tool_events": [
                *stage_events,
                _build_tool_stage_event(
                    failed_stage,
                    "error",
                    str(exc),
                ),
                _build_tool_stage_event(
                    "run_agent_workshop_real_data_test",
                    "error",
                    f"真数据测试失败，失败阶段={failed_stage}",
                ),
            ],
        })


@tool
@register_tool(
    tool_id="publish_agent_workshop_version",
    name="发布 Agent 工坊版本",
    description="在用户已经手动确认发布后，让 Nanobot 将已通过最新真数据测试评估的 Agent 工坊版本发布为 active。",
    category="assistant_ops",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    when_to_use="仅当版本已经在 testing 且最新评估结论为 pass，并且用户在当前回合明确确认要发布时使用。",
    when_not_to_use="不适合在尚未完成真数据测试评估、评估未通过，或只是测试刚通过但用户尚未明确确认发布时调用。",
    returns="返回 JSON 字符串，包含发布后的版本状态与 spec_id。",
    example="publish_agent_workshop_version(version_id='spec_x_v1')",
    related_tools=["run_agent_workshop_real_data_test", "debug_agent_workshop_version"],
)
async def publish_agent_workshop_version(
    version_id: Annotated[str, "Agent 工坊版本 ID"],
) -> str:
    """Publish a workshop version after its latest evaluation has passed."""
    try:
        clean_version_id = str(version_id or "").strip()
        if not clean_version_id:
            return _json_response({"status": "error", "message": "version_id 不能为空"})

        db = get_mongo_db()
        phase_context = await _resolve_workshop_version_phase_context(db, clean_version_id)
        if phase_context.get("guard_available") and not phase_context.get("exists"):
            return _json_response({"status": "error", "message": f"版本 {clean_version_id} 不存在"})
        if phase_context.get("guard_available") and str(phase_context.get("version_status") or "").strip().lower() != "testing":
            next_action = "请先让版本进入 testing，再执行真数据测试。"
            if phase_context.get("version_status") == "active":
                next_action = "当前版本已经发布；如需继续优化，请开始下一轮。"
            elif phase_context.get("version_status") == "archived":
                next_action = "已归档版本不能直接发布，请切换到当前 testing 版本。"
            return _build_phase_guard_blocked_response(
                tool_name="publish_agent_workshop_version",
                blocked_code=(
                    "active_version_requires_iteration"
                    if phase_context.get("version_status") == "active"
                    else "archived_version_blocked"
                    if phase_context.get("version_status") == "archived"
                    else "version_not_testing"
                ),
                message=(
                    f"当前阶段为{phase_context.get('phase_label')}，不能直接发布正式版本；"
                    "只有 testing 版本才允许发布。"
                ),
                next_action=next_action,
                phase_context=phase_context,
                target_fields={
                    "version_id": clean_version_id,
                    "spec_id": phase_context.get("spec_id"),
                },
            )
        if phase_context.get("guard_available") and str(phase_context.get("latest_evaluation_decision") or "").strip().lower() != "pass":
            return _build_phase_guard_blocked_response(
                tool_name="publish_agent_workshop_version",
                blocked_code="latest_evaluation_not_pass",
                message=(
                    f"当前阶段为{phase_context.get('phase_label')}，不能直接发布正式版本；"
                    "只有最新一次真数据测试评估为 pass 的 testing 版本才能发布。"
                ),
                next_action="先完成最新一次真数据测试，确认官方验收结论为 pass。",
                phase_context=phase_context,
                target_fields={
                    "version_id": clean_version_id,
                    "spec_id": phase_context.get("spec_id"),
                },
            )

        result = await AgentWorkshopService(db=db).publish_version(clean_version_id)
        payload = dict(result or {})
        version_status = payload.pop("status", None)
        return _json_response({
            "status": "ok",
            **payload,
            "version_status": version_status,
        })
    except Exception as exc:
        logger.error("发布 Agent 工坊版本失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"发布 Agent 工坊版本失败: {exc}"})


@tool
@register_tool(
    tool_id="evaluate_agent_workshop_version",
    name="评估 Agent 工坊版本",
    description="让 Nanobot 对指定 Agent 工坊版本执行一次显式评估落库，并返回最新评估结果。",
    category="assistant_ops",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    when_to_use="当版本已经处于 testing/evaluation 阶段，需要重新记录一次正式评估结论时使用。",
    when_not_to_use="不适合在 version_id 不存在、仍未进入 testing，或只是想看最近一次评估结果时调用。",
    returns="返回 JSON 字符串，包含 version_id、evaluation 和最新 decision 摘要。",
    example="evaluate_agent_workshop_version(version_id='spec_x_v1', evaluation_type='production-review', runtime_result_json='{\"output_text\":\"...\"}')",
    related_tools=["debug_agent_workshop_version", "run_agent_workshop_real_data_test", "iterate_agent_workshop_version"],
)
async def evaluate_agent_workshop_version(
    version_id: Annotated[str, "Agent 工坊版本 ID"],
    evaluation_type: Annotated[str, "评估类型，默认 production-review"] = "production-review",
    sample_set_id: Annotated[str, "样本集 ID，可为空"] = "",
    user_feedback: Annotated[str, "评估补充反馈，可为空"] = "",
    benchmark_outputs_json: Annotated[str, "benchmark 输出数组 JSON，可为空"] = "",
    runtime_result_json: Annotated[str, "真实运行结果 JSON 对象，可为空"] = "",
) -> str:
    """Persist one explicit evaluation result for a workshop version."""
    try:
        clean_version_id = str(version_id or "").strip()
        if not clean_version_id:
            return _json_response({"status": "error", "message": "version_id 不能为空"})

        benchmark_outputs = _parse_optional_json_list(benchmark_outputs_json, "benchmark_outputs_json")
        runtime_result = _parse_optional_json_object(runtime_result_json, "runtime_result_json")

        db = get_mongo_db()
        phase_context = await _resolve_workshop_version_phase_context(db, clean_version_id)
        if phase_context.get("guard_available") and not phase_context.get("exists"):
            return _json_response({"status": "error", "message": f"版本 {clean_version_id} 不存在"})
        if phase_context.get("guard_available"):
            version_status = str(phase_context.get("version_status") or "").strip().lower()
            current_phase = str(phase_context.get("phase") or "").strip().lower()
            allowed_phases = {"testing", "evaluation", "publish-ready"}
            if current_phase not in allowed_phases:
                next_action = "请先让版本进入 testing，再执行正式评估。"
                blocked_code = "version_not_testing"
                if version_status == "active":
                    blocked_code = "active_version_requires_iteration"
                    next_action = "当前版本已经发布；如需继续优化，请开始下一轮。"
                elif version_status == "archived":
                    blocked_code = "archived_version_blocked"
                    next_action = "已归档版本不能继续评估，请切换到当前 testing 版本。"
                return _build_phase_guard_blocked_response(
                    tool_name="evaluate_agent_workshop_version",
                    blocked_code=blocked_code,
                    message=(
                        f"当前阶段为{phase_context.get('phase_label')}，不能直接执行正式评估；"
                        "只有 testing / evaluation / publish-ready 阶段的版本才允许进入评估链路。"
                    ),
                    next_action=next_action,
                    phase_context=phase_context,
                    target_fields={
                        "version_id": clean_version_id,
                        "spec_id": phase_context.get("spec_id"),
                    },
                )

        normalized_evaluation_type = str(evaluation_type or "production-review").strip() or "production-review"
        normalized_runtime_result = runtime_result or None
        if normalized_evaluation_type == "production-review" and normalized_runtime_result is not None:
            if not _has_workshop_runtime_evidence(normalized_runtime_result):
                return _json_response({
                    "status": "error",
                    "message": (
                        "production-review 提供了 runtime_result_json，但其中缺少可用证据；"
                        "至少需要 output_text、report、output_payload、raw_result、debug_prompt 或 tool_trace 之一"
                    ),
                })
            normalized_runtime_result = _with_nanobot_review_worker_flags(normalized_runtime_result)

        result = await AgentWorkshopService(db=db).evaluate_version(
            clean_version_id,
            evaluation_type=normalized_evaluation_type,
            sample_set_id=str(sample_set_id or "").strip() or None,
            user_feedback=str(user_feedback or "").strip(),
            benchmark_outputs=benchmark_outputs,
            runtime_result=normalized_runtime_result,
        )
        evaluation = result.get("evaluation") if isinstance(result, dict) else None
        decision = _read_mapping_or_attr(evaluation, "decision", None)
        return _json_response({
            "status": "ok",
            **(result or {}),
            "_tool_events": [
                _build_tool_stage_event(
                    "evaluate_agent_workshop_version.evaluate_version",
                    "ok",
                    f"评估已落库: decision={decision or 'unknown'}",
                ),
                _build_tool_stage_event(
                    "evaluate_agent_workshop_version",
                    "ok",
                    "版本评估已完成",
                ),
            ],
            "summary": {
                "version_id": clean_version_id,
                "spec_id": _read_mapping_or_attr(evaluation, "spec_id", None) or phase_context.get("spec_id"),
                "evaluation_id": _read_mapping_or_attr(evaluation, "evaluation_id", None),
                "evaluation_type": _read_mapping_or_attr(evaluation, "evaluation_type", None),
                "decision": decision,
                "overall_score": _read_mapping_or_attr(_read_mapping_or_attr(evaluation, "scores", {}), "overall", None),
                "recorded_in_workshop": bool(_read_mapping_or_attr(evaluation, "evaluation_id", None)),
            },
            "message": f"已完成版本评估落库；最新结论为 {decision or 'unknown'}。",
        })
    except Exception as exc:
        logger.error("评估 Agent 工坊版本失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"评估 Agent 工坊版本失败: {exc}"})


@tool
@register_tool(
    tool_id="iterate_agent_workshop_version",
    name="发起 Agent 工坊下一轮迭代",
    description="让 Nanobot 基于指定 Agent 工坊版本发起下一轮迭代，并创建新的 Session。",
    category="assistant_ops",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    when_to_use="当版本已经进入 evaluation / publish-ready / published，需要基于已有结论开始下一轮时使用。",
    when_not_to_use="不适合在还没完成测试评估或仍处于 generation/testing 初期时调用。",
    returns="返回 JSON 字符串，包含 source_version_id、session_id、spec_id 和 ai_message。",
    example="iterate_agent_workshop_version(version_id='spec_x_v1', feedback='补充解释评分波动来源')",
    related_tools=["evaluate_agent_workshop_version", "build_agent_workshop_version", "publish_agent_workshop_version"],
)
async def iterate_agent_workshop_version(
    version_id: Annotated[str, "Agent 工坊版本 ID"],
    feedback: Annotated[str, "迭代反馈，可为空"] = "",
) -> str:
    """Start the next workshop iteration from an evaluated or published version."""
    try:
        clean_version_id = str(version_id or "").strip()
        if not clean_version_id:
            return _json_response({"status": "error", "message": "version_id 不能为空"})

        db = get_mongo_db()
        phase_context = await _resolve_workshop_version_phase_context(db, clean_version_id)
        if phase_context.get("guard_available") and not phase_context.get("exists"):
            return _json_response({"status": "error", "message": f"版本 {clean_version_id} 不存在"})
        if phase_context.get("guard_available"):
            version_status = str(phase_context.get("version_status") or "").strip().lower()
            current_phase = str(phase_context.get("phase") or "").strip().lower()
            allowed_phases = {"evaluation", "publish-ready", "published"}
            if current_phase not in allowed_phases:
                blocked_code = "phase_not_ready"
                next_action = "请先完成至少一轮正式评估，再决定是否开始下一轮。"
                if version_status == "archived":
                    blocked_code = "archived_version_blocked"
                    next_action = "已归档版本不能作为当前迭代起点，请切换到最新版本。"
                return _build_phase_guard_blocked_response(
                    tool_name="iterate_agent_workshop_version",
                    blocked_code=blocked_code,
                    message=(
                        f"当前阶段为{phase_context.get('phase_label')}，不能直接开始下一轮；"
                        "只有 evaluation / publish-ready / published 阶段的版本才允许发起 iterate。"
                    ),
                    next_action=next_action,
                    phase_context=phase_context,
                    target_fields={
                        "version_id": clean_version_id,
                        "spec_id": phase_context.get("spec_id"),
                    },
                )

        result = await AgentWorkshopService(db=db).iterate_version(
            clean_version_id,
            feedback=str(feedback or "").strip(),
        )
        return _json_response({
            "status": "ok",
            **(result or {}),
            "_tool_events": [
                _build_tool_stage_event(
                    "iterate_agent_workshop_version.iterate_version",
                    "ok",
                    f"已创建下一轮 Session: {result.get('session_id') or ''}；Draft 版本: {result.get('version_id') or ''}",
                ),
                _build_tool_stage_event(
                    "iterate_agent_workshop_version",
                    "ok",
                    "下一轮迭代已创建",
                ),
            ],
            "summary": {
                "source_version_id": result.get("source_version_id") or clean_version_id,
                "session_id": result.get("session_id"),
                "spec_id": result.get("spec_id") or phase_context.get("spec_id"),
                "version_id": result.get("version_id"),
                "version_status": result.get("version_status"),
                "feedback": str(feedback or "").strip(),
            },
        })
    except Exception as exc:
        logger.error("发起 Agent 工坊下一轮迭代失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"发起 Agent 工坊下一轮迭代失败: {exc}"})


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
            "prompt_contract": {
                "agent_type": "universal",
                "agent_name": clean_agent_id,
                "template_name": clean_template_name,
                "status": status,
                "workflow_id": None,
                "node_id": None,
                "must_match_universal_agent": True,
            },
        })
    except Exception as exc:
        logger.error("创建或更新 UniversalAgent 提示词模板失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"创建或更新 UniversalAgent 提示词模板失败: {exc}"})


@tool
@register_tool(
    tool_id="bind_agent_tools_and_validate_candidate",
    name="绑定 Agent 工具并校验候选",
    description="为候选 Agent 写入 tool_agent_bindings，并按真实运行时逻辑做一次干运行校验，确认配置式 Agent 已具备最小可运行条件；该校验不等于 Agent Workshop 正式测试验收。",
    category="assistant_ops",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    when_to_use="当 Nanobot 已写入 agent_configs 和提示词模板，准备绑定工具并确认候选 Agent 是否能被运行时正常创建时使用。",
    when_not_to_use="不适合用来搜索资源或生成提示词。",
    returns="返回 JSON 字符串，包含绑定后的工具列表、提示词模板存在性和干运行校验结果；结果仅代表运行时候选可实例化，不代表 Workshop 版本已生成或已通过正式验收。",
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
        existing_config = await agent_configs.find_one({"agent_id": clean_agent_id}) or {}
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
        persisted_config = await agent_configs.find_one({"agent_id": clean_agent_id}) or {
            **existing_config,
            "agent_id": clean_agent_id,
            "tools": resolved_tools,
            "default_tools": resolved_default_tools,
            "max_tool_calls": int(max_tool_calls),
        }
        workshop_sync = await _sync_linked_workshop_versions(
            db=db,
            agent_id=clean_agent_id,
            candidate_config=persisted_config,
            resolved_tools=resolved_tools,
            resolved_default_tools=resolved_default_tools,
            max_tool_calls=int(max_tool_calls),
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
            "workshop_sync": workshop_sync,
            "validation": validation,
        })
    except Exception as exc:
        logger.error("绑定 Agent 工具并校验候选失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"绑定 Agent 工具并校验候选失败: {exc}"})


@tool
@register_tool(
    tool_id="generate_confirmed_candidate_agent",
    name="确认后生成候选 Agent",
    description="在用户明确确认后，一次性完成配置写入、提示词模板写入、工具绑定和干运行校验；若已同步到 Agent Workshop Draft，则默认自动生成一个测试版本，便于直接进入真数据测试。",
    category="assistant_ops",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    when_to_use="当 Nanobot 已完成确认稿并拿到用户明确确认后，用一次调用生成候选 Agent。",
    when_not_to_use="未确认前不要调用；也不适合做资源侦察。",
    returns="返回 JSON 字符串，包含三步写入结果、最终干运行校验结果、可选的自动 version 生成结果，以及与 Agent Workshop 正式验收边界相关的治理提示。",
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
    workflow_stage: Annotated[str, "工作流阶段，默认 analyst"] = "analyst",
    report_label: Annotated[str, "报告展示标签，可为空"] = "",
    show_in_reports: Annotated[bool, "是否进入工作流报告列表，默认 true"] = True,
    execution_order: Annotated[int, "工作流展示/执行顺序，默认 50"] = 50,
    template_name: Annotated[str, "模板名称；为空时自动生成"] = "",
    default_tools: Annotated[str, "默认工具 ID，逗号分隔；为空则默认取 tool_ids 前两项"] = "",
    max_tool_calls: Annotated[int, "最大工具调用次数，默认 5"] = 5,
    category: Annotated[str, "Agent 分类，默认 analyst"] = "analyst",
    callable_surfaces: Annotated[str, "允许调用入口，逗号分隔，默认 assistant,workflow,agent"] = "assistant,workflow,agent",
    input_mode: Annotated[str, "输入模式，默认 standalone"] = "standalone",
    enabled: Annotated[bool, "是否启用，默认 true"] = True,
    status: Annotated[str, "模板状态，默认 active"] = "active",
    sync_to_workshop_draft: Annotated[bool, "是否同步创建 Agent 工坊 Draft，默认 true"] = True,
    auto_build_workshop_version: Annotated[bool, "若已同步到 Agent 工坊 Draft，是否自动生成一个可测试版本，默认 true"] = True,
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
                "workflow_stage": workflow_stage,
                "report_label": report_label,
                "show_in_reports": show_in_reports,
                "execution_order": execution_order,
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
            "workflow_stage": workflow_stage,
            "report_label": report_label,
            "show_in_reports": show_in_reports,
            "execution_order": int(execution_order),
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

        dry_run_validation = binding_result.get("validation") or {}
        if sync_to_workshop_draft and isinstance(workshop_result, dict) and workshop_result.get("spec_id"):
            agent_configs = _get_collection(db, "agent_configs")
            if agent_configs is not None:
                await agent_configs.update_one(
                    {"agent_id": clean_agent_id},
                    {
                        "$set": {
                            "metadata.source": "nanobot_generated",
                            "metadata.spec_id": workshop_result.get("spec_id"),
                            "metadata.session_id": workshop_result.get("session_id"),
                            "metadata.linked_agent_workshop": True,
                            "updated_at": _utc_now_iso(),
                        }
                    },
                    upsert=False,
                )

        workshop_version_result = None
        if auto_build_workshop_version and sync_to_workshop_draft and isinstance(workshop_result, dict):
            workshop_session_id = str(workshop_result.get("session_id") or "").strip()
            if workshop_session_id:
                workshop_version_result = await _auto_build_workshop_version_result(workshop_session_id)
                if workshop_version_result.get("status") != "ok":
                    return _json_response({"status": "error", "stage": "workshop_version", "result": workshop_version_result})
                built_version = workshop_version_result.get("version") or {}
                built_version_id = str(built_version.get("version_id") or "").strip()
                if built_version_id and agent_configs is not None:
                    await agent_configs.update_one(
                        {"agent_id": clean_agent_id},
                        {
                            "$set": {
                                "metadata.latest_workshop_version_id": built_version_id,
                                "updated_at": _utc_now_iso(),
                            }
                        },
                        upsert=False,
                    )

        workshop_governance = {
            "asset_layer": "agent_workshop" if sync_to_workshop_draft else "runtime_only",
            "spec_id": workshop_result.get("spec_id") if isinstance(workshop_result, dict) else None,
            "session_id": workshop_result.get("session_id") if isinstance(workshop_result, dict) else None,
            "spec_status": "draft" if sync_to_workshop_draft else "not_synced",
            "version_generated": bool((workshop_version_result or {}).get("version")),
            "version_id": ((workshop_version_result or {}).get("version") or {}).get("version_id"),
            "official_acceptance_status": "not_started",
            "acceptance_ready": False,
            "release_ready": False,
            "next_required_action": (
                "当前已自动生成 Agent Workshop 测试版本；下一步直接做真数据测试，并以最新评估结论决定是否可发布。"
                if (workshop_version_result or {}).get("version")
                else "下一步应先生成 Agent Workshop 测试版本，再做真数据测试；当前 dry-run 仅证明候选运行时配置可实例化。"
                if sync_to_workshop_draft
                else "当前只完成了运行时候选生成；如需 Agent Workshop 正式测试验收，请先同步到 Draft 并生成 version。"
            ),
        }

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
                "workshop_version": workshop_version_result,
            },
            "final_validation": dry_run_validation,
            "governance_boundary": {
                "runtime_candidate_validation": {
                    "agent_config_written": config_result.get("status") == "ok",
                    "prompt_template_written": prompt_result.get("status") == "ok",
                    "tool_bindings_written": binding_result.get("status") == "ok",
                    "dry_run_instantiated": bool(((dry_run_validation.get("dry_run") or {}).get("instantiated"))),
                },
                "workshop_governance": workshop_governance,
                "warnings": [
                    (
                        "Dry-run 只代表候选 Agent 可按运行时配置被实例化；当前已自动生成测试版本，但这仍不代表真数据测试已经通过。"
                        if workshop_governance["version_generated"]
                        else "Dry-run 只代表候选 Agent 可按运行时配置被实例化，不代表 Agent Workshop 已生成 version。"
                    ),
                    "即使已自动生成测试版本，也必须先完成记录在 Agent Workshop 中的样例真数据测试评估，并以最新评估结论作为发布依据。",
                ],
            },
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
    "analyze_agent_workshop_gaps",
    "generate_agent_workshop_tooling_plan",
    "build_agent_workshop_version",
    "debug_agent_workshop_version",
    "run_agent_workshop_real_data_test",
    "publish_agent_workshop_version",
    "evaluate_agent_workshop_version",
    "iterate_agent_workshop_version",
    "create_or_update_runtime_agent_config",
    "create_or_update_universal_agent_prompt_template",
    "bind_agent_tools_and_validate_candidate",
    "generate_confirmed_candidate_agent",
]