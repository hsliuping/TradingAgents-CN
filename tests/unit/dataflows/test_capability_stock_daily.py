"""数据能力注册机制 — 个股日线行情能力测试（technical_indicators 迁移）

stock_daily（个股按日 OHLC 行情，前复权，stock_daily 粒度）双源：
tushare 委托高层 get_historical_data（pro_bar qfq/ETF 分派），
akshare 委托高层 get_historical_data（qfq/超730天分批/新浪腾讯回退）。
标准名对齐两源高层方法共同输出命名（date/volume），非 tushare 裸接口
原生名（trade_date/vol）——委托对象不同，命名基准随之不同。本文件覆盖：
1. 注册健全性：源集合 + grain + 参数签名机器校验 + field_mapping 目标合法性
2. 双源适配器契约：不可用/异常 -> None 降级；空表 -> 空 DataFrame 不降级；
   tushare date 索引复位为列；akshare 单位归一（股->手、元->千元）
3. facade 真实能力全链路：标准化裁剪 + tushare->akshare 降级链 +
   query_capability_sync 同步路径

设计文档：docs/05-design/v4.0/data-architecture-problems-and-optimization.md 5.4
"""

import asyncio
import inspect
import logging

import pandas as pd

import tradingagents.dataflows.providers.china.akshare  # noqa: F401 —— import 即注册 akshare 源
import tradingagents.dataflows.providers.china.tushare  # noqa: F401 —— import 即注册 tushare 源
from tradingagents.dataflows.capability import query_capability_sync
from tradingagents.dataflows.capability.facade import get_data_facade
from tradingagents.dataflows.capability.registry import registry
from tradingagents.dataflows.capability.schema import GRAIN_STOCK_DAILY

EXPECTED_SOURCES = {"stock_daily": {"tushare", "akshare"}}
EXPECTED_GRAIN = {"stock_daily": GRAIN_STOCK_DAILY}

# 标准字段集合基准（对齐两源高层方法共同输出命名，防 schema 漂移）
STANDARD_FIELDS = {
    "ts_code", "date", "open", "high", "low", "close",
    "pre_close", "change", "pct_chg", "volume", "amount",
}

# akshare field_mapping 基准（防映射漂移）
AKSHARE_FIELD_MAPPING = {"change_percent": "pct_chg", "full_symbol": "ts_code"}


def _fixed_order(monkeypatch, order):
    from tradingagents.dataflows.capability import facade as facade_mod

    monkeypatch.setattr(
        facade_mod.CapabilityHandle,
        "_resolve_source_order",
        lambda self, registered: [s for s in order if s in registered],
    )


def _make_tushare_stub(monkeypatch, historical=None, error=None):
    """构造跳过 __init__ 的 TushareProvider 桩，get_historical_data 返回预设载荷"""
    from tradingagents.dataflows.providers.china.tushare import TushareProvider

    monkeypatch.setattr(TushareProvider, "is_available", lambda self: True)

    async def _stub(self, symbol, start_date, end_date=None, period="daily"):
        assert (symbol, start_date) == ("600519", "2024-01-01")
        if error is not None:
            raise error
        return historical

    monkeypatch.setattr(TushareProvider, "get_historical_data", _stub)
    provider = TushareProvider.__new__(TushareProvider)
    provider.api = None
    provider.logger = logging.getLogger("test-stub-tushare")
    return provider


def _make_akshare_stub(monkeypatch, historical=None, error=None):
    """构造跳过 __init__ 的 AKShareProvider 桩，记录调用参数并返回预设载荷"""
    from tradingagents.dataflows.providers.china.akshare import AKShareProvider

    monkeypatch.setattr(AKShareProvider, "is_available", lambda self: True)
    calls = []

    async def _stub(self, code, start_date, end_date, period="daily"):
        calls.append({"code": code, "start_date": start_date, "end_date": end_date})
        if error is not None:
            raise error
        return historical

    monkeypatch.setattr(AKShareProvider, "get_historical_data", _stub)
    provider = AKShareProvider.__new__(AKShareProvider)
    provider.logger = logging.getLogger("test-stub-akshare")
    return provider, calls


def _patch_factories(monkeypatch, tushare_provider=None, akshare_provider=None):
    from tradingagents.dataflows.capability import facade as facade_mod

    if tushare_provider is not None:
        monkeypatch.setitem(
            facade_mod._PROVIDER_FACTORIES, "tushare", lambda: tushare_provider
        )
    if akshare_provider is not None:
        monkeypatch.setitem(
            facade_mod._PROVIDER_FACTORIES, "akshare", lambda: akshare_provider
        )


def _tushare_payload(index_as_index=True):
    """tushare 高层 get_historical_data 输出形态（date 为索引，tushare 口径单位）"""
    data = {
        "ts_code": ["600519.SH"] * 2,
        "open": [1700.0, 1710.0],
        "high": [1720.0, 1730.0],
        "low": [1690.0, 1700.0],
        "close": [1715.0, 1725.0],
        "pre_close": [1700.0, 1715.0],
        "change": [15.0, 10.0],
        "pct_chg": [0.88, 0.58],
        "volume": [30000.0, 32000.0],      # 手
        "amount": [515000.0, 552000.0],    # 千元
    }
    idx = pd.DatetimeIndex(["2024-01-02", "2024-01-03"], name="date")
    if index_as_index:
        return pd.DataFrame(data, index=idx)
    return pd.DataFrame({**data, "date": idx})


def _akshare_payload():
    """akshare 高层 get_historical_data 输出形态（date 为列，akshare 口径单位）"""
    return pd.DataFrame({
        "date": pd.to_datetime(["2024-01-02", "2024-01-03"]),
        "open": [1700.0, 1710.0],
        "close": [1715.0, 1725.0],
        "high": [1720.0, 1730.0],
        "low": [1690.0, 1700.0],
        "volume": [3000000.0, 3200000.0],    # 股
        "amount": [515000000.0, 552000000.0],  # 元
        "amplitude": [1.76, 1.75],
        "change_percent": [0.88, 0.58],
        "change": [15.0, 10.0],
        "turnover": [0.5, 0.53],
        "code": ["600519"] * 2,
        "full_symbol": ["600519.SH"] * 2,
    })


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


def test_schema_standard_fields_baseline():
    """标准字段集合与 akshare field_mapping 对齐基准（防漂移）"""
    entry = registry.get_entry("stock_daily", "tushare")
    assert set(entry.schema.standard_field_names()) == STANDARD_FIELDS
    ak_entry = registry.get_entry("stock_daily", "akshare")
    assert ak_entry.field_mapping == AKSHARE_FIELD_MAPPING


# ---------------------------------------------------------------- 适配器契约


def test_tushare_adapter_resets_date_index(monkeypatch):
    """tushare 高层输出 date 为索引 -> 适配器复位为普通列 + 透传参数"""
    provider = _make_tushare_stub(monkeypatch, historical=_tushare_payload())
    entry = registry.get_entry("stock_daily", "tushare")

    df = asyncio.run(
        entry.func(provider, symbol="600519", start_date="2024-01-01", end_date="2024-01-31")
    )

    assert "date" in df.columns
    assert df["date"].tolist() == list(pd.to_datetime(["2024-01-02", "2024-01-03"]))
    # tushare 口径单位原样透传（手/千元），实现内不做换算
    assert df["volume"].tolist() == [30000.0, 32000.0]
    assert df["amount"].tolist() == [515000.0, 552000.0]


def test_tushare_adapter_none_and_error(monkeypatch):
    """高层方法返回 None -> None 降级；抛异常 -> None 降级"""
    entry = registry.get_entry("stock_daily", "tushare")

    provider = _make_tushare_stub(monkeypatch, historical=None)
    assert asyncio.run(
        entry.func(provider, symbol="600519", start_date="2024-01-01")
    ) is None

    provider2 = _make_tushare_stub(monkeypatch, error=RuntimeError("积分不足"))
    assert asyncio.run(
        entry.func(provider2, symbol="600519", start_date="2024-01-01")
    ) is None


def test_tushare_adapter_unavailable_returns_none(monkeypatch):
    """源不可用 -> None（触发门面降级语义）"""
    from tradingagents.dataflows.providers.china.tushare import TushareProvider

    monkeypatch.setattr(TushareProvider, "is_available", lambda self: False)
    provider = TushareProvider.__new__(TushareProvider)
    entry = registry.get_entry("stock_daily", "tushare")
    assert asyncio.run(
        entry.func(provider, symbol="600519", start_date="2024-01-01")
    ) is None


def test_akshare_adapter_unit_normalization(monkeypatch):
    """akshare 单位归一（volume 股->手 /100，amount 元->千元 /1000）+ end_date 兜底"""
    provider, calls = _make_akshare_stub(monkeypatch, historical=_akshare_payload())
    entry = registry.get_entry("stock_daily", "akshare")

    df = asyncio.run(
        entry.func(provider, symbol="600519", start_date="2024-01-01", end_date=None)
    )

    assert calls[-1]["end_date"]  # end_date 缺省时实现内兜底为当天
    assert df["volume"].tolist() == [30000.0, 32000.0]       # 手
    assert df["amount"].tolist() == [515000.0, 552000.0]     # 千元
    # 原始列名保持（change_percent/full_symbol 由门面 field_mapping 统一改名）
    assert "change_percent" in df.columns
    assert "full_symbol" in df.columns


def test_akshare_adapter_none_and_error(monkeypatch):
    """高层方法返回 None -> None 降级；抛异常 -> None 降级"""
    entry = registry.get_entry("stock_daily", "akshare")

    provider, _ = _make_akshare_stub(monkeypatch, historical=None)
    assert asyncio.run(
        entry.func(provider, symbol="600519", start_date="2024-01-01")
    ) is None

    provider2, _ = _make_akshare_stub(monkeypatch, error=RuntimeError("网络中断"))
    assert asyncio.run(
        entry.func(provider2, symbol="600519", start_date="2024-01-01")
    ) is None


# ---------------------------------------------------------------- facade 真实能力全链路


def test_facade_end_to_end_tushare(monkeypatch):
    """tushare 全链路：date 索引复位 + 标准列 + source/quality + 超集列被裁剪"""
    raw = _tushare_payload()
    raw["extra_col"] = 999.0  # 超出 Schema 的列应被门面裁剪
    provider = _make_tushare_stub(monkeypatch, historical=raw)
    _patch_factories(monkeypatch, tushare_provider=provider)
    _fixed_order(monkeypatch, ["tushare", "akshare"])

    df = asyncio.run(
        get_data_facade()
        .get_capability("stock_daily")
        .query(symbol="600519", start_date="2024-01-01", end_date="2024-01-31")
    )

    assert len(df) == 2
    assert df.iloc[-1]["source"] == "tushare"
    assert df.iloc[-1]["quality"] == "ok"
    assert df.iloc[-1]["close"] == 1725.0
    assert df.iloc[-1]["date"] == pd.Timestamp("2024-01-03")
    assert "extra_col" not in df.columns
    assert {"date", "open", "high", "low", "close", "volume", "amount",
            "source", "quality"} <= set(df.columns)


def test_facade_fallback_tushare_to_akshare(monkeypatch):
    """降级链：tushare 失败 -> akshare 接管（field_mapping 改名 + 单位归一生效）"""
    tushare_stub = _make_tushare_stub(monkeypatch, historical=None)
    akshare_stub, _ = _make_akshare_stub(monkeypatch, historical=_akshare_payload())
    _patch_factories(
        monkeypatch, tushare_provider=tushare_stub, akshare_provider=akshare_stub
    )
    _fixed_order(monkeypatch, ["tushare", "akshare"])

    df = asyncio.run(
        get_data_facade()
        .get_capability("stock_daily")
        .query(symbol="600519", start_date="2024-01-01")
    )

    assert df.iloc[-1]["source"] == "akshare"
    assert df.iloc[-1]["pct_chg"] == 0.58       # change_percent 经映射改名
    assert df.iloc[-1]["ts_code"] == "600519.SH"  # full_symbol 经映射改名
    assert df.iloc[-1]["volume"] == 32000.0     # 股 -> 手
    assert df.iloc[-1]["amount"] == 552000.0    # 元 -> 千元
    assert "change_percent" not in df.columns   # 非标准列被裁剪
    assert "amplitude" not in df.columns
    assert "turnover" not in df.columns


def test_facade_all_sources_fail_returns_empty_with_columns(monkeypatch):
    """全源失败 -> 空 DataFrame（含标准列结构），不抛异常"""
    tushare_stub = _make_tushare_stub(monkeypatch, historical=None)
    akshare_stub, _ = _make_akshare_stub(monkeypatch, historical=None)
    _patch_factories(
        monkeypatch, tushare_provider=tushare_stub, akshare_provider=akshare_stub
    )
    _fixed_order(monkeypatch, ["tushare", "akshare"])

    df = asyncio.run(
        get_data_facade()
        .get_capability("stock_daily")
        .query(symbol="600519", start_date="2024-01-01")
    )

    assert df.empty
    assert {"date", "open", "close", "volume", "source", "quality"} <= set(df.columns)


def test_query_capability_sync_path(monkeypatch):
    """同步包装路径（工具侧 technical_indicators 同款调用）"""
    provider = _make_tushare_stub(monkeypatch, historical=_tushare_payload())
    _patch_factories(monkeypatch, tushare_provider=provider)
    _fixed_order(monkeypatch, ["tushare", "akshare"])

    df = query_capability_sync(
        "stock_daily", symbol="600519", start_date="2024-01-01", end_date="2024-01-31"
    )

    assert len(df) == 2
    assert df.iloc[-1]["date"] == pd.Timestamp("2024-01-03")
    assert df.iloc[-1]["volume"] == 32000.0
    assert df.iloc[-1]["source"] == "tushare"
