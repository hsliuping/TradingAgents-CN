"""
MCP 基本面分析工具

使用 FastMCP 的 @mcp.tool() 装饰器定义统一基本面分析工具。
保留现有的分析深度配置支持，支持 A股、港股、美股。
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# 全局 toolkit 配置
_toolkit_config: dict = {}


def set_toolkit_config(config: dict):
    """设置工具配置"""
    global _toolkit_config
    _toolkit_config = config or {}


def get_stock_fundamentals(
    ticker: str,
    curr_date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> str:
    """
    统一股票基本面分析工具 - 获取股票的财务数据和估值指标。
    
    自动识别股票类型（A股/港股/美股）并调用最佳数据源。
    返回数据包括：市盈率(PE)、市净率(PB)、净资产收益率(ROE)、营收增长、利润增长等核心财务指标。
    
    Args:
        ticker: 股票代码，支持多种格式：
            - A股：如 '600519', '000001', '300750'
            - 港股：如 '0700.HK', '09988'
            - 美股：如 'AAPL', 'TSLA', 'NVDA'
        curr_date: 当前日期，格式：YYYY-MM-DD（可选，默认为今天）
        start_date: 开始日期，格式：YYYY-MM-DD（可选）
        end_date: 结束日期，格式：YYYY-MM-DD（可选）
    
    Returns:
        格式化的基本面分析数据，包含财务指标和估值数据
    """
    logger.info(f"📊 [MCP基本面工具] 分析股票: {ticker}")
    start_time = datetime.now()

    # 设置默认日期
    if not curr_date:
        curr_date = datetime.now().strftime('%Y-%m-%d')
    
    if not start_date:
        start_date = (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d')
    
    if not end_date:
        end_date = curr_date

    # 分级分析已废弃，统一使用标准深度
    data_depth = "standard"
    logger.info(f"🔧 [MCP基本面工具] 已取消分级分析，使用标准数据深度")

    try:
        from tradingagents.utils.stock_utils import StockUtils

        # 自动识别股票类型
        market_info = StockUtils.get_market_info(ticker)
        is_china = market_info['is_china']
        is_hk = market_info['is_hk']
        is_us = market_info['is_us']

        logger.info(f"📊 [MCP基本面工具] 股票类型: {market_info['market_name']}")

        result_data = []

        if is_china:
            # 中国A股
            logger.info(f"🇨🇳 [MCP基本面工具] 处理A股数据...")
            
            # 获取最新股价信息
            try:
                recent_end_date = curr_date
                recent_start_date = (datetime.strptime(curr_date, '%Y-%m-%d') - timedelta(days=2)).strftime('%Y-%m-%d')

                from tradingagents.dataflows.interface import get_china_stock_data_unified
                current_price_data = get_china_stock_data_unified(ticker, recent_start_date, recent_end_date)
                result_data.append(f"## A股当前价格信息\n{current_price_data}")
            except Exception as e:
                logger.error(f"❌ [MCP基本面工具] A股价格数据获取失败: {e}")
                result_data.append(f"## A股当前价格信息\n⚠️ 获取失败: {e}")
                current_price_data = ""

            # 获取基本面财务数据
            try:
                from tradingagents.dataflows.providers.china.optimized import OptimizedChinaDataProvider
                analyzer = OptimizedChinaDataProvider()
                
                # 根据数据深度选择分析模块
                analysis_modules = data_depth
                
                # 尝试调用报告生成方法
                if hasattr(analyzer, "generate_fundamentals_report"):
                    fundamentals_data = analyzer.generate_fundamentals_report(ticker, current_price_data, analysis_modules)
                elif hasattr(analyzer, "_generate_fundamentals_report"):
                    fundamentals_data = analyzer._generate_fundamentals_report(ticker, current_price_data, analysis_modules)
                else:
                    fundamentals_data = "基本面报告生成方法不可用"
                
                result_data.append(f"## A股基本面财务数据\n{fundamentals_data}")
            except Exception as e:
                logger.error(f"❌ [MCP基本面工具] A股基本面数据获取失败: {e}")
                result_data.append(f"## A股基本面财务数据\n⚠️ 获取失败: {e}")

        elif is_hk:
            # 港股
            logger.info(f"🇭🇰 [MCP基本面工具] 处理港股数据...")
            
            allow_full_fetch = data_depth in ["full", "comprehensive"]
            
            if allow_full_fetch:
                try:
                    from tradingagents.dataflows.interface import get_hk_stock_data_unified
                    hk_data = get_hk_stock_data_unified(ticker, start_date, end_date)
                    
                    if hk_data and len(hk_data) > 100 and "❌" not in hk_data:
                        result_data.append(f"## 港股数据\n{hk_data}")
                    else:
                        raise ValueError("港股数据质量不佳")
                except Exception as e:
                    logger.warning(f"⚠️ [MCP基本面工具] 港股主要数据源失败: {e}")
                    # 使用备用方案
                    try:
                        from tradingagents.dataflows.interface import get_hk_stock_info_unified
                        hk_info = get_hk_stock_info_unified(ticker)
                        
                        basic_info = f"""## 港股基础信息

**股票代码**: {ticker}
**股票名称**: {hk_info.get('name', f'港股{ticker}')}
**交易货币**: 港币 (HK$)
**交易所**: 香港交易所 (HKG)

⚠️ 注意：详细的财务数据暂时无法获取，建议稍后重试。
"""
                        result_data.append(basic_info)
                    except Exception as e2:
                        result_data.append(f"## 港股信息\n⚠️ 数据获取失败: {e2}")
            else:
                result_data.append(f"## 港股基础信息\n轻量模式：跳过详细数据抓取")

        else:
            # 美股
            logger.info(f"🇺🇸 [MCP基本面工具] 处理美股数据...")
            
            try:
                from tradingagents.dataflows.interface import get_fundamentals_openai
                us_data = get_fundamentals_openai(ticker, curr_date)
                result_data.append(f"## 美股基本面数据\n{us_data}")
            except Exception as e:
                logger.error(f"❌ [MCP基本面工具] 美股数据获取失败: {e}")
                result_data.append(f"## 美股基本面数据\n⚠️ 获取失败: {e}")

        # 计算执行时间
        execution_time = (datetime.now() - start_time).total_seconds()

        # 组合所有数据
        combined_result = f"""# {ticker} 基本面分析数据

**股票类型**: {market_info['market_name']}
**货币**: {market_info['currency_name']} ({market_info['currency_symbol']})
**分析日期**: {curr_date}
**数据深度级别**: {data_depth}
**执行时间**: {execution_time:.2f}秒

{chr(10).join(result_data)}

---
*数据来源: 根据股票类型自动选择最适合的数据源*
"""
        
        logger.info(f"📊 [MCP基本面工具] 数据获取完成，总长度: {len(combined_result)}")
        return combined_result

    except Exception as e:
        error_msg = f"❌ 统一基本面分析工具执行失败: {str(e)}"
        logger.error(f"[MCP基本面工具] {error_msg}")
        return f"""# {ticker} 基本面分析数据

⚠️ **错误**: {error_msg}

**建议**:
- 检查股票代码是否正确
- 稍后重试或尝试其他工具
"""
