"""OpenTelemetry Ollama instrumentation"""

import logging
import os
import json
import time
from typing import Collection
from opentelemetry.instrumentation.ollama.config import Config
from opentelemetry.instrumentation.ollama.utils import dont_throw
from wrapt import wrap_function_wrapper

from opentelemetry import context as context_api
from opentelemetry.trace import get_tracer, SpanKind, Tracer
from opentelemetry.trace.status import Status, StatusCode
from opentelemetry.metrics import Histogram, Meter, get_meter
from opentelemetry.semconv._incubating.metrics import gen_ai_metrics as GenAIMetrics

from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from opentelemetry.instrumentation.utils import (
    _SUPPRESS_INSTRUMENTATION_KEY,
    unwrap,
)

from opentelemetry.semconv_ai import (
    SUPPRESS_LANGUAGE_MODEL_INSTRUMENTATION_KEY,
    SpanAttributes,
    LLMRequestTypeValues,
    Meters
)
from opentelemetry.instrumentation.ollama.version import __version__

logger = logging.getLogger(__name__)

_instruments = ("ollama >= 0.4.0, < 1",)

WRAPPED_METHODS = [
    {
        "method": "generate",
        "span_name": "ollama.completion",
    },
    {
        "method": "chat",
        "span_name": "ollama.chat",
    },
    {
        "method": "embeddings",
        "span_name": "ollama.embeddings",
    },
]


def _sanitize_copy_messages(wrapped, instance, args, kwargs):
    # original signature: _copy_messages(messages)
    messages = args[0] if args else []
    sanitized = []
    for msg in messages or []:
        if isinstance(msg, dict):
            msg_copy = dict(msg)
            tc_list = msg_copy.get("tool_calls")
            if tc_list:
                for tc in tc_list:
                    func = tc.get("function")
                    arg = func.get("arguments") if func else None
                    if isinstance(arg, str):
                        try:
                            func["arguments"] = json.loads(arg)
                        except Exception:
                            pass
            sanitized.append(msg_copy)
        else:
            sanitized.append(msg)
    return wrapped(sanitized)


def should_send_prompts():
    return (
        os.getenv("TRACELOOP_TRACE_CONTENT") or "true"
    ).lower() == "true" or context_api.get_value("override_enable_content_tracing")


def _set_span_attribute(span, name, value):
    if value is not None:
        if value != "":
            span.set_attribute(name, value)
    return


def _set_prompts(span, messages):
    if not span.is_recording() or messages is None:
        return
    for i, msg in enumerate(messages):
        prefix = f"{SpanAttributes.LLM_PROMPTS}.{i}"

        _set_span_attribute(span, f"{prefix}.role", msg.get("role"))
        if msg.get("content"):
            content = msg.get("content")
            if isinstance(content, list):
                content = json.dumps(content)
            _set_span_attribute(span, f"{prefix}.content", content)
        if msg.get("tool_call_id"):
            _set_span_attribute(span, f"{prefix}.tool_call_id", msg.get("tool_call_id"))
        tool_calls = msg.get("tool_calls")
        if tool_calls:
            for i, tool_call in enumerate(tool_calls):
                function = tool_call.get("function")
                _set_span_attribute(
                    span,
                    f"{prefix}.tool_calls.{i}.id",
                    tool_call.get("id"),
                )
                _set_span_attribute(
                    span,
                    f"{prefix}.tool_calls.{i}.name",
                    function.get("name"),
                )
                # record arguments: ensure it's a JSON string for span attributes
                raw_args = function.get("arguments")
                if isinstance(raw_args, dict):
                    arg_str = json.dumps(raw_args)
                else:
                    arg_str = raw_args
                _set_span_attribute(
                    span,
                    f"{prefix}.tool_calls.{i}.arguments",
                    arg_str,
                )


def set_tools_attributes(span, tools):
    if not tools:
        return

    for i, tool in enumerate(tools):
        function = tool.get("function")
        if not function:
            continue

        prefix = f"{SpanAttributes.LLM_REQUEST_FUNCTIONS}.{i}"
        _set_span_attribute(span, f"{prefix}.name", function.get("name"))
        _set_span_attribute(span, f"{prefix}.description", function.get("description"))
        _set_span_attribute(
            span, f"{prefix}.parameters", json.dumps(function.get("parameters"))
        )


@dont_throw
def _set_input_attributes(span, llm_request_type, kwargs):
    json_data = kwargs.get("json", {})
    _set_span_attribute(span, SpanAttributes.LLM_REQUEST_MODEL, json_data.get("model"))
    _set_span_attribute(
        span, SpanAttributes.LLM_IS_STREAMING, kwargs.get("stream") or False
    )
    if should_send_prompts():
        if llm_request_type == LLMRequestTypeValues.CHAT:
            _set_span_attribute(span, f"{SpanAttributes.LLM_PROMPTS}.0.role", "user")
            for index, message in enumerate(json_data.get("messages")):
                _set_span_attribute(
                    span,
                    f"{SpanAttributes.LLM_PROMPTS}.{index}.content",
                    message.get("content"),
                )
                _set_span_attribute(
                    span,
                    f"{SpanAttributes.LLM_PROMPTS}.{index}.role",
                    message.get("role"),
                )
            _set_prompts(span, json_data.get("messages"))
            if json_data.get("tools"):
                set_tools_attributes(span, json_data.get("tools"))
        else:
            _set_span_attribute(span, f"{SpanAttributes.LLM_PROMPTS}.0.role", "user")
            _set_span_attribute(
                span, f"{SpanAttributes.LLM_PROMPTS}.0.content", json_data.get("prompt")
            )


@dont_throw
def _set_response_attributes(span, token_histogram, llm_request_type, response):
    if should_send_prompts():
        if llm_request_type == LLMRequestTypeValues.COMPLETION:
            _set_span_attribute(
                span,
                f"{SpanAttributes.LLM_COMPLETIONS}.0.content",
                response.get("response"),
            )
            _set_span_attribute(
                span, f"{SpanAttributes.LLM_COMPLETIONS}.0.role", "assistant"
            )
        elif llm_request_type == LLMRequestTypeValues.CHAT:
            index = 0
            prefix = f"{SpanAttributes.LLM_COMPLETIONS}.{index}"
            _set_span_attribute(
                span, f"{prefix}.content", response.get("message").get("content")
            )
            _set_span_attribute(
                span, f"{prefix}.role", response.get("message").get("role")
            )

    if llm_request_type == LLMRequestTypeValues.EMBEDDING:
        return

    _set_span_attribute(span, SpanAttributes.LLM_RESPONSE_MODEL, response.get("model"))

    input_tokens = response.get("prompt_eval_count") or 0
    output_tokens = response.get("eval_count") or 0

    _set_span_attribute(
        span,
        SpanAttributes.LLM_USAGE_TOTAL_TOKENS,
        input_tokens + output_tokens,
    )
    _set_span_attribute(
        span,
        SpanAttributes.LLM_USAGE_COMPLETION_TOKENS,
        output_tokens,
    )
    _set_span_attribute(
        span,
        SpanAttributes.LLM_USAGE_PROMPT_TOKENS,
        input_tokens,
    )
    _set_span_attribute(
        span,
        SpanAttributes.LLM_SYSTEM,
        "Ollama"
    )

    if (
        token_histogram is not None
        and isinstance(input_tokens, int)
        and input_tokens >= 0
    ):
        token_histogram.record(
            input_tokens,
            attributes={
                SpanAttributes.LLM_SYSTEM: "Ollama",
                SpanAttributes.LLM_TOKEN_TYPE: "input",
                SpanAttributes.LLM_RESPONSE_MODEL: response.get("model"),
            },
        )

    if (
        token_histogram is not None
        and isinstance(output_tokens, int)
        and output_tokens >= 0
    ):
        token_histogram.record(
            output_tokens,
            attributes={
                SpanAttributes.LLM_SYSTEM: "Ollama",
                SpanAttributes.LLM_TOKEN_TYPE: "output",
                SpanAttributes.LLM_RESPONSE_MODEL: response.get("model"),
            },
        )


def _accumulate_streaming_response(
    span,
    token_histogram,
    llm_request_type,
    response,
    streaming_time_to_first_token=None,
    start_time=None
):
    if llm_request_type == LLMRequestTypeValues.CHAT:
        accumulated_response = {"message": {"content": "", "role": ""}}
    elif llm_request_type == LLMRequestTypeValues.COMPLETION:
        accumulated_response = {"response": ""}

    first_token = True
    for res in response:
        if first_token and streaming_time_to_first_token and start_time is not None:
            streaming_time_to_first_token.record(
                time.perf_counter() - start_time,
                attributes={SpanAttributes.LLM_SYSTEM: "Ollama"},
            )
            first_token = False
        yield res

        if llm_request_type == LLMRequestTypeValues.CHAT:
            accumulated_response["message"]["content"] += res["message"]["content"]
            accumulated_response["message"]["role"] = res["message"]["role"]
        elif llm_request_type == LLMRequestTypeValues.COMPLETION:
            text = res.get("response", "")
            accumulated_response["response"] += text

    response_data = res.model_dump() if hasattr(res, 'model_dump') else res
    _set_response_attributes(span, token_histogram, llm_request_type, response_data | accumulated_response)
    span.end()


async def _aaccumulate_streaming_response(
    span,
    token_histogram,
    llm_request_type,
    response,
    streaming_time_to_first_token=None,
    start_time=None,
):
    if llm_request_type == LLMRequestTypeValues.CHAT:
        accumulated_response = {"message": {"content": "", "role": ""}}
    elif llm_request_type == LLMRequestTypeValues.COMPLETION:
        accumulated_response = {"response": ""}

    first_token = True

    async for res in response:
        if first_token and streaming_time_to_first_token and start_time is not None:
            streaming_time_to_first_token.record(
                time.perf_counter() - start_time,
                attributes={SpanAttributes.LLM_SYSTEM: "Ollama"},
            )
            first_token = False
        yield res

        if llm_request_type == LLMRequestTypeValues.CHAT:
            accumulated_response["message"]["content"] += res["message"]["content"]
            accumulated_response["message"]["role"] = res["message"]["role"]
        elif llm_request_type == LLMRequestTypeValues.COMPLETION:
            text = res.get("response", "")
            accumulated_response["response"] += text

    response_data = res.model_dump() if hasattr(res, 'model_dump') else res
    _set_response_attributes(span, token_histogram, llm_request_type, response_data | accumulated_response)
    span.end()


def _with_tracer_wrapper(func):
    """Helper for providing tracer for wrapper functions."""

    def _with_tracer(tracer, token_histogram, duration_histogram, streaming_time_to_first_token, to_wrap):
        def wrapper(wrapped, instance, args, kwargs):
            return func(
                tracer,
                token_histogram,
                duration_histogram,
                streaming_time_to_first_token,
                to_wrap,
                wrapped,
                instance,
                args,
                kwargs,
            )

        return wrapper

    return _with_tracer


def _llm_request_type_by_method(method_name):
    if method_name == "chat":
        return LLMRequestTypeValues.CHAT
    elif method_name == "generate":
        return LLMRequestTypeValues.COMPLETION
    elif method_name == "embeddings":
        return LLMRequestTypeValues.EMBEDDING
    else:
        return LLMRequestTypeValues.UNKNOWN


@_with_tracer_wrapper
def _wrap(
    tracer: Tracer,
    token_histogram: Histogram,
    duration_histogram: Histogram,
    streaming_time_to_first_token: Histogram,
    to_wrap,
    wrapped,
    instance,
    args,
    kwargs,
):
    """Instruments and calls every function defined in TO_WRAP."""
    if context_api.get_value(_SUPPRESS_INSTRUMENTATION_KEY) or context_api.get_value(
        SUPPRESS_LANGUAGE_MODEL_INSTRUMENTATION_KEY
    ):
        return wrapped(*args, **kwargs)

    name = to_wrap.get("span_name")
    llm_request_type = _llm_request_type_by_method(to_wrap.get("method"))
    span = tracer.start_span(
        name,
        kind=SpanKind.CLIENT,
        attributes={
            SpanAttributes.LLM_SYSTEM: "Ollama",
            SpanAttributes.LLM_REQUEST_TYPE: llm_request_type.value,
        },
    )
    if span.is_recording():
        _set_input_attributes(span, llm_request_type, kwargs)

    start_time = time.perf_counter()
    response = wrapped(*args, **kwargs)
    end_time = time.perf_counter()

    if response:
        if duration_histogram:
            duration = end_time - start_time
            attrs = {SpanAttributes.LLM_SYSTEM: "Ollama"}
            model = kwargs.get("model")
            if model is not None:
                attrs[SpanAttributes.LLM_RESPONSE_MODEL] = model
            duration_histogram.record(duration, attributes=attrs)

        if span.is_recording():
            if kwargs.get("stream"):
                return _accumulate_streaming_response(
                    span,
                    token_histogram,
                    llm_request_type,
                    response,
                    streaming_time_to_first_token,
                    start_time,
                )

            _set_response_attributes(span, token_histogram, llm_request_type, response)
            span.set_status(Status(StatusCode.OK))

    span.end()
    return response


@_with_tracer_wrapper
async def _awrap(
    tracer: Tracer,
    token_histogram: Histogram,
    duration_histogram: Histogram,
    streaming_time_to_first_token: Histogram,
    to_wrap,
    wrapped,
    instance,
    args,
    kwargs,
):
    """Instruments and calls every function defined in TO_WRAP."""
    if context_api.get_value(_SUPPRESS_INSTRUMENTATION_KEY) or context_api.get_value(
        SUPPRESS_LANGUAGE_MODEL_INSTRUMENTATION_KEY
    ):
        return await wrapped(*args, **kwargs)

    name = to_wrap.get("span_name")
    llm_request_type = _llm_request_type_by_method(to_wrap.get("method"))
    span = tracer.start_span(
        name,
        kind=SpanKind.CLIENT,
        attributes={
            SpanAttributes.LLM_SYSTEM: "Ollama",
            SpanAttributes.LLM_REQUEST_TYPE: llm_request_type.value,
        },
    )

    if span.is_recording():
        _set_input_attributes(span, llm_request_type, kwargs)

    start_time = time.perf_counter()
    response = await wrapped(*args, **kwargs)
    end_time = time.perf_counter()
    if response:
        if duration_histogram:
            duration = end_time - start_time
            attrs = {SpanAttributes.LLM_SYSTEM: "Ollama"}
            model = kwargs.get("model")
            if model is not None:
                attrs[SpanAttributes.LLM_RESPONSE_MODEL] = model
            duration_histogram.record(duration, attributes=attrs)

        if span.is_recording():
            if kwargs.get("stream"):
                return _aaccumulate_streaming_response(
                    span,
                    token_histogram,
                    llm_request_type,
                    response,
                    streaming_time_to_first_token,
                    start_time,
                )

            _set_response_attributes(span, token_histogram, llm_request_type, response)
            span.set_status(Status(StatusCode.OK))

    span.end()
    return response


def _build_metrics(meter: Meter):
    token_histogram = meter.create_histogram(
        name=Meters.LLM_TOKEN_USAGE,
        unit="token",
        description="Measures number of input and output tokens used",
    )

    duration_histogram = meter.create_histogram(
        name=Meters.LLM_OPERATION_DURATION,
        unit="s",
        description="GenAI operation duration",
    )

    streaming_time_to_first_token = meter.create_histogram(
        name=GenAIMetrics.GEN_AI_SERVER_TIME_TO_FIRST_TOKEN,
        unit="s",
        description="Time to first token in streaming chat completions",
    )

    return token_histogram, duration_histogram, streaming_time_to_first_token


def is_metrics_collection_enabled() -> bool:
    return (os.getenv("TRACELOOP_METRICS_ENABLED") or "true").lower() == "true"


class OllamaInstrumentor(BaseInstrumentor):
    """An instrumentor for Ollama's client library."""

    def __init__(self, exception_logger=None):
        super().__init__()
        Config.exception_logger = exception_logger

    def instrumentation_dependencies(self) -> Collection[str]:
        return _instruments

    def _instrument(self, **kwargs):
        tracer_provider = kwargs.get("tracer_provider")
        tracer = get_tracer(__name__, __version__, tracer_provider)

        meter_provider = kwargs.get("meter_provider")
        meter = get_meter(__name__, __version__, meter_provider)

        if is_metrics_collection_enabled():
            (
                token_histogram,
                duration_histogram,
                streaming_time_to_first_token,
            ) = _build_metrics(meter)
        else:
            (
                token_histogram,
                duration_histogram,
                streaming_time_to_first_token,
            ) = (None, None, None)

        # Patch _copy_messages to sanitize tool_calls arguments before Pydantic validation
        wrap_function_wrapper(
            "ollama._client",
            "_copy_messages",
            _sanitize_copy_messages,
        )
        # instrument all llm methods (generate/chat/embeddings) via _request dispatch wrapper
        wrap_function_wrapper(
            "ollama._client",
            "Client._request",
            _dispatch_wrap(tracer, token_histogram, duration_histogram, streaming_time_to_first_token),
        )
        wrap_function_wrapper(
            "ollama._client",
            "AsyncClient._request",
            _dispatch_awrap(tracer, token_histogram, duration_histogram, streaming_time_to_first_token),
        )

    def _uninstrument(self, **kwargs):
        for wrapped_method in WRAPPED_METHODS:
            unwrap(
                "ollama._client.Client",
                wrapped_method.get("method"),
            )
            unwrap(
                "ollama._client.AsyncClient",
                wrapped_method.get("method"),
            )
            unwrap(
                "ollama",
                wrapped_method.get("method"),
            )


def _dispatch_wrap(tracer, token_histogram, duration_histogram, streaming_time_to_first_token):
    def wrapper(wrapped, instance, args, kwargs):
        to_wrap = None
        if len(args) > 2 and isinstance(args[2], str):
            path = args[2]
            op = path.rstrip('/').split('/')[-1]
            to_wrap = next((m for m in WRAPPED_METHODS if m.get("method") == op), None)
        if to_wrap:
            return _wrap(tracer, token_histogram, duration_histogram, streaming_time_to_first_token, to_wrap)(
                wrapped, instance, args, kwargs
            )
        return wrapped(*args, **kwargs)
    return wrapper


def _dispatch_awrap(tracer, token_histogram, duration_histogram, streaming_time_to_first_token):
    async def wrapper(wrapped, instance, args, kwargs):
        to_wrap = None
        if len(args) > 2 and isinstance(args[2], str):
            path = args[2]
            op = path.rstrip('/').split('/')[-1]
            to_wrap = next((m for m in WRAPPED_METHODS if m.get("method") == op), None)
        if to_wrap:
            return await _awrap(tracer, token_histogram, duration_histogram, streaming_time_to_first_token, to_wrap)(
                wrapped, instance, args, kwargs
            )
        return await wrapped(*args, **kwargs)
    return wrapper
