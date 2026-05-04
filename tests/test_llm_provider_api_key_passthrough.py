from tradingagents.graph.trading_graph import create_llm_by_provider
import tradingagents.llm_adapters.openai_compatible_base as base_module


def test_create_llm_by_provider_passes_api_key_to_custom_openai(monkeypatch):
    captured = {}

    def fake_create_openai_compatible_llm(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(base_module, "create_openai_compatible_llm", fake_create_openai_compatible_llm)

    create_llm_by_provider(
        provider="custom_openai",
        model="qwen3.5-plus",
        backend_url="https://example.com/v1",
        temperature=0.2,
        max_tokens=4000,
        timeout=180,
        api_key="sk-test-custom-openai-key",
    )

    assert captured["provider"] == "custom_openai"
    assert captured["api_key"] == "sk-test-custom-openai-key"


def test_create_llm_by_provider_passes_api_key_to_qianfan(monkeypatch):
    captured = {}

    def fake_create_openai_compatible_llm(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(base_module, "create_openai_compatible_llm", fake_create_openai_compatible_llm)

    create_llm_by_provider(
        provider="qianfan",
        model="ERNIE-Speed-8K",
        backend_url="https://example.com/v2",
        temperature=0.2,
        max_tokens=4000,
        timeout=180,
        api_key="bce-v3/test-ak/test-sk",
    )

    assert captured["provider"] == "qianfan"
    assert captured["api_key"] == "bce-v3/test-ak/test-sk"


def test_create_openai_compatible_llm_forces_kimi_temperature(monkeypatch):
    captured = {}

    class FakeAdapter:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setitem(
        base_module.OPENAI_COMPATIBLE_PROVIDERS["custom_openai"],
        "adapter_class",
        FakeAdapter,
    )

    base_module.create_openai_compatible_llm(
        provider="custom_openai",
        model="kimi-k2.5",
        base_url="https://api.moonshot.cn/v1",
        temperature=0.2,
        max_tokens=4000,
    )

    assert captured["temperature"] == 1.0


def test_create_llm_by_provider_forces_kimi_temperature(monkeypatch):
    captured = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr("tradingagents.graph.trading_graph.ChatOpenAI", FakeChatOpenAI)

    create_llm_by_provider(
        provider="kimi",
        model="kimi-k2.5",
        backend_url="https://api.moonshot.cn/v1",
        temperature=0.2,
        max_tokens=4000,
        timeout=180,
        api_key="sk-test-kimi-key",
    )

    assert captured["temperature"] == 1.0