"""DCF 两阶段估值模型工具"""

import json
import logging
from typing import Annotated, Optional

import numpy as np
from langchain_core.tools import tool

from core.tools.base import register_tool

logger = logging.getLogger(__name__)


@tool
@register_tool(
    tool_id="get_dcf_valuation",
    name="DCF 两阶段估值",
    description="基于两阶段 DCF 模型对 A 股绝对估值，返回内在价值、安全边际、各阶段现金流、WACC、终值等结构化结果，适用于成熟企业",
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["dcf", "valuation", "absolute_valuation", "discounted_cashflow", "two_stage_dcf"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["absolute_valuation", "intrinsic_value_estimation"],
    when_to_use="当需要进行绝对估值、估算内在价值、计算安全边际时使用。适用于有正自由现金流的成熟企业。",
    when_not_to_use="不适合 FCF 持续为负的企业（会返回错误）。不适合金融类企业（资产结构不同）。不适合相对估值场景（应使用 PE/PB 对比工具）。",
    returns="返回 JSON 字符串，包含估值参数、情景分析、敏感性矩阵和每股内在价值。",
    example="get_dcf_valuation(symbol='600519')",
    related_tools=["get_wacc_calculation", "get_dcf_three_stage_valuation", "get_fcff_fcfe_calculation", "get_capm_cost_of_equity"],
)
def get_dcf_valuation(
    symbol: Annotated[str, "A 股股票代码，如 600519"],
    growth_rate: Annotated[Optional[float], "预测期年化增长率，默认 None 由历史数据自动估算"] = None,
    wacc: Annotated[Optional[float], "折现率（加权平均资本成本），默认 None 自动计算"] = None,
    terminal_growth_rate: Annotated[float, "永续增长率，默认 2.5%"] = 2.5,
    forecast_years: Annotated[int, "预测期年数，默认 5"] = 5,
    base_fcf: Annotated[Optional[float], "基期自由现金流覆盖值，默认 None 使用最新年报数据"] = None,
) -> str:
    """DCF 两阶段估值模型

    Args:
        symbol: A 股股票代码，如 600519
        growth_rate: 预测期年化增长率（小数形式，如 0.15 表示 15%），默认 None 由历史营收数据自动估算并夹钳到 [0.03, 0.25]
        wacc: 折现率（加权平均资本成本，小数形式），默认 None 自动计算并夹钳到 [0.05, 0.20]
        terminal_growth_rate: 永续增长率，默认 2.5（>1 时视为百分比，自动除以 100）
        forecast_years: 预测期年数，默认 5，自动夹钳到 [3, 10]
        base_fcf: 基期自由现金流覆盖值，默认 None 使用最新年报的 free_cashflow；若 ≤0 依次回退到 operating_cashflow、net_profit×0.7

    Returns:
        str: JSON 字符串，包含以下可能结构——

        错误情形返回 dict，字段：
            status: "error"
            message: 错误描述
            symbol: 股票代码

        成功情形返回 dict，字段：
            symbol: 股票代码
            method: "two_stage_dcf"
            parameters: 估值参数 dict —
                growth_rate: 实际使用的增长率（小数）
                wacc: 实际使用的折现率（小数）
                terminal_growth_rate: 永续增长率（小数）
                forecast_years: 实际预测年数
            base_year: 基期信息 dict —
                year: 基期年份
                free_cashflow: 基期自由现金流
            valuation: 估值结果 dict —
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
                growth_range: 增长率取值列表（3 个值）
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
                {"status": "error", "message": f"可用年报数据不足（仅 {len(records)} 期），无法进行 DCF 估值", "symbol": symbol},
                ensure_ascii=False, indent=2, default=str,
            )

        # 1. 确定基期 FCF
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

        # 2. 确定增长率
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

        # 3. 计算 WACC
        if wacc is not None:
            resolved_wacc = wacc
            wacc_source = "parameter_override"
        else:
            cost_of_equity = 0.035 + 1.0 * 0.06  # risk-free + beta * ERP
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
        n_forecast = max(3, min(10, int(forecast_years)))

        # 4. DCF 计算
        projected_fcfs = []
        pv_fcfs = []
        for yr in range(1, n_forecast + 1):
            pfcf = resolved_fcf * (1 + resolved_growth) ** yr
            pv = pfcf / (1 + resolved_wacc) ** yr
            projected_fcfs.append(pfcf)
            pv_fcfs.append(pv)

        terminal_value = projected_fcfs[-1] * (1 + tgr) / (resolved_wacc - tgr)
        pv_terminal = terminal_value / (1 + resolved_wacc) ** n_forecast
        enterprise_value = sum(pv_fcfs) + pv_terminal

        # 5. 净债务调整
        total_liab = latest.get("total_liab") or 0
        net_debt_adjustment = total_liab
        equity_value = enterprise_value - net_debt_adjustment

        # 6. 获取股本和当前价格
        from core.skill_runtime.data_access import get_stock_basic_info, get_latest_stock_price

        basic_info = get_stock_basic_info(symbol) or {}
        current_price = get_latest_stock_price(symbol)

        # ── 单位对齐 ──
        # equity_value / free_cashflow / total_liab 等财报口径单位为「元」，
        # 但基础信息表的股本 total_share/float_share 单位为「万股」，
        # 市值 total_mv/circ_mv 单位为「亿元」。
        # 若直接用「万股」做除数，per_share_value 会放大 1e4 倍
        # （如茅台会算出 1262 万元/股，实际约 1264 元/股）。
        # 这里统一把股本换算成「股」。
        raw_shares = (
            basic_info.get("total_shares")
            or basic_info.get("total_share")   # 单位：万股
            or basic_info.get("float_shares")
            or basic_info.get("float_share")   # 单位：万股
        )
        shares = None
        if raw_shares is not None and raw_shares > 0:
            # total_share/float_share 单位为万股 → ×1e4 换算成股
            shares = float(raw_shares) * 1e4
        else:
            # 兜底：用市值 / 当前价推算股数
            # total_mv/circ_mv 单位为亿元 → ×1e8 换算成元
            raw_mv = basic_info.get("total_mv") or basic_info.get("circ_mv")
            market_cap = basic_info.get("market_cap") or basic_info.get("market_value")
            if raw_mv and raw_mv > 0:
                market_cap = float(raw_mv) * 1e8  # 亿元 → 元
            if market_cap and current_price and current_price > 0:
                shares = market_cap / current_price
            else:
                shares = 1.256e9  # 默认约 12.5 亿股
                warnings.append("无法获取总股本，默认使用约 12.5 亿股估算。")

        per_share_value = equity_value / shares if shares and shares > 0 else None
        upside_pct = ((per_share_value - current_price) / current_price * 100) if (per_share_value and current_price and current_price > 0) else None

        # 7. 情景分析
        bear_growth = resolved_growth * 0.7
        bull_growth = resolved_growth * 1.3
        bear_wacc = resolved_wacc * 1.3
        bull_wacc = resolved_wacc * 0.7

        def _scenario(g: float, w: float) -> dict:
            pf = [resolved_fcf * (1 + g) ** y for y in range(1, n_forecast + 1)]
            tv = pf[-1] * (1 + tgr) / (w - tgr)
            ev = sum(pf[y] / (1 + w) ** (y + 1) for y in range(n_forecast)) + tv / (1 + w) ** n_forecast
            eq = ev - net_debt_adjustment
            psv = eq / shares if shares and shares > 0 else None
            up = ((psv - current_price) / current_price * 100) if (psv and current_price and current_price > 0) else None
            return {"per_share_value": psv, "upside_pct": up}

        scenarios = {
            "base": {"per_share_value": per_share_value, "upside_pct": upside_pct},
            "bull": _scenario(bull_growth, bull_wacc),
            "bear": _scenario(bear_growth, bear_wacc),
        }

        # 8. 敏感性分析
        wacc_range = [resolved_wacc - 0.01, resolved_wacc, resolved_wacc + 0.01]
        growth_range = [resolved_growth - 0.01, resolved_growth, resolved_growth + 0.01]
        matrix = []
        for w in wacc_range:
            row = []
            for g in growth_range:
                s = _scenario(g, w)
                row.append(s.get("per_share_value"))
            matrix.append(row)

        payload = {
            "symbol": symbol,
            "method": "two_stage_dcf",
            "parameters": {
                "growth_rate": round(resolved_growth, 4),
                "wacc": round(resolved_wacc, 4),
                "terminal_growth_rate": round(tgr, 4),
                "forecast_years": n_forecast,
            },
            "base_year": {
                "year": latest.get("year"),
                "free_cashflow": resolved_fcf,
            },
            "valuation": {
                "enterprise_value": round(enterprise_value, 2),
                "equity_value": round(equity_value, 2),
                "per_share_value": round(per_share_value, 2) if per_share_value is not None else None,
                "current_price": current_price,
                "upside_pct": round(upside_pct, 2) if upside_pct is not None else None,
                "net_debt_adjustment": round(net_debt_adjustment, 2),
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
        logger.error("DCF估值失败: %s", exc, exc_info=True)
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2, default=str)


__all__ = ["get_dcf_valuation"]
