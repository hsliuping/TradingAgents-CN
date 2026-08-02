"""Normal and Top runner bound to persisted PR-010 profiles and prompts."""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
import json
from typing import Any
from uuid import uuid4

from tradingagents.agents.managers.risk_manager import (
    build_top_review_model_request,
    create_risk_manager,
)
from tradingagents.agents.trader.trader import create_trader
from tradingagents.agents.utils.instrument_utils import build_instrument_context
from tradingagents.alphaguard.decision_schemas import (
    ModelExecutionMeta,
    NormalTradePlan,
    TopReviewDecision,
)
from tradingagents.alphaguard.structured_output import (
    render_structured_input_for_estimation,
)

from app.schemas.alphaguard.decision import DecisionContext, RevisionRequest, canonical_hash

from .model_audit_service import ModelAuditService
from .model_budget_service import ModelBudgetService
from .model_profile_registry import ModelProfileRegistry
from .model_provider_runtime import ModelProviderRuntime
from .prompt_profile_registry import PromptProfileRegistry


class ProfiledDecisionModelRunner:
    def __init__(
        self,
        *,
        db,
        normal_node,
        top_node,
        normal_profile,
        top_profile,
        normal_prompt,
        top_prompt,
        revision_prompt,
        run_mode: str,
        automated_execution_allowed: bool,
        model_runtime_context_hash: str,
        research_results: list[dict[str, Any]] | None = None,
    ):
        self.db = db
        self.normal_node = normal_node
        self.top_node = top_node
        self.normal_profile = normal_profile
        self.top_profile = top_profile
        self.normal_prompt = normal_prompt
        self.top_prompt = top_prompt
        self.revision_prompt = revision_prompt
        self.run_mode = run_mode
        self.automated_execution_allowed = automated_execution_allowed
        self.model_runtime_context_hash = model_runtime_context_hash
        self.research_results = research_results or []
        self.budget = ModelBudgetService(db)
        self.audit = ModelAuditService(db)

    @classmethod
    async def create(
        cls,
        *,
        db,
        run_mode: str,
        automated_execution_allowed: bool,
        model_runtime_context_hash: str,
        research_results: list[dict[str, Any]] | None = None,
        provider_runtime: ModelProviderRuntime | None = None,
    ) -> "ProfiledDecisionModelRunner":
        profiles = ModelProfileRegistry(db)
        prompts = PromptProfileRegistry(db)
        normal = await profiles.persisted_for_role("NORMAL_TRADER")
        top = await profiles.persisted_for_role("TOP_RISK_REVIEWER")
        if run_mode in {"PRODUCTION", "PRODUCTION_REPROCESS"}:
            for profile in (normal, top):
                if not profile.production_allowed:
                    raise RuntimeError(
                        "selected ModelProfile is not production allowed"
                    )
                latest_check = await db["ag_model_capability_checks"].find_one(
                    {
                        "profile_id": profile.profile_id,
                        "profile_version": profile.profile_version,
                    },
                    sort=[("checked_at", -1)],
                )
                if profile.provider_type == "OPENAI_COMPATIBLE" and (
                    not latest_check or latest_check.get("status") != "READY"
                ):
                    raise RuntimeError(
                        "compatible ModelProfile capability is not READY"
                    )
        normal_prompt_defined = prompts.definition(normal.prompt_profile_id)
        top_prompt_defined = prompts.definition(top.prompt_profile_id)
        normal_prompt = await prompts.persisted(
            normal_prompt_defined.prompt_id,
            normal_prompt_defined.prompt_version,
        )
        top_prompt = await prompts.persisted(
            top_prompt_defined.prompt_id,
            top_prompt_defined.prompt_version,
        )
        revision_defined = prompts.definition("material_revision_prompt")
        revision_prompt = await prompts.persisted(
            revision_defined.prompt_id,
            revision_defined.prompt_version,
        )
        runtime = provider_runtime or ModelProviderRuntime()
        if normal.cost_currency != top.cost_currency:
            raise RuntimeError("Normal and Top model price currencies differ")
        normal_llm = await runtime.create_registered(normal, db=db)
        top_llm = await runtime.create_registered(top, db=db)
        config = {
            "quick_provider": normal.provider,
            "deep_provider": top.provider,
            "quick_think_llm": normal.model_name,
            "deep_think_llm": top.model_name,
            "normal_profile_id": normal.profile_id,
            "normal_profile_version": normal.profile_version,
            "normal_prompt_id": normal_prompt.prompt_id,
            "normal_prompt_version": normal_prompt.prompt_version,
            "normal_prompt_template": normal_prompt.template,
            "normal_revision_prompt_version": revision_prompt.prompt_version,
            "normal_revision_prompt_template": revision_prompt.template,
            "normal_structured_output_mode": normal.structured_output_mode,
            "normal_input_cost_per_million": normal.input_cost_per_million,
            "normal_output_cost_per_million": normal.output_cost_per_million,
            "normal_max_retries": normal.max_retries,
            "normal_retry_backoff_seconds": normal.retry_backoff_seconds,
            "top_profile_id": top.profile_id,
            "top_profile_version": top.profile_version,
            "top_prompt_id": top_prompt.prompt_id,
            "top_prompt_version": top_prompt.prompt_version,
            "top_prompt_template": top_prompt.template,
            "top_structured_output_mode": top.structured_output_mode,
            "top_input_cost_per_million": top.input_cost_per_million,
            "top_output_cost_per_million": top.output_cost_per_million,
            "top_max_retries": top.max_retries,
            "top_retry_backoff_seconds": top.retry_backoff_seconds,
            "cost_currency": normal.cost_currency,
        }
        return cls(
            db=db,
            normal_node=create_trader(normal_llm, None, config),
            top_node=create_risk_manager(top_llm, None, config),
            normal_profile=normal,
            top_profile=top,
            normal_prompt=normal_prompt,
            top_prompt=top_prompt,
            revision_prompt=revision_prompt,
            run_mode=run_mode,
            automated_execution_allowed=automated_execution_allowed,
            model_runtime_context_hash=model_runtime_context_hash,
            research_results=research_results,
        )

    @staticmethod
    def _base_state(
        context: DecisionContext,
        *,
        attempt_number: int,
        trace_id: str | None,
        research_results: list[dict[str, Any]],
        model_runtime_context_hash: str,
        run_mode: str,
    ) -> dict[str, Any]:
        state = {
            "analysis_id": context.analysis_id,
            "snapshot_id": context.snapshot_id,
            "company_of_interest": context.symbol,
            "trade_date": context.trade_date.isoformat(),
            "market": context.market,
            "legacy_analysis": False,
            "decision_context": context.model_dump(mode="json"),
            "quant_trade_proposal": context.quant_proposal.model_dump(mode="json"),
            "attempt_number": attempt_number,
            "trace_id": trace_id,
            "risk_debate_state": {},
            "tradingagents_research": research_results,
            "model_runtime_context_hash": model_runtime_context_hash,
            "run_mode": run_mode,
        }
        if run_mode == "REAL_MODEL_VALIDATION":
            cst = timezone(timedelta(hours=8))
            state["evaluation_clock"] = {
                "mode": "HISTORICAL_SNAPSHOT_CLOSE",
                "as_of_trade_date": context.trade_date.isoformat(),
                "as_of_at": datetime.combine(
                    context.trade_date, time(hour=15), tzinfo=cst
                ).isoformat(),
                "current_wall_clock_allowed": False,
            }
        return state

    @staticmethod
    def _failure_meta(
        profile,
        prompt,
        context,
        attempt,
        error_type,
        model_runtime_context_hash,
    ):
        now = datetime.now(timezone.utc)
        return ModelExecutionMeta(
            provider=profile.provider,
            model_name=profile.model_name,
            model_version=profile.model_version or profile.model_name,
            prompt_name=prompt.prompt_id,
            prompt_version=prompt.prompt_version,
            started_at=now,
            finished_at=now,
            latency_ms=0,
            execution_status="MODEL_FAILED",
            error_type=error_type,
            error_message="formal model call blocked by runtime policy",
            template_hash=prompt.template_hash,
            context_hash=model_runtime_context_hash,
            input_hash=canonical_hash(
                {"context_hash": model_runtime_context_hash}
            ),
            attempt_number=attempt,
            model_profile_id=profile.profile_id,
            model_profile_version=profile.profile_version,
            prompt_id=prompt.prompt_id,
            structured_output_mode=profile.structured_output_mode,
            cost_currency=profile.cost_currency,
        )

    @classmethod
    def _failure_plan(cls, context, meta, revision_request=None):
        return NormalTradePlan(
            plan_id=str(uuid4()),
            snapshot_id=context.snapshot_id,
            quant_proposal_id=context.quant_proposal_id,
            analysis_id=context.analysis_id,
            decision_context_id=context.decision_context_id,
            symbol=context.symbol,
            market=context.market,
            trade_date=context.trade_date,
            strategy_id=context.strategy_id,
            strategy_version=context.strategy_version,
            revision_round=1 if revision_request else 0,
            supersedes_plan_id=(
                revision_request.original_plan_id if revision_request else None
            ),
            revision_request_id=(
                revision_request.revision_request_id if revision_request else None
            ),
            status="MODEL_FAILED",
            action="NONE",
            confidence=0,
            thesis="formal model runtime blocked",
            bullish_evidence=[],
            bearish_evidence=[],
            entry_zone=None,
            initial_position_pct=None,
            max_position_pct=None,
            add_conditions=[],
            stop_conditions=[],
            reduce_conditions=[],
            exit_conditions=[],
            invalidation_conditions=[],
            target_price=None,
            valid_until=None,
            main_risks=[],
            unresolved_questions=[],
            model_meta=meta,
        )

    async def _check_budget(self, profile, context, rendered):
        return await self.budget.check(
            profile=profile,
            analysis_id=context.analysis_id,
            snapshot_id=context.snapshot_id,
            rendered_input=rendered,
        )

    async def run_normal(
        self,
        *,
        context: DecisionContext,
        attempt_number: int,
        trace_id: str | None,
        revision_request: RevisionRequest | None = None,
        original_plan: NormalTradePlan | None = None,
    ) -> NormalTradePlan:
        prompt = self.revision_prompt if revision_request else self.normal_prompt
        rendered = json.dumps(
            {
                "context": context.model_dump(mode="json"),
                "model_runtime_context_hash": self.model_runtime_context_hash,
                "research": self.research_results,
                "revision_request": (
                    revision_request.model_dump(mode="json")
                    if revision_request
                    else None
                ),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        budget = await self._check_budget(self.normal_profile, context, rendered)
        if not budget.allowed:
            meta = self._failure_meta(
                self.normal_profile,
                prompt,
                context,
                attempt_number,
                budget.reason_code or "BUDGET_BLOCKED",
                self.model_runtime_context_hash,
            )
            plan = self._failure_plan(context, meta, revision_request)
            attempt_metas = [plan.model_meta]
        else:
            state = self._base_state(
                context,
                attempt_number=attempt_number,
                trace_id=trace_id,
                research_results=self.research_results,
                model_runtime_context_hash=self.model_runtime_context_hash,
                run_mode=self.run_mode,
            )
            state["model_max_retries"] = max(
                0, budget.permitted_attempts - 1
            )
            if revision_request:
                state["revision_request"] = revision_request.model_dump(mode="json")
                state["original_normal_trade_plan"] = original_plan.model_dump(
                    mode="json"
                )
            result = self.normal_node(state)
            plan = NormalTradePlan.model_validate(result["normal_trade_plan"])
            attempt_metas = [
                ModelExecutionMeta.model_validate(item)
                for item in result.get("normal_model_attempts") or []
            ]
            if not attempt_metas:
                attempt_metas = [plan.model_meta]
            else:
                attempt_metas[-1] = plan.model_meta
        request_hash = plan.model_meta.input_hash or canonical_hash(
            {"context_hash": self.model_runtime_context_hash}
        )
        for meta in attempt_metas:
            await self.audit.record(
                analysis_id=context.analysis_id,
                snapshot_id=context.snapshot_id,
                context_hash=self.model_runtime_context_hash,
                run_mode=self.run_mode,
                automated_execution_allowed=self.automated_execution_allowed,
                role="NORMAL_TRADER",
                agent_name="normal_trader",
                profile=self.normal_profile,
                prompt=prompt,
                request_hash=request_hash,
                meta=meta,
                budget=budget,
            )
        return plan

    @staticmethod
    def render_top_input(
        *,
        context: DecisionContext,
        plan: NormalTradePlan,
        risk_policy_summary: dict[str, Any],
        research_results: list[dict[str, Any]],
        model_runtime_context_hash: str,
        top_prompt_version: str,
        top_prompt_template: str,
        structured_output_mode: str,
        run_mode: str,
    ) -> str:
        state = ProfiledDecisionModelRunner._base_state(
            context,
            attempt_number=1,
            trace_id=None,
            research_results=research_results,
            model_runtime_context_hash=model_runtime_context_hash,
            run_mode=run_mode,
        )
        state["normal_trade_plan"] = plan.model_dump(mode="json")
        state["risk_policy_summary"] = risk_policy_summary
        request = build_top_review_model_request(
            context=context,
            normal_plan=plan,
            state=state,
            config={
                "top_prompt_version": top_prompt_version,
                "top_prompt_template": top_prompt_template,
            },
            prompt_version=top_prompt_version,
            instrument_context=build_instrument_context(context.symbol),
        )
        return render_structured_input_for_estimation(
            request.messages,
            schema=request.output_schema,
            structured_output_mode=structured_output_mode,
        )

    async def run_top(
        self,
        *,
        context: DecisionContext,
        plan: NormalTradePlan,
        risk_policy_summary: dict[str, Any],
        attempt_number: int,
        trace_id: str | None,
    ) -> TopReviewDecision:
        rendered = self.render_top_input(
            context=context,
            plan=plan,
            risk_policy_summary=risk_policy_summary,
            research_results=self.research_results,
            model_runtime_context_hash=self.model_runtime_context_hash,
            top_prompt_version=self.top_prompt.prompt_version,
            top_prompt_template=self.top_prompt.template,
            structured_output_mode=self.top_profile.structured_output_mode,
            run_mode=self.run_mode,
        )
        budget = await self._check_budget(self.top_profile, context, rendered)
        if not budget.allowed:
            meta = self._failure_meta(
                self.top_profile,
                self.top_prompt,
                context,
                attempt_number,
                budget.reason_code or "BUDGET_BLOCKED",
                self.model_runtime_context_hash,
            )
            review = TopReviewDecision(
                review_id=str(uuid4()),
                snapshot_id=context.snapshot_id,
                plan_id=plan.plan_id,
                analysis_id=context.analysis_id,
                decision_context_id=context.decision_context_id,
                quant_proposal_id=context.quant_proposal_id,
                symbol=context.symbol,
                market=context.market,
                trade_date=context.trade_date,
                strategy_id=context.strategy_id,
                strategy_version=context.strategy_version,
                revision_round=plan.revision_round,
                status="MODEL_FAILED",
                completeness_score=0,
                logic_consistency_score=0,
                risk_control_score=0,
                missing_evidence=[],
                logical_conflicts=[],
                risk_findings=[],
                adjusted_plan=None,
                material_change_fields=[],
                review_reason="formal model runtime blocked",
                model_meta=meta,
            )
            attempt_metas = [review.model_meta]
        else:
            state = self._base_state(
                context,
                attempt_number=attempt_number,
                trace_id=trace_id,
                research_results=self.research_results,
                model_runtime_context_hash=self.model_runtime_context_hash,
                run_mode=self.run_mode,
            )
            state["model_max_retries"] = max(
                0, budget.permitted_attempts - 1
            )
            state["normal_trade_plan"] = plan.model_dump(mode="json")
            state["risk_policy_summary"] = risk_policy_summary
            result = self.top_node(state)
            review = TopReviewDecision.model_validate(
                result["top_review_decision"]
            )
            attempt_metas = [
                ModelExecutionMeta.model_validate(item)
                for item in result.get("top_model_attempts") or []
            ]
            if not attempt_metas:
                attempt_metas = [review.model_meta]
            else:
                attempt_metas[-1] = review.model_meta
        request_hash = review.model_meta.input_hash or canonical_hash(
            {"context_hash": self.model_runtime_context_hash}
        )
        for meta in attempt_metas:
            await self.audit.record(
                analysis_id=context.analysis_id,
                snapshot_id=context.snapshot_id,
                context_hash=self.model_runtime_context_hash,
                run_mode=self.run_mode,
                automated_execution_allowed=self.automated_execution_allowed,
                role="TOP_RISK_REVIEWER",
                agent_name="top_risk_reviewer",
                profile=self.top_profile,
                prompt=self.top_prompt,
                request_hash=request_hash,
                meta=meta,
                budget=budget,
            )
        return review
