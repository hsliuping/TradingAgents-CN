"""
MongoDB stock_daily_quotes → Backtrader PandasData
"""
import logging
from datetime import datetime
from typing import List, Optional

import pandas as pd
import backtrader as bt
from pymongo import MongoClient

from config import MONGO_URI, MONGO_DB

logger = logging.getLogger(__name__)


def _normalize_date(s: str) -> str:
    """统一为 YYYY-MM-DD，与 historical_data_service 存储格式一致"""
    s = str(s).replace("-", "")[:8]
    if len(s) >= 8:
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    return s


def fetch_ohlcv_from_mongo(
    symbols: List[str],
    start_date: str,
    end_date: str,
    market: str = "CN",
    data_source: Optional[str] = "tushare",
) -> dict[str, pd.DataFrame]:
    """
    从 MongoDB stock_daily_quotes 获取 OHLCV 数据
    data_source: 数据源筛选，避免多数据源重复（tushare/akshare/baostock/local），默认 tushare
    返回 {symbol: DataFrame}
    """
    sd = _normalize_date(start_date)
    ed = _normalize_date(end_date)
    logger.info(
        f"[data_feed] 查询参数: symbols={symbols}, start_date={sd}, end_date={ed}, market={market}, "
        f"data_source={data_source}, MONGO_DB={MONGO_DB}"
    )
    # 脱敏打印 URI（仅显示 host/db）
    _uri_display = MONGO_URI.split("@")[-1] if "@" in MONGO_URI else MONGO_URI
    logger.info(f"[data_feed] MONGO_URI(脱敏): ...@{_uri_display}")

    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB]
    coll = db["stock_daily_quotes"]

    result = {}
    for sym in symbols:
        code = sym.replace(".SH", "").replace(".SZ", "").zfill(6)
        q_conditions: list = [
            {"$or": [{"symbol": code}, {"symbol": sym}, {"code": code}]},
            {"trade_date": {"$gte": sd, "$lte": ed}},
            {"$or": [{"period": "daily"}, {"period": {"$exists": False}}]},
        ]
        if data_source:
            q_conditions.append({"data_source": data_source})
        q: dict = {"$and": q_conditions}
        logger.info(f"[data_feed] {sym} 查询条件: {q}")
        cursor = coll.find(q, sort=[("trade_date", 1)])
        rows = list(cursor)
        logger.info(f"[data_feed] {sym} 命中 {len(rows)} 条")
        if not rows:
            logger.warning(f"无数据: {sym} ({code}), 查询: {q}")
            continue
        df = pd.DataFrame(rows)
        # 多数据源可能同一日期有多条，按 trade_date 去重取第一条
        df = df.drop_duplicates(subset=["trade_date"], keep="first")
        df["datetime"] = pd.to_datetime(df["trade_date"])
        df = df.set_index("datetime")
        for col in ["open", "high", "low", "close", "volume"]:
            if col not in df.columns:
                df[col] = 0.0
        df = df[["open", "high", "low", "close", "volume"]].astype(float)
        df["volume"] = df["volume"].fillna(0)
        result[sym] = df

    client.close()
    return result


def make_backtrader_feed(
    symbols: List[str],
    start_date: str,
    end_date: str,
    market: str = "CN",
    data_source: Optional[str] = "tushare",
) -> List[bt.feeds.PandasData]:
    """创建 Backtrader 数据源列表"""
    data_map = fetch_ohlcv_from_mongo(
        symbols, start_date, end_date, market, data_source
    )
    feeds = []
    for sym, df in data_map.items():
        if df.empty or len(df) < 2:
            continue
        feeds.append(bt.feeds.PandasData(dataname=df, name=sym))
    return feeds
