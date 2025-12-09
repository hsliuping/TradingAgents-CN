"""
MCP 市场数据工具

使用 FastMCP 的 @mcp.tool() 装饰器定义统一市场数据获取工具。
保留现有的自动市场类型检测逻辑，支持 A股、港股、美股。
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


def get_stock_market_data(
    ticker: str,
    start_date: str,
    end_date: str
) -> str:
    """
    统一股票市场数据工具 - 获取股票的历史价格、技术指标和市场表现。
    
    自动识别股票类型（A股/港股/美股）并调用最佳数据源：
    - A股: Tushare、AKShare
    - 港股: AKShare
    - 美股: FinnHub、yfinance
    
    返回数据包括：K线数据、移动平均线、MACD、RSI、布林带等技术指标。
    
    Args:
        ticker: 股票代码，支持多种格式：
            - A股：如 '600519', '000001', '300750'
            - 港股：如 '0700.HK', '09988'
            - 美股：如 'AAPL', 'TSLA', 'NVDA'
        start_date: 开始日期，格式：YYYY-MM-DD
            注意：系统会自动扩展到配置的回溯天数（通常为365天）
        end_date: 结束日期，格式：YYYY-MM-DD
            通常与start_date相同，传递当前分析日期即可
    
    Returns:
        格式化的市场数据，包含K线、技术指标等
    """
    logger.info(f"📈 [MCP市场工具] 分析股票: {ticker}")
    start_time = datetime.now()

    try:
        from tradingagents.utils.stock_utils import StockUtils
        
        # 自动识别股票类型
        market_info = StockUtils.get_market_info(ticker)
        is_china = market_info['is_china']
        is_hk = market_info['is_hk']
        is_us = market_info['is_us']

        logger.info(f"📈 [MCP市场工具] 股票类型: {market_info['market_name']}")

        result_data = []

        if is_china:
            # 中国A股
            logger.info(f"🇨🇳 [MCP市场工具] 处理A股市场数据...")
            try:
                from tradingagents.dataflows.interface import get_china_stock_data_unified
                cn_data = get_china_stock_data_unified(ticker, start_date, end_date)
                result_data.append(f"## A股市场数据\n{cn_data}")
            except Exception as e:
                logger.error(f"❌ [MCP市场工具] A股数据获取失败: {e}")
                result_data.append(f"## A股市场数据\n⚠️ 获取失败: {e}")

        elif is_hk:
            # 港股
            logger.info(f"🇭🇰 [MCP市场工具] 处理港股市场数据...")
            try:
                from tradingagents.dataflows.interface import get_hk_stock_data_unified
                hk_data = get_hk_stock_data_unified(ticker, start_date, end_date)
                result_data.append(f"## 港股市场数据\n{hk_data}")
            except Exception as e:
                logger.error(f"❌ [MCP市场工具] 港股数据获取失败: {e}")
                result_data.append(f"## 港股市场数据\n⚠️ 获取失败: {e}")

        else:
            # 美股
            logger.info(f"🇺🇸 [MCP市场工具] 处理美股市场数据...")
            try:
                from tradingagents.dataflows.providers.us.optimized import get_us_stock_data_cached
                us_data = get_us_stock_data_cached(ticker, start_date, end_date)
                result_data.append(f"## 美股市场数据\n{us_data}")
            except Exception as e:
                logger.error(f"❌ [MCP市场工具] 美股数据获取失败: {e}")
                result_data.append(f"## 美股市场数据\n⚠️ 获取失败: {e}")

        # 计算执行时间
        execution_time = (datetime.now() - start_time).total_seconds()

        # 组合所有数据
        combined_result = f"""# {ticker} 市场数据分析

**股票类型**: {market_info['market_name']}
**货币**: {market_info['currency_name']} ({market_info['currency_symbol']})
**分析期间**: {start_date} 至 {end_date}
**执行时间**: {execution_time:.2f}秒

{chr(10).join(result_data)}

---
*数据来源: 根据股票类型自动选择最适合的数据源*
"""

        logger.info(f"📈 [MCP市场工具] 数据获取完成，总长度: {len(combined_result)}")
        return combined_result

    except Exception as e:
        error_msg = f"❌ 统一市场数据工具执行失败: {str(e)}"
        logger.error(f"[MCP市场工具] {error_msg}")
        return f"""# {ticker} 市场数据分析

⚠️ **错误**: {error_msg}

**建议**:
- 检查股票代码是否正确
- 检查日期格式是否为 YYYY-MM-DD
- 稍后重试或尝试其他工具
"""
