"""Python wrappers for JavaScript object types."""

from __future__ import annotations

from asyncio import get_running_loop
from contextlib import ExitStack
from operator import index as op_index
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Generator,
    Iterator,
    MutableMapping,
    MutableSequence,
    cast,
)

from py_mini_racer._sync_future import SyncFuture
from py_mini_racer._types import (
    JSEvalException,
    JSObject,
    JSUndefined,
    JSUndefinedType,
    MiniRacerBaseException,
    PythonJSConvertedTypes,
)

if TYPE_CHECKING:
    from asyncio import Future

    from py_mini_racer._abstract_context import AbstractContext, AbstractValueHandle
    from py_mini_racer._numeric import Numeric


def _get_exception_msg(reason: PythonJSConvertedTypes) -> str:
    if not isinstance(reason, JSMappedObject):
        return str(reason)

    if "stack" in reason:
        return cast(str, reason["stack"])

    return str(reason)


class JSPromiseError(MiniRacerBaseException):
    """JavaScript rejected a promise."""

    def __init__(self, reason: PythonJSConvertedTypes) -> None:
        super().__init__(
            f"JavaScript rejected promise with reason: {_get_exception_msg(reason)}\n"
        )
        self.reason = reason


class JSArrayIndexError(IndexError, MiniRacerBaseException):
    """Invalid index into a JSArray."""

    def __init__(self) -> None:
        super().__init__("JSArray deletion out of range")


class JSObjectImpl(JSObject):
    """A JavaScript object."""

    def __init__(
        self,
        ctx: AbstractContext,
        handle: AbstractValueHandle,
    ):
        self._ctx = ctx
        self._handle = handle

    def __hash__(self) -> int:
        return self._ctx.get_identity_hash(self)

    @property
    def raw_handle(self) -> AbstractValueHandle:
        return self._handle


class JSMappedObject(
    JSObjectImpl,
    MutableMapping[PythonJSConvertedTypes, PythonJSConvertedTypes],
):
    """A JavaScript object with Pythonic MutableMapping methods (`keys()`,
    `__getitem__()`, etc).

    `keys()` and `__iter__()` will return properties from any prototypes as well as this
    object, as if using a for-in statement in JavaScript.
    """

    def __iter__(self) -> Iterator[PythonJSConvertedTypes]:
        return iter(self._get_own_property_names())

    def __getitem__(self, key: PythonJSConvertedTypes) -> PythonJSConvertedTypes:
        return self._ctx.get_object_item(self, key)

    def __setitem__(
        self, key: PythonJSConvertedTypes, val: PythonJSConvertedTypes
    ) -> None:
        self._ctx.set_object_item(self, key, val)

    def __delitem__(self, key: PythonJSConvertedTypes) -> None:
        self._ctx.del_object_item(self, key)

    def __len__(self) -> int:
        return len(self._get_own_property_names())

    def _get_own_property_names(self) -> tuple[PythonJSConvertedTypes, ...]:
        return self._ctx.get_own_property_names(self)


class JSArray(MutableSequence[PythonJSConvertedTypes], JSObjectImpl):
    """JavaScript array.

    Has Pythonic MutableSequence methods (e.g., `insert()`, `__getitem__()`, ...).
    """

    def __len__(self) -> int:
        ret = self._ctx.get_object_item(self, "length")
        return cast(int, ret)

    def __getitem__(self, index: int | slice) -> Any:
        if not isinstance(index, int):
            raise TypeError

        index = op_index(index)
        if index < 0:
            index += len(self)

        if 0 <= index < len(self):
            return self._ctx.get_object_item(self, index)

        raise IndexError

    def __setitem__(self, index: int | slice, val: Any) -> None:
        if not isinstance(index, int):
            raise TypeError

        self._ctx.set_object_item(self, index, val)

    def __delitem__(self, index: int | slice) -> None:
        if not isinstance(index, int):
            raise TypeError

        if index >= len(self) or index < -len(self):
            # JavaScript Array.prototype.splice() just ignores deletion beyond the
            # end of the array, meaning if you pass a very large value here it would
            # do nothing. Likewise, it just caps negative values at the length of the
            # array, meaning if you pass a very negative value here it would just
            # delete element 0.
            # For consistency with Python lists, let's tell the caller they're out of
            # bounds:
            raise JSArrayIndexError

        return self._ctx.del_from_array(self, index)

    def insert(self, index: int, new_obj: PythonJSConvertedTypes) -> None:
        return self._ctx.array_insert(self, index, new_obj)

    def __iter__(self) -> Iterator[PythonJSConvertedTypes]:
        for i in range(len(self)):
            yield self[i]


class JSFunction(JSMappedObject):
    """JavaScript function.

    You can call this object from Python, passing in positional args to match what the
    JavaScript function expects, along with a keyword argument, `timeout_sec`.
    """

    def __call__(
        self,
        *args: PythonJSConvertedTypes,
        this: JSObjectImpl | JSUndefinedType = JSUndefined,
        timeout_sec: Numeric | None = None,
    ) -> PythonJSConvertedTypes:
        return self._ctx.call_function(self, *args, this=this, timeout_sec=timeout_sec)


class JSSymbol(JSMappedObject):
    """JavaScript symbol."""


class JSPromise(JSObjectImpl):
    """JavaScript Promise.

    To get a value, call `promise.get()` to block, or `await promise` from within an
    `async` coroutine. Either will raise a Python exception if the JavaScript Promise
    is rejected.
    """

    def get(self, *, timeout: Numeric | None = None) -> PythonJSConvertedTypes:
        """Get the value, or raise an exception. This call blocks.

        Args:
            timeout: number of milliseconds after which the execution is interrupted.
                This is deprecated; use timeout_sec instead.
        """

        future = SyncFuture()

        def future_caller(value: Any) -> None:
            future.set_result(value)

        self._attach_callbacks_to_promise(future_caller)

        results = future.get(timeout=timeout)
        return self._unpack_promise_results(results)

    def __await__(self) -> Generator[Any, None, Any]:
        return self._do_await().__await__()

    async def _do_await(self) -> PythonJSConvertedTypes:
        loop = get_running_loop()
        future: Future[PythonJSConvertedTypes] = loop.create_future()

        def future_caller(value: Any) -> None:
            loop.call_soon_threadsafe(future.set_result, value)

        self._attach_callbacks_to_promise(future_caller)

        results = await future
        return self._unpack_promise_results(results)

    def _attach_callbacks_to_promise(
        self,
        future_caller: Callable[[Any], None],
    ) -> None:
        """Attach the given Python callbacks to a JS Promise."""

        exit_stack = ExitStack()

        def on_resolved_and_cleanup(
            value: PythonJSConvertedTypes | JSEvalException,
        ) -> None:
            exit_stack.__exit__(None, None, None)
            future_caller([False, cast(JSArray, value)])

        on_resolved_js_func = exit_stack.enter_context(
            self._ctx.js_callback(on_resolved_and_cleanup)
        )

        def on_rejected_and_cleanup(
            value: PythonJSConvertedTypes | JSEvalException,
        ) -> None:
            exit_stack.__exit__(None, None, None)
            future_caller([True, cast(JSArray, value)])

        on_rejected_js_func = exit_stack.enter_context(
            self._ctx.js_callback(on_rejected_and_cleanup)
        )

        self._ctx.promise_then(self, on_resolved_js_func, on_rejected_js_func)

    def _unpack_promise_results(self, results: Any) -> PythonJSConvertedTypes:
        is_rejected, argv = results
        result = cast(PythonJSConvertedTypes, cast(JSArray, argv)[0])
        if is_rejected:
            raise JSPromiseError(result)
        return result
