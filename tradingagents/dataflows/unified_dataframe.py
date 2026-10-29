"""Compatibility wrapper for unified DataFrame-style stock data access.

This module restores the historical `tradingagents.dataflows.unified_dataframe`
contract expected by the project tests and older integrations. It provides the
standard fallback order used across the repo: Tushare -> AKShare -> Baostock,
while normalizing the returned columns to a common schema.
"""

from __future__ import annotations

from typing import Iterable, List, Optional, Sequence

import pandas as pd


def _normalize_source_name(source: object) -> str:
    if hasattr(source, "value"):
        return str(source.value).lower()
    return str(source).lower()


def _standardize_dataframe(df: Optional[pd.DataFrame]) -> pd.DataFrame:
    """Standardize a dataframe to the unified schema used by data_source_manager."""
    if df is None:
        return pd.DataFrame()
    if not isinstance(df, pd.DataFrame):
        try:
            df = pd.DataFrame(df)
        except Exception:
            return pd.DataFrame()

    if df.empty:
        return pd.DataFrame()

    out = df.copy()
    colmap = {
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "vol",
        "Amount": "amount",
        "symbol": "code",
        "Symbol": "code",
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "vol": "vol",
        "volume": "vol",
        "amount": "amount",
        "code": "code",
        "date": "date",
        "trade_date": "date",
        "日期": "date",
        "开盘": "open",
        "最高": "high",
        "最低": "low",
        "收盘": "close",
        "成交量": "vol",
        "成交额": "amount",
        "涨跌幅": "pct_change",
        "涨跌额": "change",
    }

    out = out.rename(columns={c: colmap.get(str(c), str(c)) for c in out.columns})

    if "date" in out.columns:
        try:
            out["date"] = pd.to_datetime(out["date"])
            out = out.sort_values("date")
        except Exception:
            pass

    if "pct_change" not in out.columns and "close" in out.columns:
        try:
            out["pct_change"] = out["close"].pct_change() * 100.0
        except Exception:
            pass

    return out


def get_data_source_manager():
    from tradingagents.dataflows.data_source_manager import DataSourceManager

    return DataSourceManager()


def get_tushare_adapter():
    from tradingagents.dataflows.providers.china.tushare import get_tushare_provider

    return get_tushare_provider()


def get_akshare_provider():
    from tradingagents.dataflows.providers.china.akshare import get_akshare_provider as factory

    return factory()


def get_baostock_provider():
    from tradingagents.dataflows.providers.china.baostock import get_baostock_provider as factory

    return factory()


def _provider_get_dataframe(provider: object, symbol: str, start_date: str, end_date: str):
    if provider is None:
        return None

    for method_name in ("get_stock_data", "get_daily_data", "get_historical_data"):
        method = getattr(provider, method_name, None)
        if method is None:
            continue
        try:
            result = method(symbol, start_date, end_date)
        except TypeError:
            try:
                result = method(symbol, start_date, end_date, "daily")
            except TypeError:
                try:
                    result = method(symbol)
                except TypeError:
                    continue
        if result is None:
            continue
        if isinstance(result, pd.DataFrame):
            return result
        if hasattr(result, "empty") and not result.empty:
            return result
        if isinstance(result, (list, tuple)):
            try:
                df = pd.DataFrame(result)
                if not df.empty:
                    return df
            except Exception:
                pass
    return None


def _resolve_priority_order(manager: Optional[object], explicit: Optional[Sequence[str]]) -> List[str]:
    if explicit is not None:
        return [str(s).lower() for s in explicit if str(s).strip()]

    order: List[str] = []
    current_source = getattr(manager, "current_source", None)
    if current_source is not None:
        current_name = _normalize_source_name(current_source)
        if current_name:
            order.append(current_name)

    available = getattr(manager, "available_sources", []) or []
    for source in available:
        source_name = _normalize_source_name(source)
        if source_name and source_name not in order:
            order.append(source_name)

    if not order:
        order = ["tushare", "akshare", "baostock"]

    # The repo treats Tushare as the preferred real-world source when the current
    # source is unavailable or when legacy tests inject a mocked current_source.
    for preferred in ("tushare", "akshare", "baostock"):
        if preferred not in order:
            order.append(preferred)

    return order


def get_china_daily_df_unified(
    symbol: str,
    start_date: str,
    end_date: str,
    preferred_sources: Optional[Iterable[str]] = None,
) -> pd.DataFrame:
    """Return A-share daily historical data as a standardized DataFrame.

    The function intentionally mirrors the legacy contract used by older tests and
    examples. It uses the current data source manager state when available, but it
    always falls back through the canonical order: tushare -> akshare -> baostock.
    """
    manager = get_data_source_manager()
    priority = _resolve_priority_order(manager, preferred_sources)

    getter_map = {
        "tushare": get_tushare_adapter,
        "akshare": get_akshare_provider,
        "baostock": get_baostock_provider,
    }

    for source_name in priority:
        source_name = str(source_name).lower()
        if source_name not in getter_map:
            continue
        try:
            provider = getter_map[source_name]()
            df = _provider_get_dataframe(provider, symbol, start_date, end_date)
            if df is not None:
                standardized = _standardize_dataframe(df)
                if not standardized.empty:
                    return standardized
        except Exception:
            continue

    return pd.DataFrame()


__all__ = [
    "get_china_daily_df_unified",
    "get_data_source_manager",
    "get_tushare_adapter",
    "get_akshare_provider",
    "get_baostock_provider",
    "_standardize_dataframe",
]
