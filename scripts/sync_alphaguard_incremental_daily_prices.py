#!/usr/bin/env python3
"""Probe and persist one completed CN daily session; dry-run by default."""

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
from app.services.alphaguard.incremental_daily_price_service import (
    IncrementalDailyPriceService,
)


async def main(args: argparse.Namespace) -> None:
    client = AsyncIOMotorClient(
        settings.MONGO_URI,
        serverSelectionTimeoutMS=settings.MONGO_SERVER_SELECTION_TIMEOUT_MS,
    )
    try:
        await client.admin.command("ping")
        service = IncrementalDailyPriceService(client[settings.MONGO_DB])
        resolutions = await service.probe(
            symbols=args.symbol,
            trade_date=args.trade_date,
        )
        result: dict = {
            "trade_date": args.trade_date,
            "probe_results": [item.report() for item in resolutions],
        }
        if args.compare_existing:
            result["existing_comparison"] = await service.compare_existing(
                resolutions=resolutions
            )
        if not args.probe_only:
            result["sync"] = await service.sync(
                symbols=args.symbol,
                trade_date=args.trade_date,
                execute=args.execute,
                resolutions=resolutions,
            )
            result["local_gate"] = await service.local_gate(
                symbols=args.symbol,
                trade_date=args.trade_date,
            )
        print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
        if not args.execute:
            print("dry-run: provider probes completed; no price rows were written")
    finally:
        client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", action="append", required=True)
    parser.add_argument("--trade-date", type=date.fromisoformat, required=True)
    parser.add_argument("--compare-existing", action="store_true")
    parser.add_argument("--probe-only", action="store_true")
    parser.add_argument("--execute", action="store_true")
    asyncio.run(main(parser.parse_args()))
