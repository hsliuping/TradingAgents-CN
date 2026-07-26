"""Persistence boundary for PR-008 experiment-only facts."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

from pydantic import BaseModel

from app.models.alphaguard.experiment_collections import (
    EXPERIMENT_COLLECTIONS,
    EXPERIMENT_WRITE_COLLECTIONS,
)
from app.services.alphaguard.paper_storage import clean_document, to_mongo_value


class ExperimentIntegrityConflict(RuntimeError):
    pass


def experiment_document(value: BaseModel | dict[str, Any]) -> dict[str, Any]:
    """Convert PR-008 models to BSON without losing datetime ordering."""

    raw = (
        value.model_dump(mode="python")
        if isinstance(value, BaseModel)
        else value
    )

    def convert(item):
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


class ExperimentRepository:
    def __init__(self, db):
        self.db = db

    @staticmethod
    def collection_name(name: str) -> str:
        collection = EXPERIMENT_COLLECTIONS[name]
        if collection not in EXPERIMENT_WRITE_COLLECTIONS:
            raise RuntimeError("experiment repository escaped ag_exp_* boundary")
        return collection

    async def get(self, name: str, query: dict[str, Any]) -> dict[str, Any] | None:
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
        if limit is not None:
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
                raise ExperimentIntegrityConflict(
                    f"immutable {name} identity has conflicting content"
                )
            return type(model).model_validate(existing), False
        await collection.insert_one(experiment_document(model))
        return model, True

    async def insert_once(
        self,
        name: str,
        model: BaseModel,
        *,
        identity: dict[str, Any],
    ) -> tuple[BaseModel, bool]:
        collection = self.db[self.collection_name(name)]
        existing = clean_document(await collection.find_one(identity))
        if existing is not None:
            return type(model).model_validate(existing), False
        await collection.insert_one(experiment_document(model))
        return model, True

    async def replace_state(
        self,
        name: str,
        *,
        identity: dict[str, Any],
        expected: dict[str, Any],
        model: BaseModel,
    ) -> BaseModel:
        collection = self.db[self.collection_name(name)]
        result = await collection.replace_one(
            {**identity, **expected},
            experiment_document(model),
        )
        if result.matched_count != 1:
            raise ExperimentIntegrityConflict(
                f"{name} state changed concurrently or does not exist"
            )
        return model
