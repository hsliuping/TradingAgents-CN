"""
投资组合量化分析工具

提供有效前沿、蒙特卡洛模拟、因子归因等专业量化分析功能。
所有计算基于纯数学方法，无需 LLM 参与。
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Annotated, Optional

import numpy as np
import pandas as pd
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


def _load_returns_for_symbol(symbol: str, lookback_days: int) -> Optional[pd.DataFrame]:
    """获取单只股票的收益率序列。"""
    end_date = _today()
    start_date = _days_ago(int(lookback_days) * 2 + 50)
    quotes = get_stock_daily_quotes(
        str(symbol), start_date, end_date, limit=int(lookback_days) + 100
    )
    if not quotes:
        return None
    df = pd.DataFrame(quotes)
    df["close"] = df["close"].apply(_safe_float)
    df["trade_date"] = df["trade_date"].astype(str)
    df = df.dropna(subset=["close"]).sort_values("trade_date")
    df["return"] = df["close"].pct_change()
    df = df.dropna(subset=["return"])
    df["symbol"] = str(symbol)
    return df[["trade_date", "return", "symbol"]]


# ============================================================
#  Tool 1: 有效前沿
# ============================================================

@tool
@register_tool(
    tool_id="get_efficient_frontier",
    name="有效前沿分析",
    description="基于马科维茨均值-方差模型，计算投资组合的有效前沿曲线、最大夏普比率组合（切点组合）和最小波动组合。",
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["portfolio_analysis", "risk_management"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["efficient_frontier", "portfolio_optimization"],
    when_to_use="当需要分析多资产组合的风险收益特征，寻找最优资产配置比例时使用。",
    when_not_to_use="当数据不足（至少需要2只有效数据的股票且每只至少30个交易日）时无法计算。",
    returns="返回 JSON，包含 max_sharpe（收益率、波动率、夏普比率、权重）、min_vol（收益率、波动率、权重）、frontier_points、portfolio_stats。",
    example="get_efficient_frontier(symbols='600519,000001,300750', lookback_days=252, risk_free_rate=0.025, num_portfolios=5000)",
    related_tools=["get_monte_carlo_simulation", "get_sharpe_ratio"],
)
def get_efficient_frontier(
    symbols: Annotated[str, "股票代码列表，用逗号分隔，如 '600519,000001,300750'"],
    lookback_days: Annotated[int, "回看交易日数，默认252（约1年）"] = 252,
    risk_free_rate: Annotated[float, "无风险利率，默认 0.025（2.5%）"] = 0.025,
    num_portfolios: Annotated[int, "蒙特卡洛模拟的组合数量，默认5000"] = 5000,
) -> str:
    """计算投资组合有效前沿。基于马科维茨均值-方差模型，给出最大夏普组合、最小波动组合及前沿曲线。

    Args:
        symbols: 股票代码列表，用逗号分隔，如 "600519,000001,300750"（至少 2 只）
        lookback_days: 回看交易日数，默认 252（约 1 年）
        risk_free_rate: 无风险利率，默认 0.025（2.5%）
        num_portfolios: 蒙特卡洛模拟的随机组合数量，默认 5000

    Returns:
        str: JSON 字符串，字段说明——
            status: "success" | "error"
            max_sharpe: dict，最大夏普比率组合——
                — return: 年化收益
                — volatility: 年化波动率
                — sharpe_ratio: 夏普比率
                — weights: dict[str, float]，各股票权重
            min_vol: dict，最小波动组合——
                — return: 年化收益
                — volatility: 年化波动率
                — weights: dict[str, float]，各股票权重
            frontier_points: list[dict]，有效前沿曲线点，元素结构——
                — return: 目标收益
                — volatility: 对应最小波动率
            portfolio_stats: dict，组合统计——
                — num_assets: 资产数
                — valid_symbols: list[str]，实际使用的有效股票代码
                — num_portfolios_simulated: 模拟组合数
                — overlapping_trading_days: 重叠交易日数
                — risk_free_rate: 无风险利率
            warnings: list[str]，过程中产生的告警信息
            message: 当 status 为 "error" 时的错误描述
    """
    try:
        warnings: list = []
        symbol_list = [s.strip() for s in str(symbols).split(",") if s.strip()]
        if len(symbol_list) < 2:
            return json.dumps(
                {"status": "error", "message": "至少需要2只股票进行有效前沿分析。"},
                ensure_ascii=False, indent=2, default=str,
            )

        rf = float(risk_free_rate) if risk_free_rate is not None else 0.025

        # 获取各股票收益率数据并合并
        returns_dfs = []
        valid_symbols = []
        for sym in symbol_list:
            df = _load_returns_for_symbol(sym, int(lookback_days))
            if df is not None and len(df) >= 30:
                returns_dfs.append(df.rename(columns={"return": sym})[[sym, "trade_date"]])
                valid_symbols.append(sym)
            else:
                warnings.append(f"{sym} 数据不足（需要至少30个交易日），已排除。")

        if len(valid_symbols) < 2:
            return json.dumps(
                {"status": "error", "message": "至少有数据的股票不足2只，无法进行有效前沿分析。", "warnings": warnings},
                ensure_ascii=False, indent=2, default=str,
            )

        # 合并收益率数据
        merged = returns_dfs[0]
        for df in returns_dfs[1:]:
            merged = pd.merge(merged, df, on="trade_date", how="inner")
        merged = merged.dropna()
        merged = merged.set_index("trade_date")

        if len(merged) < 20:
            return json.dumps(
                {"status": "error", "message": f"股票间重叠交易日仅 {len(merged)} 天，不足20天。", "warnings": warnings},
                ensure_ascii=False, indent=2, default=str,
            )

        returns_matrix = merged.values
        n_assets = len(valid_symbols)
        mean_returns = np.mean(returns_matrix, axis=0)
        cov_matrix = np.cov(returns_matrix, rowvar=False)

        # 蒙特卡洛模拟随机组合
        np.random.seed(42)
        results = np.zeros((3, int(num_portfolios)))
        weights_record = []

        for i in range(int(num_portfolios)):
            weights = np.random.random(n_assets)
            weights = weights / np.sum(weights)
            weights_record.append(weights)

            port_return = np.sum(mean_returns * weights) * 252
            port_vol = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights))) * np.sqrt(252)
            sharpe = (port_return - rf) / port_vol if port_vol > 0 else 0

            results[0, i] = port_return
            results[1, i] = port_vol
            results[2, i] = sharpe

        # 最大夏普比率组合
        max_sharpe_idx = np.argmax(results[2])
        max_sharpe_weights = weights_record[max_sharpe_idx]
        max_sharpe_portfolio = {
            "return": float(round(results[0, max_sharpe_idx], 6)),
            "volatility": float(round(results[1, max_sharpe_idx], 6)),
            "sharpe_ratio": float(round(results[2, max_sharpe_idx], 4)),
            "weights": {sym: float(round(w, 6)) for sym, w in zip(valid_symbols, max_sharpe_weights)},
        }

        # 最小波动组合
        min_vol_idx = np.argmin(results[1])
        min_vol_weights = weights_record[min_vol_idx]
        min_vol_portfolio = {
            "return": float(round(results[0, min_vol_idx], 6)),
            "volatility": float(round(results[1, min_vol_idx], 6)),
            "weights": {sym: float(round(w, 6)) for sym, w in zip(valid_symbols, min_vol_weights)},
        }

        # 有效前沿曲线（尝试使用 scipy.optimize 计算理论前沿）
        frontier_points = []
        try:
            from scipy.optimize import minimize

            def portfolio_stats(weights):
                weights = np.array(weights)
                port_return = np.sum(mean_returns * weights) * 252
                port_vol = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights))) * np.sqrt(252)
                return port_return, port_vol

            constraints = {"type": "eq", "fun": lambda x: np.sum(x) - 1}
            bounds = tuple((0, 1) for _ in range(n_assets))

            target_returns = np.linspace(
                min_vol_portfolio["return"],
                max(results[0]) * 0.95,
                50,
            )

            for target in target_returns:
                cons = [constraints, {"type": "eq", "fun": lambda x, t=target: np.sum(mean_returns * x) * 252 - t}]
                init_guess = np.array([1.0 / n_assets] * n_assets)
                result = minimize(
                    lambda w: np.sqrt(np.dot(w.T, np.dot(cov_matrix, w))) * np.sqrt(252),
                    init_guess,
                    method="SLSQP",
                    bounds=bounds,
                    constraints=cons,
                )
                if result.success:
                    opt_weights = result.x
                    opt_vol = np.sqrt(np.dot(opt_weights.T, np.dot(cov_matrix, opt_weights))) * np.sqrt(252)
                    frontier_points.append({
                        "return": float(round(target, 6)),
                        "volatility": float(round(opt_vol, 6)),
                    })
        except ImportError:
            # scipy 不可用，使用蒙特卡洛模拟结果中的前沿点
            # 按波动率排序，取每个收益率区间的帕累托最优
            df_results = pd.DataFrame({
                "return": results[0],
                "volatility": results[1],
            }).sort_values("volatility")
            best_by_return = {}
            for _, row in df_results.iterrows():
                ret_key = round(row["return"], 4)
                if ret_key not in best_by_return or row["volatility"] < best_by_return[ret_key]["volatility"]:
                    best_by_return[ret_key] = {"return": row["return"], "volatility": row["volatility"]}
            frontier_points = sorted(best_by_return.values(), key=lambda x: x["return"])
            warnings.append("scipy 未安装，有效前沿使用蒙特卡洛模拟的近似结果。")

        # 组合统计摘要
        portfolio_stats_data = {
            "num_assets": n_assets,
            "valid_symbols": valid_symbols,
            "num_portfolios_simulated": int(num_portfolios),
            "overlapping_trading_days": len(merged),
            "risk_free_rate": rf,
        }

        payload = {
            "status": "success",
            "max_sharpe": max_sharpe_portfolio,
            "min_vol": min_vol_portfolio,
            "frontier_points": frontier_points,
            "portfolio_stats": portfolio_stats_data,
            "warnings": warnings,
        }
        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("有效前沿分析失败: %s", exc, exc_info=True)
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2, default=str)


# ============================================================
#  Tool 2: 蒙特卡洛模拟
# ============================================================

@tool
@register_tool(
    tool_id="get_monte_carlo_simulation",
    name="蒙特卡洛模拟",
    description="基于几何布朗运动模型对单只股票进行蒙特卡洛价格路径模拟，返回模拟路径、终值分布、VaR、CVaR、预期收益率和置信区间等",
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["portfolio_analysis", "risk_management"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["price_simulation", "monte_carlo"],
    when_to_use="当需要评估股票未来价格的可能分布范围，或进行风险度量时使用。",
    when_not_to_use="当数据不足（少于30个交易日）时模拟结果参考价值有限。",
    returns="返回 JSON，包含 parameters、simulation_count、stats（median、p5、p95、mean、std、prob_loss）、sample_paths、current_price。",
    example="get_monte_carlo_simulation(symbol='600519', days=252, simulations=1000)",
    related_tools=["get_efficient_frontier", "get_var_calculation"],
)
def get_monte_carlo_simulation(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"],
    days: Annotated[int, "模拟的交易日数，默认252（约1年）"] = 252,
    simulations: Annotated[int, "模拟路径数量，默认1000"] = 1000,
    mu: Annotated[Optional[float], "年化收益率期望，不传则从历史数据估计"] = None,
    sigma: Annotated[Optional[float], "年化波动率，不传则从历史数据估计"] = None,
) -> str:
    """基于几何布朗运动进行蒙特卡洛价格模拟。预测未来价格分布及风险指标。

    Args:
        symbol: A 股股票代码，如 600519、000001
        days: 模拟的交易日数，默认 252（约 1 年）
        simulations: 模拟路径数量，默认 1000（实际会被限制在 10000 以内）
        mu: 年化收益率期望；为 None 时从历史数据估计
        sigma: 年化波动率；为 None 时从历史数据估计

    Returns:
        str: JSON 字符串，字段说明——
            status: "success" | "error"
            symbol: 标的股票代码
            current_price: 当前价格（模拟起点）
            parameters: dict，模拟参数——
                — mu_annual: 年化收益率期望
                — sigma_annual: 年化波动率
                — mu_source: "user_provided" | "estimated"
                — sigma_source: "user_provided" | "estimated"
                — days: 模拟交易日数
            simulation_count: 实际模拟路径数
            stats: dict，最终价格统计——
                — median: 中位数
                — mean: 均值
                — std: 标准差
                — p5: 5 分位数
                — p95: 95 分位数
                — prob_loss: 亏损概率（最终价低于当前价的比例）
                — min: 最小值
                — max: 最大值
            sample_paths: list[dict]，样本路径（最多 100 条），元素结构——
                — simulation_id: 模拟编号
                — final_price: 最终价格
                — path: list[float]，每日价格序列
            warnings: list[str]，过程中产生的告警信息
            message: 当 status 为 "error" 时的错误描述
    """
    try:
        warnings: list = []
        end_date = _today()
        start_date = _days_ago(int(days) * 2 + 50)

        quotes = get_stock_daily_quotes(
            str(symbol), start_date, end_date, limit=int(days) + 100
        )

        if not quotes:
            return json.dumps(
                {"status": "error", "message": f"未获取到 {symbol} 的日线数据。"},
                ensure_ascii=False, indent=2, default=str,
            )

        df = pd.DataFrame(quotes)
        df["close"] = df["close"].apply(_safe_float)
        df["trade_date"] = df["trade_date"].astype(str)
        df = df.dropna(subset=["close"]).sort_values("trade_date")
        df["return"] = df["close"].pct_change()
        df = df.dropna(subset=["return"])

        returns = df["return"].values
        current_price = float(df["close"].iloc[-1])

        if len(returns) < 30:
            warnings.append(f"有效收益率数据仅 {len(returns)} 天，不足30天，模拟结果参考价值有限。")

        # 估计参数
        estimated_mu = float(np.mean(returns) * 252) if mu is None else float(mu)
        estimated_sigma = float(np.std(returns, ddof=1) * np.sqrt(252)) if sigma is None else float(sigma)

        if estimated_sigma <= 0:
            return json.dumps(
                {"status": "error", "message": "波动率估计为零，无法进行模拟。"},
                ensure_ascii=False, indent=2, default=str,
            )

        n_days = int(days)
        n_sim = min(int(simulations), 10000)  # 限制最大模拟数量
        dt = 1.0 / 252

        # 蒙特卡洛模拟
        np.random.seed(42)
        random_matrix = np.random.standard_normal((n_days, n_sim))

        # 几何布朗运动：S_t = S_0 * exp((mu - 0.5*sigma^2)*t + sigma * sqrt(t) * Z)
        drift = (estimated_mu - 0.5 * estimated_sigma ** 2) * dt
        diffusion = estimated_sigma * np.sqrt(dt) * random_matrix
        price_paths = np.exp(np.cumsum(drift + diffusion, axis=0))
        price_paths = current_price * price_paths

        # 最终价格数组
        final_prices = price_paths[-1, :]

        # 统计指标
        median_price = float(np.median(final_prices))
        p5_price = float(np.percentile(final_prices, 5))
        p95_price = float(np.percentile(final_prices, 95))
        mean_price = float(np.mean(final_prices))
        std_price = float(np.std(final_prices, ddof=1))
        prob_loss = float(np.mean(final_prices < current_price))

        # 提取样本路径（最多100条用于展示）
        sample_indices = np.linspace(0, n_sim - 1, min(100, n_sim), dtype=int)
        sample_paths_list = []
        for idx in sample_indices:
            path = price_paths[:, idx]
            sample_paths_list.append({
                "simulation_id": int(idx),
                "final_price": float(round(path[-1], 3)),
                "path": [float(round(p, 3)) for p in path],
            })

        payload = {
            "status": "success",
            "symbol": str(symbol),
            "current_price": float(round(current_price, 3)),
            "parameters": {
                "mu_annual": float(round(estimated_mu, 6)),
                "sigma_annual": float(round(estimated_sigma, 6)),
                "mu_source": "user_provided" if mu is not None else "estimated",
                "sigma_source": "user_provided" if sigma is not None else "estimated",
                "days": n_days,
            },
            "simulation_count": n_sim,
            "stats": {
                "median": float(round(median_price, 3)),
                "mean": float(round(mean_price, 3)),
                "std": float(round(std_price, 3)),
                "p5": float(round(p5_price, 3)),
                "p95": float(round(p95_price, 3)),
                "prob_loss": float(round(prob_loss, 6)),
                "min": float(round(float(np.min(final_prices)), 3)),
                "max": float(round(float(np.max(final_prices)), 3)),
            },
            "sample_paths": sample_paths_list,
            "warnings": warnings,
        }
        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("蒙特卡洛模拟失败: %s", exc, exc_info=True)
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2, default=str)


# ============================================================
#  Tool 3: 因子归因
# ============================================================

@tool
@register_tool(
    tool_id="get_factor_attribution",
    name="因子归因分析",
    description="对个股进行简化的因子归因分析，计算 Alpha、Beta、R² 及市场因子解释度，返回因子贡献度、残差收益和归因结论，识别收益来源",
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["factor_analysis", "risk_analysis"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["factor_attribution", "return_decomposition"],
    when_to_use="当需要分析个股的收益来源，区分 Alpha（超额收益）和 Beta（市场收益）时使用。",
    when_not_to_use="当数据不足（少于30个交易日）或市场组合数据缺失时分析结果有限。",
    returns="返回 JSON，包含 factor_model、alpha、beta、r_squared、explained_by_market_pct、stock_specific_pct、data_quality。",
    example="get_factor_attribution(symbol='600519', lookback_days=252)",
    related_tools=["get_beta_calculation", "get_efficient_frontier"],
)
def get_factor_attribution(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"],
    lookback_days: Annotated[int, "回看交易日数，默认252（约1年）"] = 252,
) -> str:
    """对个股进行简化的因子归因分析。基于单因子 CAPM 模型分解 Alpha、Beta、R² 及市场解释度。

    Args:
        symbol: A 股股票代码，如 600519、000001
        lookback_days: 回看交易日数，默认 252（约 1 年）

    Returns:
        str: JSON 字符串，字段说明——
            status: "success" | "error"
            symbol: 标的股票代码
            factor_model: 因子模型名，"single_factor_capm" 或 "single_factor_simplified"
            alpha: 年化 Alpha（简化模型下为 0.0）
            beta: Beta 系数（简化模型下为 1.0）
            r_squared: 决定系数 R²（简化模型下为 None）
            explained_by_market_pct: 市场因子解释度百分比（简化模型下为 None）
            stock_specific_pct: 个股特质收益占比百分比（简化模型下为 None）
            annualized_return: 年化收益
            annualized_volatility: 年化波动率
            residual_std: 残差标准差（仅完整 CAPM 模型返回）
            skewness: 偏度
            kurtosis: 峰度
            pe_ttm: 滚动市盈率（基础信息缺失时为 None）
            pb: 市净率（基础信息缺失时为 None）
            data_quality: dict，数据质量——
                — return_data_points: 收益率样本数
                — overlapping_days: 与基准重叠交易日数（仅完整模型）
                — has_benchmark: 是否有可用基准
                — benchmark_symbol: 基准代码（"000300"）
            warnings: list[str]，过程中产生的告警信息
            message: 当 status 为 "error" 时的错误描述
    """
    try:
        warnings: list = []
        sym = str(symbol)
        end_date = _today()
        start_date = _days_ago(int(lookback_days) * 2 + 50)

        # 获取基础信息
        basic_info = get_stock_basic_info(sym) or {}

        # 获取日线数据
        quotes = get_stock_daily_quotes(
            sym, start_date, end_date, limit=int(lookback_days) + 100
        )

        if not quotes:
            return json.dumps(
                {"status": "error", "message": f"未获取到 {sym} 的日线数据。"},
                ensure_ascii=False, indent=2, default=str,
            )

        df = pd.DataFrame(quotes)
        df["close"] = df["close"].apply(_safe_float)
        df["trade_date"] = df["trade_date"].astype(str)
        df = df.dropna(subset=["close"]).sort_values("trade_date")
        df["return"] = df["close"].pct_change()
        df = df.dropna(subset=["return"])

        stock_returns = df["return"].values

        if len(stock_returns) < 30:
            return json.dumps(
                {"status": "error", "message": f"{sym} 有效收益率数据少于30个交易日，无法可靠进行因子归因。",
                 "warnings": warnings},
                ensure_ascii=False, indent=2, default=str,
            )

        # 构建市场组合代理：使用自身收益 + 其他可获得的数据
        # 尝试获取沪深300（000300）作为市场基准
        market_symbol = "000300"
        market_quotes = get_stock_daily_quotes(
            market_symbol, start_date, end_date, limit=int(lookback_days) + 100
        )

        use_market_proxy = False
        if market_quotes and len(market_quotes) > 20:
            mkt_df = pd.DataFrame(market_quotes)
            mkt_df["close"] = mkt_df["close"].apply(_safe_float)
            mkt_df["trade_date"] = mkt_df["trade_date"].astype(str)
            mkt_df = mkt_df.dropna(subset=["close"]).sort_values("trade_date")
            mkt_df["return"] = mkt_df["close"].pct_change()
            mkt_df = mkt_df.dropna(subset=["return"])

            # 对齐日期
            merged = pd.merge(
                df[["trade_date", "return"]],
                mkt_df[["trade_date", "return"]],
                on="trade_date",
                how="inner",
                suffixes=("_stock", "_market"),
            )

            if len(merged) >= 30:
                stock_r = merged["return_stock"].values
                market_r = merged["return_market"].values
                use_market_proxy = True
        else:
            warnings.append(f"未获取到基准指数 {market_symbol} 数据。")

        if not use_market_proxy:
            # 无法获得市场基准，使用简化模型
            # 使用股票自身收益率作为市场代理，beta=1
            payload = {
                "status": "success",
                "symbol": sym,
                "factor_model": "single_factor_simplified",
                "alpha": 0.0,
                "beta": 1.0,
                "r_squared": None,
                "explained_by_market_pct": None,
                "stock_specific_pct": None,
                "annualized_return": float(round(float(np.mean(stock_returns) * 252), 6)),
                "annualized_volatility": float(round(float(np.std(stock_returns, ddof=1) * np.sqrt(252)), 6)),
                "skewness": float(round(float(pd.Series(stock_returns).skew()), 4)),
                "kurtosis": float(round(float(pd.Series(stock_returns).kurtosis()), 4)),
                "pe_ttm": _safe_float(basic_info.get("pe_ttm")),
                "pb": _safe_float(basic_info.get("pb")),
                "data_quality": {
                    "return_data_points": len(stock_returns),
                    "has_benchmark": False,
                    "benchmark_symbol": market_symbol,
                },
                "warnings": warnings + ["无基准指数数据，使用简化模型（beta=1.0）。"],
            }
            return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

        # OLS 回归：stock_return = alpha + beta * market_return + epsilon
        X = np.column_stack([np.ones(len(market_r)), market_r])
        y = stock_r

        try:
            coeffs = np.linalg.lstsq(X, y, rcond=None)[0]
        except np.linalg.LinAlgError:
            return json.dumps(
                {"status": "error", "message": "OLS 回归计算失败。"},
                ensure_ascii=False, indent=2, default=str,
            )

        alpha_daily = coeffs[0]
        beta = coeffs[1]

        # 年化 Alpha
        alpha_annualized = alpha_daily * 252

        # R²
        y_pred = X @ coeffs
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

        # 市场解释度
        market_contribution = beta * market_r
        total_explained = y_pred - alpha_daily  # exclude alpha
        explained_by_market = np.var(market_contribution, ddof=1)
        total_return_var = np.var(y, ddof=1)
        if total_return_var > 0:
            explained_by_market_pct = explained_by_market / total_return_var * 100
            stock_specific_pct = (1.0 - r_squared) * 100
        else:
            explained_by_market_pct = 0.0
            stock_specific_pct = 0.0

        # 统计特征
        residuals = y - y_pred
        annualized_return = float(np.mean(stock_returns) * 252)
        annualized_vol = float(np.std(stock_returns, ddof=1) * np.sqrt(252))

        payload = {
            "status": "success",
            "symbol": sym,
            "factor_model": "single_factor_capm",
            "alpha": float(round(alpha_annualized, 6)),
            "beta": float(round(beta, 4)),
            "r_squared": float(round(r_squared, 4)),
            "explained_by_market_pct": float(round(explained_by_market_pct, 2)),
            "stock_specific_pct": float(round(stock_specific_pct, 2)),
            "annualized_return": float(round(annualized_return, 6)),
            "annualized_volatility": float(round(annualized_vol, 6)),
            "residual_std": float(round(float(np.std(residuals, ddof=1)), 6)),
            "skewness": float(round(float(pd.Series(stock_returns).skew()), 4)),
            "kurtosis": float(round(float(pd.Series(stock_returns).kurtosis()), 4)),
            "pe_ttm": _safe_float(basic_info.get("pe_ttm")),
            "pb": _safe_float(basic_info.get("pb")),
            "data_quality": {
                "return_data_points": len(stock_returns),
                "overlapping_days": len(market_r),
                "has_benchmark": True,
                "benchmark_symbol": market_symbol,
            },
            "warnings": warnings,
        }
        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("因子归因分析失败: %s", exc, exc_info=True)
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2, default=str)


__all__ = ["get_efficient_frontier", "get_monte_carlo_simulation", "get_factor_attribution"]
