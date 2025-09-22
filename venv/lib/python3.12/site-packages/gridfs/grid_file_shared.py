from __future__ import annotations

import os
import warnings
from typing import Any, Optional

from pymongo import ASCENDING
from pymongo.common import MAX_MESSAGE_SIZE
from pymongo.errors import InvalidOperation

_SEEK_SET = os.SEEK_SET
_SEEK_CUR = os.SEEK_CUR
_SEEK_END = os.SEEK_END

EMPTY = b""
NEWLN = b"\n"

"""Default chunk size, in bytes."""
# Slightly under a power of 2, to work well with server's record allocations.
DEFAULT_CHUNK_SIZE = 255 * 1024
# The number of chunked bytes to buffer before calling insert_many.
_UPLOAD_BUFFER_SIZE = MAX_MESSAGE_SIZE
# The number of chunk documents to buffer before calling insert_many.
_UPLOAD_BUFFER_CHUNKS = 100000
# Rough BSON overhead of a chunk document not including the chunk data itself.
# Essentially len(encode({"_id": ObjectId(), "files_id": ObjectId(), "n": 1, "data": ""}))
_CHUNK_OVERHEAD = 60

_C_INDEX: dict[str, Any] = {"files_id": ASCENDING, "n": ASCENDING}
_F_INDEX: dict[str, Any] = {"filename": ASCENDING, "uploadDate": ASCENDING}


def _a_grid_in_property(
    field_name: str,
    docstring: str,
    read_only: Optional[bool] = False,
    closed_only: Optional[bool] = False,
) -> Any:
    """Create a GridIn property."""

    warn_str = ""
    if docstring.startswith("DEPRECATED,"):
        warn_str = (
            f"GridIn property '{field_name}' is deprecated and will be removed in PyMongo 5.0"
        )

    def getter(self: Any) -> Any:
        if warn_str:
            warnings.warn(warn_str, stacklevel=2, category=DeprecationWarning)
        if closed_only and not self._closed:
            raise AttributeError("can only get %r on a closed file" % field_name)
        # Protect against PHP-237
        if field_name == "length":
            return self._file.get(field_name, 0)
        return self._file.get(field_name, None)

    def setter(self: Any, value: Any) -> Any:
        if warn_str:
            warnings.warn(warn_str, stacklevel=2, category=DeprecationWarning)
        if self._closed:
            raise InvalidOperation(
                "AsyncGridIn does not support __setattr__ after being closed(). Set the attribute before closing the file or use AsyncGridIn.set() instead"
            )
        self._file[field_name] = value

    if read_only:
        docstring += "\n\nThis attribute is read-only."
    elif closed_only:
        docstring = "{}\n\n{}".format(
            docstring,
            "This attribute is read-only and "
            "can only be read after :meth:`close` "
            "has been called.",
        )

    if not read_only and not closed_only:
        return property(getter, setter, doc=docstring)
    return property(getter, doc=docstring)


def _a_grid_out_property(field_name: str, docstring: str) -> Any:
    """Create a GridOut property."""

    def a_getter(self: Any) -> Any:
        if not self._file:
            raise InvalidOperation(
                "You must call GridOut.open() before accessing " "the %s property" % field_name
            )
        # Protect against PHP-237
        if field_name == "length":
            return self._file.get(field_name, 0)
        return self._file.get(field_name, None)

    docstring += "\n\nThis attribute is read-only."
    return property(a_getter, doc=docstring)


def _grid_in_property(
    field_name: str,
    docstring: str,
    read_only: Optional[bool] = False,
    closed_only: Optional[bool] = False,
) -> Any:
    """Create a GridIn property."""
    warn_str = ""
    if docstring.startswith("DEPRECATED,"):
        warn_str = (
            f"GridIn property '{field_name}' is deprecated and will be removed in PyMongo 5.0"
        )

    def getter(self: Any) -> Any:
        if warn_str:
            warnings.warn(warn_str, stacklevel=2, category=DeprecationWarning)
        if closed_only and not self._closed:
            raise AttributeError("can only get %r on a closed file" % field_name)
        # Protect against PHP-237
        if field_name == "length":
            return self._file.get(field_name, 0)
        return self._file.get(field_name, None)

    def setter(self: Any, value: Any) -> Any:
        if warn_str:
            warnings.warn(warn_str, stacklevel=2, category=DeprecationWarning)
        if self._closed:
            self._coll.files.update_one({"_id": self._file["_id"]}, {"$set": {field_name: value}})
        self._file[field_name] = value

    if read_only:
        docstring += "\n\nThis attribute is read-only."
    elif closed_only:
        docstring = "{}\n\n{}".format(
            docstring,
            "This attribute is read-only and "
            "can only be read after :meth:`close` "
            "has been called.",
        )

    if not read_only and not closed_only:
        return property(getter, setter, doc=docstring)
    return property(getter, doc=docstring)


def _grid_out_property(field_name: str, docstring: str) -> Any:
    """Create a GridOut property."""
    warn_str = ""
    if docstring.startswith("DEPRECATED,"):
        warn_str = (
            f"GridOut property '{field_name}' is deprecated and will be removed in PyMongo 5.0"
        )

    def getter(self: Any) -> Any:
        if warn_str:
            warnings.warn(warn_str, stacklevel=2, category=DeprecationWarning)
        self.open()

        # Protect against PHP-237
        if field_name == "length":
            return self._file.get(field_name, 0)
        return self._file.get(field_name, None)

    docstring += "\n\nThis attribute is read-only."
    return property(getter, doc=docstring)


def _clear_entity_type_registry(entity: Any, **kwargs: Any) -> Any:
    """Clear the given database/collection object's type registry."""
    codecopts = entity.codec_options.with_options(type_registry=None)
    return entity.with_options(codec_options=codecopts, **kwargs)
