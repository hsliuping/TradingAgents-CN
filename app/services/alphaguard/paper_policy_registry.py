"""Versioned, create-only account, execution and fee policies."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.services.alphaguard.paper_storage import clean_document, model_document
from tradingagents.alphaguard.paper_schemas import (
    AccountPolicy,
    ExecutionPolicy,
    FeePolicy,
    paper_canonical_hash,
)


POLICY_ROOT = (
    Path(__file__).resolve().parents[3]
    / "config"
    / "alphaguard"
    / "paper"
)
POLICY_FILES = {
    "ACCOUNT": POLICY_ROOT / "account_policy_v1.yaml",
    "EXECUTION": POLICY_ROOT / "execution_policy_v1.yaml",
    "FEE": POLICY_ROOT / "fee_policy_v1.yaml",
}


class PaperPolicyConflictError(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"invalid paper policy: {path}")
    payload["config_hash"] = paper_canonical_hash(payload)
    return payload


def builtin_account_policy() -> AccountPolicy:
    return AccountPolicy.model_validate(_load(POLICY_FILES["ACCOUNT"]))


def builtin_execution_policy() -> ExecutionPolicy:
    return ExecutionPolicy.model_validate(_load(POLICY_FILES["EXECUTION"]))


def builtin_fee_policy() -> FeePolicy:
    return FeePolicy.model_validate(_load(POLICY_FILES["FEE"]))


class PaperPolicyRegistry:
    def __init__(self, db):
        self.db = db
        self.collection = db["ag_paper_policies"]

    async def register_builtins(self) -> dict[str, str]:
        results: dict[str, str] = {}
        for policy_type, policy in (
            ("ACCOUNT", builtin_account_policy()),
            ("EXECUTION", builtin_execution_policy()),
            ("FEE", builtin_fee_policy()),
        ):
            identity = {
                "policy_type": policy_type,
                "version": policy.version,
            }
            existing = clean_document(await self.collection.find_one(identity))
            if existing:
                existing.pop("policy_type", None)
                expected_type = type(policy)
                stored = expected_type.model_validate(existing)
                if stored.config_hash != policy.config_hash:
                    raise PaperPolicyConflictError(
                        f"same {policy_type} policy version has different content"
                    )
                results[policy_type] = "reused"
                continue
            document = model_document(policy)
            document["policy_type"] = policy_type
            await self.collection.insert_one(document)
            results[policy_type] = "created"
        return results

    async def account_policy(self) -> AccountPolicy:
        return await self._get(
            "ACCOUNT",
            builtin_account_policy(),
        )

    async def execution_policy(self) -> ExecutionPolicy:
        return await self._get(
            "EXECUTION",
            builtin_execution_policy(),
        )

    async def fee_policy(self) -> FeePolicy:
        return await self._get(
            "FEE",
            builtin_fee_policy(),
        )

    async def _get(self, policy_type: str, builtin):
        document = clean_document(
            await self.collection.find_one(
                {"policy_type": policy_type, "version": builtin.version}
            )
        )
        if document is None:
            raise LookupError(f"{policy_type} paper policy is not registered")
        document.pop("policy_type", None)
        stored = type(builtin).model_validate(document)
        if stored.config_hash != builtin.config_hash:
            raise PaperPolicyConflictError(
                f"stored {policy_type} paper policy hash mismatch"
            )
        return stored
