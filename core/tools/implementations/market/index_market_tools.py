"""
大盘/指数分析工具

提供指数走势分析、市场宽度分析等功能
这些工具用于 IndexAnalystV2 分析师
"""

import logging
from typing import Annotated
from langchain_core.tools import tool

from core.tools.base import register_tool
from core.tools.context import get_current_analysis_data_source

logger = logging.getLogger(__name__)


def _resolve_market_analysis_source() -> str:
    """获取当前大盘分析工具应使用的数据源。"""
    current_source = get_current_analysis_data_source()
    if current_source == "qmt":
        return "qmt"
    return "tushare"


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
    description="综合评估市场环境，包括波动、换手与市场规模等",
    category="market",
    is_online=True,
    auto_register=True
)
def get_market_environment(
    trade_date: Annotated[str, "交易日期，格式：YYYY-MM-DD"]
) -> str:
    """
    综合评估市场环境
    
    整合波动、换手和市场规模等多维度数据，给出市场环境综合评估。
    
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


@tool
@register_tool(
    tool_id="get_market_overview",
    name="市场概览",
    description="获取整体市场环境概览，包括指数走势、涨跌统计、资金流向等综合数据",
    category="market",
    is_online=True,
    auto_register=True
)
def get_market_overview(
    trade_date: Annotated[str, "交易日期，格式：YYYY-MM-DD"]
) -> str:
    """
    获取整体市场概览

    综合多维度数据，提供市场整体环境概览，包括：
    - 主要指数走势
    - 涨跌家数统计
    - 资金流向情况
    - 市场情绪评估

    这是 get_market_environment 的别名，提供相同的综合市场分析。

    Args:
        trade_date: 交易日期（格式：YYYY-MM-DD）

    Returns:
        str: 市场概览分析报告
    """
    try:
        from core.tools.index_tools import get_market_environment_sync
        return get_market_environment_sync(trade_date)
    except Exception as e:
        logger.error(f"获取市场概览失败: {e}")
        return f"❌ 获取市场概览失败: {e}"


@tool
@register_tool(
    tool_id="get_market_analysis",
    name="统一大盘分析",
    description="根据当前分析数据源自动选择 QMT 或 Tushare 路径，返回统一的大盘分析结果。",
    category="market",
    is_online=True,
    auto_register=True
)
def get_market_analysis(
    trade_date: Annotated[str, "交易日期，格式：YYYY-MM-DD"],
    lookback_days: Annotated[int, "回看天数，默认60天"] = 60
) -> str:
    """统一的大盘分析工具，自动按当前数据源路由。"""
    source = _resolve_market_analysis_source()

    if source == "qmt":
        try:
            from core.tools.qmt_market_tools import get_market_overview_qmt_sync
            return get_market_overview_qmt_sync(trade_date, lookback_days)
        except Exception as e:
            logger.error(f"QMT 大盘分析失败: {e}")
            return f"❌ QMT 大盘分析失败: {e}"

    sections = []
    tool_calls = [
        ("指数趋势", lambda: get_index_data(trade_date, lookback_days)),
        ("市场宽度", lambda: get_market_breadth(trade_date)),
        ("市场环境", lambda: get_market_environment(trade_date)),
        ("市场周期", lambda: identify_market_cycle(trade_date)),
        ("北向资金", lambda: get_north_flow(trade_date, min(lookback_days, 10))),
        ("两融余额", lambda: get_margin_trading(trade_date, min(lookback_days, 10))),
        ("涨跌停统计", lambda: get_limit_stats(trade_date)),
        ("指数技术面", lambda: get_index_technical(trade_date, lookback_days)),
    ]

    for title, producer in tool_calls:
        try:
            content = producer()
        except Exception as exc:
            logger.error(f"统一大盘分析组装失败 [{title}]: {exc}")
            content = f"❌ {title} 获取失败: {exc}"
        sections.append(f"## {title}\n{content}")

    return "\n\n".join(sections)


# ==================== 新增大盘分析工具 ====================

@tool
@register_tool(
    tool_id="get_north_flow",
    name="北向资金流向",
    description="获取沪深港通北向资金流向数据，分析外资动向",
    category="market",
    is_online=True,
    auto_register=True
)
def get_north_flow(
    trade_date: Annotated[str, "交易日期，格式：YYYY-MM-DD"],
    lookback_days: Annotated[int, "回看天数，默认10天"] = 10
) -> str:
    """
    获取北向资金流向分析

    分析沪股通、深股通资金流入流出情况，评估外资态度。

    Args:
        trade_date: 交易日期（格式：YYYY-MM-DD）
        lookback_days: 回看天数（默认10天）

    Returns:
        str: 北向资金流向分析报告
    """
    try:
        from core.tools.index_tools import get_north_flow_sync
        return get_north_flow_sync(trade_date, lookback_days)
    except Exception as e:
        logger.error(f"获取北向资金失败: {e}")
        return f"❌ 获取北向资金失败: {e}"


@tool
@register_tool(
    tool_id="get_margin_trading",
    name="两融余额",
    description="获取融资融券余额数据，描述余额水平并识别异常字段",
    category="market",
    is_online=True,
    auto_register=True
)
def get_margin_trading(
    trade_date: Annotated[str, "交易日期，格式：YYYY-MM-DD"],
    lookback_days: Annotated[int, "回看天数，默认10天"] = 10
) -> str:
    """
    获取两融余额分析

    描述融资融券余额水平，并识别变化字段中的异常或口径冲突。

    Args:
        trade_date: 交易日期（格式：YYYY-MM-DD）
        lookback_days: 回看天数（默认10天）

    Returns:
        str: 两融余额分析报告
    """
    try:
        from core.tools.index_tools import get_margin_trading_sync
        return get_margin_trading_sync(trade_date, lookback_days)
    except Exception as e:
        logger.error(f"获取两融余额失败: {e}")
        return f"❌ 获取两融余额失败: {e}"


@tool
@register_tool(
    tool_id="get_limit_stats",
    name="涨跌停统计",
    description="获取涨跌停家数和涨跌家数统计，描述涨跌分布事实",
    category="market",
    is_online=True,
    auto_register=True
)
def get_limit_stats(
    trade_date: Annotated[str, "交易日期，格式：YYYY-MM-DD"]
) -> str:
    """
    获取涨跌停和涨跌家数统计

    统计涨跌停家数、涨跌家数、涨跌幅分布，输出供上层模型归纳的事实数据。

    Args:
        trade_date: 交易日期（格式：YYYY-MM-DD）

    Returns:
        str: 涨跌停和涨跌家数分析报告
    """
    try:
        from core.tools.index_tools import get_limit_stats_sync
        return get_limit_stats_sync(trade_date)
    except Exception as e:
        logger.error(f"获取涨跌停统计失败: {e}")
        return f"❌ 获取涨跌停统计失败: {e}"


@tool
@register_tool(
    tool_id="get_index_technical",
    name="指数技术指标",
    description="获取指数技术指标（MACD、RSI、KDJ）及规则标签",
    category="market",
    is_online=True,
    auto_register=True
)
def get_index_technical(
    trade_date: Annotated[str, "交易日期，格式：YYYY-MM-DD"],
    lookback_days: Annotated[int, "回看天数，默认60天"] = 60
) -> str:
    """
    获取指数技术指标分析

    计算上证指数的MACD、RSI、KDJ等技术指标，返回指标数值与轻量规则标签。

    Args:
        trade_date: 交易日期（格式：YYYY-MM-DD）
        lookback_days: 回看天数（默认60天）

    Returns:
        str: 指数技术指标报告
    """
    try:
        from core.tools.index_tools import get_index_technical_sync
        return get_index_technical_sync(trade_date, lookback_days)
    except Exception as e:
        logger.error(f"获取指数技术指标失败: {e}")
        return f"❌ 获取指数技术指标失败: {e}"

