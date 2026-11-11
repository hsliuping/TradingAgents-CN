"""数据能力注册机制 — margin 能力测试

包含（接入规约：没有字段对齐测试不许注册）：
1. 降级语义单测（mock，无网络）：失败降级 / 空数据不降级 / 缺字段 quality 标记
2. 注册校验单测：grain 不一致、映射目标不在 Schema 均拒绝
3. 双源字段对齐测试（live）：tushare/akshare 同一交易日映射后字段一致、数值容差内
   — tushare 不可用（无 token）时跳过

设计文档：docs/05-design/v4.0/data-architecture-problems-and-optimization.md 5.4⑤
"""

import itertools

import pandas as pd
import pytest

from tradingagents.dataflows.capability import facade as facade_mod
from tradingagents.dataflows.capability.registry import register_capability
from tradingagents.dataflows.capability.schemas import register_schema
from tradingagents.dataflows.capability.facade import get_data_facade
from tradingagents.dataflows.capability.schema import (
    GRAIN_MARKET_DAILY,
    CapabilityField,
    CapabilityParam,
    CapabilitySchema,
)

_cap_counter = itertools.count()


def _make_test_capability():
    """每个测试独立能力 ID，避免污染全局 'margin' 注册"""
    cap_id = f"ut_margin_{next(_cap_counter)}"
    schema = CapabilitySchema(
        capability_id=cap_id,
        grain=GRAIN_MARKET_DAILY,
        fields=[
            CapabilityField("trade_date", "str", True, "交易日期 YYYYMMDD"),
            CapabilityField("margin_balance", "float", True, "融资余额（元）"),
            CapabilityField("short_balance", "float", False, "融券余额（元）"),
        ],
        params=[
            CapabilityParam("trade_date", "str", False, "交易日期 YYYYMMDD"),
            CapabilityParam("exchange_id", "str", False, "交易所代码"),
        ],
    )
    register_schema(schema)
    return cap_id


RAW_MAPPING = {
    "trade_date": "trade_date",
    "rzye": "margin_balance",
    "rqye": "short_balance",
}


class _FakeProvider:
    """占位 provider 实例（fake fetch 不依赖实例状态）"""
    pass


def _register_fake(cap_id, source, fetch, raw_mapping=RAW_MAPPING):
    async def fake_fetch(self, **params):
        return fetch(params)

    register_capability(
        cap_id, source, dict(raw_mapping),
        provider_factory=lambda: _FakeProvider(),
    )(fake_fetch)
    return fake_fetch


def _fixed_order(monkeypatch, order):
    monkeypatch.setattr(
        facade_mod.CapabilityHandle,
        "_resolve_source_order",
        lambda self, registered: [s for s in order if s in registered],
    )


# ---------------------------------------------------------------- 降级语义


def test_failure_degrades_to_next_source(monkeypatch):
    """异常/None = 请求失败 -> 试下一源"""
    cap_id = _make_test_capability()
    _fixed_order(monkeypatch, ["src_a", "src_b"])

    def fail(params):
        raise RuntimeError("模拟请求失败")

    def ok(params):
        return pd.DataFrame([{"trade_date": "20261023", "rzye": 100.0, "rqye": 1.0}])

    _register_fake(cap_id, "src_a", fail)
    _register_fake(cap_id, "src_b", ok)

    import asyncio
    df = asyncio.run(get_data_facade().get_capability(cap_id).query())
    assert len(df) == 1
    assert df.iloc[0]["source"] == "src_b"
    assert df.iloc[0]["margin_balance"] == 100.0


def test_empty_success_does_not_degrade(monkeypatch):
    """成功但数据为空 -> 返回空结果，不降级（P5 教训：空数据不漂移为另一源数据）"""
    cap_id = _make_test_capability()
    _fixed_order(monkeypatch, ["src_a", "src_b"])

    called = {"b": False}

    def empty(params):
        return pd.DataFrame()

    def ok(params):
        called["b"] = True
        return pd.DataFrame([{"trade_date": "20261023", "rzye": 100.0}])

    _register_fake(cap_id, "src_a", empty)
    _register_fake(cap_id, "src_b", ok)

    import asyncio
    df = asyncio.run(get_data_facade().get_capability(cap_id).query())
    assert df.empty
    assert called["b"] is False, "空数据不应触发降级"


def test_none_return_degrades_like_failure(monkeypatch):
    """provider 返回 None（现有实现的失败/不可用语义）-> 降级"""
    cap_id = _make_test_capability()
    _fixed_order(monkeypatch, ["src_a", "src_b"])

    _register_fake(cap_id, "src_a", lambda params: None)
    _register_fake(cap_id, "src_b", lambda params: pd.DataFrame(
        [{"trade_date": "20261023", "rzye": 200.0}]))

    import asyncio
    df = asyncio.run(get_data_facade().get_capability(cap_id).query())
    assert df.iloc[0]["source"] == "src_b"


def test_all_sources_failed_returns_structured_empty(monkeypatch):
    """全部失败 -> 空 DataFrame 但列结构完整（Schema 标准列 + source/quality）"""
    cap_id = _make_test_capability()
    _fixed_order(monkeypatch, ["src_a"])

    def fail(params):
        raise RuntimeError("挂了")

    _register_fake(cap_id, "src_a", fail)

    import asyncio
    df = asyncio.run(get_data_facade().get_capability(cap_id).query())
    assert df.empty
    assert df.columns.tolist() == [
        "trade_date", "margin_balance", "short_balance", "source", "quality",
    ]


# ---------------------------------------------------------------- 字段标准化


def test_field_mapping_and_quality_marker(monkeypatch):
    """拼音原始字段 -> 标准字段；缺必填字段的行 quality=partial"""
    cap_id = _make_test_capability()
    _fixed_order(monkeypatch, ["src_a"])

    def data(params):
        return pd.DataFrame([
            {"trade_date": "20261023", "rzye": 100.0, "rqye": 1.0},   # 齐全
            {"trade_date": "20261024", "rzye": None, "rqye": 2.0},    # 缺必填 margin_balance
        ])

    _register_fake(cap_id, "src_a", data)

    import asyncio
    df = asyncio.run(get_data_facade().get_capability(cap_id).query())
    assert df.iloc[0]["margin_balance"] == 100.0
    assert df.iloc[0]["short_balance"] == 1.0
    assert df.iloc[0]["quality"] == "ok"
    assert df.iloc[1]["quality"] == "partial"


def test_unknown_param_rejected():
    """未知查询参数直接拒绝（防止参数名拼写错误静默丢条件）"""
    cap_id = _make_test_capability()
    _register_fake(cap_id, "src_a", lambda params: pd.DataFrame())

    import asyncio
    with pytest.raises(ValueError, match="不支持查询参数"):
        asyncio.run(get_data_facade().get_capability(cap_id).query(bogus_param=1))


# ---------------------------------------------------------------- 注册校验


def test_registration_rejects_grain_mismatch():
    """粒度不同的数据不允许注册到同一能力"""
    cap_id = _make_test_capability()

    with pytest.raises(ValueError, match="粒度"):
        register_capability(cap_id, "src_x", dict(RAW_MAPPING), grain="stock_daily")

    with pytest.raises(ValueError):
        from tradingagents.dataflows.capability.registry import registry
        registry.get_entry(cap_id, "src_x")


def test_registration_rejects_mapping_target_outside_schema():
    """映射目标必须是 Schema 标准字段（防止能力内字段口径发散）"""
    cap_id = _make_test_capability()

    with pytest.raises(ValueError, match="不在标准字段集合"):
        register_capability(cap_id, "src_y", {"rzye": "made_up_field"})


# ---------------------------------------------------------------- 双源字段对齐（live）


@pytest.mark.asyncio
async def test_dual_source_alignment_margin():
    """双源同一交易日数据，映射后字段名一致、数值在容差内（联网 + tushare token）"""
    import tradingagents.dataflows.providers.china.tushare as ts_mod
    import tradingagents.dataflows.providers.china.akshare as ak_mod
    from tradingagents.dataflows.capability.registry import registry

    ts_provider = ts_mod.get_tushare_provider()
    if not ts_provider.is_available():
        pytest.skip("tushare 不可用（无 token），跳过双源对账")
    ak_provider = ak_mod.get_akshare_provider()
    if not ak_provider.is_available():
        pytest.skip("akshare 不可用，跳过双源对账")

    handle = get_data_facade().get_capability("margin")
    ts_entry = registry.get_entry("margin", "tushare")
    ak_entry = registry.get_entry("margin", "akshare")

    # 以 akshare 全市场路径的最新日期为对账基准日
    ak_raw_all = await ak_entry.func(ak_provider)
    assert ak_raw_all is not None and not ak_raw_all.empty
    latest_date = (
        ak_raw_all["日期"].astype(str).str.replace("-", "", regex=False).max()
    )

    ts_raw = await ts_entry.func(ts_provider, trade_date=latest_date)
    if ts_raw is None or ts_raw.empty:
        pytest.skip(f"tushare 无 {latest_date} 数据（发布滞后），跳过对账")

    out_columns = ts_entry.schema.standard_field_names() + ["source", "quality"]
    ts_std = handle._standardize(ts_raw, ts_entry, out_columns)
    ak_std = handle._standardize(
        ak_raw_all[ak_raw_all["日期"].astype(str)
                   .str.replace("-", "", regex=False) == latest_date],
        ak_entry, out_columns,
    )

    # 字段名一致性：映射后列集合与 Schema 标准列一致
    assert set(ts_entry.schema.standard_field_names()) <= set(ts_std.columns)
    assert set(ak_entry.schema.standard_field_names()) <= set(ak_std.columns)

    # 行集完整性防护：tushare 按交易所（SSE/SZSE）分行返回，偶发缺行会导致合计口径失真；
    # 缺主力交易所任一行时跳过对账，避免假警报
    exchanges = set(ts_std["exchange_id"].dropna().astype(str).str.upper())
    if not {"SSE", "SZSE"} <= exchanges:
        pytest.skip(
            f"tushare {latest_date} 行集不完整（交易所={sorted(exchanges)}），跳过对账"
        )

    # 数值对账：akshare TOTAL 行 vs tushare 各交易所行汇总（容差 2%）
    ts_total = ts_std["margin_balance"].astype(float).sum()
    ak_total = float(ak_std["margin_balance"].iloc[0])
    assert ak_total > 0
    rel_diff = abs(ts_total - ak_total) / ak_total
    assert rel_diff < 0.02, (
        f"{latest_date} 融资余额口径偏差过大: tushare 合计={ts_total}, "
        f"akshare TOTAL={ak_total}, 相对偏差={rel_diff:.4f}"
    )
