"""
统一股票市场数据工具

自动识别股票类型（A股、港股、美股）并调用相应的数据源
"""

import logging
import re
from typing import Annotated
from langchain_core.tools import tool

from core.tools.base import register_tool

logger = logging.getLogger(__name__)


@tool
@register_tool(
    tool_id="get_stock_market_data_unified",
    name="统一股票市场数据",
    description="获取股票市场数据和技术指标，支持A股、港股、美股",
    category="market",
    is_online=True,
    auto_register=True
)
def get_stock_market_data_unified(
    ticker: Annotated[str, "股票代码（支持A股、港股、美股）"],
    start_date: Annotated[str, "开始日期，格式：YYYY-MM-DD。注意：系统会自动扩展到配置的回溯天数（通常为365天），你只需要传递分析日期即可"],
    end_date: Annotated[str, "结束日期，格式：YYYY-MM-DD。通常与start_date相同，传递当前分析日期即可"]
) -> str:
    """
    统一的股票市场数据工具
    自动识别股票类型（A股、港股、美股）并调用相应的数据源获取价格和技术指标数据

    ⚠️ 重要：系统会自动扩展日期范围到配置的回溯天数（通常为365天），以确保技术指标计算有足够的历史数据。
    你只需要传递当前分析日期作为 start_date 和 end_date 即可，无需手动计算历史日期范围。

    Args:
        ticker: 股票代码（如：000001、0700.HK、AAPL）
        start_date: 开始日期（格式：YYYY-MM-DD）。传递当前分析日期即可，系统会自动扩展
        end_date: 结束日期（格式：YYYY-MM-DD）。传递当前分析日期即可

    Returns:
        str: 市场数据和技术分析报告

    示例：
        如果分析日期是 2025-11-09，传递：
        - ticker: "00700.HK"
        - start_date: "2025-11-09"
        - end_date: "2025-11-09"
        系统会自动获取 2024-11-09 到 2025-11-09 的365天历史数据
    """
    # 标准化 A股代码：去掉 .SZ/.SH/.BJ 后缀（前后端统一使用纯6位数字）
    original_ticker = ticker
    ticker = re.sub(r'\.(SZ|SH|BJ|sz|sh|bj)$', '', ticker.strip())
    if original_ticker != ticker:
        logger.info(f"📈 [统一市场工具] 标准化股票代码: {original_ticker} -> {ticker}")

    logger.info(f"📈 [统一市场工具] 分析股票: {ticker}")

    try:
        from tradingagents.utils.stock_utils import StockUtils

        # 自动识别股票类型
        market_info = StockUtils.get_market_info(ticker)
        is_china = market_info['is_china']
        is_hk = market_info['is_hk']
        is_us = market_info['is_us']

        logger.info(f"📈 [统一市场工具] 股票类型: {market_info['market_name']}")
        logger.info(f"📈 [统一市场工具] 货币: {market_info['currency_name']} ({market_info['currency_symbol']})")

        result_data = []

        if is_china:
            # 中国A股：使用中国股票数据源
            logger.info(f"🇨🇳 [统一市场工具] 处理A股市场数据...")

            try:
                from tradingagents.dataflows.interface import get_china_stock_data_unified
                stock_data = get_china_stock_data_unified(ticker, start_date, end_date)

                # 🔍 调试：打印返回数据的前500字符
                logger.info(f"🔍 [市场工具调试] A股数据返回长度: {len(stock_data)}")
                logger.info(f"🔍 [市场工具调试] A股数据前500字符:\n{stock_data[:500]}")

                result_data.append(f"## A股市场数据\n{stock_data}")
            except Exception as e:
                logger.error(f"❌ [市场工具调试] A股数据获取失败: {e}")
                result_data.append(f"## A股市场数据\n获取失败: {e}")

        elif is_hk:
            # 港股：使用AKShare数据源
            logger.info(f"🇭🇰 [统一市场工具] 处理港股市场数据...")

            try:
                from tradingagents.dataflows.interface import get_hk_stock_data_unified
                hk_data = get_hk_stock_data_unified(ticker, start_date, end_date)

                # 🔍 调试：打印返回数据的前500字符
                logger.info(f"🔍 [市场工具调试] 港股数据返回长度: {len(hk_data)}")
                logger.info(f"🔍 [市场工具调试] 港股数据前500字符:\n{hk_data[:500]}")

                result_data.append(f"## 港股市场数据\n{hk_data}")
            except Exception as e:
                logger.error(f"❌ [市场工具调试] 港股数据获取失败: {e}")
                result_data.append(f"## 港股市场数据\n获取失败: {e}")

        else:
            # 美股：优先使用FINNHUB API数据源
            logger.info(f"🇺🇸 [统一市场工具] 处理美股市场数据...")

            try:
                from tradingagents.dataflows.providers.us.optimized import get_us_stock_data_cached
                us_data = get_us_stock_data_cached(ticker, start_date, end_date)
                result_data.append(f"## 美股市场数据\n{us_data}")
            except Exception as e:
                result_data.append(f"## 美股市场数据\n获取失败: {e}")

        # 组合所有数据
        combined_result = f"""# {ticker} 市场数据分析

**股票类型**: {market_info['market_name']}
**货币**: {market_info['currency_name']} ({market_info['currency_symbol']})
**分析期间**: {start_date} 至 {end_date}

{chr(10).join(result_data)}

---
*数据来源: 根据股票类型自动选择最适合的数据源*
"""

        logger.info(f"📈 [统一市场工具] 数据获取完成，总长度: {len(combined_result)}")
        return combined_result

    except Exception as e:
        error_msg = f"统一市场数据工具执行失败: {str(e)}"
        logger.error(f"❌ [统一市场工具] {error_msg}")
        return error_msg

