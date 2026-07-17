"""WACC 加权平均资本成本计算器"""

import json
import logging
from typing import Annotated, Optional

import numpy as np
from langchain_core.tools import tool

from core.tools.base import register_tool

logger = logging.getLogger(__name__)


@tool
@register_tool(
    tool_id="get_wacc_calculation",
    name="WACC 计算器",
    description="计算 A 股公司加权平均资本成本 WACC，返回股权权重、债权权重、股权成本、债权成本、税率和 WACC 明细，为 DCF 估值提供折现率",
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["wacc", "cost_of_capital", "valuation", "discount_rate"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["discount_rate_estimation", "cost_of_capital_calculation"],
    when_to_use="当需要计算折现率、估算资本成本、为 DCF 或绝对估值提供 WACC 参数时使用。",
    when_not_to_use="不适合直接用于估值结论（仅提供参数）。不适合无财务数据的标的。",
    returns="返回 JSON 字符串，包含资本结构、股权成本、债权成本、WACC 及数据质量说明。",
    example="get_wacc_calculation(symbol='600519')",
    related_tools=["get_dcf_valuation", "get_dcf_three_stage_valuation", "get_capm_cost_of_equity"],
)
def get_wacc_calculation(
    symbol: Annotated[str, "A 股股票代码，如 600519"],
    risk_free_rate: Annotated[Optional[float], "无风险利率，默认 2.5%"] = 0.025,
    equity_risk_premium: Annotated[Optional[float], "股权风险溢价，默认 6%"] = 0.06,
    tax_rate: Annotated[Optional[float], "企业所得税率，默认 25%"] = 0.25,
) -> str:
    """WACC 加权平均资本成本计算

    Args:
        symbol: A 股股票代码，如 600519
        risk_free_rate: 无风险利率（小数形式，如 0.025 表示 2.5%），默认 0.025
        equity_risk_premium: 股权风险溢价（小数形式），默认 0.06
        tax_rate: 企业所得税率（小数形式），默认 0.25

    Returns:
        str: JSON 字符串，包含以下可能结构——

        错误情形返回 dict，字段：
            status: "error"
            message: 错误描述
            symbol: 股票代码

        成功情形返回 dict，字段：
            symbol: 股票代码
            parameters: 输入参数 dict —
                risk_free_rate: 无风险利率（小数）
                equity_risk_premium: 股权风险溢价（小数）
                tax_rate: 所得税率（小数）
            capital_structure: 资本结构 dict —
                market_cap: 市值
                total_debt: 总债务
                total_capital: 总资本
                equity_weight: 股权权重（小数）
                debt_weight: 债务权重（小数）
                debt_to_equity: 债务股权比（小数，缺失时为 None）
            cost_of_equity: 股权成本 dict —
                beta: Beta 系数
                risk_free_rate: 无风险利率（小数）
                equity_risk_premium: 股权风险溢价（小数）
                cost_of_equity: 股权成本（小数）
            cost_of_debt: 债权成本 dict —
                interest_expense: 利息费用
                total_debt: 总债务
                pre_tax_cost: 税前债权成本（小数）
                after_tax_cost: 税后债权成本（小数）
            wacc: 加权平均资本成本（小数）
            data_quality: 数据质量 dict —
                beta_source: Beta 来源："default" | "price_returns_estimated"
                debt_cost_source: 债权成本来源："financial_expense_based" | "default_proxy"
                warnings: 警告信息列表

        异常时返回 dict：{"status": "error", "message": ...}
    """
    try:
        from core.skill_runtime.data_access import get_stock_financial_periods, get_stock_daily_quotes
        from core.skill_runtime.standard_financial_apis import get_security_master
        import datetime

        warnings: list = []
        beta_source = "default"

        # 1. 获取市值
        master = get_security_master(symbol)
        market_cap = master.get("market_cap")
        if market_cap is None or market_cap <= 0:
            return json.dumps(
                {"status": "error", "message": f"无法获取 {symbol} 的有效市值", "symbol": symbol},
                ensure_ascii=False, indent=2, default=str,
            )

        # 2. 获取最新财务数据
        periods = get_stock_financial_periods(symbol, limit=1)
        if not periods:
            # 回退到 get_security_master 中可能带有的财务信息
            total_liab = 0.0
            total_equity = (master.get("total_equity") or 0.0)
            fin_exp = 0.0
            warnings.append("未获取到财务期间数据，债务和利息费用采用默认值。")
        else:
            latest_fin = periods[0]
            total_liab = latest_fin.get("total_liab") or 0.0
            total_equity = latest_fin.get("total_equity") or 0.0
            fin_exp = latest_fin.get("fin_exp") or 0.0

            # 🔑 检测报告期口径，对利润表累计值做年化
            from core.tools.implementations.risk.extended_risk_models import (
                _detect_period_type, _annualize_factor, _PERIOD_LABELS,
            )
            cur_period = _detect_period_type(latest_fin)
            if cur_period != "annual" and cur_period != "unknown":
                factor = _annualize_factor(cur_period)
                fin_exp_annualized = fin_exp * factor
                warnings.append(
                    f"当期为{_PERIOD_LABELS.get(cur_period, cur_period)}数据，"
                    f"财务费用已年化处理（{fin_exp:.2f}→{fin_exp_annualized:.2f}）"
                )
                fin_exp = fin_exp_annualized

        # 3. 计算 Beta（简化：从日线收益计算，或默认 1.0）
        beta = 1.0
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
                            # 用自身方差近似，假设市场波动率约 0.015 daily
                            market_var_proxy = 0.015 ** 2
                            cov_proxy = np.mean(returns) * np.mean(returns) if np.mean(returns) > 0 else 0
                            # 简化：beta = 自身波动率 / 市场波动率
                            beta = max(0.2, min(2.5, np.sqrt(var_ret) / 0.015))
                            beta_source = "price_returns_estimated"
        except Exception as e:
            warnings.append(f"Beta 计算失败，使用默认值 1.0: {e}")

        # 4. 成本计算
        rf = risk_free_rate if risk_free_rate is not None else 0.025
        erp = equity_risk_premium if equity_risk_premium is not None else 0.06
        tax = tax_rate if tax_rate is not None else 0.25

        cost_of_equity = rf + beta * erp

        # 债权成本
        if total_liab > 0 and fin_exp > 0:
            pre_tax_cost_of_debt = fin_exp / total_liab
            pre_tax_cost_of_debt = max(0.01, min(0.15, pre_tax_cost_of_debt))
            debt_cost_source = "financial_expense_based"
        else:
            pre_tax_cost_of_debt = 0.04
            debt_cost_source = "default_proxy"
            if total_liab == 0:
                warnings.append("总负债为 0，债权成本采用默认 4%。")
            if fin_exp == 0:
                warnings.append("财务费用为 0 或缺失，债权成本采用默认 4%。")

        after_tax_cost_of_debt = pre_tax_cost_of_debt * (1 - tax)

        # 5. 资本结构
        total_capital = market_cap + total_liab
        equity_weight = market_cap / total_capital if total_capital > 0 else 0.5
        debt_weight = total_liab / total_capital if total_capital > 0 else 0.5
        debt_to_equity = total_liab / total_equity if total_equity and total_equity > 0 else None

        # 6. WACC
        wacc_value = equity_weight * cost_of_equity + debt_weight * after_tax_cost_of_debt

        payload = {
            "symbol": symbol,
            "parameters": {
                "risk_free_rate": round(rf, 4),
                "equity_risk_premium": round(erp, 4),
                "tax_rate": round(tax, 4),
            },
            "capital_structure": {
                "market_cap": round(market_cap, 2),
                "total_debt": round(total_liab, 2),
                "total_capital": round(total_capital, 2),
                "equity_weight": round(equity_weight, 4),
                "debt_weight": round(debt_weight, 4),
                "debt_to_equity": round(debt_to_equity, 4) if debt_to_equity is not None else None,
            },
            "cost_of_equity": {
                "beta": round(beta, 4),
                "risk_free_rate": round(rf, 4),
                "equity_risk_premium": round(erp, 4),
                "cost_of_equity": round(cost_of_equity, 4),
            },
            "cost_of_debt": {
                "interest_expense": round(fin_exp, 2),
                "total_debt": round(total_liab, 2),
                "pre_tax_cost": round(pre_tax_cost_of_debt, 4),
                "after_tax_cost": round(after_tax_cost_of_debt, 4),
            },
            "wacc": round(wacc_value, 4),
            "data_quality": {
                "beta_source": beta_source,
                "debt_cost_source": debt_cost_source,
                "warnings": warnings,
            },
        }
        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    except Exception as exc:
        logger.error("WACC计算失败: %s", exc, exc_info=True)
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2, default=str)


__all__ = ["get_wacc_calculation"]
