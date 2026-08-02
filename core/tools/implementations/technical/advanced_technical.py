"""
高级技术分析工具

提供以下高级技术分析功能：
1. ADX 趋势强度 (Average Directional Index)
2. MACD 背离检测
3. RSI 背离检测
4. 量价背离分析

所有计算基于纯数学规则，无需 LLM 参与。
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

def _safe_float(value) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        numeric = float(value)
        if numeric != numeric:
            return None
        return numeric
    except (TypeError, ValueError):
        return None


def _ema(series: pd.Series, n: int) -> pd.Series:
    """指数移动平均"""
    return series.ewm(span=n, adjust=False).mean()


def _wilder_ema(series: pd.Series, n: int) -> pd.Series:
    """Wilder's 平滑 EMA（α=1/n）"""
    return series.ewm(alpha=1.0 / n, adjust=False).mean()


def _find_local_extrema_prices(
    series: pd.Series, order: int = 5
) -> tuple:
    """
    在价格序列中检测局部极值点。

    Returns:
        (peak_indices, peak_values, trough_indices, trough_values)
    """
    peaks_mask = (series > series.shift(order)) & (series > series.shift(-order))
    troughs_mask = (series < series.shift(order)) & (series < series.shift(-order))

    peak_indices = series.index[peaks_mask].to_numpy()
    trough_indices = series.index[troughs_mask].to_numpy()

    peak_values = series.loc[peak_indices].to_numpy() if len(peak_indices) > 0 else np.array([])
    trough_values = series.loc[trough_indices].to_numpy() if len(trough_indices) > 0 else np.array([])

    return peak_indices, peak_values, trough_indices, trough_values


def _find_lowest_low(series: pd.Series, start_idx: int, end_idx: int) -> tuple:
    """在索引范围内找最低值和对应索引"""
    subset = series.iloc[start_idx:end_idx + 1]
    min_idx = subset.idxmin()
    return min_idx, float(subset.min())


def _find_highest_high(series: pd.Series, start_idx: int, end_idx: int) -> tuple:
    """在索引范围内找最高值和对应索引"""
    subset = series.iloc[start_idx:end_idx + 1]
    max_idx = subset.idxmax()
    return max_idx, float(subset.max())


# ============================================================
#  Tool 1: ADX 趋势强度
# ============================================================

@tool
@register_tool(
    tool_id="get_adx_trend_strength",
    name="ADX 趋势强度分析",
    description="计算 ADX（平均趋向指数）及 ±DI，评估股票当前趋势的强度和方向。ADX>25=强趋势，20-25=趋势发展，<20=无趋势。",
    category="technical",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["technical_analysis", "adx", "trend_strength"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["trend_strength_analysis", "adx_analysis"],
    when_to_use="当需要量化判断趋势强度、区分趋势与震荡行情时使用。适用于确认趋势是否值得参与。",
    when_not_to_use="数据不足（少于 30 根 K 线）时结果不可靠；不适用于横盘震荡行情中的买卖点判断。",
    returns="返回 JSON，包含 latest_adx、plus_di、minus_di、trend_strength、trend_direction、adx_series 等。",
    example="get_adx_trend_strength(symbol='600519', lookback_days=120, period=14)",
    related_tools=["get_macd_divergence", "get_crossover_signals"],
)
def get_adx_trend_strength(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"],
    lookback_days: Annotated[int, "回看天数用于计算 ADX，默认 120"] = 120,
    period: Annotated[int, "ADX 计算周期，默认 14"] = 14,
) -> str:
    """计算 ADX（平均趋向指数）及 ±DI 指标，评估股票当前趋势的强度和方向。

    Args:
        symbol: A 股股票代码，如 600519、000001
        lookback_days: 回看天数用于计算 ADX，默认 120
        period: ADX 计算周期，默认 14

    Returns:
        str: JSON 字符串，正常返回字段说明——
            symbol: 股票代码
            current_price: 最新收盘价
            date: 最新交易日
            latest_adx: 最新 ADX 值
            plus_di: 最新 +DI 值
            minus_di: 最新 -DI 值
            trend_strength: 趋势强度，取值 "strong" | "moderate" | "weak"
            trend_direction: 趋势方向，取值 "up" | "down" | "neutral"
            adx_trend: ADX 变化方向，取值 "rising" | "falling" | "unknown"
            adx_series: 最近 5 期 ADX 值列表，元素结构 —
                date: 交易日期
                adx: ADX 值
            interpretation: 解读信息，子字段 —
                adx_meanings: ADX 含义说明文本
                current_assessment: 当前评估文本
            data_quality: 数据质量，子字段 —
                bars_analyzed: 分析的 K 线数量
                period: ADX 计算周期
        异常时返回字段 —
            status: "error"
            message: 错误信息
    """
    try:
        from core.skill_runtime.data_access import get_stock_daily_quotes

        today = datetime.date.today()
        end = today.strftime("%Y%m%d")
        start = (today - datetime.timedelta(days=int(lookback_days) + 60)).strftime("%Y%m%d")
        quotes = get_stock_daily_quotes(str(symbol), start, end, limit=int(lookback_days) + 100)

        if not quotes or len(quotes) < 30:
            return json.dumps(
                {"status": "error", "message": f"未获取到 {symbol} 的日线数据，或数据不足30条。"},
                ensure_ascii=False, indent=2, default=str,
            )

        df = pd.DataFrame(quotes)
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].apply(_safe_float)
        df["trade_date"] = df["trade_date"].astype(str)
        df = df.dropna(subset=["high", "low", "close"]).sort_values("trade_date")
        df = df.reset_index(drop=True)

        if len(df) < 30:
            return json.dumps(
                {"status": "error", "message": f"{symbol} 有效 OHLC 数据不足30条。"},
                ensure_ascii=False, indent=2, default=str,
            )

        high = df["high"]
        low = df["low"]
        close = df["close"]
        period_n = max(2, int(period))

        # 1. True Range (TR)
        prev_close = close.shift(1)
        tr = pd.concat([
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ], axis=1).max(axis=1)

        # 2. +DM and -DM
        prev_high = high.shift(1)
        prev_low = low.shift(1)

        up_move = high - prev_high
        down_move = prev_low - low

        plus_dm = pd.Series(0.0, index=df.index)
        minus_dm = pd.Series(0.0, index=df.index)

        plus_mask = (up_move > down_move) & (up_move > 0)
        minus_mask = (down_move > up_move) & (down_move > 0)

        plus_dm[plus_mask] = up_move[plus_mask]
        minus_dm[minus_mask] = down_move[minus_mask]

        # 3. Wilder's Smoothing
        smoothed_tr = _wilder_ema(tr, period_n)
        smoothed_plus_dm = _wilder_ema(plus_dm, period_n)
        smoothed_minus_dm = _wilder_ema(minus_dm, period_n)

        # 4. +DI and -DI
        plus_di = 100.0 * smoothed_plus_dm / smoothed_tr.replace(0, np.nan)
        minus_di = 100.0 * smoothed_minus_dm / smoothed_tr.replace(0, np.nan)

        # 5. DX
        dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)

        # 6. ADX = EMA of DX
        adx = _ema(dx, period_n)

        # --- 获取最新值 ---
        latest_idx = len(df) - 1
        latest_adx = float(adx.iloc[latest_idx]) if not pd.isna(adx.iloc[latest_idx]) else 0.0
        latest_plus_di = float(plus_di.iloc[latest_idx]) if not pd.isna(plus_di.iloc[latest_idx]) else 0.0
        latest_minus_di = float(minus_di.iloc[latest_idx]) if not pd.isna(minus_di.iloc[latest_idx]) else 0.0

        # 趋势强度判断
        if latest_adx > 25:
            trend_strength = "strong"
        elif latest_adx >= 20:
            trend_strength = "moderate"
        else:
            trend_strength = "weak"

        # 趋势方向判断
        if latest_plus_di > latest_minus_di:
            trend_direction = "up"
        elif latest_minus_di > latest_plus_di:
            trend_direction = "down"
        else:
            trend_direction = "neutral"

        # ADX 趋势（最近几根的变化方向）
        adx_values = adx.dropna()
        adx_trend = "unknown"
        if len(adx_values) >= 5:
            recent_adx = adx_values.iloc[-5:].values
            if recent_adx[-1] > recent_adx[0]:
                adx_trend = "rising"
            else:
                adx_trend = "falling"

        # 最近 5 期 ADX 值
        recent_adx_series = []
        for i in range(max(0, latest_idx - 4), latest_idx + 1):
            val = float(adx.iloc[i]) if not pd.isna(adx.iloc[i]) else 0.0
            recent_adx_series.append({
                "date": str(df.iloc[i]["trade_date"]),
                "adx": round(val, 2),
            })

        result = {
            "symbol": str(symbol),
            "current_price": round(float(close.iloc[-1]), 2),
            "date": str(df.iloc[-1]["trade_date"]),
            "latest_adx": round(latest_adx, 2),
            "plus_di": round(latest_plus_di, 2),
            "minus_di": round(latest_minus_di, 2),
            "trend_strength": trend_strength,
            "trend_direction": trend_direction,
            "adx_trend": adx_trend,
            "adx_series": recent_adx_series,
            "interpretation": {
                "adx_meanings": (
                    "ADX>25=强趋势, 20-25=趋势发展中, <20=震荡/无趋势"
                ),
                "current_assessment": (
                    f"ADX={latest_adx:.1f}，趋势强度为【{trend_strength}】。"
                    f"{'ADX上升中，趋势正在强化。' if adx_trend == 'rising' else 'ADX下降中，趋势可能减弱。'}"
                    f" {'+DI > -DI，为上升趋势。' if trend_direction == 'up' else '-DI > +DI，为下降趋势。' if trend_direction == 'down' else '多空力量均衡。'}"
                ),
            },
            "data_quality": {
                "bars_analyzed": len(df),
                "period": period_n,
            },
        }

        return json.dumps(result, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("ADX 计算失败: %s", exc, exc_info=True)
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2, default=str)


# ============================================================
#  Tool 2: MACD 背离检测
# ============================================================

@tool
@register_tool(
    tool_id="get_macd_divergence",
    name="MACD 背离检测",
    description="检测 MACD 与价格之间的背离信号。价格与 MACD 柱状图走势不一致时发出警示。",
    category="technical",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["technical_analysis", "macd_divergence"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["MACD 背离检测", "背离分析"],
    when_to_use="当需要识别趋势衰竭、潜在反转信号时使用。适用于辅助研判顶部/底部区域。",
    when_not_to_use="数据不足（少于 50 根 K 线）时检测可靠性不足；横盘震荡市场中假信号较多。",
    returns="返回 JSON，包含 divergences 列表（每个含类型、日期、强度、确认状态等）和整体评估。",
    example="get_macd_divergence(symbol='600519', lookback_days=180)",
    related_tools=["get_rsi_divergence", "get_adx_trend_strength", "get_volume_price_divergence"],
)
def get_macd_divergence(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"],
    lookback_days: Annotated[int, "回看天数用于背离检测，默认 180"] = 180,
) -> str:
    """检测 MACD 与价格之间的背离信号，识别趋势衰竭和潜在反转点。

    Args:
        symbol: A 股股票代码，如 600519、000001
        lookback_days: 回看天数用于背离检测，默认 180

    Returns:
        str: JSON 字符串，正常返回字段说明——
            symbol: 股票代码
            current_price: 最新收盘价
            date: 最新交易日
            divergences: 背离信号列表，每个元素结构 —
                type: 背离类型，取值 "bearish"（顶背离） | "bullish"（底背离）
                label: 中文标签，取值 "顶背离" | "底背离"
                price_start_date: 起始价格日期
                price_end_date: 结束价格日期
                price_start: 起始价格
                price_end: 结束价格
                price_change_pct: 价格变化百分比
                macd_start: 起始 MACD 柱值
                macd_end: 结束 MACD 柱值
                strength: 信号强度，取值 "strong" | "moderate" | "weak"
                confirmation_status: 确认状态，取值 "confirmed" | "pending"
            summary: 汇总信息，子字段 —
                total_divergences: 背离总数
                bullish_count: 上行背离数量
                bearish_count: 下行背离数量
                strong_signals: 强信号数量
            data_quality: 数据质量，子字段 —
                bars_analyzed: 分析的 K 线数量
        异常时返回字段 —
            status: "error"
            message: 错误信息
    """
    try:
        from core.skill_runtime.data_access import get_stock_daily_quotes
        from core.tools.implementations.technical import macd

        today = datetime.date.today()
        end = today.strftime("%Y%m%d")
        start = (today - datetime.timedelta(days=int(lookback_days) + 60)).strftime("%Y%m%d")
        quotes = get_stock_daily_quotes(str(symbol), start, end, limit=int(lookback_days) + 100)

        if not quotes or len(quotes) < 50:
            return json.dumps(
                {"status": "error", "message": f"未获取到 {symbol} 的日线数据，或数据不足50条。"},
                ensure_ascii=False, indent=2, default=str,
            )

        df = pd.DataFrame(quotes)
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].apply(_safe_float)
        df["trade_date"] = df["trade_date"].astype(str)
        df = df.dropna(subset=["high", "low", "close"]).sort_values("trade_date")
        df = df.reset_index(drop=True)

        if len(df) < 50:
            return json.dumps(
                {"status": "error", "message": f"{symbol} 有效数据不足50条。"},
                ensure_ascii=False, indent=2, default=str,
            )

        close = df["close"]

        # 计算 MACD
        macd_df = macd(close, fast=12, slow=26, signal=9)
        macd_hist = macd_df["macd_hist"]

        # 检测背离
        divergences = []

        # 查找局部极值点（价格和 MACD 柱状图）
        price_peaks, price_peak_vals, price_troughs, price_trough_vals = \
            _find_local_extrema_prices(close, order=5)

        macd_peaks, macd_peak_vals, macd_troughs, macd_trough_vals = \
            _find_local_extrema_prices(macd_hist, order=5)

        # --- 顶背离检测：价格更高高点，MACD 更低高点 ---
        if len(price_peaks) >= 2 and len(macd_peaks) >= 2:
            # 取最近的两个价格峰值
            p1_idx, p1_price = price_peaks[-2], float(price_peak_vals[-2])
            p2_idx, p2_price = price_peaks[-1], float(price_peak_vals[-1])

            if p2_price > p1_price:
                # 在价格峰值附近找 MACD 峰值
                macd_in_range = macd_peaks[(macd_peaks >= p1_idx) & (macd_peaks <= p2_idx)]
                if len(macd_in_range) >= 2:
                    m1_val = float(macd_hist.loc[macd_in_range[-2]])
                    m2_val = float(macd_hist.loc[macd_in_range[-1]])

                    if m2_val < m1_val:
                        # MACD 柱下降 → 顶背离
                        price_change_pct = (p2_price - p1_price) / p1_price * 100
                        hist_change_pct = (m2_val - m1_val) / max(abs(m1_val), 0.001) * 100
                        strength = "strong" if (abs(hist_change_pct) > 30) else "moderate" if (abs(hist_change_pct) > 15) else "weak"

                        # 确认状态：当前是否已开始回调
                        recent_close = close.iloc[-min(5, len(close)):].values
                        confirmation = "confirmed" if len(recent_close) >= 3 and recent_close[-1] < recent_close[0] else "pending"

                        divergences.append({
                            "type": "bearish",
                            "label": "顶背离",
                            "price_start_date": str(df.iloc[df.index.get_loc(p1_idx)]["trade_date"])[:10],
                            "price_end_date": str(df.iloc[df.index.get_loc(p2_idx)]["trade_date"])[:10],
                            "price_start": round(p1_price, 2),
                            "price_end": round(p2_price, 2),
                            "price_change_pct": round(price_change_pct, 2),
                            "macd_start": round(m1_val, 4),
                            "macd_end": round(m2_val, 4),
                            "strength": strength,
                            "confirmation_status": confirmation,
                        })

        # --- 底背离检测：价格更低低点，MACD 更高低点 ---
        if len(price_troughs) >= 2 and len(macd_troughs) >= 2:
            t1_idx, t1_price = price_troughs[-2], float(price_trough_vals[-2])
            t2_idx, t2_price = price_troughs[-1], float(price_trough_vals[-1])

            if t2_price < t1_price:
                macd_in_range = macd_troughs[(macd_troughs >= t1_idx) & (macd_troughs <= t2_idx)]
                if len(macd_in_range) >= 2:
                    m1_val = float(macd_hist.loc[macd_in_range[-2]])
                    m2_val = float(macd_hist.loc[macd_in_range[-1]])

                    if m2_val > m1_val:
                        # MACD 柱上升 → 底背离
                        price_change_pct = (t2_price - t1_price) / t1_price * 100
                        hist_change_pct = (m2_val - m1_val) / max(abs(m1_val), 0.001) * 100
                        strength = "strong" if (hist_change_pct > 30) else "moderate" if (hist_change_pct > 15) else "weak"

                        recent_close = close.iloc[-min(5, len(close)):].values
                        confirmation = "confirmed" if len(recent_close) >= 3 and recent_close[-1] > recent_close[0] else "pending"

                        divergences.append({
                            "type": "bullish",
                            "label": "底背离",
                            "price_start_date": str(df.iloc[df.index.get_loc(t1_idx)]["trade_date"])[:10],
                            "price_end_date": str(df.iloc[df.index.get_loc(t2_idx)]["trade_date"])[:10],
                            "price_start": round(t1_price, 2),
                            "price_end": round(t2_price, 2),
                            "price_change_pct": round(price_change_pct, 2),
                            "macd_start": round(m1_val, 4),
                            "macd_end": round(m2_val, 4),
                            "strength": strength,
                            "confirmation_status": confirmation,
                        })

        result = {
            "symbol": str(symbol),
            "current_price": round(float(close.iloc[-1]), 2),
            "date": str(df.iloc[-1]["trade_date"]),
            "divergences": divergences,
            "summary": {
                "total_divergences": len(divergences),
                "bullish_count": sum(1 for d in divergences if d["type"] == "bullish"),
                "bearish_count": sum(1 for d in divergences if d["type"] == "bearish"),
                "strong_signals": sum(1 for d in divergences if d["strength"] == "strong"),
            },
            "data_quality": {
                "bars_analyzed": len(df),
            },
        }

        return json.dumps(result, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("MACD 背离检测失败: %s", exc, exc_info=True)
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2, default=str)


# ============================================================
#  Tool 3: RSI 背离检测
# ============================================================

@tool
@register_tool(
    tool_id="get_rsi_divergence",
    name="RSI 背离检测",
    description="检测 RSI 与价格之间的背离信号。RSI 在超买/超卖区出现背离时信号更为可靠。",
    category="technical",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["technical_analysis", "rsi_divergence"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["rsi_divergence_detection", "divergence_analysis"],
    when_to_use="当需要识别超买/超卖区域的潜在反转信号时使用。RSI 背离结合极端区域信号更强。",
    when_not_to_use="数据不足（少于 50 根 K 线）时检测可靠性不足；单边强趋势中假信号较多。",
    returns="返回 JSON，包含 divergences 列表（每个含类型、日期、RSI 值、强度等）和整体评估。",
    example="get_rsi_divergence(symbol='600519', lookback_days=180, rsi_period=14)",
    related_tools=["get_macd_divergence", "get_volume_price_divergence"],
)
def get_rsi_divergence(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"],
    lookback_days: Annotated[int, "回看天数用于背离检测，默认 180"] = 180,
    rsi_period: Annotated[int, "RSI 计算周期，默认 14"] = 14,
) -> str:
    """检测 RSI 与价格之间的背离信号，识别超买/超卖区域的潜在反转点。

    Args:
        symbol: A 股股票代码，如 600519、000001
        lookback_days: 回看天数用于背离检测，默认 180
        rsi_period: RSI 计算周期，默认 14

    Returns:
        str: JSON 字符串，正常返回字段说明——
            symbol: 股票代码
            current_price: 最新收盘价
            date: 最新交易日
            latest_rsi: 最新 RSI 值
            rsi_zone: RSI 区域，取值 "超买(>70)" | "超卖(<30)" | "中性"
            divergences: 背离信号列表，每个元素结构 —
                type: 背离类型，取值 "bearish"（顶背离） | "bullish"（底背离）
                label: 中文标签，取值 "RSI顶背离" | "RSI底背离"
                price_start: 起始价格
                price_end: 结束价格
                rsi_start: 起始 RSI 值
                rsi_end: 结束 RSI 值
                rsi_zone: RSI 所处区域，取值 "超买区" | "中性区" | "超卖区"
                strength: 信号强度，取值 "strong" | "moderate" | "weak"
            summary: 汇总信息，子字段 —
                total_divergences: 背离总数
                bullish_count: 上行背离数量
                bearish_count: 下行背离数量
                strong_signals: 强信号数量
            data_quality: 数据质量，子字段 —
                bars_analyzed: 分析的 K 线数量
        异常时返回字段 —
            status: "error"
            message: 错误信息
    """
    try:
        from core.skill_runtime.data_access import get_stock_daily_quotes
        from core.tools.implementations.technical import rsi

        today = datetime.date.today()
        end = today.strftime("%Y%m%d")
        start = (today - datetime.timedelta(days=int(lookback_days) + 60)).strftime("%Y%m%d")
        quotes = get_stock_daily_quotes(str(symbol), start, end, limit=int(lookback_days) + 100)

        if not quotes or len(quotes) < 50:
            return json.dumps(
                {"status": "error", "message": f"未获取到 {symbol} 的日线数据，或数据不足50条。"},
                ensure_ascii=False, indent=2, default=str,
            )

        df = pd.DataFrame(quotes)
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].apply(_safe_float)
        df["trade_date"] = df["trade_date"].astype(str)
        df = df.dropna(subset=["high", "low", "close"]).sort_values("trade_date")
        df = df.reset_index(drop=True)

        if len(df) < 50:
            return json.dumps(
                {"status": "error", "message": f"{symbol} 有效数据不足50条。"},
                ensure_ascii=False, indent=2, default=str,
            )

        close = df["close"]

        # 计算 RSI
        rsi_series = rsi(close, n=int(rsi_period), method="ema")

        divergences = []

        # 查找局部极值点
        price_peaks, price_peak_vals, price_troughs, price_trough_vals = \
            _find_local_extrema_prices(close, order=5)

        rsi_peaks, rsi_peak_vals, rsi_troughs, rsi_trough_vals = \
            _find_local_extrema_prices(rsi_series, order=5)

        # --- RSI 顶背离：价格更高高点，RSI 更低高点 ---
        if len(price_peaks) >= 2 and len(rsi_peaks) >= 2:
            p1_idx, p1_price = price_peaks[-2], float(price_peak_vals[-2])
            p2_idx, p2_price = price_peaks[-1], float(price_peak_vals[-1])

            if p2_price > p1_price:
                rsi_in_range = rsi_peaks[(rsi_peaks >= p1_idx) & (rsi_peaks <= p2_idx)]
                if len(rsi_in_range) >= 2:
                    r1_val = float(rsi_series.loc[rsi_in_range[-2]])
                    r2_val = float(rsi_series.loc[rsi_in_range[-1]])

                    if r2_val < r1_val:
                        # RSI 在极端区域（>70）时信号更强
                        in_overbought = r2_val > 70 or r1_val > 70
                        strength = "strong" if (in_overbought and (r1_val - r2_val) > 5) else "moderate" if (r1_val - r2_val) > 3 else "weak"

                        divergences.append({
                            "type": "bearish",
                            "label": "RSI顶背离",
                            "price_start": round(p1_price, 2),
                            "price_end": round(p2_price, 2),
                            "rsi_start": round(r1_val, 2),
                            "rsi_end": round(r2_val, 2),
                            "rsi_zone": "超买区" if in_overbought else "中性区",
                            "strength": strength,
                        })

        # --- RSI 底背离：价格更低低点，RSI 更高低点 ---
        if len(price_troughs) >= 2 and len(rsi_troughs) >= 2:
            t1_idx, t1_price = price_troughs[-2], float(price_trough_vals[-2])
            t2_idx, t2_price = price_troughs[-1], float(price_trough_vals[-1])

            if t2_price < t1_price:
                rsi_in_range = rsi_troughs[(rsi_troughs >= t1_idx) & (rsi_troughs <= t2_idx)]
                if len(rsi_in_range) >= 2:
                    r1_val = float(rsi_series.loc[rsi_in_range[-2]])
                    r2_val = float(rsi_series.loc[rsi_in_range[-1]])

                    if r2_val > r1_val:
                        in_oversold = r2_val < 30 or r1_val < 30
                        strength = "strong" if (in_oversold and (r2_val - r1_val) > 5) else "moderate" if (r2_val - r1_val) > 3 else "weak"

                        divergences.append({
                            "type": "bullish",
                            "label": "RSI底背离",
                            "price_start": round(t1_price, 2),
                            "price_end": round(t2_price, 2),
                            "rsi_start": round(r1_val, 2),
                            "rsi_end": round(r2_val, 2),
                            "rsi_zone": "超卖区" if in_oversold else "中性区",
                            "strength": strength,
                        })

        # 最新 RSI 值
        latest_rsi = float(rsi_series.iloc[-1]) if not pd.isna(rsi_series.iloc[-1]) else 0.0
        latest_close = float(close.iloc[-1])

        result = {
            "symbol": str(symbol),
            "current_price": round(latest_close, 2),
            "date": str(df.iloc[-1]["trade_date"]),
            "latest_rsi": round(latest_rsi, 2),
            "rsi_zone": "超买(>70)" if latest_rsi > 70 else "超卖(<30)" if latest_rsi < 30 else "中性",
            "divergences": divergences,
            "summary": {
                "total_divergences": len(divergences),
                "bullish_count": sum(1 for d in divergences if d["type"] == "bullish"),
                "bearish_count": sum(1 for d in divergences if d["type"] == "bearish"),
                "strong_signals": sum(1 for d in divergences if d["strength"] == "strong"),
            },
            "data_quality": {
                "bars_analyzed": len(df),
            },
        }

        return json.dumps(result, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("RSI 背离检测失败: %s", exc, exc_info=True)
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2, default=str)


# ============================================================
#  Tool 4: 量价背离分析
# ============================================================

@tool
@register_tool(
    tool_id="get_volume_price_divergence",
    name="量价背离分析",
    description="分析成交量和价格之间的背离关系，识别放量滞涨、缩量上涨、放量下跌等典型量价形态。",
    category="technical",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["technical_analysis", "volume_price_divergence"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["量价分析", "背离分析"],
    when_to_use="当需要评估量价关系是否健康、识别潜在反转或持续信号时使用。",
    when_not_to_use="数据不足（少于 30 根 K 线）时结果参考价值有限；新股或交易不活跃的股票不适用。",
    returns="返回 JSON，包含 current_status、divergence_bars_count、trend_alignment 及近期量价评分。",
    example="get_volume_price_divergence(symbol='600519', lookback_days=120)",
    related_tools=["get_obv_analysis", "get_turnover_analysis"],
)
def get_volume_price_divergence(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"],
    lookback_days: Annotated[int, "回看天数用于量价分析，默认 120"] = 120,
) -> str:
    """分析成交量和价格之间的关系，检测量价背离信号，识别放量滞涨、缩量上涨等形态。

    Args:
        symbol: A 股股票代码，如 600519、000001
        lookback_days: 回看天数用于量价分析，默认 120

    Returns:
        str: JSON 字符串，正常返回字段说明——
            symbol: 股票代码
            current_price: 最新收盘价
            date: 最新交易日
            current_status: 当前量价状态，取值 "bearish_divergence_detected" | "capitulation_detected" | "healthy_uptrend" | "mixed"
            divergence_bars_count: 量价背离 K 线数量
            total_bars_analyzed: 分析的 K 线总数
            divergence_ratio: 背离 K 线占比
            trend_alignment: 趋势一致性，取值 "aligned_bullish" | "aligned_bearish" | "bearish_divergence" | "potential_bottom" | "neutral" | "insufficient_data"
            recent_assessments: 近期量价评估列表（最近 10 根），每个元素结构 —
                date: 交易日期
                price_change_pct: 价格变化百分比
                volume_ratio: 量比
                status: 单根 K 线状态，取值 "healthy_uptrend" | "bearish_divergence" | "capitulation" | "low_interest" | "neutral"
            interpretation: 状态解读，子字段 —
                healthy_uptrend: 价涨量增说明
                bearish_divergence: 价涨量缩说明
                capitulation: 价跌量增说明
                low_interest: 价跌量缩说明
            data_quality: 数据质量，子字段 —
                bars_analyzed: 分析的 K 线数量
        异常时返回字段 —
            status: "error"
            message: 错误信息
    """
    try:
        from core.skill_runtime.data_access import get_stock_daily_quotes

        today = datetime.date.today()
        end = today.strftime("%Y%m%d")
        start = (today - datetime.timedelta(days=int(lookback_days) + 30)).strftime("%Y%m%d")
        quotes = get_stock_daily_quotes(str(symbol), start, end, limit=int(lookback_days) + 60)

        if not quotes or len(quotes) < 30:
            return json.dumps(
                {"status": "error", "message": f"未获取到 {symbol} 的日线数据，或数据不足30条。"},
                ensure_ascii=False, indent=2, default=str,
            )

        df = pd.DataFrame(quotes)
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].apply(_safe_float)
        df["trade_date"] = df["trade_date"].astype(str)
        df = df.dropna(subset=["high", "low", "close", "volume"]).sort_values("trade_date")
        df = df.reset_index(drop=True)

        if len(df) < 30:
            return json.dumps(
                {"status": "error", "message": f"{symbol} 有效数据不足30条。"},
                ensure_ascii=False, indent=2, default=str,
            )

        close = df["close"]
        volume = df["volume"]

        # 计算价格变化和成交量变化
        price_change = close.pct_change()
        volume_ma20 = volume.rolling(window=20, min_periods=5).mean()
        volume_ratio = volume / volume_ma20.replace(0, np.nan)

        # 量价评分：对每一根 K 线分类
        bar_assessments = []
        divergence_bars_count = 0

        for i in range(1, len(df)):
            p_chg = float(price_change.iloc[i]) if not pd.isna(price_change.iloc[i]) else 0.0
            v_ratio = float(volume_ratio.iloc[i]) if not pd.isna(volume_ratio.iloc[i]) else 1.0
            is_high_vol = v_ratio > 1.5
            is_low_vol = v_ratio < 0.5

            if p_chg > 0.01 and is_high_vol:
                status = "healthy_uptrend"
            elif p_chg > 0.01 and is_low_vol:
                status = "bearish_divergence"
                divergence_bars_count += 1
            elif p_chg < -0.01 and is_high_vol:
                status = "capitulation"
                divergence_bars_count += 1
            elif p_chg < -0.01 and is_low_vol:
                status = "low_interest"
            else:
                status = "neutral"

            bar_assessments.append({
                "date": str(df.iloc[i]["trade_date"])[:10],
                "price_change_pct": round(p_chg * 100, 2),
                "volume_ratio": round(v_ratio, 2),
                "status": status,
            })

        # 当前状态判断（最近 3 根 K 线）
        recent_bars = bar_assessments[-min(3, len(bar_assessments)):]
        recent_statuses = [b["status"] for b in recent_bars]

        if "bearish_divergence" in recent_statuses:
            current_status = "bearish_divergence_detected"
        elif "capitulation" in recent_statuses:
            current_status = "capitulation_detected"
        elif recent_statuses.count("healthy_uptrend") >= 2:
            current_status = "healthy_uptrend"
        else:
            current_status = "mixed"

        # 趋势一致性评估
        recent_prices = close.iloc[-20:].values
        recent_volumes = volume.iloc[-20:].values
        if len(recent_prices) >= 10:
            price_trend = "up" if recent_prices[-1] > recent_prices[0] else "down"
            volume_trend = "up" if recent_volumes[-1] > recent_volumes[0] else "down"

            if price_trend == "up" and volume_trend == "up":
                trend_alignment = "aligned_bullish"
            elif price_trend == "down" and volume_trend == "down":
                trend_alignment = "aligned_bearish"
            elif price_trend == "up" and volume_trend == "down":
                trend_alignment = "bearish_divergence"
            elif price_trend == "down" and volume_trend == "up":
                trend_alignment = "potential_bottom"
            else:
                trend_alignment = "neutral"
        else:
            trend_alignment = "insufficient_data"

        result = {
            "symbol": str(symbol),
            "current_price": round(float(close.iloc[-1]), 2),
            "date": str(df.iloc[-1]["trade_date"])[:10],
            "current_status": current_status,
            "divergence_bars_count": divergence_bars_count,
            "total_bars_analyzed": len(bar_assessments),
            "divergence_ratio": round(divergence_bars_count / max(1, len(bar_assessments)), 4),
            "trend_alignment": trend_alignment,
            "recent_assessments": bar_assessments[-min(10, len(bar_assessments)):],
            "interpretation": {
                "healthy_uptrend": "价涨量增，上涨趋势健康",
                "bearish_divergence": "价涨量缩，上涨动能衰竭（负向背离信号）",
                "capitulation": "价跌量增，恐慌性抛售（可能接近底部）",
                "low_interest": "价跌量缩，市场关注度低",
            },
            "data_quality": {
                "bars_analyzed": len(df),
            },
        }

        return json.dumps(result, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("量价背离分析失败: %s", exc, exc_info=True)
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2, default=str)


__all__ = [
    "get_adx_trend_strength",
    "get_macd_divergence",
    "get_rsi_divergence",
    "get_volume_price_divergence",
]