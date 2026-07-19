"""
股票关注列表管理类工具

提供股票关注列表分组的查询、添加股票和移除股票功能。
用户身份通过 core.tools.context 获取。
"""

import logging
from typing import Annotated

from langchain_core.tools import tool

from core.tools.base import register_tool
from core.tools.context import require_current_user_id

logger = logging.getLogger(__name__)


@tool
@register_tool(
    tool_id="list_watchlist_groups",
    name="查看股票关注列表分组",
    description="列出用户的股票关注列表分组，显示分组名称、股票数量和股票代码预览。注意：这是分组视图，不等于完整的股票关注列表本体，也不等于定时分析配置。",
    category="assistant_ops",
    is_online=True,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["watchlist", "group", "list", "query", "assistant_ops", "stock_group", "watchlist_group", "stock_watchlist", "portfolio_group", "self_selected", "watchlist_query"],
    tool_role_hint="primary",
    output_shape="text",
    preferred_for=["查看股票关注列表分组", "股票关注列表列表", "分组查询", "股票池查看"],
    when_to_use="当用户想查看自己的股票关注列表分组列表、了解每个分组包含哪些股票时使用。",
    returns="返回文本格式的股票关注列表分组列表，每条含分组ID、名称、股票数量和股票代码预览。",
)
async def list_watchlist_groups() -> str:
    """列出当前用户的股票关注列表分组及每组股票数量。"""
    from app.core.database import get_mongo_db

    user_id = require_current_user_id()
    db = get_mongo_db()

    cursor = db.watchlist_groups.find({"user_id": user_id}).sort("sort_order", 1)

    groups = []
    async for doc in cursor:
        gid = str(doc["_id"])
        name = doc.get("name", "未命名")
        stocks = doc.get("stock_codes", [])
        active = "✅" if doc.get("is_active", True) else "⏸️"
        preview = ", ".join(stocks[:5])
        if len(stocks) > 5:
            preview += f" +{len(stocks) - 5}"
        groups.append(f"  {active} [{gid[:8]}] {name}（{len(stocks)}只）: {preview}")

    if not groups:
        return "📂 暂无股票关注列表分组。你可以让我帮你创建一个。\n\n提示：分组只是组织方式；若要查看完整股票关注列表，请使用“查看股票关注列表”。"
    return (
        f"📂 共 {len(groups)} 个股票关注列表分组：\n"
        + "\n".join(groups)
        + "\n\n说明：以上是你的股票关注列表分组视图，不等于完整股票关注列表，也不等于定时分析配置。"
        + "若要查看完整关注股票，请调用“查看股票关注列表”；若要查看自动分析计划，请调用“查看定时分析配置”。"
    )


@tool
@register_tool(
    tool_id="add_stock_to_watchlist",
    name="添加股票到股票关注列表分组",
    description="将一只或多只股票添加到指定名称的股票关注列表分组。分组不存在时自动创建新分组。注意：这只是分组管理，不代表会自动进入定时分析。",
    category="assistant_ops",
    is_online=True,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["watchlist", "group", "add", "stock", "assistant_ops", "stock_add", "watchlist_add", "portfolio_management", "self_selected", "stock_code", "watchlist_management"],
    tool_role_hint="primary",
    output_shape="text",
    preferred_for=["添加股票关注列表", "加入股票分组", "股票关注列表管理", "新建股票分组"],
    when_to_use="当用户想把一只或多只股票添加到股票关注列表分组、或需要新建分组并加入股票时使用。",
    returns="返回文本消息，提示新增股票数量、分组当前股票总数；新建分组时返回分组创建结果。",
)
async def add_stock_to_watchlist(
    group_name: Annotated[str, "股票关注列表分组名称，如「科技股」"],
    symbols: Annotated[str, "要添加的股票代码，逗号分隔，如 000001,600519"],
) -> str:
    """将一只或多只股票添加到指定名称的股票关注列表分组。分组不存在时自动创建。"""
    from app.core.database import get_mongo_db
    from app.utils.timezone import now_tz

    user_id = require_current_user_id()
    db = get_mongo_db()

    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
    if not symbol_list:
        return "❌ 请提供至少一个股票代码。"

    # 按名称查找分组
    group = await db.watchlist_groups.find_one({"user_id": user_id, "name": group_name})

    if group:
        # 已有分组，添加股票（去重）
        current = set(group.get("stock_codes", []))
        new_codes = set(symbol_list) - current
        if not new_codes:
            return f"ℹ️ 这些股票已在分组「{group_name}」中，无需重复添加。"
        updated = list(current | set(symbol_list))
        await db.watchlist_groups.update_one(
            {"_id": group["_id"]},
            {"$set": {"stock_codes": updated, "updated_at": now_tz()}},
        )
        return (
            f"✅ 已添加 {len(new_codes)} 只股票到「{group_name}」\n"
            f"- 新增: {', '.join(sorted(new_codes))}\n"
            f"- 分组当前共 {len(updated)} 只股票"
        )
    else:
        # 自动创建分组
        max_sort_doc = await db.watchlist_groups.find_one(
            {"user_id": user_id}, sort=[("sort_order", -1)]
        )
        next_sort = (max_sort_doc["sort_order"] + 1) if max_sort_doc else 0

        new_doc = {
            "user_id": user_id,
            "name": group_name,
            "description": "",
            "color": "#409EFF",
            "icon": "folder",
            "stock_codes": symbol_list,
            "analysis_depth": None,
            "quick_analysis_model": None,
            "deep_analysis_model": None,
            "prompt_template_id": None,
            "sort_order": next_sort,
            "is_active": True,
            "created_at": now_tz(),
            "updated_at": now_tz(),
        }
        await db.watchlist_groups.insert_one(new_doc)
        return (
            f"✅ 已自动创建分组「{group_name}」并添加 {len(symbol_list)} 只股票\n"
            f"- 股票: {', '.join(symbol_list)}"
        )


@tool
@register_tool(
    tool_id="remove_stock_from_watchlist",
    name="从股票关注列表分组移除股票",
    description="从指定名称的股票关注列表分组中移除一只或多只股票。不会删除分组本身，也不会影响已有定时分析配置。",
    category="assistant_ops",
    is_online=True,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["watchlist", "group", "remove", "stock", "assistant_ops", "stock_remove", "watchlist_remove", "portfolio_management", "self_selected", "stock_delete", "watchlist_management"],
    tool_role_hint="primary",
    output_shape="text",
    preferred_for=["移除股票关注列表", "删除股票分组中的股票", "股票关注列表管理", "清理股票池"],
    when_to_use="当用户想从股票关注列表分组中移除一只或多只股票、清理不再关注的股票时使用。",
    returns="返回文本消息，提示移除股票数量和分组剩余股票数量。",
)
async def remove_stock_from_watchlist(
    group_name: Annotated[str, "股票关注列表分组名称"],
    symbols: Annotated[str, "要移除的股票代码，逗号分隔"],
) -> str:
    """从指定名称的股票关注列表分组中移除一只或多只股票。"""
    from app.core.database import get_mongo_db
    from app.utils.timezone import now_tz

    user_id = require_current_user_id()
    db = get_mongo_db()

    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
    if not symbol_list:
        return "❌ 请提供至少一个股票代码。"

    group = await db.watchlist_groups.find_one({"user_id": user_id, "name": group_name})
    if not group:
        return f"❌ 未找到分组「{group_name}」。可以用「查看股票关注列表分组」查看现有分组。"

    current = set(group.get("stock_codes", []))
    to_remove = set(symbol_list) & current
    if not to_remove:
        return f"ℹ️ 这些股票不在分组「{group_name}」中。"

    remaining = list(current - to_remove)
    await db.watchlist_groups.update_one(
        {"_id": group["_id"]},
        {"$set": {"stock_codes": remaining, "updated_at": now_tz()}},
    )
    return (
        f"✅ 已从「{group_name}」移除 {len(to_remove)} 只股票\n"
        f"- 移除: {', '.join(sorted(to_remove))}\n"
        f"- 分组剩余 {len(remaining)} 只股票"
    )

