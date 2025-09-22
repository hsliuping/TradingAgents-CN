# Copyright 2022-present MongoDB, Inc.
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

"""Internal helpers for lock and condition coordination primitives."""

from __future__ import annotations

import asyncio
import os
import sys
import threading
import weakref
from asyncio import wait_for
from typing import Any, Optional, TypeVar

import pymongo._asyncio_lock

_HAS_REGISTER_AT_FORK = hasattr(os, "register_at_fork")

# References to instances of _create_lock
_forkable_locks: weakref.WeakSet[threading.Lock] = weakref.WeakSet()

_T = TypeVar("_T")

# Needed to support 3.13 asyncio fixes (https://github.com/python/cpython/issues/112202)
# in older versions of Python
if sys.version_info >= (3, 13):
    Lock = asyncio.Lock
    Condition = asyncio.Condition
else:
    Lock = pymongo._asyncio_lock.Lock
    Condition = pymongo._asyncio_lock.Condition


def _create_lock() -> threading.Lock:
    """Represents a lock that is tracked upon instantiation using a WeakSet and
    reset by pymongo upon forking.
    """
    lock = threading.Lock()
    if _HAS_REGISTER_AT_FORK:
        _forkable_locks.add(lock)
    return lock


def _async_create_lock() -> Lock:
    """Represents an asyncio.Lock."""
    return Lock()


def _create_condition(
    lock: threading.Lock, condition_class: Optional[Any] = None
) -> threading.Condition:
    """Represents a threading.Condition."""
    if condition_class:
        return condition_class(lock)
    return threading.Condition(lock)


def _async_create_condition(lock: Lock, condition_class: Optional[Any] = None) -> Condition:
    """Represents an asyncio.Condition."""
    if condition_class:
        return condition_class(lock)
    return Condition(lock)


def _release_locks() -> None:
    # Completed the fork, reset all the locks in the child.
    for lock in _forkable_locks:
        if lock.locked():
            lock.release()


async def _async_cond_wait(condition: Condition, timeout: Optional[float]) -> bool:
    try:
        return await wait_for(condition.wait(), timeout)
    except asyncio.TimeoutError:
        return False


def _cond_wait(condition: threading.Condition, timeout: Optional[float]) -> bool:
    return condition.wait(timeout)
