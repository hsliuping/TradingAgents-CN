import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set

from pymongo import MongoClient

from app.core.config import settings

DEFAULT_EXCLUDED_COLLECTIONS = {
    "analysis_tasks",
    "analysis_reports",
    "historical_data",
    "market_quotes",
    "market_quotes_hk",
    "market_quotes_us",
    "news_data",
    "social_media_data",
    "stock_basic_info",
    "stock_basic_info_hk",
    "stock_basic_info_us",
    "stock_financial_data",
    "usage_records",
}


def _split_csv(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_since(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    normalized = value.strip().replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def _build_since_query(since: Optional[datetime]) -> Dict[str, object]:
    if since is None:
        return {}

    since_iso = since.isoformat()
    return {
        "$or": [
            {"updated_at": {"$gte": since}},
            {"created_at": {"$gte": since}},
            {"updated_at": {"$gte": since_iso}},
            {"created_at": {"$gte": since_iso}},
        ]
    }


def _get_collection_names(db) -> List[str]:
    return sorted(db.list_collection_names())


def _iter_collections(
    db,
    include: Optional[Set[str]],
    exclude: Set[str],
) -> List[str]:
    names = _get_collection_names(db)
    if include:
        names = [n for n in names if n in include]
    if exclude:
        names = [n for n in names if n not in exclude]
    return names


def _copy_collection(
    source_db,
    target_db,
    name: str,
    drop_target: bool,
    dry_run: bool,
    batch_size: int,
    since: Optional[datetime],
    limit: int,
) -> dict:
    src = source_db[name]
    tgt = target_db[name]
    query = _build_since_query(since)

    src_count = src.count_documents(query)
    source_count_used = min(src_count, limit) if limit > 0 else src_count
    tgt_count_before = tgt.estimated_document_count() if name in target_db.list_collection_names() else 0

    if dry_run:
        return {
            "collection": name,
            "source_count": src_count,
            "source_count_used": source_count_used,
            "target_count_before": tgt_count_before,
            "target_count_after": tgt_count_before,
            "dropped": False,
            "upserted": 0,
            "since": since.isoformat() if since else None,
            "limit": limit if limit > 0 else None,
        }

    dropped = False
    if drop_target and name in target_db.list_collection_names():
        tgt.drop()
        dropped = True

    upserted = 0
    cursor = src.find(query, no_cursor_timeout=True).batch_size(batch_size)
    if limit > 0:
        cursor = cursor.limit(limit)
    try:
        ops = []
        for doc in cursor:
            doc_id = doc.get("_id")
            if doc_id is None:
                continue
            ops.append(({"_id": doc_id}, doc))
            if len(ops) >= batch_size:
                for filt, repl in ops:
                    tgt.replace_one(filt, repl, upsert=True)
                upserted += len(ops)
                ops = []
        if ops:
            for filt, repl in ops:
                tgt.replace_one(filt, repl, upsert=True)
            upserted += len(ops)
    finally:
        cursor.close()

    tgt_count_after = tgt.estimated_document_count()
    return {
        "collection": name,
        "source_count": src_count,
        "source_count_used": source_count_used,
        "target_count_before": tgt_count_before,
        "target_count_after": tgt_count_after,
        "dropped": dropped,
        "upserted": upserted,
        "since": since.isoformat() if since else None,
        "limit": limit if limit > 0 else None,
    }


def _write_summary_json(path: str, summary: Dict[str, object]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="migrate_mongo_db")
    parser.add_argument("--mongo-uri", default=os.getenv("MONGO_URI") or settings.MONGO_URI)
    parser.add_argument("--source-db", default=os.getenv("MONGO_SOURCE_DB") or "tradingagents")
    parser.add_argument("--target-db", default=os.getenv("MONGO_TARGET_DB") or settings.MONGO_DB)
    parser.add_argument("--include", default="", help="Comma-separated collection names to include")
    parser.add_argument("--exclude", default="", help="Comma-separated collection names to exclude")
    parser.add_argument("--since", default="", help="Incremental migration lower bound, ISO-8601 format")
    parser.add_argument("--show-default-excludes", action="store_true", help="Print default excluded large/cache collections and exit")
    parser.add_argument("--drop-target", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--limit", type=int, default=0, help="Per-collection document limit for small-sample validation")
    parser.add_argument("--summary-json", default="", help="Write migration summary JSON to file")
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.show_default_excludes:
        print(sorted(DEFAULT_EXCLUDED_COLLECTIONS))
        return 0

    include = set(_split_csv(args.include)) or None
    exclude = set(_split_csv(args.exclude))
    since = _parse_since(args.since)
    if include is None:
        exclude |= DEFAULT_EXCLUDED_COLLECTIONS

    client = MongoClient(args.mongo_uri)
    try:
        source_db = client[args.source_db]
        target_db = client[args.target_db]

        collections = _iter_collections(source_db, include, exclude)
        results = []
        for name in collections:
            results.append(
                _copy_collection(
                    source_db=source_db,
                    target_db=target_db,
                    name=name,
                    drop_target=args.drop_target,
                    dry_run=args.dry_run,
                    batch_size=args.batch_size,
                    since=since,
                    limit=args.limit,
                )
            )

        total = {
            "source_db": args.source_db,
            "target_db": args.target_db,
            "include": sorted(include) if include else None,
            "exclude": sorted(exclude),
            "since": since.isoformat() if since else None,
            "limit": args.limit if args.limit > 0 else None,
            "collections": results,
        }
        if args.summary_json:
            _write_summary_json(args.summary_json, total)
        print(total)
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
