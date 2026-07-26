"""Time-ordered holdout and walk-forward split construction."""

from __future__ import annotations

from datetime import date, datetime
from uuid import NAMESPACE_URL, uuid5

from app.services.alphaguard.experiment_audit_service import ExperimentAuditService
from app.services.alphaguard.experiment_config import replay_policy
from app.services.alphaguard.experiment_dataset_service import (
    ExperimentDatasetService,
)
from app.services.alphaguard.experiment_repository import ExperimentRepository
from tradingagents.alphaguard.experiment_schemas import (
    TimeSeriesSplitDefinition,
    experiment_hash,
)


class TimeSeriesSplitService:
    def __init__(self, db):
        self.db = db
        self.datasets = ExperimentDatasetService(db)
        self.repository = ExperimentRepository(db)
        self.audit = ExperimentAuditService(db)
        self.policy = replay_policy()

    @staticmethod
    def build_windows(
        dates: list[date],
        *,
        method: str,
        train_size: int,
        validation_size: int,
        test_size: int,
        embargo_trading_days: int,
        folds: int = 1,
    ) -> list[dict[str, date | int | None]]:
        ordered = sorted(set(dates))
        if dates != sorted(dates):
            raise ValueError("time-series input cannot be randomly shuffled")
        if min(train_size, validation_size, test_size) <= 0:
            raise ValueError("time-series windows must be positive")
        windows = []
        cursor = train_size + validation_size + embargo_trading_days
        for fold in range(1, folds + 1):
            test_start_index = cursor
            test_end_index = test_start_index + test_size - 1
            if test_end_index >= len(ordered):
                break
            if method == "ANCHORED_HOLDOUT" and fold > 1:
                break
            if method == "ROLLING_WALK_FORWARD":
                train_start_index = (fold - 1) * test_size
                train_end_index = train_start_index + train_size - 1
            elif method in {"ANCHORED_HOLDOUT", "EXPANDING_WALK_FORWARD"}:
                train_start_index = 0
                train_end_index = train_size - 1 + (
                    (fold - 1) * test_size
                    if method == "EXPANDING_WALK_FORWARD"
                    else 0
                )
            else:
                raise ValueError(f"unsupported time split method: {method}")
            validation_start_index = train_end_index + 1
            validation_end_index = validation_start_index + validation_size - 1
            test_start_index = validation_end_index + 1 + embargo_trading_days
            test_end_index = test_start_index + test_size - 1
            if test_end_index >= len(ordered):
                break
            windows.append(
                {
                    "fold_number": fold,
                    "train_start": ordered[train_start_index],
                    "train_end": ordered[train_end_index],
                    "validation_start": ordered[validation_start_index],
                    "validation_end": ordered[validation_end_index],
                    "test_start": ordered[test_start_index],
                    "test_end": ordered[test_end_index],
                }
            )
            cursor = test_end_index + 1
        return windows

    async def create(
        self,
        dataset_manifest_id: str,
        *,
        method: str,
        train_size: int | None = None,
        validation_size: int | None = None,
        test_size: int | None = None,
        embargo_trading_days: int | None = None,
        folds: int = 1,
        now: datetime | None = None,
    ) -> list[TimeSeriesSplitDefinition]:
        now = now or datetime.utcnow()
        manifest = await self.datasets.get(dataset_manifest_id)
        documents = await self.db["ag_evidence_snapshots"].find(
            {"snapshot_id": {"$in": manifest.snapshot_ids}}
        ).to_list(length=None)
        dates = sorted(item["trade_date"] for item in documents)
        train_size = train_size or int(self.policy["minimum_train_samples"])
        validation_size = validation_size or int(
            self.policy["minimum_validation_samples"]
        )
        test_size = test_size or int(self.policy["minimum_test_samples"])
        embargo = (
            embargo_trading_days
            if embargo_trading_days is not None
            else int(self.policy["default_embargo_trading_days"])
        )
        if self.policy["purge_overlapping_horizons"]:
            # A shorter user-supplied embargo must not reopen label overlap.
            # The policy horizon is expressed in ordered trading observations,
            # never calendar days.
            embargo = max(
                embargo,
                int(self.policy["maximum_label_horizon_trading_days"]),
            )
        windows = self.build_windows(
            dates,
            method=method,
            train_size=train_size,
            validation_size=validation_size,
            test_size=test_size,
            embargo_trading_days=embargo,
            folds=folds,
        )
        if not windows:
            return []
        results = []
        for window in windows:
            payload = {
                "dataset_manifest_id": dataset_manifest_id,
                "method": method,
                "train_start": window["train_start"],
                "train_end": window["train_end"],
                "validation_start": window["validation_start"],
                "validation_end": window["validation_end"],
                "test_start": window["test_start"],
                "test_end": window["test_end"],
                "embargo_trading_days": embargo,
                "purge_overlapping_horizons": bool(
                    self.policy["purge_overlapping_horizons"]
                ),
                "fold_number": window["fold_number"],
            }
            split_hash = experiment_hash(payload)
            split = TimeSeriesSplitDefinition(
                split_id=str(
                    uuid5(
                        NAMESPACE_URL,
                        f"alphaguard:time-split:{split_hash}",
                    )
                ),
                split_hash=split_hash,
                created_at=now,
                **payload,
            )
            stored, created = await self.repository.save_immutable(
                "time_splits",
                split,
                identity={"split_id": split.split_id},
                hash_field="split_hash",
            )
            results.append(stored)
            if created:
                await self.audit.record(
                    "TIME_SPLIT_CREATED",
                    f"{method} fold {stored.fold_number} created without shuffle",
                    dataset_manifest_id=dataset_manifest_id,
                    split_id=stored.split_id,
                    input_hash=stored.split_hash,
                )
        return results


class WalkForwardValidationService:
    """Run and retain every configured test fold; never select the best fold."""

    def __init__(self, db):
        self.db = db

    async def run_all(
        self,
        *,
        experiment_id: str,
        dataset_manifest_id: str,
        split_ids: list[str],
        created_by: str,
        minimum_samples: int | None = None,
    ) -> dict:
        from app.services.alphaguard.historical_replay_engine import (
            HistoricalReplayEngine,
        )

        if not split_ids:
            return {
                "status": "INSUFFICIENT_DATA",
                "folds": [],
                "reason": "no valid time-series folds",
            }
        engine = HistoricalReplayEngine(self.db)
        folds = []
        for split_id in split_ids:
            run, result = await engine.run_historical_replay(
                experiment_id,
                dataset_manifest_id,
                split_id=split_id,
                run_type="OUT_OF_SAMPLE",
                created_by=created_by,
                minimum_samples=minimum_samples,
            )
            folds.append(
                {
                    "split_id": split_id,
                    "run_id": run.run_id,
                    "status": run.status,
                    "result_id": result.result_id,
                    "net_return": result.net_return,
                    "sample_count": result.sample_count,
                    "result_hash": result.result_hash,
                }
            )
        return {
            "status": (
                "COMPLETED"
                if all(item["status"] == "COMPLETED" for item in folds)
                else "INSUFFICIENT_DATA"
            ),
            "folds": folds,
            "selected_best_fold": False,
            "all_fold_result_hash": experiment_hash(
                [item["result_hash"] for item in folds]
            ),
        }
