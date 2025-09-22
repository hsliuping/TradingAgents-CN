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
This module implements experimental propagators to inject trace context
into response carriers. This is useful for server side frameworks that start traces
when server requests and want to share the trace context with the client so the
client can add its spans to the same trace.

This is part of an upcoming W3C spec and will eventually make it to the Otel spec.

https://w3c.github.io/trace-context/#trace-context-http-response-headers-format
"""

import typing
from abc import ABC, abstractmethod

from opentelemetry import trace
from opentelemetry.context.context import Context
from opentelemetry.propagators import textmap
from opentelemetry.trace import format_span_id, format_trace_id

_HTTP_HEADER_ACCESS_CONTROL_EXPOSE_HEADERS = "Access-Control-Expose-Headers"
_RESPONSE_PROPAGATOR = None


def get_global_response_propagator():
    return _RESPONSE_PROPAGATOR


def set_global_response_propagator(propagator):
    global _RESPONSE_PROPAGATOR  # pylint:disable=global-statement
    _RESPONSE_PROPAGATOR = propagator


class Setter(ABC):
    @abstractmethod
    def set(self, carrier, key, value):
        """Inject the provided key value pair in carrier."""


class DictHeaderSetter(Setter):
    def set(self, carrier, key, value):  # pylint: disable=no-self-use
        old_value = carrier.get(key, "")
        if old_value:
            value = f"{old_value}, {value}"
        carrier[key] = value


class FuncSetter(Setter):
    """FuncSetter converts a function into a valid Setter. Any function that
    can set values in a carrier can be converted into a Setter by using
    FuncSetter. This is useful when injecting trace context into non-dict
    objects such HTTP Response objects for different framework.

    For example, it can be used to create a setter for Falcon response object
    as:

        setter = FuncSetter(falcon.api.Response.append_header)

    and then used with the propagator as:

        propagator.inject(falcon_response, setter=setter)

    This would essentially make the propagator call `falcon_response.append_header(key, value)`
    """

    def __init__(self, func):
        self._func = func

    def set(self, carrier, key, value):
        self._func(carrier, key, value)


default_setter = DictHeaderSetter()


class ResponsePropagator(ABC):
    @abstractmethod
    def inject(
        self,
        carrier: textmap.CarrierT,
        context: typing.Optional[Context] = None,
        setter: textmap.Setter = default_setter,
    ) -> None:
        """Injects SpanContext into the HTTP response carrier."""


class TraceResponsePropagator(ResponsePropagator):
    """Experimental propagator that injects tracecontext into HTTP responses."""

    def inject(
        self,
        carrier: textmap.CarrierT,
        context: typing.Optional[Context] = None,
        setter: textmap.Setter = default_setter,
    ) -> None:
        """Injects SpanContext into the HTTP response carrier."""
        span = trace.get_current_span(context)
        span_context = span.get_span_context()
        if span_context == trace.INVALID_SPAN_CONTEXT:
            return

        header_name = "traceresponse"
        setter.set(
            carrier,
            header_name,
            f"00-{format_trace_id(span_context.trace_id)}-{format_span_id(span_context.span_id)}-{span_context.trace_flags:02x}",
        )
        setter.set(
            carrier,
            _HTTP_HEADER_ACCESS_CONTROL_EXPOSE_HEADERS,
            header_name,
        )
