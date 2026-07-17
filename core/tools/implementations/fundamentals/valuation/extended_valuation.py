"""扩展估值模型工具集合：DCF三阶段、DDM、剩余收益、EVA、FCFF/FCFE、PEG、格雷厄姆、CAPM、增长质量调整估值"""

import json
import logging
from statistics import mean, pstdev
from typing import Annotated, Optional

import numpy as np
from langchain_core.tools import tool

from core.tools.base import register_tool

logger = logging.getLogger(__name__)


def _safe_div(numerator, denominator):
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def _cagr(latest, earliest, periods):
    if latest is None or earliest is None or earliest <= 0 or latest <= 0 or periods <= 0:
        return None
    return (latest / earliest) ** (1 / periods) - 1


def _resolve_shares(basic_info: dict, current_price=None, warnings: Optional[list] = None):
    """统一解析总股本，返回单位为「股」的数值。

    基础信息表中：
      - total_share / float_share 单位为「万股」→ 需 ×1e4 换算成股
      - total_mv / circ_mv 单位为「亿元」→ 需 ×1e8 换算成元
    财报口径（equity_value/net_profit/total_equity 等）单位为「元」，
    若直接用「万股」做除数，每股结果会放大 1e4 倍（如茅台会算出千万级/股）。
    """
    raw_shares = (
        basic_info.get("total_shares")
        or basic_info.get("total_share")   # 万股
        or basic_info.get("float_shares")
        or basic_info.get("float_share")   # 万股
    )
    if raw_shares is not None and raw_shares > 0:
        return float(raw_shares) * 1e4  # 万股 → 股

    # 兜底：市值 / 当前价推算
    raw_mv = basic_info.get("total_mv") or basic_info.get("circ_mv")
    market_cap = basic_info.get("market_cap") or basic_info.get("market_value")
    if raw_mv and raw_mv > 0:
        market_cap = float(raw_mv) * 1e8  # 亿元 → 元
    if market_cap and current_price and current_price > 0:
        return market_cap / current_price

    if warnings is not None:
        warnings.append("无法获取总股本，默认使用约 12.5 亿股估算。")
    return 1.256e9


# ─────────────────────────────────────────────────────────────
# Tool 1: DCF 三阶段估值
# ─────────────────────────────────────────────────────────────


@tool
@register_tool(
    tool_id="get_dcf_three_stage_valuation",
    name="DCF 三阶段估值",
    description="基于三阶段 DCF 模型对 A 股绝对估值，返回三阶段现金流预测、折现值、内在价值、安全边际和敏感性分析，适用于高增长企业",
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["valuation", "dcf", "absolute_valuation", "three_stage_dcf", "discounted_cashflow"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["absolute_valuation", "intrinsic_value_estimation", "three_stage_dcf"],
    when_to_use="当需要进行三阶段 DCF 绝对估值、估算高增长企业内在价值时使用。适合有明确高增长期后增速放缓的企业。",
    when_not_to_use="不适合 FCF 持续为负的企业。不适合金融类企业。不适合简单成熟企业（两阶段 DCF 即可）。",
    returns="返回 JSON 字符串，包含三阶段参数、情景分析、敏感性矩阵和每股内在价值。",
    example="get_dcf_three_stage_valuation(symbol='600519')",
    related_tools=["get_dcf_valuation", "get_wacc_calculation"],
)
def get_dcf_three_stage_valuation(
    symbol: Annotated[str, "A 股股票代码，如 600519"],
    growth_rate: Annotated[Optional[float], "预测期年化增长率，默认 None 由历史数据自动估算"] = None,
    wacc: Annotated[Optional[float], "折现率（加权平均资本成本），默认 None 自动计算"] = None,
    terminal_growth_rate: Annotated[float, "永续增长率，默认 2.5%"] = 2.5,
    high_growth_years: Annotated[int, "高增长期年数，默认 5"] = 5,
    transition_years: Annotated[int, "过渡期年数，默认 3"] = 3,
    high_growth_rate: Annotated[Optional[float], "高增长期增长率，默认 None 使用 growth_rate"] = None,
    transition_end_rate: Annotated[float, "过渡期结束时的增长率（即永续前增速），默认 5%"] = 0.05,
    base_fcf: Annotated[Optional[float], "基期自由现金流覆盖值，默认 None 使用最新年报数据"] = None,
) -> str:
    """DCF 三阶段估值模型：高增长 → 过渡（线性递减） → 永续

    Args:
        symbol: A 股股票代码，如 600519
        growth_rate: 预测期年化增长率（小数形式），默认 None 由历史营收数据自动估算并夹钳到 [0.03, 0.25]
        wacc: 折现率（小数形式），默认 None 自动计算并夹钳到 [0.05, 0.20]
        terminal_growth_rate: 永续增长率，默认 2.5（>1 时视为百分比，自动除以 100）
        high_growth_years: 高增长期年数，默认 5，自动夹钳到 [1, 15]
        transition_years: 过渡期年数，默认 3，自动夹钳到 [1, 10]
        high_growth_rate: 高增长期增长率（小数形式），默认 None 时使用 growth_rate
        transition_end_rate: 过渡期结束时的增长率（即永续前增速），默认 0.05
        base_fcf: 基期自由现金流覆盖值，默认 None 使用最新年报数据；若 ≤0 依次回退到 operating_cashflow、net_profit×0.7

    Returns:
        str: JSON 字符串，包含以下可能结构——

        错误情形返回 dict，字段：
            status: "error"
            message: 错误描述
            symbol: 股票代码

        成功情形返回 dict，字段：
            symbol: 股票代码
            method: "三阶段DCF"
            stages: 三阶段参数 dict —
                high_growth_years: 高增长期年数
                transition_years: 过渡期年数
                perpetual_growth_rate: 永续增长率（小数）
            parameters: 估值参数 dict —
                high_growth_rate: 高增长期增长率（小数）
                transition_end_rate: 过渡期结束增长率（小数）
                terminal_growth_rate: 永续增长率（小数）
                wacc: 折现率（小数）
            base_year: 基期信息 dict —
                year: 基期年份
                free_cashflow: 基期自由现金流
            valuation: 估值结果 dict —
                pv_stage1_high_growth: 高增长期现值合计
                pv_stage2_transition: 过渡期现值合计
                pv_terminal: 永续期现值
                enterprise_value: 企业价值
                equity_value: 股权价值
                per_share_value: 每股内在价值
                current_price: 当前股价
                upside_pct: 相对当前价格的上行空间百分比
                net_debt_adjustment: 净债务调整额
            scenarios: 情景分析 dict —
                base: 基准情景 dict — per_share_value, upside_pct
                bull: 乐观情景 dict — per_share_value, upside_pct
                bear: 悲观情景 dict — per_share_value, upside_pct
            sensitivity: 敏感性分析 dict —
                wacc_range: WACC 取值列表（3 个值）
                growth_range: 高增长率取值列表（3 个值）
                matrix: 每股价值矩阵 [[值, 值, 值], ...]
            data_quality: 数据质量 dict —
                years_available: 可用年报期数
                base_fcf_source: FCF 来源："parameter_override" | "free_cashflow" | "operating_cashflow" | "net_profit_estimated"
                growth_source: 增长率来源："parameter_override" | "revenue_historical_mean"
                wacc_source: WACC 来源："parameter_override" | "auto_computed"
                warnings: 警告信息列表

        异常时返回 dict：{"status": "error", "message": ...}
    """
    try:
        from core.skill_runtime.standard_financial_apis import get_historical_financial_annual_series

        series = get_historical_financial_annual_series(symbol, years=5)
        records = series.get("records") or []

        warnings: list = []
        if len(records) < 2:
            return json.dumps(
                {"status": "error", "message": f"可用年报数据不足（仅 {len(records)} 期），无法进行 DCF 三阶段估值", "symbol": symbol},
                ensure_ascii=False, indent=2, default=str,
            )

        latest = records[0]
        cf_fcf = base_fcf if base_fcf is not None else latest.get("free_cashflow")
        cf_ocf = latest.get("operating_cashflow")
        cf_np = latest.get("net_profit")

        fcf_source = "parameter_override" if base_fcf is not None else "free_cashflow"
        resolved_fcf = cf_fcf

        if resolved_fcf is None or resolved_fcf <= 0:
            if cf_ocf is not None and cf_ocf > 0:
                resolved_fcf = cf_ocf
                fcf_source = "operating_cashflow"
            elif cf_np is not None and cf_np > 0:
                resolved_fcf = cf_np * 0.7
                fcf_source = "net_profit_estimated"
            else:
                return json.dumps(
                    {
                        "status": "error",
                        "message": (
                            f"无法确定有效的基期自由现金流。"
                            f"free_cashflow={cf_fcf}, operating_cashflow={cf_ocf}, net_profit={cf_np}"
                        ),
                        "symbol": symbol,
                    },
                    ensure_ascii=False, indent=2, default=str,
                )

        # 确定增长率
        if growth_rate is not None:
            resolved_growth = growth_rate
            growth_source = "parameter_override"
        else:
            revenue_values = [r.get("revenue") for r in records if r.get("revenue") is not None and r.get("revenue") > 0]
            if len(revenue_values) >= 2:
                annual_growth_rates = []
                for i in range(len(revenue_values) - 1):
                    prev = revenue_values[i + 1]
                    curr = revenue_values[i]
                    if prev and prev > 0:
                        annual_growth_rates.append((curr - prev) / prev)
                avg_growth = np.mean(annual_growth_rates) if annual_growth_rates else 0.03
            else:
                avg_growth = 0.03
            resolved_growth = max(0.03, min(0.25, avg_growth))
            growth_source = "revenue_historical_mean"
            if avg_growth < 0.03:
                warnings.append(f"历史营收增长率偏低 ({avg_growth:.1%})，已夹钳至下限 3%。")
            if avg_growth > 0.25:
                warnings.append(f"历史营收增长率偏高 ({avg_growth:.1%})，已夹钳至上限 25%。")

        resolved_high_growth = high_growth_rate if high_growth_rate is not None else resolved_growth

        # 计算 WACC
        if wacc is not None:
            resolved_wacc = wacc
            wacc_source = "parameter_override"
        else:
            cost_of_equity = 0.035 + 1.0 * 0.06
            cost_of_debt = 0.04
            debt_to_assets = latest.get("debt_to_assets")
            if debt_to_assets is not None:
                debt_weight = debt_to_assets / 100.0 if debt_to_assets > 1 else debt_to_assets
            else:
                total_liab = latest.get("total_liab")
                total_assets = latest.get("total_assets")
                if total_liab is not None and total_assets is not None and total_assets > 0:
                    debt_weight = total_liab / total_assets
                else:
                    debt_weight = 0.4
                    warnings.append("负债率数据缺失，采用默认债权权重 40%。")
            equity_weight = 1.0 - debt_weight
            resolved_wacc = equity_weight * cost_of_equity + debt_weight * cost_of_debt * (1 - 0.25)
            resolved_wacc = max(0.05, min(0.20, resolved_wacc))
            wacc_source = "auto_computed"

        tgr = terminal_growth_rate / 100.0 if terminal_growth_rate > 1 else terminal_growth_rate
        n_high = max(1, min(15, int(high_growth_years)))
        n_trans = max(1, min(10, int(transition_years)))
        total_years = n_high + n_trans

        # Stage 1: 高增长期
        stage1_fcfs = []
        for yr in range(1, n_high + 1):
            fcf = resolved_fcf * (1 + resolved_high_growth) ** yr
            stage1_fcfs.append(fcf)

        # Stage 2: 过渡期（线性递减）
        last_high_fcf = stage1_fcfs[-1] if stage1_fcfs else resolved_fcf
        stage2_fcfs = []
        for yr in range(1, n_trans + 1):
            decay = yr / n_trans
            g = resolved_high_growth * (1 - decay) + transition_end_rate * decay
            fcf = last_high_fcf * (1 + g)
            stage2_fcfs.append(fcf)
            if yr == n_trans:
                last_trans_fcf = fcf

        last_trans_fcf = last_trans_fcf if stage2_fcfs else last_high_fcf

        # Stage 3: 永续增长
        terminal_value = last_trans_fcf * (1 + tgr) / (resolved_wacc - tgr)

        # 折现到现值
        pv_stage1 = sum(fcf / (1 + resolved_wacc) ** yr for yr, fcf in enumerate(stage1_fcfs, 1))
        pv_stage2 = sum(fcf / (1 + resolved_wacc) ** (n_high + yr) for yr, fcf in enumerate(stage2_fcfs, 1))
        pv_terminal = terminal_value / (1 + resolved_wacc) ** total_years
        enterprise_value = pv_stage1 + pv_stage2 + pv_terminal

        # 净债务调整
        net_debt = latest.get("total_liab") or 0
        equity_value = enterprise_value - net_debt

        # 股本和当前价格
        from core.skill_runtime.data_access import get_stock_basic_info, get_latest_stock_price

        basic_info = get_stock_basic_info(symbol) or {}
        current_price = get_latest_stock_price(symbol)

        shares = _resolve_shares(basic_info, current_price, warnings)

        per_share_value = equity_value / shares if shares and shares > 0 else None
        upside_pct = ((per_share_value - current_price) / current_price * 100) if (per_share_value and current_price and current_price > 0) else None

        # 情景分析
        def _scenario(hg: float, tr: float, w: float) -> dict:
            s1 = [resolved_fcf * (1 + hg) ** y for y in range(1, n_high + 1)]
            ls1 = s1[-1] if s1 else resolved_fcf
            s2 = []
            for y in range(1, n_trans + 1):
                d = y / n_trans
                g = hg * (1 - d) + tr * d
                s2.append(ls1 * (1 + g))
            lt = s2[-1] if s2 else ls1
            tv = lt * (1 + tgr) / (w - tgr)
            ev_ = sum(s1[y] / (1 + w) ** (y + 1) for y in range(n_high))
            ev_ += sum(s2[y] / (1 + w) ** (n_high + y + 1) for y in range(n_trans))
            ev_ += tv / (1 + w) ** total_years
            eq = ev_ - net_debt
            psv = eq / shares if shares and shares > 0 else None
            up = ((psv - current_price) / current_price * 100) if (psv and current_price and current_price > 0) else None
            return {"per_share_value": psv, "upside_pct": up}

        scenarios = {
            "base": {"per_share_value": per_share_value, "upside_pct": upside_pct},
            "bull": _scenario(resolved_high_growth * 1.3, transition_end_rate * 1.3, resolved_wacc * 0.7),
            "bear": _scenario(resolved_high_growth * 0.7, transition_end_rate * 0.7, resolved_wacc * 1.3),
        }

        # 敏感性矩阵
        wacc_range = [resolved_wacc - 0.01, resolved_wacc, resolved_wacc + 0.01]
        growth_range = [resolved_high_growth - 0.01, resolved_high_growth, resolved_high_growth + 0.01]
        matrix = []
        for w in wacc_range:
            row = []
            for g in growth_range:
                s = _scenario(g, transition_end_rate, w)
                row.append(s.get("per_share_value"))
            matrix.append(row)

        payload = {
            "symbol": symbol,
            "method": "三阶段DCF",
            "stages": {
                "high_growth_years": n_high,
                "transition_years": n_trans,
                "perpetual_growth_rate": round(tgr, 4),
            },
            "parameters": {
                "high_growth_rate": round(resolved_high_growth, 4),
                "transition_end_rate": round(transition_end_rate, 4),
                "terminal_growth_rate": round(tgr, 4),
                "wacc": round(resolved_wacc, 4),
            },
            "base_year": {
                "year": latest.get("year"),
                "free_cashflow": resolved_fcf,
            },
            "valuation": {
                "pv_stage1_high_growth": round(pv_stage1, 2),
                "pv_stage2_transition": round(pv_stage2, 2),
                "pv_terminal": round(pv_terminal, 2),
                "enterprise_value": round(enterprise_value, 2),
                "equity_value": round(equity_value, 2),
                "per_share_value": round(per_share_value, 2) if per_share_value is not None else None,
                "current_price": current_price,
                "upside_pct": round(upside_pct, 2) if upside_pct is not None else None,
                "net_debt_adjustment": round(net_debt, 2),
            },
            "scenarios": scenarios,
            "sensitivity": {
                "wacc_range": [round(w, 4) for w in wacc_range],
                "growth_range": [round(g, 4) for g in growth_range],
                "matrix": [[round(v, 2) if v is not None else None for v in row] for row in matrix],
            },
            "data_quality": {
                "years_available": len(records),
                "base_fcf_source": fcf_source,
                "growth_source": growth_source,
                "wacc_source": wacc_source,
                "warnings": warnings,
            },
        }
        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    except Exception as exc:
        logger.error("DCF三阶段估值失败: %s", exc, exc_info=True)
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2, default=str)


# ─────────────────────────────────────────────────────────────
# Tool 2: DDM 股利贴现模型
# ─────────────────────────────────────────────────────────────


@tool
@register_tool(
    tool_id="get_ddm_valuation",
    name="股利贴现模型",
    description="基于 Gordon Growth 模型对 A 股股利贴现估值，返回预期股利、贴现率、股利增长率、内在价值和安全边际，适用于稳定派息企业",
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["valuation", "ddm", "dividend_discount", "gordon_growth"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["dividend_valuation", "mature_dividend_stock_valuation"],
    when_to_use="适用于稳定派息的成熟企业估值，判断股价相对于股利折现价值的合理性。",
    when_not_to_use="不适合不派息或派息不稳定的公司（会返回 no_dividend_data）。不适合高增长未盈利企业。",
    returns="返回 JSON 字符串，包含当前股利、增长率、必要回报率、内在价值及上涨空间。",
    example="get_ddm_valuation(symbol='600519')",
    related_tools=["get_dcf_valuation", "get_shareholder_return_metrics"],
)
def get_ddm_valuation(
    symbol: Annotated[str, "A 股股票代码，如 600519"],
    growth_rate: Annotated[float, "股利永续增长率，默认 5%"] = 0.05,
    required_return: Annotated[float, "必要回报率（折现率），默认 8%"] = 0.08,
) -> str:
    """股利贴现模型（Gordon Growth Model）

    Args:
        symbol: A 股股票代码，如 600519
        growth_rate: 股利永续增长率（小数形式），默认 0.05；若 ≥ required_return，自动调整为 required_return + 0.03
        required_return: 必要回报率/折现率（小数形式），默认 0.08

    Returns:
        str: JSON 字符串，包含以下可能结构——

        无分红数据情形返回 dict，字段：
            status: "no_dividend_data"
            symbol: 股票代码
            message: 描述信息

        错误/异常情形返回 dict，字段：
            status: "error"
            message: 错误描述

        成功情形返回 dict，字段：
            symbol: 股票代码
            method: "gordon_growth_model"
            parameters: 参数 dict —
                current_dividend_per_share: 当前每股股利
                expected_dividend_d1: 预期下一期股利 D1
                growth_rate: 永续增长率（小数）
                required_return: 必要回报率（小数）
            valuation: 估值结果 dict —
                intrinsic_value: 内在价值
                current_price: 当前股价
                upside_pct: 相对当前价格的上行空间百分比
            dividend_history: 历年分红记录列表（最多 5 条）
            data_quality: 数据质量 dict —
                dividend_records_count: 分红记录条数
                dividend_positive_years: 正分红年数
                latest_dividend_yield: 最新股息率
                warnings: 警告信息列表
    """
    try:
        from core.skill_runtime.data_access import get_latest_stock_price
        from core.skill_runtime.standard_financial_apis import get_shareholder_return_metrics

        # 获取分红数据
        div_metrics = get_shareholder_return_metrics(symbol, years=5)
        records = div_metrics.get("records") or []
        annual = div_metrics.get("annual") or []
        metrics = div_metrics.get("metrics") or {}
        latest_cash = metrics.get("latest_cash_dividend_per_share")
        current_price = div_metrics.get("current_price") or get_latest_stock_price(symbol)

        if latest_cash is None or latest_cash <= 0:
            return json.dumps(
                {
                    "status": "no_dividend_data",
                    "symbol": symbol,
                    "message": "未找到有效的现金分红数据，无法进行股利贴现估值。该股票可能不派息或分红数据未同步。",
                },
                ensure_ascii=False, indent=2, default=str,
            )

        # Gordon Growth Model: P = D1 / (r - g)
        d1 = latest_cash * (1 + growth_rate)

        if required_return <= growth_rate:
            required_return = growth_rate + 0.03

        intrinsic_value = d1 / (required_return - growth_rate)
        upside_pct = ((intrinsic_value - current_price) / current_price * 100) if (current_price and current_price > 0) else None

        payload = {
            "symbol": symbol,
            "method": "gordon_growth_model",
            "parameters": {
                "current_dividend_per_share": latest_cash,
                "expected_dividend_d1": round(d1, 4),
                "growth_rate": round(growth_rate, 4),
                "required_return": round(required_return, 4),
            },
            "valuation": {
                "intrinsic_value": round(intrinsic_value, 2),
                "current_price": current_price,
                "upside_pct": round(upside_pct, 2) if upside_pct is not None else None,
            },
            "dividend_history": annual[:5] if annual else [],
            "data_quality": {
                "dividend_records_count": len(records),
                "dividend_positive_years": metrics.get("dividend_positive_years"),
                "latest_dividend_yield": metrics.get("latest_dividend_yield"),
                "warnings": div_metrics.get("warnings") or [],
            },
        }
        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    except Exception as exc:
        logger.error("DDM估值失败: %s", exc, exc_info=True)
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2, default=str)


# ─────────────────────────────────────────────────────────────
# Tool 3: 剩余收益估值
# ─────────────────────────────────────────────────────────────


@tool
@register_tool(
    tool_id="get_residual_income_valuation",
    name="剩余收益估值",
    description="基于剩余收益模型对 A 股进行绝对估值，返回账面价值、剩余收益序列、内在价值、溢价和适用场景判断，适用于银行等资产密集型企业",
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["valuation", "residual_income", "absolute_valuation", "rim"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["residual_income_valuation", "book_value_based_valuation"],
    when_to_use="适用于有正账面价值和 ROE 数据的企业，特别适合银行业和保险业等资产密集型行业。",
    when_not_to_use="不适合账面价值为负的企业。不适合轻资产高无形资产企业（估值偏差较大）。",
    returns="返回 JSON 字符串，包含每股净资产、ROE、股权成本、剩余收益序列和内在价值。",
    example="get_residual_income_valuation(symbol='600519')",
    related_tools=["get_dcf_valuation", "get_wacc_calculation"],
)
def get_residual_income_valuation(
    symbol: Annotated[str, "A 股股票代码，如 600519"],
    growth_years: Annotated[int, "预测期年数，默认 5"] = 5,
    terminal_growth: Annotated[float, "终值增长率，默认 3%"] = 0.03,
    cost_of_equity: Annotated[Optional[float], "股权成本，默认 None 自动估算"] = None,
) -> str:
    """剩余收益估值模型：RI_t = (ROE_t - r_e) × BV_{t-1}

    Args:
        symbol: A 股股票代码，如 600519
        growth_years: 预测期年数，默认 5，自动夹钳到 [3, 15]
        terminal_growth: 终值增长率（小数形式），默认 0.03
        cost_of_equity: 股权成本（小数形式），默认 None 时使用 0.035 + 1.0 × 0.06 自动估算

    Returns:
        str: JSON 字符串，包含以下可能结构——

        错误情形返回 dict，字段：
            status: "error"
            message: 错误描述
            symbol: 股票代码

        成功情形返回 dict，字段：
            symbol: 股票代码
            method: "residual_income_model"
            parameters: 参数 dict —
                book_value_per_share: 每股净资产
                roe: 最新 ROE（小数）
                cost_of_equity: 股权成本（小数）
                forecast_years: 预测期年数
                terminal_growth: 终值增长率（小数）
            valuation: 估值结果 dict —
                current_book_value_per_share: 当前每股净资产
                cumulative_pv_ri: 预测期剩余收益现值合计
                pv_terminal_ri: 终值剩余收益现值
                intrinsic_value: 内在价值
                current_price: 当前股价
                upside_pct: 相对当前价格的上行空间百分比
            residual_income_stream: 各期剩余收益流列表 [{"year": ..., "roe": ..., "book_value_per_share": ..., "residual_income_per_share": ..., "pv_residual_income": ...}, ...]
            data_quality: 数据质量 dict —
                years_available: 可用年报期数
                roe_source: ROE 来源："latest_roe" | "estimated"
                cost_of_equity_source: 股权成本来源："parameter_override" | "auto_estimated"
                warnings: 警告信息列表

        异常时返回 dict：{"status": "error", "message": ...}
    """
    try:
        from core.skill_runtime.data_access import get_latest_stock_price, get_stock_basic_info, get_stock_financial_periods
        from core.skill_runtime.standard_financial_apis import get_historical_financial_annual_series

        series = get_historical_financial_annual_series(symbol, years=5)
        records = series.get("records") or []

        if len(records) < 2:
            return json.dumps(
                {"status": "error", "message": f"可用年报数据不足（仅 {len(records)} 期），无法进行剩余收益估值", "symbol": symbol},
                ensure_ascii=False, indent=2, default=str,
            )

        warnings: list = []
        latest = records[0]
        bvps = _safe_div(latest.get("total_equity"), None)
        roe = latest.get("roe")
        current_price = get_latest_stock_price(symbol)

        # 获取总股本
        basic_info = get_stock_basic_info(symbol) or {}
        shares = _resolve_shares(basic_info, current_price, warnings)

        total_equity = latest.get("total_equity")
        if total_equity is None or total_equity <= 0 or shares is None or shares <= 0:
            return json.dumps(
                {"status": "error", "message": f"净资产数据无效（equity={total_equity}, shares={shares}），无法估值", "symbol": symbol},
                ensure_ascii=False, indent=2, default=str,
            )

        bvps = total_equity / shares

        if roe is None or roe <= 0:
            # 从记录中推算 ROE
            net_profit = latest.get("net_profit")
            if net_profit and total_equity > 0:
                roe = net_profit / total_equity
            else:
                roe = 0.08
                warnings.append(f"ROE 数据缺失，默认使用 8% 估算。")

        # 股权成本
        if cost_of_equity is not None:
            re = cost_of_equity
            re_source = "parameter_override"
        else:
            re = 0.035 + 1.0 * 0.06  # Rf + beta * ERP
            re_source = "auto_estimated"

        n_years = max(3, min(15, int(growth_years)))
        tg = terminal_growth

        # 估算各期 ROE（假设线性回归至行业均值）
        roe_start = roe
        roe_end = 0.10  # 假设长期回归至 10%
        ri_stream = []
        prev_bv = bvps
        cumulative_ri_pv = 0

        for yr in range(1, n_years + 1):
            decay = yr / n_years
            roe_t = roe_start * (1 - decay) + roe_end * decay
            ri_t = (roe_t - re) * prev_bv
            pv_ri = ri_t / (1 + re) ** yr
            ri_stream.append({
                "year": yr,
                "roe": round(roe_t, 4),
                "book_value_per_share": round(prev_bv, 4),
                "residual_income_per_share": round(ri_t, 4),
                "pv_residual_income": round(pv_ri, 4),
            })
            cumulative_ri_pv += pv_ri
            # 更新 BV: 假设股利支付率 = 1 - g/ROE
            implied_payout = 1 - tg / roe_t if roe_t > 0 else 0.6
            implied_payout = max(0, min(1, implied_payout))
            retention = 1 - implied_payout
            prev_bv = prev_bv + ri_t + roe_t * prev_bv * (1 - retention)  # 简化BV演进

        # 终值
        last_ri = ri_stream[-1]["residual_income_per_share"] if ri_stream else 0
        pv_terminal_ri = (last_ri * (1 + tg) / (re - tg)) / (1 + re) ** n_years if re > tg else 0

        intrinsic_value = bvps + cumulative_ri_pv + pv_terminal_ri
        upside_pct = ((intrinsic_value - current_price) / current_price * 100) if (current_price and current_price > 0) else None

        payload = {
            "symbol": symbol,
            "method": "residual_income_model",
            "parameters": {
                "book_value_per_share": round(bvps, 4),
                "roe": round(roe, 4),
                "cost_of_equity": round(re, 4),
                "forecast_years": n_years,
                "terminal_growth": round(tg, 4),
            },
            "valuation": {
                "current_book_value_per_share": round(bvps, 2),
                "cumulative_pv_ri": round(cumulative_ri_pv, 2),
                "pv_terminal_ri": round(pv_terminal_ri, 2),
                "intrinsic_value": round(intrinsic_value, 2),
                "current_price": current_price,
                "upside_pct": round(upside_pct, 2) if upside_pct is not None else None,
            },
            "residual_income_stream": ri_stream,
            "data_quality": {
                "years_available": len(records),
                "roe_source": "latest_roe" if roe == latest.get("roe") else "estimated",
                "cost_of_equity_source": re_source,
                "warnings": warnings,
            },
        }
        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    except Exception as exc:
        logger.error("剩余收益估值失败: %s", exc, exc_info=True)
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2, default=str)


# ─────────────────────────────────────────────────────────────
# Tool 4: EVA 估值
# ─────────────────────────────────────────────────────────────


@tool
@register_tool(
    tool_id="get_eva_valuation",
    name="EVA 估值",
    description="基于 EVA 模型计算 A 股经济利润以反映价值创造能力，返回 NOPAT、资本占用、WACC、EVA 序列和价值创造评估",
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["valuation", "eva", "economic_value_added", "value_creation"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["economic_profit_analysis", "value_creation_assessment"],
    when_to_use="当需要评估企业真实经济利润（超过资本成本的价值创造）时使用。适合资本密集型企业。",
    when_not_to_use="不适合没有有效财务数据的企业。EVA 为正不意味着股价低估，需结合其他估值方法。",
    returns="返回 JSON 字符串，包含 NOPAT、WACC、投入资本、EVA 值、EVA 利差及多期趋势。",
    example="get_eva_valuation(symbol='600519')",
    related_tools=["get_wacc_calculation", "get_dcf_valuation"],
)
def get_eva_valuation(
    symbol: Annotated[str, "A 股股票代码，如 600519"],
    tax_rate: Annotated[float, "企业所得税率，默认 25%"] = 0.25,
) -> str:
    """EVA 估值：EVA = NOPAT - WACC × Invested_Capital

    Args:
        symbol: A 股股票代码，如 600519
        tax_rate: 企业所得税率（小数形式），默认 0.25，自动夹钳到 [0, 0.5]

    Returns:
        str: JSON 字符串，包含以下可能结构——

        错误情形返回 dict，字段：
            status: "error"
            message: 错误描述
            symbol: 股票代码

        成功情形返回 dict，字段：
            symbol: 股票代码
            method: "economic_value_added"
            current_eva: 最新期 EVA 指标 dict —
                nopat: 税后净营业利润
                wacc: 加权平均资本成本（小数）
                invested_capital: 投入资本
                eva_value: EVA 值
                eva_spread: EVA 利差（EVA / 投入资本）
            trend: 多期 EVA 趋势列表 [{"year": ..., "nopat": ..., "wacc": ..., "invested_capital": ..., "eva": ..., "eva_spread": ...}, ...]
            current_price: 当前股价
            data_quality: 数据质量 dict —
                years_available: 可用年报期数
                warnings: 警告信息列表

        异常时返回 dict：{"status": "error", "message": ...}
    """
    try:
        from core.skill_runtime.data_access import get_stock_financial_periods, get_latest_stock_price, get_stock_basic_info
        from core.skill_runtime.standard_financial_apis import get_historical_financial_annual_series

        series = get_historical_financial_annual_series(symbol, years=5)
        records = series.get("records") or []

        if len(records) < 2:
            return json.dumps(
                {"status": "error", "message": f"可用年报数据不足（仅 {len(records)} 期），无法进行 EVA 估值", "symbol": symbol},
                ensure_ascii=False, indent=2, default=str,
            )

        warnings: list = []
        trend = []
        tax = max(0, min(0.5, tax_rate))

        # 计算 WACC
        rf = 0.025
        erp = 0.06
        cost_of_equity = rf + 1.0 * erp
        cost_of_debt = 0.04

        for item in records:
            nopat = _safe_div(item.get("oper_profit") or item.get("operating_profit"), None)
            if nopat is None:
                nopat = _safe_div(item.get("net_profit"), None)
                if nopat is not None:
                    nopat = nopat * (1 + tax / (1 - tax)) if tax < 1 else nopat * 1.33
            else:
                nopat = nopat * (1 - tax)

            total_liab = item.get("total_liab") or 0
            total_equity = item.get("total_equity") or 0
            money_cap = item.get("money_cap") or 0
            invested_capital = total_equity + total_liab - money_cap

            if invested_capital <= 0:
                invested_capital = total_equity + total_liab

            # WACC
            debt_to_assets = item.get("debt_to_assets")
            if debt_to_assets is not None:
                debt_w = debt_to_assets / 100.0 if debt_to_assets > 1 else debt_to_assets
            else:
                debt_w = _safe_div(total_liab, total_liab + total_equity) if (total_liab + total_equity) > 0 else 0.4
            debt_w = max(0, min(1, debt_w if debt_w else 0.4))
            eq_w = 1.0 - debt_w
            wacc_val = eq_w * cost_of_equity + debt_w * cost_of_debt * (1 - tax)

            eva_val = nopat - wacc_val * invested_capital if nopat is not None else None
            eva_spread = _safe_div(eva_val, invested_capital)

            trend.append({
                "year": item.get("year"),
                "nopat": round(nopat, 2) if nopat is not None else None,
                "wacc": round(wacc_val, 4),
                "invested_capital": round(invested_capital, 2),
                "eva": round(eva_val, 2) if eva_val is not None else None,
                "eva_spread": round(eva_spread, 4) if eva_spread is not None else None,
            })

        latest_trend = trend[0] if trend else {}
        current_price = get_latest_stock_price(symbol)

        payload = {
            "symbol": symbol,
            "method": "economic_value_added",
            "current_eva": {
                "nopat": latest_trend.get("nopat"),
                "wacc": latest_trend.get("wacc"),
                "invested_capital": latest_trend.get("invested_capital"),
                "eva_value": latest_trend.get("eva"),
                "eva_spread": latest_trend.get("eva_spread"),
            },
            "trend": trend,
            "current_price": current_price,
            "data_quality": {
                "years_available": len(records),
                "warnings": warnings,
            },
        }
        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    except Exception as exc:
        logger.error("EVA估值失败: %s", exc, exc_info=True)
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2, default=str)


# ─────────────────────────────────────────────────────────────
# Tool 5: FCFF / FCFE 自由现金流计算
# ─────────────────────────────────────────────────────────────


@tool
@register_tool(
    tool_id="get_fcff_fcfe_calculation",
    name="自由现金流计算",
    description="计算公司自由现金流 FCFF 和股权自由现金流 FCFE，返回 EBIT、税率、NOPAT、资本支出、营运资本变化及多期序列",
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["valuation", "fcff", "fcfe", "free_cashflow", "cashflow_analysis"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["free_cashflow_analysis", "dcf_input_preparation"],
    when_to_use="当需要获取 FCFF/FCFE 及其各组成部分的详细分解和多期趋势时使用。",
    when_not_to_use="不适合没有详细现金流数据的企业。",
    returns="返回 JSON 字符串，包含 FCFF、FCFE 及其各组成部分的多期趋势。",
    example="get_fcff_fcfe_calculation(symbol='600519')",
    related_tools=["get_dcf_valuation", "get_cashflow_quality_trend"],
)
def get_fcff_fcfe_calculation(
    symbol: Annotated[str, "A 股股票代码，如 600519"],
    tax_rate: Annotated[float, "企业所得税率，默认 25%"] = 0.25,
) -> str:
    """计算 FCFF = NOPAT + D&A - CapEx - ΔWC 和 FCFE = FCFF - Interest×(1-t) + NetBorrowing

    Args:
        symbol: A 股股票代码，如 600519
        tax_rate: 企业所得税率（小数形式），默认 0.25，自动夹钳到 [0, 0.5]

    Returns:
        str: JSON 字符串，包含以下可能结构——

        错误情形返回 dict，字段：
            status: "error"
            message: 错误描述
            symbol: 股票代码

        成功情形返回 dict，字段：
            symbol: 股票代码
            method: "FCFF/FCFE计算"
            latest: 最新一期数据 dict —
                fcff: 公司自由现金流
                fcfe: 股权自由现金流
                components: FCFF/FCFE 组成 dict —
                    nopat: 税后净营业利润
                    depreciation_amortization: 折旧摊销估算
                    capex: 资本支出
                    delta_working_capital: 营运资本变动
                    interest_expense: 利息费用
                    net_borrowing: 净新增借款
            trend: 多期趋势列表 [{"year": ..., "nopat": ..., "depreciation_amortization": ..., "capex": ..., "delta_working_capital": ..., "fcff": ..., "interest_expense": ..., "net_borrowing": ..., "fcfe": ...}, ...]
            data_quality: 数据质量 dict —
                years_available: 可用年报期数
                da_source: 折旧摊销来源（"estimated_percent_of_revenue"）
                capex_source: 资本支出来源（"delta_fixed_assets_plus_da"）
                warnings: 警告信息列表

        异常时返回 dict：{"status": "error", "message": ...}
    """
    try:
        from core.skill_runtime.data_access import get_stock_financial_periods
        from core.skill_runtime.standard_financial_apis import get_historical_financial_annual_series

        series = get_historical_financial_annual_series(symbol, years=5)
        records = series.get("records") or []

        if len(records) < 2:
            return json.dumps(
                {"status": "error", "message": f"可用年报数据不足（仅 {len(records)} 期），无法计算 FCFF/FCFE", "symbol": symbol},
                ensure_ascii=False, indent=2, default=str,
            )

        tax = max(0, min(0.5, tax_rate))
        raw_periods = get_stock_financial_periods(symbol, limit=max(len(records) + 2, 10))

        # 🔑 按年份分组时，同一年优先取年报（12-31 结束），避免季报累计值被当作年报
        from core.tools.implementations.risk.extended_risk_models import (
            _detect_period_type, _PERIOD_LABELS,
        )
        period_by_year = {}
        for p in raw_periods:
            yr = p.get("report_period") or p.get("report_date") or ""
            y = str(yr)[:4] if yr else ""
            if y.isdigit():
                year_int = int(y)
                p_type = _detect_period_type(p)
                # 同一年份已有数据时，优先保留口径更大的
                if year_int not in period_by_year:
                    period_by_year[year_int] = p
                else:
                    priority = {"annual": 4, "q3": 3, "h1": 2, "q1": 1, "unknown": 0}
                    existing_type = _detect_period_type(period_by_year[year_int])
                    if priority.get(p_type, 0) > priority.get(existing_type, 0):
                        period_by_year[year_int] = p

        warnings: list = []
        trend = []
        prev_wc = None

        for item in records:
            year = item.get("year")
            revenue = item.get("revenue")
            oper_profit = item.get("oper_profit") or item.get("operating_profit")
            net_profit = item.get("net_profit")
            ocf = item.get("operating_cashflow")

            # NOPAT = oper_profit × (1 - tax)
            nopat = oper_profit * (1 - tax) if oper_profit is not None else None
            if nopat is None and net_profit is not None:
                nopat = net_profit * (1 + tax / (1 - tax)) * (1 - tax) if tax < 1 else net_profit

            # D&A 估算：revenue 的 3%（典型制造业/服务业水平）
            da_estimate = revenue * 0.03 if revenue is not None else 0

            # CapEx = Δ(fix_assets) + D&A（近似）
            cur_fa = item.get("fix_assets") or 0
            # 找到前一期
            prev_fa = None
            for r in records:
                if r.get("year") == year - 1:
                    prev_fa = r.get("fix_assets") or 0
                    break
            if prev_fa is None:
                prev_fa = cur_fa
            delta_fa = cur_fa - prev_fa
            capex = delta_fa + da_estimate if delta_fa >= 0 else da_estimate
            # 如果 capex 为负或异常，使用 OCF 的 30% 作为估算
            if capex < 0 and ocf is not None and ocf > 0:
                capex = ocf * 0.3
                warnings.append(f"{year}年固定资产减少，CapEx 按 OCF 的 30% 估算")

            # ΔWorkingCapital
            cur_ca = item.get("total_cur_assets") or 0
            cur_cl = item.get("total_cur_liab") or 0
            wc = cur_ca - cur_cl
            if prev_wc is not None:
                delta_wc = wc - prev_wc
            else:
                delta_wc = 0
            prev_wc = wc

            # FCFF
            if nopat is not None:
                fcff = nopat + da_estimate - capex - delta_wc
            else:
                fcff = ocf - capex - delta_wc if ocf is not None else None

            # FCFE
            interest = item.get("fin_exp") or 0
            net_borrowing = 0  # 简化处理
            fcfe = fcff - interest * (1 - tax) + net_borrowing if fcff is not None else None

            trend.append({
                "year": year,
                "nopat": round(nopat, 2) if nopat is not None else None,
                "depreciation_amortization": round(da_estimate, 2),
                "capex": round(capex, 2),
                "delta_working_capital": round(delta_wc, 2),
                "fcff": round(fcff, 2) if fcff is not None else None,
                "interest_expense": round(interest, 2),
                "net_borrowing": net_borrowing,
                "fcfe": round(fcfe, 2) if fcfe is not None else None,
            })

        latest = trend[0] if trend else {}

        payload = {
            "symbol": symbol,
            "method": "FCFF/FCFE计算",
            "latest": {
                "fcff": latest.get("fcff"),
                "fcfe": latest.get("fcfe"),
                "components": {
                    "nopat": latest.get("nopat"),
                    "depreciation_amortization": latest.get("depreciation_amortization"),
                    "capex": latest.get("capex"),
                    "delta_working_capital": latest.get("delta_working_capital"),
                    "interest_expense": latest.get("interest_expense"),
                    "net_borrowing": latest.get("net_borrowing"),
                },
            },
            "trend": trend,
            "data_quality": {
                "years_available": len(records),
                "da_source": "estimated_percent_of_revenue",
                "capex_source": "delta_fixed_assets_plus_da",
                "warnings": warnings,
            },
        }
        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    except Exception as exc:
        logger.error("FCFF/FCFE计算失败: %s", exc, exc_info=True)
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2, default=str)


# ─────────────────────────────────────────────────────────────
# Tool 6: PEG 估值
# ─────────────────────────────────────────────────────────────


@tool
@register_tool(
    tool_id="get_peg_valuation",
    name="PEG 估值",
    description="基于 PEG 指标评估 A 股成长股估值合理性，返回 PE、3 年净利润 CAGR、PEG 比率、估值判断和行业对比，适用于成长股",
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["valuation", "peg", "growth_valuation", "relative_valuation"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["growth_stock_valuation", "peg_analysis"],
    when_to_use="适用于有正盈利和明确增长趋势的企业，用于判断成长股的估值合理性。PEG < 1 通常表示低估。",
    when_not_to_use="不适合净利润为负的公司（PE 无法计算）。不适合增长波动极大的企业（CAGR 失真）。",
    returns="返回 JSON 字符串，包含 PE、3 年净利润 CAGR、PEG 比率和评估结论。",
    example="get_peg_valuation(symbol='600519')",
    related_tools=["get_comparable_company_valuation", "get_growth_quality_metrics"],
)
def get_peg_valuation(
    symbol: Annotated[str, "A 股股票代码，如 600519"],
) -> str:
    """PEG = PE / Earnings_Growth_Rate

    Args:
        symbol: A 股股票代码，如 600519

    Returns:
        str: JSON 字符串，包含以下可能结构——

        错误情形返回 dict，字段：
            status: "error"
            message: 错误描述
            symbol: 股票代码

        成功情形返回 dict，字段：
            symbol: 股票代码
            method: "peg_valuation"
            parameters: 参数 dict —
                pe_ttm: 滚动市盈率
                growth_rate_3y_cagr: 3 年净利润 CAGR（小数），无法计算时为 None
                peg_ratio: PEG 比率，无法计算时为 None
            valuation: 估值结论 dict —
                assessment: 评估结论："低估" | "合理" | "高估" | "无法评估（增长率不足或为负）"
                current_price: 当前股价
            data_quality: 数据质量 dict —
                years_of_profit_data: 正利润数据期数
                warnings: 警告信息列表

        异常时返回 dict：{"status": "error", "message": ...}
    """
    try:
        from core.skill_runtime.data_access import get_stock_basic_info, get_latest_stock_price
        from core.skill_runtime.standard_financial_apis import get_historical_financial_annual_series

        basic_info = get_stock_basic_info(symbol) or {}
        pe_ttm = basic_info.get("pe_ttm") or basic_info.get("pe")
        current_price = get_latest_stock_price(symbol)

        if pe_ttm is None or pe_ttm <= 0:
            return json.dumps(
                {"status": "error", "message": f"无法获取 {symbol} 的有效 PE（市盈率），可能净利润为负", "symbol": symbol},
                ensure_ascii=False, indent=2, default=str,
            )

        # 获取 3 年净利润 CAGR
        series = get_historical_financial_annual_series(symbol, years=5)
        records = series.get("records") or []
        profit_values = [r.get("net_profit") for r in records if r.get("net_profit") is not None and r.get("net_profit") > 0]

        assessment = None
        growth_rate_3y_cagr = None

        if len(profit_values) >= 3:
            latest_p = profit_values[0]
            earliest_p = profit_values[min(2, len(profit_values) - 1)]
            periods = min(2, len(profit_values) - 1)
            growth_rate_3y_cagr = _cagr(latest_p, earliest_p, periods)
        elif len(profit_values) >= 2:
            latest_p = profit_values[0]
            earliest_p = profit_values[-1]
            periods = len(profit_values) - 1
            growth_rate_3y_cagr = _cagr(latest_p, earliest_p, periods)

        if growth_rate_3y_cagr is not None and growth_rate_3y_cagr > 0:
            peg_ratio = pe_ttm / (growth_rate_3y_cagr * 100)
        else:
            peg_ratio = None

        if peg_ratio is not None:
            if peg_ratio < 1:
                assessment = "低估"
            elif peg_ratio <= 2:
                assessment = "合理"
            else:
                assessment = "高估"
        else:
            assessment = "无法评估（增长率不足或为负）"

        payload = {
            "symbol": symbol,
            "method": "peg_valuation",
            "parameters": {
                "pe_ttm": round(pe_ttm, 2) if pe_ttm else None,
                "growth_rate_3y_cagr": round(growth_rate_3y_cagr, 4) if growth_rate_3y_cagr is not None else None,
                "peg_ratio": round(peg_ratio, 2) if peg_ratio is not None else None,
            },
            "valuation": {
                "assessment": assessment,
                "current_price": current_price,
            },
            "data_quality": {
                "years_of_profit_data": len(profit_values),
                "warnings": [] if growth_rate_3y_cagr else ["净利润 CAGR 无法计算，请检查盈利数据是否充足"],
            },
        }
        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    except Exception as exc:
        logger.error("PEG估值失败: %s", exc, exc_info=True)
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2, default=str)


# ─────────────────────────────────────────────────────────────
# Tool 7: 格雷厄姆估值
# ─────────────────────────────────────────────────────────────


@tool
@register_tool(
    tool_id="get_graham_valuation",
    name="格雷厄姆估值",
    description="基于格雷厄姆公式计算 A 股内在价值与安全边际，返回 EPS、账面价值、格雷厄姆数、当前股价、上涨空间和安全边际百分比，适合价值投资",
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["valuation", "graham", "value_investing", "absolute_valuation", "safety_margin"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["value_investing_analysis", "safety_margin_calculation"],
    when_to_use="适用于寻找价值型股票的投资者，判断股价相对于格雷厄姆数的安全边际。适合有稳定盈利和净资产的企业。",
    when_not_to_use="不适合高成长但盈利为负的企业。格雷厄姆数对轻资产高科技公司可能过于保守。",
    returns="返回 JSON 字符串，包含 EPS、BVPS、格雷厄姆数、当前价格、上涨空间和安全边际。",
    example="get_graham_valuation(symbol='600519')",
    related_tools=["get_dcf_valuation", "get_comparable_company_valuation", "get_graham_screen"],
)
def get_graham_valuation(
    symbol: Annotated[str, "A 股股票代码，如 600519"],
) -> str:
    """Graham Number = √(22.5 × EPS × BVPS)

    Args:
        symbol: A 股股票代码，如 600519

    Returns:
        str: JSON 字符串，包含以下可能结构——

        错误情形返回 dict，字段：
            status: "error"
            message: 错误描述
            symbol: 股票代码

        成功情形返回 dict，字段：
            symbol: 股票代码
            method: "格雷厄姆估值"
            parameters: 参数 dict —
                eps: 每股收益
                bvps: 每股净资产
                graham_number: 格雷厄姆数
            valuation: 估值结果 dict —
                graham_number: 格雷厄姆数
                current_price: 当前股价
                upside_pct: 相对当前价格的上行空间百分比
                safety_margin: 安全边际百分比
                safety_margin_level: 安全边际等级："高安全边际" | "中等安全边际" | "低安全边际" | "无安全边际"
            data_quality: 数据质量 dict —
                shares_source: 股本来源："basic_info" | "estimated"
                warnings: 警告信息列表

        异常时返回 dict：{"status": "error", "message": ...}
    """
    try:
        from core.skill_runtime.data_access import get_latest_stock_price, get_stock_basic_info, get_stock_financial_periods
        from core.skill_runtime.standard_financial_apis import get_historical_financial_annual_series

        basic_info = get_stock_basic_info(symbol) or {}
        current_price = get_latest_stock_price(symbol)

        series = get_historical_financial_annual_series(symbol, years=3)
        records = series.get("records") or []

        if not records:
            return json.dumps(
                {"status": "error", "message": f"未获取到 {symbol} 的年报数据", "symbol": symbol},
                ensure_ascii=False, indent=2, default=str,
            )

        warnings: list = []
        latest = records[0]

        # 获取总股本
        shares = _resolve_shares(basic_info, current_price, warnings)

        # EPS
        net_profit = latest.get("net_profit")
        eps = _safe_div(net_profit, shares)

        # BVPS
        total_equity = latest.get("total_equity")
        bvps = _safe_div(total_equity, shares)

        if eps is None or eps <= 0 or bvps is None or bvps <= 0:
            return json.dumps(
                {
                    "status": "error",
                    "message": f"EPS={eps}, BVPS={bvps}，EPS 或 BVPS 无效（可能净利润为负或净资产为负），无法计算格雷厄姆数",
                    "symbol": symbol,
                },
                ensure_ascii=False, indent=2, default=str,
            )

        graham_number = (22.5 * eps * bvps) ** 0.5
        upside_pct = ((graham_number - current_price) / current_price * 100) if (current_price and current_price > 0) else None
        safety_margin = ((graham_number - current_price) / graham_number * 100) if (graham_number and graham_number > 0 and current_price and current_price > 0) else None

        if safety_margin is not None:
            if safety_margin > 30:
                margin_level = "高安全边际"
            elif safety_margin > 15:
                margin_level = "中等安全边际"
            elif safety_margin > 0:
                margin_level = "低安全边际"
            else:
                margin_level = "无安全边际"
        else:
            margin_level = None

        payload = {
            "symbol": symbol,
            "method": "格雷厄姆估值",
            "parameters": {
                "eps": round(eps, 4),
                "bvps": round(bvps, 4),
                "graham_number": round(graham_number, 2),
            },
            "valuation": {
                "graham_number": round(graham_number, 2),
                "current_price": current_price,
                "upside_pct": round(upside_pct, 2) if upside_pct is not None else None,
                "safety_margin": round(safety_margin, 2) if safety_margin is not None else None,
                "safety_margin_level": margin_level,
            },
            "data_quality": {
                "shares_source": "basic_info" if (basic_info.get("total_shares") or basic_info.get("total_share")) else "estimated",
                "warnings": warnings,
            },
        }
        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    except Exception as exc:
        logger.error("格雷厄姆估值失败: %s", exc, exc_info=True)
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2, default=str)


# ─────────────────────────────────────────────────────────────
# Tool 8: CAPM 股权成本
# ─────────────────────────────────────────────────────────────


@tool
@register_tool(
    tool_id="get_capm_cost_of_equity",
    name="CAPM 股权成本",
    description="基于资本资产定价模型（CAPM）计算 A 股的股权资本成本，返回无风险利率、Beta、市场风险溢价、股权成本率等",
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["valuation", "capm", "cost_of_equity", "discount_rate"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["cost_of_equity_calculation", "capm_analysis"],
    when_to_use="当需要估算股权资本成本、为 DCF 或剩余收益模型提供折现率参数时使用。",
    when_not_to_use="不适合无 Beta 数据的新上市企业（少于 60 个交易日）。不适合非 A 股标的。",
    returns="返回 JSON 字符串，包含股权成本、Beta、无风险利率、股权风险溢价及各组成部分。",
    example="get_capm_cost_of_equity(symbol='600519')",
    related_tools=["get_wacc_calculation", "get_beta_calculation", "get_residual_income_valuation"],
)
def get_capm_cost_of_equity(
    symbol: Annotated[str, "A 股股票代码，如 600519"],
    risk_free_rate: Annotated[float, "无风险利率（10 年期国债收益率），默认 2.5%"] = 0.025,
    equity_risk_premium: Annotated[float, "股权风险溢价，默认 6%"] = 0.06,
) -> str:
    """CAPM = Rf + β × ERP

    Args:
        symbol: A 股股票代码，如 600519
        risk_free_rate: 无风险利率（小数形式，如 0.025 表示 2.5%），默认 0.025
        equity_risk_premium: 股权风险溢价（小数形式），默认 0.06

    Returns:
        str: JSON 字符串，包含以下可能结构——

        错误情形返回 dict，字段：
            status: "error"
            message: 错误描述

        成功情形返回 dict，字段：
            symbol: 股票代码
            method: "capm"
            parameters: 参数 dict —
                risk_free_rate: 无风险利率（小数）
                beta: Beta 系数
                equity_risk_premium: 股权风险溢价（小数）
            cost_of_equity: 股权成本（小数）
            components: 各组成部分 dict —
                risk_free_rate: dict — value: 无风险利率值, description: 描述
                beta: dict — value: Beta 值, source: Beta 来源："default" | "price_returns_estimated"
                equity_risk_premium: dict — value: ERP 值, description: 描述
            formula: 公式文本 "cost_of_equity = Rf + β × ERP"
            calculation: 计算过程文本
            data_quality: 数据质量 dict —
                beta_source: Beta 来源："default" | "price_returns_estimated"
                warnings: 警告信息列表

        异常时返回 dict：{"status": "error", "message": ...}
    """
    try:
        from core.skill_runtime.data_access import get_stock_daily_quotes
        from core.skill_runtime.standard_financial_apis import get_security_master
        import datetime

        rf = risk_free_rate if risk_free_rate is not None else 0.025
        erp = equity_risk_premium if equity_risk_premium is not None else 0.06
        warnings: list = []

        # 计算 Beta
        beta = 1.0
        beta_source = "default"
        try:
            end = datetime.date.today().isoformat()
            start = (datetime.date.today() - datetime.timedelta(days=365)).isoformat()
            quotes = get_stock_daily_quotes(symbol, start_date=start, end_date=end, limit=250)
            if quotes and len(quotes) >= 60:
                closes = []
                for q in quotes:
                    c = q.get("close")
                    if c is not None and isinstance(c, (int, float)) and c > 0:
                        closes.append(float(c))
                if len(closes) >= 60:
                    returns = []
                    for i in range(1, len(closes)):
                        if closes[i - 1] > 0:
                            returns.append((closes[i] - closes[i - 1]) / closes[i - 1])
                    if len(returns) >= 60:
                        var_ret = np.var(returns)
                        if var_ret > 0:
                            beta = max(0.2, min(2.5, np.sqrt(var_ret) / 0.015))
                            beta_source = "price_returns_estimated"
        except Exception as e:
            warnings.append(f"Beta 计算失败，使用默认值 1.0: {e}")

        cost_of_equity = rf + beta * erp

        master = get_security_master(symbol)

        payload = {
            "symbol": symbol,
            "method": "capm",
            "parameters": {
                "risk_free_rate": round(rf, 4),
                "beta": round(beta, 4),
                "equity_risk_premium": round(erp, 4),
            },
            "cost_of_equity": round(cost_of_equity, 4),
            "components": {
                "risk_free_rate": {
                    "value": round(rf, 4),
                    "description": "10 年期中国国债收益率（近似值）",
                },
                "beta": {
                    "value": round(beta, 4),
                    "source": beta_source,
                },
                "equity_risk_premium": {
                    "value": round(erp, 4),
                    "description": "中国股权市场风险溢价（近似值）",
                },
            },
            "formula": "cost_of_equity = Rf + β × ERP",
            "calculation": f"{rf:.4f} + {beta:.4f} × {erp:.4f} = {cost_of_equity:.4f}",
            "data_quality": {
                "beta_source": beta_source,
                "warnings": warnings,
            },
        }
        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    except Exception as exc:
        logger.error("CAPM股权成本计算失败: %s", exc, exc_info=True)
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2, default=str)


# ─────────────────────────────────────────────────────────────
# Tool 9: 增长质量调整估值
# ─────────────────────────────────────────────────────────────


@tool
@register_tool(
    tool_id="get_growth_adjusted_valuation",
    name="增长质量调整估值",
    description="基于增长质量评分（营收稳健性、ROIC、现金流质量）调整 PE 估值，返回质量评分、调整后 PE、合理估值区间和调整因子明细",
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["valuation", "growth_quality", "quality_adjusted", "adjusted_pe"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["growth_quality_analysis", "quality_adjusted_valuation"],
    when_to_use="当需要判断高增长是否具有可持续性，以及当前 PE 是否合理反映增长质量时使用。",
    when_not_to_use="不适合净利润为负导致 PE 无效的企业。不适合数据不足 3 年的企业。",
    returns="返回 JSON 字符串，包含原始 PE、增长质量评分、调整后 PE、公允价值和评估方法。",
    example="get_growth_adjusted_valuation(symbol='600519')",
    related_tools=["get_peg_valuation", "get_growth_quality_metrics", "get_cashflow_quality_trend"],
)
def get_growth_adjusted_valuation(
    symbol: Annotated[str, "A 股股票代码，如 600519"],
) -> str:
    """基于增长质量评分调整 PE

    Args:
        symbol: A 股股票代码，如 600519

    Returns:
        str: JSON 字符串，包含以下可能结构——

        错误情形返回 dict，字段：
            status: "error"
            message: 错误描述
            symbol: 股票代码

        成功情形返回 dict，字段：
            symbol: 股票代码
            method: "增长质量调整估值"
            parameters: 参数 dict —
                raw_pe_ttm: 原始滚动市盈率
            growth_quality: 增长质量评分 dict —
                total_score: 综合评分（0-100）
                quality_label: 质量标签："优秀" | "良好" | "一般" | "较差" | "差"
                components: 评分组成 dict —
                    revenue_consistency: 营收一致性评分
                    roic_sustainability: ROIC 可持续性评分
                    cashflow_quality: 现金流质量评分
                detail: 评分明细 dict —
                    revenue_growth_std: 营收增长率标准差（数据不足时为 None）
                    mean_roe: ROE 均值（数据不足时为 None）
                    mean_ocf_to_net_profit: OCF/净利润 均值（数据不足时为 None）
            valuation: 估值结果 dict —
                pe_adjustment_factor: PE 调整因子
                adjusted_pe: 调整后 PE
                industry_median_pe: 行业中位数 PE（缺失时为 None）
                fair_pe: 公允 PE
                fair_value: 公允价值（EPS 不可计算时为 None）
                current_price: 当前股价
            methodology: 方法论文本
            data_quality: 数据质量 dict —
                industry: 所属行业
                years_available: 可用年报期数
                warnings: 警告信息列表

        异常时返回 dict：{"status": "error", "message": ...}
    """
    try:
        from core.skill_runtime.data_access import get_stock_basic_info, get_latest_stock_price
        from core.skill_runtime.standard_financial_apis import (
            get_growth_quality_metrics,
            get_cashflow_quality_trend,
            get_historical_financial_annual_series,
        )

        basic_info = get_stock_basic_info(symbol) or {}
        pe_ttm = basic_info.get("pe_ttm") or basic_info.get("pe")
        current_price = get_latest_stock_price(symbol)

        if pe_ttm is None or pe_ttm <= 0:
            return json.dumps(
                {"status": "error", "message": f"无法获取 {symbol} 的有效 PE，无法进行增长质量调整估值", "symbol": symbol},
                ensure_ascii=False, indent=2, default=str,
            )

        warnings: list = []

        # 1. 营收增长一致性评分
        growth_metrics = get_growth_quality_metrics(symbol, years=5)
        growth_records = growth_metrics.get("annual_growth") or []
        revenue_growth_rates = [g.get("revenue_growth") for g in growth_records if g.get("revenue_growth") is not None]

        if len(revenue_growth_rates) >= 3:
            std_rev_growth = pstdev(revenue_growth_rates) if len(revenue_growth_rates) > 1 else 0
            mean_rev_growth = mean(revenue_growth_rates)
            # 低波动 = 高评分 (std < 0.1 -> 满分)
            consistency_score = max(0, min(30, 30 * (1 - std_rev_growth / 0.3)))
            if mean_rev_growth <= 0:
                consistency_score *= 0.5
        else:
            consistency_score = 15
            warnings.append(f"营收增长率数据不足（{len(revenue_growth_rates)} 期），一致性评分采用默认值。")

        # 2. ROIC 可持续性评分
        series = get_historical_financial_annual_series(symbol, years=5)
        records = series.get("records") or []
        roe_values = [r.get("roe") for r in records if r.get("roe") is not None]

        if len(roe_values) >= 3:
            mean_roe = mean(roe_values)
            std_roe = pstdev(roe_values) if len(roe_values) > 1 else 0
            roe_score = min(30, (mean_roe * 100) * 2)  # ROE 越高分越高, 20% ROE -> 40 capped at 30
            roe_score = max(0, roe_score)
            # 稳定性因子
            if std_roe > 0.05:
                roe_score *= max(0.5, 1 - (std_roe - 0.05) / 0.1)
        else:
            roe_score = 15
            warnings.append(f"ROE 数据不足（{len(roe_values)} 期），可持续性评分采用默认值。")

        # 3. 现金流质量评分
        cf_quality = get_cashflow_quality_trend(symbol, years=5)
        cf_trend = cf_quality.get("trend") or []
        ocf_to_np_values = [c.get("ocf_to_net_profit") for c in cf_trend if c.get("ocf_to_net_profit") is not None]

        if ocf_to_np_values:
            mean_ocf_np = mean(ocf_to_np_values)
            # OCF/NP > 1.0 = 高质量（满分）, < 0.5 = 低质量
            if mean_ocf_np >= 1.0:
                cf_score = 40
            elif mean_ocf_np >= 0.7:
                cf_score = 30
            elif mean_ocf_np >= 0.5:
                cf_score = 20
            else:
                cf_score = max(0, mean_ocf_np * 40)
        else:
            cf_score = 20
            warnings.append("现金流质量数据不足，评分采用默认值。")

        # 总分 0-100
        quality_score = round(consistency_score + roe_score + cf_score, 1)
        quality_score = max(0, min(100, quality_score))

        # PE 调整
        if quality_score >= 80:
            pe_adjustment_factor = 1.3       # 高质量: +30% PE 溢价
            quality_label = "优秀"
        elif quality_score >= 60:
            pe_adjustment_factor = 1.15      # 良好: +15% 溢价
            quality_label = "良好"
        elif quality_score >= 40:
            pe_adjustment_factor = 1.0       # 一般: 无调整
            quality_label = "一般"
        elif quality_score >= 20:
            pe_adjustment_factor = 0.85      # 较差: -15% 折价
            quality_label = "较差"
        else:
            pe_adjustment_factor = 0.7       # 差: -30% 折价
            quality_label = "差"

        adjusted_pe = pe_ttm * pe_adjustment_factor

        # 公允价值估算：行业平均 PE × 质量调整因子
        # 使用行业平均 PE 作为参考基准
        from core.skill_runtime.data_access import summarize_industry_valuation

        master = series if isinstance(series, dict) else {}
        industry = None
        if isinstance(master, dict):
            from core.skill_runtime.standard_financial_apis import get_security_master
            sec_master = get_security_master(symbol)
            industry = sec_master.get("industry")

        industry_pe = None
        if industry:
            ind_stats = summarize_industry_valuation(industry, metric="pe", exclude_symbol=symbol)
            industry_pe = ind_stats.get("median")

        # 公允 PE = 行业中位数 PE × 质量调整因子
        fair_pe = industry_pe * pe_adjustment_factor if industry_pe and industry_pe > 0 else adjusted_pe

        # 从 EPS 推算公允价值
        eps = None
        if records:
            net_profit = records[0].get("net_profit")
            shares = _resolve_shares(basic_info, current_price)
            if net_profit and shares and shares > 0:
                eps = net_profit / shares

        fair_value = eps * fair_pe if eps is not None and fair_pe is not None else None

        payload = {
            "symbol": symbol,
            "method": "增长质量调整估值",
            "parameters": {
                "raw_pe_ttm": round(pe_ttm, 2) if pe_ttm else None,
            },
            "growth_quality": {
                "total_score": quality_score,
                "quality_label": quality_label,
                "components": {
                    "revenue_consistency": round(consistency_score, 1),
                    "roic_sustainability": round(roe_score, 1),
                    "cashflow_quality": round(cf_score, 1),
                },
                "detail": {
                    "revenue_growth_std": round(std_rev_growth, 4) if len(revenue_growth_rates) >= 3 else None,
                    "mean_roe": round(mean_roe, 4) if len(roe_values) >= 3 else None,
                    "mean_ocf_to_net_profit": round(mean_ocf_np, 4) if ocf_to_np_values else None,
                },
            },
            "valuation": {
                "pe_adjustment_factor": pe_adjustment_factor,
                "adjusted_pe": round(adjusted_pe, 2) if adjusted_pe else None,
                "industry_median_pe": round(industry_pe, 2) if industry_pe else None,
                "fair_pe": round(fair_pe, 2) if fair_pe else None,
                "fair_value": round(fair_value, 2) if fair_value is not None else None,
                "current_price": current_price,
            },
            "methodology": "基于营收增长一致性(30%)、ROIC可持续性(30%)、现金流质量(40%)综合评分调整PE",
            "data_quality": {
                "industry": industry,
                "years_available": len(records),
                "warnings": warnings,
            },
        }
        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    except Exception as exc:
        logger.error("增长质量调整估值失败: %s", exc, exc_info=True)
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2, default=str)


__all__ = [
    "get_dcf_three_stage_valuation",
    "get_ddm_valuation",
    "get_residual_income_valuation",
    "get_eva_valuation",
    "get_fcff_fcfe_calculation",
    "get_peg_valuation",
    "get_graham_valuation",
    "get_capm_cost_of_equity",
    "get_growth_adjusted_valuation",
]