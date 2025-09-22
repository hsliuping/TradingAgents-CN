import importlib
import pkgutil

from wrapt import wrap_function_wrapper
from inflection import underscore

from opentelemetry import context as context_api

from opentelemetry.instrumentation.utils import _SUPPRESS_INSTRUMENTATION_KEY
from opentelemetry.semconv_ai import SpanAttributes, LLMRequestTypeValues
from opentelemetry.instrumentation.llamaindex.utils import (
    _with_tracer_wrapper,
    dont_throw,
    start_as_current_span_async,
    should_send_prompts,
)

import llama_index.llms

try:
    from llama_index.core.llms.custom import CustomLLM

    MODULE_NAME = "llama_index.llms"
except ModuleNotFoundError:
    from llama_index.llms import CustomLLM

    MODULE_NAME = "llama_index.llms"


class CustomLLMInstrumentor:
    def __init__(self, tracer):
        self._tracer = tracer

    def instrument(self):
        packages = pkgutil.iter_modules(llama_index.llms.__path__)
        modules = [
            importlib.import_module(f"llama_index.llms.{p.name}") for p in packages
        ]
        custom_llms_classes = [
            cls
            for module in modules
            for name, cls in module.__dict__.items()
            if isinstance(cls, type) and issubclass(cls, CustomLLM)
        ]

        for cls in custom_llms_classes:
            wrap_function_wrapper(
                cls.__module__,
                f"{cls.__name__}.complete",
                complete_wrapper(self._tracer),
            )
            wrap_function_wrapper(
                cls.__module__,
                f"{cls.__name__}.acomplete",
                acomplete_wrapper(self._tracer),
            )
            wrap_function_wrapper(
                cls.__module__, f"{cls.__name__}.chat", chat_wrapper(self._tracer)
            )
            wrap_function_wrapper(
                cls.__module__, f"{cls.__name__}.achat", achat_wrapper(self._tracer)
            )

    def unistrument(self):
        pass


def _set_span_attribute(span, name, value):
    if value is not None:
        if value != "":
            span.set_attribute(name, value)
    return


@_with_tracer_wrapper
def chat_wrapper(tracer, wrapped, instance: CustomLLM, args, kwargs):
    if context_api.get_value(_SUPPRESS_INSTRUMENTATION_KEY):
        return wrapped(*args, **kwargs)

    llm_request_type = LLMRequestTypeValues.CHAT

    with tracer.start_as_current_span(
        f"{snake_case_class_name(instance)}.chat"
    ) as span:
        _handle_request(span, llm_request_type, args, kwargs, instance)
        response = wrapped(*args, **kwargs)
        _handle_response(span, llm_request_type, instance, response)

        return response


@_with_tracer_wrapper
async def achat_wrapper(tracer, wrapped, instance: CustomLLM, args, kwargs):
    if context_api.get_value(_SUPPRESS_INSTRUMENTATION_KEY):
        return wrapped(*args, **kwargs)

    llm_request_type = LLMRequestTypeValues.CHAT

    async with start_as_current_span_async(
        tracer=tracer, name=f"{snake_case_class_name(instance)}.chat"
    ) as span:
        _handle_request(span, llm_request_type, args, kwargs, instance)
        response = await wrapped(*args, **kwargs)
        _handle_response(span, llm_request_type, instance, response)

        return response


@_with_tracer_wrapper
def complete_wrapper(tracer, wrapped, instance: CustomLLM, args, kwargs):
    if context_api.get_value(_SUPPRESS_INSTRUMENTATION_KEY):
        return wrapped(*args, **kwargs)

    llm_request_type = LLMRequestTypeValues.COMPLETION

    with tracer.start_as_current_span(
        f"{snake_case_class_name(instance)}.completion"
    ) as span:
        _handle_request(span, llm_request_type, args, kwargs, instance)
        response = wrapped(*args, **kwargs)
        _handle_response(span, llm_request_type, instance, response)

        return response


@_with_tracer_wrapper
async def acomplete_wrapper(tracer, wrapped, instance: CustomLLM, args, kwargs):
    if context_api.get_value(_SUPPRESS_INSTRUMENTATION_KEY):
        return wrapped(*args, **kwargs)

    llm_request_type = LLMRequestTypeValues.COMPLETION

    async with start_as_current_span_async(
        tracer=tracer, name=f"{snake_case_class_name(instance)}.completion"
    ) as span:
        _handle_request(span, llm_request_type, args, kwargs, instance)
        response = await wrapped(*args, **kwargs)
        _handle_response(span, llm_request_type, instance, response)

        return response


@dont_throw
def _handle_request(span, llm_request_type, args, kwargs, instance: CustomLLM):
    _set_span_attribute(span, SpanAttributes.LLM_SYSTEM, instance.__class__.__name__)
    _set_span_attribute(span, SpanAttributes.LLM_REQUEST_TYPE, llm_request_type.value)
    _set_span_attribute(
        span, SpanAttributes.LLM_REQUEST_MODEL, instance.metadata.model_name
    )
    _set_span_attribute(
        span, SpanAttributes.LLM_REQUEST_MAX_TOKENS, instance.metadata.context_window
    )
    _set_span_attribute(
        span, SpanAttributes.LLM_REQUEST_TOP_P, instance.metadata.num_output
    )

    if should_send_prompts():
        # TODO: add support for chat
        if llm_request_type == LLMRequestTypeValues.COMPLETION:
            if len(args) > 0:
                prompt = args[0]
                _set_span_attribute(
                    span,
                    f"{SpanAttributes.LLM_PROMPTS}.0.user",
                    prompt[0] if isinstance(prompt, list) else prompt,
                )

    return


@dont_throw
def _handle_response(span, llm_request_type, instance, response):
    _set_span_attribute(
        span, SpanAttributes.LLM_RESPONSE_MODEL, instance.metadata.model_name
    )

    if should_send_prompts():
        if llm_request_type == LLMRequestTypeValues.COMPLETION:
            _set_span_attribute(
                span, f"{SpanAttributes.LLM_COMPLETIONS}.0.content", response.text
            )

    return


def snake_case_class_name(instance):
    return underscore(instance.__class__.__name__)
