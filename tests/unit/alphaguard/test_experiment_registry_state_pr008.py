from __future__ import annotations

from copy import deepcopy
from datetime import datetime

import pytest

from app.services.alphaguard.experiment_component_adapters import (
    build_current_component_record,
    component_capability,
    current_component_payloads,
)
from app.services.alphaguard.experiment_registry import ExperimentRegistry
from app.services.alphaguard.experiment_state_machine import (
    ALLOWED_TRANSITIONS,
    ExperimentTransitionError,
    validate_transition,
)
from tests.unit.alphaguard._fakes import FakeDB
from tests.unit.alphaguard.pr008_helpers import seed_single_variable_experiment
from tradingagents.alphaguard.experiment_schemas import (
    ComponentVersionRecord,
    ExperimentDefinition,
    experiment_hash,
)


@pytest.mark.asyncio
async def test_registry_creates_stable_single_variable_experiment():
    db = FakeDB()
    registry, definition, baseline, challenger = (
        await seed_single_variable_experiment(db)
    )
    assert definition.experiment_mode == "UNIVARIATE"
    assert definition.promotion_eligible is True
    assert definition.secondary_variable_paths == []
    assert (await registry.get(definition.experiment_id)) == definition
    assert db["ag_exp_variable_changes"].count() == 1
    assert baseline.payload_hash != challenger.payload_hash


@pytest.mark.asyncio
async def test_registry_rejects_missing_baseline_or_challenger():
    db = FakeDB()
    descriptor = current_component_payloads()[0]
    record = build_current_component_record(descriptor, created_by="test")
    await ExperimentRegistry(db).register_component_version(record)
    with pytest.raises(LookupError):
        await ExperimentRegistry(db).create(
            user_id="u",
            created_by="a",
            name="x",
            description="x",
            hypothesis="x",
            component_type=record.component_type,
            component_key=record.component_key,
            market="CN",
            baseline_version_ref="missing",
            challenger_version_ref=record.version_ref,
            primary_variable_path="factor_weights.x",
        )


@pytest.mark.asyncio
async def test_registry_rejects_same_content_pseudo_version():
    db = FakeDB()
    descriptor = current_component_payloads()[0]
    baseline = build_current_component_record(descriptor, created_by="test")
    fake = baseline.model_copy(
        update={
            "version_ref": f"{baseline.version_ref}-fake",
            "source": "EXPERIMENT_VERSION",
            "parent_version_ref": baseline.version_ref,
        }
    )
    registry = ExperimentRegistry(db)
    await registry.register_component_version(baseline)
    await registry.register_component_version(fake)
    with pytest.raises(ValueError, match="same-content"):
        await registry.create(
            user_id="u",
            created_by="a",
            name="x",
            description="x",
            hypothesis="x",
            component_type=baseline.component_type,
            component_key=baseline.component_key,
            market="CN",
            baseline_version_ref=baseline.version_ref,
            challenger_version_ref=fake.version_ref,
            primary_variable_path="factor_weights.x",
        )


@pytest.mark.asyncio
async def test_multiple_changes_are_multivariate_and_not_promotable():
    db = FakeDB()
    descriptor = current_component_payloads()[0]
    baseline = build_current_component_record(descriptor, created_by="test")
    payload = deepcopy(baseline.payload)
    ids = sorted(payload["factor_weights"])[:2]
    payload["factor_weights"][ids[0]] = 0.8
    payload["factor_weights"][ids[1]] = 0.7
    challenger = ComponentVersionRecord(
        version_ref="multi-v1",
        component_type=baseline.component_type,
        component_key=baseline.component_key,
        market="CN",
        payload=payload,
        payload_hash=experiment_hash(payload),
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
        user_id="u",
        created_by="a",
        name="multi",
        description="two changes",
        hypothesis="research only",
        component_type=baseline.component_type,
        component_key=baseline.component_key,
        market="CN",
        baseline_version_ref=baseline.version_ref,
        challenger_version_ref=challenger.version_ref,
        primary_variable_path=f"factor_weights.{ids[0]}",
    )
    assert definition.experiment_mode == "MULTIVARIATE"
    assert definition.promotion_eligible is False
    assert definition.secondary_variable_paths == [f"factor_weights.{ids[1]}"]


@pytest.mark.parametrize(
    "component_type",
    ["FACTOR_WEIGHT", "FACTOR_SET", "REGIME_CONFIG", "STRATEGY_CONFIG"],
)
def test_deterministic_components_are_executable(component_type):
    capability = component_capability(component_type)
    assert capability["execution_supported"] is True
    assert capability["promotion_eligible"] is True


@pytest.mark.parametrize(
    "component_type",
    [
        "FACTOR_FORMULA",
        "NORMAL_PROMPT",
        "TOP_PROMPT",
        "MODEL_CONFIG",
        "AGENT_CONFIG",
        "DEBATE_CONFIG",
        "HARD_RISK_CONFIG",
        "MATCHING_CONFIG",
    ],
)
def test_unsafe_or_unadapted_components_are_registration_only(component_type):
    capability = component_capability(component_type)
    assert capability == {
        "registration_supported": True,
        "execution_supported": False,
        "promotion_eligible": False,
        "reason": "UNSUPPORTED_COMPONENT_ADAPTER",
    }


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (current, target)
        for current, targets in ALLOWED_TRANSITIONS.items()
        for target in targets
        if (current, target) != ("CHALLENGER", "CHAMPION")
    ],
)
def test_all_declared_state_transitions_are_allowed(current, target):
    validate_transition(current, target)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        ("DRAFT", "CHAMPION"),
        ("BACKTESTED", "CHAMPION"),
        ("SHADOW", "CHAMPION"),
        ("RETIRED", "EXPERIMENT"),
        ("DRAFT", "RETIRED"),
    ],
)
def test_direct_or_retired_state_transitions_are_blocked(current, target):
    with pytest.raises(ExperimentTransitionError):
        validate_transition(current, target)


def test_challenger_to_champion_requires_human_approval():
    with pytest.raises(ExperimentTransitionError):
        validate_transition("CHALLENGER", "CHAMPION")
    validate_transition(
        "CHALLENGER", "CHAMPION", human_approval_applied=True
    )


@pytest.mark.asyncio
async def test_core_definition_hash_detects_in_place_tampering():
    db = FakeDB()
    registry, definition, *_ = await seed_single_variable_experiment(db)
    db["ag_exp_definitions"].documents[0]["hypothesis"] = "tampered"
    with pytest.raises(Exception, match="hash mismatch"):
        await registry.get(definition.experiment_id)


def test_experiment_definition_is_frozen():
    fields = {
        "experiment_id": "e",
        "user_id": "u",
        "name": "n",
        "description": "d",
        "hypothesis": "h",
        "component_type": "FACTOR_WEIGHT",
        "component_key": "f",
        "market": "CN",
        "baseline_version_ref": "b",
        "challenger_version_ref": "c",
        "primary_variable_path": "x",
        "baseline_value_hash": "1" * 64,
        "challenger_value_hash": "2" * 64,
        "experiment_mode": "UNIVARIATE",
        "promotion_eligible": True,
        "execution_supported": True,
        "promotion_policy_version": "1.0.0",
        "status": "DRAFT",
        "created_by": "a",
        "created_at": datetime(2026, 7, 1),
        "updated_at": datetime(2026, 7, 1),
        "immutable_definition_hash": "3" * 64,
    }
    definition = ExperimentDefinition.model_validate(fields)
    with pytest.raises(Exception):
        definition.hypothesis = "changed"
