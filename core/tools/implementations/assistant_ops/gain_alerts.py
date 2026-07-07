"""
止盈提醒类工具

提供止盈提醒的设置、查看、清除能力。
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
    name="设置止盈提醒",
    description="为一只股票设置止盈提醒价格（上限）。触发后将通过系统通知推送提醒。",
    category="assistant_ops",
    is_online=True,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
)
async def set_stop_gain_alert(
    symbol: Annotated[str, "股票代码，如 300033、00700、AAPL"],
    gain_price: Annotated[float, "止盈价格（达到或接近该价格时提醒）"],
    market: Annotated[str, "市场：CN/HK/US，默认 CN"] = "CN",
) -> str:
    """设置股票止盈提醒（价格上限）。"""
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
            return f"未找到 {symbol} 的自选股记录，设置止盈提醒失败。"

        return (
            f"✅ 已设置止盈提醒\n"
            f"- 股票: {name}({symbol})\n"
            f"- 市场: {market_label}\n"
            f"- 止盈线: {gain_price:.2f}\n"
            f"当价格接近或达到该止盈线时，将收到系统通知。"
        )
    except Exception as e:
        logger.exception("[set_stop_gain_alert] 设置止盈提醒失败: %s", e)
        return f"设置止盈提醒失败: {e}"


@tool
@register_tool(
    tool_id="list_stop_gain_alerts",
    name="查看止盈提醒",
    description="查看当前已设置的止盈提醒列表（股票、市场、止盈价格）。",
    category="assistant_ops",
    is_online=True,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
)
async def list_stop_gain_alerts() -> str:
    """查看已配置的止盈提醒列表。"""
    try:
        from app.services.favorites_service import favorites_service

        user_id = require_current_user_id()
        items = await favorites_service.get_user_favorites(user_id)
        alerts = [item for item in items if item.get("alert_gain_price") is not None]

        if not alerts:
            return "当前没有设置任何止盈提醒。"

        lines = [f"共 {len(alerts)} 条止盈提醒：\n"]
        for item in alerts:
            code = item.get("stock_code", "")
            name = item.get("stock_name", code)
            market = item.get("market", "A股")
            gain = item.get("alert_gain_price")
            lines.append(f"- {name}({code}) | {market} | 止盈线: {float(gain):.2f}")
        return "\n".join(lines)
    except Exception as e:
        logger.exception("[list_stop_gain_alerts] 查看止盈提醒失败: %s", e)
        return f"查看止盈提醒失败: {e}"


@tool
@register_tool(
    tool_id="clear_stop_gain_alert",
    name="清除止盈提醒",
    description="清除某只股票的止盈提醒价格（仅清除提醒，不移除自选股）。",
    category="assistant_ops",
    is_online=True,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
)
async def clear_stop_gain_alert(
    symbol: Annotated[str, "股票代码，如 300033、00700、AAPL"],
) -> str:
    """清除某只股票的止盈提醒。"""
    try:
        from app.services.favorites_service import favorites_service

        user_id = require_current_user_id()
        ok = await favorites_service.update_alert_gain_price(user_id, symbol, None)
        if ok:
            return f"✅ 已清除 {symbol} 的止盈提醒。"
        return f"未找到 {symbol} 的提醒配置，或该股票不在自选股中。"
    except Exception as e:
        logger.exception("[clear_stop_gain_alert] 清除止盈提醒失败: %s", e)
        return f"清除止盈提醒失败: {e}"
