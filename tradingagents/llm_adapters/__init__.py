# LLM Adapters for TradingAgents
from .dashscope_openai_adapter import ChatDashScopeOpenAI
from .google_openai_adapter import ChatGoogleOpenAI

# LazyLLM 适配器（延迟导入，避免依赖问题）
def get_lazyllm_adapter():
    """
    获取 LazyLLM 适配器
    
    使用示例:
        TradingLLMAdapter, create_trading_llm = get_lazyllm_adapter()
        llm = create_trading_llm()
    """
    from .lazyllm import TradingLLMAdapter, create_trading_llm
    return TradingLLMAdapter, create_trading_llm


__all__ = [
    # 原有适配器
    "ChatDashScopeOpenAI", 
    "ChatGoogleOpenAI",
    # LazyLLM 适配器
    "get_lazyllm_adapter",
]
