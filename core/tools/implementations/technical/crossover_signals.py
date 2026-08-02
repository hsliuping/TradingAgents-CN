"""
技术指标交叉信号检测工具

检测以下交叉信号：
1. 均线金叉/死叉（MA5/10/20/60 组合）
2. MACD 金叉/死叉 + 零轴穿越
3. KDJ 金叉/死叉 + 超买超卖区
4. 价格-均线交叉（突破/跌破）

所有信号基于纯数学计算，无需 LLM 参与。
"""

import datetime
import json
import logging
from typing import Annotated, Optional

import numpy as np
import pandas as pd
from langchain_core.tools import tool

from core.tools.base import register_tool

logger = logging.getLogger(__name__)


# ============================================================
#  辅助函数
# ============================================================

def _ma(close: pd.Series, n: int) -> pd.Series:
    return close.rolling(window=n, min_periods=n).mean()


def _ema(close: pd.Series, n: int) -> pd.Series:
    return close.ewm(span=n, adjust=False).mean()


def _cross_above(series_a: pd.Series, series_b: pd.Series) -> pd.Series:
    """series_a 上穿 series_b"""
    return (series_a > series_b) & (series_a.shift(1) <= series_b.shift(1))


def _cross_below(series_a: pd.Series, series_b: pd.Series) -> pd.Series:
    """series_a 下穿 series_b"""
    return (series_a < series_b) & (series_a.shift(1) >= series_b.shift(1))


# ============================================================
#  MACD 计算
# ============================================================

def _macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    dif = _ema(close, fast) - _ema(close, slow)
    dea = _ema(dif, signal)
    hist = dif - dea
    return dif, dea, hist


# ============================================================
#  KDJ 计算
# ============================================================

def _kdj(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 9):
    lowest = low.rolling(window=n, min_periods=n).min()
    highest = high.rolling(window=n, min_periods=n).max()
    rsv = (close - lowest) / (highest - lowest) * 100
    rsv = rsv.replace([np.inf, -np.inf], np.nan)

    k = pd.Series(np.nan, index=close.index)
    d = pd.Series(np.nan, index=close.index)
    last_k, last_d = 50.0, 50.0
    for i in range(len(close)):
        rv = rsv.iloc[i]
        if np.isnan(rv):
            continue
        curr_k = last_k * 2 / 3 + rv / 3
        curr_d = last_d * 2 / 3 + curr_k / 3
        k.iloc[i] = curr_k
        d.iloc[i] = curr_d
        last_k, last_d = curr_k, curr_d
    j = 3 * k - 2 * d
    return k, d, j


# ============================================================
#  信号检测
# ============================================================

def _detect_ma_crossovers(df: pd.DataFrame) -> list[dict]:
    """检测均线金叉/死叉"""
    signals = []
    ma_pairs = [
        ("MA5", 5, "MA10", 10),
        ("MA5", 5, "MA20", 20),
        ("MA5", 5, "MA60", 60),
        ("MA10", 10, "MA20", 20),
        ("MA10", 10, "MA60", 60),
        ("MA20", 20, "MA60", 60),
    ]
    close = df["close"]

    # 预计算所有均线
    ma_cache = {}
    for _, n, _, _ in ma_pairs:
        if n not in ma_cache:
            ma_cache[n] = _ma(close, n)
    for _, _, _, n in ma_pairs:
        if n not in ma_cache:
            ma_cache[n] = _ma(close, n)

    for short_name, short_n, long_name, long_n in ma_pairs:
        short_ma = ma_cache[short_n]
        long_ma = ma_cache[long_n]

        golden = _cross_above(short_ma, long_ma)
        death = _cross_below(short_ma, long_ma)

        for idx in golden[golden].index:
            i = df.index.get_loc(idx)
            signals.append({
                "date": _get_date(df, i),
                "type": "MA金叉",
                "pair": f"{short_name}↗{long_name}",
                "direction": "bullish",
                "price": float(close.iloc[i]),
                "short_ma": round(float(short_ma.iloc[i]), 2),
                "long_ma": round(float(long_ma.iloc[i]), 2),
                "strength": _calc_strength(df, i, 20),
            })
        for idx in death[death].index:
            i = df.index.get_loc(idx)
            signals.append({
                "date": _get_date(df, i),
                "type": "MA死叉",
                "pair": f"{short_name}↘{long_name}",
                "direction": "bearish",
                "price": float(close.iloc[i]),
                "short_ma": round(float(short_ma.iloc[i]), 2),
                "long_ma": round(float(long_ma.iloc[i]), 2),
                "strength": _calc_strength(df, i, 20),
            })
    return signals


def _detect_macd_crossovers(df: pd.DataFrame) -> list[dict]:
    """检测 MACD 金叉/死叉 + 零轴穿越"""
    close = df["close"]
    dif, dea, hist = _macd(close)
    signals = []

    # MACD 金叉/死叉（DIF 与 DEA 交叉）
    golden = _cross_above(dif, dea)
    death = _cross_below(dif, dea)

    for idx in golden[golden].index:
        i = df.index.get_loc(idx)
        below_zero = dif.iloc[i] < 0
        signals.append({
            "date": _get_date(df, i),
            "type": "MACD金叉" + ("(零轴下)" if below_zero else "(零轴上)"),
            "pair": "DIF↗DEA",
            "direction": "bullish",
            "price": float(close.iloc[i]),
            "dif": round(float(dif.iloc[i]), 4),
            "dea": round(float(dea.iloc[i]), 4),
            "hist": round(float(hist.iloc[i]), 4),
            "zero_position": "below" if below_zero else "above",
            "strength": _calc_strength(df, i, 20),
        })
    for idx in death[death].index:
        i = df.index.get_loc(idx)
        above_zero = dif.iloc[i] > 0
        signals.append({
            "date": _get_date(df, i),
            "type": "MACD死叉" + ("(零轴上)" if above_zero else "(零轴下)"),
            "pair": "DIF↘DEA",
            "direction": "bearish",
            "price": float(close.iloc[i]),
            "dif": round(float(dif.iloc[i]), 4),
            "dea": round(float(dea.iloc[i]), 4),
            "hist": round(float(hist.iloc[i]), 4),
            "zero_position": "above" if above_zero else "below",
            "strength": _calc_strength(df, i, 20),
        })

    # DIF 零轴穿越
    zero_up = _cross_above(dif, pd.Series(0, index=dif.index))
    zero_down = _cross_below(dif, pd.Series(0, index=dif.index))
    for idx in zero_up[zero_up].index:
        i = df.index.get_loc(idx)
        signals.append({
            "date": _get_date(df, i),
            "type": "DIF零轴穿越(上穿)",
            "pair": "DIF↗0",
            "direction": "bullish",
            "price": float(close.iloc[i]),
            "dif": round(float(dif.iloc[i]), 4),
            "strength": _calc_strength(df, i, 20),
        })
    for idx in zero_down[zero_down].index:
        i = df.index.get_loc(idx)
        signals.append({
            "date": _get_date(df, i),
            "type": "DIF零轴穿越(下穿)",
            "pair": "DIF↘0",
            "direction": "bearish",
            "price": float(close.iloc[i]),
            "dif": round(float(dif.iloc[i]), 4),
            "strength": _calc_strength(df, i, 20),
        })
    return signals


def _detect_kdj_crossovers(df: pd.DataFrame) -> list[dict]:
    """检测 KDJ 金叉/死叉 + 超买超卖区"""
    k, d, j = _kdj(df["high"], df["low"], df["close"])
    close = df["close"]
    signals = []

    golden = _cross_above(k, d)
    death = _cross_below(k, d)

    for idx in golden[golden].index:
        i = df.index.get_loc(idx)
        k_val = float(k.iloc[i])
        zone = "超卖区(<20)" if k_val < 20 else ("中性区" if k_val < 80 else "超买区(>80)")
        signals.append({
            "date": _get_date(df, i),
            "type": "KDJ金叉",
            "pair": "K↗D",
            "direction": "bullish",
            "price": float(close.iloc[i]),
            "k": round(k_val, 2),
            "d": round(float(d.iloc[i]), 2),
            "j": round(float(j.iloc[i]), 2) if not np.isnan(j.iloc[i]) else None,
            "zone": zone,
            "strength": _calc_strength(df, i, 20),
        })
    for idx in death[death].index:
        i = df.index.get_loc(idx)
        k_val = float(k.iloc[i])
        zone = "超买区(>80)" if k_val > 80 else ("中性区" if k_val > 20 else "超卖区(<20)")
        signals.append({
            "date": _get_date(df, i),
            "type": "KDJ死叉",
            "pair": "K↘D",
            "direction": "bearish",
            "price": float(close.iloc[i]),
            "k": round(k_val, 2),
            "d": round(float(d.iloc[i]), 2),
            "j": round(float(j.iloc[i]), 2) if not np.isnan(j.iloc[i]) else None,
            "zone": zone,
            "strength": _calc_strength(df, i, 20),
        })
    return signals


def _detect_price_ma_crossovers(df: pd.DataFrame) -> list[dict]:
    """检测价格突破/跌破均线"""
    close = df["close"]
    signals = []

    for n, name in [(5, "MA5"), (10, "MA10"), (20, "MA20"), (60, "MA60")]:
        ma = _ma(close, n)
        break_up = _cross_above(close, ma)
        break_down = _cross_below(close, ma)

        for idx in break_up[break_up].index:
            i = df.index.get_loc(idx)
            signals.append({
                "date": _get_date(df, i),
                "type": f"价格突破{name}",
                "pair": f"Price↗{name}",
                "direction": "bullish",
                "price": float(close.iloc[i]),
                "ma": round(float(ma.iloc[i]), 2),
                "strength": _calc_strength(df, i, 20),
            })
        for idx in break_down[break_down].index:
            i = df.index.get_loc(idx)
            signals.append({
                "date": _get_date(df, i),
                "type": f"价格跌破{name}",
                "pair": f"Price↘{name}",
                "direction": "bearish",
                "price": float(close.iloc[i]),
                "ma": round(float(ma.iloc[i]), 2),
                "strength": _calc_strength(df, i, 20),
            })
    return signals


def _detect_ma_alignment(df: pd.DataFrame) -> dict:
    """检测当前均线多空排列状态"""
    close = df["close"]
    if len(close) < 60:
        return {"status": "insufficient_data"}

    ma5 = _ma(close, 5).iloc[-1]
    ma10 = _ma(close, 10).iloc[-1]
    ma20 = _ma(close, 20).iloc[-1]
    ma60 = _ma(close, 60).iloc[-1]

    if pd.isna(ma60):
        return {"status": "insufficient_data"}

    # 上行排列：短期 MA > 长期 MA
    if ma5 > ma10 > ma20 > ma60:
        return {
            "status": "上行排列",
            "direction": "bullish",
            "mas": {"MA5": round(float(ma5), 2), "MA10": round(float(ma10), 2),
                    "MA20": round(float(ma20), 2), "MA60": round(float(ma60), 2)},
        }
    # 下行排列：短期 MA < 长期 MA
    elif ma5 < ma10 < ma20 < ma60:
        return {
            "status": "下行排列",
            "direction": "bearish",
            "mas": {"MA5": round(float(ma5), 2), "MA10": round(float(ma10), 2),
                    "MA20": round(float(ma20), 2), "MA60": round(float(ma60), 2)},
        }
    else:
        # 粘合/交织
        return {
            "status": "均线交织",
            "direction": "neutral",
            "mas": {"MA5": round(float(ma5), 2), "MA10": round(float(ma10), 2),
                    "MA20": round(float(ma20), 2), "MA60": round(float(ma60), 2)},
            "note": "均线未形成统一排列，可能处于震荡或趋势转换期",
        }


# ============================================================
#  辅助函数
# ============================================================

def _get_date(df: pd.DataFrame, idx: int) -> str:
    if "date" in df.columns:
        return str(df.iloc[idx]["date"])[:10]
    idx_val = df.index[idx]
    if hasattr(idx_val, "strftime"):
        return idx_val.strftime("%Y-%m-%d")
    return str(idx_val)


def _calc_strength(df: pd.DataFrame, idx: int, window: int = 20) -> str:
    """计算交叉信号所处的趋势强度（基于后续价格变化）"""
    close = df["close"]
    if idx >= len(close) - 3:
        return "unknown"
    # 交叉后 3 天涨跌
    future_return = (close.iloc[min(idx + 3, len(close) - 1)] / close.iloc[idx] - 1) * 100
    if abs(future_return) > 3:
        return "strong" if future_return > 0 else "strong_reverse"
    elif abs(future_return) > 1:
        return "moderate"
    return "weak"


# ============================================================
#  工具注册与主函数
# ============================================================

@tool
@register_tool(
    tool_id="get_crossover_signals",
    name="技术指标交叉信号检测",
    description=(
        "检测均线、MACD、KDJ 等常用技术指标的金叉/死叉信号。"
        "覆盖 12 种均线配对交叉、MACD 金叉死叉+零轴穿越、KDJ 金叉死叉+超买超卖区。"
        "输出结构化 JSON，包含信号类型、方向、强度和发生日期。"
        "这里的“信号”指价格/指标交叉产生的技术交易信号，不是财务造假信号、风险事件信号、情绪信号或 Agent 能力缺口。"
    ),
    category="technical",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["crossover_signals", "golden_cross", "death_cross", "technical_signals"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["金叉信号检测", "死叉信号检测", "趋势信号检测"],
    when_to_use=(
        "当需要识别金叉/死叉信号、均线突破/跌破、MACD/KDJ 交叉信号时使用。"
        "适用于趋势确认、买卖信号辅助、均线排列判断。"
    ),
    when_not_to_use=(
        "不适合单独作为交易决策依据（应结合其他工具）。"
        "不适合识别 K 线形态（应使用 get_candlestick_patterns）。"
        "不用于财务报表异常、现金流风险、公告事件风险、市场情绪或 Agent 能力缺口分析。"
        "不适合基本面分析。"
    ),
    returns=(
        "返回 JSON 字符串，包含 signals 数组、ma_alignment、summary。"
        "每个 signal 包含 date、type、direction、price、strength 等。"
    ),
    example="get_crossover_signals(symbol='600519', lookback_days=120)",
    related_tools=[
        "get_candlestick_patterns",
        "get_technical_indicators",
        "get_technical_factor_bundle_tool",
        "get_support_resistance_levels",
        "get_adx_trend_strength",
    ],
)
def get_crossover_signals(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"],
    lookback_days: Annotated[int, "回溯天数，默认 120"] = 120,
    signal_types: Annotated[str, "信号类型，逗号分隔，默认 all。可选: ma, macd, kdj, price_ma"] = "all",
) -> str:
    """检测技术指标交叉信号，覆盖均线金叉/死叉、MACD 金叉/死叉+零轴穿越、KDJ 金叉/死叉+超买超卖区、价格/均线穿越。

    Args:
        symbol: A 股股票代码，如 600519、000001
        lookback_days: 回溯天数，默认 120
        signal_types: 信号类型筛选，逗号分隔，取值 "ma" | "macd" | "kdj" | "price_ma" | "all"，默认 "all"

    Returns:
        str: JSON 字符串，正常返回字段说明——
            symbol: 股票代码
            data_info: 数据信息，子字段 —
                total_bars: K 线总数
                date_range: 日期范围，子字段 —
                    start: 起始日期
                    end: 结束日期
            signals_found: 检测到的信号总数
            summary: 汇总统计，子字段 —
                bullish: 上行信号数量
                bearish: 下行信号数量
            ma_alignment: 均线排列状态，子字段 —
                status: 排列状态，取值 "上行排列" | "下行排列" | "均线交织" | "insufficient_data"
                direction: 方向，取值 "bullish" | "bearish" | "neutral"（数据不足时无此字段）
                mas: 各均线值，子字段 — MA5、MA10、MA20、MA60
                note: 可选，状态说明文本（仅 "均线交织" 时存在）
            latest_signals: 最近 20 条信号列表，每个元素结构 —
                date: 信号发生日期
                type: 信号类型，取值如 "MA金叉" | "MA死叉" | "MACD金叉(零轴上)" | "MACD金叉(零轴下)" | "MACD死叉(零轴上)" | "MACD死叉(零轴下)" | "DIF零轴穿越(上穿)" | "DIF零轴穿越(下穿)" | "KDJ金叉" | "KDJ死叉" | "价格上穿MA{N}" | "价格下穿MA{N}"
                pair: 信号配对标识，如 "MA5↗MA10"、"DIF↗DEA"、"K↗D"、"DIF↗0"
                direction: 方向，取值 "bullish" | "bearish"
                price: 信号发生时收盘价
                strength: 信号强度（0-1）
                （附加字段因信号类型而异：short_ma、long_ma、dif、dea、hist、zero_position、k、d、j、ma_value、zone）
        异常时返回字段 —
            status: "no_data" | "error"
            message: 错误信息
    """
    try:
        from core.skill_runtime.data_access import get_stock_daily_quotes

        data = get_stock_daily_quotes(
            symbol=symbol,
            start_date=(datetime.date.today() - datetime.timedelta(days=lookback_days + 60)).strftime("%Y%m%d"),
            end_date=datetime.date.today().strftime("%Y%m%d"),
            limit=lookback_days + 60,
        )
        if not data or len(data) < 30:
            return json.dumps(
                {"status": "no_data", "message": f"股票 {symbol} 数据不足，至少需要 30 个交易日"},
                ensure_ascii=False, indent=2, default=str,
            )

        df = pd.DataFrame(data)
        col_map = {}
        for col in df.columns:
            low = col.lower().strip()
            if low in ("open", "开盘价", "开盘"):
                col_map[col] = "open"
            elif low in ("high", "最高价", "最高"):
                col_map[col] = "high"
            elif low in ("low", "最低价", "最低"):
                col_map[col] = "low"
            elif low in ("close", "收盘价", "收盘"):
                col_map[col] = "close"
            elif low in ("trade_date", "date", "日期"):
                col_map[col] = "date"
        df = df.rename(columns=col_map)

        required = {"open", "high", "low", "close"}
        if not required.issubset(df.columns):
            return json.dumps(
                {"status": "error", "message": f"缺少必要列: {required - set(df.columns)}"},
                ensure_ascii=False, indent=2, default=str,
            )

        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date").reset_index(drop=True)
        df = df.tail(lookback_days).copy()

        # 选择信号类型
        types = [t.strip().lower() for t in signal_types.split(",")]
        detect_all = "all" in types

        signals = []
        if detect_all or "ma" in types:
            signals.extend(_detect_ma_crossovers(df))
        if detect_all or "macd" in types:
            signals.extend(_detect_macd_crossovers(df))
        if detect_all or "kdj" in types:
            signals.extend(_detect_kdj_crossovers(df))
        if detect_all or "price_ma" in types:
            signals.extend(_detect_price_ma_crossovers(df))

        # 按日期排序（最新在前）
        signals.sort(key=lambda s: s["date"], reverse=True)

        # 均线排列
        ma_alignment = _detect_ma_alignment(df)

        bullish = sum(1 for s in signals if s["direction"] == "bullish")
        bearish = sum(1 for s in signals if s["direction"] == "bearish")

        payload = {
            "symbol": symbol,
            "data_info": {
                "total_bars": len(df),
                "date_range": {
                    "start": _get_date(df, 0),
                    "end": _get_date(df, len(df) - 1),
                },
            },
            "signals_found": len(signals),
            "summary": {
                "bullish": bullish,
                "bearish": bearish,
            },
            "ma_alignment": ma_alignment,
            "latest_signals": signals[:20],  # 最近 20 条
        }

        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("交叉信号检测失败: %s", exc, exc_info=True)
        return json.dumps(
            {"status": "error", "message": f"信号检测失败: {exc}"},
            ensure_ascii=False, indent=2, default=str,
        )


__all__ = ["get_crossover_signals"]
