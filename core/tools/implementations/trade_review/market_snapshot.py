"""
获取市场快照工具

获取交易期间的市场数据快照，用于复盘分析
"""

import logging
from typing import Dict, Any, Optional, Annotated
from core.tools.base import register_tool

logger = logging.getLogger(__name__)


@register_tool(
    tool_id="get_market_snapshot_for_review",
    name="获取市场快照",
    description="获取交易期间的K线数据和市场快照，用于复盘分析",
    category="trade_review",
    is_online=True
)
def get_market_snapshot_for_review(
    code: Annotated[str, "股票代码"],
    market: Annotated[str, "市场: 'CN'(A股) 或 'US'(美股)"],
    start_date: Annotated[Optional[str], "开始日期 YYYY-MM-DD"] = None,
    end_date: Annotated[Optional[str], "结束日期 YYYY-MM-DD"] = None
) -> Dict[str, Any]:
    """
    获取市场快照

    Args:
        code: 股票代码
        market: 市场类型
        start_date: 开始日期
        end_date: 结束日期

    Returns:
        包含K线数据的字典
    """
    try:
        from tradingagents.dataflows.interface import get_stock_data_unified
        from datetime import datetime, timedelta
        import asyncio

        if not start_date or not end_date:
            # 默认获取最近3个月的数据
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")

        # 扩展日期范围（前后各10天）
        query_start = (datetime.strptime(start_date, "%Y-%m-%d") - timedelta(days=10)).strftime("%Y-%m-%d")
        query_end = (datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=10)).strftime("%Y-%m-%d")

        async def _fetch_kline():
            # 获取K线数据
            return await get_stock_data_unified(
                ticker=code,
                start_date=query_start,
                end_date=query_end,
                market_type=market.lower()
            )

        # 在同步上下文中运行异步代码
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        kline_data = loop.run_until_complete(_fetch_kline())

        logger.info(f"✅ 获取市场快照成功: {code}, {len(kline_data) if isinstance(kline_data, list) else 'N/A'} 条K线")

        return {
            "success": True,
            "data": {
                "code": code,
                "market": market,
                "start_date": start_date,
                "end_date": end_date,
                "kline_data": kline_data
            }
        }

    except Exception as e:
        logger.error(f"❌ 获取市场快照失败: {e}")
        return {
            "success": False,
            "error": str(e),
            "data": None
        }

