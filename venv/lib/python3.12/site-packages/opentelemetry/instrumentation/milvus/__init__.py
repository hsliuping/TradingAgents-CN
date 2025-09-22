"""OpenTelemetry Milvus DB instrumentation"""

import logging
import pymilvus

from typing import Collection

from opentelemetry.instrumentation.milvus.config import Config
from opentelemetry.trace import get_tracer
from wrapt import wrap_function_wrapper

from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from opentelemetry.instrumentation.utils import unwrap

from opentelemetry.instrumentation.milvus.wrapper import _wrap
from opentelemetry.instrumentation.milvus.version import __version__

logger = logging.getLogger(__name__)

_instruments = ("pymilvus >= 2.4.1",)

WRAPPED_METHODS = [
    {
        "package": pymilvus,
        "object": "MilvusClient",
        "method": "create_collection",
        "span_name": "milvus.create_collection"
    },
    {
        "package": pymilvus,
        "object": "MilvusClient",
        "method": "insert",
        "span_name": "milvus.insert"
    },
    {
        "package": pymilvus,
        "object": "MilvusClient",
        "method": "upsert",
        "span_name": "milvus.upsert"
    },
    {
        "package": pymilvus,
        "object": "MilvusClient",
        "method": "delete",
        "span_name": "milvus.delete"
    },
    {
        "package": pymilvus,
        "object": "MilvusClient",
        "method": "search",
        "span_name": "milvus.search"
    },
    {
        "package": pymilvus,
        "object": "MilvusClient",
        "method": "get",
        "span_name": "milvus.get"
    },
    {
        "package": pymilvus,
        "object": "MilvusClient",
        "method": "query",
        "span_name": "milvus.query"
    },
    {
        "package": pymilvus,
        "object": "MilvusClient",
        "method": "hybrid_search",
        "span_name": "milvus.hybrid_search"
    },
]


class MilvusInstrumentor(BaseInstrumentor):
    """An instrumentor for Milvus's client library."""

    def __init__(self, exception_logger=None):
        super().__init__()
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
            if getattr(wrap_package, wrap_object, None):
                wrap_function_wrapper(
                    wrap_package,
                    f"{wrap_object}.{wrap_method}",
                    _wrap(tracer, wrapped_method),
                )

    def _uninstrument(self, **kwargs):
        for wrapped_method in WRAPPED_METHODS:
            wrap_package = wrapped_method.get("package")
            wrap_object = wrapped_method.get("object")

            wrapped = getattr(wrap_package, wrap_object, None)
            if wrapped:
                unwrap(wrapped, wrapped_method.get("method"))
