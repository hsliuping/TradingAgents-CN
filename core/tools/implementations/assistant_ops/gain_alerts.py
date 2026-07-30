"""
收益关注提醒类工具

提供收益关注价格（价格上限）提醒的设置、查看、清除能力，便于用户自行跟踪研究观察价位。
"""

import logging
from typing import Annotated

from langchain_core.tools import tool

from core.tools.base import register_tool
from core.tools.context import require_current_user_id

logger = logging.getLogger(__name__)


def _normalize_market(market: str) -> str:
    value = (market or "CN").upper()
    if value in ("CN", "A股", "SH", "SZ"):
        return "A股"
    if value in ("HK", "港股"):
        return "港股"
    if value in ("US", "美股"):
        return "美股"
    return "A股"


@tool
@register_tool(
    tool_id="set_stop_gain_alert",
    name="设置收益关注提醒",
    description="为股票设置收益关注价格上限（价格上限），价格接近时通过系统通知推送，便于用户自行跟踪研究观察价位。返回股票名称、代码、市场和已设置的收益关注价格。",
    category="assistant_ops",
    is_online=True,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["gain_alerts", "stop_gain", "alert", "set", "assistant_ops", "price_alert", "profit_taking", "notification", "alert_setup", "price_threshold"],
    tool_role_hint="primary",
    output_shape="text",
    preferred_for=["收益关注提醒设置", "收益关注价格配置", "价格上限提醒设置", "价格上限提醒"],
    when_to_use="当用户想为某只股票设置收益关注价格（价格上限）、希望在价格上涨到该价位时收到通知以自行关注研究观察价位时使用。",
    returns="返回文本消息，包含股票名称、代码、市场和已设置的收益关注价格（价格上限）。",
)
async def set_stop_gain_alert(
    symbol: Annotated[str, "股票代码，如 300033、00700、AAPL"],
    gain_price: Annotated[float, "收益关注价格上限（达到或接近该价格时提醒）"],
    market: Annotated[str, "市场：CN/HK/US，默认 CN"] = "CN",
) -> str:
    """设置股票收益关注价格（价格上限）提醒。"""
    try:
        from app.core.database import get_mongo_db
        from app.services.favorites_service import favorites_service

        user_id = require_current_user_id()
        market_label = _normalize_market(market)
        db = get_mongo_db()

        name = symbol
        pos = await db.real_positions.find_one({"user_id": user_id, "code": symbol}, {"name": 1})
        if pos and pos.get("name"):
            name = pos["name"]

        exists = await favorites_service.is_favorite(user_id, symbol)
        if not exists:
            await favorites_service.add_favorite(
                user_id=user_id,
                stock_code=symbol,
                stock_name=name,
                market=market_label,
            )

        ok = await favorites_service.update_alert_gain_price(user_id, symbol, gain_price)
        if not ok:
            return f"未找到 {symbol} 的股票关注列表记录，设置收益关注提醒失败。"

        return (
            f"✅ 已设置收益关注提醒（价格上限）\n"
            f"- 股票: {name}({symbol})\n"
            f"- 市场: {market_label}\n"
            f"- 收益关注价格: {gain_price:.2f}\n"
            f"当价格接近或达到该收益关注价格时，将收到系统通知，便于您自行关注研究观察价位。"
        )
    except Exception as e:
        logger.exception("[set_stop_gain_alert] 设置收益关注提醒失败: %s", e)
        return f"设置收益关注提醒失败: {e}"


@tool
@register_tool(
    tool_id="list_stop_gain_alerts",
    name="查看收益关注提醒",
    description="查看当前已设置的所有收益关注提醒（价格上限）。返回提醒数量及每条提醒的股票名称、代码、市场和收益关注价格。",
    category="assistant_ops",
    is_online=True,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["gain_alerts", "stop_gain", "alert", "list", "query", "assistant_ops", "price_alert", "profit_taking", "alert_query", "notification_list"],
    tool_role_hint="supporting",
    output_shape="text",
    preferred_for=["收益关注提醒查看", "收益关注列表查询", "已配置提醒浏览", "价格上限确认"],
    when_to_use="当用户想查看当前已设置的所有收益关注提醒（价格上限）、确认哪些股票配置了收益关注价格时使用。",
    returns="返回文本消息，包含收益关注提醒数量及每条提醒的股票、市场、收益关注价格（价格上限）。",
)
async def list_stop_gain_alerts() -> str:
    """查看已配置的收益关注提醒（价格上限）列表。"""
    try:
        from app.services.favorites_service import favorites_service

        user_id = require_current_user_id()
        items = await favorites_service.get_user_favorites(user_id)
        alerts = [item for item in items if item.get("alert_gain_price") is not None]

        if not alerts:
            return "当前没有设置任何收益关注提醒（价格上限）。"

        lines = [f"共 {len(alerts)} 条收益关注提醒（价格上限）：\n"]
        for item in alerts:
            code = item.get("stock_code", "")
            name = item.get("stock_name", code)
            market = item.get("market", "A股")
            gain = item.get("alert_gain_price")
            lines.append(f"- {name}({code}) | {market} | 收益关注价格: {float(gain):.2f}")
        return "\n".join(lines)
    except Exception as e:
        logger.exception("[list_stop_gain_alerts] 查看收益关注提醒失败: %s", e)
        return f"查看收益关注提醒失败: {e}"


@tool
@register_tool(
    tool_id="clear_stop_gain_alert",
    name="清除收益关注提醒",
    description="清除指定股票的收益关注提醒价格（价格上限，仅清提醒，不移除股票关注列表）。返回操作结果或未找到配置的提示。",
    category="assistant_ops",
    is_online=True,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["gain_alerts", "stop_gain", "alert", "clear", "delete", "assistant_ops", "price_alert", "profit_taking", "alert_removal", "notification_cleanup"],
    tool_role_hint="primary",
    output_shape="text",
    preferred_for=["收益关注提醒清除", "收益关注价格移除", "提醒配置删除", "价格上限取消"],
    when_to_use="当用户想清除某只股票的收益关注提醒（价格上限）、不再接收该股票的收益关注通知时使用（仅清除提醒，不移除股票关注列表）。",
    returns="返回文本消息，确认收益关注提醒已清除或提示未找到相关配置。",
)
async def clear_stop_gain_alert(
    symbol: Annotated[str, "股票代码，如 300033、00700、AAPL"],
) -> str:
    """清除某只股票的收益关注提醒（价格上限）。"""
    try:
        from app.services.favorites_service import favorites_service

        user_id = require_current_user_id()
        ok = await favorites_service.update_alert_gain_price(user_id, symbol, None)
        if ok:
            return f"✅ 已清除 {symbol} 的收益关注提醒（价格上限）。"
        return f"未找到 {symbol} 的提醒配置，或该股票不在股票关注列表中。"
    except Exception as e:
        logger.exception("[clear_stop_gain_alert] 清除收益关注提醒失败: %s", e)
        return f"清除收益关注提醒失败: {e}"
