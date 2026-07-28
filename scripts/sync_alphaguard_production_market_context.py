#!/usr/bin/env python3
"""Fresh, dry-run-first production MarketContext synchronization."""

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
from app.services.alphaguard.production_market_context_service import (
    ProductionMarketContextService,
)
from app.services.alphaguard.akshare_market_context_provider import (
    AKShareTencentMarketContextProvider,
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
        result = await ProductionMarketContextService(
            client[settings.MONGO_DB]
        ).sync(
            trade_date=args.trade_date,
            execute=args.execute,
            provider=(
                AKShareTencentMarketContextProvider()
                if args.provider == "akshare-tencent"
                else None
            ),
            timeout_seconds=args.timeout_seconds,
            progress=progress,
        )
        print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
        if not args.execute:
            print("dry-run: provider was checked; no production rows were written")
    finally:
        client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--trade-date", type=date.fromisoformat, required=True)
    parser.add_argument(
        "--provider",
        choices=["baostock", "akshare-tencent"],
        default="baostock",
    )
    parser.add_argument("--timeout-seconds", type=float, default=3600)
    parser.add_argument("--execute", action="store_true")
    asyncio.run(main(parser.parse_args()))
