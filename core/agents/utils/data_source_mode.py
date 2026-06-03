"""分析师数据源模式选择辅助。"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.services.data_sources.qmt_adapter import QMTAdapter
from app.services.data_sources.tushare_adapter import TushareAdapter

logger = logging.getLogger(__name__)

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


def _query_db_preferred_source() -> Optional[str]:
    """从数据库配置查询优先级最高的数据源。"""
    try:
        from app.core.data_source_priority import get_preferred_data_source_sync
        preferred = get_preferred_data_source_sync("a_shares")
        if preferred and preferred.strip():
            return preferred.strip().lower()
    except Exception as e:
        logger.warning(f"⚠️ 从数据库查询数据源优先级失败: {e}")
    return None


def resolve_market_data_mode(state: Optional[Dict[str, Any]] = None) -> str:
    # 1. 优先从 state 中获取显式指定的数据源
    preferred = extract_preferred_data_source(state)

    # 2. state 中没有指定时，从数据库配置查询
    if not preferred:
        preferred = _query_db_preferred_source()

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

    # 兜底：QMT 可用时优先使用 QMT（因为数据库配置了 QMT 优先）
    if qmt_available:
        return "qmt"
    if tushare_available:
        return "tushare"
    return "tushare"
