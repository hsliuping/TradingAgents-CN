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
from core.tools.implementations.risk.extended_risk_models import (
    _detect_period_type,
    _annualize_factor,
    _PERIOD_LABELS,
)

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
    capability_tags=["cashflow_quality", "cashflow", "fcf", "cashflow_analysis", "financial_quality", "fundamentals", "cashflow_deterioration"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["cashflow_quality_analysis", "fcf_yield_assessment", "cashflow_stability_evaluation"],
    when_to_use="当需要深度现金流质量分析、FCF收益率、现金流稳定性评分、OCF/净利润比率趋势时使用。",
    returns="返回 JSON 字符串，包含 fcf、fcf_yield、ocf_to_np_ratio、stability_score、trend_direction、flags。",
    example="get_cashflow_quality_deep(symbol='600519')",
)
def get_cashflow_quality_deep(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"],
) -> str:
    """获取现金流质量深度增强数据。

    Args:
        symbol: A 股股票代码，如 "600519"、"000001"

    Returns:
        str: JSON 字符串，字段说明——
            status: 状态: "success" | "no_data" | "error"
            symbol: 标准化后的股票代码
            years_analyzed: 已分析的年数
            current_price: 当前股价
            total_market_cap: 总市值
            fcf: 最新一年自由现金流
            fcf_yield: 自由现金流收益率（小数）
            fcf_yield_pct: 自由现金流收益率（%）
            ocf_to_net_profit: dict OCF/净利润比率——
                — current: 最新值
                — average: 平均值
                — min: 最小值
                — max: 最大值
            stability_score: 现金流稳定性评分（0-100）
            quality_score: 现金流质量综合评分（0-100）
            score_components: dict 评分细分（fcf_positive_ratio / avg_ocf_to_net_profit / stability_score）
            trend_direction: 趋势方向: "improving" | "stable" | "deteriorating"
            flags: list[str] 信号标签列表
            trend_series: list[dict] 趋势序列（最多10年），元素结构——
                — year: 年份
                — report_period: 报告期
                — ocf_to_net_profit: OCF/净利润
                — fcf_to_net_profit: FCF/净利润
                — operating_cashflow: 经营现金流
                — free_cashflow: 自由现金流
            coverage: dict 数据覆盖度
            data_quality: 数据质量: "数据充足" | "数据有限" | "数据不足"
            warnings: list[str] 警告列表
            message: 错误信息（仅 status="error" 时存在）
    """
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
            "data_quality": "数据充足" if len(trend) >= 3 else "数据有限" if trend else "数据不足",
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
    capability_tags=["earnings_surprise", "earnings", "earnings_analysis", "profit_trend", "fundamentals", "earnings_quality"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["earnings_surprise_detection", "profit_trend_analysis", "earnings_consistency_evaluation"],
    when_to_use="当需要分析季度业绩趋势、识别业绩惊喜/惊吓、评估业绩一致性时使用。",
    returns="返回 JSON 字符串，包含 recent_quarters_data、recent_surprises_list、overall_sentiment、data_quality、methodology_note。",
    example="get_earnings_surprise_analysis(symbol='600519')",
)
def get_earnings_surprise_analysis(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"],
) -> str:
    """获取业绩预告/盈利惊喜分析。

    Args:
        symbol: A 股股票代码，如 "600519"、"000001"

    Returns:
        str: JSON 字符串，字段说明——
            status: 状态: "success" | "no_data" | "insufficient_data" | "error"
            symbol: 标准化后的股票代码
            total_periods_available: 可用期间总数
            periods_analyzed: 实际分析的期间数
            recent_quarters_data: list[dict] 最近年度数据（最新在前），元素结构——
                — period: 报告期
                — period_type: 期间类型: "annual" | "q3" | "h1" | "q1" | "unknown"
                — period_label: 期间中文标签
                — net_profit: 原始净利润
                — net_profit_annualized: 年化净利润
                — yoy_growth: 同比增长率
                — expected_profit: 趋势预期净利润
                — surprise: 惊喜额（实际-预期）
                — surprise_pct: 惊喜百分比
                — surprise_category: 惊喜类别: "大幅正向惊喜" | "温和正向惊喜" | "符合预期" | "温和负向惊喜" | "大幅负向惊喜"
            recent_surprises_list: list[dict] 显著惊喜列表（|surprise_pct|>20%），元素结构——
                — period: 报告期
                — period_label: 期间标签
                — actual_profit_annualized: 实际年化净利润
                — actual_profit_raw: 原始净利润
                — expected_profit: 预期净利润
                — surprise_pct: 惊喜百分比
                — category: 类别
            overall_sentiment: 整体业绩情绪: "整体偏多" | "整体偏空" | "谨慎偏多" | "谨慎偏空" | "多空均衡" | "稳定"
            trend_description: 趋势描述文本
            estimated_trend_params: dict 趋势线参数——
                — slope: 斜率
                — intercept: 截距
            data_quality: 数据质量: "数据充足" | "数据有限"
            methodology_note: 方法论说明
            warnings: list[str] 警告列表
            message: 错误或提示信息（仅 status 为 "error"/"no_data"/"insufficient_data" 时存在）
    """
    try:
        normalized_symbol = _normalize_symbol(symbol)
        if not normalized_symbol:
            return _json_response({"status": "error", "message": "无效股票代码"})

        # 1. 获取财务期间数据（最近 16 期，以确保有 8 个季度）
        periods = get_stock_financial_periods(normalized_symbol, limit=16) or []

        if not periods:
            return _json_response({"status": "no_data", "message": "未获取到财务期间数据", "symbol": normalized_symbol})

        # 2. 提取季度净利润数据，并进行口径处理
        # 🔑 关键：不同报告期（年报/季报）的净利润为累计值，不可直接做环比
        # 策略：优先筛选同一口径的数据（如全部取年报），若不足则按口径分组
        quarterly_data: List[Dict[str, Any]] = []
        caliber_warnings: List[str] = []
        for p in periods:
            period_label = str(p.get("report_period") or p.get("report_date") or "")
            net_profit = _safe_float(p.get("net_profit") or p.get("net_income") or p.get("n_income_attr_p"))
            if net_profit is not None:
                period_type = _detect_period_type(p)
                # 🔑 对非年报数据做年化处理，使口径统一为年报口径
                factor = _annualize_factor(period_type)
                net_profit_annualized = net_profit * factor
                quarterly_data.append({
                    "period": period_label,
                    "period_type": period_type,
                    "period_label": _PERIOD_LABELS.get(period_type, period_type),
                    "net_profit": net_profit,
                    "net_profit_annualized": net_profit_annualized,
                })
                if period_type != "annual" and period_type != "unknown":
                    caliber_warnings.append(f"{period_label}为{_PERIOD_LABELS.get(period_type, period_type)}口径，净利润已年化处理")

        # 按时间排序（最旧到最新）
        quarterly_data.sort(key=lambda x: str(x.get("period", "")))

        # 🔑 去重：同一年份保留口径最大的那条（优先年报 > 三季报 > 半年报 > 一季报）
        seen_years: Dict[str, Dict[str, Any]] = {}
        for q in quarterly_data:
            yr = str(q["period"])[:4]
            if yr not in seen_years:
                seen_years[yr] = q
            else:
                # 口径优先级：annual > q3 > h1 > q1
                priority = {"annual": 4, "q3": 3, "h1": 2, "q1": 1, "unknown": 0}
                if priority.get(q["period_type"], 0) > priority.get(seen_years[yr]["period_type"], 0):
                    seen_years[yr] = q
        yearly_data = sorted(seen_years.values(), key=lambda x: str(x.get("period", "")))

        # 取最近 8 年（年化后按年比较）
        recent_quarters = yearly_data[-8:] if len(yearly_data) >= 8 else yearly_data

        if len(recent_quarters) < 3:
            return _json_response({
                "status": "insufficient_data",
                "message": f"仅获取到 {len(recent_quarters)} 个年度的净利润数据，至少需要 3 个年度进行分析",
                "symbol": normalized_symbol,
                "recent_quarters_data": recent_quarters,
                "data_quality": "数据不足",
            })

        # 3. 计算同比增长率和趋势偏离（使用年化净利润）
        enhanced_quarters: List[Dict[str, Any]] = []
        for i, q in enumerate(recent_quarters):
            entry = {
                "period": q["period"],
                "period_type": q.get("period_type", "unknown"),
                "period_label": q.get("period_label", ""),
                "net_profit": q["net_profit"],
                "net_profit_annualized": q["net_profit_annualized"],
                "yoy_growth": None,
                "expected_profit": None,
                "surprise": None,
                "surprise_pct": None,
                "surprise_category": None,
            }
            if i > 0:
                # 🔑 使用年化值做同比，避免口径差异
                prev_np_ann = recent_quarters[i - 1]["net_profit_annualized"]
                cur_np_ann = q["net_profit_annualized"]
                if prev_np_ann != 0:
                    entry["yoy_growth"] = round((cur_np_ann - prev_np_ann) / abs(prev_np_ann), 4)
            enhanced_quarters.append(entry)

        # 4. 计算趋势线（简单线性回归：基于年化净利润）
        np_values = [q["net_profit_annualized"] for q in enhanced_quarters]
        n = len(np_values)
        x_mean = (n - 1) / 2
        y_mean = mean(np_values)
        numerator = sum((i - x_mean) * (np_values[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        slope = numerator / denominator if denominator != 0 else 0
        intercept = y_mean - slope * x_mean

        # 计算每个年度的预期值（趋势值）和惊喜（使用年化净利润）
        surprises: List[Dict[str, Any]] = []
        for i, entry in enumerate(enhanced_quarters):
            expected = intercept + slope * i
            actual = entry["net_profit_annualized"]
            if expected != 0:
                surprise_pct = (actual - expected) / abs(expected)
                entry["expected_profit"] = round(expected, 2)
                entry["surprise"] = round(actual - expected, 2)
                entry["surprise_pct"] = round(surprise_pct, 4)

                # 分类惊喜程度
                if surprise_pct > 0.20:
                    category = "大幅正向惊喜"
                elif surprise_pct > 0.05:
                    category = "温和正向惊喜"
                elif surprise_pct > -0.05:
                    category = "符合预期"
                elif surprise_pct > -0.20:
                    category = "温和负向惊喜"
                else:
                    category = "大幅负向惊喜"
                entry["surprise_category"] = category

                # 记录显著的惊喜/惊吓
                if abs(surprise_pct) > 0.20:
                    surprises.append({
                        "period": entry["period"],
                        "period_label": entry.get("period_label", ""),
                        "actual_profit_annualized": actual,
                        "actual_profit_raw": entry["net_profit"],
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
                overall_sentiment = "整体偏多"
            elif negative_count >= total_surprises * 0.7:
                overall_sentiment = "整体偏空"
            elif positive_count > negative_count:
                overall_sentiment = "谨慎偏多"
            elif negative_count > positive_count:
                overall_sentiment = "谨慎偏空"
            else:
                overall_sentiment = "多空均衡"
        else:
            overall_sentiment = "稳定"

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
            "data_quality": "数据充足" if periods_analyzed >= 6 else "数据有限",
            "methodology_note": (
                "由于系统不含券商盈利预测数据，'expected_profit' 基于最近 8 个年度净利润（年化后）的简单线性回归趋势线估算。"
                "'surprise' = actual_profit_annualized - expected_profit，大于 ±20% 视为显著意外变化。"
                "同一年份优先采用年报数据，季报数据已做年化处理以统一口径。"
            ),
            "warnings": (
                ["数据量有限，趋势线参考价值受限"] + caliber_warnings if periods_analyzed < 6
                else ["缺乏官方盈利预测数据，以趋势线作为预期基准"] + caliber_warnings
            ),
        })
    except Exception as exc:
        logger.error("业绩预告分析获取失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"业绩预告分析获取失败: {exc}"})


__all__ = [
    "get_cashflow_quality_deep",
    "get_earnings_surprise_analysis",
]