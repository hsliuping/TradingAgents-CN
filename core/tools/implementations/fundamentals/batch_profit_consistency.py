"""
批量盈利稳定性验证工具

一次 $in 查询 stock_financial_periods，计算近 N 年 ROE / 净利润的稳定性，
避免对每只股票单独发出 N 次查询，大幅提升效率。
"""

import json
import logging
import math
from typing import Annotated, List, Dict, Any

from langchain_core.tools import tool
from core.tools.base import register_tool

logger = logging.getLogger(__name__)

MAX_DETAIL_PER_GROUP = 5


@tool
@register_tool(
    tool_id="batch_check_profit_consistency",
    name="批量验证盈利稳定性",
    description=(
        "批量验证多只股票近N年ROE/净利润的稳定性，一次查询返回所有股票的盈利稳定性评估。"
        "输入股票代码列表（JSON数组）和检验年数，返回每只股票的稳定性结论（稳定/不稳定）、"
        "变异系数（CV=标准差/均值）和近N年ROE数据。"
        "用于在批量筛选后对候选股票做盈利质量二次验证，效率远高于逐股查询。"
    ),
    category="screening",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["profit_consistency", "batch_screening", "roe", "profitability", "stability", "screening", "earnings_quality"],
    tool_role_hint="specialized",
    output_shape="markdown",
    preferred_for=["batch_profitability_screening", "earnings_stability_verification", "roe_consistency_check"],
    data_source_handling="local_only",
)
async def batch_check_profit_consistency(
    stock_codes_json: Annotated[
        str,
        '股票代码 JSON 数组，如 ["000001", "600519", "000858"]',
    ],
    years: Annotated[int, "检验年数，默认3年（只取年报数据）"] = 3,
    threshold_cv: Annotated[
        float,
        "变异系数阈值，超过则判定为不稳定，默认0.3（即波动 > 均值的30%）",
    ] = 0.3,
) -> str:
    """批量验证多只股票近N年盈利稳定性（一次 $in 查询，高效）"""
    try:
        codes = json.loads(stock_codes_json)
        if not isinstance(codes, list) or len(codes) == 0:
            return "错误：stock_codes_json 必须是非空的 JSON 数组。"
        if len(codes) > 200:
            return "错误：单次最多验证 200 只股票，请分批提交。"
        years = max(2, min(years, 10))
    except json.JSONDecodeError as e:
        return f"错误：stock_codes_json 格式不正确：{e}"

    return await _async_check(codes, years, threshold_cv)


def _build_annual_roe_pipeline(codes: List[str]) -> List[Dict[str, Any]]:
    return [
        {
            "$addFields": {
                "normalized_code": {"$ifNull": ["$code", "$symbol"]},
                "effective_roe": {
                    "$ifNull": [
                        "$financial_indicators.roe",
                        "$roe",
                    ]
                },
                "has_roe": {
                    "$cond": [
                        {
                            "$ne": [
                                {
                                    "$ifNull": [
                                        "$financial_indicators.roe",
                                        "$roe",
                                    ]
                                },
                                None,
                            ]
                        },
                        1,
                        0,
                    ]
                },
            }
        },
        {
            "$match": {
                "normalized_code": {"$in": codes},
                "report_type": "annual",
            }
        },
        {
            "$sort": {
                "normalized_code": 1,
                "report_period": -1,
                "has_roe": -1,
                "ann_date": -1,
                "updated_at": -1,
            }
        },
        {
            "$group": {
                "_id": {
                    "code": "$normalized_code",
                    "report_period": "$report_period",
                },
                "roe": {"$first": "$effective_roe"},
                "period": {"$first": "$report_period"},
            }
        },
        {"$match": {"roe": {"$ne": None}}},
        {"$sort": {"_id.code": 1, "period": -1}},
        {
            "$group": {
                "_id": "$_id.code",
                "roe_list": {"$push": "$roe"},
                "periods": {"$push": "$period"},
            }
        },
    ]


async def _async_check(
    codes: List[str],
    years: int,
    threshold_cv: float,
) -> str:
    from app.core.database import init_database, get_mongo_db

    try:
        await init_database()
    except Exception:
        pass

    db = get_mongo_db()
    collection = db["stock_financial_periods"]
    pipeline = _build_annual_roe_pipeline(codes)

    results_map: Dict[str, Any] = {}
    async for doc in collection.aggregate(pipeline):
        code = doc["_id"]
        all_roe = [v for v in doc.get("roe_list", []) if v is not None]
        all_periods = doc.get("periods", [])

        roe_values = all_roe[:years]
        periods_used = all_periods[:years]

        results_map[code] = {
            "roe_values": roe_values,
            "periods": periods_used,
        }

    return _format_results(codes, results_map, years, threshold_cv)


def _cv(values: List[float]) -> float:
    """变异系数 = 标准差 / 均值的绝对值（防止均值接近 0 导致除零）"""
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    if abs(mean) < 1e-9:
        return 999.0  # 均值接近 0，视为极不稳定
    variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    std = math.sqrt(variance)
    return std / abs(mean)


def _build_detail_line(
    code: str,
    roe_values: List[float],
    periods: List[str],
    cv_val: float,
    threshold_cv: float,
    all_positive: bool,
    is_stable: bool,
) -> str:
    actual_years = len(roe_values)
    roe_str = " / ".join(f"{v:.1f}%" for v in roe_values)
    periods_str = " / ".join(p[:4] for p in periods)

    if is_stable:
        return (
            f"  ✅ {code}：稳定 | CV={cv_val:.2f} | ROE连续为正=是"
            f" | 近{actual_years}年ROE({periods_str}): {roe_str}"
        )

    reasons = []
    if cv_val > threshold_cv:
        reasons.append(f"CV={cv_val:.2f}>{threshold_cv:.0%}")
    if not all_positive:
        reasons.append("ROE含负值")
    reason_text = " / ".join(reasons) if reasons else "波动偏大"
    return (
        f"  ❌ {code}：不稳定 | {reason_text}"
        f" | 近{actual_years}年ROE({periods_str}): {roe_str}"
    )


def _append_group_preview(lines: List[str], title: str, entries: List[str], total_count: int) -> None:
    if not entries:
        return
    lines.append(title)
    lines.extend(entries[:MAX_DETAIL_PER_GROUP])
    if total_count > len(entries[:MAX_DETAIL_PER_GROUP]):
        lines.append(f"  ... 其余 {total_count - len(entries[:MAX_DETAIL_PER_GROUP])} 只已省略详细展开")
    lines.append("")


def _format_results(
    codes: List[str],
    results_map: Dict[str, Any],
    years: int,
    threshold_cv: float,
) -> str:
    lines = [
        f"共验证 {len(codes)} 只股票近 {years} 年盈利稳定性（变异系数阈值 ≤ {threshold_cv:.0%}）。",
        "结果已压缩为汇总摘要；如需继续筛选，请优先使用下方代码列表。",
        "",
    ]

    stable_codes, volatile_codes, no_data_codes = [], [], []
    stable_details: List[str] = []
    volatile_details: List[str] = []

    for code in codes:
        data = results_map.get(code)
        if not data or len(data.get("roe_values", [])) < years:
            no_data_codes.append(code)
            continue

        roe_values = data["roe_values"]
        periods = data["periods"]
        cv_val = _cv(roe_values)
        all_positive = all(v > 0 for v in roe_values)

        # 判断稳定性：CV 需 ≤ 阈值 且 ROE 连续为正
        is_stable = (cv_val <= threshold_cv) and all_positive

        if is_stable:
            stable_codes.append(code)
            stable_details.append(
                _build_detail_line(
                    code, roe_values, periods, cv_val, threshold_cv, all_positive, is_stable=True
                )
            )
        else:
            volatile_codes.append(code)
            volatile_details.append(
                _build_detail_line(
                    code, roe_values, periods, cv_val, threshold_cv, all_positive, is_stable=False
                )
            )

    lines.append(f"📊 汇总：稳定 {len(stable_codes)} 只 | 不稳定 {len(volatile_codes)} 只 | 无数据 {len(no_data_codes)} 只")
    lines.append("")

    _append_group_preview(lines, "稳定样例：", stable_details, len(stable_codes))
    _append_group_preview(lines, "不稳定样例：", volatile_details, len(volatile_codes))

    if stable_codes:
        lines.append(f"✅ 稳定股票代码：{', '.join(stable_codes)}")
    if volatile_codes:
        lines.append(f"❌ 不稳定股票代码：{', '.join(volatile_codes)}")
    if no_data_codes:
        lines.append(f"⚪ 无数据股票代码：{', '.join(no_data_codes)}")

    return "\n".join(lines)

