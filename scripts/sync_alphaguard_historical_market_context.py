#!/usr/bin/env python3
"""Synchronize real historical MarketContext; dry-run unless --execute is set."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import date, datetime
from pathlib import Path

from motor.motor_asyncio import AsyncIOMotorClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import settings
from app.services.alphaguard.historical_backfill_service import (
    HistoricalBackfillService,
)
from app.services.alphaguard.historical_market_context_service import (
    BaoStockHistoricalMarketProvider,
    HistoricalMarketContextService,
)


def _progress(payload: dict) -> None:
    print(
        json.dumps(
            {"progress_at": datetime.utcnow().isoformat(), **payload},
            ensure_ascii=False,
            default=str,
        ),
        flush=True,
    )


async def main(args: argparse.Namespace) -> None:
    client = AsyncIOMotorClient(
        settings.MONGO_URI,
        serverSelectionTimeoutMS=settings.MONGO_SERVER_SELECTION_TIMEOUT_MS,
    )
    try:
        await client.admin.command("ping")
        db = client[settings.MONGO_DB]
        dates = await HistoricalBackfillService(db).select_trade_dates(
            start_trade_date=args.start,
            end_trade_date=args.end,
            sampling_method=args.sampling_method,
        )
        capability = BaoStockHistoricalMarketProvider.capability_check()
        existing = await db["ag_research_market_contexts"].count_documents(
            {
                "market": "CN",
                "trade_date": {
                    "$gte": datetime.combine(args.start, datetime.min.time()),
                    "$lte": datetime.combine(args.end, datetime.min.time()),
                },
            }
        )
        plan = {
            "write": args.execute,
            "start_trade_date": args.start,
            "end_trade_date": args.end,
            "sampling_method": args.sampling_method,
            "selected_trade_date_count": len(dates),
            "selected_trade_dates": dates,
            "provider_capability": capability,
            "existing_context_count_in_range": existing,
        }
        print(json.dumps(plan, ensure_ascii=False, default=str, indent=2))
        if not args.execute:
            print("dry-run: no provider fetch or MongoDB writes performed")
            return
        result = await HistoricalMarketContextService(db).sync(
            selected_dates=dates,
            timeout_seconds=args.timeout_seconds,
            progress=_progress,
        )
        printable = {key: value for key, value in result.items() if key != "contexts"}
        printable["context_ids"] = [item.context_id for item in result["contexts"]]
        print(json.dumps(printable, ensure_ascii=False, default=str, indent=2))
    finally:
        client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument(
        "--sampling-method",
        choices=["WEEKLY_LAST_SESSION", "DAILY"],
        default="WEEKLY_LAST_SESSION",
    )
    parser.add_argument("--timeout-seconds", type=float, default=7200)
    parser.add_argument("--execute", action="store_true")
    asyncio.run(main(parser.parse_args()))
