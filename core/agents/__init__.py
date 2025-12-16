"""
智能体系统模块

提供统一的智能体基类、注册表和工厂

v2.0 新特性:
- 支持动态工具绑定
- 支持 LangChain LLM 集成
"""

from .base import BaseAgent
from .registry import AgentRegistry, get_registry, register_agent
from .factory import AgentFactory, create_agent, create_agent_with_dynamic_tools
from .config import AgentMetadata, AgentConfig, AgentCategory, LicenseTier, BUILTIN_AGENTS

# v2.0 新增：Agent基类
from .analyst import AnalystAgent
from .researcher import ResearcherAgent
from .manager import ManagerAgent
from .trader import TraderAgent
from .post_processor import PostProcessorAgent

# 导入后处理Agent实现（触发注册）
from .post_processors import (
    ReportSaverAgent,
    EmailNotifierAgent,
    SystemNotifierAgent,
)

# 导入v2.0 Agent实现（触发注册）
from .adapters import (
    # 分析师
    FundamentalsAnalystAgentV2,
    NewsAnalystV2,
    SocialMediaAnalystV2,
    SectorAnalystV2,
    IndexAnalystV2,
    # 研究员
    BullResearcherV2,
    BearResearcherV2,
    # 管理者
    ResearchManagerV2,
    RiskManagerV2,
    # 交易员
    TraderV2,
    # 风险分析师
    RiskyAnalystV2,
    SafeAnalystV2,
    NeutralAnalystV2,
)

__all__ = [
    # 基类
    "BaseAgent",
    # v2.0 Agent基类
    "AnalystAgent",
    "ResearcherAgent",
    "ManagerAgent",
    "TraderAgent",
    "PostProcessorAgent",
    # 后处理Agent
    "ReportSaverAgent",
    "EmailNotifierAgent",
    "SystemNotifierAgent",
    # 注册表
    "AgentRegistry",
    "get_registry",
    "register_agent",
    # 工厂
    "AgentFactory",
    "create_agent",
    "create_agent_with_dynamic_tools",  # v2.0
    # 配置
    "AgentMetadata",
    "AgentConfig",
    "AgentCategory",
    "LicenseTier",
    "BUILTIN_AGENTS",
]

