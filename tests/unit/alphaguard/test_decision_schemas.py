from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from tradingagents.alphaguard.decision_schemas import (
    ModelExecutionMeta,
    NormalTradePlan,
    TopReviewDecision,
)


def meta(**overrides):
    now = datetime.now(timezone.utc)
    values = {
        "provider": "test-provider",
        "model_name": "test-model",
        "model_version": "test-model-v1",
        "prompt_name": "normal_trade_plan",
        "prompt_version": "normal_trade_plan_v1",
        "started_at": now,
        "finished_at": now,
        "latency_ms": 1,
        "execution_status": "SUCCESS",
    }
    values.update(overrides)
    return ModelExecutionMeta(**values)


def plan_data(action="BUY", status="PROPOSE_TRADE", **overrides):
    values = {
        "plan_id": "plan-1",
        "snapshot_id": "legacy-analysis:test-1",
        "quant_proposal_id": "legacy-quant:none",
        "status": status,
        "action": action,
        "confidence": 0.8,
        "thesis": "经验证的交易逻辑",
        "bullish_evidence": [],
        "bearish_evidence": [],
        "entry_zone": {"lower": 9.5, "upper": 10.5, "currency": "CNY"},
        "initial_position_pct": 0.1,
        "max_position_pct": 0.2,
        "add_conditions": [],
        "stop_conditions": [
            {"condition_id": "stop-1", "description": "跌破结构止损"}
        ],
        "reduce_conditions": [],
        "exit_conditions": [],
        "invalidation_conditions": [],
        "target_price": None,
        "valid_until": datetime.now(timezone.utc) + timedelta(days=5),
        "main_risks": [],
        "unresolved_questions": [],
        "model_meta": meta(),
        "entry_zone_not_required_reason": None,
        "valid_until_compatibility_reason": None,
    }
    values.update(overrides)
    return values


def passive_plan_data(status, action):
    return plan_data(
        status=status,
        action=action,
        confidence=0.4,
        entry_zone=None,
        initial_position_pct=None,
        max_position_pct=None,
        stop_conditions=[],
        valid_until=None,
    )


def review_data(status="CONFIRM", **overrides):
    values = {
        "review_id": "review-1",
        "snapshot_id": "legacy-analysis:test-1",
        "plan_id": "plan-1",
        "status": status,
        "completeness_score": 0.9,
        "logic_consistency_score": 0.8,
        "risk_control_score": 0.7,
        "missing_evidence": [],
        "logical_conflicts": [],
        "risk_findings": [],
        "adjusted_plan": None,
        "material_change_fields": [],
        "review_reason": "终审通过",
        "model_meta": meta(
            prompt_name="top_review_decision",
            prompt_version="top_review_decision_v1",
        ),
    }
    values.update(overrides)
    return values


@pytest.mark.parametrize("action", ["BUY", "SELL"])
def test_valid_propose_trade_actions(action):
    data = plan_data(action=action)
    if action == "SELL":
        data["entry_zone"] = None
    assert NormalTradePlan(**data).action == action


def test_valid_wait():
    assert NormalTradePlan(**passive_plan_data("WAIT", "WAIT")).status == "WAIT"


def test_valid_no_trade_none():
    plan = NormalTradePlan(**passive_plan_data("NO_TRADE", "NONE"))
    assert plan.action == "NONE"


def test_target_price_none_is_valid():
    assert NormalTradePlan(**plan_data(target_price=None)).target_price is None


def test_initial_position_cannot_exceed_max():
    with pytest.raises(ValidationError):
        NormalTradePlan(
            **plan_data(initial_position_pct=0.3, max_position_pct=0.2)
        )


@pytest.mark.parametrize("confidence", [-0.01, 1.01])
def test_confidence_range(confidence):
    with pytest.raises(ValidationError):
        NormalTradePlan(**plan_data(confidence=confidence))


def test_invalid_entry_range():
    with pytest.raises(ValidationError):
        NormalTradePlan(
            **plan_data(entry_zone={"lower": 11, "upper": 10, "currency": "CNY"})
        )


@pytest.mark.parametrize(
    ("status", "action", "execution_status"),
    [
        ("MODEL_FAILED", "HOLD", "MODEL_FAILED"),
        ("INVALID_OUTPUT", "BUY", "INVALID_OUTPUT"),
        ("PROPOSE_TRADE", "NONE", "SUCCESS"),
    ],
)
def test_invalid_status_action_pairs(status, action, execution_status):
    data = passive_plan_data(status, action)
    data["model_meta"] = meta(
        execution_status=execution_status,
        error_type="TEST_ERROR" if execution_status != "SUCCESS" else None,
        error_message="failure" if execution_status != "SUCCESS" else None,
    )
    with pytest.raises(ValidationError):
        NormalTradePlan(**data)


def test_risk_adjust_requires_adjusted_plan():
    with pytest.raises(ValidationError):
        TopReviewDecision(**review_data(status="RISK_ADJUST"))


def test_material_revision_requires_change_fields():
    adjusted = deepcopy(plan_data())
    with pytest.raises(ValidationError):
        TopReviewDecision(
            **review_data(
                status="MATERIAL_REVISION",
                adjusted_plan=adjusted,
                material_change_fields=[],
            )
        )


def test_valid_risk_adjust_and_material_revision():
    adjusted = deepcopy(plan_data())
    risk_adjust = TopReviewDecision(
        **review_data(status="RISK_ADJUST", adjusted_plan=adjusted)
    )
    material = TopReviewDecision(
        **review_data(
            status="MATERIAL_REVISION",
            adjusted_plan=adjusted,
            material_change_fields=["max_position_pct"],
        )
    )
    assert risk_adjust.adjusted_plan is not None
    assert material.material_change_fields == ["max_position_pct"]
