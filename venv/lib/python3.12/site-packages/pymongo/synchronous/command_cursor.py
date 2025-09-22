# Copyright 2014-present MongoDB, Inc.
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

"""CommandCursor class to iterate over command results."""
from __future__ import annotations

from collections import deque
from typing import (
    TYPE_CHECKING,
    Any,
    Generic,
    Iterator,
    Mapping,
    NoReturn,
    Optional,
    Sequence,
    Union,
)

from bson import CodecOptions, _convert_raw_document_lists_to_streams
from pymongo import _csot
from pymongo.cursor_shared import _CURSOR_CLOSED_ERRORS
from pymongo.errors import ConnectionFailure, InvalidOperation, OperationFailure
from pymongo.message import (
    _CursorAddress,
    _GetMore,
    _OpMsg,
    _OpReply,
    _RawBatchGetMore,
)
from pymongo.response import PinnedResponse
from pymongo.synchronous.cursor import _ConnectionManager
from pymongo.typings import _Address, _DocumentOut, _DocumentType

if TYPE_CHECKING:
    from pymongo.synchronous.client_session import ClientSession
    from pymongo.synchronous.collection import Collection
    from pymongo.synchronous.pool import Connection

_IS_SYNC = True


class CommandCursor(Generic[_DocumentType]):
    """A cursor / iterator over command cursors."""

    _getmore_class = _GetMore

    def __init__(
        self,
        collection: Collection[_DocumentType],
        cursor_info: Mapping[str, Any],
        address: Optional[_Address],
        batch_size: int = 0,
        max_await_time_ms: Optional[int] = None,
        session: Optional[ClientSession] = None,
        explicit_session: bool = False,
        comment: Any = None,
    ) -> None:
        """Create a new command cursor."""
        self._sock_mgr: Any = None
        self._collection: Collection[_DocumentType] = collection
        self._id = cursor_info["id"]
        self._data = deque(cursor_info["firstBatch"])
        self._postbatchresumetoken: Optional[Mapping[str, Any]] = cursor_info.get(
            "postBatchResumeToken"
        )
        self._address = address
        self._batch_size = batch_size
        self._max_await_time_ms = max_await_time_ms
        self._timeout = self._collection.database.client.options.timeout
        self._session = session
        self._explicit_session = explicit_session
        self._killed = self._id == 0
        self._comment = comment
        if self._killed:
            self._end_session()

        if "ns" in cursor_info:  # noqa: SIM401
            self._ns = cursor_info["ns"]
        else:
            self._ns = collection.full_name

        self.batch_size(batch_size)

        if not isinstance(max_await_time_ms, int) and max_await_time_ms is not None:
            raise TypeError(
                f"max_await_time_ms must be an integer or None, not {type(max_await_time_ms)}"
            )

    def __del__(self) -> None:
        self._die_no_lock()

    def batch_size(self, batch_size: int) -> CommandCursor[_DocumentType]:
        """Limits the number of documents returned in one batch. Each batch
        requires a round trip to the server. It can be adjusted to optimize
        performance and limit data transfer.

        .. note:: batch_size can not override MongoDB's internal limits on the
           amount of data it will return to the client in a single batch (i.e
           if you set batch size to 1,000,000,000, MongoDB will currently only
           return 4-16MB of results per batch).

        Raises :exc:`TypeError` if `batch_size` is not an integer.
        Raises :exc:`ValueError` if `batch_size` is less than ``0``.

        :param batch_size: The size of each batch of results requested.
        """
        if not isinstance(batch_size, int):
            raise TypeError(f"batch_size must be an integer, not {type(batch_size)}")
        if batch_size < 0:
            raise ValueError("batch_size must be >= 0")

        self._batch_size = batch_size == 1 and 2 or batch_size
        return self

    def _has_next(self) -> bool:
        """Returns `True` if the cursor has documents remaining from the
        previous batch.
        """
        return len(self._data) > 0

    @property
    def _post_batch_resume_token(self) -> Optional[Mapping[str, Any]]:
        """Retrieve the postBatchResumeToken from the response to a
        changeStream aggregate or getMore.
        """
        return self._postbatchresumetoken

    def _maybe_pin_connection(self, conn: Connection) -> None:
        client = self._collection.database.client
        if not client._should_pin_cursor(self._session):
            return
        if not self._sock_mgr:
            conn.pin_cursor()
            conn_mgr = _ConnectionManager(conn, False)
            # Ensure the connection gets returned when the entire result is
            # returned in the first batch.
            if self._id == 0:
                conn_mgr.close()
            else:
                self._sock_mgr = conn_mgr

    def _unpack_response(
        self,
        response: Union[_OpReply, _OpMsg],
        cursor_id: Optional[int],
        codec_options: CodecOptions[Mapping[str, Any]],
        user_fields: Optional[Mapping[str, Any]] = None,
        legacy_response: bool = False,
    ) -> Sequence[_DocumentOut]:
        return response.unpack_response(cursor_id, codec_options, user_fields, legacy_response)

    @property
    def alive(self) -> bool:
        """Does this cursor have the potential to return more data?

        Even if :attr:`alive` is ``True``, :meth:`next` can raise
        :exc:`StopIteration`. Best to use a for loop::

            for doc in collection.aggregate(pipeline):
                print(doc)

        .. note:: :attr:`alive` can be True while iterating a cursor from
          a failed server. In this case :attr:`alive` will return False after
          :meth:`next` fails to retrieve the next batch of results from the
          server.
        """
        return bool(len(self._data) or (not self._killed))

    @property
    def cursor_id(self) -> int:
        """Returns the id of the cursor."""
        return self._id

    @property
    def address(self) -> Optional[_Address]:
        """The (host, port) of the server used, or None.

        .. versionadded:: 3.0
        """
        return self._address

    @property
    def session(self) -> Optional[ClientSession]:
        """The cursor's :class:`~pymongo.client_session.ClientSession`, or None.

        .. versionadded:: 3.6
        """
        if self._explicit_session:
            return self._session
        return None

    def _prepare_to_die(self) -> tuple[int, Optional[_CursorAddress]]:
        already_killed = self._killed
        self._killed = True
        if self._id and not already_killed:
            cursor_id = self._id
            assert self._address is not None
            address = _CursorAddress(self._address, self._ns)
        else:
            # Skip killCursors.
            cursor_id = 0
            address = None
        return cursor_id, address

    def _die_no_lock(self) -> None:
        """Closes this cursor without acquiring a lock."""
        cursor_id, address = self._prepare_to_die()
        self._collection.database.client._cleanup_cursor_no_lock(
            cursor_id, address, self._sock_mgr, self._session, self._explicit_session
        )
        if not self._explicit_session:
            self._session = None
        self._sock_mgr = None

    def _die_lock(self) -> None:
        """Closes this cursor."""
        cursor_id, address = self._prepare_to_die()
        self._collection.database.client._cleanup_cursor_lock(
            cursor_id,
            address,
            self._sock_mgr,
            self._session,
            self._explicit_session,
        )
        if not self._explicit_session:
            self._session = None
        self._sock_mgr = None

    def _end_session(self) -> None:
        if self._session and not self._explicit_session:
            self._session._end_implicit_session()
            self._session = None

    def close(self) -> None:
        """Explicitly close / kill this cursor."""
        self._die_lock()

    def _send_message(self, operation: _GetMore) -> None:
        """Send a getmore message and handle the response."""
        client = self._collection.database.client
        try:
            response = client._run_operation(
                operation, self._unpack_response, address=self._address
            )
        except OperationFailure as exc:
            if exc.code in _CURSOR_CLOSED_ERRORS:
                # Don't send killCursors because the cursor is already closed.
                self._killed = True
            if exc.timeout:
                self._die_no_lock()
            else:
                # Return the session and pinned connection, if necessary.
                self.close()
            raise
        except ConnectionFailure:
            # Don't send killCursors because the cursor is already closed.
            self._killed = True
            # Return the session and pinned connection, if necessary.
            self.close()
            raise
        except Exception:
            self.close()
            raise

        if isinstance(response, PinnedResponse):
            if not self._sock_mgr:
                self._sock_mgr = _ConnectionManager(response.conn, response.more_to_come)  # type: ignore[arg-type]
        if response.from_command:
            cursor = response.docs[0]["cursor"]
            documents = cursor["nextBatch"]
            self._postbatchresumetoken = cursor.get("postBatchResumeToken")
            self._id = cursor["id"]
        else:
            documents = response.docs
            assert isinstance(response.data, _OpReply)
            self._id = response.data.cursor_id

        if self._id == 0:
            self.close()
        self._data = deque(documents)

    def _refresh(self) -> int:
        """Refreshes the cursor with more data from the server.

        Returns the length of self._data after refresh. Will exit early if
        self._data is already non-empty. Raises OperationFailure when the
        cursor cannot be refreshed due to an error on the query.
        """
        if len(self._data) or self._killed:
            return len(self._data)

        if self._id:  # Get More
            dbname, collname = self._ns.split(".", 1)
            read_pref = self._collection._read_preference_for(self.session)
            self._send_message(
                self._getmore_class(
                    dbname,
                    collname,
                    self._batch_size,
                    self._id,
                    self._collection.codec_options,
                    read_pref,
                    self._session,
                    self._collection.database.client,
                    self._max_await_time_ms,
                    self._sock_mgr,
                    False,
                    self._comment,
                )
            )
        else:  # Cursor id is zero nothing else to return
            self._die_lock()

        return len(self._data)

    def __iter__(self) -> Iterator[_DocumentType]:
        return self

    def next(self) -> _DocumentType:
        """Advance the cursor."""
        # Block until a document is returnable.
        while self.alive:
            doc = self._try_next(True)
            if doc is not None:
                return doc

        raise StopIteration

    def __next__(self) -> _DocumentType:
        return self.next()

    def _try_next(self, get_more_allowed: bool) -> Optional[_DocumentType]:
        """Advance the cursor blocking for at most one getMore command."""
        if not len(self._data) and not self._killed and get_more_allowed:
            self._refresh()
        if len(self._data):
            return self._data.popleft()
        else:
            return None

    def _next_batch(self, result: list, total: Optional[int] = None) -> bool:
        """Get all or some available documents from the cursor."""
        if not len(self._data) and not self._killed:
            self._refresh()
        if len(self._data):
            if total is None:
                result.extend(self._data)
                self._data.clear()
            else:
                for _ in range(min(len(self._data), total)):
                    result.append(self._data.popleft())
            return True
        else:
            return False

    def try_next(self) -> Optional[_DocumentType]:
        """Advance the cursor without blocking indefinitely.

        This method returns the next document without waiting
        indefinitely for data.

        If no document is cached locally then this method runs a single
        getMore command. If the getMore yields any documents, the next
        document is returned, otherwise, if the getMore returns no documents
        (because there is no additional data) then ``None`` is returned.

        :return: The next document or ``None`` when no document is available
          after running a single getMore or when the cursor is closed.

        .. versionadded:: 4.5
        """
        return self._try_next(get_more_allowed=True)

    def __enter__(self) -> CommandCursor[_DocumentType]:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    @_csot.apply
    def to_list(self, length: Optional[int] = None) -> list[_DocumentType]:
        """Converts the contents of this cursor to a list more efficiently than ``[doc for doc in cursor]``.

        To use::

          >>> cursor.to_list()

        Or, so read at most n items from the cursor::

          >>> cursor.to_list(n)

        If the cursor is empty or has no more results, an empty list will be returned.

        .. versionadded:: 4.9
        """
        res: list[_DocumentType] = []
        remaining = length
        if isinstance(length, int) and length < 1:
            raise ValueError("to_list() length must be greater than 0")
        while self.alive:
            if not self._next_batch(res, remaining):
                break
            if length is not None:
                remaining = length - len(res)
                if remaining == 0:
                    break
        return res


class RawBatchCommandCursor(CommandCursor[_DocumentType]):
    _getmore_class = _RawBatchGetMore

    def __init__(
        self,
        collection: Collection[_DocumentType],
        cursor_info: Mapping[str, Any],
        address: Optional[_Address],
        batch_size: int = 0,
        max_await_time_ms: Optional[int] = None,
        session: Optional[ClientSession] = None,
        explicit_session: bool = False,
        comment: Any = None,
    ) -> None:
        """Create a new cursor / iterator over raw batches of BSON data.

        Should not be called directly by application developers -
        see :meth:`~pymongo.collection.Collection.aggregate_raw_batches`
        instead.

        .. seealso:: The MongoDB documentation on `cursors <https://dochub.mongodb.org/core/cursors>`_.
        """
        assert not cursor_info.get("firstBatch")
        super().__init__(
            collection,
            cursor_info,
            address,
            batch_size,
            max_await_time_ms,
            session,
            explicit_session,
            comment,
        )

    def _unpack_response(  # type: ignore[override]
        self,
        response: Union[_OpReply, _OpMsg],
        cursor_id: Optional[int],
        codec_options: CodecOptions,
        user_fields: Optional[Mapping[str, Any]] = None,
        legacy_response: bool = False,
    ) -> list[Mapping[str, Any]]:
        raw_response = response.raw_response(cursor_id, user_fields=user_fields)
        if not legacy_response:
            # OP_MSG returns firstBatch/nextBatch documents as a BSON array
            # Re-assemble the array of documents into a document stream
            _convert_raw_document_lists_to_streams(raw_response[0])
        return raw_response  # type: ignore[return-value]

    def __getitem__(self, index: int) -> NoReturn:
        raise InvalidOperation("Cannot call __getitem__ on RawBatchCommandCursor")
