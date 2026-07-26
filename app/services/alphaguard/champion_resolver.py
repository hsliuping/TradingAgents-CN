"""The only PR-008 Champion pointer resolver."""

from __future__ import annotations

from datetime import date, datetime

from app.services.alphaguard.experiment_repository import ExperimentRepository
from app.services.alphaguard.paper_storage import clean_document
from tradingagents.alphaguard.experiment_schemas import (
    ChampionAssignment,
    ChampionAssignmentHistory,
    ChampionResolution,
    ComponentVersionRecord,
    experiment_hash,
)


def champion_slot_id(
    component_type: str, component_key: str, market: str
) -> str:
    return f"{component_type}:{component_key}:{market}"


def assignment_hash(value) -> str:
    return experiment_hash(
        value,
        exclude={"assignment_hash", "updated_at", "schema_version"},
    )


class ChampionResolutionError(LookupError):
    pass


class ChampionResolver:
    def __init__(self, db):
        self.db = db
        self.repository = ExperimentRepository(db)

    async def _saga_committed(self, saga_id: str | None) -> bool:
        if saga_id is None:
            # Explicit legacy/current import has no promotion side effect.
            return True
        raw = await self.repository.get(
            "promotion_sagas", {"promotion_saga_id": saga_id}
        )
        return bool(raw and raw.get("status") == "COMMITTED")

    async def _eligible_assignment(
        self,
        *,
        slot_id: str,
        as_of_trade_date: date,
        include_pending_saga_id: str | None = None,
    ) -> ChampionAssignment | None:
        raw = await self.repository.get(
            "champion_assignments", {"champion_slot_id": slot_id}
        )
        if raw:
            current = ChampionAssignment.model_validate(raw)
            pending_allowed = (
                include_pending_saga_id is not None
                and current.promotion_saga_id == include_pending_saga_id
            )
            if (
                current.status != "SUSPENDED"
                and current.effective_from_trade_date <= as_of_trade_date
                and (
                    pending_allowed
                    or await self._saga_committed(current.promotion_saga_id)
                )
            ):
                return current
        histories = await self.repository.list(
            "champion_history",
            {"champion_slot_id": slot_id},
            sort=("recorded_at", -1),
        )
        eligible = []
        for item in histories:
            history = ChampionAssignmentHistory.model_validate(item)
            assignment = history.assignment
            if (
                assignment.status != "SUSPENDED"
                and assignment.effective_from_trade_date <= as_of_trade_date
                and await self._saga_committed(history.committed_saga_id)
            ):
                eligible.append(assignment)
        eligible.sort(
            key=lambda item: (
                item.effective_from_trade_date,
                item.assignment_version,
            ),
            reverse=True,
        )
        return eligible[0] if eligible else None

    async def resolve_champion(
        self,
        *,
        component_type: str,
        component_key: str,
        market: str,
        as_of_trade_date: date,
    ) -> ChampionResolution:
        return await self._resolve(
            component_type=component_type,
            component_key=component_key,
            market=market,
            as_of_trade_date=as_of_trade_date,
            include_pending_saga_id=None,
        )

    async def resolve_required_components(
        self,
        *,
        market: str,
        as_of_trade_date: date,
    ) -> dict[str, str]:
        """Resolve the complete deterministic production set, never latest."""

        if market != "CN":
            raise ChampionResolutionError(
                "PR-008 deterministic Champion set supports CN only"
            )
        from app.services.alphaguard.experiment_component_adapters import (
            current_component_payloads,
        )

        resolutions = []
        for descriptor in current_component_payloads():
            resolutions.append(
                await self.resolve_champion(
                    component_type=descriptor["component_type"],
                    component_key=descriptor["component_key"],
                    market=market,
                    as_of_trade_date=as_of_trade_date,
                )
            )
        return {
            item.champion_slot_id: item.version_ref
            for item in sorted(
                resolutions, key=lambda value: value.champion_slot_id
            )
        }

    async def verify_pending_assignment(
        self,
        *,
        champion_slot_id: str,
        saga_id: str,
        as_of_trade_date: date,
    ) -> ChampionResolution:
        parts = champion_slot_id.rsplit(":", 2)
        if len(parts) != 3:
            raise ChampionResolutionError("invalid Champion slot identity")
        return await self._resolve(
            component_type=parts[0],
            component_key=parts[1],
            market=parts[2],
            as_of_trade_date=as_of_trade_date,
            include_pending_saga_id=saga_id,
        )

    async def _resolve(
        self,
        *,
        component_type: str,
        component_key: str,
        market: str,
        as_of_trade_date: date,
        include_pending_saga_id: str | None,
    ) -> ChampionResolution:
        slot_id = champion_slot_id(component_type, component_key, market)
        assignment = await self._eligible_assignment(
            slot_id=slot_id,
            as_of_trade_date=as_of_trade_date,
            include_pending_saga_id=include_pending_saga_id,
        )
        if assignment is None:
            raise ChampionResolutionError(
                "no committed Champion is effective for this trade date"
            )
        if assignment_hash(assignment) != assignment.assignment_hash:
            raise ChampionResolutionError("ChampionAssignment hash mismatch")
        raw_version = clean_document(
            await self.db["ag_exp_component_versions"].find_one(
                {"version_ref": assignment.current_version_ref}
            )
        )
        if raw_version is None:
            raise ChampionResolutionError("Champion component version is missing")
        component = ComponentVersionRecord.model_validate(raw_version)
        return ChampionResolution(
            champion_slot_id=slot_id,
            component_type=component_type,
            component_key=component_key,
            market=market,
            as_of_trade_date=as_of_trade_date,
            version_ref=component.version_ref,
            component_hash=component.payload_hash,
            assignment_hash=assignment.assignment_hash,
            assignment_version=assignment.assignment_version,
            effective_from_trade_date=assignment.effective_from_trade_date,
            resolved_at=datetime.utcnow(),
        )
