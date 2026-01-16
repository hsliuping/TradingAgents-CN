"""
LLM 提供商适配器模块

每个适配器负责将统一接口转换为特定提供商的 API 格式
"""

from .base import BaseAdapter
from .openai_compat import OpenAICompatAdapter

# Google 适配器是可选的（需要 google-generativeai 包）
try:
    from .google import GoogleAdapter
    GOOGLE_AVAILABLE = True
except ImportError:
    GoogleAdapter = None
    GOOGLE_AVAILABLE = False

__all__ = [
    "BaseAdapter",
    "OpenAICompatAdapter",
]

if GOOGLE_AVAILABLE:
    __all__.append("GoogleAdapter")

