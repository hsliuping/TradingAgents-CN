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
    """统一为 YYYYMMDD 便于 MongoDB 字符串比较"""
    s = str(s).replace("-", "")[:8]
    return s


def fetch_ohlcv_from_mongo(
    symbols: List[str],
    start_date: str,
    end_date: str,
    market: str = "CN",
) -> dict[str, pd.DataFrame]:
    """
    从 MongoDB stock_daily_quotes 获取 OHLCV 数据
    返回 {symbol: DataFrame}
    """
    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB]
    coll = db["stock_daily_quotes"]

    result = {}
    for sym in symbols:
        code = sym.replace(".SH", "").replace(".SZ", "").zfill(6)
        sd = _normalize_date(start_date)
        ed = _normalize_date(end_date)
        q: dict = {
            "$and": [
                {"$or": [{"symbol": code}, {"symbol": sym}, {"code": code}]},
                {"trade_date": {"$gte": sd, "$lte": ed}},
                {"$or": [{"period": "daily"}, {"period": {"$exists": False}}]},
            ]
        }
        cursor = coll.find(q, sort=[("trade_date", 1)])
        rows = list(cursor)
        if not rows:
            logger.warning(f"无数据: {sym} ({code})")
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
) -> List[bt.feeds.PandasData]:
    """创建 Backtrader 数据源列表"""
    data_map = fetch_ohlcv_from_mongo(symbols, start_date, end_date, market)
    feeds = []
    for sym, df in data_map.items():
        if df.empty or len(df) < 2:
            continue
        feeds.append(bt.feeds.PandasData(dataname=df, name=sym))
    return feeds
