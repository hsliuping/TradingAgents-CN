from opentelemetry.instrumentation.milvus.utils import dont_throw
from opentelemetry.semconv.trace import SpanAttributes

from opentelemetry import context as context_api
from opentelemetry.instrumentation.utils import (
    _SUPPRESS_INSTRUMENTATION_KEY,
)
from opentelemetry.semconv_ai import Events, EventAttributes
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
        span.set_attribute(SpanAttributes.DB_SYSTEM, "milvus")
        span.set_attribute(SpanAttributes.DB_OPERATION, to_wrap.get("method"))

        if to_wrap.get("method") == "insert":
            _set_insert_attributes(span, kwargs)
        elif to_wrap.get("method") == "upsert":
            _set_upsert_attributes(span, kwargs)
        elif to_wrap.get("method") == "delete":
            _set_delete_attributes(span, kwargs)
        elif to_wrap.get("method") == "search":
            _set_search_attributes(span, kwargs)
        elif to_wrap.get("method") == "get":
            _set_get_attributes(span, kwargs)
        elif to_wrap.get("method") == "query":
            _set_query_attributes(span, kwargs)
        elif to_wrap.get("method") == "create_collection":
            _set_create_collection_attributes(span, kwargs)
        elif to_wrap.get("method") == "hybrid_search":
            _set_hybrid_search_attributes(span, kwargs)

        return_value = wrapped(*args, **kwargs)

        if to_wrap.get("method") == "query":
            _add_query_result_events(span, return_value)

        if (
            to_wrap.get("method") == "search"
            or to_wrap.get("method") == "hybrid_search"
        ):
            _add_search_result_events(span, return_value)

    return return_value


def _encode_filter(_filter):
    _filter_str = None
    if _filter:
        _filter_str = str(_filter)

    return _filter_str


def _encode_partition_name(partition_name):
    partition_name_str = None
    if partition_name:
        partition_name_str = str(partition_name)

    return partition_name_str


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
def _set_create_collection_attributes(span, kwargs):
    _set_span_attribute(
        span,
        AISpanAttributes.MILVUS_CREATE_COLLECTION_NAME,
        kwargs.get("collection_name"),
    )
    _set_span_attribute(
        span,
        AISpanAttributes.MILVUS_CREATE_COLLECTION_DIMENSION,
        kwargs.get("dimension"),
    )
    _set_span_attribute(
        span,
        AISpanAttributes.MILVUS_CREATE_COLLECTION_PRIMARY_FIELD,
        kwargs.get("primary_field_name"),
    )
    _set_span_attribute(
        span,
        AISpanAttributes.MILVUS_CREATE_COLLECTION_METRIC_TYPE,
        kwargs.get("metric_type"),
    )
    _set_span_attribute(
        span,
        AISpanAttributes.MILVUS_CREATE_COLLECTION_TIMEOUT,
        kwargs.get("timeout"),
    )
    _set_span_attribute(
        span,
        AISpanAttributes.MILVUS_CREATE_COLLECTION_ID_TYPE,
        kwargs.get("id_type"),
    )
    _set_span_attribute(
        span,
        AISpanAttributes.MILVUS_CREATE_COLLECTION_VECTOR_FIELD,
        kwargs.get("vector_field_name"),
    )


@dont_throw
def _set_insert_attributes(span, kwargs):
    _set_span_attribute(
        span,
        AISpanAttributes.MILVUS_INSERT_COLLECTION_NAME,
        kwargs.get("collection_name"),
    )
    _set_span_attribute(
        span,
        AISpanAttributes.MILVUS_INSERT_DATA_COUNT,
        count_or_none(kwargs.get("data")),
    )
    _set_span_attribute(
        span, AISpanAttributes.MILVUS_INSERT_TIMEOUT, kwargs.get("timeout")
    )
    _set_span_attribute(
        span,
        AISpanAttributes.MILVUS_INSERT_PARTITION_NAME,
        _encode_partition_name(kwargs.get("partition_name")),
    )


@dont_throw
def _set_get_attributes(span, kwargs):
    _set_span_attribute(
        span, AISpanAttributes.MILVUS_GET_COLLECTION_NAME, kwargs.get("collection_name")
    )
    _set_span_attribute(
        span, AISpanAttributes.MILVUS_GET_IDS_COUNT, count_or_none(kwargs.get("ids"))
    )
    _set_span_attribute(
        span,
        AISpanAttributes.MILVUS_GET_OUTPUT_FIELDS_COUNT,
        count_or_none(kwargs.get("output_fields")),
    )
    _set_span_attribute(
        span, AISpanAttributes.MILVUS_GET_TIMEOUT, kwargs.get("timeout")
    )
    _set_span_attribute(
        span,
        AISpanAttributes.MILVUS_GET_PARTITION_NAMES_COUNT,
        count_or_none(kwargs.get("partition_names")),
    )


@dont_throw
def _set_search_attributes(span, kwargs):
    _set_span_attribute(
        span,
        AISpanAttributes.MILVUS_SEARCH_COLLECTION_NAME,
        kwargs.get("collection_name"),
    )
    _set_span_attribute(
        span,
        AISpanAttributes.MILVUS_SEARCH_DATA_COUNT,
        count_or_none(kwargs.get("data")),
    )
    _set_span_attribute(
        span, AISpanAttributes.MILVUS_SEARCH_FILTER, kwargs.get("filter")
    )
    _set_span_attribute(span, AISpanAttributes.MILVUS_SEARCH_LIMIT, kwargs.get("limit"))
    _set_span_attribute(
        span,
        AISpanAttributes.MILVUS_SEARCH_OUTPUT_FIELDS_COUNT,
        count_or_none(kwargs.get("output_fields")),
    )
    _set_span_attribute(
        span,
        AISpanAttributes.MILVUS_SEARCH_SEARCH_PARAMS,
        _encode_include(kwargs.get("search_params")),
    )
    _set_span_attribute(
        span, AISpanAttributes.MILVUS_SEARCH_TIMEOUT, kwargs.get("timeout")
    )
    _set_span_attribute(
        span,
        AISpanAttributes.MILVUS_SEARCH_PARTITION_NAMES_COUNT,
        count_or_none(kwargs.get("partition_names")),
    )
    _set_span_attribute(
        span, AISpanAttributes.MILVUS_SEARCH_ANNS_FIELD, kwargs.get("anns_field")
    )
    _set_span_attribute(
        span,
        AISpanAttributes.MILVUS_SEARCH_PARTITION_NAMES,
        _encode_partition_name(kwargs.get("partition_names")),
    )
    query_vectors = kwargs.get("data", [])
    vector_dims = [len(vec) for vec in query_vectors]

    _set_span_attribute(
        span,
        AISpanAttributes.MILVUS_SEARCH_QUERY_VECTOR_DIMENSION,
        _encode_include(vector_dims),
    )


@dont_throw
def _set_hybrid_search_attributes(span, kwargs):
    _set_span_attribute(
        span,
        AISpanAttributes.MILVUS_SEARCH_COLLECTION_NAME,
        kwargs.get("collection_name"),
    )

    reqs_info = []
    for req in kwargs.get("reqs", []):
        req_info = {
            "anns_field": req.anns_field,
            "param": req.param,
        }
        reqs_info.append(req_info)

    _set_span_attribute(
        span,
        AISpanAttributes.MILVUS_SEARCH_ANNSEARCH_REQUEST,
        _encode_include(reqs_info),
    )
    _set_span_attribute(
        span,
        AISpanAttributes.MILVUS_SEARCH_RANKER_TYPE,
        _encode_include(type(kwargs.get("ranker")).__name__),
    )
    _set_span_attribute(span, AISpanAttributes.MILVUS_SEARCH_LIMIT, kwargs.get("limit"))
    _set_span_attribute(
        span,
        AISpanAttributes.MILVUS_SEARCH_DATA_COUNT,
        count_or_none(kwargs.get("reqs")),
    )
    _set_span_attribute(
        span,
        AISpanAttributes.MILVUS_SEARCH_OUTPUT_FIELDS_COUNT,
        count_or_none(kwargs.get("output_fields")),
    )
    _set_span_attribute(
        span, AISpanAttributes.MILVUS_SEARCH_TIMEOUT, kwargs.get("timeout")
    )
    _set_span_attribute(
        span,
        AISpanAttributes.MILVUS_SEARCH_PARTITION_NAMES_COUNT,
        count_or_none(kwargs.get("partition_names")),
    )
    _set_span_attribute(
        span,
        AISpanAttributes.MILVUS_SEARCH_PARTITION_NAMES,
        _encode_partition_name(kwargs.get("partition_names")),
    )


@dont_throw
def _set_query_attributes(span, kwargs):
    _set_span_attribute(
        span,
        AISpanAttributes.MILVUS_QUERY_COLLECTION_NAME,
        kwargs.get("collection_name"),
    )
    _set_span_attribute(
        span, AISpanAttributes.MILVUS_QUERY_FILTER, _encode_filter(kwargs.get("filter"))
    )
    _set_span_attribute(
        span,
        AISpanAttributes.MILVUS_QUERY_OUTPUT_FIELDS_COUNT,
        count_or_none(kwargs.get("output_fields")),
    )
    _set_span_attribute(
        span, AISpanAttributes.MILVUS_QUERY_TIMEOUT, kwargs.get("timeout")
    )
    _set_span_attribute(
        span, AISpanAttributes.MILVUS_QUERY_IDS_COUNT, count_or_none(kwargs.get("ids"))
    )
    _set_span_attribute(
        span,
        AISpanAttributes.MILVUS_QUERY_PARTITION_NAMES_COUNT,
        count_or_none(kwargs.get("partition_names")),
    )
    _set_span_attribute(span, AISpanAttributes.MILVUS_QUERY_LIMIT, kwargs.get("limit"))


@dont_throw
def _add_query_result_events(span, kwargs):
    for element in kwargs:
        span.add_event(name=Events.DB_QUERY_RESULT.value, attributes=element)


@dont_throw
def _add_search_result_events(span, kwargs):

    all_distances = []
    total_matches = 0

    single_query = len(kwargs) == 1

    def set_query_stats(query_idx, distances, match_ids):
        """Helper function to set per-query stats in the span."""
        _set_span_attribute(
            span,
            f"{AISpanAttributes.MILVUS_SEARCH_RESULT_COUNT}_{query_idx}",
            len(distances),
        )

    def set_global_stats():
        """Helper function to set global stats for a single query."""
        _set_span_attribute(
            span, AISpanAttributes.MILVUS_SEARCH_RESULT_COUNT, total_matches
        )
    for query_idx, query_results in enumerate(kwargs):

        query_distances = []
        query_match_ids = []

        for match in query_results:
            distance = float(match["distance"])
            query_distances.append(distance)
            all_distances.append(distance)
            total_matches += 1
            query_match_ids.append(match["id"])

            span.add_event(
                Events.DB_SEARCH_RESULT.value,
                attributes={
                    EventAttributes.DB_SEARCH_RESULT_QUERY_ID.value: query_idx,
                    EventAttributes.DB_SEARCH_RESULT_ID.value: match["id"],
                    EventAttributes.DB_SEARCH_RESULT_DISTANCE.value: str(distance),
                    EventAttributes.DB_SEARCH_RESULT_ENTITY.value: _encode_include(
                        match["entity"]
                    ),
                },
            )

        if not single_query:
            set_query_stats(query_idx, query_distances, query_match_ids)

    if single_query:
        set_global_stats()


@dont_throw
def _set_upsert_attributes(span, kwargs):
    _set_span_attribute(
        span,
        AISpanAttributes.MILVUS_UPSERT_COLLECTION_NAME,
        kwargs.get("collection_name"),
    )
    _set_span_attribute(
        span,
        AISpanAttributes.MILVUS_UPSERT_DATA_COUNT,
        count_or_none(kwargs.get("data")),
    )
    _set_span_attribute(
        span,
        AISpanAttributes.MILVUS_UPSERT_TIMEOUT,
        kwargs.get("timeout"),
    )
    _set_span_attribute(
        span,
        AISpanAttributes.MILVUS_UPSERT_PARTITION_NAME,
        _encode_partition_name(kwargs.get("partition_name")),
    )


@dont_throw
def _set_delete_attributes(span, kwargs):
    _set_span_attribute(
        span,
        AISpanAttributes.MILVUS_DELETE_COLLECTION_NAME,
        kwargs.get("collection_name"),
    )
    _set_span_attribute(
        span,
        AISpanAttributes.MILVUS_DELETE_TIMEOUT,
        kwargs.get("timeout"),
    )
    _set_span_attribute(
        span,
        AISpanAttributes.MILVUS_DELETE_PARTITION_NAME,
        _encode_partition_name(kwargs.get("partition_name")),
    )
    _set_span_attribute(
        span, AISpanAttributes.MILVUS_DELETE_IDS_COUNT, count_or_none(kwargs.get("ids"))
    )
    _set_span_attribute(
        span,
        AISpanAttributes.MILVUS_DELETE_FILTER,
        _encode_filter(kwargs.get("filter")),
    )
