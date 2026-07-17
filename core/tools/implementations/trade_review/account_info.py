"""
获取账户信息工具

获取用户的资金账户信息，用于仓位分析
"""

import asyncio
import logging
from typing import Any, Annotated, Dict

from core.tools.base import register_tool

logger = logging.getLogger(__name__)


def _sum_currencies(d: Dict[str, float]) -> float:
    """将多币种字典汇总为单一数值（简化展示）"""
    return round(sum(v for v in d.values() if isinstance(v, (int, float))), 2)


@register_tool(
    tool_id="get_account_info",
    name="获取账户信息",
    description="获取用户资金账户信息，返回总资产、现金、持仓市值、盈亏及百分比、初始资金、累计出入金和多币种汇总等账户快照",
    category="trade_review",
    is_online=False,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["account_info", "account_balance", "portfolio", "trade_review", "trading", "cash", "positions_value", "total_assets", "profit"],
    tool_role_hint="specialized",
    output_shape="structured_json",
    preferred_for=["account_balance_query", "portfolio_analysis", "position_value_check", "capital_summary"],
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

        async def _fetch_account():
            service = get_portfolio_service()
            return await service.get_account_summary(user_id)

        import threading

        container = {}

        def _run_in_thread():
            try:
                container["result"] = asyncio.run(_fetch_account())
            except Exception as exc:
                container["error"] = exc

        t = threading.Thread(target=_run_in_thread)
        t.start()
        t.join(timeout=30)
        if "error" in container:
            raise container["error"]
        account_summary = container["result"]

        account_info = {
            "total_assets": account_summary.total_assets,
            "cash": account_summary.cash,
            "positions_value": account_summary.positions_value,
            "profit": account_summary.profit,
            "profit_pct": account_summary.profit_pct,
            "initial_capital": account_summary.initial_capital,
            "total_deposit": account_summary.total_deposit,
            "total_withdraw": account_summary.total_withdraw,
            "total_assets_sum": _sum_currencies(account_summary.total_assets),
            "cash_sum": _sum_currencies(account_summary.cash),
            "positions_value_sum": _sum_currencies(account_summary.positions_value),
            "profit_sum": _sum_currencies(account_summary.profit),
        }

        logger.info("✅ 获取账户信息成功: 总资产=%s", account_info["total_assets"])

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

