"""
Agent 工坊服务

Phase 1 目标：
- 启动会话
- 多轮澄清
- 结构化 AgentSpec 草案
- 预览规格
- 基础资源缺口分析
"""

import logging
import json
import re
import uuid
from difflib import SequenceMatcher
from pathlib import Path
from threading import Lock
from time import perf_counter
from typing import Any, Dict, List, Optional, Tuple

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.prompt_template import PromptTemplateCreate, TemplateContent
from app.models.agent_workshop import (
    AgentCapabilityRequirement,
    AgentBenchmarkCase,
    AgentBenchmarkSampleSet,
    AgentExecutionPlanStep,
    AgentExecutionValidationPlan,
    AgentSpec,
    AgentSpecIOField,
    AgentSpecStatus,
    AgentEvaluationReport,
    AgentVersion,
    AgentVersionStatus,
    AgentWorkshopGapAnalysis,
    AgentWorkshopMessage,
    AgentWorkshopSession,
    AgentWorkshopStage,
    SuggestedToolItem,
)
from app.services.capability_index_service import CapabilityIndexService
from app.services.prompt_template_service import PromptTemplateService
from app.utils.timezone import now_tz
from core.agents.config import AgentCategory, AgentInput, AgentMaintenanceStatus, AgentMetadata, AgentOutput, LicenseTier
from core.llm import UnifiedLLMClient, Message
from core.tools import get_tool_registry
from core.tools.config import ToolCategory

logger = logging.getLogger(__name__)

GLOBAL_NO_TRADING_ADVICE_CONSTRAINT = (
    "全局铁律：禁止输出任何交易建议、买卖/持有判断、仓位建议、目标价、止损止盈、"
    "建仓区间、择时结论和其他可直接执行的操作性指令；只能提供研究结论、关键依据、风险揭示与情景分析。"
)

_AGENT_WORKSHOP_LLM_TRACE_LOCK = Lock()
_AGENT_WORKSHOP_LLM_TRACE_PATH = Path(__file__).resolve().parents[2] / "logs" / "agent_workshop_llm_full.log"

SPEC_COLLECTION = "agent_specs"
SESSION_COLLECTION = "agent_workshop_sessions"
VERSION_COLLECTION = "agent_versions"
EVALUATION_COLLECTION = "agent_evaluations"


class AgentWorkshopLLMStageError(Exception):
    def __init__(self, stage: str, message: str, raw_response: str = ""):
        super().__init__(message)
        self.stage = stage
        self.raw_response = raw_response


class AgentWorkshopService:
    """Agent 工坊服务层"""

    _LLM_TIMEOUT = 360

    def __init__(self, db: AsyncIOMotorDatabase):
        self._db = db
        self._llm_client: Optional[UnifiedLLMClient] = None
        self._llm_client_meta: Dict[str, Any] = {}

    def _append_llm_trace_file(
        self,
        event_type: str,
        stage: str,
        payload: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        try:
            _AGENT_WORKSHOP_LLM_TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
            block = {
                "timestamp": now_tz().isoformat(),
                "event_type": event_type,
                "stage": stage,
                "context": context or {},
                "payload": payload,
            }
            text = json.dumps(block, ensure_ascii=False, indent=2, default=str)
            with _AGENT_WORKSHOP_LLM_TRACE_LOCK:
                with _AGENT_WORKSHOP_LLM_TRACE_PATH.open("a", encoding="utf-8") as handle:
                    handle.write(text)
                    handle.write("\n\n")
        except Exception as exc:
            logger.warning("[AgentWorkshop] 写入独立 LLM trace 文件失败: %s", exc, exc_info=True)

    def _serialize_log_payload(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        try:
            return json.dumps(value, ensure_ascii=False, indent=2, default=str)
        except Exception:
            return str(value)

    def _format_log_context(self, context: Optional[Dict[str, Any]] = None) -> str:
        if not context:
            return ""
        parts: List[str] = []
        for key, value in context.items():
            if value is None:
                continue
            text = str(value).strip()
            if not text:
                continue
            parts.append(f"{key}={text}")
        return " ".join(parts)

    def _log_llm_exchange(
        self,
        stage: str,
        system_prompt: str,
        user_prompt: str,
        raw_response: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        context_text = self._format_log_context(context)
        prefix = f"[AgentWorkshop][{stage}]"
        if context_text:
            prefix = f"{prefix} {context_text}"
        logger.info("%s system_prompt:\n%s", prefix, system_prompt or "")
        logger.info("%s user_prompt:\n%s", prefix, user_prompt or "")
        logger.info("%s raw_response:\n%s", prefix, raw_response or "")
        self._append_llm_trace_file(
            event_type="llm_exchange",
            stage=stage,
            context=context,
            payload={
                "system_prompt": system_prompt or "",
                "user_prompt": user_prompt or "",
                "raw_response": raw_response or "",
            },
        )

    def _log_llm_request_prompts(
        self,
        stage: str,
        system_prompt: str,
        user_prompt: str,
        context: Optional[Dict[str, Any]] = None,
        extra_metrics: Optional[Dict[str, Any]] = None,
    ) -> None:
        context_text = self._format_log_context(context)
        prefix = f"[AgentWorkshop][{stage}]"
        if context_text:
            prefix = f"{prefix} {context_text}"
        metrics = {
            "system_prompt_chars": len(system_prompt or ""),
            "user_prompt_chars": len(user_prompt or ""),
            "system_prompt_lines": len((system_prompt or "").splitlines()),
            "user_prompt_lines": len((user_prompt or "").splitlines()),
        }
        if extra_metrics:
            metrics.update(extra_metrics)
        logger.info("%s prompt_metrics: %s", prefix, self._serialize_log_payload(metrics))
        logger.info("%s system_prompt:\n%s", prefix, system_prompt or "")
        logger.info("%s user_prompt:\n%s", prefix, user_prompt or "")
        self._append_llm_trace_file(
            event_type="llm_request",
            stage=stage,
            context=context,
            payload={
                "metrics": metrics,
                "system_prompt": system_prompt or "",
                "user_prompt": user_prompt or "",
            },
        )

    def _log_generated_result(self, stage: str, result: Any, context: Optional[Dict[str, Any]] = None) -> None:
        context_text = self._format_log_context(context)
        prefix = f"[AgentWorkshop][{stage}]"
        if context_text:
            prefix = f"{prefix} {context_text}"
        logger.info("%s generated_result:\n%s", prefix, self._serialize_log_payload(result))
        self._append_llm_trace_file(
            event_type="generated_result",
            stage=stage,
            context=context,
            payload={
                "result": result,
            },
        )

    def _log_llm_failure(
        self,
        stage: str,
        error_message: str,
        raw_response: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        context_text = self._format_log_context(context)
        prefix = f"[AgentWorkshop][{stage}]"
        if context_text:
            prefix = f"{prefix} {context_text}"
        logger.error("%s llm_failure: %s", prefix, error_message)
        if raw_response:
            logger.error("%s llm_failure_raw_response:\n%s", prefix, raw_response)
        self._append_llm_trace_file(
            event_type="llm_failure",
            stage=stage,
            context=context,
            payload={
                "error_message": error_message,
                "raw_response": raw_response or "",
            },
        )

    def _get_llm_runtime_config(self, client: UnifiedLLMClient) -> Dict[str, Any]:
        adapter = getattr(client, "_adapter", None)
        config = getattr(adapter, "config", None)
        provider = getattr(config, "provider", None)
        model = getattr(config, "model", None)
        return {
            "provider": str(provider or ""),
            "model": str(model or ""),
            "timeout_seconds": getattr(config, "timeout", None),
            "retry_times": getattr(config, "retry_times", None),
        }

    def _summarize_capability_snapshot(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        totals = snapshot.get("totals", {}) if isinstance(snapshot, dict) else {}
        return {
            "builtin_data_tools": len(snapshot.get("builtin_data_tools", []) or []),
            "builtin_analysis_tools": len(snapshot.get("builtin_analysis_tools", []) or []),
            "external_data_skills": len(snapshot.get("external_data_skills", []) or []),
            "external_analysis_skills": len(snapshot.get("external_analysis_skills", []) or []),
            "valuation_tools": len(snapshot.get("valuation_tools", []) or []),
            "valuation_skills": len(snapshot.get("valuation_skills", []) or []),
            "builtin_tools_total": int(totals.get("builtin_tools", 0) or 0),
            "external_skills_total": int(totals.get("external_skills", 0) or 0),
            "indexed_capabilities": int(totals.get("indexed_capabilities", 0) or 0),
            "retrieved_capabilities": int(totals.get("retrieved_capabilities", 0) or 0),
        }

    async def start_session(self, description: str, user_id: str = "") -> Dict[str, Any]:
        turn_result = await self._analyze_requirement_turn([description], user_id=user_id)
        spec = turn_result["spec"]
        session_id = str(uuid.uuid4())
        pending_questions = turn_result["pending_questions"]
        completeness_score = turn_result["completeness_score"]
        ai_message = turn_result["ai_message"]
        feasibility_status = turn_result["feasibility_status"]
        refusal_reason = turn_result["refusal_reason"]

        session = AgentWorkshopSession(
            session_id=session_id,
            spec_id=spec.spec_id,
            user_id=user_id,
            stage=self._infer_stage(feasibility_status, completeness_score),
            current_round=1,
            messages=[
                AgentWorkshopMessage(role="user", content=description),
                AgentWorkshopMessage(role="assistant", content=ai_message),
            ],
            current_spec_snapshot=spec,
            pending_questions=pending_questions,
            completeness_score=completeness_score,
            feasibility_status=feasibility_status,
            refusal_reason=refusal_reason,
        )

        await self._save_spec(spec, session_id=session_id)
        await self._save_session(session)

        return {
            "session_id": session.session_id,
            "spec_id": spec.spec_id,
            "ai_message": ai_message,
            "stage": session.stage.value,
            "current_round": session.current_round,
            "completeness_score": completeness_score,
            "feasibility_status": feasibility_status,
            "refusal_reason": refusal_reason,
            "pending_questions": pending_questions,
            "spec_overview": self._build_spec_overview(spec),
        }

    async def create_nanobot_draft(
        self,
        *,
        agent_id: str,
        agent_name: str,
        target_responsibility: str,
        output_field: str = "analysis_report",
        tool_ids: Optional[List[str]] = None,
        non_goals: Optional[List[str]] = None,
        preferred_methods: Optional[List[str]] = None,
        constraints: Optional[List[str]] = None,
        owner_user_id: str = "",
        source_thread_id: str = "",
    ) -> Dict[str, Any]:
        clean_agent_id = str(agent_id or "").strip()
        clean_agent_name = str(agent_name or "").strip()
        clean_responsibility = str(target_responsibility or "").strip()
        clean_output_field = str(output_field or "analysis_report").strip() or "analysis_report"
        if not clean_agent_id or not clean_agent_name or not clean_responsibility:
            raise ValueError("agent_id、agent_name、target_responsibility 不能为空")

        spec_id = self._build_nanobot_spec_id(clean_agent_id)
        session_id = str(uuid.uuid4())

        existing_doc = await self._db[SPEC_COLLECTION].find_one({"spec_id": spec_id})
        existing_spec = AgentSpec(**existing_doc) if existing_doc else None

        normalized_non_goals = self._normalize_unique_list(non_goals)
        normalized_methods = self._normalize_unique_list(preferred_methods)
        normalized_constraints = self._normalize_unique_list(constraints)
        normalized_tools = self._normalize_unique_list(tool_ids)

        if GLOBAL_NO_TRADING_ADVICE_CONSTRAINT not in normalized_constraints:
            normalized_constraints.append(GLOBAL_NO_TRADING_ADVICE_CONSTRAINT)

        spec = AgentSpec(
            spec_id=spec_id,
            name=clean_agent_name,
            domain=self._infer_nanobot_spec_domain(clean_agent_name, clean_responsibility, normalized_methods),
            primary_goal=clean_responsibility,
            responsibilities=[clean_responsibility],
            non_goals=normalized_non_goals,
            inputs=existing_spec.inputs if existing_spec and existing_spec.inputs else ["user_request", "symbol"],
            outputs=existing_spec.outputs if existing_spec and existing_spec.outputs else [clean_output_field],
            constraints=normalized_constraints,
            preferred_methods=normalized_methods,
            success_criteria=existing_spec.success_criteria if existing_spec else [],
            capability_requirements=existing_spec.capability_requirements if existing_spec else [],
            sample_symbols=existing_spec.sample_symbols if existing_spec else [],
            status=existing_spec.status if existing_spec else AgentSpecStatus.DRAFT,
            source="nanobot",
            owner_user_id=owner_user_id or (existing_spec.owner_user_id if existing_spec else ""),
            latest_session_id=session_id,
            current_version_id=existing_spec.current_version_id if existing_spec else None,
            version_count=existing_spec.version_count if existing_spec else 0,
            created_at=existing_spec.created_at if existing_spec else now_tz(),
        )

        summary_lines = [
            f"Nanobot 已将候选 Agent 同步为 Agent 工坊 Draft：{clean_agent_name}（{clean_agent_id}）。",
            f"单一职责：{clean_responsibility}",
            f"输出字段：{clean_output_field}",
        ]
        if normalized_tools:
            summary_lines.append(f"候选工具：{'、'.join(normalized_tools)}")
        if normalized_non_goals:
            summary_lines.append(f"非目标：{'、'.join(normalized_non_goals)}")
        if normalized_methods:
            summary_lines.append(f"方法范围：{'、'.join(normalized_methods)}")
        if source_thread_id:
            summary_lines.append(f"来源线程：{source_thread_id}")

        session = AgentWorkshopSession(
            session_id=session_id,
            spec_id=spec.spec_id,
            user_id=spec.owner_user_id,
            stage=self._infer_stage("feasible", 1.0),
            current_round=1,
            messages=[
                AgentWorkshopMessage(
                    role="user",
                    content=self._build_nanobot_draft_user_message(
                        agent_id=clean_agent_id,
                        agent_name=clean_agent_name,
                        target_responsibility=clean_responsibility,
                        output_field=clean_output_field,
                        tool_ids=normalized_tools,
                        non_goals=normalized_non_goals,
                        preferred_methods=normalized_methods,
                    ),
                ),
                AgentWorkshopMessage(role="assistant", content="\n".join(summary_lines)),
            ],
            current_spec_snapshot=spec,
            pending_questions=[],
            completeness_score=1.0,
            feasibility_status="feasible",
            refusal_reason="",
        )

        await self._save_spec(spec, session_id=session.session_id)
        await self._save_session(session)

        return {
            "session_id": session.session_id,
            "spec_id": spec.spec_id,
            "stage": session.stage.value,
            "status": spec.status.value,
            "source": spec.source,
            "owner_user_id": spec.owner_user_id,
            "linked_agent_id": clean_agent_id,
            "output_field": clean_output_field,
            "tool_ids": normalized_tools,
            "updated_existing_spec": existing_spec is not None,
            "spec_overview": self._build_spec_overview(spec),
        }

    async def respond(self, session_id: str, message: str) -> Dict[str, Any]:
        session = await self._load_session(session_id)
        if not session:
            raise ValueError(f"会话 {session_id} 不存在")

        user_messages = self._collect_user_messages(session)
        user_messages.append(message)

        turn_result = await self._analyze_requirement_turn(
            user_messages,
            user_id=session.user_id,
            fallback_spec_id=session.spec_id,
            existing_spec=session.current_spec_snapshot,
        )
        spec = turn_result["spec"]
        pending_questions = turn_result["pending_questions"]
        completeness_score = turn_result["completeness_score"]
        stage = self._infer_stage(turn_result["feasibility_status"], completeness_score)
        ai_message = turn_result["ai_message"]

        session.current_round += 1
        session.stage = stage
        session.current_spec_snapshot = spec
        session.pending_questions = pending_questions
        session.completeness_score = completeness_score
        session.feasibility_status = turn_result["feasibility_status"]
        session.refusal_reason = turn_result["refusal_reason"]
        session.updated_at = now_tz()
        session.messages.append(AgentWorkshopMessage(role="user", content=message))
        session.messages.append(AgentWorkshopMessage(role="assistant", content=ai_message))

        await self._save_spec(spec, session_id=session.session_id)
        await self._save_session(session)

        return {
            "session_id": session.session_id,
            "spec_id": spec.spec_id,
            "ai_message": ai_message,
            "stage": stage.value,
            "current_round": session.current_round,
            "completeness_score": completeness_score,
            "feasibility_status": session.feasibility_status,
            "refusal_reason": session.refusal_reason,
            "pending_questions": pending_questions,
            "spec_overview": self._build_spec_overview(spec),
        }

    async def preview_spec(self, session_id: str, message: str = "确认") -> Dict[str, Any]:
        session = await self._load_session(session_id)
        if not session:
            raise ValueError(f"会话 {session_id} 不存在")

        user_messages = self._collect_user_messages(session)
        if message and message.strip() and message.strip() != "确认":
            user_messages.append(message.strip())

        turn_result = await self._analyze_requirement_turn(
            user_messages,
            user_id=session.user_id,
            fallback_spec_id=session.spec_id,
            existing_spec=session.current_spec_snapshot,
        )
        spec = turn_result["spec"]
        pending_questions = turn_result["pending_questions"]
        completeness_score = turn_result["completeness_score"]

        session.current_spec_snapshot = spec
        session.pending_questions = pending_questions
        session.completeness_score = completeness_score
        session.feasibility_status = turn_result["feasibility_status"]
        session.refusal_reason = turn_result["refusal_reason"]
        session.stage = self._infer_stage(session.feasibility_status, completeness_score)
        session.updated_at = now_tz()

        await self._save_spec(spec, session_id=session.session_id)
        await self._save_session(session)

        return {
            "spec": spec,
            "completeness_score": completeness_score,
            "pending_questions": pending_questions,
            "feasibility_status": session.feasibility_status,
            "refusal_reason": session.refusal_reason,
            "readiness": self._build_readiness(session.feasibility_status, completeness_score),
        }

    async def analyze_gaps(self, session_id: str) -> Dict[str, Any]:
        session = await self._load_session(session_id)
        if not session:
            raise ValueError(f"会话 {session_id} 不存在")
        self._ensure_session_can_continue(session)

        logger.info(
            "[AgentWorkshop] 开始缺口分析: session_id=%s spec_id=%s spec_name=%s %s",
            session.session_id,
            session.spec_id,
            session.current_spec_snapshot.name,
            self._format_gap_analysis_llm_log(),
        )

        gap_report = await self._build_gap_analysis(session.current_spec_snapshot)
        session.stage = AgentWorkshopStage.GAP_ANALYSIS
        session.gap_report = gap_report
        session.updated_at = now_tz()
        await self._save_session(session)

        logger.info(
            "[AgentWorkshop] 缺口分析完成: session_id=%s spec_id=%s mode=%s existing_tools=%s suggested_tools=%s blocking_gaps=%s %s",
            session.session_id,
            session.spec_id,
            self._detect_gap_analysis_mode(gap_report),
            len(gap_report.existing_tools or []),
            len(gap_report.suggested_tools or []),
            len(gap_report.blocking_gaps or []),
            self._format_gap_analysis_llm_log(),
        )

        return {
            "session_id": session_id,
            "spec_id": session.spec_id,
            "gap_report": gap_report,
        }

    async def generate_tooling_plan(self, session_id: str) -> Dict[str, Any]:
        session = await self._load_session(session_id)
        if not session:
            raise ValueError(f"会话 {session_id} 不存在")
        self._ensure_session_can_continue(session)

        spec = session.current_spec_snapshot
        if session.gap_report is None:
            session.gap_report = await self._build_gap_analysis(spec)

        tooling_plan: Dict[str, Any]
        try:
            tooling_plan = await self._generate_tooling_plan_with_llm(spec, session.gap_report)
        except Exception as exc:
            logger.warning("[AgentWorkshop] 生成工具需求草案时 LLM 失败，直接暴露错误: %s", exc, exc_info=True)
            raw_response = exc.raw_response if isinstance(exc, AgentWorkshopLLMStageError) else ""
            tooling_plan = self._build_tooling_plan_error_report(
                spec,
                session.gap_report,
                error_message=str(exc),
                raw_response=raw_response,
            )

        session.tooling_plan = tooling_plan
        session.updated_at = now_tz()
        await self._save_session(session)

        return {
            "session_id": session.session_id,
            "spec_id": session.spec_id,
            "tooling_plan": tooling_plan,
        }

    async def build_version(self, session_id: str) -> Dict[str, Any]:
        session = await self._load_session(session_id)
        if not session:
            raise ValueError(f"会话 {session_id} 不存在")
        self._ensure_session_can_continue(session)

        spec = session.current_spec_snapshot
        if session.gap_report is None:
            session.gap_report = await self._build_gap_analysis(spec)

        version_number = await self._get_next_version_number(spec.spec_id)
        version_id = f"{spec.spec_id}_v{version_number}"

        required_tools = self._select_required_tools(spec, session.gap_report)
        capability_snapshot = await self._collect_capability_snapshot(self._build_valuation_requirement_text(spec))
        required_capabilities = self._select_required_capabilities(session.gap_report, session.tooling_plan, capability_snapshot)
        output_schema = self._build_output_schema(spec)
        evaluation_policy = self._build_evaluation_policy(spec)
        execution_plan = self._build_execution_validation_plan(
            spec,
            required_tools,
            output_schema,
            gap_report=session.gap_report,
            tooling_plan=session.tooling_plan,
        )
        evaluation_policy["creation_mode"] = "execution-first"
        evaluation_policy["execution_validation_required"] = True
        evaluation_policy["execution_validation_status"] = execution_plan.validation_status
        prompt_template = await self._create_prompt_template(
            version_id,
            spec,
            required_tools,
            gap_report=session.gap_report,
            tooling_plan=session.tooling_plan,
        )
        metadata = self._build_agent_metadata(version_id, spec, required_tools)

        version = AgentVersion(
            version_id=version_id,
            spec_id=spec.spec_id,
            version=version_number,
            status=AgentVersionStatus.DRAFT,
            agent_metadata=metadata,
            prompt_template_ref=prompt_template,
            required_tools=required_tools,
            required_capabilities=required_capabilities,
            output_schema=output_schema,
            evaluation_policy=evaluation_policy,
            execution_plan=execution_plan,
            published_from_session_id=session.session_id,
        )

        await self._save_version(version)

        session.stage = AgentWorkshopStage.BUILDING
        session.proposed_version = version.model_dump(mode="json", by_alias=True)
        session.updated_at = now_tz()
        await self._save_session(session)

        spec.version_count = max(spec.version_count, version_number)
        spec.current_version_id = version.version_id
        spec.latest_session_id = session.session_id
        spec.updated_at = now_tz()
        await self._save_spec(spec, session_id=session.session_id)

        return {
            "session_id": session.session_id,
            "spec_id": spec.spec_id,
            "version": version,
        }

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        doc = await self._db[SESSION_COLLECTION].find_one({"session_id": session_id})
        if not doc:
            return None
        doc.pop("_id", None)
        return doc

    async def list_sessions(
        self,
        stage: Optional[str] = None,
        user_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        query: Dict[str, Any] = {}
        if stage:
            query["stage"] = {"$in": [item.strip() for item in stage.split(",") if item.strip()]}
        if user_id:
            query["user_id"] = user_id

        total = await self._db[SESSION_COLLECTION].count_documents(query)
        cursor = (
            self._db[SESSION_COLLECTION]
            .find(query)
            .sort("updated_at", -1)
            .skip((page - 1) * page_size)
            .limit(page_size)
        )
        items: List[Dict[str, Any]] = []
        async for doc in cursor:
            doc.pop("_id", None)
            items.append(doc)

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": items,
        }

    async def delete_session(self, session_id: str) -> bool:
        result = await self._db[SESSION_COLLECTION].delete_one({"session_id": session_id})
        return result.deleted_count > 0

    async def list_specs(
        self,
        status: Optional[str] = None,
        user_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        query: Dict[str, Any] = {}
        if status:
            query["status"] = {"$in": [item.strip() for item in status.split(",") if item.strip()]}
        if user_id:
            query["owner_user_id"] = user_id

        total = await self._db[SPEC_COLLECTION].count_documents(query)
        cursor = (
            self._db[SPEC_COLLECTION]
            .find(query)
            .sort("updated_at", -1)
            .skip((page - 1) * page_size)
            .limit(page_size)
        )
        items: List[Dict[str, Any]] = []
        async for doc in cursor:
            doc.pop("_id", None)
            items.append(doc)

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": items,
        }

    async def get_spec(self, spec_id: str) -> Optional[Dict[str, Any]]:
        doc = await self._db[SPEC_COLLECTION].find_one({"spec_id": spec_id})
        if not doc:
            return None
        doc.pop("_id", None)
        return doc

    async def delete_spec(self, spec_id: str) -> Dict[str, Any]:
        spec_doc = await self._db[SPEC_COLLECTION].find_one({"spec_id": spec_id})
        if not spec_doc:
            return {"deleted": False, "spec_id": spec_id}

        version_docs = await self._db[VERSION_COLLECTION].find({"spec_id": spec_id}).to_list(length=200)
        version_ids = [item.get("version_id") for item in version_docs if item.get("version_id")]
        runtime_agent_ids: List[str] = []

        for item in version_docs:
            agent_metadata = item.get("agent_metadata") or {}
            agent_id = str(agent_metadata.get("id") or item.get("version_id") or "").strip()
            if agent_id:
                runtime_agent_ids.append(agent_id)

        prompt_template_ids: List[str] = []
        for item in version_docs:
            template_ref = item.get("prompt_template_ref") or {}
            template_id = template_ref.get("template_id")
            if template_id:
                prompt_template_ids.append(str(template_id))

        deleted_sessions = await self._db[SESSION_COLLECTION].delete_many({"spec_id": spec_id})
        deleted_versions = await self._db[VERSION_COLLECTION].delete_many({"spec_id": spec_id})
        deleted_evaluations = await self._db[EVALUATION_COLLECTION].delete_many({"version_id": {"$in": version_ids}}) if version_ids else None
        deleted_prompts = await self._db["prompt_templates"].delete_many({"_id": {"$in": prompt_template_ids}}) if prompt_template_ids else None
        deleted_runtime_configs = await self._db["agent_configs"].delete_many({"agent_id": {"$in": runtime_agent_ids}}) if runtime_agent_ids else None
        deleted_runtime_bindings = await self._db["tool_agent_bindings"].delete_many({"agent_id": {"$in": runtime_agent_ids}}) if runtime_agent_ids else None
        deleted_spec = await self._db[SPEC_COLLECTION].delete_one({"spec_id": spec_id})

        return {
            "deleted": deleted_spec.deleted_count > 0,
            "spec_id": spec_id,
            "deleted_sessions": deleted_sessions.deleted_count,
            "deleted_versions": deleted_versions.deleted_count,
            "deleted_evaluations": deleted_evaluations.deleted_count if deleted_evaluations is not None else 0,
            "deleted_prompts": deleted_prompts.deleted_count if deleted_prompts is not None else 0,
            "deleted_runtime_configs": deleted_runtime_configs.deleted_count if deleted_runtime_configs is not None else 0,
            "deleted_runtime_bindings": deleted_runtime_bindings.deleted_count if deleted_runtime_bindings is not None else 0,
        }

    async def list_sample_sets(self, spec_id: str) -> Dict[str, Any]:
        spec_doc = await self._db[SPEC_COLLECTION].find_one({"spec_id": spec_id})
        if not spec_doc:
            raise ValueError(f"规格 {spec_id} 不存在")
        spec = AgentSpec(**spec_doc)
        sample_sets = self._build_sample_sets_for_spec(spec)
        return {
            "spec_id": spec_id,
            "items": [sample_set.model_dump(mode="json") for sample_set in sample_sets],
        }

    async def list_versions(
        self,
        spec_id: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        query: Dict[str, Any] = {}
        if spec_id:
            query["spec_id"] = spec_id
        if status:
            query["status"] = {"$in": [item.strip() for item in status.split(",") if item.strip()]}

        total = await self._db[VERSION_COLLECTION].count_documents(query)
        cursor = (
            self._db[VERSION_COLLECTION]
            .find(query)
            .sort([("spec_id", 1), ("version", -1)])
            .skip((page - 1) * page_size)
            .limit(page_size)
        )
        items: List[Dict[str, Any]] = []
        async for doc in cursor:
            doc.pop("_id", None)
            items.append(doc)

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": items,
        }

    async def get_version(self, version_id: str) -> Optional[Dict[str, Any]]:
        doc = await self._db[VERSION_COLLECTION].find_one({"version_id": version_id})
        if not doc:
            return None
        doc.pop("_id", None)
        return doc

    async def evaluate_version(
        self,
        version_id: str,
        evaluation_type: str = "sandbox",
        sample_set_id: Optional[str] = None,
        user_feedback: str = "",
        benchmark_outputs: Optional[List[Dict[str, Any]]] = None,
        runtime_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        version_doc = await self._db[VERSION_COLLECTION].find_one({"version_id": version_id})
        if not version_doc:
            raise ValueError(f"版本 {version_id} 不存在")

        version = AgentVersion(**version_doc)
        spec_doc = await self._db[SPEC_COLLECTION].find_one({"spec_id": version.spec_id})
        if not spec_doc:
            raise ValueError(f"规格 {version.spec_id} 不存在")
        spec = AgentSpec(**spec_doc)

        evaluation_details: Dict[str, Any] = {}
        if evaluation_type == "benchmark":
            raise ValueError("样本基准评估已暂时禁用，请改用真实结果评估。")
        elif evaluation_type == "production-review":
            scores, issues, recommendations, evaluation_details = await self._evaluate_runtime_result(
                version,
                spec,
                runtime_result or {},
                user_feedback=user_feedback,
            )
        else:
            scores = self._calculate_evaluation_scores(version, spec, user_feedback=user_feedback)
            issues = self._build_evaluation_issues(version, spec, scores, user_feedback=user_feedback)
            recommendations = self._build_evaluation_recommendations(version, spec, scores, issues)
        overall_score = round(sum(scores.values()) / len(scores), 2) if scores else 0.0
        minimum_score = float((version.evaluation_policy or {}).get("minimum_score", 0.75))
        decision = self._decide_evaluation(overall_score, minimum_score, issues)

        report = AgentEvaluationReport(
            evaluation_id=str(uuid.uuid4()),
            version_id=version.version_id,
            evaluation_type=evaluation_type,
            sample_set_id=sample_set_id,
            scores={**scores, "overall": overall_score},
            issues=issues,
            recommendations=recommendations,
            details=evaluation_details,
            decision=decision,
        )

        await self._save_evaluation(report)

        if decision == "pass" and version.status == AgentVersionStatus.DRAFT:
            version.status = AgentVersionStatus.TESTING
            version.updated_at = now_tz()
            await self._save_version(version)

        # 更新关联 session 的 stage 为 EVALUATING
        if spec.latest_session_id:
            session_doc = await self._db[SESSION_COLLECTION].find_one({"session_id": spec.latest_session_id})
            if session_doc:
                session = AgentWorkshopSession(**session_doc)
                session.stage = AgentWorkshopStage.EVALUATING
                session.updated_at = now_tz()
                await self._save_session(session)

        return {
            "version_id": version.version_id,
            "evaluation": report,
        }

    async def publish_version(self, version_id: str) -> Dict[str, Any]:
        """将版本从 testing 状态发布为 active，并更新关联 Spec 的 current_version_id"""
        version_doc = await self._db[VERSION_COLLECTION].find_one({"version_id": version_id})
        if not version_doc:
            raise ValueError(f"版本 {version_id} 不存在")

        version = AgentVersion(**version_doc)
        if version.status != AgentVersionStatus.TESTING:
            raise ValueError(
                f"版本 {version_id} 当前状态为 {version.status.value}，只有 testing 状态的版本可以发布"
            )

        spec_doc = await self._db[SPEC_COLLECTION].find_one({"spec_id": version.spec_id})
        if not spec_doc:
            raise ValueError(f"规格 {version.spec_id} 不存在")
        spec = AgentSpec(**spec_doc)

        # 将之前 active 的版本归档
        await self._db[VERSION_COLLECTION].update_many(
            {"spec_id": spec.spec_id, "status": AgentVersionStatus.ACTIVE.value},
            {"$set": {"status": AgentVersionStatus.ARCHIVED.value, "updated_at": now_tz().isoformat()}},
        )

        # 更新版本状态为 active
        version.status = AgentVersionStatus.ACTIVE
        version.updated_at = now_tz()
        await self._save_version(version)

        # 注册到 agent_configs，确保发布的 Agent 能被工作流引擎调度
        await self._ensure_runtime_agent_config(version, spec)

        # 更新 Spec 的 current_version_id 和状态
        spec.current_version_id = version.version_id
        spec.status = AgentSpecStatus.ACTIVE
        await self._save_spec(spec)

        # 更新关联 session 的 stage 为 COMPLETED
        if spec.latest_session_id:
            session_doc = await self._db[SESSION_COLLECTION].find_one({"session_id": spec.latest_session_id})
            if session_doc:
                session = AgentWorkshopSession(**session_doc)
                session.stage = AgentWorkshopStage.COMPLETED
                session.updated_at = now_tz()
                await self._save_session(session)

        logger.info(
            "[AgentWorkshop] 版本发布成功: version_id=%s spec_id=%s",
            version.version_id,
            spec.spec_id,
        )

        return {
            "version_id": version.version_id,
            "spec_id": spec.spec_id,
            "status": version.status.value,
            "previous_active_archived": True,
        }

    async def list_evaluations(
        self,
        version_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        query = {"version_id": version_id}
        total = await self._db[EVALUATION_COLLECTION].count_documents(query)
        cursor = (
            self._db[EVALUATION_COLLECTION]
            .find(query)
            .sort("created_at", -1)
            .skip((page - 1) * page_size)
            .limit(page_size)
        )
        items: List[Dict[str, Any]] = []
        async for doc in cursor:
            doc.pop("_id", None)
            items.append(doc)

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": items,
        }

    async def iterate_version(self, version_id: str, feedback: str = "") -> Dict[str, Any]:
        version_doc = await self._db[VERSION_COLLECTION].find_one({"version_id": version_id})
        if not version_doc:
            raise ValueError(f"版本 {version_id} 不存在")

        version = AgentVersion(**version_doc)
        spec_doc = await self._db[SPEC_COLLECTION].find_one({"spec_id": version.spec_id})
        if not spec_doc:
            raise ValueError(f"规格 {version.spec_id} 不存在")
        spec = AgentSpec(**spec_doc)

        evaluation_doc = await self._db[EVALUATION_COLLECTION].find_one(
            {"version_id": version_id},
            sort=[("created_at", -1)],
        )
        latest_evaluation = AgentEvaluationReport(**evaluation_doc) if evaluation_doc else None

        issue_summary = latest_evaluation.issues if latest_evaluation else []
        recommendation_summary = latest_evaluation.recommendations if latest_evaluation else []

        iterate_description = self._build_iteration_description(
            spec,
            version,
            issue_summary,
            recommendation_summary,
            feedback,
        )
        result = await self.start_session(iterate_description, user_id=spec.owner_user_id)

        new_session = await self._load_session(result["session_id"])
        if new_session and latest_evaluation:
            reminder = self._build_iteration_reminder(latest_evaluation, feedback)
            new_session.messages.append(AgentWorkshopMessage(role="assistant", content=reminder))
            new_session.pending_questions = self._dedupe([
                *recommendation_summary[:3],
                *new_session.pending_questions,
            ])[:4]
            new_session.updated_at = now_tz()
            await self._save_session(new_session)

        return {
            "source_version_id": version_id,
            "session_id": result["session_id"],
            "spec_id": result["spec_id"],
            "ai_message": result["ai_message"],
        }

    async def get_version_prompt(self, version_id: str) -> Dict[str, Any]:
        """获取版本关联的提示词模板完整内容"""
        version_doc = await self._db[VERSION_COLLECTION].find_one({"version_id": version_id})
        if not version_doc:
            raise ValueError(f"版本 {version_id} 不存在")
        version = AgentVersion(**version_doc)

        template_id = str(version.prompt_template_ref.get("template_id") or "").strip()
        if not template_id:
            return {
                "version_id": version_id,
                "template_id": None,
                "template_name": version.prompt_template_ref.get("template_name"),
                "status": version.prompt_template_ref.get("status"),
                "content": None,
                "message": "当前版本没有关联的提示词模板",
            }

        prompt_service = PromptTemplateService(db=self._db)
        template = await prompt_service.get_template(template_id)
        if not template:
            return {
                "version_id": version_id,
                "template_id": template_id,
                "template_name": version.prompt_template_ref.get("template_name"),
                "status": version.prompt_template_ref.get("status"),
                "content": None,
                "message": "提示词模板已被删除或不可访问",
            }

        return {
            "version_id": version_id,
            "template_id": str(template.id),
            "template_name": template.template_name,
            "status": template.status,
            "version": template.version,
            "content": template.content.model_dump() if template.content else None,
            "remark": template.remark,
            "created_at": template.created_at.isoformat() if template.created_at else None,
            "updated_at": template.updated_at.isoformat() if template.updated_at else None,
        }

    async def update_version_prompt(
        self,
        version_id: str,
        content: Dict[str, str],
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """更新版本关联的提示词模板内容，供用户在发布前审阅和调整"""
        version_doc = await self._db[VERSION_COLLECTION].find_one({"version_id": version_id})
        if not version_doc:
            raise ValueError(f"版本 {version_id} 不存在")
        version = AgentVersion(**version_doc)

        if version.status == AgentVersionStatus.ACTIVE:
            raise ValueError("已发布的版本不允许修改提示词，请创建新版本")
        if version.status == AgentVersionStatus.ARCHIVED:
            raise ValueError("已归档的版本不允许修改提示词")

        template_id = str(version.prompt_template_ref.get("template_id") or "").strip()
        if not template_id:
            raise ValueError("当前版本没有关联的提示词模板，请先构建版本")

        prompt_service = PromptTemplateService(db=self._db)
        template = await prompt_service.get_template(template_id)
        if not template:
            raise ValueError("提示词模板不存在或已被删除")

        from app.models.prompt_template import PromptTemplateUpdate, TemplateContent
        update_data = PromptTemplateUpdate(
            content=TemplateContent(**content),
            status=status or template.status,
        )

        # 工坊生成的模板 is_system=True（无 created_by），直接更新数据库绕过权限
        update_doc = {
            "content": update_data.content.model_dump(),
            "updated_at": now_tz(),
        }
        if status:
            update_doc["status"] = status
        update_doc["version"] = template.version + 1

        from bson import ObjectId as BsonObjectId
        await self._db["prompt_templates"].update_one(
            {"_id": BsonObjectId(template_id)},
            {"$set": update_doc},
        )

        # 同步更新 version 的 prompt_template_ref 状态
        if status and status != version.prompt_template_ref.get("status"):
            version.prompt_template_ref["status"] = status
            version.updated_at = now_tz()
            await self._save_version(version)

        logger.info(
            "[AgentWorkshop] 版本提示词已更新: version_id=%s template_id=%s",
            version_id,
            template_id,
        )

        updated_template = await prompt_service.get_template(template_id)
        return {
            "version_id": version_id,
            "template_id": template_id,
            "template_name": updated_template.template_name if updated_template else None,
            "status": updated_template.status if updated_template else status,
            "version": updated_template.version if updated_template else template.version + 1,
            "content": updated_template.content.model_dump() if updated_template and updated_template.content else content,
        }

    async def debug_version(
        self,
        version_id: str,
        llm: Dict[str, Any],
        stock: Dict[str, Any],
        user_goal: str = "",
        prompt_overrides: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        version_doc = await self._db[VERSION_COLLECTION].find_one({"version_id": version_id})
        if not version_doc:
            raise ValueError(f"版本 {version_id} 不存在")
        version = AgentVersion(**version_doc)

        spec_doc = await self._db[SPEC_COLLECTION].find_one({"spec_id": version.spec_id})
        if not spec_doc:
            raise ValueError(f"规格 {version.spec_id} 不存在")
        spec = AgentSpec(**spec_doc)

        symbol = str((stock or {}).get("symbol") or "").strip()
        sample_input = version.execution_plan.sample_input if version.execution_plan else {}
        if not symbol:
            symbol = str(sample_input.get("symbol") or "").strip()
        if not symbol:
            raise ValueError("stock.symbol 不能为空")

        llm_model = str((llm or {}).get("model") or "").strip()
        llm_provider = str((llm or {}).get("provider") or "").strip()
        if not llm_model:
            raise ValueError("llm.model 不能为空")
        if not llm_provider:
            raise ValueError("llm.provider 不能为空")

        template_id = str(version.prompt_template_ref.get("template_id") or "").strip()
        if not template_id:
            raise ValueError("当前版本还没有可调试的 Prompt 模板")

        await self._ensure_runtime_agent_config(version, spec)

        from app.services.simple_analysis_service import get_provider_and_url_by_model_sync
        from core.agents.config import AgentConfig
        from core.agents.factory import create_agent
        from core.api.workflow_api import WorkflowAPI
        from tradingagents.agents.utils.agent_context import AgentContext
        from tradingagents.graph.trading_graph import create_llm_by_provider

        backend_url = str(llm.get("backend_url") or "").strip() or None
        api_key = str(llm.get("api_key") or "").strip() or None
        if not backend_url:
            try:
                provider_info = get_provider_and_url_by_model_sync(llm_model)
                backend_url = provider_info.get("backend_url")
                api_key = api_key or provider_info.get("api_key")
            except Exception as exc:
                logger.warning("[AgentWorkshop] 获取模型后端地址失败，继续使用前端输入配置: %s", exc)

        timeout = 300 if llm_provider.lower() == "ollama" else 180
        llm_instance = create_llm_by_provider(
            provider=llm_provider,
            model=llm_model,
            temperature=float(llm.get("temperature") or 0.2),
            max_tokens=int(llm.get("max_tokens") or 4000),
            backend_url=backend_url,
            timeout=timeout,
            api_key=api_key,
        )

        analysis_date = str(stock.get("analysis_date") or now_tz().strftime("%Y-%m-%d"))
        if not stock.get("analysis_date") and sample_input.get("analysis_date"):
            analysis_date = str(sample_input.get("analysis_date") or analysis_date)
        market_type = str(stock.get("market_type") or sample_input.get("market_type") or "A股")
        task_description = user_goal or str(sample_input.get("task_description") or "").strip() or spec.primary_goal or spec.name

        ctx = AgentContext(
            user_id=spec.owner_user_id or "agent_workshop",
            preference_id="neutral",
            session_id=spec.latest_session_id,
            request_id=None,
            is_debug_mode=True,
            debug_template_id=template_id,
            workflow_id=None,
        )

        agent = create_agent(
            version.version_id,
            config=AgentConfig(
                temperature=float(llm.get("temperature") or 0.2),
                max_retries=3,
            ),
            llm=llm_instance,
            tool_ids=version.required_tools,
        )

        inputs: Dict[str, Any] = {
            "stock_symbol": symbol,
            "ticker": symbol,
            "company_of_interest": symbol,
            "analysis_date": analysis_date,
            "trade_date": analysis_date,
            "market_type": market_type,
            "context": ctx,
            "skip_cache": True,
            "prompt_overrides": prompt_overrides or {},
            "task_description": task_description,
            "workflow_id": f"agent_workshop_debug_{version.version_id}",
            "agent_workshop_execution_plan": version.execution_plan.model_dump(mode="json") if version.execution_plan else {},
        }

        try:
            workflow_api = WorkflowAPI()
            system_vars = workflow_api._prepare_system_variables(
                stock_code=symbol,
                analysis_date=analysis_date,
            )
            inputs.update(system_vars)
        except Exception as exc:
            logger.warning("[AgentWorkshop] 准备系统变量失败，将继续调试: %s", exc)

        import asyncio

        if llm_provider.lower() == "ollama":
            result = await asyncio.wait_for(asyncio.to_thread(agent, inputs), timeout=timeout + 60)
        else:
            result = await asyncio.to_thread(agent, inputs)

        output_field = str(version.agent_metadata.get("output_field") or "analysis_result")
        debug_prompt = (result.get("__debug_prompt__") if isinstance(result, dict) else None) or {}
        llm_final_response = debug_prompt.get("llm_final_response") if isinstance(debug_prompt, dict) else None
        if isinstance(llm_final_response, str) and llm_final_response.strip():
            report = llm_final_response.strip()
        else:
            report = self._extract_runtime_report(result, output_field)

        debug_result = {
            "version_id": version.version_id,
            "spec_id": version.spec_id,
            "symbol": symbol,
            "analysis_date": analysis_date,
            "report": report,
            "report_length": len(report),
            "runtime_agent_id": version.version_id,
            "output_field": output_field,
            "raw_result": result if isinstance(result, dict) else {"raw": str(result)},
            "debug_prompt": debug_prompt,
            "template": {
                "template_id": template_id,
                "template_name": version.prompt_template_ref.get("template_name"),
            },
            "execution_plan": version.execution_plan.model_dump(mode="json") if version.execution_plan else {},
            "metadata": {
                "agent_id": version.agent_metadata.get("id") or version.version_id,
                "agent_name": version.agent_metadata.get("name") or spec.name,
                "maintenance_status": version.agent_metadata.get("maintenance_status") or AgentMaintenanceStatus.MAINTAINED.value,
                "required_tools": version.required_tools,
                "user_goal": user_goal,
            },
        }
        self._log_generated_result(
            "runtime_debug_execution",
            {
                "inputs": inputs,
                "debug_prompt": debug_prompt,
                "raw_result": result if isinstance(result, dict) else {"raw": str(result)},
                "extracted_report": report,
                "output_field": output_field,
            },
            context={
                "version_id": version.version_id,
                "spec_id": version.spec_id,
                "spec_name": spec.name,
                "symbol": symbol,
                "analysis_date": analysis_date,
            },
        )
        return debug_result

    async def _save_session(self, session: AgentWorkshopSession) -> None:
        doc, set_on_insert = self._prepare_upsert_doc(session.model_dump(mode="json", by_alias=True))
        await self._db[SESSION_COLLECTION].update_one(
            {"session_id": session.session_id},
            {"$set": doc, "$setOnInsert": set_on_insert},
            upsert=True,
        )

    async def _save_spec(self, spec: AgentSpec, session_id: Optional[str] = None) -> None:
        spec.latest_session_id = session_id or spec.latest_session_id
        spec.updated_at = now_tz()
        doc, set_on_insert = self._prepare_upsert_doc(spec.model_dump(mode="json", by_alias=True))
        await self._db[SPEC_COLLECTION].update_one(
            {"spec_id": spec.spec_id},
            {"$set": doc, "$setOnInsert": set_on_insert},
            upsert=True,
        )

    async def _save_version(self, version: AgentVersion) -> None:
        doc, set_on_insert = self._prepare_upsert_doc(version.model_dump(mode="json", by_alias=True))
        await self._db[VERSION_COLLECTION].update_one(
            {"version_id": version.version_id},
            {"$set": doc, "$setOnInsert": set_on_insert},
            upsert=True,
        )

    async def _save_evaluation(self, report: AgentEvaluationReport) -> None:
        doc, set_on_insert = self._prepare_upsert_doc(report.model_dump(mode="json", by_alias=True))
        await self._db[EVALUATION_COLLECTION].update_one(
            {"evaluation_id": report.evaluation_id},
            {"$set": doc, "$setOnInsert": set_on_insert},
            upsert=True,
        )

    def _prepare_upsert_doc(self, doc: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        set_doc = dict(doc)
        set_doc.pop("_id", None)
        created_at = set_doc.pop("created_at", None)

        set_on_insert: Dict[str, Any] = {}
        if created_at is not None:
            set_on_insert["created_at"] = created_at

        return set_doc, set_on_insert

    def _build_nanobot_spec_id(self, agent_id: str) -> str:
        normalized = re.sub(r"[^a-zA-Z0-9_]+", "_", str(agent_id or "").strip()).strip("_")
        if not normalized:
            normalized = uuid.uuid4().hex[:12]
        return f"spec_nanobot_{normalized}"

    def _infer_nanobot_spec_domain(self, agent_name: str, responsibility: str, preferred_methods: List[str]) -> str:
        haystack = " ".join([agent_name or "", responsibility or "", " ".join(preferred_methods or [])]).lower()
        if any(keyword in haystack for keyword in ["估值", "a股", "stock", "pe", "pb", "peg", "财务", "基本面"]):
            return "stock_analysis"
        if any(keyword in haystack for keyword in ["风险", "复盘", "review"]):
            return "risk_management"
        return "general"

    @staticmethod
    def _normalize_unique_list(values: Optional[List[str]]) -> List[str]:
        normalized: List[str] = []
        seen: set[str] = set()
        for value in values or []:
            text = str(value or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            normalized.append(text)
        return normalized

    @staticmethod
    def _build_nanobot_draft_user_message(
        *,
        agent_id: str,
        agent_name: str,
        target_responsibility: str,
        output_field: str,
        tool_ids: List[str],
        non_goals: List[str],
        preferred_methods: List[str],
    ) -> str:
        lines = [
            f"请基于 Nanobot 已确认的候选方案继续治理这个 Agent：{agent_name}（{agent_id}）。",
            f"职责：{target_responsibility}",
            f"输出字段：{output_field}",
        ]
        if tool_ids:
            lines.append(f"候选工具：{'、'.join(tool_ids)}")
        if non_goals:
            lines.append(f"非目标：{'、'.join(non_goals)}")
        if preferred_methods:
            lines.append(f"方法范围：{'、'.join(preferred_methods)}")
        lines.append("这是一份从 Nanobot 同步进 Agent 工坊的 Draft，请在此基础上继续做缺口分析、版本构建和治理。")
        return "\n".join(lines)

    async def _load_session(self, session_id: str) -> Optional[AgentWorkshopSession]:
        doc = await self._db[SESSION_COLLECTION].find_one({"session_id": session_id})
        if not doc:
            return None
        return AgentWorkshopSession(**doc)

    async def _get_next_version_number(self, spec_id: str) -> int:
        doc = await self._db[VERSION_COLLECTION].find_one(
            {"spec_id": spec_id},
            sort=[("version", -1)],
        )
        if not doc:
            return 1
        return int(doc.get("version", 0)) + 1

    def _collect_user_messages(self, session: AgentWorkshopSession) -> List[str]:
        return [message.content for message in session.messages if message.role == "user"]

    async def _collect_capability_snapshot(self, query_text: str = "", top_k: int = 18) -> Dict[str, Any]:
        try:
            capability_index = CapabilityIndexService(self._db)
            await capability_index.ensure_index()
            hits = await capability_index.search_capabilities(
                query=query_text or "金融分析 Agent 能力",
                top_k=top_k,
                bindable_only=False,
            )
            if not hits:
                return await self._collect_capability_snapshot_fallback()

            all_capabilities = await capability_index.list_capabilities()
            data_categories = {
                ToolCategory.MARKET.value,
                ToolCategory.FUNDAMENTALS.value,
                ToolCategory.NEWS.value,
                ToolCategory.SOCIAL.value,
                ToolCategory.CHINA.value,
            }
            analysis_categories = {
                ToolCategory.TECHNICAL.value,
                ToolCategory.SCREENING.value,
                ToolCategory.TRADE_REVIEW.value,
                ToolCategory.ASSISTANT_OPS.value,
                ToolCategory.UTILITY.value,
                ToolCategory.KNOWLEDGE.value,
                ToolCategory.MCP.value,
            }

            builtin_data_tools: List[str] = []
            builtin_analysis_tools: List[str] = []
            valuation_tools: List[str] = []
            builtin_tool_details: List[Dict[str, Any]] = []
            valuation_tool_details: List[Dict[str, Any]] = []
            external_data_skills: List[str] = []
            external_analysis_skills: List[str] = []
            valuation_skills: List[str] = []
            external_skill_tool_ids: List[str] = []
            external_skill_details: List[Dict[str, Any]] = []
            valuation_skill_details: List[Dict[str, Any]] = []

            for hit in hits:
                capability = hit.capability
                detail = self._build_capability_detail_from_document(capability)
                label = str(detail.get("label") or "")
                category = str(capability.category or "")

                if capability.registry_tool_id and capability.registry_tool_id not in external_skill_tool_ids:
                    external_skill_tool_ids.append(capability.registry_tool_id)

                if capability.source_type in {"builtin_tool", "mcp_tool"}:
                    if category in data_categories and label not in builtin_data_tools:
                        builtin_data_tools.append(label)
                    if category in analysis_categories and label not in builtin_analysis_tools:
                        builtin_analysis_tools.append(label)
                    builtin_tool_details.append(detail)
                else:
                    if category in data_categories and label not in external_data_skills:
                        external_data_skills.append(label)
                    elif label not in external_analysis_skills:
                        external_analysis_skills.append(label)
                    external_skill_details.append(detail)

                if self._looks_like_valuation_capability(str(detail.get("searchable") or "")):
                    if capability.bindable:
                        if label not in valuation_tools:
                            valuation_tools.append(label)
                            valuation_tool_details.append(detail)
                    else:
                        if label not in valuation_skills:
                            valuation_skills.append(label)
                            valuation_skill_details.append(detail)

            return {
                "builtin_data_tools": builtin_data_tools,
                "builtin_analysis_tools": builtin_analysis_tools,
                "external_data_skills": external_data_skills,
                "external_analysis_skills": external_analysis_skills,
                "builtin_tool_details": builtin_tool_details,
                "external_skill_details": external_skill_details,
                "external_skill_tool_ids": external_skill_tool_ids,
                "valuation_tools": valuation_tools,
                "valuation_skills": valuation_skills,
                "valuation_tool_details": valuation_tool_details,
                "valuation_skill_details": valuation_skill_details,
                "totals": {
                    "builtin_tools": len([doc for doc in all_capabilities if doc.bindable]),
                    "external_skills": len([doc for doc in all_capabilities if doc.source_type == "external_skill"]),
                    "indexed_capabilities": len(all_capabilities),
                    "retrieved_capabilities": len(hits),
                },
            }
        except Exception as exc:
            logger.warning("[AgentWorkshop] CapabilityIndex 检索失败，回退注册表快照: %s", exc)
            return await self._collect_capability_snapshot_fallback()

    async def _collect_capability_snapshot_fallback(self) -> Dict[str, Any]:
        registry = get_tool_registry()
        builtin_tools = registry.list_all()
        external_skill_docs = await self._db["external_skills"].find({"status": {"$in": ["active", "draft"]}}).to_list(length=500)

        data_categories = {
            ToolCategory.MARKET.value,
            ToolCategory.FUNDAMENTALS.value,
            ToolCategory.NEWS.value,
            ToolCategory.SOCIAL.value,
            ToolCategory.CHINA.value,
        }
        analysis_categories = {
            ToolCategory.TECHNICAL.value,
            ToolCategory.SCREENING.value,
            ToolCategory.TRADE_REVIEW.value,
            ToolCategory.ASSISTANT_OPS.value,
            ToolCategory.UTILITY.value,
            ToolCategory.KNOWLEDGE.value,
            ToolCategory.MCP.value,
        }

        builtin_data_tools: List[str] = []
        builtin_analysis_tools: List[str] = []
        valuation_tools: List[str] = []
        builtin_tool_details: List[Dict[str, Any]] = []
        valuation_tool_details: List[Dict[str, Any]] = []

        for tool in builtin_tools:
            item = f"{tool.id} | {tool.name}"
            category = str(tool.category)
            detail = self._build_registered_tool_detail(tool)
            searchable = str(detail.get("searchable") or "")
            if category in data_categories and item not in builtin_data_tools:
                builtin_data_tools.append(item)
            if category in analysis_categories and item not in builtin_analysis_tools:
                builtin_analysis_tools.append(item)
            builtin_tool_details.append(detail)
            if self._looks_like_valuation_capability(searchable) and item not in valuation_tools:
                valuation_tools.append(item)
                valuation_tool_details.append(detail)

        external_data_skills: List[str] = []
        external_analysis_skills: List[str] = []
        valuation_skills: List[str] = []
        external_skill_tool_ids: List[str] = []
        external_skill_details: List[Dict[str, Any]] = []
        valuation_skill_details: List[Dict[str, Any]] = []

        for doc in external_skill_docs:
            tool_id = str(doc.get("tool_id") or "")
            display_name = str(doc.get("display_name") or tool_id)
            description = str(doc.get("description") or "")
            category = str(doc.get("category") or "").lower()
            data_source = str(doc.get("data_source") or "")
            item = f"{tool_id} | {display_name}" if tool_id else display_name
            detail = {
                "tool_id": tool_id,
                "label": item,
                "name": display_name,
                "category": category,
                "summary": description,
                "when_to_use": "",
                "returns": "",
                "related_tools": [],
                "coverage_terms": self._extract_valuation_terms(
                    " ".join([tool_id, display_name, description, category, data_source])
                ),
                "searchable": " ".join([tool_id, display_name, description, category, data_source]).lower(),
                "source": "external_skill",
            }
            searchable = str(detail.get("searchable") or "")

            if tool_id and tool_id not in external_skill_tool_ids:
                external_skill_tool_ids.append(tool_id)

            if category in {"market", "fundamentals", "news", "social", "china"} and item not in external_data_skills:
                external_data_skills.append(item)
            elif item not in external_analysis_skills:
                external_analysis_skills.append(item)

            external_skill_details.append(detail)

            if self._looks_like_valuation_capability(searchable) and item not in valuation_skills:
                valuation_skills.append(item)
                valuation_skill_details.append(detail)

        return {
            "builtin_data_tools": builtin_data_tools,
            "builtin_analysis_tools": builtin_analysis_tools,
            "external_data_skills": external_data_skills,
            "external_analysis_skills": external_analysis_skills,
            "builtin_tool_details": builtin_tool_details,
            "external_skill_details": external_skill_details,
            "external_skill_tool_ids": external_skill_tool_ids,
            "valuation_tools": valuation_tools,
            "valuation_skills": valuation_skills,
            "valuation_tool_details": valuation_tool_details,
            "valuation_skill_details": valuation_skill_details,
            "totals": {
                "builtin_tools": len(builtin_tools),
                "external_skills": len(external_skill_docs),
            },
        }

    def _build_capability_detail_from_document(self, capability: Any) -> Dict[str, Any]:
        description = str(getattr(capability, "description", "") or "").strip()
        when_to_use = str(getattr(capability, "when_to_use", "") or "").strip()
        returns = str(getattr(capability, "returns", "") or "").strip()
        summary = " ".join(part for part in [description, when_to_use, returns] if part)
        if len(summary) > 240:
            summary = f"{summary[:240].rstrip()}..."
        return {
            "tool_id": str(getattr(capability, "registry_tool_id", None) or getattr(capability, "capability_id", "")),
            "label": str(getattr(capability, "label", "") or ""),
            "name": str(getattr(capability, "name", "") or ""),
            "category": str(getattr(capability, "category", "") or ""),
            "summary": summary,
            "when_to_use": when_to_use,
            "returns": returns,
            "related_tools": list(getattr(capability, "related_tools", []) or []),
            "coverage_terms": list(getattr(capability, "coverage_terms", []) or []),
            "searchable": str(getattr(capability, "retrieval_text", "") or "").lower(),
            "source": str(getattr(capability, "source_type", "") or ""),
            "bindable": bool(getattr(capability, "bindable", False)),
            "status": str(getattr(capability, "status", "") or ""),
        }

    def _looks_like_valuation_capability(self, searchable: str) -> bool:
        return bool(self._extract_valuation_terms(searchable))

    def _extract_valuation_terms(self, searchable: str) -> List[str]:
        text = str(searchable or "").lower()
        if not text:
            return []

        patterns = [
            (r"(?<![a-z0-9])(valuation|valuations)(?![a-z0-9])", "valuation"),
            (r"(?<![a-z0-9])dcf(?![a-z0-9])", "dcf"),
            (r"(?<![a-z0-9])pe(?![a-z0-9])|市盈率|pe_ttm", "pe"),
            (r"(?<![a-z0-9])pb(?![a-z0-9])|市净率|pb_mrq", "pb"),
            (r"(?<![a-z0-9])peg(?![a-z0-9])", "peg"),
            (r"(?<![a-z0-9])ps(?![a-z0-9])", "ps"),
            (r"ev/?ebitda", "ev_ebitda"),
            (r"可比公司|同业对比|peer comparison|peer", "peer_comparison"),
            (r"估值|估价|定价|目标价|价格区间|估值区间|相对估值", "valuation_cn"),
            (r"敏感性分析", "sensitivity"),
        ]
        matched: List[str] = []
        for pattern, normalized in patterns:
            if re.search(pattern, text):
                matched.append(normalized)
        return self._dedupe(matched)

    def _build_registered_tool_detail(self, tool: Any) -> Dict[str, Any]:
        label = f"{tool.id} | {tool.name}"
        when_to_use = str(getattr(tool, "when_to_use", "") or "").strip()
        returns = str(getattr(tool, "returns", "") or "").strip()
        description = str(getattr(tool, "description", "") or "").strip()
        related_tools = [str(item).strip() for item in (getattr(tool, "related_tools", []) or []) if str(item).strip()]
        searchable = " ".join([
            str(tool.id or ""),
            str(tool.name or ""),
            description,
            str(getattr(tool, "data_source", "") or ""),
            when_to_use,
            returns,
            " ".join(related_tools),
        ]).lower()
        summary_parts = [part for part in [description, when_to_use, returns] if part]
        summary = " ".join(summary_parts)
        if len(summary) > 240:
            summary = f"{summary[:240].rstrip()}..."
        return {
            "tool_id": str(tool.id),
            "label": label,
            "name": str(tool.name),
            "category": str(getattr(tool, "category", "") or ""),
            "summary": summary,
            "when_to_use": when_to_use,
            "returns": returns,
            "related_tools": related_tools,
            "coverage_terms": self._extract_valuation_terms(searchable),
            "searchable": searchable,
            "source": "builtin",
        }

    def _select_gap_analysis_tool_details(
        self,
        spec: AgentSpec,
        capability_snapshot: Dict[str, Any],
        limit: int = 8,
    ) -> List[Dict[str, Any]]:
        spec_text = self._build_valuation_requirement_text(spec)
        is_valuation_spec = self._is_valuation_spec(spec)
        requested_terms = set(self._extract_valuation_terms(spec_text))
        specific_requested_terms = {term for term in requested_terms if term not in {"valuation", "valuation_cn"}}
        candidates = [
            *(capability_snapshot.get("builtin_tool_details", []) or []),
            *(capability_snapshot.get("external_skill_details", []) or []),
        ]
        preferred_ids = {
            "get_stock_market_data_unified",
            "get_stock_fundamentals_unified",
            "get_peer_comparison",
            "get_sector_constituents",
            "calculate_pb_relative_valuation",
            "calculate_peg_valuation",
        }
        if is_valuation_spec:
            preferred_ids.update({
                "get_value_factor_bundle_tool",
                "get_fundamental_factor_snapshot_tool",
            })

        scored: List[Tuple[int, Dict[str, Any]]] = []
        for detail in candidates:
            tool_id = str(detail.get("tool_id") or "")
            searchable = str(detail.get("searchable") or "")
            coverage_terms = detail.get("coverage_terms") or []
            coverage_term_set = set(str(term) for term in coverage_terms if str(term).strip())
            specific_overlap = specific_requested_terms & coverage_term_set
            score = 0
            if tool_id in preferred_ids:
                score += 80
            if is_valuation_spec and coverage_terms:
                score += 60
            if requested_terms and coverage_term_set:
                score += len(requested_terms & coverage_term_set) * 25
            if requested_terms and len(requested_terms & coverage_term_set) >= 2:
                score += 20
            if specific_overlap:
                score += len(specific_overlap) * 30
            if is_valuation_spec and detail.get("category") == ToolCategory.FUNDAMENTALS.value:
                score += 20
            if "行业" in spec_text or "peer" in spec_text:
                if "peer_comparison" in coverage_terms or "peer" in searchable:
                    score += 20
            if "peg" in spec_text and "peg" in coverage_terms:
                score += 30
            if any(token in spec_text for token in ["pe", "市盈率"]) and "pe" in coverage_terms:
                score += 30
            if any(token in spec_text for token in ["pb", "市净率"]) and "pb" in coverage_terms:
                score += 30
            if any(token in spec_text for token in ["估值", "valuation"]) and self._looks_like_valuation_capability(searchable):
                score += 20
            if any(token in searchable for token in ["综合", "synthesis", "report", "模板"]) and any(token in spec_text for token in ["综合解读", "汇总", "权重"]):
                score += 10
            if is_valuation_spec and tool_id not in preferred_ids and coverage_term_set and coverage_term_set.issubset({"valuation", "valuation_cn"}):
                score -= 40
            if is_valuation_spec and tool_id not in preferred_ids and specific_requested_terms and not specific_overlap and detail.get("category") != ToolCategory.FUNDAMENTALS.value:
                score -= 30
            if score > 0:
                scored.append((score, detail))

        scored.sort(key=lambda item: (-item[0], str(item[1].get("label") or "")))
        selected: List[Dict[str, Any]] = []
        seen_labels: set[str] = set()
        for _, detail in scored:
            label = str(detail.get("label") or "")
            if not label or label in seen_labels:
                continue
            seen_labels.add(label)
            selected.append(detail)
            if len(selected) >= limit:
                break

        return selected

    def _format_coverage_term_label(self, term: str) -> str:
        labels = {
            "valuation": "估值方法",
            "valuation_cn": "估值判断",
            "pe": "PE/市盈率",
            "pb": "PB/市净率",
            "peg": "PEG",
            "ps": "PS/市销率",
            "peer_comparison": "同业估值对比",
            "growth": "成长性",
            "cashflow": "现金流",
            "quality": "质量因子",
            "technical": "技术指标",
            "dcf": "DCF",
            "ev_ebitda": "EV/EBITDA",
            "sensitivity": "敏感性分析",
        }
        return labels.get(term, term)

    def _build_capability_coverage_map_lines(
        self,
        spec: AgentSpec,
        tool_details: List[Dict[str, Any]],
    ) -> List[str]:
        if not self._is_valuation_spec(spec):
            return []

        requested_terms = self._dedupe(self._extract_valuation_terms(self._build_valuation_requirement_text(spec)))
        if not requested_terms:
            requested_terms = ["valuation_cn", "pe", "pb", "peg", "peer_comparison"]

        term_to_labels: Dict[str, List[str]] = {}
        for detail in tool_details:
            label = str(detail.get("label") or "").strip()
            if not label:
                continue
            coverage_terms = [str(term).strip() for term in (detail.get("coverage_terms") or []) if str(term).strip()]
            for term in coverage_terms:
                term_to_labels.setdefault(term, [])
                if label not in term_to_labels[term]:
                    term_to_labels[term].append(label)

        lines: List[str] = [
            "- 判断缺口时先按能力维度而不是按工具名逐个比对：聚合型因子包/快照工具内部已声明覆盖的能力，都应视为现有可直接复用能力。",
        ]
        for term in requested_terms[:8]:
            labels = term_to_labels.get(term, [])
            if not labels:
                continue
            lines.append(
                f"- 能力 {self._format_coverage_term_label(term)}：当前可由 {'；'.join(labels[:4])} 直接提供或组合复用；不能仅因缺少同名专用工具就判定为缺口。"
            )
        return lines

    def _format_tool_detail_lines(self, tool_details: List[Dict[str, Any]], limit: int = 12) -> List[str]:
        lines: List[str] = []
        for detail in tool_details[:limit]:
            label = str(detail.get("label") or "")
            coverage_terms = "/".join(detail.get("coverage_terms") or [])
            summary = str(detail.get("summary") or "")
            if coverage_terms and summary:
                lines.append(f"- {label}：覆盖 {coverage_terms}；{summary}")
            elif summary:
                lines.append(f"- {label}：{summary}")
            else:
                lines.append(f"- {label}")
        return lines

    def _normalize_capability_id(self, value: Any) -> str:
        text = str(value or "").strip().lower()
        if not text:
            return ""
        if "|" in text:
            text = text.split("|", 1)[0].strip()
        return text.replace("-", "_")

    def _collect_registered_capability_ids(self, capability_snapshot: Dict[str, Any]) -> set[str]:
        registered_ids: set[str] = set()

        for item in capability_snapshot.get("external_skill_tool_ids", []) or []:
            normalized = self._normalize_capability_id(item)
            if normalized:
                registered_ids.add(normalized)

        for group_name in [
            "builtin_data_tools",
            "builtin_analysis_tools",
            "external_data_skills",
            "external_analysis_skills",
            "valuation_tools",
            "valuation_skills",
        ]:
            for item in capability_snapshot.get(group_name, []) or []:
                normalized = self._normalize_capability_id(item)
                if normalized:
                    registered_ids.add(normalized)

        return registered_ids

    def _build_registered_capability_texts(self, capability_snapshot: Dict[str, Any]) -> List[str]:
        texts: List[str] = []
        for group_name in [
            "builtin_data_tools",
            "builtin_analysis_tools",
            "external_data_skills",
            "external_analysis_skills",
            "valuation_tools",
            "valuation_skills",
        ]:
            texts.extend([
                str(item).strip().lower()
                for item in (capability_snapshot.get(group_name, []) or [])
                if str(item).strip()
            ])

        for group_name in [
            "builtin_tool_details",
            "external_skill_details",
            "valuation_tool_details",
            "valuation_skill_details",
        ]:
            for item in capability_snapshot.get(group_name, []) or []:
                if not isinstance(item, dict):
                    continue
                texts.extend([
                    str(item.get("tool_id") or "").strip().lower(),
                    str(item.get("label") or "").strip().lower(),
                    str(item.get("name") or "").strip().lower(),
                    str(item.get("summary") or "").strip().lower(),
                    str(item.get("searchable") or "").strip().lower(),
                ])

        return [item for item in texts if item]

    def _extract_object_text(self, item: Dict[str, Any]) -> str:
        for key in ("question", "text", "content", "message", "value"):
            if isinstance(item.get(key), str) and item[key].strip():
                return item[key].strip()
        for value in item.values():
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    def _get_io_field_name(self, value: Any, fallback: str = "") -> str:
        if isinstance(value, AgentSpecIOField):
            return self._pick_str(value.name, fallback)
        if isinstance(value, dict):
            return self._pick_str(
                value.get("name"),
                self._pick_str(value.get("field_name"), self._pick_str(value.get("key"), fallback)),
            )
        if isinstance(value, str):
            return value.strip()
        return self._pick_str(value, fallback)

    def _get_io_field_type(self, value: Any, fallback: str = "string") -> str:
        if isinstance(value, AgentSpecIOField):
            return self._pick_str(value.type, fallback)
        if isinstance(value, dict):
            return self._pick_str(value.get("type"), self._pick_str(value.get("data_type"), fallback))
        return fallback

    def _get_io_field_required(self, value: Any) -> bool:
        if isinstance(value, AgentSpecIOField):
            return bool(value.required)
        if isinstance(value, dict):
            raw = value.get("required")
            if isinstance(raw, bool):
                return raw
            return str(raw or "").strip().lower() in {"true", "1", "yes", "required"}
        return False

    def _get_io_field_label(self, value: Any) -> str:
        name = self._get_io_field_name(value)
        description = ""
        if isinstance(value, AgentSpecIOField):
            description = self._pick_str(value.description, "")
        elif isinstance(value, dict):
            description = self._pick_str(value.get("description"), self._pick_str(value.get("summary"), ""))
        if name and description and description != name:
            return f"{name}：{description}"
        return name or description

    def _list_io_field_names(self, values: List[Any]) -> List[str]:
        names: List[str] = []
        for item in values or []:
            name = self._get_io_field_name(item)
            if name:
                names.append(name)
        return self._dedupe(names)

    def _list_io_field_labels(self, values: List[Any]) -> List[str]:
        labels: List[str] = []
        for item in values or []:
            label = self._get_io_field_label(item)
            if label:
                labels.append(label)
        return self._dedupe(labels)

    def _serialize_io_fields(self, values: List[Any], limit: int) -> List[Any]:
        serialized: List[Any] = []
        for item in (values or [])[:limit]:
            if isinstance(item, AgentSpecIOField):
                serialized.append(item.model_dump(mode="json"))
            elif isinstance(item, dict):
                serialized.append(item)
            elif isinstance(item, str) and item.strip():
                serialized.append(item.strip())
        return serialized

    def _require_io_fields_field(self, data: Dict[str, Any], key: str, stage: str) -> List[Any]:
        value = data.get(key)
        if not isinstance(value, list):
            if isinstance(value, str) and value.strip():
                return [value.strip()]
            raise ValueError(f"{stage} 缺少数组字段 {key}")

        normalized: List[Any] = []
        for index, item in enumerate(value):
            if isinstance(item, (str, int, float)):
                text = str(item).strip()
                if text:
                    normalized.append(text)
                continue
            if not isinstance(item, dict):
                continue

            has_structured_shape = any(field in item for field in ("name", "field_name", "type", "data_type", "description", "required"))
            if not has_structured_shape:
                text = self._extract_object_text(item)
                if text:
                    normalized.append(text)
                continue

            name = self._get_io_field_name(item)
            description = self._pick_str(item.get("description"), self._pick_str(item.get("summary"), ""))
            if not name and not description:
                raise ValueError(f"{stage} {key}[{index}] 缺少 name/description")

            normalized.append(
                AgentSpecIOField(
                    name=name or description[:80],
                    type=self._get_io_field_type(item),
                    required=self._get_io_field_required(item),
                    description=description,
                )
            )

        return normalized[:12]

    def _capability_requirement_has_registered_evidence(
        self,
        requirement: AgentCapabilityRequirement,
        registered_capability_ids: set[str],
        registered_capability_texts: List[str],
    ) -> bool:
        candidates = self._dedupe([
            self._normalize_capability_id(requirement.capability_key),
            self._normalize_capability_id(requirement.capability_name),
            self._normalize_capability_id(self._slugify(requirement.capability_name)),
            self._normalize_capability_id(self._slugify(requirement.description)),
        ])
        if any(candidate and candidate in registered_capability_ids for candidate in candidates):
            return True

        searchable_candidates = self._dedupe([
            str(requirement.capability_key or "").strip().lower(),
            str(requirement.capability_name or "").strip().lower(),
        ])
        for candidate in searchable_candidates:
            if not candidate or len(candidate) < 2:
                continue
            if any(candidate in text for text in registered_capability_texts):
                return True
        return False

    def _validate_deterministic_capability_requirements(
        self,
        spec: AgentSpec,
        capability_snapshot: Dict[str, Any],
    ) -> Tuple[AgentSpec, List[str]]:
        registered_capability_ids = self._collect_registered_capability_ids(capability_snapshot)
        registered_capability_texts = self._build_registered_capability_texts(capability_snapshot)
        downgraded_names: List[str] = []
        normalized_items: List[AgentCapabilityRequirement] = []

        for item in spec.capability_requirements or []:
            normalized_item = item.model_copy(deep=True)
            if normalized_item.delivery_requirement == "deterministic-tool":
                has_evidence = self._capability_requirement_has_registered_evidence(
                    normalized_item,
                    registered_capability_ids,
                    registered_capability_texts,
                )
                if not has_evidence:
                    normalized_item.delivery_requirement = "tool-or-prompt"
                    downgraded_names.append(normalized_item.capability_name or normalized_item.capability_key or normalized_item.description)
            normalized_items.append(normalized_item)

        return spec.model_copy(update={"capability_requirements": normalized_items}), self._dedupe([item for item in downgraded_names if item])[:4]

    def _should_force_spec_confirmation(self, response_message: str, spec: AgentSpec, conversation: str) -> bool:
        response_text = str(response_message or "").strip().lower()
        if any(keyword in response_text for keyword in ("默认", "推荐", "建议")):
            return True

        conversation_text = str(conversation or "").strip().lower()
        if not conversation_text:
            return False

        for method in spec.preferred_methods or []:
            if method and method.lower() not in conversation_text:
                return True

        for output_label in self._list_io_field_names(spec.outputs):
            normalized_output = output_label.lower()
            if normalized_output and normalized_output not in conversation_text and any(token in normalized_output for token in ("估值", "score", "评级", "结论")):
                return True

        return False

    def _post_process_requirement_clarification(
        self,
        spec: AgentSpec,
        pending_questions: List[str],
        completeness_score: float,
        feasibility_status: str,
        response_message: str,
        conversation: str,
        capability_snapshot: Dict[str, Any],
    ) -> Tuple[AgentSpec, List[str], float]:
        normalized_spec, downgraded_capabilities = self._validate_deterministic_capability_requirements(spec, capability_snapshot)
        normalized_questions = self._dedupe([
            item for item in pending_questions
            if item and self._is_user_confirmable_pending_question(item)
        ])[:2]

        if downgraded_capabilities:
            logger.info(
                "[AgentWorkshop] 能力项缺少确定性工具证据，转入下一步缺口分析处理: %s",
                "、".join(downgraded_capabilities),
            )
            completeness_score = min(completeness_score, 0.85)

        if feasibility_status == "feasible" and self._should_force_spec_confirmation(response_message, normalized_spec, conversation):
            normalized_questions = self._dedupe([
                *normalized_questions,
                "我先按推荐方案整理了这版草案。请确认方法、输出内容和适用范围是否保持这样；如果要改，直接说改哪一点。",
            ])[:2]
            completeness_score = min(completeness_score, 0.9 if len(normalized_questions) == 1 else 0.85)

        if feasibility_status == "need-clarification" and not normalized_questions:
            normalized_questions = ["请看一下上面的推荐方案能不能直接用；如果不合适，直接说哪里要改，比如方法、输出内容或适用范围。"]
            completeness_score = min(completeness_score, 0.75)

        if normalized_questions:
            completeness_score = min(completeness_score, 0.9 if feasibility_status == "feasible" else completeness_score)

        return normalized_spec, normalized_questions, round(max(0.0, min(completeness_score, 1.0)), 3)

    def _sanitize_spec_responsibilities(self, responsibilities: List[str]) -> List[str]:
        normalized: List[str] = []
        tool_id_pattern = r"[A-Za-z][A-Za-z0-9]+(?:_[A-Za-z0-9]+)+"

        for item in responsibilities or []:
            text = str(item or "").strip()
            if not text:
                continue

            text = re.sub(rf"^调用\s+{tool_id_pattern}(?:\s+工具)?\s*", "", text)
            text = re.sub(rf"^使用\s+{tool_id_pattern}(?:\s+工具)?\s*", "", text)
            text = re.sub(rf"^通过\s+{tool_id_pattern}(?:\s+工具)?\s*", "通过可用工具", text)
            text = re.sub(rf"^基于\s+{tool_id_pattern}(?:\s+工具)?\s*", "基于可用工具", text)
            text = re.sub(rf"^依托\s+{tool_id_pattern}(?:\s+工具)?\s*", "依托可用工具", text)
            text = re.sub(rf"\b{tool_id_pattern}\b", "相关工具", text)
            text = re.sub(r"\s{2,}", " ", text).strip(" ，,；;")

            if text:
                normalized.append(text)

        return self._dedupe(normalized)

    def _is_user_confirmable_pending_question(self, question: str) -> bool:
        normalized = str(question or "").strip().lower()
        if not normalized:
            return False

        internal_markers = (
            "tool-or-prompt",
            "deterministic-tool",
            "prompt-only",
            "可调用工具证据",
            "工具证据",
            "能力检查",
            "重点确认它们",
            "下一步能力检查",
            "现成工具",
            "delivery_requirement",
        )
        return not any(marker in normalized for marker in internal_markers)

    def _partition_existing_suggested_items(
        self,
        items: List[SuggestedToolItem],
        registered_capability_ids: set[str],
    ) -> tuple[List[SuggestedToolItem], List[SuggestedToolItem]]:
        pending_items: List[SuggestedToolItem] = []
        existing_items: List[SuggestedToolItem] = []

        for item in items:
            normalized_tool_id = self._normalize_capability_id(item.tool_id)
            if normalized_tool_id and normalized_tool_id in registered_capability_ids:
                existing_items.append(item)
            else:
                pending_items.append(item)

        return pending_items, existing_items

    def _is_valuation_spec(self, spec: AgentSpec) -> bool:
        searchable = " ".join([
            spec.name,
            spec.spec_id,
            spec.primary_goal,
            " ".join(self._list_io_field_labels(spec.outputs)),
            " ".join(spec.preferred_methods),
            " ".join(spec.success_criteria),
        ]).lower()
        return spec.domain == "stock_analysis" and self._looks_like_valuation_capability(searchable)

    def _build_capability_label_lookup(self, capability_snapshot: Dict[str, Any]) -> Dict[str, str]:
        lookup: Dict[str, str] = {}
        for group_name in [
            "builtin_data_tools",
            "builtin_analysis_tools",
            "external_data_skills",
            "external_analysis_skills",
            "valuation_tools",
            "valuation_skills",
        ]:
            for item in capability_snapshot.get(group_name, []) or []:
                normalized = self._normalize_capability_id(item)
                if normalized and normalized not in lookup:
                    lookup[normalized] = str(item)
        return lookup

    def _derive_required_valuation_capability_ids(self, spec: AgentSpec) -> List[str]:
        text = self._build_valuation_requirement_text(spec)
        capability_ids: List[str] = [
            "get_stock_fundamentals_unified",
            "get_peer_comparison",
            "get_value_factor_bundle_tool",
        ]

        if any(keyword in text for keyword in ["pe", "pb", "peg", "市盈率", "市净率", "估值"]):
            capability_ids.append("get_fundamental_factor_snapshot_tool")

        if any(keyword in text for keyword in ["pb", "市净率", "相对估值", "同行估值", "可比公司", "peer"]):
            capability_ids.append("calculate_pb_relative_valuation")

        if any(keyword in text for keyword in ["peg", "peg估值"]):
            capability_ids.append("calculate_peg_valuation")

        return self._dedupe(capability_ids)

    def _build_valuation_reuse_guidance_lines(
        self,
        spec: AgentSpec,
        capability_snapshot: Dict[str, Any],
    ) -> List[str]:
        if not self._is_valuation_spec(spec):
            return []

        registered_ids = self._collect_registered_capability_ids(capability_snapshot)
        guidance_lines: List[str] = [
            "- 对估值类规格，不要按工具名一一对应地要求新增能力；先判断现有估值栈能否通过组合复用完成目标。",
        ]

        if "get_value_factor_bundle_tool" in registered_ids:
            guidance_lines.append(
                "- get_value_factor_bundle_tool 已覆盖 PE/PB/PEG/PS、行业 PE/PB 中位数等价值因子；这属于现有估值输入能力，不应再把“缺少 PE/PB/PEG 指标”判成缺口。"
            )
        if "get_stock_fundamentals_unified" in registered_ids:
            guidance_lines.append(
                "- get_stock_fundamentals_unified 已提供 PE/PB 等核心基本面估值字段，可作为估值判断的直接数据底座。"
            )
        if "get_peer_comparison" in registered_ids:
            guidance_lines.append(
                "- get_peer_comparison 已提供同业估值对比，不能因为没有同名 PE 工具就忽略已有 peer valuation 能力。"
            )
        if "calculate_pb_relative_valuation" in registered_ids or "calculate_peg_valuation" in registered_ids:
            guidance_lines.append(
                "- 已有 PB/PEG 估值工具 + 价值因子包 + 同业对比，说明系统已经具备估值分析闭环的主要组件；除非规格明确要求当前系统无法通过组合产出的确定性结果，否则不要再建议新增平行的 calculate_pe_relative_valuation。"
            )

        guidance_lines.append(
            "- 如果现有工具组合可通过 Prompt/模板把 PE/PB/PEG 结果整理成结构化输出、综合解读或权重说明，这属于复用方案，不属于 blocking gap。"
        )
        return guidance_lines

    def _enforce_valuation_gap_report(
        self,
        spec: AgentSpec,
        gap_report: AgentWorkshopGapAnalysis,
        capability_snapshot: Dict[str, Any],
    ) -> AgentWorkshopGapAnalysis:
        if not self._is_valuation_spec(spec):
            return gap_report

        label_lookup = self._build_capability_label_lookup(capability_snapshot)
        required_ids = self._derive_required_valuation_capability_ids(spec)
        enforced_labels = [label_lookup[tool_id] for tool_id in required_ids if tool_id in label_lookup]
        if not enforced_labels:
            return gap_report

        existing_tool_ids = {
            self._normalize_capability_id(item)
            for item in gap_report.existing_tools or []
            if item
        }
        added_labels = [label for label in enforced_labels if self._normalize_capability_id(label) not in existing_tool_ids]

        filtered_suggested_tools = [
            item for item in (gap_report.suggested_tools or [])
            if self._normalize_capability_id(item.tool_id) not in required_ids
        ]
        filtered_suggested_capabilities = [
            item for item in (gap_report.suggested_capabilities or [])
            if self._normalize_capability_id(item.tool_id) not in required_ids
        ]

        notes = list(gap_report.notes or [])
        build_recommendations = list(gap_report.build_recommendations or [])
        if added_labels:
            notes.append(
                "估值类规格已自动补齐现有能力识别：" + "、".join(added_labels)
            )
        if len(filtered_suggested_tools) != len(gap_report.suggested_tools or []) or len(filtered_suggested_capabilities) != len(gap_report.suggested_capabilities or []):
            notes.append("已将误判为缺口的现有估值能力从 suggested_tools / suggested_capabilities 中移除。")
            build_recommendations.insert(0, "估值类 Agent 先复用现有 PE/PB/PEG/同业对比能力，再补真正缺失的计算或数据链路。")

        gap_report.existing_tools = self._dedupe([*enforced_labels, *(gap_report.existing_tools or [])])[:12]
        gap_report.suggested_tools = filtered_suggested_tools[:8]
        gap_report.suggested_capabilities = filtered_suggested_capabilities[:8]
        gap_report.build_recommendations = self._dedupe(build_recommendations)[:10]
        gap_report.notes = self._dedupe(notes)[:10]
        return gap_report

    def _build_valuation_requirement_text(self, spec: AgentSpec) -> str:
        return self._build_capability_requirement_text(spec)

    def _get_numeric_traceability_policy(self, spec: AgentSpec) -> Dict[str, Any]:
        text = self._build_valuation_requirement_text(spec)
        numeric_output_keywords = [
            "估值", "valuation", "价格", "目标价", "区间", "范围", "分数", "评分", "打分", "排序", "排名",
            "权重", "仓位", "收益率", "回报率", "波动率", "概率", "比率", "倍数", "数值", "百分比",
            "score", "rating", "rank", "price", "target", "range", "interval", "ratio", "return", "yield", "weight", "probability",
        ]
        exact_numeric_keywords = [
            "精确", "具体数值", "目标价", "价格区间", "估值区间", "打分", "评分", "权重", "排序", "排名",
            "fair value", "target price", "valuation_range", "weighted_range", "score", "rank",
        ]
        source_label_keywords = [
            "来源", "来源标签", "关键输入参数", "可追溯", "依据", "计算过程", "原始数据", "数据源",
        ]

        enabled = any(keyword in text for keyword in numeric_output_keywords)
        requires_exact_numeric_outputs = any(keyword in text for keyword in exact_numeric_keywords)
        requires_source_labels = requires_exact_numeric_outputs or any(keyword in text for keyword in source_label_keywords)

        return {
            "enabled": enabled,
            "requires_exact_numeric_outputs": requires_exact_numeric_outputs,
            "requires_source_labels": requires_source_labels,
            "trace_numeric_if_present": enabled,
        }

    def _build_numeric_traceability_rules(self, spec: AgentSpec) -> List[str]:
        policy = self._get_numeric_traceability_policy(spec)
        if not policy["enabled"]:
            return []

        rules = [
            "- 所有数值类输出都必须来自数据源直接返回，或基于原始数据/工具结果的可追溯计算，不能由模型自行估算。",
            "- 如果当前规格只需要定性判断、框架解读或方向性结论，可以不输出精确数值；但只要输出数字，就必须满足可追溯要求。",
        ]
        if policy["requires_exact_numeric_outputs"]:
            rules.append("- 当前规格要求精确数值、区间、评分、排序或权重结果时，若缺少原始数据、工具计算结果或关键输入参数，必须明确降级，禁止继续输出看似精确的数字。")
        if policy["requires_source_labels"]:
            rules.append("- 每个关键数值都必须标明来源数据、来源工具、关键输入参数或引用的上游计算结果。")
        return rules

    def _build_capability_context(self, snapshot: Dict[str, Any], compact: bool = False) -> str:
        item_limit = 2 if compact else 4
        valuation_detail_limit = 1 if compact else 3

        def format_items(title: str, items: List[str]) -> List[str]:
            if not items:
                return [f"- {title}：暂无"]
            return [f"- {title}：" + "；".join(items[:item_limit])]

        lines: List[str] = [
            "当前项目已知能力快照（来自已注册工具和已生成 Skill，不是手写假设）：",
            f"- 当前共注册内置工具 {snapshot.get('totals', {}).get('builtin_tools', 0)} 个，external_skills {snapshot.get('totals', {}).get('external_skills', 0)} 个。",
        ]
        lines.extend(format_items("内置取数能力", snapshot.get("builtin_data_tools", [])))
        lines.extend(format_items("内置分析能力", snapshot.get("builtin_analysis_tools", [])))
        lines.extend(format_items("外部取数 Skill", snapshot.get("external_data_skills", [])))
        lines.extend(format_items("外部分析 Skill", snapshot.get("external_analysis_skills", [])))
        lines.extend(format_items("估值相关能力", self._dedupe([*snapshot.get("valuation_tools", []), *snapshot.get("valuation_skills", [])])))
        if not compact:
            valuation_details = self._format_tool_detail_lines([
                *(snapshot.get("valuation_tool_details", []) or []),
                *(snapshot.get("valuation_skill_details", []) or []),
            ], limit=valuation_detail_limit)
            lines.extend(valuation_details or ["- 估值能力说明：暂无"])
        else:
            valuation_details = self._format_tool_detail_lines([
                *(snapshot.get("valuation_tool_details", []) or []),
                *(snapshot.get("valuation_skill_details", []) or []),
            ], limit=valuation_detail_limit)
            if valuation_details:
                lines.append(valuation_details[0])
        lines.extend([
            "- 对股票分析类 Agent，默认优先复用这些已存在能力。",
            "- 真正需要识别的，是这个 Agent 还缺哪些待确认设计项，以及用户希望怎样组合这些能力，而不是重复讨论项目是否已有行情或财务数据底座。",
        ])
        return "\n".join(lines)

    def _build_requirement_spec_snapshot(self, spec: AgentSpec) -> Dict[str, Any]:
        return {
            "name": spec.name,
            "domain": spec.domain,
            "primary_goal": spec.primary_goal,
            "inputs": self._serialize_io_fields(spec.inputs, 6),
            "outputs": self._serialize_io_fields(spec.outputs, 8),
            "responsibilities": list((spec.responsibilities or [])[:6]),
            "success_criteria": list((spec.success_criteria or [])[:6]),
            "constraints": list((spec.constraints or [])[:6]),
            "non_goals": list((spec.non_goals or [])[:4]),
            "preferred_methods": list((spec.preferred_methods or [])[:4]),
            "capability_requirements": [
                {
                    "capability_key": item.capability_key,
                    "capability_name": item.capability_name,
                    "capability_type": item.capability_type,
                    "delivery_requirement": item.delivery_requirement,
                }
                for item in (spec.capability_requirements or [])[:6]
            ],
            "sample_symbols": list((spec.sample_symbols or [])[:4]),
        }

    def _build_project_background_context(self) -> str:
        lines = [
            "当前项目背景：",
            "- 这是一个股票智能分析平台里的 Agent 工坊，目标是补一个能被系统稳定调用的 Agent 能力，而不是写一个抽象概念角色。",
            "- 当前系统面向散户和小团队使用，优先追求简单、够用、可维护，而不是企业级大而全设计。",
            "- 新 Agent 默认要考虑两类接入：被智能助手直接调用，或作为节点被编排进工作流。",
            "- 因此规格重点应放在：输入字段、输出字段、依赖能力、调用边界、失败降级、是否需要调试与评估，而不是泛泛描述平台故事。",
        ]
        return "\n".join(lines)

    def _build_application_scene_context(self) -> str:
        lines = [
            "接入与编排关注点：",
            "- 先判断它更适合被智能助手直接调用，还是更适合作为工作流节点调用。",
            "- 必须明确触发入口、上游输入、输出形态、下游消费方，以及是否需要进入调试运行和结果评估链路。",
            "- 如果用户描述的是一次性交付完整分析结果，就优先按“可直接调用的完整能力单元”来设计。",
            "- 如果用户描述的是流程中的一个子步骤，就优先把输入输出字段、依赖数据和边界条件定义清楚。",
        ]
        return "\n".join(lines)

    def _build_agent_role_pattern_context(self) -> str:
        lines = [
            "角色判断提示：",
            "- 只需判断这个新 Agent 更像独立分析师、流程中的专用子角色、汇总评审者，还是后处理器。",
            "- 如果用户要的只是某个已有分析角色的能力增强，应优先收敛成“专用子角色/增强版”，不要扩成大而全的新物种。",
            "- 默认先设计最小可用版本：能解决核心问题即可，不要主动引入重流程、重编排、重评分或复杂参数体系。",
            "- 角色判断的目的，是帮助你决定输入输出和职责边界，不是让你展开长篇角色百科。",
        ]
        return "\n".join(lines)

    def _build_solution_design_context(self, spec: AgentSpec) -> str:
        lines = [
            "你现在不是在做抽象的能力分类，而是在为 TradingAgents-CN 设计一个能落地的 Agent 方案。",
            "你必须同时扮演金融行业专家和系统架构师：既理解投研/交易分析场景下用户真正要什么，也理解当前系统里已有什么能力、什么适合复用、什么需要补。",
            "你的设计判断必须同时基于四个维度：",
            f"- 业务目标：{spec.primary_goal or spec.name or '待确认'}",
            f"- 用户真正要的交付：{'；'.join(self._list_io_field_labels(spec.outputs)[:6]) if spec.outputs else '需结合 responsibilities / success_criteria 判断'}",
            f"- 关键约束与边界：{'；'.join(self._dedupe([*spec.constraints, *spec.non_goals])[:8]) if (spec.constraints or spec.non_goals) else '暂无显式约束'}",
            f"- 成功标准：{'；'.join(spec.success_criteria[:6]) if spec.success_criteria else '暂无显式成功标准'}",
            "设计时不要只盯着单个字段，要结合当前系统现状、用户目标、输出方式、约束边界、可复用能力和潜在运行链路来判断缺口。",
            "如果规格里已经明确了背景、客户需求、约束和输出方式，这些信息都必须进入你的判断，而不是只围绕 suggested_tools 做机械补全。",
        ]
        return "\n".join(lines)

    def _normalize_capability_requirement_type(self, value: Any) -> str:
        normalized = str(value or "").strip().lower()
        allowed = {"data", "computation", "orchestration", "output", "guardrail"}
        if normalized in allowed:
            return normalized
        if normalized in {"analysis", "compute", "calculation"}:
            return "computation"
        if normalized in {"presentation", "report", "reporting"}:
            return "output"
        if normalized in {"constraint", "safety"}:
            return "guardrail"
        return "capability"

    def _normalize_delivery_requirement(self, value: Any) -> str:
        normalized = str(value or "").strip().lower()
        allowed = {"deterministic-tool", "tool-or-prompt", "prompt-only"}
        if normalized in allowed:
            return normalized
        if normalized in {"tool", "deterministic", "must-use-tool"}:
            return "deterministic-tool"
        if normalized in {"tool_or_prompt", "tool+prompt", "hybrid"}:
            return "tool-or-prompt"
        if normalized in {"prompt", "prompt_only"}:
            return "prompt-only"
        return "tool-or-prompt"

    def _require_capability_requirements_field(self, data: Dict[str, Any], stage: str) -> List[AgentCapabilityRequirement]:
        value = data.get("capability_requirements")
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError(f"{stage} 缺少数组字段 capability_requirements")

        normalized: List[AgentCapabilityRequirement] = []
        for index, item in enumerate(value):
            if isinstance(item, str):
                text = item.strip()
                if not text:
                    continue
                normalized.append(
                    AgentCapabilityRequirement(
                        capability_key=self._slugify(text)[:64],
                        capability_name=text[:80],
                        capability_type="capability",
                        description=text,
                        delivery_requirement="tool-or-prompt",
                        acceptance_criteria=[],
                    )
                )
                continue
            if not isinstance(item, dict):
                raise ValueError(f"{stage} capability_requirements[{index}] 必须是 object")

            capability_name = self._pick_str(item.get("capability_name"), self._pick_str(item.get("name"), ""))
            description = self._pick_str(item.get("description"), "")
            if not capability_name and not description:
                raise ValueError(f"{stage} capability_requirements[{index}] 缺少 capability_name/description")
            capability_key = self._pick_str(item.get("capability_key"), self._slugify(capability_name or description)[:64])
            normalized.append(
                AgentCapabilityRequirement(
                    capability_key=capability_key,
                    capability_name=capability_name or description[:80],
                    capability_type=self._normalize_capability_requirement_type(item.get("capability_type")),
                    description=description or capability_name,
                    delivery_requirement=self._normalize_delivery_requirement(item.get("delivery_requirement")),
                    acceptance_criteria=self._require_list_field(item, "acceptance_criteria", stage) if "acceptance_criteria" in item else [],
                )
            )
        return normalized[:12]

    def _build_capability_requirement_text(self, spec: AgentSpec) -> str:
        requirement_parts: List[str] = []
        for item in spec.capability_requirements or []:
            requirement_parts.extend([
                item.capability_key,
                item.capability_name,
                item.capability_type,
                item.description,
                item.delivery_requirement,
                *item.acceptance_criteria,
            ])
        fallback_parts = [
            spec.name,
            spec.primary_goal,
            *spec.responsibilities,
            *spec.constraints,
            *self._list_io_field_labels(spec.outputs),
            *spec.success_criteria,
            *spec.preferred_methods,
        ]
        return " ".join(part for part in [*requirement_parts, *fallback_parts] if part).lower()

    def _build_capability_requirement_lines(self, spec: AgentSpec) -> List[str]:
        lines: List[str] = []
        for item in spec.capability_requirements[:8]:
            line = f"- {item.capability_name} [{item.capability_type} | {item.delivery_requirement}]：{item.description}"
            if item.acceptance_criteria:
                line = f"{line}；验收：{'；'.join(item.acceptance_criteria[:3])}"
            lines.append(line)
        return lines

    def _build_gap_analysis_decision_rules(self, spec: AgentSpec) -> List[str]:
        rules = [
            "- 先把规格拆成能力原语，再判断缺口：数据原语、确定性计算原语、结果编排原语分开看。",
            "- 不要因为系统里某两个方法有专用工具，就自动推断第三个方法也必须有一个对称命名的专用工具。",
            "- 如果现有工具已经能提供原始数据、同行对比和部分确定性计算，真正缺口应描述为更底层的能力原语，而不是发明一个镜像工具名。",
            "- suggested_tools 只能写真实缺失的能力封装；若缺的是历史序列、分位数计算、适用性规则或统一结构化结果模板，就直接写这一层。",
            "- 如果现有能力足以产出要求的结果，只是需要 Prompt/模板把结果组织出来，这属于复用，不属于 blocking gap。",
        ]
        rules.extend(self._build_numeric_traceability_rules(spec))
        return rules

    def _build_gap_analysis_spec_brief(self, spec: AgentSpec) -> str:
        summary = {
            "goal": spec.primary_goal,
            "required_outputs": self._list_io_field_names(spec.outputs)[:4],
            "hard_constraints": self._dedupe([*spec.constraints, *spec.non_goals])[:6],
            "success_criteria": spec.success_criteria[:4],
            "preferred_methods": spec.preferred_methods[:4],
        }
        return json.dumps(summary, ensure_ascii=False, separators=(",", ":"))

    def _build_gap_analysis_prompt(
        self,
        spec: AgentSpec,
        known_tools: List[str],
        decision_rule_lines: List[str],
        spec_brief: str,
        capability_requirement_lines: List[str],
        key_tool_detail_lines: List[str],
        capability_coverage_map_lines: List[str],
        valuation_reuse_guidance_lines: List[str],
        compact: bool = False,
    ) -> str:
        tools_enum_lines = "\n".join(f"  - {t}" for t in known_tools) if known_tools else "  （暂无）"
        output_schema = json.dumps({
            "existing_tools": ["只能从【合法工具清单】中选，必须使用完整的 'tool_id | tool_name' 格式"],
            "suggested_tools": [{"tool_id": "示例_tool_id", "description": "一句话说明该能力做什么", "why_needed": "为什么当前系统缺这项能力"}],
            "suggested_capabilities": [{"tool_id": "示例_capability_id", "description": "一句话说明该能力做什么", "why_needed": "为什么当前系统缺这项能力"}],
            "manual_dependencies": [],
            "blocking_gaps": [],
            "fallback_strategy": [],
            "build_recommendations": [],
            "notes": [],
        }, ensure_ascii=False, indent=2)

        prompt_lines = [
            "你正在做 Agent 工坊的资源缺口分析。只判断：现有能力能否交付规格要求；若不能，真正缺的最小能力原语是什么。",
            "",
            "⚠️ 关键约束：existing_tools 字段只能从下方【合法工具清单】中选择，严禁编造或联想任何不在清单中的名称。",
            "",
            "【决策规则】",
            "\n".join(decision_rule_lines[:(5 if compact else 9)]),
            "",
            "【规格摘要】",
            spec_brief,
            "",
            "【规格能力项】",
            "\n".join(capability_requirement_lines[:8]) if capability_requirement_lines else "- 暂无显式能力项，请根据规格摘要谨慎拆解",
            "",
            f"【合法工具清单 - existing_tools 只能从此列表原样复制】\n{tools_enum_lines}",
        ]

        if not compact:
            prompt_lines.extend([
                "",
                "【重点工具能力说明 - 用于理解工具覆盖范围，existing_tools 仍只能从上方合法清单中原样复制】",
                "\n".join(key_tool_detail_lines[:6]) if key_tool_detail_lines else "- 暂无",
            ])

        prompt_lines.extend([
            "",
            "【能力覆盖映射 - 用于识别聚合工具内部已覆盖的可复用能力】",
            "\n".join(capability_coverage_map_lines[:(4 if compact else 8)]) if capability_coverage_map_lines else "- 暂无显式映射",
            "",
            "【估值复用判定规则 - 仅用于避免把已覆盖能力误判成缺口】",
            "\n".join(valuation_reuse_guidance_lines[:(4 if compact else 8)]) if valuation_reuse_guidance_lines else "- 暂无专门规则",
            "",
            "suggested_tools/suggested_capabilities 应尽量少而精，优先补最小闭环，不要一次性铺太大能力面。每个条目必须是结构化对象，包含 tool_id（简洁的蛇形命名）、description（一句话说明该能力做什么）、why_needed（为什么当前系统缺这项能力）。",
            "只输出合法 JSON，不要输出 Markdown 或额外解释。",
            "输出格式（填充以下 JSON 结构）：",
            output_schema,
            "\n分析要求：",
            "1. existing_tools 只能从上方【合法工具清单】中原样复制，不能改写、缩写或编造任何名称。只列真正能直接支撑当前 Agent 目标的能力。",
            "2. suggested_tools 只列当前闭环最缺的 1-4 个工具/Skill，每个必须是 {tool_id, description, why_needed} 对象。tool_id 必须对应真实缺失的能力原语，不能为了命名对称而臆造镜像工具。suggested_capabilities 同理。",
            "3. blocking_gaps 要写成‘为什么现有能力还不够’，不是重复需求描述。",
            "4. fallback_strategy 要写成没补齐前 Agent 如何安全降级，不要写空话。",
            "5. build_recommendations 要给出实现顺序和边界控制建议。",
            "6. 如果用户明确要求多步或多方法分别返回结果，不能只建议补一个上游接口；要把真正缺少的能力层讲清楚。",
            "7. 对估值类规格，必须优先参考 coverage_terms 与能力覆盖映射判断现有能力是否已被聚合工具覆盖，不能因为没有同名专用工具就把已存在的可调用能力误判为新缺口。",
        ])
        return "\n".join(prompt_lines)

    async def _analyze_requirement_turn(
        self,
        messages: List[str],
        user_id: str = "",
        fallback_spec_id: Optional[str] = None,
        existing_spec: Optional[AgentSpec] = None,
    ) -> Dict[str, Any]:
        started_at = perf_counter()
        client = await self._ensure_llm_client()
        llm_runtime = self._get_llm_runtime_config(client)
        base_spec = existing_spec or AgentSpec(
            spec_id=fallback_spec_id or f"agent-workshop-{uuid.uuid4().hex[:8]}",
            name="待确认 Agent",
            owner_user_id=user_id,
        )

        conversation = "\n\n".join(
            f"第{idx + 1}轮用户输入：\n{item.strip()}" for idx, item in enumerate(messages) if item and item.strip()
        )
        capability_started_at = perf_counter()
        capability_snapshot = await self._collect_capability_snapshot(conversation, top_k=12)
        capability_elapsed = round(perf_counter() - capability_started_at, 3)
        project_background_context = self._build_project_background_context()
        application_scene_context = self._build_application_scene_context()
        agent_role_pattern_context = self._build_agent_role_pattern_context()
        capability_context = self._build_capability_context(capability_snapshot, compact=True)

        prompt = "\n".join([
            "请基于下列材料整理一版可执行的 Agent 规格草案，核心任务是完成需求拆解、能力拆解和规格结构化，而不是继续做开放式追问。",
            "要求：",
            "1. 你不能把本应由专家判断的内容全部留空或退回给用户，但默认方案必须从简、够用、能落地，优先给出最小可用草案，而不是一次性补成重型专业系统。",
            "2. 如果已有草案字段没有新证据，不要整段改写成另一套说法；优先保留稳定字段，只补充新增信息、修正错误和显式默认项。",
            "3. 如果用户后续补充了限制、目标、输出、方法、样本或验收标准，必须覆盖到结果里。",
            "3.1 任何用户明确给出的数字型要求都必须原样保留，禁止擅自泛化。例如用户说“三种估值方式”，结果里不能偷换成“多种估值方法”。",
            "3.2 任何用户明确给出的交付方式都必须落到结构化字段里。例如用户说“根据这三种估值方式分别返回数据，并进行解读”，你就必须在 responsibilities、outputs、success_criteria 或 constraints 中明确体现“分别返回三种方法结果”和“对三种结果做解读”，不能只保留一个模糊的总目标。",
            "3.2.1 responsibilities 只写职责动作和交付要求，不写具体工具名、函数名或内部实现名。不要写“调用 get_peer_comparison 获取同业数据”，应改写成“获取同业估值数据，用于相对估值基准”。",
            "3.3 任何用户明确给出的非目标和禁止项都必须保留在 non_goals 或 constraints 中。例如“不直接给买卖建议”不能在整理过程中弱化或遗漏。",
            "3.4 primary_goal 可以概括，但不得吞掉关键限定词；如果用户要求里含有具体数量、方法清单、返回方式、解释要求，这些必须出现在 responsibilities / outputs / success_criteria / preferred_methods 中，而不是只剩一个抽象摘要。",
            "3.5 你必须显式产出 capability_requirements，把这个 Agent 真正依赖的能力项拆出来。能力项不是工具名清单，而是执行链路里的能力原语，例如数据获取、确定性计算、结果编排、输出格式控制、适用性/失效条件判定等。",
            "3.6 capability_requirements 至少包含 3-8 项；每项必须写清 capability_name、capability_type、description、delivery_requirement、acceptance_criteria。delivery_requirement 只能是 deterministic-tool、tool-or-prompt、prompt-only 之一。",
            "3.7 如果某能力项要求输出估值区间、评分、排序、权重或其他精确数值，delivery_requirement 不能写 prompt-only。",
            "3.8 如果用户没有明确要求，就不要主动加入高复杂度设计，例如多方法并行、长历史窗口、复杂评分体系、企业级审批流程或额外专家假设。默认采用当前系统最容易实现、最容易解释、最容易维护的方案。",
            "3.9 对估值类 Agent，不要默认写死‘近 5 年’、‘必须三种方法并行’、‘必须复杂 DCF’这类重口径；除非用户明确要求，否则只保留必要的方法和必要的比较维度。",
            "4. 如果需求明显超出当前 Agent 工坊范围、互相矛盾、或不可落地，请直接判定 not-feasible，并用口语化中文说明为什么做不到。",
            "5. 如果只是信息不够，请判定 need-clarification，但不要进入开放式追问；你应先给出推荐方案，再把最多 2 个真正影响后续实现的待确认项写入 pending_questions，供后续确认使用。",
            "6. 只有当需求已经足够清楚且可以进入下一步时，才判定 feasible。",
            "7. response_message 必须是直接给用户看的口语化中文，不要写“字段”“schema”“规格化”等系统术语；语气要像专家在给方案，不要像客服在收集需求。",
            "8. 输出必须是纯 JSON，不要 markdown，不要额外解释。",
            "9. 对股票分析类 Agent，要把现有项目的行情/财务/行业基础能力视为默认可复用前提，不要把用户当成要从零造数据底座。",
            "10. 如果用户已经明确说要基于现有项目能力做 Agent，就不要再把‘数据从哪来’这类基础设施问题当成待确认重点，除非需求里真的引入新的外部数据依赖。",
            "11. response_message 里优先写你的理解、默认方案和仍待确认的关键分歧，保持简洁，不要展开成长篇方案文档。",
            "12. 新 Agent 可能被助手直接调用、进入新建流程编排，或复用到现有模块；请基于用户目标推荐最合适的一种，不要强行收敛到既有流程节点。",
            "",
            project_background_context,
            "",
            application_scene_context,
            "",
            agent_role_pattern_context,
            "",
            capability_context,
            "",
            "当前已有草案（如果有）：",
            json.dumps(self._build_requirement_spec_snapshot(base_spec), ensure_ascii=False, indent=2),
            "",
            "用户多轮输入：",
            conversation or "（空）",
            "",
            "请输出如下 JSON：",
            "{",
            '  "feasibility_status": "feasible | need-clarification | not-feasible",',
            '  "response_message": "直接给用户看的中文回复",',
            '  "refusal_reason": "若做不到，说明原因；否则为空字符串",',
            '  "pending_questions": [],',
            '  "completeness_score": 0.0,',
            '  "name": "",',
            '  "domain": "stock_analysis 或 general",',
            '  "target_users": [],',
            '  "primary_goal": "",',
            '  "responsibilities": [],',
            '  "non_goals": [],',
            '  "inputs": [],',
            '  "outputs": [],',
            '  "success_criteria": [],',
            '  "constraints": [],',
            '  "preferred_methods": [],',
            '  "capability_requirements": [',
            '    {',
            '      "capability_key": "",',
            '      "capability_name": "",',
            '      "capability_type": "data | computation | orchestration | output | guardrail",',
            '      "description": "",',
            '      "delivery_requirement": "deterministic-tool | tool-or-prompt | prompt-only",',
            '      "acceptance_criteria": []',
            '    }',
            '  ],',
            '  "sample_symbols": []',
            "}",
            "自检要求：输出前请检查，用户原始需求里凡是出现了明确数量（如三种）、明确方法（如 DCF/PE-PB/PEG）、明确交付动作（如分别返回/进行解读）、明确禁止项（如不要直接给买卖建议），都必须在 JSON 中找到对应落点；找不到就说明你整理丢了。并且必须检查 capability_requirements 是否已经把能力原语拆清楚，而不是只重复业务目标。",
        ])

        system_prompt = "你服务于 TradingAgents-CN。它是一个面向股票投研、交易分析、Agent 编排与能力复用的金融分析系统。你的角色不是通用助手，而是金融行业专家兼 Agent 规格架构师。你的任务是基于已经收集到的需求材料，完成需求拆解、能力拆解和规格结构化，形成可执行的 Agent 规格草案，明确目标、职责边界、输入输出、依赖能力、约束条件和交付方式。你只能依据用户输入、系统背景、典型接入场景、角色模式、当前能力快照和已有草案做判断，不能臆造系统现状。这个阶段的重点不是继续和用户对话，而是把前面的需求分析结果收敛成结构化规格；如果确实存在信息缺口，只能把少数关键待确认项写入输出字段 pending_questions。你的输出必须是纯 JSON，内容要能直接用于后续规格确认与版本构建，不能输出 Markdown、寒暄或额外解释。"
        prompt_metrics = {
            "conversation_chars": len(conversation),
            "conversation_lines": len(conversation.splitlines()),
            "message_count": len([item for item in messages if item and item.strip()]),
            "project_background_chars": len(project_background_context),
            "application_scene_chars": len(application_scene_context),
            "agent_role_pattern_chars": len(agent_role_pattern_context),
            "capability_context_chars": len(capability_context),
            "capability_snapshot_elapsed_seconds": capability_elapsed,
            **self._summarize_capability_snapshot(capability_snapshot),
            **{f"llm_{key}": value for key, value in llm_runtime.items()},
        }
        self._log_llm_request_prompts(
            "requirement_clarification",
            system_prompt,
            prompt,
            context={
                "spec_id": base_spec.spec_id,
                "spec_name": base_spec.name,
                "user_id": user_id,
            },
            extra_metrics=prompt_metrics,
        )
        request_started_at = perf_counter()
        try:
            response = await client.achat([
                Message(role="system", content=system_prompt),
                Message(role="user", content=prompt),
            ])
        except Exception as exc:
            logger.error(
                "[AgentWorkshop][requirement_clarification] spec_id=%s spec_name=%s user_id=%s request_failed elapsed_seconds=%.3f llm_runtime=%s prompt_metrics=%s error=%s",
                base_spec.spec_id,
                base_spec.name,
                user_id,
                perf_counter() - request_started_at,
                self._serialize_log_payload(llm_runtime),
                self._serialize_log_payload(prompt_metrics),
                exc,
                exc_info=True,
            )
            raise
        request_elapsed = round(perf_counter() - request_started_at, 3)
        raw_content = (response.content or "").strip()
        self._log_llm_exchange(
            "requirement_clarification",
            system_prompt,
            prompt,
            raw_content,
            context={
                "spec_id": base_spec.spec_id,
                "spec_name": base_spec.name,
                "user_id": user_id,
            },
        )
        try:
            data = json.loads(self._strip_markdown_fence(raw_content))
            if not isinstance(data, dict):
                raise ValueError("requirement clarification LLM 返回的不是 JSON object")

            feasibility_status = self._require_feasibility_status(data, "requirement_clarification")
            completeness_score = self._require_score_field(data, "completeness_score", "requirement_clarification")
            pending_questions = self._require_list_field(data, "pending_questions", "requirement_clarification")[:2]
            refusal_reason = self._require_string_field(data, "refusal_reason", "requirement_clarification", allow_empty=True)
            spec = self._merge_llm_spec_data(data, base_spec, fallback_spec_id=fallback_spec_id)
            response_message = self._require_string_field(data, "response_message", "requirement_clarification")
            spec, pending_questions, completeness_score = self._post_process_requirement_clarification(
                spec=spec,
                pending_questions=pending_questions,
                completeness_score=completeness_score,
                feasibility_status=feasibility_status,
                response_message=response_message,
                conversation=conversation,
                capability_snapshot=capability_snapshot,
            )
            expert_recommendations = self._build_expert_recommendations(spec)
            ai_message = self._compose_turn_message(
                response_message,
                pending_questions,
                feasibility_status,
                expert_recommendations,
            )
        except Exception as exc:
            self._log_llm_failure(
                "requirement_clarification",
                str(exc),
                raw_response=raw_content,
                context={
                    "spec_id": base_spec.spec_id,
                    "spec_name": base_spec.name,
                    "user_id": user_id,
                },
            )
            raise AgentWorkshopLLMStageError("requirement_clarification", str(exc), raw_response=raw_content) from exc

        spec.owner_user_id = user_id
        result = {
            "spec": spec,
            "pending_questions": pending_questions,
            "completeness_score": completeness_score,
            "ai_message": ai_message,
            "feasibility_status": feasibility_status,
            "refusal_reason": refusal_reason,
        }
        logger.info(
            "[AgentWorkshop][requirement_clarification] spec_id=%s spec_name=%s user_id=%s completed total_elapsed_seconds=%.3f llm_elapsed_seconds=%.3f response_chars=%s pending_questions=%s completeness_score=%s feasibility_status=%s",
            base_spec.spec_id,
            base_spec.name,
            user_id,
            perf_counter() - started_at,
            request_elapsed,
            len(raw_content),
            len(pending_questions),
            completeness_score,
            feasibility_status,
        )
        self._log_generated_result(
            "requirement_clarification",
            {
                "spec": spec.model_dump(mode="json"),
                "pending_questions": pending_questions,
                "completeness_score": completeness_score,
                "ai_message": ai_message,
                "feasibility_status": feasibility_status,
                "refusal_reason": refusal_reason,
            },
            context={
                "spec_id": spec.spec_id,
                "spec_name": spec.name,
                "user_id": user_id,
            },
        )
        return result

    async def _ensure_llm_client(self) -> UnifiedLLMClient:
        if self._llm_client is not None:
            return self._llm_client

        try:
            from app.services.intelligent_assistant_service import get_reasoning_llm_config

            config = await get_reasoning_llm_config(self._db)
            if not config:
                raise RuntimeError("Agent 工坊当前必须依赖已配置的推理模型；请先在系统设置中配置大模型。")

            config.timeout = max(config.timeout, self._LLM_TIMEOUT)
            self._llm_client = UnifiedLLMClient.from_config(config)
            self._llm_client_meta = {
                "provider": config.provider,
                "model": config.model,
                "timeout": config.timeout,
            }
            logger.info(
                "[AgentWorkshop] LLM 客户端初始化成功: provider=%s model=%s timeout=%ss",
                config.provider,
                config.model,
                config.timeout,
            )
            return self._llm_client
        except Exception as exc:
            logger.warning("[AgentWorkshop] 初始化 LLM 客户端失败: %s", exc)
            raise RuntimeError(f"Agent 工坊初始化推理模型失败: {exc}")

    async def _generate_tooling_plan_with_llm(
        self,
        spec: AgentSpec,
        gap_report: AgentWorkshopGapAnalysis,
    ) -> Dict[str, Any]:
        client = await self._ensure_llm_client()
        design_context = self._build_solution_design_context(spec)
        prompt = "\n".join([
            "请基于当前 Agent 规格和缺口分析，产出一份工具需求草案。",
            "你不能脱离业务背景机械列工具，而要先理解这个客户真正要交付什么结果、当前系统已有何种能力、还缺哪一层能力，最后再决定工具方案。",
            "重点不是重复描述问题，而是回答 4 件事：缺什么工具、为什么缺、没补齐前如何降级、下一步先实现什么。",
            "draft_tools 里的 capability_description 必须是一句直接给界面展示的功能说明，用中文写清这个能力具体做什么、产出什么结果、补的是哪一段执行链路。不要写空话，也不要只重复 tool_id。",
            "只输出 JSON，不要输出 Markdown 或额外解释。",
            design_context,
            "JSON 结构必须如下：",
            json.dumps({
                "summary": "",
                "missing_capabilities": [],
                "draft_tools": [
                    {
                        "tool_id": "",
                        "tool_name": "",
                        "capability_description": "",
                        "priority": "P0 | P1 | P2",
                        "why_needed": "",
                        "solves_gaps": [],
                        "fallback_before_ready": "",
                        "dependencies": [],
                        "inputs": [{"name": "", "type": "", "required": True, "description": ""}],
                        "outputs": [{"name": "", "type": "", "description": ""}],
                        "acceptance_criteria": [],
                    }
                ],
                "implementation_order": [],
                "notes": [],
            }, ensure_ascii=False, indent=2),
            "系统背景：",
            self._build_project_background_context(),
            "典型接入场景：",
            self._build_application_scene_context(),
            "典型角色模式：",
            self._build_agent_role_pattern_context(),
            "Agent 规格：",
            json.dumps({
                "name": spec.name,
                "domain": spec.domain,
                "primary_goal": spec.primary_goal,
                "responsibilities": spec.responsibilities,
                "outputs": self._serialize_io_fields(spec.outputs, 8),
                "constraints": spec.constraints,
                "preferred_methods": spec.preferred_methods,
                "success_criteria": spec.success_criteria,
                "capability_requirements": [item.model_dump(mode="json") for item in (spec.capability_requirements or [])],
            }, ensure_ascii=False, indent=2),
            "缺口分析：",
            json.dumps(gap_report.model_dump(mode="json"), ensure_ascii=False, indent=2),
        ])

        system_prompt = "你正在 TradingAgents-CN 的 Agent 生命周期工坊中工作。TradingAgents-CN 是一个面向投研、交易分析、Agent 编排与能力复用的多智能体金融分析系统。你当前角色是金融行业专家兼系统架构师，负责把 Agent 规格和缺口分析转成可执行的工具与能力方案。你的判断依据只能来自规格、缺口分析、系统背景、典型场景、角色模式和已知能力快照，不能凭空假设系统现状。只输出合法 JSON。"
        raw_content = ""
        try:
            response = await client.achat([
                Message(role="system", content=system_prompt),
                Message(role="user", content=prompt),
            ])
            raw_content = (response.content or "").strip()
            self._log_llm_exchange(
                "tooling_plan",
                system_prompt,
                prompt,
                raw_content,
                context={
                    "spec_id": spec.spec_id,
                    "spec_name": spec.name,
                },
            )
            data = self._load_json_response(raw_content)
            normalized_plan = self._normalize_tooling_plan(data, spec, gap_report, raw_content)
        except Exception as exc:
            self._log_llm_failure(
                "tooling_plan",
                str(exc),
                raw_response=raw_content,
                context={
                    "spec_id": spec.spec_id,
                    "spec_name": spec.name,
                },
            )
            raise AgentWorkshopLLMStageError("tooling_plan", str(exc), raw_response=raw_content) from exc
        self._log_generated_result(
            "tooling_plan",
            normalized_plan,
            context={
                "spec_id": spec.spec_id,
                "spec_name": spec.name,
            },
        )
        return normalized_plan

    def _build_tooling_plan_error_report(
        self,
        spec: AgentSpec,
        gap_report: AgentWorkshopGapAnalysis,
        error_message: str,
        raw_response: str = "",
    ) -> Dict[str, Any]:
        raw_excerpt = (raw_response or "").strip()
        if len(raw_excerpt) > 1200:
            raw_excerpt = f"{raw_excerpt[:1200]}\n... [truncated]"

        result = {
            "summary": "工具需求草案生成失败，未做规则兜底。",
            "missing_capabilities": [],
            "draft_tools": [],
            "implementation_order": [],
            "notes": [
                "当前工具需求草案未采用规则兜底；请直接根据失败信息、日志和原始响应修正提示词或输出约束。",
                *self._dedupe(gap_report.blocking_gaps or [])[:4],
            ],
            "generated_by": "llm_failed",
            "error_message": error_message,
            "raw_response": raw_excerpt,
        }
        self._log_generated_result(
            "tooling_plan_error",
            result,
            context={
                "spec_id": spec.spec_id,
                "spec_name": spec.name,
            },
        )
        return result

    def _normalize_tooling_plan(
        self,
        data: Dict[str, Any],
        spec: AgentSpec,
        gap_report: AgentWorkshopGapAnalysis,
        raw_content: str,
    ) -> Dict[str, Any]:
        raw_tools = data.get("draft_tools")
        if not isinstance(raw_tools, list):
            raise ValueError("tooling_plan 缺少数组字段 draft_tools")
        draft_tools = []
        for item in raw_tools[:8]:
            if not isinstance(item, dict):
                raise ValueError("tooling_plan draft_tools 中存在非 object 项")
            normalized_tool_id = self._require_string_field(item, "tool_id", "tooling_plan")
            normalized_tool_name = self._require_string_field(item, "tool_name", "tooling_plan")
            normalized_why_needed = self._require_string_field(item, "why_needed", "tooling_plan")
            normalized_solves_gaps = self._require_list_field(item, "solves_gaps", "tooling_plan")
            draft_tools.append({
                "tool_id": normalized_tool_id,
                "tool_name": normalized_tool_name,
                "capability_description": self._require_string_field(item, "capability_description", "tooling_plan"),
                "priority": self._require_one_of(item, "priority", "tooling_plan", ["P0", "P1", "P2"]),
                "why_needed": normalized_why_needed,
                "solves_gaps": normalized_solves_gaps,
                "fallback_before_ready": self._require_string_field(item, "fallback_before_ready", "tooling_plan"),
                "dependencies": self._require_list_field(item, "dependencies", "tooling_plan"),
                "inputs": self._normalize_tool_schema_items(item.get("inputs"), kind="input", strict_stage="tooling_plan"),
                "outputs": self._normalize_tool_schema_items(item.get("outputs"), kind="output", strict_stage="tooling_plan"),
                "acceptance_criteria": self._require_list_field(item, "acceptance_criteria", "tooling_plan"),
            })

        if not draft_tools:
            raise ValueError("tooling plan LLM 未返回有效的 draft_tools")

        return {
            "summary": self._require_string_field(data, "summary", "tooling_plan"),
            "missing_capabilities": self._require_list_field(data, "missing_capabilities", "tooling_plan"),
            "draft_tools": draft_tools,
            "implementation_order": self._require_list_field(data, "implementation_order", "tooling_plan"),
            "notes": self._require_list_field(data, "notes", "tooling_plan"),
            "generated_by": "llm",
            "raw_response": raw_content,
        }

    def _normalize_tool_schema_items(self, value: Any, kind: str, strict_stage: str) -> List[Dict[str, Any]]:
        if not isinstance(value, list):
            raise ValueError(f"{strict_stage} 缺少数组字段 {kind}s")
        normalized: List[Dict[str, Any]] = []
        for item in value[:12]:
            if not isinstance(item, dict):
                raise ValueError(f"{strict_stage} 的 {kind}s 中存在非 object 项")
            normalized.append({
                "name": self._require_string_field(item, "name", strict_stage),
                "type": self._require_string_field(item, "type", strict_stage),
                "required": bool(item.get("required", kind == "input")),
                "description": self._require_string_field(item, "description", strict_stage),
            })
        return normalized

    def _build_tool_blueprint(
        self,
        tool_id: str,
        spec: AgentSpec,
        gap_report: AgentWorkshopGapAnalysis,
    ) -> Dict[str, Any]:
        blueprint = {
            "tool_name": tool_id,
            "priority": "P1",
            "why_needed": "用于补齐当前工坊识别到的能力缺口。",
            "solves_gaps": gap_report.blocking_gaps[:2],
            "dependencies": gap_report.manual_dependencies[:3],
            "inputs": [],
            "outputs": [],
            "acceptance_criteria": ["能稳定补齐当前缺口，并输出可复核结果。"],
        }
        return {
            "tool_id": tool_id,
            "tool_name": blueprint["tool_name"],
            "capability_description": self._build_tool_capability_description(
                tool_id,
                blueprint["tool_name"],
                blueprint["why_needed"],
                blueprint["solves_gaps"],
            ),
            "priority": blueprint["priority"],
            "why_needed": blueprint["why_needed"],
            "solves_gaps": blueprint["solves_gaps"],
            "fallback_before_ready": gap_report.fallback_strategy[0] if gap_report.fallback_strategy else "缺少工具时，先降级执行并明确说明当前边界。",
            "dependencies": blueprint["dependencies"],
            "inputs": blueprint["inputs"],
            "outputs": blueprint["outputs"],
            "acceptance_criteria": blueprint["acceptance_criteria"],
        }

    def _build_tool_capability_description(
        self,
        tool_id: str,
        tool_name: str,
        why_needed: str,
        solves_gaps: List[str],
    ) -> str:
        title = self._pick_str(tool_name, self._pick_str(tool_id, "待定义能力"))
        reason = self._pick_str(why_needed, "")
        if reason and all(keyword not in reason for keyword in ["缺口", "补齐", "能力"]):
            return reason
        if solves_gaps:
            return f"这个能力用于让 Agent 在“{title}”这段执行链路中稳定产出结构化结果，主要解决：{solves_gaps[0]}"
        return f"这个能力用于让 Agent 在“{title}”这段执行链路中稳定产出可直接消费的结构化结果。"

    def _merge_llm_spec_data(self, data: Dict[str, Any], fallback_spec: AgentSpec, fallback_spec_id: Optional[str] = None) -> AgentSpec:
        name = self._require_string_field(data, "name", "requirement_clarification")
        domain = self._require_domain_field(data, "domain", "requirement_clarification")
        resolved_spec_id = fallback_spec_id or fallback_spec.spec_id
        if not resolved_spec_id or resolved_spec_id.startswith("agent-workshop-"):
            resolved_spec_id = self._slugify(name or fallback_spec.name or f"agent-workshop-{uuid.uuid4().hex[:8]}")

        return AgentSpec(
            spec_id=resolved_spec_id,
            name=name,
            domain=domain,
            target_users=self._require_list_field(data, "target_users", "requirement_clarification"),
            primary_goal=self._require_string_field(data, "primary_goal", "requirement_clarification"),
            responsibilities=self._sanitize_spec_responsibilities(
                self._require_list_field(data, "responsibilities", "requirement_clarification")
            ),
            non_goals=self._require_list_field(data, "non_goals", "requirement_clarification"),
            inputs=self._require_io_fields_field(data, "inputs", "requirement_clarification"),
            outputs=self._require_io_fields_field(data, "outputs", "requirement_clarification"),
            success_criteria=self._require_list_field(data, "success_criteria", "requirement_clarification"),
            constraints=self._require_list_field(data, "constraints", "requirement_clarification"),
            preferred_methods=self._require_list_field(data, "preferred_methods", "requirement_clarification"),
            capability_requirements=self._require_capability_requirements_field(data, "requirement_clarification"),
            sample_symbols=self._require_list_field(data, "sample_symbols", "requirement_clarification"),
            status=fallback_spec.status,
            source=fallback_spec.source,
            owner_user_id=fallback_spec.owner_user_id,
            latest_session_id=fallback_spec.latest_session_id,
            current_version_id=fallback_spec.current_version_id,
            version_count=fallback_spec.version_count,
            created_at=fallback_spec.created_at,
            updated_at=now_tz(),
        )

    def _strip_markdown_fence(self, content: str) -> str:
        if content.startswith("```"):
            content = content.split("\n", 1)[1] if "\n" in content else content[3:]
        if content.endswith("```"):
            content = content[:-3]
        return content.strip()

    def _require_string_field(self, data: Dict[str, Any], key: str, stage: str, allow_empty: bool = False) -> str:
        value = data.get(key)
        if not isinstance(value, str):
            raise ValueError(f"{stage} 缺少字符串字段 {key}")
        text = value.strip()
        if not allow_empty and not text:
            raise ValueError(f"{stage} 字段 {key} 不能为空")
        return text

    def _require_list_field(self, data: Dict[str, Any], key: str, stage: str) -> List[str]:
        value = data.get(key)
        if not isinstance(value, list):
            # 兼容 LLM 返回单个字符串的情况
            if isinstance(value, str) and value.strip():
                return [value.strip()]
            raise ValueError(f"{stage} 缺少数组字段 {key}")
        normalized: List[str] = []
        for item in value:
            if isinstance(item, (str, int, float)):
                text = str(item).strip()
            elif isinstance(item, dict):
                text = self._extract_object_text(item)
                if not text:
                    continue  # 跳过无法提取文本的字典项
            elif isinstance(item, list):
                # 跳过嵌套数组
                continue
            else:
                text = str(item).strip()
            if text:
                normalized.append(text)
        return self._dedupe(normalized)

    def _parse_suggested_items(self, raw_list: Any) -> List[SuggestedToolItem]:
        """将 LLM 返回的 suggested_tools / suggested_capabilities 解析为 SuggestedToolItem 列表。

        兼容两种格式：
        - 结构化对象：[{"tool_id": "...", "description": "...", "why_needed": "..."}]
        - 旧版纯字符串：["tool_id_1", "tool_id_2"]
        """
        if not isinstance(raw_list, list):
            if isinstance(raw_list, str) and raw_list.strip():
                return [SuggestedToolItem(tool_id=raw_list.strip())]
            return []
        results: List[SuggestedToolItem] = []
        seen_ids: set = set()
        for item in raw_list:
            if isinstance(item, dict):
                tool_id = str(item.get("tool_id", item.get("id", item.get("name", "")))).strip()
                description = str(item.get("description", item.get("desc", ""))).strip()
                why_needed = str(item.get("why_needed", item.get("reason", ""))).strip()
                if tool_id and tool_id not in seen_ids:
                    seen_ids.add(tool_id)
                    results.append(SuggestedToolItem(tool_id=tool_id, description=description, why_needed=why_needed))
            elif isinstance(item, str) and item.strip():
                tool_id = item.strip()
                if tool_id not in seen_ids:
                    seen_ids.add(tool_id)
                    results.append(SuggestedToolItem(tool_id=tool_id))
        return results

    def _require_score_field(self, data: Dict[str, Any], key: str, stage: str) -> float:
        if key not in data:
            raise ValueError(f"{stage} 缺少数值字段 {key}")
        try:
            value = float(data.get(key))
        except (TypeError, ValueError):
            raise ValueError(f"{stage} 字段 {key} 不是合法数值")
        return max(0.0, min(1.0, round(value, 2)))

    def _require_domain_field(self, data: Dict[str, Any], key: str, stage: str) -> str:
        value = self._require_string_field(data, key, stage)
        if value not in {"stock_analysis", "general"}:
            raise ValueError(f"{stage} 字段 {key} 必须是 stock_analysis 或 general")
        return value

    def _require_one_of(self, data: Dict[str, Any], key: str, stage: str, allowed: List[str]) -> str:
        value = self._require_string_field(data, key, stage)
        if value not in allowed:
            raise ValueError(f"{stage} 字段 {key} 必须是 {' / '.join(allowed)}")
        return value

    def _require_feasibility_status(self, data: Dict[str, Any], stage: str) -> str:
        return self._require_one_of(data, "feasibility_status", stage, ["feasible", "need-clarification", "not-feasible"])

    def _pick_str(self, value: Any, fallback: str) -> str:
        if isinstance(value, str) and value.strip():
            return value.strip()
        return fallback

    def _pick_domain(self, value: Any, fallback: str) -> str:
        if isinstance(value, str) and value.strip() in {"stock_analysis", "general"}:
            return value.strip()
        return fallback

    def _pick_float(self, value: Any, fallback: float) -> float:
        try:
            num = float(value)
        except (TypeError, ValueError):
            return fallback
        return max(0.0, min(1.0, round(num, 2)))

    def _normalize_feasibility_status(self, value: Any) -> str:
        normalized = str(value or "").strip().lower()
        if normalized in {"feasible", "need-clarification", "not-feasible"}:
            return normalized
        if normalized in {"clarify", "needs-clarification", "needs_clarification"}:
            return "need-clarification"
        if normalized in {"blocked", "impossible", "infeasible", "not_feasible"}:
            return "not-feasible"
        return "need-clarification"

    def _build_readiness(self, feasibility_status: str, completeness_score: float) -> str:
        if feasibility_status == "not-feasible":
            return "blocked"
        if feasibility_status == "feasible" and completeness_score >= 0.75:
            return "ready"
        return "needs-clarification"

    def _infer_stage(self, feasibility_status: str, completeness_score: float) -> AgentWorkshopStage:
        if feasibility_status == "feasible" and completeness_score >= 0.75:
            return AgentWorkshopStage.PLANNING
        return AgentWorkshopStage.GATHERING

    def _ensure_session_can_continue(self, session: AgentWorkshopSession) -> None:
        if session.feasibility_status == "not-feasible":
            raise ValueError(session.refusal_reason or "当前需求超出 Agent 工坊可支持范围，无法继续生成版本。")
        if session.feasibility_status != "feasible" or session.completeness_score < 0.75:
            raise ValueError("当前需求还没澄清清楚，请先继续和工坊助手确认目标、边界和输出。")

    def _build_fallback_turn_message(
        self,
        spec: AgentSpec,
        pending_questions: List[str],
        completeness_score: float,
        feasibility_status: str,
        refusal_reason: str,
        expert_recommendations: List[str],
    ) -> str:
        if feasibility_status == "not-feasible":
            return refusal_reason or "这类需求当前没法稳定落到 Agent 工坊里，我建议先把目标收窄一点，再继续讨论。"
        if feasibility_status == "need-clarification":
            recommendation_block = "\n".join(f"- {item}" for item in expert_recommendations[:3])
            question_block = "\n".join(f"{idx + 1}. {item}" for idx, item in enumerate(pending_questions[:2]))
            message_parts = [
                f"我先按你的目标补成一版可执行草案，当前我建议把“{spec.name}”先这样设计：",
            ]
            if recommendation_block:
                message_parts.append(recommendation_block)
            if question_block:
                message_parts.append(f"还剩 1 到 2 个关键点需要你拍板：\n{question_block}")
            return "\n\n".join(message_parts).strip()
        return f"我已经把这个 Agent 的核心需求整理出来了，当前大概有 {int(completeness_score * 100)}%，可以往下一步走。"

    def _compose_turn_message(
        self,
        message: str,
        pending_questions: List[str],
        feasibility_status: str,
        expert_recommendations: Optional[List[str]] = None,
    ) -> str:
        base_message = (message or "").strip()
        recommendation_items = [item for item in (expert_recommendations or []) if item]

        if recommendation_items:
            contains_recommendation_text = any(item in base_message for item in recommendation_items)
            contains_recommendation_header = any(token in base_message for token in ["建议", "推荐", "默认", "我会先按"])
            if not contains_recommendation_text and not contains_recommendation_header:
                recommendation_block = "\n".join(f"- {item}" for item in recommendation_items[:3])
                if recommendation_block:
                    prefix = "我先给你一个推荐方案："
                    base_message = f"{base_message}\n\n{prefix}\n{recommendation_block}".strip() if base_message else f"{prefix}\n{recommendation_block}"

        if feasibility_status != "need-clarification" or not pending_questions:
            return base_message

        normalized = base_message.replace("：", ":")
        has_numbered_question = any(f"{idx + 1}." in normalized or f"{idx + 1}、" in normalized for idx in range(len(pending_questions)))
        contains_question_text = any(question in base_message for question in pending_questions)
        if has_numbered_question or contains_question_text:
            return base_message

        question_block = "\n".join(f"{idx + 1}. {question}" for idx, question in enumerate(pending_questions[:3]))
        separator = "\n\n" if base_message else ""
        if base_message and not base_message.rstrip().endswith((":", "：", "?", "？")):
            base_message = f"{base_message}\n\n还需要你确认这几个关键点："
            separator = "\n"
        return f"{base_message}{separator}{question_block}".strip()

    def _build_expert_recommendations(self, spec: AgentSpec) -> List[str]:
        if self._is_valuation_spec(spec):
            return self._dedupe([
                "先用当前系统最容易落地的估值方法收敛成可用版本，不默认叠加复杂模型。",
                "展示先聚焦在方法结果、简单解释和适用边界，不默认展开复杂评分卡或长篇因子体系。",
                "历史区间、同行对比和假设说明都可以保留，但不要先写死过重参数；优先使用容易理解、容易维护的默认口径。",
            ])

        recommendations: List[str] = []
        if spec.primary_goal:
            recommendations.append(f"我建议先围绕“{spec.primary_goal}”收敛设计，避免功能边界过宽。")
        if spec.outputs:
            recommendations.append(f"输出先默认做成结构化卡片，核心包括：{'、'.join(self._list_io_field_labels(spec.outputs)[:4])}。")
        if spec.responsibilities:
            recommendations.append(f"职责先聚焦在：{'、'.join(spec.responsibilities[:3])}，暂时不要把相邻能力混进来。")
        if spec.non_goals:
            recommendations.append(f"边界上我建议继续明确不做：{'、'.join(spec.non_goals[:3])}。")

        return self._dedupe(recommendations[:4])

    def _pick_list(self, value: Any, fallback: List[str]) -> List[str]:
        if not isinstance(value, list):
            return fallback
        normalized = self._dedupe([
            str(item).strip() for item in value if isinstance(item, (str, int, float)) and str(item).strip()
        ])
        return normalized or fallback

    def _build_spec_overview(self, spec: AgentSpec) -> Dict[str, Any]:
        return {
            "name": spec.name,
            "domain": spec.domain,
            "primary_goal": spec.primary_goal,
            "outputs": self._list_io_field_names(spec.outputs)[:5],
            "non_goals": spec.non_goals[:3],
        }

    def _build_required_capability_label(self, tool_id: str, tool_name: str = "") -> str:
        normalized_name = str(tool_name or "").replace("工具", "").strip()
        if normalized_name:
            return f"{normalized_name}能力"

        normalized_tool_id = str(tool_id or "").strip()
        if not normalized_tool_id:
            return "待补可调用能力"
        return f"{normalized_tool_id} 可调用能力"

    async def _build_gap_analysis(self, spec: AgentSpec) -> AgentWorkshopGapAnalysis:
        capability_snapshot = await self._collect_capability_snapshot(
            self._build_valuation_requirement_text(spec),
            top_k=16,
        )
        try:
            return await self._build_gap_analysis_with_llm(spec, capability_snapshot)
        except Exception as exc:
            logger.warning("[AgentWorkshop] 生成缺口分析时 LLM 失败，直接暴露错误: %s", exc, exc_info=True)
            raw_response = exc.raw_response if isinstance(exc, AgentWorkshopLLMStageError) else ""
            gap_report = self._build_gap_analysis_error_report(
                spec,
                capability_snapshot,
                error_message=str(exc),
                raw_response=raw_response,
            )
            return gap_report

    def _build_gap_analysis_error_report(
        self,
        spec: AgentSpec,
        capability_snapshot: Dict[str, Any],
        error_message: str,
        raw_response: str = "",
    ) -> AgentWorkshopGapAnalysis:
        existing_tools: List[str] = []
        if spec.domain == "stock_analysis":
            existing_tools.extend(capability_snapshot.get("builtin_data_tools", [])[:6])
            existing_tools.extend(capability_snapshot.get("builtin_analysis_tools", [])[:4])
            existing_tools.extend(capability_snapshot.get("external_data_skills", [])[:4])
            existing_tools.extend(capability_snapshot.get("external_analysis_skills", [])[:4])

        raw_excerpt = (raw_response or "").strip()
        if len(raw_excerpt) > 1200:
            raw_excerpt = f"{raw_excerpt[:1200]}\n... [truncated]"

        notes = [
            "当前缺口分析未采用规则兜底；以下内容用于直接暴露 LLM 失败现场，便于继续修正提示词或输出约束。",
            f"缺口分析调用信息：{self._format_gap_analysis_llm_log()}",
        ]
        if raw_excerpt:
            notes.append("LLM 已返回内容，但未通过当前 gap analysis 的结构校验。")
        else:
            notes.append("LLM 未返回可解析的 gap analysis 内容。")

        gap_report = AgentWorkshopGapAnalysis(
            existing_tools=self._dedupe(existing_tools)[:12],
            suggested_tools=[],
            suggested_capabilities=[],
            manual_dependencies=[],
            blocking_gaps=[f"缺口分析生成失败：{error_message}"],
            fallback_strategy=[],
            build_recommendations=[
                "先查看日志中的 gap_analysis system_prompt、user_prompt 和 raw_response，确认是提示词约束不够还是模型未按 JSON 返回。",
                "确认修复前，不要根据这次失败结果继续补能力，以免把错误分析继续传递到后续流程。",
            ],
            notes=notes,
            generated_by="llm_failed",
            error_message=error_message,
            raw_response=raw_excerpt,
        )
        gap_report = self._enforce_valuation_gap_report(spec, gap_report, capability_snapshot)
        self._log_generated_result(
            "gap_analysis_error",
            gap_report.model_dump(mode="json"),
            context={
                "spec_id": spec.spec_id,
                "spec_name": spec.name,
            },
        )
        return gap_report

    def _format_gap_analysis_llm_log(self) -> str:
        provider = self._pick_str(self._llm_client_meta.get("provider") if self._llm_client_meta else None, "unknown")
        model = self._pick_str(self._llm_client_meta.get("model") if self._llm_client_meta else None, "unknown")
        timeout = self._llm_client_meta.get("timeout") if self._llm_client_meta else "unknown"
        return f"provider={provider} model={model} timeout={timeout}s"

    def _detect_gap_analysis_mode(self, gap_report: AgentWorkshopGapAnalysis) -> str:
        notes = gap_report.notes or []
        if gap_report.generated_by:
            return gap_report.generated_by
        if any("推理模型生成" in note for note in notes):
            return "llm"
        return "unknown"

    async def _build_gap_analysis_with_llm(
        self,
        spec: AgentSpec,
        capability_snapshot: Dict[str, Any],
    ) -> AgentWorkshopGapAnalysis:
        client = await self._ensure_llm_client()
        selected_tool_details = self._select_gap_analysis_tool_details(spec, capability_snapshot)
        known_tools = self._dedupe([
            *(detail.get("label") for detail in selected_tool_details if detail.get("label")),
        ])
        key_tool_detail_lines = self._format_tool_detail_lines(selected_tool_details, limit=8)
        valuation_reuse_guidance_lines = self._build_valuation_reuse_guidance_lines(spec, capability_snapshot)
        capability_coverage_map_lines = self._build_capability_coverage_map_lines(spec, selected_tool_details)
        capability_requirement_lines = self._build_capability_requirement_lines(spec)
        decision_rule_lines = self._build_gap_analysis_decision_rules(spec)
        spec_brief = self._build_gap_analysis_spec_brief(spec)
        enriched_prompt = self._build_gap_analysis_prompt(
            spec=spec,
            known_tools=known_tools,
            decision_rule_lines=decision_rule_lines,
            spec_brief=spec_brief,
            capability_requirement_lines=capability_requirement_lines,
            key_tool_detail_lines=key_tool_detail_lines,
            capability_coverage_map_lines=capability_coverage_map_lines,
            valuation_reuse_guidance_lines=valuation_reuse_guidance_lines,
            compact=False,
        )
        compact_prompt = self._build_gap_analysis_prompt(
            spec=spec,
            known_tools=known_tools[:8],
            decision_rule_lines=decision_rule_lines,
            spec_brief=spec_brief,
            capability_requirement_lines=capability_requirement_lines,
            key_tool_detail_lines=key_tool_detail_lines,
            capability_coverage_map_lines=capability_coverage_map_lines,
            valuation_reuse_guidance_lines=valuation_reuse_guidance_lines,
            compact=True,
        )
        system_prompt = "你是 TradingAgents-CN Agent 工坊的缺口分析器。先判断现有能力能否满足规格，再识别真正缺失的最小能力原语。禁止因为命名对称或类比现有工具而臆造新工具。只输出合法 JSON。"

        raw = ""
        try:
            response = None
            used_prompt = ""
            request_name = ""
            prompt_attempts = [
                (
                    "gap_analysis_request_compact_first",
                    compact_prompt,
                    {
                        "known_tools": min(len(known_tools), 8),
                        "selected_tool_details": min(len(selected_tool_details), 6),
                        "capability_requirements": len(spec.capability_requirements or []),
                    },
                ),
                (
                    "gap_analysis_request_enriched_retry",
                    enriched_prompt,
                    {
                        "known_tools": len(known_tools),
                        "selected_tool_details": len(selected_tool_details),
                        "capability_requirements": len(spec.capability_requirements or []),
                    },
                ),
            ]

            last_error: Optional[Exception] = None
            for attempt_index, (attempt_name, attempt_prompt, attempt_metrics) in enumerate(prompt_attempts, start=1):
                self._log_llm_request_prompts(
                    attempt_name,
                    system_prompt,
                    attempt_prompt,
                    context={
                        "spec_id": spec.spec_id,
                        "spec_name": spec.name,
                    },
                    extra_metrics=attempt_metrics,
                )
                try:
                    response = await client.achat([
                        Message(role="system", content=system_prompt),
                        Message(role="user", content=attempt_prompt),
                    ])
                except Exception as exc:
                    last_error = exc
                    logger.warning(
                        "[AgentWorkshop] gap_analysis 第 %s 次请求失败，准备升级上下文重试: spec_id=%s spec_name=%s error=%s",
                        attempt_index,
                        spec.spec_id,
                        spec.name,
                        exc,
                    )
                    continue
                raw = response.content or ""
                used_prompt = attempt_prompt
                request_name = attempt_name
                self._log_llm_exchange(
                    attempt_name,
                    system_prompt,
                    attempt_prompt,
                    raw,
                    context={
                        "spec_id": spec.spec_id,
                        "spec_name": spec.name,
                    },
                )
                json_match = re.search(r"\{.*\}", raw, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                    break

                last_error = ValueError("gap analysis LLM 未返回合法 JSON")
                logger.warning(
                    "[AgentWorkshop] gap_analysis 第 %s 次请求结果不可解析，准备升级上下文重试: spec_id=%s spec_name=%s",
                    attempt_index,
                    spec.spec_id,
                    spec.name,
                )
            else:
                if last_error is not None:
                    raise last_error
                raise ValueError("gap analysis LLM 未返回合法 JSON")
        except Exception as exc:
            self._log_llm_failure(
                "gap_analysis",
                str(exc),
                raw_response=raw,
                context={
                    "spec_id": spec.spec_id,
                    "spec_name": spec.name,
                },
            )
            raise AgentWorkshopLLMStageError("gap_analysis", str(exc), raw_response=raw) from exc

        known_tool_set = set(known_tools)
        existing_tools_raw = self._require_list_field(data, "existing_tools", "gap_analysis")
        invalid_tools = [item for item in existing_tools_raw if item not in known_tool_set]
        existing_tools = [item for item in existing_tools_raw if item in known_tool_set]
        if invalid_tools:
            logger.warning(
                "[AgentWorkshop] gap_analysis existing_tools 中过滤掉 LLM 幻觉工具: %s",
                ", ".join(invalid_tools),
            )

        notes = self._require_list_field(data, "notes", "gap_analysis")
        notes.append(
            f"缺口分析由推理模型生成：provider={self._llm_client_meta.get('provider')} model={self._llm_client_meta.get('model')} timeout={self._llm_client_meta.get('timeout')}s"
        )
        suggested_tools = self._parse_suggested_items(data.get("suggested_tools", []))[:8]
        suggested_capabilities = self._parse_suggested_items(data.get("suggested_capabilities", data.get("suggested_skills", [])))[:8]
        registered_capability_ids = self._collect_registered_capability_ids(capability_snapshot)
        suggested_tools, existing_suggested_tools = self._partition_existing_suggested_items(suggested_tools, registered_capability_ids)
        suggested_capabilities, existing_suggested_capabilities = self._partition_existing_suggested_items(suggested_capabilities, registered_capability_ids)
        build_recommendations = self._dedupe(self._require_list_field(data, "build_recommendations", "gap_analysis"))[:10]

        existing_suggested_ids = self._dedupe([
            *(item.tool_id for item in existing_suggested_tools if item.tool_id),
            *(item.tool_id for item in existing_suggested_capabilities if item.tool_id),
        ])
        if existing_suggested_ids:
            notes.append(
                f"以下能力已在能力工坊或 external_skills 中存在，本轮缺口建议已自动过滤：{', '.join(existing_suggested_ids[:6])}"
            )
            build_recommendations = self._dedupe([
                f"如果页面还显示这些旧缺口，建议重新做一次缺口分析刷新：{', '.join(existing_suggested_ids[:4])}",
                *build_recommendations,
            ])[:10]

        gap_report = AgentWorkshopGapAnalysis(
            existing_tools=self._dedupe(existing_tools)[:12],
            suggested_tools=suggested_tools,
            suggested_capabilities=suggested_capabilities,
            manual_dependencies=self._dedupe(self._require_list_field(data, "manual_dependencies", "gap_analysis"))[:8],
            blocking_gaps=self._dedupe(self._require_list_field(data, "blocking_gaps", "gap_analysis"))[:8],
            fallback_strategy=self._dedupe(self._require_list_field(data, "fallback_strategy", "gap_analysis"))[:8],
            build_recommendations=build_recommendations,
            notes=self._dedupe(notes)[:10],
            generated_by="llm",
            error_message="",
            raw_response=raw,
        )
        gap_report = self._enforce_valuation_gap_report(spec, gap_report, capability_snapshot)
        self._log_generated_result(
            "gap_analysis",
            gap_report.model_dump(mode="json"),
            context={
                "spec_id": spec.spec_id,
                "spec_name": spec.name,
            },
        )
        return gap_report

    async def get_capability_snapshot(self) -> Dict[str, Any]:
        snapshot = await self._collect_capability_snapshot("金融分析 Agent 能力总览")
        return {
            **snapshot,
            "summary_text": self._build_capability_context(snapshot),
        }

    def _select_required_tools(self, spec: AgentSpec, gap_report: AgentWorkshopGapAnalysis) -> List[str]:
        registry = get_tool_registry()
        tool_ids = [tool.id for tool in registry.list_all()]
        tool_id_set = set(tool_ids)
        selected: List[str] = []

        if self._is_valuation_spec(spec):
            preferred_ids = [
                "get_value_factor_bundle_tool",
                "get_stock_fundamentals_unified",
                "get_peer_comparison",
                "calculate_pb_relative_valuation",
                "calculate_peg_valuation",
                "get_growth_cashflow_factor_bundle_tool",
                "get_income_analysis",
                "get_cashflow_analysis",
                "get_balance_sheet_analysis",
                "get_stock_market_data_unified",
            ]
        else:
            preferred_ids = [
                "get_stock_market_data_unified",
                "get_stock_fundamentals_unified",
                "get_stock_news_unified",
            ]
        # 第三步生成版本时，优先继承第二步缺口分析已确认的 existing_tools，避免重新退回到通用默认工具集。
        for tool_label in gap_report.existing_tools or []:
            tool_id = self._normalize_capability_id(tool_label)
            if tool_id in tool_id_set and tool_id not in selected:
                selected.append(tool_id)

        for tool_id in preferred_ids:
            if tool_id in tool_id_set and tool_id not in selected:
                selected.append(tool_id)

        max_tools = 8 if self._is_valuation_spec(spec) else 4
        return selected[:max_tools]

    def _select_required_capabilities(
        self,
        gap_report: AgentWorkshopGapAnalysis,
        tooling_plan: Optional[Dict[str, Any]] = None,
        capability_snapshot: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        selected: List[str] = []
        registered_capability_ids = self._collect_registered_capability_ids(capability_snapshot or {}) if capability_snapshot else set()
        for cap_item in gap_report.suggested_capabilities or []:
            cap_id = cap_item.tool_id if isinstance(cap_item, SuggestedToolItem) else str(cap_item)
            if cap_id:
                selected.append(self._build_required_capability_label(cap_id))

        if isinstance(tooling_plan, dict):
            selected.extend(self._pick_list(tooling_plan.get("missing_capabilities"), []))
            draft_tools = tooling_plan.get("draft_tools") if isinstance(tooling_plan.get("draft_tools"), list) else []
            for item in draft_tools[:8]:
                if not isinstance(item, dict):
                    continue
                selected.append(
                    self._build_required_capability_label(
                        self._pick_str(item.get("tool_id"), ""),
                        self._pick_str(item.get("tool_name"), ""),
                    )
                )

        for tool_item in gap_report.suggested_tools or []:
            tid = tool_item.tool_id if isinstance(tool_item, SuggestedToolItem) else str(tool_item)
            selected.append(self._build_required_capability_label(tid))

        deduped = self._dedupe([item for item in selected if item])
        if not registered_capability_ids:
            return deduped[:8]

        filtered: List[str] = []
        for item in deduped:
            normalized = self._normalize_capability_id(item)
            if normalized and normalized in registered_capability_ids:
                continue
            filtered.append(item)

        return filtered[:8]

    def _build_output_schema(self, spec: AgentSpec) -> Dict[str, Any]:
        output_names = self._list_io_field_names(spec.outputs)
        properties = {
            output_name: {
                "type": self._get_io_field_type(item),
                "description": self._get_io_field_label(item) or output_name,
            }
            for item in spec.outputs
            for output_name in [self._get_io_field_name(item)]
            if output_name
        }
        return {
            "type": "object",
            "required": output_names,
            "properties": properties,
        }

    def _build_evaluation_policy(self, spec: AgentSpec) -> Dict[str, Any]:
        policy = {
            "dimensions": [
                "role_alignment",
                "user_goal_alignment",
                "output_completeness",
                "explainability",
            ],
            "success_criteria": spec.success_criteria,
            "benchmark_hint": spec.sample_symbols,
            "minimum_score": 0.75,
            "required_tool_strategy": "required_tools 表示当前版本允许且优先考虑的候选工具集，应按任务需要选择性调用，而不是机械调用全部工具。",
        }
        numeric_policy = self._get_numeric_traceability_policy(spec)
        if numeric_policy["enabled"]:
            policy["numeric_traceability_required"] = numeric_policy["trace_numeric_if_present"]
            policy["numeric_traceability_policy"] = {
                "exact_numeric_must_come_from_data_or_tools": numeric_policy["requires_exact_numeric_outputs"],
                "llm_must_not_invent_numbers": True,
                "require_source_labels": numeric_policy["requires_source_labels"],
            }
        return policy

    async def _create_prompt_template(
        self,
        version_id: str,
        spec: AgentSpec,
        required_tools: List[str],
        gap_report: Optional[AgentWorkshopGapAnalysis] = None,
        tooling_plan: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        prompt_service = PromptTemplateService(db=self._db)

        responsibilities = "\n".join(f"- {item}" for item in spec.responsibilities)
        success_criteria = "\n".join(f"- {item}" for item in spec.success_criteria)
        non_goals = "\n".join(f"- {item}" for item in spec.non_goals)
        constraint_lines = [f"- {item}" for item in spec.constraints]
        output_fields = "\n".join(f"- {item}" for item in self._list_io_field_labels(spec.outputs))
        tools_text = "\n".join(f"- {item}" for item in required_tools) if required_tools else "- 当前版本尚未绑定工具"
        gap_existing_tools = self._dedupe((gap_report.existing_tools if gap_report else []) or [])[:8]
        gap_existing_tool_lookup: Dict[str, str] = {}
        for item in gap_existing_tools:
            normalized = self._normalize_capability_id(item)
            if normalized and normalized not in gap_existing_tool_lookup:
                gap_existing_tool_lookup[normalized] = item
        tool_display_lines = [
            f"- {gap_existing_tool_lookup.get(tool_id, tool_id)}"
            for tool_id in required_tools
        ] if required_tools else ["- 当前版本尚未绑定工具"]
        missing_capabilities = self._dedupe([
            *((tooling_plan or {}).get("missing_capabilities", []) if isinstance(tooling_plan, dict) else []),
            *([item.tool_id for item in (gap_report.suggested_tools or []) if isinstance(item, SuggestedToolItem)] if gap_report else []),
        ])[:6]
        numeric_rules = self._build_numeric_traceability_rules(spec)
        numeric_policy = self._get_numeric_traceability_policy(spec)
        if numeric_rules:
            constraint_lines.extend(numeric_rules)
        constraints = "\n".join(self._dedupe(constraint_lines))
        tool_strategy_lines = [
            "- required_tools 表示当前版本允许且优先考虑的候选工具集，不是要求把全部工具机械调用一遍。",
            "- 你必须先判断当前任务需要哪些证据，再在 required_tools 中选择最少且足够的工具完成分析。",
            "- 如果某个结论，尤其是估值区间、目标价、评分、排序、权重等精确数值，理论上应由工具或结构化数据支撑，就必须调用对应工具或引用上游已提供的可追溯数据。",
            "- 如果当前 required_tools 里没有能支撑该数字的工具，或者数据不足，就明确说明无法给出该精确数字，只能输出定性判断或降级结论。",
        ]

        tool_guidance_title = "优先使用以下工具获取事实依据："
        if gap_existing_tools:
            tool_guidance_title = "优先使用以下工具获取事实依据（已继承第二步缺口分析确认的可复用工具）："
        tool_guidance = f"{tool_guidance_title}\n" + "\n".join(tool_display_lines)
        tool_guidance = f"{tool_guidance}\n\nrequired_tools 使用策略：\n" + "\n".join(tool_strategy_lines)
        if numeric_rules:
            tool_guidance = f"{tool_guidance}\n\n数值输出总原则：\n" + "\n".join(numeric_rules)

        output_format = (
            "请输出结构化结果，至少包含以下字段：\n"
            f"{output_fields or '- summary'}"
        )
        if numeric_policy["enabled"] and numeric_policy["requires_exact_numeric_outputs"]:
            output_format = "\n\n".join([
                output_format,
                "若当前规格要求输出评分、排序、区间、目标值、权重等精确数值，必须同时给出每个数字的来源数据、所依据的工具结果和关键输入参数。若没有足够依据，只能输出定性判断，禁止伪造精确数字。",
                "若输出估值区间，必须同时说明区间来自哪组数据、哪一个工具结果或哪段上游结构化输入；不能只给区间而不交代证据链。",
            ])

        content = TemplateContent(
            system_prompt=(
                f"你正在 TradingAgents-CN 中运行。TradingAgents-CN 是一个面向投研、交易分析与 Agent 编排场景的多智能体金融分析系统，系统内已有行情、财务、新闻、研究、筛选、复盘、报告、工作流与工具注册等能力模块。"
                f"\n你的角色是{spec.name}。你不是通用聊天助手，而是这个系统里的专业金融分析 Agent，负责在当前规格定义的职责范围内，为用户完成可落地、可复核的分析交付。"
                f"\n你的能力边界来自四类信息：输入上下文、当前版本绑定的可用工具、上游传入的结构化数据/中间结果、以及当前任务的明确约束。凡是不在这四类信息里的能力、数据和系统状态，你都不能自行假设为已知。"
                f"\n你理解系统现状的方式，不是凭空脑补，而是优先依据当前任务输入、可用工具列表、上游上下文、显式约束以及工具调用返回结果来判断：现在系统已经提供了什么、还缺什么、这次任务能做到哪里。"
                f"\n你必须体现该角色对应的金融行业专业判断，但所有事实、数字、结论都必须建立在输入信息、可追溯数据和工具结果之上；不得把本应由数据或工具支撑的内容改成主观臆测。"
                f"\nrequired_tools 表示当前版本允许且优先考虑的候选工具集。它不是要求你把所有工具都调用一遍，而是要求你根据任务子问题选择最少且足够的工具；但凡涉及估值区间、目标价、评分、排序、权重等精确数值，你必须调用对应工具或引用上游已提供的可追溯数据，否则不得输出该精确数字。"
                f"\n你必须坚持角色边界，不扩展到未授权的交易建议或其他职责；如果当前信息或能力不足，就明确说明依据不足和降级边界。"
                f"\n{GLOBAL_NO_TRADING_ADVICE_CONSTRAINT}"
                f"\n当前版本绑定工具来自 Agent 工坊第二步缺口分析与第三步版本构建结果；若某能力未被绑定或未在上游结果中提供，不得自行假设可用。"
            ),
            user_prompt="请先识别本次任务所在的业务场景、你的角色职责、当前可用能力和已知系统现状，再结合输入标的、业务目标、上下文数据与可用工具，完成一次面向真实业务交付的分析。",
            tool_guidance=tool_guidance,
            analysis_requirements=(
                f"主要目标：{spec.primary_goal}\n\n"
                f"业务交付：\n{output_fields or '- 待补充'}\n\n"
                f"职责范围：\n{responsibilities or '- 待补充'}\n\n"
                f"成功标准：\n{success_criteria or '- 待补充'}\n\n"
                f"非目标：\n{non_goals or '- 无'}"
            ),
            output_format=output_format,
            constraints="\n".join(self._dedupe([
                constraints or "- 不得伪造数据\n- 必须显式说明关键假设和不确定性来源",
                "- 第三步生成版本时，必须继承第二步缺口分析已确认的工具绑定，不得重新假设一套新的可用工具集。",
                "- required_tools 是允许且优先考虑的候选工具集，按任务需要选择性调用；不得为了凑工具调用记录而机械调用全部工具。",
                "- 若输出估值区间、目标价、评分、排序、权重等精确数值，必须给出可追溯的数据依据、来源标签以及对应工具结果；没有依据时禁止输出精确数字。",
                f"- {GLOBAL_NO_TRADING_ADVICE_CONSTRAINT}",
                *((["- 第二步仍标记为缺失的能力：" + "；".join(missing_capabilities)] if missing_capabilities else [])),
            ])),
        )
        self._log_generated_result(
            "runtime_prompt_template_content",
            {
                "version_id": version_id,
                "spec_id": spec.spec_id,
                "required_tools": required_tools,
                "template_content": content.model_dump(mode="json"),
            },
            context={
                "version_id": version_id,
                "spec_id": spec.spec_id,
                "spec_name": spec.name,
            },
        )

        template = await prompt_service.create_template(
            PromptTemplateCreate(
                agent_type="custom_agent",
                agent_name=version_id,
                template_name=f"{spec.name} v{version_id.split('_v')[-1]} 草案",
                content=content,
                remark=f"Agent 工坊自动生成的版本草案模板，来源会话 {spec.latest_session_id or ''}",
                status="draft",
            )
        )

        if template is None:
            logger.warning("[AgentWorkshop] Prompt 草案创建失败，返回内联引用")
            return {
                "template_id": None,
                "template_name": f"{spec.name} 草案模板",
                "status": "draft",
            }

        result = {
            "template_id": str(template.id),
            "template_name": template.template_name,
            "status": template.status,
        }
        self._log_generated_result(
            "runtime_prompt_template_ref",
            result,
            context={
                "version_id": version_id,
                "spec_id": spec.spec_id,
                "spec_name": spec.name,
            },
        )
        return result

    async def _ensure_runtime_agent_config(self, version: AgentVersion, spec: AgentSpec) -> None:
        output_names = self._list_io_field_names(spec.outputs)
        output_field = version.agent_metadata.get("output_field") or (output_names[0] if output_names else "analysis_result")
        category = version.agent_metadata.get("category")
        if hasattr(category, "value"):
            category = category.value

        await self._db.agent_configs.update_one(
            {"agent_id": version.version_id},
            {
                "$set": {
                    "agent_id": version.version_id,
                    "name": version.agent_metadata.get("name") or spec.name,
                    "description": version.agent_metadata.get("description") or spec.primary_goal or spec.name,
                    "category": category or "analyst",
                    "version": version.agent_metadata.get("version") or f"0.{version.version}.0",
                    "enabled": True,
                    "config": {
                        "max_iterations": int(version.agent_metadata.get("max_tool_calls") or 4),
                        "timeout": 180,
                        "temperature": 0.2,
                    },
                    "prompt_template_type": "universal",
                    "prompt_template_name": version.version_id,
                    "default_tools": version.required_tools,
                    "required_tools": version.required_tools,
                    "output_field": output_field,
                    "metadata": {
                        "source": "agent_workshop",
                        "spec_id": version.spec_id,
                        "version_id": version.version_id,
                        "template_id": version.prompt_template_ref.get("template_id"),
                        "execution_plan": version.execution_plan.model_dump(mode="json") if version.execution_plan else {},
                    },
                    "updated_at": now_tz(),
                },
                "$setOnInsert": {
                    "created_at": now_tz(),
                },
            },
            upsert=True,
        )

    def _build_agent_metadata(self, version_id: str, spec: AgentSpec, required_tools: List[str]) -> Dict[str, Any]:
        category = AgentCategory.ANALYST if spec.domain == "stock_analysis" else AgentCategory.RESEARCHER
        inputs = [
            AgentInput(
                name=self._get_io_field_name(input_item, "user_request"),
                type=self._get_io_field_type(input_item),
                description=self._get_io_field_label(input_item) or self._get_io_field_name(input_item, "user_request"),
            )
            for input_item in (spec.inputs or ["user_request"])
        ]
        outputs = [
            AgentOutput(
                name=self._get_io_field_name(output_item, "summary"),
                type=self._get_io_field_type(output_item),
                description=self._get_io_field_label(output_item) or self._get_io_field_name(output_item, "summary"),
            )
            for output_item in (spec.outputs or ["summary"])
        ]
        output_names = self._list_io_field_names(spec.outputs)
        metadata = AgentMetadata(
            id=version_id,
            name=spec.name,
            description=spec.primary_goal or spec.name,
            category=category,
            version=f"0.{version_id.split('_v')[-1]}.0",
            maintenance_status=AgentMaintenanceStatus.MAINTAINED,
            inputs=inputs,
            outputs=outputs,
            tools=required_tools,
            default_tools=required_tools,
            max_tool_calls=4,
            license_tier=LicenseTier.PRO,
            tags=self._dedupe([spec.domain, *spec.preferred_methods, *spec.target_users]),
            icon="🧪",
            color="#0f8a7d",
            requires_tools=bool(required_tools),
            output_field=(output_names[0] if output_names else "analysis_result"),
            report_label=f"【{spec.name}】",
            node_name=spec.name,
            execution_order=50,
        )
        return metadata.model_dump(mode="json")

    def _build_execution_validation_plan(
        self,
        spec: AgentSpec,
        required_tools: List[str],
        output_schema: Dict[str, Any],
        gap_report: Optional[AgentWorkshopGapAnalysis] = None,
        tooling_plan: Optional[Dict[str, Any]] = None,
    ) -> AgentExecutionValidationPlan:
        sample_input = self._build_execution_sample_input(spec)
        output_fields = self._list_io_field_labels(spec.outputs) or list((output_schema.get("properties") or {}).keys())
        top_tools = self._dedupe(required_tools)[:4]
        evidence_tools = top_tools[:2]
        capability_gaps = self._dedupe([
            *((gap_report.blocking_gaps if gap_report else []) or []),
            *(((tooling_plan or {}).get("missing_capabilities") or []) if isinstance(tooling_plan, dict) else []),
        ])

        steps = [
            AgentExecutionPlanStep(
                step_id="understand-task",
                title="确认任务与交付边界",
                objective="根据规格确认本次运行必须覆盖的输出、边界和非目标。",
                suggested_tools=[],
                expected_evidence=self._dedupe([
                    f"至少覆盖这些输出：{'；'.join(output_fields[:4])}" if output_fields else "明确本次输出字段",
                    *( [f"遵守这些关键约束：{'；'.join(spec.constraints[:3])}"] if spec.constraints else [] ),
                ]),
                failure_signals=[
                    "输出只是在泛泛描述职责，没有回应这次具体任务。",
                    "回答越过了规格中的 non_goals 或 constraints。",
                ],
            ),
            AgentExecutionPlanStep(
                step_id="collect-evidence",
                title="收集核心证据",
                objective="优先通过当前版本绑定的工具拿到支撑结论的核心事实，而不是先写结论。",
                suggested_tools=top_tools,
                expected_evidence=self._dedupe([
                    "至少出现 1 次成功的绑定工具调用。" if top_tools else "若当前版本没有绑定工具，应明确说明这次只能做约束内的降级输出。",
                    *( [f"优先复用这些工具：{'、'.join(top_tools)}"] if top_tools else [] ),
                ]),
                failure_signals=[
                    "最终报告出现了关键结论，但 tool_trace 中没有对应事实获取过程。",
                    "把 required_tools 当成装饰信息，实际没有用于证据收集。",
                ],
            ),
            AgentExecutionPlanStep(
                step_id="deliver-output",
                title="生成可验证交付",
                objective="基于已获取证据输出结果，并对关键数字、结论和降级边界做说明。",
                suggested_tools=evidence_tools,
                expected_evidence=self._dedupe([
                    *( [f"输出字段可在结果中找到：{'；'.join(output_fields[:4])}"] if output_fields else [] ),
                    "若输出精确数值、区间、排序或评分，必须能在工具结果或上游结构化输入中追溯。",
                ]),
                failure_signals=[
                    "出现精确数字或区间，但没有对应来源、参数或工具证据。",
                    "明明数据不足，却仍然输出了完整确定性结论。",
                ],
            ),
        ]

        acceptance_checks = self._dedupe([
            *( [f"结果中应覆盖输出字段：{label}" for label in output_fields[:6]] ),
            *( [f"成功标准：{item}" for item in spec.success_criteria[:4]] ),
            *( ["tool_trace 中至少出现 1 个来自 required_tools 的成功调用。"] if required_tools else [] ),
            *( ["若输出估值区间、目标价、评分、排序、权重等精确数值，必须具备工具或结构化数据依据。"] if self._get_numeric_traceability_policy(spec)["enabled"] else [] ),
        ])

        fallback_rules = self._dedupe([
            "如果当前绑定工具不足以支撑精确结论，应降级为定性判断并说明原因。",
            "如果核心字段缺失，不要伪造数字，应直接说明缺失维度。",
            *( [f"当前仍存在未补齐能力：{'；'.join(capability_gaps[:4])}"] if capability_gaps else [] ),
        ])

        rationale_parts = [
            "创建阶段同步生成执行验证计划，目的是把版本从“规格草案”推进到“可运行交付单元”。",
            "调试和评估应优先验证是否真的调用到了所需工具、是否真的覆盖了目标输出，而不是只看 Prompt 是否写得完整。",
        ]
        if required_tools:
            rationale_parts.append(f"当前版本绑定的核心工具有：{'、'.join(top_tools)}。")
        if capability_gaps:
            rationale_parts.append(f"当前仍需关注的缺口有：{'；'.join(capability_gaps[:4])}。")

        return AgentExecutionValidationPlan(
            mode="tool-driven",
            validation_status="not-run",
            rationale="\n".join(rationale_parts),
            sample_input=sample_input,
            execution_steps=steps,
            acceptance_checks=acceptance_checks,
            fallback_rules=fallback_rules,
        )

    def _build_execution_sample_input(self, spec: AgentSpec) -> Dict[str, Any]:
        symbol = "600519"
        domain_text = " ".join([
            spec.domain or "",
            spec.primary_goal or "",
            " ".join(spec.preferred_methods or []),
            " ".join(spec.responsibilities or []),
        ]).lower()
        if any(keyword in domain_text for keyword in ["银行", "pb", "roe", "金融"]):
            symbol = "600036"
        elif any(keyword in domain_text for keyword in ["新能源", "成长", "peg"]):
            symbol = "300750"
        elif spec.sample_symbols:
            symbol = str(spec.sample_symbols[0]).strip() or symbol

        task_description = spec.primary_goal or spec.name
        if spec.outputs:
            task_description = f"{task_description}。请至少覆盖这些输出：{'、'.join(self._list_io_field_labels(spec.outputs)[:4])}"

        return {
            "symbol": symbol,
            "market_type": "A股",
            "analysis_date": now_tz().strftime("%Y-%m-%d"),
            "task_description": task_description,
        }

    def _build_sample_sets_for_spec(self, spec: AgentSpec) -> List[AgentBenchmarkSampleSet]:
        if self._is_valuation_spec(spec):
            return [self._build_valuation_sample_set(spec)]

        return [
            AgentBenchmarkSampleSet(
                sample_set_id=f"{spec.spec_id}_generic_benchmark",
                spec_id=spec.spec_id,
                name=f"{spec.name} 通用基准样本",
                domain=spec.domain,
                description="用于验证角色边界、输出结构和解释性是否达标。",
                cases=[
                    AgentBenchmarkCase(
                        case_id="generic_case_1",
                        title="基础能力验证",
                        input_payload={"user_request": spec.primary_goal or spec.name},
                        expected_outputs=self._list_io_field_names(spec.outputs)[:4],
                        required_keywords=spec.preferred_methods[:2],
                        forbidden_keywords=spec.non_goals[:2],
                    )
                ],
            )
        ]

    def _build_valuation_sample_set(self, spec: AgentSpec) -> AgentBenchmarkSampleSet:
        symbols = spec.sample_symbols or ["贵州茅台", "宁德时代", "中国移动"]
        return AgentBenchmarkSampleSet(
            sample_set_id=f"{spec.spec_id}_valuation_benchmark",
            spec_id=spec.spec_id,
            name=f"{spec.name} 基准样本集",
            domain=spec.domain,
            description="覆盖成熟蓝筹、成长股和高股息资产三类估值场景。",
            cases=[
                AgentBenchmarkCase(
                    case_id="valuation_case_bluechip",
                    title="成熟蓝筹估值",
                    input_payload={"stock_symbol": symbols[0], "market_type": "A股", "scenario": "成熟消费龙头"},
                    expected_outputs=["valuation_summary", "valuation_methods", "assumptions", "fair_value_range", "invalid_conditions"],
                    required_keywords=["估值区间", "假设", "失效条件", "护城河"],
                    forbidden_keywords=["立即买入", "梭哈"],
                    expected_methods=["DCF", "PE"],
                ),
                AgentBenchmarkCase(
                    case_id="valuation_case_growth",
                    title="成长股估值",
                    input_payload={"stock_symbol": symbols[min(1, len(symbols) - 1)], "market_type": "A股", "scenario": "高成长制造业"},
                    expected_outputs=["valuation_summary", "valuation_methods", "assumptions", "risk_adjustments", "sensitivity_analysis"],
                    required_keywords=["敏感性分析", "增长假设", "折现率"],
                    forbidden_keywords=["稳赚", "确定上涨"],
                    expected_methods=["DCF", "PS"],
                ),
                AgentBenchmarkCase(
                    case_id="valuation_case_dividend",
                    title="高股息资产估值",
                    input_payload={"stock_symbol": symbols[min(2, len(symbols) - 1)], "market_type": "A股", "scenario": "高股息通信运营商"},
                    expected_outputs=["valuation_summary", "valuation_methods", "assumptions", "fair_value_range"],
                    required_keywords=["股息", "资本开支", "分红"],
                    forbidden_keywords=["短线买点", "追涨"],
                    expected_methods=["股息折现", "PE"],
                ),
            ],
        )

    def _resolve_sample_set(self, spec: AgentSpec, sample_set_id: Optional[str]) -> AgentBenchmarkSampleSet:
        sample_sets = self._build_sample_sets_for_spec(spec)
        if sample_set_id:
            for item in sample_sets:
                if item.sample_set_id == sample_set_id:
                    return item
        return sample_sets[0]

    def _evaluate_benchmark_samples(
        self,
        version: AgentVersion,
        spec: AgentSpec,
        sample_set: AgentBenchmarkSampleSet,
        benchmark_outputs: List[Dict[str, Any]],
        user_feedback: str = "",
    ) -> tuple[Dict[str, float], List[str], List[str], Dict[str, Any]]:
        output_map = {
            item.get("case_id"): item
            for item in benchmark_outputs
            if item.get("case_id")
        }
        case_results: List[Dict[str, Any]] = []
        coverage_scores: List[float] = []
        quality_scores: List[float] = []
        constraint_scores: List[float] = []
        issues: List[str] = []

        for case in sample_set.cases:
            provided = output_map.get(case.case_id, {})
            output_text = self._normalize_output_text(provided.get("output_text"), provided.get("output_payload"))
            has_runtime_output = bool(output_text.strip())

            if has_runtime_output:
                output_coverage_detail = self._analyze_expected_outputs_runtime(
                    case.expected_outputs or self._list_io_field_names(spec.outputs),
                    provided.get("output_payload"),
                    output_text,
                )
            else:
                schema_props = set((version.output_schema.get("properties") or {}).keys())
                expected_outputs = case.expected_outputs or self._list_io_field_names(spec.outputs)
                matched_outputs = [item for item in expected_outputs if item in schema_props]
                output_coverage_detail = {
                    "matched": matched_outputs,
                    "missing": [item for item in expected_outputs if item not in matched_outputs],
                    "score": round(len(matched_outputs) / len(expected_outputs), 2) if expected_outputs else 0.6,
                    "notes": ["当前未提供实际输出，字段覆盖度按版本草案的 output schema 估算。"],
                }

            keyword_detail = self._analyze_keywords(case.required_keywords, output_text, has_runtime_output)
            method_detail = self._analyze_keywords(case.expected_methods, output_text, has_runtime_output)
            forbidden_detail = self._analyze_forbidden_keywords(case.forbidden_keywords, output_text, has_runtime_output)

            output_coverage = self._score_expected_outputs(case, provided.get("output_payload"), output_text, spec, version, has_runtime_output)
            keyword_quality = self._score_keywords(case.required_keywords, output_text, has_runtime_output)
            method_quality = self._score_keywords(case.expected_methods, output_text, has_runtime_output)
            forbidden_penalty = self._score_forbidden_keywords(case.forbidden_keywords, output_text, has_runtime_output)

            quality_score = round((keyword_quality + method_quality) / 2, 2)
            constraint_score = round(max(0.0, 1.0 - forbidden_penalty), 2)

            coverage_scores.append(output_coverage)
            quality_scores.append(quality_score)
            constraint_scores.append(constraint_score)

            if not has_runtime_output:
                issues.append(f"样本 {case.title} 尚未提供实际输出，当前只做草案覆盖度评估。")
            elif output_coverage < 0.7:
                issues.append(f"样本 {case.title} 的核心输出字段覆盖不足。")
            elif quality_score < 0.65:
                issues.append(f"样本 {case.title} 对估值方法、假设或证据的披露不足。")
            if forbidden_penalty > 0:
                issues.append(f"样本 {case.title} 出现越界表达或不应出现的结论。")

            case_results.append({
                "case_id": case.case_id,
                "title": case.title,
                "input_payload": case.input_payload,
                "has_runtime_output": has_runtime_output,
                "output_coverage": output_coverage,
                "quality_score": quality_score,
                "constraint_score": constraint_score,
                "output_excerpt": self._truncate_text(output_text, 1200),
                "expected_outputs": case.expected_outputs,
                "expected_methods": case.expected_methods,
                "required_keywords": case.required_keywords,
                "forbidden_keywords": case.forbidden_keywords,
                "output_coverage_detail": output_coverage_detail,
                "keyword_detail": keyword_detail,
                "method_detail": method_detail,
                "forbidden_detail": forbidden_detail,
                "notes": self._dedupe([
                    *(output_coverage_detail.get("notes") or []),
                    *(forbidden_detail.get("notes") or []),
                    *( ["当前样本尚未粘贴真实输出，只能按版本草案做静态覆盖评估。"] if not has_runtime_output else [] ),
                ]),
            })

        scores = {
            "benchmark_case_coverage": round(sum(coverage_scores) / max(1, len(coverage_scores)), 2),
            "benchmark_output_quality": round(sum(quality_scores) / max(1, len(quality_scores)), 2),
            "benchmark_constraint_control": round(sum(constraint_scores) / max(1, len(constraint_scores)), 2),
        }
        recommendations = self._dedupe([
            "优先补充每个 benchmark case 的实际运行输出，再做一次基准评估。",
            "针对得分最低的样本补强 Prompt 对方法选择和关键假设披露的硬约束。",
            "把 benchmark 中失败的 case 转成后续版本回归样本。",
            *( [f"额外反馈：{user_feedback.strip()}"] if user_feedback.strip() else [] ),
        ])
        details = {
            "mode": "benchmark",
            "sample_set": sample_set.model_dump(mode="json"),
            "case_results": case_results,
        }
        return scores, self._dedupe(issues), recommendations, details

    async def _evaluate_runtime_result(
        self,
        version: AgentVersion,
        spec: AgentSpec,
        runtime_result: Dict[str, Any],
        user_feedback: str = "",
    ) -> tuple[Dict[str, float], List[str], List[str], Dict[str, Any]]:
        rule_scores, rule_issues, rule_recommendations, rule_details = self._evaluate_runtime_result_rules(
            version,
            spec,
            runtime_result,
            user_feedback=user_feedback,
        )

        llm_review: Dict[str, Any] = {}
        llm_review_error = ""
        try:
            llm_review = await self._judge_runtime_result_with_llm(
                version,
                spec,
                runtime_result,
                user_feedback=user_feedback,
                rule_details=rule_details,
            )
        except Exception as exc:
            llm_review_error = str(exc)
            logger.warning("[AgentWorkshop] LLM 结果评估失败，直接暴露错误: %s", exc, exc_info=True)

        if not llm_review:
            failed_details = {
                "mode": "production-review",
                "evaluation_engine": "llm_failed",
                "judge_model": {
                    **self._llm_client_meta,
                    "fallback_used": False,
                },
                "runtime_result": runtime_result,
                "parsed_output_excerpt": rule_details.get("parsed_output_excerpt", ""),
                "valuation_traceability": rule_details.get("valuation_traceability", {}),
                "llm_review_error": llm_review_error or "LLM 评审未返回有效结果。",
                "rule_review": {
                    "scores": rule_scores,
                    "score_breakdown": rule_details.get("score_breakdown", {}),
                    "issues": rule_issues,
                    "recommendations": rule_recommendations,
                },
            }
            return {}, [f"LLM 结果评估失败：{failed_details['llm_review_error']}"], [
                "先查看 runtime_review 的 system_prompt、user_prompt 和 raw_response，确认评审提示词或输出约束哪里失效。",
                "修复前不要把这次 production-review 当成有效评估结论；规则检查只保留在下方作为辅助证据。",
            ], failed_details

        llm_scores = llm_review.get("scores") or {}
        scores = {
            "runtime_goal_alignment": round(self._pick_float(llm_scores.get("runtime_goal_alignment"), rule_scores.get("runtime_goal_alignment", 0.0)), 2),
            "runtime_output_quality": round(self._pick_float(llm_scores.get("runtime_output_quality"), rule_scores.get("runtime_output_coverage", 0.0)), 2),
            "runtime_reasoning_quality": round(self._pick_float(llm_scores.get("runtime_reasoning_quality"), rule_scores.get("runtime_explainability", 0.0)), 2),
            "runtime_tool_usage": round(self._pick_float(llm_scores.get("runtime_tool_usage"), rule_scores.get("runtime_explainability", 0.0)), 2),
            "runtime_prompt_quality": round(self._pick_float(llm_scores.get("runtime_prompt_quality"), 0.0), 2),
            "runtime_constraint_control": round(self._pick_float(llm_scores.get("runtime_constraint_control"), rule_scores.get("runtime_constraint_control", 0.0)), 2),
        }

        issues = self._dedupe([
            *(llm_review.get("issues") or []),
            *(rule_issues if llm_review_error else []),
        ])
        recommendations = self._dedupe([
            *(llm_review.get("recommendations") or []),
            *rule_recommendations,
        ])

        details = {
            "mode": "production-review",
            "evaluation_engine": "llm-judge-primary",
            "judge_model": {
                **self._llm_client_meta,
                "fallback_used": False,
            },
            "runtime_result": runtime_result,
            "parsed_output_excerpt": rule_details.get("parsed_output_excerpt", ""),
            "valuation_traceability": rule_details.get("valuation_traceability", {}),
            "llm_review": llm_review,
            "rule_review": {
                "scores": rule_scores,
                "score_breakdown": rule_details.get("score_breakdown", {}),
                "issues": rule_issues,
            },
        }
        return scores, issues, recommendations, details

    def _evaluate_runtime_result_rules(
        self,
        version: AgentVersion,
        spec: AgentSpec,
        runtime_result: Dict[str, Any],
        user_feedback: str = "",
    ) -> tuple[Dict[str, float], List[str], List[str], Dict[str, Any]]:
        output_text = self._normalize_output_text(runtime_result.get("output_text"), runtime_result.get("output_payload"))
        payload = runtime_result.get("output_payload") if isinstance(runtime_result.get("output_payload"), dict) else {}
        has_runtime_output = bool(output_text.strip())
        output_names = self._list_io_field_names(spec.outputs)
        output_evidence = self._analyze_expected_outputs_runtime(output_names, payload, output_text)
        explain_evidence = self._analyze_keywords(["假设", "风险", "失效", "不确定性"], output_text, has_runtime_output)
        method_evidence = self._analyze_keywords(spec.preferred_methods[:3], output_text, has_runtime_output) if spec.preferred_methods else {
            "matched": [],
            "missing": [],
            "score": 0.7,
        }
        forbidden_evidence = self._analyze_forbidden_keywords(spec.non_goals, output_text, has_runtime_output)
        goal_evidence = self._analyze_goal_alignment(runtime_result.get("user_goal", spec.primary_goal), output_text, payload)
        valuation_guardrail = self._analyze_valuation_numeric_guardrail(spec, runtime_result, output_text)
        valuation_traceability = self._build_valuation_traceability(spec, runtime_result, output_text)
        execution_plan_review = self._evaluate_execution_plan_review(
            version,
            spec,
            runtime_result,
            output_text,
            output_evidence,
            goal_evidence,
            valuation_guardrail,
        )

        output_coverage = output_evidence["score"]
        explainability = explain_evidence["score"]
        method_quality = method_evidence["score"]
        forbidden_penalty = max(forbidden_evidence["score"], valuation_guardrail["penalty"])
        goal_alignment = goal_evidence["score"]

        scores = {
            "runtime_goal_alignment": round(goal_alignment, 2),
            "runtime_output_coverage": round(output_coverage, 2),
            "runtime_explainability": round((explainability + method_quality) / 2, 2),
            "runtime_execution_readiness": round(execution_plan_review["score"], 2),
            "runtime_constraint_control": round(max(0.0, 1.0 - forbidden_penalty), 2),
        }
        issues: List[str] = []
        if not output_text.strip() and not payload:
            issues.append("未提供运行结果内容，无法完成运行结果评估。")
        if scores["runtime_output_coverage"] < 0.7:
            issues.append("运行结果没有覆盖足够的核心输出字段。")
        if scores["runtime_explainability"] < 0.7:
            issues.append("运行结果对关键假设、方法依据或失效条件说明不足。")
        if scores["runtime_constraint_control"] < 0.8:
            issues.append("运行结果出现了越界表达，和规格中的非目标不一致。")
        if valuation_guardrail["violation"]:
            issues.append("数值类结果违反可追溯硬约束：输出了精确数字或区间，但没有提供可追溯的数据源或工具计算依据。")
            issues.append("当前更核心的问题不是文案表达，而是缺少可复核的数据链路或直接计算工具，导致 Agent 只能生成看似合理但不可复核的数字。")
        issues.extend(execution_plan_review["issues"])
        if user_feedback.strip():
            issues.append(f"用户反馈中提到的问题待处理：{user_feedback.strip()}")

        recommendations = self._dedupe([
            "把当前运行结果中缺失的输出字段补进 Prompt 和输出 Schema。",
            "为真实任务结果增加结构化字段，避免只返回长文本。",
            "把这次 production review 中暴露的问题加入下一轮真实结果验收清单。",
            *( ["对数值类结果增加原始数据、工具计算结果、输入参数和来源标签；没有足够依据时不要输出精确数字。"] if valuation_guardrail["violation"] else [] ),
            *( ["下一轮工坊应优先补数据链路或直接计算工具，而不是继续微调 Prompt 让模型自己编数字。"] if valuation_guardrail["violation"] else [] ),
            *execution_plan_review["recommendations"],
        ])
        details = {
            "mode": "production-review",
            "runtime_result": runtime_result,
            "parsed_output_excerpt": output_text[:1200],
            "valuation_traceability": valuation_traceability,
            "execution_plan_review": execution_plan_review,
            "score_breakdown": {
                "runtime_goal_alignment": {
                    "matched": goal_evidence["matched"],
                    "missing": goal_evidence["missing"],
                    "notes": goal_evidence["notes"],
                },
                "runtime_output_coverage": {
                    "matched": output_evidence["matched"],
                    "missing": output_evidence["missing"],
                    "notes": [f"要求输出字段：{', '.join(output_names) if output_names else '未定义'}"],
                },
                "runtime_explainability": {
                    "matched": self._dedupe([*explain_evidence["matched"], *method_evidence["matched"]]),
                    "missing": self._dedupe([*explain_evidence["missing"], *method_evidence["missing"]]),
                    "notes": [
                        "检查是否解释了假设、风险、失效条件，以及规格要求的方法依据。",
                    ],
                },
                "runtime_execution_readiness": {
                    "matched": execution_plan_review["matched"],
                    "missing": execution_plan_review["missing"],
                    "notes": execution_plan_review["notes"],
                },
                "runtime_constraint_control": {
                    "matched": self._dedupe([*forbidden_evidence["matched"], *valuation_guardrail["matched"]]),
                    "missing": self._dedupe([*forbidden_evidence["missing"], *valuation_guardrail["missing"]]),
                    "notes": self._dedupe([*forbidden_evidence["notes"], *valuation_guardrail["notes"]]),
                },
            },
        }
        return scores, issues, recommendations, details

    def _evaluate_execution_plan_review(
        self,
        version: AgentVersion,
        spec: AgentSpec,
        runtime_result: Dict[str, Any],
        output_text: str,
        output_evidence: Dict[str, Any],
        goal_evidence: Dict[str, Any],
        valuation_guardrail: Dict[str, Any],
    ) -> Dict[str, Any]:
        plan = version.execution_plan or AgentExecutionValidationPlan()
        debug_prompt = self._extract_runtime_debug_prompt(runtime_result)
        tool_trace = self._sanitize_tool_trace(debug_prompt.get("tool_trace"))
        successful_tool_names = self._dedupe([
            str(item.get("tool_name") or "").strip()
            for item in tool_trace
            if isinstance(item, dict) and item.get("success") and str(item.get("tool_name") or "").strip()
        ])
        required_tools = self._dedupe([str(item).strip() for item in (version.required_tools or []) if str(item).strip()])
        successful_required_tools = [tool for tool in required_tools if tool in successful_tool_names]
        missing_required_tools = [tool for tool in required_tools if tool not in successful_required_tools]

        runtime_symbol = str(
            runtime_result.get("symbol")
            or runtime_result.get("stock_symbol")
            or runtime_result.get("metadata", {}).get("symbol")
            or ""
        ).strip()
        sample_symbol = str((plan.sample_input or {}).get("symbol") or "").strip()
        sample_symbol_aligned = not sample_symbol or not runtime_symbol or runtime_symbol == sample_symbol

        output_labels = self._list_io_field_labels(spec.outputs)
        matched_outputs = self._dedupe([str(item) for item in (output_evidence.get("matched") or []) if item])
        missing_outputs = self._dedupe([str(item) for item in (output_evidence.get("missing") or []) if item])

        acceptance_results: List[Dict[str, Any]] = []
        for label in output_labels[:6]:
            matched = any(self._match_concept(label, candidate) for candidate in matched_outputs)
            acceptance_results.append({
                "label": f"覆盖输出字段：{label}",
                "passed": matched,
                "detail": "已在结果或结构化输出中识别到。" if matched else "本次运行没有稳定覆盖该字段。",
                "category": "output",
            })

        success_criteria = self._dedupe([str(item).strip() for item in (spec.success_criteria or []) if str(item).strip()])
        for item in success_criteria[:4]:
            matched = self._match_concept(item, output_text) or any(self._match_concept(item, matched_item) for matched_item in goal_evidence.get("matched") or [])
            acceptance_results.append({
                "label": f"满足成功标准：{item}",
                "passed": matched,
                "detail": "输出中存在对应响应。" if matched else "当前输出还看不到这个成功标准的直接证据。",
                "category": "success_criteria",
            })

        if required_tools:
            acceptance_results.append({
                "label": "至少命中一个 required_tools 成功调用",
                "passed": bool(successful_required_tools),
                "detail": (
                    f"已命中：{'、'.join(successful_required_tools[:4])}" if successful_required_tools
                    else "tool_trace 中还没有看到 required_tools 的成功调用。"
                ),
                "category": "tool_usage",
            })

        numeric_policy = self._get_numeric_traceability_policy(spec)
        if numeric_policy["enabled"]:
            acceptance_results.append({
                "label": "精确数字具备可追溯来源",
                "passed": not valuation_guardrail.get("violation"),
                "detail": "本次运行没有触发不可追溯数值问题。" if not valuation_guardrail.get("violation") else "出现了精确数字，但缺少结构化来源或工具证据。",
                "category": "traceability",
            })

        passed_count = sum(1 for item in acceptance_results if item.get("passed"))
        acceptance_score = passed_count / max(1, len(acceptance_results)) if acceptance_results else 0.7
        tool_score = 1.0 if not required_tools else len(successful_required_tools) / len(required_tools)
        sample_input_score = 1.0 if sample_symbol_aligned else 0.4
        score = round((acceptance_score * 0.55) + (tool_score * 0.3) + (sample_input_score * 0.15), 2)

        matched: List[str] = []
        if sample_symbol:
            matched.append(f"默认样本标的：{sample_symbol}") if sample_symbol_aligned else None
        if successful_required_tools:
            matched.append(f"已命中的 required_tools：{'、'.join(successful_required_tools[:4])}")
        if not missing_outputs:
            matched.append("规格要求的核心输出字段已全部覆盖。")
        matched.extend([item["label"] for item in acceptance_results if item.get("passed")][:6])

        missing: List[str] = []
        if sample_symbol and not sample_symbol_aligned:
            missing.append(f"默认样本建议标的为 {sample_symbol}，但本次调试输入是 {runtime_symbol or '空'}")
        if missing_required_tools:
            missing.append(f"未命中的 required_tools：{'、'.join(missing_required_tools[:4])}")
        if missing_outputs:
            missing.append(f"未覆盖输出字段：{'、'.join(missing_outputs[:4])}")
        missing.extend([item["label"] for item in acceptance_results if not item.get("passed")][:6])

        issues: List[str] = []
        if score < 0.75:
            issues.append("execution_plan 验收未通过：这次运行还没有达到版本创建时定义的执行验证要求。")
        if missing_required_tools:
            issues.append("这次运行没有真正调用到版本声明的关键工具，当前结果更像 Prompt 演示，不像可复核的执行结果。")
        if missing_outputs:
            issues.append("execution_plan 要求的核心输出字段仍有缺失，说明版本草案和实际运行结果还没对齐。")
        if sample_symbol and not sample_symbol_aligned:
            issues.append("本次调试输入偏离了版本默认样本，当前评估结论不能直接代表 build_version 生成的执行计划是否成立。")

        recommendations = self._dedupe([
            *( ["先按 execution_plan.sample_input 重新跑一次调试，确保版本默认样本能稳定通过。"] if sample_symbol and not sample_symbol_aligned else [] ),
            *( ["把 required_tools 的调用前置到分析主链路，而不是只在 Prompt 里声明。"] if missing_required_tools else [] ),
            *( ["按 execution_plan.acceptance_checks 逐项补齐输出字段，再重新发起结果评估。"] if missing_outputs else [] ),
            *( ["如果当前工具无法支撑精确结论，就按 execution_plan.fallback_rules 降级输出，不要硬给确定性数字。"] if valuation_guardrail.get("violation") else [] ),
        ])

        status = "pass" if score >= 0.8 else "revise" if score >= 0.55 else "fail"
        notes = self._dedupe([
            f"执行计划模式：{plan.mode or 'tool-driven'}",
            f"执行计划状态：{plan.validation_status or 'not-run'}",
            *( [f"计划理由：{plan.rationale.strip()}"] if str(plan.rationale or '').strip() else [] ),
            *( [f"成功工具轨迹：{'、'.join(successful_tool_names[:6])}"] if successful_tool_names else ["当前 debug_prompt 里没有成功的 tool_trace。"] ),
            *( [f"降级规则：{'；'.join((plan.fallback_rules or [])[:3])}"] if plan.fallback_rules else [] ),
        ])

        return {
            "status": status,
            "score": score,
            "sample_input": plan.sample_input,
            "successful_tools": successful_tool_names,
            "successful_required_tools": successful_required_tools,
            "missing_required_tools": missing_required_tools,
            "acceptance_results": acceptance_results,
            "matched": self._dedupe(matched),
            "missing": self._dedupe(missing),
            "issues": self._dedupe(issues),
            "recommendations": recommendations,
            "notes": notes,
        }

    def _analyze_valuation_numeric_guardrail(self, spec: AgentSpec, runtime_result: Dict[str, Any], output_text: str) -> Dict[str, Any]:
        policy = self._get_numeric_traceability_policy(spec)
        if not policy["enabled"]:
            return {"violation": False, "penalty": 0.0, "matched": [], "missing": [], "notes": []}

        range_mentions = self._extract_valuation_range_mentions(output_text)
        if not range_mentions:
            return {
                "violation": False,
                "penalty": 0.0,
                "matched": ["未检测到需要追溯的精确数值或区间，符合当前规格下的数值约束。"],
                "missing": [],
                "notes": [
                    "若规格只要求定性判断或框架解读，不输出精确数值是允许的。",
                    "若后续要输出精确数值或区间，则必须先补齐数据源或工具计算依据。",
                ],
            }

        payload = runtime_result.get("output_payload") if isinstance(runtime_result.get("output_payload"), dict) else {}
        debug_prompt = self._extract_runtime_debug_prompt(runtime_result)
        tool_trace = debug_prompt.get("tool_trace") if isinstance(debug_prompt, dict) else []
        has_structured_calc = any(
            key in payload for key in [
                "valuation_calculations",
                "valuation_sources",
                "valuation_ranges",
                "valuation_table",
                "fair_value_range_by_tool",
            ]
        )
        calc_tool_names = {
            item.get("tool_name")
            for item in tool_trace
            if isinstance(item, dict) and item.get("tool_name")
        }
        used_calc_tools = [
            item.get("tool_name") for item in tool_trace
            if isinstance(item, dict) and item.get("tool_name") in calc_tool_names and item.get("success")
        ]
        traceability_items = self._build_numeric_traceability_items(range_mentions, output_text, used_calc_tools, has_structured_calc)
        unresolved_items = [item for item in traceability_items if item.get("source_type") == "unverified"]
        violation = bool(unresolved_items)

        notes = [
            "数值类结果一旦出现，就必须来自数据源、工具计算或结构化计算结果，不能只由模型根据文本自行给出。",
            *( [f"检测到精确区间: {'；'.join(range_mentions[:4])}"] if range_mentions else [] ),
            *( [f"已识别到可用工具轨迹: {', '.join(used_calc_tools)}"] if used_calc_tools else ["当前未识别到可支撑这些数字的工具轨迹。"] ),
            *( [f"以下数值仍缺少就地可追溯依据: {'；'.join(str(item.get('value')) for item in unresolved_items[:4])}"] if unresolved_items else [] ),
        ]
        if not policy["requires_exact_numeric_outputs"]:
            notes.append("当前规格本身未强制要求精确数值；本次拦截是因为实际输出出现了不可追溯的精确数字。")
        return {
            "violation": violation,
            "penalty": 0.6 if violation else 0.0,
            "matched": (["数值结果具备可追溯的数据或工具依据。"] if range_mentions and not unresolved_items else []),
            "missing": (["精确数值或区间缺少可追溯的数据或工具依据。"] if violation else []),
            "notes": notes,
        }

    def _extract_valuation_range_mentions(self, output_text: str) -> List[str]:
        if not output_text:
            return []
        patterns = [
            re.compile(r"[^\n]{0,24}?(\d+(?:\.\d+)?\s*[-~至]\s*\d+(?:\.\d+)?)(?:\s*(?:元|分|%|倍|分数|评分|名|位))?", re.IGNORECASE),
            re.compile(r"(?:评分|打分|排序|排名|权重|仓位|收益率|回报率|波动率|概率|目标价|价格区间|估值区间|score|rank|rating|weight|price|target|range)[^\n：:]{0,24}?(\d+(?:\.\d+)?)", re.IGNORECASE),
        ]
        matches: List[str] = []
        for pattern in patterns:
            matches.extend(match.group(0).strip() for match in pattern.finditer(output_text))
        filtered: List[str] = []
        for match_text in self._dedupe(matches):
            normalized = match_text.strip()
            if not normalized:
                continue
            if re.fullmatch(r"\**\d{4}-\d{2}(?:-\d{2})?\**", normalized):
                continue
            if re.search(r"分析日期|报告周期|数据期间|最近\d+个交易日", normalized, re.IGNORECASE):
                continue
            filtered.append(normalized)
        return filtered

    def _build_numeric_traceability_items(
        self,
        range_mentions: List[str],
        output_text: str,
        used_tool_names: List[str],
        has_structured_calc: bool,
    ) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        unique_tool_names = self._dedupe([str(name) for name in used_tool_names if name])
        for mention in range_mentions:
            context = self._extract_local_context(output_text, mention, window=120)
            local_has_tool = any(tool_name in context for tool_name in unique_tool_names)
            local_has_source_label = any(keyword in context for keyword in ["来源", "数据源", "计算依据", "输入参数", "工具计算"])
            source_type = "tool_or_data_backed" if has_structured_calc or (local_has_tool and local_has_source_label) else "unverified"
            items.append({
                "label": "数值结果",
                "value": mention,
                "source_type": source_type,
                "judgement": "具备可追溯依据" if source_type == "tool_or_data_backed" else "证据不足",
                "evidence_tools": unique_tool_names if source_type == "tool_or_data_backed" else [],
                "notes": [
                    "检测到结构化数值来源。" if has_structured_calc else (
                        "数值附近同时出现了来源标签和工具名。" if source_type == "tool_or_data_backed" else "数值附近没有发现足够的来源标签或对应工具名。"
                    )
                ],
            })
        return items

    def _extract_local_context(self, text: str, needle: str, window: int = 120) -> str:
        if not text or not needle:
            return ""
        index = text.find(needle)
        if index < 0:
            return ""
        start = max(0, index - window)
        end = min(len(text), index + len(needle) + window)
        return text[start:end]

    def _build_valuation_traceability(self, spec: AgentSpec, runtime_result: Dict[str, Any], output_text: str) -> Dict[str, Any]:
        if not self._get_numeric_traceability_policy(spec)["enabled"]:
            return {"enabled": False, "items": [], "summary": "当前版本未启用数值来源追踪。"}

        debug_prompt = self._extract_runtime_debug_prompt(runtime_result)
        tool_trace = debug_prompt.get("tool_trace") if isinstance(debug_prompt, dict) else []
        used_tool_names = [item.get("tool_name") for item in tool_trace if isinstance(item, dict) and item.get("tool_name")]
        range_mentions = self._extract_valuation_range_mentions(output_text)
        runtime_payload = runtime_result.get("output_payload") if isinstance(runtime_result.get("output_payload"), dict) else {}
        has_structured_calc = any(
            key in runtime_payload for key in [
                "valuation_calculations",
                "valuation_sources",
                "valuation_ranges",
                "valuation_table",
                "fair_value_range_by_tool",
            ]
        )
        items = self._build_numeric_traceability_items(range_mentions, output_text, used_tool_names, has_structured_calc)

        if not items:
            return {
                "enabled": True,
                "items": [],
                "summary": "当前输出里没有识别到需要追踪的精确数值或区间。",
                "used_tools": self._dedupe([str(name) for name in used_tool_names if name]),
            }

        unresolved = [item for item in items if item.get("source_type") == "unverified"]
        return {
            "enabled": True,
            "items": items,
            "summary": "已识别的数值结果均具备可追溯依据。" if not unresolved else "检测到精确数值，但其中部分仍缺少可追溯依据。",
            "used_tools": self._dedupe([str(name) for name in used_tool_names if name]),
        }

    async def _judge_runtime_result_with_llm(
        self,
        version: AgentVersion,
        spec: AgentSpec,
        runtime_result: Dict[str, Any],
        user_feedback: str,
        rule_details: Dict[str, Any],
    ) -> Dict[str, Any]:
        client = await self._ensure_llm_client()
        debug_prompt = self._extract_runtime_debug_prompt(runtime_result)
        tool_trace = debug_prompt.get("tool_trace") if isinstance(debug_prompt, dict) else []
        runtime_payload = runtime_result.get("output_payload") if isinstance(runtime_result.get("output_payload"), dict) else {}
        valuation_traceability = rule_details.get("valuation_traceability", {})
        prompt_metrics = {
            "system_prompt_chars": len(str(debug_prompt.get("system_prompt") or "")),
            "user_prompt_chars": len(str(debug_prompt.get("user_prompt") or "")),
            "output_text_chars": len(str(runtime_result.get("output_text") or "")),
            "tool_trace_items": len(tool_trace or []),
        }

        judge_input = {
            "spec": {
                "name": spec.name,
                "domain": spec.domain,
                "primary_goal": spec.primary_goal,
                "outputs": self._serialize_io_fields(spec.outputs, 8),
                "non_goals": spec.non_goals,
                "constraints": spec.constraints,
                "success_criteria": spec.success_criteria,
            },
            "version": {
                "version_id": version.version_id,
                "required_tools": version.required_tools,
                "default_tools": list((version.agent_metadata or {}).get("default_tools") or []),
                "output_fields": list((version.output_schema.get("properties") or {}).keys()),
                "numeric_traceability_required": bool((version.evaluation_policy or {}).get("numeric_traceability_required")),
                "minimum_score": (version.evaluation_policy or {}).get("minimum_score"),
            },
            "runtime_context": {
                "symbol": runtime_result.get("symbol"),
                "analysis_date": runtime_result.get("analysis_date"),
                "user_goal": runtime_result.get("user_goal") or spec.primary_goal,
                "llm": runtime_result.get("llm") or {},
                "template": runtime_result.get("template") or {},
                "metadata": {
                    "agent_id": (runtime_result.get("metadata") or {}).get("agent_id"),
                    "agent_name": (runtime_result.get("metadata") or {}).get("agent_name"),
                    "maintenance_status": (runtime_result.get("metadata") or {}).get("maintenance_status"),
                },
            },
            "prompt_debug": {
                "prompt_metrics": prompt_metrics,
                "system_prompt_excerpt": self._truncate_text(debug_prompt.get("system_prompt"), 1200),
                "user_prompt_excerpt": self._truncate_text(debug_prompt.get("user_prompt"), 1800),
                "tool_mode": debug_prompt.get("tool_mode"),
                "tool_trace": self._sanitize_tool_trace(tool_trace),
            },
            "runtime_output": {
                "output_text": self._truncate_text(runtime_result.get("output_text"), 4500),
                "output_payload_preview": self._truncate_text(self._json_preview(runtime_payload), 1500),
            },
            "numeric_traceability": {
                "enabled": valuation_traceability.get("enabled"),
                "summary": valuation_traceability.get("summary"),
                "used_tools": valuation_traceability.get("used_tools") or [],
                "items": list((valuation_traceability.get("items") or [])[:6]),
            },
            "user_feedback": user_feedback.strip(),
            "rule_signals": {
                "score_breakdown": rule_details.get("score_breakdown", {}),
                "parsed_output_excerpt": self._truncate_text(rule_details.get("parsed_output_excerpt"), 1200),
            },
        }

        prompt = "\n".join([
            "你正在 TradingAgents-CN 的 Agent 生命周期工坊中做运行评审。请基于给定证据评估这次真实调试运行的交付质量。",
            "只能依据版本信息、运行上下文、prompt 摘要、工具轨迹、运行输出、规则信号和用户反馈做判断；证据中没有的能力、数据来源或工具使用不能当成事实。",
            "请覆盖以下维度：",
            "1. runtime_goal_alignment: 输出是否真正回应用户目标。",
            "2. runtime_output_quality: 输出质量是否完整、专业、可用，而不是只看字段命中。",
            "3. runtime_reasoning_quality: 分析过程是否合理，假设、推导、结论之间是否自洽。",
            "4. runtime_tool_usage: 工具选择与工具调用过程是否合理；如果没有真实工具轨迹，要明确说明证据不足，而不是假装看到了。",
            "5. runtime_prompt_quality: system/user prompt 设计是否清晰、约束是否充分、是否容易把模型引向正确任务。",
            "6. runtime_constraint_control: 是否存在越界、幻觉、与 non_goals/constraints 冲突的问题。",
            "评分范围统一为 0 到 1。规则扫描只是辅助证据；如果某个维度证据不足，要在 notes 里明确写出原因。",
            "只输出 JSON，不要输出 Markdown、解释性前后缀或代码块。JSON 结构必须严格如下：",
            json.dumps({
                "summary": "整体结论，中文",
                "scores": {
                    "runtime_goal_alignment": 0.0,
                    "runtime_output_quality": 0.0,
                    "runtime_reasoning_quality": 0.0,
                    "runtime_tool_usage": 0.0,
                    "runtime_prompt_quality": 0.0,
                    "runtime_constraint_control": 0.0,
                },
                "dimensions": {
                    "runtime_goal_alignment": {"score": 0.0, "judgement": "", "evidence": [], "problems": [], "suggestions": [], "notes": []},
                    "runtime_output_quality": {"score": 0.0, "judgement": "", "evidence": [], "problems": [], "suggestions": [], "notes": []},
                    "runtime_reasoning_quality": {"score": 0.0, "judgement": "", "evidence": [], "problems": [], "suggestions": [], "notes": []},
                    "runtime_tool_usage": {"score": 0.0, "judgement": "", "evidence": [], "problems": [], "suggestions": [], "notes": []},
                    "runtime_prompt_quality": {"score": 0.0, "judgement": "", "evidence": [], "problems": [], "suggestions": [], "notes": []},
                    "runtime_constraint_control": {"score": 0.0, "judgement": "", "evidence": [], "problems": [], "suggestions": [], "notes": []},
                },
                "issues": [],
                "recommendations": [],
            }, ensure_ascii=False, indent=2),
            "评审输入如下：",
            json.dumps(judge_input, ensure_ascii=False, indent=2),
        ])

        system_prompt = "你正在 TradingAgents-CN 的 Agent 生命周期工坊中做运行评审。TradingAgents-CN 是一个面向投研、交易分析、Agent 编排与能力复用的多智能体金融分析系统。你当前角色是严谨的运行评审专家，同时具备金融行业和系统架构评审视角。你的判断依据只能来自版本信息、运行上下文、prompt 调试信息、工具轨迹、运行输出、规则信号和用户反馈，不能把证据中没有出现的系统能力、工具使用或数据来源当成事实。你只输出合法 JSON，并且会明确区分已有证据和证据不足。"
        raw_content = ""
        try:
            self._log_llm_request_prompts(
                "runtime_review_request",
                system_prompt,
                prompt,
                context={
                    "version_id": version.version_id,
                    "spec_id": spec.spec_id,
                    "spec_name": spec.name,
                    "symbol": runtime_result.get("symbol"),
                    "analysis_date": runtime_result.get("analysis_date"),
                },
                extra_metrics={
                    "required_tools": len(version.required_tools or []),
                    "tool_trace_items": len(tool_trace or []),
                    "has_debug_prompt": bool(debug_prompt),
                    "has_runtime_output": bool(str(runtime_result.get("output_text") or "").strip()),
                },
            )
            response = await client.achat([
                Message(role="system", content=system_prompt),
                Message(role="user", content=prompt),
            ])
            raw_content = (response.content or "").strip()
            self._log_llm_exchange(
                "runtime_review",
                system_prompt,
                prompt,
                raw_content,
                context={
                    "version_id": version.version_id,
                    "spec_id": spec.spec_id,
                    "spec_name": spec.name,
                    "symbol": runtime_result.get("symbol"),
                    "analysis_date": runtime_result.get("analysis_date"),
                },
            )
            data = self._load_json_response(raw_content)
            normalized_review = self._normalize_runtime_llm_review(data, raw_content)
        except Exception as exc:
            self._log_llm_failure(
                "runtime_review",
                str(exc),
                raw_response=raw_content,
                context={
                    "version_id": version.version_id,
                    "spec_id": spec.spec_id,
                    "spec_name": spec.name,
                    "symbol": runtime_result.get("symbol"),
                    "analysis_date": runtime_result.get("analysis_date"),
                },
            )
            raise AgentWorkshopLLMStageError("runtime_review", str(exc), raw_response=raw_content) from exc
        self._log_generated_result(
            "runtime_review",
            normalized_review,
            context={
                "version_id": version.version_id,
                "spec_id": spec.spec_id,
                "spec_name": spec.name,
                "symbol": runtime_result.get("symbol"),
                "analysis_date": runtime_result.get("analysis_date"),
            },
        )
        return normalized_review

    def _normalize_runtime_llm_review(self, data: Dict[str, Any], raw_content: str) -> Dict[str, Any]:
        dimension_keys = [
            "runtime_goal_alignment",
            "runtime_output_quality",
            "runtime_reasoning_quality",
            "runtime_tool_usage",
            "runtime_prompt_quality",
            "runtime_constraint_control",
        ]
        source_scores = data.get("scores")
        if not isinstance(source_scores, dict):
            raise ValueError("runtime_review 缺少对象字段 scores")
        source_dimensions = data.get("dimensions")
        if not isinstance(source_dimensions, dict):
            raise ValueError("runtime_review 缺少对象字段 dimensions")

        normalized_dimensions: Dict[str, Any] = {}
        normalized_scores: Dict[str, float] = {}
        all_issues: List[str] = []
        all_recommendations: List[str] = []

        for key in dimension_keys:
            raw_dimension = source_dimensions.get(key)
            if not isinstance(raw_dimension, dict):
                raise ValueError(f"runtime_review 缺少维度对象 {key}")
            score = self._require_score_field(raw_dimension, "score", f"runtime_review.{key}")
            evidence = self._require_list_field(raw_dimension, "evidence", f"runtime_review.{key}")[:6]
            problems = self._require_list_field(raw_dimension, "problems", f"runtime_review.{key}")[:6]
            suggestions = self._require_list_field(raw_dimension, "suggestions", f"runtime_review.{key}")[:6]
            notes = self._require_list_field(raw_dimension, "notes", f"runtime_review.{key}")[:6]
            judgement = self._require_string_field(raw_dimension, "judgement", f"runtime_review.{key}")

            normalized_dimensions[key] = {
                "score": score,
                "judgement": judgement,
                "evidence": evidence,
                "problems": problems,
                "suggestions": suggestions,
                "notes": notes,
            }
            normalized_scores[key] = score
            all_issues.extend(problems)
            all_recommendations.extend(suggestions)

        return {
            "summary": self._require_string_field(data, "summary", "runtime_review"),
            "scores": normalized_scores,
            "dimensions": normalized_dimensions,
            "issues": self._dedupe([*self._require_list_field(data, "issues", "runtime_review"), *all_issues]),
            "recommendations": self._dedupe([*self._require_list_field(data, "recommendations", "runtime_review"), *all_recommendations]),
            "raw_response": raw_content,
        }

    def _extract_runtime_debug_prompt(self, runtime_result: Dict[str, Any]) -> Dict[str, Any]:
        debug_prompt = runtime_result.get("debug_prompt")
        if isinstance(debug_prompt, dict):
            return debug_prompt
        output_payload = runtime_result.get("output_payload")
        if isinstance(output_payload, dict):
            nested = output_payload.get("__debug_prompt__")
            if isinstance(nested, dict):
                return nested
        return {}

    def _sanitize_tool_trace(self, tool_trace: Any) -> List[Dict[str, Any]]:
        if not isinstance(tool_trace, list):
            return []

        sanitized: List[Dict[str, Any]] = []
        for item in tool_trace[:12]:
            if not isinstance(item, dict):
                continue
            sanitized.append({
                "tool_name": item.get("tool_name"),
                "tool_args": item.get("tool_args"),
                "success": bool(item.get("success")),
                "result_length": item.get("result_length"),
                "result_preview": self._truncate_text(item.get("result_preview"), 500),
            })
        return sanitized

    def _json_preview(self, value: Any) -> str:
        try:
            return json.dumps(value, ensure_ascii=False, indent=2, default=str)
        except Exception:
            return str(value)

    def _truncate_text(self, value: Any, limit: int = 2000) -> str:
        text = str(value or "")
        if len(text) <= limit:
            return text
        return f"{text[:limit]}\n...（截断，原始长度 {len(text)}）"

    def _load_json_response(self, raw_content: str) -> Dict[str, Any]:
        content = self._strip_markdown_fence(raw_content)
        try:
            data = json.loads(content)
            if isinstance(data, dict):
                return data
        except Exception:
            pass

        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(0))
            if isinstance(data, dict):
                return data

        raise ValueError("LLM 评审结果不是合法 JSON")

    def _clamp_score(self, value: Any, fallback: float = 0.0) -> float:
        try:
            score = float(value)
        except (TypeError, ValueError):
            return fallback
        if score > 1.0:
            score = score / 10.0 if score <= 10.0 else 1.0
        return round(max(0.0, min(1.0, score)), 2)

    def _normalize_output_text(self, output_text: Any, output_payload: Any) -> str:
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()
        if isinstance(output_payload, dict):
            try:
                return json.dumps(output_payload, ensure_ascii=False)
            except Exception:
                return str(output_payload)
        if output_payload is None:
            return ""
        return str(output_payload)

    def _extract_runtime_report(self, result: Any, output_field: str) -> str:
        if not isinstance(result, dict):
            text = str(result or "").strip()
            return text or "未生成分析报告"

        direct = result.get(output_field)
        if isinstance(direct, str) and direct.strip():
            return direct.strip()

        normalized_target = str(output_field or "").strip().lower()
        for key, value in result.items():
            if str(key).strip().lower() == normalized_target and isinstance(value, str) and value.strip():
                return value.strip()

        candidates = self._collect_report_text_candidates(result)
        if candidates:
            candidates.sort(key=lambda item: item[1], reverse=True)
            return candidates[0][0]

        return "未生成分析报告"

    def _collect_report_text_candidates(self, value: Any) -> List[tuple[str, int]]:
        candidates: List[tuple[str, int]] = []

        def visit(node: Any) -> None:
            if isinstance(node, str):
                text = node.strip()
                if not text:
                    return
                score = len(text)
                if text.startswith("#") or "估值" in text or "分析报告" in text:
                    score += 500
                if len(text) >= 120:
                    candidates.append((text, score))
                return

            if isinstance(node, dict):
                for child in node.values():
                    visit(child)
                return

            if isinstance(node, list):
                for child in node:
                    visit(child)

        visit(value)
        return candidates

    def _score_expected_outputs(
        self,
        case: AgentBenchmarkCase,
        output_payload: Any,
        output_text: str,
        spec: AgentSpec,
        version: AgentVersion,
        has_runtime_output: bool,
    ) -> float:
        if has_runtime_output:
            return self._score_expected_outputs_runtime(case.expected_outputs or self._list_io_field_names(spec.outputs), output_payload, output_text)

        schema_props = set((version.output_schema.get("properties") or {}).keys())
        expected = case.expected_outputs or self._list_io_field_names(spec.outputs)
        if not expected:
            return 0.6
        matched = sum(1 for item in expected if item in schema_props)
        return round(matched / len(expected), 2)

    def _score_expected_outputs_runtime(self, expected_outputs: List[str], output_payload: Any, output_text: str) -> float:
        if not expected_outputs:
            return 0.8
        payload_keys = set(output_payload.keys()) if isinstance(output_payload, dict) else set()
        matched = 0
        for item in expected_outputs:
            if item in payload_keys or self._match_concept(item, output_text) or any(self._match_concept(item, key) for key in payload_keys):
                matched += 1
        return round(matched / len(expected_outputs), 2)

    def _score_keywords(self, keywords: List[str], output_text: str, has_runtime_output: bool) -> float:
        if not keywords:
            return 0.8
        if not has_runtime_output:
            return 0.45
        matched = sum(1 for item in keywords if item and self._match_concept(item, output_text))
        return round(matched / len(keywords), 2)

    def _score_forbidden_keywords(self, keywords: List[str], output_text: str, has_runtime_output: bool) -> float:
        if not keywords or not has_runtime_output:
            return 0.0
        matched = sum(1 for item in keywords if item and self._match_concept(item, output_text))
        return round(matched / len(keywords), 2)

    def _score_goal_alignment(self, user_goal: Any, output_text: str, output_payload: Dict[str, Any]) -> float:
        if not user_goal:
            return 0.75
        goal_text = str(user_goal).lower()
        if isinstance(output_payload, dict) and any(self._match_concept(key, goal_text) for key in output_payload.keys()):
            return 0.9
        goal_units = self._split_goal_units(str(user_goal))
        hit_count = sum(1 for token in goal_units if self._match_concept(token, output_text))
        total = len(goal_units)
        if total == 0:
            return 0.75
        return round(min(1.0, hit_count / total + 0.2), 2)

    def _analyze_expected_outputs_runtime(self, expected_outputs: List[str], output_payload: Any, output_text: str) -> Dict[str, Any]:
        if not expected_outputs:
            return {"matched": [], "missing": [], "score": 0.8}

        payload_keys = set(output_payload.keys()) if isinstance(output_payload, dict) else set()
        matched = [
            item for item in expected_outputs
            if item in payload_keys or self._match_concept(item, output_text) or any(self._match_concept(item, key) for key in payload_keys)
        ]
        missing = [item for item in expected_outputs if item not in matched]
        score = round(len(matched) / len(expected_outputs), 2)
        return {"matched": matched, "missing": missing, "score": score}

    def _analyze_keywords(self, keywords: List[str], output_text: str, has_runtime_output: bool) -> Dict[str, Any]:
        if not keywords:
            return {"matched": [], "missing": [], "score": 0.8}
        if not has_runtime_output:
            return {"matched": [], "missing": keywords, "score": 0.45}

        matched = [item for item in keywords if item and self._match_concept(item, output_text)]
        missing = [item for item in keywords if item and item not in matched]
        return {
            "matched": matched,
            "missing": missing,
            "score": round(len(matched) / len(keywords), 2),
        }

    def _analyze_forbidden_keywords(self, keywords: List[str], output_text: str, has_runtime_output: bool) -> Dict[str, Any]:
        if not keywords or not has_runtime_output:
            return {
                "matched": [],
                "missing": keywords or [],
                "score": 0.0,
                "notes": ["没有发现明显越界内容。"] if has_runtime_output else ["当前没有可检查的输出。"],
            }

        matched = [item for item in keywords if item and self._match_concept(item, output_text)]
        safe_items = [item for item in keywords if item and item not in matched]
        return {
            "matched": matched,
            "missing": safe_items,
            "score": round(len(matched) / len(keywords), 2),
            "notes": [
                "matched 表示命中了非目标或越界词，命中越多扣分越多。",
                f"当前非目标词：{', '.join(keywords)}" if keywords else "",
            ],
        }

    def _analyze_goal_alignment(self, user_goal: Any, output_text: str, output_payload: Dict[str, Any]) -> Dict[str, Any]:
        if not user_goal:
            return {"matched": [], "missing": [], "notes": ["未提供单独的用户目标，使用默认分。"], "score": 0.75}

        goal_text = str(user_goal)
        goal_tokens = self._split_goal_units(goal_text)
        payload_hits = [key for key in output_payload.keys() if self._match_concept(key, goal_text)] if isinstance(output_payload, dict) else []
        text_hits = [token for token in goal_tokens if self._match_concept(token, output_text)]
        matched = self._dedupe([*payload_hits, *text_hits])
        missing = [token for token in goal_tokens if token not in matched]
        if not goal_tokens:
            return {"matched": [], "missing": [], "notes": ["用户目标没有可分析的关键词。"], "score": 0.75}

        score = round(min(1.0, len(text_hits) / len(goal_tokens) + 0.2), 2)
        if payload_hits:
            score = max(score, 0.9)
        return {
            "matched": matched,
            "missing": missing,
            "notes": [f"目标分词：{', '.join(goal_tokens[:12])}"],
            "score": score,
        }

    def _split_goal_units(self, goal_text: str) -> List[str]:
        raw_parts = re.split(r"[，。；;\n]+", goal_text)
        parts = [part.strip() for part in raw_parts if part and part.strip()]
        if not parts:
            return []

        units: List[str] = []
        for part in parts:
            sub_parts = re.split(r"以及|并|并且|辅助|同时|或对比|或", part)
            for sub_part in sub_parts:
                normalized = sub_part.strip(" ：:")
                granular_parts = re.split(r"、", normalized)
                for granular_part in granular_parts:
                    cleaned = granular_part.strip(" ：:、")
                    if cleaned and len(cleaned) >= 2:
                        units.append(cleaned)
        return self._dedupe(units)

    def _match_concept(self, concept: str, text: Any) -> bool:
        if not concept or text is None:
            return False

        text_str = str(text)
        normalized_concept = self._normalize_match_text(concept)
        normalized_text = self._normalize_match_text(text_str)
        if not normalized_concept or not normalized_text:
            return False

        aliases = self._concept_aliases(concept)
        for alias in aliases:
            normalized_alias = self._normalize_match_text(alias)
            if normalized_alias and normalized_alias in normalized_text:
                return True

        if normalized_concept in normalized_text:
            return True

        if len(normalized_concept) >= 6 and SequenceMatcher(None, normalized_concept, normalized_text).ratio() >= 0.72:
            return True

        return False

    def _normalize_match_text(self, value: Any) -> str:
        text = str(value or "").lower()
        text = re.sub(r"（.*?）", "", text)
        text = re.sub(r"\(.*?\)", "", text)
        text = re.sub(r"[^\w\u4e00-\u9fff]+", "", text)
        return text.strip()

    def _concept_aliases(self, concept: str) -> List[str]:
        alias_map = {
            "估值方法选择说明（或三种方法的对比分析）": ["估值方法选择说明", "方法选择逻辑", "方法对比结论", "pb估值法", "pe估值法", "ddm估值法", "dcf估值法"],
            "关键假设说明": ["关键假设", "假设项目", "假设值"],
            "失效条件说明": ["失效条件", "估值失效情形", "预警信号"],
            "市盈率(pe)估值法": ["pe估值法", "市盈率估值法"],
            "市净率(pb)估值法": ["pb估值法", "市净率估值法"],
            "现金流折现(dcf)估值法": ["ddm估值法", "dcf估值法", "股息贴现模型"],
            "不确定性": ["风险提示", "风险", "预警信号"],
        }
        for key, aliases in alias_map.items():
            if concept == key:
                return [concept, *aliases]
        return [concept]

    def _calculate_evaluation_scores(
        self,
        version: AgentVersion,
        spec: AgentSpec,
        user_feedback: str = "",
    ) -> Dict[str, float]:
        role_alignment = 0.9 if spec.primary_goal and len(spec.responsibilities) >= 3 else 0.55
        user_goal_alignment = 0.88 if len(spec.success_criteria) >= 3 else 0.6
        output_completeness = min(1.0, len(version.output_schema.get("properties", {})) / max(1, len(self._list_io_field_names(spec.outputs)) or 1))
        explainability = 0.9 if version.prompt_template_ref.get("template_id") else 0.62

        if not version.required_tools:
            user_goal_alignment = min(user_goal_alignment, 0.65)
        if not spec.non_goals:
            role_alignment = min(role_alignment, 0.68)
        if user_feedback.strip():
            explainability = max(0.55, explainability - 0.05)

        return {
            "role_alignment": round(role_alignment, 2),
            "user_goal_alignment": round(user_goal_alignment, 2),
            "output_completeness": round(output_completeness, 2),
            "explainability": round(explainability, 2),
        }

    def _build_evaluation_issues(
        self,
        version: AgentVersion,
        spec: AgentSpec,
        scores: Dict[str, float],
        user_feedback: str = "",
    ) -> List[str]:
        issues: List[str] = []
        if scores.get("role_alignment", 0) < 0.75:
            issues.append("角色边界仍然偏宽，需要补充非目标和职责约束，避免与现有 Agent 重叠。")
        if scores.get("user_goal_alignment", 0) < 0.75:
            issues.append("用户目标对齐还不够明确，建议进一步收紧成功标准和使用场景。")
        if scores.get("output_completeness", 0) < 0.75:
            issues.append("输出 Schema 还不完整，当前版本没有覆盖所有核心输出字段。")
        if scores.get("explainability", 0) < 0.75:
            issues.append("Prompt 草案对假设披露、推理透明度和失效条件约束还不够强。")
        if spec.domain == "stock_analysis" and not version.required_capabilities:
            issues.append("估值相关可调用能力缺口尚未真正补齐，当前版本仍偏配置草案。")
        if user_feedback.strip():
            issues.append(f"用户补充反馈待吸收：{user_feedback.strip()}")
        return issues

    def _build_evaluation_recommendations(
        self,
        version: AgentVersion,
        spec: AgentSpec,
        scores: Dict[str, float],
        issues: List[str],
    ) -> List[str]:
        recommendations: List[str] = []
        if scores.get("role_alignment", 0) < 0.8:
            recommendations.append("补充更严格的非目标约束，并在 Prompt 中明确禁止越界输出。")
        if scores.get("user_goal_alignment", 0) < 0.8:
            recommendations.append("把成功标准改成可打分条目，并补充 2 到 3 个标准样本。")
        if scores.get("output_completeness", 0) < 0.85:
            recommendations.append("补齐输出 Schema，确保每个核心输出字段都有明确描述和必填约束。")
        if scores.get("explainability", 0) < 0.85:
            recommendations.append("加强 Prompt 中对关键假设、敏感性分析和失效条件的硬约束。")
        if spec.domain == "stock_analysis":
            recommendations.append("把缺口分析中的估值能力草案转成可执行的 Skill 生成任务，并注册为可调用能力。")
        if not version.required_tools:
            recommendations.append("补齐至少一组可运行的数据工具绑定，再进入 testing。")
        return self._dedupe(recommendations)

    def _decide_evaluation(self, overall_score: float, minimum_score: float, issues: List[str]) -> str:
        if overall_score >= minimum_score and len(issues) <= 2:
            return "pass"
        if overall_score < 0.55:
            return "reject"
        return "revise"

    def _build_iteration_description(
        self,
        spec: AgentSpec,
        version: AgentVersion,
        issues: List[str],
        recommendations: List[str],
        feedback: str,
    ) -> str:
        issue_block = "；".join(issues[:4]) if issues else "暂无明确问题"
        recommendation_block = "；".join(recommendations[:4]) if recommendations else "暂无明确建议"
        feedback_text = feedback.strip() or "无额外人工反馈"
        return (
            f"我们正在迭代 {spec.name} 的版本 {version.version_id}。"
            f"上一轮评估识别的问题包括：{issue_block}。"
            f"建议方向包括：{recommendation_block}。"
            f"人工补充反馈：{feedback_text}。"
            f"请基于这些信息继续优化这个 Agent 的角色边界、Prompt、工具与输出设计。"
        )

    def _build_iteration_reminder(self, evaluation: AgentEvaluationReport, feedback: str) -> str:
        issue_block = "\n".join(f"- {item}" for item in evaluation.issues[:5]) or "- 暂无"
        recommendation_block = "\n".join(f"- {item}" for item in evaluation.recommendations[:5]) or "- 暂无"
        extra_feedback = feedback.strip() or "无"
        return (
            "上一轮评估摘要：\n"
            f"- 决策：{evaluation.decision}\n"
            f"- 综合得分：{evaluation.scores.get('overall', 0)}\n"
            "- 主要问题：\n"
            f"{issue_block}\n"
            "- 优化建议：\n"
            f"{recommendation_block}\n"
            f"- 额外反馈：{extra_feedback}"
        )

    def _slugify(self, name: str) -> str:
        ascii_name = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "_", name).strip("_")
        if not ascii_name:
            ascii_name = f"agent_{uuid.uuid4().hex[:8]}"
        return ascii_name.lower()

    def _dedupe(self, items: List[str]) -> List[str]:
        results: List[str] = []
        for item in items:
            normalized = item.strip()
            if normalized and normalized not in results:
                results.append(normalized)
        return results