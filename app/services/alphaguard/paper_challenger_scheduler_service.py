"""Create idempotent PAPER_CHALLENGER tasks from persisted production snapshots."""

from __future__ import annotations

from datetime import date, datetime

from app.services.alphaguard.experiment_task_service import ExperimentTaskService
from app.services.alphaguard.paper_storage import clean_document, mongo_date


def _trade_date(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


class PaperChallengerSchedulerService:
    def __init__(self, db):
        self.db = db
        self.tasks = ExperimentTaskService(db)

    async def enqueue_for_trade_date(self, trading_date: date) -> dict[str, int]:
        assignments = await self.db["ag_exp_challenger_assignments"].find(
            {
                "status": "ACTIVE",
                "activation_trade_date": {"$lte": mongo_date(trading_date)},
            }
        ).to_list(length=None)
        counts = {
            "active_assignments": len(assignments),
            "queued_or_reused": 0,
            "skipped_missing_candidate": 0,
        }
        for raw_assignment in assignments:
            assignment = clean_document(raw_assignment)
            definition = clean_document(
                await self.db["ag_exp_definitions"].find_one(
                    {
                        "experiment_id": assignment["experiment_id"],
                        "status": "CHALLENGER",
                    }
                )
            )
            if definition is None:
                continue
            snapshot_rows = await self.db["ag_evidence_snapshots"].find(
                {
                    "user_id": assignment["user_id"],
                    "market": "CN",
                    "evidence_contract_status": "COMPLETE",
                    "run_mode": {"$in": [None, "ACTUAL_PRODUCTION"]},
                }
            ).to_list(length=None)
            snapshots = [
                clean_document(item)
                for item in snapshot_rows
                if _trade_date(item.get("trade_date")) == trading_date
            ]
            snapshots.sort(key=lambda item: (str(item.get("symbol")), str(item.get("snapshot_id"))))
            for snapshot in snapshots:
                candidate = clean_document(
                    await self.db["ag_candidates"].find_one(
                        {
                            "user_id": assignment["user_id"],
                            "symbol": snapshot["symbol"],
                            "market": "CN",
                            "trade_date": snapshot["trade_date"],
                        }
                    )
                )
                if candidate is None:
                    counts["skipped_missing_candidate"] += 1
                    continue
                await self.tasks.enqueue(
                    "PAPER_CHALLENGER",
                    experiment_id=assignment["experiment_id"],
                    payload={
                        "challenger_version_id": assignment.get("challenger_version_id"),
                        "trading_date": trading_date.isoformat(),
                        "candidate_id": candidate["candidate_id"],
                        "snapshot_id": snapshot["snapshot_id"],
                    },
                    requested_by="scheduler",
                    trade_date=trading_date,
                )
                counts["queued_or_reused"] += 1
        return counts
