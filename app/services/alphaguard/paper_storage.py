"""BSON-safe Decimal persistence helpers for PR-006 paper collections."""

from __future__ import annotations

from decimal import Decimal
from enum import Enum
import re
from typing import Any

from bson import Decimal128
from pydantic import BaseModel


def to_mongo_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return to_mongo_value(value.model_dump(mode="python"))
    if isinstance(value, Decimal):
        return Decimal128(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {
            str(key): to_mongo_value(item)
            for key, item in value.items()
            if key != "_id"
        }
    if isinstance(value, (list, tuple)):
        return [to_mongo_value(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return [to_mongo_value(item) for item in sorted(value)]
    return value


def from_mongo_value(value: Any) -> Any:
    if isinstance(value, Decimal128):
        return value.to_decimal()
    if isinstance(value, dict):
        return {
            key: from_mongo_value(item)
            for key, item in value.items()
            if key != "_id"
        }
    if isinstance(value, list):
        return [from_mongo_value(item) for item in value]
    return value


def model_document(model: BaseModel) -> dict[str, Any]:
    return to_mongo_value(model.model_dump(mode="python"))


def clean_document(document: dict[str, Any] | None) -> dict[str, Any] | None:
    if document is None:
        return None
    return from_mongo_value(document)


def safe_error_message(error: Exception, *, limit: int = 500) -> str:
    """Retain error class/context while removing common credential forms."""

    message = f"{type(error).__name__}: {str(error)[:limit]}"
    message = re.sub(
        r"(?i)\bauthorization\s*[:=]\s*(?:bearer\s+)?[^\s,;]+",
        "Authorization=[REDACTED]",
        message,
    )
    message = re.sub(
        r"(?i)\b(api[_-]?key|password|secret|token)"
        r"\s*[:=]\s*([^\s,;]+)",
        r"\1=[REDACTED]",
        message,
    )
    return re.sub(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+", "Bearer [REDACTED]", message)
