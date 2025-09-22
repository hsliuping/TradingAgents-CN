# Copyright 2009-present MongoDB, Inc.
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

"""Tools for representing files stored in GridFS."""
from __future__ import annotations

import datetime
import inspect
import io
import math
from collections import abc
from typing import Any, Iterable, Mapping, NoReturn, Optional, cast

from bson.int64 import Int64
from bson.objectid import ObjectId
from gridfs.errors import CorruptGridFile, FileExists, NoFile
from gridfs.grid_file_shared import (
    _C_INDEX,
    _CHUNK_OVERHEAD,
    _F_INDEX,
    _SEEK_CUR,
    _SEEK_END,
    _SEEK_SET,
    _UPLOAD_BUFFER_CHUNKS,
    _UPLOAD_BUFFER_SIZE,
    DEFAULT_CHUNK_SIZE,
    EMPTY,
    NEWLN,
    _clear_entity_type_registry,
    _grid_in_property,
    _grid_out_property,
)
from pymongo import ASCENDING, DESCENDING, WriteConcern, _csot
from pymongo.common import validate_string
from pymongo.errors import (
    BulkWriteError,
    ConfigurationError,
    CursorNotFound,
    DuplicateKeyError,
    InvalidOperation,
    OperationFailure,
)
from pymongo.helpers_shared import _check_write_command_response
from pymongo.read_preferences import ReadPreference, _ServerMode
from pymongo.synchronous.client_session import ClientSession
from pymongo.synchronous.collection import Collection
from pymongo.synchronous.cursor import Cursor
from pymongo.synchronous.database import Database
from pymongo.synchronous.helpers import next

_IS_SYNC = True


def _disallow_transactions(session: Optional[ClientSession]) -> None:
    if session and session.in_transaction:
        raise InvalidOperation("GridFS does not support multi-document transactions")


class GridFS:
    """An instance of GridFS on top of a single Database."""

    def __init__(self, database: Database, collection: str = "fs"):
        """Create a new instance of :class:`GridFS`.

        Raises :class:`TypeError` if `database` is not an instance of
        :class:`~pymongo.database.Database`.

        :param database: database to use
        :param collection: root collection to use

        .. versionchanged:: 4.0
           Removed the `disable_md5` parameter. See
           :ref:`removed-gridfs-checksum` for details.

        .. versionchanged:: 3.11
           Running a GridFS operation in a transaction now always raises an
           error. GridFS does not support multi-document transactions.

        .. versionchanged:: 3.7
           Added the `disable_md5` parameter.

        .. versionchanged:: 3.1
           Indexes are only ensured on the first write to the DB.

        .. versionchanged:: 3.0
           `database` must use an acknowledged
           :attr:`~pymongo.database.Database.write_concern`

        .. seealso:: The MongoDB documentation on `gridfs <https://dochub.mongodb.org/core/gridfs>`_.
        """
        if not isinstance(database, Database):
            raise TypeError(f"database must be an instance of Database, not {type(database)}")

        database = _clear_entity_type_registry(database)

        if not database.write_concern.acknowledged:
            raise ConfigurationError("database must use acknowledged write_concern")

        self._collection = database[collection]
        self._files = self._collection.files
        self._chunks = self._collection.chunks

    def new_file(self, **kwargs: Any) -> GridIn:
        """Create a new file in GridFS.

        Returns a new :class:`~gridfs.grid_file.GridIn` instance to
        which data can be written. Any keyword arguments will be
        passed through to :meth:`~gridfs.grid_file.GridIn`.

        If the ``"_id"`` of the file is manually specified, it must
        not already exist in GridFS. Otherwise
        :class:`~gridfs.errors.FileExists` is raised.

        :param kwargs: keyword arguments for file creation
        """
        return GridIn(self._collection, **kwargs)

    def put(self, data: Any, **kwargs: Any) -> Any:
        """Put data in GridFS as a new file.

        Equivalent to doing::

          with fs.new_file(**kwargs) as f:
              f.write(data)

        `data` can be either an instance of :class:`bytes` or a file-like
        object providing a :meth:`read` method. If an `encoding` keyword
        argument is passed, `data` can also be a :class:`str` instance, which
        will be encoded as `encoding` before being written. Any keyword
        arguments will be passed through to the created file - see
        :meth:`~gridfs.grid_file.GridIn` for possible arguments. Returns the
        ``"_id"`` of the created file.

        If the ``"_id"`` of the file is manually specified, it must
        not already exist in GridFS. Otherwise
        :class:`~gridfs.errors.FileExists` is raised.

        :param data: data to be written as a file.
        :param kwargs: keyword arguments for file creation

        .. versionchanged:: 3.0
           w=0 writes to GridFS are now prohibited.
        """
        with GridIn(self._collection, **kwargs) as grid_file:
            grid_file.write(data)
            return grid_file._id

    def get(self, file_id: Any, session: Optional[ClientSession] = None) -> GridOut:
        """Get a file from GridFS by ``"_id"``.

        Returns an instance of :class:`~gridfs.grid_file.GridOut`,
        which provides a file-like interface for reading.

        :param file_id: ``"_id"`` of the file to get
        :param session: a
            :class:`~pymongo.client_session.ClientSession`

        .. versionchanged:: 3.6
           Added ``session`` parameter.
        """
        gout = GridOut(self._collection, file_id, session=session)

        # Raise NoFile now, instead of on first attribute access.
        gout.open()
        return gout

    def get_version(
        self,
        filename: Optional[str] = None,
        version: Optional[int] = -1,
        session: Optional[ClientSession] = None,
        **kwargs: Any,
    ) -> GridOut:
        """Get a file from GridFS by ``"filename"`` or metadata fields.

        Returns a version of the file in GridFS whose filename matches
        `filename` and whose metadata fields match the supplied keyword
        arguments, as an instance of :class:`~gridfs.grid_file.GridOut`.

        Version numbering is a convenience atop the GridFS API provided
        by MongoDB. If more than one file matches the query (either by
        `filename` alone, by metadata fields, or by a combination of
        both), then version ``-1`` will be the most recently uploaded
        matching file, ``-2`` the second most recently
        uploaded, etc. Version ``0`` will be the first version
        uploaded, ``1`` the second version, etc. So if three versions
        have been uploaded, then version ``0`` is the same as version
        ``-3``, version ``1`` is the same as version ``-2``, and
        version ``2`` is the same as version ``-1``.

        Raises :class:`~gridfs.errors.NoFile` if no such version of
        that file exists.

        :param filename: ``"filename"`` of the file to get, or `None`
        :param version: version of the file to get (defaults
            to -1, the most recent version uploaded)
        :param session: a
            :class:`~pymongo.client_session.ClientSession`
        :param kwargs: find files by custom metadata.

        .. versionchanged:: 3.6
           Added ``session`` parameter.

        .. versionchanged:: 3.1
           ``get_version`` no longer ensures indexes.
        """
        query = kwargs
        if filename is not None:
            query["filename"] = filename

        _disallow_transactions(session)
        cursor = self._files.find(query, session=session)
        if version is None:
            version = -1
        if version < 0:
            skip = abs(version) - 1
            cursor.limit(-1).skip(skip).sort("uploadDate", DESCENDING)
        else:
            cursor.limit(-1).skip(version).sort("uploadDate", ASCENDING)
        try:
            doc = next(cursor)
            return GridOut(self._collection, file_document=doc, session=session)
        except StopIteration:
            raise NoFile("no version %d for filename %r" % (version, filename)) from None

    def get_last_version(
        self,
        filename: Optional[str] = None,
        session: Optional[ClientSession] = None,
        **kwargs: Any,
    ) -> GridOut:
        """Get the most recent version of a file in GridFS by ``"filename"``
        or metadata fields.

        Equivalent to calling :meth:`get_version` with the default
        `version` (``-1``).

        :param filename: ``"filename"`` of the file to get, or `None`
        :param session: a
            :class:`~pymongo.client_session.ClientSession`
        :param kwargs: find files by custom metadata.

        .. versionchanged:: 3.6
           Added ``session`` parameter.
        """
        return self.get_version(filename=filename, session=session, **kwargs)

    # TODO add optional safe mode for chunk removal?
    def delete(self, file_id: Any, session: Optional[ClientSession] = None) -> None:
        """Delete a file from GridFS by ``"_id"``.

        Deletes all data belonging to the file with ``"_id"``:
        `file_id`.

        .. warning:: Any processes/threads reading from the file while
           this method is executing will likely see an invalid/corrupt
           file. Care should be taken to avoid concurrent reads to a file
           while it is being deleted.

        .. note:: Deletes of non-existent files are considered successful
           since the end result is the same: no file with that _id remains.

        :param file_id: ``"_id"`` of the file to delete
        :param session: a
            :class:`~pymongo.client_session.ClientSession`

        .. versionchanged:: 3.6
           Added ``session`` parameter.

        .. versionchanged:: 3.1
           ``delete`` no longer ensures indexes.
        """
        _disallow_transactions(session)
        self._files.delete_one({"_id": file_id}, session=session)
        self._chunks.delete_many({"files_id": file_id}, session=session)

    def list(self, session: Optional[ClientSession] = None) -> list[str]:
        """List the names of all files stored in this instance of
        :class:`GridFS`.

        :param session: a
            :class:`~pymongo.client_session.ClientSession`

        .. versionchanged:: 3.6
           Added ``session`` parameter.

        .. versionchanged:: 3.1
           ``list`` no longer ensures indexes.
        """
        _disallow_transactions(session)
        # With an index, distinct includes documents with no filename
        # as None.
        return [
            name for name in self._files.distinct("filename", session=session) if name is not None
        ]

    def find_one(
        self,
        filter: Optional[Any] = None,
        session: Optional[ClientSession] = None,
        *args: Any,
        **kwargs: Any,
    ) -> Optional[GridOut]:
        """Get a single file from gridfs.

        All arguments to :meth:`find` are also valid arguments for
        :meth:`find_one`, although any `limit` argument will be
        ignored. Returns a single :class:`~gridfs.grid_file.GridOut`,
        or ``None`` if no matching file is found. For example:

        .. code-block: python

            file = fs.find_one({"filename": "lisa.txt"})

        :param filter: a dictionary specifying
            the query to be performing OR any other type to be used as
            the value for a query for ``"_id"`` in the file collection.
        :param args: any additional positional arguments are
            the same as the arguments to :meth:`find`.
        :param session: a
            :class:`~pymongo.client_session.ClientSession`
        :param kwargs: any additional keyword arguments
            are the same as the arguments to :meth:`find`.

        .. versionchanged:: 3.6
           Added ``session`` parameter.
        """
        if filter is not None and not isinstance(filter, abc.Mapping):
            filter = {"_id": filter}

        _disallow_transactions(session)
        for f in self.find(filter, *args, session=session, **kwargs):
            return f

        return None

    def find(self, *args: Any, **kwargs: Any) -> GridOutCursor:
        """Query GridFS for files.

        Returns a cursor that iterates across files matching
        arbitrary queries on the files collection. Can be combined
        with other modifiers for additional control. For example::

          for grid_out in fs.find({"filename": "lisa.txt"},
                                  no_cursor_timeout=True):
              data = grid_out.read()

        would iterate through all versions of "lisa.txt" stored in GridFS.
        Note that setting no_cursor_timeout to True may be important to
        prevent the cursor from timing out during long multi-file processing
        work.

        As another example, the call::

          most_recent_three = fs.find().sort("uploadDate", -1).limit(3)

        would return a cursor to the three most recently uploaded files
        in GridFS.

        Follows a similar interface to
        :meth:`~pymongo.collection.Collection.find`
        in :class:`~pymongo.collection.Collection`.

        If a :class:`~pymongo.client_session.ClientSession` is passed to
        :meth:`find`, all returned :class:`~gridfs.grid_file.GridOut` instances
        are associated with that session.

        :param filter: A query document that selects which files
            to include in the result set. Can be an empty document to include
            all files.
        :param skip: the number of files to omit (from
            the start of the result set) when returning the results
        :param limit: the maximum number of results to
            return
        :param no_cursor_timeout: if False (the default), any
            returned cursor is closed by the server after 10 minutes of
            inactivity. If set to True, the returned cursor will never
            time out on the server. Care should be taken to ensure that
            cursors with no_cursor_timeout turned on are properly closed.
        :param sort: a list of (key, direction) pairs
            specifying the sort order for this query. See
            :meth:`~pymongo.cursor.Cursor.sort` for details.

        Raises :class:`TypeError` if any of the arguments are of
        improper type. Returns an instance of
        :class:`~gridfs.grid_file.GridOutCursor`
        corresponding to this query.

        .. versionchanged:: 3.0
           Removed the read_preference, tag_sets, and
           secondary_acceptable_latency_ms options.
        .. versionadded:: 2.7
        .. seealso:: The MongoDB documentation on `find <https://dochub.mongodb.org/core/find>`_.
        """
        return GridOutCursor(self._collection, *args, **kwargs)

    def exists(
        self,
        document_or_id: Optional[Any] = None,
        session: Optional[ClientSession] = None,
        **kwargs: Any,
    ) -> bool:
        """Check if a file exists in this instance of :class:`GridFS`.

        The file to check for can be specified by the value of its
        ``_id`` key, or by passing in a query document. A query
        document can be passed in as dictionary, or by using keyword
        arguments. Thus, the following three calls are equivalent:

        >>> fs.exists(file_id)
        >>> fs.exists({"_id": file_id})
        >>> fs.exists(_id=file_id)

        As are the following two calls:

        >>> fs.exists({"filename": "mike.txt"})
        >>> fs.exists(filename="mike.txt")

        And the following two:

        >>> fs.exists({"foo": {"$gt": 12}})
        >>> fs.exists(foo={"$gt": 12})

        Returns ``True`` if a matching file exists, ``False``
        otherwise. Calls to :meth:`exists` will not automatically
        create appropriate indexes; application developers should be
        sure to create indexes if needed and as appropriate.

        :param document_or_id: query document, or _id of the
            document to check for
        :param session: a
            :class:`~pymongo.client_session.ClientSession`
        :param kwargs: keyword arguments are used as a
            query document, if they're present.

        .. versionchanged:: 3.6
           Added ``session`` parameter.
        """
        _disallow_transactions(session)
        if kwargs:
            f = self._files.find_one(kwargs, ["_id"], session=session)
        else:
            f = self._files.find_one(document_or_id, ["_id"], session=session)

        return f is not None


class GridFSBucket:
    """An instance of GridFS on top of a single Database."""

    def __init__(
        self,
        db: Database,
        bucket_name: str = "fs",
        chunk_size_bytes: int = DEFAULT_CHUNK_SIZE,
        write_concern: Optional[WriteConcern] = None,
        read_preference: Optional[_ServerMode] = None,
    ) -> None:
        """Create a new instance of :class:`GridFSBucket`.

        Raises :exc:`TypeError` if `database` is not an instance of
        :class:`~pymongo.database.Database`.

        Raises :exc:`~pymongo.errors.ConfigurationError` if `write_concern`
        is not acknowledged.

        :param database: database to use.
        :param bucket_name: The name of the bucket. Defaults to 'fs'.
        :param chunk_size_bytes: The chunk size in bytes. Defaults
            to 255KB.
        :param write_concern: The
            :class:`~pymongo.write_concern.WriteConcern` to use. If ``None``
            (the default) db.write_concern is used.
        :param read_preference: The read preference to use. If
            ``None`` (the default) db.read_preference is used.

        .. versionchanged:: 4.0
           Removed the `disable_md5` parameter. See
           :ref:`removed-gridfs-checksum` for details.

        .. versionchanged:: 3.11
           Running a GridFSBucket operation in a transaction now always raises
           an error. GridFSBucket does not support multi-document transactions.

        .. versionchanged:: 3.7
           Added the `disable_md5` parameter.

        .. versionadded:: 3.1

        .. seealso:: The MongoDB documentation on `gridfs <https://dochub.mongodb.org/core/gridfs>`_.
        """
        if not isinstance(db, Database):
            raise TypeError(f"database must be an instance of Database, not {type(db)}")

        db = _clear_entity_type_registry(db)

        wtc = write_concern if write_concern is not None else db.write_concern
        if not wtc.acknowledged:
            raise ConfigurationError("write concern must be acknowledged")

        self._bucket_name = bucket_name
        self._collection = db[bucket_name]
        self._chunks: Collection = self._collection.chunks.with_options(
            write_concern=write_concern, read_preference=read_preference
        )

        self._files: Collection = self._collection.files.with_options(
            write_concern=write_concern, read_preference=read_preference
        )

        self._chunk_size_bytes = chunk_size_bytes
        self._timeout = db.client.options.timeout

    def open_upload_stream(
        self,
        filename: str,
        chunk_size_bytes: Optional[int] = None,
        metadata: Optional[Mapping[str, Any]] = None,
        session: Optional[ClientSession] = None,
    ) -> GridIn:
        """Opens a Stream that the application can write the contents of the
        file to.

        The user must specify the filename, and can choose to add any
        additional information in the metadata field of the file document or
        modify the chunk size.
        For example::

          my_db = MongoClient().test
          fs = GridFSBucket(my_db)
          with fs.open_upload_stream(
                "test_file", chunk_size_bytes=4,
                metadata={"contentType": "text/plain"}) as grid_in:
              grid_in.write("data I want to store!")
          # uploaded on close

        Returns an instance of :class:`~gridfs.grid_file.GridIn`.

        Raises :exc:`~gridfs.errors.NoFile` if no such version of
        that file exists.
        Raises :exc:`~ValueError` if `filename` is not a string.

        :param filename: The name of the file to upload.
        :param chunk_size_bytes` (options): The number of bytes per chunk of this
            file. Defaults to the chunk_size_bytes in :class:`GridFSBucket`.
        :param metadata: User data for the 'metadata' field of the
            files collection document. If not provided the metadata field will
            be omitted from the files collection document.
        :param session: a
            :class:`~pymongo.client_session.ClientSession`

        .. versionchanged:: 3.6
           Added ``session`` parameter.
        """
        validate_string("filename", filename)

        opts = {
            "filename": filename,
            "chunk_size": (
                chunk_size_bytes if chunk_size_bytes is not None else self._chunk_size_bytes
            ),
        }
        if metadata is not None:
            opts["metadata"] = metadata

        return GridIn(self._collection, session=session, **opts)

    def open_upload_stream_with_id(
        self,
        file_id: Any,
        filename: str,
        chunk_size_bytes: Optional[int] = None,
        metadata: Optional[Mapping[str, Any]] = None,
        session: Optional[ClientSession] = None,
    ) -> GridIn:
        """Opens a Stream that the application can write the contents of the
        file to.

        The user must specify the file id and filename, and can choose to add
        any additional information in the metadata field of the file document
        or modify the chunk size.
        For example::

          my_db = MongoClient().test
          fs = GridFSBucket(my_db)
          with fs.open_upload_stream_with_id(
                ObjectId(),
                "test_file",
                chunk_size_bytes=4,
                metadata={"contentType": "text/plain"}) as grid_in:
              grid_in.write("data I want to store!")
          # uploaded on close

        Returns an instance of :class:`~gridfs.grid_file.GridIn`.

        Raises :exc:`~gridfs.errors.NoFile` if no such version of
        that file exists.
        Raises :exc:`~ValueError` if `filename` is not a string.

        :param file_id: The id to use for this file. The id must not have
            already been used for another file.
        :param filename: The name of the file to upload.
        :param chunk_size_bytes` (options): The number of bytes per chunk of this
            file. Defaults to the chunk_size_bytes in :class:`GridFSBucket`.
        :param metadata: User data for the 'metadata' field of the
            files collection document. If not provided the metadata field will
            be omitted from the files collection document.
        :param session: a
            :class:`~pymongo.client_session.ClientSession`

        .. versionchanged:: 3.6
           Added ``session`` parameter.
        """
        validate_string("filename", filename)

        opts = {
            "_id": file_id,
            "filename": filename,
            "chunk_size": (
                chunk_size_bytes if chunk_size_bytes is not None else self._chunk_size_bytes
            ),
        }
        if metadata is not None:
            opts["metadata"] = metadata

        return GridIn(self._collection, session=session, **opts)

    @_csot.apply
    def upload_from_stream(
        self,
        filename: str,
        source: Any,
        chunk_size_bytes: Optional[int] = None,
        metadata: Optional[Mapping[str, Any]] = None,
        session: Optional[ClientSession] = None,
    ) -> ObjectId:
        """Uploads a user file to a GridFS bucket.

        Reads the contents of the user file from `source` and uploads
        it to the file `filename`. Source can be a string or file-like object.
        For example::

          my_db = MongoClient().test
          fs = GridFSBucket(my_db)
          file_id = fs.upload_from_stream(
              "test_file",
              "data I want to store!",
              chunk_size_bytes=4,
              metadata={"contentType": "text/plain"})

        Returns the _id of the uploaded file.

        Raises :exc:`~gridfs.errors.NoFile` if no such version of
        that file exists.
        Raises :exc:`~ValueError` if `filename` is not a string.

        :param filename: The name of the file to upload.
        :param source: The source stream of the content to be uploaded. Must be
            a file-like object that implements :meth:`read` or a string.
        :param chunk_size_bytes` (options): The number of bytes per chunk of this
            file. Defaults to the chunk_size_bytes of :class:`GridFSBucket`.
        :param metadata: User data for the 'metadata' field of the
            files collection document. If not provided the metadata field will
            be omitted from the files collection document.
        :param session: a
            :class:`~pymongo.client_session.ClientSession`

        .. versionchanged:: 3.6
           Added ``session`` parameter.
        """
        with self.open_upload_stream(filename, chunk_size_bytes, metadata, session=session) as gin:
            gin.write(source)

        return cast(ObjectId, gin._id)

    @_csot.apply
    def upload_from_stream_with_id(
        self,
        file_id: Any,
        filename: str,
        source: Any,
        chunk_size_bytes: Optional[int] = None,
        metadata: Optional[Mapping[str, Any]] = None,
        session: Optional[ClientSession] = None,
    ) -> None:
        """Uploads a user file to a GridFS bucket with a custom file id.

        Reads the contents of the user file from `source` and uploads
        it to the file `filename`. Source can be a string or file-like object.
        For example::

          my_db = MongoClient().test
          fs = GridFSBucket(my_db)
          file_id = fs.upload_from_stream(
              ObjectId(),
              "test_file",
              "data I want to store!",
              chunk_size_bytes=4,
              metadata={"contentType": "text/plain"})

        Raises :exc:`~gridfs.errors.NoFile` if no such version of
        that file exists.
        Raises :exc:`~ValueError` if `filename` is not a string.

        :param file_id: The id to use for this file. The id must not have
            already been used for another file.
        :param filename: The name of the file to upload.
        :param source: The source stream of the content to be uploaded. Must be
            a file-like object that implements :meth:`read` or a string.
        :param chunk_size_bytes` (options): The number of bytes per chunk of this
            file. Defaults to the chunk_size_bytes of :class:`GridFSBucket`.
        :param metadata: User data for the 'metadata' field of the
            files collection document. If not provided the metadata field will
            be omitted from the files collection document.
        :param session: a
            :class:`~pymongo.client_session.ClientSession`

        .. versionchanged:: 3.6
           Added ``session`` parameter.
        """
        with self.open_upload_stream_with_id(
            file_id, filename, chunk_size_bytes, metadata, session=session
        ) as gin:
            gin.write(source)

    def open_download_stream(
        self, file_id: Any, session: Optional[ClientSession] = None
    ) -> GridOut:
        """Opens a Stream from which the application can read the contents of
        the stored file specified by file_id.

        For example::

          my_db = MongoClient().test
          fs = GridFSBucket(my_db)
          # get _id of file to read.
          file_id = fs.upload_from_stream("test_file", "data I want to store!")
          grid_out = fs.open_download_stream(file_id)
          contents = grid_out.read()

        Returns an instance of :class:`~gridfs.grid_file.GridOut`.

        Raises :exc:`~gridfs.errors.NoFile` if no file with file_id exists.

        :param file_id: The _id of the file to be downloaded.
        :param session: a
            :class:`~pymongo.client_session.ClientSession`

        .. versionchanged:: 3.6
           Added ``session`` parameter.
        """
        gout = GridOut(self._collection, file_id, session=session)

        # Raise NoFile now, instead of on first attribute access.
        gout.open()
        return gout

    @_csot.apply
    def download_to_stream(
        self, file_id: Any, destination: Any, session: Optional[ClientSession] = None
    ) -> None:
        """Downloads the contents of the stored file specified by file_id and
        writes the contents to `destination`.

        For example::

          my_db = MongoClient().test
          fs = GridFSBucket(my_db)
          # Get _id of file to read
          file_id = fs.upload_from_stream("test_file", "data I want to store!")
          # Get file to write to
          file = open('myfile','wb+')
          fs.download_to_stream(file_id, file)
          file.seek(0)
          contents = file.read()

        Raises :exc:`~gridfs.errors.NoFile` if no file with file_id exists.

        :param file_id: The _id of the file to be downloaded.
        :param destination: a file-like object implementing :meth:`write`.
        :param session: a
            :class:`~pymongo.client_session.ClientSession`

        .. versionchanged:: 3.6
           Added ``session`` parameter.
        """
        with self.open_download_stream(file_id, session=session) as gout:
            while True:
                chunk = gout.readchunk()
                if not len(chunk):
                    break
                destination.write(chunk)

    @_csot.apply
    def delete(self, file_id: Any, session: Optional[ClientSession] = None) -> None:
        """Given an file_id, delete this stored file's files collection document
        and associated chunks from a GridFS bucket.

        For example::

          my_db = MongoClient().test
          fs = GridFSBucket(my_db)
          # Get _id of file to delete
          file_id = fs.upload_from_stream("test_file", "data I want to store!")
          fs.delete(file_id)

        Raises :exc:`~gridfs.errors.NoFile` if no file with file_id exists.

        :param file_id: The _id of the file to be deleted.
        :param session: a
            :class:`~pymongo.client_session.ClientSession`

        .. versionchanged:: 3.6
           Added ``session`` parameter.
        """
        _disallow_transactions(session)
        res = self._files.delete_one({"_id": file_id}, session=session)
        self._chunks.delete_many({"files_id": file_id}, session=session)
        if not res.deleted_count:
            raise NoFile("no file could be deleted because none matched %s" % file_id)

    @_csot.apply
    def delete_by_name(self, filename: str, session: Optional[ClientSession] = None) -> None:
        """Given a filename, delete this stored file's files collection document(s)
        and associated chunks from a GridFS bucket.

        For example::

          my_db = MongoClient().test
          fs = GridFSBucket(my_db)
          fs.upload_from_stream("test_file", "data I want to store!")
          fs.delete_by_name("test_file")

        Raises :exc:`~gridfs.errors.NoFile` if no file with the given filename exists.

        :param filename: The name of the file to be deleted.
        :param session: a :class:`~pymongo.client_session.ClientSession`

        .. versionadded:: 4.12
        """
        _disallow_transactions(session)
        files = self._files.find({"filename": filename}, {"_id": 1}, session=session)
        file_ids = [file["_id"] for file in files]
        res = self._files.delete_many({"_id": {"$in": file_ids}}, session=session)
        self._chunks.delete_many({"files_id": {"$in": file_ids}}, session=session)
        if not res.deleted_count:
            raise NoFile(f"no file could be deleted because none matched filename {filename!r}")

    def find(self, *args: Any, **kwargs: Any) -> GridOutCursor:
        """Find and return the files collection documents that match ``filter``

        Returns a cursor that iterates across files matching
        arbitrary queries on the files collection. Can be combined
        with other modifiers for additional control.

        For example::

          for grid_data in fs.find({"filename": "lisa.txt"},
                                  no_cursor_timeout=True):
              data = grid_data.read()

        would iterate through all versions of "lisa.txt" stored in GridFS.
        Note that setting no_cursor_timeout to True may be important to
        prevent the cursor from timing out during long multi-file processing
        work.

        As another example, the call::

          most_recent_three = fs.find().sort("uploadDate", -1).limit(3)

        would return a cursor to the three most recently uploaded files
        in GridFS.

        Follows a similar interface to
        :meth:`~pymongo.collection.Collection.find`
        in :class:`~pymongo.collection.Collection`.

        If a :class:`~pymongo.client_session.ClientSession` is passed to
        :meth:`find`, all returned :class:`~gridfs.grid_file.GridOut` instances
        are associated with that session.

        :param filter: Search query.
        :param batch_size: The number of documents to return per
            batch.
        :param limit: The maximum number of documents to return.
        :param no_cursor_timeout: The server normally times out idle
            cursors after an inactivity period (10 minutes) to prevent excess
            memory use. Set this option to True prevent that.
        :param skip: The number of documents to skip before
            returning.
        :param sort: The order by which to sort results. Defaults to
            None.
        """
        return GridOutCursor(self._collection, *args, **kwargs)

    def open_download_stream_by_name(
        self, filename: str, revision: int = -1, session: Optional[ClientSession] = None
    ) -> GridOut:
        """Opens a Stream from which the application can read the contents of
        `filename` and optional `revision`.

        For example::

          my_db = MongoClient().test
          fs = GridFSBucket(my_db)
          grid_out = fs.open_download_stream_by_name("test_file")
          contents = grid_out.read()

        Returns an instance of :class:`~gridfs.grid_file.GridOut`.

        Raises :exc:`~gridfs.errors.NoFile` if no such version of
        that file exists.

        Raises :exc:`~ValueError` filename is not a string.

        :param filename: The name of the file to read from.
        :param revision: Which revision (documents with the same
            filename and different uploadDate) of the file to retrieve.
            Defaults to -1 (the most recent revision).
        :param session: a
            :class:`~pymongo.client_session.ClientSession`

        :Note: Revision numbers are defined as follows:

          - 0 = the original stored file
          - 1 = the first revision
          - 2 = the second revision
          - etc...
          - -2 = the second most recent revision
          - -1 = the most recent revision

        .. versionchanged:: 3.6
           Added ``session`` parameter.
        """
        validate_string("filename", filename)
        query = {"filename": filename}
        _disallow_transactions(session)
        cursor = self._files.find(query, session=session)
        if revision < 0:
            skip = abs(revision) - 1
            cursor.limit(-1).skip(skip).sort("uploadDate", DESCENDING)
        else:
            cursor.limit(-1).skip(revision).sort("uploadDate", ASCENDING)
        try:
            grid_file = next(cursor)
            return GridOut(self._collection, file_document=grid_file, session=session)
        except StopIteration:
            raise NoFile("no version %d for filename %r" % (revision, filename)) from None

    @_csot.apply
    def download_to_stream_by_name(
        self,
        filename: str,
        destination: Any,
        revision: int = -1,
        session: Optional[ClientSession] = None,
    ) -> None:
        """Write the contents of `filename` (with optional `revision`) to
        `destination`.

        For example::

          my_db = MongoClient().test
          fs = GridFSBucket(my_db)
          # Get file to write to
          file = open('myfile','wb')
          fs.download_to_stream_by_name("test_file", file)

        Raises :exc:`~gridfs.errors.NoFile` if no such version of
        that file exists.

        Raises :exc:`~ValueError` if `filename` is not a string.

        :param filename: The name of the file to read from.
        :param destination: A file-like object that implements :meth:`write`.
        :param revision: Which revision (documents with the same
            filename and different uploadDate) of the file to retrieve.
            Defaults to -1 (the most recent revision).
        :param session: a
            :class:`~pymongo.client_session.ClientSession`

        :Note: Revision numbers are defined as follows:

          - 0 = the original stored file
          - 1 = the first revision
          - 2 = the second revision
          - etc...
          - -2 = the second most recent revision
          - -1 = the most recent revision

        .. versionchanged:: 3.6
           Added ``session`` parameter.
        """
        with self.open_download_stream_by_name(filename, revision, session=session) as gout:
            while True:
                chunk = gout.readchunk()
                if not len(chunk):
                    break
                destination.write(chunk)

    def rename(
        self, file_id: Any, new_filename: str, session: Optional[ClientSession] = None
    ) -> None:
        """Renames the stored file with the specified file_id.

        For example::

          my_db = MongoClient().test
          fs = GridFSBucket(my_db)
          # Get _id of file to rename
          file_id = fs.upload_from_stream("test_file", "data I want to store!")
          fs.rename(file_id, "new_test_name")

        Raises :exc:`~gridfs.errors.NoFile` if no file with file_id exists.

        :param file_id: The _id of the file to be renamed.
        :param new_filename: The new name of the file.
        :param session: a
            :class:`~pymongo.client_session.ClientSession`

        .. versionchanged:: 3.6
           Added ``session`` parameter.
        """
        _disallow_transactions(session)
        result = self._files.update_one(
            {"_id": file_id}, {"$set": {"filename": new_filename}}, session=session
        )
        if not result.matched_count:
            raise NoFile(
                "no files could be renamed %r because none "
                "matched file_id %i" % (new_filename, file_id)
            )

    def rename_by_name(
        self, filename: str, new_filename: str, session: Optional[ClientSession] = None
    ) -> None:
        """Renames the stored file with the specified filename.

        For example::

          my_db = MongoClient().test
          fs = GridFSBucket(my_db)
          fs.upload_from_stream("test_file", "data I want to store!")
          fs.rename_by_name("test_file", "new_test_name")

        Raises :exc:`~gridfs.errors.NoFile` if no file with the given filename exists.

        :param filename: The filename of the file to be renamed.
        :param new_filename: The new name of the file.
        :param session: a :class:`~pymongo.client_session.ClientSession`

        .. versionadded:: 4.12
        """
        _disallow_transactions(session)
        result = self._files.update_many(
            {"filename": filename}, {"$set": {"filename": new_filename}}, session=session
        )
        if not result.matched_count:
            raise NoFile(
                f"no files could be renamed {new_filename!r} because none matched filename {filename!r}"
            )


class GridIn:
    """Class to write data to GridFS."""

    def __init__(
        self,
        root_collection: Collection,
        session: Optional[ClientSession] = None,
        **kwargs: Any,
    ) -> None:
        """Write a file to GridFS

        Application developers should generally not need to
        instantiate this class directly - instead see the methods
        provided by :class:`~gridfs.GridFS`.

        Raises :class:`TypeError` if `root_collection` is not an
        instance of :class:`~pymongo.collection.Collection`.

        Any of the file level options specified in the `GridFS Spec
        <http://dochub.mongodb.org/core/gridfsspec>`_ may be passed as
        keyword arguments. Any additional keyword arguments will be
        set as additional fields on the file document. Valid keyword
        arguments include:

          - ``"_id"``: unique ID for this file (default:
            :class:`~bson.objectid.ObjectId`) - this ``"_id"`` must
            not have already been used for another file

          - ``"filename"``: human name for the file

          - ``"contentType"`` or ``"content_type"``: valid mime-type
            for the file

          - ``"chunkSize"`` or ``"chunk_size"``: size of each of the
            chunks, in bytes (default: 255 kb)

          - ``"encoding"``: encoding used for this file. Any :class:`str`
            that is written to the file will be converted to :class:`bytes`.

        :param root_collection: root collection to write to
        :param session: a
            :class:`~pymongo.client_session.ClientSession` to use for all
            commands
        :param kwargs: Any: file level options (see above)

        .. versionchanged:: 4.0
           Removed the `disable_md5` parameter. See
           :ref:`removed-gridfs-checksum` for details.

        .. versionchanged:: 3.7
           Added the `disable_md5` parameter.

        .. versionchanged:: 3.6
           Added ``session`` parameter.

        .. versionchanged:: 3.0
           `root_collection` must use an acknowledged
           :attr:`~pymongo.collection.Collection.write_concern`
        """
        if not isinstance(root_collection, Collection):
            raise TypeError(
                f"root_collection must be an instance of Collection, not {type(root_collection)}"
            )

        if not root_collection.write_concern.acknowledged:
            raise ConfigurationError("root_collection must use acknowledged write_concern")
        _disallow_transactions(session)

        # Handle alternative naming
        if "content_type" in kwargs:
            kwargs["contentType"] = kwargs.pop("content_type")
        if "chunk_size" in kwargs:
            kwargs["chunkSize"] = kwargs.pop("chunk_size")

        coll = _clear_entity_type_registry(root_collection, read_preference=ReadPreference.PRIMARY)

        # Defaults
        kwargs["_id"] = kwargs.get("_id", ObjectId())
        kwargs["chunkSize"] = kwargs.get("chunkSize", DEFAULT_CHUNK_SIZE)
        object.__setattr__(self, "_session", session)
        object.__setattr__(self, "_coll", coll)
        object.__setattr__(self, "_chunks", coll.chunks)
        object.__setattr__(self, "_file", kwargs)
        object.__setattr__(self, "_buffer", io.BytesIO())
        object.__setattr__(self, "_position", 0)
        object.__setattr__(self, "_chunk_number", 0)
        object.__setattr__(self, "_closed", False)
        object.__setattr__(self, "_ensured_index", False)
        object.__setattr__(self, "_buffered_docs", [])
        object.__setattr__(self, "_buffered_docs_size", 0)

    def _create_index(self, collection: Collection, index_key: Any, unique: bool) -> None:
        doc = collection.find_one(projection={"_id": 1}, session=self._session)
        if doc is None:
            try:
                index_keys = [
                    index_spec["key"]
                    for index_spec in collection.list_indexes(session=self._session)
                ]
            except OperationFailure:
                index_keys = []
            if index_key not in index_keys:
                collection.create_index(index_key.items(), unique=unique, session=self._session)

    def _ensure_indexes(self) -> None:
        if not object.__getattribute__(self, "_ensured_index"):
            _disallow_transactions(self._session)
            self._create_index(self._coll.files, _F_INDEX, False)
            self._create_index(self._coll.chunks, _C_INDEX, True)
            object.__setattr__(self, "_ensured_index", True)

    def abort(self) -> None:
        """Remove all chunks/files that may have been uploaded and close."""
        self._coll.chunks.delete_many({"files_id": self._file["_id"]}, session=self._session)
        self._coll.files.delete_one({"_id": self._file["_id"]}, session=self._session)
        object.__setattr__(self, "_closed", True)

    @property
    def closed(self) -> bool:
        """Is this file closed?"""
        return self._closed

    _id: Any = _grid_in_property("_id", "The ``'_id'`` value for this file.", read_only=True)
    filename: Optional[str] = _grid_in_property("filename", "Name of this file.")
    name: Optional[str] = _grid_in_property("filename", "Alias for `filename`.")
    content_type: Optional[str] = _grid_in_property(
        "contentType", "DEPRECATED, will be removed in PyMongo 5.0. Mime-type for this file."
    )
    length: int = _grid_in_property("length", "Length (in bytes) of this file.", closed_only=True)
    chunk_size: int = _grid_in_property("chunkSize", "Chunk size for this file.", read_only=True)
    upload_date: datetime.datetime = _grid_in_property(
        "uploadDate", "Date that this file was uploaded.", closed_only=True
    )
    md5: Optional[str] = _grid_in_property(
        "md5",
        "DEPRECATED, will be removed in PyMongo 5.0. MD5 of the contents of this file if an md5 sum was created.",
        closed_only=True,
    )

    _buffer: io.BytesIO
    _closed: bool
    _buffered_docs: list[dict[str, Any]]
    _buffered_docs_size: int

    def __getattr__(self, name: str) -> Any:
        if name == "_coll":
            return object.__getattribute__(self, name)
        elif name in self._file:
            return self._file[name]
        raise AttributeError("GridIn object has no attribute '%s'" % name)

    def __setattr__(self, name: str, value: Any) -> None:
        # For properties of this instance like _buffer, or descriptors set on
        # the class like filename, use regular __setattr__
        if name in self.__dict__ or name in self.__class__.__dict__:
            object.__setattr__(self, name, value)
        else:
            # All other attributes are part of the document in db.fs.files.
            # Store them to be sent to server on close() or if closed, send
            # them now.
            self._file[name] = value
            if self._closed:
                if _IS_SYNC:
                    self._coll.files.update_one({"_id": self._file["_id"]}, {"$set": {name: value}})
                else:
                    raise AttributeError(
                        "GridIn does not support __setattr__ after being closed(). Set the attribute before closing the file or use GridIn.set() instead"
                    )

    def set(self, name: str, value: Any) -> None:
        self._file[name] = value
        if self._closed:
            self._coll.files.update_one({"_id": self._file["_id"]}, {"$set": {name: value}})

    def _flush_data(self, data: Any, force: bool = False) -> None:
        """Flush `data` to a chunk."""
        self._ensure_indexes()
        assert len(data) <= self.chunk_size
        if data:
            self._buffered_docs.append(
                {"files_id": self._file["_id"], "n": self._chunk_number, "data": data}
            )
            self._buffered_docs_size += len(data) + _CHUNK_OVERHEAD
        if not self._buffered_docs:
            return
        # Limit to 100,000 chunks or 32MB (+1 chunk) of data.
        if (
            force
            or self._buffered_docs_size >= _UPLOAD_BUFFER_SIZE
            or len(self._buffered_docs) >= _UPLOAD_BUFFER_CHUNKS
        ):
            try:
                self._chunks.insert_many(self._buffered_docs, session=self._session)
            except BulkWriteError as exc:
                # For backwards compatibility, raise an insert_one style exception.
                write_errors = exc.details["writeErrors"]
                for err in write_errors:
                    if err.get("code") in (11000, 11001, 12582):  # Duplicate key errors
                        self._raise_file_exists(self._file["_id"])
                result = {"writeErrors": write_errors}
                wces = exc.details["writeConcernErrors"]
                if wces:
                    result["writeConcernError"] = wces[-1]
                _check_write_command_response(result)
                raise
            self._buffered_docs = []
            self._buffered_docs_size = 0
        self._chunk_number += 1
        self._position += len(data)

    def _flush_buffer(self, force: bool = False) -> None:
        """Flush the buffer contents out to a chunk."""
        self._flush_data(self._buffer.getvalue(), force=force)
        self._buffer.close()
        self._buffer = io.BytesIO()

    def _flush(self) -> Any:
        """Flush the file to the database."""
        try:
            self._flush_buffer(force=True)
            # The GridFS spec says length SHOULD be an Int64.
            self._file["length"] = Int64(self._position)
            self._file["uploadDate"] = datetime.datetime.now(tz=datetime.timezone.utc)

            return self._coll.files.insert_one(self._file, session=self._session)
        except DuplicateKeyError:
            self._raise_file_exists(self._id)

    def _raise_file_exists(self, file_id: Any) -> NoReturn:
        """Raise a FileExists exception for the given file_id."""
        raise FileExists("file with _id %r already exists" % file_id)

    def close(self) -> None:
        """Flush the file and close it.

        A closed file cannot be written any more. Calling
        :meth:`close` more than once is allowed.
        """
        if not self._closed:
            self._flush()
            object.__setattr__(self, "_closed", True)

    def read(self, size: int = -1) -> NoReturn:
        raise io.UnsupportedOperation("read")

    def readable(self) -> bool:
        return False

    def seekable(self) -> bool:
        return False

    def write(self, data: Any) -> None:
        """Write data to the file. There is no return value.

        `data` can be either a string of bytes or a file-like object
        (implementing :meth:`read`). If the file has an
        :attr:`encoding` attribute, `data` can also be a
        :class:`str` instance, which will be encoded as
        :attr:`encoding` before being written.

        Due to buffering, the data may not actually be written to the
        database until the :meth:`close` method is called. Raises
        :class:`ValueError` if this file is already closed. Raises
        :class:`TypeError` if `data` is not an instance of
        :class:`bytes`, a file-like object, or an instance of :class:`str`.
        Unicode data is only allowed if the file has an :attr:`encoding`
        attribute.

        :param data: string of bytes or file-like object to be written
            to the file
        """
        if self._closed:
            raise ValueError("cannot write to a closed file")

        try:
            # file-like
            read = data.read
        except AttributeError:
            # string
            if not isinstance(data, (str, bytes)):
                raise TypeError("can only write strings or file-like objects") from None
            if isinstance(data, str):
                try:
                    data = data.encode(self.encoding)
                except AttributeError:
                    raise TypeError(
                        "must specify an encoding for file in order to write str"
                    ) from None
            read = io.BytesIO(data).read

        if inspect.iscoroutinefunction(read):
            self._write_async(read)
        else:
            if self._buffer.tell() > 0:
                # Make sure to flush only when _buffer is complete
                space = self.chunk_size - self._buffer.tell()
                if space:
                    try:
                        to_write = read(space)
                    except BaseException:
                        self.abort()
                        raise
                    self._buffer.write(to_write)
                    if len(to_write) < space:
                        return  # EOF or incomplete
                self._flush_buffer()
            to_write = read(self.chunk_size)
            while to_write and len(to_write) == self.chunk_size:
                self._flush_data(to_write)
                to_write = read(self.chunk_size)
            self._buffer.write(to_write)

    def _write_async(self, read: Any) -> None:
        if self._buffer.tell() > 0:
            # Make sure to flush only when _buffer is complete
            space = self.chunk_size - self._buffer.tell()
            if space:
                try:
                    to_write = read(space)
                except BaseException:
                    self.abort()
                    raise
                self._buffer.write(to_write)
                if len(to_write) < space:
                    return  # EOF or incomplete
            self._flush_buffer()
        to_write = read(self.chunk_size)
        while to_write and len(to_write) == self.chunk_size:
            self._flush_data(to_write)
            to_write = read(self.chunk_size)
        self._buffer.write(to_write)

    def writelines(self, sequence: Iterable[Any]) -> None:
        """Write a sequence of strings to the file.

        Does not add separators.
        """
        for line in sequence:
            self.write(line)

    def writeable(self) -> bool:
        return True

    def __enter__(self) -> GridIn:
        """Support for the context manager protocol."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> Any:
        """Support for the context manager protocol.

        Close the file if no exceptions occur and allow exceptions to propagate.
        """
        if exc_type is None:
            # No exceptions happened.
            self.close()
        else:
            # Something happened, at minimum mark as closed.
            object.__setattr__(self, "_closed", True)

        # propagate exceptions
        return False


GRIDOUT_BASE_CLASS = io.IOBase if _IS_SYNC else object  # type: Any


class GridOut(GRIDOUT_BASE_CLASS):  # type: ignore

    """Class to read data out of GridFS."""

    def __init__(
        self,
        root_collection: Collection,
        file_id: Optional[int] = None,
        file_document: Optional[Any] = None,
        session: Optional[ClientSession] = None,
    ) -> None:
        """Read a file from GridFS

        Application developers should generally not need to
        instantiate this class directly - instead see the methods
        provided by :class:`~gridfs.GridFS`.

        Either `file_id` or `file_document` must be specified,
        `file_document` will be given priority if present. Raises
        :class:`TypeError` if `root_collection` is not an instance of
        :class:`~pymongo.collection.Collection`.

        :param root_collection: root collection to read from
        :param file_id: value of ``"_id"`` for the file to read
        :param file_document: file document from
            `root_collection.files`
        :param session: a
            :class:`~pymongo.client_session.ClientSession` to use for all
            commands

        .. versionchanged:: 3.8
           For better performance and to better follow the GridFS spec,
           :class:`GridOut` now uses a single cursor to read all the chunks in
           the file.

        .. versionchanged:: 3.6
           Added ``session`` parameter.

        .. versionchanged:: 3.0
           Creating a GridOut does not immediately retrieve the file metadata
           from the server. Metadata is fetched when first needed.
        """
        if not isinstance(root_collection, Collection):
            raise TypeError(
                f"root_collection must be an instance of Collection, not {type(root_collection)}"
            )
        _disallow_transactions(session)

        root_collection = _clear_entity_type_registry(root_collection)

        super().__init__()

        self._chunks = root_collection.chunks
        self._files = root_collection.files
        self._file_id = file_id
        self._buffer = EMPTY
        # Start position within the current buffered chunk.
        self._buffer_pos = 0
        self._chunk_iter = None
        # Position within the total file.
        self._position = 0
        self._file = file_document
        self._session = session
        if not _IS_SYNC:
            self.closed = False

    _id: Any = _grid_out_property("_id", "The ``'_id'`` value for this file.")
    filename: str = _grid_out_property("filename", "Name of this file.")
    name: str = _grid_out_property("filename", "Alias for `filename`.")
    content_type: Optional[str] = _grid_out_property(
        "contentType", "DEPRECATED, will be removed in PyMongo 5.0. Mime-type for this file."
    )
    length: int = _grid_out_property("length", "Length (in bytes) of this file.")
    chunk_size: int = _grid_out_property("chunkSize", "Chunk size for this file.")
    upload_date: datetime.datetime = _grid_out_property(
        "uploadDate", "Date that this file was first uploaded."
    )
    aliases: Optional[list[str]] = _grid_out_property(
        "aliases", "DEPRECATED, will be removed in PyMongo 5.0. List of aliases for this file."
    )
    metadata: Optional[Mapping[str, Any]] = _grid_out_property(
        "metadata", "Metadata attached to this file."
    )
    md5: Optional[str] = _grid_out_property(
        "md5",
        "DEPRECATED, will be removed in PyMongo 5.0. MD5 of the contents of this file if an md5 sum was created.",
    )

    _file: Any
    _chunk_iter: Any

    if not _IS_SYNC:
        closed: bool

        def __next__(self) -> bytes:
            line = self.readline()
            if line:
                return line
            raise StopIteration()

        def to_list(self) -> list[bytes]:
            return [x for x in self]  # noqa: C416, RUF100

        def readline(self, size: int = -1) -> bytes:
            """Read one line or up to `size` bytes from the file.

            :param size: the maximum number of bytes to read
            """
            return self._read_size_or_line(size=size, line=True)

        def readlines(self, size: int = -1) -> list[bytes]:
            """Read one line or up to `size` bytes from the file.

            :param size: the maximum number of bytes to read
            """
            self.open()
            lines = []
            remainder = int(self.length) - self._position
            bytes_read = 0
            while remainder > 0:
                line = self._read_size_or_line(line=True)
                bytes_read += len(line)
                lines.append(line)
                remainder = int(self.length) - self._position
                if 0 < size < bytes_read:
                    break

            return lines

    def open(self) -> None:
        if not self._file:
            _disallow_transactions(self._session)
            self._file = self._files.find_one({"_id": self._file_id}, session=self._session)
            if not self._file:
                raise NoFile(
                    f"no file in gridfs collection {self._files!r} with _id {self._file_id!r}"
                )

    def __getattr__(self, name: str) -> Any:
        if _IS_SYNC:
            self.open()  # type: ignore[unused-coroutine]
        elif not self._file:
            raise InvalidOperation(
                "You must call GridOut.open() before accessing the %s property" % name
            )
        if name in self._file:
            return self._file[name]
        raise AttributeError("GridOut object has no attribute '%s'" % name)

    def readable(self) -> bool:
        return True

    def readchunk(self) -> bytes:
        """Reads a chunk at a time. If the current position is within a
        chunk the remainder of the chunk is returned.
        """
        self.open()
        received = len(self._buffer) - self._buffer_pos
        chunk_data = EMPTY
        chunk_size = int(self.chunk_size)

        if received > 0:
            chunk_data = self._buffer[self._buffer_pos :]
        elif self._position < int(self.length):
            chunk_number = int((received + self._position) / chunk_size)
            if self._chunk_iter is None:
                self._chunk_iter = GridOutChunkIterator(
                    self, self._chunks, self._session, chunk_number
                )

            chunk = self._chunk_iter.next()
            chunk_data = chunk["data"][self._position % chunk_size :]

            if not chunk_data:
                raise CorruptGridFile("truncated chunk")

        self._position += len(chunk_data)
        self._buffer = EMPTY
        self._buffer_pos = 0
        return chunk_data

    def _read_size_or_line(self, size: int = -1, line: bool = False) -> bytes:
        """Internal read() and readline() helper."""
        self.open()
        remainder = int(self.length) - self._position
        if size < 0 or size > remainder:
            size = remainder

        if size == 0:
            return EMPTY

        received = 0
        data = []
        while received < size:
            needed = size - received
            if self._buffer:
                # Optimization: Read the buffer with zero byte copies.
                buf = self._buffer
                chunk_start = self._buffer_pos
                chunk_data = memoryview(buf)[self._buffer_pos :]
                self._buffer = EMPTY
                self._buffer_pos = 0
                self._position += len(chunk_data)
            else:
                buf = self.readchunk()
                chunk_start = 0
                chunk_data = memoryview(buf)
            if line:
                pos = buf.find(NEWLN, chunk_start, chunk_start + needed) - chunk_start
                if pos >= 0:
                    # Decrease size to exit the loop.
                    size = received + pos + 1
                    needed = pos + 1
            if len(chunk_data) > needed:
                data.append(chunk_data[:needed])
                # Optimization: Save the buffer with zero byte copies.
                self._buffer = buf
                self._buffer_pos = chunk_start + needed
                self._position -= len(self._buffer) - self._buffer_pos
            else:
                data.append(chunk_data)
            received += len(chunk_data)

        # Detect extra chunks after reading the entire file.
        if size == remainder and self._chunk_iter:
            try:
                self._chunk_iter.next()
            except StopIteration:
                pass

        return b"".join(data)

    def read(self, size: int = -1) -> bytes:
        """Read at most `size` bytes from the file (less if there
        isn't enough data).

        The bytes are returned as an instance of :class:`bytes`
        If `size` is negative or omitted all data is read.

        :param size: the number of bytes to read

        .. versionchanged:: 3.8
           This method now only checks for extra chunks after reading the
           entire file. Previously, this method would check for extra chunks
           on every call.
        """
        return self._read_size_or_line(size=size)

    def tell(self) -> int:
        """Return the current position of this file."""
        return self._position

    def seek(self, pos: int, whence: int = _SEEK_SET) -> int:
        """Set the current position of this file.

        :param pos: the position (or offset if using relative
           positioning) to seek to
        :param whence: where to seek
           from. :attr:`os.SEEK_SET` (``0``) for absolute file
           positioning, :attr:`os.SEEK_CUR` (``1``) to seek relative
           to the current position, :attr:`os.SEEK_END` (``2``) to
           seek relative to the file's end.

        .. versionchanged:: 4.1
           The method now returns the new position in the file, to
           conform to the behavior of :meth:`io.IOBase.seek`.
        """
        if whence == _SEEK_SET:
            new_pos = pos
        elif whence == _SEEK_CUR:
            new_pos = self._position + pos
        elif whence == _SEEK_END:
            new_pos = int(self.length) + pos
        else:
            raise OSError(22, "Invalid value for `whence`")

        if new_pos < 0:
            raise OSError(22, "Invalid value for `pos` - must be positive")

        # Optimization, continue using the same buffer and chunk iterator.
        if new_pos == self._position:
            return new_pos

        self._position = new_pos
        self._buffer = EMPTY
        self._buffer_pos = 0
        if self._chunk_iter:
            self._chunk_iter.close()
            self._chunk_iter = None
        return new_pos

    def seekable(self) -> bool:
        return True

    def __iter__(self) -> GridOut:
        """Return an iterator over all of this file's data.

        The iterator will return lines (delimited by ``b'\\n'``) of
        :class:`bytes`. This can be useful when serving files
        using a webserver that handles such an iterator efficiently.

        .. versionchanged:: 3.8
           The iterator now raises :class:`CorruptGridFile` when encountering
           any truncated, missing, or extra chunk in a file. The previous
           behavior was to only raise :class:`CorruptGridFile` on a missing
           chunk.

        .. versionchanged:: 4.0
           The iterator now iterates over *lines* in the file, instead
           of chunks, to conform to the base class :py:class:`io.IOBase`.
           Use :meth:`GridOut.readchunk` to read chunk by chunk instead
           of line by line.
        """
        return self

    def close(self) -> None:
        """Make GridOut more generically file-like."""
        if self._chunk_iter:
            self._chunk_iter.close()
            self._chunk_iter = None
        if _IS_SYNC:
            super().close()
        else:
            self.closed = True

    def write(self, value: Any) -> NoReturn:
        raise io.UnsupportedOperation("write")

    def writelines(self, lines: Any) -> NoReturn:
        raise io.UnsupportedOperation("writelines")

    def writable(self) -> bool:
        return False

    def __enter__(self) -> GridOut:
        """Makes it possible to use :class:`GridOut` files
        with the async context manager protocol.
        """
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> Any:
        """Makes it possible to use :class:`GridOut` files
        with the async context manager protocol.
        """
        self.close()
        return False

    def fileno(self) -> NoReturn:
        raise io.UnsupportedOperation("fileno")

    def flush(self) -> None:
        # GridOut is read-only, so flush does nothing.
        pass

    def isatty(self) -> bool:
        return False

    def truncate(self, size: Optional[int] = None) -> NoReturn:
        # See https://docs.python.org/3/library/io.html#io.IOBase.writable
        # for why truncate has to raise.
        raise io.UnsupportedOperation("truncate")

    # Override IOBase.__del__ otherwise it will lead to __getattr__ on
    # __IOBase_closed which calls _ensure_file and potentially performs I/O.
    # We cannot do I/O in __del__ since it can lead to a deadlock.
    def __del__(self) -> None:
        pass


class GridOutChunkIterator:
    """Iterates over a file's chunks using a single cursor.

    Raises CorruptGridFile when encountering any truncated, missing, or extra
    chunk in a file.
    """

    def __init__(
        self,
        grid_out: GridOut,
        chunks: Collection,
        session: Optional[ClientSession],
        next_chunk: Any,
    ) -> None:
        self._id = grid_out._id
        self._chunk_size = int(grid_out.chunk_size)
        self._length = int(grid_out.length)
        self._chunks = chunks
        self._session = session
        self._next_chunk = next_chunk
        self._num_chunks = math.ceil(float(self._length) / self._chunk_size)
        self._cursor = None

    _cursor: Optional[Cursor]

    def expected_chunk_length(self, chunk_n: int) -> int:
        if chunk_n < self._num_chunks - 1:
            return self._chunk_size
        return self._length - (self._chunk_size * (self._num_chunks - 1))

    def __iter__(self) -> GridOutChunkIterator:
        return self

    def _create_cursor(self) -> None:
        filter = {"files_id": self._id}
        if self._next_chunk > 0:
            filter["n"] = {"$gte": self._next_chunk}
        _disallow_transactions(self._session)
        self._cursor = self._chunks.find(filter, sort=[("n", 1)], session=self._session)

    def _next_with_retry(self) -> Mapping[str, Any]:
        """Return the next chunk and retry once on CursorNotFound.

        We retry on CursorNotFound to maintain backwards compatibility in
        cases where two calls to read occur more than 10 minutes apart (the
        server's default cursor timeout).
        """
        if self._cursor is None:
            self._create_cursor()
            assert self._cursor is not None
        try:
            return self._cursor.next()
        except CursorNotFound:
            self._cursor.close()
            self._create_cursor()
            return self._cursor.next()

    def next(self) -> Mapping[str, Any]:
        try:
            chunk = self._next_with_retry()
        except StopIteration:
            if self._next_chunk >= self._num_chunks:
                raise
            raise CorruptGridFile("no chunk #%d" % self._next_chunk) from None

        if chunk["n"] != self._next_chunk:
            self.close()
            raise CorruptGridFile(
                "Missing chunk: expected chunk #%d but found "
                "chunk with n=%d" % (self._next_chunk, chunk["n"])
            )

        if chunk["n"] >= self._num_chunks:
            # According to spec, ignore extra chunks if they are empty.
            if len(chunk["data"]):
                self.close()
                raise CorruptGridFile(
                    "Extra chunk found: expected %d chunks but found "
                    "chunk with n=%d" % (self._num_chunks, chunk["n"])
                )

        expected_length = self.expected_chunk_length(chunk["n"])
        if len(chunk["data"]) != expected_length:
            self.close()
            raise CorruptGridFile(
                "truncated chunk #%d: expected chunk length to be %d but "
                "found chunk with length %d" % (chunk["n"], expected_length, len(chunk["data"]))
            )

        self._next_chunk += 1
        return chunk

    __next__ = next

    def close(self) -> None:
        if self._cursor:
            self._cursor.close()
            self._cursor = None


class GridOutIterator:
    def __init__(self, grid_out: GridOut, chunks: Collection, session: ClientSession):
        self._chunk_iter = GridOutChunkIterator(grid_out, chunks, session, 0)

    def __iter__(self) -> GridOutIterator:
        return self

    def next(self) -> bytes:
        chunk = self._chunk_iter.next()
        return bytes(chunk["data"])

    __next__ = next


class GridOutCursor(Cursor):
    """A cursor / iterator for returning GridOut objects as the result
    of an arbitrary query against the GridFS files collection.
    """

    def __init__(
        self,
        collection: Collection,
        filter: Optional[Mapping[str, Any]] = None,
        skip: int = 0,
        limit: int = 0,
        no_cursor_timeout: bool = False,
        sort: Optional[Any] = None,
        batch_size: int = 0,
        session: Optional[ClientSession] = None,
    ) -> None:
        """Create a new cursor, similar to the normal
        :class:`~pymongo.cursor.Cursor`.

        Should not be called directly by application developers - see
        the :class:`~gridfs.GridFS` method :meth:`~gridfs.GridFS.find` instead.

        .. versionadded 2.7

        .. seealso:: The MongoDB documentation on `cursors <https://dochub.mongodb.org/core/cursors>`_.
        """
        _disallow_transactions(session)
        collection = _clear_entity_type_registry(collection)

        # Hold on to the base "fs" collection to create GridOut objects later.
        self._root_collection = collection

        super().__init__(
            collection.files,
            filter,
            skip=skip,
            limit=limit,
            no_cursor_timeout=no_cursor_timeout,
            sort=sort,
            batch_size=batch_size,
            session=session,
        )

    def next(self) -> GridOut:
        """Get next GridOut object from cursor."""
        _disallow_transactions(self.session)
        next_file = super().next()
        return GridOut(self._root_collection, file_document=next_file, session=self.session)

    def to_list(self, length: Optional[int] = None) -> list[GridOut]:
        """Convert the cursor to a list."""
        if length is None:
            return [x for x in self]  # noqa: C416,RUF100
        if length < 1:
            raise ValueError("to_list() length must be greater than 0")
        ret = []
        for _ in range(length):
            ret.append(self.next())
        return ret

    __next__ = next

    def add_option(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise NotImplementedError("Method does not exist for GridOutCursor")

    def remove_option(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise NotImplementedError("Method does not exist for GridOutCursor")

    def _clone_base(self, session: Optional[ClientSession]) -> GridOutCursor:
        """Creates an empty GridOutCursor for information to be copied into."""
        return GridOutCursor(self._root_collection, session=session)
