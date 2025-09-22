# Copyright 2024-present MongoDB, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you
# may not use this file except in compliance with the License.  You
# may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.  See the License for the specific language governing
# permissions and limitations under the License.


"""Constants and types shared across all cursor classes."""
from __future__ import annotations

from typing import Any, Mapping, Sequence, Tuple, Union

# These errors mean that the server has already killed the cursor so there is
# no need to send killCursors.
_CURSOR_CLOSED_ERRORS = frozenset(
    [
        43,  # CursorNotFound
        175,  # QueryPlanKilled
        237,  # CursorKilled
        # On a tailable cursor, the following errors mean the capped collection
        # rolled over.
        # MongoDB 2.6:
        # {'$err': 'Runner killed during getMore', 'code': 28617, 'ok': 0}
        28617,
        # MongoDB 3.0:
        # {'$err': 'getMore executor error: UnknownError no details available',
        #  'code': 17406, 'ok': 0}
        17406,
        # MongoDB 3.2 + 3.4:
        # {'ok': 0.0, 'errmsg': 'GetMore command executor error:
        #  CappedPositionLost: CollectionScan died due to failure to restore
        #  tailable cursor position. Last seen record id: RecordId(3)',
        #  'code': 96}
        96,
        # MongoDB 3.6+:
        # {'ok': 0.0, 'errmsg': 'errmsg: "CollectionScan died due to failure to
        #  restore tailable cursor position. Last seen record id: RecordId(3)"',
        #  'code': 136, 'codeName': 'CappedPositionLost'}
        136,
    ]
)

_QUERY_OPTIONS = {
    "tailable_cursor": 2,
    "secondary_okay": 4,
    "oplog_replay": 8,
    "no_timeout": 16,
    "await_data": 32,
    "exhaust": 64,
    "partial": 128,
}


class CursorType:
    NON_TAILABLE = 0
    """The standard cursor type."""

    TAILABLE = _QUERY_OPTIONS["tailable_cursor"]
    """The tailable cursor type.

    Tailable cursors are only for use with capped collections. They are not
    closed when the last data is retrieved but are kept open and the cursor
    location marks the final document position. If more data is received
    iteration of the cursor will continue from the last document received.
    """

    TAILABLE_AWAIT = TAILABLE | _QUERY_OPTIONS["await_data"]
    """A tailable cursor with the await option set.

    Creates a tailable cursor that will wait for a few seconds after returning
    the full result set so that it can capture and return additional data added
    during the query.
    """

    EXHAUST = _QUERY_OPTIONS["exhaust"]
    """An exhaust cursor.

    MongoDB will stream batched results to the client without waiting for the
    client to request each batch, reducing latency.
    """


_Sort = Union[
    Sequence[Union[str, Tuple[str, Union[int, str, Mapping[str, Any]]]]], Mapping[str, Any]
]
_Hint = Union[str, _Sort]
