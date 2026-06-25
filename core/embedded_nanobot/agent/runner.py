from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any

from core.embedded_nanobot.agent.hook import AgentHook, AgentHookContext
from core.embedded_nanobot.agent.tools.registry import ToolRegistry
from core.embedded_nanobot.providers.base import LLMProvider, ToolCallRequest
from core.embedded_nanobot.utils.helpers import build_assistant_message, sanitize_tool_result_content

_DEFAULT_MAX_ITERATIONS_MESSAGE = "I reached the maximum number of tool call iterations ({max_iterations}) without completing the task."
_DEFAULT_ERROR_MESSAGE = "Sorry, I encountered an error calling the AI model."
_DEFAULT_EMPTY_RESPONSE_MESSAGE = "本轮模型调用已结束，但没有返回可显示的正文内容。通常是模型只返回了内部推理内容，或上游响应异常。请重试；如果问题持续出现，请检查 logs/embedded_nanobot_llm.log 中对应请求的原始响应。"


@dataclass(slots=True)
class AgentRunSpec:
    initial_messages: list[dict[str, Any]]
    tools: ToolRegistry
    model: str
    max_iterations: int
    temperature: float | None = None
    max_tokens: int | None = None
    reasoning_effort: str | None = None
    hook: AgentHook | None = None
    error_message: str | None = _DEFAULT_ERROR_MESSAGE
    max_iterations_message: str | None = None
    concurrent_tools: bool = False
    fail_on_tool_error: bool = False


@dataclass(slots=True)
class AgentRunResult:
    final_content: str | None
    messages: list[dict[str, Any]]
    tools_used: list[str] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)
    stop_reason: str = "completed"
    error: str | None = None
    tool_events: list[dict[str, Any]] = field(default_factory=list)


class AgentRunner:
    def __init__(self, provider: LLMProvider):
        self.provider = provider

    def _normalize_tool_event(self, raw_event: dict[str, Any], fallback_name: str, fallback_status: str = "ok", fallback_detail: str = "") -> dict[str, str]:
        name = str(raw_event.get("name") or raw_event.get("tool") or raw_event.get("stage") or fallback_name).strip() or fallback_name
        status = str(raw_event.get("status") or raw_event.get("event") or fallback_status).strip().lower() or fallback_status
        detail = str(raw_event.get("detail") or raw_event.get("message") or raw_event.get("summary") or fallback_detail).replace("\n", " ").strip()
        if not detail:
            detail = "(empty)"
        elif len(detail) > 120:
            detail = detail[:120] + "..."
        return {"name": name, "status": status, "detail": detail}

    def _extract_structured_tool_events(self, tool_name: str, result: Any) -> list[dict[str, str]]:
        if not isinstance(result, str):
            return []
        try:
            payload = json.loads(result)
        except Exception:
            return []
        if not isinstance(payload, dict):
            return []

        raw_events = payload.get("_tool_events") or payload.get("tool_events")
        events: list[dict[str, str]] = []
        if isinstance(raw_events, list):
            for raw_event in raw_events:
                if isinstance(raw_event, dict):
                    events.append(self._normalize_tool_event(raw_event, fallback_name=tool_name))

        if events:
            return events

        status = str(payload.get("status") or "").strip().lower()
        detail = str(payload.get("message") or payload.get("summary") or "").strip()
        if status or detail:
            normalized_status = "error" if status in {"error", "failed", "fail"} else "ok"
            return [self._normalize_tool_event({}, fallback_name=tool_name, fallback_status=normalized_status, fallback_detail=detail)]
        return []

    async def run(self, spec: AgentRunSpec) -> AgentRunResult:
        hook = spec.hook or AgentHook()
        messages = list(spec.initial_messages)
        final_content: str | None = None
        tools_used: list[str] = []
        usage = {"prompt_tokens": 0, "completion_tokens": 0}
        error: str | None = None
        stop_reason = "completed"
        tool_events: list[dict[str, str]] = []

        for iteration in range(spec.max_iterations):
            context = AgentHookContext(iteration=iteration, messages=messages)
            await hook.before_iteration(context)
            kwargs: dict[str, Any] = {"messages": messages, "tools": spec.tools.get_definitions(), "model": spec.model}
            if spec.temperature is not None:
                kwargs["temperature"] = spec.temperature
            if spec.max_tokens is not None:
                kwargs["max_tokens"] = spec.max_tokens
            if spec.reasoning_effort is not None:
                kwargs["reasoning_effort"] = spec.reasoning_effort
            if hook.wants_streaming():
                async def _stream(delta: str) -> None:
                    await hook.on_stream(context, delta)
                response = await self.provider.chat_stream_with_retry(**kwargs, on_content_delta=_stream)
            else:
                response = await self.provider.chat_with_retry(**kwargs)
            raw_usage = response.usage or {}
            usage = {"prompt_tokens": int(raw_usage.get("prompt_tokens", 0) or 0), "completion_tokens": int(raw_usage.get("completion_tokens", 0) or 0)}
            context.response = response
            context.usage = usage
            context.tool_calls = list(response.tool_calls)
            if response.has_tool_calls:
                if hook.wants_streaming():
                    await hook.on_stream_end(context, resuming=True)
                messages.append(build_assistant_message(response.content or "", tool_calls=[tc.to_openai_tool_call() for tc in response.tool_calls], reasoning_content=response.reasoning_content, thinking_blocks=response.thinking_blocks))
                tools_used.extend(tc.name for tc in response.tool_calls)
                await hook.before_execute_tools(context)
                results, new_events, fatal_error = await self._execute_tools(spec, response.tool_calls)
                tool_events.extend(new_events)
                context.tool_results = list(results)
                context.tool_events = list(new_events)
                if fatal_error is not None:
                    error = f"Error: {type(fatal_error).__name__}: {fatal_error}"
                    stop_reason = "tool_error"
                    context.error = error
                    context.stop_reason = stop_reason
                    await hook.after_iteration(context)
                    break
                for tool_call, result in zip(response.tool_calls, results):
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_call.name,
                        "content": sanitize_tool_result_content(result),
                    })
                await hook.after_iteration(context)
                continue
            if hook.wants_streaming():
                await hook.on_stream_end(context, resuming=False)
            clean = hook.finalize_content(context, response.content)
            if response.finish_reason == "error":
                final_content = clean or spec.error_message or _DEFAULT_ERROR_MESSAGE
                stop_reason = "error"
                error = final_content
                context.final_content = final_content
                context.error = error
                context.stop_reason = stop_reason
                await hook.after_iteration(context)
                break
            if clean is None or (isinstance(clean, str) and not clean.strip()):
                final_content = _DEFAULT_EMPTY_RESPONSE_MESSAGE
                stop_reason = "empty_response"
                error = "LLM completed without visible content"
                messages.append(build_assistant_message(
                    final_content,
                    reasoning_content=response.reasoning_content,
                    thinking_blocks=response.thinking_blocks,
                ))
                context.final_content = final_content
                context.error = error
                context.stop_reason = stop_reason
                await hook.after_iteration(context)
                break
            messages.append(build_assistant_message(clean, reasoning_content=response.reasoning_content, thinking_blocks=response.thinking_blocks))
            final_content = clean
            context.final_content = final_content
            context.stop_reason = stop_reason
            await hook.after_iteration(context)
            break
        else:
            stop_reason = "max_iterations"
            final_content = (spec.max_iterations_message or _DEFAULT_MAX_ITERATIONS_MESSAGE).format(max_iterations=spec.max_iterations)

        return AgentRunResult(final_content=final_content, messages=messages, tools_used=tools_used, usage=usage, stop_reason=stop_reason, error=error, tool_events=tool_events)

    async def _execute_tools(self, spec: AgentRunSpec, tool_calls: list[ToolCallRequest]) -> tuple[list[Any], list[dict[str, Any]], BaseException | None]:
        if spec.concurrent_tools:
            tool_results = await asyncio.gather(*(self._run_tool(spec, tool_call) for tool_call in tool_calls))
        else:
            tool_results = [await self._run_tool(spec, tool_call) for tool_call in tool_calls]
        results: list[Any] = []
        events: list[dict[str, Any]] = []
        fatal_error: BaseException | None = None
        for result, tool_events, err in tool_results:
            results.append(result)
            events.extend(tool_events)
            if err is not None and fatal_error is None:
                fatal_error = err
        return results, events, fatal_error

    async def _run_tool(self, spec: AgentRunSpec, tool_call: ToolCallRequest) -> tuple[Any, list[dict[str, Any]], BaseException | None]:
        try:
            result = await spec.tools.execute(tool_call.name, tool_call.arguments)
        except asyncio.CancelledError:
            raise
        except BaseException as exc:
            event = {"name": tool_call.name, "status": "error", "detail": str(exc)}
            if spec.fail_on_tool_error:
                return f"Error: {type(exc).__name__}: {exc}", [event], exc
            return f"Error: {type(exc).__name__}: {exc}", [event], None
        structured_events = self._extract_structured_tool_events(tool_call.name, result)
        if structured_events:
            fatal_error = None
            for event in structured_events:
                if event.get("status") == "error" and spec.fail_on_tool_error:
                    fatal_error = RuntimeError(event.get("detail") or f"{tool_call.name} failed")
                    break
            return result, structured_events, fatal_error
        detail = "" if result is None else str(result)
        detail = detail.replace("\n", " ").strip()
        if not detail:
            detail = "(empty)"
        elif len(detail) > 120:
            detail = detail[:120] + "..."
        return result, [{"name": tool_call.name, "status": "error" if isinstance(result, str) and result.startswith("Error") else "ok", "detail": detail}], None