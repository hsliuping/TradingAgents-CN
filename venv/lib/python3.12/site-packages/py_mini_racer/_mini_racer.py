from __future__ import annotations

import json
from json import JSONEncoder
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
)

from py_mini_racer._context import Context
from py_mini_racer._dll import init_mini_racer
from py_mini_racer._set_timeout import INSTALL_SET_TIMEOUT
from py_mini_racer._types import MiniRacerBaseException

if TYPE_CHECKING:
    from contextlib import AbstractAsyncContextManager
    from types import TracebackType

    from typing_extensions import Self

    from py_mini_racer._context import PyJsFunctionType
    from py_mini_racer._numeric import Numeric
    from py_mini_racer._objects import JSFunction
    from py_mini_racer._types import PythonJSConvertedTypes


class WrongReturnTypeException(MiniRacerBaseException):
    """Invalid type returned by the JavaScript runtime."""

    def __init__(self, typ: type):
        super().__init__(f"Unexpected return value type {typ}")


class MiniRacer:
    """
    MiniRacer evaluates JavaScript code using a V8 isolate.

    A MiniRacer instance can be explicitly closed using the close() method, or by using
    the MiniRacer as a context manager, i.e,:

    with MiniRacer() as mr:
        ...

    The MiniRacer instance will otherwise clean up the underlying V8 resource upon
    garbage collection.

    Attributes:
        json_impl: JSON module used by helper methods default is
            [json](https://docs.python.org/3/library/json.html)
    """

    json_impl: ClassVar[Any] = json

    def __init__(self) -> None:
        dll = init_mini_racer(ignore_duplicate_init=True)

        self._ctx = Context(dll)

        self.eval(INSTALL_SET_TIMEOUT)

    def close(self) -> None:
        """Close this MiniRacer instance.

        It is an error to use this MiniRacer instance or any JS objects returned by it
        after calling this method.
        """
        self._ctx.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        del exc_type
        del exc_val
        del exc_tb
        self.close()

    @property
    def v8_version(self) -> str:
        """Return the V8 version string."""
        return self._ctx.v8_version()

    def eval(
        self,
        code: str,
        timeout: Numeric | None = None,
        timeout_sec: Numeric | None = None,
        max_memory: int | None = None,
    ) -> PythonJSConvertedTypes:
        """Evaluate JavaScript code in the V8 isolate.

        Side effects from the JavaScript evaluation is persisted inside a context
        (meaning variables set are kept for the next evaluation).

        The JavaScript value returned by the last expression in `code` is converted to
        a Python value and returned by this method. Only primitive types are supported
        (numbers, strings, buffers...). Use the
        [py_mini_racer.MiniRacer.execute][] method to return more complex
        types such as arrays or objects.

        The evaluation can be interrupted by an exception for several reasons: a limit
        was reached, the code could not be parsed, a returned value could not be
        converted to a Python value.

        Args:
            code: JavaScript code
            timeout: number of milliseconds after which the execution is interrupted.
                This is deprecated; use timeout_sec instead.
            timeout_sec: number of seconds after which the execution is interrupted
            max_memory: hard memory limit, in bytes, after which the execution is
                interrupted.
        """

        if max_memory is not None:
            self.set_hard_memory_limit(max_memory)

        if timeout:
            # PyMiniRacer unfortunately uses milliseconds while Python and
            # Système international d'unités use seconds.
            timeout_sec = timeout / 1000

        return self._ctx.evaluate(code=code, timeout_sec=timeout_sec)

    def execute(
        self,
        expr: str,
        timeout: Numeric | None = None,
        timeout_sec: Numeric | None = None,
        max_memory: int | None = None,
    ) -> Any:
        """Helper to evaluate a JavaScript expression and return composite types.

        Returned value is serialized to JSON inside the V8 isolate and deserialized
        using `json_impl`.

        Args:
            expr: JavaScript expression
            timeout: number of milliseconds after which the execution is interrupted.
                This is deprecated; use timeout_sec instead.
            timeout_sec: number of seconds after which the execution is interrupted
            max_memory: hard memory limit, in bytes, after which the execution is
                interrupted.
        """

        if timeout:
            # PyMiniRacer unfortunately uses milliseconds while Python and
            # Système international d'unités use seconds.
            timeout_sec = timeout / 1000

        wrapped_expr = f"JSON.stringify((function(){{return ({expr})}})())"
        ret = self.eval(wrapped_expr, timeout_sec=timeout_sec, max_memory=max_memory)
        if not isinstance(ret, str):
            raise WrongReturnTypeException(type(ret))
        return self.json_impl.loads(ret)

    def call(
        self,
        expr: str,
        *args: Any,
        encoder: JSONEncoder | None = None,
        timeout: Numeric | None = None,
        timeout_sec: Numeric | None = None,
        max_memory: int | None = None,
    ) -> Any:
        """Helper to call a JavaScript function and return compositve types.

        The `expr` argument refers to a JavaScript function in the current V8
        isolate context. Further positional arguments are serialized using the JSON
        implementation `json_impl` and passed to the JavaScript function as arguments.

        Returned value is serialized to JSON inside the V8 isolate and deserialized
        using `json_impl`.

        Args:
            expr: JavaScript expression referring to a function
            encoder: Custom JSON encoder
            timeout: number of milliseconds after which the execution is
                interrupted.
            timeout_sec: number of seconds after which the execution is interrupted
            max_memory: hard memory limit, in bytes, after which the execution is
                interrupted
        """

        if timeout:
            # PyMiniRacer unfortunately uses milliseconds while Python and
            # Système international d'unités use seconds.
            timeout_sec = timeout / 1000

        json_args = self.json_impl.dumps(args, separators=(",", ":"), cls=encoder)
        js = f"{expr}.apply(this, {json_args})"
        return self.execute(js, timeout_sec=timeout_sec, max_memory=max_memory)

    def wrap_py_function(
        self,
        func: PyJsFunctionType,
    ) -> AbstractAsyncContextManager[JSFunction]:
        """Wrap a Python function such that it can be called from JS.

        To be wrapped and exposed in JavaScript, a Python function should:

          1. Be async,
          2. Accept variable positional arguments each of type PythonJSConvertedTypes,
             and
          3. Return one value of type PythonJSConvertedTypes (a type union which
             includes None).

        The function is rendered on the JavaScript side as an async function (i.e., a
        function which returns a Promise).

        Returns:
            An async context manager which, when entered, yields a JS Function which
            can be passed into MiniRacer and called by JS code.
        """

        return self._ctx.wrap_py_function(func)

    def set_hard_memory_limit(self, limit: int) -> None:
        """Set a hard memory limit on this V8 isolate.

        JavaScript execution will be terminated when this limit is reached.

        :param int limit: memory limit in bytes or 0 to reset the limit
        """
        self._ctx.set_hard_memory_limit(limit)

    def set_soft_memory_limit(self, limit: int) -> None:
        """Set a soft memory limit on this V8 isolate.

        The Garbage Collection will use a more aggressive strategy when
        the soft limit is reached but the execution will not be stopped.

        :param int limit: memory limit in bytes or 0 to reset the limit
        """
        self._ctx.set_soft_memory_limit(limit)

    def was_hard_memory_limit_reached(self) -> bool:
        """Return true if the hard memory limit was reached on the V8 isolate."""
        return self._ctx.was_hard_memory_limit_reached()

    def was_soft_memory_limit_reached(self) -> bool:
        """Return true if the soft memory limit was reached on the V8 isolate."""
        return self._ctx.was_soft_memory_limit_reached()

    def low_memory_notification(self) -> None:
        """Ask the V8 isolate to collect memory more aggressively."""
        self._ctx.low_memory_notification()

    def heap_stats(self) -> Any:
        """Return the V8 isolate heap statistics."""

        return self.json_impl.loads(self._ctx.heap_stats())


# Compatibility with versions 0.4 & 0.5
StrictMiniRacer = MiniRacer
