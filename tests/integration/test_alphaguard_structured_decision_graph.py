from datetime import datetime, timedelta, timezone
import json

from tradingagents.agents.managers.risk_manager import create_risk_manager
from tradingagents.agents.trader.trader import create_trader
from tradingagents.alphaguard.decision_schemas import (
    NormalTradePlan,
    TopReviewDecision,
)
from tradingagents.graph.signal_processing import LegacyDecisionAdapter


class Response:
    def __init__(self, payload):
        self.content = payload
        self.response_metadata = {}


class QueueLLM:
    model_name = "integration-model-v1"

    def __init__(self, payload=None, error=None):
        self.payload = payload
        self.error = error
        self.calls = 0

    def invoke(self, messages):
        self.calls += 1
        if self.error:
            raise self.error
        return Response(json.dumps(self.payload, ensure_ascii=False))


def base_state():
    return {
        "analysis_id": "graph-task-1",
        "company_of_interest": "000001",
        "trade_date": "2026-07-26",
        "investment_plan": "旧研究文本",
        "market_report": "market",
        "sentiment_report": "sentiment",
        "news_report": "news",
        "fundamentals_report": "fundamentals",
        "decision_error": None,
        "risk_debate_state": {
            "history": "debate",
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


def trade_payload():
    return {
        "status": "PROPOSE_TRADE",
        "action": "BUY",
        "confidence": 0.75,
        "thesis": "通过结构化链路",
        "bullish_evidence": [],
        "bearish_evidence": [],
        "entry_zone": {"lower": 9.5, "upper": 10.5, "currency": "CNY"},
        "initial_position_pct": 0.1,
        "max_position_pct": 0.2,
        "add_conditions": [],
        "stop_conditions": [
            {"condition_id": "stop-1", "description": "止损"}
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


def confirm_payload():
    return {
        "status": "CONFIRM",
        "completeness_score": 0.8,
        "logic_consistency_score": 0.8,
        "risk_control_score": 0.8,
        "missing_evidence": [],
        "logical_conflicts": [],
        "risk_findings": [],
        "adjusted_plan": None,
        "material_change_fields": [],
        "review_reason": "确认普通模型计划",
    }


def nodes(trader_llm, risk_llm):
    config = {
        "llm_provider": "test",
        "quick_think_llm": "integration-model-v1",
        "deep_think_llm": "integration-top-v1",
    }
    return (
        create_trader(trader_llm, None, config),
        create_risk_manager(risk_llm, None, config),
    )


def test_structured_plan_reaches_risk_judge_and_final_state():
    state = base_state()
    trader, risk = nodes(QueueLLM(trade_payload()), QueueLLM(confirm_payload()))
    state.update(trader(state))
    assert NormalTradePlan.model_validate(state["normal_trade_plan"]).action == "BUY"

    state.update(risk(state))
    review = TopReviewDecision.model_validate(state["top_review_decision"])
    assert review.plan_id == state["normal_trade_plan"]["plan_id"]
    assert review.status == "CONFIRM"

    legacy = LegacyDecisionAdapter().from_structured(
        state["normal_trade_plan"],
        state["top_review_decision"],
        "000001",
    )
    assert legacy["action"] == "买入"
    assert legacy["target_price"] is None
    assert legacy["not_for_automated_execution"] is True
    assert "AlphaGuard" in state["trader_investment_plan"]
    assert "AlphaGuard" in state["final_trade_decision"]


def test_model_failure_flows_without_becoming_hold():
    state = base_state()
    risk_llm = QueueLLM(confirm_payload())
    trader, risk = nodes(
        QueueLLM(error=RuntimeError("provider down")),
        risk_llm,
    )
    state.update(trader(state))
    assert state["normal_trade_plan"]["status"] == "MODEL_FAILED"
    state.update(risk(state))

    assert risk_llm.calls == 0
    assert state["normal_trade_plan"]["status"] == "MODEL_FAILED"
    assert state["top_review_decision"]["status"] == "SUSPEND"
    assert state["decision_error"]["status"] == "MODEL_FAILED"
    legacy = LegacyDecisionAdapter().from_structured(
        state["normal_trade_plan"],
        state["top_review_decision"],
    )
    assert legacy["action"] == "不可执行"


def test_parse_failure_is_not_overwritten_by_normal_hold():
    state = base_state()
    risk_llm = QueueLLM(confirm_payload())
    trader, risk = nodes(QueueLLM(payload=None), risk_llm)
    state.update(trader(state))
    assert state["normal_trade_plan"]["status"] == "INVALID_OUTPUT"
    state.update(risk(state))
    assert state["top_review_decision"]["status"] == "SUSPEND"
    assert "HOLD" not in state["final_trade_decision"]
