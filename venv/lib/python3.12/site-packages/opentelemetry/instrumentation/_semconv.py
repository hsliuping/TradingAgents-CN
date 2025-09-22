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

import os
import threading
from enum import Enum

from opentelemetry.instrumentation.utils import http_status_to_status_code
from opentelemetry.semconv.attributes.client_attributes import (
    CLIENT_ADDRESS,
    CLIENT_PORT,
)
from opentelemetry.semconv.attributes.error_attributes import ERROR_TYPE
from opentelemetry.semconv.attributes.http_attributes import (
    HTTP_REQUEST_METHOD,
    HTTP_REQUEST_METHOD_ORIGINAL,
    HTTP_RESPONSE_STATUS_CODE,
    HTTP_ROUTE,
)
from opentelemetry.semconv.attributes.network_attributes import (
    NETWORK_PROTOCOL_VERSION,
)
from opentelemetry.semconv.attributes.server_attributes import (
    SERVER_ADDRESS,
    SERVER_PORT,
)
from opentelemetry.semconv.attributes.url_attributes import (
    URL_FULL,
    URL_PATH,
    URL_QUERY,
    URL_SCHEME,
)
from opentelemetry.semconv.attributes.user_agent_attributes import (
    USER_AGENT_ORIGINAL,
)
from opentelemetry.semconv.trace import SpanAttributes
from opentelemetry.trace.status import Status, StatusCode

# Values defined in milliseconds
HTTP_DURATION_HISTOGRAM_BUCKETS_OLD = (
    0.0,
    5.0,
    10.0,
    25.0,
    50.0,
    75.0,
    100.0,
    250.0,
    500.0,
    750.0,
    1000.0,
    2500.0,
    5000.0,
    7500.0,
    10000.0,
)

# Values defined in seconds
HTTP_DURATION_HISTOGRAM_BUCKETS_NEW = (
    0.005,
    0.01,
    0.025,
    0.05,
    0.075,
    0.1,
    0.25,
    0.5,
    0.75,
    1,
    2.5,
    5,
    7.5,
    10,
)

# These lists represent attributes for metrics that are currently supported

_client_duration_attrs_old = [
    SpanAttributes.HTTP_STATUS_CODE,
    SpanAttributes.HTTP_HOST,
    SpanAttributes.NET_PEER_PORT,
    SpanAttributes.NET_PEER_NAME,
    SpanAttributes.HTTP_METHOD,
    SpanAttributes.HTTP_FLAVOR,
    SpanAttributes.HTTP_SCHEME,
]

_client_duration_attrs_new = [
    ERROR_TYPE,
    HTTP_REQUEST_METHOD,
    HTTP_RESPONSE_STATUS_CODE,
    NETWORK_PROTOCOL_VERSION,
    SERVER_ADDRESS,
    SERVER_PORT,
    # TODO: Support opt-in for scheme in new semconv
    # URL_SCHEME,
]

_server_duration_attrs_old = [
    SpanAttributes.HTTP_METHOD,
    SpanAttributes.HTTP_HOST,
    SpanAttributes.HTTP_SCHEME,
    SpanAttributes.HTTP_STATUS_CODE,
    SpanAttributes.HTTP_FLAVOR,
    SpanAttributes.HTTP_SERVER_NAME,
    SpanAttributes.NET_HOST_NAME,
    SpanAttributes.NET_HOST_PORT,
]

_server_duration_attrs_new = [
    ERROR_TYPE,
    HTTP_REQUEST_METHOD,
    HTTP_RESPONSE_STATUS_CODE,
    HTTP_ROUTE,
    NETWORK_PROTOCOL_VERSION,
    URL_SCHEME,
]

_server_active_requests_count_attrs_old = [
    SpanAttributes.HTTP_METHOD,
    SpanAttributes.HTTP_HOST,
    SpanAttributes.HTTP_SCHEME,
    SpanAttributes.HTTP_FLAVOR,
    SpanAttributes.HTTP_SERVER_NAME,
]

_server_active_requests_count_attrs_new = [
    HTTP_REQUEST_METHOD,
    URL_SCHEME,
    # TODO: Support SERVER_ADDRESS AND SERVER_PORT
]

OTEL_SEMCONV_STABILITY_OPT_IN = "OTEL_SEMCONV_STABILITY_OPT_IN"


class _OpenTelemetryStabilitySignalType:
    HTTP = "http"
    DATABASE = "database"


class _StabilityMode(Enum):
    DEFAULT = "default"
    HTTP = "http"
    HTTP_DUP = "http/dup"
    DATABASE = "database"
    DATABASE_DUP = "database/dup"


def _report_new(mode: _StabilityMode):
    return mode != _StabilityMode.DEFAULT


def _report_old(mode: _StabilityMode):
    return mode not in (_StabilityMode.HTTP, _StabilityMode.DATABASE)


class _OpenTelemetrySemanticConventionStability:
    _initialized = False
    _lock = threading.Lock()
    _OTEL_SEMCONV_STABILITY_SIGNAL_MAPPING = {}

    @classmethod
    def _initialize(cls):
        with cls._lock:
            if cls._initialized:
                return

            # Users can pass in comma delimited string for opt-in options
            # Only values for http and database stability are supported for now
            opt_in = os.environ.get(OTEL_SEMCONV_STABILITY_OPT_IN)

            if not opt_in:
                # early return in case of default
                cls._OTEL_SEMCONV_STABILITY_SIGNAL_MAPPING = {
                    _OpenTelemetryStabilitySignalType.HTTP: _StabilityMode.DEFAULT,
                    _OpenTelemetryStabilitySignalType.DATABASE: _StabilityMode.DEFAULT,
                }
                cls._initialized = True
                return

            opt_in_list = [s.strip() for s in opt_in.split(",")]

            cls._OTEL_SEMCONV_STABILITY_SIGNAL_MAPPING[
                _OpenTelemetryStabilitySignalType.HTTP
            ] = cls._filter_mode(
                opt_in_list, _StabilityMode.HTTP, _StabilityMode.HTTP_DUP
            )

            cls._OTEL_SEMCONV_STABILITY_SIGNAL_MAPPING[
                _OpenTelemetryStabilitySignalType.DATABASE
            ] = cls._filter_mode(
                opt_in_list,
                _StabilityMode.DATABASE,
                _StabilityMode.DATABASE_DUP,
            )

            cls._initialized = True

    @staticmethod
    def _filter_mode(opt_in_list, stable_mode, dup_mode):
        # Process semconv stability opt-in
        # http/dup,database/dup has higher precedence over http,database
        if dup_mode.value in opt_in_list:
            return dup_mode

        return (
            stable_mode
            if stable_mode.value in opt_in_list
            else _StabilityMode.DEFAULT
        )

    @classmethod
    def _get_opentelemetry_stability_opt_in_mode(
        cls, signal_type: _OpenTelemetryStabilitySignalType
    ) -> _StabilityMode:
        # Get OpenTelemetry opt-in mode based off of signal type (http, messaging, etc.)
        return cls._OTEL_SEMCONV_STABILITY_SIGNAL_MAPPING.get(
            signal_type, _StabilityMode.DEFAULT
        )


def _filter_semconv_duration_attrs(
    attrs,
    old_attrs,
    new_attrs,
    sem_conv_opt_in_mode=_StabilityMode.DEFAULT,
):
    filtered_attrs = {}
    # duration is two different metrics depending on sem_conv_opt_in_mode, so no DUP attributes
    allowed_attributes = (
        new_attrs if sem_conv_opt_in_mode == _StabilityMode.HTTP else old_attrs
    )
    for key, val in attrs.items():
        if key in allowed_attributes:
            filtered_attrs[key] = val
    return filtered_attrs


def _filter_semconv_active_request_count_attr(
    attrs,
    old_attrs,
    new_attrs,
    sem_conv_opt_in_mode=_StabilityMode.DEFAULT,
):
    filtered_attrs = {}
    if _report_old(sem_conv_opt_in_mode):
        for key, val in attrs.items():
            if key in old_attrs:
                filtered_attrs[key] = val
    if _report_new(sem_conv_opt_in_mode):
        for key, val in attrs.items():
            if key in new_attrs:
                filtered_attrs[key] = val
    return filtered_attrs


def set_string_attribute(result, key, value):
    if value:
        result[key] = value


def set_int_attribute(result, key, value):
    if value:
        try:
            result[key] = int(value)
        except ValueError:
            return


def _set_http_method(result, original, normalized, sem_conv_opt_in_mode):
    original = original.strip()
    normalized = normalized.strip()
    # See https://github.com/open-telemetry/semantic-conventions/blob/main/docs/http/http-spans.md#common-attributes
    # Method is case sensitive. "http.request.method_original" should not be sanitized or automatically capitalized.
    if original != normalized and _report_new(sem_conv_opt_in_mode):
        set_string_attribute(result, HTTP_REQUEST_METHOD_ORIGINAL, original)

    if _report_old(sem_conv_opt_in_mode):
        set_string_attribute(result, SpanAttributes.HTTP_METHOD, normalized)
    if _report_new(sem_conv_opt_in_mode):
        set_string_attribute(result, HTTP_REQUEST_METHOD, normalized)


def _set_http_status_code(result, code, sem_conv_opt_in_mode):
    if _report_old(sem_conv_opt_in_mode):
        set_int_attribute(result, SpanAttributes.HTTP_STATUS_CODE, code)
    if _report_new(sem_conv_opt_in_mode):
        set_int_attribute(result, HTTP_RESPONSE_STATUS_CODE, code)


def _set_http_url(result, url, sem_conv_opt_in_mode):
    if _report_old(sem_conv_opt_in_mode):
        set_string_attribute(result, SpanAttributes.HTTP_URL, url)
    if _report_new(sem_conv_opt_in_mode):
        set_string_attribute(result, URL_FULL, url)


def _set_http_scheme(result, scheme, sem_conv_opt_in_mode):
    if _report_old(sem_conv_opt_in_mode):
        set_string_attribute(result, SpanAttributes.HTTP_SCHEME, scheme)
    if _report_new(sem_conv_opt_in_mode):
        set_string_attribute(result, URL_SCHEME, scheme)


def _set_http_flavor_version(result, version, sem_conv_opt_in_mode):
    if _report_old(sem_conv_opt_in_mode):
        set_string_attribute(result, SpanAttributes.HTTP_FLAVOR, version)
    if _report_new(sem_conv_opt_in_mode):
        set_string_attribute(result, NETWORK_PROTOCOL_VERSION, version)


def _set_http_user_agent(result, user_agent, sem_conv_opt_in_mode):
    if _report_old(sem_conv_opt_in_mode):
        set_string_attribute(
            result, SpanAttributes.HTTP_USER_AGENT, user_agent
        )
    if _report_new(sem_conv_opt_in_mode):
        set_string_attribute(result, USER_AGENT_ORIGINAL, user_agent)


# Client


def _set_http_host_client(result, host, sem_conv_opt_in_mode):
    if _report_old(sem_conv_opt_in_mode):
        set_string_attribute(result, SpanAttributes.HTTP_HOST, host)
    if _report_new(sem_conv_opt_in_mode):
        set_string_attribute(result, SERVER_ADDRESS, host)


def _set_http_net_peer_name_client(result, peer_name, sem_conv_opt_in_mode):
    if _report_old(sem_conv_opt_in_mode):
        set_string_attribute(result, SpanAttributes.NET_PEER_NAME, peer_name)
    if _report_new(sem_conv_opt_in_mode):
        set_string_attribute(result, SERVER_ADDRESS, peer_name)


def _set_http_peer_port_client(result, port, sem_conv_opt_in_mode):
    if _report_old(sem_conv_opt_in_mode):
        set_int_attribute(result, SpanAttributes.NET_PEER_PORT, port)
    if _report_new(sem_conv_opt_in_mode):
        set_int_attribute(result, SERVER_PORT, port)


def _set_http_network_protocol_version(result, version, sem_conv_opt_in_mode):
    if _report_old(sem_conv_opt_in_mode):
        set_string_attribute(result, SpanAttributes.HTTP_FLAVOR, version)
    if _report_new(sem_conv_opt_in_mode):
        set_string_attribute(result, NETWORK_PROTOCOL_VERSION, version)


# Server


def _set_http_net_host(result, host, sem_conv_opt_in_mode):
    if _report_old(sem_conv_opt_in_mode):
        set_string_attribute(result, SpanAttributes.NET_HOST_NAME, host)
    if _report_new(sem_conv_opt_in_mode):
        set_string_attribute(result, SERVER_ADDRESS, host)


def _set_http_net_host_port(result, port, sem_conv_opt_in_mode):
    if _report_old(sem_conv_opt_in_mode):
        set_int_attribute(result, SpanAttributes.NET_HOST_PORT, port)
    if _report_new(sem_conv_opt_in_mode):
        set_int_attribute(result, SERVER_PORT, port)


def _set_http_target(result, target, path, query, sem_conv_opt_in_mode):
    if _report_old(sem_conv_opt_in_mode):
        set_string_attribute(result, SpanAttributes.HTTP_TARGET, target)
    if _report_new(sem_conv_opt_in_mode):
        if path:
            set_string_attribute(result, URL_PATH, path)
        if query:
            set_string_attribute(result, URL_QUERY, query)


def _set_http_host_server(result, host, sem_conv_opt_in_mode):
    if _report_old(sem_conv_opt_in_mode):
        set_string_attribute(result, SpanAttributes.HTTP_HOST, host)
    if _report_new(sem_conv_opt_in_mode):
        if not result.get(SERVER_ADDRESS):
            set_string_attribute(result, SERVER_ADDRESS, host)


# net.peer.ip -> net.sock.peer.addr
# https://github.com/open-telemetry/semantic-conventions/blob/40db676ca0e735aa84f242b5a0fb14e49438b69b/schemas/1.15.0#L18
# net.sock.peer.addr -> client.socket.address for server spans (TODO) AND client.address if missing
# https://github.com/open-telemetry/semantic-conventions/blob/v1.21.0/CHANGELOG.md#v1210-2023-07-13
# https://github.com/open-telemetry/semantic-conventions/blob/main/docs/non-normative/http-migration.md#common-attributes-across-http-client-and-server-spans
def _set_http_peer_ip_server(result, ip, sem_conv_opt_in_mode):
    if _report_old(sem_conv_opt_in_mode):
        set_string_attribute(result, SpanAttributes.NET_PEER_IP, ip)
    if _report_new(sem_conv_opt_in_mode):
        # Only populate if not already populated
        if not result.get(CLIENT_ADDRESS):
            set_string_attribute(result, CLIENT_ADDRESS, ip)


def _set_http_peer_port_server(result, port, sem_conv_opt_in_mode):
    if _report_old(sem_conv_opt_in_mode):
        set_int_attribute(result, SpanAttributes.NET_PEER_PORT, port)
    if _report_new(sem_conv_opt_in_mode):
        set_int_attribute(result, CLIENT_PORT, port)


def _set_http_net_peer_name_server(result, name, sem_conv_opt_in_mode):
    if _report_old(sem_conv_opt_in_mode):
        set_string_attribute(result, SpanAttributes.NET_PEER_NAME, name)
    if _report_new(sem_conv_opt_in_mode):
        set_string_attribute(result, CLIENT_ADDRESS, name)


def _set_status(
    span,
    metrics_attributes: dict,
    status_code: int,
    status_code_str: str,
    server_span: bool = True,
    sem_conv_opt_in_mode: _StabilityMode = _StabilityMode.DEFAULT,
):
    if status_code < 0:
        if _report_new(sem_conv_opt_in_mode):
            metrics_attributes[ERROR_TYPE] = status_code_str
        if span.is_recording():
            if _report_new(sem_conv_opt_in_mode):
                span.set_attribute(ERROR_TYPE, status_code_str)
            span.set_status(
                Status(
                    StatusCode.ERROR,
                    "Non-integer HTTP status: " + status_code_str,
                )
            )
    else:
        status = http_status_to_status_code(
            status_code, server_span=server_span
        )

        if _report_old(sem_conv_opt_in_mode):
            if span.is_recording():
                span.set_attribute(
                    SpanAttributes.HTTP_STATUS_CODE, status_code
                )
            metrics_attributes[SpanAttributes.HTTP_STATUS_CODE] = status_code
        if _report_new(sem_conv_opt_in_mode):
            if span.is_recording():
                span.set_attribute(HTTP_RESPONSE_STATUS_CODE, status_code)
            metrics_attributes[HTTP_RESPONSE_STATUS_CODE] = status_code
            if status == StatusCode.ERROR:
                if span.is_recording():
                    span.set_attribute(ERROR_TYPE, status_code_str)
                metrics_attributes[ERROR_TYPE] = status_code_str
        if span.is_recording():
            span.set_status(Status(status))


# Get schema version based off of opt-in mode
def _get_schema_url(mode: _StabilityMode) -> str:
    if mode is _StabilityMode.DEFAULT:
        return "https://opentelemetry.io/schemas/1.11.0"
    return SpanAttributes.SCHEMA_URL
