# Copyright 2024-present MongoDB, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Miscellaneous pieces that need to be synchronized."""
from __future__ import annotations

import asyncio
import builtins
import socket
import sys
from typing import (
    Any,
    Callable,
    TypeVar,
    cast,
)

from pymongo.errors import (
    OperationFailure,
)
from pymongo.helpers_shared import _REAUTHENTICATION_REQUIRED_CODE

_IS_SYNC = False

# See https://mypy.readthedocs.io/en/stable/generics.html?#decorator-factories
F = TypeVar("F", bound=Callable[..., Any])


def _handle_reauth(func: F) -> F:
    async def inner(*args: Any, **kwargs: Any) -> Any:
        no_reauth = kwargs.pop("no_reauth", False)
        from pymongo.asynchronous.pool import AsyncConnection
        from pymongo.message import _BulkWriteContext

        try:
            return await func(*args, **kwargs)
        except OperationFailure as exc:
            if no_reauth:
                raise
            if exc.code == _REAUTHENTICATION_REQUIRED_CODE:
                # Look for an argument that either is a AsyncConnection
                # or has a connection attribute, so we can trigger
                # a reauth.
                conn = None
                for arg in args:
                    if isinstance(arg, AsyncConnection):
                        conn = arg
                        break
                    if isinstance(arg, _BulkWriteContext):
                        conn = arg.conn  # type: ignore[assignment]
                        break
                if conn:
                    await conn.authenticate(reauthenticate=True)
                else:
                    raise
                return func(*args, **kwargs)
            raise

    return cast(F, inner)


async def _getaddrinfo(
    host: Any, port: Any, **kwargs: Any
) -> list[
    tuple[
        socket.AddressFamily,
        socket.SocketKind,
        int,
        str,
        tuple[str, int] | tuple[str, int, int, int],
    ]
]:
    if not _IS_SYNC:
        loop = asyncio.get_running_loop()
        return await loop.getaddrinfo(host, port, **kwargs)  # type: ignore[return-value]
    else:
        return socket.getaddrinfo(host, port, **kwargs)


if sys.version_info >= (3, 10):
    anext = builtins.anext
    aiter = builtins.aiter
else:

    async def anext(cls: Any) -> Any:
        """Compatibility function until we drop 3.9 support: https://docs.python.org/3/library/functions.html#anext."""
        return await cls.__anext__()

    def aiter(cls: Any) -> Any:
        """Compatibility function until we drop 3.9 support: https://docs.python.org/3/library/functions.html#anext."""
        return cls.__aiter__()
