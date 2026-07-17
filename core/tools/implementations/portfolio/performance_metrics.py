"""
投资组合绩效指标工具

提供 Beta 系数、夏普比率、VaR 风险价值等专业投资组合绩效指标计算。
所有指标基于纯数学计算，无需 LLM 参与。
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Annotated, Optional

import numpy as np
import pandas as pd
from langchain_core.tools import tool

from core.skill_runtime.data_access import get_stock_daily_quotes
from core.tools.base import register_tool

logger = logging.getLogger(__name__)


# ============================================================
#  辅助函数
# ============================================================

def _safe_float(value) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        numeric = float(value)
        if numeric != numeric:
            return None
        return numeric
    except (TypeError, ValueError):
        return None


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _days_ago(days: int) -> str:
    return (datetime.now() - timedelta(days=max(1, int(days)))).strftime("%Y-%m-%d")


# ============================================================
#  Tool 1: Beta 系数计算
# ============================================================

@tool
@register_tool(
    tool_id="get_beta_calculation",
    name="Beta 系数计算",
    description="计算个股相对基准指数的 Beta、Alpha、R² 和相关系数，返回回归统计、残差分析和数据点信息，用于衡量系统风险敞口",
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["risk_analysis"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["beta_calculation", "systematic_risk"],
    when_to_use="当需要衡量个股相对大盘的系统风险敞口，或评估股票与基准的联动性时使用。",
    when_not_to_use="当数据不足（少于30个交易日）或基准数据缺失且无法回退时返回警告。",
    returns="返回 JSON，包含 symbol、beta、alpha_annualized、r_squared、correlation、data_points、period_days、warnings。",
    example="get_beta_calculation(symbol='600519', benchmark='000300', lookback_days=252)",
    related_tools=["get_sharpe_ratio", "get_var_calculation"],
)
def get_beta_calculation(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"],
    benchmark: Annotated[Optional[str], "基准指数代码，默认 000300（沪深300）"] = "000300",
    lookback_days: Annotated[int, "回看交易日数，默认252（约1年）"] = 252,
) -> str:
    """计算个股相对基准指数的 Beta 系数。同时给出 Alpha、R²、相关系数等回归指标，衡量系统风险敞口。

    Args:
        symbol: A 股股票代码，如 600519、000001
        benchmark: 基准指数代码，默认 "000300"（沪深300）
        lookback_days: 回看交易日数，默认 252（约 1 年）

    Returns:
        str: JSON 字符串，字段说明——
            status: "success" | "error"
            symbol: 标的股票代码
            beta: Beta 系数（基准缺失或方差为 0 时回退为 1.0）
            alpha_annualized: 年化 Alpha（基准不可用时为 None）
            r_squared: 决定系数 R²（基准不可用时为 None）
            correlation: 相关系数（基准不可用时为 None）
            data_points: 实际使用的有效收益率样本数
            period_days: 入参 lookback_days
            benchmark: 实际使用的基准代码
            warnings: list[str]，过程中产生的告警信息
            message: 当 status 为 "error" 时的错误描述
    """
    try:
        end_date = _today()
        start_date = _days_ago(int(lookback_days) * 2 + 50)

        stock_quotes = get_stock_daily_quotes(
            str(symbol), start_date, end_date, limit=int(lookback_days) + 100
        )
        benchmark_quotes = get_stock_daily_quotes(
            str(benchmark), start_date, end_date, limit=int(lookback_days) + 100
        )

        warnings: list = []

        if not stock_quotes:
            return json.dumps(
                {"status": "error", "message": f"未获取到 {symbol} 的日线数据。", "warnings": warnings},
                ensure_ascii=False, indent=2, default=str,
            )

        stock_df = pd.DataFrame(stock_quotes)
        stock_df["close"] = stock_df["close"].apply(_safe_float)
        stock_df["trade_date"] = stock_df["trade_date"].astype(str)
        stock_df = stock_df.dropna(subset=["close"]).sort_values("trade_date")
        stock_df["return"] = stock_df["close"].pct_change()
        stock_df = stock_df.dropna(subset=["return"])

        if len(stock_df) < 30:
            return json.dumps(
                {"status": "error", "message": f"{symbol} 有效收益率数据少于30个交易日，无法可靠计算 Beta。",
                 "warnings": warnings},
                ensure_ascii=False, indent=2, default=str,
            )

        # 处理基准数据
        no_benchmark = False
        if not benchmark_quotes:
            warnings.append(f"未获取到基准指数 {benchmark} 的日线数据，使用市场默认 beta=1.0。")
            no_benchmark = True
        else:
            bench_df = pd.DataFrame(benchmark_quotes)
            bench_df["close"] = bench_df["close"].apply(_safe_float)
            bench_df["trade_date"] = bench_df["trade_date"].astype(str)
            bench_df = bench_df.dropna(subset=["close"]).sort_values("trade_date")
            bench_df["return"] = bench_df["close"].pct_change()
            bench_df = bench_df.dropna(subset=["return"])

            if len(bench_df) < 20:
                warnings.append(f"基准指数 {benchmark} 有效收益率数据不足20个交易日，使用市场默认 beta=1.0。")
                no_benchmark = True

        if no_benchmark:
            payload = {
                "status": "success",
                "symbol": str(symbol),
                "beta": 1.0,
                "alpha_annualized": None,
                "r_squared": None,
                "correlation": None,
                "data_points": len(stock_df),
                "period_days": int(lookback_days),
                "benchmark": str(benchmark),
                "warnings": warnings,
            }
            return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

        # 对齐日期
        merged = pd.merge(
            stock_df[["trade_date", "return"]],
            bench_df[["trade_date", "return"]],
            on="trade_date",
            how="inner",
            suffixes=("_stock", "_bench"),
        )

        if len(merged) < 30:
            warnings.append(f"股票与基准重叠交易日仅 {len(merged)} 天，不足30天，结果参考价值有限。")

        stock_returns = merged["return_stock"]
        bench_returns = merged["return_bench"]

        # Beta = Cov(stock, bench) / Var(bench)
        cov_matrix = np.cov(stock_returns, bench_returns)
        bench_var = np.var(bench_returns, ddof=1)

        if bench_var == 0:
            payload = {
                "status": "success",
                "symbol": str(symbol),
                "beta": 1.0,
                "alpha_annualized": None,
                "r_squared": None,
                "correlation": None,
                "data_points": len(merged),
                "period_days": int(lookback_days),
                "benchmark": str(benchmark),
                "warnings": warnings + ["基准收益率方差为零，无法计算 Beta。"],
            }
            return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

        beta = cov_matrix[0, 1] / bench_var if len(cov_matrix) > 1 else float(np.cov(stock_returns, bench_returns)[0, 1] / bench_var)

        # Alpha (annualized)
        alpha_daily = stock_returns.mean() - beta * bench_returns.mean()
        alpha_annualized = alpha_daily * 252

        # Correlation
        correlation = float(np.corrcoef(stock_returns, bench_returns)[0, 1])

        # R²
        r_squared = float(correlation ** 2)

        payload = {
            "status": "success",
            "symbol": str(symbol),
            "beta": float(round(beta, 4)),
            "alpha_annualized": float(round(alpha_annualized, 6)),
            "r_squared": float(round(r_squared, 4)),
            "correlation": float(round(correlation, 4)),
            "data_points": len(merged),
            "period_days": int(lookback_days),
            "benchmark": str(benchmark),
            "warnings": warnings,
        }
        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("Beta 系数计算失败: %s", exc, exc_info=True)
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2, default=str)


# ============================================================
#  Tool 2: 夏普比率
# ============================================================

@tool
@register_tool(
    tool_id="get_sharpe_ratio",
    name="夏普比率",
    description="计算综合风险调整收益指标，返回夏普比率、索提诺比率、卡尔玛比率、年化收益率、波动率、最大回撤等综合指标，用于评估风险收益",
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["risk_analysis", "performance"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["risk_adjusted_return", "performance_evaluation"],
    when_to_use="当需要评估股票的风险调整后收益，或比较不同资产的风险收益特征时使用。",
    when_not_to_use="当数据不足（少于30个交易日）时，指标参考价值有限。",
    returns="返回 JSON，包含 sharpe_ratio、sortino_ratio、calmar_ratio、annual_return、annual_volatility、max_drawdown、data_points、interpretation。",
    example="get_sharpe_ratio(symbol='600519', risk_free_rate=0.025, lookback_days=252)",
    related_tools=["get_beta_calculation", "get_var_calculation"],
)
def get_sharpe_ratio(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"],
    risk_free_rate: Annotated[Optional[float], "无风险利率，默认 0.025（2.5%）"] = 0.025,
    lookback_days: Annotated[int, "回看交易日数，默认252（约1年）"] = 252,
) -> str:
    """计算综合风险调整收益指标。包括夏普、索提诺、卡尔玛比率，以及年化收益、年化波动率、最大回撤。

    Args:
        symbol: A 股股票代码，如 600519、000001
        risk_free_rate: 无风险利率，默认 0.025（2.5%）
        lookback_days: 回看交易日数，默认 252（约 1 年）

    Returns:
        str: JSON 字符串，字段说明——
            status: "success" | "error"
            symbol: 标的股票代码
            sharpe_ratio: 年化夏普比率（不可计算时为 None）
            sortino_ratio: 年化索提诺比率（下行样本不足时为 None）
            calmar_ratio: 卡尔玛比率（最大回撤为 0 时为 None）
            annual_return: 年化收益率
            annual_volatility: 年化波动率
            max_drawdown: 最大回撤（负数）
            risk_free_rate: 实际使用的无风险利率
            data_points: 有效收益率样本数
            interpretation: 风险调整收益评价文案
            warnings: list[str]，过程中产生的告警信息
            message: 当 status 为 "error" 时的错误描述
    """
    try:
        end_date = _today()
        start_date = _days_ago(int(lookback_days) * 2 + 50)

        quotes = get_stock_daily_quotes(
            str(symbol), start_date, end_date, limit=int(lookback_days) + 100
        )

        if not quotes:
            return json.dumps(
                {"status": "error", "message": f"未获取到 {symbol} 的日线数据。"},
                ensure_ascii=False, indent=2, default=str,
            )

        warnings: list = []

        df = pd.DataFrame(quotes)
        df["close"] = df["close"].apply(_safe_float)
        df["trade_date"] = df["trade_date"].astype(str)
        df = df.dropna(subset=["close"]).sort_values("trade_date")
        df["return"] = df["close"].pct_change()
        df = df.dropna(subset=["return"])

        returns = df["return"].values
        close_prices = df["close"].values

        if len(returns) < 30:
            warnings.append(f"有效收益率数据仅 {len(returns)} 天，不足30天，指标参考价值有限。")

        rf = float(risk_free_rate) if risk_free_rate is not None else 0.025
        daily_rf = rf / 252

        excess_returns = returns - daily_rf
        mean_excess = np.mean(excess_returns)
        std_excess = np.std(excess_returns, ddof=1)

        # Sharpe ratio (annualized)
        if std_excess > 0:
            sharpe_ratio = (mean_excess / std_excess) * np.sqrt(252)
        else:
            sharpe_ratio = 0.0 if mean_excess == 0 else float("inf") if mean_excess > 0 else float("-inf")

        # Sortino ratio (using downside deviation)
        downside_returns = returns[returns < 0]
        if len(downside_returns) >= 2:
            downside_std = np.std(downside_returns, ddof=1)
            sortino_ratio = (mean_excess / downside_std) * np.sqrt(252) if downside_std > 0 else 0.0
        else:
            sortino_ratio = None

        # Annual return
        cumulative_return = (1 + returns).prod()
        n_days = len(returns)
        annual_return = cumulative_return ** (252 / n_days) - 1

        # Annual volatility
        annual_volatility = std_excess * np.sqrt(252)

        # Max drawdown
        cumulative = np.cumprod(1 + returns)
        peak = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - peak) / peak
        max_drawdown = float(np.min(drawdown))

        # Calmar ratio
        if max_drawdown < 0 and abs(max_drawdown) > 0:
            calmar_ratio = annual_return / abs(max_drawdown)
        else:
            calmar_ratio = None

        # Interpretation
        if sharpe_ratio > 2:
            interpretation = "优秀 — 风险调整收益极佳"
        elif sharpe_ratio > 1:
            interpretation = "良好 — 风险调整收益较好"
        elif sharpe_ratio > 0.5:
            interpretation = "一般 — 风险调整收益适中"
        elif sharpe_ratio > 0:
            interpretation = "较差 — 风险调整收益偏低"
        else:
            interpretation = "差 — 收益未跑赢无风险利率"

        payload = {
            "status": "success",
            "symbol": str(symbol),
            "sharpe_ratio": float(round(sharpe_ratio, 4)) if np.isfinite(sharpe_ratio) else None,
            "sortino_ratio": float(round(sortino_ratio, 4)) if sortino_ratio is not None and np.isfinite(sortino_ratio) else None,
            "calmar_ratio": float(round(calmar_ratio, 4)) if calmar_ratio is not None and np.isfinite(calmar_ratio) else None,
            "annual_return": float(round(annual_return, 6)),
            "annual_volatility": float(round(annual_volatility, 6)),
            "max_drawdown": float(round(max_drawdown, 6)),
            "risk_free_rate": rf,
            "data_points": len(returns),
            "interpretation": interpretation,
            "warnings": warnings,
        }
        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("夏普比率计算失败: %s", exc, exc_info=True)
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2, default=str)


# ============================================================
#  Tool 3: VaR 风险价值计算
# ============================================================

@tool
@register_tool(
    tool_id="get_var_calculation",
    name="VaR 风险价值计算",
    description="计算历史模拟法和参数法的 VaR（在险价值）与 CVaR（条件在险价值/预期亏损），支持日度和年化输出。",
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["risk_analysis", "downside_risk"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["var_calculation", "tail_risk", "risk_management"],
    when_to_use="当需要量化下尾风险，评估在给定置信度下的最大可能亏损时使用。",
    when_not_to_use="当数据不足（少于30个交易日）时，VaR 参考价值有限。",
    returns="返回 JSON，包含 method、confidence、var_daily、var_annual、cvar_daily、cvar_annual、data_points、interpretation。",
    example="get_var_calculation(symbol='600519', confidence=0.95, lookback_days=252, method='historical')",
    related_tools=["get_beta_calculation", "get_sharpe_ratio"],
)
def get_var_calculation(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"],
    confidence: Annotated[float, "置信度水平，默认 0.95"] = 0.95,
    lookback_days: Annotated[int, "回看交易日数，默认252（约1年）"] = 252,
    method: Annotated[str, "计算方法：historical（历史模拟法）或 parametric（参数法）"] = "historical",
) -> str:
    """计算 VaR 风险价值。基于历史模拟法或参数法计算日度/年化 VaR 与 CVaR（预期亏损）。

    Args:
        symbol: A 股股票代码，如 600519、000001
        confidence: 置信度水平，默认 0.95
        lookback_days: 回看交易日数，默认 252（约 1 年）
        method: 计算方法，默认 "historical"；可选 "historical"（历史模拟法）或 "parametric"（参数法），
            非法值会回退为 "historical"

    Returns:
        str: JSON 字符串，字段说明——
            status: "success" | "error"
            symbol: 标的股票代码
            method: 实际使用的计算方法，"historical" 或 "parametric"
            confidence: 实际使用的置信度（被夹取到 [0.5, 0.999]）
            var_daily: 日度 VaR（负数表示亏损）
            var_annual: 年化 VaR
            cvar_daily: 日度 CVaR / 预期亏损
            cvar_annual: 年化 CVaR / 预期亏损
            data_points: 有效收益率样本数
            interpretation: 风险等级评价文案（scipy 缺失重试场景下为 None）
            warnings: list[str]，过程中产生的告警信息
            message: 当 status 为 "error" 时的错误描述
    """
    try:
        end_date = _today()
        start_date = _days_ago(int(lookback_days) * 2 + 50)

        quotes = get_stock_daily_quotes(
            str(symbol), start_date, end_date, limit=int(lookback_days) + 100
        )

        if not quotes:
            return json.dumps(
                {"status": "error", "message": f"未获取到 {symbol} 的日线数据。"},
                ensure_ascii=False, indent=2, default=str,
            )

        warnings: list = []

        df = pd.DataFrame(quotes)
        df["close"] = df["close"].apply(_safe_float)
        df["trade_date"] = df["trade_date"].astype(str)
        df = df.dropna(subset=["close"]).sort_values("trade_date")
        df["return"] = df["close"].pct_change()
        df = df.dropna(subset=["return"])

        returns = df["return"].values

        if len(returns) < 30:
            warnings.append(f"有效收益率数据仅 {len(returns)} 天，不足30天，VaR 参考价值有限。")

        conf = float(confidence)
        cl = max(0.5, min(0.999, conf))
        alpha = 1.0 - cl
        chosen_method = str(method).strip().lower()

        if chosen_method not in ("historical", "parametric"):
            chosen_method = "historical"
            warnings.append(f"不支持的方法 '{method}'，已回退为 historical。")

        # Historical VaR
        hist_var_daily = float(np.percentile(returns, alpha * 100))

        # Historical CVaR (Expected Shortfall)
        tail_returns = returns[returns <= hist_var_daily]
        if len(tail_returns) > 0:
            hist_cvar_daily = float(np.mean(tail_returns))
        else:
            hist_cvar_daily = hist_var_daily

        # Parametric VaR
        from scipy.stats import norm as scipy_norm

        mu = np.mean(returns)
        sigma = np.std(returns, ddof=1)
        z_score = scipy_norm.ppf(alpha)  # negative for alpha < 0.5
        param_var_daily = mu + z_score * sigma

        # Parametric CVaR
        param_cvar_daily = mu - sigma * scipy_norm.pdf(z_score) / alpha

        # Annualize (square root of time rule)
        sqrt252 = np.sqrt(252)

        if chosen_method == "historical":
            var_daily = hist_var_daily
            var_annual = hist_var_daily * sqrt252
            cvar_daily = hist_cvar_daily
            cvar_annual = hist_cvar_daily * sqrt252
        else:
            var_daily = param_var_daily
            var_annual = param_var_daily * sqrt252
            cvar_daily = param_cvar_daily
            cvar_annual = param_cvar_daily * sqrt252

        # Interpretation
        var_pct = abs(var_daily) * 100
        if var_pct > 6:
            interpretation = "极高风险 — 日VaR超过6%"
        elif var_pct > 4:
            interpretation = "高风险 — 日VaR在4%-6%之间"
        elif var_pct > 2:
            interpretation = "中等风险 — 日VaR在2%-4%之间"
        elif var_pct > 1:
            interpretation = "低风险 — 日VaR在1%-2%之间"
        else:
            interpretation = "极低风险 — 日VaR低于1%"

        payload = {
            "status": "success",
            "symbol": str(symbol),
            "method": chosen_method,
            "confidence": cl,
            "var_daily": float(round(var_daily, 6)),
            "var_annual": float(round(var_annual, 6)),
            "cvar_daily": float(round(cvar_daily, 6)),
            "cvar_annual": float(round(cvar_annual, 6)),
            "data_points": len(returns),
            "interpretation": interpretation,
            "warnings": warnings,
        }
        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    except ImportError:
        logger.warning("scipy 未安装，VaR 参数法不可用，回退至历史模拟法。")
        # 重试仅历史模拟法
        try:
            end_date = _today()
            start_date = _days_ago(int(lookback_days) * 2 + 50)
            quotes = get_stock_daily_quotes(str(symbol), start_date, end_date, limit=int(lookback_days) + 100)
            if not quotes:
                return json.dumps({"status": "error", "message": f"未获取到 {symbol} 的日线数据。"}, ensure_ascii=False, indent=2, default=str)

            df = pd.DataFrame(quotes)
            df["close"] = df["close"].apply(_safe_float)
            df["trade_date"] = df["trade_date"].astype(str)
            df = df.dropna(subset=["close"]).sort_values("trade_date")
            df["return"] = df["close"].pct_change()
            df = df.dropna(subset=["return"])
            returns = df["return"].values
            conf = float(confidence)
            cl = max(0.5, min(0.999, conf))
            alpha = 1.0 - cl
            var_daily = float(np.percentile(returns, alpha * 100))
            tail_returns = returns[returns <= var_daily]
            cvar_daily = float(np.mean(tail_returns)) if len(tail_returns) > 0 else var_daily
            sqrt252 = np.sqrt(252)
            payload = {
                "status": "success",
                "symbol": str(symbol),
                "method": "historical",
                "confidence": cl,
                "var_daily": float(round(var_daily, 6)),
                "var_annual": float(round(var_daily * sqrt252, 6)),
                "cvar_daily": float(round(cvar_daily, 6)),
                "cvar_annual": float(round(cvar_daily * sqrt252, 6)),
                "data_points": len(returns),
                "interpretation": None,
                "warnings": ["scipy 未安装，仅支持历史模拟法。"],
            }
            return json.dumps(payload, ensure_ascii=False, indent=2, default=str)
        except Exception as exc2:
            logger.error("VaR 计算失败: %s", exc2, exc_info=True)
            return json.dumps({"status": "error", "message": str(exc2)}, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("VaR 计算失败: %s", exc, exc_info=True)
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2, default=str)


__all__ = [
    "get_beta_calculation",
    "get_sharpe_ratio",
    "get_var_calculation",
]
