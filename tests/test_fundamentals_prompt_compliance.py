import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_fundamentals_analyst_v2_templates_are_research_mode() -> None:
    templates_path = ROOT / "exports" / "current_db_templates.json"
    templates = json.loads(templates_path.read_text(encoding="utf-8"))

    target_templates = [
        item for item in templates
        if item.get("agent_name") == "fundamentals_analyst_v2"
        and item.get("template_name") in {
            "基本面分析师 v2.0 - 激进型",
            "基本面分析师 v2.0 - 中性型",
            "基本面分析师 v2.0 - 保守型",
        }
    ]

    assert len(target_templates) == 3

    required_phrases = [
        "核心观察",
        "财务与经营信号",
        "估值背景",
        "待验证问题",
        "get_financial_statements",
        "get_cash_flow_statement",
    ]

    for template in target_templates:
        content = template["content"]
        combined_text = "\n".join(str(content.get(field, "")) for field in content)
        output_format = str(content.get("output_format", ""))
        user_prompt = str(content.get("user_prompt", ""))
        analysis_requirements = str(content.get("analysis_requirements", ""))

        assert "价格分析区间" not in output_format
        assert "合理价位区间" not in output_format
        assert "上涨空间" not in output_format
        assert "下行空间" not in output_format
        assert "仓位建议" not in output_format
        assert "风险敞口建议" not in output_format
        assert "建议" not in output_format

        assert "不得输出交易建议" in user_prompt
        assert "目标价" in user_prompt
        assert "不得输出" in analysis_requirements
        assert "交易动作" in analysis_requirements
        assert "禁止在报告中添加任何署名信息" in combined_text
        assert "禁止生成任何虚假的人名、作者信息或署名" in combined_text

        for phrase in required_phrases:
            assert phrase in combined_text