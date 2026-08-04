"""Exact-profile, read-only bridge from containers to host Keychain."""

from __future__ import annotations

from hmac import compare_digest
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.alphaguard.model_runtime import ModelProfile

from .compatible_provider_registry import CompatibleProviderRegistryService
from .credential_host_runtime import (
    CREDENTIAL_HOST_TOKEN_HEADER,
    read_credential_host_token,
)
from .model_profile_registry import ModelProfileRegistry
from .model_secret_store import (
    KEYCHAIN_ALIAS_SERVICE,
    SecretNotFound,
    SecretStore,
    SecretStoreError,
    keychain_ref,
)


AUTHORIZED_MODEL_ROLES = (
    "RESEARCH_AGENT",
    "NORMAL_TRADER",
    "TOP_RISK_REVIEWER",
)


class CredentialHostAuthorizationError(RuntimeError):
    pass


class CredentialHostReadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    service: str = Field(min_length=1, max_length=200)
    account: str = Field(min_length=1, max_length=200)
    profile: dict[str, Any] | None = None


class CredentialHostReadResponse(BaseModel):
    status: str = "READY"
    value: str


def _profile_context(profile: ModelProfile) -> dict[str, Any]:
    return {
        "role": profile.role,
        "profile_id": profile.profile_id,
        "profile_version": profile.profile_version,
        "config_hash": profile.config_hash,
        "credential_ref": profile.credential_ref,
        "endpoint_profile_id": profile.endpoint_profile_id,
        "endpoint_profile_version": profile.endpoint_profile_version,
        "endpoint_model_id": profile.endpoint_model_id,
        "endpoint_model_version": profile.endpoint_model_version,
    }


class CredentialHostBroker:
    """Authorize each Keychain read against active persisted profiles."""

    def __init__(self, db, *, secret_store: SecretStore):
        self.db = db
        self.secret_store = secret_store
        self.profiles = ModelProfileRegistry(db)

    async def _active_profiles(self) -> list[ModelProfile]:
        profiles = []
        for role in AUTHORIZED_MODEL_ROLES:
            try:
                profiles.append(await self.profiles.persisted_for_role(role))
            except Exception:
                continue
        return profiles

    def _alias_target(self, profile: ModelProfile) -> str | None:
        reference = str(profile.credential_ref or "")
        if not reference.startswith("keychain-alias:"):
            return None
        alias = reference.removeprefix("keychain-alias:")
        try:
            target = self.secret_store.read(
                service=KEYCHAIN_ALIAS_SERVICE,
                account=alias,
            )
        except (SecretNotFound, SecretStoreError):
            return None
        return target if target.startswith("keychain:") else None

    async def _validate_profile(self, profile: ModelProfile) -> None:
        if profile.role not in AUTHORIZED_MODEL_ROLES or not profile.enabled:
            raise CredentialHostAuthorizationError(
                "model profile is not authorized for runtime credentials"
            )
        persisted = await self.profiles.persisted(
            profile.profile_id,
            profile.profile_version,
        )
        if persisted.config_hash != profile.config_hash:
            raise CredentialHostAuthorizationError(
                "model profile binding does not match persisted state"
            )
        if profile.provider_type == "OPENAI_COMPATIBLE":
            await CompatibleProviderRegistryService(
                self.db,
                secret_store=self.secret_store,
            ).resolve_profile_binding(profile)

    async def _requested_profile(
        self,
        context: dict[str, Any],
    ) -> ModelProfile:
        role = str(context.get("role") or "")
        if role not in AUTHORIZED_MODEL_ROLES:
            raise CredentialHostAuthorizationError(
                "model profile role is not authorized"
            )
        profile = await self.profiles.persisted_for_role(role)
        expected = _profile_context(profile)
        if any(context.get(key) != value for key, value in expected.items()):
            raise CredentialHostAuthorizationError(
                "model profile request does not match the active binding"
            )
        await self._validate_profile(profile)
        return profile

    async def _authorized_profiles(
        self,
        *,
        service: str,
        account: str,
        context: dict[str, Any] | None,
    ) -> list[ModelProfile]:
        profiles = (
            [await self._requested_profile(context)]
            if context is not None
            else await self._active_profiles()
        )
        if service == KEYCHAIN_ALIAS_SERVICE:
            requested_reference = f"keychain-alias:{account}"
            matches = [
                profile
                for profile in profiles
                if profile.credential_ref == requested_reference
            ]
        else:
            requested_reference = keychain_ref(
                service=service,
                account=account,
            )
            matches = [
                profile
                for profile in profiles
                if profile.credential_ref == requested_reference
                or self._alias_target(profile) == requested_reference
            ]
        if not matches:
            raise CredentialHostAuthorizationError(
                "credential reference is not bound to an active model profile"
            )
        for profile in matches:
            await self._validate_profile(profile)
        return matches

    async def read(
        self,
        *,
        service: str,
        account: str,
        profile: dict[str, Any] | None,
    ) -> str:
        await self._authorized_profiles(
            service=service,
            account=account,
            context=profile,
        )
        try:
            return self.secret_store.read(service=service, account=account)
        except (SecretNotFound, SecretStoreError) as exc:
            raise CredentialHostAuthorizationError(
                "authorized credential is unavailable"
            ) from exc


def build_credential_host_router(
    *,
    token_path: Path,
    secret_store: SecretStore,
    db_provider: Callable[[], Any],
) -> APIRouter:
    router = APIRouter()

    @router.get("/internal/alphaguard/credentials/health")
    async def credential_host_health() -> dict[str, str]:
        return {"status": "READY", "secret_store": "AVAILABLE"}

    @router.post(
        "/internal/alphaguard/credentials/read",
        response_model=CredentialHostReadResponse,
    )
    async def credential_host_read(
        payload: CredentialHostReadRequest,
        request: Request,
    ) -> CredentialHostReadResponse:
        supplied = request.headers.get(CREDENTIAL_HOST_TOKEN_HEADER, "")
        try:
            expected = read_credential_host_token(token_path)
        except RuntimeError:
            raise HTTPException(status_code=503, detail="credential host unavailable")
        if not supplied or not compare_digest(supplied, expected):
            raise HTTPException(status_code=403, detail="credential host access denied")
        try:
            value = await CredentialHostBroker(
                db_provider(),
                secret_store=secret_store,
            ).read(
                service=payload.service,
                account=payload.account,
                profile=payload.profile,
            )
        except CredentialHostAuthorizationError:
            raise HTTPException(status_code=403, detail="credential access denied")
        except Exception:
            raise HTTPException(status_code=503, detail="credential host unavailable")
        return CredentialHostReadResponse(value=value)

    return router
