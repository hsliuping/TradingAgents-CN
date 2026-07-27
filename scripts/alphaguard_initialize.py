#!/usr/bin/env python3
"""Safe AlphaGuard initialization orchestrator; dry-run unless --execute."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from motor.motor_asyncio import AsyncIOMotorClient
from redis.asyncio import Redis

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.alphaguard_config import validate_alphaguard_startup_safety  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.services.alphaguard.index_service import ensure_alphaguard_indexes  # noqa: E402
from app.services.alphaguard.operations_service import AlphaGuardOperationsService  # noqa: E402
from tradingagents.alphaguard.mongo_indexes import ALPHAGUARD_INDEX_SPECS  # noqa: E402


async def run(*, execute: bool) -> int:
    validate_alphaguard_startup_safety()
    expected = sum(len(items) for items in ALPHAGUARD_INDEX_SPECS.values())
    print(
        f"database={settings.MONGO_DB} collections={len(ALPHAGUARD_INDEX_SPECS)} "
        f"indexes={expected}"
    )
    print("safety=PASS system_mode=SIM_AUTONOMOUS live_trading_enabled=false")
    print(
        "scope=create-only indexes plus read-only readiness; "
        "no sample data, accounts, orders, candidates, experiments, or champions created"
    )
    if not execute:
        print("dry-run: no writes performed; pass --execute to create missing indexes")
        return 0

    mongo = AsyncIOMotorClient(
        settings.MONGO_URI,
        serverSelectionTimeoutMS=settings.MONGO_SERVER_SELECTION_TIMEOUT_MS,
    )
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        await mongo.admin.command("ping")
        await redis.ping()
        db = mongo[settings.MONGO_DB]
        actions = await ensure_alphaguard_indexes(db)
        report = await AlphaGuardOperationsService(
            db, redis_client=redis, scheduler=None
        ).readiness(persist_alerts=False)
        print(
            f"created={sum(item.startswith('created ') for item in actions)} "
            f"unchanged={sum(item.startswith('unchanged ') for item in actions)}"
        )
        print(
            f"overall_status={report.overall_status} "
            f"paper_ready={str(report.paper_execution_ready).lower()} "
            f"live_ready=false"
        )
        for blocker in report.blocking_items:
            print(f"blocked {blocker}")
        return 0
    finally:
        await redis.aclose()
        mongo.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    raise SystemExit(asyncio.run(run(execute=parser.parse_args().execute)))
