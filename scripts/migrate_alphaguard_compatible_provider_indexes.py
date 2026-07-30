#!/usr/bin/env python3
"""Dry-run by default; migrate only compatible-provider model indexes."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import settings  # noqa: E402
from tradingagents.alphaguard.mongo_indexes import (  # noqa: E402
    ALPHAGUARD_INDEX_SPECS,
)


TARGET_COLLECTIONS = (
    "ag_model_credentials",
    "ag_model_provider_endpoints",
    "ag_model_endpoint_models",
    "ag_model_endpoint_prices",
    "ag_model_profile_assignments",
    "ag_model_endpoint_events",
)
LEGACY_INDEX = "uniq_model_credential_provider"


def _keys(value):
    if hasattr(value, "items"):
        return [(str(key), int(direction)) for key, direction in value.items()]
    return [(str(key), int(direction)) for key, direction in value]


def main(*, execute: bool) -> int:
    print(
        "scope=alphaguard-compatible-provider-indexes "
        f"collections={len(TARGET_COLLECTIONS)}"
    )
    client = MongoClient(settings.MONGO_URI, serverSelectionTimeoutMS=5000)
    try:
        client.admin.command("ping")
        db = client[settings.MONGO_DB]
        credential_indexes = {
            item["name"]: item
            for item in db["ag_model_credentials"].list_indexes()
        }
        legacy = credential_indexes.get(LEGACY_INDEX)
        if legacy is not None and (
            _keys(legacy["key"]) != [("provider", 1)]
            or not bool(legacy.get("unique", False))
        ):
            raise RuntimeError(
                "legacy index name exists with unexpected definition"
            )
        print(
            f"legacy_index={LEGACY_INDEX} "
            f"action={'DROP' if legacy is not None else 'UNCHANGED_ABSENT'}"
        )
        for collection_name in TARGET_COLLECTIONS:
            for spec in ALPHAGUARD_INDEX_SPECS[collection_name]:
                print(
                    f"plan {collection_name}.{spec['name']} "
                    f"keys={spec['keys']} unique={bool(spec.get('unique', False))}"
                )
        if not execute:
            print("dry-run: no indexes changed; pass --execute to migrate")
            return 0
        if legacy is not None:
            db["ag_model_credentials"].drop_index(LEGACY_INDEX)
            print(f"dropped ag_model_credentials.{LEGACY_INDEX}")
        created = unchanged = 0
        for collection_name in TARGET_COLLECTIONS:
            collection = db[collection_name]
            existing = {
                item["name"]: item for item in collection.list_indexes()
            }
            for spec in ALPHAGUARD_INDEX_SPECS[collection_name]:
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
                    unchanged += 1
                    continue
                options = {
                    key: value
                    for key, value in spec.items()
                    if key not in {"keys", "name"}
                }
                collection.create_index(
                    spec["keys"], name=spec["name"], **options
                )
                created += 1
        print(f"created={created} unchanged={unchanged} failed=0")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    raise SystemExit(main(execute=parser.parse_args().execute))
