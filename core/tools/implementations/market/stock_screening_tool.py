"""
全市场股票批量筛选工具

封装 EnhancedScreeningService / DatabaseScreeningService，
让 LLM 可以通过 function calling 按条件批量筛选 A 股。
"""

import asyncio
import concurrent.futures
import json
import logging
from typing import Annotated

from langchain_core.tools import tool

from core.tools.base import register_tool

logger = logging.getLogger(__name__)

# 支持的字段说明（供 LLM 参考）
SUPPORTED_FIELDS_DOC = """
支持的筛选字段：
- pe         市盈率（TTM）
- pb         市净率
- pe_ttm     滚动市盈率（同 pe）
- pb_mrq     最新市净率
- roe        净资产收益率（%）
- total_mv   总市值（亿元）
- circ_mv    流通市值（亿元）
- turnover_rate 换手率（%）
- volume_ratio  量比
- pct_chg    当日涨跌幅（%）
- amount     成交额（万元）
- close      收盘价（元）
- industry   行业名称（使用 == 或 in 操作符）
- keyword    股票代码或名称模糊搜索（使用 contains 操作符）
- debt_to_assets   资产负债率（%，注意银行等金融股通常 >90% 属正常）
- current_ratio    流动比率（流动资产/流动负债，>1 表示流动性良好）
- dividend_yield   股息率（%，近12个月分红/当前股价）
- net_working_capital  净营运资本（亿元，= 流动资产 - 流动负债，> 0 为正）
- is_st      是否为ST/＊ST股票（True/False，使用 == 操作符）

支持的操作符：> < >= <= == != between in not_in contains
- between 的 value 为 [最小值, 最大值]
- in / not_in 的 value 为列表
"""


@tool
@register_tool(
    tool_id="screen_stocks_by_criteria",
    name="全市场股票批量筛选",
    description=(
        "按多个财务和行情指标批量筛选 A 股股票。"
        "支持 PE、PB、ROE、市值、资产负债率、流动比率、股息率、净营运资本、ST状态、行业等多条件组合筛选。"
        "条件以 JSON 数组形式传入，每个条件包含 field（字段名）、operator（操作符）、value（值）三个字段。"
        "支持的字段：pe/pb/roe/total_mv/circ_mv/debt_to_assets/current_ratio/dividend_yield/"
        "net_working_capital/is_st/turnover_rate/pct_chg/amount/close/industry/keyword 等。"
        "支持的操作符：> < >= <= == != between in not_in contains。"
        "返回符合条件的股票列表，包含代码、名称、行业、PE、PB、ROE、资产负债率、股息率等信息。"
    ),
    category="screening",
    is_online=False,
    auto_register=True
)
def screen_stocks_by_criteria(
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
    """全市场 A 股批量筛选工具，支持 PE/PB/ROE/市值/行业等多条件组合筛选"""
    try:
        # 解析条件
        try:
            raw_conditions = json.loads(conditions_json)
        except json.JSONDecodeError as e:
            return f"错误：conditions_json 格式不正确，请传入合法的 JSON 数组。详情：{e}"

        if not isinstance(raw_conditions, list) or len(raw_conditions) == 0:
            return "错误：conditions_json 必须是非空的 JSON 数组。"

        limit = max(1, min(limit, 100))

        # 运行异步筛选
        # 使用独立线程运行，避免与外层 asyncio 事件循环冲突
        def _run_in_thread():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(
                    _run_screening(raw_conditions, limit, order_by_field, order_direction)
                )
            finally:
                loop.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_run_in_thread)
            result = future.result(timeout=60)
        return result

    except Exception as e:
        logger.error(f"screen_stocks_by_criteria 执行失败: {e}", exc_info=True)
        return f"筛选执行失败：{e}"


async def _run_screening(
    raw_conditions: list,
    limit: int,
    order_by_field: str,
    order_direction: str,
) -> str:
    """异步调用 DatabaseScreeningService 执行筛选"""
    from app.core.database import init_database, get_mongo_db
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

    if total == 0 or not items:
        return "未找到符合条件的股票。请尝试放宽筛选条件。"

    # 格式化输出
    lines = [f"共找到 {total} 只符合条件的股票，以下展示前 {len(items)} 只：\n"]
    for i, item in enumerate(items, 1):
        code = item.get("code") or item.get("symbol", "")
        name = item.get("name", "")
        industry = item.get("industry", "-")
        pe = item.get("pe") or item.get("pe_ttm", "-")
        pb = item.get("pb") or item.get("pb_mrq", "-")
        roe = item.get("roe", "-")
        total_mv = item.get("total_mv", "-")
        close = item.get("close", "-")
        pct_chg = item.get("pct_chg", "-")
        debt_to_assets = item.get("debt_to_assets")
        current_ratio = item.get("current_ratio")
        dividend_yield = item.get("dividend_yield")
        net_working_capital = item.get("net_working_capital")
        is_st = item.get("is_st")

        pe_str = f"{pe:.2f}" if isinstance(pe, (int, float)) else str(pe)
        pb_str = f"{pb:.2f}" if isinstance(pb, (int, float)) else str(pb)
        roe_str = f"{roe:.2f}%" if isinstance(roe, (int, float)) else str(roe)
        mv_str = f"{total_mv:.2f}亿" if isinstance(total_mv, (int, float)) else str(total_mv)
        price_str = f"{close:.2f}元" if isinstance(close, (int, float)) else str(close)
        chg_str = f"{pct_chg:+.2f}%" if isinstance(pct_chg, (int, float)) else str(pct_chg)

        # 可选扩展指标
        extra_parts = []
        if debt_to_assets is not None:
            extra_parts.append(f"负债率={debt_to_assets:.1f}%")
        if current_ratio is not None:
            extra_parts.append(f"流动比率={current_ratio:.2f}")
        if dividend_yield is not None:
            extra_parts.append(f"股息率={dividend_yield:.2f}%")
        if net_working_capital is not None:
            extra_parts.append(f"净营运资本={net_working_capital:.2f}亿")
        if is_st is True:
            extra_parts.append("⚠️ ST")
        extra_str = (" | " + " ".join(extra_parts)) if extra_parts else ""

        lines.append(
            f"{i}. {code} {name}（{industry}）"
            f" | PE={pe_str} PB={pb_str} ROE={roe_str}"
            f" | 市值={mv_str} 股价={price_str} 涨跌={chg_str}"
            f"{extra_str}"
        )

    return "\n".join(lines)

