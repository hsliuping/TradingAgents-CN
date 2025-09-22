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


"""Constants, types, and classes shared across Client Bulk Write API implementations."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Mapping, MutableMapping, NoReturn

from pymongo.errors import ClientBulkWriteException, OperationFailure
from pymongo.helpers_shared import _get_wce_doc

if TYPE_CHECKING:
    from pymongo.typings import _DocumentOut


def _merge_command(
    ops: list[tuple[str, Mapping[str, Any]]],
    offset: int,
    full_result: MutableMapping[str, Any],
    result: Mapping[str, Any],
) -> None:
    """Merge result of a single bulk write batch into the full result."""
    if result.get("error"):
        full_result["error"] = result["error"]

    full_result["nInserted"] += result.get("nInserted", 0)
    full_result["nDeleted"] += result.get("nDeleted", 0)
    full_result["nMatched"] += result.get("nMatched", 0)
    full_result["nModified"] += result.get("nModified", 0)
    full_result["nUpserted"] += result.get("nUpserted", 0)

    write_errors = result.get("writeErrors")
    if write_errors:
        for doc in write_errors:
            # Leave the server response intact for APM.
            replacement = doc.copy()
            original_index = doc["idx"] + offset
            replacement["idx"] = original_index
            # Add the failed operation to the error document.
            replacement["op"] = ops[original_index][1]
            full_result["writeErrors"].append(replacement)

    wce = _get_wce_doc(result)
    if wce:
        full_result["writeConcernErrors"].append(wce)


def _throw_client_bulk_write_exception(
    full_result: _DocumentOut, verbose_results: bool
) -> NoReturn:
    """Raise a ClientBulkWriteException from the full result."""
    # retryWrites on MMAPv1 should raise an actionable error.
    if full_result["writeErrors"]:
        full_result["writeErrors"].sort(key=lambda error: error["idx"])
        err = full_result["writeErrors"][0]
        code = err["code"]
        msg = err["errmsg"]
        if code == 20 and msg.startswith("Transaction numbers"):
            errmsg = (
                "This MongoDB deployment does not support "
                "retryable writes. Please add retryWrites=false "
                "to your connection string."
            )
            raise OperationFailure(errmsg, code, full_result)
    if isinstance(full_result["error"], BaseException):
        raise ClientBulkWriteException(full_result, verbose_results) from full_result["error"]
    raise ClientBulkWriteException(full_result, verbose_results)
