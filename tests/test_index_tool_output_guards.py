import asyncio
import importlib.util
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


def _load_module(relative_path: str, module_name: str):
    module_path = ROOT / relative_path
    module_spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert module_spec is not None and module_spec.loader is not None
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


def _make_index_daily_frame(days: int = 260) -> pd.DataFrame:
    rows = []
    for index in range(days):
        close = 3000 + index
        rows.append(
            {
                "trade_date": f"2024{(index // 28) + 1:02d}{(index % 28) + 1:02d}",
                "close": close,
                "high": close + 20,
                "low": close - 20,
                "pct_chg": 0.5,
            }
        )
    return pd.DataFrame(rows)


def test_market_environment_uses_actual_trade_date_and_omits_pe_pb(monkeypatch) -> None:
    module = _load_module("core/tools/index_tools.py", "index_tools_market_environment")

    class FakeProvider:
        async def get_index_dailybasic(self, ts_code: str, trade_date: str) -> pd.DataFrame:
            return pd.DataFrame([
                {"turnover_rate": 1.23, "total_mv": 1_500_000_000_000}
            ])

        async def get_index_daily(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
            return _make_index_daily_frame(30)

    async def fake_latest_trade_date(trade_date: str) -> str:
        return "20260410"

    monkeypatch.setattr(module, "_get_tushare_provider", lambda: FakeProvider())
    monkeypatch.setattr(module, "_get_latest_trade_date", fake_latest_trade_date)

    report = asyncio.run(module.get_market_environment("2026-04-11"))

    assert "2026-04-10" in report
    assert "PE:" not in report
    assert "PB:" not in report
    assert "20日年化波动率" in report
    assert "中等风险" not in report
    assert "高风险" not in report
    assert "低风险" not in report


def test_market_breadth_omits_activity_labels(monkeypatch) -> None:
    module = _load_module("core/tools/index_tools.py", "index_tools_market_breadth")

    class FakeProvider:
        async def get_daily_info(self, trade_date: str) -> pd.DataFrame:
            return pd.DataFrame(
                [
                    {"ts_code": "SH_MARKET", "amount": 9567.54, "vol": 250.00, "com_count": 2300},
                    {"ts_code": "SZ_MARKET", "amount": 13678.81, "vol": 296.68, "com_count": 3100},
                ]
            )

    async def fake_latest_trade_date(trade_date: str) -> str:
        return "20260410"

    monkeypatch.setattr(module, "_get_tushare_provider", lambda: FakeProvider())
    monkeypatch.setattr(module, "_get_latest_trade_date", fake_latest_trade_date)

    report = asyncio.run(module.get_market_breadth("2026-04-11"))

    assert "总成交额" in report
    assert "平均每家上市公司成交额" in report
    assert "市场活跃度" not in report
    assert "极度活跃" not in report


def test_identify_market_cycle_removes_operation_advice(monkeypatch) -> None:
    module = _load_module("core/tools/index_tools.py", "index_tools_market_cycle")

    class FakeProvider:
        async def get_index_daily(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
            return _make_index_daily_frame(260)

    async def fake_latest_trade_date(trade_date: str) -> str:
        return "20260410"

    monkeypatch.setattr(module, "_get_tushare_provider", lambda: FakeProvider())
    monkeypatch.setattr(module, "_get_latest_trade_date", fake_latest_trade_date)

    report = asyncio.run(module.identify_market_cycle("2026-04-11"))

    assert "2026-04-10" in report
    assert "操作建议" not in report
    assert "不代表趋势确认" in report
    assert "规则识别区间" in report
    assert "牛市阶段" not in report
    assert "熊市阶段" not in report
    assert "调整阶段" not in report


def test_north_flow_uses_actual_trade_date_in_report(monkeypatch) -> None:
    module = _load_module("core/tools/index_tools.py", "index_tools_north_flow")

    class FakeProvider:
        async def get_hsgt_moneyflow(self, start_date: str, end_date: str) -> pd.DataFrame:
            return pd.DataFrame(
                [
                    {"trade_date": "20260410", "hgt": 120000.0, "sgt": 80000.0},
                    {"trade_date": "20260409", "hgt": 100000.0, "sgt": 60000.0},
                ]
            )

    async def fake_latest_trade_date(trade_date: str) -> str:
        return "20260410"

    monkeypatch.setattr(module, "_get_tushare_provider", lambda: FakeProvider())
    monkeypatch.setattr(module, "_get_latest_trade_date", fake_latest_trade_date)

    report = asyncio.run(module.get_north_flow("2026-04-11", lookback_days=10))

    assert "📅 日期: 2026-04-10" in report
    assert "已切换到最近交易日 2026-04-10" in report
    assert "【资金情绪】" not in report
    assert "外资积极流入" not in report


def test_margin_trading_flags_anomalous_change_fields(monkeypatch) -> None:
    module = _load_module("core/tools/index_tools.py", "index_tools_margin_trading")

    class FakeProvider:
        async def get_margin_detail(self, start_date: str, end_date: str) -> pd.DataFrame:
            return pd.DataFrame(
                [
                    {"trade_date": "20260410", "exchange_id": "SSE", "rzye": 5000.00 * 100000000, "rqye": 40.00 * 100000000, "rzrqye": 5040.00 * 100000000},
                    {"trade_date": "20260410", "exchange_id": "SZSE", "rzye": 7000.00 * 100000000, "rqye": 70.00 * 100000000, "rzrqye": 7070.00 * 100000000},
                    {"trade_date": "20260410", "exchange_id": "BSE", "rzye": 1156.60 * 100000000, "rqye": 14.15 * 100000000, "rzrqye": 1170.75 * 100000000},
                    {"trade_date": "20260409", "exchange_id": "SSE", "rzye": 3500.00 * 100000000, "rqye": 45.00 * 100000000, "rzrqye": 3545.00 * 100000000},
                    {"trade_date": "20260409", "exchange_id": "SZSE", "rzye": 4800.00 * 100000000, "rqye": 60.00 * 100000000, "rzrqye": 4860.00 * 100000000},
                    {"trade_date": "20260409", "exchange_id": "BSE", "rzye": 700.00 * 100000000, "rqye": 15.00 * 100000000, "rzrqye": 715.00 * 100000000},
                    {"trade_date": "20260408", "exchange_id": "SSE", "rzye": 3200.00 * 100000000, "rqye": 40.00 * 100000000, "rzrqye": 3240.00 * 100000000},
                    {"trade_date": "20260408", "exchange_id": "SZSE", "rzye": 4200.00 * 100000000, "rqye": 55.00 * 100000000, "rzrqye": 4255.00 * 100000000},
                    {"trade_date": "20260408", "exchange_id": "BSE", "rzye": 600.00 * 100000000, "rqye": 15.00 * 100000000, "rzrqye": 615.00 * 100000000},
                    {"trade_date": "20260407", "exchange_id": "SSE", "rzye": 2800.00 * 100000000, "rqye": 35.00 * 100000000, "rzrqye": 2835.00 * 100000000},
                    {"trade_date": "20260407", "exchange_id": "SZSE", "rzye": 3600.00 * 100000000, "rqye": 50.00 * 100000000, "rzrqye": 3650.00 * 100000000},
                    {"trade_date": "20260407", "exchange_id": "BSE", "rzye": 600.00 * 100000000, "rqye": 15.00 * 100000000, "rzrqye": 615.00 * 100000000},
                    {"trade_date": "20260406", "exchange_id": "SSE", "rzye": 2400.00 * 100000000, "rqye": 30.00 * 100000000, "rzrqye": 2430.00 * 100000000},
                    {"trade_date": "20260406", "exchange_id": "SZSE", "rzye": 3000.00 * 100000000, "rqye": 45.00 * 100000000, "rzrqye": 3045.00 * 100000000},
                    {"trade_date": "20260406", "exchange_id": "BSE", "rzye": 600.00 * 100000000, "rqye": 15.00 * 100000000, "rzrqye": 615.00 * 100000000},
                ]
            )

    async def fake_latest_trade_date(trade_date: str) -> str:
        return "20260410"

    monkeypatch.setattr(module, "_get_tushare_provider", lambda: FakeProvider())
    monkeypatch.setattr(module, "_get_latest_trade_date", fake_latest_trade_date)

    report = asyncio.run(module.get_margin_trading("2026-04-11", lookback_days=10))

    assert "字段一致性检查" in report
    assert "变化字段可能存在口径差异或异常值" in report
    assert "暂不据此延伸解读杠杆方向" in report
    assert "【余额水平信号】" not in report
    assert "融资余额处于相对谨慎区间" not in report
    assert "【使用限制】" in report
    assert "当前仅可引用余额数值，不应依据异常变化字段判断资金方向" in report


def test_margin_trading_reports_missing_exchange_coverage(monkeypatch) -> None:
    module = _load_module("core/tools/index_tools.py", "index_tools_margin_trading_incomplete")

    class FakeProvider:
        async def get_margin_detail(self, start_date: str, end_date: str) -> pd.DataFrame:
            return pd.DataFrame(
                [
                    {"trade_date": "20260410", "exchange_id": "SSE", "rzye": 13156.60 * 100000000, "rqye": 124.15 * 100000000, "rzrqye": 13280.75 * 100000000},
                    {"trade_date": "20260409", "exchange_id": "SSE", "rzye": 13000.00 * 100000000, "rqye": 120.00 * 100000000, "rzrqye": 13120.00 * 100000000},
                    {"trade_date": "20260409", "exchange_id": "SZSE", "rzye": 12000.00 * 100000000, "rqye": 60.00 * 100000000, "rzrqye": 12060.00 * 100000000},
                    {"trade_date": "20260409", "exchange_id": "BSE", "rzye": 902.06 * 100000000, "rqye": 5.05 * 100000000, "rzrqye": 907.11 * 100000000},
                ]
            )

    async def fake_latest_trade_date(trade_date: str) -> str:
        return "20260410"

    monkeypatch.setattr(module, "_get_tushare_provider", lambda: FakeProvider())
    monkeypatch.setattr(module, "_get_latest_trade_date", fake_latest_trade_date)

    report = asyncio.run(module.get_margin_trading("2026-04-11", lookback_days=10))

    assert "【数据完整性】" in report
    assert "数据状态: 不完整" in report
    assert "已返回交易所: SSE" in report
    assert "缺失交易所: SZSE、BSE" in report
    assert "当前数据仅覆盖部分交易所，不代表 A 股全市场两融口径" in report
    assert "不应据此判断两融余额水平、单日变化或杠杆资金方向" in report
    assert "融资异常" not in report
    assert "【今日两融余额】" not in report
    assert "【余额水平信号】" not in report


def test_index_technical_returns_rule_tags_without_summary_judgment(monkeypatch) -> None:
    module = _load_module("core/tools/index_tools.py", "index_tools_technical")

    class FakeProvider:
        async def get_index_daily(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
            return _make_index_daily_frame(120)

    async def fake_latest_trade_date(trade_date: str) -> str:
        return "20260410"

    monkeypatch.setattr(module, "_get_tushare_provider", lambda: FakeProvider())
    monkeypatch.setattr(module, "_get_latest_trade_date", fake_latest_trade_date)

    report = asyncio.run(module.get_index_technical("2026-04-11", lookback_days=60))

    assert "【指标规则标签】" in report
    assert "偏上规则标签数量" in report
    assert "偏下规则标签数量" in report
    assert "不等同于市场结论" in report
    assert "【技术面综合】" not in report
    assert "技术面偏多，偏多特征占优" not in report
    assert "技术面偏空，偏弱特征占优" not in report
    assert "技术面中性" not in report
    assert "指标看多" not in report
    assert "指标看空" not in report
    assert "多方占优" not in report
    assert "空方占优" not in report
    assert "底部金叉形成" not in report
    assert "高位金叉" not in report


def test_limit_stats_uses_neutral_distribution_wording(monkeypatch) -> None:
    module = _load_module("core/tools/index_tools.py", "index_tools_limit_stats")

    class FakeProvider:
        async def get_daily_stats(self, trade_date: str):
            return {
                "up_count": 3977,
                "up_ratio": 72.4,
                "down_count": 1397,
                "down_ratio": 25.4,
                "flat_count": 121,
                "up_gt5": 244,
                "up_3_5": 324,
                "down_gt5": 55,
                "down_3_5": 111,
            }

        async def get_limit_list(self, trade_date: str) -> pd.DataFrame:
            up_rows = [{"limit": "U", "up_stat": "2"} for _ in range(17)]
            up_rows.extend({"limit": "U", "up_stat": "1"} for _ in range(42))
            down_rows = [{"limit": "D", "up_stat": "0"} for _ in range(8)]
            return pd.DataFrame(up_rows + down_rows)

    async def fake_latest_trade_date(trade_date: str) -> str:
        return "20260410"

    monkeypatch.setattr(module, "_get_tushare_provider", lambda: FakeProvider())
    monkeypatch.setattr(module, "_get_latest_trade_date", fake_latest_trade_date)

    report = asyncio.run(module.get_limit_stats("2026-04-11"))

    assert "涨幅居前个股数量明显多于跌幅居前个股" in report
    assert "赚钱效应强" not in report
    assert "【市场情绪】" not in report
    assert "极度乐观" not in report
    assert "偏向乐观" not in report
    assert "偏向悲观" not in report
    assert "【涨跌停统计】" in report
    assert "  • 涨停: 59 家" in report
    assert "  • 跌停: 8 家" in report
    assert "  • 连板: 17 家" in report
    assert "【涨跌停统计（汇总口径）】" not in report
    assert "【涨跌停统计（明细口径）】" not in report
    assert "【口径差异摘要】" not in report
    assert "汇总口径" not in report
    assert "其中涨停家数" not in report