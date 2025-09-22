"""Stubs for orjson operations, compatible with PyPy via a json fallback."""

try:
    from orjson import (
        OPT_NON_STR_KEYS,
        OPT_SERIALIZE_DATACLASS,
        OPT_SERIALIZE_NUMPY,
        OPT_SERIALIZE_UUID,
        Fragment,
        JSONDecodeError,
        dumps,
        loads,
    )

except ImportError:
    import dataclasses
    import json
    import uuid
    from typing import Any, Callable, Optional

    OPT_NON_STR_KEYS = 1
    OPT_SERIALIZE_DATACLASS = 2
    OPT_SERIALIZE_NUMPY = 4
    OPT_SERIALIZE_UUID = 8

    class Fragment:  # type: ignore
        def __init__(self, payloadb: bytes):
            self.payloadb = payloadb

    from json import JSONDecodeError  # type: ignore

    def dumps(  # type: ignore
        obj: Any,
        /,
        default: Optional[Callable[[Any], Any]] = None,
        option: int = 0,
    ) -> bytes:  # type: ignore
        # for now, don't do anything for this case because `json.dumps`
        # automatically encodes non-str keys as str by default, unlike orjson
        # enable_non_str_keys = bool(option & OPT_NON_STR_KEYS)

        enable_serialize_numpy = bool(option & OPT_SERIALIZE_NUMPY)
        enable_serialize_dataclass = bool(option & OPT_SERIALIZE_DATACLASS)
        enable_serialize_uuid = bool(option & OPT_SERIALIZE_UUID)

        class CustomEncoder(json.JSONEncoder):  # type: ignore
            def encode(self, o: Any) -> str:
                if isinstance(o, Fragment):
                    return o.payloadb.decode("utf-8")  # type: ignore
                return super().encode(o)

            def default(self, o: Any) -> Any:
                if enable_serialize_uuid and isinstance(o, uuid.UUID):
                    return str(o)
                if enable_serialize_numpy and hasattr(o, "tolist"):
                    # even objects like np.uint16(15) have a .tolist() function
                    return o.tolist()
                if (
                    enable_serialize_dataclass
                    and dataclasses.is_dataclass(o)
                    and not isinstance(o, type)
                ):
                    return dataclasses.asdict(o)
                if default is not None:
                    return default(o)

                return super().default(o)

        return json.dumps(obj, cls=CustomEncoder).encode("utf-8")

    def loads(payload: bytes, /) -> Any:  # type: ignore
        return json.loads(payload)


__all__ = [
    "loads",
    "dumps",
    "Fragment",
    "JSONDecodeError",
    "OPT_SERIALIZE_NUMPY",
    "OPT_SERIALIZE_DATACLASS",
    "OPT_SERIALIZE_UUID",
    "OPT_NON_STR_KEYS",
]
