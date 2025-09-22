import logging
import time
from opentelemetry import context as context_api
from opentelemetry.instrumentation.openai.shared import (
    _set_span_attribute,
    model_as_dict,
)
from opentelemetry.trace import SpanKind
from opentelemetry.instrumentation.utils import _SUPPRESS_INSTRUMENTATION_KEY

from opentelemetry.semconv_ai import SpanAttributes, LLMRequestTypeValues

from opentelemetry.instrumentation.openai.utils import _with_tracer_wrapper, dont_throw
from opentelemetry.instrumentation.openai.shared.config import Config

from openai._legacy_response import LegacyAPIResponse
from openai.types.beta.threads.run import Run

logger = logging.getLogger(__name__)

assistants = {}
runs = {}


@_with_tracer_wrapper
def assistants_create_wrapper(tracer, wrapped, instance, args, kwargs):
    if context_api.get_value(_SUPPRESS_INSTRUMENTATION_KEY):
        return wrapped(*args, **kwargs)

    response = wrapped(*args, **kwargs)

    assistants[response.id] = {
        "model": kwargs.get("model"),
        "instructions": kwargs.get("instructions"),
    }

    return response


@_with_tracer_wrapper
def runs_create_wrapper(tracer, wrapped, instance, args, kwargs):
    if context_api.get_value(_SUPPRESS_INSTRUMENTATION_KEY):
        return wrapped(*args, **kwargs)

    thread_id = kwargs.get("thread_id")
    instructions = kwargs.get("instructions")

    response = wrapped(*args, **kwargs)
    response_dict = model_as_dict(response)

    runs[thread_id] = {
        "start_time": time.time_ns(),
        "assistant_id": kwargs.get("assistant_id"),
        "instructions": instructions,
        "run_id": response_dict.get("id"),
    }

    return response


@_with_tracer_wrapper
def runs_retrieve_wrapper(tracer, wrapped, instance, args, kwargs):
    @dont_throw
    def process_response(response):
        if type(response) is LegacyAPIResponse:
            parsed_response = response.parse()
        else:
            parsed_response = response
        assert type(parsed_response) is Run

        if parsed_response.thread_id in runs:
            thread_id = parsed_response.thread_id
            runs[thread_id]["end_time"] = time.time_ns()
            if parsed_response.usage:
                runs[thread_id]["usage"] = parsed_response.usage

    if context_api.get_value(_SUPPRESS_INSTRUMENTATION_KEY):
        return wrapped(*args, **kwargs)

    response = wrapped(*args, **kwargs)
    process_response(response)

    return response


@_with_tracer_wrapper
def messages_list_wrapper(tracer, wrapped, instance, args, kwargs):
    if context_api.get_value(_SUPPRESS_INSTRUMENTATION_KEY):
        return wrapped(*args, **kwargs)

    id = kwargs.get("thread_id")

    response = wrapped(*args, **kwargs)

    response_dict = model_as_dict(response)
    if id not in runs:
        return response

    run = runs[id]
    messages = sorted(response_dict["data"], key=lambda x: x["created_at"])

    span = tracer.start_span(
        "openai.assistant.run",
        kind=SpanKind.CLIENT,
        attributes={SpanAttributes.LLM_REQUEST_TYPE: LLMRequestTypeValues.CHAT.value},
        start_time=run.get("start_time"),
    )

    prompt_index = 0
    if assistants.get(run["assistant_id"]) is not None or Config.enrich_assistant:
        if Config.enrich_assistant:
            assistant = model_as_dict(
                instance._client.beta.assistants.retrieve(run["assistant_id"])
            )
            assistants[run["assistant_id"]] = assistant
        else:
            assistant = assistants[run["assistant_id"]]

        _set_span_attribute(
            span,
            SpanAttributes.LLM_SYSTEM,
            "openai",
        )
        _set_span_attribute(
            span,
            SpanAttributes.LLM_REQUEST_MODEL,
            assistant["model"],
        )
        _set_span_attribute(
            span,
            SpanAttributes.LLM_RESPONSE_MODEL,
            assistant["model"],
        )
        _set_span_attribute(span, f"{SpanAttributes.LLM_PROMPTS}.{prompt_index}.role", "system")
        _set_span_attribute(
            span,
            f"{SpanAttributes.LLM_PROMPTS}.{prompt_index}.content",
            assistant["instructions"],
        )
        prompt_index += 1
    _set_span_attribute(span, f"{SpanAttributes.LLM_PROMPTS}.{prompt_index}.role", "system")
    _set_span_attribute(
        span, f"{SpanAttributes.LLM_PROMPTS}.{prompt_index}.content", run["instructions"]
    )
    prompt_index += 1

    completion_index = 0
    for msg in messages:
        prefix = f"{SpanAttributes.LLM_COMPLETIONS}.{completion_index}"
        content = msg.get("content")

        message_content = content[0].get("text").get("value")
        message_role = msg.get("role")
        if message_role in ["user", "system"]:
            _set_span_attribute(span, f"{SpanAttributes.LLM_PROMPTS}.{prompt_index}.role", message_role)
            _set_span_attribute(span, f"{SpanAttributes.LLM_PROMPTS}.{prompt_index}.content", message_content)
            prompt_index += 1
        else:
            _set_span_attribute(span, f"{prefix}.role", msg.get("role"))
            _set_span_attribute(span, f"{prefix}.content", message_content)
            _set_span_attribute(span, f"gen_ai.response.{completion_index}.id", msg.get("id"))
            completion_index += 1

    if run.get("usage"):
        usage_dict = model_as_dict(run.get("usage"))
        _set_span_attribute(
            span,
            SpanAttributes.LLM_USAGE_COMPLETION_TOKENS,
            usage_dict.get("completion_tokens"),
        )
        _set_span_attribute(
            span,
            SpanAttributes.LLM_USAGE_PROMPT_TOKENS,
            usage_dict.get("prompt_tokens"),
        )

    span.end(run.get("end_time"))

    return response


@_with_tracer_wrapper
def runs_create_and_stream_wrapper(tracer, wrapped, instance, args, kwargs):
    if context_api.get_value(_SUPPRESS_INSTRUMENTATION_KEY):
        return wrapped(*args, **kwargs)

    assistant_id = kwargs.get("assistant_id")
    instructions = kwargs.get("instructions")

    span = tracer.start_span(
        "openai.assistant.run_stream",
        kind=SpanKind.CLIENT,
        attributes={SpanAttributes.LLM_REQUEST_TYPE: LLMRequestTypeValues.CHAT.value},
    )

    i = 0
    if assistants.get(assistant_id) is not None or Config.enrich_assistant:
        if Config.enrich_assistant:
            assistant = model_as_dict(
                instance._client.beta.assistants.retrieve(assistant_id)
            )
            assistants[assistant_id] = assistant
        else:
            assistant = assistants[assistant_id]

        _set_span_attribute(
            span, SpanAttributes.LLM_REQUEST_MODEL, assistants[assistant_id]["model"]
        )
        _set_span_attribute(
            span,
            SpanAttributes.LLM_SYSTEM,
            "openai",
        )
        _set_span_attribute(
            span,
            SpanAttributes.LLM_RESPONSE_MODEL,
            assistants[assistant_id]["model"],
        )
        _set_span_attribute(span, f"{SpanAttributes.LLM_PROMPTS}.{i}.role", "system")
        _set_span_attribute(
            span,
            f"{SpanAttributes.LLM_PROMPTS}.{i}.content",
            assistants[assistant_id]["instructions"],
        )
        i += 1
    _set_span_attribute(span, f"{SpanAttributes.LLM_PROMPTS}.{i}.role", "system")
    _set_span_attribute(span, f"{SpanAttributes.LLM_PROMPTS}.{i}.content", instructions)

    from opentelemetry.instrumentation.openai.v1.event_handler_wrapper import (
        EventHandleWrapper,
    )

    kwargs["event_handler"] = EventHandleWrapper(
        original_handler=kwargs["event_handler"], span=span,
    )

    response = wrapped(*args, **kwargs)

    return response
