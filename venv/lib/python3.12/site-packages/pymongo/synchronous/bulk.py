# Copyright 2014-present MongoDB, Inc.
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

"""The bulk write operations interface.

.. versionadded:: 2.7
"""
from __future__ import annotations

import copy
import datetime
import logging
from collections.abc import MutableMapping
from itertools import islice
from typing import (
    TYPE_CHECKING,
    Any,
    Iterator,
    Mapping,
    Optional,
    Type,
    Union,
)

from bson.objectid import ObjectId
from bson.raw_bson import RawBSONDocument
from pymongo import _csot, common
from pymongo.bulk_shared import (
    _COMMANDS,
    _DELETE_ALL,
    _merge_command,
    _raise_bulk_write_error,
    _Run,
)
from pymongo.common import (
    validate_is_document_type,
    validate_ok_for_replace,
    validate_ok_for_update,
)
from pymongo.errors import (
    ConfigurationError,
    InvalidOperation,
    NotPrimaryError,
    OperationFailure,
)
from pymongo.helpers_shared import _RETRYABLE_ERROR_CODES
from pymongo.logger import _COMMAND_LOGGER, _CommandStatusMessage, _debug_log
from pymongo.message import (
    _DELETE,
    _INSERT,
    _UPDATE,
    _BulkWriteContext,
    _convert_exception,
    _convert_write_result,
    _EncryptedBulkWriteContext,
    _randint,
)
from pymongo.read_preferences import ReadPreference
from pymongo.synchronous.client_session import ClientSession, _validate_session_write_concern
from pymongo.synchronous.helpers import _handle_reauth
from pymongo.write_concern import WriteConcern

if TYPE_CHECKING:
    from pymongo.synchronous.collection import Collection
    from pymongo.synchronous.mongo_client import MongoClient
    from pymongo.synchronous.pool import Connection
    from pymongo.typings import _DocumentOut, _DocumentType, _Pipeline

_IS_SYNC = True


class _Bulk:
    """The private guts of the bulk write API."""

    def __init__(
        self,
        collection: Collection[_DocumentType],
        ordered: bool,
        bypass_document_validation: Optional[bool],
        comment: Optional[str] = None,
        let: Optional[Any] = None,
    ) -> None:
        """Initialize a _Bulk instance."""
        self.collection = collection.with_options(
            codec_options=collection.codec_options._replace(
                unicode_decode_error_handler="replace", document_class=dict
            )
        )
        self.let = let
        if self.let is not None:
            common.validate_is_document_type("let", self.let)
        self.comment: Optional[str] = comment
        self.ordered = ordered
        self.ops: list[tuple[int, Mapping[str, Any]]] = []
        self.executed = False
        self.bypass_doc_val = bypass_document_validation
        self.uses_collation = False
        self.uses_array_filters = False
        self.uses_hint_update = False
        self.uses_hint_delete = False
        self.uses_sort = False
        self.is_retryable = True
        self.retrying = False
        self.started_retryable_write = False
        # Extra state so that we know where to pick up on a retry attempt.
        self.current_run = None
        self.next_run = None
        self.is_encrypted = False

    @property
    def bulk_ctx_class(self) -> Type[_BulkWriteContext]:
        encrypter = self.collection.database.client._encrypter
        if encrypter and not encrypter._bypass_auto_encryption:
            self.is_encrypted = True
            return _EncryptedBulkWriteContext
        else:
            self.is_encrypted = False
            return _BulkWriteContext

    def add_insert(self, document: _DocumentOut) -> None:
        """Add an insert document to the list of ops."""
        validate_is_document_type("document", document)
        # Generate ObjectId client side.
        if not (isinstance(document, RawBSONDocument) or "_id" in document):
            document["_id"] = ObjectId()
        self.ops.append((_INSERT, document))

    def add_update(
        self,
        selector: Mapping[str, Any],
        update: Union[Mapping[str, Any], _Pipeline],
        multi: bool,
        upsert: Optional[bool],
        collation: Optional[Mapping[str, Any]] = None,
        array_filters: Optional[list[Mapping[str, Any]]] = None,
        hint: Union[str, dict[str, Any], None] = None,
        sort: Optional[Mapping[str, Any]] = None,
    ) -> None:
        """Create an update document and add it to the list of ops."""
        validate_ok_for_update(update)
        cmd: dict[str, Any] = {"q": selector, "u": update, "multi": multi}
        if upsert is not None:
            cmd["upsert"] = upsert
        if collation is not None:
            self.uses_collation = True
            cmd["collation"] = collation
        if array_filters is not None:
            self.uses_array_filters = True
            cmd["arrayFilters"] = array_filters
        if hint is not None:
            self.uses_hint_update = True
            cmd["hint"] = hint
        if sort is not None:
            self.uses_sort = True
            cmd["sort"] = sort
        if multi:
            # A bulk_write containing an update_many is not retryable.
            self.is_retryable = False
        self.ops.append((_UPDATE, cmd))

    def add_replace(
        self,
        selector: Mapping[str, Any],
        replacement: Mapping[str, Any],
        upsert: Optional[bool],
        collation: Optional[Mapping[str, Any]] = None,
        hint: Union[str, dict[str, Any], None] = None,
        sort: Optional[Mapping[str, Any]] = None,
    ) -> None:
        """Create a replace document and add it to the list of ops."""
        validate_ok_for_replace(replacement)
        cmd: dict[str, Any] = {"q": selector, "u": replacement}
        if upsert is not None:
            cmd["upsert"] = upsert
        if collation is not None:
            self.uses_collation = True
            cmd["collation"] = collation
        if hint is not None:
            self.uses_hint_update = True
            cmd["hint"] = hint
        if sort is not None:
            self.uses_sort = True
            cmd["sort"] = sort
        self.ops.append((_UPDATE, cmd))

    def add_delete(
        self,
        selector: Mapping[str, Any],
        limit: int,
        collation: Optional[Mapping[str, Any]] = None,
        hint: Union[str, dict[str, Any], None] = None,
    ) -> None:
        """Create a delete document and add it to the list of ops."""
        cmd: dict[str, Any] = {"q": selector, "limit": limit}
        if collation is not None:
            self.uses_collation = True
            cmd["collation"] = collation
        if hint is not None:
            self.uses_hint_delete = True
            cmd["hint"] = hint
        if limit == _DELETE_ALL:
            # A bulk_write containing a delete_many is not retryable.
            self.is_retryable = False
        self.ops.append((_DELETE, cmd))

    def gen_ordered(self) -> Iterator[Optional[_Run]]:
        """Generate batches of operations, batched by type of
        operation, in the order **provided**.
        """
        run = None
        for idx, (op_type, operation) in enumerate(self.ops):
            if run is None:
                run = _Run(op_type)
            elif run.op_type != op_type:
                yield run
                run = _Run(op_type)
            run.add(idx, operation)
        yield run

    def gen_unordered(self) -> Iterator[_Run]:
        """Generate batches of operations, batched by type of
        operation, in arbitrary order.
        """
        operations = [_Run(_INSERT), _Run(_UPDATE), _Run(_DELETE)]
        for idx, (op_type, operation) in enumerate(self.ops):
            operations[op_type].add(idx, operation)

        for run in operations:
            if run.ops:
                yield run

    @_handle_reauth
    def write_command(
        self,
        bwc: _BulkWriteContext,
        cmd: MutableMapping[str, Any],
        request_id: int,
        msg: bytes,
        docs: list[Mapping[str, Any]],
        client: MongoClient,
    ) -> dict[str, Any]:
        """A proxy for SocketInfo.write_command that handles event publishing."""
        cmd[bwc.field] = docs
        if _COMMAND_LOGGER.isEnabledFor(logging.DEBUG):
            _debug_log(
                _COMMAND_LOGGER,
                message=_CommandStatusMessage.STARTED,
                clientId=client._topology_settings._topology_id,
                command=cmd,
                commandName=next(iter(cmd)),
                databaseName=bwc.db_name,
                requestId=request_id,
                operationId=request_id,
                driverConnectionId=bwc.conn.id,
                serverConnectionId=bwc.conn.server_connection_id,
                serverHost=bwc.conn.address[0],
                serverPort=bwc.conn.address[1],
                serviceId=bwc.conn.service_id,
            )
        if bwc.publish:
            bwc._start(cmd, request_id, docs)
        try:
            reply = bwc.conn.write_command(request_id, msg, bwc.codec)  # type: ignore[misc]
            duration = datetime.datetime.now() - bwc.start_time
            if _COMMAND_LOGGER.isEnabledFor(logging.DEBUG):
                _debug_log(
                    _COMMAND_LOGGER,
                    message=_CommandStatusMessage.SUCCEEDED,
                    clientId=client._topology_settings._topology_id,
                    durationMS=duration,
                    reply=reply,
                    commandName=next(iter(cmd)),
                    databaseName=bwc.db_name,
                    requestId=request_id,
                    operationId=request_id,
                    driverConnectionId=bwc.conn.id,
                    serverConnectionId=bwc.conn.server_connection_id,
                    serverHost=bwc.conn.address[0],
                    serverPort=bwc.conn.address[1],
                    serviceId=bwc.conn.service_id,
                )
            if bwc.publish:
                bwc._succeed(request_id, reply, duration)  # type: ignore[arg-type]
            client._process_response(reply, bwc.session)  # type: ignore[arg-type]
        except Exception as exc:
            duration = datetime.datetime.now() - bwc.start_time
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
                    databaseName=bwc.db_name,
                    requestId=request_id,
                    operationId=request_id,
                    driverConnectionId=bwc.conn.id,
                    serverConnectionId=bwc.conn.server_connection_id,
                    serverHost=bwc.conn.address[0],
                    serverPort=bwc.conn.address[1],
                    serviceId=bwc.conn.service_id,
                    isServerSideError=isinstance(exc, OperationFailure),
                )

            if bwc.publish:
                bwc._fail(request_id, failure, duration)
            # Process the response from the server.
            if isinstance(exc, (NotPrimaryError, OperationFailure)):
                client._process_response(exc.details, bwc.session)  # type: ignore[arg-type]
            raise
        return reply  # type: ignore[return-value]

    def unack_write(
        self,
        bwc: _BulkWriteContext,
        cmd: MutableMapping[str, Any],
        request_id: int,
        msg: bytes,
        max_doc_size: int,
        docs: list[Mapping[str, Any]],
        client: MongoClient,
    ) -> Optional[Mapping[str, Any]]:
        """A proxy for Connection.unack_write that handles event publishing."""
        if _COMMAND_LOGGER.isEnabledFor(logging.DEBUG):
            _debug_log(
                _COMMAND_LOGGER,
                message=_CommandStatusMessage.STARTED,
                clientId=client._topology_settings._topology_id,
                command=cmd,
                commandName=next(iter(cmd)),
                databaseName=bwc.db_name,
                requestId=request_id,
                operationId=request_id,
                driverConnectionId=bwc.conn.id,
                serverConnectionId=bwc.conn.server_connection_id,
                serverHost=bwc.conn.address[0],
                serverPort=bwc.conn.address[1],
                serviceId=bwc.conn.service_id,
            )
        if bwc.publish:
            cmd = bwc._start(cmd, request_id, docs)
        try:
            result = bwc.conn.unack_write(msg, max_doc_size)  # type: ignore[func-returns-value, misc, override]
            duration = datetime.datetime.now() - bwc.start_time
            if result is not None:
                reply = _convert_write_result(bwc.name, cmd, result)  # type: ignore[arg-type]
            else:
                # Comply with APM spec.
                reply = {"ok": 1}
                if _COMMAND_LOGGER.isEnabledFor(logging.DEBUG):
                    _debug_log(
                        _COMMAND_LOGGER,
                        message=_CommandStatusMessage.SUCCEEDED,
                        clientId=client._topology_settings._topology_id,
                        durationMS=duration,
                        reply=reply,
                        commandName=next(iter(cmd)),
                        databaseName=bwc.db_name,
                        requestId=request_id,
                        operationId=request_id,
                        driverConnectionId=bwc.conn.id,
                        serverConnectionId=bwc.conn.server_connection_id,
                        serverHost=bwc.conn.address[0],
                        serverPort=bwc.conn.address[1],
                        serviceId=bwc.conn.service_id,
                    )
            if bwc.publish:
                bwc._succeed(request_id, reply, duration)
        except Exception as exc:
            duration = datetime.datetime.now() - bwc.start_time
            if isinstance(exc, OperationFailure):
                failure: _DocumentOut = _convert_write_result(bwc.name, cmd, exc.details)  # type: ignore[arg-type]
            elif isinstance(exc, NotPrimaryError):
                failure = exc.details  # type: ignore[assignment]
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
                    databaseName=bwc.db_name,
                    requestId=request_id,
                    operationId=request_id,
                    driverConnectionId=bwc.conn.id,
                    serverConnectionId=bwc.conn.server_connection_id,
                    serverHost=bwc.conn.address[0],
                    serverPort=bwc.conn.address[1],
                    serviceId=bwc.conn.service_id,
                    isServerSideError=isinstance(exc, OperationFailure),
                )
            if bwc.publish:
                assert bwc.start_time is not None
                bwc._fail(request_id, failure, duration)
            raise
        return result  # type: ignore[return-value]

    def _execute_batch_unack(
        self,
        bwc: Union[_BulkWriteContext, _EncryptedBulkWriteContext],
        cmd: dict[str, Any],
        ops: list[Mapping[str, Any]],
        client: MongoClient,
    ) -> list[Mapping[str, Any]]:
        if self.is_encrypted:
            _, batched_cmd, to_send = bwc.batch_command(cmd, ops)
            bwc.conn.command(  # type: ignore[misc]
                bwc.db_name,
                batched_cmd,  # type: ignore[arg-type]
                write_concern=WriteConcern(w=0),
                session=bwc.session,  # type: ignore[arg-type]
                client=client,  # type: ignore[arg-type]
            )
        else:
            request_id, msg, to_send = bwc.batch_command(cmd, ops)
            # Though this isn't strictly a "legacy" write, the helper
            # handles publishing commands and sending our message
            # without receiving a result. Send 0 for max_doc_size
            # to disable size checking. Size checking is handled while
            # the documents are encoded to BSON.
            self.unack_write(bwc, cmd, request_id, msg, 0, to_send, client)  # type: ignore[arg-type]

        return to_send

    def _execute_batch(
        self,
        bwc: Union[_BulkWriteContext, _EncryptedBulkWriteContext],
        cmd: dict[str, Any],
        ops: list[Mapping[str, Any]],
        client: MongoClient,
    ) -> tuple[dict[str, Any], list[Mapping[str, Any]]]:
        if self.is_encrypted:
            _, batched_cmd, to_send = bwc.batch_command(cmd, ops)
            result = bwc.conn.command(  # type: ignore[misc]
                bwc.db_name,
                batched_cmd,  # type: ignore[arg-type]
                codec_options=bwc.codec,
                session=bwc.session,  # type: ignore[arg-type]
                client=client,  # type: ignore[arg-type]
            )
        else:
            request_id, msg, to_send = bwc.batch_command(cmd, ops)
            result = self.write_command(bwc, cmd, request_id, msg, to_send, client)  # type: ignore[arg-type]

        return result, to_send  # type: ignore[return-value]

    def _execute_command(
        self,
        generator: Iterator[Any],
        write_concern: WriteConcern,
        session: Optional[ClientSession],
        conn: Connection,
        op_id: int,
        retryable: bool,
        full_result: MutableMapping[str, Any],
        final_write_concern: Optional[WriteConcern] = None,
    ) -> None:
        db_name = self.collection.database.name
        client = self.collection.database.client
        listeners = client._event_listeners

        if not self.current_run:
            self.current_run = next(generator)
            self.next_run = None
        run = self.current_run

        # Connection.command validates the session, but we use
        # Connection.write_command
        conn.validate_session(client, session)
        last_run = False

        while run:
            if not self.retrying:
                self.next_run = next(generator, None)
                if self.next_run is None:
                    last_run = True

            cmd_name = _COMMANDS[run.op_type]
            bwc = self.bulk_ctx_class(
                db_name,
                cmd_name,
                conn,
                op_id,
                listeners,
                session,
                run.op_type,
                self.collection.codec_options,
            )

            while run.idx_offset < len(run.ops):
                # If this is the last possible operation, use the
                # final write concern.
                if last_run and (len(run.ops) - run.idx_offset) == 1:
                    write_concern = final_write_concern or write_concern

                cmd = {cmd_name: self.collection.name, "ordered": self.ordered}
                if self.comment:
                    cmd["comment"] = self.comment
                _csot.apply_write_concern(cmd, write_concern)
                if self.bypass_doc_val is not None:
                    cmd["bypassDocumentValidation"] = self.bypass_doc_val
                if self.let is not None and run.op_type in (_DELETE, _UPDATE):
                    cmd["let"] = self.let
                if session:
                    # Start a new retryable write unless one was already
                    # started for this command.
                    if retryable and not self.started_retryable_write:
                        session._start_retryable_write()
                        self.started_retryable_write = True
                    session._apply_to(cmd, retryable, ReadPreference.PRIMARY, conn)
                conn.send_cluster_time(cmd, session, client)
                conn.add_server_api(cmd)
                # CSOT: apply timeout before encoding the command.
                conn.apply_timeout(client, cmd)
                ops = islice(run.ops, run.idx_offset, None)

                # Run as many ops as possible in one command.
                if write_concern.acknowledged:
                    result, to_send = self._execute_batch(bwc, cmd, ops, client)

                    # Retryable writeConcernErrors halt the execution of this run.
                    wce = result.get("writeConcernError", {})
                    if wce.get("code", 0) in _RETRYABLE_ERROR_CODES:
                        # Synthesize the full bulk result without modifying the
                        # current one because this write operation may be retried.
                        full = copy.deepcopy(full_result)
                        _merge_command(run, full, run.idx_offset, result)
                        _raise_bulk_write_error(full)

                    _merge_command(run, full_result, run.idx_offset, result)

                    # We're no longer in a retry once a command succeeds.
                    self.retrying = False
                    self.started_retryable_write = False

                    if self.ordered and "writeErrors" in result:
                        break
                else:
                    to_send = self._execute_batch_unack(bwc, cmd, ops, client)

                run.idx_offset += len(to_send)

            # We're supposed to continue if errors are
            # at the write concern level (e.g. wtimeout)
            if self.ordered and full_result["writeErrors"]:
                break
            # Reset our state
            self.current_run = run = self.next_run

    def execute_command(
        self,
        generator: Iterator[Any],
        write_concern: WriteConcern,
        session: Optional[ClientSession],
        operation: str,
    ) -> dict[str, Any]:
        """Execute using write commands."""
        # nModified is only reported for write commands, not legacy ops.
        full_result = {
            "writeErrors": [],
            "writeConcernErrors": [],
            "nInserted": 0,
            "nUpserted": 0,
            "nMatched": 0,
            "nModified": 0,
            "nRemoved": 0,
            "upserted": [],
        }
        op_id = _randint()

        def retryable_bulk(
            session: Optional[ClientSession], conn: Connection, retryable: bool
        ) -> None:
            self._execute_command(
                generator,
                write_concern,
                session,
                conn,
                op_id,
                retryable,
                full_result,
            )

        client = self.collection.database.client
        _ = client._retryable_write(
            self.is_retryable,
            retryable_bulk,
            session,
            operation,
            bulk=self,  # type: ignore[arg-type]
            operation_id=op_id,
        )

        if full_result["writeErrors"] or full_result["writeConcernErrors"]:
            _raise_bulk_write_error(full_result)
        return full_result

    def execute_op_msg_no_results(self, conn: Connection, generator: Iterator[Any]) -> None:
        """Execute write commands with OP_MSG and w=0 writeConcern, unordered."""
        db_name = self.collection.database.name
        client = self.collection.database.client
        listeners = client._event_listeners
        op_id = _randint()

        if not self.current_run:
            self.current_run = next(generator)
        run = self.current_run

        while run:
            cmd_name = _COMMANDS[run.op_type]
            bwc = self.bulk_ctx_class(
                db_name,
                cmd_name,
                conn,
                op_id,
                listeners,
                None,
                run.op_type,
                self.collection.codec_options,
            )

            while run.idx_offset < len(run.ops):
                cmd = {
                    cmd_name: self.collection.name,
                    "ordered": False,
                    "writeConcern": {"w": 0},
                }
                conn.add_server_api(cmd)
                ops = islice(run.ops, run.idx_offset, None)
                # Run as many ops as possible.
                to_send = self._execute_batch_unack(bwc, cmd, ops, client)
                run.idx_offset += len(to_send)
            self.current_run = run = next(generator, None)

    def execute_command_no_results(
        self,
        conn: Connection,
        generator: Iterator[Any],
        write_concern: WriteConcern,
    ) -> None:
        """Execute write commands with OP_MSG and w=0 WriteConcern, ordered."""
        full_result = {
            "writeErrors": [],
            "writeConcernErrors": [],
            "nInserted": 0,
            "nUpserted": 0,
            "nMatched": 0,
            "nModified": 0,
            "nRemoved": 0,
            "upserted": [],
        }
        # Ordered bulk writes have to be acknowledged so that we stop
        # processing at the first error, even when the application
        # specified unacknowledged writeConcern.
        initial_write_concern = WriteConcern()
        op_id = _randint()
        try:
            self._execute_command(
                generator,
                initial_write_concern,
                None,
                conn,
                op_id,
                False,
                full_result,
                write_concern,
            )
        except OperationFailure:
            pass

    def execute_no_results(
        self,
        conn: Connection,
        generator: Iterator[Any],
        write_concern: WriteConcern,
    ) -> None:
        """Execute all operations, returning no results (w=0)."""
        if self.uses_collation:
            raise ConfigurationError("Collation is unsupported for unacknowledged writes.")
        if self.uses_array_filters:
            raise ConfigurationError("arrayFilters is unsupported for unacknowledged writes.")
        # Guard against unsupported unacknowledged writes.
        unack = write_concern and not write_concern.acknowledged
        if unack and self.uses_hint_delete and conn.max_wire_version < 9:
            raise ConfigurationError(
                "Must be connected to MongoDB 4.4+ to use hint on unacknowledged delete commands."
            )
        if unack and self.uses_hint_update and conn.max_wire_version < 8:
            raise ConfigurationError(
                "Must be connected to MongoDB 4.2+ to use hint on unacknowledged update commands."
            )
        if unack and self.uses_sort and conn.max_wire_version < 25:
            raise ConfigurationError(
                "Must be connected to MongoDB 8.0+ to use sort on unacknowledged update commands."
            )
        # Cannot have both unacknowledged writes and bypass document validation.
        if self.bypass_doc_val:
            raise OperationFailure(
                "Cannot set bypass_document_validation with unacknowledged write concern"
            )

        if self.ordered:
            return self.execute_command_no_results(conn, generator, write_concern)
        return self.execute_op_msg_no_results(conn, generator)

    def execute(
        self,
        write_concern: WriteConcern,
        session: Optional[ClientSession],
        operation: str,
    ) -> Any:
        """Execute operations."""
        if not self.ops:
            raise InvalidOperation("No operations to execute")
        if self.executed:
            raise InvalidOperation("Bulk operations can only be executed once.")
        self.executed = True
        write_concern = write_concern or self.collection.write_concern
        session = _validate_session_write_concern(session, write_concern)

        if self.ordered:
            generator = self.gen_ordered()
        else:
            generator = self.gen_unordered()

        client = self.collection.database.client
        if not write_concern.acknowledged:
            with client._conn_for_writes(session, operation) as connection:
                self.execute_no_results(connection, generator, write_concern)
                return None
        else:
            return self.execute_command(generator, write_concern, session, operation)
