"""SSRF-safe HTTPS transport for registered model provider endpoints.

The safety boundary is intentionally narrower than a general HTTP client:
only one pre-validated HTTPS origin and one path prefix are reachable, DNS is
resolved before a request, the TCP connection is pinned to the validated IP,
TLS still authenticates the registered hostname, proxies are disabled, and
redirects are never followed by credential-bearing requests.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import ipaddress
import re
import socket
import ssl
from typing import Iterable
from urllib.parse import unquote, urljoin, urlsplit, urlunsplit

import httpcore
import httpx
from httpcore._backends.sync import SyncBackend


_BLOCKED_HOSTS = frozenset(
    {
        "localhost",
        "localhost.localdomain",
        "metadata.google.internal",
        "metadata.azure.internal",
        "instance-data",
    }
)
_BLOCKED_HOST_SUFFIXES = (
    ".localhost",
    ".local",
    ".internal",
    ".lan",
    ".home",
    ".corp",
)
_REDIRECT_CODES = frozenset({301, 302, 303, 307, 308})
_INVALID_PERCENT_ESCAPE = re.compile(r"%(?![0-9A-Fa-f]{2})")


class EndpointSecurityError(ValueError):
    """A stable, non-secret endpoint validation failure."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ParsedEndpoint:
    base_url: str
    normalized_origin: str
    hostname: str
    port: int
    path_prefix: str


@dataclass(frozen=True)
class EndpointSafetyResult:
    base_url: str
    normalized_origin: str
    resolved_ips: tuple[str, ...]
    actual_peer_ip: str | None
    status_code: int | None
    redirect_status: str


def _fully_decode_path(value: str) -> str:
    """Decode nested escapes so downstream decoding cannot escape the base path."""
    current = value
    for _ in range(len(value) + 1):
        if _INVALID_PERCENT_ESCAPE.search(current):
            raise EndpointSecurityError("UNSAFE_PATH", "endpoint path has invalid escaping")
        try:
            decoded = unquote(current, errors="strict")
        except UnicodeDecodeError as exc:
            raise EndpointSecurityError(
                "UNSAFE_PATH", "endpoint path has invalid escaping"
            ) from exc
        if decoded == current:
            return decoded
        current = decoded
    raise EndpointSecurityError("UNSAFE_PATH", "endpoint path escaping is too deep")


def _safe_ip(value: str) -> str:
    try:
        parsed = ipaddress.ip_address(value.split("%", 1)[0])
    except ValueError as exc:
        raise EndpointSecurityError(
            "DNS_INVALID_ADDRESS", "endpoint DNS returned an invalid address"
        ) from exc
    if not parsed.is_global:
        raise EndpointSecurityError(
            "SSRF_UNSAFE_ADDRESS",
            "endpoint resolves to a non-public network address",
        )
    return parsed.compressed


def parse_registered_endpoint(value: str) -> ParsedEndpoint:
    candidate = value.strip()
    try:
        parsed = urlsplit(candidate)
        port = parsed.port
    except ValueError as exc:
        raise EndpointSecurityError(
            "INVALID_URL", "endpoint URL is invalid"
        ) from exc
    if parsed.scheme.lower() != "https":
        raise EndpointSecurityError(
            "HTTPS_REQUIRED", "model endpoints must use HTTPS"
        )
    if not parsed.hostname:
        raise EndpointSecurityError("HOST_REQUIRED", "endpoint host is required")
    if parsed.username is not None or parsed.password is not None:
        raise EndpointSecurityError(
            "URL_CREDENTIALS_FORBIDDEN",
            "endpoint URL cannot contain a username or password",
        )
    if parsed.fragment:
        raise EndpointSecurityError(
            "URL_FRAGMENT_FORBIDDEN", "endpoint URL cannot contain a fragment"
        )
    if parsed.query:
        raise EndpointSecurityError(
            "URL_QUERY_FORBIDDEN", "endpoint base URL cannot contain a query"
        )
    try:
        hostname = parsed.hostname.rstrip(".").encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise EndpointSecurityError(
            "INVALID_HOSTNAME", "endpoint hostname is invalid"
        ) from exc
    if (
        hostname in _BLOCKED_HOSTS
        or any(hostname.endswith(suffix) for suffix in _BLOCKED_HOST_SUFFIXES)
    ):
        raise EndpointSecurityError(
            "SSRF_INTERNAL_HOSTNAME", "internal endpoint hostnames are forbidden"
        )
    try:
        _safe_ip(hostname)
    except EndpointSecurityError:
        try:
            ipaddress.ip_address(hostname)
        except ValueError:
            pass
        else:
            raise
    normalized_port = port or 443
    if normalized_port < 1 or normalized_port > 65535:
        raise EndpointSecurityError("INVALID_PORT", "endpoint port is invalid")
    path = parsed.path or "/"
    decoded_path = _fully_decode_path(path)
    if "\\" in decoded_path or "\x00" in decoded_path:
        raise EndpointSecurityError("UNSAFE_PATH", "endpoint base path is unsafe")
    path_parts = [part for part in decoded_path.split("/") if part]
    if any(part in {".", ".."} for part in path_parts):
        raise EndpointSecurityError(
            "UNSAFE_PATH", "endpoint base path cannot contain dot segments"
        )
    normalized_path = "/" + "/".join(path_parts)
    if path.endswith("/") and normalized_path != "/":
        normalized_path += "/"
    host_for_url = f"[{hostname}]" if ":" in hostname else hostname
    authority = (
        host_for_url
        if normalized_port == 443
        else f"{host_for_url}:{normalized_port}"
    )
    origin = f"https://{authority}"
    return ParsedEndpoint(
        base_url=urlunsplit(("https", authority, normalized_path, "", "")),
        normalized_origin=origin,
        hostname=hostname,
        port=normalized_port,
        path_prefix=normalized_path.rstrip("/") or "/",
    )


def _default_resolve(hostname: str, port: int) -> list[str]:
    addresses = {
        item[4][0]
        for item in socket.getaddrinfo(
            hostname,
            port,
            type=socket.SOCK_STREAM,
            proto=socket.IPPROTO_TCP,
        )
    }
    if not addresses:
        raise EndpointSecurityError(
            "DNS_NO_RESULTS", "endpoint hostname did not resolve"
        )
    return sorted(addresses)


class _PinnedSyncBackend(SyncBackend):
    def __init__(self, *, expected_host: str, pinned_ip: str):
        self.expected_host = expected_host
        self.pinned_ip = pinned_ip
        self.actual_peer_ip: str | None = None

    def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[tuple] | None = None,
    ):
        normalized_host = (
            host.decode("ascii") if isinstance(host, bytes) else str(host)
        ).rstrip(".").lower()
        if normalized_host != self.expected_host:
            raise EndpointSecurityError(
                "SSRF_ORIGIN_ESCAPE",
                "request attempted to connect outside the registered origin",
            )
        stream = super().connect_tcp(
            self.pinned_ip,
            port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )
        peer = stream.get_extra_info("server_addr")
        actual = _safe_ip(str(peer[0])) if peer else self.pinned_ip
        if actual != self.pinned_ip:
            stream.close()
            raise EndpointSecurityError(
                "SSRF_PEER_MISMATCH",
                "actual connection peer differs from the pinned endpoint IP",
            )
        self.actual_peer_ip = actual
        return stream


class PinnedHTTPSNetworkTransport(httpx.HTTPTransport):
    def __init__(self, *, endpoint: ParsedEndpoint, pinned_ip: str):
        super().__init__(trust_env=False, http1=True, http2=False, retries=0)
        self._pool.close()
        self.endpoint = endpoint
        self.backend = _PinnedSyncBackend(
            expected_host=endpoint.hostname,
            pinned_ip=_safe_ip(pinned_ip),
        )
        self._pool = httpcore.ConnectionPool(
            ssl_context=ssl.create_default_context(),
            max_connections=4,
            max_keepalive_connections=2,
            keepalive_expiry=15,
            http1=True,
            http2=False,
            retries=0,
            network_backend=self.backend,
        )

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        request_host = (request.url.host or "").rstrip(".").lower()
        request_port = request.url.port or 443
        if (
            request.url.scheme != "https"
            or request_host != self.endpoint.hostname
            or request_port != self.endpoint.port
        ):
            raise EndpointSecurityError(
                "SSRF_ORIGIN_ESCAPE",
                "request attempted to leave the registered endpoint origin",
            )
        request_path = _fully_decode_path(request.url.path).rstrip("/") or "/"
        if "\\" in request_path or any(
            part in {".", ".."} for part in request_path.split("/")
        ):
            raise EndpointSecurityError(
                "SSRF_PATH_ESCAPE", "request path is outside the safe base path"
            )
        prefix = self.endpoint.path_prefix.rstrip("/") or "/"
        if prefix != "/" and not (
            request_path == prefix or request_path.startswith(f"{prefix}/")
        ):
            raise EndpointSecurityError(
                "SSRF_PATH_ESCAPE",
                "request attempted to leave the registered endpoint base path",
            )
        response = super().handle_request(request)
        stream = response.extensions.get("network_stream")
        peer = stream.get_extra_info("server_addr") if stream else None
        if peer and _safe_ip(str(peer[0])) != self.backend.pinned_ip:
            response.close()
            raise EndpointSecurityError(
                "SSRF_PEER_MISMATCH",
                "actual connection peer differs from the pinned endpoint IP",
            )
        return response


class EndpointAuth(httpx.Auth):
    """Attach exactly the registered authentication scheme in memory."""

    def __init__(self, *, scheme: str, secret: str):
        self.scheme = scheme
        self.secret = secret

    def auth_flow(self, request: httpx.Request):
        request.headers.pop("authorization", None)
        request.headers.pop("x-api-key", None)
        if self.scheme == "BEARER":
            request.headers["authorization"] = f"Bearer {self.secret}"
        elif self.scheme == "X_API_KEY":
            request.headers["x-api-key"] = self.secret
        else:  # pragma: no cover - schema validation owns this branch.
            raise EndpointSecurityError(
                "AUTH_SCHEME_UNSUPPORTED", "endpoint auth scheme is unsupported"
            )
        yield request


def build_pinned_client(
    *,
    endpoint: ParsedEndpoint,
    resolved_ips: Iterable[str],
    timeout_seconds: float,
    secret: str | None = None,
    auth_scheme: str | None = None,
) -> httpx.Client:
    safe_ips = tuple(_safe_ip(item) for item in resolved_ips)
    if not safe_ips:
        raise EndpointSecurityError(
            "DNS_NO_RESULTS", "endpoint has no validated public address"
        )
    auth = (
        EndpointAuth(scheme=auth_scheme or "BEARER", secret=secret)
        if secret is not None
        else None
    )
    return httpx.Client(
        transport=PinnedHTTPSNetworkTransport(
            endpoint=endpoint, pinned_ip=safe_ips[0]
        ),
        timeout=httpx.Timeout(timeout_seconds),
        follow_redirects=False,
        trust_env=False,
        auth=auth,
        headers={"user-agent": "AlphaGuard-ModelEndpointValidator/1"},
    )


class EndpointSafetyValidator:
    def __init__(self, *, resolver=None):
        self.resolver = resolver or _default_resolve

    async def resolve(self, endpoint: ParsedEndpoint) -> tuple[str, ...]:
        raw = await asyncio.to_thread(
            self.resolver, endpoint.hostname, endpoint.port
        )
        resolved = tuple(sorted({_safe_ip(item) for item in raw}))
        if not resolved:
            raise EndpointSecurityError(
                "DNS_NO_RESULTS", "endpoint hostname did not resolve"
            )
        return resolved

    async def validate(self, base_url: str) -> EndpointSafetyResult:
        endpoint = parse_registered_endpoint(base_url)
        resolved = await self.resolve(endpoint)

        def probe() -> tuple[int, str, str | None]:
            with build_pinned_client(
                endpoint=endpoint,
                resolved_ips=resolved,
                timeout_seconds=15,
            ) as client:
                response = client.get(endpoint.base_url)
                redirect_status = "NONE"
                if response.status_code in _REDIRECT_CODES:
                    location = response.headers.get("location")
                    if not location:
                        raise EndpointSecurityError(
                            "REDIRECT_INVALID", "endpoint redirect has no location"
                        )
                    target = parse_registered_endpoint(
                        urljoin(endpoint.base_url, location)
                    )
                    if target.normalized_origin != endpoint.normalized_origin:
                        raise EndpointSecurityError(
                            "CROSS_ORIGIN_REDIRECT",
                            "cross-origin endpoint redirects are forbidden",
                        )
                    redirect_status = "SAME_ORIGIN_REJECTED_FOR_EXPLICIT_REVIEW"
                transport = client._transport
                peer = getattr(
                    getattr(transport, "backend", None),
                    "actual_peer_ip",
                    None,
                )
                return response.status_code, redirect_status, peer

        try:
            status_code, redirect_status, peer = await asyncio.to_thread(probe)
        except EndpointSecurityError:
            raise
        except Exception as exc:
            raise EndpointSecurityError(
                "ENDPOINT_UNREACHABLE",
                f"endpoint HTTPS probe failed: {exc.__class__.__name__}",
            ) from exc
        return EndpointSafetyResult(
            base_url=endpoint.base_url,
            normalized_origin=endpoint.normalized_origin,
            resolved_ips=resolved,
            actual_peer_ip=peer,
            status_code=status_code,
            redirect_status=redirect_status,
        )
