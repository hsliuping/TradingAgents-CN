"""Side-effect-free Champion/Challenger Shadow execution."""

from __future__ import annotations

import platform
import subprocess
from datetime import datetime
from uuid import NAMESPACE_URL, uuid5

from app.services.alphaguard.experiment_audit_service import ExperimentAuditService
from app.services.alphaguard.experiment_component_adapters import (
    DeterministicExperimentAdapter,
)
from app.services.alphaguard.experiment_config import promotion_policy
from app.services.alphaguard.experiment_dataset_service import (
    ExperimentDatasetService,
)
from app.services.alphaguard.experiment_registry import ExperimentRegistry
from app.services.alphaguard.experiment_repository import (
    ExperimentRepository,
    experiment_document,
)
from app.services.alphaguard.snapshot_data_resolver import SnapshotDataResolver
from tradingagents.alphaguard.experiment_schemas import (
    ExperimentOutputPair,
    ExperimentRun,
    ShadowRun,
    experiment_hash,
)


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


class ShadowExperimentService:
    def __init__(self, db):
        self.db = db
        self.registry = ExperimentRegistry(db)
        self.datasets = ExperimentDatasetService(db)
        self.repository = ExperimentRepository(db)
        self.audit = ExperimentAuditService(db)
        self.resolver = SnapshotDataResolver(db)
        self.adapter = DeterministicExperimentAdapter()
        self.policy = promotion_policy()

    async def start(
        self,
        experiment_id: str,
        *,
        dataset_manifest_id: str,
        created_by: str,
        now: datetime | None = None,
    ) -> ShadowRun:
        now = now or datetime.utcnow()
        definition = await self.registry.validate(experiment_id)
        if definition.status not in {"BACKTESTED", "SHADOW"}:
            raise ValueError("Shadow can start only from BACKTESTED")
        await self.datasets.get(dataset_manifest_id)
        existing_raw = await self.repository.get(
            "shadow_runs",
            {"experiment_id": experiment_id, "status": {"$in": ["ACTIVE", "PAUSED"]}},
        )
        if existing_raw:
            return ShadowRun.model_validate(existing_raw)
        baseline = await self.registry.component_version(
            definition.baseline_version_ref
        )
        challenger = await self.registry.component_version(
            definition.challenger_version_ref
        )
        run_input_hash = experiment_hash(
            {
                "experiment_id": experiment_id,
                "dataset_manifest_id": dataset_manifest_id,
                "run_type": "SHADOW",
                "baseline_hash": baseline.payload_hash,
                "challenger_hash": challenger.payload_hash,
                "code_commit": _git("rev-parse", "HEAD"),
            }
        )
        run_id = str(
            uuid5(NAMESPACE_URL, f"alphaguard:shadow-run:{run_input_hash}")
        )
        run = ExperimentRun(
            run_id=run_id,
            experiment_id=experiment_id,
            dataset_manifest_id=dataset_manifest_id,
            split_id=None,
            run_type="SHADOW",
            status="RUNNING",
            champion_version_refs={
                definition.component_key: baseline.version_ref
            },
            challenger_version_refs={
                definition.component_key: challenger.version_ref
            },
            code_commit=_git("rev-parse", "HEAD"),
            code_tree_hash=_git("rev-parse", "HEAD^{tree}"),
            config_hash=self.policy.immutable_hash,
            environment_hash=experiment_hash(
                {
                    "python": platform.python_version(),
                    "shadow": "shadow-experiment-v1",
                }
            ),
            reproducibility="DETERMINISTIC",
            attempt_number=1,
            started_at=now,
            input_hash=run_input_hash,
            created_by=created_by,
            created_at=now,
        )
        await self.db["ag_exp_runs"].insert_one(experiment_document(run))
        minimum_days = int(
            self.policy.minimum_sample_rules["shadow_trade_days"]
        )
        shadow = ShadowRun(
            shadow_run_id=str(
                uuid5(
                    NAMESPACE_URL,
                    f"alphaguard:shadow:{experiment_id}:{run_id}",
                )
            ),
            experiment_id=experiment_id,
            run_id=run_id,
            status="ACTIVE",
            started_at=now,
            champion_output_count=0,
            challenger_output_count=0,
            paired_output_count=0,
            divergence_count=0,
            integrity_error_count=0,
            min_required_trade_days=minimum_days,
            observed_trade_days=0,
            input_hash=experiment_hash(
                {
                    "run_input_hash": run_input_hash,
                    "minimum_trade_days": minimum_days,
                }
            ),
            created_at=now,
        )
        await self.db["ag_exp_shadow_runs"].insert_one(
            experiment_document(shadow)
        )
        if definition.status == "BACKTESTED":
            await self.registry.transition(
                experiment_id,
                "SHADOW",
                reason="Shadow run started after backtest",
            )
        await self.audit.record(
            "SHADOW_STARTED",
            "same-snapshot Shadow started without execution side effects",
            experiment_id=experiment_id,
            run_id=run_id,
            shadow_run_id=shadow.shadow_run_id,
            dataset_manifest_id=dataset_manifest_id,
            user_id=definition.user_id,
            market=definition.market,
            input_hash=shadow.input_hash,
        )
        return shadow

    async def process_snapshot(
        self,
        shadow_run_id: str,
        snapshot_id: str,
        *,
        now: datetime | None = None,
    ) -> ExperimentOutputPair:
        now = now or datetime.utcnow()
        output_id = str(
            uuid5(
                NAMESPACE_URL,
                f"alphaguard:shadow-output:{shadow_run_id}:{snapshot_id}",
            )
        )
        existing = await self.repository.get(
            "shadow_outputs", {"output_id": output_id}
        )
        if existing is not None:
            return ExperimentOutputPair.model_validate(existing)
        raw = await self.repository.get(
            "shadow_runs", {"shadow_run_id": shadow_run_id}
        )
        if raw is None:
            raise LookupError("ShadowRun does not exist")
        shadow = ShadowRun.model_validate(raw)
        if shadow.status != "ACTIVE":
            raise ValueError("ShadowRun is not ACTIVE")
        definition = await self.registry.get(shadow.experiment_id)
        baseline = await self.registry.component_version(
            definition.baseline_version_ref
        )
        challenger = await self.registry.component_version(
            definition.challenger_version_ref
        )
        data = await self.resolver.resolve(snapshot_id)
        if data.snapshot.market != definition.market:
            raise ValueError("Shadow snapshot market mismatch")
        champion_output, challenger_output, difference = self.adapter.run_pair(
            data, baseline, challenger
        )
        payload = {
            "experiment_id": definition.experiment_id,
            "run_id": shadow.run_id,
            "run_type": "SHADOW",
            "snapshot_id": snapshot_id,
            "symbol": data.snapshot.symbol,
            "market": data.snapshot.market,
            "trade_date": data.snapshot.trade_date,
            "decision_cutoff_at": data.snapshot.price_cutoff_at,
            "baseline_version_ref": baseline.version_ref,
            "challenger_version_ref": challenger.version_ref,
            "fixed_version_refs": {
                "factor_set": experiment_hash(
                    data.snapshot.factor_version_set
                ),
                "strategy": data.snapshot.strategy_version or "legacy:none",
                "normal_model": data.snapshot.normal_model_version or "not-run",
                "top_model": data.snapshot.top_model_version or "not-run",
            },
            "champion_output": champion_output,
            "challenger_output": challenger_output,
            "difference": difference,
            "comparable": True,
            "incomparability_reasons": [],
            "decision_input_refs": sorted(data.input_refs),
            "evaluation_label_ids": [],
        }
        output = ExperimentOutputPair(
            output_id=output_id,
            input_hash=experiment_hash(
                {
                    "shadow_input_hash": shadow.input_hash,
                    "snapshot_input_hash": data.input_hash,
                }
            ),
            result_hash=experiment_hash(payload),
            created_at=data.snapshot.price_cutoff_at,
            **payload,
        )
        stored, created = await self.repository.save_immutable(
            "shadow_outputs",
            output,
            identity={"output_id": output.output_id},
            hash_field="result_hash",
        )
        if created:
            documents = await self.repository.list(
                "shadow_outputs", {"run_id": shadow.run_id}
            )
            observed_days = len({item["trade_date"] for item in documents})
            divergence = sum(
                not item["difference"].get("outputs_equal", False)
                for item in documents
            )
            updated = shadow.model_copy(
                update={
                    "champion_output_count": len(documents),
                    "challenger_output_count": len(documents),
                    "paired_output_count": len(documents),
                    "divergence_count": divergence,
                    "observed_trade_days": observed_days,
                }
            )
            await self.db["ag_exp_shadow_runs"].replace_one(
                {"shadow_run_id": shadow_run_id},
                experiment_document(updated),
            )
            await self.audit.record(
                "SHADOW_OUTPUT_CREATED",
                "paired output saved with no Candidate/order/account writes",
                experiment_id=definition.experiment_id,
                run_id=shadow.run_id,
                shadow_run_id=shadow_run_id,
                user_id=definition.user_id,
                market=definition.market,
                input_hash=stored.input_hash,
                result_hash=stored.result_hash,
            )
        return stored

    async def pause(self, shadow_run_id: str, *, reason: str) -> ShadowRun:
        raw = await self.repository.get(
            "shadow_runs", {"shadow_run_id": shadow_run_id}
        )
        if raw is None:
            raise LookupError("ShadowRun does not exist")
        shadow = ShadowRun.model_validate(raw)
        if shadow.status not in {"ACTIVE", "PAUSED"}:
            raise ValueError("completed Shadow cannot be paused")
        updated = shadow.model_copy(update={"status": "PAUSED"})
        await self.db["ag_exp_shadow_runs"].replace_one(
            {"shadow_run_id": shadow_run_id}, experiment_document(updated)
        )
        await self.audit.record(
            "SHADOW_PAUSED",
            reason,
            experiment_id=shadow.experiment_id,
            run_id=shadow.run_id,
            shadow_run_id=shadow_run_id,
        )
        return updated

    async def complete(self, shadow_run_id: str) -> ShadowRun:
        raw = await self.repository.get(
            "shadow_runs", {"shadow_run_id": shadow_run_id}
        )
        if raw is None:
            raise LookupError("ShadowRun does not exist")
        shadow = ShadowRun.model_validate(raw)
        if shadow.observed_trade_days < shadow.min_required_trade_days:
            status = "INSUFFICIENT_DATA"
        else:
            status = "COMPLETED"
        now = datetime.utcnow()
        updated = shadow.model_copy(
            update={"status": status, "ended_at": now}
        )
        await self.db["ag_exp_shadow_runs"].replace_one(
            {"shadow_run_id": shadow_run_id}, experiment_document(updated)
        )
        await self.db["ag_exp_runs"].update_one(
            {"run_id": shadow.run_id},
            {
                "$set": {
                    "status": (
                        "COMPLETED"
                        if status == "COMPLETED"
                        else "INSUFFICIENT_DATA"
                    ),
                    "completed_at": now,
                    "result_hash": experiment_hash(
                        {
                            "shadow_run_id": shadow_run_id,
                            "observed_trade_days": shadow.observed_trade_days,
                        }
                    ),
                }
            },
        )
        await self.audit.record(
            "SHADOW_COMPLETED",
            f"Shadow ended with status={status}",
            experiment_id=shadow.experiment_id,
            run_id=shadow.run_id,
            shadow_run_id=shadow_run_id,
        )
        return updated
