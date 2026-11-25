"""
Skill 运行时本地数据访问模块。

生成的 Skill 只应从此模块导入数据库访问 helper，
避免触发 Skill 生成管线包的初始化副作用。
"""

import logging
import re
from statistics import median
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_COL_BASIC = "stock_basic_info"
_COL_DAILY = "stock_daily_quotes"
_COL_NEWS = "stock_news"
_COL_QUOTES = "market_quotes"
_COL_FINANCIAL = "stock_financial_data"
_COL_FINANCIAL_PERIODS = "stock_financial_periods"


def _safe_float(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        try:
            numeric = float(value)
            if numeric != numeric:
                return None
            return numeric
        except (TypeError, ValueError):
            return None
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


def _normalize_date_digits(value: Any) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())[:8]


def _pick_first(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _determine_report_type(period: str) -> str:
    normalized = _normalize_date_digits(period)
    if normalized.endswith("1231"):
        return "annual"
    if normalized:
        return "quarterly"
    return "unknown"


def _normalize_statement_list(section_data: Any) -> List[Dict[str, Any]]:
    if isinstance(section_data, list):
        return [dict(item) for item in section_data if isinstance(item, dict)]
    if isinstance(section_data, dict):
        return [dict(section_data)]
    return []


def _statement_quality_score(record: Dict[str, Any]) -> int:
    return sum(1 for value in record.values() if value not in (None, "", [], {}))


def _prefer_statement(existing: Optional[Dict[str, Any]], candidate: Dict[str, Any]) -> Dict[str, Any]:
    if not existing:
        return dict(candidate)
    if _statement_quality_score(candidate) >= _statement_quality_score(existing):
        merged = dict(existing)
        merged.update(candidate)
        return merged
    merged = dict(candidate)
    merged.update(existing)
    return merged


def _extract_from_candidates(record: Dict[str, Any], *field_names: str) -> Optional[float]:
    for field_name in field_names:
        value = _safe_float(record.get(field_name))
        if value is not None:
            return value
    return None


def _flatten_financial_period_record(period_record: Dict[str, Any]) -> Dict[str, Any]:
    income = dict(period_record.get("income_statement") or {})
    balance = dict(period_record.get("balance_sheet") or {})
    cashflow = dict(period_record.get("cashflow_statement") or {})
    indicators = dict(period_record.get("financial_indicators") or {})

    period_record.update({
        "revenue": _extract_from_candidates(income, "revenue", "oper_rev"),
        "oper_rev": _extract_from_candidates(income, "oper_rev", "revenue"),
        "net_income": _extract_from_candidates(income, "n_income", "net_income"),
        "net_profit": _extract_from_candidates(income, "n_income_attr_p", "net_profit", "n_income"),
        "oper_profit": _extract_from_candidates(income, "operate_profit", "oper_profit"),
        "operating_profit": _extract_from_candidates(income, "operate_profit", "oper_profit"),
        "ebit": _extract_from_candidates(income, "ebit", "operate_profit", "oper_profit"),
        "total_profit": _extract_from_candidates(income, "total_profit"),
        "oper_cost": _extract_from_candidates(income, "oper_cost"),
        "oper_exp": _extract_from_candidates(income, "oper_exp", "sell_exp"),
        "admin_exp": _extract_from_candidates(income, "admin_exp"),
        "fin_exp": _extract_from_candidates(income, "fin_exp"),
        "rd_exp": _extract_from_candidates(income, "rd_exp", "r_and_d"),
        "total_assets": _extract_from_candidates(balance, "total_assets"),
        "total_liab": _extract_from_candidates(balance, "total_liab"),
        "total_equity": _extract_from_candidates(balance, "total_hldr_eqy_exc_min_int", "total_equity", "total_hldr_eqy_inc_min_int"),
        "total_cur_assets": _extract_from_candidates(balance, "total_cur_assets"),
        "total_nca": _extract_from_candidates(balance, "total_nca"),
        "total_cur_liab": _extract_from_candidates(balance, "total_cur_liab"),
        "total_ncl": _extract_from_candidates(balance, "total_ncl"),
        "money_cap": _extract_from_candidates(balance, "money_cap"),
        "accounts_receiv": _extract_from_candidates(balance, "accounts_receiv", "acct_receiv", "acc_receivable"),
        "inventories": _extract_from_candidates(balance, "inventories"),
        "fix_assets": _extract_from_candidates(balance, "fix_assets"),
        "n_cashflow_act": _extract_from_candidates(cashflow, "n_cashflow_act"),
        "n_cashflow_inv_act": _extract_from_candidates(cashflow, "n_cashflow_inv_act"),
        "n_cashflow_fin_act": _extract_from_candidates(cashflow, "n_cashflow_fin_act"),
        "c_cash_equ_end_period": _extract_from_candidates(cashflow, "c_cash_equ_end_period", "end_bal_cash"),
        "c_cash_equ_beg_period": _extract_from_candidates(cashflow, "c_cash_equ_beg_period", "beg_bal_cash"),
        "roe": _extract_from_candidates(indicators, "roe", "roe_avg", "roe_waa"),
        "roa": _extract_from_candidates(indicators, "roa", "roa2"),
        "gross_margin": _extract_from_candidates(indicators, "grossprofit_margin", "gross_margin"),
        "netprofit_margin": _extract_from_candidates(indicators, "netprofit_margin"),
        "debt_to_assets": _extract_from_candidates(indicators, "debt_to_assets"),
        "assets_to_eqt": _extract_from_candidates(indicators, "assets_to_eqt"),
        "current_ratio": _extract_from_candidates(indicators, "current_ratio"),
        "quick_ratio": _extract_from_candidates(indicators, "quick_ratio"),
        "cash_ratio": _extract_from_candidates(indicators, "cash_ratio"),
    })

    period_record["raw_data"] = {
        "income_statement": income,
        "balance_sheet": balance,
        "cashflow_statement": cashflow,
        "financial_indicators": indicators,
    }
    return period_record


def expand_financial_document_to_periods(document: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """将单条财务快照文档按报告期展开为多期标准财务记录。

    Args:
        document: 财务快照文档 dict，需含 raw_data（含 income_statement/balance_sheet/
                  cashflow_statement/financial_indicators/main_business 子段）及
                  symbol/code/name/data_source/report_period 等元信息；为 None 或空时返回空列表

    Returns:
        list[dict]: 按报告期降序排列的标准财务记录列表（无数据时返回 []），每项字段 ——
            symbol: 股票代码（取 document.symbol 或 document.code）
            code: 股票代码（取 document.code 或 document.symbol）
            name: 股票名称
            data_source: 数据源名称
            source: 数据源名称（同 data_source）
            report_period: 报告期 8 位日期串（YYYYMMDD）
            report_date: 报告日期 8 位日期串（同 report_period）
            report_type: 报告类型: "annual"(年报) | "quarterly"(季报) | "unknown"
            ann_date: 公告日期 8 位日期串
            updated_at: 原始文档的更新时间
            income_statement: 利润表分项 dict
            balance_sheet: 资产负债表分项 dict
            cashflow_statement: 现金流量表分项 dict
            financial_indicators: 财务指标分项 dict
            main_business: 主营业务分项 dict（如存在）
            revenue: 营业收入（从 income_statement 提取）
            oper_rev: 营业收入（备用字段）
            net_income: 净利润
            net_profit: 归母净利润
            oper_profit: 经营利润
            operating_profit: 经营利润（同 oper_profit）
            ebit: 息税前利润
            total_profit: 利润总额
            oper_cost: 营业成本
            oper_exp: 营业费用
            admin_exp: 管理费用
            fin_exp: 财务费用
            rd_exp: 研发费用
            total_assets: 总资产
            total_liab: 总负债
            total_equity: 股东权益
            total_cur_assets: 流动资产
            total_nca: 非流动资产
            total_cur_liab: 流动负债
            total_ncl: 非流动负债
            money_cap: 货币资金
            accounts_receiv: 应收账款
            inventories: 存货
            fix_assets: 固定资产
            n_cashflow_act: 经营活动现金流净额
            n_cashflow_inv_act: 投资活动现金流净额
            n_cashflow_fin_act: 筹资活动现金流净额
            c_cash_equ_end_period: 期末现金及等价物
            c_cash_equ_beg_period: 期初现金及等价物
            roe: 净资产收益率
            roa: 总资产收益率
            gross_margin: 毛利率
            netprofit_margin: 净利率
            debt_to_assets: 资产负债率
            assets_to_eqt: 权益乘数
            current_ratio: 流动比率
            quick_ratio: 速动比率
            cash_ratio: 现金比率
            raw_data: 原始分项数据 dict — income_statement, balance_sheet, cashflow_statement, financial_indicators
    """
    if not document:
        return []

    raw_data = document.get("raw_data") or {}
    grouped: Dict[str, Dict[str, Any]] = {}
    section_names = [
        "income_statement",
        "balance_sheet",
        "cashflow_statement",
        "financial_indicators",
        "main_business",
    ]

    for section_name in section_names:
        for entry in _normalize_statement_list(raw_data.get(section_name)):
            period = _normalize_date_digits(
                _pick_first(entry.get("end_date"), entry.get("report_period"), document.get("report_period"), document.get("report_date"))
            )
            if not period:
                continue
            period_entry = grouped.setdefault(period, {
                "symbol": document.get("symbol") or document.get("code"),
                "code": document.get("code") or document.get("symbol"),
                "name": document.get("name"),
                "data_source": document.get("data_source") or document.get("source"),
                "source": document.get("data_source") or document.get("source"),
                "report_period": period,
                "report_date": period,
                "report_type": _determine_report_type(period),
                "ann_date": _normalize_date_digits(_pick_first(entry.get("ann_date"), entry.get("f_ann_date"), document.get("ann_date"))),
                "updated_at": document.get("updated_at"),
            })
            period_entry[section_name] = _prefer_statement(period_entry.get(section_name), entry)
            ann_date = _normalize_date_digits(_pick_first(entry.get("ann_date"), entry.get("f_ann_date"), document.get("ann_date")))
            if ann_date and ann_date > str(period_entry.get("ann_date") or ""):
                period_entry["ann_date"] = ann_date

    latest_period = _normalize_date_digits(_pick_first(document.get("report_period"), document.get("report_date")))
    if latest_period:
        snapshot_entry = grouped.setdefault(latest_period, {
            "symbol": document.get("symbol") or document.get("code"),
            "code": document.get("code") or document.get("symbol"),
            "name": document.get("name"),
            "data_source": document.get("data_source") or document.get("source"),
            "source": document.get("data_source") or document.get("source"),
            "report_period": latest_period,
            "report_date": latest_period,
            "report_type": document.get("report_type") or _determine_report_type(latest_period),
            "ann_date": _normalize_date_digits(document.get("ann_date")),
            "updated_at": document.get("updated_at"),
        })
        for field_name in [
            "revenue", "revenue_ttm", "oper_rev", "net_income", "net_profit", "net_profit_ttm", "oper_profit", "operating_profit", "ebit",
            "total_profit", "oper_cost", "oper_exp", "admin_exp", "fin_exp", "rd_exp", "total_assets", "total_liab", "total_equity",
            "total_cur_assets", "total_nca", "total_cur_liab", "total_ncl", "money_cap", "accounts_receiv", "inventories", "fix_assets",
            "n_cashflow_act", "n_cashflow_inv_act", "n_cashflow_fin_act", "c_cash_equ_end_period", "c_cash_equ_beg_period", "roe", "roa",
            "gross_margin", "netprofit_margin", "debt_to_assets", "assets_to_eqt", "current_ratio", "quick_ratio", "cash_ratio"
        ]:
            value = document.get(field_name)
            if value is not None and snapshot_entry.get(field_name) is None:
                snapshot_entry[field_name] = value

    if not grouped:
        fallback_period = _normalize_date_digits(_pick_first(document.get("report_period"), document.get("report_date")))
        if fallback_period:
            fallback = dict(document)
            fallback["report_period"] = fallback_period
            fallback["report_date"] = fallback_period
            fallback["source"] = fallback.get("data_source") or fallback.get("source")
            grouped[fallback_period] = fallback

    records = [_flatten_financial_period_record(record) for record in grouped.values()]
    records.sort(
        key=lambda item: (
            str(item.get("report_period") or item.get("report_date") or ""),
            str(item.get("ann_date") or ""),
        ),
        reverse=True,
    )
    return records


def _query_financial_period_documents(symbol: str, source: Optional[str], limit: int) -> List[Dict[str, Any]]:
    db = _get_db()
    col = db[_COL_FINANCIAL_PERIODS]
    query: Dict[str, Any] = {"$or": [{"symbol": symbol}, {"code": symbol}]}
    if source:
        query["source"] = source
    cursor = col.find(query, {"_id": 0}).sort([
        ("report_period", -1),
        ("ann_date", -1),
        ("updated_at", -1),
    ]).limit(limit)
    return list(cursor)


def _query_financial_snapshot_documents(symbol: str, source: Optional[str], limit: int) -> List[Dict[str, Any]]:
    db = _get_db()
    col = db[_COL_FINANCIAL]
    query: Dict[str, Any] = {"$or": [{"symbol": symbol}, {"code": symbol}]}
    if source:
        query["data_source"] = source
    items = list(col.find(query, {"_id": 0}).limit(max(limit * 3, 50)))
    items.sort(
        key=lambda item: str(item.get("report_period") or item.get("report_date") or ""),
        reverse=True,
    )
    return items[:limit]


def _get_db():
    """获取同步 MongoDB 连接。"""
    from app.core.database import get_mongo_db_sync

    return get_mongo_db_sync()


def _get_sources(market: str = "a_shares") -> List[str]:
    """获取数据源优先级列表。"""
    try:
        from app.core.data_source_priority import get_enabled_data_sources_sync

        return get_enabled_data_sources_sync(market_category=market)
    except Exception:
        return ["local", "tushare", "akshare", "baostock"]


def get_stock_basic_info(symbol: str, source: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """获取股票基础信息。

    Args:
        symbol: A 股股票代码（6 位数字或含交易所前后缀，会被 zfill 到 6 位）
        source: 指定数据源（如 "tushare" / "akshare"），为 None 时按 _get_sources() 优先级依次尝试

    Returns:
        dict | None: 股票基础信息文档，无匹配时返回 None。字段（以 stock_basic_info 集合存储为准）——
            symbol: 6 位股票代码
            code: 6 位股票代码（备用字段）
            name: 股票名称
            industry: 行业分类
            area: 地区
            list_date: 上市日期
            total_mv: 总市值（万元）
            circ_mv: 流通市值（万元）
            pe_ttm: 滚动市盈率
            pb: 市净率
            pb_mrq: 最近报告期市净率
            ps_ttm: 滚动市销率
            source: 数据源名称
            其他可能的字段：close/current_price/pre_close/open 等行情快照字段
    """
    symbol = str(symbol).strip().zfill(6)
    db = _get_db()
    col = db[_COL_BASIC]
    query = {"$or": [{"symbol": symbol}, {"code": symbol}]}
    if source:
        query["source"] = source
        doc = col.find_one(query, {"_id": 0})
    else:
        doc = None
        for src in _get_sources():
            q = {**query, "source": src}
            doc = col.find_one(q, {"_id": 0})
            if doc:
                break
        if not doc:
            doc = col.find_one(query, {"_id": 0})
    return doc


def get_stock_daily_quotes(
    symbol: str,
    start_date: str,
    end_date: str,
    period: str = "daily",
    source: Optional[str] = None,
    limit: int = 1000,
) -> List[Dict[str, Any]]:
    """获取股票日线或 K 线数据。

    Args:
        symbol: A 股股票代码（6 位数字或含交易所前后缀，会被 zfill 到 6 位）
        start_date: 起始日期，格式 YYYYMMDD 或 YYYY-MM-DD
        end_date: 结束日期，格式 YYYYMMDD 或 YYYY-MM-DD
        period: K 线周期（默认 "daily"），可选 "daily"/"weekly"/"monthly" 等数据库中已存的 period 值
        source: 指定数据源（如 "tushare" / "akshare"），为 None 时按 _get_sources() 优先级依次尝试，
                优先返回第一个有数据的数据源
        limit: 最多返回记录数（默认 1000）

    Returns:
        list[dict]: 按 trade_date 升序排列的日线/K 线记录列表（无数据时返回 []），每项字段 ——
            symbol: 6 位股票代码
            period: K 线周期
            trade_date: 交易日期（YYYYMMDD 或 YYYY-MM-DD，与数据库存储一致）
            open: 开盘价
            high: 最高价
            low: 最低价
            close: 收盘价
            pre_close: 前收盘价
            volume: 成交量
            amount: 成交额
            pct_chg: 涨跌幅（%）
            change: 涨跌额
            turnover: 换手率
            data_source: 数据源名称
            其他字段以数据库 stock_daily_quotes 集合存储为准
    """
    symbol = str(symbol).strip().zfill(6)
    start = start_date.replace("-", "")[:8]
    end = end_date.replace("-", "")[:8]
    start_dash = f"{start[:4]}-{start[4:6]}-{start[6:8]}" if len(start) == 8 else start_date
    end_dash = f"{end[:4]}-{end[4:6]}-{end[6:8]}" if len(end) == 8 else end_date
    db = _get_db()
    col = db[_COL_DAILY]
    date_filter = {
        "$or": [
            {"trade_date": {"$gte": start, "$lte": end}},
            {"trade_date": {"$gte": start_dash, "$lte": end_dash}},
        ]
    }
    query = {
        "symbol": symbol,
        "period": period,
        **date_filter,
    }
    if source:
        query["data_source"] = source
    else:
        for src in _get_sources():
            q = {**query, "data_source": src}
            cursor = col.find(q, {"_id": 0}).sort("trade_date", 1).limit(limit)
            items = list(cursor)
            if items:
                return items
        cursor = col.find(query, {"_id": 0}).sort("trade_date", 1).limit(limit)
        return list(cursor)
    cursor = col.find(query, {"_id": 0}).sort("trade_date", 1).limit(limit)
    return list(cursor)


def get_stock_news(
    symbol: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """获取股票新闻。

    Args:
        symbol: A 股股票代码（6 位数字或含交易所前后缀，会被 zfill 到 6 位）
        start_date: 起始时间（datetime 对象，为 None 时不限起点），同时匹配 publish_time / pub_date 字段
        end_date: 结束时间（datetime 对象，为 None 时不限终点）
        limit: 最多返回记录数（默认 20）

    Returns:
        list[dict]: 按 publish_time（或 pub_date）降序排列的新闻记录列表（无数据时返回 []），每项字段 ——
            symbol: 6 位股票代码
            title: 新闻标题
            content: 新闻正文
            publish_time: 发布时间（datetime，优先字段）
            pub_date: 发布时间（备用字段）
            url: 新闻链接
            source: 新闻来源
            其他字段以数据库 stock_news 集合存储为准
    """
    symbol = str(symbol).strip().zfill(6)
    db = _get_db()
    col = db[_COL_NEWS]
    query: Dict[str, Any] = {"symbol": symbol}
    if start_date or end_date:
        q: Dict[str, datetime] = {}
        if start_date:
            q["$gte"] = start_date
        if end_date:
            q["$lte"] = end_date
        query["$or"] = [{"publish_time": q}, {"pub_date": q}]
    try:
        cursor = col.find(query, {"_id": 0}).sort("publish_time", -1).limit(limit)
        return list(cursor)
    except Exception:
        cursor = col.find(query, {"_id": 0}).sort("pub_date", -1).limit(limit)
        return list(cursor)


def get_stock_news_by_date_range(
    symbol: str,
    start_date: str,
    end_date: str,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """按日期范围获取股票新闻。

    Args:
        symbol: A 股股票代码（6 位数字或含交易所前后缀，会被 zfill 到 6 位）
        start_date: 起始日期字符串，格式 YYYY-MM-DD（仅取前 10 位解析）
        end_date: 结束日期字符串，格式 YYYY-MM-DD
        limit: 最多返回记录数（默认 20）

    Returns:
        list[dict]: 按发布时间降序排列的新闻记录列表（无数据或日期解析失败时返回 []），每项字段 ——
            symbol: 6 位股票代码
            title: 新闻标题
            content: 新闻正文
            publish_time: 发布时间（datetime，优先字段）
            pub_date: 发布时间（备用字段）
            url: 新闻链接
            source: 新闻来源
            其他字段以数据库 stock_news 集合存储为准
    """
    symbol = str(symbol).strip().zfill(6)
    try:
        start_dt = datetime.strptime(start_date[:10], "%Y-%m-%d")
        end_dt = datetime.strptime(end_date[:10], "%Y-%m-%d")
    except ValueError:
        return []
    return get_stock_news(symbol, start_date=start_dt, end_date=end_dt, limit=limit)


def get_market_quotes(symbol: str) -> Optional[Dict[str, Any]]:
    """获取股票实时行情。

    Args:
        symbol: A 股股票代码（6 位数字或含交易所前后缀，会被 zfill 到 6 位）

    Returns:
        dict | None: 实时行情文档，无匹配时返回 None。字段（以 market_quotes 集合存储为准）——
            symbol: 6 位股票代码
            code: 6 位股票代码（备用字段）
            name: 股票名称
            close: 收盘价/最新价
            current_price: 最新价
            pre_close: 前收盘价
            open: 开盘价
            high: 最高价
            low: 最低价
            volume: 成交量
            amount: 成交额
            pct_chg: 涨跌幅（%）
            change: 涨跌额
            turnover: 换手率
            trade_date: 交易日期
            其他字段以数据库 market_quotes 集合存储为准
    """
    symbol = str(symbol).strip().zfill(6)
    db = _get_db()
    col = db[_COL_QUOTES]
    return col.find_one({"$or": [{"symbol": symbol}, {"code": symbol}]}, {"_id": 0})


def get_latest_stock_price(symbol: str) -> Optional[float]:
    """获取股票最新可用价格。

    Args:
        symbol: A 股股票代码（6 位数字或含交易所前后缀，会被 zfill 到 6 位）

    Returns:
        float | None: 标准价格入口，按以下优先级返回第一个有效正值 ——
            1. get_market_quotes() 返回的 close / current_price / pre_close / open 字段
            2. get_stock_basic_info() 返回的 close / current_price / pre_close / open 字段
            若以上均无有效正值，返回 None
    """
    symbol = str(symbol).strip().zfill(6)

    quotes = get_market_quotes(symbol) or {}
    for field in ("close", "current_price", "pre_close", "open"):
        value = quotes.get(field)
        if isinstance(value, (int, float)) and value > 0:
            return float(value)

    basic_info = get_stock_basic_info(symbol) or {}
    for field in ("close", "current_price", "pre_close", "open"):
        value = basic_info.get(field)
        if isinstance(value, (int, float)) and value > 0:
            return float(value)

    return None


def get_stock_financial_data(
    symbol: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 20,
    source: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """获取股票财务数据。

    Args:
        symbol: A 股股票代码（6 位数字或含交易所前后缀，会被 zfill 到 6 位）
        start_date: 起始日期（YYYYMMDD 或 YYYY-MM-DD，为 None 时不限起点），
                    同时匹配 report_period / report_date 字段
        end_date: 结束日期（YYYYMMDD 或 YYYY-MM-DD，为 None 时不限终点）
        limit: 最多返回记录数（默认 20，实际查询会放大 3 倍以保证排序后样本充足）
        source: 指定数据源（如 "tushare" / "akshare"），为 None 时不按 source 过滤

    Returns:
        list[dict]: 按 report_period（或 report_date）降序排列的财务记录列表（无数据时返回 []），
                    每项字段 ——
            symbol: 6 位股票代码
            code: 6 位股票代码（备用字段）
            name: 股票名称
            data_source: 数据源名称
            source: 数据源名称（同 data_source）
            report_period: 报告期
            report_date: 报告日期（备用字段）
            ann_date: 公告日期
            updated_at: 更新时间
            raw_data: 原始分项数据 dict（如存在）— income_statement, balance_sheet,
                      cashflow_statement, financial_indicators, main_business
            其他字段以数据库 stock_financial_data 集合存储为准（可能含 revenue/net_profit/
                      total_assets/roe 等扁平字段，结构因数据源而异）
    """
    symbol = str(symbol).strip().zfill(6)
    db = _get_db()
    col = db[_COL_FINANCIAL]
    query: Dict[str, Any] = {"$or": [{"symbol": symbol}, {"code": symbol}]}
    if source:
        query["data_source"] = source
    if start_date or end_date:
        q: Dict[str, str] = {}
        if start_date:
            q["$gte"] = start_date.replace("-", "")[:8]
        if end_date:
            q["$lte"] = end_date.replace("-", "")[:8]
        query["$and"] = [{"$or": [{"report_period": q}, {"report_date": q}]}]

    items = list(col.find(query, {"_id": 0}).limit(max(limit * 3, 50)))
    items.sort(
        key=lambda item: str(item.get("report_period") or item.get("report_date") or ""),
        reverse=True,
    )
    return items[:limit]


def get_stock_financial_periods(
    symbol: str,
    source: Optional[str] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """获取按报告期展开后的标准财务记录。

    Args:
        symbol: A 股股票代码（6 位数字或含交易所前后缀，会被 zfill 到 6 位）
        source: 指定数据源（如 "tushare" / "akshare"），为 None 时按 _get_sources() 优先级依次尝试，
                优先返回第一个有数据的数据源
        limit: 最多返回记录数（默认 20）

    Returns:
        list[dict]: 按报告期降序排列的标准财务记录列表（无数据时返回 []），每项字段 ——
            symbol: 股票代码
            code: 股票代码（备用字段）
            name: 股票名称
            data_source: 数据源名称
            source: 数据源名称（同 data_source）
            report_period: 报告期 8 位日期串（YYYYMMDD）
            report_date: 报告日期 8 位日期串（同 report_period）
            report_type: 报告类型: "annual"(年报) | "quarterly"(季报) | "unknown"
            ann_date: 公告日期 8 位日期串
            updated_at: 更新时间
            income_statement: 利润表分项 dict
            balance_sheet: 资产负债表分项 dict
            cashflow_statement: 现金流量表分项 dict
            financial_indicators: 财务指标分项 dict
            main_business: 主营业务分项 dict（如存在）
            raw_data: 原始分项数据 dict — income_statement, balance_sheet, cashflow_statement, financial_indicators
            以及经 _flatten_financial_period_record 提取的扁平字段 —
                revenue, oper_rev, net_income, net_profit, oper_profit, operating_profit, ebit,
                total_profit, oper_cost, oper_exp, admin_exp, fin_exp, rd_exp, total_assets,
                total_liab, total_equity, total_cur_assets, total_nca, total_cur_liab, total_ncl,
                money_cap, accounts_receiv, inventories, fix_assets, n_cashflow_act, n_cashflow_inv_act,
                n_cashflow_fin_act, c_cash_equ_end_period, c_cash_equ_beg_period, roe, roa,
                gross_margin, netprofit_margin, debt_to_assets, assets_to_eqt, current_ratio,
                quick_ratio, cash_ratio
    """
    symbol = str(symbol).strip().zfill(6)

    candidate_sources = [source] if source else _get_sources()
    for candidate_source in candidate_sources:
        period_docs = _query_financial_period_documents(symbol, candidate_source, limit)
        if period_docs:
            return period_docs

        snapshot_docs = _query_financial_snapshot_documents(symbol, candidate_source, max(limit, 8))
        expanded: List[Dict[str, Any]] = []
        for document in snapshot_docs:
            expanded.extend(expand_financial_document_to_periods(document))
        if expanded:
            deduped: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
            for item in expanded:
                key = (
                    str(item.get("source") or item.get("data_source") or candidate_source or ""),
                    str(item.get("report_period") or item.get("report_date") or ""),
                    str(item.get("ann_date") or ""),
                )
                existing = deduped.get(key)
                if existing is None or _statement_quality_score(item) >= _statement_quality_score(existing):
                    deduped[key] = item
            records = list(deduped.values())
            records.sort(
                key=lambda item: (
                    str(item.get("report_period") or item.get("report_date") or ""),
                    str(item.get("ann_date") or ""),
                ),
                reverse=True,
            )
            return records[:limit]

    fallback_docs = _query_financial_period_documents(symbol, None, limit)
    if fallback_docs:
        return fallback_docs

    snapshot_docs = _query_financial_snapshot_documents(symbol, None, max(limit, 8))
    expanded: List[Dict[str, Any]] = []
    for document in snapshot_docs:
        expanded.extend(expand_financial_document_to_periods(document))
    expanded.sort(
        key=lambda item: (
            str(item.get("report_period") or item.get("report_date") or ""),
            str(item.get("ann_date") or ""),
        ),
        reverse=True,
    )
    return expanded[:limit]


def get_industry_peer_basic_info(
    industry: str,
    exclude_symbol: Optional[str] = None,
    limit: int = 200,
    source: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """按行业获取同行股票基础信息。

    Args:
        industry: 行业名称关键词（大小写不敏感，使用 regex 子串匹配，例如 "银行" / "半导体"）
        exclude_symbol: 需要排除的股票代码（6 位数字，为 None 时不排除）
        limit: 最多返回记录数（默认 200）
        source: 指定数据源（如 "tushare" / "akshare"），为 None 时不按 source 过滤

    Returns:
        list[dict]: 同行股票基础信息列表（industry 为空时返回 []），每项字段 ——
            symbol: 6 位股票代码
            code: 6 位股票代码（备用字段）
            name: 股票名称
            industry: 行业分类
            area: 地区
            list_date: 上市日期
            total_mv: 总市值（万元）
            circ_mv: 流通市值（万元）
            pe_ttm: 滚动市盈率
            pb: 市净率
            pb_mrq: 最近报告期市净率
            ps_ttm: 滚动市销率
            source: 数据源名称
            其他字段以数据库 stock_basic_info 集合存储为准
    """
    industry_text = str(industry or "").strip()
    if not industry_text:
        return []

    db = _get_db()
    col = db[_COL_BASIC]
    query: Dict[str, Any] = {
        "industry": {"$regex": re.escape(industry_text), "$options": "i"}
    }

    normalized_exclude = str(exclude_symbol or "").strip().zfill(6) if exclude_symbol else ""
    if normalized_exclude:
        query["$and"] = [{"symbol": {"$ne": normalized_exclude}}, {"code": {"$ne": normalized_exclude}}]

    if source:
        query["source"] = source

    cursor = col.find(query, {"_id": 0}).limit(max(limit, 1))
    return list(cursor)


def summarize_industry_valuation(
    industry: str,
    metric: str = "pb",
    exclude_symbol: Optional[str] = None,
    limit: int = 200,
    source: Optional[str] = None,
    min_value: float = 0.0,
    max_value: float = 1000.0,
) -> Dict[str, Any]:
    """汇总行业估值指标统计结果。

    Args:
        industry: 行业名称关键词（同 get_industry_peer_basic_info）
        metric: 估值指标（默认 "pb"），可选 "pb" / "pe" / "ps" 或自定义字段名；
                "pb" 取 pb/pb_mrq，"pe" 取 pe_ttm/pe，"ps" 取 ps_ttm/ps
        exclude_symbol: 需要排除的股票代码（6 位数字，为 None 时不排除）
        limit: 同行样本最大数量（默认 200）
        source: 指定数据源（同 get_industry_peer_basic_info，为 None 时不按 source 过滤）
        min_value: 指标下界（默认 0.0），低于此值的样本会被剔除
        max_value: 指标上界（默认 1000.0），高于此值的样本会被剔除

    Returns:
        dict: 行业估值统计结果，字段（代码中使用 .get() 或 [] 访问这些 key）——
            industry: 输入的行业关键词原值
            metric: 标准化后的指标名（小写）
            count: 有效样本数（int，无样本时为 0）
            average: 均值（float，无样本时为 None）
            median: 中位数（float，无样本时为 None）
            min: 最小值（float，无样本时为 None）
            max: 最大值（float，无样本时为 None）
            samples: 样本列表（最多 20 条），每项结构 —
                {"symbol": 6 位代码, "name": 股票名称, <metric_key>: 指标值}
                （无样本时为 []）
    """
    metric_key = str(metric or "pb").strip().lower()
    metric_fields = {
        "pb": ("pb", "pb_mrq"),
        "pe": ("pe_ttm", "pe"),
        "ps": ("ps_ttm", "ps"),
    }
    candidate_fields = metric_fields.get(metric_key, (metric_key,))

    peers = get_industry_peer_basic_info(
        industry=industry,
        exclude_symbol=exclude_symbol,
        limit=limit,
        source=source,
    )

    values: List[float] = []
    samples: List[Dict[str, Any]] = []
    for item in peers:
        raw_value = None
        for field_name in candidate_fields:
            candidate = item.get(field_name)
            if isinstance(candidate, (int, float)):
                raw_value = float(candidate)
                break

        if raw_value is None or raw_value <= min_value or raw_value >= max_value:
            continue

        values.append(raw_value)
        if len(samples) < 20:
            samples.append(
                {
                    "symbol": item.get("symbol") or item.get("code"),
                    "name": item.get("name"),
                    metric_key: raw_value,
                }
            )

    if not values:
        return {
            "industry": industry,
            "metric": metric_key,
            "count": 0,
            "average": None,
            "median": None,
            "min": None,
            "max": None,
            "samples": [],
        }

    return {
        "industry": industry,
        "metric": metric_key,
        "count": len(values),
        "average": sum(values) / len(values),
        "median": median(values),
        "min": min(values),
        "max": max(values),
        "samples": samples,
    }


def get_stock_valuation_context(symbol: str, financial_limit: int = 8) -> Dict[str, Any]:
    """获取估值场景标准输入上下文。

    Args:
        symbol: A 股股票代码（6 位数字或含交易所前后缀，会被 zfill 到 6 位）
        financial_limit: 财务记录期数（默认 8），传给 get_stock_financial_periods(limit=...)

    Returns:
        dict: 估值场景标准输入上下文，字段（代码中使用 .get() 或 [] 访问这些 key）——
            basic_info: 股票基础信息 dict（无数据时为 {}），字段见 get_stock_basic_info
            market_quotes: 实时行情 dict（无数据时为 {}），字段见 get_market_quotes
            current_price: 最新可用价格（float | None，详见 get_latest_stock_price）
            pe_ttm: 滚动市盈率（取 basic_info.pe_ttm 或 basic_info.pe，可能为 None）
            pb: 市净率（取 basic_info.pb 或 basic_info.pb_mrq，可能为 None）
            ps_ttm: 滚动市销率（取 basic_info.ps_ttm 或 basic_info.ps，可能为 None）
            financial_data: 标准财务记录列表（list[dict]，每项字段见 get_stock_financial_periods）
    """
    symbol = str(symbol).strip().zfill(6)
    basic_info = get_stock_basic_info(symbol) or {}
    market_quotes = get_market_quotes(symbol) or {}
    financial_data = get_stock_financial_periods(symbol, limit=financial_limit)
    current_price = get_latest_stock_price(symbol)

    return {
        "basic_info": basic_info,
        "market_quotes": market_quotes,
        "current_price": current_price,
        "pe_ttm": basic_info.get("pe_ttm") or basic_info.get("pe"),
        "pb": basic_info.get("pb") or basic_info.get("pb_mrq"),
        "ps_ttm": basic_info.get("ps_ttm") or basic_info.get("ps"),
        "financial_data": financial_data,
    }


LOCAL_DATA_API_DOC = """
【本地数据访问 — 可从数据库获取已有数据】

本系统已同步的股票数据存储在 MongoDB 中，生成的 Skill 可直接查询，无需调用外部 API。
优先考虑从本地数据获取，再考虑外部数据源。数据不足时再调用 akshare、tushare 等。

允许导入：from core.skill_runtime.data_access import ...

可用函数（均为同步函数，直接调用即可）：

1. get_stock_basic_info(symbol: str, source=None) -> dict | None
   - 股票基础信息：name、industry、total_mv、pe_ttm、pb 等
   - symbol: 6 位代码

2. get_stock_daily_quotes(symbol, start_date, end_date, period="daily", source=None, limit=1000) -> list
   - 日线/K 线数据：open、high、low、close、volume 等
   - 日期格式：YYYYMMDD 或 YYYY-MM-DD

3. get_stock_news(symbol, start_date=None, end_date=None, limit=20) -> list
   或 get_stock_news_by_date_range(symbol, start_date, end_date, limit=20) -> list
   - 股票新闻：title、content、publish_time、url

4. get_market_quotes(symbol) -> dict | None
   - 实时行情：close、pct_chg、volume、amount

5. get_latest_stock_price(symbol) -> float | None
   - 标准价格入口：优先 market_quotes，再回退 basic_info
   - 估值类 Skill 优先用这个函数取 current_price，不要把价格默默设成 0

6. get_stock_financial_data(symbol, start_date=None, end_date=None, limit=20, source=None) -> list
   - 财务数据：兼容 report_period / report_date 两种报告期字段

7. get_stock_financial_periods(symbol, source=None, limit=20) -> list
    - 按报告期展开后的标准财务记录，适合同比、CAGR 和多期质量因子计算

8. get_stock_valuation_context(symbol, financial_limit=8) -> dict
   - 估值场景标准入口：一次返回 basic_info、market_quotes、current_price、pe_ttm、pb、ps_ttm、financial_data

9. get_industry_peer_basic_info(industry, exclude_symbol=None, limit=200, source=None) -> list
   - 从本地 stock_basic_info 中按行业取同行样本
   - 适合 PB/PE/PS 相对估值、行业对比、样本筛选

10. summarize_industry_valuation(industry, metric="pb", exclude_symbol=None, limit=200, source=None, min_value=0.0, max_value=1000.0) -> dict
   - 基于本地同行样本，返回 average / median / min / max / count
   - 相对估值类 Skill 优先用这个函数，不要自行写 Mongo 聚合

【标准结构化金融数据能力 — 推荐 Agent/Skill 优先复用】
允许导入：from core.skill_runtime.standard_financial_apis import ...

11. get_historical_financial_annual_series(symbol, years=10, source=None) -> dict
   - 一键返回最近 N 年年报序列，字段含 revenue、net_profit、roe、gross_margin、operating_cashflow、free_cashflow、debt_to_assets 等
   - 适合巴菲特深度分析、长期财务台账、5-10 年趋势，不要用 get_income_analysis 的 Markdown 表格替代

12. get_profitability_stability_metrics(symbol, years=10, source=None) -> dict
   - 基于年报序列计算营收/净利/ROE/毛利率及同比增长的均值、中位数、波动率、变异系数
   - 盈利稳定性、护城河财务证据、质量分析优先用这个函数

13. get_cashflow_quality_trend(symbol, years=10, source=None) -> dict
   - 基于年报序列返回 OCF/净利、FCF/净利、OCF margin、FCF margin 的年度趋势和统计摘要
   - 现金流质量、利润含金量、自由现金流分析优先用这个函数

14. get_historical_valuation_percentile(symbol, metrics=None, lookback_years=5, as_of_date=None) -> dict
   - 结构化返回 pe_ttm / pb / ps_ttm / pcf_ttm 的历史分位、当前值、中位数、样本数和窗口
   - 替代 get_stock_fundamentals_unified 中隐藏的 3 年文本分位输出

⚠️ 注意：以上函数 4-5（get_market_quotes、get_latest_stock_price）和 8（get_stock_valuation_context）只能拿到当前 PE/PB 快照。
需要 **结构化历史 PE/PB 分位**（如历史分位数、PE 通道、安全边际）时，优先用标准函数：

    from core.skill_runtime.standard_financial_apis import get_historical_valuation_percentile
    result = get_historical_valuation_percentile("600519", metrics=["pe_ttm", "pb"], lookback_years=5)

如果只需要原始历史估值序列，可用 project_access 的专用函数：

    from core.skill_runtime.project_access import get_external_valuation_data
    result = get_external_valuation_data("600519", "2020-01-01", "2025-06-01")
    # 返回 {source: "baostock", data: [{date, close, pe_ttm, pb_mrq, ps_ttm, pcf_ttm}, ...]}

不要用 get_external_historical_data 代替——它只含 OHLCV 价格，不含 PE/PB 字段。

示例1：先查本地，无数据再调外部 API
    from core.skill_runtime.data_access import get_stock_basic_info, get_stock_daily_quotes
    info = get_stock_basic_info("600519")
    if info:
        ...
    else:
        ...

示例2：估值类 Skill 的推荐写法
    from core.skill_runtime.data_access import get_stock_valuation_context
    ctx = get_stock_valuation_context("600519")
    current_price = ctx["current_price"]
    if current_price is None or current_price <= 0:
        return {"status": "error", "message": "未获取到有效现价，无法估值"}

    pe_ttm = ctx["pe_ttm"]
    pb = ctx["pb"]
    ps_ttm = ctx["ps_ttm"]
    financial_data = ctx["financial_data"]

示例3：行业 PB 相对估值的推荐写法
    from core.skill_runtime.data_access import get_stock_valuation_context, summarize_industry_valuation

    ctx = get_stock_valuation_context(symbol)
    industry = (ctx["basic_info"] or {}).get("industry")
    industry_pb = summarize_industry_valuation(industry, metric="pb", exclude_symbol=symbol)
"""