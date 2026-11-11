"""数据能力注册机制 — 特色接口批量挂载声明测试

覆盖 5.4⑦ 步骤 6 的 8 个特色接口能力声明
（hsgt_moneyflow / limit_list / stk_limit / pledge_detail /
 audit_opinion / disclosure_rating / equity_incentive / management_penalties）：

1. 声明完整性：每个能力已注册 tushare 源，映射目标均在 Schema 标准字段内
2. 参数签名一致性：Schema 声明参数必须能以 kwargs 传给 provider 方法
   （facade 按 kwargs 调用，参数名对不上会在运行时才炸）
3. live smoke（可选）：tushare 可用时抽查走 facade 真实查询链路

设计文档：docs/05-design/v4.0/data-architecture-problems-and-optimization.md 5.4⑦
"""

import inspect

import pytest

import tradingagents.dataflows.providers.china.tushare  # noqa: F401 —— import 即注册
from tradingagents.dataflows.capability.registry import registry

SPECIAL_CAPABILITIES = [
    "hsgt_moneyflow",
    "limit_list",
    "stk_limit",
    "pledge_detail",
    "audit_opinion",
    "disclosure_rating",
    "equity_incentive",
    "management_penalties",
]


# ---------------------------------------------------------------- 声明完整性


@pytest.mark.parametrize("cap_id", SPECIAL_CAPABILITIES)
def test_tushare_registered_with_schema_aligned_mapping(cap_id):
    """每个特色能力已挂 tushare 源，映射目标全部是 Schema 标准字段"""
    entry = registry.get_entry(cap_id, "tushare")
    standard = set(entry.schema.standard_field_names())
    for raw_name, std_name in entry.field_mapping.items():
        assert std_name in standard, (
            f"{cap_id} 映射目标 '{std_name}' 不在标准字段集合 {sorted(standard)}"
        )


@pytest.mark.parametrize("cap_id", SPECIAL_CAPABILITIES)
def test_schema_params_match_provider_signature(cap_id):
    """Schema 参数必须被 provider 方法签名接受（facade 以 kwargs 传参）"""
    entry = registry.get_entry(cap_id, "tushare")
    sig = inspect.signature(entry.func)
    func_params = set(sig.parameters)
    for param in entry.schema.params:
        assert param.name in func_params, (
            f"{cap_id} 的 Schema 参数 '{param.name}' 不在 provider 方法签名 "
            f"{sorted(func_params)} 中，facade 传参会 TypeError"
        )


def test_all_special_capabilities_registered():
    """8 个特色能力全部在注册表中（防止漏挂装饰器）"""
    registered = registry.list_capabilities()
    for cap_id in SPECIAL_CAPABILITIES:
        assert cap_id in registered, f"能力 '{cap_id}' 未注册（装饰器漏挂？）"


# ---------------------------------------------------------------- live smoke（可跳过）


@pytest.mark.asyncio
async def test_live_query_through_facade_stk_limit():
    """抽查 stk_limit 走完整 facade 链路（联网 + tushare token）"""
    import tradingagents.dataflows.providers.china.tushare as ts_mod
    from tradingagents.dataflows.capability.facade import get_data_facade

    if not ts_mod.get_tushare_provider().is_available():
        pytest.skip("tushare 不可用（无 token），跳过 live smoke")

    # 用指数日线拿一个近期交易日，避免猜非交易日
    provider = ts_mod.get_tushare_provider()
    idx = await provider.get_index_daily(ts_code="000001.SH")
    if idx is None or idx.empty:
        pytest.skip("tushare 无指数日线数据，跳过 live smoke")
    trade_date = str(idx["trade_date"].max())

    df = await get_data_facade().get_capability("stk_limit").query(trade_date=trade_date)
    assert not df.empty, f"{trade_date} 无涨跌停价格数据"
    for col in ("trade_date", "ts_code", "up_limit_price", "down_limit_price",
                "source", "quality"):
        assert col in df.columns
    assert (df["source"] == "tushare").all()
