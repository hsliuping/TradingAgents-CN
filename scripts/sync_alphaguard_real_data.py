#!/usr/bin/env python3
"""Dry-run-first entrypoint for versioned AlphaGuard real-data activation."""

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
from app.services.alphaguard.real_data_ingestion_service import (
    RealDataIngestionService,
)
from app.services.alphaguard.real_data_candidate_service import (
    CandidateRealDataService,
)


async def main(args: argparse.Namespace) -> None:
    client = AsyncIOMotorClient(
        settings.MONGO_URI,
        serverSelectionTimeoutMS=settings.MONGO_SERVER_SELECTION_TIMEOUT_MS,
    )
    try:
        await client.admin.command("ping")
        db = client[settings.MONGO_DB]
        if args.domain == "TRADING_CALENDAR":
            result = await RealDataIngestionService(db).sync_calendar(
                start=args.start,
                end=args.end,
                execute=args.execute,
            )
        else:
            if not args.symbol:
                raise SystemExit(
                    "CANDIDATE_REAL_DATA requires one or more user-selected --symbol"
                )
            result = {
                "domain": "CANDIDATE_REAL_DATA",
                "write": args.execute,
                "results": [
                    await CandidateRealDataService(db).sync_candidate(
                        symbol=symbol,
                        start=args.start,
                        end=args.end,
                        execute=args.execute,
                    )
                    for symbol in args.symbol
                ],
            }
        print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
    finally:
        client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--domain",
        choices=["TRADING_CALENDAR", "CANDIDATE_REAL_DATA"],
        default="TRADING_CALENDAR",
    )
    parser.add_argument(
        "--symbol",
        action="append",
        help="explicit user-selected CN code; repeat for multiple candidates",
    )
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument("--execute", action="store_true")
    asyncio.run(main(parser.parse_args()))
