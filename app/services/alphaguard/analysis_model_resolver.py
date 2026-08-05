"""Resolve legacy analysis models from the active AlphaGuard registry."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
import re
from typing import Callable

from pymongo import MongoClient

from app.core.config import settings
from app.schemas.alphaguard.model_runtime import ModelProfile

from .model_credential_service import (
    CredentialNotConfigured,
    ModelCredentialService,
)
from .model_profile_registry import ModelProfileRegistry


logger = logging.getLogger("app.services.alphaguard.analysis_model_resolver")

ANALYSIS_MODEL_SELECTOR_PREFIX = "alphaguard-profile:"
_SELECTOR_PATTERN = re.compile(
    r"^alphaguard-profile:([^@\s]+)@([^@\s]+)$"
)


class AnalysisModelConfigurationError(RuntimeError):
    """The secure registry cannot provide a usable analysis model pair."""


@dataclass(frozen=True)
class ResolvedAnalysisModel:
    profile: ModelProfile
    provider: str
    backend_url: str
    api_key: str = field(repr=False)

    @property
    def selector(self) -> str:
        return model_profile_selector(self.profile)

    @property
    def provider_info(self) -> dict:
        return {
            "provider": self.provider,
            "backend_url": self.backend_url,
            "api_key": self.api_key,
        }

    @property
    def model_config(self) -> dict:
        return {
            "max_tokens": self.profile.max_output_tokens,
            "temperature": self.profile.temperature,
            "timeout": self.profile.timeout_seconds,
            "retry_times": self.profile.max_retries,
        }


@dataclass(frozen=True)
class ResolvedAnalysisModelPair:
    quick: ResolvedAnalysisModel
    deep: ResolvedAnalysisModel


def model_profile_selector(profile: ModelProfile) -> str:
    return (
        f"{ANALYSIS_MODEL_SELECTOR_PREFIX}{profile.profile_id}"
        f"@{profile.profile_version}"
    )


def parse_model_profile_selector(value: str) -> tuple[str, str]:
    match = _SELECTOR_PATTERN.fullmatch(str(value or "").strip())
    if match is None:
        raise AnalysisModelConfigurationError("分析模型选择格式无效，请刷新页面后重试")
    return match.group(1), match.group(2)


class AnalysisModelResolver:
    """Synchronous adapter for the thread-based TradingAgents runtime."""

    def __init__(
        self,
        *,
        client_factory: Callable[..., object] = MongoClient,
        credential_service: ModelCredentialService | None = None,
        mongo_uri: str | None = None,
        mongo_db: str | None = None,
    ):
        self.client_factory = client_factory
        self.credentials = credential_service or ModelCredentialService()
        self.mongo_uri = mongo_uri or settings.MONGO_URI
        self.mongo_db = mongo_db or settings.MONGO_DB

    @staticmethod
    def _requested_identity(
        selector: str | None,
    ) -> tuple[str, str] | None:
        value = str(selector or "").strip()
        if not value:
            return None
        if not value.startswith(ANALYSIS_MODEL_SELECTOR_PREFIX):
            logger.warning(
                "Ignoring legacy analysis model name; using the active "
                "AlphaGuard profile"
            )
            return None
        return parse_model_profile_selector(value)

    @staticmethod
    def _active_identity(db, role: str) -> tuple[str, str]:
        assignment = db["ag_model_profile_assignments"].find_one(
            {"role": role, "status": "ACTIVE"},
            sort=[("assigned_at", -1)],
        )
        if assignment is not None:
            return (
                str(assignment["profile_id"]),
                str(assignment["profile_version"]),
            )

        try:
            defined = ModelProfileRegistry().for_role(role)
        except Exception as exc:
            raise AnalysisModelConfigurationError(
                f"{role} 尚未绑定可用模型，请先在模型与 API 中完成配置"
            ) from exc
        return defined.profile_id, defined.profile_version

    @staticmethod
    def _profile(db, role: str, selector: str | None) -> ModelProfile:
        active_identity = AnalysisModelResolver._active_identity(db, role)
        requested_identity = AnalysisModelResolver._requested_identity(selector)
        if requested_identity is not None and requested_identity != active_identity:
            raise AnalysisModelConfigurationError(
                "分析模型配置已更新，请刷新页面后重新提交"
            )

        raw = db["ag_model_profiles"].find_one(
            {
                "profile_id": active_identity[0],
                "profile_version": active_identity[1],
            }
        )
        if raw is None:
            raise AnalysisModelConfigurationError(
                f"{role} 的模型档案未完成持久化，请先在模型与 API 中完成配置"
            )
        try:
            profile = ModelProfile.model_validate(
                {key: value for key, value in raw.items() if key != "_id"}
            )
        except Exception as exc:
            raise AnalysisModelConfigurationError(
                f"{role} 的模型档案无效，请在模型与 API 中重新配置"
            ) from exc
        if profile.role != role or not profile.enabled or not profile.research_allowed:
            raise AnalysisModelConfigurationError(
                f"{role} 当前未启用分析权限，请在模型与 API 中检查配置"
            )

        latest_check = db["ag_model_capability_checks"].find_one(
            {
                "profile_id": profile.profile_id,
                "profile_version": profile.profile_version,
            },
            sort=[("checked_at", -1)],
        )
        if not latest_check or latest_check.get("status") != "READY":
            raise AnalysisModelConfigurationError(
                f"{role} 模型尚未通过能力检测，请先在模型与 API 中完成检测"
            )
        return profile

    def _resolve(self, db, role: str, selector: str | None) -> ResolvedAnalysisModel:
        profile = self._profile(db, role, selector)
        if profile.provider_type == "OPENAI_COMPATIBLE":
            if profile.auth_scheme != "BEARER":
                raise AnalysisModelConfigurationError(
                    "当前分析引擎暂不支持该模型端点的认证方式"
                )
            provider = "custom_openai"
        else:
            provider = profile.provider.strip().lower()

        try:
            api_key = self.credentials.resolve_for_profile(profile)
        except CredentialNotConfigured as exc:
            raise AnalysisModelConfigurationError(
                f"{role} 的 API 凭据不可用，请在模型与 API 中重新验证"
            ) from exc

        backend_url = str(profile.base_url or "").strip()
        if not backend_url:
            raise AnalysisModelConfigurationError(
                f"{role} 的模型端点未配置"
            )
        return ResolvedAnalysisModel(
            profile=profile,
            provider=provider,
            backend_url=backend_url,
            api_key=api_key,
        )

    def resolve_pair(
        self,
        *,
        quick_selector: str | None,
        deep_selector: str | None,
    ) -> ResolvedAnalysisModelPair:
        client = self.client_factory(self.mongo_uri)
        try:
            db = client[self.mongo_db]
            quick = self._resolve(db, "RESEARCH_AGENT", quick_selector)
            deep = self._resolve(db, "TOP_RISK_REVIEWER", deep_selector)
            return ResolvedAnalysisModelPair(quick=quick, deep=deep)
        finally:
            client.close()


def resolve_analysis_model_pair_sync(
    *,
    quick_selector: str | None,
    deep_selector: str | None,
) -> ResolvedAnalysisModelPair:
    return AnalysisModelResolver().resolve_pair(
        quick_selector=quick_selector,
        deep_selector=deep_selector,
    )
