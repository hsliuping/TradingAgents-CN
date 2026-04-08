import json

from app.scripts.migrate_historical_manager_reports_to_mem0 import (
    MIGRATION_SOURCE,
    REPORT_SOURCE_ANALYSIS_RESULTS,
    REPORT_SOURCE_PROGRESS_JSON,
    _build_analysis_result_record,
    _build_progress_records,
    _build_store_metadata,
)


def test_build_analysis_result_record_parses_python_literal_markdown(tmp_path):
    report_path = (
        tmp_path
        / "data"
        / "analysis_results"
        / "UNKNOWN"
        / "2025-08-20"
        / "reports"
        / "research_team_decision.md"
    )
    report_path.parent.mkdir(parents=True)
    report_path.write_text(
        "{'judge_decision': '### 投资组合决策：万科A（000002）建议持有', 'history': '...'}",
        encoding="utf-8",
    )

    record = _build_analysis_result_record(report_path)

    assert record is not None
    assert record.target_agent_id == "research_manager_v2"
    assert record.source_kind == REPORT_SOURCE_ANALYSIS_RESULTS
    assert record.ticker == "000002"
    assert record.analysis_date == "2025-08-20"
    assert record.content == "### 投资组合决策：万科A（000002）建议持有"
    assert record.legacy_doc_id.endswith("data/analysis_results/UNKNOWN/2025-08-20/reports/research_team_decision.md")


def test_build_progress_records_extracts_both_manager_decisions(tmp_path):
    progress_path = tmp_path / "data" / "temp" / "processing" / "progress_analysis_demo.json"
    progress_path.parent.mkdir(parents=True)
    payload = {
        "company_of_interest": "000002",
        "trade_date": "2025-08-01",
        "investment_debate_state": {"judge_decision": "研究经理最终判断：持有"},
        "risk_debate_state": {"judge_decision": "风险经理最终判断：卖出"},
    }
    progress_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    records = _build_progress_records(progress_path, payload)

    assert len(records) == 2
    assert {record.target_agent_id for record in records} == {"research_manager_v2", "risk_manager_v2"}
    assert all(record.ticker == "000002" for record in records)
    assert all(record.analysis_date == "2025-08-01" for record in records)
    assert all(record.source_kind == REPORT_SOURCE_PROGRESS_JSON for record in records)


def test_build_store_metadata_adds_mem0_filters_and_source_details(tmp_path):
    report_path = (
        tmp_path
        / "data"
        / "analysis_results"
        / "000002"
        / "2025-08-20"
        / "reports"
        / "risk_management_decision.md"
    )
    report_path.parent.mkdir(parents=True)
    report_path.write_text("{'judge_decision': '风险管理委员会主席建议卖出'}", encoding="utf-8")

    record = _build_analysis_result_record(report_path)
    metadata = _build_store_metadata(record)

    assert metadata["source"] == MIGRATION_SOURCE
    assert metadata["target_agent_id"] == "risk_manager_v2"
    assert metadata["source_kind"] == REPORT_SOURCE_ANALYSIS_RESULTS
    assert metadata["source_file"] == "data/analysis_results/000002/2025-08-20/reports/risk_management_decision.md"
    assert metadata["ticker"] == "000002"
    assert metadata["symbol"] == "000002"
    assert metadata["object_type"] == "stock"
    assert metadata["object_key"] == "000002"
    assert metadata["analysis_date"] == "2025-08-20"