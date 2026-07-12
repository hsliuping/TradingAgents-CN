"""单股数据同步工具。"""

import logging
from typing import Annotated

from langchain_core.tools import tool

from core.tools.base import register_tool
from core.tools.context import require_current_user_id

logger = logging.getLogger(__name__)


def _normalize_cn_symbol(symbol: str) -> str:
    text = str(symbol or "").strip().upper()
    if "." in text:
        text = text.split(".", 1)[0]
    return text


def _format_sync_section(title: str, payload: dict | None) -> str:
    if payload is None:
        return f"- {title}: 未执行"

    if payload.get("success"):
        details = []
        if payload.get("records") is not None:
            details.append(f"记录数 {payload['records']}")
        if payload.get("data_source_used"):
            details.append(f"数据源 {payload['data_source_used']}")
        suffix = f"（{'，'.join(details)}）" if details else ""
        return f"- {title}: 成功{suffix}"

    error = payload.get("error") or payload.get("message") or "未知错误"
    return f"- {title}: 失败（{error}）"


@tool
@register_tool(
    tool_id="sync_single_stock_data",
    name="同步单股数据",
    description="同步单只股票的数据到本地数据库，支持历史行情和财务数据，也可选补充基础数据。适合用户明确要求‘同步某只股票数据’‘更新某股历史/财务数据’的场景。",
    category="assistant_ops",
    is_online=True,
    auto_register=True,
    timeout_tier="heavy",
    data_source_handling="self_contained",
    capability_tags=["data_sync", "stock_data", "sync", "assistant_ops", "historical_data", "financial_data", "data_pipeline", "local_database", "stock_sync", "data_ingestion"],
    tool_role_hint="specialized",
    output_shape="text",
    preferred_for=["同步单只股票数据", "更新股票历史行情", "更新股票财务数据", "补充股票基础数据"],
    when_to_use="当用户明确要求同步某只股票的历史行情、财务数据，或更新某只股票的本地数据时使用。",
    returns="返回文本格式的同步结果，包含历史数据、财务数据、基础数据的同步状态和记录数。",
)
async def sync_single_stock_data(
    symbol: Annotated[str, "股票代码，支持 6 位数字或带交易所后缀，如 000001、600519.SH"],
    data_source: Annotated[str, "数据源，支持 tushare 或 akshare，默认 tushare"] = "tushare",
    days: Annotated[int, "历史数据同步天数，默认 365"] = 365,
    sync_historical: Annotated[bool, "是否同步历史行情，默认 true"] = True,
    sync_financial: Annotated[bool, "是否同步财务数据，默认 true"] = True,
    sync_basic: Annotated[bool, "是否补充基础数据，默认 false"] = False,
) -> str:
    """同步单只股票的历史数据和财务数据。"""
    from app.routers.stock_sync import SingleStockSyncRequest, run_single_stock_sync

    require_current_user_id()

    normalized_symbol = _normalize_cn_symbol(symbol)
    if not (len(normalized_symbol) == 6 and normalized_symbol.isdigit()):
        return f"❌ 股票代码格式不正确：{symbol}。请输入 6 位数字代码，如 000001 或 600519。"

    if data_source not in {"tushare", "akshare"}:
        return f"❌ 暂仅支持 tushare 或 akshare 数据源，当前为：{data_source}。"

    if not sync_historical and not sync_financial and not sync_basic:
        return "❌ 请至少选择一种同步内容：历史数据、财务数据或基础数据。"

    try:
        result = await run_single_stock_sync(
            SingleStockSyncRequest(
                symbol=normalized_symbol,
                sync_realtime=False,
                sync_historical=sync_historical,
                sync_financial=sync_financial,
                sync_basic=sync_basic,
                data_source=data_source,
                days=days,
            )
        )
    except Exception as exc:
        logger.exception("[sync_single_stock_data] 单股数据同步失败: %s", exc)
        return f"❌ 单股数据同步失败：{exc}"

    lines = [
        f"{'✅' if result.get('overall_success') else '⚠️'} 单股数据同步完成",
        f"- 股票: {normalized_symbol}",
        f"- 数据源: {data_source}",
        _format_sync_section("历史数据", result.get("historical_sync")),
        _format_sync_section("财务数据", result.get("financial_sync")),
    ]

    if sync_basic:
        lines.append(_format_sync_section("基础数据", result.get("basic_sync")))

    if result.get("overall_success"):
        lines.append("- 结果: 本次请求的同步项已成功完成，可继续查询最新数据或发起分析。")
    else:
        lines.append("- 结果: 存在失败项，请根据上面的失败原因决定是否更换数据源或稍后重试。")

    return "\n".join(lines)