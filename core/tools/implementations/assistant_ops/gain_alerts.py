# 止盈提醒助手工具
# 提供设置、查看、清除止盈提醒的接口

favorites_service = FavoritesService()
def set_stop_gain_alert(user_id, symbol, gain_price):
def list_stop_gain_alerts(user_id):
def clear_stop_gain_alert(user_id, symbol):
from app.services.favorites_service import FavoritesService
from core.tools.registry import register_tool

favorites_service = FavoritesService()

@register_tool(
    name="设置止盈提醒",
    description="为指定股票设置止盈提醒价格，支持自选股管理。",
    category="风险管理",
    parameters=[
        {"name": "user_id", "type": "str", "description": "用户ID"},
        {"name": "symbol", "type": "str", "description": "股票代码"},
        {"name": "gain_price", "type": "float", "description": "止盈价格"}
    ]
)
def set_stop_gain_alert(user_id, symbol, gain_price):
    import asyncio
    loop = asyncio.get_event_loop()
    loop.run_until_complete(favorites_service.update_alert_gain_price(user_id, symbol, gain_price))
    return f"已为 {symbol} 设置止盈提醒：{gain_price}"

@register_tool(
    name="查看止盈提醒",
    description="列出当前用户所有已设置止盈提醒的股票。",
    category="风险管理",
    parameters=[
        {"name": "user_id", "type": "str", "description": "用户ID"}
    ]
)
def list_stop_gain_alerts(user_id):
    import asyncio
    loop = asyncio.get_event_loop()
    items = loop.run_until_complete(favorites_service.get_user_favorites(user_id))
    alerts = [item for item in items if item.get('alert_gain_price')]
    return alerts

@register_tool(
    name="清除止盈提醒",
    description="清除指定股票的止盈提醒价格。",
    category="风险管理",
    parameters=[
        {"name": "user_id", "type": "str", "description": "用户ID"},
        {"name": "symbol", "type": "str", "description": "股票代码"}
    ]
)
def clear_stop_gain_alert(user_id, symbol):
    import asyncio
    loop = asyncio.get_event_loop()
    loop.run_until_complete(favorites_service.update_alert_gain_price(user_id, symbol, None))
    return f"已清除 {symbol} 的止盈提醒"
