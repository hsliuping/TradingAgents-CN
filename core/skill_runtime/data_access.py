"""
Skill 运行时本地数据访问模块。

生成的 Skill 只应从此模块导入数据库访问 helper，
避免触发 Skill 生成管线包的初始化副作用。
"""

import logging
import re
from statistics import median
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_COL_BASIC = "stock_basic_info"
_COL_DAILY = "stock_daily_quotes"
_COL_NEWS = "stock_news"
_COL_QUOTES = "market_quotes"
_COL_FINANCIAL = "stock_financial_data"


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
    """获取股票基础信息。"""
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
    """获取股票日线或 K 线数据。"""
    symbol = str(symbol).strip().zfill(6)
    start = start_date.replace("-", "")[:8]
    end = end_date.replace("-", "")[:8]
    db = _get_db()
    col = db[_COL_DAILY]
    query = {
        "symbol": symbol,
        "trade_date": {"$gte": start, "$lte": end},
        "period": period,
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
    """获取股票新闻。"""
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
    """按日期范围获取股票新闻。"""
    symbol = str(symbol).strip().zfill(6)
    try:
        start_dt = datetime.strptime(start_date[:10], "%Y-%m-%d")
        end_dt = datetime.strptime(end_date[:10], "%Y-%m-%d")
    except ValueError:
        return []
    return get_stock_news(symbol, start_date=start_dt, end_date=end_dt, limit=limit)


def get_market_quotes(symbol: str) -> Optional[Dict[str, Any]]:
    """获取股票实时行情。"""
    symbol = str(symbol).strip().zfill(6)
    db = _get_db()
    col = db[_COL_QUOTES]
    return col.find_one({"$or": [{"symbol": symbol}, {"code": symbol}]}, {"_id": 0})


def get_latest_stock_price(symbol: str) -> Optional[float]:
    """获取股票最新可用价格。"""
    symbol = str(symbol).strip().zfill(6)

    quotes = get_market_quotes(symbol) or {}
    for field in ("current_price", "close", "pre_close", "open"):
        value = quotes.get(field)
        if isinstance(value, (int, float)) and value > 0:
            return float(value)

    basic_info = get_stock_basic_info(symbol) or {}
    for field in ("current_price", "close", "pre_close", "open"):
        value = basic_info.get(field)
        if isinstance(value, (int, float)) and value > 0:
            return float(value)

    return None


def get_stock_financial_data(
    symbol: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """获取股票财务数据。"""
    symbol = str(symbol).strip().zfill(6)
    db = _get_db()
    col = db[_COL_FINANCIAL]
    query: Dict[str, Any] = {"$or": [{"symbol": symbol}, {"code": symbol}]}
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


def get_industry_peer_basic_info(
    industry: str,
    exclude_symbol: Optional[str] = None,
    limit: int = 200,
    source: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """按行业获取同行股票基础信息。"""
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
    """汇总行业估值指标统计结果。"""
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
    """获取估值场景标准输入上下文。"""
    symbol = str(symbol).strip().zfill(6)
    basic_info = get_stock_basic_info(symbol) or {}
    market_quotes = get_market_quotes(symbol) or {}
    financial_data = get_stock_financial_data(symbol, limit=financial_limit)
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

6. get_stock_financial_data(symbol, start_date=None, end_date=None, limit=20) -> list
   - 财务数据：兼容 report_period / report_date 两种报告期字段

7. get_stock_valuation_context(symbol, financial_limit=8) -> dict
   - 估值场景标准入口：一次返回 basic_info、market_quotes、current_price、pe_ttm、pb、ps_ttm、financial_data

8. get_industry_peer_basic_info(industry, exclude_symbol=None, limit=200, source=None) -> list
   - 从本地 stock_basic_info 中按行业取同行样本
   - 适合 PB/PE/PS 相对估值、行业对比、样本筛选

9. summarize_industry_valuation(industry, metric="pb", exclude_symbol=None, limit=200, source=None, min_value=0.0, max_value=1000.0) -> dict
   - 基于本地同行样本，返回 average / median / min / max / count
   - 相对估值类 Skill 优先用这个函数，不要自行写 Mongo 聚合

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