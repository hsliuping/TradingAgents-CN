# Copyright The OpenTelemetry Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
This library provides functionality to enrich HTTP client spans with IPs. It does
not create spans on its own.
"""

from __future__ import annotations

import contextlib
import http.client
import logging
import socket  # pylint:disable=unused-import # Used for typing
import typing
from typing import Any, Callable, Collection, TypedDict, cast

import wrapt

from opentelemetry import context
from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from opentelemetry.instrumentation.utils import unwrap
from opentelemetry.semconv._incubating.attributes.net_attributes import (
    NET_PEER_IP,
)
from opentelemetry.trace.span import Span

_STATE_KEY = "httpbase_instrumentation_state"

logger = logging.getLogger(__name__)

R = typing.TypeVar("R")


class HttpClientInstrumentor(BaseInstrumentor):
    def instrumentation_dependencies(self) -> Collection[str]:
        return ()  # This instruments http.client from stdlib; no extra deps.

    def _instrument(self, **kwargs: Any):
        """Instruments the http.client module (not creating spans on its own)"""
        _instrument()

    def _uninstrument(self, **kwargs: Any):
        _uninstrument()


def _remove_nonrecording(spanlist: list[Span]) -> bool:
    idx = len(spanlist) - 1
    while idx >= 0:
        if not spanlist[idx].is_recording():
            logger.debug("Span is not recording: %s", spanlist[idx])
            islast = idx + 1 == len(spanlist)
            if not islast:
                spanlist[idx] = spanlist[len(spanlist) - 1]
            spanlist.pop()
            if islast:
                if idx == 0:
                    return False  # We removed everything
                idx -= 1
        else:
            idx -= 1
    return True


def trysetip(
    conn: http.client.HTTPConnection, loglevel: int = logging.DEBUG
) -> bool:
    """Tries to set the net.peer.ip semantic attribute on the current span from the given
    HttpConnection.

    Returns False if the connection is not yet established, False if the IP was captured
    or there is no need to capture it.
    """

    state = _getstate()
    if not state:
        return True
    spanlist: typing.List[Span] = state.get("need_ip")
    if not spanlist:
        return True

    # Remove all non-recording spans from the list.
    if not _remove_nonrecording(spanlist):
        return True

    sock = "<property not accessed>"
    try:
        sock: typing.Optional[socket.socket] = conn.sock
        logger.debug("Got socket: %s", sock)
        if sock is None:
            return False
        addr = sock.getpeername()
        if addr and addr[0]:
            ip = addr[0]
    except Exception:  # pylint:disable=broad-except
        logger.log(
            loglevel,
            "Failed to get peer address from %s",
            sock,
            exc_info=True,
            stack_info=True,
        )
    else:
        for span in spanlist:
            span.set_attribute(NET_PEER_IP, ip)
    return True


def _instrumented_connect(
    wrapped: Callable[..., R],
    instance: http.client.HTTPConnection,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> R:
    result = wrapped(*args, **kwargs)
    trysetip(instance, loglevel=logging.WARNING)
    return result


def instrument_connect(module: type[Any], name: str = "connect"):
    """Instrument additional connect() methods, e.g. for derived classes."""

    wrapt.wrap_function_wrapper(
        module,
        name,
        _instrumented_connect,
    )


def _instrument():
    def instrumented_send(
        wrapped: Callable[..., R],
        instance: http.client.HTTPConnection,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> R:
        done = trysetip(instance)
        result = wrapped(*args, **kwargs)
        if not done:
            trysetip(instance, loglevel=logging.WARNING)
        return result

    wrapt.wrap_function_wrapper(
        http.client.HTTPConnection,
        "send",
        instrumented_send,
    )

    instrument_connect(http.client.HTTPConnection)
    # No need to instrument HTTPSConnection, as it calls super().connect()


class _ConnectionState(TypedDict):
    need_ip: list[Span]


def _getstate() -> _ConnectionState | None:
    return cast(_ConnectionState, context.get_value(_STATE_KEY))


@contextlib.contextmanager
def set_ip_on_next_http_connection(span: Span):
    state = _getstate()
    if not state:
        token = context.attach(
            context.set_value(_STATE_KEY, {"need_ip": [span]})
        )
        try:
            yield
        finally:
            context.detach(token)
    else:
        spans = state["need_ip"]
        spans.append(span)
        try:
            yield
        finally:
            try:
                spans.remove(span)
            except ValueError:  # Span might have become non-recording
                pass


def _uninstrument():
    unwrap(http.client.HTTPConnection, "send")
    unwrap(http.client.HTTPConnection, "connect")
