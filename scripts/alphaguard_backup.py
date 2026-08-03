#!/usr/bin/env python3
"""Versioned AlphaGuard BSON backup with verification; dry-run by default."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from uuid import NAMESPACE_URL, uuid5

from bson import BSON, decode_file_iter
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import settings  # noqa: E402
from tradingagents.alphaguard.mongo_indexes import ALPHAGUARD_INDEX_SPECS  # noqa: E402


BACKUP_COLLECTIONS = tuple(sorted(ALPHAGUARD_INDEX_SPECS))
BACKUP_FORMAT = "alphaguard-bson-stream-v2"
BACKUP_SCHEMA_VERSION = "alphaguard-mvp-rc1-backup-v1"
DEFAULT_BACKUP_ROOT = ROOT / "backups"
FORBIDDEN_SECRET_KEYS = re.compile(
    r"^(authorization|api[_-]?key|api[_-]?secret|password|secret|"
    r"access[_-]?token|refresh[_-]?token|cookie|private[_-]?key)$",
    re.IGNORECASE,
)
SECRET_VALUE = re.compile(
    r"(?i)(bearer\s+[A-Za-z0-9._~+/=-]{12,}|"
    r"(?<![A-Za-z0-9])(?:sk|sess)-[A-Za-z0-9_-]{16,}|"
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)
SECRET_ASSIGNMENT = re.compile(
    r"(?im)^\s*(authorization|api[_-]?key|api[_-]?secret|password|secret|"
    r"access[_-]?token|refresh[_-]?token|cookie|private[_-]?key)\s*[:=]\s*(.+?)\s*$"
)
REFERENCE_VALUE = re.compile(
    r"(?i)^(?:[\"']?)\s*(?:null|none|~|not[-_ ]configured|"
    r"\$\{?[A-Z][A-Z0-9_]*\}?|env:|keychain|credential[_-]?ref|ref:|"
    r"\[redacted\]|•+)"
)


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


def _canonical_hash(payload: dict[str, Any]) -> str:
    value = {key: item for key, item in payload.items() if key != "manifest_hash"}
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()


def _git_value(*args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()
    except Exception:
        return "unknown"


def _source_tag() -> str:
    tags = [item for item in _git_value("tag", "--points-at", "HEAD").splitlines() if item]
    return sorted(tags)[-1] if tags else "untagged"


def _secret_paths(value: Any, path: str = "$") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            current = f"{path}.{key}"
            if (
                FORBIDDEN_SECRET_KEYS.fullmatch(str(key))
                and item is not None
                and item != ""
            ):
                findings.append(current)
            else:
                findings.extend(_secret_paths(item, current))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            findings.extend(_secret_paths(item, f"{path}[{index}]"))
    elif isinstance(value, str) and SECRET_VALUE.search(value):
        findings.append(path)
    return findings


def _secret_text_paths(content: str, path: str) -> list[str]:
    findings = []
    for match in SECRET_ASSIGNMENT.finditer(content):
        value = match.group(2).strip()
        if value in {"", '""', "''"} or REFERENCE_VALUE.match(value):
            continue
        findings.append(f"{path}:{match.group(1)}")
    if SECRET_VALUE.search(content):
        findings.append(f"{path}:secret-like-value")
    return sorted(set(findings))


def _config_files() -> list[Path]:
    root = ROOT / "config" / "alphaguard"
    return sorted(path for path in root.rglob("*") if path.is_file())


def _copy_config_snapshot(target: Path) -> dict[str, dict[str, Any]]:
    result = {}
    for source in _config_files():
        relative = source.relative_to(ROOT / "config" / "alphaguard")
        content = source.read_text(encoding="utf-8")
        findings = _secret_text_paths(content, str(relative))
        if findings:
            raise RuntimeError(f"secret-like config content refused: {relative}")
        destination = target / "config" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        result[str(relative)] = {
            "file": str(Path("config") / relative),
            "sha256": _sha256(destination),
            "size": destination.stat().st_size,
        }
    return result


def _manifest_path(source: Path) -> Path:
    return source.expanduser().resolve() / "manifest.json"


def load_manifest(source: Path) -> dict[str, Any]:
    return json.loads(_manifest_path(source).read_text(encoding="utf-8"))


def verify_backup(source: Path, *, scan_secrets: bool = True) -> dict[str, Any]:
    source = source.expanduser().resolve()
    manifest = load_manifest(source)
    if manifest.get("format") not in {"alphaguard-bson-stream-v1", BACKUP_FORMAT}:
        raise RuntimeError("unsupported backup format")
    names = tuple(sorted(manifest.get("collections", {})))
    if names != BACKUP_COLLECTIONS:
        raise RuntimeError("backup collection scope does not match this release")
    if manifest.get("format") == BACKUP_FORMAT:
        if manifest.get("manifest_hash") != _canonical_hash(manifest):
            raise RuntimeError("backup manifest hash mismatch")
    collection_counts = {}
    secret_findings = []
    for name, metadata in manifest["collections"].items():
        path = source / metadata["file"]
        if not path.is_file() or _sha256(path) != metadata["sha256"]:
            raise RuntimeError(f"backup integrity failure: {name}")
        count = 0
        if scan_secrets:
            with path.open("rb") as handle:
                for document in decode_file_iter(handle):
                    count += 1
                    secret_findings.extend(
                        f"{name}:{item}" for item in _secret_paths(document)
                    )
        else:
            count = int(metadata.get("count") or 0)
        if count != int(metadata.get("count") or 0):
            raise RuntimeError(f"backup count mismatch: {name}")
        collection_counts[name] = count
    for relative, metadata in (manifest.get("config_files") or {}).items():
        path = source / metadata["file"]
        if not path.is_file() or _sha256(path) != metadata["sha256"]:
            raise RuntimeError(f"backup config integrity failure: {relative}")
        if scan_secrets:
            secret_findings.extend(
                _secret_text_paths(
                    path.read_text(encoding="utf-8"),
                    f"config:{relative}",
                )
            )
    if secret_findings:
        raise RuntimeError(
            "secret-like content found in backup: " + ",".join(secret_findings[:10])
        )
    return {
        "backup_id": manifest.get("backup_id"),
        "status": "PASS",
        "manifest_hash": manifest.get("manifest_hash"),
        "collection_counts": collection_counts,
        "secret_scan": "PASS" if scan_secrets else "SKIPPED",
        "source_commit": manifest.get("source_commit"),
        "source_tag": manifest.get("source_tag"),
    }


def list_backups(root: Path = DEFAULT_BACKUP_ROOT) -> list[dict[str, Any]]:
    resolved = root.expanduser().resolve()
    if not resolved.exists():
        return []
    items = []
    for manifest_path in sorted(resolved.glob("*/manifest.json"), reverse=True):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest_valid = (
                manifest.get("format") == BACKUP_FORMAT
                and manifest.get("manifest_hash") == _canonical_hash(manifest)
                and (manifest.get("verification") or {}).get("status") == "PASS"
            )
            items.append(
                {
                    "backup_id": manifest.get("backup_id"),
                    "created_at": manifest.get("created_at"),
                    "schema_version": manifest.get("schema_version"),
                    "source_commit": manifest.get("source_commit"),
                    "source_tag": manifest.get("source_tag"),
                    "manifest_hash": manifest.get("manifest_hash"),
                    "path": str(manifest_path.parent),
                    "status": "READY" if manifest_valid else "INVALID",
                    "verified_at": (manifest.get("verification") or {}).get(
                        "verified_at"
                    ),
                }
            )
        except Exception:
            items.append({"path": str(manifest_path.parent), "status": "INVALID"})
    items.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
    return items


def run(*, execute: bool, output: Path, client_factory=MongoClient) -> int:
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
    client = client_factory(settings.MONGO_URI, serverSelectionTimeoutMS=5000)
    created_at = datetime.now(timezone.utc).isoformat()
    source_commit = _git_value("rev-parse", "HEAD")
    source_tag = _source_tag()
    backup_id = str(
        uuid5(
            NAMESPACE_URL,
            f"alphaguard:backup:{settings.MONGO_DB}:{created_at}:{source_commit}",
        )
    )
    manifest = {
        "format": BACKUP_FORMAT,
        "backup_id": backup_id,
        "created_at": created_at,
        "schema_version": BACKUP_SCHEMA_VERSION,
        "source_database": settings.MONGO_DB,
        "source_commit": source_commit,
        "source_tag": source_tag,
        "collections": {},
        "collection_counts": {},
        "config_files": {},
        "secret_policy": "references-only; no API keys, passwords, cookies or tokens",
        "verification": {"status": "PENDING", "verified_at": None},
    }
    try:
        client.admin.command("ping")
        db = client[settings.MONGO_DB]
        for name in BACKUP_COLLECTIONS:
            path = target / f"{name}.bson"
            count = 0
            with path.open("wb") as handle:
                for document in db[name].find({}):
                    findings = _secret_paths(document)
                    if findings:
                        raise RuntimeError(
                            f"secret-like content refused in {name}: {findings[0]}"
                        )
                    handle.write(BSON.encode(document))
                    count += 1
            manifest["collections"][name] = {
                "file": path.name,
                "count": count,
                "sha256": _sha256(path),
            }
            manifest["collection_counts"][name] = count
            print(f"backed_up {name} count={count}")
        manifest["config_files"] = _copy_config_snapshot(target)
        manifest["manifest_hash"] = _canonical_hash(manifest)
        manifest_path = target / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        verify_backup(target)
        manifest["verification"] = {
            "status": "PASS",
            "verified_at": datetime.now(timezone.utc).isoformat(),
        }
        manifest["manifest_hash"] = _canonical_hash(manifest)
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        verify_backup(target)
        print(
            f"backup_complete backup_id={backup_id} manifest={manifest_path} "
            f"manifest_hash={manifest['manifest_hash']}"
        )
        return 0
    except Exception:
        # The target is a validated dedicated output directory created by this
        # run.  Remove partial BSON so failed or secret-blocked data cannot be
        # mistaken for a backup or consume unbounded disk space.
        if target.exists():
            shutil.rmtree(target)
            print(f"partial_backup_cleanup=complete output={target}")
        raise
    finally:
        client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--verify", type=Path)
    parser.add_argument("--backup-root", type=Path, default=DEFAULT_BACKUP_ROOT)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_BACKUP_ROOT / f"alphaguard-{datetime.now():%Y%m%d-%H%M%S}",
    )
    args = parser.parse_args()
    if args.list:
        print(json.dumps(list_backups(args.backup_root), ensure_ascii=False, indent=2))
        raise SystemExit(0)
    if args.verify:
        print(json.dumps(verify_backup(args.verify), ensure_ascii=False, indent=2))
        raise SystemExit(0)
    raise SystemExit(run(execute=args.execute, output=args.output))
