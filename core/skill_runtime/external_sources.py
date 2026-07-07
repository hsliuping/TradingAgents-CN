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
    """同步获取外部新闻数据。

    Args:
        symbol: A 股股票代码（6 位数字或含交易所前后缀）
        source: 指定数据源（目前仅支持 "akshare"），为 None 时自动选择已配置的源
        limit: 返回新闻条数上限，默认 10
        market_category: 市场类别，默认 "a_shares"

    Returns:
        dict: 字段说明（代码中使用 .get() 或 [] 访问这些 key）——
            source: 数据源标识: "akshare" | None（无可用源或调用失败时为 None）
            data: 新闻列表，元素为按列归一化的 dict（trade_date/title/content 等字段，
                  依上游数据源而定）；无数据时为空列表 []
    """
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

    Args:
        symbol: A 股股票代码（6 位数字或含交易所前后缀）
        start_date: 起始日期（YYYY-MM-DD 或 YYYYMMDD）
        end_date: 结束日期（YYYY-MM-DD 或 YYYYMMDD）
        source: 指定数据源（"tushare" / "baostock"），为 None 时自动选择；
                baostock 不稳定会自动降级到 tushare
        market_category: 市场类别，默认 "a_shares"

    Returns:
        dict: 字段说明（代码中使用 .get() 或 [] 访问这些 key）——
            成功时直接透传 tushare provider 返回的 dict，常见字段 ——
                source: 数据源标识: "tushare"
                symbol: 标准化后的股票代码
                data: 估值序列列表，元素为 dict ——
                    trade_date: 交易日期
                    pe_ttm: 滚动市盈率
                    pb_mrq: 最近报告期市净率
                    ps_ttm: 滚动市销率
                    pcf_ttm: 滚动市现率
            失败降级时返回 ——
                source: None
                data: 空列表 []
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
    """同步获取外部历史行情。

    Args:
        symbol: A 股股票代码（6 位数字或含交易所前后缀）
        start_date: 起始日期（YYYY-MM-DD 或 YYYYMMDD）
        end_date: 结束日期（YYYY-MM-DD 或 YYYYMMDD）
        period: K 线周期，默认 "daily"；可选 "daily" / "weekly" / "monthly"（依上游数据源支持情况）
        source: 指定数据源（"tushare" / "akshare" / "baostock"），为 None 时自动选择
        market_category: 市场类别，默认 "a_shares"

    Returns:
        dict: 字段说明（代码中使用 .get() 或 [] 访问这些 key）——
            source: 数据源标识: "tushare" | "akshare" | "baostock" | None（无可用源或调用失败时为 None）
            data: 行情序列列表，元素为按列归一化的 dict（trade_date/open/high/low/close/volume
                  等字段，依上游数据源而定）；无数据时为空列表 []
    """
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
    """同步获取外部财务数据。

    Args:
        symbol: A 股股票代码（6 位数字或含交易所前后缀）
        source: 指定数据源（"tushare" / "akshare" / "baostock"），为 None 时自动选择
        market_category: 市场类别，默认 "a_shares"
        report_type: 财报类型，默认 "quarterly"；可选 "quarterly" / "annual" 等（tushare 路径使用）
        period: 报告期（如 "20240331"），为 None 时由上游默认行为决定；baostock 路径会解析为 year/quarter
        limit: 返回记录数上限，默认 4（仅 tushare 路径生效）

    Returns:
        dict: 字段说明（代码中使用 .get() 或 [] 访问这些 key）——
            source: 数据源标识: "tushare" | "akshare" | "baostock" | None（无可用源或调用失败时为 None）
            data: 财务数据，按列归一化的 dict（注意成功时为 dict 结构，而非列表）；
                  字段依上游数据源而定（如总资产/净利润/营收等），无数据时为空 dict {}
    """
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
    """同步获取按查询词聚合的外部新闻。

    Args:
        query: 查询关键词（公司名、股票名或主题词）
        curr_date: 当前日期（YYYY-MM-DD），作为查询的右端点
        look_back_days: 向前回溯天数，默认 7
        source: 数据源，默认 "google_news"；可选 "google_news" / "finnhub"

    Returns:
        dict: 字段说明（代码中使用 .get() 或 [] 访问这些 key）——
            source: 数据源标识: "google_news" | "finnhub" | None（无可用源或调用失败时为 None）
            data: 新闻聚合结果，类型依上游返回而定（通常为字符串形式的新闻摘要文本）；
                  无数据或调用失败时为空字符串 ""
    """
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