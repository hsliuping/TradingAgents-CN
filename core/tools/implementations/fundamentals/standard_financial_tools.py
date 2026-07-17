"""标准金融数据能力工具。

这些工具封装 core.skill_runtime.standard_financial_apis，向 Agent 暴露结构化、可审计的常用股票分析数据能力。
"""

import json
import logging
from typing import Annotated, Optional

from langchain_core.tools import tool

from core.skill_runtime.standard_financial_apis import (
    get_adjusted_price_series,
    get_capital_efficiency_trend,
    get_capital_flow_series,
    get_cashflow_quality_trend,
    get_chip_distribution_context,
    get_company_announcements,
    get_company_event_timeline,
    get_current_valuation_snapshot,
    get_debt_solvency_trend,
    get_drawdown_metrics,
    get_growth_quality_metrics,
    get_historical_financial_annual_series,
    get_historical_valuation_percentile,
    get_industry_fundamental_summary,
    get_industry_market_performance,
    get_business_segment_trend,
    get_margin_stability_metrics,
    get_peer_group,
    get_peer_relative_growth,
    get_peer_relative_quality,
    get_peer_relative_valuation,
    get_pledge_historical_series,
    get_pledge_risk_profile,
    get_portfolio_risk_profile,
    get_profitability_stability_metrics,
    get_return_series,
    get_risk_event_flags,
    get_security_master,
    get_shareholder_return_metrics,
    get_single_stock_risk_profile,
    get_technical_indicator_series,
    get_volatility_metrics,
)
from core.tools.base import register_tool

logger = logging.getLogger(__name__)


def _json_response(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def _parse_metrics(metrics: Optional[str]) -> list[str] | None:
    if not metrics:
        return None
    items = [item.strip().lower() for item in str(metrics).replace("，", ",").split(",") if item.strip()]
    return items or None


def _parse_positions(positions_json: str) -> list[dict]:
    data = json.loads(positions_json or "[]")
    if isinstance(data, dict):
        data = data.get("positions") or []
    if not isinstance(data, list):
        raise ValueError("positions_json 必须是持仓数组或包含 positions 字段的 JSON 对象")
    return [item for item in data if isinstance(item, dict)]


@tool
@register_tool(
    tool_id="get_company_event_timeline_tool",
    name="公司公告监管事件时间线",
    description="结构化返回正式公告/监管事件时间线；本地公告数据优先，缺失时使用新闻代理识别事件。",
    category="news",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    when_to_use="当需要正式公告、监管函、处罚、减持、质押、诉讼、分红公告等事件时间线时使用。",
    when_not_to_use="不适合实时新闻流监控（请使用 get_stock_news）；不适合非正式/社交媒体传闻；不适合定量事件研究（请使用 get_event_study）。",
    capability_tags=["event", "announcement", "regulatory"],
    tool_role_hint="specialized",
    returns="返回 JSON 字符串，包含 events、summary、coverage、warnings。",
    example="get_company_event_timeline_tool(symbol='600519', lookback_days=365)",
    related_tools=["get_risk_event_flags_tool", "get_company_announcements_tool", "get_event_study", "get_stock_news"],
)
def get_company_event_timeline_tool(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"],
    lookback_days: Annotated[int, "回看天数，默认365"] = 365,
    event_types: Annotated[str, "逗号分隔事件类型，可为空"] = "",
    limit: Annotated[int, "最多返回事件数，默认100"] = 100,
) -> str:
    """获取公司公告/监管事件时间线。

    Args:
        symbol: A 股股票代码，如 600519、000001
        lookback_days: 回看天数，默认365
        event_types: 逗号分隔事件类型，可为空
        limit: 最多返回事件数，默认100

    Returns:
        str: JSON 字符串。解析后的字段结构同
            ``core.skill_runtime.standard_financial_apis.get_company_event_timeline`` 的 Returns ——
            status, symbol, window, data_source, events, summary(event_count/type_counts/high_severity_count),
            warnings
    """
    try:
        return _json_response(get_company_event_timeline(symbol, lookback_days=lookback_days, event_types=_parse_metrics(event_types), limit=limit))
    except Exception as exc:
        logger.error("公司公告监管事件时间线获取失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"公司公告监管事件时间线获取失败: {exc}"})


@tool
@register_tool(
    tool_id="get_business_segment_trend_tool",
    name="主营结构趋势",
    description="结构化返回主营业务分部收入、毛利、毛利率、收入占比、Top1/Top3 集中度和 HHI 趋势。",
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=[
        "business_segment", "segment_revenue", "segment_margin", "revenue_mix",
        "product_mix", "regional_mix", "gross_margin", "segment_gross_margin",
        "concentration", "hhi", "top1_concentration", "top3_concentration",
        "business_structure", "revenue_composition", "diversification",
        "moat_analysis", "competitive_advantage", "time_series",
    ],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=[
        "business_segment_analysis", "revenue_mix_trend", "concentration_analysis",
        "product_mix_analysis", "regional_mix_analysis", "diversification_assessment",
        "moat_analysis",
    ],
    when_to_use="当需要分析主营业务结构、产品/地区收入占比变化、业务集中度和毛利率结构时使用。",
    returns="返回 JSON 字符串，包含 periods、concentration、coverage、warnings。",
    example="get_business_segment_trend_tool(symbol='600519', years=5, segment_type='product')",
)
def get_business_segment_trend_tool(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"],
    years: Annotated[int, "年数，默认5"] = 5,
    segment_type: Annotated[str, "分部类型，如 product/region/all"] = "product",
) -> str:
    """获取主营结构趋势。

    Args:
        symbol: A 股股票代码，如 600519、000001
        years: 年数，默认5
        segment_type: 分部类型，如 product/region/all

    Returns:
        str: JSON 字符串。解析后的字段结构同
            ``core.skill_runtime.standard_financial_apis.get_business_segment_trend`` 的 Returns ——
            status, symbol, segment_type, periods, coverage(period_count/raw_segment_count), warnings
    """
    try:
        return _json_response(get_business_segment_trend(symbol, years=years, segment_type=segment_type))
    except Exception as exc:
        logger.error("主营结构趋势获取失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"主营结构趋势获取失败: {exc}"})


@tool
@register_tool(
    tool_id="get_shareholder_return_metrics_tool",
    name="股东回报指标",
    description="结构化返回分红记录、每股现金分红、股息率、分红连续性和自由现金流覆盖上下文。",
    category="fundamentals",
    is_online=True,
    auto_register=True,
    timeout_tier="medium",
    capability_tags=[
        "shareholder_return", "dividend", "dividend_history", "cash_dividend",
        "dividend_yield", "dividend_continuity", "payout_ratio",
        "free_cashflow_coverage", "shareholder_value", "dividend_stability",
        "total_shareholder_return", "yield_analysis", "income_investing",
        "value_investing", "dividend_payout", "return_on_capital",
    ],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=[
        "dividend_analysis", "dividend_yield_assessment", "shareholder_return_analysis",
        "dividend_continuity_check", "free_cashflow_coverage_check",
        "income_investing", "value_investing",
    ],
    when_to_use="当需要分析分红、股息率、股东回报、红利稳定性或现金流覆盖时使用。",
    returns="返回 JSON 字符串，包含 records、annual、metrics、coverage、warnings。",
    example="get_shareholder_return_metrics_tool(symbol='600519', years=5)",
)
def get_shareholder_return_metrics_tool(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"],
    years: Annotated[int, "年数，默认5"] = 5,
) -> str:
    """获取股东回报指标。

    Args:
        symbol: A 股股票代码，如 600519、000001
        years: 年数，默认5

    Returns:
        str: JSON 字符串。解析后的字段结构同
            ``core.skill_runtime.standard_financial_apis.get_shareholder_return_metrics`` 的 Returns ——
            status, symbol, data_source, current_price, records, annual, metrics, coverage, warnings
    """
    try:
        return _json_response(get_shareholder_return_metrics(symbol, years=years))
    except Exception as exc:
        logger.error("股东回报指标获取失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"股东回报指标获取失败: {exc}"})


@tool
@register_tool(
    tool_id="get_portfolio_risk_profile_tool",
    name="组合风险画像",
    description="基于持仓 JSON 和价格收益序列返回组合波动率、最大回撤、VaR、CVaR、行业暴露和集中度。",
    category="assistant_ops",
    is_online=False,
    auto_register=True,
    timeout_tier="medium",
    when_to_use="当用户提供持仓并需要组合风险、集中度、行业暴露、VaR 或最大回撤时使用。",
    when_not_to_use="不适合单只股票风险分析（请使用 get_single_stock_risk_profile_tool）；不适合没有持仓数据的场景。",
    capability_tags=["portfolio", "risk_management", "var"],
    tool_role_hint="specialized",
    returns="返回 JSON 字符串，包含 positions、metrics、exposure、return_series、coverage、warnings。",
    example="get_portfolio_risk_profile_tool(positions_json='[{\"symbol\":\"600519\",\"market_value\":100000}]')",
    related_tools=["get_correlation_matrix", "get_single_stock_risk_profile_tool", "get_cointegration_test"],
)
def get_portfolio_risk_profile_tool(
    positions_json: Annotated[str, "持仓 JSON 数组，元素包含 symbol/code 与 market_value 或 quantity*price"],
    start_date: Annotated[Optional[str], "开始日期 YYYY-MM-DD，默认近一年"] = None,
    end_date: Annotated[Optional[str], "结束日期 YYYY-MM-DD，默认今天"] = None,
    limit: Annotated[int, "最多价格样本，默认300"] = 300,
) -> str:
    """获取组合风险画像。

    Args:
        positions_json: 持仓 JSON 数组，元素包含 symbol/code 与 market_value 或 quantity*price
        start_date: 开始日期 YYYY-MM-DD，默认近一年
        end_date: 结束日期 YYYY-MM-DD，默认今天
        limit: 最多价格样本，默认300

    Returns:
        str: JSON 字符串。解析后的字段结构同
            ``core.skill_runtime.standard_financial_apis.get_portfolio_risk_profile`` 的 Returns ——
            status, window, positions, metrics, exposure, return_series, coverage, warnings
    """
    try:
        return _json_response(get_portfolio_risk_profile(_parse_positions(positions_json), start_date=start_date, end_date=end_date, limit=limit))
    except Exception as exc:
        logger.error("组合风险画像获取失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"组合风险画像获取失败: {exc}"})


@tool
@register_tool(
    tool_id="get_technical_indicator_series_tool",
    name="技术指标历史序列",
    description=(
        "基于标准价格序列结构化计算 MA、MACD、RSI、KDJ、BOLL、ATR、OBV、支撑压力等历史指标。"
        "这里的“技术信号/趋势”指价格和成交量的技术面指标序列，不是财务风险信号、公告事件信号或 Agent 能力缺口。"
    ),
    category="technical",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    when_to_use="当需要技术指标历史序列、支撑压力、ATR/BOLL/OBV 或结构化技术面输入时使用，适合技术分析、量价指标和价格趋势判断。",
    when_not_to_use="不用于财务风险、现金流风险、公告事件信号、基本面质量或 Agent 工坊能力缺口分析。如果只需要当前值（非历史序列），应使用 get_technical_factor_bundle_tool；如果需要可读文本分析报告，应使用 get_technical_indicators。",
    capability_tags=["technical_indicators", "historical_series", "structured_data", "ma", "macd", "rsi", "kdj", "boll", "atr", "obv"],
    tool_role_hint="supporting",
    preferred_for=["技术指标历史序列", "回测数据准备", "结构化技术面输入"],
    returns="返回 JSON 字符串，包含 records、latest、summary、coverage、warnings。",
    example="get_technical_indicator_series_tool(symbol='600519', start_date='2024-01-01', end_date='2024-12-31')",
    related_tools=["get_technical_factor_bundle_tool", "get_technical_indicators", "get_adjusted_price_series_tool"],
)
def get_technical_indicator_series_tool(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"],
    start_date: Annotated[Optional[str], "开始日期 YYYY-MM-DD，默认近一年"] = None,
    end_date: Annotated[Optional[str], "结束日期 YYYY-MM-DD，默认今天"] = None,
    indicators: Annotated[str, "逗号分隔指标，如 ma,macd,rsi,kdj,boll,atr,obv,support_resistance"] = "ma,macd,rsi,kdj,boll,atr,obv,support_resistance",
    limit: Annotated[int, "最多返回条数，默认300"] = 300,
) -> str:
    """获取技术指标历史序列。

    Args:
        symbol: A 股股票代码，如 600519、000001
        start_date: 开始日期 YYYY-MM-DD，默认近一年
        end_date: 结束日期 YYYY-MM-DD，默认今天
        indicators: 逗号分隔指标，如 ma,macd,rsi,kdj,boll,atr,obv,support_resistance
        limit: 最多返回条数，默认300

    Returns:
        str: JSON 字符串。解析后的字段结构同
            ``core.skill_runtime.standard_financial_apis.get_technical_indicator_series`` 的 Returns ——
            status, symbol, window, data_source, indicators, records, latest, summary, warnings
    """
    try:
        return _json_response(get_technical_indicator_series(symbol, start_date=start_date, end_date=end_date, indicators=_parse_metrics(indicators), limit=limit))
    except Exception as exc:
        logger.error("技术指标历史序列获取失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"技术指标历史序列获取失败: {exc}"})


@tool
@register_tool(
    tool_id="get_industry_market_performance_tool",
    name="行业市场表现",
    description="结构化返回目标股票所在行业的同行涨跌、行业收益、涨跌家数比例、成交额和行业资金流上下文。",
    category="market",
    is_online=True,
    auto_register=True,
    timeout_tier="medium",
    capability_tags=[
        "industry_performance", "industry_returns", "peer_performance",
        "market_breadth", "advance_decline", "industry_rotation",
        "industry_moneyflow", "sector_performance", "top_gainers", "top_losers",
        "industry_relative", "market_heat", "sector_rotation",
        "peer_comparison", "industry_trend",
    ],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=[
        "industry_performance_analysis", "sector_rotation_analysis",
        "industry_relative_performance", "market_breadth_check",
        "industry_moneyflow_analysis", "peer_performance_comparison",
    ],
    when_to_use="当需要行业涨跌、行业轮动、行业资金流、目标股票相对行业表现时使用。",
    returns="返回 JSON 字符串，包含 summary、top_gainers、top_losers、moneyflow、coverage、warnings。",
    example="get_industry_market_performance_tool(symbol='600519', lookback_days=20, peer_limit=50)",
)
def get_industry_market_performance_tool(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"],
    start_date: Annotated[Optional[str], "开始日期 YYYY-MM-DD，可为空"] = None,
    end_date: Annotated[Optional[str], "结束日期 YYYY-MM-DD，默认今天"] = None,
    lookback_days: Annotated[int, "回看天数，默认20"] = 20,
    peer_limit: Annotated[int, "同行样本上限，默认100"] = 100,
) -> str:
    """获取行业市场表现。

    Args:
        symbol: A 股股票代码，如 600519、000001
        start_date: 开始日期 YYYY-MM-DD，可为空
        end_date: 结束日期 YYYY-MM-DD，默认今天
        lookback_days: 回看天数，默认20
        peer_limit: 同行样本上限，默认100

    Returns:
        str: JSON 字符串。解析后的字段结构同
            ``core.skill_runtime.standard_financial_apis.get_industry_market_performance`` 的 Returns ——
            status, symbol, industry, window, summary, top_gainers, top_losers, moneyflow,
            coverage, warnings
    """
    try:
        return _json_response(get_industry_market_performance(symbol, start_date=start_date, end_date=end_date, lookback_days=lookback_days, peer_limit=peer_limit))
    except Exception as exc:
        logger.error("行业市场表现获取失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"行业市场表现获取失败: {exc}"})


@tool
@register_tool(
    tool_id="get_peer_relative_growth_tool",
    name="同业成长分位",
    description="结构化返回营收、净利润、经营现金流、自由现金流 CAGR 相对同行样本的分位。",
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="medium",
    capability_tags=[
        "peer_comparison", "peer_growth", "industry_growth", "growth_percentile",
        "revenue_cagr", "net_profit_cagr", "operating_cashflow_cagr", "free_cashflow_cagr",
        "growth_benchmarking", "peer_relative", "same_industry_growth",
        "moat_analysis", "competitive_advantage",
    ],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=[
        "peer_growth_comparison", "industry_growth_percentile", "growth_benchmarking",
        "revenue_growth_peer_ranking", "profit_growth_peer_ranking",
        "moat_analysis", "competitive_advantage_assessment",
    ],
    when_to_use="当需要判断成长性在同行中的相对位置、成长质量横向比较时使用。",
    returns="返回 JSON 字符串，包含 metrics、samples、coverage、warnings。",
    example="get_peer_relative_growth_tool(symbol='600519', metrics='revenue_cagr,net_profit_cagr', years=5)",
)
def get_peer_relative_growth_tool(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"],
    metrics: Annotated[str, "逗号分隔指标，如 revenue_cagr,net_profit_cagr,operating_cashflow_cagr,free_cashflow_cagr"] = "revenue_cagr,net_profit_cagr,operating_cashflow_cagr,free_cashflow_cagr",
    years: Annotated[int, "年报年数，默认5，最大15"] = 5,
    peer_limit: Annotated[int, "同行样本上限，默认50"] = 50,
) -> str:
    """获取同业成长分位。

    Args:
        symbol: A 股股票代码，如 600519、000001
        metrics: 逗号分隔指标，如 revenue_cagr,net_profit_cagr,operating_cashflow_cagr,free_cashflow_cagr
        years: 年报年数，默认5，最大15
        peer_limit: 同行样本上限，默认50

    Returns:
        str: JSON 字符串。解析后的字段结构同
            ``core.skill_runtime.standard_financial_apis.get_peer_relative_growth`` 的 Returns ——
            status, symbol, industry, years, metrics, samples, coverage, warnings
    """
    try:
        return _json_response(get_peer_relative_growth(symbol, metrics=_parse_metrics(metrics), years=years, peer_limit=peer_limit))
    except Exception as exc:
        logger.error("同业成长分位获取失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"同业成长分位获取失败: {exc}"})


@tool
@register_tool(
    tool_id="get_historical_financial_annual_series_tool",
    name="历史年报财务序列",
    description=(
        "结构化返回单只 A 股最近 N 年年报财务序列。"
        "适合长期财务质量、盈利稳定性、现金流质量等场景，"
        "避免从 get_income_analysis 的 Markdown 和混合季度序列中抠数。"
    ),
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=[
        "historical_financials", "annual_series", "multi_year_financials",
        "financial_trend", "long_term_financials",
        "gross_margin", "gross_margin_trend", "operating_margin", "operating_margin_trend",
        "netprofit_margin", "profitability_trend",
        "revenue", "revenue_trend", "net_profit", "profit_trend",
        "roe", "roe_trend", "roa", "roic", "return_on_equity",
        "operating_cashflow", "free_cashflow", "cashflow_trend",
        "total_assets", "total_equity", "debt_to_assets", "balance_sheet",
        "moat_analysis", "competitive_advantage",
    ],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=[
        "historical_financial_trend_analysis", "gross_margin_trend", "operating_margin_trend",
        "profitability_trend", "multi_year_financial_series", "revenue_trend",
        "moat_analysis", "competitive_advantage_assessment", "long_term_financial_quality",
    ],
    when_to_use=(
        "当 Agent/Skill 需要 5-10 年完整年报序列、营收/净利/ROE/经营现金流长期趋势、"
        "毛利率/营业利润率多年趋势、或需要结构化财务台账作为后续计算输入时优先使用。"
    ),
    when_not_to_use="如果只需要最近季度利润表文字摘要，可使用 get_income_analysis。",
    returns="返回 JSON 字符串，包含 records、coverage、warnings；records 为按年份倒序的结构化年报字段（含 gross_margin/operating_margin/netprofit_margin/roe/revenue/net_profit 等）。",
    example="get_historical_financial_annual_series_tool(symbol='600519', years=10)",
    related_tools=["get_profitability_stability_metrics_tool", "get_cashflow_quality_trend_tool", "get_income_analysis"],
)
def get_historical_financial_annual_series_tool(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"],
    years: Annotated[int, "年报年数，默认 10，最大 15"] = 10,
) -> str:
    """获取结构化历史年报财务序列。

    Args:
        symbol: A 股股票代码，如 600519、000001
        years: 年报年数，默认 10，最大 15

    Returns:
        str: JSON 字符串。解析后的字段结构同
            ``core.skill_runtime.standard_financial_apis.get_historical_financial_annual_series`` 的 Returns ——
            status, symbol, requested_years, records, coverage(requested_years/available_years/missing_years),
            warnings
    """
    try:
        return _json_response(get_historical_financial_annual_series(symbol, years=years))
    except Exception as exc:
        logger.error("历史年报财务序列获取失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"历史年报财务序列获取失败: {exc}"})


@tool
@register_tool(
    tool_id="get_profitability_stability_metrics_tool",
    name="盈利稳定性指标",
    description=(
        "基于历史年报序列计算营收、净利润、ROE、毛利率及同比增长的均值、中位数、波动率和变异系数。"
        "适合盈利稳定性、长期质量分析、营收波动性评估。"
    ),
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=[
        "profitability_stability", "financial_stability", "long_term_quality",
        "revenue_volatility", "revenue_stability", "revenue_fluctuation",
        "gross_margin_stability", "gross_margin_volatility",
        "roe_stability", "roe_persistence", "return_stability",
        "profit_volatility", "profit_stability",
        "coefficient_of_variation", "stddev", "growth_stability",
        "growth_volatility", "yoy_growth_stability",
        "moat_analysis", "competitive_advantage",
    ],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=[
        "profitability_stability_analysis", "revenue_volatility", "revenue_stability",
        "revenue_fluctuation_analysis", "gross_margin_stability", "roe_persistence",
        "moat_analysis", "competitive_advantage_assessment", "long_term_quality_analysis",
    ],
    when_to_use="当需要量化盈利稳定性、营收波动性、ROE/毛利率持续性、长期质量分析时使用。",
    when_not_to_use="不用于估值分位；估值分位请用 get_historical_valuation_percentile_tool。",
    returns="返回 JSON 字符串，包含 metrics(含 coefficient_of_variation)、trend_series(含 revenue_growth_yoy)、coverage、warnings。",
    example="get_profitability_stability_metrics_tool(symbol='600519', years=10)",
    related_tools=["get_historical_financial_annual_series_tool", "get_quality_factor_bundle_tool"],
)
def get_profitability_stability_metrics_tool(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"],
    years: Annotated[int, "年报年数，默认 10，最大 15"] = 10,
) -> str:
    """获取结构化盈利稳定性指标。

    Args:
        symbol: A 股股票代码，如 600519、000001
        years: 年报年数，默认 10，最大 15

    Returns:
        str: JSON 字符串。解析后的字段结构同
            ``core.skill_runtime.standard_financial_apis.get_profitability_stability_metrics`` 的 Returns ——
            status, symbol, years_used, coverage, metrics, trend_series, warnings
    """
    try:
        return _json_response(get_profitability_stability_metrics(symbol, years=years))
    except Exception as exc:
        logger.error("盈利稳定性指标获取失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"盈利稳定性指标获取失败: {exc}"})


@tool
@register_tool(
    tool_id="get_cashflow_quality_trend_tool",
    name="现金流质量趋势",
    description=(
        "基于历史年报序列计算经营现金流/净利润、自由现金流/净利润、经营现金流率、自由现金流率等趋势。"
        "适合判断利润含金量、现金流稳定性、自由现金流质量，以及经营现金流下滑、自由现金流长期为负等现金流恶化信号。"
    ),
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["cashflow_quality", "cashflow_deterioration", "earnings_quality", "free_cashflow", "operating_cashflow"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["cashflow_quality_analysis", "financial_risk_signal_detection", "earnings_quality_analysis"],
    when_to_use="当需要长期现金流质量、CFO/净利、FCF/净利、现金流率、经营现金流下滑、自由现金流长期为负等结构化指标时使用。",
    when_not_to_use="如果只需要现金流量表文字摘要，可使用 get_cashflow_analysis。",
    returns="返回 JSON 字符串，包含 trend、summary、coverage、warnings。",
    example="get_cashflow_quality_trend_tool(symbol='600519', years=10)",
    related_tools=["get_historical_financial_annual_series_tool", "get_growth_cashflow_factor_bundle_tool", "get_cashflow_analysis"],
)
def get_cashflow_quality_trend_tool(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"],
    years: Annotated[int, "年报年数，默认 10，最大 15"] = 10,
) -> str:
    """获取结构化现金流质量趋势。

    Args:
        symbol: A 股股票代码，如 600519、000001
        years: 年报年数，默认 10，最大 15

    Returns:
        str: JSON 字符串。解析后的字段结构同
            ``core.skill_runtime.standard_financial_apis.get_cashflow_quality_trend`` 的 Returns ——
            status, symbol, years_used, coverage, trend, summary, warnings
    """
    try:
        return _json_response(get_cashflow_quality_trend(symbol, years=years))
    except Exception as exc:
        logger.error("现金流质量趋势获取失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"现金流质量趋势获取失败: {exc}"})


@tool
@register_tool(
    tool_id="get_historical_valuation_percentile_tool",
    name="历史估值分位",
    description=(
        "结构化计算 PE_TTM、PB、PS_TTM、PCF_TTM 等历史估值分位，支持指定回看年数。"
        "用于替代 get_stock_fundamentals_unified 中隐藏的 3 年文本分位输出。"
    ),
    category="fundamentals",
    is_online=True,
    auto_register=True,
    timeout_tier="medium",
    capability_tags=[
        "valuation", "historical_valuation", "valuation_percentile",
        "pe_ttm", "pb", "ps_ttm", "pcf_ttm", "valuation_band",
        "valuation_range", "safety_margin", "valuation_channel",
        "historical_range", "percentile_rank", "valuation_analysis",
        "relative_valuation", "time_series", "valuation_metrics",
    ],
    tool_role_hint="primary",
    output_shape="structured_metrics",
    preferred_for=[
        "valuation_percentile", "historical_valuation_analysis",
        "valuation_band_analysis", "safety_margin_assessment",
        "pe_percentile", "pb_percentile", "ps_percentile",
        "valuation_channel_analysis",
    ],
    when_to_use="当需要历史 PE/PB/PS/PCF 分位、估值通道、安全边际或可审计估值分位数据时使用。",
    when_not_to_use="如果只需要当前 PE/PB 快照，可用 get_current_valuation_snapshot_tool 或 get_value_factor_bundle_tool。",
    returns="返回 JSON 字符串，包含 window、data_source、metrics、warnings；metrics 内含 current_value、median、percentile、sample_count。",
    example="get_historical_valuation_percentile_tool(symbol='600519', metrics='pe_ttm,pb,ps_ttm', lookback_years=5)",
    related_tools=["get_current_valuation_snapshot_tool", "get_value_factor_bundle_tool", "get_stock_fundamentals_unified"],
)
def get_historical_valuation_percentile_tool(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"],
    metrics: Annotated[str, "逗号分隔指标，如 pe_ttm,pb,ps_ttm,pcf_ttm"] = "pe_ttm,pb,ps_ttm",
    lookback_years: Annotated[int, "回看年数，默认 5，最大 15"] = 5,
    as_of_date: Annotated[Optional[str], "分析日期 YYYY-MM-DD，默认今天"] = None,
) -> str:
    """获取结构化历史估值分位。

    Args:
        symbol: A 股股票代码，如 600519、000001
        metrics: 逗号分隔指标，如 pe_ttm,pb,ps_ttm,pcf_ttm
        lookback_years: 回看年数，默认 5，最大 15
        as_of_date: 分析日期 YYYY-MM-DD，默认今天

    Returns:
        str: JSON 字符串。解析后的字段结构同
            ``core.skill_runtime.standard_financial_apis.get_historical_valuation_percentile`` 的 Returns ——
            status, symbol, window, data_source, metrics, warnings
    """
    try:
        return _json_response(
            get_historical_valuation_percentile(
                symbol,
                metrics=_parse_metrics(metrics),
                lookback_years=lookback_years,
                as_of_date=as_of_date,
            )
        )
    except Exception as exc:
        logger.error("历史估值分位获取失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"历史估值分位获取失败: {exc}"})


@tool
@register_tool(
    tool_id="get_security_master_tool",
    name="证券主数据",
    description="按股票代码或股票名称返回统一证券主数据，包括代码、名称、交易所、行业、上市状态、ST 标记、市值等。",
    category="market",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=[
        "security_master", "stock_metadata", "symbol_lookup", "stock_identity",
        "exchange_info", "listing_status", "industry_info", "market_cap",
        "st_flag", "basic_info", "security_info", "stock_basics",
        "ticker_lookup", "company_profile", "metadata",
    ],
    tool_role_hint="supporting",
    output_shape="structured_json",
    preferred_for=[
        "stock_identity_verification", "symbol_resolution", "basic_stock_info",
        "listing_status_check", "industry_lookup", "market_cap_lookup",
    ],
    when_to_use="当 Agent 需要确认股票身份、代码、名称、行业、交易所、上市状态、基础元数据时使用。支持输入股票代码或股票名称。",
    returns="返回 JSON 字符串，包含 query、symbol、name、exchange、industry、listing_status、coverage、warnings。",
    example="get_security_master_tool(symbol='600519') 或 get_security_master_tool(symbol='科大讯飞')",
)
def get_security_master_tool(symbol: Annotated[str, "A 股股票代码或股票名称，如 600519、科大讯飞、贵州茅台"]) -> str:
    """获取证券主数据。

    Args:
        symbol: A 股股票代码或股票名称，如 600519、科大讯飞、贵州茅台

    Returns:
        str: JSON 字符串。解析后的字段结构同
            ``core.skill_runtime.standard_financial_apis.get_security_master`` 的 Returns ——
            status, query, symbol, ts_code, name, exchange, industry, area, list_date,
            listing_status, is_st, market_cap, float_market_cap, data_source, coverage, warnings
    """
    try:
        return _json_response(get_security_master(symbol))
    except Exception as exc:
        logger.error("证券主数据获取失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"证券主数据获取失败: {exc}"})


@tool
@register_tool(
    tool_id="get_adjusted_price_series_tool",
    name="标准价格序列",
    description="返回标准化日线价格序列，包含 open/high/low/close/volume/amount/turnover_rate。",
    category="market",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=[
        "price_series", "ohlcv", "daily_price", "adjusted_price", "kline",
        "candlestick", "volume", "turnover_rate", "market_data",
        "price_history", "time_series", "trading_data", "price_trend",
        "backtest_input", "ohlc",
    ],
    tool_role_hint="supporting",
    output_shape="structured_records",
    preferred_for=[
        "price_history_query", "kline_data", "backtest_data_preparation",
        "price_trend_analysis", "volume_analysis", "technical_analysis_input",
    ],
    when_to_use="当需要 K 线序列、价格走势、后续收益率/波动/回撤计算输入时使用。",
    returns="返回 JSON 字符串，包含 records、window、coverage、warnings。",
    example="get_adjusted_price_series_tool(symbol='600519', start_date='2024-01-01', end_date='2024-12-31')",
)
def get_adjusted_price_series_tool(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"],
    start_date: Annotated[Optional[str], "开始日期 YYYY-MM-DD，默认近3年"] = None,
    end_date: Annotated[Optional[str], "结束日期 YYYY-MM-DD，默认今天"] = None,
    limit: Annotated[int, "最多返回条数，默认1000"] = 1000,
) -> str:
    """获取标准价格序列。

    Args:
        symbol: A 股股票代码，如 600519、000001
        start_date: 开始日期 YYYY-MM-DD，默认近3年
        end_date: 结束日期 YYYY-MM-DD，默认今天
        limit: 最多返回条数，默认1000

    Returns:
        str: JSON 字符串。解析后的字段结构同
            ``core.skill_runtime.standard_financial_apis.get_adjusted_price_series`` 的 Returns ——
            status, symbol, period, adjustment, data_source, window, records, coverage, warnings
    """
    try:
        return _json_response(get_adjusted_price_series(symbol, start_date=start_date, end_date=end_date, limit=limit))
    except Exception as exc:
        logger.error("标准价格序列获取失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"标准价格序列获取失败: {exc}"})


@tool
@register_tool(
    tool_id="get_return_series_tool",
    name="收益率序列",
    description="结构化返回逐期收益率记录、统计摘要和覆盖率，用于波动率计算与回测输入。",
    category="market",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=[
        "return_series", "daily_returns", "return_statistics",
        "return_distribution", "price_return", "risk_metrics",
        "volatility_input", "backtest_input", "return_history",
        "time_series", "return_analysis", "performance_measurement",
        "periodic_returns",
    ],
    tool_role_hint="supporting",
    output_shape="structured_records",
    preferred_for=[
        "return_series_analysis", "volatility_calculation", "backtest_input",
        "risk_metrics_calculation", "return_distribution_analysis",
        "performance_measurement",
    ],
    when_to_use="当需要收益率序列、风险指标、回测输入或波动率计算输入时使用。",
    returns="返回 JSON 字符串，包含 records、summary、coverage、warnings。",
    example="get_return_series_tool(symbol='600519', start_date='2024-01-01', end_date='2024-12-31')",
)
def get_return_series_tool(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"],
    start_date: Annotated[Optional[str], "开始日期 YYYY-MM-DD，默认近3年"] = None,
    end_date: Annotated[Optional[str], "结束日期 YYYY-MM-DD，默认今天"] = None,
    limit: Annotated[int, "最多返回条数，默认1000"] = 1000,
) -> str:
    """获取收益率序列。

    Args:
        symbol: A 股股票代码，如 600519、000001
        start_date: 开始日期 YYYY-MM-DD，默认近3年
        end_date: 结束日期 YYYY-MM-DD，默认今天
        limit: 最多返回条数，默认1000

    Returns:
        str: JSON 字符串。解析后的字段结构同
            ``core.skill_runtime.standard_financial_apis.get_return_series`` 的 Returns ——
            status, symbol, period, window, records, summary, coverage, warnings
    """
    try:
        return _json_response(get_return_series(symbol, start_date=start_date, end_date=end_date, limit=limit))
    except Exception as exc:
        logger.error("收益率序列获取失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"收益率序列获取失败: {exc}"})


@tool
@register_tool(
    tool_id="get_volatility_metrics_tool",
    name="波动率指标",
    description="结构化返回日波动率、年化波动率及样本数指标，用于个股价格风险衡量与风险画像。",
    category="market",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=[
        "volatility", "annualized_volatility", "price_risk",
        "volatility_metrics", "risk_measurement", "return_volatility",
        "risk_metrics", "market_risk", "volatility_analysis",
        "standard_deviation", "price_volatility",
    ],
    tool_role_hint="specialized",
    output_shape="structured_metrics",
    preferred_for=[
        "volatility_analysis", "annualized_volatility_calculation",
        "price_risk_assessment", "risk_profile", "market_risk_measurement",
    ],
    when_to_use="当需要衡量个股价格风险、年化波动、风险画像时使用。",
    returns="返回 JSON 字符串，包含 metrics、window、warnings。",
    example="get_volatility_metrics_tool(symbol='600519', start_date='2024-01-01', end_date='2024-12-31')",
)
def get_volatility_metrics_tool(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"],
    start_date: Annotated[Optional[str], "开始日期 YYYY-MM-DD，默认近3年"] = None,
    end_date: Annotated[Optional[str], "结束日期 YYYY-MM-DD，默认今天"] = None,
    limit: Annotated[int, "最多返回条数，默认1000"] = 1000,
) -> str:
    """获取波动率指标。

    Args:
        symbol: A 股股票代码，如 600519、000001
        start_date: 开始日期 YYYY-MM-DD，默认近3年
        end_date: 结束日期 YYYY-MM-DD，默认今天
        limit: 最多返回条数，默认1000

    Returns:
        str: JSON 字符串。解析后的字段结构同
            ``core.skill_runtime.standard_financial_apis.get_volatility_metrics`` 的 Returns ——
            status, symbol, period, window, metrics, warnings
    """
    try:
        return _json_response(get_volatility_metrics(symbol, start_date=start_date, end_date=end_date, limit=limit))
    except Exception as exc:
        logger.error("波动率指标获取失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"波动率指标获取失败: {exc}"})


@tool
@register_tool(
    tool_id="get_drawdown_metrics_tool",
    name="回撤指标",
    description="结构化返回最大回撤、回撤起止日期和回撤序列，用于下行风险评估与回测。",
    category="market",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=[
        "drawdown", "max_drawdown", "downside_risk", "drawdown_series",
        "peak_to_trough", "loss_analysis", "risk_metrics",
        "downside_deviation", "drawdown_duration", "recovery_analysis",
        "market_risk", "drawdown_recovery",
    ],
    tool_role_hint="specialized",
    output_shape="structured_metrics",
    preferred_for=[
        "max_drawdown_analysis", "downside_risk_assessment",
        "drawdown_analysis", "backtest_risk_metrics", "loss_analysis",
        "recovery_analysis",
    ],
    when_to_use="当需要衡量下行风险、最大回撤、风险画像或回测风险指标时使用。",
    returns="返回 JSON 字符串，包含 metrics、drawdown_series、warnings。",
    example="get_drawdown_metrics_tool(symbol='600519', start_date='2024-01-01', end_date='2024-12-31')",
)
def get_drawdown_metrics_tool(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"],
    start_date: Annotated[Optional[str], "开始日期 YYYY-MM-DD，默认近3年"] = None,
    end_date: Annotated[Optional[str], "结束日期 YYYY-MM-DD，默认今天"] = None,
    limit: Annotated[int, "最多返回条数，默认1000"] = 1000,
) -> str:
    """获取回撤指标。

    Args:
        symbol: A 股股票代码，如 600519、000001
        start_date: 开始日期 YYYY-MM-DD，默认近3年
        end_date: 结束日期 YYYY-MM-DD，默认今天
        limit: 最多返回条数，默认1000

    Returns:
        str: JSON 字符串。解析后的字段结构同
            ``core.skill_runtime.standard_financial_apis.get_drawdown_metrics`` 的 Returns ——
            status, symbol, period, window, metrics, drawdown_series, warnings
    """
    try:
        return _json_response(get_drawdown_metrics(symbol, start_date=start_date, end_date=end_date, limit=limit))
    except Exception as exc:
        logger.error("回撤指标获取失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"回撤指标获取失败: {exc}"})


@tool
@register_tool(
    tool_id="get_current_valuation_snapshot_tool",
    name="当前估值快照",
    description=(
        "结构化返回当前 PE/PB/PS/PEG/股息率/市值等估值快照。"
        "用于当前截面的估值指标取数，不计算历史分位、同业相对位置、DCF 目标价或完整估值区间。"
    ),
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=[
        "valuation", "current_valuation", "valuation_snapshot",
        "pe", "pb", "ps", "peg", "dividend_yield", "market_cap",
        "valuation_metrics", "valuation_analysis", "snapshot",
        "current_metrics", "relative_valuation", "valuation_snapshot",
    ],
    tool_role_hint="primary",
    output_shape="structured_metrics",
    preferred_for=[
        "current_valuation_snapshot", "pe_pb_snapshot", "valuation_quick_check",
        "market_cap_lookup", "dividend_yield_check", "valuation_metrics_lookup",
    ],
    when_to_use="当只需要当前 PE/PB/PS/PEG/股息率/市值等估值指标快照，而不是历史分位、同业比较或目标价模型时使用。",
    when_not_to_use="不用于历史估值分位（用 get_historical_valuation_percentile_tool）、同业相对估值（用 get_peer_relative_valuation_tool）、DCF/目标价估值或财务质量/风险分析。",
    returns="返回 JSON 字符串，包含 current_price、metrics、data_source、warnings。",
    example="get_current_valuation_snapshot_tool(symbol='600519')",
)
def get_current_valuation_snapshot_tool(symbol: Annotated[str, "A 股股票代码，如 600519、000001"]) -> str:
    """获取当前估值快照。

    Args:
        symbol: A 股股票代码，如 600519、000001

    Returns:
        str: JSON 字符串。解析后的字段结构同
            ``core.skill_runtime.standard_financial_apis.get_current_valuation_snapshot`` 的 Returns ——
            status, symbol, name, industry, trade_date, current_price, metrics, metric_sources,
            raw_metrics, data_source, warnings
    """
    try:
        return _json_response(get_current_valuation_snapshot(symbol))
    except Exception as exc:
        logger.error("当前估值快照获取失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"当前估值快照获取失败: {exc}"})


@tool
@register_tool(
    tool_id="get_debt_solvency_trend_tool",
    name="偿债能力长期趋势",
    description="结构化返回资产负债率、流动比率、速动比率、债务权益比、经营现金流债务覆盖等长期趋势。",
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=[
        "solvency", "debt_solvency", "debt_to_assets", "current_ratio",
        "quick_ratio", "debt_to_equity", "financial_health", "leverage",
        "leverage_trend", "debt_coverage", "cashflow_debt_coverage",
        "balance_sheet", "financial_risk", "long_term_solvency",
        "liquidity_ratio", "time_series",
    ],
    tool_role_hint="specialized",
    output_shape="structured_records",
    preferred_for=[
        "solvency_analysis", "leverage_trend_analysis",
        "financial_health_assessment", "debt_coverage_analysis",
        "liquidity_analysis", "financial_risk_assessment",
    ],
    when_to_use="当需要分析财务健康度、偿债能力、杠杆趋势时使用。",
    returns="返回 JSON 字符串，包含 trend、summary、coverage、warnings。",
    example="get_debt_solvency_trend_tool(symbol='600519', years=10)",
)
def get_debt_solvency_trend_tool(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"],
    years: Annotated[int, "年报年数，默认10，最大15"] = 10,
) -> str:
    """获取偿债能力长期趋势。

    Args:
        symbol: A 股股票代码，如 600519、000001
        years: 年报年数，默认10，最大15

    Returns:
        str: JSON 字符串。解析后的字段结构同
            ``core.skill_runtime.standard_financial_apis.get_debt_solvency_trend`` 的 Returns ——
            status, symbol, years_used, coverage, trend, summary, warnings
    """
    try:
        return _json_response(get_debt_solvency_trend(symbol, years=years))
    except Exception as exc:
        logger.error("偿债能力长期趋势获取失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"偿债能力长期趋势获取失败: {exc}"})


@tool
@register_tool(
    tool_id="get_peer_group_tool",
    name="标准同行组",
    description="基于行业返回标准化同行样本组，包含市值、PE、PB、ROE 等基础字段。",
    category="market",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=[
        "peer_group", "peer_comparison", "industry_peers", "peers",
        "same_industry", "competitors", "peer_list", "industry_competition",
        "market_cap", "pe", "pb", "roe", "valuation",
        "moat_analysis", "competitive_advantage", "peer_benchmarking",
    ],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=[
        "peer_group_construction", "peer_comparison", "industry_peer_analysis",
        "competitor_analysis", "moat_analysis", "competitive_advantage_assessment",
        "peer_benchmarking",
    ],
    when_to_use="当需要构建同行样本、同业估值或同业质量比较前置数据、同业竞争分析时使用。",
    returns="返回 JSON 字符串，包含 industry、peers、coverage、warnings。",
    example="get_peer_group_tool(symbol='600519', limit=50)",
)
def get_peer_group_tool(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"],
    limit: Annotated[int, "同行数量上限，默认50"] = 50,
) -> str:
    """获取标准同行组。

    Args:
        symbol: A 股股票代码，如 600519、000001
        limit: 同行数量上限，默认50

    Returns:
        str: JSON 字符串。解析后的字段结构同
            ``core.skill_runtime.standard_financial_apis.get_peer_group`` 的 Returns ——
            status, symbol, industry, peers, coverage(peer_count/limit), warnings
    """
    try:
        return _json_response(get_peer_group(symbol, limit=limit))
    except Exception as exc:
        logger.error("标准同行组获取失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"标准同行组获取失败: {exc}"})


@tool
@register_tool(
    tool_id="get_peer_relative_valuation_tool",
    name="同业相对估值",
    description=(
        "结构化返回 PE/PB/PS 相对行业同行的均值、中位数和分位。"
        "用于横向同业估值比较和行业相对位置判断，不用于历史估值分位、DCF 目标价或单纯当前估值快照。"
    ),
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=[
        "peer_comparison", "peer_valuation", "industry_valuation", "valuation_percentile",
        "pe", "pb", "ps", "valuation_benchmarking", "peer_relative",
        "same_industry_valuation", "relative_valuation",
        "moat_analysis", "competitive_advantage",
    ],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=[
        "peer_valuation_comparison", "industry_valuation_percentile", "valuation_benchmarking",
        "pe_peer_ranking", "pb_peer_ranking", "ps_peer_ranking",
        "moat_analysis", "competitive_advantage_assessment",
    ],
    when_to_use="当需要同业估值比较、行业估值相对位置、PE/PB/PS 横向分位时使用。",
    when_not_to_use="不用于历史估值分位时间序列（用 get_historical_valuation_percentile_tool）、当前估值快照（用 get_current_valuation_snapshot_tool）、DCF/目标价模型或质量因子分析。",
    returns="返回 JSON 字符串，包含 industry、metrics、warnings。",
    example="get_peer_relative_valuation_tool(symbol='600519', metrics='pe,pb,ps')",
)
def get_peer_relative_valuation_tool(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"],
    metrics: Annotated[str, "逗号分隔指标，如 pe,pb,ps"] = "pe,pb,ps",
    peer_limit: Annotated[int, "同行样本上限，默认200"] = 200,
) -> str:
    """获取同业相对估值。

    Args:
        symbol: A 股股票代码，如 600519、000001
        metrics: 逗号分隔指标，如 pe,pb,ps
        peer_limit: 同行样本上限，默认200

    Returns:
        str: JSON 字符串。解析后的字段结构同
            ``core.skill_runtime.standard_financial_apis.get_peer_relative_valuation`` 的 Returns ——
            status, symbol, industry, metrics, warnings
    """
    try:
        return _json_response(get_peer_relative_valuation(symbol, metrics=_parse_metrics(metrics), peer_limit=peer_limit))
    except Exception as exc:
        logger.error("同业相对估值获取失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"同业相对估值获取失败: {exc}"})


@tool
@register_tool(
    tool_id="get_peer_relative_quality_tool",
    name="同业相对质量",
    description=(
        "结构化返回 ROE/PB/PE 等质量或估值质量指标相对同行的位置。"
        "这里的“质量”指公司基本面质量和同行相对质量，如 ROE、盈利能力、资产效率与部分估值质量，不是数据质量、报告质量、现金流专项质量或技术信号质量。"
    ),
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=[
        "peer_comparison", "peer_quality", "industry_quality", "quality_percentile",
        "roe", "pb", "pe_ttm", "quality_benchmarking", "peer_relative",
        "same_industry_quality", "relative_quality", "profitability",
        "moat_analysis", "competitive_advantage",
    ],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=[
        "peer_quality_comparison", "industry_quality_percentile", "quality_benchmarking",
        "roe_peer_ranking", "profitability_peer_ranking",
        "moat_analysis", "competitive_advantage_assessment",
    ],
    when_to_use="当需要判断公司基本面质量指标在同行中的相对位置，如 ROE、盈利能力、资产效率、估值质量横向比较时使用。",
    when_not_to_use="不用于数据质量检查、报告质量评审、现金流专项质量趋势（用 get_cashflow_quality_trend_tool）或技术指标信号质量。",
    returns="返回 JSON 字符串，包含 industry、metrics、warnings。",
    example="get_peer_relative_quality_tool(symbol='600519', metrics='roe,pb,pe_ttm')",
)
def get_peer_relative_quality_tool(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"],
    metrics: Annotated[str, "逗号分隔指标，如 roe,pb,pe_ttm"] = "roe,pb,pe_ttm",
    peer_limit: Annotated[int, "同行样本上限，默认200"] = 200,
) -> str:
    """获取同业相对质量。

    Args:
        symbol: A 股股票代码，如 600519、000001
        metrics: 逗号分隔指标，如 roe,pb,pe_ttm
        peer_limit: 同行样本上限，默认200

    Returns:
        str: JSON 字符串。解析后的字段结构同
            ``core.skill_runtime.standard_financial_apis.get_peer_relative_quality`` 的 Returns ——
            status, symbol, industry, metrics, warnings
    """
    try:
        return _json_response(get_peer_relative_quality(symbol, metrics=_parse_metrics(metrics), peer_limit=peer_limit))
    except Exception as exc:
        logger.error("同业相对质量获取失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"同业相对质量获取失败: {exc}"})


@tool
@register_tool(
    tool_id="get_company_announcements_tool",
    name="公司公告代理",
    description="从近期新闻中识别公告类记录，作为公告专用数据源接入前的结构化代理能力。",
    category="news",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    when_to_use="当需要公司公告、披露、财报、分红、减持、重组等事件线索时使用。",
    when_not_to_use="不适合正式公告数据库查询（请使用 get_company_event_timeline_tool）；不适合一般性新闻分析（请使用 get_stock_news）。",
    capability_tags=["event", "announcement", "disclosure"],
    tool_role_hint="specialized",
    returns="返回 JSON 字符串，包含 announcements、coverage、warnings。",
    example="get_company_announcements_tool(symbol='600519', lookback_days=365)",
    related_tools=["get_company_event_timeline_tool", "get_risk_event_flags_tool", "get_stock_news"],
)
def get_company_announcements_tool(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"],
    lookback_days: Annotated[int, "回看天数，默认365"] = 365,
    limit: Annotated[int, "返回条数上限，默认50"] = 50,
) -> str:
    """获取公司公告代理记录。

    Args:
        symbol: A 股股票代码，如 600519、000001
        lookback_days: 回看天数，默认365
        limit: 返回条数上限，默认50

    Returns:
        str: JSON 字符串。解析后的字段结构同
            ``core.skill_runtime.standard_financial_apis.get_company_announcements`` 的 Returns ——
            status, symbol, window, announcements, coverage, warnings
    """
    try:
        return _json_response(get_company_announcements(symbol, lookback_days=lookback_days, limit=limit))
    except Exception as exc:
        logger.error("公司公告代理获取失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"公司公告代理获取失败: {exc}"})


@tool
@register_tool(
    tool_id="get_risk_event_flags_tool",
    name="风险事件标记",
    description=(
        "基于近期新闻标题/摘要识别监管处罚、诉讼、减持、质押、业绩预警、重组、高管变动等风险 flags。"
        "这里的“风险事件/信号”指新闻和公告事件线索，不是财务报表异常、现金流恶化、市场波动风险、技术买卖信号或 Agent 能力缺口。"
    ),
    category="news",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    when_to_use="当需要快速判断近期是否存在监管处罚、诉讼、减持、质押、业绩预警、重组等重大新闻/公告事件线索时使用。",
    when_not_to_use="不适合财务风险深度分析、现金流异常识别或财务造假信号检测；这类需求应使用财务风险/财报质量工具。不适合深度事件定量分析（请使用 get_event_study）；不适合正式公告查询（请使用 get_company_event_timeline_tool）；不适合一般性新闻浏览（请使用 get_stock_news）。",
    capability_tags=["event", "risk", "regulatory"],
    tool_role_hint="specialized",
    returns="返回 JSON 字符串，包含 hit_flags、flags、news_count、warnings。",
    example="get_risk_event_flags_tool(symbol='600519', lookback_days=180)",
    related_tools=["get_company_event_timeline_tool", "get_company_announcements_tool", "get_event_study", "get_stock_news"],
)
def get_risk_event_flags_tool(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"],
    lookback_days: Annotated[int, "回看天数，默认180"] = 180,
    limit: Annotated[int, "新闻条数上限，默认50"] = 50,
) -> str:
    """获取风险事件标记。

    Args:
        symbol: A 股股票代码，如 600519、000001
        lookback_days: 回看天数，默认180
        limit: 新闻条数上限，默认50

    Returns:
        str: JSON 字符串。解析后的字段结构同
            ``core.skill_runtime.standard_financial_apis.get_risk_event_flags`` 的 Returns ——
            status, symbol, window, news_count, hit_flags, flags, warnings
    """
    try:
        return _json_response(get_risk_event_flags(symbol, lookback_days=lookback_days, limit=limit))
    except Exception as exc:
        logger.error("风险事件标记获取失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"风险事件标记获取失败: {exc}"})


@tool
@register_tool(
    tool_id="get_margin_stability_metrics_tool",
    name="利润率稳定性指标",
    description="结构化返回毛利率、净利率、营业利润率、费用率的长期稳定性统计。",
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=[
        "margin_stability", "gross_margin_stability", "net_margin_stability",
        "operating_margin_stability", "expense_ratio", "expense_ratio_stability",
        "profitability_stability", "margin_trend", "margin_volatility",
        "moat_analysis", "competitive_advantage", "cost_control",
        "operating_efficiency", "margin_persistence",
    ],
    tool_role_hint="specialized",
    output_shape="structured_metrics",
    preferred_for=[
        "margin_stability_analysis", "gross_margin_persistence",
        "net_margin_stability", "expense_ratio_analysis", "moat_analysis",
        "competitive_advantage_assessment", "cost_control_assessment",
    ],
    when_to_use="当需要分析利润率稳定性、护城河证据、费用控制质量时使用。",
    returns="返回 JSON 字符串，包含 trend、metrics、coverage、warnings。",
    example="get_margin_stability_metrics_tool(symbol='600519', years=10)",
)
def get_margin_stability_metrics_tool(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"],
    years: Annotated[int, "年报年数，默认10，最大15"] = 10,
) -> str:
    """获取利润率稳定性指标。

    Args:
        symbol: A 股股票代码，如 600519、000001
        years: 年报年数，默认10，最大15

    Returns:
        str: JSON 字符串。解析后的字段结构同
            ``core.skill_runtime.standard_financial_apis.get_margin_stability_metrics`` 的 Returns ——
            status, symbol, years_used, coverage, trend, metrics, warnings
    """
    try:
        return _json_response(get_margin_stability_metrics(symbol, years=years))
    except Exception as exc:
        logger.error("利润率稳定性指标获取失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"利润率稳定性指标获取失败: {exc}"})


@tool
@register_tool(
    tool_id="get_capital_efficiency_trend_tool",
    name="资本效率趋势",
    description="结构化返回 ROE、ROA、ROIC、资产周转率、权益乘数等资本效率长期趋势。",
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=[
        "capital_efficiency", "roe", "roa", "roic", "asset_turnover",
        "equity_multiplier", "dupont_analysis", "return_on_equity",
        "return_on_assets", "return_on_invested_capital",
        "operating_efficiency", "capital_allocation",
        "financial_efficiency", "time_series",
    ],
    tool_role_hint="specialized",
    output_shape="structured_records",
    preferred_for=[
        "capital_efficiency_analysis", "dupont_decomposition",
        "roe_trend_analysis", "roa_trend_analysis", "roic_analysis",
        "operating_efficiency_assessment", "capital_allocation_analysis",
    ],
    when_to_use="当需要分析资本使用效率、杜邦拆解基础指标、长期经营效率时使用。",
    returns="返回 JSON 字符串，包含 trend、summary、coverage、warnings。",
    example="get_capital_efficiency_trend_tool(symbol='600519', years=10)",
)
def get_capital_efficiency_trend_tool(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"],
    years: Annotated[int, "年报年数，默认10，最大15"] = 10,
) -> str:
    """获取资本效率趋势。

    Args:
        symbol: A 股股票代码，如 600519、000001
        years: 年报年数，默认10，最大15

    Returns:
        str: JSON 字符串。解析后的字段结构同
            ``core.skill_runtime.standard_financial_apis.get_capital_efficiency_trend`` 的 Returns ——
            status, symbol, years_used, coverage, trend, summary, warnings
    """
    try:
        return _json_response(get_capital_efficiency_trend(symbol, years=years))
    except Exception as exc:
        logger.error("资本效率趋势获取失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"资本效率趋势获取失败: {exc}"})


@tool
@register_tool(
    tool_id="get_growth_quality_metrics_tool",
    name="成长质量指标",
    description="结构化返回营收、净利润、经营现金流、自由现金流 CAGR 和年度增长稳定性。",
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=[
        "growth_quality", "revenue_cagr", "net_profit_cagr",
        "operating_cashflow_cagr", "free_cashflow_cagr", "growth_stability",
        "growth_volatility", "earnings_growth", "revenue_growth",
        "sustainable_growth", "growth_persistence", "cashflow_backed_growth",
        "quality_growth", "growth_consistency",
    ],
    tool_role_hint="specialized",
    output_shape="structured_metrics",
    preferred_for=[
        "growth_quality_analysis", "cagr_analysis", "growth_stability_assessment",
        "sustainable_growth_check", "cashflow_backed_growth_verification",
        "earnings_growth_quality",
    ],
    when_to_use="当需要判断成长质量、增长是否由现金流支撑、收入利润增长是否稳定时使用。",
    returns="返回 JSON 字符串，包含 cagr、annual_growth、growth_stability、quality_flags、warnings。",
    example="get_growth_quality_metrics_tool(symbol='600519', years=10)",
)
def get_growth_quality_metrics_tool(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"],
    years: Annotated[int, "年报年数，默认10，最大15"] = 10,
) -> str:
    """获取成长质量指标。

    Args:
        symbol: A 股股票代码，如 600519、000001
        years: 年报年数，默认10，最大15

    Returns:
        str: JSON 字符串。解析后的字段结构同
            ``core.skill_runtime.standard_financial_apis.get_growth_quality_metrics`` 的 Returns ——
            status, symbol, years_used, coverage, cagr, annual_growth, growth_stability,
            quality_flags, warnings
    """
    try:
        return _json_response(get_growth_quality_metrics(symbol, years=years))
    except Exception as exc:
        logger.error("成长质量指标获取失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"成长质量指标获取失败: {exc}"})


@tool
@register_tool(
    tool_id="get_single_stock_risk_profile_tool",
    name="个股风险画像",
    description="基于价格序列返回收益分布、年化波动率、最大回撤、下行波动、正负收益日比例等风险画像。",
    category="market",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=[
        "risk_profile", "single_stock_risk", "return_distribution",
        "annualized_volatility", "max_drawdown", "downside_volatility",
        "upside_ratio", "downside_ratio", "risk_metrics", "price_risk",
        "market_risk", "risk_assessment", "return_distribution_analysis",
        "downside_risk",
    ],
    tool_role_hint="specialized",
    output_shape="structured_metrics",
    preferred_for=[
        "single_stock_risk_profile", "price_risk_assessment",
        "return_distribution_analysis", "downside_risk_analysis",
        "volatility_assessment", "backtest_risk_context",
    ],
    when_to_use="当需要个股风险画像、价格风险、下行风险或回测前风险上下文时使用。",
    returns="返回 JSON 字符串，包含 metrics、components、warnings。",
    example="get_single_stock_risk_profile_tool(symbol='600519', start_date='2024-01-01', end_date='2024-12-31')",
)
def get_single_stock_risk_profile_tool(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"],
    start_date: Annotated[Optional[str], "开始日期 YYYY-MM-DD，默认近3年"] = None,
    end_date: Annotated[Optional[str], "结束日期 YYYY-MM-DD，默认今天"] = None,
    limit: Annotated[int, "最多返回条数，默认1000"] = 1000,
) -> str:
    """获取个股风险画像。

    Args:
        symbol: A 股股票代码，如 600519、000001
        start_date: 开始日期 YYYY-MM-DD，默认近3年
        end_date: 结束日期 YYYY-MM-DD，默认今天
        limit: 最多返回条数，默认1000

    Returns:
        str: JSON 字符串。解析后的字段结构同
            ``core.skill_runtime.standard_financial_apis.get_single_stock_risk_profile`` 的 Returns ——
            status, symbol, period, window, metrics, components, warnings
    """
    try:
        return _json_response(get_single_stock_risk_profile(symbol, start_date=start_date, end_date=end_date, limit=limit))
    except Exception as exc:
        logger.error("个股风险画像获取失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"个股风险画像获取失败: {exc}"})


@tool
@register_tool(
    tool_id="get_industry_fundamental_summary_tool",
    name="行业基本面摘要",
    description="基于同行样本返回行业市值、PE、PB、ROE 等基本面统计和头部样本。",
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=[
        "industry_fundamental", "industry_summary", "industry_statistics",
        "industry_pe", "industry_pb", "industry_roe", "peer_statistics",
        "industry_valuation", "industry_quality", "top_peers",
        "market_cap_distribution", "peer_comparison", "industry_benchmark",
        "fundamental_summary",
    ],
    tool_role_hint="supporting",
    output_shape="structured_json",
    preferred_for=[
        "industry_fundamental_background", "peer_distribution_analysis",
        "industry_valuation_benchmark", "industry_quality_benchmark",
        "top_peer_identification", "industry_context",
    ],
    when_to_use="当需要行业基本面背景、同行样本分布、行业估值/质量统计上下文时使用。",
    returns="返回 JSON 字符串，包含 industry、metrics、top_market_cap_peers、coverage、warnings。",
    example="get_industry_fundamental_summary_tool(symbol='600519', peer_limit=100)",
)
def get_industry_fundamental_summary_tool(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"],
    peer_limit: Annotated[int, "同行样本上限，默认100"] = 100,
) -> str:
    """获取行业基本面摘要。

    Args:
        symbol: A 股股票代码，如 600519、000001
        peer_limit: 同行样本上限，默认100

    Returns:
        str: JSON 字符串。解析后的字段结构同
            ``core.skill_runtime.standard_financial_apis.get_industry_fundamental_summary`` 的 Returns ——
            status, symbol, industry, coverage, metrics, top_market_cap_peers, warnings
    """
    try:
        return _json_response(get_industry_fundamental_summary(symbol, peer_limit=peer_limit))
    except Exception as exc:
        logger.error("行业基本面摘要获取失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"行业基本面摘要获取失败: {exc}"})


@tool
@register_tool(
    tool_id="get_capital_flow_series_tool",
    name="个股资金流序列",
    description=(
        "结构化返回本地个股资金流序列，包括主力净流入、净流入比例、大单/小单净流入等字段。"
        "这里的“资金流”指交易资金流向和主力资金行为，不是财务报表中的经营现金流、投资现金流、筹资现金流或自由现金流。"
    ),
    category="market",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=[
        "capital_flow", "money_flow", "main_force_flow", "institutional_flow",
        "large_order_flow", "small_order_flow", "net_inflow", "inflow_ratio",
        "trading_flow", "fund_flow", "market_behavior", "capital_behavior",
        "liquidity_analysis", "main_force_behavior", "time_series",
    ],
    tool_role_hint="specialized",
    output_shape="structured_records",
    preferred_for=[
        "capital_flow_analysis", "main_force_behavior_analysis",
        "fund_flow_trend", "large_order_flow_analysis",
        "market_behavior_evidence", "liquidity_analysis",
    ],
    when_to_use="当需要交易资金流趋势、主力资金行为、资金面证据、大单/小单净流入结构时使用。若本地未同步资金流，将返回 no_data 和原因。",
    when_not_to_use="不用于财务报表现金流质量、经营现金流下滑、自由现金流为负或利润含金量分析；这些需求应使用 get_cashflow_quality_trend_tool、get_cashflow_analysis 或 get_growth_cashflow_factor_bundle_tool。",
    returns="返回 JSON 字符串，包含 records、summary、coverage、warnings。",
    example="get_capital_flow_series_tool(symbol='600519', start_date='2024-01-01', end_date='2024-12-31')",
)
def get_capital_flow_series_tool(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"],
    start_date: Annotated[Optional[str], "开始日期 YYYY-MM-DD，默认近180天"] = None,
    end_date: Annotated[Optional[str], "结束日期 YYYY-MM-DD，默认今天"] = None,
    limit: Annotated[int, "最多返回条数，默认120"] = 120,
) -> str:
    """获取个股资金流序列。

    Args:
        symbol: A 股股票代码，如 600519、000001
        start_date: 开始日期 YYYY-MM-DD，默认近180天
        end_date: 结束日期 YYYY-MM-DD，默认今天
        limit: 最多返回条数，默认120

    Returns:
        str: JSON 字符串。解析后的字段结构同
            ``core.skill_runtime.standard_financial_apis.get_capital_flow_series`` 的 Returns ——
            status, symbol, window, data_source, records, summary, coverage, warnings
    """
    try:
        return _json_response(get_capital_flow_series(symbol, start_date=start_date, end_date=end_date, limit=limit))
    except Exception as exc:
        logger.error("个股资金流序列获取失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"个股资金流序列获取失败: {exc}"})


@tool
@register_tool(
    tool_id="get_chip_distribution_context_tool",
    name="筹码分布上下文",
    description="结构化返回获利比例、平均成本、70%/90%筹码成本区间和集中度。",
    category="market",
    is_online=True,
    auto_register=True,
    timeout_tier="medium",
    capability_tags=[
        "chip_distribution", "profit_ratio", "average_cost", "cost_distribution",
        "chip_concentration", "cost_range", "holder_cost", "market_behavior",
        "chip_structure", "concentration_ratio", "profit_margin_distribution",
        "cost_basis", "holding_cost", "snapshot",
    ],
    tool_role_hint="specialized",
    output_shape="structured_metrics",
    preferred_for=[
        "chip_distribution_analysis", "cost_concentration_analysis",
        "profit_ratio_check", "average_cost_analysis",
        "support_resistance_from_cost", "market_behavior_analysis",
    ],
    when_to_use="当需要筹码分布、成本集中度、获利盘比例等市场行为证据时使用。",
    returns="返回 JSON 字符串，包含 metrics、data_source、warnings。",
    example="get_chip_distribution_context_tool(symbol='600519', trade_date='2024-12-31')",
)
def get_chip_distribution_context_tool(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"],
    trade_date: Annotated[Optional[str], "交易日期 YYYY-MM-DD，默认今天"] = None,
) -> str:
    """获取筹码分布上下文。

    Args:
        symbol: A 股股票代码，如 600519、000001
        trade_date: 交易日期 YYYY-MM-DD，默认今天

    Returns:
        str: JSON 字符串。解析后的字段结构同
            ``core.skill_runtime.standard_financial_apis.get_chip_distribution_context`` 的 Returns ——
            status, symbol, trade_date, message, data_source, metrics, warnings
    """
    try:
        return _json_response(get_chip_distribution_context(symbol, trade_date=trade_date))
    except Exception as exc:
        logger.error("筹码分布上下文获取失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"筹码分布上下文获取失败: {exc}"})


@tool
@register_tool(
    tool_id="get_pledge_risk_profile_tool",
    name="股权质押风险画像",
    description=(
        "返回股权质押风险画像：总质押比例、未解押规模、前几大质押股东、最近质押事件、风险等级。"
        "数据来源优先使用项目内置 Tushare/akshare 数据源，无需用户指定数据源。"
    ),
    category="fundamentals",
    is_online=True,
    auto_register=True,
    timeout_tier="medium",
    when_to_use="当需要分析股权质押比例、大股东质押情况、质押爆仓风险、平仓线压力时使用。",
    when_not_to_use="不适合非质押类的股东分析（请使用 get_shareholder_return_metrics_tool）；不适合一般风险画像（请使用 get_single_stock_risk_profile_tool）。",
    capability_tags=["pledge", "shareholder", "risk"],
    tool_role_hint="specialized",
    returns="返回 JSON 字符串，包含 status、metrics（total_pledge_ratio/outstanding_amount 等）、top_pledgers、recent_pledges、risk_level、warnings。",
    example="get_pledge_risk_profile_tool(symbol='600519')",
    related_tools=["get_risk_event_flags_tool", "get_shareholder_return_metrics_tool", "get_single_stock_risk_profile_tool"],
)
def get_pledge_risk_profile_tool(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"],
    source: Annotated[Optional[str], "数据源，默认自动选择"] = None,
) -> str:
    """获取股权质押风险画像。

    Args:
        symbol: A 股股票代码，如 600519、000001
        source: 数据源，默认自动选择

    Returns:
        str: JSON 字符串。解析后的字段结构同
            ``core.skill_runtime.standard_financial_apis.get_pledge_risk_profile`` 的 Returns ——
            status, symbol, data_source, metrics(total_pledge_ratio/outstanding_pledge_amount_wan 等),
            top_pledgers, recent_pledges, risk_level, warnings, data_source_status
    """
    try:
        return _json_response(get_pledge_risk_profile(symbol, source=source))
    except Exception as exc:
        logger.error("股权质押风险画像获取失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"股权质押风险画像获取失败: {exc}"})


@register_tool(
    tool_id="get_pledge_historical_series_tool",
    name="股权质押历史趋势",
    description=(
        "返回单只 A 股指定时间段内的股权质押趋势数据，支持按年/季/月统计，"
        "包括每个周期末的质押比例、未解押股数、活跃质押笔数，以及自动评估的趋势方向（好转/恶化/稳定）。"
        "数据来源优先使用项目内置 Tushare/akshare 数据源，无需用户指定数据源。"
    ),
    category="fundamentals",
    is_online=True,
    auto_register=True,
    timeout_tier="medium",
    when_to_use="当需要分析股权质押比例的历史变化趋势、判断质押风险是好转还是恶化、按时间周期对比质押数据时使用。支持自定义起止日期和统计粒度。",
    when_not_to_use="不适合查询当前质押快照（请使用 get_pledge_risk_profile_tool）；不适合非质押类的股东分析。",
    capability_tags=["pledge", "shareholder", "risk", "trend", "historical"],
    tool_role_hint="specialized",
    returns="返回 JSON 字符串，包含 status、period（统计周期）、start_date、end_date、series（周期数组，含 period/pledge_ratio/outstanding_pledge_amount_wan 等）、trend_assessment（趋势方向评估）、warnings。",
    example="get_pledge_historical_series_tool(symbol='600519', start_date='2021-01-01', end_date='2024-12-31', period='year')",
    related_tools=["get_pledge_risk_profile_tool", "get_single_stock_risk_profile_tool", "get_risk_event_flags_tool"],
)
def get_pledge_historical_series_tool(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"],
    start_date: Annotated[Optional[str], "开始日期，YYYY-MM-DD 格式，与 years 二选一"] = None,
    end_date: Annotated[Optional[str], "结束日期，YYYY-MM-DD 格式，默认今天"] = None,
    years: Annotated[Optional[int], "最近 N 年，便捷参数，与 start_date 二选一，默认 3 年"] = None,
    period: Annotated[Optional[str], "统计周期：year/quarter/month，默认 year"] = "year",
    source: Annotated[Optional[str], "数据源，默认自动选择"] = None,
) -> str:
    """获取股权质押历史趋势。

    Args:
        symbol: A 股股票代码，如 600519、000001
        start_date: 开始日期，YYYY-MM-DD 格式，与 years 二选一
        end_date: 结束日期，YYYY-MM-DD 格式，默认今天
        years: 最近 N 年，便捷参数，与 start_date 二选一，默认 3 年
        period: 统计周期：year/quarter/month，默认 year
        source: 数据源，默认自动选择

    Returns:
        str: JSON 字符串。解析后的字段结构同
            ``core.skill_runtime.standard_financial_apis.get_pledge_historical_series`` 的 Returns ——
            status, symbol, data_source, period, start_date, end_date, period_count, series,
            trend_assessment(direction/change_pct/summary), warnings
    """
    try:
        return _json_response(get_pledge_historical_series(
            symbol, start_date=start_date, end_date=end_date,
            years=years, period=period, source=source
        ))
    except Exception as exc:
        logger.error("股权质押历史趋势获取失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"股权质押历史趋势获取失败: {exc}"})
