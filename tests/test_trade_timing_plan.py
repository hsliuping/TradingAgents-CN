from datetime import datetime

from app.models.analysis import AnalysisParameters, SingleAnalysisRequest
from app.services.simple_analysis_service import SimpleAnalysisService


def _request(agent_engine: str = "tradingagents") -> SingleAnalysisRequest:
    return SingleAnalysisRequest(
        symbol="000001",
        parameters=AnalysisParameters(
            market_type="A股",
            analysis_date=datetime(2026, 6, 6),
            research_depth="标准",
            selected_analysts=["market", "fundamentals"],
            agent_engine=agent_engine,
        ),
    )


def _reports() -> dict:
    return {
        "market_report": (
            "当前价格：10.00元。支撑位：9.50元。压力位：12.00元。"
            "突破买入价：10.80元。跌破卖出价：9.20元。止损位：9.20元。"
        ),
        "fundamentals_report": "基本面稳健，盈利质量需要继续观察。" * 6,
        "final_trade_decision": "最终交易建议: **买入**。目标价格：12.50元。" * 4,
    }


def test_trade_timing_plan_generates_buy_sell_hold_shapes():
    service = SimpleAnalysisService()

    buy_plan = service._build_trade_timing_plan(
        request=_request(),
        reports=_reports(),
        decision={"action": "买入", "target_price": 12.5, "confidence": 0.72, "risk_score": 0.38},
    )
    sell_plan = service._build_trade_timing_plan(
        request=_request(),
        reports=_reports(),
        decision={"action": "卖出", "target_price": 9.2, "confidence": 0.65, "risk_score": 0.72},
    )
    hold_plan = service._build_trade_timing_plan(
        request=_request(),
        reports=_reports(),
        decision={"action": "持有", "target_price": 12.0, "confidence": 0.55, "risk_score": 0.5},
    )

    assert buy_plan["action"] == "buy"
    assert sell_plan["action"] == "sell"
    assert hold_plan["action"] == "hold"
    for plan in (buy_plan, sell_plan, hold_plan):
        assert plan["time_horizon"] == "5-20个交易日"
        assert "entry_zone" in plan
        assert "entry_trigger" in plan
        assert "stop_loss" in plan
        assert "take_profit" in plan
        assert plan["position_hint"]
        assert plan["evidence_grade"] in {"A", "B", "C", "D"}


def test_trade_timing_plan_degrades_evidence_when_price_levels_are_missing():
    service = SimpleAnalysisService()

    plan = service._build_trade_timing_plan(
        request=_request(),
        reports={"final_trade_decision": "建议观望，等待更明确的价格信号。"},
        decision={"action": "观望", "confidence": 0.4, "risk_score": 0.6},
    )

    assert plan["action"] == "watch"
    assert plan["evidence_grade"] == "D"
    assert plan["entry_zone"]["low"] is None
    assert plan["stop_loss"]["price"] is None
    assert "缺少" in plan["invalidations"][0]


def test_codex_structured_trade_plan_is_preserved_and_report_is_added():
    service = SimpleAnalysisService()

    result = service._normalize_codex_agent_response(
        task_id="task-1",
        request=_request(agent_engine="codex"),
        response={
            "content": "建议买入。",
            "decision": {"action": "买入", "target_price": 12.0, "confidence": 0.7, "risk_score": 0.4},
            "trade_plan": {
                "action": "buy",
                "entry_zone": {"low": 10.0, "high": 10.8, "text": "10.00-10.80"},
                "entry_trigger": "放量突破10.80元",
                "stop_loss": {"price": 9.2, "reason": "跌破关键支撑"},
                "take_profit": {"price": 12.0, "zone": "12.00附近", "strategy": "分批止盈"},
                "invalidations": ["跌破9.20元"],
                "time_horizon": "5-20个交易日",
                "position_hint": "单笔不超过计划资金的20%",
                "confidence": 0.7,
                "risk_level": "中等",
                "evidence_grade": "B",
            },
        },
        analysis_date="2026-06-06",
        execution_time=1.2,
    )

    assert result["trade_plan"]["action"] == "buy"
    assert result["reports"]["trade_timing_plan"].startswith("## 交易执行计划")


def test_codex_text_response_gets_trade_plan_fallback():
    service = SimpleAnalysisService()

    result = service._normalize_codex_agent_response(
        task_id="task-1",
        request=_request(agent_engine="codex"),
        response={
            "content": "建议买入，当前价格10.00元，突破买入价10.80元，止损位9.20元，目标价12.50元。"
        },
        analysis_date="2026-06-06",
        execution_time=1.2,
    )

    assert result["trade_plan"]["action"] == "buy"
    assert result["trade_plan"]["stop_loss"]["price"] == 9.2
    assert "trade_timing_plan" in result["reports"]
