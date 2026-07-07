"""统计工具集。

提供 6 个金融统计工具：
1. get_correlation_matrix - 相关性矩阵
2. get_cointegration_test - 协整检验
3. get_rolling_regression - 滚动回归
4. get_normality_test - 正态性检验
5. get_stationarity_test - 平稳性检验
6. get_garch_volatility - GARCH 波动率建模
"""

import datetime
import json
import logging
import math
from typing import Annotated, Any, Dict, List, Optional, Tuple

import numpy as np
from langchain_core.tools import tool

from core.skill_runtime.data_access import get_stock_daily_quotes, get_latest_stock_price
from core.tools.base import register_tool

logger = logging.getLogger(__name__)


# ─── 辅助函数 ──────────────────────────────────────────────────


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        try:
            numeric = float(value)
            if numeric != numeric:
                return None
            return numeric
        except (TypeError, ValueError):
            return None
    try:
        numeric = float(str(value).strip())
        if numeric != numeric:
            return None
        return numeric
    except (TypeError, ValueError):
        return None


def _dash_date(date_str: str) -> str:
    """标准化日期为 YYYY-MM-DD。"""
    cleaned = "".join(ch for ch in date_str if ch.isdigit())[:8]
    if len(cleaned) == 8:
        return f"{cleaned[:4]}-{cleaned[4:6]}-{cleaned[6:]}"
    return date_str


def _try_get_benchmark_quotes(benchmark_symbol: str, start_date_obj: datetime.date,
                                end_date_obj: datetime.date, lookback_days: int) -> Any:
    """获取基准指数行情，DB 无数据时用 AKShare 兜底。"""
    quotes = get_stock_daily_quotes(
        benchmark_symbol, start_date=start_date_obj.isoformat(), end_date=end_date_obj.isoformat(),
        period="daily", limit=lookback_days + 60,
    )
    if quotes:
        return quotes
    # AKShare 兜底
    if benchmark_symbol in ("000300", "399300", "sh000300"):
        try:
            import akshare as ak
            import pandas as pd
            df = ak.stock_zh_index_daily(symbol="sh000300")
            # date 列是 datetime.date 类型，用 date 对象直接比较
            sd = start_date_obj if isinstance(start_date_obj, datetime.date) else start_date_obj
            ed = end_date_obj if isinstance(end_date_obj, datetime.date) else end_date_obj
            df = df[df["date"] >= sd]
            df = df[df["date"] <= ed]
            records = []
            for _, row in df.iterrows():
                records.append({
                    "trade_date": str(row["date"]),
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": int(row["volume"]),
                })
            return records
        except Exception:
            return None
    return None


def _compute_daily_returns(quotes: List[Dict[str, Any]]) -> List[float]:
    """从日线记录列表计算每日收益率。"""
    closes = []
    for q in quotes:
        c = _to_float(q.get("close"))
        if c is not None and c > 0:
            closes.append(c)
    if len(closes) < 2:
        return []
    returns = []
    for i in range(1, len(closes)):
        returns.append((closes[i] - closes[i - 1]) / closes[i - 1])
    return returns


def _fetch_quotes(symbol: str, lookback_days: int) -> List[Dict[str, Any]]:
    """获取最近 N 天的日线数据。"""
    end = datetime.date.today()
    start = end - datetime.timedelta(days=lookback_days + 30)  # 多取一些确保有足够数据
    return get_stock_daily_quotes(
        symbol,
        start_date=start.isoformat(),
        end_date=end.isoformat(),
        period="daily",
        limit=lookback_days + 60,
    )


def _safe_autocorr(series: List[float], lag: int = 1) -> Optional[float]:
    """计算一阶自相关系数。"""
    if len(series) < lag + 2:
        return None
    arr = np.array(series)
    if np.std(arr[:-lag]) == 0 or np.std(arr[lag:]) == 0:
        return None
    return float(np.corrcoef(arr[:-lag], arr[lag:])[0, 1])


def _adf_test_simple(series: List[float]) -> Tuple[float, float]:
    """简易 ADF 检验。

    对残差序列回归 Δε_t = ρ × ε_{t-1}，检验 ρ 是否显著为负。
    使用 scipy.stats 的临界值（如果可用）。

    Returns:
        (adf_statistic, p_value_simplified)
    """
    if len(series) < 4:
        return float("nan"), 1.0

    arr = np.array(series)
    y = np.diff(arr)  # Δε_t
    x = arr[:-1]      # ε_{t-1}

    if np.std(x) == 0:
        return float("nan"), 1.0

    # OLS: y = β * x + ε (without intercept for ADF on residuals)
    beta = np.sum(x * y) / np.sum(x ** 2)
    residuals = y - beta * x
    se = math.sqrt(np.sum(residuals ** 2) / (len(residuals) - 1))
    se_beta = se / math.sqrt(np.sum(x ** 2))

    if se_beta == 0:
        return float("nan"), 1.0

    adf_stat = beta / se_beta

    # 用 scipy 查临界值
    try:
        from scipy import stats
        # ADF 临界值约 -3.43 (1%), -2.86 (5%), -2.57 (10%) - 样本量约 500
        # 使用近似 t 分布估算 p 值
        p_value = 2.0 * stats.t.cdf(adf_stat, df=len(residuals) - 1)
    except ImportError:
        # 手动估算
        if adf_stat < -3.43:
            p_value = 0.01
        elif adf_stat < -2.86:
            p_value = 0.05
        elif adf_stat < -2.57:
            p_value = 0.10
        else:
            p_value = 0.50

    return float(adf_stat), float(p_value)


# ────────────────────────────────────────────────────────────────
# Tool 1: 相关性矩阵
# ────────────────────────────────────────────────────────────────


@tool
@register_tool(
    tool_id="get_correlation_matrix",
    name="相关性矩阵",
    description=(
        "计算多只股票之间的收益率相关系数矩阵。"
        "支持 Pearson、Spearman、Kendall 三种方法。"
        "自动找出高相关（|r|>0.7）的股票对。"
    ),
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="medium",
    capability_tags=["statistics", "correlation", "quantitative"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["多股票相关性分析", "组合分散化评估", "风险对冲配对识别"],
    when_to_use=(
        "当需要分析多只股票之间的价格联动关系、构建低相关投资组合、"
        "或寻找对冲配对时使用。适合量化分析和风险管理场景。"
    ),
    when_not_to_use=(
        "不适合单股票分析；不适合因果分析（相关性不等于因果性）；"
        "数据不足时（< 20 个交易日）结果不可靠。"
    ),
    returns=(
        "返回 JSON 字符串，包含 symbols、method、bars_used、"
        "correlation_matrix（行列表格式）、top_correlated_pairs（|r|>0.7 的高相关对）。"
    ),
    example="get_correlation_matrix(symbols='600519,000001,300750')",
    related_tools=[
        "get_cointegration_test",
        "get_rolling_regression",
    ],
)
def get_correlation_matrix(
    symbols: Annotated[str, "多个股票代码，用逗号分隔，如 '600519,000001,300750'"],
    lookback_days: Annotated[int, "回溯天数，默认 252（约 1 个交易日年）"] = 252,
    method: Annotated[str, "相关系数方法：pearson / spearman / kendall，默认 pearson"] = "pearson",
) -> str:
    """计算多只股票的收益率相关性矩阵。

    Args:
        symbols: 多个股票代码，用逗号分隔（如 "600519,000001,300750"）
        lookback_days: 回溯天数（自动截断到 20-1000），默认 252
        method: 相关系数方法: "pearson" / "spearman" / "kendall"，默认 "pearson"

    Returns:
        str: JSON 字符串，字段说明——
            status: 状态（仅在异常时为 "error"）
            symbols: list[str] 实际使用的股票代码列表
            method: 实际使用的方法
            bars_used: 对齐后使用的收益率样本数
            correlation_matrix: list[dict] 相关性矩阵，元素结构——
                — symbol: 股票代码
                — values: list[float] 与各股票的相关系数
            top_correlated_pairs: list[dict] 相关系数绝对值 > 0.7 的股票对（最多20个），元素结构——
                — stock_a: 股票 A
                — stock_b: 股票 B
                — correlation: 相关系数
                — strength: 强度: "强正相关" | "强负相关"
            data_quality: dict 数据质量——
                — requested_symbols: 请求的股票列表
                — valid_symbols: 有效股票数
                — returns_per_stock: 每只股票的收益率数
                — note: 说明
            message: 错误信息（仅 status="error" 时存在）
    """
    try:
        lookback_days = max(20, min(int(lookback_days), 1000))
        sym_list = [s.strip() for s in symbols.split(",") if s.strip()]
        if len(sym_list) < 2:
            return json.dumps(
                {"status": "error", "message": "至少需要 2 只股票"},
                ensure_ascii=False, indent=2, default=str,
            )

        method_map = {"pearson": "pearson", "spearman": "spearman", "kendall": "kendall"}
        corr_method = method_map.get(method, "pearson")

        # 获取每只股票的日线和收益率
        end = datetime.date.today()
        start = end - datetime.timedelta(days=lookback_days + 30)

        returns_by_symbol: Dict[str, List[float]] = {}
        dates_by_symbol: Dict[str, List[str]] = {}
        min_bars = float("inf")

        for sym in sym_list:
            quotes = get_stock_daily_quotes(
                sym,
                start_date=start.isoformat(),
                end_date=end.isoformat(),
                period="daily",
                limit=lookback_days + 60,
            )
            if not quotes or len(quotes) < 20:
                continue
            dates = []
            closes = []
            for q in quotes:
                c = _to_float(q.get("close"))
                d = str(q.get("trade_date", ""))
                if c is not None and c > 0 and d:
                    closes.append(c)
                    dates.append(d)
            if len(closes) < 20:
                continue
            rets = [(closes[i] - closes[i - 1]) / closes[i - 1] for i in range(1, len(closes))]
            returns_by_symbol[sym] = rets
            dates_by_symbol[sym] = dates[1:]  # returns align with dates[1:]
            min_bars = min(min_bars, len(rets))

        if len(returns_by_symbol) < 2:
            return json.dumps(
                {"status": "error", "message": "至少需要 2 只有足够行情数据的股票"},
                ensure_ascii=False, indent=2, default=str,
            )

        # 对齐到相同长度
        aligned_symbols = list(returns_by_symbol.keys())
        aligned_returns: Dict[str, List[float]] = {}
        for sym in aligned_symbols:
            aligned_returns[sym] = returns_by_symbol[sym][-min_bars:]

        # 构建矩阵
        n = len(aligned_symbols)
        matrix = [[0.0] * n for _ in range(n)]
        top_pairs = []

        for i in range(n):
            for j in range(n):
                if i == j:
                    matrix[i][j] = 1.0
                elif j > i:
                    xi = np.array(aligned_returns[aligned_symbols[i]])
                    xj = np.array(aligned_returns[aligned_symbols[j]])

                    if corr_method == "pearson":
                        r = float(np.corrcoef(xi, xj)[0, 1])
                    elif corr_method == "spearman":
                        from scipy.stats import spearmanr
                        r = float(spearmanr(xi, xj)[0])
                    elif corr_method == "kendall":
                        from scipy.stats import kendalltau
                        r = float(kendalltau(xi, xj)[0])
                    else:
                        r = float(np.corrcoef(xi, xj)[0, 1])

                    matrix[i][j] = round(r, 4)
                    matrix[j][i] = round(r, 4)

                    if abs(r) > 0.7:
                        top_pairs.append({
                            "stock_a": aligned_symbols[i],
                            "stock_b": aligned_symbols[j],
                            "correlation": round(r, 4),
                            "strength": "强正相关" if r > 0 else "强负相关",
                        })

        top_pairs.sort(key=lambda x: abs(x["correlation"]), reverse=True)

        payload = {
            "symbols": aligned_symbols,
            "method": corr_method,
            "bars_used": min_bars,
            "correlation_matrix": [
                {"symbol": aligned_symbols[i], "values": matrix[i]}
                for i in range(n)
            ],
            "top_correlated_pairs": top_pairs[:20],
            "data_quality": {
                "requested_symbols": sym_list,
                "valid_symbols": len(aligned_symbols),
                "returns_per_stock": min_bars,
                "note": "收益率基于日收盘价计算。Spearman/Kendall 需 scipy 支持。",
            },
        }

        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("相关性矩阵计算失败: %s", exc, exc_info=True)
        return json.dumps(
            {"status": "error", "message": str(exc)},
            ensure_ascii=False, indent=2, default=str,
        )


# ────────────────────────────────────────────────────────────────
# Tool 2: 协整检验
# ────────────────────────────────────────────────────────────────


@tool
@register_tool(
    tool_id="get_cointegration_test",
    name="协整检验",
    description=(
        "对两只股票进行协整检验。"
        "使用 OLS 回归 y = α + β × x + ε，对残差进行 ADF 平稳性检验，"
        "判断是否存在协整关系，并计算均值回归半衰期。"
    ),
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="medium",
    capability_tags=["statistics", "cointegration", "pairs_trading", "quantitative"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["配对交易策略研究", "均值回归分析", "统计套利机会识别"],
    when_to_use=(
        "当需要判断两只股票是否存在长期均衡关系、为配对交易策略做准备、"
        "或评估价差序列的均值回归特性时使用。"
    ),
    when_not_to_use=(
        "不适合单股票分析；至少需要约 60 个交易日数据才有统计意义；"
        "不适合因果关系检验。"
    ),
    returns=(
        "返回 JSON 字符串，包含 beta、alpha、hedge_ratio、adf_statistic、"
        "p_value、is_cointegrated、half_life、spread_series（最近 10 期）。"
    ),
    example="get_cointegration_test(symbol_x='600519', symbol_y='000858')",
    related_tools=[
        "get_correlation_matrix",
        "get_stationarity_test",
    ],
)
def get_cointegration_test(
    symbol_x: Annotated[str, "第一只股票代码，如 600519"],
    symbol_y: Annotated[str, "第二只股票代码，如 000858"],
    lookback_days: Annotated[int, "回溯天数，默认 504（约 2 年）"] = 504,
) -> str:
    """对两只股票进行协整检验。

    Args:
        symbol_x: 第一只股票代码（如 "600519"）
        symbol_y: 第二只股票代码（如 "000858"）
        lookback_days: 回溯天数（自动截断到 60-2000），默认 504

    Returns:
        str: JSON 字符串，字段说明——
            status: 状态（仅在异常时为 "error"）
            symbol_x: 第一只股票代码
            symbol_y: 第二只股票代码
            alpha: OLS 回归截距
            beta: OLS 回归斜率（对冲比率）
            hedge_ratio: 对冲比率（= beta）
            adf_statistic: ADF 检验统计量
            p_value: ADF 检验 p 值
            is_cointegrated: 是否协整（p<0.05）
            half_life_days: 均值回归半衰期（天，无法计算时为 None）
            current_z_score: 当前价差 Z-Score
            spread_series: list[dict] 最近10期价差序列，元素结构——
                — date: 日期
                — spread: 价差
            bars_used: 共同交易日数
            interpretation: 解读文本
            message: 错误信息（仅 status="error" 时存在）
    """
    try:
        lookback_days = max(60, min(int(lookback_days), 2000))

        end = datetime.date.today()
        start = end - datetime.timedelta(days=lookback_days + 30)

        quotes_x = get_stock_daily_quotes(
            symbol_x, start_date=start.isoformat(), end_date=end.isoformat(),
            period="daily", limit=lookback_days + 60,
        )
        quotes_y = get_stock_daily_quotes(
            symbol_y, start_date=start.isoformat(), end_date=end.isoformat(),
            period="daily", limit=lookback_days + 60,
        )

        if not quotes_x or not quotes_y:
            return json.dumps(
                {"status": "error", "message": "未能获取足够行情数据"},
                ensure_ascii=False, indent=2, default=str,
            )

        # 按 trade_date 对齐
        prices_x: Dict[str, float] = {}
        prices_y: Dict[str, float] = {}
        for q in quotes_x:
            d = str(q.get("trade_date", ""))
            c = _to_float(q.get("close"))
            if c and c > 0 and d:
                prices_x[d] = c
        for q in quotes_y:
            d = str(q.get("trade_date", ""))
            c = _to_float(q.get("close"))
            if c and c > 0 and d:
                prices_y[d] = c

        common_dates = sorted(set(prices_x.keys()) & set(prices_y.keys()))
        if len(common_dates) < 30:
            return json.dumps(
                {"status": "error", "message": f"共同交易日不足（仅 {len(common_dates)} 天）"},
                ensure_ascii=False, indent=2, default=str,
            )

        px = np.array([prices_x[d] for d in common_dates], dtype=float)
        py = np.array([prices_y[d] for d in common_dates], dtype=float)

        # OLS: y = α + β × x + ε
        X = np.vstack([np.ones(len(px)), px]).T
        beta_vec = np.linalg.lstsq(X, py, rcond=None)[0]
        alpha = float(beta_vec[0])
        beta = float(beta_vec[1])
        residuals = py - (alpha + beta * px)

        hedge_ratio = beta  # 对冲比率 = β

        # ADF 检验残差
        adf_stat, p_value = _adf_test_simple(residuals.tolist())
        is_cointegrated = p_value < 0.05

        # 半衰期
        half_life: Optional[float] = None
        rho = _safe_autocorr(residuals.tolist(), lag=1)
        if rho is not None and 0 < rho < 1:
            half_life = round(-math.log(2) / math.log(rho), 2)

        # 价差序列（最近 10 期）
        spread = py - beta * px  # 价差 = y - β × x
        spread_series = [
            {"date": common_dates[i], "spread": round(float(spread[i]), 4)}
            for i in range(max(0, len(spread) - 10), len(spread))
        ]

        current_spread = float(spread[-1]) if len(spread) > 0 else 0
        spread_mean = float(np.mean(spread))
        spread_std = float(np.std(spread))
        z_score = (current_spread - spread_mean) / spread_std if spread_std > 0 else 0

        payload = {
            "symbol_x": symbol_x,
            "symbol_y": symbol_y,
            "alpha": round(alpha, 4),
            "beta": round(beta, 4),
            "hedge_ratio": round(hedge_ratio, 4),
            "adf_statistic": round(adf_stat, 4),
            "p_value": round(p_value, 4),
            "is_cointegrated": is_cointegrated,
            "half_life_days": half_life,
            "current_z_score": round(z_score, 4),
            "spread_series": spread_series,
            "bars_used": len(common_dates),
            "interpretation": (
                "残差序列平稳（p<0.05），存在协整关系" if is_cointegrated
                else "残差序列非平稳，不存在协整关系"
            ),
        }

        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("协整检验失败: %s", exc, exc_info=True)
        return json.dumps(
            {"status": "error", "message": str(exc)},
            ensure_ascii=False, indent=2, default=str,
        )


# ────────────────────────────────────────────────────────────────
# Tool 3: 滚动回归
# ────────────────────────────────────────────────────────────────


@tool
@register_tool(
    tool_id="get_rolling_regression",
    name="滚动回归",
    description=(
        "对股票相对于基准指数（默认沪深300）的收益率进行滚动 OLS 回归，"
        "计算滚动 Beta、Alpha 和 R²。可用于分析 Beta 稳定性。"
    ),
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="medium",
    capability_tags=["statistics", "beta", "rolling_regression", "quantitative"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["Beta 稳定性分析", "因子暴露时变性研究", "风险模型验证"],
    when_to_use=(
        "当需要分析股票 Beta 是否随时间变化、评估滚动 Alpha 趋势、"
        "或检查相对于基准的风险暴露稳定性时使用。"
    ),
    when_not_to_use=(
        "不适合单期静态 Beta 计算；数据不足（< window+20 个交易日）无法计算。"
    ),
    returns=(
        "返回 JSON 字符串，包含 rolling_beta（最近 20 期）、rolling_alpha、"
        "rolling_r_squared、latest_beta、beta_stability。"
    ),
    example="get_rolling_regression(symbol='600519', benchmark_symbol='000300')",
    related_tools=[
        "get_correlation_matrix",
        "get_stationarity_test",
    ],
)
def get_rolling_regression(
    symbol: Annotated[str, "股票代码，如 600519"],
    benchmark_symbol: Annotated[str, "基准指数代码，默认 000300（沪深 300）"] = "000300",
    lookback_days: Annotated[int, "总回溯天数，默认 504（约 2 年）"] = 504,
    window: Annotated[int, "滚动窗口大小（交易日数），默认 60"] = 60,
) -> str:
    """对个股相对基准指数进行滚动回归。

    Args:
        symbol: 股票代码（如 "600519"）
        benchmark_symbol: 基准指数代码，默认 "000300"（沪深300）
        lookback_days: 总回溯天数（自动截断到 100-2000），默认 504
        window: 滚动窗口大小（交易日数，自动截断到 20 至 lookback_days/2），默认 60

    Returns:
        str: JSON 字符串，字段说明——
            status: 状态（仅在异常时为 "error"）
            symbol: 股票代码
            benchmark: 基准指数代码
            window_days: 滚动窗口大小
            total_bars: 收益率总数
            rolling_windows_computed: 计算出的滚动窗口数
            latest_beta: 最新 Beta 值
            latest_alpha: 最新 Alpha 值
            latest_r_squared: 最新 R² 值
            beta_stability: Beta 稳定性（标准差）
            beta_stability_interpretation: Beta 稳定性解读: "稳定" | "中等波动" | "高度波动"
            rolling_series: list[dict] 最近20个滚动回归结果，元素结构——
                — beta: Beta 值
                — alpha: Alpha 值
                — r_squared: R² 值
            message: 错误信息（仅 status="error" 时存在）
    """
    try:
        lookback_days = max(100, min(int(lookback_days), 2000))
        window = max(20, min(int(window), lookback_days // 2))

        end = datetime.date.today()
        start = end - datetime.timedelta(days=lookback_days + 30)

        quotes_stock = get_stock_daily_quotes(
            symbol, start_date=start.isoformat(), end_date=end.isoformat(),
            period="daily", limit=lookback_days + 60,
        )

        # 基准指数：000300 用 AKShare 兜底
        quotes_bm = _try_get_benchmark_quotes(benchmark_symbol, start, end, lookback_days)

        if not quotes_stock or not quotes_bm:
            return json.dumps(
                {"status": "error", "message": "未能获取足够行情数据"},
                ensure_ascii=False, indent=2, default=str,
            )

        # 按日期对齐收盘价
        prices_s: Dict[str, float] = {}
        prices_b: Dict[str, float] = {}
        for q in quotes_stock:
            d = str(q.get("trade_date", ""))
            c = _to_float(q.get("close"))
            if c and c > 0 and d:
                prices_s[d] = c
        for q in quotes_bm:
            d = str(q.get("trade_date", ""))
            c = _to_float(q.get("close"))
            if c and c > 0 and d:
                prices_b[d] = c

        common_dates = sorted(set(prices_s.keys()) & set(prices_b.keys()))
        if len(common_dates) < window + 10:
            return json.dumps(
                {"status": "error", "message": f"共同交易日不足（仅 {len(common_dates)} 天，需要至少 {window + 10} 天）"},
                ensure_ascii=False, indent=2, default=str,
            )

        ps_arr = np.array([prices_s[d] for d in common_dates], dtype=float)
        pb_arr = np.array([prices_b[d] for d in common_dates], dtype=float)

        # 收益率
        ret_s = (ps_arr[1:] - ps_arr[:-1]) / ps_arr[:-1]
        ret_b = (pb_arr[1:] - pb_arr[:-1]) / pb_arr[:-1]

        # 滚动回归
        rolling_beta = []
        rolling_alpha = []
        rolling_r2 = []

        for i in range(window, len(ret_s)):
            y = ret_s[i - window:i]
            x = ret_b[i - window:i]

            if np.std(x) == 0:
                continue

            X = np.vstack([np.ones(window), x]).T
            beta_vec = np.linalg.lstsq(X, y, rcond=None)[0]
            a = float(beta_vec[0])
            b = float(beta_vec[1])

            y_pred = a + b * x
            ss_res = np.sum((y - y_pred) ** 2)
            ss_tot = np.sum((y - np.mean(y)) ** 2)
            r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

            rolling_alpha.append(round(a, 6))
            rolling_beta.append(round(b, 4))
            rolling_r2.append(round(float(r2), 4))

        if not rolling_beta:
            return json.dumps(
                {"status": "error", "message": "滚动回归计算失败"},
                ensure_ascii=False, indent=2, default=str,
            )

        latest_beta = rolling_beta[-1]
        beta_std = float(np.std(rolling_beta)) if len(rolling_beta) > 1 else 0.0

        # 最近 20 个滚动值
        n_latest = min(20, len(rolling_beta))
        rolling_series = [
            {
                "beta": rolling_beta[-(n_latest - i)],
                "alpha": rolling_alpha[-(n_latest - i)],
                "r_squared": rolling_r2[-(n_latest - i)],
            }
            for i in range(n_latest - 1, -1, -1)
        ]

        payload = {
            "symbol": symbol,
            "benchmark": benchmark_symbol,
            "window_days": window,
            "total_bars": len(ret_s),
            "rolling_windows_computed": len(rolling_beta),
            "latest_beta": latest_beta,
            "latest_alpha": round(rolling_alpha[-1], 6),
            "latest_r_squared": round(rolling_r2[-1], 4),
            "beta_stability": round(beta_std, 4),
            "beta_stability_interpretation": (
                "稳定" if beta_std < 0.1
                else "中等波动" if beta_std < 0.3
                else "高度波动"
            ),
            "rolling_series": rolling_series,
        }

        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("滚动回归失败: %s", exc, exc_info=True)
        return json.dumps(
            {"status": "error", "message": str(exc)},
            ensure_ascii=False, indent=2, default=str,
        )


# ────────────────────────────────────────────────────────────────
# Tool 4: 正态性检验
# ────────────────────────────────────────────────────────────────


@tool
@register_tool(
    tool_id="get_normality_test",
    name="正态性检验",
    description=(
        "对股票日收益率进行 Jarque-Bera 正态性检验。"
        "计算偏度、峰度，判断收益率分布是否服从正态分布。"
    ),
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["statistics", "normality", "quantitative"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["收益率分布分析", "风险管理假设检验", "金融计量研究"],
    when_to_use=(
        "当需要检验股票收益率是否服从正态分布（许多风险模型的假设前提）、"
        "或分析收益率分布的偏度和峰度特征时使用。"
    ),
    when_not_to_use=(
        "不适合单一日收益率计算；数据不足（< 30 个交易日）结果不可靠。"
    ),
    returns=(
        "返回 JSON 字符串，包含 jb_stat、p_value、is_normal、"
        "skewness、kurtosis、interpretation。"
    ),
    example="get_normality_test(symbol='600519')",
    related_tools=[
        "get_stationarity_test",
        "get_garch_volatility",
    ],
)
def get_normality_test(
    symbol: Annotated[str, "A 股股票代码，如 600519"],
    lookback_days: Annotated[int, "回溯天数，默认 252（约 1 年）"] = 252,
) -> str:
    """对股票日收益率进行 Jarque-Bera 正态性检验。

    Args:
        symbol: A 股股票代码（如 "600519"）
        lookback_days: 回溯天数（自动截断到 30-1000），默认 252

    Returns:
        str: JSON 字符串，字段说明——
            status: 状态（仅在异常时为 "error"）
            symbol: 股票代码
            jb_statistic: Jarque-Bera 统计量
            p_value: p 值
            is_normal: 是否服从正态分布（p>0.05）
            skewness: 偏度
            kurtosis: 峰度
            excess_kurtosis: 超额峰度（kurtosis - 3）
            samples_used: 样本数
            interpretation: 解读文本
            message: 错误信息（仅 status="error" 时存在）
    """
    try:
        lookback_days = max(30, min(int(lookback_days), 1000))

        quotes = _fetch_quotes(symbol, lookback_days)
        if not quotes or len(quotes) < 30:
            return json.dumps(
                {"status": "error", "message": f"行情数据不足（仅 {len(quotes) if quotes else 0} 条）"},
                ensure_ascii=False, indent=2, default=str,
            )

        returns = _compute_daily_returns(quotes)
        if len(returns) < 30:
            return json.dumps(
                {"status": "error", "message": f"有效收益率数据不足（仅 {len(returns)} 个）"},
                ensure_ascii=False, indent=2, default=str,
            )

        ret_arr = np.array(returns)
        n = len(ret_arr)
        skewness = float(np.mean((ret_arr - np.mean(ret_arr)) ** 3) / (np.std(ret_arr) ** 3 + 1e-10))
        kurtosis = float(np.mean((ret_arr - np.mean(ret_arr)) ** 4) / (np.std(ret_arr) ** 4 + 1e-10))

        # Jarque-Bera 检验
        try:
            from scipy import stats
            jb_stat, p_value = stats.jarque_bera(ret_arr)
        except ImportError:
            # 手动计算
            jb_stat = n / 6.0 * (skewness ** 2 + (kurtosis - 3) ** 2 / 4.0)
            from scipy.stats import chi2
            p_value = 1.0 - chi2.cdf(jb_stat, df=2)

        is_normal = p_value > 0.05

        # 解读
        if abs(skewness) < 0.5:
            skew_desc = "接近对称"
        elif skewness > 0:
            skew_desc = "右偏（正偏），正收益极端值较多"
        else:
            skew_desc = "左偏（负偏），负收益极端值较多"

        if abs(kurtosis - 3) < 0.5:
            kurt_desc = "接近正态峰度"
        elif kurtosis > 3:
            kurt_desc = f"尖峰（kurtosis={kurtosis:.2f}），厚尾分布"
        else:
            kurt_desc = f"低峰（kurtosis={kurtosis:.2f}），薄尾分布"

        payload = {
            "symbol": symbol,
            "jb_statistic": round(float(jb_stat), 4),
            "p_value": round(float(p_value), 4),
            "is_normal": is_normal,
            "skewness": round(float(skewness), 4),
            "kurtosis": round(float(kurtosis), 4),
            "excess_kurtosis": round(float(kurtosis - 3), 4),
            "samples_used": n,
            "interpretation": (
                f"收益率分布{'服从' if is_normal else '不服从'}正态分布 (p={'%.4f' % p_value})。"
                f" 偏度: {skew_desc}。峰度: {kurt_desc}。"
            ),
        }

        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("正态性检验失败: %s", exc, exc_info=True)
        return json.dumps(
            {"status": "error", "message": str(exc)},
            ensure_ascii=False, indent=2, default=str,
        )


# ────────────────────────────────────────────────────────────────
# Tool 5: 平稳性检验
# ────────────────────────────────────────────────────────────────


@tool
@register_tool(
    tool_id="get_stationarity_test",
    name="平稳性检验",
    description=(
        "对股票价格序列进行 ADF（Augmented Dickey-Fuller）平稳性检验。"
        "判断价格序列是否具有单位根（非平稳）。"
    ),
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["statistics", "stationarity", "adf", "quantitative"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["时间序列平稳性判断", "单位根检验", "建模前提验证"],
    when_to_use=(
        "当需要判断股票价格序列是否平稳（许多时间序列模型的前提假设）、"
        "或检验单位根存在性时使用。"
    ),
    when_not_to_use=(
        "不适合收益率序列（收益率通常已平稳）；"
        "数据不足（< 30 个交易日）结果不可靠。"
    ),
    returns=(
        "返回 JSON 字符串，包含 adf_statistic、p_value、is_stationary、"
        "critical_values、test_type 和 interpretation。"
    ),
    example="get_stationarity_test(symbol='600519')",
    related_tools=[
        "get_normality_test",
        "get_cointegration_test",
    ],
)
def get_stationarity_test(
    symbol: Annotated[str, "A 股股票代码，如 600519"],
    lookback_days: Annotated[int, "回溯天数，默认 252（约 1 年）"] = 252,
    price_type: Annotated[str, "价格类型：close（收盘价）/ adjusted（后复权），默认 close"] = "close",
) -> str:
    """对股票价格序列进行 ADF 平稳性检验。

    Args:
        symbol: A 股股票代码（如 "600519"）
        lookback_days: 回溯天数（自动截断到 30-2000），默认 252
        price_type: 价格类型: "close"（收盘价）或 "adjusted"（后复权），默认 "close"

    Returns:
        str: JSON 字符串，字段说明——
            status: 状态（仅在异常时为 "error"）
            symbol: 股票代码
            price_type: 价格类型
            adf_statistic: ADF 检验统计量
            p_value: p 值
            is_stationary: 是否平稳（p<0.05）
            critical_values: dict 临界值——
                — "1%": 1% 临界值
                — "5%": 5% 临界值
                — "10%": 10% 临界值
            test_type: 检验类型说明
            samples_used: 样本数
            interpretation: 解读文本
            message: 错误信息（仅 status="error" 时存在）
    """
    try:
        lookback_days = max(30, min(int(lookback_days), 2000))

        quotes = _fetch_quotes(symbol, lookback_days)
        if not quotes or len(quotes) < 30:
            return json.dumps(
                {"status": "error", "message": "行情数据不足"},
                ensure_ascii=False, indent=2, default=str,
            )

        # 根据 price_type 选择价格字段
        if price_type == "adjusted":
            fields = ["adj_close", "adj_close", "close"]
        else:
            fields = ["close"]

        prices = []
        for q in quotes:
            c = None
            for f in fields:
                c = _to_float(q.get(f))
                if c is not None and c > 0:
                    break
            if c is not None and c > 0:
                prices.append(c)

        if len(prices) < 30:
            return json.dumps(
                {"status": "error", "message": f"有效价格数据不足（仅 {len(prices)} 条）"},
                ensure_ascii=False, indent=2, default=str,
            )

        # ADF 检验
        adf_stat, p_value = _adf_test_simple(prices)
        test_type = "ADF (Augmented Dickey-Fuller, simplified)"

        is_stationary = p_value < 0.05

        # 临界值
        critical_values = {
            "1%": -3.43,
            "5%": -2.86,
            "10%": -2.57,
        }

        payload = {
            "symbol": symbol,
            "price_type": price_type,
            "adf_statistic": round(adf_stat, 4),
            "p_value": round(p_value, 4),
            "is_stationary": is_stationary,
            "critical_values": critical_values,
            "test_type": test_type,
            "samples_used": len(prices),
            "interpretation": (
                f"价格序列{'平稳（拒绝单位根假设）' if is_stationary else '非平稳（无法拒绝单位根假设）'}。"
                f" ADF 统计量 = {adf_stat:.4f}，p 值 = {p_value:.4f}。"
                f" {'注意：股票价格通常非平稳，差分或取对数后可能平稳。' if not is_stationary else ''}"
            ),
        }

        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("平稳性检验失败: %s", exc, exc_info=True)
        return json.dumps(
            {"status": "error", "message": str(exc)},
            ensure_ascii=False, indent=2, default=str,
        )


# ────────────────────────────────────────────────────────────────
# Tool 6: GARCH 波动率（EWMA 简化版）
# ────────────────────────────────────────────────────────────────


@tool
@register_tool(
    tool_id="get_garch_volatility",
    name="EWMA 条件波动率",
    description=(
        "使用 EWMA（指数加权移动平均）模型估计股票的条件波动率。"
        "采用 RiskMetrics 标准衰减因子 λ=0.94。"
        "比较当前波动率与长期历史波动率。"
    ),
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["statistics", "volatility", "garch", "ewma", "quantitative"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["条件波动率估计", "风险度量（VaR 输入）", "波动率趋势分析"],
    when_to_use=(
        "当需要估计股票当前的条件波动率水平、比较不同时期的波动率变化、"
        "或为风险管理模型提供波动率输入时使用。"
    ),
    when_not_to_use=(
        "不适合直接预测未来波动率（EWMA 是简化方法）；"
        "数据不足（< 60 个交易日）结果不可靠。"
    ),
    returns=(
        "返回 JSON 字符串，包含 current_volatility（年化）、long_term_vol、"
        "vol_ratio、volatility_series（最近 20 期）、method_note。"
    ),
    example="get_garch_volatility(symbol='600519')",
    related_tools=[
        "get_normality_test",
        "get_stationarity_test",
    ],
)
def get_garch_volatility(
    symbol: Annotated[str, "A 股股票代码，如 600519"],
    lookback_days: Annotated[int, "回溯天数，默认 504（约 2 年）"] = 504,
    p: Annotated[int, "GARCH 滞后阶数 p，默认 1（在 EWMA 模式下固定为 EWMA）"] = 1,
    q: Annotated[int, "ARCH 滞后阶数 q，默认 1（在 EWMA 模式下固定为 EWMA）"] = 1,
) -> str:
    """使用 EWMA（RiskMetrics 标准）估计条件波动率。

    Args:
        symbol: A 股股票代码（如 "600519"）
        lookback_days: 回溯天数（自动截断到 60-2000），默认 504
        p: GARCH 滞后阶数 p（当前实现固定为 EWMA，参数保留），默认 1
        q: ARCH 滞后阶数 q（当前实现固定为 EWMA，参数保留），默认 1

    Returns:
        str: JSON 字符串，字段说明——
            status: 状态（仅在异常时为 "error"）
            symbol: 股票代码
            model: 模型标识（固定为 "EWMA (RiskMetrics, λ=0.94)"）
            current_volatility: 当前条件波动率（年化）
            long_term_historical_volatility: 长期历史波动率（年化）
            volatility_ratio: 当前/长期 波动率比值
            volatility_regime: 波动率状态: "高波动（当前 > 长期 × 1.2）" | "低波动（当前 < 长期 × 0.8）" | "正常波动"
            volatility_series: list[dict] 最近20期波动率序列，元素结构——
                — date: 日期
                — daily_volatility: 日波动率
                — annualized_volatility: 年化波动率
            method_note: 方法说明
            bars_used: 使用的收益率样本数
            message: 错误信息（仅 status="error" 时存在）
    """
    try:
        lookback_days = max(60, min(int(lookback_days), 2000))

        quotes = _fetch_quotes(symbol, lookback_days)
        if not quotes or len(quotes) < 60:
            return json.dumps(
                {"status": "error", "message": "行情数据不足"},
                ensure_ascii=False, indent=2, default=str,
            )

        returns = _compute_daily_returns(quotes)
        if len(returns) < 60:
            return json.dumps(
                {"status": "error", "message": f"有效收益率数据不足（仅 {len(returns)} 个）"},
                ensure_ascii=False, indent=2, default=str,
            )

        ret_arr = np.array(returns)

        # EWMA: σ²_t = λ × σ²_{t-1} + (1-λ) × r²_{t-1}
        lam = 0.94  # RiskMetrics 标准
        n = len(ret_arr)
        sigma2 = np.zeros(n)

        # 初始化：使用前 10 个收益率的方差
        sigma2[0] = np.var(ret_arr[:10]) if n >= 10 else np.var(ret_arr)

        for t in range(1, n):
            sigma2[t] = lam * sigma2[t - 1] + (1 - lam) * ret_arr[t - 1] ** 2

        sigma = np.sqrt(sigma2)

        # 年化（假设 252 个交易日）
        annual_factor = math.sqrt(252)
        current_vol = float(sigma[-1] * annual_factor)
        long_term_vol = float(np.std(ret_arr) * annual_factor)

        # 波动率序列（最近 20 期）
        vol_series = [
            {
                "date": str(quotes[min(i + 1, len(quotes) - 1)].get("trade_date", "")),
                "daily_volatility": round(float(sigma[i]), 6),
                "annualized_volatility": round(float(sigma[i] * annual_factor), 4),
            }
            for i in range(max(0, n - 20), n)
        ]

        vol_ratio = current_vol / long_term_vol if long_term_vol > 0 else 1.0

        payload = {
            "symbol": symbol,
            "model": "EWMA (RiskMetrics, λ=0.94)",
            "current_volatility": round(current_vol, 4),
            "long_term_historical_volatility": round(long_term_vol, 4),
            "volatility_ratio": round(vol_ratio, 4),
            "volatility_regime": (
                "高波动（当前 > 长期 × 1.2）" if vol_ratio > 1.2
                else "低波动（当前 < 长期 × 0.8）" if vol_ratio < 0.8
                else "正常波动"
            ),
            "volatility_series": vol_series,
            "method_note": (
                "使用 RiskMetrics EWMA 模型（λ=0.94）估计条件波动率。"
                "年化因子 = sqrt(252)。"
                "完整 GARCH(p,q) 需要非线性优化求解，此处以 EWMA 作为简化替代。"
            ),
            "bars_used": n,
        }

        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("GARCH 波动率建模失败: %s", exc, exc_info=True)
        return json.dumps(
            {"status": "error", "message": str(exc)},
            ensure_ascii=False, indent=2, default=str,
        )


__all__ = [
    "get_correlation_matrix",
    "get_cointegration_test",
    "get_rolling_regression",
    "get_normality_test",
    "get_stationarity_test",
    "get_garch_volatility",
]