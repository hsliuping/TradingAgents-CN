"""Altman Z-Score 破产风险评分工具"""

import json
import logging
from typing import Annotated

from langchain_core.tools import tool

from core.skill_runtime.data_access import get_stock_financial_periods
from core.skill_runtime.standard_financial_apis import get_security_master
from core.tools.base import register_tool
from core.tools.implementations.risk.extended_risk_models import (
    _detect_period_type,
    _annualize_factor,
    _period_caliber_payload,
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


@tool
@register_tool(
    tool_id="get_altman_zscore",
    name="Altman Z-Score 破产风险评分",
    description="基于Altman Z-Score模型评估A股公司的破产风险，综合考虑营运资金、留存收益、EBIT、市值和销售收入五个维度。",
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["bankruptcy_risk", "financial_health"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["bankruptcy_risk_assessment"],
    when_to_use="当需要评估公司破产风险、财务健康状况或识别财务困境信号时使用。",
    when_not_to_use="不用于短期交易决策；Z-Score仅反映长期财务风险。",
    returns="返回JSON字符串，包含z_score、zone、components、raw_data、interpretation和data_quality。",
    example="get_altman_zscore(symbol='600519')",
    related_tools=["get_piotroski_fscore", "get_beneish_mscore"],
)
def get_altman_zscore(symbol: Annotated[str, "A 股股票代码，如 600519、000001"]) -> str:
    """计算 Altman Z-Score 破产风险评分。综合考虑营运资金、留存收益、EBIT、市值和销售收入五个维度。

    Args:
        symbol: A 股股票代码，如 600519、000001

    Returns:
        str: JSON 字符串，字段说明——
            status: "success" | "error"
            symbol: 标的股票代码
            period_type: 当期报告期类型，"annual" | "interim" | "q1" | "q3" | "unknown"
            period_caliber: 报告期口径信息
            z_score: Z-Score 评分
            zone: 风险分区，"安全区" | "灰色区" | "破产风险区"
            components: dict，五个分量——
                — x1_wc_to_ta: 营运资金 / 总资产
                — x2_re_to_ta: 留存收益 / 总资产（近似值）
                — x3_ebit_to_ta: EBIT / 总资产
                — x4_mve_to_tl: 市值 / 总负债
                — x5_sales_to_ta: 年化营收 / 总资产
            raw_data: dict，原始数据——
                — working_capital: 营运资金
                — total_assets: 总资产
                — ebit: 营业利润（EBIT 代理）
                — market_cap: 市值
                — total_liabilities: 总负债
                — revenue: 报告期营收（未年化）
            interpretation: dict，评分解读——
                — score: Z-Score
                — zone: 风险分区
                — bankruptcy_risk: 破产风险等级，"low" | "medium" | "high"
            data_quality: dict，数据质量——
                — warnings: list[str]，告警信息
            message: 当 status 为 "error" 时的错误描述
    """
    try:
        # 获取最新财务数据
        fin_data_list = get_stock_financial_periods(symbol, limit=1)
        if not fin_data_list:
            return json.dumps(
                {"status": "error", "message": f"未获取到 {symbol} 的财务数据", "symbol": symbol},
                ensure_ascii=False, indent=2, default=str,
            )

        fin = fin_data_list[0]

        # 🔑 检测报告期口径
        cur_period_type = _detect_period_type(fin)
        cur_factor = _annualize_factor(cur_period_type)

        # 获取市值
        master = get_security_master(symbol)
        market_cap = _safe_float(master.get("market_cap"))

        # 提取原始数据
        total_cur_assets = _safe_float(fin.get("total_cur_assets"))
        total_cur_liab = _safe_float(fin.get("total_cur_liab"))
        total_assets = _safe_float(fin.get("total_assets"))
        total_equity = _safe_float(fin.get("total_equity"))
        total_liab = _safe_float(fin.get("total_liab"))
        oper_profit = _safe_float(fin.get("oper_profit"))
        revenue = _safe_float(fin.get("revenue"))

        # 🔑 年化营收（X5 分量需要年度营收）
        revenue_annualized = revenue * cur_factor if revenue is not None else None

        # 计算营运资金
        working_capital = (
            total_cur_assets - total_cur_liab
            if total_cur_assets is not None and total_cur_liab is not None
            else None
        )

        warnings: list[str] = []

        if cur_period_type != "annual" and cur_period_type != "unknown":
            warnings.append(f"当期为{_PERIOD_LABELS.get(cur_period_type, cur_period_type)}数据，营收已年化处理以消除口径差异")

        # X1 = 营运资金 / 总资产
        x1_wc_to_ta = _safe_div(working_capital, total_assets)

        # X2 = 留存收益 / 总资产（近似: total_equity / total_assets * 0.5）
        equity_to_assets = _safe_div(total_equity, total_assets)
        x2_re_to_ta = equity_to_assets * 0.5 if equity_to_assets is not None else None
        if equity_to_assets is not None:
            warnings.append("X2留存收益使用近似值（净资产/总资产×0.5），非真实留存收益数据")

        # X3 = EBIT / 总资产（使用营业利润作为EBIT代理）
        x3_ebit_to_ta = _safe_div(oper_profit, total_assets)
        if oper_profit is not None:
            warnings.append("X3使用营业利润作为EBIT代理")

        # X4 = 市值 / 总负债
        x4_mve_to_tl = _safe_div(market_cap, total_liab)

        # X5 = 销售收入 / 总资产 — 使用年化营收
        x5_sales_to_ta = _safe_div(revenue_annualized, total_assets)

        # 计算Z-Score
        components = {
            "x1_wc_to_ta": x1_wc_to_ta,
            "x2_re_to_ta": x2_re_to_ta,
            "x3_ebit_to_ta": x3_ebit_to_ta,
            "x4_mve_to_tl": x4_mve_to_tl,
            "x5_sales_to_ta": x5_sales_to_ta,
        }

        valid_components = {k: v for k, v in components.items() if v is not None}
        if len(valid_components) < 3:
            return json.dumps(
                {
                    "status": "error",
                    "message": f"有效数据不足，仅 {len(valid_components)}/5 个分量可用",
                    "symbol": symbol,
                },
                ensure_ascii=False, indent=2, default=str,
            )

        z_score = round(
            (1.2 * (x1_wc_to_ta or 0.0))
            + (1.4 * (x2_re_to_ta or 0.0))
            + (3.3 * (x3_ebit_to_ta or 0.0))
            + (0.6 * (x4_mve_to_tl or 0.0))
            + (1.0 * (x5_sales_to_ta or 0.0)),
            2,
        )

        if z_score > 3.0:
            zone = "安全区"
            bankruptcy_risk = "low"
        elif z_score >= 1.8:
            zone = "灰色区"
            bankruptcy_risk = "medium"
        else:
            zone = "破产风险区"
            bankruptcy_risk = "high"

        if len(valid_components) < 5:
            missing = [k for k, v in components.items() if v is None]
            warnings.append(f"部分分量缺失: {missing}，Z-Score仅供参考")

        payload = {
            "symbol": symbol,
            "period_type": cur_period_type,
            "period_caliber": _period_caliber_payload(cur_period_type, "unknown", False),
            "z_score": z_score,
            "zone": zone,
            "components": components,
            "raw_data": {
                "working_capital": working_capital,
                "total_assets": total_assets,
                "ebit": oper_profit,
                "market_cap": market_cap,
                "total_liabilities": total_liab,
                "revenue": revenue,
            },
            "interpretation": {
                "score": z_score,
                "zone": zone,
                "bankruptcy_risk": bankruptcy_risk,
            },
            "data_quality": {"warnings": warnings},
        }

        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("Altman Z-Score计算失败: %s", exc, exc_info=True)
        return json.dumps(
            {"status": "error", "message": str(exc)},
            ensure_ascii=False, indent=2, default=str,
        )


__all__ = ["get_altman_zscore"]
