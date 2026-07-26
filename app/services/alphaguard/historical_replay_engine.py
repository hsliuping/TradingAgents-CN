"""Deterministic, experiment-only historical replay."""

from __future__ import annotations

import platform
import subprocess
from datetime import date, datetime
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

from app.services.alphaguard.experiment_audit_service import ExperimentAuditService
from app.services.alphaguard.experiment_component_adapters import (
    DeterministicExperimentAdapter,
)
from app.services.alphaguard.experiment_config import (
    replay_policy,
    robustness_policy,
)
from app.services.alphaguard.experiment_dataset_service import (
    ExperimentDatasetService,
)
from app.services.alphaguard.experiment_registry import ExperimentRegistry
from app.services.alphaguard.experiment_repository import (
    ExperimentRepository,
    experiment_document,
)
from app.services.alphaguard.paper_storage import clean_document
from app.services.alphaguard.snapshot_data_resolver import SnapshotDataResolver
from tradingagents.alphaguard.evaluation_schemas import HorizonLabel
from tradingagents.alphaguard.experiment_schemas import (
    ExperimentOutputPair,
    ExperimentRun,
    ExperimentRunResult,
    TimeSeriesSplitDefinition,
    experiment_hash,
)


def _git_value(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _decimal(value) -> Decimal:
    return Decimal(str(value))


def _proposal_action(output: dict) -> str:
    for proposal in output.get("quant_proposals", []):
        if proposal.get("status") == "TRIGGERED":
            return str(proposal.get("action_candidate") or "HOLD")
    return "HOLD"


def _aligned(raw_return: Decimal, action: str) -> Decimal:
    if action == "BUY":
        return raw_return
    if action in {"SELL", "REDUCE"}:
        return -raw_return
    return Decimal("0")


def _metrics(returns: list[Decimal]) -> dict:
    if not returns:
        return {
            "net_return": None,
            "gross_return": None,
            "max_drawdown": None,
            "return_drawdown_ratio": None,
            "trade_count": 0,
            "win_rate": None,
            "profit_factor": None,
            "top_trade_contribution_pct": None,
            "top_five_trade_contribution_pct": None,
        }
    equity = Decimal("1")
    peak = equity
    max_drawdown = Decimal("0")
    for value in returns:
        equity *= Decimal("1") + value
        peak = max(peak, equity)
        drawdown = equity / peak - Decimal("1") if peak else Decimal("0")
        max_drawdown = min(max_drawdown, drawdown)
    total_return = equity - Decimal("1")
    positives = [value for value in returns if value > 0]
    negatives = [value for value in returns if value < 0]
    total_abs = sum((abs(value) for value in returns), Decimal("0"))
    ranked = sorted((abs(value) for value in returns), reverse=True)
    return {
        "net_return": total_return,
        "gross_return": total_return,
        "max_drawdown": max_drawdown,
        "return_drawdown_ratio": (
            total_return / abs(max_drawdown)
            if max_drawdown < 0
            else None
        ),
        "trade_count": len(returns),
        "win_rate": Decimal(len(positives)) / Decimal(len(returns)),
        "profit_factor": (
            sum(positives, Decimal("0"))
            / abs(sum(negatives, Decimal("0")))
            if negatives
            else None
        ),
        "top_trade_contribution_pct": (
            ranked[0] / total_abs if total_abs and ranked else None
        ),
        "top_five_trade_contribution_pct": (
            sum(ranked[:5], Decimal("0")) / total_abs
            if total_abs and ranked
            else None
        ),
    }


class HistoricalReplayEngine:
    def __init__(self, db):
        self.db = db
        self.registry = ExperimentRegistry(db)
        self.datasets = ExperimentDatasetService(db)
        self.repository = ExperimentRepository(db)
        self.audit = ExperimentAuditService(db)
        self.resolver = SnapshotDataResolver(db)
        self.adapter = DeterministicExperimentAdapter()
        self.policy = replay_policy()

    async def _split(
        self, split_id: str | None
    ) -> TimeSeriesSplitDefinition | None:
        if split_id is None:
            return None
        raw = await self.repository.get("time_splits", {"split_id": split_id})
        if raw is None:
            raise LookupError("TimeSeriesSplitDefinition does not exist")
        return TimeSeriesSplitDefinition.model_validate(raw)

    async def _mature_label(
        self, snapshot_id: str
    ) -> HorizonLabel | None:
        subject = clean_document(
            await self.db["ag_eval_subjects"].find_one(
                {
                    "snapshot_id": snapshot_id,
                    "decision_stage": "QUANT",
                },
                sort=[("created_at", 1)],
            )
        )
        if subject is None:
            return None
        label = clean_document(
            await self.db["ag_eval_horizon_labels"].find_one(
                {
                    "subject_id": subject["subject_id"],
                    "horizon": "10D",
                    "anchor_type": "DECISION_CLOSE",
                    "status": "CALCULATED",
                }
            )
        )
        return HorizonLabel.model_validate(label) if label else None

    async def run_historical_replay(
        self,
        experiment_id: str,
        dataset_manifest_id: str,
        *,
        split_id: str | None = None,
        run_type: str = "HISTORICAL_REPLAY",
        created_by: str,
        minimum_samples: int | None = None,
        now: datetime | None = None,
    ) -> tuple[ExperimentRun, ExperimentRunResult]:
        now = now or datetime.utcnow()
        definition = await self.registry.validate(experiment_id)
        if not definition.execution_supported:
            raise ValueError("UNSUPPORTED_COMPONENT_ADAPTER")
        manifest = await self.datasets.get(dataset_manifest_id)
        if manifest.experiment_id != experiment_id:
            raise ValueError("manifest belongs to another experiment")
        split = await self._split(split_id)
        if split and split.dataset_manifest_id != dataset_manifest_id:
            raise ValueError("time split belongs to another manifest")
        baseline = await self.registry.component_version(
            definition.baseline_version_ref
        )
        challenger = await self.registry.component_version(
            definition.challenger_version_ref
        )
        commit = _git_value("rev-parse", "HEAD")
        tree_hash = _git_value("rev-parse", "HEAD^{tree}")
        config_hash = experiment_hash(
            {
                "replay_policy": self.policy,
                "robustness_policy": robustness_policy(),
                "baseline": baseline.payload_hash,
                "challenger": challenger.payload_hash,
            }
        )
        environment_hash = experiment_hash(
            {
                "python": platform.python_version(),
                "platform": platform.system(),
                "replay_engine": "historical-replay-v1",
            }
        )
        input_payload = {
            "experiment_id": experiment_id,
            "dataset_manifest_id": dataset_manifest_id,
            "split_id": split_id,
            "run_type": run_type,
            "baseline_version_ref": baseline.version_ref,
            "baseline_hash": baseline.payload_hash,
            "challenger_version_ref": challenger.version_ref,
            "challenger_hash": challenger.payload_hash,
            "manifest_hash": manifest.manifest_hash,
            "code_commit": commit,
            "code_tree_hash": tree_hash,
            "config_hash": config_hash,
            "environment_hash": environment_hash,
        }
        input_hash = experiment_hash(input_payload)
        run_id = str(
            uuid5(
                NAMESPACE_URL,
                f"alphaguard:experiment-run:{input_hash}",
            )
        )
        existing = await self.repository.get("runs", {"run_id": run_id})
        if existing and existing.get("status") in {
            "COMPLETED",
            "INSUFFICIENT_DATA",
        }:
            result_raw = await self.repository.get(
                "run_results", {"run_id": run_id}
            )
            if result_raw is None:
                raise ValueError("terminal run is missing immutable result")
            return (
                ExperimentRun.model_validate(existing),
                ExperimentRunResult.model_validate(result_raw),
            )
        attempt = int(existing.get("attempt_number", 0)) + 1 if existing else 1
        run = ExperimentRun(
            run_id=run_id,
            experiment_id=experiment_id,
            dataset_manifest_id=dataset_manifest_id,
            split_id=split_id,
            run_type=run_type,
            status="RUNNING",
            champion_version_refs={
                definition.component_key: baseline.version_ref
            },
            challenger_version_refs={
                definition.component_key: challenger.version_ref
            },
            code_commit=commit,
            code_tree_hash=tree_hash,
            config_hash=config_hash,
            environment_hash=environment_hash,
            reproducibility="DETERMINISTIC",
            attempt_number=attempt,
            started_at=now,
            completed_at=None,
            input_hash=input_hash,
            result_hash=None,
            error_type=None,
            error_message=None,
            created_by=created_by,
            created_at=existing.get("created_at", now) if existing else now,
        )
        await self.db["ag_exp_runs"].replace_one(
            {"run_id": run_id},
            experiment_document(run),
            upsert=True,
        )
        await self.audit.record(
            "EXPERIMENT_RUN_STARTED",
            f"{run_type} started in experiment-only namespace",
            experiment_id=experiment_id,
            run_id=run_id,
            dataset_manifest_id=dataset_manifest_id,
            split_id=split_id,
            baseline_version_ref=baseline.version_ref,
            challenger_version_ref=challenger.version_ref,
            input_hash=input_hash,
        )
        snapshot_documents = await self.db["ag_evidence_snapshots"].find(
            {"snapshot_id": {"$in": manifest.snapshot_ids}}
        ).to_list(length=None)
        snapshot_documents.sort(
            key=lambda item: (item["trade_date"], item["snapshot_id"])
        )
        if split:
            snapshot_documents = [
                item
                for item in snapshot_documents
                if split.test_start <= item["trade_date"] <= split.test_end
            ]
        champion_returns: list[Decimal] = []
        challenger_returns: list[Decimal] = []
        paired_differences: list[Decimal] = []
        insufficient = 0
        outputs = []
        for snapshot_document in snapshot_documents:
            snapshot_id = str(snapshot_document["snapshot_id"])
            data = await self.resolver.resolve(snapshot_id)
            champion_output, challenger_output, difference = (
                self.adapter.run_pair(data, baseline, challenger)
            )
            # Outcome labels are loaded only after both decisions have been
            # produced from snapshot-time inputs.
            label = await self._mature_label(snapshot_id)
            label_ids = [label.label_id] if label else []
            if label is None or label.raw_forward_return is None:
                insufficient += 1
            else:
                champion_return = _aligned(
                    label.raw_forward_return,
                    _proposal_action(champion_output),
                )
                challenger_return = _aligned(
                    label.raw_forward_return,
                    _proposal_action(challenger_output),
                )
                champion_returns.append(champion_return)
                challenger_returns.append(challenger_return)
                paired_differences.append(challenger_return - champion_return)
            output_payload = {
                "experiment_id": experiment_id,
                "run_id": run_id,
                "run_type": run_type,
                "snapshot_id": snapshot_id,
                "symbol": data.snapshot.symbol,
                "market": data.snapshot.market,
                "trade_date": data.snapshot.trade_date,
                "decision_cutoff_at": data.snapshot.price_cutoff_at,
                "baseline_version_ref": baseline.version_ref,
                "challenger_version_ref": challenger.version_ref,
                "fixed_version_refs": {
                    "snapshot_factor_set": experiment_hash(
                        data.snapshot.factor_version_set
                    ),
                    "snapshot_strategy": (
                        data.snapshot.strategy_version or "legacy:none"
                    ),
                    "normal_model": (
                        data.snapshot.normal_model_version or "not-run"
                    ),
                    "top_model": (
                        data.snapshot.top_model_version or "not-run"
                    ),
                },
                "champion_output": champion_output,
                "challenger_output": challenger_output,
                "difference": difference,
                "comparable": True,
                "incomparability_reasons": [],
                "decision_input_refs": sorted(data.input_refs),
                "evaluation_label_ids": label_ids,
            }
            output_input_hash = experiment_hash(
                {
                    "run_input_hash": input_hash,
                    "snapshot_input_hash": data.input_hash,
                }
            )
            output_result_hash = experiment_hash(output_payload)
            output = ExperimentOutputPair(
                output_id=str(
                    uuid5(
                        NAMESPACE_URL,
                        f"alphaguard:experiment-output:{run_id}:{snapshot_id}",
                    )
                ),
                input_hash=output_input_hash,
                result_hash=output_result_hash,
                created_at=data.snapshot.price_cutoff_at,
                **output_payload,
            )
            stored, _ = await self.repository.save_immutable(
                "shadow_outputs",
                output,
                identity={"output_id": output.output_id},
                hash_field="result_hash",
            )
            outputs.append(stored)
        champion_metrics = _metrics(champion_returns)
        challenger_metrics = _metrics(challenger_returns)
        paired_metrics = {
            "paired_sample_count": len(paired_differences),
            "average_value_added": (
                sum(paired_differences, Decimal("0"))
                / Decimal(len(paired_differences))
                if paired_differences
                else None
            ),
            "positive_value_added_rate": (
                Decimal(sum(value > 0 for value in paired_differences))
                / Decimal(len(paired_differences))
                if paired_differences
                else None
            ),
            "champion_returns": champion_returns,
            "challenger_returns": challenger_returns,
            "paired_differences": paired_differences,
        }
        minimum = (
            int(minimum_samples)
            if minimum_samples is not None
            else int(self.policy["minimum_manifest_samples"])
        )
        status_flags = []
        if len(paired_differences) < minimum:
            status_flags.append("INSUFFICIENT_DATA")
        result_payload = {
            "run_id": run_id,
            "experiment_id": experiment_id,
            "sample_count": len(snapshot_documents),
            "eligible_sample_count": len(outputs),
            "executed_sample_count": max(
                champion_metrics["trade_count"],
                challenger_metrics["trade_count"],
            ),
            "insufficient_sample_count": insufficient,
            "gross_return": challenger_metrics["gross_return"],
            "net_return": challenger_metrics["net_return"],
            "max_drawdown": challenger_metrics["max_drawdown"],
            "return_drawdown_ratio": challenger_metrics[
                "return_drawdown_ratio"
            ],
            "trade_count": challenger_metrics["trade_count"],
            "win_rate": challenger_metrics["win_rate"],
            "profit_factor": challenger_metrics["profit_factor"],
            "turnover": None,
            "fee_drag_pct": None,
            "average_mfe": None,
            "average_mae": None,
            "regime_breakdown": {},
            "horizon_breakdown": {"10D": paired_metrics},
            "top_trade_contribution_pct": challenger_metrics[
                "top_trade_contribution_pct"
            ],
            "top_five_trade_contribution_pct": challenger_metrics[
                "top_five_trade_contribution_pct"
            ],
            "champion_metrics": champion_metrics,
            "challenger_metrics": challenger_metrics,
            "paired_metrics": paired_metrics,
            "status_flags": status_flags,
            "input_hash": input_hash,
        }
        result_hash = experiment_hash(result_payload)
        result = ExperimentRunResult(
            result_id=str(
                uuid5(
                    NAMESPACE_URL,
                    f"alphaguard:experiment-result:{run_id}:{result_hash}",
                )
            ),
            result_hash=result_hash,
            calculated_at=now,
            **result_payload,
        )
        stored_result, _ = await self.repository.save_immutable(
            "run_results",
            result,
            identity={"run_id": run_id},
            hash_field="result_hash",
        )
        terminal_status = (
            "INSUFFICIENT_DATA" if status_flags else "COMPLETED"
        )
        completed = run.model_copy(
            update={
                "status": terminal_status,
                "completed_at": now,
                "result_hash": result_hash,
            }
        )
        await self.db["ag_exp_runs"].replace_one(
            {"run_id": run_id}, experiment_document(completed)
        )
        await self.audit.record(
            (
                "EXPERIMENT_RUN_INSUFFICIENT_DATA"
                if terminal_status == "INSUFFICIENT_DATA"
                else "EXPERIMENT_RUN_COMPLETED"
            ),
            f"{run_type} finished with {len(paired_differences)} mature pairs",
            experiment_id=experiment_id,
            run_id=run_id,
            dataset_manifest_id=dataset_manifest_id,
            split_id=split_id,
            input_hash=input_hash,
            result_hash=result_hash,
        )
        return completed, stored_result
