"""
智能体适配器

将现有的函数式智能体适配为 BaseAgent 子类
"""

import logging
from .legacy_adapter import LegacyAgentAdapter

logger = logging.getLogger(__name__)
from .market_analyst import MarketAnalystAgent
from .news_analyst import NewsAnalystAgent
from .fundamentals_analyst import FundamentalsAnalystAgent
from .social_analyst import SocialMediaAnalystAgent
from .sector_analyst import SectorAnalystAgent
from .index_analyst import IndexAnalystAgent

# 复盘相关智能体
from .review import (
    TimingAnalystAgent,
    PositionAnalystAgent,
    EmotionAnalystAgent,
    AttributionAnalystAgent,
    ReviewManagerAgent,
)

# 持仓分析相关智能体
from .position import (
    TechnicalAnalystAgent,
    FundamentalAnalystAgent,
    RiskAssessorAgent,
    ActionAdvisorAgent,
)

__all__ = [
    "LegacyAgentAdapter",
    "MarketAnalystAgent",
    "NewsAnalystAgent",
    "FundamentalsAnalystAgent",
    "SocialMediaAnalystAgent",
    "SectorAnalystAgent",
    "IndexAnalystAgent",
    # 复盘相关
    "TimingAnalystAgent",
    "PositionAnalystAgent",
    "EmotionAnalystAgent",
    "AttributionAnalystAgent",
    "ReviewManagerAgent",
    # 持仓分析相关
    "TechnicalAnalystAgent",
    "FundamentalAnalystAgent",
    "RiskAssessorAgent",
    "ActionAdvisorAgent",
]


# ============================================================
# 自动注册新分析师到 AnalystRegistry
# ============================================================

def _register_new_analysts():
    """
    注册新的分析师到 AnalystRegistry

    这些分析师不需要工具调用循环，直接执行并返回结果
    """
    from ..analyst_registry import get_analyst_registry
    from ..config import BUILTIN_AGENTS

    registry = get_analyst_registry()

    # 注册板块分析师
    if "sector_analyst" in BUILTIN_AGENTS:
        registry.register(
            "sector_analyst",
            agent_class=SectorAnalystAgent,
            metadata=BUILTIN_AGENTS["sector_analyst"],
            override=True
        )

    # 注册大盘分析师
    if "index_analyst" in BUILTIN_AGENTS:
        registry.register(
            "index_analyst",
            agent_class=IndexAnalystAgent,
            metadata=BUILTIN_AGENTS["index_analyst"],
            override=True
        )

    # 注册复盘相关智能体到 AnalystRegistry
    review_agents = [
        ("timing_analyst", TimingAnalystAgent),
        ("position_analyst", PositionAnalystAgent),
        ("emotion_analyst", EmotionAnalystAgent),
        ("attribution_analyst", AttributionAnalystAgent),
        ("review_manager", ReviewManagerAgent),
    ]

    for agent_id, agent_class in review_agents:
        if agent_id in BUILTIN_AGENTS:
            registry.register(
                agent_id,
                agent_class=agent_class,
                metadata=BUILTIN_AGENTS[agent_id],
                override=True
            )

    # 注册持仓分析相关智能体到 AnalystRegistry
    position_agents = [
        ("pa_technical", TechnicalAnalystAgent),
        ("pa_fundamental", FundamentalAnalystAgent),
        ("pa_risk", RiskAssessorAgent),
        ("pa_advisor", ActionAdvisorAgent),
    ]

    for agent_id, agent_class in position_agents:
        if agent_id in BUILTIN_AGENTS:
            registry.register(
                agent_id,
                agent_class=agent_class,
                metadata=BUILTIN_AGENTS[agent_id],
                override=True
            )

    # 同时注册到 AgentRegistry（用于工作流引擎）
    from ..registry import get_registry
    agent_registry = get_registry()

    all_workflow_agents = review_agents + position_agents
    for agent_id, agent_class in all_workflow_agents:
        if agent_id in BUILTIN_AGENTS:
            try:
                agent_registry.register(agent_class, override=True)
                logger.info(f"✅ [AgentRegistry] 注册智能体: {agent_id}")
            except Exception as e:
                logger.warning(f"⚠️ [AgentRegistry] 注册失败 {agent_id}: {e}")


# 模块加载时自动注册
_register_new_analysts()

