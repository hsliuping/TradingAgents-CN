"""
智能体适配器

将现有的函数式智能体适配为 BaseAgent 子类
"""

from .legacy_adapter import LegacyAgentAdapter
from .market_analyst import MarketAnalystAgent
from .news_analyst import NewsAnalystAgent
from .fundamentals_analyst import FundamentalsAnalystAgent
from .social_analyst import SocialMediaAnalystAgent

__all__ = [
    "LegacyAgentAdapter",
    "MarketAnalystAgent",
    "NewsAnalystAgent",
    "FundamentalsAnalystAgent",
    "SocialMediaAnalystAgent",
]

