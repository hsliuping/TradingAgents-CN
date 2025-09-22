from __future__ import annotations

import ctypes
from datetime import datetime, timezone
from typing import (
    TYPE_CHECKING,
    ClassVar,
)

from py_mini_racer._abstract_context import AbstractContext, AbstractValueHandle
from py_mini_racer._objects import (
    JSArray,
    JSFunction,
    JSMappedObject,
    JSObjectImpl,
    JSPromise,
    JSSymbol,
)
from py_mini_racer._types import (
    JSEvalException,
    JSUndefined,
    MiniRacerBaseException,
    PythonJSConvertedTypes,
)


class _RawValueUnion(ctypes.Union):
    _fields_: ClassVar[list[tuple[str, object]]] = [
        ("value_ptr", ctypes.c_void_p),
        ("bytes_val", ctypes.POINTER(ctypes.c_char)),
        ("char_p_val", ctypes.c_char_p),
        ("int_val", ctypes.c_int64),
        ("double_val", ctypes.c_double),
    ]


class _RawValue(ctypes.Structure):
    _fields_: ClassVar[list[tuple[str, object]]] = [
        ("value", _RawValueUnion),
        ("len", ctypes.c_size_t),
        ("type", ctypes.c_uint8),
    ]
    _pack_ = 1


RawValueHandle = ctypes.POINTER(_RawValue)

if TYPE_CHECKING:
    RawValueHandleType = ctypes._Pointer[_RawValue]  # noqa: SLF001


class _ArrayBufferByte(ctypes.Structure):
    # Cannot use c_ubyte directly because it uses <B
    # as an internal type but we need B for memoryview.
    _fields_: ClassVar[list[tuple[str, object]]] = [
        ("b", ctypes.c_ubyte),
    ]
    _pack_ = 1


class JSParseException(JSEvalException):
    """JavaScript could not be parsed."""


class JSKeyError(JSEvalException, KeyError):
    """No such key found."""


class JSOOMException(JSEvalException):
    """JavaScript execution ran out of memory."""


class JSTerminatedException(JSEvalException):
    """JavaScript execution terminated."""


class JSValueError(JSEvalException, ValueError):
    """Bad value passed to JavaScript engine."""


class JSConversionException(MiniRacerBaseException):
    """Type could not be converted to or from JavaScript."""


class MiniRacerTypes:
    """MiniRacer types identifier

    Note: it needs to be coherent with mini_racer.cc.
    """

    invalid = 0
    null = 1
    bool = 2
    integer = 3
    double = 4
    str_utf8 = 5
    array = 6
    # deprecated:
    hash = 7
    date = 8
    symbol = 9
    object = 10
    undefined = 11

    function = 100
    shared_array_buffer = 101
    array_buffer = 102
    promise = 103

    execute_exception = 200
    parse_exception = 201
    oom_exception = 202
    timeout_exception = 203
    terminated_exception = 204
    value_exception = 205
    key_exception = 206


_ERRORS: dict[int, tuple[type[JSEvalException], str]] = {
    MiniRacerTypes.parse_exception: (
        JSParseException,
        "Unknown JavaScript error during parse",
    ),
    MiniRacerTypes.execute_exception: (
        JSEvalException,
        "Uknown JavaScript error during execution",
    ),
    MiniRacerTypes.oom_exception: (JSOOMException, "JavaScript memory limit reached"),
    MiniRacerTypes.terminated_exception: (
        JSTerminatedException,
        "JavaScript was terminated",
    ),
    MiniRacerTypes.key_exception: (
        JSKeyError,
        "No such key found in object",
    ),
    MiniRacerTypes.value_exception: (
        JSValueError,
        "Bad value passed to JavaScript engine",
    ),
}


class ValueHandle(AbstractValueHandle):
    """An object which holds open a Python reference to a _RawValue owned by
    a C++ MiniRacer context."""

    def __init__(self, ctx: AbstractContext, raw: RawValueHandleType):
        self.ctx = ctx
        self._raw = raw

    def __del__(self) -> None:
        self.ctx.free(self)

    @property
    def raw(self) -> RawValueHandleType:
        return self._raw

    def to_python_or_raise(self) -> PythonJSConvertedTypes:
        val = self.to_python()
        if isinstance(val, JSEvalException):
            raise val
        return val

    def to_python(self) -> PythonJSConvertedTypes | JSEvalException:
        """Convert a binary value handle from the C++ side into a Python object."""

        # A MiniRacer binary value handle is a pointer to a structure which, for some
        # simple types like ints, floats, and strings, is sufficient to describe the
        # data, enabling us to convert the value immediately and free the handle.

        # For more complex types, like Objects and Arrays, the handle is just an opaque
        # pointer to a V8 object. In these cases, we retain the binary value handle,
        # wrapping it in a Python object. We can then use the handle in follow-on API
        # calls to work with the underlying V8 object.

        # In either case the handle is owned by the C++ side. It's the responsibility
        # of the Python side to call mr_free_value() when done with with the handle
        # to free up memory, but the C++ side will eventually free it on context
        # teardown either way.

        typ = self._raw.contents.type
        val = self._raw.contents.value
        length = self._raw.contents.len

        error_info = _ERRORS.get(self._raw.contents.type)
        if error_info:
            klass, generic_msg = error_info

            msg = val.bytes_val[0:length].decode("utf-8")
            msg = msg or generic_msg

            return klass(msg)

        if typ == MiniRacerTypes.null:
            return None
        if typ == MiniRacerTypes.undefined:
            return JSUndefined
        if typ == MiniRacerTypes.bool:
            return bool(val.int_val == 1)
        if typ == MiniRacerTypes.integer:
            return int(val.int_val)
        if typ == MiniRacerTypes.double:
            return float(val.double_val)
        if typ == MiniRacerTypes.str_utf8:
            return str(val.bytes_val[0:length].decode("utf-8"))
        if typ == MiniRacerTypes.function:
            return JSFunction(self.ctx, self)
        if typ == MiniRacerTypes.date:
            timestamp = val.double_val
            # JS timestamps are milliseconds. In Python we are in seconds:
            return datetime.fromtimestamp(timestamp / 1000.0, timezone.utc)
        if typ == MiniRacerTypes.symbol:
            return JSSymbol(self.ctx, self)
        if typ in (MiniRacerTypes.shared_array_buffer, MiniRacerTypes.array_buffer):
            buf = _ArrayBufferByte * length
            cdata = buf.from_address(val.value_ptr)
            # Save a reference to ourselves to prevent garbage collection of the
            # backing store:
            cdata._origin = self  # noqa: SLF001
            result = memoryview(cdata)
            # Avoids "NotImplementedError: memoryview: unsupported format T{<B:b:}"
            # in Python 3.12:
            return result.cast("B")

        if typ == MiniRacerTypes.promise:
            return JSPromise(self.ctx, self)

        if typ == MiniRacerTypes.array:
            return JSArray(self.ctx, self)

        if typ == MiniRacerTypes.object:
            return JSMappedObject(self.ctx, self)

        raise JSConversionException


def python_to_value_handle(
    context: AbstractContext, obj: PythonJSConvertedTypes
) -> AbstractValueHandle:
    if isinstance(obj, JSObjectImpl):
        # JSObjects originate from the V8 side. We can just send back the handle
        # we originally got. (This also covers derived types JSFunction, JSSymbol,
        # JSPromise, and JSArray.)
        return obj.raw_handle

    if obj is None:
        return context.create_intish_val(0, MiniRacerTypes.null)
    if obj is JSUndefined:
        return context.create_intish_val(0, MiniRacerTypes.undefined)
    if isinstance(obj, bool):
        return context.create_intish_val(1 if obj else 0, MiniRacerTypes.bool)
    if isinstance(obj, int):
        if obj - 2**31 <= obj < 2**31:
            return context.create_intish_val(obj, MiniRacerTypes.integer)

        # We transmit ints as int32, so "upgrade" to double upon overflow.
        # (ECMAScript numeric is double anyway, but V8 does internally distinguish
        # int types, so we try and preserve integer-ness for round-tripping
        # purposes.)
        # JS BigInt would be a closer representation of Python int, but upgrading
        # to BigInt would probably be surprising for most applications, so for now,
        # we approximate with double:
        return context.create_doublish_val(obj, MiniRacerTypes.double)
    if isinstance(obj, float):
        return context.create_doublish_val(obj, MiniRacerTypes.double)
    if isinstance(obj, str):
        return context.create_string_val(obj, MiniRacerTypes.str_utf8)
    if isinstance(obj, datetime):
        # JS timestamps are milliseconds. In Python we are in seconds:
        return context.create_doublish_val(
            obj.timestamp() * 1000.0, MiniRacerTypes.date
        )

    # Note: we skip shared array buffers, so for now at least, handles to shared
    # array buffers can only be transmitted from JS to Python.

    raise JSConversionException
