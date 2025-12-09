"""
MCP 情绪分析工具

使用 FastMCP 的 @mcp.tool() 装饰器定义统一情绪分析工具。
保留现有的社交媒体情绪分析逻辑，支持 A股、港股、美股。
"""

import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# 全局 toolkit 配置
_toolkit_config: dict = {}


def set_toolkit_config(config: dict):
    """设置工具配置"""
    global _toolkit_config
    _toolkit_config = config or {}


def get_stock_sentiment(
    ticker: str,
    curr_date: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    source_name: Optional[str] = None
) -> str:
    """
    统一股票情绪分析工具 - 获取市场对股票的情绪倾向。
    
    自动识别股票类型并调用相应数据源（如中国社交媒体、Reddit、内部交易等）。
    返回数据包括：投资者情绪指数、社交媒体热度、内部人士交易信号等。
    
    Args:
        ticker: 股票代码，支持多种格式：
            - A股：如 '600519', '000001', '300750'
            - 港股：如 '0700.HK', '09988'
            - 美股：如 'AAPL', 'TSLA', 'NVDA'
        curr_date: 当前日期，格式：YYYY-MM-DD
        start_date: 可选：开始日期 (YYYY-MM-DD)，如果不提供则默认分析curr_date当天
        end_date: 可选：结束日期 (YYYY-MM-DD)，如果不提供则默认分析curr_date当天
        source_name: 可选：指定数据源名称（如'雪球'、'Reddit'），如果不支持将自动忽略
    
    Returns:
        格式化的情绪分析数据，包含情绪指数和社交媒体热度
    """
    logger.info(f"😊 [MCP情绪工具] 分析股票: {ticker}")
    start_time = datetime.now()

    try:
        from tradingagents.utils.stock_utils import StockUtils

        # 自动识别股票类型
        market_info = StockUtils.get_market_info(ticker)
        is_china = market_info['is_china']
        is_hk = market_info['is_hk']
        is_us = market_info['is_us']

        logger.info(f"😊 [MCP情绪工具] 股票类型: {market_info['market_name']}")

        result_data = []

        if is_china or is_hk:
            # 中国A股和港股：使用社交媒体情绪分析
            logger.info(f"🇨🇳🇭🇰 [MCP情绪工具] 处理中文市场情绪...")

            try:
                from tradingagents.dataflows.interface import get_chinese_social_sentiment
                sentiment_data = get_chinese_social_sentiment(ticker, curr_date)
                
                if sentiment_data and len(sentiment_data) > 50:
                    result_data.append(f"## 中文社交媒体情绪\n{sentiment_data}")
                    logger.info(f"✅ [MCP情绪工具] 中文情绪数据获取成功")
                else:
                    logger.warning(f"⚠️ [MCP情绪工具] 中文情绪数据为空或过短，尝试备用源")
                    # 备用：Reddit新闻
                    try:
                        from tradingagents.dataflows.interface import get_reddit_company_news
                        reddit_data = get_reddit_company_news(ticker, curr_date, 7, 5)
                        result_data.append(f"## Reddit讨论(备用)\n{reddit_data}")
                    except Exception as e:
                        result_data.append(f"## 社交媒体情绪\n⚠️ 数据获取失败: {e}")

            except Exception as e:
                logger.error(f"❌ [MCP情绪工具] 中文情绪获取失败: {e}")
                result_data.append(f"## 市场情绪分析\n⚠️ 获取失败: {e}")

        else:
            # 美股：使用Finnhub内幕交易和情绪数据
            logger.info(f"🇺🇸 [MCP情绪工具] 处理美股市场情绪...")

            try:
                # 尝试获取内幕交易情绪
                try:
                    from tradingagents.dataflows.interface import get_finnhub_insider_sentiment
                    insider_sentiment = get_finnhub_insider_sentiment(ticker, curr_date)
                    if insider_sentiment:
                        result_data.append(f"## 内部人士情绪\n{insider_sentiment}")
                except Exception as e:
                    logger.warning(f"⚠️ [MCP情绪工具] 内幕交易数据获取失败: {e}")
                
                # 尝试获取Reddit讨论
                try:
                    from tradingagents.dataflows.interface import get_reddit_company_news
                    reddit_info = get_reddit_company_news(ticker, curr_date, 7, 5)
                    if reddit_info:
                        result_data.append(f"## Reddit讨论\n{reddit_info}")
                except Exception as e:
                    logger.warning(f"⚠️ [MCP情绪工具] Reddit数据获取失败: {e}")

                if not result_data:
                    result_data.append("## 市场情绪分析\n⚠️ 暂无可用的情绪数据")

            except Exception as e:
                logger.error(f"❌ [MCP情绪工具] 美股情绪获取失败: {e}")
                result_data.append(f"## 市场情绪分析\n⚠️ 获取失败: {e}")

        # 计算执行时间
        execution_time = (datetime.now() - start_time).total_seconds()

        # 组合所有数据
        combined_result = f"""# {ticker} 市场情绪分析

**股票类型**: {market_info['market_name']}
**分析日期**: {curr_date}
**执行时间**: {execution_time:.2f}秒

{chr(10).join(result_data)}

---
*数据来源: 社交媒体、新闻评论及内部交易数据*
"""
        
        logger.info(f"😊 [MCP情绪工具] 数据获取完成，总长度: {len(combined_result)}")
        return combined_result

    except Exception as e:
        error_msg = f"❌ 统一情绪分析工具执行失败: {str(e)}"
        logger.error(f"[MCP情绪工具] {error_msg}")
        return f"""# {ticker} 市场情绪分析

⚠️ **错误**: {error_msg}

**建议**:
- 检查股票代码是否正确
- 稍后重试或尝试其他工具
"""
