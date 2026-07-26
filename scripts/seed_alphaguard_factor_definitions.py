#!/usr/bin/env python3
"""Preview or explicitly seed immutable PR-004 factor definitions."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.database import close_database, get_mongo_db, init_database
from app.services.alphaguard.factor_registry import FactorRegistry, builtin_factor_definitions


async def main(execute: bool) -> None:
    factor_set, definitions, coverage = builtin_factor_definitions()
    print(f"factor_set={factor_set} definitions={len(definitions)} coverage={coverage}")
    for definition in definitions:
        print(f"{definition.factor_id}:{definition.factor_version} {definition.parameter_hash}")
    if not execute:
        print("dry-run only; pass --execute to write")
        return
    await init_database()
    try:
        seeded = await FactorRegistry(get_mongo_db()).seed_builtins()
        print(f"seeded_or_verified={len(seeded)}")
    finally:
        await close_database()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    asyncio.run(main(parser.parse_args().execute))
