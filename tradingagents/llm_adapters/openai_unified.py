import os
from typing import Optional

from tradingagents.utils.logging_manager import get_logger
from .llm_clients import UnifiedOpenAIClient
from .local_messages import HumanMessage

logger = get_logger('agents')


class ChatCustomOpenAI:
    def __init__(self, model: str, api_key: Optional[str] = None, base_url: Optional[str] = None, **kwargs):
        api_key = api_key or os.getenv("OPENAI_API_KEY") or os.getenv("CUSTOM_OPENAI_API_KEY")
        base_url = base_url or os.getenv("CUSTOM_OPENAI_BASE_URL") or "https://api.openai.com/v1"
        if not api_key:
            raise ValueError("OpenAI API Key 未配置")
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


PROVIDER_BASE_URLS = {
    "deepseek": "https://api.deepseek.com",
    "dashscope": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "zhipu": "https://open.bigmodel.cn/api/paas/v4",
    "openai": "https://api.openai.com/v1",
}

PROVIDER_ENV_KEYS = {
    "deepseek": "DEEPSEEK_API_KEY",
    "dashscope": "DASHSCOPE_API_KEY",
    "zhipu": "ZHIPU_API_KEY",
    "openai": "OPENAI_API_KEY",
}


def create_openai_compatible_llm(provider: str, model: str, api_key: Optional[str] = None,
                                 base_url: Optional[str] = None, **kwargs):
    env_key = PROVIDER_ENV_KEYS.get(provider, "OPENAI_API_KEY")
    api_key = api_key or os.getenv(env_key)
    base_url = base_url or PROVIDER_BASE_URLS.get(provider, "https://api.openai.com/v1")
    return ChatCustomOpenAI(model=model, api_key=api_key, base_url=base_url, **kwargs)
