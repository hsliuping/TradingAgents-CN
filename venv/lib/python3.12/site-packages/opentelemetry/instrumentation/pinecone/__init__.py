"""OpenTelemetry Pinecone instrumentation"""

import logging
import time
import pinecone
from typing import Collection
from wrapt import wrap_function_wrapper

from opentelemetry import context as context_api
from opentelemetry.metrics import get_meter
from opentelemetry.trace import get_tracer, SpanKind
from opentelemetry.trace.status import Status, StatusCode

from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from opentelemetry.instrumentation.utils import (
    _SUPPRESS_INSTRUMENTATION_KEY,
    unwrap,
)
from opentelemetry.instrumentation.pinecone.config import Config
from opentelemetry.instrumentation.pinecone.utils import (
    dont_throw,
    is_metrics_enabled,
    set_span_attribute,
)
from opentelemetry.instrumentation.pinecone.version import __version__
from opentelemetry.instrumentation.pinecone.query_handlers import (
    set_query_input_attributes,
    set_query_response,
)
from opentelemetry.semconv.trace import SpanAttributes
from opentelemetry.semconv_ai import Meters, SpanAttributes as AISpanAttributes

logger = logging.getLogger(__name__)

_instruments = ("pinecone-client >= 2.2.2, <6",)


WRAPPED_METHODS = [
    {
        "object": "GRPCIndex",
        "method": "query",
        "span_name": "pinecone.query",
    },
    {
        "object": "GRPCIndex",
        "method": "upsert",
        "span_name": "pinecone.upsert",
    },
    {
        "object": "GRPCIndex",
        "method": "delete",
        "span_name": "pinecone.delete",
    },
    {
        "object": "Index",
        "method": "query",
        "span_name": "pinecone.query",
    },
    {
        "object": "Index",
        "method": "upsert",
        "span_name": "pinecone.upsert",
    },
    {
        "object": "Index",
        "method": "delete",
        "span_name": "pinecone.delete",
    },
]


@dont_throw
def _set_input_attributes(span, instance, kwargs):
    set_span_attribute(span, SpanAttributes.SERVER_ADDRESS, instance._config.host)


@dont_throw
def _set_response_attributes(
    span, read_units_metric, write_units_metric, shared_attributes, response
):
    if response.get("usage"):
        read_units = response.get("usage").get("read_units") or 0
        write_units = response.get("usage").get("write_units") or 0

        read_units_metric.add(read_units, shared_attributes)
        span.set_attribute(AISpanAttributes.PINECONE_USAGE_READ_UNITS, read_units)

        write_units_metric.add(write_units, shared_attributes)
        span.set_attribute(AISpanAttributes.PINECONE_USAGE_WRITE_UNITS, write_units)


def _with_wrapper(func):
    """Helper for providing tracer for wrapper functions."""

    def _with_tracer(
        tracer,
        query_duration_metric,
        read_units_metric,
        write_units_metric,
        scores_metric,
        to_wrap,
    ):
        def wrapper(wrapped, instance, args, kwargs):
            return func(
                tracer,
                query_duration_metric,
                read_units_metric,
                write_units_metric,
                scores_metric,
                to_wrap,
                wrapped,
                instance,
                args,
                kwargs,
            )

        return wrapper

    return _with_tracer


@_with_wrapper
def _wrap(
    tracer,
    query_duration_metric,
    read_units_metric,
    write_units_metric,
    scores_metric,
    to_wrap,
    wrapped,
    instance,
    args,
    kwargs,
):
    """Instruments and calls every function defined in TO_WRAP."""
    if context_api.get_value(_SUPPRESS_INSTRUMENTATION_KEY):
        return wrapped(*args, **kwargs)

    name = to_wrap.get("span_name")
    with tracer.start_as_current_span(
        name,
        kind=SpanKind.CLIENT,
        attributes={
            AISpanAttributes.VECTOR_DB_VENDOR: "Pinecone",
        },
    ) as span:
        if span.is_recording():
            _set_input_attributes(span, instance, kwargs)
            if to_wrap.get("method") == "query":
                set_query_input_attributes(span, kwargs)

        shared_attributes = {}
        if hasattr(instance, "_config"):
            shared_attributes["server.address"] = instance._config.host

        start_time = time.time()
        response = wrapped(*args, **kwargs)
        end_time = time.time()

        duration = end_time - start_time
        if duration > 0 and query_duration_metric and to_wrap.get("method") == "query":
            query_duration_metric.record(duration, shared_attributes)

        if response:
            if span.is_recording():
                if to_wrap.get("method") == "query":
                    set_query_response(span, scores_metric, shared_attributes, response)

                _set_response_attributes(
                    span,
                    read_units_metric,
                    write_units_metric,
                    shared_attributes,
                    response,
                )

                span.set_status(Status(StatusCode.OK))

        return response


class PineconeInstrumentor(BaseInstrumentor):
    """An instrumentor for Pinecone's client library."""

    def __init__(self, exception_logger=None):
        super().__init__()
        Config.exception_logger = exception_logger

    def instrumentation_dependencies(self) -> Collection[str]:
        return _instruments

    def _instrument(self, **kwargs):
        if is_metrics_enabled():
            meter_provider = kwargs.get("meter_provider")
            meter = get_meter(__name__, __version__, meter_provider)

            query_duration_metric = meter.create_histogram(
                Meters.PINECONE_DB_QUERY_DURATION,
                "s",
                "Duration of query operations to Pinecone",
            )
            read_units_metric = meter.create_counter(
                Meters.PINECONE_DB_USAGE_READ_UNITS,
                "unit",
                "Number of read units consumed in serverless calls",
            )
            write_units_metric = meter.create_counter(
                Meters.PINECONE_DB_USAGE_WRITE_UNITS,
                "unit",
                "Number of write units consumed in serverless calls",
            )
            scores_metric = meter.create_histogram(
                Meters.PINECONE_DB_QUERY_SCORES,
                "score",
                "Scores returned from Pinecone calls",
            )

        tracer_provider = kwargs.get("tracer_provider")
        tracer = get_tracer(__name__, __version__, tracer_provider)
        for wrapped_method in WRAPPED_METHODS:
            wrap_object = wrapped_method.get("object")
            wrap_method = wrapped_method.get("method")
            if getattr(pinecone, wrap_object, None):
                wrap_function_wrapper(
                    "pinecone",
                    f"{wrap_object}.{wrap_method}",
                    _wrap(
                        tracer,
                        query_duration_metric,
                        read_units_metric,
                        write_units_metric,
                        scores_metric,
                        wrapped_method,
                    ),
                )

    def _uninstrument(self, **kwargs):
        for wrapped_method in WRAPPED_METHODS:
            wrap_object = wrapped_method.get("object")
            unwrap(f"pinecone.{wrap_object}", wrapped_method.get("method"))
