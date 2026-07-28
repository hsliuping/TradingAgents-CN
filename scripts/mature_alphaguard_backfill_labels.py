#!/usr/bin/env python3
"""Mature canonical 20D labels from persisted QFQ; dry-run by default."""

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
from app.services.alphaguard.backfill_label_maturity_service import (
    BackfillLabelMaturityService,
)


async def main(args: argparse.Namespace) -> None:
    client = AsyncIOMotorClient(
        settings.MONGO_URI,
        serverSelectionTimeoutMS=settings.MONGO_SERVER_SELECTION_TIMEOUT_MS,
    )
    try:
        await client.admin.command("ping")
        service = BackfillLabelMaturityService(client[settings.MONGO_DB])
        if args.recover_invalid_incomplete:
            result = await service.recover_invalid_incomplete_to_pending(
                backfill_run_id=args.backfill_run_id,
                as_of_trade_date=args.as_of_trade_date,
                execute=args.execute,
            )
        else:
            result = await service.mature(
                backfill_run_id=args.backfill_run_id,
                as_of_trade_date=args.as_of_trade_date,
                execute=args.execute,
            )
        display = dict(result)
        display.pop("terminal_label_hashes_before", None)
        print(json.dumps(display, ensure_ascii=False, default=str, indent=2))
        if not args.execute:
            print("dry-run: no HorizonLabel was modified")
    finally:
        client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--backfill-run-id", required=True)
    parser.add_argument(
        "--as-of-trade-date",
        type=date.fromisoformat,
        required=True,
    )
    parser.add_argument("--execute", action="store_true")
    parser.add_argument(
        "--recover-invalid-incomplete",
        action="store_true",
        help=(
            "compare-and-set only labels terminalized by the version-lock "
            "preflight defect back to PENDING"
        ),
    )
    asyncio.run(main(parser.parse_args()))
