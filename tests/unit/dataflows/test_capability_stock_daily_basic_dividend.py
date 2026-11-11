"""数据能力注册机制 — 个股每日指标与分红送股能力测试（fundamentals 长尾迁移）

stock_daily_basic（个股按日估值指标区间序列，stock_daily 粒度）与
stock_dividend（个股分红送股事件流，stock_event 粒度）目前仅 tushare 源
（标准名=tushare 原生字段名，零映射）。本文件覆盖：
1. 注册健全性：源集合 + grain + 参数签名机器校验 + field_mapping 目标合法性
2. tushare 源适配器契约：不可用/异常 -> None 降级；空表 -> 空 DataFrame 不降级；
   排序与 limit 截断；请求 fields 与 Schema 标准字段集合一致（防缺失列填 NA 漂移）
3. facade 真实能力全链路：标准化裁剪 + 全源失败空表 + query_capability_sync 同步路径

设计文档：docs/05-design/v4.0/data-architecture-problems-and-optimization.md 5.4
"""

import asyncio
import inspect
import logging

import pandas as pd

import tradingagents.dataflows.providers.china.tushare  # noqa: F401 —— import 即注册 tushare 源
from tradingagents.dataflows.capability import query_capability_sync
from tradingagents.dataflows.capability.facade import get_data_facade
from tradingagents.dataflows.capability.registry import registry
from tradingagents.dataflows.capability.schema import GRAIN_STOCK_DAILY, GRAIN_STOCK_EVENT

EXPECTED_SOURCES = {
    "stock_daily_basic": {"tushare"},
    "stock_dividend": {"tushare"},
}

EXPECTED_GRAIN = {
    "stock_daily_basic": GRAIN_STOCK_DAILY,
    "stock_dividend": GRAIN_STOCK_EVENT,
}

# tushare 原生字段名基准（标准名=原生名，防 schema 漂移）
TUSHARE_NATIVE_FIELDS = {
    "stock_daily_basic": {"ts_code", "trade_date", "pe", "pe_ttm", "pb", "ps_ttm"},
    "stock_dividend": {
        "ts_code", "end_date", "ann_date", "div_proc", "stk_div",
        "stk_bo_rate", "stk_co_rate", "cash_div", "cash_div_tax",
        "record_date", "ex_date", "pay_date",
    },
}


def _fixed_order(monkeypatch, order):
    from tradingagents.dataflows.capability import facade as facade_mod

    monkeypatch.setattr(
        facade_mod.CapabilityHandle,
        "_resolve_source_order",
        lambda self, registered: [s for s in order if s in registered],
    )


class _StubTushareApi:
    """daily_basic / dividend 打桩：记录调用参数，返回预设载荷或抛错"""

    def __init__(self, daily_basic=None, dividend=None):
        self._daily_basic = daily_basic
        self._dividend = dividend
        self.daily_basic_calls = []
        self.dividend_calls = []

    def daily_basic(self, **kwargs):
        self.daily_basic_calls.append(kwargs)
        if isinstance(self._daily_basic, Exception):
            raise self._daily_basic
        return self._daily_basic

    def dividend(self, **kwargs):
        self.dividend_calls.append(kwargs)
        if isinstance(self._dividend, Exception):
            raise self._dividend
        return self._dividend


def _make_provider(monkeypatch, api):
    """构造跳过 __init__ 的 TushareProvider 桩（补 logger/api，is_available 恒真）"""
    from tradingagents.dataflows.providers.china.tushare import TushareProvider

    monkeypatch.setattr(TushareProvider, "is_available", lambda self: True)
    provider = TushareProvider.__new__(TushareProvider)
    provider.api = api
    provider.logger = logging.getLogger("test-stub-tushare")
    return provider


def _patch_tushare_factory(monkeypatch, provider):
    from tradingagents.dataflows.capability import facade as facade_mod

    monkeypatch.setitem(facade_mod._PROVIDER_FACTORIES, "tushare", lambda: provider)


# ---------------------------------------------------------------- 注册健全性


def test_registration_sanity():
    """源集合 + grain + Schema 参数被 provider 方法签名接受 + 映射目标合法性"""
    for cap_id, expected in EXPECTED_SOURCES.items():
        assert set(registry.get_sources(cap_id)) == expected, cap_id
        for source in sorted(registry.get_sources(cap_id)):
            entry = registry.get_entry(cap_id, source)
            assert entry.schema.grain == EXPECTED_GRAIN[cap_id], cap_id
            func_params = set(inspect.signature(entry.func).parameters)
            for param in entry.schema.params:
                assert param.name in func_params, f"{cap_id}/{source} 缺参数 {param.name}"
            assert set(entry.field_mapping.values()) <= set(
                entry.schema.standard_field_names()
            ), cap_id


def test_tushare_standard_fields_are_native_columns():
    """tushare 源标准名=tushare 原生字段名（字段集合对齐基准防漂移）"""
    for cap_id, expected in TUSHARE_NATIVE_FIELDS.items():
        entry = registry.get_entry(cap_id, "tushare")
        assert set(entry.schema.standard_field_names()) == expected, cap_id


# ---------------------------------------------------------------- tushare 源适配器契约


def test_tushare_daily_basic_unavailable_returns_none(monkeypatch):
    """源不可用 -> None（触发门面降级语义）"""
    from tradingagents.dataflows.providers.china.tushare import TushareProvider

    monkeypatch.setattr(TushareProvider, "is_available", lambda self: False)
    provider = TushareProvider.__new__(TushareProvider)
    entry = registry.get_entry("stock_daily_basic", "tushare")
    assert asyncio.run(entry.func(provider, symbol="600519")) is None


def test_tushare_daily_basic_interval_query_sort_desc(monkeypatch):
    """区间查询透传参数 + fields=Schema 全字段 + trade_date 降序"""
    raw = pd.DataFrame({
        "ts_code": ["600519.SH"] * 2,
        "trade_date": ["20240102", "20240103"],
        "pe": [30.0, 31.0],
        "pe_ttm": [29.0, 30.0],
        "pb": [8.0, 8.1],
        "ps_ttm": [15.0, 15.2],
    })
    api = _StubTushareApi(daily_basic=raw)
    provider = _make_provider(monkeypatch, api)
    entry = registry.get_entry("stock_daily_basic", "tushare")

    df = asyncio.run(
        entry.func(provider, symbol="600519", start_date="20240101", end_date="20240131")
    )

    call = api.daily_basic_calls[-1]
    assert call["ts_code"] == "600519.SH"  # 6 位代码自动补后缀
    assert call["start_date"] == "20240101"
    assert call["end_date"] == "20240131"
    assert call["fields"] == ",".join(entry.schema.standard_field_names())
    assert df["trade_date"].tolist() == ["20240103", "20240102"]


def test_tushare_daily_basic_empty_returns_empty_frame(monkeypatch):
    """成功但无数据 -> 空 DataFrame（不降级契约，区别于失败 None）"""
    api = _StubTushareApi(daily_basic=None)
    provider = _make_provider(monkeypatch, api)
    entry = registry.get_entry("stock_daily_basic", "tushare")
    df = asyncio.run(
        entry.func(provider, symbol="600519", start_date="20240101", end_date="20240131")
    )
    assert isinstance(df, pd.DataFrame)
    assert df.empty


def test_tushare_daily_basic_api_error_returns_none(monkeypatch):
    """API 异常 -> None（门面按请求失败降级）"""
    api = _StubTushareApi(daily_basic=RuntimeError("限频"))
    provider = _make_provider(monkeypatch, api)
    entry = registry.get_entry("stock_daily_basic", "tushare")
    assert asyncio.run(
        entry.func(provider, symbol="600519", start_date="20240101", end_date="20240131")
    ) is None


def test_tushare_dividend_sort_desc_and_limit(monkeypatch):
    """end_date 降序 + limit 截断 + fields=Schema 全字段"""
    raw = pd.DataFrame({
        "ts_code": ["000001.SZ"] * 3,
        "end_date": ["20221231", "20231231", "20241231"],
        "ann_date": ["20230401", "20240315", "20250320"],
        "div_proc": ["实施", "实施", "预案"],
        "stk_div": [0.0, 0.0, 0.0],
        "stk_bo_rate": [0.0, 0.0, 0.0],
        "stk_co_rate": [0.0, 0.0, 0.0],
        "cash_div": [0.28, 0.29, 0.30],
        "cash_div_tax": [0.285, 0.296, 0.305],
        "record_date": ["20230601", "20240603", ""],
        "ex_date": ["20230602", "20240604", ""],
        "pay_date": ["20230602", "20240604", ""],
    })
    api = _StubTushareApi(dividend=raw)
    provider = _make_provider(monkeypatch, api)
    entry = registry.get_entry("stock_dividend", "tushare")

    df = asyncio.run(entry.func(provider, symbol="000001", limit=2))

    call = api.dividend_calls[-1]
    assert call["ts_code"] == "000001.SZ"
    assert call["fields"] == ",".join(entry.schema.standard_field_names())
    assert df["end_date"].tolist() == ["20241231", "20231231"]


def test_tushare_dividend_empty_and_error(monkeypatch):
    """空数据 -> 空 DataFrame 不降级；异常 -> None 降级"""
    entry = registry.get_entry("stock_dividend", "tushare")

    api = _StubTushareApi(dividend=None)
    provider = _make_provider(monkeypatch, api)
    df = asyncio.run(entry.func(provider, symbol="000001"))
    assert isinstance(df, pd.DataFrame)
    assert df.empty

    api2 = _StubTushareApi(dividend=RuntimeError("权限不足"))
    provider2 = _make_provider(monkeypatch, api2)
    assert asyncio.run(entry.func(provider2, symbol="000001")) is None


# ---------------------------------------------------------------- facade 真实能力全链路


def test_facade_daily_basic_end_to_end(monkeypatch):
    """全链路：标准列 + source/quality 标记 + 非标准列被门面裁剪"""
    raw = pd.DataFrame({
        "ts_code": ["600519.SH"],
        "trade_date": ["20240103"],
        "pe": [31.0],
        "pe_ttm": [30.0],
        "pb": [8.1],
        "ps_ttm": [15.2],
        "circ_mv": [9999.0],  # 超出 Schema 的列应被门面裁剪
    })
    provider = _make_provider(monkeypatch, _StubTushareApi(daily_basic=raw))
    _patch_tushare_factory(monkeypatch, provider)
    _fixed_order(monkeypatch, ["tushare"])

    df = asyncio.run(
        get_data_facade()
        .get_capability("stock_daily_basic")
        .query(symbol="600519", start_date="20240101", end_date="20240131")
    )

    assert len(df) == 1
    assert df.iloc[0]["source"] == "tushare"
    assert df.iloc[0]["quality"] == "ok"
    assert df.iloc[0]["trade_date"] == "20240103"
    assert df.iloc[0]["pe_ttm"] == 30.0
    assert "circ_mv" not in df.columns


def test_facade_all_sources_fail_returns_empty_with_columns(monkeypatch):
    """全源失败 -> 空 DataFrame（含标准列结构），不抛异常"""
    provider = _make_provider(monkeypatch, _StubTushareApi(daily_basic=RuntimeError("x")))
    _patch_tushare_factory(monkeypatch, provider)
    _fixed_order(monkeypatch, ["tushare"])

    df = asyncio.run(
        get_data_facade().get_capability("stock_daily_basic").query(symbol="600519")
    )

    assert df.empty
    assert {"ts_code", "trade_date", "source", "quality"} <= set(df.columns)


def test_query_capability_sync_dividend_records(monkeypatch):
    """同步包装路径（工具侧同款 to_dict('records') plain 转换）"""
    raw = pd.DataFrame({
        "ts_code": ["000001.SZ"],
        "end_date": ["20241231"],
        "ann_date": ["20250320"],
        "div_proc": ["预案"],
        "stk_div": [0.0],
        "stk_bo_rate": [0.0],
        "stk_co_rate": [0.0],
        "cash_div": [0.30],
        "cash_div_tax": [0.305],
        "record_date": [""],
        "ex_date": [""],
        "pay_date": [""],
    })
    provider = _make_provider(monkeypatch, _StubTushareApi(dividend=raw))
    _patch_tushare_factory(monkeypatch, provider)
    _fixed_order(monkeypatch, ["tushare"])

    df = query_capability_sync("stock_dividend", symbol="000001", limit=15)
    records = df.to_dict("records")

    assert records
    assert records[0]["div_proc"] == "预案"
    assert records[0]["cash_div_tax"] == 0.305
    assert records[0]["source"] == "tushare"
