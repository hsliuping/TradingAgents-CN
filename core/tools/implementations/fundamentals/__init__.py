"""基本面分析工具"""

from .stock_fundamentals import get_stock_fundamentals_unified
from .financial_tools import (
    get_income_analysis,
    get_balance_sheet_analysis,
    get_cashflow_analysis,
    get_dividend_data,
    get_main_business,
)
from .factor_bundle_tools import (
    get_fundamental_factor_snapshot_tool,
    get_growth_cashflow_factor_bundle_tool,
    get_quality_factor_bundle_tool,
    get_value_factor_bundle_tool,
)
from .standard_financial_tools import (
    get_cashflow_quality_trend_tool,
    get_historical_financial_annual_series_tool,
    get_historical_valuation_percentile_tool,
    get_profitability_stability_metrics_tool,
)
from .valuation_excel_tool import generate_valuation_excel_tool
from .bond_tools import (
    get_bond_yield_calculation,
    get_credit_spread_analysis,
    get_bond_duration_convexity,
)
from .option_tools import (
    get_black_scholes_price,
    get_implied_volatility,
    get_option_greeks,
    get_option_strategy_pnl,
)
from .management_assessment import (
    get_audit_opinion,
    get_disclosure_rating,
    get_equity_incentive,
    get_management_penalties,
)

__all__ = [
    'get_stock_fundamentals_unified',
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
    'generate_valuation_excel_tool',
    'get_bond_yield_calculation',
    'get_credit_spread_analysis',
    'get_bond_duration_convexity',
    'get_black_scholes_price',
    'get_implied_volatility',
    'get_option_greeks',
    'get_option_strategy_pnl',
    'get_audit_opinion',
    'get_disclosure_rating',
    'get_equity_incentive',
    'get_management_penalties',
]

