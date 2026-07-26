"""One-call structured-output adapter with auditable, fail-closed errors."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
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


def _serialise_raw(raw: Any) -> str:
    if isinstance(raw, BaseModel):
        raw = raw.model_dump(mode="json")
    if isinstance(raw, dict):
        return json.dumps(raw, ensure_ascii=False, sort_keys=True, default=str)
    return str(raw)


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
        error_type=error_type,
        error_message=error_message,
        raw_output_hash=(
            hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
            if raw_text
            else None
        ),
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
        error_type=error_type,
        error_message=_sanitise_error(error_message),
    )


def invoke_json_object(
    *,
    llm: Any,
    messages: Any,
    schema_model: Type[BaseModel],
    provider: str,
    configured_model_name: str | None,
    prompt_name: str,
    prompt_version: str,
) -> StructuredInvocation:
    """Invoke the model once and return one strict JSON object.

    Native structured output is preferred. If the adapter cannot even construct
    such a runnable, the same model is invoked once with a strict-JSON prompt.
    A failed model invocation is never retried as a parsing call.
    """

    started_at = datetime.now(timezone.utc)
    started_perf = time.perf_counter()
    name = _model_name(llm, configured_model_name)
    schema = _json_schema_without_execution_meta(schema_model)
    runnable = None

    with_structured_output = getattr(llm, "with_structured_output", None)
    if callable(with_structured_output):
        try:
            runnable = with_structured_output(schema)
        except (AttributeError, NotImplementedError, TypeError, ValueError):
            runnable = None

    try:
        response = (runnable or llm).invoke(messages)
    except Exception as exc:
        error_type = (
            "MODEL_TIMEOUT"
            if isinstance(exc, TimeoutError)
            or "timeout" in exc.__class__.__name__.lower()
            else "PROVIDER_ERROR"
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
            execution_status="MODEL_FAILED",
            error_type=error_type,
            error_message=error_message,
        )
        return StructuredInvocation(
            payload=None,
            model_meta=meta,
            failure_status="MODEL_FAILED",
            error_type=error_type,
            error_message=error_message,
        )

    request_id = _extract_request_id(response)
    raw = response
    if hasattr(response, "content") and not isinstance(response, (dict, BaseModel)):
        raw = response.content

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
    )
    return StructuredInvocation(payload=payload, model_meta=meta)
