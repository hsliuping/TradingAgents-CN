"""数据能力注册机制 — index_daily 能力测试

包含（接入规约：没有字段对齐测试不许注册）：
1. 注册校验：双源同一 Schema、akshare 映射目标全在标准字段集合、grain 声明一致、
   tushare 列名已是标准名（field_mapping={} 直通）
2. 双源字段对齐（mock，无网络）：tushare 标准列 / akshare 中文列映射后标准字段
   集合与取值一致（含成交额 元->千元 单位归一）
3. facade 降级语义（真实 index_daily 条目 + fake provider）：tushare 失败 ->
   akshare 接管；成功空数据不降级
4. akshare 适配器契约：ts_code 去后缀、日期归一 YYYYMMDD、成交额 /1000、
   trade_date 降序、失败返回 None、成功空数据返回空 DataFrame、不可用返回 None
5. 工具接入（mock facade）：china_market_overview 输出换算/来源/日期回退标注
   与 NaN 容错、index_tools._get_latest_trade_date 经能力取最新交易日
6. b3 批次：index_tools 四个分析函数（trend/cycle/technical/environment）
   经能力取数——降序返回 + 函数内升序排序语义、调用面全部收敛到 index_daily

设计文档：docs/05-design/v4.0/data-architecture-problems-and-optimization.md 5.4
"""

import asyncio
import logging
import sys
import types

import pandas as pd
import pytest

import tradingagents.dataflows.providers.china.akshare  # noqa: F401 —— import 即注册
import tradingagents.dataflows.providers.china.tushare  # noqa: F401
from tradingagents.dataflows.capability import facade as facade_mod
from tradingagents.dataflows.capability.facade import get_data_facade
from tradingagents.dataflows.capability.registry import registry
from tradingagents.dataflows.capability.schema import GRAIN_INDEX_DAILY

TS_RAW_ROW = {
    "ts_code": "000001.SH",
    "trade_date": "20260105",
    "open": 3200.0,
    "high": 3260.0,
    "low": 3190.0,
    "close": 3250.0,
    "pre_close": 3200.0,
    "change": 50.0,
    "pct_chg": 1.56,
    "vol": 350000000.0,      # 手（tushare 原始单位）
    "amount": 400000000.0,   # 千元（tushare 原始单位）
}

# akshare 适配器返回的原始行（东财中文列；成交额已由适配器 /1000 归一为千元）
AK_RAW_ROW = {
    "ts_code": "000001.SH",
    "日期": "20260105",
    "开盘": 3200.0,
    "收盘": 3250.0,
    "最高": 3260.0,
    "最低": 3190.0,
    "成交量": 350000000.0,   # 手
    "成交额": 400000000.0,   # 千元（元 /1000 后）
    "振幅": 2.19,
    "涨跌幅": 1.56,
    "涨跌额": 50.0,
    "换手率": 0.85,
}


# ---------------------------------------------------------------- 注册校验


def test_registration_dual_source_same_schema_and_grain():
    """双源挂同一 Schema；tushare 列名直通（field_mapping={}）；grain 声明一致"""
    ts_entry = registry.get_entry("index_daily", "tushare")
    ak_entry = registry.get_entry("index_daily", "akshare")
    assert ts_entry.schema is ak_entry.schema
    assert ts_entry.field_mapping == {}
    assert ts_entry.schema.grain == GRAIN_INDEX_DAILY
    assert ak_entry.schema.grain == GRAIN_INDEX_DAILY


def test_akshare_registration_mapping_targets_in_schema():
    """akshare 映射目标全部是 Schema 标准字段，且参数签名接受 Schema 全部参数"""
    import inspect

    entry = registry.get_entry("index_daily", "akshare")
    standard = set(entry.schema.standard_field_names())
    for raw_name, std_name in entry.field_mapping.items():
        assert std_name in standard, (
            f"映射目标 '{std_name}' 不在标准字段集合 {sorted(standard)}"
        )
    func_params = set(inspect.signature(entry.func).parameters)
    for param in entry.schema.params:
        assert param.name in func_params, f"Schema 参数 {param.name} 不在适配方法签名中"


# ---------------------------------------------------------------- 双源字段对齐（mock）


def test_dual_source_field_alignment_index_daily():
    """tushare 标准列 / akshare 中文列映射后标准字段一致（列集合 + 关键取值）"""
    ts_entry = registry.get_entry("index_daily", "tushare")
    ak_entry = registry.get_entry("index_daily", "akshare")
    handle = get_data_facade().get_capability("index_daily")
    out_columns = ts_entry.schema.standard_field_names() + ["source", "quality"]

    ts_std = handle._standardize(pd.DataFrame([TS_RAW_ROW]), ts_entry, out_columns)
    ak_std = handle._standardize(pd.DataFrame([AK_RAW_ROW]), ak_entry, out_columns)

    # 字段名一致性：映射后列集合与 Schema 标准列一致
    assert ts_std.columns.tolist() == out_columns
    assert ak_std.columns.tolist() == out_columns

    # 必填字段（ts_code/trade_date/close）齐全 -> quality=ok；
    # akshare 缺 pre_close 为非必填缺失，不扣 quality
    assert ts_std.iloc[0]["quality"] == "ok"
    assert ak_std.iloc[0]["quality"] == "ok"

    # 取值一致性：缺失值（NaN/pd.NA）归一为 None 后比较
    def _norm(value):
        try:
            if pd.isna(value):
                return None
        except (TypeError, ValueError):
            pass
        return value

    for field in ("ts_code", "trade_date", "open", "high", "low", "close",
                  "change", "pct_chg", "vol", "amount"):
        ts_val = _norm(ts_std.iloc[0][field])
        ak_val = _norm(ak_std.iloc[0][field])
        assert ts_val == ak_val, f"标准字段 {field} 双源取值不一致: {ts_val!r} != {ak_val!r}"

    # akshare 东财无昨收列 -> pre_close 落 NaN（非必填）
    assert pd.isna(ak_std.iloc[0]["pre_close"])
    assert ts_std.iloc[0]["pre_close"] == 3200.0


# ---------------------------------------------------------------- facade 降级语义


class _FakeTushareProvider:
    def __init__(self, result):
        self._result = result
        self.logger = logging.getLogger("ut_tushare")

    def is_available(self):
        return True

    async def get_index_daily(self, ts_code=None, start_date=None,
                              end_date=None, use_cache=True):
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


class _FakeAKShareProvider:
    def __init__(self, result):
        self._result = result
        self.logger = logging.getLogger("ut_akshare")

    def is_available(self):
        return True

    async def get_index_daily_capability(self, ts_code=None,
                                         start_date=None, end_date=None):
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


def _fixed_order(monkeypatch, order):
    monkeypatch.setattr(
        facade_mod.CapabilityHandle,
        "_resolve_source_order",
        lambda self, registered: [s for s in order if s in registered],
    )


def _install_fake_providers(monkeypatch, ts_result, ak_result):
    monkeypatch.setattr(
        facade_mod, "_PROVIDER_FACTORIES",
        {
            "tushare": lambda: _FakeTushareProvider(ts_result),
            "akshare": lambda: _FakeAKShareProvider(ak_result),
        },
    )


def _install_fake_ak_module(monkeypatch, hist_impl):
    """注入 fake akshare 模块（适配器内部 import akshare，需拦截真网络）"""
    monkeypatch.setitem(sys.modules, "akshare",
                        types.SimpleNamespace(index_zh_a_hist=hist_impl))


def test_facade_tushare_failure_degrades_to_akshare(monkeypatch):
    """tushare 请求失败 -> akshare 接管（真实 index_daily 条目走完整门面链路）"""
    _fixed_order(monkeypatch, ["tushare", "akshare"])
    _install_fake_providers(
        monkeypatch, RuntimeError("模拟 tushare 请求失败"), None,
    )
    _install_fake_ak_module(monkeypatch, lambda **kw: pd.DataFrame([
        # 东财中文列原生升序、成交额单位元
        {"日期": "2026-01-05", "开盘": 3200.0, "收盘": 3250.0, "最高": 3260.0,
         "最低": 3190.0, "成交量": 350000000.0, "成交额": 400000000000.0,
         "涨跌幅": 1.56, "涨跌额": 50.0},
    ]))

    df = asyncio.run(get_data_facade().get_capability("index_daily").query(
        ts_code="000001.SH", start_date="20251206", end_date="20260105"))

    assert len(df) == 1
    assert df.iloc[0]["source"] == "akshare"
    # 中文列映射后读同一套标准字段
    assert df.iloc[0]["close"] == 3250.0
    assert df.iloc[0]["pct_chg"] == 1.56
    assert df.iloc[0]["amount"] == pytest.approx(400000000.0)  # 元 /1000 -> 千元


def test_facade_empty_success_does_not_degrade(monkeypatch):
    """成功但空数据 -> 不降级（P5 教训：空数据不漂移为另一源数据）"""
    _fixed_order(monkeypatch, ["tushare", "akshare"])
    ak_called = {"v": False}

    class _AkSpy(_FakeAKShareProvider):
        async def get_index_daily_capability(self, ts_code=None,
                                             start_date=None, end_date=None):
            ak_called["v"] = True
            return self._result

    monkeypatch.setattr(
        facade_mod, "_PROVIDER_FACTORIES",
        {
            "tushare": lambda: _FakeTushareProvider(pd.DataFrame()),
            "akshare": lambda: _AkSpy(pd.DataFrame([AK_RAW_ROW])),
        },
    )

    df = asyncio.run(get_data_facade().get_capability("index_daily").query(
        ts_code="000001.SH", start_date="20251206", end_date="20260105"))

    assert df.empty
    assert ak_called["v"] is False, "空数据不应触发降级"
    assert (df["source"] == "tushare").all()


# ---------------------------------------------------------------- akshare 适配器契约


def _fake_akshare_instance(monkeypatch, hist_impl):
    """绕过 AKShareProvider.__init__（避免网络初始化），注入 fake akshare 模块"""
    import tradingagents.dataflows.providers.china.akshare as ak_mod

    inst = object.__new__(ak_mod.AKShareProvider)
    inst.logger = logging.getLogger("ut_akshare")
    monkeypatch.setattr(inst, "is_available", lambda: True)
    monkeypatch.setitem(sys.modules, "akshare",
                        types.SimpleNamespace(index_zh_a_hist=hist_impl))
    return inst


def _ak_entry_func():
    return registry.get_entry("index_daily", "akshare").func


@pytest.mark.asyncio
async def test_akshare_adapter_conversion_and_order(monkeypatch):
    """ts_code 去后缀、日期归一 YYYYMMDD、成交额 元->千元、trade_date 降序"""
    seen = {}

    def hist_impl(**kwargs):
        seen.update(kwargs)
        # 东财原生升序（旧 -> 新）
        return pd.DataFrame([
            {"日期": "2026-01-02", "开盘": 3180.0, "收盘": 3200.0, "最高": 3210.0,
             "最低": 3170.0, "成交量": 340000000.0, "成交额": 390000000000.0,
             "涨跌幅": 0.10, "涨跌额": 3.0},
            {"日期": "2026-01-05", "开盘": 3200.0, "收盘": 3250.0, "最高": 3260.0,
             "最低": 3190.0, "成交量": 350000000.0, "成交额": 400000000000.0,
             "涨跌幅": 1.56, "涨跌额": 50.0},
        ])

    inst = _fake_akshare_instance(monkeypatch, hist_impl)
    df = await _ak_entry_func()(inst, ts_code="000001.SH",
                                start_date="20260101", end_date="20260105")

    assert seen["symbol"] == "000001"        # ts_code 去后缀
    assert seen["period"] == "daily"
    assert seen["start_date"] == "20260101"
    assert seen["end_date"] == "20260105"

    assert df.iloc[0]["ts_code"] == "000001.SH"   # 标准列直通
    assert df.iloc[0]["日期"] == "20260105"        # 日期归一 YYYYMMDD
    # 排序约定：trade_date 降序（最新在前）
    assert df.iloc[0]["日期"] > df.iloc[-1]["日期"]
    # 成交额 元 -> 千元（/1000）
    assert df.iloc[0]["成交额"] == pytest.approx(400000000.0)


@pytest.mark.asyncio
async def test_akshare_adapter_empty_returns_empty_df(monkeypatch):
    """成功但无数据 -> 空 DataFrame（facade 不降级）"""
    inst = _fake_akshare_instance(monkeypatch, lambda **kw: pd.DataFrame())
    df = await _ak_entry_func()(inst, ts_code="000001.SH",
                                start_date="20260101", end_date="20260105")
    assert df is not None and df.empty


@pytest.mark.asyncio
async def test_akshare_adapter_failure_returns_none(monkeypatch):
    """请求失败 -> None（facade 降级到下一源）"""
    def boom(**kw):
        raise RuntimeError("模拟东财接口失败")

    inst = _fake_akshare_instance(monkeypatch, boom)
    assert await _ak_entry_func()(inst, ts_code="000001.SH") is None


@pytest.mark.asyncio
async def test_akshare_adapter_unavailable_returns_none(monkeypatch):
    """源不可用 -> None（facade 降级到下一源）"""
    import tradingagents.dataflows.providers.china.akshare as ak_mod

    inst = object.__new__(ak_mod.AKShareProvider)
    inst.logger = logging.getLogger("ut_akshare")
    monkeypatch.setattr(inst, "is_available", lambda: False)
    assert await _ak_entry_func()(inst, ts_code="000001.SH") is None


# ---------------------------------------------------------------- 工具接入


def _market_overview_module():
    import core.tools.implementations.market.china_market_overview as omo
    return omo


def test_china_market_overview_output(monkeypatch):
    """工具输出：单位换算（手->万手、千元->亿元）、涨跌格式、日期回退与来源标注"""
    omo = _market_overview_module()

    async def fake_query(ts_code, start_date, end_date):
        return pd.DataFrame([{
            "ts_code": ts_code, "trade_date": "20260103", "close": 3250.0,
            "change": 50.0, "pct_chg": 1.56, "vol": 350000000.0,
            "amount": 400000000.0, "source": "akshare", "quality": "ok",
        }])

    monkeypatch.setattr(omo, "_query_index_daily", fake_query)
    report = omo.get_china_market_overview.invoke({"curr_date": "2026-01-05"})

    assert "上证指数" in report
    assert "+50.00 (+1.56%)" in report
    # vol 手 -> 万手（/1e4）
    assert "35000.00 万手" in report
    # amount 千元 -> 亿元（/1e5）
    assert "4000.00 亿元" in report
    # 日期回退标注（请求日无数据，用最近交易日）
    assert "使用最近交易日 2026-01-03" in report
    # 来源标注取实际命中源
    assert "akshare（DataFacade 自动降级）" in report


def test_china_market_overview_nan_fields(monkeypatch):
    """可选字段为 NaN 时输出'暂无数据'而非 nan 字样"""
    omo = _market_overview_module()

    async def fake_query(ts_code, start_date, end_date):
        return pd.DataFrame([{
            "ts_code": ts_code, "trade_date": "20260103", "close": 3250.0,
            "change": float("nan"), "pct_chg": float("nan"),
            "vol": float("nan"), "amount": float("nan"),
            "source": "tushare", "quality": "partial",
        }])

    monkeypatch.setattr(omo, "_query_index_daily", fake_query)
    report = omo.get_china_market_overview.invoke({"curr_date": "2026-01-05"})

    assert "nan" not in report.lower()
    assert "- **涨跌**: 暂无数据" in report
    assert "- **成交量**: 暂无数据" in report
    assert "- **成交额**: 暂无数据" in report


def test_china_market_overview_empty(monkeypatch):
    """查询窗口无数据 -> 各指数'暂无数据'，不抛异常"""
    omo = _market_overview_module()

    async def fake_query(ts_code, start_date, end_date):
        return pd.DataFrame()

    monkeypatch.setattr(omo, "_query_index_daily", fake_query)
    report = omo.get_china_market_overview.invoke({"curr_date": "2026-01-05"})

    assert report.count("暂无数据") >= 4
    assert "多数据源（DataFacade 自动降级）" in report


def test_index_tools_latest_trade_date_via_facade(monkeypatch):
    """index_tools._get_latest_trade_date 经 DataFacade 取最新交易日（降序 iloc[0]）"""
    import core.tools.index_tools as idx

    seen = {}

    async def fake_query(capability_id, **params):
        seen["capability_id"] = capability_id
        seen["params"] = params
        return pd.DataFrame([
            {"trade_date": "20260105", "close": 3250.0},
            {"trade_date": "20260102", "close": 3200.0},
        ])

    monkeypatch.setattr(idx, "_query_capability", fake_query)
    result = asyncio.run(idx._get_latest_trade_date("2026-01-05"))

    assert seen["capability_id"] == "index_daily"
    assert seen["params"]["ts_code"] == "000001.SH"
    assert result == "20260105"


def test_index_tools_latest_trade_date_empty_fallback(monkeypatch):
    """窗口内无数据 -> 回退原始请求日期，不抛异常"""
    import core.tools.index_tools as idx

    async def fake_query(capability_id, **params):
        return pd.DataFrame()

    monkeypatch.setattr(idx, "_query_capability", fake_query)
    result = asyncio.run(idx._get_latest_trade_date("2026-01-05"))
    assert result == "20260105"


# ---------------------------------------------------------------- b3 批次：index_tools 分析函数迁移


def _ascending_dates(n, end_date="20260105"):
    """生成 n 个升序日期字符串（YYYYMMDD），结束于 end_date（含）"""
    from datetime import datetime as _dt
    from datetime import timedelta as _td

    end = _dt.strptime(end_date, "%Y%m%d")
    return [(end - _td(days=n - 1 - i)).strftime("%Y%m%d") for i in range(n)]


def _trend_up_series(ts_code, n=70):
    """单调上涨指数日线（升序生成 -> 降序返回，模拟 facade 降序契约）"""
    rows, prev = [], 3200.0
    for i, d in enumerate(_ascending_dates(n)):
        close = 3200.0 + i * 10.0
        rows.append({
            "ts_code": ts_code, "trade_date": d,
            "open": close - 10.0, "high": close + 10.0, "low": close - 20.0,
            "close": close, "pre_close": prev,
            "change": close - prev, "pct_chg": (close - prev) / prev * 100,
            "vol": 3.5e8, "amount": 4.0e8,
        })
        prev = close
    return pd.DataFrame(rows).sort_values("trade_date", ascending=False).reset_index(drop=True)


def _install_capability_stub(monkeypatch, series_by_code, extra_frames=None):
    """monkeypatch idx._query_capability：按 ts_code/start/end 过滤返回降序数据，并记录调用

    extra_frames: capability_id -> DataFrame，非 index_daily 能力的固定返回
    （如 index_dailybasic 单日快照，随批次 4a 已迁移至能力取数）
    """
    import core.tools.index_tools as idx
    calls = []
    extra_frames = extra_frames or {}

    async def fake_query(capability_id, **params):
        calls.append({"capability_id": capability_id, **params})
        if capability_id in extra_frames:
            return extra_frames[capability_id]
        if capability_id != "index_daily":
            return pd.DataFrame()
        df = series_by_code.get(params.get("ts_code"))
        if df is None or df.empty:
            return pd.DataFrame()
        start, end = params.get("start_date"), params.get("end_date")
        mask = pd.Series(True, index=df.index)
        if start:
            mask &= df["trade_date"] >= start
        if end:
            mask &= df["trade_date"] <= end
        return df[mask].reset_index(drop=True)

    monkeypatch.setattr(idx, "_query_capability", fake_query)
    return calls


def test_get_index_trend_via_capability(monkeypatch):
    """5 指数循环经能力取数；降序数据 + 函数内升序排序 -> 涨跌幅/均线计算正确"""
    import core.tools.index_tools as idx

    series = {code: _trend_up_series(code) for code in idx.MAIN_INDICES}
    calls = _install_capability_stub(monkeypatch, series)

    report = asyncio.run(idx.get_index_trend("2026-01-05"))

    assert calls, "应经 _query_capability 取数"
    assert {c["capability_id"] for c in calls} == {"index_daily"}
    queried_codes = {c["ts_code"] for c in calls if c.get("ts_code")}
    assert queried_codes == set(idx.MAIN_INDICES)

    for name in idx.MAIN_INDICES.values():
        assert name in report

    # 升序第 -5 行 close=3850、最新 3890 -> 5 日涨跌幅 +1.04%（若降序被当升序用，此值完全不同）
    assert "+1.04%" in report
    # 单调上涨 -> close > MA5 > MA20 > MA60 -> 多头排列
    assert "多头排列" in report


def test_identify_market_cycle_via_capability(monkeypatch):
    """一年窗口经能力取数；单调上涨 -> 年内位置 100%、短中期均线上方区间"""
    import core.tools.index_tools as idx

    calls = _install_capability_stub(
        monkeypatch, {"000001.SH": _trend_up_series("000001.SH")})

    report = asyncio.run(idx.identify_market_cycle("2026-01-05"))

    assert {c["capability_id"] for c in calls} == {"index_daily"}
    assert "数据不足" not in report
    # 年内位置按 high/low 列：(3890-3180)/(3900-3180) = 98.6%
    assert "年内位置: 98.6%" in report
    assert "短中期均线上方区间" in report


def test_get_index_technical_via_capability(monkeypatch):
    """技术指标经能力取数；30+ 行 -> MACD/RSI/KDJ 三段输出且无 NaN 字样"""
    import core.tools.index_tools as idx

    calls = _install_capability_stub(
        monkeypatch, {"000001.SH": _trend_up_series("000001.SH")})

    report = asyncio.run(idx.get_index_technical("2026-01-05"))

    assert {c["capability_id"] for c in calls} == {"index_daily"}
    assert "数据不足" not in report
    for section in ("MACD 指标", "RSI 指标", "KDJ 指标"):
        assert section in report
    assert "nan" not in report.lower()


def test_get_market_environment_via_capability(monkeypatch):
    """波动率与 index_dailybasic 单日快照均经能力取数（批次 4a 迁移完成）"""
    import core.tools.index_tools as idx

    calls = _install_capability_stub(
        monkeypatch, {"000001.SH": _trend_up_series("000001.SH")},
        extra_frames={
            "index_dailybasic": pd.DataFrame([{
                "turnover_rate": 0.85,
                "total_mv": 4.5e9,  # 万元 -> /1e8 = 45 万亿
            }]),
        },
    )

    report = asyncio.run(idx.get_market_environment("2026-01-05"))

    assert {c["capability_id"] for c in calls} == {"index_daily", "index_dailybasic"}
    assert "45.00 万亿" in report
    assert "0.85%" in report
    assert "20日年化波动率" in report
