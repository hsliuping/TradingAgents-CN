import logging
from typing import Annotated
try:
    from langchain_core.pydantic_v1 import BaseModel, Field
except ImportError:
    from pydantic import BaseModel, Field

from tradingagents.utils.logging_init import get_logger
from tradingagents.utils.tool_logging import log_tool_call

logger = get_logger("tools.local.sentiment")

def create_unified_sentiment_tool(toolkit):
    """创建统一情绪分析工具函数"""
    
    class UnifiedSentimentInput(BaseModel):
        ticker: str = Field(description="股票代码（支持A股、港股、美股）")
        curr_date: str = Field(description="当前日期，格式：YYYY-MM-DD")
        start_date: Annotated[str, Field(description="可选：开始日期 (YYYY-MM-DD)，如果不提供则默认分析curr_date当天")] = None
        end_date: Annotated[str, Field(description="可选：结束日期 (YYYY-MM-DD)，如果不提供则默认分析curr_date当天")] = None
        source_name: Annotated[str, Field(description="可选：指定数据源名称（如'雪球'、'Reddit'），如果不支持将自动忽略")] = None

    @log_tool_call(tool_name="get_stock_sentiment_unified", log_args=True)
    def get_stock_sentiment_unified(
        ticker: str,
        curr_date: str,
        start_date: str = None,
        end_date: str = None,
        source_name: str = None
    ) -> str:
        """
        统一的股票情绪分析工具
        自动识别股票类型（A股、港股、美股）并调用相应的情绪数据源。
        请注意：通常只需要提供 ticker 和 curr_date。
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
                    from tradingagents.dataflows.interface import get_chinese_social_sentiment
                    sentiment_data = get_chinese_social_sentiment(ticker, curr_date)
                    
                    if sentiment_data and len(sentiment_data) > 50:
                        result_data.append(f"## 中文社交媒体情绪\n{sentiment_data}")
                        logger.info(f"✅ [统一情绪工具] 中文情绪数据获取成功")
                    else:
                        logger.warning(f"⚠️ [统一情绪工具] 中文情绪数据为空或过短，尝试备用源")
                        # 备用：Reddit新闻（可能包含相关讨论）
                        from tradingagents.dataflows.interface import get_reddit_company_news
                        reddit_data = get_reddit_company_news(ticker, curr_date, 7, 5)
                        result_data.append(f"## Reddit讨论(备用)\n{reddit_data}")

                except Exception as e:
                    logger.error(f"❌ [统一情绪工具] 中文情绪获取失败: {e}")
                    result_data.append(f"## 市场情绪分析\n获取失败: {e}")

            else:
                # 美股：使用Finnhub内幕交易和情绪数据
                logger.info(f"🇺🇸 [统一情绪工具] 处理美股市场情绪...")

                try:
                    # 1. 获取内幕交易情绪
                    if hasattr(toolkit, 'get_finnhub_company_insider_sentiment'):
                        insider_sentiment = toolkit.get_finnhub_company_insider_sentiment.invoke({"ticker": ticker, "curr_date": curr_date})
                        result_data.append(f"## 内部人士情绪\n{insider_sentiment}")
                    
                    # 2. 获取Reddit讨论
                    if hasattr(toolkit, 'get_reddit_stock_info'):
                        reddit_info = toolkit.get_reddit_stock_info.invoke({"ticker": ticker, "curr_date": curr_date})
                        result_data.append(f"## Reddit讨论\n{reddit_info}")

                except Exception as e:
                    logger.error(f"❌ [统一情绪工具] 美股情绪获取失败: {e}")
                    result_data.append(f"## 市场情绪分析\n获取失败: {e}")

            # 组合所有数据
            combined_result = f"""# {ticker} 市场情绪分析

**股票类型**: {market_info['market_name']}
**分析日期**: {curr_date}

{chr(10).join(result_data)}

---
*数据来源: 社交媒体、新闻评论及内部交易数据*
"""
            return combined_result

        except Exception as e:
            error_msg = f"统一情绪分析工具执行失败: {str(e)}"
            logger.error(f"❌ [统一情绪工具] {error_msg}")
            return error_msg

    # 设置工具属性
    get_stock_sentiment_unified.name = "get_stock_sentiment_unified"
    get_stock_sentiment_unified.description = """
统一股票情绪分析工具 - 获取市场对股票的情绪倾向。
自动识别股票类型并调用相应数据源（如中国社交媒体、Reddit、内部交易等）。
返回数据包括：投资者情绪指数、社交媒体热度、内部人士交易信号等。
"""
    get_stock_sentiment_unified.args_schema = UnifiedSentimentInput
    
    return get_stock_sentiment_unified
