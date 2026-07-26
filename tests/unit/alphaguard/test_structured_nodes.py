from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json

import pytest

from tradingagents.agents.managers.risk_manager import create_risk_manager
from tradingagents.agents.trader.trader import create_trader
from tradingagents.alphaguard.decision_schemas import (
    ModelExecutionMeta,
    NormalTradePlan,
)


class FakeResponse:
    def __init__(self, content):
        self.content = content
        self.response_metadata = {"request_id": "request-test-1"}


class FakeLLM:
    model_name = "fake-model-v1"

    def __init__(self, payload=None, *, content=None, error=None):
        self.payload = payload
        self.content = content
        self.error = error
        self.calls = 0

    def invoke(self, messages):
        self.calls += 1
        if self.error:
            raise self.error
        if self.content is not None:
            return FakeResponse(self.content)
        return FakeResponse(json.dumps(self.payload, ensure_ascii=False))


def plan_payload(status="PROPOSE_TRADE", action="BUY", **overrides):
    values = {
        "status": status,
        "action": action,
        "confidence": 0.8,
        "thesis": "结构化交易逻辑",
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
        "valid_until": (
            datetime.now(timezone.utc) + timedelta(days=5)
        ).isoformat(),
        "main_risks": [],
        "unresolved_questions": [],
        "entry_zone_not_required_reason": None,
        "valid_until_compatibility_reason": None,
    }
    values.update(overrides)
    return values


def passive_payload(status, action):
    return plan_payload(
        status=status,
        action=action,
        confidence=0.4,
        entry_zone=None,
        initial_position_pct=None,
        max_position_pct=None,
        stop_conditions=[],
        valid_until=None,
    )


def trader_state():
    return {
        "analysis_id": "task-123",
        "company_of_interest": "000001",
        "trade_date": "2026-07-26",
        "investment_plan": "旧研究报告，仅供上下文",
        "market_report": "market",
        "sentiment_report": "sentiment",
        "news_report": "news",
        "fundamentals_report": "fundamentals",
    }


def normal_meta():
    now = datetime.now(timezone.utc)
    return ModelExecutionMeta(
        provider="test-provider",
        model_name="test-model",
        model_version="test-model-v1",
        prompt_name="normal_trade_plan",
        prompt_version="normal_trade_plan_v1",
        started_at=now,
        finished_at=now,
        latency_ms=1,
        execution_status="SUCCESS",
    )


def validated_normal_plan(**overrides):
    payload = plan_payload()
    payload.update(
        plan_id="plan-1",
        snapshot_id="legacy-analysis:task-123",
        quant_proposal_id="legacy-quant:none",
        model_meta=normal_meta().model_dump(mode="json"),
    )
    payload.update(overrides)
    return NormalTradePlan.model_validate(payload)


def risk_state(plan=None):
    return {
        **trader_state(),
        "normal_trade_plan": (plan or validated_normal_plan()).model_dump(
            mode="json"
        ),
        "decision_error": None,
        "risk_debate_state": {
            "history": "risk debate",
            "risky_history": "",
            "safe_history": "",
            "neutral_history": "",
            "latest_speaker": "",
            "current_risky_response": "",
            "current_safe_response": "",
            "current_neutral_response": "",
            "judge_decision": "",
            "count": 1,
        },
    }


def review_payload(status="CONFIRM", **overrides):
    values = {
        "status": status,
        "completeness_score": 0.9,
        "logic_consistency_score": 0.8,
        "risk_control_score": 0.7,
        "missing_evidence": [],
        "logical_conflicts": [],
        "risk_findings": [],
        "adjusted_plan": None,
        "material_change_fields": [],
        "review_reason": "风险终审完成",
    }
    values.update(overrides)
    return values


def run_trader(llm):
    return create_trader(
        llm,
        None,
        {
            "llm_provider": "test-provider",
            "quick_think_llm": "fake-model-v1",
        },
    )(trader_state())


def run_risk(llm, state=None):
    return create_risk_manager(
        llm,
        None,
        {
            "llm_provider": "test-provider",
            "deep_think_llm": "fake-top-v1",
        },
    )(state or risk_state())


def test_trader_accepts_valid_structured_output_without_target():
    result = run_trader(FakeLLM(plan_payload(target_price=None)))
    plan = NormalTradePlan.model_validate(result["normal_trade_plan"])
    assert plan.status == "PROPOSE_TRADE"
    assert plan.target_price is None
    assert plan.snapshot_id == "legacy-analysis:task-123"
    assert plan.quant_proposal_id == "legacy-quant:none"
    assert plan.model_meta.prompt_version == "normal_trade_plan_v1"
    assert plan.model_meta.raw_output_hash is not None


@pytest.mark.parametrize(
    ("llm", "expected_status", "error_type"),
    [
        (FakeLLM(content=""), "MODEL_FAILED", "EMPTY_RESPONSE"),
        (FakeLLM(content="{broken"), "INVALID_OUTPUT", "MALFORMED_JSON"),
        (
            FakeLLM(plan_payload(status="PROPOSE_TRADE", action="NONE")),
            "INVALID_OUTPUT",
            "SCHEMA_VALIDATION_ERROR",
        ),
        (
            FakeLLM(error=RuntimeError("provider unavailable")),
            "MODEL_FAILED",
            "PROVIDER_ERROR",
        ),
        (
            FakeLLM(error=TimeoutError("timed out")),
            "MODEL_FAILED",
            "MODEL_TIMEOUT",
        ),
    ],
)
def test_trader_failures_are_not_hold(llm, expected_status, error_type):
    result = run_trader(llm)
    plan = NormalTradePlan.model_validate(result["normal_trade_plan"])
    assert plan.status == expected_status
    assert plan.action == "NONE"
    assert plan.action != "HOLD"
    assert result["decision_error"]["error_type"] == error_type


def test_provider_errors_are_redacted():
    result = run_trader(
        FakeLLM(error=RuntimeError("api_key=supersecret provider failed"))
    )
    error_message = result["decision_error"]["error_message"]
    assert "supersecret" not in error_message
    assert "[REDACTED]" in error_message


@pytest.mark.parametrize(
    ("payload", "status", "action"),
    [
        (passive_payload("INSUFFICIENT_DATA", "NONE"), "INSUFFICIENT_DATA", "NONE"),
        (passive_payload("WAIT", "WAIT"), "WAIT", "WAIT"),
    ],
)
def test_trader_preserves_non_trade_statuses(payload, status, action):
    plan = NormalTradePlan.model_validate(run_trader(FakeLLM(payload))["normal_trade_plan"])
    assert (plan.status, plan.action) == (status, action)


def test_risk_judge_confirm():
    result = run_risk(FakeLLM(review_payload()))
    assert result["top_review_decision"]["status"] == "CONFIRM"
    assert result["top_review_decision"]["adjusted_plan"] is None
    assert result["top_model_meta"]["prompt_version"] == "top_review_decision_v1"


@pytest.mark.parametrize(
    ("status", "material_fields"),
    [
        ("RISK_ADJUST", []),
        ("MATERIAL_REVISION", ["max_position_pct"]),
    ],
)
def test_risk_judge_accepts_adjustments(status, material_fields):
    adjusted = deepcopy(plan_payload(max_position_pct=0.15))
    result = run_risk(
        FakeLLM(
            review_payload(
                status=status,
                adjusted_plan=adjusted,
                material_change_fields=material_fields,
            )
        )
    )
    assert result["top_review_decision"]["status"] == status
    assert result["top_review_decision"]["adjusted_plan"] is not None


@pytest.mark.parametrize(
    ("llm", "expected_status", "error_type"),
    [
        (FakeLLM(content=""), "MODEL_FAILED", "EMPTY_RESPONSE"),
        (FakeLLM(content="not json"), "INVALID_OUTPUT", "MALFORMED_JSON"),
        (
            FakeLLM(error=RuntimeError("provider failed")),
            "MODEL_FAILED",
            "PROVIDER_ERROR",
        ),
    ],
)
def test_risk_judge_failures_are_explicit(llm, expected_status, error_type):
    result = run_risk(llm)
    assert result["top_review_decision"]["status"] == expected_status
    assert "HOLD" not in result["final_trade_decision"]
    assert result["decision_error"]["error_type"] == error_type


def test_risk_judge_rejects_opposite_direction():
    adjusted = deepcopy(plan_payload(action="SELL", entry_zone=None))
    result = run_risk(
        FakeLLM(
            review_payload(
                status="MATERIAL_REVISION",
                adjusted_plan=adjusted,
                material_change_fields=["action"],
            )
        )
    )
    assert result["top_review_decision"]["status"] == "INVALID_OUTPUT"
    assert result["decision_error"]["error_type"] == "SCHEMA_VALIDATION_ERROR"


def test_missing_normal_plan_blocks_risk_model_call():
    llm = FakeLLM(review_payload())
    state = risk_state()
    state["normal_trade_plan"] = None
    result = run_risk(llm, state)
    assert llm.calls == 0
    assert result["top_review_decision"]["status"] == "INVALID_OUTPUT"
