#!/usr/bin/env python3
"""Create AlphaGuard PR-003/PR-004 indexes without deleting existing objects."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pymongo import MongoClient


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import settings  # noqa: E402
from tradingagents.alphaguard.mongo_indexes import ALPHAGUARD_INDEX_SPECS  # noqa: E402


def _keys(value):
    if hasattr(value, "items"):
        return [(str(key), int(direction)) for key, direction in value.items()]
    return [(str(key), int(direction)) for key, direction in value]


def print_plan() -> None:
    print("AlphaGuard PR-003/PR-004 MongoDB index plan (create-only):")
    for collection_name, specs in ALPHAGUARD_INDEX_SPECS.items():
        for spec in specs:
            print(
                f"  {collection_name}.{spec['name']}: "
                f"keys={spec['keys']} unique={bool(spec.get('unique', False))}"
            )


def ensure_indexes() -> list[str]:
    client = MongoClient(settings.MONGO_URI, serverSelectionTimeoutMS=5000)
    try:
        client.admin.command("ping")
        db = client[settings.MONGO_DB]
        actions: list[str] = []
        for collection_name, specs in ALPHAGUARD_INDEX_SPECS.items():
            collection = db[collection_name]
            existing = {index["name"]: index for index in collection.list_indexes()}
            for spec in specs:
                current = existing.get(spec["name"])
                if current is not None:
                    if (
                        _keys(current["key"]) != _keys(spec["keys"])
                        or bool(current.get("unique", False))
                        != bool(spec.get("unique", False))
                    ):
                        raise RuntimeError(
                            f"index conflict: {collection_name}.{spec['name']}"
                        )
                    actions.append(f"unchanged {collection_name}.{spec['name']}")
                    continue
                collection.create_index(
                    spec["keys"],
                    name=spec["name"],
                    unique=bool(spec.get("unique", False)),
                )
                actions.append(f"created {collection_name}.{spec['name']}")
        return actions
    finally:
        client.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="print the create-only plan without connecting or changing MongoDB",
    )
    args = parser.parse_args()
    print_plan()
    if args.plan_only:
        return 0
    for action in ensure_indexes():
        print(action)
    print("AlphaGuard indexes are ready; no collection or index was deleted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
