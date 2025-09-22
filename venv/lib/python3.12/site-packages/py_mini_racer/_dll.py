from __future__ import annotations

import ctypes
import sys
from contextlib import ExitStack, contextmanager
from importlib import resources
from os.path import exists
from os.path import join as pathjoin
from sys import platform, version_info
from threading import Lock
from typing import (
    Iterable,
    Iterator,
)

from py_mini_racer._types import (
    MiniRacerBaseException,
)
from py_mini_racer._value_handle import (
    RawValueHandle,
)


def _get_lib_filename(name: str) -> str:
    """Return the path of the library called `name` on the current system."""
    if platform == "darwin":
        prefix, ext = "lib", ".dylib"
    elif platform == "win32":
        prefix, ext = "", ".dll"
    else:
        prefix, ext = "lib", ".so"

    return prefix + name + ext


MR_CALLBACK = ctypes.CFUNCTYPE(None, ctypes.c_uint64, RawValueHandle)


def _build_dll_handle(dll_path: str) -> ctypes.CDLL:
    handle = ctypes.CDLL(dll_path)

    handle.mr_init_v8.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p]

    handle.mr_init_context.argtypes = [MR_CALLBACK]
    handle.mr_init_context.restype = ctypes.c_uint64

    handle.mr_eval.argtypes = [
        ctypes.c_uint64,
        RawValueHandle,
        ctypes.c_uint64,
    ]
    handle.mr_eval.restype = ctypes.c_uint64

    handle.mr_free_value.argtypes = [ctypes.c_uint64, RawValueHandle]

    handle.mr_alloc_int_val.argtypes = [ctypes.c_uint64, ctypes.c_int64, ctypes.c_uint8]
    handle.mr_alloc_int_val.restype = RawValueHandle

    handle.mr_alloc_double_val.argtypes = [
        ctypes.c_uint64,
        ctypes.c_double,
        ctypes.c_uint8,
    ]
    handle.mr_alloc_double_val.restype = RawValueHandle

    handle.mr_alloc_string_val.argtypes = [
        ctypes.c_uint64,
        ctypes.c_char_p,
        ctypes.c_uint64,
        ctypes.c_uint8,
    ]
    handle.mr_alloc_string_val.restype = RawValueHandle

    handle.mr_free_context.argtypes = [ctypes.c_uint64]

    handle.mr_context_count.argtypes = []
    handle.mr_context_count.restype = ctypes.c_size_t

    handle.mr_cancel_task.argtypes = [ctypes.c_uint64, ctypes.c_uint64]

    handle.mr_heap_stats.argtypes = [
        ctypes.c_uint64,
        ctypes.c_uint64,
    ]
    handle.mr_heap_stats.restype = ctypes.c_uint64

    handle.mr_low_memory_notification.argtypes = [ctypes.c_uint64]

    handle.mr_make_js_callback.argtypes = [
        ctypes.c_uint64,
        ctypes.c_uint64,
    ]
    handle.mr_make_js_callback.restype = RawValueHandle

    handle.mr_heap_snapshot.argtypes = [
        ctypes.c_uint64,
        ctypes.c_uint64,
    ]
    handle.mr_heap_snapshot.restype = ctypes.c_uint64

    handle.mr_get_identity_hash.argtypes = [
        ctypes.c_uint64,
        RawValueHandle,
    ]
    handle.mr_get_identity_hash.restype = RawValueHandle

    handle.mr_get_own_property_names.argtypes = [
        ctypes.c_uint64,
        RawValueHandle,
    ]
    handle.mr_get_own_property_names.restype = RawValueHandle

    handle.mr_get_object_item.argtypes = [
        ctypes.c_uint64,
        RawValueHandle,
        RawValueHandle,
    ]
    handle.mr_get_object_item.restype = RawValueHandle

    handle.mr_set_object_item.argtypes = [
        ctypes.c_uint64,
        RawValueHandle,
        RawValueHandle,
        RawValueHandle,
    ]
    handle.mr_set_object_item.restype = RawValueHandle

    handle.mr_del_object_item.argtypes = [
        ctypes.c_uint64,
        RawValueHandle,
        RawValueHandle,
    ]
    handle.mr_del_object_item.restype = RawValueHandle

    handle.mr_splice_array.argtypes = [
        ctypes.c_uint64,
        RawValueHandle,
        ctypes.c_int32,
        ctypes.c_int32,
        RawValueHandle,
    ]
    handle.mr_splice_array.restype = RawValueHandle

    handle.mr_call_function.argtypes = [
        ctypes.c_uint64,
        RawValueHandle,
        RawValueHandle,
        RawValueHandle,
        ctypes.c_uint64,
    ]
    handle.mr_call_function.restype = ctypes.c_uint64

    handle.mr_set_hard_memory_limit.argtypes = [ctypes.c_uint64, ctypes.c_size_t]

    handle.mr_set_soft_memory_limit.argtypes = [ctypes.c_uint64, ctypes.c_size_t]
    handle.mr_set_soft_memory_limit.restype = None

    handle.mr_hard_memory_limit_reached.argtypes = [ctypes.c_uint64]
    handle.mr_hard_memory_limit_reached.restype = ctypes.c_bool

    handle.mr_soft_memory_limit_reached.argtypes = [ctypes.c_uint64]
    handle.mr_soft_memory_limit_reached.restype = ctypes.c_bool

    handle.mr_v8_version.argtypes = []
    handle.mr_v8_version.restype = ctypes.c_char_p

    handle.mr_v8_is_using_sandbox.argtypes = []
    handle.mr_v8_is_using_sandbox.restype = ctypes.c_bool

    handle.mr_value_count.argtypes = [ctypes.c_uint64]
    handle.mr_value_count.restype = ctypes.c_size_t

    return handle


# V8 internationalization data:
_ICU_DATA_FILENAME = "icudtl.dat"

# V8 fast-startup snapshot; a dump of the heap after loading built-in JS
# modules:
_SNAPSHOT_FILENAME = "snapshot_blob.bin"

DEFAULT_V8_FLAGS = ("--single-threaded",)


class LibNotFoundError(MiniRacerBaseException):
    """MiniRacer-wrapped V8 build not found."""

    def __init__(self, path: str):
        super().__init__(f"Native library or dependency not available at {path}")


class LibAlreadyInitializedError(MiniRacerBaseException):
    """MiniRacer-wrapped V8 build not found."""

    def __init__(self) -> None:
        super().__init__(
            "MiniRacer was already initialized before the call to init_mini_racer"
        )


def _open_resource_file(filename: str, exit_stack: ExitStack) -> str:
    if version_info >= (3, 9):
        # resources.as_file was added in Python 3.9
        resource_path = resources.files("py_mini_racer") / filename

        context_manager = resources.as_file(resource_path)
    else:
        # now-deprecated API for Pythons older than 3.9
        context_manager = resources.path("py_mini_racer", filename)

    return str(exit_stack.enter_context(context_manager))


def _check_path(path: str) -> None:
    if path is None or not exists(path):
        raise LibNotFoundError(path)


@contextmanager
def _open_dll(flags: Iterable[str]) -> Iterator[ctypes.CDLL]:
    dll_filename = _get_lib_filename("mini_racer")

    with ExitStack() as exit_stack:
        # Find the dll and its external dependency files:
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass is not None:
            # We are running under PyInstaller
            dll_path = pathjoin(meipass, dll_filename)
            icu_data_path = pathjoin(meipass, _ICU_DATA_FILENAME)
            snapshot_path = pathjoin(meipass, _SNAPSHOT_FILENAME)
        else:
            dll_path = _open_resource_file(dll_filename, exit_stack)
            icu_data_path = _open_resource_file(_ICU_DATA_FILENAME, exit_stack)
            snapshot_path = _open_resource_file(_SNAPSHOT_FILENAME, exit_stack)

        _check_path(dll_path)
        _check_path(icu_data_path)
        _check_path(snapshot_path)

        handle = _build_dll_handle(dll_path)

        handle.mr_init_v8(
            " ".join(flags).encode("utf-8"),
            icu_data_path.encode("utf-8"),
            snapshot_path.encode("utf-8"),
        )

        yield handle


_init_lock = Lock()
_dll_handle_context_manager = None
_dll_handle = None


def init_mini_racer(
    *, flags: Iterable[str] = DEFAULT_V8_FLAGS, ignore_duplicate_init: bool = False
) -> ctypes.CDLL:
    """Initialize py_mini_racer (and V8).

    This function can optionally be used to set V8 flags. This function can be called
    at most once, before any instances of MiniRacer are initialized. Instances of
    MiniRacer will automatically call this function to initialize MiniRacer and V8.
    """

    global _dll_handle_context_manager  # noqa: PLW0603
    global _dll_handle  # noqa: PLW0603

    with _init_lock:
        if _dll_handle is None:
            _dll_handle_context_manager = _open_dll(flags)
            _dll_handle = _dll_handle_context_manager.__enter__()
            # Note: we never call _dll_handle_context_manager.__exit__() because it's
            # designed as a singleton. But we could if we wanted to!
        elif not ignore_duplicate_init:
            raise LibAlreadyInitializedError

        return _dll_handle
