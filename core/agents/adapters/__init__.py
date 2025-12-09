"""
智能体适配器

将现有的函数式智能体适配为 BaseAgent 子类
"""

from .legacy_adapter import LegacyAgentAdapter
from .market_analyst import MarketAnalystAgent
from .news_analyst import NewsAnalystAgent
from .fundamentals_analyst import FundamentalsAnalystAgent
from .social_analyst import SocialMediaAnalystAgent
from .sector_analyst import SectorAnalystAgent
from .index_analyst import IndexAnalystAgent

__all__ = [
    "LegacyAgentAdapter",
    "MarketAnalystAgent",
    "NewsAnalystAgent",
    "FundamentalsAnalystAgent",
    "SocialMediaAnalystAgent",
    "SectorAnalystAgent",
    "IndexAnalystAgent",
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


# 模块加载时自动注册
_register_new_analysts()

