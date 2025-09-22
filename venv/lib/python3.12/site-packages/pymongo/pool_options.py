# Copyright 2024-present MongoDB, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you
# may not use this file except in compliance with the License.  You
# may obtain a copy of the License at
#
# https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.  See the License for the specific language governing
# permissions and limitations under the License.

"""Pool options for AsyncMongoClient/MongoClient.

.. seealso:: This module is compatible with both the synchronous and asynchronous PyMongo APIs.
"""
from __future__ import annotations

import copy
import os
import platform
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, MutableMapping, Optional

import bson
from pymongo import __version__
from pymongo.common import (
    MAX_CONNECTING,
    MAX_IDLE_TIME_SEC,
    MAX_POOL_SIZE,
    MIN_POOL_SIZE,
    WAIT_QUEUE_TIMEOUT,
    has_c,
)

if TYPE_CHECKING:
    from pymongo.auth_shared import MongoCredential
    from pymongo.compression_support import CompressionSettings
    from pymongo.driver_info import DriverInfo
    from pymongo.monitoring import _EventListeners
    from pymongo.pyopenssl_context import SSLContext
    from pymongo.server_api import ServerApi


_METADATA: dict[str, Any] = {"driver": {"name": "PyMongo", "version": __version__}}

if sys.platform.startswith("linux"):
    # platform.linux_distribution was deprecated in Python 3.5
    # and removed in Python 3.8. Starting in Python 3.5 it
    # raises DeprecationWarning
    # DeprecationWarning: dist() and linux_distribution() functions are deprecated in Python 3.5
    _name = platform.system()
    _METADATA["os"] = {
        "type": _name,
        "name": _name,
        "architecture": platform.machine(),
        # Kernel version (e.g. 4.4.0-17-generic).
        "version": platform.release(),
    }
elif sys.platform == "darwin":
    _METADATA["os"] = {
        "type": platform.system(),
        "name": platform.system(),
        "architecture": platform.machine(),
        # (mac|i|tv)OS(X) version (e.g. 10.11.6) instead of darwin
        # kernel version.
        "version": platform.mac_ver()[0],
    }
elif sys.platform == "win32":
    _ver = sys.getwindowsversion()
    _METADATA["os"] = {
        "type": "Windows",
        "name": "Windows",
        # Avoid using platform calls, see PYTHON-4455.
        "architecture": os.environ.get("PROCESSOR_ARCHITECTURE") or platform.machine(),
        # Windows patch level (e.g. 10.0.17763-SP0).
        "version": ".".join(map(str, _ver[:3])) + f"-SP{_ver[-1] or '0'}",
    }
elif sys.platform.startswith("java"):
    _name, _ver, _arch = platform.java_ver()[-1]
    _METADATA["os"] = {
        # Linux, Windows 7, Mac OS X, etc.
        "type": _name,
        "name": _name,
        # x86, x86_64, AMD64, etc.
        "architecture": _arch,
        # Linux kernel version, OSX version, etc.
        "version": _ver,
    }
else:
    # Get potential alias (e.g. SunOS 5.11 becomes Solaris 2.11)
    _aliased = platform.system_alias(platform.system(), platform.release(), platform.version())
    _METADATA["os"] = {
        "type": platform.system(),
        "name": " ".join([part for part in _aliased[:2] if part]),
        "architecture": platform.machine(),
        "version": _aliased[2],
    }

if platform.python_implementation().startswith("PyPy"):
    _METADATA["platform"] = " ".join(
        (
            platform.python_implementation(),
            ".".join(map(str, sys.pypy_version_info)),  # type: ignore
            "(Python %s)" % ".".join(map(str, sys.version_info)),
        )
    )
elif sys.platform.startswith("java"):
    _METADATA["platform"] = " ".join(
        (
            platform.python_implementation(),
            ".".join(map(str, sys.version_info)),
            "(%s)" % " ".join((platform.system(), platform.release())),
        )
    )
else:
    _METADATA["platform"] = " ".join(
        (platform.python_implementation(), ".".join(map(str, sys.version_info)))
    )

DOCKER_ENV_PATH = "/.dockerenv"
ENV_VAR_K8S = "KUBERNETES_SERVICE_HOST"

RUNTIME_NAME_DOCKER = "docker"
ORCHESTRATOR_NAME_K8S = "kubernetes"


def get_container_env_info() -> dict[str, str]:
    """Returns the runtime and orchestrator of a container.
    If neither value is present, the metadata client.env.container field will be omitted."""
    container = {}

    if Path(DOCKER_ENV_PATH).exists():
        container["runtime"] = RUNTIME_NAME_DOCKER
    if os.getenv(ENV_VAR_K8S):
        container["orchestrator"] = ORCHESTRATOR_NAME_K8S

    return container


def _is_lambda() -> bool:
    if os.getenv("AWS_LAMBDA_RUNTIME_API"):
        return True
    env = os.getenv("AWS_EXECUTION_ENV")
    if env:
        return env.startswith("AWS_Lambda_")
    return False


def _is_azure_func() -> bool:
    return bool(os.getenv("FUNCTIONS_WORKER_RUNTIME"))


def _is_gcp_func() -> bool:
    return bool(os.getenv("K_SERVICE") or os.getenv("FUNCTION_NAME"))


def _is_vercel() -> bool:
    return bool(os.getenv("VERCEL"))


def _is_faas() -> bool:
    return _is_lambda() or _is_azure_func() or _is_gcp_func() or _is_vercel()


def _getenv_int(key: str) -> Optional[int]:
    """Like os.getenv but returns an int, or None if the value is missing/malformed."""
    val = os.getenv(key)
    if not val:
        return None
    try:
        return int(val)
    except ValueError:
        return None


def _metadata_env() -> dict[str, Any]:
    env: dict[str, Any] = {}
    container = get_container_env_info()
    if container:
        env["container"] = container
    # Skip if multiple (or no) envs are matched.
    if (_is_lambda(), _is_azure_func(), _is_gcp_func(), _is_vercel()).count(True) != 1:
        return env
    if _is_lambda():
        env["name"] = "aws.lambda"
        region = os.getenv("AWS_REGION")
        if region:
            env["region"] = region
        memory_mb = _getenv_int("AWS_LAMBDA_FUNCTION_MEMORY_SIZE")
        if memory_mb is not None:
            env["memory_mb"] = memory_mb
    elif _is_azure_func():
        env["name"] = "azure.func"
    elif _is_gcp_func():
        env["name"] = "gcp.func"
        region = os.getenv("FUNCTION_REGION")
        if region:
            env["region"] = region
        memory_mb = _getenv_int("FUNCTION_MEMORY_MB")
        if memory_mb is not None:
            env["memory_mb"] = memory_mb
        timeout_sec = _getenv_int("FUNCTION_TIMEOUT_SEC")
        if timeout_sec is not None:
            env["timeout_sec"] = timeout_sec
    elif _is_vercel():
        env["name"] = "vercel"
        region = os.getenv("VERCEL_REGION")
        if region:
            env["region"] = region
    return env


_MAX_METADATA_SIZE = 512


# See: https://github.com/mongodb/specifications/blob/master/source/mongodb-handshake/handshake.md#limitations
def _truncate_metadata(metadata: MutableMapping[str, Any]) -> None:
    """Perform metadata truncation."""
    if len(bson.encode(metadata)) <= _MAX_METADATA_SIZE:
        return
    # 1. Omit fields from env except env.name.
    env_name = metadata.get("env", {}).get("name")
    if env_name:
        metadata["env"] = {"name": env_name}
    if len(bson.encode(metadata)) <= _MAX_METADATA_SIZE:
        return
    # 2. Omit fields from os except os.type.
    os_type = metadata.get("os", {}).get("type")
    if os_type:
        metadata["os"] = {"type": os_type}
    if len(bson.encode(metadata)) <= _MAX_METADATA_SIZE:
        return
    # 3. Omit the env document entirely.
    metadata.pop("env", None)
    encoded_size = len(bson.encode(metadata))
    if encoded_size <= _MAX_METADATA_SIZE:
        return
    # 4. Truncate platform.
    overflow = encoded_size - _MAX_METADATA_SIZE
    plat = metadata.get("platform", "")
    if plat:
        plat = plat[:-overflow]
    if plat:
        metadata["platform"] = plat
    else:
        metadata.pop("platform", None)
    encoded_size = len(bson.encode(metadata))
    if encoded_size <= _MAX_METADATA_SIZE:
        return
    # 5. Truncate driver info.
    overflow = encoded_size - _MAX_METADATA_SIZE
    driver = metadata.get("driver", {})
    if driver:
        # Truncate driver version.
        driver_version = driver.get("version")[:-overflow]
        if len(driver_version) >= len(_METADATA["driver"]["version"]):
            metadata["driver"]["version"] = driver_version
        else:
            metadata["driver"]["version"] = _METADATA["driver"]["version"]
        encoded_size = len(bson.encode(metadata))
        if encoded_size <= _MAX_METADATA_SIZE:
            return
        # Truncate driver name.
        overflow = encoded_size - _MAX_METADATA_SIZE
        driver_name = driver.get("name")[:-overflow]
        if len(driver_name) >= len(_METADATA["driver"]["name"]):
            metadata["driver"]["name"] = driver_name
        else:
            metadata["driver"]["name"] = _METADATA["driver"]["name"]


# If the first getaddrinfo call of this interpreter's life is on a thread,
# while the main thread holds the import lock, getaddrinfo deadlocks trying
# to import the IDNA codec. Import it here, where presumably we're on the
# main thread, to avoid the deadlock. See PYTHON-607.
"foo".encode("idna")


class PoolOptions:
    """Read only connection pool options for an AsyncMongoClient/MongoClient.

    Should not be instantiated directly by application developers. Access
    a client's pool options via
    :attr:`~pymongo.client_options.ClientOptions.pool_options` instead::

      pool_opts = client.options.pool_options
      pool_opts.max_pool_size
      pool_opts.min_pool_size

    """

    __slots__ = (
        "__max_pool_size",
        "__min_pool_size",
        "__max_idle_time_seconds",
        "__connect_timeout",
        "__socket_timeout",
        "__wait_queue_timeout",
        "__ssl_context",
        "__tls_allow_invalid_hostnames",
        "__event_listeners",
        "__appname",
        "__driver",
        "__metadata",
        "__compression_settings",
        "__max_connecting",
        "__pause_enabled",
        "__server_api",
        "__load_balanced",
        "__credentials",
    )

    def __init__(
        self,
        max_pool_size: int = MAX_POOL_SIZE,
        min_pool_size: int = MIN_POOL_SIZE,
        max_idle_time_seconds: Optional[int] = MAX_IDLE_TIME_SEC,
        connect_timeout: Optional[float] = None,
        socket_timeout: Optional[float] = None,
        wait_queue_timeout: Optional[int] = WAIT_QUEUE_TIMEOUT,
        ssl_context: Optional[SSLContext] = None,
        tls_allow_invalid_hostnames: bool = False,
        event_listeners: Optional[_EventListeners] = None,
        appname: Optional[str] = None,
        driver: Optional[DriverInfo] = None,
        compression_settings: Optional[CompressionSettings] = None,
        max_connecting: int = MAX_CONNECTING,
        pause_enabled: bool = True,
        server_api: Optional[ServerApi] = None,
        load_balanced: Optional[bool] = None,
        credentials: Optional[MongoCredential] = None,
        is_sync: Optional[bool] = True,
    ):
        self.__max_pool_size = max_pool_size
        self.__min_pool_size = min_pool_size
        self.__max_idle_time_seconds = max_idle_time_seconds
        self.__connect_timeout = connect_timeout
        self.__socket_timeout = socket_timeout
        self.__wait_queue_timeout = wait_queue_timeout
        self.__ssl_context = ssl_context
        self.__tls_allow_invalid_hostnames = tls_allow_invalid_hostnames
        self.__event_listeners = event_listeners
        self.__appname = appname
        self.__driver = driver
        self.__compression_settings = compression_settings
        self.__max_connecting = max_connecting
        self.__pause_enabled = pause_enabled
        self.__server_api = server_api
        self.__load_balanced = load_balanced
        self.__credentials = credentials
        self.__metadata = copy.deepcopy(_METADATA)

        if appname:
            self.__metadata["application"] = {"name": appname}

        # Combine the "driver" AsyncMongoClient option with PyMongo's info, like:
        # {
        #    'driver': {
        #        'name': 'PyMongo|MyDriver',
        #        'version': '4.2.0|1.2.3',
        #    },
        #    'platform': 'CPython 3.8.0|MyPlatform'
        # }
        if has_c():
            self.__metadata["driver"]["name"] = "{}|{}".format(
                self.__metadata["driver"]["name"],
                "c",
            )
        if not is_sync:
            self.__metadata["driver"]["name"] = "{}|{}".format(
                self.__metadata["driver"]["name"],
                "async",
            )
        if driver:
            if driver.name:
                self.__metadata["driver"]["name"] = "{}|{}".format(
                    self.__metadata["driver"]["name"],
                    driver.name,
                )
            if driver.version:
                self.__metadata["driver"]["version"] = "{}|{}".format(
                    _METADATA["driver"]["version"],
                    driver.version,
                )
            if driver.platform:
                self.__metadata["platform"] = "{}|{}".format(_METADATA["platform"], driver.platform)

        env = _metadata_env()
        if env:
            self.__metadata["env"] = env

        _truncate_metadata(self.__metadata)

    @property
    def _credentials(self) -> Optional[MongoCredential]:
        """A :class:`~pymongo.auth.MongoCredentials` instance or None."""
        return self.__credentials

    @property
    def non_default_options(self) -> dict[str, Any]:
        """The non-default options this pool was created with.

        Added for CMAP's :class:`PoolCreatedEvent`.
        """
        opts = {}
        if self.__max_pool_size != MAX_POOL_SIZE:
            opts["maxPoolSize"] = self.__max_pool_size
        if self.__min_pool_size != MIN_POOL_SIZE:
            opts["minPoolSize"] = self.__min_pool_size
        if self.__max_idle_time_seconds != MAX_IDLE_TIME_SEC:
            assert self.__max_idle_time_seconds is not None
            opts["maxIdleTimeMS"] = self.__max_idle_time_seconds * 1000
        if self.__wait_queue_timeout != WAIT_QUEUE_TIMEOUT:
            assert self.__wait_queue_timeout is not None
            opts["waitQueueTimeoutMS"] = self.__wait_queue_timeout * 1000
        if self.__max_connecting != MAX_CONNECTING:
            opts["maxConnecting"] = self.__max_connecting
        return opts

    @property
    def max_pool_size(self) -> float:
        """The maximum allowable number of concurrent connections to each
        connected server. Requests to a server will block if there are
        `maxPoolSize` outstanding connections to the requested server.
        Defaults to 100. Cannot be 0.

        When a server's pool has reached `max_pool_size`, operations for that
        server block waiting for a socket to be returned to the pool. If
        ``waitQueueTimeoutMS`` is set, a blocked operation will raise
        :exc:`~pymongo.errors.ConnectionFailure` after a timeout.
        By default ``waitQueueTimeoutMS`` is not set.
        """
        return self.__max_pool_size

    @property
    def min_pool_size(self) -> int:
        """The minimum required number of concurrent connections that the pool
        will maintain to each connected server. Default is 0.
        """
        return self.__min_pool_size

    @property
    def max_connecting(self) -> int:
        """The maximum number of concurrent connection creation attempts per
        pool. Defaults to 2.
        """
        return self.__max_connecting

    @property
    def pause_enabled(self) -> bool:
        return self.__pause_enabled

    @property
    def max_idle_time_seconds(self) -> Optional[int]:
        """The maximum number of seconds that a connection can remain
        idle in the pool before being removed and replaced. Defaults to
        `None` (no limit).
        """
        return self.__max_idle_time_seconds

    @property
    def connect_timeout(self) -> Optional[float]:
        """How long a connection can take to be opened before timing out."""
        return self.__connect_timeout

    @property
    def socket_timeout(self) -> Optional[float]:
        """How long a send or receive on a socket can take before timing out."""
        return self.__socket_timeout

    @property
    def wait_queue_timeout(self) -> Optional[int]:
        """How long a thread will wait for a socket from the pool if the pool
        has no free sockets.
        """
        return self.__wait_queue_timeout

    @property
    def _ssl_context(self) -> Optional[SSLContext]:
        """An SSLContext instance or None."""
        return self.__ssl_context

    @property
    def tls_allow_invalid_hostnames(self) -> bool:
        """If True skip ssl.match_hostname."""
        return self.__tls_allow_invalid_hostnames

    @property
    def _event_listeners(self) -> Optional[_EventListeners]:
        """An instance of pymongo.monitoring._EventListeners."""
        return self.__event_listeners

    @property
    def appname(self) -> Optional[str]:
        """The application name, for sending with hello in server handshake."""
        return self.__appname

    @property
    def driver(self) -> Optional[DriverInfo]:
        """Driver name and version, for sending with hello in handshake."""
        return self.__driver

    @property
    def _compression_settings(self) -> Optional[CompressionSettings]:
        return self.__compression_settings

    @property
    def metadata(self) -> dict[str, Any]:
        """A dict of metadata about the application, driver, os, and platform."""
        return self.__metadata.copy()

    @property
    def server_api(self) -> Optional[ServerApi]:
        """A pymongo.server_api.ServerApi or None."""
        return self.__server_api

    @property
    def load_balanced(self) -> Optional[bool]:
        """True if this Pool is configured in load balanced mode."""
        return self.__load_balanced
