"""OpenTelemetry Bedrock instrumentation"""

from functools import partial, wraps
import json
import logging
import os
import time
from typing import Collection
from opentelemetry.instrumentation.bedrock.config import Config
from opentelemetry.instrumentation.bedrock.guardrail import (
    guardrail_handling,
    guardrail_converse,
)
from opentelemetry.instrumentation.bedrock.prompt_caching import prompt_caching_handling
from opentelemetry.instrumentation.bedrock.reusable_streaming_body import (
    ReusableStreamingBody,
)
from opentelemetry.instrumentation.bedrock.streaming_wrapper import StreamingWrapper
from opentelemetry.instrumentation.bedrock.utils import dont_throw
from opentelemetry.metrics import Counter, Histogram, Meter, get_meter
from wrapt import wrap_function_wrapper
import anthropic

from opentelemetry import context as context_api
from opentelemetry.trace import get_tracer, SpanKind

from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from opentelemetry.instrumentation.utils import (
    _SUPPRESS_INSTRUMENTATION_KEY,
    unwrap,
)

from opentelemetry.semconv._incubating.attributes.gen_ai_attributes import (
    GEN_AI_RESPONSE_ID,
)
from opentelemetry.semconv_ai import (
    SUPPRESS_LANGUAGE_MODEL_INSTRUMENTATION_KEY,
    SpanAttributes,
    LLMRequestTypeValues,
    Meters,
)

from opentelemetry.instrumentation.bedrock.version import __version__


class MetricParams:
    def __init__(
        self,
        token_histogram: Histogram,
        choice_counter: Counter,
        duration_histogram: Histogram,
        exception_counter: Counter,
        guardrail_activation: Counter,
        guardrail_latency_histogram: Histogram,
        guardrail_coverage: Counter,
        guardrail_sensitive_info: Counter,
        guardrail_topic: Counter,
        guardrail_content: Counter,
        guardrail_words: Counter,
        prompt_caching: Counter,
    ):
        self.vendor = ""
        self.model = ""
        self.is_stream = False
        self.token_histogram = token_histogram
        self.choice_counter = choice_counter
        self.duration_histogram = duration_histogram
        self.exception_counter = exception_counter
        self.guardrail_activation = guardrail_activation
        self.guardrail_latency_histogram = guardrail_latency_histogram
        self.guardrail_coverage = guardrail_coverage
        self.guardrail_sensitive_info = guardrail_sensitive_info
        self.guardrail_topic = guardrail_topic
        self.guardrail_content = guardrail_content
        self.guardrail_words = guardrail_words
        self.prompt_caching = prompt_caching
        self.start_time = time.time()


logger = logging.getLogger(__name__)

anthropic_client = anthropic.Anthropic()

_instruments = ("boto3 >= 1.28.57",)

WRAPPED_METHODS = [
    {
        "package": "botocore.client",
        "object": "ClientCreator",
        "method": "create_client",
    },
    {"package": "botocore.session", "object": "Session", "method": "create_client"},
]

_BEDROCK_INVOKE_SPAN_NAME = "bedrock.completion"
_BEDROCK_CONVERSE_SPAN_NAME = "bedrock.converse"


def should_send_prompts():
    return (
        os.getenv("TRACELOOP_TRACE_CONTENT") or "true"
    ).lower() == "true" or context_api.get_value("override_enable_content_tracing")


def is_metrics_enabled() -> bool:
    return (os.getenv("TRACELOOP_METRICS_ENABLED") or "true").lower() == "true"


def _set_span_attribute(span, name, value):
    if value is not None:
        if value != "":
            span.set_attribute(name, value)
    return


def _with_tracer_wrapper(func):
    """Helper for providing tracer for wrapper functions."""

    def _with_tracer(
        tracer,
        metric_params,
        to_wrap,
    ):
        def wrapper(wrapped, instance, args, kwargs):
            return func(
                tracer,
                metric_params,
                to_wrap,
                wrapped,
                instance,
                args,
                kwargs,
            )

        return wrapper

    return _with_tracer


@_with_tracer_wrapper
def _wrap(
    tracer,
    metric_params,
    to_wrap,
    wrapped,
    instance,
    args,
    kwargs,
):
    """Instruments and calls every function defined in TO_WRAP."""
    if context_api.get_value(_SUPPRESS_INSTRUMENTATION_KEY):
        return wrapped(*args, **kwargs)

    if kwargs.get("service_name") == "bedrock-runtime":
        try:
            start_time = time.time()
            metric_params.start_time = time.time()
            client = wrapped(*args, **kwargs)
            client.invoke_model = _instrumented_model_invoke(
                client.invoke_model, tracer, metric_params
            )
            client.invoke_model_with_response_stream = (
                _instrumented_model_invoke_with_response_stream(
                    client.invoke_model_with_response_stream, tracer, metric_params
                )
            )
            client.converse = _instrumented_converse(
                client.converse, tracer, metric_params
            )
            client.converse_stream = _instrumented_converse_stream(
                client.converse_stream, tracer, metric_params
            )
            return client
        except Exception as e:
            end_time = time.time()
            duration = end_time - start_time if "start_time" in locals() else 0

            attributes = {
                "error.type": e.__class__.__name__,
            }

            if duration > 0 and metric_params.duration_histogram:
                metric_params.duration_histogram.record(duration, attributes=attributes)
            if metric_params.exception_counter:
                metric_params.exception_counter.add(1, attributes=attributes)

            raise e

    return wrapped(*args, **kwargs)


def _instrumented_model_invoke(fn, tracer, metric_params):
    @wraps(fn)
    def with_instrumentation(*args, **kwargs):
        if context_api.get_value(SUPPRESS_LANGUAGE_MODEL_INSTRUMENTATION_KEY):
            return fn(*args, **kwargs)

        with tracer.start_as_current_span(
            _BEDROCK_INVOKE_SPAN_NAME, kind=SpanKind.CLIENT
        ) as span:
            response = fn(*args, **kwargs)

            if span.is_recording():
                _handle_call(span, kwargs, response, metric_params)

            return response

    return with_instrumentation


def _instrumented_model_invoke_with_response_stream(fn, tracer, metric_params):
    @wraps(fn)
    def with_instrumentation(*args, **kwargs):
        if context_api.get_value(SUPPRESS_LANGUAGE_MODEL_INSTRUMENTATION_KEY):
            return fn(*args, **kwargs)

        span = tracer.start_span(_BEDROCK_INVOKE_SPAN_NAME, kind=SpanKind.CLIENT)
        response = fn(*args, **kwargs)

        if span.is_recording():
            _handle_stream_call(span, kwargs, response, metric_params)

        return response

    return with_instrumentation


def _instrumented_converse(fn, tracer, metric_params):
    # see
    # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/bedrock-runtime/client/converse.html
    # for the request/response format
    @wraps(fn)
    def with_instrumentation(*args, **kwargs):
        if context_api.get_value(SUPPRESS_LANGUAGE_MODEL_INSTRUMENTATION_KEY):
            return fn(*args, **kwargs)

        with tracer.start_as_current_span(
            _BEDROCK_CONVERSE_SPAN_NAME, kind=SpanKind.CLIENT
        ) as span:
            response = fn(*args, **kwargs)
            _handle_converse(span, kwargs, response, metric_params)

            return response

    return with_instrumentation


def _instrumented_converse_stream(fn, tracer, metric_params):
    @wraps(fn)
    def with_instrumentation(*args, **kwargs):
        if context_api.get_value(SUPPRESS_LANGUAGE_MODEL_INSTRUMENTATION_KEY):
            return fn(*args, **kwargs)

        span = tracer.start_span(_BEDROCK_CONVERSE_SPAN_NAME, kind=SpanKind.CLIENT)
        response = fn(*args, **kwargs)
        if span.is_recording():
            _handle_converse_stream(span, kwargs, response, metric_params)

        return response

    return with_instrumentation


@dont_throw
def _handle_stream_call(span, kwargs, response, metric_params):

    (vendor, model) = _get_vendor_model(kwargs.get("modelId"))
    request_body = json.loads(kwargs.get("body"))

    headers = {}
    if "ResponseMetadata" in response:
        headers = response.get("ResponseMetadata").get("HTTPHeaders", {})

    @dont_throw
    def stream_done(response_body):

        metric_params.vendor = vendor
        metric_params.model = model
        metric_params.is_stream = True

        prompt_caching_handling(headers, vendor, model, metric_params)
        guardrail_handling(response_body, vendor, model, metric_params)

        _set_model_span_attributes(
            vendor, model, span, request_body, response_body, headers, metric_params
        )

        span.end()

    response["body"] = StreamingWrapper(
        response["body"], stream_done_callback=stream_done
    )


@dont_throw
def _handle_call(span, kwargs, response, metric_params):
    response["body"] = ReusableStreamingBody(
        response["body"]._raw_stream, response["body"]._content_length
    )
    request_body = json.loads(kwargs.get("body"))
    response_body = json.loads(response.get("body").read())
    headers = {}
    if "ResponseMetadata" in response:
        headers = response.get("ResponseMetadata").get("HTTPHeaders", {})

    (vendor, model) = _get_vendor_model(kwargs.get("modelId"))
    metric_params.vendor = vendor
    metric_params.model = model
    metric_params.is_stream = False

    prompt_caching_handling(headers, vendor, model, metric_params)
    guardrail_handling(response_body, vendor, model, metric_params)

    _set_model_span_attributes(
        vendor, model, span, request_body, response_body, headers, metric_params
    )


@dont_throw
def _handle_converse(span, kwargs, response, metric_params):
    (vendor, model) = _get_vendor_model(kwargs.get("modelId"))
    guardrail_converse(response, vendor, model, metric_params)

    _set_span_attribute(span, SpanAttributes.LLM_SYSTEM, vendor)
    _set_span_attribute(span, SpanAttributes.LLM_REQUEST_MODEL, model)
    _set_span_attribute(
        span, SpanAttributes.LLM_REQUEST_TYPE, LLMRequestTypeValues.CHAT.value
    )

    config = {}
    if "inferenceConfig" in kwargs:
        config = kwargs.get("inferenceConfig")

    _set_span_attribute(span, SpanAttributes.LLM_REQUEST_TOP_P, config.get("topP"))
    _set_span_attribute(
        span, SpanAttributes.LLM_REQUEST_TEMPERATURE, config.get("temperature")
    )
    _set_span_attribute(
        span, SpanAttributes.LLM_REQUEST_MAX_TOKENS, config.get("maxTokens")
    )

    _converse_usage_record(span, response, metric_params)

    if should_send_prompts():
        _report_converse_input_prompt(kwargs, span)

        if "output" in response:
            message = response["output"]["message"]
            _set_span_attribute(
                span, f"{SpanAttributes.LLM_COMPLETIONS}.0.role", message.get("role")
            )
            for idx, content in enumerate(message["content"]):
                _set_span_attribute(
                    span,
                    f"{SpanAttributes.LLM_COMPLETIONS}.{idx}.content",
                    content.get("text"),
                )


@dont_throw
def _handle_converse_stream(span, kwargs, response, metric_params):
    (vendor, model) = _get_vendor_model(kwargs.get("modelId"))

    _set_span_attribute(span, SpanAttributes.LLM_SYSTEM, vendor)
    _set_span_attribute(span, SpanAttributes.LLM_REQUEST_MODEL, model)
    _set_span_attribute(
        span, SpanAttributes.LLM_REQUEST_TYPE, LLMRequestTypeValues.CHAT.value
    )

    config = {}
    if "inferenceConfig" in kwargs:
        config = kwargs.get("inferenceConfig")

    _set_span_attribute(span, SpanAttributes.LLM_REQUEST_TOP_P, config.get("topP"))
    _set_span_attribute(
        span, SpanAttributes.LLM_REQUEST_TEMPERATURE, config.get("temperature")
    )
    _set_span_attribute(
        span, SpanAttributes.LLM_REQUEST_MAX_TOKENS, config.get("maxTokens")
    )

    if should_send_prompts():
        _report_converse_input_prompt(kwargs, span)

    stream = response.get("stream")
    if stream:

        def handler(func):
            def wrap(*args, **kwargs):
                response_msg = kwargs.pop("response_msg")
                span = kwargs.pop("span")
                event = func(*args, **kwargs)
                if "contentBlockDelta" in event:
                    response_msg.append(event["contentBlockDelta"]["delta"]["text"])
                elif "messageStart" in event:
                    if should_send_prompts():
                        role = event["messageStart"]["role"]
                        _set_span_attribute(
                            span, f"{SpanAttributes.LLM_COMPLETIONS}.0.role", role
                        )
                elif "metadata" in event:
                    # last message sent
                    guardrail_converse(event["metadata"], vendor, model, metric_params)
                    _converse_usage_record(span, event["metadata"], metric_params)
                    span.end()
                elif "messageStop" in event:
                    if should_send_prompts():
                        _set_span_attribute(
                            span,
                            f"{SpanAttributes.LLM_COMPLETIONS}.0.content",
                            "".join(response_msg),
                        )
                return event

            return partial(wrap, response_msg=[], span=span)

        stream._parse_event = handler(stream._parse_event)


def _get_vendor_model(modelId):
    # Docs:
    # https://docs.aws.amazon.com/bedrock/latest/userguide/inference-profiles-support.html#inference-profiles-support-system
    vendor = "imported_model"
    model = modelId

    if modelId is not None and modelId.startswith("arn"):
        components = modelId.split(":")
        if len(components) > 5:
            inf_profile = components[5].split("/")
            if len(inf_profile) == 2:
                if "." in inf_profile[1]:
                    (vendor, model) = _cross_region_check(inf_profile[1])
    elif modelId is not None and "." in modelId:
        (vendor, model) = _cross_region_check(modelId)

    return vendor, model


def _cross_region_check(value):
    prefixes = ["us", "us-gov", "eu", "apac"]
    if any(value.startswith(prefix + ".") for prefix in prefixes):
        parts = value.split(".")
        if len(parts) > 2:
            parts.pop(0)
        return parts[0], parts[1]
    else:
        (vendor, model) = value.split(".")
    return vendor, model


def _report_converse_input_prompt(kwargs, span):
    prompt_idx = 0
    if "system" in kwargs:
        for idx, prompt in enumerate(kwargs["system"]):
            prompt_idx = idx + 1
            _set_span_attribute(
                span, f"{SpanAttributes.LLM_PROMPTS}.{idx}.role", "system"
            )
            # TODO: add support for "image"
            _set_span_attribute(
                span,
                f"{SpanAttributes.LLM_PROMPTS}.{idx}.content",
                prompt.get("text"),
            )
    if "messages" in kwargs:
        for idx, prompt in enumerate(kwargs["messages"]):
            _set_span_attribute(
                span,
                f"{SpanAttributes.LLM_PROMPTS}.{prompt_idx+idx}.role",
                prompt.get("role"),
            )
            # TODO: here we stringify the object, consider moving these to events or prompt.{i}.content.{j}
            _set_span_attribute(
                span,
                f"{SpanAttributes.LLM_PROMPTS}.{prompt_idx+idx}.content",
                json.dumps(prompt.get("content", ""), default=str),
            )


def _converse_usage_record(span, response, metric_params):
    prompt_tokens = 0
    completion_tokens = 0
    if "usage" in response:
        if "inputTokens" in response["usage"]:
            prompt_tokens = response["usage"]["inputTokens"]
        if "outputTokens" in response["usage"]:
            completion_tokens = response["usage"]["outputTokens"]

    _record_usage_to_span(
        span,
        prompt_tokens,
        completion_tokens,
        metric_params,
    )


def _record_usage_to_span(span, prompt_tokens, completion_tokens, metric_params):
    _set_span_attribute(
        span,
        SpanAttributes.LLM_USAGE_PROMPT_TOKENS,
        prompt_tokens,
    )
    _set_span_attribute(
        span,
        SpanAttributes.LLM_USAGE_COMPLETION_TOKENS,
        completion_tokens,
    )
    _set_span_attribute(
        span,
        SpanAttributes.LLM_USAGE_TOTAL_TOKENS,
        prompt_tokens + completion_tokens,
    )

    metric_attributes = _metric_shared_attributes(
        metric_params.vendor, metric_params.model, metric_params.is_stream
    )

    if metric_params.duration_histogram:
        duration = time.time() - metric_params.start_time
        metric_params.duration_histogram.record(
            duration,
            attributes=metric_attributes,
        )

    if (
        metric_params.token_histogram
        and type(prompt_tokens) is int
        and prompt_tokens >= 0
    ):
        metric_params.token_histogram.record(
            prompt_tokens,
            attributes={
                **metric_attributes,
                SpanAttributes.LLM_TOKEN_TYPE: "input",
            },
        )
    if (
        metric_params.token_histogram
        and type(completion_tokens) is int
        and completion_tokens >= 0
    ):
        metric_params.token_histogram.record(
            completion_tokens,
            attributes={
                **metric_attributes,
                SpanAttributes.LLM_TOKEN_TYPE: "output",
            },
        )


def _metric_shared_attributes(
    response_vendor: str, response_model: str, is_streaming: bool = False
):
    return {
        "vendor": response_vendor,
        SpanAttributes.LLM_RESPONSE_MODEL: response_model,
        SpanAttributes.LLM_SYSTEM: "bedrock",
        "stream": is_streaming,
    }


def _set_model_span_attributes(
    vendor, model, span, request_body, response_body, headers, metric_params
):

    response_model = response_body.get("model")
    response_id = response_body.get("id")

    _set_span_attribute(span, SpanAttributes.LLM_SYSTEM, vendor)
    _set_span_attribute(span, SpanAttributes.LLM_REQUEST_MODEL, model)
    _set_span_attribute(span, SpanAttributes.LLM_RESPONSE_MODEL, response_model)
    _set_span_attribute(span, GEN_AI_RESPONSE_ID, response_id)

    if vendor == "cohere":
        _set_cohere_span_attributes(span, request_body, response_body, metric_params)
    elif vendor == "anthropic":
        if "prompt" in request_body:
            _set_anthropic_completion_span_attributes(
                span, request_body, response_body, metric_params
            )
        elif "messages" in request_body:
            _set_anthropic_messages_span_attributes(
                span, request_body, response_body, metric_params
            )
    elif vendor == "ai21":
        _set_ai21_span_attributes(span, request_body, response_body, metric_params)
    elif vendor == "meta":
        _set_llama_span_attributes(span, request_body, response_body, metric_params)
    elif vendor == "amazon":
        _set_amazon_span_attributes(
            span, request_body, response_body, headers, metric_params
        )
    elif vendor == "imported_model":
        _set_imported_model_span_attributes(span, request_body, response_body, metric_params)


def _set_cohere_span_attributes(span, request_body, response_body, metric_params):
    _set_span_attribute(
        span, SpanAttributes.LLM_REQUEST_TYPE, LLMRequestTypeValues.COMPLETION.value
    )
    _set_span_attribute(span, SpanAttributes.LLM_REQUEST_TOP_P, request_body.get("p"))
    _set_span_attribute(
        span, SpanAttributes.LLM_REQUEST_TEMPERATURE, request_body.get("temperature")
    )
    _set_span_attribute(
        span, SpanAttributes.LLM_REQUEST_MAX_TOKENS, request_body.get("max_tokens")
    )

    # based on contract at
    # https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-cohere-command-r-plus.html
    input_tokens = response_body.get("token_count", {}).get("prompt_tokens")
    output_tokens = response_body.get("token_count", {}).get("response_tokens")

    print("response_body", response_body)

    if input_tokens is None or output_tokens is None:
        meta = response_body.get("meta", {})
        billed_units = meta.get("billed_units", {})
        input_tokens = input_tokens or billed_units.get("input_tokens")
        output_tokens = output_tokens or billed_units.get("output_tokens")

    if input_tokens is not None and output_tokens is not None:
        _record_usage_to_span(
            span,
            input_tokens,
            output_tokens,
            metric_params,
        )

    if should_send_prompts():
        _set_span_attribute(
            span, f"{SpanAttributes.LLM_PROMPTS}.0.user", request_body.get("prompt")
        )

        for i, generation in enumerate(response_body.get("generations")):
            _set_span_attribute(
                span,
                f"{SpanAttributes.LLM_COMPLETIONS}.{i}.content",
                generation.get("text"),
            )


def _set_anthropic_completion_span_attributes(
    span, request_body, response_body, metric_params
):
    _set_span_attribute(
        span, SpanAttributes.LLM_REQUEST_TYPE, LLMRequestTypeValues.COMPLETION.value
    )
    _set_span_attribute(
        span, SpanAttributes.LLM_REQUEST_TOP_P, request_body.get("top_p")
    )
    _set_span_attribute(
        span, SpanAttributes.LLM_REQUEST_TEMPERATURE, request_body.get("temperature")
    )
    _set_span_attribute(
        span,
        SpanAttributes.LLM_REQUEST_MAX_TOKENS,
        request_body.get("max_tokens_to_sample"),
    )

    if (
        response_body.get("usage") is not None
        and response_body.get("usage").get("input_tokens") is not None
        and response_body.get("usage").get("output_tokens") is not None
    ):
        _record_usage_to_span(
            span,
            response_body.get("usage").get("input_tokens"),
            response_body.get("usage").get("output_tokens"),
            metric_params,
        )
    elif response_body.get("invocation_metrics") is not None:
        _record_usage_to_span(
            span,
            response_body.get("invocation_metrics").get("inputTokenCount"),
            response_body.get("invocation_metrics").get("outputTokenCount"),
            metric_params,
        )
    elif Config.enrich_token_usage:
        _record_usage_to_span(
            span,
            _count_anthropic_tokens([request_body.get("prompt")]),
            _count_anthropic_tokens([response_body.get("completion")]),
            metric_params,
        )

    if should_send_prompts():
        _set_span_attribute(
            span, f"{SpanAttributes.LLM_PROMPTS}.0.user", request_body.get("prompt")
        )
        _set_span_attribute(
            span,
            f"{SpanAttributes.LLM_COMPLETIONS}.0.content",
            response_body.get("completion"),
        )


def _set_anthropic_messages_span_attributes(
    span, request_body, response_body, metric_params
):
    _set_span_attribute(
        span, SpanAttributes.LLM_REQUEST_TYPE, LLMRequestTypeValues.CHAT.value
    )
    _set_span_attribute(
        span, SpanAttributes.LLM_REQUEST_TOP_P, request_body.get("top_p")
    )
    _set_span_attribute(
        span, SpanAttributes.LLM_REQUEST_TEMPERATURE, request_body.get("temperature")
    )
    _set_span_attribute(
        span,
        SpanAttributes.LLM_REQUEST_MAX_TOKENS,
        request_body.get("max_tokens"),
    )

    prompt_tokens = 0
    completion_tokens = 0
    if (
        response_body.get("usage") is not None
        and response_body.get("usage").get("input_tokens") is not None
        and response_body.get("usage").get("output_tokens") is not None
    ):
        prompt_tokens = response_body.get("usage").get("input_tokens")
        completion_tokens = response_body.get("usage").get("output_tokens")
        _record_usage_to_span(span, prompt_tokens, completion_tokens, metric_params)
    elif response_body.get("invocation_metrics") is not None:
        prompt_tokens = response_body.get("invocation_metrics").get("inputTokenCount")
        completion_tokens = response_body.get("invocation_metrics").get(
            "outputTokenCount"
        )
        _record_usage_to_span(span, prompt_tokens, completion_tokens, metric_params)
    elif Config.enrich_token_usage:
        messages = [message.get("content") for message in request_body.get("messages")]

        raw_messages = []
        for message in messages:
            if isinstance(message, str):
                raw_messages.append(message)
            else:
                raw_messages.extend([content.get("text") for content in message])
        prompt_tokens = _count_anthropic_tokens(raw_messages)
        completion_tokens = _count_anthropic_tokens(
            [content.get("text") for content in response_body.get("content")]
        )
        _record_usage_to_span(span, prompt_tokens, completion_tokens, metric_params)

    if should_send_prompts():
        for idx, message in enumerate(request_body.get("messages")):
            _set_span_attribute(
                span, f"{SpanAttributes.LLM_PROMPTS}.{idx}.role", message.get("role")
            )
            _set_span_attribute(
                span,
                f"{SpanAttributes.LLM_PROMPTS}.0.content",
                json.dumps(message.get("content")),
            )

        _set_span_attribute(
            span, f"{SpanAttributes.LLM_COMPLETIONS}.0.content", "assistant"
        )
        _set_span_attribute(
            span,
            f"{SpanAttributes.LLM_COMPLETIONS}.0.content",
            json.dumps(response_body.get("content")),
        )


def _count_anthropic_tokens(messages: list[str]):
    count = 0
    for message in messages:
        count += anthropic_client.count_tokens(text=message)
    return count


def _set_ai21_span_attributes(span, request_body, response_body, metric_params):
    _set_span_attribute(
        span, SpanAttributes.LLM_REQUEST_TYPE, LLMRequestTypeValues.COMPLETION.value
    )
    _set_span_attribute(
        span, SpanAttributes.LLM_REQUEST_TOP_P, request_body.get("topP")
    )
    _set_span_attribute(
        span, SpanAttributes.LLM_REQUEST_TEMPERATURE, request_body.get("temperature")
    )
    _set_span_attribute(
        span, SpanAttributes.LLM_REQUEST_MAX_TOKENS, request_body.get("maxTokens")
    )

    _record_usage_to_span(
        span,
        len(response_body.get("prompt").get("tokens")),
        len(response_body.get("completions")[0].get("data").get("tokens")),
        metric_params,
    )

    if should_send_prompts():
        _set_span_attribute(
            span, f"{SpanAttributes.LLM_PROMPTS}.0.user", request_body.get("prompt")
        )

        for i, completion in enumerate(response_body.get("completions")):
            _set_span_attribute(
                span,
                f"{SpanAttributes.LLM_COMPLETIONS}.{i}.content",
                completion.get("data").get("text"),
            )


def _set_llama_span_attributes(span, request_body, response_body, metric_params):
    _set_span_attribute(
        span, SpanAttributes.LLM_REQUEST_TYPE, LLMRequestTypeValues.COMPLETION.value
    )
    _set_span_attribute(
        span, SpanAttributes.LLM_REQUEST_TOP_P, request_body.get("top_p")
    )
    _set_span_attribute(
        span, SpanAttributes.LLM_REQUEST_TEMPERATURE, request_body.get("temperature")
    )
    _set_span_attribute(
        span, SpanAttributes.LLM_REQUEST_MAX_TOKENS, request_body.get("max_gen_len")
    )

    _record_usage_to_span(
        span,
        response_body.get("prompt_token_count"),
        response_body.get("generation_token_count"),
        metric_params,
    )

    if should_send_prompts():
        _set_span_attribute(
            span, f"{SpanAttributes.LLM_PROMPTS}.0.content", request_body.get("prompt")
        )
        _set_span_attribute(span, f"{SpanAttributes.LLM_PROMPTS}.0.role", "user")

        if response_body.get("generation"):
            _set_span_attribute(
                span, f"{SpanAttributes.LLM_COMPLETIONS}.0.role", "assistant"
            )
            _set_span_attribute(
                span,
                f"{SpanAttributes.LLM_COMPLETIONS}.0.content",
                response_body.get("generation"),
            )
        else:
            for i, generation in enumerate(response_body.get("generations")):
                _set_span_attribute(
                    span, f"{SpanAttributes.LLM_COMPLETIONS}.{i}.role", "assistant"
                )
                _set_span_attribute(
                    span, f"{SpanAttributes.LLM_COMPLETIONS}.{i}.content", generation
                )


def _set_amazon_span_attributes(
    span, request_body, response_body, headers, metric_params
):
    _set_span_attribute(
        span, SpanAttributes.LLM_REQUEST_TYPE, LLMRequestTypeValues.COMPLETION.value
    )

    if "textGenerationConfig" in request_body:
        config = request_body.get("textGenerationConfig", {})
        _set_span_attribute(span, SpanAttributes.LLM_REQUEST_TOP_P, config.get("topP"))
        _set_span_attribute(
            span, SpanAttributes.LLM_REQUEST_TEMPERATURE, config.get("temperature")
        )
        _set_span_attribute(
            span, SpanAttributes.LLM_REQUEST_MAX_TOKENS, config.get("maxTokenCount")
        )
    elif "inferenceConfig" in request_body:
        config = request_body.get("inferenceConfig", {})
        _set_span_attribute(span, SpanAttributes.LLM_REQUEST_TOP_P, config.get("topP"))
        _set_span_attribute(
            span, SpanAttributes.LLM_REQUEST_TEMPERATURE, config.get("temperature")
        )
        _set_span_attribute(
            span, SpanAttributes.LLM_REQUEST_MAX_TOKENS, config.get("maxTokens")
        )

    total_completion_tokens = 0
    total_prompt_tokens = 0
    if "results" in response_body:
        total_prompt_tokens = int(response_body.get("inputTextTokenCount", 0))
        for result in response_body.get("results"):
            if "tokenCount" in result:
                total_completion_tokens += int(result.get("tokenCount", 0))
            elif "totalOutputTextTokenCount" in result:
                total_completion_tokens += int(
                    result.get("totalOutputTextTokenCount", 0)
                )
    elif "usage" in response_body:
        total_prompt_tokens += int(response_body.get("inputTokens", 0))
        total_completion_tokens += int(
            headers.get("x-amzn-bedrock-output-token-count", 0)
        )
    # checks for Titan models
    if "inputTextTokenCount" in response_body:
        total_prompt_tokens = response_body.get("inputTextTokenCount")
    if "totalOutputTextTokenCount" in response_body:
        total_completion_tokens = response_body.get("totalOutputTextTokenCount")

    _record_usage_to_span(
        span,
        total_prompt_tokens,
        total_completion_tokens,
        metric_params,
    )

    if should_send_prompts():
        if "inputText" in request_body:
            _set_span_attribute(
                span,
                f"{SpanAttributes.LLM_PROMPTS}.0.user",
                request_body.get("inputText"),
            )
        else:
            prompt_idx = 0
            if "system" in request_body:
                for idx, prompt in enumerate(request_body["system"]):
                    prompt_idx = idx + 1
                    _set_span_attribute(
                        span, f"{SpanAttributes.LLM_PROMPTS}.{idx}.role", "system"
                    )
                    # TODO: add support for "image"
                    _set_span_attribute(
                        span,
                        f"{SpanAttributes.LLM_PROMPTS}.{idx}.content",
                        prompt.get("text"),
                    )
            for idx, prompt in enumerate(request_body["messages"]):
                _set_span_attribute(
                    span,
                    f"{SpanAttributes.LLM_PROMPTS}.{prompt_idx+idx}.role",
                    prompt.get("role"),
                )
                # TODO: here we stringify the object, consider moving these to events or prompt.{i}.content.{j}
                _set_span_attribute(
                    span,
                    f"{SpanAttributes.LLM_PROMPTS}.{prompt_idx+idx}.content",
                    json.dumps(prompt.get("content", ""), default=str),
                )

        if "results" in response_body:
            for i, result in enumerate(response_body.get("results")):
                _set_span_attribute(
                    span,
                    f"{SpanAttributes.LLM_COMPLETIONS}.{i}.content",
                    result.get("outputText"),
                )
        elif "outputText" in response_body:
            _set_span_attribute(
                span,
                f"{SpanAttributes.LLM_COMPLETIONS}.0.content",
                response_body.get("outputText"),
            )
        elif "output" in response_body:
            msgs = response_body.get("output").get("message", {}).get("content", [])
            for idx, msg in enumerate(msgs):
                _set_span_attribute(
                    span,
                    f"{SpanAttributes.LLM_COMPLETIONS}.{idx}.content",
                    msg.get("text"),
                )


def _set_imported_model_span_attributes(span, request_body, response_body, metric_params):
    _set_span_attribute(
        span, SpanAttributes.LLM_REQUEST_TYPE, LLMRequestTypeValues.COMPLETION.value
    )
    _set_span_attribute(
        span, SpanAttributes.LLM_REQUEST_TOP_P, request_body.get("topP")
    )
    _set_span_attribute(
        span, SpanAttributes.LLM_REQUEST_TEMPERATURE, request_body.get("temperature")
    )
    _set_span_attribute(
        span, SpanAttributes.LLM_REQUEST_MAX_TOKENS, request_body.get("max_tokens")
    )
    prompt_tokens = (
        response_body.get("usage", {}).get("prompt_tokens")
        if response_body.get("usage", {}).get("prompt_tokens") is not None
        else response_body.get("prompt_token_count")
    )
    completion_tokens = response_body.get("usage", {}).get(
        "completion_tokens"
    ) or response_body.get("generation_token_count")

    _record_usage_to_span(span, prompt_tokens, completion_tokens, metric_params, )

    if should_send_prompts():
        _set_span_attribute(
            span, f"{SpanAttributes.LLM_PROMPTS}.0.content", request_body.get("prompt")
        )
        _set_span_attribute(
                span, f"{SpanAttributes.LLM_COMPLETIONS}.0.content",
                response_body.get("generation"),
            )


class GuardrailMeters:
    LLM_BEDROCK_GUARDRAIL_ACTIVATION = "gen_ai.bedrock.guardrail.activation"
    LLM_BEDROCK_GUARDRAIL_LATENCY = "gen_ai.bedrock.guardrail.latency"
    LLM_BEDROCK_GUARDRAIL_COVERAGE = "gen_ai.bedrock.guardrail.coverage"
    LLM_BEDROCK_GUARDRAIL_SENSITIVE = "gen_ai.bedrock.guardrail.sensitive_info"
    LLM_BEDROCK_GUARDRAIL_TOPICS = "gen_ai.bedrock.guardrail.topics"
    LLM_BEDROCK_GUARDRAIL_CONTENT = "gen_ai.bedrock.guardrail.content"
    LLM_BEDROCK_GUARDRAIL_WORDS = "gen_ai.bedrock.guardrail.words"


class PromptCaching:
    # will be moved under the AI SemConv. Not namespaced since also OpenAI supports this.
    LLM_BEDROCK_PROMPT_CACHING = "gen_ai.prompt.caching"


def _create_metrics(meter: Meter):
    token_histogram = meter.create_histogram(
        name=Meters.LLM_TOKEN_USAGE,
        unit="token",
        description="Measures number of input and output tokens used",
    )

    choice_counter = meter.create_counter(
        name=Meters.LLM_GENERATION_CHOICES,
        unit="choice",
        description="Number of choices returned by chat completions call",
    )

    duration_histogram = meter.create_histogram(
        name=Meters.LLM_OPERATION_DURATION,
        unit="s",
        description="GenAI operation duration",
    )

    exception_counter = meter.create_counter(
        # TODO: will fix this in future as a consolidation for semantic convention
        name="llm.bedrock.completions.exceptions",
        unit="time",
        description="Number of exceptions occurred during chat completions",
    )

    # Guardrail metrics
    guardrail_activation = meter.create_counter(
        name=GuardrailMeters.LLM_BEDROCK_GUARDRAIL_ACTIVATION,
        unit="",
        description="Number of guardrail activation",
    )

    guardrail_latency_histogram = meter.create_histogram(
        name=GuardrailMeters.LLM_BEDROCK_GUARDRAIL_LATENCY,
        unit="ms",
        description="GenAI guardrail latency",
    )

    guardrail_coverage = meter.create_counter(
        name=GuardrailMeters.LLM_BEDROCK_GUARDRAIL_COVERAGE,
        unit="char",
        description="GenAI guardrail coverage",
    )

    guardrail_sensitive_info = meter.create_counter(
        name=GuardrailMeters.LLM_BEDROCK_GUARDRAIL_SENSITIVE,
        unit="",
        description="GenAI guardrail sensitive information protection",
    )

    guardrail_topic = meter.create_counter(
        name=GuardrailMeters.LLM_BEDROCK_GUARDRAIL_TOPICS,
        unit="",
        description="GenAI guardrail topics protection",
    )

    guardrail_content = meter.create_counter(
        name=GuardrailMeters.LLM_BEDROCK_GUARDRAIL_CONTENT,
        unit="",
        description="GenAI guardrail content filter protection",
    )

    guardrail_words = meter.create_counter(
        name=GuardrailMeters.LLM_BEDROCK_GUARDRAIL_WORDS,
        unit="",
        description="GenAI guardrail words filter protection",
    )

    # Prompt Caching
    prompt_caching = meter.create_counter(
        name=PromptCaching.LLM_BEDROCK_PROMPT_CACHING,
        unit="",
        description="Number of cached tokens",
    )

    return (
        token_histogram,
        choice_counter,
        duration_histogram,
        exception_counter,
        guardrail_activation,
        guardrail_latency_histogram,
        guardrail_coverage,
        guardrail_sensitive_info,
        guardrail_topic,
        guardrail_content,
        guardrail_words,
        prompt_caching,
    )


class BedrockInstrumentor(BaseInstrumentor):
    """An instrumentor for Bedrock's client library."""

    def __init__(self, enrich_token_usage: bool = False, exception_logger=None):
        super().__init__()
        Config.enrich_token_usage = enrich_token_usage
        Config.exception_logger = exception_logger

    def instrumentation_dependencies(self) -> Collection[str]:
        return _instruments

    def _instrument(self, **kwargs):
        tracer_provider = kwargs.get("tracer_provider")
        tracer = get_tracer(__name__, __version__, tracer_provider)

        # meter and counters are inited here
        meter_provider = kwargs.get("meter_provider")
        meter = get_meter(__name__, __version__, meter_provider)

        if is_metrics_enabled():
            (
                token_histogram,
                choice_counter,
                duration_histogram,
                exception_counter,
                guardrail_activation,
                guardrail_latency_histogram,
                guardrail_coverage,
                guardrail_sensitive_info,
                guardrail_topic,
                guardrail_content,
                guardrail_words,
                prompt_caching,
            ) = _create_metrics(meter)
        else:
            (
                token_histogram,
                choice_counter,
                duration_histogram,
                exception_counter,
                guardrail_activation,
                guardrail_latency_histogram,
                guardrail_coverage,
                guardrail_sensitive_info,
                guardrail_topic,
                guardrail_content,
                guardrail_words,
                prompt_caching,
            ) = (None, None, None, None, None, None, None, None, None, None, None, None)

        metric_params = MetricParams(
            token_histogram,
            choice_counter,
            duration_histogram,
            exception_counter,
            guardrail_activation,
            guardrail_latency_histogram,
            guardrail_coverage,
            guardrail_sensitive_info,
            guardrail_topic,
            guardrail_content,
            guardrail_words,
            prompt_caching,
        )

        for wrapped_method in WRAPPED_METHODS:
            wrap_package = wrapped_method.get("package")
            wrap_object = wrapped_method.get("object")
            wrap_method = wrapped_method.get("method")
            wrap_function_wrapper(
                wrap_package,
                f"{wrap_object}.{wrap_method}",
                _wrap(
                    tracer,
                    metric_params,
                    wrapped_method,
                ),
            )

    def _uninstrument(self, **kwargs):
        for wrapped_method in WRAPPED_METHODS:
            wrap_package = wrapped_method.get("package")
            wrap_object = wrapped_method.get("object")
            unwrap(
                f"{wrap_package}.{wrap_object}",
                wrapped_method.get("method"),
            )
