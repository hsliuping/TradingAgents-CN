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