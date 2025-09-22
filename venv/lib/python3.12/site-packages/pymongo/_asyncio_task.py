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

"""A custom asyncio.Task that allows checking if a task has been sent a cancellation request.
Can be removed once we drop Python 3.10 support in favor of asyncio.Task.cancelling."""


from __future__ import annotations

import asyncio
import sys
from typing import Any, Coroutine, Optional


# TODO (https://jira.mongodb.org/browse/PYTHON-4981): Revisit once the underlying cause of the swallowed cancellations is uncovered
class _Task(asyncio.Task):
    def __init__(self, coro: Coroutine[Any, Any, Any], *, name: Optional[str] = None) -> None:
        super().__init__(coro, name=name)
        self._cancel_requests = 0
        asyncio._register_task(self)

    def cancel(self, msg: Optional[str] = None) -> bool:
        self._cancel_requests += 1
        return super().cancel(msg=msg)

    def uncancel(self) -> int:
        if self._cancel_requests > 0:
            self._cancel_requests -= 1
        return self._cancel_requests

    def cancelling(self) -> int:
        return self._cancel_requests


def create_task(coro: Coroutine[Any, Any, Any], *, name: Optional[str] = None) -> asyncio.Task:
    if sys.version_info >= (3, 11):
        return asyncio.create_task(coro, name=name)
    return _Task(coro, name=name)
