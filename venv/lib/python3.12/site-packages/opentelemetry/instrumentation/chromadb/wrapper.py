from opentelemetry.instrumentation.chromadb.utils import dont_throw
from opentelemetry.semconv.trace import SpanAttributes

from opentelemetry import context as context_api
from opentelemetry.instrumentation.utils import (
    _SUPPRESS_INSTRUMENTATION_KEY,
)
from opentelemetry.semconv_ai import EventAttributes, Events
from opentelemetry.semconv_ai import SpanAttributes as AISpanAttributes
import itertools
import json


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
        span.set_attribute(SpanAttributes.DB_SYSTEM, "chroma")
        span.set_attribute(SpanAttributes.DB_OPERATION, to_wrap.get("method"))

        if to_wrap.get("method") == "add":
            _set_add_attributes(span, kwargs)
        elif to_wrap.get("method") == "get":
            _set_get_attributes(span, kwargs)
        elif to_wrap.get("method") == "peek":
            _set_peek_attributes(span, kwargs)
        elif to_wrap.get("method") == "query":
            _set_query_attributes(span, kwargs)
        elif to_wrap.get("method") == "_query":
            _set_segment_query_attributes(span, kwargs)
            _add_segment_query_embeddings_events(span, kwargs)
        elif to_wrap.get("method") == "modify":
            _set_modify_attributes(span, kwargs)
        elif to_wrap.get("method") == "update":
            _set_update_attributes(span, kwargs)
        elif to_wrap.get("method") == "upsert":
            _set_upsert_attributes(span, kwargs)
        elif to_wrap.get("method") == "delete":
            _set_delete_attributes(span, kwargs)

        return_value = wrapped(*args, **kwargs)
        if to_wrap.get("method") == "query":
            _add_query_result_events(span, return_value)

    return return_value


def _encode_where(where):
    where_str = None
    if where:
        where_str = str(where)

    return where_str


def _encode_where_document(where_document):
    where_document_str = None
    if where_document:
        where_document_str = str(where_document)

    return where_document_str


def _encode_include(include):
    include_str = None
    if include:
        include_str = str(include)

    return include_str


def count_or_none(obj):
    if obj:
        return len(obj)

    return None


@dont_throw
def _set_add_attributes(span, kwargs):
    _set_span_attribute(
        span, AISpanAttributes.CHROMADB_ADD_IDS_COUNT, count_or_none(kwargs.get("ids"))
    )
    _set_span_attribute(
        span,
        AISpanAttributes.CHROMADB_ADD_EMBEDDINGS_COUNT,
        count_or_none(kwargs.get("embeddings")),
    )
    _set_span_attribute(
        span,
        AISpanAttributes.CHROMADB_ADD_METADATAS_COUNT,
        count_or_none(kwargs.get("metadatas")),
    )
    _set_span_attribute(
        span,
        AISpanAttributes.CHROMADB_ADD_DOCUMENTS_COUNT,
        count_or_none(kwargs.get("documents")),
    )


@dont_throw
def _set_get_attributes(span, kwargs):
    _set_span_attribute(
        span, AISpanAttributes.CHROMADB_GET_IDS_COUNT, count_or_none(kwargs.get("ids"))
    )
    _set_span_attribute(
        span, AISpanAttributes.CHROMADB_GET_WHERE, _encode_where(kwargs.get("where"))
    )
    _set_span_attribute(span, AISpanAttributes.CHROMADB_GET_LIMIT, kwargs.get("limit"))
    _set_span_attribute(
        span, AISpanAttributes.CHROMADB_GET_OFFSET, kwargs.get("offset")
    )
    _set_span_attribute(
        span,
        AISpanAttributes.CHROMADB_GET_WHERE_DOCUMENT,
        _encode_where_document(kwargs.get("where_document")),
    )
    _set_span_attribute(
        span,
        AISpanAttributes.CHROMADB_GET_INCLUDE,
        _encode_include(kwargs.get("include")),
    )


@dont_throw
def _set_peek_attributes(span, kwargs):
    _set_span_attribute(span, AISpanAttributes.CHROMADB_PEEK_LIMIT, kwargs.get("limit"))


@dont_throw
def _set_query_attributes(span, kwargs):
    _set_span_attribute(
        span,
        AISpanAttributes.CHROMADB_QUERY_EMBEDDINGS_COUNT,
        count_or_none(kwargs.get("query_embeddings")),
    )
    _set_span_attribute(
        span,
        AISpanAttributes.CHROMADB_QUERY_TEXTS_COUNT,
        count_or_none(kwargs.get("query_texts")),
    )
    _set_span_attribute(
        span, AISpanAttributes.CHROMADB_QUERY_N_RESULTS, kwargs.get("n_results")
    )
    _set_span_attribute(
        span, AISpanAttributes.CHROMADB_QUERY_WHERE, _encode_where(kwargs.get("where"))
    )
    _set_span_attribute(
        span,
        AISpanAttributes.CHROMADB_QUERY_WHERE_DOCUMENT,
        _encode_where_document(kwargs.get("where_document")),
    )
    _set_span_attribute(
        span,
        AISpanAttributes.CHROMADB_QUERY_INCLUDE,
        _encode_include(kwargs.get("include")),
    )


@dont_throw
def _set_segment_query_attributes(span, kwargs):
    _set_span_attribute(
        span,
        AISpanAttributes.CHROMADB_QUERY_SEGMENT_QUERY_COLLECTION_ID,
        str(kwargs.get("collection_id")),
    )


@dont_throw
def _add_segment_query_embeddings_events(span, kwargs):
    for i, embeddings in enumerate(kwargs.get("query_embeddings", [])):
        span.add_event(
            name=Events.DB_QUERY_EMBEDDINGS.value,
            attributes={
                EventAttributes.DB_QUERY_EMBEDDINGS_VECTOR.value: json.dumps(embeddings)
            },
        )


@dont_throw
def _add_query_result_events(span, kwargs):
    """
    There's a lot of logic here involved in converting the query result
    format from ChromaDB into the canonical format (taken from Pinecone)

    This is because Chroma query result looks like this:

        {
           ids: [1, 2, 3...],
           distances: [0.3, 0.5, 0.6...],
           metadata: ["some metadata text", "another metadata text",...],
           documents: ["retrieved text", "retrieved text2", ...]
        }

    We'd like instead to log it like this:

        [
            {"id": 1, "distance": 0.3,  "document": "retrieved text", "metadata": "some metadata text",
            {"id": 2, "distance" 0.5, , "document": "retrieved text2": "another metadata text",
            {"id": 3, "distance": 0.6, "document": ..., "metadata": ...
        ]

    If you'd like to understand better why, please read the discussions on PR #370:
    https://github.com/traceloop/openllmetry/pull/370

    The goal is to set a canonical format which we call as a Semantic Convention.
    """
    zipped = itertools.zip_longest(
        kwargs.get("ids", []) or [],
        kwargs.get("distances", []) or [],
        kwargs.get("metadatas", []) or [],
        kwargs.get("documents", []) or [],
    )
    for tuple_ in zipped:
        attributes = {
            EventAttributes.DB_QUERY_RESULT_ID.value: None,
            EventAttributes.DB_QUERY_RESULT_DISTANCE.value: None,
            EventAttributes.DB_QUERY_RESULT_METADATA.value: None,
            EventAttributes.DB_QUERY_RESULT_DOCUMENT.value: None,
        }

        attributes_order = ["ids", "distances", "metadatas", "documents"]
        attributes_mapping_to_canonical_format = {
            "ids": EventAttributes.DB_QUERY_RESULT_ID.value,
            "distances": EventAttributes.DB_QUERY_RESULT_DISTANCE.value,
            "metadatas": EventAttributes.DB_QUERY_RESULT_METADATA.value,
            "documents": EventAttributes.DB_QUERY_RESULT_DOCUMENT.value,
        }
        for j, attr in enumerate(tuple_):
            original_attribute_name = attributes_order[j]
            canonical_name = attributes_mapping_to_canonical_format[
                original_attribute_name
            ]
            try:
                value = attr[0]
                if isinstance(value, dict):
                    value = json.dumps(value)

                attributes[canonical_name] = value
            except (IndexError, TypeError):
                # Don't send missing values as nulls, OpenTelemetry dislikes them!
                del attributes[canonical_name]

        span.add_event(name=Events.DB_QUERY_RESULT.value, attributes=attributes)


@dont_throw
def _set_modify_attributes(span, kwargs):
    _set_span_attribute(span, AISpanAttributes.CHROMADB_MODIFY_NAME, kwargs.get("name"))
    # TODO: Add metadata attribute


@dont_throw
def _set_update_attributes(span, kwargs):
    _set_span_attribute(
        span,
        AISpanAttributes.CHROMADB_UPDATE_IDS_COUNT,
        count_or_none(kwargs.get("ids")),
    )
    _set_span_attribute(
        span,
        AISpanAttributes.CHROMADB_UPDATE_EMBEDDINGS_COUNT,
        count_or_none(kwargs.get("embeddings")),
    )
    _set_span_attribute(
        span,
        AISpanAttributes.CHROMADB_UPDATE_METADATAS_COUNT,
        count_or_none(kwargs.get("metadatas")),
    )
    _set_span_attribute(
        span,
        AISpanAttributes.CHROMADB_UPDATE_DOCUMENTS_COUNT,
        count_or_none(kwargs.get("documents")),
    )


@dont_throw
def _set_upsert_attributes(span, kwargs):
    _set_span_attribute(
        span,
        AISpanAttributes.CHROMADB_UPSERT_EMBEDDINGS_COUNT,
        count_or_none(kwargs.get("embeddings")),
    )
    _set_span_attribute(
        span,
        AISpanAttributes.CHROMADB_UPSERT_METADATAS_COUNT,
        count_or_none(kwargs.get("metadatas")),
    )
    _set_span_attribute(
        span,
        AISpanAttributes.CHROMADB_UPSERT_DOCUMENTS_COUNT,
        count_or_none(kwargs.get("documents")),
    )


@dont_throw
def _set_delete_attributes(span, kwargs):
    _set_span_attribute(
        span,
        AISpanAttributes.CHROMADB_DELETE_IDS_COUNT,
        count_or_none(kwargs.get("ids")),
    )
    _set_span_attribute(
        span, AISpanAttributes.CHROMADB_DELETE_WHERE, _encode_where(kwargs.get("where"))
    )
    _set_span_attribute(
        span,
        AISpanAttributes.CHROMADB_DELETE_WHERE_DOCUMENT,
        _encode_where_document(kwargs.get("where_document")),
    )
