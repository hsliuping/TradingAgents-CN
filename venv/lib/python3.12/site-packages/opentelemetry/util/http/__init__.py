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

from __future__ import annotations

from collections.abc import Mapping
from os import environ
from re import IGNORECASE as RE_IGNORECASE
from re import compile as re_compile
from re import search
from typing import Callable, Iterable, overload
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from opentelemetry.semconv._incubating.attributes.http_attributes import (
    HTTP_FLAVOR,
    HTTP_HOST,
    HTTP_METHOD,
    HTTP_SCHEME,
    HTTP_SERVER_NAME,
    HTTP_STATUS_CODE,
)
from opentelemetry.semconv._incubating.attributes.net_attributes import (
    NET_HOST_NAME,
    NET_HOST_PORT,
)

OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_SANITIZE_FIELDS = (
    "OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_SANITIZE_FIELDS"
)
OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_SERVER_REQUEST = (
    "OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_SERVER_REQUEST"
)
OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_SERVER_RESPONSE = (
    "OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_SERVER_RESPONSE"
)

OTEL_PYTHON_INSTRUMENTATION_HTTP_CAPTURE_ALL_METHODS = (
    "OTEL_PYTHON_INSTRUMENTATION_HTTP_CAPTURE_ALL_METHODS"
)

# List of recommended metrics attributes
_duration_attrs = {
    HTTP_METHOD,
    HTTP_HOST,
    HTTP_SCHEME,
    HTTP_STATUS_CODE,
    HTTP_FLAVOR,
    HTTP_SERVER_NAME,
    NET_HOST_NAME,
    NET_HOST_PORT,
}

_active_requests_count_attrs = {
    HTTP_METHOD,
    HTTP_HOST,
    HTTP_SCHEME,
    HTTP_FLAVOR,
    HTTP_SERVER_NAME,
}

PARAMS_TO_REDACT = ["AWSAccessKeyId", "Signature", "sig", "X-Goog-Signature"]


class ExcludeList:
    """Class to exclude certain paths (given as a list of regexes) from tracing requests"""

    def __init__(self, excluded_urls: Iterable[str]):
        self._excluded_urls = excluded_urls
        if self._excluded_urls:
            self._regex = re_compile("|".join(excluded_urls))

    def url_disabled(self, url: str) -> bool:
        return bool(self._excluded_urls and search(self._regex, url))


class SanitizeValue:
    """Class to sanitize (remove sensitive data from) certain headers (given as a list of regexes)"""

    def __init__(self, sanitized_fields: Iterable[str]):
        self._sanitized_fields = sanitized_fields
        if self._sanitized_fields:
            self._regex = re_compile("|".join(sanitized_fields), RE_IGNORECASE)

    def sanitize_header_value(self, header: str, value: str) -> str:
        return (
            "[REDACTED]"
            if (self._sanitized_fields and search(self._regex, header))
            else value
        )

    def sanitize_header_values(
        self,
        headers: Mapping[str, str | list[str]],
        header_regexes: list[str],
        normalize_function: Callable[[str], str],
    ) -> dict[str, list[str]]:
        values: dict[str, list[str]] = {}

        if header_regexes:
            header_regexes_compiled = re_compile(
                "|".join(header_regexes),
                RE_IGNORECASE,
            )

            for header_name, header_value in headers.items():
                if header_regexes_compiled.fullmatch(header_name):
                    key = normalize_function(header_name.lower())
                    if isinstance(header_value, str):
                        values[key] = [
                            self.sanitize_header_value(
                                header_name, header_value
                            )
                        ]
                    else:
                        values[key] = [
                            self.sanitize_header_value(header_name, value)
                            for value in header_value
                        ]

        return values


_root = r"OTEL_PYTHON_{}"


def get_traced_request_attrs(instrumentation: str) -> list[str]:
    traced_request_attrs = environ.get(
        _root.format(f"{instrumentation}_TRACED_REQUEST_ATTRS")
    )
    if traced_request_attrs:
        return [
            traced_request_attr.strip()
            for traced_request_attr in traced_request_attrs.split(",")
        ]
    return []


def get_excluded_urls(instrumentation: str) -> ExcludeList:
    # Get instrumentation-specific excluded URLs. If not set, retrieve them
    # from generic variable.
    excluded_urls = environ.get(
        _root.format(f"{instrumentation}_EXCLUDED_URLS"),
        environ.get(_root.format("EXCLUDED_URLS"), ""),
    )

    return parse_excluded_urls(excluded_urls)


def parse_excluded_urls(excluded_urls: str) -> ExcludeList:
    """
    Small helper to put an arbitrary url list inside an ExcludeList
    """
    if excluded_urls:
        excluded_url_list = [
            excluded_url.strip() for excluded_url in excluded_urls.split(",")
        ]
    else:
        excluded_url_list = []

    return ExcludeList(excluded_url_list)


def remove_url_credentials(url: str) -> str:
    """Given a string url, replace the username and password with the keyword `REDACTED` only if it is a valid url"""
    try:
        parsed = urlparse(url)
        if all([parsed.scheme, parsed.netloc]):  # checks for valid url
            if "@" in parsed.netloc:
                _, _, host = parsed.netloc.rpartition("@")
                new_netloc = "REDACTED:REDACTED@" + host
                return urlunparse(
                    (
                        parsed.scheme,
                        new_netloc,
                        parsed.path,
                        parsed.params,
                        parsed.query,
                        parsed.fragment,
                    )
                )
    except ValueError:  # an unparsable url was passed
        pass
    return url


def normalise_request_header_name(header: str) -> str:
    key = header.lower().replace("-", "_")
    return f"http.request.header.{key}"


def normalise_response_header_name(header: str) -> str:
    key = header.lower().replace("-", "_")
    return f"http.response.header.{key}"


@overload
def sanitize_method(method: str) -> str: ...


@overload
def sanitize_method(method: None) -> None: ...


def sanitize_method(method: str | None) -> str | None:
    if method is None:
        return None
    method = method.upper()
    if (
        environ.get(OTEL_PYTHON_INSTRUMENTATION_HTTP_CAPTURE_ALL_METHODS)
        or
        # Based on https://www.rfc-editor.org/rfc/rfc7231#section-4.1 and https://www.rfc-editor.org/rfc/rfc5789#section-2.
        method
        in [
            "GET",
            "HEAD",
            "POST",
            "PUT",
            "DELETE",
            "CONNECT",
            "OPTIONS",
            "TRACE",
            "PATCH",
        ]
    ):
        return method
    return "_OTHER"


def get_custom_headers(env_var: str) -> list[str]:
    custom_headers = environ.get(env_var, None)
    if custom_headers:
        return [
            custom_headers.strip()
            for custom_headers in custom_headers.split(",")
        ]
    return []


def _parse_active_request_count_attrs(req_attrs):
    active_requests_count_attrs = {
        key: req_attrs[key]
        for key in _active_requests_count_attrs.intersection(req_attrs.keys())
    }
    return active_requests_count_attrs


def _parse_duration_attrs(req_attrs):
    duration_attrs = {
        key: req_attrs[key]
        for key in _duration_attrs.intersection(req_attrs.keys())
    }
    return duration_attrs


def _parse_url_query(url: str):
    parsed_url = urlparse(url)
    path = parsed_url.path
    query_params = parsed_url.query
    return path, query_params


def redact_query_parameters(url: str) -> str:
    """Given a string url, redact sensitive query parameter values"""
    try:
        parsed = urlparse(url)
        if not parsed.query:  # No query parameters to redact
            return url
        query_params = parse_qs(parsed.query)
        if not any(param in query_params for param in PARAMS_TO_REDACT):
            return url
        for param in PARAMS_TO_REDACT:
            if param in query_params:
                query_params[param] = ["REDACTED"]
        return urlunparse(
            (
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                parsed.params,
                urlencode(query_params, doseq=True),
                parsed.fragment,
            )
        )
    except ValueError:  # an unparsable url was passed
        return url


def redact_url(url: str) -> str:
    """Redact sensitive data from the URL, including credentials and query parameters."""
    url = remove_url_credentials(url)
    url = redact_query_parameters(url)
    return url
