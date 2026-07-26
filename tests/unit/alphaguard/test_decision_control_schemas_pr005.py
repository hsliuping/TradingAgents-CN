from datetime import datetime

import pytest
from pydantic import ValidationError

from app.schemas.alphaguard.decision import (
    ConsensusDecision,
    RiskDecision,
    canonical_hash,
)
from app.services.alphaguard.decision_validation import (
    validate_plan_against_context,
    validate_risk_adjustment,
)
from tests.unit.alphaguard.pr005_helpers import (
    make_context,
    make_plan,
    make_review,
)


def test_context_hash_is_stable_and_tampering_is_rejected():
    first = make_context()
    second = make_context()
    assert first.context_hash == second.context_hash
    with pytest.raises(ValidationError):
        first.model_copy(update={"symbol": "000001"}).__class__.model_validate(
            {**first.model_dump(mode="python"), "symbol": "000001"}
        )


@pytest.mark.parametrize("action", ["BUY", "SELL", "REDUCE"])
def test_quant_bound_plan_allows_only_proposal_direction(action):
    context = make_context(action)
    plan = make_plan(context)
    validate_plan_against_context(plan, context)
    opposite = "SELL" if action == "BUY" else "BUY"
    invalid = plan.model_copy(update={"action": opposite})
    with pytest.raises(ValueError, match="reverse"):
        validate_plan_against_context(invalid, context)


def test_plan_cannot_exceed_quant_position_or_escape_evidence():
    context = make_context()
    plan = make_plan(context)
    with pytest.raises(ValueError, match="position"):
        validate_plan_against_context(
            plan.model_copy(update={"max_position_pct": 0.11}), context
        )
    bad_ref = plan.bullish_evidence[0].model_copy(
        update={"evidence_id": "outside:latest"}
    )
    with pytest.raises(ValueError, match="outside"):
        validate_plan_against_context(
            plan.model_copy(update={"bullish_evidence": [bad_ref]}), context
        )


def test_target_price_none_remains_valid_in_quant_mode():
    context = make_context()
    plan = make_plan(context)
    assert plan.target_price is None
    validate_plan_against_context(plan, context)


def test_round_one_requires_explicit_lineage():
    context = make_context()
    original = make_plan(context)
    revised = make_plan(
        context,
        revision_round=1,
        original_plan=original,
        revision_request_id="revision-1",
    )
    validate_plan_against_context(
        revised,
        context,
        original_plan=original,
        revision_request_id="revision-1",
    )
    with pytest.raises(ValueError, match="lineage"):
        validate_plan_against_context(
            revised,
            context,
            original_plan=original,
            revision_request_id="different",
        )


def test_risk_adjustment_whitelist_accepts_only_reduction_and_append():
    context = make_context()
    plan = make_plan(context)
    adjusted = plan.model_copy(
        update={
            "initial_position_pct": 0.03,
            "max_position_pct": 0.08,
            "confidence": 0.7,
            "entry_zone": plan.entry_zone.model_copy(
                update={"lower": 99.5, "upper": 100.5}
            ),
            "valid_until": datetime(2030, 7, 2),
        }
    )
    assert validate_risk_adjustment(plan, adjusted) == []
    assert validate_risk_adjustment(
        plan, adjusted.model_copy(update={"max_position_pct": 0.11})
    )
    assert validate_risk_adjustment(
        plan,
        adjusted.model_copy(
            update={
                "entry_zone": plan.entry_zone.model_copy(
                    update={"lower": 98, "upper": 102}
                )
            }
        ),
    )
    assert validate_risk_adjustment(
        plan, adjusted.model_copy(update={"action": "SELL"})
    )


def test_consensus_and_risk_schema_enforce_non_executable_contracts():
    context = make_context()
    plan = make_plan(context)
    review = make_review(context, plan)
    decision = ConsensusDecision(
        consensus_id="consensus",
        analysis_id=context.analysis_id,
        snapshot_id=context.snapshot_id,
        quant_proposal_id=context.quant_proposal_id,
        plan_id=plan.plan_id,
        review_id=review.review_id,
        status="CONSENSUS_PASS",
        final_plan=plan,
        final_plan_hash=canonical_hash(plan),
        revision_round=0,
        requires_normal_reconfirm=False,
        reasons=["confirmed"],
        validation_errors=[],
        created_at=datetime(2026, 7, 1),
    )
    assert decision.status == "CONSENSUS_PASS"
    with pytest.raises(ValidationError):
        RiskDecision(
            risk_decision_id="risk",
            analysis_id=context.analysis_id,
            consensus_id=decision.consensus_id,
            snapshot_id=context.snapshot_id,
            quant_proposal_id=context.quant_proposal_id,
            account_id=None,
            status="PASS",
            action="BUY",
            original_position_pct=0.1,
            approved_position_pct=0.1,
            original_quantity=None,
            approved_quantity=100,
            pricing_reference=100,
            earliest_eligible_execute_at=None,
            requires_execution_recheck=True,
            triggered_rules=[],
            reasons=["pass"],
            risk_policy_version="v1",
            input_hash="0" * 64,
            created_at=datetime(2026, 7, 1),
            order_intent_created=True,
        )
