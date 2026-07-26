"""The only write boundary for PR-007 evaluation collections."""

from __future__ import annotations

from typing import Any

from app.models.alphaguard.evaluation_collections import EVALUATION_COLLECTIONS
from app.services.alphaguard.paper_storage import clean_document
from pydantic import BaseModel


PRODUCTION_COLLECTION_PREFIXES = (
    "ag_paper_",
    "ag_order_",
    "ag_execution_",
    "ag_settlement_",
)


class EvaluationIntegrityConflict(ValueError):
    pass


class EvaluationRepository:
    """Create-only analytical persistence.

    The repository intentionally has no update/delete method for completed
    analytical facts.  EvaluationRun is the one journal with mutable status.
    """

    def __init__(self, db):
        self.db = db

    @staticmethod
    def _collection(name: str) -> str:
        collection = EVALUATION_COLLECTIONS[name]
        if not collection.startswith("ag_eval_"):
            raise RuntimeError("evaluation repository escaped ag_eval_* boundary")
        return collection

    async def save_immutable(
        self,
        name: str,
        model: BaseModel,
        *,
        identity: dict[str, Any],
        hash_field: str = "input_hash",
    ) -> tuple[BaseModel, bool]:
        collection = self.db[self._collection(name)]
        existing = clean_document(await collection.find_one(identity))
        if existing is not None:
            expected = getattr(model, hash_field, None)
            actual = existing.get(hash_field)
            if expected is None and hash_field == "immutable_hash":
                expected = getattr(model, "immutable_hash")
            if actual != expected:
                raise EvaluationIntegrityConflict(
                    f"immutable {name} identity has conflicting content"
                )
            return type(model).model_validate(existing), False
        await collection.insert_one(model.model_dump(mode="python"))
        return model, True

    async def append_override(self, model: BaseModel) -> BaseModel:
        collection = self.db[self._collection("attribution_overrides")]
        existing = await collection.find_one({"override_id": model.override_id})
        if existing is not None:
            raise EvaluationIntegrityConflict("AttributionOverride is append-only")
        await collection.insert_one(model.model_dump(mode="python"))
        return model

    async def save_horizon_label(self, model: BaseModel) -> tuple[BaseModel, bool]:
        identity = {
            "subject_id": model.subject_id,
            "horizon": model.horizon,
            "anchor_type": model.anchor_type,
            "calculation_version": model.calculation_version,
        }
        collection = self.db[self._collection("horizon_labels")]
        existing = clean_document(await collection.find_one(identity))
        if existing is None:
            await collection.insert_one(model.model_dump(mode="python"))
            return model, True
        stored = type(model).model_validate(existing)
        if stored.status == "PENDING" and model.status != "PENDING":
            # PENDING is scheduling state, not a completed historical fact.
            # The terminal label replaces it exactly once; terminal labels are
            # immutable thereafter.
            await collection.replace_one(
                identity,
                model.model_dump(mode="python"),
            )
            return model, True
        if stored.input_hash != model.input_hash:
            raise EvaluationIntegrityConflict(
                "completed HorizonLabel identity has conflicting content"
            )
        return stored, False

    async def save_counterfactual(self, model: BaseModel) -> tuple[BaseModel, bool]:
        identity = {
            "subject_id": model.subject_id,
            "mode": model.mode,
            "execution_rule_version": model.execution_rule_version,
        }
        collection = self.db[self._collection("counterfactuals")]
        existing = clean_document(await collection.find_one(identity))
        if existing is None:
            await collection.insert_one(model.model_dump(mode="python"))
            return model, True
        stored = type(model).model_validate(existing)
        if stored.status == "PENDING" and model.status != "PENDING":
            await collection.replace_one(identity, model.model_dump(mode="python"))
            return model, True
        if stored.input_hash != model.input_hash:
            raise EvaluationIntegrityConflict(
                "completed Counterfactual identity has conflicting content"
            )
        return stored, False

    async def save_attribution(self, model: BaseModel) -> tuple[BaseModel, bool]:
        identity = {
            "subject_id": model.subject_id,
            "attribution_rule_version": model.attribution_rule_version,
        }
        collection = self.db[self._collection("attributions")]
        existing = clean_document(await collection.find_one(identity))
        if existing is None:
            await collection.insert_one(model.model_dump(mode="python"))
            return model, True
        stored = type(model).model_validate(existing)
        if stored.status == "PENDING_HORIZON" and model.status != "PENDING_HORIZON":
            await collection.replace_one(identity, model.model_dump(mode="python"))
            return model, True
        if stored.input_hash != model.input_hash:
            raise EvaluationIntegrityConflict(
                "completed Attribution identity has conflicting content"
            )
        return stored, False

    async def pending_candidate_count(self, candidate_id: str) -> int:
        subjects = await self.db[self._collection("subjects")].find(
            {"candidate_id": candidate_id}
        ).to_list(length=None)
        subject_ids = [item["subject_id"] for item in subjects]
        if not subject_ids:
            return 0
        count = 0
        labels = await self.db[self._collection("horizon_labels")].find(
            {"subject_id": {"$in": subject_ids}, "status": "PENDING"}
        ).to_list(length=None)
        count += len(labels)
        counterfactuals = await self.db[self._collection("counterfactuals")].find(
            {"subject_id": {"$in": subject_ids}, "status": "PENDING"}
        ).to_list(length=None)
        count += len(counterfactuals)
        attributions = await self.db[self._collection("attributions")].find(
            {"subject_id": {"$in": subject_ids}, "status": "PENDING_HORIZON"}
        ).to_list(length=None)
        return count + len(attributions)
