"""Skill 运行时能力目录与元数据。"""

from __future__ import annotations

from typing import Any, Dict, List, Sequence

from app.core.data_source_priority import get_enabled_data_sources_sync


SUPPORTED_COLLECTIONS = {
    "stock_basic_info",
    "market_quotes",
    "stock_daily_quotes",
    "stock_financial_data",
    "stock_financial_periods",
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
        "collection": "stock_financial_periods",
        "purpose": "按报告期展开后的标准化财务记录，适合同比、环比、多期质量与成长因子计算。",
        "preferred_access": ["get_stock_financial_periods"],
        "query_keys": ["symbol", "report_period", "ann_date", "source"],
    },
    {
        "collection": "stock_news",
        "purpose": "股票相关新闻、公告、研报与事件流。",
        "preferred_access": ["get_stock_news", "get_stock_news_by_date_range"],
        "query_keys": ["symbol", "publish_time", "source"],
    },
]


def list_supported_stock_collections() -> List[Dict[str, Any]]:
    """返回允许 Skill 访问的本地集合目录。

    Returns:
        list[dict]: 集合描述列表，每个元素字段说明——
            collection: 集合名称（如 "stock_basic_info" / "market_quotes" / "stock_daily_quotes" /
                "stock_financial_data" / "stock_financial_periods" / "stock_news"）
            purpose: 集合用途描述
            preferred_access: 推荐访问该集合的 helper 函数名列表
            query_keys: 该集合支持的查询键名列表（如 ["symbol", "code", "source"]）
    """
    return list(STOCK_COLLECTION_SUMMARY)


def list_supported_external_sources(market_category: str = "a_shares") -> List[str]:
    """返回某个市场下受支持的外部数据源。

    Args:
        market_category: 市场类别，默认为 "a_shares"。可选值："a_shares" / "hk_stocks" / "us_stocks"

    Returns:
        list[str]: 受支持的外部数据源名称列表（如 ["tushare", "akshare", "baostock"]）；
            未配置的市场类别返回空列表
    """
    return list(SUPPORTED_EXTERNAL_SOURCES.get(market_category, ()))


def list_configured_external_sources(market_category: str = "a_shares") -> List[str]:
    """返回当前配置启用的外部数据源，已过滤 local 与不受支持的数据源。

    Args:
        market_category: 市场类别，默认为 "a_shares"。可选值："a_shares" / "hk_stocks" / "us_stocks"

    Returns:
        list[str]: 当前已启用且受支持的外部数据源名称列表，元素为数据源名称字符串
    """
    configured = get_enabled_data_sources_sync(market_category=market_category)
    allowed = set(list_supported_external_sources(market_category))
    return [item for item in configured if item in allowed]