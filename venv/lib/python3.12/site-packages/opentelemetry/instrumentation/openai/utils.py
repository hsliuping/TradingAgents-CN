import asyncio
from importlib.metadata import version
from contextlib import asynccontextmanager
import logging
import os
import threading
import traceback

import openai
from opentelemetry.instrumentation.openai.shared.config import Config

_OPENAI_VERSION = version("openai")


def is_openai_v1():
    return _OPENAI_VERSION >= "1.0.0"


def is_azure_openai(instance):
    return is_openai_v1() and isinstance(
        instance._client, (openai.AsyncAzureOpenAI, openai.AzureOpenAI)
    )


def is_metrics_enabled() -> bool:
    return (os.getenv("TRACELOOP_METRICS_ENABLED") or "true").lower() == "true"


def should_record_stream_token_usage():
    return Config.enrich_token_usage


def _with_image_gen_metric_wrapper(func):
    def _with_metric(duration_histogram, exception_counter):
        def wrapper(wrapped, instance, args, kwargs):
            return func(
                duration_histogram, exception_counter, wrapped, instance, args, kwargs
            )

        return wrapper

    return _with_metric


def _with_embeddings_telemetry_wrapper(func):
    def _with_embeddings_telemetry(
        tracer,
        token_counter,
        vector_size_counter,
        duration_histogram,
        exception_counter,
    ):
        def wrapper(wrapped, instance, args, kwargs):
            return func(
                tracer,
                token_counter,
                vector_size_counter,
                duration_histogram,
                exception_counter,
                wrapped,
                instance,
                args,
                kwargs,
            )

        return wrapper

    return _with_embeddings_telemetry


def _with_chat_telemetry_wrapper(func):
    def _with_chat_telemetry(
        tracer,
        token_counter,
        choice_counter,
        duration_histogram,
        exception_counter,
        streaming_time_to_first_token,
        streaming_time_to_generate,
    ):
        def wrapper(wrapped, instance, args, kwargs):
            return func(
                tracer,
                token_counter,
                choice_counter,
                duration_histogram,
                exception_counter,
                streaming_time_to_first_token,
                streaming_time_to_generate,
                wrapped,
                instance,
                args,
                kwargs,
            )

        return wrapper

    return _with_chat_telemetry


def _with_tracer_wrapper(func):
    def _with_tracer(tracer):
        def wrapper(wrapped, instance, args, kwargs):
            return func(tracer, wrapped, instance, args, kwargs)

        return wrapper

    return _with_tracer


@asynccontextmanager
async def start_as_current_span_async(tracer, *args, **kwargs):
    with tracer.start_as_current_span(*args, **kwargs) as span:
        yield span


def dont_throw(func):
    """
    A decorator that wraps the passed in function and logs exceptions instead of throwing them.
    Works for both synchronous and asynchronous functions.
    """
    logger = logging.getLogger(func.__module__)

    async def async_wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            _handle_exception(e, func, logger)

    def sync_wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            _handle_exception(e, func, logger)

    def _handle_exception(e, func, logger):
        logger.debug(
            "OpenLLMetry failed to trace in %s, error: %s",
            func.__name__,
            traceback.format_exc(),
        )
        if Config.exception_logger:
            Config.exception_logger(e)

    return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper


def run_async(method):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        thread = threading.Thread(target=lambda: asyncio.run(method))
        thread.start()
        thread.join()
    else:
        asyncio.run(method)
