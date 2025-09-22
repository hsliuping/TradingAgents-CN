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

"""The client-level bulk write operations interface.

.. versionadded:: 4.9
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
    Mapping,
    Optional,
    Type,
    Union,
)

from bson.objectid import ObjectId
from bson.raw_bson import RawBSONDocument
from pymongo import _csot, common
from pymongo.synchronous.client_session import ClientSession, _validate_session_write_concern
from pymongo.synchronous.collection import Collection
from pymongo.synchronous.command_cursor import CommandCursor
from pymongo.synchronous.database import Database
from pymongo.synchronous.helpers import _handle_reauth

if TYPE_CHECKING:
    from pymongo.synchronous.mongo_client import MongoClient
    from pymongo.synchronous.pool import Connection
from pymongo._client_bulk_shared import (
    _merge_command,
    _throw_client_bulk_write_exception,
)
from pymongo.common import (
    validate_is_document_type,
    validate_ok_for_replace,
    validate_ok_for_update,
)
from pymongo.errors import (
    ConfigurationError,
    ConnectionFailure,
    InvalidOperation,
    NotPrimaryError,
    OperationFailure,
    WaitQueueTimeoutError,
)
from pymongo.helpers_shared import _RETRYABLE_ERROR_CODES
from pymongo.logger import _COMMAND_LOGGER, _CommandStatusMessage, _debug_log
from pymongo.message import (
    _ClientBulkWriteContext,
    _convert_client_bulk_exception,
    _convert_exception,
    _convert_write_result,
    _randint,
)
from pymongo.read_preferences import ReadPreference
from pymongo.results import (
    ClientBulkWriteResult,
    DeleteResult,
    InsertOneResult,
    UpdateResult,
)
from pymongo.typings import _DocumentOut, _Pipeline
from pymongo.write_concern import WriteConcern

_IS_SYNC = True


class _ClientBulk:
    """The private guts of the client-level bulk write API."""

    def __init__(
        self,
        client: MongoClient,
        write_concern: WriteConcern,
        ordered: bool = True,
        bypass_document_validation: Optional[bool] = None,
        comment: Optional[str] = None,
        let: Optional[Any] = None,
        verbose_results: bool = False,
    ) -> None:
        """Initialize a _ClientBulk instance."""
        self.client = client
        self.write_concern = write_concern
        self.let = let
        if self.let is not None:
            common.validate_is_document_type("let", self.let)
        self.ordered = ordered
        self.bypass_doc_val = bypass_document_validation
        self.comment = comment
        self.verbose_results = verbose_results
        self.ops: list[tuple[str, Mapping[str, Any]]] = []
        self.namespaces: list[str] = []
        self.idx_offset: int = 0
        self.total_ops: int = 0
        self.executed = False
        self.uses_collation = False
        self.uses_array_filters = False
        self.is_retryable = self.client.options.retry_writes
        self.retrying = False
        self.started_retryable_write = False

    @property
    def bulk_ctx_class(self) -> Type[_ClientBulkWriteContext]:
        return _ClientBulkWriteContext

    def add_insert(self, namespace: str, document: _DocumentOut) -> None:
        """Add an insert document to the list of ops."""
        validate_is_document_type("document", document)
        # Generate ObjectId client side.
        if not (isinstance(document, RawBSONDocument) or "_id" in document):
            document["_id"] = ObjectId()
        cmd = {"insert": -1, "document": document}
        self.ops.append(("insert", cmd))
        self.namespaces.append(namespace)
        self.total_ops += 1

    def add_update(
        self,
        namespace: str,
        selector: Mapping[str, Any],
        update: Union[Mapping[str, Any], _Pipeline],
        multi: bool,
        upsert: Optional[bool] = None,
        collation: Optional[Mapping[str, Any]] = None,
        array_filters: Optional[list[Mapping[str, Any]]] = None,
        hint: Union[str, dict[str, Any], None] = None,
        sort: Optional[Mapping[str, Any]] = None,
    ) -> None:
        """Create an update document and add it to the list of ops."""
        validate_ok_for_update(update)
        cmd = {
            "update": -1,
            "filter": selector,
            "updateMods": update,
            "multi": multi,
        }
        if upsert is not None:
            cmd["upsert"] = upsert
        if array_filters is not None:
            self.uses_array_filters = True
            cmd["arrayFilters"] = array_filters
        if hint is not None:
            cmd["hint"] = hint
        if collation is not None:
            self.uses_collation = True
            cmd["collation"] = collation
        if sort is not None:
            cmd["sort"] = sort
        if multi:
            # A bulk_write containing an update_many is not retryable.
            self.is_retryable = False
        self.ops.append(("update", cmd))
        self.namespaces.append(namespace)
        self.total_ops += 1

    def add_replace(
        self,
        namespace: str,
        selector: Mapping[str, Any],
        replacement: Mapping[str, Any],
        upsert: Optional[bool] = None,
        collation: Optional[Mapping[str, Any]] = None,
        hint: Union[str, dict[str, Any], None] = None,
        sort: Optional[Mapping[str, Any]] = None,
    ) -> None:
        """Create a replace document and add it to the list of ops."""
        validate_ok_for_replace(replacement)
        cmd = {
            "update": -1,
            "filter": selector,
            "updateMods": replacement,
            "multi": False,
        }
        if upsert is not None:
            cmd["upsert"] = upsert
        if hint is not None:
            cmd["hint"] = hint
        if collation is not None:
            self.uses_collation = True
            cmd["collation"] = collation
        if sort is not None:
            cmd["sort"] = sort
        self.ops.append(("replace", cmd))
        self.namespaces.append(namespace)
        self.total_ops += 1

    def add_delete(
        self,
        namespace: str,
        selector: Mapping[str, Any],
        multi: bool,
        collation: Optional[Mapping[str, Any]] = None,
        hint: Union[str, dict[str, Any], None] = None,
    ) -> None:
        """Create a delete document and add it to the list of ops."""
        cmd = {"delete": -1, "filter": selector, "multi": multi}
        if hint is not None:
            cmd["hint"] = hint
        if collation is not None:
            self.uses_collation = True
            cmd["collation"] = collation
        if multi:
            # A bulk_write containing an update_many is not retryable.
            self.is_retryable = False
        self.ops.append(("delete", cmd))
        self.namespaces.append(namespace)
        self.total_ops += 1

    @_handle_reauth
    def write_command(
        self,
        bwc: _ClientBulkWriteContext,
        cmd: MutableMapping[str, Any],
        request_id: int,
        msg: Union[bytes, dict[str, Any]],
        op_docs: list[Mapping[str, Any]],
        ns_docs: list[Mapping[str, Any]],
        client: MongoClient,
    ) -> dict[str, Any]:
        """A proxy for Connection.write_command that handles event publishing."""
        cmd["ops"] = op_docs
        cmd["nsInfo"] = ns_docs
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
            bwc._start(cmd, request_id, op_docs, ns_docs)
        try:
            reply = bwc.conn.write_command(request_id, msg, bwc.codec)  # type: ignore[misc, arg-type]
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
            # Process the response from the server.
            self.client._process_response(reply, bwc.session)  # type: ignore[arg-type]
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
            # Top-level error will be embedded in ClientBulkWriteException.
            reply = {"error": exc}
            # Process the response from the server.
            if isinstance(exc, OperationFailure):
                self.client._process_response(exc.details, bwc.session)  # type: ignore[arg-type]
            else:
                self.client._process_response({}, bwc.session)  # type: ignore[arg-type]
        return reply  # type: ignore[return-value]

    def unack_write(
        self,
        bwc: _ClientBulkWriteContext,
        cmd: MutableMapping[str, Any],
        request_id: int,
        msg: bytes,
        op_docs: list[Mapping[str, Any]],
        ns_docs: list[Mapping[str, Any]],
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
            cmd = bwc._start(cmd, request_id, op_docs, ns_docs)
        try:
            result = bwc.conn.unack_write(msg, bwc.max_bson_size)  # type: ignore[func-returns-value, misc, override]
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
            # Top-level error will be embedded in ClientBulkWriteException.
            reply = {"error": exc}
        return reply

    def _execute_batch_unack(
        self,
        bwc: _ClientBulkWriteContext,
        cmd: dict[str, Any],
        ops: list[tuple[str, Mapping[str, Any]]],
        namespaces: list[str],
    ) -> tuple[list[Mapping[str, Any]], list[Mapping[str, Any]]]:
        """Executes a batch of bulkWrite server commands (unack)."""
        request_id, msg, to_send_ops, to_send_ns = bwc.batch_command(cmd, ops, namespaces)
        self.unack_write(bwc, cmd, request_id, msg, to_send_ops, to_send_ns, self.client)  # type: ignore[arg-type]
        return to_send_ops, to_send_ns

    def _execute_batch(
        self,
        bwc: _ClientBulkWriteContext,
        cmd: dict[str, Any],
        ops: list[tuple[str, Mapping[str, Any]]],
        namespaces: list[str],
    ) -> tuple[dict[str, Any], list[Mapping[str, Any]], list[Mapping[str, Any]]]:
        """Executes a batch of bulkWrite server commands (ack)."""
        request_id, msg, to_send_ops, to_send_ns = bwc.batch_command(cmd, ops, namespaces)
        result = self.write_command(bwc, cmd, request_id, msg, to_send_ops, to_send_ns, self.client)  # type: ignore[arg-type]
        return result, to_send_ops, to_send_ns  # type: ignore[return-value]

    def _process_results_cursor(
        self,
        full_result: MutableMapping[str, Any],
        result: MutableMapping[str, Any],
        conn: Connection,
        session: Optional[ClientSession],
    ) -> None:
        """Internal helper for processing the server reply command cursor."""
        if result.get("cursor"):
            coll = Collection(
                database=Database(self.client, "admin"),
                name="$cmd.bulkWrite",
            )
            cmd_cursor = CommandCursor(
                coll,
                result["cursor"],
                conn.address,
                session=session,
                explicit_session=session is not None,
                comment=self.comment,
            )
            cmd_cursor._maybe_pin_connection(conn)

            # Iterate the cursor to get individual write results.
            try:
                for doc in cmd_cursor:
                    original_index = doc["idx"] + self.idx_offset
                    op_type, op = self.ops[original_index]

                    if not doc["ok"]:
                        result["writeErrors"].append(doc)
                        if self.ordered:
                            return

                    # Record individual write result.
                    if doc["ok"] and self.verbose_results:
                        if op_type == "insert":
                            inserted_id = op["document"]["_id"]
                            res = InsertOneResult(inserted_id, acknowledged=True)  # type: ignore[assignment]
                        if op_type in ["update", "replace"]:
                            op_type = "update"
                            res = UpdateResult(doc, acknowledged=True, in_client_bulk=True)  # type: ignore[assignment]
                        if op_type == "delete":
                            res = DeleteResult(doc, acknowledged=True)  # type: ignore[assignment]
                        full_result[f"{op_type}Results"][original_index] = res
            except Exception as exc:
                # Attempt to close the cursor, then raise top-level error.
                if cmd_cursor.alive:
                    cmd_cursor.close()
                result["error"] = _convert_client_bulk_exception(exc)

    def _execute_command(
        self,
        write_concern: WriteConcern,
        session: Optional[ClientSession],
        conn: Connection,
        op_id: int,
        retryable: bool,
        full_result: MutableMapping[str, Any],
        final_write_concern: Optional[WriteConcern] = None,
    ) -> None:
        """Internal helper for executing batches of bulkWrite commands."""
        db_name = "admin"
        cmd_name = "bulkWrite"
        listeners = self.client._event_listeners

        # Connection.command validates the session, but we use
        # Connection.write_command
        conn.validate_session(self.client, session)

        bwc = self.bulk_ctx_class(
            db_name,
            cmd_name,
            conn,
            op_id,
            listeners,  # type: ignore[arg-type]
            session,
            self.client.codec_options,
        )

        while self.idx_offset < self.total_ops:
            # If this is the last possible batch, use the
            # final write concern.
            if self.total_ops - self.idx_offset <= bwc.max_write_batch_size:
                write_concern = final_write_concern or write_concern

            # Construct the server command, specifying the relevant options.
            cmd = {"bulkWrite": 1}
            cmd["errorsOnly"] = not self.verbose_results
            cmd["ordered"] = self.ordered  # type: ignore[assignment]
            not_in_transaction = session and not session.in_transaction
            if not_in_transaction or not session:
                _csot.apply_write_concern(cmd, write_concern)
            if self.bypass_doc_val is not None:
                cmd["bypassDocumentValidation"] = self.bypass_doc_val
            if self.comment:
                cmd["comment"] = self.comment  # type: ignore[assignment]
            if self.let:
                cmd["let"] = self.let

            if session:
                # Start a new retryable write unless one was already
                # started for this command.
                if retryable and not self.started_retryable_write:
                    session._start_retryable_write()
                    self.started_retryable_write = True
                session._apply_to(cmd, retryable, ReadPreference.PRIMARY, conn)
            conn.send_cluster_time(cmd, session, self.client)
            conn.add_server_api(cmd)
            # CSOT: apply timeout before encoding the command.
            conn.apply_timeout(self.client, cmd)
            ops = islice(self.ops, self.idx_offset, None)
            namespaces = islice(self.namespaces, self.idx_offset, None)

            # Run as many ops as possible in one server command.
            if write_concern.acknowledged:
                raw_result, to_send_ops, _ = self._execute_batch(bwc, cmd, ops, namespaces)  # type: ignore[arg-type]
                result = raw_result

                # Top-level server/network error.
                if result.get("error"):
                    error = result["error"]
                    retryable_top_level_error = (
                        hasattr(error, "details")
                        and isinstance(error.details, dict)
                        and error.details.get("code", 0) in _RETRYABLE_ERROR_CODES
                    )
                    retryable_network_error = isinstance(
                        error, ConnectionFailure
                    ) and not isinstance(error, (NotPrimaryError, WaitQueueTimeoutError))

                    # Synthesize the full bulk result without modifying the
                    # current one because this write operation may be retried.
                    if retryable and (retryable_top_level_error or retryable_network_error):
                        full = copy.deepcopy(full_result)
                        _merge_command(self.ops, self.idx_offset, full, result)
                        _throw_client_bulk_write_exception(full, self.verbose_results)
                    else:
                        _merge_command(self.ops, self.idx_offset, full_result, result)
                        _throw_client_bulk_write_exception(full_result, self.verbose_results)

                result["error"] = None
                result["writeErrors"] = []
                if result.get("nErrors", 0) < len(to_send_ops):
                    full_result["anySuccessful"] = True

                # Top-level command error.
                if not result["ok"]:
                    result["error"] = raw_result
                    _merge_command(self.ops, self.idx_offset, full_result, result)
                    break

                if retryable:
                    # Retryable writeConcernErrors halt the execution of this batch.
                    wce = result.get("writeConcernError", {})
                    if wce.get("code", 0) in _RETRYABLE_ERROR_CODES:
                        # Synthesize the full bulk result without modifying the
                        # current one because this write operation may be retried.
                        full = copy.deepcopy(full_result)
                        _merge_command(self.ops, self.idx_offset, full, result)
                        _throw_client_bulk_write_exception(full, self.verbose_results)

                # Process the server reply as a command cursor.
                self._process_results_cursor(full_result, result, conn, session)

                # Merge this batch's results with the full results.
                _merge_command(self.ops, self.idx_offset, full_result, result)

                # We're no longer in a retry once a command succeeds.
                self.retrying = False
                self.started_retryable_write = False

            else:
                to_send_ops, _ = self._execute_batch_unack(bwc, cmd, ops, namespaces)  # type: ignore[arg-type]

            self.idx_offset += len(to_send_ops)

            # We halt execution if we hit a top-level error,
            # or an individual error in an ordered bulk write.
            if full_result["error"] or (self.ordered and full_result["writeErrors"]):
                break

    def execute_command(
        self,
        session: Optional[ClientSession],
        operation: str,
    ) -> MutableMapping[str, Any]:
        """Execute commands with w=1 WriteConcern."""
        full_result: MutableMapping[str, Any] = {
            "anySuccessful": False,
            "error": None,
            "writeErrors": [],
            "writeConcernErrors": [],
            "nInserted": 0,
            "nUpserted": 0,
            "nMatched": 0,
            "nModified": 0,
            "nDeleted": 0,
            "insertResults": {},
            "updateResults": {},
            "deleteResults": {},
        }
        op_id = _randint()

        def retryable_bulk(
            session: Optional[ClientSession],
            conn: Connection,
            retryable: bool,
        ) -> None:
            if conn.max_wire_version < 25:
                raise InvalidOperation(
                    "MongoClient.bulk_write requires MongoDB server version 8.0+."
                )
            self._execute_command(
                self.write_concern,
                session,
                conn,
                op_id,
                retryable,
                full_result,
            )

        self.client._retryable_write(
            self.is_retryable,
            retryable_bulk,
            session,
            operation,
            bulk=self,
            operation_id=op_id,
        )

        if full_result["error"] or full_result["writeErrors"] or full_result["writeConcernErrors"]:
            _throw_client_bulk_write_exception(full_result, self.verbose_results)
        return full_result

    def execute_command_unack(
        self,
        conn: Connection,
    ) -> None:
        """Execute commands with OP_MSG and w=0 writeConcern. Always unordered."""
        db_name = "admin"
        cmd_name = "bulkWrite"
        listeners = self.client._event_listeners
        op_id = _randint()

        bwc = self.bulk_ctx_class(
            db_name,
            cmd_name,
            conn,
            op_id,
            listeners,  # type: ignore[arg-type]
            None,
            self.client.codec_options,
        )

        while self.idx_offset < self.total_ops:
            # Construct the server command, specifying the relevant options.
            cmd = {"bulkWrite": 1}
            cmd["errorsOnly"] = True
            cmd["ordered"] = False
            if self.bypass_doc_val is not None:
                cmd["bypassDocumentValidation"] = self.bypass_doc_val
            cmd["writeConcern"] = {"w": 0}  # type: ignore[assignment]
            if self.comment:
                cmd["comment"] = self.comment  # type: ignore[assignment]
            if self.let:
                cmd["let"] = self.let

            conn.add_server_api(cmd)
            ops = islice(self.ops, self.idx_offset, None)
            namespaces = islice(self.namespaces, self.idx_offset, None)

            # Run as many ops as possible in one server command.
            to_send_ops, _ = self._execute_batch_unack(bwc, cmd, ops, namespaces)  # type: ignore[arg-type]

            self.idx_offset += len(to_send_ops)

    def execute_no_results(
        self,
        conn: Connection,
    ) -> None:
        """Execute all operations, returning no results (w=0)."""
        if self.uses_collation:
            raise ConfigurationError("Collation is unsupported for unacknowledged writes.")
        if self.uses_array_filters:
            raise ConfigurationError("arrayFilters is unsupported for unacknowledged writes.")
        # Cannot have both unacknowledged writes and bypass document validation.
        if self.bypass_doc_val is not None:
            raise OperationFailure(
                "Cannot set bypass_document_validation with unacknowledged write concern"
            )

        return self.execute_command_unack(conn)

    def execute(
        self,
        session: Optional[ClientSession],
        operation: str,
    ) -> Any:
        """Execute operations."""
        if not self.ops:
            raise InvalidOperation("No operations to execute")
        if self.executed:
            raise InvalidOperation("Bulk operations can only be executed once.")
        self.executed = True
        session = _validate_session_write_concern(session, self.write_concern)

        if not self.write_concern.acknowledged:
            with self.client._conn_for_writes(session, operation) as connection:
                if connection.max_wire_version < 25:
                    raise InvalidOperation(
                        "MongoClient.bulk_write requires MongoDB server version 8.0+."
                    )
                self.execute_no_results(connection)
                return ClientBulkWriteResult(None, False, False)  # type: ignore[arg-type]

        result = self.execute_command(session, operation)
        return ClientBulkWriteResult(
            result,
            self.write_concern.acknowledged,
            self.verbose_results,
        )
