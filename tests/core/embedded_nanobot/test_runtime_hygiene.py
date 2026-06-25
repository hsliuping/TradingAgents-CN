import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.services.embedded_nanobot_service import EmbeddedNanobotService
from core.embedded_nanobot.agent.context import ContextBuilder
from core.embedded_nanobot.agent.memory import MemoryStore
from core.embedded_nanobot.agent.runner import AgentRunSpec, AgentRunner
from core.embedded_nanobot.agent.runner import AgentRunResult
from core.embedded_nanobot.agent.tools.base import Tool
from core.embedded_nanobot.agent.tools.tradingagents_bridge import TradingAgentsRegistryTool
from core.embedded_nanobot.agent.tools.registry import ToolRegistry
from core.memory.models import StoreResult
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


class _PublishSensitiveProvider(LLMProvider):
    def __init__(self):
        super().__init__()
        self.calls: list[list[dict]] = []

    async def chat(self, messages, tools=None, model=None, max_tokens=4096, temperature=0.7, reasoning_effort=None, tool_choice=None):
        del tools, model, max_tokens, temperature, reasoning_effort, tool_choice
        self.calls.append(copy.deepcopy(messages))
        if len(self.calls) == 1:
            return LLMResponse(
                content=None,
                tool_calls=[
                    ToolCallRequest(
                        id="call_test",
                        name="run_agent_workshop_real_data_test",
                        arguments={
                            "version_id": "spec_test_agent_v3",
                            "stock_symbol": "000002",
                        },
                    )
                ],
            )

        joined_content = "\n".join(
            str(message.get("content") or "")
            for message in messages
            if isinstance(message, dict)
        )
        if (
            "user explicitly confirms publication in the current turn" in joined_content
            and "must not trigger automatic publication" in joined_content
        ):
            return LLMResponse(content="真数据测试已通过，当前状态为待确认发布；如需正式发布，请由用户手动确认。")

        if len(self.calls) == 2:
            return LLMResponse(
                content=None,
                tool_calls=[
                    ToolCallRequest(
                        id="call_publish",
                        name="publish_agent_workshop_version",
                        arguments={"version_id": "spec_test_agent_v3"},
                    )
                ],
            )

        return LLMResponse(content="版本已自动发布。")

    def get_default_model(self) -> str:
        return "fake-model"


class _FakeCursor:
    def __init__(self, items: list[dict]):
        self._items = list(items)

    def sort(self, key, direction):
        reverse = direction == -1
        self._items.sort(key=lambda item: item.get(key), reverse=reverse)
        return self

    def limit(self, count: int):
        self._items = self._items[:count]
        return self

    def __aiter__(self):
        self._index = 0
        return self

    async def __anext__(self):
        if self._index >= len(self._items):
            raise StopAsyncIteration
        item = self._items[self._index]
        self._index += 1
        return dict(item)


class _FakeInsertOneResult:
    def __init__(self, inserted_id: str):
        self.inserted_id = inserted_id


class _FakeUpdateResult:
    def __init__(self, modified_count: int = 0):
        self.modified_count = modified_count


class _FakeCollection:
    def __init__(self, items: list[dict] | None = None):
        self._items = list(items or [])

    @staticmethod
    def _get_nested(item: dict, key: str):
        current = item
        for part in key.split('.'):
            if not isinstance(current, dict) or part not in current:
                return None
            current = current[part]
        return current

    @classmethod
    def _match(cls, item: dict, query: dict | None):
        for key, expected in (query or {}).items():
            actual = cls._get_nested(item, key)
            if isinstance(expected, dict):
                if "$ne" in expected and actual == expected["$ne"]:
                    return False
                if "$in" in expected and actual not in expected["$in"]:
                    return False
                continue
            if actual != expected:
                return False
        return True

    @staticmethod
    def _set_nested(item: dict, key: str, value):
        current = item
        parts = key.split('.')
        for part in parts[:-1]:
            current = current.setdefault(part, {})
        current[parts[-1]] = value

    def find(self, query=None):
        return _FakeCursor([item for item in self._items if self._match(item, query)])

    async def find_one(self, query=None):
        for item in self._items:
            if self._match(item, query):
                return dict(item)
        return None

    async def update_one(self, query, update, upsert=False):
        target = None
        for item in self._items:
            if self._match(item, query):
                target = item
                break
        if target is None and upsert:
            target = dict(query)
            self._items.append(target)
        if target is None:
            return _FakeUpdateResult(0)
        for key, value in update.get("$setOnInsert", {}).items():
            if upsert and key not in target:
                self._set_nested(target, key, value)
        for key, value in update.get("$set", {}).items():
            self._set_nested(target, key, value)
        for key, value in update.get("$inc", {}).items():
            current = self._get_nested(target, key) or 0
            self._set_nested(target, key, current + value)
        return _FakeUpdateResult(1)

    async def insert_one(self, document):
        self._items.append(dict(document))
        return _FakeInsertOneResult(str(document.get("message_id") or len(self._items)))


class _FakeDb:
    def __init__(self, collections: dict[str, _FakeCollection]):
        self._collections = collections

    def __getitem__(self, name: str):
        return self._collections[name]


class _FakeMemoryService:
    def __init__(self, result: StoreResult):
        self.result = result
        self.calls: list[dict[str, Any]] = []
        self.recall_calls: list[dict[str, Any]] = []
        self.recall_text = ""

    async def store(self, messages, **kwargs):
        self.calls.append({"messages": messages, **kwargs})
        return self.result

    async def recall_formatted(self, **kwargs):
        self.recall_calls.append(dict(kwargs))
        return self.recall_text


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


class _StructuredEventTool(Tool):
    @property
    def name(self) -> str:
        return "structured_event_tool"

    @property
    def description(self) -> str:
        return "Return structured tool-stage events"

    @property
    def parameters(self) -> dict:
        return {"type": "object", "properties": {}, "required": []}

    async def execute(self, **kwargs):
        del kwargs
        return '{"status":"error","message":"组合工具失败","_tool_events":[{"name":"structured_event_tool.stage_a","status":"ok","detail":"阶段A完成"},{"name":"structured_event_tool.stage_b","status":"error","detail":"阶段B失败"}]}'


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


@pytest.mark.asyncio
async def test_runner_expands_structured_tool_events() -> None:
    provider = _FakeProvider([
        LLMResponse(content=None, tool_calls=[ToolCallRequest(id="call_1", name="structured_event_tool", arguments={})]),
        LLMResponse(content="handled"),
    ])
    registry = ToolRegistry()
    registry.register(_StructuredEventTool())

    runner = AgentRunner(provider)
    result = await runner.run(AgentRunSpec(
        initial_messages=[{"role": "user", "content": "run"}],
        tools=registry,
        model="fake-model",
        max_iterations=4,
    ))

    assert result.final_content == "handled"
    assert [event["name"] for event in result.tool_events] == [
        "structured_event_tool.stage_a",
        "structured_event_tool.stage_b",
    ]
    assert result.tool_events[1]["status"] == "error"


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
    assert "When the user asks which prompt template is currently active or effective in the current thread" in prompt
    assert "Do not infer the effective prompt template from agent_name alone" in prompt


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
    assert selection["category_matches"] == {}




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
    assert selection["category_matches"]["fundamentals"] == ["估值", "pe", "pb"]
    valuation_item = next(item for item in selection["selected_dynamic_tools"] if item["name"] == "valuation_tool")
    assert valuation_item["matched_category_terms"] == ["估值", "pe", "pb"]


def test_runtime_build_scoped_tools_includes_prompt_template_tools_for_template_query(tmp_path) -> None:
    provider = _FakeProvider([])
    runtime = EmbeddedNanobotRuntime(provider=provider, workspace=tmp_path)

    effective_meta = ToolMetadata(
        id="get_effective_prompt_template",
        name="Get Effective Prompt Template",
        description="查询当前生效模板",
        category="assistant_ops",
        parameters=[],
        when_to_use="当用户询问当前模板、生效模板、调试模板时使用。",
    )
    inspect_meta = ToolMetadata(
        id="inspect_prompt_templates",
        name="Inspect Prompt Templates",
        description="检索模板库",
        category="assistant_ops",
        parameters=[],
        when_to_use="当用户要浏览或搜索模板库时使用。",
    )
    detail_meta = ToolMetadata(
        id="get_prompt_template_detail",
        name="Get Prompt Template Detail",
        description="读取模板详情",
        category="assistant_ops",
        parameters=[],
        when_to_use="当用户要查看某个模板全文或详细元数据时使用。",
    )
    current_effective_meta = ToolMetadata(
        id="get_current_thread_effective_prompt_template",
        name="Get Current Thread Effective Prompt Template",
        description="基于当前线程查询当前生效模板",
        category="assistant_ops",
        parameters=[],
        when_to_use="当用户询问当前线程里实际生效的模板时使用。",
    )
    runtime.tools.register(TradingAgentsRegistryTool(metadata=effective_meta, func=lambda: {"ok": True}))
    runtime.tools.register(TradingAgentsRegistryTool(metadata=inspect_meta, func=lambda: {"ok": True}))
    runtime.tools.register(TradingAgentsRegistryTool(metadata=detail_meta, func=lambda: {"ok": True}))
    runtime.tools.register(TradingAgentsRegistryTool(metadata=current_effective_meta, func=lambda: {"ok": True}))

    scoped, selection = runtime._build_scoped_tools("现在调试态下当前生效模板是哪一个？")

    assert "get_effective_prompt_template" in scoped.tool_names
    assert "get_current_thread_effective_prompt_template" in scoped.tool_names
    assert "inspect_prompt_templates" in scoped.tool_names
    assert "get_prompt_template_detail" in scoped.tool_names
    assert "get_current_thread_effective_prompt_template" in selection["selected_tool_names"]
    assert "get_effective_prompt_template" in selection["selected_tool_names"]


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


def test_runtime_build_scoped_tools_prefers_callable_agents_for_integrated_request(tmp_path) -> None:
    provider = _FakeProvider([])
    runtime = EmbeddedNanobotRuntime(provider=provider, workspace=tmp_path)

    list_meta = ToolMetadata(
        id="list_callable_agents",
        name="List Callable Agents",
        description="列出可直接调用的完整 Agent 能力",
        category="assistant_ops",
        parameters=[ToolParameter(name="keyword", type="string", description="关键词", required=False)],
        when_to_use="当用户要做完整估值、研究、复盘、风险分析任务时，先检查是否已有可复用 Agent。",
    )
    execute_meta = ToolMetadata(
        id="execute_callable_agent",
        name="Execute Callable Agent",
        description="调用完整 Agent 能力",
        category="assistant_ops",
        parameters=[ToolParameter(name="agent_identifier", type="string", description="Agent 标识", required=True)],
        when_to_use="确认已有合适 Agent 后，优先直接调用完整 Agent，而不是拆多个底层工具。",
    )
    valuation_meta = ToolMetadata(
        id="valuation_tool",
        name="Valuation Tool",
        description="A股估值底层工具",
        category="fundamentals",
        parameters=[ToolParameter(name="ticker", type="string", description="股票代码", required=True)],
        when_to_use="当没有合适完整 Agent 时，才作为底层估值工具使用。",
    )

    runtime.tools.register(TradingAgentsRegistryTool(metadata=list_meta, func=lambda keyword=None: {"keyword": keyword}))
    runtime.tools.register(TradingAgentsRegistryTool(metadata=execute_meta, func=lambda agent_identifier: {"agent_identifier": agent_identifier}))
    runtime.tools.register(TradingAgentsRegistryTool(metadata=valuation_meta, func=lambda ticker: {"ticker": ticker}))

    scoped, selection = runtime._build_scoped_tools("帮我做一下茅台的估值分析，给我一份完整结论")

    assert "list_callable_agents" in scoped.tool_names
    assert "execute_callable_agent" in scoped.tool_names
    assert selection["agent_first"]["enabled"] is True
    assert selection["agent_first"]["keyword"] == "估值"
    assert selection["route_decision"]["primary_intent"] == "analysis_task"
    assert selection["route_decision"]["callable_agent_mode"] == "preferred"
    assert "domain_hint" in selection["intent"]["reason_codes"]
    assert "verb_hint" in selection["intent"]["reason_codes"]
    assert "callable_agent_preferred" in selection["intent"]["reason_codes"]
    assert "list_callable_agents" in selection["agent_first"]["guidance"]


def test_runtime_build_scoped_tools_does_not_trigger_agent_first_for_preview_request(tmp_path) -> None:
    provider = _FakeProvider([])
    runtime = EmbeddedNanobotRuntime(provider=provider, workspace=tmp_path)

    list_meta = ToolMetadata(
        id="list_callable_agents",
        name="List Callable Agents",
        description="列出可直接调用的完整 Agent 能力",
        category="assistant_ops",
        parameters=[ToolParameter(name="keyword", type="string", description="关键词", required=False)],
        when_to_use="当用户要做完整分析任务时使用。",
    )
    execute_meta = ToolMetadata(
        id="execute_callable_agent",
        name="Execute Callable Agent",
        description="调用完整 Agent 能力",
        category="assistant_ops",
        parameters=[ToolParameter(name="agent_identifier", type="string", description="Agent 标识", required=True)],
        when_to_use="确认已有合适 Agent 后使用。",
    )
    runtime.tools.register(TradingAgentsRegistryTool(metadata=list_meta, func=lambda keyword=None: {"keyword": keyword}))
    runtime.tools.register(TradingAgentsRegistryTool(metadata=execute_meta, func=lambda agent_identifier: {"agent_identifier": agent_identifier}))

    scoped, selection = runtime._build_scoped_tools("这个估值 agent 生成的报告会是什么样子，先给我看输出结构")

    assert selection["agent_first"]["enabled"] is False
    assert selection["agent_first"]["guidance"] == ""
    assert selection["intent"]["preview"] is True
    assert selection["route_decision"]["primary_intent"] == "preview_request"
    assert selection["route_decision"]["callable_agent_mode"] == "suppressed"
    assert "preview_hint" in selection["route_decision"]["suppression_reasons"]
    assert "preview_hint" in selection["intent"]["reason_codes"]
    assert "execute_callable_agent" not in scoped.tool_names


def test_runtime_build_scoped_tools_does_not_trigger_agent_first_for_agent_builder_request(tmp_path) -> None:
    provider = _FakeProvider([])
    runtime = EmbeddedNanobotRuntime(provider=provider, workspace=tmp_path)

    list_meta = ToolMetadata(
        id="list_callable_agents",
        name="List Callable Agents",
        description="列出可直接调用的完整 Agent 能力",
        category="assistant_ops",
        parameters=[ToolParameter(name="keyword", type="string", description="关键词", required=False)],
        when_to_use="当用户要做完整分析任务时使用。",
    )
    execute_meta = ToolMetadata(
        id="execute_callable_agent",
        name="Execute Callable Agent",
        description="调用完整 Agent 能力",
        category="assistant_ops",
        parameters=[ToolParameter(name="agent_identifier", type="string", description="Agent 标识", required=True)],
        when_to_use="确认已有合适 Agent 后使用。",
    )
    runtime.tools.register(TradingAgentsRegistryTool(metadata=list_meta, func=lambda keyword=None: {"keyword": keyword}))
    runtime.tools.register(TradingAgentsRegistryTool(metadata=execute_meta, func=lambda agent_identifier: {"agent_identifier": agent_identifier}))

    valuation_meta = ToolMetadata(
        id="valuation_tool",
        name="Valuation Tool",
        description="A股估值底层工具",
        category="fundamentals",
        parameters=[ToolParameter(name="ticker", type="string", description="股票代码", required=True)],
        when_to_use="当用户要做估值分析时使用。",
    )
    runtime.tools.register(TradingAgentsRegistryTool(metadata=valuation_meta, func=lambda ticker: {"ticker": ticker}))

    scoped, selection = runtime._build_scoped_tools("帮我创建一个估值 agent，先把蓝图和工作流搭出来")

    assert selection["intent"]["agent_builder"] is True
    assert selection["route_decision"]["primary_intent"] == "agent_builder_request"
    assert selection["route_decision"]["callable_agent_mode"] == "suppressed"
    assert "agent_builder_hint" in selection["intent"]["reason_codes"]
    assert selection["focused_factory_scope"] is True
    assert selection["selected_dynamic_tools"] == []
    assert selection["agent_first"]["enabled"] is False
    assert selection["agent_builder_governance"]["enabled"] is True
    assert "inspect_agent_workshop_assets" in selection["agent_builder_governance"]["guidance"]
    assert "execute_callable_agent" not in scoped.tool_names
    assert "valuation_tool" not in scoped.tool_names


def test_runtime_build_scoped_tools_injects_workshop_governance_guidance_for_iteration_request(tmp_path) -> None:
    provider = _FakeProvider([])
    runtime = EmbeddedNanobotRuntime(provider=provider, workspace=tmp_path)

    inspect_workshop_meta = ToolMetadata(
        id="inspect_agent_workshop_assets",
        name="Inspect Agent Workshop Assets",
        description="查看 Agent 工坊中的 spec 和 version 资产摘要",
        category="assistant_ops",
        parameters=[],
        when_to_use="当用户要查看、修改、继续迭代现有 Agent 工坊资产时，先确认当前 spec/version 状态。",
    )
    inspect_runtime_meta = ToolMetadata(
        id="inspect_runtime_agent_configs",
        name="Inspect Runtime Agent Configs",
        description="查看运行时 agent 配置",
        category="assistant_ops",
        parameters=[],
        when_to_use="当用户要确认当前运行时 Agent 配置是否仍存在时使用。",
    )
    iterate_meta = ToolMetadata(
        id="iterate_agent_workshop_version",
        name="Iterate Agent Workshop Version",
        description="基于现有版本发起下一轮迭代",
        category="assistant_ops",
        parameters=[],
        when_to_use="当已发布或已评估版本需要修改时，创建下一轮迭代。",
    )
    build_meta = ToolMetadata(
        id="build_agent_workshop_version",
        name="Build Agent Workshop Version",
        description="构建新的 Agent 工坊版本",
        category="assistant_ops",
        parameters=[],
        when_to_use="当会话已经确认好修改内容，需要生成新的 testing 版本时使用。",
    )
    test_meta = ToolMetadata(
        id="run_agent_workshop_real_data_test",
        name="Run Agent Workshop Real Data Test",
        description="执行官方真数据测试",
        category="assistant_ops",
        parameters=[],
        when_to_use="当新的 testing 版本需要执行正式真数据验收时使用。",
    )
    publish_meta = ToolMetadata(
        id="publish_agent_workshop_version",
        name="Publish Agent Workshop Version",
        description="发布已通过验收的版本",
        category="assistant_ops",
        parameters=[],
        when_to_use="仅在最新评估已通过后发布版本。",
    )

    runtime.tools.register(TradingAgentsRegistryTool(metadata=inspect_workshop_meta, func=lambda: {"ok": True}))
    runtime.tools.register(TradingAgentsRegistryTool(metadata=inspect_runtime_meta, func=lambda: {"ok": True}))
    runtime.tools.register(TradingAgentsRegistryTool(metadata=iterate_meta, func=lambda: {"ok": True}))
    runtime.tools.register(TradingAgentsRegistryTool(metadata=build_meta, func=lambda: {"ok": True}))
    runtime.tools.register(TradingAgentsRegistryTool(metadata=test_meta, func=lambda: {"ok": True}))
    runtime.tools.register(TradingAgentsRegistryTool(metadata=publish_meta, func=lambda: {"ok": True}))

    scoped, selection = runtime._build_scoped_tools(
        "帮我修改这个已发布的估值 agent，先看看现在的配置，然后基于它继续做 v2",
        thread_context={
            "spec_id": "spec_valuation_agent",
            "version_id": "spec_valuation_agent_v2",
            "version_status": "active",
            "workshop_session_id": "session_iterate_001",
        },
    )

    assert selection["route_decision"]["primary_intent"] == "agent_builder_request"
    assert selection["thread_context"]["spec_id"] == "spec_valuation_agent"
    assert selection["agent_builder_governance"]["enabled"] is True
    guidance = selection["agent_builder_governance"]["guidance"]
    assert "spec_id=spec_valuation_agent" in guidance
    assert "version_id=spec_valuation_agent_v2" in guidance
    assert "version_status=active" in guidance
    assert "inspect_agent_workshop_assets(spec_id='spec_valuation_agent', version_id='spec_valuation_agent_v2')" in guidance
    assert "inspect_agent_workshop_assets" in guidance
    assert "iterate_agent_workshop_version" in guidance
    assert "published or active Workshop version must not be edited in place" in guidance
    assert "run_agent_workshop_real_data_test" in guidance
    assert "publish_agent_workshop_version" in guidance
    assert "inspect_agent_workshop_assets" in scoped.tool_names
    assert "iterate_agent_workshop_version" in scoped.tool_names


def test_runtime_build_scoped_tools_recommends_session_based_workshop_lookup(tmp_path) -> None:
    provider = _FakeProvider([])
    runtime = EmbeddedNanobotRuntime(provider=provider, workspace=tmp_path)

    inspect_workshop_meta = ToolMetadata(
        id="inspect_agent_workshop_assets",
        name="Inspect Agent Workshop Assets",
        description="查看 Agent 工坊中的 spec 和 version 资产摘要",
        category="assistant_ops",
        parameters=[],
        when_to_use="当用户要查看、修改、继续迭代现有 Agent 工坊资产时，先确认当前 spec/version 状态。",
    )
    runtime.tools.register(TradingAgentsRegistryTool(metadata=inspect_workshop_meta, func=lambda: {"ok": True}))

    scoped, selection = runtime._build_scoped_tools(
        "继续这个 agent 工坊会话，先看当前资产状态",
        thread_context={
            "workshop_session_id": "session_iterate_002",
            "spec_name": "估值助手",
        },
    )

    assert selection["route_decision"]["primary_intent"] == "agent_builder_request"
    guidance = selection["agent_builder_governance"]["guidance"]
    assert "workshop_session_id=session_iterate_002" in guidance
    assert "inspect_agent_workshop_assets(workshop_session_id='session_iterate_002')" in guidance
    assert "inspect_agent_workshop_assets" in scoped.tool_names


def test_runtime_build_scoped_tools_disambiguates_official_test_from_debug(tmp_path) -> None:
    provider = _FakeProvider([])
    runtime = EmbeddedNanobotRuntime(provider=provider, workspace=tmp_path)

    debug_meta = ToolMetadata(
        id="debug_agent_workshop_version",
        name="Debug Agent Workshop Version",
        description="执行单次调试运行，不落正式评估。",
        category="assistant_ops",
        parameters=[],
        when_to_use="当用户明确要排查 Prompt 或运行时问题时使用。",
    )
    test_meta = ToolMetadata(
        id="run_agent_workshop_real_data_test",
        name="Run Agent Workshop Real Data Test",
        description="执行官方真数据测试并记录评估结果。",
        category="assistant_ops",
        parameters=[],
        when_to_use="当用户要执行正式测试、验收或评估时使用。",
    )

    runtime.tools.register(TradingAgentsRegistryTool(metadata=debug_meta, func=lambda: {"ok": True}))
    runtime.tools.register(TradingAgentsRegistryTool(metadata=test_meta, func=lambda: {"ok": True}))

    _, selection = runtime._build_scoped_tools(
        "帮我给这个 Agent 工坊版本做一次真数据测试，看看为什么它还停留在 testing，能不能通过正式验收",
        thread_context={
            "spec_id": "spec_test_agent",
            "version_id": "spec_test_agent_v3",
            "version_status": "testing",
        },
    )

    guidance = selection["agent_builder_governance"]["guidance"]
    assert selection["route_decision"]["primary_intent"] == "agent_builder_request"
    assert "debug_agent_workshop_version only for prompt/runtime diagnosis" in guidance
    assert "choose run_agent_workshop_real_data_test instead of debug_agent_workshop_version" in guidance
    assert "prefer run_agent_workshop_real_data_test unless the user explicitly asks for debug-only diagnosis" in guidance


def test_runtime_build_scoped_tools_requires_explicit_publish_confirmation(tmp_path) -> None:
    provider = _FakeProvider([])
    runtime = EmbeddedNanobotRuntime(provider=provider, workspace=tmp_path)

    inspect_meta = ToolMetadata(
        id="inspect_agent_workshop_assets",
        name="Inspect Agent Workshop Assets",
        description="查看 Agent 工坊中的 spec 和 version 资产摘要。",
        category="assistant_ops",
        parameters=[],
        when_to_use="当用户要查看、测试或发布现有 Agent 工坊版本时先确认当前状态。",
    )
    publish_meta = ToolMetadata(
        id="publish_agent_workshop_version",
        name="Publish Agent Workshop Version",
        description="发布已通过验收的版本。",
        category="assistant_ops",
        parameters=[],
        when_to_use="仅在用户明确确认发布时使用。",
    )
    runtime.tools.register(TradingAgentsRegistryTool(metadata=inspect_meta, func=lambda: {"ok": True}))
    runtime.tools.register(TradingAgentsRegistryTool(metadata=publish_meta, func=lambda: {"ok": True}))

    _, selection = runtime._build_scoped_tools(
        "帮我看一下这个 Agent 工坊版本已经 pass 了没有，先告诉我测试结果和当前状态，不要直接发布",
        thread_context={
            "spec_id": "spec_test_agent",
            "version_id": "spec_test_agent_v3",
            "version_status": "testing",
        },
    )

    guidance = selection["agent_builder_governance"]["guidance"]
    assert selection["route_decision"]["primary_intent"] == "agent_builder_request"
    assert "user explicitly confirms publication in the current turn" in guidance
    assert "must not trigger automatic publication" in guidance


@pytest.mark.asyncio
async def test_runtime_handle_message_injects_project_memory_for_agent_builder_request(tmp_path, monkeypatch) -> None:
    provider = _FakeProvider([])
    runtime = EmbeddedNanobotRuntime(provider=provider, workspace=tmp_path, memory_db=object())

    inspect_meta = ToolMetadata(
        id="inspect_agent_workshop_assets",
        name="Inspect Agent Workshop Assets",
        description="查看 Agent 工坊中的 spec 和 version 资产摘要。",
        category="assistant_ops",
        parameters=[],
        when_to_use="当用户要查看或修改现有 Agent 工坊资产时先确认状态。",
    )
    runtime.tools.register(TradingAgentsRegistryTool(metadata=inspect_meta, func=lambda: {"ok": True}))

    captured = {}

    class _FakeProjectMemoryService:
        async def build_prompt_block(self, **kwargs):
            captured["project_memory_kwargs"] = dict(kwargs)
            return "【项目长期记忆】\n- 项目规则\n  - 禁止直接投资建议：所有分析只提供研究与学习参考。"

    async def _fake_build_capped_initial_messages(*args, **kwargs):
        captured["extra_system_guidance"] = kwargs.get("extra_system_guidance")
        return ([{"role": "system", "content": "sys"}, {"role": "user", "content": "msg"}], [], 10)

    async def _fake_run(self, spec):
        del self, spec
        return AgentRunResult(final_content="ok", messages=[{"role": "assistant", "content": "ok"}], stop_reason="completed", usage={}, tools_used=[], tool_events=[])

    monkeypatch.setattr(
        "app.services.project_memory_service.get_project_memory_service",
        lambda db: _FakeProjectMemoryService(),
    )
    monkeypatch.setattr(runtime, "_build_capped_initial_messages", _fake_build_capped_initial_messages)
    monkeypatch.setattr(runtime, "_dump_prompt_context", lambda **kwargs: tmp_path / "ctx.json")
    monkeypatch.setattr(runtime.runner, "run", _fake_run.__get__(runtime.runner, type(runtime.runner)))

    result = await runtime.handle_message(
        user_message="继续修改这个 agent 工坊版本，先确认当前状态再决定下一步",
        session_key="embedded:agent-builder:l4",
        thread_context={
            "spec_id": "spec_agent_builder_demo",
            "version_id": "spec_agent_builder_demo_v2",
            "version_status": "testing",
        },
    )

    assert result["content"] == "ok"
    assert captured["project_memory_kwargs"]["categories"] == ["project_rule", "governance_constraint", "research_template"]
    assert "# Agent Workshop project memory" in captured["extra_system_guidance"]
    assert "【项目长期记忆】" in captured["extra_system_guidance"]
    assert "禁止直接投资建议" in captured["extra_system_guidance"]
    assert "# Agent Workshop governance rule" in captured["extra_system_guidance"]


@pytest.mark.asyncio
async def test_runtime_handle_message_injects_agent_builder_lessons_for_governance_request(tmp_path, monkeypatch) -> None:
    provider = _FakeProvider([])
    runtime = EmbeddedNanobotRuntime(provider=provider, workspace=tmp_path, memory_db=object())

    inspect_meta = ToolMetadata(
        id="inspect_agent_workshop_assets",
        name="Inspect Agent Workshop Assets",
        description="查看 Agent 工坊中的 spec 和 version 资产摘要。",
        category="assistant_ops",
        parameters=[],
        when_to_use="当用户要查看或修改现有 Agent 工坊资产时先确认状态。",
    )
    runtime.tools.register(TradingAgentsRegistryTool(metadata=inspect_meta, func=lambda: {"ok": True}))

    captured = {}
    fake_memory_service = _FakeMemoryService(StoreResult())
    fake_memory_service.recall_text = "【工坊历史教训】\n- 上一轮缺少行业对比证据\n- 修正动作：补充行业横向比较和估值解释\n"

    class _FakeProjectMemoryService:
        async def build_prompt_block(self, **kwargs):
            captured["project_memory_kwargs"] = dict(kwargs)
            return "【项目长期记忆】\n- 项目规则\n  - 禁止直接投资建议：所有分析只提供研究与学习参考。"

    async def _fake_build_capped_initial_messages(*args, **kwargs):
        captured["extra_system_guidance"] = kwargs.get("extra_system_guidance")
        return ([{"role": "system", "content": "sys"}, {"role": "user", "content": "msg"}], [], 10)

    async def _fake_run(self, spec):
        del self, spec
        return AgentRunResult(final_content="ok", messages=[{"role": "assistant", "content": "ok"}], stop_reason="completed", usage={}, tools_used=[], tool_events=[])

    def _fake_log_agent_builder_lesson_recall_observation(**kwargs):
        captured["lesson_observation"] = dict(kwargs)

    monkeypatch.setattr(
        "app.services.project_memory_service.get_project_memory_service",
        lambda db: _FakeProjectMemoryService(),
    )
    monkeypatch.setattr("core.memory.service.get_memory_service", lambda db: fake_memory_service)
    monkeypatch.setattr(runtime, "_log_agent_builder_lesson_recall_observation", _fake_log_agent_builder_lesson_recall_observation)
    monkeypatch.setattr(runtime, "_build_capped_initial_messages", _fake_build_capped_initial_messages)
    monkeypatch.setattr(runtime, "_dump_prompt_context", lambda **kwargs: tmp_path / "ctx.json")
    monkeypatch.setattr(runtime.runner, "run", _fake_run.__get__(runtime.runner, type(runtime.runner)))

    result = await runtime.handle_message(
        user_message="继续修改这个 agent 工坊版本，先结合历史评估结论确认下一步",
        session_key="embedded:agent-builder:l6",
        user_id="user-123",
        thread_context={
            "spec_id": "spec_agent_builder_demo",
            "version_id": "spec_agent_builder_demo_v2",
            "version_status": "testing",
        },
    )

    assert result["content"] == "ok"
    assert captured["project_memory_kwargs"]["categories"] == ["project_rule", "governance_constraint", "research_template"]
    assert len(fake_memory_service.recall_calls) == 1
    recall_call = fake_memory_service.recall_calls[0]
    assert recall_call["user_id"] == "user-123"
    assert recall_call["agent_id"] == "agent_builder"
    assert recall_call["scopes"] == ["agent_builder_lesson"]
    assert recall_call["metadata_filters"] == {"spec_id": "spec_agent_builder_demo"}
    assert recall_call["ranking_profile"] == "agent_builder"
    assert captured["lesson_observation"]["source_stage"] == "runtime_governance"
    assert captured["lesson_observation"]["status"] == "hit"
    assert captured["lesson_observation"]["user_id"] == "user-123"
    assert captured["lesson_observation"]["metadata_filters"] == {"spec_id": "spec_agent_builder_demo"}
    assert "# Agent Workshop project memory" in captured["extra_system_guidance"]
    assert "# Agent Workshop historical lessons" in captured["extra_system_guidance"]
    assert "【工坊历史教训】" in captured["extra_system_guidance"]
    assert "# Agent Workshop governance rule" in captured["extra_system_guidance"]
    assert captured["extra_system_guidance"].index("# Agent Workshop project memory") < captured["extra_system_guidance"].index("# Agent Workshop historical lessons")
    assert captured["extra_system_guidance"].index("# Agent Workshop historical lessons") < captured["extra_system_guidance"].index("# Agent Workshop governance rule")


@pytest.mark.asyncio
async def test_runtime_handle_message_logs_agent_builder_lesson_miss_for_governance_request(tmp_path, monkeypatch) -> None:
    provider = _FakeProvider([])
    runtime = EmbeddedNanobotRuntime(provider=provider, workspace=tmp_path, memory_db=object())

    inspect_meta = ToolMetadata(
        id="inspect_agent_workshop_assets",
        name="Inspect Agent Workshop Assets",
        description="查看 Agent 工坊中的 spec 和 version 资产摘要。",
        category="assistant_ops",
        parameters=[],
        when_to_use="当用户要查看或修改现有 Agent 工坊资产时先确认状态。",
    )
    runtime.tools.register(TradingAgentsRegistryTool(metadata=inspect_meta, func=lambda: {"ok": True}))

    captured = {}
    fake_memory_service = _FakeMemoryService(StoreResult())
    fake_memory_service.recall_text = ""

    async def _fake_build_capped_initial_messages(*args, **kwargs):
        captured["extra_system_guidance"] = kwargs.get("extra_system_guidance")
        return ([{"role": "system", "content": "sys"}, {"role": "user", "content": "msg"}], [], 10)

    async def _fake_run(self, spec):
        del self, spec
        return AgentRunResult(final_content="ok", messages=[{"role": "assistant", "content": "ok"}], stop_reason="completed", usage={}, tools_used=[], tool_events=[])

    def _fake_log_agent_builder_lesson_recall_observation(**kwargs):
        captured["lesson_observation"] = dict(kwargs)

    monkeypatch.setattr("core.memory.service.get_memory_service", lambda db: fake_memory_service)
    monkeypatch.setattr(runtime, "_log_agent_builder_lesson_recall_observation", _fake_log_agent_builder_lesson_recall_observation)
    monkeypatch.setattr(runtime, "_build_capped_initial_messages", _fake_build_capped_initial_messages)
    monkeypatch.setattr(runtime, "_dump_prompt_context", lambda **kwargs: tmp_path / "ctx.json")
    monkeypatch.setattr(runtime.runner, "run", _fake_run.__get__(runtime.runner, type(runtime.runner)))

    result = await runtime.handle_message(
        user_message="继续修改这个 agent 工坊版本，先结合历史评估结论确认下一步",
        session_key="embedded:agent-builder:l6-miss",
        user_id="user-123",
        thread_context={
            "spec_id": "spec_agent_builder_demo",
            "version_id": "spec_agent_builder_demo_v2",
            "version_status": "testing",
        },
    )

    assert result["content"] == "ok"
    assert len(fake_memory_service.recall_calls) == 1
    assert captured["lesson_observation"]["source_stage"] == "runtime_governance"
    assert captured["lesson_observation"]["status"] == "miss"
    assert captured["lesson_observation"]["user_id"] == "user-123"
    assert captured["lesson_observation"]["metadata_filters"] == {"spec_id": "spec_agent_builder_demo"}
    assert captured["lesson_observation"]["recalled"] == ""
    assert "# Agent Workshop historical lessons" not in str(captured["extra_system_guidance"] or "")


@pytest.mark.asyncio
async def test_runtime_handle_message_skips_agent_builder_lessons_for_non_governance_request(tmp_path, monkeypatch) -> None:
    provider = _FakeProvider([])
    runtime = EmbeddedNanobotRuntime(provider=provider, workspace=tmp_path, memory_db=object())
    captured = {}
    fake_memory_service = _FakeMemoryService(StoreResult())
    fake_memory_service.recall_text = "【工坊历史教训】\n- 不应该出现在普通请求里\n"

    async def _fake_build_capped_initial_messages(*args, **kwargs):
        captured["extra_system_guidance"] = kwargs.get("extra_system_guidance")
        return ([{"role": "system", "content": "sys"}, {"role": "user", "content": "msg"}], [], 10)

    async def _fake_run(self, spec):
        del self, spec
        return AgentRunResult(final_content="ok", messages=[{"role": "assistant", "content": "ok"}], stop_reason="completed", usage={}, tools_used=[], tool_events=[])

    monkeypatch.setattr("core.memory.service.get_memory_service", lambda db: fake_memory_service)
    monkeypatch.setattr(runtime, "_build_capped_initial_messages", _fake_build_capped_initial_messages)
    monkeypatch.setattr(runtime, "_dump_prompt_context", lambda **kwargs: tmp_path / "ctx.json")
    monkeypatch.setattr(runtime.runner, "run", _fake_run.__get__(runtime.runner, type(runtime.runner)))

    result = await runtime.handle_message(
        user_message="帮我看下贵州茅台近期估值变化",
        session_key="embedded:agent-builder:non-governance",
        user_id="user-123",
        thread_context={"symbol": "600519"},
    )

    assert result["content"] == "ok"
    assert fake_memory_service.recall_calls == []
    assert "# Agent Workshop historical lessons" not in str(captured["extra_system_guidance"] or "")


def test_runtime_build_scoped_tools_does_not_trigger_agent_first_for_skill_creation_request(tmp_path) -> None:
    provider = _FakeProvider([])
    runtime = EmbeddedNanobotRuntime(provider=provider, workspace=tmp_path)

    list_meta = ToolMetadata(
        id="list_callable_agents",
        name="List Callable Agents",
        description="列出可直接调用的完整 Agent 能力",
        category="assistant_ops",
        parameters=[ToolParameter(name="keyword", type="string", description="关键词", required=False)],
        when_to_use="当用户要做完整分析任务时使用。",
    )
    execute_meta = ToolMetadata(
        id="execute_callable_agent",
        name="Execute Callable Agent",
        description="调用完整 Agent 能力",
        category="assistant_ops",
        parameters=[ToolParameter(name="agent_identifier", type="string", description="Agent 标识", required=True)],
        when_to_use="确认已有合适 Agent 后使用。",
    )
    runtime.tools.register(TradingAgentsRegistryTool(metadata=list_meta, func=lambda keyword=None: {"keyword": keyword}))
    runtime.tools.register(TradingAgentsRegistryTool(metadata=execute_meta, func=lambda agent_identifier: {"agent_identifier": agent_identifier}))

    valuation_meta = ToolMetadata(
        id="valuation_tool",
        name="Valuation Tool",
        description="A股估值底层工具",
        category="fundamentals",
        parameters=[ToolParameter(name="ticker", type="string", description="股票代码", required=True)],
        when_to_use="当用户要做估值分析时使用。",
    )
    runtime.tools.register(TradingAgentsRegistryTool(metadata=valuation_meta, func=lambda ticker: {"ticker": ticker}))

    scoped, selection = runtime._build_scoped_tools("把这个能力沉淀成可复用 skill，顺便整理参数")

    assert selection["intent"]["skill_creation"] is True
    assert selection["route_decision"]["primary_intent"] == "skill_creation_request"
    assert selection["route_decision"]["callable_agent_mode"] == "suppressed"
    assert "skill_creation_hint" in selection["intent"]["reason_codes"]
    assert selection["focused_factory_scope"] is True
    assert selection["selected_dynamic_tools"] == []
    assert selection["agent_first"]["enabled"] is False
    assert "execute_callable_agent" not in scoped.tool_names
    assert "valuation_tool" not in scoped.tool_names


@pytest.mark.asyncio
async def test_runtime_handle_message_uses_llm_route_fallback_for_ambiguous_request(tmp_path, monkeypatch) -> None:
    provider = _FakeProvider([
        LLMResponse(content=json.dumps({
            "primary_intent": "analysis_task",
            "prefer_callable_agent": True,
            "confidence": "high",
            "rationale": "用户主要是在要求系统直接做完整分析",
        }, ensure_ascii=False)),
    ])
    runtime = EmbeddedNanobotRuntime(provider=provider, workspace=tmp_path)

    list_meta = ToolMetadata(
        id="list_callable_agents",
        name="List Callable Agents",
        description="列出可直接调用的完整 Agent 能力",
        category="assistant_ops",
        parameters=[ToolParameter(name="keyword", type="string", description="关键词", required=False)],
        when_to_use="当用户要做完整分析任务时使用。",
    )
    execute_meta = ToolMetadata(
        id="execute_callable_agent",
        name="Execute Callable Agent",
        description="调用完整 Agent 能力",
        category="assistant_ops",
        parameters=[ToolParameter(name="agent_identifier", type="string", description="Agent 标识", required=True)],
        when_to_use="确认已有合适 Agent 后使用。",
    )
    runtime.tools.register(TradingAgentsRegistryTool(metadata=list_meta, func=lambda keyword=None: {"keyword": keyword}))
    runtime.tools.register(TradingAgentsRegistryTool(metadata=execute_meta, func=lambda agent_identifier: {"agent_identifier": agent_identifier}))

    async def _fake_build_capped_initial_messages(*args, **kwargs):
        del args, kwargs
        return ([{"role": "system", "content": "sys"}, {"role": "user", "content": "msg"}], [], 10)

    async def _fake_run(self, spec):
        del self, spec
        return AgentRunResult(final_content="ok", messages=[{"role": "assistant", "content": "ok"}], stop_reason="completed", usage={}, tools_used=[], tool_events=[])

    monkeypatch.setattr(runtime, "_build_capped_initial_messages", _fake_build_capped_initial_messages)
    monkeypatch.setattr(runtime, "_dump_prompt_context", lambda **kwargs: tmp_path / "ctx.json")
    monkeypatch.setattr(runtime.runner, "run", _fake_run.__get__(runtime.runner, type(runtime.runner)))

    result = await runtime.handle_message(
        user_message="帮我创建一个估值 agent，但先直接分析一下茅台给我完整结论",
        session_key="embedded:fallback",
        channel="api",
        chat_id="embedded:fallback",
    )

    assert result["content"] == "ok"
    assert len(provider.calls) == 1


@pytest.mark.asyncio
async def test_runtime_handle_message_skips_llm_route_fallback_for_clear_preview_request(tmp_path, monkeypatch) -> None:
    provider = _FakeProvider([])
    runtime = EmbeddedNanobotRuntime(provider=provider, workspace=tmp_path)

    async def _fake_build_capped_initial_messages(*args, **kwargs):
        del args, kwargs
        return ([{"role": "system", "content": "sys"}, {"role": "user", "content": "msg"}], [], 10)

    async def _fake_run(self, spec):
        del self, spec
        return AgentRunResult(final_content="ok", messages=[{"role": "assistant", "content": "ok"}], stop_reason="completed", usage={}, tools_used=[], tool_events=[])

    monkeypatch.setattr(runtime, "_build_capped_initial_messages", _fake_build_capped_initial_messages)
    monkeypatch.setattr(runtime, "_dump_prompt_context", lambda **kwargs: tmp_path / "ctx.json")
    monkeypatch.setattr(runtime.runner, "run", _fake_run.__get__(runtime.runner, type(runtime.runner)))

    result = await runtime.handle_message(
        user_message="这个估值 agent 的报告长什么样，先给我看输出结构",
        session_key="embedded:no-fallback",
        channel="api",
        chat_id="embedded:no-fallback",
    )

    assert result["content"] == "ok"
    assert provider.calls == []


def test_runtime_dump_prompt_context_exposes_route_decision_top_level(tmp_path: Path) -> None:
    provider = _FakeProvider([])
    runtime = EmbeddedNanobotRuntime(provider=provider, workspace=tmp_path)

    dump_path = runtime._dump_prompt_context(
        session_key="embedded:route-dump",
        active_tools=runtime.tools,
        tool_selection={
            "selected_tool_names": ["read_file"],
            "route_decision": {
                "primary_intent": "analysis_task",
                "decision_source": "llm_fallback",
                "callable_agent_mode": "preferred",
                "reason_codes": ["domain_hint", "verb_hint", "llm_route_fallback"],
                "suppression_reasons": ["agent_builder_hint"],
                "matched_categories": ["fundamentals"],
                "callable_keyword": "估值",
                "fallback": {
                    "considered": True,
                    "used": True,
                    "status": "applied",
                },
            },
        },
        initial_messages=[
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "帮我分析茅台估值"},
        ],
        estimated_tokens=42,
        history=[],
        skill_names=None,
        channel="api",
        chat_id="embedded:route-dump",
    )

    payload = json.loads(dump_path.read_text(encoding="utf-8"))

    assert payload["route_decision"]["primary_intent"] == "analysis_task"
    assert payload["route_decision"]["decision_source"] == "llm_fallback"
    assert payload["route_fallback"] == {
        "considered": True,
        "used": True,
        "status": "applied",
    }
    assert payload["tool_selection"]["route_decision"]["callable_keyword"] == "估值"


@pytest.mark.asyncio
async def test_runtime_build_capped_initial_messages_injects_agent_first_guidance(tmp_path) -> None:
    provider = _FakeProvider([])
    runtime = EmbeddedNanobotRuntime(provider=provider, workspace=tmp_path)
    session = runtime.sessions.get_or_create("embedded:agent-first")

    initial_messages, history, _ = await runtime._build_capped_initial_messages(
        session,
        runtime.tools,
        user_message="帮我做一下茅台的估值分析",
        skill_names=None,
        media=None,
        channel="api",
        chat_id="embedded:agent-first",
        extra_system_guidance="优先调用 list_callable_agents，再决定是否使用 execute_callable_agent。",
    )

    assert history == []
    assert initial_messages[0]["role"] == "system"
    assert initial_messages[1]["role"] == "system"
    assert "list_callable_agents" in initial_messages[1]["content"]


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
async def test_embedded_nanobot_service_persists_chat_turn_to_database(monkeypatch, tmp_path) -> None:
    class _FakeRuntime:
        def __init__(self):
            self.last_kwargs = None

        async def sync_tradingagents_capabilities(self, db) -> None:
            return None

        async def handle_message(self, **kwargs):
            self.last_kwargs = dict(kwargs)
            return {
                "content": "Nanobot 回复",
                "tools_used": ["inspect_agent_workshop_assets"],
                "stop_reason": "completed",
                "usage": {"prompt_tokens": 12, "completion_tokens": 34},
                "tool_events": [{"name": "inspect_agent_workshop_assets", "status": "ok", "detail": "完成"}],
            }

    fake_runtime = _FakeRuntime()
    fake_db = _FakeDb({
        "embedded_nanobot_threads": _FakeCollection([]),
        "embedded_nanobot_thread_messages": _FakeCollection([]),
    })
    service = EmbeddedNanobotService(db=fake_db, workspace=tmp_path)
    monkeypatch.setattr(service, "get_runtime", AsyncMock(return_value=fake_runtime))

    result = await service.chat(
        user_message="继续当前 Agent Workshop Draft 讨论。\n\nsession_id='session_001'。\n\n用户本次补充：帮我看一下当前 Draft 状态",
        display_message="帮我看一下当前 Draft 状态",
        session_key="embedded:user:test",
        user_id="user-123",
        current_thread_id="thread-001",
        chat_id="thread-001",
        channel="agent_workshop",
        thread_context={
            "spec_id": "spec_001",
            "spec_name": "财报风险跟踪助手",
            "workshop_session_id": "session_001",
            "workflow_id": "agent_workshop_debug_spec_001_v2",
            "node_id": "prompt_debug_node_001",
            "preference_id": "aggressive",
            "debug_template_id": "tpl_debug_001",
            "symbol": "600519",
            "object_type": "stock",
            "object_key": "600519",
        },
    )

    assert result["content"] == "Nanobot 回复"
    assert fake_runtime.last_kwargs is not None
    assert fake_runtime.last_kwargs["thread_context"] == {
        "spec_id": "spec_001",
        "spec_name": "财报风险跟踪助手",
        "workshop_session_id": "session_001",
        "workflow_id": "agent_workshop_debug_spec_001_v2",
        "node_id": "prompt_debug_node_001",
        "preference_id": "aggressive",
        "debug_template_id": "tpl_debug_001",
        "symbol": "600519",
        "object_type": "stock",
        "object_key": "600519",
    }
    assert fake_runtime.last_kwargs["user_id"] == "user-123"
    assert fake_runtime.last_kwargs["thread_id"] == "thread-001"
    thread_doc = fake_db["embedded_nanobot_threads"]._items[0]
    message_docs = fake_db["embedded_nanobot_thread_messages"]._items

    assert thread_doc["thread_id"] == "thread-001"
    assert thread_doc["user_id"] == "user-123"
    assert thread_doc["session_key"] == "embedded:user:test"
    assert thread_doc["channel"] == "agent_workshop"
    assert thread_doc["thread_context"] == {
        "spec_id": "spec_001",
        "spec_name": "财报风险跟踪助手",
        "workshop_session_id": "session_001",
        "workflow_id": "agent_workshop_debug_spec_001_v2",
        "node_id": "prompt_debug_node_001",
        "preference_id": "aggressive",
        "debug_template_id": "tpl_debug_001",
        "symbol": "600519",
        "object_type": "stock",
        "object_key": "600519",
    }
    assert thread_doc["message_count"] == 2
    assert thread_doc["last_user_message"] == "帮我看一下当前 Draft 状态"
    assert thread_doc["current_summary"]["abstract"] == "Nanobot 回复"
    assert len(message_docs) == 2
    assert message_docs[0]["role"] == "user"
    assert message_docs[0]["content"] == "帮我看一下当前 Draft 状态"
    assert "用户本次补充：帮我看一下当前 Draft 状态" in message_docs[0]["raw_content"]
    assert message_docs[1]["role"] == "assistant"
    assert message_docs[1]["content"] == "Nanobot 回复"
    assert message_docs[1]["tools_used"] == ["inspect_agent_workshop_assets"]
    assert message_docs[1]["usage"] == {"prompt_tokens": 12, "completion_tokens": 34}


@pytest.mark.asyncio
async def test_embedded_nanobot_service_lists_and_reads_thread_messages(tmp_path) -> None:
    now = datetime.now(timezone.utc)
    fake_db = _FakeDb({
        "embedded_nanobot_threads": _FakeCollection([
            {
                "thread_id": "thread-001",
                "user_id": "user-123",
                "title": "财报风险跟踪",
                "session_key": "embedded:user:test",
                "channel": "agent_workshop",
                "archived": False,
                "message_count": 2,
                "last_user_message": "帮我继续看风险项",
                "current_summary": {"abstract": "已整理最近风险点"},
                "created_at": now,
                "updated_at": now,
            }
        ]),
        "embedded_nanobot_thread_messages": _FakeCollection([
            {
                "message_id": "msg-001",
                "thread_id": "thread-001",
                "user_id": "user-123",
                "role": "user",
                "content": "帮我继续看风险项",
                "tools_used": [],
                "created_at": now,
            },
            {
                "message_id": "msg-002",
                "thread_id": "thread-001",
                "user_id": "user-123",
                "role": "assistant",
                "content": "已整理最近风险点",
                "tools_used": ["run_agent_workshop_real_data_test"],
                "usage": {"prompt_tokens": 10},
                "tool_events": [{"name": "run_agent_workshop_real_data_test", "status": "ok", "detail": "执行完成"}],
                "created_at": now,
            },
        ]),
    })
    service = EmbeddedNanobotService(db=fake_db, workspace=tmp_path)

    threads = await service.list_threads(user_id="user-123", limit=20)
    thread, messages = await service.get_thread_messages(user_id="user-123", thread_id="thread-001")

    assert len(threads) == 1
    assert threads[0]["thread_id"] == "thread-001"
    assert threads[0]["title"] == "财报风险跟踪"
    assert threads[0]["summary"] == "已整理最近风险点"
    assert thread is not None
    assert thread["thread_id"] == "thread-001"
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"
    assert messages[1]["tools_used"] == ["run_agent_workshop_real_data_test"]


@pytest.mark.asyncio
async def test_embedded_nanobot_service_updates_and_reads_thread_context(tmp_path) -> None:
    fake_db = _FakeDb({
        "embedded_nanobot_threads": _FakeCollection([]),
        "embedded_nanobot_thread_messages": _FakeCollection([]),
    })
    service = EmbeddedNanobotService(db=fake_db, workspace=tmp_path)

    updated = await service.update_thread_context(
        user_id="user-123",
        thread_id="thread-ctx-001",
        session_key="embedded:user:test:ctx",
        channel="agent_workshop",
        thread_context={
            "spec_id": "spec_nanobot_financial_report_risk_tracker_v1",
            "spec_name": "财报风险跟踪助手",
            "workshop_session_id": "session_ctx_001",
            "version_id": "spec_nanobot_financial_report_risk_tracker_v1_v2",
            "version_status": "testing",
            "workflow_id": "agent_workshop_debug_spec_nanobot_financial_report_risk_tracker_v1_v2",
            "node_id": "prompt_debug_node_financial_risk",
            "preference_id": "conservative",
            "debug_template_id": "tpl_financial_risk_debug_v2",
        },
    )
    thread, messages = await service.get_thread_messages(user_id="user-123", thread_id="thread-ctx-001")

    assert updated is not None
    assert updated["thread_context"]["spec_id"] == "spec_nanobot_financial_report_risk_tracker_v1"
    assert thread is not None
    assert thread["thread_context"]["version_id"] == "spec_nanobot_financial_report_risk_tracker_v1_v2"
    assert thread["thread_context"]["version_status"] == "testing"
    assert thread["thread_context"]["workflow_id"] == "agent_workshop_debug_spec_nanobot_financial_report_risk_tracker_v1_v2"
    assert thread["thread_context"]["node_id"] == "prompt_debug_node_financial_risk"
    assert thread["thread_context"]["preference_id"] == "conservative"
    assert thread["thread_context"]["debug_template_id"] == "tpl_financial_risk_debug_v2"
    assert messages == []


@pytest.mark.asyncio
async def test_embedded_nanobot_service_archives_thread_without_removing_messages(tmp_path) -> None:
    now = datetime.now(timezone.utc)
    fake_db = _FakeDb({
        "embedded_nanobot_threads": _FakeCollection([
            {
                "thread_id": "thread-archive-001",
                "user_id": "user-123",
                "title": "财报风险跟踪",
                "session_key": "embedded:user:test:archive",
                "channel": "agent_workshop",
                "archived": False,
                "message_count": 2,
                "last_user_message": "继续看最近风险项",
                "current_summary": {"abstract": "已整理最近风险点"},
                "created_at": now,
                "updated_at": now,
            }
        ]),
        "embedded_nanobot_thread_messages": _FakeCollection([
            {
                "message_id": "msg-archive-001",
                "thread_id": "thread-archive-001",
                "user_id": "user-123",
                "role": "user",
                "content": "继续看最近风险项",
                "tools_used": [],
                "created_at": now,
            },
            {
                "message_id": "msg-archive-002",
                "thread_id": "thread-archive-001",
                "user_id": "user-123",
                "role": "assistant",
                "content": "已整理最近风险点",
                "tools_used": ["run_agent_workshop_real_data_test"],
                "created_at": now,
            },
        ]),
    })
    service = EmbeddedNanobotService(db=fake_db, workspace=tmp_path)

    archived = await service.delete_thread(user_id="user-123", thread_id="thread-archive-001")
    visible_threads = await service.list_threads(user_id="user-123", limit=20)
    archived_threads = await service.list_threads(user_id="user-123", limit=20, archived_only=True)
    thread, messages = await service.get_thread_messages(user_id="user-123", thread_id="thread-archive-001")

    assert archived["archived"] is True
    assert archived["deleted_messages"] == 0
    assert visible_threads == []
    assert len(archived_threads) == 1
    assert archived_threads[0]["thread_id"] == "thread-archive-001"
    assert thread is not None
    assert thread["archived"] is True
    assert len(messages) == 2

    restored = await service.restore_thread(user_id="user-123", thread_id="thread-archive-001")
    visible_threads = await service.list_threads(user_id="user-123", limit=20)
    archived_threads = await service.list_threads(user_id="user-123", limit=20, archived_only=True)

    assert restored["restored"] is True
    assert restored["archived"] is False
    assert len(visible_threads) == 1
    assert archived_threads == []

    await service.persist_chat_turn(
        user_id="user-123",
        thread_id="thread-archive-001",
        session_key="embedded:user:test:archive",
        channel="agent_workshop",
        user_content="补充一个新问题",
        assistant_content="这是新的回复",
    )
    visible_threads = await service.list_threads(user_id="user-123", limit=20)
    thread, messages = await service.get_thread_messages(user_id="user-123", thread_id="thread-archive-001")

    assert len(visible_threads) == 1
    assert visible_threads[0]["thread_id"] == "thread-archive-001"
    assert thread is not None
    assert thread["archived"] is False
    assert len(messages) == 4


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


@pytest.mark.asyncio
async def test_embedded_nanobot_runtime_emits_step_events(tmp_path) -> None:
    provider = _FakeProvider([
        LLMResponse(content="", tool_calls=[ToolCallRequest(id="tool-1", name="echo_tool", arguments={"text": "hello"})]),
        LLMResponse(content="最终答复"),
    ])
    runtime = EmbeddedNanobotRuntime(provider=provider, workspace=tmp_path)
    runtime.tools.register(_EchoTool())

    step_events: list[dict[str, object]] = []

    result = await runtime.handle_message(
        user_message="请先调用工具再回复",
        session_key="embedded:test:steps",
        on_step_event=step_events.append,
    )

    assert result["content"] == "最终答复"
    assert any(event.get("step") == "context_preparation" and event.get("status") == "started" for event in step_events)
    assert any(event.get("step") == "context_preparation" and event.get("status") == "completed" for event in step_events)
    assert any(event.get("step") == "tool_execution" and event.get("status") == "started" for event in step_events)
    assert any(event.get("step") == "tool_execution" and event.get("status") == "completed" for event in step_events)
    assert any(event.get("step") == "final_response" and event.get("status") == "completed" for event in step_events)


@pytest.mark.asyncio
async def test_runtime_handle_message_does_not_auto_publish_after_pass(tmp_path) -> None:
    provider = _PublishSensitiveProvider()
    runtime = EmbeddedNanobotRuntime(provider=provider, workspace=tmp_path)

    inspect_meta = ToolMetadata(
        id="inspect_agent_workshop_assets",
        name="Inspect Agent Workshop Assets",
        description="查看 Agent 工坊中的 spec 和 version 资产摘要。",
        category="assistant_ops",
        parameters=[],
        when_to_use="当用户要查看、测试或发布现有 Agent 工坊版本时先确认当前状态。",
    )
    test_meta = ToolMetadata(
        id="run_agent_workshop_real_data_test",
        name="Run Agent Workshop Real Data Test",
        description="执行官方真数据测试并记录评估结果。",
        category="assistant_ops",
        parameters=[],
        when_to_use="当用户要执行正式测试、验收或评估时使用。",
    )
    publish_meta = ToolMetadata(
        id="publish_agent_workshop_version",
        name="Publish Agent Workshop Version",
        description="在用户明确确认后发布已通过验收的版本。",
        category="assistant_ops",
        parameters=[],
        when_to_use="仅在用户明确确认发布时使用。",
    )

    runtime.tools.register(TradingAgentsRegistryTool(metadata=inspect_meta, func=lambda: {"ok": True}))
    runtime.tools.register(
        TradingAgentsRegistryTool(
            metadata=test_meta,
            func=lambda: json.dumps({
                "status": "ok",
                "official_acceptance_decision": "pass",
                "official_acceptance_passed": True,
                "message": "测试已通过，版本进入待确认发布状态。",
                "_tool_events": [{"name": "run_agent_workshop_real_data_test", "status": "ok", "detail": "执行完成"}],
            }, ensure_ascii=False),
        )
    )
    runtime.tools.register(
        TradingAgentsRegistryTool(
            metadata=publish_meta,
            func=lambda: json.dumps({"status": "ok", "message": "版本已发布"}, ensure_ascii=False),
        )
    )

    result = await runtime.handle_message(
        user_message="帮我给这个 Agent 工坊版本做一次真数据测试，如果通过了先告诉我结果和当前状态，不要直接发布。",
        session_key="embedded:test:no-auto-publish-after-pass",
        thread_context={
            "spec_id": "spec_test_agent",
            "version_id": "spec_test_agent_v3",
            "version_status": "testing",
        },
    )

    assert result["content"] == "真数据测试已通过，当前状态为待确认发布；如需正式发布，请由用户手动确认。"
    assert result["tools_used"] == ["run_agent_workshop_real_data_test"]
    assert "publish_agent_workshop_version" not in result["tools_used"]
    assert len(provider.calls) == 2

    joined_messages = "\n".join(
        str(message.get("content") or "")
        for message in provider.calls[1]
        if isinstance(message, dict)
    )
    assert "user explicitly confirms publication in the current turn" in joined_messages
    assert "must not trigger automatic publication" in joined_messages


@pytest.mark.asyncio
async def test_runtime_handle_message_updates_session_metadata_for_compaction(tmp_path) -> None:
    provider = _FakeProvider([])
    runtime = EmbeddedNanobotRuntime(provider=provider, workspace=tmp_path)
    runtime._build_capped_initial_messages = AsyncMock(return_value=([{"role": "user", "content": "hi"}], [], 0))

    async def _run(self, _spec):
        return AgentRunResult(
            final_content="done",
            messages=[
                {"role": "user", "content": "hi"},
                {"role": "assistant", "content": "done"},
            ],
            tools_used=[],
            usage={"prompt_tokens": 1, "completion_tokens": 1},
            stop_reason="completed",
            tool_events=[],
        )

    runtime.runner = type("_Runner", (), {"run": _run})()

    result = await runtime.handle_message(
        user_message="帮我继续看一下 600519 这条线索",
        session_key="embedded:test:mem0-sync",
        channel="agent_workshop",
        chat_id="thread-xyz",
        user_id="user-xyz",
        thread_id="thread-xyz",
        thread_context={"workflow_id": "wf-001", "spec_id": "spec-001"},
    )

    session = runtime.sessions.get_or_create("embedded:test:mem0-sync")

    assert result["content"] == "done"
    assert session.metadata["user_id"] == "user-xyz"
    assert session.metadata["thread_id"] == "thread-xyz"
    assert session.metadata["session_key"] == "embedded:test:mem0-sync"
    assert session.metadata["channel"] == "agent_workshop"
    assert session.metadata["chat_id"] == "thread-xyz"
    assert session.metadata["thread_context"] == {"workflow_id": "wf-001", "spec_id": "spec-001"}
    assert session.metadata["symbol"] == "600519"
    assert session.metadata["object_type"] == "stock"
    assert session.metadata["object_key"] == "600519"


@pytest.mark.asyncio
async def test_memory_store_consolidate_mirrors_compaction_to_mem0(tmp_path, monkeypatch) -> None:
    provider = _FakeProvider([
        LLMResponse(
            content=None,
            tool_calls=[
                ToolCallRequest(
                    id="call_save_memory",
                    name="save_memory",
                    arguments={
                        "history_entry": "[2026-04-08 10:00] 完成主题压缩",
                        "memory_update": "# Long-term Memory\n- 保留了关键上下文",
                    },
                )
            ],
        )
    ])
    fake_memory_service = _FakeMemoryService(StoreResult(memory_ids=["m1"], facts_extracted=1))
    monkeypatch.setattr("core.memory.service.get_memory_service", lambda db: fake_memory_service)

    store = MemoryStore(tmp_path, db=object())
    ok = await store.consolidate(
        [{"role": "user", "content": "请记录这轮调试结论", "timestamp": "2026-04-08T10:00:00"}],
        provider,
        "fake-model",
        session_metadata={
            "user_id": "user-123",
            "thread_id": "thread-123",
            "session_key": "embedded:user:123",
            "channel": "agent_workshop",
            "chat_id": "thread-123",
            "symbol": "600519",
            "object_type": "stock",
            "object_key": "600519",
            "thread_context": {"workflow_id": "wf-123", "spec_id": "spec-123"},
        },
    )

    assert ok is True
    assert store.memory_file.read_text(encoding="utf-8") == "# Long-term Memory\n- 保留了关键上下文"
    assert len(fake_memory_service.calls) == 1
    call = fake_memory_service.calls[0]
    assert call["user_id"] == "user-123"
    assert call["agent_id"] == "embedded_nanobot"
    assert call["session_id"] == "thread-123"
    assert call["scope"] == "conversation"
    assert call["metadata"]["source"] == "embedded_nanobot_compaction"
    assert call["metadata"]["symbol"] == "600519"
    assert call["metadata"]["object_type"] == "stock"
    assert call["metadata"]["object_key"] == "600519"
    assert call["metadata"]["workflow_id"] == "wf-123"
    assert call["metadata"]["spec_id"] == "spec-123"
    assert "完成主题压缩" in call["messages"][0]["content"]


@pytest.mark.asyncio
async def test_runtime_handle_message_prefers_explicit_object_binding(tmp_path) -> None:
    provider = _FakeProvider([])
    runtime = EmbeddedNanobotRuntime(provider=provider, workspace=tmp_path)
    runtime._build_capped_initial_messages = AsyncMock(return_value=([{"role": "user", "content": "hi"}], [], 0))

    async def _run(self, _spec):
        return AgentRunResult(
            final_content="done",
            messages=[
                {"role": "user", "content": "hi"},
                {"role": "assistant", "content": "done"},
            ],
            tools_used=[],
            usage={"prompt_tokens": 1, "completion_tokens": 1},
            stop_reason="completed",
            tool_events=[],
        )

    runtime.runner = type("_Runner", (), {"run": _run})()

    await runtime.handle_message(
        user_message="继续看这个版本，不是股票问题",
        session_key="embedded:test:object-binding",
        user_id="user-xyz",
        thread_id="thread-xyz",
        thread_context={
            "workflow_id": "wf-001",
            "object_type": "agent_workshop_version",
            "object_key": "spec_test_agent_v3",
        },
    )

    session = runtime.sessions.get_or_create("embedded:test:object-binding")

    assert session.metadata["object_type"] == "agent_workshop_version"
    assert session.metadata["object_key"] == "spec_test_agent_v3"
    assert "symbol" not in session.metadata


@pytest.mark.asyncio
async def test_memory_store_consolidate_keeps_success_when_mem0_mirror_fails(tmp_path, monkeypatch) -> None:
    provider = _FakeProvider([
        LLMResponse(
            content=None,
            tool_calls=[
                ToolCallRequest(
                    id="call_save_memory",
                    name="save_memory",
                    arguments={
                        "history_entry": "[2026-04-08 10:00] 完成主题压缩",
                        "memory_update": "# Long-term Memory\n- 保留了关键上下文",
                    },
                )
            ],
        )
    ])
    fake_memory_service = _FakeMemoryService(StoreResult(success=False, error="mem0 unavailable"))
    monkeypatch.setattr("core.memory.service.get_memory_service", lambda db: fake_memory_service)

    store = MemoryStore(tmp_path, db=object())
    ok = await store.consolidate(
        [{"role": "user", "content": "请记录这轮调试结论", "timestamp": "2026-04-08T10:00:00"}],
        provider,
        "fake-model",
        session_metadata={"user_id": "user-123", "thread_id": "thread-123", "session_key": "embedded:user:123"},
    )

    assert ok is True
    assert store.memory_file.read_text(encoding="utf-8") == "# Long-term Memory\n- 保留了关键上下文"
    assert len(fake_memory_service.calls) == 1