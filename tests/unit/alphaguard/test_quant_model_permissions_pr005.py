from __future__ import annotations

from copy import deepcopy
import json

import pytest

from tests.unit.alphaguard.pr005_helpers import make_context, make_plan
from tradingagents.agents.managers.risk_manager import create_risk_manager
from tradingagents.agents.trader.trader import create_trader
from tradingagents.alphaguard.decision_schemas import (
    NormalTradePlan,
    TopReviewDecision,
)


class Response:
    def __init__(self, content):
        self.content = content
        self.response_metadata = {"request_id": "request-pr005"}


class CapturingLLM:
    model_name = "fixed-quant-model-v1"

    def __init__(self, payload=None, *, error=None, content=None):
        self.payload = payload
        self.error = error
        self.content = content
        self.calls = 0
        self.messages = None

    def invoke(self, messages):
        self.calls += 1
        self.messages = messages
        if self.error:
            raise self.error
        content = (
            self.content
            if self.content is not None
            else json.dumps(self.payload, ensure_ascii=False)
        )
        return Response(content)


def quant_trade_payload(context, **overrides):
    values = {
        "status": "PROPOSE_TRADE",
        "action": context.quant_proposal.action_candidate,
        "confidence": 0.8,
        "thesis": "only snapshot evidence supports this plan",
        "bullish_evidence": [
            item.model_dump(mode="json") for item in context.price_evidence[:1]
        ],
        "bearish_evidence": [],
        "entry_zone": context.quant_proposal.entry_zone.model_dump(mode="json"),
        "initial_position_pct": context.quant_proposal.initial_position_pct,
        "max_position_pct": context.quant_proposal.max_position_pct,
        "add_conditions": [],
        "stop_conditions": [],
        "reduce_conditions": [],
        "exit_conditions": [
            {"condition_id": "exit", "description": "exit on invalidation"}
        ],
        "invalidation_conditions": [
            {"condition_id": "invalid", "description": "thesis invalidated"}
        ],
        "target_price": None,
        "valid_until": context.quant_proposal.valid_until.isoformat(),
        "main_risks": [],
        "unresolved_questions": [],
    }
    values.update(overrides)
    return values


def quant_state(context):
    return {
        "analysis_id": context.analysis_id,
        "snapshot_id": context.snapshot_id,
        "company_of_interest": context.symbol,
        "market": context.market,
        "trade_date": context.trade_date.isoformat(),
        "legacy_analysis": False,
        "decision_context": context.model_dump(mode="json"),
        "quant_trade_proposal": context.quant_proposal.model_dump(mode="json"),
        "market_report": "LATEST_MARKET_MUST_NOT_ENTER_QUANT_PROMPT",
        "news_report": "FUTURE_NEWS_MUST_NOT_ENTER_QUANT_PROMPT",
        "attempt_number": 1,
        "trace_id": "trace-pr005",
        "risk_debate_state": {},
    }


def run_trader(context, llm):
    node = create_trader(
        llm,
        None,
        {
            "quick_provider": "fixed",
            "quick_think_llm": "fixed-quant-model-v1",
        },
    )
    return node(quant_state(context))


def review_payload(status="CONFIRM", **overrides):
    values = {
        "status": status,
        "completeness_score": 1,
        "logic_consistency_score": 1,
        "risk_control_score": 1,
        "missing_evidence": [],
        "logical_conflicts": [],
        "risk_findings": [],
        "adjusted_plan": None,
        "material_change_fields": [],
        "review_reason": "fixed quant review",
    }
    values.update(overrides)
    return values


def run_top(context, plan, llm):
    state = quant_state(context)
    state["normal_trade_plan"] = plan.model_dump(mode="json")
    state["risk_policy_summary"] = {
        "risk_policy_id": "risk-policy-v1",
        "version": "1.0.0",
    }
    node = create_risk_manager(
        llm,
        None,
        {
            "deep_provider": "fixed",
            "deep_think_llm": "fixed-top-model-v1",
        },
    )
    return node(state)


def test_quant_trader_uses_only_context_and_enforces_prompt_audit_fields():
    context = make_context()
    llm = CapturingLLM(quant_trade_payload(context, target_price=None))
    result = run_trader(context, llm)
    plan = NormalTradePlan.model_validate(result["normal_trade_plan"])
    assert plan.status == "PROPOSE_TRADE"
    assert plan.action == context.quant_proposal.action_candidate
    assert plan.target_price is None
    assert plan.decision_context_id == context.decision_context_id
    assert plan.model_meta.prompt_version == "normal_trade_plan_quant_v1"
    assert plan.model_meta.context_hash == context.context_hash
    assert plan.model_meta.template_hash
    assert plan.model_meta.input_hash
    prompt = json.dumps(llm.messages, ensure_ascii=False)
    assert "LATEST_MARKET_MUST_NOT_ENTER_QUANT_PROMPT" not in prompt
    assert "FUTURE_NEWS_MUST_NOT_ENTER_QUANT_PROMPT" not in prompt


@pytest.mark.parametrize(
    "overrides",
    [
        {"action": "SELL", "entry_zone": None},
        {"max_position_pct": 0.11},
        {
            "bullish_evidence": [
                {
                    "evidence_id": "latest-data:not-in-snapshot",
                    "summary": "forbidden",
                    "source": "latest",
                }
            ]
        },
    ],
)
def test_quant_trader_rejects_direction_position_or_evidence_escape(overrides):
    context = make_context()
    result = run_trader(
        context, CapturingLLM(quant_trade_payload(context, **overrides))
    )
    plan = NormalTradePlan.model_validate(result["normal_trade_plan"])
    assert plan.status == "INVALID_OUTPUT"
    assert plan.action == "NONE"
    assert result["decision_error"]["error_type"] == "SCHEMA_VALIDATION_ERROR"


@pytest.mark.parametrize(
    ("status", "action"),
    [
        ("NO_TRADE", "NONE"),
        ("WAIT", "WAIT"),
        ("INSUFFICIENT_DATA", "NONE"),
    ],
)
def test_quant_trader_preserves_explicit_non_trade_states(status, action):
    context = make_context()
    payload = quant_trade_payload(
        context,
        status=status,
        action=action,
        confidence=0.3,
        bullish_evidence=[],
        entry_zone=None,
        initial_position_pct=None,
        max_position_pct=None,
        exit_conditions=[],
        invalidation_conditions=[],
        valid_until=None,
    )
    plan = NormalTradePlan.model_validate(
        run_trader(context, CapturingLLM(payload))["normal_trade_plan"]
    )
    assert (plan.status, plan.action) == (status, action)


def test_quant_top_confirm_reads_context_plan_policy_and_not_legacy_reports():
    context = make_context()
    plan = make_plan(context)
    llm = CapturingLLM(review_payload())
    result = run_top(context, plan, llm)
    review = TopReviewDecision.model_validate(result["top_review_decision"])
    assert review.status == "CONFIRM"
    assert review.plan_id == plan.plan_id
    assert review.model_meta.prompt_version == "top_review_decision_quant_v1"
    assert review.model_meta.context_hash == context.context_hash
    prompt = json.dumps(llm.messages, ensure_ascii=False)
    assert context.quant_proposal_id in prompt
    assert "risk-policy-v1" in prompt
    assert "LATEST_MARKET_MUST_NOT_ENTER_QUANT_PROMPT" not in prompt
    assert "FUTURE_NEWS_MUST_NOT_ENTER_QUANT_PROMPT" not in prompt


def test_quant_top_accepts_provable_risk_only_adjustment():
    context = make_context()
    plan = make_plan(context)
    adjusted = plan.model_dump(mode="json")
    adjusted.update(
        confidence=0.7,
        initial_position_pct=0.04,
        max_position_pct=0.08,
        entry_zone={"lower": 99.5, "upper": 100.5, "currency": "CNY"},
        stop_conditions=[
            {"condition_id": "top-stop", "description": "additional stop"}
        ],
    )
    result = run_top(
        context,
        plan,
        CapturingLLM(
            review_payload(status="RISK_ADJUST", adjusted_plan=adjusted)
        ),
    )
    review = TopReviewDecision.model_validate(result["top_review_decision"])
    assert review.status == "RISK_ADJUST"
    assert review.adjusted_plan.max_position_pct == 0.08
    assert review.adjusted_plan.target_price is None


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("max_position_pct", 0.11),
        ("entry_zone", {"lower": 98, "upper": 102, "currency": "CNY"}),
        ("valid_until", "2031-07-03T00:00:00"),
        ("exit_conditions", []),
        ("action", "SELL"),
        ("strategy_id", "FORBIDDEN_STRATEGY"),
        ("target_price", 123.0),
        ("thesis", "different core thesis"),
    ],
)
def test_quant_top_rejects_non_whitelisted_adjustments(field, value):
    context = make_context()
    plan = make_plan(context)
    adjusted = plan.model_dump(mode="json")
    adjusted[field] = value
    result = run_top(
        context,
        plan,
        CapturingLLM(
            review_payload(status="RISK_ADJUST", adjusted_plan=adjusted)
        ),
    )
    assert result["top_review_decision"]["status"] == "INVALID_OUTPUT"
    assert result["decision_error"]["error_type"] == "SCHEMA_VALIDATION_ERROR"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("max_position_pct", 0.11),
        ("entry_zone", {"lower": 98, "upper": 102, "currency": "CNY"}),
        ("valid_until", "2031-07-03T00:00:00"),
        ("exit_conditions", []),
        ("target_price", 123.0),
    ],
)
def test_material_revision_cannot_hide_a_risk_increase(field, value):
    context = make_context()
    plan = make_plan(context)
    adjusted = plan.model_dump(mode="json")
    adjusted[field] = value
    result = run_top(
        context,
        plan,
        CapturingLLM(
            review_payload(
                status="MATERIAL_REVISION",
                adjusted_plan=adjusted,
                material_change_fields=[field],
            )
        ),
    )
    assert result["top_review_decision"]["status"] == "INVALID_OUTPUT"


@pytest.mark.parametrize("status", ["REJECT", "SUSPEND"])
def test_quant_top_can_block_but_cannot_create_an_adjusted_trade(status):
    context = make_context()
    plan = make_plan(context)
    result = run_top(context, plan, CapturingLLM(review_payload(status=status)))
    review = TopReviewDecision.model_validate(result["top_review_decision"])
    assert review.status == status
    assert review.adjusted_plan is None


@pytest.mark.parametrize(
    ("llm", "expected"),
    [
        (CapturingLLM(content=""), "MODEL_FAILED"),
        (CapturingLLM(content="{bad"), "INVALID_OUTPUT"),
        (CapturingLLM(error=RuntimeError("provider failed")), "MODEL_FAILED"),
    ],
)
def test_quant_top_failures_are_explicit_and_never_hold(llm, expected):
    context = make_context()
    result = run_top(context, make_plan(context), llm)
    assert result["top_review_decision"]["status"] == expected
    assert "HOLD" not in result["final_trade_decision"]
