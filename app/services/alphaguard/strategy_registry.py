"""Immutable StrategyDefinition registry backed by versioned YAML."""

from __future__ import annotations

from datetime import datetime

from app.schemas.alphaguard import StrategyDefinition

from .factor_registry import DefinitionConflictError
from .quant_audit_service import QuantAuditService
from .quant_config import STRATEGY_ENGINE_CODE_VERSION, sha256_value, strategy_configs


STRATEGY_SET_VERSION = "strategy-set-v1"


def builtin_strategy_definitions() -> list[StrategyDefinition]:
    definitions = []
    for item in strategy_configs():
        parameters = item["parameters"]
        definitions.append(
            StrategyDefinition(
                strategy_id=item["strategy_id"],
                strategy_version=item["strategy_version"],
                name=item["name"],
                description=item["description"],
                status=item["status"],
                supported_markets=item["supported_markets"],
                allowed_regimes=item["allowed_regimes"],
                factor_dependencies=item["factor_dependencies"],
                required_group_scores=item["required_group_scores"],
                parameters=parameters,
                code_hash=sha256_value(
                    {
                        "engine": STRATEGY_ENGINE_CODE_VERSION,
                        "strategy_id": item["strategy_id"],
                    }
                ),
                parameter_hash=sha256_value(parameters),
                parent_version=None,
                created_at=datetime(2026, 7, 26),
                promoted_at=datetime(2026, 7, 26),
            )
        )
    return definitions


class StrategyRegistry:
    def __init__(self, db):
        self.db = db
        self.audit = QuantAuditService(db)

    async def register(self, definition: StrategyDefinition) -> StrategyDefinition:
        query = {
            "strategy_id": definition.strategy_id,
            "strategy_version": definition.strategy_version,
        }
        existing = await self.db["ag_strategy_definitions"].find_one(query)
        if existing:
            existing.pop("_id", None)
            stored = StrategyDefinition.model_validate(existing)
            if stored.model_dump(mode="json") != definition.model_dump(mode="json"):
                await self.audit.record(
                    "QUANT_INTEGRITY_CONFLICT",
                    entity_id=f"{definition.strategy_id}:{definition.strategy_version}",
                    details={"entity": "StrategyDefinition"},
                )
                raise DefinitionConflictError(
                    "strategy definition identity already exists with different content"
                )
            return stored
        await self.db["ag_strategy_definitions"].insert_one(
            definition.model_dump(mode="python")
        )
        await self.audit.record(
            "STRATEGY_DEFINITION_REGISTERED",
            entity_id=f"{definition.strategy_id}:{definition.strategy_version}",
        )
        return definition

    async def seed_builtins(self) -> list[StrategyDefinition]:
        return [await self.register(item) for item in builtin_strategy_definitions()]

    async def require_strategy_set(self) -> list[StrategyDefinition]:
        result = []
        for item in builtin_strategy_definitions():
            document = await self.db["ag_strategy_definitions"].find_one(
                {
                    "strategy_id": item.strategy_id,
                    "strategy_version": item.strategy_version,
                    "status": "CHAMPION",
                }
            )
            if not document:
                raise LookupError(
                    f"strategy definition not registered: {item.strategy_id}:{item.strategy_version}"
                )
            document.pop("_id", None)
            result.append(StrategyDefinition.model_validate(document))
        return result
