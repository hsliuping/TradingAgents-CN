"""
风险提醒类工具

提供止损提醒的设置、查看、清除能力。
"""

import logging
from typing import Annotated, Optional

from langchain_core.tools import tool

from core.tools.base import register_tool
from core.tools.context import require_current_user_id

logger = logging.getLogger(__name__)


def _normalize_market(market: str) -> str:
    m = (market or "CN").upper()
    if m in ("CN", "A股", "SH", "SZ"):
        return "A股"
    if m in ("HK", "港股"):
        return "港股"
    if m in ("US", "美股"):
        return "美股"
    return "A股"


@tool
@register_tool(
    tool_id="set_stop_loss_alert",
    name="设置止损提醒",
    description="为一只股票设置止损提醒价格（下限）。支持持仓股票优先场景。触发后将通过系统通知推送提醒。",
    category="assistant_ops",
    is_online=True,
    auto_register=True,
    timeout_tier="light",
)
async def set_stop_loss_alert(
    symbol: Annotated[str, "股票代码，如 300033、00700、AAPL"],
    stop_loss_price: Annotated[float, "止损价格（低于或接近该价格时提醒）"],
    market: Annotated[str, "市场：CN/HK/US，默认 CN"] = "CN",
) -> str:
    """设置股票止损提醒（价格下限）。"""
    try:
        from app.services.favorites_service import favorites_service
        from app.core.database import get_mongo_db

        user_id = require_current_user_id()
        market_label = _normalize_market(market)
        db = get_mongo_db()

        # 尝试从持仓中补全股票名称
        name = symbol
        pos = await db.real_positions.find_one({"user_id": user_id, "code": symbol}, {"name": 1})
        if pos and pos.get("name"):
            name = pos["name"]

        # 若不存在则自动加入自选股，再写入提醒阈值
        exists = await favorites_service.is_favorite(user_id, symbol)
        if not exists:
            await favorites_service.add_favorite(
                user_id=user_id,
                stock_code=symbol,
                stock_name=name,
                market=market_label,
                alert_price_low=stop_loss_price,
            )
        else:
            await favorites_service.update_favorite(
                user_id=user_id,
                stock_code=symbol,
                alert_price_low=stop_loss_price,
            )

        return (
            f"✅ 已设置止损提醒\n"
            f"- 股票: {name}({symbol})\n"
            f"- 市场: {market_label}\n"
            f"- 止损线: {stop_loss_price:.2f}\n"
            f"当价格接近或跌破该止损线时，将收到系统通知。"
        )
    except Exception as e:
        logger.exception("[set_stop_loss_alert] 设置止损提醒失败: %s", e)
        return f"设置止损提醒失败: {e}"


@tool
@register_tool(
    tool_id="list_stop_loss_alerts",
    name="查看止损提醒",
    description="查看当前已设置的止损提醒列表（股票、市场、止损价格）。",
    category="assistant_ops",
    is_online=True,
    auto_register=True,
    timeout_tier="light",
)
async def list_stop_loss_alerts() -> str:
    """查看已配置的止损提醒列表。"""
    try:
        from app.services.favorites_service import favorites_service

        user_id = require_current_user_id()
        items = await favorites_service.get_user_favorites(user_id)
        alerts = [x for x in items if x.get("alert_price_low") is not None]

        if not alerts:
            return "当前没有设置任何止损提醒。"

        lines = [f"共 {len(alerts)} 条止损提醒：\n"]
        for it in alerts:
            code = it.get("stock_code", "")
            name = it.get("stock_name", code)
            market = it.get("market", "A股")
            low = it.get("alert_price_low")
            lines.append(f"- {name}({code}) | {market} | 止损线: {float(low):.2f}")
        return "\n".join(lines)
    except Exception as e:
        logger.exception("[list_stop_loss_alerts] 查看止损提醒失败: %s", e)
        return f"查看止损提醒失败: {e}"


@tool
@register_tool(
    tool_id="clear_stop_loss_alert",
    name="清除止损提醒",
    description="清除某只股票的止损提醒价格（仅清除提醒，不移除自选股）。",
    category="assistant_ops",
    is_online=True,
    auto_register=True,
    timeout_tier="light",
)
async def clear_stop_loss_alert(
    symbol: Annotated[str, "股票代码，如 300033、00700、AAPL"],
) -> str:
    """清除某只股票的止损提醒。"""
    try:
        from app.services.favorites_service import favorites_service

        user_id = require_current_user_id()
        ok = await favorites_service.update_favorite(
            user_id=user_id,
            stock_code=symbol,
            clear_alert_price_low=True,
        )
        if ok:
            return f"✅ 已清除 {symbol} 的止损提醒。"
        return f"未找到 {symbol} 的提醒配置，或该股票不在自选股中。"
    except Exception as e:
        logger.exception("[clear_stop_loss_alert] 清除止损提醒失败: %s", e)
        return f"清除止损提醒失败: {e}"
