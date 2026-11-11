"""数据能力注册机制 — 财务三表+指标能力测试（stock_fundamentals 模式 C 迁移）

financial_income / financial_balance / financial_cashflow / financial_indicators
为按报告期（stock_period 粒度）的多行 DataFrame 能力：local 源读取本地财务缓存，
tushare 直连原表接口（标准名=原生字段名，零映射），akshare 走东财 EM 报表接口
（financial_indicators 无 akshare 源，EM 摘要纵表不适配）。本文件覆盖：
1. 注册健全性：4 能力源集合 + grain=stock_period + 参数签名机器校验
   + field_mapping 目标合法性（接入规约：没有字段对齐测试不许注册）
2. local 源适配器契约：整包无数据/全桶空 → None 降级；排序截断；
   桶候选兼容（cashflow_statement 兜底）；单桶空 → 空 DataFrame 不降级
3. facade 真实能力全链路：空表不降级语义 + local 命中标准化裁剪

设计文档：docs/05-design/v4.0/data-architecture-problems-and-optimization.md 5.4
"""

import asyncio
import dataclasses
import inspect

import pandas as pd
import pytest

import tradingagents.dataflows.optimized_china_data  # noqa: F401 —— import 即注册 local 源
import tradingagents.dataflows.providers.china.akshare  # noqa: F401 —— import 即注册 akshare 源
import tradingagents.dataflows.providers.china.tushare  # noqa: F401 —— import 即注册 tushare 源
from tradingagents.dataflows.capability.facade import get_data_facade
from tradingagents.dataflows.capability.registry import registry
from tradingagents.dataflows.capability.schema import GRAIN_STOCK_PERIOD

EXPECTED_SOURCES = {
    "financial_income": {"local", "tushare", "akshare"},
    "financial_balance": {"local", "tushare", "akshare"},
    "financial_cashflow": {"local", "tushare", "akshare"},
    "financial_indicators": {"local", "tushare"},  # EM 摘要纵表不适配，akshare 不注册
}

# tushare 原生字段名基准（标准名=原生名，防 schema 漂移）
TUSHARE_STATEMENT_FIELDS = {
    "financial_income": {
        "end_date", "ann_date", "f_ann_date",
        "total_revenue", "revenue", "operate_profit",
        "n_income_attr_p", "n_income", "basic_eps",
    },
    "financial_balance": {
        "end_date", "ann_date", "f_ann_date",
        "total_assets", "total_liab", "total_hldr_eqy_exc_min_int",
        "total_cur_assets", "total_cur_liab", "money_cap",
    },
    "financial_cashflow": {
        "end_date", "ann_date", "f_ann_date",
        "n_cashflow_act", "n_cashflow_inv_act", "n_cash_flows_fnc_act",
        "c_cash_equ_beg_period", "c_cash_equ_end_period",
    },
    "financial_indicators": {
        "end_date", "ann_date", "f_ann_date",
        "roe", "roe_dt", "roa", "grossprofit_margin",
        "netprofit_margin", "debt_to_assets", "current_ratio",
    },
}

# akshare EM 适配器映射基准（EM 原始列名 → 标准字段，防接口漂移）
AKSHARE_EM_FIELD_MAPPING = {
    "financial_income": {
        "REPORT_DATE", "TOTAL_OPERATE_INCOME", "OPERATE_INCOME", "OPERATE_PROFIT",
        "PARENT_NETPROFIT", "NETPROFIT", "BASIC_EPS",
    },
    "financial_balance": {
        "REPORT_DATE", "TOTAL_ASSETS", "TOTAL_LIABILITIES", "TOTAL_PARENT_EQUITY",
        "TOTAL_CURRENT_ASSETS", "TOTAL_CURRENT_LIAB", "MONETARYFUNDS",
    },
    "financial_cashflow": {
        "REPORT_DATE", "NETCASH_OPERATE", "NETCASH_INVEST", "NETCASH_FINANCE",
        "BEGIN_CCE", "END_CCE",
    },
}


def _fixed_order(monkeypatch, order):
    from tradingagents.dataflows.capability import facade as facade_mod

    monkeypatch.setattr(
        facade_mod.CapabilityHandle,
        "_resolve_source_order",
        lambda self, registered: [s for s in order if s in registered],
    )


def _patch_local_cache(monkeypatch, payload):
    """替换 local 源底层缓存读取（不触碰 MongoDB）"""
    from tradingagents.dataflows.optimized_china_data import OptimizedChinaDataProvider

    monkeypatch.setattr(
        OptimizedChinaDataProvider,
        "_get_cached_raw_financial_data",
        lambda self, symbol: payload,
    )


# ---------------------------------------------------------------- 注册健全性


def test_financial_capabilities_registration_sanity():
    """4 能力源集合 + grain=stock_period + 参数签名机器校验 + 映射目标合法性"""
    for cap_id, expected in EXPECTED_SOURCES.items():
        assert set(registry.get_sources(cap_id)) == expected, cap_id
        for source in sorted(registry.get_sources(cap_id)):
            entry = registry.get_entry(cap_id, source)
            assert entry.schema.grain == GRAIN_STOCK_PERIOD, cap_id
            # Schema 参数必须被 provider 方法签名接受（self + symbol + limit）
            func_params = set(inspect.signature(entry.func).parameters)
            for param in entry.schema.params:
                assert param.name in func_params, f"{cap_id}/{source} 缺参数 {param.name}"
            # 映射目标必须是 Schema 标准字段（零映射亦合法：标准名=原生名）
            assert set(entry.field_mapping.values()) <= set(
                entry.schema.standard_field_names()
            ), cap_id


def test_tushare_standard_fields_are_native_columns():
    """tushare 源标准名=tushare 原生字段名（字段集合对齐基准防漂移）；
    映射源不得占用标准字段名（防 rename 产生重复列名冲突）"""
    for cap_id, expected in TUSHARE_STATEMENT_FIELDS.items():
        entry = registry.get_entry(cap_id, "tushare")
        assert not (set(entry.field_mapping) & expected), cap_id
        assert set(entry.schema.standard_field_names()) == expected, cap_id


def test_akshare_em_field_mapping_covers_key_columns():
    """akshare EM 适配器映射：报告期与核心科目列均有标准字段承接，防接口漂移"""
    for cap_id, expected in AKSHARE_EM_FIELD_MAPPING.items():
        entry = registry.get_entry(cap_id, "akshare")
        assert set(entry.field_mapping) == expected, cap_id
        assert entry.field_mapping["REPORT_DATE"] == "end_date", cap_id
        assert set(entry.field_mapping.values()) <= set(
            entry.schema.standard_field_names()
        ), cap_id


# ---------------------------------------------------------------- local 源适配器契约


def test_local_none_payload_degrades(monkeypatch):
    """本地缓存整包无数据 -> None（触发门面降级到下一源）"""
    _patch_local_cache(monkeypatch, None)
    entry = registry.get_entry("financial_income", "local")
    provider = entry.provider_factory()
    assert asyncio.run(entry.func(provider, symbol="600519")) is None


def test_local_all_buckets_empty_degrades(monkeypatch):
    """本地缓存存在但所有消费桶全空 -> None（对齐历史 any(payload.values()) 降级语义）"""
    _patch_local_cache(monkeypatch, {"income_statement": [], "balance_sheet": []})
    entry = registry.get_entry("financial_balance", "local")
    provider = entry.provider_factory()
    assert asyncio.run(entry.func(provider, symbol="600519")) is None


def test_local_sort_desc_and_limit(monkeypatch):
    """命中桶按 end_date 降序 + limit 截断（取最新报告期在前）"""
    _patch_local_cache(monkeypatch, {
        "income_statement": [
            {"end_date": "20240331", "total_revenue": 1.0},
            {"end_date": "20241231", "total_revenue": 3.0},
            {"end_date": "20240930", "total_revenue": 2.0},
        ],
    })
    entry = registry.get_entry("financial_income", "local")
    provider = entry.provider_factory()
    df = asyncio.run(entry.func(provider, symbol="600519", limit=2))
    assert df["end_date"].tolist() == ["20241231", "20240930"]
    assert df["total_revenue"].tolist() == [3.0, 2.0]


def test_local_cashflow_bucket_candidates(monkeypatch):
    """cashflow 桶候选兼容两种历史命名（cash_flow 优先，cashflow_statement 兜底）"""
    _patch_local_cache(monkeypatch, {
        "cashflow_statement": [{"end_date": "20240930", "n_cashflow_act": 5.0}],
        "balance_sheet": [{"end_date": "20240930", "total_assets": 1.0}],
    })
    entry = registry.get_entry("financial_cashflow", "local")
    provider = entry.provider_factory()
    df = asyncio.run(entry.func(provider, symbol="600519"))
    assert len(df) == 1
    assert df.iloc[0]["n_cashflow_act"] == 5.0


def test_local_missing_bucket_returns_empty_without_degrade(monkeypatch):
    """其它桶有数据、本能力桶为空 -> 空 DataFrame（不降级，缺桶不补）"""
    _patch_local_cache(monkeypatch, {
        "income_statement": [{"end_date": "20240930", "total_revenue": 1.0}],
    })
    entry = registry.get_entry("financial_indicators", "local")
    provider = entry.provider_factory()
    df = asyncio.run(entry.func(provider, symbol="600519"))
    assert df.empty


# ---------------------------------------------------------------- facade 真实能力全链路


def test_facade_empty_frame_not_degraded(monkeypatch):
    """真实能力全链路：local 命中有效包但本能力桶空 -> 门面直接返回空表不降级（避免语义漂移）"""
    # 其它桶有数据、本能力桶为空：local 源契约返回空 DataFrame（非 None，不触发降级）
    _patch_local_cache(monkeypatch, {
        "income_statement": [],
        "balance_sheet": [{"end_date": "20240930", "total_assets": 1.0}],
    })
    _fixed_order(monkeypatch, ["local", "tushare"])

    # tushare 返回非空哨兵帧：若门面错误降级到 tushare，断言立即失败（同时保证单测离线）
    # CapabilityEntry 是 frozen dataclass：用 dataclasses.replace 造替身，setitem 换入注册表
    async def _sentinel(provider, **params):
        return pd.DataFrame([{"end_date": "20991231", "total_revenue": 999.0}])

    entry = registry.get_entry("financial_income", "tushare")
    monkeypatch.setitem(
        registry._entries["financial_income"],
        "tushare",
        dataclasses.replace(entry, func=_sentinel),
    )

    df = asyncio.run(
        get_data_facade().get_capability("financial_income").query(symbol="600519")
    )
    assert df.empty
    assert "end_date" in df.columns


def test_facade_local_source_end_to_end(monkeypatch):
    """真实能力全链路：local 命中 -> 标准列 + source=local + 非标准列被门面裁剪"""
    _patch_local_cache(monkeypatch, {
        "income_statement": [
            {"end_date": "20240930", "total_revenue": 100.0, "update_flag": "1"},
        ],
    })
    _fixed_order(monkeypatch, ["local"])
    df = asyncio.run(
        get_data_facade()
        .get_capability("financial_income")
        .query(symbol="600519", limit=1)
    )
    assert len(df) == 1
    assert df.iloc[0]["source"] == "local"
    assert df.iloc[0]["quality"] == "ok"
    assert df.iloc[0]["end_date"] == "20240930"
    assert df.iloc[0]["total_revenue"] == 100.0
    assert "update_flag" not in df.columns  # 超出 Schema 的列被门面裁剪
