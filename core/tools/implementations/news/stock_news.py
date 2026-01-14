"""
统一股票新闻工具

自动识别股票类型（A股、港股、美股）并调用相应的新闻数据源
"""

import logging
from typing import Annotated
from langchain_core.tools import tool
from datetime import datetime, timedelta

from core.tools.base import register_tool

logger = logging.getLogger(__name__)


@tool
@register_tool(
    tool_id="get_stock_news_unified",
    name="统一股票新闻",
    description="获取股票相关新闻，支持A股、港股、美股",
    category="news",
    is_online=True,
    auto_register=True
)
def get_stock_news_unified(
    ticker: Annotated[str, "股票代码（支持A股、港股、美股）"],
    curr_date: Annotated[str, "当前日期，格式：YYYY-MM-DD"]
) -> str:
    """
    统一的股票新闻工具
    自动识别股票类型（A股、港股、美股）并调用相应的新闻数据源

    Args:
        ticker: 股票代码（如：000001、0700.HK、AAPL）
        curr_date: 当前日期（格式：YYYY-MM-DD）

    Returns:
        str: 新闻分析报告
    """
    logger.info(f"📰 [统一新闻工具] 分析股票: {ticker}")

    try:
        from tradingagents.utils.stock_utils import StockUtils

        # 自动识别股票类型
        market_info = StockUtils.get_market_info(ticker)
        is_china = market_info['is_china']
        is_hk = market_info['is_hk']
        is_us = market_info['is_us']

        logger.info(f"📰 [统一新闻工具] 股票类型: {market_info['market_name']}")

        # 计算新闻查询的日期范围
        # 处理可能包含时间的日期字符串（如 "2026-01-14 00:00:00"）
        curr_date_clean = curr_date.split()[0] if ' ' in curr_date else curr_date
        end_date = datetime.strptime(curr_date_clean, '%Y-%m-%d')
        start_date = end_date - timedelta(days=7)
        start_date_str = start_date.strftime('%Y-%m-%d')

        result_data = []

        if is_china or is_hk:
            # 中国A股和港股：使用AKShare东方财富新闻和Google新闻
            logger.info(f"🇨🇳🇭🇰 [统一新闻工具] 处理中文新闻...")

            # 1. 尝试获取AKShare东方财富新闻
            try:
                clean_ticker = ticker.replace('.SH', '').replace('.SZ', '').replace('.SS', '')\
                               .replace('.HK', '').replace('.XSHE', '').replace('.XSHG', '')

                from tradingagents.dataflows.providers.china.akshare import AKShareProvider
                provider = AKShareProvider()
                news_df = provider.get_stock_news_sync(symbol=clean_ticker)

                if news_df is not None and not news_df.empty:
                    em_news_items = []
                    for _, row in news_df.iterrows():
                        news_title = row.get('新闻标题', '') or row.get('标题', '')
                        news_time = row.get('发布时间', '') or row.get('时间', '')
                        news_url = row.get('新闻链接', '') or row.get('链接', '')
                        news_item = f"- **{news_title}** [{news_time}]({news_url})"
                        em_news_items.append(news_item)

                    if em_news_items:
                        em_news_text = "\n".join(em_news_items)
                        result_data.append(f"## 东方财富新闻\n{em_news_text}")
                        logger.info(f"✅ 成功获取{len(em_news_items)}条东方财富新闻")
            except Exception as em_e:
                logger.error(f"❌ 东方财富新闻获取失败: {em_e}")
                result_data.append(f"## 东方财富新闻\n获取失败: {em_e}")

            # 2. 获取Google新闻作为补充
            try:
                if is_china:
                    clean_ticker = ticker.replace('.SH', '').replace('.SZ', '').replace('.SS', '')\
                                   .replace('.XSHE', '').replace('.XSHG', '')
                    search_query = f"{clean_ticker} 股票 公司 财报 新闻"
                else:
                    search_query = f"{ticker} 港股"

                from tradingagents.dataflows.interface import get_google_news
                news_data = get_google_news(search_query, curr_date)
                result_data.append(f"## Google新闻\n{news_data}")
                logger.info(f"✅ 成功获取Google新闻")
            except Exception as google_e:
                logger.error(f"❌ Google新闻获取失败: {google_e}")
                result_data.append(f"## Google新闻\n获取失败: {google_e}")

        else:
            # 美股：使用Finnhub新闻
            logger.info(f"🇺🇸 [统一新闻工具] 处理美股新闻...")

            try:
                from tradingagents.dataflows.interface import get_finnhub_news
                news_data = get_finnhub_news(ticker, start_date_str, curr_date)
                result_data.append(f"## 美股新闻\n{news_data}")
            except Exception as e:
                result_data.append(f"## 美股新闻\n获取失败: {e}")

        # 组合所有数据
        combined_result = f"""# {ticker} 新闻分析

**股票类型**: {market_info['market_name']}
**分析日期**: {curr_date}
**新闻时间范围**: {start_date_str} 至 {curr_date}

{chr(10).join(result_data)}

---
*数据来源: 根据股票类型自动选择最适合的新闻源*
"""

        logger.info(f"📰 [统一新闻工具] 数据获取完成，总长度: {len(combined_result)}")
        return combined_result

    except Exception as e:
        error_msg = f"统一新闻工具执行失败: {str(e)}"
        logger.error(f"❌ [统一新闻工具] {error_msg}")
        return error_msg

