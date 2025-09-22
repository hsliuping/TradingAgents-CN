from opentelemetry.instrumentation.marqo.utils import dont_throw
from opentelemetry.semconv.trace import SpanAttributes

from opentelemetry import context as context_api
from opentelemetry.instrumentation.utils import (
    _SUPPRESS_INSTRUMENTATION_KEY,
)
from opentelemetry.semconv_ai import SUPPRESS_LANGUAGE_MODEL_INSTRUMENTATION_KEY, Events
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
    if context_api.get_value(_SUPPRESS_INSTRUMENTATION_KEY) or context_api.get_value(
        SUPPRESS_LANGUAGE_MODEL_INSTRUMENTATION_KEY
    ):
        return wrapped(*args, **kwargs)

    name = to_wrap.get("span_name")
    with tracer.start_as_current_span(name) as span:
        span.set_attribute(SpanAttributes.DB_SYSTEM, "marqo")
        span.set_attribute(SpanAttributes.DB_OPERATION, to_wrap.get("method"))

        if to_wrap.get("method") == "add_documents":
            _set_add_documents_attributes(span, kwargs)
        elif to_wrap.get("method") == "search":
            _set_search_attributes(span, kwargs)
        elif to_wrap.get("method") == "delete_documents":
            _set_delete_documents_attributes(span, kwargs)

        return_value = wrapped(*args, **kwargs)
        if to_wrap.get("method") == "search":
            _set_search_result_attributes(span, return_value)
        if to_wrap.get("method") == "delete_documents":
            _set_delete_documents_response_attributes(span, return_value)

    return return_value


def count_or_none(obj):
    if obj:
        return len(obj)

    return None


@dont_throw
def _set_add_documents_attributes(span, kwargs):
    """
    In contrast to the example in Marqo's docs,
    this requires the declaration of the documents array with the label "documents = ..."
    (https://docs.marqo.ai/2.8/API-Reference/Documents/add_or_replace_documents/)
    Otherwise we cannot retrieve the documents
    see also: https://github.com/traceloop/openllmetry/issues/539
    """
    _set_span_attribute(
        span,
        AISpanAttributes.CHROMADB_ADD_DOCUMENTS_COUNT,
        count_or_none(kwargs.get("documents")),
    )


@dont_throw
def _set_search_attributes(span, kwargs):
    _set_span_attribute(span, "db.marqo.search.query", kwargs.get("q"))


@dont_throw
def _set_delete_documents_attributes(span, kwargs):
    _set_span_attribute(
        span, AISpanAttributes.MILVUS_DELETE_IDS_COUNT, count_or_none(kwargs.get("ids"))
    )


@dont_throw
def _set_search_result_attributes(span, kwargs):
    _set_span_attribute(
        span, "db.marqo.search.processing_time", kwargs.get("processingTimeMs")
    )

    events = kwargs.get("hits")
    for event in events:
        span.add_event(name=Events.DB_QUERY_RESULT.value, attributes=event)


@dont_throw
def _set_delete_documents_response_attributes(span, kwargs):
    _set_span_attribute(span, "db.marqo.delete_documents.status", kwargs.get("status"))
