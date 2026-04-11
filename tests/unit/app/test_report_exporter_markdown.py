from app.utils.report_exporter import ReportExporter


def test_generate_markdown_report_hides_internal_module_keys_and_role_ids():
	exporter = ReportExporter()
	report_doc = {
		"stock_symbol": "000001",
		"analysis_date": "2026-04-11 00:00:00",
		"analysts": [
			"market_analyst",
			"bull_researcher",
			"risky_analyst",
		],
		"research_depth": "快速",
		"summary": "这里是摘要。",
		"reports": {
			"market_report": "## 核心观察\n\n这里是市场技术研究内容。",
			"trader_investment_plan": "## 研究摘要\n\n这里是用户版研究简报内容。",
			"final_trade_decision": "## 综合研究结论\n\n这里是综合研究结论内容。\n\n**免责声明**：请结合自身情况独立判断。投资有风险，决策需谨慎。必要时请咨询专业顾问。",
			"bull_researcher": "## 核心主张\n\n这里是乐观情景论证内容。",
			"risky_analyst": "## 情景结论\n\n这里是高弹性情景评估内容。",
		},
	}

	markdown_content = exporter.generate_markdown_report(report_doc)

	assert "bull_researcher" not in markdown_content
	assert "trader_investment_plan" not in markdown_content
	assert "final_trade_decision" not in markdown_content
	assert "risky_analyst" not in markdown_content
	assert "**分析师**: 市场技术分析师, 乐观情景论证, 高弹性情景评估" in markdown_content
	assert "## 🧩 用户版研究简报" in markdown_content
	assert "## 📝 综合研究结论" in markdown_content
	assert "## 🌤️ 乐观情景论证" in markdown_content
	assert "## ⚡ 高弹性情景评估" in markdown_content
	assert "## 综合研究结论" not in markdown_content
	assert "### 核心观察" in markdown_content
	assert "投资有风险，决策需谨慎" not in markdown_content
	assert "本报告仅供研究参考，不构成个股推荐、投资建议或操作依据。请结合公开信息披露与自身研究独立判断。" in markdown_content
