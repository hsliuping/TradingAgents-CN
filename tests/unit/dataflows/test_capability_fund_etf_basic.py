"""数据能力注册机制 — ETF 基金能力测试（fund_etf_basic / fund_etf_hist）

fund_etf_basic（ETF 基金静态档案，GRAIN_REFERENCE 粒度）单源 tushare
（fund_basic，market="E" 按单基金 ts_code 过滤）；fund_etf_hist（ETF
日线行情，GRAIN_FUND_DAILY 粒度）双源：tushare fund_daily + akshare
fund_etf_hist_em。单位换算在适配器内完成（tushare amount 千元→元、
issue_amount 万份→份；akshare 原生元），门面 field_mapping 仅负责改名。

本文件覆盖：
1. 注册健全性：源集合 + grain + 参数签名机器校验 + field_mapping
   目标合法性
2. schema 字段基准（fund_etf_basic 18 字段，防漂移）
3. tushare 适配器契约：不可用/异常 -> None 降级；空表 -> 空
   DataFrame 不降级；ts_code 归一；trade_date 格式化；amount/
   fund_scale 单位换算；trade_date 降序
4. facade 真实能力全链路：field_mapping 改名 + 门面 source/quality 列 +
   tushare->akshare 降级链 + query_capability_sync 同步路径

设计文档：docs/05-design/v4.0/data-architecture-problems-and-optimization.md 5.4
"""

import asyncio
import inspect
import logging
from datetime import datetime

import pandas as pd

import tradingagents.dataflows.providers.china.akshare  # noqa: F401 —— import 即注册 akshare 源
import tradingagents.dataflows.providers.china.tushare  # noqa: F401 —— import 即注册 tushare 源
from tradingagents.dataflows.capability import query_capability_sync
from tradingagents.dataflows.capability.facade import get_data_facade
from tradingagents.dataflows.capability.registry import registry
from tradingagents.dataflows.capability.schema import GRAIN_FUND_DAILY, GRAIN_REFERENCE

EXPECTED_SOURCES = {
    "fund_etf_basic": {"tushare"},
    "fund_etf_hist": {"tushare", "akshare"},
}
EXPECTED_GRAIN = {
    "fund_etf_basic": GRAIN_REFERENCE,
    "fund_etf_hist": GRAIN_FUND_DAILY,
}

# 标准字段集合基准（对齐 schema 定义，防漂移）
BASIC_STANDARD_FIELDS = {
    "fund_code", "name", "fund_type", "track_index", "management", "custodian",
    "management_fee", "custodian_fee", "found_date", "list_date", "issue_date",
    "due_date", "invest_type", "status", "min_amount", "purchase_start_date",
    "redemption_start_date", "fund_scale",
}
HIST_STANDARD_FIELDS = {
    "trade_date", "open", "high", "low", "close", "volume", "amount",
    "amplitude", "pct_change", "change", "turnover_rate",
}

# tushare field_mapping 基准（防映射漂移）
BASIC_FIELD_MAPPING = {
    "benchmark": "track_index",
    "m_fee": "management_fee",
    "c_fee": "custodian_fee",
    "purc_startdate": "purchase_start_date",
    "redm_startdate": "redemption_start_date",
    "issue_amount": "fund_scale",
}
HIST_FIELD_MAPPING = {"vol": "volume", "pct_chg": "pct_change"}


def _fixed_order(monkeypatch, order):
    from tradingagents.dataflows.capability import facade as facade_mod

    monkeypatch.setattr(
        facade_mod.CapabilityHandle,
        "_resolve_source_order",
        lambda self, registered: [s for s in order if s in registered],
    )


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


def _make_tushare_stub(monkeypatch, api):
    """构造跳过 __init__ 的 TushareProvider 桩，api 为可录调用的替身"""
    from tradingagents.dataflows.providers.china.tushare import TushareProvider

    monkeypatch.setattr(TushareProvider, "is_available", lambda self: True)
    provider = TushareProvider.__new__(TushareProvider)
    provider.api = api
    provider.logger = logging.getLogger("test-stub-tushare-etf")
    return provider


class _TushareAPIStub:
    """录调用式 tushare pro api 替身（fund_daily / fund_basic）"""

    def __init__(self, daily_df=None, basic_df=None, error=None):
        self.daily_df = daily_df
        self.basic_df = basic_df
        self.error = error
        self.calls = []

    def fund_daily(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.daily_df

    def fund_basic(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.basic_df


def _hist_raw_df():
    """tushare fund_daily 原生形态（trade_date YYYYMMDD、vol/amount 千元、乱序）"""
    return pd.DataFrame(
        {
            "ts_code": ["510050.SH"] * 3,
            "trade_date": ["20241023", "20241025", "20241024"],
            "open": [2.51, 2.55, 2.53],
            "high": [2.56, 2.58, 2.54],
            "low": [2.50, 2.52, 2.49],
            "close": [2.55, 2.53, 2.52],
            "pre_close": [2.52, 2.55, 2.53],
            "change": [0.03, -0.02, -0.01],
            "pct_chg": [1.19, -0.78, -0.40],
            "vol": [123456.0, 234567.0, 345678.0],
            "amount": [31500.0, 59400.0, 87100.0],
        }
    )


def _basic_raw_df():
    """tushare fund_basic 原生形态（tushare 原生命名 + issue_amount 万份）"""
    return pd.DataFrame(
        [
            {
                "ts_code": "510050.SH",
                "market": "E",
                "name": "华夏上证50ETF",
                "fund_type": "股票型",
                "benchmark": "上证50指数",
                "m_fee": 0.5,
                "c_fee": 0.1,
                "found_date": "20041230",
                "list_date": "20050223",
                "issue_date": "20041129",
                "due_date": None,
                "invest_type": "指数型",
                "status": "L",
                "issue_amount": 97.31,
                "min_amount": 1000.0,
                "purc_startdate": "20050223",
                "redm_startdate": "20050223",
            }
        ]
    )


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


def test_schema_fields_baseline():
    """标准字段集合与 field_mapping 对齐基准（防漂移）"""
    basic_entry = registry.get_entry("fund_etf_basic", "tushare")
    assert set(basic_entry.schema.standard_field_names()) == BASIC_STANDARD_FIELDS
    assert basic_entry.field_mapping == BASIC_FIELD_MAPPING

    hist_ts_entry = registry.get_entry("fund_etf_hist", "tushare")
    assert set(hist_ts_entry.schema.standard_field_names()) == HIST_STANDARD_FIELDS
    assert hist_ts_entry.field_mapping == HIST_FIELD_MAPPING

    hist_ak_entry = registry.get_entry("fund_etf_hist", "akshare")
    assert set(hist_ak_entry.schema.standard_field_names()) == HIST_STANDARD_FIELDS


# ---------------------------------------------------------------- tushare 适配器契约


def test_tushare_hist_adapter_formats_and_sorts(monkeypatch):
    """fund_etf_hist tushare 适配器：日期格式化 + amount 千元→元 + 降序；
    vol/pct_chg 仍以原名承载（field_mapping 改名由门面完成）"""
    api = _TushareAPIStub(daily_df=_hist_raw_df())
    provider = _make_tushare_stub(monkeypatch, api)
    entry = registry.get_entry("fund_etf_hist", "tushare")

    df = asyncio.run(
        entry.func(provider, symbol="510050", start_date="20241020", end_date="20241025")
    )

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 3
    # 请求参数：6 位代码归一为 ts_code，窗口透传
    assert api.calls[-1] == {
        "ts_code": "510050.SH",
        "start_date": "20241020",
        "end_date": "20241025",
    }
    # trade_date 归一 YYYY-MM-DD 且降序（最新在前）
    assert df["trade_date"].tolist() == ["2024-10-25", "2024-10-24", "2024-10-23"]
    # amount 千元 -> 元
    assert df["amount"].tolist() == [59400000.0, 87100000.0, 31500000.0]
    # 原名承载，改名交给门面
    assert "vol" in df.columns and "pct_chg" in df.columns


def test_tushare_hist_adapter_default_window(monkeypatch):
    """fund_etf_hist tushare 适配器：start/end 缺省取近 30 天（YYYYMMDD）"""
    api = _TushareAPIStub(daily_df=_hist_raw_df())
    provider = _make_tushare_stub(monkeypatch, api)
    entry = registry.get_entry("fund_etf_hist", "tushare")

    df = asyncio.run(entry.func(provider, symbol="159915"))

    assert not df.empty
    call = api.calls[-1]
    assert call["ts_code"] == "159915.SZ"
    assert call["start_date"].isdigit() and len(call["start_date"]) == 8
    assert call["end_date"].isdigit() and len(call["end_date"]) == 8
    assert call["end_date"] == datetime.now().strftime("%Y%m%d")


def test_tushare_hist_adapter_empty_and_error(monkeypatch):
    """fund_etf_hist tushare 适配器：api 返回 None/空表 -> 空 DataFrame（不降级）；
    抛异常 -> None 降级"""
    entry = registry.get_entry("fund_etf_hist", "tushare")

    api = _TushareAPIStub(daily_df=None)
    provider = _make_tushare_stub(monkeypatch, api)
    df = asyncio.run(entry.func(provider, symbol="510050"))
    assert isinstance(df, pd.DataFrame) and df.empty

    api2 = _TushareAPIStub(error=RuntimeError("网络中断"))
    provider2 = _make_tushare_stub(monkeypatch, api2)
    assert asyncio.run(entry.func(provider2, symbol="510050")) is None


def test_tushare_basic_adapter_injects_code_and_scale(monkeypatch):
    """fund_etf_basic tushare 适配器：fund_code 注入 6 位代码 + issue_amount
    万份→份；tushare 原生命名承载（改名由门面完成）"""
    api = _TushareAPIStub(basic_df=_basic_raw_df())
    provider = _make_tushare_stub(monkeypatch, api)
    entry = registry.get_entry("fund_etf_basic", "tushare")

    df = asyncio.run(entry.func(provider, symbol="510050"))

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 1
    # 请求参数：market="E" + status="L" + ts_code 归一
    assert api.calls[-1] == {"market": "E", "status": "L", "ts_code": "510050.SH"}
    # fund_code 注入 6 位代码
    assert df["fund_code"].tolist() == ["510050"]
    # issue_amount 万份 -> 份
    assert df["issue_amount"].tolist() == [973100.0]
    # 原名承载
    assert df["benchmark"].tolist() == ["上证50指数"]
    assert df["m_fee"].tolist() == [0.5]


def test_tushare_basic_adapter_empty_and_error(monkeypatch):
    """fund_etf_basic tushare 适配器：api 返回 None/空表 -> 空 DataFrame（不降级）；
    抛异常 -> None 降级"""
    entry = registry.get_entry("fund_etf_basic", "tushare")

    api = _TushareAPIStub(basic_df=None)
    provider = _make_tushare_stub(monkeypatch, api)
    df = asyncio.run(entry.func(provider, symbol="510050"))
    assert isinstance(df, pd.DataFrame) and df.empty

    api2 = _TushareAPIStub(error=RuntimeError("接口权限不足"))
    provider2 = _make_tushare_stub(monkeypatch, api2)
    assert asyncio.run(entry.func(provider2, symbol="510050")) is None


def test_tushare_adapters_unavailable_returns_none(monkeypatch):
    """源不可用 -> None（触发门面降级语义），两个能力同契约"""
    from tradingagents.dataflows.providers.china.tushare import TushareProvider

    monkeypatch.setattr(TushareProvider, "is_available", lambda self: False)
    provider = TushareProvider.__new__(TushareProvider)
    provider.api = None

    assert asyncio.run(
        registry.get_entry("fund_etf_hist", "tushare").func(provider, symbol="510050")
    ) is None
    assert asyncio.run(
        registry.get_entry("fund_etf_basic", "tushare").func(provider, symbol="510050")
    ) is None


# ---------------------------------------------------------------- facade 真实能力全链路


def test_facade_etf_basic_end_to_end(monkeypatch):
    """全链路：field_mapping 改名 + fund_code 保留 + 非标准列裁剪 +
    门面 source/quality 列"""
    api = _TushareAPIStub(basic_df=_basic_raw_df())
    provider = _make_tushare_stub(monkeypatch, api)
    _patch_factories(monkeypatch, tushare_provider=provider)
    _fixed_order(monkeypatch, ["tushare", "akshare"])

    df = asyncio.run(
        get_data_facade()
        .get_capability("fund_etf_basic")
        .query(symbol="510050")
    )

    assert len(df) == 1
    row = df.iloc[0]
    # 改名落地
    assert row["track_index"] == "上证50指数"
    assert row["management_fee"] == 0.5
    assert row["custodian_fee"] == 0.1
    assert row["purchase_start_date"] == "20050223"
    assert row["redemption_start_date"] == "20050223"
    # 单位换算落地（万份 -> 份）
    assert row["fund_scale"] == 973100.0
    # 适配器注入的 fund_code 保留
    assert row["fund_code"] == "510050"
    # 门面标记列 + 非标准列（ts_code/market）裁剪
    assert row["source"] == "tushare"
    assert row["quality"] == "ok"
    assert "ts_code" not in df.columns and "market" not in df.columns
    assert BASIC_STANDARD_FIELDS | {"source", "quality"} == set(df.columns)


def test_facade_etf_hist_rename_and_source(monkeypatch):
    """全链路：vol/pct_chg 改名为 volume/pct_change + 门面 source 标记"""
    api = _TushareAPIStub(daily_df=_hist_raw_df())
    provider = _make_tushare_stub(monkeypatch, api)
    _patch_factories(monkeypatch, tushare_provider=provider)
    _fixed_order(monkeypatch, ["tushare", "akshare"])

    df = asyncio.run(
        get_data_facade()
        .get_capability("fund_etf_hist")
        .query(symbol="510050", start_date="20241020", end_date="20241025")
    )

    assert len(df) == 3
    assert df.iloc[0]["trade_date"] == "2024-10-25"
    assert df.iloc[0]["volume"] == 234567.0
    assert df.iloc[0]["pct_change"] == -0.78
    assert df.iloc[0]["source"] == "tushare"
    assert df.iloc[0]["quality"] == "ok"
    assert "vol" not in df.columns and "pct_chg" not in df.columns


def test_facade_etf_hist_fallback_tushare_to_akshare(monkeypatch):
    """降级链：tushare 异常（None）-> akshare 接管（中文列改名落地）"""
    api = _TushareAPIStub(error=RuntimeError("tushare 限频"))
    tushare_stub = _make_tushare_stub(monkeypatch, api)

    from tradingagents.dataflows.providers.china.akshare import AKShareProvider

    monkeypatch.setattr(AKShareProvider, "is_available", lambda self: True)
    akshare_stub = AKShareProvider.__new__(AKShareProvider)
    akshare_stub.logger = logging.getLogger("test-stub-akshare-etf")

    ak_hist = pd.DataFrame(
        {
            "日期": ["2024-10-25", "2024-10-24"],
            "开盘": [2.55, 2.53],
            "收盘": [2.53, 2.52],
            "最高": [2.58, 2.54],
            "最低": [2.52, 2.49],
            "成交量": [234567.0, 345678.0],
            "成交额": [59400000.0, 87100000.0],
            "振幅": [2.35, 1.98],
            "涨跌幅": [-0.78, -0.40],
            "涨跌额": [-0.02, -0.01],
            "换手率": [1.12, 1.65],
        }
    )

    import akshare as ak

    monkeypatch.setattr(ak, "fund_etf_hist_em", lambda **kwargs: ak_hist)
    _patch_factories(monkeypatch, tushare_provider=tushare_stub, akshare_provider=akshare_stub)
    _fixed_order(monkeypatch, ["tushare", "akshare"])

    df = asyncio.run(
        get_data_facade()
        .get_capability("fund_etf_hist")
        .query(symbol="510050")
    )

    assert len(df) == 2
    assert df.iloc[-1]["source"] == "akshare"
    assert df.iloc[0]["trade_date"] == "2024-10-25"
    assert df.iloc[0]["close"] == 2.53
    assert df.iloc[0]["pct_change"] == -0.78


def test_query_capability_sync_path(monkeypatch):
    """同步包装路径（工具侧 etf_fundamentals 同款调用）"""
    api = _TushareAPIStub(basic_df=_basic_raw_df())
    provider = _make_tushare_stub(monkeypatch, api)
    _patch_factories(monkeypatch, tushare_provider=provider)
    _fixed_order(monkeypatch, ["tushare", "akshare"])

    df = query_capability_sync("fund_etf_basic", symbol="510050")

    assert len(df) == 1
    assert df.iloc[-1]["source"] == "tushare"
    assert df.iloc[0]["fund_code"] == "510050"
    assert df.iloc[0]["fund_scale"] == 973100.0
