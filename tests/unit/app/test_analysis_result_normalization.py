from app.routers.analysis import normalize_result_data


def test_normalize_result_data_preserves_full_reports_for_detail_endpoints():
	raw_market_report = "# 市场技术分析\n\n这是完整的市场技术分析内容，不应在详情接口中被压缩。\n\n- 观察点A\n- 观察点B"
	raw_research_report = "# 乐观情景研究员\n\n这是完整的乐观情景论证，不应被过滤掉。"

	result = normalize_result_data(
		{
			"summary": "完整摘要",
			"recommendation": "完整研究结论",
			"reports": {
				"market_report": raw_market_report,
				"bull_researcher": raw_research_report,
			},
		}
	)

	assert result["summary"] == "完整摘要"
	assert result["recommendation"] == "完整研究结论"
	assert result["reports"]["market_report"] == raw_market_report
	assert result["reports"]["bull_researcher"] == raw_research_report
