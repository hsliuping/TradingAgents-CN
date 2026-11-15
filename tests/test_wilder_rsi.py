import asyncio
import importlib.util
import re
from pathlib import Path

import pandas as pd
import pytest

pytest.importorskip("fin_primitives")

ROOT = Path(__file__).resolve().parents[1]


def _load_module(relative_path: str, module_name: str):
    module_path = ROOT / relative_path
    module_spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert module_spec is not None and module_spec.loader is not None
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


def _closes(days: int) -> list:
    # 确定性的锯齿走势，涨跌幅不对称，保证 SMA RSI 与 Wilder RSI 明显不同
    closes = [3000.0]
    for i in range(1, days):
        step = 13.0 if i % 3 else -21.0
        if i % 7 == 0:
            step = -34.0
        closes.append(closes[-1] + step)
    return closes


def _wilder_reference(closes: list, period: int = 14) -> float:
    """Wilder (1978) 原始算法：首个均值为前 period 个涨跌幅的简单平均，之后递推平滑。"""
    deltas = [b - a for a, b in zip(closes, closes[1:])]
    gains = [max(d, 0.0) for d in deltas]
    losses = [max(-d, 0.0) for d in deltas]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for g, l in zip(gains[period:], losses[period:]):
        avg_gain = (avg_gain * (period - 1) + g) / period
        avg_loss = (avg_loss * (period - 1) + l) / period
    return 100 - 100 / (1 + avg_gain / avg_loss)


def _sma_rsi(closes: list, period: int = 14) -> float:
    s = pd.Series(closes).diff()
    gain = s.where(s > 0, 0).rolling(period).mean().iloc[-1]
    loss = (-s.where(s < 0, 0)).rolling(period).mean().iloc[-1]
    return 100 - 100 / (1 + gain / loss)


def test_index_technical_rsi_matches_wilder_reference(monkeypatch) -> None:
    module = _load_module("core/tools/index_tools.py", "index_tools_wilder_rsi")
    closes = _closes(80)
    frame = pd.DataFrame(
        {
            "trade_date": [f"2024{(i // 28) + 1:02d}{(i % 28) + 1:02d}" for i in range(len(closes))],
            "close": closes,
            "high": [c + 20 for c in closes],
            "low": [c - 20 for c in closes],
            "pct_chg": 0.5,
        }
    )

    class FakeProvider:
        async def get_index_daily(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
            return frame

    async def fake_latest_trade_date(trade_date: str) -> str:
        return "20260410"

    monkeypatch.setattr(module, "_get_tushare_provider", lambda: FakeProvider())
    monkeypatch.setattr(module, "_get_latest_trade_date", fake_latest_trade_date)

    report = asyncio.run(module.get_index_technical("2026-04-11", lookback_days=60))
    reported = float(re.search(r"RSI\(14\): ([\d.]+)", report).group(1))

    expected = _wilder_reference(closes)
    assert reported == pytest.approx(expected, abs=0.006)
    # 旧的 14 日简单均值 RSI 与 Wilder 值相差明显
    assert abs(_sma_rsi(closes) - expected) > 1.0


def _hk_provider(module):
    provider = object.__new__(module.HKStockProvider)
    provider.get_stock_info = lambda symbol: {"name": "测试港股"}
    return provider


def _hk_frame(closes: list) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Date": pd.date_range("2024-01-02", periods=len(closes)),
            "Open": closes,
            "High": [c + 5 for c in closes],
            "Low": [c - 5 for c in closes],
            "Close": closes,
            "Volume": 1_000_000,
        }
    )


def test_hk_rsi_matches_wilder_reference() -> None:
    module = _load_module("tradingagents/dataflows/providers/hk/hk_stock.py", "hk_stock_wilder_rsi")
    closes = _closes(60)

    text = _hk_provider(module).format_stock_data("0700.HK", _hk_frame(closes), "2024-01-02", "2024-03-01")
    reported = float(re.search(r"RSI\(14\): ([\d.]+)", text).group(1))

    assert reported == pytest.approx(_wilder_reference(closes), abs=0.006)


def test_hk_rsi_not_reported_during_warmup() -> None:
    # 旧实现使用 rolling(14, min_periods=1)，第 2 根K线起就输出 RSI
    module = _load_module("tradingagents/dataflows/providers/hk/hk_stock.py", "hk_stock_wilder_rsi_warmup")
    closes = _closes(10)

    text = _hk_provider(module).format_stock_data("0700.HK", _hk_frame(closes), "2024-01-02", "2024-01-11")

    assert "RSI(14):" not in text
    assert "数据不足，无法计算RSI" in text


def test_wilder_rsi_skips_missing_closes() -> None:
    module = _load_module("tradingagents/dataflows/providers/hk/hk_stock.py", "hk_stock_wilder_rsi_nan")
    closes = _closes(40)
    series = pd.Series(closes[:20] + [float("nan")] + closes[20:])

    rsi = module._wilder_rsi(series, 14)

    assert pd.isna(rsi.iloc[20])
    assert rsi.iloc[-1] == pytest.approx(_wilder_reference(closes), abs=1e-9)
