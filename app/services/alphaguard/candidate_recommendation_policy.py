"""Versioned policy registry for governed candidate recommendations."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path

import yaml

from app.services.alphaguard.paper_storage import clean_document, model_document
from tradingagents.alphaguard.recommendation_schemas import (
    CandidateRecommendationPolicy,
    recommendation_hash,
)


_POLICY_PATH = (
    Path(__file__).resolve().parents[3]
    / "config"
    / "alphaguard"
    / "recommendations"
    / "candidate_recommendation_v2.yaml"
)


class RecommendationPolicyConflict(RuntimeError):
    pass


def builtin_candidate_recommendation_policy() -> CandidateRecommendationPolicy:
    with _POLICY_PATH.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    eligibility = raw.pop("eligibility")
    payload = {
        **raw,
        **eligibility,
        "factor_weights": {
            key: Decimal(str(value)) for key, value in raw["factor_weights"].items()
        },
        "risk_penalties": {
            key: Decimal(str(value)) for key, value in raw["risk_penalties"].items()
        },
        "minimum_average_amount": Decimal(str(eligibility["minimum_average_amount"])),
        "minimum_recommendation_score": Decimal(
            str(raw["minimum_recommendation_score"])
        ),
        "score_change_breaks_cooldown": Decimal(
            str(raw["score_change_breaks_cooldown"])
        ),
        "created_at": datetime(2026, 8, 2),
    }
    payload["config_hash"] = recommendation_hash(
        payload,
        exclude={"config_hash", "created_at", "schema_version"},
    )
    return CandidateRecommendationPolicy.model_validate(payload)


class CandidateRecommendationPolicyRegistry:
    COLLECTION = "ag_candidate_recommendation_policies"

    def __init__(self, db):
        self.db = db

    async def get_active(
        self, *, persist_if_missing: bool = True
    ) -> CandidateRecommendationPolicy:
        expected = builtin_candidate_recommendation_policy()
        existing = clean_document(
            await self.db[self.COLLECTION].find_one(
                {
                    "policy_id": expected.policy_id,
                    "policy_version": expected.policy_version,
                }
            )
        )
        if existing:
            stored = CandidateRecommendationPolicy.model_validate(existing)
            if stored.config_hash != expected.config_hash:
                raise RecommendationPolicyConflict(
                    "candidate recommendation policy identity changed content"
                )
            return stored
        if not persist_if_missing:
            return expected
        await self.db[self.COLLECTION].insert_one(model_document(expected))
        return expected
