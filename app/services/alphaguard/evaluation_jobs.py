"""Non-blocking, idempotent PR-007 evaluation Worker entry points."""

from __future__ import annotations

import logging
from datetime import date

from app.core.database import get_mongo_db
from app.services.alphaguard.evaluation_pipeline import EvaluationPipeline
from app.services.alphaguard.paper_storage import clean_document
from app.utils.timezone import now_tz


logger = logging.getLogger(__name__)


async def run_pending_evaluations(limit: int = 10) -> dict[str, int]:
    db = get_mongo_db()
    runs = await db["ag_eval_runs"].find(
        {"status": {"$in": ["PENDING", "FAILED"]}}
    ).sort("created_at", 1).limit(limit).to_list(length=limit)
    counts = {"completed": 0, "failed": 0}
    for raw in runs:
        run = clean_document(raw)
        try:
            await EvaluationPipeline(db).evaluate_trade_date(
                as_of_trade_date=run["as_of_trade_date"],
                user_id=run.get("user_id"),
            )
            counts["completed"] += 1
        except Exception:
            counts["failed"] += 1
            logger.exception(
                "PR-007 evaluation failed independently of decision/execution flows"
            )
    return counts


async def schedule_daily_evaluation(
    as_of_trade_date: date | None = None,
) -> dict[str, str | bool]:
    trade_date = as_of_trade_date or now_tz().date()
    run, created = await EvaluationPipeline(get_mongo_db()).schedule(
        as_of_trade_date=trade_date,
        user_id=None,
    )
    return {
        "evaluation_job_id": run.evaluation_job_id,
        "status": run.status,
        "created": created,
    }


# Explicit operational task names required by the PR-007 blueprint.  The
# unified evaluation run preserves the required ordering and idempotency.
evaluation_subject_discovery = run_pending_evaluations
horizon_label_update = run_pending_evaluations
counterfactual_evaluation = run_pending_evaluations
account_metric_calculation = run_pending_evaluations
paired_comparison_calculation = run_pending_evaluations
attribution_calculation = run_pending_evaluations
evaluation_reconciliation = run_pending_evaluations
