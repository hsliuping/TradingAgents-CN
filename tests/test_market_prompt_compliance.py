import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_market_analyst_v2_templates_are_research_observation_mode() -> None:
    templates_path = ROOT / "exports" / "current_db_templates.json"
    templates = json.loads(templates_path.read_text(encoding="utf-8"))

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
        "核心观察",
        "关键证据与数据依据",
        "对整体研究结论的可能影响",
        "后续观察点",
        "get_stock_market_data_unified",
        "只能使用工具返回的真实数据",
        "可以引用工具返回的真实数值",
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

        for phrase in required_phrases:
            assert phrase in combined_text

        for phrase in output_format_forbidden_phrases:
            assert phrase not in output_format

        assert "不得输出交易建议" in user_prompt
        assert "突破跌破条件" in user_prompt
        assert "不得使用 LLM 自身知识补数据" in user_prompt
        assert "不得把数字写成交易计划、关键执行位或触发条件" in user_prompt
        assert "后续观察点" in analysis_requirements
        assert "不得写成“若突破/跌破某价位”" in analysis_requirements
        assert "工具结果未提供" in combined_text
        assert "禁止脱离工具结果做判断" in combined_text
        assert "允许引用工具结果中的真实数值做事实说明" in combined_text
        assert "不得输出目标价" in analysis_requirements
        assert "不得输出买入、卖出" in analysis_requirements
        assert "不要输出具体价位清单" not in combined_text
        assert "上轨/中轨/下轨具体价位" not in combined_text
        assert "禁止在报告中添加任何署名信息" in combined_text
        assert "禁止生成任何虚假的人名、作者信息或署名" in combined_text