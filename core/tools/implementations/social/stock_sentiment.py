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
                # 尝试使用 AKShareProvider 获取新闻进行情绪分析
                from tradingagents.dataflows.providers.china.akshare import AKShareProvider
                ak_provider = AKShareProvider()
                
                # 清理代码后缀
                clean_ticker = ticker
                for suffix in ['.SH', '.SZ', '.SS', '.HK', '.XSHE', '.XSHG']:
                    clean_ticker = clean_ticker.replace(suffix, '')
                
                # 获取新闻 (优先使用 _get_stock_news_direct 如果公开接口不可用)
                if hasattr(ak_provider, 'get_stock_news_sync'):
                    news_df = ak_provider.get_stock_news_sync(symbol=clean_ticker)
                else:
                    news_df = ak_provider._get_stock_news_direct(symbol=clean_ticker)
                
                if news_df is not None and not news_df.empty:
                    # 简单分析
                    news_titles = []
                    # 兼容不同的列名
                    col_map = {'新闻标题': 'title', '标题': 'title', 'title': 'title'}
                    
                    for col in news_df.columns:
                        if col in col_map:
                            news_titles = news_df[col].tolist()
                            break
                    
                    if not news_titles and not news_df.empty:
                         # 如果没找到标题列，尝试第一列
                         news_titles = news_df.iloc[:, 0].astype(str).tolist()

                    # 关键词统计
                    pos_words = ['上涨', '利好', '增长', '突破', '买入', '增持', '大涨', '新高', '预增']
                    neg_words = ['下跌', '利空', '减少', '跌破', '卖出', '减持', '大跌', '新低', '亏损']
                    
                    pos_count = 0
                    neg_count = 0
                    
                    recent_titles = news_titles[:10] # 只看最近10条
                    
                    for title in recent_titles:
                        if not isinstance(title, str): continue
                        for w in pos_words:
                            if w in title: pos_count += 1
                        for w in neg_words:
                            if w in title: neg_count += 1
                            
                    sentiment_score = "中性"
                    if pos_count > neg_count: sentiment_score = "偏多"
                    if neg_count > pos_count: sentiment_score = "偏空"
                    
                    sentiment_summary = f"""## 中文市场情绪分析
**股票**: {ticker}
**情绪评级**: {sentiment_score} (正向词:{pos_count}, 负向词:{neg_count})

### 最近新闻摘要
{chr(10).join(['- ' + str(t) for t in recent_titles[:5]])}

*基于最近 {len(recent_titles)} 条新闻标题分析*
"""
                    result_data.append(sentiment_summary)
                else:
                    result_data.append(f"## 中文市场情绪\n暂无相关新闻数据 (API返回空)")
                    
            except Exception as e:
                logger.error(f"中文情绪分析失败: {e}")
                result_data.append(f"## 中文市场情绪\n分析失败: {e}")

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

