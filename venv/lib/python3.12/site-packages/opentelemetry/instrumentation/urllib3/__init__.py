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
`urllib3 <https://urllib3.readthedocs.io/>`_ library.

Usage
-----
.. code-block:: python

    import urllib3
    from opentelemetry.instrumentation.urllib3 import URLLib3Instrumentor

    def strip_query_params(url: str) -> str:
        return url.split("?")[0]

    URLLib3Instrumentor().instrument(
        # Remove all query params from the URL attribute on the span.
        url_filter=strip_query_params,
    )

    http = urllib3.PoolManager()
    response = http.request("GET", "https://www.example.org/")

Configuration
-------------

Request/Response hooks
**********************

The urllib3 instrumentation supports extending tracing behavior with the help of
request and response hooks. These are functions that are called back by the instrumentation
right after a Span is created for a request and right before the span is finished processing a response respectively.
The hooks can be configured as follows:

.. code:: python

    from typing import Any

    from urllib3.connectionpool import HTTPConnectionPool
    from urllib3.response import HTTPResponse

    from opentelemetry.instrumentation.urllib3 import RequestInfo, URLLib3Instrumentor
    from opentelemetry.trace import Span

    def request_hook(
        span: Span,
        pool: HTTPConnectionPool,
        request_info: RequestInfo,
    ) -> Any:
        pass

    def response_hook(
        span: Span,
        pool: HTTPConnectionPool,
        response: HTTPResponse,
    ) -> Any:
        pass

    URLLib3Instrumentor().instrument(
        request_hook=request_hook,
        response_hook=response_hook,
    )

Exclude lists
*************

To exclude certain URLs from being tracked, set the environment variable ``OTEL_PYTHON_URLLIB3_EXCLUDED_URLS``
(or ``OTEL_PYTHON_EXCLUDED_URLS`` as fallback) with comma delimited regexes representing which URLs to exclude.

For example,

::

    export OTEL_PYTHON_URLLIB3_EXCLUDED_URLS="client/.*/info,healthcheck"

will exclude requests such as ``https://site/client/123/info`` and ``https://site/xyz/healthcheck``.

API
---
"""

import collections.abc
import io
import typing
from dataclasses import dataclass
from timeit import default_timer
from typing import Collection

import urllib3.connectionpool
import wrapt

from opentelemetry.instrumentation._semconv import (
    HTTP_DURATION_HISTOGRAM_BUCKETS_NEW,
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
from opentelemetry.instrumentation.urllib3.package import _instruments
from opentelemetry.instrumentation.urllib3.version import __version__
from opentelemetry.instrumentation.utils import (
    is_http_instrumentation_enabled,
    suppress_http_instrumentation,
    unwrap,
)
from opentelemetry.metrics import Histogram, get_meter
from opentelemetry.propagate import inject
from opentelemetry.semconv._incubating.metrics.http_metrics import (
    create_http_client_request_body_size,
    create_http_client_response_body_size,
)
from opentelemetry.semconv.metrics import MetricInstruments
from opentelemetry.semconv.metrics.http_metrics import (
    HTTP_CLIENT_REQUEST_DURATION,
)
from opentelemetry.trace import Span, SpanKind, Tracer, get_tracer
from opentelemetry.util.http import (
    ExcludeList,
    get_excluded_urls,
    parse_excluded_urls,
    sanitize_method,
)
from opentelemetry.util.http.httplib import set_ip_on_next_http_connection

_excluded_urls_from_env = get_excluded_urls("URLLIB3")


@dataclass
class RequestInfo:
    """Arguments that were passed to the ``urlopen()`` call."""

    __slots__ = ("method", "url", "headers", "body")

    # The type annotations here come from ``HTTPConnectionPool.urlopen()``.
    method: str
    url: str
    headers: typing.Optional[typing.Mapping[str, str]]
    body: typing.Union[
        bytes, typing.IO[typing.Any], typing.Iterable[bytes], str, None
    ]


_UrlFilterT = typing.Optional[typing.Callable[[str], str]]
_RequestHookT = typing.Optional[
    typing.Callable[
        [
            Span,
            urllib3.connectionpool.HTTPConnectionPool,
            RequestInfo,
        ],
        None,
    ]
]
_ResponseHookT = typing.Optional[
    typing.Callable[
        [
            Span,
            urllib3.connectionpool.HTTPConnectionPool,
            urllib3.response.HTTPResponse,
        ],
        None,
    ]
]

_URL_OPEN_ARG_TO_INDEX_MAPPING = {
    "method": 0,
    "url": 1,
    "body": 2,
}


class URLLib3Instrumentor(BaseInstrumentor):
    def instrumentation_dependencies(self) -> Collection[str]:
        return _instruments

    def _instrument(self, **kwargs):
        """Instruments the urllib3 module

        Args:
            **kwargs: Optional arguments
                ``tracer_provider``: a TracerProvider, defaults to global.
                ``request_hook``: An optional callback that is invoked right after a span is created.
                ``response_hook``: An optional callback which is invoked right before the span is finished processing a response.
                ``url_filter``: A callback to process the requested URL prior
                    to adding it as a span attribute.
                ``excluded_urls``: A string containing a comma-delimited
                    list of regexes used to exclude URLs from tracking
        """
        # initialize semantic conventions opt-in if needed
        _OpenTelemetrySemanticConventionStability._initialize()
        sem_conv_opt_in_mode = _OpenTelemetrySemanticConventionStability._get_opentelemetry_stability_opt_in_mode(
            _OpenTelemetryStabilitySignalType.HTTP,
        )
        schema_url = _get_schema_url(sem_conv_opt_in_mode)
        tracer_provider = kwargs.get("tracer_provider")
        tracer = get_tracer(
            __name__,
            __version__,
            tracer_provider,
            schema_url=schema_url,
        )

        excluded_urls = kwargs.get("excluded_urls")

        meter_provider = kwargs.get("meter_provider")
        meter = get_meter(
            __name__,
            __version__,
            meter_provider,
            schema_url=schema_url,
        )
        duration_histogram_old = None
        request_size_histogram_old = None
        response_size_histogram_old = None
        if _report_old(sem_conv_opt_in_mode):
            # http.client.duration histogram
            duration_histogram_old = meter.create_histogram(
                name=MetricInstruments.HTTP_CLIENT_DURATION,
                unit="ms",
                description="Measures the duration of the outbound HTTP request",
            )
            # http.client.request.size histogram
            request_size_histogram_old = meter.create_histogram(
                name=MetricInstruments.HTTP_CLIENT_REQUEST_SIZE,
                unit="By",
                description="Measures the size of HTTP request messages.",
            )
            # http.client.response.size histogram
            response_size_histogram_old = meter.create_histogram(
                name=MetricInstruments.HTTP_CLIENT_RESPONSE_SIZE,
                unit="By",
                description="Measures the size of HTTP response messages.",
            )

        duration_histogram_new = None
        request_size_histogram_new = None
        response_size_histogram_new = None
        if _report_new(sem_conv_opt_in_mode):
            # http.client.request.duration histogram
            duration_histogram_new = meter.create_histogram(
                name=HTTP_CLIENT_REQUEST_DURATION,
                unit="s",
                description="Duration of HTTP client requests.",
                explicit_bucket_boundaries_advisory=HTTP_DURATION_HISTOGRAM_BUCKETS_NEW,
            )
            # http.client.request.body.size histogram
            request_size_histogram_new = create_http_client_request_body_size(
                meter
            )
            # http.client.response.body.size histogram
            response_size_histogram_new = (
                create_http_client_response_body_size(meter)
            )
        _instrument(
            tracer,
            duration_histogram_old,
            duration_histogram_new,
            request_size_histogram_old,
            request_size_histogram_new,
            response_size_histogram_old,
            response_size_histogram_new,
            request_hook=kwargs.get("request_hook"),
            response_hook=kwargs.get("response_hook"),
            url_filter=kwargs.get("url_filter"),
            excluded_urls=(
                _excluded_urls_from_env
                if excluded_urls is None
                else parse_excluded_urls(excluded_urls)
            ),
            sem_conv_opt_in_mode=sem_conv_opt_in_mode,
        )

    def _uninstrument(self, **kwargs):
        _uninstrument()


def _get_span_name(method: str) -> str:
    method = sanitize_method(method.strip())
    if method == "_OTHER":
        method = "HTTP"
    return method


def _instrument(
    tracer: Tracer,
    duration_histogram_old: Histogram,
    duration_histogram_new: Histogram,
    request_size_histogram_old: Histogram,
    request_size_histogram_new: Histogram,
    response_size_histogram_old: Histogram,
    response_size_histogram_new: Histogram,
    request_hook: _RequestHookT = None,
    response_hook: _ResponseHookT = None,
    url_filter: _UrlFilterT = None,
    excluded_urls: ExcludeList = None,
    sem_conv_opt_in_mode: _StabilityMode = _StabilityMode.DEFAULT,
):
    def instrumented_urlopen(wrapped, instance, args, kwargs):
        if not is_http_instrumentation_enabled():
            return wrapped(*args, **kwargs)

        url = _get_url(instance, args, kwargs, url_filter)
        if excluded_urls and excluded_urls.url_disabled(url):
            return wrapped(*args, **kwargs)

        method = _get_url_open_arg("method", args, kwargs).upper()
        headers = _prepare_headers(kwargs)
        body = _get_url_open_arg("body", args, kwargs)

        span_name = _get_span_name(method)
        span_attributes = {}

        _set_http_method(
            span_attributes,
            method,
            sanitize_method(method),
            sem_conv_opt_in_mode,
        )
        _set_http_url(span_attributes, url, sem_conv_opt_in_mode)

        with (
            tracer.start_as_current_span(
                span_name, kind=SpanKind.CLIENT, attributes=span_attributes
            ) as span,
            set_ip_on_next_http_connection(span),
        ):
            if callable(request_hook):
                request_hook(
                    span,
                    instance,
                    RequestInfo(
                        method=method,
                        url=url,
                        headers=headers,
                        body=body,
                    ),
                )
            inject(headers)
            # TODO: add error handling to also set exception `error.type` in new semconv
            with suppress_http_instrumentation():
                start_time = default_timer()
                response = wrapped(*args, **kwargs)
                duration_s = default_timer() - start_time
            # set http status code based on semconv
            metric_attributes = {}
            _set_status_code_attribute(
                span, response.status, metric_attributes, sem_conv_opt_in_mode
            )

            if callable(response_hook):
                response_hook(span, instance, response)

            request_size = _get_body_size(body)
            response_size = int(response.headers.get("Content-Length", 0))

            _set_metric_attributes(
                metric_attributes,
                instance,
                response,
                method,
                sem_conv_opt_in_mode,
            )

            _record_metrics(
                metric_attributes,
                duration_histogram_old,
                duration_histogram_new,
                request_size_histogram_old,
                request_size_histogram_new,
                response_size_histogram_old,
                response_size_histogram_new,
                duration_s,
                request_size,
                response_size,
                sem_conv_opt_in_mode,
            )

            return response

    wrapt.wrap_function_wrapper(
        urllib3.connectionpool.HTTPConnectionPool,
        "urlopen",
        instrumented_urlopen,
    )


def _get_url_open_arg(name: str, args: typing.List, kwargs: typing.Mapping):
    arg_idx = _URL_OPEN_ARG_TO_INDEX_MAPPING.get(name)
    if arg_idx is not None:
        try:
            return args[arg_idx]
        except IndexError:
            pass
    return kwargs.get(name)


def _get_url(
    instance: urllib3.connectionpool.HTTPConnectionPool,
    args: typing.List,
    kwargs: typing.Mapping,
    url_filter: _UrlFilterT,
) -> str:
    url_or_path = _get_url_open_arg("url", args, kwargs)
    if not url_or_path.startswith("/"):
        url = url_or_path
    else:
        url = instance.scheme + "://" + instance.host
        if _should_append_port(instance.scheme, instance.port):
            url += ":" + str(instance.port)
        url += url_or_path

    if url_filter:
        return url_filter(url)
    return url


def _get_body_size(body: object) -> typing.Optional[int]:
    if body is None:
        return 0
    if isinstance(body, collections.abc.Sized):
        return len(body)
    if isinstance(body, io.BytesIO):
        return body.getbuffer().nbytes
    return None


def _should_append_port(scheme: str, port: typing.Optional[int]) -> bool:
    if not port:
        return False
    if scheme == "http" and port == 80:
        return False
    if scheme == "https" and port == 443:
        return False
    return True


def _prepare_headers(urlopen_kwargs: typing.Dict) -> typing.Dict:
    headers = urlopen_kwargs.get("headers")

    # avoid modifying original headers on inject
    headers = headers.copy() if headers is not None else {}
    urlopen_kwargs["headers"] = headers

    return headers


def _set_status_code_attribute(
    span: Span,
    status_code: int,
    metric_attributes: dict = None,
    sem_conv_opt_in_mode: _StabilityMode = _StabilityMode.DEFAULT,
) -> None:
    status_code_str = str(status_code)
    try:
        status_code = int(status_code)
    except ValueError:
        status_code = -1

    if metric_attributes is None:
        metric_attributes = {}

    _set_status(
        span,
        metric_attributes,
        status_code,
        status_code_str,
        server_span=False,
        sem_conv_opt_in_mode=sem_conv_opt_in_mode,
    )


def _set_metric_attributes(
    metric_attributes: dict,
    instance: urllib3.connectionpool.HTTPConnectionPool,
    response: urllib3.response.HTTPResponse,
    method: str,
    sem_conv_opt_in_mode: _StabilityMode = _StabilityMode.DEFAULT,
) -> None:
    _set_http_host_client(
        metric_attributes, instance.host, sem_conv_opt_in_mode
    )
    _set_http_scheme(metric_attributes, instance.scheme, sem_conv_opt_in_mode)
    _set_http_method(
        metric_attributes,
        method,
        sanitize_method(method),
        sem_conv_opt_in_mode,
    )
    _set_http_net_peer_name_client(
        metric_attributes, instance.host, sem_conv_opt_in_mode
    )
    _set_http_peer_port_client(
        metric_attributes, instance.port, sem_conv_opt_in_mode
    )

    version = getattr(response, "version")
    if version:
        http_version = "1.1" if version == 11 else "1.0"
        _set_http_network_protocol_version(
            metric_attributes, http_version, sem_conv_opt_in_mode
        )


def _filter_attributes_semconv(
    metric_attributes,
    sem_conv_opt_in_mode: _StabilityMode = _StabilityMode.DEFAULT,
):
    duration_attrs_old = None
    duration_attrs_new = None
    if _report_old(sem_conv_opt_in_mode):
        duration_attrs_old = _filter_semconv_duration_attrs(
            metric_attributes,
            _client_duration_attrs_old,
            _client_duration_attrs_new,
            _StabilityMode.DEFAULT,
        )
    if _report_new(sem_conv_opt_in_mode):
        duration_attrs_new = _filter_semconv_duration_attrs(
            metric_attributes,
            _client_duration_attrs_old,
            _client_duration_attrs_new,
            _StabilityMode.HTTP,
        )

    return (duration_attrs_old, duration_attrs_new)


def _record_metrics(
    metric_attributes: dict,
    duration_histogram_old: Histogram,
    duration_histogram_new: Histogram,
    request_size_histogram_old: Histogram,
    request_size_histogram_new: Histogram,
    response_size_histogram_old: Histogram,
    response_size_histogram_new: Histogram,
    duration_s: float,
    request_size: typing.Optional[int],
    response_size: int,
    sem_conv_opt_in_mode: _StabilityMode = _StabilityMode.DEFAULT,
):
    attrs_old, attrs_new = _filter_attributes_semconv(
        metric_attributes, sem_conv_opt_in_mode
    )
    if duration_histogram_old:
        # Default behavior is to record the duration in milliseconds
        duration_histogram_old.record(
            max(round(duration_s * 1000), 0),
            attributes=attrs_old,
        )

    if duration_histogram_new:
        # New semconv record the duration in seconds
        duration_histogram_new.record(
            duration_s,
            attributes=attrs_new,
        )

    if request_size is not None:
        if request_size_histogram_old:
            request_size_histogram_old.record(
                request_size, attributes=attrs_old
            )

        if request_size_histogram_new:
            request_size_histogram_new.record(
                request_size, attributes=attrs_new
            )

    if response_size_histogram_old:
        response_size_histogram_old.record(response_size, attributes=attrs_old)

    if response_size_histogram_new:
        response_size_histogram_new.record(response_size, attributes=attrs_new)


def _uninstrument():
    unwrap(urllib3.connectionpool.HTTPConnectionPool, "urlopen")
