"""
大盘/指数分析工具

提供指数走势分析、市场宽度分析等功能
这些工具用于 IndexAnalystV2 分析师
"""

import logging
from typing import Annotated
from langchain_core.tools import tool

from core.tools.base import register_tool

logger = logging.getLogger(__name__)


@tool
@register_tool(
    tool_id="get_index_data",
    name="指数数据",
    description="获取主要指数数据（上证、深证、创业板等），分析大盘走势和趋势",
    category="market",
    is_online=True,
    auto_register=True
)
def get_index_data(
    trade_date: Annotated[str, "交易日期，格式：YYYY-MM-DD"],
    lookback_days: Annotated[int, "回看天数，默认60天"] = 60
) -> str:
    """
    获取主要指数数据和走势分析
    
    分析上证指数、深证成指、创业板指、沪深300、中证500等主要指数的走势，
    包括今日涨跌、5日/20日涨跌幅、均线位置和趋势判断。
    
    Args:
        trade_date: 交易日期（格式：YYYY-MM-DD）
        lookback_days: 回看天数，用于计算均线和趋势（默认60天）
    
    Returns:
        str: 指数走势分析报告
    """
    try:
        from core.tools.index_tools import get_index_trend_sync
        return get_index_trend_sync(trade_date, lookback_days)
    except Exception as e:
        logger.error(f"获取指数数据失败: {e}")
        return f"❌ 获取指数数据失败: {e}"


@tool
@register_tool(
    tool_id="get_market_breadth",
    name="市场宽度",
    description="分析市场宽度（涨跌家数、涨停跌停等），评估市场整体情绪",
    category="market",
    is_online=True,
    auto_register=True
)
def get_market_breadth(
    trade_date: Annotated[str, "交易日期，格式：YYYY-MM-DD"]
) -> str:
    """
    分析市场宽度
    
    统计涨跌家数、涨停跌停数量、成交量分布等，评估市场整体参与度和情绪。
    
    Args:
        trade_date: 交易日期（格式：YYYY-MM-DD）
    
    Returns:
        str: 市场宽度分析报告
    """
    try:
        from core.tools.index_tools import get_market_breadth_sync
        return get_market_breadth_sync(trade_date)
    except Exception as e:
        logger.error(f"获取市场宽度失败: {e}")
        return f"❌ 获取市场宽度失败: {e}"


@tool
@register_tool(
    tool_id="get_market_environment",
    name="市场环境",
    description="综合评估市场环境，包括指数走势、市场宽度、资金流向等",
    category="market",
    is_online=True,
    auto_register=True
)
def get_market_environment(
    trade_date: Annotated[str, "交易日期，格式：YYYY-MM-DD"]
) -> str:
    """
    综合评估市场环境
    
    整合指数走势、市场宽度、资金流向等多维度数据，给出市场环境综合评估。
    
    Args:
        trade_date: 交易日期（格式：YYYY-MM-DD）
    
    Returns:
        str: 市场环境综合评估报告
    """
    try:
        from core.tools.index_tools import get_market_environment_sync
        return get_market_environment_sync(trade_date)
    except Exception as e:
        logger.error(f"获取市场环境失败: {e}")
        return f"❌ 获取市场环境失败: {e}"


@tool
@register_tool(
    tool_id="identify_market_cycle",
    name="市场周期识别",
    description="识别当前市场所处的周期阶段（牛市、熊市、震荡等）",
    category="market",
    is_online=True,
    auto_register=True
)
def identify_market_cycle(
    trade_date: Annotated[str, "交易日期，格式：YYYY-MM-DD"]
) -> str:
    """
    识别市场周期
    
    基于技术指标和市场数据，识别当前市场所处的周期阶段。
    
    Args:
        trade_date: 交易日期（格式：YYYY-MM-DD）
    
    Returns:
        str: 市场周期分析报告
    """
    try:
        from core.tools.index_tools import identify_market_cycle_sync
        return identify_market_cycle_sync(trade_date)
    except Exception as e:
        logger.error(f"识别市场周期失败: {e}")
        return f"❌ 识别市场周期失败: {e}"

