"""One-call structured-output adapter with auditable, fail-closed errors."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib
import json
import re
import time
from typing import Any, Type

from pydantic import BaseModel

from .decision_schemas import ModelExecutionMeta


@dataclass(frozen=True)
class StructuredInvocation:
    payload: dict[str, Any] | None
    model_meta: ModelExecutionMeta
    failure_status: str | None = None
    error_type: str | None = None
    error_message: str | None = None
    attempt_metas: tuple[ModelExecutionMeta, ...] = ()


def _sanitise_error(error: BaseException | str) -> str:
    text = str(error)
    text = re.sub(
        r"(?i)(authorization|api[-_ ]?key|access[-_ ]?token|bearer)"
        r"(\s*[:=]\s*|\s+)[^\s,;]+",
        r"\1=[REDACTED]",
        text,
    )
    text = re.sub(r"\bsk-[A-Za-z0-9_-]{8,}\b", "[REDACTED]", text)
    if text:
        return text[:500]
    if isinstance(error, BaseException):
        return error.__class__.__name__
    return "unspecified error"


def _json_schema_without_execution_meta(
    schema_model: Type[BaseModel],
) -> dict[str, Any]:
    """Models must not invent provider/runtime audit metadata."""

    schema = deepcopy(schema_model.model_json_schema())

    def strip_meta(node: Any) -> None:
        if isinstance(node, dict):
            properties = node.get("properties")
            if isinstance(properties, dict):
                properties.pop("model_meta", None)
            required = node.get("required")
            if isinstance(required, list) and "model_meta" in required:
                required.remove("model_meta")
            for value in node.values():
                strip_meta(value)
        elif isinstance(node, list):
            for value in node:
                strip_meta(value)

    strip_meta(schema)
    definitions = schema.get("$defs")
    if isinstance(definitions, dict):
        definitions.pop("ModelExecutionMeta", None)
    return schema


def model_output_schema_json(schema_model: Type[BaseModel]) -> str:
    """Return the exact model-facing schema without runtime-owned metadata."""

    return json.dumps(
        _json_schema_without_execution_meta(schema_model),
        ensure_ascii=False,
        sort_keys=True,
    )


def _model_name(llm: Any, configured_name: str | None) -> str:
    return str(
        configured_name
        or getattr(llm, "model_name", None)
        or getattr(llm, "model", None)
        or llm.__class__.__name__
    )


def _extract_request_id(response: Any) -> str | None:
    metadata = getattr(response, "response_metadata", None)
    if not isinstance(metadata, dict):
        return None
    for key in ("request_id", "id", "response_id"):
        value = metadata.get(key)
        if value:
            return str(value)
    return None


def _extract_token_usage(response: Any) -> tuple[int | None, int | None, int | None]:
    usage = getattr(response, "usage_metadata", None)
    if not isinstance(usage, dict):
        metadata = getattr(response, "response_metadata", None)
        if isinstance(metadata, dict):
            usage = metadata.get("token_usage") or metadata.get("usage")
    if not isinstance(usage, dict):
        return None, None, None
    input_tokens = usage.get("input_tokens", usage.get("prompt_tokens"))
    output_tokens = usage.get("output_tokens", usage.get("completion_tokens"))
    total_tokens = usage.get("total_tokens")
    try:
        input_value = int(input_tokens) if input_tokens is not None else None
        output_value = int(output_tokens) if output_tokens is not None else None
        total_value = int(total_tokens) if total_tokens is not None else None
    except (TypeError, ValueError):
        return None, None, None
    if total_value is None and input_value is not None and output_value is not None:
        total_value = input_value + output_value
    return input_value, output_value, total_value


def _classify_provider_error(exc: BaseException) -> str:
    text = f"{exc.__class__.__name__} {exc}".lower()
    status = getattr(exc, "status_code", None)
    if status in {401, 403} or "unauthorized" in text or "authentication" in text:
        return "UNAUTHORIZED"
    if status == 404 or "model_not_found" in text or "model not found" in text:
        return "MODEL_NOT_FOUND"
    if status == 429 or "rate limit" in text or "ratelimit" in text:
        return "RATE_LIMITED"
    if (
        isinstance(exc, TimeoutError)
        or "timeout" in exc.__class__.__name__.lower()
        or "timed out" in text
    ):
        return "TIMEOUT"
    return "PROVIDER_ERROR"


def _serialise_raw(raw: Any) -> str:
    if isinstance(raw, BaseModel):
        raw = raw.model_dump(mode="json")
    if isinstance(raw, dict):
        return json.dumps(raw, ensure_ascii=False, sort_keys=True, default=str)
    return str(raw)


def _with_json_schema_instruction(
    messages: Any,
    *,
    schema: dict[str, Any],
) -> list[Any]:
    if not isinstance(messages, (list, tuple)):
        raise TypeError("JSON_SCHEMA mode requires an ordered message list")
    instruction = (
        "\n\nReturn exactly one JSON object matching this schema. Do not add "
        "markdown or commentary:\n"
        + json.dumps(schema, ensure_ascii=False, sort_keys=True)
    )
    copied = deepcopy(list(messages))
    if (
        copied
        and isinstance(copied[0], dict)
        and copied[0].get("role") == "system"
    ):
        copied[0]["content"] = str(copied[0].get("content") or "") + instruction
    else:
        copied.insert(0, {"role": "system", "content": instruction.strip()})
    return copied


def _finish_meta(
    *,
    provider: str,
    model_name: str,
    model_version: str,
    prompt_name: str,
    prompt_version: str,
    started_at: datetime,
    started_perf: float,
    execution_status: str,
    request_id: str | None = None,
    error_type: str | None = None,
    error_message: str | None = None,
    raw_text: str | None = None,
    trace_id: str | None = None,
    template_hash: str | None = None,
    context_hash: str | None = None,
    input_hash: str | None = None,
    attempt_number: int = 1,
    model_profile_id: str | None = None,
    model_profile_version: str | None = None,
    prompt_id: str | None = None,
    structured_output_mode: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    total_tokens: int | None = None,
    estimated_cost: float | None = None,
    cost_currency: str | None = None,
) -> ModelExecutionMeta:
    finished_at = datetime.now(timezone.utc)
    return ModelExecutionMeta(
        provider=provider or "unknown",
        model_name=model_name or "unknown",
        model_version=model_version or model_name or "unknown",
        prompt_name=prompt_name,
        prompt_version=prompt_version,
        started_at=started_at,
        finished_at=finished_at,
        latency_ms=max(0.0, (time.perf_counter() - started_perf) * 1000),
        execution_status=execution_status,
        request_id=request_id,
        trace_id=trace_id,
        error_type=error_type,
        error_message=error_message,
        raw_output_hash=(
            hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
            if raw_text
            else None
        ),
        template_hash=template_hash,
        context_hash=context_hash,
        input_hash=input_hash,
        attempt_number=attempt_number,
        model_profile_id=model_profile_id,
        model_profile_version=model_profile_version,
        prompt_id=prompt_id,
        structured_output_mode=structured_output_mode,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        estimated_cost=estimated_cost,
        cost_currency=cost_currency,
    )


def not_run_meta(
    *,
    llm: Any,
    provider: str,
    configured_model_name: str | None,
    prompt_name: str,
    prompt_version: str,
    error_type: str,
    error_message: str,
    trace_id: str | None = None,
    template_hash: str | None = None,
    context_hash: str | None = None,
    input_hash: str | None = None,
    attempt_number: int = 1,
) -> ModelExecutionMeta:
    now = datetime.now(timezone.utc)
    name = _model_name(llm, configured_model_name)
    return ModelExecutionMeta(
        provider=provider or "unknown",
        model_name=name,
        model_version=name,
        prompt_name=prompt_name,
        prompt_version=prompt_version,
        started_at=now,
        finished_at=now,
        latency_ms=0,
        execution_status="NOT_RUN",
        trace_id=trace_id,
        error_type=error_type,
        error_message=_sanitise_error(error_message),
        template_hash=template_hash,
        context_hash=context_hash,
        input_hash=input_hash,
        attempt_number=attempt_number,
    )


def _invoke_json_object_once(
    *,
    llm: Any,
    messages: Any,
    schema_model: Type[BaseModel],
    provider: str,
    configured_model_name: str | None,
    prompt_name: str,
    prompt_version: str,
    trace_id: str | None = None,
    template_hash: str | None = None,
    context_hash: str | None = None,
    input_hash: str | None = None,
    attempt_number: int = 1,
    structured_output_mode: str = "AUTO",
    model_profile_id: str | None = None,
    model_profile_version: str | None = None,
    prompt_id: str | None = None,
    input_cost_per_million: float | None = None,
    output_cost_per_million: float | None = None,
    cost_currency: str = "USD",
) -> StructuredInvocation:
    """Invoke the model exactly once and return one strict JSON object.

    Native structured output is preferred. If the adapter cannot even construct
    such a runnable, the same model is invoked once with a strict-JSON prompt.
    """

    started_at = datetime.now(timezone.utc)
    started_perf = time.perf_counter()
    name = _model_name(llm, configured_model_name)
    schema = _json_schema_without_execution_meta(schema_model)
    runnable = None
    effective_mode: str | None = None
    invocation_messages = messages

    if structured_output_mode not in {
        "AUTO",
        "NATIVE_SCHEMA",
        "TOOL_CALL",
        "JSON_SCHEMA",
    }:
        raise ValueError("unsupported structured_output_mode")
    with_structured_output = getattr(llm, "with_structured_output", None)
    if structured_output_mode in {"AUTO", "NATIVE_SCHEMA"} and callable(
        with_structured_output
    ):
        try:
            runnable = (
                with_structured_output(schema)
                if structured_output_mode == "AUTO"
                else with_structured_output(schema, include_raw=True)
            )
            effective_mode = "NATIVE_SCHEMA"
        except (AttributeError, NotImplementedError, TypeError, ValueError) as exc:
            if structured_output_mode == "NATIVE_SCHEMA":
                error_message = _sanitise_error(exc)
                meta = _finish_meta(
                    provider=provider,
                    model_name=name,
                    model_version=name,
                    prompt_name=prompt_name,
                    prompt_version=prompt_version,
                    started_at=started_at,
                    started_perf=started_perf,
                    execution_status="MODEL_FAILED",
                    error_type="STRUCTURED_OUTPUT_UNSUPPORTED",
                    error_message=error_message,
                    trace_id=trace_id,
                    template_hash=template_hash,
                    context_hash=context_hash,
                    input_hash=input_hash,
                    attempt_number=attempt_number,
                    model_profile_id=model_profile_id,
                    model_profile_version=model_profile_version,
                    prompt_id=prompt_id,
                    structured_output_mode=structured_output_mode,
                )
                return StructuredInvocation(
                    payload=None,
                    model_meta=meta,
                    failure_status="MODEL_FAILED",
                    error_type="STRUCTURED_OUTPUT_UNSUPPORTED",
                    error_message=error_message,
                )
            runnable = None
    elif structured_output_mode == "NATIVE_SCHEMA":
        error_message = "provider adapter has no native structured-output interface"
        meta = _finish_meta(
            provider=provider,
            model_name=name,
            model_version=name,
            prompt_name=prompt_name,
            prompt_version=prompt_version,
            started_at=started_at,
            started_perf=started_perf,
            execution_status="MODEL_FAILED",
            error_type="STRUCTURED_OUTPUT_UNSUPPORTED",
            error_message=error_message,
            trace_id=trace_id,
            template_hash=template_hash,
            context_hash=context_hash,
            input_hash=input_hash,
            attempt_number=attempt_number,
            model_profile_id=model_profile_id,
            model_profile_version=model_profile_version,
            prompt_id=prompt_id,
            structured_output_mode=structured_output_mode,
        )
        return StructuredInvocation(
            payload=None,
            model_meta=meta,
            failure_status="MODEL_FAILED",
            error_type="STRUCTURED_OUTPUT_UNSUPPORTED",
            error_message=error_message,
        )

    bind_tools = getattr(llm, "bind_tools", None)
    if (
        runnable is None
        and structured_output_mode in {"AUTO", "TOOL_CALL"}
        and callable(bind_tools)
    ):
        try:
            runnable = bind_tools(
                [schema_model],
                tool_choice=schema_model.__name__,
            )
            effective_mode = "TOOL_CALL"
        except (AttributeError, NotImplementedError, TypeError, ValueError) as exc:
            if structured_output_mode == "TOOL_CALL":
                error_message = _sanitise_error(exc)
                meta = _finish_meta(
                    provider=provider,
                    model_name=name,
                    model_version=name,
                    prompt_name=prompt_name,
                    prompt_version=prompt_version,
                    started_at=started_at,
                    started_perf=started_perf,
                    execution_status="MODEL_FAILED",
                    error_type="STRUCTURED_OUTPUT_UNSUPPORTED",
                    error_message=error_message,
                    trace_id=trace_id,
                    template_hash=template_hash,
                    context_hash=context_hash,
                    input_hash=input_hash,
                    attempt_number=attempt_number,
                    model_profile_id=model_profile_id,
                    model_profile_version=model_profile_version,
                    prompt_id=prompt_id,
                    structured_output_mode=structured_output_mode,
                )
                return StructuredInvocation(
                    payload=None,
                    model_meta=meta,
                    failure_status="MODEL_FAILED",
                    error_type="STRUCTURED_OUTPUT_UNSUPPORTED",
                    error_message=error_message,
                )
            runnable = None
    elif runnable is None and structured_output_mode == "TOOL_CALL":
        error_message = "provider adapter has no tool-call interface"
        meta = _finish_meta(
            provider=provider,
            model_name=name,
            model_version=name,
            prompt_name=prompt_name,
            prompt_version=prompt_version,
            started_at=started_at,
            started_perf=started_perf,
            execution_status="MODEL_FAILED",
            error_type="STRUCTURED_OUTPUT_UNSUPPORTED",
            error_message=error_message,
            trace_id=trace_id,
            template_hash=template_hash,
            context_hash=context_hash,
            input_hash=input_hash,
            attempt_number=attempt_number,
            model_profile_id=model_profile_id,
            model_profile_version=model_profile_version,
            prompt_id=prompt_id,
            structured_output_mode=structured_output_mode,
        )
        return StructuredInvocation(
            payload=None,
            model_meta=meta,
            failure_status="MODEL_FAILED",
            error_type="STRUCTURED_OUTPUT_UNSUPPORTED",
            error_message=error_message,
        )

    if runnable is None:
        effective_mode = "JSON_SCHEMA"
        try:
            invocation_messages = _with_json_schema_instruction(
                messages,
                schema=schema,
            )
        except TypeError as exc:
            error_message = _sanitise_error(exc)
            meta = _finish_meta(
                provider=provider,
                model_name=name,
                model_version=name,
                prompt_name=prompt_name,
                prompt_version=prompt_version,
                started_at=started_at,
                started_perf=started_perf,
                execution_status="MODEL_FAILED",
                error_type="STRUCTURED_OUTPUT_UNSUPPORTED",
                error_message=error_message,
                trace_id=trace_id,
                template_hash=template_hash,
                context_hash=context_hash,
                input_hash=input_hash,
                attempt_number=attempt_number,
                model_profile_id=model_profile_id,
                model_profile_version=model_profile_version,
                prompt_id=prompt_id,
                structured_output_mode=effective_mode,
            )
            return StructuredInvocation(
                payload=None,
                model_meta=meta,
                failure_status="MODEL_FAILED",
                error_type="STRUCTURED_OUTPUT_UNSUPPORTED",
                error_message=error_message,
            )

    try:
        response = (runnable or llm).invoke(invocation_messages)
    except Exception as exc:
        error_type = _classify_provider_error(exc)
        if structured_output_mode == "AUTO" and error_type == "TIMEOUT":
            error_type = "MODEL_TIMEOUT"
        error_message = _sanitise_error(exc)
        meta = _finish_meta(
            provider=provider,
            model_name=name,
            model_version=name,
            prompt_name=prompt_name,
            prompt_version=prompt_version,
            started_at=started_at,
            started_perf=started_perf,
            execution_status="MODEL_FAILED",
            error_type=error_type,
            error_message=error_message,
            trace_id=trace_id,
            template_hash=template_hash,
            context_hash=context_hash,
            input_hash=input_hash,
            attempt_number=attempt_number,
            model_profile_id=model_profile_id,
            model_profile_version=model_profile_version,
            prompt_id=prompt_id,
            structured_output_mode=effective_mode,
        )
        return StructuredInvocation(
            payload=None,
            model_meta=meta,
            failure_status="MODEL_FAILED",
            error_type=error_type,
            error_message=error_message,
        )

    usage_response = response
    parsed_response = response
    if (
        effective_mode == "NATIVE_SCHEMA"
        and isinstance(response, dict)
        and "parsed" in response
        and "raw" in response
    ):
        usage_response = response.get("raw")
        parsed_response = response.get("parsed")
        if response.get("parsing_error") is not None:
            parsed_response = None
    request_id = _extract_request_id(usage_response)
    input_tokens, output_tokens, total_tokens = _extract_token_usage(
        usage_response
    )
    estimated_cost = None
    if input_tokens is not None and output_tokens is not None:
        if (
            input_cost_per_million is not None
            and output_cost_per_million is not None
        ):
            estimated_cost = (
                input_tokens * input_cost_per_million
                + output_tokens * output_cost_per_million
            ) / 1_000_000
    raw = parsed_response
    if effective_mode == "TOOL_CALL":
        tool_calls = getattr(response, "tool_calls", None)
        if (
            isinstance(tool_calls, list)
            and len(tool_calls) == 1
            and isinstance(tool_calls[0], dict)
            and isinstance(tool_calls[0].get("args"), dict)
        ):
            raw = tool_calls[0]["args"]
        else:
            raw = None
    if effective_mode != "TOOL_CALL" and hasattr(
        parsed_response, "content"
    ) and not isinstance(
        parsed_response, (dict, BaseModel)
    ):
        raw = parsed_response.content

    if raw is None or (isinstance(raw, str) and not raw.strip()):
        error_type = "EMPTY_RESPONSE"
        error_message = "model returned an empty response"
        meta = _finish_meta(
            provider=provider,
            model_name=name,
            model_version=name,
            prompt_name=prompt_name,
            prompt_version=prompt_version,
            started_at=started_at,
            started_perf=started_perf,
            execution_status="MODEL_FAILED",
            request_id=request_id,
            error_type=error_type,
            error_message=error_message,
            trace_id=trace_id,
            template_hash=template_hash,
            context_hash=context_hash,
            input_hash=input_hash,
            attempt_number=attempt_number,
            model_profile_id=model_profile_id,
            model_profile_version=model_profile_version,
            prompt_id=prompt_id,
            structured_output_mode=effective_mode,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            estimated_cost=estimated_cost,
            cost_currency=cost_currency,
        )
        return StructuredInvocation(
            payload=None,
            model_meta=meta,
            failure_status="MODEL_FAILED",
            error_type=error_type,
            error_message=error_message,
        )

    raw_text = _serialise_raw(raw)
    try:
        if isinstance(raw, BaseModel):
            payload = raw.model_dump(mode="json")
        elif isinstance(raw, dict):
            payload = raw
        elif isinstance(raw, str):
            payload = json.loads(raw.strip())
        else:
            raise TypeError(f"unsupported response type: {type(raw).__name__}")
        if not isinstance(payload, dict):
            raise TypeError("structured response must be a JSON object")
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        error_type = (
            "MALFORMED_JSON"
            if isinstance(exc, json.JSONDecodeError)
            else "INVALID_RESPONSE_TYPE"
        )
        error_message = _sanitise_error(exc)
        meta = _finish_meta(
            provider=provider,
            model_name=name,
            model_version=name,
            prompt_name=prompt_name,
            prompt_version=prompt_version,
            started_at=started_at,
            started_perf=started_perf,
            execution_status="INVALID_OUTPUT",
            request_id=request_id,
            error_type=error_type,
            error_message=error_message,
            raw_text=raw_text,
            trace_id=trace_id,
            template_hash=template_hash,
            context_hash=context_hash,
            input_hash=input_hash,
            attempt_number=attempt_number,
            model_profile_id=model_profile_id,
            model_profile_version=model_profile_version,
            prompt_id=prompt_id,
            structured_output_mode=effective_mode,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            estimated_cost=estimated_cost,
            cost_currency=cost_currency,
        )
        return StructuredInvocation(
            payload=None,
            model_meta=meta,
            failure_status="INVALID_OUTPUT",
            error_type=error_type,
            error_message=error_message,
        )

    meta = _finish_meta(
        provider=provider,
        model_name=name,
        model_version=name,
        prompt_name=prompt_name,
        prompt_version=prompt_version,
        started_at=started_at,
        started_perf=started_perf,
        execution_status="SUCCESS",
        request_id=request_id,
        raw_text=raw_text,
        trace_id=trace_id,
        template_hash=template_hash,
        context_hash=context_hash,
        input_hash=input_hash,
        attempt_number=attempt_number,
        model_profile_id=model_profile_id,
        model_profile_version=model_profile_version,
        prompt_id=prompt_id,
        structured_output_mode=effective_mode,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        estimated_cost=estimated_cost,
        cost_currency=cost_currency,
    )
    return StructuredInvocation(payload=payload, model_meta=meta)


def invoke_json_object(
    *,
    llm: Any,
    messages: Any,
    schema_model: Type[BaseModel],
    provider: str,
    configured_model_name: str | None,
    prompt_name: str,
    prompt_version: str,
    trace_id: str | None = None,
    template_hash: str | None = None,
    context_hash: str | None = None,
    input_hash: str | None = None,
    attempt_number: int = 1,
    structured_output_mode: str = "AUTO",
    model_profile_id: str | None = None,
    model_profile_version: str | None = None,
    prompt_id: str | None = None,
    input_cost_per_million: float | None = None,
    output_cost_per_million: float | None = None,
    cost_currency: str = "USD",
    max_retries: int = 0,
    retry_backoff_seconds: float = 0,
) -> StructuredInvocation:
    """Invoke with explicit, auditable retries for transient failures only.

    Authentication, missing-model, structured-output, and parsing failures are
    never retried. Provider SDK retries are disabled by ModelProviderRuntime so
    every network attempt is represented by one ModelExecutionMeta.
    """

    if max_retries < 0:
        raise ValueError("max_retries must be non-negative")
    if retry_backoff_seconds < 0:
        raise ValueError("retry_backoff_seconds must be non-negative")

    attempts: list[ModelExecutionMeta] = []
    retryable = {"TIMEOUT", "MODEL_TIMEOUT", "RATE_LIMITED", "PROVIDER_ERROR"}
    for retry_index in range(max_retries + 1):
        result = _invoke_json_object_once(
            llm=llm,
            messages=messages,
            schema_model=schema_model,
            provider=provider,
            configured_model_name=configured_model_name,
            prompt_name=prompt_name,
            prompt_version=prompt_version,
            trace_id=trace_id,
            template_hash=template_hash,
            context_hash=context_hash,
            input_hash=input_hash,
            attempt_number=attempt_number + retry_index,
            structured_output_mode=structured_output_mode,
            model_profile_id=model_profile_id,
            model_profile_version=model_profile_version,
            prompt_id=prompt_id,
            input_cost_per_million=input_cost_per_million,
            output_cost_per_million=output_cost_per_million,
            cost_currency=cost_currency,
        )
        attempts.append(result.model_meta)
        if (
            result.failure_status is None
            or result.error_type not in retryable
            or retry_index >= max_retries
        ):
            return replace(result, attempt_metas=tuple(attempts))
        delay = retry_backoff_seconds * (2**retry_index)
        if delay:
            time.sleep(delay)

    raise AssertionError("structured invocation retry loop did not return")
