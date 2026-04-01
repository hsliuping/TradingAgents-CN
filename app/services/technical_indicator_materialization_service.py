from __future__ import annotations

from datetime import datetime
from typing import Callable, Dict, Iterable, List, Optional

import pandas as pd

from app.core.database import get_mongo_db_sync
from core.tools.implementations.technical.indicators import IndicatorSpec, compute_many


LOOKBACK_LIMIT = 120
TECHNICAL_SPECS = [
    IndicatorSpec("ma", {"n": 20}),
    IndicatorSpec("macd"),
    IndicatorSpec("rsi", {"n": 14}),
    IndicatorSpec("kdj", {"n": 9, "m1": 3, "m2": 3}),
]
OUTPUT_FIELDS = ["ma20", "rsi14", "kdj_k", "kdj_d", "kdj_j", "dif", "dea", "macd_hist"]

ProgressLogger = Optional[Callable[[str], None]]


def _safe_float(value: object) -> Optional[float]:
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _iter_symbol_sources(collection) -> Iterable[Dict[str, str]]:
    pipeline = [
        {"$match": {"period": "daily"}},
        {
            "$group": {
                "_id": {
                    "code": {"$ifNull": ["$code", "$symbol"]},
                    "symbol": {"$ifNull": ["$symbol", "$code"]},
                    "source": "$data_source",
                }
            }
        },
        {"$sort": {"_id.code": 1, "_id.source": 1}},
    ]
    for row in collection.aggregate(pipeline, allowDiskUse=True):
        item = row.get("_id") or {}
        code = str(item.get("code") or "").zfill(6)
        symbol = str(item.get("symbol") or code).zfill(6)
        source = str(item.get("source") or "")
        if not code or not source:
            continue
        yield {"code": code, "symbol": symbol, "source": source}


def _load_recent_quotes(collection, symbol: str, source: str) -> List[Dict[str, object]]:
    cursor = collection.find(
        {"symbol": symbol, "data_source": source, "period": "daily"},
        {
            "_id": 0,
            "trade_date": 1,
            "open": 1,
            "high": 1,
            "low": 1,
            "close": 1,
            "volume": 1,
            "amount": 1,
        },
    ).sort("trade_date", -1).limit(LOOKBACK_LIMIT)
    return list(cursor)


def _build_snapshot(symbol_row: Dict[str, str], quotes: List[Dict[str, object]]) -> Optional[Dict[str, object]]:
    if len(quotes) < 35:
        return None

    frame = pd.DataFrame(quotes)
    if frame.empty or "trade_date" not in frame.columns:
        return None

    frame = frame.sort_values("trade_date").reset_index(drop=True)
    frame["vol"] = frame.get("volume")
    enriched = compute_many(frame, TECHNICAL_SPECS)
    last = enriched.iloc[-1]

    trade_date = last.get("trade_date")
    if trade_date is None:
        return None

    snapshot = {
        "code": symbol_row["code"],
        "symbol": symbol_row["symbol"],
        "source": symbol_row["source"],
        "trade_date": str(trade_date),
        "updated_at": datetime.utcnow(),
        "version": 1,
    }
    for field in OUTPUT_FIELDS:
        snapshot[field] = _safe_float(last.get(field))

    if all(snapshot.get(field) is None for field in OUTPUT_FIELDS):
        return None

    return snapshot


def materialize_technical_indicators(progress_every: int = 200, progress_logger: ProgressLogger = None) -> Dict[str, int]:
    db = get_mongo_db_sync()
    quote_collection = db["stock_daily_quotes"]
    target_collection = db["stock_technical_indicators"]

    processed = 0
    written = 0

    for symbol_row in _iter_symbol_sources(quote_collection):
        processed += 1
        quotes = _load_recent_quotes(quote_collection, symbol_row["symbol"], symbol_row["source"])
        snapshot = _build_snapshot(symbol_row, quotes)
        if snapshot is None:
            continue

        target_collection.update_one(
            {
                "code": snapshot["code"],
                "source": snapshot["source"],
                "trade_date": snapshot["trade_date"],
            },
            {
                "$set": snapshot,
                "$setOnInsert": {"created_at": snapshot["updated_at"]},
            },
            upsert=True,
        )
        written += 1

        if progress_logger and processed % progress_every == 0:
            progress_logger(f"processed={processed} written={written}")

    if progress_logger:
        progress_logger(f"done processed={processed} written={written}")

    return {"processed": processed, "written": written}
