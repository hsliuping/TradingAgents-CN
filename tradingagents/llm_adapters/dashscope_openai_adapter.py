"""
DashScope OpenAI 兼容适配器（移除LangChain）
"""

import os
from typing import Any, Dict, Optional

from tradingagents.utils.logging_manager import get_logger
from .llm_clients import UnifiedOpenAIClient
from .local_messages import HumanMessage

logger = get_logger('agents')


class ChatDashScopeOpenAI:
    def __init__(self, model: str = "qwen-turbo", api_key: Optional[str] = None, base_url: Optional[str] = None,
                 **kwargs):
        api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
        base_url = base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1"
        if not api_key:
            raise ValueError("DASHSCOPE_API_KEY 未配置")
        self.model = model
        self._client = UnifiedOpenAIClient(model=model, api_key=api_key, base_url=base_url, **kwargs)

    def invoke(self, input):
        if isinstance(input, str):
            messages = [HumanMessage(content=input)]
        else:
            messages = input
        return self._client.invoke(messages)

    def bind_tools(self, tools):
        return self


def create_dashscope_openai_llm(model: str = "qwen-plus-latest", api_key: Optional[str] = None,
                                **kwargs) -> ChatDashScopeOpenAI:
    return ChatDashScopeOpenAI(model=model, api_key=api_key, **kwargs)
