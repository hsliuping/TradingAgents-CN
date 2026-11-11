"""能力框架调用方迁移回归 — 复盘 K 线（stock_daily）

覆盖 trade_review_service._fetch_kline_unified A 股分支从 akshare
直调（stock_zh_a_hist + 中文列 rename）改为 query_capability_sync
("stock_daily") 后的消费者行为：
1. 标准列直读（免 rename）：date/open/high/low/close/volume
2. date 为 datetime 时截取 YYYY-MM-DD（与原 astype(str) 后 [:10] 等价）
3. 参数透传：YYYY-MM-DD 原样透传（不再去横线）
4. None/空 df 防御（门面全源失败语义）

patch 方式：调用方为函数内 import，运行时按 capability 包命名空间
查找，monkeypatch 包属性即可生效。
"""

import asyncio
from datetime import datetime

import pandas as pd
import pytest

import tradingagents.dataflows.capability as capability_pkg
from app.services.trade_review_service import TradeReviewService


def _patch_capability(monkeypatch, df=None, error=None):
    calls = []

    def _stub(capability_id, **params):
        calls.append({"capability_id": capability_id, **params})
        if error is not None:
            raise error
        return df

    monkeypatch.setattr(capability_pkg, "query_capability_sync", _stub)
    return calls


def _std_daily_df():
    """stock_daily 能力标准输出形态（date 为 datetime，升序）"""
    return pd.DataFrame(
        {
            "ts_code": ["600519.SH"] * 2,
            "date": [datetime(2024, 9, 2), datetime(2024, 9, 3)],
            "open": [1700.0, 1710.0],
            "high": [1720.0, 1730.0],
            "low": [1690.0, 1700.0],
            "close": [1710.0, 1725.0],
            "volume": [30000.0, 31000.0],
        }
    )


def test_fetch_kline_a_share_maps_standard_columns(monkeypatch):
    """标准列直读 + date 截取 + 参数原样透传"""
    calls = _patch_capability(monkeypatch, df=_std_daily_df())
    svc = TradeReviewService.__new__(TradeReviewService)

    klines = asyncio.run(
        svc._fetch_kline_unified("600519", "CN", "2024-09-01", "2024-09-30")
    )

    assert len(klines) == 2
    assert klines[0]["date"] == "2024-09-02"  # datetime -> YYYY-MM-DD
    assert klines[-1]["date"] == "2024-09-03"
    assert klines[0]["open"] == 1700.0
    assert klines[0]["close"] == 1710.0
    assert klines[0]["volume"] == 30000.0
    assert calls[0] == {
        "capability_id": "stock_daily",
        "symbol": "600519",
        "start_date": "2024-09-01",
        "end_date": "2024-09-30",
    }


def test_fetch_kline_none_empty_and_error_defense(monkeypatch):
    """None / 空 df / 抛异常 -> 统一返回空列表，不抛出"""
    svc = TradeReviewService.__new__(TradeReviewService)

    _patch_capability(monkeypatch, df=None)
    assert (
        asyncio.run(svc._fetch_kline_unified("600519", "CN", "2024-09-01", "2024-09-30"))
        == []
    )

    _patch_capability(monkeypatch, df=pd.DataFrame())
    assert (
        asyncio.run(svc._fetch_kline_unified("600519", "CN", "2024-09-01", "2024-09-30"))
        == []
    )

    _patch_capability(monkeypatch, error=RuntimeError("全源失败"))
    assert (
        asyncio.run(svc._fetch_kline_unified("600519", "CN", "2024-09-01", "2024-09-30"))
        == []
    )


def test_fetch_kline_skips_invalid_rows(monkeypatch):
    """date 为空的行被过滤（len(date) >= 10 防御保留）"""
    df = _std_daily_df()
    df.loc[len(df)] = ["600519.SH", "", 0, 0, 0, 0, 0]  # type: ignore[index]
    _patch_capability(monkeypatch, df=df)
    svc = TradeReviewService.__new__(TradeReviewService)

    klines = asyncio.run(
        svc._fetch_kline_unified("600519", "CN", "2024-09-01", "2024-09-30")
    )

    assert len(klines) == 2
    assert all(k["date"] for k in klines)
