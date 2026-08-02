"""
斐波那契回调/扩展工具

基于近期价格波动的最高点和最低点，自动计算斐波那契回调位和扩展位，
并评估每个价格水平在当前市场中的触及情况和支撑/阻力作用。

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


def _detect_trend(close_series: pd.Series) -> str:
    """根据最近 N/2 根 K 线的收盘价变化判断趋势方向。"""
    n = len(close_series)
    half = max(1, n // 2)
    if close_series.iloc[-1] > close_series.iloc[-half]:
        return "up"
    else:
        return "down"


def _check_touched(
    level_price: float, high: pd.Series, low: pd.Series, bars: int = 5, tolerance: float = 0.005
) -> bool:
    """
    检查最近 bars 根 K 线内价格是否触及过某个水平。

    Args:
        level_price: 价格水平
        high: 最高价序列
        low: 最低价序列
        bars: 检查的最近 K 线根数
        tolerance: 容忍度（比例），默认 0.5%

    Returns:
        bool: 是否触及
    """
    recent_high = high.iloc[-bars:]
    recent_low = low.iloc[-bars:]
    upper_bound = level_price * (1 + tolerance)
    lower_bound = level_price * (1 - tolerance)
    return bool((recent_high >= lower_bound).any() and (recent_low <= upper_bound).any())


def _detect_action(
    level_price: float, close: pd.Series, high: pd.Series, low: pd.Series, lookback: int = 10
) -> str:
    """
    判断某个价格水平在最近 lookback 根 K 线内表现出的作用。

    如果价格从该水平反弹（接触后反转），视为支撑或阻力。
    如果价格直接穿过该水平，视为突破。

    Returns:
        "support", "resistance", "breakout", or ""
    """
    if lookback < 3:
        return ""

    recent_close = close.iloc[-lookback:]
    recent_high = high.iloc[-lookback:]
    recent_low = low.iloc[-lookback:]

    for i in range(2, lookback):
        # 检查是否触及
        prev_high = recent_high.iloc[i - 1]
        prev_low = recent_low.iloc[i - 1]
        curr_close = recent_close.iloc[i]
        prev_close = recent_close.iloc[i - 1]

        upper = level_price * 1.005
        lower = level_price * 0.995

        touched_prev = prev_low <= upper and prev_high >= lower
        if not touched_prev:
            continue

        # 接触后反转判断
        if curr_close > prev_close * 1.01 and prev_close < level_price:
            return "support"
        elif curr_close < prev_close * 0.99 and prev_close > level_price:
            return "resistance"
        elif curr_close > prev_close * 1.02 and prev_close > level_price:
            return "breakout_above"
        elif curr_close < prev_close * 0.98 and prev_close < level_price:
            return "breakout_below"

    return ""


# ============================================================
#  Tool: 斐波那契回调/扩展
# ============================================================

FIB_LEVELS = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
FIB_EXTENSIONS = [1.272, 1.382, 1.618, 2.0, 2.618]


@tool
@register_tool(
    tool_id="get_fibonacci_retracement",
    name="斐波那契回调",
    description="基于近期价格波动的最高点和最低点，自动计算斐波那契回调位和扩展位，评估每个价格水平的支撑/阻力作用。",
    category="technical",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["technical_analysis", "fibonacci"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["fibonacci_retracement", "fibonacci_extension", "price_targets"],
    when_to_use="当需要识别潜在的价格回调支撑/阻力位和趋势扩展目标位时使用。适用于趋势明确的行情。",
    when_not_to_use="震荡市或无明显趋势时，斐波那契水平的参考价值有限；数据不足（少于 30 根 K 线）时不可靠。",
    returns="返回 JSON，包含 symbol、current_price、trend、swing（高点/低点/范围）、retracement_levels（回调位列表）、extension_levels（扩展位列表）、closest_level（最近水平）、data_quality。",
    example="get_fibonacci_retracement(symbol='600519', lookback_days=120, trend_direction='auto', extension_levels=True)",
    related_tools=["get_support_resistance_levels", "get_chart_patterns", "get_fibonacci_extension"],
)
def get_fibonacci_retracement(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"],
    lookback_days: Annotated[int, "回看天数用于计算波动范围，默认120"] = 120,
    trend_direction: Annotated[str, "趋势方向：up（上升趋势回调）、down（下降趋势回调）、auto（自动识别）"] = "auto",
    extension_levels: Annotated[bool, "是否计算扩展位（1.272、1.382、1.618、2.0、2.618）"] = False,
) -> str:
    """计算股票的斐波那契回调位和扩展位，评估每个价格水平的支撑/阻力作用。

    Args:
        symbol: A 股股票代码，如 600519、000001
        lookback_days: 回看天数用于计算波动范围，默认 120
        trend_direction: 趋势方向，取值 "up"（上升趋势回调） | "down"（下降趋势回调） | "auto"（自动识别），默认 "auto"
        extension_levels: 是否计算扩展位（1.272、1.382、1.618、2.0、2.618），默认 False

    Returns:
        str: JSON 字符串，正常返回字段说明——
            symbol: 股票代码
            current_price: 最新收盘价
            date: 最新交易日
            trend: 实际使用的趋势方向，取值 "up" | "down"
            swing: 波动区间，子字段 —
                high: 区间最高价
                low: 区间最低价
                range: 区间振幅
            retracement_levels: 回调位列表，每个元素结构 —
                level: 斐波那契比例（0.0、0.236、0.382、0.5、0.618、0.786、1.0）
                price: 对应价格
                distance_pct: 距离当前价的百分比
                touched: 是否被触及
                action: 可选，价格行为，取值 "bounce_above" | "breakout_above" | "breakout_below"（仅 touched 时存在）
            closest_level: 最近的水平（结构同 retracement_levels 元素，并附加 role 字段） —
                role: 价格角色，取值 "resistance" | "support" | "current"
            extension_levels: 可选，扩展位列表（仅 extension_levels=True 时存在），元素结构 —
                level: 扩展比例（1.272、1.382、1.618、2.0、2.618）
                price: 对应价格
                distance_pct: 距离当前价的百分比
                touched: 是否被触及
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
        start = (today - datetime.timedelta(days=int(lookback_days) + 50)).strftime("%Y%m%d")
        quotes = get_stock_daily_quotes(str(symbol), start, end, limit=int(lookback_days) + 100)

        if not quotes or len(quotes) < 20:
            return json.dumps(
                {"status": "error", "message": f"未获取到 {symbol} 的日线数据，或数据不足20条。"},
                ensure_ascii=False, indent=2, default=str,
            )

        df = pd.DataFrame(quotes)
        for col in ["open", "high", "low", "close"]:
            df[col] = df[col].apply(_safe_float)
        df["trade_date"] = df["trade_date"].astype(str)
        df = df.dropna(subset=["high", "low", "close"]).sort_values("trade_date")
        df = df.reset_index(drop=True)

        if len(df) < 20:
            return json.dumps(
                {"status": "error", "message": f"{symbol} 有效 OHLC 数据不足20条。"},
                ensure_ascii=False, indent=2, default=str,
            )

        latest = df.iloc[-1]
        current_price = float(latest["close"])
        latest_date = str(latest["trade_date"])

        high = df["high"]
        low = df["low"]
        close = df["close"]

        # 确定趋势方向
        trend = str(trend_direction).strip().lower()
        if trend == "auto":
            trend = _detect_trend(close)
        elif trend not in ("up", "down"):
            trend = _detect_trend(close)

        # 计算波动区间
        swing_high = float(high.max())
        swing_low = float(low.min())
        swing_range = swing_high - swing_low

        if swing_range <= 0:
            return json.dumps(
                {"status": "error", "message": f"{symbol} 价格区间异常（最高=最低），无法计算斐波那契水平。"},
                ensure_ascii=False, indent=2, default=str,
            )

        # 计算回调位
        if trend == "up":
            # 上升趋势回调：从低点画到高点
            retracement_levels = []
            for level in FIB_LEVELS:
                level_price = swing_high - level * swing_range
                touched = _check_touched(level_price, high, low, bars=5, tolerance=0.005)
                action = _detect_action(level_price, close, high, low, lookback=10) if touched else ""
                distance_pct = (level_price - current_price) / current_price * 100
                entry = {
                    "level": level,
                    "price": round(level_price, 2),
                    "distance_pct": round(distance_pct, 2),
                    "touched": touched,
                }
                if action:
                    entry["action"] = action
                retracement_levels.append(entry)

            # 扩展位（基于同方向延伸）
            ext_levels = []
            if extension_levels:
                for ext in FIB_EXTENSIONS:
                    ext_price = swing_low + ext * swing_range
                    touched = _check_touched(ext_price, high, low, bars=5, tolerance=0.005)
                    distance_pct = (ext_price - current_price) / current_price * 100
                    entry = {
                        "level": ext,
                        "price": round(ext_price, 2),
                        "distance_pct": round(distance_pct, 2),
                        "touched": touched,
                    }
                    ext_levels.append(entry)

        else:
            # 下降趋势回调：从高点画到低点
            retracement_levels = []
            for level in FIB_LEVELS:
                level_price = swing_low + level * swing_range
                touched = _check_touched(level_price, high, low, bars=5, tolerance=0.005)
                action = _detect_action(level_price, close, high, low, lookback=10) if touched else ""
                distance_pct = (level_price - current_price) / current_price * 100
                entry = {
                    "level": level,
                    "price": round(level_price, 2),
                    "distance_pct": round(distance_pct, 2),
                    "touched": touched,
                }
                if action:
                    entry["action"] = action
                retracement_levels.append(entry)

            # 扩展位（基于同方向延伸）
            ext_levels = []
            if extension_levels:
                for ext in FIB_EXTENSIONS:
                    ext_price = swing_high - ext * swing_range
                    touched = _check_touched(ext_price, high, low, bars=5, tolerance=0.005)
                    distance_pct = (ext_price - current_price) / current_price * 100
                    entry = {
                        "level": ext,
                        "price": round(ext_price, 2),
                        "distance_pct": round(distance_pct, 2),
                        "touched": touched,
                    }
                    ext_levels.append(entry)

        # 最近的水平
        closest_level = min(
            retracement_levels,
            key=lambda x: abs(x["distance_pct"]),
        )

        # 判断最近的 level 的作用角色
        if closest_level["price"] > current_price:
            closest_level["role"] = "resistance"
        elif closest_level["price"] < current_price:
            closest_level["role"] = "support"
        else:
            closest_level["role"] = "current"

        result = {
            "symbol": str(symbol),
            "current_price": round(current_price, 2),
            "date": latest_date,
            "trend": trend,
            "swing": {
                "high": round(swing_high, 2),
                "low": round(swing_low, 2),
                "range": round(swing_range, 2),
            },
            "retracement_levels": retracement_levels,
            "closest_level": closest_level,
            "data_quality": {
                "bars_analyzed": len(df),
            },
        }

        if extension_levels:
            result["extension_levels"] = ext_levels

        return json.dumps(result, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("斐波那契回调/扩展计算失败: %s", exc, exc_info=True)
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2, default=str)


__all__ = ["get_fibonacci_retracement"]
