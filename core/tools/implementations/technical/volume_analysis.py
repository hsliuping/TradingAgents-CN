"""
成交量分析工具

提供以下成交量分析功能：
1. VWAP (成交量加权均价)
2. OBV (能量潮指标)
3. 换手率分析
4. 枢轴点计算
5. 成交量分布
6. 斐波那契扩展

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
    return series.ewm(span=n, adjust=False).mean()


# ============================================================
#  Tool 5: VWAP (成交量加权均价)
# ============================================================

@tool
@register_tool(
    tool_id="get_vwap",
    name="VWAP 成交量加权均价",
    description="计算 VWAP（成交量加权平均价格）及多周期 VWAP 趋势，评估当前价格相对于 VWAP 的偏离程度。",
    category="technical",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["technical_analysis", "vwap"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["vwap_analysis", "volume_weighted_price"],
    when_to_use="当需要评估当前价格相对于平均成交价格的偏离程度、识别买卖压力时使用。",
    when_not_to_use="数据不足（少于 20 根 K 线）时结果不可靠；不适用于分钟级别短线交易。",
    returns="返回 JSON，包含 latest_vwap、current_close、deviation_pct、vwap_trend（5d/20d）。",
    example="get_vwap(symbol='600519', lookback_days=60)",
    related_tools=["get_obv_analysis", "get_turnover_analysis", "get_volume_profile"],
)
def get_vwap(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"],
    lookback_days: Annotated[int, "回看天数用于 VWAP 计算，默认 60"] = 60,
) -> str:
    """计算 VWAP（成交量加权平均价格）及多周期 VWAP 趋势，评估当前价格相对于 VWAP 的偏离程度。

    Args:
        symbol: A 股股票代码，如 600519、000001
        lookback_days: 回看天数用于 VWAP 计算，默认 60

    Returns:
        str: JSON 字符串，正常返回字段说明——
            symbol: 股票代码
            current_close: 最新收盘价
            date: 最新交易日
            latest_vwap: 最新 VWAP 值
            deviation_pct: 当前价相对 VWAP 的偏离百分比
            position: 价格相对 VWAP 的位置，取值 "above_vwap" | "below_vwap" | "at_vwap"
            vwap_trend: 多周期 VWAP 趋势，子字段 —
                vwap_5d: 5 日 VWAP
                vwap_20d: 20 日 VWAP
            interpretation: 解读文本
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

        if not quotes or len(quotes) < 20:
            return json.dumps(
                {"status": "error", "message": f"未获取到 {symbol} 的日线数据，或数据不足20条。"},
                ensure_ascii=False, indent=2, default=str,
            )

        df = pd.DataFrame(quotes)
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].apply(_safe_float)
        df["trade_date"] = df["trade_date"].astype(str)
        df = df.dropna(subset=["high", "low", "close", "volume"]).sort_values("trade_date")
        df = df.reset_index(drop=True)

        if len(df) < 20:
            return json.dumps(
                {"status": "error", "message": f"{symbol} 有效数据不足20条。"},
                ensure_ascii=False, indent=2, default=str,
            )

        close = df["close"]
        high = df["high"]
        low = df["low"]
        volume = df["volume"]

        # 典型价格 = (高 + 低 + 收) / 3
        typical_price = (high + low + close) / 3.0

        # 日 VWAP
        vwap = (typical_price * volume).cumsum() / volume.cumsum().replace(0, np.nan)

        # 滚动 VWAP：5 日和 20 日
        def _rolling_vwap(tp: pd.Series, vol: pd.Series, n: int) -> pd.Series:
            cum_pv = (tp * vol).rolling(window=n, min_periods=n).sum()
            cum_v = vol.rolling(window=n, min_periods=n).sum()
            return cum_pv / cum_v.replace(0, np.nan)

        vwap_5 = _rolling_vwap(typical_price, volume, 5)
        vwap_20 = _rolling_vwap(typical_price, volume, 20)

        latest_idx = len(df) - 1
        latest_vwap = float(vwap.iloc[latest_idx]) if not pd.isna(vwap.iloc[latest_idx]) else 0.0
        latest_close = float(close.iloc[-1])
        deviation_pct = ((latest_close - latest_vwap) / latest_vwap * 100) if latest_vwap > 0 else 0.0

        vwap_5_val = float(vwap_5.iloc[latest_idx]) if not pd.isna(vwap_5.iloc[latest_idx]) else 0.0
        vwap_20_val = float(vwap_20.iloc[latest_idx]) if not pd.isna(vwap_20.iloc[latest_idx]) else 0.0

        result = {
            "symbol": str(symbol),
            "current_close": round(latest_close, 2),
            "date": str(df.iloc[-1]["trade_date"])[:10],
            "latest_vwap": round(latest_vwap, 2),
            "deviation_pct": round(deviation_pct, 2),
            "position": "above_vwap" if latest_close > latest_vwap else "below_vwap" if latest_close < latest_vwap else "at_vwap",
            "vwap_trend": {
                "vwap_5d": round(vwap_5_val, 2),
                "vwap_20d": round(vwap_20_val, 2),
            },
            "interpretation": (
                f"当前价格 {latest_close:.2f}，"
                f"VWAP {latest_vwap:.2f}，"
                f"偏离 {deviation_pct:+.2f}%。"
                f" {'价格高于 VWAP，买方力量占优。' if latest_close > latest_vwap else '价格低于 VWAP，卖方力量占优。'}"
            ),
            "data_quality": {
                "bars_analyzed": len(df),
            },
        }

        return json.dumps(result, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("VWAP 计算失败: %s", exc, exc_info=True)
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2, default=str)


# ============================================================
#  Tool 6: OBV (能量潮指标)
# ============================================================

@tool
@register_tool(
    tool_id="get_obv_analysis",
    name="OBV 能量潮分析",
    description="计算 OBV（能量潮指标）并检测 OBV 趋势以及与价格的背离信号。",
    category="technical",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["technical_analysis", "obv", "volume_analysis"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["obv_analysis", "volume_divergence"],
    when_to_use="当需要通过成交量验证价格趋势的可靠性、检测量价背离时使用。",
    when_not_to_use="数据不足（少于 30 根 K 线）时结果不可靠；不适用于交易不活跃的股票。",
    returns="返回 JSON，包含 latest_obv、obv_trend、divergence_signal、obv_data（最近 5 期）。",
    example="get_obv_analysis(symbol='600519', lookback_days=120)",
    related_tools=["get_vwap", "get_volume_price_divergence", "get_turnover_analysis"],
)
def get_obv_analysis(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"],
    lookback_days: Annotated[int, "回看天数用于 OBV 计算，默认 120"] = 120,
) -> str:
    """计算 OBV（On-Balance Volume，能量潮指标）并检测 OBV 趋势以及与价格的背离信号。

    Args:
        symbol: A 股股票代码，如 600519、000001
        lookback_days: 回看天数用于 OBV 计算，默认 120

    Returns:
        str: JSON 字符串，正常返回字段说明——
            symbol: 股票代码
            current_price: 最新收盘价
            date: 最新交易日
            latest_obv: 最新 OBV 值
            obv_trend: OBV 趋势，取值 "up" | "down" | "neutral"
            divergence_signal: 背离信号，取值 "bearish" | "bullish" | "none"
            obv_data: 最近 5 期 OBV 数据列表，每个元素结构 —
                date: 交易日期
                close: 收盘价
                obv: OBV 值
            interpretation: 解读信息，子字段 —
                obv_up: OBV 上升说明
                obv_down: OBV 下降说明
                bearish_divergence: 下行背离说明
                bullish_divergence: 上行背离说明
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

        # 计算 OBV
        obv = pd.Series(0.0, index=df.index)
        obv_vals = [0.0]
        for i in range(1, len(df)):
            if close.iloc[i] > close.iloc[i - 1]:
                obv_vals.append(obv_vals[-1] + volume.iloc[i])
            elif close.iloc[i] < close.iloc[i - 1]:
                obv_vals.append(obv_vals[-1] - volume.iloc[i])
            else:
                obv_vals.append(obv_vals[-1])
        obv = pd.Series(obv_vals, index=df.index)

        # OBV 移动平均线
        obv_ma20 = obv.rolling(window=20, min_periods=10).mean()
        obv_ma50 = obv.rolling(window=50, min_periods=20).mean()

        # OBV 趋势判断
        latest_idx = len(df) - 1
        ma20_val = float(obv_ma20.iloc[latest_idx]) if not pd.isna(obv_ma20.iloc[latest_idx]) else 0.0
        ma50_val = float(obv_ma50.iloc[latest_idx]) if not pd.isna(obv_ma50.iloc[latest_idx]) else 0.0

        if ma20_val > ma50_val:
            obv_trend = "up"
        elif ma20_val < ma50_val:
            obv_trend = "down"
        else:
            obv_trend = "neutral"

        # OBV 与价格背离检测
        divergence_signal = "none"

        # 检查最近 20 根 K 线的趋势
        recent_close = close.iloc[-20:]
        recent_obv = obv.iloc[-20:]

        if len(recent_close) >= 10:
            close_start = float(recent_close.iloc[0])
            close_end = float(recent_close.iloc[-1])
            obv_start = float(recent_obv.iloc[0])
            obv_end = float(recent_obv.iloc[-1])

            price_up = close_end > close_start * 1.02
            price_down = close_end < close_start * 0.98
            obv_up = obv_end > obv_start * 1.02
            obv_down = obv_end < obv_start * 0.98

            if price_up and (not obv_up or obv_down):
                divergence_signal = "bearish"
            elif price_down and (not obv_down or obv_up):
                divergence_signal = "bullish"

        # 最新的 OBV 值
        latest_obv = float(obv.iloc[latest_idx])

        # 最近 5 期 OBV
        obv_data = []
        for i in range(max(0, latest_idx - 4), latest_idx + 1):
            obv_data.append({
                "date": str(df.iloc[i]["trade_date"])[:10],
                "close": round(float(close.iloc[i]), 2),
                "obv": round(float(obv.iloc[i]), 2),
            })

        result = {
            "symbol": str(symbol),
            "current_price": round(float(close.iloc[-1]), 2),
            "date": str(df.iloc[-1]["trade_date"])[:10],
            "latest_obv": round(latest_obv, 2),
            "obv_trend": obv_trend,
            "divergence_signal": divergence_signal,
            "obv_data": obv_data,
            "interpretation": {
                "obv_up": "OBV 上升，成交量支持上涨趋势",
                "obv_down": "OBV 下降，成交量支持下跌趋势",
                "bearish_divergence": "价格上升但 OBV 下降/停滞，上涨缺乏成交量支持（负向背离信号）",
                "bullish_divergence": "价格下降但 OBV 上升/企稳，下跌缺乏成交量支持（正向背离信号）",
            },
            "data_quality": {
                "bars_analyzed": len(df),
            },
        }

        return json.dumps(result, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("OBV 分析失败: %s", exc, exc_info=True)
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2, default=str)


# ============================================================
#  Tool 7: 换手率分析
# ============================================================

@tool
@register_tool(
    tool_id="get_turnover_analysis",
    name="换手率分析",
    description="计算股票历史平均换手率，检测异常放量/缩量信号，评估交易活跃度变化趋势。",
    category="technical",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["technical_analysis", "turnover", "volume_analysis"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["换手率分析", "异常放量/缩量"],
    when_to_use="当需要评估股票交易活跃度、检测异常放量/缩量、分析筹码交换情况时使用。",
    when_not_to_use="新股上市不足 30 天数据不足；停牌期间无数据。",
    returns="返回 JSON，包含 avg_turnover、current_turnover、abnormal_days_count、turnover_trend。",
    example="get_turnover_analysis(symbol='600519', lookback_days=120)",
    related_tools=["get_obv_analysis", "get_volume_price_divergence"],
)
def get_turnover_analysis(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"],
    lookback_days: Annotated[int, "回看天数用于换手率分析，默认 120"] = 120,
) -> str:
    """分析股票换手率，计算历史平均换手率，检测异常放量/缩量信号，评估交易活跃度变化趋势。

    Args:
        symbol: A 股股票代码，如 600519、000001
        lookback_days: 回看天数用于换手率分析，默认 120

    Returns:
        str: JSON 字符串，正常返回字段说明——
            symbol: 股票代码
            current_price: 最新收盘价
            date: 最新交易日
            has_shares_info: 是否获取到总股本信息（False 时换手率字段为 None，使用成交额近似估算）
            avg_turnover: 平均换手率（百分比），无总股本时为 None
            current_turnover: 当前换手率（百分比），无总股本时为 None
            abnormal_days_count: 异常放量天数
            abnormal_days: 异常放量日列表（最近 5 条），每个元素结构 —
                date: 交易日期
                volume: 成交量
                volume_ratio: 量比
            turnover_trend: 换手率趋势，取值 "increasing" | "decreasing" | "stable"
            data_quality: 数据质量，子字段 —
                bars_analyzed: 分析的 K 线数量
        异常时返回字段 —
            status: "error"
            message: 错误信息
    """
    try:
        from core.skill_runtime.data_access import get_stock_daily_quotes, get_stock_basic_info

        today = datetime.date.today()
        end = today.strftime("%Y%m%d")
        start = (today - datetime.timedelta(days=int(lookback_days) + 30)).strftime("%Y%m%d")
        quotes = get_stock_daily_quotes(str(symbol), start, end, limit=int(lookback_days) + 60)

        if not quotes or len(quotes) < 20:
            return json.dumps(
                {"status": "error", "message": f"未获取到 {symbol} 的日线数据，或数据不足20条。"},
                ensure_ascii=False, indent=2, default=str,
            )

        df = pd.DataFrame(quotes)
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].apply(_safe_float)
        df["trade_date"] = df["trade_date"].astype(str)
        df = df.dropna(subset=["high", "low", "close", "volume"]).sort_values("trade_date")
        df = df.reset_index(drop=True)

        if len(df) < 20:
            return json.dumps(
                {"status": "error", "message": f"{symbol} 有效数据不足20条。"},
                ensure_ascii=False, indent=2, default=str,
            )

        close = df["close"]
        volume = df["volume"]

        # 获取总股本
        basic_info = get_stock_basic_info(str(symbol))
        total_shares = None
        if basic_info:
            total_shares = (
                _safe_float(basic_info.get("total_shares"))
                or _safe_float(basic_info.get("total_share"))
                or _safe_float(basic_info.get("total_mv"))
            )

        if total_shares is None or total_shares <= 0:
            # 如果没有总股本信息，使用成交额近似估算换手率
            turnover_series = pd.Series([0.0] * len(df), index=df.index)
            for i in range(1, len(df)):
                vol_value = float(volume.iloc[i]) if not pd.isna(volume.iloc[i]) else 0
                turnover_series.iloc[i] = vol_value / (vol_value + 1e-10)
            has_shares_info = False
        else:
            has_shares_info = True
            # 换手率 = 成交量 / 总股本
            turnover_series = volume / total_shares * 100.0

        # 计算平均换手率
        avg_turnover = float(turnover_series.iloc[1:].mean()) if len(df) > 1 else 0.0
        current_turnover = float(turnover_series.iloc[-1]) if not pd.isna(turnover_series.iloc[-1]) else 0.0

        # 检测异常放量（>2x 均值）
        mean_vol = float(volume.iloc[1:].mean()) if len(df) > 1 else 0.0
        abnormal_days = []
        for i in range(1, len(df)):
            v = float(volume.iloc[i]) if not pd.isna(volume.iloc[i]) else 0.0
            if mean_vol > 0 and v > mean_vol * 2:
                abnormal_days.append({
                    "date": str(df.iloc[i]["trade_date"])[:10],
                    "volume": round(v, 2),
                    "volume_ratio": round(v / mean_vol, 2),
                })

        # 换手率趋势（用 MA5 和 MA20 判断）
        turnover_ma5 = turnover_series.rolling(window=5, min_periods=3).mean()
        turnover_ma20 = turnover_series.rolling(window=20, min_periods=10).mean()

        ma5_val = float(turnover_ma5.iloc[-1]) if not pd.isna(turnover_ma5.iloc[-1]) else 0.0
        ma20_val = float(turnover_ma20.iloc[-1]) if not pd.isna(turnover_ma20.iloc[-1]) else 0.0

        if ma5_val > ma20_val * 1.1:
            turnover_trend = "increasing"
        elif ma5_val < ma20_val * 0.9:
            turnover_trend = "decreasing"
        else:
            turnover_trend = "stable"

        result = {
            "symbol": str(symbol),
            "current_price": round(float(close.iloc[-1]), 2),
            "date": str(df.iloc[-1]["trade_date"])[:10],
            "has_shares_info": has_shares_info,
            "avg_turnover": round(avg_turnover, 4) if has_shares_info else None,
            "current_turnover": round(current_turnover, 4) if has_shares_info else None,
            "abnormal_days_count": len(abnormal_days),
            "abnormal_days": abnormal_days[-5:] if abnormal_days else [],
            "turnover_trend": turnover_trend,
            "data_quality": {
                "bars_analyzed": len(df),
            },
        }

        return json.dumps(result, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("换手率分析失败: %s", exc, exc_info=True)
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2, default=str)


# ============================================================
#  Tool 8: 枢轴点 (Pivot Points)
# ============================================================

@tool
@register_tool(
    tool_id="get_pivot_points",
    name="枢轴点计算",
    description="基于经典枢轴点公式和斐波那契枢轴点公式计算关键支撑/阻力位，为日内研究提供参考。",
    category="technical",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["technical_analysis", "pivot_points"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["pivot_points_calculation", "intraday_levels"],
    when_to_use="当需要计算日内关键支撑阻力位、设置风险关注与收益关注参考时使用。",
    when_not_to_use="数据不足（少于 2 根 K 线）时无法计算；不适用于非日线级别的长周期分析。",
    returns="返回 JSON，包含 classic 和 fibonacci 两组枢轴点（PP/R1-3/S1-3）及当前价格。",
    example="get_pivot_points(symbol='600519', lookback_days=30)",
    related_tools=["get_support_resistance_levels", "get_fibonacci_extension"],
)
def get_pivot_points(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"],
    lookback_days: Annotated[int, "回看天数用于枢轴点计算，默认 30"] = 30,
) -> str:
    """计算经典枢轴点和斐波那契枢轴点，为日内研究提供支撑/阻力位参考。

    Args:
        symbol: A 股股票代码，如 600519、000001
        lookback_days: 回看天数用于枢轴点计算，默认 30

    Returns:
        str: JSON 字符串，正常返回字段说明——
            symbol: 股票代码
            current_price: 最新收盘价
            date: 最新交易日
            reference_bar: 参考K线（前一根），子字段 —
                date: 参考K线日期
                high: 最高价
                low: 最低价
                close: 收盘价
            classic: 经典枢轴点，每个水平的值为 {price, distance_pct}，key 包括 —
                pp: 枢轴点
                r1, r2, r3: 阻力位 1/2/3
                s1, s2, s3: 支撑位 1/2/3
            fibonacci: 斐波那契枢轴点，子字段 —
                pp: 枢轴点
                resistances: 阻力位字典，key 为 "r_{level}"（level 取值 0.0、0.236、0.382、0.5、0.618、0.786、1.0），值为 {price, distance_pct}
                supports: 支撑位字典，key 为 "s_{level}"（level 同上），值为 {price, distance_pct}
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
        start = (today - datetime.timedelta(days=int(lookback_days) + 10)).strftime("%Y%m%d")
        quotes = get_stock_daily_quotes(str(symbol), start, end, limit=int(lookback_days) + 20)

        if not quotes or len(quotes) < 2:
            return json.dumps(
                {"status": "error", "message": f"未获取到 {symbol} 的日线数据，或数据不足2条。"},
                ensure_ascii=False, indent=2, default=str,
            )

        df = pd.DataFrame(quotes)
        for col in ["open", "high", "low", "close"]:
            df[col] = df[col].apply(_safe_float)
        df["trade_date"] = df["trade_date"].astype(str)
        df = df.dropna(subset=["high", "low", "close"]).sort_values("trade_date")
        df = df.reset_index(drop=True)

        if len(df) < 2:
            return json.dumps(
                {"status": "error", "message": f"{symbol} 有效数据不足2条。"},
                ensure_ascii=False, indent=2, default=str,
            )

        latest = df.iloc[-1]
        current_price = float(latest["close"])

        # 最近一根完整 K 线
        if len(df) >= 2:
            ref_bar = df.iloc[-2]  # 用前一根计算
        else:
            ref_bar = df.iloc[-1]

        high = float(ref_bar["high"])
        low = float(ref_bar["low"])
        close = float(ref_bar["close"])
        ref_date = str(ref_bar["trade_date"])[:10]

        # --- 经典枢轴点 ---
        pp = (high + low + close) / 3.0

        classic = {
            "pp": round(pp, 2),
            "r1": round(2 * pp - low, 2),
            "r2": round(pp + (high - low), 2),
            "r3": round(high + 2 * (pp - low), 2),
            "s1": round(2 * pp - high, 2),
            "s2": round(pp - (high - low), 2),
            "s3": round(low - 2 * (high - pp), 2),
        }

        classic_with_dist = {}
        for k, v in classic.items():
            dist = round((v - current_price) / current_price * 100, 2) if current_price > 0 else 0.0
            classic_with_dist[k] = {"price": v, "distance_pct": dist}

        # --- 斐波那契枢轴点 ---
        fib_levels = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
        fib_pivot = pp
        fib_range = high - low

        fib_resistances = {}
        fib_supports = {}

        for level in fib_levels:
            # 阻力 = PP + level * range
            r_price = fib_pivot + level * fib_range
            r_dist = round((r_price - current_price) / current_price * 100, 2) if current_price > 0 else 0.0
            fib_resistances[f"r_{level}"] = {"price": round(r_price, 2), "distance_pct": r_dist}

            # 支撑 = PP - level * range
            s_price = fib_pivot - level * fib_range
            s_dist = round((s_price - current_price) / current_price * 100, 2) if current_price > 0 else 0.0
            fib_supports[f"s_{level}"] = {"price": round(s_price, 2), "distance_pct": s_dist}

        fibonacci = {
            "pp": round(fib_pivot, 2),
            "resistances": fib_resistances,
            "supports": fib_supports,
        }

        result = {
            "symbol": str(symbol),
            "current_price": round(current_price, 2),
            "date": str(df.iloc[-1]["trade_date"])[:10],
            "reference_bar": {
                "date": ref_date,
                "high": round(high, 2),
                "low": round(low, 2),
                "close": round(close, 2),
            },
            "classic": classic_with_dist,
            "fibonacci": fibonacci,
            "data_quality": {
                "bars_analyzed": len(df),
            },
        }

        return json.dumps(result, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("枢轴点计算失败: %s", exc, exc_info=True)
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2, default=str)


# ============================================================
#  Tool 9: 成交量分布 (Volume Profile)
# ============================================================

@tool
@register_tool(
    tool_id="get_volume_profile",
    name="成交量分布分析",
    description="计算成交量分布，识别 POC（控制点）、价值区域（Value Area），评估当前价格在价值区域中的位置。",
    category="technical",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["technical_analysis", "volume_profile"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["成交量分布分析", "POC 控制点识别"],
    when_to_use="当需要识别成交最密集的价格区间、判断公允价值区域时使用。适用于大周期趋势判断。",
    when_not_to_use="数据不足（少于 20 根 K 线）时分布不可靠；不适用于短线高频交易。",
    returns="返回 JSON，包含 poc_price、value_area_high、value_area_low、current_position_relative_to_va、distribution_profile。",
    example="get_volume_profile(symbol='600519', lookback_days=60, price_bins=20)",
    related_tools=["get_support_resistance_levels", "get_vwap"],
)
def get_volume_profile(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"],
    lookback_days: Annotated[int, "回看天数用于成交量分布计算，默认 60"] = 60,
    price_bins: Annotated[int, "价格区间分箱数量，默认 20"] = 20,
) -> str:
    """计算成交量分布（Volume Profile），识别 POC（控制点）、价值区域，评估当前价格在价值区域中的位置。

    Args:
        symbol: A 股股票代码，如 600519、000001
        lookback_days: 回看天数用于成交量分布计算，默认 60
        price_bins: 价格区间分箱数量，默认 20

    Returns:
        str: JSON 字符串，正常返回字段说明——
            symbol: 股票代码
            current_price: 最新收盘价
            date: 最新交易日
            poc_price: POC（控制点）价格
            poc_volume: POC 成交量
            poc_volume_pct: POC 成交量占比（百分比）
            value_area_high: 价值区域上沿
            value_area_low: 价值区域下沿
            value_area_width: 价值区域宽度
            current_position_relative_to_va: 当前价相对价值区域的位置，取值 "above_va" | "below_va" | "within_va"
            distribution_profile: 分布概况列表（最多 20 个分箱），每个元素结构 —
                price_level: 价格水平（分箱中心）
                price_low: 分箱下沿
                price_high: 分箱上沿
                volume: 成交量
                volume_pct: 成交量占比（百分比）
                is_poc: 是否为 POC
                in_value_area: 是否在价值区域内
            data_quality: 数据质量，子字段 —
                bars_analyzed: 分析的 K 线数量
                price_bins: 实际分箱数
        异常时返回字段 —
            status: "error"
            message: 错误信息
    """
    try:
        from core.skill_runtime.data_access import get_stock_daily_quotes

        today = datetime.date.today()
        end = today.strftime("%Y%m%d")
        start = (today - datetime.timedelta(days=int(lookback_days) + 20)).strftime("%Y%m%d")
        quotes = get_stock_daily_quotes(str(symbol), start, end, limit=int(lookback_days) + 40)

        if not quotes or len(quotes) < 20:
            return json.dumps(
                {"status": "error", "message": f"未获取到 {symbol} 的日线数据，或数据不足20条。"},
                ensure_ascii=False, indent=2, default=str,
            )

        df = pd.DataFrame(quotes)
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].apply(_safe_float)
        df["trade_date"] = df["trade_date"].astype(str)
        df = df.dropna(subset=["high", "low", "close", "volume"]).sort_values("trade_date")
        df = df.reset_index(drop=True)

        if len(df) < 20:
            return json.dumps(
                {"status": "error", "message": f"{symbol} 有效数据不足20条。"},
                ensure_ascii=False, indent=2, default=str,
            )

        close = df["close"]
        high = df["high"]
        low = df["low"]
        volume = df["volume"]

        # 确定价格范围
        price_min = float(low.min())
        price_max = float(high.max())
        price_range = price_max - price_min

        if price_range <= 0:
            return json.dumps(
                {"status": "error", "message": "价格区间异常，无法计算成交量分布。"},
                ensure_ascii=False, indent=2, default=str,
            )

        n_bins = max(5, min(50, int(price_bins)))
        bin_width = price_range / n_bins

        # 建立价格分箱
        bin_edges = [price_min + i * bin_width for i in range(n_bins + 1)]
        bin_centers = [(bin_edges[i] + bin_edges[i + 1]) / 2.0 for i in range(n_bins)]
        bin_volume = [0.0] * n_bins

        # 分配成交量到各个价格分箱
        for i in range(len(df)):
            bar_high = float(high.iloc[i])
            bar_low = float(low.iloc[i])
            bar_volume = float(volume.iloc[i])

            if bar_high <= bar_low or bar_volume <= 0:
                continue

            for j in range(n_bins):
                bin_top = bin_edges[j + 1]
                bin_bottom = bin_edges[j]

                # 计算重叠区间
                overlap_low = max(bar_low, bin_bottom)
                overlap_high = min(bar_high, bin_top)

                if overlap_high > overlap_low:
                    overlap_pct = (overlap_high - overlap_low) / (bar_high - bar_low)
                    bin_volume[j] += bar_volume * overlap_pct

        # 找到 POC（成交量最大的价格水平）
        poc_idx = int(np.argmax(bin_volume))
        poc_price = round(bin_centers[poc_idx], 2)
        poc_volume = round(bin_volume[poc_idx], 2)

        # 价值区域：找出包含 70% 成交量的价格区间
        total_volume = sum(bin_volume)
        if total_volume <= 0:
            return json.dumps(
                {"status": "error", "message": "成交量数据异常。"},
                ensure_ascii=False, indent=2, default=str,
            )

        # 从 POC 向两侧扩展
        sorted_indices = sorted(
            range(n_bins),
            key=lambda x: bin_volume[x],
            reverse=True,
        )

        target_vol = total_volume * 0.7
        accumulated_vol = 0.0
        value_area_bins = []

        for idx in sorted_indices:
            if accumulated_vol >= target_vol:
                break
            value_area_bins.append(idx)
            accumulated_vol += bin_volume[idx]

        if value_area_bins:
            va_low_idx = min(value_area_bins)
            va_high_idx = max(value_area_bins)
            value_area_low = round(bin_edges[va_low_idx], 2)
            value_area_high = round(bin_edges[va_high_idx + 1], 2)
        else:
            value_area_low = round(price_min, 2)
            value_area_high = round(price_max, 2)

        current_price_val = float(close.iloc[-1])
        if current_price_val > value_area_high:
            current_position = "above_va"
        elif current_price_val < value_area_low:
            current_position = "below_va"
        else:
            current_position = "within_va"

        # 分布概况
        distribution_profile = []
        for j in range(n_bins):
            vol_pct = (bin_volume[j] / total_volume * 100) if total_volume > 0 else 0
            distribution_profile.append({
                "price_level": round(bin_centers[j], 2),
                "price_low": round(bin_edges[j], 2),
                "price_high": round(bin_edges[j + 1], 2),
                "volume": round(bin_volume[j], 2),
                "volume_pct": round(vol_pct, 2),
                "is_poc": j == poc_idx,
                "in_value_area": j in value_area_bins,
            })

        result = {
            "symbol": str(symbol),
            "current_price": round(current_price_val, 2),
            "date": str(df.iloc[-1]["trade_date"])[:10],
            "poc_price": poc_price,
            "poc_volume": poc_volume,
            "poc_volume_pct": round(poc_volume / total_volume * 100, 2) if total_volume > 0 else 0,
            "value_area_high": value_area_high,
            "value_area_low": value_area_low,
            "value_area_width": round(value_area_high - value_area_low, 2),
            "current_position_relative_to_va": current_position,
            "distribution_profile": distribution_profile[:20] if len(distribution_profile) > 20 else distribution_profile,
            "data_quality": {
                "bars_analyzed": len(df),
                "price_bins": n_bins,
            },
        }

        return json.dumps(result, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("成交量分布计算失败: %s", exc, exc_info=True)
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2, default=str)


# ============================================================
#  Tool 10: 斐波那契扩展
# ============================================================

@tool
@register_tool(
    tool_id="get_fibonacci_extension",
    name="斐波那契扩展",
    description="基于最近的价格波动（高点到低点或低点到高点）计算斐波那契扩展目标位，提供潜在价格目标参考。",
    category="technical",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["technical_analysis", "fibonacci_extension"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["斐波那契扩展", "价格目标位"],
    when_to_use="当需要在趋势行情中寻找潜在的扩展价格位、设置收益关注参考时使用。",
    when_not_to_use="震荡市中扩展位参考价值有限；数据不足（少于 30 根 K 线）时结果不可靠。",
    returns="返回 JSON，包含 swing_analysis、extension_prices（各水平）、current_proximity。",
    example="get_fibonacci_extension(symbol='600519', lookback_days=120, extension_levels='1.272,1.382,1.618,2.0,2.618')",
    related_tools=["get_fibonacci_retracement", "get_pivot_points"],
)
def get_fibonacci_extension(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"],
    lookback_days: Annotated[int, "回看天数用于波动区间识别，默认 120"] = 120,
    extension_levels: Annotated[str, "扩展水平，逗号分隔，默认 1.272,1.382,1.618,2.0,2.618"] = "1.272,1.382,1.618,2.0,2.618",
) -> str:
    """计算斐波那契扩展目标位，基于最近的价格波动（高点到低点或低点到高点）计算潜在价格目标。

    Args:
        symbol: A 股股票代码，如 600519、000001
        lookback_days: 回看天数用于波动区间识别，默认 120
        extension_levels: 扩展水平，逗号分隔，默认 "1.272,1.382,1.618,2.0,2.618"

    Returns:
        str: JSON 字符串，正常返回字段说明——
            symbol: 股票代码
            current_price: 最新收盘价
            date: 最新交易日
            trend: 当前趋势方向，取值 "up" | "down"
            swing_analysis: 波动分析，子字段 —
                swing_type: 波动类型，取值 "上升波动" | "下降波动"
                start_price: 波动起点价
                end_price: 波动终点价
                swing_range: 波动幅度
            extension_prices: 扩展位列表，每个元素结构 —
                level: 扩展比例（如 1.272、1.382、1.618、2.0、2.618）
                price: 扩展位价格
                distance_pct: 距离当前价的百分比
            current_proximity: 最近的扩展位信息，子字段 —
                closest_level: 最近扩展比例
                closest_price: 最近扩展位价格
                distance_pct: 距离当前价的百分比
                role: 价格角色，取值 "resistance" | "support"
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

        if not quotes or len(quotes) < 30:
            return json.dumps(
                {"status": "error", "message": f"未获取到 {symbol} 的日线数据，或数据不足30条。"},
                ensure_ascii=False, indent=2, default=str,
            )

        df = pd.DataFrame(quotes)
        for col in ["open", "high", "low", "close"]:
            df[col] = df[col].apply(_safe_float)
        df["trade_date"] = df["trade_date"].astype(str)
        df = df.dropna(subset=["high", "low", "close"]).sort_values("trade_date")
        df = df.reset_index(drop=True)

        if len(df) < 30:
            return json.dumps(
                {"status": "error", "message": f"{symbol} 有效数据不足30条。"},
                ensure_ascii=False, indent=2, default=str,
            )

        close = df["close"]
        high = df["high"]
        low = df["low"]

        # 解析扩展水平
        levels = []
        for s in extension_levels.split(","):
            s = s.strip()
            try:
                val = float(s)
                if val > 0:
                    levels.append(val)
            except (ValueError, TypeError):
                continue

        if not levels:
            levels = [1.272, 1.382, 1.618, 2.0, 2.618]

        current_price = float(close.iloc[-1])

        # 找最近的显著波动（用最近一半的数据找高低点）
        half_len = max(20, len(df) // 2)
        recent = df.iloc[-half_len:]

        swing_high = float(recent["high"].max())
        swing_low = float(recent["low"].min())
        swing_high_idx = recent["high"].idxmax()
        swing_low_idx = recent["low"].idxmin()

        # 判断当前趋势方向：最近 N 根 K 线的价格变化
        recent_close_vals = close.iloc[-min(20, len(close)):]
        trend = "up" if float(recent_close_vals.iloc[-1]) > float(recent_close_vals.iloc[0]) else "down"

        # 确定波动方向
        if swing_low_idx < swing_high_idx:
            # 低点在前，高点在后 → 上升波动
            swing_type = "low_to_high"
            swing_start_price = swing_low
            swing_end_price = swing_high
            swing_range = swing_high - swing_low
            direction = "up"
        else:
            # 高点在前，低点在后 → 下降波动
            swing_type = "high_to_low"
            swing_start_price = swing_high
            swing_end_price = swing_low
            swing_range = swing_high - swing_low
            direction = "down"

        if swing_range <= 0:
            return json.dumps(
                {"status": "error", "message": "价格波动区间异常，无法计算扩展位。"},
                ensure_ascii=False, indent=2, default=str,
            )

        # 计算扩展价格
        extension_prices = []
        for level in levels:
            if direction == "up":
                # 上升扩展：从起点往终点方向再延伸
                ext_price = swing_start_price + level * swing_range
            else:
                # 下降扩展：从起点往终点方向再延伸
                ext_price = swing_start_price - level * swing_range

            # 当前价格到扩展位的距离百分比
            if direction == "up":
                distance_pct = (ext_price - current_price) / current_price * 100 if current_price > 0 else 0.0
            else:
                distance_pct = (current_price - ext_price) / current_price * 100 if current_price > 0 else 0.0

            extension_prices.append({
                "level": level,
                "price": round(ext_price, 2),
                "distance_pct": round(distance_pct, 2),
            })

        # 找到最近的扩展位
        if extension_prices:
            closest = min(extension_prices, key=lambda x: abs(x["distance_pct"]))
            current_proximity = {
                "closest_level": closest["level"],
                "closest_price": closest["price"],
                "distance_pct": closest["distance_pct"],
                "role": "resistance" if closest["price"] > current_price else "support",
            }
        else:
            current_proximity = None

        result = {
            "symbol": str(symbol),
            "current_price": round(current_price, 2),
            "date": str(df.iloc[-1]["trade_date"])[:10],
            "trend": trend,
            "swing_analysis": {
                "swing_type": "上升波动" if direction == "up" else "下降波动",
                "start_price": round(swing_start_price, 2),
                "end_price": round(swing_end_price, 2),
                "swing_range": round(swing_range, 2),
            },
            "extension_prices": extension_prices,
            "current_proximity": current_proximity,
            "data_quality": {
                "bars_analyzed": len(df),
            },
        }

        return json.dumps(result, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("斐波那契扩展计算失败: %s", exc, exc_info=True)
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2, default=str)


__all__ = [
    "get_vwap",
    "get_obv_analysis",
    "get_turnover_analysis",
    "get_pivot_points",
    "get_volume_profile",
    "get_fibonacci_extension",
]