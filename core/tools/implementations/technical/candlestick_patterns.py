"""
K线形态识别工具

提供 25+ 种经典 K 线形态的自动识别，按三大类组织：
- 单根 K 线形态（7 种）
- 双根 K 线形态（8 种）
- 三根 K 线形态（10 种）

所有形态基于纯数学规则，无需 LLM 参与。
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
#  辅助计算函数
# ============================================================

def _body(row: pd.Series) -> float:
    """实体长度（绝对值）"""
    return abs(row["close"] - row["open"])


def _body_dir(row: pd.Series) -> int:
    """实体方向：1=阳线(green/bull), -1=阴线(red/bear), 0=十字星"""
    diff = row["close"] - row["open"]
    if diff > 0:
        return 1
    elif diff < 0:
        return -1
    return 0


def _upper_shadow(row: pd.Series) -> float:
    """上影线长度"""
    return row["high"] - max(row["open"], row["close"])


def _lower_shadow(row: pd.Series) -> float:
    """下影线长度"""
    return min(row["open"], row["close"]) - row["low"]


def _total_range(row: pd.Series) -> float:
    """K线全长"""
    return row["high"] - row["low"]


def _body_ratio(row: pd.Series, threshold: float = 0.1) -> bool:
    """判断是否为小实体（实体/全长 < threshold）"""
    r = _total_range(row)
    if r == 0:
        return True
    return _body(row) / r < threshold


def _body_center(row: pd.Series) -> float:
    """实体中心位置"""
    return (row["open"] + row["close"]) / 2


def _trend(close_series: pd.Series, window: int = 5) -> str:
    """判断短期趋势：up / down / sideways"""
    if len(close_series) < window:
        return "unknown"
    recent = close_series.iloc[-window:]
    ma = recent.mean()
    first_half = recent.iloc[: window // 2].mean() if window >= 2 else ma
    second_half = recent.iloc[window // 2 :].mean() if window >= 2 else ma
    if second_half > first_half * 1.005:
        return "up"
    elif second_half < first_half * 0.995:
        return "down"
    return "sideways"


def _gap_up(row1: pd.Series, row2: pd.Series) -> bool:
    """row2 相对 row1 向上跳空"""
    return row2["low"] > row1["high"]


def _gap_down(row1: pd.Series, row2: pd.Series) -> bool:
    """row2 相对 row1 向下跳空"""
    return row2["high"] < row1["low"]


def _engulfs(prev: pd.Series, curr: pd.Series) -> bool:
    """curr 是否吞没 prev 的实体"""
    prev_body_high = max(prev["open"], prev["close"])
    prev_body_low = min(prev["open"], prev["close"])
    curr_body_high = max(curr["open"], curr["close"])
    curr_body_low = min(curr["open"], curr["close"])
    return curr_body_high > prev_body_high and curr_body_low < prev_body_low


# ============================================================
#  单根 K 线形态
# ============================================================

def _pattern_doji(row: pd.Series) -> Optional[dict]:
    """十字星：实体极小，上下影线有长度"""
    if _body_ratio(row, 0.03) and _total_range(row) > 0:
        upper = _upper_shadow(row)
        lower = _lower_shadow(row)
        if upper > 0 and lower > 0:
            return {"name": "十字星", "direction": "neutral", "confidence": 0.8}
        if upper > lower * 3 and lower == 0:
            return {"name": "墓碑十字", "direction": "bearish", "confidence": 0.75}
        if lower > upper * 3 and upper == 0:
            return {"name": "蜻蜓十字", "direction": "bullish", "confidence": 0.75}
        return {"name": "十字星", "direction": "neutral", "confidence": 0.6}
    return None


def _pattern_marubozu(row: pd.Series) -> Optional[dict]:
    """光头光脚：几乎没有影线"""
    r = _total_range(row)
    if r == 0:
        return None
    body = _body(row)
    upper_s = _upper_shadow(row)
    lower_s = _lower_shadow(row)
    if body / r > 0.9 and upper_s / r < 0.05 and lower_s / r < 0.05:
        d = _body_dir(row)
        if d == 1:
            return {"name": "光头光脚阳线", "direction": "bullish", "confidence": 0.9}
        elif d == -1:
            return {"name": "光头光脚阴线", "direction": "bearish", "confidence": 0.9}
    return None


def _pattern_hammer(row: pd.Series, trend: str) -> Optional[dict]:
    """锤子线/上吊线：小实体在顶部，长下影线"""
    r = _total_range(row)
    if r == 0:
        return None
    lower = _lower_shadow(row)
    upper = _upper_shadow(row)
    body = _body(row)
    # 下影线 ≥ 2倍实体，上影线 ≤ 10% 实体
    if lower >= 2 * body and body > 0 and upper < body * 0.3:
        center = _body_center(row)
        # 实体在 K 线上半部
        if center > row["low"] + r * 0.6:
            if trend == "down":
                return {"name": "锤子线", "direction": "bullish", "confidence": 0.85}
            elif trend == "up":
                return {"name": "上吊线", "direction": "bearish", "confidence": 0.7}
            return {"name": "锤子线形态", "direction": "neutral", "confidence": 0.5}
    return None


def _pattern_inverted_hammer(row: pd.Series, trend: str) -> Optional[dict]:
    """倒锤子/射击之星：小实体在底部，长上影线"""
    r = _total_range(row)
    if r == 0:
        return None
    upper = _upper_shadow(row)
    lower = _lower_shadow(row)
    body = _body(row)
    # 上影线 ≥ 2倍实体，下影线 ≤ 10% 实体
    if upper >= 2 * body and body > 0 and lower < body * 0.3:
        center = _body_center(row)
        # 实体在 K 线下半部
        if center < row["high"] - r * 0.6:
            if trend == "down":
                return {"name": "倒锤子", "direction": "bullish", "confidence": 0.75}
            elif trend == "up":
                return {"name": "射击之星", "direction": "bearish", "confidence": 0.85}
            return {"name": "倒锤子形态", "direction": "neutral", "confidence": 0.5}
    return None


def _pattern_spinning_top(row: pd.Series) -> Optional[dict]:
    """纺锤线：小实体，上下影线都有"""
    r = _total_range(row)
    if r == 0:
        return None
    body = _body(row)
    upper = _upper_shadow(row)
    lower = _lower_shadow(row)
    if 0.05 < body / r < 0.4 and upper > body * 0.5 and lower > body * 0.5:
        return {"name": "纺锤线", "direction": "neutral", "confidence": 0.6}
    return None


def _pattern_belt_hold(row: pd.Series) -> Optional[dict]:
    """捉腰带线：光头阳线或光脚阴线"""
    r = _total_range(row)
    if r == 0:
        return None
    body = _body(row)
    upper = _upper_shadow(row)
    lower = _lower_shadow(row)
    if body / r > 0.7:
        if upper / r < 0.05 and _body_dir(row) == 1:
            return {"name": "阳线捉腰带线", "direction": "bullish", "confidence": 0.7}
        if lower / r < 0.05 and _body_dir(row) == -1:
            return {"name": "阴线捉腰带线", "direction": "bearish", "confidence": 0.7}
    return None


# ============================================================
#  双根 K 线形态
# ============================================================

def _pattern_engulfing(prev: pd.Series, curr: pd.Series) -> Optional[dict]:
    """吞没形态"""
    if _engulfs(prev, curr):
        prev_dir = _body_dir(prev)
        curr_dir = _body_dir(curr)
        if prev_dir == -1 and curr_dir == 1:
            return {"name": "阳线吞没", "direction": "bullish", "confidence": 0.85}
        elif prev_dir == 1 and curr_dir == -1:
            return {"name": "阴线吞没", "direction": "bearish", "confidence": 0.85}
    return None


def _pattern_piercing(prev: pd.Series, curr: pd.Series) -> Optional[dict]:
    """刺透形态（阳线）"""
    if _body_dir(prev) == -1 and _body_dir(curr) == 1:
        prev_close = prev["close"]
        prev_open = prev["open"]
        curr_open = curr["open"]
        curr_close = curr["close"]
        prev_body_mid = (prev_open + prev_close) / 2
        # curr 开在 prev 实体下方，收在 prev 实体中点上方
        if curr_open < prev_close and curr_close > prev_body_mid and curr_close < prev_open:
            return {"name": "刺透形态", "direction": "bullish", "confidence": 0.8}
    return None


def _pattern_dark_cloud(prev: pd.Series, curr: pd.Series) -> Optional[dict]:
    """乌云盖顶（阴线）"""
    if _body_dir(prev) == 1 and _body_dir(curr) == -1:
        prev_close = prev["close"]
        prev_open = prev["open"]
        curr_open = curr["open"]
        curr_close = curr["close"]
        prev_body_mid = (prev_open + prev_close) / 2
        # curr 开在 prev 实体上方，收在 prev 实体中点下方
        if curr_open > prev_close and curr_close < prev_body_mid and curr_close > prev_open:
            return {"name": "乌云盖顶", "direction": "bearish", "confidence": 0.8}
    return None


def _pattern_harami(prev: pd.Series, curr: pd.Series) -> Optional[dict]:
    """孕线：前一根大实体，后一根小实体在其内部"""
    if _engulfs(curr, prev):  # prev 吞没 curr = curr 在 prev 内部
        prev_body = _body(prev)
        curr_body = _body(curr)
        if prev_body > 0 and curr_body / prev_body < 0.5:
            prev_dir = _body_dir(prev)
            curr_dir = _body_dir(curr)
            if prev_dir == -1 and curr_dir == 1:
                return {"name": "阳线孕线", "direction": "bullish", "confidence": 0.7}
            elif prev_dir == -1 and curr_dir == -1:
                return {"name": "阳线孕线(阴)", "direction": "bullish", "confidence": 0.5}
            elif prev_dir == 1 and curr_dir == -1:
                return {"name": "阴线孕线", "direction": "bearish", "confidence": 0.7}
            elif prev_dir == 1 and curr_dir == 1:
                return {"name": "阴线孕线(阳)", "direction": "bearish", "confidence": 0.5}
    return None


def _pattern_harami_cross(prev: pd.Series, curr: pd.Series) -> Optional[dict]:
    """十字孕线：孕线中后一根为十字星"""
    if _engulfs(curr, prev) and _body_ratio(curr, 0.03):
        prev_dir = _body_dir(prev)
        if prev_dir == -1:
            return {"name": "阳线十字孕线", "direction": "bullish", "confidence": 0.8}
        elif prev_dir == 1:
            return {"name": "阴线十字孕线", "direction": "bearish", "confidence": 0.8}
    return None


def _pattern_tweezer(prev: pd.Series, curr: pd.Series) -> Optional[dict]:
    """平头/平底：两根 K 线高低点几乎相同"""
    r1 = _total_range(prev)
    r2 = _total_range(curr)
    avg_r = (r1 + r2) / 2
    if avg_r == 0:
        return None
    threshold = avg_r * 0.05
    prev_dir = _body_dir(prev)
    curr_dir = _body_dir(curr)

    # 平底：low 相近
    if abs(prev["low"] - curr["low"]) < threshold:
        if prev_dir == -1 and curr_dir == 1:
            return {"name": "平底形态", "direction": "bullish", "confidence": 0.65}
    # 平顶：high 相近
    if abs(prev["high"] - curr["high"]) < threshold:
        if prev_dir == 1 and curr_dir == -1:
            return {"name": "平顶形态", "direction": "bearish", "confidence": 0.65}
    return None


def _pattern_kicking(prev: pd.Series, curr: pd.Series) -> Optional[dict]:
    """反击线（约会线）：两根反向大实体，开盘点相近"""
    prev_body = _body(prev)
    curr_body = _body(curr)
    prev_r = _total_range(prev)
    curr_r = _total_range(curr)
    if prev_r == 0 or curr_r == 0:
        return None
    # 两根都是大实体
    if prev_body / prev_r < 0.6 or curr_body / curr_r < 0.6:
        return None
    prev_dir = _body_dir(prev)
    curr_dir = _body_dir(curr)
    if prev_dir == -1 and curr_dir == 1:
        if abs(prev["open"] - curr["open"]) < curr_body * 0.2:
            return {"name": "阳线反击线", "direction": "bullish", "confidence": 0.7}
    elif prev_dir == 1 and curr_dir == -1:
        if abs(prev["open"] - curr["open"]) < curr_body * 0.2:
            return {"name": "阴线反击线", "direction": "bearish", "confidence": 0.7}
    return None


# ============================================================
#  三根 K 线形态
# ============================================================

def _pattern_morning_star(r1: pd.Series, r2: pd.Series, r3: pd.Series) -> Optional[dict]:
    """晨星：阴线 → 小实体(跳空低) → 阳线(跳空高，收过半)"""
    if not (_body_dir(r1) == -1 and _body_dir(r3) == 1):
        return None
    r1_body_center = _body_center(r1)
    # r2 小实体 + 在 r1 下方
    if not (_body_ratio(r2, 0.4) and r2["high"] < r1_body_center):
        return None
    # r3 收在 r1 实体中点以上
    r1_body_mid = (r1["open"] + r1["close"]) / 2
    if r3["close"] > r1_body_mid:
        return {"name": "晨星", "direction": "bullish", "confidence": 0.85}
    return None


def _pattern_evening_star(r1: pd.Series, r2: pd.Series, r3: pd.Series) -> Optional[dict]:
    """黄昏之星：阳线 → 小实体(跳空高) → 阴线(跳空低，收过半)"""
    if not (_body_dir(r1) == 1 and _body_dir(r3) == -1):
        return None
    r1_body_center = _body_center(r1)
    # r2 小实体 + 在 r1 上方
    if not (_body_ratio(r2, 0.4) and r2["low"] > r1_body_center):
        return None
    # r3 收在 r1 实体中点以下
    r1_body_mid = (r1["open"] + r1["close"]) / 2
    if r3["close"] < r1_body_mid:
        return {"name": "黄昏之星", "direction": "bearish", "confidence": 0.85}
    return None


def _pattern_three_white_soldiers(r1: pd.Series, r2: pd.Series, r3: pd.Series) -> Optional[dict]:
    """三白兵(红三兵)：三根连续增长的阳线"""
    if not (_body_dir(r1) == 1 and _body_dir(r2) == 1 and _body_dir(r3) == 1):
        return None
    b1, b2, b3 = _body(r1), _body(r2), _body(r3)
    if b1 == 0 or b2 == 0:
        return None
    # 实体递增
    if not (b3 > b2 * 0.8 and b2 > b1 * 0.8):
        return None
    # 收盘价递增
    if not (r3["close"] > r2["close"] and r2["close"] > r1["close"]):
        return None
    # 上影线较短
    if _upper_shadow(r3) / b3 < 0.3:
        return {"name": "三白兵(红三兵)", "direction": "bullish", "confidence": 0.8}
    return None


def _pattern_three_black_crows(r1: pd.Series, r2: pd.Series, r3: pd.Series) -> Optional[dict]:
    """三只乌鸦：三根连续增长的阴线"""
    if not (_body_dir(r1) == -1 and _body_dir(r2) == -1 and _body_dir(r3) == -1):
        return None
    b1, b2, b3 = _body(r1), _body(r2), _body(r3)
    if b1 == 0 or b2 == 0:
        return None
    # 实体递增
    if not (b3 > b2 * 0.8 and b2 > b1 * 0.8):
        return None
    # 收盘价递减
    if not (r3["close"] < r2["close"] and r2["close"] < r1["close"]):
        return None
    # 下影线较短
    if _lower_shadow(r3) / b3 < 0.3:
        return {"name": "三只乌鸦", "direction": "bearish", "confidence": 0.8}
    return None


def _pattern_three_inside_up(r1: pd.Series, r2: pd.Series, r3: pd.Series) -> Optional[dict]:
    """三内升：阴线 → 阳孕线 → 阳线突破"""
    if not (_body_dir(r1) == -1 and _engulfs(r2, r1) and _body_dir(r3) == 1):
        return None
    if r3["close"] > r1["open"]:
        return {"name": "三内升", "direction": "bullish", "confidence": 0.75}
    return None


def _pattern_three_inside_down(r1: pd.Series, r2: pd.Series, r3: pd.Series) -> Optional[dict]:
    """三内降：阳线 → 阴孕线 → 阴线跌破"""
    if not (_body_dir(r1) == 1 and _engulfs(r2, r1) and _body_dir(r3) == -1):
        return None
    if r3["close"] < r1["open"]:
        return {"name": "三内降", "direction": "bearish", "confidence": 0.75}
    return None


def _pattern_three_outside_up(r1: pd.Series, r2: pd.Series, r3: pd.Series) -> Optional[dict]:
    """三外升：阴线 → 阳吞没 → 阳线确认"""
    if not (_body_dir(r1) == -1 and _engulfs(r1, r2) and _body_dir(r2) == 1):
        return None
    if _body_dir(r3) == 1 and r3["close"] > r2["close"]:
        return {"name": "三外升", "direction": "bullish", "confidence": 0.8}
    return None


def _pattern_three_outside_down(r1: pd.Series, r2: pd.Series, r3: pd.Series) -> Optional[dict]:
    """三外降：阳线 → 阴吞没 → 阴线确认"""
    if not (_body_dir(r1) == 1 and _engulfs(r1, r2) and _body_dir(r2) == -1):
        return None
    if _body_dir(r3) == -1 and r3["close"] < r2["close"]:
        return {"name": "三外降", "direction": "bearish", "confidence": 0.8}
    return None


def _pattern_abandoned_baby(r1: pd.Series, r2: pd.Series, r3: pd.Series) -> Optional[dict]:
    """弃婴形态：晨星/黄昏之星中 r2 为十字星且有跳空"""
    if not _body_ratio(r2, 0.05):
        return None
    if _body_dir(r1) == -1 and _body_dir(r3) == 1:
        if _gap_down(r1, r2) and _gap_up(r2, r3):
            return {"name": "底部弃婴", "direction": "bullish", "confidence": 0.9}
    elif _body_dir(r1) == 1 and _body_dir(r3) == -1:
        if _gap_up(r1, r2) and _gap_down(r2, r3):
            return {"name": "顶部弃婴", "direction": "bearish", "confidence": 0.9}
    return None


# ============================================================
#  四根及以上 K 线形态
# ============================================================

def _pattern_rising_window(df_window: pd.DataFrame) -> Optional[dict]:
    """上升三法：阳线 → 三根小阴线在阳线内 → 大阳线突破"""
    if len(df_window) < 5:
        return None
    r1 = df_window.iloc[0]
    r5 = df_window.iloc[-1]
    if not (_body_dir(r1) == 1 and _body_dir(r5) == 1):
        return None
    r1_high = max(r1["open"], r1["close"])
    r1_low = min(r1["open"], r1["close"])
    # r2, r3, r4 都在 r1 实体范围内
    for i in [1, 2, 3]:
        row = df_window.iloc[i]
        if _body_dir(row) >= 0:
            return None
        if row["high"] > r1_high or row["low"] < r1_low:
            return None
    if r5["close"] > r1_high:
        return {"name": "上升三法", "direction": "bullish", "confidence": 0.75}
    return None


def _pattern_falling_window(df_window: pd.DataFrame) -> Optional[dict]:
    """下降三法：阴线 → 三根小阳线在阴线内 → 大阴线跌破"""
    if len(df_window) < 5:
        return None
    r1 = df_window.iloc[0]
    r5 = df_window.iloc[-1]
    if not (_body_dir(r1) == -1 and _body_dir(r5) == -1):
        return None
    r1_high = max(r1["open"], r1["close"])
    r1_low = min(r1["open"], r1["close"])
    for i in [1, 2, 3]:
        row = df_window.iloc[i]
        if _body_dir(row) <= 0:
            return None
        if row["high"] > r1_high or row["low"] < r1_low:
            return None
    if r5["close"] < r1_low:
        return {"name": "下降三法", "direction": "bearish", "confidence": 0.75}
    return None


# ============================================================
#  工具注册与主函数
# ============================================================

@tool
@register_tool(
    tool_id="get_candlestick_patterns",
    name="K线形态识别",
    description=(
        "基于 OHLC 数据自动识别 25+ 种经典 K 线形态，包括十字星、锤子线、吞没、"
        "晨星/黄昏之星、三白兵/三只乌鸦等。返回结构化 JSON，包含形态名称、方向、"
        "置信度和发生日期。"
    ),
    category="technical",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["candlestick_patterns", "technical_pattern_recognition", "price_action"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["K线形态识别", "价格行为分析"],
    when_to_use=(
        "当需要识别 K 线形态信号（反转信号/持续信号）时使用。"
        "适用于短期择时、入场/出场时机判断、支撑/压力位附近的反转确认。"
    ),
    when_not_to_use=(
        "不适合需要完整趋势判断（应结合趋势分析工具）、"
        "不适合基本面分析、不适合中长期估值判断。"
        "形态识别仅为概率信号，不能替代综合判断。"
    ),
    returns=(
        "返回 JSON 字符串，包含 patterns 数组、summary、data_info。"
        "每个 pattern 包含 date、name、direction(bullish/bearish/neutral)、confidence(0-1)。"
    ),
    example="get_candlestick_patterns(symbol='600519', lookback_days=60)",
    related_tools=[
        "get_technical_indicators",
        "get_technical_factor_bundle_tool",
        "get_stock_market_data_unified",
        "get_chart_patterns",
        "get_crossover_signals",
    ],
)
def get_candlestick_patterns(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"],
    lookback_days: Annotated[int, "回溯天数，默认 60"] = 60,
    trend_window: Annotated[int, "趋势判断窗口（日），默认 5"] = 5,
    min_confidence: Annotated[float, "最小置信度阈值 (0-1)，默认 0.5"] = 0.5,
) -> str:
    """识别 K 线形态，自动识别 25+ 种经典 K 线形态（十字星、锤子线、吞没、晨星/黄昏之星等）。

    Args:
        symbol: A 股股票代码，如 600519、000001
        lookback_days: 回溯天数，默认 60
        trend_window: 趋势判断窗口（日），默认 5
        min_confidence: 最小置信度阈值 (0-1)，默认 0.5

    Returns:
        str: JSON 字符串，正常返回字段说明——
            symbol: 股票代码
            data_info: 数据信息，子字段 —
                total_bars: K 线总数
                date_range: 日期范围，子字段 —
                    start: 起始日期
                    end: 结束日期
            patterns_found: 识别到的形态总数
            summary: 汇总统计，子字段 —
                bullish: 阳线形态数量
                bearish: 阴线形态数量
                neutral: 中性形态数量
            patterns: 形态列表，每个元素结构 —
                date: 交易日期
                index: K 线索引
                name: 形态名称（如 "十字星"、"锤子线"、"阳线吞没"）
                direction: 方向，取值 "bullish" | "bearish" | "neutral"
                confidence: 置信度 (0-1)
                close: 该日收盘价
        异常时返回字段 —
            status: "no_data" | "error"
            message: 错误信息
    """
    try:
        from core.skill_runtime.data_access import get_stock_daily_quotes

        data = get_stock_daily_quotes(
            symbol=symbol,
            start_date=(datetime.date.today() - datetime.timedelta(days=lookback_days + 30)).strftime("%Y%m%d"),
            end_date=datetime.date.today().strftime("%Y%m%d"),
            limit=lookback_days + 20,
        )
        if not data or len(data) < 10:
            return json.dumps(
                {"status": "no_data", "message": f"股票 {symbol} 数据不足，至少需要 10 个交易日数据"},
                ensure_ascii=False, indent=2, default=str,
            )

        df = pd.DataFrame(data)
        # 标准化列名
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

        required_cols = {"open", "high", "low", "close"}
        if not required_cols.issubset(df.columns):
            missing = required_cols - set(df.columns)
            return json.dumps(
                {"status": "error", "message": f"缺少必要列: {missing}，实际列: {list(df.columns)}"},
                ensure_ascii=False, indent=2, default=str,
            )

        # 按日期排序
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date").reset_index(drop=True)

        # 截取最近的 lookback_days
        df = df.tail(lookback_days).copy()
        close_series = df["close"]

        patterns = []

        # 遍历每根 K 线
        for i in range(len(df)):
            row = df.iloc[i]
            trend = _trend(close_series.iloc[: i + 1], trend_window) if i >= trend_window else "unknown"

            # 单根形态
            for fn in [
                _pattern_doji,
                _pattern_marubozu,
                _pattern_spinning_top,
                _pattern_belt_hold,
            ]:
                result = fn(row)
                if result and result["confidence"] >= min_confidence:
                    _append_pattern(patterns, df, i, result)

            # 需要趋势上下文的单根形态
            if trend != "unknown":
                for fn in [_pattern_hammer, _pattern_inverted_hammer]:
                    result = fn(row, trend)
                    if result and result["confidence"] >= min_confidence:
                        _append_pattern(patterns, df, i, result)

            # 双根形态
            if i >= 1:
                prev = df.iloc[i - 1]
                for fn in [
                    _pattern_engulfing,
                    _pattern_piercing,
                    _pattern_dark_cloud,
                    _pattern_harami,
                    _pattern_harami_cross,
                    _pattern_tweezer,
                    _pattern_kicking,
                ]:
                    result = fn(prev, row)
                    if result and result["confidence"] >= min_confidence:
                        _append_pattern(patterns, df, i, result)

            # 三根形态
            if i >= 2:
                r1, r2, r3 = df.iloc[i - 2], df.iloc[i - 1], row
                for fn in [
                    _pattern_morning_star,
                    _pattern_evening_star,
                    _pattern_three_white_soldiers,
                    _pattern_three_black_crows,
                    _pattern_three_inside_up,
                    _pattern_three_inside_down,
                    _pattern_three_outside_up,
                    _pattern_three_outside_down,
                    _pattern_abandoned_baby,
                ]:
                    result = fn(r1, r2, r3)
                    if result and result["confidence"] >= min_confidence:
                        _append_pattern(patterns, df, i, result)

            # 五根形态（上升/下降三法）
            if i >= 4:
                window = df.iloc[i - 4 : i + 1]
                for fn in [_pattern_rising_window, _pattern_falling_window]:
                    result = fn(window)
                    if result and result["confidence"] >= min_confidence:
                        _append_pattern(patterns, df, i, result)

        # 统计摘要
        bullish_count = sum(1 for p in patterns if p["direction"] == "bullish")
        bearish_count = sum(1 for p in patterns if p["direction"] == "bearish")

        # 按日期去重（同一天同一形态只保留置信度最高的）
        seen = {}
        for p in patterns:
            key = (p["date"], p["name"])
            if key not in seen or p["confidence"] > seen[key]["confidence"]:
                seen[key] = p
        patterns = sorted(seen.values(), key=lambda x: x["date"], reverse=True)

        payload = {
            "symbol": symbol,
            "data_info": {
                "total_bars": len(df),
                "date_range": {
                    "start": str(df.iloc[0].get("date", ""))[:10] if "date" in df.columns else "N/A",
                    "end": str(df.iloc[-1].get("date", ""))[:10] if "date" in df.columns else "N/A",
                },
            },
            "patterns_found": len(patterns),
            "summary": {
                "bullish": bullish_count,
                "bearish": bearish_count,
                "neutral": len(patterns) - bullish_count - bearish_count,
            },
            "patterns": patterns,
        }

        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("K线形态识别失败: %s", exc, exc_info=True)
        return json.dumps(
            {"status": "error", "message": f"形态识别失败: {exc}"},
            ensure_ascii=False, indent=2, default=str,
        )


def _append_pattern(patterns: list, df: pd.DataFrame, idx: int, result: dict):
    """辅助：向 patterns 列表中添加识别到的形态"""
    date_str = ""
    if "date" in df.columns:
        date_str = str(df.iloc[idx]["date"])[:10]
    patterns.append({
        "date": date_str,
        "index": idx,
        "name": result["name"],
        "direction": result["direction"],
        "confidence": round(result["confidence"], 2),
        "close": float(df.iloc[idx]["close"]),
    })


__all__ = ["get_candlestick_patterns"]
