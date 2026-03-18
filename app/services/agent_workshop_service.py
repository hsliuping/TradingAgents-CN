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
from typing import Any, Dict, List, Optional, Tuple

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.prompt_template import PromptTemplateCreate, TemplateContent
from app.models.agent_workshop import (
    AgentBenchmarkCase,
    AgentBenchmarkSampleSet,
    AgentSpec,
    AgentSpecStatus,
    AgentEvaluationReport,
    AgentVersion,
    AgentVersionStatus,
    AgentWorkshopGapAnalysis,
    AgentWorkshopMessage,
    AgentWorkshopSession,
    AgentWorkshopStage,
)
from app.services.prompt_template_service import PromptTemplateService
from app.utils.timezone import now_tz
from core.agents.config import AgentCategory, AgentInput, AgentMaintenanceStatus, AgentMetadata, AgentOutput, LicenseTier
from core.llm import UnifiedLLMClient, Message
from core.tools import get_tool_registry
from core.tools.config import ToolCategory

logger = logging.getLogger(__name__)

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

    _LLM_TIMEOUT = 180

    def __init__(self, db: AsyncIOMotorDatabase):
        self._db = db
        self._llm_client: Optional[UnifiedLLMClient] = None
        self._llm_client_meta: Dict[str, Any] = {}

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

    def _log_generated_result(self, stage: str, result: Any, context: Optional[Dict[str, Any]] = None) -> None:
        context_text = self._format_log_context(context)
        prefix = f"[AgentWorkshop][{stage}]"
        if context_text:
            prefix = f"{prefix} {context_text}"
        logger.info("%s generated_result:\n%s", prefix, self._serialize_log_payload(result))

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
        required_capabilities = self._select_required_capabilities(session.gap_report, session.tooling_plan)
        output_schema = self._build_output_schema(spec)
        evaluation_policy = self._build_evaluation_policy(spec)
        prompt_template = await self._create_prompt_template(version_id, spec, required_tools)
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
        deleted_spec = await self._db[SPEC_COLLECTION].delete_one({"spec_id": spec_id})

        return {
            "deleted": deleted_spec.deleted_count > 0,
            "spec_id": spec_id,
            "deleted_sessions": deleted_sessions.deleted_count,
            "deleted_versions": deleted_versions.deleted_count,
            "deleted_evaluations": deleted_evaluations.deleted_count if deleted_evaluations is not None else 0,
            "deleted_prompts": deleted_prompts.deleted_count if deleted_prompts is not None else 0,
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
            sample_set = self._resolve_sample_set(spec, sample_set_id)
            scores, issues, recommendations, evaluation_details = self._evaluate_benchmark_samples(
                version,
                spec,
                sample_set,
                benchmark_outputs or [],
                user_feedback=user_feedback,
            )
            sample_set_id = sample_set.sample_set_id
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

        return {
            "version_id": version.version_id,
            "evaluation": report,
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
        market_type = str(stock.get("market_type") or "A股")
        task_description = user_goal or spec.primary_goal or spec.name

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

    async def _collect_capability_snapshot(self) -> Dict[str, Any]:
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

        for tool in builtin_tools:
            item = f"{tool.id} | {tool.name}"
            category = str(tool.category)
            searchable = " ".join([tool.id, tool.name, tool.description, tool.data_source]).lower()
            if category in data_categories and item not in builtin_data_tools:
                builtin_data_tools.append(item)
            if category in analysis_categories and item not in builtin_analysis_tools:
                builtin_analysis_tools.append(item)
            if self._looks_like_valuation_capability(searchable) and item not in valuation_tools:
                valuation_tools.append(item)

        external_data_skills: List[str] = []
        external_analysis_skills: List[str] = []
        valuation_skills: List[str] = []

        for doc in external_skill_docs:
            tool_id = str(doc.get("tool_id") or "")
            display_name = str(doc.get("display_name") or tool_id)
            description = str(doc.get("description") or "")
            category = str(doc.get("category") or "").lower()
            data_source = str(doc.get("data_source") or "")
            item = f"{tool_id} | {display_name}" if tool_id else display_name
            searchable = " ".join([tool_id, display_name, description, category, data_source]).lower()

            if category in {"market", "fundamentals", "news", "social", "china"} and item not in external_data_skills:
                external_data_skills.append(item)
            elif item not in external_analysis_skills:
                external_analysis_skills.append(item)

            if self._looks_like_valuation_capability(searchable) and item not in valuation_skills:
                valuation_skills.append(item)

        return {
            "builtin_data_tools": builtin_data_tools[:12],
            "builtin_analysis_tools": builtin_analysis_tools[:12],
            "external_data_skills": external_data_skills[:12],
            "external_analysis_skills": external_analysis_skills[:12],
            "valuation_tools": valuation_tools[:8],
            "valuation_skills": valuation_skills[:8],
            "totals": {
                "builtin_tools": len(builtin_tools),
                "external_skills": len(external_skill_docs),
            },
        }

    def _looks_like_valuation_capability(self, searchable: str) -> bool:
        keywords = [
            "valuation", "估值", "估价", "定价", "dcf", "pe", "pb", "ps", "ev/ebitda", "可比公司", "peer comparison", "敏感性分析",
        ]
        return any(keyword in searchable for keyword in keywords)

    def _is_valuation_spec(self, spec: AgentSpec) -> bool:
        searchable = " ".join([
            spec.name,
            spec.spec_id,
            spec.primary_goal,
            " ".join(spec.outputs),
            " ".join(spec.preferred_methods),
            " ".join(spec.success_criteria),
        ]).lower()
        return spec.domain == "stock_analysis" and self._looks_like_valuation_capability(searchable)

    def _build_valuation_requirement_text(self, spec: AgentSpec) -> str:
        return " ".join([
            spec.name,
            spec.primary_goal,
            *spec.responsibilities,
            *spec.constraints,
            *spec.outputs,
            *spec.success_criteria,
            *spec.preferred_methods,
        ]).lower()

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

    def _build_capability_context(self, snapshot: Dict[str, Any]) -> str:
        def format_items(title: str, items: List[str]) -> List[str]:
            if not items:
                return [f"- {title}：暂无"]
            return [f"- {title}：" + "；".join(items[:6])]

        lines: List[str] = [
            "当前项目已知能力快照（来自已注册工具和已生成 Skill，不是手写假设）：",
            f"- 当前共注册内置工具 {snapshot.get('totals', {}).get('builtin_tools', 0)} 个，external_skills {snapshot.get('totals', {}).get('external_skills', 0)} 个。",
        ]
        lines.extend(format_items("内置取数能力", snapshot.get("builtin_data_tools", [])))
        lines.extend(format_items("内置分析能力", snapshot.get("builtin_analysis_tools", [])))
        lines.extend(format_items("外部取数 Skill", snapshot.get("external_data_skills", [])))
        lines.extend(format_items("外部分析 Skill", snapshot.get("external_analysis_skills", [])))
        lines.extend(format_items("估值相关能力", self._dedupe([*snapshot.get("valuation_tools", []), *snapshot.get("valuation_skills", [])])))
        lines.extend([
            "- 对股票分析类 Agent，默认优先复用这些已存在能力。",
            "- 真正需要追问的，是用户想怎么组合这些能力，以及还缺什么，而不是重新追问项目有没有行情或财务数据底座。",
        ])
        return "\n".join(lines)

    def _build_project_background_context(self) -> str:
        lines = [
            "当前项目背景：",
            "- 这是 TradingAgents-CN，一个面向投研和交易分析场景的多智能体金融分析系统。",
            "- 系统已经具备单股分析、ETF 分析、持仓分析、交易复盘、组合健康度、智能助手、Prompt 设计、工作流生成、能力生成与任务中心等模块。",
            "- 系统里的 Agent 不是独立 App，也不是一次性的聊天角色，而是可以被接入现有分析流、全新自定义流程、智能助手调用链、提示词系统、工具注册表、调试链路和评估链路的可运行能力单元。",
            "- Agent 工坊的目的，是围绕某个新 Agent 做完整生命周期闭环：需求澄清、规格定义、能力缺口识别、版本草案生成、真实结果评估、再迭代。",
            "- 这里之所以要生成 Agent，不是为了展示一个概念，而是为了给现有系统补一个可复用、可评估、可继续迭代的新角色能力。",
            "- 因此你在需求沟通时，要优先考虑这个 Agent 如何嵌入现有系统：它服务什么分析场景，复用哪些现有能力，还缺哪些可调用能力，以及它更适合被单独调用、被助手调用、还是被编排进某条工作流。",
            "- 对用户来说，Agent 工坊的价值不是从零造一个全新系统，而是基于现有金融分析系统，补齐一个更专业、更可复核的新 Agent。",
        ]
        return "\n".join(lines)

    def _build_application_scene_context(self) -> str:
        lines = [
            "当前系统中的典型接入场景：",
            "- 单股分析 / ETF 分析：适合能输出结构化观点、估值、风险拆解、催化剂分析、结论摘要的 Agent。",
            "- 批量分析 / 股票筛选：适合能做标准化打分、排序、初筛、信号归类、候选池比较的 Agent。",
            "- 智能助手：适合能被助手直接调用、一次性交付完整能力结果的 Agent。这里不必预设助手一定要先组装多个工具；Agent 本身就可以是被调用的完整能力单元。",
            "- 持仓分析 / 组合健康度：适合能做仓位诊断、集中度检查、风险暴露识别、再平衡建议的 Agent。",
            "- 操作复盘 / 交易计划：适合能复盘买卖逻辑、检查纪律执行、提炼经验教训、生成计划模板的 Agent。",
            "- 分析报告 / 任务中心：适合能把中间结果整理成报告卡片、阶段结论、异步任务产物或可追踪检查项的 Agent。",
            "- 多 Agent 编排 / 自定义流程：适合放入新建工作流中的专用角色，例如研究员、评审者、风险把关者、估值汇总者。",
            "- 这些场景只是帮助理解典型用法，不是限制条件。新 Agent 既可能复用到现有页面，也可能进入全新自定义流程，或被智能助手直接当作完整能力调用。",
            "- 需求沟通时请主动补齐这些关键落点：核心使用方式、触发入口、上游输入、依赖能力、输出形态、下游消费方、是否需要进入调试或评估链路。",
        ]
        return "\n".join(lines)

    def _build_agent_role_pattern_context(self) -> str:
        lines = [
            "当前系统里已有的典型 Agent 角色模式：",
            "- 单股/行业研究链路常见角色：市场分析师、基本面分析师、新闻分析师、社媒分析师、大盘分析师、板块分析师、ETF 分析师。适合做分维度观察、形成结构化子结论。",
            "- 观点对抗链路常见角色：看涨研究员、看跌研究员。适合把同一标的拆成多空两套论证，再交给管理者汇总。",
            "- 管理汇总链路常见角色：研究经理、风险管理者。适合做跨分析师整合、冲突裁决、风险兜底、结论收束。",
            "- 风险辩论链路常见角色：激进风险分析师、保守风险分析师、中性风险分析师。适合围绕仓位、风险承受和交易约束给出不同风险立场。",
            "- 复盘链路常见角色：时机分析师、仓位分析师、情绪分析师、归因分析师、复盘总结师。适合解释交易为什么做、哪里做对/做错、后续如何改。",
            "- 持仓/组合链路常见角色：技术面分析师、基本面分析师、风险评估师、操作建议师。适合对现有持仓做诊断、归因和调仓建议。",
            "- 后处理链路常见角色：数据准备器、报告生成器。适合把上游结果规整成统一输入或可展示报告。",
            "- 如果用户提的是一个新 Agent，你应先判断它更像哪一类角色：独立分析师、对抗研究员、管理者、风险辩论者、复盘分析者、持仓顾问，还是后处理器。",
            "- 如果用户描述其实是某个既有角色的细分能力升级，例如估值、筹码、情绪、归因，请优先建议做成现有角色的增强版或专用子角色，而不是凭空创造难落地的大而全新物种。",
        ]
        return "\n".join(lines)

    def _build_solution_design_context(self, spec: AgentSpec) -> str:
        lines = [
            "你现在不是在做抽象的能力分类，而是在为 TradingAgents-CN 设计一个能落地的 Agent 方案。",
            "你必须同时扮演金融行业专家和系统架构师：既理解投研/交易分析场景下用户真正要什么，也理解当前系统里已有什么能力、什么适合复用、什么需要补。",
            "你的设计判断必须同时基于四个维度：",
            f"- 业务目标：{spec.primary_goal or spec.name or '待确认'}",
            f"- 用户真正要的交付：{'；'.join(spec.outputs[:6]) if spec.outputs else '需结合 responsibilities / success_criteria 判断'}",
            f"- 关键约束与边界：{'；'.join(self._dedupe([*spec.constraints, *spec.non_goals])[:8]) if (spec.constraints or spec.non_goals) else '暂无显式约束'}",
            f"- 成功标准：{'；'.join(spec.success_criteria[:6]) if spec.success_criteria else '暂无显式成功标准'}",
            "设计时不要只盯着单个字段，要结合当前系统现状、用户目标、输出方式、约束边界、可复用能力和潜在运行链路来判断缺口。",
            "如果规格里已经明确了背景、客户需求、约束和输出方式，这些信息都必须进入你的判断，而不是只围绕 suggested_tools 做机械补全。",
        ]
        return "\n".join(lines)

    async def _analyze_requirement_turn(
        self,
        messages: List[str],
        user_id: str = "",
        fallback_spec_id: Optional[str] = None,
        existing_spec: Optional[AgentSpec] = None,
    ) -> Dict[str, Any]:
        client = await self._ensure_llm_client()
        base_spec = existing_spec or AgentSpec(
            spec_id=fallback_spec_id or f"agent-workshop-{uuid.uuid4().hex[:8]}",
            name="待确认 Agent",
            owner_user_id=user_id,
        )

        conversation = "\n\n".join(
            f"第{idx + 1}轮用户输入：\n{item.strip()}" for idx, item in enumerate(messages) if item and item.strip()
        )
        capability_snapshot = await self._collect_capability_snapshot()
        project_background_context = self._build_project_background_context()
        application_scene_context = self._build_application_scene_context()
        agent_role_pattern_context = self._build_agent_role_pattern_context()
        capability_context = self._build_capability_context(capability_snapshot)

        prompt = "\n".join([
            "你正在 TradingAgents-CN 的 Agent 工坊中工作。这个系统是一个面向投研、交易分析、Agent 编排与能力复用的多智能体金融分析系统。",
            "你当前扮演的角色不是通用问答助手，而是 Agent 工坊里的金融行业专家兼需求澄清助手，负责把用户想要的新 Agent 需求整理成可执行的设计输入。",
            "你对系统现状的理解，必须优先来自项目背景、典型接入场景、已有角色模式、能力快照、用户输入和现有草案，而不是凭空假设系统里已经有或没有某种能力。",
            "你的任务不是套用固定模板，而是根据用户多轮输入，动态判断需求是否清楚、是否可做，并整理出一版 Agent 规格草案。你要像资深金融产品专家一样，先给可落地建议，再只追问少数真正会影响设计分叉的点。",
            "要求：",
            "1. 你不能把本应由专家判断的内容全部反问给用户。对于行业常识、常见金融分析框架、默认展示结构、常用评分口径，你应先给出推荐方案和理由，再只追问会导致设计分叉的关键点。",
            "2. 不要用僵硬的硬编码模板替用户做决定，但可以基于金融行业常见最佳实践，主动补成一版可执行草案，并明确哪些是你的推荐默认值。",
            "3. 如果用户后续补充了限制、目标、输出、方法、样本或验收标准，必须覆盖到结果里。",
            "3.1 任何用户明确给出的数字型要求都必须原样保留，禁止擅自泛化。例如用户说“三种估值方式”，结果里不能偷换成“多种估值方法”。",
            "3.2 任何用户明确给出的交付方式都必须落到结构化字段里。例如用户说“根据这三种估值方式分别返回数据，并进行解读”，你就必须在 responsibilities、outputs、success_criteria 或 constraints 中明确体现“分别返回三种方法结果”和“对三种结果做解读”，不能只保留一个模糊的总目标。",
            "3.3 任何用户明确给出的非目标和禁止项都必须保留在 non_goals 或 constraints 中。例如“不直接给买卖建议”不能在整理过程中弱化或遗漏。",
            "3.4 primary_goal 可以概括，但不得吞掉关键限定词；如果用户要求里含有具体数量、方法清单、返回方式、解释要求，这些必须出现在 responsibilities / outputs / success_criteria / preferred_methods 中，而不是只剩一个抽象摘要。",
            "4. 如果需求明显超出当前 Agent 工坊范围、互相矛盾、或不可落地，请直接判定 not-feasible，并用口语化中文说明为什么做不到。",
            "5. 如果只是信息不够，请判定 need-clarification，但必须先给出推荐方案，再提出最多 2 个最关键的问题。不要把零散小问题全部丢给用户。",
            "6. 只有当需求已经足够清楚且可以进入下一步时，才判定 feasible。",
            "7. response_message 必须是直接给用户看的口语化中文，不要写“字段”“schema”“规格化”等系统术语；语气要像专家在给方案，不要像客服在收集需求。",
            "8. 输出必须是纯 JSON，不要 markdown，不要额外解释。",
            "9. 对股票分析类 Agent，要把现有项目的行情/财务/行业基础能力视为默认可复用前提，不要把用户当成要从零造数据底座。",
            "10. 如果用户已经明确说要基于现有项目能力做 Agent，就不要再追问‘数据从哪来’这类基础设施问题，除非用户需求里真的涉及新的外部数据依赖。",
            "11. response_message 里要优先包含：你的理解、你的推荐默认方案、为什么这样更合理；如果还有关键分歧，再补少量确认问题。",
            "12. 你要把新 Agent 理解成系统里的可运行能力单元，但不要默认它必须挂到现有页面或既有流程；它也可能进入新的自定义工作流，或被智能助手直接调用来一次性完成完整能力。",
            "13. 讨论接入方式时，请把“被助手直接调用”“进入新建流程编排”“复用到现有模块”都视为平级选项，根据用户目标推荐最合适的一种，而不是强行收敛到既有流程节点。",
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
            json.dumps({
                "name": base_spec.name,
                "domain": base_spec.domain,
                "target_users": base_spec.target_users,
                "primary_goal": base_spec.primary_goal,
                "responsibilities": base_spec.responsibilities,
                "non_goals": base_spec.non_goals,
                "inputs": base_spec.inputs,
                "outputs": base_spec.outputs,
                "success_criteria": base_spec.success_criteria,
                "constraints": base_spec.constraints,
                "preferred_methods": base_spec.preferred_methods,
                "sample_symbols": base_spec.sample_symbols,
            }, ensure_ascii=False, indent=2),
            "",
            "用户多轮输入：",
            conversation or "（空）",
            "",
            "请输出如下 JSON：",
            "{",
            '  "feasibility_status": "feasible | need-clarification | not-feasible",',
            '  "response_message": "直接给用户看的中文回复",',
            '  "refusal_reason": "若做不到，说明原因；否则为空字符串",',
            '  "expert_recommendations": [],',
            '  "assumed_defaults": [],',
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
            '  "sample_symbols": []',
            "}",
            "自检要求：输出前请检查，用户原始需求里凡是出现了明确数量（如三种）、明确方法（如 DCF/PE-PB/PEG）、明确交付动作（如分别返回/进行解读）、明确禁止项（如不要直接给买卖建议），都必须在 JSON 中找到对应落点；找不到就说明你整理丢了。",
        ])

        system_prompt = "你正在 TradingAgents-CN 的 Agent 工坊中工作。TradingAgents-CN 是一个面向投研、交易分析、Agent 编排与能力复用的多智能体金融分析系统。你当前角色是金融行业专家兼系统架构视角下的需求澄清助手，职责是把用户需求整理成可执行的 Agent 设计输入。你的判断依据只能来自用户输入、系统背景、典型场景、已有角色模式、能力快照和当前草案，不能凭空假设系统现状。你会先给推荐方案和默认设计，再只追问少数关键分歧。只输出纯 JSON。"
        response = await client.achat([
            Message(role="system", content=system_prompt),
            Message(role="user", content=prompt),
        ])
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
            expert_recommendations = self._dedupe([
                *self._require_list_field(data, "expert_recommendations", "requirement_clarification"),
                *self._require_list_field(data, "assumed_defaults", "requirement_clarification"),
            ])
            spec = self._merge_llm_spec_data(data, base_spec, fallback_spec_id=fallback_spec_id)
            ai_message = self._compose_turn_message(
                self._require_string_field(data, "response_message", "requirement_clarification"),
                pending_questions,
                feasibility_status,
                expert_recommendations,
            )
        except Exception as exc:
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
            "你正在 TradingAgents-CN 的 Agent 生命周期工坊中工作。这个系统是一个面向投研、交易分析、Agent 编排与能力复用的多智能体金融分析系统。",
            "你当前角色是金融行业专家兼系统架构师，负责把 Agent 规格和缺口分析转成可执行的工具与能力方案。",
            "你对系统现状的理解，必须来自当前规格、缺口分析、系统背景、典型接入场景、已有角色模式和已知能力信息，不能自己脑补系统已有能力。",
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
                "outputs": spec.outputs,
                "constraints": spec.constraints,
                "preferred_methods": spec.preferred_methods,
                "success_criteria": spec.success_criteria,
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
            responsibilities=self._require_list_field(data, "responsibilities", "requirement_clarification"),
            non_goals=self._require_list_field(data, "non_goals", "requirement_clarification"),
            inputs=self._require_list_field(data, "inputs", "requirement_clarification"),
            outputs=self._require_list_field(data, "outputs", "requirement_clarification"),
            success_criteria=self._require_list_field(data, "success_criteria", "requirement_clarification"),
            constraints=self._require_list_field(data, "constraints", "requirement_clarification"),
            preferred_methods=self._require_list_field(data, "preferred_methods", "requirement_clarification"),
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
            raise ValueError(f"{stage} 缺少数组字段 {key}")
        normalized: List[str] = []
        for item in value:
            if not isinstance(item, (str, int, float)):
                raise ValueError(f"{stage} 字段 {key} 必须是字符串数组")
            text = str(item).strip()
            if not text:
                raise ValueError(f"{stage} 字段 {key} 里存在空项")
            normalized.append(text)
        return self._dedupe(normalized)

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
                "默认采用 PB、PE、DCF 三种方法并行，先给方法结论，再做综合估值汇总。",
                "页面先展示综合结论卡、各方法估值区间、关键假设、失效条件和数据依据，这样最符合金融分析阅读习惯。",
                "评分先默认拆成估值吸引力、基本面质量和安全边际三部分，避免只给单一总分却没有解释。",
                "“需要考虑”的因素先默认纳入宏观利率、行业景气、资产负债表风险和现金流质量，而不是泛泛罗列所有可能因素。",
            ])

        recommendations: List[str] = []
        if spec.primary_goal:
            recommendations.append(f"我建议先围绕“{spec.primary_goal}”收敛设计，避免功能边界过宽。")
        if spec.outputs:
            recommendations.append(f"输出先默认做成结构化卡片，核心包括：{'、'.join(spec.outputs[:4])}。")
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
            "outputs": spec.outputs[:5],
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
        capability_snapshot = await self._collect_capability_snapshot()
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
        reusable_modules = [
            "workflow-generation",
            "skill-generation",
            "skill-gaps",
            "prompt-design",
            "report-templates",
        ]
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
            reusable_modules=reusable_modules,
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
        capability_context = self._build_capability_context(capability_snapshot)
        design_context = self._build_solution_design_context(spec)
        reusable_modules = [
            "workflow-generation",
            "skill-generation",
            "skill-gaps",
            "prompt-design",
            "report-templates",
        ]
        known_tools = self._dedupe([
            *capability_snapshot.get("builtin_data_tools", []),
            *capability_snapshot.get("builtin_analysis_tools", []),
            *capability_snapshot.get("external_data_skills", []),
            *capability_snapshot.get("external_analysis_skills", []),
            *capability_snapshot.get("valuation_tools", []),
            *capability_snapshot.get("valuation_skills", []),
        ])

        prompt = "\n".join([
            "你正在 TradingAgents-CN 的 Agent 工坊中做资源缺口分析。这个系统是一个面向投研、交易分析、Agent 编排与能力复用的多智能体金融分析系统。",
            "你当前角色是金融行业专家兼系统架构师，负责判断当前 Agent 目标在系统内哪些能力已可复用，哪些地方是真缺口。",
            "你对系统现状的理解，必须来自当前规格、项目背景、典型接入场景、已有角色模式和能力快照，不能凭工具名联想不存在的能力，也不能脑补未提供的系统状态。",
            "你的任务是基于当前 Agent 规格和系统现有能力，判断哪些能力已可直接复用，哪些地方是真缺口。",
            "你不能只盯着工具名做机械匹配，而要先理解这个客户想要什么结果、当前系统处在什么基础上、现有能力能否支撑交付、哪些约束会影响设计。",
            "不要机械地把问题拆成数据获取、分析、报告三层；要根据 Agent 的实际目标判断最小闭环。",
            "如果某项能力可以通过现有工具组合或通过 Prompt/模板约束解决，就不要夸大成阻塞缺口。",
            "只有当当前系统确实缺少关键可调用能力，且会直接影响 Agent 的目标达成时，才列入 blocking_gaps。",
            "existing_tools/reusable_modules 必须只使用提供给你的名称，不能编造。",
            "suggested_tools/suggested_capabilities 应尽量少而精，优先补最小闭环，不要一次性铺太大能力面。",
            "如果当前规格要求输出精确数值、区间、评分、排序或权重，Prompt/模板约束不能替代数据链路或工具计算链路；若能力不足，应明确指出缺的是数据源、工具还是来源标注能力。",
            "只输出合法 JSON，不要输出 Markdown 或额外解释。",
            design_context,
            json.dumps({
                "reusable_modules": reusable_modules,
                "existing_tools": [],
                "suggested_tools": [],
                "suggested_capabilities": [],
                "manual_dependencies": [],
                "blocking_gaps": [],
                "fallback_strategy": [],
                "build_recommendations": [],
                "notes": [],
            }, ensure_ascii=False, indent=2),
            "系统背景：",
            self._build_project_background_context(),
            "典型接入场景：",
            self._build_application_scene_context(),
            "典型角色模式：",
            self._build_agent_role_pattern_context(),
            "\n当前 Agent 规格：",
            json.dumps({
                "name": spec.name,
                "domain": spec.domain,
                "primary_goal": spec.primary_goal,
                "responsibilities": spec.responsibilities,
                "non_goals": spec.non_goals,
                "inputs": spec.inputs,
                "outputs": spec.outputs,
                "success_criteria": spec.success_criteria,
                "constraints": spec.constraints,
                "preferred_methods": spec.preferred_methods,
                "sample_symbols": spec.sample_symbols,
            }, ensure_ascii=False, indent=2),
            "\n系统能力快照：",
            capability_context,
            "\n分析要求：",
            "1. existing_tools 只列真正能直接支撑当前 Agent 目标的能力，不要为了凑数把所有相关工具都放进去。",
            "2. suggested_tools 只列当前闭环最缺的 1-4 个工具/Skill。",
            "3. blocking_gaps 要写成‘为什么现有能力还不够’，不是重复需求描述。",
            "4. fallback_strategy 要写成没补齐前 Agent 如何安全降级，不要写空话。",
            "5. build_recommendations 要给出实现顺序和边界控制建议。",
            "6. 如果用户明确要求多步或多方法分别返回结果，不能只建议补一个上游接口；要把真正缺少的能力层讲清楚。",
        ])
        system_prompt = "你正在 TradingAgents-CN 的 Agent 工坊中做资源缺口分析。TradingAgents-CN 是一个面向投研、交易分析、Agent 编排与能力复用的多智能体金融分析系统。你当前角色是金融行业专家兼系统架构师，负责把 Agent 的业务目标、系统现状和约束边界分析成可执行的缺口建设计划。你的判断依据只能来自当前规格、系统背景、典型场景、角色模式和能力快照，不能凭空补系统能力。只输出合法 JSON。"

        raw = ""
        try:
            response = await client.achat([
                Message(role="system", content=system_prompt),
                Message(role="user", content=prompt),
            ])
            raw = response.content or ""
            self._log_llm_exchange(
                "gap_analysis",
                system_prompt,
                prompt,
                raw,
                context={
                    "spec_id": spec.spec_id,
                    "spec_name": spec.name,
                },
            )
            json_match = re.search(r"\{.*\}", raw, re.DOTALL)
            if not json_match:
                raise ValueError("gap analysis LLM 未返回合法 JSON")
            data = json.loads(json_match.group())
        except Exception as exc:
            raise AgentWorkshopLLMStageError("gap_analysis", str(exc), raw_response=raw) from exc

        known_tool_set = set(known_tools)
        known_module_set = set(reusable_modules)
        existing_tools = self._require_list_field(data, "existing_tools", "gap_analysis")
        invalid_tools = [item for item in existing_tools if item not in known_tool_set]
        if invalid_tools:
            raise ValueError(f"gap_analysis existing_tools 包含未定义能力: {', '.join(invalid_tools)}")

        modules = self._require_list_field(data, "reusable_modules", "gap_analysis")
        invalid_modules = [item for item in modules if item not in known_module_set]
        if invalid_modules:
            raise ValueError(f"gap_analysis reusable_modules 包含未定义模块: {', '.join(invalid_modules)}")

        notes = self._require_list_field(data, "notes", "gap_analysis")
        notes.append(
            f"缺口分析由推理模型生成：provider={self._llm_client_meta.get('provider')} model={self._llm_client_meta.get('model')} timeout={self._llm_client_meta.get('timeout')}s"
        )
        gap_report = AgentWorkshopGapAnalysis(
            reusable_modules=self._dedupe(modules)[:8],
            existing_tools=self._dedupe(existing_tools)[:12],
            suggested_tools=self._dedupe(self._require_list_field(data, "suggested_tools", "gap_analysis"))[:8],
            suggested_capabilities=self._dedupe(self._require_list_field(data, "suggested_capabilities", "gap_analysis"))[:8],
            manual_dependencies=self._dedupe(self._require_list_field(data, "manual_dependencies", "gap_analysis"))[:8],
            blocking_gaps=self._dedupe(self._require_list_field(data, "blocking_gaps", "gap_analysis"))[:8],
            fallback_strategy=self._dedupe(self._require_list_field(data, "fallback_strategy", "gap_analysis"))[:8],
            build_recommendations=self._dedupe(self._require_list_field(data, "build_recommendations", "gap_analysis"))[:10],
            notes=self._dedupe(notes)[:10],
            generated_by="llm",
            error_message="",
            raw_response=raw,
        )
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
        snapshot = await self._collect_capability_snapshot()
        return {
            **snapshot,
            "summary_text": self._build_capability_context(snapshot),
        }

    def _select_required_tools(self, spec: AgentSpec, gap_report: AgentWorkshopGapAnalysis) -> List[str]:
        registry = get_tool_registry()
        tool_ids = [tool.id for tool in registry.list_all()]
        selected: List[str] = []

        if self._is_valuation_spec(spec):
            preferred_ids = [
                "get_stock_fundamentals_unified",
                "get_peer_comparison",
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
        for tool_id in preferred_ids:
            if tool_id in tool_ids and tool_id not in selected:
                selected.append(tool_id)

        if spec.domain == "stock_analysis":
            for tool_id in gap_report.existing_tools:
                if any(keyword in tool_id.lower() for keyword in ["stock", "fundamental", "financial", "market"]):
                    if tool_id not in selected:
                        selected.append(tool_id)
                if len(selected) >= (6 if self._is_valuation_spec(spec) else 4):
                    break

        return selected[: (6 if self._is_valuation_spec(spec) else 4)]

    def _select_required_capabilities(
        self,
        gap_report: AgentWorkshopGapAnalysis,
        tooling_plan: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        selected: List[str] = []
        selected.extend(gap_report.suggested_capabilities or [])

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

        for tool_id in gap_report.suggested_tools or []:
            selected.append(self._build_required_capability_label(tool_id))

        return self._dedupe([item for item in selected if item])[:8]

    def _build_output_schema(self, spec: AgentSpec) -> Dict[str, Any]:
        properties = {
            output_name: {
                "type": "string",
                "description": output_name,
            }
            for output_name in spec.outputs
        }
        return {
            "type": "object",
            "required": spec.outputs,
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

    async def _create_prompt_template(self, version_id: str, spec: AgentSpec, required_tools: List[str]) -> Dict[str, Any]:
        prompt_service = PromptTemplateService(db=self._db)

        responsibilities = "\n".join(f"- {item}" for item in spec.responsibilities)
        success_criteria = "\n".join(f"- {item}" for item in spec.success_criteria)
        non_goals = "\n".join(f"- {item}" for item in spec.non_goals)
        constraint_lines = [f"- {item}" for item in spec.constraints]
        output_fields = "\n".join(f"- {item}" for item in spec.outputs)
        tools_text = "\n".join(f"- {item}" for item in required_tools) if required_tools else "- 当前版本尚未绑定工具"
        numeric_rules = self._build_numeric_traceability_rules(spec)
        numeric_policy = self._get_numeric_traceability_policy(spec)
        if numeric_rules:
            constraint_lines.extend(numeric_rules)
        constraints = "\n".join(self._dedupe(constraint_lines))

        tool_guidance = f"优先使用以下工具获取事实依据：\n{tools_text}"
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
            ])

        content = TemplateContent(
            system_prompt=(
                f"你正在 TradingAgents-CN 中运行。TradingAgents-CN 是一个面向投研、交易分析与 Agent 编排场景的多智能体金融分析系统，系统内已有行情、财务、新闻、研究、筛选、复盘、报告、工作流与工具注册等能力模块。"
                f"\n你的角色是{spec.name}。你不是通用聊天助手，而是这个系统里的专业金融分析 Agent，负责在当前规格定义的职责范围内，为用户完成可落地、可复核的分析交付。"
                f"\n你的能力边界来自四类信息：输入上下文、当前版本绑定的可用工具、上游传入的结构化数据/中间结果、以及当前任务的明确约束。凡是不在这四类信息里的能力、数据和系统状态，你都不能自行假设为已知。"
                f"\n你理解系统现状的方式，不是凭空脑补，而是优先依据当前任务输入、可用工具列表、上游上下文、显式约束以及工具调用返回结果来判断：现在系统已经提供了什么、还缺什么、这次任务能做到哪里。"
                f"\n你必须体现该角色对应的金融行业专业判断，但所有事实、数字、结论都必须建立在输入信息、可追溯数据和工具结果之上；不得把本应由数据或工具支撑的内容改成主观臆测。"
                f"\n你必须坚持角色边界，不扩展到未授权的交易建议或其他职责；如果当前信息或能力不足，就明确说明依据不足和降级边界。"
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
            constraints=constraints or "- 不得伪造数据\n- 必须显式说明关键假设和不确定性来源",
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
        output_field = version.agent_metadata.get("output_field") or (spec.outputs[0] if spec.outputs else "analysis_result")
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
            AgentInput(name=input_name, type="string", description=input_name)
            for input_name in (spec.inputs or ["user_request"])
        ]
        outputs = [
            AgentOutput(name=output_name, type="string", description=output_name)
            for output_name in (spec.outputs or ["summary"])
        ]
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
            default_tools=required_tools[:2],
            max_tool_calls=4,
            license_tier=LicenseTier.PRO,
            tags=self._dedupe([spec.domain, *spec.preferred_methods, *spec.target_users]),
            icon="🧪",
            color="#0f8a7d",
            requires_tools=bool(required_tools),
            output_field=(spec.outputs[0] if spec.outputs else "analysis_result"),
            report_label=f"【{spec.name}】",
            node_name=spec.name,
            execution_order=50,
        )
        return metadata.model_dump(mode="json")

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
                        expected_outputs=spec.outputs[:4],
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
                    case.expected_outputs or spec.outputs,
                    provided.get("output_payload"),
                    output_text,
                )
            else:
                schema_props = set((version.output_schema.get("properties") or {}).keys())
                expected_outputs = case.expected_outputs or spec.outputs
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
            "runtime_prompt_quality": round(self._pick_float(llm_scores.get("runtime_prompt_quality"), rule_scores.get("runtime_goal_alignment", 0.0)), 2),
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
        output_evidence = self._analyze_expected_outputs_runtime(spec.outputs, payload, output_text)
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

        output_coverage = output_evidence["score"]
        explainability = explain_evidence["score"]
        method_quality = method_evidence["score"]
        forbidden_penalty = max(forbidden_evidence["score"], valuation_guardrail["penalty"])
        goal_alignment = goal_evidence["score"]

        scores = {
            "runtime_goal_alignment": round(goal_alignment, 2),
            "runtime_output_coverage": round(output_coverage, 2),
            "runtime_explainability": round((explainability + method_quality) / 2, 2),
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
        if user_feedback.strip():
            issues.append(f"用户反馈中提到的问题待处理：{user_feedback.strip()}")

        recommendations = self._dedupe([
            "把当前运行结果中缺失的输出字段补进 Prompt 和输出 Schema。",
            "为真实任务结果增加结构化字段，避免只返回长文本。",
            "把这次 production review 中暴露的问题加入下一轮 benchmark 回归。",
            *( ["对数值类结果增加原始数据、工具计算结果、输入参数和来源标签；没有足够依据时不要输出精确数字。"] if valuation_guardrail["violation"] else [] ),
            *( ["下一轮工坊应优先补数据链路或直接计算工具，而不是继续微调 Prompt 让模型自己编数字。"] if valuation_guardrail["violation"] else [] ),
        ])
        details = {
            "mode": "production-review",
            "runtime_result": runtime_result,
            "parsed_output_excerpt": output_text[:1200],
            "valuation_traceability": valuation_traceability,
            "score_breakdown": {
                "runtime_goal_alignment": {
                    "matched": goal_evidence["matched"],
                    "missing": goal_evidence["missing"],
                    "notes": goal_evidence["notes"],
                },
                "runtime_output_coverage": {
                    "matched": output_evidence["matched"],
                    "missing": output_evidence["missing"],
                    "notes": [f"要求输出字段：{', '.join(spec.outputs) if spec.outputs else '未定义'}"],
                },
                "runtime_explainability": {
                    "matched": self._dedupe([*explain_evidence["matched"], *method_evidence["matched"]]),
                    "missing": self._dedupe([*explain_evidence["missing"], *method_evidence["missing"]]),
                    "notes": [
                        "检查是否解释了假设、风险、失效条件，以及规格要求的方法依据。",
                    ],
                },
                "runtime_constraint_control": {
                    "matched": self._dedupe([*forbidden_evidence["matched"], *valuation_guardrail["matched"]]),
                    "missing": self._dedupe([*forbidden_evidence["missing"], *valuation_guardrail["missing"]]),
                    "notes": self._dedupe([*forbidden_evidence["notes"], *valuation_guardrail["notes"]]),
                },
            },
        }
        return scores, issues, recommendations, details

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
        has_calc_source_label = any(keyword in output_text for keyword in ["来源工具", "计算依据", "输入参数", "工具计算", "数据来源"])
        calc_tool_names = {
            item.get("tool_name")
            for item in tool_trace
            if isinstance(item, dict) and item.get("tool_name")
        }
        used_calc_tools = [
            item.get("tool_name") for item in tool_trace
            if isinstance(item, dict) and item.get("tool_name") in calc_tool_names and item.get("success")
        ]
        has_traceable_evidence = has_structured_calc or bool(used_calc_tools)
        violation = bool(range_mentions) and not has_traceable_evidence

        notes = [
            "数值类结果一旦出现，就必须来自数据源、工具计算或结构化计算结果，不能只由模型根据文本自行给出。",
            *( [f"检测到精确区间: {'；'.join(range_mentions[:4])}"] if range_mentions else [] ),
            *( ["当前输出中虽然有来源标签文本，但未发现结构化工具计算结果。"] if has_calc_source_label and not has_traceable_evidence else [] ),
            *( [f"已识别到可用工具轨迹: {', '.join(used_calc_tools)}"] if used_calc_tools else ["当前未识别到可支撑这些数字的工具轨迹。"] ),
        ]
        if not policy["requires_exact_numeric_outputs"]:
            notes.append("当前规格本身未强制要求精确数值；本次拦截是因为实际输出出现了不可追溯的精确数字。")
        return {
            "violation": violation,
            "penalty": 0.6 if violation else 0.0,
            "matched": (["数值结果具备可追溯的数据或工具依据。"] if has_traceable_evidence else []),
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
        return self._dedupe(matches)

    def _build_valuation_traceability(self, spec: AgentSpec, runtime_result: Dict[str, Any], output_text: str) -> Dict[str, Any]:
        if not self._get_numeric_traceability_policy(spec)["enabled"]:
            return {"enabled": False, "items": [], "summary": "当前版本未启用数值来源追踪。"}

        debug_prompt = self._extract_runtime_debug_prompt(runtime_result)
        tool_trace = debug_prompt.get("tool_trace") if isinstance(debug_prompt, dict) else []
        used_tool_names = [item.get("tool_name") for item in tool_trace if isinstance(item, dict) and item.get("tool_name")]
        range_mentions = self._extract_valuation_range_mentions(output_text)
        has_source_labels = any(keyword in output_text for keyword in ["来源", "数据源", "计算依据", "输入参数", "工具计算"])
        source_type = "tool_or_data_backed" if used_tool_names or has_source_labels else "unverified"
        judgement = "具备可追溯依据" if source_type == "tool_or_data_backed" else "证据不足"
        note = (
            f"检测到工具轨迹: {', '.join(str(name) for name in used_tool_names if name)}"
            if used_tool_names else
            ("输出中包含来源/依据说明。" if has_source_labels else "未检测到可支撑这些数字的工具轨迹或来源说明。")
        )
        items = [
            {
                "label": "数值结果",
                "value": mention,
                "source_type": source_type,
                "judgement": judgement,
                "evidence_tools": self._dedupe([str(name) for name in used_tool_names if name]),
                "notes": [note],
            }
            for mention in range_mentions
        ]

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

        judge_input = {
            "spec": {
                "name": spec.name,
                "domain": spec.domain,
                "primary_goal": spec.primary_goal,
                "responsibilities": spec.responsibilities,
                "outputs": spec.outputs,
                "non_goals": spec.non_goals,
                "constraints": spec.constraints,
                "preferred_methods": spec.preferred_methods,
                "success_criteria": spec.success_criteria,
            },
            "version": {
                "version_id": version.version_id,
                "agent_metadata": version.agent_metadata,
                "required_tools": version.required_tools,
                "output_schema": version.output_schema,
                "prompt_template_ref": version.prompt_template_ref,
                "evaluation_policy": version.evaluation_policy,
            },
            "runtime_context": {
                "symbol": runtime_result.get("symbol"),
                "analysis_date": runtime_result.get("analysis_date"),
                "user_goal": runtime_result.get("user_goal") or spec.primary_goal,
                "llm": runtime_result.get("llm") or {},
                "template": runtime_result.get("template") or {},
                "metadata": runtime_result.get("metadata") or {},
            },
            "prompt_debug": {
                "system_prompt": self._truncate_text(debug_prompt.get("system_prompt"), 4000),
                "user_prompt": self._truncate_text(debug_prompt.get("user_prompt"), 5000),
                "tool_mode": debug_prompt.get("tool_mode"),
                "tool_trace": self._sanitize_tool_trace(tool_trace),
            },
            "runtime_output": {
                "output_text": self._truncate_text(runtime_result.get("output_text"), 8000),
                "output_payload_preview": self._truncate_text(self._json_preview(runtime_payload), 4000),
                "llm_final_response": self._truncate_text(debug_prompt.get("llm_final_response"), 8000),
            },
            "numeric_traceability": valuation_traceability,
            "user_feedback": user_feedback.strip(),
            "rule_signals": {
                "score_breakdown": rule_details.get("score_breakdown", {}),
                "parsed_output_excerpt": self._truncate_text(rule_details.get("parsed_output_excerpt"), 2000),
            },
        }

        prompt = "\n".join([
            "你正在 TradingAgents-CN 的 Agent 生命周期工坊中做运行评审。这个系统是一个面向投研、交易分析、Agent 编排与能力复用的多智能体金融分析系统。",
            "你当前角色是高级评审官，同时具备金融行业专家和系统架构评审者视角，负责评估某个 Agent 版本在一次真实调试运行中的交付质量。",
            "你对系统现状和运行表现的理解，必须来自版本信息、运行上下文、prompt 调试信息、工具轨迹、运行输出、规则信号与用户反馈，不能把未出现的工具使用、数据来源或系统能力当成既成事实。",
            "你的任务不是做关键词匹配，而是基于完整证据评估这个 Agent 版本在一次真实调试运行中的质量，并判断它是否真的符合业务目标、系统现状和约束边界。",
            "你既要看结论在金融业务上是否像样，也要看它在系统实现上是否可复核、可执行、可持续迭代。",
            "你必须覆盖以下维度：",
            "1. runtime_goal_alignment: 输出是否真正回应用户目标。",
            "2. runtime_output_quality: 输出质量是否完整、专业、可用，而不是只看字段命中。",
            "3. runtime_reasoning_quality: 分析过程是否合理，假设、推导、结论之间是否自洽。",
            "4. runtime_tool_usage: 工具选择与工具调用过程是否合理；如果没有真实工具轨迹，要明确说明证据不足，而不是假装看到了。",
            "5. runtime_prompt_quality: system/user prompt 设计是否清晰、约束是否充分、是否容易把模型引向正确任务。",
            "6. runtime_constraint_control: 是否存在越界、幻觉、与 non_goals/constraints 冲突的问题。",
            "评分范围统一为 0 到 1。0 表示严重不合格，1 表示非常好。",
            "规则扫描结果只能作为参考证据，不能直接照抄成结论。",
            "如果某个维度证据不足，要在 notes 里明确写出证据不足的原因。",
            "只输出 JSON，不要输出 Markdown、解释性前后缀或代码块。",
            "JSON 结构必须严格如下：",
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
            return self._score_expected_outputs_runtime(case.expected_outputs or spec.outputs, output_payload, output_text)

        schema_props = set((version.output_schema.get("properties") or {}).keys())
        expected = case.expected_outputs or spec.outputs
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
                cleaned = sub_part.strip(" ：:、")
                if cleaned and len(cleaned) >= 3:
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
        output_completeness = min(1.0, len(version.output_schema.get("properties", {})) / max(1, len(spec.outputs) or 1))
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