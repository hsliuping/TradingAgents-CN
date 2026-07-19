"""使用问答机器人工具：查询用户当前状态。

提供查询当前用户的关注列表股票数、历史任务数、最近任务、定时分析配置数等能力，
让使用问答助手能"看到"用户当前真实状态，而非凭 FAQ 猜答案。
"""

import logging
from datetime import datetime
from typing import Annotated, Any, Dict, List

from langchain_core.tools import tool

from core.tools.base import register_tool
from core.tools.context import require_current_user_id

logger = logging.getLogger(__name__)


def _is_valid_object_id(user_id: str) -> bool:
    if not user_id or not isinstance(user_id, str):
        return False
    try:
        from bson import ObjectId
        ObjectId(user_id)
        return len(user_id) == 24
    except Exception:
        return False


async def _count_user_favorites(db, user_id: str) -> tuple[int, List[Dict[str, Any]]]:
    """返回 (关注列表股票数, 前 5 条股票名)"""
    try:
        if _is_valid_object_id(user_id):
            from bson import ObjectId
            user = await db.users.find_one({"_id": ObjectId(user_id)}, {"favorite_stocks": 1})
            if user is None:
                user = await db.users.find_one({"_id": user_id}, {"favorite_stocks": 1})
            favorites = (user or {}).get("favorite_stocks", []) or []
        else:
            doc = await db.user_favorites.find_one({"user_id": user_id}, {"favorites": 1})
            favorites = (doc or {}).get("favorites", []) or []

        count = len(favorites)
        preview = [
            f"{f.get('stock_name', '?')}({f.get('stock_code', '?')})"
            for f in favorites[:5]
        ]
        return count, preview
    except Exception as exc:
        logger.warning("[get_user_current_state] 查询关注列表失败: %s", exc)
        return -1, []


async def _count_user_tasks(db, user_id: str) -> tuple[int, int, List[Dict[str, Any]]]:
    """返回 (任务总数, 失败任务数, 最近 5 条任务摘要)"""
    try:
        # unified_analysis_tasks 集合 user_id 可能是字符串或 ObjectId
        query: Dict[str, Any] = {"user_id": user_id}
        total = await db.unified_analysis_tasks.count_documents(query)
        if total == 0 and _is_valid_object_id(user_id):
            from bson import ObjectId
            total = await db.unified_analysis_tasks.count_documents({"user_id": ObjectId(user_id)})

        recent_cursor = db.unified_analysis_tasks.find(
            query, {"status": 1, "task_params": 1, "created_at": 1, "task_type": 1, "error_message": 1}
        ).sort("created_at", -1).limit(5)
        recent = await recent_cursor.to_list(length=5)

        if not recent and _is_valid_object_id(user_id):
            from bson import ObjectId
            recent_cursor2 = db.unified_analysis_tasks.find(
                {"user_id": ObjectId(user_id)},
                {"status": 1, "task_params": 1, "created_at": 1, "task_type": 1, "error_message": 1}
            ).sort("created_at", -1).limit(5)
            recent = await recent_cursor2.to_list(length=5)
            if total == 0:
                total = await db.unified_analysis_tasks.count_documents({"user_id": ObjectId(user_id)})

        failed = sum(1 for t in recent if t.get("status") == "failed")
        preview = []
        for t in recent:
            params = t.get("task_params") or {}
            symbol = params.get("symbol") or params.get("stock_code") or "?"
            status = t.get("status", "?")
            created = t.get("created_at")
            created_str = created.isoformat()[:19] if isinstance(created, datetime) else (str(created)[:19] if created else "?")
            preview.append({
                "symbol": symbol,
                "status": status,
                "task_type": t.get("task_type", "?"),
                "created_at": created_str,
                "error": (t.get("error_message") or "")[:100] if status == "failed" else None,
            })
        return total, failed, preview
    except Exception as exc:
        logger.warning("[get_user_current_state] 查询任务失败: %s", exc)
        return -1, 0, []


async def _count_scheduled(db, user_id: str) -> int:
    """返回启用中的定时分析配置数"""
    try:
        count = await db.scheduled_analysis_configs.count_documents({"user_id": user_id, "enabled": True})
        return count
    except Exception as exc:
        logger.warning("[get_user_current_state] 查询定时分析配置失败: %s", exc)
        return -1


@tool
@register_tool(
    tool_id="get_user_current_state",
    name="获取用户当前状态",
    description="查询当前用户的关注列表股票数、历史任务总数、最近任务执行情况、定时分析配置数。当用户问'我的任务在哪''关注列表里有几只股票''今日任务为什么是0'等问题时使用。",
    category="assistant_ops",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["usage_helper", "user_state", "favorites_count", "task_count", "recent_tasks", "scheduled_analysis"],
    tool_role_hint="primary",
    output_shape="text",
    preferred_for=["查询关注列表数量", "查看任务总数", "今日任务为什么是0", "最近任务执行情况"],
    when_to_use="当用户问到自己当前状态（关注列表数/任务数/定时分析配置）时使用。",
    returns="返回文本格式的用户状态摘要，包含关注列表股票数、任务总数、失败任务数、最近 5 条任务和定时分析配置数。",
)
async def get_user_current_state() -> str:
    """获取当前用户的系统状态摘要。"""
    from app.core.database import get_mongo_db

    user_id = require_current_user_id()
    db = get_mongo_db()

    fav_count, fav_preview = await _count_user_favorites(db, user_id)
    task_total, task_failed, task_recent = await _count_user_tasks(db, user_id)
    scheduled_count = await _count_scheduled(db, user_id)

    lines = ["📊 用户当前状态"]
    if fav_count >= 0:
        lines.append(f"- 关注列表股票数: {fav_count}")
        if fav_preview:
            lines.append(f"  前 5 只: {', '.join(fav_preview)}")
    else:
        lines.append("- 关注列表股票数: 查询失败")

    if task_total >= 0:
        lines.append(f"- 历史任务总数: {task_total}")
        lines.append(f"- 最近 5 条任务中失败数: {task_failed}")
        for t in task_recent:
            err_hint = f" ❌错误: {t['error']}" if t.get("error") else ""
            lines.append(f"  • {t['symbol']} | {t['task_type']} | {t['status']} | {t['created_at']}{err_hint}")
    else:
        lines.append("- 历史任务: 查询失败")

    if scheduled_count >= 0:
        lines.append(f"- 启用中的定时分析配置: {scheduled_count}")
    else:
        lines.append("- 定时分析配置: 查询失败")

    return "\n".join(lines)
