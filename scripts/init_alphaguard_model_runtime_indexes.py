#!/usr/bin/env python3
"""Dry-run by default; create only PR-010 model runtime indexes."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import settings  # noqa: E402
from tradingagents.alphaguard.mongo_indexes import ALPHAGUARD_INDEX_SPECS  # noqa: E402


MODEL_COLLECTIONS = tuple(
    name for name in ALPHAGUARD_INDEX_SPECS if name.startswith("ag_model_")
)


def _keys(value):
    if hasattr(value, "items"):
        return [(str(key), int(direction)) for key, direction in value.items()]
    return [(str(key), int(direction)) for key, direction in value]


def main(*, execute: bool) -> int:
    expected = sum(
        len(ALPHAGUARD_INDEX_SPECS[name]) for name in MODEL_COLLECTIONS
    )
    print(
        f"model_collections={len(MODEL_COLLECTIONS)} "
        f"model_indexes={expected}"
    )
    for name in MODEL_COLLECTIONS:
        for spec in ALPHAGUARD_INDEX_SPECS[name]:
            print(
                f"plan {name}.{spec['name']} "
                f"keys={spec['keys']} unique={bool(spec.get('unique', False))}"
            )
    if not execute:
        print("dry-run: no indexes written; pass --execute to initialize")
        return 0

    client = MongoClient(settings.MONGO_URI, serverSelectionTimeoutMS=5000)
    try:
        client.admin.command("ping")
        db = client[settings.MONGO_DB]
        created = unchanged = 0
        for name in MODEL_COLLECTIONS:
            collection = db[name]
            existing = {item["name"]: item for item in collection.list_indexes()}
            for spec in ALPHAGUARD_INDEX_SPECS[name]:
                current = existing.get(spec["name"])
                if current is not None:
                    if (
                        _keys(current["key"]) != _keys(spec["keys"])
                        or bool(current.get("unique", False))
                        != bool(spec.get("unique", False))
                    ):
                        raise RuntimeError(f"index conflict: {name}.{spec['name']}")
                    print(f"unchanged {name}.{spec['name']}")
                    unchanged += 1
                    continue
                collection.create_index(
                    spec["keys"],
                    name=spec["name"],
                    unique=bool(spec.get("unique", False)),
                )
                print(f"created {name}.{spec['name']}")
                created += 1
        print(f"created={created} unchanged={unchanged} failed=0")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    raise SystemExit(main(execute=parser.parse_args().execute))
