"""现金流质量深度增强与业绩预告分析工具。

提供：
1. get_cashflow_quality_deep — 现金流质量深度分析
2. get_earnings_surprise_analysis — 业绩预告/盈利惊喜分析
"""

import json
import logging
from statistics import mean, pstdev
from typing import Annotated, Any, Dict, List, Optional

from langchain_core.tools import tool

from core.skill_runtime.data_access import (
    get_latest_stock_price,
    get_stock_basic_info,
    get_stock_financial_periods,
)
from core.skill_runtime.standard_financial_apis import (
    get_cashflow_quality_trend,
    get_historical_financial_annual_series,
)
from core.tools.base import register_tool

logger = logging.getLogger(__name__)


# ==================== 工具内部 helper ====================

def _safe_div(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def _safe_float(value) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        try:
            numeric = float(value)
            if numeric != numeric:
                return None
            return numeric
        except (TypeError, ValueError):
            return None
    try:
        text = str(value).strip()
        if not text:
            return None
        numeric = float(text)
        if numeric != numeric:
            return None
        return numeric
    except (TypeError, ValueError):
        return None


def _json_response(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def _normalize_symbol(symbol: str) -> str:
    text = str(symbol or "").strip().upper()
    for prefix in ("SH", "SZ", "SS", "BJ"):
        text = text.replace(prefix, "")
    if "." in text:
        text = text.split(".", 1)[0]
    digits = "".join(ch for ch in text if ch.isdigit())
    return digits[-6:].zfill(6) if digits else ""


# ==================== Tool 3: 现金流质量深度 ====================

@tool
@register_tool(
    tool_id="get_cashflow_quality_deep",
    name="现金流质量深度",
    description=(
        "基于年报序列和财务期间数据对现金流质量进行深度分析。"
        "计算自由现金流（FCF）、FCF Yield、OCF/净利润比率趋势、"
        "现金流稳定性评分（0-100），以及现金流质量综合评分。"
    ),
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    when_to_use="当需要深度现金流质量分析、FCF收益率、现金流稳定性评分、OCF/净利润比率趋势时使用。",
    returns="返回 JSON 字符串，包含 fcf、fcf_yield、ocf_to_np_ratio、stability_score、trend_direction、flags。",
    example="get_cashflow_quality_deep(symbol='600519')",
)
def get_cashflow_quality_deep(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"],
) -> str:
    """获取现金流质量深度增强数据。"""
    try:
        normalized_symbol = _normalize_symbol(symbol)
        if not normalized_symbol:
            return _json_response({"status": "error", "message": "无效股票代码"})

        # 1. 获取现金流质量趋势（年报序列）
        cashflow = get_cashflow_quality_trend(normalized_symbol, years=10)
        trend = cashflow.get("trend") or []
        summary = cashflow.get("summary") or {}
        coverage = cashflow.get("coverage") or {}
        cashflow_warnings = list(cashflow.get("warnings") or [])

        # 2. 获取财务期间数据（用于 capex 近似）
        financial_periods = get_stock_financial_periods(normalized_symbol, limit=12) or []

        # 3. 获取当前价格和市值
        current_price = get_latest_stock_price(normalized_symbol)
        if current_price is None or current_price <= 0:
            basic = get_stock_basic_info(normalized_symbol) or {}
            current_price = _safe_float(basic.get("close") or basic.get("current_price"))

        total_mv = _safe_float(basic.get("total_mv") or basic.get("market_cap")) if (basic := get_stock_basic_info(normalized_symbol)) else None

        # 4. 计算 FCF（直接从年报序列取；取最新一年）
        fcf = None
        fcf_yield = None
        if trend:
            latest_trend = trend[0]
            fcf = _safe_float(latest_trend.get("free_cashflow"))
            if fcf is not None and total_mv is not None and total_mv > 0:
                fcf_yield = fcf / total_mv

        # 5. OCF/净利润比率趋势
        ocf_np_ratios: List[Optional[float]] = [item.get("ocf_to_net_profit") for item in trend]
        valid_ocf_np = [v for v in ocf_np_ratios if v is not None]
        latest_ocf_np = valid_ocf_np[0] if valid_ocf_np else None
        avg_ocf_np = mean(valid_ocf_np) if valid_ocf_np else None

        # 趋势方向：最近3年 vs 更早3年
        trend_direction = "stable"
        if len(valid_ocf_np) >= 4:
            recent_3 = valid_ocf_np[:3]
            earlier = valid_ocf_np[-3:] if len(valid_ocf_np) >= 6 else valid_ocf_np[-len(valid_ocf_np)//2:]
            if recent_3 and earlier:
                recent_avg = mean(recent_3)
                earlier_avg = mean(earlier)
                if recent_avg > earlier_avg * 1.1:
                    trend_direction = "improving"
                elif recent_avg < earlier_avg * 0.9:
                    trend_direction = "deteriorating"

        # 6. 现金流稳定性评分（0-100）
        ocf_values: List[Optional[float]] = [item.get("operating_cashflow") for item in trend]
        valid_ocf = [v for v in ocf_values if v is not None]

        stability_score = 50  # 默认中等
        if len(valid_ocf) >= 3:
            ocf_mean = mean(valid_ocf)
            if ocf_mean != 0:
                cv = pstdev(valid_ocf) / abs(ocf_mean) if len(valid_ocf) > 1 else 0
                if cv < 0.3:
                    stability_score = 90
                elif cv < 0.5:
                    stability_score = 75
                elif cv < 0.8:
                    stability_score = 60
                elif cv < 1.2:
                    stability_score = 40
                else:
                    stability_score = 20
            # 连续正 OCF 加分
            positive_ratio = sum(1 for v in valid_ocf if v > 0) / len(valid_ocf)
            if positive_ratio > 0.8:
                stability_score = min(100, stability_score + 10)
            elif positive_ratio < 0.5:
                stability_score = max(0, stability_score - 10)

        # 7. 现金流质量综合评分（0-100）
        quality_score = 50
        score_components: Dict[str, float] = {}

        # 子项：FCF 质量
        if len(valid_ocf) >= 3:
            fcf_positive_ratio = sum(1 for v in valid_ocf if v and v > 0) / len(valid_ocf)
            fcf_score = fcf_positive_ratio * 100
            score_components["fcf_positive_ratio"] = round(fcf_positive_ratio, 4)

        # 子项：OCF/净利润
        if valid_ocf_np:
            avg_ratio = mean(valid_ocf_np)
            ocf_np_score = min(100, max(0, (avg_ratio - 0.5) * 100))
            score_components["avg_ocf_to_net_profit"] = round(avg_ratio, 4)
        else:
            ocf_np_score = 0

        # 子项：稳定性
        score_components["stability_score"] = stability_score

        # 综合评分
        counts = 0
        total_score = 0.0
        for key in score_components:
            if key == "stability_score":
                total_score += stability_score
                counts += 1
            elif key == "avg_ocf_to_net_profit":
                total_score += ocf_np_score
                counts += 1
            elif key == "fcf_positive_ratio":
                total_score += score_components[key] * 100
                counts += 1
        quality_score = round(total_score / max(counts, 1), 1)

        # 8. 信号标签
        flags: List[str] = []
        if latest_ocf_np is not None and latest_ocf_np > 1.0:
            flags.append("利润含金量高（OCF/净利>1）")
        elif latest_ocf_np is not None and latest_ocf_np < 0.5:
            flags.append("利润含金量偏低（OCF/净利<0.5）")
        if stability_score >= 75:
            flags.append("现金流稳定性优秀")
        elif stability_score <= 30:
            flags.append("现金流波动较大")
        if fcf_yield is not None and fcf_yield > 0.05:
            flags.append("自由现金流充裕（FCF收益率>5%）")
        elif fcf_yield is not None and fcf_yield < 0:
            flags.append("自由现金流为负")
        if trend_direction == "improving":
            flags.append("现金流质量趋势向好")
        elif trend_direction == "deteriorating":
            flags.append("现金流质量趋势恶化")

        # 构建 OCF/净利润趋势
        trend_series = []
        for item in trend:
            trend_series.append({
                "year": item.get("year"),
                "report_period": item.get("report_period"),
                "ocf_to_net_profit": item.get("ocf_to_net_profit"),
                "fcf_to_net_profit": item.get("fcf_to_net_profit"),
                "operating_cashflow": item.get("operating_cashflow"),
                "free_cashflow": item.get("free_cashflow"),
            })

        return _json_response({
            "status": "success" if trend else "no_data",
            "symbol": normalized_symbol,
            "years_analyzed": len(trend),
            "current_price": current_price,
            "total_market_cap": total_mv,
            "fcf": fcf,
            "fcf_yield": round(fcf_yield, 6) if fcf_yield is not None else None,
            "fcf_yield_pct": round(fcf_yield * 100, 4) if fcf_yield is not None else None,
            "ocf_to_net_profit": {
                "current": round(latest_ocf_np, 4) if latest_ocf_np is not None else None,
                "average": round(avg_ocf_np, 4) if avg_ocf_np is not None else None,
                "min": round(min(valid_ocf_np), 4) if valid_ocf_np else None,
                "max": round(max(valid_ocf_np), 4) if valid_ocf_np else None,
            },
            "stability_score": stability_score,
            "quality_score": quality_score,
            "score_components": score_components,
            "trend_direction": trend_direction,
            "flags": flags,
            "trend_series": trend_series[:10],
            "coverage": coverage,
            "data_quality": "sufficient" if len(trend) >= 3 else "limited" if trend else "insufficient",
            "warnings": cashflow_warnings,
        })
    except Exception as exc:
        logger.error("现金流质量深度分析获取失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"现金流质量深度分析获取失败: {exc}"})


# ==================== Tool 4: 业绩预告分析 ====================

@tool
@register_tool(
    tool_id="get_earnings_surprise_analysis",
    name="业绩预告分析",
    description=(
        "基于财务期间数据的净利润季度趋势，分析业绩惊喜/惊吓。"
        "计算最近 8 个季度的净利润、环比增长、趋势偏离度，"
        "识别显著偏离趋势的季度（>20%意外变化），"
        "并给出整体业绩情绪（大幅超预期/符合预期/大幅低于预期）。"
    ),
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    when_to_use="当需要分析季度业绩趋势、识别业绩惊喜/惊吓、评估业绩一致性时使用。",
    returns="返回 JSON 字符串，包含 recent_quarters_data、recent_surprises_list、overall_sentiment、data_quality、methodology_note。",
    example="get_earnings_surprise_analysis(symbol='600519')",
)
def get_earnings_surprise_analysis(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"],
) -> str:
    """获取业绩预告/盈利惊喜分析。"""
    try:
        normalized_symbol = _normalize_symbol(symbol)
        if not normalized_symbol:
            return _json_response({"status": "error", "message": "无效股票代码"})

        # 1. 获取财务期间数据（最近 12 期，以确保有 8 个季度）
        periods = get_stock_financial_periods(normalized_symbol, limit=16) or []

        if not periods:
            return _json_response({"status": "no_data", "message": "未获取到财务期间数据", "symbol": normalized_symbol})

        # 2. 提取季度净利润数据
        quarterly_data: List[Dict[str, Any]] = []
        for p in periods:
            period_label = str(p.get("report_period") or p.get("report_date") or "")
            net_profit = _safe_float(p.get("net_profit") or p.get("net_income") or p.get("n_income_attr_p"))
            if net_profit is not None:
                quarterly_data.append({
                    "period": period_label,
                    "net_profit": net_profit,
                })

        # 按时间排序（最旧到最新）
        quarterly_data.sort(key=lambda x: str(x.get("period", "")))

        # 取最近 8 个季度
        recent_quarters = quarterly_data[-8:] if len(quarterly_data) >= 8 else quarterly_data

        if len(recent_quarters) < 3:
            return _json_response({
                "status": "insufficient_data",
                "message": f"仅获取到 {len(recent_quarters)} 个季度的净利润数据，至少需要 3 个季度进行分析",
                "symbol": normalized_symbol,
                "recent_quarters_data": recent_quarters,
                "data_quality": "insufficient",
            })

        # 3. 计算环比增长率和趋势偏离
        enhanced_quarters: List[Dict[str, Any]] = []
        for i, q in enumerate(recent_quarters):
            entry = {
                "period": q["period"],
                "net_profit": q["net_profit"],
                "sequential_growth": None,
                "expected_profit": None,
                "surprise": None,
                "surprise_pct": None,
                "surprise_category": None,
            }
            if i > 0:
                prev_np = recent_quarters[i - 1]["net_profit"]
                if prev_np != 0:
                    entry["sequential_growth"] = round((q["net_profit"] - prev_np) / abs(prev_np), 4)
            enhanced_quarters.append(entry)

        # 4. 计算趋势线（简单线性回归：最近 8 个季度）
        np_values = [q["net_profit"] for q in enhanced_quarters]
        n = len(np_values)
        x_mean = (n - 1) / 2
        y_mean = mean(np_values)
        numerator = sum((i - x_mean) * (np_values[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        slope = numerator / denominator if denominator != 0 else 0
        intercept = y_mean - slope * x_mean

        # 计算每个季度的预期值（趋势值）和惊喜
        surprises: List[Dict[str, Any]] = []
        for i, entry in enumerate(enhanced_quarters):
            expected = intercept + slope * i
            actual = entry["net_profit"]
            if expected != 0:
                surprise_pct = (actual - expected) / abs(expected)
                entry["expected_profit"] = round(expected, 2)
                entry["surprise"] = round(actual - expected, 2)
                entry["surprise_pct"] = round(surprise_pct, 4)

                # 分类惊喜程度
                if surprise_pct > 0.20:
                    category = "large_positive_surprise"
                elif surprise_pct > 0.05:
                    category = "moderate_positive_surprise"
                elif surprise_pct > -0.05:
                    category = "in_line"
                elif surprise_pct > -0.20:
                    category = "moderate_negative_surprise"
                else:
                    category = "large_negative_surprise"
                entry["surprise_category"] = category

                # 记录显著的惊喜/惊吓
                if abs(surprise_pct) > 0.20:
                    surprises.append({
                        "period": entry["period"],
                        "actual_profit": actual,
                        "expected_profit": round(expected, 2),
                        "surprise_pct": round(surprise_pct, 4),
                        "category": category,
                    })

        # 5. 整体情绪判断
        if surprises:
            positive_count = sum(1 for s in surprises if s["surprise_pct"] > 0)
            negative_count = sum(1 for s in surprises if s["surprise_pct"] < 0)
            total_surprises = len(surprises)
            if positive_count >= total_surprises * 0.7:
                overall_sentiment = "predominantly_positive"
            elif negative_count >= total_surprises * 0.7:
                overall_sentiment = "predominantly_negative"
            elif positive_count > negative_count:
                overall_sentiment = "mixed_positive"
            elif negative_count > positive_count:
                overall_sentiment = "mixed_negative"
            else:
                overall_sentiment = "mixed"
        else:
            overall_sentiment = "stable"

        # 检查趋势方向
        if slope > 0:
            trend_desc = "上升"
        elif slope < 0:
            trend_desc = "下降"
        else:
            trend_desc = "持平"

        recent_surprises = surprises[-5:] if len(surprises) > 5 else surprises

        total_periods_available = len(quarterly_data)
        periods_analyzed = len(enhanced_quarters)

        return _json_response({
            "status": "success",
            "symbol": normalized_symbol,
            "total_periods_available": total_periods_available,
            "periods_analyzed": periods_analyzed,
            "recent_quarters_data": list(reversed(enhanced_quarters)),
            "recent_surprises_list": recent_surprises,
            "overall_sentiment": overall_sentiment,
            "trend_description": f"净利润趋势{trend_desc}（斜率={round(slope, 2)}）",
            "estimated_trend_params": {
                "slope": round(slope, 2),
                "intercept": round(intercept, 2),
            },
            "data_quality": "sufficient" if periods_analyzed >= 6 else "limited",
            "methodology_note": (
                "由于系统不含券商盈利预测数据，'expected_profit' 基于最近 8 个季度净利润的简单线性回归趋势线估算。"
                "'surprise' = actual_profit - expected_profit，大于 ±20% 视为显著意外变化。"
                "此方法无法区分季节性影响，仅供参考。"
            ),
            "warnings": (
                ["数据量有限，趋势线参考价值受限"] if periods_analyzed < 6
                else ["缺乏官方盈利预测数据，以趋势线作为预期基准"]
            ),
        })
    except Exception as exc:
        logger.error("业绩预告分析获取失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"业绩预告分析获取失败: {exc}"})


__all__ = [
    "get_cashflow_quality_deep",
    "get_earnings_surprise_analysis",
]