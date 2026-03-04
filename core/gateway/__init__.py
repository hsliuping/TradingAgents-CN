"""
Gateway 模块 — IM 平台双向接入框架

提供统一的消息模型、适配器基类、路由分发和会话管理，
让飞书/QQ/钉钉等 IM 平台的用户能直接与分析助理对话。

核心组件：
- models.py       统一消息模型（GatewayMessage / GatewayResponse）
- router.py       GatewayRouter 路由分发（选择适配器、调用助理、回复）
- session.py      多通道 Session 管理
- user_mapping.py IM 用户 → 系统用户映射
- adapters/       各平台适配器实现
"""

from core.gateway.models import (
    ChannelType,
    GatewayMessage,
    GatewayResponse,
    MessageType,
    ResponseType,
    UserMapping,
)
from core.gateway.adapters.base import BaseGatewayAdapter
from core.gateway.session import SessionManager
from core.gateway.user_mapping import UserMappingManager

__all__ = [
    "ChannelType",
    "GatewayMessage",
    "GatewayResponse",
    "MessageType",
    "ResponseType",
    "UserMapping",
    "BaseGatewayAdapter",
    "SessionManager",
    "UserMappingManager",
]

