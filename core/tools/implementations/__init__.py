"""
工具实现模块

所有工具按类别组织在子目录中
"""

# 导入所有工具以触发自动注册
from .market.stock_market_data import get_stock_market_data_unified
from .fundamentals.stock_fundamentals import get_stock_fundamentals_unified
from .fundamentals.etf_fundamentals import get_etf_fundamentals
from .fundamentals.financial_tools import (
    get_income_analysis,
    get_balance_sheet_analysis,
    get_cashflow_analysis,
    get_dividend_data,
    get_main_business,
)
from .fundamentals.factor_bundle_tools import (
    get_fundamental_factor_snapshot_tool,
    get_growth_cashflow_factor_bundle_tool,
    get_quality_factor_bundle_tool,
    get_value_factor_bundle_tool,
)
from .fundamentals.standard_financial_tools import (
    get_cashflow_quality_trend_tool,
    get_historical_financial_annual_series_tool,
    get_historical_valuation_percentile_tool,
    get_profitability_stability_metrics_tool,
)
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

# 导入筹码分布分析工具
from .market.chip_distribution_tools import (
    get_chip_distribution,
    get_chip_distribution_akshare_tool,
    get_chip_distribution_tushare_tool,
)

# 导入全市场批量筛选工具
from .market.stock_screening_tool import screen_stocks_by_criteria
from .market.technical_factor_bundle_tool import get_technical_factor_bundle_tool

# 导入批量盈利稳定性验证工具
from .fundamentals.batch_profit_consistency import batch_check_profit_consistency

__all__ = [
    'get_stock_market_data_unified',
    'get_stock_fundamentals_unified',
    'get_stock_news_unified',
    'get_stock_sentiment_unified',
    # 专项财务分析工具
    'get_income_analysis',
    'get_balance_sheet_analysis',
    'get_cashflow_analysis',
    'get_dividend_data',
    'get_main_business',
    'get_value_factor_bundle_tool',
    'get_quality_factor_bundle_tool',
    'get_growth_cashflow_factor_bundle_tool',
    'get_fundamental_factor_snapshot_tool',
    'get_historical_financial_annual_series_tool',
    'get_profitability_stability_metrics_tool',
    'get_cashflow_quality_trend_tool',
    'get_historical_valuation_percentile_tool',
    'get_technical_factor_bundle_tool',
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
    # 筹码分布分析工具
    'get_chip_distribution',
    'get_chip_distribution_akshare_tool',
    'get_chip_distribution_tushare_tool',
    # 全市场批量筛选工具
    'screen_stocks_by_criteria',
    # 批量盈利稳定性验证工具
    'batch_check_profit_consistency',
]

