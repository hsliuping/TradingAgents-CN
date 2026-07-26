#!/usr/bin/env python3
"""Preview or explicitly seed immutable PR-004 strategy definitions."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.database import close_database, get_mongo_db, init_database
from app.services.alphaguard.strategy_registry import (
    StrategyRegistry,
    builtin_strategy_definitions,
)


async def main(execute: bool) -> None:
    definitions = builtin_strategy_definitions()
    for definition in definitions:
        print(
            f"{definition.strategy_id}:{definition.strategy_version} "
            f"{definition.parameter_hash}"
        )
    if not execute:
        print("dry-run only; pass --execute to write")
        return
    await init_database()
    try:
        seeded = await StrategyRegistry(get_mongo_db()).seed_builtins()
        print(f"seeded_or_verified={len(seeded)}")
    finally:
        await close_database()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    asyncio.run(main(parser.parse_args().execute))
