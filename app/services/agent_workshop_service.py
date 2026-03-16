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
from core.agents.config import AgentCategory, AgentInput, AgentMetadata, AgentOutput, LicenseTier
from core.llm import UnifiedLLMClient, Message
from core.tools import get_tool_registry
from core.tools.config import ToolCategory

logger = logging.getLogger(__name__)

SPEC_COLLECTION = "agent_specs"
SESSION_COLLECTION = "agent_workshop_sessions"
VERSION_COLLECTION = "agent_versions"
EVALUATION_COLLECTION = "agent_evaluations"


class AgentWorkshopService:
    """Agent 工坊服务层"""

    _LLM_TIMEOUT = 180

    def __init__(self, db: AsyncIOMotorDatabase):
        self._db = db
        self._llm_client: Optional[UnifiedLLMClient] = None
        self._llm_client_meta: Dict[str, Any] = {}

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

        gap_report = await self._build_gap_analysis(session.current_spec_snapshot)
        session.stage = AgentWorkshopStage.GAP_ANALYSIS
        session.gap_report = gap_report
        session.updated_at = now_tz()
        await self._save_session(session)

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
            logger.warning("[AgentWorkshop] 生成工具需求草案时 LLM 失败，使用规则兜底: %s", exc, exc_info=True)
            tooling_plan = self._build_tooling_plan_fallback(spec, session.gap_report)

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
        required_skills = self._select_required_skills(session.gap_report)
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
            required_skills=required_skills,
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

        return {
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
                "agent_name": version.agent_metadata.get("name") or spec.name,
                "required_tools": version.required_tools,
                "user_goal": user_goal,
            },
        }

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

    def _build_valuation_hard_rules(self, spec: AgentSpec) -> List[str]:
        if not self._is_valuation_spec(spec):
            return []
        return [
            "- PB/PE/DCF/综合估值区间必须来自工具计算或可追溯的工具结果汇总，不能由模型自行臆测。",
            "- 如果没有工具计算结果或缺少关键输入参数，禁止输出任何精确估值区间、目标价、加权结果。",
            "- 允许输出方向性判断，但必须明确说明当前缺少工具化计算结果，暂不提供精确区间。",
            "- 每个估值数字都必须标明来源工具、关键输入参数或引用的工具结果。",
        ]

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
        capability_context = self._build_capability_context(capability_snapshot)

        prompt = "\n".join([
            "你是 Agent 工坊里的需求澄清助手。",
            "你的任务不是套用固定模板，而是根据用户多轮输入，动态判断需求是否清楚、是否可做，并整理出一版 Agent 规格草案。",
            "要求：",
            "1. 严禁使用硬编码的行业默认规则去替用户补需求。用户没说清楚的地方，要追问，不要自作主张。",
            "2. 如果用户后续补充了限制、目标、输出、方法、样本或验收标准，必须覆盖到结果里。",
            "3. 如果需求明显超出当前 Agent 工坊范围、互相矛盾、或不可落地，请直接判定 not-feasible，并用口语化中文说明为什么做不到。",
            "4. 如果只是信息不够，请判定 need-clarification，并提出最多 3 个最关键的问题。",
            "5. 只有当需求已经足够清楚且可以进入下一步时，才判定 feasible。",
            "6. response_message 必须是直接给用户看的口语化中文，不要写“字段”“schema”“规格化”等系统术语。",
            "7. 输出必须是纯 JSON，不要 markdown，不要额外解释。",
            "8. 对股票分析类 Agent，要把现有项目的行情/财务/行业基础能力视为默认可复用前提，不要把用户当成要从零造数据底座。",
            "9. 如果用户已经明确说要基于现有项目能力做 Agent，就不要再追问‘数据从哪来’这类基础设施问题，除非用户需求里真的涉及新的外部数据依赖。",
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
        ])

        response = await client.achat([
            Message(role="system", content="你擅长把用户需求澄清成可执行的 Agent 设计输入。你不会乱补默认规则；不清楚就追问，做不到就直接说明。只输出纯 JSON。"),
            Message(role="user", content=prompt),
        ])
        data = json.loads(self._strip_markdown_fence((response.content or "").strip()))

        feasibility_status = self._normalize_feasibility_status(data.get("feasibility_status"))
        completeness_score = self._pick_float(data.get("completeness_score"), 0.0)
        pending_questions = self._pick_list(data.get("pending_questions"), [])[:3]
        refusal_reason = self._pick_str(data.get("refusal_reason"), "")
        spec = self._merge_llm_spec_data(data, base_spec, fallback_spec_id=fallback_spec_id)
        ai_message = self._compose_turn_message(
            self._pick_str(
            data.get("response_message"),
            self._build_fallback_turn_message(spec, pending_questions, completeness_score, feasibility_status, refusal_reason),
            ),
            pending_questions,
            feasibility_status,
        )

        spec.owner_user_id = user_id
        return {
            "spec": spec,
            "pending_questions": pending_questions,
            "completeness_score": completeness_score,
            "ai_message": ai_message,
            "feasibility_status": feasibility_status,
            "refusal_reason": refusal_reason,
        }

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
        prompt = "\n".join([
            "你是 Agent 生命周期工坊里的工具架构师。",
            "请基于当前 Agent 规格和缺口分析，产出一份工具需求草案。",
            "重点不是重复描述问题，而是回答 4 件事：缺什么工具、为什么缺、没补齐前如何降级、下一步先实现什么。",
            "只输出 JSON，不要输出 Markdown 或额外解释。",
            "JSON 结构必须如下：",
            json.dumps({
                "summary": "",
                "missing_capabilities": [],
                "draft_tools": [
                    {
                        "tool_id": "",
                        "tool_name": "",
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

        response = await client.achat([
            Message(role="system", content="你擅长把工具缺口转成可执行的工具设计草案，只输出合法 JSON。"),
            Message(role="user", content=prompt),
        ])
        raw_content = (response.content or "").strip()
        data = self._load_json_response(raw_content)
        return self._normalize_tooling_plan(data, spec, gap_report, raw_content)

    def _build_tooling_plan_fallback(
        self,
        spec: AgentSpec,
        gap_report: AgentWorkshopGapAnalysis,
    ) -> Dict[str, Any]:
        draft_tools = [
            self._build_tool_blueprint(tool_id, spec, gap_report)
            for tool_id in (gap_report.suggested_tools or [])[:6]
        ]

        if not draft_tools and self._is_valuation_spec(spec):
            draft_tools = [
                self._build_tool_blueprint(tool_id, spec, gap_report)
                for tool_id in [
                    "calculate_pb_valuation",
                    "calculate_pe_valuation",
                    "calculate_dcf_valuation",
                    "calculate_weighted_valuation",
                ]
            ]

        implementation_order = [
            f"{item.get('priority', 'P1')} - {item.get('tool_name') or item.get('tool_id')}"
            for item in draft_tools
        ]
        return {
            "summary": f"当前工坊已识别 {len(gap_report.blocking_gaps)} 个阻塞缺口，建议先补工具再继续追求精确输出。",
            "missing_capabilities": self._dedupe([
                *gap_report.blocking_gaps,
                *gap_report.manual_dependencies,
            ]),
            "draft_tools": draft_tools,
            "implementation_order": implementation_order,
            "notes": self._dedupe([
                *gap_report.fallback_strategy,
                *gap_report.build_recommendations,
            ]),
            "generated_by": "fallback",
        }

    def _normalize_tooling_plan(
        self,
        data: Dict[str, Any],
        spec: AgentSpec,
        gap_report: AgentWorkshopGapAnalysis,
        raw_content: str,
    ) -> Dict[str, Any]:
        raw_tools = data.get("draft_tools") if isinstance(data.get("draft_tools"), list) else []
        draft_tools = []
        for item in raw_tools[:8]:
            if not isinstance(item, dict):
                continue
            draft_tools.append({
                "tool_id": self._pick_str(item.get("tool_id"), "tool_to_define"),
                "tool_name": self._pick_str(item.get("tool_name"), self._pick_str(item.get("tool_id"), "待定义工具")),
                "priority": self._pick_str(item.get("priority"), "P1"),
                "why_needed": self._pick_str(item.get("why_needed"), "用于补齐当前工坊识别到的能力缺口。"),
                "solves_gaps": self._pick_list(item.get("solves_gaps"), []),
                "fallback_before_ready": self._pick_str(item.get("fallback_before_ready"), "缺少该工具前，先降级执行并明确说明结果边界。"),
                "dependencies": self._pick_list(item.get("dependencies"), []),
                "inputs": self._normalize_tool_schema_items(item.get("inputs"), kind="input"),
                "outputs": self._normalize_tool_schema_items(item.get("outputs"), kind="output"),
                "acceptance_criteria": self._pick_list(item.get("acceptance_criteria"), []),
            })

        if not draft_tools:
            return self._build_tooling_plan_fallback(spec, gap_report)

        return {
            "summary": self._pick_str(data.get("summary"), "工具需求草案已生成。"),
            "missing_capabilities": self._pick_list(data.get("missing_capabilities"), gap_report.blocking_gaps),
            "draft_tools": draft_tools,
            "implementation_order": self._pick_list(data.get("implementation_order"), []),
            "notes": self._pick_list(data.get("notes"), []),
            "generated_by": "llm",
            "raw_response": raw_content,
        }

    def _normalize_tool_schema_items(self, value: Any, kind: str) -> List[Dict[str, Any]]:
        if not isinstance(value, list):
            return []
        normalized: List[Dict[str, Any]] = []
        for item in value[:12]:
            if not isinstance(item, dict):
                continue
            normalized.append({
                "name": self._pick_str(item.get("name"), f"{kind}_field"),
                "type": self._pick_str(item.get("type"), "string"),
                "required": bool(item.get("required", kind == "input")),
                "description": self._pick_str(item.get("description"), ""),
            })
        return normalized

    def _build_tool_blueprint(
        self,
        tool_id: str,
        spec: AgentSpec,
        gap_report: AgentWorkshopGapAnalysis,
    ) -> Dict[str, Any]:
        blueprints = {
            "calculate_pb_valuation": {
                "tool_name": "PB 估值计算工具",
                "priority": "P0",
                "why_needed": "把市净率估值从文本推断升级为可复核的结构化计算。",
                "solves_gaps": ["缺少直接输出 PB 估值区间的专用计算工具。"],
                "dependencies": ["每股净资产或净资产口径", "同行 PB 参考值", "目标安全边际参数"],
                "inputs": [
                    {"name": "ticker", "type": "string", "required": True, "description": "股票代码"},
                    {"name": "analysis_date", "type": "string", "required": True, "description": "分析日期"},
                    {"name": "peer_pb_reference", "type": "array", "required": True, "description": "同行 PB 参考值列表"},
                    {"name": "book_value_per_share", "type": "number", "required": True, "description": "每股净资产"},
                ],
                "outputs": [
                    {"name": "valuation_range", "type": "object", "description": "PB 估值区间"},
                    {"name": "calculation_steps", "type": "array", "description": "关键计算过程"},
                ],
                "acceptance_criteria": [
                    "输出低/中/高三档 PB 假设与对应价格区间。",
                    "能回溯关键输入参数与采用的同行参考口径。",
                ],
            },
            "calculate_pe_valuation": {
                "tool_name": "PE 估值计算工具",
                "priority": "P0",
                "why_needed": "为盈利类估值提供可追溯的目标价区间。",
                "solves_gaps": ["缺少直接输出 PE 估值区间的专用计算工具。"],
                "dependencies": ["EPS 口径定义", "同行 PE 参考值", "盈利预测来源"],
                "inputs": [
                    {"name": "ticker", "type": "string", "required": True, "description": "股票代码"},
                    {"name": "analysis_date", "type": "string", "required": True, "description": "分析日期"},
                    {"name": "eps", "type": "number", "required": True, "description": "每股收益"},
                    {"name": "peer_pe_reference", "type": "array", "required": True, "description": "同行 PE 参考值列表"},
                ],
                "outputs": [
                    {"name": "valuation_range", "type": "object", "description": "PE 估值区间"},
                    {"name": "assumption_summary", "type": "array", "description": "采用的盈利与估值假设"},
                ],
                "acceptance_criteria": [
                    "明确区分 TTM 与 forward EPS 口径。",
                    "输出价格区间及对应的 PE 假设。",
                ],
            },
            "calculate_dcf_valuation": {
                "tool_name": "DCF 估值计算工具",
                "priority": "P1",
                "why_needed": "把 DCF 从模型想象的区间变成有参数、有过程的折现计算。",
                "solves_gaps": ["缺少直接输出 DCF 估值区间的专用计算工具。"],
                "dependencies": ["自由现金流预测", "折现率", "永续增长率", "股本"],
                "inputs": [
                    {"name": "ticker", "type": "string", "required": True, "description": "股票代码"},
                    {"name": "forecast_cashflows", "type": "array", "required": True, "description": "预测期现金流"},
                    {"name": "discount_rate", "type": "number", "required": True, "description": "折现率"},
                    {"name": "terminal_growth_rate", "type": "number", "required": True, "description": "永续增长率"},
                ],
                "outputs": [
                    {"name": "valuation_range", "type": "object", "description": "DCF 估值区间"},
                    {"name": "scenario_table", "type": "array", "description": "不同参数情景下的估值结果"},
                ],
                "acceptance_criteria": [
                    "输出基础/乐观/保守三个场景。",
                    "展示关键输入参数和终值计算方式。",
                ],
            },
            "calculate_weighted_valuation": {
                "tool_name": "综合估值汇总工具",
                "priority": "P1",
                "why_needed": "把多种估值方法的结果汇总为统一的综合估值区间。",
                "solves_gaps": ["缺少综合估值区间和权重汇总工具。"],
                "dependencies": ["PB/PE/DCF 等单方法结果", "权重配置规则"],
                "inputs": [
                    {"name": "valuation_results", "type": "array", "required": True, "description": "各方法的估值结果"},
                    {"name": "weights", "type": "object", "required": True, "description": "各方法权重"},
                ],
                "outputs": [
                    {"name": "weighted_range", "type": "object", "description": "综合估值区间"},
                    {"name": "weight_breakdown", "type": "array", "description": "权重与贡献拆解"},
                ],
                "acceptance_criteria": [
                    "输出综合区间、方法权重和各方法贡献。",
                    "权重和结果都可回溯到单方法工具输出。",
                ],
            },
        }
        blueprint = blueprints.get(tool_id, {
            "tool_name": tool_id,
            "priority": "P1",
            "why_needed": "用于补齐当前工坊识别到的能力缺口。",
            "solves_gaps": gap_report.blocking_gaps[:2],
            "dependencies": gap_report.manual_dependencies[:3],
            "inputs": [],
            "outputs": [],
            "acceptance_criteria": ["能稳定补齐当前缺口，并输出可复核结果。"],
        })
        return {
            "tool_id": tool_id,
            "tool_name": blueprint["tool_name"],
            "priority": blueprint["priority"],
            "why_needed": blueprint["why_needed"],
            "solves_gaps": blueprint["solves_gaps"],
            "fallback_before_ready": gap_report.fallback_strategy[0] if gap_report.fallback_strategy else "缺少工具时，先降级执行并明确说明当前边界。",
            "dependencies": blueprint["dependencies"],
            "inputs": blueprint["inputs"],
            "outputs": blueprint["outputs"],
            "acceptance_criteria": blueprint["acceptance_criteria"],
        }

    def _merge_llm_spec_data(self, data: Dict[str, Any], fallback_spec: AgentSpec, fallback_spec_id: Optional[str] = None) -> AgentSpec:
        name = self._pick_str(data.get("name"), fallback_spec.name)
        domain = self._pick_domain(data.get("domain"), fallback_spec.domain)
        resolved_spec_id = fallback_spec_id or fallback_spec.spec_id
        if not resolved_spec_id or resolved_spec_id.startswith("agent-workshop-"):
            resolved_spec_id = self._slugify(name or fallback_spec.name or f"agent-workshop-{uuid.uuid4().hex[:8]}")

        return AgentSpec(
            spec_id=resolved_spec_id,
            name=name,
            domain=domain,
            target_users=self._pick_list(data.get("target_users"), fallback_spec.target_users),
            primary_goal=self._pick_str(data.get("primary_goal"), fallback_spec.primary_goal),
            responsibilities=self._pick_list(data.get("responsibilities"), fallback_spec.responsibilities),
            non_goals=self._pick_list(data.get("non_goals"), fallback_spec.non_goals),
            inputs=self._pick_list(data.get("inputs"), fallback_spec.inputs),
            outputs=self._pick_list(data.get("outputs"), fallback_spec.outputs),
            success_criteria=self._pick_list(data.get("success_criteria"), fallback_spec.success_criteria),
            constraints=self._pick_list(data.get("constraints"), fallback_spec.constraints),
            preferred_methods=self._pick_list(data.get("preferred_methods"), fallback_spec.preferred_methods),
            sample_symbols=self._pick_list(data.get("sample_symbols"), fallback_spec.sample_symbols),
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
    ) -> str:
        if feasibility_status == "not-feasible":
            return refusal_reason or "这类需求当前没法稳定落到 Agent 工坊里，我建议先把目标收窄一点，再继续讨论。"
        if feasibility_status == "need-clarification":
            question_block = "\n".join(f"{idx + 1}. {item}" for idx, item in enumerate(pending_questions[:3]))
            return (
                f"我大概理解了你想做一个“{spec.name}”，但现在信息还不够，我不想替你脑补规则。"
                f"\n\n还需要你先确认这几件事：\n{question_block}"
            ).strip()
        return f"我已经把这个 Agent 的核心需求整理出来了，当前大概有 {int(completeness_score * 100)}%，可以往下一步走。"

    def _compose_turn_message(self, message: str, pending_questions: List[str], feasibility_status: str) -> str:
        base_message = (message or "").strip()
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
            base_message = f"{base_message}\n\n我还需要你确认这几件事："
            separator = "\n"
        return f"{base_message}{separator}{question_block}".strip()

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

    async def _build_gap_analysis(self, spec: AgentSpec) -> AgentWorkshopGapAnalysis:
        capability_snapshot = await self._collect_capability_snapshot()
        available_data_tools = capability_snapshot.get("builtin_data_tools", [])
        available_analysis_tools = capability_snapshot.get("builtin_analysis_tools", [])
        available_external_data = capability_snapshot.get("external_data_skills", [])
        available_external_analysis = capability_snapshot.get("external_analysis_skills", [])
        valuation_capabilities = self._dedupe([
            *capability_snapshot.get("valuation_tools", []),
            *capability_snapshot.get("valuation_skills", []),
        ])

        reusable_modules = [
            "workflow-generation",
            "skill-generation",
            "skill-gaps",
            "prompt-design",
            "report-templates",
        ]

        existing_tools: List[str] = []
        suggested_tools: List[str] = []
        suggested_skills: List[str] = []
        manual_dependencies: List[str] = []
        blocking_gaps: List[str] = []
        fallback_strategy: List[str] = []
        build_recommendations: List[str] = []
        notes: List[str] = []

        if spec.domain == "stock_analysis":
            existing_tools.extend(available_data_tools[:6])
            existing_tools.extend(available_analysis_tools[:4])
            existing_tools.extend(available_external_data[:4])
            existing_tools.extend(available_external_analysis[:4])

            if self._is_valuation_spec(spec):
                notes.append("工坊会优先判断：现有能力能否支撑结果，哪些地方必须补工具，哪些地方只能先降级。")
                direct_calc_tools = [
                    "calculate_pb_valuation",
                    "calculate_pe_valuation",
                    "calculate_dcf_valuation",
                    "calculate_weighted_valuation",
                ]
                existing_calc_tools = [tool for tool in direct_calc_tools if tool in valuation_capabilities]
                missing_calc_tools = [tool for tool in direct_calc_tools if tool not in valuation_capabilities]

                if valuation_capabilities:
                    notes.append("系统已经发现一批与估值相关的现有能力，可优先复用而不是从零设计。")
                else:
                    notes.append("现有注册能力里，直接面向估值的 Skill/Tool 还不够集中，建议补齐专门的估值能力层。")

                if missing_calc_tools:
                    blocking_gaps.extend([
                        "缺少直接输出 PB/PE/DCF/综合估值区间的专用计算工具。",
                        "当前只能拿到估值证据数据，不能把精确估值数字当作可复核结果。",
                    ])
                    suggested_tools.extend(missing_calc_tools)
                    suggested_skills.extend([
                        "估值方法选择器 Skill",
                        "可比公司筛选 Skill",
                        "敏感性分析 Skill",
                    ])
                    manual_dependencies.extend([
                        "统一行业可比公司映射规则",
                        "估值报告展示模板",
                        "估值计算输入口径定义（TTM/预测、股本、折现率等）",
                    ])
                    fallback_strategy.extend([
                        "降级为定性估值分析：允许输出方法比较、关键假设、风险和方向性判断。",
                        "禁止输出精确目标价、估值区间和加权汇总结果。",
                        "在报告中明确说明：当前缺少工具化估值计算能力，数字结果暂不提供。",
                    ])
                    build_recommendations.extend([
                        "优先补 calculate_pb_valuation 和 calculate_pe_valuation，先把相对估值工具链闭环。",
                        "再补 calculate_dcf_valuation，用于现金流折现的结构化计算。",
                        "最后补 calculate_weighted_valuation，把多方法结果汇总成综合估值区间。",
                        "让每个估值数字输出来源工具、关键参数和中间过程，供工坊评估与复盘。",
                    ])
                else:
                    notes.append(f"已发现直接估值计算工具: {', '.join(existing_calc_tools)}")
                    build_recommendations.append("下一步重点检查这些工具的输入参数口径是否统一，以及输出是否带来源标签。")
        else:
            suggested_skills.append("领域专属分析 Skill")
            notes.append("当前为通用 Agent 草案，后续需要结合具体领域再细化工具缺口。")

        notes.append(
            f"当前已识别到 {len(available_data_tools) + len(available_external_data)} 个取数类能力，"
            f"{len(available_analysis_tools) + len(available_external_analysis)} 个分析类能力。"
        )

        return AgentWorkshopGapAnalysis(
            reusable_modules=reusable_modules,
            existing_tools=self._dedupe(existing_tools)[:12],
            suggested_tools=self._dedupe(suggested_tools),
            suggested_skills=self._dedupe(suggested_skills),
            manual_dependencies=self._dedupe(manual_dependencies),
            blocking_gaps=self._dedupe(blocking_gaps),
            fallback_strategy=self._dedupe(fallback_strategy),
            build_recommendations=self._dedupe(build_recommendations),
            notes=notes,
        )

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

    def _select_required_skills(self, gap_report: AgentWorkshopGapAnalysis) -> List[str]:
        return gap_report.suggested_skills[:3]

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
        if self._is_valuation_spec(spec):
            policy["numeric_traceability_required"] = True
            policy["valuation_numeric_policy"] = {
                "exact_ranges_must_come_from_tools": True,
                "llm_must_not_invent_numeric_ranges": True,
                "require_source_labels": True,
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
        valuation_rules = self._build_valuation_hard_rules(spec)
        if valuation_rules:
            constraint_lines.extend(valuation_rules)
        constraints = "\n".join(self._dedupe(constraint_lines))

        tool_guidance = f"优先使用以下工具获取事实依据：\n{tools_text}"
        if valuation_rules:
            tool_guidance = f"{tool_guidance}\n\n估值数字规则：\n" + "\n".join(valuation_rules)

        output_format = (
            "请输出结构化结果，至少包含以下字段：\n"
            f"{output_fields or '- summary'}"
        )
        if valuation_rules:
            output_format = "\n\n".join([
                output_format,
                "若输出 PB/PE/DCF/综合估值区间，必须同时给出每个数字的来源标签、所依据的工具结果和关键输入参数。若没有工具计算结果，只能给方向性判断，禁止输出精确区间。",
            ])

        content = TemplateContent(
            system_prompt=(
                f"你是{spec.name}。你的唯一任务是围绕用户目标输出稳定、可解释、可复核的专业结论。"
                f"\n你必须坚持角色边界，不扩展到未授权的交易建议或其他职责。"
            ),
            user_prompt="请基于输入标的、上下文数据和可用工具完成本次分析。",
            tool_guidance=tool_guidance,
            analysis_requirements=(
                f"主要目标：{spec.primary_goal}\n\n"
                f"职责范围：\n{responsibilities or '- 待补充'}\n\n"
                f"成功标准：\n{success_criteria or '- 待补充'}\n\n"
                f"非目标：\n{non_goals or '- 无'}"
            ),
            output_format=output_format,
            constraints=constraints or "- 不得伪造数据\n- 必须显式说明关键假设和不确定性来源",
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

        return {
            "template_id": str(template.id),
            "template_name": template.template_name,
            "status": template.status,
        }

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
                "has_runtime_output": has_runtime_output,
                "output_coverage": output_coverage,
                "quality_score": quality_score,
                "constraint_score": constraint_score,
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
            logger.warning("[AgentWorkshop] LLM 结果评估失败，降级到规则评估: %s", exc, exc_info=True)

        if not llm_review:
            fallback_details = dict(rule_details)
            fallback_details.update({
                "evaluation_engine": "rules-fallback",
                "judge_model": self._llm_client_meta,
                "llm_review_error": llm_review_error or "LLM 评审未返回有效结果，已回退到规则评估。",
            })
            return rule_scores, rule_issues, rule_recommendations, fallback_details

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
            issues.append("估值数字违反工具化硬约束：输出了精确区间，但没有提供可追溯的工具计算依据。")
            issues.append("当前更核心的问题不是文案表达，而是缺少直接估值计算工具，导致 Agent 只能生成看似合理但不可复核的数字。")
        if user_feedback.strip():
            issues.append(f"用户反馈中提到的问题待处理：{user_feedback.strip()}")

        recommendations = self._dedupe([
            "把当前运行结果中缺失的输出字段补进 Prompt 和输出 Schema。",
            "为真实任务结果增加结构化字段，避免只返回长文本。",
            "把这次 production review 中暴露的问题加入下一轮 benchmark 回归。",
            *( ["对估值类数字增加工具计算结果、输入参数和来源标签；没有工具计算时不要输出精确区间。"] if valuation_guardrail["violation"] else [] ),
            *( ["下一轮工坊应优先补估值计算工具，而不是继续微调 Prompt 让模型自己编数字。"] if valuation_guardrail["violation"] else [] ),
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
        if not self._is_valuation_spec(spec):
            return {"violation": False, "penalty": 0.0, "matched": [], "missing": [], "notes": []}

        range_mentions = self._extract_valuation_range_mentions(output_text)
        if not range_mentions:
            return {
                "violation": False,
                "penalty": 0.0,
                "matched": ["未输出精确估值区间，符合当前工具化约束。"],
                "missing": [],
                "notes": ["估值类 Agent 在缺少工具计算时，应避免给出精确目标价或区间。"],
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
        calc_tool_names = {"calculate_pb_valuation", "calculate_pe_valuation", "calculate_dcf_valuation", "calculate_weighted_valuation"}
        used_calc_tools = [
            item.get("tool_name") for item in tool_trace
            if isinstance(item, dict) and item.get("tool_name") in calc_tool_names and item.get("success")
        ]
        has_traceable_evidence = has_structured_calc or bool(used_calc_tools)
        violation = bool(range_mentions) and not has_traceable_evidence

        notes = [
            "估值类数字必须来自工具计算或结构化计算结果，不能只由模型根据文本自行给出。",
            *( [f"检测到精确区间: {'；'.join(range_mentions[:4])}"] if range_mentions else [] ),
            *( ["当前输出中虽然有来源标签文本，但未发现结构化工具计算结果。"] if has_calc_source_label and not has_traceable_evidence else [] ),
            *( [f"已识别到计算工具: {', '.join(used_calc_tools)}"] if used_calc_tools else ["当前未识别到专门的估值计算工具轨迹。"] ),
        ]
        return {
            "violation": violation,
            "penalty": 0.6 if violation else 0.0,
            "matched": (["估值数字具备工具化或结构化计算依据。"] if has_traceable_evidence else []),
            "missing": (["精确估值区间缺少工具计算依据。"] if violation else []),
            "notes": notes,
        }

    def _extract_valuation_range_mentions(self, output_text: str) -> List[str]:
        if not output_text:
            return []
        pattern = re.compile(r"(?:PB|PE|DCF|市净率|市盈率|现金流折现|综合估值)[^\n：:]{0,24}?(\d+(?:\.\d+)?\s*[-~至]\s*\d+(?:\.\d+)?)", re.IGNORECASE)
        matches = [match.group(0).strip() for match in pattern.finditer(output_text)]
        return self._dedupe(matches)

    def _build_valuation_traceability(self, spec: AgentSpec, runtime_result: Dict[str, Any], output_text: str) -> Dict[str, Any]:
        if not self._is_valuation_spec(spec):
            return {"enabled": False, "items": [], "summary": "当前版本不是估值类，不启用数值来源追踪。"}

        debug_prompt = self._extract_runtime_debug_prompt(runtime_result)
        tool_trace = debug_prompt.get("tool_trace") if isinstance(debug_prompt, dict) else []
        used_tool_names = [item.get("tool_name") for item in tool_trace if isinstance(item, dict) and item.get("tool_name")]
        range_mentions = self._extract_valuation_range_mentions(output_text)
        items = [
            self._build_valuation_source_item(self._infer_valuation_method_key(mention), mention, used_tool_names)
            for mention in range_mentions
        ]

        if not items:
            return {
                "enabled": True,
                "items": [],
                "summary": "当前输出里没有识别到精确估值区间。",
                "used_tools": self._dedupe([str(name) for name in used_tool_names if name]),
            }

        unresolved = [item for item in items if item.get("source_type") != "tool_calculated"]
        return {
            "enabled": True,
            "items": items,
            "summary": "已识别的估值数字全部来自工具计算。" if not unresolved else "检测到估值区间，但其中部分仍不是工具直接计算结果。",
            "used_tools": self._dedupe([str(name) for name in used_tool_names if name]),
        }

    def _infer_valuation_method_key(self, mention: str) -> str:
        text = str(mention or "").lower()
        if "pb" in text or "市净率" in text:
            return "pb"
        if "pe" in text or "市盈率" in text:
            return "pe"
        if "dcf" in text or "现金流折现" in text:
            return "dcf"
        if "综合估值" in text:
            return "weighted"
        return "unknown"

    def _build_valuation_source_item(self, method_key: str, mention: str, used_tool_names: List[Any]) -> Dict[str, Any]:
        method_label_map = {
            "pb": "PB 估值区间",
            "pe": "PE 估值区间",
            "dcf": "DCF 估值区间",
            "weighted": "综合估值区间",
            "unknown": "估值区间",
        }
        direct_calc_tools = {
            "pb": ["calculate_pb_valuation"],
            "pe": ["calculate_pe_valuation"],
            "dcf": ["calculate_dcf_valuation"],
            "weighted": ["calculate_weighted_valuation"],
        }
        evidence_tools = {
            "pb": ["get_peer_comparison", "get_stock_fundamentals_unified", "get_balance_sheet_analysis"],
            "pe": ["get_peer_comparison", "get_stock_fundamentals_unified", "get_income_analysis"],
            "dcf": ["get_cashflow_analysis", "get_income_analysis", "get_stock_fundamentals_unified"],
            "weighted": ["get_peer_comparison", "get_cashflow_analysis", "get_stock_fundamentals_unified"],
            "unknown": [],
        }

        used_tools = [str(name) for name in used_tool_names if name]
        calc_hits = [tool for tool in direct_calc_tools.get(method_key, []) if tool in used_tools]
        evidence_hits = [tool for tool in evidence_tools.get(method_key, []) if tool in used_tools]

        if calc_hits:
            source_type = "tool_calculated"
            judgement = "工具计算"
            notes = [f"检测到直接计算工具: {', '.join(calc_hits)}"]
        elif evidence_hits:
            source_type = "llm_inferred_from_tool_data"
            judgement = "模型基于工具数据推导"
            notes = [f"只检测到证据类工具: {', '.join(evidence_hits)}，未检测到直接估值计算工具。"]
        else:
            source_type = "unverified"
            judgement = "证据不足"
            notes = ["未检测到可支撑该数字的直接计算工具或关键证据工具。"]

        return {
            "label": method_label_map.get(method_key, "估值区间"),
            "value": mention,
            "source_type": source_type,
            "judgement": judgement,
            "evidence_tools": self._dedupe([*calc_hits, *evidence_hits]),
            "notes": notes,
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
            "你是 Agent 生命周期工坊里的高级评审官。",
            "你的任务不是做关键词匹配，而是基于完整证据评估这个 Agent 版本在一次真实调试运行中的质量。",
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

        response = await client.achat([
            Message(role="system", content="你是严谨的 Agent 运行评审专家。你只输出合法 JSON，并且会明确区分已有证据和证据不足。"),
            Message(role="user", content=prompt),
        ])
        raw_content = (response.content or "").strip()
        data = self._load_json_response(raw_content)
        return self._normalize_runtime_llm_review(data, raw_content)

    def _normalize_runtime_llm_review(self, data: Dict[str, Any], raw_content: str) -> Dict[str, Any]:
        dimension_keys = [
            "runtime_goal_alignment",
            "runtime_output_quality",
            "runtime_reasoning_quality",
            "runtime_tool_usage",
            "runtime_prompt_quality",
            "runtime_constraint_control",
        ]
        source_scores = data.get("scores") if isinstance(data.get("scores"), dict) else {}
        source_dimensions = data.get("dimensions") if isinstance(data.get("dimensions"), dict) else {}

        normalized_dimensions: Dict[str, Any] = {}
        normalized_scores: Dict[str, float] = {}
        all_issues: List[str] = []
        all_recommendations: List[str] = []

        for key in dimension_keys:
            raw_dimension = source_dimensions.get(key) if isinstance(source_dimensions.get(key), dict) else {}
            score = self._clamp_score(
                raw_dimension.get("score", source_scores.get(key, 0.0)),
                fallback=0.0,
            )
            evidence = self._pick_list(raw_dimension.get("evidence"), [])[:6]
            problems = self._pick_list(raw_dimension.get("problems"), [])[:6]
            suggestions = self._pick_list(raw_dimension.get("suggestions"), [])[:6]
            notes = self._pick_list(raw_dimension.get("notes"), [])[:6]
            judgement = self._pick_str(raw_dimension.get("judgement"), "")

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
            "summary": self._pick_str(data.get("summary"), "LLM 已完成运行评审。"),
            "scores": normalized_scores,
            "dimensions": normalized_dimensions,
            "issues": self._dedupe([*self._pick_list(data.get("issues"), []), *all_issues]),
            "recommendations": self._dedupe([*self._pick_list(data.get("recommendations"), []), *all_recommendations]),
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
        if spec.domain == "stock_analysis" and not version.required_skills:
            issues.append("估值相关 Skill 缺口尚未真正补齐，当前版本仍偏配置草案。")
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
            recommendations.append("把缺口分析中的估值 Skill 转成可执行的 Skill 生成任务。")
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