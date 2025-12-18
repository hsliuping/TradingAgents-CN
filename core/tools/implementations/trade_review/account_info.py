"""
获取账户信息工具

获取用户的资金账户信息，用于仓位分析
"""

import logging
from typing import Dict, Any, Annotated
from core.tools.base import register_tool

logger = logging.getLogger(__name__)


@register_tool(
    tool_id="get_account_info",
    name="获取账户信息",
    description="获取用户的资金账户信息，包括现金、持仓市值、总资产等",
    category="trade_review",
    is_online=False
)
def get_account_info(
    user_id: Annotated[str, "用户ID"]
) -> Dict[str, Any]:
    """
    获取账户信息

    Args:
        user_id: 用户ID

    Returns:
        包含账户信息的字典
    """
    try:
        from app.services.portfolio_service import get_portfolio_service
        import asyncio

        async def _fetch_account():
            service = get_portfolio_service()
            account_summary = await service.get_account_summary(user_id)
            return account_summary

        # 在同步上下文中运行异步代码
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        account_summary = loop.run_until_complete(_fetch_account())

        account_info = {
            "total_assets": account_summary.total_assets,
            "cash": account_summary.cash,
            "positions_value": account_summary.positions_value,
            "total_pnl": account_summary.total_pnl,
            "total_pnl_pct": account_summary.total_pnl_pct,
            "initial_capital": account_summary.initial_capital,
            "total_deposit": account_summary.total_deposit,
            "total_withdraw": account_summary.total_withdraw
        }

        logger.info(f"✅ 获取账户信息成功: 总资产={account_info['total_assets']}")

        return {
            "success": True,
            "data": account_info
        }

    except Exception as e:
        logger.error(f"❌ 获取账户信息失败: {e}")
        return {
            "success": False,
            "error": str(e),
            "data": None
        }

