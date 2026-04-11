from app.routers.analysis import has_meaningful_result_payload, normalize_result_data


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


def test_normalize_result_data_builds_final_decision_report_when_missing():
	result = normalize_result_data(
		{
			"reports": {
				"fundamentals_report": "# 基本面分析\n\n这里是完整的基本面分析。"
			},
			"decision": {
				"analysis_view": "中性",
				"confidence": 0.75,
				"risk_score": 0.62,
				"summary": "当前更接近基准情景。",
				"reasoning": "主要依据来自息差、资产质量与估值约束。",
				"risk_warning": "需继续关注不良率变化。",
				"watch_items": ["季度息差变化", "零售逾期率"],
			},
		}
	)

	assert "final_trade_decision" in result["reports"]
	assert "研究判断：中性" in result["reports"]["final_trade_decision"]
	assert "主要依据来自息差、资产质量与估值约束" in result["reports"]["final_trade_decision"]
	assert "季度息差变化" in result["reports"]["final_trade_decision"]


def test_normalize_result_data_demotes_inferential_core_evidence_in_decision():
	result = normalize_result_data(
		{
			"decision": {
				"analysis_view": "中性",
				"reasoning": "当前更适合等待年报披露。",
				"core_evidence": ["PB为0.48倍", "零售贷款占比推断超60%"],
				"uncertainties": ["净息差数据缺失"],
				"watch_items": ["下一期财报"],
			},
		}
	)

	assert result["decision"]["core_evidence"] == ["PB为0.48倍"]
	assert "零售贷款占比推断超60%" in result["decision"]["uncertainties"]


def test_has_meaningful_result_payload_rejects_empty_shell_result():
	assert has_meaningful_result_payload(
		{
			"summary": "",
			"recommendation": "",
			"reports": {},
			"decision": {},
			"key_points": [],
		}
	) is False


def test_has_meaningful_result_payload_accepts_report_backed_result():
	assert has_meaningful_result_payload(
		{
			"summary": "",
			"recommendation": "",
			"reports": {
				"market_report": "# 市场技术分析\n\n这是有效报告内容。"
			},
			"decision": {},
			"key_points": [],
		}
	) is True
