"""
统一股票情绪分析工具

自动识别股票类型（A股、港股、美股）并调用相应的情绪数据源
"""

import logging
from typing import Annotated
from langchain_core.tools import tool

from core.tools.base import register_tool

logger = logging.getLogger(__name__)


@tool
@register_tool(
    tool_id="get_stock_sentiment_unified",
    name="统一股票情绪分析",
    description="获取股票市场情绪和社交媒体情绪，支持A股、港股、美股",
    category="social",
    is_online=True,
    auto_register=True
)
def get_stock_sentiment_unified(
    ticker: Annotated[str, "股票代码（支持A股、港股、美股）"],
    curr_date: Annotated[str, "当前日期，格式：YYYY-MM-DD"]
) -> str:
    """
    统一的股票情绪分析工具
    自动识别股票类型（A股、港股、美股）并调用相应的情绪数据源

    Args:
        ticker: 股票代码（如：000001、0700.HK、AAPL）
        curr_date: 当前日期（格式：YYYY-MM-DD）

    Returns:
        str: 情绪分析报告
    """
    logger.info(f"😊 [统一情绪工具] 分析股票: {ticker}")

    try:
        from tradingagents.utils.stock_utils import StockUtils

        # 自动识别股票类型
        market_info = StockUtils.get_market_info(ticker)
        is_china = market_info['is_china']
        is_hk = market_info['is_hk']
        is_us = market_info['is_us']

        logger.info(f"😊 [统一情绪工具] 股票类型: {market_info['market_name']}")

        result_data = []

        if is_china or is_hk:
            # 中国A股和港股：使用社交媒体情绪分析
            logger.info(f"🇨🇳🇭🇰 [统一情绪工具] 处理中文市场情绪...")

            try:
                sentiment_summary = f"""
## 中文市场情绪分析

**股票**: {ticker} ({market_info['market_name']})
**分析日期**: {curr_date}

### 市场情绪概况
- 由于中文社交媒体情绪数据源暂未完全集成，当前提供基础分析
- 建议关注雪球、东方财富、同花顺等平台的讨论热度
- 港股市场还需关注香港本地财经媒体情绪

### 情绪指标
- 整体情绪: 中性
- 讨论热度: 待分析
- 投资者信心: 待评估

*注：完整的中文社交媒体情绪分析功能正在开发中*
"""
                result_data.append(sentiment_summary)
            except Exception as e:
                result_data.append(f"## 中文市场情绪\n获取失败: {e}")

        else:
            # 美股：使用Reddit情绪分析
            logger.info(f"🇺🇸 [统一情绪工具] 处理美股情绪...")

            try:
                from tradingagents.dataflows.interface import get_reddit_sentiment

                sentiment_data = get_reddit_sentiment(ticker, curr_date)
                result_data.append(f"## 美股Reddit情绪\n{sentiment_data}")
            except Exception as e:
                result_data.append(f"## 美股Reddit情绪\n获取失败: {e}")

        # 组合所有数据
        combined_result = f"""# {ticker} 情绪分析

**股票类型**: {market_info['market_name']}
**分析日期**: {curr_date}

{chr(10).join(result_data)}

---
*数据来源: 根据股票类型自动选择最适合的情绪数据源*
"""

        logger.info(f"😊 [统一情绪工具] 数据获取完成，总长度: {len(combined_result)}")
        return combined_result

    except Exception as e:
        error_msg = f"统一情绪分析工具执行失败: {str(e)}"
        logger.error(f"❌ [统一情绪工具] {error_msg}")
        return error_msg

