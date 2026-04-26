from core.workflow.builder import LegacyDependencyProvider, _select_llm_type_for_agent


def test_index_and_sector_v2_agents_use_deep_llm() -> None:
    assert _select_llm_type_for_agent("index_analyst_v2") == "deep"
    assert _select_llm_type_for_agent("sector_analyst_v2") == "deep"


def test_managers_stay_on_deep_llm() -> None:
    assert _select_llm_type_for_agent("research_manager_v2") == "deep"
    assert _select_llm_type_for_agent("risk_manager_v2") == "deep"


def test_regular_analysts_stay_on_quick_llm() -> None:
    assert _select_llm_type_for_agent("market_analyst_v2") == "quick"
    assert _select_llm_type_for_agent("fundamentals_analyst_v2") == "quick"


def test_custom_llm_respects_agent_timeout_and_max_tokens(monkeypatch) -> None:
    captured = {}

    def fake_get_provider_and_url_by_model_sync(model: str):
        return {
            "provider": "dashscope",
            "backend_url": "https://example.com/v1",
            "api_key": "db-key",
        }

    def fake_create_llm_by_provider(**kwargs):
        captured.update(kwargs)
        return kwargs

    monkeypatch.setattr(
        "app.services.simple_analysis_service.get_provider_and_url_by_model_sync",
        fake_get_provider_and_url_by_model_sync,
    )
    monkeypatch.setattr(
        "tradingagents.graph.trading_graph.create_llm_by_provider",
        fake_create_llm_by_provider,
    )

    provider = LegacyDependencyProvider(
        {
            "quick_think_llm": "qwen3.5-plus",
            "quick_timeout": 60,
            "quick_max_tokens": 2000,
        }
    )

    llm = provider.get_llm("quick", temperature=0.6, timeout=120, max_tokens=3200)

    assert llm["temperature"] == 0.6
    assert llm["timeout"] == 120
    assert llm["max_tokens"] == 3200
    assert captured["model"] == "qwen3.5-plus"
