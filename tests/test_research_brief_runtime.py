from app.utils.compliance import (
    sanitize_analysis_payload,
    sanitize_display_report_text,
    sanitize_report_artifacts,
    sanitize_position_analysis_payload,
    sanitize_trade_review_payload,
)
from app.utils.report_formatter import (
    _convert_json_to_markdown,
    _convert_final_decision_json_to_markdown,
    format_decision,
)


def test_sanitize_analysis_payload_strips_legacy_execution_fields() -> None:
    raw_result = {
        "summary": "建议买入，目标价100元，仓位20%。",
        "reports": {
            "market_report": "公司订单回暖，盈利能力改善，后续仍需跟踪原材料波动。",
            "final_trade_decision": "建议买入并关注目标价100元。",
        },
        "decision": {
            "action": "BUY",
            "confidence": 82,
            "risk_score": 65,
            "target_price": 100,
            "price_analysis_range": [90, 100],
            "risk_exposure_ratio": "20%",
            "stop_loss": 88,
            "reasoning": "订单回暖，毛利率修复，现金流改善。",
            "summary": "盈利修复趋势在延续，但仍需关注成本压力。",
            "risk_warning": "原材料价格波动可能侵蚀利润。",
            "core_evidence": ["订单回暖", "毛利率修复"],
            "uncertainties": ["需求持续性"],
            "invalidation_conditions": ["订单再次下滑"],
            "watch_items": ["下一期财报"],
        },
    }

    sanitized = sanitize_analysis_payload(raw_result)

    assert sanitized["reports"] == {
        "market_report": "公司订单回暖，盈利能力改善，后续仍需跟踪原材料波动。"
    }
    assert sanitized["decision"]["action"] == "看涨"
    assert sanitized["decision"]["analysis_view"] == "看涨"
    assert sanitized["decision"]["confidence"] == 0.82
    assert sanitized["decision"]["risk_score"] == 0.65
    assert sanitized["decision"]["core_evidence"] == ["订单回暖", "毛利率修复"]
    assert sanitized["decision"]["uncertainties"] == ["需求持续性"]
    assert sanitized["decision"]["invalidation_conditions"] == ["订单再次下滑"]
    assert sanitized["decision"]["watch_items"] == ["下一期财报"]
    assert "target_price" not in sanitized["decision"]
    assert "price_analysis_range" not in sanitized["decision"]
    assert "risk_exposure_ratio" not in sanitized["decision"]
    assert "stop_loss" not in sanitized["decision"]
    assert sanitized["recommendation"].startswith("研究判断：看涨；")
    assert "目标价" not in sanitized["recommendation"]
    assert "仓位" not in sanitized["recommendation"]


def test_format_decision_keeps_research_brief_fields_only() -> None:
    decision = format_decision(
        {
            "action": "BUY",
            "confidence": 0.78,
            "risk_score": 0.32,
            "target_price": 120,
            "position_ratio": "15%",
            "reasoning": "需求改善带动盈利预期上修。",
            "summary": "当前证据偏向看涨，但需继续跟踪兑现节奏。",
            "risk_warning": "若需求复苏不及预期，判断可能转弱。",
            "core_evidence": ["需求改善", "盈利预期上修"],
            "uncertainties": ["兑现节奏"],
            "invalidation_conditions": ["景气度再次转弱"],
            "watch_items": ["月度销售数据"],
        }
    )

    assert decision == {
        "action": "看涨",
        "analysis_view": "看涨",
        "confidence": 0.78,
        "risk_score": 0.32,
        "reasoning": "需求改善带动盈利预期上修。",
        "summary": "当前证据偏向看涨，但需继续跟踪兑现节奏。",
        "risk_warning": "若需求复苏不及预期，判断可能转弱。",
        "core_evidence": ["需求改善", "盈利预期上修"],
        "uncertainties": ["兑现节奏"],
        "invalidation_conditions": ["景气度再次转弱"],
        "watch_items": ["月度销售数据"],
    }


def test_format_decision_demotes_inferential_core_evidence() -> None:
    decision = format_decision(
        {
            "action": "HOLD",
            "confidence": 0.66,
            "risk_score": 0.41,
            "reasoning": "当前关键分歧仍需等待更完整披露验证。",
            "core_evidence": ["ROE连续四季度回升", "零售贷款占比推断超60%"],
            "uncertainties": ["净息差变动方向未披露"],
            "watch_items": ["下一期财报"],
        }
    )

    assert decision["core_evidence"] == ["ROE连续四季度回升"]
    assert "零售贷款占比推断超60%" in decision["uncertainties"]


def test_convert_final_decision_json_to_markdown_uses_research_brief_sections() -> None:
    markdown = _convert_final_decision_json_to_markdown(
        {
            "risk_level": "中",
            "risk_score": 0.4,
            "final_trade_decision": {
                "analysis_view": "中性",
                "confidence": 72,
                "target_price": 88,
                "risk_control_reference": 75,
                "risk_exposure_ratio": "10%",
                "reasoning": "当前证据尚不足以支持更明确方向，需要继续观察经营数据。",
                "summary": "判断维持中性，等待更多经营验证。",
                "core_evidence": ["盈利表现企稳"],
                "uncertainties": ["需求恢复斜率"],
                "invalidation_conditions": ["盈利再次恶化"],
                "watch_items": ["下一期经营披露"],
                "risk_warning": "若行业需求持续走弱，结论可能下修。",
            },
        }
    )

    assert "# 🎯 综合研究结论" in markdown
    assert "- **研究观点**: 🟡 中性" in markdown
    assert "## 🔍 核心依据" in markdown
    assert "## ❓ 关键不确定性" in markdown
    assert "## 🔄 判断调整条件" in markdown
    assert "## 👀 后续观察事项" in markdown
    assert "观察区间参考" not in markdown
    assert "关键验证位" not in markdown
    assert "风险承受前提" not in markdown


def test_convert_final_decision_json_to_markdown_reindexes_non_empty_lists() -> None:
    markdown = _convert_final_decision_json_to_markdown(
        {
            "final_trade_decision": {
                "analysis_view": "中性",
                "core_evidence": ["证据A", "", None, "证据B"],
                "uncertainties": [None, "不确定性A"],
                "invalidation_conditions": ["条件A", "", "条件B"],
                "watch_items": ["观察项A", None, "观察项B"],
            }
        }
    )

    assert "1. 证据A" in markdown
    assert "2. 证据B" in markdown
    assert "3. 证据B" not in markdown
    assert "1. 不确定性A" in markdown
    assert "1. 条件A" in markdown
    assert "2. 条件B" in markdown
    assert "1. 观察项A" in markdown
    assert "2. 观察项B" in markdown


def test_sanitize_display_report_text_normalizes_legacy_disclaimer() -> None:
    raw_text = """## 综合研究结论

当前判断仍需结合后续披露继续验证。

**免责声明**：请结合自身情况独立判断。投资有风险，决策需谨慎。必要时请咨询专业顾问。
"""

    sanitized = sanitize_display_report_text(raw_text)

    assert "当前判断仍需结合后续披露继续验证。" in sanitized
    assert "投资有风险，决策需谨慎" not in sanitized
    assert "本报告仅供研究参考，不构成个股推荐、投资建议或操作依据。请结合公开信息披露与自身研究独立判断。" in sanitized


def test_sanitize_display_report_text_removes_price_and_actionable_lines() -> None:
    raw_text = """## 情景结论

当前判断仍依赖后续财报与经营数据验证。

- 价格中枢可能上移至12.8-13.5元区间
- 若突破11.33元则强化上行预期
- 建议维持60%-80%风险敞口

## 继续验证的公开信号

1. 下一期财报是否披露更完整的资产质量数据
2. 监管口径是否出现变化
"""

    sanitized = sanitize_display_report_text(raw_text)

    assert "当前判断仍依赖后续财报与经营数据验证。" in sanitized
    assert "下一期财报是否披露更完整的资产质量数据" in sanitized
    assert "监管口径是否出现变化" in sanitized
    assert "12.8-13.5元区间" not in sanitized
    assert "突破11.33元" not in sanitized
    assert "60%-80%风险敞口" not in sanitized


def test_sanitize_display_report_text_normalizes_legacy_titles_and_soft_investment_language() -> None:
    raw_text = """## 新闻分析师研究报告

该事件可能成为价值修复的起点，对配置型投资者具备一定吸引力。

## 板块分析师研究观察报告

当前行业讨论热度上升，但更适合作为后续研究线索而非投资机会。
"""

    sanitized = sanitize_display_report_text(raw_text)

    assert "## 新闻研究" in sanitized
    assert "## 行业板块研究" in sanitized
    assert "价值修复的起点" not in sanitized
    assert "配置型投资者" not in sanitized
    assert "投资机会" not in sanitized
    assert "估值与预期修复的早期信号" in sanitized
    assert "研究型用户" in sanitized
    assert "研究线索" in sanitized


def test_sanitize_report_artifacts_removes_raw_news_tool_call_payload() -> None:
    raw_text = """## 新闻研究报告

{"name": "get_stock_news_details_unified", "arguments": {"news_ids": "news_1,news_2"}}
</tool_call>
"""

    sanitized = sanitize_report_artifacts(raw_text)

    assert 'get_stock_news_details_unified' not in sanitized
    assert '</tool_call>' not in sanitized
    assert '## 新闻研究报告' in sanitized


def test_sanitize_report_artifacts_downgrades_conflicting_stable_data_snapshot_date() -> None:
    raw_text = """### 核心观察
当前尚无分析日（2026-04-21）对应的稳定收盘后日频数据，因此本次历史估值分位与同业比较均按前一可用交易日口径执行。
所有估值指标快照日期统一为 **2026-04-21**。
"""

    sanitized = sanitize_report_artifacts(raw_text)

    assert '所有估值指标快照日期统一为 **2026-04-21**' not in sanitized
    assert '当前正文日期口径仍待验证' in sanitized


def test_convert_json_report_to_markdown_downgrades_error_payload_dict() -> None:
    markdown = _convert_json_to_markdown(
        "{'error': 'Request timed out.', 'success': False}",
        report_type="risk",
    )

    assert markdown == "风险治理模块执行未完成，当前风险结论仍待验证。"


def test_convert_json_report_to_markdown_downgrades_execution_failure_text() -> None:
    markdown = _convert_json_to_markdown(
        "执行失败: LLM API 调用失败（已重试 0 次）: Request timed out.",
        report_type="investment",
    )

    assert markdown == "综合研究结论模块执行未完成，当前结论仍待验证。"


def test_sanitize_position_analysis_payload_strips_execution_fields() -> None:
    raw_result = {
        "action": "add",
        "action_reason": "建议加仓，跌破9.8元止损，目标价12元。",
        "summary": "建议继续持有并等待12元目标价。",
        "detailed_analysis": "公司基本面稳定，但若跌破9.8元需要止损。",
        "risk_assessment": "若行业景气继续走弱，盈利能力会承压。",
        "opportunity_assessment": "若资产质量改善，估值修复弹性可能提升。",
        "price_targets": {"stop_loss_price": 9.8, "take_profit_price": 12.0},
        "suggested_quantity": 1000,
        "suggested_amount": 10000,
        "confidence": 88,
    }

    sanitized = sanitize_position_analysis_payload(raw_result)

    assert sanitized["action"] == "hold"
    assert sanitized["user_view"]["conclusion"]
    assert sanitized["user_view"]["risk_focus"]
    assert sanitized["user_view"]["watch_items"]
    assert sanitized["price_targets"] == {}
    assert sanitized["suggested_quantity"] is None
    assert sanitized["suggested_amount"] is None
    assert sanitized["confidence"] == 88.0
    assert "加仓" not in sanitized["action_reason"]
    assert "止损" not in sanitized["action_reason"]
    assert "目标价" not in sanitized["summary"]
    assert sanitized["recommendation"].startswith("该持仓研究仅提供研究观察")


def test_sanitize_position_analysis_payload_strips_score_and_trigger_language() -> None:
    raw_result = {
        "action": "hold",
        "action_reason": (
            "当前持仓处于观察期。技术面评分5分，基本面评分7.3分。"
            "需持续验证价格是否能在MA20上方形成连续三日收盘站稳，并关注成交量是否温和放大。"
            "核心判断是公司经营质量仍具韧性，但市场预期尚待修复。"
        ),
        "detailed_analysis": "价格紧贴MA20与布林中轨，暂不具备右侧介入依据。",
        "risk_assessment": "若行业景气继续走弱，盈利能力会承压。",
        "opportunity_assessment": "若经营改善兑现，估值修复弹性可能提升。",
    }

    sanitized = sanitize_position_analysis_payload(raw_result)

    assert "评分" not in sanitized["action_reason"]
    assert "连续三日" not in sanitized["action_reason"]
    assert "站稳" not in sanitized["action_reason"]
    assert "放大" not in sanitized["action_reason"]
    assert "MA20" not in sanitized["action_reason"]
    assert "核心判断是公司经营质量仍具韧性" in sanitized["action_reason"]


def test_sanitize_position_analysis_payload_rewrites_deep_loss_into_user_summary() -> None:
    raw_result = {
        "action": "hold",
        "action_reason": (
            "研究结论；当前持仓处于技术结构临界守稳、基本面坚实但估值结构分化的中性观察阶段；"
            "价格紧贴中期支撑，尚未出现趋势反转信号；核心依据"
        ),
        "risk_assessment": "请重点关注持仓波动、行业变化和公告风险。",
        "opportunity_assessment": "请持续跟踪经营质量、估值变化和潜在催化事件。",
        "detailed_analysis": "已连续3日站稳MA20上方，并关注成交量是否温和放大。",
    }
    snapshot = {
        "cost_price": 345.5,
        "current_price": 228.52,
        "unrealized_pnl_pct": -33.86,
        "holding_days": 85,
    }

    sanitized = sanitize_position_analysis_payload(raw_result, position_snapshot=snapshot)

    assert "浮亏约33.86%" in sanitized["action_reason"]
    assert sanitized["user_view"]["position_context"]
    assert len(sanitized["user_view"]["key_points"]) >= 1
    assert "成本价约¥345.50，当前价约¥228.52" in sanitized["action_reason"]
    assert "持有时间约85天" in sanitized["action_reason"]
    assert "暂时只能继续观察" in sanitized["action_reason"]
    assert "站稳" not in sanitized["action_reason"]
    assert "MA20" not in sanitized["action_reason"]
    assert "技术结构临界守稳" not in sanitized["action_reason"]
    assert "### 当前状态" in sanitized["detailed_analysis"]
    assert "### 风险提示" in sanitized["detailed_analysis"]


def test_sanitize_position_analysis_payload_rewrites_user_view_into_plain_complete_items() -> None:
    raw_result = {
        "action": "hold",
        "action_reason": (
            "当前这笔持仓浮盈约31.83%，但后续判断仍需关注证据是否延续。 成本价约¥329.87，当前价约¥434.88。 "
            "持有时间约152天，后续更应优先确认经营与风险是否改善，而不是依赖短线技术信号。"
            "现阶段技术面高度安全、基本面确定性优势兑现但成长逻辑待验证的中性偏强状态；"
            "成本价深埋于所有关键均线之下，财务指标稳健，盈利质量优异，但ROE阶段性回落与毛利率数据缺失构成核心验证缺口；"
            "- 经营现金流持续高倍覆盖净利润，财务安全边际坚实"
        ),
        "risk_assessment": (
            "宁德时代当前持仓面临的主要风险并非流动性或信用危机类显性风险，而是结构性预期错配引发的估值再平衡风险。"
            "第二风险点为毛利率信息不可用所导致的盈利归因失焦：无法区分当前净利率水平是源于上游原材料价格回落的被动传导，"
            "还是自身技术降本能力的真实体现，抑或市场份额策略性让"
        ),
        "opportunity_assessment": (
            "当前持仓具备清晰的结构性机会窗口，核心催化来源于盈利质量与成长动能的双重验证兑现。"
            "第一类机会来自ROE趋势修复：若2026年中报显示净资产收益率环比明显回升，则高PB估值将获"
        ),
        "user_view": {
            "conclusion": "现阶段技术面高度安全、基本面确定性优势兑现但成长逻辑待验证的中性偏强状态；成本价深埋于所有关键均线之下，财务指标稳健，盈利质量优异，但ROE阶段性回落与毛利率数据缺失构成核心验证缺口；- 经营现金流持续高倍覆盖净利润，财务安全边际坚实",
            "position_context": "当前这笔持仓浮盈约31.83%，但后续判断仍需关注证据是否延续。 成本价约¥329.87，当前价约¥434.88。 持有时间约152天，后续更应优先确认经营与风险是否改善，而不是依赖短线技术信号",
            "key_points": ["当前判断主要基于已披露经营信息与风险信号整理"],
            "risk_focus": [
                "宁德时代当前持仓面临的主要风险并非流动性或信用危机类显性风险，而是结构性预期错配引发的估值再平衡风险",
                "第二风险点为毛利率信息不可用所导致的盈利归因失焦：无法区分当前净利率水平是源于上游原材料价格回落的被动传导，还是自身技术降本能力的真实体现，抑或市场份额策略性让",
            ],
            "watch_items": [
                "当前持仓具备清晰的结构性机会窗口，核心催化来源于盈利质量与成长动能的双重验证兑现",
                "第一类机会来自ROE趋势修复：若2026年中报显示净资产收益率环比明显回升，则高PB估值将获",
            ],
            "uncertainty_note": "当前结论主要基于已披露信息，后续仍需结合财报、公告和行业变化继续验证",
        },
    }
    snapshot = {
        "cost_price": 329.8699,
        "current_price": 434.88,
        "unrealized_pnl_pct": 31.83,
        "holding_days": 152,
    }

    sanitized = sanitize_position_analysis_payload(raw_result, position_snapshot=snapshot)

    assert "技术面" not in sanitized["user_view"]["conclusion"]
    assert "均线" not in sanitized["user_view"]["conclusion"]
    assert "PB" not in " ".join(sanitized["user_view"]["watch_items"])
    assert "已披露经营信息与风险信号整理" not in sanitized["user_view"]["key_points"][0]
    assert len(sanitized["user_view"]["key_points"]) >= 1
    assert all(
        not item.endswith(("将", "让", "获", "并", "但", "与"))
        for item in sanitized["user_view"]["risk_focus"] + sanitized["user_view"]["watch_items"]
    )
    assert "技术面" not in sanitized["action_reason"]
    assert "关键均线" not in sanitized["action_reason"]


def test_sanitize_position_analysis_payload_removes_target_and_stop_loss_language_from_user_view() -> None:
    raw_result = {
        "action_reason": "持有86天浮亏33.1%，成本远高于现价，短期未达目标也未触止损。",
        "risk_assessment": "请重点关注持仓波动、行业变化和公告风险。",
        "opportunity_assessment": "请持续跟踪经营质量、估值变化和潜在催化事件。",
    }
    snapshot = {
        "cost_price": 345.5,
        "current_price": 231.2,
        "unrealized_pnl_pct": -33.1,
        "holding_days": 86,
    }

    sanitized = sanitize_position_analysis_payload(raw_result, position_snapshot=snapshot)

    assert "目标" not in sanitized["action_reason"]
    assert "止损" not in sanitized["action_reason"]
    assert "表现未达到预期" in sanitized["action_reason"]
    assert "进一步恶化信号" in sanitized["action_reason"]
    assert "目标" not in sanitized["user_view"]["position_context"]
    assert "止损" not in sanitized["user_view"]["position_context"]


def test_sanitize_position_analysis_payload_preserves_appendix_sections() -> None:
    raw_result = {
        "detailed_analysis": (
            "【技术面分析】\n短期趋势仍偏弱，但未出现流动性风险。\n\n"
            "【基本面分析】\n经营现金流尚可，但订单修复仍待确认。\n\n"
            "【风险评估】\n若后续回款继续放缓，估值修复节奏可能继续推迟。"
        ),
        "action_reason": "现阶段仍需继续观察。",
    }

    sanitized = sanitize_position_analysis_payload(raw_result)

    assert [section["key"] for section in sanitized["appendix_sections"]] == [
        "technical_analysis",
        "fundamental_analysis",
        "risk_analysis",
    ]
    assert sanitized["appendix_sections"][0]["title"] == "技术面分析"
    assert "短期趋势仍偏弱" in sanitized["appendix_sections"][0]["content"]
    assert "经营现金流尚可" in sanitized["appendix_sections"][1]["content"]
    assert "估值修复节奏可能继续推迟" in sanitized["appendix_sections"][2]["content"]


def test_sanitize_analysis_payload_strips_news_and_sentiment_execution_language() -> None:
    raw_result = {
        "reports": {
            "news_report": "建议买入，目标价12元。\n公司公告显示新产线投产，后续仍需跟踪放量节奏。",
            "sentiment_report": "社交媒体建议加仓并设置止损。\n讨论热度上升，但分歧明显且噪音较多。",
        },
        "summary": "建议买入，目标价12元。",
        "key_points": ["建议买入", "新产线投产"],
    }

    sanitized = sanitize_analysis_payload(raw_result)

    assert "买入" not in sanitized["summary"]
    assert "目标价" not in sanitized["summary"]
    assert "公司公告显示新产线投产" in sanitized["reports"]["news_report"]
    assert "讨论热度上升" in sanitized["reports"]["sentiment_report"]
    assert all("买入" not in point for point in sanitized["key_points"])


def test_sanitize_analysis_payload_demotes_inferential_core_evidence() -> None:
    raw_result = {
        "summary": "等待年报进一步验证。",
        "reports": {
            "market_report": "价格仍处于震荡区间。"
        },
        "decision": {
            "analysis_view": "中性",
            "confidence": 68,
            "risk_score": 52,
            "reasoning": "当前更适合基于已披露数据维持中性研究判断。",
            "core_evidence": ["PB为0.48倍", "零售贷款占比推断超60%"],
            "uncertainties": ["不良贷款率细分数据缺失"],
            "watch_items": ["下一期财报"],
        },
    }

    sanitized = sanitize_analysis_payload(raw_result)

    assert sanitized["decision"]["core_evidence"] == ["PB为0.48倍"]
    assert "零售贷款占比推断超60%" in sanitized["decision"]["uncertainties"]


def test_sanitize_analysis_payload_strips_index_and_sector_execution_language() -> None:
    raw_result = {
        "reports": {
            "index_report": "建议关注3300点支撑位并逢低布局。\n流动性中性，仍需跟踪政策节奏。",
            "sector_report": "新能源板块具备配置建议和安全边际。\n行业景气度修复，但同业分化明显。",
        },
        "summary": "建议关注3300点支撑位并逢低布局。",
        "key_points": ["配置建议", "行业景气度修复"],
    }

    sanitized = sanitize_analysis_payload(raw_result)

    assert "支撑位" not in sanitized["summary"]
    assert "配置建议" not in sanitized["summary"]
    assert "流动性中性" in sanitized["reports"]["index_report"]
    assert "行业景气度修复" in sanitized["reports"]["sector_report"]
    assert all("配置建议" not in point for point in sanitized["key_points"])


def test_sanitize_trade_review_payload_strips_future_trade_actions() -> None:
    raw_result = {
        "summary": "下次可在10元附近买回，并把仓位提升到五成。",
        "timing_analysis": "若回到10.2元可再次买入，跌破9.8元应止损。",
        "position_analysis": "建议下次加仓到50%，并设置止盈。",
        "emotion_analysis": "出现了恐慌卖出，但可以通过预设规则改善。",
        "attribution_analysis": "本次收益更多来自行业回暖，而非稳定的择时能力。",
        "suggestions": ["下次跌到10元买入", "仓位提到50%"],
    }

    sanitized = sanitize_trade_review_payload(raw_result)

    assert "10元" not in sanitized["summary"]
    assert "买入" not in sanitized["timing_analysis"]
    assert "加仓" not in sanitized["position_analysis"]
    assert all("买入" not in item for item in sanitized["suggestions"])
    assert all("50%" not in item for item in sanitized["suggestions"])


def test_sanitize_trade_review_payload_removes_counterfactual_profit_fields() -> None:
    raw_result = {
        "summary": "本次交易的核心问题是退出依据不足。",
        "optimal_pnl": 3200.0,
        "missed_profit": 1800.0,
        "avoided_loss": 0.0,
    }

    sanitized = sanitize_trade_review_payload(raw_result)

    assert "optimal_pnl" not in sanitized
    assert "missed_profit" not in sanitized
    assert "avoided_loss" not in sanitized


def test_sanitize_trade_review_payload_preserves_detail_markdown_blocks() -> None:
    raw_result = {
        "summary": "本次交易的核心问题是归因证据闭环不足。",
        "attribution_analysis": """# 宁德时代（300750）持仓归因复盘报告

## 1. Beta收益分析（大盘贡献）

- 持仓周期内，大盘收益率为 -0.78%。
- 假设该股Beta系数约为1.45，理论Beta收益应为：

Beta收益 = -0.78% × 1.45 = -1.13%

## 2. 行业超额收益分析

- 行业相对大盘并未贡献显著正向超额。
""",
    }

    sanitized = sanitize_trade_review_payload(raw_result)

    assert "理论Beta收益应为：" in sanitized["attribution_analysis"]
    assert "Beta收益 = -0.78% × 1.45 = -1.13%" in sanitized["attribution_analysis"]
    assert "## 2. 行业超额收益分析" in sanitized["attribution_analysis"]
