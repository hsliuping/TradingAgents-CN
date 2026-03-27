"""Skill 运行时能力目录与元数据。"""

from __future__ import annotations

from typing import Any, Dict, List, Sequence

from app.core.data_source_priority import get_enabled_data_sources_sync


SUPPORTED_COLLECTIONS = {
    "stock_basic_info",
    "market_quotes",
    "stock_daily_quotes",
    "stock_financial_data",
    "stock_news",
}

SUPPORTED_EXTERNAL_SOURCES: Dict[str, Sequence[str]] = {
    "a_shares": ("tushare", "akshare", "baostock"),
    "hk_stocks": ("akshare",),
    "us_stocks": ("google_news", "finnhub"),
}

STOCK_COLLECTION_SUMMARY: List[Dict[str, Any]] = [
    {
        "collection": "stock_basic_info",
        "purpose": "股票基础信息、行业归属、静态估值和部分交易指标。",
        "preferred_access": ["get_stock_basic_info", "get_industry_peer_basic_info", "summarize_industry_valuation"],
        "query_keys": ["symbol", "code", "source"],
    },
    {
        "collection": "market_quotes",
        "purpose": "近实时行情、涨跌、成交额和盘口相关字段。",
        "preferred_access": ["get_market_quotes"],
        "query_keys": ["symbol", "code"],
    },
    {
        "collection": "stock_daily_quotes",
        "purpose": "历史日线/K 线，供价格趋势、区间统计、技术指标计算使用。",
        "preferred_access": ["get_stock_daily_quotes"],
        "query_keys": ["symbol", "trade_date", "period", "data_source"],
    },
    {
        "collection": "stock_financial_data",
        "purpose": "财务报表与关键财务指标，供基本面分析和估值计算使用。",
        "preferred_access": ["get_stock_financial_data"],
        "query_keys": ["symbol", "report_period", "data_source", "report_type"],
    },
    {
        "collection": "stock_news",
        "purpose": "股票相关新闻、公告、研报与事件流。",
        "preferred_access": ["get_stock_news", "get_stock_news_by_date_range"],
        "query_keys": ["symbol", "publish_time", "source"],
    },
]


def list_supported_stock_collections() -> List[Dict[str, Any]]:
    """返回允许 Skill 访问的本地集合目录。"""
    return list(STOCK_COLLECTION_SUMMARY)


def list_supported_external_sources(market_category: str = "a_shares") -> List[str]:
    """返回某个市场下受支持的外部数据源。"""
    return list(SUPPORTED_EXTERNAL_SOURCES.get(market_category, ()))


def list_configured_external_sources(market_category: str = "a_shares") -> List[str]:
    """返回当前配置启用的外部数据源，已过滤 local 与不受支持的数据源。"""
    configured = get_enabled_data_sources_sync(market_category=market_category)
    allowed = set(list_supported_external_sources(market_category))
    return [item for item in configured if item in allowed]