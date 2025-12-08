"""
统一 LLM 客户端模块

提供统一的 LLM 调用接口，支持多种后端：
- OpenAI 兼容 API (DeepSeek, 通义千问, 智谱AI, 硅基流动等)
- Google Generative AI
- Anthropic Claude

主要组件:
- UnifiedLLMClient: 统一客户端入口
- LLMConfig: 配置模型
- ToolCallNormalizer: 工具调用标准化
"""

from .models import LLMConfig, LLMResponse, Message, ToolCall, ToolResult
from .unified_client import UnifiedLLMClient
from .tool_normalizer import ToolCallNormalizer

__all__ = [
    "UnifiedLLMClient",
    "LLMConfig",
    "LLMResponse",
    "Message",
    "ToolCall",
    "ToolResult",
    "ToolCallNormalizer",
]

