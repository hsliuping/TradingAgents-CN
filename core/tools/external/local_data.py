"""
本地数据访问模块 — 供生成的 Skill 从数据库获取数据

生成的 Skill 可从此模块导入，直接查询系统已同步的股票数据，
无需调用外部 API。适用于数据组合、二次加工等场景。

用法示例：
    from core.tools.external.local_data import (
        get_stock_basic_info,
        get_stock_daily_quotes,
        get_stock_news,
        get_market_quotes,
        get_etf_basic_info,
        get_etf_daily_quotes,
    )
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# 集合名（A 股）
_COL_BASIC = "stock_basic_info"
_COL_DAILY = "stock_daily_quotes"
_COL_NEWS = "stock_news"
_COL_QUOTES = "market_quotes"
_COL_FINANCIAL = "stock_financial_data"

# 集合名（ETF）
_COL_ETF_BASIC = "etf_basic_info"
_COL_ETF_DAILY = "etf_daily_quotes"


def _get_db():
    """获取同步 MongoDB 连接"""
    from app.core.database import get_mongo_db_sync
    return get_mongo_db_sync()


def _get_sources(market: str = "a_shares") -> List[str]:
    """获取数据源优先级列表"""
    try:
        from app.core.data_source_priority import get_enabled_data_sources_sync
        return get_enabled_data_sources_sync(market_category=market)
    except Exception:
        return ["local", "tushare", "akshare", "baostock"]


def get_stock_basic_info(symbol: str, source: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    获取股票基础信息（从本地数据库）

    Args:
        symbol: 6 位股票代码，如 600519
        source: 指定数据源（可选），不传则按系统优先级查询

    Returns:
        股票基础信息字典，含 name、industry、total_mv、pe_ttm 等；无数据返回 None
    """
    symbol = str(symbol).strip().zfill(6)
    db = _get_db()
    col = db[_COL_BASIC]
    query = {"$or": [{"symbol": symbol}, {"code": symbol}]}
    if source:
        query["source"] = source
        doc = col.find_one(query, {"_id": 0})
    else:
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
    """
    获取股票日线/K 线数据（从本地数据库）

    Args:
        symbol: 6 位股票代码
        start_date: 开始日期，格式 YYYYMMDD 或 YYYY-MM-DD
        end_date: 结束日期，格式同上
        period: 周期，daily/weekly/monthly，默认 daily
        source: 指定数据源（可选）
        limit: 最大条数，默认 1000

    Returns:
        日线列表，按 trade_date 升序
    """
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
    """
    获取股票新闻（从本地数据库）

    Args:
        symbol: 6 位股票代码
        start_date: 开始时间（可选）
        end_date: 结束时间（可选）
        limit: 最大条数，默认 20

    Returns:
        新闻列表，含 title、content、publish_time、url 等
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
    """
    按日期范围获取股票新闻（从本地数据库）

    Args:
        symbol: 6 位股票代码
        start_date: 开始日期 YYYY-MM-DD
        end_date: 结束日期 YYYY-MM-DD
        limit: 最大条数

    Returns:
        新闻列表
    """
    symbol = str(symbol).strip().zfill(6)
    try:
        start_dt = datetime.strptime(start_date[:10], "%Y-%m-%d")
        end_dt = datetime.strptime(end_date[:10], "%Y-%m-%d")
    except ValueError:
        return []
    return get_stock_news(symbol, start_date=start_dt, end_date=end_dt, limit=limit)


def get_market_quotes(symbol: str) -> Optional[Dict[str, Any]]:
    """
    获取股票实时行情（从本地数据库）

    Args:
        symbol: 6 位股票代码

    Returns:
        行情字典，含 close、pct_chg、volume、amount 等；无数据返回 None
    """
    symbol = str(symbol).strip().zfill(6)
    db = _get_db()
    col = db[_COL_QUOTES]
    doc = col.find_one({"$or": [{"symbol": symbol}, {"code": symbol}]}, {"_id": 0})
    return doc


def get_latest_stock_price(symbol: str) -> Optional[float]:
    """
    获取股票最新可用价格。

    优先使用 market_quotes，其次回退到 stock_basic_info 中的 close/current_price/pre_close。
    若无正数价格则返回 None。
    """
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
    """
    获取股票财务数据（从本地数据库）

    Args:
        symbol: 6 位股票代码
        start_date: 开始日期 YYYYMMDD（可选）
        end_date: 结束日期 YYYYMMDD（可选）
        limit: 最大条数

    Returns:
        财务数据列表
    """
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

    # 财务数据历史上同时存在 report_period / report_date 两种口径，
    # 这里统一拉取后在 Python 侧兼容排序，避免生成的 Skill 因字段差异取到错误记录。
    items = list(col.find(query, {"_id": 0}).limit(max(limit * 3, 50)))
    items.sort(
        key=lambda item: str(item.get("report_period") or item.get("report_date") or ""),
        reverse=True,
    )
    return items[:limit]


def get_stock_valuation_context(symbol: str, financial_limit: int = 8) -> Dict[str, Any]:
    """
    获取估值场景的标准输入上下文。

    返回值包含：
    - basic_info: 基础信息
    - market_quotes: 实时行情
    - current_price: 最新可用价格
    - pe_ttm / pb / ps_ttm: 常用估值指标
    - financial_data: 最近若干期财务数据
    """
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


# ─── ETF 数据访问 ──────────────────────────────────────────────


def get_etf_basic_info(symbol: str) -> Optional[Dict[str, Any]]:
    """
    获取 ETF 基础信息（从本地数据库）

    Args:
        symbol: 6 位 ETF 代码，如 510050、159919

    Returns:
        ETF 基础信息字典，含 name、fund_type、track_index、fund_scale、
        management_fee、unit_nav、accum_nav 等；无数据返回 None
    """
    symbol = str(symbol).strip().zfill(6)
    db = _get_db()
    doc = db[_COL_ETF_BASIC].find_one({"code": symbol}, {"_id": 0})
    return doc


def get_etf_daily_quotes(
    symbol: str,
    start_date: str,
    end_date: str,
    limit: int = 1000,
) -> List[Dict[str, Any]]:
    """
    获取 ETF 日线数据（从本地数据库）

    Args:
        symbol: 6 位 ETF 代码
        start_date: 开始日期，格式 YYYYMMDD 或 YYYY-MM-DD
        end_date: 结束日期，格式同上
        limit: 最大条数，默认 1000

    Returns:
        日线列表，按 trade_date 升序；含 close、pct_chg、volume、amount、unit_nav、accum_nav
    """
    symbol = str(symbol).strip().zfill(6)
    start = start_date.replace("-", "")[:8]
    end = end_date.replace("-", "")[:8]
    db = _get_db()
    col = db[_COL_ETF_DAILY]
    cursor = (
        col.find(
            {"code": symbol, "trade_date": {"$gte": start, "$lte": end}},
            {"_id": 0},
        )
        .sort("trade_date", 1)
        .limit(limit)
    )
    return list(cursor)


# ─── API 文档（供代码生成器引用）────────────────────────────────


# 供代码生成器 Prompt 引用的文档
LOCAL_DATA_API_DOC = """
【本地数据访问 — 可从数据库获取已有数据】

本系统已同步的股票数据存储在 MongoDB 中，生成的 Skill 可直接查询，无需调用外部 API。
优先考虑从本地数据获取，再考虑外部数据源。数据不足时再调用 akshare、tushare 等。

允许导入：from core.tools.external.local_data import ...

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

8. get_etf_basic_info(symbol: str) -> dict | None
   - ETF 基础信息：name、fund_type、track_index、fund_scale、management_fee、unit_nav、accum_nav 等
   - symbol: 6 位 ETF 代码，如 510050、159919

9. get_etf_daily_quotes(symbol, start_date, end_date, limit=1000) -> list
   - ETF 日线数据：close、pct_chg、volume、amount、unit_nav、accum_nav
   - 日期格式：YYYYMMDD 或 YYYY-MM-DD

示例1：先查本地，无数据再调外部 API
    from core.tools.external.local_data import get_stock_basic_info, get_stock_daily_quotes
    info = get_stock_basic_info("600519")
    if info:
        ...
    else:
        ...

示例2：估值类 Skill 的推荐写法
    from core.tools.external.local_data import get_stock_valuation_context
    ctx = get_stock_valuation_context("600519")
    current_price = ctx["current_price"]
    if current_price is None or current_price <= 0:
        return {"status": "error", "message": "未获取到有效现价，无法估值"}

    pe_ttm = ctx["pe_ttm"]
    pb = ctx["pb"]
    ps_ttm = ctx["ps_ttm"]
    financial_data = ctx["financial_data"]

硬规则：
- 估值类 Skill 不允许把 current_price 默默设为 0 后继续计算
- fair_value、valuation_range 若缺少必要输入，应返回 invalid / error，而不是输出 0
- 财务数据排序优先使用 report_period，其次兼容 report_date
"""
