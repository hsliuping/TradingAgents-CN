"""债券分析工具：收益率计算、信用利差分析、久期与凸性计算。"""

import datetime
import json
import logging
import math
from typing import Annotated, Optional, Any

import numpy as np
import pandas as pd
from langchain_core.tools import tool

from core.tools.base import register_tool

logger = logging.getLogger(__name__)

_TENORS = ["3月", "6月", "1年", "3年", "5年", "7年", "10年", "30年"]


def _fetch_china_yield_curve() -> dict:
    """通过 AKShare 获取中国国债收益率曲线最新数据。"""
    try:
        import akshare as ak
        df = ak.bond_china_yield()
        treasury = df[df["曲线名称"] == "中债国债收益率曲线"]
        if treasury.empty:
            return {"status": "no_data", "message": "未找到国债收益率曲线数据"}
        treasury["日期"] = pd.to_datetime(treasury["日期"])
        latest = treasury.loc[treasury["日期"].idxmax()]
        yields = {}
        for col in _TENORS:
            val = latest.get(col)
            if val is not None and val == val:
                yields[col] = round(float(val), 4)
            else:
                yields[col] = None
        return {
            "status": "ok",
            "date": str(latest["日期"].date()),
            "yields": yields,
        }
    except Exception as e:
        logger.warning("AKShare 国债收益率获取失败: %s", e)
        return {"status": "error", "message": str(e)}


def _fetch_china_multi_curve() -> dict:
    """通过 AKShare 获取多条收益率曲线（国债、AAA中短期票据、AAA银行普通债）。"""
    try:
        import akshare as ak
        df = ak.bond_china_yield()
        df["日期"] = pd.to_datetime(df["日期"])
        curves_found = {}
        latest_dates = {}
        for curve_name in [
            "中债国债收益率曲线",
            "中债中短期票据收益率曲线(AAA)",
            "中债商业银行普通债收益率曲线(AAA)",
        ]:
            subset = df[df["曲线名称"] == curve_name]
            if subset.empty:
                curves_found[curve_name] = {"status": "no_data"}
                continue
            latest = subset.loc[subset["日期"].idxmax()]
            latest_dates[curve_name] = str(latest["日期"].date())
            yields = {}
            for col in _TENORS:
                val = latest.get(col)
                if val is not None and val == val:
                    yields[col] = round(float(val), 4)
                else:
                    yields[col] = None
            curves_found[curve_name] = {
                "status": "ok",
                "date": str(latest["日期"].date()),
                "yields": yields,
            }
        # 整体最新日期
        all_dates = set(v["date"] for v in curves_found.values() if v.get("status") == "ok" and v.get("date"))
        return {
            "status": "ok",
            "date": max(all_dates) if all_dates else None,
            "curves": curves_found,
        }
    except Exception as e:
        logger.warning("AKShare 多曲线获取失败: %s", e)
        return {"status": "error", "message": str(e)}


def _fetch_zh_us_rate() -> dict:
    """通过 AKShare 获取中美收益率对比最新数据。"""
    try:
        import akshare as ak
        df = ak.bond_zh_us_rate()
        df["日期"] = pd.to_datetime(df["日期"])
        latest = df.sort_values("日期").iloc[-1]
        result = {
            "date": str(latest["日期"].date()),
            "china": {},
            "us": {},
        }
        cn_cols = {"中国国债收益率2年": "2年", "中国国债收益率5年": "5年",
                    "中国国债收益率10年": "10年", "中国国债收益率30年": "30年"}
        us_cols = {"美国国债收益率2年": "2年", "美国国债收益率5年": "5年",
                    "美国国债收益率10年": "10年", "美国国债收益率30年": "30年"}
        for raw, name in cn_cols.items():
            v = latest.get(raw)
            if v is not None and v == v:
                result["china"][name] = round(float(v), 4)
        for raw, name in us_cols.items():
            v = latest.get(raw)
            if v is not None and v == v:
                result["us"][name] = round(float(v), 4)
        return result
    except Exception as e:
        logger.warning("AKShare 中美收益率获取失败: %s", e)
        return {"status": "error", "message": str(e)}


def _classify_curve_shape(yields: dict) -> str:
    """根据收益率数据判断曲线形态。"""
    y1 = yields.get("1年")
    y10 = yields.get("10年")
    y3m = yields.get("3月")
    if y10 is not None and y1 is not None:
        if y10 > y1 + 0.5:
            return "正常向上倾斜（Normal Upward Sloping）"
        elif y10 < y1 - 0.1:
            return "倒挂（Inverted）"
        else:
            return "平坦（Flat）"
    if y10 is not None and y3m is not None:
        if y10 > y3m + 0.5:
            return "正常向上倾斜（Normal Upward Sloping）"
        elif y10 < y3m - 0.1:
            return "倒挂（Inverted）"
        else:
            return "平坦（Flat）"
    return "数据不足无法判断"


def _generate_yield_commentary(yields: dict, date: str) -> str:
    """生成收益率水平评论。"""
    y10 = yields.get("10年")
    y2 = yields.get("1年")
    if y10 is None:
        return "收益率数据不足，无法生成解读。"
    parts = [f"截至 {date}，中国10年期国债收益率为 {y10}%。"]
    if y10 < 1.5:
        parts.append("10Y收益率处于历史低位区间，反映市场对经济前景偏谨慎及宽松货币预期。")
    elif y10 < 2.5:
        parts.append("10Y收益率处于偏低水平，债券定价偏贵，资本利得空间有限。")
    elif y10 < 3.5:
        parts.append("10Y收益率处于中等偏低区间，债券估值中性偏贵。")
    elif y10 < 4.5:
        parts.append("10Y收益率处于中等偏高区间，配置价值逐步显现。")
    else:
        parts.append("10Y收益率处于高位区间，债券具备较好的配置价值。")
    if y2 is not None and y10 is not None:
        spread = y10 - y2
        if spread > 1.0:
            parts.append(f"期限利差（10Y-1Y）为 {spread:.2f}%，曲线陡峭，长端风险溢价较高。")
        elif spread > 0.3:
            parts.append(f"期限利差（10Y-1Y）为 {spread:.2f}%，曲线形态正常。")
        elif spread > 0:
            parts.append(f"期限利差（10Y-1Y）为 {spread:.2f}%，曲线平坦化。")
        else:
            parts.append(f"期限利差（10Y-1Y）为 {spread:.2f}%，曲线倒挂，需关注衰退风险。")
    return " ".join(parts)


def _generate_spread_commentary(spreads: dict, date: str) -> str:
    """生成信用利差评论。"""
    if not spreads:
        return "信用利差数据不足，无法生成解读。"
    parts = [f"截至 {date}，信用利差分析如下："]
    avg_spreads = [v for v in spreads.values() if v is not None]
    if avg_spreads:
        avg = sum(avg_spreads) / len(avg_spreads)
        if avg > 2.0:
            parts.append(
                f"平均信用利差约 {avg:.2f}%，处于偏高水平，"
                "反映市场风险偏好较低或信用环境偏紧。"
            )
        elif avg > 1.0:
            parts.append(
                f"平均信用利差约 {avg:.2f}%，处于中等水平，"
                "信用定价合理，市场风险偏好中性。"
            )
        else:
            parts.append(
                f"平均信用利差约 {avg:.2f}%，处于偏低水平，"
                "反映市场风险偏好较高或流动性充裕。"
            )
    # 期限结构判断
    short_tenors = ["1年", "3年"]
    long_tenors = ["5年", "7年", "10年"]
    short_vals = [spreads.get(t) for t in short_tenors if spreads.get(t) is not None]
    long_vals = [spreads.get(t) for t in long_tenors if spreads.get(t) is not None]
    if short_vals and long_vals:
        short_avg = sum(short_vals) / len(short_vals)
        long_avg = sum(long_vals) / len(long_vals)
        if long_avg > short_avg + 0.3:
            parts.append("信用利差期限结构向上倾斜，长端信用风险溢价显著。")
        elif long_avg < short_avg - 0.2:
            parts.append("信用利差期限结构倒挂，短端信用风险溢价更高。")
        else:
            parts.append("信用利差期限结构平坦。")
    return " ".join(parts)


def _calculate_duration_convexity(
    coupon_rate: float,
    years_to_maturity: float,
    yield_to_maturity: float,
    frequency: int,
) -> dict:
    """计算 Macaulay 久期、修正久期和凸性。

    Args:
        coupon_rate: 票面利率（小数形式，如 0.03 表示 3%）
        years_to_maturity: 剩余期限（年）
        yield_to_maturity: 到期收益率（小数形式，如 0.03 表示 3%）
        frequency: 年付息频率（1=年付, 2=半年付）

    Returns:
        包含 macaulay_duration, modified_duration, convexity, price, cash_flows 的字典
    """
    face_value = 100.0
    coupon = coupon_rate * face_value / frequency
    n_periods = int(years_to_maturity * frequency)
    ytm_per_period = yield_to_maturity / frequency

    # 计算各期现金流
    cf_times = []
    cf_amounts = []
    for i in range(1, n_periods + 1):
        t = i  # 期数
        if i == n_periods:
            cf = coupon + face_value  # 最后一期包含本金
        else:
            cf = coupon
        cf_times.append(t)
        cf_amounts.append(cf)

    # 计算现值
    pv_factors = [cf / ((1 + ytm_per_period) ** t) for t, cf in zip(cf_times, cf_amounts)]
    price = sum(pv_factors)

    if price <= 0:
        return {"error": "债券价格为负或零，无法计算久期和凸性"}

    # Macaulay Duration（单位：期数）
    macaulay_periods = sum(t * pv for t, pv in zip(cf_times, pv_factors)) / price
    # Macaulay Duration（单位：年）
    macaulay_duration_years = macaulay_periods / frequency

    # Modified Duration
    modified_duration = macaulay_duration_years / (1 + ytm_per_period)

    # Convexity
    # Convexity = Σ [t * (t + 1/frequency) * PV_CF_t] / (Price * (1 + ytm/f)^2)
    # 其中 t 为期数，frequency 为年付息次数
    convexity_numerator = sum(
        t * (t + 1.0 / frequency) * pv
        for t, pv in zip(cf_times, pv_factors)
    )
    convexity = convexity_numerator / (price * (1 + ytm_per_period) ** 2)

    # 价格变化估计（收益率上升 1% = 100bp = 0.01）
    delta_y = 0.01
    price_change_pct = -modified_duration * delta_y + 0.5 * convexity * (delta_y ** 2)

    # 生成现金流明细
    cash_flow_details = []
    for i, (t, cf, pv) in enumerate(zip(cf_times, cf_amounts, pv_factors)):
        cash_flow_details.append({
            "period": i + 1,
            "year": round(t / frequency, 4),
            "cash_flow": round(cf, 4),
            "present_value": round(pv, 4),
        })

    return {
        "price": round(price, 4),
        "macaulay_duration_years": round(macaulay_duration_years, 4),
        "modified_duration": round(modified_duration, 4),
        "convexity": round(convexity, 6),
        "price_change_1pct": {
            "yield_increase_1pct": round(price_change_pct * 100, 4),
            "explanation": "收益率上升1个百分点（100bp）时债券价格的近似变动百分比",
        },
        "cash_flows_summary": {
            "total_periods": n_periods,
            "total_coupon_payments": round(coupon * (n_periods - 1) + (coupon + face_value) if n_periods > 0 else 0, 4),
            "face_value": face_value,
        },
    }


# ── Tool 1: 债券收益率计算 ─────────────────────────────────────────

@tool
@register_tool(
    tool_id="get_bond_yield_calculation",
    name="国债收益率曲线",
    description=(
        "通过 akshare 实时获取中国国债收益率曲线及美国国债收益率数据，"
        "返回市场收益率水平而非个券 YTM。"
        "与 get_yield_curve_analysis 的区别：本工具侧重中美对比和收益水平分析，"
        "get_yield_curve_analysis 侧重曲线形态和利差分析。"
    ),
    category="fundamentals",
    is_online=True,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["bond", "yield_curve", "interest_rate", "macro"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["查询中国国债各期限收益率", "中美收益率曲线对比", "收益率水平市场解读"],
    when_to_use=(
        "当用户询问当前债券市场收益率水平、各期限国债收益率、"
        "中美收益率曲线对比、收益率曲线形态判断及市场含义解读时使用。"
    ),
    when_not_to_use=(
        "不适合计算单只个券的到期收益率（YTM）；"
        "不适合债券久期和凸性计算（请使用 get_bond_duration_convexity）；"
        "不适合信用利差分析（请使用 get_credit_spread_analysis）。"
    ),
    returns=(
        "返回 JSON 字符串，包含 date（数据日期）、yields_by_tenor（各期限收益率表）、"
        "yield_curve_shape_china（中国曲线形态）、yield_curve_shape_us（美国曲线形态）、"
        "commentary_with_key_levels（市场解读）。"
    ),
    example="get_bond_yield_calculation()",
    related_tools=["get_yield_curve_analysis", "get_credit_spread_analysis", "get_bond_duration_convexity"],
)
def get_bond_yield_calculation() -> str:
    """获取中国国债收益率曲线与美国国债收益率对比，并提供市场解读。

    使用 AKShare 的 bond_china_yield() 和 bond_zh_us_rate() 接口，
    返回最新各期限收益率及曲线形态判断。

    Returns:
        str: JSON 字符串，字段说明——
            status: 状态: "ok" | "error"
            date: 数据日期（YYYY-MM-DD）
            data_source: 数据源说明
            data_note: 数据注释（强调返回即期收益率曲线而非个券YTM）
            yields_by_tenor: list[dict] 各期限收益率表，元素结构——
                — tenor: 期限（如 "1年"、"10年"）
                — china_yield_pct: 中国该期限国债收益率（%）
            yield_curve_shape_china: 中国收益率曲线形态判断
            yield_curve_shape_us: 美国收益率曲线形态判断
            china_us_comparison: dict 中美利差对比（数据不可用时为 {"status": "unavailable"}）——
                — china_10y: 中国10年期收益率
                — us_10y: 美国10年期收益率
                — china_2y: 中国2年期收益率（实际取1年）
                — us_2y: 美国2年期收益率
                — cn_us_10y_spread: 中美10年期利差（百分点）
            commentary_with_key_levels: 市场解读文本（含关键水平）
            message: 错误信息（仅 status="error" 时存在）
            suggestion: 建议（仅部分错误场景存在）
    """
    try:
        curve = _fetch_china_yield_curve()
        zh_us = _fetch_zh_us_rate()

        if curve.get("status") == "error":
            return json.dumps({
                "status": "error",
                "message": f"国债收益率数据获取失败: {curve.get('message')}",
                "suggestion": "可通过 akshare.bond_china_yield() 直接获取",
            }, ensure_ascii=False, indent=2, default=str)

        yields = curve.get("yields", {})
        date = curve.get("date", "未知")

        # 曲线形态
        china_shape = _classify_curve_shape(yields)

        us_shape = "数据不足"
        if "status" not in zh_us and zh_us.get("us"):
            us_shape = _classify_curve_shape(zh_us["us"])

        # 中美利差
        cn_10y = yields.get("10年")
        us_10y = zh_us.get("us", {}).get("10年") if "status" not in zh_us else None
        cn_2y = yields.get("1年")
        us_2y = zh_us.get("us", {}).get("2年") if "status" not in zh_us else None

        spread_cn_us = None
        if cn_10y is not None and us_10y is not None:
            spread_cn_us = round(cn_10y - us_10y, 4)

        # 评论
        commentary = _generate_yield_commentary(yields, date)

        # 构建收益率表
        yields_table = []
        for tenor in _TENORS:
            cn_val = yields.get(tenor)
            yields_table.append({
                "tenor": tenor,
                "china_yield_pct": cn_val,
            })

        payload = {
            "status": "ok",
            "date": date,
            "data_source": "akshare.bond_china_yield() / bond_zh_us_rate()",
            "data_note": "本工具返回市场收益率水平（即期收益率曲线），非个券到期收益率计算。如需个券YTM计算，请使用债券定价模型。",
            "yields_by_tenor": yields_table,
            "yield_curve_shape_china": china_shape,
            "yield_curve_shape_us": us_shape,
            "china_us_comparison": {
                "china_10y": cn_10y,
                "us_10y": us_10y,
                "china_2y": cn_2y,
                "us_2y": us_2y,
                "cn_us_10y_spread": spread_cn_us,
            } if "status" not in zh_us else {"status": "unavailable"},
            "commentary_with_key_levels": commentary,
        }

        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("债券收益率计算失败: %s", exc, exc_info=True)
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2, default=str)


# ── Tool 2: 信用利差分析 ───────────────────────────────────────────

@tool
@register_tool(
    tool_id="get_credit_spread_analysis",
    name="信用利差分析",
    description=(
        "通过 akshare 实时获取中国债券市场多条收益率曲线，"
        "计算信用利差（AAA中短期票据/AAA银行普通债收益率 - 同期限国债收益率）。"
        "信用利差扩大反映市场风险偏好下降（避险情绪升温），"
        "信用利差收窄反映市场风险偏好上升（风险 appetite 增强）。"
    ),
    category="fundamentals",
    is_online=True,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["bond", "credit_spread", "credit_analysis", "macro"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["查询信用利差水平", "分析市场风险偏好", "债券信用定价分析"],
    when_to_use=(
        "当用户询问信用利差水平、AAA级债券与国债利差、"
        "市场风险偏好变化、信用债定价合理性时使用。"
    ),
    when_not_to_use=(
        "不适合单只信用债的个券信用评级分析；"
        "不适合计算个券到期收益率（YTM）；"
        "不适合查询国债收益率曲线本身（请使用 get_bond_yield_calculation）。"
    ),
    returns=(
        "返回 JSON 字符串，包含 date（数据日期）、credit_spreads_by_tenor（各期限信用利差表）、"
        "interpretation（市场解读）、warning_if_data_stale（数据时效警告）。"
    ),
    example="get_credit_spread_analysis()",
    related_tools=["get_bond_yield_calculation", "get_bond_duration_convexity"],
)
def get_credit_spread_analysis() -> str:
    """获取中国债券市场信用利差分析。

    利用 AKShare 获取多条收益率曲线，计算 AAA 中短期票据、
    AAA 银行普通债与同期限国债之间的信用利差。

    Returns:
        str: JSON 字符串，字段说明——
            status: 状态: "ok" | "error"
            date: 数据日期（YYYY-MM-DD）
            data_source: 数据源说明
            data_note: 数据注释（信用利差定义与解读说明）
            curves_available: dict 各曲线可用日期——
                — treasury: 国债收益率曲线数据日期
                — aaa_corporate_note: AAA中短期票据曲线日期
                — aaa_bank_note: AAA银行普通债曲线日期
            credit_spreads_by_tenor: list[dict] 各期限信用利差表，元素结构——
                — tenor: 期限
                — treasury_yield_%: 国债收益率（%）
                — aaa_corporate_spread_%: AAA企业债信用利差（%）
                — aaa_bank_spread_%: AAA银行债信用利差（%）
            key_tenor_spreads: dict 关键期限（1/3/5/7/10年）利差汇总——
                — <tenor>: 该期限下 aaa_corporate_spread / aaa_bank_spread
            interpretation: 市场解读文本
            warning_if_data_stale: 数据时效警告（数据较旧时返回字符串，否则为 None）
            message: 错误信息（仅 status="error" 时存在）
    """
    try:
        multi = _fetch_china_multi_curve()

        if multi.get("status") == "error":
            return json.dumps({
                "status": "error",
                "message": f"收益率曲线数据获取失败: {multi.get('message')}",
            }, ensure_ascii=False, indent=2, default=str)

        date = multi.get("date", "未知")
        curves = multi.get("curves", {})

        treasury = curves.get("中债国债收益率曲线", {})
        corporate = curves.get("中债中短期票据收益率曲线(AAA)", {})
        bank = curves.get("中债商业银行普通债收益率曲线(AAA)", {})

        treasury_yields = treasury.get("yields", {}) if treasury.get("status") == "ok" else {}
        corporate_yields = corporate.get("yields", {}) if corporate.get("status") == "ok" else {}
        bank_yields = bank.get("yields", {}) if bank.get("status") == "ok" else {}

        # 计算信用利差
        credit_spreads = {}
        for tenor in _TENORS:
            rf = treasury_yields.get(tenor)
            cr = corporate_yields.get(tenor)
            bk = bank_yields.get(tenor)
            entry = {"tenor": tenor}
            if rf is not None and cr is not None:
                entry["aaa_corporate_spread"] = round(cr - rf, 4)
                entry["aaa_corporate_yield"] = cr
            if rf is not None and bk is not None:
                entry["aaa_bank_spread"] = round(bk - rf, 4)
                entry["aaa_bank_yield"] = bk
            if rf is not None:
                entry["treasury_yield"] = rf
            credit_spreads[tenor] = entry

        # 关键期限利差汇总
        key_spreads = {}
        for tenor in ["1年", "3年", "5年", "7年", "10年"]:
            entry = credit_spreads.get(tenor, {})
            key = {}
            if "aaa_corporate_spread" in entry:
                key["aaa_corporate_spread"] = entry["aaa_corporate_spread"]
            if "aaa_bank_spread" in entry:
                key["aaa_bank_spread"] = entry["aaa_bank_spread"]
            if key:
                key_spreads[tenor] = key

        # 生成解读
        spread_values = {}
        for t in _TENORS:
            entry = credit_spreads.get(t, {})
            if "aaa_corporate_spread" in entry:
                spread_values[f"AAA企业债_{t}"] = entry["aaa_corporate_spread"]
            if "aaa_bank_spread" in entry:
                spread_values[f"AAA银行债_{t}"] = entry["aaa_bank_spread"]

        interpretation = _generate_spread_commentary(spread_values, date)

        # 数据时效检查
        warning = None
        if date and date != "未知":
            try:
                data_date = datetime.datetime.strptime(date, "%Y-%m-%d").date()
                today = datetime.date.today()
                diff = (today - data_date).days
                if diff > 5:
                    warning = f"数据已 {diff} 天未更新（最新日期 {date}），可能影响分析准确性。"
                elif diff > 2:
                    warning = f"数据为 {diff} 天前（{date}），时效性一般。"
            except (ValueError, TypeError):
                pass

        # 整理为表格格式输出
        spreads_table = []
        for tenor in _TENORS:
            entry = credit_spreads.get(tenor, {})
            row = {"tenor": tenor}
            if "treasury_yield" in entry:
                row["treasury_yield_%"] = entry["treasury_yield"]
            if "aaa_corporate_spread" in entry:
                row["aaa_corporate_spread_%"] = entry["aaa_corporate_spread"]
            if "aaa_bank_spread" in entry:
                row["aaa_bank_spread_%"] = entry["aaa_bank_spread"]
            spreads_table.append(row)

        payload = {
            "status": "ok",
            "date": date,
            "data_source": "akshare.bond_china_yield()",
            "data_note": (
                "信用利差 = 信用债收益率 - 同期限国债收益率。"
                "利差扩大 = 风险偏好下降（避险），利差收窄 = 风险偏好上升（逐险）。"
            ),
            "curves_available": {
                "treasury": treasury.get("date"),
                "aaa_corporate_note": corporate.get("date", "不可用"),
                "aaa_bank_note": bank.get("date", "不可用"),
            },
            "credit_spreads_by_tenor": spreads_table,
            "key_tenor_spreads": key_spreads,
            "interpretation": interpretation,
            "warning_if_data_stale": warning,
        }

        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("信用利差分析失败: %s", exc, exc_info=True)
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2, default=str)


# ── Tool 3: 债券久期与凸性 ─────────────────────────────────────────

@tool
@register_tool(
    tool_id="get_bond_duration_convexity",
    name="债券久期与凸性",
    description=(
        "计算固定利率债券的 Macaulay 久期、修正久期和凸性，"
        "并估算收益率变动对债券价格的影响。"
        "若不提供到期收益率，将自动获取当前10年期国债收益率作为参考。"
    ),
    category="fundamentals",
    is_online=True,
    auto_register=True,
    timeout_tier="medium",
    capability_tags=["bond", "duration", "convexity", "fixed_income"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["计算债券久期", "计算债券凸性", "估算利率变动对债券价格的影响"],
    when_to_use=(
        "当用户需要计算固定利率债券的 Macaulay 久期、修正久期、凸性，"
        "或估算收益率变动对债券价格的近似影响时使用。"
        "适用于标准化债券的久期凸性分析。"
    ),
    when_not_to_use=(
        "不适合浮动利率债券（久期计算方式不同）；"
        "不适合含权债券（如可赎回/可回售债券，需使用有效久期）；"
        "不适合查询市场收益率曲线（请使用 get_bond_yield_calculation）。"
    ),
    returns=(
        "返回 JSON 字符串，包含 macaulay_duration（Macaulay久期年）、"
        "modified_duration（修正久期）、convexity（凸性）、"
        "price_change_1pct（收益率升1%的价格变动估算）、"
        "parameters_used（使用的参数）、methodology（计算方法说明）。"
    ),
    example="get_bond_duration_convexity(coupon_rate=0.03, years_to_maturity=10, frequency=2)",
    related_tools=["get_bond_yield_calculation", "get_credit_spread_analysis"],
)
def get_bond_duration_convexity(
    coupon_rate: Annotated[float, "票面利率，如 0.03 表示 3%"] = 0.03,
    years_to_maturity: Annotated[float, "剩余期限（年）"] = 10.0,
    yield_to_maturity: Annotated[Optional[float], "到期收益率，不提供则自动获取当前10Y国债收益率"] = None,
    frequency: Annotated[int, "年付息频率，1=年付，2=半年付"] = 2,
) -> str:
    """计算固定利率债券的 Macaulay 久期、修正久期和凸性。

    若不提供 yield_to_maturity，将通过 akshare 获取当前10年期国债收益率。

    Args:
        coupon_rate: 票面利率（小数，如 0.03 表示 3%），默认 0.03
        years_to_maturity: 剩余期限（年），默认 10.0
        yield_to_maturity: 到期收益率（小数），为 None 时自动获取当前10年期国债收益率，默认 None
        frequency: 年付息频率，可选 1（年付）/ 2（半年付）/ 4（季付）/ 12（月付），默认 2

    Returns:
        str: JSON 字符串，字段说明——
            status: 状态: "ok" | "error"
            macaulay_duration: dict Macaulay 久期——
                — years: 久期年数
                — description: 含义说明
            modified_duration: dict 修正久期——
                — value: 修正久期数值
                — description: 含义说明
            convexity: dict 凸性——
                — value: 凸性数值
                — description: 含义说明
            price_change_1pct: dict 收益率上升1%时的价格变动估算——
                — yield_increase_1pct_pct_change: 价格变动百分比
                — explanation: 解释文本
                — formula: 使用的公式
                — linear_estimate_only_mod_duration: 仅久期线性估算的百分比
                — with_convexity_adjustment: 含凸性调整后的百分比
            bond_price: dict 债券价格——
                — current_price: 当前价格
                — face_value: 面值（100.0）
            parameters_used: dict 实际使用的参数——
                — coupon_rate: 票面利率（小数）
                — coupon_rate_pct: 票面利率（%）
                — years_to_maturity: 剩余期限
                — yield_to_maturity: 到期收益率（小数）
                — yield_to_maturity_pct: 到期收益率（%）
                — frequency: 付息频率文本说明
                — payment_periods: 总付息期数
            methodology: dict 各指标计算方法说明（macaulay_duration/modified_duration/convexity/price_change）
            message: 错误信息（仅 status="error" 时存在）
    """
    try:
        if yield_to_maturity is None:
            curve = _fetch_china_yield_curve()
            if curve.get("status") == "ok":
                y10 = curve.get("yields", {}).get("10年")
                if y10 is not None:
                    yield_to_maturity = y10 / 100.0  # 转为小数
                else:
                    return json.dumps({
                        "status": "error",
                        "message": "无法获取当前10年期国债收益率，请手动提供 yield_to_maturity 参数",
                    }, ensure_ascii=False, indent=2, default=str)
            else:
                return json.dumps({
                    "status": "error",
                    "message": f"自动获取收益率失败: {curve.get('message')}，请手动提供 yield_to_maturity 参数",
                }, ensure_ascii=False, indent=2, default=str)

        if coupon_rate < 0 or coupon_rate > 1:
            return json.dumps({
                "status": "error",
                "message": "票面利率 coupon_rate 应在 0~1 范围内（如 0.03 表示 3%）",
            }, ensure_ascii=False, indent=2, default=str)

        if yield_to_maturity < 0 or yield_to_maturity > 1:
            return json.dumps({
                "status": "error",
                "message": "到期收益率 yield_to_maturity 应在 0~1 范围内（如 0.03 表示 3%）",
            }, ensure_ascii=False, indent=2, default=str)

        if years_to_maturity <= 0:
            return json.dumps({
                "status": "error",
                "message": "剩余期限 years_to_maturity 必须大于 0",
            }, ensure_ascii=False, indent=2, default=str)

        if frequency not in (1, 2, 4, 12):
            return json.dumps({
                "status": "error",
                "message": "付息频率 frequency 仅支持 1（年付）、2（半年付）、4（季付）、12（月付）",
            }, ensure_ascii=False, indent=2, default=str)

        result = _calculate_duration_convexity(
            coupon_rate=coupon_rate,
            years_to_maturity=years_to_maturity,
            yield_to_maturity=yield_to_maturity,
            frequency=frequency,
        )

        if "error" in result:
            return json.dumps({
                "status": "error",
                "message": result["error"],
            }, ensure_ascii=False, indent=2, default=str)

        payload = {
            "status": "ok",
            "macaulay_duration": {
                "years": result["macaulay_duration_years"],
                "description": "Macaulay 久期 = Σ(t × PV_CF_t) / 债券价格，表示回收投资本息的平均时间（年）",
            },
            "modified_duration": {
                "value": result["modified_duration"],
                "description": "修正久期 = Macaulay 久期 / (1 + YTM/付息频率)，表示收益率变动 1% 时价格的近似变动百分比",
            },
            "convexity": {
                "value": result["convexity"],
                "description": "凸性 = Σ[t × (t+1/f) × PV_CF_t] / (价格 × (1+YTM/f)²)，衡量久期对收益率变化的敏感度",
            },
            "price_change_1pct": {
                "yield_increase_1pct_pct_change": result["price_change_1pct"]["yield_increase_1pct"],
                "explanation": result["price_change_1pct"]["explanation"],
                "formula": "ΔP/P ≈ -ModDuration × Δy + 0.5 × Convexity × (Δy)²",
                "linear_estimate_only_mod_duration": round(-result["modified_duration"] * 0.01 * 100, 4),
                "with_convexity_adjustment": result["price_change_1pct"]["yield_increase_1pct"],
            },
            "bond_price": {
                "current_price": result["price"],
                "face_value": 100.0,
            },
            "parameters_used": {
                "coupon_rate": coupon_rate,
                "coupon_rate_pct": round(coupon_rate * 100, 2),
                "years_to_maturity": years_to_maturity,
                "yield_to_maturity": round(yield_to_maturity, 6),
                "yield_to_maturity_pct": round(yield_to_maturity * 100, 4),
                "frequency": f"每{'半' if frequency == 2 else ''}年{' ' if frequency == 1 else ''}{frequency}次"
                            if frequency <= 2 else f"每年 {frequency} 次",
                "payment_periods": int(years_to_maturity * frequency),
            },
            "methodology": {
                "macaulay_duration": "Macaulay Duration = Σ(t × PV_CF_t) / Σ(PV_CF_t)，其中 t 为现金流时间（年），PV_CF_t 为各期现金流现值",
                "modified_duration": "Modified Duration = Macaulay Duration / (1 + YTM / frequency)",
                "convexity": "Convexity = Σ[t × (t + 1/frequency) × PV_CF_t] / (Price × (1 + YTM/frequency)²)",
                "price_change": "ΔP/P ≈ -MD × Δy + 0.5 × Convexity × (Δy)²",
            },
        }

        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("债券久期与凸性计算失败: %s", exc, exc_info=True)
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2, default=str)


__all__ = [
    "get_bond_yield_calculation",
    "get_credit_spread_analysis",
    "get_bond_duration_convexity",
]