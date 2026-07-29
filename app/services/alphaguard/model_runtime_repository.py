"""Create-only persistence for secret-free model runtime facts."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

from pydantic import BaseModel
from pymongo.errors import DuplicateKeyError

from app.models.alphaguard.model_runtime_collections import (
    MODEL_RUNTIME_COLLECTIONS,
    MODEL_RUNTIME_WRITE_COLLECTIONS,
)
from app.services.alphaguard.paper_storage import clean_document, to_mongo_value


class ModelRuntimeIntegrityConflict(RuntimeError):
    pass


def model_runtime_document(
    value: BaseModel | dict[str, Any],
) -> dict[str, Any]:
    raw = (
        value.model_dump(mode="python")
        if isinstance(value, BaseModel)
        else dict(value)
    )

    def convert(item: Any) -> Any:
        if isinstance(item, datetime):
            return item
        if isinstance(item, date):
            return datetime.combine(item, time.min)
        if isinstance(item, dict):
            return {
                str(key): convert(child)
                for key, child in item.items()
                if key != "_id"
            }
        if isinstance(item, (list, tuple)):
            return [convert(child) for child in item]
        return to_mongo_value(item)

    return convert(raw)


class ModelRuntimeRepository:
    def __init__(self, db):
        self.db = db

    @staticmethod
    def collection_name(name: str) -> str:
        collection = MODEL_RUNTIME_COLLECTIONS[name]
        if collection not in MODEL_RUNTIME_WRITE_COLLECTIONS:
            raise RuntimeError("model runtime escaped ag_model_* boundary")
        return collection

    async def get(
        self, name: str, query: dict[str, Any]
    ) -> dict[str, Any] | None:
        return clean_document(
            await self.db[self.collection_name(name)].find_one(query)
        )

    async def list(
        self,
        name: str,
        query: dict[str, Any] | None = None,
        *,
        sort: tuple[str, int] | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        cursor = self.db[self.collection_name(name)].find(query or {})
        if sort:
            cursor = cursor.sort(*sort)
        if limit:
            cursor = cursor.limit(limit)
        return [
            clean_document(item)
            for item in await cursor.to_list(length=limit)
        ]

    async def save_immutable(
        self,
        name: str,
        model: BaseModel,
        *,
        identity: dict[str, Any],
        hash_field: str,
    ) -> tuple[BaseModel, bool]:
        collection = self.db[self.collection_name(name)]
        existing = clean_document(await collection.find_one(identity))
        if existing is not None:
            if existing.get(hash_field) != getattr(model, hash_field):
                raise ModelRuntimeIntegrityConflict(
                    f"immutable {name} identity has conflicting content"
                )
            return type(model).model_validate(existing), False
        try:
            await collection.insert_one(model_runtime_document(model))
            return model, True
        except DuplicateKeyError:
            # Concurrent create-only requests may race after the initial read.
            # Re-read the exact identity and accept only byte-equivalent
            # immutable content; a different hash remains a hard conflict.
            existing = clean_document(await collection.find_one(identity))
            if (
                existing is not None
                and existing.get(hash_field) == getattr(model, hash_field)
            ):
                return type(model).model_validate(existing), False
            raise ModelRuntimeIntegrityConflict(
                f"immutable {name} identity conflicted during concurrent create"
            )
