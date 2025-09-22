from importlib.metadata import version as package_version, PackageNotFoundError

from wrapt import wrap_function_wrapper

from opentelemetry.instrumentation.llamaindex.utils import (
    _with_tracer_wrapper,
    process_request,
    process_response,
    start_as_current_span_async,
)
from opentelemetry.semconv_ai import SpanAttributes, TraceloopSpanKindValues

V9_MODULE_NAME = "llama_index.response_synthesizers"
V10_MODULE_NAME = "llama_index.core.response_synthesizers"
V10_LEGACY_MODULE_NAME = "llama_index.legacy.response_synthesizers.base"

CLASS_NAME = "BaseSynthesizer"
TASK_NAME = "synthesize"


class BaseSynthesizerInstrumentor:
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
            module_name, f"{CLASS_NAME}.synthesize", synthesize_wrapper(self._tracer)
        )
        wrap_function_wrapper(
            module_name, f"{CLASS_NAME}.asynthesize", asynthesize_wrapper(self._tracer)
        )


@_with_tracer_wrapper
def synthesize_wrapper(tracer, wrapped, instance, args, kwargs):
    with tracer.start_as_current_span(f"{TASK_NAME}.task") as span:
        span.set_attribute(
            SpanAttributes.TRACELOOP_SPAN_KIND,
            TraceloopSpanKindValues.TASK.value,
        )
        span.set_attribute(SpanAttributes.TRACELOOP_ENTITY_NAME, TASK_NAME)

        process_request(span, args, kwargs)
        res = wrapped(*args, **kwargs)
        process_response(span, res)
        return res


@_with_tracer_wrapper
async def asynthesize_wrapper(tracer, wrapped, instance, args, kwargs):
    async with start_as_current_span_async(
        tracer=tracer, name=f"{TASK_NAME}.task"
    ) as span:
        span.set_attribute(
            SpanAttributes.TRACELOOP_SPAN_KIND,
            TraceloopSpanKindValues.TASK.value,
        )
        span.set_attribute(SpanAttributes.TRACELOOP_ENTITY_NAME, TASK_NAME)

        process_request(span, args, kwargs)
        res = await wrapped(*args, **kwargs)
        process_response(span, res)
        return res
