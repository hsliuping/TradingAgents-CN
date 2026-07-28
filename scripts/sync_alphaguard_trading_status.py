#!/usr/bin/env python3
"""Derive versioned daily CN trading status; dry-run by default."""

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
from app.services.alphaguard.cn_trading_status_service import (
    CNTradingStatusService,
)


async def main(args: argparse.Namespace) -> None:
    client = AsyncIOMotorClient(
        settings.MONGO_URI,
        serverSelectionTimeoutMS=settings.MONGO_SERVER_SELECTION_TIMEOUT_MS,
    )
    try:
        await client.admin.command("ping")
        result = await CNTradingStatusService(client[settings.MONGO_DB]).sync(
            symbols=args.symbol,
            trade_date=args.trade_date,
            execute=args.execute,
        )
        print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
        if not args.execute:
            print("dry-run: no trading-status rows were written")
    finally:
        client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", action="append", required=True)
    parser.add_argument("--trade-date", type=date.fromisoformat, required=True)
    parser.add_argument("--execute", action="store_true")
    asyncio.run(main(parser.parse_args()))
