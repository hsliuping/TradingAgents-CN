#!/usr/bin/env python3
"""Idempotently merge existing favorites into the AlphaGuard candidate pool."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from motor.motor_asyncio import AsyncIOMotorClient


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import settings  # noqa: E402
from app.services.alphaguard.candidate_pool_service import (  # noqa: E402
    CandidatePoolService,
)
from tradingagents.alphaguard.candidate_schemas import CandidateSource  # noqa: E402
from tradingagents.alphaguard.instruments import normalize_instrument  # noqa: E402


async def migrate_database(db, *, dry_run: bool = True) -> dict[str, int]:
    """Merge both legacy favorite storage shapes into one candidate pool."""

    stats = {"added": 0, "updated": 0, "skipped": 0, "failed": 0}
    service = CandidatePoolService(db)
    rows: list[tuple[str, dict]] = []

    for document in await db["user_favorites"].find({}).to_list(length=None):
        user_id = str(document.get("user_id", ""))
        rows.extend((user_id, favorite) for favorite in document.get("favorites", []))

    for document in await db["users"].find(
        {"favorite_stocks": {"$exists": True, "$ne": []}}
    ).to_list(length=None):
        user_id = str(document.get("_id", ""))
        rows.extend(
            (user_id, favorite)
            for favorite in document.get("favorite_stocks", [])
        )

    for user_id, favorite in rows:
        try:
            market, symbol = normalize_instrument(
                favorite.get("stock_code") or favorite.get("symbol"),
                favorite.get("market") or "CN",
            )
            current = await service.get_by_identity(user_id, market, symbol)
            if current is None:
                action = "added"
            elif CandidateSource.USER_SELECTED not in current.sources:
                action = "updated"
            else:
                action = "skipped"
            stats[action] += 1
            if dry_run or action == "skipped":
                continue
            await service.upsert_source(
                user_id=user_id,
                symbol=symbol,
                market=market,
                source=CandidateSource.USER_SELECTED,
                name=favorite.get("stock_name") or favorite.get("name"),
                reason="favorites migration",
            )
        except Exception as exc:
            stats["failed"] += 1
            print(
                "FAILED "
                f"user_id={user_id!r} favorite={favorite!r} "
                f"error={exc.__class__.__name__}: {exc}"
            )
    return stats


async def migrate(*, dry_run: bool = True) -> dict[str, int]:
    client = AsyncIOMotorClient(settings.MONGO_URI, serverSelectionTimeoutMS=5000)
    try:
        await client.admin.command("ping")
        return await migrate_database(
            client[settings.MONGO_DB],
            dry_run=dry_run,
        )
    finally:
        client.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--execute",
        action="store_true",
        help="write candidate merges; the default is a non-mutating dry-run",
    )
    args = parser.parse_args()
    dry_run = not args.execute
    print(f"mode={'DRY-RUN' if dry_run else 'EXECUTE'}")
    stats = asyncio.run(migrate(dry_run=dry_run))
    print(
        "migration result: "
        f"added={stats['added']} updated={stats['updated']} "
        f"skipped={stats['skipped']} failed={stats['failed']}"
    )
    print("Existing favorites were not deleted or overwritten.")
    return 1 if stats["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
