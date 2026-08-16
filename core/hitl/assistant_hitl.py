"""智能助手 HITL 集成（v3.5.0 项4）。

在智能助手 ReAct 循环中，对"关键操作"实现真正的 HITL：
1. LLM 调用关键工具时，不直接执行，而是保存 pending 操作到 MongoDB
2. 返回"需要确认"消息给 LLM，LLM 转告用户
3. 用户通过前端确认/拒绝（调用 /api/assistant/hitl/{pending_id}/confirm 或 reject）
4. 确认后执行真正的工作；拒绝则丢弃

关键操作清单（基于 system prompt 中的"先确认再执行"原则）：
- trigger_stock_analysis（触发分析）
- trigger_batch_analysis（批量分析）
- remove_stock_from_watchlist（移除自选股）
- delete_scheduled_config（删除定时配置）
- delete_topic（删除研究主题）
"""

from __future__ import annotations

import logging
import re
import uuid
from typing import Any, Awaitable, Callable, Dict, List, Optional

from .checkpoint_store import HITLCheckpointService, get_hitl_service

logger = logging.getLogger(__name__)


# 需要 HITL 确认的关键工具 ID 列表
CRITICAL_TOOL_IDS: Dict[str, Dict[str, Any]] = {
    "trigger_stock_analysis": {
        "display_name": "触发股票分析",
        "risk_level": "medium",
        "reason": "分析任务会消耗较多 Token 和时间",
    },
    "trigger_batch_analysis": {
        "display_name": "触发批量分析",
        "risk_level": "high",
        "reason": "批量分析会同时消耗大量资源",
    },
    "remove_stock_from_watchlist": {
        "display_name": "移除自选股",
        "risk_level": "medium",
        "reason": "移除操作不可自动恢复",
    },
    "delete_scheduled_config": {
        "display_name": "删除定时分析配置",
        "risk_level": "high",
        "reason": "删除配置会影响后续自动分析",
    },
    "delete_topic": {
        "display_name": "删除研究主题",
        "risk_level": "high",
        "reason": "删除主题会丢失相关对话历史",
    },
}


# 用户确认意图的关键词
CONFIRM_KEYWORDS = {"确认", "确定", "yes", "ok", "好的", "同意", "执行", "确认执行", "确认删除", "继续"}
REJECT_KEYWORDS = {"取消", "no", "不", "不要", "拒绝", "算了", "放弃", "不执行", "取消执行"}


def is_critical_tool(tool_id: str) -> bool:
    """判断工具是否为关键操作（需要 HITL）"""
    return tool_id in CRITICAL_TOOL_IDS


def is_user_confirming(user_message: str) -> bool:
    """判断用户消息是否为确认意图"""
    if not user_message:
        return False
    msg = user_message.strip().lower()
    return any(kw in msg for kw in CONFIRM_KEYWORDS)


def is_user_rejecting(user_message: str) -> bool:
    """判断用户消息是否为拒绝意图"""
    if not user_message:
        return False
    msg = user_message.strip().lower()
    return any(kw in msg for kw in REJECT_KEYWORDS)


def generate_pending_id() -> str:
    """生成唯一的 pending_id"""
    return f"hitl_{uuid.uuid4().hex[:12]}"


async def save_pending_critical_action(
    db: Any,
    *,
    user_id: str,
    conversation_id: str,
    tool_id: str,
    tool_arguments: Dict[str, Any],
    display_message: str = "",
) -> Optional[str]:
    """保存待确认的关键操作。

    Args:
        db: MongoDB 句柄
        user_id: 用户 ID
        conversation_id: 会话 ID
        tool_id: 工具 ID
        tool_arguments: 工具参数（用户确认后用于执行）
        display_message: 给用户看的说明

    Returns:
        pending_id 或 None（保存失败时）
    """
    if not is_critical_tool(tool_id):
        return None

    tool_meta = CRITICAL_TOOL_IDS[tool_id]
    pending_id = generate_pending_id()

    svc = get_hitl_service(db)
    try:
        await svc.save_pending(
            pending_id=pending_id,
            user_id=user_id,
            thread_id=conversation_id,
            operation_type="assistant_critical_action",
            operation_payload={
                "tool_id": tool_id,
                "tool_arguments": tool_arguments,
            },
            display_data={
                "tool_name": tool_meta["display_name"],
                "risk_level": tool_meta["risk_level"],
                "reason": tool_meta["reason"],
                "display_message": display_message or f"即将执行：{tool_meta['display_name']}",
                "arguments_preview": _format_arguments_preview(tool_arguments),
            },
        )
        return pending_id
    except Exception as e:
        logger.warning("[HITL·助手] 保存待确认操作失败: %s", e)
        return None


def _format_arguments_preview(arguments: Dict[str, Any]) -> str:
    """格式化参数预览（给用户看）"""
    if not arguments:
        return "（无参数）"
    parts = []
    for k, v in list(arguments.items())[:5]:
        v_str = str(v)
        if len(v_str) > 50:
            v_str = v_str[:50] + "..."
        parts.append(f"{k}={v_str}")
    return ", ".join(parts)


def build_pending_confirmation_reply(
    tool_id: str,
    tool_arguments: Dict[str, Any],
    pending_id: str,
) -> str:
    """构建"需要确认"的回复文本（LLM 看到后会转告用户）"""
    tool_meta = CRITICAL_TOOL_IDS.get(tool_id, {})
    display_name = tool_meta.get("display_name", tool_id)
    reason = tool_meta.get("reason", "")
    risk_level = tool_meta.get("risk_level", "medium")

    risk_emoji = {"high": "⚠️", "medium": "🟡", "low": "🟢"}.get(risk_level, "🟡")
    args_preview = _format_arguments_preview(tool_arguments)

    return (
        f"{risk_emoji} 即将执行关键操作：**{display_name}**\n\n"
        f"- 操作参数：{args_preview}\n"
        f"- 风险等级：{risk_level}\n"
        f"- 原因：{reason}\n\n"
        f"请确认是否执行（回复「确认」执行，回复「取消」放弃）。\n"
        f"确认 ID：`{pending_id}`"
    )


async def try_resolve_pending_action(
    db: Any,
    *,
    user_id: str,
    conversation_id: str,
    user_message: str,
) -> Optional[Dict[str, Any]]:
    """尝试解析用户的确认/拒绝意图，执行或丢弃待确认操作。

    在 chat() 主流程开始时调用，如果用户在确认/拒绝，则执行相应操作并返回结果。

    Returns:
        - None：用户消息不是确认/拒绝，或没有 pending 操作
        - {"type": "confirmed", "result": ...}：已确认并执行
        - {"type": "rejected", "message": ...}：已拒绝
    """
    svc = get_hitl_service(db)
    pending_list = await svc.list_pending(
        user_id=user_id,
        thread_id=conversation_id,
        operation_type="assistant_critical_action",
    )
    if not pending_list:
        return None

    # 取最新的 pending 操作
    pending = pending_list[0]
    if pending.status != "pending":
        return None

    if is_user_rejecting(user_message):
        await svc.decide(pending_id=pending.pending_id, decision="rejected")
        return {
            "type": "rejected",
            "message": f"已取消操作：{pending.display_data.get('tool_name', '')}",
        }

    if not is_user_confirming(user_message):
        return None

    # 用户确认 → 执行真正的工作
    tool_id = pending.operation_payload.get("tool_id", "")
    tool_arguments = pending.operation_payload.get("tool_arguments", {})

    try:
        result = await _execute_critical_tool(db, tool_id, tool_arguments, user_id=user_id)
        await svc.decide(pending_id=pending.pending_id, decision="confirmed")
        return {
            "type": "confirmed",
            "result": result,
            "tool_id": tool_id,
        }
    except Exception as e:
        logger.error("[HITL·助手] 执行确认操作失败: %s", e, exc_info=True)
        await svc.decide(pending_id=pending.pending_id, decision="rejected")
        return {
            "type": "rejected",
            "message": f"操作执行失败：{e}",
        }


async def _execute_critical_tool(
    db: Any,
    tool_id: str,
    arguments: Dict[str, Any],
    *,
    user_id: str = "",
) -> str:
    """执行真正的关键工具（用户确认后调用）"""
    import inspect
    from core.tools import get_tool_registry
    registry = get_tool_registry()
    func = registry.get_function(tool_id)
    if func is None:
        raise ValueError(f"工具 {tool_id} 未注册")

    call_args = dict(arguments or {})

    # 检查工具签名：是否接受 user_id / 是否接受 **kwargs
    try:
        sig = inspect.signature(func)
        param_names = set(sig.parameters.keys())
        accepts_var_kwargs = any(
            p.kind == inspect.Parameter.VAR_KEYWORD
            for p in sig.parameters.values()
        )
    except (TypeError, ValueError):
        param_names = set()
        accepts_var_kwargs = False

    # 仅当工具签名接受 user_id 时才注入（如 remember_this 闭包）；
    # 不接受 user_id 的工具（如 trigger_stock_analysis 内部自行取当前用户）不注入，
    # 否则 func(**arguments) 会抛 TypeError
    if (
        user_id
        and "user_id" not in call_args
        and ("user_id" in param_names or accepts_var_kwargs)
    ):
        call_args["user_id"] = user_id

    # 过滤工具不接受的参数（LLM 可能编造多余参数导致 TypeError），**kwargs 除外
    if not accepts_var_kwargs and param_names:
        call_args = {k: v for k, v in call_args.items() if k in param_names}

    result = func(**call_args)
    if hasattr(result, "__await__"):
        result = await result

    return str(result) if result is not None else ""


async def list_pending_for_user(
    db: Any,
    *,
    user_id: str,
    conversation_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """列出用户待确认操作（前端展示用）"""
    svc = get_hitl_service(db)
    pending_list = await svc.list_pending(
        user_id=user_id,
        thread_id=conversation_id,
        operation_type="assistant_critical_action",
    )
    return [
        {
            "pending_id": p.pending_id,
            "tool_name": p.display_data.get("tool_name", ""),
            "display_message": p.display_data.get("display_message", ""),
            "risk_level": p.display_data.get("risk_level", "medium"),
            "reason": p.display_data.get("reason", ""),
            "arguments_preview": p.display_data.get("arguments_preview", ""),
            "created_at": p.created_at,
        }
        for p in pending_list
    ]


async def confirm_pending(
    db: Any,
    *,
    pending_id: str,
    user_id: str,
) -> Dict[str, Any]:
    """API 端点用：确认执行待确认操作"""
    svc = get_hitl_service(db)
    pending = await svc.load_pending(pending_id)
    if not pending:
        return {"success": False, "error": "操作不存在"}
    if pending.user_id != user_id:
        return {"success": False, "error": "无权操作"}
    if pending.status != "pending":
        return {"success": False, "error": f"操作已处理（状态：{pending.status}）"}

    tool_id = pending.operation_payload.get("tool_id", "")
    tool_arguments = pending.operation_payload.get("tool_arguments", {})

    try:
        result = await _execute_critical_tool(db, tool_id, tool_arguments, user_id=user_id)
        await svc.decide(pending_id=pending_id, decision="confirmed")
        return {
            "success": True,
            "result": result,
            "tool_id": tool_id,
        }
    except Exception as e:
        await svc.decide(pending_id=pending_id, decision="rejected")
        return {"success": False, "error": str(e)}


async def reject_pending(
    db: Any,
    *,
    pending_id: str,
    user_id: str,
) -> Dict[str, Any]:
    """API 端点用：拒绝执行待确认操作"""
    svc = get_hitl_service(db)
    pending = await svc.load_pending(pending_id)
    if not pending:
        return {"success": False, "error": "操作不存在"}
    if pending.user_id != user_id:
        return {"success": False, "error": "无权操作"}
    if pending.status != "pending":
        return {"success": False, "error": f"操作已处理（状态：{pending.status}）"}

    await svc.decide(pending_id=pending_id, decision="rejected")
    return {"success": True, "message": "已拒绝操作"}
