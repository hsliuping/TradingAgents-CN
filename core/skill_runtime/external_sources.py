"""Skill 运行时外部数据源桥接。"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .catalog import SUPPORTED_EXTERNAL_SOURCES, list_configured_external_sources
from .sync_wrappers import normalize_tabular_result, run_async_in_sync

logger = logging.getLogger(__name__)


def _resolve_sources(preferred_source: Optional[str], market_category: str) -> List[str]:
    if preferred_source:
        return [preferred_source]
    configured = list_configured_external_sources(market_category=market_category)
    if configured:
        return configured
    return list(SUPPORTED_EXTERNAL_SOURCES.get(market_category, ()))


def get_external_stock_news(
    symbol: str,
    source: Optional[str] = None,
    limit: int = 10,
    market_category: str = "a_shares",
) -> Dict[str, Any]:
    """同步获取外部新闻数据。"""
    for source_id in _resolve_sources(source, market_category):
        try:
            if source_id == "akshare":
                from tradingagents.dataflows.providers.china.akshare import get_akshare_provider

                provider = get_akshare_provider()
                result = provider.get_stock_news_sync(symbol, limit=limit)
                normalized = normalize_tabular_result(result)
                if normalized:
                    return {"source": source_id, "data": normalized}
        except Exception as exc:
            logger.warning("外部新闻源 %s 调用失败: %s", source_id, exc)

    return {"source": None, "data": []}


def get_external_valuation_data(
    symbol: str,
    start_date: str,
    end_date: str,
    source: Optional[str] = None,
    market_category: str = "a_shares",
) -> Dict[str, Any]:
    """同步获取外部历史估值数据（PE_TTM、PB_MRQ、PS_TTM、PCF_TTM）。

    使用 Tushare daily_basic 日期范围查询，一次调用获取全量数据。
    """
    for source_id in _resolve_sources(source, market_category):
        try:
            if source_id == "baostock":
                # Baostock 不稳定，降级到 Tushare
                pass
            elif source_id == "tushare":
                from tradingagents.dataflows.providers.china.tushare import get_tushare_provider

                provider = get_tushare_provider()
                result = run_async_in_sync(
                    provider.get_valuation_history(symbol, start_date, end_date)
                )
                if result.get("data"):
                    return result
        except Exception as exc:
            logger.warning("外部估值源 %s 调用失败: %s", source_id, exc)

    # 降级：直接再试一次 Tushare
    try:
        from tradingagents.dataflows.providers.china.tushare import get_tushare_provider

        provider = get_tushare_provider()
        result = run_async_in_sync(
            provider.get_valuation_history(symbol, start_date, end_date)
        )
        if result.get("data"):
            return result
    except Exception:
        pass

    return {"source": None, "data": []}


def get_external_historical_data(
    symbol: str,
    start_date: str,
    end_date: str,
    period: str = "daily",
    source: Optional[str] = None,
    market_category: str = "a_shares",
) -> Dict[str, Any]:
    """同步获取外部历史行情。"""
    for source_id in _resolve_sources(source, market_category):
        try:
            if source_id == "tushare":
                from tradingagents.dataflows.providers.china.tushare import get_tushare_provider

                provider = get_tushare_provider()
                result = run_async_in_sync(provider.get_historical_data(symbol, start_date, end_date, period=period))
            elif source_id == "akshare":
                from tradingagents.dataflows.providers.china.akshare import get_akshare_provider

                provider = get_akshare_provider()
                result = run_async_in_sync(provider.get_historical_data(symbol, start_date, end_date, period=period))
            elif source_id == "baostock":
                from tradingagents.dataflows.providers.china.baostock import get_baostock_provider

                provider = get_baostock_provider()
                result = run_async_in_sync(provider.get_historical_data(symbol, start_date, end_date, frequency=period))
            else:
                continue

            normalized = normalize_tabular_result(result)
            if normalized:
                return {"source": source_id, "data": normalized}
        except Exception as exc:
            logger.warning("外部历史行情源 %s 调用失败: %s", source_id, exc)

    return {"source": None, "data": []}


def get_external_financial_data(
    symbol: str,
    source: Optional[str] = None,
    market_category: str = "a_shares",
    report_type: str = "quarterly",
    period: Optional[str] = None,
    limit: int = 4,
) -> Dict[str, Any]:
    """同步获取外部财务数据。"""
    for source_id in _resolve_sources(source, market_category):
        try:
            if source_id == "tushare":
                from tradingagents.dataflows.providers.china.tushare import get_tushare_provider

                provider = get_tushare_provider()
                result = run_async_in_sync(
                    provider.get_financial_data(
                        symbol,
                        report_type=report_type,
                        period=period,
                        limit=limit,
                    )
                )
            elif source_id == "akshare":
                from tradingagents.dataflows.providers.china.akshare import get_akshare_provider

                provider = get_akshare_provider()
                result = run_async_in_sync(provider.get_financial_data(symbol))
            elif source_id == "baostock":
                from tradingagents.dataflows.providers.china.baostock import get_baostock_provider

                provider = get_baostock_provider()
                year = int(period[:4]) if period and len(period) >= 4 and str(period[:4]).isdigit() else None
                quarter = None
                if period and len(period) >= 6 and str(period[4:6]).isdigit():
                    month = int(period[4:6])
                    quarter = max(1, min(4, (month - 1) // 3 + 1))
                result = run_async_in_sync(provider.get_financial_data(symbol, year=year, quarter=quarter))
            else:
                continue

            normalized = normalize_tabular_result(result)
            if normalized:
                return {"source": source_id, "data": normalized}
        except Exception as exc:
            logger.warning("外部财务源 %s 调用失败: %s", source_id, exc)

    return {"source": None, "data": {}}


def get_external_query_news(
    query: str,
    curr_date: str,
    look_back_days: int = 7,
    source: str = "google_news",
) -> Dict[str, Any]:
    """同步获取按查询词聚合的外部新闻。"""
    try:
        if source == "google_news":
            from tradingagents.dataflows.interface import get_google_news

            return {"source": source, "data": get_google_news(query, curr_date, look_back_days)}

        if source == "finnhub":
            from tradingagents.dataflows.interface import get_finnhub_news

            return {"source": source, "data": get_finnhub_news(query, curr_date, look_back_days)}
    except Exception as exc:
        logger.warning("外部查询新闻源 %s 调用失败: %s", source, exc)

    return {"source": None, "data": ""}