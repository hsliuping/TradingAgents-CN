"""通用金融数据处理能力。

这些函数提供结构化、可审计的标准数据能力，供 Agent 与生成的 Skill 复用。
原则：固定口径、结构化输出、显式覆盖率与 warnings，避免 LLM 从 Markdown 文本中自行抠数和计算。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from statistics import mean, median, pstdev
from typing import Any, Dict, List, Optional, Tuple

from .data_access import (
    _get_db,
    get_industry_peer_basic_info,
    get_market_quotes,
    get_stock_basic_info,
    get_stock_daily_quotes,
    get_stock_financial_periods,
    get_stock_news_by_date_range,
    summarize_industry_valuation,
)
from .project_access import get_external_historical_data, get_external_valuation_data
from .sync_wrappers import normalize_tabular_result, run_async_in_sync


def _normalize_symbol(symbol: str) -> str:
    text = str(symbol or "").strip().upper()
    for prefix in ("SH", "SZ", "SS", "BJ"):
        if text.startswith(prefix):
            text = text[len(prefix):]
    if "." in text:
        text = text.split(".", 1)[0]
    digits = "".join(ch for ch in text if ch.isdigit())
    return digits[-6:].zfill(6) if digits else ""


def _normalize_date(value: Any) -> str:
    text = str(value or "").strip()
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) >= 8:
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
    return text


def _date_digits(value: Any) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())[:8]


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _days_ago(days: int) -> str:
    return (datetime.now() - timedelta(days=max(1, int(days)))).strftime("%Y-%m-%d")


def _exchange_suffix(symbol: str) -> Optional[str]:
    if not symbol:
        return None
    if symbol.startswith(("6", "9")):
        return "SH"
    if symbol.startswith(("0", "2", "3")):
        return "SZ"
    if symbol.startswith(("4", "8")):
        return "BJ"
    return None


def _infer_listing_status(basic: Dict[str, Any]) -> str:
    for field in ("list_status", "listing_status", "status"):
        value = str(basic.get(field) or "").strip().upper()
        if value:
            if value in {"L", "LISTED", "上市"}:
                return "listed"
            if value in {"D", "DELISTED", "退市"}:
                return "delisted"
            if value in {"P", "PAUSED", "暂停上市"}:
                return "paused"
            return value.lower()
    return "listed" if basic else "unknown"


def _safe_float(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        numeric = float(value)
        if numeric != numeric:
            return None
        return numeric
    except (TypeError, ValueError):
        return None


def _safe_div(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def _pick_number(record: Dict[str, Any], *fields: str) -> Optional[float]:
    for field in fields:
        value = _safe_float(record.get(field))
        if value is not None:
            return value
    return None


def _period_year(period: Any) -> Optional[int]:
    text = "".join(ch for ch in str(period or "") if ch.isdigit())
    if len(text) >= 4:
        try:
            return int(text[:4])
        except ValueError:
            return None
    return None


def _is_annual_record(record: Dict[str, Any]) -> bool:
    period = "".join(ch for ch in str(record.get("report_period") or record.get("report_date") or "") if ch.isdigit())
    return period.endswith("1231") or str(record.get("report_type") or "").lower() == "annual"


def _dedupe_by_year(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_year: Dict[int, Dict[str, Any]] = {}
    for record in records:
        year = _period_year(record.get("report_period") or record.get("report_date"))
        if year is None:
            continue
        existing = by_year.get(year)
        if existing is None:
            by_year[year] = record
            continue
        existing_score = sum(1 for value in existing.values() if value not in (None, "", [], {}))
        candidate_score = sum(1 for value in record.values() if value not in (None, "", [], {}))
        if candidate_score >= existing_score:
            by_year[year] = record
    return [by_year[year] for year in sorted(by_year.keys(), reverse=True)]


def _percentile_rank(values: List[float], current: float) -> Optional[float]:
    valid = [value for value in values if value is not None and value > 0]
    if not valid:
        return None
    return sum(1 for value in valid if value <= current) / len(valid) * 100


def _percentile_rank_numeric(values: List[float], current: Optional[float]) -> Optional[float]:
    if current is None:
        return None
    valid = [float(value) for value in values if value is not None]
    if not valid:
        return None
    return sum(1 for value in valid if value <= current) / len(valid) * 100


def _growth_rate(current: Optional[float], previous: Optional[float]) -> Optional[float]:
    if current is None or previous is None or previous == 0:
        return None
    return (current - previous) / abs(previous)


def _series_stats(values: List[Optional[float]]) -> Dict[str, Any]:
    valid = [float(value) for value in values if value is not None]
    if not valid:
        return {"count": 0, "mean": None, "median": None, "min": None, "max": None, "stddev": None, "coefficient_of_variation": None}
    avg = mean(valid)
    std = pstdev(valid) if len(valid) > 1 else 0.0
    return {
        "count": len(valid),
        "mean": avg,
        "median": median(valid),
        "min": min(valid),
        "max": max(valid),
        "stddev": std,
        "coefficient_of_variation": _safe_div(std, abs(avg)) if avg else None,
    }


def _cagr(latest: Optional[float], earliest: Optional[float], periods: int) -> Optional[float]:
    if latest is None or earliest is None or earliest <= 0 or latest <= 0 or periods <= 0:
        return None
    return (latest / earliest) ** (1 / periods) - 1


def _positive_ratio(values: List[Optional[float]]) -> Optional[float]:
    valid = [value for value in values if value is not None]
    if not valid:
        return None
    return sum(1 for value in valid if value > 0) / len(valid)


def _normalize_metric_key(metric: str) -> str:
    return str(metric or "").strip().lower().replace("-", "_").replace(" ", "_")


def _to_tushare_ts_code(symbol: str) -> str:
    normalized = _normalize_symbol(symbol)
    if not normalized:
        return ""
    suffix = "SH" if normalized.startswith(("6", "9")) else "SZ"
    return f"{normalized}.{suffix}"


def _load_tushare_moneyflow_rows(symbol: str, start_date: str, end_date: str, limit: int) -> List[Dict[str, Any]]:
    try:
        from tradingagents.dataflows.providers.china.tushare import get_tushare_provider

        provider = get_tushare_provider()
        if not provider or not provider.is_available():
            return []
        result = run_async_in_sync(
            provider.get_moneyflow_ths(
                ts_code=_to_tushare_ts_code(symbol),
                start_date=_date_digits(start_date),
                end_date=_date_digits(end_date),
            )
        )
        rows = normalize_tabular_result(result) or []
    except Exception:
        return []

    normalized_symbol = _normalize_symbol(symbol)
    filtered = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        row_symbol = _normalize_symbol(row.get("ts_code") or row.get("symbol") or row.get("code"))
        if row_symbol and row_symbol != normalized_symbol:
            continue
        filtered.append(row)

    filtered.sort(key=lambda item: str(item.get("trade_date") or item.get("date") or ""))
    return filtered[:max(1, min(int(limit or 120), 1000))]


def _load_tushare_industry_moneyflow_rows(start_date: str, end_date: str, limit: int) -> List[Dict[str, Any]]:
    try:
        from tradingagents.dataflows.providers.china.tushare import get_tushare_provider

        provider = get_tushare_provider()
        if not provider or not provider.is_available():
            return []
        result = run_async_in_sync(
            provider.get_moneyflow_ind_ths(
                start_date=_date_digits(start_date),
                end_date=_date_digits(end_date),
            )
        )
        rows = normalize_tabular_result(result) or []
    except Exception:
        return []

    filtered = [row for row in rows if isinstance(row, dict)]
    filtered.sort(key=lambda item: str(item.get("trade_date") or item.get("date") or ""), reverse=True)
    return filtered[:max(1, min(int(limit or 200), 1000))]


def _load_tushare_dividend_rows(symbol: str, limit: int) -> List[Dict[str, Any]]:
    try:
        from tradingagents.dataflows.providers.china.tushare import get_tushare_provider

        provider = get_tushare_provider()
        if not provider or not provider.is_available():
            return []
        result = run_async_in_sync(provider.get_dividend_data(symbol, limit=max(1, min(int(limit or 20), 100))))
        rows = normalize_tabular_result(result) or []
    except Exception:
        return []
    return [row for row in rows if isinstance(row, dict)]


def _read_local_collection_rows(collection_names: List[str], query: Dict[str, Any], limit: int = 200, sort_field: str = "trade_date") -> Tuple[List[Dict[str, Any]], Optional[str]]:
    db = _get_db()
    for collection_name in collection_names:
        try:
            rows = list(db[collection_name].find(query, {"_id": 0}).sort(sort_field, -1).limit(max(1, min(int(limit or 200), 1000))))
            if rows:
                return rows, collection_name
        except Exception:
            continue
    return [], None


def _extract_quote_value(record: Dict[str, Any], *fields: str) -> Optional[float]:
    return _pick_number(record, *fields)


def _sort_price_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(rows, key=lambda row: _date_digits(row.get("trade_date") or row.get("date") or row.get("datetime") or row.get("index")))


def _normalize_price_row(row: Dict[str, Any]) -> Dict[str, Any]:
    close = _extract_quote_value(row, "close", "price", "last_price")
    pre_close = _extract_quote_value(row, "pre_close", "prev_close")
    pct_chg = _extract_quote_value(row, "pct_chg", "change_pct")
    return {
        "trade_date": _normalize_date(row.get("trade_date") or row.get("date") or row.get("datetime") or row.get("index")),
        "open": _extract_quote_value(row, "open"),
        "high": _extract_quote_value(row, "high"),
        "low": _extract_quote_value(row, "low"),
        "close": close,
        "pre_close": pre_close,
        "volume": _extract_quote_value(row, "volume", "vol"),
        "amount": _extract_quote_value(row, "amount"),
        "turnover_rate": _extract_quote_value(row, "turnover_rate", "turnover"),
        "pct_chg": pct_chg,
        "data_source": row.get("data_source") or row.get("source"),
    }


def get_security_master(symbol: str) -> Dict[str, Any]:
    """返回统一证券主数据。"""
    normalized_symbol = _normalize_symbol(symbol)
    basic = get_stock_basic_info(normalized_symbol) or {}
    quote = get_market_quotes(normalized_symbol) or {}
    exchange = basic.get("exchange") or basic.get("market") or _exchange_suffix(normalized_symbol)
    name = basic.get("name") or quote.get("name")
    warnings: List[str] = []
    if not basic:
        warnings.append("未在 stock_basic_info 中找到证券基础信息。")
    return {
        "status": "success" if basic or quote else "no_data",
        "symbol": normalized_symbol,
        "ts_code": basic.get("ts_code") or (f"{normalized_symbol}.{exchange}" if exchange else None),
        "name": name,
        "exchange": exchange,
        "industry": basic.get("industry") or basic.get("sw_industry") or basic.get("sector"),
        "area": basic.get("area"),
        "list_date": _normalize_date(basic.get("list_date") or basic.get("listing_date")),
        "listing_status": _infer_listing_status(basic),
        "is_st": bool("ST" in str(name or "").upper()),
        "market_cap": _pick_number(basic, "total_mv", "market_cap", "market_value"),
        "float_market_cap": _pick_number(basic, "circ_mv", "float_market_cap"),
        "data_source": basic.get("source") or basic.get("data_source") or quote.get("source") or quote.get("data_source"),
        "coverage": {
            "has_basic_info": bool(basic),
            "has_market_quote": bool(quote),
        },
        "warnings": warnings,
    }


def get_adjusted_price_series(
    symbol: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    period: str = "daily",
    limit: int = 1000,
) -> Dict[str, Any]:
    """返回标准化价格序列。当前优先使用本地日线，若本地已复权则透传复权价。"""
    normalized_symbol = _normalize_symbol(symbol)
    end = end_date or _today()
    start = start_date or _days_ago(365 * 3)
    rows = get_stock_daily_quotes(normalized_symbol, start, end, period=period, limit=max(1, min(int(limit or 1000), 3000)))
    data_source = "local"
    if not rows:
        external = get_external_historical_data(normalized_symbol, start, end, period=period)
        external_rows = external.get("data") if isinstance(external, dict) else []
        if isinstance(external_rows, list) and external_rows:
            rows = external_rows[: max(1, min(int(limit or 1000), 3000))]
            data_source = str(external.get("source") or "external")
    records = [_normalize_price_row(row) for row in _sort_price_rows(rows)]
    records = [row for row in records if row.get("trade_date") and row.get("close") is not None]
    warnings: List[str] = []
    if not records:
        warnings.append("未获取到有效价格序列。")
    if len(records) >= max(1, min(int(limit or 1000), 3000)):
        warnings.append("价格序列可能受 limit 截断。")
    return {
        "status": "success" if records else "no_data",
        "symbol": normalized_symbol,
        "period": period,
        "adjustment": "as_stored",
        "data_source": data_source,
        "window": {"start": start, "end": end},
        "records": records,
        "coverage": {"sample_count": len(records)},
        "warnings": warnings,
    }


def _rolling_mean(values: List[Optional[float]], window: int) -> List[Optional[float]]:
    result: List[Optional[float]] = []
    for index in range(len(values)):
        subset = [value for value in values[max(0, index - window + 1): index + 1] if value is not None]
        result.append(mean(subset) if len(subset) >= min(window, index + 1) and subset else None)
    return result


def _rolling_std(values: List[Optional[float]], window: int) -> List[Optional[float]]:
    result: List[Optional[float]] = []
    for index in range(len(values)):
        subset = [value for value in values[max(0, index - window + 1): index + 1] if value is not None]
        result.append(pstdev(subset) if len(subset) >= 2 else None)
    return result


def _ema_series(values: List[Optional[float]], span: int) -> List[Optional[float]]:
    alpha = 2 / (span + 1)
    result: List[Optional[float]] = []
    previous: Optional[float] = None
    for value in values:
        if value is None:
            result.append(previous)
            continue
        previous = value if previous is None else alpha * value + (1 - alpha) * previous
        result.append(previous)
    return result


def _latest_valid(records: List[Dict[str, Any]], field: str) -> Optional[float]:
    for row in reversed(records):
        value = _safe_float(row.get(field))
        if value is not None:
            return value
    return None


def get_return_series(
    symbol: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    period: str = "daily",
    limit: int = 1000,
) -> Dict[str, Any]:
    """基于价格序列返回收益率序列。"""
    price = get_adjusted_price_series(symbol, start_date=start_date, end_date=end_date, period=period, limit=limit)
    records = price.get("records") or []
    returns: List[Dict[str, Any]] = []
    previous_close: Optional[float] = None
    for row in records:
        close = _safe_float(row.get("close"))
        ret = _safe_div(close - previous_close, previous_close) if close is not None and previous_close else None
        returns.append({
            "trade_date": row.get("trade_date"),
            "close": close,
            "return": ret,
            "return_pct": ret * 100 if ret is not None else None,
        })
        if close is not None and close > 0:
            previous_close = close
    valid_returns = [item.get("return") for item in returns if item.get("return") is not None]
    return {
        "status": "success" if valid_returns else price.get("status"),
        "symbol": price.get("symbol"),
        "period": period,
        "window": price.get("window"),
        "records": returns,
        "summary": _series_stats(valid_returns),
        "coverage": {"price_sample_count": len(records), "return_sample_count": len(valid_returns)},
        "warnings": list(price.get("warnings") or []),
    }


def get_technical_indicator_series(
    symbol: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    indicators: Optional[List[str]] = None,
    limit: int = 300,
) -> Dict[str, Any]:
    """基于标准价格序列计算结构化技术指标历史序列。"""
    requested = {_normalize_metric_key(item) for item in (indicators or ["ma", "macd", "rsi", "kdj", "boll", "atr", "obv", "support_resistance"])}
    price = get_adjusted_price_series(symbol, start_date=start_date, end_date=end_date, limit=max(80, min(int(limit or 300), 1000)))
    rows = price.get("records") or []
    closes = [_safe_float(row.get("close")) for row in rows]
    highs = [_safe_float(row.get("high")) for row in rows]
    lows = [_safe_float(row.get("low")) for row in rows]
    volumes = [_safe_float(row.get("volume")) for row in rows]

    ma5 = _rolling_mean(closes, 5)
    ma10 = _rolling_mean(closes, 10)
    ma20 = _rolling_mean(closes, 20)
    ma60 = _rolling_mean(closes, 60)
    ema12 = _ema_series(closes, 12)
    ema26 = _ema_series(closes, 26)
    dif = [(a - b) if a is not None and b is not None else None for a, b in zip(ema12, ema26)]
    dea = _ema_series(dif, 9)
    macd_hist = [((d - e) * 2) if d is not None and e is not None else None for d, e in zip(dif, dea)]

    returns = [None]
    gains: List[Optional[float]] = [None]
    losses: List[Optional[float]] = [None]
    for index in range(1, len(closes)):
        current = closes[index]
        previous = closes[index - 1]
        change = current - previous if current is not None and previous is not None else None
        returns.append(_safe_div(change, previous) if change is not None and previous else None)
        gains.append(max(change, 0) if change is not None else None)
        losses.append(abs(min(change, 0)) if change is not None else None)
    avg_gain = _rolling_mean(gains, 14)
    avg_loss = _rolling_mean(losses, 14)
    rsi14 = []
    for gain, loss in zip(avg_gain, avg_loss):
        if gain is None or loss is None:
            rsi14.append(None)
        elif loss == 0:
            rsi14.append(100.0)
        else:
            rs = gain / loss
            rsi14.append(100 - 100 / (1 + rs))

    boll_mid = ma20
    boll_std = _rolling_std(closes, 20)
    boll_upper = [(mid + 2 * std) if mid is not None and std is not None else None for mid, std in zip(boll_mid, boll_std)]
    boll_lower = [(mid - 2 * std) if mid is not None and std is not None else None for mid, std in zip(boll_mid, boll_std)]

    kdj_k: List[Optional[float]] = []
    kdj_d: List[Optional[float]] = []
    k_value: Optional[float] = 50.0
    d_value: Optional[float] = 50.0
    for index in range(len(rows)):
        low_window = [value for value in lows[max(0, index - 8): index + 1] if value is not None]
        high_window = [value for value in highs[max(0, index - 8): index + 1] if value is not None]
        close = closes[index]
        if close is None or not low_window or not high_window or max(high_window) == min(low_window):
            kdj_k.append(k_value)
            kdj_d.append(d_value)
            continue
        rsv = (close - min(low_window)) / (max(high_window) - min(low_window)) * 100
        k_value = (2 / 3) * (k_value or 50) + (1 / 3) * rsv
        d_value = (2 / 3) * (d_value or 50) + (1 / 3) * k_value
        kdj_k.append(k_value)
        kdj_d.append(d_value)
    kdj_j = [(3 * k - 2 * d) if k is not None and d is not None else None for k, d in zip(kdj_k, kdj_d)]

    true_ranges: List[Optional[float]] = []
    obv: List[Optional[float]] = []
    running_obv = 0.0
    for index, row in enumerate(rows):
        high = highs[index]
        low = lows[index]
        close = closes[index]
        previous_close = closes[index - 1] if index > 0 else None
        tr_candidates = []
        if high is not None and low is not None:
            tr_candidates.append(high - low)
        if high is not None and previous_close is not None:
            tr_candidates.append(abs(high - previous_close))
        if low is not None and previous_close is not None:
            tr_candidates.append(abs(low - previous_close))
        true_ranges.append(max(tr_candidates) if tr_candidates else None)
        volume = volumes[index] or 0
        if index > 0 and close is not None and previous_close is not None:
            if close > previous_close:
                running_obv += volume
            elif close < previous_close:
                running_obv -= volume
        obv.append(running_obv)
    atr14 = _rolling_mean(true_ranges, 14)
    support_20 = [min([value for value in lows[max(0, index - 19): index + 1] if value is not None], default=None) for index in range(len(rows))]
    resistance_20 = [max([value for value in highs[max(0, index - 19): index + 1] if value is not None], default=None) for index in range(len(rows))]

    records: List[Dict[str, Any]] = []
    for index, row in enumerate(rows):
        item: Dict[str, Any] = {"trade_date": row.get("trade_date"), "close": closes[index]}
        if "ma" in requested or "moving_average" in requested:
            item.update({"ma5": ma5[index], "ma10": ma10[index], "ma20": ma20[index], "ma60": ma60[index]})
        if "macd" in requested:
            item.update({"dif": dif[index], "dea": dea[index], "macd_hist": macd_hist[index]})
        if "rsi" in requested or "rsi14" in requested:
            item["rsi14"] = rsi14[index]
        if "kdj" in requested:
            item.update({"kdj_k": kdj_k[index], "kdj_d": kdj_d[index], "kdj_j": kdj_j[index]})
        if "boll" in requested or "bollinger" in requested:
            item.update({"boll_mid": boll_mid[index], "boll_upper": boll_upper[index], "boll_lower": boll_lower[index]})
        if "atr" in requested or "atr14" in requested:
            item["atr14"] = atr14[index]
        if "obv" in requested:
            item["obv"] = obv[index]
        if "support_resistance" in requested or "support" in requested or "resistance" in requested:
            item.update({"support_20": support_20[index], "resistance_20": resistance_20[index]})
        records.append(item)

    latest = records[-1] if records else {}
    warnings = list(price.get("warnings") or [])
    if len(records) < 60:
        warnings.append("价格样本少于 60 条，MA60 等中期指标参考价值有限。")
    return {
        "status": "success" if records else "no_data",
        "symbol": price.get("symbol"),
        "window": price.get("window"),
        "data_source": price.get("data_source"),
        "indicators": sorted(requested),
        "records": records[-max(1, min(int(limit or 300), 1000)):],
        "latest": latest,
        "summary": {
            "sample_count": len(records),
            "latest_close": latest.get("close"),
            "latest_ma20": latest.get("ma20"),
            "latest_atr14": latest.get("atr14"),
            "latest_boll_position": _safe_div((latest.get("close") - latest.get("boll_lower")) if latest.get("close") is not None and latest.get("boll_lower") is not None else None, (latest.get("boll_upper") - latest.get("boll_lower")) if latest.get("boll_upper") is not None and latest.get("boll_lower") is not None else None),
            "latest_support_20": latest.get("support_20"),
            "latest_resistance_20": latest.get("resistance_20"),
        },
        "warnings": warnings,
    }


def get_volatility_metrics(
    symbol: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    period: str = "daily",
    limit: int = 1000,
) -> Dict[str, Any]:
    """返回收益率波动率指标。"""
    returns = get_return_series(symbol, start_date=start_date, end_date=end_date, period=period, limit=limit)
    values = [item.get("return") for item in returns.get("records", []) if item.get("return") is not None]
    valid = [float(value) for value in values]
    trading_days = 252 if period == "daily" else 52 if period == "weekly" else 12
    daily_vol = pstdev(valid) if len(valid) > 1 else None
    annualized = daily_vol * (trading_days ** 0.5) if daily_vol is not None else None
    return {
        "status": "success" if daily_vol is not None else "insufficient_data",
        "symbol": returns.get("symbol"),
        "period": period,
        "window": returns.get("window"),
        "metrics": {
            "volatility": daily_vol,
            "volatility_pct": daily_vol * 100 if daily_vol is not None else None,
            "annualized_volatility": annualized,
            "annualized_volatility_pct": annualized * 100 if annualized is not None else None,
            "sample_count": len(valid),
        },
        "warnings": list(returns.get("warnings") or []) + ([] if len(valid) >= 20 else ["有效收益率样本少于 20 个，波动率参考价值有限。"]),
    }


def get_drawdown_metrics(
    symbol: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    period: str = "daily",
    limit: int = 1000,
) -> Dict[str, Any]:
    """返回最大回撤和回撤序列。"""
    price = get_adjusted_price_series(symbol, start_date=start_date, end_date=end_date, period=period, limit=limit)
    peak: Optional[float] = None
    peak_date: Optional[str] = None
    max_drawdown: Optional[float] = None
    max_drawdown_start: Optional[str] = None
    max_drawdown_end: Optional[str] = None
    series: List[Dict[str, Any]] = []
    for row in price.get("records", []):
        close = _safe_float(row.get("close"))
        if close is None or close <= 0:
            continue
        trade_date = row.get("trade_date")
        if peak is None or close > peak:
            peak = close
            peak_date = trade_date
        drawdown = _safe_div(close - peak, peak) if peak else None
        series.append({"trade_date": trade_date, "close": close, "peak": peak, "drawdown": drawdown, "drawdown_pct": drawdown * 100 if drawdown is not None else None})
        if drawdown is not None and (max_drawdown is None or drawdown < max_drawdown):
            max_drawdown = drawdown
            max_drawdown_start = peak_date
            max_drawdown_end = trade_date
    return {
        "status": "success" if max_drawdown is not None else "insufficient_data",
        "symbol": price.get("symbol"),
        "period": period,
        "window": price.get("window"),
        "metrics": {
            "max_drawdown": max_drawdown,
            "max_drawdown_pct": max_drawdown * 100 if max_drawdown is not None else None,
            "max_drawdown_start": max_drawdown_start,
            "max_drawdown_end": max_drawdown_end,
            "sample_count": len(series),
        },
        "drawdown_series": series,
        "warnings": list(price.get("warnings") or []),
    }


def get_historical_financial_annual_series(
    symbol: str,
    years: int = 10,
    source: Optional[str] = None,
) -> Dict[str, Any]:
    """返回单只 A 股最近 N 年完整年报财务序列。"""
    normalized_symbol = _normalize_symbol(symbol)
    requested_years = max(1, min(int(years or 10), 15))
    fetch_limit = max(requested_years * 4 + 8, 40)
    records = get_stock_financial_periods(normalized_symbol, source=source, limit=fetch_limit)
    annual_records = _dedupe_by_year([record for record in records if _is_annual_record(record)])[:requested_years]

    output_records: List[Dict[str, Any]] = []
    for record in annual_records:
        period = str(record.get("report_period") or record.get("report_date") or "")
        year = _period_year(period)
        revenue = _pick_number(record, "revenue", "oper_rev")
        net_profit = _pick_number(record, "net_profit", "n_income_attr_p", "net_income")
        operating_cashflow = _pick_number(record, "n_cashflow_act")
        total_assets = _pick_number(record, "total_assets")
        total_liab = _pick_number(record, "total_liab")
        total_equity = _pick_number(record, "total_equity", "total_hldr_eqy_exc_min_int", "total_hldr_eqy_inc_min_int")
        capex = _pick_number(record, "capex", "c_pay_acq_const_fiolta", "c_pay_acq_const_fiolta")
        free_cashflow = operating_cashflow - capex if operating_cashflow is not None and capex is not None else None
        output_records.append({
            "year": year,
            "report_period": period,
            "ann_date": record.get("ann_date"),
            "revenue": revenue,
            "net_profit": net_profit,
            "roe": _pick_number(record, "roe", "roe_avg", "roe_waa"),
            "roa": _pick_number(record, "roa", "roa2"),
            "roic": _pick_number(record, "roic", "invested_capital_return"),
            "gross_margin": _pick_number(record, "gross_margin", "grossprofit_margin"),
            "netprofit_margin": _pick_number(record, "netprofit_margin"),
            "operating_margin": _pick_number(record, "operating_margin", "operate_profit_margin"),
            "expense_ratio": _pick_number(record, "expense_ratio") or _safe_div(
                sum(value for value in (
                    _pick_number(record, "oper_exp", "sell_exp"),
                    _pick_number(record, "admin_exp"),
                    _pick_number(record, "fin_exp"),
                ) if value is not None),
                revenue,
            ),
            "asset_turnover": _pick_number(record, "asset_turnover", "assets_turn"),
            "equity_multiplier": _safe_div(total_assets, total_equity),
            "operating_cashflow": operating_cashflow,
            "free_cashflow": free_cashflow,
            "total_assets": total_assets,
            "total_liab": total_liab,
            "total_equity": total_equity,
            "debt_to_assets": _pick_number(record, "debt_to_assets") or (_safe_div(total_liab, total_assets) * 100 if _safe_div(total_liab, total_assets) is not None else None),
            "data_source": record.get("source") or record.get("data_source"),
        })

    years_present = [item["year"] for item in output_records if item.get("year")]
    latest_year = max(years_present) if years_present else None
    expected_years = list(range(latest_year, latest_year - requested_years, -1)) if latest_year else []
    missing_years = [year for year in expected_years if year not in years_present]
    warnings: List[str] = []
    if len(output_records) < requested_years:
        warnings.append(f"仅获取到 {len(output_records)} 个年报期，少于请求的 {requested_years} 年。")
    if missing_years:
        warnings.append(f"缺少年报年份: {missing_years}")

    return {
        "status": "success" if output_records else "no_data",
        "symbol": normalized_symbol,
        "requested_years": requested_years,
        "records": output_records,
        "coverage": {
            "requested_years": requested_years,
            "available_years": len(output_records),
            "missing_years": missing_years,
        },
        "warnings": warnings,
    }


def get_profitability_stability_metrics(symbol: str, years: int = 10, source: Optional[str] = None) -> Dict[str, Any]:
    """基于年报序列计算盈利稳定性指标。"""
    series = get_historical_financial_annual_series(symbol, years=years, source=source)
    records = series.get("records") or []
    revenue_values = [item.get("revenue") for item in records]
    profit_values = [item.get("net_profit") for item in records]
    roe_values = [item.get("roe") for item in records]
    gross_margin_values = [item.get("gross_margin") for item in records]

    revenue_growth: List[Optional[float]] = []
    profit_growth: List[Optional[float]] = []
    for index, current in enumerate(records[:-1]):
        previous = records[index + 1]
        revenue_growth.append(_growth_rate(current.get("revenue"), previous.get("revenue")))
        profit_growth.append(_growth_rate(current.get("net_profit"), previous.get("net_profit")))

    warnings = list(series.get("warnings") or [])
    if len(records) < 5:
        warnings.append("有效年报样本少于 5 年，稳定性指标参考价值有限。")

    return {
        "status": series.get("status"),
        "symbol": series.get("symbol"),
        "years_used": len(records),
        "coverage": series.get("coverage"),
        "metrics": {
            "revenue": _series_stats(revenue_values),
            "net_profit": _series_stats(profit_values),
            "roe": _series_stats(roe_values),
            "gross_margin": _series_stats(gross_margin_values),
            "revenue_growth_yoy": _series_stats(revenue_growth),
            "net_profit_growth_yoy": _series_stats(profit_growth),
        },
        "trend_series": {
            "revenue": revenue_values,
            "net_profit": profit_values,
            "roe": roe_values,
            "gross_margin": gross_margin_values,
            "revenue_growth_yoy": revenue_growth,
            "net_profit_growth_yoy": profit_growth,
        },
        "warnings": warnings,
    }


def get_cashflow_quality_trend(symbol: str, years: int = 10, source: Optional[str] = None) -> Dict[str, Any]:
    """基于年报序列计算现金流质量趋势。"""
    series = get_historical_financial_annual_series(symbol, years=years, source=source)
    records = series.get("records") or []
    trend: List[Dict[str, Any]] = []
    for item in records:
        net_profit = item.get("net_profit")
        ocf = item.get("operating_cashflow")
        fcf = item.get("free_cashflow")
        revenue = item.get("revenue")
        trend.append({
            "year": item.get("year"),
            "report_period": item.get("report_period"),
            "net_profit": net_profit,
            "operating_cashflow": ocf,
            "free_cashflow": fcf,
            "ocf_to_net_profit": _safe_div(ocf, net_profit),
            "fcf_to_net_profit": _safe_div(fcf, net_profit),
            "ocf_margin": _safe_div(ocf, revenue),
            "fcf_margin": _safe_div(fcf, revenue),
        })

    return {
        "status": series.get("status"),
        "symbol": series.get("symbol"),
        "years_used": len(records),
        "coverage": series.get("coverage"),
        "trend": trend,
        "summary": {
            "ocf_to_net_profit": _series_stats([item.get("ocf_to_net_profit") for item in trend]),
            "fcf_to_net_profit": _series_stats([item.get("fcf_to_net_profit") for item in trend]),
            "ocf_margin": _series_stats([item.get("ocf_margin") for item in trend]),
            "fcf_margin": _series_stats([item.get("fcf_margin") for item in trend]),
        },
        "warnings": list(series.get("warnings") or []),
    }


def get_historical_valuation_percentile(
    symbol: str,
    metrics: Optional[List[str]] = None,
    lookback_years: int = 5,
    as_of_date: Optional[str] = None,
) -> Dict[str, Any]:
    """返回结构化历史估值分位。"""
    normalized_symbol = _normalize_symbol(symbol)
    requested_metrics = [str(item).strip().lower() for item in (metrics or ["pe_ttm", "pb", "ps_ttm"]) if str(item).strip()]
    metric_alias = {
        "pe": "pe_ttm",
        "pe_ttm": "pe_ttm",
        "pb": "pb_mrq",
        "pb_mrq": "pb_mrq",
        "ps": "ps_ttm",
        "ps_ttm": "ps_ttm",
        "pcf": "pcf_ttm",
        "pcf_ttm": "pcf_ttm",
    }
    lookback = max(1, min(int(lookback_years or 5), 15))
    end_date = as_of_date or datetime.now().strftime("%Y-%m-%d")
    try:
        end_dt = datetime.strptime(end_date[:10], "%Y-%m-%d")
    except Exception:
        end_dt = datetime.now()
        end_date = end_dt.strftime("%Y-%m-%d")
    start_dt = end_dt - timedelta(days=365 * lookback)
    start_date = start_dt.strftime("%Y-%m-%d")

    valuation_result = get_external_valuation_data(normalized_symbol, start_date, end_date)
    rows = valuation_result.get("data") if isinstance(valuation_result, dict) else []
    if not isinstance(rows, list):
        rows = []
    sorted_rows = sorted([row for row in rows if isinstance(row, dict)], key=lambda row: str(row.get("date") or row.get("trade_date") or ""), reverse=True)

    metric_results: Dict[str, Any] = {}
    warnings: List[str] = []
    for requested_metric in requested_metrics:
        field = metric_alias.get(requested_metric)
        if not field:
            metric_results[requested_metric] = {"status": "unsupported_metric", "field": None}
            warnings.append(f"不支持的估值指标: {requested_metric}")
            continue
        valid_points: List[Dict[str, Any]] = []
        for row in sorted_rows:
            value = _safe_float(row.get(field))
            if value is not None and value > 0:
                valid_points.append({"date": row.get("date") or row.get("trade_date"), "value": value})
        if not valid_points:
            metric_results[requested_metric] = {"status": "no_data", "field": field, "sample_count": 0}
            warnings.append(f"{requested_metric} 无有效历史估值样本。")
            continue
        current = valid_points[0]
        values = [point["value"] for point in valid_points]
        percentile = _percentile_rank(values, current["value"])
        metric_results[requested_metric] = {
            "status": "success" if len(valid_points) >= 60 else "insufficient_samples",
            "field": field,
            "current_value": current["value"],
            "current_date": current["date"],
            "median": median(values),
            "average": mean(values),
            "min": min(values),
            "max": max(values),
            "percentile": percentile,
            "sample_count": len(valid_points),
        }
        if len(valid_points) < 60:
            warnings.append(f"{requested_metric} 有效样本不足 60 个，分位数参考价值有限。")

    return {
        "status": "success" if any(item.get("status") == "success" for item in metric_results.values()) else "partial_or_no_data",
        "symbol": normalized_symbol,
        "window": {"start": start_date, "end": end_date, "lookback_years": lookback},
        "data_source": valuation_result.get("source") if isinstance(valuation_result, dict) else None,
        "metrics": metric_results,
        "warnings": warnings,
    }


def get_current_valuation_snapshot(symbol: str) -> Dict[str, Any]:
    """返回当前估值快照。"""
    normalized_symbol = _normalize_symbol(symbol)
    basic = get_stock_basic_info(normalized_symbol) or {}
    quote = get_market_quotes(normalized_symbol) or {}
    return {
        "status": "success" if basic or quote else "no_data",
        "symbol": normalized_symbol,
        "name": basic.get("name") or quote.get("name"),
        "industry": basic.get("industry"),
        "trade_date": quote.get("trade_date") or basic.get("trade_date"),
        "current_price": _pick_number(quote, "close", "price", "last_price") or _pick_number(basic, "close", "current_price"),
        "metrics": {
            "pe": _pick_number(basic, "pe", "pe_ttm"),
            "pe_ttm": _pick_number(basic, "pe_ttm", "pe"),
            "pb": _pick_number(basic, "pb", "pb_mrq"),
            "pb_mrq": _pick_number(basic, "pb_mrq", "pb"),
            "ps": _pick_number(basic, "ps", "ps_ttm"),
            "ps_ttm": _pick_number(basic, "ps_ttm", "ps"),
            "peg": _pick_number(basic, "peg"),
            "dividend_yield": _pick_number(basic, "dividend_yield", "dv_ttm"),
            "total_mv": _pick_number(basic, "total_mv", "market_cap", "market_value"),
        },
        "data_source": basic.get("source") or basic.get("data_source") or quote.get("source") or quote.get("data_source"),
        "warnings": [] if basic else ["未在 stock_basic_info 中找到估值快照。"],
    }


def get_debt_solvency_trend(symbol: str, years: int = 10, source: Optional[str] = None) -> Dict[str, Any]:
    """返回偿债能力长期趋势。"""
    series = get_historical_financial_annual_series(symbol, years=years, source=source)
    trend: List[Dict[str, Any]] = []
    raw_records = get_stock_financial_periods(_normalize_symbol(symbol), source=source, limit=max(int(years or 10) * 4 + 8, 40))
    raw_by_period = {str(item.get("report_period") or item.get("report_date") or ""): item for item in raw_records}
    for item in series.get("records") or []:
        raw = raw_by_period.get(str(item.get("report_period") or ""), {})
        total_liab = item.get("total_liab")
        total_equity = item.get("total_equity")
        ocf = item.get("operating_cashflow")
        trend.append({
            "year": item.get("year"),
            "report_period": item.get("report_period"),
            "total_assets": item.get("total_assets"),
            "total_liab": total_liab,
            "total_equity": total_equity,
            "debt_to_assets": item.get("debt_to_assets"),
            "current_ratio": _pick_number(raw, "current_ratio"),
            "quick_ratio": _pick_number(raw, "quick_ratio"),
            "cash_ratio": _pick_number(raw, "cash_ratio"),
            "debt_to_equity": _safe_div(total_liab, total_equity),
            "ocf_to_total_liab": _safe_div(ocf, total_liab),
        })
    debt_values = [item.get("debt_to_assets") for item in trend]
    return {
        "status": series.get("status"),
        "symbol": series.get("symbol"),
        "years_used": len(trend),
        "coverage": series.get("coverage"),
        "trend": trend,
        "summary": {
            "debt_to_assets": _series_stats(debt_values),
            "debt_to_equity": _series_stats([item.get("debt_to_equity") for item in trend]),
            "ocf_to_total_liab": _series_stats([item.get("ocf_to_total_liab") for item in trend]),
        },
        "warnings": list(series.get("warnings") or []),
    }


def get_margin_stability_metrics(symbol: str, years: int = 10, source: Optional[str] = None) -> Dict[str, Any]:
    """返回利润率稳定性指标。"""
    series = get_historical_financial_annual_series(symbol, years=years, source=source)
    records = series.get("records") or []
    metrics = {
        "gross_margin": _series_stats([item.get("gross_margin") for item in records]),
        "netprofit_margin": _series_stats([item.get("netprofit_margin") for item in records]),
        "operating_margin": _series_stats([item.get("operating_margin") for item in records]),
        "expense_ratio": _series_stats([item.get("expense_ratio") for item in records]),
    }
    trend = [
        {
            "year": item.get("year"),
            "report_period": item.get("report_period"),
            "gross_margin": item.get("gross_margin"),
            "netprofit_margin": item.get("netprofit_margin"),
            "operating_margin": item.get("operating_margin"),
            "expense_ratio": item.get("expense_ratio"),
        }
        for item in records
    ]
    warnings = list(series.get("warnings") or [])
    if len(records) < 5:
        warnings.append("有效年报样本少于 5 年，利润率稳定性参考价值有限。")
    return {
        "status": series.get("status"),
        "symbol": series.get("symbol"),
        "years_used": len(records),
        "coverage": series.get("coverage"),
        "trend": trend,
        "metrics": metrics,
        "warnings": warnings,
    }


def get_capital_efficiency_trend(symbol: str, years: int = 10, source: Optional[str] = None) -> Dict[str, Any]:
    """返回资本效率长期趋势。"""
    series = get_historical_financial_annual_series(symbol, years=years, source=source)
    records = series.get("records") or []
    trend: List[Dict[str, Any]] = []
    previous_assets: Optional[float] = None
    for item in records:
        revenue = item.get("revenue")
        total_assets = item.get("total_assets")
        total_equity = item.get("total_equity")
        avg_assets = mean([value for value in (total_assets, previous_assets) if value is not None]) if previous_assets is not None or total_assets is not None else None
        asset_turnover = item.get("asset_turnover") or _safe_div(revenue, avg_assets)
        equity_multiplier = item.get("equity_multiplier") or _safe_div(total_assets, total_equity)
        trend.append({
            "year": item.get("year"),
            "report_period": item.get("report_period"),
            "roe": item.get("roe"),
            "roa": item.get("roa"),
            "roic": item.get("roic"),
            "asset_turnover": asset_turnover,
            "equity_multiplier": equity_multiplier,
            "total_assets": total_assets,
            "total_equity": total_equity,
        })
        if total_assets is not None:
            previous_assets = total_assets
    return {
        "status": series.get("status"),
        "symbol": series.get("symbol"),
        "years_used": len(trend),
        "coverage": series.get("coverage"),
        "trend": trend,
        "summary": {
            "roe": _series_stats([item.get("roe") for item in trend]),
            "roa": _series_stats([item.get("roa") for item in trend]),
            "roic": _series_stats([item.get("roic") for item in trend]),
            "asset_turnover": _series_stats([item.get("asset_turnover") for item in trend]),
            "equity_multiplier": _series_stats([item.get("equity_multiplier") for item in trend]),
        },
        "warnings": list(series.get("warnings") or []),
    }


def get_growth_quality_metrics(symbol: str, years: int = 10, source: Optional[str] = None) -> Dict[str, Any]:
    """返回成长质量指标。"""
    series = get_historical_financial_annual_series(symbol, years=years, source=source)
    records = series.get("records") or []
    chronological = list(reversed(records))
    annual_growth: List[Dict[str, Any]] = []
    for index in range(1, len(chronological)):
        previous = chronological[index - 1]
        current = chronological[index]
        annual_growth.append({
            "year": current.get("year"),
            "report_period": current.get("report_period"),
            "revenue_growth": _growth_rate(current.get("revenue"), previous.get("revenue")),
            "net_profit_growth": _growth_rate(current.get("net_profit"), previous.get("net_profit")),
            "operating_cashflow_growth": _growth_rate(current.get("operating_cashflow"), previous.get("operating_cashflow")),
            "free_cashflow_growth": _growth_rate(current.get("free_cashflow"), previous.get("free_cashflow")),
        })
    latest = chronological[-1] if chronological else {}
    earliest = chronological[0] if chronological else {}
    periods = max(0, len(chronological) - 1)
    revenue_growth = [item.get("revenue_growth") for item in annual_growth]
    profit_growth = [item.get("net_profit_growth") for item in annual_growth]
    fcf_growth = [item.get("free_cashflow_growth") for item in annual_growth]
    quality_flags = {
        "revenue_positive_year_ratio": _positive_ratio(revenue_growth),
        "profit_positive_year_ratio": _positive_ratio(profit_growth),
        "fcf_positive_year_ratio": _positive_ratio(fcf_growth),
        "profit_growth_above_revenue_ratio": _positive_ratio([
            (p - r) if p is not None and r is not None else None
            for p, r in zip(profit_growth, revenue_growth)
        ]),
    }
    return {
        "status": series.get("status"),
        "symbol": series.get("symbol"),
        "years_used": len(records),
        "coverage": series.get("coverage"),
        "cagr": {
            "revenue": _cagr(latest.get("revenue"), earliest.get("revenue"), periods),
            "net_profit": _cagr(latest.get("net_profit"), earliest.get("net_profit"), periods),
            "operating_cashflow": _cagr(latest.get("operating_cashflow"), earliest.get("operating_cashflow"), periods),
            "free_cashflow": _cagr(latest.get("free_cashflow"), earliest.get("free_cashflow"), periods),
        },
        "annual_growth": annual_growth,
        "growth_stability": {
            "revenue_growth": _series_stats(revenue_growth),
            "net_profit_growth": _series_stats(profit_growth),
            "operating_cashflow_growth": _series_stats([item.get("operating_cashflow_growth") for item in annual_growth]),
            "free_cashflow_growth": _series_stats(fcf_growth),
        },
        "quality_flags": quality_flags,
        "warnings": list(series.get("warnings") or []),
    }


def get_single_stock_risk_profile(
    symbol: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    period: str = "daily",
    limit: int = 1000,
) -> Dict[str, Any]:
    """返回单只股票价格风险画像。"""
    returns = get_return_series(symbol, start_date=start_date, end_date=end_date, period=period, limit=limit)
    volatility = get_volatility_metrics(symbol, start_date=start_date, end_date=end_date, period=period, limit=limit)
    drawdown = get_drawdown_metrics(symbol, start_date=start_date, end_date=end_date, period=period, limit=limit)
    values = [item.get("return") for item in returns.get("records", []) if item.get("return") is not None]
    valid = [float(value) for value in values]
    downside = [value for value in valid if value < 0]
    best = max(valid) if valid else None
    worst = min(valid) if valid else None
    positive_days = sum(1 for value in valid if value > 0)
    negative_days = sum(1 for value in valid if value < 0)
    return {
        "status": "success" if len(valid) >= 20 else "insufficient_data",
        "symbol": returns.get("symbol"),
        "period": period,
        "window": returns.get("window"),
        "metrics": {
            "sample_count": len(valid),
            "average_return": mean(valid) if valid else None,
            "median_return": median(valid) if valid else None,
            "best_return": best,
            "best_return_pct": best * 100 if best is not None else None,
            "worst_return": worst,
            "worst_return_pct": worst * 100 if worst is not None else None,
            "positive_day_ratio": positive_days / len(valid) if valid else None,
            "negative_day_ratio": negative_days / len(valid) if valid else None,
            "downside_volatility": pstdev(downside) if len(downside) > 1 else None,
            "downside_volatility_pct": pstdev(downside) * 100 if len(downside) > 1 else None,
            "annualized_volatility": (volatility.get("metrics") or {}).get("annualized_volatility"),
            "max_drawdown": (drawdown.get("metrics") or {}).get("max_drawdown"),
            "max_drawdown_start": (drawdown.get("metrics") or {}).get("max_drawdown_start"),
            "max_drawdown_end": (drawdown.get("metrics") or {}).get("max_drawdown_end"),
        },
        "components": {
            "return_series_status": returns.get("status"),
            "volatility_status": volatility.get("status"),
            "drawdown_status": drawdown.get("status"),
        },
        "warnings": list(returns.get("warnings") or []) + list(volatility.get("warnings") or []) + list(drawdown.get("warnings") or []),
    }


def get_peer_group(symbol: str, limit: int = 50) -> Dict[str, Any]:
    """返回标准化同行样本组。"""
    master = get_security_master(symbol)
    industry = master.get("industry")
    warnings: List[str] = []
    if not industry:
        return {"status": "no_data", "symbol": master.get("symbol"), "industry": None, "peers": [], "coverage": {"peer_count": 0}, "warnings": ["无法识别行业，不能构建同行组。"]}
    peers = get_industry_peer_basic_info(str(industry), exclude_symbol=master.get("symbol"), limit=max(1, min(int(limit or 50), 300)))
    normalized_peers = []
    for item in peers:
        normalized_peers.append({
            "symbol": item.get("symbol") or item.get("code"),
            "name": item.get("name"),
            "industry": item.get("industry"),
            "total_mv": _pick_number(item, "total_mv", "market_cap", "market_value"),
            "pe_ttm": _pick_number(item, "pe_ttm", "pe"),
            "pb": _pick_number(item, "pb", "pb_mrq"),
            "roe": _pick_number(item, "roe"),
            "data_source": item.get("source") or item.get("data_source"),
        })
    if not normalized_peers:
        warnings.append("未找到同行样本。")
    return {
        "status": "success" if normalized_peers else "no_data",
        "symbol": master.get("symbol"),
        "industry": industry,
        "peers": normalized_peers,
        "coverage": {"peer_count": len(normalized_peers), "limit": limit},
        "warnings": warnings,
    }


def get_industry_market_performance(
    symbol: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    lookback_days: int = 20,
    peer_limit: int = 100,
) -> Dict[str, Any]:
    """返回结构化行业市场表现。"""
    master = get_security_master(symbol)
    industry = master.get("industry")
    normalized_symbol = master.get("symbol") or _normalize_symbol(symbol)
    end = end_date or _today()
    start = start_date or _days_ago(max(1, int(lookback_days or 20) * 2))
    peer_group = get_peer_group(normalized_symbol, limit=peer_limit)
    peer_symbols = [peer.get("symbol") for peer in peer_group.get("peers") or [] if peer.get("symbol")]
    rows: List[Dict[str, Any]] = []
    for peer_symbol in peer_symbols[:max(1, min(int(peer_limit or 100), 200))]:
        price = get_adjusted_price_series(str(peer_symbol), start_date=start, end_date=end, limit=max(10, int(lookback_days or 20) + 10))
        records = price.get("records") or []
        if len(records) < 2:
            continue
        first = records[0]
        latest = records[-1]
        first_close = _safe_float(first.get("close"))
        latest_close = _safe_float(latest.get("close"))
        pct_change = _safe_div(latest_close - first_close, first_close) if first_close and latest_close is not None else None
        latest_pct = _safe_float(latest.get("pct_chg"))
        rows.append({
            "symbol": peer_symbol,
            "name": next((peer.get("name") for peer in peer_group.get("peers") or [] if peer.get("symbol") == peer_symbol), None),
            "first_date": first.get("trade_date"),
            "latest_date": latest.get("trade_date"),
            "first_close": first_close,
            "latest_close": latest_close,
            "period_return": pct_change,
            "period_return_pct": pct_change * 100 if pct_change is not None else None,
            "latest_pct_chg": latest_pct,
            "amount": _safe_float(latest.get("amount")),
        })
    valid_returns = [row.get("period_return") for row in rows if row.get("period_return") is not None]
    target_price = get_adjusted_price_series(normalized_symbol, start_date=start, end_date=end, limit=max(10, int(lookback_days or 20) + 10))
    target_records = target_price.get("records") or []
    target_return = None
    if len(target_records) >= 2:
        first_close = _safe_float(target_records[0].get("close"))
        latest_close = _safe_float(target_records[-1].get("close"))
        target_return = _safe_div(latest_close - first_close, first_close) if first_close and latest_close is not None else None
    moneyflow_rows = _load_tushare_industry_moneyflow_rows(start, end, 300)
    matched_flow = []
    if industry:
        for row in moneyflow_rows:
            name = str(row.get("industry") or row.get("name") or "")
            if str(industry) in name or name in str(industry):
                matched_flow.append({
                    "trade_date": _normalize_date(row.get("trade_date") or row.get("date")),
                    "industry": name,
                    "pct_change": _pick_number(row, "pct_change", "pct_chg"),
                    "net_amount": _pick_number(row, "net_amount"),
                    "net_buy_amount": _pick_number(row, "net_buy_amount"),
                    "net_sell_amount": _pick_number(row, "net_sell_amount"),
                    "company_num": _pick_number(row, "company_num"),
                })
    warnings = list(peer_group.get("warnings") or [])
    if not rows:
        warnings.append("未能从同行价格序列计算行业市场表现。")
    if not matched_flow:
        warnings.append("未匹配到 Tushare 行业资金流，资金流字段为空。")
    return {
        "status": "success" if rows else "no_data",
        "symbol": normalized_symbol,
        "industry": industry,
        "window": {"start": start, "end": end, "lookback_days": lookback_days},
        "summary": {
            "peer_count": len(rows),
            "industry_return": mean(valid_returns) if valid_returns else None,
            "industry_return_pct": mean(valid_returns) * 100 if valid_returns else None,
            "industry_return_median": median(valid_returns) if valid_returns else None,
            "target_return": target_return,
            "target_return_pct": target_return * 100 if target_return is not None else None,
            "target_return_percentile": _percentile_rank_numeric(valid_returns, target_return),
            "rising_ratio": _positive_ratio(valid_returns),
            "latest_total_amount": sum(row.get("amount") or 0 for row in rows),
            "matched_moneyflow_count": len(matched_flow),
        },
        "top_gainers": sorted(rows, key=lambda item: item.get("period_return") if item.get("period_return") is not None else -999, reverse=True)[:10],
        "top_losers": sorted(rows, key=lambda item: item.get("period_return") if item.get("period_return") is not None else 999)[:10],
        "moneyflow": matched_flow[:20],
        "coverage": {"peer_price_sample_count": len(rows), "peer_limit": peer_limit, "moneyflow_sample_count": len(matched_flow)},
        "warnings": warnings,
    }


def get_peer_relative_growth(symbol: str, metrics: Optional[List[str]] = None, years: int = 5, peer_limit: int = 50) -> Dict[str, Any]:
    """返回同业成长指标相对分位。"""
    requested = [_normalize_metric_key(item) for item in (metrics or ["revenue_cagr", "net_profit_cagr", "operating_cashflow_cagr", "free_cashflow_cagr"]) if str(item).strip()]
    metric_alias = {
        "revenue": "revenue_cagr",
        "revenue_cagr": "revenue_cagr",
        "net_profit": "net_profit_cagr",
        "profit_cagr": "net_profit_cagr",
        "net_profit_cagr": "net_profit_cagr",
        "operating_cashflow": "operating_cashflow_cagr",
        "operating_cashflow_cagr": "operating_cashflow_cagr",
        "free_cashflow": "free_cashflow_cagr",
        "free_cashflow_cagr": "free_cashflow_cagr",
    }
    normalized_metrics = [metric_alias.get(metric, metric) for metric in requested]
    master = get_security_master(symbol)
    normalized_symbol = master.get("symbol") or _normalize_symbol(symbol)
    peer_group = get_peer_group(normalized_symbol, limit=peer_limit)
    peer_symbols = [normalized_symbol] + [peer.get("symbol") for peer in peer_group.get("peers") or [] if peer.get("symbol")]
    samples: List[Dict[str, Any]] = []
    for peer_symbol in peer_symbols[:max(1, min(int(peer_limit or 50) + 1, 101))]:
        growth = get_growth_quality_metrics(str(peer_symbol), years=years)
        cagr = growth.get("cagr") or {}
        row = {
            "symbol": peer_symbol,
            "is_target": peer_symbol == normalized_symbol,
            "revenue_cagr": cagr.get("revenue"),
            "net_profit_cagr": cagr.get("net_profit"),
            "operating_cashflow_cagr": cagr.get("operating_cashflow"),
            "free_cashflow_cagr": cagr.get("free_cashflow"),
            "years_used": growth.get("years_used"),
            "status": growth.get("status"),
        }
        samples.append(row)
    target = next((row for row in samples if row.get("is_target")), {})
    result: Dict[str, Any] = {}
    warnings = list(peer_group.get("warnings") or [])
    for metric in normalized_metrics:
        values = [_safe_float(row.get(metric)) for row in samples if not row.get("is_target")]
        valid = [value for value in values if value is not None]
        current = _safe_float(target.get(metric))
        result[metric] = {
            "current_value": current,
            "current_value_pct": current * 100 if current is not None else None,
            "peer_count": len(valid),
            "peer_average": mean(valid) if valid else None,
            "peer_median": median(valid) if valid else None,
            "peer_percentile": _percentile_rank_numeric(valid, current),
        }
        if not valid:
            warnings.append(f"{metric} 缺少有效同行成长样本。")
    return {
        "status": "success" if any(item.get("peer_count") for item in result.values()) else "partial_or_no_data",
        "symbol": normalized_symbol,
        "industry": peer_group.get("industry"),
        "years": years,
        "metrics": result,
        "samples": samples,
        "coverage": {"sample_count": len(samples), "peer_limit": peer_limit},
        "warnings": warnings,
    }


def get_peer_relative_valuation(symbol: str, metrics: Optional[List[str]] = None, peer_limit: int = 200) -> Dict[str, Any]:
    """返回同业相对估值分位和行业统计。"""
    requested = [str(item).lower() for item in (metrics or ["pe", "pb", "ps"]) if str(item).strip()]
    master = get_security_master(symbol)
    snapshot = get_current_valuation_snapshot(symbol)
    industry = master.get("industry")
    result: Dict[str, Any] = {}
    warnings: List[str] = []
    if not industry:
        return {"status": "no_data", "symbol": master.get("symbol"), "industry": None, "metrics": {}, "warnings": ["无法识别行业，不能计算同业估值。"]}
    current_metrics = snapshot.get("metrics") or {}
    for metric in requested:
        metric_key = "pe" if metric in {"pe", "pe_ttm"} else "pb" if metric in {"pb", "pb_mrq"} else "ps" if metric in {"ps", "ps_ttm"} else metric
        stats = summarize_industry_valuation(str(industry), metric=metric_key, exclude_symbol=master.get("symbol"), limit=peer_limit)
        current_value = _safe_float(current_metrics.get(metric_key) or current_metrics.get(f"{metric_key}_ttm") or current_metrics.get(f"{metric_key}_mrq"))
        samples = [item.get(metric_key) for item in stats.get("samples", []) if _safe_float(item.get(metric_key)) is not None]
        percentile = _percentile_rank([float(value) for value in samples], current_value) if current_value is not None and samples else None
        result[metric_key] = {
            "current_value": current_value,
            "industry_average": stats.get("average"),
            "industry_median": stats.get("median"),
            "industry_min": stats.get("min"),
            "industry_max": stats.get("max"),
            "peer_count": stats.get("count"),
            "peer_percentile": percentile,
        }
        if not stats.get("count"):
            warnings.append(f"{metric_key} 缺少有效同行样本。")
    return {
        "status": "success" if result else "no_data",
        "symbol": master.get("symbol"),
        "industry": industry,
        "metrics": result,
        "warnings": warnings,
    }


def get_peer_relative_quality(symbol: str, metrics: Optional[List[str]] = None, peer_limit: int = 200) -> Dict[str, Any]:
    """返回同业质量指标相对位置。"""
    requested = [str(item).lower() for item in (metrics or ["roe", "pb", "pe_ttm"]) if str(item).strip()]
    peer_group = get_peer_group(symbol, limit=peer_limit)
    master = get_security_master(symbol)
    basic = get_stock_basic_info(master.get("symbol") or "") or {}
    peers = peer_group.get("peers") or []
    results: Dict[str, Any] = {}
    warnings = list(peer_group.get("warnings") or [])
    field_alias = {"pe": "pe_ttm", "pe_ttm": "pe_ttm", "pb": "pb", "roe": "roe"}
    for metric in requested:
        field = field_alias.get(metric, metric)
        current = _pick_number(basic, field, metric)
        values = [_safe_float(peer.get(field)) for peer in peers]
        valid = [value for value in values if value is not None]
        results[metric] = {
            "current_value": current,
            "peer_count": len(valid),
            "peer_average": mean(valid) if valid else None,
            "peer_median": median(valid) if valid else None,
            "peer_percentile": _percentile_rank(valid, current) if current is not None and valid else None,
        }
        if not valid:
            warnings.append(f"{metric} 缺少有效同行样本。")
    return {
        "status": "success" if any(item.get("peer_count") for item in results.values()) else "partial_or_no_data",
        "symbol": master.get("symbol"),
        "industry": peer_group.get("industry"),
        "metrics": results,
        "warnings": warnings,
    }


def get_industry_fundamental_summary(symbol: str, peer_limit: int = 100) -> Dict[str, Any]:
    """返回目标股票所在行业的基本面样本统计。"""
    peer_group = get_peer_group(symbol, limit=peer_limit)
    peers = peer_group.get("peers") or []
    requested_fields = ["total_mv", "pe_ttm", "pb", "roe"]
    metrics: Dict[str, Any] = {}
    for field in requested_fields:
        values = [_safe_float(peer.get(field)) for peer in peers]
        valid = [value for value in values if value is not None and (field not in {"pe_ttm", "pb"} or value > 0)]
        metrics[field] = _series_stats(valid)
    warnings = list(peer_group.get("warnings") or [])
    if len(peers) < 5:
        warnings.append("同行样本少于 5 个，行业基本面统计参考价值有限。")
    return {
        "status": "success" if peers else "no_data",
        "symbol": peer_group.get("symbol"),
        "industry": peer_group.get("industry"),
        "coverage": {"peer_count": len(peers), "peer_limit": peer_limit},
        "metrics": metrics,
        "top_market_cap_peers": sorted(peers, key=lambda item: _safe_float(item.get("total_mv")) or 0, reverse=True)[:10],
        "warnings": warnings,
    }


def get_capital_flow_series(symbol: str, start_date: Optional[str] = None, end_date: Optional[str] = None, limit: int = 120) -> Dict[str, Any]:
    """返回个股资金流序列。当前优先读取本地资金流集合；没有数据时显式返回 no_data。"""
    normalized_symbol = _normalize_symbol(symbol)
    end = end_date or _today()
    start = start_date or _days_ago(180)
    start_digits = _date_digits(start)
    end_digits = _date_digits(end)
    start_dash = _normalize_date(start)
    end_dash = _normalize_date(end)
    collection_names = ["stock_capital_flow", "stock_fund_flow", "stock_moneyflow", "capital_flow_daily"]
    records: List[Dict[str, Any]] = []
    used_collection: Optional[str] = None
    used_source = "local"
    db = _get_db()
    for collection_name in collection_names:
        try:
            col = db[collection_name]
            query = {
                "$and": [
                    {"$or": [{"symbol": normalized_symbol}, {"code": normalized_symbol}, {"ts_code": {"$regex": normalized_symbol}}]},
                    {"$or": [
                        {"trade_date": {"$gte": start_digits, "$lte": end_digits}},
                        {"trade_date": {"$gte": start_dash, "$lte": end_dash}},
                        {"date": {"$gte": start_digits, "$lte": end_digits}},
                        {"date": {"$gte": start_dash, "$lte": end_dash}},
                    ]},
                ]
            }
            rows = list(col.find(query, {"_id": 0}).sort("trade_date", 1).limit(max(1, min(int(limit or 120), 1000))))
            if rows:
                records = rows
                used_collection = collection_name
                break
        except Exception:
            continue
    if not records:
        records = _load_tushare_moneyflow_rows(normalized_symbol, start, end, limit)
        if records:
            used_source = "tushare"
    normalized_records: List[Dict[str, Any]] = []
    for row in records:
        normalized_records.append({
            "trade_date": _normalize_date(row.get("trade_date") or row.get("date")),
            "main_net_inflow": _pick_number(row, "main_net_inflow", "net_mf_amount", "net_amount", "main_net_amount"),
            "main_net_inflow_pct": _pick_number(row, "main_net_inflow_pct", "net_mf_pct", "net_pct", "net_amount_rate"),
            "extra_large_net_inflow": _pick_number(row, "extra_large_net_inflow", "buy_elg_amount", "elg_net_amount"),
            "large_net_inflow": _pick_number(row, "large_net_inflow", "buy_lg_amount", "lg_net_amount"),
            "medium_net_inflow": _pick_number(row, "medium_net_inflow", "buy_md_amount", "md_net_amount"),
            "small_net_inflow": _pick_number(row, "small_net_inflow", "buy_sm_amount", "sm_net_amount"),
            "amount": _pick_number(row, "amount", "turnover"),
            "data_source": row.get("source") or row.get("data_source") or used_source,
        })
    valid_main = [item.get("main_net_inflow") for item in normalized_records if item.get("main_net_inflow") is not None]
    return {
        "status": "success" if normalized_records else "no_data",
        "symbol": normalized_symbol,
        "window": {"start": start, "end": end},
        "data_source": used_collection or used_source,
        "records": normalized_records,
        "summary": {
            "main_net_inflow": _series_stats(valid_main),
            "positive_flow_ratio": _positive_ratio(valid_main),
        },
        "coverage": {"sample_count": len(normalized_records)},
        "warnings": [] if normalized_records else ["本地和 Tushare 均未找到个股资金流序列；请检查本地同步或 Tushare moneyflow_ths 权限。"],
    }


def get_chip_distribution_context(symbol: str, trade_date: Optional[str] = None) -> Dict[str, Any]:
    """返回结构化筹码分布上下文。"""
    normalized_symbol = _normalize_symbol(symbol)
    target_date = trade_date or _today()
    try:
        from core.tools.chip_distribution_tools import get_chip_distribution_akshare, get_chip_distribution_tushare
        data = get_chip_distribution_akshare(normalized_symbol, target_date) or get_chip_distribution_tushare(normalized_symbol, target_date)
    except Exception as exc:
        return {
            "status": "error",
            "symbol": normalized_symbol,
            "trade_date": target_date,
            "message": str(exc),
            "warnings": ["筹码分布数据源调用失败。"],
        }
    if not data:
        return {
            "status": "no_data",
            "symbol": normalized_symbol,
            "trade_date": target_date,
            "metrics": {},
            "warnings": ["未获取到筹码分布数据；该数据依赖外部 AkShare/Tushare 接口。"],
        }
    avg_cost = _safe_float(data.get("avg_cost"))
    cost_90_low = _safe_float(data.get("cost_90_low"))
    cost_90_high = _safe_float(data.get("cost_90_high"))
    cost_70_low = _safe_float(data.get("cost_70_low"))
    cost_70_high = _safe_float(data.get("cost_70_high"))
    profit_ratio = _safe_float(data.get("profit_ratio"))
    if profit_ratio is not None and profit_ratio > 1:
        profit_ratio = profit_ratio / 100
    return {
        "status": "success",
        "symbol": normalized_symbol,
        "trade_date": _normalize_date(data.get("date") or target_date),
        "data_source": data.get("source"),
        "metrics": {
            "profit_ratio": profit_ratio,
            "avg_cost": avg_cost,
            "cost_90_low": cost_90_low,
            "cost_90_high": cost_90_high,
            "cost_90_width": cost_90_high - cost_90_low if cost_90_high is not None and cost_90_low is not None else None,
            "concentration_90": _safe_float(data.get("concentration_90")),
            "cost_70_low": cost_70_low,
            "cost_70_high": cost_70_high,
            "cost_70_width": cost_70_high - cost_70_low if cost_70_high is not None and cost_70_low is not None else None,
            "concentration_70": _safe_float(data.get("concentration_70")),
        },
        "warnings": [],
    }


def get_company_event_timeline(symbol: str, lookback_days: int = 365, event_types: Optional[List[str]] = None, limit: int = 100) -> Dict[str, Any]:
    """返回正式公告/监管事件第一版结构化时间线。"""
    normalized_symbol = _normalize_symbol(symbol)
    end = _today()
    start = _days_ago(lookback_days)
    start_digits = _date_digits(start)
    end_digits = _date_digits(end)
    query = {
        "$and": [
            {"$or": [{"symbol": normalized_symbol}, {"code": normalized_symbol}, {"ts_code": {"$regex": normalized_symbol}}]},
            {"$or": [
                {"publish_date": {"$gte": start_digits, "$lte": end_digits}},
                {"publish_date": {"$gte": start, "$lte": end}},
                {"ann_date": {"$gte": start_digits, "$lte": end_digits}},
                {"ann_date": {"$gte": start, "$lte": end}},
                {"event_date": {"$gte": start_digits, "$lte": end_digits}},
                {"event_date": {"$gte": start, "$lte": end}},
            ]},
        ]
    }
    rows, source_collection = _read_local_collection_rows(
        ["company_announcements", "stock_announcements", "regulatory_events", "company_events"],
        query,
        limit=max(limit * 3, 100),
        sort_field="publish_date",
    )
    if not rows:
        news = get_stock_news_by_date_range(normalized_symbol, start, end, limit=max(1, min(int(limit or 100), 200)))
        rows = [row for row in news if any(word in " ".join(str(row.get(field) or "") for field in ("title", "summary", "content", "category")) for word in ["公告", "监管", "问询函", "警示函", "处罚", "减持", "质押", "重组", "诉讼", "分红"])]
        source_collection = "stock_news_proxy" if rows else None

    event_rules = {
        "financial_report": ["年报", "季报", "半年报", "财报"],
        "dividend_plan": ["分红", "派息", "权益分派"],
        "shareholder_reduction": ["减持", "被动减持"],
        "shareholder_increase": ["增持"],
        "pledge": ["质押", "冻结"],
        "litigation": ["诉讼", "仲裁", "判决"],
        "regulatory_inquiry": ["问询函", "监管函"],
        "regulatory_penalty": ["处罚", "警示函", "立案", "调查"],
        "major_restructuring": ["重组", "并购", "资产出售"],
        "performance_forecast": ["业绩预告", "预亏", "业绩修正"],
        "management_change": ["辞职", "离任", "董事长", "总经理"],
    }
    requested = {_normalize_metric_key(item) for item in event_types or [] if str(item).strip()}
    events: List[Dict[str, Any]] = []
    for row in rows:
        text = " ".join(str(row.get(field) or "") for field in ("title", "summary", "content", "category", "event_type"))
        matched_types = [event_type for event_type, keywords in event_rules.items() if any(keyword in text for keyword in keywords)]
        explicit_type = _normalize_metric_key(row.get("event_type") or row.get("type") or "")
        if explicit_type and explicit_type not in matched_types:
            matched_types.append(explicit_type)
        if not matched_types:
            matched_types = ["other_announcement"]
        if requested and not any(item in requested for item in matched_types):
            continue
        severity = 1
        if any(item in matched_types for item in ["regulatory_penalty", "litigation"]):
            severity = 3
        elif any(item in matched_types for item in ["regulatory_inquiry", "shareholder_reduction", "pledge", "performance_forecast", "major_restructuring"]):
            severity = 2
        events.append({
            "event_date": _normalize_date(row.get("event_date") or row.get("publish_date") or row.get("ann_date") or row.get("publish_time") or row.get("pub_date")),
            "publish_date": _normalize_date(row.get("publish_date") or row.get("ann_date") or row.get("publish_time") or row.get("pub_date")),
            "event_types": matched_types,
            "title": row.get("title") or row.get("name"),
            "summary": row.get("summary") or row.get("content"),
            "source": row.get("source") or row.get("data_source") or source_collection,
            "url": row.get("url"),
            "severity": severity,
        })
    events.sort(key=lambda item: str(item.get("publish_date") or item.get("event_date") or ""), reverse=True)
    type_counts: Dict[str, int] = {}
    for item in events:
        for event_type in item.get("event_types") or []:
            type_counts[event_type] = type_counts.get(event_type, 0) + 1
    return {
        "status": "success" if events else "no_data",
        "symbol": normalized_symbol,
        "window": {"start": start, "end": end, "lookback_days": lookback_days},
        "data_source": source_collection,
        "events": events[:max(1, min(int(limit or 100), 300))],
        "summary": {"event_count": len(events), "type_counts": type_counts, "high_severity_count": sum(1 for item in events if item.get("severity", 0) >= 3)},
        "warnings": [] if events and source_collection != "stock_news_proxy" else (["当前使用新闻代理识别公告/监管事件，建议后续接入正式公告专用数据源。"] if events else ["未找到公告/监管事件数据。"]),
    }


def get_business_segment_trend(symbol: str, years: int = 5, segment_type: str = "product") -> Dict[str, Any]:
    """返回主营结构趋势第一版。"""
    normalized_symbol = _normalize_symbol(symbol)
    records = get_stock_financial_periods(normalized_symbol, source=None, limit=max(int(years or 5) * 6, 40))
    segments: List[Dict[str, Any]] = []
    for record in records:
        raw = record.get("raw_data") or {}
        candidates = record.get("main_business") or raw.get("main_business") or []
        if isinstance(candidates, dict):
            candidates = [candidates]
        for item in candidates or []:
            if not isinstance(item, dict):
                continue
            bz_item = str(item.get("bz_item") or item.get("item") or item.get("segment") or item.get("name") or "").strip()
            bz_type = str(item.get("bz_type") or item.get("type") or segment_type or "").lower()
            if segment_type and segment_type.lower() not in bz_type and bz_type and segment_type.lower() not in {"all", "全部"}:
                if segment_type.lower() == "product" and "产品" not in bz_type and "product" not in bz_type:
                    continue
                if segment_type.lower() == "region" and "地区" not in bz_type and "region" not in bz_type:
                    continue
            revenue = _pick_number(item, "bz_sales", "revenue", "sales")
            cost = _pick_number(item, "bz_cost", "cost")
            profit = _pick_number(item, "bz_profit", "profit", "gross_profit")
            if profit is None and revenue is not None and cost is not None:
                profit = revenue - cost
            segments.append({
                "report_period": str(item.get("end_date") or item.get("report_period") or record.get("report_period") or record.get("report_date") or ""),
                "year": _period_year(item.get("end_date") or item.get("report_period") or record.get("report_period") or record.get("report_date")),
                "segment_name": bz_item,
                "segment_type": bz_type or segment_type,
                "revenue": revenue,
                "cost": cost,
                "gross_profit": profit,
                "gross_margin": _pick_number(item, "bz_profit_rate", "gross_margin") or (_safe_div(profit, revenue) * 100 if profit is not None and revenue else None),
                "source": item.get("source") or record.get("source") or record.get("data_source"),
            })
    by_period: Dict[str, List[Dict[str, Any]]] = {}
    for item in segments:
        period = str(item.get("report_period") or "")
        if period:
            by_period.setdefault(period, []).append(item)
    period_summaries = []
    for period, items in sorted(by_period.items(), reverse=True)[:max(1, min(int(years or 5), 10))]:
        valid_revenue = [item.get("revenue") for item in items if item.get("revenue") is not None and item.get("revenue") > 0]
        total_revenue = sum(valid_revenue)
        enriched = []
        for item in items:
            share = _safe_div(item.get("revenue"), total_revenue) if total_revenue else None
            enriched.append({**item, "revenue_share": share, "revenue_share_pct": share * 100 if share is not None else None})
        enriched.sort(key=lambda item: item.get("revenue_share") or 0, reverse=True)
        shares = [item.get("revenue_share") for item in enriched if item.get("revenue_share") is not None]
        period_summaries.append({
            "report_period": period,
            "segment_count": len(enriched),
            "total_segment_revenue": total_revenue,
            "top_segments": enriched[:10],
            "concentration": {
                "top1_share": shares[0] if shares else None,
                "top3_share": sum(shares[:3]) if shares else None,
                "hhi": sum(value * value for value in shares) if shares else None,
            },
        })
    return {
        "status": "success" if period_summaries else "no_data",
        "symbol": normalized_symbol,
        "segment_type": segment_type,
        "periods": period_summaries,
        "coverage": {"period_count": len(period_summaries), "raw_segment_count": len(segments)},
        "warnings": [] if period_summaries else ["未找到主营业务分部数据；需同步 Tushare fina_mainbz 或财报分部数据。"],
    }


def get_shareholder_return_metrics(symbol: str, years: int = 5) -> Dict[str, Any]:
    """返回股东回报指标第一版。"""
    normalized_symbol = _normalize_symbol(symbol)
    rows, source = _read_local_collection_rows(
        ["stock_dividend", "stock_dividends", "dividend_data"],
        {"$or": [{"symbol": normalized_symbol}, {"code": normalized_symbol}, {"ts_code": {"$regex": normalized_symbol}}]},
        limit=max(20, int(years or 5) * 4),
        sort_field="end_date",
    )
    if not rows:
        rows = _load_tushare_dividend_rows(normalized_symbol, max(20, int(years or 5) * 4))
        source = "tushare" if rows else None
    implemented = [row for row in rows if str(row.get("div_proc") or row.get("status") or "").strip() in {"实施", "implemented", "实施分配"} or row.get("cash_div_tax") is not None or row.get("cash_div") is not None]
    implemented.sort(key=lambda item: str(item.get("end_date") or item.get("ann_date") or ""), reverse=True)
    implemented = implemented[:max(1, min(int(years or 5) * 3, 50))]
    annual_cash: Dict[int, float] = {}
    records = []
    for row in implemented:
        year = _period_year(row.get("end_date") or row.get("ann_date"))
        cash = _pick_number(row, "cash_div_tax", "cash_div", "dividend_per_share")
        if year and cash is not None:
            annual_cash[year] = annual_cash.get(year, 0.0) + cash
        records.append({
            "end_date": _normalize_date(row.get("end_date")),
            "ann_date": _normalize_date(row.get("ann_date")),
            "ex_date": _normalize_date(row.get("ex_date")),
            "cash_div_tax": cash,
            "cash_div": _pick_number(row, "cash_div"),
            "div_proc": row.get("div_proc") or row.get("status"),
        })
    quote = get_current_valuation_snapshot(normalized_symbol)
    current_price = quote.get("current_price")
    latest_year = max(annual_cash.keys()) if annual_cash else None
    latest_cash = annual_cash.get(latest_year) if latest_year else None
    dividend_yield = _safe_div(latest_cash, current_price)
    annual_values = [{"year": year, "cash_dividend_per_share": cash, "dividend_yield": _safe_div(cash, current_price)} for year, cash in sorted(annual_cash.items(), reverse=True)]
    financial = get_historical_financial_annual_series(normalized_symbol, years=years)
    fcf_values = [row.get("free_cashflow") for row in financial.get("records") or [] if row.get("free_cashflow") is not None]
    return {
        "status": "success" if records else "no_data",
        "symbol": normalized_symbol,
        "data_source": source,
        "current_price": current_price,
        "records": records,
        "annual": annual_values,
        "metrics": {
            "latest_cash_dividend_per_share": latest_cash,
            "latest_dividend_yield": dividend_yield,
            "latest_dividend_yield_pct": dividend_yield * 100 if dividend_yield is not None else None,
            "average_cash_dividend_per_share": mean(list(annual_cash.values())) if annual_cash else None,
            "dividend_positive_years": sum(1 for value in annual_cash.values() if value > 0),
            "dividend_continuity_ratio": sum(1 for value in annual_cash.values() if value > 0) / max(1, min(int(years or 5), len(annual_cash))) if annual_cash else None,
            "fcf_positive_ratio": _positive_ratio(fcf_values),
        },
        "coverage": {"dividend_record_count": len(records), "annual_count": len(annual_cash), "financial_years": len(financial.get("records") or [])},
        "warnings": [] if records else ["未找到分红数据；需 Tushare dividend 权限或本地分红同步。"],
    }


def get_portfolio_risk_profile(positions: List[Dict[str, Any]], start_date: Optional[str] = None, end_date: Optional[str] = None, limit: int = 300) -> Dict[str, Any]:
    """返回持仓组合风险画像。"""
    normalized_positions = []
    for item in positions or []:
        symbol = _normalize_symbol(item.get("symbol") or item.get("code"))
        if not symbol:
            continue
        market_value = _safe_float(item.get("market_value"))
        quantity = _safe_float(item.get("quantity") or item.get("shares"))
        price = _safe_float(item.get("price") or item.get("current_price") or item.get("cost_price"))
        if market_value is None and quantity is not None and price is not None:
            market_value = quantity * price
        if market_value is None or market_value <= 0:
            continue
        normalized_positions.append({"symbol": symbol, "name": item.get("name"), "market_value": market_value})
    total_value = sum(item["market_value"] for item in normalized_positions)
    if total_value <= 0:
        return {"status": "no_data", "positions": [], "metrics": {}, "warnings": ["未提供有效持仓市值。"]}
    for item in normalized_positions:
        item["weight"] = item["market_value"] / total_value
        master = get_security_master(item["symbol"])
        item["industry"] = master.get("industry")
        item["name"] = item.get("name") or master.get("name")
    end = end_date or _today()
    start = start_date or _days_ago(365)
    return_by_date: Dict[str, float] = {}
    sample_counts: Dict[str, int] = {}
    for item in normalized_positions:
        ret = get_return_series(item["symbol"], start_date=start, end_date=end, limit=limit)
        sample_counts[item["symbol"]] = ret.get("coverage", {}).get("return_sample_count", 0)
        for row in ret.get("records") or []:
            value = row.get("return")
            date = row.get("trade_date")
            if value is not None and date:
                return_by_date[date] = return_by_date.get(date, 0.0) + item["weight"] * value
    series = [{"trade_date": date, "return": value} for date, value in sorted(return_by_date.items())]
    values = [item["return"] for item in series]
    nav = 1.0
    peak = 1.0
    max_drawdown = 0.0
    for value in values:
        nav *= 1 + value
        peak = max(peak, nav)
        max_drawdown = min(max_drawdown, nav / peak - 1)
    sorted_returns = sorted(values)
    var_95 = sorted_returns[int(len(sorted_returns) * 0.05)] if len(sorted_returns) >= 20 else None
    cvar_95 = mean([value for value in sorted_returns if var_95 is not None and value <= var_95]) if var_95 is not None else None
    industry_weights: Dict[str, float] = {}
    for item in normalized_positions:
        industry = item.get("industry") or "unknown"
        industry_weights[industry] = industry_weights.get(industry, 0.0) + item["weight"]
    weights = [item["weight"] for item in normalized_positions]
    return {
        "status": "success" if len(values) >= 20 else "insufficient_data",
        "window": {"start": start, "end": end},
        "positions": sorted(normalized_positions, key=lambda item: item["weight"], reverse=True),
        "metrics": {
            "total_market_value": total_value,
            "sample_count": len(values),
            "annualized_volatility": pstdev(values) * (252 ** 0.5) if len(values) > 1 else None,
            "max_drawdown": max_drawdown if values else None,
            "var_95": var_95,
            "cvar_95": cvar_95,
            "top1_weight": max(weights) if weights else None,
            "top3_weight": sum(sorted(weights, reverse=True)[:3]),
            "concentration_hhi": sum(weight * weight for weight in weights),
        },
        "exposure": {"industry_weights": industry_weights},
        "return_series": series,
        "coverage": {"position_count": len(normalized_positions), "sample_counts": sample_counts},
        "warnings": [] if len(values) >= 20 else ["组合收益率样本少于 20 个，风险指标参考价值有限。"],
    }


def get_risk_event_flags(symbol: str, lookback_days: int = 180, limit: int = 50) -> Dict[str, Any]:
    """基于近期新闻标题/摘要提取风险事件 flags。"""
    normalized_symbol = _normalize_symbol(symbol)
    end = _today()
    start = _days_ago(lookback_days)
    news = get_stock_news_by_date_range(normalized_symbol, start, end, limit=max(1, min(int(limit or 50), 200)))
    risk_keywords = {
        "regulatory_penalty": ["处罚", "监管", "立案", "调查", "警示函", "问询函"],
        "litigation": ["诉讼", "仲裁", "纠纷", "判决"],
        "shareholder_reduction": ["减持", "被动减持"],
        "pledge": ["质押", "冻结"],
        "performance_warning": ["预亏", "业绩下滑", "亏损", "暴雷"],
        "major_restructuring": ["重组", "并购", "资产出售", "重大合同"],
        "management_change": ["辞职", "离任", "董事长", "总经理"],
    }
    flags = {key: {"hit": False, "count": 0, "examples": []} for key in risk_keywords}
    for item in news:
        text = " ".join(str(item.get(field) or "") for field in ("title", "summary", "content", "category"))
        for key, keywords in risk_keywords.items():
            if any(keyword in text for keyword in keywords):
                flags[key]["hit"] = True
                flags[key]["count"] += 1
                if len(flags[key]["examples"]) < 3:
                    flags[key]["examples"].append({
                        "title": item.get("title"),
                        "publish_time": str(item.get("publish_time") or item.get("pub_date") or ""),
                        "url": item.get("url"),
                    })
    hit_flags = [key for key, value in flags.items() if value.get("hit")]
    return {
        "status": "success" if news else "no_news",
        "symbol": normalized_symbol,
        "window": {"start": start, "end": end, "lookback_days": lookback_days},
        "news_count": len(news),
        "hit_flags": hit_flags,
        "flags": flags,
        "warnings": [] if news else ["未获取到近期新闻，风险事件 flags 可能不完整。"],
    }


def get_company_announcements(symbol: str, lookback_days: int = 365, limit: int = 50) -> Dict[str, Any]:
    """返回公司公告/公告类新闻的结构化列表。"""
    normalized_symbol = _normalize_symbol(symbol)
    end = _today()
    start = _days_ago(lookback_days)
    news = get_stock_news_by_date_range(normalized_symbol, start, end, limit=max(1, min(int(limit or 50), 200)))
    announcement_keywords = ["公告", "披露", "年报", "季报", "半年报", "分红", "减持", "增持", "重组", "停牌", "复牌"]
    announcements = []
    for item in news:
        text = " ".join(str(item.get(field) or "") for field in ("title", "summary", "content", "category"))
        if any(keyword in text for keyword in announcement_keywords):
            announcements.append({
                "title": item.get("title"),
                "publish_time": str(item.get("publish_time") or item.get("pub_date") or ""),
                "category": item.get("category"),
                "summary": item.get("summary") or item.get("content"),
                "url": item.get("url"),
                "source": item.get("source") or item.get("data_source"),
            })
    return {
        "status": "success" if announcements else "no_data",
        "symbol": normalized_symbol,
        "window": {"start": start, "end": end, "lookback_days": lookback_days},
        "announcements": announcements[:limit],
        "coverage": {"source_news_count": len(news), "announcement_count": len(announcements[:limit])},
        "warnings": [] if announcements else ["未在近期新闻中识别到公告类记录；如需正式公告，应接入公告专用数据源。"],
    }

