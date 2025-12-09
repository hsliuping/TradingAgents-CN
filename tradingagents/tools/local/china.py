import logging
from typing import Annotated
try:
    from langchain_core.pydantic_v1 import BaseModel, Field
except ImportError:
    from pydantic import BaseModel, Field

from tradingagents.utils.logging_init import get_logger
from tradingagents.utils.tool_logging import log_tool_call

logger = get_logger("tools.local.china")

def create_china_market_overview_tool(toolkit):
    """创建中国市场概览工具"""
    
    class ChinaMarketOverviewInput(BaseModel):
        curr_date: str = Field(description="当前日期，格式 yyyy-mm-dd")

    @log_tool_call(tool_name="get_china_market_overview", log_args=True)
    def get_china_market_overview(
        curr_date: str
    ) -> str:
        """
        获取中国股市整体概览，包括主要指数的实时行情。
        涵盖上证指数(000001.SH)、深证成指(399001.SZ)、创业板指(399006.SZ)等。
        """
        try:
            from tradingagents.dataflows.interface import get_china_stock_data_unified
            
            # 定义主要指数
            indices = {
                "上证指数": "000001.SH",
                "深证成指": "399001.SZ",
                "创业板指": "399006.SZ",
                "科创50": "000688.SH"
            }
            
            report = [f"# 中国股市概览 - {curr_date}\n"]
            
            for name, code in indices.items():
                try:
                    # 获取最近几天的行情以展示趋势
                    data = get_china_stock_data_unified(code, curr_date, curr_date)
                    # 简化输出，只保留关键信息
                    if "获取失败" not in data:
                        report.append(f"## {name} ({code})")
                        report.append(data)
                    else:
                        report.append(f"## {name}: 暂无数据")
                except Exception as e:
                    report.append(f"## {name}: 获取失败 ({e})")
            
            report.append(f"\n数据来源: Tushare/AKShare专业数据源")
            report.append(f"更新时间: {curr_date}")
            
            return "\n".join(report)

        except Exception as e:
            return f"中国市场概览获取失败: {str(e)}。请尝试使用个股查询功能。"

    get_china_market_overview.name = "get_china_market_overview"
    get_china_market_overview.description = "获取中国股市整体概览，包括主要指数的实时行情。"
    get_china_market_overview.args_schema = ChinaMarketOverviewInput
    
    return get_china_market_overview


def create_yfinance_tool(toolkit):
    """创建Yahoo Finance数据工具"""
    
    class YFinanceInput(BaseModel):
        symbol: str = Field(description="股票代码/Ticker")
        start_date: str = Field(description="开始日期 yyyy-mm-dd")
        end_date: str = Field(description="结束日期 yyyy-mm-dd")

    @log_tool_call(tool_name="get_YFin_data", log_args=True)
    def get_YFin_data(
        symbol: str,
        start_date: str,
        end_date: str
    ) -> str:
        """
        通过Yahoo Finance获取股票价格数据。
        """
        try:
            from tradingagents.dataflows.interface import get_YFin_data
            result_data = get_YFin_data(symbol, start_date, end_date)
            return result_data
        except Exception as e:
            return f"Yahoo Finance数据获取失败: {str(e)}"

    get_YFin_data.name = "get_YFin_data"
    get_YFin_data.description = "通过Yahoo Finance获取股票价格数据。"
    get_YFin_data.args_schema = YFinanceInput
    
    return get_YFin_data
