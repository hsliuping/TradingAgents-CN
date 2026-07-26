from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime

from app.services.alphaguard.champion_resolver import (
    assignment_hash,
    champion_slot_id,
)
from app.services.alphaguard.experiment_component_adapters import (
    build_current_component_record,
    current_component_payloads,
)
from app.services.alphaguard.experiment_registry import ExperimentRegistry
from tradingagents.alphaguard.experiment_schemas import (
    ChampionAssignment,
    ComponentVersionRecord,
    experiment_hash,
)


async def seed_single_variable_experiment(db, *, user_id: str = "user-1"):
    descriptor = next(
        item
        for item in current_component_payloads()
        if item["component_type"] == "FACTOR_WEIGHT"
    )
    baseline = build_current_component_record(
        descriptor,
        created_by="test",
        created_at=datetime(2026, 7, 1),
    )
    payload = deepcopy(baseline.payload)
    factor_id = sorted(payload["factor_weights"])[0]
    payload["factor_weights"][factor_id] = 0.75
    challenger = ComponentVersionRecord(
        version_ref=f"{baseline.version_ref}-challenger",
        component_type=baseline.component_type,
        component_key=baseline.component_key,
        market=baseline.market,
        payload=payload,
        payload_hash=experiment_hash(payload),
        registration_supported=True,
        execution_supported=True,
        promotion_eligible=True,
        source="EXPERIMENT_VERSION",
        parent_version_ref=baseline.version_ref,
        created_by="test",
        created_at=datetime(2026, 7, 1),
    )
    registry = ExperimentRegistry(db)
    await registry.register_component_version(baseline)
    await registry.register_component_version(challenger)
    definition = await registry.create(
        user_id=user_id,
        created_by="admin",
        name="single weight",
        description="one deterministic weight only",
        hypothesis="lower one factor weight improves stability",
        component_type=baseline.component_type,
        component_key=baseline.component_key,
        market="CN",
        baseline_version_ref=baseline.version_ref,
        challenger_version_ref=challenger.version_ref,
        primary_variable_path=f"factor_weights.{factor_id}",
        expected_improvement=["stability"],
        expected_risks=["under-weighting"],
        success_criteria=["paired comparison"],
        failure_criteria=["leakage"],
        now=datetime(2026, 7, 1),
    )
    return registry, definition, baseline, challenger


async def seed_champion_assignment(
    db,
    component: ComponentVersionRecord,
    *,
    previous_version_ref: str | None = None,
    effective_date: date = date(2026, 7, 1),
):
    payload = {
        "champion_slot_id": champion_slot_id(
            component.component_type, component.component_key, component.market
        ),
        "component_type": component.component_type,
        "component_key": component.component_key,
        "market": component.market,
        "current_version_ref": component.version_ref,
        "previous_version_ref": previous_version_ref,
        "source_experiment_id": None,
        "source_promotion_request_id": None,
        "effective_from_trade_date": effective_date,
        "assignment_version": 1,
        "status": "ACTIVE",
        "promotion_saga_id": None,
        "updated_by": "test",
        "updated_at": datetime(2026, 7, 1),
    }
    payload["assignment_hash"] = assignment_hash(payload)
    assignment = ChampionAssignment.model_validate(payload)
    await db["ag_exp_champion_assignments"].insert_one(
        assignment.model_dump(mode="python")
    )
    return assignment
