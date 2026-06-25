"""
Agent Builder Provider 抽象层

提供统一的 Agent 构建器接口，支持：
- EmbeddedNanobotBuilderProvider：当前主力，封装 EmbeddedNanobotRuntime
- LLMBuilderProvider：回退/测试实现，直接调用 LLM
- HermesBuilderProvider：预留，未来通过 Provider 切换

AgentWorkshopService 通过 provider 进行需求澄清、缺口分析、工具规划，
不再直接关心底层构建器实现。
"""

from app.services.agent_builders.base import (
    AgentBuilderDraft,
    AgentBuilderProvider,
)

__all__ = [
    "AgentBuilderDraft",
    "AgentBuilderProvider",
]
