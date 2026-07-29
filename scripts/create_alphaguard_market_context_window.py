#!/usr/bin/env python3
"""Create the immutable production MarketContext window; dry-run by default."""

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
from app.services.alphaguard.market_context_window_service import (
    MarketContextWindowService,
)


async def main(args: argparse.Namespace) -> None:
    client = AsyncIOMotorClient(
        settings.MONGO_URI,
        serverSelectionTimeoutMS=settings.MONGO_SERVER_SELECTION_TIMEOUT_MS,
    )
    try:
        await client.admin.command("ping")
        result = await MarketContextWindowService(
            client[settings.MONGO_DB]
        ).build(
            as_of_trade_date=args.trade_date,
            cutoff_at=args.cutoff_at,
            execute=args.execute,
            prior_session_count=args.prior_session_count,
        )
        print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
        if not args.execute:
            print("dry-run: no MarketContext window manifest was written")
    finally:
        client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--trade-date", type=date.fromisoformat, required=True)
    parser.add_argument("--cutoff-at", type=datetime.fromisoformat, required=True)
    parser.add_argument("--prior-session-count", type=int)
    parser.add_argument("--execute", action="store_true")
    asyncio.run(main(parser.parse_args()))
