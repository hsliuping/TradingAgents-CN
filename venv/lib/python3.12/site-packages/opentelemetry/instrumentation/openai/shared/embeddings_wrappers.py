import logging
import time

from opentelemetry import context as context_api
from opentelemetry.metrics import Counter, Histogram
from opentelemetry.semconv_ai import (
    SUPPRESS_LANGUAGE_MODEL_INSTRUMENTATION_KEY,
    SpanAttributes,
    LLMRequestTypeValues,
)

from opentelemetry.instrumentation.utils import _SUPPRESS_INSTRUMENTATION_KEY
from opentelemetry.instrumentation.openai.utils import (
    dont_throw,
    start_as_current_span_async,
    _with_embeddings_telemetry_wrapper,
)
from opentelemetry.instrumentation.openai.shared import (
    metric_shared_attributes,
    _set_client_attributes,
    _set_request_attributes,
    _set_span_attribute,
    _set_response_attributes,
    _token_type,
    should_send_prompts,
    model_as_dict,
    _get_openai_base_url,
    OPENAI_LLM_USAGE_TOKEN_TYPES,
    propagate_trace_context,
)

from opentelemetry.instrumentation.openai.shared.config import Config

from opentelemetry.instrumentation.openai.utils import is_openai_v1

from opentelemetry.trace import SpanKind
from opentelemetry.trace import Status, StatusCode

SPAN_NAME = "openai.embeddings"
LLM_REQUEST_TYPE = LLMRequestTypeValues.EMBEDDING

logger = logging.getLogger(__name__)


@_with_embeddings_telemetry_wrapper
def embeddings_wrapper(
    tracer,
    token_counter: Counter,
    vector_size_counter: Counter,
    duration_histogram: Histogram,
    exception_counter: Counter,
    wrapped,
    instance,
    args,
    kwargs,
):
    if context_api.get_value(_SUPPRESS_INSTRUMENTATION_KEY) or context_api.get_value(
        SUPPRESS_LANGUAGE_MODEL_INSTRUMENTATION_KEY
    ):
        return wrapped(*args, **kwargs)

    with tracer.start_as_current_span(
        name=SPAN_NAME,
        kind=SpanKind.CLIENT,
        attributes={SpanAttributes.LLM_REQUEST_TYPE: LLM_REQUEST_TYPE.value},
    ) as span:
        _handle_request(span, kwargs, instance)

        try:
            # record time for duration
            start_time = time.time()
            response = wrapped(*args, **kwargs)
            end_time = time.time()
        except Exception as e:  # pylint: disable=broad-except
            end_time = time.time()
            duration = end_time - start_time if "start_time" in locals() else 0
            attributes = {
                "error.type": e.__class__.__name__,
            }

            # if there are legal duration, record it
            if duration > 0 and duration_histogram:
                duration_histogram.record(duration, attributes=attributes)
            if exception_counter:
                exception_counter.add(1, attributes=attributes)

            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.end()

            raise e

        duration = end_time - start_time

        _handle_response(
            response,
            span,
            instance,
            token_counter,
            vector_size_counter,
            duration_histogram,
            duration,
        )

        return response


@_with_embeddings_telemetry_wrapper
async def aembeddings_wrapper(
    tracer,
    token_counter: Counter,
    vector_size_counter: Counter,
    duration_histogram: Histogram,
    exception_counter: Counter,
    wrapped,
    instance,
    args,
    kwargs,
):
    if context_api.get_value(_SUPPRESS_INSTRUMENTATION_KEY) or context_api.get_value(
        SUPPRESS_LANGUAGE_MODEL_INSTRUMENTATION_KEY
    ):
        return await wrapped(*args, **kwargs)

    async with start_as_current_span_async(
        tracer=tracer,
        name=SPAN_NAME,
        kind=SpanKind.CLIENT,
        attributes={SpanAttributes.LLM_REQUEST_TYPE: LLM_REQUEST_TYPE.value},
    ) as span:
        _handle_request(span, kwargs, instance)
        try:
            # record time for duration
            start_time = time.time()
            response = await wrapped(*args, **kwargs)
            end_time = time.time()
        except Exception as e:  # pylint: disable=broad-except
            end_time = time.time()
            duration = end_time - start_time if "start_time" in locals() else 0
            attributes = {
                "error.type": e.__class__.__name__,
            }

            # if there are legal duration, record it
            if duration > 0 and duration_histogram:
                duration_histogram.record(duration, attributes=attributes)
            if exception_counter:
                exception_counter.add(1, attributes=attributes)

            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.end()

            raise e

        duration = end_time - start_time
        _handle_response(
            response,
            span,
            instance,
            token_counter,
            vector_size_counter,
            duration_histogram,
            duration,
        )

        return response


@dont_throw
def _handle_request(span, kwargs, instance):
    _set_request_attributes(span, kwargs)
    if should_send_prompts():
        _set_prompts(span, kwargs.get("input"))
    _set_client_attributes(span, instance)
    if Config.enable_trace_context_propagation:
        propagate_trace_context(span, kwargs)


@dont_throw
def _handle_response(
    response,
    span,
    instance=None,
    token_counter=None,
    vector_size_counter=None,
    duration_histogram=None,
    duration=None,
):
    if is_openai_v1():
        response_dict = model_as_dict(response)
    else:
        response_dict = response
    # metrics record
    _set_embeddings_metrics(
        instance,
        token_counter,
        vector_size_counter,
        duration_histogram,
        response_dict,
        duration,
    )
    # span attributes
    _set_response_attributes(span, response_dict)


def _set_embeddings_metrics(
    instance,
    token_counter,
    vector_size_counter,
    duration_histogram,
    response_dict,
    duration,
):
    shared_attributes = metric_shared_attributes(
        response_model=response_dict.get("model") or None,
        operation="embeddings",
        server_address=_get_openai_base_url(instance),
    )

    # token count metrics
    usage = response_dict.get("usage")
    if usage and token_counter:
        for name, val in usage.items():
            if name in OPENAI_LLM_USAGE_TOKEN_TYPES:
                if val is None:
                    logging.error(f"Received None value for {name} in usage")
                    continue
                attributes_with_token_type = {
                    **shared_attributes,
                    SpanAttributes.LLM_TOKEN_TYPE: _token_type(name),
                }
                token_counter.record(val, attributes=attributes_with_token_type)

    # vec size metrics
    # should use counter for vector_size?
    vec_embedding = (response_dict.get("data") or [{}])[0].get("embedding", [])
    vec_size = len(vec_embedding)
    if vector_size_counter:
        vector_size_counter.add(vec_size, attributes=shared_attributes)

    # duration metrics
    if duration and isinstance(duration, (float, int)) and duration_histogram:
        duration_histogram.record(duration, attributes=shared_attributes)


def _set_prompts(span, prompt):
    if not span.is_recording() or not prompt:
        return

    if isinstance(prompt, list):
        for i, p in enumerate(prompt):
            _set_span_attribute(span, f"{SpanAttributes.LLM_PROMPTS}.{i}.content", p)
    else:
        _set_span_attribute(
            span,
            f"{SpanAttributes.LLM_PROMPTS}.0.content",
            prompt,
        )
