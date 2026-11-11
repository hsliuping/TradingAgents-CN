"""融资融券工具 — 数据能力门面（DataFacade）驱动

本工具是 P4 能力注册机制的示范调用点：工具零感知数据源，
查询经 tradingagents.dataflows.capability 门面调度（优先级 + 降级 + 字段标准化），
数据源新增/切换不需要修改本工具。

设计文档：docs/05-design/v4.0/data-architecture-problems-and-optimization.md 5.4
"""

import asyncio
import json
import logging
from typing import Annotated, Optional

import pandas as pd
from langchain_core.tools import tool

from core.tools.base import register_tool

logger = logging.getLogger(__name__)


def _run_async(coro):
    """同步工具内执行异步门面查询（已有运行中事件循环时放到独立线程执行）"""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


@tool
@register_tool(
    tool_id="get_margin_balance",
    name="融资融券余额",
    description=(
        "查询融资融券交易汇总（两融余额），覆盖全市场合计或沪深交易所分项。"
        "数据经统一数据能力门面调度，自动按数据源优先级获取并在请求失败时降级，"
        "输出为标准字段（金额单位为元）。"
    ),
    category="fundamentals",
    is_online=True,
    auto_register=True,
    timeout_tier="light",
    capability_tags=["margin", "securities_lending", "market_sentiment", "macro"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["查询融资融券余额", "两融余额变化", "融资买入额", "市场杠杆情绪"],
    when_to_use=(
        "当用户询问融资融券余额、两融余额走势、融资买入额、融券余额、"
        "市场杠杆资金水平或两融情绪分析时使用。"
    ),
    when_not_to_use=(
        "不适合查询单只股票的融资融券明细（个股粒度）；"
        "不适合查询沪深港通北向资金流向。"
    ),
    returns=(
        "返回 JSON 字符串，包含 status、data_source（实际数据来源）、"
        "data_note（口径说明）、quality（字段完整性）、rows（标准化行：trade_date、"
        "exchange_id（SSE/SZSE/TOTAL）、margin_balance 融资余额（元）、"
        "margin_buy_amount 融资买入额（元）、margin_repay_amount 融资偿还额（元）、"
        "short_balance 融券余额（元）、short_sell_volume 融券卖出量（股）、"
        "total_balance 两融余额（元）、source、quality）。"
    ),
    example="get_margin_balance(trade_date='20261023')",
)
def get_margin_balance(
    trade_date: Annotated[Optional[str], "交易日期 YYYYMMDD，精确查询某日"] = None,
    start_date: Annotated[Optional[str], "开始日期 YYYYMMDD"] = None,
    end_date: Annotated[Optional[str], "结束日期 YYYYMMDD"] = None,
    exchange_id: Annotated[Optional[str], "交易所代码：SSE上交所/SZSE深交所；缺省为全市场合计"] = None,
) -> str:
    """查询融资融券交易汇总（两融余额），返回标准化 JSON。

    Args:
        trade_date: 交易日期 YYYYMMDD
        start_date: 开始日期 YYYYMMDD
        end_date: 结束日期 YYYYMMDD
        exchange_id: SSE/SZSE（缺省返回全市场合计行）

    Returns:
        str: JSON 字符串，见 returns 字段说明
    """
    try:
        from tradingagents.dataflows.capability import get_data_facade

        params = {}
        if trade_date:
            params["trade_date"] = str(trade_date).replace("-", "")
        if start_date:
            params["start_date"] = str(start_date).replace("-", "")
        if end_date:
            params["end_date"] = str(end_date).replace("-", "")
        if exchange_id:
            params["exchange_id"] = str(exchange_id).upper()

        df = _run_async(get_data_facade().get_capability("margin").query(**params))

        if df.empty:
            return json.dumps({
                "status": "ok",
                "note": "查询条件下无融资融券数据（可能为非交易日或数据尚未发布）",
                "rows": [],
            }, ensure_ascii=False)

        rows = []
        for record in df.to_dict("records"):
            row = {}
            for key, value in record.items():
                if value is None or (not isinstance(value, (list, dict)) and pd.isna(value)):
                    row[key] = None
                elif hasattr(value, "item"):
                    row[key] = value.item()
                else:
                    row[key] = value
            rows.append(row)

        return json.dumps({
            "status": "ok",
            "data_source": str(df["source"].iloc[0]),
            "data_note": (
                "金额单位为元；不同源返回粒度可能为交易所分项行（SSE/SZSE）"
                "或全市场合计行（TOTAL），按日取全市场水平应汇总当日全部行"
            ),
            "quality": sorted({str(q) for q in df["quality"] if not pd.isna(q)}),
            "rows": rows,
        }, ensure_ascii=False)
    except ValueError as e:
        return json.dumps({"status": "error", "error": f"参数错误: {e}"}, ensure_ascii=False)
    except Exception as e:
        logger.error(f"获取融资融券数据失败: {e}")
        return json.dumps({"status": "error", "error": str(e)}, ensure_ascii=False)
