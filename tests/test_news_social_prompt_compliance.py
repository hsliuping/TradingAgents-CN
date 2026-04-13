import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _load_module(relative_path: str, module_name: str):
    module_path = ROOT / relative_path
    module_spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert module_spec is not None and module_spec.loader is not None
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


def _load_templates(relative_path: str):
    payload = json.loads((ROOT / relative_path).read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    return payload.get("data", {}).get("prompt_templates", [])


def test_legacy_news_analyst_migration_keeps_inline_validation_note_only() -> None:
    module = _load_module(
        "scripts/compliance/migrate_prompt_templates_to_research_mode.py",
        "migrate_prompt_templates_to_research_mode_legacy_news",
    )

    legacy_output_format = module.transform_text("original", "news_analyst", "output_format", "news_analyst")
    legacy_user_prompt = module.transform_text("original", "news_analyst", "user_prompt", "news_analyst")
    legacy_system_prompt = module.transform_text("original", "news_analyst", "system_prompt", "news_analyst")
    v2_output_format = module.transform_text("original", "news_analyst", "output_format", "news_analyst_v2")

    assert "四、待验证问题" not in legacy_output_format
    assert "无需另起章节" in legacy_output_format
    assert "4. 待继续验证的问题" not in legacy_user_prompt
    assert "无需另起章节" in legacy_user_prompt
    assert "只输出研究观察、证据说明与影响评估" in legacy_system_prompt
    assert "风险提示和待验证问题" not in legacy_system_prompt
    assert "四、待验证问题" in v2_output_format


def test_legacy_news_analyst_export_template_uses_three_section_format() -> None:
    templates = _load_templates("exports/current_db_templates.json")

    target_templates = [
        item
        for item in templates
        if item.get("agent_name") == "news_analyst"
        and item.get("template_name") == "System Neutral Template"
    ]

    assert len(target_templates) == 1

    content = target_templates[0]["content"]
    system_prompt = str(content.get("system_prompt", ""))
    analysis_requirements = str(content.get("analysis_requirements", ""))
    output_format = str(content.get("output_format", ""))

    assert "四、待验证问题" not in output_format
    assert output_format.startswith("使用 Markdown 输出：一、核心观察；二、关键证据；三、影响评估。")
    assert "无需另起章节" in output_format
    assert "只输出研究观察、证据说明与影响评估" in system_prompt
    assert "风险提示和待验证问题" not in system_prompt
    assert "必须同时给出证据来源与结论影响" in analysis_requirements
    assert "无需另起章节" in analysis_requirements


@pytest.mark.parametrize(
    "relative_path",
    [
        "exports/current_db_templates.json",
        "install/database_export_config_2026-02-10.json",
    ],
)
def test_news_analyst_v2_templates_follow_legacy_structure_with_compliance(relative_path: str) -> None:
    templates = _load_templates(relative_path)

    target_templates = [
        item
        for item in templates
        if item.get("agent_name") == "news_analyst_v2"
        and item.get("template_name")
        in {
            "新闻分析师 v2.0 - 激进型",
            "新闻分析师 v2.0 - 中性型",
            "新闻分析师 v2.0 - 保守型",
        }
    ]

    assert len(target_templates) == 3

    required_phrases = [
        "最新新闻汇总",
        "新闻影响分析",
        "市场情绪评估",
        "分析观点",
        "短期反应预期",
        "对整体研究结论的影响",
        "新闻面评估",
        "对整体研究结论的影响",
        "get_stock_news_unified",
        "多个标题本质上描述同一事件",
        "如果工具只返回标题",
        "工具结果未提供",
        "偏积极",
        "偏审慎",
        "重大利好",
        "短期市场反应预期",
        "不少于700字",
    ]

    output_format_forbidden_phrases = [
        "目标价",
        "价格区间",
        "支撑位",
        "阻力位",
        "仓位",
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

        assert "客观中立" in user_prompt
        assert "最新新闻事件汇总" in user_prompt
        assert "市场情绪变化评估" in user_prompt
        assert "短期市场反应预期" in user_prompt
        assert "工具结果未提供" in user_prompt
        assert "不得补造细节" in user_prompt
        assert "不要输出投资建议、目标价、价格区间、仓位计划或任何执行指令" in user_prompt
        assert "新闻分类分析" in analysis_requirements
        assert "影响评估" in analysis_requirements
        assert "分析观点" in analysis_requirements
        assert "无需单列章节" in analysis_requirements
        assert "对整体研究结论的影响" in analysis_requirements
        assert "短期市场反应预期（1-3天）" in analysis_requirements
        assert "新闻分析报告" in output_format
        assert "市场情绪评估" in output_format
        assert "分析观点" in output_format
        assert "待验证问题" not in output_format
        assert "禁止在报告中添加任何署名信息" in constraints


@pytest.mark.parametrize(
    "relative_path",
    [
        "exports/current_db_templates.json",
        "install/database_export_config_2026-02-10.json",
    ],
)
def test_social_analyst_v2_templates_follow_legacy_structure_with_compliance(relative_path: str) -> None:
    templates = _load_templates(relative_path)

    target_templates = [
        item
        for item in templates
        if item.get("agent_name") == "social_analyst_v2"
        and item.get("template_name")
        in {
            "社交分析师 v2.0 - 激进型",
            "社交分析师 v2.0 - 中性型",
            "社交分析师 v2.0 - 保守型",
        }
    ]

    assert len(target_templates) == 3

    required_phrases = [
        "情绪方向与热度",
        "观点结构与渠道差异",
        "情绪变化与分化",
        "噪音与风险",
        "对整体研究结论的影响",
        "后续观察事项",
        "get_stock_sentiment_unified",
        "如果工具明确说明当前结果来自新闻回退情绪摘要",
        "不要分析该维度",
        "工具结果未提供",
        "偏积极",
        "偏审慎",
        "情绪拐点已至",
        "全面看多",
        "不少于700字",
    ]

    output_format_forbidden_phrases = [
        "目标价",
        "价格区间",
        "支撑位",
        "阻力位",
        "仓位",
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

        assert "客观中立" in user_prompt
        assert "该维度暂不分析" in user_prompt
        assert "新闻回退情绪摘要" in user_prompt
        assert "持续升温" in user_prompt
        assert "不要输出投资建议、目标价、价格区间、仓位计划或任何执行指令" in user_prompt
        assert "观点结构与渠道差异" in analysis_requirements
        assert "情绪变化与分化" in analysis_requirements
        assert "对整体研究结论的影响" in analysis_requirements
        assert "禁止在报告中添加任何署名信息" in constraints
