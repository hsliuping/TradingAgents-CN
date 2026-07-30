import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load_module(relative_path: str, module_name: str):
    module_path = ROOT / relative_path
    module_spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert module_spec is not None and module_spec.loader is not None
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


def test_bear_researcher_builder_restores_debate_context_and_source_constraints() -> None:
    module = _load_module(
        "scripts/template_upgrades/update_research_brief_v2_prompts.py",
        "update_research_brief_v2_prompts_bear",
    )

    content = module.build_bear_researcher_content("neutral")

    assert "当前分析市场：{market_name}" in content["system_prompt"]
    assert "请优先使用公司名称“{company_name}”" in content["system_prompt"]
    assert "风险和挑战" in content["analysis_requirements"]
    assert "竞争劣势" in content["analysis_requirements"]
    assert "负面指标" in content["analysis_requirements"]
    assert "偏乐观论点" in content["analysis_requirements"]
    assert "经验教训" in content["analysis_requirements"]
    assert "多轮辩论时" in content["analysis_requirements"]
    assert "本轮暂无新的高质量风险证据" in content["analysis_requirements"]
    assert "本轮暂无新增观察信号" in content["analysis_requirements"]
    assert "社交媒体情绪报告" in content["user_prompt"]
    assert "最新偏乐观论点" in content["user_prompt"]
    assert "反思和经验教训" in content["user_prompt"]
    assert "本轮没有新的观察信号，可以省略该标题" in content["output_format"]
    assert "每个关键论据必须在句末用【】标注来源" in content["output_format"]
    assert "【基本面报告】" in content["analysis_requirements"]
    assert "LLM 内部知识" in content["constraints"]
    assert "报告中未提供此数据" in content["constraints"]
    assert "基于现有报告，无法判断" in content["constraints"]
    assert "2023年" in content["constraints"]
    assert "去年" in content["constraints"]


def test_bear_researcher_aggressive_bias_points_to_downside_not_upside() -> None:
    module = _load_module(
        "scripts/template_upgrades/update_research_brief_v2_prompts.py",
        "update_research_brief_v2_prompts_bear_aggressive",
    )

    content = module.build_bear_researcher_content("aggressive")

    assert "下行催化" in content["system_prompt"]
    assert "上行催化" not in content["system_prompt"]


def test_bear_researcher_fallback_prompt_uses_consistent_placeholders() -> None:
    source = (ROOT / "core/agents/adapters/bear_researcher_v2.py").read_text(encoding="utf-8")

    assert "市场研究报告：{reports.get('market_report', '')}" in source
    assert "市场研究报告：{reports.get('market_research_report', '')}" not in source
    assert "每个关键论据必须在句末用【】标注来源" in source
    assert "最新偏乐观论点" in source
    assert "暂无新增高质量风险证据或前提修正" in source
    assert "本轮没有新的观察信号，可以省略该标题" in source


def test_bull_researcher_builder_and_fallback_allow_incremental_rounds() -> None:
    module = _load_module(
        "scripts/template_upgrades/update_research_brief_v2_prompts.py",
        "update_research_brief_v2_prompts_bull",
    )

    content = module.build_bull_researcher_content("neutral")
    source = (ROOT / "core/agents/adapters/bull_researcher_v2.py").read_text(encoding="utf-8")

    assert "多轮辩论时" in content["analysis_requirements"]
    assert "本轮暂无新的高质量支撑证据" in content["analysis_requirements"]
    assert "本轮暂无新增观察信号" in content["analysis_requirements"]
    assert "本轮没有新的观察信号，可以省略该标题" in content["output_format"]
    assert "市场研究报告：{reports.get('market_report', '')}" in source
    assert "市场研究报告：{reports.get('market_research_report', '')}" not in source
    assert "暂无新增高质量支撑证据或前提修正" in source
    assert "本轮没有新的观察信号，可以省略该标题" in source


def test_research_manager_builder_restores_strongest_case_structure_without_trading_fields() -> None:
    module = _load_module(
        "scripts/template_upgrades/update_research_brief_v2_prompts.py",
        "update_research_brief_v2_prompts_manager",
    )

    content = module.build_research_manager_content("neutral")

    assert "双方最强的成立逻辑" in content["system_prompt"]
    assert "先按双方最强论点等权审阅" in content["system_prompt"]
    assert "看多与看空各自最强的 2-3 条成立逻辑" in content["analysis_requirements"]
    assert "共识点" in content["analysis_requirements"]
    assert "分歧根源" in content["analysis_requirements"]
    assert "市场定价是否已反映预期" in content["analysis_requirements"]
    assert "多方最强依据 -> 空方最强依据 -> 共识点 -> 分歧根源 -> 最终判断" in content["analysis_requirements"]
    assert "多方最强依据、空方最强依据、双方共识、关键分歧根源" in content["output_format"]
    assert "price_analysis_range" not in content["output_format"]
    assert "risk_exposure_ratio" not in content["output_format"]
    assert "投资机会" not in content["user_prompt"]


def test_research_manager_fallback_tracks_structured_reasoning_without_old_trading_language() -> None:
    source = (ROOT / "core/agents/adapters/research_manager_v2.py").read_text(encoding="utf-8")

    assert "不要把任一方写成稻草人" in source
    assert "分歧主要来自数据解读、前提假设、时间维度还是市场定价反映程度" in source
    assert "市场是否已经计入部分乐观/悲观预期" in source
    assert "乐观情景最强依据、审慎情景最强依据、双方共识、关键分歧根源" in source
    assert "投资机会" not in source


def test_trader_builder_and_fallback_prioritize_manager_judgment_without_trading_regression() -> None:
    module = _load_module(
        "scripts/template_upgrades/update_research_brief_v2_prompts.py",
        "update_research_brief_v2_prompts_trader",
    )

    content = module.build_trader_content("neutral")
    source = (ROOT / "core/agents/adapters/trader_v2.py").read_text(encoding="utf-8")

    assert "一句话结论要像对朋友解释" in content["system_prompt"]
    assert "不要把所有报告平均复述成流水账" in content["system_prompt"]
    assert "不要直接写‘估值修复逻辑’‘提供防御’‘材料未提供’‘风险审阅结论未提供’‘投资决策材料未提供’" in content["system_prompt"]
    assert "整篇用户版研究简报正文总长度控制在 500-800 个中文字符之间" in content["analysis_requirements"]
    assert "不要把‘低 PB’直接塞进一句话结论" in content["analysis_requirements"]
    assert "500-800 个中文字符" in content["analysis_requirements"]
    assert "完整白话段落" in content["output_format"]
    assert "历史交易记录只能作为背景参考" in content["analysis_requirements"]
    assert "用户版简报要像对普通人解释" in content["user_prompt"]
    assert "不能只写成几句很短的话" in content["user_prompt"]
    assert "历史交易记录只能作为背景" in content["user_prompt"]
    assert "一句话结论" in source
    assert "历史交易记录" in source
    assert "研究简报" in source
    assert "不构成投资建议" in source


def test_trader_runtime_keeps_sentiment_report_and_structured_plan_rendering() -> None:
    trader_source = (ROOT / "core/agents/trader.py").read_text(encoding="utf-8")
    adapter_source = (ROOT / "core/agents/adapters/trader_v2.py").read_text(encoding="utf-8")

    assert '"sentiment_report"' in trader_source
    assert 'reports["sentiment_report"] = state["social_report"]' in trader_source
    assert "extract_content(all_reports.get(\"sentiment_report\", \"\"))" in adapter_source
    assert "一句话结论" in adapter_source
    assert "历史交易记录" in adapter_source