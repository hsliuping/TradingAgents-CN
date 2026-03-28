"""
历史统一 DataFrame 接口兼容层。

为旧测试保留 ``get_china_daily_df_unified``，实际桥接到当前数据源实现。
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from tradingagents.dataflows.data_source_manager import get_data_source_manager
from tradingagents.dataflows.providers.china.akshare import get_akshare_provider
from tradingagents.dataflows.providers.china.baostock import get_baostock_provider
from tradingagents.dataflows.providers.china.tushare import get_tushare_provider


def get_tushare_adapter() -> Any:
    """兼容旧测试中的 tushare adapter 入口。"""
    return get_tushare_provider()


def _normalize_daily_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    normalized = df.copy()
    normalized.columns = [str(col).strip().lower() for col in normalized.columns]

    rename_map = {
        "date": "trade_date",
        "datetime": "trade_date",
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "volume": "volume",
        "vol": "volume",
        "amount": "amount",
    }
    normalized = normalized.rename(columns=rename_map)
    return normalized


def get_china_daily_df_unified(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    依次尝试 tushare -> akshare -> baostock，返回标准化日线 DataFrame。
    """
    manager = get_data_source_manager()
    current_source = getattr(getattr(manager, "current_source", None), "value", "tushare")
    fallback_sources = list(getattr(manager, "available_sources", []) or [])

    source_order = [current_source, *fallback_sources]
    deduped_sources: list[str] = []
    for source in source_order:
        if source and source not in deduped_sources:
            deduped_sources.append(source)

    provider_map = {
        "tushare": get_tushare_adapter,
        "akshare": get_akshare_provider,
        "baostock": get_baostock_provider,
    }

    for source_name in deduped_sources:
        factory = provider_map.get(source_name)
        if factory is None:
            continue

        provider = factory()
        fetch = getattr(provider, "get_stock_data", None)
        if fetch is None:
            continue

        df = fetch(symbol, start_date, end_date)
        normalized = _normalize_daily_dataframe(df)
        if not normalized.empty:
            return normalized

    return pd.DataFrame()

