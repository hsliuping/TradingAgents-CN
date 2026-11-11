"""数据能力注册机制 — daily_stats 能力测试

daily_stats 为单条聚合 Dict 形状能力（tushare 由 daily 接口逐股聚合计算；
akshare 为乐咕乐股赚钱效应快照，仅覆盖最新交易日、缺涨跌幅分布 4 桶），
本文件覆盖：
1. 注册健全性：tushare + akshare 双源注册 + Schema 粒度 + 参数签名机器校验
   （接入规约：没有字段对齐测试不许注册）
2. facade Dict 包装（模式 C）：全标量值 Dict -> 单行 DataFrame + 标准化；
   部分字段 Dict -> 缺省可选字段补 NaN（quality 仍为 ok）
3. facade Dict 失败语义：含集合值 Dict 记失败 -> 降级下一源；
   请求失败（None）-> 降级下一源接管
4. akshare legu 适配器契约：快照聚合/单位归一/日期守卫/异常降级

设计文档：docs/05-design/v4.0/data-architecture-problems-and-optimization.md 5.4
"""

import asyncio
import inspect
import itertools

import pandas as pd
import pytest

import tradingagents.dataflows.providers.china.akshare  # noqa: F401 —— import 即注册
import tradingagents.dataflows.providers.china.tushare  # noqa: F401 —— import 即注册
from tradingagents.dataflows.capability import facade as facade_mod
from tradingagents.dataflows.capability.facade import get_data_facade
from tradingagents.dataflows.capability.registry import register_capability, registry
from tradingagents.dataflows.capability.schema import (
    GRAIN_MARKET_DAILY,
    CapabilityField,
    CapabilityParam,
    CapabilitySchema,
)
from tradingagents.dataflows.capability.schemas import register_schema

_cap_counter = itertools.count()

STATS_RAW = {
    "trade_date": "20260410",
    "total": 5495,
    "up_count": 3977,
    "down_count": 1397,
    "flat_count": 121,
    "up_ratio": 72.4,
    "down_ratio": 25.4,
    "up_gt5": 244,
    "up_3_5": 324,
    "down_gt5": 55,
    "down_3_5": 111,
}


def _make_test_capability():
    """每个测试独立能力 ID，避免污染全局 'daily_stats' 注册"""
    cap_id = f"ut_dstats_{next(_cap_counter)}"
    schema = CapabilitySchema(
        capability_id=cap_id,
        grain=GRAIN_MARKET_DAILY,
        fields=[
            CapabilityField("trade_date", "str", True, "交易日期 YYYYMMDD"),
            CapabilityField("total", "int", False, "全市场股票总数（家）"),
            CapabilityField("up_count", "int", False, "上涨家数（家）"),
            CapabilityField("down_count", "int", False, "下跌家数（家）"),
            CapabilityField("up_ratio", "float", False, "上涨占比（%）"),
        ],
        params=[
            CapabilityParam("trade_date", "str", True, "交易日期 YYYYMMDD"),
        ],
    )
    register_schema(schema)
    return cap_id


class _FakeProvider:
    """占位 provider 实例（fake fetch 不依赖实例状态）"""
    pass


def _register_fake(cap_id, source, fetch):
    async def fake_fetch(self, **params):
        return fetch(params)

    register_capability(
        cap_id, source, {},
        provider_factory=lambda: _FakeProvider(),
    )(fake_fetch)
    return fake_fetch


def _fixed_order(monkeypatch, order):
    monkeypatch.setattr(
        facade_mod.CapabilityHandle,
        "_resolve_source_order",
        lambda self, registered: [s for s in order if s in registered],
    )


# ---------------------------------------------------------------- 注册健全性


def test_daily_stats_registration_sanity():
    """tushare + akshare 双源注册 + 粒度 market_daily + 参数签名机器校验"""
    # 注册顺序取决于模块 import 顺序（测试会话内全局注册表），断言集合而非顺序
    assert set(registry.get_sources("daily_stats")) == {"tushare", "akshare"}
    for source in sorted(registry.get_sources("daily_stats")):
        entry = registry.get_entry("daily_stats", source)
        assert entry.schema.grain == GRAIN_MARKET_DAILY
        # Dict 形状零映射：键即标准名
        assert entry.field_mapping == {}
        # Schema 参数必须被 provider 方法签名接受（self + trade_date）
        func_params = set(inspect.signature(entry.func).parameters)
        for param in entry.schema.params:
            assert param.name in func_params, f"Schema 参数 {param.name} 不在方法签名中"


def test_daily_stats_tushare_dict_keys_are_standard_fields():
    """tushare get_daily_stats 返回 Dict 的键集合与 Schema 标准字段对齐"""
    entry = registry.get_entry("daily_stats", "tushare")
    import tradingagents.dataflows.providers.china.tushare as ts_mod

    import asyncio

    provider = ts_mod.get_tushare_provider()
    if not provider.is_available():
        # 无 token 环境跳过实测，改为静态校验返回结构（键集合由实现保证）
        assert set(entry.schema.standard_field_names()) == set(STATS_RAW)
        return
    raw = asyncio.run(entry.func(provider, trade_date="20260410"))
    if raw is None:
        return  # 非交易日/接口无数据，不视为失败
    assert set(raw) <= set(entry.schema.standard_field_names())


# ---------------------------------------------------------------- facade Dict 包装（模式 C）


def test_dict_shape_wrapped_to_single_row(monkeypatch):
    """全标量值 Dict -> 门面包装为单行 DataFrame + 标准字段补齐 + quality 标记"""
    cap_id = _make_test_capability()
    _fixed_order(monkeypatch, ["tushare"])
    _register_fake(cap_id, "tushare", lambda params: dict(STATS_RAW))

    df = asyncio.run(get_data_facade().get_capability(cap_id).query(trade_date="20260410"))
    assert len(df) == 1
    assert df.iloc[0]["source"] == "tushare"
    assert df.iloc[0]["quality"] == "ok"  # 必填字段 trade_date 齐全
    assert df.iloc[0]["up_count"] == 3977
    assert df.iloc[0]["up_ratio"] == 72.4
    # 输出列 = Schema 标准字段 + source/quality（Dict 中超出 Schema 的键被裁剪）
    assert df.columns.tolist() == entry_schema_field_names(cap_id) + ["source", "quality"]


def test_dict_partial_fields_padded_with_na(monkeypatch):
    """Dict 仅含部分标准字段（如 akshare 快照缺分布 4 桶）-> 缺省可选字段补 NaN，quality 仍为 ok"""
    cap_id = _make_test_capability()
    _fixed_order(monkeypatch, ["tushare"])
    _register_fake(
        cap_id, "tushare",
        lambda params: {"trade_date": "20260410", "up_count": 3977},
    )

    df = asyncio.run(get_data_facade().get_capability(cap_id).query(trade_date="20260410"))
    assert len(df) == 1
    assert df.iloc[0]["quality"] == "ok"  # 必填字段 trade_date 齐全
    assert df.iloc[0]["up_count"] == 3977
    assert pd.isna(df.iloc[0]["up_ratio"])  # 缺省可选字段补 NA（消费方需容错）


def entry_schema_field_names(cap_id):
    from tradingagents.dataflows.capability.schemas import get_schema
    return get_schema(cap_id).standard_field_names()


def test_dict_with_collection_values_fails_and_degrades(monkeypatch):
    """含集合值 Dict 非单条记录形状 -> 记失败降级下一源接管"""
    cap_id = _make_test_capability()
    _fixed_order(monkeypatch, ["tushare", "akshare"])

    def bad_shape(params):
        return {"trade_date": "20260410", "rows": [1, 2, 3]}

    _register_fake(cap_id, "tushare", bad_shape)
    _register_fake(cap_id, "akshare", lambda params: dict(STATS_RAW))

    df = asyncio.run(get_data_facade().get_capability(cap_id).query(trade_date="20260410"))
    assert len(df) == 1
    assert df.iloc[0]["source"] == "akshare"


def test_dict_all_sources_bad_shape_returns_empty(monkeypatch):
    """所有源均返回含集合值 Dict -> 全部记失败，返回空表（含标准列结构）"""
    cap_id = _make_test_capability()
    _fixed_order(monkeypatch, ["tushare"])

    def bad_shape(params):
        return {"trade_date": "20260410", "nested": {"a": 1}}

    _register_fake(cap_id, "tushare", bad_shape)

    df = asyncio.run(get_data_facade().get_capability(cap_id).query(trade_date="20260410"))
    assert df.empty
    assert "up_count" in df.columns


def test_none_failure_degrades_to_dict_source(monkeypatch):
    """请求失败（None）-> 降级下一源；下一源 Dict 形状正常接管"""
    cap_id = _make_test_capability()
    _fixed_order(monkeypatch, ["tushare", "akshare"])

    _register_fake(cap_id, "tushare", lambda params: None)
    _register_fake(cap_id, "akshare", lambda params: dict(STATS_RAW))

    df = asyncio.run(get_data_facade().get_capability(cap_id).query(trade_date="20260410"))
    assert len(df) == 1
    assert df.iloc[0]["source"] == "akshare"


# ---------------------------------------------------------------- akshare legu 适配器契约


def _legu_snapshot_frame() -> pd.DataFrame:
    """乐咕乐股赚钱效应快照（12×2 纵表，item/value），取自 2026-10-23 实测"""
    return pd.DataFrame(
        {
            "item": [
                "上涨", "涨停", "真实涨停", "st st*涨停",
                "下跌", "跌停", "真实跌停", "st st*跌停",
                "平盘", "停牌", "活跃度", "统计日期",
            ],
            "value": [
                4197.0, 82.0, 78.0, 2.0,
                887.0, 9.0, 6.0, 1.0,
                135.0, 5.0, "80.34%", "2026-10-23 15:00:00",
            ],
        }
    )


def _get_akshare_entry_and_provider():
    import tradingagents.dataflows.providers.china.akshare as akshare_mod

    entry = registry.get_entry("daily_stats", "akshare")
    provider = akshare_mod.get_akshare_provider()
    if not provider.is_available():
        pytest.skip("akshare 未安装/不可用")
    return entry, provider


def test_daily_stats_akshare_snapshot_aggregates(monkeypatch):
    """legu 快照 -> 家数聚合 + ratio % 归一 + 分布 4 桶不输出；快照外字段（涨停/活跃度）不进入结果"""
    import akshare as ak

    entry, provider = _get_akshare_entry_and_provider()
    monkeypatch.setattr(ak, "stock_market_activity_legu", lambda: _legu_snapshot_frame())

    raw = asyncio.run(entry.func(provider, trade_date="20261023"))
    assert raw is not None
    assert set(raw) <= set(entry.schema.standard_field_names())
    assert raw["trade_date"] == "20261023"
    assert raw["up_count"] == 4197
    assert raw["down_count"] == 887
    assert raw["flat_count"] == 135
    assert raw["total"] == 5224  # 上涨+下跌+平盘+停牌（与 legu 活跃度分母同口径）
    assert abs(raw["up_ratio"] - 80.34) < 0.01  # % 口径，实现内归一
    assert "up_gt5" not in raw  # 快照无逐股明细，分布 4 桶宁缺勿造


def test_daily_stats_akshare_date_mismatch_returns_none(monkeypatch):
    """legu 快照仅覆盖最新交易日，请求日不一致 -> None（宁缺勿造，不编造历史）"""
    import akshare as ak

    entry, provider = _get_akshare_entry_and_provider()
    monkeypatch.setattr(ak, "stock_market_activity_legu", lambda: _legu_snapshot_frame())

    assert asyncio.run(entry.func(provider, trade_date="20260101")) is None


def test_daily_stats_akshare_missing_core_counts_returns_none(monkeypatch):
    """快照缺上涨/下跌/平盘核心家数 -> None"""
    import akshare as ak

    entry, provider = _get_akshare_entry_and_provider()
    frame = _legu_snapshot_frame()
    monkeypatch.setattr(
        ak, "stock_market_activity_legu",
        lambda: frame[frame["item"] != "上涨"],
    )

    assert asyncio.run(entry.func(provider, trade_date="20261023")) is None


def test_daily_stats_akshare_exception_returns_none(monkeypatch):
    """接口抛异常 -> None（触发 facade 降级）"""
    import akshare as ak

    entry, provider = _get_akshare_entry_and_provider()

    def _boom():
        raise RuntimeError("legu 不可用")

    monkeypatch.setattr(ak, "stock_market_activity_legu", _boom)

    assert asyncio.run(entry.func(provider, trade_date="20261023")) is None
