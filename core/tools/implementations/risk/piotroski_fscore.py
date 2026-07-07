"""Piotroski F-Score 基本面质量评分工具"""

import json
import logging
from typing import Annotated

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
    tool_id="get_piotroski_fscore",
    name="Piotroski F-Score 基本面质量评分",
    description="基于Piotroski F-Score模型从盈利能力、杠杆流动性、运营效率三个维度（共9分）评估公司基本面质量。",
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["fundamental_quality", "value_investing"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["fundamental_quality_screening"],
    when_to_use="当需要评估公司基本面强弱、价值投资筛选或识别财务改善/恶化信号时使用。",
    when_not_to_use="不用于短期交易信号；F-Score评估的是基本面质量而非短期动量。",
    returns="返回JSON字符串，包含f_score、rating、categories、comparison和data_quality。",
    example="get_piotroski_fscore(symbol='600519')",
    related_tools=["get_altman_zscore", "get_beneish_mscore"],
)
def get_piotroski_fscore(symbol: Annotated[str, "A 股股票代码，如 600519、000001"]) -> str:
    """计算 Piotroski F-Score 基本面质量评分。从盈利能力、杠杆流动性和运营效率三个维度评估（满分 9 分）。

    Args:
        symbol: A 股股票代码，如 600519、000001

    Returns:
        str: JSON 字符串，字段说明——
            status: "error" 时存在；成功时不包含该字段
            symbol: 标的股票代码
            f_score: F-Score 总分（满分 9）
            rating: 评级，"优质"（≥7） | "中性"（4-6） | "弱势"（≤3）
            categories: dict，三类评分——
                — profitability: dict，盈利能力（满分 4）——
                    — score: 得分
                    — max: 满分 4
                    — details: dict，4 个布尔项——
                        — p1_roa_positive: 当期 ROA > 0
                        — p2_ocf_positive: 当期经营现金流 > 0
                        — p3_delta_roa_positive: ROA 同比上升
                        — p4_ocf_gt_netprofit: 经营现金流 > 净利润
                — leverage_liquidity: dict，杠杆/流动性（满分 3）——
                    — score / max
                    — details: dict，3 个布尔项——
                        — p5_deleveraging: 资产负债率下降
                        — p6_liquidity_improving: 流动比率上升
                        — p7_no_dilution: 无股权稀释
                — operating_efficiency: dict，运营效率（满分 2）——
                    — score / max
                    — details: dict，2 个布尔项——
                        — p8_gross_margin_improving: 毛利率上升
                        — p9_asset_turnover_improving: 资产周转率上升
            comparison: dict，对比年份——
                — current_year: 当期年份
                — prior_year: 上期年份
            data_quality: dict，数据质量——
                — warnings: list[str]，告警信息
            message: 当 status 为 "error" 时的错误描述
    """
    try:
        # 获取最近3年年报数据（需要当前年 + 至少1个前一年）
        annual_data = get_historical_financial_annual_series(symbol, years=3)
        records = annual_data.get("records") or []

        if len(records) < 2:
            return json.dumps(
                {
                    "status": "error",
                    "message": f"年报数据不足，仅获取到 {len(records)} 年数据，需要至少2年",
                    "symbol": symbol,
                },
                ensure_ascii=False, indent=2, default=str,
            )

        # records 按年倒序排列（最新在前）
        current = records[0]
        prior = records[1]

        warnings: list[str] = list(annual_data.get("warnings") or [])

        current_year = current.get("year")
        prior_year = prior.get("year")

        # =========== 盈利能力 (4分) ===========
        profitability_details = {}

        # P1: ROA > 0 (current year)
        roa_cur = _safe_float(current.get("roa"))
        p1_roa_positive = (roa_cur or 0) > 0
        profitability_details["p1_roa_positive"] = p1_roa_positive

        # P2: Operating Cash Flow > 0 (current year)
        ocf_cur = _safe_float(current.get("operating_cashflow"))
        p2_ocf_positive = (ocf_cur or 0) > 0
        profitability_details["p2_ocf_positive"] = p2_ocf_positive

        # P3: ΔROA > 0 (current - prior)
        roa_prior = _safe_float(prior.get("roa"))
        delta_roa = (roa_cur - roa_prior) if roa_cur is not None and roa_prior is not None else None
        p3_delta_roa = (delta_roa or 0) > 0
        profitability_details["p3_delta_roa_positive"] = p3_delta_roa

        # P4: Operating Cash Flow > Net Profit (accrual quality)
        net_profit_cur = _safe_float(current.get("net_profit"))
        p4_ocf_gt_np = (ocf_cur or 0) > (net_profit_cur or 0) if ocf_cur is not None and net_profit_cur is not None else False
        profitability_details["p4_ocf_gt_netprofit"] = p4_ocf_gt_np

        profitability_score = sum(
            [p1_roa_positive, p2_ocf_positive, p3_delta_roa, p4_ocf_gt_np]
        )

        # =========== 杠杆/流动性 (3分) ===========
        leverage_details = {}

        # P5: Δ(debt_to_assets) < 0 (deleveraging)
        debt_cur = _safe_float(current.get("debt_to_assets"))
        debt_prior = _safe_float(prior.get("debt_to_assets"))
        delta_debt = (debt_cur - debt_prior) if debt_cur is not None and debt_prior is not None else None
        p5_delta_debt = (delta_debt or 0) < 0
        leverage_details["p5_deleveraging"] = p5_delta_debt

        # P6: Δ(current_ratio) > 0 (liquidity improving)
        cr_cur = _safe_float(current.get("current_ratio"))
        cr_prior = _safe_float(prior.get("current_ratio"))
        delta_cr = (cr_cur - cr_prior) if cr_cur is not None and cr_prior is not None else None
        p6_delta_cr = (delta_cr or 0) > 0
        leverage_details["p6_liquidity_improving"] = p6_delta_cr

        # P7: No new shares issued → total_equity growth <= revenue growth
        equity_cur = _safe_float(current.get("total_equity"))
        equity_prior = _safe_float(prior.get("total_equity"))
        revenue_cur = _safe_float(current.get("revenue"))
        revenue_prior = _safe_float(prior.get("revenue"))

        equity_growth = _safe_div(equity_cur, equity_prior) if equity_cur is not None and equity_prior is not None else None
        revenue_growth = _safe_div(revenue_cur, revenue_prior) if revenue_cur is not None and revenue_prior is not None else None
        p7_no_dilution = (
            (equity_growth or 0) <= (revenue_growth or 0)
            if equity_growth is not None and revenue_growth is not None
            else False
        )
        leverage_details["p7_no_dilution"] = p7_no_dilution

        leverage_score = sum([p5_delta_debt, p6_delta_cr, p7_no_dilution])

        # =========== 运营效率 (2分) ===========
        efficiency_details = {}

        # P8: Δ(gross_margin) > 0
        gm_cur = _safe_float(current.get("gross_margin"))
        gm_prior = _safe_float(prior.get("gross_margin"))
        delta_gm = (gm_cur - gm_prior) if gm_cur is not None and gm_prior is not None else None
        p8_delta_gm = (delta_gm or 0) > 0
        efficiency_details["p8_gross_margin_improving"] = p8_delta_gm

        # P9: Δ(asset_turnover) > 0 (revenue / total_assets)
        ta_cur = _safe_float(current.get("total_assets"))
        ta_prior = _safe_float(prior.get("total_assets"))
        at_cur = _safe_div(revenue_cur, ta_cur)
        at_prior = _safe_div(revenue_prior, ta_prior)
        delta_at = (at_cur - at_prior) if at_cur is not None and at_prior is not None else None
        p9_delta_at = (delta_at or 0) > 0
        efficiency_details["p9_asset_turnover_improving"] = p9_delta_at

        efficiency_score = sum([p8_delta_gm, p9_delta_at])

        # =========== 总分与评级 ===========
        total_score = profitability_score + leverage_score + efficiency_score

        if total_score >= 7:
            rating = "优质"
        elif total_score >= 4:
            rating = "中性"
        else:
            rating = "弱势"

        if len(records) < 3:
            warnings.append(f"仅获取到 {len(records)} 年数据，评分可能不够稳健")

        payload = {
            "symbol": symbol,
            "f_score": total_score,
            "rating": rating,
            "categories": {
                "profitability": {
                    "score": profitability_score,
                    "max": 4,
                    "details": profitability_details,
                },
                "leverage_liquidity": {
                    "score": leverage_score,
                    "max": 3,
                    "details": leverage_details,
                },
                "operating_efficiency": {
                    "score": efficiency_score,
                    "max": 2,
                    "details": efficiency_details,
                },
            },
            "comparison": {
                "current_year": current_year,
                "prior_year": prior_year,
            },
            "data_quality": {"warnings": warnings},
        }

        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("Piotroski F-Score计算失败: %s", exc, exc_info=True)
        return json.dumps(
            {"status": "error", "message": str(exc)},
            ensure_ascii=False, indent=2, default=str,
        )


__all__ = ["get_piotroski_fscore"]
