from importlib.metadata import version
import os
import logging
import traceback
from opentelemetry import context as context_api
from opentelemetry.instrumentation.groq.config import Config
from opentelemetry.semconv_ai import SpanAttributes

GEN_AI_SYSTEM = "gen_ai.system"
GEN_AI_SYSTEM_GROQ = "groq"

_PYDANTIC_VERSION = version("pydantic")


def set_span_attribute(span, name, value):
    if value is not None and value != "":
        span.set_attribute(name, value)


def should_send_prompts():
    return (
        os.getenv("TRACELOOP_TRACE_CONTENT") or "true"
    ).lower() == "true" or context_api.get_value("override_enable_content_tracing")


def dont_throw(func):
    """
    A decorator that wraps the passed in function and logs exceptions instead of throwing them.

    @param func: The function to wrap
    @return: The wrapper function
    """
    # Obtain a logger specific to the function's module
    logger = logging.getLogger(func.__module__)

    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.debug(
                "OpenLLMetry failed to trace in %s, error: %s",
                func.__name__,
                traceback.format_exc(),
            )
            if Config.exception_logger:
                Config.exception_logger(e)

    return wrapper


@dont_throw
def shared_metrics_attributes(response):
    response_dict = model_as_dict(response)

    common_attributes = Config.get_common_metrics_attributes()

    return {
        **common_attributes,
        GEN_AI_SYSTEM: GEN_AI_SYSTEM_GROQ,
        SpanAttributes.LLM_RESPONSE_MODEL: response_dict.get("model"),
    }


@dont_throw
def error_metrics_attributes(exception):
    return {
        GEN_AI_SYSTEM: GEN_AI_SYSTEM_GROQ,
        "error.type": exception.__class__.__name__,
    }


def model_as_dict(model):
    if _PYDANTIC_VERSION < "2.0.0":
        return model.dict()
    if hasattr(model, "model_dump"):
        return model.model_dump()
    elif hasattr(model, "parse"):  # Raw API response
        return model_as_dict(model.parse())
    else:
        return model
