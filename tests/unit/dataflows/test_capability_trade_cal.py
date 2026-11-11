"""数据能力注册机制 — A股交易日历能力测试（trade_cal）

trade_cal（A 股交易日历，GRAIN_MARKET_DAILY 粒度）双源：
- tushare 委托 pro.trade_cal：返回区间内全部日历日（含休市日 is_open=0）
- akshare 委托 tool_trade_date_hist_sina：新浪历史交易日历仅含交易日、
  无休市行，适配器内区间过滤后统一 is_open=1

消费方约定：取 is_open==1 子集即为交易日列表，两源等价。

本文件覆盖：
1. 注册健全性：源集合 + grain + 参数签名机器校验
2. schema 字段基准（3 字段，防漂移）
3. 双源适配器契约：区间标准化/None/异常 -> None 降级；空 -> 空
   DataFrame 不降级；tushare 参数去横线透传
4. facade 真实能力全链路：tushare->akshare 降级链 + 全源失败空
   DataFrame（含标准列）+ query_capability_sync 同步路径
5. 调用方迁移：data_completeness_checker._get_latest_trade_date 走
   能力（is_open==1 max -> YYYY-MM-DD）/ 异常与空日历回退工作日
   猜测 / 非 CN 市场跳过能力调用

设计文档：docs/05-design/v4.0/data-architecture-problems-and-optimization.md 5.4
"""

import asyncio
import inspect
import logging
from datetime import datetime, timedelta

import pandas as pd

import tradingagents.dataflows.providers.china.akshare  # noqa: F401 —— import 即注册 akshare 源
import tradingagents.dataflows.providers.china.tushare  # noqa: F401 —— import 即注册 tushare 源
from tradingagents.dataflows.capability import query_capability_sync
from tradingagents.dataflows.capability.facade import get_data_facade
from tradingagents.dataflows.capability.registry import registry
from tradingagents.dataflows.capability.schema import GRAIN_MARKET_DAILY

EXPECTED_SOURCES = {"trade_cal": {"tushare", "akshare"}}
EXPECTED_GRAIN = {"trade_cal": GRAIN_MARKET_DAILY}

# 标准字段集合基准（防 schema 漂移）
STANDARD_FIELDS = {"exchange", "cal_date", "is_open"}


def _fixed_order(monkeypatch, order):
    from tradingagents.dataflows.capability import facade as facade_mod

    monkeypatch.setattr(
        facade_mod.CapabilityHandle,
        "_resolve_source_order",
        lambda self, registered: [s for s in order if s in registered],
    )


def _tushare_cal_payload():
    """tushare pro.trade_cal 原始形态（YYYYMMDD 字符串 + 休市行 + 多余列）"""
    return pd.DataFrame(
        {
            "exchange": ["SSE", "SSE", "SSE", "SSE", "SSE"],
            "cal_date": ["20241001", "20241002", "20241004", "20241007", "20241008"],
            "is_open": [0, 0, 1, 0, 1],
            "pretrade_date": ["20240930", "20241001", "20241002", "20241004", "20241007"],
        }
    )


def _sina_payload():
    """akshare tool_trade_date_hist_sina 原始形态（仅交易日，含区间外日期）"""
    return pd.DataFrame(
        {
            "trade_date": [
                "2024-09-27", "2024-09-30", "2024-10-08", "2024-10-31", "2024-11-01",
            ]
        }
    )


def _make_tushare_stub(monkeypatch, payload=None, error=None):
    """构造跳过 __init__ 的 TushareProvider 桩，api.trade_cal 返回预设载荷"""
    from tradingagents.dataflows.providers.china.tushare import TushareProvider

    monkeypatch.setattr(TushareProvider, "is_available", lambda self: True)
    calls = []

    class _ApiStub:
        def trade_cal(self, exchange, start_date, end_date):
            calls.append(
                {"exchange": exchange, "start_date": start_date, "end_date": end_date}
            )
            if error is not None:
                raise error
            return payload

    provider = TushareProvider.__new__(TushareProvider)
    provider.api = _ApiStub()
    provider.logger = logging.getLogger("test-stub-tushare")
    return provider, calls


def _make_akshare_stub(monkeypatch, payload=None, error=None):
    """patch akshare.tool_trade_date_hist_sina 模块属性 + 构造 __new__ 桩 provider"""
    import akshare as ak
    from tradingagents.dataflows.providers.china.akshare import AKShareProvider

    monkeypatch.setattr(AKShareProvider, "is_available", lambda self: True)
    calls = []

    def _stub():
        calls.append({})
        if error is not None:
            raise error
        return payload

    monkeypatch.setattr(ak, "tool_trade_date_hist_sina", _stub)
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


# ---------------------------------------------------------------- 注册健全性


def test_registration_sanity():
    """源集合 + grain + Schema 参数被 provider 方法签名接受"""
    for cap_id, expected in EXPECTED_SOURCES.items():
        assert set(registry.get_sources(cap_id)) == expected, cap_id
        for source in sorted(registry.get_sources(cap_id)):
            entry = registry.get_entry(cap_id, source)
            assert entry.schema.grain == EXPECTED_GRAIN[cap_id], cap_id
            func_params = set(inspect.signature(entry.func).parameters)
            for param in entry.schema.params:
                assert param.name in func_params, f"{cap_id}/{source} 缺参数 {param.name}"


def test_schema_standard_fields_baseline():
    """标准字段集合基准（防漂移）"""
    entry = registry.get_entry("trade_cal", "tushare")
    assert set(entry.schema.standard_field_names()) == STANDARD_FIELDS
    ak_entry = registry.get_entry("trade_cal", "akshare")
    assert set(ak_entry.schema.standard_field_names()) == STANDARD_FIELDS


# ---------------------------------------------------------------- 适配器契约


def test_tushare_adapter_normalizes_calendar(monkeypatch):
    """tushare 适配器：YYYYMMDD -> datetime、is_open 数值化、升序、参数去横线"""
    provider, calls = _make_tushare_stub(monkeypatch, payload=_tushare_cal_payload())
    entry = registry.get_entry("trade_cal", "tushare")

    df = asyncio.run(
        entry.func(provider, start_date="2024-10-01", end_date="2024-10-31")
    )

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 5
    # 日期标准化为 datetime 且升序
    assert all(isinstance(v, pd.Timestamp) for v in df["cal_date"])
    assert df["cal_date"].is_monotonic_increasing
    assert df["cal_date"].iloc[0] == pd.Timestamp("2024-10-01")
    assert df["is_open"].tolist() == [0, 0, 1, 0, 1]
    assert (df["exchange"] == "SSE").all()
    # 参数去横线透传
    assert calls[0] == {
        "exchange": "SSE",
        "start_date": "20241001",
        "end_date": "20241031",
    }


def test_tushare_adapter_none_error_unavailable(monkeypatch):
    """tushare 接口失败 -> None 降级；抛异常 -> None 降级；源不可用 -> None"""
    from tradingagents.dataflows.providers.china.tushare import TushareProvider

    entry = registry.get_entry("trade_cal", "tushare")

    provider, _ = _make_tushare_stub(monkeypatch, payload=None)
    assert asyncio.run(
        entry.func(provider, start_date="2024-10-01")
    ) is None

    provider2, _ = _make_tushare_stub(monkeypatch, error=RuntimeError("接口权限不足"))
    assert asyncio.run(
        entry.func(provider2, start_date="2024-10-01")
    ) is None

    monkeypatch.setattr(TushareProvider, "is_available", lambda self: False)
    provider3 = TushareProvider.__new__(TushareProvider)
    provider3.api = None
    assert asyncio.run(
        entry.func(provider3, start_date="2024-10-01")
    ) is None


def test_tushare_adapter_empty_returns_empty_dataframe(monkeypatch):
    """接口成功但无数据 -> 空 DataFrame（不降级语义，与 None 相区别）"""
    entry = registry.get_entry("trade_cal", "tushare")
    provider, _ = _make_tushare_stub(monkeypatch, payload=pd.DataFrame())
    df = asyncio.run(entry.func(provider, start_date="2024-10-01"))
    assert isinstance(df, pd.DataFrame)
    assert df.empty


def test_akshare_adapter_filters_range_and_marks_open(monkeypatch):
    """akshare 适配器：区间过滤（区间外/休市期缺失）+ 统一 is_open=1 + 升序"""
    provider, calls = _make_akshare_stub(monkeypatch, payload=_sina_payload())
    entry = registry.get_entry("trade_cal", "akshare")

    df = asyncio.run(
        entry.func(provider, start_date="2024-09-28", end_date="2024-10-31")
    )

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 3
    assert df["cal_date"].tolist() == [
        pd.Timestamp("2024-09-30"),
        pd.Timestamp("2024-10-08"),
        pd.Timestamp("2024-10-31"),
    ]
    assert df["is_open"].tolist() == [1, 1, 1]
    assert (df["exchange"] == "SSE").all()
    assert calls == [{}]


def test_akshare_adapter_none_and_error(monkeypatch):
    """akshare 反爬拦截（None）-> 空 DataFrame；抛异常 -> None 降级"""
    entry = registry.get_entry("trade_cal", "akshare")

    provider, _ = _make_akshare_stub(monkeypatch, payload=None)
    df = asyncio.run(entry.func(provider, start_date="2024-10-01"))
    assert isinstance(df, pd.DataFrame)
    assert df.empty

    provider2, _ = _make_akshare_stub(monkeypatch, error=RuntimeError("网络中断"))
    assert asyncio.run(
        entry.func(provider2, start_date="2024-10-01")
    ) is None


# ---------------------------------------------------------------- facade 全链路


def test_facade_fallback_tushare_to_akshare(monkeypatch):
    """降级链：tushare 失败（None）-> akshare 接管"""
    tushare_stub, _ = _make_tushare_stub(monkeypatch, payload=None)
    akshare_stub, _ = _make_akshare_stub(monkeypatch, payload=_sina_payload())
    _patch_factories(
        monkeypatch, tushare_provider=tushare_stub, akshare_provider=akshare_stub
    )
    _fixed_order(monkeypatch, ["tushare", "akshare"])

    df = asyncio.run(
        get_data_facade()
        .get_capability("trade_cal")
        .query(start_date="2024-09-28", end_date="2024-10-31")
    )

    assert len(df) == 3
    assert df.iloc[-1]["source"] == "akshare"
    assert df.iloc[-1]["cal_date"] == pd.Timestamp("2024-10-31")
    assert df.iloc[-1]["is_open"] == 1
    assert df.iloc[-1]["quality"] == "ok"


def test_facade_all_sources_fail_returns_empty_with_columns(monkeypatch):
    """全源失败 -> 空 DataFrame（含标准列结构），不抛异常"""
    tushare_stub, _ = _make_tushare_stub(monkeypatch, payload=None)
    akshare_stub, _ = _make_akshare_stub(monkeypatch, payload=None)
    _patch_factories(
        monkeypatch, tushare_provider=tushare_stub, akshare_provider=akshare_stub
    )
    _fixed_order(monkeypatch, ["tushare", "akshare"])

    df = asyncio.run(
        get_data_facade()
        .get_capability("trade_cal")
        .query(start_date="2024-10-01")
    )

    assert df.empty
    assert {"exchange", "cal_date", "is_open", "source", "quality"} <= set(df.columns)


def test_query_capability_sync_path(monkeypatch):
    """同步包装路径（data_completeness_checker 同款调用）"""
    provider, _ = _make_tushare_stub(monkeypatch, payload=_tushare_cal_payload())
    _patch_factories(monkeypatch, tushare_provider=provider)
    _fixed_order(monkeypatch, ["tushare", "akshare"])

    df = query_capability_sync("trade_cal", start_date="2024-10-01", end_date="2024-10-31")

    assert len(df) == 5
    assert df.iloc[-1]["source"] == "tushare"
    assert df.iloc[-1]["cal_date"] == pd.Timestamp("2024-10-08")


# ---------------------------------------------------------------- 调用方迁移


def _expected_fallback():
    """复刻调用方回退逻辑：今天往前 5 天内最近的工作日（YYYY-MM-DD）"""
    today = datetime.now()
    for delta in range(0, 5):
        check = today - timedelta(days=delta)
        if check.weekday() < 5:
            return check.strftime("%Y-%m-%d")
    return None


def test_caller_completeness_checker_uses_capability(monkeypatch):
    """_get_latest_trade_date：能力日历 -> is_open==1 max -> YYYY-MM-DD"""
    import tradingagents.dataflows.capability as capability_pkg
    from tradingagents.dataflows.data_completeness_checker import (
        DataCompletenessChecker,
    )

    cal_df = pd.DataFrame(
        {
            "cal_date": pd.to_datetime(
                ["2024-09-30", "2024-10-01", "2024-10-04", "2024-10-08"]
            ),
            "is_open": [1, 0, 1, 1],
        }
    )
    calls = []

    def _stub(capability_id, **params):
        calls.append({"capability_id": capability_id, **params})
        return cal_df

    monkeypatch.setattr(capability_pkg, "query_capability_sync", _stub)

    checker = DataCompletenessChecker()
    assert checker._get_latest_trade_date("CN") == "2024-10-08"
    assert calls[0]["capability_id"] == "trade_cal"
    assert calls[0]["end_date"] == datetime.now().strftime("%Y-%m-%d")


def test_caller_completeness_checker_falls_back_on_error(monkeypatch):
    """能力抛异常 -> 回退方案（今天往前最近工作日）"""
    import tradingagents.dataflows.capability as capability_pkg
    from tradingagents.dataflows.data_completeness_checker import (
        DataCompletenessChecker,
    )

    def _stub(capability_id, **params):
        raise RuntimeError("网络中断")

    monkeypatch.setattr(capability_pkg, "query_capability_sync", _stub)

    checker = DataCompletenessChecker()
    assert checker._get_latest_trade_date("CN") == _expected_fallback()


def test_caller_completeness_checker_falls_back_on_empty(monkeypatch):
    """全源失败返回空日历 -> 回退方案"""
    import tradingagents.dataflows.capability as capability_pkg
    from tradingagents.dataflows.data_completeness_checker import (
        DataCompletenessChecker,
    )

    monkeypatch.setattr(
        capability_pkg,
        "query_capability_sync",
        lambda capability_id, **params: pd.DataFrame(
            columns=["exchange", "cal_date", "is_open"]
        ),
    )

    checker = DataCompletenessChecker()
    assert checker._get_latest_trade_date("CN") == _expected_fallback()


def test_caller_skips_non_cn_market(monkeypatch):
    """非 CN 市场：不调能力，直接走回退方案"""
    import tradingagents.dataflows.capability as capability_pkg
    from tradingagents.dataflows.data_completeness_checker import (
        DataCompletenessChecker,
    )

    calls = []

    def _stub(capability_id, **params):
        calls.append(capability_id)
        return pd.DataFrame()

    monkeypatch.setattr(capability_pkg, "query_capability_sync", _stub)

    checker = DataCompletenessChecker()
    result = checker._get_latest_trade_date("US")
    assert calls == []
    assert result == _expected_fallback()
