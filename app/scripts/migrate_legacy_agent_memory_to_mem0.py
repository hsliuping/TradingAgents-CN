"""
Migrate legacy TradingAgents vector memories into mem0.

Usage:
    python app/scripts/migrate_legacy_agent_memory_to_mem0.py --dry-run
    python app/scripts/migrate_legacy_agent_memory_to_mem0.py --source qdrant --limit 20
    python app/scripts/migrate_legacy_agent_memory_to_mem0.py --source chroma --memory-names bull_memory,bear_memory
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("legacy.agent_memory_migration")


DEFAULT_CHROMA_MEMORY_NAMES = [
    "bull_memory",
    "bear_memory",
    "trader_memory",
    "invest_judge_memory",
    "risk_manager_memory",
]

DEFAULT_USER_ID = "legacy_tradingagents"
DEFAULT_QDRANT_PREFIX = "memory_"
MIGRATION_SOURCE = "legacy_financial_situation_memory_migration"
_SYMBOL_PATTERN = re.compile(r"\b(?:sh|sz|bj|hk)\.\d{5,6}\b|\b\d{6}(?:\.[A-Z]{2})?\b", re.IGNORECASE)


@dataclass
class LegacyMemoryRecord:
    memory_name: str
    legacy_doc_id: str
    situation: str
    recommendation: str = ""
    legacy_metadata: Dict[str, Any] = field(default_factory=dict)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate legacy TradingAgents vector memories into mem0")
    parser.add_argument(
        "--source",
        choices=["auto", "qdrant", "chroma"],
        default="auto",
        help="Legacy source type. auto prefers Qdrant memory_* collections, then falls back to Chroma.",
    )
    parser.add_argument(
        "--memory-names",
        default="",
        help="Comma separated legacy collection names. For Qdrant, defaults to all memory_* collections. For Chroma, defaults to v1 collections.",
    )
    parser.add_argument("--user-id", default=DEFAULT_USER_ID, help="Target mem0 user_id")
    parser.add_argument("--session-prefix", default="legacy_migration", help="run_id prefix for migrated memories")
    parser.add_argument("--batch-size", type=int, default=100, help="Records per read batch")
    parser.add_argument("--limit", type=int, default=0, help="Maximum records to migrate, 0 means unlimited")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, do not write to mem0")
    parser.add_argument(
        "--allow-duplicates",
        action="store_true",
        help="Write even if the same legacy_doc_id was migrated before",
    )
    parser.add_argument("--preview", type=int, default=3, help="How many records to preview in dry-run logs")
    return parser.parse_args()


def _parse_memory_names(raw: str) -> List[str]:
    return [item.strip() for item in str(raw or "").split(",") if item.strip()]


def _extract_symbol(text: str) -> str:
    match = _SYMBOL_PATTERN.search(str(text or ""))
    return match.group(0).upper() if match else ""


def _normalize_collection_rows(memory_name: str, payload: Dict[str, Sequence[Any]]) -> List[LegacyMemoryRecord]:
    ids = list(payload.get("ids") or [])
    documents = list(payload.get("documents") or [])
    metadatas = list(payload.get("metadatas") or [])

    records: List[LegacyMemoryRecord] = []
    for index, document in enumerate(documents):
        metadata = metadatas[index] if index < len(metadatas) and isinstance(metadatas[index], dict) else {}
        legacy_doc_id = str(ids[index] if index < len(ids) else index)
        records.append(
            LegacyMemoryRecord(
                memory_name=memory_name,
                legacy_doc_id=legacy_doc_id,
                situation=str(document or "").strip(),
                recommendation=str(metadata.get("recommendation") or "").strip(),
                legacy_metadata=dict(metadata),
            )
        )
    return records


def _normalize_qdrant_scroll_rows(memory_name: str, points: Sequence[Any]) -> List[LegacyMemoryRecord]:
    records: List[LegacyMemoryRecord] = []
    for index, point in enumerate(points or []):
        payload = dict(getattr(point, "payload", {}) or {})
        document = str(payload.pop("document", "") or "").strip()
        legacy_doc_id = str(getattr(point, "id", "") or index)
        records.append(
            LegacyMemoryRecord(
                memory_name=memory_name,
                legacy_doc_id=legacy_doc_id,
                situation=document,
                legacy_metadata=payload,
            )
        )
    return records


def _build_store_messages(record: LegacyMemoryRecord) -> List[Dict[str, str]]:
    if record.recommendation:
        payload = (
            f"Legacy situation:\n{record.situation}\n\n"
            f"Recommendation:\n{record.recommendation}"
        )
    else:
        payload = record.situation
    return [{"role": "user", "content": payload}]


def _build_store_metadata(record: LegacyMemoryRecord) -> Dict[str, Any]:
    symbol = (
        _extract_symbol(record.situation)
        or _extract_symbol(record.recommendation)
        or _extract_symbol(record.legacy_metadata.get("ticker") or "")
    )
    metadata: Dict[str, Any] = {
        "source": MIGRATION_SOURCE,
        "legacy_memory_name": record.memory_name,
        "legacy_doc_id": record.legacy_doc_id,
    }
    if record.recommendation:
        metadata["legacy_situation"] = record.situation
        metadata["legacy_recommendation"] = record.recommendation
    else:
        metadata["legacy_content"] = record.situation

    ticker = str(record.legacy_metadata.get("ticker") or "").strip()
    stance = str(record.legacy_metadata.get("stance") or "").strip()
    legacy_agent_id = str(record.legacy_metadata.get("agent_id") or "").strip()
    timestamp = str(record.legacy_metadata.get("timestamp") or "").strip()
    provider = str(record.legacy_metadata.get("provider") or "").strip()

    if ticker:
        metadata["ticker"] = ticker.upper()
    if stance:
        metadata["legacy_stance"] = stance
    if legacy_agent_id:
        metadata["legacy_agent_id"] = legacy_agent_id
    if timestamp:
        metadata["legacy_timestamp"] = timestamp
    if provider:
        metadata["legacy_embedding_provider"] = provider
    if symbol:
        metadata["symbol"] = symbol
        metadata["object_type"] = "stock"
        metadata["object_key"] = symbol
    return metadata


def _build_session_id(prefix: str, memory_name: str) -> str:
    return f"{prefix}:{memory_name}"


def _get_existing_collection(chroma_manager: Any, memory_name: str):
    try:
        return chroma_manager._client.get_collection(name=memory_name)
    except Exception:
        return None


def _list_chroma_collection_names(chroma_manager: Any) -> List[str]:
    try:
        raw_items = chroma_manager._client.list_collections()
    except Exception:
        return []

    names: List[str] = []
    for item in raw_items or []:
        name = getattr(item, "name", item)
        value = str(name or "").strip()
        if value:
            names.append(value)
    return names


def _iter_chroma_collection_records(collection: Any, memory_name: str, batch_size: int, limit: int) -> Iterable[List[LegacyMemoryRecord]]:
    count = int(collection.count() or 0)
    seen = 0
    offset = 0

    while offset < count:
        if limit and seen >= limit:
            break

        current_batch_size = min(batch_size, count - offset)
        if limit:
            current_batch_size = min(current_batch_size, limit - seen)
        if current_batch_size <= 0:
            break

        payload = collection.get(limit=current_batch_size, offset=offset, include=["documents", "metadatas"])
        records = _normalize_collection_rows(memory_name, payload)
        if not records:
            break

        yield records
        batch_count = len(records)
        seen += batch_count
        offset += batch_count


def _build_qdrant_client() -> Any:
    from qdrant_client import QdrantClient

    data_dir = os.getenv("QDRANT_DATA_DIR", "./data/qdrant")
    resolved_dir = (ROOT_DIR / data_dir).resolve() if not Path(data_dir).is_absolute() else Path(data_dir)
    resolved_dir.mkdir(parents=True, exist_ok=True)
    return QdrantClient(path=str(resolved_dir))


def _list_qdrant_collection_names(qdrant_client: Any) -> List[str]:
    try:
        collections = qdrant_client.get_collections().collections
    except Exception:
        return []

    names: List[str] = []
    for item in collections or []:
        value = str(getattr(item, "name", "") or "").strip()
        if value:
            names.append(value)
    return names


def _iter_qdrant_collection_records(qdrant_client: Any, memory_name: str, batch_size: int, limit: int) -> Iterable[List[LegacyMemoryRecord]]:
    seen = 0
    offset = None

    while True:
        if limit and seen >= limit:
            break

        current_batch_size = max(1, batch_size)
        if limit:
            current_batch_size = min(current_batch_size, limit - seen)
        if current_batch_size <= 0:
            break

        points, next_offset = qdrant_client.scroll(
            collection_name=memory_name,
            limit=current_batch_size,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        records = _normalize_qdrant_scroll_rows(memory_name, points)
        if not records:
            break

        yield records
        seen += len(records)
        offset = next_offset
        if offset is None:
            break


def _resolve_source(requested_source: str, available_qdrant: List[str], available_chroma: List[str]) -> str:
    if requested_source != "auto":
        return requested_source
    if any(name.startswith(DEFAULT_QDRANT_PREFIX) for name in available_qdrant):
        return "qdrant"
    if available_chroma:
        return "chroma"
    return "qdrant"


def _resolve_default_memory_names(source: str, available_qdrant: List[str]) -> List[str]:
    if source == "qdrant":
        return sorted(name for name in available_qdrant if name.startswith(DEFAULT_QDRANT_PREFIX))
    return list(DEFAULT_CHROMA_MEMORY_NAMES)


async def _load_existing_legacy_doc_ids(memory_service: Any, user_id: str, memory_name: str) -> set[str]:
    existing_ids: set[str] = set()
    page = 1

    while True:
        result = await memory_service.get_all(
            user_id=user_id,
            scopes=["agent_experience"],
            metadata_filters={
                "source": MIGRATION_SOURCE,
                "legacy_memory_name": memory_name,
            },
            limit=200,
            page=page,
        )
        items = result.get("items") or []
        if not items:
            break

        for item in items:
            legacy_doc_id = str(getattr(item, "metadata", {}).get("legacy_doc_id") or "").strip()
            if legacy_doc_id:
                existing_ids.add(legacy_doc_id)
        page += 1

    return existing_ids


def _preview_log(record: LegacyMemoryRecord, preview_limit: int) -> Tuple[str, str]:
    return record.situation[:preview_limit], record.recommendation[:preview_limit]


async def _migrate_memory_name(
    args: argparse.Namespace,
    source: str,
    memory_name: str,
    legacy_reader: Any,
    memory_service: Any,
) -> Dict[str, int]:
    if source == "qdrant":
        available = set(_list_qdrant_collection_names(legacy_reader))
        if memory_name not in available:
            logger.info("skip collection=%s source=qdrant reason=missing_collection", memory_name)
            return {"seen": 0, "migrated": 0, "skipped_existing": 0, "skipped_invalid": 0, "errors": 0}
        batch_iter = _iter_qdrant_collection_records(legacy_reader, memory_name, max(1, args.batch_size), max(0, args.limit))
    else:
        collection = _get_existing_collection(legacy_reader, memory_name)
        if collection is None:
            logger.info("skip collection=%s source=chroma reason=missing_collection", memory_name)
            return {"seen": 0, "migrated": 0, "skipped_existing": 0, "skipped_invalid": 0, "errors": 0}
        batch_iter = _iter_chroma_collection_records(collection, memory_name, max(1, args.batch_size), max(0, args.limit))

    existing_ids = set()
    if not args.allow_duplicates:
        existing_ids = await _load_existing_legacy_doc_ids(memory_service, args.user_id, memory_name)

    stats = {"seen": 0, "migrated": 0, "skipped_existing": 0, "skipped_invalid": 0, "errors": 0}
    preview_logged = 0

    for batch in batch_iter:
        for record in batch:
            stats["seen"] += 1

            if not record.situation:
                stats["skipped_invalid"] += 1
                continue

            if not args.allow_duplicates and record.legacy_doc_id in existing_ids:
                stats["skipped_existing"] += 1
                continue

            if args.dry_run:
                if preview_logged < max(0, args.preview):
                    preview_text, preview_recommendation = _preview_log(record, 120)
                    logger.info(
                        "dry-run preview source=%s collection=%s legacy_doc_id=%s content=%s recommendation=%s",
                        source,
                        memory_name,
                        record.legacy_doc_id,
                        preview_text,
                        preview_recommendation,
                    )
                    preview_logged += 1
                stats["migrated"] += 1
                continue

            result = await memory_service.store(
                _build_store_messages(record),
                user_id=args.user_id,
                agent_id=_resolve_agent_id(memory_name, record),
                session_id=_build_session_id(args.session_prefix, memory_name),
                scope="agent_experience",
                metadata=_build_store_metadata(record),
                infer=False,
            )
            if result.success:
                stats["migrated"] += 1
                existing_ids.add(record.legacy_doc_id)
            else:
                stats["errors"] += 1
                logger.warning(
                    "write failed source=%s collection=%s legacy_doc_id=%s error=%s",
                    source,
                    memory_name,
                    record.legacy_doc_id,
                    result.error,
                )

        logger.info(
            "batch progress source=%s collection=%s seen=%d migrated=%d skipped_existing=%d skipped_invalid=%d errors=%d dry_run=%s",
            source,
            memory_name,
            stats["seen"],
            stats["migrated"],
            stats["skipped_existing"],
            stats["skipped_invalid"],
            stats["errors"],
            args.dry_run,
        )

    return stats


def _resolve_agent_id(memory_name: str, record: Optional[LegacyMemoryRecord] = None) -> str:
    if record is not None:
        legacy_agent_id = str(record.legacy_metadata.get("agent_id") or "").strip()
        if legacy_agent_id:
            return legacy_agent_id
    if memory_name.startswith(DEFAULT_QDRANT_PREFIX):
        return memory_name[len(DEFAULT_QDRANT_PREFIX):] or memory_name

    from tradingagents.core.engine.memory_provider import MEMORY_AGENT_MAPPING

    return MEMORY_AGENT_MAPPING.get(memory_name, [memory_name])[0]


async def main_async() -> int:
    args = _parse_args()

    from app.core.database import get_mongo_db_sync
    from core.memory.service import get_memory_service

    db = get_mongo_db_sync()
    memory_service = get_memory_service(db)
    if not await memory_service._ensure_init():
        raise RuntimeError(memory_service._init_error or "mem0 is unavailable")

    qdrant_client = None
    chroma_manager = None
    available_qdrant: List[str] = []
    available_chroma: List[str] = []

    try:
        try:
            qdrant_client = _build_qdrant_client()
            available_qdrant = _list_qdrant_collection_names(qdrant_client)
        except Exception as exc:
            logger.info("qdrant unavailable: %s", exc)

        try:
            from tradingagents.agents.utils.memory import ChromaDBManager

            chroma_manager = ChromaDBManager()
            available_chroma = _list_chroma_collection_names(chroma_manager)
        except Exception as exc:
            logger.info("chroma unavailable: %s", exc)

        source = _resolve_source(args.source, available_qdrant, available_chroma)
        memory_names = _parse_memory_names(args.memory_names) or _resolve_default_memory_names(source, available_qdrant)
        legacy_reader = qdrant_client if source == "qdrant" else chroma_manager
        if legacy_reader is None:
            raise RuntimeError(f"legacy source unavailable: {source}")

        totals = {"seen": 0, "migrated": 0, "skipped_existing": 0, "skipped_invalid": 0, "errors": 0}
        logger.info("migration start source=%s memory_names=%s dry_run=%s user_id=%s", source, memory_names, args.dry_run, args.user_id)
        logger.info("available qdrant collections=%s", available_qdrant)
        logger.info("available chroma collections=%s", available_chroma)

        for memory_name in memory_names:
            stats = await _migrate_memory_name(args, source, memory_name, legacy_reader, memory_service)
            for key in totals:
                totals[key] += stats[key]

        logger.info(
            "migration finished source=%s seen=%d migrated=%d skipped_existing=%d skipped_invalid=%d errors=%d dry_run=%s",
            source,
            totals["seen"],
            totals["migrated"],
            totals["skipped_existing"],
            totals["skipped_invalid"],
            totals["errors"],
            args.dry_run,
        )
        return 0 if totals["errors"] == 0 else 1
    finally:
        close_qdrant = getattr(qdrant_client, "close", None)
        if callable(close_qdrant):
            close_qdrant()


def main() -> int:
    return asyncio.run(main_async())


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        logger.error("migration failed: %s", exc)
        raise