"""Immutable FactorDefinition registry backed by versioned YAML."""

from __future__ import annotations

from datetime import datetime

from app.schemas.alphaguard import FactorDefinition

from .quant_audit_service import QuantAuditService
from .quant_config import FACTOR_ENGINE_CODE_VERSION, factor_config, sha256_value


class DefinitionConflictError(RuntimeError):
    pass


def builtin_factor_definitions() -> tuple[str, list[FactorDefinition], float]:
    config = factor_config()
    definitions: list[FactorDefinition] = []
    for item in config["factors"]:
        parameters = {
            key: value
            for key, value in item.items()
            if key
            not in {
                "factor_id",
                "factor_version",
                "name",
                "group",
                "formula",
                "inputs",
                "lookback",
            }
        }
        definitions.append(
            FactorDefinition(
                factor_id=item["factor_id"],
                factor_version=item["factor_version"],
                name=item["name"],
                group=item["group"],
                description=f"Deterministic {item['name']} factor.",
                formula_description=item["formula"],
                required_inputs=item["inputs"],
                lookback_trading_days=item["lookback"],
                missing_policy=(
                    "Return raw_value=null, normalized_score=null, direction=UNKNOWN, "
                    "confidence=0 and an explicit missing_reason."
                ),
                normalization_method=item["normalization"],
                score_semantics=(
                    "Higher means higher risk"
                    if item["group"] in {"VOLATILITY_RISK", "EVENT_RISK"}
                    else "Higher means stronger or more attractive"
                ),
                parameters=parameters,
                code_hash=sha256_value(
                    {
                        "engine": FACTOR_ENGINE_CODE_VERSION,
                        "factor_id": item["factor_id"],
                        "formula": item["formula"],
                    }
                ),
                parameter_hash=sha256_value(parameters),
                status="ACTIVE",
                created_at=datetime(2026, 7, 26),
            )
        )
    return (
        config["factor_set_version"],
        definitions,
        float(config["group_coverage_threshold"]),
    )


class FactorRegistry:
    def __init__(self, db):
        self.db = db
        self.audit = QuantAuditService(db)

    async def register(self, definition: FactorDefinition) -> FactorDefinition:
        query = {
            "factor_id": definition.factor_id,
            "factor_version": definition.factor_version,
        }
        existing = await self.db["ag_factor_definitions"].find_one(query)
        if existing:
            existing.pop("_id", None)
            stored = FactorDefinition.model_validate(existing)
            if stored.model_dump(mode="json") != definition.model_dump(mode="json"):
                await self.audit.record(
                    "QUANT_INTEGRITY_CONFLICT",
                    entity_id=f"{definition.factor_id}:{definition.factor_version}",
                    details={"entity": "FactorDefinition"},
                )
                raise DefinitionConflictError(
                    "factor definition identity already exists with different content"
                )
            return stored
        await self.db["ag_factor_definitions"].insert_one(
            definition.model_dump(mode="python")
        )
        await self.audit.record(
            "FACTOR_DEFINITION_REGISTERED",
            entity_id=f"{definition.factor_id}:{definition.factor_version}",
        )
        return definition

    async def seed_builtins(self) -> list[FactorDefinition]:
        _, definitions, _ = builtin_factor_definitions()
        return [await self.register(item) for item in definitions]

    async def get_version_set(self, *, require_registered: bool = True) -> dict[str, str]:
        _, definitions, _ = builtin_factor_definitions()
        result = {item.factor_id: item.factor_version for item in definitions}
        if require_registered:
            for item in definitions:
                stored = await self.db["ag_factor_definitions"].find_one(
                    {
                        "factor_id": item.factor_id,
                        "factor_version": item.factor_version,
                        "status": "ACTIVE",
                    }
                )
                if not stored:
                    raise LookupError(
                        f"factor definition not registered: {item.factor_id}:{item.factor_version}"
                    )
        return result
