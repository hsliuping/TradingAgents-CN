#!/usr/bin/env python3
"""Dry-run by default; create PR-006 indexes only with --execute."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.database import close_database, get_mongo_db, init_database
from app.services.alphaguard.index_service import ensure_alphaguard_indexes
from tradingagents.alphaguard.mongo_indexes import ALPHAGUARD_INDEX_SPECS


PAPER_COLLECTIONS = tuple(
    name
    for name in ALPHAGUARD_INDEX_SPECS
    if name.startswith("ag_paper_")
    or name
    in {
        "ag_order_intents",
        "ag_execution_market_snapshots",
        "ag_execution_outbox",
        "ag_settlement_records",
        "ag_benchmark_execution_decisions",
    }
)


async def main(execute: bool) -> None:
    expected = sum(
        len(ALPHAGUARD_INDEX_SPECS[name]) for name in PAPER_COLLECTIONS
    )
    print(
        f"paper_collections={len(PAPER_COLLECTIONS)} "
        f"paper_indexes={expected}"
    )
    if not execute:
        print("dry-run: no indexes written; pass --execute to initialize")
        return
    await init_database()
    try:
        paper_actions = await ensure_alphaguard_indexes(
            get_mongo_db(),
            collection_names=PAPER_COLLECTIONS,
        )
        created = sum(action.startswith("created ") for action in paper_actions)
        unchanged = sum(action.startswith("unchanged ") for action in paper_actions)
        for action in paper_actions:
            print(action)
        print(f"created={created} unchanged={unchanged} failed=0")
    finally:
        await close_database()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    asyncio.run(main(parser.parse_args().execute))
