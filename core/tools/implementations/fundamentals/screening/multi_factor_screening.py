"""多因子选股工具。

根据用户指定的因子条件（PE、ROE、资产负债率等）对 A 股全市场进行筛选和评分。
"""

import json
import logging
from typing import Annotated, Any, Dict, List, Optional, Tuple

from langchain_core.tools import tool

from core.skill_runtime.data_access import get_stock_financial_periods
from core.tools.base import register_tool

logger = logging.getLogger(__name__)

# 候选池上限（按总市值取前 N 只作为筛选候选）
MAX_CANDIDATES = 500
DEFAULT_LIMIT = 30

# 支持的因子及其在数据中的字段名
SUPPORTED_FACTORS = {
    "pe_ttm": {"label": "市盈率(TTM)", "source": "basic_info", "fields": ["pe_ttm", "pe"]},
    "pb": {"label": "市净率", "source": "basic_info", "fields": ["pb", "pb_mrq"]},
    "ps_ttm": {"label": "市销率(TTM)", "source": "basic_info", "fields": ["ps_ttm", "ps"]},
    "total_mv": {"label": "总市值", "source": "basic_info", "fields": ["total_mv"]},
    "roe": {"label": "净资产收益率", "source": "financial", "fields": ["roe", "roe_avg", "roe_waa"]},
    "roa": {"label": "总资产收益率", "source": "financial", "fields": ["roa", "roa2"]},
    "debt_to_assets": {"label": "资产负债率", "source": "financial", "fields": ["debt_to_assets"]},
    "gross_margin": {"label": "毛利率", "source": "financial", "fields": ["grossprofit_margin", "gross_margin"]},
    "netprofit_margin": {"label": "净利率", "source": "financial", "fields": ["netprofit_margin"]},
    "current_ratio": {"label": "流动比率", "source": "financial", "fields": ["current_ratio"]},
}


def _get_db():
    """获取同步 MongoDB 连接。"""
    from app.core.database import get_mongo_db_sync

    return get_mongo_db_sync()


def _safe_float(value: Any) -> Optional[float]:
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


def _get_field(record: Dict[str, Any], *field_names: str) -> Optional[float]:
    """从记录中按优先级尝试获取字段值。"""
    for field_name in field_names:
        value = _safe_float(record.get(field_name))
        if value is not None:
            return value
    return None


def _parse_criteria(criteria_json: str) -> Tuple[Dict[str, Dict[str, float]], List[str]]:
    """解析筛选条件 JSON，返回 (条件字典, 警告列表)。"""
    warnings: List[str] = []
    try:
        raw = json.loads(criteria_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"条件 JSON 解析失败: {exc}")

    if not isinstance(raw, dict):
        raise ValueError("条件必须为 JSON 对象，如 {\"pe_ttm\": {\"min\": 0, \"max\": 20}}")

    parsed: Dict[str, Dict[str, float]] = {}
    for factor_key, constraints in raw.items():
        if factor_key not in SUPPORTED_FACTORS:
            warnings.append(f"不支持因子 '{factor_key}'，已忽略。支持: {', '.join(SUPPORTED_FACTORS)}")
            continue
        if not isinstance(constraints, dict):
            warnings.append(f"因子 '{factor_key}' 的条件格式错误，已忽略")
            continue
        parsed[factor_key] = {}
        for op_key in ("min", "max"):
            if op_key in constraints:
                try:
                    parsed[factor_key][op_key] = float(constraints[op_key])
                except (TypeError, ValueError):
                    warnings.append(f"因子 '{factor_key}' 的 {op_key} 值不是有效数值，已忽略")

    if not parsed:
        raise ValueError("未解析出任何有效条件")

    return parsed, warnings


def _fetch_candidate_universe() -> List[Dict[str, Any]]:
    """从 stock_basic_info 获取候选股票池（取市值前 N 且 PE>0）。"""
    db = _get_db()
    col = db["stock_basic_info"]

    cursor = col.find(
        {
            "total_mv": {"$gt": 0, "$exists": True},
            "pe_ttm": {"$gt": 0, "$exists": True},
        },
        {
            "_id": 0,
            "symbol": 1,
            "name": 1,
            "industry": 1,
            "pe_ttm": 1,
            "pe": 1,
            "pb": 1,
            "pb_mrq": 1,
            "ps_ttm": 1,
            "ps": 1,
            "total_mv": 1,
        },
    ).sort("total_mv", -1).limit(MAX_CANDIDATES)

    return list(cursor)


def _enrich_with_financials(stocks: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """为每只股票补充最近的财务指标（ROE、资产负债率等）。"""
    enriched: Dict[str, Dict[str, Any]] = {}
    for stock in stocks:
        symbol = str(stock.get("symbol") or "").strip().zfill(6)
        if not symbol:
            continue

        # 从 basic_info 已有的字段复制
        enriched[symbol] = {
            "symbol": symbol,
            "name": stock.get("name", ""),
            "industry": stock.get("industry", ""),
            "pe_ttm": _get_field(stock, "pe_ttm", "pe"),
            "pb": _get_field(stock, "pb", "pb_mrq"),
            "ps_ttm": _get_field(stock, "ps_ttm", "ps"),
            "total_mv": _safe_float(stock.get("total_mv")),
        }

        # 获取财务周期数据补充 ROE、资产负债率等
        try:
            periods = get_stock_financial_periods(symbol, limit=1)
            if periods and isinstance(periods, list) and len(periods) > 0:
                latest = periods[0]
                roe = _get_field(latest, "roe", "roe_avg", "roe_waa")
                if roe is not None:
                    enriched[symbol]["roe"] = roe

                debt_to_assets = _get_field(latest, "debt_to_assets")
                if debt_to_assets is not None:
                    enriched[symbol]["debt_to_assets"] = debt_to_assets

                gross_margin = _get_field(latest, "grossprofit_margin", "gross_margin")
                if gross_margin is not None:
                    enriched[symbol]["gross_margin"] = gross_margin

                netprofit_margin = _get_field(latest, "netprofit_margin")
                if netprofit_margin is not None:
                    enriched[symbol]["netprofit_margin"] = netprofit_margin

                roa = _get_field(latest, "roa", "roa2")
                if roa is not None:
                    enriched[symbol]["roa"] = roa

                current_ratio = _get_field(latest, "current_ratio")
                if current_ratio is not None:
                    enriched[symbol]["current_ratio"] = current_ratio

        except Exception:
            pass  # 财务数据缺失不阻塞筛选

    return enriched


def _get_factor_value(
    stock: Dict[str, Any],
    factor_key: str,
) -> Optional[float]:
    """从股票数据中获取指定因子的值。"""
    factor_def = SUPPORTED_FACTORS.get(factor_key)
    if not factor_def:
        return None
    return _get_field(stock, *factor_def["fields"])


def _normalize_score(value: float, min_val: float, max_val: float) -> float:
    """将值归一化到 0-100 分。"""
    if max_val <= min_val:
        return 50.0
    clipped = max(min_val, min(max_val, value))
    return (clipped - min_val) / (max_val - min_val) * 100.0


def _score_stock(
    stock: Dict[str, Any],
    criteria: Dict[str, Dict[str, float]],
) -> Tuple[float, Dict[str, Any], List[str]]:
    """对单只股票打分。

    Returns:
        (总分, 各因子得分和指标, 警告列表)
    """
    all_warnings: List[str] = []
    factor_scores: Dict[str, Any] = {}
    score_sum = 0.0
    valid_factors = 0

    for factor_key, constraints in criteria.items():
        value = _get_factor_value(stock, factor_key)
        factor_label = SUPPORTED_FACTORS.get(factor_key, {}).get("label", factor_key)

        if value is None:
            all_warnings.append(f"{stock.get('symbol', '')} 缺少 {factor_label}")
            factor_scores[factor_key] = {"value": None, "score": 0, "passed": False}
            continue

        factor_scores[factor_key] = {"value": round(value, 4)}

        # 检查是否满足条件
        passed = True
        min_val = constraints.get("min")
        max_val = constraints.get("max")

        if min_val is not None and value < min_val:
            passed = False
        if max_val is not None and value > max_val:
            passed = False

        factor_scores[factor_key]["passed"] = passed

        if not passed:
            factor_scores[factor_key]["score"] = 0
            continue

        # 计算归一化得分
        norm_min = min_val if min_val is not None else 0.0
        norm_max = max_val if max_val is not None else value * 2.0
        if min_val is None and max_val is not None:
            norm_min = 0.0
        if max_val is None and min_val is not None:
            norm_max = min_val * 2.0

        score = _normalize_score(value, norm_min, norm_max) if norm_max > norm_min else 50.0
        factor_scores[factor_key]["score"] = round(score, 1)
        score_sum += score
        valid_factors += 1

    total_score = round(score_sum / max(valid_factors, 1), 1)
    return total_score, factor_scores, all_warnings


@tool
@register_tool(
    tool_id="get_multi_factor_screening",
    name="多因子选股",
    description=(
        "根据用户指定的多因子条件从 A 股全市场筛选股票，并对每只股票进行评分。"
        "支持的因子：pe_ttm（市盈率）、pb（市净率）、ps_ttm（市销率）、"
        "total_mv（总市值）、roe（净资产收益率）、roa（总资产收益率）、"
        "debt_to_assets（资产负债率）、gross_margin（毛利率）、"
        "netprofit_margin（净利率）、current_ratio（流动比率）。"
        "条件格式为 JSON，如 {\"pe_ttm\": {\"min\": 0, \"max\": 20}, \"roe\": {\"min\": 15}}。"
    ),
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="heavy",
    capability_tags=["screening", "multi_factor", "fundamentals"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["多因子条件选股", "全市场批量筛选", "因子评分排序"],
    when_to_use=(
        "当需要根据多个基本面因子条件从全市场筛选股票时使用。"
        "例如：PE<20 且 ROE>15% 且 资产负债率<50%。"
        "候选池按总市值取前 500 只。"
    ),
    when_not_to_use=(
        "不适合查询单只股票的详细基本面因子（请用 get_fundamental_factor_snapshot_tool）；"
        "不适合技术指标选股或 K 线形态筛选。"
    ),
    returns=(
        "返回 JSON 字符串，包含 criteria_applied（应用的条件）、total_screened（候选总数）、"
        "passed（通过数）、results（排名列表，含各因子得分和总分）、data_quality（数据说明）。"
    ),
    example=(
        'get_multi_factor_screening(criteria=\'{"pe_ttm": {"min": 0, "max": 20}, '
        '"roe": {"min": 15}, "debt_to_assets": {"max": 50}}\')'
    ),
    related_tools=[
        "screen_stocks_by_criteria",
        "get_fundamental_factor_snapshot_tool",
        "get_value_factor_bundle_tool",
    ],
)
def get_multi_factor_screening(
    criteria: Annotated[str, "因子条件 JSON 字符串，例如 '{\"pe_ttm\": {\"min\": 0, \"max\": 20}, \"roe\": {\"min\": 15}}'"],
    sort_by: Annotated[str, "排序字段：score（总分）、pe_ttm、pb、roe、total_mv，默认 score"] = "score",
    limit: Annotated[int, "返回前 N 只股票，默认 30"] = DEFAULT_LIMIT,
) -> str:
    """多因子选股工具。

    从 A 股全市场（按总市值取前 500 只作为候选池）筛选满足多因子条件的股票，
    并计算综合评分。

    Args:
        criteria: 因子条件 JSON
        sort_by: 排序字段
        limit: 返回数量

    Returns:
        JSON 字符串格式的筛选结果
    """
    try:
        limit = max(1, min(int(limit), 100))

        # 1. 解析条件
        parsed_criteria, parse_warnings = _parse_criteria(criteria)

        # 2. 获取候选池
        raw_candidates = _fetch_candidate_universe()
        total_candidates = len(raw_candidates)

        if total_candidates == 0:
            return json.dumps(
                {
                    "status": "error",
                    "message": "未从 stock_basic_info 获取到有效的候选股票",
                },
                ensure_ascii=False,
                default=str,
            )

        # 3. 补充财务数据
        enriched = _enrich_with_financials(raw_candidates)

        # 4. 评分和筛选
        scored_results: List[Dict[str, Any]] = []
        all_warnings: List[str] = list(parse_warnings)

        for symbol, stock_data in enriched.items():
            total_score, factor_scores, stock_warnings = _score_stock(stock_data, parsed_criteria)
            all_warnings.extend(stock_warnings)

            # 检查是否所有条件都满足（硬筛选）
            all_passed = all(
                fs.get("passed", False) for fs in factor_scores.values()
            )

            if all_passed:
                metrics = {
                    "pe_ttm": stock_data.get("pe_ttm"),
                    "pb": stock_data.get("pb"),
                    "total_mv": stock_data.get("total_mv"),
                }
                # 补充财务指标
                for fin_key in ("roe", "roa", "debt_to_assets", "gross_margin", "netprofit_margin", "current_ratio"):
                    if fin_key in stock_data:
                        metrics[fin_key] = stock_data[fin_key]

                scored_results.append({
                    "symbol": symbol,
                    "name": stock_data.get("name", ""),
                    "industry": stock_data.get("industry", ""),
                    "score": total_score,
                    "factor_scores": factor_scores,
                    "metrics": {k: round(v, 4) if isinstance(v, float) else v for k, v in metrics.items() if v is not None},
                })

        # 5. 排序
        reverse = True
        if sort_by in ("pe_ttm",):
            reverse = False  # 估值越低越好

        if sort_by == "score":
            scored_results.sort(key=lambda x: x["score"], reverse=True)
        elif sort_by == "pe_ttm":
            scored_results.sort(
                key=lambda x: x.get("metrics", {}).get("pe_ttm", float("inf")),
                reverse=reverse,
            )
        elif sort_by == "pb":
            scored_results.sort(
                key=lambda x: x.get("metrics", {}).get("pb", float("inf")),
                reverse=reverse,
            )
        elif sort_by == "roe":
            scored_results.sort(
                key=lambda x: x.get("metrics", {}).get("roe", 0),
                reverse=True,
            )
        elif sort_by == "total_mv":
            scored_results.sort(
                key=lambda x: x.get("metrics", {}).get("total_mv", 0),
                reverse=True,
            )

        top_results = scored_results[:limit]

        # 6. 构建输出
        ranked_results = []
        for rank, item in enumerate(top_results, 1):
            ranked_results.append({
                "rank": rank,
                "symbol": item["symbol"],
                "name": item["name"],
                "industry": item["industry"],
                "score": item["score"],
                "factor_scores": item["factor_scores"],
                "metrics": item["metrics"],
            })

        payload = {
            "criteria_applied": {
                k: {op: round(v, 4) if isinstance(v, float) else v for op, v in constraints.items()}
                for k, constraints in parsed_criteria.items()
            },
            "total_screened": total_candidates,
            "passed": len(scored_results),
            "returned": len(ranked_results),
            "sort_by": sort_by,
            "results": ranked_results,
            "data_quality": {
                "candidates_examined": total_candidates,
                "financial_data_enriched": len(enriched),
                "warnings": all_warnings[:20],  # 截断过长警告
                "note": (
                    "候选池为按总市值排序的前 500 只 A 股（pe_ttm>0 且 total_mv>0）。"
                    "ROE、资产负债率等财务指标从最近一期财务报告获取，可能因数据同步延迟而不完整。"
                ),
            },
        }

        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    except ValueError as ve:
        return json.dumps({"status": "error", "message": str(ve)}, ensure_ascii=False, default=str)
    except Exception as exc:
        logger.error("多因子选股失败: %s", exc, exc_info=True)
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2, default=str)


__all__ = ["get_multi_factor_screening"]
