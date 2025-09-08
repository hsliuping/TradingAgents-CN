#!/usr/bin/env python3
"""
Analysis history manager

Persists each analysis result as a JSON file and maintains an index for quick listing.

Storage layout:
- data/history/index.json: list of entries metadata
- data/history/{analysis_id}.json: full raw results
"""

import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from tradingagents.utils.logging_manager import get_logger
from .async_progress_tracker import safe_serialize

logger = get_logger('history')


HISTORY_DIR = Path("data/history")
INDEX_FILE = HISTORY_DIR / "index.json"


def _ensure_dirs() -> None:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)


def _load_index() -> List[Dict[str, Any]]:
    _ensure_dirs()
    if INDEX_FILE.exists():
        try:
            with INDEX_FILE.open('r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception as e:
            logger.warning(f"Failed to load history index: {e}")
    return []


def _save_index(index: List[Dict[str, Any]]) -> None:
    _ensure_dirs()
    try:
        with INDEX_FILE.open('w', encoding='utf-8') as f:
            json.dump(index, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to save history index: {e}")


def _build_entry_from_results(analysis_id: str, results: Dict[str, Any]) -> Dict[str, Any]:
    # Extract minimal metadata for fast listing
    stock_symbol = results.get('stock_symbol') or results.get('ticker') or 'UNKNOWN'
    analysis_date = results.get('analysis_date') or results.get('date') or ''
    success = bool(results.get('success', True))
    decision = results.get('decision', {}) or {}
    action = None
    target_price = None
    confidence = None
    risk_score = None

    if isinstance(decision, dict):
        action = decision.get('action')
        target_price = decision.get('target_price')
        confidence = decision.get('confidence')
        risk_score = decision.get('risk_score')
    elif isinstance(decision, str):
        action = decision

    created_at = datetime.utcnow().isoformat() + 'Z'

    return {
        'analysis_id': analysis_id,
        'stock_symbol': stock_symbol,
        'analysis_date': analysis_date,
        'success': success,
        'action': action,
        'target_price': target_price,
        'confidence': confidence,
        'risk_score': risk_score,
        'created_at': created_at,
    }


def save_analysis_result(analysis_id: str, results: Dict[str, Any]) -> Optional[str]:
    """
    Persist the given analysis results and update index.

    Returns path to saved result file, or None on failure.
    """
    try:
        _ensure_dirs()

        # Save full results with safe serialization
        result_path = HISTORY_DIR / f"{analysis_id}.json"
        with result_path.open('w', encoding='utf-8') as f:
            # Use safe_serialize to handle LangChain messages and other non-serializable objects
            safe_results = safe_serialize(results)
            json.dump(safe_results, f, ensure_ascii=False, indent=2)

        # Update index (prepend newest). If index is missing/corrupt, rebuild from files.
        index = _load_index()
        entry = _build_entry_from_results(analysis_id, results)
        try:
            # Remove existing entry with same id if present
            index = [e for e in index if e.get('analysis_id') != analysis_id]
            index.insert(0, entry)
        except Exception:
            # Rebuild: scan history files
            index = _rebuild_index()
            index = [e for e in index if e.get('analysis_id') != analysis_id]
            index.insert(0, entry)
        # Cap index length to prevent unbounded growth
        if len(index) > 5000:
            index = index[:5000]
        _save_index(index)

        logger.info(f"Saved analysis result to {result_path}")
        return str(result_path)
    except Exception as e:
        logger.error(f"Failed to save analysis result: {e}")
        return None


def list_history(limit: int = 200, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return recent history entries, optionally filtered by symbol. Auto-rebuild if index is empty but files exist."""
    index = _load_index()
    if not index:
        # Attempt rebuild when empty index but there may be files
        index = _rebuild_index()
    if symbol:
        index = [e for e in index if str(e.get('stock_symbol', '')).upper() == str(symbol).upper()]
    return index[:limit]


def get_history_item(analysis_id: str) -> Optional[Dict[str, Any]]:
    """Load a full saved result by id."""
    result_path = HISTORY_DIR / f"{analysis_id}.json"
    if not result_path.exists():
        return None
    try:
        with result_path.open('r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to read history item {analysis_id}: {e}")
        return None


def _rebuild_index() -> List[Dict[str, Any]]:
    """Rebuild index from existing history files."""
    _ensure_dirs()
    entries: List[Dict[str, Any]] = []
    try:
        for file in HISTORY_DIR.glob("*.json"):
            try:
                with file.open('r', encoding='utf-8') as f:
                    data = json.load(f)
                    analysis_id = file.stem
                    entries.append(_build_entry_from_results(analysis_id, data))
            except Exception:
                continue
        # Sort by created_at desc if present
        entries.sort(key=lambda e: e.get('created_at', ''), reverse=True)
        _save_index(entries)
    except Exception as e:
        logger.warning(f"Failed to rebuild history index: {e}")
    return entries


