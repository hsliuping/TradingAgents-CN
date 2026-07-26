#!/usr/bin/env python3
"""Dry-run by default; initialize only PR-008 indexes with --execute."""

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


EXPERIMENT_COLLECTIONS = tuple(
    name for name in ALPHAGUARD_INDEX_SPECS if name.startswith("ag_exp_")
)


async def main(execute: bool) -> None:
    expected = sum(
        len(ALPHAGUARD_INDEX_SPECS[name]) for name in EXPERIMENT_COLLECTIONS
    )
    print(
        f"experiment_collections={len(EXPERIMENT_COLLECTIONS)} "
        f"experiment_indexes={expected}"
    )
    if not execute:
        print("dry-run: no indexes written; pass --execute to initialize")
        return
    await init_database()
    try:
        actions = await ensure_alphaguard_indexes(
            get_mongo_db(), collection_names=EXPERIMENT_COLLECTIONS
        )
        for action in actions:
            print(action)
        print(
            f"created={sum(item.startswith('created ') for item in actions)} "
            f"unchanged={sum(item.startswith('unchanged ') for item in actions)} "
            "failed=0"
        )
    finally:
        await close_database()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    asyncio.run(main(parser.parse_args().execute))
