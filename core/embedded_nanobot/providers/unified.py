from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.llm import UnifiedLLMClient
from core.llm.models import Message, MessageRole, ToolCall as CoreToolCall
from core.embedded_nanobot.providers.base import LLMProvider, LLMResponse, ToolCallRequest

_TRACE_LOGGER_NAME = "embedded_nanobot.llm_trace"
_TRACE_LOG_FILE = Path("logs") / "embedded_nanobot_llm.log"


def _safe_json_default(value: Any) -> str:
    return str(value)


def _get_trace_logger() -> logging.Logger:
    logger = logging.getLogger(_TRACE_LOGGER_NAME)
    if logger.handlers:
        return logger

    _TRACE_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        _TRACE_LOG_FILE,
        maxBytes=20 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


def _normalize_message_for_log(msg: dict[str, Any]) -> dict[str, Any]:
    normalized = {
        "role": msg.get("role"),
        "content": msg.get("content"),
        "name": msg.get("name"),
        "tool_call_id": msg.get("tool_call_id"),
    }
    tool_calls = msg.get("tool_calls") or []
    if isinstance(tool_calls, list) and tool_calls:
        normalized["tool_calls"] = tool_calls
    return normalized


def _normalize_response_for_log(response: Any) -> dict[str, Any]:
    tool_calls = []
    for tool in getattr(response, "tool_calls", []) or []:
        tool_calls.append({
            "id": getattr(tool, "id", ""),
            "name": getattr(tool, "name", ""),
            "arguments": getattr(tool, "arguments", {}),
        })
    return {
        "content": getattr(response, "content", None),
        "reasoning_content": getattr(response, "reasoning_content", None),
        "thinking_blocks": getattr(response, "thinking_blocks", None),
        "tool_calls": tool_calls,
        "finish_reason": getattr(response, "finish_reason", None),
        "usage": getattr(response, "usage", None),
        "model": getattr(response, "model", None),
        "provider": getattr(response, "provider", None),
    }


def _write_trace(event: str, payload: dict[str, Any]) -> None:
    trace_logger = _get_trace_logger()
    trace_logger.info(
        json.dumps({"event": event, **payload}, ensure_ascii=False, default=_safe_json_default)
    )


class TradingAgentsLLMProvider(LLMProvider):
    def __init__(self, client: UnifiedLLMClient, model: str):
        super().__init__()
        self.client = client
        self._default_model = model

    @classmethod
    async def from_database(cls, db, preferred_model: str | None = None):
        from app.services.intelligent_assistant_service import _get_assistant_llm_config

        config = await _get_assistant_llm_config(db, use_reasoning_model=True, preferred_models={"model": preferred_model} if preferred_model else None)
        if not config:
            raise ValueError("数据库中没有可用的 LLM 配置")
        client = UnifiedLLMClient.from_config(config)
        provider = cls(client=client, model=config.model)
        provider.generation = provider.generation.__class__(
            temperature=config.temperature,
            max_tokens=max(config.max_tokens or 4096, 16384),
            reasoning_effort=None,
        )
        return provider

    def _convert_messages(self, messages: list[dict[str, Any]]) -> list[Message]:
        converted: list[Message] = []
        for msg in messages:
            role = MessageRole(msg.get("role", "user"))
            tool_calls = None
            raw_tool_calls = msg.get("tool_calls") or []
            if raw_tool_calls:
                tool_calls = []
                for item in raw_tool_calls:
                    if isinstance(item, dict):
                        function = item.get("function") or {}
                        arguments = function.get("arguments") or {}
                        if isinstance(arguments, str):
                            import json
                            try:
                                arguments = json.loads(arguments)
                            except Exception:
                                arguments = {}
                        tool_calls.append(CoreToolCall(id=str(item.get("id") or ""), name=str(function.get("name") or ""), arguments=arguments if isinstance(arguments, dict) else {}))
            converted.append(Message(
                role=role,
                content=msg.get("content") if isinstance(msg.get("content"), str) else None,
                name=msg.get("name"),
                tool_call_id=msg.get("tool_call_id"),
                tool_calls=tool_calls,
            ))
        return converted

    async def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None, model: str | None = None, max_tokens: int = 4096, temperature: float = 0.7, reasoning_effort: str | None = None, tool_choice: str | dict[str, Any] | None = None) -> LLMResponse:
        request_id = str(uuid4())
        selected_model = model or self._default_model
        _write_trace(
            "llm_request",
            {
                "request_id": request_id,
                "model": selected_model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "reasoning_effort": reasoning_effort,
                "tool_choice": tool_choice,
                "tools": tools or [],
                "messages": [_normalize_message_for_log(item) for item in messages],
            },
        )
        try:
            response = await self.client.achat(
                self._convert_messages(messages),
                tools=tools,
                auto_execute_tools=False,
                model=selected_model,
                max_tokens=max_tokens,
                temperature=temperature,
                tool_choice=tool_choice,
            )
        except Exception as exc:
            _write_trace(
                "llm_error",
                {
                    "request_id": request_id,
                    "model": selected_model,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
            )
            raise

        _write_trace(
            "llm_response",
            {
                "request_id": request_id,
                "model": selected_model,
                "response": _normalize_response_for_log(response),
            },
        )
        if not getattr(response, "content", None) and not getattr(response, "tool_calls", None):
            _write_trace(
                "llm_empty_visible_response",
                {
                    "request_id": request_id,
                    "model": selected_model,
                    "finish_reason": getattr(response, "finish_reason", None),
                    "usage": getattr(response, "usage", None),
                    "has_reasoning_content": bool(getattr(response, "reasoning_content", None)),
                    "has_thinking_blocks": bool(getattr(response, "thinking_blocks", None)),
                },
            )
        return LLMResponse(
            content=response.content,
            tool_calls=[ToolCallRequest(id=tool.id, name=tool.name, arguments=tool.arguments) for tool in response.tool_calls],
            finish_reason=response.finish_reason or "stop",
            usage=response.usage or {},
            reasoning_content=getattr(response, "reasoning_content", None),
            thinking_blocks=getattr(response, "thinking_blocks", None),
        )

    def get_default_model(self) -> str:
        return self._default_model