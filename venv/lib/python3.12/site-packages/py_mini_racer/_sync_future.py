from __future__ import annotations

from threading import Condition
from typing import TYPE_CHECKING

from py_mini_racer._types import JSTimeoutException

if TYPE_CHECKING:
    from py_mini_racer._numeric import Numeric
    from py_mini_racer._types import PythonJSConvertedTypes


class SyncFuture:
    """A blocking synchronization object for function return values.

    This is like asyncio.Future but blocking, or like
    concurrent.futures.Future but without an executor.
    """

    def __init__(self) -> None:
        self._cv = Condition()
        self._settled: bool = False
        self._res: PythonJSConvertedTypes = None
        self._exc: Exception | None = None

    def get(self, *, timeout: Numeric | None = None) -> PythonJSConvertedTypes:
        with self._cv:
            while not self._settled:
                if not self._cv.wait(timeout=timeout):
                    raise JSTimeoutException

            if self._exc:
                raise self._exc
            return self._res

    def set_result(self, res: PythonJSConvertedTypes) -> None:
        with self._cv:
            self._res = res
            self._settled = True
            self._cv.notify()

    def set_exception(self, exc: Exception) -> None:
        with self._cv:
            self._exc = exc
            self._settled = True
            self._cv.notify()
