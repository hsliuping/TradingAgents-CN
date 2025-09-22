from typing import Any, Callable, Optional, Union

__version__: str

def packb(
    obj: Any,
    /,
    default: Optional[Callable[[Any], Any]] = ...,
    option: Optional[int] = None,
) -> bytes: ...
def unpackb(
    obj: Union[bytes, bytearray, memoryview],
    /,
    *,
    ext_hook: Optional[Callable[[int, bytes], Any]] = ...,
    option: Optional[int] = ...,
) -> Any: ...

class MsgpackDecodeError(ValueError): ...
class MsgpackEncodeError(TypeError): ...

class Ext:
    def __init__(self, tag: int, data: bytes) -> None: ...

OPT_DATETIME_AS_TIMESTAMP_EXT: int
OPT_NAIVE_UTC: int
OPT_OMIT_MICROSECONDS: int
OPT_PASSTHROUGH_BIG_INT: int
OPT_PASSTHROUGH_DATACLASS: int
OPT_PASSTHROUGH_DATETIME: int
OPT_PASSTHROUGH_ENUM: int
OPT_PASSTHROUGH_SUBCLASS: int
OPT_PASSTHROUGH_TUPLE: int
OPT_PASSTHROUGH_UUID: int
OPT_SERIALIZE_NUMPY: int
OPT_SERIALIZE_PYDANTIC: int
OPT_NON_STR_KEYS: int
OPT_SORT_KEYS: int
OPT_UTC_Z: int
