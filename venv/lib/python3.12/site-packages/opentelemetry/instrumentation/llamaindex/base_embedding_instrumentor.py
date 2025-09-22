from importlib.metadata import version as package_version, PackageNotFoundError

from wrapt import wrap_function_wrapper

from opentelemetry.instrumentation.llamaindex.utils import (
    _with_tracer_wrapper,
    start_as_current_span_async,
)
from opentelemetry.semconv_ai import SpanAttributes, TraceloopSpanKindValues

V9_MODULE_NAME = "llama_index.embeddings.base"
V10_MODULE_NAME = "llama_index.core.embeddings"
V10_LEGACY_MODULE_NAME = "llama_index.legacy.embeddings.base"

CLASS_NAME = "BaseEmbedding"
TASK_NAME = "get_query_embedding"


class BaseEmbeddingInstrumentor:
    def __init__(self, tracer):
        self._tracer = tracer

    def instrument(self):
        try:
            package_version("llama-index-core")
            self._instrument_module(V10_MODULE_NAME)
            self._instrument_module(V10_LEGACY_MODULE_NAME)

        except PackageNotFoundError:
            self._instrument_module(V9_MODULE_NAME)

    def _instrument_module(self, module_name):
        wrap_function_wrapper(
            module_name,
            f"{CLASS_NAME}.get_query_embedding",
            get_query_embedding_wrapper(self._tracer),
        )
        wrap_function_wrapper(
            module_name,
            f"{CLASS_NAME}.aget_query_embedding",
            aget_query_embedding_wrapper(self._tracer),
        )


@_with_tracer_wrapper
def get_query_embedding_wrapper(tracer, wrapped, instance, args, kwargs):
    with tracer.start_as_current_span(f"{TASK_NAME}.task") as span:
        span.set_attribute(
            SpanAttributes.TRACELOOP_SPAN_KIND,
            TraceloopSpanKindValues.TASK.value,
        )
        span.set_attribute(SpanAttributes.TRACELOOP_ENTITY_NAME, TASK_NAME)

        return wrapped(*args, **kwargs)


@_with_tracer_wrapper
async def aget_query_embedding_wrapper(tracer, wrapped, instance, args, kwargs):
    async with start_as_current_span_async(
        tracer=tracer, name=f"{TASK_NAME}.task"
    ) as span:
        span.set_attribute(
            SpanAttributes.TRACELOOP_SPAN_KIND,
            TraceloopSpanKindValues.TASK.value,
        )
        span.set_attribute(SpanAttributes.TRACELOOP_ENTITY_NAME, TASK_NAME)

        return await wrapped(*args, **kwargs)
