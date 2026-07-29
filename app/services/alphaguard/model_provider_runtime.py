"""Exact-profile provider construction; unknown providers never fall back."""

from __future__ import annotations

from typing import Any

from tradingagents.graph.trading_graph import create_llm_by_provider

from app.schemas.alphaguard.model_runtime import ModelProfile

from .model_credential_service import ModelCredentialService


EXPLICIT_MODEL_PROVIDERS = frozenset(
    {
        "openai",
        "siliconflow",
        "openrouter",
        "aihubmix",
        "volcengine",
        "volcengine_coding",
        "ollama",
        "deepseek",
        "qwen",
        "glm",
        "custom_openai",
        "qianfan",
        "google",
        "anthropic",
    }
)


class UnsupportedModelProvider(ValueError):
    pass


class ModelProviderRuntime:
    def __init__(self, credential_service: ModelCredentialService | None = None):
        self.credentials = credential_service or ModelCredentialService()

    def create(self, profile: ModelProfile) -> Any:
        provider = profile.provider.strip().lower()
        if provider not in EXPLICIT_MODEL_PROVIDERS:
            raise UnsupportedModelProvider(
                f"provider is not explicitly supported: {provider}"
            )
        credential = self.credentials.resolve(profile.credential_ref)
        return create_llm_by_provider(
            provider=provider,
            model=profile.model_name,
            backend_url=profile.base_url or "",
            temperature=profile.temperature,
            max_tokens=profile.max_output_tokens,
            timeout=profile.timeout_seconds,
            api_key=credential,
            # Retries are performed by invoke_json_object so each provider
            # attempt receives a separate immutable audit record.
            max_retries=0,
        )
