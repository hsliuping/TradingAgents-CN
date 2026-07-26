"""Fail-closed integrity checks for PR-008 experiment state."""

from __future__ import annotations

from datetime import date

from app.services.alphaguard.champion_resolver import (
    ChampionResolver,
    ChampionResolutionError,
)
from app.services.alphaguard.champion_promotion_service import (
    ChampionPromotionService,
)
from app.services.alphaguard.experiment_repository import ExperimentRepository
from tradingagents.alphaguard.experiment_schemas import ChampionAssignment


class ExperimentReconciliation:
    def __init__(self, db):
        self.db = db
        self.repository = ExperimentRepository(db)

    async def reconcile(self, *, as_of_trade_date: date) -> dict[str, int]:
        recovered = await ChampionPromotionService(
            self.db
        ).recover_incomplete_sagas()
        assignments = await self.repository.list("champion_assignments")
        valid = conflicts = 0
        resolver = ChampionResolver(self.db)
        seen: set[tuple[str, str, str]] = set()
        for raw in assignments:
            assignment = ChampionAssignment.model_validate(raw)
            identity = (
                assignment.component_type,
                assignment.component_key,
                assignment.market,
            )
            if identity in seen:
                conflicts += 1
                continue
            seen.add(identity)
            if assignment.effective_from_trade_date > as_of_trade_date:
                continue
            try:
                await resolver.resolve_champion(
                    component_type=assignment.component_type,
                    component_key=assignment.component_key,
                    market=assignment.market,
                    as_of_trade_date=as_of_trade_date,
                )
                valid += 1
            except ChampionResolutionError:
                conflicts += 1
        return {
            "valid_champions": valid,
            "integrity_conflicts": conflicts,
            **{f"sagas_{key}": value for key, value in recovered.items()},
        }
