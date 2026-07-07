"""
经典技术形态识别工具

基于 OHLC 数据，自动识别以下五大类经典技术形态：
- 头肩顶/底 (Head and Shoulders)
- 双顶/双底 (Double Top/Bottom)
- 三角形态 (Triangle: Ascending/Descending/Symmetrical)
- 旗形/三角旗 (Flag/Pennant)
- 通道 (Channel)

所有形态基于纯数学规则检测，无需 LLM 参与。
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


def _find_peaks_and_troughs(
    high: pd.Series, low: pd.Series, n: int = 5
) -> tuple:
    """
    使用 N 邻域比较法检测局部极值点。

    Returns:
        (peak_indices, trough_indices) 分别为局部最高点和最低点的索引数组。
    """
    # 峰值：比左右各 N 个邻居都高
    peak_mask = (high > high.shift(n)) & (high > high.shift(-n))
    # 谷值：比左右各 N 个邻居都低
    trough_mask = (low < low.shift(n)) & (low < low.shift(-n))

    peak_indices = high.index[peak_mask].to_numpy()
    trough_indices = low.index[trough_mask].to_numpy()

    return peak_indices, trough_indices


def _filter_consecutive_extrema(indices: np.ndarray, prices: pd.Series) -> list:
    """
    过滤连续极值点，只保留每个局部窗口内最极端的那个。
    若两个极值点距离小于 3 根 K 线，保留价格更极端的那个。
    """
    if len(indices) < 2:
        return list(indices)

    filtered = [indices[0]]
    for i in range(1, len(indices)):
        idx = indices[i]
        prev_idx = filtered[-1]
        if abs(idx - prev_idx) < 3:
            # 保留更极端的价格
            if abs(prices.loc[idx]) > abs(prices.loc[prev_idx]):
                filtered[-1] = idx
        else:
            filtered.append(idx)
    return filtered


def _detect_head_shoulders(
    peaks: np.ndarray, peak_prices: np.ndarray, volumes: pd.Series
) -> list:
    """
    检测头肩顶形态。

    条件：
    1. 找到连续的 3 个峰值：左肩 < 头部 > 右肩
    2. 头部比左右肩高 > 3%
    3. 左右肩高度差异 < 3%
    4. 成交量从左到右递减
    """
    results = []
    for i in range(len(peaks) - 2):
        ls_idx, h_idx, rs_idx = peaks[i], peaks[i + 1], peaks[i + 2]
        ls_price, head_price, rs_price = (
            peak_prices[i],
            peak_prices[i + 1],
            peak_prices[i + 2],
        )

        # 头比两肩高 > 3%
        if head_price <= ls_price * 1.03 or head_price <= rs_price * 1.03:
            continue
        # 两肩高度差异 < 3%
        shoulder_diff = abs(ls_price - rs_price) / max(ls_price, rs_price)
        if shoulder_diff >= 0.03:
            continue

        # 成交量递减
        ls_vol = volumes.iloc[ls_idx]
        h_vol = volumes.iloc[h_idx]
        rs_vol = volumes.iloc[rs_idx]
        if h_vol > ls_vol or rs_vol > h_vol:
            continue

        # 颈线 = 连接左肩和右肩之间的谷底
        # 简单近似：用两肩价格的平均作为颈线
        neckline = (ls_price + rs_price) / 2.0
        results.append({
            "pattern": "head_and_shoulders_top",
            "type": "top",
            "left_shoulder_price": round(ls_price, 2),
            "head_price": round(head_price, 2),
            "right_shoulder_price": round(rs_price, 2),
            "neckline": round(neckline, 2),
            "break_down_target": round(neckline - (head_price - neckline), 2),
            "confidence": "high" if shoulder_diff < 0.015 else "medium",
        })
    return results


def _detect_inverse_head_shoulders(
    troughs: np.ndarray, trough_prices: np.ndarray, volumes: pd.Series
) -> list:
    """
    检测头肩底形态（倒转头肩）。
    """
    results = []
    for i in range(len(troughs) - 2):
        ls_idx, h_idx, rs_idx = troughs[i], troughs[i + 1], troughs[i + 2]
        ls_price, head_price, rs_price = (
            trough_prices[i],
            trough_prices[i + 1],
            trough_prices[i + 2],
        )

        # 头比两肩低 > 3%
        if head_price >= ls_price * 0.97 or head_price >= rs_price * 0.97:
            continue
        # 两肩差异 < 3%
        shoulder_diff = abs(ls_price - rs_price) / max(abs(ls_price), abs(rs_price))
        if shoulder_diff >= 0.03:
            continue

        # 成交量在头部放大，之后缩小（底部形态成交量特征相反）
        results.append({
            "pattern": "head_and_shoulders_bottom",
            "type": "bottom",
            "left_shoulder_price": round(ls_price, 2),
            "head_price": round(head_price, 2),
            "right_shoulder_price": round(rs_price, 2),
            "neckline": round((ls_price + rs_price) / 2.0, 2),
            "break_up_target": round((ls_price + rs_price) / 2.0 + abs((ls_price + rs_price) / 2.0 - head_price), 2),
            "confidence": "high" if shoulder_diff < 0.015 else "medium",
        })
    return results


def _detect_double_top(
    peaks: np.ndarray, peak_prices: np.ndarray, low_series: pd.Series
) -> list:
    """
    检测双顶形态。

    条件：
    1. 两个峰值在相似水平（差异 < 3%）
    2. 峰值之间距离 > 10 根 K 线
    3. 两峰之间存在明显的谷底
    """
    results = []
    for i in range(len(peaks) - 1):
        p1_idx, p2_idx = peaks[i], peaks[i + 1]
        p1_price, p2_price = peak_prices[i], peak_prices[i + 1]

        # 两峰价格接近（差异 < 3%）
        diff = abs(p1_price - p2_price) / max(p1_price, p2_price)
        if diff >= 0.03:
            continue

        # 距离 > 10 根 K 线
        bar_distance = abs(p2_idx - p1_idx)
        if bar_distance <= 10:
            continue

        # 两峰之间的谷底
        valley = low_series.loc[int(p1_idx):int(p2_idx)].min()

        results.append({
            "pattern": "double_top",
            "type": "top",
            "peak1_price": round(p1_price, 2),
            "peak2_price": round(p2_price, 2),
            "valley_price": round(float(valley), 2),
            "neckline": round(float(valley), 2),
            "break_down_target": round(float(valley) - (p1_price - float(valley)), 2),
            "bar_distance": int(bar_distance),
            "confidence": "high" if diff < 0.015 else "medium",
        })
    return results


def _detect_double_bottom(
    troughs: np.ndarray, trough_prices: np.ndarray, high_series: pd.Series
) -> list:
    """
    检测双底形态。
    """
    results = []
    for i in range(len(troughs) - 1):
        t1_idx, t2_idx = troughs[i], troughs[i + 1]
        t1_price, t2_price = trough_prices[i], trough_prices[i + 1]

        diff = abs(t1_price - t2_price) / max(abs(t1_price), abs(t2_price))
        if diff >= 0.03:
            continue

        bar_distance = abs(t2_idx - t1_idx)
        if bar_distance <= 10:
            continue

        peak = high_series.loc[int(t1_idx):int(t2_idx)].max()

        results.append({
            "pattern": "double_bottom",
            "type": "bottom",
            "trough1_price": round(t1_price, 2),
            "trough2_price": round(t2_price, 2),
            "neckline": round(float(peak), 2),
            "break_up_target": round(float(peak) + (float(peak) - t1_price), 2),
            "bar_distance": int(bar_distance),
            "confidence": "high" if diff < 0.015 else "medium",
        })
    return results


def _detect_triangles(
    peaks: np.ndarray, peak_prices: np.ndarray,
    troughs: np.ndarray, trough_prices: np.ndarray,
) -> list:
    """
    检测三角形态。

    取最近的一组峰-谷序列，用线性回归检查收敛性。
    """
    results = []

    if len(peaks) < 3 or len(troughs) < 3:
        return results

    # 取最近 10 个峰和谷
    recent_peaks = peaks[-10:]
    recent_peak_prices = peak_prices[-10:]
    recent_troughs = troughs[-10:]
    recent_trough_prices = trough_prices[-10:]

    if len(recent_peaks) >= 3 and len(recent_troughs) >= 3:
        # 检查上升三角形：更高的谷底 + 水平的峰
        trough_slope = np.polyfit(
            range(len(recent_troughs)), recent_trough_prices, 1
        )[0]
        peak_slope = np.polyfit(
            range(len(recent_peaks)), recent_peak_prices, 1
        )[0]

        # 归一化斜率（相对于价格水平）
        avg_price = (np.mean(recent_peak_prices) + np.mean(recent_trough_prices)) / 2.0
        trough_slope_norm = trough_slope / avg_price * 100 if avg_price > 0 else 0
        peak_slope_norm = peak_slope / avg_price * 100 if avg_price > 0 else 0
        peak_slope_abs = abs(peak_slope_norm)
        trough_slope_abs = abs(trough_slope_norm)

        # 对称三角形：峰下降 + 谷上升
        if peak_slope_norm < -0.05 and trough_slope_norm > 0.05:
            convergence = trough_slope_norm - peak_slope_norm
            if convergence > 0.2:
                apex_bar = len(recent_troughs) + (
                    (recent_trough_prices[-1] - recent_peak_prices[-1])
                    / (peak_slope - trough_slope)
                    if abs(peak_slope - trough_slope) > 1e-8 else 50
                )
                results.append({
                    "pattern": "symmetrical_triangle",
                    "type": "neutral",
                    "peak_trend_slope_pct": round(peak_slope_norm, 3),
                    "trough_trend_slope_pct": round(trough_slope_norm, 3),
                    "bars_to_apex": max(0, int(apex_bar)),
                    "confidence": "medium",
                })
        # 上升三角形：谷上升 + 峰水平
        elif trough_slope_norm > 0.05 and peak_slope_abs < 0.1:
            results.append({
                "pattern": "ascending_triangle",
                "type": "bullish",
                "peak_trend_slope_pct": round(peak_slope_norm, 3),
                "trough_trend_slope_pct": round(trough_slope_norm, 3),
                "confidence": "medium",
            })
        # 下降三角形：峰下降 + 谷水平
        elif peak_slope_norm < -0.05 and trough_slope_abs < 0.1:
            results.append({
                "pattern": "descending_triangle",
                "type": "bearish",
                "peak_trend_slope_pct": round(peak_slope_norm, 3),
                "trough_trend_slope_pct": round(trough_slope_norm, 3),
                "confidence": "medium",
            })

    return results


def _detect_flag_pennant(
    df: pd.DataFrame, high: pd.Series, low: pd.Series, close: pd.Series
) -> list:
    """
    检测旗形和三角旗形态。

    旗形：先有一波剧烈拉升/下跌（旗杆），然后进入与趋势反向的平行通道整理。
    三角旗：先有旗杆，然后进入收敛整理（成交量递减）。
    """
    results = []
    n = len(df)
    if n < 40:
        return results

    # 取最近 40 根 K 线
    recent_high = high.iloc[-40:]
    recent_low = low.iloc[-40:]
    recent_close = close.iloc[-40:]

    # 检测旗杆：过去 40 根中最大的 10 根涨跌幅
    returns_10 = recent_close.pct_change(10).dropna()
    if len(returns_10) < 5:
        return results

    max_idx = returns_10.idxmax()
    min_idx = returns_10.idxmin()

    max_ret = returns_10.loc[max_idx]
    min_ret = returns_10.loc[min_idx]

    # 如果最大涨幅 > 15%，可能有上升旗形
    if max_ret > 0.15:
        # 旗杆后的走势特征
        pole_end_pos = recent_high.index.get_loc(max_idx)
        if pole_end_pos < len(recent_high) - 10:
            consolidation_high = recent_high.iloc[pole_end_pos + 1:]
            consolidation_low = recent_low.iloc[pole_end_pos + 1:]
            if len(consolidation_high) >= 10:
                # 整理区间：高点和低点变化范围 < 10%
                consol_range = (consolidation_high.max() - consolidation_low.min()) / consolidation_low.min()
                if consol_range < 0.10:
                    results.append({
                        "pattern": "bull_flag",
                        "type": "bullish",
                        "pole_move_pct": round(float(max_ret) * 100, 2),
                        "consolidation_days": len(consolidation_high),
                        "consolidation_range_pct": round(float(consol_range) * 100, 2),
                        "confidence": "medium",
                    })

    # 如果最大跌幅 > 15%，可能有下降旗形
    if abs(min_ret) > 0.15:
        pole_end_pos = recent_low.index.get_loc(min_idx)
        if pole_end_pos < len(recent_low) - 10:
            consolidation_high = recent_high.iloc[pole_end_pos + 1:]
            consolidation_low = recent_low.iloc[pole_end_pos + 1:]
            if len(consolidation_high) >= 10:
                consol_range = (consolidation_high.max() - consolidation_low.min()) / consolidation_low.min()
                if consol_range < 0.10:
                    results.append({
                        "pattern": "bear_flag",
                        "type": "bearish",
                        "pole_move_pct": round(float(min_ret) * 100, 2),
                        "consolidation_days": len(consolidation_high),
                        "consolidation_range_pct": round(float(consol_range) * 100, 2),
                        "confidence": "medium",
                    })

    return results


def _detect_channel(
    peaks: np.ndarray, peak_prices: np.ndarray,
    troughs: np.ndarray, trough_prices: np.ndarray,
    high: pd.Series, low: pd.Series,
) -> list:
    """
    检测通道形态（平行支撑和阻力线）。
    """
    results = []

    if len(peaks) < 3 or len(troughs) < 3:
        return results

    recent_peaks = peaks[-6:]
    recent_peak_prices = peak_prices[-6:]
    recent_troughs = troughs[-6:]
    recent_trough_prices = trough_prices[-6:]

    if len(recent_peaks) >= 3 and len(recent_troughs) >= 3:
        # 用线性回归拟合通道上下轨
        peak_slope, peak_intercept = np.polyfit(
            np.array([float(i) for i in range(len(recent_peaks))]),
            recent_peak_prices, 1
        )
        trough_slope, trough_intercept = np.polyfit(
            np.array([float(i) for i in range(len(recent_troughs))]),
            recent_trough_prices, 1
        )

        avg_price = (np.mean(recent_peak_prices) + np.mean(recent_trough_prices)) / 2.0
        slope_diff_pct = abs(peak_slope - trough_slope) / avg_price * 100 if avg_price > 0 else 0

        # 上下轨斜率接近（平行），且通道宽度合理
        if slope_diff_pct < 0.5:
            channel_height = (recent_peak_prices[-1] - recent_trough_prices[-1]) / recent_trough_prices[-1] * 100
            if 2 < channel_height < 30:
                direction = "up" if peak_slope > 0 else ("down" if peak_slope < 0 else "horizontal")
                results.append({
                    "pattern": "channel",
                    "type": "horizontal" if direction == "horizontal" else f"{direction}trend_channel",
                    "channel_height_pct": round(channel_height, 2),
                    "resistance_slope": round(float(peak_slope), 4),
                    "support_slope": round(float(trough_slope), 4),
                    "current_resistance": round(float(peak_intercept + peak_slope * (len(recent_peaks) - 1)), 2),
                    "current_support": round(float(trough_intercept + trough_slope * (len(recent_troughs) - 1)), 2),
                    "confidence": "medium",
                })

    return results


# ============================================================
#  Tool: 经典技术形态识别
# ============================================================

@tool
@register_tool(
    tool_id="get_chart_patterns",
    name="经典技术形态识别",
    description=(
        "基于 OHLC 数据自动识别头肩顶/底、双顶/双底、三角、旗形、通道五大类经典技术形态。"
        "这里的“形态/缺口/图形”属于 K 线价格技术分析语境，不用于 Agent 工坊能力缺口、工具缺口、数据缺失或财务缺口分析。"
    ),
    category="technical",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["technical_analysis", "chart_patterns"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["chart_pattern_recognition", "technical_patterns"],
    when_to_use="当需要自动识别股票 K 线图中的经典技术形态（头肩、双顶、三角等）和价格图形结构时使用。",
    when_not_to_use="数据不足（少于 60 根 K 线）时检测可靠性不足；不适用于分时或分钟级别数据；不用于 Agent 工坊能力 gap、数据缺口、财务风险缺口或现金流/估值分析。",
    returns="返回 JSON，包含 symbol、current_price、date、patterns 列表（每个形态含类型、价格、置信度）、data_quality。",
    example="get_chart_patterns(symbol='600519', lookback_days=180, pattern_types='all')",
    related_tools=["get_support_resistance_levels", "get_candlestick_patterns", "get_fibonacci_retracement", "get_fibonacci_extension"],
)
def get_chart_patterns(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"],
    lookback_days: Annotated[int, "回看天数用于形态识别，默认180"] = 180,
    pattern_types: Annotated[str, "形态类型筛选，逗号分隔：head_shoulders,double_top_bottom,triangle,flag,channel,all"] = "all",
) -> str:
    """识别股票经典技术形态，自动识别头肩顶/底、双顶/双底、三角、旗形、通道五大类形态。

    Args:
        symbol: A 股股票代码，如 600519、000001
        lookback_days: 回看天数用于形态识别，默认 180
        pattern_types: 形态类型筛选，逗号分隔，取值 "head_shoulders" | "double_top_bottom" | "triangle" | "flag" | "channel" | "all"，默认 "all"

    Returns:
        str: JSON 字符串，正常返回字段说明——
            symbol: 股票代码
            current_price: 最新收盘价
            date: 最新交易日
            patterns: 形态列表，每个元素结构因形态而异，公共字段 —
                pattern: 形态名称，取值如 "head_and_shoulders_top" | "head_and_shoulders_bottom" | "double_top" | "double_bottom" | "symmetrical_triangle" | "ascending_triangle" | "descending_triangle" | "bull_flag" | "bear_flag" | "channel"
                type: 形态子类型/方向，取值如 "top" | "bottom" | "bullish" | "bearish" | "neutral" | "horizontal" | "uptrend_channel" | "downtrend_channel"
                confidence: 置信度，取值 "high" | "medium"
                （附加字段因形态不同而异，如 left_shoulder_price、head_price、right_shoulder_price、neckline、break_down_target、break_up_target、peak1_price、peak2_price、valley_price、trough1_price、trough2_price、bar_distance、peak_trend_slope_pct、trough_trend_slope_pct、bars_to_apex、pole_move_pct、consolidation_days、consolidation_range_pct、channel_height_pct、resistance_slope、support_slope、current_resistance、current_support）
            note: 可选，未检测到形态时的说明文本
            data_quality: 数据质量，子字段 —
                bars_analyzed: 分析的 K 线数量
                peaks_detected: 检测到的峰值数
                troughs_detected: 检测到的谷值数
                patterns_found: 检测到的形态数量
        异常时返回字段 —
            status: "error"
            message: 错误信息
    """
    try:
        from core.skill_runtime.data_access import get_stock_daily_quotes

        today = datetime.date.today()
        end = today.strftime("%Y%m%d")
        start = (today - datetime.timedelta(days=int(lookback_days) + 50)).strftime("%Y%m%d")
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

        latest = df.iloc[-1]
        current_price = float(latest["close"])
        latest_date = str(latest["trade_date"])

        high = df["high"]
        low = df["low"]
        close = df["close"]
        volume = df["volume"] if "volume" in df.columns else pd.Series(0, index=df.index)

        # 峰谷检测
        peak_indices, trough_indices = _find_peaks_and_troughs(high, low, n=5)
        peak_prices = high.loc[peak_indices].to_numpy() if len(peak_indices) > 0 else np.array([])
        trough_prices = low.loc[trough_indices].to_numpy() if len(trough_indices) > 0 else np.array([])

        # 过滤连续极值
        peak_indices = np.array(_filter_consecutive_extrema(peak_indices, high), dtype=int)
        trough_indices = np.array(_filter_consecutive_extrema(trough_indices, low), dtype=int)
        peak_prices = high.iloc[peak_indices].to_numpy() if len(peak_indices) > 0 else np.array([])
        trough_prices = low.iloc[trough_indices].to_numpy() if len(trough_indices) > 0 else np.array([])

        patterns_found = []
        types_to_check = [t.strip() for t in str(pattern_types).lower().split(",")]

        # 1. 头肩顶/底
        if "all" in types_to_check or "head_shoulders" in types_to_check:
            if len(peak_indices) >= 3:
                patterns_found.extend(
                    _detect_head_shoulders(peak_indices, peak_prices, volume)
                )
            if len(trough_indices) >= 3:
                patterns_found.extend(
                    _detect_inverse_head_shoulders(trough_indices, trough_prices, volume)
                )

        # 2. 双顶/双底
        if "all" in types_to_check or "double_top_bottom" in types_to_check:
            if len(peak_indices) >= 2:
                patterns_found.extend(
                    _detect_double_top(peak_indices, peak_prices, low)
                )
            if len(trough_indices) >= 2:
                patterns_found.extend(
                    _detect_double_bottom(trough_indices, trough_prices, high)
                )

        # 3. 三角形态
        if "all" in types_to_check or "triangle" in types_to_check:
            patterns_found.extend(
                _detect_triangles(peak_indices, peak_prices, trough_indices, trough_prices)
            )

        # 4. 旗形/三角旗
        if "all" in types_to_check or "flag" in types_to_check:
            patterns_found.extend(
                _detect_flag_pennant(df, high, low, close)
            )

        # 5. 通道
        if "all" in types_to_check or "channel" in types_to_check:
            patterns_found.extend(
                _detect_channel(peak_indices, peak_prices, trough_indices, trough_prices, high, low)
            )

        result = {
            "symbol": str(symbol),
            "current_price": round(current_price, 2),
            "date": latest_date,
            "patterns": patterns_found,
            "data_quality": {
                "bars_analyzed": len(df),
                "peaks_detected": len(peak_indices),
                "troughs_detected": len(trough_indices),
                "patterns_found": len(patterns_found),
            },
        }

        if not patterns_found:
            result["note"] = "未检测到明显符合规则的经典技术形态。当前价格区间内无明显头肩、双顶/底、三角、旗形或通道结构。"

        return json.dumps(result, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("经典技术形态识别失败: %s", exc, exc_info=True)
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2, default=str)


__all__ = ["get_chart_patterns"]
