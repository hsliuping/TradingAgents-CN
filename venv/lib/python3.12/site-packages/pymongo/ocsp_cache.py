# Copyright 2020-present MongoDB, Inc.
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

"""Utilities for caching OCSP responses."""

from __future__ import annotations

from collections import namedtuple
from datetime import datetime as _datetime
from datetime import timezone
from typing import TYPE_CHECKING, Any, Optional

from pymongo.lock import _create_lock

if TYPE_CHECKING:
    from cryptography.x509.ocsp import OCSPRequest, OCSPResponse


def _next_update(value: OCSPResponse) -> Optional[_datetime]:
    """Compat helper to return the response's next_update_utc."""
    # Added in cryptography 43.0.0.
    if hasattr(value, "next_update_utc"):
        return value.next_update_utc
    return value.next_update


def _this_update(value: OCSPResponse) -> Optional[_datetime]:
    """Compat helper to return the response's this_update_utc."""
    # Added in cryptography 43.0.0.
    if hasattr(value, "this_update_utc"):
        return value.this_update_utc
    return value.this_update


class _OCSPCache:
    """A cache for OCSP responses."""

    CACHE_KEY_TYPE = namedtuple(  # type: ignore
        "OcspResponseCacheKey",
        ["hash_algorithm", "issuer_name_hash", "issuer_key_hash", "serial_number"],
    )

    def __init__(self) -> None:
        self._data: dict[Any, OCSPResponse] = {}
        # Hold this lock when accessing _data.
        self._lock = _create_lock()

    def _get_cache_key(self, ocsp_request: OCSPRequest) -> CACHE_KEY_TYPE:
        return self.CACHE_KEY_TYPE(
            hash_algorithm=ocsp_request.hash_algorithm.name.lower(),
            issuer_name_hash=ocsp_request.issuer_name_hash,
            issuer_key_hash=ocsp_request.issuer_key_hash,
            serial_number=ocsp_request.serial_number,
        )

    def __setitem__(self, key: OCSPRequest, value: OCSPResponse) -> None:
        """Add/update a cache entry.

        'key' is of type cryptography.x509.ocsp.OCSPRequest
        'value' is of type cryptography.x509.ocsp.OCSPResponse

        Validity of the OCSP response must be checked by caller.
        """
        with self._lock:
            cache_key = self._get_cache_key(key)

            # As per the OCSP protocol, if the response's nextUpdate field is
            # not set, the responder is indicating that newer revocation
            # information is available all the time.
            next_update = _next_update(value)
            if next_update is None:
                self._data.pop(cache_key, None)
                return

            this_update = _this_update(value)
            if this_update is None:
                return
            now = _datetime.now(tz=timezone.utc)
            if this_update.tzinfo is None:
                # Make naive to match cryptography.
                now = now.replace(tzinfo=None)
            # Do nothing if the response is invalid.
            if not (this_update <= now < next_update):
                return

            # Cache new response OR update cached response if new response
            # has longer validity.
            cached_value = self._data.get(cache_key, None)
            if cached_value is None:
                self._data[cache_key] = value
                return
            cached_next_update = _next_update(cached_value)
            if cached_next_update is not None and cached_next_update < next_update:
                self._data[cache_key] = value

    def __getitem__(self, item: OCSPRequest) -> OCSPResponse:
        """Get a cache entry if it exists.

        'item' is of type cryptography.x509.ocsp.OCSPRequest

        Raises KeyError if the item is not in the cache.
        """
        with self._lock:
            cache_key = self._get_cache_key(item)
            value = self._data[cache_key]

            # Return cached response if it is still valid.
            this_update = _this_update(value)
            next_update = _next_update(value)
            assert this_update is not None
            assert next_update is not None
            now = _datetime.now(tz=timezone.utc)
            if this_update.tzinfo is None:
                # Make naive to match cryptography.
                now = now.replace(tzinfo=None)
            if this_update <= now < next_update:
                return value

            self._data.pop(cache_key, None)
            raise KeyError(cache_key)
