"""
风险提醒类工具

提供价格下限提醒的设置、查看、清除能力，便于用户自行跟踪风险。
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
    name="设置价格下限提醒",
    description="为股票设置价格下限提醒，价格接近或跌破时通过系统通知推送，便于用户自行跟踪风险。返回股票名称、代码、市场和提醒价格。",
    category="assistant_ops",
    is_online=True,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["risk_alerts", "stop_loss", "alert", "set", "assistant_ops", "price_alert", "risk_management", "notification", "alert_setup", "price_threshold", "loss_prevention"],
    tool_role_hint="primary",
    output_shape="text",
    preferred_for=["价格下限提醒设置", "风险关注价格配置", "风险控制提醒", "价格下限提醒"],
    when_to_use="当用户想为某只股票设置价格下限、希望在价格跌破阈值时收到通知以自行关注风险时使用。",
    returns="返回文本消息，包含股票名称、代码、市场和已设置的价格下限。",
)
async def set_stop_loss_alert(
    symbol: Annotated[str, "股票代码，如 300033、00700、AAPL"],
    stop_loss_price: Annotated[float, "价格下限（低于或接近该价格时提醒）"],
    market: Annotated[str, "市场：CN/HK/US，默认 CN"] = "CN",
) -> str:
    """设置股票价格下限提醒。"""
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

        # 若不存在则自动加入股票关注列表，再写入提醒阈值
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
            f"✅ 已设置价格下限提醒\n"
            f"- 股票: {name}({symbol})\n"
            f"- 市场: {market_label}\n"
            f"- 价格下限: {stop_loss_price:.2f}\n"
            f"当价格接近或跌破该下限时，将收到系统通知，便于您自行关注风险。"
        )
    except Exception as e:
        logger.exception("[set_stop_loss_alert] 设置价格下限提醒失败: %s", e)
        return f"设置价格下限提醒失败: {e}"


@tool
@register_tool(
    tool_id="list_stop_loss_alerts",
    name="查看价格下限提醒",
    description="查看当前已设置的所有价格下限提醒。返回提醒数量及每条提醒的股票名称、代码、市场和提醒价格。",
    category="assistant_ops",
    is_online=True,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["risk_alerts", "stop_loss", "alert", "list", "query", "assistant_ops", "price_alert", "risk_management", "alert_query", "notification_list"],
    tool_role_hint="supporting",
    output_shape="text",
    preferred_for=["价格下限提醒查看", "价格下限列表查询", "已配置提醒浏览", "风险控制确认"],
    when_to_use="当用户想查看当前已设置的所有价格下限提醒、确认哪些股票配置了价格下限时使用。",
    returns="返回文本消息，包含价格下限提醒数量及每条提醒的股票、市场、提醒价格。",
)
async def list_stop_loss_alerts() -> str:
    """查看已配置的价格下限提醒列表。"""
    try:
        from app.services.favorites_service import favorites_service

        user_id = require_current_user_id()
        items = await favorites_service.get_user_favorites(user_id)
        alerts = [x for x in items if x.get("alert_price_low") is not None]

        if not alerts:
            return "当前没有设置任何价格下限提醒。"

        lines = [f"共 {len(alerts)} 条价格下限提醒：\n"]
        for it in alerts:
            code = it.get("stock_code", "")
            name = it.get("stock_name", code)
            market = it.get("market", "A股")
            low = it.get("alert_price_low")
            lines.append(f"- {name}({code}) | {market} | 价格下限: {float(low):.2f}")
        return "\n".join(lines)
    except Exception as e:
        logger.exception("[list_stop_loss_alerts] 查看价格下限提醒失败: %s", e)
        return f"查看价格下限提醒失败: {e}"


@tool
@register_tool(
    tool_id="clear_stop_loss_alert",
    name="清除价格下限提醒",
    description="清除指定股票的价格下限提醒（仅清提醒，不移除股票关注列表）。返回操作结果或未找到配置的提示。",
    category="assistant_ops",
    is_online=True,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["risk_alerts", "stop_loss", "alert", "clear", "delete", "assistant_ops", "price_alert", "risk_management", "alert_removal", "notification_cleanup"],
    tool_role_hint="primary",
    output_shape="text",
    preferred_for=["价格下限提醒清除", "风险关注价格移除", "提醒配置删除", "风险提醒取消"],
    when_to_use="当用户想清除某只股票的价格下限提醒、不再接收该股票的价格下限通知时使用（仅清除提醒，不移除股票关注列表）。",
    returns="返回文本消息，确认价格下限提醒已清除或提示未找到相关配置。",
)
async def clear_stop_loss_alert(
    symbol: Annotated[str, "股票代码，如 300033、00700、AAPL"],
) -> str:
    """清除某只股票的价格下限提醒。"""
    try:
        from app.services.favorites_service import favorites_service

        user_id = require_current_user_id()
        ok = await favorites_service.update_favorite(
            user_id=user_id,
            stock_code=symbol,
            clear_alert_price_low=True,
        )
        if ok:
            return f"✅ 已清除 {symbol} 的价格下限提醒。"
        return f"未找到 {symbol} 的价格下限提醒配置，或该股票不在股票关注列表中。"
    except Exception as e:
        logger.exception("[clear_stop_loss_alert] 清除价格下限提醒失败: %s", e)
        return f"清除价格下限提醒失败: {e}"
