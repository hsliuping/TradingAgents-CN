#!/usr/bin/env python3
"""Read-only verification for imported/committed Champion assignments."""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.database import close_database, get_mongo_db, init_database
from app.services.alphaguard.champion_resolver import ChampionResolver
from app.services.alphaguard.paper_storage import clean_document


async def main(as_of: date) -> None:
    await init_database()
    try:
        db = get_mongo_db()
        documents = await db["ag_exp_champion_assignments"].find({}).to_list(
            length=None
        )
        seen: set[tuple[str, str, str]] = set()
        verified = conflicts = 0
        resolver = ChampionResolver(db)
        for raw in documents:
            item = clean_document(raw)
            identity = (
                item["component_type"],
                item["component_key"],
                item["market"],
            )
            if identity in seen:
                conflicts += 1
                print(f"conflict duplicate_identity={identity}")
                continue
            seen.add(identity)
            try:
                resolution = await resolver.resolve_champion(
                    component_type=identity[0],
                    component_key=identity[1],
                    market=identity[2],
                    as_of_trade_date=as_of,
                )
                verified += 1
                print(
                    f"verified slot={resolution.champion_slot_id} "
                    f"version={resolution.version_ref}"
                )
            except Exception as exc:
                conflicts += 1
                print(f"conflict identity={identity} reason={type(exc).__name__}")
        print(
            f"assignments={len(documents)} verified={verified} conflicts={conflicts}"
        )
        if conflicts:
            raise RuntimeError("Champion assignment verification failed")
    finally:
        await close_database()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    asyncio.run(main(parser.parse_args().as_of))
