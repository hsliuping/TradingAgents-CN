"""OpenTelemetry Weaviate instrumentation"""

import importlib
import logging
from typing import Collection

from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from opentelemetry.instrumentation.utils import unwrap
from opentelemetry.instrumentation.weaviate.config import Config
from opentelemetry.instrumentation.weaviate.version import __version__
from opentelemetry.instrumentation.weaviate.wrapper import _wrap
from opentelemetry.trace import get_tracer
from wrapt import wrap_function_wrapper


logger = logging.getLogger(__name__)

_instruments = ("weaviate-client >= 3.26.0, <5",)


WRAPPED_METHODS_v3 = [
    {
        "module": "weaviate.schema",
        "object": "Schema",
        "method": "get",
        "span_name": "db.weaviate.schema.get",
    },
    {
        "module": "weaviate.schema",
        "object": "Schema",
        "method": "create_class",
        "span_name": "db.weaviate.schema.create_class",
    },
    {
        "module": "weaviate.schema",
        "object": "Schema",
        "method": "create",
        "span_name": "db.weaviate.schema.create",
    },
    {
        "module": "weaviate.schema",
        "object": "Schema",
        "method": "delete_class",
        "span_name": "db.weaviate.schema.delete_class",
    },
    {
        "module": "weaviate.schema",
        "object": "Schema",
        "method": "delete_all",
        "span_name": "db.weaviate.schema.delete_all",
    },
    {
        "module": "weaviate.data.crud_data",
        "object": "DataObject",
        "method": "create",
        "span_name": "db.weaviate.data.crud_data.create",
    },
    {
        "module": "weaviate.data.crud_data",
        "object": "DataObject",
        "method": "validate",
        "span_name": "db.weaviate.data.crud_data.validate",
    },
    {
        "module": "weaviate.data.crud_data",
        "object": "DataObject",
        "method": "get",
        "span_name": "db.weaviate.data.crud_data.get",
    },
    {
        "module": "weaviate.batch.crud_batch",
        "object": "Batch",
        "method": "add_data_object",
        "span_name": "db.weaviate.batch.crud_batch.add_data_object",
    },
    {
        "module": "weaviate.batch.crud_batch",
        "object": "Batch",
        "method": "flush",
        "span_name": "db.weaviate.batch.crud_batch.flush",
    },
    {
        "module": "weaviate.batch.crud_batch",
        "object": "Batch",
        "method": "flush",
        "span_name": "db.weaviate.batch.crud_batch.flush",
    },
    {
        "module": "weaviate.gql.query",
        "object": "Query",
        "method": "get",
        "span_name": "db.weaviate.gql.query.get",
    },
    {
        "module": "weaviate.gql.query",
        "object": "Query",
        "method": "aggregate",
        "span_name": "db.weaviate.gql.query.aggregate",
    },
    {
        "module": "weaviate.gql.query",
        "object": "Query",
        "method": "raw",
        "span_name": "db.weaviate.gql.query.raw",
    },
    {
        "module": "weaviate.gql.get",
        "object": "GetBuilder",
        "method": "do",
        "span_name": "db.weaviate.gql.query.get.do",
    },
]
WRAPPED_METHODS_v4 = [
    {
        "module": "weaviate.collections.collections",
        "object": "_Collections",
        "method": "get",
        "span_name": "db.weaviate.collections.get",
    },
    {
        "module": "weaviate.collections.collections",
        "object": "_Collections",
        "method": "create",
        "span_name": "db.weaviate.collections.create",
    },
    {
        "module": "weaviate.collections.collections",
        "object": "_Collections",
        "method": "create_from_dict",
        "span_name": "db.weaviate.collections.create_from_dict",
    },
    {
        "module": "weaviate.collections.collections",
        "object": "_Collections",
        "method": "delete",
        "span_name": "db.weaviate.collections.delete",
    },
    {
        "module": "weaviate.collections.collections",
        "object": "_Collections",
        "method": "delete_all",
        "span_name": "db.weaviate.collections.delete_all",
    },
    {
        "module": "weaviate.collections.data",
        "object": "_DataCollection",
        "method": "insert",
        "span_name": "db.weaviate.collections.data.insert",
    },
    {
        "module": "weaviate.collections.data",
        "object": "_DataCollection",
        "method": "replace",
        "span_name": "db.weaviate.collections.data.replace",
    },
    {
        "module": "weaviate.collections.data",
        "object": "_DataCollection",
        "method": "update",
        "span_name": "db.weaviate.collections.data.update",
    },
    {
        "module": "weaviate.collections.batch.collection",
        "object": "_BatchCollection",
        "method": "add_object",
        "span_name": "db.weaviate.collections.batch.add_object",
    },
    {
        "module": "weaviate.collections.queries.fetch_object_by_id.query",
        "object": "_FetchObjectByIDQuery",
        "method": "fetch_object_by_id",
        "span_name": "db.weaviate.collections.query.fetch_object_by_id",
    },
    {
        "module": "weaviate.collections.queries.fetch_objects.query",
        "object": "_FetchObjectsQuery",
        "method": "fetch_objects",
        "span_name": "db.weaviate.collections.query.fetch_objects",
    },
    {
        "module": "weaviate.collections.grpc.query",
        "object": "_QueryGRPC",
        "method": "get",
        "span_name": "db.weaviate.collections.query.get",
    },
    {
        "module": "weaviate.gql.filter",
        "object": "GraphQL",
        "method": "do",
        "span_name": "db.weaviate.gql.filter.do",
    },
    {
        "module": "weaviate.gql.aggregate",
        "object": "AggregateBuilder",
        "method": "do",
        "span_name": "db.weaviate.gql.aggregate.do",
    },
    {
        "module": "weaviate.gql.get",
        "object": "GetBuilder",
        "method": "do",
        "span_name": "db.weaviate.gql.get.do",
    },
    {
        "module": "weaviate.client",
        "object": "WeaviateClient",
        "method": "graphql_raw_query",
        "span_name": "db.weaviate.client.graphql_raw_query",
    },
]
WRAPPED_METHODS = WRAPPED_METHODS_v3 + WRAPPED_METHODS_v4


class WeaviateInstrumentor(BaseInstrumentor):
    """An instrumentor for Weaviate's client library."""

    def __init__(self, exception_logger=None):
        super().__init__()
        Config.exception_logger = exception_logger

    def instrumentation_dependencies(self) -> Collection[str]:
        return _instruments

    def _instrument(self, **kwargs):
        tracer_provider = kwargs.get("tracer_provider")
        tracer = get_tracer(__name__, __version__, tracer_provider)
        for wrapped_method in WRAPPED_METHODS:
            wrap_module = wrapped_method.get("module")
            wrap_object = wrapped_method.get("object")
            wrap_method = wrapped_method.get("method")
            module = importlib.import_module(wrap_module)
            if getattr(module, wrap_object, None):
                wrap_function_wrapper(
                    wrap_module,
                    f"{wrap_object}.{wrap_method}",
                    _wrap(tracer, wrapped_method),
                )

    def _uninstrument(self, **kwargs):
        for wrapped_method in WRAPPED_METHODS:
            wrap_module = wrapped_method.get("module")
            wrap_object = wrapped_method.get("object")
            module = importlib.import_module(wrap_module)
            wrapped = getattr(module, wrap_object, None)
            if wrapped:
                unwrap(wrapped, wrapped_method.get("method"))
