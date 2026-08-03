#!/usr/bin/env python3
"""Restore AlphaGuard BSON backup to a new DB by default."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

from bson import BSON, decode_file_iter
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import settings  # noqa: E402
from scripts.alphaguard_backup import (  # noqa: E402
    BACKUP_COLLECTIONS,
    load_manifest,
    verify_backup,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_manifest(source: Path) -> dict:
    verify_backup(source)
    return load_manifest(source)


def _restore_bson_stream(
    collection,
    path: Path,
    *,
    max_documents: int = 100,
    max_bytes: int = 8 * 1024 * 1024,
) -> int:
    """Restore bounded batches so large collections cannot exhaust memory."""
    restored = 0
    batch = []
    batch_bytes = 0
    with path.open("rb") as handle:
        for document in decode_file_iter(handle):
            document_size = len(BSON.encode(document))
            if batch and (
                len(batch) >= max_documents
                or batch_bytes + document_size > max_bytes
            ):
                collection.insert_many(batch, ordered=True)
                restored += len(batch)
                batch = []
                batch_bytes = 0
            batch.append(document)
            batch_bytes += document_size
        if batch:
            collection.insert_many(batch, ordered=True)
            restored += len(batch)
    return restored


def run(
    *,
    source: Path,
    target_database: str,
    execute: bool,
    overwrite_current: bool,
    confirmation: str | None,
    drill: bool = False,
    client_factory=MongoClient,
) -> int:
    source = source.expanduser().resolve()
    manifest = _load_manifest(source)
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", target_database):
        raise ValueError("invalid target database name")
    source_database = str(manifest["source_database"])
    is_current = target_database == settings.MONGO_DB
    if is_current:
        expected = f"OVERWRITE {settings.MONGO_DB}"
        if not overwrite_current or confirmation != expected:
            raise RuntimeError(
                f"current database restore requires --overwrite-current "
                f"--confirmation '{expected}'"
            )
    elif overwrite_current:
        raise RuntimeError("--overwrite-current only applies to the configured database")
    if drill and is_current:
        raise RuntimeError("restore drill is only allowed for an isolated database")
    print(
        f"backup_source_database={source_database} "
        f"target_database={target_database} collections={len(BACKUP_COLLECTIONS)}"
    )
    print("restore_scope=AlphaGuard collections only; manual paper collections excluded")
    if not execute:
        print("dry-run: no database writes; pass --execute to restore")
        return 0

    client = client_factory(settings.MONGO_URI, serverSelectionTimeoutMS=5000)
    try:
        client.admin.command("ping")
        db = client[target_database]
        existing = {
            name: db[name].count_documents({}) for name in BACKUP_COLLECTIONS
        }
        if not is_current and any(existing.values()):
            raise RuntimeError("target database already contains AlphaGuard documents")
        for name in BACKUP_COLLECTIONS:
            if is_current:
                db[name].delete_many({})
            path = source / manifest["collections"][name]["file"]
            restored = _restore_bson_stream(db[name], path)
            print(f"restored {name} count={restored}")
        restored_counts = {
            name: db[name].count_documents({}) for name in BACKUP_COLLECTIONS
        }
        expected_counts = {
            name: int(manifest["collections"][name]["count"])
            for name in BACKUP_COLLECTIONS
        }
        if restored_counts != expected_counts:
            raise RuntimeError("restore count verification failed")
        print(
            "restore_complete; run scripts/verify_champion_assignments.py and "
            "scripts/alphaguard_readiness_report.py before use"
        )
        if drill:
            print(
                "restore_drill=PASS target_database="
                f"{target_database} collections={len(restored_counts)}"
            )
        return 0
    except Exception:
        if not is_current and hasattr(client, "drop_database"):
            client.drop_database(target_database)
            print(
                "restore_failed_isolated_cleanup=complete "
                f"target_database={target_database}"
            )
        raise
    finally:
        client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument(
        "--target-database",
        default=f"{settings.MONGO_DB}_restore_{datetime.now():%Y%m%d_%H%M%S}",
    )
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--overwrite-current", action="store_true")
    parser.add_argument("--confirmation")
    parser.add_argument("--drill", action="store_true")
    args = parser.parse_args()
    raise SystemExit(
        run(
            source=args.source,
            target_database=args.target_database,
            execute=args.execute,
            overwrite_current=args.overwrite_current,
            confirmation=args.confirmation,
            drill=args.drill,
        )
    )
