"""OpenTelemetry Chroma DB instrumentation"""

import logging
import chromadb
import chromadb.api.segment

from typing import Collection

from opentelemetry.instrumentation.chromadb.config import Config
from opentelemetry.trace import get_tracer
from wrapt import wrap_function_wrapper

from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from opentelemetry.instrumentation.utils import unwrap

from opentelemetry.instrumentation.chromadb.wrapper import _wrap
from opentelemetry.instrumentation.chromadb.version import __version__

logger = logging.getLogger(__name__)

_instruments = ("chromadb >= 0.3",)

WRAPPED_METHODS = [
    {
        "package": chromadb.api.segment,
        "object": "SegmentAPI",
        "method": "_query",
        "span_name": "chroma.query.segment._query",
    },
    {
        "package": chromadb,
        "object": "Collection",
        "method": "add",
        "span_name": "chroma.add",
    },
    {
        "package": chromadb,
        "object": "Collection",
        "method": "get",
        "span_name": "chroma.get",
    },
    {
        "package": chromadb,
        "object": "Collection",
        "method": "peek",
        "span_name": "chroma.peek",
    },
    {
        "package": chromadb,
        "object": "Collection",
        "method": "query",
        "span_name": "chroma.query",
    },
    {
        "package": chromadb,
        "object": "Collection",
        "method": "modify",
        "span_name": "chroma.modify",
    },
    {
        "package": chromadb,
        "object": "Collection",
        "method": "update",
        "span_name": "chroma.update",
    },
    {
        "package": chromadb,
        "object": "Collection",
        "method": "upsert",
        "span_name": "chroma.upsert",
    },
    {
        "package": chromadb,
        "object": "Collection",
        "method": "delete",
        "span_name": "chroma.delete",
    },
]


class ChromaInstrumentor(BaseInstrumentor):
    """An instrumentor for Chroma's client library."""

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
