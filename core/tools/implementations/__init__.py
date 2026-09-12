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
from .fundamentals.valuation_excel_tool import generate_valuation_excel_tool
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

# 导入估值模型工具
from .fundamentals.valuation.dcf_valuation import get_dcf_valuation
from .fundamentals.valuation.wacc_calculator import get_wacc_calculation

# 导入风险评分工具
from .risk.altman_zscore import get_altman_zscore
from .risk.piotroski_fscore import get_piotroski_fscore
from .risk.beneish_mscore import get_beneish_mscore
from .risk.earnings_quality import get_earnings_quality_score

# 导入投资组合管理工具
from .portfolio.performance_metrics import (
    get_beta_calculation,
    get_sharpe_ratio,
    get_var_calculation,
)

# 导入技术分析工具
from .technical.candlestick_patterns import get_candlestick_patterns
from .technical.crossover_signals import get_crossover_signals
from .technical.support_resistance import get_support_resistance_levels
from .technical.chart_patterns import get_chart_patterns
from .technical.fibonacci_tools import get_fibonacci_retracement

# 导入 P1 新增工具
from .fundamentals.macro_tools import (
    get_macro_dashboard,
    get_yield_curve_analysis,
)
from .fundamentals.event_study import get_event_study
from .fundamentals.screening.multi_factor_screening import get_multi_factor_screening
from .fundamentals.valuation.comparable_valuation import get_comparable_company_valuation
from .risk.fraud_signals import get_financial_fraud_signals
from .portfolio.quant_tools import (
    get_efficient_frontier,
    get_monte_carlo_simulation,
    get_factor_attribution,
)

# A类-估值扩展工具
from .fundamentals.valuation.extended_valuation import (
    get_dcf_three_stage_valuation,
    get_ddm_valuation,
    get_residual_income_valuation,
    get_eva_valuation,
    get_fcff_fcfe_calculation,
    get_peg_valuation,
    get_graham_valuation,
    get_capm_cost_of_equity,
    get_growth_adjusted_valuation,
)

# A类-财务风险扩展工具
from .risk.extended_risk_models import (
    get_ohlson_oscore,
    get_receivables_quality,
    get_inventory_quality,
    get_liquidity_stress_test,
    get_debt_structure_analysis,
)

# A类-投资组合扩展工具
from .portfolio.extended_performance import (
    get_sortino_ratio,
    get_treynor_ratio,
    get_information_ratio,
    get_calmar_ratio,
    get_jensen_alpha,
    get_portfolio_stress_test,
    get_scenario_analysis,
    get_brinson_attribution,
    get_sector_attribution,
)

# A类-高级技术分析工具
from .technical.advanced_technical import (
    get_adx_trend_strength,
    get_macd_divergence,
    get_rsi_divergence,
    get_volume_price_divergence,
)
from .technical.volume_analysis import (
    get_vwap,
    get_obv_analysis,
    get_turnover_analysis,
    get_pivot_points,
    get_volume_profile,
    get_fibonacci_extension,
)

# A类-统计工具
from .fundamentals.statistical_tools import (
    get_correlation_matrix,
    get_cointegration_test,
    get_rolling_regression,
    get_normality_test,
    get_stationarity_test,
    get_garch_volatility,
)

# A类-筛选工具
from .fundamentals.screening.value_screening import (
    get_graham_screen,
    get_growth_stock_screen,
    get_dividend_stock_screen,
    get_turnaround_screen,
)

# B类-宏观周期工具
from .fundamentals.macro_cycle_tools import (
    get_economic_cycle_position,
    get_monetary_environment,
    get_sector_rotation_signals,
)

# B类-债券工具
from .fundamentals.bond_tools import (
    get_bond_yield_calculation,
    get_credit_spread_analysis,
    get_bond_duration_convexity,
)

# B类-增强工具
from .fundamentals.dividend_enhancement import (
    get_dividend_valuation_context,
    get_industry_valuation_distribution,
)
from .fundamentals.cashflow_enhancement import (
    get_cashflow_quality_deep,
    get_earnings_surprise_analysis,
)

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
    # 估值模型工具
    'get_dcf_valuation',
    'get_wacc_calculation',
    # 风险评分工具
    'get_altman_zscore',
    'get_piotroski_fscore',
    'get_beneish_mscore',
    'get_earnings_quality_score',
    # 投资组合管理工具
    'get_beta_calculation',
    'get_sharpe_ratio',
    'get_var_calculation',
    # 技术分析高级工具
    'get_candlestick_patterns',
    'get_crossover_signals',
    'get_support_resistance_levels',
    'get_chart_patterns',
    'get_fibonacci_retracement',
    # P1-宏观/事件/选股
    'get_macro_dashboard',
    'get_yield_curve_analysis',
    'get_event_study',
    'get_multi_factor_screening',
    # P1-估值/风险
    'get_comparable_company_valuation',
    'get_financial_fraud_signals',
    # P1-组合量化
    'get_efficient_frontier',
    'get_monte_carlo_simulation',
    'get_factor_attribution',
    # A类-估值扩展
    'get_dcf_three_stage_valuation',
    'get_ddm_valuation',
    'get_residual_income_valuation',
    'get_eva_valuation',
    'get_fcff_fcfe_calculation',
    'get_peg_valuation',
    'get_graham_valuation',
    'get_capm_cost_of_equity',
    'get_growth_adjusted_valuation',
    # A类-财务风险扩展
    'get_ohlson_oscore',
    'get_receivables_quality',
    'get_inventory_quality',
    'get_liquidity_stress_test',
    'get_debt_structure_analysis',
    # A类-组合扩展
    'get_sortino_ratio',
    'get_treynor_ratio',
    'get_information_ratio',
    'get_calmar_ratio',
    'get_jensen_alpha',
    'get_portfolio_stress_test',
    'get_scenario_analysis',
    'get_brinson_attribution',
    'get_sector_attribution',
    # A类-高级技术分析
    'get_adx_trend_strength',
    'get_macd_divergence',
    'get_rsi_divergence',
    'get_volume_price_divergence',
    'get_vwap',
    'get_obv_analysis',
    'get_turnover_analysis',
    'get_pivot_points',
    'get_volume_profile',
    'get_fibonacci_extension',
    # A类-统计
    'get_correlation_matrix',
    'get_cointegration_test',
    'get_rolling_regression',
    'get_normality_test',
    'get_stationarity_test',
    'get_garch_volatility',
    # A类-筛选
    'get_graham_screen',
    'get_growth_stock_screen',
    'get_dividend_stock_screen',
    'get_turnaround_screen',
    # B类-宏观周期
    'get_economic_cycle_position',
    'get_monetary_environment',
    'get_sector_rotation_signals',
    # B类-债券
    'get_bond_yield_calculation',
    'get_credit_spread_analysis',
    'get_bond_duration_convexity',
    # B类-增强
    'get_dividend_valuation_context',
    'get_industry_valuation_distribution',
    'get_cashflow_quality_deep',
    'get_earnings_surprise_analysis',
]

