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

V9_MODULE_NAME = "llama_index.query_engine.retriever_query_engine"
V10_MODULE_NAME = "llama_index.core.query_engine.retriever_query_engine"
V10_LEGACY_MODULE_NAME = "llama_index.legacy.query_engine.retriever_query_engine"

CLASS_NAME = "RetrieverQueryEngine"
WORKFLOW_NAME = "llama_index_retriever_query"


class RetrieverQueryEngineInstrumentor:
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
            module_name, f"{CLASS_NAME}.query", query_wrapper(self._tracer)
        )
        wrap_function_wrapper(
            module_name, f"{CLASS_NAME}.aquery", aquery_wrapper(self._tracer)
        )


def set_workflow_context():
    attach(set_value("workflow_name", WORKFLOW_NAME))


@_with_tracer_wrapper
def query_wrapper(tracer, wrapped, instance, args, kwargs):
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
async def aquery_wrapper(tracer, wrapped, instance, args, kwargs):
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
