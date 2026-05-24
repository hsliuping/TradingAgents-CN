from __future__ import annotations

import math
import re
import logging
import asyncio
import threading
from datetime import datetime, timedelta
from statistics import median
from typing import Any, Dict, Iterable, List, Optional, Tuple

logger = logging.getLogger("agents")


BASIC_COLLECTION = "stock_basic_info"
DAILY_COLLECTION = "stock_daily_quotes"


def normalize_stock_code(symbol: str) -> str:
    """Return the six-digit A-share code used by local MongoDB collections."""
    raw = str(symbol or "").strip().upper()
    for suffix in (".SH", ".SZ", ".SS", ".XSHE", ".XSHG", ".HK"):
        raw = raw.replace(suffix, "")
    digits = "".join(ch for ch in raw if ch.isdigit())
    return digits.zfill(6) if digits else raw


def _get_db():
    try:
        from tradingagents.config.database_manager import get_database_manager

        manager = get_database_manager()
        return manager.get_mongodb_db()
    except Exception as exc:
        logger.warning(f"同行/历史分析无法连接MongoDB: {exc}")
        return None


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if math.isnan(value) or math.isinf(value):
            return None
        return float(value)

    text = str(value).strip()
    if not text or text.upper() in {"N/A", "NA", "NONE", "NULL", "--", "NAN"}:
        return None

    text = text.replace(",", "")
    match = re.search(r"[-+]?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _first_number(doc: Dict[str, Any], fields: Iterable[str]) -> Optional[float]:
    for field in fields:
        value = _to_float(doc.get(field))
        if value is not None:
            return value
    return None


def _fmt(value: Optional[float], digits: int = 2, suffix: str = "") -> str:
    if value is None:
        return "N/A"
    return f"{value:.{digits}f}{suffix}"


def _fmt_int(value: Optional[float]) -> str:
    if value is None:
        return "N/A"
    return f"{value:.0f}"


def _fmt_percent(value: Optional[float], digits: int = 2) -> str:
    if value is None:
        return "N/A"
    return f"{value * 100:.{digits}f}%"


def _company_name(doc: Dict[str, Any]) -> str:
    return str(doc.get("name") or doc.get("stock_name") or doc.get("symbol") or doc.get("code") or "未知")


def _basic_query(code: str) -> Dict[str, Any]:
    return {
        "$or": [
            {"code": code},
            {"symbol": code},
            {"ts_code": f"{code}.SZ"},
            {"ts_code": f"{code}.SH"},
        ]
    }


def _run_async(coro):
    """Run an async provider call from sync tool code, including inside active loops."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result: Dict[str, Any] = {}

    def _runner():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result["value"] = loop.run_until_complete(coro)
        except Exception as exc:  # pragma: no cover - defensive path
            result["error"] = exc
        finally:
            loop.close()

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()
    thread.join(timeout=45)
    if thread.is_alive():
        raise TimeoutError("异步数据源调用超时")
    if "error" in result:
        raise result["error"]
    return result.get("value")


def _to_baostock_code(code: str) -> str:
    return f"sh.{code}" if code.startswith(("5", "6", "9")) else f"sz.{code}"


def _query_market_quote(db, code: str) -> Dict[str, Any]:
    try:
        quote = db["market_quotes"].find_one(
            {"$or": [{"code": code}, {"symbol": code}, {"full_symbol": f"{code}.SS"}, {"full_symbol": f"{code}.SZ"}]},
            {"_id": 0},
        )
        return quote or {}
    except Exception:
        return {}


def _upsert_basic_info(db, doc: Dict[str, Any]) -> None:
    if not doc or not doc.get("code"):
        return
    try:
        payload = dict(doc)
        payload.setdefault("updated_at", datetime.now())
        db[BASIC_COLLECTION].update_one({"code": payload["code"]}, {"$set": payload}, upsert=True)
    except Exception as exc:
        logger.debug(f"回填 stock_basic_info 失败: {exc}")


def _fetch_akshare_basic_info(code: str) -> Dict[str, Any]:
    try:
        from tradingagents.dataflows.providers.china.akshare import AKShareProvider

        provider = AKShareProvider()
        info = _run_async(provider.get_stock_basic_info(code))
        return info or {}
    except Exception as exc:
        logger.warning(f"AKShare基础信息获取失败 {code}: {exc}")
        return {}


def _fetch_baostock_latest_valuation(code: str) -> Dict[str, Any]:
    try:
        from tradingagents.dataflows.providers.china.baostock import BaoStockProvider

        provider = BaoStockProvider()
        return _run_async(provider.get_valuation_data(code)) or {}
    except Exception as exc:
        logger.warning(f"BaoStock最新估值获取失败 {code}: {exc}")
        return {}


def _merge_basic_fallback(db, code: str) -> Dict[str, Any]:
    """Build and persist a basic info document when MongoDB has no stock_basic_info."""
    doc: Dict[str, Any] = {"code": code, "symbol": code}

    quote = _query_market_quote(db, code)
    if quote:
        doc.update(
            {
                "name": quote.get("name") or quote.get("stock_name") or f"股票{code}",
                "current_price": _first_number(quote, ("current_price", "close", "price")),
                "total_mv": _first_number(quote, ("total_mv", "market_cap")),
                "circ_mv": _first_number(quote, ("circ_mv",)),
                "pe": _first_number(quote, ("pe",)),
                "pe_ttm": _first_number(quote, ("pe_ttm", "pe")),
                "pb": _first_number(quote, ("pb",)),
                "pb_mrq": _first_number(quote, ("pb_mrq", "pb")),
                "data_source": quote.get("data_source", "market_quotes"),
            }
        )

    ak_info = _fetch_akshare_basic_info(code)
    if ak_info:
        doc.update({k: v for k, v in ak_info.items() if v not in (None, "", "未知")})
        doc["source"] = "akshare"

    valuation = _fetch_baostock_latest_valuation(code)
    if valuation:
        doc.update(
            {
                "pe": valuation.get("pe_ttm") or doc.get("pe"),
                "pe_ttm": valuation.get("pe_ttm") or doc.get("pe_ttm"),
                "pb": valuation.get("pb_mrq") or doc.get("pb"),
                "pb_mrq": valuation.get("pb_mrq") or doc.get("pb_mrq"),
                "ps": valuation.get("ps_ttm") or doc.get("ps"),
                "ps_ttm": valuation.get("ps_ttm") or doc.get("ps_ttm"),
                "pcf_ttm": valuation.get("pcf_ttm"),
                "close": valuation.get("close") or doc.get("current_price"),
                "valuation_date": valuation.get("date"),
            }
        )

    profit = _fetch_baostock_profit(code)
    if profit:
        doc.update(profit)

    _upsert_basic_info(db, doc)
    return doc


def _metric_row(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "code": str(doc.get("code") or doc.get("symbol") or ""),
        "name": _company_name(doc),
        "industry": str(doc.get("industry") or doc.get("industry_name") or "未知"),
        "total_mv": _first_number(doc, ("total_mv", "market_cap", "money_cap")),
        "pe": _first_number(doc, ("pe_ttm", "pe")),
        "pb": _first_number(doc, ("pb_mrq", "pb")),
        "ps": _first_number(doc, ("ps_ttm", "ps")),
        "roe": _first_number(doc, ("roe", "roe_waa", "roe_dt")),
        "net_profit": _first_number(doc, ("net_profit", "netProfit")),
        "gross_margin": _first_number(doc, ("gross_margin", "gpMargin")),
        "net_margin": _first_number(doc, ("net_margin", "npMargin")),
    }


def _mean(values: List[float]) -> Optional[float]:
    values = [v for v in values if v is not None and v > 0]
    return sum(values) / len(values) if values else None


def _median(values: List[float]) -> Optional[float]:
    values = [v for v in values if v is not None and v > 0]
    return float(median(values)) if values else None


def _relation(value: Optional[float], benchmark: Optional[float], lower_is_better: bool = True) -> str:
    if value is None or benchmark is None or benchmark <= 0:
        return "数据不足"
    diff = (value - benchmark) / benchmark
    if abs(diff) < 0.05:
        return "接近行业中位数"
    if lower_is_better:
        return f"低于行业中位数{abs(diff):.1%}" if diff < 0 else f"高于行业中位数{diff:.1%}"
    return f"高于行业中位数{diff:.1%}" if diff > 0 else f"低于行业中位数{abs(diff):.1%}"


def _select_representative_peers(rows: List[Dict[str, Any]], target: Dict[str, Any], limit: int) -> List[Dict[str, Any]]:
    """Select representative peers: leaders, target-size peers, and valuation-typical samples."""
    peers = [row for row in rows if normalize_stock_code(row["code"]) != normalize_stock_code(target["code"])]
    non_st_peers = [row for row in peers if "ST" not in str(row.get("name", "")).upper()]
    if len(non_st_peers) >= max(3, min(limit, 5)):
        peers = non_st_peers
    representative_peers = [
        row for row in peers
        if row.get("pe") and row["pe"] > 0 and "ST" not in str(row.get("name", "")).upper()
    ]
    if len(representative_peers) >= max(3, min(limit, 5)):
        peers = representative_peers
    if not peers:
        return []

    selected: List[Dict[str, Any]] = []
    selected_codes = set()

    def add(row: Optional[Dict[str, Any]]) -> None:
        if not row or len(selected) >= limit:
            return
        code = normalize_stock_code(row["code"])
        if code in selected_codes:
            return
        selected.append(row)
        selected_codes.add(code)

    peers_with_mv = [row for row in peers if row.get("total_mv") and row["total_mv"] > 0]
    peers_with_pe = [row for row in peers if row.get("pe") and row["pe"] > 0]
    peers_with_pb = [row for row in peers if row.get("pb") and row["pb"] > 0]

    # 代表性覆盖：行业龙头、标的市值附近、估值中位附近、估值与标的接近。
    # 不选市值最小公司，避免极端小盘/壳股扰动同业参考。
    if peers_with_mv:
        add(max(peers_with_mv, key=lambda row: row["total_mv"]))

        target_mv = target.get("total_mv")
        if target_mv:
            add(min(peers_with_mv, key=lambda row: abs(row["total_mv"] - target_mv)))

    if peers_with_pe:
        median_pe = _median([row["pe"] for row in peers_with_pe])
        if median_pe:
            add(min(peers_with_pe, key=lambda row: abs(row["pe"] - median_pe)))

        target_pe = target.get("pe")
        if target_pe:
            add(min(peers_with_pe, key=lambda row: abs(row["pe"] - target_pe)))

    if peers_with_pb:
        median_pb = _median([row["pb"] for row in peers_with_pb])
        if median_pb:
            add(min(peers_with_pb, key=lambda row: abs(row["pb"] - median_pb)))

    for row in sorted(peers, key=lambda item: (item.get("total_mv") or 0), reverse=True):
        add(row)
        if len(selected) >= limit:
            break

    return selected


def _fetch_baostock_profit(code: str, bs_module=None, year: Optional[int] = None, quarter: Optional[int] = None) -> Dict[str, Any]:
    """Fetch latest available profit metrics from BaoStock."""
    try:
        import baostock as bs

        bs = bs_module or bs
        should_logout = False
        if bs_module is None:
            lg = bs.login()
            if lg.error_code != "0":
                return {}
            should_logout = True
        now = datetime.now()
        year = year or now.year
        quarter = quarter or ((now.month - 1) // 3 + 1)
        candidates: List[Tuple[int, int]] = []
        try:
            for y in range(year, year - 2, -1):
                for q in range(quarter if y == year else 4, 0, -1):
                    candidates.append((y, q))

            for y, q in candidates:
                rs = bs.query_profit_data(code=_to_baostock_code(code), year=y, quarter=q)
                if rs.error_code != "0":
                    continue
                rows = []
                while rs.error_code == "0" and rs.next():
                    rows.append(rs.get_row_data())
                if not rows:
                    continue
                data = dict(zip(rs.fields, rows[-1]))
                return {
                    "roe": _to_float(data.get("roeAvg")),
                    "net_margin": _to_float(data.get("npMargin")),
                    "gross_margin": _to_float(data.get("gpMargin")),
                    "net_profit": (_to_float(data.get("netProfit")) or 0) / 100000000,
                    "eps_ttm": _to_float(data.get("epsTTM")),
                    "total_share": _to_float(data.get("totalShare")),
                    "float_share": _to_float(data.get("liqaShare")),
                    "profit_date": data.get("statDate"),
                }
        finally:
            if should_logout:
                bs.logout()
    except Exception as exc:
        logger.debug(f"BaoStock利润数据获取失败 {code}: {exc}")
    return {}


def _fetch_baostock_peer_rows(code: str, peer_limit: int) -> Tuple[List[Dict[str, Any]], str]:
    result: Dict[str, Any] = {}

    def _runner() -> None:
        result["value"] = _fetch_baostock_peer_rows_inner(code, peer_limit)

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()
    thread.join(timeout=60)
    if thread.is_alive():
        logger.warning(f"BaoStock同业数据获取超时 {code}")
        return [], ""
    return result.get("value", ([], ""))


def _fetch_baostock_peer_rows_inner(code: str, peer_limit: int) -> Tuple[List[Dict[str, Any]], str]:
    """Fetch same-industry peers and latest PE/PB/PS/profit from BaoStock."""
    try:
        import baostock as bs

        lg = bs.login()
        if lg.error_code != "0":
            return [], ""

        try:
            target_bs_code = _to_baostock_code(code)
            industry_rs = bs.query_stock_industry()
            if industry_rs.error_code != "0":
                return [], ""

            industry_rows = []
            while industry_rs.error_code == "0" and industry_rs.next():
                item = dict(zip(industry_rs.fields, industry_rs.get_row_data()))
                industry_rows.append(item)

            target_industry = ""
            for row in industry_rows:
                if row.get("code") == target_bs_code:
                    target_industry = row.get("industry") or ""
                    break
            if not target_industry:
                return [], ""

            candidates = [
                row for row in industry_rows
                if row.get("industry") == target_industry and row.get("code_name") and row.get("code", "").startswith(("sh.", "sz."))
            ]

            def latest_valuation(bs_code: str) -> Dict[str, Any]:
                end_date = datetime.now().strftime("%Y-%m-%d")
                start_date = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")
                rs = bs.query_history_k_data_plus(
                    code=bs_code,
                    fields="date,code,close,peTTM,pbMRQ,psTTM,pcfNcfTTM",
                    start_date=start_date,
                    end_date=end_date,
                    frequency="d",
                    adjustflag="3",
                )
                if rs.error_code != "0":
                    return {}
                values = []
                while rs.error_code == "0" and rs.next():
                    values.append(rs.get_row_data())
                if not values:
                    return {}
                data = dict(zip(rs.fields, values[-1]))
                return {
                    "close": _to_float(data.get("close")),
                    "pe": _to_float(data.get("peTTM")),
                    "pe_ttm": _to_float(data.get("peTTM")),
                    "pb": _to_float(data.get("pbMRQ")),
                    "pb_mrq": _to_float(data.get("pbMRQ")),
                    "ps": _to_float(data.get("psTTM")),
                    "ps_ttm": _to_float(data.get("psTTM")),
                    "pcf_ttm": _to_float(data.get("pcfNcfTTM")),
                    "valuation_date": data.get("date"),
                }

            target_rows: List[Dict[str, Any]] = []
            peer_rows: List[Dict[str, Any]] = []
            for item in candidates:
                candidate_code = normalize_stock_code(item.get("code", ""))
                valuation = latest_valuation(item["code"])
                if not valuation or valuation.get("pe") is None or valuation.get("pb") is None:
                    continue
                profit = _fetch_baostock_profit(candidate_code, bs_module=bs)
                total_mv = None
                close = valuation.get("close")
                total_share = profit.get("total_share")
                if close and total_share:
                    total_mv = close * total_share / 100000000
                row = {
                    "code": candidate_code,
                    "name": item.get("code_name") or candidate_code,
                    "industry": target_industry,
                    "source": "baostock",
                    "total_mv": total_mv,
                    **valuation,
                    **profit,
                }
                if candidate_code == code:
                    target_rows = [row]
                elif len(peer_rows) < max(20, peer_limit * 8):
                    peer_rows.append(row)
                if target_rows and len(peer_rows) >= max(20, peer_limit * 8):
                    break

            if not target_rows:
                return [], target_industry
            return target_rows + peer_rows, target_industry
        finally:
            bs.logout()
    except Exception as exc:
        logger.warning(f"BaoStock同业数据获取失败 {code}: {exc}")
        return [], ""


def build_peer_comparison_report(symbol: str, peer_limit: int = 5) -> str:
    """Build a same-industry comparison table from stock_basic_info."""
    code = normalize_stock_code(symbol)
    db = _get_db()
    if db is None:
        return "## 同业对比\n\n未连接MongoDB，无法读取 stock_basic_info 进行同业对比。"

    try:
        coll = db[BASIC_COLLECTION]
        target_doc = coll.find_one(_basic_query(code), {"_id": 0})
        if not target_doc:
            target_doc = _merge_basic_fallback(db, code)
            if not target_doc:
                return f"## 同业对比\n\nstock_basic_info 中未找到 {code} 的基础信息，且实时补取失败，无法生成同业对比。"

        target = _metric_row(target_doc)
        industry = target["industry"]
        rows: List[Dict[str, Any]] = []

        baostock_rows: List[Dict[str, Any]] = []
        baostock_industry = ""
        if not industry or industry == "未知":
            baostock_rows, baostock_industry = _fetch_baostock_peer_rows(code, peer_limit)
            if baostock_rows:
                rows = [_metric_row(row) for row in baostock_rows]
                target = _metric_row(baostock_rows[0])
                industry = baostock_industry or target["industry"]
                for row in baostock_rows:
                    _upsert_basic_info(db, row)
            else:
                return f"## 同业对比\n\n{code} 缺少明确行业字段，且BaoStock行业分类补取失败，无法按 industry 聚合同业。"

        if not rows:
            cursor = coll.find(
                {
                    "industry": industry,
                    "$or": [
                        {"pe": {"$exists": True}},
                        {"pe_ttm": {"$exists": True}},
                        {"pb": {"$exists": True}},
                        {"pb_mrq": {"$exists": True}},
                        {"total_mv": {"$exists": True}},
                    ],
                },
                {"_id": 0},
            ).limit(2000)
            rows = [_metric_row(doc) for doc in cursor]
            rows = [row for row in rows if row["code"]]

        if len(rows) < peer_limit + 1 or not any(row.get("pe") for row in rows):
            baostock_rows, baostock_industry = _fetch_baostock_peer_rows(code, peer_limit)
            if baostock_rows:
                rows = [_metric_row(row) for row in baostock_rows]
                target = rows[0]
                industry = baostock_industry or industry
                for row in baostock_rows:
                    _upsert_basic_info(db, row)

        if not rows:
            return f"## 同业对比\n\n未找到 {industry} 行业的可比股票数据。"

        pe_values = [row["pe"] for row in rows if row["pe"] and row["pe"] > 0]
        pb_values = [row["pb"] for row in rows if row["pb"] and row["pb"] > 0]
        ps_values = [row["ps"] for row in rows if row["ps"] and row["ps"] > 0]
        roe_values = [row["roe"] for row in rows if row["roe"] is not None]
        profit_values = [row["net_profit"] for row in rows if row["net_profit"] is not None]

        peer_display_limit = max(3, min(peer_limit, 5))
        peers = _select_representative_peers(rows, target, peer_display_limit)

        display_rows = [target] + peers
        table_lines = [
            "| 类型 | 代码 | 名称 | 总市值(亿元) | PE/PE_TTM | PB/PB_MRQ | PS | 净利润(亿元) | ROE | 毛利率 |",
            "|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for idx, row in enumerate(display_rows):
            kind = "分析标的" if idx == 0 else "可比公司"
            table_lines.append(
                "| {kind} | {code} | {name} | {mv} | {pe} | {pb} | {ps} | {profit} | {roe} | {gross} |".format(
                    kind=kind,
                    code=row["code"],
                    name=row["name"],
                    mv=_fmt(row["total_mv"], 1),
                    pe=_fmt(row["pe"], 2),
                    pb=_fmt(row["pb"], 2),
                    ps=_fmt(row["ps"], 2),
                    roe=_fmt_percent(row["roe"], 2),
                    profit=_fmt(row["net_profit"], 2),
                    gross=_fmt_percent(row["gross_margin"], 2),
                )
            )

        report = f"""## 同业对比

**行业**: {industry}  
**样本数量**: {len(rows)} 只股票（最多读取2000条基础信息）  
**展示样本选择**: 覆盖行业龙头、标的市值附近、估值中位附近和估值接近标的的代表性公司

### 行业估值统计

| 指标 | 均值 | 中位数 | 有效样本 |
|---|---:|---:|---:|
| PE/PE_TTM | {_fmt(_mean(pe_values), 2)} | {_fmt(_median(pe_values), 2)} | {_fmt_int(len(pe_values))} |
| PB/PB_MRQ | {_fmt(_mean(pb_values), 2)} | {_fmt(_median(pb_values), 2)} | {_fmt_int(len(pb_values))} |
| PS | {_fmt(_mean(ps_values), 2)} | {_fmt(_median(ps_values), 2)} | {_fmt_int(len(ps_values))} |
| 净利润(亿元) | {_fmt(_mean(profit_values), 2)} | {_fmt(_median(profit_values), 2)} | {_fmt_int(len(profit_values))} |
| ROE | {_fmt_percent(_mean(roe_values), 2)} | {_fmt_percent(_median(roe_values), 2)} | {_fmt_int(len(roe_values))} |

### 可比公司表

{chr(10).join(table_lines)}

### 相对估值解读

- PE/PE_TTM：{_relation(target["pe"], _median(pe_values), lower_is_better=True)}
- PB/PB_MRQ：{_relation(target["pb"], _median(pb_values), lower_is_better=True)}
- ROE：{_relation(target["roe"], _median(roe_values), lower_is_better=False)}

> 数据说明：若 MongoDB 缺少 `stock_basic_info`，本工具会按需使用 AKShare/BaoStock 补取基础信息、行业分类和最新估值。PEG 需要未来盈利增速预测，当前数据源未稳定提供，禁止用技术指标替代PEG。
"""
        return report.strip()
    except Exception as exc:
        logger.error(f"生成同业对比失败: {exc}", exc_info=True)
        return f"## 同业对比\n\n生成同业对比失败: {exc}"


def _parse_trade_date(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%Y/%m/%d"):
        try:
            date_text = text[:10] if fmt in ("%Y-%m-%d", "%Y/%m/%d") else text[:8]
            return datetime.strptime(date_text, fmt)
        except ValueError:
            continue
    return None


def _percentile_rank(series: List[float], current: float) -> Optional[float]:
    valid = [value for value in series if value is not None and value > 0]
    if not valid or current is None or current <= 0:
        return None
    below_or_equal = sum(1 for value in valid if value <= current)
    return below_or_equal / len(valid) * 100


def _history_metric(docs: List[Dict[str, Any]], fields: Tuple[str, ...]) -> Tuple[List[float], Optional[float]]:
    values: List[float] = []
    latest: Optional[float] = None
    for doc in docs:
        value = _first_number(doc, fields)
        if value is None or value <= 0:
            continue
        values.append(value)
        latest = value
    return values, latest


def _fetch_baostock_history_docs(code: str, years: int) -> List[Dict[str, Any]]:
    """Fetch daily close and valuation series from BaoStock for percentile analysis."""
    try:
        import baostock as bs

        lg = bs.login()
        if lg.error_code != "0":
            logger.warning(f"BaoStock登录失败，无法补取历史分位数据: {lg.error_msg}")
            return []

        try:
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=365 * years + 20)).strftime("%Y-%m-%d")
            rs = bs.query_history_k_data_plus(
                code=_to_baostock_code(code),
                fields="date,code,close,peTTM,pbMRQ,psTTM,pcfNcfTTM",
                start_date=start_date,
                end_date=end_date,
                frequency="d",
                adjustflag="3",
            )
            if rs.error_code != "0":
                logger.warning(f"BaoStock历史估值查询失败 {code}: {rs.error_msg}")
                return []

            docs: List[Dict[str, Any]] = []
            while rs.error_code == "0" and rs.next():
                data = dict(zip(rs.fields, rs.get_row_data()))
                trade_date = data.get("date")
                doc = {
                    "symbol": code,
                    "code": code,
                    "ts_code": f"{code}.SH" if code.startswith(("5", "6", "9")) else f"{code}.SZ",
                    "period": "daily",
                    "trade_date": trade_date,
                    "date": trade_date,
                    "close": _to_float(data.get("close")),
                    "pe": _to_float(data.get("peTTM")),
                    "pe_ttm": _to_float(data.get("peTTM")),
                    "pb": _to_float(data.get("pbMRQ")),
                    "pb_mrq": _to_float(data.get("pbMRQ")),
                    "ps": _to_float(data.get("psTTM")),
                    "ps_ttm": _to_float(data.get("psTTM")),
                    "pcf_ttm": _to_float(data.get("pcfNcfTTM")),
                    "data_source": "baostock",
                    "updated_at": datetime.now(),
                }
                if doc["trade_date"] and doc["close"]:
                    docs.append(doc)
            return docs
        finally:
            bs.logout()
    except Exception as exc:
        logger.warning(f"BaoStock历史分位数据补取失败 {code}: {exc}")
        return []


def _upsert_daily_docs(db, docs: List[Dict[str, Any]]) -> None:
    if not docs:
        return
    try:
        coll = db[DAILY_COLLECTION]
        for doc in docs:
            coll.update_one(
                {"symbol": doc["symbol"], "period": "daily", "trade_date": doc["trade_date"]},
                {"$set": doc},
                upsert=True,
            )
    except Exception as exc:
        logger.debug(f"回填 stock_daily_quotes 失败: {exc}")


def build_historical_percentile_report(symbol: str, years: int = 5) -> str:
    """Build close/valuation percentile report from stock_daily_quotes."""
    code = normalize_stock_code(symbol)
    years = 5 if years not in (3, 5) else years
    db = _get_db()
    if db is None:
        return "## 历史分位\n\n未连接MongoDB，无法读取 stock_daily_quotes 计算历史分位。"

    try:
        coll = db[DAILY_COLLECTION]
        cutoff = datetime.now() - timedelta(days=365 * years + 10)
        cursor = coll.find(
            {
                "$or": [
                    {"symbol": code},
                    {"code": code},
                    {"ts_code": f"{code}.SZ"},
                    {"ts_code": f"{code}.SH"},
                ],
                "period": "daily",
            },
            {
                "_id": 0,
                "trade_date": 1,
                "date": 1,
                "close": 1,
                "pe": 1,
                "pe_ttm": 1,
                "pb": 1,
                "pb_mrq": 1,
            },
        ).sort("trade_date", 1)

        docs = []
        for doc in cursor:
            trade_dt = _parse_trade_date(doc.get("trade_date") or doc.get("date"))
            if trade_dt is None or trade_dt < cutoff:
                continue
            doc["_trade_dt"] = trade_dt
            docs.append(doc)

        if not docs:
            docs = _fetch_baostock_history_docs(code, years)
            _upsert_daily_docs(db, docs)
            docs = [
                {**doc, "_trade_dt": _parse_trade_date(doc.get("trade_date") or doc.get("date"))}
                for doc in docs
                if _parse_trade_date(doc.get("trade_date") or doc.get("date")) is not None
                and _parse_trade_date(doc.get("trade_date") or doc.get("date")) >= cutoff
            ]
        if not docs:
            return f"## 历史分位\n\nstock_daily_quotes 中未找到 {code} 最近{years}年的日线数据，且BaoStock补取失败。"

        close_values, latest_close = _history_metric(docs, ("close",))
        pe_values, latest_pe = _history_metric(docs, ("pe_ttm", "pe"))
        pb_values, latest_pb = _history_metric(docs, ("pb_mrq", "pb"))

        latest_date = docs[-1]["_trade_dt"].strftime("%Y-%m-%d")
        rows = [
            ("收盘价", latest_close, close_values, "价格"),
            ("PE/PE_TTM", latest_pe, pe_values, "估值"),
            ("PB/PB_MRQ", latest_pb, pb_values, "估值"),
        ]

        table_lines = [
            "| 指标 | 最新值 | 历史低点 | 历史中位数 | 历史高点 | 当前分位 | 有效样本 |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
        notes = []
        for name, latest, values, category in rows:
            pct = _percentile_rank(values, latest) if latest is not None else None
            table_lines.append(
                "| {name} | {latest} | {low} | {mid} | {high} | {pct} | {count} |".format(
                    name=name,
                    latest=_fmt(latest, 2),
                    low=_fmt(min(values), 2) if values else "N/A",
                    mid=_fmt(_median(values), 2) if values else "N/A",
                    high=_fmt(max(values), 2) if values else "N/A",
                    pct=_fmt(pct, 1, "%") if pct is not None else "N/A",
                    count=len(values),
                )
            )
            if pct is None:
                notes.append(f"- {name}：缺少可用历史序列，暂不能计算分位。")
            elif category == "估值" and pct >= 80:
                notes.append(f"- {name}：处于历史较高分位，估值压力需要重点关注。")
            elif category == "估值" and pct <= 20:
                notes.append(f"- {name}：处于历史较低分位，估值安全边际相对更高。")
            elif category == "价格" and pct >= 80:
                notes.append(f"- {name}：价格处于历史偏高区间，注意追高风险。")
            elif category == "价格" and pct <= 20:
                notes.append(f"- {name}：价格处于历史偏低区间，需结合基本面判断是否低估。")

        report = f"""## 历史分位

**统计窗口**: 最近{years}年  
**最新交易日**: {latest_date}  
**数据来源**: MongoDB `{DAILY_COLLECTION}` / 缺失时按需使用 BaoStock 补取

{chr(10).join(table_lines)}

### 分位解读

{chr(10).join(notes) if notes else "- 各项指标位于历史中部区间，需结合趋势和基本面进一步判断。"}

> 数据说明：PE/PB/PS 分位来自历史估值序列；PEG需要未来盈利增速预测，当前工具不使用技术指标替代PEG。
"""
        return report.strip()
    except Exception as exc:
        logger.error(f"生成历史分位失败: {exc}", exc_info=True)
        return f"## 历史分位\n\n生成历史分位失败: {exc}"


def build_peer_and_history_report(symbol: str, peer_limit: int = 5, years: int = 5) -> str:
    """Build the combined supplemental report used by analysts."""
    parts = [
        build_peer_comparison_report(symbol, peer_limit=peer_limit),
        build_historical_percentile_report(symbol, years=years),
    ]
    return "\n\n---\n\n".join(parts)
