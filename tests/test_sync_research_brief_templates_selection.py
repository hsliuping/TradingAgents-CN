import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "template_upgrades" / "sync_research_brief_templates_to_mongodb.py"
MODULE_SPEC = importlib.util.spec_from_file_location("sync_research_brief_templates_to_mongodb", MODULE_PATH)
assert MODULE_SPEC is not None and MODULE_SPEC.loader is not None
MODULE = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(MODULE)


select_export_template = MODULE.select_export_template


def test_select_export_template_prefers_system_template_over_copy() -> None:
    candidates = [
        {
            "agent_name": "market_analyst_v2",
            "preference_type": "neutral",
            "template_name": "市场分析师 v2.0 - 中性型（副本 2026/01/11 21:34:16）",
            "is_system": False,
            "status": "active",
            "content": {"analysis_requirements": "📊 **输出格式要求（必须严格遵守）：**"},
        },
        {
            "agent_name": "market_analyst_v2",
            "preference_type": "neutral",
            "template_name": "市场分析师 v2.0 - 中性型",
            "is_system": True,
            "status": "active",
            "content": {"analysis_requirements": "## 一、核心观察"},
        },
    ]

    selected = select_export_template(candidates, "market_analyst_v2", "neutral")

    assert selected["is_system"] is True
    assert selected["template_name"] == "市场分析师 v2.0 - 中性型"
    assert selected["content"]["analysis_requirements"] == "## 一、核心观察"


def test_select_export_template_supports_fundamentals_canonical_name() -> None:
    candidates = [
        {
            "agent_name": "fundamentals_analyst_v2",
            "preference_type": "neutral",
            "template_name": "基本面分析师 v2.0 - 中性型（副本 2026/01/11 21:34:06）",
            "is_system": False,
            "status": "active",
            "content": {"output_format": "## 📊 基本面分析报告（中性视角）"},
        },
        {
            "agent_name": "fundamentals_analyst_v2",
            "preference_type": "neutral",
            "template_name": "基本面分析师 v2.0 - 中性型",
            "is_system": True,
            "status": "active",
            "content": {"output_format": "使用 Markdown 输出：一、核心观察；二、财务与经营信号；三、估值背景；四、对整体研究结论的影响；五、待验证问题。"},
        },
    ]

    selected = select_export_template(candidates, "fundamentals_analyst_v2", "neutral")

    assert selected["is_system"] is True
    assert selected["template_name"] == "基本面分析师 v2.0 - 中性型"
    assert "核心观察" in selected["content"]["output_format"]