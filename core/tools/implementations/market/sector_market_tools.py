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
    top_n: Annotated[int, "返回前N个板块，默认10"] = 10
) -> str:
    """
    获取板块资金流向数据
    
    分析各板块的资金流入流出情况，识别主力资金动向和板块轮动趋势。
    
    Args:
        trade_date: 交易日期（格式：YYYY-MM-DD）
        top_n: 返回前N个板块（默认10）
    
    Returns:
        str: 板块资金流向分析报告
    """
    try:
        from core.tools.sector_tools import get_sector_rotation_sync
        return get_sector_rotation_sync(trade_date, top_n)
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

