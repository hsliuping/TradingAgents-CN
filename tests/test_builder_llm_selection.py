from types import SimpleNamespace

from core.workflow.builder import LegacyDependencyProvider, WorkflowBuilder, _select_llm_type_for_agent


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


def test_workflow_builder_passes_agent_llm_overrides(monkeypatch) -> None:
    from core.agents import AgentConfig

    captured = {}

    builder = WorkflowBuilder.__new__(WorkflowBuilder)
    builder.registry = SimpleNamespace(is_registered=lambda agent_id: True)
    builder.factory = SimpleNamespace(create=lambda *args, **kwargs: SimpleNamespace())
    builder.default_config = AgentConfig()
    builder.binding_manager = SimpleNamespace(get_tools_for_node=lambda **kwargs: [])
    builder.agent_config_manager = SimpleNamespace(
        get_agent_config=lambda agent_id: {
            "config": {
                "temperature": 0.6,
                "timeout": 180,
                "max_tokens": 3200,
            }
        }
    )
    builder.memory_manager = None
    builder.llm_override = None
    builder._agents = {}
    builder._workflow_id = "wf-test"
    builder._has_agent_config_in_db = lambda agent_id: False
    builder._ensure_workflow_surface_access = lambda agent_id, db_agent_config=None: None
    builder._resolve_agent_output_field = lambda *args, **kwargs: None
    builder._execute_agent_node_with_runtime = lambda **kwargs: kwargs
    builder._legacy_provider = SimpleNamespace(
        get_llm=lambda llm_type, temperature=None, timeout=None, max_tokens=None: captured.update(
            {
                "llm_type": llm_type,
                "temperature": temperature,
                "timeout": timeout,
                "max_tokens": max_tokens,
            }
        ) or SimpleNamespace(),
        get_toolkit=lambda: None,
    )

    node = SimpleNamespace(
        id="risk-node",
        type="risk",
        agent_id="risky_analyst_v2",
        label="风险分析",
        config={},
    )

    builder._create_agent_node(node)

    assert captured == {
        "llm_type": "deep",
        "temperature": 0.6,
        "timeout": 180,
        "max_tokens": 3200,
    }
