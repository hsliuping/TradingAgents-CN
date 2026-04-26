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
	assert markdown_content.index("## 🧩 用户版研究简报") < markdown_content.index("## 📝 综合研究结论")
	assert markdown_content.index("## 🧩 用户版研究简报") < markdown_content.index("## 📈 市场技术研究报告")
	assert "## 综合研究结论" not in markdown_content
	assert "### 核心观察" in markdown_content
	assert "投资有风险，决策需谨慎" not in markdown_content
	assert "本报告仅供研究参考，不构成个股推荐、投资建议或操作依据。请结合公开信息披露与自身研究独立判断。" in markdown_content


def test_generate_markdown_report_normalizes_chinese_numbered_subsections():
	exporter = ReportExporter()
	report_doc = {
		"stock_symbol": "000001",
		"analysis_date": "2026-04-11 00:00:00",
		"research_depth": "快速",
		"reports": {
			"index_report": "## 一、核心观察\n\n量能回升但结构分化仍在。\n\n二、后续关注\n\n关注政策催化与成交持续性。",
			"sector_report": "**一、景气线索**\n\n板块轮动速度加快。\n\n**二、验证要点**\n\n观察主线成交是否延续。",
		},
	}

	markdown_content = exporter.generate_markdown_report(report_doc)

	assert "## 📊 大盘环境研究报告" in markdown_content
	assert "## 🏭 行业板块研究报告" in markdown_content
	assert "### 核心观察" in markdown_content
	assert "### 后续关注" in markdown_content
	assert "### 景气线索" in markdown_content
	assert "### 验证要点" in markdown_content
	assert "### 一、核心观察" not in markdown_content
	assert "### 二、后续关注" not in markdown_content
	assert "一、景气线索" not in markdown_content
	assert "二、验证要点" not in markdown_content
