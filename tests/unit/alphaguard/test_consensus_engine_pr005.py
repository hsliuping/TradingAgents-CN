from datetime import datetime

import pytest

from app.services.alphaguard.consensus_engine import ConsensusEngine
from tests.unit.alphaguard.pr005_helpers import (
    make_context,
    make_plan,
    make_review,
)


def evaluate(plan_status="PROPOSE_TRADE", review_status="CONFIRM"):
    context = make_context()
    plan = make_plan(context, status=plan_status)
    review = make_review(context, plan, status=review_status)
    return ConsensusEngine().evaluate(
        context=context,
        plan=plan,
        review=review,
        now=datetime(2026, 7, 2),
    )


def test_propose_confirm_passes():
    decision = evaluate()
    assert decision.status == "CONSENSUS_PASS"
    assert decision.final_plan is not None


def test_legal_risk_adjust_passes_with_adjusted_plan():
    context = make_context()
    plan = make_plan(context)
    adjusted = plan.model_copy(
        update={
            "initial_position_pct": 0.03,
            "max_position_pct": 0.08,
            "confidence": 0.7,
        }
    )
    review = make_review(
        context, plan, status="RISK_ADJUST", adjusted_plan=adjusted
    )
    result = ConsensusEngine().evaluate(
        context=context, plan=plan, review=review, now=datetime(2026, 7, 2)
    )
    assert result.status == "CONSENSUS_PASS"
    assert result.final_plan.max_position_pct == 0.08


@pytest.mark.parametrize(
    "change",
    [
        {"max_position_pct": 0.11},
        {"valid_until": datetime(2031, 1, 1)},
        {"action": "SELL"},
    ],
)
def test_illegal_risk_adjust_is_invalid(change):
    context = make_context()
    plan = make_plan(context)
    adjusted = plan.model_copy(update=change)
    review = make_review(
        context, plan, status="RISK_ADJUST", adjusted_plan=adjusted
    )
    result = ConsensusEngine().evaluate(
        context=context, plan=plan, review=review, now=datetime(2026, 7, 2)
    )
    assert result.status == "CONSENSUS_INVALID"
    assert result.validation_errors


def test_first_material_revision_revises_and_second_rejects():
    context = make_context()
    first = make_plan(context)
    review = make_review(
        context,
        first,
        status="MATERIAL_REVISION",
        adjusted_plan=first,
    )
    result = ConsensusEngine().evaluate(
        context=context, plan=first, review=review, now=datetime(2026, 7, 2)
    )
    assert result.status == "CONSENSUS_REVISE"
    assert result.requires_normal_reconfirm is True

    revised = make_plan(
        context,
        revision_round=1,
        original_plan=first,
        revision_request_id="request-1",
    )
    second = make_review(
        context,
        revised,
        status="MATERIAL_REVISION",
        adjusted_plan=revised,
    )
    result = ConsensusEngine().evaluate(
        context=context, plan=revised, review=second, now=datetime(2026, 7, 2)
    )
    assert result.status == "CONSENSUS_REJECT"


@pytest.mark.parametrize("status", ["NO_TRADE", "WAIT", "INSUFFICIENT_DATA"])
def test_normal_business_stop_is_reject_not_system_failure(status):
    result = evaluate(plan_status=status, review_status="REJECT")
    assert result.status == "CONSENSUS_REJECT"
    assert result.validation_errors == []


@pytest.mark.parametrize("status", ["MODEL_FAILED", "INVALID_OUTPUT"])
def test_normal_failure_is_consensus_invalid(status):
    context = make_context()
    plan = make_plan(context, status=status)
    meta = plan.model_meta.model_copy(
        update={
            "execution_status": status,
            "error_type": "FIXED_ERROR",
            "error_message": "fixed",
        }
    )
    plan = plan.model_copy(update={"model_meta": meta})
    review = make_review(context, plan, status="SUSPEND")
    result = ConsensusEngine().evaluate(
        context=context, plan=plan, review=review, now=datetime(2026, 7, 2)
    )
    assert result.status == "CONSENSUS_INVALID"


@pytest.mark.parametrize("review_status", ["REJECT", "SUSPEND"])
def test_top_reject_or_suspend_never_passes(review_status):
    result = evaluate(review_status=review_status)
    assert result.status == "CONSENSUS_REJECT"


def test_identity_mismatch_and_expired_plan_are_invalid():
    context = make_context()
    plan = make_plan(context)
    review = make_review(context, plan)
    bad_review = review.model_copy(update={"quant_proposal_id": "other"})
    result = ConsensusEngine().evaluate(
        context=context,
        plan=plan,
        review=bad_review,
        now=datetime(2026, 7, 2),
    )
    assert result.status == "CONSENSUS_INVALID"
    expired = plan.model_copy(update={"valid_until": datetime(2026, 7, 1)})
    review = make_review(context, expired)
    result = ConsensusEngine().evaluate(
        context=context,
        plan=expired,
        review=review,
        now=datetime(2026, 7, 2),
    )
    assert result.status == "CONSENSUS_INVALID"
