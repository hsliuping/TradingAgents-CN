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


"""Constants, helpers, and types shared across all database classes."""
from __future__ import annotations

from typing import Any, Mapping, TypeVar

from pymongo.errors import InvalidName


def _check_name(name: str) -> None:
    """Check if a database name is valid."""
    if not name:
        raise InvalidName("database name cannot be the empty string")

    for invalid_char in [" ", ".", "$", "/", "\\", "\x00", '"']:
        if invalid_char in name:
            raise InvalidName("database names cannot contain the character %r" % invalid_char)


_CodecDocumentType = TypeVar("_CodecDocumentType", bound=Mapping[str, Any])
