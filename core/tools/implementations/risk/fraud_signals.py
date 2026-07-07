"""财务造假信号检测工具"""

import json
import logging
from typing import Annotated

import numpy as np
from langchain_core.tools import tool

from core.skill_runtime.data_access import get_stock_financial_periods
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


def _match_financial_period_by_year(fin_periods: list[dict], year: int) -> dict | None:
    """按年份匹配财务期间数据，优先匹配年报（12-31 结束的报告期）。"""
    # 第一轮：优先找年报（report_period 以 12-31 结尾）
    for record in fin_periods:
        report_period = str(record.get("report_period") or record.get("report_date") or "")
        clean = report_period.replace("-", "").replace("/", "")
        if len(clean) >= 8 and clean[:4] == str(year) and clean[4:8] == "1231":
            return record
    # 第二轮：检查 report_type 字段
    for record in fin_periods:
        report_period = str(record.get("report_period") or record.get("report_date") or "")
        clean = report_period.replace("-", "").replace("/", "")
        report_type = str(record.get("report_type") or record.get("statement_type") or "").lower()
        if len(clean) >= 8 and clean[:4] == str(year) and report_type in ("annual", "yearly", "年报"):
            return record
    # 第三轮：退而求其次，找该年份任意报告期（但标注可能非年报）
    for record in fin_periods:
        report_period = str(record.get("report_period") or record.get("report_date") or "")
        clean = report_period.replace("-", "").replace("/", "")
        if len(clean) >= 8 and clean[:4] == str(year):
            return record
    return None


@tool
@register_tool(
    tool_id="get_financial_fraud_signals",
    name="财务造假信号检测",
    description="从收入确认、利润质量、资产异常、关联交易、现金流、毛利率和费用资本化七个维度检测财务造假信号，综合评分0-100分。",
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["fraud_detection", "accounting_quality", "financial_risk", "cashflow_deterioration", "cashflow_quality"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["financial_fraud_screening", "financial_risk_signal_detection", "cashflow_quality_analysis"],
    when_to_use="当需要筛查财务造假风险、发现会计异常信号、识别现金流异常/恶化或评估财报可信度时使用。",
    when_not_to_use="不适用于未披露完整年报的公司；评分基于公开财务数据，不能替代深度尽职调查。",
    returns="返回JSON字符串，包含total_score、rating、categories分项评分与signals、data_quality。",
    example="get_financial_fraud_signals(symbol='600519')",
    related_tools=["get_earnings_quality_score", "get_beneish_mscore"],
)
def get_financial_fraud_signals(symbol: Annotated[str, "A 股股票代码，如 600519、000001"]) -> str:
    """检测财务造假信号。从收入确认、利润质量、资产异常、关联交易、现金流、毛利率和费用资本化七个维度综合评分。

    Args:
        symbol: A 股股票代码，如 600519、000001

    Returns:
        str: JSON 字符串，字段说明——
            status: "error" 时存在；成功时不包含该字段
            symbol: 标的股票代码
            total_score: 总分（满分 100，分数越高越可疑）
            rating: 风险评级，"正常" | "需关注" | "可疑" | "高度可疑"
            categories: dict，七个维度评分与信号——
                — revenue_recognition: dict，收入确认异常（满分 20）——
                    — score: 得分
                    — max: 满分 20
                    — signals: list[str]，信号描述
                — earnings_quality: dict，利润质量异常（满分 20）——
                    — score / max / signals
                — asset_irregularities: dict，资产异常（满分 15）——
                    — score / max / signals
                — related_party: dict，关联交易信号（满分 15）——
                    — score / max / signals
                — cash_flow: dict，现金流异常（满分 15）——
                    — score / max / signals
                — margin_anomalies: dict，毛利率异常（满分 10）——
                    — score / max / signals
                — capitalization: dict，费用资本化信号（满分 5）——
                    — score / max / signals
            warnings: list[str]，过程中产生的告警信息
            data_quality: dict，数据质量——
                — years_available: 可用年报年数
            message: 当 status 为 "error" 时的错误描述
    """
    try:
        warnings: list[str] = []

        # 获取年报序列（至少需要2年）
        annual_data = get_historical_financial_annual_series(symbol, years=5)
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

        if len(records) < 3:
            warnings.append("仅2年报数据，部分同比指标无法计算，评分可靠性受限")

        # 按年份升序便于计算
        sorted_records = sorted(records, key=lambda r: r.get("year") or 0)
        n = len(sorted_records)
        latest = sorted_records[-1]
        latest_year = latest.get("year")
        prior = sorted_records[-2] if n >= 2 else None
        prior_year = prior.get("year") if prior else None

        # 获取财务期间数据（用于 accounts_receiv, inventories, total_cur_assets 等）
        fin_periods = get_stock_financial_periods(symbol, limit=30)
        fin_cur = _match_financial_period_by_year(fin_periods, latest_year) if latest_year else None
        fin_prior = _match_financial_period_by_year(fin_periods, prior_year) if prior_year else None

        # 🔑 检查匹配的期间是否为年报口径
        def _is_annual_period(fin: dict | None) -> bool:
            if not fin:
                return True  # 无数据时不告警
            rp = str(fin.get("report_period") or fin.get("report_date") or "")
            return rp[:10].endswith("12-31") or rp.replace("-", "").endswith("1231")

        if fin_cur and not _is_annual_period(fin_cur):
            warnings.append(f"当期({latest_year})匹配到非年报期间数据，DSO等指标可能存在口径偏差")
        if fin_prior and not _is_annual_period(fin_prior):
            warnings.append(f"上期({prior_year})匹配到非年报期间数据，同比比较可能存在口径偏差")

        # 获取现金流质量趋势
        cf_trend_data = get_cashflow_quality_trend(symbol, years=5)
        cf_trend = cf_trend_data.get("trend") or []

        # ===== 提取基础字段 =====
        rev_cur = _safe_float(latest.get("revenue"))
        rev_prior = _safe_float(prior.get("revenue")) if prior else None
        np_cur = _safe_float(latest.get("net_profit"))
        np_prior = _safe_float(prior.get("net_profit")) if prior else None
        ocf_cur = _safe_float(latest.get("operating_cashflow"))
        ocf_prior = _safe_float(prior.get("operating_cashflow")) if prior else None
        ta_cur = _safe_float(latest.get("total_assets"))
        ta_prior = _safe_float(prior.get("total_assets")) if prior else None
        tl_cur = _safe_float(latest.get("total_liab"))
        te_cur = _safe_float(latest.get("total_equity"))
        gm_cur = _safe_float(latest.get("gross_margin"))
        gm_prior = _safe_float(prior.get("gross_margin")) if prior else None
        npm_cur = _safe_float(latest.get("netprofit_margin"))

        # 财务期间字段
        ar_cur = _safe_float(fin_cur.get("accounts_receiv")) if fin_cur else None
        ar_prior = _safe_float(fin_prior.get("accounts_receiv")) if fin_prior else None
        inv_cur = _safe_float(fin_cur.get("inventories")) if fin_cur else None
        inv_prior = _safe_float(fin_prior.get("inventories")) if fin_prior else None
        tca_cur = _safe_float(fin_cur.get("total_cur_assets")) if fin_cur else None
        tca_prior = _safe_float(fin_prior.get("total_cur_assets")) if fin_prior else None
        tcl_cur = _safe_float(fin_cur.get("total_cur_liab")) if fin_cur else None
        fe_cur = _safe_float(fin_cur.get("fin_exp")) if fin_cur else None

        # ======================================================================
        # D1: 收入确认异常 (20pts)
        # ======================================================================
        d1_score = 0.0
        d1_signals: list[str] = []

        revenue_growth = _pct_change(rev_cur, rev_prior) if rev_cur is not None and rev_prior is not None else None
        ocf_growth = _pct_change(ocf_cur, ocf_prior) if ocf_cur is not None and ocf_prior is not None else None

        # 1a: Revenue growing much faster than OCF
        if revenue_growth is not None and ocf_growth is not None:
            divergence = revenue_growth - ocf_growth
            if divergence > 0.30:
                severity = min(1.0, (divergence - 0.30) / 0.50)
                d1_score += 10.0 * severity
                d1_signals.append(f"营收增长({revenue_growth*100:.1f}%)远超经营现金流增长({ocf_growth*100:.1f}%)， divergence={divergence*100:.1f}%")
            elif divergence > 0.15:
                d1_score += 5.0
                d1_signals.append(f"营收与经营现金流增长差异偏大({divergence*100:.1f}%)")
            else:
                d1_signals.append(f"营收与经营现金流增长基本匹配(divergence={divergence*100:.1f}%)")

        # 1b: DSO (Days Sales Outstanding) 变化
        # 🔑 年化营收：季报营收为累计值，需年化后才能用于 DSO 计算
        cur_period = _detect_period_type(fin_cur) if fin_cur else "unknown"
        prev_period = _detect_period_type(fin_prior) if fin_prior else "unknown"
        cur_factor = _annualize_factor(cur_period)
        prev_factor = _annualize_factor(prev_period)
        rev_cur_ann = rev_cur * cur_factor if rev_cur is not None else None
        rev_prior_ann = rev_prior * prev_factor if rev_prior is not None else None

        if cur_period != "annual" and cur_period != "unknown":
            warnings.append(f"当期利润表为{_PERIOD_LABELS.get(cur_period, cur_period)}口径，DSO计算已使用年化营收")
        if prev_period != "annual" and prev_period != "unknown":
            warnings.append(f"上期利润表为{_PERIOD_LABELS.get(prev_period, prev_period)}口径，DSO计算已使用年化营收")

        dso_cur = _safe_div(ar_cur, _safe_div(rev_cur_ann, 365)) if ar_cur is not None and rev_cur_ann is not None else None
        dso_prior = _safe_div(ar_prior, _safe_div(rev_prior_ann, 365)) if ar_prior is not None and rev_prior_ann is not None else None
        if dso_cur is not None and dso_prior is not None and dso_prior > 0:
            dso_change = (dso_cur - dso_prior) / dso_prior
            if dso_change > 0.20:
                severity = min(1.0, (dso_change - 0.20) / 0.40)
                d1_score += 10.0 * severity
                d1_signals.append(f"DSO 同比增加 {dso_change*100:.1f}%（{dso_prior:.1f}→{dso_cur:.1f}天），回款显著恶化")
            elif dso_change > 0.10:
                d1_score += 4.0
                d1_signals.append(f"DSO 同比增加 {dso_change*100:.1f}%，回款趋紧")
            else:
                d1_signals.append(f"DSO 同比变化 {dso_change*100:.1f}%，回款稳定")
        elif dso_cur is not None:
            d1_signals.append(f"当前 DSO={dso_cur:.1f}天（无上年可比）")
        else:
            warnings.append("应收账款或营收数据缺失，DSO 信号跳过")

        d1_score = min(d1_score, 20.0)

        # ======================================================================
        # D2: 利润质量异常 (20pts)
        # ======================================================================
        d2_score = 0.0
        d2_signals: list[str] = []

        # 2a: Net profit growing but OCF declining
        np_growth = _pct_change(np_cur, np_prior) if np_cur is not None and np_prior is not None else None
        if np_growth is not None and np_growth > 0 and ocf_growth is not None and ocf_growth < 0:
            gap = np_growth - ocf_growth
            severity = min(1.0, gap / 0.50)
            d2_score += 12.0 * severity
            d2_signals.append(f"净利润增长({np_growth*100:.1f}%)但经营现金流下降({ocf_growth*100:.1f}%)，利润含金量低")
        elif np_growth is not None and ocf_growth is not None:
            gap = abs(np_growth - ocf_growth)
            if gap > 0.30:
                d2_score += 4.0
                d2_signals.append(f"净利润增长({np_growth*100:.1f}%)与现金流增长({ocf_growth*100:.1f}%)差距较大")
            else:
                d2_signals.append(f"净利润与现金流增长趋势一致(gap={gap*100:.1f}%)")

        # 2b: Accruals ratio
        accrual_ratios = []
        for i in range(1, n):
            np_val = _safe_float(sorted_records[i].get("net_profit"))
            ocf_val = _safe_float(sorted_records[i].get("operating_cashflow"))
            ta_val = _safe_float(sorted_records[i].get("total_assets"))
            if np_val is not None and ocf_val is not None and ta_val is not None and ta_val > 0:
                accrual_ratios.append((np_val - ocf_val) / ta_val)

        if accrual_ratios:
            mean_accrual = float(np.mean(accrual_ratios))
            if abs(mean_accrual) > 0.1:
                severity = min(1.0, (abs(mean_accrual) - 0.1) / 0.20)
                d2_score += 8.0 * severity
                d2_signals.append(f"应计比率 {mean_accrual:.4f}（绝对值>{abs(mean_accrual):.4f}），利润与现金流偏离较大")
            else:
                d2_signals.append(f"应计比率 {mean_accrual:.4f}，利润质量正常")
        else:
            warnings.append("应计比率无法计算")

        d2_score = min(d2_score, 20.0)

        # ======================================================================
        # D3: 资产异常 (15pts)
        # ======================================================================
        d3_score = 0.0
        d3_signals: list[str] = []

        # 3a: Total assets growing much faster than revenue (asset inflation)
        ta_growth = _pct_change(ta_cur, ta_prior) if ta_cur is not None and ta_prior is not None else None
        if revenue_growth is not None and ta_growth is not None and ta_growth > 0:
            asset_rev_gap = ta_growth - revenue_growth
            if asset_rev_gap > 0.30:
                severity = min(1.0, (asset_rev_gap - 0.30) / 0.50)
                d3_score += 6.0 * severity
                d3_signals.append(f"总资产增长({ta_growth*100:.1f}%)远超营收增长({revenue_growth*100:.1f}%)，资产膨胀")
            elif asset_rev_gap > 0.15:
                d3_score += 3.0
                d3_signals.append(f"总资产增长({ta_growth*100:.1f}%)快于营收，资产效率下降")
            else:
                d3_signals.append(f"总资产与营收增长匹配(gap={asset_rev_gap*100:.1f}%)")

        # 3b: Receivables growing much faster than revenue
        ar_growth = _pct_change(ar_cur, ar_prior) if ar_cur is not None and ar_prior is not None else None
        if ar_growth is not None and revenue_growth is not None and ar_growth > 0:
            ar_rev_gap = ar_growth - revenue_growth
            if ar_rev_gap > 0.30:
                severity = min(1.0, (ar_rev_gap - 0.30) / 0.50)
                d3_score += 5.0 * severity
                d3_signals.append(f"应收账款增长({ar_growth*100:.1f}%)远超营收增长({revenue_growth*100:.1f}%)，信用政策过度宽松")
            elif ar_rev_gap > 0.15:
                d3_score += 2.0
                d3_signals.append(f"应收账款增长({ar_growth*100:.1f}%)快于营收")
            else:
                d3_signals.append(f"应收账款与营收增长匹配")

        # 3c: Inventory growing much faster than COGS
        # Approximate COGS as revenue - gross_profit, or check directly
        if inv_cur is not None and inv_prior is not None:
            inv_growth = _pct_change(inv_cur, inv_prior)
            cogs_cur = rev_cur * (1 - gm_cur / 100) if rev_cur is not None and gm_cur is not None and gm_cur > 1 else None
            cogs_prior = rev_prior * (1 - gm_prior / 100) if rev_prior is not None and gm_prior is not None and gm_prior > 1 else None
            cogs_growth = _pct_change(cogs_cur, cogs_prior) if cogs_cur is not None and cogs_prior is not None else None
            if inv_growth is not None and cogs_growth is not None and cogs_growth > 0:
                inv_cogs_gap = inv_growth - cogs_growth
                if inv_cogs_gap > 0.30:
                    severity = min(1.0, (inv_cogs_gap - 0.30) / 0.50)
                    d3_score += 4.0 * severity
                    d3_signals.append(f"存货增长({inv_growth*100:.1f}%)远超营业成本增长({cogs_growth*100:.1f}%)，可能存在滞销")
                elif inv_cogs_gap > 0.15:
                    d3_score += 2.0
                    d3_signals.append(f"存货增长快于营业成本")
                else:
                    d3_signals.append(f"存货与营业成本增长匹配")
        else:
            warnings.append("存货数据缺失，存货信号跳过")

        d3_score = min(d3_score, 15.0)

        # ======================================================================
        # D4: 关联交易信号 (15pts)
        # ======================================================================
        d4_score = 0.0
        d4_signals: list[str] = []

        # 4a: Other receivables ratio > 10% of total assets (proxy for related party)
        # Use total_cur_assets - accounts_receiv - inventories - money_cap as rough "other receivables"
        money_cap_cur = _safe_float(fin_cur.get("money_cap")) if fin_cur else None
        if tca_cur is not None and ar_cur is not None and inv_cur is not None:
            other_receivables = tca_cur - (ar_cur or 0) - (inv_cur or 0) - (money_cap_cur or 0)
            if ta_cur is not None and ta_cur > 0:
                other_rec_ratio = other_receivables / ta_cur
                if other_rec_ratio > 0.10:
                    severity = min(1.0, (other_rec_ratio - 0.10) / 0.20)
                    d4_score += 8.0 * severity
                    d4_signals.append(f"其他应收类资产占总资产 {other_rec_ratio*100:.1f}%（>10%），关联交易风险较高")
                elif other_rec_ratio > 0.05:
                    d4_score += 3.0
                    d4_signals.append(f"其他应收类资产占总资产 {other_rec_ratio*100:.1f}%，需关注")
                else:
                    d4_signals.append(f"其他应收类资产占比 {other_rec_ratio*100:.1f}%，正常")
        else:
            warnings.append("流动资产数据不足，其他应收信号跳过")

        # 4b: Significant changes in non-current assets
        nca_cur = _safe_float(fin_cur.get("total_nca")) if fin_cur else None
        nca_prior = _safe_float(fin_prior.get("total_nca")) if fin_prior else None
        if nca_cur is not None and nca_prior is not None and nca_prior > 0:
            nca_change = (nca_cur - nca_prior) / nca_prior
            if abs(nca_change) > 0.50:
                severity = min(1.0, (abs(nca_change) - 0.50) / 0.50)
                d4_score += 7.0 * severity
                d4_signals.append(f"非流动资产同比变动 {nca_change*100:.1f}%，幅度异常")
            elif abs(nca_change) > 0.30:
                d4_score += 3.0
                d4_signals.append(f"非流动资产同比变动 {nca_change*100:.1f}%，偏大")
            else:
                d4_signals.append(f"非流动资产同比变动 {nca_change*100:.1f}%，正常")
        else:
            warnings.append("非流动资产数据不足")

        d4_score = min(d4_score, 15.0)

        # ======================================================================
        # D5: 现金流异常 (15pts)
        # ======================================================================
        d5_score = 0.0
        d5_signals: list[str] = []

        # 5a: Net profit positive but operating cashflow negative
        if np_cur is not None and np_cur > 0 and ocf_cur is not None and ocf_cur < 0:
            d5_score += 10.0
            d5_signals.append("净利润为正但经营现金流为负，严重警示信号")
        elif np_cur is not None and ocf_cur is not None and ocf_cur < 0:
            d5_signals.append("经营现金流为负（净利润亦为负）")
        elif np_cur is not None and ocf_cur is not None and ocf_cur / np_cur < 0.5:
            d5_score += 5.0
            d5_signals.append(f"经营现金流仅为净利润的 {ocf_cur/np_cur*100:.1f}%，含金量偏低")
        elif np_cur is not None and ocf_cur is not None:
            d5_signals.append(f"经营现金流覆盖净利润 {ocf_cur/np_cur*100:.1f}%，现金流正常")

        # 5b: Large positive financing cashflow while operations generate cash
        ncf_fin_cur = _safe_float(fin_cur.get("n_cashflow_fin_act")) if fin_cur else None
        if ncf_fin_cur is not None and ocf_cur is not None and ncf_fin_cur > 0 and ocf_cur > 0:
            ratio = ncf_fin_cur / abs(ocf_cur) if ocf_cur != 0 else 0
            if ratio > 0.50:
                d5_score += 5.0
                d5_signals.append(f"经营现金流为正的同时筹资现金流大幅流入(={ratio*100:.1f}% of OCF)，异常")
            else:
                d5_signals.append("筹资与经营现金流关系正常")
        elif ncf_fin_cur is not None:
            d5_signals.append(f"筹资现金流={ncf_fin_cur:.0f}")

        d5_score = min(d5_score, 15.0)

        # ======================================================================
        # D6: 毛利率异常 (10pts)
        # ======================================================================
        d6_score = 0.0
        d6_signals: list[str] = []

        # 6a: Gross margin significantly above typical range
        # Typical A-share gross margins: most companies between 10%-60%
        # Above 90% or below -20% is suspicious
        if gm_cur is not None:
            if gm_cur > 95:
                d6_score += 5.0
                d6_signals.append(f"毛利率高达 {gm_cur:.1f}%，远超正常水平")
            elif gm_cur > 85:
                d6_score += 2.0
                d6_signals.append(f"毛利率较高({gm_cur:.1f}%)，需结合行业判断")
            elif gm_cur < -10:
                d6_score += 5.0
                d6_signals.append(f"毛利率为负({gm_cur:.1f}%)，经营异常")
            else:
                d6_signals.append(f"毛利率 {gm_cur:.1f}%")
        else:
            warnings.append("毛利率数据缺失")

        # 6b: Gross margin improving while revenue declining
        if gm_cur is not None and gm_prior is not None and rev_cur is not None and rev_prior is not None:
            gm_change = _pct_change(gm_cur, gm_prior)
            if gm_change is not None and gm_change > 0.05 and revenue_growth is not None and revenue_growth < -0.05:
                d6_score += 5.0
                d6_signals.append(f"营收下降({revenue_growth*100:.1f}%)但毛利率上升({gm_change*100:.1f}%)，趋势异常")
            elif gm_change is not None:
                d6_signals.append(f"毛利率同比变动 {gm_change*100:.1f}%")

        d6_score = min(d6_score, 10.0)

        # ======================================================================
        # D7: 费用资本化信号 (5pts)
        # ======================================================================
        d7_score = 0.0
        d7_signals: list[str] = []

        # 7a: Asset turnover declining while assets growing
        asset_turnover_cur = _safe_div(rev_cur, ta_cur) if rev_cur is not None and ta_cur is not None else None
        asset_turnover_prior = _safe_div(rev_prior, ta_prior) if rev_prior is not None and ta_prior is not None and prior else None
        if asset_turnover_cur is not None and asset_turnover_prior is not None:
            at_change = (asset_turnover_cur - asset_turnover_prior) / asset_turnover_prior
            ta_growth = _pct_change(ta_cur, ta_prior)
            if at_change is not None and at_change < -0.15 and ta_growth is not None and ta_growth > 0.10:
                d7_score += 3.0
                d7_signals.append(f"总资产周转率下降({at_change*100:.1f}%)而资产增长({ta_growth*100:.1f}%)，收入确认可能偏慢")
            else:
                d7_signals.append(f"资产周转率同比变动 {at_change*100:.1f}%")
        else:
            warnings.append("资产周转率无法计算")

        # 7b: Fixed assets growing but revenue flat
        fix_assets_cur = _safe_float(fin_cur.get("fix_assets")) if fin_cur else None
        fix_assets_prior = _safe_float(fin_prior.get("fix_assets")) if fin_prior else None
        if fix_assets_cur is not None and fix_assets_prior is not None and rev_cur is not None and rev_prior is not None:
            fa_growth = _pct_change(fix_assets_cur, fix_assets_prior)
            if fa_growth is not None and fa_growth > 0.20 and revenue_growth is not None and revenue_growth < 0.05:
                d7_score += 2.0
                d7_signals.append(f"固定资产增长({fa_growth*100:.1f}%)但营收未同步增长({revenue_growth*100:.1f}%)，费用资本化可能")
            elif fa_growth is not None:
                d7_signals.append(f"固定资产同比变动 {fa_growth*100:.1f}%")

        d7_score = min(d7_score, 5.0)

        # ======================================================================
        # 总分与评级
        # ======================================================================
        total_score = round(d1_score + d2_score + d3_score + d4_score + d5_score + d6_score + d7_score, 1)

        if total_score <= 30:
            rating = "正常"
        elif total_score <= 50:
            rating = "需关注"
        elif total_score <= 70:
            rating = "可疑"
        else:
            rating = "高度可疑"

        # 附加备注
        warnings.append("注：行业平均毛利率不可用，毛利率异常判断基于绝对阈值")

        payload = {
            "symbol": symbol,
            "total_score": total_score,
            "rating": rating,
            "categories": {
                "revenue_recognition": {
                    "score": round(d1_score, 1),
                    "max": 20,
                    "signals": d1_signals,
                },
                "earnings_quality": {
                    "score": round(d2_score, 1),
                    "max": 20,
                    "signals": d2_signals,
                },
                "asset_irregularities": {
                    "score": round(d3_score, 1),
                    "max": 15,
                    "signals": d3_signals,
                },
                "related_party": {
                    "score": round(d4_score, 1),
                    "max": 15,
                    "signals": d4_signals,
                },
                "cash_flow": {
                    "score": round(d5_score, 1),
                    "max": 15,
                    "signals": d5_signals,
                },
                "margin_anomalies": {
                    "score": round(d6_score, 1),
                    "max": 10,
                    "signals": d6_signals,
                },
                "capitalization": {
                    "score": round(d7_score, 1),
                    "max": 5,
                    "signals": d7_signals,
                },
            },
            "warnings": warnings,
            "data_quality": {
                "years_available": n,
            },
        }

        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("财务造假信号检测失败: %s", exc, exc_info=True)
        return json.dumps(
            {"status": "error", "message": str(exc)},
            ensure_ascii=False, indent=2, default=str,
        )


__all__ = ["get_financial_fraud_signals"]
