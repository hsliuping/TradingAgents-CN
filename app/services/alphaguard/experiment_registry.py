"""Immutable component/experiment registry and controlled state transitions."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from app.services.alphaguard.experiment_audit_service import ExperimentAuditService
from app.services.alphaguard.experiment_component_adapters import (
    component_capability,
    diff_leaf_paths,
    value_at_path,
)
from app.services.alphaguard.experiment_config import promotion_policy
from app.services.alphaguard.experiment_repository import (
    ExperimentIntegrityConflict,
    ExperimentRepository,
    experiment_document,
)
from app.services.alphaguard.experiment_state_machine import validate_transition
from app.services.alphaguard.paper_storage import clean_document
from tradingagents.alphaguard.experiment_schemas import (
    ComponentVersionRecord,
    ExperimentDefinition,
    ExperimentVariableChange,
    experiment_hash,
)


def _definition_hash(payload: dict) -> str:
    return experiment_hash(
        payload,
        exclude={
            "immutable_definition_hash",
            "status",
            "updated_at",
            "schema_version",
        },
    )


class ExperimentRegistry:
    def __init__(self, db):
        self.db = db
        self.repository = ExperimentRepository(db)
        self.audit = ExperimentAuditService(db)

    async def register_component_version(
        self, record: ComponentVersionRecord
    ) -> tuple[ComponentVersionRecord, bool]:
        stored, created = await self.repository.save_immutable(
            "component_versions",
            record,
            identity={"version_ref": record.version_ref},
            hash_field="payload_hash",
        )
        return stored, created

    async def component_version(self, version_ref: str) -> ComponentVersionRecord:
        raw = await self.repository.get(
            "component_versions", {"version_ref": version_ref}
        )
        if raw is None:
            raise LookupError(f"component version does not exist: {version_ref}")
        return ComponentVersionRecord.model_validate(raw)

    async def create(
        self,
        *,
        user_id: str,
        created_by: str,
        name: str,
        description: str,
        hypothesis: str,
        component_type: str,
        component_key: str,
        market: str,
        baseline_version_ref: str,
        challenger_version_ref: str,
        primary_variable_path: str,
        expected_improvement: list[str] | None = None,
        expected_risks: list[str] | None = None,
        success_criteria: list[str] | None = None,
        failure_criteria: list[str] | None = None,
        now: datetime | None = None,
    ) -> ExperimentDefinition:
        now = now or datetime.utcnow()
        baseline = await self.component_version(baseline_version_ref)
        challenger = await self.component_version(challenger_version_ref)
        if (
            baseline.component_type != component_type
            or challenger.component_type != component_type
            or baseline.component_key != component_key
            or challenger.component_key != component_key
            or baseline.market != market
            or challenger.market != market
        ):
            raise ValueError("baseline/Challenger component identity mismatch")
        if baseline.payload_hash == challenger.payload_hash:
            raise ValueError("Challenger is a same-content pseudo-version")
        paths = diff_leaf_paths(baseline.payload, challenger.payload)
        if primary_variable_path not in paths:
            raise ValueError("declared primary variable did not change")
        secondary = [path for path in paths if path != primary_variable_path]
        mode = "UNIVARIATE" if not secondary else "MULTIVARIATE"
        capability = component_capability(component_type)
        execution_supported = bool(
            capability["execution_supported"]
            and baseline.execution_supported
            and challenger.execution_supported
        )
        eligible = bool(
            mode == "UNIVARIATE"
            and execution_supported
            and baseline.promotion_eligible
            and challenger.promotion_eligible
        )
        policy = promotion_policy()
        payload = {
            "experiment_id": str(uuid4()),
            "user_id": str(user_id),
            "name": name,
            "description": description,
            "hypothesis": hypothesis,
            "component_type": component_type,
            "component_key": component_key,
            "market": market,
            "baseline_version_ref": baseline_version_ref,
            "challenger_version_ref": challenger_version_ref,
            "primary_variable_path": primary_variable_path,
            "baseline_value_hash": experiment_hash(
                value_at_path(baseline.payload, primary_variable_path)
            ),
            "challenger_value_hash": experiment_hash(
                value_at_path(challenger.payload, primary_variable_path)
            ),
            "secondary_variable_paths": secondary,
            "experiment_mode": mode,
            "promotion_eligible": eligible,
            "execution_supported": execution_supported,
            "unsupported_reason": (
                None if execution_supported else "UNSUPPORTED_COMPONENT_ADAPTER"
            ),
            "promotion_policy_version": policy.policy_version,
            "expected_improvement": expected_improvement or [],
            "expected_risks": expected_risks or [],
            "success_criteria": success_criteria or [],
            "failure_criteria": failure_criteria or [],
            "status": "DRAFT",
            "created_by": str(created_by),
            "created_at": now,
            "updated_at": now,
        }
        payload["immutable_definition_hash"] = _definition_hash(payload)
        definition = ExperimentDefinition.model_validate(payload)
        primary = ExperimentVariableChange(
            change_id=str(uuid4()),
            experiment_id=definition.experiment_id,
            variable_path=primary_variable_path,
            change_type=(
                "WEIGHT"
                if component_type == "FACTOR_WEIGHT"
                else "COMPONENT_SET"
                if component_type == "FACTOR_SET"
                else "PARAMETER"
            ),
            baseline_value=value_at_path(
                baseline.payload, primary_variable_path
            ),
            challenger_value=value_at_path(
                challenger.payload, primary_variable_path
            ),
            is_primary=True,
            safety_impact=(
                "HIGH"
                if component_type in {"REGIME_CONFIG", "STRATEGY_CONFIG"}
                else "MEDIUM"
            ),
            baseline_hash=definition.baseline_value_hash,
            challenger_hash=definition.challenger_value_hash,
            created_at=now,
        )
        await self.db["ag_exp_definitions"].insert_one(
            experiment_document(definition)
        )
        await self.db["ag_exp_variable_changes"].insert_one(
            experiment_document(primary)
        )
        for path in secondary:
            change = ExperimentVariableChange(
                change_id=str(uuid4()),
                experiment_id=definition.experiment_id,
                variable_path=path,
                change_type="PARAMETER",
                baseline_value=value_at_path(baseline.payload, path),
                challenger_value=value_at_path(challenger.payload, path),
                is_primary=False,
                safety_impact="HIGH",
                baseline_hash=experiment_hash(value_at_path(baseline.payload, path)),
                challenger_hash=experiment_hash(
                    value_at_path(challenger.payload, path)
                ),
                created_at=now,
            )
            await self.db["ag_exp_variable_changes"].insert_one(
                experiment_document(change)
            )
        await self.audit.record(
            "EXPERIMENT_CREATED",
            f"{mode} experiment created; promotion_eligible={eligible}",
            experiment_id=definition.experiment_id,
            user_id=definition.user_id,
            market=definition.market,
            baseline_version_ref=definition.baseline_version_ref,
            challenger_version_ref=definition.challenger_version_ref,
            input_hash=definition.immutable_definition_hash,
        )
        return definition

    async def get(self, experiment_id: str) -> ExperimentDefinition:
        raw = clean_document(
            await self.db["ag_exp_definitions"].find_one(
                {"experiment_id": experiment_id}
            )
        )
        if raw is None:
            raise LookupError("ExperimentDefinition does not exist")
        model = ExperimentDefinition.model_validate(raw)
        if _definition_hash(model.model_dump(mode="python")) != model.immutable_definition_hash:
            raise ExperimentIntegrityConflict(
                "ExperimentDefinition immutable hash mismatch"
            )
        return model

    async def list(
        self,
        *,
        user_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[ExperimentDefinition]:
        query = {}
        if user_id is not None:
            query["user_id"] = str(user_id)
        if status:
            query["status"] = status
        documents = await self.db["ag_exp_definitions"].find(query).sort(
            "created_at", -1
        ).limit(limit).to_list(length=limit)
        return [
            ExperimentDefinition.model_validate(clean_document(item))
            for item in documents
        ]

    async def validate(self, experiment_id: str) -> ExperimentDefinition:
        definition = await self.get(experiment_id)
        baseline = await self.component_version(definition.baseline_version_ref)
        challenger = await self.component_version(
            definition.challenger_version_ref
        )
        paths = diff_leaf_paths(baseline.payload, challenger.payload)
        expected = [definition.primary_variable_path] + list(
            definition.secondary_variable_paths
        )
        if paths != sorted(expected):
            await self.audit.record(
                "EXPERIMENT_VALIDATION_FAILED",
                "stored component difference no longer matches immutable definition",
                experiment_id=definition.experiment_id,
                input_hash=definition.immutable_definition_hash,
            )
            raise ExperimentIntegrityConflict("experiment component diff mismatch")
        await self.audit.record(
            "EXPERIMENT_VALIDATED",
            "immutable versions and single-variable contract validated",
            experiment_id=definition.experiment_id,
            input_hash=definition.immutable_definition_hash,
        )
        return definition

    async def transition(
        self,
        experiment_id: str,
        target: str,
        *,
        human_approval_applied: bool = False,
        reason: str,
        now: datetime | None = None,
    ) -> ExperimentDefinition:
        current = await self.get(experiment_id)
        validate_transition(
            current.status,
            target,
            human_approval_applied=human_approval_applied,
        )
        now = now or datetime.utcnow()
        updated = current.model_copy(
            update={"status": target, "updated_at": now}
        )
        await self.repository.replace_state(
            "definitions",
            identity={"experiment_id": experiment_id},
            expected={
                "status": current.status,
                "immutable_definition_hash": current.immutable_definition_hash,
            },
            model=updated,
        )
        await self.audit.record(
            "EXPERIMENT_STATE_CHANGED",
            f"{current.status} -> {target}: {reason}",
            experiment_id=experiment_id,
            user_id=current.user_id,
            market=current.market,
            input_hash=current.immutable_definition_hash,
        )
        return updated

    async def suspend(self, experiment_id: str, *, reason: str):
        return await self.transition(experiment_id, "SUSPENDED", reason=reason)

    async def retire(self, experiment_id: str, *, reason: str):
        return await self.transition(experiment_id, "RETIRED", reason=reason)
