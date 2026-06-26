import asyncio
import json
import logging
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any


logger = logging.getLogger(__name__)


@dataclass
class ToolCallRequest:
    id: str
    name: str
    arguments: dict[str, Any]
    extra_content: dict[str, Any] | None = None
    provider_specific_fields: dict[str, Any] | None = None
    function_provider_specific_fields: dict[str, Any] | None = None

    def to_openai_tool_call(self) -> dict[str, Any]:
        tool_call = {
            "id": self.id,
            "type": "function",
            "function": {"name": self.name, "arguments": json.dumps(self.arguments, ensure_ascii=False)},
        }
        if self.extra_content:
            tool_call["extra_content"] = self.extra_content
        if self.provider_specific_fields:
            tool_call["provider_specific_fields"] = self.provider_specific_fields
        if self.function_provider_specific_fields:
            tool_call["function"]["provider_specific_fields"] = self.function_provider_specific_fields
        return tool_call


@dataclass
class LLMResponse:
    content: str | None
    tool_calls: list[ToolCallRequest] = field(default_factory=list)
    finish_reason: str = "stop"
    usage: dict[str, int] = field(default_factory=dict)
    reasoning_content: str | None = None
    thinking_blocks: list[dict[str, Any]] | None = None

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


@dataclass(frozen=True)
class GenerationSettings:
    temperature: float = 0.7
    max_tokens: int = 4096
    reasoning_effort: str | None = None


class LLMProvider(ABC):
    _CHAT_RETRY_DELAYS = (1, 2, 4)
    _TRANSIENT_ERROR_MARKERS = ("429", "rate limit", "500", "502", "503", "504", "overloaded", "timeout", "timed out", "connection", "server error", "temporarily unavailable", "unterminated string", "jsondecodeerror")
    _SENTINEL = object()

    def __init__(self, api_key: str | None = None, api_base: str | None = None):
        self.api_key = api_key
        self.api_base = api_base
        self.generation = GenerationSettings()

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        reasoning_effort: str | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> LLMResponse:
        raise NotImplementedError

    async def chat_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        reasoning_effort: str | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        on_content_delta: Callable[[str], Awaitable[None]] | None = None,
    ) -> LLMResponse:
        response = await self.chat(messages=messages, tools=tools, model=model, max_tokens=max_tokens, temperature=temperature, reasoning_effort=reasoning_effort, tool_choice=tool_choice)
        if on_content_delta and response.content:
            await on_content_delta(response.content)
        return response

    @classmethod
    def _is_transient_error(cls, content: str | None) -> bool:
        err = (content or "").lower()
        return any(marker in err for marker in cls._TRANSIENT_ERROR_MARKERS)

    async def _safe_chat(self, **kwargs: Any) -> LLMResponse:
        try:
            return await self.chat(**kwargs)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            return LLMResponse(content=f"Error calling LLM: {exc}", finish_reason="error")

    async def _safe_chat_stream(self, **kwargs: Any) -> LLMResponse:
        try:
            return await self.chat_stream(**kwargs)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            return LLMResponse(content=f"Error calling LLM: {exc}", finish_reason="error")

    async def chat_stream_with_retry(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None, model: str | None = None, max_tokens: object = _SENTINEL, temperature: object = _SENTINEL, reasoning_effort: object = _SENTINEL, tool_choice: str | dict[str, Any] | None = None, on_content_delta: Callable[[str], Awaitable[None]] | None = None) -> LLMResponse:
        if max_tokens is self._SENTINEL:
            max_tokens = self.generation.max_tokens
        if temperature is self._SENTINEL:
            temperature = self.generation.temperature
        if reasoning_effort is self._SENTINEL:
            reasoning_effort = self.generation.reasoning_effort
        kwargs = dict(messages=messages, tools=tools, model=model, max_tokens=max_tokens, temperature=temperature, reasoning_effort=reasoning_effort, tool_choice=tool_choice, on_content_delta=on_content_delta)
        for attempt, delay in enumerate(self._CHAT_RETRY_DELAYS, start=1):
            response = await self._safe_chat_stream(**kwargs)
            if response.finish_reason != "error":
                return response
            if not self._is_transient_error(response.content):
                return response
            logger.warning(
                "Embedded nanobot transient stream error (attempt %s/%s), retrying in %ss: %s",
                attempt,
                len(self._CHAT_RETRY_DELAYS),
                delay,
                (response.content or "")[:120].lower(),
            )
            await asyncio.sleep(delay)
        return await self._safe_chat_stream(**kwargs)

    async def chat_with_retry(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None, model: str | None = None, max_tokens: object = _SENTINEL, temperature: object = _SENTINEL, reasoning_effort: object = _SENTINEL, tool_choice: str | dict[str, Any] | None = None) -> LLMResponse:
        if max_tokens is self._SENTINEL:
            max_tokens = self.generation.max_tokens
        if temperature is self._SENTINEL:
            temperature = self.generation.temperature
        if reasoning_effort is self._SENTINEL:
            reasoning_effort = self.generation.reasoning_effort
        kwargs = dict(messages=messages, tools=tools, model=model, max_tokens=max_tokens, temperature=temperature, reasoning_effort=reasoning_effort, tool_choice=tool_choice)
        for attempt, delay in enumerate(self._CHAT_RETRY_DELAYS, start=1):
            response = await self._safe_chat(**kwargs)
            if response.finish_reason != "error":
                return response
            if not self._is_transient_error(response.content):
                return response
            logger.warning(
                "Embedded nanobot transient error (attempt %s/%s), retrying in %ss: %s",
                attempt,
                len(self._CHAT_RETRY_DELAYS),
                delay,
                (response.content or "")[:120].lower(),
            )
            await asyncio.sleep(delay)
        return await self._safe_chat(**kwargs)

    def estimate_prompt_tokens(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None, model: str | None = None) -> tuple[int, str]:
        from core.embedded_nanobot.utils.helpers import estimate_prompt_tokens
        return estimate_prompt_tokens(messages, tools), "embedded_tiktoken"

    @abstractmethod
    def get_default_model(self) -> str:
        raise NotImplementedError