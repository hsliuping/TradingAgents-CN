"""
MCP 工具模块

本模块包含所有转换为 MCP 格式的本地工具。
使用 FastMCP 的 @mcp.tool() 装饰器定义，与官方 MCP 工具接口一致。
"""

from .news import get_stock_news
from .market import get_stock_market_data
from .fundamentals import get_stock_fundamentals
from .sentiment import get_stock_sentiment
from .china import get_china_market_overview

__all__ = [
    "get_stock_news",
    "get_stock_market_data",
    "get_stock_fundamentals",
    "get_stock_sentiment",
    "get_china_market_overview",
]
