"""
Migrate persisted historical manager decisions from report files into mem0.

Usage:
    python app/scripts/migrate_historical_manager_reports_to_mem0.py --dry-run
    python app/scripts/migrate_historical_manager_reports_to_mem0.py --ticker 000002
    python app/scripts/migrate_historical_manager_reports_to_mem0.py --source progress-json --limit 20
"""

from __future__ import annotations

import argparse
import ast
import asyncio
import json
import logging
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("historical.manager_report_migration")


DEFAULT_USER_ID = "legacy_tradingagents"
MIGRATION_SOURCE = "historical_manager_report_migration"
REPORT_SOURCE_ANALYSIS_RESULTS = "analysis-results"
REPORT_SOURCE_PROGRESS_JSON = "progress-json"
_SYMBOL_PATTERN = re.compile(r"\b(?:sh|sz|bj|hk)\.\d{5,6}\b|\b\d{6}(?:\.[A-Z]{2})?\b", re.IGNORECASE)
_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_REPORT_AGENT_MAPPING = {
    "research_team_decision.md": "research_manager_v2",
    "risk_management_decision.md": "risk_manager_v2",
}


@dataclass
class HistoricalManagerRecord:
    target_agent_id: str
    legacy_doc_id: str
    content: str
    ticker: str = ""
    analysis_date: str = ""
    source_kind: str = ""
    source_file: str = ""
    title: str = ""
    legacy_metadata: Dict[str, Any] = field(default_factory=dict)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate persisted manager report history into mem0")
    parser.add_argument(
        "--source",
        choices=["auto", REPORT_SOURCE_ANALYSIS_RESULTS, REPORT_SOURCE_PROGRESS_JSON, "all"],
        default="auto",
        help="Report source type. auto prefers stable analysis_results reports and falls back to progress JSON.",
    )
    parser.add_argument("--ticker", default="", help="Only migrate a specific ticker")
    parser.add_argument("--user-id", default=DEFAULT_USER_ID, help="Target mem0 user_id")
    parser.add_argument("--session-prefix", default="manager_report_migration", help="run_id prefix for migrated memories")
    parser.add_argument("--limit", type=int, default=0, help="Maximum records to migrate, 0 means unlimited")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, do not write to mem0")
    parser.add_argument(
        "--allow-duplicates",
        action="store_true",
        help="Write even if the same historical record was migrated before",
    )
    parser.add_argument("--preview", type=int, default=3, help="How many records to preview in dry-run logs")
    return parser.parse_args()


def _normalize_ticker(value: str) -> str:
    text = str(value or "").strip().upper()
    if not text or text == "UNKNOWN":
        return ""
    return text


def _extract_symbol(text: str) -> str:
    match = _SYMBOL_PATTERN.search(str(text or ""))
    return match.group(0).upper() if match else ""


def _safe_read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _normalize_source_file(path: Path) -> str:
    try:
        return path.relative_to(ROOT_DIR).as_posix()
    except ValueError:
        parts = list(path.parts)
        if "data" in parts:
            index = parts.index("data")
            return Path(*parts[index:]).as_posix()
        return path.as_posix()


def _parse_report_payload(raw_text: str) -> Dict[str, Any]:
    text = str(raw_text or "").strip()
    if not text:
        return {}

    if not text.startswith("{"):
        return {"judge_decision": text}

    try:
        parsed = ast.literal_eval(text)
    except Exception:
        return {"judge_decision": text}

    return parsed if isinstance(parsed, dict) else {"judge_decision": text}


def _extract_report_content(payload: Dict[str, Any]) -> str:
    for key in ("judge_decision", "current_response", "decision", "content", "markdown", "text"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _build_analysis_result_record(path: Path) -> Optional[HistoricalManagerRecord]:
    target_agent_id = _REPORT_AGENT_MAPPING.get(path.name)
    if not target_agent_id:
        return None

    payload = _parse_report_payload(_safe_read_text(path))
    content = _extract_report_content(payload)
    if not content:
        return None

    ticker_dir = path.parents[2].name if len(path.parents) >= 3 else ""
    analysis_date = path.parents[1].name if len(path.parents) >= 2 and _DATE_PATTERN.match(path.parents[1].name) else ""
    ticker = _normalize_ticker(ticker_dir) or _extract_symbol(content)
    relative_path = _normalize_source_file(path)

    return HistoricalManagerRecord(
        target_agent_id=target_agent_id,
        legacy_doc_id=f"report:{target_agent_id}:{relative_path}",
        content=content,
        ticker=ticker,
        analysis_date=analysis_date,
        source_kind=REPORT_SOURCE_ANALYSIS_RESULTS,
        source_file=relative_path,
        title=path.stem,
        legacy_metadata={
            "report_file_name": path.name,
            "history_available": bool(payload.get("history")),
        },
    )


def _build_progress_records(path: Path, payload: Dict[str, Any]) -> List[HistoricalManagerRecord]:
    ticker = (
        _normalize_ticker(payload.get("company_of_interest") or "")
        or _normalize_ticker(payload.get("ticker") or "")
    )
    analysis_date = str(payload.get("trade_date") or payload.get("analysis_date") or "").strip()
    relative_path = _normalize_source_file(path)

    records: List[HistoricalManagerRecord] = []
    source_slots = [
        ("research_manager_v2", "investment_debate_state", "judge_decision"),
        ("risk_manager_v2", "risk_debate_state", "judge_decision"),
    ]

    for target_agent_id, state_key, decision_key in source_slots:
        state = payload.get(state_key)
        if not isinstance(state, dict):
            continue

        content = str(state.get(decision_key) or "").strip()
        if not content:
            continue

        resolved_ticker = ticker or _extract_symbol(content)
        records.append(
            HistoricalManagerRecord(
                target_agent_id=target_agent_id,
                legacy_doc_id=f"progress:{target_agent_id}:{relative_path}",
                content=content,
                ticker=resolved_ticker,
                analysis_date=analysis_date,
                source_kind=REPORT_SOURCE_PROGRESS_JSON,
                source_file=relative_path,
                title=path.stem,
                legacy_metadata={
                    "session_id": str(payload.get("session_id") or "").strip(),
                    "sender": str(payload.get("sender") or "").strip(),
                },
            )
        )

    return records


def _load_progress_payload(path: Path) -> Dict[str, Any]:
    try:
        raw = _safe_read_text(path)
        payload = json.loads(raw)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _iter_analysis_result_records(data_dir: Path, ticker_filter: str = "") -> Iterable[HistoricalManagerRecord]:
    for report_name in sorted(_REPORT_AGENT_MAPPING):
        for path in sorted(data_dir.glob(f"analysis_results/**/reports/{report_name}")):
            record = _build_analysis_result_record(path)
            if record is None:
                continue
            if ticker_filter and record.ticker != ticker_filter:
                continue
            yield record


def _iter_progress_json_records(data_dir: Path, ticker_filter: str = "") -> Iterable[HistoricalManagerRecord]:
    candidates = list(sorted(data_dir.glob("progress_analysis_*.json")))
    candidates.extend(sorted(data_dir.glob("temp/processing/progress_analysis_*.json")))

    for path in candidates:
        payload = _load_progress_payload(path)
        if not payload:
            continue
        for record in _build_progress_records(path, payload):
            if ticker_filter and record.ticker != ticker_filter:
                continue
            yield record


def _collect_records(data_dir: Path, requested_source: str, ticker_filter: str) -> List[HistoricalManagerRecord]:
    if requested_source == REPORT_SOURCE_ANALYSIS_RESULTS:
        return list(_iter_analysis_result_records(data_dir, ticker_filter))
    if requested_source == REPORT_SOURCE_PROGRESS_JSON:
        return list(_iter_progress_json_records(data_dir, ticker_filter))
    if requested_source == "all":
        return list(_iter_analysis_result_records(data_dir, ticker_filter)) + list(_iter_progress_json_records(data_dir, ticker_filter))

    analysis_records = list(_iter_analysis_result_records(data_dir, ticker_filter))
    if analysis_records:
        return analysis_records
    return list(_iter_progress_json_records(data_dir, ticker_filter))


def _build_store_messages(record: HistoricalManagerRecord) -> List[Dict[str, str]]:
    return [{"role": "user", "content": record.content}]


def _build_store_metadata(record: HistoricalManagerRecord) -> Dict[str, Any]:
    metadata: Dict[str, Any] = {
        "source": MIGRATION_SOURCE,
        "legacy_doc_id": record.legacy_doc_id,
        "source_kind": record.source_kind,
        "source_file": record.source_file,
        "target_agent_id": record.target_agent_id,
        "title": record.title,
    }
    if record.analysis_date:
        metadata["analysis_date"] = record.analysis_date
        metadata["legacy_timestamp"] = record.analysis_date
    if record.ticker:
        metadata["ticker"] = record.ticker
        metadata["symbol"] = record.ticker
        metadata["object_type"] = "stock"
        metadata["object_key"] = record.ticker
    metadata.update(record.legacy_metadata)
    return metadata


def _build_session_id(prefix: str, record: HistoricalManagerRecord) -> str:
    ticker = record.ticker or "unknown"
    return f"{prefix}:{record.target_agent_id}:{ticker}"


async def _load_existing_legacy_doc_ids(memory_service: Any, user_id: str, target_agent_id: str) -> set[str]:
    existing_ids: set[str] = set()
    page = 1

    while True:
        result = await memory_service.get_all(
            user_id=user_id,
            scopes=["agent_experience"],
            metadata_filters={
                "source": MIGRATION_SOURCE,
                "target_agent_id": target_agent_id,
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


def _preview_text(content: str, limit: int = 160) -> str:
    return str(content or "").strip().replace("\n", " ")[:limit]


async def _migrate_records(args: argparse.Namespace, records: Sequence[HistoricalManagerRecord], memory_service: Any) -> Dict[str, int]:
    stats = {"seen": 0, "migrated": 0, "skipped_existing": 0, "skipped_invalid": 0, "errors": 0}
    preview_logged = 0
    existing_by_agent: Dict[str, set[str]] = {}

    for record in records:
        stats["seen"] += 1

        if not record.content.strip():
            stats["skipped_invalid"] += 1
            continue

        if not args.allow_duplicates:
            if record.target_agent_id not in existing_by_agent:
                existing_by_agent[record.target_agent_id] = await _load_existing_legacy_doc_ids(
                    memory_service,
                    args.user_id,
                    record.target_agent_id,
                )
            if record.legacy_doc_id in existing_by_agent[record.target_agent_id]:
                stats["skipped_existing"] += 1
                continue

        if args.dry_run:
            if preview_logged < max(0, args.preview):
                logger.info(
                    "dry-run preview source=%s agent_id=%s legacy_doc_id=%s ticker=%s content=%s",
                    record.source_kind,
                    record.target_agent_id,
                    record.legacy_doc_id,
                    record.ticker,
                    _preview_text(record.content),
                )
                preview_logged += 1
            stats["migrated"] += 1
            continue

        result = await memory_service.store(
            _build_store_messages(record),
            user_id=args.user_id,
            agent_id=record.target_agent_id,
            session_id=_build_session_id(args.session_prefix, record),
            scope="agent_experience",
            metadata=_build_store_metadata(record),
            infer=False,
        )
        if result.success:
            stats["migrated"] += 1
            existing_by_agent.setdefault(record.target_agent_id, set()).add(record.legacy_doc_id)
        else:
            stats["errors"] += 1
            logger.warning(
                "write failed source=%s agent_id=%s legacy_doc_id=%s error=%s",
                record.source_kind,
                record.target_agent_id,
                record.legacy_doc_id,
                result.error,
            )

    return stats


async def main_async() -> int:
    args = _parse_args()

    from app.core.database import get_mongo_db_sync
    from core.memory.service import get_memory_service

    db = get_mongo_db_sync()
    memory_service = get_memory_service(db)
    if not await memory_service._ensure_init():
        raise RuntimeError(memory_service._init_error or "mem0 is unavailable")

    ticker_filter = _normalize_ticker(args.ticker)
    data_dir = ROOT_DIR / "data"
    records = _collect_records(data_dir, args.source, ticker_filter)
    if args.limit > 0:
        records = records[: args.limit]

    logger.info(
        "migration start source=%s ticker=%s records=%d dry_run=%s user_id=%s",
        args.source,
        ticker_filter or "ALL",
        len(records),
        args.dry_run,
        args.user_id,
    )

    stats = await _migrate_records(args, records, memory_service)
    logger.info(
        "migration finished source=%s seen=%d migrated=%d skipped_existing=%d skipped_invalid=%d errors=%d dry_run=%s",
        args.source,
        stats["seen"],
        stats["migrated"],
        stats["skipped_existing"],
        stats["skipped_invalid"],
        stats["errors"],
        args.dry_run,
    )
    return 0 if stats["errors"] == 0 else 1


def main() -> int:
    return asyncio.run(main_async())


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        logger.error("migration failed: %s", exc)
        raise