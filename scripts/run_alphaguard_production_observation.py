#!/usr/bin/env python3
"""Run the existing persisted-data production chain; dry-run by default."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import date, datetime
from pathlib import Path

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import settings
from app.services.alphaguard.production_observation_service import (
    ProductionObservationService,
)


async def _admin_user_id(db, args: argparse.Namespace) -> str:
    clauses = []
    if args.user_id:
        clauses.extend([{"_id": args.user_id}, {"id": args.user_id}])
        if ObjectId.is_valid(args.user_id):
            clauses.append({"_id": ObjectId(args.user_id)})
    if args.username:
        clauses.append({"username": args.username})
    if not clauses:
        raise SystemExit("--user-id or --username is required")
    user = await db["users"].find_one({"$or": clauses})
    if (
        user is None
        or user.get("is_admin") is not True
        or user.get("is_active") is False
    ):
        raise SystemExit("production observation requires an active administrator")
    return str(user.get("id") or user.get("_id"))


async def main(args: argparse.Namespace) -> None:
    client = AsyncIOMotorClient(
        settings.MONGO_URI,
        serverSelectionTimeoutMS=settings.MONGO_SERVER_SELECTION_TIMEOUT_MS,
    )
    try:
        await client.admin.command("ping")
        db = client[settings.MONGO_DB]
        user_id = await _admin_user_id(db, args)
        result = await ProductionObservationService(db).run(
            user_id=user_id,
            symbols=args.symbol,
            trade_date=args.trade_date,
            cutoff_at=args.cutoff_at,
            execute=args.execute,
            trace_id=args.trace_id,
        )
        print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
        if not args.execute:
            print("dry-run: no Snapshot, Proposal, Decision, Outbox, or account row written")
    finally:
        client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id")
    parser.add_argument("--username")
    parser.add_argument("--symbol", action="append", required=True)
    parser.add_argument("--trade-date", type=date.fromisoformat, required=True)
    parser.add_argument("--cutoff-at", type=datetime.fromisoformat, required=True)
    parser.add_argument(
        "--trace-id",
        default="alphaguard-production-live-observation",
    )
    parser.add_argument("--execute", action="store_true")
    asyncio.run(main(parser.parse_args()))
