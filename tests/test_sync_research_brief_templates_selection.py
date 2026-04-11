import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "template_upgrades" / "sync_research_brief_templates_to_mongodb.py"
MODULE_SPEC = importlib.util.spec_from_file_location("sync_research_brief_templates_to_mongodb", MODULE_PATH)
assert MODULE_SPEC is not None and MODULE_SPEC.loader is not None
MODULE = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(MODULE)


select_export_template = MODULE.select_export_template
select_db_doc_for_sync = MODULE._select_db_doc_for_sync


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


def test_select_export_template_supports_social_and_sector_canonical_names() -> None:
    social_candidates = [
        {
            "agent_name": "social_analyst_v2",
            "preference_type": "neutral",
            "template_name": "社交分析师 v2.0 - 中性型（副本 2026/01/11 21:33:55）",
            "is_system": False,
            "status": "active",
            "content": {"analysis_requirements": "旧版情绪分析"},
        },
        {
            "agent_name": "social_analyst_v2",
            "preference_type": "neutral",
            "template_name": "社交分析师 v2.0 - 中性型",
            "is_system": True,
            "status": "active",
            "content": {"analysis_requirements": "## 情绪方向与热度"},
        },
    ]
    sector_candidates = [
        {
            "agent_name": "sector_analyst_v2",
            "preference_type": "neutral",
            "template_name": "行业分析师 v2.0 - 中性型（副本 2026/01/11 21:33:57）",
            "is_system": False,
            "status": "active",
            "content": {"analysis_requirements": "旧版行业分析"},
        },
        {
            "agent_name": "sector_analyst_v2",
            "preference_type": "neutral",
            "template_name": "行业分析师 v2.0 - 中性型",
            "is_system": True,
            "status": "active",
            "content": {"analysis_requirements": "## 行业景气度"},
        },
    ]

    social_selected = select_export_template(social_candidates, "social_analyst_v2", "neutral")
    sector_selected = select_export_template(sector_candidates, "sector_analyst_v2", "neutral")

    assert social_selected["template_name"] == "社交分析师 v2.0 - 中性型"
    assert sector_selected["template_name"] == "行业分析师 v2.0 - 中性型"
    assert "情绪方向与热度" in social_selected["content"]["analysis_requirements"]
    assert "行业景气度" in sector_selected["content"]["analysis_requirements"]


def test_select_db_doc_for_sync_prefers_system_template_and_archives_copy() -> None:
    export_doc = {
        "template_name": "新闻分析师 v2.0 - 中性型",
        "content": {"analysis_requirements": "## 核心事件"},
    }
    candidates = [
        {
            "_id": "system-id",
            "agent_name": "news_analyst_v2",
            "preference_type": "neutral",
            "template_name": "新闻分析师 v2.0 - 中性型",
            "is_system": True,
            "status": "active",
            "version": 3,
            "remark": "正式模板",
        },
        {
            "_id": "copy-id",
            "agent_name": "news_analyst_v2",
            "preference_type": "neutral",
            "template_name": "新闻分析师 v2.0 - 中性型（副本 2026/02/12 13:51:42）",
            "is_system": False,
            "status": "active",
            "version": 6,
            "remark": "副本模板",
        },
    ]

    selected, duplicates = select_db_doc_for_sync(candidates, export_doc)

    assert selected["_id"] == "system-id"
    assert [item["_id"] for item in duplicates] == ["copy-id"]