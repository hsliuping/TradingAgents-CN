"""期权与衍生品定价工具。"""

import json
import logging
import math
from typing import Annotated, Optional

import numpy as np
from langchain_core.tools import tool

from core.tools.base import register_tool

logger = logging.getLogger(__name__)

# ── scipy availability check ────────────────────────────────────────

try:
    from scipy import stats as _stats

    def _norm_cdf(x: float) -> float:
        """标准正态分布 CDF，优先 scipy，回退 math.erf。"""
        return float(_stats.norm.cdf(x))

    _HAS_SCIPY = True
except ImportError:
    _HAS_SCIPY = False

    def _norm_cdf(x: float) -> float:
        """标准正态分布 CDF —— math.erf 近似。"""
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    """标准正态分布 PDF。"""
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


# ── Black-Scholes 内部计算 ─────────────────────────────────────────

def _bs_d1(
    spot: float, strike: float, t: float, r: float, sigma: float
) -> float:
    return (math.log(spot / strike) + (r + 0.5 * sigma * sigma) * t) / (
        sigma * math.sqrt(t)
    )


def _bs_price(
    spot: float, strike: float, t: float, r: float, sigma: float, opt_type: str
) -> dict:
    """计算 Black-Scholes 价格及中间变量。

    Returns
        dict with: price, d1, d2, delta, intrinsic_value, time_value
    """
    d1 = _bs_d1(spot, strike, t, r, sigma)
    d2 = d1 - sigma * math.sqrt(t)

    n1 = _norm_cdf(d1)
    n2 = _norm_cdf(d2)
    nm1 = _norm_cdf(-d1)
    nm2 = _norm_cdf(-d2)

    disc = strike * math.exp(-r * t)

    if opt_type == "call":
        price = spot * n1 - disc * n2
        delta = n1
        intrinsic = max(spot - strike, 0.0)
    else:
        price = disc * nm2 - spot * nm1
        delta = n1 - 1.0
        intrinsic = max(strike - spot, 0.0)

    time_value = price - intrinsic
    return {
        "price": round(price, 6),
        "d1": round(d1, 6),
        "d2": round(d2, 6),
        "delta": round(delta, 6),
        "intrinsic_value": round(intrinsic, 6),
        "time_value": round(time_value, 6),
    }


def _bs_vega(
    spot: float, strike: float, t: float, r: float, sigma: float
) -> float:
    """计算 Vega = S * N'(d1) * sqrt(T)"""
    d1 = _bs_d1(spot, strike, t, r, sigma)
    return spot * _norm_pdf(d1) * math.sqrt(t)


# ── Tool 1: Black-Scholes 期权定价 ─────────────────────────────────

@tool
@register_tool(
    tool_id="get_black_scholes_price",
    name="Black-Scholes 期权定价",
    description=(
        "基于 Black-Scholes 模型计算欧式期权的理论价格，同时返回 d1、d2、Delta、"
        "内在价值和时间价值。使用 scipy.stats.norm.cdf 计算正态分布累积函数；"
        "若 scipy 不可用则回退至 math.erf 近似。"
    ),
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["derivatives", "option_pricing", "black_scholes"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["欧式期权理论定价", "Black-Scholes 模型计算"],
    when_to_use=(
        "当用户需要计算欧式期权的理论价格、d1/d2、Delta、内在价值或时间价值时使用。"
        "适用于标准化的欧式看涨/看跌期权定价。"
    ),
    when_not_to_use=(
        "不适合美式期权（需考虑提前行权）；"
        "不适合奇异期权（如障碍期权、亚式期权等）；"
        "不适合隐含波动率计算（请使用 get_implied_volatility）。"
    ),
    returns=(
        "返回 JSON 字符串，包含 option_price（期权价格）、d1、d2、delta、"
        "intrinsic_value（内在价值）、time_value（时间价值）、parameters_used（使用参数）、"
        "methodology（计算说明）。"
    ),
    example="get_black_scholes_price(spot_price=100, strike_price=100, time_to_expiry=0.5)",
    related_tools=["get_implied_volatility", "get_option_greeks", "get_option_strategy_pnl"],
)
def get_black_scholes_price(
    spot_price: Annotated[float, "标的资产当前价格"],
    strike_price: Annotated[float, "行权价"],
    time_to_expiry: Annotated[float, "到期时间（年），如 0.5 表示半年"],
    risk_free_rate: Annotated[float, "无风险利率"] = 0.025,
    volatility: Annotated[float, "波动率（年化）"] = 0.25,
    option_type: Annotated[str, "期权类型：call（看涨）或 put（看跌）"] = "call",
) -> str:
    """计算欧式期权的 Black-Scholes 理论价格。

    Args:
        spot_price: 标的资产当前价格
        strike_price: 行权价
        time_to_expiry: 到期时间（年），如 0.5 表示半年
        risk_free_rate: 无风险利率（小数），默认 0.025
        volatility: 波动率（年化小数），默认 0.25
        option_type: 期权类型: "call"（看涨）或 "put"（看跌），默认 "call"

    Returns:
        str: JSON 字符串，字段说明——
            status: 状态: "ok" | "error"
            option_type: 期权类型: "call" | "put"
            option_price: 期权理论价格
            d1: BS 公式中的 d1
            d2: BS 公式中的 d2
            delta: Delta 值
            intrinsic_value: 内在价值
            time_value: 时间价值
            moneyness: 价内状态: "价内" | "价平或价外"
            parameters_used: dict 使用的参数——
                — spot_price: 标的价格
                — strike_price: 行权价
                — time_to_expiry_years: 到期时间（年）
                — risk_free_rate: 无风险利率
                — volatility: 波动率
                — option_type: 期权类型
            methodology: 计算方法说明
            message: 错误信息（仅 status="error" 时存在）
    """
    try:
        opt_type = option_type.lower()
        if opt_type not in ("call", "put"):
            return json.dumps({
                "status": "error",
                "message": "option_type 必须是 'call' 或 'put'",
            }, ensure_ascii=False, indent=2, default=str)

        if spot_price <= 0 or strike_price <= 0:
            return json.dumps({
                "status": "error",
                "message": "spot_price 和 strike_price 必须大于 0",
            }, ensure_ascii=False, indent=2, default=str)

        if time_to_expiry <= 0:
            return json.dumps({
                "status": "error",
                "message": "time_to_expiry 必须大于 0",
            }, ensure_ascii=False, indent=2, default=str)

        if volatility <= 0:
            return json.dumps({
                "status": "error",
                "message": "volatility 必须大于 0",
            }, ensure_ascii=False, indent=2, default=str)

        result = _bs_price(
            spot=spot_price,
            strike=strike_price,
            t=time_to_expiry,
            r=risk_free_rate,
            sigma=volatility,
            opt_type=opt_type,
        )

        payload = {
            "status": "ok",
            "option_type": opt_type,
            "option_price": result["price"],
            "d1": result["d1"],
            "d2": result["d2"],
            "delta": result["delta"],
            "intrinsic_value": result["intrinsic_value"],
            "time_value": result["time_value"],
            "moneyness": "价内" if result["intrinsic_value"] > 0 else "价平或价外",
            "parameters_used": {
                "spot_price": spot_price,
                "strike_price": strike_price,
                "time_to_expiry_years": time_to_expiry,
                "risk_free_rate": risk_free_rate,
                "volatility": volatility,
                "option_type": opt_type,
            },
            "methodology": (
                "Black-Scholes 欧式期权定价模型："
                "d1 = [ln(S/K) + (r + σ²/2)T] / (σ√T)；"
                "d2 = d1 - σ√T；"
                "Call = S·N(d1) - K·e^(-rT)·N(d2)；"
                "Put = K·e^(-rT)·N(-d2) - S·N(-d1)。"
                f"{'使用 scipy.stats.norm.cdf 计算 N(·)。' if _HAS_SCIPY else '使用 math.erf 近似计算 N(·)（scipy 不可用）。'}"
            ),
        }

        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("Black-Scholes 定价失败: %s", exc, exc_info=True)
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2, default=str)


# ── Tool 2: 隐含波动率 ─────────────────────────────────────────────

@tool
@register_tool(
    tool_id="get_implied_volatility",
    name="隐含波动率计算",
    description=(
        "通过 Newton-Raphson 迭代法从期权市场价反推隐含波动率。"
        "迭代公式：σ_new = σ - (BS(σ) - market_price) / vega(σ)，"
        "最大迭代 100 次，收敛容差 0.0001。"
    ),
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["derivatives", "implied_volatility", "option_pricing"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["从期权市场价反推隐含波动率"],
    when_to_use=(
        "当用户已知期权市场价，需要反推出对应的隐含波动率时使用。"
        "常用于波动率交易、期权定价校验。"
    ),
    when_not_to_use=(
        "不适合理论定价（请使用 get_black_scholes_price）；"
        "不适合历史波动率计算（请使用统计工具）；"
        "不适合深度虚值期权（迭代可能不收敛）。"
    ),
    returns=(
        "返回 JSON 字符串，包含 implied_volatility（隐含波动率）、"
        "iterations（迭代次数）、convergence_status（收敛状态）、"
        "initial_guess（初始猜测值）、price_at_iv（IV对应的BS价格）。"
    ),
    example="get_implied_volatility(spot_price=100, strike_price=100, time_to_expiry=0.5, option_price=10)",
    related_tools=["get_black_scholes_price", "get_option_greeks", "get_option_strategy_pnl"],
)
def get_implied_volatility(
    spot_price: Annotated[float, "标的资产当前价格"],
    strike_price: Annotated[float, "行权价"],
    time_to_expiry: Annotated[float, "到期时间（年）"],
    option_price: Annotated[float, "期权市场价"],
    risk_free_rate: Annotated[float, "无风险利率"] = 0.025,
    option_type: Annotated[str, "期权类型：call 或 put"] = "call",
) -> str:
    """通过 Newton-Raphson 迭代从市场价反推隐含波动率。

    Args:
        spot_price: 标的资产当前价格
        strike_price: 行权价
        time_to_expiry: 到期时间（年）
        option_price: 期权市场价
        risk_free_rate: 无风险利率（小数），默认 0.025
        option_type: 期权类型: "call" 或 "put"，默认 "call"

    Returns:
        str: JSON 字符串，字段说明——
            status: 状态: "ok" | "error"
            implied_volatility: 隐含波动率（小数）
            implied_volatility_pct: 隐含波动率（%）
            iterations: 迭代次数
            convergence_status: 收敛状态: "已收敛" | "未收敛"
            initial_guess: 初始猜测值（0.3）
            price_at_iv: IV 对应的 BS 价格（仅 status="ok" 时存在）
            target_price: 目标期权市场价（仅 status="ok" 时存在）
            price_error: 价格误差（仅 status="ok" 时存在）
            parameters_used: dict 使用的参数（仅 status="ok" 时存在）——
                — spot_price: 标的价格
                — strike_price: 行权价
                — time_to_expiry_years: 到期时间（年）
                — risk_free_rate: 无风险利率
                — option_price: 期权市场价
                — option_type: 期权类型
            methodology: 计算方法说明（仅 status="ok" 时存在）
            message: 错误信息（仅 status="error" 时存在）
    """
    try:
        opt_type = option_type.lower()
        if opt_type not in ("call", "put"):
            return json.dumps({
                "status": "error",
                "message": "option_type 必须是 'call' 或 'put'",
            }, ensure_ascii=False, indent=2, default=str)

        if spot_price <= 0 or strike_price <= 0:
            return json.dumps({
                "status": "error",
                "message": "spot_price 和 strike_price 必须大于 0",
            }, ensure_ascii=False, indent=2, default=str)

        if time_to_expiry <= 0:
            return json.dumps({
                "status": "error",
                "message": "time_to_expiry 必须大于 0",
            }, ensure_ascii=False, indent=2, default=str)

        if option_price <= 0:
            return json.dumps({
                "status": "error",
                "message": "option_price 必须大于 0",
            }, ensure_ascii=False, indent=2, default=str)

        # 判断内在价值上限
        intrinsic = max(spot_price - strike_price, 0.0) if opt_type == "call" else max(strike_price - spot_price, 0.0)
        if option_price < intrinsic:
            return json.dumps({
                "status": "error",
                "message": (
                    f"期权价格 {option_price} 低于内在价值 {intrinsic}，"
                    "存在无风险套利机会，无法计算有意义的隐含波动率"
                ),
            }, ensure_ascii=False, indent=2, default=str)

        sigma = 0.3  # 初始猜测
        max_iter = 100
        tolerance = 0.0001

        for i in range(max_iter):
            bs = _bs_price(spot_price, strike_price, time_to_expiry, risk_free_rate, sigma, opt_type)
            price_diff = bs["price"] - option_price

            if abs(price_diff) < tolerance:
                payload = {
                    "status": "ok",
                    "implied_volatility": round(sigma, 6),
                    "implied_volatility_pct": round(sigma * 100, 4),
                    "iterations": i + 1,
                    "convergence_status": "已收敛",
                    "initial_guess": 0.3,
                    "price_at_iv": bs["price"],
                    "target_price": option_price,
                    "price_error": round(price_diff, 8),
                    "parameters_used": {
                        "spot_price": spot_price,
                        "strike_price": strike_price,
                        "time_to_expiry_years": time_to_expiry,
                        "risk_free_rate": risk_free_rate,
                        "option_price": option_price,
                        "option_type": opt_type,
                    },
                    "methodology": (
                        "Newton-Raphson 迭代法：σ_new = σ - (BS(σ) - market_price) / vega(σ)。"
                        + ("使用 scipy.stats.norm 计算 N(·) 和 N'(·)。" if _HAS_SCIPY else "使用 math.erf 近似计算 N(·)（scipy 不可用）。")
                    ),
                }
                return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

            vega = _bs_vega(spot_price, strike_price, time_to_expiry, risk_free_rate, sigma)
            if abs(vega) < 1e-12:
                break  # vega 太小，无法继续迭代

            sigma = sigma - price_diff / vega
            sigma = max(sigma, 0.001)  # 波动率保底

        return json.dumps({
            "status": "error",
            "message": f"迭代 {max_iter} 次未收敛，请检查输入参数或尝试不同的初始猜测",
            "implied_volatility": round(sigma, 6) if sigma > 0 else None,
            "iterations": max_iter,
            "convergence_status": "未收敛",
            "initial_guess": 0.3,
        }, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("隐含波动率计算失败: %s", exc, exc_info=True)
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2, default=str)


# ── Tool 3: 希腊字母计算 ───────────────────────────────────────────

@tool
@register_tool(
    tool_id="get_option_greeks",
    name="期权希腊字母计算",
    description=(
        "计算欧式期权的 Greeks（Delta、Gamma、Theta、Vega、Rho），"
        "并给出每个希腊字母的释义。Gamma 和 Vega 对看涨/看跌期权相同。"
    ),
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["derivatives", "option_greeks", "risk_management"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["计算期权希腊字母（Delta、Gamma、Theta、Vega、Rho）"],
    when_to_use=(
        "当用户需要计算欧式期权的风险指标（Delta/Gamma/Theta/Vega/Rho）时使用。"
        "适用于风险管理、对冲策略分析。"
    ),
    when_not_to_use=(
        "不适合美式期权希腊字母计算；"
        "不适合奇异期权；"
        "不适合期权定价本身（请使用 get_black_scholes_price）。"
    ),
    returns=(
        "返回 JSON 字符串，包含 delta、gamma、theta（年化）、vega（1%波动率变动）、"
        "rho（1%利率变动），以及每个希腊字母的释义。"
    ),
    example="get_option_greeks(spot_price=100, strike_price=100, time_to_expiry=0.5)",
    related_tools=["get_black_scholes_price", "get_implied_volatility", "get_option_strategy_pnl"],
)
def get_option_greeks(
    spot_price: Annotated[float, "标的资产当前价格"],
    strike_price: Annotated[float, "行权价"],
    time_to_expiry: Annotated[float, "到期时间（年）"],
    risk_free_rate: Annotated[float, "无风险利率"] = 0.025,
    volatility: Annotated[float, "波动率（年化）"] = 0.25,
    option_type: Annotated[str, "期权类型：call 或 put"] = "call",
) -> str:
    """计算欧式期权的 Delta、Gamma、Theta、Vega、Rho。

    Args:
        spot_price: 标的资产当前价格
        strike_price: 行权价
        time_to_expiry: 到期时间（年）
        risk_free_rate: 无风险利率（小数），默认 0.025
        volatility: 波动率（年化小数），默认 0.25
        option_type: 期权类型: "call" 或 "put"，默认 "call"

    Returns:
        str: JSON 字符串，字段说明——
            status: 状态: "ok" | "error"
            option_type: 期权类型: "call" | "put"
            spot_price_used: 使用的标的价格
            delta: dict Delta——
                — value: Delta 值
                — description: 含义说明
                — interpretation: 解释（方向性风险敞口）
            gamma: dict Gamma——
                — value: Gamma 值
                — description: 含义说明
                — interpretation: 解释（Delta 的敏感度/凸性风险）
            theta: dict Theta（年化）——
                — value: Theta 值（年化）
                — description: 含义说明（含日均 Theta）
                — interpretation: 解释（时间衰减）
            vega: dict Vega（每 1% 波动率变动）——
                — value: Vega 值
                — description: 含义说明
                — interpretation: 解释（波动率风险敞口）
            rho: dict Rho（每 1% 利率变动）——
                — value: Rho 值
                — description: 含义说明
                — interpretation: 解释（利率风险敞口）
            parameters_used: dict 使用的参数
            methodology: 计算方法说明
            message: 错误信息（仅 status="error" 时存在）
    """
    try:
        opt_type = option_type.lower()
        if opt_type not in ("call", "put"):
            return json.dumps({
                "status": "error",
                "message": "option_type 必须是 'call' 或 'put'",
            }, ensure_ascii=False, indent=2, default=str)

        if spot_price <= 0 or strike_price <= 0:
            return json.dumps({
                "status": "error",
                "message": "spot_price 和 strike_price 必须大于 0",
            }, ensure_ascii=False, indent=2, default=str)

        if time_to_expiry <= 0:
            return json.dumps({
                "status": "error",
                "message": "time_to_expiry 必须大于 0",
            }, ensure_ascii=False, indent=2, default=str)

        if volatility <= 0:
            return json.dumps({
                "status": "error",
                "message": "volatility 必须大于 0",
            }, ensure_ascii=False, indent=2, default=str)

        d1 = _bs_d1(spot_price, strike_price, time_to_expiry, risk_free_rate, volatility)
        d2 = d1 - volatility * math.sqrt(time_to_expiry)

        n1 = _norm_cdf(d1)
        nd1_pdf = _norm_pdf(d1)  # N'(d1)

        sqrt_t = math.sqrt(time_to_expiry)
        disc = strike_price * math.exp(-risk_free_rate * time_to_expiry)

        # Delta
        if opt_type == "call":
            delta = n1
        else:
            delta = n1 - 1.0

        # Gamma（call/put 相同）
        gamma = nd1_pdf / (spot_price * volatility * sqrt_t)

        # Theta（年化）
        theta_common = -(spot_price * nd1_pdf * volatility) / (2.0 * sqrt_t)
        if opt_type == "call":
            theta = theta_common - risk_free_rate * disc * _norm_cdf(d2)
        else:
            theta = theta_common + risk_free_rate * disc * _norm_cdf(-d2)

        # Vega（call/put 相同）
        vega = spot_price * nd1_pdf * sqrt_t

        # Rho
        if opt_type == "call":
            rho = disc * time_to_expiry * _norm_cdf(d2)
        else:
            rho = -disc * time_to_expiry * _norm_cdf(-d2)

        payload = {
            "status": "ok",
            "option_type": opt_type,
            "spot_price_used": spot_price,
            "delta": {
                "value": round(delta, 6),
                "description": (
                    "标的资产价格变化 $1 时期权价格的变化量。"
                    f"看涨期权 Delta={round(delta, 4)}，"
                    f"意味着标的价格上涨 $1，期权价格约变动 {round(delta, 4)}。"
                ),
                "interpretation": "方向性风险敞口" if opt_type == "call" else "方向性风险敞口（负值）",
            },
            "gamma": {
                "value": round(gamma, 6),
                "description": (
                    f"标的资产价格变化 $1 时 Delta 的变化量。Gamma={round(gamma, 6)}，"
                    "Gamma 越大，Delta 对价格变化越敏感。"
                ),
                "interpretation": "Delta 的敏感度（凸性风险）",
            },
            "theta": {
                "value": round(theta, 6),
                "description": (
                    f"时间每流逝一天（年化/365），期权价格的变化量。"
                    f"Theta（年化）={round(theta, 6)}，"
                    f"日均 Theta ≈ {round(theta / 365.0, 6)}。"
                ),
                "interpretation": "时间衰减（Theta 通常为负，表示时间价值流失）",
            },
            "vega": {
                "value": round(vega / 100.0, 6),
                "description": (
                    f"波动率每上升 1%（即 0.01），期权价格的变化量。"
                    f"Vega（每 1% 波动率）≈ {round(vega / 100.0, 6)}。"
                ),
                "interpretation": "波动率风险敞口",
            },
            "rho": {
                "value": round(rho / 100.0, 6),
                "description": (
                    f"无风险利率每上升 1%（即 0.01），期权价格的变化量。"
                    f"Rho（每 1% 利率变动）≈ {round(rho / 100.0, 6)}。"
                ),
                "interpretation": "利率风险敞口（对短期限期权通常影响较小）",
            },
            "parameters_used": {
                "spot_price": spot_price,
                "strike_price": strike_price,
                "time_to_expiry_years": time_to_expiry,
                "risk_free_rate": risk_free_rate,
                "volatility": volatility,
                "option_type": opt_type,
            },
            "methodology": (
                "Delta = N(d1)（call）或 N(d1)-1（put）；"
                "Gamma = N'(d1) / (S·σ·√T)；"
                "Theta(call) = -(S·N'(d1)·σ)/(2√T) - r·K·e^(-rT)·N(d2)；"
                "Vega = S·N'(d1)·√T；"
                "Rho(call) = K·T·e^(-rT)·N(d2)。"
                + ("使用 scipy.stats.norm 计算 N(·) 和 N'(·)。" if _HAS_SCIPY else "使用 math.erf 近似计算 N(·)（scipy 不可用）。")
            ),
        }

        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("希腊字母计算失败: %s", exc, exc_info=True)
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2, default=str)


# ── Tool 4: 期权策略盈亏图 ─────────────────────────────────────────

def _covered_call_pnl(
    spot_range: np.ndarray, spot_0: float, k1: float, prem1: float
) -> np.ndarray:
    """covered_call: long stock + short call at k1"""
    call_intrinsic = np.maximum(spot_range - k1, 0.0)
    stock_pnl = spot_range - spot_0
    return stock_pnl + prem1 - call_intrinsic


def _protective_put_pnl(
    spot_range: np.ndarray, spot_0: float, k1: float, prem1: float
) -> np.ndarray:
    """protective_put: long stock + long put at k1"""
    put_intrinsic = np.maximum(k1 - spot_range, 0.0)
    stock_pnl = spot_range - spot_0
    return stock_pnl - prem1 + put_intrinsic


def _straddle_pnl(
    spot_range: np.ndarray, k: float, prem1: float
) -> np.ndarray:
    """straddle: long call + long put at same strike; total_prem = 2*prem1"""
    return np.abs(spot_range - k) - 2.0 * prem1


def _strangle_pnl(
    spot_range: np.ndarray, k1: float, k2: float, prem1: float, prem2: float
) -> np.ndarray:
    """strangle: long put at k1 (< spot) + long call at k2 (> spot)"""
    put_pnl = np.maximum(k1 - spot_range, 0.0) - prem1
    call_pnl = np.maximum(spot_range - k2, 0.0) - prem2
    return put_pnl + call_pnl


def _bull_spread_pnl(
    spot_range: np.ndarray, k1: float, k2: float, prem1: float, prem2: float
) -> np.ndarray:
    """bull_spread: long call at k1 + short call at k2 (k2 > k1)"""
    long_call = np.maximum(spot_range - k1, 0.0) - prem1
    short_call = prem2 - np.maximum(spot_range - k2, 0.0)
    return long_call + short_call


def _bear_spread_pnl(
    spot_range: np.ndarray, k1: float, k2: float, prem1: float, prem2: float
) -> np.ndarray:
    """bear_spread: long put at k1 + short put at k2 (k1 > k2)"""
    long_put = np.maximum(k1 - spot_range, 0.0) - prem1
    short_put = prem2 - np.maximum(k2 - spot_range, 0.0)
    return long_put + short_put


def _iron_condor_pnl(
    spot_range: np.ndarray,
    k1: float, k2: float, k3: float, k4: float,
    prem1: float, prem2: float, prem3: float, prem4: float,
) -> np.ndarray:
    """iron_condor: bear put spread (k1>k2) + bull call spread (k3<k4)"""
    # Bear put spread: long put at k1, short put at k2
    long_put = np.maximum(k1 - spot_range, 0.0) - prem1
    short_put = prem2 - np.maximum(k2 - spot_range, 0.0)
    # Bull call spread: long call at k3, short call at k4
    long_call = np.maximum(spot_range - k3, 0.0) - prem3
    short_call = prem4 - np.maximum(spot_range - k4, 0.0)
    return long_put + short_put + long_call + short_call


_STRATEGIES = {
    "covered_call": {
        "label": "备兑开仓（Covered Call）",
        "description": "持有标的资产 + 卖出看涨期权。适用于温和看涨或中性预期，通过权利金增厚收益。",
        "legs": 2,
    },
    "protective_put": {
        "label": "保护性看跌（Protective Put）",
        "description": "持有标的资产 + 买入看跌期权。适用于看涨但担心下行风险，相当于为持仓买保险。",
        "legs": 2,
    },
    "straddle": {
        "label": "跨式组合（Straddle）",
        "description": "同时买入同价看涨和看跌期权。适用于预期标的将有大幅波动但方向不确定。",
        "legs": 2,
    },
    "strangle": {
        "label": "宽跨式组合（Strangle）",
        "description": "买入虚值看跌（K1<S）和虚值看涨（K2>S）。适用于预期大幅波动，成本低于 straddle。",
        "legs": 2,
    },
    "bull_spread": {
        "label": "牛市价差（Bull Spread）",
        "description": "买入低行权价看涨 + 卖出高行权价看涨。适用于温和看涨、降低成本。",
        "legs": 2,
    },
    "bear_spread": {
        "label": "熊市价差（Bear Spread）",
        "description": "买入高行权价看跌 + 卖出低行权价看跌。适用于温和看跌、降低成本。",
        "legs": 2,
    },
    "iron_condor": {
        "label": "铁鹰式（Iron Condor）",
        "description": "熊市看跌价差 + 牛市看涨价差（共4腿）。适用于预期标的窄幅震荡。",
        "legs": 4,
    },
}


@tool
@register_tool(
    tool_id="get_option_strategy_pnl",
    name="期权策略盈亏图",
    description=(
        "计算常见期权策略在到期日的盈亏曲线，包括最大盈利、最大亏损、"
        "盈亏平衡点，以及约 20 个价格点的盈亏明细表。"
        "支持策略：covered_call（备兑开仓）、protective_put（保护性看跌）、"
        "straddle（跨式）、strangle（宽跨式）、bull_spread（牛市价差）、"
        "bear_spread（熊市价差）、iron_condor（铁鹰式）。"
    ),
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["derivatives", "option_strategy", "pnl_analysis"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["期权策略盈亏分析", "策略对比", "盈亏平衡点计算"],
    when_to_use=(
        "当用户需要分析期权组合策略在到期日的盈亏情况、计算最大盈利/亏损、"
        "盈亏平衡点，或需要盈亏可视化数据时使用。"
    ),
    when_not_to_use=(
        "不适合单腿期权定价（请使用 get_black_scholes_price）；"
        "不适合希腊字母计算（请使用 get_option_greeks）；"
        "不适合隐含波动率计算（请使用 get_implied_volatility）。"
    ),
    returns=(
        "返回 JSON 字符串，包含 strategy（策略名称及描述）、max_profit（最大盈利）、"
        "max_loss（最大亏损）、break_even_points（盈亏平衡点列表）、"
        "pnl_table（价格-盈亏数组，约 20 个点）。"
    ),
    example="get_option_strategy_pnl(strategy_type='covered_call', spot_price=100, strike1=100)",
    related_tools=["get_black_scholes_price", "get_option_greeks", "get_implied_volatility"],
)
def get_option_strategy_pnl(
    strategy_type: Annotated[str, "策略类型"] = "covered_call",
    spot_price: Annotated[float, "标的当前价格"] = 100.0,
    strike1: Annotated[float, "主行权价（第一腿）"] = 100.0,
    strike2: Annotated[Optional[float], "第二行权价（价差策略使用）"] = None,
    premium1: Annotated[float, "第一腿权利金（收/付）"] = 5.0,
    premium2: Annotated[Optional[float], "第二腿权利金（收/付）"] = None,
    volatility: Annotated[float, "波动率（用于 ATM 期权参考）"] = 0.25,
    time_to_expiry: Annotated[float, "到期时间（年）"] = 0.25,
    risk_free_rate: Annotated[float, "无风险利率"] = 0.025,
) -> str:
    """计算期权策略在到期日的盈亏分布。

    Args:
        strategy_type: 策略类型，可选 "covered_call" / "protective_put" / "straddle" /
            "strangle" / "bull_spread" / "bear_spread" / "iron_condor"，默认 "covered_call"
        spot_price: 标的当前价格，默认 100.0
        strike1: 主行权价（第一腿），默认 100.0
        strike2: 第二行权价（价差策略使用），为 None 时按策略自动推算，默认 None
        premium1: 第一腿权利金，默认 5.0
        premium2: 第二腿权利金，为 None 时按策略自动推算，默认 None
        volatility: 波动率（用于 ATM 期权参考），默认 0.25
        time_to_expiry: 到期时间（年），默认 0.25
        risk_free_rate: 无风险利率，默认 0.025

    Returns:
        str: JSON 字符串，字段说明——
            status: 状态: "ok" | "error"
            strategy: 策略中文名称
            strategy_description: 策略描述
            legs: 各腿组合说明文本
            max_profit: 最大盈利（数值或 "无穷（理论上限）"）
            max_loss: 最大亏损（数值或 "无穷（理论下限）"）
            break_even_points: list[float] 盈亏平衡点列表
            pnl_table: list[dict] 盈亏明细表（约 21 个点），元素结构——
                — spot_price_at_expiry: 到期标的价格
                — pnl: 该价格下的盈亏
            visualization_note: 可视化说明
            parameters_used: dict 使用的参数——
                — strategy_type: 策略类型
                — spot_price: 标的价格
                — strike1: 主行权价
                — strike2: 第二行权价
                — premium1: 第一腿权利金
                — premium2: 第二腿权利金
                — time_to_expiry_years: 到期时间（年）
                — volatility: 波动率
            methodology: 计算方法说明
            message: 错误信息（仅 status="error" 时存在）
    """
    try:
        strategy = strategy_type.lower()
        if strategy not in _STRATEGIES:
            return json.dumps({
                "status": "error",
                "message": (
                    f"不支持的策略类型 '{strategy_type}'。"
                    f"支持：{', '.join(_STRATEGIES.keys())}"
                ),
            }, ensure_ascii=False, indent=2, default=str)

        s0 = spot_price
        k1 = strike1

        # 生成价格范围：0 ~ 2*s0，约 20 个点
        price_points = 21
        spot_range = np.linspace(0.0, 2.0 * s0, price_points)

        # 根据策略类型计算盈亏
        strategy_info = _STRATEGIES[strategy]

        if strategy == "covered_call":
            k2 = strike2 if strike2 is not None else k1
            pnl = _covered_call_pnl(spot_range, s0, k1, premium1)
            legs_desc = f"Long stock @ {s0} + Short call @ {k1}（权利金收入 {premium1}）"
            # max profit = k1 - s0 + premium (capped at k1)
            max_profit = k1 - s0 + premium1
            # max loss = s0 - 0 + (-premium when deep ITM) -- actually at S_T=0, stock loses all, keep premium
            # Actually: max loss = s0 (stock goes to 0, loss S_0) + keep premium
            # Wait: profit = S_T - S_0 + prem - max(S_T-K, 0)
            # If S_T=0: profit = 0 - S0 + prem - 0 = prem - S0
            # If S_T=inf: profit = S_T - S0 + prem - (S_T-K) = K - S0 + prem
            max_loss = premium1 - s0
            be1 = s0 - premium1
            be_points = sorted({round(p, 2) for p in [be1] if p >= 0})

        elif strategy == "protective_put":
            k2 = strike2 if strike2 is not None else k1
            pnl = _protective_put_pnl(spot_range, s0, k1, premium1)
            legs_desc = f"Long stock @ {s0} + Long put @ {k1}（权利金支出 {premium1}）"
            # profit = S_T - S_0 - prem + max(K-S_T, 0)
            # if S_T >= K: profit = S_T - S_0 - prem, unlimited upside
            # if S_T < K: profit = K - S_0 - prem (floor)
            max_profit = None  # unlimited upside
            max_loss = premium1 - (k1 - s0)  # = s0 + prem - k1
            if s0 + premium1 > k1:
                max_loss = s0 + premium1 - k1
            else:
                max_loss = premium1 + s0 - k1
            # Wait: floor is when S_T=0: profit = 0 - s0 - prem + (K-0) = K - s0 - prem
            max_loss = k1 - s0 - premium1  # this is negative if k1 < s0+prem
            be1 = s0 + premium1
            be_points = sorted({round(p, 2) for p in [be1] if p >= 0})

        elif strategy == "straddle":
            k2 = strike2 if strike2 is not None else k1
            pnl = _straddle_pnl(spot_range, k1, premium1)
            legs_desc = f"Long call @ {k1} + Long put @ {k1}（总权利金支出 {2 * premium1}）"
            max_profit = None  # unlimited upside
            max_loss = -2.0 * premium1
            be_low = k1 - 2.0 * premium1
            be_high = k1 + 2.0 * premium1
            be_points = sorted({round(p, 2) for p in [be_low, be_high] if p >= 0})

        elif strategy == "strangle":
            k2 = strike2 if strike2 is not None else s0 * 1.1
            p2 = premium2 if premium2 is not None else premium1 * 0.8
            pnl = _strangle_pnl(spot_range, k1, k2, premium1, p2)
            legs_desc = f"Long put @ {k1}（权利金 {premium1}）+ Long call @ {k2}（权利金 {p2}）"
            total_prem = premium1 + p2
            max_loss = -total_prem
            be_low = k1 - total_prem
            be_high = k2 + total_prem
            max_profit = None  # unlimited upside
            be_points = sorted({round(p, 2) for p in [be_low, be_high] if p >= 0})

        elif strategy == "bull_spread":
            k2 = strike2 if strike2 is not None else k1 * 1.1
            p2 = premium2 if premium2 is not None else premium1 * 0.6
            pnl = _bull_spread_pnl(spot_range, k1, k2, premium1, p2)
            legs_desc = f"Long call @ {k1}（权利金 {premium1}）+ Short call @ {k2}（权利金 {p2}）"
            net_prem = premium1 - p2
            max_loss = -net_prem
            max_profit = (k2 - k1) - net_prem
            be1 = k1 + net_prem
            be_points = sorted({round(p, 2) for p in [be1] if p >= 0})

        elif strategy == "bear_spread":
            k2 = strike2 if strike2 is not None else k1 * 0.9
            p2 = premium2 if premium2 is not None else premium1 * 0.6
            pnl = _bear_spread_pnl(spot_range, k1, k2, premium1, p2)
            legs_desc = f"Long put @ {k1}（权利金 {premium1}）+ Short put @ {k2}（权利金 {p2}）"
            net_prem = premium1 - p2
            max_loss = -net_prem
            max_profit = (k1 - k2) - net_prem
            be1 = k1 - net_prem
            be_points = sorted({round(p, 2) for p in [be1] if p >= 0})

        elif strategy == "iron_condor":
            # Bear put spread: long put at k1, short put at k2
            # Bull call spread: long call at k3, short call at k4
            # Default: k1=s0*1.1, k2=s0*1.05, k3=s0*0.95, k4=s0*0.9
            k2_val = strike2 if strike2 is not None else s0 * 1.05
            k3 = s0 * 0.95
            k4 = s0 * 0.90
            p2_val = premium2 if premium2 is not None else premium1 * 0.7
            p3 = premium1 * 0.7
            p4 = premium1 * 0.5
            pnl = _iron_condor_pnl(spot_range, k1, k2_val, k3, k4, premium1, p2_val, p3, p4)
            legs_desc = (
                f"Bear put spread: long put @ {k1}（{premium1}）+ short put @ {k2_val}（{p2_val}）；"
                f"Bull call spread: long call @ {k3}（{p3}）+ short call @ {k4}（{p4}）"
            )
            net_prem = (p2_val + p4) - (premium1 + p3)
            max_profit = net_prem
            max_loss = (k1 - k2_val) - net_prem  # width of put spread minus net credit
            be_low = k1 + net_prem
            be_high = k4 - net_prem
            be_points = sorted({round(p, 2) for p in [be_low, be_high] if p >= 0})
            # Fix: iron_condor max profit/loss logic
            # Net credit = credit received - debit paid
            # Put spread: sell k2 (higher credit), buy k1 (lower debit)
            # In iron condor: bear put spread = sell put at k2, buy put at k1 (k1 > k2)
            # Bull call spread = buy call at k3, sell call at k4 (k3 < k4)
            # If we receive net credit: max profit = net credit
            # Width = k1 - k2 (put spread width) or k4 - k3 (call spread width)
            # Max loss = width - net credit
            width_put = k1 - k2_val
            width_call = k4 - k3
            width = min(width_put, width_call)
            max_loss = width - net_prem if net_prem < width else 0.0

        # 构建 PnL 表
        pnl_list = []
        for i in range(len(spot_range)):
            pnl_list.append({
                "spot_price_at_expiry": round(float(spot_range[i]), 4),
                "pnl": round(float(pnl[i]), 4),
            })

        # 盈亏平衡点过滤（确保在价格范围内且合理）
        be_points = [p for p in be_points if 0 <= p <= 2 * s0]

        payload = {
            "status": "ok",
            "strategy": strategy_info["label"],
            "strategy_description": strategy_info["description"],
            "legs": legs_desc,
            "max_profit": round(max_profit, 4) if max_profit is not None else "无穷（理论上限）",
            "max_loss": round(max_loss, 4) if max_loss is not None else "无穷（理论下限）",
            "break_even_points": be_points,
            "pnl_table": pnl_list,
            "visualization_note": (
                "以上盈亏为到期日损益（不考虑时间价值）。"
                "PnL 表可导入 Excel / matplotlib 进行可视化。"
            ),
            "parameters_used": {
                "strategy_type": strategy,
                "spot_price": s0,
                "strike1": k1,
                "strike2": strike2 if strike2 is not None else k2 if strategy in ("covered_call", "protective_put", "straddle") else k2 if strategy in ("strangle", "bull_spread", "bear_spread") else k2_val if strategy == "iron_condor" else None,
                "premium1": premium1,
                "premium2": premium2,
                "time_to_expiry_years": time_to_expiry,
                "volatility": volatility,
            },
            "methodology": (
                "到期日盈亏计算：PnL = 各腿内在价值之和 - 净权利金支出（+ 净权利金收入）。"
                "covered_call: PnL = (S_T - S_0) + premium - max(S_T - K, 0)；"
                "protective_put: PnL = (S_T - S_0) - premium + max(K - S_T, 0)；"
                "straddle: PnL = |S_T - K| - 2×premium；"
                "strangle: PnL = max(K1 - S_T, 0) + max(S_T - K2, 0) - (prem1 + prem2)；"
                "bull_spread: PnL = max(S_T-K1,0) - max(S_T-K2,0) - prem1 + prem2；"
                "bear_spread: PnL = max(K1-S_T,0) - max(K2-S_T,0) - prem1 + prem2；"
                "iron_condor: 4腿组合 = bear put spread + bull call spread。"
            ),
        }

        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("期权策略盈亏分析失败: %s", exc, exc_info=True)
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2, default=str)


__all__ = [
    "get_black_scholes_price",
    "get_implied_volatility",
    "get_option_greeks",
    "get_option_strategy_pnl",
]