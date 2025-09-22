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
This library allows tracing HTTP requests made by the
`requests <https://requests.readthedocs.io/en/master/>`_ library.

Usage
-----

.. code-block:: python

    import requests
    from opentelemetry.instrumentation.requests import RequestsInstrumentor

    # You can optionally pass a custom TracerProvider to instrument().
    RequestsInstrumentor().instrument()
    response = requests.get(url="https://www.example.org/")

Configuration
-------------

Request/Response hooks
**********************

The requests instrumentation supports extending tracing behavior with the help of
request and response hooks. These are functions that are called back by the instrumentation
right after a Span is created for a request and right before the span is finished processing a response respectively.
The hooks can be configured as follows:

.. code:: python

    import requests
    from opentelemetry.instrumentation.requests import RequestsInstrumentor

    # `request_obj` is an instance of requests.PreparedRequest
    def request_hook(span, request_obj):
        pass

    # `request_obj` is an instance of requests.PreparedRequest
    # `response` is an instance of requests.Response
    def response_hook(span, request_obj, response):
        pass

    RequestsInstrumentor().instrument(
        request_hook=request_hook, response_hook=response_hook
    )

Custom Duration Histogram Boundaries
************************************
To customize the duration histogram bucket boundaries used for HTTP client request duration metrics,
you can provide a list of values when instrumenting:

.. code:: python

    import requests
    from opentelemetry.instrumentation.requests import RequestsInstrumentor

    custom_boundaries = [0.0, 5.0, 10.0, 25.0, 50.0, 100.0]

    RequestsInstrumentor().instrument(
        duration_histogram_boundaries=custom_boundaries
    )

Exclude lists
*************
To exclude certain URLs from being tracked, set the environment variable ``OTEL_PYTHON_REQUESTS_EXCLUDED_URLS``
(or ``OTEL_PYTHON_EXCLUDED_URLS`` as fallback) with comma delimited regexes representing which URLs to exclude.

For example,

::

    export OTEL_PYTHON_REQUESTS_EXCLUDED_URLS="client/.*/info,healthcheck"

will exclude requests such as ``https://site/client/123/info`` and ``https://site/xyz/healthcheck``.

API
---
"""

from __future__ import annotations

import functools
import types
from timeit import default_timer
from typing import Any, Callable, Collection, Optional
from urllib.parse import urlparse

from requests.models import PreparedRequest, Response
from requests.sessions import Session
from requests.structures import CaseInsensitiveDict

from opentelemetry.instrumentation._semconv import (
    HTTP_DURATION_HISTOGRAM_BUCKETS_NEW,
    HTTP_DURATION_HISTOGRAM_BUCKETS_OLD,
    _client_duration_attrs_new,
    _client_duration_attrs_old,
    _filter_semconv_duration_attrs,
    _get_schema_url,
    _OpenTelemetrySemanticConventionStability,
    _OpenTelemetryStabilitySignalType,
    _report_new,
    _report_old,
    _set_http_host_client,
    _set_http_method,
    _set_http_net_peer_name_client,
    _set_http_network_protocol_version,
    _set_http_peer_port_client,
    _set_http_scheme,
    _set_http_url,
    _set_status,
    _StabilityMode,
)
from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from opentelemetry.instrumentation.requests.package import _instruments
from opentelemetry.instrumentation.requests.version import __version__
from opentelemetry.instrumentation.utils import (
    is_http_instrumentation_enabled,
    suppress_http_instrumentation,
)
from opentelemetry.metrics import Histogram, get_meter
from opentelemetry.propagate import inject
from opentelemetry.semconv.attributes.error_attributes import ERROR_TYPE
from opentelemetry.semconv.attributes.network_attributes import (
    NETWORK_PEER_ADDRESS,
    NETWORK_PEER_PORT,
)
from opentelemetry.semconv.metrics import MetricInstruments
from opentelemetry.semconv.metrics.http_metrics import (
    HTTP_CLIENT_REQUEST_DURATION,
)
from opentelemetry.trace import SpanKind, Tracer, get_tracer
from opentelemetry.trace.span import Span
from opentelemetry.util.http import (
    ExcludeList,
    get_excluded_urls,
    parse_excluded_urls,
    redact_url,
    sanitize_method,
)
from opentelemetry.util.http.httplib import set_ip_on_next_http_connection

_excluded_urls_from_env = get_excluded_urls("REQUESTS")

_RequestHookT = Optional[Callable[[Span, PreparedRequest], None]]
_ResponseHookT = Optional[Callable[[Span, PreparedRequest, Response], None]]


def _set_http_status_code_attribute(
    span,
    status_code,
    metric_attributes=None,
    sem_conv_opt_in_mode=_StabilityMode.DEFAULT,
):
    status_code_str = str(status_code)
    try:
        status_code = int(status_code)
    except ValueError:
        status_code = -1
    if metric_attributes is None:
        metric_attributes = {}
    # When we have durations we should set metrics only once
    # Also the decision to include status code on a histogram should
    # not be dependent on tracing decisions.
    _set_status(
        span,
        metric_attributes,
        status_code,
        status_code_str,
        server_span=False,
        sem_conv_opt_in_mode=sem_conv_opt_in_mode,
    )


# pylint: disable=unused-argument
# pylint: disable=R0915
def _instrument(
    tracer: Tracer,
    duration_histogram_old: Histogram,
    duration_histogram_new: Histogram,
    request_hook: _RequestHookT = None,
    response_hook: _ResponseHookT = None,
    excluded_urls: ExcludeList | None = None,
    sem_conv_opt_in_mode: _StabilityMode = _StabilityMode.DEFAULT,
):
    """Enables tracing of all requests calls that go through
    :code:`requests.session.Session.request` (this includes
    :code:`requests.get`, etc.)."""

    # Since
    # https://github.com/psf/requests/commit/d72d1162142d1bf8b1b5711c664fbbd674f349d1
    # (v0.7.0, Oct 23, 2011), get, post, etc are implemented via request which
    # again, is implemented via Session.request (`Session` was named `session`
    # before v1.0.0, Dec 17, 2012, see
    # https://github.com/psf/requests/commit/4e5c4a6ab7bb0195dececdd19bb8505b872fe120)

    wrapped_send = Session.send

    # pylint: disable-msg=too-many-locals,too-many-branches
    @functools.wraps(wrapped_send)
    def instrumented_send(
        self: Session, request: PreparedRequest, **kwargs: Any
    ):
        if excluded_urls and excluded_urls.url_disabled(request.url):
            return wrapped_send(self, request, **kwargs)

        def get_or_create_headers():
            request.headers = (
                request.headers
                if request.headers is not None
                else CaseInsensitiveDict()
            )
            return request.headers

        if not is_http_instrumentation_enabled():
            return wrapped_send(self, request, **kwargs)

        # See
        # https://github.com/open-telemetry/semantic-conventions/blob/main/docs/http/http-spans.md#http-client
        method = request.method
        span_name = get_default_span_name(method)

        url = redact_url(request.url)

        span_attributes = {}
        _set_http_method(
            span_attributes,
            method,
            sanitize_method(method),
            sem_conv_opt_in_mode,
        )
        _set_http_url(span_attributes, url, sem_conv_opt_in_mode)

        metric_labels = {}
        _set_http_method(
            metric_labels,
            method,
            sanitize_method(method),
            sem_conv_opt_in_mode,
        )

        try:
            parsed_url = urlparse(url)
            if parsed_url.scheme:
                if _report_old(sem_conv_opt_in_mode):
                    # TODO: Support opt-in for url.scheme in new semconv
                    _set_http_scheme(
                        metric_labels, parsed_url.scheme, sem_conv_opt_in_mode
                    )
            if parsed_url.hostname:
                _set_http_host_client(
                    metric_labels, parsed_url.hostname, sem_conv_opt_in_mode
                )
                _set_http_net_peer_name_client(
                    metric_labels, parsed_url.hostname, sem_conv_opt_in_mode
                )
                if _report_new(sem_conv_opt_in_mode):
                    _set_http_host_client(
                        span_attributes,
                        parsed_url.hostname,
                        sem_conv_opt_in_mode,
                    )
                    # Use semconv library when available
                    span_attributes[NETWORK_PEER_ADDRESS] = parsed_url.hostname
            if parsed_url.port:
                _set_http_peer_port_client(
                    metric_labels, parsed_url.port, sem_conv_opt_in_mode
                )
                if _report_new(sem_conv_opt_in_mode):
                    _set_http_peer_port_client(
                        span_attributes, parsed_url.port, sem_conv_opt_in_mode
                    )
                    # Use semconv library when available
                    span_attributes[NETWORK_PEER_PORT] = parsed_url.port
        except ValueError:
            pass

        with (
            tracer.start_as_current_span(
                span_name, kind=SpanKind.CLIENT, attributes=span_attributes
            ) as span,
            set_ip_on_next_http_connection(span),
        ):
            exception = None
            if callable(request_hook):
                request_hook(span, request)

            headers = get_or_create_headers()
            inject(headers)

            with suppress_http_instrumentation():
                start_time = default_timer()
                try:
                    result = wrapped_send(
                        self, request, **kwargs
                    )  # *** PROCEED
                except Exception as exc:  # pylint: disable=W0703
                    exception = exc
                    result = getattr(exc, "response", None)
                finally:
                    elapsed_time = max(default_timer() - start_time, 0)

            if isinstance(result, Response):
                span_attributes = {}
                _set_http_status_code_attribute(
                    span,
                    result.status_code,
                    metric_labels,
                    sem_conv_opt_in_mode,
                )

                if result.raw is not None:
                    version = getattr(result.raw, "version", None)
                    if version:
                        # Only HTTP/1 is supported by requests
                        version_text = "1.1" if version == 11 else "1.0"
                        _set_http_network_protocol_version(
                            metric_labels, version_text, sem_conv_opt_in_mode
                        )
                        if _report_new(sem_conv_opt_in_mode):
                            _set_http_network_protocol_version(
                                span_attributes,
                                version_text,
                                sem_conv_opt_in_mode,
                            )
                for key, val in span_attributes.items():
                    span.set_attribute(key, val)

                if callable(response_hook):
                    response_hook(span, request, result)

            if exception is not None and _report_new(sem_conv_opt_in_mode):
                span.set_attribute(ERROR_TYPE, type(exception).__qualname__)
                metric_labels[ERROR_TYPE] = type(exception).__qualname__

            if duration_histogram_old is not None:
                duration_attrs_old = _filter_semconv_duration_attrs(
                    metric_labels,
                    _client_duration_attrs_old,
                    _client_duration_attrs_new,
                    _StabilityMode.DEFAULT,
                )
                duration_histogram_old.record(
                    max(round(elapsed_time * 1000), 0),
                    attributes=duration_attrs_old,
                )
            if duration_histogram_new is not None:
                duration_attrs_new = _filter_semconv_duration_attrs(
                    metric_labels,
                    _client_duration_attrs_old,
                    _client_duration_attrs_new,
                    _StabilityMode.HTTP,
                )
                duration_histogram_new.record(
                    elapsed_time, attributes=duration_attrs_new
                )

            if exception is not None:
                raise exception.with_traceback(exception.__traceback__)

        return result

    instrumented_send.opentelemetry_instrumentation_requests_applied = True
    Session.send = instrumented_send


def _uninstrument():
    """Disables instrumentation of :code:`requests` through this module.

    Note that this only works if no other module also patches requests."""
    _uninstrument_from(Session)


def _uninstrument_from(instr_root, restore_as_bound_func: bool = False):
    for instr_func_name in ("request", "send"):
        instr_func = getattr(instr_root, instr_func_name)
        if not getattr(
            instr_func,
            "opentelemetry_instrumentation_requests_applied",
            False,
        ):
            continue

        original = instr_func.__wrapped__  # pylint:disable=no-member
        if restore_as_bound_func:
            original = types.MethodType(original, instr_root)
        setattr(instr_root, instr_func_name, original)


def get_default_span_name(method: str) -> str:
    """
    Default implementation for name_callback, returns HTTP {method_name}.
    https://opentelemetry.io/docs/reference/specification/trace/semantic_conventions/http/#name

    Args:
        method: string representing HTTP method
    Returns:
        span name
    """
    method = sanitize_method(method.strip())
    if method == "_OTHER":
        return "HTTP"
    return method


class RequestsInstrumentor(BaseInstrumentor):
    """An instrumentor for requests
    See `BaseInstrumentor`
    """

    def instrumentation_dependencies(self) -> Collection[str]:
        return _instruments

    def _instrument(self, **kwargs: Any):
        """Instruments requests module

        Args:
            **kwargs: Optional arguments
                ``tracer_provider``: a TracerProvider, defaults to global
                ``request_hook``: An optional callback that is invoked right after a span is created.
                ``response_hook``: An optional callback which is invoked right before the span is finished processing a response.
                ``excluded_urls``: A string containing a comma-delimited list of regexes used to exclude URLs from tracking
                ``duration_histogram_boundaries``: A list of float values representing the explicit bucket boundaries for the duration histogram.
        """
        semconv_opt_in_mode = _OpenTelemetrySemanticConventionStability._get_opentelemetry_stability_opt_in_mode(
            _OpenTelemetryStabilitySignalType.HTTP,
        )
        schema_url = _get_schema_url(semconv_opt_in_mode)
        tracer_provider = kwargs.get("tracer_provider")
        tracer = get_tracer(
            __name__,
            __version__,
            tracer_provider,
            schema_url=schema_url,
        )
        excluded_urls = kwargs.get("excluded_urls")
        meter_provider = kwargs.get("meter_provider")
        duration_histogram_boundaries = kwargs.get(
            "duration_histogram_boundaries"
        )
        meter = get_meter(
            __name__,
            __version__,
            meter_provider,
            schema_url=schema_url,
        )
        duration_histogram_old = None
        if _report_old(semconv_opt_in_mode):
            duration_histogram_old = meter.create_histogram(
                name=MetricInstruments.HTTP_CLIENT_DURATION,
                unit="ms",
                description="measures the duration of the outbound HTTP request",
                explicit_bucket_boundaries_advisory=duration_histogram_boundaries
                or HTTP_DURATION_HISTOGRAM_BUCKETS_OLD,
            )
        duration_histogram_new = None
        if _report_new(semconv_opt_in_mode):
            duration_histogram_new = meter.create_histogram(
                name=HTTP_CLIENT_REQUEST_DURATION,
                unit="s",
                description="Duration of HTTP client requests.",
                explicit_bucket_boundaries_advisory=duration_histogram_boundaries
                or HTTP_DURATION_HISTOGRAM_BUCKETS_NEW,
            )
        _instrument(
            tracer,
            duration_histogram_old,
            duration_histogram_new,
            request_hook=kwargs.get("request_hook"),
            response_hook=kwargs.get("response_hook"),
            excluded_urls=(
                _excluded_urls_from_env
                if excluded_urls is None
                else parse_excluded_urls(excluded_urls)
            ),
            sem_conv_opt_in_mode=semconv_opt_in_mode,
        )

    def _uninstrument(self, **kwargs: Any):
        _uninstrument()

    @staticmethod
    def uninstrument_session(session: Session):
        """Disables instrumentation on the session object."""
        _uninstrument_from(session, restore_as_bound_func=True)
