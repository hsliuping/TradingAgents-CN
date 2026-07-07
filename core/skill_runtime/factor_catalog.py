"""Skill 运行时因子目录。

把当前仓库内“已有数据 + 已有 helper + 已有指标实现”能够稳定支撑的常用因子
整理成结构化目录，供以下场景复用：

1. 手工实现 Skill 时快速选型
2. 生成式 Skill 的白名单约束
3. 工作流/Agent 需要能力缺口分析时，优先复用现成因子
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import Dict, List, Literal, Optional

from .factor_schema import (
    COND_ACCOUNTS_RECEIV_NON_ZERO,
    COND_ALL_REQUIRED_SIGNAL_INPUTS_AVAILABLE,
    COND_ASSET_QUALITY_PREVIOUS_NON_ZERO,
    COND_BASE_PERIOD_AVAILABLE,
    COND_BASE_VALUE_POSITIVE,
    COND_COMPARISON_PERIOD_AVAILABLE,
    COND_CURRENT_VALUE_POSITIVE,
    COND_DEPRECIATION_PLUS_FIXED_ASSETS_CURRENT_NON_ZERO,
    COND_DEPRECIATION_PLUS_FIXED_ASSETS_PREVIOUS_NON_ZERO,
    COND_GROSS_MARGIN_CURRENT_NON_ZERO,
    COND_INDUSTRY_PEER_SAMPLE_COUNT_GE_5,
    COND_INTEREST_EXPENSE_POSITIVE,
    COND_INVENTORIES_NON_ZERO,
    COND_INVESTED_CAPITAL_POSITIVE,
    COND_MARKET_CAP_NON_ZERO,
    COND_NET_PROFIT_NON_ZERO,
    COND_NET_PROFIT_YOY_NON_ZERO,
    COND_NET_PROFIT_YOY_POSITIVE,
    COND_PREVIOUS_PERIOD_AVAILABLE,
    COND_PRIOR_PERIOD_METRIC_NON_ZERO,
    COND_REVENUE_BASE_NON_ZERO,
    COND_SALES_CURRENT_NON_ZERO,
    COND_SALES_PREVIOUS_NON_ZERO,
    COND_SGA_PREVIOUS_NON_ZERO,
    COND_TECHNICAL_LOOKBACK_WINDOW_AVAILABLE,
    COND_TOTAL_ASSETS_CURRENT_NON_ZERO,
    COND_TOTAL_ASSETS_NON_ZERO,
    COND_TOTAL_ASSETS_PREVIOUS_NON_ZERO,
    COND_TOTAL_EQUITY_NON_ZERO,
    COND_TOTAL_LIAB_NON_ZERO,
    COND_TOTAL_LIAB_PREVIOUS_NON_ZERO,
    P0_FACTOR_FIELD_SCHEMA,
    P0_SOURCE_PRIORITY_BY_FIELD,
    TECHNICAL_FACTOR_FIELD_SCHEMA,
    WARN_DIVIDEND_YIELD_FALLBACK_TO_FINANCIAL_FIELD,
    WARN_FCF_CONSERVATIVE_PROXY_USED,
    WARN_INDUSTRY_PEER_SAMPLE_COUNT_LT_5,
    WARN_INTEREST_COVERAGE_FALLBACK_TO_RAW_INTEREST_EXPENSE,
    WARN_INVENTORY_TURNOVER_COST_PROXY_USED,
    WARN_NET_CASH_POSITION_PROXY_TOTAL_NCL_USED,
    WARN_NET_PROFIT_TTM_FALLBACK_TO_NET_PROFIT_OR_NET_INCOME,
    WARN_PB_FALLBACK_TO_PB_MRQ,
    WARN_PB_MRQ_ESTIMATED_FROM_MARKET_CAP_AND_EQUITY,
    WARN_PE_TTM_FALLBACK_TO_PE,
    WARN_PS_TTM_FALLBACK_TO_PS,
    WARN_ROIC_MONEY_CAP_MISSING_AS_ZERO,
    list_bundle_fields,
)


SCHEMA_TAG_BY_CONTRACT_CATEGORY = {
    "fallback_chain": "fallback_chain",
    "denominator_guards": "denominator_guard",
    "unit_conversions": "unit_conversion",
    "conservative_proxies": "conservative_proxy",
    "availability_constraints": "availability_guard",
}


FactorCategory = Literal[
    "valuation",
    "quality",
    "growth",
    "cashflow",
    "momentum",
    "technical",
    "trading",
    "risk",
]

ImplementationLevel = Literal[
    "ready",
    "derived",
    "time_series",
    "cautious",
]


@dataclass(frozen=True)
class FactorDefinition:
    factor_id: str
    display_name: str
    category: FactorCategory
    description: str
    implementation_level: ImplementationLevel
    primary_sources: List[str] = field(default_factory=list)
    helper_functions: List[str] = field(default_factory=list)
    required_fields: List[str] = field(default_factory=list)
    formula: Optional[str] = None
    fallback_rules: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class RuntimeSemanticContract:
    direct_fields: List[str] = field(default_factory=list)
    source_priority: List[str] = field(default_factory=list)
    fallback_chain: List[str] = field(default_factory=list)
    denominator_guards: List[str] = field(default_factory=list)
    unit_conversions: List[str] = field(default_factory=list)
    conservative_proxies: List[str] = field(default_factory=list)
    availability_constraints: List[str] = field(default_factory=list)
    tax_estimation_strategy: str | None = None
    period_selection_strategy: str | None = None
    minimum_input_groups: List[List[str]] = field(default_factory=list)
    minimum_computable_conditions: List[str] = field(default_factory=list)
    warning_conditions: List[str] = field(default_factory=list)
    warning_categories: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def _missing_text_fragments(notes: List[str], expected_fragments: List[str]) -> List[str]:
    combined = "\n".join(notes)
    return [fragment for fragment in expected_fragments if fragment not in combined]


COMMON_FACTOR_CATALOG: Dict[str, FactorDefinition] = {
    "pe": FactorDefinition(
        factor_id="pe",
        display_name="市盈率",
        category="valuation",
        description="静态市盈率，适合做横向估值比较。",
        implementation_level="ready",
        primary_sources=["stock_basic_info", "market_quotes"],
        helper_functions=["get_stock_basic_info", "get_market_quotes"],
        required_fields=["pe"],
        fallback_rules=["若 basic_info.pe 缺失，可尝试 market_quotes.pe"],
    ),
    "pe_ttm": FactorDefinition(
        factor_id="pe_ttm",
        display_name="滚动市盈率",
        category="valuation",
        description="优先使用的 PE 估值主字段。",
        implementation_level="ready",
        primary_sources=["stock_basic_info", "market_quotes"],
        helper_functions=["get_stock_valuation_context", "get_stock_basic_info"],
        required_fields=["pe_ttm"],
        fallback_rules=["缺失时回退到 pe"],
    ),
    "pb": FactorDefinition(
        factor_id="pb",
        display_name="市净率",
        category="valuation",
        description="适合金融、周期、重资产行业的估值比较。",
        implementation_level="ready",
        primary_sources=["stock_basic_info"],
        helper_functions=["get_stock_valuation_context", "get_stock_basic_info"],
        required_fields=["pb"],
        fallback_rules=["缺失时回退到 pb_mrq"],
    ),
    "pb_mrq": FactorDefinition(
        factor_id="pb_mrq",
        display_name="最新市净率",
        category="valuation",
        description="最新口径 PB，可作为 PB 的回退字段。",
        implementation_level="ready",
        primary_sources=["stock_basic_info", "stock_financial_periods", "market_quotes"],
        helper_functions=["get_stock_basic_info", "get_stock_financial_periods", "get_market_quotes"],
        required_fields=["pb_mrq|total_mv", "total_equity"],
        fallback_rules=["若 basic_info.pb_mrq 缺失，则回退为 total_mv / total_equity 的最新期保守估算。"],
        warnings=["当走 total_mv / total_equity 回补时，属于最新期保守估算口径。"],
    ),
    "ps_ttm": FactorDefinition(
        factor_id="ps_ttm",
        display_name="滚动市销率",
        category="valuation",
        description="适合利润不稳定但营收可比的公司。",
        implementation_level="ready",
        primary_sources=["stock_basic_info"],
        helper_functions=["get_stock_valuation_context", "get_stock_basic_info"],
        required_fields=["ps_ttm"],
        fallback_rules=["缺失时回退到 ps"],
    ),
    "dividend_yield": FactorDefinition(
        factor_id="dividend_yield",
        display_name="股息率",
        category="valuation",
        description="适合高分红、防御型资产筛选。",
        implementation_level="ready",
        primary_sources=["stock_financial_periods"],
        helper_functions=["get_stock_financial_periods"],
        required_fields=["dividend_yield|financial_indicators.dividend_yield"],
        fallback_rules=["优先使用 basic_info.dividend_yield，缺失时回退到最新财务期 financial_indicators.dividend_yield 或 period 顶层 dividend_yield。"],
    ),
    "peg": FactorDefinition(
        factor_id="peg",
        display_name="PEG",
        category="valuation",
        description="PE TTM 与净利润同比增速的比值。",
        implementation_level="derived",
        primary_sources=["stock_financial_periods", "stock_basic_info", "market_quotes"],
        helper_functions=["get_stock_financial_periods", "get_stock_basic_info", "get_market_quotes"],
        required_fields=["pe_ttm|pe", "net_profit_yoy"],
        formula="pe_ttm / net_profit_yoy",
        fallback_rules=["pe_ttm 缺失时回退到 pe。"],
        warnings=["仅在净利润同比为正且非 0 时计算，其他情况返回空值。"],
    ),
    "industry_pe_median": FactorDefinition(
        factor_id="industry_pe_median",
        display_name="行业 PE 中位数",
        category="valuation",
        description="用于横向行业比较的基准估值。",
        implementation_level="derived",
        primary_sources=["stock_basic_info"],
        helper_functions=["summarize_industry_valuation", "get_stock_basic_info"],
        required_fields=["industry", "pe_ttm|pe"],
        formula="summarize_industry_valuation(industry, metric='pe')['median']",
        warnings=["行业样本数建议 >= 5，过小样本只做参考"],
    ),
    "industry_pb_median": FactorDefinition(
        factor_id="industry_pb_median",
        display_name="行业 PB 中位数",
        category="valuation",
        description="用于重资产行业的横向比较。",
        implementation_level="derived",
        primary_sources=["stock_basic_info"],
        helper_functions=["summarize_industry_valuation", "get_stock_basic_info"],
        required_fields=["industry", "pb|pb_mrq"],
        formula="summarize_industry_valuation(industry, metric='pb')['median']",
    ),
    "roe": FactorDefinition(
        factor_id="roe",
        display_name="净资产收益率",
        category="quality",
        description="核心盈利质量指标。",
        implementation_level="ready",
        primary_sources=["stock_financial_periods"],
        helper_functions=["get_stock_financial_periods"],
        required_fields=["roe"],
    ),
    "roa": FactorDefinition(
        factor_id="roa",
        display_name="总资产收益率",
        category="quality",
        description="衡量资产效率。",
        implementation_level="ready",
        primary_sources=["stock_financial_periods"],
        helper_functions=["get_stock_financial_periods"],
        required_fields=["roa"],
    ),
    "gross_margin": FactorDefinition(
        factor_id="gross_margin",
        display_name="毛利率",
        category="quality",
        description="衡量产品/业务议价能力。",
        implementation_level="ready",
        primary_sources=["stock_financial_periods"],
        helper_functions=["get_stock_financial_periods"],
        required_fields=["gross_margin"],
    ),
    "netprofit_margin": FactorDefinition(
        factor_id="netprofit_margin",
        display_name="净利率",
        category="quality",
        description="衡量收入转利润的能力。",
        implementation_level="ready",
        primary_sources=["stock_financial_periods"],
        helper_functions=["get_stock_financial_periods"],
        required_fields=["netprofit_margin"],
    ),
    "debt_to_assets": FactorDefinition(
        factor_id="debt_to_assets",
        display_name="资产负债率",
        category="risk",
        description="财务杠杆与偿债压力指标。",
        implementation_level="ready",
        primary_sources=["stock_financial_periods"],
        helper_functions=["get_stock_financial_periods"],
        required_fields=["debt_to_assets"],
    ),
    "assets_to_eqt": FactorDefinition(
        factor_id="assets_to_eqt",
        display_name="权益乘数",
        category="risk",
        description="总资产相对股东权益的杠杆倍数。",
        implementation_level="ready",
        primary_sources=["stock_financial_periods"],
        helper_functions=["get_stock_financial_periods"],
        required_fields=["assets_to_eqt"],
    ),
    "current_ratio": FactorDefinition(
        factor_id="current_ratio",
        display_name="流动比率",
        category="risk",
        description="短期偿债能力指标。",
        implementation_level="ready",
        primary_sources=["stock_financial_periods"],
        helper_functions=["get_stock_financial_periods"],
        required_fields=["current_ratio"],
    ),
    "quick_ratio": FactorDefinition(
        factor_id="quick_ratio",
        display_name="速动比率",
        category="risk",
        description="剔除存货后的短期偿债能力。",
        implementation_level="ready",
        primary_sources=["stock_financial_periods"],
        helper_functions=["get_stock_financial_periods"],
        required_fields=["quick_ratio"],
    ),
    "cash_ratio": FactorDefinition(
        factor_id="cash_ratio",
        display_name="现金比率",
        category="risk",
        description="最保守的短期偿债能力。",
        implementation_level="ready",
        primary_sources=["stock_financial_periods"],
        helper_functions=["get_stock_financial_periods"],
        required_fields=["cash_ratio"],
    ),
    "net_working_capital": FactorDefinition(
        factor_id="net_working_capital",
        display_name="净营运资本",
        category="cashflow",
        description="流动资产减流动负债，衡量营运缓冲。",
        implementation_level="derived",
        primary_sources=["stock_financial_periods"],
        helper_functions=["get_stock_financial_periods"],
        required_fields=["total_cur_assets", "total_cur_liab"],
        formula="total_cur_assets - total_cur_liab",
    ),
    "revenue_ttm": FactorDefinition(
        factor_id="revenue_ttm",
        display_name="滚动营收",
        category="growth",
        description="适合作为成长规模基线。",
        implementation_level="ready",
        primary_sources=["stock_financial_periods"],
        helper_functions=["get_stock_financial_periods"],
        required_fields=["revenue_ttm"],
    ),
    "net_profit_ttm": FactorDefinition(
        factor_id="net_profit_ttm",
        display_name="滚动净利润",
        category="growth",
        description="成长股利润规模基线。",
        implementation_level="ready",
        primary_sources=["stock_financial_periods"],
        helper_functions=["get_stock_financial_periods"],
        required_fields=["net_profit_ttm|net_profit|net_income"],
        fallback_rules=["优先使用 net_profit_ttm，缺失时回退到 net_profit 或 net_income。"],
    ),
    "piotroski_f_score": FactorDefinition(
        factor_id="piotroski_f_score",
        display_name="Piotroski F-Score",
        category="quality",
        description="基于近两期财务信号的 9 分制质量评分。",
        implementation_level="cautious",
        primary_sources=["stock_financial_periods"],
        helper_functions=["get_stock_financial_periods"],
        required_fields=["roa", "n_cashflow_act", "current_ratio", "gross_margin", "asset_turnover"],
        warnings=["依赖近两期可比财务记录；缺少对比期或关键字段时应视为 cautious 输出。"],
    ),
    "altman_z_score": FactorDefinition(
        factor_id="altman_z_score",
        display_name="Altman Z-Score",
        category="risk",
        description="财务困境风险评分。",
        implementation_level="cautious",
        primary_sources=["stock_financial_periods", "stock_basic_info", "market_quotes"],
        helper_functions=["get_stock_financial_periods", "get_stock_basic_info", "get_market_quotes"],
        required_fields=["total_assets", "total_liab", "total_cur_assets", "total_cur_liab", "ebit", "revenue"],
        warnings=["依赖留存收益、EBIT 与市值口径，缺少关键分量或分母异常时应返回空值并附诊断。"],
    ),
    "beneish_m_score": FactorDefinition(
        factor_id="beneish_m_score",
        display_name="Beneish M-Score",
        category="risk",
        description="盈余操纵风险识别评分。",
        implementation_level="cautious",
        primary_sources=["stock_financial_periods"],
        helper_functions=["get_stock_financial_periods"],
        required_fields=["revenue", "accounts_receiv", "oper_cost", "total_assets", "total_cur_assets", "fix_assets", "n_cashflow_act"],
        warnings=["强依赖近两期原始折旧摊销和费用字段，当前真实覆盖率可能受 raw_data 完整性影响。"],
    ),
    "n_cashflow_act": FactorDefinition(
        factor_id="n_cashflow_act",
        display_name="经营现金流净额",
        category="cashflow",
        description="现金流质量核心指标。",
        implementation_level="ready",
        primary_sources=["stock_financial_periods"],
        helper_functions=["get_stock_financial_periods"],
        required_fields=["n_cashflow_act"],
    ),
    "revenue_yoy": FactorDefinition(
        factor_id="revenue_yoy",
        display_name="营收同比",
        category="growth",
        description="最新报告期相对上年同季的营收同比增速。",
        implementation_level="derived",
        primary_sources=["stock_financial_periods"],
        helper_functions=["get_stock_financial_periods"],
        required_fields=["revenue|oper_rev", "上年同季报告期"],
        formula="(本期营收 - 上年同季营收) / 上年同季营收",
        warnings=["缺少上年同季报告期或基期为 0 时返回空值。"],
    ),
    "net_profit_yoy": FactorDefinition(
        factor_id="net_profit_yoy",
        display_name="净利润同比",
        category="growth",
        description="最新报告期相对上年同季的净利润同比增速。",
        implementation_level="derived",
        primary_sources=["stock_financial_periods"],
        helper_functions=["get_stock_financial_periods"],
        required_fields=["net_profit|net_income", "上年同季报告期"],
        formula="(本期净利润 - 上年同季净利润) / 上年同季净利润",
        warnings=["缺少上年同季报告期或基期为 0 时返回空值。"],
    ),
    "oper_profit_yoy": FactorDefinition(
        factor_id="oper_profit_yoy",
        display_name="营业利润同比",
        category="growth",
        description="最新报告期相对上年同季的营业利润同比增速。",
        implementation_level="derived",
        primary_sources=["stock_financial_periods"],
        helper_functions=["get_stock_financial_periods"],
        required_fields=["oper_profit|operating_profit|ebit", "上年同季报告期"],
        formula="(本期营业利润 - 上年同季营业利润) / 上年同季营业利润",
        warnings=["缺少上年同季报告期或基期为 0 时返回空值。"],
    ),
    "revenue_cagr_3y": FactorDefinition(
        factor_id="revenue_cagr_3y",
        display_name="营收三年复合增速",
        category="growth",
        description="同季三年前对比的三年营收 CAGR。",
        implementation_level="derived",
        primary_sources=["stock_financial_periods"],
        helper_functions=["get_stock_financial_periods"],
        required_fields=["revenue_ttm|revenue|oper_rev", "同季三年前报告期"],
        formula="(营收_t / 营收_t-3)^(1/3) - 1",
        warnings=["缺少同季三年前报告期、基期非正或当前值非正时返回空值。"],
    ),
    "profit_cagr_3y": FactorDefinition(
        factor_id="profit_cagr_3y",
        display_name="净利润三年复合增速",
        category="growth",
        description="同季三年前对比的三年净利润 CAGR。",
        implementation_level="derived",
        primary_sources=["stock_financial_periods"],
        helper_functions=["get_stock_financial_periods"],
        required_fields=["net_profit_ttm|net_profit|net_income", "同季三年前报告期"],
        formula="(净利润_t / 净利润_t-3)^(1/3) - 1",
        warnings=["缺少同季三年前报告期、基期非正或当前值非正时返回空值。"],
    ),
    "roic": FactorDefinition(
        factor_id="roic",
        display_name="投入资本回报率",
        category="quality",
        description="营业利润近似 EBIT 的保守代理口径 ROIC。",
        implementation_level="derived",
        primary_sources=["stock_financial_periods"],
        helper_functions=["get_stock_financial_periods"],
        required_fields=["ebit|oper_profit|operating_profit", "total_equity", "total_liab"],
        formula="NOPAT / (total_equity + total_liab - money_cap)",
        fallback_rules=["税率优先按 total_profit 与 net_profit 估算，缺失时使用 25% 默认税率。", "money_cap 缺失时按 0 处理。"],
        warnings=["当前实现使用最新期口径和保守代理，不是严格的平均投入资本 ROIC。"],
    ),
    "cash_conversion": FactorDefinition(
        factor_id="cash_conversion",
        display_name="利润现金转换率",
        category="cashflow",
        description="经营现金流相对净利润的转换能力。",
        implementation_level="derived",
        primary_sources=["stock_financial_periods"],
        helper_functions=["get_stock_financial_periods"],
        required_fields=["n_cashflow_act", "net_profit|net_income"],
        formula="n_cashflow_act / net_profit",
        warnings=["净利润缺失或为 0 时返回空值。"],
    ),
    "accrual_ratio": FactorDefinition(
        factor_id="accrual_ratio",
        display_name="应计利润比率",
        category="quality",
        description="净利润与经营现金流偏离度。",
        implementation_level="derived",
        primary_sources=["stock_financial_periods"],
        helper_functions=["get_stock_financial_periods"],
        required_fields=["net_profit|net_income", "n_cashflow_act", "total_assets"],
        formula="(net_profit - n_cashflow_act) / total_assets",
        warnings=["当前以最新总资产为分母并输出百分比，不是平均总资产口径。"],
    ),
    "asset_turnover": FactorDefinition(
        factor_id="asset_turnover",
        display_name="资产周转率",
        category="quality",
        description="营业收入相对总资产的周转效率。",
        implementation_level="derived",
        primary_sources=["stock_financial_periods"],
        helper_functions=["get_stock_financial_periods"],
        required_fields=["revenue_ttm|revenue|oper_rev", "total_assets"],
        formula="revenue_base / total_assets",
        warnings=["当前以最新总资产为分母，不是平均总资产口径。"],
    ),
    "gross_profit_to_assets": FactorDefinition(
        factor_id="gross_profit_to_assets",
        display_name="毛利资产比",
        category="quality",
        description="毛利润相对总资产的效率指标。",
        implementation_level="derived",
        primary_sources=["stock_financial_periods"],
        helper_functions=["get_stock_financial_periods"],
        required_fields=["revenue_ttm|revenue|oper_rev", "gross_margin", "total_assets"],
        formula="revenue_base * gross_margin / total_assets",
        warnings=["当前以最新总资产为分母并输出百分比，不是平均总资产口径。"],
    ),
    "interest_coverage": FactorDefinition(
        factor_id="interest_coverage",
        display_name="利息保障倍数",
        category="risk",
        description="EBIT 对利息费用的覆盖能力。",
        implementation_level="derived",
        primary_sources=["stock_financial_periods"],
        helper_functions=["get_stock_financial_periods"],
        required_fields=["ebit|oper_profit|operating_profit", "fin_exp|raw_data.income_statement.int_exp"],
        formula="ebit / interest_expense",
        fallback_rules=["优先使用 ebit / fin_exp。", "当 fin_exp <= 0 时，回退到 raw income 中的 int_exp 或 fin_exp_int_exp。"],
        warnings=["当利息费用缺失、非正或无法从 raw_data 回补时返回空值。"],
    ),
    "inventory_turnover": FactorDefinition(
        factor_id="inventory_turnover",
        display_name="存货周转率",
        category="quality",
        description="营业成本相对存货余额的周转效率。",
        implementation_level="derived",
        primary_sources=["stock_financial_periods"],
        helper_functions=["get_stock_financial_periods"],
        required_fields=["oper_cost|revenue_ttm|revenue|oper_rev", "inventories"],
        formula="cost_base / inventories",
        fallback_rules=["oper_cost 缺失时，允许用 revenue_base 与 gross_margin 反推成本代理。"],
        warnings=["当前使用最新存货余额而不是平均存货余额。"],
    ),
    "receivable_turnover": FactorDefinition(
        factor_id="receivable_turnover",
        display_name="应收账款周转率",
        category="quality",
        description="营业收入相对最新应收账款余额的周转效率。",
        implementation_level="derived",
        primary_sources=["stock_financial_periods"],
        helper_functions=["get_stock_financial_periods"],
        required_fields=["revenue_ttm|revenue|oper_rev", "accounts_receiv"],
        formula="revenue_base / accounts_receiv",
        warnings=["当前使用最新应收账款余额而不是平均应收余额。"],
    ),
    "net_cash_position": FactorDefinition(
        factor_id="net_cash_position",
        display_name="净现金头寸",
        category="risk",
        description="货币资金相对债务代理和总资产的保守净现金指标。",
        implementation_level="derived",
        primary_sources=["stock_financial_periods"],
        helper_functions=["get_stock_financial_periods"],
        required_fields=["money_cap", "total_assets", "total_ncl|total_liab|total_cur_liab"],
        formula="(money_cap - debt_proxy) / total_assets",
        fallback_rules=["优先使用 total_ncl。", "缺少 total_ncl 时，回退为 total_liab - total_cur_liab。"],
        warnings=["当前输出为保守代理口径百分比。"],
    ),
    "fcf": FactorDefinition(
        factor_id="fcf",
        display_name="自由现金流",
        category="cashflow",
        description="自由现金流的保守代理口径。",
        implementation_level="derived",
        primary_sources=["stock_financial_periods"],
        helper_functions=["get_stock_financial_periods"],
        required_fields=["n_cashflow_act", "n_cashflow_inv_act"],
        formula="n_cashflow_act + n_cashflow_inv_act",
        warnings=["当前不是严格资本开支口径，而是 n_cashflow_act + n_cashflow_inv_act 的保守代理。"],
    ),
    "fcf_yield": FactorDefinition(
        factor_id="fcf_yield",
        display_name="自由现金流收益率",
        category="valuation",
        description="自由现金流相对总市值的收益率。",
        implementation_level="derived",
        primary_sources=["stock_financial_periods", "stock_basic_info", "market_quotes"],
        helper_functions=["get_stock_financial_periods", "get_stock_basic_info", "get_market_quotes"],
        required_fields=["fcf", "total_mv|market_cap"],
        formula="fcf / total_mv",
        warnings=["市值字段当前按亿元口径换算，自由现金流按元口径计算。"],
    ),
    "fcf_margin": FactorDefinition(
        factor_id="fcf_margin",
        display_name="自由现金流率",
        category="cashflow",
        description="自由现金流相对营收的比率。",
        implementation_level="derived",
        primary_sources=["stock_financial_periods"],
        helper_functions=["get_stock_financial_periods"],
        required_fields=["fcf", "revenue_ttm|revenue|oper_rev"],
        formula="fcf / revenue_base",
        fallback_rules=["当前营收优先使用 revenue_ttm，缺失时回退到单期 revenue/oper_rev。"],
    ),
    "ocf_yield": FactorDefinition(
        factor_id="ocf_yield",
        display_name="经营现金流收益率",
        category="valuation",
        description="经营现金流相对总市值的收益率。",
        implementation_level="derived",
        primary_sources=["stock_financial_periods", "stock_basic_info", "market_quotes"],
        helper_functions=["get_stock_financial_periods", "get_stock_basic_info", "get_market_quotes"],
        required_fields=["n_cashflow_act", "total_mv|market_cap"],
        formula="n_cashflow_act / total_mv",
        warnings=["市值字段当前按亿元口径换算。"],
    ),
    "working_capital_change": FactorDefinition(
        factor_id="working_capital_change",
        display_name="营运资本变动",
        category="cashflow",
        description="最近两期净营运资本差额。",
        implementation_level="derived",
        primary_sources=["stock_financial_periods"],
        helper_functions=["get_stock_financial_periods"],
        required_fields=["最近两期 total_cur_assets", "最近两期 total_cur_liab"],
        formula="net_working_capital_t - net_working_capital_t-1",
        warnings=["缺少最近两期任一期流动资产/流动负债时返回空值。"],
    ),
    "pct_chg": FactorDefinition(
        factor_id="pct_chg",
        display_name="涨跌幅",
        category="momentum",
        description="最新日涨跌幅。",
        implementation_level="ready",
        primary_sources=["market_quotes", "stock_daily_quotes"],
        helper_functions=["get_market_quotes", "get_stock_daily_quotes"],
        required_fields=["pct_chg"],
    ),
    "turnover_rate": FactorDefinition(
        factor_id="turnover_rate",
        display_name="换手率",
        category="trading",
        description="交投活跃度指标。",
        implementation_level="ready",
        primary_sources=["stock_basic_info", "market_quotes"],
        helper_functions=["get_stock_basic_info", "get_market_quotes"],
        required_fields=["turnover_rate"],
    ),
    "volume_ratio": FactorDefinition(
        factor_id="volume_ratio",
        display_name="量比",
        category="trading",
        description="短期放量/缩量强度。",
        implementation_level="ready",
        primary_sources=["stock_basic_info", "market_quotes"],
        helper_functions=["get_stock_basic_info", "get_market_quotes"],
        required_fields=["volume_ratio"],
    ),
    "ma20": FactorDefinition(
        factor_id="ma20",
        display_name="20 日均线",
        category="technical",
        description="中短期趋势基线。",
        implementation_level="time_series",
        primary_sources=["stock_daily_quotes"],
        helper_functions=["get_stock_daily_quotes", "compute_many"],
        required_fields=["close"],
        formula="MA(close, 20)",
        warnings=["至少 20 个交易日历史行情。"],
    ),
    "ma60": FactorDefinition(
        factor_id="ma60",
        display_name="60 日均线",
        category="technical",
        description="中期趋势基线。",
        implementation_level="time_series",
        primary_sources=["stock_daily_quotes"],
        helper_functions=["get_stock_daily_quotes", "compute_many"],
        required_fields=["close"],
        formula="MA(close, 60)",
        warnings=["至少 60 个交易日历史行情。"],
    ),
    "rsi14": FactorDefinition(
        factor_id="rsi14",
        display_name="RSI14",
        category="technical",
        description="常用超买超卖指标。",
        implementation_level="time_series",
        primary_sources=["stock_daily_quotes"],
        helper_functions=["get_stock_daily_quotes", "compute_many"],
        required_fields=["close"],
        formula="RSI(close, 14)",
        warnings=["至少 14 个交易日历史行情。"],
    ),
    "kdj_k": FactorDefinition(
        factor_id="kdj_k",
        display_name="KDJ-K",
        category="technical",
        description="KDJ 随机指标 K 值。",
        implementation_level="time_series",
        primary_sources=["stock_daily_quotes"],
        helper_functions=["get_stock_daily_quotes", "compute_many"],
        required_fields=["high", "low", "close"],
        formula="KDJ(high, low, close).k",
        warnings=["至少 9 个交易日高低收序列。"],
    ),
    "kdj_d": FactorDefinition(
        factor_id="kdj_d",
        display_name="KDJ-D",
        category="technical",
        description="KDJ 随机指标 D 值。",
        implementation_level="time_series",
        primary_sources=["stock_daily_quotes"],
        helper_functions=["get_stock_daily_quotes", "compute_many"],
        required_fields=["high", "low", "close"],
        formula="KDJ(high, low, close).d",
        warnings=["至少 9 个交易日高低收序列。"],
    ),
    "kdj_j": FactorDefinition(
        factor_id="kdj_j",
        display_name="KDJ-J",
        category="technical",
        description="KDJ 随机指标 J 值。",
        implementation_level="time_series",
        primary_sources=["stock_daily_quotes"],
        helper_functions=["get_stock_daily_quotes", "compute_many"],
        required_fields=["high", "low", "close"],
        formula="KDJ(high, low, close).j",
        warnings=["至少 9 个交易日高低收序列。"],
    ),
    "dif": FactorDefinition(
        factor_id="dif",
        display_name="MACD-DIF",
        category="technical",
        description="MACD 快慢线差值。",
        implementation_level="time_series",
        primary_sources=["stock_daily_quotes"],
        helper_functions=["get_stock_daily_quotes", "compute_many"],
        required_fields=["close"],
        formula="MACD(close).dif",
        warnings=["至少 26 个交易日历史行情。"],
    ),
    "dea": FactorDefinition(
        factor_id="dea",
        display_name="MACD-DEA",
        category="technical",
        description="MACD 信号线。",
        implementation_level="time_series",
        primary_sources=["stock_daily_quotes"],
        helper_functions=["get_stock_daily_quotes", "compute_many"],
        required_fields=["close"],
        formula="MACD(close).dea",
        warnings=["至少 26 个交易日历史行情。"],
    ),
    "macd_hist": FactorDefinition(
        factor_id="macd_hist",
        display_name="MACD 柱状图",
        category="technical",
        description="MACD 动量扩散程度。",
        implementation_level="time_series",
        primary_sources=["stock_daily_quotes"],
        helper_functions=["get_stock_daily_quotes", "compute_many"],
        required_fields=["close"],
        formula="MACD(close).hist",
        warnings=["至少 26 个交易日历史行情。"],
    ),
}


P0_BUNDLE_FACTOR_PACKS: Dict[str, List[str]] = {
    "value_core": list_bundle_fields("value_core"),
    "quality_core": list_bundle_fields("quality_core"),
    "growth_cashflow_core": list_bundle_fields("growth_cashflow_core"),
}


RECOMMENDED_FACTOR_PACKS: Dict[str, List[str]] = {
    **P0_BUNDLE_FACTOR_PACKS,
    "growth_core": list(P0_BUNDLE_FACTOR_PACKS["growth_cashflow_core"]),
    "technical_core": [
        "ma20",
        "ma60",
        "rsi14",
        "kdj_k",
        "kdj_d",
        "kdj_j",
        "dif",
        "dea",
        "macd_hist",
    ],
    "liquidity_core": [
        "pct_chg",
        "turnover_rate",
        "volume_ratio",
    ],
}


FACTOR_RUNTIME_SEMANTIC_CONTRACTS: Dict[str, RuntimeSemanticContract] = {
    "pe": RuntimeSemanticContract(direct_fields=["pe"], source_priority=["basic_info.pe", "market_quotes.pe"], minimum_input_groups=[["pe"]]),
    "pe_ttm": RuntimeSemanticContract(direct_fields=["pe_ttm"], source_priority=["basic_info.pe_ttm", "basic_info.pe", "market_quotes.pe"], fallback_chain=["pe"], minimum_input_groups=[["pe_ttm"], ["pe"]], warning_conditions=[WARN_PE_TTM_FALLBACK_TO_PE], warning_categories=["fallback_used"]),
    "pb": RuntimeSemanticContract(direct_fields=["pb"], source_priority=["basic_info.pb", "pb_mrq"], fallback_chain=["pb_mrq"], minimum_input_groups=[["pb"], ["pb_mrq"]], warning_conditions=[WARN_PB_FALLBACK_TO_PB_MRQ], warning_categories=["fallback_used"]),
    "pb_mrq": RuntimeSemanticContract(
        direct_fields=["pb_mrq|total_mv", "total_equity"],
        source_priority=["basic_info.pb_mrq", "market_quotes.total_mv|basic_info.total_mv|basic_info.market_cap", "latest_financial.total_equity"],
        fallback_chain=["total_mv / total_equity"],
        conservative_proxies=["保守估算"],
        minimum_input_groups=[["pb_mrq"], ["total_mv|market_cap", "total_equity"]],
        minimum_computable_conditions=[COND_TOTAL_EQUITY_NON_ZERO],
        warning_conditions=[WARN_PB_MRQ_ESTIMATED_FROM_MARKET_CAP_AND_EQUITY],
        warning_categories=["proxy_used"],
    ),
    "ps_ttm": RuntimeSemanticContract(direct_fields=["ps_ttm"], source_priority=["basic_info.ps_ttm", "basic_info.ps"], fallback_chain=["ps"], minimum_input_groups=[["ps_ttm"], ["ps"]], warning_conditions=[WARN_PS_TTM_FALLBACK_TO_PS], warning_categories=["fallback_used"]),
    "dividend_yield": RuntimeSemanticContract(
        direct_fields=["dividend_yield|financial_indicators.dividend_yield"],
        source_priority=["basic_info.dividend_yield", "latest_financial.financial_indicators.dividend_yield", "latest_financial.dividend_yield"],
        fallback_chain=[
            "basic_info.dividend_yield",
            "financial_indicators.dividend_yield",
            "period 顶层 dividend_yield",
        ],
        minimum_input_groups=[["dividend_yield"], ["financial_indicators.dividend_yield"]],
        warning_conditions=[WARN_DIVIDEND_YIELD_FALLBACK_TO_FINANCIAL_FIELD],
        warning_categories=["fallback_used"],
    ),
    "peg": RuntimeSemanticContract(
        direct_fields=["pe_ttm|pe", "net_profit_yoy"],
        fallback_chain=["pe_ttm 缺失时回退到 pe"],
        availability_constraints=["净利润同比为正且非 0"],
        minimum_input_groups=[["pe_ttm", "net_profit_yoy"], ["pe", "net_profit_yoy"]],
        minimum_computable_conditions=[COND_NET_PROFIT_YOY_POSITIVE, COND_NET_PROFIT_YOY_NON_ZERO],
    ),
    "industry_pe_median": RuntimeSemanticContract(
        direct_fields=["industry", "pe_ttm|pe"],
        availability_constraints=["行业样本数建议 >= 5"],
        minimum_input_groups=[["industry", "pe_ttm"], ["industry", "pe"]],
        warning_conditions=[WARN_INDUSTRY_PEER_SAMPLE_COUNT_LT_5],
        warning_categories=["low_sample_size"],
    ),
    "industry_pb_median": RuntimeSemanticContract(direct_fields=["industry", "pb|pb_mrq"], minimum_input_groups=[["industry", "pb"], ["industry", "pb_mrq"]], warning_conditions=[WARN_INDUSTRY_PEER_SAMPLE_COUNT_LT_5], warning_categories=["low_sample_size"]),
    "roe": RuntimeSemanticContract(direct_fields=["roe"], minimum_input_groups=[["roe"]]),
    "roa": RuntimeSemanticContract(direct_fields=["roa"], minimum_input_groups=[["roa"]]),
    "gross_margin": RuntimeSemanticContract(direct_fields=["gross_margin"], minimum_input_groups=[["gross_margin"]]),
    "netprofit_margin": RuntimeSemanticContract(direct_fields=["netprofit_margin"], minimum_input_groups=[["netprofit_margin"]]),
    "debt_to_assets": RuntimeSemanticContract(direct_fields=["debt_to_assets"], minimum_input_groups=[["debt_to_assets"]]),
    "assets_to_eqt": RuntimeSemanticContract(direct_fields=["assets_to_eqt"], minimum_input_groups=[["assets_to_eqt"]]),
    "current_ratio": RuntimeSemanticContract(direct_fields=["current_ratio"], minimum_input_groups=[["current_ratio"]]),
    "quick_ratio": RuntimeSemanticContract(direct_fields=["quick_ratio"], minimum_input_groups=[["quick_ratio"]]),
    "cash_ratio": RuntimeSemanticContract(direct_fields=["cash_ratio"], minimum_input_groups=[["cash_ratio"]]),
    "net_working_capital": RuntimeSemanticContract(direct_fields=["total_cur_assets", "total_cur_liab"], period_selection_strategy="current_period_only", minimum_input_groups=[["total_cur_assets", "total_cur_liab"]]),
    "revenue_ttm": RuntimeSemanticContract(direct_fields=["revenue_ttm"], period_selection_strategy="current_period_only", minimum_input_groups=[["revenue_ttm"]]),
    "net_profit_ttm": RuntimeSemanticContract(
        direct_fields=["net_profit_ttm|net_profit|net_income"],
        source_priority=["latest_financial.net_profit_ttm", "latest_financial.net_profit", "latest_financial.net_income"],
        fallback_chain=["net_profit_ttm", "net_profit", "net_income"],
        minimum_input_groups=[["net_profit_ttm"], ["net_profit"], ["net_income"]],
        warning_conditions=[WARN_NET_PROFIT_TTM_FALLBACK_TO_NET_PROFIT_OR_NET_INCOME],
        warning_categories=["fallback_used"],
    ),
    "piotroski_f_score": RuntimeSemanticContract(direct_fields=["roa", "n_cashflow_act", "current_ratio", "gross_margin", "asset_turnover"], minimum_input_groups=[["latest_period", "comparison_period", "roa", "n_cashflow_act", "current_ratio", "gross_margin", "asset_turnover"]], minimum_computable_conditions=[COND_COMPARISON_PERIOD_AVAILABLE, COND_ALL_REQUIRED_SIGNAL_INPUTS_AVAILABLE]),
    "altman_z_score": RuntimeSemanticContract(direct_fields=["total_assets", "total_liab", "total_cur_assets", "total_cur_liab", "ebit", "revenue"], minimum_input_groups=[["total_assets", "total_liab", "total_cur_assets", "total_cur_liab", "ebit", "revenue", "market_value_proxy", "undistr_porfit"]], minimum_computable_conditions=[COND_TOTAL_ASSETS_NON_ZERO, COND_TOTAL_LIAB_NON_ZERO]),
    "beneish_m_score": RuntimeSemanticContract(direct_fields=["revenue", "accounts_receiv", "oper_cost", "total_assets", "total_cur_assets", "fix_assets", "n_cashflow_act"], minimum_input_groups=[["latest_period", "comparison_period", "revenue", "accounts_receiv", "oper_cost", "total_assets", "total_cur_assets", "fix_assets", "n_cashflow_act", "depreciation_current", "depreciation_previous"]], minimum_computable_conditions=[COND_COMPARISON_PERIOD_AVAILABLE, COND_SALES_CURRENT_NON_ZERO, COND_SALES_PREVIOUS_NON_ZERO, COND_TOTAL_ASSETS_CURRENT_NON_ZERO, COND_TOTAL_ASSETS_PREVIOUS_NON_ZERO, COND_TOTAL_LIAB_PREVIOUS_NON_ZERO, COND_DEPRECIATION_PLUS_FIXED_ASSETS_CURRENT_NON_ZERO, COND_DEPRECIATION_PLUS_FIXED_ASSETS_PREVIOUS_NON_ZERO, COND_SGA_PREVIOUS_NON_ZERO, COND_GROSS_MARGIN_CURRENT_NON_ZERO, COND_ASSET_QUALITY_PREVIOUS_NON_ZERO]),
    "n_cashflow_act": RuntimeSemanticContract(direct_fields=["n_cashflow_act"], period_selection_strategy="current_period_only", minimum_input_groups=[["n_cashflow_act"]]),
    "revenue_yoy": RuntimeSemanticContract(direct_fields=["revenue|oper_rev", "上年同季报告期"], period_selection_strategy="same_period_last_year", minimum_input_groups=[["latest_period.revenue|oper_rev", "prior_same_period.revenue|oper_rev"]], minimum_computable_conditions=[COND_COMPARISON_PERIOD_AVAILABLE, COND_PRIOR_PERIOD_METRIC_NON_ZERO]),
    "net_profit_yoy": RuntimeSemanticContract(direct_fields=["net_profit|net_income", "上年同季报告期"], period_selection_strategy="same_period_last_year", minimum_input_groups=[["latest_period.net_profit|net_income", "prior_same_period.net_profit|net_income"]], minimum_computable_conditions=[COND_COMPARISON_PERIOD_AVAILABLE, COND_PRIOR_PERIOD_METRIC_NON_ZERO]),
    "oper_profit_yoy": RuntimeSemanticContract(direct_fields=["oper_profit|operating_profit|ebit", "上年同季报告期"], period_selection_strategy="same_period_last_year", minimum_input_groups=[["latest_period.oper_profit|operating_profit|ebit", "prior_same_period.oper_profit|operating_profit|ebit"]], minimum_computable_conditions=[COND_COMPARISON_PERIOD_AVAILABLE, COND_PRIOR_PERIOD_METRIC_NON_ZERO]),
    "revenue_cagr_3y": RuntimeSemanticContract(direct_fields=["revenue_ttm|revenue|oper_rev", "同季三年前报告期"], period_selection_strategy="same_period_n_years_3", minimum_input_groups=[["latest_period.revenue_ttm|revenue|oper_rev", "base_3y_period.revenue_ttm|revenue|oper_rev"]], minimum_computable_conditions=[COND_BASE_PERIOD_AVAILABLE, COND_CURRENT_VALUE_POSITIVE, COND_BASE_VALUE_POSITIVE]),
    "profit_cagr_3y": RuntimeSemanticContract(direct_fields=["net_profit_ttm|net_profit|net_income", "同季三年前报告期"], period_selection_strategy="same_period_n_years_3", minimum_input_groups=[["latest_period.net_profit_ttm|net_profit|net_income", "base_3y_period.net_profit_ttm|net_profit|net_income"]], minimum_computable_conditions=[COND_BASE_PERIOD_AVAILABLE, COND_CURRENT_VALUE_POSITIVE, COND_BASE_VALUE_POSITIVE]),
    "roic": RuntimeSemanticContract(
        direct_fields=["ebit|oper_profit|operating_profit", "total_equity", "total_liab"],
        fallback_chain=["total_profit 与 net_profit 估算", "25% 默认税率", "money_cap 缺失时按 0 处理"],
        conservative_proxies=["平均投入资本"],
        tax_estimation_strategy="profit_based_clamped_0_35_else_fixed_25",
        minimum_input_groups=[["ebit|oper_profit|operating_profit", "total_equity", "total_liab"]],
        minimum_computable_conditions=[COND_INVESTED_CAPITAL_POSITIVE],
        warning_conditions=[WARN_ROIC_MONEY_CAP_MISSING_AS_ZERO],
        warning_categories=["precision_degraded"],
    ),
    "cash_conversion": RuntimeSemanticContract(
        direct_fields=["n_cashflow_act", "net_profit|net_income"],
        availability_constraints=["净利润缺失或为 0 时返回空值"],
        minimum_input_groups=[["n_cashflow_act", "net_profit|net_income"]],
        minimum_computable_conditions=[COND_NET_PROFIT_NON_ZERO],
    ),
    "accrual_ratio": RuntimeSemanticContract(
        direct_fields=["net_profit|net_income", "n_cashflow_act", "total_assets"],
        denominator_guards=["最新总资产为分母"],
        unit_conversions=["百分比"],
        minimum_input_groups=[["net_profit|net_income", "n_cashflow_act", "total_assets"]],
        minimum_computable_conditions=[COND_TOTAL_ASSETS_NON_ZERO],
    ),
    "asset_turnover": RuntimeSemanticContract(
        direct_fields=["revenue_ttm|revenue|oper_rev", "total_assets"],
        denominator_guards=["最新总资产为分母", "不是平均总资产口径"],
        minimum_input_groups=[["revenue_ttm|revenue|oper_rev", "total_assets"]],
        minimum_computable_conditions=[COND_TOTAL_ASSETS_NON_ZERO],
    ),
    "gross_profit_to_assets": RuntimeSemanticContract(
        direct_fields=["revenue_ttm|revenue|oper_rev", "gross_margin", "total_assets"],
        denominator_guards=["最新总资产为分母"],
        unit_conversions=["百分比"],
        minimum_input_groups=[["revenue_ttm|revenue|oper_rev", "gross_margin", "total_assets"]],
        minimum_computable_conditions=[COND_TOTAL_ASSETS_NON_ZERO],
    ),
    "interest_coverage": RuntimeSemanticContract(
        direct_fields=["ebit|oper_profit|operating_profit", "fin_exp|raw_data.income_statement.int_exp"],
        fallback_chain=["ebit / fin_exp", "fin_exp <= 0", "int_exp", "fin_exp_int_exp"],
        availability_constraints=["利息费用缺失", "非正", "raw_data"],
        minimum_input_groups=[["ebit|oper_profit|operating_profit", "fin_exp"], ["ebit|oper_profit|operating_profit", "raw_data.income_statement.int_exp|fin_exp_int_exp"]],
        minimum_computable_conditions=[COND_INTEREST_EXPENSE_POSITIVE],
        warning_conditions=[WARN_INTEREST_COVERAGE_FALLBACK_TO_RAW_INTEREST_EXPENSE],
        warning_categories=["fallback_used"],
    ),
    "inventory_turnover": RuntimeSemanticContract(
        direct_fields=["oper_cost|revenue_ttm|revenue|oper_rev", "inventories"],
        fallback_chain=["oper_cost 缺失时", "gross_margin"],
        denominator_guards=["最新存货余额", "不是平均存货余额"],
        minimum_input_groups=[["oper_cost", "inventories"], ["revenue_ttm|revenue|oper_rev", "gross_margin", "inventories"]],
        minimum_computable_conditions=[COND_INVENTORIES_NON_ZERO],
        warning_conditions=[WARN_INVENTORY_TURNOVER_COST_PROXY_USED],
        warning_categories=["proxy_used"],
    ),
    "receivable_turnover": RuntimeSemanticContract(
        direct_fields=["revenue_ttm|revenue|oper_rev", "accounts_receiv"],
        denominator_guards=["最新应收账款余额", "不是平均应收余额"],
        minimum_input_groups=[["revenue_ttm|revenue|oper_rev", "accounts_receiv"]],
        minimum_computable_conditions=[COND_ACCOUNTS_RECEIV_NON_ZERO],
    ),
    "net_cash_position": RuntimeSemanticContract(
        direct_fields=["money_cap", "total_assets", "total_ncl|total_liab|total_cur_liab"],
        fallback_chain=["total_ncl", "total_liab - total_cur_liab"],
        conservative_proxies=["保守代理口径百分比"],
        minimum_input_groups=[["money_cap", "total_ncl", "total_assets"], ["money_cap", "total_liab", "total_cur_liab", "total_assets"]],
        minimum_computable_conditions=[COND_TOTAL_ASSETS_NON_ZERO],
        warning_conditions=[WARN_NET_CASH_POSITION_PROXY_TOTAL_NCL_USED],
        warning_categories=["proxy_used"],
    ),
    "fcf": RuntimeSemanticContract(
        direct_fields=["n_cashflow_act", "n_cashflow_inv_act"],
        conservative_proxies=["n_cashflow_act + n_cashflow_inv_act", "保守代理"],
        minimum_input_groups=[["n_cashflow_act", "n_cashflow_inv_act"]],
        warning_conditions=[WARN_FCF_CONSERVATIVE_PROXY_USED],
        warning_categories=["proxy_used"],
    ),
    "fcf_yield": RuntimeSemanticContract(
        direct_fields=["fcf", "total_mv|market_cap"],
        source_priority=["market_quotes.total_mv", "basic_info.total_mv", "basic_info.market_cap"],
        unit_conversions=["亿元口径换算", "元口径"],
        minimum_input_groups=[["fcf", "total_mv|market_cap"]],
        minimum_computable_conditions=[COND_MARKET_CAP_NON_ZERO],
    ),
    "fcf_margin": RuntimeSemanticContract(
        direct_fields=["fcf", "revenue_ttm|revenue|oper_rev"],
        fallback_chain=["revenue_ttm", "revenue/oper_rev"],
        minimum_input_groups=[["fcf", "revenue_ttm"], ["fcf", "revenue"], ["fcf", "oper_rev"]],
        minimum_computable_conditions=[COND_REVENUE_BASE_NON_ZERO],
    ),
    "ocf_yield": RuntimeSemanticContract(
        direct_fields=["n_cashflow_act", "total_mv|market_cap"],
        source_priority=["market_quotes.total_mv", "basic_info.total_mv", "basic_info.market_cap"],
        unit_conversions=["亿元口径换算"],
        minimum_input_groups=[["n_cashflow_act", "total_mv|market_cap"]],
        minimum_computable_conditions=[COND_MARKET_CAP_NON_ZERO],
    ),
    "working_capital_change": RuntimeSemanticContract(
        direct_fields=["最近两期 total_cur_assets", "最近两期 total_cur_liab"],
        availability_constraints=["最近两期", "流动资产/流动负债"],
        period_selection_strategy="previous_available_period",
        minimum_input_groups=[["latest_period.total_cur_assets", "latest_period.total_cur_liab", "previous_period.total_cur_assets", "previous_period.total_cur_liab"]],
        minimum_computable_conditions=[COND_PREVIOUS_PERIOD_AVAILABLE],
    ),
    "ma20": RuntimeSemanticContract(direct_fields=["close"], source_priority=["stock_technical_indicators.ma20", "stock_daily_quotes.close"], availability_constraints=["至少 20 个交易日历史行情"], minimum_input_groups=[["close"]], minimum_computable_conditions=[COND_TECHNICAL_LOOKBACK_WINDOW_AVAILABLE]),
    "ma60": RuntimeSemanticContract(direct_fields=["close"], source_priority=["stock_daily_quotes.close"], availability_constraints=["至少 60 个交易日历史行情"], minimum_input_groups=[["close"]], minimum_computable_conditions=[COND_TECHNICAL_LOOKBACK_WINDOW_AVAILABLE]),
    "rsi14": RuntimeSemanticContract(direct_fields=["close"], source_priority=["stock_technical_indicators.rsi14", "stock_daily_quotes.close"], availability_constraints=["至少 14 个交易日历史行情"], minimum_input_groups=[["close"]], minimum_computable_conditions=[COND_TECHNICAL_LOOKBACK_WINDOW_AVAILABLE]),
    "kdj_k": RuntimeSemanticContract(direct_fields=["high", "low", "close"], source_priority=["stock_technical_indicators.kdj_k", "stock_daily_quotes.high|low|close"], availability_constraints=["至少 9 个交易日高低收序列"], minimum_input_groups=[["high", "low", "close"]], minimum_computable_conditions=[COND_TECHNICAL_LOOKBACK_WINDOW_AVAILABLE]),
    "kdj_d": RuntimeSemanticContract(direct_fields=["high", "low", "close"], source_priority=["stock_technical_indicators.kdj_d", "stock_daily_quotes.high|low|close"], availability_constraints=["至少 9 个交易日高低收序列"], minimum_input_groups=[["high", "low", "close"]], minimum_computable_conditions=[COND_TECHNICAL_LOOKBACK_WINDOW_AVAILABLE]),
    "kdj_j": RuntimeSemanticContract(direct_fields=["high", "low", "close"], source_priority=["stock_technical_indicators.kdj_j", "stock_daily_quotes.high|low|close"], availability_constraints=["至少 9 个交易日高低收序列"], minimum_input_groups=[["high", "low", "close"]], minimum_computable_conditions=[COND_TECHNICAL_LOOKBACK_WINDOW_AVAILABLE]),
    "dif": RuntimeSemanticContract(direct_fields=["close"], source_priority=["stock_technical_indicators.dif", "stock_daily_quotes.close"], availability_constraints=["至少 26 个交易日历史行情"], minimum_input_groups=[["close"]], minimum_computable_conditions=[COND_TECHNICAL_LOOKBACK_WINDOW_AVAILABLE]),
    "dea": RuntimeSemanticContract(direct_fields=["close"], source_priority=["stock_technical_indicators.dea", "stock_daily_quotes.close"], availability_constraints=["至少 26 个交易日历史行情"], minimum_input_groups=[["close"]], minimum_computable_conditions=[COND_TECHNICAL_LOOKBACK_WINDOW_AVAILABLE]),
    "macd_hist": RuntimeSemanticContract(direct_fields=["close"], source_priority=["stock_technical_indicators.macd_hist", "stock_daily_quotes.close"], availability_constraints=["至少 26 个交易日历史行情"], minimum_input_groups=[["close"]], minimum_computable_conditions=[COND_TECHNICAL_LOOKBACK_WINDOW_AVAILABLE]),
}

FACTOR_RUNTIME_SEMANTIC_CONTRACTS = {
    name: contract if contract.source_priority else replace(contract, source_priority=list(P0_SOURCE_PRIORITY_BY_FIELD.get(name, [])))
    for name, contract in FACTOR_RUNTIME_SEMANTIC_CONTRACTS.items()
}


def get_factor_definition(factor_id: str) -> Optional[FactorDefinition]:
    """按 factor_id 查询通用因子目录中的因子定义。

    Args:
        factor_id: 因子标识（如 "pe_ttm" / "roe"），内部会去除首尾空白

    Returns:
        Optional[FactorDefinition]: 命中的因子定义对象；未登记时返回 None
    """
    return COMMON_FACTOR_CATALOG.get(str(factor_id).strip())


def list_factor_definitions(category: Optional[FactorCategory] = None) -> List[Dict[str, object]]:
    """列出通用因子目录中的因子定义（按 category 与 factor_id 排序）。

    Args:
        category: 可选的因子类别过滤，默认为 None（不过滤）

    Returns:
        list[dict]: 因子定义 dict 列表，元素结构由 FactorDefinition.to_dict() 决定，按
            (category, factor_id) 升序排序
    """
    items = list(COMMON_FACTOR_CATALOG.values())
    if category:
        items = [item for item in items if item.category == category]
    return [item.to_dict() for item in sorted(items, key=lambda item: (item.category, item.factor_id))]


def get_factor_pack(pack_id: str) -> List[Dict[str, object]]:
    """按 pack_id 获取推荐因子包内的因子定义列表。

    Args:
        pack_id: 因子包标识（如 "value_core" / "quality_core" / "growth_cashflow_core" /
            "technical_core" / "liquidity_core"），内部会去除首尾空白

    Returns:
        list[dict]: 该 pack 中所有已登记因子的 to_dict() 结果列表；
            未配置或因子均未登记时返回空列表
    """
    factor_ids = RECOMMENDED_FACTOR_PACKS.get(str(pack_id).strip(), [])
    return [COMMON_FACTOR_CATALOG[factor_id].to_dict() for factor_id in factor_ids if factor_id in COMMON_FACTOR_CATALOG]


def infer_recommended_factor_packs(
    text: str = "",
    *,
    category: str = "",
    expected_fields: Optional[List[str]] = None,
) -> List[str]:
    """根据自然语言文本、类别或期望字段推断推荐的 factor pack 列表。

    Args:
        text: 自然语言需求描述，默认为 ""
        category: 类别关键词，默认为 ""
        expected_fields: 期望因子字段名列表，默认为 None

    Returns:
        list[str]: 推荐 pack_id 列表，元素可能值：
            "value_core" / "quality_core" / "growth_cashflow_core" /
            "technical_core" / "liquidity_core"；按命中顺序去重
    """
    normalized = " ".join([
        str(text or "").lower(),
        str(category or "").lower(),
        " ".join(str(field).lower() for field in (expected_fields or []) if str(field).strip()),
    ])

    pack_ids: List[str] = []

    if any(keyword in normalized for keyword in ["估值", "valuation", "pe", "pb", "ps", "peg", "股息率", "同行", "peer"]):
        pack_ids.append("value_core")
    if any(keyword in normalized for keyword in ["peg", "净利润增长", "profit growth", "earnings growth"]):
        pack_ids.append("growth_cashflow_core")
    if any(keyword in normalized for keyword in ["质量", "quality", "roe", "roa", "毛利率", "净利率", "负债率", "流动比率", "财务健康"]):
        pack_ids.append("quality_core")
    if any(keyword in normalized for keyword in ["增长", "growth", "现金流", "cashflow", "营收", "净利润", "fcf", "ttm", "同比", "cagr"]):
        pack_ids.append("growth_cashflow_core")
    if any(keyword in normalized for keyword in ["技术", "technical", "ma", "均线", "rsi", "kdj", "macd", "动量", "momentum"]):
        pack_ids.append("technical_core")
    if any(keyword in normalized for keyword in ["换手率", "量比", "涨跌幅", "成交活跃", "流动性", "liquidity", "turnover", "volume_ratio", "pct_chg"]):
        pack_ids.append("liquidity_core")

    for field_name in expected_fields or []:
        normalized_field = str(field_name).strip()
        if not normalized_field:
            continue
        for pack_id, factor_ids in RECOMMENDED_FACTOR_PACKS.items():
            if normalized_field in factor_ids and pack_id not in pack_ids:
                pack_ids.append(pack_id)

    return list(dict.fromkeys(pack_ids))


def select_relevant_factor_definitions(
    text: str = "",
    *,
    category: str = "",
    expected_fields: Optional[List[str]] = None,
    max_items: int = 16,
) -> List[Dict[str, object]]:
    """根据需求文本/类别/期望字段挑选相关因子定义，最多返回 max_items 条。

    Args:
        text: 自然语言需求描述，默认为 ""
        category: 类别关键词，默认为 ""
        expected_fields: 期望因子字段名列表，默认为 None
        max_items: 最多返回条目数，默认为 16

    Returns:
        list[dict]: 选中因子的 to_dict() 结果，元素结构由 FactorDefinition.to_dict() 决定；
            选取顺序：先 expected_fields 命中字段，再 infer_recommended_factor_packs 命中字段，
            最后按 fallback category 兜底；总数不超过 max_items
    """
    selected_ids: List[str] = []

    for field_name in expected_fields or []:
        normalized_field = str(field_name).strip()
        if normalized_field in COMMON_FACTOR_CATALOG and normalized_field not in selected_ids:
            selected_ids.append(normalized_field)

    for pack_id in infer_recommended_factor_packs(text, category=category, expected_fields=expected_fields):
        for factor_id in RECOMMENDED_FACTOR_PACKS.get(pack_id, []):
            if factor_id in COMMON_FACTOR_CATALOG and factor_id not in selected_ids:
                selected_ids.append(factor_id)

    if not selected_ids:
        normalized = f"{text} {category}".lower()
        fallback_categories: List[str] = []
        if any(keyword in normalized for keyword in ["估值", "valuation", "pe", "pb", "peg", "ps"]):
            fallback_categories.append("valuation")
        if any(keyword in normalized for keyword in ["质量", "quality", "roe", "roa", "毛利率", "净利率"]):
            fallback_categories.append("quality")
        if any(keyword in normalized for keyword in ["技术", "technical", "rsi", "macd", "kdj", "ma"]):
            fallback_categories.append("technical")
        if any(keyword in normalized for keyword in ["增长", "growth", "现金流", "cashflow", "同比", "fcf"]):
            fallback_categories.extend(["growth", "cashflow"])
        if any(keyword in normalized for keyword in ["换手率", "量比", "涨跌幅", "liquidity", "turnover"]):
            fallback_categories.append("trading")

        for item in list_factor_definitions():
            factor_id = str(item.get("factor_id") or "").strip()
            factor_category = str(item.get("category") or "").strip()
            if factor_id and factor_category in fallback_categories and factor_id not in selected_ids:
                selected_ids.append(factor_id)

    return [COMMON_FACTOR_CATALOG[factor_id].to_dict() for factor_id in selected_ids[:max_items] if factor_id in COMMON_FACTOR_CATALOG]


def build_factor_catalog_prompt_context(
    text: str = "",
    *,
    category: str = "",
    expected_fields: Optional[List[str]] = None,
    max_items: int = 16,
) -> str:
    """构建用于 Skill 生成提示的因子目录上下文文本。

    Args:
        text: 自然语言需求描述，默认为 ""
        category: 类别关键词，默认为 ""
        expected_fields: 期望因子字段名列表，默认为 None
        max_items: 选取因子上限，默认为 16

    Returns:
        str: 多行 prompt 文本；包含推荐 pack、helper/bundle 提示、可用因子列表与生成约束；
            若未命中任何因子且无 pack，返回空字符串 ""
    """
    factor_items = select_relevant_factor_definitions(
        text,
        category=category,
        expected_fields=expected_fields,
        max_items=max_items,
    )
    pack_ids = infer_recommended_factor_packs(
        text,
        category=category,
        expected_fields=expected_fields,
    )

    if not factor_items and not pack_ids:
        return ""

    lines: List[str] = [
        "当前需求命中的常用分析因子白名单：",
        "- 这些因子已经在 runtime catalog 中登记，生成 Skill 时优先复用，不要自造近义字段或另起一套口径。",
    ]
    if pack_ids:
        lines.append(f"- 推荐 factor packs: {', '.join(pack_ids)}")

    helper_hints: List[str] = []
    if "value_core" in pack_ids:
        helper_hints.extend(["get_stock_valuation_context", "get_value_factor_bundle", "summarize_industry_valuation"])
    if "quality_core" in pack_ids:
        helper_hints.extend(["get_quality_factor_bundle", "get_fundamental_factor_snapshot"])
    if "growth_cashflow_core" in pack_ids:
        helper_hints.extend(["get_growth_cashflow_factor_bundle", "get_fundamental_factor_snapshot"])
    if "technical_core" in pack_ids:
        helper_hints.extend(["get_stock_daily_quotes", "compute_many"])
    if helper_hints:
        lines.append(f"- 优先 helper/bundle: {', '.join(list(dict.fromkeys(helper_hints)))}")

    lines.append("- 可用因子: ")
    for item in factor_items:
        factor_id = str(item.get("factor_id") or "").strip()
        display_name = str(item.get("display_name") or factor_id).strip()
        implementation_level = str(item.get("implementation_level") or "").strip()
        helpers = ", ".join(item.get("helper_functions") or [])
        formula = str(item.get("formula") or "").strip()
        description = str(item.get("description") or "").strip()
        line = f"  - {factor_id} ({display_name}) | level={implementation_level}"
        if helpers:
            line += f" | helpers={helpers}"
        if formula:
            line += f" | formula={formula}"
        elif description:
            line += f" | {description}"
        lines.append(line)

    lines.extend([
        "- 如果需求只是这些白名单因子的读取、组合或固定公式计算，优先实现成确定性 Skill，不要发明新的底层因子。",
        "- 若 expected_output.fields 涉及因子字段，优先使用 catalog 中已有 factor_id 作为输出字段名。",
    ])
    return "\n".join(lines)


def build_factor_implementation_outline(factor_ids: List[str]) -> Dict[str, object]:
    """基于一组 factor_id 构建实现轮廓摘要。

    Args:
        factor_ids: 因子标识列表；未在 COMMON_FACTOR_CATALOG 中登记的会被忽略

    Returns:
        dict: 字段说明——
            factor_ids: list[str]，命中并展开后的 factor_id 列表
            collections: list[str]，涉及的数据集合名（去重升序）
            helpers: list[str]，涉及的 helper 函数名（去重升序）
            implementation_levels: list[str]，涉及的实现级别（去重升序）
            warnings: list[str]，所有因子的告警文案（保留重复顺序）
    """
    selected: List[FactorDefinition] = []
    for factor_id in factor_ids:
        factor = get_factor_definition(factor_id)
        if factor:
            selected.append(factor)

    return {
        "factor_ids": [factor.factor_id for factor in selected],
        "collections": sorted({source for factor in selected for source in factor.primary_sources}),
        "helpers": sorted({helper for factor in selected for helper in factor.helper_functions}),
        "implementation_levels": sorted({factor.implementation_level for factor in selected}),
        "warnings": [warning for factor in selected for warning in factor.warnings],
    }


def validate_factor_catalog_schema_alignment() -> Dict[str, List[Dict[str, str]]]:
    """校验 P0 factor schema 与 COMMON_FACTOR_CATALOG 的一致性。

    Returns:
        dict: 字段说明——
            mismatches: list[dict]，schema 与 catalog 的 data_quality_tier / implementation_level
                不一致条目，每个元素字段：
                — field: 字段名
                — catalog_implementation_level: catalog 中登记的 implementation_level
                — schema_data_quality_tier: schema 中登记的 data_quality_tier
            missing_catalog_entries: list[dict]，schema 已登记但 catalog 未登记的字段
                — field: 字段名
                — reason: 缺失原因说明
            missing_cautious_catalog_entries: list[dict]，schema 标记为 cautious 但 catalog 未登记的字段
                — field: 字段名
                — expected_implementation_level: 期望级别（"cautious"）
                — reason: 缺失原因说明
    """
    mismatches: List[Dict[str, str]] = []
    missing_catalog_entries: List[Dict[str, str]] = []
    missing_cautious_catalog_entries: List[Dict[str, str]] = []

    for field_name, schema in P0_FACTOR_FIELD_SCHEMA.items():
        catalog_entry = COMMON_FACTOR_CATALOG.get(field_name)
        if catalog_entry is None:
            missing_catalog_entries.append(
                {
                    "field": field_name,
                    "reason": "schema 已登记该字段，但 factor_catalog 尚未登记。",
                }
            )
            if schema.data_quality_tier == "cautious":
                missing_cautious_catalog_entries.append(
                    {
                        "field": field_name,
                        "expected_implementation_level": "cautious",
                        "reason": "schema 标记为 cautious，但 factor_catalog 尚未登记该字段。",
                    }
                )
            continue

        expected_tier = "cautious" if catalog_entry.implementation_level == "cautious" else "standard"
        if expected_tier != schema.data_quality_tier:
            mismatches.append(
                {
                    "field": field_name,
                    "catalog_implementation_level": catalog_entry.implementation_level,
                    "schema_data_quality_tier": schema.data_quality_tier,
                }
            )

    return {
        "mismatches": mismatches,
        "missing_catalog_entries": missing_catalog_entries,
        "missing_cautious_catalog_entries": missing_cautious_catalog_entries,
    }


def validate_technical_factor_catalog_schema_alignment() -> Dict[str, List[Dict[str, str]]]:
    """校验技术因子 schema 与 COMMON_FACTOR_CATALOG 的一致性。

    Returns:
        dict: 字段说明——
            mismatches: list[dict]，catalog 类别与期望 technical 不一致条目，每个元素字段：
                — field: 字段名
                — catalog_category: catalog 中登记的类别
                — expected_category: 期望类别（"technical"）
            missing_catalog_entries: list[dict]，technical schema 已登记但 catalog 未登记的字段
                — field: 字段名
                — reason: 缺失原因说明
    """
    mismatches: List[Dict[str, str]] = []
    missing_catalog_entries: List[Dict[str, str]] = []

    for field_name in TECHNICAL_FACTOR_FIELD_SCHEMA.keys():
        catalog_entry = COMMON_FACTOR_CATALOG.get(field_name)
        if catalog_entry is None:
            missing_catalog_entries.append(
                {
                    "field": field_name,
                    "reason": "technical schema 已登记该字段，但 factor_catalog 尚未登记。",
                }
            )
            continue

        if catalog_entry.category != "technical":
            mismatches.append(
                {
                    "field": field_name,
                    "catalog_category": catalog_entry.category,
                    "expected_category": "technical",
                }
            )

    return {
        "mismatches": mismatches,
        "missing_catalog_entries": missing_catalog_entries,
    }


def validate_factor_pack_schema_alignment() -> Dict[str, List[Dict[str, object]]]:
    """校验 RECOMMENDED_FACTOR_PACKS 与 schema bundle 字段集是否对齐。

    Returns:
        dict: 字段说明——
            mismatches: list[dict]，pack 字段集与 schema bundle 不一致条目，每个元素字段：
                — pack_id: pack 标识（"value_core" / "quality_core" /
                    "growth_cashflow_core" / "growth_core"）
                — expected_fields: list[str]，期望的字段名列表
                — actual_fields: list[str]，实际登记的字段名列表
                — missing_fields: list[str]，缺失字段名
                — extra_fields: list[str]，多余字段名
    """
    mismatches: List[Dict[str, object]] = []
    expected_packs = {
        "value_core": list_bundle_fields("value_core"),
        "quality_core": list_bundle_fields("quality_core"),
        "growth_cashflow_core": list_bundle_fields("growth_cashflow_core"),
        "growth_core": list_bundle_fields("growth_cashflow_core"),
    }

    for pack_id, expected_fields in expected_packs.items():
        actual_fields = RECOMMENDED_FACTOR_PACKS.get(pack_id, [])
        if actual_fields != expected_fields:
            mismatches.append(
                {
                    "pack_id": pack_id,
                    "expected_fields": expected_fields,
                    "actual_fields": actual_fields,
                    "missing_fields": [field for field in expected_fields if field not in actual_fields],
                    "extra_fields": [field for field in actual_fields if field not in expected_fields],
                }
            )

    return {"mismatches": mismatches}


def validate_factor_catalog_source_alignment() -> Dict[str, List[Dict[str, object]]]:
    """校验 catalog 中是否仍引用 legacy 数据源（stock_financial_data / get_stock_financial_data）。

    Returns:
        dict: 字段说明——
            legacy_source_refs: list[dict]，仍引用 legacy 数据源的字段条目，每个元素字段：
                — field: 字段名
                — legacy_sources: list[str]，命中的 legacy 数据源名（"stock_financial_data"）
                — legacy_helpers: list[str]，命中的 legacy helper 名（"get_stock_financial_data"）
    """
    legacy_source_refs: List[Dict[str, object]] = []

    for field_name in P0_FACTOR_FIELD_SCHEMA.keys():
        catalog_entry = COMMON_FACTOR_CATALOG.get(field_name)
        if catalog_entry is None:
            continue

        legacy_sources = [
            source for source in catalog_entry.primary_sources if source == "stock_financial_data"
        ]
        legacy_helpers = [
            helper for helper in catalog_entry.helper_functions if helper == "get_stock_financial_data"
        ]
        if legacy_sources or legacy_helpers:
            legacy_source_refs.append(
                {
                    "field": field_name,
                    "legacy_sources": legacy_sources,
                    "legacy_helpers": legacy_helpers,
                }
            )

    return {"legacy_source_refs": legacy_source_refs}


def validate_factor_catalog_runtime_semantic_alignment() -> Dict[str, List[Dict[str, object]]]:
    """校验 P0 schema 字段与 runtime semantic contract / catalog 的一致性。

    Returns:
        dict: 字段说明——
            missing_contract_entries: list[dict]，schema 已登记但 runtime semantic contract
                未登记的字段，元素字段：
                — field: 字段名
                — reason: 缺失原因说明
            mismatches: list[dict]，contract 文本片段在 catalog 中缺失的条目，元素字段：
                — field: 字段名
                — missing_direct_fields: list[str]，catalog.required_fields 中缺失的 contract.direct_fields 片段
                — missing_fallback_chain: list[str]，catalog.fallback_rules 中缺失的 contract.fallback_chain 片段
                — missing_denominator_guards: list[str]，catalog.warnings 中缺失的 contract.denominator_guards 片段
                — missing_unit_conversions: list[str]，catalog.warnings 中缺失的 contract.unit_conversions 片段
                — missing_conservative_proxies: list[str]，catalog.warnings 中缺失的 contract.conservative_proxies 片段
                — missing_availability_constraints: list[str]，catalog.warnings 中缺失的 contract.availability_constraints 片段
    """
    missing_contract_entries: List[Dict[str, object]] = []
    mismatches: List[Dict[str, object]] = []

    for field_name in P0_FACTOR_FIELD_SCHEMA.keys():
        if field_name not in FACTOR_RUNTIME_SEMANTIC_CONTRACTS:
            missing_contract_entries.append(
                {
                    "field": field_name,
                    "reason": "schema 已登记该字段，但 runtime semantic contract 尚未登记。",
                }
            )

    for field_name in P0_FACTOR_FIELD_SCHEMA.keys():
        contract = FACTOR_RUNTIME_SEMANTIC_CONTRACTS.get(field_name)
        if contract is None:
            continue
        catalog_entry = COMMON_FACTOR_CATALOG.get(field_name)
        if catalog_entry is None:
            mismatches.append(
                {
                    "field": field_name,
                    "missing_entry": True,
                }
            )
            continue

        missing_direct_fields = _missing_text_fragments(catalog_entry.required_fields, contract.direct_fields)
        missing_fallback_chain = _missing_text_fragments(catalog_entry.fallback_rules, contract.fallback_chain)
        missing_denominator_guards = _missing_text_fragments(catalog_entry.warnings, contract.denominator_guards)
        missing_unit_conversions = _missing_text_fragments(catalog_entry.warnings, contract.unit_conversions)
        missing_conservative_proxies = _missing_text_fragments(catalog_entry.warnings, contract.conservative_proxies)
        missing_availability_constraints = _missing_text_fragments(catalog_entry.warnings, contract.availability_constraints)

        if (
            missing_direct_fields
            or missing_fallback_chain
            or missing_denominator_guards
            or missing_unit_conversions
            or missing_conservative_proxies
            or missing_availability_constraints
        ):
            mismatches.append(
                {
                    "field": field_name,
                    "missing_direct_fields": missing_direct_fields,
                    "missing_fallback_chain": missing_fallback_chain,
                    "missing_denominator_guards": missing_denominator_guards,
                    "missing_unit_conversions": missing_unit_conversions,
                    "missing_conservative_proxies": missing_conservative_proxies,
                    "missing_availability_constraints": missing_availability_constraints,
                }
            )

    return {
        "missing_contract_entries": missing_contract_entries,
        "mismatches": mismatches,
    }


def validate_technical_factor_catalog_runtime_semantic_alignment() -> Dict[str, List[Dict[str, object]]]:
    """校验技术因子 schema 字段与 runtime semantic contract / catalog 的一致性。

    Returns:
        dict: 字段说明——
            missing_contract_entries: list[dict]，technical schema 已登记但 contract 未登记的字段，元素字段：
                — field: 字段名
                — reason: 缺失原因说明
            mismatches: list[dict]，contract 文本片段在 catalog 中缺失的条目，元素字段：
                — field: 字段名
                — missing_direct_fields: list[str]，catalog.required_fields 中缺失的 contract.direct_fields 片段
                — missing_availability_constraints: list[str]，catalog.warnings 中缺失的 contract.availability_constraints 片段
    """
    missing_contract_entries: List[Dict[str, object]] = []
    mismatches: List[Dict[str, object]] = []

    for field_name in TECHNICAL_FACTOR_FIELD_SCHEMA.keys():
        if field_name not in FACTOR_RUNTIME_SEMANTIC_CONTRACTS:
            missing_contract_entries.append(
                {
                    "field": field_name,
                    "reason": "technical schema 已登记该字段，但 runtime semantic contract 尚未登记。",
                }
            )

    for field_name in TECHNICAL_FACTOR_FIELD_SCHEMA.keys():
        contract = FACTOR_RUNTIME_SEMANTIC_CONTRACTS.get(field_name)
        catalog_entry = COMMON_FACTOR_CATALOG.get(field_name)
        if contract is None or catalog_entry is None:
            continue

        missing_direct_fields = _missing_text_fragments(catalog_entry.required_fields, contract.direct_fields)
        missing_availability_constraints = _missing_text_fragments(catalog_entry.warnings, contract.availability_constraints)
        if missing_direct_fields or missing_availability_constraints:
            mismatches.append(
                {
                    "field": field_name,
                    "missing_direct_fields": missing_direct_fields,
                    "missing_availability_constraints": missing_availability_constraints,
                }
            )

    return {
        "missing_contract_entries": missing_contract_entries,
        "mismatches": mismatches,
    }


def validate_factor_schema_semantic_alignment() -> Dict[str, List[Dict[str, object]]]:
    """校验 P0 factor schema 与 runtime semantic contract 在 source_priority /
    minimum_input_groups / minimum_computable_conditions / warning 等维度的一致性。

    Returns:
        dict: 字段说明——
            missing_schema_fields: list[dict]，contract 已登记但 schema 未登记的字段，元素字段：
                — field: 字段名
                — reason: 缺失原因说明
            missing_source_priority_entries: list[dict]，任一侧 source_priority 缺失的字段，元素字段：
                — field: 字段名
                — schema_source_priority: list[str]
                — contract_source_priority: list[str]
            missing_minimum_input_group_entries: list[dict]，任一侧 minimum_input_groups 缺失的字段，元素字段：
                — field: 字段名
                — schema_minimum_input_groups: list[list[str]]
                — contract_minimum_input_groups: list[list[str]]
            missing_minimum_computable_condition_entries: list[dict]，需要可计算条件但任一侧缺失的字段，元素字段：
                — field: 字段名
                — schema_minimum_computable_conditions: list[str]
                — contract_minimum_computable_conditions: list[str]
            missing_warning_condition_entries: list[dict]，需要 warning 条件但任一侧缺失的字段，元素字段：
                — field: 字段名
                — schema_warning_conditions: list[str]
                — contract_warning_conditions: list[str]
            missing_warning_category_entries: list[dict]，需要 warning 类别但任一侧缺失的字段，元素字段：
                — field: 字段名
                — schema_warning_categories: list[str]
                — contract_warning_categories: list[str]
            mismatches: list[dict]，schema 与 contract 各维度不一致条目，元素字段：
                — field: 字段名
                — missing_semantic_tags: list[str]，缺失的语义标签
                — schema_source_priority / contract_source_priority: list[str]
                — source_priority_mismatch: bool
                — schema_tax_estimation_strategy / contract_tax_estimation_strategy: str
                — tax_estimation_strategy_mismatch: bool
                — schema_period_selection_strategy / contract_period_selection_strategy: str
                — period_selection_strategy_mismatch: bool
                — schema_minimum_input_groups / contract_minimum_input_groups: list[list[str]]
                — minimum_input_groups_mismatch: bool
                — schema_minimum_computable_conditions / contract_minimum_computable_conditions: list[str]
                — minimum_computable_conditions_mismatch: bool
                — schema_warning_conditions / contract_warning_conditions: list[str]
                — warning_conditions_mismatch: bool
                — schema_warning_categories / contract_warning_categories: list[str]
                — warning_categories_mismatch: bool
                — schema_calculation_mode: str
                — requires_non_direct_mode: bool，是否要求非 direct 计算模式
    """
    missing_schema_fields: List[Dict[str, object]] = []
    missing_source_priority_entries: List[Dict[str, object]] = []
    missing_minimum_input_group_entries: List[Dict[str, object]] = []
    missing_minimum_computable_condition_entries: List[Dict[str, object]] = []
    missing_warning_condition_entries: List[Dict[str, object]] = []
    missing_warning_category_entries: List[Dict[str, object]] = []
    mismatches: List[Dict[str, object]] = []

    for field_name in P0_FACTOR_FIELD_SCHEMA.keys():
        contract = FACTOR_RUNTIME_SEMANTIC_CONTRACTS.get(field_name)
        if contract is None:
            continue
        schema = P0_FACTOR_FIELD_SCHEMA.get(field_name)
        if schema is None:
            missing_schema_fields.append(
                {
                    "field": field_name,
                    "reason": "runtime semantic contract 已登记，但 factor_schema 尚无该字段。",
                }
            )
            continue

        if not schema.source_priority or not contract.source_priority:
            missing_source_priority_entries.append(
                {
                    "field": field_name,
                    "schema_source_priority": list(schema.source_priority or []),
                    "contract_source_priority": list(contract.source_priority or []),
                }
            )

        if not schema.minimum_input_groups or not contract.minimum_input_groups:
            missing_minimum_input_group_entries.append(
                {
                    "field": field_name,
                    "schema_minimum_input_groups": list(schema.minimum_input_groups or []),
                    "contract_minimum_input_groups": list(contract.minimum_input_groups or []),
                }
            )

        requires_minimum_computable_conditions = any(
            [
                schema.data_quality_tier == "cautious",
                schema.period_selection_strategy in {"same_period_last_year", "same_period_n_years_3", "previous_available_period"},
                bool(contract.denominator_guards),
            ]
        )
        if requires_minimum_computable_conditions and (
            not schema.minimum_computable_conditions or not contract.minimum_computable_conditions
        ):
            missing_minimum_computable_condition_entries.append(
                {
                    "field": field_name,
                    "schema_minimum_computable_conditions": list(schema.minimum_computable_conditions or []),
                    "contract_minimum_computable_conditions": list(contract.minimum_computable_conditions or []),
                }
            )

        requires_warning_conditions = any(
            [
                schema.calculation_mode == "fallback",
                bool(contract.conservative_proxies),
                bool(contract.warning_conditions),
            ]
        )
        if requires_warning_conditions and (not schema.warning_conditions or not contract.warning_conditions):
            missing_warning_condition_entries.append(
                {
                    "field": field_name,
                    "schema_warning_conditions": list(schema.warning_conditions or []),
                    "contract_warning_conditions": list(contract.warning_conditions or []),
                }
            )

        if requires_warning_conditions and (not schema.warning_categories or not contract.warning_categories):
            missing_warning_category_entries.append(
                {
                    "field": field_name,
                    "schema_warning_categories": list(schema.warning_categories or []),
                    "contract_warning_categories": list(contract.warning_categories or []),
                }
            )

        schema_tags = set(schema.semantic_tags or [])
        missing_tags: List[str] = []
        for contract_attr, schema_tag in SCHEMA_TAG_BY_CONTRACT_CATEGORY.items():
            if getattr(contract, contract_attr) and schema_tag not in schema_tags:
                missing_tags.append(schema_tag)

        source_priority_mismatch = list(schema.source_priority or []) != list(contract.source_priority or [])
        tax_estimation_strategy_mismatch = schema.tax_estimation_strategy != contract.tax_estimation_strategy
        period_selection_strategy_mismatch = schema.period_selection_strategy != contract.period_selection_strategy
        minimum_input_groups_mismatch = list(schema.minimum_input_groups or []) != list(contract.minimum_input_groups or [])
        minimum_computable_conditions_mismatch = list(schema.minimum_computable_conditions or []) != list(contract.minimum_computable_conditions or [])
        warning_conditions_mismatch = list(schema.warning_conditions or []) != list(contract.warning_conditions or [])
        warning_categories_mismatch = list(schema.warning_categories or []) != list(contract.warning_categories or [])

        expected_direct_mode = any(
            [
                contract.fallback_chain,
                contract.denominator_guards,
                contract.unit_conversions,
                contract.conservative_proxies,
                contract.availability_constraints,
            ]
        )
        calculation_mode_mismatch = expected_direct_mode and schema.calculation_mode == "direct"

        if missing_tags or calculation_mode_mismatch or tax_estimation_strategy_mismatch or period_selection_strategy_mismatch or minimum_input_groups_mismatch or minimum_computable_conditions_mismatch or warning_conditions_mismatch or warning_categories_mismatch:
            mismatches.append(
                {
                    "field": field_name,
                    "missing_semantic_tags": missing_tags,
                    "schema_source_priority": list(schema.source_priority or []),
                    "contract_source_priority": list(contract.source_priority or []),
                    "source_priority_mismatch": source_priority_mismatch,
                    "schema_tax_estimation_strategy": schema.tax_estimation_strategy,
                    "contract_tax_estimation_strategy": contract.tax_estimation_strategy,
                    "tax_estimation_strategy_mismatch": tax_estimation_strategy_mismatch,
                    "schema_period_selection_strategy": schema.period_selection_strategy,
                    "contract_period_selection_strategy": contract.period_selection_strategy,
                    "period_selection_strategy_mismatch": period_selection_strategy_mismatch,
                    "schema_minimum_input_groups": list(schema.minimum_input_groups or []),
                    "contract_minimum_input_groups": list(contract.minimum_input_groups or []),
                    "minimum_input_groups_mismatch": minimum_input_groups_mismatch,
                    "schema_minimum_computable_conditions": list(schema.minimum_computable_conditions or []),
                    "contract_minimum_computable_conditions": list(contract.minimum_computable_conditions or []),
                    "minimum_computable_conditions_mismatch": minimum_computable_conditions_mismatch,
                    "schema_warning_conditions": list(schema.warning_conditions or []),
                    "contract_warning_conditions": list(contract.warning_conditions or []),
                    "warning_conditions_mismatch": warning_conditions_mismatch,
                    "schema_warning_categories": list(schema.warning_categories or []),
                    "contract_warning_categories": list(contract.warning_categories or []),
                    "warning_categories_mismatch": warning_categories_mismatch,
                    "schema_calculation_mode": schema.calculation_mode,
                    "requires_non_direct_mode": calculation_mode_mismatch,
                }
            )

        elif source_priority_mismatch:
            mismatches.append(
                {
                    "field": field_name,
                    "missing_semantic_tags": [],
                    "schema_source_priority": list(schema.source_priority or []),
                    "contract_source_priority": list(contract.source_priority or []),
                    "source_priority_mismatch": True,
                    "schema_tax_estimation_strategy": schema.tax_estimation_strategy,
                    "contract_tax_estimation_strategy": contract.tax_estimation_strategy,
                    "tax_estimation_strategy_mismatch": False,
                    "schema_period_selection_strategy": schema.period_selection_strategy,
                    "contract_period_selection_strategy": contract.period_selection_strategy,
                    "period_selection_strategy_mismatch": False,
                    "schema_minimum_input_groups": list(schema.minimum_input_groups or []),
                    "contract_minimum_input_groups": list(contract.minimum_input_groups or []),
                    "minimum_input_groups_mismatch": False,
                    "schema_minimum_computable_conditions": list(schema.minimum_computable_conditions or []),
                    "contract_minimum_computable_conditions": list(contract.minimum_computable_conditions or []),
                    "minimum_computable_conditions_mismatch": False,
                    "schema_warning_conditions": list(schema.warning_conditions or []),
                    "contract_warning_conditions": list(contract.warning_conditions or []),
                    "warning_conditions_mismatch": False,
                    "schema_warning_categories": list(schema.warning_categories or []),
                    "contract_warning_categories": list(contract.warning_categories or []),
                    "warning_categories_mismatch": False,
                    "schema_calculation_mode": schema.calculation_mode,
                    "requires_non_direct_mode": False,
                }
            )

    return {
        "missing_schema_fields": missing_schema_fields,
        "missing_source_priority_entries": missing_source_priority_entries,
        "missing_minimum_input_group_entries": missing_minimum_input_group_entries,
        "missing_minimum_computable_condition_entries": missing_minimum_computable_condition_entries,
        "missing_warning_condition_entries": missing_warning_condition_entries,
        "missing_warning_category_entries": missing_warning_category_entries,
        "mismatches": mismatches,
    }


def validate_technical_factor_schema_semantic_alignment() -> Dict[str, List[Dict[str, object]]]:
    """校验技术因子 schema 与 runtime semantic contract 在 source_priority /
    minimum_input_groups / minimum_computable_conditions 维度的一致性。

    Returns:
        dict: 字段说明——
            missing_schema_fields: list[dict]，technical schema 字段未登记 contract 的条目，元素字段：
                — field: 字段名
                — reason: 缺失原因说明
            missing_source_priority_entries: list[dict]，任一侧 source_priority 缺失的字段，元素字段：
                — field: 字段名
                — schema_source_priority: list[str]
                — contract_source_priority: list[str]
            missing_minimum_input_group_entries: list[dict]，任一侧 minimum_input_groups 缺失的字段，元素字段：
                — field: 字段名
                — schema_minimum_input_groups: list[list[str]]
                — contract_minimum_input_groups: list[list[str]]
            missing_minimum_computable_condition_entries: list[dict]，任一侧 minimum_computable_conditions 缺失的字段，元素字段：
                — field: 字段名
                — schema_minimum_computable_conditions: list[str]
                — contract_minimum_computable_conditions: list[str]
            mismatches: list[dict]，schema 与 contract 不一致条目，元素字段：
                — field: 字段名
                — schema_source_priority: list[str]
                — contract_source_priority: list[str]
                — schema_minimum_input_groups: list[list[str]]
                — contract_minimum_input_groups: list[list[str]]
                — schema_minimum_computable_conditions: list[str]
                — contract_minimum_computable_conditions: list[str]
    """
    missing_schema_fields: List[Dict[str, object]] = []
    missing_source_priority_entries: List[Dict[str, object]] = []
    missing_minimum_input_group_entries: List[Dict[str, object]] = []
    missing_minimum_computable_condition_entries: List[Dict[str, object]] = []
    mismatches: List[Dict[str, object]] = []

    for field_name, schema in TECHNICAL_FACTOR_FIELD_SCHEMA.items():
        contract = FACTOR_RUNTIME_SEMANTIC_CONTRACTS.get(field_name)
        if contract is None:
            missing_schema_fields.append(
                {
                    "field": field_name,
                    "reason": "technical runtime semantic contract 尚未登记。",
                }
            )
            continue

        if not schema.source_priority or not contract.source_priority:
            missing_source_priority_entries.append(
                {
                    "field": field_name,
                    "schema_source_priority": list(schema.source_priority or []),
                    "contract_source_priority": list(contract.source_priority or []),
                }
            )

        if not schema.minimum_input_groups or not contract.minimum_input_groups:
            missing_minimum_input_group_entries.append(
                {
                    "field": field_name,
                    "schema_minimum_input_groups": list(schema.minimum_input_groups or []),
                    "contract_minimum_input_groups": list(contract.minimum_input_groups or []),
                }
            )

        if not schema.minimum_computable_conditions or not contract.minimum_computable_conditions:
            missing_minimum_computable_condition_entries.append(
                {
                    "field": field_name,
                    "schema_minimum_computable_conditions": list(schema.minimum_computable_conditions or []),
                    "contract_minimum_computable_conditions": list(contract.minimum_computable_conditions or []),
                }
            )

        if (
            list(schema.source_priority or []) != list(contract.source_priority or [])
            or list(schema.minimum_input_groups or []) != list(contract.minimum_input_groups or [])
            or list(schema.minimum_computable_conditions or []) != list(contract.minimum_computable_conditions or [])
        ):
            mismatches.append(
                {
                    "field": field_name,
                    "schema_source_priority": list(schema.source_priority or []),
                    "contract_source_priority": list(contract.source_priority or []),
                    "schema_minimum_input_groups": list(schema.minimum_input_groups or []),
                    "contract_minimum_input_groups": list(contract.minimum_input_groups or []),
                    "schema_minimum_computable_conditions": list(schema.minimum_computable_conditions or []),
                    "contract_minimum_computable_conditions": list(contract.minimum_computable_conditions or []),
                }
            )

    return {
        "missing_schema_fields": missing_schema_fields,
        "missing_source_priority_entries": missing_source_priority_entries,
        "missing_minimum_input_group_entries": missing_minimum_input_group_entries,
        "missing_minimum_computable_condition_entries": missing_minimum_computable_condition_entries,
        "mismatches": mismatches,
    }


__all__ = [
    "COMMON_FACTOR_CATALOG",
    "FACTOR_RUNTIME_SEMANTIC_CONTRACTS",
    "P0_BUNDLE_FACTOR_PACKS",
    "RECOMMENDED_FACTOR_PACKS",
    "FactorDefinition",
    "RuntimeSemanticContract",
    "build_factor_implementation_outline",
    "validate_factor_catalog_schema_alignment",
    "validate_factor_catalog_runtime_semantic_alignment",
    "validate_technical_factor_catalog_schema_alignment",
    "validate_technical_factor_catalog_runtime_semantic_alignment",
    "validate_factor_schema_semantic_alignment",
    "validate_technical_factor_schema_semantic_alignment",
    "validate_factor_catalog_source_alignment",
    "validate_factor_pack_schema_alignment",
    "get_factor_definition",
    "get_factor_pack",
    "list_factor_definitions",
]