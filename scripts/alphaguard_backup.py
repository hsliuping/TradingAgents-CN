#!/usr/bin/env python3
"""Exact-scope BSON backup for AlphaGuard collections; dry-run by default."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from bson import BSON
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import settings  # noqa: E402
from tradingagents.alphaguard.mongo_indexes import ALPHAGUARD_INDEX_SPECS  # noqa: E402


BACKUP_COLLECTIONS = tuple(sorted(ALPHAGUARD_INDEX_SPECS))


def _safe_output(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if resolved in {Path("/"), Path.home().resolve(), ROOT.resolve()}:
        raise ValueError("backup output must be a dedicated directory")
    return resolved


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(*, execute: bool, output: Path) -> int:
    target = _safe_output(output)
    print(
        f"source_database={settings.MONGO_DB} collections={len(BACKUP_COLLECTIONS)} "
        f"output={target}"
    )
    for name in BACKUP_COLLECTIONS:
        print(f"plan backup {name}")
    if not execute:
        print("dry-run: no files written; pass --execute to create backup")
        return 0
    if target.exists() and any(target.iterdir()):
        raise RuntimeError("backup target already exists and is not empty")
    target.mkdir(parents=True, exist_ok=True)
    client = MongoClient(settings.MONGO_URI, serverSelectionTimeoutMS=5000)
    manifest = {
        "format": "alphaguard-bson-stream-v1",
        "source_database": settings.MONGO_DB,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "collections": {},
    }
    try:
        client.admin.command("ping")
        db = client[settings.MONGO_DB]
        for name in BACKUP_COLLECTIONS:
            path = target / f"{name}.bson"
            count = 0
            with path.open("wb") as handle:
                for document in db[name].find({}):
                    handle.write(BSON.encode(document))
                    count += 1
            manifest["collections"][name] = {
                "file": path.name,
                "count": count,
                "sha256": _sha256(path),
            }
            print(f"backed_up {name} count={count}")
        manifest_path = target / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"backup_complete manifest={manifest_path}")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "backups" / f"alphaguard-{datetime.now():%Y%m%d-%H%M%S}",
    )
    args = parser.parse_args()
    raise SystemExit(run(execute=args.execute, output=args.output))
