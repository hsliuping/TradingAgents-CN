from datetime import datetime, timedelta, timezone
import json

import pytest

from app.services.simple_analysis_service import SimpleAnalysisService
from tradingagents.agents.managers.risk_manager import create_risk_manager
from tradingagents.agents.trader.trader import create_trader
from tradingagents.alphaguard.decision_schemas import (
    NormalTradePlan,
    TopReviewDecision,
)
from tradingagents.graph.propagation import Propagator

from tests.unit.alphaguard._fakes import FakeDB


class Response:
    def __init__(self, payload):
        self.content = json.dumps(payload, ensure_ascii=False)
        self.response_metadata = {"request_id": "pr003-test"}


class FixedLLM:
    model_name = "fixed-model-v1"

    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def invoke(self, messages):
        self.calls += 1
        return Response(self.payload)


def trade_payload():
    return {
        "status": "PROPOSE_TRADE",
        "action": "BUY",
        "confidence": 0.8,
        "thesis": "同一证据快照下的结构化计划",
        "bullish_evidence": [],
        "bearish_evidence": [],
        "entry_zone": {"lower": 9.5, "upper": 10.5, "currency": "CNY"},
        "initial_position_pct": 0.1,
        "max_position_pct": 0.2,
        "add_conditions": [],
        "stop_conditions": [{"condition_id": "stop", "description": "止损"}],
        "reduce_conditions": [],
        "exit_conditions": [],
        "invalidation_conditions": [],
        "target_price": None,
        "valid_until": (
            datetime.now(timezone.utc) + timedelta(days=3)
        ).isoformat(),
        "main_risks": [],
        "unresolved_questions": [],
        "entry_zone_not_required_reason": None,
        "valid_until_compatibility_reason": None,
    }


def confirm_payload():
    return {
        "status": "CONFIRM",
        "completeness_score": 1,
        "logic_consistency_score": 1,
        "risk_control_score": 1,
        "missing_evidence": [],
        "logical_conflicts": [],
        "risk_findings": [],
        "adjusted_plan": None,
        "material_change_fields": [],
        "review_reason": "确认同一快照下的计划",
    }


def snapshot_state():
    state = Propagator().create_initial_state(
        "600519",
        "2026-07-24",
        analysis_id="analysis-1",
        snapshot_id="snapshot-pr003-1",
        data_quality_status="PASS",
        market="CN",
    )
    state.update(
        investment_plan="研究报告",
        market_report="market",
        sentiment_report="sentiment",
        news_report="news",
        fundamentals_report="fundamentals",
    )
    return state


def test_snapshot_id_reaches_both_structured_model_objects():
    trader_llm = FixedLLM(trade_payload())
    risk_llm = FixedLLM(confirm_payload())
    config = {
        "llm_provider": "test",
        "quick_think_llm": "fixed-model-v1",
        "deep_think_llm": "fixed-top-v1",
    }
    state = snapshot_state()
    state.update(create_trader(trader_llm, None, config)(state))
    plan = NormalTradePlan.model_validate(state["normal_trade_plan"])
    assert plan.snapshot_id == state["snapshot_id"] == "snapshot-pr003-1"

    state.update(create_risk_manager(risk_llm, None, config)(state))
    review = TopReviewDecision.model_validate(state["top_review_decision"])
    assert review.snapshot_id == plan.snapshot_id
    assert trader_llm.calls == risk_llm.calls == 1


def test_data_quality_fail_stops_before_any_model_node():
    trader_llm = FixedLLM(trade_payload())
    risk_llm = FixedLLM(confirm_payload())
    with pytest.raises(ValueError, match="PASS or WARN"):
        Propagator().create_initial_state(
            "600519",
            "2026-07-24",
            snapshot_id="snapshot-fail",
            data_quality_status="FAIL",
            market="CN",
        )
    assert trader_llm.calls == 0
    assert risk_llm.calls == 0


@pytest.mark.asyncio
async def test_snapshot_trace_fields_are_saved_to_analysis_report(monkeypatch):
    db = FakeDB()
    monkeypatch.setattr(
        "app.services.simple_analysis_service.get_mongo_db",
        lambda: db,
    )
    monkeypatch.setattr(
        "tradingagents.utils.stock_utils.StockUtils.get_market_info",
        lambda symbol: {"market": "unknown"},
    )
    service = SimpleAnalysisService.__new__(SimpleAnalysisService)
    result = {
        "stock_symbol": "600519",
        "stock_code": "600519",
        "state": {},
        "snapshot_id": "snapshot-pr003-1",
        "data_quality_status": "PASS",
        "legacy_analysis": False,
        "automated_execution_allowed": False,
        "normal_trade_plan": {"snapshot_id": "snapshot-pr003-1"},
        "top_review_decision": {"snapshot_id": "snapshot-pr003-1"},
        "decision": {"not_for_automated_execution": True},
    }
    await service._save_analysis_result_web_style("task-1", result)
    document = await db["analysis_reports"].find_one({"task_id": "task-1"})
    assert document["snapshot_id"] == "snapshot-pr003-1"
    assert document["data_quality_status"] == "PASS"
    assert document["legacy_analysis"] is False
    assert document["automated_execution_allowed"] is False
