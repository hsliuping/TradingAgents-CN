"""
支撑压力位计算工具

基于枢轴点（Pivot Points）和历史价格极值两种方法，自动识别股票的支撑位和压力位。
所有计算基于纯数学规则，无需 LLM 参与。
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Annotated, Optional

import numpy as np
import pandas as pd
from langchain_core.tools import tool

from core.skill_runtime.data_access import get_stock_daily_quotes
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


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _days_ago(days: int) -> str:
    return (datetime.now() - timedelta(days=max(1, int(days)))).strftime("%Y-%m-%d")


def _calc_pivot_points(high: float, low: float, close: float, current_price: float) -> dict:
    """计算标准枢轴点及支撑阻力位。"""
    pivot = (high + low + close) / 3.0

    resistances = [
        {"level": "R1", "price": round(2 * pivot - low, 2)},
        {"level": "R2", "price": round(pivot + (high - low), 2)},
        {"level": "R3", "price": round(high + 2 * (pivot - low), 2)},
    ]
    # Mid-points
    r1_price = resistances[0]["price"]
    r2_price = resistances[1]["price"]
    resistances.append({"level": "R1-R2_MP", "price": round((r1_price + r2_price) / 2, 2)})

    supports = [
        {"level": "S1", "price": round(2 * pivot - high, 2)},
        {"level": "S2", "price": round(pivot - (high - low), 2)},
        {"level": "S3", "price": round(low - 2 * (high - pivot), 2)},
    ]
    s1_price = supports[0]["price"]
    s2_price = supports[1]["price"]
    supports.append({"level": "S1-S2_MP", "price": round((s1_price + s2_price) / 2, 2)})

    for item in resistances:
        item["distance_pct"] = round((item["price"] - current_price) / current_price * 100, 2) if current_price > 0 else 0.0
    for item in supports:
        item["distance_pct"] = round((item["price"] - current_price) / current_price * 100, 2) if current_price > 0 else 0.0

    return {
        "pivot": round(pivot, 2),
        "resistances": resistances,
        "supports": supports,
    }


def _find_local_extrema(prices: np.ndarray, n_neighbors: int = 5) -> tuple:
    """识别局部极值点——峰值（阻力候选）和谷值（支撑候选）。"""
    highs = np.array([_safe_float(row["high"]) or 0 for row in prices])
    lows = np.array([_safe_float(row["low"]) or 0 for row in prices])

    peak_indices = []
    trough_indices = []

    for i in range(n_neighbors, len(highs) - n_neighbors):
        is_peak = True
        is_trough = True
        for j in range(1, n_neighbors + 1):
            if highs[i] <= highs[i - j] or highs[i] <= highs[i + j]:
                is_peak = False
            if lows[i] >= lows[i - j] or lows[i] >= lows[i + j]:
                is_trough = False
        if is_peak:
            peak_indices.append(i)
        if is_trough:
            trough_indices.append(i)

    peak_levels = [float(highs[i]) for i in peak_indices]
    trough_levels = [float(lows[i]) for i in trough_indices]

    return peak_levels, trough_levels


def _cluster_levels(levels: list, threshold_pct: float = 0.02) -> list:
    """聚类附近的价格水平（阈值内合并），按触及次数排序。"""
    if not levels:
        return []

    sorted_levels = sorted(set(round(level, 2) for level in levels))
    clusters = []
    current_cluster = [sorted_levels[0]]

    for level in sorted_levels[1:]:
        if (level - current_cluster[-1]) / current_cluster[-1] < threshold_pct:
            current_cluster.append(level)
        else:
            clusters.append(current_cluster)
            current_cluster = [level]
    clusters.append(current_cluster)

    result = []
    for cluster in clusters:
        avg_price = round(sum(cluster) / len(cluster), 2)
        touches = len(cluster)
        if touches >= 3:
            strength = "very_strong"
        elif touches >= 2:
            strength = "strong"
        else:
            strength = "moderate"
        result.append({"price": avg_price, "touches": touches, "strength": strength})

    result.sort(key=lambda x: x["touches"], reverse=True)
    return result


def _calc_historical_levels(quotes: list, current_price: float) -> dict:
    """基于历史价格极值计算支撑和阻力位。"""
    prices_data = []
    for q in quotes:
        high_val = _safe_float(q.get("high"))
        low_val = _safe_float(q.get("low"))
        if high_val is not None and low_val is not None:
            prices_data.append({"high": high_val, "low": low_val})

    if len(prices_data) < 30:
        return {"resistances": [], "supports": [], "warnings": ["历史数据不足30条，支撑压力位参考价值有限。"]}

    peak_levels, trough_levels = _find_local_extrema(prices_data, n_neighbors=5)

    resistance_clusters = _cluster_levels(peak_levels)
    support_clusters = _cluster_levels([-level for level in trough_levels])  # 负值排序
    support_clusters_positive = [
        {"price": round(abs(item["price"]), 2), "touches": item["touches"], "strength": item["strength"]}
        for item in support_clusters
    ]

    # Take top 3
    top_resistances = resistance_clusters[:3]
    top_supports = support_clusters_positive[:3]

    # Remove supports above current price and resistances below
    top_resistances = [r for r in top_resistances if r["price"] > current_price * 1.005]
    top_supports = [s for s in top_supports if s["price"] < current_price * 0.995]

    for item in top_resistances:
        item["distance_pct"] = round((item["price"] - current_price) / current_price * 100, 2) if current_price > 0 else 0.0
    for item in top_supports:
        item["distance_pct"] = round((item["price"] - current_price) / current_price * 100, 2) if current_price > 0 else 0.0

    return {"resistances": top_resistances, "supports": top_supports, "warnings": []}


# ============================================================
#  Tool: 支撑压力位计算
# ============================================================

@tool
@register_tool(
    tool_id="get_support_resistance_levels",
    name="支撑压力位计算",
    description="基于枢轴点公式和历史价格极值聚类，计算股票的关键支撑位和压力位。",
    category="technical",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["technical_analysis", "support_resistance", "price_levels", "pivot"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["支撑压力位", "关键价格水平"],
    when_to_use="当需要识别股票的关键支撑/压力价格区间，辅助入场离场决策时使用。",
    when_not_to_use="当数据不足（少于20条K线）时，结果参考价值有限。",
    returns="返回 JSON，包含 symbol、current_price、date、pivot_points（枢轴点）、historical_levels（历史极值聚类）、data_quality。",
    example="get_support_resistance_levels(symbol='600519', lookback_days=120, method='all')",
    related_tools=["get_candlestick_patterns", "get_crossover_signals", "get_pivot_points", "get_fibonacci_retracement"],
)
def get_support_resistance_levels(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"],
    lookback_days: Annotated[int, "回看天数，默认120"] = 120,
    method: Annotated[str, "计算方法：pivot（枢轴点）、historical（历史极值聚类）、all（两者都计算）"] = "all",
) -> str:
    """计算股票支撑位和压力位，基于枢轴点公式和历史价格极值聚类。

    Args:
        symbol: A 股股票代码，如 600519、000001
        lookback_days: 回看天数，默认 120
        method: 计算方法，取值 "pivot"（枢轴点） | "historical"（历史极值聚类） | "all"（两者都计算），默认 "all"

    Returns:
        str: JSON 字符串，正常返回字段说明——
            symbol: 股票代码
            current_price: 最新收盘价
            date: 最新交易日
            pivot_points: 枢轴点结果（method 不含 pivot 时为 None），子字段 —
                pivot: 枢轴点价格
                resistances: 阻力位列表，每个元素结构 —
                    level: 阻力位标识，取值 "R1" | "R2" | "R3" | "R1-R2_MP"
                    price: 价格
                    distance_pct: 距离当前价的百分比
                supports: 支撑位列表，每个元素结构 —
                    level: 支撑位标识，取值 "S1" | "S2" | "S3" | "S1-S2_MP"
                    price: 价格
                    distance_pct: 距离当前价的百分比
            historical_levels: 历史极值聚类结果（method 不含 historical 时为 None），子字段 —
                resistances: 阻力位列表，每个元素结构 —
                    price: 价格
                    touches: 触及次数
                    strength: 强度，取值 "very_strong" | "strong" | "moderate"
                    distance_pct: 距离当前价的百分比
                supports: 支撑位列表，元素结构同 resistances
            data_quality: 数据质量，子字段 —
                bars_analyzed: 分析的 K 线数量
                warnings: 警告信息列表
        异常时返回字段 —
            status: "error"
            message: 错误信息
            warnings: 可选，警告信息列表
    """
    try:
        end_date = _today()
        start_date = _days_ago(int(lookback_days) + 60)

        quotes = get_stock_daily_quotes(
            str(symbol), start_date, end_date, limit=int(lookback_days) + 100
        )

        warnings: list = []

        if not quotes or len(quotes) < 5:
            return json.dumps(
                {"status": "error", "message": f"未获取到 {symbol} 的日线数据，或数据不足5条。", "warnings": warnings},
                ensure_ascii=False, indent=2, default=str,
            )

        if len(quotes) < 20:
            warnings.append(f"K线数据仅 {len(quotes)} 条，不足20条，支撑压力位参考价值有限。")

        # Parse quotes into DataFrame for processing
        df = pd.DataFrame(quotes)
        for col in ["open", "high", "low", "close"]:
            df[col] = df[col].apply(_safe_float)
        df["trade_date"] = df["trade_date"].astype(str)
        df = df.dropna(subset=["high", "low", "close"]).sort_values("trade_date")

        if len(df) < 5:
            return json.dumps(
                {"status": "error", "message": f"{symbol} 有效 OHLC 数据不足5条。", "warnings": warnings},
                ensure_ascii=False, indent=2, default=str,
            )

        latest = df.iloc[-1]
        current_price = float(latest["close"])
        latest_date = str(latest["trade_date"])

        chosen_method = str(method).strip().lower()
        if chosen_method not in ("pivot", "historical", "all"):
            chosen_method = "all"
            warnings.append(f"不支持的方法 '{method}'，已回退为 all。")

        result = {
            "symbol": str(symbol),
            "current_price": round(current_price, 2),
            "date": latest_date,
            "pivot_points": None,
            "historical_levels": None,
            "data_quality": {
                "bars_analyzed": len(df),
                "warnings": warnings,
            },
        }

        # Pivot Points
        if chosen_method in ("pivot", "all"):
            # Use the most recent complete period (latest bar)
            last_high = float(latest["high"])
            last_low = float(latest["low"])
            last_close = float(latest["close"])
            pivot_result = _calc_pivot_points(last_high, last_low, last_close, current_price)
            result["pivot_points"] = pivot_result

        # Historical levels
        if chosen_method in ("historical", "all"):
            quotes_list = df.to_dict("records")
            hist_result = _calc_historical_levels(quotes_list, current_price)
            result["historical_levels"] = {
                "resistances": hist_result["resistances"],
                "supports": hist_result["supports"],
            }
            if hist_result.get("warnings"):
                result["data_quality"]["warnings"].extend(hist_result["warnings"])

        return json.dumps(result, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("支撑压力位计算失败: %s", exc, exc_info=True)
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2, default=str)


__all__ = [
    "get_support_resistance_levels",
]
