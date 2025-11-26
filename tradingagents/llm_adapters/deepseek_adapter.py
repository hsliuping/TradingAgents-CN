"""
DeepSeek 适配器（移除LangChain）
"""

import os
from typing import Optional

from tradingagents.utils.logging_manager import get_logger
from .llm_clients import UnifiedOpenAIClient
from .local_messages import HumanMessage

logger = get_logger('agents')


class ChatDeepSeek:
    def __init__(self, model: str = "deepseek-chat", api_key: Optional[str] = None,
                 base_url: str = "https://api.deepseek.com", **kwargs):
        api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY 未配置")
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


def create_deepseek_llm(model: str = "deepseek-chat", **kwargs) -> ChatDeepSeek:
    return ChatDeepSeek(model=model, **kwargs)

DeepSeekLLM = ChatDeepSeek
