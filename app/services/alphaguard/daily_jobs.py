"""Scheduler entry for the canonical AlphaGuard MVP daily run."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import subprocess

from app.core.database import get_mongo_db, get_redis_client
from app.services.alphaguard.candidate_recommendation_service import (
    CandidateRecommendationService,
)
from app.services.alphaguard.daily_run_service import AlphaGuardDailyRunService
from app.services.alphaguard.daily_stage_executor import ProductionDailyStageExecutor
from tradingagents.alphaguard.operations_schemas import operations_hash


ROOT = Path(__file__).resolve().parents[3]


def daily_input_version() -> str:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()
    except Exception:
        commit = "unknown"
    config_paths = sorted((ROOT / "config" / "alphaguard").rglob("*.yaml"))
    config_hash = operations_hash(
        {
            str(path.relative_to(ROOT)): path.read_text(encoding="utf-8")
            for path in config_paths
        }
    )
    return f"{commit}:{config_hash[:16]}"


async def scheduled_alphaguard_daily_run() -> dict:
    from app.services.scheduler_service import _scheduler_instance

    db = get_mongo_db()
    trading_date = await CandidateRecommendationService(db).resolve_latest_trade_date()
    service = AlphaGuardDailyRunService(
        db,
        executor=ProductionDailyStageExecutor(
            db,
            redis_client=get_redis_client(),
            scheduler=_scheduler_instance,
        ),
    )
    summary = await service.run(
        trading_date=trading_date,
        input_version=daily_input_version(),
        resume=True,
    )
    return {
        "daily_run_id": summary.daily_run_id,
        "trading_date": trading_date.isoformat(),
        "status": summary.status,
        "created_count": summary.created_count,
        "reused_count": summary.reused_count,
        "completed_at": datetime.utcnow().isoformat(),
        "live_execution_allowed": False,
    }
