"""扩展风险模型工具：Ohlson O-Score、应收账款质量、存货质量、流动性压力测试、债务结构分析"""

import json
import logging
import math
from typing import Annotated, Optional, Any

import numpy as np
from langchain_core.tools import tool

from core.skill_runtime.data_access import get_stock_financial_periods
from core.tools.base import register_tool

logger = logging.getLogger(__name__)


def _safe_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _safe_div(numerator, denominator) -> float | None:
    n = _safe_float(numerator)
    d = _safe_float(denominator)
    if n is None or d is None or d == 0:
        return None
    return n / d


def _pct_change(current, previous) -> float | None:
    c = _safe_float(current)
    p = _safe_float(previous)
    if c is None or p is None or p == 0:
        return None
    return (c - p) / abs(p)


# ============================================================================
# 报告期口径检测（避免季报 vs 年报的错误比较）
# ============================================================================

_PERIOD_LABELS = {"q1": "一季报", "h1": "半年报", "q3": "三季报", "annual": "年报", "unknown": "未知"}


def _detect_period_type(fin: dict) -> str:
    """返回 period_type: annual / q1 / h1 / q3 / unknown"""
    rp = str(fin.get("report_period") or fin.get("report_date") or fin.get("end_date") or "").strip()
    if not rp:
        return "unknown"
    # 提取月份：支持 "2025-03-31" 和 "20250331" 两种格式
    digits = "".join(ch for ch in rp[:10] if ch.isdigit())
    if len(digits) >= 6:
        month_part = digits[4:6]
    elif "-" in rp and len(rp) >= 7:
        month_part = rp[:10].split("-")[1]
    else:
        month_part = ""
    return {"03": "q1", "06": "h1", "09": "q3", "12": "annual"}.get(month_part, "unknown")


def _annualize_factor(period_type: str) -> float:
    """年化因子：年报=1, 一季报=4, 半年报=2, 三季报=4/3"""
    return {"annual": 1.0, "q1": 4.0, "h1": 2.0, "q3": 4.0 / 3.0}.get(period_type, 1.0)


def _find_same_period_prev(fin_data_list: list, cur_period_type: str) -> tuple:
    """找相同口径的上期数据做同比。返回 (fin_prev, prev_period_type, period_mismatch)"""
    for candidate in fin_data_list[1:]:
        if _detect_period_type(candidate) == cur_period_type:
            return candidate, cur_period_type, False
    # 退而求其次用最近一期
    if len(fin_data_list) > 1:
        fin_prev = fin_data_list[1]
        prev_type = _detect_period_type(fin_prev)
        mismatch = (prev_type != cur_period_type and cur_period_type != "unknown")
        return fin_prev, prev_type, mismatch
    return None, "unknown", False


def _period_caliber_payload(cur_type: str, prev_type: str, mismatch: bool) -> dict:
    """生成口径信息 payload"""
    return {
        "current": cur_type,
        "previous": prev_type,
        "period_mismatch": mismatch,
        "annualized": cur_type != "annual" and cur_type != "unknown",
    }


# ============================================================================
# Tool 1:  Ohlson O-Score 破产预测
# ============================================================================

@tool
@register_tool(
    tool_id="get_ohlson_oscore",
    name="Ohlson O-Score 破产预测",
    description="基于Ohlson O-Score logit模型预测A股公司破产概率，综合考虑公司规模、负债水平、流动性、盈利能力等六个维度。",
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["bankruptcy_risk", "financial_distress"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["bankruptcy_probability_prediction"],
    when_to_use="当需要量化评估公司破产概率、识别财务困境风险时使用，尤其适合制造业和成熟企业。",
    when_not_to_use="不适用于金融行业公司（财务报表结构不同）；O-Score对高成长科技公司准确率有限。",
    returns="返回JSON字符串，包含o_score、probability、risk_level、components和data_quality。",
    example="get_ohlson_oscore(symbol='600519')",
    related_tools=["get_altman_zscore", "get_piotroski_fscore"],
)
def get_ohlson_oscore(symbol: Annotated[str, "A 股股票代码，如 600519、000001"]) -> str:
    """计算 Ohlson O-Score 破产概率。基于 logit 模型综合公司规模、负债、流动性、盈利等维度预测破产概率。

    Args:
        symbol: A 股股票代码，如 600519、000001

    Returns:
        str: JSON 字符串，字段说明——
            status: "success" | "error"
            symbol: 标的股票代码
            o_score: O-Score 评分（越高破产概率越大）
            probability: 破产概率（0-1，由 O-Score 经 logit 转换得到）
            risk_level: 风险等级，"high"（>0.5） | "medium"（>0.15） | "low"
            components: dict，六个分量——
                — x1_log_assets: log(总资产)
                — x2_debt_ratio: 总负债 / 总资产
                — x3_wc_to_assets: 营运资金 / 总资产
                — x4_cl_to_ca: 流动负债 / 流动资产
                — x5_liab_exceeds_assets: 资不抵债虚拟变量（1.0 或 0.0）
                — x6_ni_change: 净利润变化率（口径不一致或数据缺失时为 None）
            interpretation: dict，解读——
                — o_score: O-Score
                — probability: 破产概率
                — risk_level: 风险等级
            data_quality: dict，数据质量——
                — warnings: list[str]，告警信息
            message: 当 status 为 "error" 时的错误描述
    """
    try:
        # 获取多期财务数据（计算净利变化需要相同口径）
        fin_data_list = get_stock_financial_periods(symbol, limit=4)
        if not fin_data_list:
            return json.dumps(
                {"status": "error", "message": f"未获取到 {symbol} 的财务数据", "symbol": symbol},
                ensure_ascii=False, indent=2, default=str,
            )

        fin_t = fin_data_list[0]
        # 🔑 找相同口径的上期数据（避免季报 vs 年报的错误比较）
        cur_period_type = _detect_period_type(fin_t)
        fin_t1, prev_period_type, period_mismatch = _find_same_period_prev(fin_data_list, cur_period_type)

        # 提取当期数据
        total_assets = _safe_float(fin_t.get("total_assets"))
        total_liab = _safe_float(fin_t.get("total_liab"))
        total_cur_assets = _safe_float(fin_t.get("total_cur_assets"))
        total_cur_liab = _safe_float(fin_t.get("total_cur_liab"))
        net_profit_t = _safe_float(fin_t.get("net_profit"))

        # 提取上期净利润
        net_profit_t1 = _safe_float(fin_t1.get("net_profit")) if fin_t1 else None

        warnings: list[str] = []
        components: dict[str, Optional[float]] = {}

        if period_mismatch:
            warnings.append(f"口径不一致：当期{_PERIOD_LABELS.get(cur_period_type, cur_period_type)} vs 上期{_PERIOD_LABELS.get(prev_period_type, prev_period_type)}，净利润变化率(X6)已跳过")

        # X1 = log(总资产)
        x1 = math.log(total_assets) if total_assets is not None and total_assets > 0 else None
        components["x1_log_assets"] = x1
        if x1 is None:
            warnings.append("总资产数据缺失或非正，X1分量无效")

        # X2 = 总负债 / 总资产
        x2 = _safe_div(total_liab, total_assets)
        components["x2_debt_ratio"] = x2
        if x2 is None:
            warnings.append("负债或资产数据缺失，X2分量无效")

        # X3 = 营运资金 / 总资产
        working_capital = (
            total_cur_assets - total_cur_liab
            if total_cur_assets is not None and total_cur_liab is not None
            else None
        )
        x3 = _safe_div(working_capital, total_assets)
        components["x3_wc_to_assets"] = x3
        if x3 is None:
            warnings.append("营运资金数据缺失，X3分量无效")

        # X4 = 流动负债 / 流动资产
        x4 = _safe_div(total_cur_liab, total_cur_assets)
        components["x4_cl_to_ca"] = x4
        if x4 is None:
            warnings.append("流动负债或流动资产数据缺失，X4分量无效")

        # X5 = 虚拟变量：总负债 > 总资产 则为1（资不抵债）
        x5 = 1.0 if (total_liab is not None and total_assets is not None and total_liab > total_assets) else 0.0
        components["x5_liab_exceeds_assets"] = x5

        # X6 = 净利润变化率： (NI_t - NI_{t-1}) / (|NI_t| + |NI_{t-1}|)
        # 🔑 口径不一致时跳过（季报 vs 年报的净利比较无意义）
        x6 = None
        if not period_mismatch and net_profit_t is not None and net_profit_t1 is not None:
            denom = abs(net_profit_t) + abs(net_profit_t1)
            if denom != 0:
                x6 = (net_profit_t - net_profit_t1) / denom
        components["x6_ni_change"] = x6
        if x6 is None and not period_mismatch:
            warnings.append("净利润历史数据不足，X6分量无效")

        # 计算 O-Score
        valid_components = {k: v for k, v in components.items() if v is not None}
        if len(valid_components) < 4:
            return json.dumps(
                {
                    "status": "error",
                    "message": f"有效数据不足，仅 {len(valid_components)}/6 个分量可用",
                    "symbol": symbol,
                },
                ensure_ascii=False, indent=2, default=str,
            )

        o_score = round(
            -1.32
            - 0.407 * (x1 or 0.0)
            + 6.03 * (x2 or 0.0)
            - 1.43 * (x3 or 0.0)
            + 0.0757 * (x4 or 0.0)
            - 1.72 * x5
            - 0.521 * (x6 or 0.0),
            4,
        )

        # 概率转换
        probability = round(math.exp(o_score) / (1 + math.exp(o_score)), 4)

        # 风险等级
        if probability > 0.5:
            risk_level = "high"
        elif probability > 0.15:
            risk_level = "medium"
        else:
            risk_level = "low"

        if len(valid_components) < 6:
            missing = [k for k, v in components.items() if v is None]
            warnings.append(f"部分分量缺失: {missing}，O-Score仅供参考")

        payload = {
            "symbol": symbol,
            "o_score": o_score,
            "probability": probability,
            "risk_level": risk_level,
            "components": components,
            "interpretation": {
                "o_score": o_score,
                "probability": probability,
                "risk_level": risk_level,
            },
            "data_quality": {"warnings": warnings},
        }

        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("Ohlson O-Score计算失败: %s", exc, exc_info=True)
        return json.dumps(
            {"status": "error", "message": str(exc)},
            ensure_ascii=False, indent=2, default=str,
        )


# ============================================================================
# Tool 2:  应收账款质量
# ============================================================================

@tool
@register_tool(
    tool_id="get_receivables_quality",
    name="应收账款质量评分",
    description=(
        "评估 A 股公司应收账款质量，通过 DSO、应收/营收比、应收/总资产比及同比变化综合评分 0-100 分。"
        "这里的“质量/风险”专指应收账款回款质量、客户信用风险和资产质量异常，不是现金流质量、盈利质量、数据质量或技术信号质量。"
    ),
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["receivables_quality", "asset_quality"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["accounts_receivable_quality_assessment"],
    when_to_use="当需要评估公司回款能力、应收账款异常、账龄/周转风险、客户信用风险或资产质量中的应收部分时使用。",
    when_not_to_use="不适用于无应收账款或现金交易占比极高的行业（如零售超市）；不用于现金流恶化、盈利质量、存货质量、数据质量或技术交易信号分析。",
    returns="返回JSON字符串，包含metrics、score、flags和data_quality。",
    example="get_receivables_quality(symbol='600519')",
    related_tools=["get_inventory_quality", "get_liquidity_stress_test"],
)
def get_receivables_quality(symbol: Annotated[str, "A 股股票代码，如 600519、000001"]) -> str:
    """评估应收账款质量。通过 DSO、应收/营收比、应收/总资产比及同比变化综合评分 0-100 分。

    Args:
        symbol: A 股股票代码，如 600519、000001

    Returns:
        str: JSON 字符串，字段说明——
            status: "success" | "error"
            symbol: 标的股票代码
            period_type: 当期报告期类型，"annual" | "interim" | "q1" | "q3" | "unknown"
            period_caliber: dict，报告期口径信息——
                — current: 当期类型
                — previous: 上期类型
                — period_mismatch: 是否存在口径不一致
                — annualized: 是否进行了年化处理
            metrics: dict，应收账款指标——
                — dso_days: 应收账款周转天数
                — dso_previous_days: 上期 DSO
                — dso_change_pct: DSO 同比变化百分比
                — receivables_to_revenue_pct: 应收/营收比（百分比）
                — receivables_to_assets_pct: 应收/总资产比（百分比）
                — receivables_growth_pct: 应收同比增长百分比
                — revenue_growth_pct: 营收同比增长百分比
            score: 应收账款质量评分（0-100，越高越好；口径不一致时同比相关指标为 None）
            flags: list[str]，触发的不良信号描述
            data_quality: dict，数据质量——
                — warnings: list[str]，告警信息
            message: 当 status 为 "error" 时的错误描述
    """
    try:
        fin_data_list = get_stock_financial_periods(symbol, limit=4)
        if not fin_data_list:
            return json.dumps(
                {"status": "error", "message": f"未获取到 {symbol} 的财务数据", "symbol": symbol},
                ensure_ascii=False, indent=2, default=str,
            )

        fin_cur = fin_data_list[0]

        # 🔑 检测报告期口径，避免季报 vs 年报的错误比较
        cur_period_type = _detect_period_type(fin_cur)
        cur_factor = _annualize_factor(cur_period_type)
        fin_prev, prev_period_type, period_mismatch = _find_same_period_prev(fin_data_list, cur_period_type)

        warnings: list[str] = []
        flags: list[str] = []

        if cur_period_type != "annual" and cur_period_type != "unknown":
            warnings.append(f"当期为{_PERIOD_LABELS.get(cur_period_type, cur_period_type)}数据，营收已年化处理以消除口径差异")

        if period_mismatch:
            warnings.append(f"口径不一致：当期{_PERIOD_LABELS.get(cur_period_type, cur_period_type)} vs 上期{_PERIOD_LABELS.get(prev_period_type, prev_period_type)}，同比指标已标注口径失真")

        # 提取当前期数据
        accounts_receiv = _safe_float(fin_cur.get("accounts_receiv"))
        revenue = _safe_float(fin_cur.get("revenue"))
        total_assets = _safe_float(fin_cur.get("total_assets"))

        # 🔑 年化营收（用于 DSO 和应收/营收比）
        revenue_annualized = revenue * cur_factor if revenue is not None else None

        # 提取上期数据
        ar_prev = _safe_float(fin_prev.get("accounts_receiv")) if fin_prev else None
        rev_prev = _safe_float(fin_prev.get("revenue")) if fin_prev else None
        prev_factor = _annualize_factor(prev_period_type)
        rev_prev_annualized = rev_prev * prev_factor if rev_prev is not None else None

        # DSO (Days Sales Outstanding) — 使用年化营收
        dso = _safe_div(accounts_receiv, _safe_div(revenue_annualized, 365)) if accounts_receiv is not None and revenue_annualized is not None else None
        dso_prev = _safe_div(ar_prev, _safe_div(rev_prev_annualized, 365)) if ar_prev is not None and rev_prev_annualized is not None else None

        # 应收/营收比 — 使用年化营收
        receivables_to_revenue = _safe_div(accounts_receiv, revenue_annualized)

        # 应收/总资产比（不受营收口径影响）
        receivables_to_assets = _safe_div(accounts_receiv, total_assets)

        # 同比变化（仅在口径一致时才有意义）
        if period_mismatch:
            # 口径不一致，不计算同比
            dso_change = None
            ar_growth = None
            rev_growth = None
            warnings.append("因报告期口径不一致，DSO同比、应收增长、营收增长等同比指标已跳过")
        else:
            ar_growth = _pct_change(accounts_receiv, ar_prev)
            rev_growth = _pct_change(revenue, rev_prev)  # 用原始值比较（同期口径相同）
            dso_change = _pct_change(dso, dso_prev) if dso is not None and dso_prev is not None else None

        # 评分 (0-100)
        score = 50.0  # 基础分

        if dso is not None:
            if dso > 180:
                score -= 20
                flags.append(f"DSO高达{dso:.1f}天，回款周期极长")
            elif dso > 90:
                score -= 10
                flags.append(f"DSO={dso:.1f}天，回款偏慢")
            elif dso > 60:
                score -= 5
            elif dso < 30:
                score += 10
                flags.append(f"DSO仅{dso:.1f}天，回款能力优秀")
        else:
            warnings.append("无法计算DSO")
            score -= 10

        if dso_change is not None:
            if dso_change > 0.20:
                score -= 20
                flags.append(f"DSO同比上升{dso_change*100:.1f}%（>{'20%'}），回款严重恶化")
            elif dso_change > 0.10:
                score -= 10
                flags.append(f"DSO同比上升{dso_change*100:.1f}%，回款趋紧")
            elif dso_change < -0.10:
                score += 5
                flags.append(f"DSO同比下降{abs(dso_change)*100:.1f}%，回款改善")
        else:
            warnings.append("无法计算DSO同比变化")

        if receivables_to_revenue is not None:
            if receivables_to_revenue > 0.5:
                score -= 15
                flags.append(f"应收/营收比高达{receivables_to_revenue*100:.1f}%，营收质量风险高")
            elif receivables_to_revenue > 0.3:
                score -= 8
                flags.append(f"应收/营收比为{receivables_to_revenue*100:.1f}%，偏高")
            elif receivables_to_revenue < 0.1:
                score += 10
                flags.append(f"应收/营收比仅{receivables_to_revenue*100:.1f}%，营收质量优秀")
        else:
            warnings.append("无法计算应收/营收比")

        if ar_growth is not None and rev_growth is not None:
            gap = ar_growth - rev_growth
            if gap > 0.20:
                score -= 15
                flags.append(f"应收增长({ar_growth*100:.1f}%)远超营收增长({rev_growth*100:.1f}%)，信用政策过度宽松")
            elif gap > 0.10:
                score -= 5
                flags.append(f"应收增长快于营收，需关注")
        elif ar_growth is not None:
            flags.append(f"应收账款同比变动{ar_growth*100:.1f}%（无营收对比）")

        if receivables_to_assets is not None:
            if receivables_to_assets > 0.3:
                score -= 10
                flags.append(f"应收/总资产比{receivables_to_assets*100:.1f}%，资产占压严重")
            elif receivables_to_assets > 0.15:
                score -= 3

        score = max(0.0, min(100.0, score))

        metrics = {
            "dso_days": round(dso, 1) if dso is not None else None,
            "dso_previous_days": round(dso_prev, 1) if dso_prev is not None else None,
            "dso_change_pct": round(dso_change * 100, 1) if dso_change is not None else None,
            "receivables_to_revenue_pct": round(receivables_to_revenue * 100, 1) if receivables_to_revenue is not None else None,
            "receivables_to_assets_pct": round(receivables_to_assets * 100, 1) if receivables_to_assets is not None else None,
            "receivables_growth_pct": round(ar_growth * 100, 1) if ar_growth is not None else None,
            "revenue_growth_pct": round(rev_growth * 100, 1) if rev_growth is not None else None,
        }

        payload = {
            "symbol": symbol,
            "period_type": cur_period_type,
            "period_caliber": {
                "current": cur_period_type,
                "previous": prev_period_type,
                "period_mismatch": period_mismatch,
                "annualized": cur_period_type != "annual" and cur_period_type != "unknown",
            },
            "metrics": metrics,
            "score": round(score, 1),
            "flags": flags,
            "data_quality": {"warnings": warnings},
        }

        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("应收账款质量评估失败: %s", exc, exc_info=True)
        return json.dumps(
            {"status": "error", "message": str(exc)},
            ensure_ascii=False, indent=2, default=str,
        )


# ============================================================================
# Tool 3:  存货质量
# ============================================================================

@tool
@register_tool(
    tool_id="get_inventory_quality",
    name="存货质量评分",
    description="评估A股公司存货质量，通过存货周转率、DIO、存货/营收比及同比变化综合评分0-100分。",
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["inventory_quality", "asset_quality"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["inventory_quality_assessment"],
    when_to_use="当需要评估公司库存管理效率、存货积压风险或营运资金效率时使用。",
    when_not_to_use="不适用于无存货的服务型企业或金融公司。",
    returns="返回JSON字符串，包含metrics、score、flags和data_quality。",
    example="get_inventory_quality(symbol='600519')",
    related_tools=["get_receivables_quality", "get_liquidity_stress_test"],
)
def get_inventory_quality(symbol: Annotated[str, "A 股股票代码，如 600519、000001"]) -> str:
    """评估存货质量。通过存货周转率、DIO、存货/营收比及同比变化综合评分 0-100 分。

    Args:
        symbol: A 股股票代码，如 600519、000001

    Returns:
        str: JSON 字符串，字段说明——
            status: "success" | "error"
            symbol: 标的股票代码
            period_type: 当期报告期类型，"annual" | "interim" | "q1" | "q3" | "unknown"
            period_caliber: dict，报告期口径信息——
                — current: 当期类型
                — previous: 上期类型
                — period_mismatch: 是否存在口径不一致
                — annualized: 是否进行了年化处理
            metrics: dict，存货指标——
                — inventory_turnover: 存货周转率（次/年）
                — dio_days: 存货周转天数
                — inventory_to_revenue_pct: 存货/营收比（百分比）
                — inventory_to_assets_pct: 存货/总资产比（百分比）
                — inventory_to_current_assets_pct: 存货/流动资产比（百分比）
                — inventory_growth_pct: 存货同比增长百分比
                — revenue_growth_pct: 营收同比增长百分比
            score: 存货质量评分（0-100，越高越好）
            flags: list[str]，触发的不良信号描述
            data_quality: dict，数据质量——
                — warnings: list[str]，告警信息
            message: 当 status 为 "error" 时的错误描述
    """
    try:
        fin_data_list = get_stock_financial_periods(symbol, limit=4)
        if not fin_data_list:
            return json.dumps(
                {"status": "error", "message": f"未获取到 {symbol} 的财务数据", "symbol": symbol},
                ensure_ascii=False, indent=2, default=str,
            )

        fin_cur = fin_data_list[0]

        # 🔑 检测报告期口径
        cur_period_type = _detect_period_type(fin_cur)
        cur_factor = _annualize_factor(cur_period_type)
        fin_prev, prev_period_type, period_mismatch = _find_same_period_prev(fin_data_list, cur_period_type)

        warnings: list[str] = []
        flags: list[str] = []

        if cur_period_type != "annual" and cur_period_type != "unknown":
            warnings.append(f"当期为{_PERIOD_LABELS.get(cur_period_type, cur_period_type)}数据，营收和成本已年化处理")
        if period_mismatch:
            warnings.append(f"口径不一致：当期{_PERIOD_LABELS.get(cur_period_type, cur_period_type)} vs 上期{_PERIOD_LABELS.get(prev_period_type, prev_period_type)}，同比指标已跳过")

        # 提取数据
        inventories = _safe_float(fin_cur.get("inventories"))
        revenue = _safe_float(fin_cur.get("revenue"))
        total_assets = _safe_float(fin_cur.get("total_assets"))
        total_cur_assets = _safe_float(fin_cur.get("total_cur_assets"))

        # 🔑 年化营收
        revenue_annualized = revenue * cur_factor if revenue is not None else None

        # 营业成本（使用营收 - 毛利近似）
        gross_margin = _safe_float(fin_cur.get("gross_margin"))
        cogs = revenue_annualized * (1 - gross_margin / 100) if revenue_annualized is not None and gross_margin is not None and gross_margin > 1 else None

        # 上期数据
        inv_prev = _safe_float(fin_prev.get("inventories")) if fin_prev else None
        rev_prev = _safe_float(fin_prev.get("revenue")) if fin_prev else None
        gm_prev = _safe_float(fin_prev.get("gross_margin")) if fin_prev else None
        prev_factor = _annualize_factor(prev_period_type)
        rev_prev_annualized = rev_prev * prev_factor if rev_prev is not None else None
        cogs_prev = rev_prev_annualized * (1 - gm_prev / 100) if rev_prev_annualized is not None and gm_prev is not None and gm_prev > 1 else None

        # 存货周转率（使用年化成本）
        inventory_turnover = _safe_div(cogs, inventories) if cogs is not None and inventories is not None else None

        # DIO (Days Inventory Outstanding)
        dio = _safe_div(365, inventory_turnover) if inventory_turnover is not None and inventory_turnover > 0 else None

        # 存货/营收比 — 使用年化营收
        inventory_to_revenue = _safe_div(inventories, revenue_annualized)

        # 存货/总资产比（不受营收口径影响）
        inventory_to_assets = _safe_div(inventories, total_assets)

        # 存货/流动资产比
        inventory_to_ca = _safe_div(inventories, total_cur_assets)

        # 同比变化（仅在口径一致时计算）
        if period_mismatch:
            inv_growth = None
            rev_growth = None
        else:
            inv_growth = _pct_change(inventories, inv_prev)
            rev_growth = _pct_change(revenue, rev_prev)

        # 评分 (0-100)
        score = 50.0

        if inventory_turnover is not None:
            if inventory_turnover < 1:
                score -= 20
                flags.append(f"存货周转率仅{inventory_turnover:.2f}次/年，周转极慢")
            elif inventory_turnover < 3:
                score -= 10
                flags.append(f"存货周转率为{inventory_turnover:.2f}次/年，偏慢")
            elif inventory_turnover > 10:
                score += 10
                flags.append(f"存货周转率达{inventory_turnover:.2f}次/年，周转优秀")
            elif inventory_turnover > 5:
                score += 5
        else:
            warnings.append("无法计算存货周转率（营业成本数据不足）")

        if dio is not None:
            if dio > 365:
                flags.append(f"DIO高达{dio:.1f}天，存货积压超过一年")
            elif dio > 180:
                flags.append(f"DIO={dio:.1f}天，存货积压较重")
        else:
            warnings.append("无法计算DIO")

        if inv_growth is not None and rev_growth is not None:
            if inv_growth > rev_growth + 0.20:
                score -= 20
                flags.append(f"存货增长({inv_growth*100:.1f}%)远超营收增长({rev_growth*100:.1f}%)，可能存在滞销")
            elif inv_growth > rev_growth + 0.10:
                score -= 8
                flags.append(f"存货增长快于营收增长")
            elif inv_growth < rev_growth - 0.10:
                score += 5
                flags.append(f"存货增长低于营收增长，管理良好")
        elif inv_growth is not None:
            flags.append(f"存货同比变动{inv_growth*100:.1f}%（无营收对比）")

        if inventory_to_revenue is not None:
            if inventory_to_revenue > 0.5:
                score -= 15
                flags.append(f"存货/营收比高达{inventory_to_revenue*100:.1f}%, 占压严重")
            elif inventory_to_revenue > 0.25:
                score -= 5
            elif inventory_to_revenue < 0.1:
                score += 10
                flags.append(f"存货/营收比仅{inventory_to_revenue*100:.1f}%，存货管理优秀")
        else:
            warnings.append("无法计算存货/营收比")

        if inventory_to_assets is not None and inventory_to_assets > 0.3:
            score -= 5
            flags.append(f"存货占总资产{inventory_to_assets*100:.1f}%，占比偏高")

        if inventory_to_ca is not None and inventory_to_ca > 0.5:
            score -= 5
            flags.append(f"存货占流动资产{inventory_to_ca*100:.1f}%，流动性风险")

        score = max(0.0, min(100.0, score))

        metrics = {
            "inventory_turnover": round(inventory_turnover, 2) if inventory_turnover is not None else None,
            "dio_days": round(dio, 1) if dio is not None else None,
            "inventory_to_revenue_pct": round(inventory_to_revenue * 100, 1) if inventory_to_revenue is not None else None,
            "inventory_to_assets_pct": round(inventory_to_assets * 100, 1) if inventory_to_assets is not None else None,
            "inventory_to_current_assets_pct": round(inventory_to_ca * 100, 1) if inventory_to_ca is not None else None,
            "inventory_growth_pct": round(inv_growth * 100, 1) if inv_growth is not None else None,
            "revenue_growth_pct": round(rev_growth * 100, 1) if rev_growth is not None else None,
        }

        payload = {
            "symbol": symbol,
            "period_type": cur_period_type,
            "period_caliber": _period_caliber_payload(cur_period_type, prev_period_type, period_mismatch),
            "metrics": metrics,
            "score": round(score, 1),
            "flags": flags,
            "data_quality": {"warnings": warnings},
        }

        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("存货质量评估失败: %s", exc, exc_info=True)
        return json.dumps(
            {"status": "error", "message": str(exc)},
            ensure_ascii=False, indent=2, default=str,
        )


# ============================================================================
# Tool 4:  流动性压力测试
# ============================================================================

@tool
@register_tool(
    tool_id="get_liquidity_stress_test",
    name="流动性压力测试",
    description="对A股公司进行流动性压力测试，通过当前比率、速动比率、现金覆盖天数等指标，模拟不同营收下滑情景下的流动性风险。",
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["liquidity_risk", "stress_testing"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["liquidity_stress_testing"],
    when_to_use="当需要评估公司在营收下滑、市场紧缩等不利情景下的流动性风险时使用。",
    when_not_to_use="不适用于金融行业公司（资产负债结构不同）；压力测试为模拟分析，不构成实际预测。",
    returns="返回JSON字符串，包含liquidity_metrics、stress_scenarios和data_quality。",
    example="get_liquidity_stress_test(symbol='600519', revenue_decline_pcts='0.1,0.2,0.3')",
    related_tools=["get_debt_structure_analysis", "get_receivables_quality"],
)
def get_liquidity_stress_test(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"],
    revenue_decline_pcts: Annotated[str, "营收下滑百分比（逗号分隔），如'0.1,0.2,0.3' 表示10%/20%/30%"] = "0.1,0.2,0.3",
) -> str:
    """执行流动性压力测试。模拟不同营收下滑情景下的流动性风险。

    Args:
        symbol: A 股股票代码，如 600519、000001
        revenue_decline_pcts: 营收下滑百分比（逗号分隔），默认 "0.1,0.2,0.3"；
            每个值会被夹取到 [0, 1]；解析失败时回退为默认值

    Returns:
        str: JSON 字符串，字段说明——
            status: "success" | "error"
            symbol: 标的股票代码
            period_type: 当期报告期类型，"annual" | "interim" | "q1" | "q3" | "unknown"
            period_caliber: dict，报告期口径信息——
                — current: 当期类型
                — previous: 上期类型（恒为 "unknown"）
                — period_mismatch: 是否存在口径不一致（恒为 False）
                — annualized: 是否进行了年化处理
            liquidity_metrics: dict，基础流动性指标——
                — current_ratio: 流动比率
                — quick_ratio: 速动比率
                — cash_coverage_days: 现金覆盖天数
            stress_scenarios: list[dict]，压力情景结果，元素结构——
                — revenue_decline_pct: 营收下滑比例
                — stressed_revenue: 受压营收
                — stressed_oper_profit: 受压营业利润
                — stressed_net_profit: 受压净利润
                — stressed_current_ratio: 受压流动比率
                — stressed_cash_coverage_days: 受压现金覆盖天数
            data_quality: dict，数据质量——
                — warnings: list[str]，告警信息
            message: 当 status 为 "error" 时的错误描述
    """
    try:
        fin_data_list = get_stock_financial_periods(symbol, limit=1)
        if not fin_data_list:
            return json.dumps(
                {"status": "error", "message": f"未获取到 {symbol} 的财务数据", "symbol": symbol},
                ensure_ascii=False, indent=2, default=str,
            )

        fin = fin_data_list[0]
        warnings: list[str] = []

        # 🔑 检测报告期口径
        cur_period_type = _detect_period_type(fin)
        cur_factor = _annualize_factor(cur_period_type)
        if cur_period_type != "annual" and cur_period_type != "unknown":
            warnings.append(f"当期为{_PERIOD_LABELS.get(cur_period_type, cur_period_type)}数据，营收已年化处理")

        # 提取数据
        total_cur_assets = _safe_float(fin.get("total_cur_assets"))
        total_cur_liab = _safe_float(fin.get("total_cur_liab"))
        total_assets = _safe_float(fin.get("total_assets"))
        total_liab = _safe_float(fin.get("total_liab"))
        inventories = _safe_float(fin.get("inventories"))
        money_cap = _safe_float(fin.get("money_cap"))
        revenue = _safe_float(fin.get("revenue"))
        net_profit = _safe_float(fin.get("net_profit"))
        oper_profit = _safe_float(fin.get("oper_profit"))

        # 🔑 年化营收
        revenue_annualized = revenue * cur_factor if revenue is not None else None

        # 流动性指标
        current_ratio = _safe_div(total_cur_assets, total_cur_liab)

        # 速动比率 = (流动资产 - 存货) / 流动负债
        quick_assets = (
            total_cur_assets - inventories
            if total_cur_assets is not None and inventories is not None
            else None
        )
        quick_ratio = _safe_div(quick_assets, total_cur_liab)

        # 现金覆盖天数 — 使用年化营收
        daily_opex = _safe_div(revenue_annualized * 0.7, 365) if revenue_annualized is not None else None  # 假设营业费用约占营收70%
        cash_coverage_days = _safe_div(money_cap, daily_opex) if money_cap is not None and daily_opex is not None and daily_opex > 0 else None

        if daily_opex is None:
            warnings.append("无法计算日均营业支出，现金覆盖天数可能不准确")

        liquidity_metrics = {
            "current_ratio": round(current_ratio, 2) if current_ratio is not None else None,
            "quick_ratio": round(quick_ratio, 2) if quick_ratio is not None else None,
            "cash_coverage_days": round(cash_coverage_days, 1) if cash_coverage_days is not None else None,
        }

        # 解析营收下滑百分比
        try:
            declines = [float(x.strip()) for x in revenue_decline_pcts.split(",") if x.strip()]
            declines = [max(0.0, min(1.0, d)) for d in declines]
        except (ValueError, AttributeError):
            declines = [0.1, 0.2, 0.3]
            warnings.append(f"营收下滑参数解析失败，使用默认值: {revenue_decline_pcts}")

        if not declines:
            declines = [0.1, 0.2, 0.3]
            warnings.append("营收下滑参数为空，使用默认值")

        # 压力场景分析
        stress_scenarios = []
        for pct in sorted(declines):
            # 营收下滑后的营收（基于年化营收）
            stressed_revenue = revenue_annualized * (1 - pct) if revenue_annualized is not None else None

            # 假设固定成本占营收50%，变动成本随营收线性变化
            # 模拟成本结构：总成本 = 0.5*原营收(固定) + 0.5*原营收*(1-下滑率) = 原营收*(1 - 0.5*下滑率)
            cost_ratio_after = 1.0 - 0.5 * pct  # 成本占原营收比例
            stressed_oper_profit = stressed_revenue - (revenue_annualized * cost_ratio_after) if stressed_revenue is not None and revenue_annualized is not None else None

            # 模拟净利（假设税率25%）
            stressed_net_profit = stressed_oper_profit * 0.75 if stressed_oper_profit is not None else None

            # 模拟后的流动比率（假设流动资产随营收下降，流动负债不变）
            # 假设流动资产中50%随营收变动
            if total_cur_assets is not None:
                stressed_ca = total_cur_assets * (1 - 0.5 * pct)
            else:
                stressed_ca = None
            stressed_cr = _safe_div(stressed_ca, total_cur_liab)

            # 模拟后的现金覆盖天数 — 使用年化营收
            stressed_daily_opex = _safe_div(stressed_revenue * 0.7, 365) if stressed_revenue is not None else None
            stressed_cash_coverage = _safe_div(money_cap, stressed_daily_opex) if money_cap is not None and stressed_daily_opex is not None and stressed_daily_opex > 0 else None

            scenario = {
                "revenue_decline_pct": pct,
                "stressed_revenue": round(stressed_revenue, 2) if stressed_revenue is not None else None,
                "stressed_oper_profit": round(stressed_oper_profit, 2) if stressed_oper_profit is not None else None,
                "stressed_net_profit": round(stressed_net_profit, 2) if stressed_net_profit is not None else None,
                "stressed_current_ratio": round(stressed_cr, 2) if stressed_cr is not None else None,
                "stressed_cash_coverage_days": round(stressed_cash_coverage, 1) if stressed_cash_coverage is not None else None,
            }
            stress_scenarios.append(scenario)

        payload = {
            "symbol": symbol,
            "period_type": cur_period_type,
            "period_caliber": _period_caliber_payload(cur_period_type, "unknown", False),
            "liquidity_metrics": liquidity_metrics,
            "stress_scenarios": stress_scenarios,
            "data_quality": {"warnings": warnings},
        }

        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("流动性压力测试失败: %s", exc, exc_info=True)
        return json.dumps(
            {"status": "error", "message": str(exc)},
            ensure_ascii=False, indent=2, default=str,
        )


# ============================================================================
# Tool 5:  债务结构分析
# ============================================================================

@tool
@register_tool(
    tool_id="get_debt_structure_analysis",
    name="债务结构分析",
    description="分析A股公司债务结构，通过负债/权益比、负债/资产比、利息覆盖倍数、短期债务占比等指标综合评分0-100分。",
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["debt_structure", "solvency_risk"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["debt_structure_analysis"],
    when_to_use="当需要评估公司偿债能力、债务风险或资本结构合理性时使用。",
    when_not_to_use="不适用于金融行业公司（高杠杆为行业特性）；不适用于资不抵债的公司（负债率>100%）。",
    returns="返回JSON字符串，包含ratios、score、interpretation和data_quality。",
    example="get_debt_structure_analysis(symbol='600519')",
    related_tools=["get_liquidity_stress_test", "get_ohlson_oscore"],
)
def get_debt_structure_analysis(symbol: Annotated[str, "A 股股票代码，如 600519、000001"]) -> str:
    """分析债务结构。通过负债/权益比、负债/资产比、利息覆盖倍数、短期债务占比等指标综合评分 0-100 分。

    Args:
        symbol: A 股股票代码，如 600519、000001

    Returns:
        str: JSON 字符串，字段说明——
            status: "success" | "error"
            symbol: 标的股票代码
            period_type: 当期报告期类型，"annual" | "interim" | "q1" | "q3" | "unknown"
            period_caliber: dict，报告期口径信息——
                — current: 当期类型
                — previous: 上期类型
                — period_mismatch: 是否存在口径不一致
                — annualized: 是否进行了年化处理
            ratios: dict，债务结构指标——
                — debt_to_equity: 负债/权益比
                — debt_to_equity_previous: 上期负债/权益比
                — debt_to_equity_change_pct: 负债/权益比同比变化百分比
                — debt_to_assets_pct: 负债/总资产比（百分比）
                — interest_coverage: 利息覆盖倍数（无穷大时为字符串 "inf"）
                — short_term_debt_ratio_pct: 短期债务占比（百分比）
            score: 债务结构评分（0-100，越高越好）
            interpretation: 债务结构解读文案
            data_quality: dict，数据质量——
                — warnings: list[str]，告警信息
            message: 当 status 为 "error" 时的错误描述
    """
    try:
        fin_data_list = get_stock_financial_periods(symbol, limit=4)
        if not fin_data_list:
            return json.dumps(
                {"status": "error", "message": f"未获取到 {symbol} 的财务数据", "symbol": symbol},
                ensure_ascii=False, indent=2, default=str,
            )

        fin_cur = fin_data_list[0]

        # 🔑 检测报告期口径
        cur_period_type = _detect_period_type(fin_cur)
        fin_prev, prev_period_type, period_mismatch = _find_same_period_prev(fin_data_list, cur_period_type)

        warnings: list[str] = []
        if period_mismatch:
            warnings.append(f"口径不一致：当期{_PERIOD_LABELS.get(cur_period_type, cur_period_type)} vs 上期{_PERIOD_LABELS.get(prev_period_type, prev_period_type)}，D/E 同比已跳过")

        # 提取当期数据
        total_liab = _safe_float(fin_cur.get("total_liab"))
        total_equity = _safe_float(fin_cur.get("total_equity"))
        total_assets = _safe_float(fin_cur.get("total_assets"))
        total_cur_liab = _safe_float(fin_cur.get("total_cur_liab"))
        oper_profit = _safe_float(fin_cur.get("oper_profit"))
        fin_exp = _safe_float(fin_cur.get("fin_exp"))

        # 提取上期数据用于趋势
        tl_prev = _safe_float(fin_prev.get("total_liab")) if fin_prev else None
        te_prev = _safe_float(fin_prev.get("total_equity")) if fin_prev else None

        # 负债/权益比
        debt_to_equity = _safe_div(total_liab, total_equity)

        # 负债/资产比
        debt_to_assets = _safe_div(total_liab, total_assets)

        # 利息覆盖倍数 = 营业利润 / 财务费用
        interest_coverage = _safe_div(oper_profit, fin_exp) if fin_exp is not None and fin_exp != 0 else None
        if fin_exp is not None and fin_exp == 0:
            interest_coverage = float("inf")
            warnings.append("财务费用为0，利息覆盖倍数视为无穷大")

        # 短期债务占比（使用流动负债/总负债作为近似）
        short_term_debt_ratio = _safe_div(total_cur_liab, total_liab)

        # 趋势 — 口径不一致时跳过同比
        if period_mismatch:
            de_change = None
            debt_to_equity_prev = None
        else:
            debt_to_equity_prev = _safe_div(tl_prev, te_prev) if tl_prev is not None and te_prev is not None else None
            de_change = _pct_change(debt_to_equity, debt_to_equity_prev) if debt_to_equity is not None and debt_to_equity_prev is not None else None

        # 评分 (0-100)
        score = 50.0

        if debt_to_equity is not None:
            if debt_to_equity > 2.0:
                score -= 20
                warnings.append(f"负债/权益比高达{debt_to_equity:.2f}，杠杆风险极高")
            elif debt_to_equity > 1.0:
                score -= 10
                warnings.append(f"负债/权益比为{debt_to_equity:.2f}，偏高")
            elif debt_to_equity < 0.3:
                score += 10
                warnings.append(f"负债/权益比仅{debt_to_equity:.2f}，杠杆保守")
            else:
                score += 5
        else:
            warnings.append("无法计算负债/权益比")

        if debt_to_assets is not None:
            if debt_to_assets > 0.7:
                score -= 15
            elif debt_to_assets > 0.5:
                score -= 5
            elif debt_to_assets < 0.3:
                score += 10
        else:
            warnings.append("无法计算负债/资产比")

        if interest_coverage is not None and interest_coverage != float("inf"):
            if interest_coverage < 1.0:
                score -= 25
                warnings.append(f"利息覆盖倍数仅{interest_coverage:.2f}，利润不足以覆盖利息支出")
            elif interest_coverage < 2.0:
                score -= 15
                warnings.append(f"利息覆盖倍数={interest_coverage:.2f}，偿债能力偏弱")
            elif interest_coverage > 5.0:
                score += 10
                warnings.append(f"利息覆盖倍数达{interest_coverage:.2f}，偿债能力优秀")
            elif interest_coverage > 3.0:
                score += 5
        elif interest_coverage is None:
            warnings.append("无法计算利息覆盖倍数")

        if short_term_debt_ratio is not None:
            if short_term_debt_ratio > 0.8:
                score -= 15
                warnings.append(f"短期债务占比{short_term_debt_ratio*100:.1f}%，流动性压力大")
            elif short_term_debt_ratio > 0.6:
                score -= 5
                warnings.append(f"短期债务占比{short_term_debt_ratio*100:.1f}%，偏高")
            elif short_term_debt_ratio < 0.3:
                score += 10
            else:
                score += 5
        else:
            warnings.append("无法计算短期债务占比")

        if de_change is not None:
            if de_change > 0.20:
                score -= 10
                warnings.append(f"负债/权益比同比上升{de_change*100:.1f}%，杠杆加速")
            elif de_change < -0.10:
                score += 5
                warnings.append(f"负债/权益比同比下降{abs(de_change)*100:.1f}%，杠杆改善")

        score = max(0.0, min(100.0, score))

        # 解读
        if score >= 80:
            interpretation = "债务结构非常健康，偿债能力强"
        elif score >= 60:
            interpretation = "债务结构合理，风险可控"
        elif score >= 40:
            interpretation = "债务结构需关注，存在一定偿债风险"
        elif score >= 20:
            interpretation = "债务结构不佳，偿债压力较大"
        else:
            interpretation = "债务结构危险，可能面临偿债危机"

        ratios = {
            "debt_to_equity": round(debt_to_equity, 2) if debt_to_equity is not None else None,
            "debt_to_equity_previous": round(debt_to_equity_prev, 2) if debt_to_equity_prev is not None else None,
            "debt_to_equity_change_pct": round(de_change * 100, 1) if de_change is not None else None,
            "debt_to_assets_pct": round(debt_to_assets * 100, 1) if debt_to_assets is not None else None,
            "interest_coverage": round(interest_coverage, 2) if interest_coverage is not None and interest_coverage != float("inf") else ("inf" if interest_coverage == float("inf") else None),
            "short_term_debt_ratio_pct": round(short_term_debt_ratio * 100, 1) if short_term_debt_ratio is not None else None,
        }

        payload = {
            "symbol": symbol,
            "period_type": cur_period_type,
            "period_caliber": _period_caliber_payload(cur_period_type, prev_period_type, period_mismatch),
            "ratios": ratios,
            "score": round(score, 1),
            "interpretation": interpretation,
            "data_quality": {"warnings": warnings},
        }

        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("债务结构分析失败: %s", exc, exc_info=True)
        return json.dumps(
            {"status": "error", "message": str(exc)},
            ensure_ascii=False, indent=2, default=str,
        )


__all__ = [
    "get_ohlson_oscore",
    "get_receivables_quality",
    "get_inventory_quality",
    "get_liquidity_stress_test",
    "get_debt_structure_analysis",
]