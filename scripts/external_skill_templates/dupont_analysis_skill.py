"""A 股杜邦分析 external skill 模板。"""

from typing import Any, Dict, List, Optional

from core.skill_runtime.data_access import get_stock_basic_info, get_stock_financial_periods


def _safe_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_symbol(symbol: str) -> str:
    clean = str(symbol or "").strip()
    if not clean:
        raise ValueError("symbol 不能为空")
    digits = "".join(ch for ch in clean if ch.isdigit())
    if len(digits) != 6:
        raise ValueError("symbol 必须是 6 位 A 股代码")
    return digits


def _report_period(record: Dict[str, Any]) -> str:
    return str(record.get("report_period") or record.get("report_date") or "")


def _annualization_factor(report_period: str) -> float:
    period = str(report_period or "")
    if len(period) != 8:
        return 1.0
    month_day = period[4:8]
    if month_day == "0331":
        return 4.0
    if month_day == "0630":
        return 2.0
    if month_day == "0930":
        return 4.0 / 3.0
    return 1.0


def _average_value(current_value: Optional[float], previous_value: Optional[float]) -> Optional[float]:
    if current_value is None:
        return None
    if previous_value is None:
        return current_value
    return (current_value + previous_value) / 2.0


def _build_dupont_entry(current: Dict[str, Any], previous: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    report_period = _report_period(current)
    revenue = _safe_float(current.get("revenue"))
    total_assets = _safe_float(current.get("total_assets"))
    total_equity = _safe_float(current.get("total_equity"))
    previous_assets = _safe_float((previous or {}).get("total_assets"))
    previous_equity = _safe_float((previous or {}).get("total_equity"))

    average_assets = _average_value(total_assets, previous_assets)
    average_equity = _average_value(total_equity, previous_equity)
    annualization_factor = _annualization_factor(report_period)

    asset_turnover = None
    if revenue is not None and average_assets is not None and average_assets > 0:
        asset_turnover = (revenue * annualization_factor) / average_assets

    equity_multiplier = None
    if average_assets is not None and average_equity is not None and average_equity > 0:
        equity_multiplier = average_assets / average_equity

    roe = _safe_float(current.get("roe"))
    net_margin = _safe_float(current.get("netprofit_margin"))
    gross_margin = _safe_float(current.get("gross_margin"))

    formula_roe = None
    if net_margin is not None and asset_turnover is not None and equity_multiplier is not None:
        formula_roe = (net_margin / 100.0) * asset_turnover * equity_multiplier * 100.0

    roe_gap = None
    if roe is not None and formula_roe is not None:
        roe_gap = formula_roe - roe

    return {
        "report_period": report_period,
        "roe_percent": roe,
        "net_margin_percent": net_margin,
        "gross_margin_percent": gross_margin,
        "asset_turnover": asset_turnover,
        "equity_multiplier": equity_multiplier,
        "formula_roe_percent": formula_roe,
        "roe_gap_percent": roe_gap,
        "annualization_factor": annualization_factor,
        "revenue": revenue,
        "average_total_assets": average_assets,
        "average_total_equity": average_equity,
        "raw_total_assets": total_assets,
        "raw_total_equity": total_equity,
    }


def _build_summary(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    latest = entries[0] if entries else {}
    recent = entries[:4]
    valid_roe = [item.get("roe_percent") for item in recent if item.get("roe_percent") is not None]
    valid_turnover = [item.get("asset_turnover") for item in recent if item.get("asset_turnover") is not None]
    valid_margin = [item.get("net_margin_percent") for item in recent if item.get("net_margin_percent") is not None]

    return {
        "latest_report_period": latest.get("report_period"),
        "latest_reported_roe_percent": latest.get("roe_percent"),
        "latest_formula_roe_percent": latest.get("formula_roe_percent"),
        "latest_net_margin_percent": latest.get("net_margin_percent"),
        "latest_asset_turnover": latest.get("asset_turnover"),
        "latest_equity_multiplier": latest.get("equity_multiplier"),
        "recent_period_count": len(recent),
        "recent_roe_range_percent": [min(valid_roe), max(valid_roe)] if valid_roe else None,
        "recent_asset_turnover_range": [min(valid_turnover), max(valid_turnover)] if valid_turnover else None,
        "recent_net_margin_range_percent": [min(valid_margin), max(valid_margin)] if valid_margin else None,
    }


def analyze_a_share_dupont(symbol: str, periods: int = 8) -> Dict[str, Any]:
    """执行 A 股杜邦分析并返回结构化结果。"""
    normalized_symbol = _normalize_symbol(symbol)
    effective_periods = max(2, min(int(periods or 8), 12))

    basic_info = get_stock_basic_info(normalized_symbol) or {}
    financial_periods = get_stock_financial_periods(normalized_symbol, limit=effective_periods)
    if not financial_periods:
        return {
            "symbol": normalized_symbol,
            "status": "no_data",
            "message": "未获取到财务周期数据",
            "history": [],
            "summary": None,
            "warnings": ["get_stock_financial_periods 返回空结果"],
        }

    entries: List[Dict[str, Any]] = []
    for index, current in enumerate(financial_periods):
        previous = financial_periods[index + 1] if index + 1 < len(financial_periods) else None
        entries.append(_build_dupont_entry(current, previous))

    warnings: List[str] = []
    if any(item.get("average_total_assets") is None for item in entries):
        warnings.append("部分报告期缺少总资产，相关资产周转率无法计算")
    if any(item.get("average_total_equity") is None for item in entries):
        warnings.append("部分报告期缺少股东权益，相关权益乘数无法计算")
    if any(item.get("roe_gap_percent") is not None and abs(item.get("roe_gap_percent")) > 5 for item in entries):
        warnings.append("部分报告期的公式 ROE 与披露 ROE 存在较大差异，可能受平均口径、少数股东权益或指标定义影响")

    latest = entries[0]
    return {
        "symbol": normalized_symbol,
        "name": basic_info.get("name"),
        "industry": basic_info.get("industry"),
        "status": "ok",
        "analysis_scope": {
            "market": "A股",
            "periods_requested": effective_periods,
            "periods_returned": len(entries),
            "method": "ROE = 净利率 × 资产周转率 × 权益乘数",
            "notes": [
                "资产周转率按累计营收与平均总资产估算",
                "季度报告使用年化因子修正累计营收口径",
                "本结果仅提供财务结构拆解，不包含交易建议",
            ],
        },
        "latest_dupont": latest,
        "history": entries,
        "summary": _build_summary(entries),
        "warnings": warnings,
    }
