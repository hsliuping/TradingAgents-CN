from app.utils.report_formatter import extract_reports_from_state, generate_summary_recommendation


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


def test_generate_summary_recommendation_prefers_trader_brief_over_final_decision():
    reports = {
        "final_trade_decision": "# 综合研究结论\n\n这是内部综合结论，应该作为次级回退使用。" * 4,
        "trader_investment_plan": "# 用户版研究简报\n\n一句话结论：当前更接近中性偏谨慎判断，后续重点观察资产质量与成交修复是否延续。\n\n为什么这么看：估值不高，但催化和验证数据还不够扎实。",
    }

    summary, recommendation = generate_summary_recommendation(
        reports,
        {"action": "中性", "reasoning": "等待更多验证数据。"},
        "000001",
    )

    assert "一句话结论" in summary
    assert "内部综合结论" not in summary
    assert "研究观点：中性" in recommendation