"""
板块分析工具

提供板块表现分析、轮动识别、同业对比等功能
这些工具用于 SectorAnalystV2 分析师
"""

import logging
from typing import Annotated
from langchain_core.tools import tool

from core.tools.base import register_tool

logger = logging.getLogger(__name__)


@tool
@register_tool(
    tool_id="get_sector_data",
    name="板块数据",
    description="获取股票所属板块的表现数据，分析行业趋势",
    category="market",
    is_online=True,
    auto_register=True
)
def get_sector_data(
    ticker: Annotated[str, "股票代码（如 000001 或 000001.SZ）"],
    trade_date: Annotated[str, "交易日期，格式：YYYY-MM-DD"],
    lookback_days: Annotated[int, "回看天数，默认20天"] = 20
) -> str:
    """
    获取股票所属板块的表现数据
    
    分析股票所属行业板块的近期表现，包括涨跌幅、资金流向、板块排名等。
    
    Args:
        ticker: 股票代码（如 000001 或 000001.SZ）
        trade_date: 交易日期（格式：YYYY-MM-DD）
        lookback_days: 回看天数（默认20天）
    
    Returns:
        str: 板块表现分析报告
    """
    try:
        from core.tools.sector_tools import get_sector_performance_sync
        return get_sector_performance_sync(ticker, trade_date, lookback_days)
    except Exception as e:
        logger.error(f"获取板块数据失败: {e}")
        return f"❌ 获取板块数据失败: {e}"


@tool
@register_tool(
    tool_id="get_fund_flow_data",
    name="资金流向",
    description="获取板块资金流向数据，分析主力资金动向",
    category="market",
    is_online=True,
    auto_register=True
)
def get_fund_flow_data(
    trade_date: Annotated[str, "交易日期，格式：YYYY-MM-DD"],
    top_n: Annotated[int, "返回前N个板块，默认10"] = 10,
    lookback_days: Annotated[int, "回溯天数，1=仅当天，30=最近一个月累计，默认1"] = 1
) -> str:
    """
    获取板块资金流向数据

    分析各板块的资金流入流出情况，识别主力资金动向和板块轮动趋势。
    支持单日快照（lookback_days=1）和多日累计聚合（lookback_days>1）两种模式。

    Args:
        trade_date: 截止交易日期（格式：YYYY-MM-DD）
        top_n: 返回前N个板块（默认10）
        lookback_days: 回溯天数，1=仅当天，30=最近一个月累计（默认1）

    Returns:
        str: 板块资金流向分析报告
    """
    try:
        from core.tools.sector_tools import get_sector_rotation_sync
        return get_sector_rotation_sync(trade_date, top_n, lookback_days)
    except Exception as e:
        logger.error(f"获取资金流向失败: {e}")
        return f"❌ 获取资金流向失败: {e}"


@tool
@register_tool(
    tool_id="get_peer_comparison",
    name="同业对比",
    description="获取同行业股票对比数据，分析个股在行业中的位置",
    category="market",
    is_online=True,
    auto_register=True
)
def get_peer_comparison(
    ticker: Annotated[str, "股票代码（如 000001 或 000001.SZ）"],
    trade_date: Annotated[str, "交易日期，格式：YYYY-MM-DD"],
    top_n: Annotated[int, "返回前N个同业股票，默认10"] = 10
) -> str:
    """
    获取同行业股票对比数据
    
    分析目标股票在同行业中的表现排名，包括涨跌幅、市值、估值等维度的对比。
    
    Args:
        ticker: 股票代码（如 000001 或 000001.SZ）
        trade_date: 交易日期（格式：YYYY-MM-DD）
        top_n: 返回前N个同业股票（默认10）
    
    Returns:
        str: 同业对比分析报告
    """
    try:
        from core.tools.sector_tools import get_peer_comparison_sync
        return get_peer_comparison_sync(ticker, trade_date, top_n)
    except Exception as e:
        logger.error(f"获取同业对比失败: {e}")
        return f"❌ 获取同业对比失败: {e}"


@tool
@register_tool(
    tool_id="analyze_sector",
    name="综合板块分析",
    description="综合分析股票所属板块，包括表现、轮动、同业对比等",
    category="market",
    is_online=True,
    auto_register=True
)
def analyze_sector(
    ticker: Annotated[str, "股票代码（如 000001 或 000001.SZ）"],
    trade_date: Annotated[str, "交易日期，格式：YYYY-MM-DD"]
) -> str:
    """
    综合板块分析
    
    整合板块表现、资金流向、同业对比等多维度数据，给出综合板块分析报告。
    
    Args:
        ticker: 股票代码（如 000001 或 000001.SZ）
        trade_date: 交易日期（格式：YYYY-MM-DD）
    
    Returns:
        str: 综合板块分析报告
    """
    try:
        from core.tools.sector_tools import analyze_sector_sync
        return analyze_sector_sync(ticker, trade_date)
    except Exception as e:
        logger.error(f"综合板块分析失败: {e}")
        return f"❌ 综合板块分析失败: {e}"


# ============================================================
# 板块级别工具（以板块名称为入口，无需 ticker）
# ============================================================

@tool
@register_tool(
    tool_id="search_sector",
    name="板块搜索",
    description="按名称关键词搜索A股板块（行业/概念/地域），返回匹配的板块列表",
    category="market",
    is_online=True,
    auto_register=True,
    when_to_use="当用户提到板块、行业、概念等关键词，需要先查找板块代码时使用",
)
def search_sector_tool(
    keyword: Annotated[str, "板块名称关键词（如 光伏、半导体、白酒、新能源）"],
    sector_type: Annotated[str, "板块类型: N=行业 S=概念 R=地域，默认N"] = "N",
) -> str:
    """
    按名称关键词搜索同花顺板块

    返回匹配的板块列表，包含板块代码、名称、成分股数量。

    Args:
        keyword: 板块名称关键词
        sector_type: 板块类型（N=行业, S=概念, R=地域）

    Returns:
        str: 板块搜索结果
    """
    try:
        from core.tools.sector_tools import search_sector_sync
        return search_sector_sync(keyword, sector_type)
    except Exception as e:
        logger.error(f"板块搜索失败: {e}")
        return f"❌ 板块搜索失败: {e}"


@tool
@register_tool(
    tool_id="get_sector_daily",
    name="板块行情",
    description="获取板块指数的日线行情数据，包括涨跌幅、成交量、换手率、市值等",
    category="market",
    is_online=True,
    auto_register=True,
    when_to_use="当用户想了解某个板块的近期走势、涨跌情况时使用",
)
def get_sector_daily_tool(
    sector_name: Annotated[str, "板块名称关键词（如 光伏、半导体、白酒）"],
    trade_date: Annotated[str, "交易日期，格式：YYYY-MM-DD"],
    lookback_days: Annotated[int, "回看天数，默认20天"] = 20,
) -> str:
    """
    获取板块指数日线行情

    Args:
        sector_name: 板块名称关键词
        trade_date: 交易日期
        lookback_days: 回看天数

    Returns:
        str: 板块行情报告
    """
    try:
        from core.tools.sector_tools import get_sector_daily_sync
        return get_sector_daily_sync(sector_name, trade_date, lookback_days)
    except Exception as e:
        logger.error(f"板块行情获取失败: {e}")
        return f"❌ 板块行情获取失败: {e}"


@tool
@register_tool(
    tool_id="get_sector_constituents",
    name="板块成分股",
    description="获取板块的成分股列表及其市值、估值排名",
    category="market",
    is_online=True,
    auto_register=True,
    when_to_use="当用户想知道某个板块有哪些股票、龙头股是哪些时使用",
)
def get_sector_constituents_tool(
    sector_name: Annotated[str, "板块名称关键词（如 光伏、半导体、白酒）"],
    trade_date: Annotated[str, "交易日期，格式：YYYY-MM-DD"],
    top_n: Annotated[int, "返回前N只成分股，默认15"] = 15,
) -> str:
    """
    获取板块成分股列表及表现

    Args:
        sector_name: 板块名称关键词
        trade_date: 交易日期
        top_n: 返回前N只成分股

    Returns:
        str: 板块成分股报告
    """
    try:
        from core.tools.sector_tools import get_sector_constituents_sync
        return get_sector_constituents_sync(sector_name, trade_date, top_n)
    except Exception as e:
        logger.error(f"板块成分股获取失败: {e}")
        return f"❌ 板块成分股获取失败: {e}"


@tool
@register_tool(
    tool_id="analyze_sector_by_name",
    name="板块综合分析",
    description="按板块名称进行综合分析，整合板块行情、成分股龙头、全市场资金流向",
    category="market",
    is_online=True,
    auto_register=True,
    when_to_use="当用户问某个板块的投资机会、板块分析、行业前景时使用",
)
def analyze_sector_by_name_tool(
    sector_name: Annotated[str, "板块名称关键词（如 光伏、半导体、白酒、新能源汽车）"],
    trade_date: Annotated[str, "交易日期，格式：YYYY-MM-DD"],
) -> str:
    """
    板块综合分析（以板块名称为入口）

    Args:
        sector_name: 板块名称关键词
        trade_date: 交易日期

    Returns:
        str: 板块综合分析报告
    """
    try:
        from core.tools.sector_tools import analyze_sector_by_name_sync
        return analyze_sector_by_name_sync(sector_name, trade_date)
    except Exception as e:
        logger.error(f"板块综合分析失败: {e}")
        return f"❌ 板块综合分析失败: {e}"

