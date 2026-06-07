from datetime import datetime

from app.models.analysis import AnalysisParameters, SingleAnalysisRequest
from app.services.simple_analysis_service import SimpleAnalysisService


def _request(
    committee_mode: str = "standard",
    selected_committee_agents=None,
    agent_engine: str = "tradingagents",
) -> SingleAnalysisRequest:
    return SingleAnalysisRequest(
        symbol="000001",
        parameters=AnalysisParameters(
            market_type="A股",
            analysis_date=datetime(2026, 6, 6),
            research_depth="标准",
            selected_analysts=["market", "fundamentals"],
            agent_engine=agent_engine,
            committee_mode=committee_mode,
            selected_committee_agents=selected_committee_agents or [],
        ),
    )


def test_analysis_parameters_default_to_standard_committee_mode():
    params = AnalysisParameters()

    assert params.committee_mode == "standard"
    assert params.selected_committee_agents == []


def test_standard_committee_mode_does_not_add_enhanced_reports():
    service = SimpleAnalysisService()
    reports = {"market_report": "市场报告内容" * 10}

    enhanced = service._build_enhanced_committee_reports(
        request=_request(),
        reports=reports,
        state={},
        decision={},
    )

    assert enhanced == {}


def test_enhanced_committee_generates_selected_reports_without_llm():
    service = SimpleAnalysisService()

    enhanced = service._build_enhanced_committee_reports(
        request=_request(
            committee_mode="enhanced",
            selected_committee_agents=["data_steward", "valuation", "flow_positioning", "scorecard"],
        ),
        reports={
            "market_report": "市场趋势向上，成交量温和放大。" * 8,
            "fundamentals_report": "收入稳定，现金流质量仍需观察。" * 8,
            "final_trade_decision": "最终建议持有，等待更明确的催化。" * 8,
        },
        state={"performance_metrics": {"total_time": 12.5}},
        decision={"action": "持有", "confidence": 0.6, "risk_score": 0.45},
    )

    assert "committee_data_steward" in enhanced
    assert "committee_valuation" in enhanced
    assert "committee_flow_positioning" in enhanced
    assert "committee_scorecard" in enhanced
    assert "committee_reconciliation" in enhanced
    assert "证据等级" in enhanced["committee_scorecard"]


def test_data_steward_marks_missing_sources_as_low_evidence():
    service = SimpleAnalysisService()

    enhanced = service._build_enhanced_committee_reports(
        request=_request(committee_mode="enhanced", selected_committee_agents=["data_steward"]),
        reports={},
        state={},
        decision={},
    )

    assert "committee_data_steward" in enhanced
    assert "证据等级：D" in enhanced["committee_data_steward"]
    assert "缺失" in enhanced["committee_data_steward"]


def test_codex_context_includes_committee_selection(monkeypatch):
    service = SimpleAnalysisService()
    captured = {}

    def fake_bridge(prompt, context):
        captured["prompt"] = prompt
        captured["context"] = context
        return {"content": "建议持有。"}

    monkeypatch.setattr(service, "_invoke_codex_agent_bridge", fake_bridge)

    service._run_codex_agent_analysis_sync(
        task_id="task-1",
        user_id="user-1",
        request=_request(
            committee_mode="enhanced",
            selected_committee_agents=["data_steward", "valuation", "scorecard"],
            agent_engine="codex",
        ),
        progress_tracker=None,
        update_progress_sync=lambda *args, **kwargs: None,
    )

    assert captured["context"]["committee_mode"] == "enhanced"
    assert captured["context"]["selected_committee_agents"] == [
        "data_steward",
        "valuation",
        "scorecard",
    ]
    assert "增强研究委员会" in captured["prompt"]
