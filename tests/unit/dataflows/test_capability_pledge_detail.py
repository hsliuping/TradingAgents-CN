"""数据能力注册机制 — pledge_detail 能力测试

包含（接入规约：没有字段对齐测试不许注册）：
1. 双源字段对齐（mock，无网络）：tushare 拼音列 / akshare 中文列经各自
   field_mapping 映射后标准字段集合与取值一致
2. facade 降级语义（mock）：tushare 失败 -> akshare 接管；成功空数据不降级；
   空结果经 SOURCE_STATUS_ATTR 区分"成功无数据"与"全部失败"
3. akshare 适配器契约：ts_code 统一参数转换、失败返回 None、成功空数据返回空 DataFrame
4. skill 层 data_source_status 三态重建（success_with_data / success_empty / error）
5. 双源字段对齐（live）：tushare 无 token 或接口不可用时跳过

设计文档：docs/05-design/v4.0/data-architecture-problems-and-optimization.md 5.4
"""

import itertools
import logging

import pandas as pd
import pytest

import tradingagents.dataflows.providers.china.akshare  # noqa: F401 —— import 即注册
import tradingagents.dataflows.providers.china.tushare  # noqa: F401
from tradingagents.dataflows.capability import facade as facade_mod
from tradingagents.dataflows.capability.facade import get_data_facade
from tradingagents.dataflows.capability.registry import register_capability, registry
from tradingagents.dataflows.capability.schema import (
    GRAIN_STOCK_EVENT,
    CapabilityField,
    CapabilityParam,
    CapabilitySchema,
)
from tradingagents.dataflows.capability.schemas import register_schema
from tradingagents.dataflows.capability.schemas.pledge_detail import SOURCE_STATUS_ATTR

_cap_counter = itertools.count()


def _make_test_capability():
    """每个测试独立能力 ID，避免污染全局 'pledge_detail' 注册"""
    cap_id = f"ut_pledge_{next(_cap_counter)}"
    schema = CapabilitySchema(
        capability_id=cap_id,
        grain=GRAIN_STOCK_EVENT,
        fields=[
            CapabilityField("ts_code", "str", True, "股票代码"),
            CapabilityField("ann_date", "str", True, "公告日期 YYYYMMDD"),
            CapabilityField("holder_name", "str", False, "股东名称"),
            CapabilityField("pledge_amount", "float", False, "质押数量（万股）"),
            CapabilityField("pledge_total_ratio", "float", False, "本次质押占总股本比例（%）"),
            CapabilityField("is_released", "str", False, "是否已解押（0否 1是）"),
        ],
        params=[
            CapabilityParam("ts_code", "str", False, "股票代码（TS 格式）"),
        ],
    )
    register_schema(schema)
    return cap_id


class _FakeProvider:
    """占位 provider 实例（fake fetch 不依赖实例状态）"""
    pass


def _register_fake(cap_id, source, fetch, raw_mapping=None):
    async def fake_fetch(self, **params):
        return fetch(params)

    register_capability(
        cap_id, source,
        dict(raw_mapping or {
            "ts_code": "ts_code",
            "ann_date": "ann_date",
            "holder_name": "holder_name",
            "pledge_amount": "pledge_amount",
            "p_total_ratio": "pledge_total_ratio",
            "is_release": "is_released",
        }),
        provider_factory=lambda: _FakeProvider(),
    )(fake_fetch)
    return fake_fetch


def _fixed_order(monkeypatch, order):
    monkeypatch.setattr(
        facade_mod.CapabilityHandle,
        "_resolve_source_order",
        lambda self, registered: [s for s in order if s in registered],
    )


TS_RAW_ROW = {
    "ts_code": "600519.SH",
    "ann_date": "20260105",
    "holder_name": "某股东",
    "pledge_amount": 120.0,
    "start_date": "20250101",
    "end_date": "20280101",
    "is_release": "0",
    "release_date": None,
    "pledgor": "某银行",
    "holding_amount": 1000.0,
    "pledged_amount": 300.0,
    "p_total_ratio": 0.37,
    "h_total_ratio": 5.2,
    "is_buyback": "0",
}

AK_RAW_ROW = {
    # ts_code 为标准列直通（适配器 df["ts_code"] = ts_code，不经 field_mapping 改名）
    "ts_code": "600519.SH",
    "股票代码": "sh600519",
    "公告日期": "2026-01-05",
    "股东名称": "某股东",
    "质押股份数量": 120.0,
    "质押开始日期": "2025-01-01",
    "质押结束日期": "2028-01-01",
    "是否解押": "否",
    "解押日期": None,
    "质押方": "某银行",
    "持股总数": 1000.0,
    "质押总数": 300.0,
    "占总股本比例": 0.37,
    "持股占总股本比例": 5.2,
    "是否回购": "否",
}


# ---------------------------------------------------------------- 双源字段对齐（mock）


def test_dual_source_field_alignment_pledge_detail():
    """tushare 拼音列 / akshare 中文列映射后标准字段一致（列集合 + 关键取值）"""
    ts_entry = registry.get_entry("pledge_detail", "tushare")
    ak_entry = registry.get_entry("pledge_detail", "akshare")
    assert ts_entry.schema is ak_entry.schema

    handle = get_data_facade().get_capability("pledge_detail")
    out_columns = ts_entry.schema.standard_field_names() + ["source", "quality"]

    ts_std = handle._standardize(pd.DataFrame([TS_RAW_ROW]), ts_entry, out_columns)
    ak_std = handle._standardize(pd.DataFrame([AK_RAW_ROW]), ak_entry, out_columns)

    # 字段名一致性：映射后列集合与 Schema 标准列一致
    assert ts_std.columns.tolist() == out_columns
    assert ak_std.columns.tolist() == out_columns

    # 取值一致性：不同源同义字段映射到同一标准字段
    # 日期字段双源格式不同（tushare YYYYMMDD / akshare YYYY-MM-DD），归一为纯数字比较；
    # 缺失值（pd.NA/NaN）归一为 None 后比较，避免 pd.NA 真值歧义
    def _norm(value, field):
        try:
            if pd.isna(value):
                return None
        except (TypeError, ValueError):
            pass
        if field == "ann_date":
            return "".join(ch for ch in str(value) if ch.isdigit())
        return value

    for field in ("ts_code", "ann_date", "holder_name", "pledge_amount",
                  "pledge_total_ratio", "holding_amount", "holding_total_ratio"):
        ts_val = _norm(ts_std.iloc[0][field], field)
        ak_val = _norm(ak_std.iloc[0][field], field)
        assert ts_val == ak_val, f"标准字段 {field} 双源取值不一致: {ts_val!r} != {ak_val!r}"

    assert ak_std.iloc[0]["ts_code"] == "600519.SH"  # ts_code 标准列直通
    assert "is_released" in ak_std.columns  # 是否解押 -> is_released 改名生效


def test_akshare_registration_mapping_targets_in_schema():
    """akshare 映射目标全部是 Schema 标准字段，且参数签名接受 Schema 全部参数"""
    import inspect

    entry = registry.get_entry("pledge_detail", "akshare")
    standard = set(entry.schema.standard_field_names())
    for raw_name, std_name in entry.field_mapping.items():
        assert std_name in standard, (
            f"映射目标 '{std_name}' 不在标准字段集合 {sorted(standard)}"
        )
    func_params = set(inspect.signature(entry.func).parameters)
    for param in entry.schema.params:
        assert param.name in func_params, f"Schema 参数 {param.name} 不在适配方法签名中"
    assert entry.schema.grain == GRAIN_STOCK_EVENT


# ---------------------------------------------------------------- facade 降级语义


def test_tushare_failure_degrades_to_akshare(monkeypatch):
    """tushare 请求失败 -> akshare 接管（双源降级语义）"""
    cap_id = _make_test_capability()
    _fixed_order(monkeypatch, ["tushare", "akshare"])

    def fail(params):
        raise RuntimeError("模拟 tushare 请求失败")

    def ok(params):
        return pd.DataFrame([{
            "ts_code": "600519.SH", "ann_date": "20260105",
            "股东名称": "某股东", "质押股份数量": 120.0, "占总股本比例": 0.37,
        }])

    _register_fake(cap_id, "tushare", fail)
    _register_fake(cap_id, "akshare", ok, raw_mapping={
        "ts_code": "ts_code",
        "ann_date": "ann_date",
        "股东名称": "holder_name",
        "质押股份数量": "pledge_amount",
        "占总股本比例": "pledge_total_ratio",
    })

    import asyncio
    df = asyncio.run(get_data_facade().get_capability(cap_id).query(ts_code="600519.SH"))
    assert len(df) == 1
    assert df.iloc[0]["source"] == "akshare"
    # 双源映射后读同一套标准字段
    assert df.iloc[0]["holder_name"] == "某股东"
    assert df.iloc[0]["pledge_amount"] == 120.0
    assert df.iloc[0]["pledge_total_ratio"] == 0.37


def test_empty_success_does_not_degrade(monkeypatch):
    """成功但空数据 -> 不降级（P5 教训：空数据不漂移为另一源数据）"""
    cap_id = _make_test_capability()
    _fixed_order(monkeypatch, ["tushare", "akshare"])

    called = {"b": False}

    def empty(params):
        return pd.DataFrame()

    def ok(params):
        called["b"] = True
        return pd.DataFrame([{"ts_code": "600519.SH", "ann_date": "20260105"}])

    _register_fake(cap_id, "tushare", empty)
    _register_fake(cap_id, "akshare", ok)

    import asyncio
    df = asyncio.run(get_data_facade().get_capability(cap_id).query(ts_code="600519.SH"))
    assert df.empty
    assert called["b"] is False, "空数据不应触发降级"


def test_success_empty_marker_survives_facade(monkeypatch):
    """适配器的空结果状态标记穿过 facade 标准化，供调用方区分 success_empty / error"""
    cap_id = _make_test_capability()
    _fixed_order(monkeypatch, ["tushare", "akshare"])

    def empty_marked(params):
        df = pd.DataFrame()
        df.attrs[SOURCE_STATUS_ATTR] = {"akshare": "success_empty"}
        return df

    _register_fake(cap_id, "tushare", lambda params: None)
    _register_fake(cap_id, "akshare", empty_marked)

    import asyncio
    df = asyncio.run(get_data_facade().get_capability(cap_id).query(ts_code="600519.SH"))
    assert df.empty
    assert df.attrs.get(SOURCE_STATUS_ATTR) == {"akshare": "success_empty"}

    # 全部失败：降级穷尽后的结构化空表不带标记
    cap_id2 = _make_test_capability()
    _fixed_order(monkeypatch, ["tushare"])

    def fail(params):
        raise RuntimeError("挂了")

    _register_fake(cap_id2, "tushare", fail)
    df2 = asyncio.run(get_data_facade().get_capability(cap_id2).query(ts_code="600519.SH"))
    assert df2.empty
    assert not df2.attrs.get(SOURCE_STATUS_ATTR)


# ---------------------------------------------------------------- akshare 适配器契约


def _fake_akshare_instance(monkeypatch, pledge_impl):
    """绕过 AKShareProvider.__init__（避免网络初始化），构造可控实例"""
    import tradingagents.dataflows.providers.china.akshare as ak_mod

    inst = object.__new__(ak_mod.AKShareProvider)
    inst.logger = logging.getLogger("ut_akshare")
    monkeypatch.setattr(inst, "is_available", lambda: True)
    monkeypatch.setattr(inst, "get_pledge_detail", pledge_impl)
    return inst


def _ak_entry_func():
    return registry.get_entry("pledge_detail", "akshare").func


@pytest.mark.asyncio
async def test_akshare_adapter_param_conversion(monkeypatch):
    """统一参数 ts_code -> 6 位 symbol 调原实现，返回补 ts_code 标准列 + 公告日期本地过滤"""
    seen = {}

    async def stub(symbol=None, date=None):
        seen["symbol"] = symbol
        return pd.DataFrame([AK_RAW_ROW, dict(AK_RAW_ROW, 公告日期="2026-02-01")])

    inst = _fake_akshare_instance(monkeypatch, stub)
    df = await _ak_entry_func()(inst, ts_code="600519.SH", ann_date="2026-01-05")

    assert seen["symbol"] == "600519"
    assert len(df) == 1
    assert df.iloc[0]["ts_code"] == "600519.SH"


@pytest.mark.asyncio
async def test_akshare_adapter_empty_marks_success_empty(monkeypatch):
    """成功但无数据 -> 空 DataFrame + 状态标记（facade 不降级）"""

    async def stub(symbol=None, date=None):
        return pd.DataFrame()

    inst = _fake_akshare_instance(monkeypatch, stub)
    df = await _ak_entry_func()(inst, ts_code="600519.SH")
    assert df is not None and df.empty
    assert df.attrs.get(SOURCE_STATUS_ATTR) == {"akshare": "success_empty"}


@pytest.mark.asyncio
async def test_akshare_adapter_failure_returns_none(monkeypatch):
    """请求失败/不可用 -> None（facade 降级到下一源）"""

    async def stub(symbol=None, date=None):
        return None

    inst = _fake_akshare_instance(monkeypatch, stub)
    assert await _ak_entry_func()(inst, ts_code="600519.SH") is None


# ---------------------------------------------------------------- skill 层状态重建


class _FakeTushareAPI:
    def __init__(self, result):
        self._result = result

    def pledge_detail(self, **params):
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


class _FakeTushareProvider:
    def __init__(self, result):
        self.api = _FakeTushareAPI(result)
        self.logger = logging.getLogger("ut_tushare")

    def is_available(self):
        return True


class _FakeAKShareProvider:
    def __init__(self, result):
        self._result = result
        self.logger = logging.getLogger("ut_akshare")

    def is_available(self):
        return True

    async def get_pledge_detail(self, symbol=None, date=None):
        return self._result


def _install_fake_providers(monkeypatch, ts_result, ak_result):
    monkeypatch.setattr(
        facade_mod, "_PROVIDER_FACTORIES",
        {
            "tushare": lambda: _FakeTushareProvider(ts_result),
            "akshare": lambda: _FakeAKShareProvider(ak_result),
        },
    )


def _query_pledge_rows(monkeypatch, ts_result, ak_result, **kwargs):
    import asyncio

    import core.skill_runtime.standard_financial_apis as sfa

    _install_fake_providers(monkeypatch, ts_result, ak_result)
    _fixed_order(monkeypatch, ["tushare", "akshare"])
    return sfa._query_pledge_detail_rows(**kwargs)


def test_skill_status_success_with_data(monkeypatch):
    """tushare 有数据 -> 标准字段行 + success_with_data"""
    rows, data_source, status, errors = _query_pledge_rows(
        monkeypatch, pd.DataFrame([TS_RAW_ROW]), None, ts_code="600519.SH")
    assert data_source == "tushare"
    assert status == {"tushare": "success_with_data"}
    assert rows[0]["pledge_total_ratio"] == 0.37
    assert rows[0]["is_released"] == "0"


def test_skill_status_tushare_fail_akshare_takes_over(monkeypatch):
    """tushare 失败（legacy 空/失败均 None）-> akshare 接管，行读标准字段"""
    rows, data_source, status, errors = _query_pledge_rows(
        monkeypatch, None, pd.DataFrame([AK_RAW_ROW]), ts_code="600519.SH")
    assert data_source == "akshare"
    assert status == {"akshare": "success_with_data"}
    assert rows[0]["holder_name"] == "某股东"
    assert rows[0]["pledge_total_ratio"] == 0.37


def test_skill_status_success_empty(monkeypatch):
    """akshare 成功但空（带标记）-> success_empty（业务口径"无质押"）"""
    rows, data_source, status, errors = _query_pledge_rows(
        monkeypatch, None, pd.DataFrame(), ts_code="600519.SH")
    assert rows == [] and data_source is None
    assert status == {"akshare": "success_empty"}


def test_skill_status_all_failed_is_error(monkeypatch):
    """全部源请求失败（无空标记）-> error"""
    rows, data_source, status, errors = _query_pledge_rows(
        monkeypatch, None, None, ts_code="600519.SH")
    assert rows == [] and data_source is None
    assert set(status) == {"tushare", "akshare"}
    assert all(v == "error" for v in status.values())


def test_skill_pinned_source_skips_other_sources(monkeypatch):
    """source 参数钉住单一源：不跨源降级（保持既有对外语义）"""
    rows, data_source, status, errors = _query_pledge_rows(
        monkeypatch, pd.DataFrame([TS_RAW_ROW]), pd.DataFrame([AK_RAW_ROW]),
        preferred_source="akshare", ts_code="600519.SH")
    assert data_source == "akshare"
    assert rows[0]["holder_name"] == "某股东"

    rows, data_source, status, errors = _query_pledge_rows(
        monkeypatch, pd.DataFrame([TS_RAW_ROW]), None,
        preferred_source="tushare", ts_code="600519.SH")
    assert data_source == "tushare"


# ---------------------------------------------------------------- 双源字段对齐（live）


@pytest.mark.asyncio
async def test_dual_source_alignment_pledge_detail_live():
    """双源同一股票映射后字段名一致（联网 + tushare token）"""
    import tradingagents.dataflows.providers.china.akshare as ak_mod
    import tradingagents.dataflows.providers.china.tushare as ts_mod

    ts_provider = ts_mod.get_tushare_provider()
    if not ts_provider.is_available():
        pytest.skip("tushare 不可用（无 token），跳过双源对账")
    ak_provider = ak_mod.get_akshare_provider()
    if not ak_provider.is_available():
        pytest.skip("akshare 不可用，跳过双源对账")

    ts_entry = registry.get_entry("pledge_detail", "tushare")
    ak_entry = registry.get_entry("pledge_detail", "akshare")
    handle = get_data_facade().get_capability("pledge_detail")
    out_columns = ts_entry.schema.standard_field_names() + ["source", "quality"]

    ts_raw = await ts_entry.func(ts_provider, ts_code="002557.SZ")
    ak_raw = await ak_entry.func(ak_provider, ts_code="002557.SZ")
    if ts_raw is None or ak_raw is None:
        pytest.skip("某一数据源无数据/接口不可用，跳过双源对账")

    ts_std = handle._standardize(ts_raw, ts_entry, out_columns)
    ak_std = handle._standardize(ak_raw, ak_entry, out_columns)

    # 字段名一致性：映射后列集合与 Schema 标准列一致
    assert set(ts_entry.schema.standard_field_names()) <= set(ts_std.columns)
    assert set(ak_entry.schema.standard_field_names()) <= set(ak_std.columns)
    assert ts_std.columns.tolist() == ak_std.columns.tolist()
