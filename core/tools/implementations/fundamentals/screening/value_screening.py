"""价值筛选工具集。

提供 4 个策略筛选工具：
1. get_graham_screen - 格雷厄姆式筛选（低估值、低负债、正利润）
2. get_growth_stock_screen - 成长股筛选（高增长、高 ROE）
3. get_dividend_stock_screen - 红利股筛选（高股息、稳定分红）
4. get_turnaround_screen - 困境反转筛选
"""

import json
import logging
import math
from typing import Annotated, Any, Dict, List, Optional, Tuple

from langchain_core.tools import tool

from core.skill_runtime.data_access import get_stock_financial_periods
from core.tools.base import register_tool
from core.tools.implementations.risk.extended_risk_models import (
    _detect_period_type,
    _annualize_factor,
    _find_same_period_prev,
    _PERIOD_LABELS,
)

logger = logging.getLogger(__name__)

# 候选池上限
MAX_CANDIDATES = 500
DEFAULT_LIMIT = 30


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


def _fetch_candidate_universe(extra_fields: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """从 stock_basic_info 获取候选股票池（取市值前 N 且 PE>0）。"""
    db = _get_db()
    col = db["stock_basic_info"]

    projection = {
        "_id": 0,
        "symbol": 1,
        "name": 1,
        "industry": 1,
        "pe_ttm": 1,
        "pe": 1,
        "pb": 1,
        "pb_mrq": 1,
        "total_mv": 1,
        "dividend_yield": 1,
        "dividend_yield_ttm": 1,
    }
    if extra_fields:
        for f in extra_fields:
            projection[f] = 1

    cursor = col.find(
        {
            "total_mv": {"$gt": 0, "$exists": True},
            "pe_ttm": {"$gt": 0, "$exists": True},
        },
        projection,
    ).sort("total_mv", -1).limit(MAX_CANDIDATES)

    return list(cursor)


def _enrich_with_financials(
    stocks: List[Dict[str, Any]],
    extra_fields: Optional[List[str]] = None,
) -> Dict[str, Dict[str, Any]]:
    """为每只股票补充最近的财务指标。"""
    enriched: Dict[str, Dict[str, Any]] = {}
    for stock in stocks:
        symbol = str(stock.get("symbol") or "").strip().zfill(6)
        if not symbol:
            continue

        record: Dict[str, Any] = {
            "symbol": symbol,
            "name": stock.get("name", ""),
            "industry": stock.get("industry", ""),
            "pe_ttm": _get_field(stock, "pe_ttm", "pe"),
            "pb": _get_field(stock, "pb", "pb_mrq"),
            "total_mv": _safe_float(stock.get("total_mv")),
            "dividend_yield": _get_field(stock, "dividend_yield", "dividend_yield_ttm"),
        }
        if extra_fields:
            for f in extra_fields:
                val = _safe_float(stock.get(f))
                if val is not None:
                    record[f] = val

        try:
            periods = get_stock_financial_periods(symbol, limit=4)
            if periods and isinstance(periods, list) and len(periods) > 0:
                latest = periods[0]

                roe = _get_field(latest, "roe", "roe_avg", "roe_waa")
                if roe is not None:
                    record["roe"] = roe

                debt_to_assets = _get_field(latest, "debt_to_assets")
                if debt_to_assets is not None:
                    record["debt_to_assets"] = debt_to_assets

                net_profit = _get_field(latest, "net_profit", "n_income_attr_p", "n_income", "net_income")
                if net_profit is not None:
                    record["net_profit"] = net_profit

                revenue = _get_field(latest, "revenue", "total_revenue", "oper_rev")
                if revenue is not None:
                    record["revenue"] = revenue

                n_cashflow_act = _get_field(latest, "n_cashflow_act")
                if n_cashflow_act is not None:
                    record["n_cashflow_act"] = n_cashflow_act

                total_liab = _get_field(latest, "total_liab")
                total_equity = _get_field(latest, "total_equity", "total_hldr_eqy_exc_min_int")
                if total_liab is not None and total_equity is not None and total_equity > 0:
                    record["debt_to_equity"] = total_liab / total_equity

                gross_margin = _get_field(latest, "grossprofit_margin", "gross_margin")
                if gross_margin is not None:
                    record["gross_margin"] = gross_margin

                # 多期数据用于增长计算
                if len(periods) >= 2:
                    rev_growth = _calc_growth(periods, "revenue", "total_revenue", "oper_rev")
                    if rev_growth is not None:
                        record["revenue_growth"] = rev_growth

                    np_growth = _calc_growth(periods, "net_profit", "n_income_attr_p", "n_income", "net_income")
                    if np_growth is not None:
                        record["net_profit_growth"] = np_growth

                # 尝试计算 3 年增长（需要多期数据）
                if len(periods) >= 4:
                    rev_growth_3y = _calc_cagr_3y(periods, "revenue", "total_revenue", "oper_rev")
                    if rev_growth_3y is not None:
                        record["revenue_growth_3y"] = rev_growth_3y

        except Exception:
            pass  # 财务数据缺失不阻塞筛选

    return enriched


def _calc_growth(periods: List[Dict[str, Any]], *fields: str) -> Optional[float]:
    """计算最新两期之间的同比增长率，自动处理口径差异。

    如果两期口径不一致（如一季报 vs 年报），先对非年报期做年化后再比较。
    仅在口径完全不同（如年报 vs 一季报无法简单年化对比）时跳过。
    """
    if len(periods) < 2:
        return None
    cur_type = _detect_period_type(periods[0])
    prev_type = _detect_period_type(periods[1])

    current = _get_field(periods[0], *fields)
    previous = _get_field(periods[1], *fields)

    if current is None or previous is None or previous == 0:
        return None

    # 🔑 口径一致时直接比较
    if cur_type == prev_type:
        return (current - previous) / abs(previous)

    # 🔑 口径不一致时，年化后再比较（利润表科目需要年化）
    # 仅对可能是利润表累计值的科目做年化（revenue / net_profit 等）
    cur_annualized = current * _annualize_factor(cur_type)
    prev_annualized = previous * _annualize_factor(prev_type)
    if prev_annualized == 0:
        return None
    return (cur_annualized - prev_annualized) / abs(prev_annualized)


def _calc_cagr_3y(periods: List[Dict[str, Any]], *fields: str) -> Optional[float]:
    """计算约 3 年的 CAGR。取最新期和最早期（约 3 年前）的数据。

    periods 按报告期倒序排列，取第 0 期（最新）和第 min(3, len-1) 期。
    仅在两期口径一致（都是年报或同一季报类型）时才计算，否则返回 None。
    """
    if len(periods) < 4:
        return None
    cur_type = _detect_period_type(periods[0])
    older_type = _detect_period_type(periods[3])

    current = _get_field(periods[0], *fields)
    older = _get_field(periods[3], *fields)

    if current is None or older is None or older <= 0 or current <= 0:
        return None

    # 🔑 CAGR 要求口径一致，否则跨年比较无意义
    if cur_type != older_type:
        return None

    ratio = current / older
    if ratio > 0:
        return ratio ** (1.0 / 3.0) - 1.0
    return None


def _score_item(
    score_components: List[Tuple[Optional[float], float, float]],
) -> float:
    """计算加权综合得分。

    Args:
        score_components: [(值, 权重, 最大值归一化), ...]
            如果值为 None，跳过该组件。
    """
    total_weight = 0.0
    weighted_sum = 0.0
    for value, weight, max_norm in score_components:
        if value is not None:
            # 归一化到 0-100
            normalized = min(100.0, max(0.0, value / max_norm * 100)) if max_norm > 0 else 50.0
            weighted_sum += normalized * weight
            total_weight += weight
    return round(weighted_sum / max(total_weight, 0.001), 1)


# ────────────────────────────────────────────────────────────────
# Tool 7: 格雷厄姆式筛选
# ────────────────────────────────────────────────────────────────


@tool
@register_tool(
    tool_id="get_graham_screen",
    name="格雷厄姆式筛选",
    description=(
        "按照本杰明·格雷厄姆的价值投资标准筛选 A 股。"
        "条件：PE < 15、PB < 1.5、负债权益比 < 1.0、净利润为正。"
        "按格雷厄姆数（√(22.5 × EPS × BVPS)） upside 排序。"
    ),
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="heavy",
    capability_tags=["screening", "value_investing", "graham", "fundamentals", "valuation"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["价值投资选股", "格雷厄姆策略", "低估股票筛选"],
    when_to_use=(
        "当用户想要寻找低估值的价值股、按照格雷厄姆的安全边际原则选股、"
        "或需要一份低估值的股票清单时使用。"
    ),
    when_not_to_use=(
        "不适合成长股、亏损企业筛选；"
        "不适合需要技术指标或行业主题筛选的场景。"
    ),
    returns=(
        "返回 JSON 字符串，包含 criteria_applied、total_screened、"
        "passed、results（按格雷厄姆数 upside 排序）。"
    ),
    example="get_graham_screen(limit=30)",
    related_tools=[
        "get_growth_stock_screen",
        "get_dividend_stock_screen",
        "get_multi_factor_screening",
    ],
)
def get_graham_screen(
    limit: Annotated[int, "返回前 N 只股票，默认 30"] = 30,
) -> str:
    """格雷厄姆式价值筛选。

    Args:
        limit: 返回前 N 只股票，默认 30，自动夹钳到 [1, 100]

    Returns:
        str: JSON 字符串，包含以下可能结构——

        错误情形返回 dict，字段：
            status: "error"
            message: 错误描述

        成功情形返回 dict，字段：
            criteria_applied: 筛选条件 dict —
                pe_ttm: dict — max: 15
                pb: dict — max: 1.5
                debt_to_equity: dict — max: 1.0
                net_profit: dict — min: 0
            total_screened: 候选池总数
            passed: 通过筛选的股票数
            returned: 实际返回数量
            results: 排序后的股票列表 [{"rank": 序号, "symbol": 代码, "name": 名称, "industry": 行业, "score": 综合得分, "pe_ttm": 市盈率, "pb": 市净率, "debt_to_equity": 债务股权比, "graham_number": 格雷厄姆数, "graham_upside_pct": 格雷厄姆数 upside 百分比}, ...]
            data_quality: 数据质量 dict —
                note: 候选池与方法说明文本

        异常时返回 dict：{"status": "error", "message": ...}
    """
    try:
        limit = max(1, min(int(limit), 100))

        raw_candidates = _fetch_candidate_universe()
        total_candidates = len(raw_candidates)

        if total_candidates == 0:
            return json.dumps(
                {"status": "error", "message": "未获取到候选股票"},
                ensure_ascii=False, indent=2, default=str,
            )

        enriched = _enrich_with_financials(raw_candidates)

        criteria = {
            "pe_ttm": {"max": 15},
            "pb": {"max": 1.5},
            "debt_to_equity": {"max": 1.0},
            "net_profit": {"min": 0},
        }

        passed_results: List[Dict[str, Any]] = []
        for symbol, data in enriched.items():
            pe = data.get("pe_ttm")
            pb = data.get("pb")
            debt_eq = data.get("debt_to_equity")
            net_profit = data.get("net_profit")

            if pe is None or pb is None:
                continue
            if pe <= 0 or pe >= 15:
                continue
            if pb <= 0 or pb >= 1.5:
                continue
            if debt_eq is not None and debt_eq >= 1.0:
                continue
            if net_profit is not None and net_profit <= 0:
                continue
            # 如果 net_profit 缺失，尝试其他利润字段
            if net_profit is None:
                continue

            # 格雷厄姆数 = √(22.5 × EPS × BVPS)
            # EPS ≈ net_profit / shares, BVPS ≈ equity / shares
            # Graham Number ≈ √(22.5 × NetProfit × Equity) / shares
            # 简化：格雷厄姆数 upside = (graham_price - current_price) / current_price
            total_equity = data.get("total_mv") / pb if pb and pb > 0 and data.get("total_mv") else None
            if total_equity and data.get("total_mv"):
                # graham_number = sqrt(22.5 * net_profit * total_equity) / (total_mv / price)
                # 简化计算 upside
                eps = net_profit / (data["total_mv"] / pe) if pe and pe > 0 else None
                bvps = total_equity / (data["total_mv"] / pe) if pe and pe > 0 else None

                graham_number = None
                if eps is not None and bvps is not None and eps > 0 and bvps > 0:
                    graham_number = math.sqrt(22.5 * eps * bvps)
            else:
                graham_number = None

            current_price = data["total_mv"] / (data["total_mv"] / pe) if pe and pe > 0 else None
            upside = None
            if graham_number is not None and current_price is not None and current_price > 0:
                upside = (graham_number - current_price) / current_price * 100

            score_components: List[Tuple[Optional[float], float, float]] = [
                (pe, 1.0, 15.0) if pe else (None, 0, 1),
                (pb, 1.0, 1.5) if pb else (None, 0, 1),
            ]
            # 倒转 PE 和 PB 得分（越低越好）
            pe_score = max(0, 100 - (pe / 15 * 100)) if pe else 0
            pb_score = max(0, 100 - (pb / 1.5 * 100)) if pb else 0
            total_score = round((pe_score + pb_score) / 2, 1)

            passed_results.append({
                "symbol": symbol,
                "name": data.get("name", ""),
                "industry": data.get("industry", ""),
                "pe_ttm": pe,
                "pb": pb,
                "debt_to_equity": round(debt_eq, 4) if debt_eq is not None else None,
                "net_profit": round(net_profit, 2) if net_profit is not None else None,
                "graham_number": round(graham_number, 2) if graham_number is not None else None,
                "graham_upside_pct": round(upside, 2) if upside is not None else None,
                "score": total_score,
            })

        # 按 upside 降序
        passed_results.sort(key=lambda x: x.get("graham_upside_pct") or -9999, reverse=True)
        top_results = passed_results[:limit]

        ranked = []
        for rank, item in enumerate(top_results, 1):
            ranked.append({
                "rank": rank,
                "symbol": item["symbol"],
                "name": item["name"],
                "industry": item["industry"],
                "score": item["score"],
                "pe_ttm": item["pe_ttm"],
                "pb": item["pb"],
                "debt_to_equity": item["debt_to_equity"],
                "graham_number": item["graham_number"],
                "graham_upside_pct": item["graham_upside_pct"],
            })

        payload = {
            "criteria_applied": criteria,
            "total_screened": total_candidates,
            "passed": len(passed_results),
            "returned": len(ranked),
            "results": ranked,
            "data_quality": {
                "note": (
                    "候选池为按总市值排序的前 500 只 A 股（pe_ttm>0 且 total_mv>0）。"
                    "格雷厄姆数 = √(22.5 × EPS × BVPS)。"
                    "debt_to_equity 从最近一期财报计算，缺失时不排除。"
                ),
            },
        }

        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("格雷厄姆式筛选失败: %s", exc, exc_info=True)
        return json.dumps(
            {"status": "error", "message": str(exc)},
            ensure_ascii=False, indent=2, default=str,
        )


# ────────────────────────────────────────────────────────────────
# Tool 8: 成长股筛选
# ────────────────────────────────────────────────────────────────


@tool
@register_tool(
    tool_id="get_growth_stock_screen",
    name="成长股筛选",
    description=(
        "按照成长投资标准筛选 A 股。"
        "条件：近 3 年营收增长率 > 20%、ROE > 15%、PE < 50。"
        "按 PEG 比率（PE / 增长率）评分排序。"
    ),
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="heavy",
    capability_tags=["screening", "growth", "investing", "fundamentals"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["成长股筛选", "高增长策略", "PEG 选股"],
    when_to_use=(
        "当用户想要寻找高成长性的股票、按照 PEG 标准选股、"
        "或需要筛选营收和 ROE 双双优秀的公司时使用。"
    ),
    when_not_to_use=(
        "不适合价值股、亏损企业、金融类企业筛选；"
        "数据不足时（财务数据少于 2 期）无法计算增长率。"
    ),
    returns=(
        "返回 JSON 字符串，包含 criteria_applied、total_screened、"
        "passed、results（按 PEG 升序排列）。"
    ),
    example="get_growth_stock_screen(limit=30)",
    related_tools=[
        "get_graham_screen",
        "get_dividend_stock_screen",
        "get_multi_factor_screening",
    ],
)
def get_growth_stock_screen(
    limit: Annotated[int, "返回前 N 只股票，默认 30"] = 30,
) -> str:
    """成长股筛选。

    Args:
        limit: 返回前 N 只股票，默认 30，自动夹钳到 [1, 100]

    Returns:
        str: JSON 字符串，包含以下可能结构——

        错误情形返回 dict，字段：
            status: "error"
            message: 错误描述

        成功情形返回 dict，字段：
            criteria_applied: 筛选条件 dict —
                revenue_growth_3y: dict — min: 20
                roe: dict — min: 15
                pe_ttm: dict — max: 50
            total_screened: 候选池总数
            passed: 通过筛选的股票数
            returned: 实际返回数量
            results: 按 PEG 升序排列的股票列表 [{"rank": 序号, "symbol": 代码, "name": 名称, "industry": 行业, "score": 综合得分, "revenue_growth_3y_pct": 3 年营收 CAGR 百分比, "roe": ROE, "pe_ttm": 市盈率, "peg": PEG 比率}, ...]
            data_quality: 数据质量 dict —
                note: 候选池与方法说明文本

        异常时返回 dict：{"status": "error", "message": ...}
    """
    try:
        limit = max(1, min(int(limit), 100))

        raw_candidates = _fetch_candidate_universe()
        total_candidates = len(raw_candidates)

        if total_candidates == 0:
            return json.dumps(
                {"status": "error", "message": "未获取到候选股票"},
                ensure_ascii=False, indent=2, default=str,
            )

        enriched = _enrich_with_financials(raw_candidates)

        criteria = {
            "revenue_growth_3y": {"min": 20},  # 20% CAGR
            "roe": {"min": 15},  # 15% ROE
            "pe_ttm": {"max": 50},
        }

        passed_results: List[Dict[str, Any]] = []
        for symbol, data in enriched.items():
            growth_3y = data.get("revenue_growth_3y")
            roe = data.get("roe")
            pe = data.get("pe_ttm")

            if growth_3y is None or roe is None or pe is None:
                continue
            if growth_3y <= 0.20:  # 20% CAGR
                continue
            if roe <= 15:
                continue
            if pe <= 0 or pe >= 50:
                continue

            # PEG = PE / (增长率 × 100)
            peg = pe / (growth_3y * 100) if growth_3y > 0 else 999

            # 得分：PEG 越低越好
            peg_score = max(0, 100 - peg * 20) if peg < 5 else max(0, 100 - peg * 10)
            roe_score = min(100, roe / 15 * 100)
            total_score = round((peg_score + roe_score) / 2, 1)

            passed_results.append({
                "symbol": symbol,
                "name": data.get("name", ""),
                "industry": data.get("industry", ""),
                "revenue_growth_3y_pct": round(growth_3y * 100, 2),
                "roe": round(roe, 2),
                "pe_ttm": pe,
                "peg": round(peg, 2),
                "score": total_score,
            })

        # 按 PEG 升序
        passed_results.sort(key=lambda x: x.get("peg") or 9999)
        top_results = passed_results[:limit]

        ranked = []
        for rank, item in enumerate(top_results, 1):
            ranked.append({
                "rank": rank,
                "symbol": item["symbol"],
                "name": item["name"],
                "industry": item["industry"],
                "score": item["score"],
                "revenue_growth_3y_pct": item["revenue_growth_3y_pct"],
                "roe": item["roe"],
                "pe_ttm": item["pe_ttm"],
                "peg": item["peg"],
            })

        payload = {
            "criteria_applied": criteria,
            "total_screened": total_candidates,
            "passed": len(passed_results),
            "returned": len(ranked),
            "results": ranked,
            "data_quality": {
                "note": (
                    "候选池为按总市值排序的前 500 只 A 股（pe_ttm>0 且 total_mv>0）。"
                    "revenue_growth_3y 为近 3 年营收 CAGR，从最近 3-4 期财务数据计算。"
                    "ROE 为最近一期报告期值。PEG = PE / (营收增长率×100)。"
                ),
            },
        }

        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("成长股筛选失败: %s", exc, exc_info=True)
        return json.dumps(
            {"status": "error", "message": str(exc)},
            ensure_ascii=False, indent=2, default=str,
        )


# ────────────────────────────────────────────────────────────────
# Tool 9: 红利股筛选
# ────────────────────────────────────────────────────────────────


@tool
@register_tool(
    tool_id="get_dividend_stock_screen",
    name="红利股筛选",
    description=(
        "按照红利投资标准筛选 A 股。"
        "条件：股息率 > 3%、连续分红 >= 3 年、分红率 20%-80%。"
        "综合股息率和财务健康度评分排序。"
    ),
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="heavy",
    capability_tags=["screening", "dividend", "income", "fundamentals"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["红利股筛选", "高股息策略", "分红选股"],
    when_to_use=(
        "当用户想要寻找高股息率的股票、构建红利投资组合、"
        "或筛选分红稳定且可持续的公司时使用。"
    ),
    when_not_to_use=(
        "不适合成长股、亏损企业筛选；"
        "股息率数据可能缺失（需 basic_info 中有 dividend_yield 字段）。"
    ),
    returns=(
        "返回 JSON 字符串，包含 criteria_applied、total_screened、"
        "passed、results（按综合得分排序）。"
    ),
    example="get_dividend_stock_screen(limit=30)",
    related_tools=[
        "get_graham_screen",
        "get_growth_stock_screen",
        "get_multi_factor_screening",
    ],
)
def get_dividend_stock_screen(
    limit: Annotated[int, "返回前 N 只股票，默认 30"] = 30,
) -> str:
    """红利股筛选。

    Args:
        limit: 返回前 N 只股票，默认 30，自动夹钳到 [1, 100]

    Returns:
        str: JSON 字符串，包含以下可能结构——

        错误情形返回 dict，字段：
            status: "error"
            message: 错误描述

        成功情形返回 dict，字段：
            criteria_applied: 筛选条件 dict —
                dividend_yield: dict — min: 3
                payout_ratio: dict — min: 0.2, max: 0.8
                consecutive_dividend_years: dict — min: 3
            total_screened: 候选池总数
            passed: 通过筛选的股票数
            returned: 实际返回数量
            results: 按股息率降序排列的股票列表 [{"rank": 序号, "symbol": 代码, "name": 名称, "industry": 行业, "score": 综合得分, "dividend_yield_pct": 股息率百分比, "pe_ttm": 市盈率, "payout_ratio": 分红率}, ...]
            data_quality: 数据质量 dict —
                note: 候选池与方法说明文本

        异常时返回 dict：{"status": "error", "message": ...}
    """
    try:
        limit = max(1, min(int(limit), 100))

        raw_candidates = _fetch_candidate_universe(extra_fields=["dividend_yield", "dividend_yield_ttm"])
        total_candidates = len(raw_candidates)

        if total_candidates == 0:
            return json.dumps(
                {"status": "error", "message": "未获取到候选股票"},
                ensure_ascii=False, indent=2, default=str,
            )

        enriched = _enrich_with_financials(raw_candidates)

        criteria = {
            "dividend_yield": {"min": 3},  # 3%
            "payout_ratio": {"min": 0.2, "max": 0.8},
            "consecutive_dividend_years": {"min": 3},
        }

        passed_results: List[Dict[str, Any]] = []
        for symbol, data in enriched.items():
            div_yield = data.get("dividend_yield")
            pe = data.get("pe_ttm")

            if div_yield is None:
                continue
            # dividend_yield 可能以小数形式（如 0.03 = 3%）或以百分比形式（如 3.0）
            # 尝试判断：如果值 < 1，视为小数，否则视为百分比
            if div_yield < 1:
                div_yield_pct = div_yield * 100
            else:
                div_yield_pct = div_yield

            if div_yield_pct < 3.0:
                continue

            # 分红率 = 股息率 × PE（简化估算）
            payout_ratio = None
            if pe is not None and pe > 0:
                payout_ratio = div_yield_pct * pe / 100

            if payout_ratio is not None and (payout_ratio < 0.2 or payout_ratio > 0.8):
                continue

            # 连续分红年数（简化：从财务数据判断 >= 3 期正利润）
            net_profit = data.get("net_profit")
            if net_profit is None or net_profit <= 0:
                continue

            # 得分
            div_score = min(100, div_yield_pct / 3 * 100)
            pe_score = max(0, 100 - (pe / 50 * 100)) if pe else 50
            total_score = round((div_score + pe_score) / 2, 1)

            passed_results.append({
                "symbol": symbol,
                "name": data.get("name", ""),
                "industry": data.get("industry", ""),
                "dividend_yield_pct": round(div_yield_pct, 2),
                "pe_ttm": pe,
                "payout_ratio": round(payout_ratio, 4) if payout_ratio is not None else None,
                "net_profit": round(net_profit, 2) if net_profit is not None else None,
                "score": total_score,
            })

        # 按股息率降序
        passed_results.sort(key=lambda x: x.get("dividend_yield_pct") or 0, reverse=True)
        top_results = passed_results[:limit]

        ranked = []
        for rank, item in enumerate(top_results, 1):
            ranked.append({
                "rank": rank,
                "symbol": item["symbol"],
                "name": item["name"],
                "industry": item["industry"],
                "score": item["score"],
                "dividend_yield_pct": item["dividend_yield_pct"],
                "pe_ttm": item["pe_ttm"],
                "payout_ratio": item["payout_ratio"],
            })

        payload = {
            "criteria_applied": criteria,
            "total_screened": total_candidates,
            "passed": len(passed_results),
            "returned": len(ranked),
            "results": ranked,
            "data_quality": {
                "note": (
                    "候选池为按总市值排序的前 500 只 A 股。"
                    "股息率来自 stock_basic_info 的 dividend_yield 字段。"
                    "分红率 = 股息率 × PE，为简化估算值。"
                    "连续分红年数基于净利润是否连续多期为正判断。"
                ),
            },
        }

        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("红利股筛选失败: %s", exc, exc_info=True)
        return json.dumps(
            {"status": "error", "message": str(exc)},
            ensure_ascii=False, indent=2, default=str,
        )


# ────────────────────────────────────────────────────────────────
# Tool 10: 困境反转筛选
# ────────────────────────────────────────────────────────────────


@tool
@register_tool(
    tool_id="get_turnaround_screen",
    name="困境反转筛选",
    description=(
        "筛选可能处于困境反转阶段的股票。"
        "条件：PE < 20、营收增长率从负转正改善、经营现金流为正。"
        "寻找近期亏损但改善趋势明显的公司。"
    ),
    category="fundamentals",
    is_online=False,
    auto_register=True,
    timeout_tier="heavy",
    capability_tags=["screening", "turnaround", "turnaround_investing", "fundamentals"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["困境反转策略", "逆境反转选股", "拐点型投资"],
    when_to_use=(
        "当用户想要寻找处于困境但正在改善的股票、"
        "挖掘业绩拐点型投资机会、或筛选低估值的反转候选股时使用。"
    ),
    when_not_to_use=(
        "不适合稳定增长型企业筛选；"
        "需要多期财务数据判断趋势，数据不足时将给出不完整结果。"
    ),
    returns=(
        "返回 JSON 字符串，包含 criteria_applied、total_screened、"
        "passed、results（按改善幅度排序）。"
    ),
    example="get_turnaround_screen(limit=30)",
    related_tools=[
        "get_graham_screen",
        "get_growth_stock_screen",
        "get_multi_factor_screening",
    ],
)
def get_turnaround_screen(
    limit: Annotated[int, "返回前 N 只股票，默认 30"] = 30,
) -> str:
    """困境反转筛选。

    Args:
        limit: 返回前 N 只股票，默认 30，自动夹钳到 [1, 100]

    Returns:
        str: JSON 字符串，包含以下可能结构——

        错误情形返回 dict，字段：
            status: "error"
            message: 错误描述

        成功情形返回 dict，字段：
            criteria_applied: 筛选条件 dict —
                pe_ttm: dict — max: 20
                revenue_growth_improving: 改善判断说明文本
                n_cashflow_act: dict — min: 0
            total_screened: 候选池总数
            passed: 通过筛选的股票数
            returned: 实际返回数量
            results: 按改善分数降序排列的股票列表 [{"rank": 序号, "symbol": 代码, "name": 名称, "industry": 行业, "pe_ttm": 市盈率, "revenue_growth_pct": 营收增长率百分比, "operating_cashflow": 经营现金流, "net_profit": 净利润, "roe": ROE, "improvement_score": 改善评分}, ...]
            data_quality: 数据质量 dict —
                note: 候选池与方法说明文本

        异常时返回 dict：{"status": "error", "message": ...}
    """
    try:
        limit = max(1, min(int(limit), 100))

        raw_candidates = _fetch_candidate_universe()
        total_candidates = len(raw_candidates)

        if total_candidates == 0:
            return json.dumps(
                {"status": "error", "message": "未获取到候选股票"},
                ensure_ascii=False, indent=2, default=str,
            )

        enriched = _enrich_with_financials(raw_candidates)

        criteria = {
            "pe_ttm": {"max": 20},
            "revenue_growth_improving": "近两期营收增长率改善（负→正或收窄）",
            "n_cashflow_act": {"min": 0},  # 经营现金流为正
        }

        passed_results: List[Dict[str, Any]] = []
        for symbol, data in enriched.items():
            pe = data.get("pe_ttm")
            revenue_growth = data.get("revenue_growth")
            n_cashflow_act = data.get("n_cashflow_act")
            net_profit = data.get("net_profit")
            roe = data.get("roe")

            if pe is None or pe <= 0 or pe >= 20:
                continue

            if n_cashflow_act is None or n_cashflow_act <= 0:
                continue

            # 判断改善趋势：营收增长从负转正或亏损收窄
            improving = False
            improvement_score = 0

            if revenue_growth is not None:
                # 营收增速改善：负值但正在提升
                if revenue_growth > -0.1:  # 亏损收窄到 -10% 以内
                    improving = True
                    improvement_score += 50
                if revenue_growth > 0:  # 已转正
                    improving = True
                    improvement_score += 100

            # 有正的经营现金流说明造血能力在恢复
            if n_cashflow_act > 0:
                improvement_score += 30

            # 如果最近一期仍有净亏损但经营现金流转正，分数更高
            if net_profit is not None and net_profit < 0 and n_cashflow_act > 0:
                improvement_score += 40  # 现金流转正是更强信号

            if not improving and (net_profit is None or net_profit < 0):
                # 至少要有一种改善信号
                if net_profit is None:
                    continue

            total_score = min(100, improvement_score)

            passed_results.append({
                "symbol": symbol,
                "name": data.get("name", ""),
                "industry": data.get("industry", ""),
                "pe_ttm": pe,
                "revenue_growth_pct": round(revenue_growth * 100, 2) if revenue_growth is not None else None,
                "operating_cashflow": round(n_cashflow_act, 2) if n_cashflow_act is not None else None,
                "net_profit": round(net_profit, 2) if net_profit is not None else None,
                "roe": round(roe, 2) if roe is not None else None,
                "improvement_score": total_score,
            })

        # 按改善分数降序
        passed_results.sort(key=lambda x: x.get("improvement_score") or 0, reverse=True)
        top_results = passed_results[:limit]

        ranked = []
        for rank, item in enumerate(top_results, 1):
            ranked.append({
                "rank": rank,
                "symbol": item["symbol"],
                "name": item["name"],
                "industry": item["industry"],
                "pe_ttm": item["pe_ttm"],
                "revenue_growth_pct": item["revenue_growth_pct"],
                "operating_cashflow": item["operating_cashflow"],
                "net_profit": item["net_profit"],
                "roe": item["roe"],
                "improvement_score": item["improvement_score"],
            })

        payload = {
            "criteria_applied": criteria,
            "total_screened": total_candidates,
            "passed": len(passed_results),
            "returned": len(ranked),
            "results": ranked,
            "data_quality": {
                "note": (
                    "候选池为按总市值排序的前 500 只 A 股（pe_ttm>0 且 total_mv>0）。"
                    "改善判断基于最新两期财务数据的营收同比增长。"
                    "经营现金流为正说明公司造血能力恢复。"
                ),
            },
        }

        return json.dumps(payload, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.error("困境反转筛选失败: %s", exc, exc_info=True)
        return json.dumps(
            {"status": "error", "message": str(exc)},
            ensure_ascii=False, indent=2, default=str,
        )


__all__ = [
    "get_graham_screen",
    "get_growth_stock_screen",
    "get_dividend_stock_screen",
    "get_turnaround_screen",
]