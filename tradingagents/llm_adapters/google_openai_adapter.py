"""
Google Gemini 适配器（移除LangChain）
"""

import os
from typing import Optional

from tradingagents.utils.logging_manager import get_logger
from .llm_clients import GoogleGeminiClient
from .local_messages import HumanMessage

logger = get_logger('agents')


class ChatGoogleOpenAI:
    def __init__(self, model: str, google_api_key: Optional[str] = None, **kwargs):
        api_key = google_api_key or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY 未配置")
        self.model = model
        self._client = GoogleGeminiClient(model=model, api_key=api_key, **kwargs)

    def invoke(self, input):
        if isinstance(input, str):
            messages = [HumanMessage(content=input)]
        else:
            messages = input
        return self._client.invoke(messages)

    def bind_tools(self, tools):
        return self


def create_google_openai_llm(model: str, google_api_key: Optional[str] = None, **kwargs) -> ChatGoogleOpenAI:
    return ChatGoogleOpenAI(model=model, google_api_key=google_api_key, **kwargs)
