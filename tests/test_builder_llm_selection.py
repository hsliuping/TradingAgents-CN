from core.workflow.builder import _select_llm_type_for_agent


def test_index_and_sector_v2_agents_use_deep_llm() -> None:
    assert _select_llm_type_for_agent("index_analyst_v2") == "deep"
    assert _select_llm_type_for_agent("sector_analyst_v2") == "deep"


def test_managers_stay_on_deep_llm() -> None:
    assert _select_llm_type_for_agent("research_manager_v2") == "deep"
    assert _select_llm_type_for_agent("risk_manager_v2") == "deep"


def test_regular_analysts_stay_on_quick_llm() -> None:
    assert _select_llm_type_for_agent("market_analyst_v2") == "quick"
    assert _select_llm_type_for_agent("fundamentals_analyst_v2") == "quick"
