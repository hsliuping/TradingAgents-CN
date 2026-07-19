"""使用问答机器人工具：查询用户最近任务和错误日志。

提供查询用户最近 N 条任务、失败任务错误信息等能力，
让使用问答助手能"看到"用户最近操作的真实状态，便于排查"为什么报错""任务去哪了"等问题。
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


async def _query_recent_tasks(db, user_id: str, limit: int) -> List[Dict[str, Any]]:
    """查询用户最近任务（兼容 ObjectId 和字符串 user_id）"""
    queries = [{"user_id": user_id}]
    if _is_valid_object_id(user_id):
        from bson import ObjectId
        queries.append({"user_id": ObjectId(user_id)})

    for query in queries:
        try:
            cursor = db.unified_analysis_tasks.find(
                query,
                {
                    "task_id": 1, "task_type": 1, "status": 1, "task_params": 1,
                    "created_at": 1, "started_at": 1, "completed_at": 1,
                    "execution_time": 1, "error_message": 1, "current_step": 1,
                }
            ).sort("created_at", -1).limit(limit)
            docs = await cursor.to_list(length=limit)
            if docs:
                return docs
        except Exception as exc:
            logger.warning("[get_user_recent_activity] 查询失败 query=%s: %s", query, exc)
    return []


def _format_task_line(t: Dict[str, Any]) -> str:
    """格式化单条任务"""
    params = t.get("task_params") or {}
    symbol = params.get("symbol") or params.get("stock_code") or params.get("analysis_target") or "?"
    status = t.get("status", "?")
    task_type = t.get("task_type", "?")
    task_id = t.get("task_id", "?")

    # 时间字段
    created = t.get("created_at")
    started = t.get("started_at")
    completed = t.get("completed_at")
    created_str = created.isoformat()[:19] if isinstance(created, datetime) else (str(created)[:19] if created else "?")
    completed_str = completed.isoformat()[:19] if isinstance(completed, datetime) else (str(completed)[:19] if completed else "")

    # 执行时长
    exec_time = t.get("execution_time") or 0
    exec_hint = f" | 耗时 {exec_time:.1f}s" if isinstance(exec_time, (int, float)) and exec_time > 0 else ""

    # 错误信息
    error_hint = ""
    if status == "failed":
        err_msg = (t.get("error_message") or "无错误信息")[:200]
        error_hint = f"\n      ❌ 错误: {err_msg}"

    # 进度
    progress_hint = ""
    if status == "running" and t.get("current_step"):
        progress_hint = f" | 当前步骤: {t['current_step']}"

    completed_part = f" | 完成于 {completed_str}" if completed_str else ""
    return f"  • [{task_type}] {symbol} | {status}{progress_hint}{exec_hint}{completed_part} | 创建于 {created_str} | task_id={task_id}{error_hint}"


@tool
@register_tool(
    tool_id="get_user_recent_activity",
    name="获取用户最近活动",
    description="查询当前用户最近 N 条任务（默认 10 条）的执行情况，包括状态、耗时、错误信息。当用户问'我的任务去哪了''为什么任务失败''最近执行了什么'等问题时使用。",
    category="assistant_ops",
    is_online=False,
    auto_register=True,
    timeout_tier="light",
    data_source_handling="local_only",
    capability_tags=["usage_helper", "user_activity", "recent_tasks", "error_log", "task_history"],
    tool_role_hint="primary",
    output_shape="text",
    preferred_for=["最近任务执行情况", "为什么任务失败", "任务去哪了", "排查报错"],
    when_to_use="当用户问到自己最近的任务执行情况、报错原因或任务历史时使用。",
    returns="返回文本格式的最近任务列表，包含任务类型、目标、状态、耗时和错误信息。",
)
async def get_user_recent_activity(
    limit: Annotated[int, "返回最近 N 条任务，默认 10，最大 30"] = 10,
) -> str:
    """获取当前用户最近的任务执行记录。"""
    from app.core.database import get_mongo_db

    if limit < 1:
        limit = 1
    if limit > 30:
        limit = 30

    user_id = require_current_user_id()
    db = get_mongo_db()

    tasks = await _query_recent_tasks(db, user_id, limit)

    if not tasks:
        return f"📭 最近没有任务记录（已查询 {limit} 条上限，user_id={user_id}）。可能原因：\n  - 你还没有发起过任何分析任务\n  - 数据库连接异常\n  - user_id 字段不匹配（试试 Ctrl+F5 刷新页面）"

    failed_count = sum(1 for t in tasks if t.get("status") == "failed")
    success_count = sum(1 for t in tasks if t.get("status") == "completed")
    running_count = sum(1 for t in tasks if t.get("status") == "running")
    pending_count = sum(1 for t in tasks if t.get("status") == "pending")

    lines = [
        f"📋 最近 {len(tasks)} 条任务（成功 {success_count} | 失败 {failed_count} | 运行中 {running_count} | 排队 {pending_count}）",
        "",
    ]
    for t in tasks:
        lines.append(_format_task_line(t))

    if failed_count > 0:
        lines.append("")
        lines.append(f"💡 失败任务 {failed_count} 条，请查看上方每条任务的错误信息。常见原因：")
        lines.append("  - 数据源 Token 未配置或失效")
        lines.append("  - LLM 调用超时或额度不足")
        lines.append("  - 股票代码错误或数据不存在")

    return "\n".join(lines)
