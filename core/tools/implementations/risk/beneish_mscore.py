"""Beneish M-Score 盈余操纵概率评估工具"""

import json
import logging
from typing import Annotated

from langchain_core.tools import tool

from core.skill_runtime.data_access import get_stock_financial_periods
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


def _match_financial_period_by_year(
    fin_periods: list[dict], year: int
) -> dict | None:
    """从财务期间数据中匹配指定年份的年报记录"""
    for record in fin_periods:
        report_period = str(record.get("report_period") or record.get("report_date") or "")
        report_type = str(record.get("report_type") or "").lower()
        # 年报类型过滤
        if report_type and report_type not in ("annual", "yearly", "年报"):
            continue
        # 从 report_period 提取年份（格式如 20231231）
        clean = report_period.replace("-", "").replace("/", "")
        if len(clean) >= 8 and clean[:4] == str(year):
            return record
    return None


@tool
@register_tool(
    tool_id="get_beneish_mscore",
    name="Beneish M-Score 盈余操纵概率",
    description="基于Beneish M-Score模型评估公司盈余操纵概率，通过8个财务比率的变化检测潜在盈余管理行为。",
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["earnings_manipulation", "accounting_quality"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["accounting_fraud_detection"],
    when_to_use="当需要评估公司盈余质量、识别潜在会计操纵或财务造假风险时使用。",
    when_not_to_use="M-Score不能替代深度尽职调查；高分仅表示操纵概率较高，需结合其他信息综合判断。",
    returns="返回JSON字符串，包含m_score、interpretation、threshold、components和data_quality。",
    example="get_beneish_mscore(symbol='600519')",
    related_tools=["get_altman_zscore", "get_piotroski_fscore"],
)
def get_beneish_mscore(symbol: Annotated[str, "A 股股票代码，如 600519、000001"]) -> str:
    """计算 Beneish M-Score 盈余操纵概率。通过8个财务比率变化检测潜在盈余管理行为。

    Args:
        symbol: A 股股票代码，如 600519、000001

    Returns:
        str: JSON 字符串，字段说明——
            status: "error" 时存在；成功时不包含该字段
            symbol: 标的股票代码
            m_score: M-Score 评分（高于阈值 -1.78 表示操纵概率较高）
            interpretation: 解读文案，"盈余操纵概率较高" | "盈余操纵概率较低"
            threshold: 判定阈值（-1.78）
            components: dict，8 个分量，每个分量为 {value, weight, contribution}——
                — dsri: 应收账款周转天数指数
                — gmi: 毛利率指数
                — aqi: 资产质量指数
                — sgi: 销售增长指数
                — depi: 折旧指数（默认 1.0）
                — sgai: 销售管理费用指数（默认 1.0）
                — tata: 总应计项目 / 总资产
                — lvgi: 杠杆指数
            data_quality: dict，数据质量——
                — years_available: 可用年报年数
                — depi_defaulted: 折旧指数是否使用默认值
                — sgai_defaulted: 销售管理费用指数是否使用默认值
                — warnings: list[str]，告警信息
            message: 当 status 为 "error" 时的错误描述
    """
    try:
        warnings: list[str] = []

        # 获取年报序列（需要当前年 + 前一年）
        annual_data = get_historical_financial_annual_series(symbol, years=3)
        records = annual_data.get("records") or []
        warnings.extend(annual_data.get("warnings") or [])

        if len(records) < 2:
            return json.dumps(
                {
                    "status": "error",
                    "message": f"年报数据不足，仅获取到 {len(records)} 年数据，需要至少2年",
                    "symbol": symbol,
                },
                ensure_ascii=False, indent=2, default=str,
            )

        current = records[0]
        prior = records[1]

        current_year = current.get("year")
        prior_year = prior.get("year")

        # 获取财务期间数据（用于 accounts_receiv 和 total_cur_assets）
        fin_periods = get_stock_financial_periods(symbol, limit=30)

        fin_cur = _match_financial_period_by_year(fin_periods, current_year) if current_year else None
        fin_prior = _match_financial_period_by_year(fin_periods, prior_year) if prior_year else None

        # 从年报序列提取基础字段
        revenue_cur = _safe_float(current.get("revenue"))
        revenue_prior = _safe_float(prior.get("revenue"))
        net_profit_cur = _safe_float(current.get("net_profit"))
        ocf_cur = _safe_float(current.get("operating_cashflow"))
        ta_cur = _safe_float(current.get("total_assets"))
        ta_prior = _safe_float(prior.get("total_assets"))
        tl_cur = _safe_float(current.get("total_liab"))
        tl_prior = _safe_float(prior.get("total_liab"))
        gm_cur = _safe_float(current.get("gross_margin"))
        gm_prior = _safe_float(prior.get("gross_margin"))

        # 从财务期间数据提取 accounts_receiv 和 total_cur_assets
        ar_cur = _safe_float(fin_cur.get("accounts_receiv")) if fin_cur else None
        ar_prior = _safe_float(fin_prior.get("accounts_receiv")) if fin_prior else None
        tca_cur = _safe_float(fin_cur.get("total_cur_assets")) if fin_cur else None
        tca_prior = _safe_float(fin_prior.get("total_cur_assets")) if fin_prior else None

        if ar_cur is None or ar_prior is None:
            warnings.append("应收账款数据缺失，DSRI使用默认值1.0")
        if tca_cur is None or tca_prior is None:
            warnings.append("流动资产数据缺失，AQI使用默认值1.0")

        # ---- DSRI: Days Sales in Receivables Index ----
        dsri_ratio_cur = _safe_div(ar_cur, revenue_cur)
        dsri_ratio_prior = _safe_div(ar_prior, revenue_prior)
        dsri = _safe_div(dsri_ratio_cur, dsri_ratio_prior) if dsri_ratio_cur is not None and dsri_ratio_prior is not None else 1.0

        # ---- GMI: Gross Margin Index (inverse) ----
        gmi = _safe_div(gm_prior, gm_cur) if gm_cur is not None and gm_prior is not None else 1.0

        # ---- AQI: Asset Quality Index ----
        # 近似: (non_current / total_assets)_t / (non_current / total_assets)_t-1
        nc_ratio_cur = (
            _safe_div((ta_cur or 0) - (tca_cur or 0), ta_cur)
            if ta_cur is not None and tca_cur is not None
            else None
        )
        nc_ratio_prior = (
            _safe_div((ta_prior or 0) - (tca_prior or 0), ta_prior)
            if ta_prior is not None and tca_prior is not None
            else None
        )
        aqi = _safe_div(nc_ratio_cur, nc_ratio_prior) if nc_ratio_cur is not None and nc_ratio_prior is not None else 1.0

        # ---- SGI: Sales Growth Index ----
        sgi = _safe_div(revenue_cur, revenue_prior) if revenue_cur is not None and revenue_prior is not None else 1.0

        # ---- DEPI: Depreciation Index ----
        depi = 1.0
        depi_defaulted = True
        if depi_defaulted:
            warnings.append("折旧指数(DEPI)使用默认值1.0，因缺乏折旧数据")

        # ---- SGAI: SG&A Index ----
        # 缺乏 admin_exp 数据，默认1.0
        sgai = 1.0
        warnings.append("销售管理费用指数(SGAI)使用默认值1.0，因缺乏管理费用数据")

        # ---- TATA: Total Accruals to Total Assets ----
        tata = _safe_div(
            (net_profit_cur or 0) - (ocf_cur or 0),
            ta_cur,
        ) if net_profit_cur is not None and ocf_cur is not None and ta_cur is not None else 0.0

        # ---- LVGI: Leverage Index ----
        lvgi_ratio_cur = _safe_div(tl_cur, ta_cur)
        lvgi_ratio_prior = _safe_div(tl_prior, ta_prior)
        lvgi = _safe_div(lvgi_ratio_cur, lvgi_ratio_prior) if lvgi_ratio_cur is not None and lvgi_ratio_prior is not None else 1.0

        # 8个变量与权重
        variables = {
            "dsri": {"value": dsri or 0.0, "weight": 0.92},
            "gmi": {"value": gmi or 0.0, "weight": 0.528},
            "aqi": {"value": aqi or 0.0, "weight": 0.404},
            "sgi": {"value": sgi or 0.0, "weight": 0.892},
            "depi": {"value": depi or 0.0, "weight": 0.115},
            "sgai": {"value": sgai or 0.0, "weight": -0.172},
            "tata": {"value": tata or 0.0, "weight": 4.679},
            "lvgi": {"value": lvgi or 0.0, "weight": -0.327},
        }

        # 计算 M-Score
        m_score = -4.84
        components = {}
        for key, item in variables.items():
            contribution = round(item["value"] * item["weight"], 4)
            m_score += contribution
            components[key] = {
                "value": round(item["value"], 4),
                "weight": item["weight"],
                "contribution": contribution,
            }

        m_score = round(m_score, 4)

        threshold = -1.78
        if m_score > threshold:
            interpretation = "盈余操纵概率较高"
        else:
            interpretation = "盈余操纵概率较低"

        payload = {
            "symbol": symbol,
            "m_score": m_score,
            "interpretation": interpretation,
            "threshold": threshold,
            "components": components,
            "data_quality": {
                "years_available": len(records),
                "depi_defaulted": depi_defaulted,
                "sgai_defaulted": True,
                "warnings": warnings,
            },
        }

        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("Beneish M-Score计算失败: %s", exc, exc_info=True)
        return json.dumps(
            {"status": "error", "message": str(exc)},
            ensure_ascii=False, indent=2, default=str,
        )


__all__ = ["get_beneish_mscore"]
