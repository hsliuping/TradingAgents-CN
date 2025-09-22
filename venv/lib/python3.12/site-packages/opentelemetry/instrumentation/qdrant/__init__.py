"""OpenTelemetry Qdrant instrumentation"""

import json
import logging
from pathlib import Path
from opentelemetry.instrumentation.qdrant.config import Config
from opentelemetry.instrumentation.qdrant.wrapper import _wrap
import qdrant_client
from typing import Collection
from wrapt import wrap_function_wrapper


from opentelemetry.trace import get_tracer


from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from opentelemetry.instrumentation.utils import unwrap
from opentelemetry.instrumentation.qdrant.version import __version__


logger = logging.getLogger(__name__)

_instruments = ("qdrant-client >= 1.7",)

p = Path(__file__).with_name("qdrant_client_methods.json")
with open(p, "r") as f:
    QDRANT_CLIENT_METHODS = json.loads(f.read())

p = Path(__file__).with_name("async_qdrant_client_methods.json")
with open(p, "r") as f:
    ASYNC_QDRANT_CLIENT_METHODS = json.loads(f.read())

WRAPPED_METHODS = QDRANT_CLIENT_METHODS + ASYNC_QDRANT_CLIENT_METHODS

MODULE = "qdrant_client"


class QdrantInstrumentor(BaseInstrumentor):
    """An instrumentor for Qdrant's client library."""

    def __init__(self, exception_logger=None):
        super().__init__()
        Config.exception_logger = exception_logger

    def instrumentation_dependencies(self) -> Collection[str]:
        return _instruments

    def _instrument(self, **kwargs):
        tracer_provider = kwargs.get("tracer_provider")
        tracer = get_tracer(__name__, __version__, tracer_provider)
        for wrapped_method in WRAPPED_METHODS:
            wrap_object = wrapped_method.get("object")
            wrap_method = wrapped_method.get("method")
            if getattr(qdrant_client, wrap_object, None):
                wrap_function_wrapper(
                    MODULE,
                    f"{wrap_object}.{wrap_method}",
                    _wrap(tracer, wrapped_method),
                )

    def _uninstrument(self, **kwargs):
        for wrapped_method in WRAPPED_METHODS:
            wrap_object = wrapped_method.get("object")
            unwrap(f"{MODULE}.{wrap_object}", wrapped_method.get("method"))
