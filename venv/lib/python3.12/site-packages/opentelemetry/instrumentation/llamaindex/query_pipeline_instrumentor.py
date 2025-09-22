from importlib.metadata import version as package_version, PackageNotFoundError

from wrapt import wrap_function_wrapper
from opentelemetry.context import attach, set_value

from opentelemetry.instrumentation.llamaindex.utils import (
    _with_tracer_wrapper,
    process_request,
    process_response,
    start_as_current_span_async,
)
from opentelemetry.semconv_ai import SpanAttributes, TraceloopSpanKindValues

V10_MODULE_NAME = "llama_index.core.query_pipeline.query"
V10_LEGACY_MODULE_NAME = "llama_index.legacy.query_pipeline.query"

CLASS_NAME = "QueryPipeline"
WORKFLOW_NAME = "llama_index_query_pipeline"


class QueryPipelineInstrumentor:
    def __init__(self, tracer):
        self._tracer = tracer

    def instrument(self):
        try:
            package_version("llama-index-core")
            self._instrument_module(V10_MODULE_NAME)
            self._instrument_module(V10_LEGACY_MODULE_NAME)

        except PackageNotFoundError:
            pass  # not supported before v10

    def _instrument_module(self, module_name):
        wrap_function_wrapper(
            module_name, f"{CLASS_NAME}.run", run_wrapper(self._tracer)
        )
        wrap_function_wrapper(
            module_name, f"{CLASS_NAME}.arun", arun_wrapper(self._tracer)
        )


def set_workflow_context():
    attach(set_value("workflow_name", WORKFLOW_NAME))


@_with_tracer_wrapper
def run_wrapper(tracer, wrapped, instance, args, kwargs):
    set_workflow_context()

    with tracer.start_as_current_span(f"{WORKFLOW_NAME}.workflow") as span:
        span.set_attribute(
            SpanAttributes.TRACELOOP_SPAN_KIND,
            TraceloopSpanKindValues.WORKFLOW.value,
        )
        span.set_attribute(SpanAttributes.TRACELOOP_ENTITY_NAME, WORKFLOW_NAME)

        process_request(span, args, kwargs)
        res = wrapped(*args, **kwargs)
        process_response(span, res)
        return res


@_with_tracer_wrapper
async def arun_wrapper(tracer, wrapped, instance, args, kwargs):
    set_workflow_context()

    async with start_as_current_span_async(
        tracer=tracer, name=f"{WORKFLOW_NAME}.workflow"
    ) as span:
        span.set_attribute(
            SpanAttributes.TRACELOOP_SPAN_KIND,
            TraceloopSpanKindValues.WORKFLOW.value,
        )
        span.set_attribute(SpanAttributes.TRACELOOP_ENTITY_NAME, WORKFLOW_NAME)

        process_request(span, args, kwargs)
        res = await wrapped(*args, **kwargs)
        process_response(span, res)
        return res
