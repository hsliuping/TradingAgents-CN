import os
from typing import Any, Optional

from langchain_openai import ChatOpenAI

from .base_client import BaseLLMClient, normalize_content
from .validators import validate_model


class NormalizedChatOpenAI(ChatOpenAI):
    """ChatOpenAI wrapper that normalizes typed content blocks to text."""

    def invoke(self, input, config=None, **kwargs):
        return normalize_content(super().invoke(input, config, **kwargs))


_PASSTHROUGH_KWARGS = (
    "temperature",
    "max_tokens",
    "timeout",
    "max_retries",
    "callbacks",
    "http_client",
    "http_async_client",
)

# 🔧 默认超时时间（秒）—— 推理模型可能需要长时间思考
DEFAULT_TIMEOUT = 300
# 🔧 默认重试次数
DEFAULT_MAX_RETRIES = 2

_PROVIDER_CONFIG = {
    "deepseek": ("https://api.deepseek.com", "DEEPSEEK_API_KEY"),
    "qwen": ("https://dashscope.aliyuncs.com/compatible-mode/v1", "DASHSCOPE_API_KEY"),
    "glm": ("https://open.bigmodel.cn/api/paas/v4/", "ZHIPU_API_KEY"),
    "qianfan": ("https://qianfan.baidubce.com/v2", "QIANFAN_API_KEY"),
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    "aihubmix": ("https://aihubmix.com/v1", "AIHUBMIX_API_KEY"),
    "volcengine": ("https://ark.cn-beijing.volces.com/api/v3", "VOLCENGINE_API_KEY"),
    "volcengine_coding": ("https://ark.cn-beijing.volces.com/api/coding/v3", "VOLCENGINE_CODING_API_KEY"),
    "ollama": ("http://localhost:11434/v1", None),
    "custom_openai": (None, "CUSTOM_OPENAI_API_KEY"),
    "atlascloud": ("https://api.atlascloud.ai/v1", ("ATLASCLOUD_API_KEY", "ATLAS_CLOUD_API_KEY")),
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
            atlas_base_url = None
            if self.provider == "atlascloud" and not self.base_url:
                atlas_base_url = (
                    os.environ.get("ATLASCLOUD_API_BASE")
                    or os.environ.get("ATLASCLOUD_BASE_URL")
                    or os.environ.get("ATLAS_CLOUD_API_BASE")
                    or os.environ.get("ATLAS_CLOUD_BASE_URL")
                )
            llm_kwargs["base_url"] = self.base_url or atlas_base_url or default_base_url
            if api_key_env:
                api_key = self.kwargs.get("api_key")
                env_names = (api_key_env,) if isinstance(api_key_env, str) else api_key_env
                if not api_key:
                    api_key = next(
                        (os.environ.get(env_name) for env_name in env_names if os.environ.get(env_name)),
                        None,
                    )
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

        # 🔧 设置默认超时和重试参数
        if "timeout" not in llm_kwargs:
            llm_kwargs["timeout"] = DEFAULT_TIMEOUT
        if "max_retries" not in llm_kwargs:
            llm_kwargs["max_retries"] = DEFAULT_MAX_RETRIES

        # 🔧 reasoning_effort: 火山方舟推理模型支持，控制思考深度
        # 取值: none / minimal / low / medium / high / xhigh / max
        # 通过 model_kwargs 传递，最终会加到 API 请求体中
        model_kwargs = {}
        if "reasoning_effort" in self.kwargs and self.kwargs["reasoning_effort"]:
            model_kwargs["reasoning_effort"] = self.kwargs["reasoning_effort"]
        if model_kwargs:
            llm_kwargs["model_kwargs"] = model_kwargs

        import logging
        logger = logging.getLogger(__name__)
        logger.info(
            f"🔧 [OpenAIClient] provider={self.provider}, model={self.model}, "
            f"timeout={llm_kwargs.get('timeout')}, max_retries={llm_kwargs.get('max_retries')}"
        )
        if model_kwargs:
            logger.info(f"🔧 [OpenAIClient] model_kwargs={model_kwargs}")

        return NormalizedChatOpenAI(**llm_kwargs)

    def validate_model(self) -> bool:
        return validate_model(self.provider, self.model)
