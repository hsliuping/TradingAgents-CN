"""能力框架调用方迁移回归 — 交易日历（trade_cal）

覆盖 trading_calendar_service._fetch_last_trade_date 从 tushare
daily_basic 逐日回溯 + akshare 新浪日历直调改为 DataFacade 能力
get_data_facade().get_capability("trade_cal").query(start_date=...) 后的
消费者行为：
1. 成功路径：过滤 is_open==1 后取最大 cal_date，source 取门面附加列
2. 空 df / None（门面全源失败语义）-> 回退周一~周五工作日兜底
3. 查询参数：start_date 为今天-15 的 YYYY-MM-DD

patch 方式：调用方为函数内 import，运行时按 capability.facade 包命名空间
查找，monkeypatch 包属性即可生效；TradingCalendarService 无 __init__ 依赖，
可直接实例化。
"""

import asyncio
import re
from datetime import datetime, timedelta

import pandas as pd

import tradingagents.dataflows.capability.facade as facade_module
from app.services.trading_calendar_service import TradingCalendarService


class _FakeFacade:
    def __init__(self, df=None, calls=None):
        self._df = df
        self._calls = calls

    def get_capability(self, capability_id):
        assert capability_id == "trade_cal"
        calls = self._calls
        df = self._df

        class _Capability:
            async def query(self, **params):
                if calls is not None:
                    calls.append({"capability_id": capability_id, **params})
                return df

        return _Capability()


def _patch_facade(monkeypatch, df=None):
    calls = []
    monkeypatch.setattr(facade_module, "get_data_facade", lambda: _FakeFacade(df=df, calls=calls))
    return calls


def _trade_cal_df():
    """trade_cal 能力输出形态（cal_date 为 datetime，含休市日，升序）"""
    return pd.DataFrame(
        {
            "cal_date": pd.to_datetime(
                ["2026-10-21", "2026-10-22", "2026-10-23", "2026-10-24", "2026-10-25"]
            ),
            "is_open": [1, 1, 1, 0, 0],
            "exchange": ["SSE"] * 5,
            "source": ["tushare"] * 5,
            "quality": ["official"] * 5,
        }
    )


def test_fetch_via_capability_returns_latest_open_day(monkeypatch):
    """is_open==1 过滤后取最大 cal_date，source 取门面附加列"""
    calls = _patch_facade(monkeypatch, df=_trade_cal_df())
    service = TradingCalendarService()

    result = asyncio.run(service._fetch_via_capability())

    expected_start = (datetime.now() - timedelta(days=15)).strftime("%Y-%m-%d")
    assert calls == [{"capability_id": "trade_cal", "start_date": expected_start}]
    assert result == ("2026-10-23", "tushare")


def test_fetch_via_capability_returns_none_when_empty(monkeypatch):
    """空 df / None（门面全源失败）-> 返回 None 交由兜底"""
    service = TradingCalendarService()

    _patch_facade(monkeypatch, df=pd.DataFrame())
    assert asyncio.run(service._fetch_via_capability()) is None

    _patch_facade(monkeypatch, df=None)
    assert asyncio.run(service._fetch_via_capability()) is None


def test_fetch_last_trade_date_uses_capability_result(monkeypatch):
    """能力链路成功时直接返回其结果，不再走兜底"""
    _patch_facade(monkeypatch, df=_trade_cal_df())
    service = TradingCalendarService()

    result = asyncio.run(service._fetch_last_trade_date())

    assert result == ("2026-10-23", "tushare")


def test_fetch_last_trade_date_falls_back_to_weekday(monkeypatch):
    """能力链路无数据 -> 回退最近工作日（周一~周五，不保证节假日准确）"""
    _patch_facade(monkeypatch, df=None)
    service = TradingCalendarService()

    last_trade_date, source = asyncio.run(service._fetch_last_trade_date())

    assert source == "fallback"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", last_trade_date)
    parsed = datetime.strptime(last_trade_date, "%Y-%m-%d")
    assert parsed.weekday() < 5
    assert parsed <= datetime.now()
