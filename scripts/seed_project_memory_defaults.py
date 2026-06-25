"""Seed default L4 project-memory rules into MongoDB."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.database import get_mongo_db
from app.services.project_memory_service import get_project_memory_service


async def seed_defaults() -> dict:
    db = get_mongo_db()
    svc = get_project_memory_service(db)
    result = await svc.seed_default_items(updated_by="system_seed")
    items = result["items"]
    return {
        "ok": True,
        "count": result["count"],
        "memory_keys": [item.memory_key for item in items],
        "titles": [item.title for item in items],
    }


def main() -> int:
    summary = asyncio.run(seed_defaults())
    print(f"[PASS] seeded project memory defaults: {summary['count']}")
    for key, title in zip(summary["memory_keys"], summary["titles"]):
        print(f"- {key}: {title}")
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())