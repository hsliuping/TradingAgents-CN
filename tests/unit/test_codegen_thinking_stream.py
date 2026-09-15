# -*- coding: utf-8 -*-
"""
Skill 代码生成思考过程流式展示 — 单元测试

覆盖：
1. OpenAICompatAdapter.chat_stream_deltas：reasoning/content 增量产出
2. UnifiedLLMClient.chat_stream：增量回调 + 完整 content 拼接
3. UnifiedLLMClient.chat_stream：适配器不支持流式时回退普通 chat
"""
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

from core.llm.models import LLMConfig, LLMProvider, LLMResponse, Message
from core.llm.providers.openai_compat import OpenAICompatAdapter
from core.llm.unified_client import UnifiedLLMClient


def _make_adapter() -> OpenAICompatAdapter:
    config = LLMConfig(
        provider=LLMProvider.DEEPSEEK,
        model="deepseek-reasoner",
        api_key="test-key",
        base_url="https://api.deepseek.com",
        timeout=60,
        retry_times=1,
    )
    return OpenAICompatAdapter(config)


def _make_chunk(reasoning: Optional[str] = None, content: Optional[str] = None):
    delta = SimpleNamespace(reasoning_content=reasoning, content=content)
    choice = SimpleNamespace(delta=delta)
    return SimpleNamespace(choices=[choice])


class _FakeStreamClient:
    """模拟 OpenAI 同步客户端的流式返回"""

    def __init__(self, chunks):
        self._chunks = chunks
        outer = self

        class _Completions:
            def create(self, **kwargs):
                assert kwargs.get("stream") is True
                return iter(outer._chunks)

        class _Chat:
            completions = _Completions()

        self.chat = _Chat()


class _FakeNonStreamAdapter:
    """无 chat_stream_deltas 的适配器，验证回退路径"""

    def __init__(self):
        self.config = LLMConfig(
            provider=LLMProvider.DEEPSEEK,
            model="deepseek-chat",
            api_key="test-key",
            timeout=60,
            retry_times=1,
        )

    def chat(self, messages, tools=None, **kwargs) -> LLMResponse:
        return LLMResponse(content="完整回复", model="deepseek-chat", finish_reason="stop")


def _messages() -> List[Message]:
    return [Message(role="user", content="生成代码")]


def test_adapter_stream_yields_reasoning_and_content():
    adapter = _make_adapter()
    adapter._sync_client = _FakeStreamClient([
        _make_chunk(reasoning="先分析需求"),
        _make_chunk(reasoning="，再看数据结构"),
        _make_chunk(content="```python"),
        _make_chunk(content="\nprint('hi')\n```"),
    ])

    deltas = list(adapter.chat_stream_deltas(_messages(), max_tokens=128))

    assert deltas == [
        {"type": "reasoning", "text": "先分析需求"},
        {"type": "reasoning", "text": "，再看数据结构"},
        {"type": "content", "text": "```python"},
        {"type": "content", "text": "\nprint('hi')\n```"},
    ]


def test_client_chat_stream_collects_content_and_calls_on_delta():
    adapter = _make_adapter()
    adapter._sync_client = _FakeStreamClient([
        _make_chunk(reasoning="思考中"),
        _make_chunk(content="print"),
        _make_chunk(content="('hi')"),
    ])
    client = UnifiedLLMClient(adapter)

    events: List[Dict[str, str]] = []
    response = client.chat_stream(
        _messages(),
        on_delta=lambda kind, text: events.append({"kind": kind, "text": text}),
        max_tokens=128,
    )

    assert response.content == "print('hi')"
    assert response.model == "deepseek-reasoner"
    assert events == [
        {"kind": "reset", "text": ""},
        {"kind": "reasoning", "text": "思考中"},
        {"kind": "content", "text": "print"},
        {"kind": "content", "text": "('hi')"},
    ]


def test_client_chat_stream_falls_back_to_chat_without_stream_adapter():
    client = UnifiedLLMClient(_FakeNonStreamAdapter())

    events: List[Dict[str, str]] = []
    response = client.chat_stream(
        _messages(),
        on_delta=lambda kind, text: events.append({"kind": kind, "text": text}),
        max_tokens=128,
    )

    assert response.content == "完整回复"
    assert events == [{"kind": "content", "text": "完整回复"}]
