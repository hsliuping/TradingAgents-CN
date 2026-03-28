"""DashScope 适配器的轻量单元测试。"""

from types import SimpleNamespace
from unittest.mock import Mock

from tradingagents.llm_adapters.dashscope_openai_adapter import ChatDashScopeOpenAI


def test_dashscope_adapter_export_available():
    """当前主链路应暴露 OpenAI 兼容适配器。"""
    from tradingagents.llm_adapters import ChatDashScopeOpenAI as exported

    assert exported is ChatDashScopeOpenAI


def test_generate_tracks_token_usage(monkeypatch):
    """_generate 应把 token usage 记入 token_tracker。"""
    llm = ChatDashScopeOpenAI.model_construct(model_name="qwen-turbo")

    tracked = Mock()
    monkeypatch.setattr(
        "tradingagents.llm_adapters.dashscope_openai_adapter.token_tracker.track_usage",
        tracked,
    )

    def fake_super_generate(self, *args, **kwargs):
        return SimpleNamespace(
            llm_output={
                "token_usage": {
                    "prompt_tokens": 12,
                    "completion_tokens": 8,
                }
            }
        )

    monkeypatch.setattr(
        "langchain_openai.ChatOpenAI._generate",
        fake_super_generate,
    )

    result = ChatDashScopeOpenAI._generate(
        llm,
        [],
        session_id="session-1",
        analysis_type="unit-test",
    )

    assert result.llm_output["token_usage"]["prompt_tokens"] == 12
    tracked.assert_called_once_with(
        provider="dashscope",
        model_name="qwen-turbo",
        input_tokens=12,
        output_tokens=8,
        session_id="session-1",
        analysis_type="unit-test",
    )


def test_generate_ignores_missing_token_usage(monkeypatch):
    """缺少 token usage 时不应上报统计，也不应报错。"""
    llm = ChatDashScopeOpenAI.model_construct(model_name="qwen-turbo")

    tracked = Mock()
    monkeypatch.setattr(
        "tradingagents.llm_adapters.dashscope_openai_adapter.token_tracker.track_usage",
        tracked,
    )

    monkeypatch.setattr(
        "langchain_openai.ChatOpenAI._generate",
        lambda self, *args, **kwargs: SimpleNamespace(llm_output={}),
    )

    result = ChatDashScopeOpenAI._generate(llm, [])

    assert result.llm_output == {}
    tracked.assert_not_called()
