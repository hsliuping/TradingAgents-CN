"""
智能体适配器

将现有的函数式智能体适配为 BaseAgent 子类
"""

import logging
from .legacy_adapter import LegacyAgentAdapter

logger = logging.getLogger(__name__)
from .market_analyst import MarketAnalystAgent
from .market_analyst_v2 import MarketAnalystV2
from .news_analyst import NewsAnalystAgent
from .fundamentals_analyst import FundamentalsAnalystAgent
from .fundamentals_analyst_v2 import FundamentalsAnalystAgentV2
from .social_analyst import SocialMediaAnalystAgent
from .sector_analyst import SectorAnalystAgent
from .index_analyst import IndexAnalystAgent

# v2.0 基于基类的Agent
from .bull_researcher_v2 import BullResearcherV2
from .bear_researcher_v2 import BearResearcherV2
from .research_manager_v2 import ResearchManagerV2
from .risk_manager_v2 import RiskManagerV2
from .trader_v2 import TraderV2
from .news_analyst_v2 import NewsAnalystV2
from .social_analyst_v2 import SocialMediaAnalystV2
from .sector_analyst_v2 import SectorAnalystV2
from .index_analyst_v2 import IndexAnalystV2
from .risky_analyst_v2 import RiskyAnalystV2
from .safe_analyst_v2 import SafeAnalystV2
from .neutral_analyst_v2 import NeutralAnalystV2

# 复盘相关智能体 (v1 & v2)
from .review import (
    # v1.0
    TimingAnalystAgent,
    PositionAnalystAgent,
    EmotionAnalystAgent,
    AttributionAnalystAgent,
    ReviewManagerAgent,
    # v2.0
    TimingAnalystV2,
    PositionAnalystV2,
    EmotionAnalystV2,
    AttributionAnalystV2,
    ReviewManagerV2,
)

# 持仓分析相关智能体 (v1 & v2)
from .position import (
    # v1.0
    TechnicalAnalystAgent,
    FundamentalAnalystAgent,
    RiskAssessorAgent,
    ActionAdvisorAgent,
    # v2.0
    TechnicalAnalystV2,
    FundamentalAnalystV2,
    RiskAssessorV2,
    ActionAdvisorV2,
)

__all__ = [
    "LegacyAgentAdapter",
    "MarketAnalystAgent",
    "MarketAnalystV2",
    "NewsAnalystAgent",
    "FundamentalsAnalystAgent",
    "FundamentalsAnalystAgentV2",
    "SocialMediaAnalystAgent",
    "SectorAnalystAgent",
    "IndexAnalystAgent",
    # v2.0 基于基类的Agent
    "BullResearcherV2",
    "BearResearcherV2",
    "ResearchManagerV2",
    "RiskManagerV2",
    "TraderV2",
    "NewsAnalystV2",
    "SocialMediaAnalystV2",
    "SectorAnalystV2",
    "IndexAnalystV2",
    # 复盘相关 (v1)
    "TimingAnalystAgent",
    "PositionAnalystAgent",
    "EmotionAnalystAgent",
    "AttributionAnalystAgent",
    "ReviewManagerAgent",
    # 复盘相关 (v2)
    "TimingAnalystV2",
    "PositionAnalystV2",
    "EmotionAnalystV2",
    "AttributionAnalystV2",
    "ReviewManagerV2",
    # 持仓分析相关 (v1)
    "TechnicalAnalystAgent",
    "FundamentalAnalystAgent",
    "RiskAssessorAgent",
    "ActionAdvisorAgent",
    # 持仓分析相关 (v2)
    "TechnicalAnalystV2",
    "FundamentalAnalystV2",
    "RiskAssessorV2",
    "ActionAdvisorV2",
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

