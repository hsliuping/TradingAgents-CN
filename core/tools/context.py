"""
工具执行上下文管理

使用 Python contextvars 在异步调用链中传递用户上下文，
使操作类工具（assistant_ops）能获取当前用户身份，而无需在工具签名中暴露 user_id。
"""

import contextvars
from typing import Optional

# 当前用户 ID（在 IntelligentAssistantService.chat 入口设置）
_current_user_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    'current_user_id', default=None
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

