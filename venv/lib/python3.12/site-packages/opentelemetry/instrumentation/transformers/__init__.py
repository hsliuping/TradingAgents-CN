"""OpenTelemetry transformers instrumentation"""

import logging
from typing import Collection
from opentelemetry.instrumentation.transformers.config import Config
from wrapt import wrap_function_wrapper

from opentelemetry.trace import get_tracer

from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from opentelemetry.instrumentation.utils import unwrap

from opentelemetry.instrumentation.transformers.text_generation_pipeline_wrapper import (
    text_generation_pipeline_wrapper,
)
from opentelemetry.instrumentation.transformers.version import __version__

logger = logging.getLogger(__name__)

_instruments = ("transformers >= 4.0",)

WRAPPED_METHODS = [
    {
        "package": "transformers",
        "object": "TextGenerationPipeline",
        "method": "__call__",
        "span_name": "transformers_text_generation_pipeline.call",
        "wrapper": text_generation_pipeline_wrapper,
    }
]


class TransformersInstrumentor(BaseInstrumentor):
    """An instrumentor for transformers library."""

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
            wrapper = wrapped_method.get("wrapper")
            wrap_function_wrapper(
                wrap_package,
                f"{wrap_object}.{wrap_method}" if wrap_object else wrap_method,
                wrapper(tracer, wrapped_method),
            )

    def _uninstrument(self, **kwargs):
        for wrapped_method in WRAPPED_METHODS:
            wrap_package = wrapped_method.get("package")
            wrap_object = wrapped_method.get("object")
            wrap_method = wrapped_method.get("method")
            unwrap(
                f"{wrap_package}.{wrap_object}" if wrap_object else wrap_package,
                wrap_method,
            )
