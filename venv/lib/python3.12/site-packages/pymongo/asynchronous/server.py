# Copyright 2014-present MongoDB, Inc.
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

"""Communicate with one MongoDB server in a topology."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncContextManager,
    Callable,
    Optional,
    Union,
)

from bson import _decode_all_selective
from pymongo.asynchronous.helpers import _handle_reauth
from pymongo.errors import NotPrimaryError, OperationFailure
from pymongo.helpers_shared import _check_command_response
from pymongo.logger import (
    _COMMAND_LOGGER,
    _SDAM_LOGGER,
    _CommandStatusMessage,
    _debug_log,
    _SDAMStatusMessage,
)
from pymongo.message import _convert_exception, _GetMore, _OpMsg, _Query
from pymongo.response import PinnedResponse, Response

if TYPE_CHECKING:
    from queue import Queue
    from weakref import ReferenceType

    from bson.objectid import ObjectId
    from pymongo.asynchronous.mongo_client import AsyncMongoClient, _MongoClientErrorHandler
    from pymongo.asynchronous.monitor import Monitor
    from pymongo.asynchronous.pool import AsyncConnection, Pool
    from pymongo.monitoring import _EventListeners
    from pymongo.read_preferences import _ServerMode
    from pymongo.server_description import ServerDescription
    from pymongo.typings import _DocumentOut

_IS_SYNC = False

_CURSOR_DOC_FIELDS = {"cursor": {"firstBatch": 1, "nextBatch": 1}}


class Server:
    def __init__(
        self,
        server_description: ServerDescription,
        pool: Pool,
        monitor: Monitor,
        topology_id: Optional[ObjectId] = None,
        listeners: Optional[_EventListeners] = None,
        events: Optional[ReferenceType[Queue]] = None,
    ) -> None:
        """Represent one MongoDB server."""
        self._description = server_description
        self._pool = pool
        self._monitor = monitor
        self._topology_id = topology_id
        self._publish = listeners is not None and listeners.enabled_for_server
        self._listener = listeners
        self._events = None
        if self._publish:
            self._events = events()  # type: ignore[misc]

    async def open(self) -> None:
        """Start monitoring, or restart after a fork.

        Multiple calls have no effect.
        """
        if not self._pool.opts.load_balanced:
            self._monitor.open()

    async def reset(self, service_id: Optional[ObjectId] = None) -> None:
        """Clear the connection pool."""
        await self.pool.reset(service_id)

    async def close(self) -> None:
        """Clear the connection pool and stop the monitor.

        Reconnect with open().
        """
        if self._publish:
            assert self._listener is not None
            assert self._events is not None
            self._events.put(
                (
                    self._listener.publish_server_closed,
                    (self._description.address, self._topology_id),
                )
            )
        if _SDAM_LOGGER.isEnabledFor(logging.DEBUG):
            _debug_log(
                _SDAM_LOGGER,
                message=_SDAMStatusMessage.STOP_SERVER,
                topologyId=self._topology_id,
                serverHost=self._description.address[0],
                serverPort=self._description.address[1],
            )

        await self._monitor.close()
        await self._pool.close()

    def request_check(self) -> None:
        """Check the server's state soon."""
        self._monitor.request_check()

    async def operation_to_command(
        self, operation: Union[_Query, _GetMore], conn: AsyncConnection, apply_timeout: bool = False
    ) -> tuple[dict[str, Any], str]:
        cmd, db = operation.as_command(conn, apply_timeout)
        # Support auto encryption
        if operation.client._encrypter and not operation.client._encrypter._bypass_auto_encryption:
            cmd = await operation.client._encrypter.encrypt(  # type: ignore[misc, assignment]
                operation.db, cmd, operation.codec_options
            )
        operation.update_command(cmd)

        return cmd, db

    @_handle_reauth
    async def run_operation(
        self,
        conn: AsyncConnection,
        operation: Union[_Query, _GetMore],
        read_preference: _ServerMode,
        listeners: Optional[_EventListeners],
        unpack_res: Callable[..., list[_DocumentOut]],
        client: AsyncMongoClient,
    ) -> Response:
        """Run a _Query or _GetMore operation and return a Response object.

        This method is used only to run _Query/_GetMore operations from
        cursors.
        Can raise ConnectionFailure, OperationFailure, etc.

        :param conn: An AsyncConnection instance.
        :param operation: A _Query or _GetMore object.
        :param read_preference: The read preference to use.
        :param listeners: Instance of _EventListeners or None.
        :param unpack_res: A callable that decodes the wire protocol response.
        :param client: An AsyncMongoClient instance.
        """
        assert listeners is not None
        publish = listeners.enabled_for_commands
        start = datetime.now()

        use_cmd = operation.use_command(conn)
        more_to_come = operation.conn_mgr and operation.conn_mgr.more_to_come
        cmd, dbn = await self.operation_to_command(operation, conn, use_cmd)
        if more_to_come:
            request_id = 0
        else:
            message = operation.get_message(read_preference, conn, use_cmd)
            request_id, data, max_doc_size = self._split_message(message)

        if _COMMAND_LOGGER.isEnabledFor(logging.DEBUG):
            _debug_log(
                _COMMAND_LOGGER,
                message=_CommandStatusMessage.STARTED,
                clientId=client._topology_settings._topology_id,
                command=cmd,
                commandName=next(iter(cmd)),
                databaseName=dbn,
                requestId=request_id,
                operationId=request_id,
                driverConnectionId=conn.id,
                serverConnectionId=conn.server_connection_id,
                serverHost=conn.address[0],
                serverPort=conn.address[1],
                serviceId=conn.service_id,
            )

        if publish:
            if "$db" not in cmd:
                cmd["$db"] = dbn
            assert listeners is not None
            listeners.publish_command_start(
                cmd,
                dbn,
                request_id,
                conn.address,
                conn.server_connection_id,
                service_id=conn.service_id,
            )

        try:
            if more_to_come:
                reply = await conn.receive_message(None)
            else:
                await conn.send_message(data, max_doc_size)
                reply = await conn.receive_message(request_id)

            # Unpack and check for command errors.
            if use_cmd:
                user_fields = _CURSOR_DOC_FIELDS
                legacy_response = False
            else:
                user_fields = None
                legacy_response = True
            docs = unpack_res(
                reply,
                operation.cursor_id,
                operation.codec_options,
                legacy_response=legacy_response,
                user_fields=user_fields,
            )
            if use_cmd:
                first = docs[0]
                await operation.client._process_response(first, operation.session)  # type: ignore[misc, arg-type]
                _check_command_response(first, conn.max_wire_version)
        except Exception as exc:
            duration = datetime.now() - start
            if isinstance(exc, (NotPrimaryError, OperationFailure)):
                failure: _DocumentOut = exc.details  # type: ignore[assignment]
            else:
                failure = _convert_exception(exc)
            if _COMMAND_LOGGER.isEnabledFor(logging.DEBUG):
                _debug_log(
                    _COMMAND_LOGGER,
                    message=_CommandStatusMessage.FAILED,
                    clientId=client._topology_settings._topology_id,
                    durationMS=duration,
                    failure=failure,
                    commandName=next(iter(cmd)),
                    databaseName=dbn,
                    requestId=request_id,
                    operationId=request_id,
                    driverConnectionId=conn.id,
                    serverConnectionId=conn.server_connection_id,
                    serverHost=conn.address[0],
                    serverPort=conn.address[1],
                    serviceId=conn.service_id,
                    isServerSideError=isinstance(exc, OperationFailure),
                )
            if publish:
                assert listeners is not None
                listeners.publish_command_failure(
                    duration,
                    failure,
                    operation.name,
                    request_id,
                    conn.address,
                    conn.server_connection_id,
                    service_id=conn.service_id,
                    database_name=dbn,
                )
            raise
        duration = datetime.now() - start
        # Must publish in find / getMore / explain command response
        # format.
        if use_cmd:
            res = docs[0]
        elif operation.name == "explain":
            res = docs[0] if docs else {}
        else:
            res = {"cursor": {"id": reply.cursor_id, "ns": operation.namespace()}, "ok": 1}  # type: ignore[union-attr]
            if operation.name == "find":
                res["cursor"]["firstBatch"] = docs
            else:
                res["cursor"]["nextBatch"] = docs
        if _COMMAND_LOGGER.isEnabledFor(logging.DEBUG):
            _debug_log(
                _COMMAND_LOGGER,
                message=_CommandStatusMessage.SUCCEEDED,
                clientId=client._topology_settings._topology_id,
                durationMS=duration,
                reply=res,
                commandName=next(iter(cmd)),
                databaseName=dbn,
                requestId=request_id,
                operationId=request_id,
                driverConnectionId=conn.id,
                serverConnectionId=conn.server_connection_id,
                serverHost=conn.address[0],
                serverPort=conn.address[1],
                serviceId=conn.service_id,
            )
        if publish:
            assert listeners is not None
            listeners.publish_command_success(
                duration,
                res,
                operation.name,
                request_id,
                conn.address,
                conn.server_connection_id,
                service_id=conn.service_id,
                database_name=dbn,
            )

        # Decrypt response.
        client = operation.client  # type: ignore[assignment]
        if client and client._encrypter:
            if use_cmd:
                decrypted = await client._encrypter.decrypt(reply.raw_command_response())
                docs = _decode_all_selective(decrypted, operation.codec_options, user_fields)

        response: Response

        if client._should_pin_cursor(operation.session) or operation.exhaust:  # type: ignore[arg-type]
            conn.pin_cursor()
            if isinstance(reply, _OpMsg):
                # In OP_MSG, the server keeps sending only if the
                # more_to_come flag is set.
                more_to_come = reply.more_to_come
            else:
                # In OP_REPLY, the server keeps sending until cursor_id is 0.
                more_to_come = bool(operation.exhaust and reply.cursor_id)
            if operation.conn_mgr:
                operation.conn_mgr.update_exhaust(more_to_come)
            response = PinnedResponse(
                data=reply,
                address=self._description.address,
                conn=conn,
                duration=duration,
                request_id=request_id,
                from_command=use_cmd,
                docs=docs,
                more_to_come=more_to_come,
            )
        else:
            response = Response(
                data=reply,
                address=self._description.address,
                duration=duration,
                request_id=request_id,
                from_command=use_cmd,
                docs=docs,
            )

        return response

    async def checkout(
        self, handler: Optional[_MongoClientErrorHandler] = None
    ) -> AsyncContextManager[AsyncConnection]:
        return self.pool.checkout(handler)

    @property
    def description(self) -> ServerDescription:
        return self._description

    @description.setter
    def description(self, server_description: ServerDescription) -> None:
        assert server_description.address == self._description.address
        self._description = server_description

    @property
    def pool(self) -> Pool:
        return self._pool

    def _split_message(
        self, message: Union[tuple[int, Any], tuple[int, Any, int]]
    ) -> tuple[int, Any, int]:
        """Return request_id, data, max_doc_size.

        :param message: (request_id, data, max_doc_size) or (request_id, data)
        """
        if len(message) == 3:
            return message  # type: ignore[return-value]
        else:
            # get_more and kill_cursors messages don't include BSON documents.
            request_id, data = message  # type: ignore[misc]
            return request_id, data, 0

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self._description!r}>"
