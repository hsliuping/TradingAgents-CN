"""Deterministic dual-model consensus; this module never calls an LLM."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5

from app.schemas.alphaguard.decision import (
    ConsensusDecision,
    DecisionContext,
    canonical_hash,
)
from tradingagents.alphaguard.decision_schemas import (
    NormalTradePlan,
    TopReviewDecision,
)

from .decision_validation import (
    validate_plan_against_context,
    validate_review_against_context,
    validate_risk_adjustment,
)


def _expired(value: datetime | None, now: datetime) -> bool:
    if value is None:
        return False
    left = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    right = now.replace(tzinfo=timezone.utc) if now.tzinfo is None else now
    return left < right


class ConsensusEngine:
    policy_version = "consensus-policy-v1"

    def evaluate(
        self,
        *,
        context: DecisionContext,
        plan: NormalTradePlan,
        review: TopReviewDecision,
        now: datetime | None = None,
    ) -> ConsensusDecision:
        now = now or datetime.utcnow()
        errors: list[str] = []
        reasons: list[str] = []
        runtime_context_hash = plan.model_meta.context_hash
        try:
            validate_plan_against_context(
                plan,
                context,
                model_runtime_context_hash=runtime_context_hash,
            )
        except ValueError as exc:
            errors.append(str(exc))
        try:
            validate_review_against_context(
                review,
                plan,
                context,
                model_runtime_context_hash=runtime_context_hash,
            )
        except ValueError as exc:
            errors.append(str(exc))
        if context.quant_proposal.status != "TRIGGERED":
            errors.append("QuantTradeProposal is not TRIGGERED")
        if context.quant_proposal.action_candidate not in {"BUY", "SELL", "REDUCE"}:
            errors.append("QuantTradeProposal action is not tradable")
        if _expired(context.quant_proposal.valid_until, now):
            errors.append("QuantTradeProposal is expired")
        if _expired(plan.valid_until, now):
            errors.append("NormalTradePlan is expired")
        if plan.revision_round not in {0, 1}:
            errors.append("revision_round is invalid")

        status = "CONSENSUS_REJECT"
        final_plan = None
        requires_reconfirm = False
        if errors:
            status = "CONSENSUS_INVALID"
            reasons.append("identity, evidence, hash, expiry, or schema validation failed")
        elif plan.status in {"MODEL_FAILED", "INVALID_OUTPUT"} or review.status in {
            "MODEL_FAILED",
            "INVALID_OUTPUT",
        }:
            status = "CONSENSUS_INVALID"
            reasons.append("a required model execution failed or returned invalid output")
        elif plan.status in {"NO_TRADE", "WAIT", "INSUFFICIENT_DATA"}:
            status = "CONSENSUS_REJECT"
            reasons.append(f"normal model business outcome is {plan.status}")
        elif plan.status != "PROPOSE_TRADE":
            status = "CONSENSUS_INVALID"
            errors.append(f"unsupported normal plan status: {plan.status}")
        elif review.status == "CONFIRM":
            status = "CONSENSUS_PASS"
            final_plan = plan
            reasons.append("top review confirmed the normal plan")
        elif review.status == "RISK_ADJUST":
            assert review.adjusted_plan is not None
            adjustment_errors = validate_risk_adjustment(
                plan, review.adjusted_plan
            )
            if adjustment_errors:
                status = "CONSENSUS_INVALID"
                errors.extend(adjustment_errors)
                reasons.append("RISK_ADJUST exceeded the risk-only whitelist")
            else:
                status = "CONSENSUS_PASS"
                final_plan = review.adjusted_plan
                reasons.append("verified risk-only adjustment accepted")
        elif review.status == "MATERIAL_REVISION":
            if plan.revision_round == 0:
                status = "CONSENSUS_REVISE"
                requires_reconfirm = True
                reasons.append("one normal-model revision is required")
            else:
                status = "CONSENSUS_REJECT"
                reasons.append("material revision limit reached")
        elif review.status in {"REJECT", "SUSPEND"}:
            status = "CONSENSUS_REJECT"
            reasons.append(f"top review outcome is {review.status}")
        else:
            status = "CONSENSUS_INVALID"
            errors.append(f"unsupported top review status: {review.status}")

        identity = (
            f"{context.analysis_id}:{plan.plan_id}:{review.review_id}:"
            f"{status}:{plan.revision_round}"
        )
        return ConsensusDecision(
            consensus_id=str(uuid5(NAMESPACE_URL, identity)),
            analysis_id=context.analysis_id,
            snapshot_id=context.snapshot_id,
            quant_proposal_id=context.quant_proposal_id,
            plan_id=plan.plan_id,
            review_id=review.review_id,
            status=status,
            final_plan=final_plan,
            final_plan_hash=canonical_hash(final_plan) if final_plan else None,
            revision_round=plan.revision_round,
            requires_normal_reconfirm=requires_reconfirm,
            reasons=reasons,
            validation_errors=errors,
            consensus_policy_version=self.policy_version,
            created_at=now,
        )
