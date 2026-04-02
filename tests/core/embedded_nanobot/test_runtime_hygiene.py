import copy
from unittest.mock import AsyncMock

import pytest

from app.services.embedded_nanobot_service import EmbeddedNanobotService
from core.embedded_nanobot.agent.context import ContextBuilder
from core.embedded_nanobot.agent.runner import AgentRunSpec, AgentRunner
from core.embedded_nanobot.agent.runner import AgentRunResult
from core.embedded_nanobot.agent.tools.base import Tool
from core.embedded_nanobot.agent.tools.tradingagents_bridge import TradingAgentsRegistryTool
from core.embedded_nanobot.agent.tools.registry import ToolRegistry
from core.embedded_nanobot.providers.base import LLMProvider, LLMResponse, ToolCallRequest
from core.embedded_nanobot.runtime import EmbeddedNanobotRuntime
from core.embedded_nanobot.session.manager import Session
from core.embedded_nanobot.utils.helpers import TOOL_RESULT_MAX_CHARS, TRUNCATION_SUFFIX
from core.tools.context import get_current_assistant_thread_id, get_current_user_id
from core.tools.config import ToolMetadata, ToolParameter


class _FakeProvider(LLMProvider):
    def __init__(self, responses: list[LLMResponse]):
        super().__init__()
        self._responses = list(responses)
        self.calls: list[list[dict]] = []

    async def chat(self, messages, tools=None, model=None, max_tokens=4096, temperature=0.7, reasoning_effort=None, tool_choice=None):
        self.calls.append(copy.deepcopy(messages))
        return self._responses.pop(0)

    def get_default_model(self) -> str:
        return "fake-model"


class _LongResultTool(Tool):
    @property
    def name(self) -> str:
        return "long_tool"

    @property
    def description(self) -> str:
        return "Return a long string"

    @property
    def parameters(self) -> dict:
        return {"type": "object", "properties": {}, "required": []}

    async def execute(self, **kwargs):
        return "x" * (TOOL_RESULT_MAX_CHARS + 500)


class _EchoTool(Tool):
    @property
    def name(self) -> str:
        return "echo_tool"

    @property
    def description(self) -> str:
        return "Return a short deterministic result"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
            },
            "required": ["text"],
        }

    async def execute(self, **kwargs):
        return {"echo": kwargs.get("text", "")}


@pytest.mark.asyncio
async def test_runner_truncates_tool_result_before_replay() -> None:
    provider = _FakeProvider([
        LLMResponse(content=None, tool_calls=[ToolCallRequest(id="call_1", name="long_tool", arguments={})]),
        LLMResponse(content="done"),
    ])
    registry = ToolRegistry()
    registry.register(_LongResultTool())

    runner = AgentRunner(provider)
    result = await runner.run(AgentRunSpec(
        initial_messages=[{"role": "user", "content": "run"}],
        tools=registry,
        model="fake-model",
        max_iterations=4,
    ))

    assert result.final_content == "done"
    assert len(provider.calls) == 2
    replayed_tool_message = provider.calls[1][-1]
    assert replayed_tool_message["role"] == "tool"
    assert replayed_tool_message["content"].endswith(TRUNCATION_SUFFIX)
    assert len(replayed_tool_message["content"]) == TOOL_RESULT_MAX_CHARS + len(TRUNCATION_SUFFIX)


@pytest.mark.asyncio
async def test_runner_returns_diagnostic_when_llm_completes_without_visible_content() -> None:
    provider = _FakeProvider([
        LLMResponse(content=None, finish_reason="stop", usage={"prompt_tokens": 10, "completion_tokens": 20}),
    ])
    registry = ToolRegistry()

    runner = AgentRunner(provider)
    result = await runner.run(AgentRunSpec(
        initial_messages=[{"role": "user", "content": "run"}],
        tools=registry,
        model="fake-model",
        max_iterations=2,
    ))

    assert result.stop_reason == "empty_response"
    assert result.final_content is not None
    assert "没有返回可显示的正文内容" in result.final_content


def test_save_turn_strips_runtime_context_and_replaces_image_payload() -> None:
    runtime = EmbeddedNanobotRuntime.__new__(EmbeddedNanobotRuntime)
    runtime.context = type("_Ctx", (), {"_RUNTIME_CONTEXT_TAG": ContextBuilder._RUNTIME_CONTEXT_TAG})()
    session = Session(key="embedded:test")
    runtime_context = ContextBuilder._RUNTIME_CONTEXT_TAG + "\nCurrent Time: now"

    runtime._save_turn(session, [{
        "role": "user",
        "content": [
            {"type": "text", "text": runtime_context},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}, "_meta": {"path": "/tmp/demo.png"}},
            {"type": "text", "text": "请分析这个文件"},
        ],
    }], skip=0)

    assert session.messages == [{
        "role": "user",
        "content": [
            {"type": "text", "text": "[image: /tmp/demo.png]"},
            {"type": "text", "text": "请分析这个文件"},
        ],
        "timestamp": session.messages[0]["timestamp"],
    }]


def test_retain_recent_legal_suffix_keeps_tool_boundary() -> None:
    session = Session(key="embedded:trim")
    session.messages.append({"role": "user", "content": "old"})
    session.messages.append({
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {"id": "old_a", "type": "function", "function": {"name": "x", "arguments": "{}"}},
            {"id": "old_b", "type": "function", "function": {"name": "y", "arguments": "{}"}},
        ],
    })
    session.messages.append({"role": "tool", "tool_call_id": "old_a", "name": "x", "content": "ok"})
    session.messages.append({"role": "tool", "tool_call_id": "old_b", "name": "y", "content": "ok"})
    session.messages.append({"role": "user", "content": "keep"})
    session.messages.append({
        "role": "assistant",
        "content": None,
        "tool_calls": [{"id": "keep_a", "type": "function", "function": {"name": "x", "arguments": "{}"}}],
    })
    session.messages.append({"role": "tool", "tool_call_id": "keep_a", "name": "x", "content": "ok"})
    session.messages.append({"role": "assistant", "content": "done"})

    session.retain_recent_legal_suffix(4)
    history = session.get_history(max_messages=500)

    assert history[0]["role"] == "user"
    assert history[0]["content"] == "keep"
    assert [msg["tool_call_id"] for msg in history if msg.get("role") == "tool"] == ["keep_a"]


def test_runtime_drop_oldest_turn_keeps_latest_turns() -> None:
    history = [
        {"role": "user", "content": "u1"},
        {"role": "assistant", "content": "a1"},
        {"role": "user", "content": "u2"},
        {"role": "assistant", "content": "a2"},
    ]

    trimmed = EmbeddedNanobotRuntime._drop_oldest_turn(history)

    assert trimmed == [
        {"role": "user", "content": "u2"},
        {"role": "assistant", "content": "a2"},
    ]


def test_context_builder_lazy_loads_always_skill_body(tmp_path) -> None:
    skill_dir = tmp_path / "skills" / "always-demo"
    skill_dir.mkdir(parents=True)
    skill_dir.joinpath("SKILL.md").write_text(
        "---\n"
        "name: always-demo\n"
        "description: Demo skill for lazy loading\n"
        "metadata: '{\"nanobot\":{\"always\":true}}'\n"
        "---\n\n"
        "UNIQUE_ALWAYS_SKILL_BODY_SHOULD_NOT_BE_IN_SYSTEM_PROMPT\n",
        encoding="utf-8",
    )

    prompt = ContextBuilder(tmp_path).build_system_prompt()

    assert "always-demo" in prompt
    assert "Demo skill for lazy loading" in prompt
    assert "UNIQUE_ALWAYS_SKILL_BODY_SHOULD_NOT_BE_IN_SYSTEM_PROMPT" not in prompt
    assert "Read a skill's SKILL.md with read_file only when that skill is relevant" in prompt


def test_runtime_build_scoped_tools_excludes_domain_tools_for_greeting(tmp_path) -> None:
    provider = _FakeProvider([])
    runtime = EmbeddedNanobotRuntime(provider=provider, workspace=tmp_path)

    valuation_meta = ToolMetadata(
        id="valuation_tool",
        name="Valuation Tool",
        description="估值分析工具",
        category="fundamentals",
        parameters=[ToolParameter(name="ticker", type="string", description="股票代码", required=True)],
        when_to_use="当用户询问估值、PE、PB、PEG 时使用。",
    )
    runtime.tools.register(TradingAgentsRegistryTool(metadata=valuation_meta, func=lambda ticker: {"ticker": ticker}))

    scoped, selection = runtime._build_scoped_tools("你好")

    assert "read_file" in scoped.tool_names
    assert "valuation_tool" not in scoped.tool_names
    assert selection["selected_dynamic_tools"] == []


def test_runtime_build_scoped_tools_selects_domain_tools_by_query(tmp_path) -> None:
    provider = _FakeProvider([])
    runtime = EmbeddedNanobotRuntime(provider=provider, workspace=tmp_path)

    valuation_meta = ToolMetadata(
        id="valuation_tool",
        name="Valuation Tool",
        description="A股估值分析工具",
        category="fundamentals",
        parameters=[ToolParameter(name="ticker", type="string", description="股票代码", required=True)],
        when_to_use="当用户询问估值、PE、PB、PEG、财务健康度时使用。",
    )
    news_meta = ToolMetadata(
        id="news_tool",
        name="News Tool",
        description="新闻分析工具",
        category="news",
        parameters=[ToolParameter(name="ticker", type="string", description="股票代码", required=True)],
        when_to_use="当用户询问新闻时使用。",
    )
    runtime.tools.register(TradingAgentsRegistryTool(metadata=valuation_meta, func=lambda ticker: {"ticker": ticker}))
    runtime.tools.register(TradingAgentsRegistryTool(metadata=news_meta, func=lambda ticker: {"ticker": ticker}))

    scoped, selection = runtime._build_scoped_tools("分析一下茅台的估值，看看PE和PB")

    assert "valuation_tool" in scoped.tool_names
    assert any(item["name"] == "valuation_tool" for item in selection["selected_dynamic_tools"])


def test_runtime_build_scoped_tools_selects_skill_creation_tools_by_query(tmp_path) -> None:
    provider = _FakeProvider([])
    runtime = EmbeddedNanobotRuntime(provider=provider, workspace=tmp_path)

    skill_meta = ToolMetadata(
        id="start_external_skill_generation_session",
        name="Start External Skill Session",
        description="创建可复用 external skill 的生成会话",
        category="external",
        parameters=[ToolParameter(name="description", type="string", description="需求描述", required=True)],
        when_to_use="当用户明确说这是可复用能力、要沉淀为 skill 而不是 temp 脚本时使用。",
    )
    runtime.tools.register(TradingAgentsRegistryTool(metadata=skill_meta, func=lambda description: {"description": description}))

    scoped, selection = runtime._build_scoped_tools("这个能力后续要复用，别再生成 temp 脚本了，直接做成 skill")

    assert "start_external_skill_generation_session" in scoped.tool_names
    assert "start_external_skill_generation_session" in selection["selected_tool_names"]


@pytest.mark.asyncio
async def test_runtime_build_capped_initial_messages_trims_history_when_over_budget(tmp_path) -> None:
    provider = _FakeProvider([])
    runtime = EmbeddedNanobotRuntime(provider=provider, workspace=tmp_path, context_window_tokens=1200)
    provider.generation = provider.generation.__class__(temperature=0.7, max_tokens=100, reasoning_effort=None)

    def _fake_estimate(_messages, _tools=None, _model=None):
        user_count = sum(1 for item in _messages if item.get("role") == "user")
        return (5000 if user_count > 2 else 100, "fake")

    provider.estimate_prompt_tokens = _fake_estimate  # type: ignore[method-assign]

    session = runtime.sessions.get_or_create("embedded:test")
    session.messages = [
        {"role": "user", "content": "old-user-1"},
        {"role": "assistant", "content": "old-assistant-1"},
        {"role": "user", "content": "old-user-2"},
        {"role": "assistant", "content": "old-assistant-2"},
    ]

    initial_messages, history, estimated_tokens = await runtime._build_capped_initial_messages(
        session,
        runtime.tools,
        user_message="latest-user",
        skill_names=None,
        media=None,
        channel="api",
        chat_id="embedded:test",
    )

    assert estimated_tokens == 100
    assert history == []
    assert initial_messages[-1]["role"] == "user"
    assert "latest-user" in initial_messages[-1]["content"]


@pytest.mark.asyncio
async def test_tradingagents_registry_tool_executes_sync_function() -> None:
    metadata = ToolMetadata(
        id="assistant_tool",
        name="Assistant Tool",
        description="Bridge test tool",
        category="utility",
        parameters=[
            ToolParameter(name="ticker", type="string", description="股票代码", required=True),
            ToolParameter(name="limit", type="integer", description="数量", required=False, default=5),
        ],
    )

    def _tool_impl(ticker: str, limit: int = 5):
        return {"ticker": ticker, "limit": limit}

    tool = TradingAgentsRegistryTool(metadata=metadata, func=_tool_impl)

    assert tool.parameters["required"] == ["ticker"]
    assert tool.parameters["properties"]["limit"]["default"] == 5
    assert await tool.execute(ticker="600519") == {"ticker": "600519", "limit": 5}


@pytest.mark.asyncio
async def test_runtime_sync_registers_registry_tools(monkeypatch, tmp_path) -> None:
    provider = _FakeProvider([])
    runtime = EmbeddedNanobotRuntime(provider=provider, workspace=tmp_path)

    metadata = ToolMetadata(
        id="assistant_tool",
        name="Assistant Tool",
        description="Bridge test tool",
        category="utility",
        parameters=[ToolParameter(name="ticker", type="string", description="股票代码", required=True)],
    )

    class _FakeRegistry:
        def list_all(self):
            return [metadata]

        def get_function(self, tool_id: str):
            if tool_id == "assistant_tool":
                return lambda ticker: {"ticker": ticker}
            return None

    monkeypatch.setattr("core.tools.registry.get_tool_registry", lambda: _FakeRegistry())
    monkeypatch.setattr(runtime, "_hydrate_registry_capabilities", AsyncMock())

    await runtime.sync_tradingagents_capabilities(db=object())

    assert runtime.tools.has("assistant_tool")
    assert await runtime.tools.execute("assistant_tool", {"ticker": "600519"}) == {"ticker": "600519"}


@pytest.mark.asyncio
async def test_embedded_nanobot_service_sets_and_resets_tool_context(monkeypatch, tmp_path) -> None:
    class _FakeRuntime:
        def __init__(self):
            self.seen_user_id = None
            self.seen_thread_id = None

        async def sync_tradingagents_capabilities(self, db) -> None:
            return None

        async def handle_message(self, **kwargs):
            self.seen_user_id = get_current_user_id()
            self.seen_thread_id = get_current_assistant_thread_id()
            return {"content": "ok"}

    fake_runtime = _FakeRuntime()
    service = EmbeddedNanobotService(db=object(), workspace=tmp_path)
    monkeypatch.setattr(service, "get_runtime", AsyncMock(return_value=fake_runtime))

    assert get_current_user_id() is None
    assert get_current_assistant_thread_id() is None

    result = await service.chat(
        user_message="查看我的持仓",
        session_key="embedded:user:test",
        user_id="user-123",
        current_thread_id="thread-456",
        chat_id="thread-456",
    )

    assert result == {"content": "ok"}
    assert fake_runtime.seen_user_id == "user-123"
    assert fake_runtime.seen_thread_id == "thread-456"
    assert get_current_user_id() is None
    assert get_current_assistant_thread_id() is None


@pytest.mark.asyncio
async def test_runtime_handle_message_emits_progress_and_stream_callbacks(tmp_path) -> None:
    provider = _FakeProvider([
        LLMResponse(content=None, tool_calls=[ToolCallRequest(id="call_1", name="echo_tool", arguments={"text": "hello"})]),
        LLMResponse(content="最终答复"),
    ])
    runtime = EmbeddedNanobotRuntime(provider=provider, workspace=tmp_path)
    runtime.tools.register(_EchoTool())

    progress_events: list[str] = []
    streamed_tokens: list[str] = []

    result = await runtime.handle_message(
        user_message="请先调用工具再回复",
        session_key="embedded:test:progress",
        on_progress=progress_events.append,
        on_stream=streamed_tokens.append,
    )

    assert result["content"] == "最终答复"
    assert result["tools_used"] == ["echo_tool"]
    assert streamed_tokens == ["最终答复"]
    assert any("正在准备上下文和可用能力" in item for item in progress_events)
    assert any("准备调用工具: echo_tool" in item for item in progress_events)
    assert any("工具执行完成: echo_tool(ok)" in item for item in progress_events)
    assert any("正在整理最终答复" in item for item in progress_events)