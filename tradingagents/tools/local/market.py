import logging
from typing import Annotated
try:
    from langchain_core.pydantic_v1 import BaseModel, Field
except ImportError:
    from pydantic import BaseModel, Field

from tradingagents.utils.logging_init import get_logger
from tradingagents.utils.tool_logging import log_tool_call

logger = get_logger("tools.local.market")

def create_unified_market_tool(toolkit):
    """创建统一市场数据工具函数"""
    
    class UnifiedMarketInput(BaseModel):
        ticker: str = Field(description="股票代码（支持A股、港股、美股）")
        start_date: str = Field(description="开始日期，格式：YYYY-MM-DD。注意：系统会自动扩展到配置的回溯天数（通常为365天），你只需要传递分析日期即可")
        end_date: str = Field(description="结束日期，格式：YYYY-MM-DD。通常与start_date相同，传递当前分析日期即可")

    @log_tool_call(tool_name="get_stock_market_data_unified", log_args=True)
    def get_stock_market_data_unified(
        ticker: str,
        start_date: str,
        end_date: str
    ) -> str:
        """
        统一的股票市场数据工具
        自动识别股票类型（A股、港股、美股）并调用相应的数据源
        """
        logger.info(f"📈 [统一市场工具] 分析股票: {ticker}")

        try:
            from tradingagents.utils.stock_utils import StockUtils
            
            # 自动识别股票类型
            market_info = StockUtils.get_market_info(ticker)
            is_china = market_info['is_china']
            is_hk = market_info['is_hk']
            is_us = market_info['is_us']

            logger.info(f"📈 [统一市场工具] 股票类型: {market_info['market_name']}")

            result_data = []

            if is_china:
                # 中国A股：使用统一接口（优先Tushare）
                logger.info(f"🇨🇳 [统一市场工具] 处理A股市场数据...")
                try:
                    from tradingagents.dataflows.interface import get_china_stock_data_unified
                    cn_data = get_china_stock_data_unified(ticker, start_date, end_date)
                    
                    # 🔍 调试：打印返回数据的前500字符
                    logger.info(f"🔍 [市场工具调试] A股数据返回长度: {len(cn_data)}")
                    logger.info(f"🔍 [市场工具调试] A股数据前500字符:\n{cn_data[:500]}")
                    
                    result_data.append(f"## A股市场数据\n{cn_data}")
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

    # 设置工具属性
    get_stock_market_data_unified.name = "get_stock_market_data_unified"
    get_stock_market_data_unified.description = """
统一股票市场数据工具 - 获取股票的历史价格、技术指标和市场表现。
自动识别股票类型（A股/港股/美股）并调用最佳数据源。
返回数据包括：K线数据、移动平均线、MACD、RSI、布林带等技术指标。
"""
    get_stock_market_data_unified.args_schema = UnifiedMarketInput
    
    return get_stock_market_data_unified
