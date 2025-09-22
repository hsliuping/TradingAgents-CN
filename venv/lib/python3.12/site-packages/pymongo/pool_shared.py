# Copyright 2025-present MongoDB, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Pool utilities and shared helper methods."""
from __future__ import annotations

import asyncio
import functools
import socket
import ssl
import sys
from typing import (
    TYPE_CHECKING,
    Any,
    NoReturn,
    Optional,
    Union,
)

from pymongo import _csot
from pymongo.asynchronous.helpers import _getaddrinfo
from pymongo.errors import (  # type:ignore[attr-defined]
    AutoReconnect,
    ConnectionFailure,
    NetworkTimeout,
    _CertificateError,
)
from pymongo.network_layer import AsyncNetworkingInterface, NetworkingInterface, PyMongoProtocol
from pymongo.pool_options import PoolOptions
from pymongo.ssl_support import PYSSLError, SSLError, _has_sni

SSLErrors = (PYSSLError, SSLError)
if TYPE_CHECKING:
    from pymongo.pyopenssl_context import _sslConn
    from pymongo.typings import _Address

try:
    from fcntl import F_GETFD, F_SETFD, FD_CLOEXEC, fcntl

    def _set_non_inheritable_non_atomic(fd: int) -> None:
        """Set the close-on-exec flag on the given file descriptor."""
        flags = fcntl(fd, F_GETFD)
        fcntl(fd, F_SETFD, flags | FD_CLOEXEC)

except ImportError:
    # Windows, various platforms we don't claim to support
    # (Jython, IronPython, ..), systems that don't provide
    # everything we need from fcntl, etc.
    def _set_non_inheritable_non_atomic(fd: int) -> None:  # noqa: ARG001
        """Dummy function for platforms that don't provide fcntl."""


_MAX_TCP_KEEPIDLE = 120
_MAX_TCP_KEEPINTVL = 10
_MAX_TCP_KEEPCNT = 9

if sys.platform == "win32":
    try:
        import _winreg as winreg
    except ImportError:
        import winreg

    def _query(key, name, default):
        try:
            value, _ = winreg.QueryValueEx(key, name)
            # Ensure the value is a number or raise ValueError.
            return int(value)
        except (OSError, ValueError):
            # QueryValueEx raises OSError when the key does not exist (i.e.
            # the system is using the Windows default value).
            return default

    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters"
        ) as key:
            _WINDOWS_TCP_IDLE_MS = _query(key, "KeepAliveTime", 7200000)
            _WINDOWS_TCP_INTERVAL_MS = _query(key, "KeepAliveInterval", 1000)
    except OSError:
        # We could not check the default values because winreg.OpenKey failed.
        # Assume the system is using the default values.
        _WINDOWS_TCP_IDLE_MS = 7200000
        _WINDOWS_TCP_INTERVAL_MS = 1000

    def _set_keepalive_times(sock):
        idle_ms = min(_WINDOWS_TCP_IDLE_MS, _MAX_TCP_KEEPIDLE * 1000)
        interval_ms = min(_WINDOWS_TCP_INTERVAL_MS, _MAX_TCP_KEEPINTVL * 1000)
        if idle_ms < _WINDOWS_TCP_IDLE_MS or interval_ms < _WINDOWS_TCP_INTERVAL_MS:
            sock.ioctl(socket.SIO_KEEPALIVE_VALS, (1, idle_ms, interval_ms))

else:

    def _set_tcp_option(sock: socket.socket, tcp_option: str, max_value: int) -> None:
        if hasattr(socket, tcp_option):
            sockopt = getattr(socket, tcp_option)
            try:
                # PYTHON-1350 - NetBSD doesn't implement getsockopt for
                # TCP_KEEPIDLE and friends. Don't attempt to set the
                # values there.
                default = sock.getsockopt(socket.IPPROTO_TCP, sockopt)
                if default > max_value:
                    sock.setsockopt(socket.IPPROTO_TCP, sockopt, max_value)
            except OSError:
                pass

    def _set_keepalive_times(sock: socket.socket) -> None:
        _set_tcp_option(sock, "TCP_KEEPIDLE", _MAX_TCP_KEEPIDLE)
        _set_tcp_option(sock, "TCP_KEEPINTVL", _MAX_TCP_KEEPINTVL)
        _set_tcp_option(sock, "TCP_KEEPCNT", _MAX_TCP_KEEPCNT)


def _raise_connection_failure(
    address: Any,
    error: Exception,
    msg_prefix: Optional[str] = None,
    timeout_details: Optional[dict[str, float]] = None,
) -> NoReturn:
    """Convert a socket.error to ConnectionFailure and raise it."""
    host, port = address
    # If connecting to a Unix socket, port will be None.
    if port is not None:
        msg = "%s:%d: %s" % (host, port, error)
    else:
        msg = f"{host}: {error}"
    if msg_prefix:
        msg = msg_prefix + msg
    if "configured timeouts" not in msg:
        msg += format_timeout_details(timeout_details)
    if isinstance(error, socket.timeout):
        raise NetworkTimeout(msg) from error
    elif isinstance(error, SSLErrors) and "timed out" in str(error):
        # Eventlet does not distinguish TLS network timeouts from other
        # SSLErrors (https://github.com/eventlet/eventlet/issues/692).
        # Luckily, we can work around this limitation because the phrase
        # 'timed out' appears in all the timeout related SSLErrors raised.
        raise NetworkTimeout(msg) from error
    else:
        raise AutoReconnect(msg) from error


def _get_timeout_details(options: PoolOptions) -> dict[str, float]:
    details = {}
    timeout = _csot.get_timeout()
    socket_timeout = options.socket_timeout
    connect_timeout = options.connect_timeout
    if timeout:
        details["timeoutMS"] = timeout * 1000
    if socket_timeout and not timeout:
        details["socketTimeoutMS"] = socket_timeout * 1000
    if connect_timeout:
        details["connectTimeoutMS"] = connect_timeout * 1000
    return details


def format_timeout_details(details: Optional[dict[str, float]]) -> str:
    result = ""
    if details:
        result += " (configured timeouts:"
        for timeout in ["socketTimeoutMS", "timeoutMS", "connectTimeoutMS"]:
            if timeout in details:
                result += f" {timeout}: {details[timeout]}ms,"
        result = result[:-1]
        result += ")"
    return result


class _CancellationContext:
    def __init__(self) -> None:
        self._cancelled = False

    def cancel(self) -> None:
        """Cancel this context."""
        self._cancelled = True

    @property
    def cancelled(self) -> bool:
        """Was cancel called?"""
        return self._cancelled


async def _async_create_connection(address: _Address, options: PoolOptions) -> socket.socket:
    """Given (host, port) and PoolOptions, connect and return a raw socket object.

    Can raise socket.error.

    This is a modified version of create_connection from CPython >= 2.7.
    """
    host, port = address

    # Check if dealing with a unix domain socket
    if host.endswith(".sock"):
        if not hasattr(socket, "AF_UNIX"):
            raise ConnectionFailure("UNIX-sockets are not supported on this system")
        sock = socket.socket(socket.AF_UNIX)
        # SOCK_CLOEXEC not supported for Unix sockets.
        _set_non_inheritable_non_atomic(sock.fileno())
        try:
            sock.setblocking(False)
            await asyncio.get_running_loop().sock_connect(sock, host)
            return sock
        except OSError:
            sock.close()
            raise

    # Don't try IPv6 if we don't support it. Also skip it if host
    # is 'localhost' (::1 is fine). Avoids slow connect issues
    # like PYTHON-356.
    family = socket.AF_INET
    if socket.has_ipv6 and host != "localhost":
        family = socket.AF_UNSPEC

    err = None
    for res in await _getaddrinfo(host, port, family=family, type=socket.SOCK_STREAM):
        af, socktype, proto, dummy, sa = res
        # SOCK_CLOEXEC was new in CPython 3.2, and only available on a limited
        # number of platforms (newer Linux and *BSD). Starting with CPython 3.4
        # all file descriptors are created non-inheritable. See PEP 446.
        try:
            sock = socket.socket(af, socktype | getattr(socket, "SOCK_CLOEXEC", 0), proto)
        except OSError:
            # Can SOCK_CLOEXEC be defined even if the kernel doesn't support
            # it?
            sock = socket.socket(af, socktype, proto)
        # Fallback when SOCK_CLOEXEC isn't available.
        _set_non_inheritable_non_atomic(sock.fileno())
        try:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            # CSOT: apply timeout to socket connect.
            timeout = _csot.remaining()
            if timeout is None:
                timeout = options.connect_timeout
            elif timeout <= 0:
                raise socket.timeout("timed out")
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, True)
            _set_keepalive_times(sock)
            # Socket needs to be non-blocking during connection to not block the event loop
            sock.setblocking(False)
            await asyncio.wait_for(
                asyncio.get_running_loop().sock_connect(sock, sa), timeout=timeout
            )
            sock.settimeout(timeout)
            return sock
        except asyncio.TimeoutError as e:
            sock.close()
            err = socket.timeout("timed out")
            err.__cause__ = e
        except OSError as e:
            sock.close()
            err = e  # type: ignore[assignment]

    if err is not None:
        raise err
    else:
        # This likely means we tried to connect to an IPv6 only
        # host with an OS/kernel or Python interpreter that doesn't
        # support IPv6. The test case is Jython2.5.1 which doesn't
        # support IPv6 at all.
        raise OSError("getaddrinfo failed")


async def _async_configured_socket(
    address: _Address, options: PoolOptions
) -> Union[socket.socket, _sslConn]:
    """Given (host, port) and PoolOptions, return a raw configured socket.

    Can raise socket.error, ConnectionFailure, or _CertificateError.

    Sets socket's SSL and timeout options.
    """
    sock = await _async_create_connection(address, options)
    ssl_context = options._ssl_context

    if ssl_context is None:
        sock.settimeout(options.socket_timeout)
        return sock

    host = address[0]
    try:
        # We have to pass hostname / ip address to wrap_socket
        # to use SSLContext.check_hostname.
        if _has_sni(False):
            loop = asyncio.get_running_loop()
            ssl_sock = await loop.run_in_executor(
                None,
                functools.partial(ssl_context.wrap_socket, sock, server_hostname=host),  # type: ignore[assignment, misc, unused-ignore]
            )
        else:
            loop = asyncio.get_running_loop()
            ssl_sock = await loop.run_in_executor(None, ssl_context.wrap_socket, sock)  # type: ignore[assignment, misc, unused-ignore]
    except _CertificateError:
        sock.close()
        # Raise _CertificateError directly like we do after match_hostname
        # below.
        raise
    except (OSError, *SSLErrors) as exc:
        sock.close()
        # We raise AutoReconnect for transient and permanent SSL handshake
        # failures alike. Permanent handshake failures, like protocol
        # mismatch, will be turned into ServerSelectionTimeoutErrors later.
        details = _get_timeout_details(options)
        _raise_connection_failure(address, exc, "SSL handshake failed: ", timeout_details=details)
    if (
        ssl_context.verify_mode
        and not ssl_context.check_hostname
        and not options.tls_allow_invalid_hostnames
    ):
        try:
            ssl.match_hostname(ssl_sock.getpeercert(), hostname=host)  # type:ignore[attr-defined, unused-ignore]
        except _CertificateError:
            ssl_sock.close()
            raise

    ssl_sock.settimeout(options.socket_timeout)
    return ssl_sock


async def _configured_protocol_interface(
    address: _Address, options: PoolOptions
) -> AsyncNetworkingInterface:
    """Given (host, port) and PoolOptions, return a configured AsyncNetworkingInterface.

    Can raise socket.error, ConnectionFailure, or _CertificateError.

    Sets protocol's SSL and timeout options.
    """
    sock = await _async_create_connection(address, options)
    ssl_context = options._ssl_context
    timeout = options.socket_timeout

    if ssl_context is None:
        return AsyncNetworkingInterface(
            await asyncio.get_running_loop().create_connection(
                lambda: PyMongoProtocol(timeout=timeout), sock=sock
            )
        )

    host = address[0]
    try:
        # We have to pass hostname / ip address to wrap_socket
        # to use SSLContext.check_hostname.
        transport, protocol = await asyncio.get_running_loop().create_connection(  # type: ignore[call-overload]
            lambda: PyMongoProtocol(timeout=timeout),
            sock=sock,
            server_hostname=host,
            ssl=ssl_context,
        )
    except _CertificateError:
        # Raise _CertificateError directly like we do after match_hostname
        # below.
        raise
    except (OSError, *SSLErrors) as exc:
        # We raise AutoReconnect for transient and permanent SSL handshake
        # failures alike. Permanent handshake failures, like protocol
        # mismatch, will be turned into ServerSelectionTimeoutErrors later.
        details = _get_timeout_details(options)
        _raise_connection_failure(address, exc, "SSL handshake failed: ", timeout_details=details)
    if (
        ssl_context.verify_mode
        and not ssl_context.check_hostname
        and not options.tls_allow_invalid_hostnames
    ):
        try:
            ssl.match_hostname(transport.get_extra_info("peercert"), hostname=host)  # type:ignore[attr-defined,unused-ignore]
        except _CertificateError:
            transport.abort()
            raise

    return AsyncNetworkingInterface((transport, protocol))


def _create_connection(address: _Address, options: PoolOptions) -> socket.socket:
    """Given (host, port) and PoolOptions, connect and return a raw socket object.

    Can raise socket.error.

    This is a modified version of create_connection from CPython >= 2.7.
    """
    host, port = address

    # Check if dealing with a unix domain socket
    if host.endswith(".sock"):
        if not hasattr(socket, "AF_UNIX"):
            raise ConnectionFailure("UNIX-sockets are not supported on this system")
        sock = socket.socket(socket.AF_UNIX)
        # SOCK_CLOEXEC not supported for Unix sockets.
        _set_non_inheritable_non_atomic(sock.fileno())
        try:
            sock.connect(host)
            return sock
        except OSError:
            sock.close()
            raise

    # Don't try IPv6 if we don't support it. Also skip it if host
    # is 'localhost' (::1 is fine). Avoids slow connect issues
    # like PYTHON-356.
    family = socket.AF_INET
    if socket.has_ipv6 and host != "localhost":
        family = socket.AF_UNSPEC

    err = None
    for res in socket.getaddrinfo(host, port, family=family, type=socket.SOCK_STREAM):  # type: ignore[attr-defined, unused-ignore]
        af, socktype, proto, dummy, sa = res
        # SOCK_CLOEXEC was new in CPython 3.2, and only available on a limited
        # number of platforms (newer Linux and *BSD). Starting with CPython 3.4
        # all file descriptors are created non-inheritable. See PEP 446.
        try:
            sock = socket.socket(af, socktype | getattr(socket, "SOCK_CLOEXEC", 0), proto)
        except OSError:
            # Can SOCK_CLOEXEC be defined even if the kernel doesn't support
            # it?
            sock = socket.socket(af, socktype, proto)
        # Fallback when SOCK_CLOEXEC isn't available.
        _set_non_inheritable_non_atomic(sock.fileno())
        try:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            # CSOT: apply timeout to socket connect.
            timeout = _csot.remaining()
            if timeout is None:
                timeout = options.connect_timeout
            elif timeout <= 0:
                raise socket.timeout("timed out")
            sock.settimeout(timeout)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, True)
            _set_keepalive_times(sock)
            sock.connect(sa)
            return sock
        except OSError as e:
            err = e
            sock.close()

    if err is not None:
        raise err
    else:
        # This likely means we tried to connect to an IPv6 only
        # host with an OS/kernel or Python interpreter that doesn't
        # support IPv6. The test case is Jython2.5.1 which doesn't
        # support IPv6 at all.
        raise OSError("getaddrinfo failed")


def _configured_socket(address: _Address, options: PoolOptions) -> Union[socket.socket, _sslConn]:
    """Given (host, port) and PoolOptions, return a raw configured socket.

    Can raise socket.error, ConnectionFailure, or _CertificateError.

    Sets socket's SSL and timeout options.
    """
    sock = _create_connection(address, options)
    ssl_context = options._ssl_context

    if ssl_context is None:
        sock.settimeout(options.socket_timeout)
        return sock

    host = address[0]
    try:
        # We have to pass hostname / ip address to wrap_socket
        # to use SSLContext.check_hostname.
        if _has_sni(True):
            ssl_sock = ssl_context.wrap_socket(sock, server_hostname=host)  # type: ignore[assignment, misc, unused-ignore]
        else:
            ssl_sock = ssl_context.wrap_socket(sock)  # type: ignore[assignment, misc, unused-ignore]
    except _CertificateError:
        sock.close()
        # Raise _CertificateError directly like we do after match_hostname
        # below.
        raise
    except (OSError, *SSLErrors) as exc:
        sock.close()
        # We raise AutoReconnect for transient and permanent SSL handshake
        # failures alike. Permanent handshake failures, like protocol
        # mismatch, will be turned into ServerSelectionTimeoutErrors later.
        details = _get_timeout_details(options)
        _raise_connection_failure(address, exc, "SSL handshake failed: ", timeout_details=details)
    if (
        ssl_context.verify_mode
        and not ssl_context.check_hostname
        and not options.tls_allow_invalid_hostnames
    ):
        try:
            ssl.match_hostname(ssl_sock.getpeercert(), hostname=host)  # type:ignore[attr-defined, unused-ignore]
        except _CertificateError:
            ssl_sock.close()
            raise

    ssl_sock.settimeout(options.socket_timeout)
    return ssl_sock


def _configured_socket_interface(address: _Address, options: PoolOptions) -> NetworkingInterface:
    """Given (host, port) and PoolOptions, return a NetworkingInterface wrapping a configured socket.

    Can raise socket.error, ConnectionFailure, or _CertificateError.

    Sets socket's SSL and timeout options.
    """
    sock = _create_connection(address, options)
    ssl_context = options._ssl_context

    if ssl_context is None:
        sock.settimeout(options.socket_timeout)
        return NetworkingInterface(sock)

    host = address[0]
    try:
        # We have to pass hostname / ip address to wrap_socket
        # to use SSLContext.check_hostname.
        if _has_sni(True):
            ssl_sock = ssl_context.wrap_socket(sock, server_hostname=host)
        else:
            ssl_sock = ssl_context.wrap_socket(sock)
    except _CertificateError:
        sock.close()
        # Raise _CertificateError directly like we do after match_hostname
        # below.
        raise
    except (OSError, *SSLErrors) as exc:
        sock.close()
        # We raise AutoReconnect for transient and permanent SSL handshake
        # failures alike. Permanent handshake failures, like protocol
        # mismatch, will be turned into ServerSelectionTimeoutErrors later.
        details = _get_timeout_details(options)
        _raise_connection_failure(address, exc, "SSL handshake failed: ", timeout_details=details)
    if (
        ssl_context.verify_mode
        and not ssl_context.check_hostname
        and not options.tls_allow_invalid_hostnames
    ):
        try:
            ssl.match_hostname(ssl_sock.getpeercert(), hostname=host)  # type:ignore[attr-defined,unused-ignore]
        except _CertificateError:
            ssl_sock.close()
            raise

    ssl_sock.settimeout(options.socket_timeout)
    return NetworkingInterface(ssl_sock)
