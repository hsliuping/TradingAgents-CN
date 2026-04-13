import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _load_templates(relative_path: str):
    payload = json.loads((ROOT / relative_path).read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    return payload.get("data", {}).get("prompt_templates", [])


@pytest.mark.parametrize(
    "relative_path",
    [
        "exports/current_db_templates.json",
        "install/database_export_config_2026-02-10.json",
    ],
)
def test_market_analyst_v2_templates_are_research_observation_mode(relative_path: str) -> None:
    templates = _load_templates(relative_path)

    target_templates = [
        item for item in templates
        if item.get("agent_name") == "market_analyst_v2"
        and item.get("template_name") in {
            "市场分析师 v2.0 - 激进型",
            "市场分析师 v2.0 - 中性型",
            "市场分析师 v2.0 - 保守型",
        }
    ]

    assert len(target_templates) == 3

    required_phrases = [
        "股票基本信息",
        "技术指标分析",
        "移动平均线（MA）分析",
        "MACD指标分析",
        "RSI相对强弱指标",
        "布林带（BOLL）分析",
        "价格趋势分析",
        "短期趋势（5-10个交易日）",
        "中期趋势（20-60个交易日）",
        "成交量分析",
        "综合评估",
        "对整体研究结论的影响",
        "后续观察点",
        "get_stock_market_data_unified",
        "实际数据日期",
        "短期与中期信号冲突",
        "只能使用工具返回的真实价格、技术指标与成交数据",
        "可以引用工具返回的真实数值",
        "表达方式示例",
        "若工具结果只提供当前值、最近5日统计或单次快照",
        "均线排列关系",
        "均线斜率方向",
        "只说明这些信号对整体研究是强化、削弱还是中性及其原因",
        "后续文字必须与表格和数值一致",
        "后续观察点不要写成“是否站稳于MA5之上”",
        "不能写成“MA60 高于 MA20”",
        "不要写“未形成有效突破”",
        "不要写“尚未站稳于MA5之上”",
        "柱状图是否出现持续放大",
        "具备一定上行空间",
        "输出前必须做一次逐词自检",
        "不得出现“站上”“站稳”",
    ]

    output_format_forbidden_phrases = [
        "目标价",
        "价格区间",
        "支撑位",
        "阻力位",
        "关键价位",
        "突破看涨价",
        "跌破看跌价",
        "风险收益比",
        "仓位比例",
    ]

    for template in target_templates:
        content = template["content"]
        combined_text = "\n".join(str(content.get(field, "")) for field in content)
        analysis_requirements = str(content.get("analysis_requirements", ""))
        user_prompt = str(content.get("user_prompt", ""))
        output_format = str(content.get("output_format", ""))
        constraints = str(content.get("constraints", ""))

        for phrase in required_phrases:
            assert phrase in combined_text

        for phrase in output_format_forbidden_phrases:
            assert phrase not in output_format

        assert "不得输出交易建议" in user_prompt
        assert "支撑阻力位" in user_prompt
        assert "突破跌破条件" in user_prompt
        assert "不得使用 LLM 自身知识补数据" in user_prompt
        assert "不得把数字写成目标价、支撑阻力位、关键执行位、触发阈值或交易计划" in user_prompt
        assert "如果短期与中期信号冲突" in user_prompt
        assert "实际数据日期" in user_prompt
        assert "可以写：" in user_prompt
        assert "不得写：" in user_prompt
        assert "股票基本信息" in analysis_requirements
        assert "技术指标分析" in analysis_requirements
        assert "移动平均线（MA）分析" in analysis_requirements
        assert "MACD指标分析" in analysis_requirements
        assert "RSI相对强弱指标" in analysis_requirements
        assert "布林带（BOLL）分析" in analysis_requirements
        assert "价格趋势分析" in analysis_requirements
        assert "综合评估" in analysis_requirements
        assert "当前价格、涨跌幅和成交量" in analysis_requirements
        assert "正常情况下不少于800字" in combined_text
        assert "后续观察点" in analysis_requirements
        assert "如果短期与中期信号冲突" in analysis_requirements
        assert "实际数据日期" in analysis_requirements
        assert "表达方式示例" in analysis_requirements
        assert "工具结果未提供" in combined_text
        assert "只能基于工具返回的真实价格、技术指标与成交数据做判断" in combined_text
        assert "允许引用真实数值做事实说明" in combined_text
        assert "柱状图持续放大" in combined_text
        assert "不得输出投资评级" in analysis_requirements
        assert "不得输出目标价" in analysis_requirements
        assert "不得输出买入、卖出" in analysis_requirements
        assert "突破 32.5 元即可确认主升浪" in combined_text
        assert "支撑位 28 元，跌破则止损" in combined_text
        assert "价格分析区间" in combined_text
        assert "禁止在报告中添加任何署名信息" in constraints
        assert "禁止生成任何虚假的人名、作者信息或署名" in constraints