"""Load and create-only persist versioned hard-risk policy records."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import yaml

from app.schemas.alphaguard.decision import RiskPolicy, canonical_hash


POLICY_PATH = (
    Path(__file__).resolve().parents[3]
    / "config"
    / "alphaguard"
    / "risk"
    / "risk_policy_v1.yaml"
)


def builtin_risk_policy() -> RiskPolicy:
    payload = yaml.safe_load(POLICY_PATH.read_text(encoding="utf-8"))
    payload["config_hash"] = canonical_hash(payload)
    payload["created_at"] = datetime.utcnow()
    return RiskPolicy.model_validate(payload)


class RiskPolicyConflictError(ValueError):
    pass


class RiskPolicyRegistry:
    def __init__(self, db):
        self.db = db

    async def register_builtin(self) -> RiskPolicy:
        policy = builtin_risk_policy()
        identity = {
            "risk_policy_id": policy.risk_policy_id,
            "version": policy.version,
        }
        existing = await self.db["ag_risk_policies"].find_one(identity)
        if existing:
            existing.pop("_id", None)
            stored = RiskPolicy.model_validate(existing)
            if stored.config_hash != policy.config_hash:
                raise RiskPolicyConflictError(
                    "same RiskPolicy identity has different content"
                )
            return stored
        await self.db["ag_risk_policies"].insert_one(
            policy.model_dump(mode="python")
        )
        return policy

    async def get_active(self) -> RiskPolicy:
        document = await self.db["ag_risk_policies"].find_one(
            {"risk_policy_id": "risk-policy-v1", "status": "ACTIVE"}
        )
        if document is None:
            raise LookupError("active risk-policy-v1 is not registered")
        document.pop("_id", None)
        policy = RiskPolicy.model_validate(document)
        expected = builtin_risk_policy()
        if policy.config_hash != expected.config_hash:
            raise RiskPolicyConflictError("stored risk-policy-v1 hash mismatch")
        return policy
