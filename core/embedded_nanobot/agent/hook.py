from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.embedded_nanobot.providers.base import LLMResponse, ToolCallRequest


@dataclass(slots=True)
class AgentHookContext:
    iteration: int
    messages: list[dict[str, Any]]
    response: LLMResponse | None = None
    usage: dict[str, int] = field(default_factory=dict)
    tool_calls: list[ToolCallRequest] = field(default_factory=list)
    tool_results: list[Any] = field(default_factory=list)
    tool_events: list[dict[str, str]] = field(default_factory=list)
    final_content: str | None = None
    stop_reason: str | None = None
    error: str | None = None


class AgentHook:
    def wants_streaming(self) -> bool:
        return False

    async def before_iteration(self, context: AgentHookContext) -> None:
        return None

    async def on_stream(self, context: AgentHookContext, delta: str) -> None:
        return None

    async def on_stream_end(self, context: AgentHookContext, *, resuming: bool) -> None:
        return None

    async def before_execute_tools(self, context: AgentHookContext) -> None:
        return None

    async def after_iteration(self, context: AgentHookContext) -> None:
        return None

    def finalize_content(self, context: AgentHookContext, content: str | None) -> str | None:
        return content