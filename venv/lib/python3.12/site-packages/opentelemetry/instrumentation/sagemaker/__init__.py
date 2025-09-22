"""OpenTelemetry SageMaker instrumentation"""

from functools import wraps
import json
import logging
import os
from typing import Collection
from opentelemetry.instrumentation.sagemaker.config import Config
from opentelemetry.instrumentation.sagemaker.reusable_streaming_body import (
    ReusableStreamingBody,
)
from opentelemetry.instrumentation.sagemaker.streaming_wrapper import StreamingWrapper
from opentelemetry.instrumentation.sagemaker.utils import dont_throw
from wrapt import wrap_function_wrapper

from opentelemetry import context as context_api
from opentelemetry.trace import get_tracer, SpanKind

from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from opentelemetry.instrumentation.utils import (
    _SUPPRESS_INSTRUMENTATION_KEY,
    unwrap,
)

from opentelemetry.semconv_ai import (
    SUPPRESS_LANGUAGE_MODEL_INSTRUMENTATION_KEY,
    SpanAttributes,
)
from opentelemetry.instrumentation.sagemaker.version import __version__

logger = logging.getLogger(__name__)

_instruments = ("boto3 >= 1.28.57",)

WRAPPED_METHODS = [
    {
        "package": "botocore.client",
        "object": "ClientCreator",
        "method": "create_client",
    },
    {"package": "botocore.session", "object": "Session", "method": "create_client"},
]


def should_send_prompts():
    return (
        os.getenv("TRACELOOP_TRACE_CONTENT") or "true"
    ).lower() == "true" or context_api.get_value("override_enable_content_tracing")


def _set_span_attribute(span, name, value):
    if value is not None:
        if value != "":
            span.set_attribute(name, value)
    return


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

    if kwargs.get("service_name") == "sagemaker-runtime":
        client = wrapped(*args, **kwargs)
        client.invoke_endpoint = _instrumented_endpoint_invoke(
            client.invoke_endpoint, tracer
        )
        client.invoke_endpoint_with_response_stream = (
            _instrumented_endpoint_invoke_with_response_stream(
                client.invoke_endpoint_with_response_stream, tracer
            )
        )

        return client

    return wrapped(*args, **kwargs)


def _instrumented_endpoint_invoke(fn, tracer):
    @wraps(fn)
    def with_instrumentation(*args, **kwargs):
        if context_api.get_value(SUPPRESS_LANGUAGE_MODEL_INSTRUMENTATION_KEY):
            return fn(*args, **kwargs)

        with tracer.start_as_current_span(
            "sagemaker.completion", kind=SpanKind.CLIENT
        ) as span:
            response = fn(*args, **kwargs)

            if span.is_recording():
                _handle_call(span, kwargs, response)

            return response

    return with_instrumentation


def _instrumented_endpoint_invoke_with_response_stream(fn, tracer):
    @wraps(fn)
    def with_instrumentation(*args, **kwargs):
        if context_api.get_value(SUPPRESS_LANGUAGE_MODEL_INSTRUMENTATION_KEY):
            return fn(*args, **kwargs)

        span = tracer.start_span("sagemaker.completion", kind=SpanKind.CLIENT)
        response = fn(*args, **kwargs)

        if span.is_recording():
            _handle_stream_call(span, kwargs, response)

        return response

    return with_instrumentation


def _handle_stream_call(span, kwargs, response):
    @dont_throw
    def stream_done(response_body):
        request_body = json.loads(kwargs.get("Body"))

        endpoint_name = kwargs.get("EndpointName")

        _set_span_attribute(span, SpanAttributes.LLM_REQUEST_MODEL, endpoint_name)
        _set_span_attribute(
            span, SpanAttributes.TRACELOOP_ENTITY_INPUT, json.dumps(request_body)
        )
        _set_span_attribute(
            span, SpanAttributes.TRACELOOP_ENTITY_OUTPUT, json.dumps(response_body)
        )

        span.end()

    response["Body"] = StreamingWrapper(response["Body"], stream_done)


def _try_parse_json(value):
    """Try to decode JSON if it's a string or bytes; fallback to raw value."""
    try:
        if isinstance(value, bytes):
            value = value.decode("utf-8").strip()
        if isinstance(value, str):
            return json.loads(value)
        return value
    except (json.JSONDecodeError, UnicodeDecodeError):
        return str(value)


@dont_throw
def _handle_call(span, kwargs, response):
    response["Body"] = ReusableStreamingBody(
        response["Body"]._raw_stream, response["Body"]._content_length
    )

    raw_request = kwargs.get("Body")
    raw_response = response["Body"].read()

    request_body = _try_parse_json(raw_request)
    response_body = _try_parse_json(raw_response)

    endpoint_name = kwargs.get("EndpointName")
    _set_span_attribute(span, SpanAttributes.LLM_REQUEST_MODEL, endpoint_name)
    _set_span_attribute(
        span, SpanAttributes.TRACELOOP_ENTITY_INPUT, json.dumps(request_body)
    )
    _set_span_attribute(
        span, SpanAttributes.TRACELOOP_ENTITY_OUTPUT, json.dumps(response_body)
    )


class SageMakerInstrumentor(BaseInstrumentor):
    """An instrumentor for Bedrock's client library."""

    def __init__(self, enrich_token_usage: bool = False, exception_logger=None):
        super().__init__()
        Config.enrich_token_usage = enrich_token_usage
        Config.exception_logger = exception_logger

    def instrumentation_dependencies(self) -> Collection[str]:
        return _instruments

    def _instrument(self, **kwargs):
        tracer_provider = kwargs.get("tracer_provider")
        tracer = get_tracer(__name__, __version__, tracer_provider)
        for wrapped_method in WRAPPED_METHODS:
            wrap_package = wrapped_method.get("package")
            wrap_object = wrapped_method.get("object")
            wrap_method = wrapped_method.get("method")
            wrap_function_wrapper(
                wrap_package,
                f"{wrap_object}.{wrap_method}",
                _wrap(tracer, wrapped_method),
            )

    def _uninstrument(self, **kwargs):
        for wrapped_method in WRAPPED_METHODS:
            wrap_package = wrapped_method.get("package")
            wrap_object = wrapped_method.get("object")
            unwrap(
                f"{wrap_package}.{wrap_object}",
                wrapped_method.get("method"),
            )
