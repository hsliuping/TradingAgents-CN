"""盈利质量评分工具"""

import json
import logging
from typing import Annotated

import numpy as np

from langchain_core.tools import tool

from core.skill_runtime.standard_financial_apis import get_historical_financial_annual_series
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


@tool
@register_tool(
    tool_id="get_earnings_quality_score",
    name="盈利质量评分",
    description=(
        "从应计质量、现金流稳定性、盈利持续性、自由现金流覆盖和一次性项目影响五个维度评估公司盈利质量，总分100分。"
        "这里的“质量”指盈利真实性、可持续性和会计质量，不是数据质量、报告质量、产品质量、技术信号质量或单纯现金流量表分析。"
    ),
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["earnings_quality", "accounting_quality"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["earnings_quality_assessment"],
    when_to_use="当需要评估公司盈利真实性、盈利可持续性、会计质量、应计利润风险、现金流对盈利覆盖情况时使用。",
    when_not_to_use="不用于短期盈利预测；不用于数据质量检查、报告质量评审、技术信号或交易资金流分析；盈利质量评分衡量历史质量而非未来盈利。",
    returns="返回JSON字符串，包含total_score、rating、dimensions和data_quality。",
    example="get_earnings_quality_score(symbol='600519')",
    related_tools=["get_beneish_mscore", "get_piotroski_fscore"],
)
def get_earnings_quality_score(symbol: Annotated[str, "A 股股票代码，如 600519、000001"]) -> str:
    """评估公司盈利质量。从应计质量、现金流稳定性、盈利持续性、自由现金流覆盖和一次性项目影响五个维度打分。

    Args:
        symbol: A 股股票代码，如 600519、000001

    Returns:
        str: JSON 字符串，字段说明——
            status: "error" 时存在；成功时不包含该字段
            symbol: 标的股票代码
            total_score: 总分（满分 100）
            rating: 评级，"优质" | "良好" | "一般" | "较差" | "差"
            dimensions: dict，五个维度评分（每维度满分 20）——
                — accrual_quality: dict，应计质量——
                    — score: 得分
                    — max: 满分 20
                    — value: 应计比率均值（数据不足时为 None）
                — cashflow_stability: dict，现金流稳定性——
                    — score: 得分
                    — max: 满分 20
                    — value: 经营现金流变异系数（数据不足时为 None）
                — earnings_persistence: dict，盈利持续性——
                    — score: 得分
                    — max: 满分 20
                    — detail: 正增长年份占比文案
                — fcf_coverage: dict，自由现金流覆盖——
                    — score: 得分
                    — max: 满分 20
                    — value: 自由现金流 / 净利润 均值（数据不足时为 None）
                — recurring_quality: dict，一次性项目影响（净利率稳定性）——
                    — score: 得分
                    — max: 满分 20
                    — value: 净利率标准差（数据不足时为 None）
            data_quality: dict，数据质量——
                — years_available: 可用年报年数
                — warnings: list[str]，告警信息
            message: 当 status 为 "error" 时的错误描述
    """
    try:
        # 获取5年年报数据
        annual_data = get_historical_financial_annual_series(symbol, years=5)
        records = annual_data.get("records") or []
        warnings: list[str] = list(annual_data.get("warnings") or [])

        if len(records) < 2:
            return json.dumps(
                {
                    "status": "error",
                    "message": f"年报数据不足，仅获取到 {len(records)} 年数据，需要至少2年",
                    "symbol": symbol,
                },
                ensure_ascii=False, indent=2, default=str,
            )

        if len(records) < 5:
            warnings.append(f"理想需要5年数据，当前仅{len(records)}年，评分可靠性降低")

        # 将 records 按年份升序（便于计算增长率）
        sorted_records = sorted(records, key=lambda r: r.get("year") or 0)

        n = len(sorted_records)

        # 提取关键字段
        net_profits = [_safe_float(r.get("net_profit")) for r in sorted_records]
        operating_cashflows = [_safe_float(r.get("operating_cashflow")) for r in sorted_records]
        free_cashflows = [_safe_float(r.get("free_cashflow")) for r in sorted_records]
        netprofit_margins = [_safe_float(r.get("netprofit_margin")) for r in sorted_records]

        # ===== D1: 应计质量 (20pts) =====
        # mean(abs(net_profit - operating_cashflow) / abs(net_profit))
        accrual_ratios = []
        for np_val, ocf_val in zip(net_profits, operating_cashflows):
            if np_val is not None and ocf_val is not None and np_val != 0:
                accrual_ratios.append(abs(np_val - ocf_val) / abs(np_val))

        if accrual_ratios:
            mean_accrual_ratio = float(np.mean(accrual_ratios))
            d1_score = max(0.0, min(20.0, 20.0 - mean_accrual_ratio * 20.0))
        else:
            mean_accrual_ratio = None
            d1_score = 10.0
            warnings.append("应计质量无法计算，已赋中间分")

        # ===== D2: 现金流稳定性 (20pts) =====
        valid_ocfs = [v for v in operating_cashflows if v is not None]
        if len(valid_ocfs) >= 2:
            mean_ocf = float(np.mean(valid_ocfs))
            if mean_ocf != 0:
                cv_ocf = float(np.std(valid_ocfs, ddof=1)) / abs(mean_ocf)
            else:
                cv_ocf = float(np.std(valid_ocfs, ddof=1))
            d2_score = max(0.0, min(20.0, 20.0 - cv_ocf * 40.0))
        else:
            cv_ocf = None
            d2_score = 10.0
            warnings.append("现金流稳定性数据不足，已赋中间分")

        # ===== D3: 盈利持续性 (20pts) =====
        positive_growth_years = 0
        total_growth_years = 0
        for i in range(1, n):
            cur_np = net_profits[i]
            prev_np = net_profits[i - 1]
            if cur_np is not None and prev_np is not None:
                total_growth_years += 1
                if cur_np > prev_np:
                    positive_growth_years += 1

        if total_growth_years > 0:
            d3_score = (positive_growth_years / total_growth_years) * 20.0
        else:
            d3_score = 10.0

        # ===== D4: 自由现金流覆盖 (20pts) =====
        fcf_coverage_ratios = []
        for fcf_val, np_val in zip(free_cashflows, net_profits):
            if fcf_val is not None and np_val is not None and np_val > 0:
                fcf_coverage_ratios.append(fcf_val / np_val)

        if fcf_coverage_ratios:
            mean_fcf_coverage = float(np.mean(fcf_coverage_ratios))
            # >0.8 = full marks
            d4_score = max(0.0, min(20.0, (mean_fcf_coverage / 0.8) * 20.0))
        else:
            mean_fcf_coverage = None
            d4_score = 10.0
            warnings.append("自由现金流覆盖数据不足，已赋中间分")

        # ===== D5: 一次性项目影响 (20pts) =====
        valid_margins = [v for v in netprofit_margins if v is not None]
        if len(valid_margins) >= 2:
            # netprofit_margin 已经是百分比（如30表示30%），这里处理小数形式
            # 先判断值域：如果大部分值 > 1 则视为百分比形式
            if float(np.mean(valid_margins)) > 1:
                # 百分比形式，转成小数
                valid_margins_dec = [v / 100.0 for v in valid_margins]
            else:
                valid_margins_dec = valid_margins
            std_margin = float(np.std(valid_margins_dec, ddof=1))
            d5_score = max(0.0, min(20.0, 20.0 - std_margin * 200.0))
        else:
            std_margin = None
            d5_score = 10.0
            warnings.append("净利率数据不足，已赋中间分")

        # ===== 总分与评级 =====
        total_score = round(d1_score + d2_score + d3_score + d4_score + d5_score, 1)

        if total_score >= 80:
            rating = "优质"
        elif total_score >= 60:
            rating = "良好"
        elif total_score >= 40:
            rating = "一般"
        elif total_score >= 20:
            rating = "较差"
        else:
            rating = "差"

        payload = {
            "symbol": symbol,
            "total_score": total_score,
            "rating": rating,
            "dimensions": {
                "accrual_quality": {
                    "score": round(d1_score, 1),
                    "max": 20,
                    "value": round(mean_accrual_ratio, 4) if mean_accrual_ratio is not None else None,
                },
                "cashflow_stability": {
                    "score": round(d2_score, 1),
                    "max": 20,
                    "value": round(cv_ocf, 4) if cv_ocf is not None else None,
                },
                "earnings_persistence": {
                    "score": round(d3_score, 1),
                    "max": 20,
                    "detail": f"{positive_growth_years}/{total_growth_years} years growth",
                },
                "fcf_coverage": {
                    "score": round(d4_score, 1),
                    "max": 20,
                    "value": round(mean_fcf_coverage, 4) if mean_fcf_coverage is not None else None,
                },
                "recurring_quality": {
                    "score": round(d5_score, 1),
                    "max": 20,
                    "value": round(std_margin, 4) if std_margin is not None else None,
                },
            },
            "data_quality": {
                "years_available": n,
                "warnings": warnings,
            },
        }

        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("盈利质量评分计算失败: %s", exc, exc_info=True)
        return json.dumps(
            {"status": "error", "message": str(exc)},
            ensure_ascii=False, indent=2, default=str,
        )


__all__ = ["get_earnings_quality_score"]
