# Copyright 2015-present MongoDB, Inc.
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

"""Result class definitions.

.. seealso:: This module is compatible with both the synchronous and asynchronous PyMongo APIs.
"""
from __future__ import annotations

from typing import Any, Mapping, MutableMapping, Optional, cast

from pymongo.errors import InvalidOperation


class _WriteResult:
    """Base class for write result classes."""

    __slots__ = ("__acknowledged",)

    def __init__(self, acknowledged: bool) -> None:
        self.__acknowledged = acknowledged

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.__acknowledged})"

    def _raise_if_unacknowledged(self, property_name: str) -> None:
        """Raise an exception on property access if unacknowledged."""
        if not self.__acknowledged:
            raise InvalidOperation(
                f"A value for {property_name} is not available when "
                "the write is unacknowledged. Check the "
                "acknowledged attribute to avoid this "
                "error."
            )

    @property
    def acknowledged(self) -> bool:
        """Is this the result of an acknowledged write operation?

        The :attr:`acknowledged` attribute will be ``False`` when using
        ``WriteConcern(w=0)``, otherwise ``True``.

        .. note::
          If the :attr:`acknowledged` attribute is ``False`` all other
          attributes of this class will raise
          :class:`~pymongo.errors.InvalidOperation` when accessed. Values for
          other attributes cannot be determined if the write operation was
          unacknowledged.

        .. seealso::
          :class:`~pymongo.write_concern.WriteConcern`
        """
        return self.__acknowledged


class InsertOneResult(_WriteResult):
    """The return type for :meth:`~pymongo.collection.Collection.insert_one`
    and as part of :meth:`~pymongo.mongo_client.MongoClient.bulk_write`.
    """

    __slots__ = ("__inserted_id",)

    def __init__(self, inserted_id: Any, acknowledged: bool) -> None:
        self.__inserted_id = inserted_id
        super().__init__(acknowledged)

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}({self.__inserted_id!r}, acknowledged={self.acknowledged})"
        )

    @property
    def inserted_id(self) -> Any:
        """The inserted document's _id."""
        return self.__inserted_id


class InsertManyResult(_WriteResult):
    """The return type for :meth:`~pymongo.collection.Collection.insert_many`."""

    __slots__ = ("__inserted_ids",)

    def __init__(self, inserted_ids: list[Any], acknowledged: bool) -> None:
        self.__inserted_ids = inserted_ids
        super().__init__(acknowledged)

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}({self.__inserted_ids!r}, acknowledged={self.acknowledged})"
        )

    @property
    def inserted_ids(self) -> list[Any]:
        """A list of _ids of the inserted documents, in the order provided.

        .. note:: If ``False`` is passed for the `ordered` parameter to
          :meth:`~pymongo.collection.Collection.insert_many` the server
          may have inserted the documents in a different order than what
          is presented here.
        """
        return self.__inserted_ids


class UpdateResult(_WriteResult):
    """The return type for :meth:`~pymongo.collection.Collection.update_one`,
    :meth:`~pymongo.collection.Collection.update_many`, and
    :meth:`~pymongo.collection.Collection.replace_one`, and as part of
    :meth:`~pymongo.mongo_client.MongoClient.bulk_write`.
    """

    __slots__ = (
        "__raw_result",
        "__in_client_bulk",
    )

    def __init__(
        self,
        raw_result: Optional[Mapping[str, Any]],
        acknowledged: bool,
        in_client_bulk: bool = False,
    ):
        self.__raw_result = raw_result
        self.__in_client_bulk = in_client_bulk
        super().__init__(acknowledged)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.__raw_result!r}, acknowledged={self.acknowledged})"

    @property
    def raw_result(self) -> Optional[Mapping[str, Any]]:
        """The raw result document returned by the server."""
        return self.__raw_result

    @property
    def matched_count(self) -> int:
        """The number of documents matched for this update."""
        self._raise_if_unacknowledged("matched_count")
        assert self.__raw_result is not None
        if not self.__in_client_bulk and self.upserted_id is not None:
            return 0
        return self.__raw_result.get("n", 0)

    @property
    def modified_count(self) -> int:
        """The number of documents modified."""
        self._raise_if_unacknowledged("modified_count")
        assert self.__raw_result is not None
        return cast(int, self.__raw_result.get("nModified"))

    @property
    def upserted_id(self) -> Any:
        """The _id of the inserted document if an upsert took place. Otherwise
        ``None``.
        """
        self._raise_if_unacknowledged("upserted_id")
        assert self.__raw_result is not None
        if self.__in_client_bulk and self.__raw_result.get("upserted"):
            return self.__raw_result["upserted"]["_id"]
        return self.__raw_result.get("upserted", None)

    @property
    def did_upsert(self) -> bool:
        """Whether an upsert took place.

        .. versionadded:: 4.9
        """
        assert self.__raw_result is not None
        return "upserted" in self.__raw_result


class DeleteResult(_WriteResult):
    """The return type for :meth:`~pymongo.collection.Collection.delete_one`
    and :meth:`~pymongo.collection.Collection.delete_many`
    and as part of :meth:`~pymongo.mongo_client.MongoClient.bulk_write`.
    """

    __slots__ = ("__raw_result",)

    def __init__(self, raw_result: Mapping[str, Any], acknowledged: bool) -> None:
        self.__raw_result = raw_result
        super().__init__(acknowledged)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.__raw_result!r}, acknowledged={self.acknowledged})"

    @property
    def raw_result(self) -> Mapping[str, Any]:
        """The raw result document returned by the server."""
        return self.__raw_result

    @property
    def deleted_count(self) -> int:
        """The number of documents deleted."""
        self._raise_if_unacknowledged("deleted_count")
        return self.__raw_result.get("n", 0)


class _BulkWriteResultBase(_WriteResult):
    """Private base class for bulk write API results."""

    __slots__ = ("__bulk_api_result",)

    def __init__(self, bulk_api_result: dict[str, Any], acknowledged: bool) -> None:
        self.__bulk_api_result = bulk_api_result
        super().__init__(acknowledged)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.__bulk_api_result!r}, acknowledged={self.acknowledged})"

    @property
    def bulk_api_result(self) -> dict[str, Any]:
        """The raw bulk write API result."""
        return self.__bulk_api_result

    @property
    def inserted_count(self) -> int:
        """The number of documents inserted."""
        self._raise_if_unacknowledged("inserted_count")
        return cast(int, self.__bulk_api_result.get("nInserted"))

    @property
    def matched_count(self) -> int:
        """The number of documents matched for an update."""
        self._raise_if_unacknowledged("matched_count")
        return cast(int, self.__bulk_api_result.get("nMatched"))

    @property
    def modified_count(self) -> int:
        """The number of documents modified."""
        self._raise_if_unacknowledged("modified_count")
        return cast(int, self.__bulk_api_result.get("nModified"))

    @property
    def deleted_count(self) -> int:
        """The number of documents deleted."""
        self._raise_if_unacknowledged("deleted_count")
        if "nRemoved" in self.__bulk_api_result:
            return cast(int, self.__bulk_api_result.get("nRemoved"))
        else:
            return cast(int, self.__bulk_api_result.get("nDeleted"))

    @property
    def upserted_count(self) -> int:
        """The number of documents upserted."""
        self._raise_if_unacknowledged("upserted_count")
        return cast(int, self.__bulk_api_result.get("nUpserted"))


class BulkWriteResult(_BulkWriteResultBase):
    """An object wrapper for collection-level bulk write API results."""

    __slots__ = ()

    def __init__(self, bulk_api_result: dict[str, Any], acknowledged: bool) -> None:
        """Create a BulkWriteResult instance.

        :param bulk_api_result: A result dict from the collection-level bulk write API
        :param acknowledged: Was this write result acknowledged? If ``False``
            then all properties of this object will raise
            :exc:`~pymongo.errors.InvalidOperation`.
        """
        super().__init__(bulk_api_result, acknowledged)

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}({self.bulk_api_result!r}, acknowledged={self.acknowledged})"
        )

    @property
    def upserted_ids(self) -> Optional[dict[int, Any]]:
        """A map of operation index to the _id of the upserted document."""
        self._raise_if_unacknowledged("upserted_ids")
        if self.bulk_api_result:
            return {upsert["index"]: upsert["_id"] for upsert in self.bulk_api_result["upserted"]}
        return None


class ClientBulkWriteResult(_BulkWriteResultBase):
    """An object wrapper for client-level bulk write API results."""

    __slots__ = ("__has_verbose_results",)

    def __init__(
        self,
        bulk_api_result: MutableMapping[str, Any],
        acknowledged: bool,
        has_verbose_results: bool,
    ) -> None:
        """Create a ClientBulkWriteResult instance.

        :param bulk_api_result: A result dict from the client-level bulk write API
        :param acknowledged: Was this write result acknowledged? If ``False``
            then all properties of this object will raise
            :exc:`~pymongo.errors.InvalidOperation`.
        :param has_verbose_results: Should the returned result be verbose?
            If ``False``, then the ``insert_results``, ``update_results``, and
            ``delete_results`` properties of this object will raise
            :exc:`~pymongo.errors.InvalidOperation`.
        """
        self.__has_verbose_results = has_verbose_results
        super().__init__(
            bulk_api_result,  # type: ignore[arg-type]
            acknowledged,
        )

    def __repr__(self) -> str:
        return "{}({!r}, acknowledged={}, verbose={})".format(
            self.__class__.__name__,
            self.bulk_api_result,
            self.acknowledged,
            self.has_verbose_results,
        )

    def _raise_if_not_verbose(self, property_name: str) -> None:
        """Raise an exception on property access if verbose results are off."""
        if not self.__has_verbose_results:
            raise InvalidOperation(
                f"A value for {property_name} is not available when "
                "the results are not set to be verbose. Check the "
                "verbose_results attribute to avoid this error."
            )

    @property
    def has_verbose_results(self) -> bool:
        """Whether the returned results should be verbose."""
        return self.__has_verbose_results

    @property
    def insert_results(self) -> Mapping[int, InsertOneResult]:
        """A map of successful insertion operations to their results."""
        self._raise_if_unacknowledged("insert_results")
        self._raise_if_not_verbose("insert_results")
        return cast(
            Mapping[int, InsertOneResult],
            self.bulk_api_result.get("insertResults"),
        )

    @property
    def update_results(self) -> Mapping[int, UpdateResult]:
        """A map of successful update operations to their results."""
        self._raise_if_unacknowledged("update_results")
        self._raise_if_not_verbose("update_results")
        return cast(
            Mapping[int, UpdateResult],
            self.bulk_api_result.get("updateResults"),
        )

    @property
    def delete_results(self) -> Mapping[int, DeleteResult]:
        """A map of successful delete operations to their results."""
        self._raise_if_unacknowledged("delete_results")
        self._raise_if_not_verbose("delete_results")
        return cast(
            Mapping[int, DeleteResult],
            self.bulk_api_result.get("deleteResults"),
        )
