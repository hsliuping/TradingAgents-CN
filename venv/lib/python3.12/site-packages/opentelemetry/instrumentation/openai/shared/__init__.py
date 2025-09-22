import os
import openai
import json
import types
import logging

from importlib.metadata import version

from opentelemetry import context as context_api
from opentelemetry.trace.propagation import set_span_in_context
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from opentelemetry.instrumentation.openai.shared.config import Config
from opentelemetry.semconv._incubating.attributes.gen_ai_attributes import (
    GEN_AI_RESPONSE_ID,
)
from opentelemetry.semconv_ai import SpanAttributes
from opentelemetry.instrumentation.openai.utils import (
    dont_throw,
    is_openai_v1,
    should_record_stream_token_usage,
)

OPENAI_LLM_USAGE_TOKEN_TYPES = ["prompt_tokens", "completion_tokens"]
PROMPT_FILTER_KEY = "prompt_filter_results"
PROMPT_ERROR = "prompt_error"

_PYDANTIC_VERSION = version("pydantic")

# tiktoken encodings map for different model, key is model_name, value is tiktoken encoding
tiktoken_encodings = {}

logger = logging.getLogger(__name__)


def should_send_prompts():
    return (
        os.getenv("TRACELOOP_TRACE_CONTENT") or "true"
    ).lower() == "true" or context_api.get_value("override_enable_content_tracing")


def _set_span_attribute(span, name, value):
    if value is None or value == "":
        return

    if hasattr(openai, "NOT_GIVEN") and value == openai.NOT_GIVEN:
        return

    span.set_attribute(name, value)


def _set_client_attributes(span, instance):
    if not span.is_recording():
        return

    if not is_openai_v1():
        return

    client = instance._client  # pylint: disable=protected-access
    if isinstance(client, (openai.AsyncOpenAI, openai.OpenAI)):
        _set_span_attribute(
            span, SpanAttributes.LLM_OPENAI_API_BASE, str(client.base_url)
        )
    if isinstance(client, (openai.AsyncAzureOpenAI, openai.AzureOpenAI)):
        _set_span_attribute(
            span, SpanAttributes.LLM_OPENAI_API_VERSION, client._api_version
        )  # pylint: disable=protected-access


def _set_api_attributes(span):
    if not span.is_recording():
        return

    if is_openai_v1():
        return

    base_url = openai.base_url if hasattr(openai, "base_url") else openai.api_base

    _set_span_attribute(span, SpanAttributes.LLM_OPENAI_API_BASE, base_url)
    _set_span_attribute(span, SpanAttributes.LLM_OPENAI_API_TYPE, openai.api_type)
    _set_span_attribute(span, SpanAttributes.LLM_OPENAI_API_VERSION, openai.api_version)

    return


def _set_functions_attributes(span, functions):
    if not functions:
        return

    for i, function in enumerate(functions):
        prefix = f"{SpanAttributes.LLM_REQUEST_FUNCTIONS}.{i}"
        _set_span_attribute(span, f"{prefix}.name", function.get("name"))
        _set_span_attribute(span, f"{prefix}.description", function.get("description"))
        _set_span_attribute(
            span, f"{prefix}.parameters", json.dumps(function.get("parameters"))
        )


def set_tools_attributes(span, tools):
    if not tools:
        return

    for i, tool in enumerate(tools):
        function = tool.get("function")
        if not function:
            continue

        prefix = f"{SpanAttributes.LLM_REQUEST_FUNCTIONS}.{i}"
        _set_span_attribute(span, f"{prefix}.name", function.get("name"))
        _set_span_attribute(span, f"{prefix}.description", function.get("description"))
        _set_span_attribute(
            span, f"{prefix}.parameters", json.dumps(function.get("parameters"))
        )


def _set_request_attributes(span, kwargs):
    if not span.is_recording():
        return

    _set_api_attributes(span)
    _set_span_attribute(span, SpanAttributes.LLM_SYSTEM, "OpenAI")
    _set_span_attribute(span, SpanAttributes.LLM_REQUEST_MODEL, kwargs.get("model"))
    _set_span_attribute(
        span, SpanAttributes.LLM_REQUEST_MAX_TOKENS, kwargs.get("max_tokens")
    )
    _set_span_attribute(
        span, SpanAttributes.LLM_REQUEST_TEMPERATURE, kwargs.get("temperature")
    )
    _set_span_attribute(span, SpanAttributes.LLM_REQUEST_TOP_P, kwargs.get("top_p"))
    _set_span_attribute(
        span, SpanAttributes.LLM_FREQUENCY_PENALTY, kwargs.get("frequency_penalty")
    )
    _set_span_attribute(
        span, SpanAttributes.LLM_PRESENCE_PENALTY, kwargs.get("presence_penalty")
    )
    _set_span_attribute(span, SpanAttributes.LLM_USER, kwargs.get("user"))
    _set_span_attribute(span, SpanAttributes.LLM_HEADERS, str(kwargs.get("headers")))
    # The new OpenAI SDK removed the `headers` and create new field called `extra_headers`
    if kwargs.get("extra_headers") is not None:
        _set_span_attribute(
            span, SpanAttributes.LLM_HEADERS, str(kwargs.get("extra_headers"))
        )
    _set_span_attribute(
        span, SpanAttributes.LLM_IS_STREAMING, kwargs.get("stream") or False
    )


@dont_throw
def _set_response_attributes(span, response):
    if not span.is_recording():
        return

    if "error" in response:
        _set_span_attribute(
            span,
            f"{SpanAttributes.LLM_PROMPTS}.{PROMPT_ERROR}",
            json.dumps(response.get("error")),
        )
        return

    _set_span_attribute(span, SpanAttributes.LLM_RESPONSE_MODEL, response.get("model"))
    _set_span_attribute(span, GEN_AI_RESPONSE_ID, response.get("id"))

    _set_span_attribute(
        span,
        SpanAttributes.LLM_OPENAI_RESPONSE_SYSTEM_FINGERPRINT,
        response.get("system_fingerprint"),
    )
    _log_prompt_filter(span, response)
    usage = response.get("usage")
    if not usage:
        return

    if is_openai_v1() and not isinstance(usage, dict):
        usage = usage.__dict__

    _set_span_attribute(
        span, SpanAttributes.LLM_USAGE_TOTAL_TOKENS, usage.get("total_tokens")
    )
    _set_span_attribute(
        span,
        SpanAttributes.LLM_USAGE_COMPLETION_TOKENS,
        usage.get("completion_tokens"),
    )
    _set_span_attribute(
        span, SpanAttributes.LLM_USAGE_PROMPT_TOKENS, usage.get("prompt_tokens")
    )
    prompt_tokens_details = dict(usage.get("prompt_tokens_details", {}))
    _set_span_attribute(
        span, SpanAttributes.LLM_USAGE_CACHE_READ_INPUT_TOKENS, prompt_tokens_details.get("cached_tokens", 0)
    )
    return


def _log_prompt_filter(span, response_dict):
    if response_dict.get("prompt_filter_results"):
        _set_span_attribute(
            span,
            f"{SpanAttributes.LLM_PROMPTS}.{PROMPT_FILTER_KEY}",
            json.dumps(response_dict.get("prompt_filter_results")),
        )


@dont_throw
def _set_span_stream_usage(span, prompt_tokens, completion_tokens):
    if not span.is_recording():
        return

    if type(completion_tokens) is int and completion_tokens >= 0:
        _set_span_attribute(
            span, SpanAttributes.LLM_USAGE_COMPLETION_TOKENS, completion_tokens
        )

    if type(prompt_tokens) is int and prompt_tokens >= 0:
        _set_span_attribute(span, SpanAttributes.LLM_USAGE_PROMPT_TOKENS, prompt_tokens)

    if (
        type(prompt_tokens) is int
        and type(completion_tokens) is int
        and completion_tokens + prompt_tokens >= 0
    ):
        _set_span_attribute(
            span,
            SpanAttributes.LLM_USAGE_TOTAL_TOKENS,
            completion_tokens + prompt_tokens,
        )


def _get_openai_base_url(instance):
    if hasattr(instance, "_client"):
        client = instance._client  # pylint: disable=protected-access
        if isinstance(client, (openai.AsyncOpenAI, openai.OpenAI)):
            return str(client.base_url)

    return ""


def is_streaming_response(response):
    if is_openai_v1():
        return isinstance(response, openai.Stream) or isinstance(
            response, openai.AsyncStream
        )

    return isinstance(response, types.GeneratorType) or isinstance(
        response, types.AsyncGeneratorType
    )


def model_as_dict(model):
    if isinstance(model, dict):
        return model
    if _PYDANTIC_VERSION < "2.0.0":
        return model.dict()
    if hasattr(model, "model_dump"):
        return model.model_dump()
    elif hasattr(model, "parse"):  # Raw API response
        return model_as_dict(model.parse())
    else:
        return model


def get_token_count_from_string(string: str, model_name: str):
    if not should_record_stream_token_usage():
        return None

    import tiktoken

    if tiktoken_encodings.get(model_name) is None:
        try:
            encoding = tiktoken.encoding_for_model(model_name)
        except KeyError as ex:
            # no such model_name in tiktoken
            logger.warning(
                f"Failed to get tiktoken encoding for model_name {model_name}, error: {str(ex)}"
            )
            return None

        tiktoken_encodings[model_name] = encoding
    else:
        encoding = tiktoken_encodings.get(model_name)

    token_count = len(encoding.encode(string))
    return token_count


def _token_type(token_type: str):
    if token_type == "prompt_tokens":
        return "input"
    elif token_type == "completion_tokens":
        return "output"

    return None


def metric_shared_attributes(
    response_model: str, operation: str, server_address: str, is_streaming: bool = False
):
    attributes = Config.get_common_metrics_attributes()

    return {
        **attributes,
        SpanAttributes.LLM_SYSTEM: "openai",
        SpanAttributes.LLM_RESPONSE_MODEL: response_model,
        "gen_ai.operation.name": operation,
        "server.address": server_address,
        "stream": is_streaming,
    }


def propagate_trace_context(span, kwargs):
    if is_openai_v1():
        extra_headers = kwargs.get("extra_headers", {})
        ctx = set_span_in_context(span)
        TraceContextTextMapPropagator().inject(extra_headers, context=ctx)
        kwargs["extra_headers"] = extra_headers
    else:
        headers = kwargs.get("headers", {})
        ctx = set_span_in_context(span)
        TraceContextTextMapPropagator().inject(headers, context=ctx)
        kwargs["headers"] = headers
