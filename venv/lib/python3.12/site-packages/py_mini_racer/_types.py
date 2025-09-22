"""Declarations for Python renderings of basic JavaScript types."""

from __future__ import annotations

from datetime import datetime
from typing import (
    Union,
)


class JSUndefinedType:
    """The JavaScript undefined type.

    Where JavaScript null is represented as None, undefined is represented as this
    type."""

    def __bool__(self) -> bool:
        return False

    def __repr__(self) -> str:
        return "JSUndefined"


JSUndefined = JSUndefinedType()


class JSObject:
    pass


PythonJSConvertedTypes = Union[
    None,
    JSUndefinedType,
    bool,
    int,
    float,
    str,
    JSObject,
    datetime,
    memoryview,
]


class MiniRacerBaseException(Exception):  # noqa: N818
    """Base MiniRacer exception."""


class JSEvalException(MiniRacerBaseException):
    """JavaScript could not be executed."""


class JSTimeoutException(JSEvalException):
    """JavaScript execution timed out."""

    def __init__(self) -> None:
        super().__init__("JavaScript was terminated by timeout")
