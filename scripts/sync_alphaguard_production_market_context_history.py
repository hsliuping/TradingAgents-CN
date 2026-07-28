#!/usr/bin/env python3
"""Backfill a fixed production MarketContext history; dry-run by default."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import date
from pathlib import Path

from motor.motor_asyncio import AsyncIOMotorClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import settings
from app.services.alphaguard.production_history_continuity_service import (
    ProductionHistoryContinuityService,
)


def progress(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, default=str), flush=True)


async def main(args: argparse.Namespace) -> None:
    client = AsyncIOMotorClient(
        settings.MONGO_URI,
        serverSelectionTimeoutMS=settings.MONGO_SERVER_SELECTION_TIMEOUT_MS,
    )
    try:
        await client.admin.command("ping")
        service = ProductionHistoryContinuityService(
            client[settings.MONGO_DB]
        )
        if args.audit_pending_labels:
            result = await service.audit_pending_20d(
                backfill_run_id=args.backfill_run_id
            )
        elif args.verify_regimes:
            result = await service.verify_locked_regimes(
                trade_date=args.through_trade_date
            )
        else:
            result = await service.sync(
                through_trade_date=args.through_trade_date,
                prior_session_count=args.prior_session_count,
                execute=args.execute,
                timeout_seconds=args.timeout_seconds,
                progress=progress,
            )
        print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
        if not args.execute:
            print("dry-run: no production or evaluation row was modified")
    finally:
        client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--through-trade-date",
        type=date.fromisoformat,
        default=date(2026, 7, 28),
    )
    parser.add_argument("--prior-session-count", type=int, default=120)
    parser.add_argument("--timeout-seconds", type=float, default=7200)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--audit-pending-labels", action="store_true")
    parser.add_argument("--verify-regimes", action="store_true")
    parser.add_argument(
        "--backfill-run-id",
        default="9b921ffa-71a5-578b-85e8-252b2f9cfca9",
    )
    asyncio.run(main(parser.parse_args()))
