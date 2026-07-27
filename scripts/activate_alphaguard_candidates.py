#!/usr/bin/env python3
"""Dry-run-first activation of explicitly user-selected AlphaGuard candidates."""

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
from app.services.alphaguard.candidate_pool_service import CandidatePoolService
from app.services.alphaguard.real_data_candidate_service import (
    CandidateRealDataService,
)
from tradingagents.alphaguard.candidate_schemas import CandidateSource
from tradingagents.alphaguard.instruments import normalize_instrument


async def main(args: argparse.Namespace) -> None:
    symbols = list(dict.fromkeys(args.symbol))
    if not 3 <= len(symbols) <= 5:
        raise SystemExit("real activation requires exactly 3 to 5 user-selected codes")
    normalized = [normalize_instrument(symbol, "CN")[1] for symbol in symbols]
    cutoff_at = args.cutoff_at
    client = AsyncIOMotorClient(
        settings.MONGO_URI,
        serverSelectionTimeoutMS=settings.MONGO_SERVER_SELECTION_TIMEOUT_MS,
    )
    try:
        await client.admin.command("ping")
        db = client[settings.MONGO_DB]
        clauses: list[dict] = [
            {"_id": str(args.user_id)},
            {"id": str(args.user_id)},
        ]
        if ObjectId.is_valid(str(args.user_id)):
            clauses.append({"_id": ObjectId(str(args.user_id))})
        user = await db["users"].find_one({"$or": clauses})
        if (
            user is None
            or user.get("is_admin") is not True
            or user.get("is_active") is False
        ):
            raise SystemExit("candidate activation requires an active administrator user_id")

        data = CandidateRealDataService(db)
        pool = CandidatePoolService(db)
        results = []
        for symbol in normalized:
            precheck = await data.precheck_candidate(
                symbol=symbol,
                trade_date=args.trade_date,
                cutoff_at=cutoff_at,
            )
            if precheck["data_quality"]["status"] == "FAIL":
                raise SystemExit(f"{symbol} DataQuality precheck failed")
            existing = await pool.get_by_identity(str(args.user_id), "CN", symbol)
            candidate = existing
            if args.execute:
                candidate = await pool.upsert_source(
                    user_id=str(args.user_id),
                    symbol=symbol,
                    market="CN",
                    source=CandidateSource.USER_SELECTED,
                    name=precheck["name"] or None,
                    trace_id=args.trace_id,
                    reason="explicit user-selected real-data activation",
                )
            display_precheck = dict(precheck)
            # Full immutable references remain in the service result for
            # EvidenceSnapshot creation. CLI output reports counts instead of
            # printing thousands of identifiers into operational logs.
            display_precheck.pop("raw_refs", None)
            results.append(
                {
                    **display_precheck,
                    "candidate_action": (
                        "REUSED"
                        if existing is not None
                        else ("CREATED" if args.execute else "WOULD_CREATE")
                    ),
                    "candidate_id": (
                        candidate.candidate_id if candidate is not None else None
                    ),
                }
            )
        print(
            json.dumps(
                {
                    "write": args.execute,
                    "user_id": str(args.user_id),
                    "trade_date": args.trade_date,
                    "cutoff_at": cutoff_at,
                    "results": results,
                },
                ensure_ascii=False,
                default=str,
                indent=2,
            )
        )
    finally:
        client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--symbol", action="append", required=True)
    parser.add_argument("--trade-date", type=date.fromisoformat, required=True)
    parser.add_argument("--cutoff-at", type=datetime.fromisoformat, required=True)
    parser.add_argument("--trace-id", default="real-data-activation")
    parser.add_argument("--execute", action="store_true")
    asyncio.run(main(parser.parse_args()))
