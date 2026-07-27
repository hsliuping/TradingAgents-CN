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

from bson import decode_file_iter
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import settings  # noqa: E402
from scripts.alphaguard_backup import BACKUP_COLLECTIONS  # noqa: E402


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_manifest(source: Path) -> dict:
    manifest_path = source.resolve() / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("format") != "alphaguard-bson-stream-v1":
        raise RuntimeError("unsupported backup format")
    names = tuple(sorted(manifest.get("collections", {})))
    if names != BACKUP_COLLECTIONS:
        raise RuntimeError("backup collection scope does not match this release")
    for name, metadata in manifest["collections"].items():
        path = source / metadata["file"]
        if not path.is_file() or _sha256(path) != metadata["sha256"]:
            raise RuntimeError(f"backup integrity failure: {name}")
    return manifest


def run(
    *,
    source: Path,
    target_database: str,
    execute: bool,
    overwrite_current: bool,
    confirmation: str | None,
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
    print(
        f"backup_source_database={source_database} "
        f"target_database={target_database} collections={len(BACKUP_COLLECTIONS)}"
    )
    print("restore_scope=AlphaGuard collections only; manual paper collections excluded")
    if not execute:
        print("dry-run: no database writes; pass --execute to restore")
        return 0

    client = MongoClient(settings.MONGO_URI, serverSelectionTimeoutMS=5000)
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
            with path.open("rb") as handle:
                documents = list(decode_file_iter(handle))
            if documents:
                db[name].insert_many(documents, ordered=True)
            print(f"restored {name} count={len(documents)}")
        print(
            "restore_complete; run scripts/verify_champion_assignments.py and "
            "scripts/alphaguard_readiness_report.py before use"
        )
        return 0
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
    args = parser.parse_args()
    raise SystemExit(
        run(
            source=args.source,
            target_database=args.target_database,
            execute=args.execute,
            overwrite_current=args.overwrite_current,
            confirmation=args.confirmation,
        )
    )
