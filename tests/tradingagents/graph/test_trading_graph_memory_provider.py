from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph import trading_graph as trading_graph_module


class _DummyLLM:
    pass


class _FakeMemoryProvider:
    def __init__(self, config=None, memory_enabled=True):
        self.config = config or {}
        self.memory_enabled = memory_enabled
        self.requested = []

    def get_memory(self, memory_name):
        self.requested.append(memory_name)
        return {"memory_name": memory_name}


class _FakeGraphSetup:
    last_init_args = None

    def __init__(self, *args):
        _FakeGraphSetup.last_init_args = args

    def setup_graph(self, selected_analysts):
        return {"selected_analysts": selected_analysts}


class _FakeConditionalLogic:
    def __init__(self, max_debate_rounds=1, max_risk_discuss_rounds=1):
        self.max_debate_rounds = max_debate_rounds
        self.max_risk_discuss_rounds = max_risk_discuss_rounds


def test_trading_graph_initializes_memories_via_memory_provider(monkeypatch):
    fake_provider = _FakeMemoryProvider()

    monkeypatch.setattr(trading_graph_module, "set_config", lambda config: None)
    monkeypatch.setattr(trading_graph_module.os, "makedirs", lambda *args, **kwargs: None)
    monkeypatch.setattr(trading_graph_module, "ChatOpenAI", lambda *args, **kwargs: _DummyLLM())
    monkeypatch.setattr(trading_graph_module, "Toolkit", lambda config=None: object())
    monkeypatch.setattr(trading_graph_module.TradingAgentsGraph, "_create_tool_nodes", lambda self: {})
    monkeypatch.setattr(trading_graph_module, "MemoryProvider", lambda config=None, memory_enabled=True: fake_provider)
    monkeypatch.setattr(trading_graph_module, "GraphSetup", _FakeGraphSetup)
    monkeypatch.setattr(trading_graph_module, "ConditionalLogic", _FakeConditionalLogic)
    monkeypatch.setattr(trading_graph_module, "Reflector", lambda llm: object())
    monkeypatch.setattr(trading_graph_module, "SignalProcessor", lambda llm: object())

    config = DEFAULT_CONFIG.copy()
    config.update(
        {
            "llm_provider": "openai",
            "backend_url": "https://example.test/v1",
            "deep_think_llm": "deep-model",
            "quick_think_llm": "quick-model",
            "memory_enabled": True,
        }
    )

    graph = trading_graph_module.TradingAgentsGraph(selected_analysts=["market"], config=config)

    assert fake_provider.requested == [
        "bull_memory",
        "bear_memory",
        "trader_memory",
        "invest_judge_memory",
        "risk_manager_memory",
    ]
    assert graph.bull_memory == {"memory_name": "bull_memory"}
    assert graph.risk_manager_memory == {"memory_name": "risk_manager_memory"}
    assert _FakeGraphSetup.last_init_args[4] == {"memory_name": "bull_memory"}
    assert _FakeGraphSetup.last_init_args[8] == {"memory_name": "risk_manager_memory"}
