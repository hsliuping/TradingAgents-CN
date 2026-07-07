"""可比公司估值工具"""

import json
import logging
from typing import Annotated

from langchain_core.tools import tool

from core.skill_runtime.data_access import (
    get_industry_peer_basic_info,
    get_latest_stock_price,
    get_stock_basic_info,
    summarize_industry_valuation,
)
from core.skill_runtime.standard_financial_apis import get_security_master
from core.tools.base import register_tool

logger = logging.getLogger(__name__)


def _safe_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _calc_percentile(values: list[float], current: float) -> float | None:
    valid = [v for v in values if v is not None and v > 0]
    if not valid:
        return None
    return round(sum(1 for v in valid if v <= current) / len(valid) * 100, 1)


@tool
@register_tool(
    tool_id="get_comparable_company_valuation",
    name="可比公司估值",
    description="通过与同行业公司在PE、PB、PS估值指标上的对比，评估当前股票估值水平，计算估值溢价/折价和隐含公允价值。",
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["valuation", "peer_comparison", "relative_valuation"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["relative_valuation", "peer_valuation_comparison"],
    when_to_use="当需要了解股票在同行业中的估值水平、判断估值偏高或偏低时使用。",
    when_not_to_use="不适合跨行业比较；不适用于净利润为负的公司（PE 无法计算，但 PB/PS 仍可用）。",
    returns="返回JSON字符串，包含valuation_comparison（PE/PB/PS对比）、overall_assessment和fair_value_estimate。",
    example="get_comparable_company_valuation(symbol='600519')",
    related_tools=["get_dcf_valuation", "get_stock_valuation_context"],
)
def get_comparable_company_valuation(symbol: Annotated[str, "A 股股票代码，如 600519、000001"]) -> str:
    """计算可比公司估值，通过与行业PE/PB/PS对比评估估值水平。

    Args:
        symbol: A 股股票代码（6 位数字或含交易所前后缀），如 600519、000001

    Returns:
        str: JSON 字符串，包含以下可能结构——

        错误情形返回 dict，字段：
            status: "error"
            message: 错误描述
            symbol: 股票代码（部分情形附带）
            industry: 行业（仅在「未找到可比公司」错误时附）

        成功情形返回 dict，字段：
            symbol: 股票代码
            name: 股票名称
            industry: 所属行业
            peers_in_industry: 行业内可比公司数量
            valuation_comparison: 各指标对比 dict，键为 "pe" / "pb" / "ps"（仅含可用指标）—
                stock: 当前股票该指标值
                industry_median: 行业中位数
                industry_mean: 行业均值
                premium_pct: 相对中位数的溢价/折价百分比
                percentile: 当前值在行业样本中的百分位
            overall_assessment: 综合评估 dict —
                average_premium_pct: 加权平均溢价百分比
                valuation_level: 估值水平："偏高" | "略高" | "合理" | "略低" | "偏低"
                peers_available: 可比公司数量
            fair_value_estimate: 隐含公允价值 dict —
                based_on_pe: 基于 PE 估算的公允价格（可选）
                based_on_pb: 基于 PB 估算的公允价格（可选）
                based_on_ps: 基于 PS 估算的公允价格（可选）
                current_price: 当前股价
            data_quality: 数据质量 dict —
                warnings: 警告信息列表

        异常时返回 dict：{"status": "error", "message": ...}
    """
    try:
        warnings: list[str] = []

        # 1. 获取股票基础信息
        basic_info = get_stock_basic_info(symbol)
        if not basic_info:
            return json.dumps(
                {"status": "error", "message": f"未获取到 {symbol} 的基础信息", "symbol": symbol},
                ensure_ascii=False, indent=2, default=str,
            )

        # 2. 获取证券主数据（含行业、名称）
        master = get_security_master(symbol)
        industry = master.get("industry")
        name = master.get("name") or basic_info.get("name")

        if not industry:
            return json.dumps(
                {"status": "error", "message": f"未获取到 {symbol} 的行业信息", "symbol": symbol},
                ensure_ascii=False, indent=2, default=str,
            )

        # 3. 获取当前估值指标
        pe_ttm = _safe_float(basic_info.get("pe_ttm") or basic_info.get("pe"))
        pb = _safe_float(basic_info.get("pb") or basic_info.get("pb_mrq"))
        ps_ttm = _safe_float(basic_info.get("ps_ttm") or basic_info.get("ps"))
        total_mv = _safe_float(basic_info.get("total_mv") or basic_info.get("market_cap") or basic_info.get("market_value"))
        current_price = get_latest_stock_price(symbol)

        # 4. 获取行业估值统计
        industry_pe = summarize_industry_valuation(industry, metric="pe", exclude_symbol=symbol)
        industry_pb = summarize_industry_valuation(industry, metric="pb", exclude_symbol=symbol)
        industry_ps = summarize_industry_valuation(industry, metric="ps", exclude_symbol=symbol)

        peers_count = max(
            industry_pe.get("count", 0),
            industry_pb.get("count", 0),
            industry_ps.get("count", 0),
        )

        if peers_count == 0:
            return json.dumps(
                {
                    "status": "error",
                    "message": f"行业「{industry}」中未找到可比公司数据",
                    "symbol": symbol,
                    "industry": industry,
                },
                ensure_ascii=False, indent=2, default=str,
            )

        # 5. 计算各指标溢价/折让
        valuation_comparison: dict = {}

        def _build_metric_comparison(
            metric_name: str,
            stock_value: float | None,
            industry_stats: dict,
        ) -> dict | None:
            if stock_value is None or stock_value <= 0:
                return None
            median_val = industry_stats.get("median")
            mean_val = industry_stats.get("average")
            count = industry_stats.get("count", 0)
            if median_val is None or median_val <= 0:
                return None
            premium_pct = round((stock_value / median_val - 1) * 100, 1)

            # 获取所有同行样本值以计算百分位
            samples = industry_stats.get("samples") or []
            values = [s.get(metric_name) for s in samples if s.get(metric_name) is not None]
            # 补充从 get_industry_peer_basic_info 获取更多样本
            peers = get_industry_peer_basic_info(industry, exclude_symbol=symbol, limit=200)
            field_map = {"pe": "pe_ttm", "pb": "pb", "ps": "ps_ttm"}
            field = field_map.get(metric_name, metric_name)
            for p in peers:
                v = _safe_float(p.get(field) or p.get(field.replace("_ttm", "")))
                if v is not None and v > 0:
                    values.append(v)

            percentile = _calc_percentile(values, stock_value) if values else None

            return {
                "stock": stock_value,
                "industry_median": median_val,
                "industry_mean": mean_val,
                "premium_pct": premium_pct,
                "percentile": percentile,
            }

        pe_comp = _build_metric_comparison("pe", pe_ttm, industry_pe)
        pb_comp = _build_metric_comparison("pb", pb, industry_pb)
        ps_comp = _build_metric_comparison("ps", ps_ttm, industry_ps)

        if pe_comp:
            valuation_comparison["pe"] = pe_comp
        if pb_comp:
            valuation_comparison["pb"] = pb_comp
        if ps_comp:
            valuation_comparison["ps"] = ps_comp

        if not valuation_comparison:
            return json.dumps(
                {
                    "status": "error",
                    "message": f"无法计算 {symbol} 的有效估值对比（估值指标或行业数据不足）",
                    "symbol": symbol,
                },
                ensure_ascii=False, indent=2, default=str,
            )

        # 6. 综合评估
        premiums = [
            comp["premium_pct"]
            for comp in valuation_comparison.values()
            if isinstance(comp, dict) and comp.get("premium_pct") is not None
        ]

        if premiums:
            average_premium = round(sum(premiums) / len(premiums), 1)
        else:
            average_premium = 0.0

        if average_premium > 50:
            valuation_level = "偏高"
        elif average_premium > 20:
            valuation_level = "略高"
        elif average_premium < -30:
            valuation_level = "偏低"
        elif average_premium < -10:
            valuation_level = "略低"
        else:
            valuation_level = "合理"

        # 7. 隐含公允价值估算
        fair_value_estimate: dict = {}
        if current_price is not None and current_price > 0 and average_premium != -100:
            if pe_comp and pe_comp.get("premium_pct") is not None:
                fair_pe = current_price / (1 + pe_comp["premium_pct"] / 100)
                fair_value_estimate["based_on_pe"] = round(fair_pe, 2)
            if pb_comp and pb_comp.get("premium_pct") is not None:
                fair_pb = current_price / (1 + pb_comp["premium_pct"] / 100)
                fair_value_estimate["based_on_pb"] = round(fair_pb, 2)
            if ps_comp and ps_comp.get("premium_pct") is not None:
                fair_ps = current_price / (1 + ps_comp["premium_pct"] / 100)
                fair_value_estimate["based_on_ps"] = round(fair_ps, 2)
            fair_value_estimate["current_price"] = current_price

        # 标注数据质量
        if peers_count < 10:
            warnings.append(f"行业可比公司仅 {peers_count} 家，统计参考价值有限")
        if pe_comp is None:
            warnings.append("PE 不可用（净利润可能为负），已跳过 PE 对比")
        if pb_comp is None:
            warnings.append("PB 不可用，已跳过 PB 对比")
        if ps_comp is None:
            warnings.append("PS 不可用，已跳过 PS 对比")

        warnings.append("基于当前行业估值分布")

        payload = {
            "symbol": symbol,
            "name": name,
            "industry": industry,
            "peers_in_industry": peers_count,
            "valuation_comparison": valuation_comparison,
            "overall_assessment": {
                "average_premium_pct": average_premium,
                "valuation_level": valuation_level,
                "peers_available": peers_count,
            },
            "fair_value_estimate": fair_value_estimate,
            "data_quality": {
                "warnings": warnings,
            },
        }

        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("可比公司估值失败: %s", exc, exc_info=True)
        return json.dumps(
            {"status": "error", "message": str(exc)},
            ensure_ascii=False, indent=2, default=str,
        )


__all__ = ["get_comparable_company_valuation"]
