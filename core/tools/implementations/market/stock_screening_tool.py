"""
全市场股票批量筛选工具

封装 EnhancedScreeningService / DatabaseScreeningService，
让 LLM 可以通过 function calling 按条件批量筛选 A 股。
"""

import json
import logging
from typing import Annotated

from langchain_core.tools import tool

from app.services.screening_metric_display import resolve_metric_value, select_metric_display_spec
from app.services.factor_registry_service import build_screening_fields_markdown, build_screening_tool_description
from core.tools.base import register_tool

logger = logging.getLogger(__name__)

MAX_DETAILED_RESULTS = 8

SUPPORTED_FIELDS_DOC = """
支持的筛选字段：
{fields_markdown}

支持的操作符：> < >= <= == != between in not_in contains
- between 的 value 为 [最小值, 最大值]
- in / not_in 的 value 为列表
""".format(fields_markdown=build_screening_fields_markdown(public_only=True))


def _format_metric(value, *, suffix: str = "", decimals: int = 2, scale: float = 1.0) -> str:
    if not isinstance(value, (int, float)):
        return "-"
    scaled = value / scale
    return f"{scaled:.{decimals}f}{suffix}"


def _build_compact_candidate_line(
    index: int,
    item: dict,
    pe_display_field: str,
    pe_display_label: str,
    pb_display_field: str,
    pb_display_label: str,
) -> str:
    code = item.get("code") or item.get("symbol", "")
    name = item.get("name", "")
    industry = item.get("industry", "-")
    pe_value = resolve_metric_value(item, pe_display_field, "pe")
    pb_value = resolve_metric_value(item, pb_display_field, "pb")

    parts = [
        f"股息率={_format_metric(item.get('dividend_yield'), suffix='%')}",
        f"{pe_display_label}={_format_metric(pe_value)}",
        f"{pb_display_label}={_format_metric(pb_value)}",
        f"ROE={_format_metric(item.get('roe'), suffix='%')}",
        f"负债率={_format_metric(item.get('debt_to_assets'), suffix='%', decimals=1)}",
        f"经营现金流={_format_metric(item.get('n_cashflow_act'), suffix='亿', decimals=2, scale=1e8)}",
        f"市值={_format_metric(item.get('total_mv'), suffix='亿')}",
    ]

    price = item.get("close")
    if isinstance(price, (int, float)):
        parts.append(f"股价={price:.2f}元")

    pct_chg = item.get("pct_chg")
    if isinstance(pct_chg, (int, float)):
        parts.append(f"涨跌={pct_chg:+.2f}%")

    report_period = item.get("report_period")
    if report_period:
        parts.append(f"财报期={report_period}")

    if item.get("is_st") is True:
        parts.append("ST")

    compact_parts = [part for part in parts if not part.endswith("=-")]
    return f"{index}. {code} {name}（{industry}） | " + " | ".join(compact_parts)


@tool
@register_tool(
    tool_id="screen_stocks_by_criteria",
    name="全市场股票批量筛选",
    description=build_screening_tool_description(),
    category="screening",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["screening", "fundamentals", "technical"],
    tool_role_hint="specialized",
    when_to_use="当需要按多个财务、交易和技术指标组合条件批量筛选 A 股股票时使用。支持 50+ 字段和 > < >= <= == != between in not_in contains 等操作符。适合复杂自定义筛选条件。",
    when_not_to_use="不适合单只股票深度分析；不适合简单单条件筛选（可考虑专门的筛选工具如 get_graham_screen 等预置策略）。",
    related_tools=["get_multi_factor_screening", "get_graham_screen", "get_growth_stock_screen", "get_dividend_stock_screen", "get_turnaround_screen"],
)
async def screen_stocks_by_criteria(
    conditions_json: Annotated[
        str,
        (
            '筛选条件 JSON 数组，格式: [{"field": "pe", "operator": "<", "value": 15}, '
            '{"field": "total_mv", "operator": ">", "value": 50}]。'
            "field 为字段名，operator 为操作符，value 为比较值。"
            "between 操作符的 value 格式为 [最小值, 最大值]，in/not_in 为列表。"
        )
    ],
    limit: Annotated[int, "返回数量，默认 20，最大 100"] = 20,
    order_by_field: Annotated[str, "排序字段，如 pe/pb/roe/total_mv，默认按总市值降序"] = "total_mv",
    order_direction: Annotated[str, "排序方向：asc（升序）或 desc（降序），默认 desc"] = "desc",
) -> str:
    """全市场 A 股批量筛选工具。

    {supported_fields_doc}
    """
    try:
        # 解析条件
        try:
            raw_conditions = json.loads(conditions_json)
        except json.JSONDecodeError as e:
            return f"错误：conditions_json 格式不正确，请传入合法的 JSON 数组。详情：{e}"

        if not isinstance(raw_conditions, list) or len(raw_conditions) == 0:
            return "错误：conditions_json 必须是非空的 JSON 数组。"

        limit = max(1, min(limit, 100))

        return await _run_screening(raw_conditions, limit, order_by_field, order_direction)

    except Exception as e:
        logger.error(f"screen_stocks_by_criteria 执行失败: {e}", exc_info=True)
        return f"筛选执行失败：{e}"


async def _execute_screening_query(
    raw_conditions: list,
    limit: int,
    order_by_field: str,
    order_direction: str,
) -> tuple[list, int]:
    """异步调用 DatabaseScreeningService 执行筛选并返回结构化结果。"""
    from app.core.database import init_database
    from app.services.database_screening_service import get_database_screening_service

    # 确保数据库已初始化
    try:
        await init_database()
    except Exception:
        pass  # 可能已经初始化

    service = get_database_screening_service()

    order_by = [{"field": order_by_field, "direction": order_direction}]

    items, total = await service.screen_stocks(
        conditions=raw_conditions,
        limit=limit,
        offset=0,
        order_by=order_by,
    )

    return items, total


def _format_screening_output(
    raw_conditions: list,
    items: list,
    total: int,
    order_by_field: str,
) -> str:
    """将结构化筛选结果格式化为工具文本输出。"""

    if total == 0 or not items:
        return "未找到符合条件的股票。当前没有适合该筛选要求的标的，不要推荐其它不符合条件的股票。"

    display_count = min(len(items), MAX_DETAILED_RESULTS)
    pe_display_field, pe_display_label = select_metric_display_spec(raw_conditions, order_by_field, "pe")
    pb_display_field, pb_display_label = select_metric_display_spec(raw_conditions, order_by_field, "pb")
    lines = [
        f"共找到 {total} 只符合条件的股票，以下展示前 {display_count} 只核心候选：",
        "结果已压缩为摘要，避免占用过多上下文；如需继续验证，请优先使用下方代码列表调用后续工具。\n",
    ]

    for i, item in enumerate(items[:display_count], 1):
        lines.append(
            _build_compact_candidate_line(
                i,
                item,
                pe_display_field,
                pe_display_label,
                pb_display_field,
                pb_display_label,
            )
        )

    all_codes = [
        str(item.get("code") or item.get("symbol", "")).strip()
        for item in items
        if str(item.get("code") or item.get("symbol", "")).strip()
    ]
    if all_codes:
        lines.append("")
        lines.append(f"候选代码列表（按当前排序，共 {len(all_codes)} 只）: {', '.join(all_codes)}")

    if len(items) > display_count:
        lines.append(f"其余 {len(items) - display_count} 只候选已省略详细展开。")

    return "\n".join(lines)


async def _run_screening(
    raw_conditions: list,
    limit: int,
    order_by_field: str,
    order_direction: str,
) -> str:
    items, total = await _execute_screening_query(raw_conditions, limit, order_by_field, order_direction)
    return _format_screening_output(raw_conditions, items, total, order_by_field)

