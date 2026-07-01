"""
工具执行上下文管理

使用 Python contextvars 在异步调用链中传递用户上下文，
使操作类工具（assistant_ops）能获取当前用户身份，而无需在工具签名中暴露 user_id。
"""

import contextvars
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# 🔒 按 thread_id 隔离的 intent 存储（替代不稳定的 contextvar）
# contextvar 在 LangChain/LLM provider 的工具调用链中会被静默回退，
# 因此用模块级 dict + thread_id 索引来可靠传递 intent 变化。
_nanobot_intents_by_thread: Dict[str, Dict[str, Any]] = {}

# 当前用户 ID（在 IntelligentAssistantService.chat 入口设置）
_current_user_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    'current_user_id', default=None
)

# 当前 IM 渠道信息（在 GatewayRouter._invoke_assistant 入口设置）
# 格式: {"channel_type": "qq", "channel_id": "c2c:xxx"}
_current_im_channel: contextvars.ContextVar[Optional[Dict[str, str]]] = contextvars.ContextVar(
    'current_im_channel', default=None
)

# 当前智能助手主题 ID（在 IntelligentAssistantService.chat 入口设置）
_current_assistant_thread_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    'current_assistant_thread_id', default=None
)

# 当前智能助手线程上下文（用于工具调用期读取前端当前选中的对象，如 Agent 工坊 spec/version）
_current_assistant_thread_context: contextvars.ContextVar[Optional[Dict[str, Any]]] = contextvars.ContextVar(
    'current_assistant_thread_context', default=None
)

# 当前分析数据源（在 Agent 工具调用前设置）
_current_analysis_data_source: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    'current_analysis_data_source', default=None
)


def set_current_user_id(user_id: str) -> contextvars.Token:
    """设置当前用户 ID

    Args:
        user_id: 用户 ID 字符串

    Returns:
        contextvars.Token，可用于 reset
    """
    return _current_user_id.set(user_id)


def get_current_user_id() -> Optional[str]:
    """获取当前用户 ID

    Returns:
        当前用户 ID，未设置时返回 None
    """
    return _current_user_id.get()


def require_current_user_id() -> str:
    """获取当前用户 ID，未设置时抛出异常

    Returns:
        当前用户 ID

    Raises:
        RuntimeError: 未在上下文中设置用户 ID
    """
    user_id = _current_user_id.get()
    if user_id is None:
        raise RuntimeError(
            "当前上下文中未设置 user_id。"
            "请确保在 IntelligentAssistantService.chat() 入口调用了 set_current_user_id()。"
        )
    return user_id


def set_current_im_channel(channel_type: str, channel_id: str) -> contextvars.Token:
    """设置当前 IM 渠道信息（由 GatewayRouter 在处理消息时调用）

    Args:
        channel_type: 平台类型，如 "qq"、"feishu"
        channel_id:   平台侧会话 ID，如 "c2c:openid"、"group:group_openid"

    Returns:
        contextvars.Token，可用于 reset
    """
    return _current_im_channel.set({"channel_type": channel_type, "channel_id": channel_id})


def get_current_im_channel() -> Optional[Dict[str, str]]:
    """获取当前 IM 渠道信息

    Returns:
        {"channel_type": "qq", "channel_id": "c2c:xxx"} 或 None（非 IM 渠道）
    """
    return _current_im_channel.get()


def set_current_assistant_thread_id(thread_id: Optional[str]) -> contextvars.Token:
    """设置当前智能助手主题 ID"""
    return _current_assistant_thread_id.set(thread_id)


def get_current_assistant_thread_id() -> Optional[str]:
    """获取当前智能助手主题 ID"""
    return _current_assistant_thread_id.get()


def set_current_assistant_thread_context(thread_context: Optional[Dict[str, Any]]) -> contextvars.Token:
    """设置当前智能助手线程上下文。"""
    clean_context = dict(thread_context or {}) if isinstance(thread_context, dict) else None
    return _current_assistant_thread_context.set(clean_context)


def get_current_assistant_thread_context() -> Dict[str, Any]:
    """获取当前智能助手线程上下文。"""
    return dict(_current_assistant_thread_context.get() or {})


def set_current_analysis_data_source(data_source: Optional[str]) -> contextvars.Token:
    """设置当前分析数据源。

    Args:
        data_source: 数据源名称，如 "qmt"、"tushare"

    Returns:
        contextvars.Token，可用于 reset
    """
    normalized = None
    if isinstance(data_source, str):
        text = data_source.strip().lower()
        normalized = text or None
    return _current_analysis_data_source.set(normalized)


def reset_current_analysis_data_source(token: contextvars.Token) -> None:
    """重置当前分析数据源。"""
    _current_analysis_data_source.reset(token)


def get_current_analysis_data_source() -> Optional[str]:
    """获取当前分析数据源。"""
    return _current_analysis_data_source.get()


# ── 独立于 contextvar 的 Nanobot Intent 存储 ──
# contextvar 在异步工具调用中可能被 Task 边界隔离/覆盖，因此使用模块级 dict 作为兜底。
# 写入路径：update_intent_context_in_thread() 同时写到这里
# 读取路径：service.chat() persist 前读取
#
# 🔒 治理规则（来自 nanobot-memory-governance-design.md）：
# - contextvar 只作为同进程内的加速缓存，不可作为跨轮唯一来源。
# - 模块级 dict 按 thread_id 隔离，作为持久化前的可靠来源。
# - 每轮对话结束时，embedded_nanobot_service.py 从此处读取 intent 并合并到 thread_context。
# - 禁止在工具调用链内部通过 contextvar 隐式写入后不复写回模块级 dict。

def set_latest_nanobot_intent(intent_dict: Dict[str, Any]) -> None:
    """存储最新的 Nanobot intent（按 thread_id 隔离）。

    每次工具调用完成后，应将当前 intent 写入此处。
    这是跨轮持久化的唯一可靠来源。
    """
    thread_id = _current_assistant_thread_id.get() or "unknown"
    _nanobot_intents_by_thread[thread_id] = dict(intent_dict)
    logger.debug(
        "[IntentStore] set_latest_nanobot_intent thread_id=%s stage=%s action=%s spec_id=%s",
        thread_id,
        intent_dict.get("stage", "-"),
        intent_dict.get("action", "-"),
        intent_dict.get("spec_id", "-"),
    )


def get_latest_nanobot_intent() -> Dict[str, Any]:
    """读取最新 Nanobot intent（按 thread_id 隔离）。"""
    thread_id = _current_assistant_thread_id.get() or "unknown"
    return _nanobot_intents_by_thread.get(thread_id, {})


def clear_latest_nanobot_intent() -> None:
    """清除当前线程的 Nanobot intent。"""
    thread_id = _current_assistant_thread_id.get() or "unknown"
    _nanobot_intents_by_thread.pop(thread_id, None)

