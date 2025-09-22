from importlib.metadata import version as package_version, PackageNotFoundError

from wrapt import wrap_function_wrapper

from opentelemetry.instrumentation.llamaindex.utils import (
    _with_tracer_wrapper,
    process_request,
    process_response,
    start_as_current_span_async,
)
from opentelemetry.semconv_ai import SpanAttributes, TraceloopSpanKindValues


TO_INSTRUMENT = [
    {
        "class": "AgentRunner",
        "v10_module": "llama_index.core.agent.runner.base",
        "v10_legacy_module": "llama_index.legacy.agent.runner.base",
    },
    {
        "class": "OpenAIAssistantAgent",
        "v10_module": "llama_index.agent.openai.openai_assistant_agent",
        "v10_legacy_module": "llama_index.legacy.agent.openai_assistant_agent",
    },
]


class BaseAgentInstrumentor:
    def __init__(self, tracer):
        self._tracer = tracer

    def instrument(self):
        for module in TO_INSTRUMENT:
            try:
                package_version("llama-index-core")
                self._instrument_module(module["v10_module"], module["class"])
                self._instrument_module(module["v10_legacy_module"], module["class"])

            except PackageNotFoundError:
                pass  # not supported before v10

    def _instrument_module(self, module_name, class_name):
        wrap_function_wrapper(
            module_name, f"{class_name}.chat", query_wrapper(self._tracer)
        )
        wrap_function_wrapper(
            module_name, f"{class_name}.achat", aquery_wrapper(self._tracer)
        )


@_with_tracer_wrapper
def query_wrapper(tracer, wrapped, instance, args, kwargs):
    name = instance.__class__.__name__
    with tracer.start_as_current_span(f"{name}.agent") as span:
        span.set_attribute(
            SpanAttributes.TRACELOOP_SPAN_KIND,
            TraceloopSpanKindValues.AGENT.value,
        )
        span.set_attribute(SpanAttributes.TRACELOOP_ENTITY_NAME, name)

        process_request(span, args, kwargs)
        res = wrapped(*args, **kwargs)
        process_response(span, res)
        return res


@_with_tracer_wrapper
async def aquery_wrapper(tracer, wrapped, instance, args, kwargs):
    name = instance.__class__.__name__
    async with start_as_current_span_async(tracer=tracer, name=f"{name}.agent") as span:
        span.set_attribute(
            SpanAttributes.TRACELOOP_SPAN_KIND,
            TraceloopSpanKindValues.AGENT.value,
        )
        span.set_attribute(SpanAttributes.TRACELOOP_ENTITY_NAME, name)

        process_request(span, args, kwargs)
        res = await wrapped(*args, **kwargs)
        process_response(span, res)
        return res
