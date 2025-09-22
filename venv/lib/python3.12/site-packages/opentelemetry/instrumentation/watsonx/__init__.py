"""OpenTelemetry IBM Watsonx AI instrumentation"""

import logging
import os
import types
import time
from typing import Collection, Optional
from opentelemetry.instrumentation.watsonx.config import Config
from opentelemetry.instrumentation.watsonx.utils import dont_throw
from wrapt import wrap_function_wrapper

from opentelemetry import context as context_api
from opentelemetry.trace import get_tracer, SpanKind
from opentelemetry.trace.status import Status, StatusCode
from opentelemetry.metrics import get_meter
from opentelemetry.metrics import Counter, Histogram

from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from opentelemetry.instrumentation.utils import (
    _SUPPRESS_INSTRUMENTATION_KEY,
    unwrap,
)

from opentelemetry.semconv_ai import (
    SUPPRESS_LANGUAGE_MODEL_INSTRUMENTATION_KEY,
    Meters,
    SpanAttributes,
    LLMRequestTypeValues,
)
from opentelemetry.instrumentation.watsonx.version import __version__

logger = logging.getLogger(__name__)

_instruments = ("ibm-watson-machine-learning >= 1.0.333",)

WRAPPED_METHODS_WATSON_ML_VERSION_1 = [
    {
        "module": "ibm_watson_machine_learning.foundation_models.inference",
        "object": "ModelInference",
        "method": "__init__",
        "span_name": "watsonx.model_init",
    },
    {
        "module": "ibm_watson_machine_learning.foundation_models.inference",
        "object": "ModelInference",
        "method": "generate",
        "span_name": "watsonx.generate",
    },
    {
        "module": "ibm_watson_machine_learning.foundation_models.inference",
        "object": "ModelInference",
        "method": "generate_text_stream",
        "span_name": "watsonx.generate_text_stream",
    },
    {
        "module": "ibm_watson_machine_learning.foundation_models.inference",
        "object": "ModelInference",
        "method": "get_details",
        "span_name": "watsonx.get_details",
    },
]

WRAPPED_METHODS_WATSON_AI_VERSION_1 = [
    {
        "module": "ibm_watsonx_ai.foundation_models",
        "object": "ModelInference",
        "method": "__init__",
        "span_name": "watsonx.model_init",
    },
    {
        "module": "ibm_watsonx_ai.foundation_models",
        "object": "ModelInference",
        "method": "generate",
        "span_name": "watsonx.generate",
    },
    {
        "module": "ibm_watsonx_ai.foundation_models",
        "object": "ModelInference",
        "method": "generate_text_stream",
        "span_name": "watsonx.generate_text_stream",
    },
    {
        "module": "ibm_watsonx_ai.foundation_models",
        "object": "ModelInference",
        "method": "get_details",
        "span_name": "watsonx.get_details",
    },
]

WATSON_MODULES = [
    WRAPPED_METHODS_WATSON_ML_VERSION_1,
    WRAPPED_METHODS_WATSON_AI_VERSION_1,
]


def _set_span_attribute(span, name, value):
    if value is not None:
        if value != "":
            span.set_attribute(name, value)
    return


def _set_api_attributes(span):
    _set_span_attribute(
        span,
        WatsonxSpanAttributes.WATSONX_API_BASE,
        "https://us-south.ml.cloud.ibm.com",
    )
    _set_span_attribute(span, WatsonxSpanAttributes.WATSONX_API_TYPE, "watsonx.ai")
    _set_span_attribute(span, WatsonxSpanAttributes.WATSONX_API_VERSION, "1.0")

    return


def should_send_prompts():
    return (
        os.getenv("TRACELOOP_TRACE_CONTENT") or "true"
    ).lower() == "true" or context_api.get_value("override_enable_content_tracing")


def is_metrics_enabled() -> bool:
    return (os.getenv("TRACELOOP_METRICS_ENABLED") or "true").lower() == "true"


def _set_input_attributes(span, instance, kwargs):
    if should_send_prompts() and kwargs is not None and len(kwargs) > 0:
        prompt = kwargs.get("prompt")
        if isinstance(prompt, list):
            for index, input in enumerate(prompt):
                _set_span_attribute(
                    span,
                    f"{SpanAttributes.LLM_PROMPTS}.{index}.user",
                    input,
                )
        else:
            _set_span_attribute(
                span,
                f"{SpanAttributes.LLM_PROMPTS}.0.user",
                prompt,
            )

    _set_span_attribute(span, SpanAttributes.LLM_REQUEST_MODEL, instance.model_id)
    # Set other attributes
    modelParameters = instance.params
    if modelParameters is not None:
        _set_span_attribute(
            span,
            SpanAttributes.LLM_DECODING_METHOD,
            modelParameters.get("decoding_method", None),
        )
        _set_span_attribute(
            span,
            SpanAttributes.LLM_RANDOM_SEED,
            modelParameters.get("random_seed", None),
        )
        _set_span_attribute(
            span,
            SpanAttributes.LLM_MAX_NEW_TOKENS,
            modelParameters.get("max_new_tokens", None),
        )
        _set_span_attribute(
            span,
            SpanAttributes.LLM_MIN_NEW_TOKENS,
            modelParameters.get("min_new_tokens", None),
        )
        _set_span_attribute(
            span, SpanAttributes.LLM_TOP_K, modelParameters.get("top_k", None)
        )
        _set_span_attribute(
            span,
            SpanAttributes.LLM_REPETITION_PENALTY,
            modelParameters.get("repetition_penalty", None),
        )
        _set_span_attribute(
            span,
            SpanAttributes.LLM_REQUEST_TEMPERATURE,
            modelParameters.get("temperature", None),
        )
        _set_span_attribute(
            span, SpanAttributes.LLM_REQUEST_TOP_P, modelParameters.get("top_p", None)
        )

    return


def _set_stream_response_attributes(span, stream_response):
    _set_span_attribute(
        span, SpanAttributes.LLM_RESPONSE_MODEL, stream_response.get("model_id")
    )
    _set_span_attribute(
        span,
        SpanAttributes.LLM_USAGE_PROMPT_TOKENS,
        stream_response.get("input_token_count"),
    )
    _set_span_attribute(
        span,
        SpanAttributes.LLM_USAGE_COMPLETION_TOKENS,
        stream_response.get("generated_token_count"),
    )
    total_token = stream_response.get("input_token_count") + stream_response.get(
        "generated_token_count"
    )
    _set_span_attribute(
        span,
        SpanAttributes.LLM_USAGE_TOTAL_TOKENS,
        total_token,
    )
    _set_span_attribute(
        span,
        f"{SpanAttributes.LLM_COMPLETIONS}.0.content",
        stream_response.get("generated_text"),
    )


def _set_completion_content_attributes(
    span, response, index, response_counter
) -> Optional[str]:
    if not isinstance(response, dict):
        return None

    if results := response.get("results"):
        _set_span_attribute(
            span,
            f"{SpanAttributes.LLM_COMPLETIONS}.{index}.content",
            results[0]["generated_text"],
        )
        model_id = response.get("model_id")

        if response_counter:
            attributes_with_reason = {
                SpanAttributes.LLM_RESPONSE_MODEL: model_id,
                SpanAttributes.LLM_RESPONSE_STOP_REASON: results[0]["stop_reason"],
            }
            response_counter.add(1, attributes=attributes_with_reason)

        return model_id

    return None


def _token_usage_count(responses):
    prompt_token = 0
    completion_token = 0
    if isinstance(responses, list):
        for response in responses:
            prompt_token += response["results"][0]["input_token_count"]
            completion_token += response["results"][0]["generated_token_count"]
    elif isinstance(responses, dict):
        response = responses
        prompt_token = response["results"][0]["input_token_count"]
        completion_token = response["results"][0]["generated_token_count"]

    return prompt_token, completion_token


@dont_throw
def _set_response_attributes(
    span, responses, token_histogram, response_counter, duration_histogram, duration
):
    if not isinstance(responses, (list, dict)):
        return

    if isinstance(responses, list):
        if len(responses) == 0:
            return
        for index, response in enumerate(responses):
            model_id = _set_completion_content_attributes(
                span, response, index, response_counter
            )
    elif isinstance(responses, dict):
        response = responses
        model_id = _set_completion_content_attributes(
            span, response, 0, response_counter
        )

    if model_id is None:
        return
    _set_span_attribute(span, SpanAttributes.LLM_RESPONSE_MODEL, model_id)

    prompt_token, completion_token = _token_usage_count(responses)
    if (prompt_token + completion_token) != 0:
        _set_span_attribute(
            span,
            SpanAttributes.LLM_USAGE_COMPLETION_TOKENS,
            completion_token,
        )
        _set_span_attribute(
            span,
            SpanAttributes.LLM_USAGE_PROMPT_TOKENS,
            prompt_token,
        )
        _set_span_attribute(
            span,
            SpanAttributes.LLM_USAGE_TOTAL_TOKENS,
            prompt_token + completion_token,
        )

        shared_attributes = _metric_shared_attributes(response_model=model_id)

        if token_histogram:
            attributes_with_token_type = {
                **shared_attributes,
                SpanAttributes.LLM_TOKEN_TYPE: "output",
            }
            token_histogram.record(
                completion_token, attributes=attributes_with_token_type
            )
            attributes_with_token_type = {
                **shared_attributes,
                SpanAttributes.LLM_TOKEN_TYPE: "input",
            }
            token_histogram.record(prompt_token, attributes=attributes_with_token_type)

    if duration and isinstance(duration, (float, int)) and duration_histogram:
        duration_histogram.record(duration, attributes=shared_attributes)


def _build_and_set_stream_response(
    span,
    response,
    raw_flag,
    token_histogram,
    response_counter,
    duration_histogram,
    start_time,
):
    stream_generated_text = ""
    stream_model_id = ""
    stream_stop_reason = ""
    stream_generated_token_count = 0
    stream_input_token_count = 0
    for item in response:
        stream_model_id = item["model_id"]
        stream_generated_text += item["results"][0]["generated_text"]
        stream_input_token_count += item["results"][0]["input_token_count"]
        stream_generated_token_count = item["results"][0]["generated_token_count"]
        stream_stop_reason = item["results"][0]["stop_reason"]

        if raw_flag:
            yield item
        else:
            yield item["results"][0]["generated_text"]

    shared_attributes = _metric_shared_attributes(
        response_model=stream_model_id, is_streaming=True
    )
    stream_response = {
        "model_id": stream_model_id,
        "generated_text": stream_generated_text,
        "generated_token_count": stream_generated_token_count,
        "input_token_count": stream_input_token_count,
    }
    _set_stream_response_attributes(span, stream_response)
    # response counter
    if response_counter:
        attributes_with_reason = {
            **shared_attributes,
            SpanAttributes.LLM_RESPONSE_STOP_REASON: stream_stop_reason,
        }
        response_counter.add(1, attributes=attributes_with_reason)

    # token histogram
    if token_histogram:
        attributes_with_token_type = {
            **shared_attributes,
            SpanAttributes.LLM_TOKEN_TYPE: "output",
        }
        token_histogram.record(
            stream_generated_token_count, attributes=attributes_with_token_type
        )
        attributes_with_token_type = {
            **shared_attributes,
            SpanAttributes.LLM_TOKEN_TYPE: "input",
        }
        token_histogram.record(
            stream_input_token_count, attributes=attributes_with_token_type
        )

    # duration histogram
    if start_time and isinstance(start_time, (float, int)):
        duration = time.time() - start_time
    else:
        duration = None
    if duration and isinstance(duration, (float, int)) and duration_histogram:
        duration_histogram.record(duration, attributes=shared_attributes)

    span.set_status(Status(StatusCode.OK))
    span.end()


def _metric_shared_attributes(response_model: str, is_streaming: bool = False):
    return {
        SpanAttributes.LLM_RESPONSE_MODEL: response_model,
        SpanAttributes.LLM_SYSTEM: "watsonx",
        "stream": is_streaming,
    }


def _with_tracer_wrapper(func):
    """Helper for providing tracer for wrapper functions."""

    def _with_tracer(
        tracer,
        to_wrap,
        token_histogram,
        response_counter,
        duration_histogram,
        exception_counter,
    ):
        def wrapper(wrapped, instance, args, kwargs):
            return func(
                tracer,
                to_wrap,
                token_histogram,
                response_counter,
                duration_histogram,
                exception_counter,
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
    to_wrap,
    token_histogram: Histogram,
    response_counter: Counter,
    duration_histogram: Histogram,
    exception_counter: Counter,
    wrapped,
    instance,
    args,
    kwargs,
):
    """Instruments and calls every function defined in TO_WRAP."""
    if context_api.get_value(_SUPPRESS_INSTRUMENTATION_KEY) or context_api.get_value(
        SUPPRESS_LANGUAGE_MODEL_INSTRUMENTATION_KEY
    ):
        return wrapped(*args, **kwargs)

    name = to_wrap.get("span_name")

    span = tracer.start_span(
        name,
        kind=SpanKind.CLIENT,
        attributes={
            SpanAttributes.LLM_SYSTEM: "Watsonx",
            SpanAttributes.LLM_REQUEST_TYPE: LLMRequestTypeValues.COMPLETION.value,
        },
    )

    _set_api_attributes(span)
    if "generate" in name:
        _set_input_attributes(span, instance, kwargs)
        if to_wrap.get("method") == "generate_text_stream":
            if (raw_flag := kwargs.get("raw_response", None)) is None:
                kwargs = {**kwargs, "raw_response": True}
            elif raw_flag is False:
                kwargs["raw_response"] = True

    try:
        start_time = time.time()
        response = wrapped(*args, **kwargs)
        end_time = time.time()
    except Exception as e:
        end_time = time.time()
        duration = end_time - start_time if "start_time" in locals() else 0

        attributes = {
            "error.type": e.__class__.__name__,
        }

        if duration > 0 and duration_histogram:
            duration_histogram.record(duration, attributes=attributes)
        if exception_counter:
            exception_counter.add(1, attributes=attributes)

        raise e

    if "generate" in name:
        if isinstance(response, types.GeneratorType):
            return _build_and_set_stream_response(
                span,
                response,
                raw_flag,
                token_histogram,
                response_counter,
                duration_histogram,
                start_time,
            )
        else:
            duration = end_time - start_time
            _set_response_attributes(
                span,
                response,
                token_histogram,
                response_counter,
                duration_histogram,
                duration,
            )

    span.end()
    return response


class WatsonxSpanAttributes:
    WATSONX_API_VERSION = "watsonx.api_version"
    WATSONX_API_BASE = "watsonx.api_base"
    WATSONX_API_TYPE = "watsonx.api_type"


class WatsonxInstrumentor(BaseInstrumentor):
    """An instrumentor for Watsonx's client library."""

    def __init__(self, exception_logger=None):
        super().__init__()
        Config.exception_logger = exception_logger

    def instrumentation_dependencies(self) -> Collection[str]:
        return _instruments

    def _instrument(self, **kwargs):
        tracer_provider = kwargs.get("tracer_provider")
        tracer = get_tracer(__name__, __version__, tracer_provider)

        meter_provider = kwargs.get("meter_provider")
        meter = get_meter(__name__, __version__, meter_provider)

        if is_metrics_enabled():
            token_histogram = meter.create_histogram(
                name=Meters.LLM_TOKEN_USAGE,
                unit="token",
                description="Measures number of input and output tokens used",
            )

            response_counter = meter.create_counter(
                name=Meters.LLM_WATSONX_COMPLETIONS_RESPONSES,
                unit="response",
                description="Number of response returned by completions call",
            )

            duration_histogram = meter.create_histogram(
                name=Meters.LLM_OPERATION_DURATION,
                unit="s",
                description="GenAI operation duration",
            )

            exception_counter = meter.create_counter(
                name=Meters.LLM_WATSONX_COMPLETIONS_EXCEPTIONS,
                unit="time",
                description="Number of exceptions occurred during completions",
            )
        else:
            (
                token_histogram,
                response_counter,
                duration_histogram,
                exception_counter,
            ) = (
                None,
                None,
                None,
                None,
            )

        for wrapped_methods in WATSON_MODULES:
            for wrapped_method in wrapped_methods:
                wrap_module = wrapped_method.get("module")
                wrap_object = wrapped_method.get("object")
                wrap_method = wrapped_method.get("method")
                wrap_function_wrapper(
                    wrap_module,
                    f"{wrap_object}.{wrap_method}",
                    _wrap(
                        tracer,
                        wrapped_method,
                        token_histogram,
                        response_counter,
                        duration_histogram,
                        exception_counter,
                    ),
                )

    def _uninstrument(self, **kwargs):
        for wrapped_methods in WATSON_MODULES:
            for wrapped_method in wrapped_methods:
                wrap_module = wrapped_method.get("module")
                wrap_object = wrapped_method.get("object")
                unwrap(f"{wrap_module}.{wrap_object}", wrapped_method.get("method"))
