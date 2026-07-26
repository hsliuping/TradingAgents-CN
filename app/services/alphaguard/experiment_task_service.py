"""DB-backed, low-priority and idempotent PR-008 experiment task queue."""

from __future__ import annotations

from datetime import date, datetime
from uuid import NAMESPACE_URL, uuid5

from app.services.alphaguard.champion_comparison_service import (
    ChampionComparisonService,
)
from app.services.alphaguard.champion_promotion_service import (
    ChampionPromotionService,
)
from app.services.alphaguard.experiment_reconciliation import (
    ExperimentReconciliation,
)
from app.services.alphaguard.experiment_repository import experiment_document
from app.services.alphaguard.experiment_risk_review_service import (
    ExperimentRiskReviewService,
)
from app.services.alphaguard.historical_replay_engine import (
    HistoricalReplayEngine,
)
from app.services.alphaguard.leakage_audit_service import LeakageAuditService
from app.services.alphaguard.paper_storage import clean_document, safe_error_message
from app.services.alphaguard.robustness_test_service import RobustnessTestService
from app.services.alphaguard.shadow_experiment_service import (
    ShadowExperimentService,
)
from app.services.alphaguard.walk_forward_validation import (
    WalkForwardValidationService,
)
from tradingagents.alphaguard.experiment_schemas import (
    ExperimentTaskRun,
    experiment_hash,
)


class ExperimentTaskService:
    def __init__(self, db):
        self.db = db

    async def enqueue(
        self,
        job_type: str,
        *,
        experiment_id: str | None,
        payload: dict,
        requested_by: str,
        trade_date: date | None = None,
        now: datetime | None = None,
    ) -> ExperimentTaskRun:
        now = now or datetime.utcnow()
        idempotency_key = experiment_hash(
            {
                "job_type": job_type,
                "experiment_id": experiment_id,
                "payload": payload,
            }
        )
        existing = clean_document(
            await self.db["ag_exp_task_runs"].find_one(
                {"idempotency_key": idempotency_key}
            )
        )
        if existing:
            return ExperimentTaskRun.model_validate(existing)
        task = ExperimentTaskRun(
            task_run_id=str(
                uuid5(
                    NAMESPACE_URL,
                    f"alphaguard:experiment-task:{idempotency_key}",
                )
            ),
            job_type=job_type,
            experiment_id=experiment_id,
            trade_date=trade_date,
            idempotency_key=idempotency_key,
            status="PENDING",
            attempt_count=1,
            result={"request": payload, "requested_by": str(requested_by)},
            created_at=now,
            updated_at=now,
        )
        await self.db["ag_exp_task_runs"].insert_one(
            experiment_document(task)
        )
        return task

    async def process(
        self,
        *,
        job_types: set[str] | None = None,
        limit: int = 5,
    ) -> dict[str, int]:
        query: dict = {"status": "PENDING"}
        if job_types:
            query["job_type"] = {"$in": sorted(job_types)}
        pending = await self.db["ag_exp_task_runs"].find(query).sort(
            "created_at", 1
        ).limit(limit).to_list(length=limit)
        counts = {"completed": 0, "failed": 0}
        for raw in pending:
            item = ExperimentTaskRun.model_validate(clean_document(raw))
            running = item.model_copy(
                update={
                    "status": "RUNNING",
                    "started_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                }
            )
            claimed = await self.db["ag_exp_task_runs"].replace_one(
                {"task_run_id": item.task_run_id, "status": "PENDING"},
                experiment_document(running),
            )
            if claimed.matched_count != 1:
                continue
            try:
                result = await self._dispatch(running)
                terminal = running.model_copy(
                    update={
                        "status": "COMPLETED",
                        "result": {
                            **(running.result or {}),
                            "response": result,
                        },
                        "finished_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow(),
                    }
                )
                counts["completed"] += 1
            except Exception as exc:
                terminal = running.model_copy(
                    update={
                        "status": "FAILED",
                        "error": safe_error_message(exc),
                        "finished_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow(),
                    }
                )
                counts["failed"] += 1
            await self.db["ag_exp_task_runs"].replace_one(
                {"task_run_id": item.task_run_id},
                experiment_document(terminal),
            )
        return counts

    async def _dispatch(self, task: ExperimentTaskRun) -> dict:
        payload = dict((task.result or {}).get("request") or {})
        requested_by = str((task.result or {}).get("requested_by") or "worker")
        if task.job_type == "HISTORICAL_REPLAY":
            run, result = await HistoricalReplayEngine(
                self.db
            ).run_historical_replay(
                task.experiment_id or "",
                payload["dataset_manifest_id"],
                split_id=payload.get("split_id"),
                created_by=requested_by,
            )
            return {"run_id": run.run_id, "result_id": result.result_id}
        if task.job_type == "WALK_FORWARD":
            return await WalkForwardValidationService(self.db).run_all(
                experiment_id=task.experiment_id or "",
                dataset_manifest_id=payload["dataset_manifest_id"],
                split_ids=payload["split_ids"],
                created_by=requested_by,
            )
        if task.job_type == "LEAKAGE_AUDIT":
            report = await LeakageAuditService(self.db).audit(payload["run_id"])
            return {"leakage_audit_id": report.leakage_audit_id, "status": report.status}
        if task.job_type == "ROBUSTNESS":
            report = await RobustnessTestService(self.db).run(payload["run_id"])
            return {"robustness_report_id": report.robustness_report_id, "status": report.status}
        if task.job_type == "SHADOW_SNAPSHOT":
            output = await ShadowExperimentService(self.db).process_snapshot(
                payload["shadow_run_id"], payload["snapshot_id"]
            )
            return {"output_id": output.output_id, "result_hash": output.result_hash}
        if task.job_type == "COMPARISON":
            report = await ChampionComparisonService(self.db).create(
                task.experiment_id or ""
            )
            return {"comparison_report_id": report.comparison_report_id, "status": report.status}
        if task.job_type == "RISK_REVIEW":
            review = await ExperimentRiskReviewService(self.db).review(
                task.experiment_id or "",
                comparison_report_id=payload["comparison_report_id"],
            )
            return {"risk_review_id": review.review_id, "status": review.status}
        if task.job_type == "PROMOTION_SAGA_RECOVERY":
            return await ChampionPromotionService(
                self.db
            ).recover_incomplete_sagas()
        if task.job_type == "EXPERIMENT_RECONCILIATION":
            return await ExperimentReconciliation(self.db).reconcile(
                as_of_trade_date=date.fromisoformat(payload["as_of_trade_date"])
            )
        raise ValueError(f"unsupported experiment task: {task.job_type}")
