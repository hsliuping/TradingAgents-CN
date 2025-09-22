import logging
from opentelemetry import context as context_api
from opentelemetry.context import attach, set_value
from opentelemetry.instrumentation.utils import (
    _SUPPRESS_INSTRUMENTATION_KEY,
)
from opentelemetry.instrumentation.haystack.utils import (
    with_tracer_wrapper,
    process_request,
    process_response,
)
from opentelemetry.semconv_ai import SpanAttributes, TraceloopSpanKindValues

logger = logging.getLogger(__name__)


@with_tracer_wrapper
def wrap(tracer, to_wrap, wrapped, instance, args, kwargs):
    if context_api.get_value(_SUPPRESS_INSTRUMENTATION_KEY):
        return wrapped(*args, **kwargs)
    name = "haystack_pipeline"
    attach(set_value("workflow_name", name))
    with tracer.start_as_current_span(f"{name}.workflow") as span:
        span.set_attribute(
            SpanAttributes.TRACELOOP_SPAN_KIND,
            TraceloopSpanKindValues.WORKFLOW.value,
        )
        span.set_attribute(SpanAttributes.TRACELOOP_ENTITY_NAME, name)
        process_request(span, args, kwargs)
        response = wrapped(*args, **kwargs)
        process_response(span, response)

    return response
