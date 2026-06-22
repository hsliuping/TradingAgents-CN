"""QMT 模式下的大盘与板块分析工具。"""

import logging
from typing import Annotated

from langchain_core.tools import tool

from core.tools.base import register_tool
from core.tools.qmt_market_tools import get_market_overview_qmt_enhanced, get_sector_analysis_qmt_enhanced

logger = logging.getLogger(__name__)


@tool
@register_tool(
    tool_id="get_market_overview_qmt",
    name="QMT 大盘概览",
    description="基于 QMT 指数行情、全市场快照和活跃度代理指标，生成盘面型大盘分析报告。",
    category="market",
    is_online=True,
    auto_register=True,
)
def get_market_overview_qmt(
    trade_date: Annotated[str, "分析日期，格式：YYYY-MM-DD"],
    lookback_days: Annotated[int, "回看天数，默认60天"] = 60,
) -> str:
    """基于 QMT 指数行情、全市场快照和活跃度代理指标，生成盘面型大盘分析报告。

    Args:
        trade_date: 分析日期（格式：YYYY-MM-DD）
        lookback_days: 回看天数（默认60天）

    Returns:
        str: 大盘分析报告
    """
    try:
        return get_market_overview_qmt_enhanced(trade_date, lookback_days)
    except Exception as exc:
        logger.error(f"QMT 大盘概览失败: {exc}")
        return f"❌ QMT 大盘概览失败: {exc}"


@tool
@register_tool(
    tool_id="get_sector_analysis_qmt",
    name="QMT 板块分析",
    description="基于 QMT 个股行情和本地行业映射，分析行业内部强弱、龙头与扩散情况。",
    category="market",
    is_online=True,
    auto_register=True,
)
def get_sector_analysis_qmt(
    ticker: Annotated[str, "股票代码（如 600519、000001）"],
    trade_date: Annotated[str, "分析日期，格式：YYYY-MM-DD"],
    lookback_days: Annotated[int, "回看天数，默认20天"] = 20,
    top_n: Annotated[int, "展示前N个强势成分股，默认10"] = 10,
) -> str:
    """基于 QMT 个股行情和本地行业映射，分析行业内部强弱、龙头与扩散情况。

    Args:
        ticker: 股票代码（如 600519、000001）
        trade_date: 分析日期（格式：YYYY-MM-DD）
        lookback_days: 回看天数（默认20天）
        top_n: 展示前N个强势成分股（默认10）

    Returns:
        str: 板块分析报告
    """
    try:
        return get_sector_analysis_qmt_enhanced(ticker, trade_date, lookback_days, top_n)
    except Exception as exc:
        logger.error(f"QMT 板块分析失败: {exc}")
        return f"❌ QMT 板块分析失败: {exc}"
