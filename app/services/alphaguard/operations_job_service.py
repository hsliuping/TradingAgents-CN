"""Controlled DB-backed operations queue; no arbitrary function execution."""

from __future__ import annotations

from datetime import date, datetime
from uuid import NAMESPACE_URL, uuid5

from app.services.alphaguard.evaluation_pipeline import EvaluationPipeline
from app.services.alphaguard.experiment_task_service import ExperimentTaskService
from app.services.alphaguard.operations_service import AlphaGuardOperationsService
from app.services.alphaguard.paper_jobs import reconcile_paper_accounts
from app.services.alphaguard.paper_storage import (
    clean_document,
    model_document,
    safe_error_message,
)
from tradingagents.alphaguard.operations_schemas import (
    OperationsJobRequest,
    operations_hash,
)


ALLOWED_OPERATIONS_JOBS = frozenset(
    {
        "HEALTH_CHECK",
        "DATA_READINESS_CHECK",
        "PAPER_RECONCILIATION",
        "EVALUATION_RECALCULATION",
        "EXPERIMENT_RECONCILIATION",
        "PROMOTION_SAGA_RECOVERY",
        "INTEGRITY_CHECK",
    }
)


class OperationsJobService:
    def __init__(self, db, *, redis_client=None, scheduler=None):
        self.db = db
        self.redis = redis_client
        self.scheduler = scheduler

    async def enqueue(
        self,
        job_name: str,
        *,
        requested_by: str,
        idempotency_key: str | None = None,
        payload: dict | None = None,
        now: datetime | None = None,
    ) -> tuple[OperationsJobRequest, bool]:
        now = now or datetime.utcnow()
        name = str(job_name).upper()
        if name not in ALLOWED_OPERATIONS_JOBS:
            raise ValueError(f"operation job is not allowed: {name}")
        safe_payload = self._validate_payload(name, payload or {})
        stable_key = idempotency_key or operations_hash(
            {
                "job_name": name,
                "requested_by": str(requested_by),
                "payload": safe_payload,
            }
        )
        existing = clean_document(
            await self.db["ag_ops_job_requests"].find_one(
                {"idempotency_key": stable_key}
            )
        )
        if existing:
            return OperationsJobRequest.model_validate(existing), False
        request = OperationsJobRequest(
            job_request_id=str(
                uuid5(NAMESPACE_URL, f"alphaguard:operations-job:{stable_key}")
            ),
            job_name=name,
            requested_by=str(requested_by),
            idempotency_key=stable_key,
            status="PENDING",
            payload=safe_payload,
            attempt_count=0,
            created_at=now,
            updated_at=now,
        )
        await self.db["ag_ops_job_requests"].insert_one(model_document(request))
        await self._event(
            "OPERATIONS_JOB_QUEUED",
            request,
            reason="controlled operation queued",
            now=now,
        )
        return request, True

    @staticmethod
    def _validate_payload(job_name: str, payload: dict) -> dict:
        allowed: dict[str, set[str]] = {
            "HEALTH_CHECK": set(),
            "DATA_READINESS_CHECK": set(),
            "PAPER_RECONCILIATION": set(),
            "EVALUATION_RECALCULATION": {"as_of_trade_date"},
            "EXPERIMENT_RECONCILIATION": {"as_of_trade_date"},
            "PROMOTION_SAGA_RECOVERY": set(),
            "INTEGRITY_CHECK": set(),
        }
        unexpected = set(payload) - allowed[job_name]
        if unexpected:
            raise ValueError(
                f"unsupported payload fields for {job_name}: {sorted(unexpected)}"
            )
        result = dict(payload)
        if "as_of_trade_date" in result:
            result["as_of_trade_date"] = date.fromisoformat(
                str(result["as_of_trade_date"])
            ).isoformat()
        return result

    async def process_pending(self, *, limit: int = 5) -> dict[str, int]:
        rows = await self.db["ag_ops_job_requests"].find(
            {"status": "PENDING"}
        ).sort("created_at", 1).limit(limit).to_list(length=limit)
        counts = {"completed": 0, "failed": 0}
        for raw in rows:
            request = OperationsJobRequest.model_validate(clean_document(raw))
            now = datetime.utcnow()
            running = request.model_copy(
                update={
                    "status": "RUNNING",
                    "attempt_count": request.attempt_count + 1,
                    "started_at": now,
                    "updated_at": now,
                }
            )
            claimed = await self.db["ag_ops_job_requests"].replace_one(
                {
                    "job_request_id": request.job_request_id,
                    "status": "PENDING",
                },
                model_document(running),
            )
            if claimed.matched_count != 1:
                continue
            try:
                result = await self._dispatch(running)
                terminal = running.model_copy(
                    update={
                        "status": "COMPLETED",
                        "result": result,
                        "finished_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow(),
                    }
                )
                counts["completed"] += 1
                event_type = "OPERATIONS_JOB_COMPLETED"
            except Exception as exc:
                terminal = running.model_copy(
                    update={
                        "status": "FAILED",
                        "error_code": type(exc).__name__.upper(),
                        "sanitized_message": safe_error_message(exc),
                        "finished_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow(),
                    }
                )
                counts["failed"] += 1
                event_type = "OPERATIONS_JOB_FAILED"
            await self.db["ag_ops_job_requests"].replace_one(
                {"job_request_id": request.job_request_id},
                model_document(terminal),
            )
            await self._event(
                event_type,
                terminal,
                reason=terminal.sanitized_message or terminal.status,
                now=terminal.finished_at or datetime.utcnow(),
            )
        return counts

    async def _dispatch(self, request: OperationsJobRequest) -> dict:
        operations = AlphaGuardOperationsService(
            self.db, redis_client=self.redis, scheduler=self.scheduler
        )
        if request.job_name == "HEALTH_CHECK":
            report = await operations.readiness()
            return {
                "report_id": report.report_id,
                "overall_status": report.overall_status,
                "report_hash": report.report_hash,
            }
        if request.job_name == "DATA_READINESS_CHECK":
            data = await operations.data_readiness()
            return {
                "components": len(data),
                "not_ready": sum(item.status != "READY" for item in data),
            }
        if request.job_name == "PAPER_RECONCILIATION":
            return await reconcile_paper_accounts()
        if request.job_name == "EVALUATION_RECALCULATION":
            as_of = date.fromisoformat(request.payload["as_of_trade_date"])
            run, created = await EvaluationPipeline(self.db).schedule(
                as_of_trade_date=as_of,
                user_id=None,
            )
            return {
                "evaluation_job_id": run.evaluation_job_id,
                "created": created,
                "status": run.status,
            }
        if request.job_name in {
            "EXPERIMENT_RECONCILIATION",
            "PROMOTION_SAGA_RECOVERY",
        }:
            job_type = (
                "EXPERIMENT_RECONCILIATION"
                if request.job_name == "EXPERIMENT_RECONCILIATION"
                else "PROMOTION_SAGA_RECOVERY"
            )
            payload = (
                {"as_of_trade_date": request.payload["as_of_trade_date"]}
                if job_type == "EXPERIMENT_RECONCILIATION"
                else {}
            )
            task = await ExperimentTaskService(self.db).enqueue(
                job_type,
                experiment_id=None,
                payload=payload,
                requested_by=request.requested_by,
            )
            return {"task_run_id": task.task_run_id, "status": task.status}
        if request.job_name == "INTEGRITY_CHECK":
            return await operations.integrity()
        raise ValueError(f"unsupported operation job: {request.job_name}")

    async def _event(
        self,
        event_type: str,
        request: OperationsJobRequest,
        *,
        reason: str,
        now: datetime,
    ) -> None:
        event_key = operations_hash(
            {
                "event_type": event_type,
                "job_request_id": request.job_request_id,
                "attempt_count": request.attempt_count,
            }
        )
        await self.db["ag_ops_events"].update_one(
            {"event_id": event_key},
            {
                "$setOnInsert": {
                    "event_id": event_key,
                    "event_type": event_type,
                    "job_request_id": request.job_request_id,
                    "actor_id": request.requested_by,
                    "reason": reason,
                    "created_at": now,
                    "schema_version": "alphaguard-operations-v1",
                }
            },
            upsert=True,
        )


async def process_operations_job_requests() -> dict[str, int]:
    from app.core.database import get_mongo_db, get_redis_client
    from app.services.scheduler_service import _scheduler_instance

    return await OperationsJobService(
        get_mongo_db(),
        redis_client=get_redis_client(),
        scheduler=_scheduler_instance,
    ).process_pending()

