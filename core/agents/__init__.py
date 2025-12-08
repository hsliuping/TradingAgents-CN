"""
智能体系统模块

提供统一的智能体基类、注册表和工厂
"""

from .base import BaseAgent
from .registry import AgentRegistry, get_registry, register_agent
from .factory import AgentFactory, create_agent
from .config import AgentMetadata, AgentConfig, AgentCategory, LicenseTier, BUILTIN_AGENTS

__all__ = [
    # 基类
    "BaseAgent",
    # 注册表
    "AgentRegistry",
    "get_registry",
    "register_agent",
    # 工厂
    "AgentFactory",
    "create_agent",
    # 配置
    "AgentMetadata",
    "AgentConfig",
    "AgentCategory",
    "LicenseTier",
    "BUILTIN_AGENTS",
]

