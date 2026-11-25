"""Skill 运行时基本面因子标准实现。"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .data_access import (
    get_latest_stock_price,
    get_market_quotes,
    get_stock_basic_info,
    get_stock_financial_periods,
    summarize_industry_valuation,
)
from .factor_schema import get_factor_field_schema


Numeric = Optional[float]


def _normalize_symbol(symbol: str) -> str:
    return str(symbol).strip().zfill(6)


def _pick_first(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _to_float(value: Any) -> Numeric:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        numeric = float(value)
        if numeric != numeric:
            return None
        return numeric
    try:
        text = str(value).strip()
        if not text:
            return None
        numeric = float(text)
        if numeric != numeric:
            return None
        return numeric
    except (TypeError, ValueError):
        return None


def _safe_divide(numerator: Numeric, denominator: Numeric) -> Numeric:
    if numerator is None or denominator in (None, 0):
        return None
    try:
        return float(numerator) / float(denominator)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _append_factor_warning(warnings: Dict[str, List[str]], field_name: str, condition: str) -> None:
    warning_list = warnings.setdefault(field_name, [])
    if condition not in warning_list:
        warning_list.append(condition)


def _build_factor_warning_payload(warnings: Dict[str, List[str]]) -> Dict[str, Dict[str, Any]]:
    payload: Dict[str, Dict[str, Any]] = {}
    for field_name, conditions in warnings.items():
        schema = get_factor_field_schema(field_name)
        payload[field_name] = {
            "warning_conditions": list(conditions),
            "warning_categories": list(schema.warning_categories or []) if schema else [],
        }
    return payload


def _build_value_factor_warnings(context: Dict[str, Any], factors: Dict[str, Any], industry_pe_stats: Dict[str, Any], industry_pb_stats: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    warnings: Dict[str, List[str]] = {}
    basic_info = context["basic_info"]
    latest_financial = context["latest_financial"]

    if factors.get("pe_ttm") is not None and basic_info.get("pe_ttm") is None and _pick_first(basic_info.get("pe"), context["market_quotes"].get("pe")) is not None:
        _append_factor_warning(warnings, "pe_ttm", "pe_ttm fallback_to pe")
    if factors.get("pb") is not None and basic_info.get("pb") is None and factors.get("pb_mrq") is not None:
        _append_factor_warning(warnings, "pb", "pb fallback_to pb_mrq")
    if factors.get("pb_mrq") is not None and basic_info.get("pb_mrq") is None:
        _append_factor_warning(warnings, "pb_mrq", "pb_mrq estimated_from market_cap_and_total_equity")
    if factors.get("ps_ttm") is not None and basic_info.get("ps_ttm") is None and basic_info.get("ps") is not None:
        _append_factor_warning(warnings, "ps_ttm", "ps_ttm fallback_to ps")
    if factors.get("dividend_yield") is not None and basic_info.get("dividend_yield") is None and _pick_first(_get_nested(latest_financial, "financial_indicators", "dividend_yield"), latest_financial.get("dividend_yield")) is not None:
        _append_factor_warning(warnings, "dividend_yield", "dividend_yield fallback_to financial_field")
    if factors.get("industry_pe_median") is not None and _to_float(industry_pe_stats.get("count")) is not None and float(industry_pe_stats.get("count")) < 5:
        _append_factor_warning(warnings, "industry_pe_median", "industry_peer_sample_count < 5")
    if factors.get("industry_pb_median") is not None and _to_float(industry_pb_stats.get("count")) is not None and float(industry_pb_stats.get("count")) < 5:
        _append_factor_warning(warnings, "industry_pb_median", "industry_peer_sample_count < 5")

    return _build_factor_warning_payload(warnings)


def _build_quality_factor_warnings(context: Dict[str, Any], factors: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    warnings: Dict[str, List[str]] = {}
    latest_financial = context["latest_financial"]

    if factors.get("roic") is not None and _extract_financial_field(latest_financial, ("money_cap",), ("balance_sheet", "money_cap")) is None:
        _append_factor_warning(warnings, "roic", "roic money_cap_missing_assumed_zero")

    finance_expense = _extract_financial_field(latest_financial, ("fin_exp",), ("income_statement", "fin_exp"))
    raw_interest = _extract_raw_statement_field(latest_financial, "income_statement", "int_exp", "fin_exp_int_exp")
    if factors.get("interest_coverage") is not None and (finance_expense in (None, 0) or (finance_expense is not None and finance_expense <= 0)) and raw_interest is not None:
        _append_factor_warning(warnings, "interest_coverage", "interest_coverage fallback_to raw_interest_expense")

    oper_cost = _extract_financial_field(latest_financial, ("oper_cost",), ("income_statement", "oper_cost"))
    revenue_base = _extract_financial_field(latest_financial, ("revenue_ttm",), ("revenue",), ("oper_rev",), ("income_statement", "revenue"), ("income_statement", "oper_rev"))
    gross_margin = _extract_financial_field(latest_financial, ("gross_margin",), ("financial_indicators", "grossprofit_margin"), ("financial_indicators", "gross_margin"))
    if factors.get("inventory_turnover") is not None and oper_cost is None and revenue_base is not None and gross_margin is not None:
        _append_factor_warning(warnings, "inventory_turnover", "inventory_turnover cost_proxy_used")

    total_ncl = _extract_financial_field(latest_financial, ("total_ncl",), ("balance_sheet", "total_ncl"))
    total_liab = _extract_financial_field(latest_financial, ("total_liab",), ("balance_sheet", "total_liab"))
    total_cur_liab = _extract_financial_field(latest_financial, ("total_cur_liab",), ("balance_sheet", "total_cur_liab"))
    if factors.get("net_cash_position") is not None and total_ncl is None and total_liab is not None and total_cur_liab is not None:
        _append_factor_warning(warnings, "net_cash_position", "net_cash_position proxy_total_ncl_used")

    return _build_factor_warning_payload(warnings)


def _build_growth_factor_warnings(context: Dict[str, Any], factors: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    warnings: Dict[str, List[str]] = {}
    latest_financial = context["latest_financial"]

    if factors.get("net_profit_ttm") is not None and _extract_financial_field(latest_financial, ("net_profit_ttm",)) is None:
        net_profit = _extract_financial_field(latest_financial, ("net_profit",), ("net_income",), ("income_statement", "net_profit"), ("income_statement", "net_income"))
        if net_profit is not None:
            _append_factor_warning(warnings, "net_profit_ttm", "net_profit_ttm fallback_to net_profit_or_net_income")

    if factors.get("fcf") is not None:
        _append_factor_warning(warnings, "fcf", "fcf conservative_proxy_used")

    return _build_factor_warning_payload(warnings)


def _get_nested(mapping: Optional[Dict[str, Any]], *keys: str) -> Any:
    current: Any = mapping or {}
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
        if current is None:
            return None
    return current


def _report_period(record: Optional[Dict[str, Any]]) -> str:
    raw_value = _pick_first(
        (record or {}).get("report_period"),
        (record or {}).get("report_date"),
    )
    digits = "".join(ch for ch in str(raw_value or "") if ch.isdigit())
    return digits[:8]


def _same_period_last_year(period: str) -> str:
    if len(period) != 8:
        return ""
    try:
        return f"{int(period[:4]) - 1:04d}{period[4:]}"
    except ValueError:
        return ""


def _same_period_n_years(period: str, years: int) -> str:
    if len(period) != 8:
        return ""
    try:
        return f"{int(period[:4]) - years:04d}{period[4:]}"
    except ValueError:
        return ""


def _latest_financial_record(financial_records: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    return dict(financial_records[0]) if financial_records else {}


def _find_financial_record_by_period(
    financial_records: Sequence[Dict[str, Any]],
    period: str,
) -> Dict[str, Any]:
    normalized_period = str(period or "")
    if not normalized_period:
        return {}
    for record in financial_records:
        if _report_period(record) == normalized_period:
            return dict(record)
    return {}


def _previous_financial_record(financial_records: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    return dict(financial_records[1]) if len(financial_records) > 1 else {}


def _extract_financial_field(record: Dict[str, Any], *candidates: Tuple[str, ...]) -> Numeric:
    for candidate in candidates:
        value = _get_nested(record, *candidate)
        numeric_value = _to_float(value)
        if numeric_value is not None:
            return numeric_value
    return None


def _get_raw_statement_record(record: Dict[str, Any], section: str) -> Dict[str, Any]:
    section_data = _get_nested(record, "raw_data", section)
    if isinstance(section_data, list) and section_data and isinstance(section_data[0], dict):
        return dict(section_data[0])
    if isinstance(section_data, dict):
        return dict(section_data)
    return {}


def _extract_raw_statement_field(record: Dict[str, Any], section: str, *field_names: str) -> Numeric:
    statement_record = _get_raw_statement_record(record, section)
    for field_name in field_names:
        value = _to_float(statement_record.get(field_name))
        if value is not None:
            return value
    return None


def _extract_period_metric(record: Dict[str, Any], metric: str) -> Numeric:
    candidate_map: Dict[str, Tuple[Tuple[str, ...], ...]] = {
        "revenue": (
            ("revenue",),
            ("oper_rev",),
            ("income_statement", "revenue"),
            ("income_statement", "oper_rev"),
        ),
        "net_profit": (
            ("net_profit",),
            ("net_income",),
            ("income_statement", "net_profit"),
            ("income_statement", "net_income"),
        ),
        "oper_profit": (
            ("oper_profit",),
            ("operating_profit",),
            ("ebit",),
            ("income_statement", "oper_profit"),
            ("income_statement", "operating_profit"),
            ("income_statement", "ebit"),
        ),
    }
    candidates = candidate_map.get(metric, ((metric,),))
    return _extract_financial_field(record, *candidates)


def _compute_yoy_growth(financial_records: Sequence[Dict[str, Any]], metric: str) -> Numeric:
    latest_record = _latest_financial_record(financial_records)
    latest_period = _report_period(latest_record)
    prior_period = _same_period_last_year(latest_period)
    if not latest_period or not prior_period:
        return None

    prior_record = _find_financial_record_by_period(financial_records, prior_period)
    current_value = _extract_period_metric(latest_record, metric)
    prior_value = _extract_period_metric(prior_record, metric)
    if current_value is None or prior_value in (None, 0):
        return None

    return ((current_value - prior_value) / prior_value) * 100.0


def _estimate_tax_rate(latest_financial: Dict[str, Any]) -> Numeric:
    total_profit = _extract_financial_field(
        latest_financial,
        ("total_profit",),
        ("income_statement", "total_profit"),
    )
    net_profit = _extract_financial_field(
        latest_financial,
        ("net_profit",),
        ("net_income",),
        ("income_statement", "net_profit"),
        ("income_statement", "net_income"),
    )
    if total_profit is not None and total_profit > 0 and net_profit is not None:
        estimated = 1.0 - (net_profit / total_profit)
        return max(0.0, min(0.35, estimated))
    return 0.25


def _estimate_roic(latest_financial: Dict[str, Any]) -> Numeric:
    operating_profit = _extract_financial_field(
        latest_financial,
        ("ebit",),
        ("oper_profit",),
        ("operating_profit",),
        ("income_statement", "ebit"),
        ("income_statement", "oper_profit"),
        ("income_statement", "operating_profit"),
    )
    total_equity = _extract_financial_field(
        latest_financial,
        ("total_equity",),
        ("balance_sheet", "total_equity"),
        ("balance_sheet", "total_hldr_eqy_exc_min_int"),
    )
    total_liab = _extract_financial_field(
        latest_financial,
        ("total_liab",),
        ("balance_sheet", "total_liab"),
    )
    money_cap = _extract_financial_field(
        latest_financial,
        ("money_cap",),
        ("balance_sheet", "money_cap"),
    )

    if operating_profit is None or total_equity is None or total_liab is None:
        return None

    invested_capital = total_equity + total_liab - (money_cap or 0.0)
    if invested_capital <= 0:
        return None

    nopat = operating_profit * (1.0 - (_estimate_tax_rate(latest_financial) or 0.25))
    return (nopat / invested_capital) * 100.0


def _estimate_interest_coverage(latest_financial: Dict[str, Any]) -> Numeric:
    operating_profit = _extract_financial_field(
        latest_financial,
        ("ebit",),
        ("oper_profit",),
        ("operating_profit",),
        ("income_statement", "ebit"),
        ("income_statement", "oper_profit"),
        ("income_statement", "operating_profit"),
    )
    finance_expense = _extract_financial_field(
        latest_financial,
        ("fin_exp",),
        ("income_statement", "fin_exp"),
    )
    if finance_expense in (None, 0) or (finance_expense is not None and finance_expense <= 0):
        finance_expense = _extract_raw_statement_field(
            latest_financial,
            "income_statement",
            "int_exp",
            "fin_exp_int_exp",
        )
    if operating_profit is None or finance_expense is None or finance_expense <= 0:
        return None
    return operating_profit / finance_expense


def _estimate_pb_mrq(context: Dict[str, Any]) -> Numeric:
    latest_financial = context["latest_financial"]
    total_equity = _extract_financial_field(
        latest_financial,
        ("total_equity",),
        ("balance_sheet", "total_hldr_eqy_exc_min_int"),
        ("balance_sheet", "total_equity"),
    )
    market_cap_yi = _to_float(
        _pick_first(
            context["market_quotes"].get("total_mv"),
            context["basic_info"].get("total_mv"),
            context["basic_info"].get("market_cap"),
        )
    )
    if total_equity in (None, 0) or market_cap_yi is None:
        return None
    return (market_cap_yi * 100000000.0) / total_equity


def _estimate_net_cash_position(latest_financial: Dict[str, Any]) -> Numeric:
    money_cap = _extract_financial_field(
        latest_financial,
        ("money_cap",),
        ("balance_sheet", "money_cap"),
    )
    total_assets = _extract_financial_field(
        latest_financial,
        ("total_assets",),
        ("balance_sheet", "total_assets"),
    )
    total_ncl = _extract_financial_field(
        latest_financial,
        ("total_ncl",),
        ("balance_sheet", "total_ncl"),
    )
    if total_ncl is None:
        total_liab = _extract_financial_field(
            latest_financial,
            ("total_liab",),
            ("balance_sheet", "total_liab"),
        )
        total_cur_liab = _extract_financial_field(
            latest_financial,
            ("total_cur_liab",),
            ("balance_sheet", "total_cur_liab"),
        )
        if total_liab is not None and total_cur_liab is not None:
            total_ncl = total_liab - total_cur_liab

    if money_cap is None or total_assets in (None, 0) or total_ncl is None:
        return None

    debt_proxy = max(total_ncl, 0.0)
    return ((money_cap - debt_proxy) / total_assets) * 100.0


def _comparison_financial_record(financial_records: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    latest_record = _latest_financial_record(financial_records)
    latest_period = _report_period(latest_record)
    prior_same_period = _same_period_last_year(latest_period)
    if prior_same_period:
        matched_record = _find_financial_record_by_period(financial_records, prior_same_period)
        if matched_record:
            return matched_record
    return _previous_financial_record(financial_records)


def _estimate_roa(record: Dict[str, Any]) -> Numeric:
    roa = _extract_financial_field(
        record,
        ("roa",),
        ("financial_indicators", "roa"),
    )
    if roa is not None:
        return roa

    net_profit = _extract_financial_field(
        record,
        ("net_profit",),
        ("net_income",),
        ("income_statement", "net_profit"),
        ("income_statement", "net_income"),
    )
    total_assets = _extract_financial_field(
        record,
        ("total_assets",),
        ("balance_sheet", "total_assets"),
    )
    roa_ratio = _safe_divide(net_profit, total_assets)
    return roa_ratio * 100.0 if roa_ratio is not None else None


def _estimate_current_ratio(record: Dict[str, Any]) -> Numeric:
    current_ratio = _extract_financial_field(
        record,
        ("current_ratio",),
        ("financial_indicators", "current_ratio"),
    )
    if current_ratio is not None:
        return current_ratio

    total_cur_assets = _extract_financial_field(record, ("total_cur_assets",), ("balance_sheet", "total_cur_assets"))
    total_cur_liab = _extract_financial_field(record, ("total_cur_liab",), ("balance_sheet", "total_cur_liab"))
    return _safe_divide(total_cur_assets, total_cur_liab)


def _estimate_gross_margin(record: Dict[str, Any]) -> Numeric:
    gross_margin = _extract_financial_field(
        record,
        ("gross_margin",),
        ("financial_indicators", "grossprofit_margin"),
        ("financial_indicators", "gross_margin"),
    )
    if gross_margin is not None:
        return gross_margin

    revenue = _extract_period_metric(record, "revenue")
    oper_cost = _extract_financial_field(record, ("oper_cost",), ("income_statement", "oper_cost"))
    if revenue in (None, 0) or oper_cost is None:
        return None
    return ((revenue - oper_cost) / revenue) * 100.0


def _estimate_asset_turnover(record: Dict[str, Any]) -> Numeric:
    revenue = _extract_period_metric(record, "revenue")
    total_assets = _extract_financial_field(record, ("total_assets",), ("balance_sheet", "total_assets"))
    return _safe_divide(revenue, total_assets)


def _estimate_long_term_leverage(record: Dict[str, Any]) -> Numeric:
    total_ncl = _extract_financial_field(record, ("total_ncl",), ("balance_sheet", "total_ncl"))
    total_assets = _extract_financial_field(record, ("total_assets",), ("balance_sheet", "total_assets"))
    if total_ncl is None:
        total_liab = _extract_financial_field(record, ("total_liab",), ("balance_sheet", "total_liab"))
        total_cur_liab = _extract_financial_field(record, ("total_cur_liab",), ("balance_sheet", "total_cur_liab"))
        if total_liab is not None and total_cur_liab is not None:
            total_ncl = total_liab - total_cur_liab
    return _safe_divide(total_ncl, total_assets)


def _extract_share_count(record: Dict[str, Any], basic_info: Optional[Dict[str, Any]] = None) -> Numeric:
    share_count = _extract_raw_statement_field(record, "balance_sheet", "total_share")
    if share_count is not None:
        return share_count
    if basic_info:
        return _to_float(_pick_first(basic_info.get("total_share"), basic_info.get("total_shares")))
    return None


def _extract_retained_earnings(record: Dict[str, Any]) -> Numeric:
    return _extract_raw_statement_field(record, "balance_sheet", "undistr_porfit", "surplus_rese")


def _extract_depreciation_expense(record: Dict[str, Any]) -> Numeric:
    values = [
        _extract_raw_statement_field(record, "cashflow_statement", "prov_depr_assets"),
        _extract_raw_statement_field(record, "cashflow_statement", "depr_fa_coga_dpba"),
        _extract_raw_statement_field(record, "cashflow_statement", "amort_intang_assets"),
        _extract_raw_statement_field(record, "cashflow_statement", "lt_amort_deferred_exp"),
    ]
    numeric_values = [value for value in values if value is not None]
    if not numeric_values:
        return None
    return sum(numeric_values)


def _estimate_piotroski_f_score(context: Dict[str, Any]) -> Numeric:
    latest_record = context["latest_financial"]
    previous_record = _comparison_financial_record(context["financial_records"])
    if not previous_record:
        return None

    current_roa = _estimate_roa(latest_record)
    previous_roa = _estimate_roa(previous_record)
    current_cfo = _extract_financial_field(latest_record, ("n_cashflow_act",), ("cashflow_statement", "n_cashflow_act"))
    current_net_profit = _extract_financial_field(latest_record, ("net_profit",), ("net_income",), ("income_statement", "net_profit"), ("income_statement", "net_income"))
    current_leverage = _estimate_long_term_leverage(latest_record)
    previous_leverage = _estimate_long_term_leverage(previous_record)
    current_liquidity = _estimate_current_ratio(latest_record)
    previous_liquidity = _estimate_current_ratio(previous_record)
    current_share_count = _extract_share_count(latest_record, context.get("basic_info"))
    previous_share_count = _extract_share_count(previous_record)
    current_margin = _estimate_gross_margin(latest_record)
    previous_margin = _estimate_gross_margin(previous_record)
    current_turnover = _estimate_asset_turnover(latest_record)
    previous_turnover = _estimate_asset_turnover(previous_record)

    required_values = [
        current_roa,
        previous_roa,
        current_cfo,
        current_net_profit,
        current_leverage,
        previous_leverage,
        current_liquidity,
        previous_liquidity,
        current_share_count,
        previous_share_count,
        current_margin,
        previous_margin,
        current_turnover,
        previous_turnover,
    ]
    if any(value is None for value in required_values):
        return None

    signals = [
        current_roa > 0,
        current_cfo > 0,
        current_roa > previous_roa,
        current_cfo > current_net_profit,
        current_leverage < previous_leverage,
        current_liquidity > previous_liquidity,
        current_share_count <= previous_share_count,
        current_margin > previous_margin,
        current_turnover > previous_turnover,
    ]
    return float(sum(1 for signal in signals if signal))


def _estimate_altman_z_score(context: Dict[str, Any]) -> Numeric:
    latest_record = context["latest_financial"]
    total_assets = _extract_financial_field(latest_record, ("total_assets",), ("balance_sheet", "total_assets"))
    total_liab = _extract_financial_field(latest_record, ("total_liab",), ("balance_sheet", "total_liab"))
    working_capital = _extract_net_working_capital(latest_record)
    retained_earnings = _extract_retained_earnings(latest_record)
    ebit = _extract_financial_field(
        latest_record,
        ("ebit",),
        ("oper_profit",),
        ("income_statement", "ebit"),
        ("income_statement", "oper_profit"),
    )
    sales = _extract_period_metric(latest_record, "revenue")
    market_cap_yi = _to_float(
        _pick_first(
            context["market_quotes"].get("total_mv"),
            context["basic_info"].get("total_mv"),
            context["basic_info"].get("market_cap"),
        )
    )
    if None in (total_assets, total_liab, working_capital, retained_earnings, ebit, sales, market_cap_yi):
        return None
    if total_assets == 0 or total_liab == 0:
        return None

    market_value_equity = market_cap_yi * 100000000.0
    a_value = working_capital / total_assets
    b_value = retained_earnings / total_assets
    c_value = ebit / total_assets
    d_value = market_value_equity / total_liab
    e_value = sales / total_assets
    return 1.2 * a_value + 1.4 * b_value + 3.3 * c_value + 0.6 * d_value + 1.0 * e_value


def _estimate_beneish_m_score(context: Dict[str, Any]) -> Numeric:
    latest_record = context["latest_financial"]
    previous_record = _comparison_financial_record(context["financial_records"])
    if not previous_record:
        return None

    sales_current = _extract_period_metric(latest_record, "revenue")
    sales_previous = _extract_period_metric(previous_record, "revenue")
    receivables_current = _extract_financial_field(latest_record, ("accounts_receiv",), ("balance_sheet", "accounts_receiv"))
    receivables_previous = _extract_financial_field(previous_record, ("accounts_receiv",), ("balance_sheet", "accounts_receiv"))
    oper_cost_current = _extract_financial_field(latest_record, ("oper_cost",), ("income_statement", "oper_cost"))
    oper_cost_previous = _extract_financial_field(previous_record, ("oper_cost",), ("income_statement", "oper_cost"))
    total_assets_current = _extract_financial_field(latest_record, ("total_assets",), ("balance_sheet", "total_assets"))
    total_assets_previous = _extract_financial_field(previous_record, ("total_assets",), ("balance_sheet", "total_assets"))
    current_assets_current = _extract_financial_field(latest_record, ("total_cur_assets",), ("balance_sheet", "total_cur_assets"))
    current_assets_previous = _extract_financial_field(previous_record, ("total_cur_assets",), ("balance_sheet", "total_cur_assets"))
    fixed_assets_current = _extract_financial_field(latest_record, ("fix_assets",), ("balance_sheet", "fix_assets"))
    fixed_assets_previous = _extract_financial_field(previous_record, ("fix_assets",), ("balance_sheet", "fix_assets"))
    depreciation_current = _extract_depreciation_expense(latest_record)
    depreciation_previous = _extract_depreciation_expense(previous_record)
    sga_current = sum(
        value for value in [
            _extract_financial_field(latest_record, ("oper_exp",), ("income_statement", "oper_exp")),
            _extract_financial_field(latest_record, ("admin_exp",), ("income_statement", "admin_exp")),
            _extract_financial_field(latest_record, ("rd_exp",), ("income_statement", "rd_exp")),
        ] if value is not None
    )
    sga_previous = sum(
        value for value in [
            _extract_financial_field(previous_record, ("oper_exp",), ("income_statement", "oper_exp")),
            _extract_financial_field(previous_record, ("admin_exp",), ("income_statement", "admin_exp")),
            _extract_financial_field(previous_record, ("rd_exp",), ("income_statement", "rd_exp")),
        ] if value is not None
    )
    total_liab_current = _extract_financial_field(latest_record, ("total_liab",), ("balance_sheet", "total_liab"))
    total_liab_previous = _extract_financial_field(previous_record, ("total_liab",), ("balance_sheet", "total_liab"))
    net_profit_current = _extract_financial_field(latest_record, ("net_profit",), ("net_income",), ("income_statement", "net_profit"), ("income_statement", "net_income"))
    cfo_current = _extract_financial_field(latest_record, ("n_cashflow_act",), ("cashflow_statement", "n_cashflow_act"))

    if None in (
        sales_current,
        sales_previous,
        receivables_current,
        receivables_previous,
        oper_cost_current,
        oper_cost_previous,
        total_assets_current,
        total_assets_previous,
        current_assets_current,
        current_assets_previous,
        fixed_assets_current,
        fixed_assets_previous,
        depreciation_current,
        depreciation_previous,
        total_liab_current,
        total_liab_previous,
        net_profit_current,
        cfo_current,
    ):
        return None

    if 0 in (
        sales_current,
        sales_previous,
        total_assets_current,
        total_assets_previous,
        total_liab_previous,
        depreciation_current + fixed_assets_current,
        depreciation_previous + fixed_assets_previous,
    ):
        return None

    dsri = (receivables_current / sales_current) / (receivables_previous / sales_previous)
    gross_margin_current = (sales_current - oper_cost_current) / sales_current
    gross_margin_previous = (sales_previous - oper_cost_previous) / sales_previous
    if gross_margin_current == 0:
        return None
    gmi = gross_margin_previous / gross_margin_current
    asset_quality_current = 1.0 - ((current_assets_current + fixed_assets_current) / total_assets_current)
    asset_quality_previous = 1.0 - ((current_assets_previous + fixed_assets_previous) / total_assets_previous)
    if asset_quality_previous == 0:
        return None
    aqi = asset_quality_current / asset_quality_previous
    sgi = sales_current / sales_previous
    depi = (depreciation_previous / (depreciation_previous + fixed_assets_previous)) / (depreciation_current / (depreciation_current + fixed_assets_current))
    if sga_previous == 0:
        return None
    sgai = (sga_current / sales_current) / (sga_previous / sales_previous)
    lvgi = (total_liab_current / total_assets_current) / (total_liab_previous / total_assets_previous)
    tata = (net_profit_current - cfo_current) / total_assets_current

    return (
        -4.84
        + 0.92 * dsri
        + 0.528 * gmi
        + 0.404 * aqi
        + 0.892 * sgi
        + 0.115 * depi
        - 0.172 * sgai
        + 4.679 * tata
        - 0.327 * lvgi
    )


def _estimate_fcf(latest_financial: Dict[str, Any]) -> Numeric:
    operating_cashflow = _extract_financial_field(
        latest_financial,
        ("n_cashflow_act",),
        ("cashflow_statement", "n_cashflow_act"),
        ("operating_cash_flow",),
    )
    investing_cashflow = _extract_financial_field(
        latest_financial,
        ("n_cashflow_inv_act",),
        ("cashflow_statement", "n_cashflow_inv_act"),
        ("investing_cash_flow",),
    )
    if operating_cashflow is None or investing_cashflow is None:
        return None
    return operating_cashflow + investing_cashflow


def _extract_net_working_capital(record: Dict[str, Any]) -> Numeric:
    total_cur_assets = _extract_financial_field(
        record,
        ("total_cur_assets",),
        ("balance_sheet", "total_cur_assets"),
    )
    total_cur_liab = _extract_financial_field(
        record,
        ("total_cur_liab",),
        ("balance_sheet", "total_cur_liab"),
    )
    if total_cur_assets is None or total_cur_liab is None:
        return None
    return total_cur_assets - total_cur_liab


def _compute_cagr(
    financial_records: Sequence[Dict[str, Any]],
    metric_candidates: Sequence[Tuple[str, ...]],
    years: int,
) -> Numeric:
    latest_record = _latest_financial_record(financial_records)
    latest_period = _report_period(latest_record)
    base_period = _same_period_n_years(latest_period, years)
    if not latest_period or not base_period:
        return None

    base_record = _find_financial_record_by_period(financial_records, base_period)
    current_value = _extract_financial_field(latest_record, *metric_candidates)
    base_value = _extract_financial_field(base_record, *metric_candidates)
    if current_value is None or base_value in (None, 0) or current_value <= 0 or base_value <= 0:
        return None

    return ((current_value / base_value) ** (1.0 / years) - 1.0) * 100.0


def _build_context(symbol: str) -> Dict[str, Any]:
    normalized_symbol = _normalize_symbol(symbol)
    basic_info = get_stock_basic_info(normalized_symbol) or {}
    market_quotes = get_market_quotes(normalized_symbol) or {}
    financial_records = get_stock_financial_periods(normalized_symbol, limit=20)
    latest_financial = _latest_financial_record(financial_records)
    current_price = get_latest_stock_price(normalized_symbol)

    return {
        "symbol": normalized_symbol,
        "basic_info": basic_info,
        "market_quotes": market_quotes,
        "financial_records": financial_records,
        "latest_financial": latest_financial,
        "current_price": current_price,
    }


def _base_snapshot(context: Dict[str, Any]) -> Dict[str, Any]:
    basic_info = context["basic_info"]
    latest_financial = context["latest_financial"]
    return {
        "symbol": context["symbol"],
        "name": basic_info.get("name"),
        "industry": basic_info.get("industry"),
        "current_price": context["current_price"],
        "report_period": _pick_first(
            latest_financial.get("report_period"),
            latest_financial.get("report_date"),
        ),
        "data_source": _pick_first(
            latest_financial.get("data_source"),
            basic_info.get("source"),
        ),
    }


def _find_missing(factors: Dict[str, Any], required: Iterable[str]) -> List[str]:
    missing: List[str] = []
    for field_name in required:
        if factors.get(field_name) is None:
            missing.append(field_name)
    return missing


def _missing_input_names(values: Dict[str, Any]) -> List[str]:
    return sorted(field_name for field_name, value in values.items() if value is None)


def _build_beneish_m_score_diagnostic(context: Dict[str, Any], factor_value: Numeric) -> Dict[str, Any]:
    latest_record = context["latest_financial"]
    previous_record = _comparison_financial_record(context["financial_records"])
    latest_period = _report_period(latest_record)
    comparison_period = _report_period(previous_record)

    base_diagnostic = {
        "field_name": "beneish_m_score",
        "display_name": "Beneish M-Score",
        "data_quality_state": "available",
        "unavailable_reason": None,
        "missing_inputs": [],
        "report_period": latest_period,
        "comparison_period": comparison_period,
    }
    if factor_value is not None:
        return base_diagnostic

    if not previous_record:
        return {
            **base_diagnostic,
            "data_quality_state": "missing_comparison_period",
            "unavailable_reason": "缺少用于同比比较的上一年同季或上一期财务记录，无法构造 Beneish M-Score 所需的双期输入。",
        }

    sales_current = _extract_period_metric(latest_record, "revenue")
    sales_previous = _extract_period_metric(previous_record, "revenue")
    receivables_current = _extract_financial_field(latest_record, ("accounts_receiv",), ("balance_sheet", "accounts_receiv"))
    receivables_previous = _extract_financial_field(previous_record, ("accounts_receiv",), ("balance_sheet", "accounts_receiv"))
    oper_cost_current = _extract_financial_field(latest_record, ("oper_cost",), ("income_statement", "oper_cost"))
    oper_cost_previous = _extract_financial_field(previous_record, ("oper_cost",), ("income_statement", "oper_cost"))
    total_assets_current = _extract_financial_field(latest_record, ("total_assets",), ("balance_sheet", "total_assets"))
    total_assets_previous = _extract_financial_field(previous_record, ("total_assets",), ("balance_sheet", "total_assets"))
    current_assets_current = _extract_financial_field(latest_record, ("total_cur_assets",), ("balance_sheet", "total_cur_assets"))
    current_assets_previous = _extract_financial_field(previous_record, ("total_cur_assets",), ("balance_sheet", "total_cur_assets"))
    fixed_assets_current = _extract_financial_field(latest_record, ("fix_assets",), ("balance_sheet", "fix_assets"))
    fixed_assets_previous = _extract_financial_field(previous_record, ("fix_assets",), ("balance_sheet", "fix_assets"))
    depreciation_current = _extract_depreciation_expense(latest_record)
    depreciation_previous = _extract_depreciation_expense(previous_record)
    sga_current_values = [
        _extract_financial_field(latest_record, ("oper_exp",), ("income_statement", "oper_exp")),
        _extract_financial_field(latest_record, ("admin_exp",), ("income_statement", "admin_exp")),
        _extract_financial_field(latest_record, ("rd_exp",), ("income_statement", "rd_exp")),
    ]
    sga_previous_values = [
        _extract_financial_field(previous_record, ("oper_exp",), ("income_statement", "oper_exp")),
        _extract_financial_field(previous_record, ("admin_exp",), ("income_statement", "admin_exp")),
        _extract_financial_field(previous_record, ("rd_exp",), ("income_statement", "rd_exp")),
    ]
    sga_current = sum(value for value in sga_current_values if value is not None)
    sga_previous = sum(value for value in sga_previous_values if value is not None)
    total_liab_current = _extract_financial_field(latest_record, ("total_liab",), ("balance_sheet", "total_liab"))
    total_liab_previous = _extract_financial_field(previous_record, ("total_liab",), ("balance_sheet", "total_liab"))
    net_profit_current = _extract_financial_field(latest_record, ("net_profit",), ("net_income",), ("income_statement", "net_profit"), ("income_statement", "net_income"))
    cfo_current = _extract_financial_field(latest_record, ("n_cashflow_act",), ("cashflow_statement", "n_cashflow_act"))

    missing_inputs = _missing_input_names(
        {
            "sales_current": sales_current,
            "sales_previous": sales_previous,
            "receivables_current": receivables_current,
            "receivables_previous": receivables_previous,
            "oper_cost_current": oper_cost_current,
            "oper_cost_previous": oper_cost_previous,
            "total_assets_current": total_assets_current,
            "total_assets_previous": total_assets_previous,
            "current_assets_current": current_assets_current,
            "current_assets_previous": current_assets_previous,
            "fixed_assets_current": fixed_assets_current,
            "fixed_assets_previous": fixed_assets_previous,
            "depreciation_current": depreciation_current,
            "depreciation_previous": depreciation_previous,
            "total_liab_current": total_liab_current,
            "total_liab_previous": total_liab_previous,
            "net_profit_current": net_profit_current,
            "cfo_current": cfo_current,
        }
    )
    if missing_inputs:
        return {
            **base_diagnostic,
            "data_quality_state": "missing_required_inputs",
            "unavailable_reason": "缺少 Beneish M-Score 所需的关键输入字段，当前仓库最常见的是折旧摊销类原始字段在最新期或对比期缺失。",
            "missing_inputs": missing_inputs,
        }

    zero_denominator_inputs: List[str] = []
    if sales_current == 0:
        zero_denominator_inputs.append("sales_current")
    if sales_previous == 0:
        zero_denominator_inputs.append("sales_previous")
    if total_assets_current == 0:
        zero_denominator_inputs.append("total_assets_current")
    if total_assets_previous == 0:
        zero_denominator_inputs.append("total_assets_previous")
    if total_liab_previous == 0:
        zero_denominator_inputs.append("total_liab_previous")
    if (depreciation_current or 0) + (fixed_assets_current or 0) == 0:
        zero_denominator_inputs.append("depreciation_plus_fixed_assets_current")
    if (depreciation_previous or 0) + (fixed_assets_previous or 0) == 0:
        zero_denominator_inputs.append("depreciation_plus_fixed_assets_previous")
    if sga_previous == 0:
        zero_denominator_inputs.append("sga_previous")
    gross_margin_current = ((sales_current - oper_cost_current) / sales_current) if sales_current not in (None, 0) and oper_cost_current is not None else None
    gross_margin_previous = ((sales_previous - oper_cost_previous) / sales_previous) if sales_previous not in (None, 0) and oper_cost_previous is not None else None
    if gross_margin_current == 0:
        zero_denominator_inputs.append("gross_margin_current")
    asset_quality_previous = 1.0 - ((current_assets_previous + fixed_assets_previous) / total_assets_previous) if total_assets_previous not in (None, 0) and current_assets_previous is not None and fixed_assets_previous is not None else None
    if asset_quality_previous == 0:
        zero_denominator_inputs.append("asset_quality_previous")
    if zero_denominator_inputs:
        return {
            **base_diagnostic,
            "data_quality_state": "invalid_denominator",
            "unavailable_reason": "Beneish M-Score 计算过程中存在 0 分母或无效比例项，按当前保守实现直接返回空值。",
            "missing_inputs": zero_denominator_inputs,
        }

    return {
        **base_diagnostic,
        "data_quality_state": "calculation_blocked",
        "unavailable_reason": "Beneish M-Score 未能完成计算，但未命中已知的缺期、缺字段或 0 分母规则。",
    }


def _build_piotroski_f_score_diagnostic(context: Dict[str, Any], factor_value: Numeric) -> Dict[str, Any]:
    latest_record = context["latest_financial"]
    previous_record = _comparison_financial_record(context["financial_records"])
    latest_period = _report_period(latest_record)
    comparison_period = _report_period(previous_record)

    base_diagnostic = {
        "field_name": "piotroski_f_score",
        "display_name": "Piotroski F-Score",
        "data_quality_state": "available",
        "unavailable_reason": None,
        "missing_inputs": [],
        "report_period": latest_period,
        "comparison_period": comparison_period,
    }
    if factor_value is not None:
        return base_diagnostic

    if not previous_record:
        return {
            **base_diagnostic,
            "data_quality_state": "missing_comparison_period",
            "unavailable_reason": "缺少近两期对比财务记录，无法计算 Piotroski F-Score 的 9 项双期信号。",
        }

    current_roa = _estimate_roa(latest_record)
    previous_roa = _estimate_roa(previous_record)
    current_cfo = _extract_financial_field(latest_record, ("n_cashflow_act",), ("cashflow_statement", "n_cashflow_act"))
    current_net_profit = _extract_financial_field(latest_record, ("net_profit",), ("net_income",), ("income_statement", "net_profit"), ("income_statement", "net_income"))
    current_leverage = _estimate_long_term_leverage(latest_record)
    previous_leverage = _estimate_long_term_leverage(previous_record)
    current_liquidity = _estimate_current_ratio(latest_record)
    previous_liquidity = _estimate_current_ratio(previous_record)
    current_share_count = _extract_share_count(latest_record, context.get("basic_info"))
    previous_share_count = _extract_share_count(previous_record)
    current_margin = _estimate_gross_margin(latest_record)
    previous_margin = _estimate_gross_margin(previous_record)
    current_turnover = _estimate_asset_turnover(latest_record)
    previous_turnover = _estimate_asset_turnover(previous_record)

    missing_inputs = _missing_input_names(
        {
            "current_roa": current_roa,
            "previous_roa": previous_roa,
            "current_cfo": current_cfo,
            "current_net_profit": current_net_profit,
            "current_leverage": current_leverage,
            "previous_leverage": previous_leverage,
            "current_liquidity": current_liquidity,
            "previous_liquidity": previous_liquidity,
            "current_share_count": current_share_count,
            "previous_share_count": previous_share_count,
            "current_margin": current_margin,
            "previous_margin": previous_margin,
            "current_turnover": current_turnover,
            "previous_turnover": previous_turnover,
        }
    )
    if missing_inputs:
        return {
            **base_diagnostic,
            "data_quality_state": "missing_required_inputs",
            "unavailable_reason": "缺少 Piotroski F-Score 所需的关键双期输入字段，无法完成 9 项财务信号评分。",
            "missing_inputs": missing_inputs,
        }

    return {
        **base_diagnostic,
        "data_quality_state": "calculation_blocked",
        "unavailable_reason": "Piotroski F-Score 未能完成计算，但未命中已知的缺期或缺字段规则。",
    }


def _build_altman_z_score_diagnostic(context: Dict[str, Any], factor_value: Numeric) -> Dict[str, Any]:
    latest_record = context["latest_financial"]
    latest_period = _report_period(latest_record)

    base_diagnostic = {
        "field_name": "altman_z_score",
        "display_name": "Altman Z-Score",
        "data_quality_state": "available",
        "unavailable_reason": None,
        "missing_inputs": [],
        "report_period": latest_period,
        "comparison_period": None,
    }
    if factor_value is not None:
        return base_diagnostic

    total_assets = _extract_financial_field(latest_record, ("total_assets",), ("balance_sheet", "total_assets"))
    total_liab = _extract_financial_field(latest_record, ("total_liab",), ("balance_sheet", "total_liab"))
    working_capital = _extract_net_working_capital(latest_record)
    retained_earnings = _extract_retained_earnings(latest_record)
    ebit = _extract_financial_field(
        latest_record,
        ("ebit",),
        ("oper_profit",),
        ("income_statement", "ebit"),
        ("income_statement", "oper_profit"),
    )
    sales = _extract_period_metric(latest_record, "revenue")
    market_cap_yi = _to_float(
        _pick_first(
            context["market_quotes"].get("total_mv"),
            context["basic_info"].get("total_mv"),
            context["basic_info"].get("market_cap"),
        )
    )

    missing_inputs = _missing_input_names(
        {
            "total_assets": total_assets,
            "total_liab": total_liab,
            "working_capital": working_capital,
            "retained_earnings": retained_earnings,
            "ebit": ebit,
            "sales": sales,
            "market_cap_yi": market_cap_yi,
        }
    )
    if missing_inputs:
        return {
            **base_diagnostic,
            "data_quality_state": "missing_required_inputs",
            "unavailable_reason": "缺少 Altman Z-Score 所需的关键输入字段，当前实现无法构造 5 个分量。",
            "missing_inputs": missing_inputs,
        }

    zero_denominator_inputs: List[str] = []
    if total_assets == 0:
        zero_denominator_inputs.append("total_assets")
    if total_liab == 0:
        zero_denominator_inputs.append("total_liab")
    if zero_denominator_inputs:
        return {
            **base_diagnostic,
            "data_quality_state": "invalid_denominator",
            "unavailable_reason": "Altman Z-Score 的关键分母为 0，按当前保守实现返回空值。",
            "missing_inputs": zero_denominator_inputs,
        }

    return {
        **base_diagnostic,
        "data_quality_state": "calculation_blocked",
        "unavailable_reason": "Altman Z-Score 未能完成计算，但未命中已知的缺字段或 0 分母规则。",
    }


def _build_factor_diagnostics(context: Dict[str, Any], factors: Dict[str, Any]) -> Dict[str, Any]:
    diagnostics: Dict[str, Any] = {}
    for field_name, factor_value in factors.items():
        schema = get_factor_field_schema(field_name)
        if schema is None or schema.data_quality_tier != "cautious":
            continue
        if field_name == "beneish_m_score":
            diagnostics[field_name] = {
                "data_quality_tier": schema.data_quality_tier,
                **_build_beneish_m_score_diagnostic(context, factor_value),
            }
        elif field_name == "piotroski_f_score":
            diagnostics[field_name] = {
                "data_quality_tier": schema.data_quality_tier,
                **_build_piotroski_f_score_diagnostic(context, factor_value),
            }
        elif field_name == "altman_z_score":
            diagnostics[field_name] = {
                "data_quality_tier": schema.data_quality_tier,
                **_build_altman_z_score_diagnostic(context, factor_value),
            }
    return diagnostics


def get_value_factor_bundle(symbol: str, allow_remote_fetch: bool = True) -> Dict[str, Any]:
    """获取股票的价值因子 bundle（value_core）。

    Args:
        symbol: A 股股票代码（6 位数字或含交易所前后缀）
        allow_remote_fetch: 透传给 get_shareholder_return_metrics；
            交互式接口（因子预览）应传 False 避免现场拉取 Tushare 分红数据

    Returns:
        dict: 字段说明（合并 _base_snapshot 后还包括 symbol/name/industry/current_price/
            report_period/data_source）——
            bundle: 固定值 "value_core"
            factors: 价值因子字典，子字段：
                — pe: 市盈率（静态）
                — pe_ttm: TTM 市盈率
                — pb: 市净率
                — pb_mrq: 最近报告期市净率
                — ps_ttm: TTM 市销率
                — dividend_yield: 股息率（百分比，已与 shareholder return 口径对齐）
                — peg: PEG = pe_ttm / net_profit_yoy（增长率非正或缺失时为 None）
                — industry_pe_median: 行业 PE 中位数
                — industry_pb_median: 行业 PB 中位数
            factor_warnings: 该 bundle 的告警字典
            industry_samples: 行业样本统计
                — pe_count: PE 行业样本数
                — pb_count: PB 行业样本数
            calculation_notes: list[str]，计算口径说明
            missing_factors: list[str]，缺失的关键因子名列表
    """
    context = _build_context(symbol)
    basic_info = context["basic_info"]
    market_quotes = context["market_quotes"]

    industry = basic_info.get("industry")
    industry_pe_stats = summarize_industry_valuation(industry, metric="pe", exclude_symbol=context["symbol"]) if industry else {}
    industry_pb_stats = summarize_industry_valuation(industry, metric="pb", exclude_symbol=context["symbol"]) if industry else {}
    net_profit_yoy = _compute_yoy_growth(context["financial_records"], "net_profit")
    pe_ttm = _to_float(_pick_first(basic_info.get("pe_ttm"), basic_info.get("pe"), market_quotes.get("pe")))
    peg = _safe_divide(pe_ttm, net_profit_yoy) if net_profit_yoy and net_profit_yoy > 0 else None

    pb_mrq = _to_float(_pick_first(basic_info.get("pb_mrq"), _estimate_pb_mrq(context)))

    raw_dividend_yield = _to_float(_pick_first(
        basic_info.get("dividend_yield"),
        _get_nested(context["latest_financial"], "financial_indicators", "dividend_yield"),
        context["latest_financial"].get("dividend_yield"),
    ))
    dividend_yield = raw_dividend_yield
    try:
        # 与 get_current_valuation_snapshot_tool / get_dividend_valuation_context 对齐：
        # 使用已实施分红 / 当前价格的可追溯口径，避免同一报告里股息率出现 0.09pct 左右差异。
        from core.skill_runtime.standard_financial_apis import get_shareholder_return_metrics
        shareholder = get_shareholder_return_metrics(context["symbol"], years=5, allow_remote_fetch=allow_remote_fetch)
        canonical_pct = _to_float((shareholder.get("metrics") or {}).get("latest_dividend_yield_pct"))
        if canonical_pct is not None:
            dividend_yield = canonical_pct
    except Exception:
        pass

    factors = {
        "pe": _to_float(_pick_first(basic_info.get("pe"), market_quotes.get("pe"))),
        "pe_ttm": pe_ttm,
        "pb": _to_float(_pick_first(basic_info.get("pb"), pb_mrq)),
        "pb_mrq": pb_mrq,
        "ps_ttm": _to_float(_pick_first(basic_info.get("ps_ttm"), basic_info.get("ps"))),
        "dividend_yield": dividend_yield,
        "peg": peg,
        "industry_pe_median": _to_float(industry_pe_stats.get("median")),
        "industry_pb_median": _to_float(industry_pb_stats.get("median")),
    }
    factor_warnings = _build_value_factor_warnings(context, factors, industry_pe_stats, industry_pb_stats)

    return {
        **_base_snapshot(context),
        "bundle": "value_core",
        "factors": factors,
        "factor_warnings": factor_warnings,
        "industry_samples": {
            "pe_count": industry_pe_stats.get("count"),
            "pb_count": industry_pb_stats.get("count"),
        },
        "calculation_notes": [
            "peg 使用 pe_ttm / net_profit_yoy，增长率按同季同比百分比口径计算。",
            "dividend_yield 使用已实施现金分红 / 当前价格口径，与股息率估值增强和当前估值快照保持一致；basic_info.daily_basic 股息率作为回退口径。",
        ],
        "missing_factors": _find_missing(
            factors,
            ["pe_ttm", "pb", "ps_ttm", "dividend_yield", "peg"],
        ),
    }


def get_quality_factor_bundle(symbol: str) -> Dict[str, Any]:
    """获取股票的质量因子 bundle（quality_core）。

    Args:
        symbol: A 股股票代码（6 位数字或含交易所前后缀）

    Returns:
        dict: 字段说明（合并 _base_snapshot 后还包括 symbol/name/industry/current_price/
            report_period/data_source）——
            bundle: 固定值 "quality_core"
            factors: 质量因子字典，子字段：
                — roe: 净资产收益率
                — roa: 总资产收益率
                — gross_margin: 毛利率
                — netprofit_margin: 净利率
                — debt_to_assets: 资产负债率
                — assets_to_eqt: 权益乘数
                — current_ratio: 流动比率
                — quick_ratio: 速动比率
                — cash_ratio: 现金比率
                — roic: 投入资本回报率（保守代理口径）
                — cash_conversion: 经营现金流/净利润
                — accrual_ratio: 应计比率（百分比）
                — asset_turnover: 资产周转率
                — gross_profit_to_assets: 毛利/总资产（百分比）
                — interest_coverage: 利息保障倍数
                — inventory_turnover: 存货周转率
                — receivable_turnover: 应收账款周转率
                — net_cash_position: 净现金比率（保守代理）
                — piotroski_f_score: Piotroski F 评分
                — altman_z_score: Altman Z 评分
                — beneish_m_score: Beneish M 评分
            factor_diagnostics: dict，因子的诊断信息（按字段名展开，含 data_quality_tier 等）
            factor_warnings: 该 bundle 的告警字典
            calculation_notes: list[str]，计算口径说明
            missing_factors: list[str]，缺失的关键因子名列表
    """
    context = _build_context(symbol)
    latest_financial = context["latest_financial"]
    roic = _estimate_roic(latest_financial)
    interest_coverage = _estimate_interest_coverage(latest_financial)
    net_cash_position = _estimate_net_cash_position(latest_financial)
    piotroski_f_score = _estimate_piotroski_f_score(context)
    altman_z_score = _estimate_altman_z_score(context)
    beneish_m_score = _estimate_beneish_m_score(context)
    net_profit = _extract_financial_field(
        latest_financial,
        ("net_profit",),
        ("net_income",),
        ("income_statement", "net_profit"),
        ("income_statement", "net_income"),
    )
    n_cashflow_act = _extract_financial_field(
        latest_financial,
        ("n_cashflow_act",),
        ("cashflow_statement", "n_cashflow_act"),
    )
    total_assets = _extract_financial_field(
        latest_financial,
        ("total_assets",),
        ("balance_sheet", "total_assets"),
    )
    revenue_base = _extract_financial_field(
        latest_financial,
        ("revenue_ttm",),
        ("revenue",),
        ("oper_rev",),
        ("income_statement", "revenue"),
        ("income_statement", "oper_rev"),
    )
    oper_cost = _extract_financial_field(
        latest_financial,
        ("oper_cost",),
        ("income_statement", "oper_cost"),
    )
    gross_margin = _extract_financial_field(
        latest_financial,
        ("gross_margin",),
        ("financial_indicators", "grossprofit_margin"),
        ("financial_indicators", "gross_margin"),
    )
    inventories = _extract_financial_field(
        latest_financial,
        ("inventories",),
        ("balance_sheet", "inventories"),
    )
    accounts_receiv = _extract_financial_field(
        latest_financial,
        ("accounts_receiv",),
        ("balance_sheet", "accounts_receiv"),
    )
    cash_conversion = _safe_divide(n_cashflow_act, net_profit)
    accrual_ratio = _safe_divide(
        (net_profit - n_cashflow_act) if net_profit is not None and n_cashflow_act is not None else None,
        total_assets,
    )
    if accrual_ratio is not None:
        accrual_ratio *= 100.0
    asset_turnover = _safe_divide(revenue_base, total_assets)
    gross_profit = None
    if revenue_base is not None and gross_margin is not None:
        gross_profit = revenue_base * gross_margin / 100.0
    gross_profit_to_assets = _safe_divide(gross_profit, total_assets)
    if gross_profit_to_assets is not None:
        gross_profit_to_assets *= 100.0
    cost_base = oper_cost
    if cost_base is None and revenue_base is not None and gross_margin is not None:
        cost_base = revenue_base * (1.0 - gross_margin / 100.0)
    inventory_turnover = _safe_divide(cost_base, inventories)
    receivable_turnover = _safe_divide(revenue_base, accounts_receiv)

    factors = {
        "roe": _extract_financial_field(
            latest_financial,
            ("roe",),
            ("financial_indicators", "roe"),
            ("financial_indicators", "roe_avg"),
        ),
        "roa": _extract_financial_field(
            latest_financial,
            ("roa",),
            ("financial_indicators", "roa"),
        ),
        "gross_margin": gross_margin,
        "netprofit_margin": _extract_financial_field(
            latest_financial,
            ("netprofit_margin",),
            ("financial_indicators", "netprofit_margin"),
        ),
        "debt_to_assets": _extract_financial_field(
            latest_financial,
            ("debt_to_assets",),
            ("financial_indicators", "debt_to_assets"),
        ),
        "assets_to_eqt": _extract_financial_field(
            latest_financial,
            ("assets_to_eqt",),
            ("financial_indicators", "assets_to_eqt"),
        ),
        "current_ratio": _extract_financial_field(
            latest_financial,
            ("current_ratio",),
            ("financial_indicators", "current_ratio"),
        ),
        "quick_ratio": _extract_financial_field(
            latest_financial,
            ("quick_ratio",),
            ("financial_indicators", "quick_ratio"),
        ),
        "cash_ratio": _extract_financial_field(
            latest_financial,
            ("cash_ratio",),
            ("financial_indicators", "cash_ratio"),
        ),
        "roic": roic,
        "cash_conversion": cash_conversion,
        "accrual_ratio": accrual_ratio,
        "asset_turnover": asset_turnover,
        "gross_profit_to_assets": gross_profit_to_assets,
        "interest_coverage": interest_coverage,
        "inventory_turnover": inventory_turnover,
        "receivable_turnover": receivable_turnover,
        "net_cash_position": net_cash_position,
        "piotroski_f_score": piotroski_f_score,
        "altman_z_score": altman_z_score,
        "beneish_m_score": beneish_m_score,
    }
    factor_diagnostics = _build_factor_diagnostics(context, factors)
    factor_warnings = _build_quality_factor_warnings(context, factors)

    return {
        **_base_snapshot(context),
        "bundle": "quality_core",
        "factors": factors,
        "factor_diagnostics": factor_diagnostics,
        "factor_warnings": factor_warnings,
        "calculation_notes": [
            "roic 使用营业利润近似 EBIT，投入资本使用 total_equity + total_liab - money_cap 的保守代理口径。",
            "cash_conversion 使用经营现金流/净利润，accrual_ratio 使用 (净利润-经营现金流)/总资产，并以百分比输出。",
            "asset_turnover 与 gross_profit_to_assets 使用最新总资产作为保守代理，而非平均总资产。",
            "interest_coverage 优先使用 ebit / fin_exp，若净财务费用 <= 0 则回退到原始报表中的 int_exp/fin_exp_int_exp。",
            "inventory_turnover 与 receivable_turnover 当前使用最新存货/应收账款作为保守代理，而非平均余额。",
            "net_cash_position 当前使用 (money_cap - total_ncl) / total_assets 的保守代理；缺少 total_ncl 时回退为 total_liab - total_cur_liab。",
            "piotroski_f_score 使用近两期可得财务记录计算 9 项信号，缺少对比期或关键字段时返回空。",
            "altman_z_score 使用原始报表中的 undistr_porfit 与 ebit 字段；缺少任一关键分量时返回空。",
            "beneish_m_score 使用原始报表中的折旧摊销与费用字段计算 8 指标模型，缺少同比基准期时返回空。",
        ],
        "missing_factors": _find_missing(
            factors,
            [
                "roe",
                "roa",
                "gross_margin",
                "netprofit_margin",
                "roic",
                "cash_conversion",
                "accrual_ratio",
                "asset_turnover",
                "gross_profit_to_assets",
                "interest_coverage",
                "inventory_turnover",
                "receivable_turnover",
                "net_cash_position",
                "piotroski_f_score",
                "altman_z_score",
                "beneish_m_score",
                "debt_to_assets",
                "current_ratio",
                "quick_ratio",
                "cash_ratio",
            ],
        ),
    }


def get_growth_cashflow_factor_bundle(symbol: str) -> Dict[str, Any]:
    """获取股票的成长与现金流因子 bundle（growth_cashflow_core）。

    Args:
        symbol: A 股股票代码（6 位数字或含交易所前后缀）

    Returns:
        dict: 字段说明（合并 _base_snapshot 后还包括 symbol/name/industry/current_price/
            report_period/data_source）——
            bundle: 固定值 "growth_cashflow_core"
            factors: 成长与现金流因子字典，子字段：
                — revenue_yoy: 营收同比增速
                — net_profit_yoy: 净利润同比增速
                — oper_profit_yoy: 营业利润同比增速
                — revenue_cagr_3y: 营收 3 年复合增速
                — profit_cagr_3y: 净利润 3 年复合增速
                — revenue_ttm: TTM 营收
                — net_profit_ttm: TTM 净利润
                — n_cashflow_act: 经营活动现金流
                — fcf: 自由现金流（保守代理）
                — fcf_yield: 自由现金流收益率（百分比）
                — fcf_margin: 自由现金流利润率（百分比）
                — ocf_yield: 经营现金流收益率（百分比）
                — total_cur_assets: 流动资产
                — total_cur_liab: 流动负债
                — net_working_capital: 净营运资本
                — working_capital_change: 净营运资本变动额
            factor_warnings: 该 bundle 的告警字典
            calculation_notes: list[str]，计算口径说明
            missing_factors: list[str]，缺失的关键因子名列表
    """
    context = _build_context(symbol)
    latest_financial = context["latest_financial"]
    previous_financial = _previous_financial_record(context["financial_records"])
    revenue_yoy = _compute_yoy_growth(context["financial_records"], "revenue")
    net_profit_yoy = _compute_yoy_growth(context["financial_records"], "net_profit")
    oper_profit_yoy = _compute_yoy_growth(context["financial_records"], "oper_profit")
    revenue_cagr_3y = _compute_cagr(context["financial_records"], (("revenue_ttm",), ("revenue",), ("oper_rev",)), 3)
    profit_cagr_3y = _compute_cagr(context["financial_records"], (("net_profit_ttm",), ("net_profit",), ("net_income",)), 3)
    fcf = _estimate_fcf(latest_financial)
    market_cap = _to_float(
        _pick_first(
            context["market_quotes"].get("total_mv"),
            context["basic_info"].get("total_mv"),
            context["basic_info"].get("market_cap"),
        )
    )
    fcf_yield = (fcf / (market_cap * 100000000.0) * 100.0) if fcf is not None and market_cap not in (None, 0) else None

    total_cur_assets = _extract_financial_field(
        latest_financial,
        ("total_cur_assets",),
        ("balance_sheet", "total_cur_assets"),
    )
    total_cur_liab = _extract_financial_field(
        latest_financial,
        ("total_cur_liab",),
        ("balance_sheet", "total_cur_liab"),
    )
    net_working_capital = _extract_net_working_capital(latest_financial)
    previous_net_working_capital = _extract_net_working_capital(previous_financial)
    working_capital_change = None
    if net_working_capital is not None and previous_net_working_capital is not None:
        working_capital_change = net_working_capital - previous_net_working_capital

    revenue_base = _extract_financial_field(
        latest_financial,
        ("revenue_ttm",),
        ("revenue",),
        ("oper_rev",),
        ("income_statement", "revenue"),
        ("income_statement", "oper_rev"),
    )
    n_cashflow_act = _extract_financial_field(latest_financial, ("n_cashflow_act",), ("cashflow_statement", "n_cashflow_act"))
    fcf_margin = _safe_divide(fcf, revenue_base)
    if fcf_margin is not None:
        fcf_margin *= 100.0
    ocf_yield = (n_cashflow_act / (market_cap * 100000000.0) * 100.0) if n_cashflow_act is not None and market_cap not in (None, 0) else None

    factors = {
        "revenue_yoy": revenue_yoy,
        "net_profit_yoy": net_profit_yoy,
        "oper_profit_yoy": oper_profit_yoy,
        "revenue_cagr_3y": revenue_cagr_3y,
        "profit_cagr_3y": profit_cagr_3y,
        "revenue_ttm": _extract_financial_field(latest_financial, ("revenue_ttm",)),
        "net_profit_ttm": _extract_financial_field(latest_financial, ("net_profit_ttm",)),
        "n_cashflow_act": n_cashflow_act,
        "fcf": fcf,
        "fcf_yield": fcf_yield,
        "fcf_margin": fcf_margin,
        "ocf_yield": ocf_yield,
        "total_cur_assets": total_cur_assets,
        "total_cur_liab": total_cur_liab,
        "net_working_capital": net_working_capital,
        "working_capital_change": working_capital_change,
    }
    factor_warnings = _build_growth_factor_warnings(context, factors)

    return {
        **_base_snapshot(context),
        "bundle": "growth_cashflow_core",
        "factors": factors,
        "factor_warnings": factor_warnings,
        "calculation_notes": [
            "同比增速按最新报告期对上年同季报告期计算。",
            "fcf 暂按 n_cashflow_act + n_cashflow_inv_act 作为保守代理，fcf_yield 基于市值字段 total_mv 的亿元口径换算。",
            "fcf_margin 使用自由现金流/营收基础口径，working_capital_change 使用最近两期净营运资本差额。",
            "CAGR 使用同季三年前报告期做复合增速计算，缺少对应历史期时返回空。",
        ],
        "missing_factors": _find_missing(
            factors,
            [
                "revenue_yoy",
                "net_profit_yoy",
                "revenue_cagr_3y",
                "profit_cagr_3y",
                "revenue_ttm",
                "net_profit_ttm",
                "n_cashflow_act",
                "fcf_yield",
                "fcf_margin",
                "ocf_yield",
                "net_working_capital",
                "working_capital_change",
            ],
        ),
    }


def get_fundamental_factor_snapshot(symbol: str, allow_remote_fetch: bool = True) -> Dict[str, Any]:
    """聚合价值/质量/成长三个 bundle，返回基本面因子综合快照。

    Args:
        symbol: A 股股票代码（6 位数字或含交易所前后缀）
        allow_remote_fetch: 透传给价值 bundle 的股东回报指标；
            交互式接口（因子预览/财务明细页）应传 False，禁止现场拉取 Tushare

    Returns:
        dict: 字段说明——
            symbol: 标准化后的股票代码
            name: 股票名称
            industry: 所属行业
            current_price: 当前价格
            report_period: 报告期（优先 growth，其次 quality，最后 value）
            data_source: 数据源（优先级同 report_period）
            factors: dict，三个 bundle 因子的合并字典
            factor_diagnostics: dict，三个 bundle 因子诊断信息的合并字典
            factor_warnings: dict，三个 bundle 告警的合并字典
            missing_factors: list[str]，三个 bundle 缺失因子的去重升序列表
            bundles: 各 bundle 完整结果
                — value_core: dict，价值 bundle 完整结果
                — quality_core: dict，质量 bundle 完整结果
                — growth_cashflow_core: dict，成长与现金流 bundle 完整结果
    """
    value_bundle = get_value_factor_bundle(symbol, allow_remote_fetch=allow_remote_fetch)
    quality_bundle = get_quality_factor_bundle(symbol)
    growth_bundle = get_growth_cashflow_factor_bundle(symbol)

    factors = {
        **value_bundle["factors"],
        **quality_bundle["factors"],
        **growth_bundle["factors"],
    }
    factor_diagnostics = {
        **value_bundle.get("factor_diagnostics", {}),
        **quality_bundle.get("factor_diagnostics", {}),
        **growth_bundle.get("factor_diagnostics", {}),
    }
    factor_warnings = {
        **value_bundle.get("factor_warnings", {}),
        **quality_bundle.get("factor_warnings", {}),
        **growth_bundle.get("factor_warnings", {}),
    }

    return {
        "symbol": value_bundle["symbol"],
        "name": value_bundle.get("name"),
        "industry": value_bundle.get("industry"),
        "current_price": value_bundle.get("current_price"),
        "report_period": _pick_first(
            growth_bundle.get("report_period"),
            quality_bundle.get("report_period"),
            value_bundle.get("report_period"),
        ),
        "data_source": _pick_first(
            growth_bundle.get("data_source"),
            quality_bundle.get("data_source"),
            value_bundle.get("data_source"),
        ),
        "factors": factors,
        "factor_diagnostics": factor_diagnostics,
        "factor_warnings": factor_warnings,
        "missing_factors": sorted(
            set(
                value_bundle.get("missing_factors", [])
                + quality_bundle.get("missing_factors", [])
                + growth_bundle.get("missing_factors", [])
            )
        ),
        "bundles": {
            "value_core": value_bundle,
            "quality_core": quality_bundle,
            "growth_cashflow_core": growth_bundle,
        },
    }


__all__ = [
    "get_fundamental_factor_snapshot",
    "get_growth_cashflow_factor_bundle",
    "get_quality_factor_bundle",
    "get_value_factor_bundle",
]