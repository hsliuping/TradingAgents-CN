"""Exact-profile provider construction; unknown providers never fall back."""

from __future__ import annotations

from contextlib import nullcontext
from typing import Any

from tradingagents.graph.trading_graph import create_llm_by_provider

from app.schemas.alphaguard.model_runtime import ModelProfile

from .model_credential_service import ModelCredentialService
from .compatible_provider_registry import CompatibleProviderRegistryService
from .model_endpoint_security import build_pinned_client, parse_registered_endpoint


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

    def _resolve_profile(self, profile: ModelProfile) -> str:
        resolver = getattr(self.credentials, "resolve_for_profile", None)
        return (
            resolver(profile)
            if resolver is not None
            else self.credentials.resolve(profile.credential_ref)
        )

    def _profile_context(self, profile: ModelProfile):
        manager = getattr(self.credentials, "profile_context", None)
        return manager(profile) if manager is not None else nullcontext()

    def create(self, profile: ModelProfile) -> Any:
        provider = profile.provider.strip().lower()
        if provider not in EXPLICIT_MODEL_PROVIDERS:
            raise UnsupportedModelProvider(
                f"provider is not explicitly supported: {provider}"
            )
        credential = self._resolve_profile(profile)
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

    async def create_registered(self, profile: ModelProfile, *, db) -> Any:
        if profile.provider_type != "OPENAI_COMPATIBLE":
            return self.create(profile)
        with self._profile_context(profile):
            registry = CompatibleProviderRegistryService(
                db,
                secret_store=getattr(self.credentials, "secret_store", None),
            )
            endpoint, model, _price, _credential = (
                await registry.resolve_profile_binding(profile)
            )
            secret = self.credentials.resolve(profile.credential_ref)
        client = build_pinned_client(
            endpoint=parse_registered_endpoint(endpoint.base_url),
            resolved_ips=endpoint.resolved_ips,
            timeout_seconds=profile.timeout_seconds,
            secret=secret,
            auth_scheme=endpoint.auth_scheme,
        )
        from tradingagents.llm_clients.openai_client import NormalizedChatOpenAI

        llm = NormalizedChatOpenAI(
            model=model.remote_model_name,
            base_url=endpoint.base_url,
            api_key=(secret if endpoint.auth_scheme == "BEARER" else "managed"),
            temperature=profile.temperature,
            max_tokens=profile.max_output_tokens,
            timeout=profile.timeout_seconds,
            max_retries=0,
            http_client=client,
            use_responses_api=(
                endpoint.api_mode == "OPENAI_RESPONSES"
            ),
        )
        # Retain the exact transport for the lifetime of the model instance.
        # This is not a Secret and is never serialized into model context.
        object.__setattr__(llm, "_alphaguard_pinned_http_client", client)
        return llm
