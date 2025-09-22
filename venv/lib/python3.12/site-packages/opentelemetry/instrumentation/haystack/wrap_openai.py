import logging

from opentelemetry import context as context_api
from opentelemetry.trace import SpanKind
from opentelemetry.trace.status import Status, StatusCode

from opentelemetry.instrumentation.utils import _SUPPRESS_INSTRUMENTATION_KEY
from opentelemetry.semconv_ai import SpanAttributes, LLMRequestTypeValues
from opentelemetry.instrumentation.haystack.utils import (
    dont_throw,
    with_tracer_wrapper,
    set_span_attribute,
)

logger = logging.getLogger(__name__)


@dont_throw
def _set_input_attributes(span, llm_request_type, kwargs):

    if llm_request_type == LLMRequestTypeValues.COMPLETION:
        set_span_attribute(
            span, f"{SpanAttributes.LLM_PROMPTS}.0.user", kwargs.get("prompt")
        )
    elif llm_request_type == LLMRequestTypeValues.CHAT:
        set_span_attribute(
            span,
            f"{SpanAttributes.LLM_PROMPTS}.0.user",
            [message.content for message in kwargs.get("messages")],
        )

    if "generation_kwargs" in kwargs and kwargs["generation_kwargs"] is not None:
        generation_kwargs = kwargs["generation_kwargs"]
        if "model" in generation_kwargs:
            set_span_attribute(
                span, SpanAttributes.LLM_REQUEST_MODEL, generation_kwargs["model"]
            )
        if "temperature" in generation_kwargs:
            set_span_attribute(
                span,
                SpanAttributes.LLM_REQUEST_TEMPERATURE,
                generation_kwargs["temperature"],
            )
        if "top_p" in generation_kwargs:
            set_span_attribute(
                span, SpanAttributes.LLM_REQUEST_TOP_P, generation_kwargs["top_p"]
            )
        if "frequency_penalty" in generation_kwargs:
            set_span_attribute(
                span,
                SpanAttributes.LLM_FREQUENCY_PENALTY,
                generation_kwargs["frequency_penalty"],
            )
        if "presence_penalty" in generation_kwargs:
            set_span_attribute(
                span,
                SpanAttributes.LLM_PRESENCE_PENALTY,
                generation_kwargs["presence_penalty"],
            )

    return


def _set_span_completions(span, llm_request_type, choices):
    if choices is None:
        return

    for index, message in enumerate(choices):
        prefix = f"{SpanAttributes.LLM_COMPLETIONS}.{index}"

        if llm_request_type == LLMRequestTypeValues.CHAT:
            if message is not None:
                set_span_attribute(span, f"{prefix}.role", "assistant")
                set_span_attribute(span, f"{prefix}.content", message)
        elif llm_request_type == LLMRequestTypeValues.COMPLETION:
            set_span_attribute(span, f"{prefix}.content", message)


@dont_throw
def _set_response_attributes(span, llm_request_type, response):
    _set_span_completions(span, llm_request_type, response)


def _llm_request_type_by_object(object_name):
    if object_name == "OpenAIGenerator":
        return LLMRequestTypeValues.COMPLETION
    elif object_name == "OpenAIChatGenerator":
        return LLMRequestTypeValues.CHAT
    else:
        return LLMRequestTypeValues.UNKNOWN


@with_tracer_wrapper
def wrap(tracer, to_wrap, wrapped, instance, args, kwargs):
    if context_api.get_value(_SUPPRESS_INSTRUMENTATION_KEY):
        return wrapped(*args, **kwargs)

    llm_request_type = _llm_request_type_by_object(to_wrap.get("object"))
    with tracer.start_as_current_span(
        (
            SpanAttributes.HAYSTACK_OPENAI_CHAT
            if llm_request_type == LLMRequestTypeValues.CHAT
            else SpanAttributes.HAYSTACK_OPENAI_COMPLETION
        ),
        kind=SpanKind.CLIENT,
        attributes={
            SpanAttributes.LLM_SYSTEM: "OpenAI",
            SpanAttributes.LLM_REQUEST_TYPE: llm_request_type.value,
        },
    ) as span:
        if span.is_recording():
            _set_input_attributes(span, llm_request_type, kwargs)

        response = wrapped(*args, **kwargs)

        if response:
            if span.is_recording():
                _set_response_attributes(span, llm_request_type, response)

                span.set_status(Status(StatusCode.OK))

        return response
