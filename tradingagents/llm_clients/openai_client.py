import os
from typing import Any, Optional

from langchain_openai import ChatOpenAI

from .base_client import BaseLLMClient, normalize_content
from .validators import validate_model


class NormalizedChatOpenAI(ChatOpenAI):
    """ChatOpenAI wrapper that normalizes typed content blocks to text.

    Also preserves reasoning_content for DeepSeek V4 thinking mode compatibility.
    DeepSeek V4 requires reasoning_content to be passed back in multi-turn conversations.
    """

    def invoke(self, input, config=None, **kwargs):
        return normalize_content(super().invoke(input, config, **kwargs))

    def _create_chat_result(self, response, generation_info=None):
        """Capture reasoning_content from API response into additional_kwargs."""
        result = super()._create_chat_result(response, generation_info)

        # DeepSeek V4 returns reasoning_content in the API response message
        # LangChain's ChatOpenAI doesn't preserve it, so we inject it manually
        response_dict = response if isinstance(response, dict) else response.model_dump()
        for i, choice in enumerate(response_dict.get("choices", [])):
            msg = choice.get("message", {})
            reasoning = msg.get("reasoning_content", "")
            if reasoning and i < len(result.generations):
                result.generations[i].message.additional_kwargs["reasoning_content"] = reasoning

        return result

    def _get_request_payload(self, input_, *, stop=None, **kwargs):
        """Inject reasoning_content back into outgoing assistant messages for DeepSeek V4."""
        payload = super()._get_request_payload(input_, stop=stop, **kwargs)

        messages = input_ if isinstance(input_, list) else []
        for i, msg_dict in enumerate(payload.get("messages", [])):
            if msg_dict.get("role") == "assistant" and i < len(messages):
                original = messages[i]
                reasoning = getattr(original, "additional_kwargs", {}).get("reasoning_content")
                if reasoning:
                    msg_dict["reasoning_content"] = reasoning

        return payload


_PASSTHROUGH_KWARGS = (
    "temperature",
    "max_tokens",
    "timeout",
    "max_retries",
    "callbacks",
    "http_client",
    "http_async_client",
)

_PROVIDER_CONFIG = {
    "deepseek": ("https://api.deepseek.com", "DEEPSEEK_API_KEY"),
    "qwen": ("https://dashscope.aliyuncs.com/compatible-mode/v1", "DASHSCOPE_API_KEY"),
    "glm": ("https://open.bigmodel.cn/api/paas/v4/", "ZHIPU_API_KEY"),
    "qianfan": ("https://qianfan.baidubce.com/v2", "QIANFAN_API_KEY"),
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    "aihubmix": ("https://aihubmix.com/v1", "AIHUBMIX_API_KEY"),
    "ollama": ("http://localhost:11434/v1", None),
    "custom_openai": (None, "CUSTOM_OPENAI_API_KEY"),
}


class OpenAIClient(BaseLLMClient):
    """Client for OpenAI and OpenAI-compatible providers."""

    def __init__(
        self,
        model: str,
        base_url: Optional[str] = None,
        provider: str = "openai",
        **kwargs,
    ):
        super().__init__(model, base_url, **kwargs)
        self.provider = provider.lower()

    def get_llm(self) -> Any:
        self.warn_if_unknown_model()
        llm_kwargs = {"model": self.model}

        if self.provider in _PROVIDER_CONFIG:
            default_base_url, api_key_env = _PROVIDER_CONFIG[self.provider]
            llm_kwargs["base_url"] = self.base_url or default_base_url
            if api_key_env:
                api_key = self.kwargs.get("api_key") or os.environ.get(api_key_env)
                if api_key:
                    llm_kwargs["api_key"] = api_key
            else:
                llm_kwargs["api_key"] = "ollama"
        elif self.base_url:
            llm_kwargs["base_url"] = self.base_url
            api_key = self.kwargs.get("api_key") or os.environ.get("OPENAI_API_KEY")
            if api_key:
                llm_kwargs["api_key"] = api_key

        for key in _PASSTHROUGH_KWARGS:
            if key in self.kwargs:
                llm_kwargs[key] = self.kwargs[key]

        return NormalizedChatOpenAI(**llm_kwargs)

    def validate_model(self) -> bool:
        return validate_model(self.provider, self.model)
