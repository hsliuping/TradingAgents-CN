#!/usr/bin/env python3
"""Complete targeted CN security-master facts; dry-run by default."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from motor.motor_asyncio import AsyncIOMotorClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import settings
from app.services.alphaguard.security_master_sync_service import (
    SecurityMasterSyncService,
)


async def main(args: argparse.Namespace) -> None:
    client = AsyncIOMotorClient(
        settings.MONGO_URI,
        serverSelectionTimeoutMS=settings.MONGO_SERVER_SELECTION_TIMEOUT_MS,
    )
    try:
        await client.admin.command("ping")
        result = await SecurityMasterSyncService(
            client[settings.MONGO_DB]
        ).sync(
            symbols=args.symbol,
            execute=args.execute,
        )
        print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
        if not args.execute:
            print("dry-run: no source audit or stock_basic_info row was written")
    finally:
        client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", action="append", required=True)
    parser.add_argument("--execute", action="store_true")
    asyncio.run(main(parser.parse_args()))
