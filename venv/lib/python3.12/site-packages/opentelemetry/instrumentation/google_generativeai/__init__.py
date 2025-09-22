"""OpenTelemetry Google Generative AI API instrumentation"""

import logging
import os
import types
from typing import Collection
from opentelemetry.instrumentation.google_generativeai.config import Config
from opentelemetry.instrumentation.google_generativeai.utils import dont_throw, is_package_installed
from wrapt import wrap_function_wrapper

from opentelemetry import context as context_api
from opentelemetry.trace import get_tracer, SpanKind
from opentelemetry.trace.status import Status, StatusCode

from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from opentelemetry.instrumentation.utils import _SUPPRESS_INSTRUMENTATION_KEY, unwrap

from opentelemetry.semconv_ai import (
    SUPPRESS_LANGUAGE_MODEL_INSTRUMENTATION_KEY,
    SpanAttributes,
    LLMRequestTypeValues,
)
from opentelemetry.instrumentation.google_generativeai.version import __version__

logger = logging.getLogger(__name__)

LEGACY_WRAPPED_METHODS = [
    {
        "package": "google.generativeai.generative_models",
        "object": "GenerativeModel",
        "method": "generate_content",
        "span_name": "gemini.generate_content",
    },
    {
        "package": "google.generativeai.generative_models",
        "object": "GenerativeModel",
        "method": "generate_content_async",
        "span_name": "gemini.generate_content_async",
    },
]

WRAPPED_METHODS = [
    {
        "package": "google.genai.models",
        "object": "Models",
        "method": "generate_content",
        "span_name": "gemini.generate_content",
    },
    {
        "package": "google.genai.models",
        "object": "AsyncModels",
        "method": "generate_content",
        "span_name": "gemini.generate_content",
    },
]


def should_send_prompts():
    return (
        os.getenv("TRACELOOP_TRACE_CONTENT") or "true"
    ).lower() == "true" or context_api.get_value("override_enable_content_tracing")


def is_streaming_response(response):
    return isinstance(response, types.GeneratorType)


def is_async_streaming_response(response):
    return isinstance(response, types.AsyncGeneratorType)


def _set_span_attribute(span, name, value):
    if value is not None:
        if value != "":
            span.set_attribute(name, value)
    return


def _set_input_attributes(span, args, kwargs, llm_model):
    if not should_send_prompts():
        return

    if "contents" in kwargs:
        contents = kwargs["contents"]
        if isinstance(contents, str):
            _set_span_attribute(
                span,
                f"{SpanAttributes.LLM_PROMPTS}.0.content",
                contents,
            )
            _set_span_attribute(
                span,
                f"{SpanAttributes.LLM_PROMPTS}.0.role",
                "user",
            )
        elif isinstance(contents, list):
            for i, content in enumerate(contents):
                if hasattr(content, "parts"):
                    for part in content.parts:
                        if hasattr(part, "text"):
                            _set_span_attribute(
                                span,
                                f"{SpanAttributes.LLM_PROMPTS}.{i}.content",
                                part.text,
                            )
                            _set_span_attribute(
                                span,
                                f"{SpanAttributes.LLM_PROMPTS}.{i}.role",
                                getattr(content, "role", "user"),
                            )
    elif args and len(args) > 0:
        prompt = ""
        for arg in args:
            if isinstance(arg, str):
                prompt = f"{prompt}{arg}\n"
            elif isinstance(arg, list):
                for subarg in arg:
                    prompt = f"{prompt}{subarg}\n"
        if prompt:
            _set_span_attribute(
                span,
                f"{SpanAttributes.LLM_PROMPTS}.0.content",
                prompt,
            )
            _set_span_attribute(
                span,
                f"{SpanAttributes.LLM_PROMPTS}.0.role",
                "user",
            )
    elif "prompt" in kwargs:
        _set_span_attribute(
            span,
            f"{SpanAttributes.LLM_PROMPTS}.0.content",
            kwargs["prompt"],
        )
        _set_span_attribute(
            span,
            f"{SpanAttributes.LLM_PROMPTS}.0.role",
            "user",
        )

    _set_span_attribute(span, SpanAttributes.LLM_REQUEST_MODEL, llm_model)
    _set_span_attribute(
        span, SpanAttributes.LLM_REQUEST_TEMPERATURE, kwargs.get("temperature")
    )
    _set_span_attribute(
        span, SpanAttributes.LLM_REQUEST_MAX_TOKENS, kwargs.get("max_output_tokens")
    )
    _set_span_attribute(span, SpanAttributes.LLM_REQUEST_TOP_P, kwargs.get("top_p"))
    _set_span_attribute(span, SpanAttributes.LLM_TOP_K, kwargs.get("top_k"))
    _set_span_attribute(
        span, SpanAttributes.LLM_PRESENCE_PENALTY, kwargs.get("presence_penalty")
    )
    _set_span_attribute(
        span, SpanAttributes.LLM_FREQUENCY_PENALTY, kwargs.get("frequency_penalty")
    )

    return


@dont_throw
def _set_response_attributes(span, response, llm_model):
    _set_span_attribute(span, SpanAttributes.LLM_RESPONSE_MODEL, llm_model)

    if hasattr(response, "usage_metadata"):
        _set_span_attribute(
            span,
            SpanAttributes.LLM_USAGE_TOTAL_TOKENS,
            response.usage_metadata.total_token_count,
        )
        _set_span_attribute(
            span,
            SpanAttributes.LLM_USAGE_COMPLETION_TOKENS,
            response.usage_metadata.candidates_token_count,
        )
        _set_span_attribute(
            span,
            SpanAttributes.LLM_USAGE_PROMPT_TOKENS,
            response.usage_metadata.prompt_token_count,
        )

        if isinstance(response.text, list):
            for index, item in enumerate(response):
                prefix = f"{SpanAttributes.LLM_COMPLETIONS}.{index}"
                _set_span_attribute(span, f"{prefix}.content", item.text)
                _set_span_attribute(span, f"{prefix}.role", "assistant")
        elif isinstance(response.text, str):
            _set_span_attribute(
                span, f"{SpanAttributes.LLM_COMPLETIONS}.0.content", response.text
            )
            _set_span_attribute(
                span, f"{SpanAttributes.LLM_COMPLETIONS}.0.role", "assistant"
            )
    else:
        if isinstance(response, list):
            for index, item in enumerate(response):
                prefix = f"{SpanAttributes.LLM_COMPLETIONS}.{index}"
                _set_span_attribute(span, f"{prefix}.content", item)
                _set_span_attribute(span, f"{prefix}.role", "assistant")
        elif isinstance(response, str):
            _set_span_attribute(
                span, f"{SpanAttributes.LLM_COMPLETIONS}.0.content", response
            )
            _set_span_attribute(
                span, f"{SpanAttributes.LLM_COMPLETIONS}.0.role", "assistant"
            )

    return


def _build_from_streaming_response(span, response, llm_model):
    complete_response = ""
    for item in response:
        item_to_yield = item
        complete_response += str(item.text)

        yield item_to_yield

    _set_response_attributes(span, complete_response, llm_model)

    span.set_status(Status(StatusCode.OK))
    span.end()


async def _abuild_from_streaming_response(span, response, llm_model):
    complete_response = ""
    async for item in response:
        item_to_yield = item
        complete_response += str(item.text)

        yield item_to_yield

    _set_response_attributes(span, complete_response, llm_model)

    span.set_status(Status(StatusCode.OK))
    span.end()


# @dont_throw
def _handle_request(span, args, kwargs, llm_model):
    if span.is_recording():
        _set_input_attributes(span, args, kwargs, llm_model)


@dont_throw
def _handle_response(span, response, llm_model):
    if span.is_recording():
        _set_response_attributes(span, response, llm_model)

        span.set_status(Status(StatusCode.OK))


def _with_tracer_wrapper(func):
    """Helper for providing tracer for wrapper functions."""

    def _with_tracer(tracer, to_wrap):
        def wrapper(wrapped, instance, args, kwargs):
            return func(tracer, to_wrap, wrapped, instance, args, kwargs)

        return wrapper

    return _with_tracer


@_with_tracer_wrapper
async def _awrap(tracer, to_wrap, wrapped, instance, args, kwargs):
    """Instruments and calls every function defined in TO_WRAP."""
    if context_api.get_value(_SUPPRESS_INSTRUMENTATION_KEY) or context_api.get_value(
        SUPPRESS_LANGUAGE_MODEL_INSTRUMENTATION_KEY
    ):
        return await wrapped(*args, **kwargs)

    llm_model = "unknown"
    if hasattr(instance, "_model_id"):
        llm_model = instance._model_id.replace("models/", "")
    if hasattr(instance, "_model_name"):
        llm_model = instance._model_name.replace(
            "publishers/google/models/", ""
        ).replace("models/", "")
    if hasattr(instance, "model") and hasattr(instance.model, "model_name"):
        llm_model = instance.model.model_name.replace("models/", "")
    if "model" in kwargs:
        llm_model = kwargs["model"].replace("models/", "")

    name = to_wrap.get("span_name")
    span = tracer.start_span(
        name,
        kind=SpanKind.CLIENT,
        attributes={
            SpanAttributes.LLM_SYSTEM: "Gemini",
            SpanAttributes.LLM_REQUEST_TYPE: LLMRequestTypeValues.COMPLETION.value,
        },
    )

    _handle_request(span, args, kwargs, llm_model)

    response = await wrapped(*args, **kwargs)

    if response:
        if is_streaming_response(response):
            return _build_from_streaming_response(span, response, llm_model)
        elif is_async_streaming_response(response):
            return _abuild_from_streaming_response(span, response, llm_model)
        else:
            _handle_response(span, response, llm_model)

    span.end()
    return response


@_with_tracer_wrapper
def _wrap(tracer, to_wrap, wrapped, instance, args, kwargs):
    """Instruments and calls every function defined in TO_WRAP."""
    if context_api.get_value(_SUPPRESS_INSTRUMENTATION_KEY) or context_api.get_value(
        SUPPRESS_LANGUAGE_MODEL_INSTRUMENTATION_KEY
    ):
        return wrapped(*args, **kwargs)

    llm_model = "unknown"
    if hasattr(instance, "_model_id"):
        llm_model = instance._model_id.replace("models/", "")
    if hasattr(instance, "_model_name"):
        llm_model = instance._model_name.replace(
            "publishers/google/models/", ""
        ).replace("models/", "")
    if hasattr(instance, "model") and hasattr(instance.model, "model_name"):
        llm_model = instance.model.model_name.replace("models/", "")
    if "model" in kwargs:
        llm_model = kwargs["model"].replace("models/", "")

    name = to_wrap.get("span_name")
    span = tracer.start_span(
        name,
        kind=SpanKind.CLIENT,
        attributes={
            SpanAttributes.LLM_SYSTEM: "Gemini",
            SpanAttributes.LLM_REQUEST_TYPE: LLMRequestTypeValues.COMPLETION.value,
        },
    )

    _handle_request(span, args, kwargs, llm_model)

    response = wrapped(*args, **kwargs)

    if response:
        if is_streaming_response(response):
            return _build_from_streaming_response(span, response, llm_model)
        elif is_async_streaming_response(response):
            return _abuild_from_streaming_response(span, response, llm_model)
        else:
            _handle_response(span, response, llm_model)

    span.end()
    return response


class GoogleGenerativeAiInstrumentor(BaseInstrumentor):
    """An instrumentor for Google Generative AI's client library."""

    def __init__(self, exception_logger=None):
        super().__init__()
        Config.exception_logger = exception_logger

    def instrumentation_dependencies(self) -> Collection[str]:
        if is_package_installed("google-genai"):
            return ("google-genai >= 0.1.0",)
        elif is_package_installed("google-generativeai"):
            return ["google-generativeai >= 0.5.0"]
        else:
            return []

    def _wrapped_methods(self):
        if is_package_installed("google-genai"):
            return WRAPPED_METHODS
        elif is_package_installed("google-generativeai"):
            return LEGACY_WRAPPED_METHODS
        else:
            return []

    def _instrument(self, **kwargs):
        tracer_provider = kwargs.get("tracer_provider")
        tracer = get_tracer(__name__, __version__, tracer_provider)
        for wrapped_method in self._wrapped_methods():
            wrap_package = wrapped_method.get("package")
            wrap_object = wrapped_method.get("object")
            wrap_method = wrapped_method.get("method")

            wrap_function_wrapper(
                wrap_package,
                f"{wrap_object}.{wrap_method}",
                (
                    _awrap(tracer, wrapped_method)
                    if wrap_method == "generate_content_async"
                    else _wrap(tracer, wrapped_method)
                ),
            )

    def _uninstrument(self, **kwargs):
        for wrapped_method in self._wrapped_methods():
            wrap_package = wrapped_method.get("package")
            wrap_object = wrapped_method.get("object")
            unwrap(
                f"{wrap_package}.{wrap_object}",
                wrapped_method.get("method", ""),
            )
