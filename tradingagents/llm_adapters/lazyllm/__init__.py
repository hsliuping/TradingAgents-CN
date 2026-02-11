"""
LazyLLM 适配器模块
为 TradingAgents 提供基于 LazyLLM 的统一模型接入

使用方法:
    1. 设置环境变量:
       - TRADING_QWEN_API_KEY: 阿里云 DashScope API Key
       - TRADING_DEFAULT_MODEL: 默认模型名称 (可选，默认 qwen-plus)
       - TRADING_DEFAULT_SOURCE: 默认模型来源 (可选，默认 qwen)
    
    2. 代码调用:
       from tradingagents.llm_adapters.lazyllm import TradingAutoModel, TradingLLMAdapter
       
       # 方式1: 直接使用 LazyLLM 模型
       model = TradingAutoModel()  # 自动从环境变量读取配置
       response = model("你好")
       
       # 方式2: 使用 LangChain 兼容适配器
       llm = TradingLLMAdapter()  # 自动从环境变量读取配置
       llm.invoke("你好")

环境变量前缀: TRADING_
"""

from .config import trading_config, TradingNamespace
from .adapter import TradingLLMAdapter, create_trading_llm
from .automodel import TradingAutoModel

__all__ = [
    # 配置
    "trading_config",
    "TradingNamespace",
    # 适配器
    "TradingLLMAdapter",
    "create_trading_llm",
    # AutoModel
    "TradingAutoModel",
]
