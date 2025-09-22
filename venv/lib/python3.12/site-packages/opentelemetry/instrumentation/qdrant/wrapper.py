from opentelemetry import context as context_api
from opentelemetry.instrumentation.qdrant.utils import dont_throw
from opentelemetry.trace.status import Status, StatusCode
from opentelemetry.instrumentation.utils import (
    _SUPPRESS_INSTRUMENTATION_KEY,
)
from opentelemetry.trace import SpanKind
from opentelemetry.semconv_ai import SpanAttributes


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

    name = to_wrap.get("span_name")
    method = to_wrap.get("method")
    with tracer.start_as_current_span(
        name,
        kind=SpanKind.CLIENT,
        attributes={
            SpanAttributes.VECTOR_DB_VENDOR: "Qdrant",
        },
    ) as span:
        _set_collection_name_attribute(
            span, method, args, kwargs
        )  # Set the collection name attribute for all traced methods

        # Begin setting addional attributes for specific methods
        if method == "upsert":
            _set_upsert_attributes(span, args, kwargs)
        elif method == "add":
            _set_upload_attributes(span, args, kwargs, method, "documents")
        elif method == "upload_points":
            _set_upload_attributes(span, args, kwargs, method, "points")
        elif method == "upload_records":
            _set_upload_attributes(span, args, kwargs, method, "records")
        elif method == "upload_collection":
            _set_upload_attributes(span, args, kwargs, method, "vectors")
        elif method in [
            "search",
            "search_groups",
            "query",
            "discover",
            "recommend",
            "recommend_groups",
        ]:
            _set_search_attributes(span, args, kwargs)
        elif method in ["search_batch", "recommend_batch", "discover_batch"]:
            _set_batch_search_attributes(span, args, kwargs, method)

        response = wrapped(*args, **kwargs)
        if response:
            span.set_status(Status(StatusCode.OK))
    return response


@dont_throw
def _set_collection_name_attribute(span, method, args, kwargs):
    _set_span_attribute(
        span,
        f"qdrant.{method}.collection_name",
        kwargs.get("collection_name") or args[0],
    )


@dont_throw
def _set_upsert_attributes(span, args, kwargs):
    points = kwargs.get("points") or args[1]
    if isinstance(points, list):
        length = len(points)
    else:
        length = len(
            points.ids
        )  # If using models.Batch instead of list[models.PointStruct]
    _set_span_attribute(span, SpanAttributes.QDRANT_UPSERT_POINTS_COUNT, length)


@dont_throw
def _set_upload_attributes(span, args, kwargs, method_name, param_name):
    points = list(kwargs.get(param_name) or args[1])
    _set_span_attribute(span, f"qdrant.{method_name}.points_count", len(points))


@dont_throw
def _set_search_attributes(span, args, kwargs):
    limit = kwargs.get("limit") or 10
    _set_span_attribute(span, SpanAttributes.VECTOR_DB_QUERY_TOP_K, limit)


@dont_throw
def _set_batch_search_attributes(span, args, kwargs, method):
    requests = kwargs.get("requests") or []
    _set_span_attribute(span, f"qdrant.{method}.requests_count", len(requests))
