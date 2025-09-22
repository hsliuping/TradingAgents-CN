from __future__ import annotations

from collections.abc import Iterable
from io import BufferedReader
from typing import Union

MultipartPart = tuple[
    str, tuple[None, Union[bytes, BufferedReader], str, dict[str, str]]
]


class MultipartPartsAndContext:
    parts: list[MultipartPart]
    context: str

    __slots__ = ("parts", "context")

    def __init__(self, parts: list[MultipartPart], context: str) -> None:
        self.parts = parts
        self.context = context


def join_multipart_parts_and_context(
    parts_and_contexts: Iterable[MultipartPartsAndContext],
) -> MultipartPartsAndContext:
    acc_parts: list[MultipartPart] = []
    acc_context: list[str] = []
    for parts_and_context in parts_and_contexts:
        acc_parts.extend(parts_and_context.parts)
        acc_context.append(parts_and_context.context)
    return MultipartPartsAndContext(acc_parts, "; ".join(acc_context))
