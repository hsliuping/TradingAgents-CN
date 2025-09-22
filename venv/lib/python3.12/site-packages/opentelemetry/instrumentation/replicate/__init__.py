"""OpenTelemetry Replicate instrumentation"""

import logging
import os
import types
from typing import Collection
from opentelemetry.instrumentation.replicate.config import Config
from opentelemetry.instrumentation.replicate.utils import dont_throw
from wrapt import wrap_function_wrapper

from opentelemetry import context as context_api
from opentelemetry.trace import get_tracer, SpanKind
from opentelemetry.trace.status import Status, StatusCode

from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from opentelemetry.instrumentation.utils import (
    _SUPPRESS_INSTRUMENTATION_KEY,
    unwrap,
)

from opentelemetry.semconv_ai import SpanAttributes, LLMRequestTypeValues
from opentelemetry.instrumentation.replicate.version import __version__

logger = logging.getLogger(__name__)

_instruments = ("replicate >= 0.22.0",)

WRAPPED_METHODS = [
    {
        "module": "replicate",
        "method": "run",
        "span_name": "replicate.run",
    },
    {
        "module": "replicate",
        "method": "stream",
        "span_name": "replicate.stream",
    },
    {
        "module": "replicate",
        "method": "predictions.create",
        "span_name": "replicate.predictions.create",
    },
]


def should_send_prompts():
    return (
        os.getenv("TRACELOOP_TRACE_CONTENT") or "true"
    ).lower() == "true" or context_api.get_value("override_enable_content_tracing")


def is_streaming_response(response):
    return isinstance(response, types.GeneratorType)


def _set_span_attribute(span, name, value):
    if value is not None:
        if value != "":
            span.set_attribute(name, value)
    return


input_attribute_map = {
    "prompt": f"{SpanAttributes.LLM_PROMPTS}.0.user",
    "temperature": SpanAttributes.LLM_REQUEST_TEMPERATURE,
    "top_p": SpanAttributes.LLM_REQUEST_TOP_P,
}


def _set_input_attributes(span, args, kwargs):
    if args is not None and len(args) > 0:
        _set_span_attribute(span, SpanAttributes.LLM_REQUEST_MODEL, args[0])
    elif kwargs.get("version"):
        _set_span_attribute(
            span, SpanAttributes.LLM_REQUEST_MODEL, kwargs.get("version").id
        )
    else:
        _set_span_attribute(span, SpanAttributes.LLM_REQUEST_MODEL, "unknown")

    input_attribute = kwargs.get("input")
    for key in input_attribute:
        if key in input_attribute_map:
            if key == "prompt" and not should_send_prompts():
                continue
            _set_span_attribute(
                span,
                input_attribute_map.get(key, f"llm.request.{key}"),
                input_attribute.get(key),
            )
    return


@dont_throw
def _set_response_attributes(span, response):
    if should_send_prompts():
        if isinstance(response, list):
            for index, item in enumerate(response):
                prefix = f"{SpanAttributes.LLM_COMPLETIONS}.{index}"
                _set_span_attribute(span, f"{prefix}.content", item)
        elif isinstance(response, str):
            _set_span_attribute(
                span, f"{SpanAttributes.LLM_COMPLETIONS}.0.content", response
            )
    return


def _build_from_streaming_response(span, response):
    complete_response = ""
    for item in response:
        item_to_yield = item
        complete_response += str(item)

        yield item_to_yield

    _set_response_attributes(span, complete_response)

    span.set_status(Status(StatusCode.OK))
    span.end()


@dont_throw
def _handle_request(span, args, kwargs):
    if span.is_recording():
        _set_input_attributes(span, args, kwargs)


@dont_throw
def _handle_response(span, response):
    if span.is_recording():
        _set_response_attributes(span, response)

        span.set_status(Status(StatusCode.OK))


def _with_tracer_wrapper(func):
    """Helper for providing tracer for wrapper functions."""

    def _with_tracer(tracer, to_wrap):
        def wrapper(wrapped, instance, args, kwargs):
            return func(tracer, to_wrap, wrapped, instance, args, kwargs)

        return wrapper

    return _with_tracer


@_with_tracer_wrapper
def _wrap(tracer, to_wrap, wrapped, instance, args, kwargs):
    """Instruments and calls every function defined in TO_WRAP."""
    if context_api.get_value(_SUPPRESS_INSTRUMENTATION_KEY):
        return wrapped(*args, **kwargs)

    name = to_wrap.get("span_name")
    span = tracer.start_span(
        name,
        kind=SpanKind.CLIENT,
        attributes={
            SpanAttributes.LLM_SYSTEM: "Replicate",
            SpanAttributes.LLM_REQUEST_TYPE: LLMRequestTypeValues.COMPLETION.value,
        },
    )

    _handle_request(span, args, kwargs)

    response = wrapped(*args, **kwargs)

    if response:
        if is_streaming_response(response):
            return _build_from_streaming_response(span, response)
        else:
            _handle_response(span, response)

    span.end()
    return response


class ReplicateInstrumentor(BaseInstrumentor):
    """An instrumentor for Replicate's client library."""

    def __init__(self, exception_logger=None):
        super().__init__()
        Config.exception_logger = exception_logger

    def instrumentation_dependencies(self) -> Collection[str]:
        return _instruments

    def _instrument(self, **kwargs):
        tracer_provider = kwargs.get("tracer_provider")
        tracer = get_tracer(__name__, __version__, tracer_provider)
        for wrapper_method in WRAPPED_METHODS:
            wrap_function_wrapper(
                wrapper_method.get("module"),
                wrapper_method.get("method"),
                _wrap(tracer, wrapper_method),
            )

    def _uninstrument(self, **kwargs):
        for wrapper_method in WRAPPED_METHODS:
            unwrap(wrapper_method.get("module"), wrapper_method.get("method", ""))
