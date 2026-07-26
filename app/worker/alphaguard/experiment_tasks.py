"""Scheduled PR-008 task entrypoints.

These run after production paper/evaluation work and failures never pause the
Champion production chain.
"""

from __future__ import annotations

from datetime import date, datetime

from app.core.database import get_mongo_db
from app.services.alphaguard.challenger_assignment_service import (
    ChallengerAssignmentService,
)
from app.services.alphaguard.experiment_task_service import ExperimentTaskService


async def _consume(job_types: set[str], limit: int = 3) -> dict[str, int]:
    return await ExperimentTaskService(get_mongo_db()).process(
        job_types=job_types, limit=limit
    )


async def experiment_run_consumer():
    return await _consume(
        {
            "HISTORICAL_REPLAY",
            "WALK_FORWARD",
            "LEAKAGE_AUDIT",
            "ROBUSTNESS",
            "COMPARISON",
            "RISK_REVIEW",
        }
    )


async def historical_replay_worker():
    return await _consume({"HISTORICAL_REPLAY"})


async def walk_forward_validation_worker():
    return await _consume({"WALK_FORWARD"})


async def leakage_audit_worker():
    return await _consume({"LEAKAGE_AUDIT"})


async def robustness_test_worker():
    return await _consume({"ROBUSTNESS"})


async def shadow_experiment_worker():
    return await _consume({"SHADOW_SNAPSHOT"})


async def challenger_monitor_worker():
    # It only completes naturally-flat CLOSING assignments; never liquidates.
    return await ChallengerAssignmentService(
        get_mongo_db()
    ).reconcile_closing()


async def comparison_report_worker():
    return await _consume({"COMPARISON"})


async def experiment_risk_review_worker():
    return await _consume({"RISK_REVIEW"})


async def promotion_saga_recovery_worker():
    service = ExperimentTaskService(get_mongo_db())
    await service.enqueue(
        "PROMOTION_SAGA_RECOVERY",
        experiment_id=None,
        payload={},
        requested_by="scheduler",
    )
    return await service.process(job_types={"PROMOTION_SAGA_RECOVERY"}, limit=1)


async def experiment_reconciliation_worker():
    service = ExperimentTaskService(get_mongo_db())
    await service.enqueue(
        "EXPERIMENT_RECONCILIATION",
        experiment_id=None,
        payload={"as_of_trade_date": date.today().isoformat()},
        requested_by="scheduler",
        trade_date=date.today(),
        now=datetime.utcnow(),
    )
    return await service.process(
        job_types={"EXPERIMENT_RECONCILIATION"}, limit=1
    )
