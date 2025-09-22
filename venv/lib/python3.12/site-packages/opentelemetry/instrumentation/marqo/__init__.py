"""OpenTelemetry Marqo instrumentation"""

import logging
import marqo.index

from typing import Collection

from opentelemetry.instrumentation.marqo.config import Config
from opentelemetry.trace import get_tracer
from wrapt import wrap_function_wrapper

from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from opentelemetry.instrumentation.utils import unwrap

from opentelemetry.instrumentation.marqo.wrapper import _wrap
from opentelemetry.instrumentation.marqo.version import __version__

logger = logging.getLogger(__name__)

_instruments = ("marqo >= 3.5.1",)

WRAPPED_METHODS = [
    {
        "package": marqo.index,
        "object": "Index",
        "method": "add_documents",
        "span_name": "marqo.add_documents",
    },
    {
        "package": marqo.index,
        "object": "Index",
        "method": "search",
        "span_name": "marqo.search",
    },
    {
        "package": marqo.index,
        "object": "Index",
        "method": "delete_documents",
        "span_name": "marqo.delete_documents",
    },
]


class MarqoInstrumentor(BaseInstrumentor):
    """An instrumentor for Marqo's client library."""

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
