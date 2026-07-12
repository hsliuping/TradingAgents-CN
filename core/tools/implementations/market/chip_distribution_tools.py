"""
筹码分布分析工具

提供筹码分布数据获取功能，支持 AkShare（优先）和 Tushare（备用）数据源。
这些工具用于 ChipDistributionAnalystV2 分析师。
"""

import logging
from typing import Annotated
from langchain_core.tools import tool

from core.tools.base import register_tool

logger = logging.getLogger(__name__)


@tool
@register_tool(
    tool_id="get_chip_distribution",
    name="筹码分布",
    description="获取股票筹码分布数据，分析获利比例、平均成本和筹码集中度（AkShare优先，Tushare备用）",
    category="market",
    is_online=True,
    auto_register=True,
    capability_tags=["chip_distribution", "cost_distribution", "profit_ratio", "chip_concentration", "holder_cost"],
    tool_role_hint="specialized",
    output_shape="markdown",
    preferred_for=["chip_distribution_analysis", "cost_structure_analysis", "support_resistance_identification"],
)
def get_chip_distribution(
    ticker: Annotated[str, "股票代码（如 000001 或 000001.SZ）"],
    trade_date: Annotated[str, "交易日期，格式：YYYY-MM-DD"],
) -> str:
    """
    获取股票筹码分布数据（统一接口）

    分析股票的筹码分布情况，包括：
    - 获利比例：当前价格下持仓盈利的筹码占比
    - 平均成本：所有持仓者的平均持仓成本
    - 90%/70%筹码成本区间：集中持仓的成本范围
    - 筹码集中度：筹码分布的集中程度

    数据来源优先级：AkShare（东财） → Tushare（官方API）

    Args:
        ticker: 股票代码（如 000001 或 000001.SZ）
        trade_date: 交易日期（格式：YYYY-MM-DD）

    Returns:
        str: 筹码分布分析报告
    """
    try:
        from core.tools.chip_distribution_tools import get_chip_distribution_sync
        return get_chip_distribution_sync(ticker, trade_date)
    except Exception as e:
        logger.error(f"获取筹码分布失败: {e}")
        return f"❌ 获取筹码分布失败: {e}"


@tool
@register_tool(
    tool_id="get_chip_distribution_akshare",
    name="筹码分布(AkShare)",
    description="通过 AkShare 获取股票筹码分布数据（东方财富数据源，免费）",
    category="market",
    is_online=True,
    auto_register=True,
    capability_tags=["chip_distribution", "akshare", "cost_distribution", "profit_ratio", "eastmoney"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["chip_distribution_via_akshare", "cost_structure_analysis", "free_data_source_chip"],
)
def get_chip_distribution_akshare_tool(
    ticker: Annotated[str, "股票代码（如 000001 或 000001.SZ）"],
    trade_date: Annotated[str, "交易日期，格式：YYYY-MM-DD"],
) -> str:
    """
    通过 AkShare 获取股票筹码分布数据

    使用东方财富数据接口，免费获取A股筹码分布信息。

    Args:
        ticker: 股票代码（如 000001 或 000001.SZ）
        trade_date: 交易日期（格式：YYYY-MM-DD）

    Returns:
        str: 筹码分布数据（JSON格式）或错误信息
    """
    try:
        import json
        from core.tools.chip_distribution_tools import get_chip_distribution_akshare
        data = get_chip_distribution_akshare(ticker, trade_date)
        if data:
            return json.dumps(data, ensure_ascii=False, indent=2)
        return f"❌ AkShare未能获取 {ticker} 的筹码分布数据"
    except Exception as e:
        logger.error(f"AkShare筹码分布获取失败: {e}")
        return f"❌ AkShare筹码分布获取失败: {e}"


@tool
@register_tool(
    tool_id="get_chip_distribution_tushare",
    name="筹码分布(Tushare)",
    description="通过 Tushare 获取股票筹码分布数据（官方API，需要5000积分）",
    category="market",
    is_online=True,
    auto_register=True,
    capability_tags=["chip_distribution", "tushare", "cost_distribution", "cyq_perf", "profit_ratio"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["chip_distribution_via_tushare", "cost_structure_analysis", "official_api_chip"],
)
def get_chip_distribution_tushare_tool(
    ticker: Annotated[str, "股票代码（如 000001 或 000001.SZ）"],
    trade_date: Annotated[str, "交易日期，格式：YYYY-MM-DD"],
) -> str:
    """
    通过 Tushare 获取股票筹码分布数据（cyq_perf 接口）

    使用 Tushare 官方 API 获取筹码分析数据，需要 5000 积分权限。
    包含：获利比例（winner_rate）、加权平均成本（weight_avg）、各百分位成本价格等。

    Args:
        ticker: 股票代码（如 000001 或 000001.SZ）
        trade_date: 交易日期（格式：YYYY-MM-DD）

    Returns:
        str: 筹码分布数据（JSON格式）或错误信息
    """
    try:
        import json
        from core.tools.chip_distribution_tools import get_chip_distribution_tushare
        data = get_chip_distribution_tushare(ticker, trade_date)
        if data:
            return json.dumps(data, ensure_ascii=False, indent=2)
        return f"❌ Tushare未能获取 {ticker} 的筹码分布数据（可能需要5000积分权限）"
    except Exception as e:
        logger.error(f"Tushare筹码分布获取失败: {e}")
        return f"❌ Tushare筹码分布获取失败: {e}"

