"""腾讯 ETF 日线数据。"""

from __future__ import annotations

import json
import math
import urllib.request


def fetch_tencent_etf_data(ticker: str, days: int = 60) -> str:
    """获取并格式化腾讯前复权日线。"""
    if not ticker.isdigit() or len(ticker) != 6:
        raise ValueError("ETF 代码必须是 6 位数字")
    symbol = ("sh" if ticker.startswith(("5", "6")) else "sz") + ticker
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={symbol},day,,,{days},qfq"
    request = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://gu.qq.com/"}
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)
    rows = payload.get("data", {}).get(symbol, {}).get("qfqday", [])
    if len(rows) < 20:
        raise RuntimeError(f"腾讯行情数据不足：仅 {len(rows)} 个交易日")
    return format_tencent_etf_data(ticker, rows)


def format_tencent_etf_data(ticker: str, rows: list[list[str]]) -> str:
    """将腾讯 K 线格式化为市场分析师可读报告。"""
    closes = [float(row[2]) for row in rows]
    highs = [float(row[3]) for row in rows]
    lows = [float(row[4]) for row in rows]
    volumes = [float(row[5]) for row in rows]
    returns = [closes[index] / closes[index - 1] - 1 for index in range(1, len(closes))]
    gains = [max(value, 0) for value in returns[-14:]]
    losses = [max(-value, 0) for value in returns[-14:]]
    average_loss = sum(losses) / len(losses)
    rsi = 100.0 if average_loss == 0 else 100 - 100 / (1 + (sum(gains) / len(gains)) / average_loss)
    recent_returns = returns[-20:]
    mean_return = sum(recent_returns) / len(recent_returns)
    volatility = math.sqrt(252) * math.sqrt(
        sum((value - mean_return) ** 2 for value in recent_returns) / (len(recent_returns) - 1)
    )
    true_ranges = [
        max(
            highs[index] - lows[index],
            abs(highs[index] - closes[index - 1]),
            abs(lows[index] - closes[index - 1]),
        )
        for index in range(1, len(rows))
    ]
    atr = sum(true_ranges[-14:]) / 14
    support = min(lows[-20:])
    resistance = max(highs[-20:])
    buy_zone = (support, support + atr * 0.35)
    sell_zone = (resistance - atr * 0.35, resistance)
    stop_loss = max(0.001, support - atr * 0.5)
    breakout = resistance + atr * 0.1
    metrics = {
        "ticker": ticker,
        "last_trade_date": rows[-1][0],
        "close": closes[-1],
        "daily_change_pct": round(returns[-1] * 100, 2),
        "five_day_change_pct": round((closes[-1] / closes[-6] - 1) * 100, 2),
        "twenty_day_change_pct": round((closes[-1] / closes[-21] - 1) * 100, 2),
        "MA5": round(sum(closes[-5:]) / 5, 4),
        "MA10": round(sum(closes[-10:]) / 10, 4),
        "MA20": round(sum(closes[-20:]) / 20, 4),
        "RSI14": round(rsi, 2),
        "ATR14": round(atr, 4),
        "support_20d": round(support, 4),
        "resistance_20d": round(resistance, 4),
        "reference_buy_zone": [round(value, 4) for value in buy_zone],
        "breakout_confirmation": round(breakout, 4),
        "reference_sell_zone": [round(value, 4) for value in sell_zone],
        "stop_loss_reference": round(stop_loss, 4),
        "annualized_volatility_20d_pct": round(volatility * 100, 2),
        "volume": int(volumes[-1]),
        "average_volume_5d": int(sum(volumes[-5:]) / 5),
    }
    lines = ["date,open,close,high,low,volume", *(",".join(row) for row in rows[-30:])]
    return (
        f"# {ticker} ETF 市场数据\n\n"
        f"数据源: 腾讯行情\n"
        f"指标: {json.dumps(metrics, ensure_ascii=False)}\n\n"
        f"最近30个交易日前复权日线:\n{chr(10).join(lines)}"
    )
