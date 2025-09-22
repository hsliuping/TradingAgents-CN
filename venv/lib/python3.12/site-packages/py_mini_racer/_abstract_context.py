from __future__ import annotations

from abc import ABC, abstractmethod
from typing import (
    TYPE_CHECKING,
    Callable,
)

from py_mini_racer._types import JSUndefined

if TYPE_CHECKING:
    from contextlib import AbstractContextManager

    from py_mini_racer._numeric import Numeric
    from py_mini_racer._objects import (
        JSArray,
        JSFunction,
        JSPromise,
    )
    from py_mini_racer._types import (
        JSEvalException,
        JSObject,
        JSUndefinedType,
        PythonJSConvertedTypes,
    )


class AbstractValueHandle(ABC):
    @property
    @abstractmethod
    def raw(self) -> object:
        pass

    @abstractmethod
    def to_python(self) -> PythonJSConvertedTypes | JSEvalException:
        pass

    @abstractmethod
    def to_python_or_raise(self) -> PythonJSConvertedTypes:
        pass


class AbstractContext(ABC):
    """A Context provides Pythonic wrappers around the MiniRacer C API.

    This is intended for internal usage by py_mini_racer. MiniRacerContext provides
    a further wrapper around this interface.
    """

    @abstractmethod
    def get_identity_hash(self, obj: JSObject) -> int:
        pass

    @abstractmethod
    def get_own_property_names(
        self, obj: JSObject
    ) -> tuple[PythonJSConvertedTypes, ...]:
        pass

    @abstractmethod
    def get_object_item(
        self, obj: JSObject, key: PythonJSConvertedTypes
    ) -> PythonJSConvertedTypes:
        pass

    @abstractmethod
    def set_object_item(
        self, obj: JSObject, key: PythonJSConvertedTypes, val: PythonJSConvertedTypes
    ) -> None:
        pass

    @abstractmethod
    def del_object_item(self, obj: JSObject, key: PythonJSConvertedTypes) -> None:
        pass

    @abstractmethod
    def del_from_array(self, arr: JSArray, index: int) -> None:
        pass

    @abstractmethod
    def array_insert(
        self, arr: JSArray, index: int, new_val: PythonJSConvertedTypes
    ) -> None:
        pass

    @abstractmethod
    def call_function(
        self,
        func: JSFunction,
        *args: PythonJSConvertedTypes,
        this: JSObject | JSUndefinedType = JSUndefined,
        timeout_sec: Numeric | None = None,
    ) -> PythonJSConvertedTypes:
        pass

    @abstractmethod
    def js_callback(
        self, func: Callable[[PythonJSConvertedTypes | JSEvalException], None]
    ) -> AbstractContextManager[JSFunction]:
        pass

    @abstractmethod
    def promise_then(
        self, promise: JSPromise, on_resolved: JSFunction, on_rejected: JSFunction
    ) -> None:
        pass

    @abstractmethod
    def create_intish_val(self, val: int, typ: int) -> AbstractValueHandle:
        pass

    @abstractmethod
    def create_doublish_val(self, val: float, typ: int) -> AbstractValueHandle:
        pass

    @abstractmethod
    def create_string_val(self, val: str, typ: int) -> AbstractValueHandle:
        pass

    @abstractmethod
    def free(self, val_handle: AbstractValueHandle) -> None:
        pass

    @abstractmethod
    def evaluate(
        self,
        code: str,
        timeout_sec: Numeric | None = None,
    ) -> PythonJSConvertedTypes:
        pass
