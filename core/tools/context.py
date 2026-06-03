"""
工具执行上下文管理

使用 Python contextvars 在异步调用链中传递用户上下文，
使操作类工具（assistant_ops）能获取当前用户身份，而无需在工具签名中暴露 user_id。
"""

import contextvars
from typing import Any, Dict, Optional

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

