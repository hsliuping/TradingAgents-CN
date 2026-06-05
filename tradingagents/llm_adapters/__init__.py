# LLM Adapters for TradingAgents
from .dashscope_openai_adapter import ChatDashScopeOpenAI

try:
    from .google_openai_adapter import ChatGoogleOpenAI
except ImportError:
    ChatGoogleOpenAI = None

from .minimax_adapter import ChatMiniMax

__all__ = ["ChatDashScopeOpenAI", "ChatGoogleOpenAI", "ChatMiniMax"]
