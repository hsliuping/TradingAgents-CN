import json
import logging
from typing import Optional

from opentelemetry import context as context_api
from opentelemetry.instrumentation.utils import _SUPPRESS_INSTRUMENTATION_KEY
from opentelemetry.instrumentation.weaviate.utils import dont_throw
from opentelemetry.semconv.trace import SpanAttributes


logger = logging.getLogger(__name__)


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
        span.set_attribute(SpanAttributes.DB_SYSTEM, "weaviate")
        span.set_attribute(SpanAttributes.DB_OPERATION, to_wrap.get("method"))

        obj = to_wrap.get("object")
        instrumentor = InstrumentorFactory.from_name(obj)
        if instrumentor:
            instrumentor.instrument(to_wrap.get("method"), span, args, kwargs)

        return_value = wrapped(*args, **kwargs)

    return return_value


def count_or_none(obj):
    if obj:
        return len(obj)

    return None


class ArgsGetter:
    """Helper to make sure we get arguments regardless
    of whether they were passed as args or as kwargs.

    Additionally, cast serializes dicts to JSON string.
    """

    def __init__(self, args, kwargs):
        self.args = args
        self.kwargs = kwargs

    def __call__(self, index, name):
        try:
            obj = self.args[index]
        except IndexError:
            obj = self.kwargs.get(name)

        if obj:
            try:
                return json.dumps(obj)
            except json.decoder.JSONDecodeError:
                logger.warning(
                    "Failed to decode argument (%s) (%s) to JSON", index, name
                )


class _Instrumentor:
    def map_attributes(self, span, method_name, attributes, args, kwargs):
        getter = ArgsGetter(args, kwargs)
        for idx, attribute in enumerate(attributes):
            _set_span_attribute(
                span,
                f"{self.namespace}.{method_name}.{attribute}",
                getter(idx, attribute),
            )

    @dont_throw
    def instrument(self, method_name, span, args, kwargs):
        attributes = self.mapped_attributes.get(method_name)
        if attributes:
            self.map_attributes(span, method_name, attributes, args, kwargs)


class _SchemaInstrumentorV3(_Instrumentor):
    """v3, replaced in v4 by _CollectionsInstrumentor"""
    namespace = "db.weaviate.schema"
    mapped_attributes = {
        "get": ["class_name"],
        "create_class": ["schema_class"],
        "create": ["schema"],
        "delete_class": ["class_name"],
    }


class _CollectionsInstrumentor(_Instrumentor):
    namespace = "db.weaviate.collections"
    mapped_attributes = {
        "create": ["name"],
        "create_from_dict": ["config"],
        "get": ["name"],
        "delete": ["name"],
    }


class _DataObjectInstrumentorV3(_Instrumentor):
    """v3, replaced in v4 by _DataObjectInstrumentor"""
    namespace = "weaviate.data.crud_data"
    mapped_attributes = {
        "create": [
            "data_object",
            "class_name",
            "uuid",
            "vector",
            "consistency_level",
            "tenant",
        ],
        "validate": [
            "data_object",
            "class_name",
            "uuid",
            "vector",
        ],
        "get": [
            "uuid",
            "additional_properties",
            "with_vector",
            "class_name",
            "node_name",
            "consistency_level",
            "limit",
            "after",
            "offset",
            "sort",
            "tenant",
        ],
    }


class _DataObjectInstrumentor(_Instrumentor):
    namespace = "weaviate.collections.data"
    mapped_attributes = {
        "insert": [
            "properties",
            "references",
            "uuid",
            "vector",
        ],
        "replace": [
            "uuid",
            "properties",
            "references",
            "vector",
        ],
        "update": [
            "uuid",
            "properties",
            "references",
            "vector",
        ],
    }


class _BatchInstrumentorV3(_Instrumentor):
    """v3, replaced in v4 by _BatchInstrumentor"""
    namespace = "db.weaviate.batch"
    mapped_attributes = {
        "add_data_object": [
            "data_object",
            "class_name",
            "uuid",
            "vector",
            "tenant",
        ],
        "flush": [],
    }


class _BatchInstrumentor(_Instrumentor):
    namespace = "db.weaviate.collections.batch"
    mapped_attributes = {
        "add_object": [
            "properties",
            "references",
            "uuid",
            "vector",
        ],
    }


class _QueryInstrumentorV3(_Instrumentor):
    """v3, replaced in v4 by _QueryInstrumentor"""
    namespace = "db.weaviate.query"
    mapped_attributes = {
        "get": [
            "class_name",
            "properties",
        ],
        "aggregate": ["class_name"],
        "raw": ["gql_query"],
    }


class _QueryInstrumentor(_Instrumentor):
    namespace = "db.weaviate.collections.query"
    mapped_attributes = {
        "fetch_object_by_id": [
            "uuid",
            "include_vector",
            "return_properties",
            "return_references",
        ],
        "fetch_objects": [
            "limit",
            "offset",
            "after",
            "filters",
            "sort",
            "include_vector",
            "return_metadata",
            "return_properties",
            "return_references",
        ],
    }


class _AggregateBuilderInstrumentor(_Instrumentor):
    namespace = "db.weaviate.gql.aggregate"
    mapped_attributes = {
        "do": [],
    }


class _GetBuilderInstrumentorV3(_Instrumentor):
    """v3, replaced in v4 by _GetBuilderInstrumentor"""
    namespace = "db.weaviate.query.get"
    mapped_attributes = {
        "do": [],
    }


class _GetBuilderInstrumentor(_Instrumentor):
    namespace = "db.weaviate.gql.get"
    mapped_attributes = {
        "do": [],
    }


class _GraphQLInstrumentor(_Instrumentor):
    namespace = "db.weaviate.gql.filter"
    mapped_attributes = {
        "do": [],
    }


class _RawInstrumentor(_Instrumentor):
    namespace = "db.weaviate.client"
    mapped_attributes = {
        "graphql_raw_query": ["gql_query", ],
    }


class InstrumentorFactory:
    @classmethod
    def from_name(cls, name: str) -> Optional[_Instrumentor]:
        if name == "Schema":
            return _SchemaInstrumentorV3()
        elif name == "DataObject":
            return _DataObjectInstrumentorV3()
        elif name == "Batch":
            return _BatchInstrumentorV3()
        elif name == "Query":
            return _QueryInstrumentorV3()
        elif name == "GetBuilder":
            return _GetBuilderInstrumentorV3()

        if name == "_Collections":
            return _CollectionsInstrumentor()
        if name == "_DataCollection":
            return _DataObjectInstrumentor()
        if name == "_BatchCollection":
            return _BatchInstrumentor()
        if name in ("_FetchObjectByIDQuery", "_FetchObjectsQuery", "_QueryGRPC"):
            return _QueryInstrumentor()
        if name == "AggregateBuilder":
            return _AggregateBuilderInstrumentor()
        if name == "GetBuilder":
            return _GetBuilderInstrumentor()
        if name == "GraphQL":
            return _GraphQLInstrumentor()
        if name == "WeaviateClient":
            return _RawInstrumentor()
        return None
