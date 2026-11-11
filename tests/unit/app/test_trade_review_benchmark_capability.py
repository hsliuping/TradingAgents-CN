"""能力框架调用方迁移回归 — 复盘大盘/行业基准（index_daily）

覆盖 trade_review_service._get_benchmark_data 从 tushare provider 直调
（provider.get_index_daily）改为 DataFacade 能力
get_data_facade().get_capability("index_daily").query(...) 后的消费者行为：
1. 参数透传：ts_code 固定沪深300，start/end 去 YYYY-MM-DD 横线（YYYYMMDD）
2. 标准列直读：trade_date 排序后取首尾收盘价算涨跌幅、high.max/low.min
3. None/空 df 防御（门面全源失败语义）：market_benchmark 保持默认 None，
   不抛出
4. 行业归属仍经 get_stock_sector_info 统一工具函数获取

patch 方式：调用方为函数内 import，运行时按 capability.facade 包命名空间
查找，monkeypatch 包属性即可生效；TradeReviewService.__init__ 依赖 MongoDB，
用 __new__ 绕过。
"""

import asyncio

import pandas as pd

import tradingagents.dataflows.capability.facade as facade_module
from app.services.trade_review_service import TradeReviewService


class _FakeFacade:
    def __init__(self, df=None, error=None, calls=None):
        self._df = df
        self._error = error
        self._calls = calls

    def get_capability(self, capability_id):
        assert capability_id == "index_daily"
        calls = self._calls
        df = self._df
        error = self._error

        class _Capability:
            async def query(self, **params):
                if calls is not None:
                    calls.append({"capability_id": capability_id, **params})
                if error is not None:
                    raise error
                return df

        return _Capability()


def _patch_facade(monkeypatch, df=None, error=None):
    calls = []
    monkeypatch.setattr(
        facade_module, "get_data_facade", lambda: _FakeFacade(df=df, error=error, calls=calls)
    )
    return calls


def _patch_sector_info(monkeypatch):
    async def _fake_sector_info(stock_code):
        return {"industry": "银行"}

    monkeypatch.setattr(
        "core.tools.sector_tools.get_stock_sector_info", _fake_sector_info
    )


def _index_daily_df():
    """index_daily 能力 tushare 源输出形态（trade_date 为 YYYYMMDD 字符串）"""
    return pd.DataFrame(
        {
            "ts_code": ["000300.SH"] * 2,
            "trade_date": ["20260408", "20260407"],
            "open": [3910.0, 3900.0],
            "high": [3960.0, 3950.0],
            "low": [3890.0, 3880.0],
            "close": [3950.0, 3900.0],
            "vol": [100.0, 110.0],
            "amount": [1000.0, 1100.0],
            "pct_chg": [1.28, 0.0],
            "source": ["tushare", "tushare"],
            "quality": ["official", "official"],
        }
    )


def test_get_benchmark_data_uses_index_daily_capability(monkeypatch):
    """参数去横线透传 + trade_date 排序取首尾 + 行业归属正常填充"""
    calls = _patch_facade(monkeypatch, df=_index_daily_df())
    _patch_sector_info(monkeypatch)
    svc = TradeReviewService.__new__(TradeReviewService)

    result = asyncio.run(svc._get_benchmark_data("000001", "A股", "2026-04-07", "2026-04-08"))

    assert calls == [
        {
            "capability_id": "index_daily",
            "ts_code": "000300.SH",
            "start_date": "20260407",
            "end_date": "20260408",
        }
    ]
    market = result["market_benchmark"]
    assert market["index_code"] == "000300.SH"
    assert market["index_name"] == "沪深300"
    assert market["start_price"] == 3900.0
    assert market["end_price"] == 3950.0
    assert market["change_pct"] == round((3950.0 - 3900.0) / 3900.0 * 100, 2)
    assert market["period_high"] == 3960.0
    assert market["period_low"] == 3880.0
    assert result["industry_benchmark"]["industry_name"] == "银行"
    assert result["attribution"]["beta_contribution"] == market["change_pct"]


def test_get_benchmark_data_keeps_defaults_when_capability_empty(monkeypatch):
    """空 df / None（门面全源失败）-> market_benchmark 保持默认 None，不抛出"""
    svc = TradeReviewService.__new__(TradeReviewService)
    _patch_sector_info(monkeypatch)

    _patch_facade(monkeypatch, df=pd.DataFrame())
    result = asyncio.run(svc._get_benchmark_data("000001", "A股", "2026-04-07", "2026-04-08"))
    assert result["market_benchmark"]["change_pct"] is None
    assert result["attribution"]["beta_contribution"] is None

    _patch_facade(monkeypatch, df=None)
    result = asyncio.run(svc._get_benchmark_data("000001", "A股", "2026-04-07", "2026-04-08"))
    assert result["market_benchmark"]["change_pct"] is None
    assert result["industry_benchmark"]["industry_name"] == "银行"


def test_get_benchmark_data_swallows_capability_error(monkeypatch):
    """能力查询抛异常 -> 记录日志后返回默认结构，不向上抛出"""
    svc = TradeReviewService.__new__(TradeReviewService)
    _patch_sector_info(monkeypatch)
    _patch_facade(monkeypatch, error=RuntimeError("全源失败"))

    result = asyncio.run(svc._get_benchmark_data("000001", "A股", "2026-04-07", "2026-04-08"))

    assert result["market_benchmark"]["change_pct"] is None
    assert result["attribution"]["beta_contribution"] is None
