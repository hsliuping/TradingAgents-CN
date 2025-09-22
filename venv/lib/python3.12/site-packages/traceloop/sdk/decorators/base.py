import json
from functools import wraps
import os
from typing import (
    Optional,
    TypeVar,
    Callable,
    Any,
    cast,
    ParamSpec,
    Awaitable,
)
import inspect
import warnings
import types

from opentelemetry import trace
from opentelemetry.trace.status import Status, StatusCode
from opentelemetry import context as context_api
from opentelemetry.semconv_ai import SpanAttributes, TraceloopSpanKindValues

from traceloop.sdk.telemetry import Telemetry
from traceloop.sdk.tracing import get_tracer, set_workflow_name
from traceloop.sdk.tracing.tracing import (
    TracerWrapper,
    set_entity_path,
    get_chained_entity_path,
)
from traceloop.sdk.utils import camel_to_snake
from traceloop.sdk.utils.json_encoder import JSONEncoder

P = ParamSpec("P")

R = TypeVar("R")
F = TypeVar("F", bound=Callable[P, R | Awaitable[R]])


def _is_json_size_valid(json_str: str) -> bool:
    """Check if JSON string size is less than 1MB"""
    return len(json_str) < 1_000_000


# Async Decorators - Deprecated


def aentity_method(
    name: Optional[str] = None,
    version: Optional[int] = None,
    tlp_span_kind: Optional[TraceloopSpanKindValues] = TraceloopSpanKindValues.TASK,
):
    warnings.warn(
        "DeprecationWarning: The @aentity_method function will be removed in a future version. "
        "Please migrate to @entity_method for both sync and async operations.",
        DeprecationWarning,
        stacklevel=2,
    )

    return entity_method(
        name=name,
        version=version,
        tlp_span_kind=tlp_span_kind,
    )


def aentity_class(
    name: Optional[str],
    version: Optional[int],
    method_name: str,
    tlp_span_kind: Optional[TraceloopSpanKindValues] = TraceloopSpanKindValues.TASK,
):
    warnings.warn(
        "DeprecationWarning: The @aentity_class function will be removed in a future version. "
        "Please migrate to @entity_class for both sync and async operations.",
        DeprecationWarning,
        stacklevel=2,
    )

    return entity_class(
        name=name,
        version=version,
        method_name=method_name,
        tlp_span_kind=tlp_span_kind,
    )


def _handle_generator(span, res):
    # for some reason the SPAN_KEY is not being set in the context of the generator, so we re-set it
    context_api.attach(trace.set_span_in_context(span))
    try:
        for item in res:
            yield item
    except Exception as e:
        span.set_status(Status(StatusCode.ERROR, str(e)))
        span.record_exception(e)
        raise
    finally:
        span.end()
        # Note: we don't detach the context here as this fails in some situations
        # https://github.com/open-telemetry/opentelemetry-python/issues/2606
        # This is not a problem since the context will be detached automatically during garbage collection


async def _ahandle_generator(span, ctx_token, res):
    try:
        async for part in res:
            yield part
    except Exception as e:
        span.set_status(Status(StatusCode.ERROR, str(e)))
        span.record_exception(e)
        raise
    finally:
        span.end()
        context_api.detach(ctx_token)


def _should_send_prompts():
    return (
        os.getenv("TRACELOOP_TRACE_CONTENT") or "true"
    ).lower() == "true" or context_api.get_value("override_enable_content_tracing")


# Unified Decorators : handles both sync and async operations


def _is_async_method(fn):
    # check if co-routine function or async generator( example : using async & yield)
    return inspect.iscoroutinefunction(fn) or inspect.isasyncgenfunction(fn)


def _setup_span(entity_name, tlp_span_kind, version):
    """Sets up the OpenTelemetry span and context"""
    if tlp_span_kind in [
        TraceloopSpanKindValues.WORKFLOW,
        TraceloopSpanKindValues.AGENT,
    ]:
        set_workflow_name(entity_name)
    span_name = f"{entity_name}.{tlp_span_kind.value}"

    with get_tracer() as tracer:
        span = tracer.start_span(span_name)
        ctx = trace.set_span_in_context(span)
        ctx_token = context_api.attach(ctx)

        if tlp_span_kind in [
            TraceloopSpanKindValues.TASK,
            TraceloopSpanKindValues.TOOL,
        ]:
            entity_path = get_chained_entity_path(entity_name)
            set_entity_path(entity_path)

        span.set_attribute(SpanAttributes.TRACELOOP_SPAN_KIND, tlp_span_kind.value)
        span.set_attribute(SpanAttributes.TRACELOOP_ENTITY_NAME, entity_name)
        if version:
            span.set_attribute(SpanAttributes.TRACELOOP_ENTITY_VERSION, version)

    return span, ctx, ctx_token


def _handle_span_input(span, args, kwargs, cls=None):
    """Handles entity input logging in JSON for both sync and async functions"""
    try:
        if _should_send_prompts():
            json_input = json.dumps(
                {"args": args, "kwargs": kwargs}, **({"cls": cls} if cls else {})
            )
            if _is_json_size_valid(json_input):
                span.set_attribute(
                    SpanAttributes.TRACELOOP_ENTITY_INPUT,
                    json_input,
                )
    except TypeError as e:
        Telemetry().log_exception(e)


def _handle_span_output(span, res, cls=None):
    """Handles entity output logging in JSON for both sync and async functions"""
    try:
        if _should_send_prompts():
            json_output = json.dumps(res, **({"cls": cls} if cls else {}))
            if _is_json_size_valid(json_output):
                span.set_attribute(
                    SpanAttributes.TRACELOOP_ENTITY_OUTPUT,
                    json_output,
                )
    except TypeError as e:
        Telemetry().log_exception(e)


def _cleanup_span(span, ctx_token):
    """End the span process and detach the context token"""
    span.end()
    context_api.detach(ctx_token)


def entity_method(
    name: Optional[str] = None,
    version: Optional[int] = None,
    tlp_span_kind: Optional[TraceloopSpanKindValues] = TraceloopSpanKindValues.TASK,
) -> Callable[[F], F]:
    def decorate(fn: F) -> F:
        is_async = _is_async_method(fn)
        entity_name = name or fn.__qualname__
        if is_async:
            if inspect.isasyncgenfunction(fn):

                @wraps(fn)
                async def async_gen_wrap(*args: Any, **kwargs: Any) -> Any:
                    if not TracerWrapper.verify_initialized():
                        async for item in fn(*args, **kwargs):
                            yield item
                        return

                    span, ctx, ctx_token = _setup_span(
                        entity_name, tlp_span_kind, version
                    )
                    _handle_span_input(span, args, kwargs, cls=JSONEncoder)
                    async for item in _ahandle_generator(
                        span, ctx_token, fn(*args, **kwargs)
                    ):
                        yield item

                return cast(F, async_gen_wrap)
            else:

                @wraps(fn)
                async def async_wrap(*args: Any, **kwargs: Any) -> Any:
                    if not TracerWrapper.verify_initialized():
                        return await fn(*args, **kwargs)

                    span, ctx, ctx_token = _setup_span(
                        entity_name, tlp_span_kind, version
                    )
                    _handle_span_input(span, args, kwargs, cls=JSONEncoder)
                    try:
                        res = await fn(*args, **kwargs)
                        _handle_span_output(span, res, cls=JSONEncoder)
                        return res
                    except Exception as e:
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                        span.record_exception(e)
                        raise
                    finally:
                        _cleanup_span(span, ctx_token)

                return cast(F, async_wrap)
        else:

            @wraps(fn)
            def sync_wrap(*args: Any, **kwargs: Any) -> Any:
                if not TracerWrapper.verify_initialized():
                    return fn(*args, **kwargs)

                span, ctx, ctx_token = _setup_span(entity_name, tlp_span_kind, version)
                _handle_span_input(span, args, kwargs, cls=JSONEncoder)
                try:
                    res = fn(*args, **kwargs)
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    _cleanup_span(span, ctx_token)
                    raise

                # span will be ended in the generator
                if isinstance(res, types.GeneratorType):
                    return _handle_generator(span, res)

                _handle_span_output(span, res, cls=JSONEncoder)
                _cleanup_span(span, ctx_token)
                return res

            return cast(F, sync_wrap)

    return decorate


def entity_class(
    name: Optional[str],
    version: Optional[int],
    method_name: str,
    tlp_span_kind: Optional[TraceloopSpanKindValues] = TraceloopSpanKindValues.TASK,
):
    def decorator(cls):
        task_name = name if name else camel_to_snake(cls.__qualname__)
        method = getattr(cls, method_name)
        setattr(
            cls,
            method_name,
            entity_method(name=task_name, version=version, tlp_span_kind=tlp_span_kind)(
                method
            ),
        )
        return cls

    return decorator
