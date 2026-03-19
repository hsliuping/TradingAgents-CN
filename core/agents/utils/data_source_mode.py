"""分析师数据源模式选择辅助。"""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.services.data_sources.qmt_adapter import QMTAdapter
from app.services.data_sources.tushare_adapter import TushareAdapter


_QMT_ALIASES = {"qmt", "miniqmt"}
_TUSHARE_ALIASES = {"tushare", "ts"}


def extract_preferred_data_source(state: Optional[Dict[str, Any]]) -> Optional[str]:
    if not isinstance(state, dict):
        return None
    for key in (
        "analysis_data_source",
        "preferred_data_source",
        "market_data_source",
        "data_source",
    ):
        value = state.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
    return None


def resolve_market_data_mode(state: Optional[Dict[str, Any]] = None) -> str:
    preferred = extract_preferred_data_source(state)
    tushare_available = TushareAdapter().is_available()
    qmt_available = QMTAdapter().is_available()

    if preferred in _QMT_ALIASES:
        if qmt_available:
            return "qmt"
        if tushare_available:
            return "tushare"
    if preferred in _TUSHARE_ALIASES:
        if tushare_available:
            return "tushare"
        if qmt_available:
            return "qmt"

    if tushare_available:
        return "tushare"
    if qmt_available:
        return "qmt"
    return "tushare"
