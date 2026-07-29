#!/usr/bin/env python3
"""Dry-run-first production EvidenceSnapshot v2 reprocessing."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import date, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.database import close_database, get_mongo_db, init_database
from app.services.alphaguard.production_reprocess_service import (
    ProductionReprocessService,
)
from app.services.alphaguard.quant_config import canonical_value


async def run(args) -> None:
    await init_database()
    try:
        db = get_mongo_db()
        user_id = args.user_id
        if not user_id:
            users = await db["ag_candidates"].distinct("user_id")
            if len(users) != 1:
                raise RuntimeError(
                    "exact --user-id is required when candidate ownership "
                    "is not unique"
                )
            user_id = str(users[0])
        result = await ProductionReprocessService(db).run(
            user_id=str(user_id),
            source_trade_date=date.fromisoformat(args.trade_date),
            cutoff_at=datetime.fromisoformat(args.cutoff_at),
            execute=args.execute,
            call_real_model=args.call_real_model,
        )
        print(
            json.dumps(
                canonical_value(result),
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            )
        )
    finally:
        await close_database()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id")
    parser.add_argument("--trade-date", default="2026-07-29")
    parser.add_argument(
        "--cutoff-at",
        default="2026-07-29T18:30:00",
        help="fixed post-close evidence cutoff; never defaults to now",
    )
    parser.add_argument("--execute", action="store_true")
    parser.add_argument(
        "--call-real-model",
        action="store_true",
        help="perform at most one Normal and one Top provider call",
    )
    args = parser.parse_args()
    if args.call_real_model and not args.execute:
        parser.error("--call-real-model requires --execute")
    asyncio.run(run(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
