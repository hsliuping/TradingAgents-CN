from app.utils.report_formatter import extract_reports_from_state


def test_extract_reports_from_state_prefers_nested_reports_mapping():
    state = {
        "analysis_id": "demo-analysis",
        "reports": {
            "fundamentals_report": "# 基本面分析\n\n公司盈利能力改善，现金流表现稳定。",
            "neutral_analyst": "# 平安银行（000001）情景平衡与证据权重审阅报告\n\n## 一、核心情景判断\n\n当前更接近基准情景。",
            "risk_management_decision": {
                "content": "# 风险治理摘要\n\n## 核心风险\n\n需继续跟踪资产质量变化。"
            },
        },
    }

    reports = extract_reports_from_state(state)

    assert "fundamentals_report" in reports
    assert "neutral_analyst" in reports
    assert "risk_management_decision" in reports
    assert "盈利能力改善" in reports["fundamentals_report"]
    assert "核心情景判断" in reports["neutral_analyst"]
    assert "核心风险" in reports["risk_management_decision"]