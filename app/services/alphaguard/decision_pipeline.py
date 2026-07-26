"""Unified PR-005 orchestration ending at RiskDecision, never at an order."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable
from uuid import uuid4

from app.schemas.alphaguard.decision import (
    DECISION_PIPELINE_VERSION,
    ConsensusDecision,
    DecisionPipelineResult,
    RiskDecision,
    RiskRuleResult,
    canonical_hash,
)
from tradingagents.alphaguard.candidate_schemas import CandidateStatus
from tradingagents.alphaguard.decision_schemas import (
    ModelExecutionMeta,
    NormalTradePlan,
    TopReviewDecision,
)

from .candidate_pool_service import CandidatePoolService
from .consensus_engine import ConsensusEngine
from .decision_audit_service import DecisionAuditService
from .decision_context_builder import (
    DecisionContextBuilder,
    DecisionContextError,
    ProposalNotEligibleError,
)
from .decision_model_runner import (
    DecisionModelRunner,
    ExistingProviderDecisionModelRunner,
)
from .hard_risk_engine import HardRiskEngine
from .revision_service import RevisionService
from .risk_policy_registry import RiskPolicyRegistry


class DecisionIntegrityError(ValueError):
    pass


def decision_run_key(
    *,
    user_id: str,
    snapshot_id: str,
    quant_proposal_id: str,
    account_id: str | None,
) -> str:
    return canonical_hash(
        {
            "user_id": str(user_id),
            "snapshot_id": snapshot_id,
            "quant_proposal_id": quant_proposal_id,
            "account_id": account_id,
            "decision_pipeline_version": DECISION_PIPELINE_VERSION,
        }
    )


def _now_meta(
    *,
    context_hash: str,
    attempt_number: int,
    error_message: str,
    trace_id: str | None,
) -> ModelExecutionMeta:
    now = datetime.now(timezone.utc)
    return ModelExecutionMeta(
        provider="unavailable",
        model_name="unconfigured",
        model_version="unconfigured",
        prompt_name="normal_trade_plan",
        prompt_version="normal_trade_plan_quant_v1",
        started_at=now,
        finished_at=now,
        latency_ms=0,
        execution_status="MODEL_FAILED",
        trace_id=trace_id,
        error_type="PROMPT_CONFIGURATION_ERROR",
        error_message=error_message[:500],
        template_hash=canonical_hash("normal_trade_plan_quant_v1"),
        context_hash=context_hash,
        input_hash=canonical_hash({"context_hash": context_hash}),
        attempt_number=attempt_number,
    )


def _model_configuration_failure(
    context,
    *,
    attempt_number: int,
    error_message: str,
    trace_id: str | None,
) -> NormalTradePlan:
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
        status="MODEL_FAILED",
        action="NONE",
        confidence=0,
        thesis="normal model could not be configured",
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
        model_meta=_now_meta(
            context_hash=context.context_hash,
            attempt_number=attempt_number,
            error_message=error_message,
            trace_id=trace_id,
        ),
    )


class DecisionPipeline:
    def __init__(
        self,
        db,
        *,
        model_runner: DecisionModelRunner | None = None,
        clock: Callable[[], datetime] | None = None,
    ):
        self.db = db
        self.model_runner = model_runner
        self.clock = clock or datetime.utcnow
        self.context_builder = DecisionContextBuilder(db)
        self.consensus = ConsensusEngine()
        self.hard_risk = HardRiskEngine()
        self.revisions = RevisionService(db)
        self.policies = RiskPolicyRegistry(db)
        self.candidates = CandidatePoolService(db=db)

    async def _save_plan(self, context, plan: NormalTradePlan) -> None:
        await self.db["analysis_reports"].update_one(
            {"analysis_id": context.analysis_id},
            {
                "$setOnInsert": {
                    "analysis_id": context.analysis_id,
                    "user_id": context.user_id,
                    "stock_symbol": context.symbol,
                    "analysis_date": context.trade_date,
                    "created_at": datetime.utcnow(),
                    "status": "alphaguard_decision",
                },
                "$set": {
                    "normal_trade_plan": plan.model_dump(mode="python"),
                    "snapshot_id": context.snapshot_id,
                    "decision_context_id": context.decision_context_id,
                    "updated_at": datetime.utcnow(),
                    "automated_execution_allowed": False,
                },
                "$push": {
                    "normal_trade_plan_history": plan.model_dump(mode="python")
                },
            },
            upsert=True,
        )

    async def _save_review(self, context, review: TopReviewDecision) -> None:
        await self.db["analysis_reports"].update_one(
            {"analysis_id": context.analysis_id},
            {
                "$set": {
                    "top_review_decision": review.model_dump(mode="python"),
                    "updated_at": datetime.utcnow(),
                },
                "$push": {
                    "top_review_history": review.model_dump(mode="python")
                },
            },
        )

    async def _transition(
        self,
        context,
        target: CandidateStatus,
        reason: str,
        trace_id: str | None,
    ) -> None:
        if not context.candidate_id:
            return
        candidate = await self.candidates.get_candidate(
            context.candidate_id, context.user_id
        )
        if candidate is None or candidate.status == target:
            return
        await self.candidates.transition_status(
            context.candidate_id,
            context.user_id,
            target,
            reason=reason,
            trace_id=trace_id,
        )

    async def _persist_run(
        self,
        *,
        run_key: str,
        proposal_input_hash: str,
        result: DecisionPipelineResult,
    ) -> None:
        await self.db["ag_decision_runs"].update_one(
            {
                "decision_run_key": run_key,
                "attempt_number": result.attempt_number,
            },
            {
                "$setOnInsert": {
                    "decision_run_key": run_key,
                    "attempt_number": result.attempt_number,
                    "proposal_input_hash": proposal_input_hash,
                    "created_at": datetime.utcnow(),
                },
                "$set": {
                    "terminal": True,
                    "terminal_status": result.terminal_status,
                    "result": result.model_dump(mode="python"),
                    "updated_at": datetime.utcnow(),
                    "order_intent_created": False,
                },
            },
            upsert=True,
        )

    async def evaluate_quant_proposal(
        self,
        quant_proposal_id: str,
        *,
        user_id: str,
        account_id: str | None = None,
        trace_id: str | None = None,
        retry_failed: bool = False,
    ) -> DecisionPipelineResult:
        proposal_doc = await self.db["ag_quant_proposals"].find_one(
            {"proposal_id": quant_proposal_id, "user_id": str(user_id)}
        )
        if proposal_doc is None:
            raise LookupError("QuantTradeProposal not found")
        run_key = decision_run_key(
            user_id=str(user_id),
            snapshot_id=str(proposal_doc["snapshot_id"]),
            quant_proposal_id=quant_proposal_id,
            account_id=account_id,
        )
        runs = await self.db["ag_decision_runs"].find(
            {"decision_run_key": run_key}
        ).sort("attempt_number", -1).to_list(length=None)
        audit = DecisionAuditService(self.db)
        if runs:
            latest = runs[0]
            if latest.get("proposal_input_hash") != proposal_doc.get("input_hash"):
                previous = DecisionPipelineResult.model_validate(latest["result"])
                previous_context = previous.decision_context
                if previous_context is not None:
                    await audit.record(
                        "DECISION_INTEGRITY_CONFLICT",
                        context=previous_context,
                        reason="same decision_run_key has conflicting proposal content",
                        attempt_number=int(latest.get("attempt_number") or 1),
                        trace_id=trace_id,
                    )
                raise DecisionIntegrityError(
                    "same decision_run_key has conflicting proposal content"
                )
            terminal_status = str(latest.get("terminal_status") or "")
            retryable = terminal_status in {
                "NORMAL_MODEL_FAILED",
                "TOP_MODEL_FAILED",
                "CONSENSUS_INVALID",
            }
            if not (retry_failed and retryable):
                result = DecisionPipelineResult.model_validate(latest["result"])
                if result.decision_context is not None:
                    await audit.record(
                        "DECISION_RUN_REUSED",
                        context=result.decision_context,
                        reason="terminal decision_run_key result reused",
                        plan_id=(
                            result.normal_trade_plan.plan_id
                            if result.normal_trade_plan
                            else None
                        ),
                        review_id=(
                            result.top_review_decision.review_id
                            if result.top_review_decision
                            else None
                        ),
                        consensus_id=(
                            result.consensus_decision.consensus_id
                            if result.consensus_decision
                            else None
                        ),
                        risk_decision_id=(
                            result.risk_decision.risk_decision_id
                            if result.risk_decision
                            else None
                        ),
                        revision_round=(
                            result.normal_trade_plan.revision_round
                            if result.normal_trade_plan
                            else 0
                        ),
                        attempt_number=result.attempt_number,
                        trace_id=trace_id,
                    )
                return result.model_copy(update={"reused": True})
        attempt_number = 1 + max(
            (int(item.get("attempt_number") or 0) for item in runs), default=0
        )

        try:
            context, resolved = await self.context_builder.build(
                quant_proposal_id, user_id=str(user_id)
            )
        except ProposalNotEligibleError as exc:
            result = DecisionPipelineResult(
                analysis_id=(
                    proposal_doc.get("analysis_id")
                    or f"ag-analysis:{quant_proposal_id}"
                ),
                decision_run_key=run_key,
                attempt_number=attempt_number,
                terminal_status="PROPOSAL_NOT_ELIGIBLE",
            )
            await self._persist_run(
                run_key=run_key,
                proposal_input_hash=proposal_doc["input_hash"],
                result=result,
            )
            return result
        except DecisionContextError as exc:
            await audit.record_identity(
                "DECISION_CONTEXT_INVALID",
                analysis_id=(
                    proposal_doc.get("analysis_id")
                    or f"ag-analysis:{quant_proposal_id}"
                ),
                user_id=str(user_id),
                candidate_id=proposal_doc.get("candidate_id"),
                snapshot_id=str(proposal_doc["snapshot_id"]),
                quant_proposal_id=quant_proposal_id,
                reason=str(exc),
                attempt_number=attempt_number,
                trace_id=trace_id,
            )
            raise

        await audit.record(
            "DECISION_CONTEXT_CREATED",
            context=context,
            reason="immutable DecisionContext created or reused",
            attempt_number=attempt_number,
            trace_id=trace_id,
        )
        if attempt_number > 1 and context.candidate_id:
            candidate = await self.candidates.get_candidate(
                context.candidate_id, context.user_id
            )
            if candidate and candidate.status == CandidateStatus.COOLDOWN:
                await self._transition(
                    context,
                    CandidateStatus.SIGNAL_DETECTED,
                    "explicit failed decision retry",
                    trace_id,
                )
        await self._transition(
            context,
            CandidateStatus.AI_ANALYZING,
            "PR-005 decision evaluation started",
            trace_id,
        )

        runner = self.model_runner
        await audit.record(
            "NORMAL_MODEL_STARTED",
            context=context,
            reason="normal model invocation started",
            attempt_number=attempt_number,
            trace_id=trace_id,
        )
        if runner is None:
            try:
                runner = await ExistingProviderDecisionModelRunner.create(context)
            except Exception as exc:
                plan = _model_configuration_failure(
                    context,
                    attempt_number=attempt_number,
                    error_message=f"model configuration failed: {type(exc).__name__}",
                    trace_id=trace_id,
                )
            else:
                plan = await runner.run_normal(
                    context=context,
                    attempt_number=attempt_number,
                    trace_id=trace_id,
                )
        else:
            plan = await runner.run_normal(
                context=context,
                attempt_number=attempt_number,
                trace_id=trace_id,
            )
        await self._save_plan(context, plan)
        await audit.record(
            "NORMAL_MODEL_COMPLETED"
            if plan.status not in {"MODEL_FAILED", "INVALID_OUTPUT"}
            else "NORMAL_MODEL_FAILED",
            context=context,
            plan_id=plan.plan_id,
            reason=f"normal model status={plan.status}",
            attempt_number=attempt_number,
            trace_id=trace_id,
        )
        if plan.status != "PROPOSE_TRADE":
            await audit.record(
                "NORMAL_PLAN_REJECTED",
                context=context,
                plan_id=plan.plan_id,
                reason=f"normal plan is not eligible for top review: {plan.status}",
                attempt_number=attempt_number,
                trace_id=trace_id,
            )
            target = (
                CandidateStatus.COOLDOWN
                if plan.status
                in {"WAIT", "INSUFFICIENT_DATA", "MODEL_FAILED", "INVALID_OUTPUT"}
                else CandidateStatus.REJECTED
            )
            await self._transition(
                context, target, f"normal model ended with {plan.status}", trace_id
            )
            terminal = (
                "NORMAL_MODEL_FAILED"
                if plan.status in {"MODEL_FAILED", "INVALID_OUTPUT"}
                else f"NORMAL_{plan.status}"
            )
            result = DecisionPipelineResult(
                analysis_id=context.analysis_id,
                decision_run_key=run_key,
                attempt_number=attempt_number,
                terminal_status=terminal,
                decision_context=context,
                normal_trade_plan=plan,
            )
            await self._persist_run(
                run_key=run_key,
                proposal_input_hash=proposal_doc["input_hash"],
                result=result,
            )
            return result

        await self._transition(
            context, CandidateStatus.PLAN_PROPOSED, "normal plan proposed", trace_id
        )
        await self._transition(
            context, CandidateStatus.TOP_REVIEWING, "top review started", trace_id
        )
        try:
            policy = await self.policies.get_active()
            policy_summary = policy.model_dump(
                mode="json",
                exclude={"created_at", "config_hash"},
            )
        except (LookupError, ValueError):
            policy = None
            policy_summary = {"risk_policy_id": "missing", "status": "MISSING"}

        assert runner is not None
        await audit.record(
            "TOP_REVIEW_STARTED",
            context=context,
            plan_id=plan.plan_id,
            reason="top review invocation started",
            revision_round=plan.revision_round,
            attempt_number=attempt_number,
            trace_id=trace_id,
        )
        review = await runner.run_top(
            context=context,
            plan=plan,
            risk_policy_summary=policy_summary,
            attempt_number=attempt_number,
            trace_id=trace_id,
        )
        await self._save_review(context, review)
        await audit.record(
            "TOP_REVIEW_COMPLETED"
            if review.status not in {"MODEL_FAILED", "INVALID_OUTPUT"}
            else "TOP_REVIEW_FAILED",
            context=context,
            plan_id=plan.plan_id,
            review_id=review.review_id,
            reason=f"top review status={review.status}",
            revision_round=plan.revision_round,
            attempt_number=attempt_number,
            trace_id=trace_id,
        )
        consensus = self.consensus.evaluate(
            context=context,
            plan=plan,
            review=review,
            now=self.clock(),
        )
        revision_request = None

        if consensus.status == "CONSENSUS_REVISE":
            revision_request = await self.revisions.create(
                analysis_id=context.analysis_id,
                plan=plan,
                review=review,
            )
            await audit.record(
                "MATERIAL_REVISION_REQUESTED",
                context=context,
                plan_id=plan.plan_id,
                review_id=review.review_id,
                reason="single material revision requested",
                revision_round=1,
                attempt_number=attempt_number,
                trace_id=trace_id,
            )
            revised = await runner.run_normal(
                context=context,
                attempt_number=attempt_number,
                trace_id=trace_id,
                revision_request=revision_request,
                original_plan=plan,
            )
            await self._save_plan(context, revised)
            await audit.record(
                "NORMAL_REVISION_COMPLETED",
                context=context,
                plan_id=revised.plan_id,
                review_id=review.review_id,
                reason=f"normal revision status={revised.status}",
                revision_round=1,
                attempt_number=attempt_number,
                trace_id=trace_id,
            )
            if revised.status == "PROPOSE_TRADE":
                await audit.record(
                    "TOP_REVIEW_STARTED",
                    context=context,
                    plan_id=revised.plan_id,
                    reason="second and final top review invocation started",
                    revision_round=1,
                    attempt_number=attempt_number,
                    trace_id=trace_id,
                )
                second_review = await runner.run_top(
                    context=context,
                    plan=revised,
                    risk_policy_summary=policy_summary,
                    attempt_number=attempt_number,
                    trace_id=trace_id,
                )
                await self._save_review(context, second_review)
                consensus = self.consensus.evaluate(
                    context=context,
                    plan=revised,
                    review=second_review,
                    now=self.clock(),
                )
                plan, review = revised, second_review
                await audit.record(
                    "TOP_REVIEW_COMPLETED"
                    if second_review.status
                    not in {"MODEL_FAILED", "INVALID_OUTPUT"}
                    else "TOP_REVIEW_FAILED",
                    context=context,
                    plan_id=revised.plan_id,
                    review_id=second_review.review_id,
                    reason=f"top review status={second_review.status}",
                    revision_round=1,
                    attempt_number=attempt_number,
                    trace_id=trace_id,
                )
                if second_review.status == "MATERIAL_REVISION":
                    await audit.record(
                        "REVISION_LIMIT_REACHED",
                        context=context,
                        plan_id=revised.plan_id,
                        review_id=second_review.review_id,
                        reason="second MATERIAL_REVISION rejected",
                        revision_round=1,
                        attempt_number=attempt_number,
                        trace_id=trace_id,
                    )
            else:
                # No second top call is needed for a normal-model business stop.
                consensus = ConsensusDecision(
                    consensus_id=str(uuid4()),
                    analysis_id=context.analysis_id,
                    snapshot_id=context.snapshot_id,
                    quant_proposal_id=context.quant_proposal_id,
                    plan_id=revised.plan_id,
                    review_id=review.review_id,
                    status=(
                        "CONSENSUS_INVALID"
                        if revised.status in {"MODEL_FAILED", "INVALID_OUTPUT"}
                        else "CONSENSUS_REJECT"
                    ),
                    final_plan=None,
                    final_plan_hash=None,
                    revision_round=1,
                    requires_normal_reconfirm=False,
                    reasons=[f"revision ended with {revised.status}"],
                    validation_errors=[],
                    created_at=datetime.utcnow(),
                )
                plan = revised

        await self.db["ag_consensus_decisions"].update_one(
            {"consensus_id": consensus.consensus_id},
            {"$setOnInsert": consensus.model_dump(mode="python")},
            upsert=True,
        )
        await audit.record(
            consensus.status.replace("CONSENSUS_", "CONSENSUS_"),
            context=context,
            plan_id=plan.plan_id,
            review_id=review.review_id,
            consensus_id=consensus.consensus_id,
            reason="; ".join(consensus.reasons) or consensus.status,
            revision_round=plan.revision_round,
            attempt_number=attempt_number,
            trace_id=trace_id,
        )

        risk_decision = None
        if consensus.status == "CONSENSUS_PASS":
            await audit.record(
                "HARD_RISK_STARTED",
                context=context,
                plan_id=plan.plan_id,
                review_id=review.review_id,
                consensus_id=consensus.consensus_id,
                reason="pure-Python hard-risk evaluation started",
                revision_round=plan.revision_round,
                attempt_number=attempt_number,
                trace_id=trace_id,
            )
            if policy is None:
                rule = RiskRuleResult(
                    rule_id="AG-RISK-POLICY",
                    rule_version="1.0.0",
                    status="SUSPEND",
                    observed_value=None,
                    threshold_value="registered active risk-policy-v1",
                    evidence_refs=[],
                    reason="active RiskPolicy is missing",
                    evaluated_at=datetime.utcnow(),
                )
                risk_decision = RiskDecision(
                    risk_decision_id=str(uuid4()),
                    analysis_id=context.analysis_id,
                    consensus_id=consensus.consensus_id,
                    snapshot_id=context.snapshot_id,
                    quant_proposal_id=context.quant_proposal_id,
                    account_id=account_id,
                    status="SUSPEND",
                    action=consensus.final_plan.action,
                    original_position_pct=consensus.final_plan.max_position_pct,
                    approved_position_pct=None,
                    original_quantity=None,
                    approved_quantity=None,
                    pricing_reference=None,
                    earliest_eligible_execute_at=None,
                    requires_execution_recheck=True,
                    triggered_rules=[rule],
                    reasons=["active RiskPolicy is missing"],
                    risk_policy_version="missing",
                    input_hash=canonical_hash(
                        {
                            "context": context.context_hash,
                            "consensus": consensus.consensus_id,
                            "policy": None,
                        }
                    ),
                    created_at=datetime.utcnow(),
                    order_intent_created=False,
                )
            else:
                risk_decision = self.hard_risk.evaluate(
                    data=resolved,
                    context=context,
                    consensus=consensus,
                    policy=policy,
                    account_id=account_id,
                    now=self.clock(),
                )
            await self.db["ag_risk_decisions"].update_one(
                {"risk_decision_id": risk_decision.risk_decision_id},
                {"$setOnInsert": risk_decision.model_dump(mode="python")},
                upsert=True,
            )
            await audit.record(
                f"HARD_RISK_{risk_decision.status}",
                context=context,
                plan_id=plan.plan_id,
                review_id=review.review_id,
                consensus_id=consensus.consensus_id,
                risk_decision_id=risk_decision.risk_decision_id,
                reason="; ".join(risk_decision.reasons),
                revision_round=plan.revision_round,
                attempt_number=attempt_number,
                trace_id=trace_id,
            )
            target = (
                CandidateStatus.APPROVED
                if risk_decision.status in {"PASS", "REDUCE"}
                else (
                    CandidateStatus.REJECTED
                    if risk_decision.status == "REJECT"
                    else CandidateStatus.RISK_ALERT
                )
            )
            await self._transition(
                context, target, f"HardRisk {risk_decision.status}", trace_id
            )
        else:
            target = (
                CandidateStatus.RISK_ALERT
                if consensus.status == "CONSENSUS_INVALID"
                else CandidateStatus.REJECTED
            )
            await self._transition(
                context, target, consensus.status, trace_id
            )

        terminal = (
            f"RISK_{risk_decision.status}"
            if risk_decision
            else consensus.status
        )
        result = DecisionPipelineResult(
            analysis_id=context.analysis_id,
            decision_run_key=run_key,
            attempt_number=attempt_number,
            terminal_status=terminal,
            decision_context=context,
            normal_trade_plan=plan,
            top_review_decision=review,
            revision_request=revision_request,
            consensus_decision=consensus,
            risk_decision=risk_decision,
            order_intent_created=False,
        )
        await self._persist_run(
            run_key=run_key,
            proposal_input_hash=proposal_doc["input_hash"],
            result=result,
        )
        return result
