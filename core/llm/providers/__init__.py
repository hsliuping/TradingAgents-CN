"""
LLM 提供商适配器模块

每个适配器负责将统一接口转换为特定提供商的 API 格式
"""

from .base import BaseAdapter
from .openai_compat import OpenAICompatAdapter
from .google import GoogleAdapter

__all__ = [
    "BaseAdapter",
    "OpenAICompatAdapter",
    "GoogleAdapter",
]

