from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Callable, Collection, Tuple, cast
import json
import logging
import traceback

from opentelemetry import context, propagate
from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from opentelemetry.instrumentation.utils import unwrap
from opentelemetry.trace import get_tracer
from wrapt import ObjectProxy, register_post_import_hook, wrap_function_wrapper
from opentelemetry.trace.status import Status, StatusCode
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.trace.propagation import set_span_in_context
from opentelemetry.semconv_ai import SpanAttributes

from opentelemetry.instrumentation.mcp.version import __version__

_instruments = ("mcp >= 1.6.0",)


class Config:
    exception_logger = None


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


class McpInstrumentor(BaseInstrumentor):
    def instrumentation_dependencies(self) -> Collection[str]:
        return _instruments

    def _instrument(self, **kwargs):
        tracer_provider = kwargs.get("tracer_provider")
        tracer = get_tracer(__name__, __version__, tracer_provider)

        register_post_import_hook(
            lambda _: wrap_function_wrapper(
                "mcp.client.sse", "sse_client", self._transport_wrapper(tracer)
            ),
            "mcp.client.sse",
        )
        register_post_import_hook(
            lambda _: wrap_function_wrapper(
                "mcp.server.sse",
                "SseServerTransport.connect_sse",
                self._transport_wrapper(tracer),
            ),
            "mcp.server.sse",
        )
        register_post_import_hook(
            lambda _: wrap_function_wrapper(
                "mcp.client.stdio", "stdio_client", self._transport_wrapper(tracer)
            ),
            "mcp.client.stdio",
        )
        register_post_import_hook(
            lambda _: wrap_function_wrapper(
                "mcp.server.stdio", "stdio_server", self._transport_wrapper(tracer)
            ),
            "mcp.server.stdio",
        )
        register_post_import_hook(
            lambda _: wrap_function_wrapper(
                "mcp.server.session",
                "ServerSession.__init__",
                self._base_session_init_wrapper(tracer),
            ),
            "mcp.server.session",
        )
        wrap_function_wrapper(
            "mcp.shared.session",
            "BaseSession.send_request",
            self.patch_mcp_client(tracer),
        )

    def _uninstrument(self, **kwargs):
        unwrap("mcp.client.stdio", "stdio_client")
        unwrap("mcp.server.stdio", "stdio_server")

    def _transport_wrapper(self, tracer):
        @asynccontextmanager
        async def traced_method(
            wrapped: Callable[..., Any], instance: Any, args: Any, kwargs: Any
        ) -> AsyncGenerator[
            Tuple["InstrumentedStreamReader", "InstrumentedStreamWriter"], None
        ]:
            async with wrapped(*args, **kwargs) as (read_stream, write_stream):
                yield InstrumentedStreamReader(
                    read_stream, tracer
                ), InstrumentedStreamWriter(write_stream, tracer)

        return traced_method

    def _base_session_init_wrapper(self, tracer):
        def traced_method(
            wrapped: Callable[..., None], instance: Any, args: Any, kwargs: Any
        ) -> None:
            wrapped(*args, **kwargs)
            reader = getattr(instance, "_incoming_message_stream_reader", None)
            writer = getattr(instance, "_incoming_message_stream_writer", None)
            if reader and writer:
                setattr(
                    instance,
                    "_incoming_message_stream_reader",
                    ContextAttachingStreamReader(reader, tracer),
                )
                setattr(
                    instance,
                    "_incoming_message_stream_writer",
                    ContextSavingStreamWriter(writer, tracer),
                )

        return traced_method

    def patch_mcp_client(self, tracer):
        @dont_throw
        async def traced_method(wrapped, instance, args, kwargs):
            import mcp.types

            if len(args) < 1:
                return
            meta = None
            method = None
            params = None
            if hasattr(args[0].root, "method"):
                method = args[0].root.method
            if hasattr(args[0].root, "params"):
                params = args[0].root.params
            if params is None:
                args[0].root.params = mcp.types.RequestParams()
                meta = mcp.types.RequestParams.Meta()
            else:
                if hasattr(args[0].root.params, "meta"):
                    meta = args[0].root.params.meta
                if meta is None:
                    meta = mcp.types.RequestParams.Meta()

            with tracer.start_as_current_span(f"{method}.mcp") as span:
                span.set_attribute(
                    SpanAttributes.TRACELOOP_ENTITY_INPUT, f"{serialize(args[0])}"
                )
                ctx = set_span_in_context(span)
                parent_span = {}
                TraceContextTextMapPropagator().inject(parent_span, ctx)
                meta.traceparent = parent_span["traceparent"]
                args[0].root.params.meta = meta
                try:
                    result = await wrapped(*args, **kwargs)
                    span.set_attribute(
                        SpanAttributes.TRACELOOP_ENTITY_OUTPUT,
                        serialize(result),
                    )
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    raise

        return traced_method


def serialize(request, depth=0, max_depth=4):
    """Serialize input args to MCP server into JSON.
    The function accepts input object and converts into JSON
    keeping depth in mind to prevent creating large nested JSON"""
    if depth > max_depth:
        return {}
    depth += 1

    def is_serializable(request):
        try:
            json.dumps(request)
            return True
        except Exception:
            return False

    if is_serializable(request):
        return json.dumps(request)
    else:
        result = {}
        try:
            if hasattr(request, "model_dump_json"):
                return request.model_dump_json()
            if hasattr(request, "__dict__"):
                for attrib in request.__dict__:
                    if not attrib.startswith("_"):
                        if type(request.__dict__[attrib]) in [
                            bool,
                            str,
                            int,
                            float,
                            type(None),
                        ]:
                            result[str(attrib)] = request.__dict__[attrib]
                        else:
                            result[str(attrib)] = serialize(
                                request.__dict__[attrib], depth
                            )
        except Exception:
            pass
        return json.dumps(result)


class InstrumentedStreamReader(ObjectProxy):  # type: ignore
    # ObjectProxy missing context manager - https://github.com/GrahamDumpleton/wrapt/issues/73
    def __init__(self, wrapped, tracer):
        super().__init__(wrapped)
        self._tracer = tracer

    async def __aenter__(self) -> Any:
        return await self.__wrapped__.__aenter__()

    async def __aexit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> Any:
        return await self.__wrapped__.__aexit__(exc_type, exc_value, traceback)

    @dont_throw
    async def __aiter__(self) -> AsyncGenerator[Any, None]:
        from mcp.types import JSONRPCMessage, JSONRPCRequest
        from mcp.shared.message import SessionMessage

        async for item in self.__wrapped__:
            if isinstance(item, SessionMessage):
                request = cast(JSONRPCMessage, item.message).root
            elif type(item) is JSONRPCMessage:
                request = cast(JSONRPCMessage, item).root
            else:
                return
            if not isinstance(request, JSONRPCRequest):
                yield item
                continue

            if request.params:
                meta = request.params.get("_meta")
                if meta:
                    ctx = propagate.extract(meta)
                    restore = context.attach(ctx)
                    try:
                        yield item
                        continue
                    finally:
                        context.detach(restore)
            yield item


class InstrumentedStreamWriter(ObjectProxy):  # type: ignore
    # ObjectProxy missing context manager - https://github.com/GrahamDumpleton/wrapt/issues/73
    def __init__(self, wrapped, tracer):
        super().__init__(wrapped)
        self._tracer = tracer

    async def __aenter__(self) -> Any:
        return await self.__wrapped__.__aenter__()

    async def __aexit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> Any:
        return await self.__wrapped__.__aexit__(exc_type, exc_value, traceback)

    @dont_throw
    async def send(self, item: Any) -> Any:
        from mcp.types import JSONRPCMessage, JSONRPCRequest
        from mcp.shared.message import SessionMessage

        if isinstance(item, SessionMessage):
            request = cast(JSONRPCMessage, item.message).root
        elif type(item) is JSONRPCMessage:
            request = cast(JSONRPCMessage, item).root
        else:
            return

        with self._tracer.start_as_current_span("ResponseStreamWriter") as span:
            if hasattr(request, "result"):
                span.set_attribute(
                    SpanAttributes.MCP_RESPONSE_VALUE, f"{serialize(request.result)}"
                )
                if hasattr(request.result, "isError"):
                    if request.result.isError is True:
                        span.set_status(
                            Status(StatusCode.ERROR, f"{serialize(request.result)}")
                        )
            if hasattr(request, "id"):
                span.set_attribute(SpanAttributes.MCP_REQUEST_ID, f"{request.id}")

            if not isinstance(request, JSONRPCRequest):
                return await self.__wrapped__.send(item)
            meta = None
            if not request.params:
                request.params = {}
            meta = request.params.setdefault("_meta", {})

            propagate.get_global_textmap().inject(meta)
            return await self.__wrapped__.send(item)


@dataclass(slots=True, frozen=True)
class ItemWithContext:
    item: Any
    ctx: context.Context


class ContextSavingStreamWriter(ObjectProxy):  # type: ignore
    # ObjectProxy missing context manager - https://github.com/GrahamDumpleton/wrapt/issues/73
    def __init__(self, wrapped, tracer):
        super().__init__(wrapped)
        self._tracer = tracer

    async def __aenter__(self) -> Any:
        return await self.__wrapped__.__aenter__()

    async def __aexit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> Any:
        return await self.__wrapped__.__aexit__(exc_type, exc_value, traceback)

    @dont_throw
    async def send(self, item: Any) -> Any:
        with self._tracer.start_as_current_span("RequestStreamWriter") as span:
            if hasattr(item, "request_id"):
                span.set_attribute(SpanAttributes.MCP_REQUEST_ID, f"{item.request_id}")
            if hasattr(item, "request"):
                if hasattr(item.request, "root"):
                    if hasattr(item.request.root, "method"):
                        span.set_attribute(
                            SpanAttributes.MCP_METHOD_NAME,
                            f"{item.request.root.method}",
                        )
                    if hasattr(item.request.root, "params"):
                        span.set_attribute(
                            SpanAttributes.MCP_REQUEST_ARGUMENT,
                            f"{serialize(item.request.root.params)}",
                        )
            ctx = context.get_current()
            return await self.__wrapped__.send(ItemWithContext(item, ctx))


class ContextAttachingStreamReader(ObjectProxy):  # type: ignore
    # ObjectProxy missing context manager - https://github.com/GrahamDumpleton/wrapt/issues/73
    def __init__(self, wrapped, tracer):
        super().__init__(wrapped)
        self._tracer = tracer

    async def __aenter__(self) -> Any:
        return await self.__wrapped__.__aenter__()

    async def __aexit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> Any:
        return await self.__wrapped__.__aexit__(exc_type, exc_value, traceback)

    async def __aiter__(self) -> AsyncGenerator[Any, None]:
        async for item in self.__wrapped__:
            item_with_context = cast(ItemWithContext, item)
            restore = context.attach(item_with_context.ctx)
            try:
                yield item_with_context.item
            finally:
                context.detach(restore)
