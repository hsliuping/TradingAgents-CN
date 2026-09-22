"""Nanobot 友好的 Agent 设计与资源侦察工具。"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
from datetime import datetime, timedelta
from typing import Annotated, Any

from langchain_core.tools import tool

from app.core.database import get_mongo_db
from app.core.database import get_mongo_db_sync
from app.models.capability_index import CapabilitySearchHit
try:
    from app.pro.models.agent_workshop import AgentSpec, AgentSpecIOField, AgentSpecStatus
    from app.pro.models.prompt_template import TemplateContent
    from app.pro.services.agent_workshop_service import AgentWorkshopService
except ImportError:  # 社区版无 Agent 工坊模块（manifest 剔除），本工具链在社区版停用
    AgentSpec = AgentSpecIOField = AgentSpecStatus = None  # type: ignore[assignment,misc]
    TemplateContent = None  # type: ignore[assignment,misc]
    AgentWorkshopService = None  # type: ignore[assignment,misc]
from core.agents.factory import AgentFactory
from core.config.binding_manager import BindingManager
from app.services.capability_index_service import CapabilityIndexService
from core.agents.registry import get_registry
from core.tools import get_tool_registry
from core.tools.base import register_tool
from core.tools.context import get_current_assistant_thread_context, get_current_assistant_thread_id, require_current_user_id

logger = logging.getLogger(__name__)

_DEFAULT_CALLABLE_SURFACES = ["assistant", "workflow", "agent"]
_GLOBAL_NO_TRADING_ADVICE_POLICY = (
    "全局铁律：所有 Agent 一律禁止输出任何交易建议、买卖/持有判断、仓位建议、"
    "目标价、止损止盈、建仓区间、择时结论和其他操作性指令；只能提供研究结论、"
    "关键依据、风险因素与情景分析。"
)
_GLOBAL_NUMERICAL_TOOL_POLICY = (
    "全局铁律：所有关键数值计算必须通过项目提供的工具或 Skill 完成，"
    "禁止 LLM 自行计算。包括但不限于 DCF 估值、相对估值指标、财务比率、"
    "评分、排序、权重、公允价格、目标价区间等任何精确数值。"
    "若缺少对应工具或 Skill，必须标记为 blocking gap 并补齐，"
    "不得以「LLM 自己算也可以」作为降级方案。"
)
_GLOBAL_DATA_SOURCE_POLICY = (
    "全局铁律：优先使用本系统提供的数据源（tushare、akshare、QMT 等）。"
    "Skill 中若使用非系统数据源（如直接爬取网页、第三方 API、自有数据接口等），"
    "必须在 data_source 字段和 Skill 描述中明确标注来源，"
    "方便用户判断数据可靠性和可追溯性。"
    "禁止在使用外部数据源时隐瞒或模糊数据来源。"
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


def _auto_update_intent(
    *,
    action: str = "",
    stage: str = "",
    spec_id: str = "",
    spec_name: str = "",
    intent_summary: str = "",
    active_subtask: str = "",
    next_action: str = "",
    evaluation_decision: str = "",
    evaluation_blockers: list[str] | None = None,
    evaluation_categories: list[str] | None = None,
    pending_options: list[dict[str, Any]] | None = None,
    pending_question: str = "",
    proposed_items: list[dict[str, Any]] | None = None,
    clear_pending_options: bool = False,
    task: dict[str, str] | None = None,
    linked_skill: dict[str, str] | None = None,
    conversation_summary: str = "",
) -> None:
    """自动更新当前线程的意图上下文（contextvar）。"""
    try:
        from core.embedded_nanobot.intent_context import (
            update_intent_context_in_thread,
            update_evaluation_evidence_in_thread,
        )
        update_intent_context_in_thread(
            action=action,
            stage=stage,
            spec_id=spec_id,
            spec_name=spec_name,
            intent_summary=intent_summary,
            active_subtask=active_subtask,
            next_action=next_action,
            pending_options=pending_options,
            pending_question=pending_question,
            proposed_items=proposed_items,
            clear_pending_options=clear_pending_options,
            task=task,
            linked_skill=linked_skill,
            conversation_summary=conversation_summary,
        )
        if evaluation_decision or evaluation_blockers or evaluation_categories:
            update_evaluation_evidence_in_thread(
                decision=evaluation_decision,
                blockers=evaluation_blockers,
                categories=evaluation_categories,
            )
    except Exception as exc:
        logger.debug("[IntentContext][AutoUpdate] skipped: %s", exc)


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


def _truncate_text(value: Any, max_chars: int = 1200) -> str:
    text = str(value or "").strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "..."


def _collect_gap_job_known_context(
    gaps: list[dict[str, Any]],
    *,
    exclude_gap_id: str = "",
    max_failures: int = 5,
    max_facts: int = 12,
) -> dict[str, list[str]]:
    """聚合同一个 GapJob 内已知失败摘要和已验证事实，供后续 gap 避坑。"""
    failures: list[str] = []
    facts: list[str] = []
    for gap in gaps or []:
        if not isinstance(gap, dict):
            continue
        gap_id = str(gap.get("gap_id") or "").strip()
        if exclude_gap_id and gap_id == exclude_gap_id:
            continue
        summary = str(gap.get("agentic_failure_summary") or gap.get("error") or "").strip()
        if summary:
            prefix = str(gap.get("description") or gap_id or "未知缺口").strip()
            failures.append(_truncate_text(f"{prefix}: {summary}", 1000))
        for item in list(gap.get("agentic_verified_facts") or []):
            if str(item or "").strip():
                facts.append(_truncate_text(item, 800))
    return {
        "known_failure_summaries": _dedupe_string_list(failures)[:max_failures],
        "known_verified_facts": _dedupe_string_list(facts)[:max_facts],
    }


def _extract_agentic_context_from_session_doc(session_doc: dict[str, Any]) -> dict[str, Any]:
    """从 skill_creation_sessions 中抽取 Agentic 失败经验。"""
    result = session_doc.get("pipeline_result") or {}
    metadata = result.get("final_metadata") if isinstance(result, dict) else {}
    if not isinstance(metadata, dict):
        metadata = {}
    facts = metadata.get("verified_facts") if isinstance(metadata.get("verified_facts"), list) else []
    trace = metadata.get("agentic_trace") if isinstance(metadata.get("agentic_trace"), list) else []
    failure_summary = ""
    if isinstance(result, dict):
        failure_summary = str(result.get("error") or "").strip()
    if not failure_summary:
        for item in reversed(trace):
            if isinstance(item, dict) and str(item.get("failure_summary") or "").strip():
                failure_summary = str(item.get("failure_summary") or "").strip()
                break
    if not failure_summary:
        failure_summary = str(session_doc.get("pipeline_message") or "").strip()
    return {
        "failure_summary": _truncate_text(failure_summary, 2000),
        "verified_facts": _dedupe_string_list([_truncate_text(item, 800) for item in facts])[:20],
        "agentic_trace": trace[-20:] if isinstance(trace, list) else [],
        "generation_engine": str(metadata.get("generation_engine") or ""),
    }


def _utc_now_iso() -> str:
    return datetime.utcnow().isoformat()


def _parse_json_tool_result(raw: str) -> dict[str, Any]:
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {"status": "error", "message": "工具返回不是 JSON 对象"}
    except Exception as exc:
        return {"status": "error", "message": f"工具返回无法解析为 JSON: {exc}", "raw": raw}


async def _create_skill_generation_service_with_system_llm(db: Any) -> Any:
    """创建 SkillGenerationService，按系统设置读取推理模型和编程模型配置。"""
    from app.services.skill_generation_service import SkillGenerationService
    from app.services.intelligent_assistant_service import get_coding_llm_config, get_reasoning_llm_config
    from core.llm import UnifiedLLMClient

    reasoning_config = None
    coding_config = None
    try:
        reasoning_config = await get_reasoning_llm_config(db)
    except Exception as exc:
        logger.debug("[SkillGeneration][LLMConfig] 读取推理模型配置失败，使用默认配置: %s", exc)
    try:
        coding_config = await get_coding_llm_config(db)
    except Exception as exc:
        logger.debug("[SkillGeneration][LLMConfig] 读取编程模型配置失败，使用默认配置: %s", exc)
    reasoning_client = UnifiedLLMClient.from_config(reasoning_config) if reasoning_config else None
    coding_client = UnifiedLLMClient.from_config(coding_config) if coding_config else None
    if coding_config:
        logger.info(
            "[SkillGeneration][LLMConfig] coding provider=%s model=%s base_url=%s",
            getattr(coding_config, "provider", ""),
            getattr(coding_config, "model", ""),
            getattr(coding_config, "base_url", ""),
        )
    try:
        return SkillGenerationService(
            db=db,
            reasoning_llm_client=reasoning_client,
            coding_llm_client=coding_client,
        )
    except TypeError:
        return SkillGenerationService(db=db)


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


def _json_compact_dump(obj: Any) -> str:
    """紧凑 JSON 序列化，仅用于日志调试。"""
    try:
        return json.dumps(obj, ensure_ascii=False, default=str, separators=(",", ":"))
    except Exception:
        return str(obj)[:500]


_EXTERNAL_DATA_RISK_KEYWORDS = (
    "akshare",
    "tushare",
    "yfinance",
    "wind",
    "同花顺",
    "网络",
    "联网",
    "实时",
    "api",
    "http",
    "third-party",
    "第三方",
    "外部数据",
    "爬取",
    "抓取",
)


def _contains_external_data_risk(text: str) -> bool:
    lower_text = str(text or "").strip().lower()
    if not lower_text:
        return False
    return any(keyword in lower_text for keyword in _EXTERNAL_DATA_RISK_KEYWORDS)


def _is_skill_source_type(source_type: str) -> bool:
    source = str(source_type or "").strip().lower()
    return source in {"skill", "external_skill"}


_GAP_RESOLUTION_JOB_COLLECTION = "agent_workshop_gap_resolution_jobs"
_GAP_JOB_ACTIVE_STATUSES = {"pending", "running", "partial_completed"}
_GAP_JOB_TERMINAL_STATUSES = {"completed", "failed", "timeout", "cancelled"}
_GAP_ITEM_TIMEOUT_SECONDS = 1800
_GAP_JOB_CLAIM_LEASE_SECONDS = 30
_GAP_AUTO_RETRY_MAX_ATTEMPTS = 3
_GAP_AUTO_RETRY_BASE_DELAY_SECONDS = 30
_GAP_AUTO_RETRY_MAX_DELAY_SECONDS = 600


def _build_gap_resolution_job_id(seed: str) -> str:
    now_token = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:8]
    return f"gap_job_{now_token}_{digest}"


def _build_gap_resolution_idempotency_key(session_id: str, gaps: list[str]) -> str:
    normalized = "|".join(_dedupe_string_list(gaps))
    payload = f"{session_id}::{normalized}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def _normalize_gap_capability_key(text: str) -> str:
    return "".join(ch for ch in str(text or "").strip().lower() if ch.isalnum())


async def _find_active_gap_skill_session(
    db: Any,
    *,
    agent_spec_id: str = "",
    workshop_session_id: str = "",
    gap_id: str = "",
    gap_description: str = "",
) -> dict[str, Any] | None:
    """查找同一 Agent/同一能力缺口已有的活跃 Skill 生成会话，避免重复生成。"""
    try:
        from app.services.skill_generation_service import SESSION_COLLECTION

        collection = _get_collection(db, SESSION_COLLECTION)
        if collection is None:
            return None

        active_statuses = ["gathering", "confirmed", "generating"]
        cursor = collection.find({
            "status": {"$in": active_statuses},
            "handoff_context.source": "agent_studio_gap",
        })
        docs = await cursor.to_list(length=200)

        clean_spec_id = str(agent_spec_id or "").strip()
        clean_session_id = str(workshop_session_id or "").strip()
        clean_gap_id = str(gap_id or "").strip()
        capability_key = _normalize_gap_capability_key(gap_description)

        for doc in docs:
            ctx = dict((doc or {}).get("handoff_context") or {})
            ctx_spec_id = str(ctx.get("source_spec_id") or ctx.get("spec_id") or "").strip()
            if clean_spec_id and ctx_spec_id and ctx_spec_id != clean_spec_id:
                continue
            ctx_workshop_session_id = str(ctx.get("workshop_session_id") or "").strip()
            if clean_session_id and ctx_workshop_session_id and ctx_workshop_session_id != clean_session_id:
                continue
            ctx_gap_id = str(ctx.get("gap_id") or "").strip()
            if clean_gap_id and ctx_gap_id and ctx_gap_id == clean_gap_id:
                return dict(doc or {})
            target_key = _normalize_gap_capability_key(str(ctx.get("target_capability") or ""))
            if capability_key and target_key and capability_key == target_key:
                return dict(doc or {})
        return None
    except Exception as exc:
        logger.debug("查找活跃 gap Skill 会话失败，忽略: %s", exc)
        return None


async def _resolve_single_gap_capability(
    *,
    db: Any,
    ws_service: Any,
    gap_description: str,
    gap_id: str,
    gap_index: int = 0,
    workshop_session_id: str = "",
    agent_spec_id: str = "",
    agent_name: str = "",
    agent_goal: str = "",
    user_id: str = "nanobot",
    allow_medium_similarity_autocreate: bool = False,
    related_gaps: list[str] | None = None,
    known_context: dict[str, list[str]] | None = None,
    handoff_intent: str = "auto_resolve_blocking_gap",
) -> dict[str, Any]:
    """统一处理单个 gap 的 builtin evidence、去重复用和 Skill 生成会话启动。"""
    clean_gap = str(gap_description or "").strip()
    result: dict[str, Any] = {
        "gap_index": gap_index,
        "gap_id": str(gap_id or f"gap_{gap_index + 1}").strip(),
        "gap_description": clean_gap,
        "status": "pending",
        "pipeline_stage": "",
        "pipeline_message": "",
        "dedup": {},
        "dedup_candidate": {},
        "skill_tool_id": None,
        "skill_display_name": None,
        "session_id": None,
        "error": None,
        "elapsed_seconds": 0,
    }

    if not clean_gap:
        result.update({"status": "failed", "error": "gap_description 不能为空"})
        return result

    try:
        builtin_evidence_fn = getattr(ws_service, "_builtin_tool_evidence_for_gap", None)
        builtin_evidence = builtin_evidence_fn(clean_gap) if callable(builtin_evidence_fn) else None
        if builtin_evidence is not None:
            result.update({
                "status": "reused_existing",
                "skill_tool_id": str(builtin_evidence.get("skill_tool_id") or ""),
                "skill_display_name": str(builtin_evidence.get("skill_display_name") or builtin_evidence.get("skill_tool_id") or ""),
                "pipeline_stage": "builtin_evidence",
                "pipeline_message": str(builtin_evidence.get("reason") or "命中已注册内置能力，直接复用"),
                "dedup": {
                    "source": "builtin_evidence",
                    "reason": builtin_evidence.get("reason"),
                    "additional_tool_ids": list(builtin_evidence.get("additional_tool_ids") or []),
                },
            })
            logger.info(
                "[GapResolver][builtin_evidence] reused_existing tool_id=%s gap=%s",
                result["skill_tool_id"],
                clean_gap,
            )
            return result

        dedup_hits = await CapabilityIndexService(db).search_capabilities(
            query=clean_gap,
            top_k=8,
            bindable_only=True,
            source_types=["builtin_tool", "skill", "external_skill"],
        )
        dedup_candidates: list[dict[str, Any]] = []
        for hit in dedup_hits:
            capability = hit.capability
            dedup_candidates.append({
                "capability_id": str(getattr(capability, "capability_id", "") or ""),
                "source_type": str(getattr(capability, "source_type", "") or ""),
                "registry_tool_id": str(getattr(capability, "registry_tool_id", "") or ""),
                "name": str(getattr(capability, "name", "") or ""),
                "display_name": str(getattr(capability, "display_name", "") or str(getattr(capability, "name", "") or "")),
                "description": str(getattr(capability, "description", "") or ""),
                "score": float(getattr(hit, "score", 0.0) or 0.0),
            })
        result["dedup"] = {
            "candidate_count": len(dedup_candidates),
            "top_candidates": dedup_candidates[:3],
        }

        high_match = next(
            (
                item for item in dedup_candidates
                if str(item.get("registry_tool_id") or "").strip()
                and (_is_skill_source_type(item.get("source_type")) or str(item.get("source_type") or "") == "builtin_tool")
                and float(item.get("score") or 0.0) >= 0.85
            ),
            None,
        )
        if high_match is not None:
            result.update({
                "status": "reused_existing",
                "pipeline_stage": "dedup_reuse",
                "pipeline_message": "命中高相似度已有可绑定能力，直接复用",
                "skill_tool_id": str(high_match.get("registry_tool_id") or ""),
                "skill_display_name": str(high_match.get("name") or high_match.get("display_name") or ""),
            })
            logger.info(
                "[GapResolver][dedup] reused_existing source_type=%s tool_id=%s score=%s gap=%s",
                high_match.get("source_type"),
                high_match.get("registry_tool_id"),
                high_match.get("score"),
                clean_gap,
            )
            return result

        medium_match = next(
            (
                item for item in dedup_candidates
                if str(item.get("registry_tool_id") or "").strip()
                and (_is_skill_source_type(item.get("source_type")) or str(item.get("source_type") or "") == "builtin_tool")
                and 0.6 <= float(item.get("score") or 0.0) < 0.85
            ),
            None,
        )
        if medium_match is not None and not allow_medium_similarity_autocreate:
            result.update({
                "status": "needs_dedup_confirmation",
                "pipeline_stage": "dedup_confirmation",
                "pipeline_message": "命中中等相似度候选 Skill，需用户确认是复用还是新建",
                "error": "needs_dedup_confirmation",
                "dedup_candidate": {
                    "name": str(medium_match.get("name") or medium_match.get("display_name") or ""),
                    "registry_tool_id": str(medium_match.get("registry_tool_id") or ""),
                    "score": round(float(medium_match.get("score") or 0.0), 2),
                    "description": str(medium_match.get("description") or ""),
                    "source_type": str(medium_match.get("source_type") or ""),
                },
            })
            return result

        existing_skill_session = await _find_active_gap_skill_session(
            db,
            agent_spec_id=agent_spec_id,
            workshop_session_id=workshop_session_id,
            gap_id=gap_id,
            gap_description=clean_gap,
        )
        if existing_skill_session is not None:
            skill_session_id = str(existing_skill_session.get("session_id") or "")
            result.update({
                "status": "generating",
                "pipeline_stage": str(existing_skill_session.get("pipeline_stage") or "generating"),
                "pipeline_message": "复用同一 Agent/同一能力缺口已有的 Skill 生成会话，避免重复生成",
                "session_id": skill_session_id,
                "skill_session_id": skill_session_id,
            })
            logger.info(
                "[GapResolver][ReuseSkillSession] gap_id=%s skill_session_id=%s skill_status=%s",
                gap_id,
                skill_session_id,
                existing_skill_session.get("status"),
            )
            return result

        context = dict(known_context or {})
        candidates_for_context = [str(item.get("name") or item.get("registry_tool_id") or "") for item in dedup_candidates[:5]]
        skill_service = await _create_skill_generation_service_with_system_llm(db=db)
        start_result = await skill_service.start_session(
            description=clean_gap,
            user_id=str(user_id or "nanobot").strip() or "nanobot",
            handoff_context={
                "source": "agent_studio_gap",
                "source_spec_id": agent_spec_id,
                "source_name": agent_name,
                "target_capability": clean_gap,
                "handoff_intent": handoff_intent,
                "user_id": str(user_id or "nanobot").strip() or "nanobot",
                "workshop_session_id": workshop_session_id,
                "spec_id": agent_spec_id,
                "gap_id": gap_id,
                "agent_name": agent_name,
                "agent_goal": agent_goal,
                "gap_context": f"{agent_name or 'Agent'} 为达成目标“{agent_goal or '未提供'}”缺少能力：{clean_gap}",
                "related_gaps": [str(item or "") for item in (related_gaps or []) if str(item or "").strip() and str(item or "").strip() != clean_gap][:8],
                "searched_capabilities": [f"CapabilityIndex 已搜索：{clean_gap}", *candidates_for_context],
                "confirmed_data_sources": [],
                "user_clarifications": [],
                "known_failure_summaries": context.get("known_failure_summaries") or [],
                "known_verified_facts": context.get("known_verified_facts") or [],
            },
        )
        skill_session_id = str((start_result or {}).get("session_id") or "").strip()
        if not skill_session_id:
            result.update({"status": "failed", "error": "启动 Skill 生成会话失败"})
            return result

        await skill_service.respond_to_session(skill_session_id, "确认按可复用能力来设计，这是一个可参数化、可绑定到 Agent 的工具。")
        preview = await skill_service.preview_spec(skill_session_id, "确认")
        if not preview:
            result.update({"status": "failed", "session_id": skill_session_id, "error": "预览 Skill 规格失败"})
            return result
        await skill_service.confirm_spec(skill_session_id, "确认生成")
        result.update({
            "status": "generating",
            "pipeline_stage": "generating",
            "pipeline_message": "Skill 生成已提交，等待完成",
            "session_id": skill_session_id,
            "skill_session_id": skill_session_id,
        })
        return result
    except Exception as exc:
        logger.error("[GapResolver] 处理 gap 异常: %s", exc, exc_info=True)
        result.update({"status": "failed", "error": str(exc)})
        return result


def _summarize_gap_job_gaps(gaps: list[dict[str, Any]]) -> dict[str, int]:
    summary: dict[str, int] = {
        "total": 0,
        "pending": 0,
        "running": 0,
        "completed": 0,
        "failed": 0,
        "timeout": 0,
        "cancelled": 0,
    }
    for item in gaps:
        summary["total"] += 1
        status = str((item or {}).get("status") or "").strip().lower()
        if status in summary:
            summary[status] += 1
    return summary


def _derive_gap_job_status(gaps: list[dict[str, Any]]) -> str:
    summary = _summarize_gap_job_gaps(gaps)
    total = int(summary.get("total") or 0)
    if total <= 0:
        return "completed"

    pending_or_running = int(summary.get("pending") or 0) + int(summary.get("running") or 0)
    if pending_or_running > 0:
        return "running"

    completed = int(summary.get("completed") or 0)
    failed = int(summary.get("failed") or 0) + int(summary.get("timeout") or 0)
    cancelled = int(summary.get("cancelled") or 0)

    if completed == total:
        return "completed"
    if cancelled == total:
        return "cancelled"
    if completed > 0 and (failed > 0 or cancelled > 0):
        return "partial_completed"
    if failed > 0 and completed <= 0:
        return "failed"
    return "failed"


def _derive_gap_execution_state(status: str) -> str:
    normalized = str(status or "").strip().lower()
    if normalized in {"pending", "running", "partial_completed"}:
        return "running"
    if normalized in {"completed", "failed", "timeout", "cancelled"}:
        return normalized
    return "queued"


def _iso_elapsed_seconds(started_at: str, now_utc: datetime | None = None) -> int:
    text = str(started_at or "").strip()
    if not text:
        return 0
    try:
        start = datetime.fromisoformat(text)
    except Exception:
        return 0
    now = now_utc or datetime.utcnow()
    return max(int((now - start).total_seconds()), 0)


def _is_claim_expired(expires_at: str, now_utc: datetime | None = None) -> bool:
    text = str(expires_at or "").strip()
    if not text:
        return True
    try:
        expires = datetime.fromisoformat(text)
    except Exception:
        return True
    now = now_utc or datetime.utcnow()
    return expires <= now


def _is_retry_due(next_retry_at: str, now_utc: datetime | None = None) -> bool:
    text = str(next_retry_at or "").strip()
    if not text:
        return True
    try:
        next_at = datetime.fromisoformat(text)
    except Exception:
        return True
    now = now_utc or datetime.utcnow()
    return next_at <= now


def _read_gap_retry_policy(job_doc: dict[str, Any]) -> dict[str, int]:
    execution = dict((job_doc or {}).get("execution") or {})
    policy = dict(execution.get("retry_policy") or {})

    max_attempts = int(policy.get("max_attempts") or _GAP_AUTO_RETRY_MAX_ATTEMPTS)
    base_delay_seconds = int(policy.get("base_delay_seconds") or _GAP_AUTO_RETRY_BASE_DELAY_SECONDS)
    max_delay_seconds = int(policy.get("max_delay_seconds") or _GAP_AUTO_RETRY_MAX_DELAY_SECONDS)

    return {
        "max_attempts": max(0, min(max_attempts, 10)),
        "base_delay_seconds": max(1, min(base_delay_seconds, 3600)),
        "max_delay_seconds": max(1, min(max_delay_seconds, 3600)),
    }


def _compute_retry_backoff_seconds(attempt: int, retry_policy: dict[str, int]) -> int:
    base = int(retry_policy.get("base_delay_seconds") or _GAP_AUTO_RETRY_BASE_DELAY_SECONDS)
    cap = int(retry_policy.get("max_delay_seconds") or _GAP_AUTO_RETRY_MAX_DELAY_SECONDS)
    step = max(0, int(attempt) - 1)
    delay = base * (2 ** step)
    return max(1, min(delay, cap))


def _apply_gap_retry_or_dead_letter(
    target_gap: dict[str, Any],
    *,
    reason_code: str,
    reason_message: str,
    terminal_status: str,
    now_utc: datetime,
    now_iso: str,
    retry_policy: dict[str, int],
) -> dict[str, Any]:
    max_attempts = int(retry_policy.get("max_attempts") or 0)
    current_retry = int(target_gap.get("auto_retry_count") or 0)

    if max_attempts > 0 and current_retry < max_attempts:
        next_retry = current_retry + 1
        delay_seconds = _compute_retry_backoff_seconds(next_retry, retry_policy)
        next_retry_at = (now_utc + timedelta(seconds=delay_seconds)).isoformat()

        target_gap["status"] = "pending"
        target_gap["pipeline_stage"] = "retry_backoff"
        target_gap["pipeline_message"] = (
            f"{reason_message}；将在 {delay_seconds}s 后自动重试（{next_retry}/{max_attempts}）"
        )
        target_gap["error"] = str(reason_code or "retryable_failure").strip() or "retryable_failure"
        target_gap["last_error"] = target_gap["error"]
        target_gap["last_error_message"] = str(reason_message or "").strip()
        target_gap["last_failure_at"] = now_iso
        target_gap["next_retry_at"] = next_retry_at
        target_gap["auto_retry_count"] = next_retry
        target_gap["dead_letter"] = {}
        return target_gap

    terminal = str(terminal_status or "failed").strip().lower() or "failed"
    if terminal not in {"failed", "timeout", "cancelled", "completed"}:
        terminal = "failed"
    target_gap["status"] = terminal
    target_gap["pipeline_stage"] = "dead_letter"
    target_gap["pipeline_message"] = (
        f"{reason_message}；已达自动重试上限（{max_attempts}），转入 dead-letter"
    )
    target_gap["error"] = str(reason_code or "dead_lettered").strip() or "dead_lettered"
    target_gap["last_error"] = target_gap["error"]
    target_gap["last_error_message"] = str(reason_message or "").strip()
    target_gap["last_failure_at"] = now_iso
    target_gap["next_retry_at"] = ""
    target_gap["dead_letter"] = {
        "reason_code": target_gap["error"],
        "reason_message": str(reason_message or "").strip(),
        "failed_at": now_iso,
        "auto_retry_count": int(target_gap.get("auto_retry_count") or 0),
        "max_attempts": max_attempts,
    }
    return target_gap


def _build_gap_job_claim_token(job_id: str, worker_id: str, now_iso: str) -> str:
    seed = f"{job_id}:{worker_id}:{now_iso}"
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()


async def _try_claim_gap_resolution_job(
    collection: Any,
    job_doc: dict[str, Any],
    worker_id: str,
    lease_seconds: int,
) -> dict[str, Any]:
    clean_job_id = str((job_doc or {}).get("job_id") or "").strip()
    if not clean_job_id:
        return {"claimed": False, "reason": "job_id_missing"}

    current_status = str((job_doc or {}).get("status") or "").strip().lower()
    if current_status not in _GAP_JOB_ACTIVE_STATUSES:
        return {"claimed": False, "reason": "job_not_active"}

    now_utc = datetime.utcnow()
    now_iso = now_utc.isoformat()
    lease = max(5, min(int(lease_seconds), 300))
    expires_iso = (now_utc + timedelta(seconds=lease)).isoformat()

    execution = dict((job_doc or {}).get("execution") or {})
    claim = dict(execution.get("claim") or {})
    owner = str(claim.get("owner") or "").strip()
    expires_at = str(claim.get("expires_at") or "").strip()
    if owner and owner != worker_id and not _is_claim_expired(expires_at, now_utc):
        return {"claimed": False, "reason": "already_claimed", "owner": owner}

    token = _build_gap_job_claim_token(clean_job_id, worker_id, now_iso)
    update_result = await collection.update_one(
        {
            "job_id": clean_job_id,
            "status": current_status,
            "updated_at": (job_doc or {}).get("updated_at"),
        },
        {
            "$set": {
                "execution.claim.owner": worker_id,
                "execution.claim.token": token,
                "execution.claim.claimed_at": now_iso,
                "execution.claim.heartbeat_at": now_iso,
                "execution.claim.expires_at": expires_iso,
                "execution.claim.lease_seconds": lease,
                "execution.last_worker_id": worker_id,
                "updated_at": now_iso,
            }
        },
    )

    modified_count = getattr(update_result, "modified_count", None)
    if modified_count is not None and int(modified_count) <= 0:
        return {"claimed": False, "reason": "claim_conflict"}

    return {
        "claimed": True,
        "owner": worker_id,
        "token": token,
        "claimed_at": now_iso,
        "expires_at": expires_iso,
    }


async def _release_gap_resolution_job_claim(
    collection: Any,
    job_id: str,
    worker_id: str,
    token: str,
) -> None:
    now_iso = _utc_now_iso()
    await collection.update_one(
        {
            "job_id": str(job_id or "").strip(),
            "execution.claim.owner": str(worker_id or "").strip(),
            "execution.claim.token": str(token or "").strip(),
        },
        {
            "$set": {
                "execution.claim.released_at": now_iso,
                "execution.claim.owner": "",
                "execution.claim.token": "",
                "execution.claim.expires_at": now_iso,
                "execution.claim.heartbeat_at": now_iso,
                "updated_at": now_iso,
            }
        },
    )


async def _process_single_gap_resolution_job(db: Any, job_doc: dict[str, Any]) -> dict[str, Any]:
    from app.services.skill_generation_service import SESSION_COLLECTION

    collection = _get_collection(db, _GAP_RESOLUTION_JOB_COLLECTION)
    if collection is None:
        return {"status": "error", "message": f"数据库中不可用集合: {_GAP_RESOLUTION_JOB_COLLECTION}"}

    clean_job_id = str((job_doc or {}).get("job_id") or "").strip()
    if not clean_job_id:
        return {"status": "error", "message": "job_id 为空"}

    now_iso = _utc_now_iso()
    now_utc = datetime.utcnow()
    job_status = str((job_doc or {}).get("status") or "").strip().lower()
    if job_status in _GAP_JOB_TERMINAL_STATUSES:
        return {"status": "ok", "job_id": clean_job_id, "processed": False, "message": "job 已在终态"}

    workshop_session_id = str((job_doc or {}).get("workshop_session_id") or "").strip()
    retry_policy = _read_gap_retry_policy(job_doc)
    mode = str((job_doc or {}).get("mode") or "manual_confirmed").strip().lower() or "manual_confirmed"
    allow_medium_similarity_autocreate = mode == "auto"

    logger.info(
        "[GapJob][ProcessJob] start job_id=%s session_id=%s mode=%s status=%s",
        clean_job_id,
        workshop_session_id or "-",
        mode,
        job_status,
    )

    ws_service = AgentWorkshopService(db=db)
    workshop_session = None
    if workshop_session_id:
        try:
            workshop_session = await ws_service._load_session(workshop_session_id)
        except Exception as exc:
            logger.debug("worker 读取 workshop session 失败，降级继续: session_id=%s err=%s", workshop_session_id, exc)
    agent_spec_id = str((job_doc or {}).get("spec_id") or "").strip()
    if not agent_spec_id and workshop_session is not None:
        agent_spec_id = str(getattr(workshop_session, "spec_id", "") or "").strip()

    agent_name = ""
    agent_goal = ""
    session_owner = str((job_doc or {}).get("user_id") or "").strip()
    if workshop_session is not None:
        snapshot = getattr(workshop_session, "current_spec_snapshot", None)
        if snapshot is not None:
            agent_name = str(getattr(snapshot, "name", "") or "").strip()
            agent_goal = str(getattr(snapshot, "primary_goal", "") or "").strip()
        if not session_owner:
            session_owner = str(getattr(workshop_session, "user_id", "") or "").strip()
    effective_user_id = session_owner or "nanobot"

    gaps: list[dict[str, Any]] = [dict(item or {}) for item in list((job_doc or {}).get("gaps") or [])]
    if not gaps:
        derived_status = "completed"
        await collection.update_one(
            {"job_id": clean_job_id},
            {
                "$set": {
                    "status": derived_status,
                    "execution.state": _derive_gap_execution_state(derived_status),
                    "updated_at": now_iso,
                }
            },
        )
        return {"status": "ok", "job_id": clean_job_id, "processed": False, "message": "job 无 gaps"}

    target_index = -1
    for idx, gap in enumerate(gaps):
        if str(gap.get("status") or "").strip().lower() == "pending":
            if not _is_retry_due(str(gap.get("next_retry_at") or ""), now_utc):
                continue
            target_index = idx
            break
    if target_index < 0:
        for idx, gap in enumerate(gaps):
            if str(gap.get("status") or "").strip().lower() == "running":
                target_index = idx
                break

    if target_index < 0:
        derived_status = _derive_gap_job_status(gaps)
        await collection.update_one(
            {"job_id": clean_job_id},
            {
                "$set": {
                    "status": derived_status,
                    "execution.state": _derive_gap_execution_state(derived_status),
                    "updated_at": now_iso,
                }
            },
        )
        return {"status": "ok", "job_id": clean_job_id, "processed": False, "message": "job 无可执行 gap"}

    target_gap = dict(gaps[target_index] or {})
    gap_id = str(target_gap.get("gap_id") or f"gap_{target_index + 1}").strip() or f"gap_{target_index + 1}"
    gap_desc = str(target_gap.get("description") or "").strip()
    gap_status = str(target_gap.get("status") or "").strip().lower()

    async def _persist_gap(target: dict[str, Any]) -> dict[str, Any]:
        target["gap_id"] = gap_id
        target["updated_at"] = now_iso
        gaps[target_index] = target
        derived = _derive_gap_job_status(gaps)
        logger.info(
            "[GapJob][PersistGap] job_id=%s gap_id=%s gap_status=%s stage=%s derived_job_status=%s skill_tool_id=%s",
            clean_job_id,
            gap_id,
            target.get("status"),
            target.get("pipeline_stage"),
            derived,
            target.get("skill_tool_id") or "-",
        )
        await collection.update_one(
            {"job_id": clean_job_id},
            {
                "$set": {
                    "gaps": gaps,
                    "status": derived,
                    "updated_at": now_iso,
                    "execution.state": _derive_gap_execution_state(derived),
                    "execution.last_gap_id": gap_id,
                    "execution.last_gap_status": str(target.get("status") or "").strip().lower(),
                    "execution.last_gap_message": str(target.get("pipeline_message") or "").strip(),
                }
            },
        )
        return {
            "status": "ok",
            "job_id": clean_job_id,
            "processed": True,
            "job_status": derived,
            "gap": target,
            "summary": _summarize_gap_job_gaps(gaps),
        }

    if gap_status == "pending":
        # 先切到 running，避免并发 worker 重复抢占
        target_gap["status"] = "running"
        target_gap["pipeline_stage"] = "planning"
        target_gap["pipeline_message"] = "worker 已接单，开始处理"
        target_gap.setdefault("retry_count", 0)
        target_gap.setdefault("auto_retry_count", 0)
        target_gap["next_retry_at"] = ""
        target_gap.setdefault("created_at", now_iso)
        target_gap.setdefault("started_at", now_iso)

        known_context = _collect_gap_job_known_context(gaps, exclude_gap_id=gap_id)
        logger.info(
            "[GapJob][KnownContext] job_id=%s gap_id=%s known_failures=%s known_facts=%s",
            clean_job_id,
            gap_id,
            len(known_context.get("known_failure_summaries") or []),
            len(known_context.get("known_verified_facts") or []),
        )
        resolution = await _resolve_single_gap_capability(
            db=db,
            ws_service=ws_service,
            gap_description=gap_desc,
            gap_id=gap_id,
            gap_index=0,
            workshop_session_id=workshop_session_id,
            agent_spec_id=agent_spec_id,
            agent_name=agent_name,
            agent_goal=agent_goal,
            user_id=effective_user_id,
            allow_medium_similarity_autocreate=allow_medium_similarity_autocreate,
            related_gaps=[str(item.get("description") or "") for item in gaps if isinstance(item, dict)],
            known_context=known_context,
            handoff_intent="async_gap_resolution_worker",
        )

        resolution_status = str(resolution.get("status") or "").strip().lower()
        target_gap["pipeline_stage"] = str(resolution.get("pipeline_stage") or target_gap.get("pipeline_stage") or "")
        target_gap["pipeline_message"] = str(resolution.get("pipeline_message") or target_gap.get("pipeline_message") or "")
        target_gap["skill_tool_id"] = str(resolution.get("skill_tool_id") or target_gap.get("skill_tool_id") or "")
        target_gap["skill_display_name"] = str(resolution.get("skill_display_name") or target_gap.get("skill_display_name") or "")
        target_gap["skill_session_id"] = str(resolution.get("skill_session_id") or resolution.get("session_id") or target_gap.get("skill_session_id") or "")
        target_gap["dedup"] = resolution.get("dedup") or target_gap.get("dedup") or {}
        if resolution.get("dedup_candidate"):
            target_gap["dedup_candidate"] = resolution.get("dedup_candidate")
        target_gap["elapsed_seconds"] = _iso_elapsed_seconds(str(target_gap.get("started_at") or now_iso), now_utc)

        if resolution_status == "reused_existing":
            target_gap["status"] = "completed"
            target_gap["error"] = None
            target_gap["next_retry_at"] = ""
            logger.info(
                "[GapJob][ResolvedExisting] job_id=%s gap_id=%s stage=%s tool_id=%s",
                clean_job_id,
                gap_id,
                target_gap.get("pipeline_stage"),
                target_gap.get("skill_tool_id") or "-",
            )
            return await _persist_gap(target_gap)

        if resolution_status == "needs_dedup_confirmation":
            target_gap["status"] = "failed"
            target_gap["error"] = "needs_dedup_confirmation"
            target_gap["next_retry_at"] = ""
            return await _persist_gap(target_gap)

        if resolution_status == "generating":
            target_gap["status"] = "running"
            target_gap["error"] = None
            target_gap["next_retry_at"] = ""
            return await _persist_gap(target_gap)

        target_gap = _apply_gap_retry_or_dead_letter(
            target_gap,
            reason_code=str(resolution.get("error") or "skill_resolution_failed"),
            reason_message=str(resolution.get("error") or "启动 Skill 生成会话失败"),
            terminal_status="failed",
            now_utc=now_utc,
            now_iso=now_iso,
            retry_policy=retry_policy,
        )
        target_gap["elapsed_seconds"] = _iso_elapsed_seconds(str(target_gap.get("started_at") or now_iso), now_utc)
        return await _persist_gap(target_gap)


    # running 状态：轮询 Skill 生成会话
    skill_session_id = str(target_gap.get("skill_session_id") or "").strip()
    if not skill_session_id:
        target_gap = _apply_gap_retry_or_dead_letter(
            target_gap,
            reason_code="missing_skill_session_id",
            reason_message="running gap 缺少 skill_session_id",
            terminal_status="failed",
            now_utc=now_utc,
            now_iso=now_iso,
            retry_policy=retry_policy,
        )
        target_gap["elapsed_seconds"] = _iso_elapsed_seconds(str(target_gap.get("started_at") or now_iso), now_utc)
        return await _persist_gap(target_gap)

    session_doc = await db[SESSION_COLLECTION].find_one({"session_id": skill_session_id})
    if not session_doc:
        target_gap = _apply_gap_retry_or_dead_letter(
            target_gap,
            reason_code="skill_session_not_found",
            reason_message="Skill 生成会话不存在",
            terminal_status="failed",
            now_utc=now_utc,
            now_iso=now_iso,
            retry_policy=retry_policy,
        )
        target_gap["elapsed_seconds"] = _iso_elapsed_seconds(str(target_gap.get("started_at") or now_iso), now_utc)
        return await _persist_gap(target_gap)

    skill_status = str(session_doc.get("status") or "").strip().lower()
    target_gap["pipeline_stage"] = str(session_doc.get("pipeline_stage") or target_gap.get("pipeline_stage") or "")
    target_gap["pipeline_message"] = str(session_doc.get("pipeline_message") or target_gap.get("pipeline_message") or "")
    target_gap["elapsed_seconds"] = _iso_elapsed_seconds(str(target_gap.get("started_at") or now_iso), now_utc)

    if skill_status == "completed":
        agentic_context = _extract_agentic_context_from_session_doc(session_doc)
        spec = session_doc.get("spec") or {}
        target_gap["status"] = "completed"
        target_gap["skill_tool_id"] = str(spec.get("tool_id") or "")
        target_gap["skill_display_name"] = str(spec.get("display_name") or "")
        target_gap["error"] = None
        target_gap["next_retry_at"] = ""
        target_gap["dead_letter"] = {}
        if agentic_context.get("verified_facts"):
            target_gap["agentic_verified_facts"] = agentic_context.get("verified_facts") or []
        if agentic_context.get("agentic_trace"):
            target_gap["agentic_trace"] = agentic_context.get("agentic_trace") or []
        if agentic_context.get("generation_engine"):
            target_gap["generation_engine"] = agentic_context.get("generation_engine")
        logger.info(
            "[GapJob][AgenticContext] job_id=%s gap_id=%s skill_status=completed engine=%s facts=%s trace_events=%s",
            clean_job_id,
            gap_id,
            agentic_context.get("generation_engine") or "-",
            len(agentic_context.get("verified_facts") or []),
            len(agentic_context.get("agentic_trace") or []),
        )
        return await _persist_gap(target_gap)

    if skill_status == "failed":
        agentic_context = _extract_agentic_context_from_session_doc(session_doc)
        if agentic_context.get("failure_summary"):
            target_gap["agentic_failure_summary"] = agentic_context.get("failure_summary")
        if agentic_context.get("verified_facts"):
            target_gap["agentic_verified_facts"] = agentic_context.get("verified_facts") or []
        if agentic_context.get("agentic_trace"):
            target_gap["agentic_trace"] = agentic_context.get("agentic_trace") or []
        if agentic_context.get("generation_engine"):
            target_gap["generation_engine"] = agentic_context.get("generation_engine")
        logger.info(
            "[GapJob][AgenticContext] job_id=%s gap_id=%s skill_status=failed engine=%s facts=%s trace_events=%s failure_summary=%s",
            clean_job_id,
            gap_id,
            agentic_context.get("generation_engine") or "-",
            len(agentic_context.get("verified_facts") or []),
            len(agentic_context.get("agentic_trace") or []),
            (agentic_context.get("failure_summary") or "")[:300],
        )
        target_gap = _apply_gap_retry_or_dead_letter(
            target_gap,
            reason_code="skill_generation_failed",
            reason_message=str(session_doc.get("pipeline_message") or "Skill 生成失败").strip() or "Skill 生成失败",
            terminal_status="failed",
            now_utc=now_utc,
            now_iso=now_iso,
            retry_policy=retry_policy,
        )
        return await _persist_gap(target_gap)

    if target_gap["elapsed_seconds"] >= _GAP_ITEM_TIMEOUT_SECONDS:
        target_gap = _apply_gap_retry_or_dead_letter(
            target_gap,
            reason_code="skill_generation_timeout",
            reason_message=f"Skill 生成超时（>{_GAP_ITEM_TIMEOUT_SECONDS}s）",
            terminal_status="timeout",
            now_utc=now_utc,
            now_iso=now_iso,
            retry_policy=retry_policy,
        )
        return await _persist_gap(target_gap)

    # 尚未完成，保持 running
    return await _persist_gap(target_gap)


async def process_agent_workshop_gap_resolution_jobs_once(
    limit: int = 1,
    worker_id: str = "",
    claim_lease_seconds: int = _GAP_JOB_CLAIM_LEASE_SECONDS,
) -> dict[str, Any]:
    """由后台 worker 调用：单次消费并推进 gap resolution jobs 状态机。"""
    try:
        db = get_mongo_db()
        collection = _get_collection(db, _GAP_RESOLUTION_JOB_COLLECTION)
        if collection is None:
            return {
                "status": "error",
                "message": f"数据库中不可用集合: {_GAP_RESOLUTION_JOB_COLLECTION}",
                "processed": 0,
            }

        cap = max(1, min(int(limit), 20))
        effective_worker_id = str(worker_id or "").strip() or "gap-worker"
        lease_seconds = max(5, min(int(claim_lease_seconds), 300))
        docs = await collection.find({}).to_list(length=200)
        if len(docs) == 0:
            logger.debug(
                "[GapJob][Worker] worker_id=%s total_jobs=0 cap=%s (idle, skip)",
                effective_worker_id,
                cap,
            )
            return {
                "status": "ok",
                "active_jobs": 0,
                "processed": 0,
                "attempted": 0,
                "claim_skipped": 0,
            }

        active_docs = [
            doc
            for doc in docs
            if str((doc or {}).get("status") or "").strip().lower() in _GAP_JOB_ACTIVE_STATUSES
        ]
        active_docs.sort(key=lambda item: str((item or {}).get("updated_at") or ""))

        if len(active_docs) == 0:
            logger.debug(
                "[GapJob][Worker] worker_id=%s total_jobs=%s active_jobs=0 cap=%s (all terminal, skip)",
                effective_worker_id,
                len(docs),
                cap,
            )
            return {
                "status": "ok",
                "active_jobs": 0,
                "processed": 0,
                "attempted": 0,
                "claim_skipped": 0,
            }

        logger.info(
            "[GapJob][Worker] worker_id=%s total_jobs=%s active_jobs=%s cap=%s",
            effective_worker_id,
            len(docs),
            len(active_docs),
            cap,
        )

        handled: list[dict[str, Any]] = []
        claim_skipped = 0
        for doc in active_docs[:cap]:
            claim = await _try_claim_gap_resolution_job(
                collection=collection,
                job_doc=doc,
                worker_id=effective_worker_id,
                lease_seconds=lease_seconds,
            )
            if not bool(claim.get("claimed")):
                claim_skipped += 1
                continue

            try:
                handled.append(await _process_single_gap_resolution_job(db, doc))
            finally:
                try:
                    await _release_gap_resolution_job_claim(
                        collection=collection,
                        job_id=str((doc or {}).get("job_id") or ""),
                        worker_id=effective_worker_id,
                        token=str(claim.get("token") or ""),
                    )
                except Exception as release_exc:
                    logger.debug("[GapJob][Worker] release_claim_fail job_id=%s err=%s", (doc or {}).get("job_id"), release_exc)

        processed_count = sum(1 for item in handled if bool((item or {}).get("processed")))

        if processed_count > 0 or len(handled) > 0:
            logger.info(
                "[GapJob][Worker] done worker_id=%s handled=%s processed=%s claim_skipped=%s",
                effective_worker_id,
                len(handled),
                processed_count,
                claim_skipped,
            )
        else:
            logger.debug(
                "[GapJob][Worker] done worker_id=%s handled=%s processed=%s claim_skipped=%s (idle)",
                effective_worker_id,
                len(handled),
                processed_count,
                claim_skipped,
            )

        return {
            "status": "ok",
            "active_jobs": len(active_docs),
            "processed": processed_count,
            "attempted": len(handled),
            "claim_skipped": claim_skipped,
            "results": handled,
        }
    except Exception as exc:
        logger.error("worker 消费 gap resolution jobs 失败: %s", exc, exc_info=True)
        return {"status": "error", "message": f"worker 消费 gap jobs 失败: {exc}", "processed": 0}


def _extract_blocking_gaps_from_report(gap_report: Any) -> list[str]:
    blocking_gaps = _read_mapping_or_attr(gap_report, "blocking_gaps", []) or []
    if not isinstance(blocking_gaps, list):
        return []
    return [str(item).strip() for item in blocking_gaps if str(item).strip()]


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


async def _get_existing_version_summary(db: Any, version_id: str) -> dict[str, Any]:
    """获取已有版本的摘要信息，用于"覆盖或继续"决策展示。"""
    if not version_id:
        return {"version_id": "", "found": False}
    versions = _get_collection(db, _WORKSHOP_VERSION_COLLECTION)
    if versions is None:
        return {"version_id": version_id, "found": False}
    version_doc = await versions.find_one({"version_id": version_id})
    if not version_doc:
        return {"version_id": version_id, "found": False}

    required_tools = version_doc.get("required_tools") or []
    required_capabilities = version_doc.get("required_capabilities") or []
    # required_tools 可能是 ["tool_id|tool_name", ...] 格式，提取 tool_id
    tool_ids = []
    for item in required_tools[:20]:
        if isinstance(item, str):
            tool_ids.append(item.split("|")[0].strip())
        elif isinstance(item, dict):
            tool_ids.append(str(item.get("tool_id") or item.get("id") or "").strip())

    return {
        "version_id": version_id,
        "found": True,
        "status": version_doc.get("status") or "",
        "created_at": str(version_doc.get("created_at") or "")[:19],
        "required_tools": tool_ids,
        "required_tools_count": len(tool_ids),
        "required_capabilities_count": len(required_capabilities),
        "agent_metadata": {
            "name": (version_doc.get("agent_metadata") or {}).get("name") or "",
            "type": (version_doc.get("agent_metadata") or {}).get("type") or "",
        },
    }


def _get_current_thread_context_spec_id() -> str:
    """从 contextvar 读取当前线程的 spec_id。"""
    try:
        from core.tools.context import get_current_assistant_thread_context
        ctx = get_current_assistant_thread_context() or {}
        return str(ctx.get("spec_id") or "").strip()
    except Exception:
        return ""


def _agent_id_equivalent(left: str, right: str) -> bool:
    """判断候选 Agent ID 是否只是历史前缀差异。"""
    clean_left = str(left or "").strip()
    clean_right = str(right or "").strip()
    if not clean_left or not clean_right:
        return False
    if clean_left == clean_right:
        return True

    def _canonical(value: str) -> str:
        for prefix in ("agent_candidate_", "candidate_"):
            if value.startswith(prefix):
                return value[len(prefix):]
        return value

    return _canonical(clean_left) == _canonical(clean_right)


async def _resolve_spec_name(db: Any, spec_id: str) -> str:
    """从数据库解析 spec_id 对应的 name。"""
    try:
        specs = _get_collection(db, _WORKSHOP_SPEC_COLLECTION)
        if specs is None:
            return ""
        doc = await specs.find_one({"spec_id": spec_id})
        if doc:
            return str(doc.get("name") or "").strip()
    except Exception:
        pass
    return ""


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


async def _auto_sync_gap_tools_to_workshop_version(db: Any, version_id: str) -> dict[str, Any]:
    """将已补齐/可复用的 gap 工具同步到当前 testing 版本，避免 rebuild/iterate 阶段死锁。"""
    clean_version_id = str(version_id or "").strip()
    versions = _get_collection(db, _WORKSHOP_VERSION_COLLECTION)
    if not clean_version_id or versions is None:
        return {"status": "skipped", "reason": "missing_version_or_collection", "version_id": clean_version_id}

    version_doc = await versions.find_one({"version_id": clean_version_id})
    if not version_doc:
        return {"status": "skipped", "reason": "version_not_found", "version_id": clean_version_id}
    version_status = str(version_doc.get("status") or "").strip().lower()
    if version_status not in {"testing", "draft", "evaluation"}:
        return {"status": "skipped", "reason": f"version_status_{version_status or 'unknown'}", "version_id": clean_version_id}

    service = AgentWorkshopService(db=db)
    workshop_session_id = str(version_doc.get("published_from_session_id") or "").strip()
    if not workshop_session_id:
        return {"status": "skipped", "reason": "missing_workshop_session_id", "version_id": clean_version_id}
    session = await service._load_session(workshop_session_id)
    if session is None:
        return {"status": "skipped", "reason": "workshop_session_not_found", "version_id": clean_version_id}

    existing_tools = _parse_string_list(",".join(list(version_doc.get("required_tools") or [])))
    auto_resolved = await service._collect_auto_resolved_gaps_for_session(workshop_session_id)
    auto_resolved_tools = [
        str(item.get("skill_tool_id") or "").strip()
        for item in auto_resolved
        if str(item.get("skill_tool_id") or "").strip()
    ]
    builtin_tools: list[str] = []
    gap_report = getattr(session, "gap_report", None)
    for gap_text in list(_read_mapping_or_attr(gap_report, "blocking_gaps", []) or []):
        evidence = service._builtin_tool_evidence_for_gap(str(gap_text or ""))
        if evidence:
            for tool_id in [str(evidence.get("skill_tool_id") or "").strip(), *[str(item or "").strip() for item in list(evidence.get("additional_tool_ids") or [])]]:
                if tool_id:
                    builtin_tools.append(tool_id)

    merged_tools = _dedupe_string_list([*existing_tools, *auto_resolved_tools, *builtin_tools])
    if merged_tools == existing_tools:
        return {
            "status": "unchanged",
            "version_id": clean_version_id,
            "workshop_session_id": workshop_session_id,
            "required_tools": merged_tools,
            "auto_resolved_tools": auto_resolved_tools,
            "builtin_tools": builtin_tools,
        }

    sync_result = await service.sync_version_required_tools(
        version_id=clean_version_id,
        required_tools=merged_tools,
        default_tools=merged_tools[:4],
        max_tool_calls=max(6, len(merged_tools)),
    )
    logger.info(
        "[AgentWorkshop][AutoSyncGapTools] version_id=%s session_id=%s added_tools=%s total_tools=%s",
        clean_version_id,
        workshop_session_id,
        [tool_id for tool_id in merged_tools if tool_id not in existing_tools],
        len(merged_tools),
    )
    return {
        "status": "synced",
        "version_id": clean_version_id,
        "workshop_session_id": workshop_session_id,
        "required_tools": merged_tools,
        "auto_resolved_tools": auto_resolved_tools,
        "builtin_tools": builtin_tools,
        "sync_result": sync_result,
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


def _extract_governance_version_id(version_result: dict[str, Any] | None) -> str | None:
    """从 build_workshop_version 结果中安全提取 version_id，兼容 version 字段为 dict 或 str 的情况。"""
    if not isinstance(version_result, dict):
        return None
    version = version_result.get("version")
    if isinstance(version, dict):
        return str(version.get("version_id") or "").strip() or None
    if isinstance(version, str):
        return version.strip() or None
    return None


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


def _generate_short_agent_name_llm(user_request: str, target_responsibility: str = "") -> dict:
    """用 LLM 同步生成简短 Agent 中文名和英文 slug（在同步工具函数中调用）。

    LLM 失败时用简单拼音/哈希兜底（不再用关键词映射表）。
    返回 {"name": "中文名", "slug": "english_slug"}
    """
    text = f"{target_responsibility or ''} {user_request or ''}".strip()
    if not text:
        return {"name": "智能分析助手", "slug": "intelligent_analysis"}

    try:
        from app.core.database import get_mongo_db_sync
        from core.llm import UnifiedLLMClient
        from core.llm.models import Message

        # 同步读取 LLM 配置
        sync_db = get_mongo_db_sync()
        config_doc = sync_db.system_configs.find_one(
            {"is_active": True},
            sort=[("version", -1)],
        )
        if not config_doc or "llm_configs" not in config_doc:
            logger.warning("[AgentName][LLM] 无活跃 LLM 配置，使用拼音兜底")
            return _generate_simple_slug_fallback(user_request, target_responsibility)

        # 复用 intelligent_assistant_service 的模型选择逻辑（同步部分）
        from app.services.intelligent_assistant_service import _resolve_models, _selection_model_name, _selection_config_id, resolve_llm_config_from_config_doc
        _, deep_selection, reasoning_selection, _ = _resolve_models(config_doc)
        target_selection = reasoning_selection or deep_selection
        target_model = _selection_model_name(target_selection)
        target_config_id = _selection_config_id(target_selection)
        if not target_model:
            logger.warning("[AgentName][LLM] 无法解析模型名称，使用拼音兜底 (reasoning=%s deep=%s)", reasoning_selection, deep_selection)
            return _generate_simple_slug_fallback(user_request, target_responsibility)

        config = resolve_llm_config_from_config_doc(
            config_doc,
            target_model=target_model,
            target_config_id=target_config_id,
            purpose="agent_naming",
        )
        if not config:
            logger.warning("[AgentName][LLM] 无法构建 LLM 配置 (model=%s config_id=%s)，使用拼音兜底", target_model, target_config_id)
            return _generate_simple_slug_fallback(user_request, target_responsibility)

        client = UnifiedLLMClient.from_config(config)

        system_prompt = """你是一个 Agent 命名专家。根据用户需求和职责描述，生成一个简短、专业、好记的 Agent 中文名和对应的英文标识（slug）。

命名规则：
【中文名】
1. 名字必须简短：不超过 12 个汉字（可含英文缩写如 DCF/PE/PB）
2. 名字必须体现 Agent 的核心业务能力，不要包含"对A股""上市公司""执行""输出"等冗余词
3. 名字以"助手"或"专家"结尾（默认"助手"）
4. 不要使用"Agent"这个英文词

【英文 slug】
1. 全部小写，用下划线分隔，只能包含字母、数字、下划线
2. 长度控制在 3-40 个字符之间
3. 准确反映 Agent 的核心业务能力，优先用专业术语
4. 以 "_analyst" 或 "_assistant" 结尾（默认用更具体的）
5. 不要使用 "agent"、"nanobot"、"candidate" 等无意义词

输出格式（严格 JSON，不要加解释）：
{"name": "中文名", "slug": "english_slug"}

示例：
- 需求"对A股上市公司执行多维度估值分析" → {"name": "多维度估值分析助手", "slug": "multidimensional_valuation_analyst"}
- 需求"帮我创建一个财报排雷助手" → {"name": "财报排雷助手", "slug": "financial_risk_screener"}
- 需求"分析股息率和分红情况" → {"name": "股息率分析助手", "slug": "dividend_yield_analyst"}
- 需求"做一个DCF估值工具" → {"name": "DCF估值助手", "slug": "dcf_valuation_assistant"}
- 需求"创建一个技术分析Agent" → {"name": "技术分析助手", "slug": "technical_analysis_assistant"}
- 需求"对上市公司进行风险排雷" → {"name": "风险排雷助手", "slug": "risk_screening_assistant"}
- 需求"生成研报" → {"name": "研报生成助手", "slug": "research_report_generator"}"""

        user_prompt = f"用户需求：{user_request or '(未提供)'}\n职责描述：{target_responsibility or '(未提供)'}\n\n请生成 Agent 的中文名和英文 slug（严格输出 JSON）："

        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_prompt),
        ]
        # DeepSeek 推理模型会先输出思考过程再输出 JSON，需要足够的 token 配额
        response = client.chat(messages, temperature=0.3, max_tokens=1000)
        raw_content = str(response.content or "").strip()

        logger.info("[AgentName][LLM] 原始响应: %s", raw_content[:400])

        # 尝试解析 JSON（支持推理模型在 JSON 前后输出思考文本）
        import json as _json
        try:
            cleaned = raw_content.strip()
            # 去掉 markdown 代码块标记
            if cleaned.startswith("```"):
                cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
                cleaned = re.sub(r"\s*```$", "", cleaned)
            # 优先尝试从文本中提取 JSON 对象
            json_match = re.search(r'\{[^{}]*"name"[^{}]*"slug"[^{}]*\}', cleaned, re.DOTALL)
            if not json_match:
                # 宽松匹配：找最后一个 { 到最后一个 } 之间的内容
                last_brace = cleaned.rfind("{")
                last_close = cleaned.rfind("}")
                if last_brace >= 0 and last_close > last_brace:
                    json_match = re.search(
                        r'\{.*\}', cleaned[last_brace:last_close + 1], re.DOTALL
                    )
                    if json_match:
                        cleaned = json_match.group(0)
            if json_match and json_match is not cleaned:
                cleaned = json_match.group(0)
            result = _json.loads(cleaned)
            name = str(result.get("name", "")).strip()
            slug = str(result.get("slug", "")).strip().lower()
            logger.info("[AgentName][LLM] 解析成功: name=%s slug=%s", name, slug)
        except Exception as parse_exc:
            # JSON 解析失败，尝试从文本中智能提取名字
            logger.warning("[AgentName][LLM] JSON 解析失败: %s, raw=%s", parse_exc, raw_content[:200])
            # 尝试从思考文本中提取 "中文名：xxx" 或 "名字：xxx" 模式
            name = ""
            slug = ""
            name_match = re.search(r'(?:中文名|名字)[：:]\s*([^\n。]{2,12})', raw_content)
            if name_match:
                name = name_match.group(1).strip()
            if not name:
                # 尝试找 slug 模式: "英文slug：xxx"
                slug_match = re.search(r'(?:英文\s*slug|slug)[：:]\s*([a-z][a-z0-9_]{2,39})', raw_content)
                if slug_match:
                    slug = slug_match.group(1).strip().lower()
                # 最后兜底：取第一行
                name = raw_content.strip().strip("\"'""''「」【】 ").split("\n")[0].strip()
                name = name.rstrip("。.；;")

        # 清理中文名
        name = name.rstrip("。.；;")

        # 验证 slug 格式
        import re as _re
        if not slug or not _re.match(r"^[a-z][a-z0-9_]{2,39}$", slug):
            # slug 不合规，用简单拼音兜底
            logger.warning("[AgentName][LLM] slug 不合规: slug=%r，使用拼音兜底", slug)
            slug = _generate_simple_slug_fallback(name or user_request, target_responsibility)["slug"]

        if name and len(name) <= 20:
            logger.info("[AgentName][LLM] 最终结果: request=%s -> name=%s slug=%s", user_request[:40], name, slug)
            return {"name": name, "slug": slug}

        logger.warning("[AgentName][LLM] 名字不合规: name=%r (len=%d)，使用拼音兜底", name, len(name or ""))
        return _generate_simple_slug_fallback(user_request, target_responsibility)
    except Exception as exc:
        logger.error("[AgentName][LLM] LLM 命名异常: %s", exc, exc_info=True)
        return _generate_simple_slug_fallback(user_request, target_responsibility)


def _fallback_slug_from_name(name: str, user_request: str = "", target_responsibility: str = "") -> str:
    """简单兜底：从文本生成哈希 slug（命名由 LLM 负责，此处仅为最终兜底）。"""
    text = f"{name or ''} {target_responsibility or ''} {user_request or ''}".strip()
    if not text:
        return "analysis_assistant"
    import hashlib
    digest = hashlib.md5(text.encode("utf-8")).hexdigest()[:6]
    # 尝试从英文名提取前缀（如果有英文的话）
    import re as _re
    english_parts = _re.findall(r'[a-zA-Z]{2,}', text)
    if english_parts:
        prefix = english_parts[0].lower()[:15]
        return f"{prefix}_assistant_{digest}"
    return f"analysis_assistant_{digest}"


def _generate_simple_slug_fallback(user_request: str, target_responsibility: str = "") -> dict:
    """LLM 命名失败时的简单兜底（不再用关键词映射）。

    返回 {"name": "中文名", "slug": "english_slug"}
    """
    text = f"{target_responsibility or ''} {user_request or ''}".strip()
    if not text:
        return {"name": "智能分析助手", "slug": "intelligent_analysis_assistant"}

    # 从需求中提取前 10 字作为简短名称
    short_name = text[:10].rstrip("，。、的了是") + "助手"
    slug = _fallback_slug_from_name(short_name, user_request, target_responsibility)
    return {"name": short_name, "slug": slug}


# 保留旧名作为别名，兼容 agent_builder_nodes.py 的引用
_generate_short_agent_name_fallback = _generate_simple_slug_fallback


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


def _build_temp_agent_spec_for_confirmation(
    *,
    agent_id: str,
    agent_name: str,
    responsibility: str,
    output_field: str,
    desired_output_shape: str,
    non_goals: list[str],
    constraints: list[str],
    valuation_method_scope: str,
    tool_ids: list[str],
) -> AgentSpec:
    capability_requirements = []
    for idx, text in enumerate([responsibility, desired_output_shape, valuation_method_scope], start=1):
        clean_text = str(text or "").strip()
        if not clean_text:
            continue
        capability_requirements.append({
            "capability_key": f"requirement_{idx}",
            "capability_name": clean_text[:40],
            "capability_type": "orchestration" if idx == 1 else "output",
            "description": clean_text,
            "delivery_requirement": "tool-or-prompt",
            "acceptance_criteria": ["按确认稿边界交付，不超出单一职责"],
        })
    preferred_methods = [item for item in [valuation_method_scope] if str(item or "").strip()]
    if tool_ids:
        preferred_methods.append("候选工具：" + "、".join(tool_ids))
    return AgentSpec(
        spec_id=agent_id,
        name=agent_name,
        domain="stock_analysis" if _is_stock_analysis_request(agent_name, responsibility, desired_output_shape) else "general",
        primary_goal=responsibility,
        responsibilities=[responsibility],
        non_goals=non_goals,
        inputs=[AgentSpecIOField(name="symbol", type="string", required=False, description="股票代码或用户输入标的")],
        outputs=[AgentSpecIOField(name=str(output_field or "analysis_report").strip() or "analysis_report", type="string", description=desired_output_shape or "分析报告")],
        constraints=constraints,
        preferred_methods=preferred_methods,
        capability_requirements=capability_requirements,
        status=AgentSpecStatus.DRAFT,
        source="nanobot_prepare",
    )


def _build_capability_inventory_from_hits(hits: list[Any]) -> dict[str, Any]:
    formatted: list[dict[str, Any]] = []
    available_tools: list[str] = []
    available_skills: list[str] = []
    missing_capabilities: list[str] = []
    for hit in hits or []:
        try:
            item = _format_capability_hit(hit)
        except Exception:
            continue
        formatted.append(item)
        tool_id = str(item.get("registry_tool_id") or item.get("capability_id") or "").strip()
        source_type = str(item.get("source_type") or "").strip().lower()
        if tool_id and source_type in {"skill", "external_skill"}:
            available_skills.append(tool_id)
        elif tool_id:
            available_tools.append(tool_id)
    return {
        "available_tools": _dedupe_string_list(available_tools),
        "available_skills": _dedupe_string_list(available_skills),
        "missing_capabilities": missing_capabilities,
        "results": formatted,
        "count": len(formatted),
    }


def _gap_report_to_dict(gap_report: Any) -> dict[str, Any]:
    if hasattr(gap_report, "model_dump"):
        return gap_report.model_dump(mode="json")
    return dict(gap_report or {}) if isinstance(gap_report, dict) else {}


def _gap_item_to_text(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("description") or item.get("gap") or item.get("gap_id") or "").strip()
    return str(item or "").strip()


def _quick_plan_feasible(gap_report: dict[str, Any], resolved_tools: list[str]) -> bool:
    blocking = [_gap_item_to_text(item) for item in gap_report.get("blocking_gaps") or []]
    if not resolved_tools:
        return False
    hard_markers = ("外部数据", "新数据源", "实时", "爬取", "api", "接口", "必须补齐", "无法降级")
    return not any(any(marker in gap for marker in hard_markers) for gap in blocking)


def _build_candidate_plans(gap_report: dict[str, Any], resolved_tools: list[str]) -> tuple[list[dict[str, Any]], str]:
    blocking_gaps = [_gap_item_to_text(item) for item in gap_report.get("blocking_gaps") or [] if _gap_item_to_text(item)]
    blocking_count = len(blocking_gaps)
    plans: list[dict[str, Any]] = []
    label_ord = ord("A")

    def add_plan(plan_id: str, name: str, description: str, recommended: bool, risk: str, required_new_skills: list[str] | None = None) -> None:
        nonlocal label_ord
        display_label = chr(label_ord)
        label_ord += 1
        plans.append({
            "plan_id": plan_id,
            "display_label": display_label,
            "plan_name": name,
            "name": f"{display_label}. {name}",
            "description": description,
            "required_new_skills": required_new_skills or [],
            "acknowledged_gaps": blocking_gaps if plan_id in {"complete", "quick"} else [],
            "estimated_effort": "低" if plan_id in {"direct", "quick"} else "中-高" if plan_id == "complete" else "待重新确认",
            "risk": risk,
            "recommended": recommended,
        })

    if blocking_count == 0:
        add_plan("direct", "推荐完整交付", "现有能力已覆盖需求，可直接生成完整版 Agent，并按原定核心风险/分析维度进入真数据测试。", True, "低：主要风险来自真实数据质量和后续验收结果。")
        add_plan("strict", "保守可追溯版", "仍使用现有能力，但收紧输出边界：只输出工具和数据明确支撑的结论，未覆盖或数据不足的部分标注为信息缺口。", False, "低：覆盖更稳健，但报告表达会更保守。")
        add_plan("enhanced", "扩展增强版", "在核心需求已满足的基础上，把非阻塞增强项作为可选扩展，例如更细的预警分级、更多风险信号或更丰富的情景说明。", False, "中：不是当前交付的必要条件，扩展过多会增加测试和解释复杂度。")
        return plans, "direct"

    suggested_skills = []
    for item in list(gap_report.get("suggested_tools") or []) + list(gap_report.get("suggested_capabilities") or []):
        if isinstance(item, dict):
            tool_id = str(item.get("tool_id") or item.get("capability_id") or "").strip()
            if tool_id:
                suggested_skills.append(tool_id)
    add_plan("complete", "完整方案", "先承认并补齐 blocking gaps，再生成完整 Agent，保留原需求目标和输出深度。", True, "需要补能力或生成 Skill，耗时更高但目标完整。", _dedupe_string_list(suggested_skills))
    if _quick_plan_feasible(gap_report, resolved_tools):
        add_plan("quick", "快速方案", "不补新能力，先用现有工具生成简化版；缺失字段标注信息缺口，不输出综合四色评级。", False, "覆盖范围受限，适合先试跑验证。")
    if blocking_count >= 3:
        add_plan("narrow", "缩小需求范围", "先回到需求重定义，缩小目标或输出范围后重新盘点能力。", False, "需要用户重新确认范围，不直接生成。")
    return plans, "complete"


def _plan_options_for_intent(candidate_plans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "index": idx + 1,
            "id": str(plan.get("plan_id") or ""),
            "name": str(plan.get("name") or plan.get("plan_name") or plan.get("plan_id") or ""),
            "description": str(plan.get("description") or ""),
            "display_label": str(plan.get("display_label") or ""),
            "selected_plan_id": str(plan.get("plan_id") or ""),
            "acknowledged_gaps": list(plan.get("acknowledged_gaps") or []),
        }
        for idx, plan in enumerate(candidate_plans)
    ]


def _quick_plan_constraint_text(acknowledged_gaps: list[str] | None = None) -> str:
    gap_text = "；".join([str(item).strip() for item in acknowledged_gaps or [] if str(item).strip()])
    suffix = f" 已知缺口：{gap_text}" if gap_text else ""
    return (
        "quick 方案约束：只允许使用现有已绑定工具直接返回可追溯指标；缺失字段必须标注为信息缺口；"
        "禁止要求 LLM 自行计算关键审计/财务/估值指标；禁止自行打综合四色评级或用缺失数据拼凑评分。"
        + suffix
    )


def _parse_acknowledged_gaps(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return _dedupe_string_list([str(item or "").strip() for item in raw if str(item or "").strip()])
    text = str(raw or "").strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return _dedupe_string_list([str(item or "").strip() for item in parsed if str(item or "").strip()])
    except Exception:
        pass
    return _parse_string_list(text)

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
    """以财经产品专家的口吻构建用户确认稿，避免技术清单式输出。

    系统收到本模板后，应以财经产品顾问的角度与用户沟通——
    讲分析框架和业务价值，不要逐行念工具ID和技术参数。
    后端所需的技术绑定信息已在 JSON 的其他字段中传递。
    """
    # ── 业务叙事版确认稿（不是技术清单） ──
    lines = [
        "【方案概览】",
        f"名称：{agent_name}",
        f"定位：{responsibility}",
        f"输出：{desired_output_shape}",
    ]

    scope_parts = []
    if valuation_method_scope:
        scope_parts.append(f"估值方法：{valuation_method_scope}")
    if resolved_default_tools := bound_tools:
        # 不列 tool_id，只说覆盖了哪些维度
        pass  # 维度覆盖由 capability_inventory 的 business 描述提供
    lines.append("")

    if non_goals:
        lines.append("【明确不做的】")
        for item in non_goals:
            lines.append(f"- {item}")
        lines.append("")

    if report_contract is not None:
        forbidden_items = report_contract.get("forbidden_expansions") or []
        lines.append("【报告内容边界】")
        lines.append(f"章节范围：{report_contract.get('content_scope') or '与职责相匹配的估值分析章节'}")
        lines.append(f"预览方式：{_humanize_preview_mode(str(report_contract.get('style_preview_mode') or ''))}")
        if forbidden_items:
            lines.append(f"明确排除：{_join_display_items(forbidden_items, default='无')}")
        lines.append("")

    # 覆盖风险
    overwrite_text = "会覆盖现有配置，需用户明确同意" if overwrite_risk.get("requires_explicit_overwrite") else "不影响现有配置"
    lines.append(f"【覆盖影响】{overwrite_text}")
    lines.append("")

    # 确认引导
    lines.append("如果以上内容确认无误，请回复：确认")
    if overwrite_risk.get("requires_explicit_overwrite"):
        lines.append("（注意：后续生成该 Agent 时会覆盖现有配置）")

    return "\n".join(lines)


def _normalize_recommendation_policy(_: str = "") -> str:
    return f"{_GLOBAL_NO_TRADING_ADVICE_POLICY}\n\n{_GLOBAL_NUMERICAL_TOOL_POLICY}"


def _append_trading_guard(text: str) -> str:
    clean_text = str(text or "").strip()
    if not clean_text:
        return f"{_GLOBAL_NO_TRADING_ADVICE_POLICY}\n\n{_GLOBAL_NUMERICAL_TOOL_POLICY}"
    if _GLOBAL_NO_TRADING_ADVICE_POLICY in clean_text and _GLOBAL_NUMERICAL_TOOL_POLICY in clean_text:
        return clean_text
    if _GLOBAL_NO_TRADING_ADVICE_POLICY in clean_text:
        return f"{clean_text}\n\n{_GLOBAL_NUMERICAL_TOOL_POLICY}"
    if _GLOBAL_NUMERICAL_TOOL_POLICY in clean_text:
        return f"{clean_text}\n\n{_GLOBAL_NO_TRADING_ADVICE_POLICY}"
    return f"{clean_text}\n\n{_GLOBAL_NO_TRADING_ADVICE_POLICY}\n\n{_GLOBAL_NUMERICAL_TOOL_POLICY}"


def _append_trading_guard_constraint(text: str) -> str:
    clean_text = str(text or "").strip()
    if _GLOBAL_NO_TRADING_ADVICE_POLICY in clean_text and _GLOBAL_NUMERICAL_TOOL_POLICY in clean_text:
        return clean_text
    if _GLOBAL_NO_TRADING_ADVICE_POLICY in clean_text:
        return f"{clean_text}\n{_GLOBAL_NUMERICAL_TOOL_POLICY}"
    if _GLOBAL_NUMERICAL_TOOL_POLICY in clean_text:
        return f"{clean_text}\n{_GLOBAL_NO_TRADING_ADVICE_POLICY}"
    if not clean_text:
        return f"{_GLOBAL_NO_TRADING_ADVICE_POLICY}\n{_GLOBAL_NUMERICAL_TOOL_POLICY}"
    return f"{clean_text}\n{_GLOBAL_NO_TRADING_ADVICE_POLICY}\n{_GLOBAL_NUMERICAL_TOOL_POLICY}"


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


async def _merge_latest_evaluations_into_versions(
    version_results: list[dict[str, Any]],
    db,
) -> None:
    """批量查询最新评估记录，合并评分/结论到 version_results 中。"""
    if not version_results:
        return
    version_ids = [str(v.get("version_id") or "").strip() for v in version_results if v.get("version_id")]
    if not version_ids:
        return

    try:
        evaluations_collection = _get_collection(db, _WORKSHOP_EVALUATION_COLLECTION)
        if evaluations_collection is None:
            return

        # 批量查询所有相关评估，按 created_at 降序
        eval_cursor = evaluations_collection.find(
            {"version_id": {"$in": version_ids}},
            {"_id": 0, "evaluation_id": 1, "version_id": 1, "decision": 1, "scores": 1, "issues": 1, "created_at": 1},
        )
        if hasattr(eval_cursor, "sort"):
            eval_cursor = eval_cursor.sort("created_at", -1)

        eval_docs = await eval_cursor.to_list(length=len(version_ids) * 3)

        # 按 version_id 分组，取每个版本最新的评估
        latest_eval_by_version: dict[str, dict[str, Any]] = {}
        for doc in eval_docs:
            vid = str(doc.get("version_id") or "").strip()
            if vid and vid not in latest_eval_by_version:
                latest_eval_by_version[vid] = doc

        for version in version_results:
            vid = str(version.get("version_id") or "").strip()
            if not vid:
                continue
            eval_doc = latest_eval_by_version.get(vid)
            if not eval_doc:
                continue
            scores = eval_doc.get("scores") or {}
            version["latest_evaluation"] = {
                "decision": str(eval_doc.get("decision") or ""),
                "overall_score": scores.get("overall") if isinstance(scores, dict) else None,
                "issues_count": len(eval_doc.get("issues") or []),
                "evaluation_id": str(eval_doc.get("evaluation_id") or ""),
            }
    except Exception:
        pass


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
        return {"status": "error", "message": f"未找到 thread_id={clean_thread_id} 对应的会话"}

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
            resolved_agent_type = "universal"
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
    description="根据用户的初始创建请求，生成下一轮应该追问的需求采集提纲，避免在需求仍模糊时直接生成 Agent。",
    category="assistant_ops",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    when_to_use="当用户刚提出创建 Agent 的想法，但职责边界、输出形状、非目标或工具依赖还不清楚时使用。",
    when_not_to_use="当需求已经清晰并且可以直接进入确认稿或生成阶段时，不需要再调用。",
    returns="返回 JSON 字符串，包含已知信息、缺失决策、推荐追问问题，以及是否可以直接进入确认阶段。",
    example="prepare_agent_requirement_intake(user_request='帮我做一个估值分析 agent')",
    related_tools=["prepare_agent_generation_confirmation", "generate_confirmed_candidate_agent"],
    data_source_handling="local_only",
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
    report_section_scope: Annotated[str, "报告章节边界，如 仅估值相关章节，不含技术面/交易执行方案/多情景研究"] = "",
) -> str:
    """生成 Agent 创建前的需求采集提纲 —— 自动补全智能默认值，只将最关键决策提升给用户。"""
    try:
        clean_request = str(user_request or "").strip()
        if not clean_request:
            return _json_response({"status": "error", "message": "user_request 不能为空"})

        resolved_non_goals = _parse_string_list(non_goals)
        resolved_tools = _parse_string_list(preferred_tools)
        stock_analysis_request = _is_stock_analysis_request(clean_request, target_responsibility, desired_output_shape)
        output_preview_request = _is_output_preview_request(clean_request, desired_output_shape)

        # ── 🔍 入口日志：需求采集 ──
        logger.info(
            "[Intake][Entry] request_len=%d responsibility_len=%d output_shape_len=%d "
            "non_goals_len=%d preferred_tools=%s stock=%s output_preview=%s existing=%s",
            len(clean_request),
            len(str(target_responsibility or "")),
            len(str(desired_output_shape or "")),
            len(str(non_goals or "")),
            str(preferred_tools or "")[:80],
            "yes" if stock_analysis_request else "no",
            "yes" if output_preview_request else "no",
            str(existing_agent_id or ""),
        )
        effective_recommendation_policy = _normalize_recommendation_policy(recommendation_policy)

        # === 智能默认值：用户没说的情况下，自动补全 ===
        smart_defaults = {
            "output_shape": "结构化的自然语言报告，包含评分/评级和关键数据依据",
            "non_goals": "不做交易建议/仓位建议/目标价区间/止损止盈/技术择时",
            "preferred_tools": resolved_tools,  # 如果为空，让缺口分析阶段自动推荐
            "creation_mode": "new",  # 默认新建
            "recommendation_policy": "只做研究分析，不输出任何买卖建议、仓位建议、目标价、止损止盈等操作性指令",
            "valuation_method_scope": "综合估值（行业对比PE/PB + 历史估值分位 + DCF），如用户指定则优先用户",
            "test_strategy": "auto_test",  # 默认允许自动跑样例验证
            "preview_mode": "structure_only",  # 报告样式预览只看结构骨架
            "report_section_scope": "仅保留估值/分析相关章节，不扩展到技术面、交易执行方案、多情景研究",
        }

        # 确定实际值（用户提供 > 智能默认）
        effective_output_shape = desired_output_shape if not _looks_unspecified(desired_output_shape) else smart_defaults["output_shape"]
        effective_non_goals = resolved_non_goals if resolved_non_goals else _parse_string_list(smart_defaults["non_goals"])
        effective_tools = resolved_tools if resolved_tools else []
        effective_creation_mode = "new" if not existing_agent_id.strip() else "overwrite"
        effective_valuation_scope = valuation_method_scope if not _looks_unspecified(valuation_method_scope) else smart_defaults["valuation_method_scope"]
        effective_test_strategy = test_strategy if not _looks_unspecified(test_strategy) else smart_defaults["test_strategy"]
        effective_preview_mode = preview_mode if not _looks_unspecified(preview_mode) else smart_defaults["preview_mode"]
        effective_report_scope = report_section_scope if not _looks_unspecified(report_section_scope) else smart_defaults["report_section_scope"]

        # === 只将真正关键的决策提升给用户（最多2个） ===
        critical_questions: list[dict] = []
        has_critical_single_responsibility_gap = _looks_unspecified(target_responsibility)

        if has_critical_single_responsibility_gap:
            critical_questions.append({
                "id": "single_responsibility",
                "question": "这个 Agent 要做什么？请用一句话描述它的核心任务。",
                "why_critical": "没有明确的职责边界，后续的工具选择、输出结构都无法精准匹配。",
            })

        if not effective_tools and not has_critical_single_responsibility_gap:
            # 工具偏好缺失但在职责明确时可以自动推荐
            critical_questions.append({
                "id": "tool_preferences",
                "question": "你是否已经知道它必须依赖哪些工具或数据来源？如果没有偏好，我会在缺口分析阶段自动推荐最适合的工具。",
                "why_critical": "工具范围影响能力边界，但你也可以完全交给我推荐。",
            })

        # === 生成简短 Agent 名（中文名 + 英文 slug）===
        naming_result = _generate_short_agent_name_llm(clean_request, target_responsibility)
        proposed_agent_name = naming_result.get("name", "智能分析助手")
        proposed_agent_slug = naming_result.get("slug", "analysis_assistant")

        # === 构建提案 ===
        proposed_plan = {
            "single_responsibility": target_responsibility if not has_critical_single_responsibility_gap else "（待确认）",
            "proposed_agent_name": proposed_agent_name,
            "proposed_agent_slug": proposed_agent_slug,
            "output_shape": effective_output_shape,
            "non_goals": effective_non_goals,
            "preferred_tools": effective_tools if effective_tools else "（缺口分析阶段自动推荐）",
            "creation_mode": effective_creation_mode,
            "recommendation_policy": effective_recommendation_policy,
        }
        if stock_analysis_request:
            proposed_plan["valuation_method_scope"] = effective_valuation_scope
            proposed_plan["test_strategy"] = effective_test_strategy
            proposed_plan["preview_mode"] = effective_preview_mode
            proposed_plan["report_section_scope"] = effective_report_scope

        can_proceed_to_confirmation = len(critical_questions) == 0

        # ── 🔍 出口日志：需求采集结果 ──
        logger.info(
            "[Intake][Exit] responsibility=%s output=%s can_proceed=%s critical_q=%d next=%s",
            str(target_responsibility or "")[:80],
            str(desired_output_shape or "")[:80],
            "yes" if can_proceed_to_confirmation else "no",
            len(critical_questions),
            "prepare_agent_generation_confirmation" if can_proceed_to_confirmation else "present_proposed_plan_and_ask_critical_questions",
        )

        # ── 更新 thread_context：让 FlowController 追踪进度 ──
        try:
            from core.embedded_nanobot.intent_context import update_intent_context_in_thread
            stage = "exploring" if not can_proceed_to_confirmation else "draft_preparing"
            pending_q = ""
            pending_opts = []
            if not can_proceed_to_confirmation and critical_questions:
                # 将关键问题写入 pending 状态，确保跨轮对话不丢失上下文
                pending_q = critical_questions[0]["question"]
                pending_opts = [
                    {"index": i + 1, "id": q["id"], "name": q["question"][:60], "description": q.get("why_critical", "")}
                    for i, q in enumerate(critical_questions[:3])
                ]
            update_intent_context_in_thread(
                action="requirement_intake",
                stage=stage,
                pending_question=pending_q,
                pending_options=pending_opts,
            )
        except Exception:
            pass

        return _json_response({
            "status": "ok",
            "user_request": clean_request,
            "request_profile": {
                "stock_analysis_request": stock_analysis_request,
                "output_preview_request": output_preview_request,
            },
            "proposed_plan": proposed_plan,
            "critical_questions": critical_questions,
            "can_proceed_to_confirmation": can_proceed_to_confirmation,
            "recommended_next_step": (
                "prepare_agent_generation_confirmation" if can_proceed_to_confirmation
                else "present_proposed_plan_and_ask_critical_questions"
            ),
            "nanobot_guidance": (
                "✅ 方案已自动补全。你现在是财经产品专家，不是问卷调查员。\n\n"
                "核心原则：抛砖引玉 —— 先给出你的专业草稿，用户自然会纠正。\n\n"
                "沟通规则：\n"
                "1. 先呈现 proposed_plan，用业务语言说明每个选择的理由。\n"
                "2. 如果 critical_questions 非空，最多问 1 个最关键的问题，其余全部用默认值。\n"
                "3. 每个问题必须给出背景、不同选择的区别、你的推荐方案和理由。\n"
                "   例如不要说「你希望用哪些估值方法？」，而要说「估值有两大类：相对估值（PE/PB/PEG等，看同行业对比）和绝对估值（DCF等，看内在价值）。两者互补，我建议都纳入。你觉得呢？」\n"
                "4. 禁止列出一长串问题让用户逐个回答。这是最低效的沟通方式。\n"
                "5. 禁止问用户「你用什么数据源/数据终端」——平台内置 Tushare/AKShare/BaoStock 等数据源，Agent 通过工具自动获取数据，不需要用户选择。\n"
                "6. 用户说「可以」「好的」「没意见」即视为认可，直接推进到确认阶段。\n"
                "7. 用户没有提到的维度，直接用专业默认值补全，不要追问。\n"
                "   例如用户没说要不要风险提示，默认加上；用户没说 A 股还是港股，默认 A 股。\n"
                "   用户在草稿中看到默认值后如果不同意，自然会告诉你。\n"
                "8. 【重要】禁止在回复中提及任何工具名（如 get_dcf_valuation、get_comparable_company_valuation 等）。\n"
                "   用户不关心底层用了哪个工具，只关心 Agent 能解决什么业务问题。\n"
                "   工具绑定是平台内部的事，会在后续能力盘点阶段自动处理，不需要也不应该暴露给用户。\n"
                "   正确说法：「我们会自动获取同行业估值数据做横向对比」「系统会拉取历史估值区间计算分位」\n"
                "   错误说法：「平台有 get_comparable_company_valuation 工具」「需要确认 get_historical_valuation_percentile_tool 是否就绪」"
            ) if can_proceed_to_confirmation else (
                "✅ 方案已自动补全大部分维度。你现在是财经产品专家，不是问卷调查员。\n\n"
                "核心原则：抛砖引玉 —— 先给出你的专业草稿，用户自然会纠正。\n\n"
                "沟通规则：\n"
                "1. 先简要呈现 proposed_plan，说明每个默认选择的理由。\n"
                "2. 针对 critical_questions，最多展开 1 个最关键的问题，其余全部用默认值。\n"
                "3. 每个问题必须给出背景、不同选择、你的推荐方案和理由，不要只扔问题。\n"
                "4. 禁止列出一长串问题让用户逐个回答。\n"
                "5. 用户没有提到的维度，直接用专业默认值补全，不要追问。\n"
                "6. 禁止问用户「你用什么数据源/数据终端」——平台内置 Tushare/AKShare/BaoStock 等数据源，Agent 通过工具自动获取数据，不需要用户选择。\n"
                "7. 用户说「可以」「好的」「没意见」即视为认可，直接推进。\n"
                "8. 【重要】禁止在回复中提及任何工具名（如 get_dcf_valuation、get_comparable_company_valuation 等）。\n"
                "   用户不关心底层用了哪个工具，只关心 Agent 能解决什么业务问题。\n"
                "   工具绑定是平台内部的事，会在后续能力盘点阶段自动处理，不需要也不应该暴露给用户。\n"
                "   正确说法：「我们会自动获取同行业估值数据做横向对比」「系统会拉取历史估值区间计算分位」\n"
                "   错误说法：「平台有 get_comparable_company_valuation 工具」「需要确认 get_historical_valuation_percentile_tool 是否就绪」"
            ),
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
    when_to_use="当已经形成候选 Agent 方案，但还没有拿到用户对职责边界、输出形状和覆盖风险的明确确认时使用。",
    when_not_to_use="不适合直接落库创建 Agent。它只负责生成确认稿。",
    returns="返回 JSON 字符串，包含确认稿、覆盖风险和建议用户确认项。",
    example="prepare_agent_generation_confirmation(agent_id='valuation_candidate_v1', agent_name='估值候选Agent', target_responsibility='输出A股估值结论', tool_ids='get_value_factor_bundle_tool')",
    related_tools=["generate_confirmed_candidate_agent", "create_or_update_runtime_agent_config"],
    data_source_handling="local_only",
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
    report_section_scope: Annotated[str, "报告章节边界，如 仅估值相关章节，不含技术面/交易执行方案/多情景研究"] = "",
    status: Annotated[str, "目标模板状态，默认 active"] = "active",
) -> str:
    """生成 Agent 创建确认稿。"""
    try:
        clean_agent_id = str(agent_id or "").strip()
        clean_agent_name = str(agent_name or "").strip()
        clean_responsibility = str(target_responsibility or "").strip()
        if not clean_agent_id or not clean_agent_name or not clean_responsibility:
            return _json_response({"status": "error", "message": "agent_id、agent_name、target_responsibility 不能为空"})

        # ── 🔍 入口日志：生成确认稿 ──
        logger.info(
            "[Prepare][Entry] agent_id=%s name=%s responsibility_len=%d tool_count=%d",
            clean_agent_id,
            str(clean_agent_name)[:60],
            len(clean_responsibility),
            len(_parse_string_list(tool_ids)),
        )

        resolved_tools = _parse_string_list(tool_ids)
        resolved_default_tools = _parse_string_list(default_tools) or resolved_tools[:2] or list(resolved_tools)
        resolved_non_goals = _parse_string_list(non_goals)
        effective_recommendation_policy = _normalize_recommendation_policy(recommendation_policy)
        output_preview_request = _is_output_preview_request(clean_responsibility, desired_output_shape)
        report_like_request = _is_report_like_request(output_field, desired_output_shape, clean_responsibility)
        # 需求确认阶段允许 tool_ids 为空：此时确认稿只包含职责/输出/非目标，
        # 工具候选留待能力盘点（CAPABILITY_CHECK）阶段补全。
        # 与 _build_confirmation_template 的空 bound_tools 处理一致。

        stock_analysis_request = _is_stock_analysis_request(clean_agent_name, clean_responsibility, desired_output_shape)
        # 自动补全默认值，与 prepare_agent_requirement_intake 保持一致
        if stock_analysis_request and not resolved_non_goals:
            resolved_non_goals = _parse_string_list("不做交易建议/仓位建议/目标价区间/止损止盈/技术择时")
        if stock_analysis_request and _looks_unspecified(valuation_method_scope):
            valuation_method_scope = "综合估值（行业对比PE/PB + 历史估值分位 + DCF）"
        if stock_analysis_request and _looks_unspecified(test_strategy):
            test_strategy = "auto_test"
        if output_preview_request and _looks_unspecified(preview_mode):
            preview_mode = "structure_only"
        if stock_analysis_request and output_preview_request and _looks_unspecified(report_section_scope):
            report_section_scope = "仅保留估值/分析相关章节，不扩展到技术面、交易执行方案、多情景研究"

        registry = get_tool_registry()
        missing_tools = [tool_id for tool_id in resolved_tools if registry.get(tool_id) is None]
        if missing_tools:
            return _json_response({"status": "error", "message": f"以下工具未注册: {', '.join(missing_tools)}", "missing_tools": missing_tools})

        db = get_mongo_db()

        # ── 幂等性保护：同一 agent_id 已有活跃确认稿时禁止覆盖 ──
        try:
            existing_doc = await db["agent_workshop_sessions"].find_one(
                {"agent_id": clean_agent_id, "builder_contracts.stage": "confirmation_pending"},
                {"session_id": 1, "builder_contracts": 1},
            )
        except Exception:
            existing_doc = None
        if existing_doc:
            logger.warning(
                "[Prepare][Idempotent] ⚠️ agent_id=%s 已有活跃确认稿，拒绝覆盖 session_id=%s",
                clean_agent_id,
                existing_doc.get("session_id", ""),
            )
            return _json_response({
                "status": "already_pending",
                "message": (
                    f"Agent `{clean_agent_id}` 已有待确认的生成方案。"
                    f"请直接引导用户选择方案或回复质疑，不要重复生成确认稿。"
                    f"如果用户已明确选择方案，调用 generate_confirmed_candidate_agent。"
                ),
            })

        # ── V2 流程：需求确认阶段只确认职责/输出/边界，不展示工具候选，不做缺口分析 ──
        # 缺口分析放在用户确认需求后的 CAPABILITY_CHECK 阶段统一进行。
        # 此阶段不把 capability_inventory / gap_report 暴露给用户。
        logger.info(
            "[Prepare][RequirementOnly] agent_id=%s name=%s (no capability inventory, no gap analysis)",
            clean_agent_id,
            clean_agent_name,
        )
        overwrite_risk = await _inspect_agent_overwrite_risk(db, clean_agent_id, status=status)
        report_contract = None
        if report_like_request:
            report_contract = {
                "style_preview_mode": preview_mode or "structure_skeleton",
                "content_scope": report_section_scope or "仅限当前已确认职责相关章节，不得自动扩展到未确认模块",
                "preview_instruction": "确认阶段默认只展示章节骨架/字段模板，不填充真实内容；只有用户明确要求时才允许占位符 mock。",
                "forbidden_expansions": [
                    "技术分析",
                    "交易执行方案",
                    "多情景研究",
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

        pending_question = (
            "以上是我对这个 Agent 需求的理解。请确认职责边界和输出形态是否符合你的预期。"
            "如果无误，请回复「确认」；如需调整，请直接告诉我修改点。"
        )

        # 更新意图上下文：等待用户确认需求
        _auto_update_intent(
            action="create_agent",
            stage="requirement_confirmation_pending",
            spec_id=clean_agent_id,
            spec_name=clean_agent_name,
            intent_summary=f"创建 Agent：{clean_responsibility}",
            pending_options=[],
            proposed_items=[],
            pending_question=pending_question,
            active_subtask="等待用户确认需求",
            next_action="用户确认需求后进入 CAPABILITY_CHECK，调用 search_project_capabilities + analyze_agent_workshop_gaps",
        )

        # ── 🔍 追踪日志：确认 prepare 阶段输出 ──
        logger.info(
            "[Prepare][Output] agent_id=%s confirmation_type=requirement_confirmation "
            "responsibility_len=%d output_shape_len=%d pending_question_len=%d",
            clean_agent_id,
            len(clean_responsibility),
            len(desired_output_shape or ""),
            len(pending_question),
        )

        return _json_response({
            "status": "ok",
            "confirmation_required": True,
            "ready_to_execute": False,
            "confirmation_type": "requirement_confirmation",
            "nanobot_guidance": (
                "你现在是财经产品专家的身份与用户沟通，不是技术架构师。\n\n"
                "核心原则：抛砖引玉 —— 先给出你的专业确认稿，用户自然会纠正。\n\n"
                "沟通规则：\n"
                "1. 只讲业务价值：这个 Agent 做什么、输出什么、不做什么。"
                "不要讲「绑定了几个工具」或列出 tool_id。\n"
                "2. 不要展示能力盘点：用户不需要知道系统有哪些工具，"
                "只需要知道 Agent 能解决什么问题。\n"
                "3. 不要提前给方案：此阶段只确认需求，方案会在需求确认后、"
                "做完能力盘点再给出。\n"
                "4. 不要问一连串问题：需求已通过 proposed_plan 自动补全了默认值，"
                "直接呈现确认稿，让用户看到草稿后自然纠正。\n"
                "5. 禁止问用户「你用什么数据源/数据终端」——平台内置 Tushare/AKShare/BaoStock 等数据源，Agent 通过工具自动获取数据，不需要用户选择。\n"
                "6. 用户回复「确认」「好的」「可以」等任意认可表述，"
                "就视为需求已确认，进入下一阶段做能力盘点。"
            ),
            "pending_question": pending_question,
            "confirmation_brief": {
                "target_responsibility": clean_responsibility,
                "proposed_agent_id": clean_agent_id,
                "proposed_agent_name": clean_agent_name,
                "desired_output_shape": desired_output_shape,
                "output_field": output_field,
                "chosen_build_path": "create_universal_agent",
                "confirmation_type": "requirement_confirmation",
                "agent_id": clean_agent_id,
                "agent_name": clean_agent_name,
                "target_responsibility": clean_responsibility,
                "desired_output_shape": desired_output_shape,
                "output_field": output_field,
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
                    "职责边界：这个 Agent 该做什么、不做什么，是否符合你的预期？",
                    "输出内容：报告/分析的结构是否覆盖了你关心的维度？",
                    "分析方法：估值逻辑和覆盖范围是否准确？",
                ],
                "suggested_user_reply": f"确认；allow_overwrite={'yes' if overwrite_risk['requires_explicit_overwrite'] else 'no'}",
            },
        })
    except Exception as exc:
        logger.error("生成 Agent 创建确认稿失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"生成 Agent 创建确认稿失败: {exc}"})


@tool
@register_tool(
    tool_id="propose_agent_build_plans",
    name="基于缺口分析生成候选方案",
    description="在需求确认后、根据 gap_report 生成 2-4 个 Agent 构建方案（推荐完整版/严格交付版/扩展增强版/降级版），供用户选择。",
    category="assistant_ops",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    when_to_use=(
        "当已经确认用户需求，并已完成能力盘点和 gap 分析后，"
        "需要把技术缺口翻译成用户可理解的多个可行方案时使用。"
    ),
    when_not_to_use=(
        "不要在需求未确认前调用；也不要在没有任何 gap_report 时调用。"
        "此工具只负责生成方案，不执行 Agent 创建。"
    ),
    returns=(
        "返回 JSON 字符串，包含 candidate_plans（固定字段）、recommended_plan_id、pending_question。"
    ),
    example="propose_agent_build_plans(gap_report_json='{\"blocking_gaps\":[],\"non_blocking_gaps\":[]}')",
    related_tools=["search_project_capabilities", "analyze_agent_workshop_gaps", "generate_confirmed_candidate_agent"],
    data_source_handling="local_only",
)
async def propose_agent_build_plans(
    gap_report_json: Annotated[str, "JSON 字符串，包含 blocking_gaps、non_blocking_gaps、suggested_tools 等"],
    agent_responsibility: Annotated[str, "Agent 职责描述，用于生成更贴合的方案"] = "",
    agent_output_shape: Annotated[str, "Agent 输出形状描述"] = "",
) -> str:
    """基于 gap 分析报告生成候选构建方案。"""
    try:
        gap_report = _parse_optional_json_object(gap_report_json, "gap_report_json")
        blocking_gaps = gap_report.get("blocking_gaps") or []
        non_blocking_gaps = gap_report.get("non_blocking_gaps") or []
        inferable_gaps = gap_report.get("inferable_gaps") or []
        if not isinstance(blocking_gaps, list):
            blocking_gaps = []
        if not isinstance(non_blocking_gaps, list):
            non_blocking_gaps = []
        if not isinstance(inferable_gaps, list):
            inferable_gaps = []

        # 构造 LLM 提示词
        system_prompt = (
            "你是一位资深的财经产品专家。你的任务是根据系统的能力缺口分析结果，"
            "为用户生成 2-4 个清晰、可执行、可比较的 Agent 构建方案。即使没有 blocking gap，也必须给出不同交付取向的候选方案，而不是只给一套。\n\n"
            "规则：\n"
            "1. 输出必须是合法 JSON，不要包含 markdown 代码块标记。\n"
            "2. 方案用业务语言描述，不要暴露内部工具 ID 或技术细节。\n"
            "3. 方案数量：\n"
            "   - 0 个 blocking gap：至少提供 direct（推荐完整交付）、strict（保守可追溯版）和 enhanced（扩展增强版）三套；enhanced 只能作为可选扩展，不能伪造必需缺口。\n"
            "   - 1-2 个 blocking gap：提供 complete（补齐）、quick（降级先跑）和 strict（缩小到可追溯范围）。\n"
            "   - 3 个及以上 blocking gap：提供 complete、quick、narrow 三套。\n"
            "4. complete 方案必须列出 required_new_skills（需要生成/复用的能力）。\n"
            "5. quick/strict 方案必须说明哪些输出会被降级、收窄或要求更严格的数据依据。\n"
            "6. narrow 方案必须给出建议缩小后的职责范围。\n"
            "7. 必须设置 recommended_plan_id：0 个 blocking gap 时推荐 direct；有 blocking gap 时默认推荐 complete。\n"
            "8. 每个方案必须包含 gap_summary 字段，说明该方案下的数据覆盖情况：哪些数据有直接工具支撑、哪些通过推断获取、哪些缺失。\n"
            "9. 每个方案必须包含 feasibility 字段，说明实现可行性：能否实现、有哪些困难、需要哪些额外开发或数据接入。\n"
            "10. 对于有 blocking_gaps 的方案，必须在 feasibility 中明确说明这些缺口能否补齐、补齐方式（新建 Skill/接入外部数据/降级处理）以及补齐失败的影响。\n"
        )

        user_prompt = (
            f"Agent 职责：{agent_responsibility or '（未提供）'}\n"
            f"Agent 输出：{agent_output_shape or '（未提供）'}\n\n"
            "能力缺口分析结果：\n"
            f"blocking_gaps（阻塞性缺口，无法实现的分析维度）数量：{len(blocking_gaps)}\n"
            f"blocking_gaps 详情：{_json_compact_dump(blocking_gaps)}\n"
            f"inferable_gaps（可推断缺口，有相关数据可定性推断但不阻塞）数量：{len(inferable_gaps)}\n"
            f"inferable_gaps 详情：{_json_compact_dump(inferable_gaps)}\n"
            f"non_blocking_gaps（其他非阻塞性缺口）数量：{len(non_blocking_gaps)}\n"
            f"non_blocking_gaps 详情：{_json_compact_dump(non_blocking_gaps)}\n\n"
            "请按以下固定 JSON 格式输出：\n"
            "{\n"
            '  "candidate_plans": [\n'
            '    {"plan_id": "direct|strict|enhanced|complete|quick|narrow", "plan_name": "...", "description": "...", "required_new_skills": [...], "estimated_effort": "高|中|低", "risk": "...", "gap_summary": "该方案的数据覆盖情况说明", "feasibility": "实现可行性说明，包括能否实现、困难和补齐方式", "recommended": true|false}\n'
            '  ],\n'
            '  "recommended_plan_id": "...",\n'
            '  "pending_question": "..."\n'
            "}"
        )

        plan_data = None
        try:
            db = get_mongo_db()
            from app.services.intelligent_assistant_service import get_reasoning_llm_config
            from core.llm import UnifiedLLMClient
            from core.llm.models import Message

            config = await get_reasoning_llm_config(db)
            if not config:
                raise ValueError("系统中未找到可用的默认推理模型配置")
            client = UnifiedLLMClient.from_config(config)

            messages = [
                Message(role="system", content=system_prompt),
                Message(role="user", content=user_prompt),
            ]
            response = await client.achat(messages, temperature=0.3, max_tokens=4000)
            raw_content = str(response.content or "").strip()

            # 尝试从 markdown 代码块中提取 JSON
            plan_payload = _extract_json_from_markdown(raw_content) or raw_content
            try:
                plan_data = json.loads(plan_payload)
            except Exception as exc:
                logger.warning("[ProposePlans][ParseFailed] raw=%s exc=%s", raw_content[:500], exc)
        except Exception as exc:
            logger.warning("[ProposePlans][LLMFallback] using rule-based plans because llm failed: %s", exc, exc_info=True)

        if not isinstance(plan_data, dict):
            plan_data = _fallback_build_plans(blocking_gaps, non_blocking_gaps)

        candidate_plans = plan_data.get("candidate_plans") or []
        recommended_plan_id = str(plan_data.get("recommended_plan_id") or "").strip()
        if not candidate_plans:
            candidate_plans = _fallback_build_plans(blocking_gaps, non_blocking_gaps).get("candidate_plans", [])
        if not recommended_plan_id:
            recommended_plan_id = candidate_plans[0].get("plan_id") if candidate_plans else "direct"

        # 规范每个 plan 的字段
        normalized_plans = []
        for p in candidate_plans:
            plan_id = str(p.get("plan_id") or "").strip()
            if not plan_id:
                continue
            normalized_plans.append({
                "plan_id": plan_id,
                "plan_name": str(p.get("plan_name") or _humanize_plan_id(plan_id)),
                "description": str(p.get("description") or ""),
                "required_new_skills": _to_str_list(p.get("required_new_skills")),
                "estimated_effort": str(p.get("estimated_effort") or "中"),
                "risk": str(p.get("risk") or ""),
                "gap_summary": str(p.get("gap_summary") or ""),
                "feasibility": str(p.get("feasibility") or ""),
                "recommended": bool(p.get("recommended", False)),
            })

        # 安全网：LLM 仍然只返回一套时，按规则补齐到可比较方案，避免方案选择阶段退化成单选。
        min_expected = 3 if len(blocking_gaps) == 0 else 2
        if len(normalized_plans) < min_expected:
            fallback_plans = _fallback_build_plans(blocking_gaps, non_blocking_gaps).get("candidate_plans", [])
            seen_plan_ids = {str(p.get("plan_id") or "").strip() for p in normalized_plans}
            for fallback_plan in fallback_plans:
                fallback_plan_id = str(fallback_plan.get("plan_id") or "").strip()
                if not fallback_plan_id or fallback_plan_id in seen_plan_ids:
                    continue
                normalized_plans.append({
                    "plan_id": fallback_plan_id,
                    "plan_name": str(fallback_plan.get("plan_name") or _humanize_plan_id(fallback_plan_id)),
                    "description": str(fallback_plan.get("description") or ""),
                    "required_new_skills": _to_str_list(fallback_plan.get("required_new_skills")),
                    "estimated_effort": str(fallback_plan.get("estimated_effort") or "中"),
                    "risk": str(fallback_plan.get("risk") or ""),
                    "gap_summary": str(fallback_plan.get("gap_summary") or ""),
                    "feasibility": str(fallback_plan.get("feasibility") or ""),
                    "recommended": bool(fallback_plan.get("recommended", False)),
                })
                seen_plan_ids.add(fallback_plan_id)
                if len(normalized_plans) >= min_expected:
                    break

        if recommended_plan_id not in {p.get("plan_id") for p in normalized_plans}:
            fallback_recommended = str(_fallback_build_plans(blocking_gaps, non_blocking_gaps).get("recommended_plan_id") or "").strip()
            recommended_plan_id = fallback_recommended or (normalized_plans[0].get("plan_id") if normalized_plans else "direct")

        # 确保 recommended 标志与 recommended_plan_id 一致
        for p in normalized_plans:
            p["recommended"] = (p["plan_id"] == recommended_plan_id)

        pending_question = str(plan_data.get("pending_question") or "你希望采用哪个方案？").strip()

        # 更新意图上下文：等待用户选择方案
        pending_options = [
            {
                "index": i + 1,
                "id": p["plan_id"],
                "name": p["plan_name"],
                "description": p["description"],
                "recommended": bool(p.get("recommended")),
                "acknowledged_gaps": blocking_gaps if p["plan_id"] in {"complete", "quick"} else [],
                "gap_summary": p.get("gap_summary", ""),
                "feasibility": p.get("feasibility", ""),
            }
            for i, p in enumerate(normalized_plans)
        ]
        _auto_update_intent(
            action="create_agent",
            stage="plan_selection_pending",
            intent_summary="等待用户选择 Agent 构建方案",
            pending_options=pending_options,
            proposed_items=[{"index": i + 1, "id": p["plan_id"], "name": p["plan_name"]} for i, p in enumerate(normalized_plans)],
            pending_question=pending_question,
            active_subtask="等待用户选择方案",
            next_action="用户选择方案后调用 generate_confirmed_candidate_agent，传入 selected_plan_id 与 acknowledged_gaps",
        )

        logger.info(
            "[ProposePlans][Output] plan_count=%d recommended=%s blocking_gaps=%d pending_options=%d option_ids=%s",
            len(normalized_plans),
            recommended_plan_id,
            len(blocking_gaps),
            len(pending_options),
            [opt.get("id") for opt in pending_options],
        )

        return _json_response({
            "status": "ok",
            "candidate_plans": normalized_plans,
            "recommended_plan_id": recommended_plan_id,
            "pending_question": pending_question,
            "pending_options": pending_options,
            "nanobot_guidance": (
                "你现在是财经产品专家。向用户展示方案时：\n"
                "1. 用业务语言解释每个方案的区别。\n"
                "2. 不要暴露 direct/strict/enhanced/complete/quick/narrow 等内部代号。\n"
                "3. 明确说明各方案在交付范围、保守程度、是否补能力、是否扩展增强上的区别。\n"
                "4. 用户回复「选 A」「按推荐的来」「确认」等任意认可表述，"
                "就视为已选择 recommended_plan_id，直接调用 generate_confirmed_candidate_agent。"
            ),
        })
    except Exception as exc:
        logger.error("生成候选方案失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"生成候选方案失败: {exc}"})


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
        "当需要先确认仓库里已有哪类能力，再决定如何设计或创建新 Agent 时使用。"
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
    data_source_handling="local_only",
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
        "当需要确认项目里是否已经存在数据库驱动的专用 Agent，"
        "或判断某个能力是否可以通过 UniversalAgent + agent_configs 直接承载时使用。"
    ),
    when_not_to_use="不适合执行 Agent，也不适合搜索通用工具能力；它只看数据库里的运行时 Agent 定义。",
    returns=(
        "返回 JSON 字符串，包含 runtime_mode、effective_tools、output_field、metadata、"
        "以及该配置是否覆盖了内置蓝图。"
    ),
    example="inspect_runtime_agent_configs(keyword='估值', limit=5)",
    related_tools=["inspect_agent_workshop_assets", "inspect_agent_blueprints", "search_project_capabilities"],
    data_source_handling="local_only",
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
                "docs/05-design/v3.0/ai-workflow-generation.md",
                "docs/05-design/v3.0/agent-workshop-interface-sequence.md",
                "docs/05-design/v3.0/implementation-status-report.md",
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
        "当需要判断应该复用哪个现有 Agent 模式时使用。"
        "适合先按关键词、分类或维护状态筛选，再决定读哪一个实现。"
    ),
    when_not_to_use="不适合直接输出最终实现代码。它提供的是现有 Agent 的结构化蓝图摘要。",
    returns=(
        "返回 JSON 字符串，包含 agent_id、description、tools、default_tools、inputs、outputs、"
        "callable_surfaces、maintenance_status 等元数据。"
    ),
    example="inspect_agent_blueprints(keyword='估值', category='analyst', limit=5)",
    related_tools=["get_agent_blueprint_details", "search_project_capabilities"],
    data_source_handling="local_only",
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
        "当已经通过 inspect_agent_blueprints 找到候选 Agent，"
        "需要进一步确认输入输出、默认工具、依赖关系和调用面时使用。"
    ),
    when_not_to_use="不适合用来搜索能力集合；先筛选候选，再看详情。",
    returns="返回 JSON 字符串，包含单个 Agent 的完整元数据详情。",
    example="get_agent_blueprint_details(agent_id='valuation_analyst_v2')",
    related_tools=["inspect_agent_blueprints", "search_project_capabilities"],
    data_source_handling="local_only",
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
        "当需要确认是否已有接近需求的 Agent 规格、已构建版本或提示词资产时使用。"
        "适合在决定新建前先看已有配置式资产，或在当前线程已知 workshop_session_id/spec_id/version_id 时先做精确核验。"
        "**重要**：在 agent_workshop 渠道下，若当前线程有选中的 Agent（thread_context 含 spec_id/version_id），"
        "且调用时未指定任何过滤参数，本工具将自动仅返回当前选中 Agent 的资产，而非全量搜索。"
        "若确实需要查看全部资产，请显式传入 keyword='' 或其他过滤参数。"
    ),
    when_not_to_use="不适合做通用工具搜索，也不适合直接发布 Agent；它只汇总工坊资产摘要。",
    returns=(
        "返回 JSON 字符串，包含 spec 摘要、version 摘要、required_tools、required_capabilities、"
        "prompt_template_ref 等信息，以及本次使用或解析后的精确过滤条件。"
    ),
    example="inspect_agent_workshop_assets(workshop_session_id='session_001')",
    related_tools=["inspect_runtime_agent_configs", "inspect_agent_blueprints", "search_project_capabilities"],
    data_source_handling="local_only",
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

        # 🔥 自动使用线程上下文：当没有显式过滤参数时，使用当前线程的 spec_id/version_id
        has_explicit_filters = bool(
            clean_keyword
            or clean_workshop_session_id
            or clean_spec_id
            or clean_version_id
            or clean_agent_id
        )
        if not has_explicit_filters:
            # 优先使用 EmbededNanobotService.chat() 传入并写入 contextvar 的 thread_context
            thread_context = get_current_assistant_thread_context()
            context_spec_id = str(thread_context.get("spec_id") or "").strip()
            context_version_id = str(thread_context.get("version_id") or "").strip()
            if not context_spec_id and not context_version_id:
                # contextvar 没有 → 回退到 DB 查 embedded_nanobot_threads
                current_thread_id = get_current_assistant_thread_id()
                if current_thread_id:
                    try:
                        threads_collection = _get_collection(db, "embedded_nanobot_threads")
                        if threads_collection is not None:
                            thread_doc = await threads_collection.find_one(
                                {"$or": [{"thread_id": current_thread_id}, {"session_key": current_thread_id}]}
                            )
                            if thread_doc:
                                thread_context2 = dict(thread_doc.get("thread_context") or {})
                                context_spec_id = str(thread_context2.get("spec_id") or "").strip()
                                context_version_id = str(thread_context2.get("version_id") or "").strip()
                    except Exception as ctx_exc:
                        logger.debug("自动读取线程上下文失败，继续使用无过滤模式: %s", ctx_exc)
            if context_spec_id:
                clean_spec_id = context_spec_id
                logger.info(
                    "[AgentWorkshop][ThreadContextFilter] auto spec_id=%s (from thread_context contextvar or DB)",
                    context_spec_id,
                )
                # 🔥 自动设置意图上下文
                _auto_update_intent(
                    action="check_status",
                    stage="",
                    spec_id=context_spec_id,
                    spec_name=str(thread_context.get("spec_name") or "").strip() or context_spec_id,
                    intent_summary="查看当前 Agent 的进度和状态",
                )
            if context_version_id:
                clean_version_id = context_version_id
                logger.info(
                    "[AgentWorkshop][ThreadContextFilter] auto version_id=%s (from thread_context contextvar or DB)",
                    context_version_id,
                )
            if not clean_spec_id and not clean_version_id:
                logger.info(
                    "[AgentWorkshop][ThreadContextFilter] no spec_id/version_id in thread_context, returning unfiltered results"
                )

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
                        "docs/05-design/v3.0/agent-workshop-interface-sequence.md",
                        "docs/05-design/v3.0/implementation-status-report.md",
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

        # 🔥 批量获取每个版本的最新评估数据，避免 Nanobot 依赖 stale 对话记忆
        await _merge_latest_evaluations_into_versions(version_results, db)

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
                "docs/05-design/v3.0/agent-workshop-interface-sequence.md",
                "docs/05-design/v3.0/implementation-status-report.md",
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
    when_to_use="当需要确认数据库中有哪些提示词模板、某个 Agent 当前绑定了哪些模板，或要查模板资产时使用。",
    when_not_to_use="不适合直接修改模板正文；只做读取和筛选。",
    returns="返回 JSON 字符串，包含模板摘要列表。",
    example="inspect_prompt_templates(agent_type='universal', keyword='估值', status='active', limit=10)",
    related_tools=["get_prompt_template_detail", "inspect_agent_workshop_assets", "create_or_update_universal_agent_prompt_template"],
    data_source_handling="local_only",
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
        cursor = templates.find({}, {"_id": 1, "agent_type": 1, "agent_name": 1, "template_name": 1, "workflow_id": 1, "node_id": 1, "status": 1, "is_system": 1, "remark": 1, "updated_at": 1, "version": 1})
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
    when_to_use="当已经知道 template_id，需要查看完整 system_prompt、tool_guidance、output_format 等正文时使用。",
    when_not_to_use="不适合模糊搜索模板列表；那种场景应先使用 inspect_prompt_templates。",
    returns="返回 JSON 字符串，包含模板详情和完整 content 字段。",
    example="get_prompt_template_detail(template_id='69cfdf8db1828a17f6b00cfb')",
    related_tools=["inspect_prompt_templates", "create_or_update_universal_agent_prompt_template"],
    data_source_handling="local_only",
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

        cursor = templates.find({})
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
    data_source_handling="local_only",
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
    description="基于当前线程上下文自动推断当前正在调试或讨论的 Agent 版本，再解析该上下文下实际生效的提示词模板。",
    category="assistant_ops",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    when_to_use="当用户问当前线程里现在实际命中了哪份模板，且上下文已经在当前会话中时优先使用。",
    when_not_to_use="不适合做模板库浏览；那种场景应先使用 inspect_prompt_templates。",
    returns="返回 JSON 字符串，包含线程上下文、自动推断得到的 resolution_input 和实际生效模板内容。",
    example="get_current_thread_effective_prompt_template()",
    related_tools=["get_effective_prompt_template", "inspect_prompt_templates", "get_prompt_template_detail"],
    data_source_handling="local_only",
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
    description="创建一个可运行的 UniversalAgent 候选配置，写入 agent_configs，作为最小生成链的第一步。",
    category="assistant_ops",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    when_to_use="当已经确认要生成一个新的配置式 Agent 候选，并准备把最小运行时定义写入数据库时使用。",
    when_not_to_use="不适合做资源侦察，也不适合直接绑定工具或写提示词模板。",
    returns="返回 JSON 字符串，包含写入后的 agent_configs 摘要。",
    example="create_or_update_runtime_agent_config(agent_id='valuation_candidate_v1', agent_name='估值候选Agent', description='输出估值结论')",
    related_tools=["create_or_update_universal_agent_prompt_template", "bind_agent_tools_and_validate_candidate"],
    data_source_handling="local_only",
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
    description="把已确认的候选 Agent 同步到 Agent 工坊 Draft 资产层，使其在工坊列表中可见并可继续做版本治理。",
    category="assistant_ops",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    when_to_use="当已经确认了候选 Agent 的职责、输出和工具范围，希望把它沉淀为 Agent 工坊 Draft 而不是只停留在运行时候选时使用。",
    when_not_to_use="不适合直接做版本发布，也不适合在需求尚未确认时调用。",
    returns="返回 JSON 字符串，包含写入后的 spec_id、session_id 和概览信息。",
    example="create_or_update_agent_workshop_draft(agent_id='valuation_candidate_v1', agent_name='估值候选Agent', target_responsibility='输出A股估值结论')",
    related_tools=["generate_confirmed_candidate_agent", "inspect_agent_workshop_assets", "create_or_update_runtime_agent_config"],
    data_source_handling="local_only",
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

        # 🔥 防止 LLM 意图漂移：对比 agent_id 与当前线程上下文的 spec_id
        thread_context_spec_id = _get_current_thread_context_spec_id()
        # 🔑 关键追踪日志：IntentGuard 检查
        logger.info(
            "[WorkshopDraft][IntentGuard] thread_context.spec_id=%r tool_arg.agent_id=%r equivalent=%s",
            thread_context_spec_id, clean_agent_id,
            _agent_id_equivalent(thread_context_spec_id, clean_agent_id) if thread_context_spec_id else "N/A(empty_ctx)",
        )
        if thread_context_spec_id and thread_context_spec_id != clean_agent_id:
            if _agent_id_equivalent(thread_context_spec_id, clean_agent_id):
                logger.info(
                    "[AgentWorkshop][IntentGuard] 允许历史候选 ID 前缀差异: thread_context.spec_id='%s' tool_arg.agent_id='%s'",
                    thread_context_spec_id, clean_agent_id,
                )
                clean_agent_id = thread_context_spec_id
            else:
                existing_name = await _resolve_spec_name(db, thread_context_spec_id) or thread_context_spec_id
                logger.warning(
                    "[AgentWorkshop][IntentGuard] ⚠️ LLM 意图漂移！"
                    " thread_context.spec_id='%s' name='%s' ≠ tool_arg.agent_id='%s' agent_name='%s'",
                    thread_context_spec_id, existing_name, clean_agent_id, clean_agent_name,
                )
                return _json_response({
                    "status": "error",
                    "code": "intent_drift_detected",
                    "message": (
                        f"意图漂移检测：当前正在操作的 Agent 是 "
                        f"「{existing_name}」（{thread_context_spec_id}），"
                        f"但你传入的 agent_id 是「{clean_agent_id}」（{clean_agent_name}）。"
                        f"请使用正确的 agent_id={thread_context_spec_id} agent_name={existing_name} 重试。"
                    ),
                })

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
        # 🔑 关键追踪日志：create_nanobot_draft 写库前
        logger.info(
            "[WorkshopDraft][WriteDB] 即将调用 create_nanobot_draft agent_id=%r agent_name=%r",
            clean_agent_id, clean_agent_name,
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
        # 🔑 关键追踪日志：create_nanobot_draft 写库后
        result_status = result.get("status", "") if isinstance(result, dict) else "non_dict"
        result_spec_id = result.get("spec_id", "") if isinstance(result, dict) else ""
        result_session_id = result.get("session_id", "") if isinstance(result, dict) else ""
        logger.info(
            "[WorkshopDraft][WriteDB] create_nanobot_draft 结果 status=%s spec_id=%r session_id=%r",
            result_status, result_spec_id, result_session_id,
        )
        if result_status != "ok":
            logger.warning(
                "[WorkshopDraft][WriteDB] ❌ create_nanobot_draft 失败！full_result=%s",
                json.dumps(result, ensure_ascii=False, default=str)[:500] if isinstance(result, dict) else str(result)[:500],
            )
        # 🔥 自动更新意图上下文
        # V2 流程：需求确认后才创建 session，此时可能处于 capability_check 阶段，
        # 不应把 stage 改回 draft_preparing。
        current_stage = _get_current_intent_stage()
        if current_stage in {"capability_check", "plan_selection_pending", "requirement_confirmation_pending"}:
            next_stage = "capability_check"
            next_action = "继续执行能力盘点：search_project_capabilities + analyze_agent_workshop_gaps"
            task_status = "capability_check"
        else:
            next_stage = "draft_preparing"
            next_action = "继续执行缺口分析，若存在 blocking gap 则为当前 Agent 创建/绑定 Skill，之后回到版本构建和真数据测试"
            task_status = "draft_preparing"
        _auto_update_intent(
            action="create_agent",
            stage=next_stage,
            spec_id=clean_agent_id,
            spec_name=clean_agent_name,
            intent_summary=f"创建 Agent「{clean_agent_name}」，准备工坊草稿",
            next_action=next_action,
            task={
                "type": "agent",
                "id": clean_agent_id,
                "name": clean_agent_name,
                "status": task_status,
            },
        )
        return _json_response({**result, "status": "ok"})
    except Exception as exc:
        logger.error("创建或更新 Agent 工坊 Draft 失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"创建或更新 Agent 工坊 Draft 失败: {exc}"})


@tool
@register_tool(
    tool_id="analyze_agent_workshop_gaps",
    name="执行 Agent 工坊缺口分析",
    description="直接触发 Agent 工坊会话的缺口分析阶段，并返回结构化缺口摘要。如果没有现成 session_id，可传入 agent_id 等基本信息自动创建临时 session。",
    category="assistant_ops",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    when_to_use="当用户需求已确认，需要运行真实 gap 分析时使用。如果已有 session_id 则直接分析；如果没有，可传入 agent_id/agent_name/target_responsibility/tool_ids 自动创建 session 后再分析。",
    when_not_to_use="不适合在需求尚未确认时调用。也不适合在版本已通过 auto-build（如 generate_confirmed_candidate_agent）自动构建后调用，因为自动构建内部已执行缺口分析。如果当前处于 BUILDING 阶段，应跳过此工具，直接进入测试。",
    returns="返回 JSON 字符串，包含 session_id、spec_id 与 gap_report 摘要。",
    example="analyze_agent_workshop_gaps(session_id='session_123') 或 analyze_agent_workshop_gaps(agent_id='risk_signal_agent', agent_name='财报风险信号助手', target_responsibility='识别财报风险信号', tool_ids='tool_a,tool_b')",
    related_tools=["create_or_update_agent_workshop_draft", "search_project_capabilities", "generate_agent_workshop_tooling_plan", "build_agent_workshop_version"],
    data_source_handling="local_only",
)
async def analyze_agent_workshop_gaps(
    session_id: Annotated[str, "Agent 工坊会话 ID；如果为空，则需要提供 agent_id 等参数自动创建"] = "",
    agent_id: Annotated[str, "候选 Agent ID，session_id 为空时必填"] = "",
    agent_name: Annotated[str, "Agent 显示名称，session_id 为空时必填"] = "",
    target_responsibility: Annotated[str, "单一职责描述，session_id 为空时必填"] = "",
    tool_ids: Annotated[str, "候选工具 ID，逗号分隔，session_id 为空时使用"] = "",
) -> str:
    """执行 Agent 工坊缺口分析并返回结构化结果。"""
    try:
        clean_session_id = str(session_id or "").strip()
        clean_agent_id = str(agent_id or "").strip()
        clean_agent_name = str(agent_name or "").strip()
        clean_responsibility = str(target_responsibility or "").strip()

        db = get_mongo_db()

        # 如果没有 session_id，尝试根据 agent_id 查找或创建 session
        if not clean_session_id:
            if not clean_agent_id or not clean_agent_name or not clean_responsibility:
                return _json_response({
                    "status": "error",
                    "message": "session_id 为空时，agent_id、agent_name、target_responsibility 不能为空",
                })

            # 优先查找同一线程同 agent_id 的现有 session
            current_thread_id = (get_current_assistant_thread_id() or "").strip()
            existing_session = None
            try:
                sessions = _get_collection(db, "agent_workshop_sessions")
                if sessions is not None:
                    existing_session = await sessions.find_one(
                        {"agent_id": clean_agent_id, "source_thread_id": current_thread_id},
                        {"session_id": 1},
                        sort=[("created_at", -1)],
                    )
            except Exception:
                existing_session = None

            if existing_session and existing_session.get("session_id"):
                clean_session_id = str(existing_session["session_id"]).strip()
                logger.info("[AnalyzeGaps] 复用已有 session_id=%s agent_id=%s", clean_session_id, clean_agent_id)
            else:
                # 自动创建 draft session
                draft_result = await AgentWorkshopService(db=db).create_nanobot_draft(
                    agent_id=clean_agent_id,
                    agent_name=clean_agent_name,
                    target_responsibility=clean_responsibility,
                    output_field="analysis_report",
                    tool_ids=_parse_string_list(tool_ids),
                    runtime_contract={"required_tools": _parse_string_list(tool_ids)},
                    tooling_contract={"required_tools": _parse_string_list(tool_ids)},
                    owner_user_id="",
                    source_thread_id=current_thread_id,
                )
                clean_session_id = str(draft_result.get("session_id") or "").strip()
                if not clean_session_id:
                    return _json_response({
                        "status": "error",
                        "message": "自动创建 Agent 工坊 session 失败，无法执行缺口分析",
                    })
                logger.info("[AnalyzeGaps] 自动创建 session_id=%s agent_id=%s", clean_session_id, clean_agent_id)

        result = await AgentWorkshopService(db=db).analyze_gaps(clean_session_id)
        gap_report = result.get("gap_report") if isinstance(result, dict) else None
        # AgentWorkshopService.analyze_gaps 返回的 gap_report 是 AgentWorkshopGapAnalysis
        # Pydantic 模型对象。若直接传给 _json_response，json.dumps 的 default=str 会
        # 把它转成字符串，导致下游 node_gap_analysis 提取不到 blocking_gaps 等字段
        # （state["gap_report"] 永远为空 {}，进而 acknowledged_gaps=0，build 失败）。
        # 这里统一转成 dict，保证 JSON 序列化后仍是结构化对象。
        if gap_report is not None and not isinstance(gap_report, dict):
            if hasattr(gap_report, "model_dump"):
                gap_report = gap_report.model_dump(by_alias=True, exclude_none=False)
            elif hasattr(gap_report, "dict"):
                gap_report = gap_report.dict(by_alias=True)
            else:
                # 兜底：用 __dict__ 或 str
                gap_report = (
                    dict(getattr(gap_report, "__dict__", {}))
                    if getattr(gap_report, "__dict__", None)
                    else None
                )

        # 更新意图上下文：gap 分析完成后进入方案选择阶段
        _auto_update_intent(
            action="create_agent",
            stage="plan_selection_pending",
            spec_id=clean_agent_id,
            spec_name=clean_agent_name,
            intent_summary=f"为 Agent「{clean_agent_name}」完成能力缺口分析，等待生成候选方案",
            next_action="调用 propose_agent_build_plans 生成候选方案",
        )

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
    description="直接触发 Agent 工坊工具需求草案生成，并返回结构化工具计划。",
    category="assistant_ops",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    when_to_use="仅在需要人工诊断或单独查看工具需求草案时使用。普通 Agent 生成主流程不需要直接调用，因为 build_agent_workshop_version 和 resolve_agent_workshop_blocking_gaps 内部会自动生成/使用 tooling_plan。",
    when_not_to_use="不适合在 session_id 无效时调用；不适合在普通自动构建流程中作为必经步骤调用；不适合在 BUILDING/TESTING/PUBLISHING 阶段重复调用。",
    returns="返回 JSON 字符串，包含 session_id、spec_id 与 tooling_plan。",
    example="generate_agent_workshop_tooling_plan(session_id='session_123')",
    related_tools=["analyze_agent_workshop_gaps", "build_agent_workshop_version"],
    data_source_handling="local_only",
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
    description="直接触发 Agent 工坊版本草案生成，并返回生成后的版本信息。如果已有版本处于测试中，会返回 needs_user_decision 状态让用户选择是覆盖还是继续推进。",
    category="assistant_ops",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    when_to_use="当 Agent Draft 已生成但尚未产生测试版本（READY_TO_BUILD 阶段）时使用。该工具会在内部完成真实 gap 分析、工具计划和版本草案生成。如果返回 status=needs_user_decision，必须向用户展示旧版本信息（existing_version 中的工具列表）并询问用户选择：覆盖旧版本（用户确认后用 overwrite_existing=True 再次调用）还是继续推进旧版本（引导用户使用 iterate_agent_workshop_version 或继续测试）。",
    when_not_to_use="不适合在 session_id 缺失或规格尚未准备好时调用。用户未明确确认要覆盖时，不要传 overwrite_existing=True。",
    returns="返回 JSON 字符串。正常时包含 session_id、spec_id 和 version；已有版本时返回 status=needs_user_decision 及旧版本信息和选项。",
    example="build_agent_workshop_version(session_id='session_123')",
    related_tools=["analyze_agent_workshop_gaps", "generate_agent_workshop_tooling_plan", "iterate_agent_workshop_version"],
    data_source_handling="local_only",
)
async def build_agent_workshop_version(
    session_id: Annotated[str, "Agent 工坊会话 ID"],
    overwrite_existing: Annotated[bool, "是否覆盖已有版本（删除旧版本后重建）。仅在用户明确确认要覆盖时传 True。"] = False,
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
            current_version_id = str(phase_context.get("current_version_id") or "").strip()

            # 用户确认要覆盖旧版本：先删除旧版本再继续构建
            if overwrite_existing and current_version_id:
                svc = AgentWorkshopService(db=db)
                delete_result = await svc.delete_version(current_version_id, force=True)
                if not delete_result.get("deleted"):
                    return _json_response({
                        "status": "error",
                        "message": f"删除旧版本 {current_version_id} 失败：{delete_result.get('message', '未知原因')}",
                        "current_version_id": current_version_id,
                    })
                # 删除成功后继续执行 build_version
            else:
                # 返回"需要用户决策"的响应，让 LLM 询问用户是覆盖还是继续推进
                existing_version_summary = await _get_existing_version_summary(db, current_version_id)
                phase_label = phase_context.get("phase_label") or version_status
                response_payload = {
                    "status": "needs_user_decision",
                    "decision_type": "overwrite_or_continue",
                    "message": (
                        f"当前会话已有一个处于「{phase_label}」阶段的版本 {current_version_id}。"
                        f"请向用户展示旧版本信息，并询问用户是要覆盖旧版本（删除后重建）还是继续推进旧版本。"
                    ),
                    "existing_version": existing_version_summary,
                    "options": [
                        {
                            "label": "覆盖旧版本",
                            "description": "删除当前版本并基于最新需求重新构建（适用于工具选择或 gap 分析有误需要重建的情况）",
                            "action": "调用 build_agent_workshop_version(session_id, overwrite_existing=True)",
                        },
                        {
                            "label": "继续推进旧版本",
                            "description": "保留当前版本，按流程继续推进：先运行真数据测试，评估通过后可发布或迭代创建 v2",
                            "action": "先调用 run_agent_workshop_real_data_test 执行真数据测试；评估通过后可调用 publish_agent_workshop_version 发布，或调用 iterate_agent_workshop_version 创建 v2 版本（注意：iterate 要求版本已进入 evaluation/publish-ready/published 阶段，testing 阶段不能直接 iterate）",
                        },
                    ],
                    "current_phase": phase_context.get("phase"),
                    "current_phase_label": phase_label,
                    "session_id": clean_session_id,
                    "spec_id": phase_context.get("spec_id"),
                    "current_version_id": current_version_id,
                    "_tool_events": [
                        _build_tool_stage_event(
                            "build_agent_workshop_version.needs_user_decision",
                            "needs_user_decision",
                            f"已有版本 {current_version_id} 处于 {phase_label} 阶段，需要用户决策是否覆盖",
                        ),
                    ],
                }
                logger.info(
                    "[BuildAgent] needs_user_decision | current_version_id=%s | phase=%s | existing_version_keys=%s | options_count=%d",
                    current_version_id,
                    phase_label,
                    list(existing_version_summary.keys()) if existing_version_summary else [],
                    len(response_payload.get("options", [])),
                )
                return _json_response(response_payload)

        result = await AgentWorkshopService(db=db).build_version(clean_session_id)
        version = result.get("version") if isinstance(result, dict) else None
        # AgentWorkshopService.build_version 返回的 version 是 AgentVersion Pydantic 模型对象。
        # 若直接传给 _json_response，json.dumps 的 default=str 会把它转成 str repr
        # （形如 "id=ObjectId('...') version_id='...' spec_id='...' ..."），
        # 导致下游 node_generate_candidate_agent / node_build_or_ready 提取到的
        # version_id 是整个对象 repr 而非 version_id 字符串，进而 real_data_test /
        # publish 全部失败。这里统一转成 dict，保证 JSON 序列化后仍是结构化对象。
        if version is not None and not isinstance(version, dict):
            if hasattr(version, "model_dump"):
                version = version.model_dump(by_alias=True, exclude_none=False)
            elif hasattr(version, "dict"):
                version = version.dict(by_alias=True)
            elif hasattr(version, "__dict__") and getattr(version, "__dict__", None):
                version = dict(getattr(version, "__dict__"))
            else:
                version = {"_repr": str(version)}
        # 顶层 version_id：方便下游直接取用，避免重复嵌套解析
        top_version_id = ""
        if isinstance(version, dict):
            top_version_id = str(version.get("version_id") or "").strip()
        return _json_response({
            "status": "ok",
            "session_id": clean_session_id,
            "spec_id": result.get("spec_id") if isinstance(result, dict) else "",
            "version_id": top_version_id,
            "version": version,
            "summary": {
                "version_id": top_version_id or None,
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
    description="对指定 Agent 工坊版本执行一次真实股票样例运行，并返回调试结果；该工具不会自动写入正式评估记录。",
    category="assistant_ops",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    when_to_use="当用户明确要做调试排障、查看最近一次样例输出、诊断 Prompt 或运行时问题时使用。",
    when_not_to_use="不适合替代正式真数据测试、验收、评估落库、发布前确认，或回答为什么版本仍处于 testing。",
    returns="返回 JSON 字符串，包含 version_id、spec_id、report、raw_result 和运行元数据，但不会自动生成 evaluation 记录。",
    example="debug_agent_workshop_version(version_id='spec_x_v1', stock_symbol='600519')",
    related_tools=["run_agent_workshop_real_data_test", "publish_agent_workshop_version"],
    data_source_handling="local_only",
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
    description="对指定 Agent 工坊版本执行一次真实股票样例测试，并自动记录评估结果到 Agent Workshop。",
    category="assistant_ops",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    when_to_use="当用户要执行真数据测试、正式验收、验证是否通过、查看评估结果、确认发布前 readiness，或排查为什么版本仍停留在 testing 时使用。",
    when_not_to_use="不适合只做样式预览、只讨论方案、只想单步调试 Prompt，或还没有 version_id 时调用。",
    returns="返回 JSON 字符串，包含 debug_result、evaluation、latest_decision 和是否已完成正式落库。",
    example="run_agent_workshop_real_data_test(version_id='spec_x_v1', stock_symbol='600519')",
    related_tools=["debug_agent_workshop_version", "publish_agent_workshop_version"],
    data_source_handling="local_only",
)
async def run_agent_workshop_real_data_test(
    version_id: Annotated[str, "Agent 工坊版本 ID"],
    stock_symbol: Annotated[str, "真实股票代码，如 600519"],
    market_type: Annotated[str, "市场类型，默认 A股"] = "A股",
    analysis_date: Annotated[str, "分析日期，格式 YYYY-MM-DD，可为空"] = "",
    user_goal: Annotated[str, "本次测试目标，可为空"] = "",
    user_feedback: Annotated[str, "本次测试补充反馈，可为空"] = "",
    prompt_overrides_json: Annotated[str, "Prompt 覆盖 JSON 对象，可为空"] = "",
    skip_evaluation: Annotated[bool, "仅运行测试不评估，评估由后续单独执行"] = False,
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
        gap_tool_sync = await _auto_sync_gap_tools_to_workshop_version(db, clean_version_id)
        if gap_tool_sync.get("status") in {"synced", "unchanged"}:
            stage_events.append(_build_tool_stage_event(
                "run_agent_workshop_real_data_test.auto_sync_gap_tools",
                "ok",
                f"已同步 gap 工具到当前版本: {gap_tool_sync.get('status')}；tools={len(gap_tool_sync.get('required_tools') or [])}",
            ))
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

        # 🔑 skip_evaluation=True：仅运行测试，不做评估，评估由 node_real_data_test 后续单独执行
        if skip_evaluation:
            stage_events.append(_build_tool_stage_event(
                "run_agent_workshop_real_data_test.skip_evaluation",
                "ok",
                "测试完成，跳过评估阶段（由后续单独执行）",
            ))
            return _json_response({
                "status": "ok",
                "test_chain_status": "test_only",
                "version_id": clean_version_id,
                "spec_id": debug_result.get("spec_id"),
                "debug_result": debug_result,
                "runtime_result": runtime_result_payload,
                "user_feedback": str(user_feedback or "").strip(),
                "_tool_events": [
                    *stage_events,
                    _build_tool_stage_event(
                        "run_agent_workshop_real_data_test",
                        "ok",
                        "真数据测试完成（跳过评估）",
                    ),
                ],
                "summary": {
                    "symbol": debug_result.get("symbol"),
                    "analysis_date": debug_result.get("analysis_date"),
                    "report_length": debug_result.get("report_length"),
                },
                "message": "真数据测试已完成，测试报告已生成。评估将在下一步单独执行。",
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

        # 🔥 把评估证据写回意图上下文，供 ITERATING 阶段做细粒度路由
        publish_readiness = (_read_mapping_or_attr(evaluation, "publish_readiness", {}) or {}) if isinstance(evaluation, dict) else {}
        if isinstance(publish_readiness, dict):
            eval_blockers = [str(b).strip() for b in (publish_readiness.get("blockers") or []) if str(b).strip()]
            eval_categories = []
            details = _read_mapping_or_attr(evaluation, "details", {}) or {}
            evidence_bundle = details.get("evidence_bundle") if isinstance(details, dict) else None
            if isinstance(evidence_bundle, dict):
                for finding in (evidence_bundle.get("findings") or []):
                    if isinstance(finding, dict):
                        cat = str(finding.get("category") or "").strip()
                        if cat:
                            eval_categories.append(cat)
            if not eval_categories:
                # fallback：从 blockers 文本推断 category
                blocker_text = " ".join(eval_blockers).lower()
                if "工具" in blocker_text or "tool" in blocker_text:
                    eval_categories.append("tool_usage")
                if "输出字段" in blocker_text or "output" in blocker_text:
                    eval_categories.append("output_coverage")
                if "执行计划" in blocker_text or "execution_plan" in blocker_text:
                    eval_categories.append("execution_plan")
            _auto_update_intent(
                evaluation_decision=str(evaluation_decision or "").strip().lower(),
                evaluation_blockers=eval_blockers,
                evaluation_categories=_dedupe_string_list(eval_categories),
            )

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
    description="在用户已经手动确认发布后，将已通过最新真数据测试评估的 Agent 工坊版本发布为 active。",
    category="assistant_ops",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    when_to_use="仅当版本已经在 testing 且最新评估结论为 pass，并且用户在当前回合明确确认要发布时使用。",
    when_not_to_use="不适合在尚未完成真数据测试评估、评估未通过，或只是测试刚通过但用户尚未明确确认发布时调用。",
    returns="返回 JSON 字符串，包含发布后的版本状态与 spec_id。",
    example="publish_agent_workshop_version(version_id='spec_x_v1')",
    related_tools=["run_agent_workshop_real_data_test", "debug_agent_workshop_version"],
    data_source_handling="local_only",
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
    description="对指定 Agent 工坊版本执行一次显式评估落库，并返回最新评估结果。",
    category="assistant_ops",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    when_to_use="当版本已经处于 testing/evaluation 阶段，需要重新记录一次正式评估结论时使用。",
    when_not_to_use="不适合在 version_id 不存在、仍未进入 testing，或只是想看最近一次评估结果时调用。",
    returns="返回 JSON 字符串，包含 version_id、evaluation 和最新 decision 摘要。",
    example="evaluate_agent_workshop_version(version_id='spec_x_v1', evaluation_type='production-review', runtime_result_json='{\"output_text\":\"...\"}')",
    related_tools=["debug_agent_workshop_version", "run_agent_workshop_real_data_test", "iterate_agent_workshop_version"],
    data_source_handling="local_only",
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
        gap_tool_sync = await _auto_sync_gap_tools_to_workshop_version(db, clean_version_id)
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
        # 把 Pydantic 模型转为 dict，避免 _json_response 的 default=str 把它序列化成字符串
        # 导致前端解析时 evaluation 不是 dict，decision/scores 取不到值
        if result and "evaluation" in result:
            eval_obj = result["evaluation"]
            if hasattr(eval_obj, "model_dump"):
                result["evaluation"] = eval_obj.model_dump(mode="json")
            elif hasattr(eval_obj, "dict"):
                result["evaluation"] = eval_obj.dict()
        return _json_response({
            "status": "ok",
            **(result or {}),
            "_tool_events": [
                *([
                    _build_tool_stage_event(
                        "evaluate_agent_workshop_version.auto_sync_gap_tools",
                        "ok",
                        f"已同步 gap 工具到当前版本: {gap_tool_sync.get('status')}；tools={len(gap_tool_sync.get('required_tools') or [])}",
                    )
                ] if gap_tool_sync.get("status") in {"synced", "unchanged"} else []),
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
    description="基于指定 Agent 工坊版本发起下一轮迭代，并创建新的 Session。",
    category="assistant_ops",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    when_to_use="当版本已经进入 evaluation / publish-ready / published，需要基于已有结论开始下一轮时使用。",
    when_not_to_use="不适合在还没完成测试评估或仍处于 generation/testing 初期时调用。",
    returns="返回 JSON 字符串，包含 source_version_id、session_id、spec_id 和 ai_message。",
    example="iterate_agent_workshop_version(version_id='spec_x_v1', feedback='补充解释评分波动来源')",
    related_tools=["evaluate_agent_workshop_version", "build_agent_workshop_version", "publish_agent_workshop_version"],
    data_source_handling="local_only",
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
    when_to_use="当已决定创建配置式 Agent 候选，并需要让该 Agent 在运行时读取到可用提示词时使用。",
    when_not_to_use="不适合做工具绑定或能力侦察。",
    returns="返回 JSON 字符串，包含写入后的 prompt_templates 摘要。",
    example="create_or_update_universal_agent_prompt_template(agent_id='valuation_candidate_v1', template_name='估值候选模板', system_prompt='你是一名估值分析师')",
    related_tools=["create_or_update_runtime_agent_config", "bind_agent_tools_and_validate_candidate"],
    data_source_handling="local_only",
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
    when_to_use="当已写入 agent_configs 和提示词模板，准备绑定工具并确认候选 Agent 是否能被运行时正常创建时使用。",
    when_not_to_use="不适合用来搜索资源或生成提示词。",
    returns="返回 JSON 字符串，包含绑定后的工具列表、提示词模板存在性和干运行校验结果；结果仅代表运行时候选可实例化，不代表 Workshop 版本已生成或已通过正式验收。",
    example="bind_agent_tools_and_validate_candidate(agent_id='valuation_candidate_v1', tool_ids='get_value_factor_bundle_tool,get_peer_comparison')",
    related_tools=["create_or_update_runtime_agent_config", "create_or_update_universal_agent_prompt_template"],
    data_source_handling="local_only",
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
    name="确认方案后生成候选 Agent",
    description="在用户明确选择方案后，一次性完成配置写入、提示词模板写入、工具绑定和干运行校验；若已同步到 Agent Workshop Draft，则默认自动生成一个测试版本。V2 流程中必须传入 selected_plan_id、acknowledged_gaps 和 gap_report_json，避免执行阶段重复做缺口分析。",
    category="assistant_ops",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    when_to_use="当已完成需求确认、能力盘点、方案选择，并拿到用户明确的方案选择后，用一次调用生成候选 Agent。",
    when_not_to_use="未选择方案前不要调用；也不适合做资源侦察或缺口分析。",
    returns="返回 JSON 字符串，包含三步写入结果、最终干运行校验结果、可选的自动 version 生成结果，以及与 Agent Workshop 正式验收边界相关的治理提示。",
    example="generate_confirmed_candidate_agent(agent_id='valuation_candidate_v1', agent_name='估值候选Agent', target_responsibility='输出A股估值结论', tool_ids='get_value_factor_bundle_tool', system_prompt='你是一名估值分析师', selected_plan_id='complete', acknowledged_gaps='[\"financial_ratio_calculator\"]', gap_report_json='{...}')",
    related_tools=["propose_agent_build_plans", "bind_agent_tools_and_validate_candidate", "resolve_agent_workshop_blocking_gaps"],
    data_source_handling="local_only",
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
    selected_plan_id: Annotated[str, "用户选择的方案 ID：direct/strict/enhanced/complete/quick/narrow；为空时兼容旧确认流程"] = "",
    acknowledged_gaps: Annotated[str, "用户已知晓并接受的 blocking gaps，JSON 数组或逗号分隔；旧流程可为空"] = "",
    capability_inventory_json: Annotated[str, "prepare 阶段能力盘点 JSON，可为空"] = "",
    gap_report_json: Annotated[str, "prepare 阶段 analyze_spec_gaps 返回的 gap_report JSON。complete/quick 方案时必须传递；direct 方案可为空"] = "",
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
        clean_selected_plan_id = str(selected_plan_id or "").strip().lower()
        parsed_acknowledged_gaps = _parse_acknowledged_gaps(acknowledged_gaps)
        capability_inventory = _parse_optional_json_object(capability_inventory_json, "capability_inventory_json")
        gap_report = _parse_optional_json_object(gap_report_json, "gap_report_json")
        # ── 🔍 关键追踪日志：记录 LLM 传入的所有参数 ──
        logger.info(
            "[GenAgent][Params] agent_id=%s plan=%s acknowledged_gaps=%d gap_report_keys=%s gap_report_json_size=%d "
            "capability_inventory_size=%d selected_plan_id_raw=%r",
            clean_agent_id,
            clean_selected_plan_id,
            len(parsed_acknowledged_gaps),
            sorted(gap_report.keys()) if gap_report else [],
            len(str(gap_report_json or "")),
            len(str(capability_inventory_json or "")),
            str(selected_plan_id or "")[:120],
        )
        for i, item in list(enumerate(parsed_acknowledged_gaps))[:10]:
            logger.info("[GenAgent][Params]   acknowledged_gaps[%d] = %s", i, item[:200])
        for i, item in list(enumerate(gap_report.get("blocking_gaps") or []))[:10]:
            _desc = _gap_item_to_text(item)
            logger.info("[GenAgent][Params]   gap_report.blocking_gaps[%d] = %s", i, _desc[:200])
        if clean_selected_plan_id in {"complete", "quick"} and not gap_report:
            logger.warning(
                "[GenAgent][Params] ⚠️ %s 方案但 gap_report_json 为空！build_version 将尝试从 builder_contracts 恢复",
                clean_selected_plan_id,
            )
        if clean_selected_plan_id == "narrow":
            _auto_update_intent(
                action="create_agent",
                stage="exploring",
                spec_id=clean_agent_id,
                spec_name=clean_agent_name,
                intent_summary=f"Agent「{clean_agent_name}」选择缩小需求范围",
                next_action="回到需求重定义，先缩小目标/输出范围后重新做能力盘点与方案确认",
                task={"type": "agent", "id": clean_agent_id, "name": clean_agent_name, "status": "exploring"},
                clear_pending_options=True,
            )
            return _json_response({
                "status": "ok",
                "agent_id": clean_agent_id,
                "selected_plan_id": "narrow",
                "next_stage": "exploring",
                "message": "已按 narrow 方案回到需求重定义。本方案不会直接生成 Agent，请先缩小范围后重新能力盘点。",
            })
        if clean_selected_plan_id not in {"", "direct", "strict", "enhanced", "complete", "quick"}:
            return _json_response({"status": "error", "message": "selected_plan_id 只支持 direct/strict/enhanced/complete/quick/narrow"})
        if clean_selected_plan_id == "quick":
            quick_constraint = _quick_plan_constraint_text(parsed_acknowledged_gaps)
            constraints = _append_trading_guard_constraint(f"{constraints}\n{quick_constraint}")
            tool_guidance = f"{tool_guidance}\n{quick_constraint}"
            analysis_requirements = f"{analysis_requirements}\n{quick_constraint}"
            output_format = f"{output_format}\n必须对缺失字段标注信息缺口，不输出综合四色评级。"
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
            workshop_constraints = constraints
            if clean_selected_plan_id == "quick" and _quick_plan_constraint_text(parsed_acknowledged_gaps) not in workshop_constraints:
                workshop_constraints = f"{workshop_constraints}\n{_quick_plan_constraint_text(parsed_acknowledged_gaps)}"
            # 🔑 关键追踪日志：写库前打印 agent_id 和 agent_name
            logger.info(
                "[GenAgent][WriteDraft] 即将调用 create_or_update_agent_workshop_draft "
                "agent_id=%r agent_name=%r responsibility=%r",
                clean_agent_id, clean_agent_name, clean_responsibility[:80],
            )
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
                "preferred_methods": "quick_plan" if clean_selected_plan_id == "quick" else "",
                "constraints": workshop_constraints,
            }))
            # 🔑 关键追踪日志：写库结果
            logger.info(
                "[GenAgent][WriteDraft] 结果 status=%s spec_id=%r session_id=%r message=%s",
                workshop_result.get("status", ""),
                workshop_result.get("spec_id", ""),
                workshop_result.get("session_id", ""),
                str(workshop_result.get("message", ""))[:200],
            )
            if workshop_result.get("status") != "ok":
                logger.warning(
                    "[GenAgent][WriteDraft] ❌ workshop_draft 失败！agent 不会写入数据库。full_result=%s",
                    json.dumps(workshop_result, ensure_ascii=False)[:500],
                )
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

        # 🔑 只有不同步到 Workshop 时才单独创建通用模板
        # 同步到 Workshop 时，Workshop 会在构建版本时创建版本模板，并同步短名配置的模板绑定
        # 避免生成两套重复的模板
        prompt_result = {"status": "ok", "message": "skipped (workshop manages templates)"}
        if not sync_to_workshop_draft:
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
            workshop_session_id = str(workshop_result.get("session_id") or "").strip()
            builder_contracts_patch = {
                "selected_plan_id": clean_selected_plan_id or "legacy_confirmed",
                "acknowledged_gaps": parsed_acknowledged_gaps,
            }
            if capability_inventory:
                builder_contracts_patch["capability_inventory"] = capability_inventory
            if gap_report:
                builder_contracts_patch["gap_report"] = gap_report
            if clean_selected_plan_id == "quick":
                builder_contracts_patch["quick_plan_constraints"] = _quick_plan_constraint_text(parsed_acknowledged_gaps)
            sessions = _get_collection(db, "agent_workshop_sessions")
            if sessions is not None and workshop_session_id:
                await sessions.update_one(
                    {"session_id": workshop_session_id},
                    {"$set": {
                        "builder_contracts.selected_plan_id": builder_contracts_patch["selected_plan_id"],
                        "builder_contracts.acknowledged_gaps": parsed_acknowledged_gaps,
                        "builder_contracts.capability_inventory": capability_inventory,
                        "builder_contracts.gap_report": gap_report,
                        "builder_contracts.quick_plan_constraints": builder_contracts_patch.get("quick_plan_constraints", ""),
                        "gap_report": gap_report if gap_report else None,
                        "updated_at": _utc_now_iso(),
                    }},
                    upsert=False,
                )
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
        should_auto_build_workshop_version = (
            auto_build_workshop_version
            and not (clean_selected_plan_id == "complete" and bool(parsed_acknowledged_gaps))
            and clean_selected_plan_id != "quick"  # quick 方案已接受缺口，跳过 auto-build
        )
        # ── 🔍 追踪日志：auto-build 决策 ──
        logger.info(
            "[GenAgent][AutoBuild] should_auto=%s plan=%s has_gaps=%s gap_report_keys=%s session_id=%s",
            should_auto_build_workshop_version,
            clean_selected_plan_id,
            bool(parsed_acknowledged_gaps),
            sorted(gap_report.keys()) if gap_report else [],
            str(workshop_result.get("session_id") or "") if isinstance(workshop_result, dict) else "N/A",
        )
        # 安全网：complete/quick 方案下，若 gap_report 未传入，禁止 auto-build
        # 否则 build_version 会重新运行 analyze_spec_gaps，产生不一致的 blocking_gap 文本，
        # 导致 acknowledged_gaps 无法匹配而错误阻断
        if clean_selected_plan_id in {"complete", "quick"} and not gap_report:
            logger.warning(
                "[GenAgent] gap_report_json 未传入但为 %s 方案，跳过 auto-build session_id=%s",
                clean_selected_plan_id,
                str(workshop_result.get("session_id") or "").strip(),
            )
            should_auto_build_workshop_version = False
        if should_auto_build_workshop_version and sync_to_workshop_draft and isinstance(workshop_result, dict):
            workshop_session_id = str(workshop_result.get("session_id") or "").strip()
            if workshop_session_id:
                workshop_version_result = await _auto_build_workshop_version_result(workshop_session_id)
                if workshop_version_result.get("status") != "ok":
                    error_message = str(workshop_version_result.get("message") or workshop_version_result.get("error") or "")
                    likely_gap_blocked = any(
                        marker in error_message.lower()
                        for marker in ("blocking", "gap", "缺口", "阻断")
                    )
                    _auto_update_intent(
                        action="create_agent",
                        stage="gap_resolving" if likely_gap_blocked else "ready_to_build",
                        spec_id=clean_agent_id,
                        spec_name=clean_agent_name,
                        intent_summary=f"Agent「{clean_agent_name}」已生成，但自动构建未通过",
                        next_action=(
                            "解释自动构建发现的 blocking gap，并在用户确认后调用 resolve_agent_workshop_blocking_gaps"
                            if likely_gap_blocked
                            else "检查构建失败原因，修复后重新调用 build_agent_workshop_version"
                        ),
                        task={
                            "type": "agent",
                            "id": clean_agent_id,
                            "name": clean_agent_name,
                            "status": "gap_resolving" if likely_gap_blocked else "ready_to_build",
                        },
                    )
                    return _json_response({"status": "error", "stage": "workshop_version", "result": workshop_version_result})
                built_version = workshop_version_result.get("version")
                if isinstance(built_version, dict):
                    built_version_id = str(built_version.get("version_id") or "").strip()
                else:
                    built_version_id = str(built_version or "").strip()
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
            "version_id": _extract_governance_version_id(workshop_version_result),
            "selected_plan_id": clean_selected_plan_id or "legacy_confirmed",
            "acknowledged_gaps": parsed_acknowledged_gaps,
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

        # 🔥 自动更新意图上下文为"生成完成"
        #    auto-build 成功: building = 版本已构建，准备测试
        #    未 auto-build: ready_to_build = Draft 已生成，待构建版本
        #    quick 方案: building = 缺口已接受，可直接测试（跳过 auto-build）
        built_workshop_version = bool((workshop_version_result or {}).get("version"))
        if clean_selected_plan_id == "complete" and parsed_acknowledged_gaps and not built_workshop_version:
            next_stage = "gap_resolving"
            next_action_text = "按已确认 complete 方案补齐 blocking gaps，完成后再构建测试版本"
            task_status = "gap_resolving"
        elif clean_selected_plan_id == "quick":
            next_stage = "building"
            next_action_text = "简化版 Agent 已生成，缺口已确认接受；下一步直接运行真数据测试（run_agent_workshop_real_data_test）"
            task_status = "building"
        elif built_workshop_version:
            next_stage = "building"
            next_action_text = "按已确认方案已生成测试版本；下一步运行真数据测试（run_agent_workshop_real_data_test）"
            task_status = "building"
        else:
            next_stage = "ready_to_build"
            next_action_text = "按已确认方案已生成 Draft；下一步调用 build_agent_workshop_version 生成测试版本"
            task_status = "ready_to_build"
        _auto_update_intent(
            action="create_agent",
            stage=next_stage,
            spec_id=clean_agent_id,
            spec_name=clean_agent_name,
            intent_summary=f"Agent「{clean_agent_name}」已按 {clean_selected_plan_id or 'legacy'} 方案生成",
            next_action=next_action_text,
            clear_pending_options=True,
            task={
                "type": "agent",
                "id": clean_agent_id,
                "name": clean_agent_name,
                "status": task_status,
            },
        )

        return _json_response({
            "status": "ok",
            "agent_id": clean_agent_id,
            "nanobot_guidance": (
                "候选 Agent 已生成成功。请向用户简洁汇报生成结果，以业务价值为主。\n\n"
                "回复规则：\n"
                "1. 说明 Agent 名称、核心职责、输出什么报告即可。\n"
                "2. 可以简要介绍报告结构（几个章节分别讲什么），帮用户建立预期。\n"
                "3. 【禁止】罗列「可用路径 / 调用入口 / Assistant / Workflow / Agent Workshop」等技术接入方式——用户不关心从哪里调用，这是平台内部的事。\n"
                "4. 【禁止】展示 Agent ID、执行顺序、运行模式、输出字段名等技术元数据。\n"
                "5. 工具名可以在「已绑定能力」里用业务语言简述（如「同业估值对比、历史分位、DCF估值」），但不要写 get_xxx 这种函数名。\n"
                "6. 结尾自然引导用户进入下一步：可以用真实股票代码跑一次测试验证效果（如「要不要用 600519 试跑一次？」）。"
            ),
            "confirmation": {
                "confirmed": confirmed,
                "allow_overwrite": allow_overwrite,
                "selected_plan_id": clean_selected_plan_id or "legacy_confirmed",
                "acknowledged_gaps": parsed_acknowledged_gaps,
                "execution_message": "已按用户在 prepare 阶段确认的方案执行，本次不再重新要求确认缺口分析。",
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
                "selected_plan_id": clean_selected_plan_id or "legacy_confirmed",
                "acknowledged_gaps": parsed_acknowledged_gaps,
                "next_stage": next_stage,
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
                        if clean_selected_plan_id != "quick"
                        else "简化版 Agent 已跳过 Workshop 版本构建（缺口已确认接受）。可直接运行真数据测试，或手动调用 build_agent_workshop_version 生成版本。"
                    ),
                    "即使已自动生成测试版本，也必须先完成记录在 Agent Workshop 中的样例真数据测试评估，并以最新评估结论作为发布依据。"
                    if workshop_governance["version_generated"]
                    else "简化版 Agent 可直接用 run_agent_workshop_real_data_test 进行真数据测试；测试通过后再评估是否发布。"
                    if clean_selected_plan_id == "quick"
                    else "即使已自动生成测试版本，也必须先完成记录在 Agent Workshop 中的样例真数据测试评估，并以最新评估结论作为发布依据。",
                ],
            },
        })
    except Exception as exc:
        logger.error("确认后生成候选 Agent 失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"确认后生成候选 Agent 失败: {exc}"})


@tool
@register_tool(
    tool_id="resolve_agent_workshop_blocking_gaps",
    name="补全 Agent 工坊能力缺口",
    description="当缺口分析发现 blocking_gaps 时，自动为每个缺口创建 Skill 生成会话并等待完成，返回可绑定的新能力。",
    category="assistant_ops",
    is_online=True,
    auto_register=True,
    timeout_tier="heavy",
    when_to_use=(
        "当发现 blocking_gaps（来源不限：auto-build 的 gap_report、analyze_agent_workshop_gaps 返回值、或评估反馈），"
        "且这些缺口确实是可复用能力时使用。"
        "无需手动逐个调用 Skill 创建工具，一个调用即可完成缺口补全。"
    ),
    when_not_to_use=(
        "不适合在缺口尚未明确时调用（先确认 blocking_gaps 存在）；"
        "不适合一次性补全过多（>3 个）缺口，那种情况建议分批处理；"
        "不适合在没有 gap 的 TESTING 或 PUBLISHING 阶段调用。"
    ),
    returns="返回 JSON 字符串，包含每个缺口的处理结果、生成的 Skill 信息，以及后续建议。",
    example="resolve_agent_workshop_blocking_gaps(session_id='ws_abc123')",
    related_tools=[
        "analyze_agent_workshop_gaps",
        "build_agent_workshop_version",
        "search_project_capabilities",
    ],
    data_source_handling="local_only",
)
async def resolve_agent_workshop_blocking_gaps(
    session_id: Annotated[str, "Agent 工坊会话 ID"],
    blocking_gaps_json: Annotated[str, "可选 JSON 数组，直接指定要补全的缺口描述；若为空则从 session 的 gap_report 中读取"] = "",
    max_wait_seconds: Annotated[int, "每个 Skill 生成的最长等待时间（秒），默认 300"] = 300,
    auto_continue_build: Annotated[bool, "补齐后是否自动执行能力重检并继续构建版本，默认 true"] = True,
    confirm_external_data_risk: Annotated[bool, "若缺口涉及外部数据源/第三方接口，是否已向用户明确披露风险并获得确认"] = False,
    allow_medium_similarity_autocreate: Annotated[bool, "命中中等相似度（0.6-0.85）候选 Skill 时，是否允许直接继续新建"] = False,
    mode: Annotated[str, "任务模式：auto 或 manual_confirmed，与 start_agent_workshop_gap_resolution 保持一致；若指定则覆盖 allow_medium_similarity_autocreate"] = "",
) -> str:
    """自动补全 Agent 工坊的能力缺口。

    流程：
    1. 从 workshop session 中读取 gap_report.blocking_gaps
    2. 对每个缺口并行启动 Skill 生成会话
    3. 等待所有 Skill 生成完成（带超时）
    4. 返回结果，供后续 build_version 使用
    """
    try:
        clean_session_id = str(session_id or "").strip()
        if not clean_session_id:
            return _json_response({"status": "error", "message": "session_id 不能为空"})

        # 统一 mode 参数：若指定 mode 则覆盖 allow_medium_similarity_autocreate
        clean_mode = str(mode or "").strip().lower()
        if clean_mode in ("auto", "manual_confirmed"):
            allow_medium_similarity_autocreate = clean_mode == "auto"
        elif clean_mode:
            return _json_response({"status": "error", "message": f"mode 只支持 auto 或 manual_confirmed，实际传入: {clean_mode}"})

        db = get_mongo_db()
        from app.services.skill_generation_service import SESSION_COLLECTION

        # 解析真实发起用户（用于 Skill 归属与权限），失败回退到 nanobot
        resolved_user_id = ""
        try:
            resolved_user_id = str(require_current_user_id() or "").strip()
        except Exception:
            resolved_user_id = ""
        effective_user_id = resolved_user_id or "nanobot"

        # 始终加载工坊会话，提取 Agent 来源上下文（spec_id / 名称 / 目标），用于反向追溯
        ws_service = AgentWorkshopService(db=db)
        workshop_session = await ws_service._load_session(clean_session_id)
        agent_spec_id = ""
        agent_name = ""
        agent_goal = ""
        if workshop_session is not None:
            agent_spec_id = str(getattr(workshop_session, "spec_id", "") or "")
            spec_snapshot = getattr(workshop_session, "current_spec_snapshot", None)
            if spec_snapshot is not None:
                agent_name = str(getattr(spec_snapshot, "name", "") or "")
                agent_goal = str(getattr(spec_snapshot, "primary_goal", "") or "")
            # 调用方无用户上下文时，回退到工坊会话归属用户，避免落到匿名 nanobot
            if not resolved_user_id:
                session_user = str(getattr(workshop_session, "user_id", "") or "").strip()
                if session_user:
                    effective_user_id = session_user

        # 1. 获取 blocking_gaps
        gaps: list[str] = []
        if blocking_gaps_json.strip():
            try:
                parsed = json.loads(blocking_gaps_json)
                if isinstance(parsed, list):
                    gaps = [str(g).strip() for g in parsed if str(g).strip()]
            except (json.JSONDecodeError, TypeError):
                return _json_response({"status": "error", "message": "blocking_gaps_json 不是有效的 JSON 数组"})

        if not gaps:
            # 从已加载的 workshop session 中读取
            if workshop_session is None:
                return _json_response({"status": "error", "message": f"Agent 工坊会话 {clean_session_id} 不存在"})

            gap_report = workshop_session.gap_report
            if not gap_report:
                # 尝试先执行缺口分析
                gap_analysis = await ws_service.analyze_gaps(clean_session_id)
                gap_report = gap_analysis.get("gap_report") if isinstance(gap_analysis, dict) else None

            if not gap_report:
                return _json_response({"status": "error", "message": "无法获取缺口分析报告，请先执行 analyze_agent_workshop_gaps"})

            blocking_gaps = getattr(gap_report, "blocking_gaps", None) or []
            if isinstance(blocking_gaps, list):
                gaps = [str(g).strip() for g in blocking_gaps if str(g).strip()]

        if not gaps:
            return _json_response({
                "status": "ok",
                "message": "没有需要补全的阻塞缺口",
                "gaps_found": 0,
                "skills_generated": [],
            })

        capped_gaps = gaps[:3]
        if len(gaps) > 3:
            logger.warning(
                "[resolve_gaps] 缺口数量 %d 超过默认上限，只处理前 3 个，其余建议分批: %s",
                len(gaps), capped_gaps,
            )

        risky_gaps = [gap for gap in capped_gaps if _contains_external_data_risk(gap)]
        if risky_gaps and not confirm_external_data_risk:
            return _json_response({
                "status": "blocked",
                "blocked_by": "external_data_risk_confirmation",
                "message": "检测到缺口可能依赖外部数据源或第三方接口，需先向用户披露来源与风险并获得确认后再生成。",
                "workshop_session_id": clean_session_id,
                "risky_gaps": risky_gaps,
                "next_action": "与用户确认后，重新调用 resolve_agent_workshop_blocking_gaps 并传 confirm_external_data_risk=true",
            })

        wait_seconds = max(60, min(int(max_wait_seconds), 600))

        logger.info(
            "[resolve_gaps] 开始补全 %d 个能力缺口 (workshop_session=%s, timeout=%ds): %s",
            len(capped_gaps), clean_session_id, wait_seconds, capped_gaps,
        )

        # 2. 对每个缺口启动 Skill 生成
        results: list[dict[str, Any]] = []

        async def _process_single_gap(gap_index: int, gap_description: str) -> dict[str, Any]:
            gap_id = f"gap_{gap_index + 1}"
            gap_result = await _resolve_single_gap_capability(
                db=db,
                ws_service=ws_service,
                gap_description=gap_description,
                gap_id=gap_id,
                gap_index=gap_index,
                workshop_session_id=clean_session_id,
                agent_spec_id=agent_spec_id,
                agent_name=agent_name,
                agent_goal=agent_goal,
                user_id=effective_user_id,
                allow_medium_similarity_autocreate=allow_medium_similarity_autocreate,
                related_gaps=capped_gaps,
                handoff_intent="auto_resolve_blocking_gap",
            )
            if str(gap_result.get("status") or "") != "generating":
                return gap_result

            skill_session_id = str(gap_result.get("session_id") or gap_result.get("skill_session_id") or "").strip()
            if not skill_session_id:
                gap_result["status"] = "failed"
                gap_result["error"] = "Skill 生成会话丢失"
                return gap_result

            poll_interval = 5
            elapsed = 0
            while elapsed < wait_seconds:
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval
                gap_result["elapsed_seconds"] = elapsed

                session_doc = await db[SESSION_COLLECTION].find_one({"session_id": skill_session_id})
                if not session_doc:
                    gap_result["status"] = "failed"
                    gap_result["error"] = "Skill 生成会话丢失"
                    return gap_result

                status = session_doc.get("status", "")
                pipeline_stage = session_doc.get("pipeline_stage", "")
                pipeline_message = session_doc.get("pipeline_message", "")
                gap_result["pipeline_stage"] = pipeline_stage
                gap_result["pipeline_message"] = pipeline_message

                if status == "completed":
                    spec = session_doc.get("spec") or {}
                    gap_result["status"] = "completed"
                    gap_result["skill_tool_id"] = spec.get("tool_id", "")
                    gap_result["skill_display_name"] = spec.get("display_name", "")
                    logger.info(
                        "[resolve_gaps] Skill #%d 生成完成: tool_id=%s display_name=%s elapsed=%ds",
                        gap_index,
                        gap_result["skill_tool_id"],
                        gap_result["skill_display_name"],
                        elapsed,
                    )
                    return gap_result

                if status == "failed":
                    gap_result["status"] = "failed"
                    gap_result["error"] = f"Skill 生成失败: {pipeline_message}"
                    return gap_result

                logger.debug(
                    "[resolve_gaps] Skill #%d 仍在生成中: status=%s stage=%s elapsed=%ds",
                    gap_index, status, pipeline_stage, elapsed,
                )

            gap_result["status"] = "timeout"
            gap_result["error"] = f"Skill 生成超时（{wait_seconds}s）"
            return gap_result

        # 并行处理所有缺口
        tasks = [
            _process_single_gap(i, gap_desc)
            for i, gap_desc in enumerate(capped_gaps)
        ]
        results = await asyncio.gather(*tasks)

        successful = [r for r in results if r["status"] in ("completed", "reused_existing")]
        completed = [r for r in results if r["status"] == "completed"]
        reused = [r for r in results if r["status"] == "reused_existing"]
        pending_confirmation = [r for r in results if r["status"] == "needs_dedup_confirmation"]
        failed = [r for r in results if r["status"] in ("failed", "timeout")]

        auto_continue = {
            "enabled": bool(auto_continue_build),
            "status": "skipped",
            "capability_search": None,
            "gap_analysis": None,
            "tooling_plan": None,
            "build_version": None,
            "error": None,
        }

        if auto_continue_build and successful:
            try:
                # Step A: 重新检索能力，帮助后续缺口/工具规划消费新生成 Skill
                capability_query = " ".join(_dedupe_string_list([
                    *capped_gaps,
                    agent_name,
                    agent_goal,
                    *[str(item.get("skill_display_name") or "") for item in successful],
                    *[str(item.get("skill_tool_id") or "") for item in successful],
                ])).strip()
                capability_hits = await CapabilityIndexService(db).search_capabilities(
                    query=capability_query or "agent capability",
                    top_k=12,
                    bindable_only=True,
                    source_types=["builtin_tool", "skill", "external_skill", "mcp_tool"],
                )
                auto_continue["capability_search"] = {
                    "query": capability_query or "agent capability",
                    "count": len(capability_hits),
                    "top_results": [_format_capability_hit(hit) for hit in capability_hits[:5]],
                }

                # Step B/C: 重新分析缺口 -> 生成工具计划
                # v3.6.0 项6 路径B：生成完成后不再自动调用 build_version / sync_version_required_tools
                # 改为写入 skill_review_queue 等待用户审核，用户确认后才触发绑定
                gap_analysis_result = await ws_service.analyze_gaps(clean_session_id)
                tooling_plan_result = await ws_service.generate_tooling_plan(clean_session_id)
                phase_context = await _resolve_workshop_session_phase_context(db, clean_session_id)
                current_version_id = str(phase_context.get("current_version_id") or "").strip()
                current_version_status = str(phase_context.get("version_status") or "").strip().lower()

                # 写入待审核记录（路径B HITL）
                pending_reviews: list[dict[str, Any]] = []
                try:
                    from app.pro.services.skill_review_service import SkillReviewService
                    review_service = SkillReviewService(db=db)
                    pending_reviews = await review_service.create_pending_reviews_for_workshop(
                        workshop_session_id=clean_session_id,
                        agent_spec_id=agent_spec_id,
                        agent_name=agent_name,
                        user_id=effective_user_id,
                        successful_items=successful,
                    )
                except Exception as review_exc:
                    logger.warning(
                        "[resolve_gaps] 写入 skill_review_queue 失败（不阻塞）: %s",
                        review_exc, exc_info=True,
                    )

                auto_continue["gap_analysis"] = {
                    "spec_id": gap_analysis_result.get("spec_id") if isinstance(gap_analysis_result, dict) else "",
                    "blocking_gaps": len(_read_mapping_or_attr(gap_analysis_result.get("gap_report") if isinstance(gap_analysis_result, dict) else None, "blocking_gaps", []) or []),
                }
                auto_continue["tooling_plan"] = {
                    "spec_id": tooling_plan_result.get("spec_id") if isinstance(tooling_plan_result, dict) else "",
                    "missing_capabilities": len(_read_mapping_or_attr(tooling_plan_result.get("tooling_plan") if isinstance(tooling_plan_result, dict) else None, "missing_capabilities", []) or []),
                }
                # build_version 字段保留向后兼容，但不再自动构建版本
                auto_continue["build_version"] = {
                    "spec_id": agent_spec_id,
                    "version_id": current_version_id,
                    "existing_version_status": current_version_status,
                    "skipped": True,
                    "reason": "pending_user_review",
                    "pending_review_count": len(pending_reviews),
                }
                auto_continue["pending_user_review"] = {
                    "count": len(pending_reviews),
                    "tool_ids": [r.get("tool_id") for r in pending_reviews if r.get("tool_id")],
                    "review_ids": [r.get("review_id") for r in pending_reviews if r.get("review_id")],
                    "next_action": (
                        "用户审核后调用 "
                        "/api/agent-workshop/skill-review/{session_id}/{tool_id}/confirm 或 /reject"
                    ),
                }
                auto_continue["status"] = "pending_user_review"
            except Exception as auto_exc:
                logger.warning("[resolve_gaps] 自动续建失败: %s", auto_exc, exc_info=True)
                auto_continue["status"] = "failed"
                auto_continue["error"] = str(auto_exc)

        summary = {
            "total_gaps": len(capped_gaps),
            "generated": len(completed),
            "reused": len(reused),
            "completed": len(completed),
            "successful": len(successful),
            "needs_confirmation": len(pending_confirmation),
            "failed": len(failed),
            "generated_tool_ids": [r["skill_tool_id"] for r in completed if r["skill_tool_id"]],
            "reused_tool_ids": [r["skill_tool_id"] for r in reused if r["skill_tool_id"]],
            "failed_gaps": [
                {
                    "gap_id": r.get("gap_id"),
                    "gap_description": r.get("gap_description"),
                    "error": r.get("error") or r.get("pipeline_message") or "补齐失败",
                    "skill_session_id": r.get("session_id"),
                }
                for r in failed
            ],
            "pending_confirmation_details": [
                {
                    "gap_id": r.get("gap_id"),
                    "gap_description": r.get("gap_description"),
                    "dedup_candidate": r.get("dedup_candidate") or {},
                    "pipeline_message": r.get("pipeline_message"),
                }
                for r in pending_confirmation
            ],
            "next_action": (
                (
                    "存在中等相似度候选 Skill 等待确认："
                    + "；".join([
                        f"缺口「{r.get('gap_description') or r.get('gap_id') or '?'}」"
                        + "命中候选 Skill「"
                        + str((r.get('dedup_candidate') or {}).get('name') or '?') + '」'
                        + f"（相似度 {(r.get('dedup_candidate') or {}).get('score') or 0:.0%}）"
                        for r in pending_confirmation
                    ])
                    + "。请向用户展示候选 Skill 的名称、功能描述和相似度，"
                    "让用户确认是复用现有 Skill 还是创建新的。"
                )
                if pending_confirmation
                else (
                    # v3.6.0 项6 路径B：所有 Skill 生成后均需用户审核，不再自动绑定
                    "所有缺口已补全，生成的 Skill 等待用户审核。请向用户展示每个 Skill 的代码和测试结果，"
                    "用户确认后调用 /api/agent-workshop/skill-review/{session_id}/{tool_id}/confirm 绑定，"
                    "或 /reject 拒绝（Skill 留在工坊）。所有 Skill 审核通过后再调用 build_agent_workshop_version 构建版本。"
                    if len(successful) == len(capped_gaps)
                    else (
                        f"已补全 {len(completed)}/{len(capped_gaps)} 个缺口，"
                        "剩余缺口可能需要手动处理。已生成的 Skill 等待用户审核（确认后才绑定），"
                        "审核完成后建议调用 build_agent_workshop_version 构建版本。"
                    )
                )
            ),
            "user_facing_message": (
                (
                    f"Agent「{agent_name}」有 {len(failed)} 个能力缺口自动补齐失败，Agent 版本不能视为完整通过："
                    + "、".join([
                        f"「{r.get('gap_description') or r.get('gap_id') or '?'}」失败原因：{r.get('error') or r.get('pipeline_message') or '未知'}"
                        for r in failed
                    ])
                    + "。请先修复或重试这些 Skill，再继续构建、评审或发布 Agent。"
                )
                if failed
                else (
                    (
                        "存在中等相似度候选 Skill 等待确认：\n"
                        + "\n".join([
                            f"• 缺口「{r.get('gap_description') or r.get('gap_id') or '?'}」"
                            + f" → 候选 Skill：「{str((r.get('dedup_candidate') or {}).get('name') or '?')}」"
                            + f"（相似度 {round(float((r.get('dedup_candidate') or {}).get('score') or 0) * 100)}%）"
                            + (
                                f"\n  功能描述：{str((r.get('dedup_candidate') or {}).get('description') or '')[:200]}"
                                if str((r.get('dedup_candidate') or {}).get('description') or '').strip()
                                else ""
                            )
                            for r in pending_confirmation
                        ])
                        + "\n\n请向用户展示候选 Skill 的名称与功能描述，说明复用 vs 新建的利弊，让用户做出选择。"
                    )
                    if pending_confirmation
                    else (
                        # v3.6.0 项6 路径B：生成成功后不再自动绑定，提示用户审核
                        f"已为 Agent「{agent_name}」自动补齐 {len(successful)} 个能力缺口：\n"
                        + "\n".join([
                            f"• 「{r.get('skill_display_name') or r.get('skill_tool_id') or '?'}」"
                            + f"（缺口：{r.get('gap_description', '')}）"
                            for r in successful
                        ])
                        + "\n\n这些 Skill 已通过质量门禁（语法/沙箱/评估），但不会自动绑定到 Agent。"
                        "请向用户展示每个 Skill 的代码和测试结果，让用户决定是否绑定：\n"
                        "  - 确认绑定：调用 /api/agent-workshop/skill-review/{session_id}/{tool_id}/confirm\n"
                        "  - 拒绝绑定：调用 /api/agent-workshop/skill-review/{session_id}/{tool_id}/reject（Skill 留在工坊可后续复用）\n"
                        "所有 Skill 审核完成后，再继续 Agent 版本构建流程。"
                        if successful
                        else "未能成功补齐任何缺口，请检查失败原因后重试。"
                    )
                )
            ),
        }

        logger.info(
            "[resolve_gaps] 补全完成: completed=%d failed=%d tool_ids=%s",
            len(completed), len(failed), summary["generated_tool_ids"],
        )

        # 🔥 记录 Agent → Gap → Skill 的父子任务链，确保 Nanobot 完成 Skill 后回到父 Agent
        # 同时把需要用户确认的 dedup candidate 写入 last_proposed_items，支持后续指代消解
        dedup_items = [
            {
                "index": idx + 1,
                "id": f"dedup_{r.get('gap_id') or idx}",
                "name": f"缺口「{r.get('gap_description') or r.get('gap_id') or '?'}」的候选 Skill「{str((r.get('dedup_candidate') or {}).get('name') or '?')}」",
                "description": (
                    f"相似度 {round(float((r.get('dedup_candidate') or {}).get('score') or 0) * 100)}%；"
                    + f"候选描述：{str((r.get('dedup_candidate') or {}).get('description') or '')[:200]}"
                ),
                "gap_id": str(r.get("gap_id") or ""),
                "candidate_name": str((r.get("dedup_candidate") or {}).get("name") or ""),
                "candidate_score": float((r.get("dedup_candidate") or {}).get("score") or 0),
            }
            for idx, r in enumerate(pending_confirmation)
        ]
        if dedup_items:
            _auto_update_intent(
                action="resolve_gap",
                stage="gap_resolving",
                spec_id=agent_spec_id,
                spec_name=agent_name,
                pending_question=f"Agent「{agent_name}」有 {len(dedup_items)} 个缺口发现相似候选 Skill，请确认对每个缺口是复用候选还是新建 Skill？",
                proposed_items=dedup_items,
                active_subtask="等待用户确认候选 Skill 复用/新建",
                next_action="用户确认后再次调用 resolve_agent_workshop_blocking_gaps 并传入明确参数",
            )

        for idx, gap_text in enumerate(capped_gaps):
            _auto_update_intent(
                action="resolve_gap",
                stage="gap_resolving",
                spec_id=agent_spec_id,
                spec_name=agent_name,
                active_subtask=f"为 Agent「{agent_name}」补齐缺口：{gap_text}",
                next_action=summary.get("next_action") or "回到父 Agent 继续构建/测试",
                task={
                    "type": "gap",
                    "id": f"{clean_session_id}:gap_{idx + 1}",
                    "name": gap_text[:80],
                    "status": "completed" if idx < len(successful) else "failed_or_pending",
                    "parent_id": agent_spec_id,
                },
            )
        for item in successful:
            gaps_all_successful = len(successful) == len(capped_gaps)
            next_stage_after_skill = (
                "building"
                if auto_continue.get("status") == "completed"
                else "ready_to_build"
                if gaps_all_successful
                else "gap_resolving"
            )
            _auto_update_intent(
                action="resolve_gap",
                stage=next_stage_after_skill,
                spec_id=agent_spec_id,
                spec_name=agent_name,
                linked_skill={
                    "skill_id": str(item.get("skill_tool_id") or ""),
                    "skill_name": str(item.get("skill_display_name") or item.get("skill_tool_id") or ""),
                    "gap": str(item.get("gap_description") or ""),
                    "status": str(item.get("status") or ""),
                },
                task={
                    "type": "skill",
                    "id": str(item.get("skill_tool_id") or item.get("session_id") or ""),
                    "name": str(item.get("skill_display_name") or item.get("skill_tool_id") or ""),
                    "status": str(item.get("status") or ""),
                    "parent_id": agent_spec_id,
                },
            )

        return _json_response({
            "status": "error" if failed else "ok",
            "message": summary.get("user_facing_message", ""),
            "workshop_session_id": clean_session_id,
            "summary": summary,
            "results": results,
            "auto_continue": auto_continue,
        })

    except Exception as exc:
        logger.error("补全 Agent 工坊能力缺口失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"补全能力缺口失败: {exc}"})


@tool
@register_tool(
    tool_id="start_agent_workshop_gap_resolution",
    name="启动 Agent 能力缺口异步补齐任务",
    description="创建 gap resolution job 并返回 job_id，供后续轮询进度与控制。",
    category="assistant_ops",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    when_to_use="当缺口补齐可能耗时较长时，先创建异步 job，再通过 inspect/cancel/retry 工具治理。",
    when_not_to_use="不适合在 session_id 无效时调用。",
    returns="返回 JSON 字符串，包含 job_id、status、gaps 与 idempotency_key。",
    example="start_agent_workshop_gap_resolution(session_id='ws_123')",
    related_tools=[
        "inspect_agent_workshop_gap_resolution",
        "cancel_agent_workshop_gap_resolution",
        "retry_agent_workshop_gap_resolution_item",
    ],
    data_source_handling="local_only",
)
async def start_agent_workshop_gap_resolution(
    session_id: Annotated[str, "Agent 工坊会话 ID"],
    blocking_gaps_json: Annotated[str, "可选 JSON 数组，直接指定缺口描述；为空时从 session gap_report 读取"] = "",
    mode: Annotated[str, "任务模式：auto 或 manual_confirmed，默认 manual_confirmed"] = "manual_confirmed",
    idempotency_key: Annotated[str, "幂等键；为空时按 session_id + gaps 自动生成"] = "",
    max_items: Annotated[int, "最多纳入 job 的缺口数，默认 3，最大 10"] = 3,
) -> str:
    """创建 Agent 能力缺口异步补齐 job，并返回 job_id 与初始状态。"""
    try:
        clean_session_id = str(session_id or "").strip()
        if not clean_session_id:
            return _json_response({"status": "error", "message": "session_id 不能为空"})

        db = get_mongo_db()
        ws_service = AgentWorkshopService(db=db)
        workshop_session = await ws_service._load_session(clean_session_id)
        if workshop_session is None:
            return _json_response({"status": "error", "message": f"Agent 工坊会话 {clean_session_id} 不存在"})

        gaps: list[str] = []
        if str(blocking_gaps_json or "").strip():
            try:
                parsed = json.loads(blocking_gaps_json)
                if isinstance(parsed, list):
                    gaps = [str(item).strip() for item in parsed if str(item).strip()]
            except Exception as exc:
                return _json_response({"status": "error", "message": f"blocking_gaps_json 解析失败: {exc}"})
        if not gaps:
            gap_report = getattr(workshop_session, "gap_report", None)
            if gap_report is None:
                analysis = await ws_service.analyze_gaps(clean_session_id)
                gap_report = analysis.get("gap_report") if isinstance(analysis, dict) else None
            gaps = _extract_blocking_gaps_from_report(gap_report)

        capped_limit = max(1, min(int(max_items), 10))
        gaps = gaps[:capped_limit]
        if not gaps:
            return _json_response({
                "status": "ok",
                "message": "当前没有 blocking gaps，无需创建异步补齐任务",
                "workshop_session_id": clean_session_id,
                "created": False,
            })

        clean_mode = str(mode or "manual_confirmed").strip().lower() or "manual_confirmed"
        if clean_mode not in {"auto", "manual_confirmed"}:
            clean_mode = "manual_confirmed"

        effective_idempotency_key = str(idempotency_key or "").strip() or _build_gap_resolution_idempotency_key(clean_session_id, gaps)
        collection = _get_collection(db, _GAP_RESOLUTION_JOB_COLLECTION)
        if collection is None:
            return _json_response({"status": "error", "message": f"数据库中不可用集合: {_GAP_RESOLUTION_JOB_COLLECTION}"})

        existing_docs = await collection.find({
            "workshop_session_id": clean_session_id,
            "idempotency_key": effective_idempotency_key,
        }).to_list(length=5)
        for doc in existing_docs:
            if str((doc or {}).get("status") or "").strip().lower() in _GAP_JOB_ACTIVE_STATUSES:
                logger.info(
                    "[GapJob][Start] idempotent_hit session_id=%s key=%s existing_job_id=%s status=%s",
                    clean_session_id,
                    effective_idempotency_key,
                    doc.get("job_id"),
                    doc.get("status"),
                )
                return _json_response({
                    "status": "ok",
                    "created": False,
                    "message": "命中幂等任务，返回现有进行中 job",
                    "job": {
                        "job_id": doc.get("job_id"),
                        "status": doc.get("status"),
                        "workshop_session_id": doc.get("workshop_session_id"),
                        "mode": doc.get("mode"),
                        "idempotency_key": doc.get("idempotency_key"),
                    },
                })

        now_iso = _utc_now_iso()
        seed = f"{clean_session_id}:{effective_idempotency_key}:{now_iso}"
        job_id = _build_gap_resolution_job_id(seed)
        job_gaps = [
            {
                "gap_id": f"gap_{index + 1}",
                "description": gap,
                "status": "pending",
                "pipeline_stage": "queued",
                "pipeline_message": "等待 worker 执行",
                "error": None,
                "skill_session_id": "",
                "skill_tool_id": "",
                "skill_display_name": "",
                "retry_count": 0,
                "auto_retry_count": 0,
                "next_retry_at": "",
                "dead_letter": {},
                "created_at": now_iso,
                "updated_at": now_iso,
            }
            for index, gap in enumerate(gaps)
        ]

        job_doc = {
            "job_id": job_id,
            "workshop_session_id": clean_session_id,
            "spec_id": str(getattr(workshop_session, "spec_id", "") or ""),
            "version_id": "",
            "user_id": str(getattr(workshop_session, "user_id", "") or ""),
            "status": "pending",
            "mode": clean_mode,
            "idempotency_key": effective_idempotency_key,
            "execution": {
                "runner": "worker_required",
                "state": "queued",
                "note": "Phase 3 先落 job 协议；执行由后台 worker 接管",
                "retry_policy": {
                    "max_attempts": _GAP_AUTO_RETRY_MAX_ATTEMPTS,
                    "base_delay_seconds": _GAP_AUTO_RETRY_BASE_DELAY_SECONDS,
                    "max_delay_seconds": _GAP_AUTO_RETRY_MAX_DELAY_SECONDS,
                },
            },
            "gaps": job_gaps,
            "created_at": now_iso,
            "updated_at": now_iso,
        }
        await collection.insert_one(job_doc)

        logger.info(
            "[GapJob][Start] created session_id=%s job_id=%s gaps=%d mode=%s key=%s",
            clean_session_id,
            job_id,
            len(job_gaps),
            clean_mode,
            effective_idempotency_key,
        )

        return _json_response({
            "status": "ok",
            "created": True,
            "message": "已创建 gap resolution job，等待 worker 消费",
            "job": {
                "job_id": job_id,
                "status": "pending",
                "workshop_session_id": clean_session_id,
                "spec_id": job_doc.get("spec_id"),
                "mode": clean_mode,
                "idempotency_key": effective_idempotency_key,
                "summary": _summarize_gap_job_gaps(job_gaps),
            },
        })
    except Exception as exc:
        logger.error("启动 Agent 缺口异步补齐任务失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"启动异步补齐任务失败: {exc}"})


@tool
@register_tool(
    tool_id="inspect_agent_workshop_gap_resolution",
    name="查看 Agent 能力缺口异步补齐任务",
    description="查询 gap resolution job 的当前状态与每个 gap 的进度。",
    category="assistant_ops",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    when_to_use="需要在 Agent Studio 里持续查看补齐任务进度时使用。",
    when_not_to_use="不适合在 job_id 不存在时调用。",
    returns="返回 JSON 字符串，包含 job 状态、gap 列表与汇总计数。",
    example="inspect_agent_workshop_gap_resolution(job_id='gap_job_xxx')",
    related_tools=[
        "start_agent_workshop_gap_resolution",
        "cancel_agent_workshop_gap_resolution",
        "retry_agent_workshop_gap_resolution_item",
    ],
    data_source_handling="local_only",
)
async def inspect_agent_workshop_gap_resolution(
    job_id: Annotated[str, "gap resolution job_id"],
    include_gaps: Annotated[bool, "是否返回每个 gap 明细，默认 true"] = True,
) -> str:
    """查询 gap resolution job 的状态、汇总与（可选）gap 明细。"""
    try:
        clean_job_id = str(job_id or "").strip()
        if not clean_job_id:
            return _json_response({"status": "error", "message": "job_id 不能为空"})

        db = get_mongo_db()
        collection = _get_collection(db, _GAP_RESOLUTION_JOB_COLLECTION)
        if collection is None:
            return _json_response({"status": "error", "message": f"数据库中不可用集合: {_GAP_RESOLUTION_JOB_COLLECTION}"})

        doc = await collection.find_one({"job_id": clean_job_id})
        if not doc:
            return _json_response({"status": "error", "message": f"job {clean_job_id} 不存在"})

        gaps = list(doc.get("gaps") or [])
        summary = _summarize_gap_job_gaps(gaps)
        logger.info(
            "[GapJob][Inspect] job_id=%s status=%s summary=%s",
            clean_job_id,
            doc.get("status"),
            summary,
        )
        payload = {
            "status": "ok",
            "job": {
                "job_id": doc.get("job_id"),
                "workshop_session_id": doc.get("workshop_session_id"),
                "spec_id": doc.get("spec_id"),
                "version_id": doc.get("version_id"),
                "user_id": doc.get("user_id"),
                "status": doc.get("status"),
                "mode": doc.get("mode"),
                "idempotency_key": doc.get("idempotency_key"),
                "execution": doc.get("execution") or {},
                "summary": _summarize_gap_job_gaps(gaps),
                "created_at": doc.get("created_at"),
                "updated_at": doc.get("updated_at"),
            },
        }
        if include_gaps:
            payload["job"]["gaps"] = gaps
        return _json_response(payload)
    except Exception as exc:
        logger.error("查看 Agent 缺口异步补齐任务失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"查看异步补齐任务失败: {exc}"})


@tool
@register_tool(
    tool_id="cancel_agent_workshop_gap_resolution",
    name="取消 Agent 能力缺口异步补齐任务",
    description="将 pending/running 的 gap resolution job 标记为 cancelled。",
    category="assistant_ops",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    when_to_use="用户明确要求停止当前补齐任务时使用。",
    when_not_to_use="不适合取消已完成任务。",
    returns="返回 JSON 字符串，包含取消结果与更新后的汇总。",
    example="cancel_agent_workshop_gap_resolution(job_id='gap_job_xxx')",
    related_tools=[
        "inspect_agent_workshop_gap_resolution",
        "retry_agent_workshop_gap_resolution_item",
    ],
    data_source_handling="local_only",
)
async def cancel_agent_workshop_gap_resolution(
    job_id: Annotated[str, "gap resolution job_id"],
    reason: Annotated[str, "取消原因，可选"] = "",
) -> str:
    """取消 pending/running 的 gap resolution job。"""
    try:
        clean_job_id = str(job_id or "").strip()
        if not clean_job_id:
            return _json_response({"status": "error", "message": "job_id 不能为空"})

        db = get_mongo_db()
        collection = _get_collection(db, _GAP_RESOLUTION_JOB_COLLECTION)
        if collection is None:
            return _json_response({"status": "error", "message": f"数据库中不可用集合: {_GAP_RESOLUTION_JOB_COLLECTION}"})

        doc = await collection.find_one({"job_id": clean_job_id})
        if not doc:
            return _json_response({"status": "error", "message": f"job {clean_job_id} 不存在"})

        current_status = str(doc.get("status") or "").strip().lower()
        if current_status in _GAP_JOB_TERMINAL_STATUSES:
            return _json_response({
                "status": "ok",
                "message": f"job 已处于终态: {current_status}，无需取消",
                "job": {
                    "job_id": clean_job_id,
                    "status": current_status,
                    "summary": _summarize_gap_job_gaps(list(doc.get("gaps") or [])),
                },
            })

        now_iso = _utc_now_iso()
        updated_gaps: list[dict[str, Any]] = []
        for gap in list(doc.get("gaps") or []):
            item = dict(gap or {})
            gap_status = str(item.get("status") or "").strip().lower()
            if gap_status not in {"completed", "failed", "timeout"}:
                item["status"] = "cancelled"
                item["pipeline_message"] = str(reason or "用户取消任务")
                item["updated_at"] = now_iso
            updated_gaps.append(item)

        await collection.update_one(
            {"job_id": clean_job_id},
            {
                "$set": {
                    "status": "cancelled",
                    "gaps": updated_gaps,
                    "updated_at": now_iso,
                    "execution.state": "cancelled",
                    "execution.cancel_reason": str(reason or "").strip(),
                }
            },
        )

        logger.info(
            "[GapJob][Cancel] done job_id=%s reason=%s summary=%s",
            clean_job_id,
            str(reason or "").strip() or "-",
            _summarize_gap_job_gaps(updated_gaps),
        )

        return _json_response({
            "status": "ok",
            "message": "已取消 gap resolution job",
            "job": {
                "job_id": clean_job_id,
                "status": "cancelled",
                "summary": _summarize_gap_job_gaps(updated_gaps),
                "updated_at": now_iso,
            },
        })
    except Exception as exc:
        logger.error("取消 Agent 缺口异步补齐任务失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"取消异步补齐任务失败: {exc}"})


@tool
@register_tool(
    tool_id="retry_agent_workshop_gap_resolution_item",
    name="重试 Agent 缺口补齐任务中的单个缺口",
    description="将某个 gap 重新置为 pending，等待 worker 重新执行该项。",
    category="assistant_ops",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    when_to_use="当某个 gap 失败/超时/取消后，希望单项重试时使用。",
    when_not_to_use="不适合对仍在运行的 gap 重复重试。",
    returns="返回 JSON 字符串，包含重试后的 job 汇总与目标 gap 状态。",
    example="retry_agent_workshop_gap_resolution_item(job_id='gap_job_xxx', gap_id='gap_1')",
    related_tools=[
        "inspect_agent_workshop_gap_resolution",
        "cancel_agent_workshop_gap_resolution",
    ],
    data_source_handling="local_only",
)
async def retry_agent_workshop_gap_resolution_item(
    job_id: Annotated[str, "gap resolution job_id"],
    gap_id: Annotated[str, "目标缺口 ID，如 gap_1"],
    reason: Annotated[str, "重试原因，可选"] = "",
) -> str:
    """重试 gap resolution job 中的单个失败/超时/取消项。"""
    try:
        clean_job_id = str(job_id or "").strip()
        clean_gap_id = str(gap_id or "").strip()
        if not clean_job_id:
            return _json_response({"status": "error", "message": "job_id 不能为空"})
        if not clean_gap_id:
            return _json_response({"status": "error", "message": "gap_id 不能为空"})

        db = get_mongo_db()
        collection = _get_collection(db, _GAP_RESOLUTION_JOB_COLLECTION)
        if collection is None:
            return _json_response({"status": "error", "message": f"数据库中不可用集合: {_GAP_RESOLUTION_JOB_COLLECTION}"})

        doc = await collection.find_one({"job_id": clean_job_id})
        if not doc:
            return _json_response({"status": "error", "message": f"job {clean_job_id} 不存在"})

        now_iso = _utc_now_iso()
        target_after: dict[str, Any] | None = None
        updated_gaps: list[dict[str, Any]] = []
        found = False
        for gap in list(doc.get("gaps") or []):
            item = dict(gap or {})
            if str(item.get("gap_id") or "").strip() != clean_gap_id:
                updated_gaps.append(item)
                continue

            found = True
            current_status = str(item.get("status") or "").strip().lower()
            if current_status in {"pending", "running"}:
                return _json_response({
                    "status": "error",
                    "message": f"gap {clean_gap_id} 当前状态为 {current_status}，无需重试",
                })

            item["status"] = "pending"
            item["pipeline_stage"] = "queued"
            item["pipeline_message"] = str(reason or "已提交重试，等待 worker 执行")
            item["error"] = None
            item["updated_at"] = now_iso
            item["retry_count"] = int(item.get("retry_count") or 0) + 1
            item["auto_retry_count"] = 0
            item["next_retry_at"] = ""
            item["dead_letter"] = {}
            target_after = item
            updated_gaps.append(item)

        if not found:
            return _json_response({"status": "error", "message": f"job {clean_job_id} 中不存在 gap_id={clean_gap_id}"})

        await collection.update_one(
            {"job_id": clean_job_id},
            {
                "$set": {
                    "status": "pending",
                    "gaps": updated_gaps,
                    "updated_at": now_iso,
                    "execution.state": "queued",
                }
            },
        )

        return _json_response({
            "status": "ok",
            "message": "已重置目标 gap 为 pending",
            "job": {
                "job_id": clean_job_id,
                "status": "pending",
                "summary": _summarize_gap_job_gaps(updated_gaps),
                "updated_at": now_iso,
            },
            "gap": target_after,
        })
    except Exception as exc:
        logger.error("重试 Agent 缺口异步补齐项失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"重试异步补齐项失败: {exc}"})


__all__ = [
    "search_project_capabilities",
    "propose_agent_build_plans",
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
    "resolve_agent_workshop_blocking_gaps",
    "start_agent_workshop_gap_resolution",
    "inspect_agent_workshop_gap_resolution",
    "cancel_agent_workshop_gap_resolution",
    "retry_agent_workshop_gap_resolution_item",
]


async def _get_progress_collection():
    """获取 workshop_test_progress 集合（懒初始化）。"""
    try:
        db = get_mongo_db()
        collection = db.get_collection("workshop_test_progress")
        await collection.create_index("version_id", unique=True)
        return collection
    except Exception:
        return None


def _get_current_intent_stage() -> str:
    """读取当前线程的 intent stage（优先 module 存储，其次 contextvar）。"""
    try:
        from core.tools.context import get_latest_nanobot_intent
        intent = get_latest_nanobot_intent()
        if isinstance(intent, dict):
            return str(intent.get("stage") or "").strip()
    except Exception:
        pass
    try:
        from core.tools.context import get_current_assistant_thread_context
        ctx = get_current_assistant_thread_context() or {}
        intent = ctx.get("intent") or {}
        if isinstance(intent, dict):
            return str(intent.get("stage") or "").strip()
    except Exception:
        pass
    return ""


def _extract_json_from_markdown(text: str) -> str:
    """从 markdown 代码块中提取 JSON 字符串。"""
    clean = str(text or "").strip()
    if clean.startswith("```"):
        # 去掉首行的 ```json / ```
        lines = clean.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return clean


def _humanize_plan_id(plan_id: str) -> str:
    """把内部 plan_id 翻译成用户可读的方案名。"""
    mapping = {
        "direct": "推荐完整交付",
        "strict": "保守可追溯版",
        "enhanced": "扩展增强版",
        "complete": "完整方案",
        "quick": "快速方案",
        "narrow": "缩小范围",
    }
    return mapping.get(str(plan_id or "").strip().lower(), "方案")


def _to_str_list(value: Any) -> list[str]:
    """将任意值转换为字符串列表。

    - None / 空值 → []
    - list / tuple → 逐项 str() 并过滤空值
    - 其它 → [str(value)] （过滤空值）
    """
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        result: list[str] = []
        for item in value:
            text = str(item or "").strip()
            if text:
                result.append(text)
        return result
    text = str(value or "").strip()
    return [text] if text else []


def _fallback_build_plans(blocking_gaps: list[Any], non_blocking_gaps: list[Any]) -> dict[str, Any]:
    """当 LLM 解析失败时的规则化方案生成。"""
    blocking_count = len(blocking_gaps)
    blocking_descriptions = []
    for g in blocking_gaps:
        if isinstance(g, dict):
            desc = str(g.get("description") or g.get("gap") or "")
        else:
            desc = str(g)
        if desc:
            blocking_descriptions.append(desc)

    if blocking_count == 0:
        candidate_plans = [
            {
                "plan_id": "direct",
                "plan_name": "推荐完整交付",
                "description": "现有能力已覆盖需求，可直接生成完整版 Agent，并按原定核心风险/分析维度进入真数据测试。",
                "required_new_skills": [],
                "estimated_effort": "低",
                "risk": "能力已覆盖，主要风险来自真实数据质量和后续验收结果。",
                "gap_summary": "所有分析维度均有直接工具支撑，无数据缺口。",
                "feasibility": "可直接实现，无需额外开发。",
                "recommended": True,
            },
            {
                "plan_id": "strict",
                "plan_name": "保守可追溯版",
                "description": "仍使用现有能力，但收紧输出边界：只输出工具和数据明确支撑的结论，未覆盖或数据不足的部分标注为信息缺口。",
                "required_new_skills": [],
                "estimated_effort": "低",
                "risk": "覆盖更稳健，但报告表达会更保守，部分扩展解读不会展开。",
                "gap_summary": "所有分析维度均有直接工具支撑，但对推断性结论做严格限制。",
                "feasibility": "可直接实现，无需额外开发。",
                "recommended": False,
            },
            {
                "plan_id": "enhanced",
                "plan_name": "扩展增强版",
                "description": "在核心需求已满足的基础上，把非阻塞增强项作为可选扩展，例如更细的预警分级、更多风险信号或更丰富的情景说明。",
                "required_new_skills": [],
                "estimated_effort": "中",
                "risk": "不是当前交付的必要条件；如果扩展过多，可能增加测试和解释复杂度。",
                "gap_summary": "核心维度有直接工具支撑，扩展维度可能需要额外数据接入。",
                "feasibility": "可实现，但扩展部分需要额外开发和数据接入。",
                "recommended": False,
            },
        ]
        recommended_plan_id = "direct"
    elif blocking_count <= 2:
        candidate_plans = [
            {
                "plan_id": "complete",
                "plan_name": "完整方案",
                "description": f"补齐 {blocking_count} 个阻塞性能力缺口，输出完整功能。",
                "required_new_skills": blocking_descriptions,
                "estimated_effort": "高",
                "risk": "需要生成新能力，可能失败或耗时",
                "gap_summary": f"有 {blocking_count} 个阻塞性缺口需要补齐，补齐后所有维度均可覆盖。",
                "feasibility": f"需要新建 Skill 补齐 {blocking_count} 个缺口，可能失败或耗时。补齐方式：新建 Skill 或接入外部数据源。",
                "recommended": True,
            },
            {
                "plan_id": "quick",
                "plan_name": "快速方案",
                "description": "用现有能力做简化版，跳过暂缺的能力。",
                "required_new_skills": [],
                "estimated_effort": "低",
                "risk": "功能不完整，部分输出会降级或省略",
                "gap_summary": f"有 {blocking_count} 个维度无法覆盖，将标注为'数据不足'或做降级处理。",
                "feasibility": "可直接实现，但部分分析维度会缺失或降级。",
                "recommended": False,
            },
        ]
        recommended_plan_id = "complete"
    else:
        candidate_plans = [
            {
                "plan_id": "complete",
                "plan_name": "完整方案",
                "description": f"补齐 {blocking_count} 个阻塞性能力缺口，输出完整功能。",
                "required_new_skills": blocking_descriptions,
                "estimated_effort": "高",
                "risk": "需要生成多个新能力，周期较长",
                "gap_summary": f"有 {blocking_count} 个阻塞性缺口需要补齐，补齐后所有维度均可覆盖。",
                "feasibility": f"需要新建多个 Skill 补齐 {blocking_count} 个缺口，周期较长，可能失败。补齐方式：新建 Skill 或接入外部数据源。",
                "recommended": True,
            },
            {
                "plan_id": "quick",
                "plan_name": "快速方案",
                "description": "用现有能力做简化版，优先覆盖核心维度。",
                "required_new_skills": [],
                "estimated_effort": "低",
                "risk": "功能不完整，部分输出会降级或省略",
                "gap_summary": f"有 {blocking_count} 个维度无法覆盖，将标注为'数据不足'或做降级处理。",
                "feasibility": "可直接实现，但多个分析维度会缺失或降级。",
                "recommended": False,
            },
            {
                "plan_id": "narrow",
                "plan_name": "缩小范围",
                "description": "把需求范围缩小到现有能力可覆盖的子集。",
                "required_new_skills": [],
                "estimated_effort": "低",
                "risk": "只覆盖部分需求",
                "gap_summary": f"缩小范围后，只覆盖现有能力可支撑的维度，{blocking_count} 个缺口维度不在范围内。",
                "feasibility": "可实现，但需要缩小 Agent 的职责范围。",
                "recommended": False,
            },
        ]
        recommended_plan_id = "complete"

    return {
        "candidate_plans": candidate_plans,
        "recommended_plan_id": recommended_plan_id,
        "pending_question": "你希望采用哪个方案？",
    }
