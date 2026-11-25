"""
扩展投资组合绩效指标工具

提供 Sortino 比率、Treynor 比率、信息比率、Calmar 比率、Jensen Alpha、
压力测试、情景分析、Brinson 归因、行业归因等专业投资组合绩效分析功能。
所有指标基于纯数学计算，无需 LLM 参与。
"""

import json
import logging
import math
from datetime import datetime, timedelta
from typing import Annotated, Optional, Any, List

import numpy as np
from langchain_core.tools import tool

from core.skill_runtime.data_access import get_stock_daily_quotes, get_stock_basic_info
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


def _load_returns(symbol: str, lookback_days: int) -> Optional[np.ndarray]:
    """获取单只股票的日收益率序列。"""
    end_date = _today()
    start_date = _days_ago(int(lookback_days) * 2 + 50)
    quotes = get_stock_daily_quotes(
        str(symbol), start_date, end_date, limit=int(lookback_days) + 100
    )
    if not quotes:
        return None
    import pandas as pd
    df = pd.DataFrame(quotes)
    df["close"] = df["close"].apply(_safe_float)
    df["trade_date"] = df["trade_date"].astype(str)
    df = df.dropna(subset=["close"]).sort_values("trade_date")
    df["return"] = df["close"].pct_change()
    df = df.dropna(subset=["return"])
    return df["return"].values


def _load_benchmark_returns(lookback_days: int = 252) -> Optional[np.ndarray]:
    """从本地 DB 获取基准指数（沪深300）收益率，失败时用 AKShare 兜底。"""
    import pandas as pd
    end = _today()
    start = _days_ago(lookback_days * 2 + 50)
    # 先试 000300
    quotes = get_stock_daily_quotes("000300", start, end, limit=lookback_days + 100)
    if quotes:
        df = pd.DataFrame(quotes)
        df["close"] = df["close"].apply(_safe_float)
        df["trade_date"] = df["trade_date"].astype(str)
        df = df.dropna(subset=["close"]).sort_values("trade_date")
        df["return"] = df["close"].pct_change()
        return df["return"].dropna().values
    # DB 无数据，用 AKShare 兜底
    try:
        import akshare as ak
        df = ak.stock_zh_index_daily(symbol="sh000300")
        df = df.sort_values("date")
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        df["return"] = df["close"].pct_change()
        df = df.dropna(subset=["return"]).tail(lookback_days)
        return df["return"].values
    except Exception:
        return None


def _annualized_return(returns: np.ndarray) -> float:
    n = len(returns)
    if n == 0:
        return 0.0
    cumulative = float(np.prod(1 + returns))
    return cumulative ** (252.0 / n) - 1


def _max_drawdown_from_returns(returns: np.ndarray) -> float:
    cumulative = np.cumprod(1 + returns)
    peak = np.maximum.accumulate(cumulative)
    drawdown = (cumulative - peak) / peak
    return float(np.min(drawdown))


def _parse_symbols_weights(symbols_str: str, weights_str: Optional[str] = None):
    """解析符号和权重字符串，返回 (symbols_list, weights_list_or_equal)."""
    sym_list = [s.strip() for s in str(symbols_str).split(",") if s.strip()]
    if weights_str:
        w_list = [float(w.strip()) for w in str(weights_str).split(",") if w.strip()]
        # 如果权重数量与符号数量不一致，回退等权
        if len(w_list) != len(sym_list):
            w_list = [1.0 / len(sym_list)] * len(sym_list)
        else:
            total = sum(w_list)
            if total > 0:
                w_list = [w / total for w in w_list]
    else:
        w_list = [1.0 / len(sym_list)] * len(sym_list) if sym_list else []
    return sym_list, w_list


# ============================================================
#  Tool 1: Sortino 比率
# ============================================================

@tool
@register_tool(
    tool_id="get_sortino_ratio",
    name="Sortino 比率",
    description="计算 Sortino 比率衡量下行风险调整后收益，返回年化收益、下行波动率、Sortino 比率、目标收益率和样本数，用于评估资产收益",
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["risk_analysis", "performance"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["sortino_ratio", "downside_risk_adjusted_return"],
    when_to_use="当需要评估资产的风险调整收益，且希望只惩罚下行波动而非整体波动时使用。",
    when_not_to_use="当数据不足（少于30个交易日）时指标参考价值有限。",
    returns="返回 JSON，包含 sortino_ratio、downside_deviation、annualized_return、excess_return。",
    example="get_sortino_ratio(symbol='600519', lookback_days=252, risk_free_rate=0.025)",
    related_tools=["get_sharpe_ratio", "get_calmar_ratio"],
)
def get_sortino_ratio(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"],
    lookback_days: Annotated[int, "回看交易日数，默认252（约1年）"] = 252,
    risk_free_rate: Annotated[float, "无风险利率，默认 0.025（2.5%）"] = 0.025,
    target_return: Annotated[float, "目标收益率，默认 0.0"] = 0.0,
) -> str:
    """计算 Sortino 比率。仅以负收益偏离（下行偏差）作为风险度量，衡量单位下行风险的超额收益。

    Args:
        symbol: A 股股票代码，如 600519、000001
        lookback_days: 回看交易日数，默认 252（约 1 年）
        risk_free_rate: 无风险利率，默认 0.025（2.5%）
        target_return: 目标收益率（MAR），默认 0.0

    Returns:
        str: JSON 字符串，字段说明——
            status: "success" | "error"
            symbol: 标的股票代码
            sortino_ratio: 年化 Sortino 比率（不可计算时为 None）
            downside_deviation: 年化下行偏差
            annualized_return: 年化收益率
            excess_return: 年化超额收益（年化收益 - 无风险利率）
            risk_free_rate: 实际使用的无风险利率
            target_return: 实际使用的目标收益率
            data_points: 有效收益率样本数
            warnings: list[str]，过程中产生的告警信息
            message: 当 status 为 "error" 时的错误描述
    """
    try:
        warnings: list = []
        rf = float(risk_free_rate) if risk_free_rate is not None else 0.025
        target = float(target_return)
        returns = _load_returns(str(symbol), int(lookback_days))

        if returns is None or len(returns) < 30:
            return json.dumps(
                {"status": "error", "message": f"未获取到 {symbol} 足够的历史数据（需要至少30个交易日）。"},
                ensure_ascii=False, indent=2, default=str,
            )

        # 年化收益率
        ann_return = _annualized_return(returns)

        # 超额收益 (Rp - Rf)
        excess_return = ann_return - rf

        # 下行偏差：收益率低于 target_return 部分的标准差
        downside_returns = returns[returns < target]
        if len(downside_returns) >= 2:
            downside_deviation = float(np.std(downside_returns, ddof=1)) * np.sqrt(252)
        elif len(downside_returns) == 1:
            downside_deviation = float(np.std(downside_returns, ddof=0)) * np.sqrt(252)
        else:
            downside_deviation = 0.0

        # Sortino 比率
        if downside_deviation > 0:
            sortino_ratio = excess_return / downside_deviation
        else:
            sortino_ratio = None if excess_return == 0 else (float("inf") if excess_return > 0 else float("-inf"))

        payload = {
            "status": "success",
            "symbol": str(symbol),
            "sortino_ratio": float(round(sortino_ratio, 4)) if sortino_ratio is not None and np.isfinite(sortino_ratio) else None,
            "downside_deviation": float(round(downside_deviation, 6)),
            "annualized_return": float(round(ann_return, 6)),
            "excess_return": float(round(excess_return, 6)),
            "risk_free_rate": rf,
            "target_return": target,
            "data_points": len(returns),
            "warnings": warnings,
        }
        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("Sortino 比率计算失败: %s", exc, exc_info=True)
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2, default=str)


# ============================================================
#  Tool 2: Treynor 比率
# ============================================================

@tool
@register_tool(
    tool_id="get_treynor_ratio",
    name="Treynor 比率",
    description="计算 Treynor 比率衡量单位系统性风险超额收益，返回超额收益、Beta、Treynor 比率、无风险利率和样本区间",
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["risk_analysis", "performance"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["treynor_ratio", "systematic_risk_adjusted_return"],
    when_to_use="当需要评估资产相对于系统性风险的超额收益表现时使用。",
    when_not_to_use="当数据不足或 Beta 无法计算时指标不可用。",
    returns="返回 JSON，包含 treynor_ratio、beta、annualized_return、excess_return。",
    example="get_treynor_ratio(symbol='600519', lookback_days=252, risk_free_rate=0.025)",
    related_tools=["get_beta_calculation", "get_sortino_ratio"],
)
def get_treynor_ratio(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"],
    lookback_days: Annotated[int, "回看交易日数，默认252（约1年）"] = 252,
    risk_free_rate: Annotated[float, "无风险利率，默认 0.025（2.5%）"] = 0.025,
) -> str:
    """计算 Treynor 比率。以 Beta 衡量系统性风险，衡量单位系统性风险的超额收益。

    Args:
        symbol: A 股股票代码，如 600519、000001
        lookback_days: 回看交易日数，默认 252（约 1 年）
        risk_free_rate: 无风险利率，默认 0.025（2.5%）

    Returns:
        str: JSON 字符串，字段说明——
            status: "success" | "error"
            symbol: 标的股票代码
            treynor_ratio: Treynor 比率（不可计算时为 None）
            beta: 相对沪深300 的 Beta 系数（Beta 计算失败时回退为 1.0）
            annualized_return: 年化收益率
            excess_return: 年化超额收益
            risk_free_rate: 实际使用的无风险利率
            data_points: 有效收益率样本数
            warnings: list[str]，过程中产生的告警信息
            message: 当 status 为 "error" 时的错误描述
    """
    try:
        warnings: list = []
        sym = str(symbol)
        rf = float(risk_free_rate) if risk_free_rate is not None else 0.025
        ldays = int(lookback_days)

        returns = _load_returns(sym, ldays)
        if returns is None or len(returns) < 30:
            return json.dumps(
                {"status": "error", "message": f"未获取到 {sym} 足够的历史数据（需要至少30个交易日）。"},
                ensure_ascii=False, indent=2, default=str,
            )

        # 从 get_beta_calculation 获取 Beta
        from core.tools.registry import ToolRegistry as _TR
        _reg = _TR()
        beta_raw = _reg.get_function('get_beta_calculation')
        beta_result_str = beta_raw(symbol=sym, benchmark="000300", lookback_days=ldays)
        beta_result = json.loads(beta_result_str)

        if beta_result.get("status") == "error":
            warnings.append(f"Beta 计算异常: {beta_result.get('message')}")
            beta = 1.0
        else:
            beta = beta_result.get("beta", 1.0)
            if beta_result.get("warnings"):
                warnings.extend(beta_result.get("warnings"))

        if beta == 0:
            return json.dumps(
                {"status": "error", "message": "Beta 为零，无法计算 Treynor 比率。"},
                ensure_ascii=False, indent=2, default=str,
            )

        # 年化收益率
        ann_return = _annualized_return(returns)
        excess_return = ann_return - rf
        treynor_ratio = excess_return / beta

        payload = {
            "status": "success",
            "symbol": sym,
            "treynor_ratio": float(round(treynor_ratio, 6)) if np.isfinite(treynor_ratio) else None,
            "beta": float(round(beta, 4)),
            "annualized_return": float(round(ann_return, 6)),
            "excess_return": float(round(excess_return, 6)),
            "risk_free_rate": rf,
            "data_points": len(returns),
            "warnings": warnings,
        }
        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("Treynor 比率计算失败: %s", exc, exc_info=True)
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2, default=str)


# ============================================================
#  Tool 3: 信息比率
# ============================================================

@tool
@register_tool(
    tool_id="get_information_ratio",
    name="信息比率",
    description="计算信息比率（Information Ratio），衡量投资组合相对于基准指数的超额收益与跟踪误差之比。",
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["risk_analysis", "performance"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["information_ratio", "active_management"],
    when_to_use="当需要评估主动管理能力，衡量相对于基准的超额收益稳定性时使用。",
    when_not_to_use="当数据不足跟踪误差无法可靠计算时指标参考价值有限。",
    returns="返回 JSON，包含 information_ratio、tracking_error、excess_return。",
    example="get_information_ratio(symbol='600519', benchmark_symbol='000300', lookback_days=252)",
    related_tools=["get_sortino_ratio", "get_treynor_ratio"],
)
def get_information_ratio(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"],
    benchmark_symbol: Annotated[str, "基准指数代码，默认 000300（沪深300）"] = "000300",
    lookback_days: Annotated[int, "回看交易日数，默认252（约1年）"] = 252,
) -> str:
    """计算信息比率。衡量组合相对基准的超额收益与跟踪误差之比。

    Args:
        symbol: A 股股票代码，如 600519、000001
        benchmark_symbol: 基准指数代码，默认 "000300"（沪深300）
        lookback_days: 回看交易日数，默认 252（约 1 年）

    Returns:
        str: JSON 字符串，字段说明——
            status: "success" | "error"
            symbol: 标的股票代码
            benchmark_symbol: 实际使用的基准代码
            information_ratio: 信息比率
            tracking_error: 年化跟踪误差
            excess_return: 年化超额收益
            data_points: 实际对齐使用的样本数
            warnings: list[str]，过程中产生的告警信息
            message: 当 status 为 "error" 时的错误描述
    """
    try:
        warnings: list = []
        sym = str(symbol)
        bench = str(benchmark_symbol)
        ldays = int(lookback_days)

        stock_returns = _load_returns(sym, ldays)

        # 基准指数：000300 用 AKShare 兜底
        if bench in ("000300", "399300", "sh000300"):
            benchmark_returns = _load_benchmark_returns(ldays)
        else:
            benchmark_returns = _load_returns(bench, ldays)

        if stock_returns is None or len(stock_returns) < 30:
            return json.dumps(
                {"status": "error", "message": f"未获取到 {sym} 足够的历史数据。"},
                ensure_ascii=False, indent=2, default=str,
            )

        if benchmark_returns is None or len(benchmark_returns) < 30:
            return json.dumps(
                {"status": "error", "message": f"未获取到基准 {bench} 足够的历史数据。"},
                ensure_ascii=False, indent=2, default=str,
            )

        # 对齐长度（取较短者）
        min_len = min(len(stock_returns), len(benchmark_returns))
        stock_r = stock_returns[-min_len:]
        bench_r = benchmark_returns[-min_len:]

        # 超额收益序列
        excess_series = stock_r - bench_r
        excess_return = float(np.mean(excess_series) * 252)
        tracking_error = float(np.std(excess_series, ddof=1) * np.sqrt(252))

        if tracking_error > 0:
            information_ratio = excess_return / tracking_error
        else:
            information_ratio = 0.0

        payload = {
            "status": "success",
            "symbol": sym,
            "benchmark_symbol": bench,
            "information_ratio": float(round(information_ratio, 4)),
            "tracking_error": float(round(tracking_error, 6)),
            "excess_return": float(round(excess_return, 6)),
            "data_points": min_len,
            "warnings": warnings,
        }
        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("信息比率计算失败: %s", exc, exc_info=True)
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2, default=str)


# ============================================================
#  Tool 4: Calmar 比率
# ============================================================

@tool
@register_tool(
    tool_id="get_calmar_ratio",
    name="Calmar 比率",
    description="计算 Calmar 比率衡量年化收益与最大回撤之比，返回年化收益、最大回撤、Calmar 比率和回撤区间，反映资产回撤调整后收益",
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["risk_analysis", "performance"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["calmar_ratio", "drawdown_adjusted_return"],
    when_to_use="当需要评估资产在经历最大回撤后的收益恢复能力时使用。",
    when_not_to_use="当数据不足（少于30个交易日）时指标参考价值有限。",
    returns="返回 JSON，包含 calmar_ratio、annualized_return、max_drawdown。",
    example="get_calmar_ratio(symbol='600519', lookback_days=252)",
    related_tools=["get_sortino_ratio", "get_sharpe_ratio"],
)
def get_calmar_ratio(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"],
    lookback_days: Annotated[int, "回看交易日数，默认252（约1年）"] = 252,
) -> str:
    """计算 Calmar 比率。年化收益率与最大回撤（绝对值）之比，衡量回撤调整后收益。

    Args:
        symbol: A 股股票代码，如 600519、000001
        lookback_days: 回看交易日数，默认 252（约 1 年）

    Returns:
        str: JSON 字符串，字段说明——
            status: "success" | "error"
            symbol: 标的股票代码
            calmar_ratio: Calmar 比率（最大回撤为 0 时为 None）
            annualized_return: 年化收益率
            max_drawdown: 最大回撤（负数）
            data_points: 有效收益率样本数
            warnings: list[str]，过程中产生的告警信息
            message: 当 status 为 "error" 时的错误描述
    """
    try:
        warnings: list = []
        sym = str(symbol)
        ldays = int(lookback_days)

        returns = _load_returns(sym, ldays)
        if returns is None or len(returns) < 30:
            return json.dumps(
                {"status": "error", "message": f"未获取到 {sym} 足够的历史数据（需要至少30个交易日）。"},
                ensure_ascii=False, indent=2, default=str,
            )

        ann_return = _annualized_return(returns)
        max_dd = _max_drawdown_from_returns(returns)

        if max_dd < 0 and abs(max_dd) > 0:
            calmar_ratio = ann_return / abs(max_dd)
        else:
            calmar_ratio = None

        payload = {
            "status": "success",
            "symbol": sym,
            "calmar_ratio": float(round(calmar_ratio, 4)) if calmar_ratio is not None and np.isfinite(calmar_ratio) else None,
            "annualized_return": float(round(ann_return, 6)),
            "max_drawdown": float(round(max_dd, 6)),
            "data_points": len(returns),
            "warnings": warnings,
        }
        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("Calmar 比率计算失败: %s", exc, exc_info=True)
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2, default=str)


# ============================================================
#  Tool 5: Jensen Alpha
# ============================================================

@tool
@register_tool(
    tool_id="get_jensen_alpha",
    name="Jensen Alpha",
    description="计算 Jensen Alpha（詹森阿尔法），衡量投资组合实际收益与 CAPM 模型预期收益之间的差异。",
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["risk_analysis", "performance"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["jensen_alpha", "excess_return_attribution"],
    when_to_use="当需要评估基金经理或资产的超额收益能力，判断收益是否超越市场风险补偿时使用。",
    when_not_to_use="当数据不足或 Beta 无法计算时指标不可用。",
    returns="返回 JSON，包含 jensen_alpha、beta、expected_return、actual_return。",
    example="get_jensen_alpha(symbol='600519', lookback_days=252, risk_free_rate=0.025)",
    related_tools=["get_beta_calculation", "get_treynor_ratio"],
)
def get_jensen_alpha(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"],
    lookback_days: Annotated[int, "回看交易日数，默认252（约1年）"] = 252,
    risk_free_rate: Annotated[float, "无风险利率，默认 0.025（2.5%）"] = 0.025,
) -> str:
    """计算 Jensen Alpha。基于 CAPM 模型衡量组合实际收益与预期收益之差。

    Args:
        symbol: A 股股票代码，如 600519、000001
        lookback_days: 回看交易日数，默认 252（约 1 年）
        risk_free_rate: 无风险利率，默认 0.025（2.5%）

    Returns:
        str: JSON 字符串，字段说明——
            status: "success" | "error"
            symbol: 标的股票代码
            jensen_alpha: Jensen Alpha（实际收益 - CAPM 预期收益）
            beta: 相对沪深300 的 Beta 系数
            expected_return: CAPM 预期收益
            actual_return: 实际年化收益
            market_return: 基准年化收益
            risk_free_rate: 实际使用的无风险利率
            data_points: 实际对齐使用的样本数
            warnings: list[str]，过程中产生的告警信息
            message: 当 status 为 "error" 时的错误描述
    """
    try:
        warnings: list = []
        sym = str(symbol)
        rf = float(risk_free_rate) if risk_free_rate is not None else 0.025
        ldays = int(lookback_days)

        returns = _load_returns(sym, ldays)
        if returns is None or len(returns) < 30:
            return json.dumps(
                {"status": "error", "message": f"未获取到 {sym} 足够的历史数据（需要至少30个交易日）。"},
                ensure_ascii=False, indent=2, default=str,
            )

        # 获取市场收益率（沪深300，AKShare 兜底）
        market_returns = _load_benchmark_returns(ldays)
        if market_returns is None or len(market_returns) < 30:
            return json.dumps(
                {"status": "error", "message": "未获取到基准指数（000300）足够的历史数据，无法计算 Jensen Alpha。"},
                ensure_ascii=False, indent=2, default=str,
            )

        # 对齐
        min_len = min(len(returns), len(market_returns))
        stock_r = returns[-min_len:]
        mkt_r = market_returns[-min_len:]

        # 计算 Beta
        cov = np.cov(stock_r, mkt_r)
        mkt_var = np.var(mkt_r, ddof=1)
        if mkt_var == 0:
            return json.dumps(
                {"status": "error", "message": "基准指数方差为零，无法计算 Beta。"},
                ensure_ascii=False, indent=2, default=str,
            )
        beta = cov[0, 1] / mkt_var

        # 年化收益率
        actual_return = _annualized_return(stock_r)
        market_return = _annualized_return(mkt_r)

        # CAPM 预期收益: E(R) = Rf + beta * (Rm - Rf)
        expected_return = rf + beta * (market_return - rf)

        # Jensen Alpha
        jensen_alpha = actual_return - expected_return

        payload = {
            "status": "success",
            "symbol": sym,
            "jensen_alpha": float(round(jensen_alpha, 6)),
            "beta": float(round(beta, 4)),
            "expected_return": float(round(expected_return, 6)),
            "actual_return": float(round(actual_return, 6)),
            "market_return": float(round(market_return, 6)),
            "risk_free_rate": rf,
            "data_points": min_len,
            "warnings": warnings,
        }
        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("Jensen Alpha 计算失败: %s", exc, exc_info=True)
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2, default=str)


# ============================================================
#  Tool 6: 投资组合压力测试
# ============================================================

@tool
@register_tool(
    tool_id="get_portfolio_stress_test",
    name="投资组合压力测试",
    description="对投资组合进行历史情景压力测试，模拟 2008 金融危机、2015 股灾、2020 疫情、2022 调整等极端市场情景下的影响。",
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["risk_analysis", "stress_testing"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["stress_test", "scenario_analysis"],
    when_to_use="当需要评估投资组合在极端市场条件下的潜在损失时使用。",
    when_not_to_use="当无法获取股票当前价格或基础信息时压力测试无法进行。",
    returns="返回 JSON，包含 current_value、scenarios（每个情景的名称、总收益率、影响金额）。",
    example="get_portfolio_stress_test(symbols='600519,000001,300750', weights='0.4,0.3,0.3')",
    related_tools=["get_scenario_analysis", "get_var_calculation"],
)
def get_portfolio_stress_test(
    symbols: Annotated[str, "股票代码列表，用逗号分隔，如 '600519,000001,300750'"],
    weights: Annotated[Optional[str], "权重列表，用逗号分隔，如 '0.4,0.3,0.3'，不传则等权"] = None,
) -> str:
    """对投资组合进行压力测试。模拟 2008 金融危机、2015 股灾、2020 疫情、2022 调整等极端情景下的影响。

    Args:
        symbols: 股票代码列表，用逗号分隔，如 "600519,000001,300750"
        weights: 权重列表，用逗号分隔，如 "0.4,0.3,0.3"；为 None 时等权；
            权重数量与 symbols 不一致时回退等权；权重会被归一化

    Returns:
        str: JSON 字符串，字段说明——
            status: "success" | "error"
            current_value: 组合当前总价值（按权重 × 价格聚合）
            num_assets: 资产数量
            assets: list[dict]，资产清单，元素结构——
                — symbol: 股票代码
                — weight: 归一化后的权重
                — price: 当前价格（缺失时使用假设价格 100.0）
            scenarios: list[dict]，情景结果，元素结构——
                — name: 情景名（"2008 金融危机" / "2015 股灾" / "2020 疫情冲击" / "2022 市场调整"）
                — description: 情景描述
                — shock: 情景冲击幅度（如 -0.50）
                — total_return: 组合总收益率
                — impact: 影响金额
                — remaining_value: 剩余价值
            warnings: list[str]，过程中产生的告警信息
            message: 当 status 为 "error" 时的错误描述
    """
    try:
        warnings: list = []
        sym_list, w_list = _parse_symbols_weights(str(symbols), weights)

        if not sym_list:
            return json.dumps(
                {"status": "error", "message": "至少需要提供一个股票代码。"},
                ensure_ascii=False, indent=2, default=str,
            )

        # 获取当前价格和基础信息
        current_prices = {}
        for sym in sym_list:
            basic_info = get_stock_basic_info(sym) or {}
            # 尝试从基础信息获取最新价格
            price = _safe_float(basic_info.get("close")) or _safe_float(basic_info.get("price")) or _safe_float(basic_info.get("latest_price"))
            if price is None:
                # 回退：从日线获取最新收盘价
                end_date = _today()
                start_date = _days_ago(10)
                quotes = get_stock_daily_quotes(sym, start_date, end_date, limit=5)
                if quotes:
                    price = _safe_float(quotes[-1].get("close"))
            if price is not None:
                current_prices[sym] = price
            else:
                warnings.append(f"无法获取 {sym} 的当前价格，使用假设价格 100。")
                current_prices[sym] = 100.0

        # 计算组合当前总价值（假设每只股票持有1个单位或按权重）
        # 使用归一化权重与价格
        total_value = sum(w_list[i] * current_prices[sym_list[i]] for i in range(len(sym_list)))

        # 四个历史压力情景
        scenarios_config = [
            {"name": "2008 金融危机", "shock": -0.50, "description": "2008年全球金融危机，市场下跌约50%"},
            {"name": "2015 股灾", "shock": -0.40, "description": "2015年中国股灾，市场下跌约40%"},
            {"name": "2020 疫情冲击", "shock": -0.30, "description": "2020年新冠疫情冲击，市场下跌约30%"},
            {"name": "2022 市场调整", "shock": -0.20, "description": "2022年市场调整，下跌约20%"},
        ]

        scenario_results = []
        for sc in scenarios_config:
            shock = sc["shock"]
            # 简化：所有资产承受相同冲击
            portfolio_return = shock
            impact = total_value * shock

            scenario_results.append({
                "name": sc["name"],
                "description": sc["description"],
                "shock": shock,
                "total_return": float(round(portfolio_return, 4)),
                "impact": float(round(impact, 2)),
                "remaining_value": float(round(total_value + impact, 2)),
            })

        payload = {
            "status": "success",
            "current_value": float(round(total_value, 2)),
            "num_assets": len(sym_list),
            "assets": [{"symbol": sym_list[i], "weight": float(round(w_list[i], 4)), "price": float(round(current_prices[sym_list[i]], 2))} for i in range(len(sym_list))],
            "scenarios": scenario_results,
            "warnings": warnings,
        }
        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("压力测试失败: %s", exc, exc_info=True)
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2, default=str)


# ============================================================
#  Tool 7: 情景分析
# ============================================================

@tool
@register_tool(
    tool_id="get_scenario_analysis",
    name="情景分析",
    description="对投资组合进行自定义情景分析，按用户指定各资产涨跌幅计算组合整体影响，返回各情景下组合市值变化、盈亏额、新权重和风险指标",
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["risk_analysis", "scenario_analysis"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["custom_scenario_analysis", "what_if_analysis"],
    when_to_use="当需要模拟自定义市场情景对投资组合的影响时使用。",
    when_not_to_use="当情景 JSON 格式不正确时无法解析。",
    returns="返回 JSON，包含 base_value、scenario_results（每个情景的名称、冲击后的总价值、总收益率、详情）。",
    example="get_scenario_analysis(symbols='600519,000001', weights='0.5,0.5', scenarios='[{\"name\":\"牛市\",\"shocks\":{\"600519\":0.2,\"000001\":0.1}}]')",
    related_tools=["get_portfolio_stress_test"],
)
def get_scenario_analysis(
    symbols: Annotated[str, "股票代码列表，用逗号分隔，如 '600519,000001'"],
    weights: Annotated[Optional[str], "权重列表，用逗号分隔，如 '0.5,0.5'，不传则等权"] = None,
    scenarios: Annotated[str, "情景 JSON 字符串，格式为 [{\"name\": \"情景名\", \"shocks\": {\"600519\": -0.1, \"000001\": 0.05}}]"] = "[]",
) -> str:
    """对投资组合进行自定义情景分析。按用户指定的各资产涨跌幅计算组合整体影响。

    Args:
        symbols: 股票代码列表，用逗号分隔，如 "600519,000001"
        weights: 权重列表，用逗号分隔，如 "0.5,0.5"；为 None 时等权；权重会被归一化
        scenarios: 情景 JSON 字符串，默认 "[]"；
            格式为 [{"name": "情景名", "shocks": {"600519": -0.1, "000001": 0.05}}]

    Returns:
        str: JSON 字符串，字段说明——
            status: "success" | "error"
            base_value: 组合基础总价值
            num_assets: 资产数量
            num_scenarios: 解析得到的情景数
            scenario_results: list[dict]，情景结果，元素结构——
                — name: 情景名
                — total_return: 组合总收益率
                — post_value: 冲击后组合总价值
                — impact: 影响金额
                — asset_details: list[dict]，资产明细，元素结构——
                    — symbol: 股票代码
                    — weight: 权重
                    — shock: 该资产的冲击幅度
                    — contribution: 对组合收益的贡献
                    — value_change: 资产价值变化
            warnings: list[str]，过程中产生的告警信息
            message: 当 status 为 "error" 时的错误描述
    """
    try:
        warnings: list = []
        sym_list, w_list = _parse_symbols_weights(str(symbols), weights)

        if not sym_list:
            return json.dumps(
                {"status": "error", "message": "至少需要提供一个股票代码。"},
                ensure_ascii=False, indent=2, default=str,
            )

        # 获取当前价格
        current_prices = {}
        for sym in sym_list:
            basic_info = get_stock_basic_info(sym) or {}
            price = _safe_float(basic_info.get("close")) or _safe_float(basic_info.get("price")) or _safe_float(basic_info.get("latest_price"))
            if price is None:
                end_date = _today()
                start_date = _days_ago(10)
                quotes = get_stock_daily_quotes(sym, start_date, end_date, limit=5)
                if quotes:
                    price = _safe_float(quotes[-1].get("close"))
            if price is not None:
                current_prices[sym] = price
            else:
                warnings.append(f"无法获取 {sym} 的当前价格，使用假设价格 100。")
                current_prices[sym] = 100.0

        base_value = sum(w_list[i] * current_prices[sym_list[i]] for i in range(len(sym_list)))

        # 解析情景
        try:
            parsed_scenarios = json.loads(str(scenarios))
            if not isinstance(parsed_scenarios, list):
                parsed_scenarios = [parsed_scenarios]
        except (json.JSONDecodeError, TypeError):
            return json.dumps(
                {"status": "error", "message": "情景 JSON 格式不正确，请提供有效的 JSON 数组。"},
                ensure_ascii=False, indent=2, default=str,
            )

        scenario_results = []
        for scenario in parsed_scenarios:
            name = scenario.get("name", "未命名情景")
            shocks = scenario.get("shocks", {})

            total_impact = 0.0
            asset_details = []
            for i, sym in enumerate(sym_list):
                shock = float(shocks.get(sym, 0.0))
                weight = w_list[i]
                contribution = weight * shock
                total_impact += contribution

                asset_value_change = current_prices[sym] * shock
                asset_details.append({
                    "symbol": sym,
                    "weight": float(round(weight, 4)),
                    "shock": shock,
                    "contribution": float(round(contribution, 6)),
                    "value_change": float(round(asset_value_change, 2)),
                })

            post_value = base_value * (1 + total_impact)
            scenario_results.append({
                "name": name,
                "total_return": float(round(total_impact, 6)),
                "post_value": float(round(post_value, 2)),
                "impact": float(round(base_value * total_impact, 2)),
                "asset_details": asset_details,
            })

        payload = {
            "status": "success",
            "base_value": float(round(base_value, 2)),
            "num_assets": len(sym_list),
            "num_scenarios": len(scenario_results),
            "scenario_results": scenario_results,
            "warnings": warnings,
        }
        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("情景分析失败: %s", exc, exc_info=True)
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2, default=str)


# ============================================================
#  Tool 8: Brinson 归因
# ============================================================

@tool
@register_tool(
    tool_id="get_brinson_attribution",
    name="Brinson 归因分析",
    description="使用 Brinson 模型对投资组合进行绩效归因，分解超额收益来源，返回配置效应、选股效应、交互效应、各行业贡献和超额收益分解",
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["performance_attribution", "portfolio_analysis"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["brinson_attribution", "performance_decomposition"],
    when_to_use="当需要分析投资组合超额收益的来源，区分配置决策和选股决策的贡献时使用。",
    when_not_to_use="当数据不足或行业分类信息不可用时归因结果可能不完整。",
    returns="返回 JSON，包含 allocation_effect、selection_effect、interaction_effect、total_excess_return。",
    example="get_brinson_attribution(symbols='600519,000001,300750', benchmark_symbols='000300,399001,399006')",
    related_tools=["get_sector_attribution", "get_factor_attribution"],
)
def get_brinson_attribution(
    symbols: Annotated[str, "投资组合股票代码列表，用逗号分隔，如 '600519,000001,300750'"],
    benchmark_symbols: Annotated[str, "基准指数代码列表，用逗号分隔，默认 '000300,399001,399006'（沪深300、深证成指、创业板指）"] = "000300,399001,399006",
) -> str:
    """对投资组合进行 Brinson 绩效归因。将超额收益分解为配置效应、选股效应和交互效应。

    Args:
        symbols: 投资组合股票代码列表，用逗号分隔，如 "600519,000001,300750"
        benchmark_symbols: 基准指数代码列表，用逗号分隔，默认 "000300,399001,399006"
            （沪深300、深证成指、创业板指）

    Returns:
        str: JSON 字符串，字段说明——
            status: "success" | "error"
            allocation_effect: 配置效应
            selection_effect: 选股效应
            interaction_effect: 交互效应
            total_excess_return: 总超额收益（组合 - 基准）
            portfolio_return: 组合年化收益
            benchmark_return: 基准年化收益
            portfolio_assets: list[str]，组合股票代码列表
            benchmark_assets: list[str]，基准指数代码列表
            industry_breakdown: dict，行业分解——
                — portfolio: dict[str, dict]，组合各行业——
                    — <行业名>: {weight: 权重, return: 行业收益}
                — benchmark: dict[str, dict]，基准各行业——
                    — <行业名>: {weight: 权重, return: 行业收益}
            warnings: list[str]，过程中产生的告警信息
            message: 当 status 为 "error" 时的错误描述
    """
    try:
        warnings: list = []
        sym_list = [s.strip() for s in str(symbols).split(",") if s.strip()]
        bench_list = [s.strip() for s in str(benchmark_symbols).split(",") if s.strip()]

        if not sym_list:
            return json.dumps(
                {"status": "error", "message": "至少需要提供一个投资组合股票代码。"},
                ensure_ascii=False, indent=2, default=str,
            )

        if not bench_list:
            bench_list = ["000300", "399001", "399006"]

        ldays = 252
        end_date = _today()
        start_date = _days_ago(ldays * 2 + 50)

        # 获取组合中各股票的行业分类和收益率
        portfolio_sectors = {}
        portfolio_returns = {}
        for sym in sym_list:
            basic_info = get_stock_basic_info(sym) or {}
            industry = str(basic_info.get("industry", basic_info.get("sector", "未知")))
            if industry in ("None", "", "未知"):
                industry = "未知"
            portfolio_sectors[sym] = industry

            quotes = get_stock_daily_quotes(sym, start_date, end_date, limit=ldays + 50)
            if quotes:
                import pandas as pd
                df = pd.DataFrame(quotes)
                df["close"] = df["close"].apply(_safe_float)
                df = df.dropna(subset=["close"]).sort_values("trade_date")
                df["return"] = df["close"].pct_change()
                df = df.dropna(subset=["return"])
                if len(df) >= 20:
                    portfolio_returns[sym] = float(np.mean(df["return"].values) * 252)
                else:
                    portfolio_returns[sym] = 0.0
                    warnings.append(f"{sym} 数据不足，收益率设为 0。")
            else:
                portfolio_returns[sym] = 0.0
                warnings.append(f"无法获取 {sym} 的日线数据，收益率设为 0。")

        # 获取基准指数的行业分类和收益率
        benchmark_sectors = {}
        benchmark_returns = {}
        for bench in bench_list:
            basic_info = get_stock_basic_info(bench) or {}
            industry = str(basic_info.get("industry", basic_info.get("sector", "基准")))
            if industry in ("None", "", "未知"):
                industry = "基准"
            benchmark_sectors[bench] = industry

            quotes = get_stock_daily_quotes(bench, start_date, end_date, limit=ldays + 50)
            if quotes:
                import pandas as pd
                df = pd.DataFrame(quotes)
                df["close"] = df["close"].apply(_safe_float)
                df = df.dropna(subset=["close"]).sort_values("trade_date")
                df["return"] = df["close"].pct_change()
                df = df.dropna(subset=["return"])
                if len(df) >= 20:
                    benchmark_returns[bench] = float(np.mean(df["return"].values) * 252)
                else:
                    benchmark_returns[bench] = 0.0
            else:
                benchmark_returns[bench] = 0.0

        # 简化版 Brinson 归因
        # 等权假设
        port_weight = 1.0 / len(sym_list)
        bench_weight = 1.0 / len(bench_list)

        # 组合总收益率
        port_total_return = sum(portfolio_returns.get(sym, 0.0) for sym in sym_list) / len(sym_list)
        # 基准总收益率
        bench_total_return = sum(benchmark_returns.get(b, 0.0) for b in bench_list) / len(bench_list)

        # 配置效应: 各行业配置权重差异 * 基准行业收益率
        allocation_effect = 0.0
        selection_effect = 0.0
        interaction_effect = 0.0

        # 按行业分组
        port_industry_weights = {}
        port_industry_returns = {}
        for sym in sym_list:
            ind = portfolio_sectors.get(sym, "未知")
            port_industry_weights[ind] = port_industry_weights.get(ind, 0.0) + port_weight
            port_industry_returns[ind] = port_industry_returns.get(ind, 0.0) + portfolio_returns.get(sym, 0.0) * port_weight

        bench_industry_weights = {}
        bench_industry_returns = {}
        for bench in bench_list:
            ind = benchmark_sectors.get(bench, "基准")
            bench_industry_weights[ind] = bench_industry_weights.get(ind, 0.0) + bench_weight
            bench_industry_returns[ind] = bench_industry_returns.get(ind, 0.0) + benchmark_returns.get(bench, 0.0) * bench_weight

        all_industries = set(list(port_industry_weights.keys()) + list(bench_industry_weights.keys()))
        for ind in all_industries:
            pw = port_industry_weights.get(ind, 0.0)
            bw = bench_industry_weights.get(ind, 0.0)
            pr = port_industry_returns.get(ind, 0.0)
            br = bench_industry_returns.get(ind, 0.0)

            allocation_effect += (pw - bw) * br
            selection_effect += bw * (pr - br)
            interaction_effect += (pw - bw) * (pr - br)

        total_excess_return = port_total_return - bench_total_return

        payload = {
            "status": "success",
            "allocation_effect": float(round(allocation_effect, 6)),
            "selection_effect": float(round(selection_effect, 6)),
            "interaction_effect": float(round(interaction_effect, 6)),
            "total_excess_return": float(round(total_excess_return, 6)),
            "portfolio_return": float(round(port_total_return, 6)),
            "benchmark_return": float(round(bench_total_return, 6)),
            "portfolio_assets": sym_list,
            "benchmark_assets": bench_list,
            "industry_breakdown": {
                "portfolio": {k: {"weight": float(round(v, 4)), "return": float(round(port_industry_returns.get(k, 0.0), 6))} for k, v in port_industry_weights.items()},
                "benchmark": {k: {"weight": float(round(v, 4)), "return": float(round(bench_industry_returns.get(k, 0.0), 6))} for k, v in bench_industry_weights.items()},
            },
            "warnings": warnings,
        }
        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("Brinson 归因分析失败: %s", exc, exc_info=True)
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2, default=str)


# ============================================================
#  Tool 9: 行业归因
# ============================================================

@tool
@register_tool(
    tool_id="get_sector_attribution",
    name="行业归因分析",
    description="对投资组合中各股票按行业分类计算收益贡献，返回各行业权重、收益率、贡献占比、资产数量及明细列表等结构化归因报告",
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["performance_attribution", "sector_analysis"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["sector_attribution", "industry_contribution"],
    when_to_use="当需要分析投资组合中各行业对总收益的贡献度时使用。",
    when_not_to_use="当无法获取股票的行业分类信息时归因无法完成。",
    returns="返回 JSON，包含 sector_contributions 列表（每个行业的名称、权重、收益率、贡献度）。",
    example="get_sector_attribution(symbols='600519,000001,300750,002415,601318')",
    related_tools=["get_brinson_attribution", "get_factor_attribution"],
)
def get_sector_attribution(
    symbols: Annotated[str, "股票代码列表，用逗号分隔，如 '600519,000001,300750'"],
) -> str:
    """对投资组合进行行业归因分析。按行业分类计算各行业对组合总收益的贡献度。

    Args:
        symbols: 股票代码列表，用逗号分隔，如 "600519,000001,300750"

    Returns:
        str: JSON 字符串，字段说明——
            status: "success" | "error"
            portfolio_return: 组合年化收益
            num_sectors: 行业数量
            num_assets: 资产数量
            sector_contributions: list[dict]，按行业收益降序排列，元素结构——
                — sector: 行业名
                — weight: 行业权重
                — return: 行业加权收益
                — contribution_pct: 收益贡献百分比
                — num_assets: 该行业资产数
                — assets: list[dict]，该行业资产清单——
                    — symbol: 股票代码
                    — return: 年化收益
                    — weight: 权重
            warnings: list[str]，过程中产生的告警信息
            message: 当 status 为 "error" 时的错误描述
    """
    try:
        warnings: list = []
        sym_list = [s.strip() for s in str(symbols).split(",") if s.strip()]

        if not sym_list:
            return json.dumps(
                {"status": "error", "message": "至少需要提供一个股票代码。"},
                ensure_ascii=False, indent=2, default=str,
            )

        ldays = 252
        end_date = _today()
        start_date = _days_ago(ldays * 2 + 50)

        # 获取每个股票的行业信息和收益率
        sector_data = {}  # sector -> {total_return, weight, symbols}
        total_weight = 1.0 / len(sym_list)

        for sym in sym_list:
            basic_info = get_stock_basic_info(sym) or {}
            industry = str(basic_info.get("industry", basic_info.get("sector", "未知")))
            if industry in ("None", "", "未知"):
                industry = "未知"

            # 获取收益率
            quotes = get_stock_daily_quotes(sym, start_date, end_date, limit=ldays + 50)
            stock_return = 0.0
            if quotes:
                import pandas as pd
                df = pd.DataFrame(quotes)
                df["close"] = df["close"].apply(_safe_float)
                df = df.dropna(subset=["close"]).sort_values("trade_date")
                df["return"] = df["close"].pct_change()
                df = df.dropna(subset=["return"])
                if len(df) >= 20:
                    stock_return = float(np.mean(df["return"].values) * 252)
                else:
                    warnings.append(f"{sym} 数据不足，收益率设为 0。")
            else:
                warnings.append(f"无法获取 {sym} 的日线数据，收益率设为 0。")

            if industry not in sector_data:
                sector_data[industry] = {
                    "total_return": 0.0,
                    "total_weight": 0.0,
                    "assets": [],
                }
            sector_data[industry]["total_return"] += stock_return * total_weight
            sector_data[industry]["total_weight"] += total_weight
            sector_data[industry]["assets"].append({
                "symbol": sym,
                "return": float(round(stock_return, 6)),
                "weight": float(round(total_weight, 4)),
            })

        portfolio_return = sum(sd["total_return"] for sd in sector_data.values())

        sector_contributions = []
        for sector_name, data in sorted(sector_data.items(), key=lambda x: x[1]["total_return"], reverse=True):
            contribution_pct = (data["total_return"] / portfolio_return * 100) if portfolio_return != 0 else 0.0
            sector_contributions.append({
                "sector": sector_name,
                "weight": float(round(data["total_weight"], 4)),
                "return": float(round(data["total_return"], 6)),
                "contribution_pct": float(round(contribution_pct, 2)),
                "num_assets": len(data["assets"]),
                "assets": data["assets"],
            })

        payload = {
            "status": "success",
            "portfolio_return": float(round(portfolio_return, 6)),
            "num_sectors": len(sector_contributions),
            "num_assets": len(sym_list),
            "sector_contributions": sector_contributions,
            "warnings": warnings,
        }
        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("行业归因分析失败: %s", exc, exc_info=True)
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2, default=str)


__all__ = [
    "get_sortino_ratio",
    "get_treynor_ratio",
    "get_information_ratio",
    "get_calmar_ratio",
    "get_jensen_alpha",
    "get_portfolio_stress_test",
    "get_scenario_analysis",
    "get_brinson_attribution",
    "get_sector_attribution",
]