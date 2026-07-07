"""股息率估值增强与行业估值分布工具。

提供：
1. get_dividend_valuation_context — 股息率估值增强
2. get_industry_valuation_distribution — 行业估值分布
"""

import json
import logging
from statistics import mean, median
from typing import Annotated, Any, Dict, List, Optional

from langchain_core.tools import tool

from core.skill_runtime.data_access import (
    get_latest_stock_price,
    get_stock_basic_info,
)
from core.skill_runtime.standard_financial_apis import (
    get_historical_financial_annual_series,
    get_shareholder_return_metrics,
)
from core.tools.base import register_tool

logger = logging.getLogger(__name__)


# ==================== 工具内部 helper ====================

def _safe_div(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def _safe_float(value) -> Optional[float]:
    if value is None or isinstance(value, bool):
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
        text = str(value).strip()
        if not text:
            return None
        numeric = float(text)
        if numeric != numeric:
            return None
        return numeric
    except (TypeError, ValueError):
        return None


def _cagr(values: List[Optional[float]]) -> Optional[float]:
    """计算 3 年 CAGR（年复合增长率）。"""
    valid = [v for v in values if v is not None and v > 0]
    if len(valid) < 2:
        return None
    n = len(valid)
    return (valid[0] / valid[-1]) ** (1.0 / max(n - 1, 1)) - 1.0


def _json_response(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def _fetch_akshare_dividend_yield(symbol: str) -> Optional[Dict[str, Any]]:
    """尝试用 AKShare 东方财富分红数据兜底。"""
    try:
        import akshare as ak
        df = ak.stock_dividents_cninfo(symbol=symbol)
        if df is None or df.empty:
            return None
        # 只取已实施的记录
        df = df[df["实施进度"] == "实施"]
        if df.empty:
            return None
        df = df.sort_values("股权登记日", ascending=False)
        records = df.head(5).to_dict("records")
        return {"source": "akshare", "records": records}
    except Exception as exc:
        logger.warning("AKShare dividend fallback failed: %s", exc)
        return None


# ==================== Tool 1: 股息率估值增强 ====================

@tool
@register_tool(
    tool_id="get_dividend_valuation_context",
    name="股息率估值增强",
    description=(
        "基于分红记录计算当前股息率、5年平均股息率、股息率历史分位、"
        "派息率、股息增长率（3年CAGR），并给出估值信号（低于平均=低估）。"
        "本地数据不足时通过 AKShare 兜底。"
    ),
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["valuation", "dividend", "dividend_yield", "payout_ratio", "dividend_growth"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["分红估值分析", "股息率历史分位", "派息率评估"],
    when_to_use="当需要股息率估值、分红回报分析、股息率历史分位或股息增长率时使用。",
    when_not_to_use="不适合无分红记录的公司（会返回 no_dividend_data）。不适合高增长不派息企业。",
    returns="返回 JSON 字符串，包含 current_yield、avg_5y_yield、yield_percentile、payout_ratio、dividend_growth、valuation_signal、dividend_history、data_quality。",
    example="get_dividend_valuation_context(symbol='600519')",
    related_tools=["get_ddm_valuation", "get_dividend_data"],
)
def get_dividend_valuation_context(
    symbol: Annotated[str, "A 股股票代码，如 600519、000001"],
) -> str:
    """获取股息率估值增强上下文。

    Args:
        symbol: A 股股票代码，如 "600519"、"000001"

    Returns:
        str: JSON 字符串，字段说明——
            status: 状态: "success" | "error"
            symbol: 标准化后的 6 位股票代码
            current_price: 当前股价
            current_yield: 当前股息率（小数）
            current_yield_pct: 当前股息率（%）
            avg_5y_yield: 5年平均股息率（小数）
            avg_5y_yield_pct: 5年平均股息率（%）
            yield_percentile: 当前股息率历史分位（0-100）
            payout_ratio: 派息率（小数）
            payout_ratio_pct: 派息率（%）
            dividend_growth: 股息3年CAGR（小数）
            dividend_growth_pct: 股息3年CAGR（%）
            valuation_signal: 估值信号: "低估" | "中性" | "高估"
            dividend_history: list[dict] 分红历史（最近5年），元素结构——
                — year: 年份
                — cash_dividend_per_share: 每股现金分红
                — dividend_yield: 股息率（小数）
                — dividend_yield_pct: 股息率（%）
            data_quality: 数据质量: "数据充足" | "数据有限" | "数据不足"
            data_source: 数据来源标识
            warnings: list[str] 警告列表
            message: 错误信息（仅 status="error" 时存在）
    """
    try:
        normalized_symbol = str(symbol).strip().upper()
        for prefix in ("SH", "SZ", "SS", "BJ"):
            normalized_symbol = normalized_symbol.replace(prefix, "")
        normalized_symbol = "".join(ch for ch in normalized_symbol if ch.isdigit())[-6:].zfill(6)
        if not normalized_symbol:
            return _json_response({"status": "error", "message": "无效股票代码"})

        # 1. 获取当前价格
        current_price = get_latest_stock_price(normalized_symbol)
        if current_price is None or current_price <= 0:
            basic = get_stock_basic_info(normalized_symbol) or {}
            current_price = _safe_float(basic.get("close") or basic.get("current_price"))

        if current_price is None or current_price <= 0:
            return _json_response({"status": "error", "message": "未获取到有效现价", "symbol": normalized_symbol})

        # 2. 获取股东回报/分红数据
        shareholder = get_shareholder_return_metrics(normalized_symbol, years=5)
        dividend_annual = shareholder.get("annual") or []
        dividend_records = shareholder.get("records") or []
        data_source = shareholder.get("data_source") or "local"

        # 如果本地分红数据不足，尝试 AKShare 兜底
        if not dividend_annual and not dividend_records:
            akshare_data = _fetch_akshare_dividend_yield(normalized_symbol)
            if akshare_data:
                data_source = akshare_data.get("source", "akshare")

        # 3. 计算各年度股息率
        annual_yields: List[Dict[str, Any]] = []
        for entry in dividend_annual:
            year = entry.get("year")
            cash = _safe_float(entry.get("cash_dividend_per_share"))
            if year and cash is not None:
                yield_val = cash / current_price
                annual_yields.append({
                    "year": year,
                    "cash_dividend_per_share": cash,
                    "dividend_yield": yield_val,
                    "dividend_yield_pct": round(yield_val * 100, 4),
                })

        # 4. 核心指标
        current_yield = annual_yields[0]["dividend_yield"] if annual_yields else None
        yield_values = [item["dividend_yield"] for item in annual_yields if item["dividend_yield"] is not None]
        avg_5y_yield = mean(yield_values) if yield_values else None

        # 股息率历史分位（当前 yield 在历史队列中的位置）
        yield_percentile = None
        if current_yield is not None and yield_values:
            sorted_yields = sorted(yield_values)
            yield_percentile = sum(1 for y in sorted_yields if y <= current_yield) / len(sorted_yields) * 100

        # 5. 派息率（最近一期）
        payout_ratio = None
        financial = get_historical_financial_annual_series(normalized_symbol, years=3)
        financial_records = financial.get("records") or []
        latest_cash = annual_yields[0].get("cash_dividend_per_share") if annual_yields else None
        if financial_records and latest_cash is not None:
            latest_financial = financial_records[0]
            net_profit = _safe_float(latest_financial.get("net_profit"))
            if net_profit is not None and net_profit > 0:
                basic_info = get_stock_basic_info(normalized_symbol) or {}
                # total_share/total_shares 单位为「万股」，需 ×1e4 换算成「股」，
                # 否则 net_profit（元）/ 万股 会把 EPS 放大 1e4 倍，
                # 导致派息率被缩小 1e4 倍（如茅台会算出 0.03%，实际约 50%）。
                raw_shares = _safe_float(basic_info.get("total_share") or basic_info.get("total_shares"))
                total_shares = raw_shares * 1e4 if raw_shares is not None and raw_shares > 0 else None
                if total_shares is not None and total_shares > 0:
                    eps_approximate = net_profit / total_shares
                    payout_ratio = latest_cash / eps_approximate if eps_approximate > 0 else None

        # 6. 股息增长率（3年CAGR）
        cash_values = [item["cash_dividend_per_share"] for item in annual_yields[:3]]
        dividend_growth = _cagr(cash_values) if len(cash_values) >= 2 else None

        # 7. 估值信号
        valuation_signal = "中性"
        if current_yield is not None and avg_5y_yield is not None:
            if current_yield > avg_5y_yield:
                valuation_signal = "低估"
            else:
                valuation_signal = "高估"

        # 8. 数据质量
        data_quality = "数据充足" if len(annual_yields) >= 3 else "数据有限" if annual_yields else "数据不足"

        return _json_response({
            "status": "success",
            "symbol": normalized_symbol,
            "current_price": current_price,
            "current_yield": round(current_yield, 6) if current_yield is not None else None,
            "current_yield_pct": round(current_yield * 100, 4) if current_yield is not None else None,
            "avg_5y_yield": round(avg_5y_yield, 6) if avg_5y_yield is not None else None,
            "avg_5y_yield_pct": round(avg_5y_yield * 100, 4) if avg_5y_yield is not None else None,
            "yield_percentile": round(yield_percentile, 2) if yield_percentile is not None else None,
            "payout_ratio": round(payout_ratio, 4) if payout_ratio is not None else None,
            "payout_ratio_pct": round(payout_ratio * 100, 2) if payout_ratio is not None else None,
            "dividend_growth": round(dividend_growth, 6) if dividend_growth is not None else None,
            "dividend_growth_pct": round(dividend_growth * 100, 4) if dividend_growth is not None else None,
            "valuation_signal": valuation_signal,
            "dividend_history": annual_yields[:5],
            "data_quality": data_quality,
            "data_source": data_source,
            "warnings": [] if annual_yields else ["未找到分红数据，无法计算股息率估值。"],
        })
    except Exception as exc:
        logger.error("股息率估值增强获取失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"股息率估值增强获取失败: {exc}"})


# ==================== Tool 2: 行业估值分布 ====================

@tool
@register_tool(
    tool_id="get_industry_valuation_distribution",
    name="行业估值分布",
    description=(
        "按行业统计 PE/PB 分布（计数、均值、中位数、P25、P75、最小、最大），"
        "并返回各行业最便宜和最贵的 Top 10 股票。"
        "若指定 industry 则只分析该行业，否则遍历所有行业。"
    ),
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    when_to_use="当需要行业估值分布、行业 PE/PB 统计、寻找行业内低估/高估个股时使用。",
    returns="返回 JSON 字符串，包含 distribution_stats、cheapest_stocks、priciest_stocks、data_quality。",
    example="get_industry_valuation_distribution(industry='白酒')",
)
def get_industry_valuation_distribution(
    industry: Annotated[str, "行业名称，如 '白酒'、'银行'；为空时分析所有行业"] = "",
) -> str:
    """获取行业估值分布。

    Args:
        industry: 行业名称（如 "白酒"、"银行"），为空字符串时分析所有行业，默认 ""

    Returns:
        str: JSON 字符串，字段说明——
            status: 状态: "success" | "no_data" | "error"
            industries_covered: 覆盖的行业数
            total_stocks_analyzed: 分析的股票总数
            distribution_stats: dict 行业估值统计，key 为行业名，value 结构——
                — pe: dict PE分布（count/mean/median/p25/p75/min/max）
                — pb: dict PB分布（count/mean/median/p25/p75/min/max）
                — sample_count: 样本数
            cheapest_stocks: dict 各行业 PE 最低的 Top 10 股票列表，元素结构——
                — symbol: 股票代码
                — name: 股票名称
                — pe: PE值
                — pb: PB值
                — total_mv: 总市值
            priciest_stocks: dict 各行业 PE 最高的 Top 10 股票列表（结构同上）
            data_quality: 数据质量: "数据充足" | "数据不足"
            warnings: list[str] 警告列表
            message: 错误或提示信息（仅 status 为 "no_data"/"error" 时存在）
    """
    try:
        # 从 stock_basic_info 获取全量数据
        # 通过 project_access 的聚合或直接查询
        from core.skill_runtime.project_access import query_stock_collection

        target_industry = str(industry).strip() if industry else None

        # 构造过滤条件
        filters: Dict[str, Any] = {}
        if target_industry:
            filters["industry"] = target_industry
        else:
            filters["industry"] = {"$ne": None, "$ne": ""}

        # 查询所有有行业归属的股票
        stocks = query_stock_collection(
            "stock_basic_info",
            filters=filters,
            projection={
                "_id": 0, "symbol": 1, "name": 1, "industry": 1,
                "pe": 1, "pe_ttm": 1, "pb": 1, "pb_mrq": 1,
                "total_mv": 1, "market_cap": 1,
            },
            limit=500,
        )

        if not stocks:
            msg = f"未找到行业 '{target_industry}' 的股票数据" if target_industry else "未找到有行业归属的股票数据"
            return _json_response({"status": "no_data", "message": msg})

        # 按行业分组，或直接使用目标行业
        industry_groups: Dict[str, List[Dict[str, Any]]] = {}
        for stock in stocks:
            ind = str(stock.get("industry") or "").strip()
            if not ind:
                continue
            industry_groups.setdefault(ind, []).append(stock)

        distribution_stats: Dict[str, Dict[str, Any]] = {}
        cheapest_stocks: Dict[str, List[Dict[str, Any]]] = {}
        priciest_stocks: Dict[str, List[Dict[str, Any]]] = {}

        for ind, group in industry_groups.items():
            pe_values = [
                _safe_float(s.get("pe") or s.get("pe_ttm"))
                for s in group
                if _safe_float(s.get("pe") or s.get("pe_ttm")) is not None and _safe_float(s.get("pe") or s.get("pe_ttm")) > 0
            ]
            pb_values = [
                _safe_float(s.get("pb") or s.get("pb_mrq"))
                for s in group
                if _safe_float(s.get("pb") or s.get("pb_mrq")) is not None and _safe_float(s.get("pb") or s.get("pb_mrq")) > 0
            ]

            def _dist(vals: List[float]) -> Dict[str, Any]:
                if not vals:
                    return {"count": 0, "mean": None, "median": None, "p25": None, "p75": None, "min": None, "max": None}
                sorted_vals = sorted(vals)
                n = len(sorted_vals)
                return {
                    "count": n,
                    "mean": round(mean(sorted_vals), 4),
                    "median": round(median(sorted_vals), 4),
                    "p25": round(sorted_vals[n // 4], 4),
                    "p75": round(sorted_vals[3 * n // 4], 4),
                    "min": round(sorted_vals[0], 4),
                    "max": round(sorted_vals[-1], 4),
                }

            distribution_stats[ind] = {
                "pe": _dist(pe_values),
                "pb": _dist(pb_values),
                "sample_count": len(group),
            }

            # Top 10 cheapest / priciest by PE
            pe_stocks = [
                {"symbol": s.get("symbol"), "name": s.get("name"), "pe": _safe_float(s.get("pe") or s.get("pe_ttm")), "pb": _safe_float(s.get("pb") or s.get("pb_mrq")), "total_mv": _safe_float(s.get("total_mv") or s.get("market_cap"))}
                for s in group
                if _safe_float(s.get("pe") or s.get("pe_ttm")) is not None and _safe_float(s.get("pe") or s.get("pe_ttm")) > 0
            ]
            pe_sorted = sorted(pe_stocks, key=lambda x: x["pe"])
            cheapest_stocks[ind] = pe_sorted[:10]
            priciest_stocks[ind] = list(reversed(pe_sorted[-10:])) if len(pe_sorted) >= 10 else list(reversed(pe_sorted))

        # 如果指定了行业，只返回该行业的数据
        if target_industry and target_industry in distribution_stats:
            result_stats = {target_industry: distribution_stats[target_industry]}
            result_cheapest = {target_industry: cheapest_stocks.get(target_industry, [])}
            result_priciest = {target_industry: priciest_stocks.get(target_industry, [])}
        else:
            result_stats = distribution_stats
            result_cheapest = cheapest_stocks
            result_priciest = priciest_stocks

        total_stocks = sum(v.get("sample_count", 0) for v in result_stats.values())
        industries_covered = len(result_stats)

        return _json_response({
            "status": "success",
            "industries_covered": industries_covered,
            "total_stocks_analyzed": total_stocks,
            "distribution_stats": result_stats,
            "cheapest_stocks": result_cheapest,
            "priciest_stocks": result_priciest,
            "data_quality": "数据充足" if total_stocks > 0 else "数据不足",
            "warnings": [] if total_stocks > 0 else ["未获取到有效数据。"],
        })
    except Exception as exc:
        logger.error("行业估值分布获取失败: %s", exc, exc_info=True)
        return _json_response({"status": "error", "message": f"行业估值分布获取失败: {exc}"})


__all__ = [
    "get_dividend_valuation_context",
    "get_industry_valuation_distribution",
]