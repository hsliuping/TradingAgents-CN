"""
LLM 适配器模板 - 适用于 OpenAI 兼容提供商

使用方式：复制本文件为 tradingagents/llm_adapters/{provider}_adapter.py，
并根据目标提供商修改 provider_name、base_url、API Key 环境变量等信息。
"""

from typing import Any, Dict
import os
import logging

from tradingagents.llm_adapters.openai_compatible_base import OpenAICompatibleBase

logger = logging.getLogger(__name__)


class ChatProviderTemplate(OpenAICompatibleBase):
    """{ProviderDisplayName} OpenAI 兼容适配器"""

    def __init__(
        self,
        model: str = "{default-model-name}",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        timeout: int = 120,
        **kwargs: Any,
    ) -> None:
        """初始化 {ProviderDisplayName} OpenAI 兼容客户端"""
        super().__init__(
            provider_name="{provider}",
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key_env_var="{PROVIDER_API_KEY}",
            base_url="{https://api.provider.com/v1}",
            request_timeout=timeout,
            **kwargs,
        )
        logger.info("✅ {ProviderDisplayName} OpenAI 兼容适配器初始化成功")


# 供 openai_compatible_base.py 注册参考
PROVIDER_TEMPLATE_MODELS: Dict[str, Dict[str, Any]] = {
    "{default-model-name}": {"context_length": 8192, "supports_function_calling": True},
    "{advanced-model-name}": {"context_length": 32768, "supports_function_calling": True},
}