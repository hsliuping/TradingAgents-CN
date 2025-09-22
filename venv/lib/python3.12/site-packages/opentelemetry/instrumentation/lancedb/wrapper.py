from opentelemetry.instrumentation.lancedb.utils import dont_throw
from opentelemetry.semconv.trace import SpanAttributes

from opentelemetry import context as context_api
from opentelemetry.instrumentation.utils import (
    _SUPPRESS_INSTRUMENTATION_KEY,
)
from opentelemetry.semconv_ai import SpanAttributes as AISpanAttributes


def _with_tracer_wrapper(func):
    """Helper for providing tracer for wrapper functions."""

    def _with_tracer(tracer, to_wrap):
        def wrapper(wrapped, instance, args, kwargs):
            return func(tracer, to_wrap, wrapped, instance, args, kwargs)

        return wrapper

    return _with_tracer


def _set_span_attribute(span, name, value):
    if value is not None:
        if value != "":
            span.set_attribute(name, value)
    return


@_with_tracer_wrapper
def _wrap(tracer, to_wrap, wrapped, instance, args, kwargs):
    """Instruments and calls every function defined in TO_WRAP."""
    if context_api.get_value(_SUPPRESS_INSTRUMENTATION_KEY):
        return wrapped(*args, **kwargs)

    name = to_wrap.get("span_name")
    with tracer.start_as_current_span(name) as span:
        span.set_attribute(SpanAttributes.DB_SYSTEM, "lancedb")
        span.set_attribute(SpanAttributes.DB_OPERATION, to_wrap.get("method"))

        if to_wrap.get("method") == "add":
            _set_add_attributes(span, kwargs)
        elif to_wrap.get("method") == "search":
            _set_search_attributes(span, kwargs)
        elif to_wrap.get("method") == "delete":
            _set_delete_attributes(span, kwargs)

        return_value = wrapped(*args, **kwargs)

    return return_value


def _encode_query(_query):
    _query_str = None
    if _query:
        _query_str = str(_query)

    return _query_str


def _count_or_none(obj):
    if obj:
        return len(obj)

    return None


@dont_throw
def _set_add_attributes(span, kwargs):
    _set_span_attribute(
        span, AISpanAttributes.MILVUS_INSERT_DATA_COUNT, _count_or_none(kwargs.get("data"))
    )


@dont_throw
def _set_search_attributes(span, kwargs):
    _set_span_attribute(
        span, AISpanAttributes.MILVUS_SEARCH_FILTER, _encode_query(kwargs.get("query"))
    )


@dont_throw
def _set_delete_attributes(span, kwargs):
    _set_span_attribute(
        span, AISpanAttributes.CHROMADB_DELETE_WHERE, kwargs.get("where")
    )
