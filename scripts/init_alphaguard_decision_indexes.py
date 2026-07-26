#!/usr/bin/env python3
"""Create-only AlphaGuard index runner (all PR-003 through PR-005 specs)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.database import close_database, get_mongo_db, init_database
from app.services.alphaguard.index_service import ensure_alphaguard_indexes


async def main() -> None:
    await init_database()
    try:
        for action in await ensure_alphaguard_indexes(get_mongo_db()):
            if any(
                name in action
                for name in (
                    "ag_decision_",
                    "ag_consensus_",
                    "ag_risk_",
                    "ag_revision_",
                )
            ):
                print(action)
    finally:
        await close_database()


if __name__ == "__main__":
    asyncio.run(main())
