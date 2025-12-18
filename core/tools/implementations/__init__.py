"""
工具实现模块

所有工具按类别组织在子目录中
"""

# 导入所有工具以触发自动注册
from .market.stock_market_data import get_stock_market_data_unified
from .fundamentals.stock_fundamentals import get_stock_fundamentals_unified
from .news.stock_news import get_stock_news_unified
from .social.stock_sentiment import get_stock_sentiment_unified
from . import legacy_bridge

# 导入大盘/指数分析工具
from .market.index_market_tools import (
    get_index_data,
    get_market_breadth,
    get_market_environment,
    identify_market_cycle,
)

# 导入板块分析工具
from .market.sector_market_tools import (
    get_sector_data,
    get_fund_flow_data,
    get_peer_comparison,
    analyze_sector,
)

__all__ = [
    'get_stock_market_data_unified',
    'get_stock_fundamentals_unified',
    'get_stock_news_unified',
    'get_stock_sentiment_unified',
    # 大盘/指数分析工具
    'get_index_data',
    'get_market_breadth',
    'get_market_environment',
    'identify_market_cycle',
    # 板块分析工具
    'get_sector_data',
    'get_fund_flow_data',
    'get_peer_comparison',
    'analyze_sector',
]

