"""
统一股票基本面数据工具

自动识别股票类型（A股、港股、美股）并调用相应的数据源
"""

import logging
from typing import Annotated, Optional
from langchain_core.tools import tool
from datetime import datetime, timedelta

from core.tools.base import register_tool

logger = logging.getLogger(__name__)


@tool
@register_tool(
    tool_id="get_stock_fundamentals_unified",
    name="统一股票基本面数据",
    description="获取股票基本面分析数据，支持A股、港股、美股",
    category="fundamentals",
    is_online=True,
    auto_register=True
)
def get_stock_fundamentals_unified(
    ticker: Annotated[str, "股票代码（支持A股、港股、美股）"],
    start_date: Annotated[Optional[str], "开始日期，格式：YYYY-MM-DD"] = None,
    end_date: Annotated[Optional[str], "结束日期，格式：YYYY-MM-DD"] = None,
    curr_date: Annotated[Optional[str], "当前日期，格式：YYYY-MM-DD"] = None
) -> str:
    """
    统一的股票基本面分析工具
    自动识别股票类型（A股、港股、美股）并调用相应的数据源
    支持基于分析级别的数据获取策略

    Args:
        ticker: 股票代码（如：000001、0700.HK、AAPL）
        start_date: 开始日期（可选，格式：YYYY-MM-DD）
        end_date: 结束日期（可选，格式：YYYY-MM-DD）
        curr_date: 当前日期（可选，格式：YYYY-MM-DD）

    Returns:
        str: 基本面分析数据和报告
    """
    logger.info(f"📊 [统一基本面工具] 分析股票: {ticker}")

    try:
        from tradingagents.utils.stock_utils import StockUtils

        # 自动识别股票类型
        market_info = StockUtils.get_market_info(ticker)
        is_china = market_info['is_china']
        is_hk = market_info['is_hk']
        is_us = market_info['is_us']

        logger.info(f"📊 [统一基本面工具] 股票类型: {market_info['market_name']}")

        # 设置默认日期
        if not curr_date:
            curr_date = datetime.now().strftime('%Y-%m-%d')

        # 基本面分析只需要最近的数据
        days_to_fetch = 10
        if not start_date:
            start_date = (datetime.now() - timedelta(days=days_to_fetch)).strftime('%Y-%m-%d')
        if not end_date:
            end_date = curr_date

        result_data = []

        if is_china:
            # 中国A股
            logger.info(f"🇨🇳 [统一基本面工具] 处理A股数据...")

            try:
                # 获取最新股价信息
                recent_end_date = curr_date
                recent_start_date = (datetime.strptime(curr_date, '%Y-%m-%d') - timedelta(days=2)).strftime('%Y-%m-%d')

                from tradingagents.dataflows.interface import get_china_stock_data_unified
                current_price_data = get_china_stock_data_unified(ticker, recent_start_date, recent_end_date)
                result_data.append(f"## A股当前价格信息\n{current_price_data}")
            except Exception as e:
                logger.error(f"❌ A股价格数据获取失败: {e}")
                result_data.append(f"## A股当前价格信息\n获取失败: {e}")

            try:
                # 获取基本面财务数据
                from tradingagents.dataflows.optimized_china_data import OptimizedChinaDataProvider
                analyzer = OptimizedChinaDataProvider()
                fundamentals_data = analyzer._generate_fundamentals_report(ticker, current_price_data if 'current_price_data' in locals() else "", "standard")
                result_data.append(f"## A股基本面财务数据\n{fundamentals_data}")
            except Exception as e:
                logger.error(f"❌ A股基本面数据获取失败: {e}")
                result_data.append(f"## A股基本面财务数据\n获取失败: {e}")

        elif is_hk:
            # 港股
            logger.info(f"🇭🇰 [统一基本面工具] 处理港股数据...")

            try:
                from tradingagents.dataflows.interface import get_hk_stock_data_unified
                hk_data = get_hk_stock_data_unified(ticker, start_date, end_date)

                if hk_data and len(hk_data) > 100 and "❌" not in hk_data:
                    result_data.append(f"## 港股数据\n{hk_data}")
                else:
                    raise ValueError("港股数据质量不佳")
            except Exception as e:
                logger.error(f"❌ 港股数据获取失败: {e}")
                result_data.append(f"## 港股数据\n获取失败: {e}")

        else:
            # 美股
            logger.info(f"🇺🇸 [统一基本面工具] 处理美股数据...")

            try:
                from tradingagents.dataflows.interface import get_fundamentals_openai
                us_data = get_fundamentals_openai(ticker, curr_date)
                result_data.append(f"## 美股基本面数据\n{us_data}")
            except Exception as e:
                logger.error(f"❌ 美股数据获取失败: {e}")
                result_data.append(f"## 美股基本面数据\n获取失败: {e}")

        # 组合所有数据
        combined_result = f"""# {ticker} 基本面分析数据

**股票类型**: {market_info['market_name']}
**货币**: {market_info['currency_name']} ({market_info['currency_symbol']})
**分析日期**: {curr_date}

{chr(10).join(result_data)}

---
*数据来源: 根据股票类型自动选择最适合的数据源*
"""

        logger.info(f"📊 [统一基本面工具] 数据获取完成，总长度: {len(combined_result)}")
        return combined_result

    except Exception as e:
        error_msg = f"统一基本面分析工具执行失败: {str(e)}"
        logger.error(f"❌ [统一基本面工具] {error_msg}")
        return error_msg

