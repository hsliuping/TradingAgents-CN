"""Admin-only model credential lifecycle backed by a system Secret Store."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import re
import time
from typing import Any
from uuid import uuid4

from openai import OpenAI

from app.schemas.alphaguard.decision import canonical_hash
from app.schemas.alphaguard.model_runtime import (
    CredentialCapabilitySummary,
    ModelCredentialMetadata,
    ModelCredentialMutationResult,
)
from tradingagents.alphaguard.structured_output import invoke_json_object

from .model_audit_service import ModelAuditService
from .model_budget_service import ModelBudgetService
from .model_capability_service import CapabilityEcho, ModelCapabilityService
from .model_credential_service import (
    CredentialNotConfigured,
    ModelCredentialService,
)
from .model_profile_registry import ModelProfileRegistry
from .model_provider_runtime import ModelProviderRuntime
from .model_runtime_repository import model_runtime_document
from .compatible_provider_registry import (
    CompatibleProviderRegistryService,
    ProviderRegistryNotReady,
)
from .model_endpoint_security import (
    EndpointSecurityError,
    build_pinned_client,
    parse_registered_endpoint,
)
from .model_secret_store import (
    KEYCHAIN_ALIAS_SERVICE,
    PROVIDER_KEYCHAIN_SERVICES,
    SecretNotFound,
    SecretStore,
    SecretStoreError,
    default_secret_store,
    keychain_ref,
)
from .prompt_profile_registry import PromptProfileRegistry


_SAFE_CREDENTIAL_ID = re.compile(r"^[^\x00-\x1f\x7f]{1,100}$")
_ERROR_MESSAGES = {
    "UNAUTHORIZED": "Provider authentication failed",
    "PROJECT_ACCESS_DENIED": "Provider project access was denied",
    "MODEL_NOT_FOUND": "A registered model is unavailable",
    "STRUCTURED_OUTPUT_UNSUPPORTED": "Structured model output is unsupported",
    "USAGE_UNAVAILABLE": "Provider token usage is unavailable",
    "RATE_LIMITED": "Provider rate limit reached",
    "TIMEOUT": "Provider request timed out",
    "PROVIDER_ERROR": "Provider access check failed",
    "PRICE_NOT_VERIFIED": "Registered model pricing is not verified",
    "BUDGET_BLOCKED": "Model budget policy blocked the call",
    "SECRET_STORE_UNAVAILABLE": "macOS Keychain Secret Store is unavailable",
    "CREDENTIAL_NOT_FOUND": "Credential is not configured",
}


class CredentialLifecycleConflict(RuntimeError):
    pass


class CredentialLifecycleNotFound(CredentialLifecycleConflict):
    pass


class _EphemeralCredentialResolver:
    """Request-scoped resolver used only before a Keychain switch."""

    def __init__(self, secret: str):
        self._secret = secret

    def configured(self, _credential_ref: str) -> bool:
        return bool(self._secret)

    def resolve(self, _credential_ref: str) -> str:
        return self._secret


def _classify_provider_error(exc: Exception) -> str:
    status_code = getattr(exc, "status_code", None)
    text = f"{exc.__class__.__name__} {exc}".lower()
    if status_code == 401 or "authentication" in text:
        return "UNAUTHORIZED"
    if status_code == 403:
        return "PROJECT_ACCESS_DENIED"
    if status_code == 404 or "model_not_found" in text:
        return "MODEL_NOT_FOUND"
    if status_code == 429 or "rate limit" in text:
        return "RATE_LIMITED"
    if "timeout" in text or "timed out" in text:
        return "TIMEOUT"
    return "PROVIDER_ERROR"


class ModelCredentialManagementService:
    def __init__(
        self,
        db,
        *,
        secret_store: SecretStore | None = None,
    ):
        self.db = db
        self.secret_store = secret_store or default_secret_store()
        self.profiles = ModelProfileRegistry(db)
        self.prompts = PromptProfileRegistry(db)
        self.budget = ModelBudgetService(db)
        self.model_audit = ModelAuditService(db)

    @property
    def secret_store_status(self) -> str:
        return "READY" if self.secret_store.available else "UNAVAILABLE"

    @staticmethod
    def _alias(
        provider: str,
        credential_id: str | None = None,
        provider_type: str = "OPENAI_OFFICIAL",
    ) -> str:
        if provider_type == "OPENAI_COMPATIBLE":
            if not credential_id:
                raise ValueError("compatible credential alias requires an id")
            return credential_id
        return f"{provider}-primary"

    @staticmethod
    def _clean_id(value: str) -> str:
        normalized = value.strip()
        if not _SAFE_CREDENTIAL_ID.fullmatch(normalized):
            raise ValueError("credential_id contains unsupported characters")
        return normalized

    async def _acquire_lifecycle(
        self,
        existing: dict[str, Any],
        *,
        operation: str,
    ) -> str:
        operation_id = str(uuid4())
        result = await self.db["ag_model_credentials"].update_one(
            {
                "credential_id": existing["credential_id"],
                "credential_ref": existing["credential_ref"],
                "status": existing["status"],
                "lifecycle_operation_id": {"$in": [None]},
            },
            {
                "$set": {
                    "lifecycle_operation_id": operation_id,
                    "lifecycle_operation": operation,
                    "lifecycle_started_at": datetime.now(timezone.utc),
                }
            },
        )
        if result.matched_count != 1:
            raise CredentialLifecycleConflict(
                "credential lifecycle operation is already in progress"
            )
        return operation_id

    async def _release_lifecycle(
        self,
        *,
        credential_id: str,
        operation_id: str,
    ) -> None:
        await self.db["ag_model_credentials"].update_one(
            {
                "credential_id": credential_id,
                "lifecycle_operation_id": operation_id,
            },
            {
                "$set": {
                    "lifecycle_operation_id": None,
                    "lifecycle_operation": None,
                    "lifecycle_started_at": None,
                }
            },
        )

    def _read_alias_target(self, alias: str) -> str | None:
        try:
            return self.secret_store.read(
                service=KEYCHAIN_ALIAS_SERVICE,
                account=alias,
            )
        except SecretNotFound:
            return None

    def _restore_alias_state(
        self,
        *,
        alias: str,
        owned_target: str | None,
        previous_target: str | None,
    ) -> None:
        current_target = self._read_alias_target(alias)
        if current_target != owned_target:
            raise CredentialLifecycleConflict(
                "credential alias changed concurrently"
            )
        if previous_target is None:
            self.secret_store.delete(
                service=KEYCHAIN_ALIAS_SERVICE,
                account=alias,
                missing_ok=True,
            )
        else:
            self.secret_store.write(
                service=KEYCHAIN_ALIAS_SERVICE,
                account=alias,
                secret=previous_target,
            )

    async def _audit_secret_store_failure(
        self,
        *,
        credential_id: str,
        provider: str,
        operator_user_id: str,
        action: str,
        trace_id: str,
    ) -> None:
        try:
            await self.audit(
                credential_id=credential_id,
                provider=provider,
                operator_user_id=operator_user_id,
                action=action,
                status="FAILED",
                error_code="SECRET_STORE_UNAVAILABLE",
                trace_id=trace_id,
            )
        except Exception:
            # Preserve the SecretStoreError so the API always returns its
            # sanitized 503 instead of leaking a secondary audit failure.
            return

    async def audit(
        self,
        *,
        credential_id: str,
        provider: str,
        operator_user_id: str,
        action: str,
        status: str,
        error_code: str | None,
        trace_id: str,
    ) -> None:
        # The allowlist is intentional: no context, body, Secret-derived data,
        # request hash, response hash, or provider response belongs here.
        await self.db["ag_model_credential_events"].insert_one(
            {
                "credential_id": credential_id,
                "provider": provider,
                "operator_user_id": operator_user_id,
                "action": action,
                "status": status,
                "error_code": error_code,
                "trace_id": trace_id,
                "created_at": datetime.now(timezone.utc),
            }
        )

    def _validate_base_url(
        self, *, provider: str, base_url: str | None
    ) -> str:
        registered = {
            (item.base_url or "").rstrip("/")
            for item in self.profiles.definitions()
            if item.provider.lower() == provider
        }
        requested = (base_url or next(iter(registered), "")).rstrip("/")
        if not requested or requested not in registered:
            raise ValueError(
                "Base URL must match an explicitly registered ModelProfile"
            )
        return requested

    async def _provider_probe(
        self,
        *,
        provider: str,
        secret: str,
        base_url: str,
        model_name: str | None,
    ) -> str:
        if provider != "openai":
            return "PROVIDER_ERROR"

        def probe() -> None:
            client = OpenAI(
                api_key=secret,
                base_url=base_url,
                timeout=30,
                max_retries=0,
            )
            if model_name:
                client.models.retrieve(model_name)
            else:
                # Listing is an authentication/project probe and does not
                # generate tokens or model output.
                client.models.list()

        try:
            await asyncio.to_thread(probe)
            return "READY"
        except Exception as exc:
            return _classify_provider_error(exc)

    async def _probe_secret(
        self,
        *,
        credential_id: str,
        provider: str,
        secret: str,
        base_url: str | None,
        operator_user_id: str,
        trace_id: str,
    ) -> CredentialCapabilitySummary:
        checked_at = datetime.now(timezone.utc)
        if provider not in PROVIDER_KEYCHAIN_SERVICES:
            return CredentialCapabilitySummary(
                provider=provider,
                authentication_status="PROVIDER_ERROR",
                provider_access_status="PROVIDER_ERROR",
                normal_model_status="PROVIDER_ERROR",
                top_model_status="PROVIDER_ERROR",
                structured_output_status="PROVIDER_ERROR",
                price_status="NOT_VERIFIED",
                budget_status="BLOCKED",
                checked_at=checked_at,
            )
        resolved_base_url = self._validate_base_url(
            provider=provider, base_url=base_url
        )
        profiles = {
            item.role: item
            for item in self.profiles.definitions()
            if item.provider.lower() == provider
        }
        normal = profiles["NORMAL_TRADER"]
        top = profiles["TOP_RISK_REVIEWER"]

        auth = await self._provider_probe(
            provider=provider,
            secret=secret,
            base_url=resolved_base_url,
            model_name=None,
        )
        if auth != "READY":
            return CredentialCapabilitySummary(
                provider=provider,
                authentication_status=auth,
                provider_access_status=auth,
                normal_model_status="NOT_CHECKED",
                top_model_status="NOT_CHECKED",
                structured_output_status="NOT_CHECKED",
                price_status="NOT_VERIFIED",
                budget_status="BLOCKED",
                checked_at=checked_at,
            )
        normal_status, top_status = await asyncio.gather(
            self._provider_probe(
                provider=provider,
                secret=secret,
                base_url=resolved_base_url,
                model_name=normal.model_name,
            ),
            self._provider_probe(
                provider=provider,
                secret=secret,
                base_url=resolved_base_url,
                model_name=top.model_name,
            ),
        )
        price_verified = all(
            value is not None
            for value in (
                normal.input_cost_per_million,
                normal.output_cost_per_million,
                top.input_cost_per_million,
                top.output_cost_per_million,
            )
        )
        price_status = "VERIFIED" if price_verified else "NOT_VERIFIED"
        budget_status = "BLOCKED"
        structured_status = "NOT_CHECKED"
        if (
            normal_status == "READY"
            and top_status == "READY"
            and price_verified
        ):
            budget = await self.budget.check(
                profile=normal,
                analysis_id=f"credential:{credential_id}",
                snapshot_id=None,
                rendered_input="credential capability schema probe",
            )
            budget_status = "READY" if budget.allowed else "BLOCKED"
            if budget.allowed:
                capability_prompt = self.prompts.definition(
                    "model_capability_prompt"
                )
                runtime = ModelProviderRuntime(
                    _EphemeralCredentialResolver(secret)
                )
                request_hash = canonical_hash(
                    {
                        "operation": "CREDENTIAL_STRUCTURED_CAPABILITY",
                        "profile_hash": normal.config_hash,
                        "prompt_hash": capability_prompt.template_hash,
                        "trace_id": trace_id,
                    }
                )
                started = time.perf_counter()
                invocation = await asyncio.to_thread(
                    invoke_json_object,
                    llm=runtime.create(normal),
                    messages=[
                        {
                            "role": "system",
                            "content": capability_prompt.template,
                        }
                    ],
                    schema_model=CapabilityEcho,
                    provider=normal.provider,
                    configured_model_name=normal.model_name,
                    prompt_name=capability_prompt.prompt_id,
                    prompt_version=capability_prompt.prompt_version,
                    template_hash=capability_prompt.template_hash,
                    input_hash=request_hash,
                    structured_output_mode=normal.structured_output_mode,
                    model_profile_id=normal.profile_id,
                    model_profile_version=normal.profile_version,
                    prompt_id=capability_prompt.prompt_id,
                    input_cost_per_million=normal.input_cost_per_million,
                    output_cost_per_million=normal.output_cost_per_million,
                    cost_currency=normal.cost_currency,
                    max_retries=0,
                )
                for meta in invocation.attempt_metas or (
                    invocation.model_meta,
                ):
                    await self.model_audit.record(
                        analysis_id=f"credential:{credential_id}",
                        snapshot_id=None,
                        context_hash=None,
                        run_mode="MODEL_CAPABILITY_CHECK",
                        automated_execution_allowed=False,
                        role=normal.role,
                        agent_name="credential_structured_capability",
                        profile=normal,
                        prompt=capability_prompt,
                        request_hash=request_hash,
                        meta=meta,
                    )
                structured_status = (
                    "READY"
                    if invocation.failure_status is None
                    else invocation.error_type or "PROVIDER_ERROR"
                )
                _ = time.perf_counter() - started
            else:
                structured_status = "BUDGET_BLOCKED"
        elif not price_verified:
            budget_status = "BLOCKED"
            structured_status = "PRICE_NOT_VERIFIED"

        return CredentialCapabilitySummary(
            provider=provider,
            authentication_status="READY",
            provider_access_status="READY",
            normal_model_status=normal_status,
            top_model_status=top_status,
            structured_output_status=structured_status,
            price_status=price_status,
            budget_status=budget_status,
            checked_at=checked_at,
        )

    async def _probe_compatible_secret(
        self,
        *,
        credential_id: str,
        secret: str,
        endpoint_profile_id: str,
        endpoint_profile_version: str,
    ) -> CredentialCapabilitySummary:
        checked_at = datetime.now(timezone.utc)
        registry = CompatibleProviderRegistryService(
            self.db, secret_store=self.secret_store
        )
        try:
            endpoint = await registry.endpoint(
                endpoint_profile_id, endpoint_profile_version
            )
        except ProviderRegistryNotReady:
            return CredentialCapabilitySummary(
                provider="openai_compatible",
                authentication_status="PROVIDER_ERROR",
                provider_access_status="PROVIDER_ERROR",
                normal_model_status="NOT_CHECKED",
                top_model_status="NOT_CHECKED",
                structured_output_status="NOT_CHECKED",
                price_status="NOT_VERIFIED",
                budget_status="BLOCKED",
                checked_at=checked_at,
            )
        if (
            endpoint.provider_type != "OPENAI_COMPATIBLE"
            or endpoint.state
            not in {"URL_VALIDATED", "CAPABILITY_CHECKED", "READY"}
            or endpoint.url_validation_status != "PASS"
            or not endpoint.resolved_ips
        ):
            return CredentialCapabilitySummary(
                provider="openai_compatible",
                authentication_status="PROVIDER_ERROR",
                provider_access_status="PROVIDER_ERROR",
                normal_model_status="NOT_CHECKED",
                top_model_status="NOT_CHECKED",
                structured_output_status="NOT_CHECKED",
                price_status="NOT_VERIFIED",
                budget_status="BLOCKED",
                checked_at=checked_at,
            )
        models = await registry.list_models(
            endpoint_profile_id, endpoint_profile_version
        )
        roles = {
            role: next(
                (
                    item
                    for item in models
                    if role in item.get("role_capabilities", [])
                    and item.get("status") != "DISABLED"
                ),
                None,
            )
            for role in ("NORMAL_TRADER", "TOP_RISK_REVIEWER")
        }
        if not endpoint.models_endpoint_enabled and not all(roles.values()):
            return CredentialCapabilitySummary(
                provider="openai_compatible",
                authentication_status="NOT_CHECKED",
                provider_access_status="NOT_CHECKED",
                normal_model_status=(
                    "NOT_CHECKED" if roles["NORMAL_TRADER"] else "MODEL_NOT_FOUND"
                ),
                top_model_status=(
                    "NOT_CHECKED"
                    if roles["TOP_RISK_REVIEWER"]
                    else "MODEL_NOT_FOUND"
                ),
                structured_output_status="NOT_CHECKED",
                price_status="NOT_VERIFIED",
                budget_status="BLOCKED",
                checked_at=checked_at,
            )
        parsed = parse_registered_endpoint(endpoint.base_url)

        def probe() -> tuple[str, set[str]]:
            try:
                with build_pinned_client(
                    endpoint=parsed,
                    resolved_ips=endpoint.resolved_ips,
                    timeout_seconds=30,
                    secret=secret,
                    auth_scheme=endpoint.auth_scheme,
                ) as client:
                    if endpoint.models_endpoint_enabled:
                        response = client.get(
                            f"{endpoint.base_url.rstrip('/')}/models"
                        )
                        if 300 <= response.status_code < 400:
                            return "PROVIDER_ERROR", set()
                        if response.status_code >= 400:
                            error = RuntimeError("provider access failed")
                            error.status_code = response.status_code
                            return _classify_provider_error(error), set()
                        payload = response.json()
                        names = {
                            str(item["id"])
                            for item in payload.get("data", [])
                            if isinstance(item, dict)
                            and isinstance(item.get("id"), str)
                        }
                        return "READY", names

                    # A provider without /models is checked through one fixed,
                    # minimal non-trading request per explicitly registered
                    # model. No user prompt, header, method or body is proxied.
                    names = set()
                    for model in roles.values():
                        if endpoint.api_mode == "OPENAI_RESPONSES":
                            path = "responses"
                            body = {
                                "model": model["remote_model_name"],
                                "input": "Return one JSON object with status READY.",
                                "max_output_tokens": 32,
                            }
                        else:
                            path = "chat/completions"
                            body = {
                                "model": model["remote_model_name"],
                                "messages": [
                                    {
                                        "role": "user",
                                        "content": (
                                            "Return one JSON object with status READY."
                                        ),
                                    }
                                ],
                                "max_tokens": 32,
                                "temperature": 0,
                                "response_format": {"type": "json_object"},
                            }
                        response = client.post(
                            f"{endpoint.base_url.rstrip('/')}/{path}",
                            json=body,
                        )
                        if 300 <= response.status_code < 400:
                            return "PROVIDER_ERROR", set()
                        if response.status_code >= 400:
                            error = RuntimeError("provider access failed")
                            error.status_code = response.status_code
                            return _classify_provider_error(error), set()
                        response.json()
                        names.add(str(model["remote_model_name"]))
                    return "READY", names
            except (EndpointSecurityError, ValueError):
                return "PROVIDER_ERROR", set()
            except Exception as exc:
                return _classify_provider_error(exc), set()

        access_status, available_models = await asyncio.to_thread(probe)
        if access_status != "READY":
            return CredentialCapabilitySummary(
                provider="openai_compatible",
                authentication_status=access_status,
                provider_access_status=access_status,
                normal_model_status="NOT_CHECKED",
                top_model_status="NOT_CHECKED",
                structured_output_status="NOT_CHECKED",
                price_status="NOT_VERIFIED",
                budget_status="BLOCKED",
                checked_at=checked_at,
            )
        normal_status = (
            "READY"
            if roles["NORMAL_TRADER"]
            and roles["NORMAL_TRADER"]["remote_model_name"] in available_models
            else "MODEL_NOT_FOUND"
        )
        top_status = (
            "READY"
            if roles["TOP_RISK_REVIEWER"]
            and roles["TOP_RISK_REVIEWER"]["remote_model_name"]
            in available_models
            else "MODEL_NOT_FOUND"
        )
        # Credential bootstrap deliberately precedes model/profile/price
        # registration for endpoints that expose an authenticated /models
        # catalog. Authentication can therefore be proven and the secret can
        # be stored as DEGRADED without pretending the remaining capabilities
        # are ready. Endpoints without /models still require explicit model
        # definitions before a bounded authentication probe is possible.
        if not all(roles.values()):
            return CredentialCapabilitySummary(
                provider="openai_compatible",
                authentication_status="READY",
                provider_access_status="READY",
                normal_model_status=normal_status,
                top_model_status=top_status,
                structured_output_status="NOT_CHECKED",
                price_status="NOT_VERIFIED",
                budget_status="BLOCKED",
                checked_at=checked_at,
            )
        prices = await registry.list_prices(endpoint_profile_id)
        priced_models = {
            item["endpoint_model_id"]
            for item in prices
            if item.get("verified")
            and item.get("endpoint_profile_version") == endpoint_profile_version
        }
        price_verified = all(
            model["endpoint_model_id"] in priced_models
            for model in roles.values()
        )
        role_prices = [
            item
            for item in prices
            if item.get("endpoint_model_id")
            in {model["endpoint_model_id"] for model in roles.values()}
            and item.get("verified")
            and item.get("endpoint_profile_version")
            == endpoint_profile_version
        ]
        budget_currency_ready = bool(role_prices) and all(
            item.get("currency") == self.budget.policy.currency
            for item in role_prices
        )
        structured_ready = endpoint.structured_output_mode != "UNKNOWN" and all(
            (
                endpoint.structured_output_mode == "JSON_ONLY"
                or endpoint.structured_output_mode == "NATIVE_JSON_SCHEMA"
                and model.get("supports_json_schema")
                or endpoint.structured_output_mode == "TOOL_CALL"
                and model.get("supports_tool_call")
            )
            for model in roles.values()
        )
        return CredentialCapabilitySummary(
            provider="openai_compatible",
            authentication_status="READY",
            provider_access_status="READY",
            normal_model_status=normal_status,
            top_model_status=top_status,
            structured_output_status=(
                "READY" if structured_ready else "STRUCTURED_OUTPUT_UNSUPPORTED"
            ),
            price_status="VERIFIED" if price_verified else "NOT_VERIFIED",
            budget_status=(
                "READY"
                if price_verified and budget_currency_ready
                else "BLOCKED"
            ),
            checked_at=checked_at,
        )

    @staticmethod
    def _credential_checks_pass(
        result: CredentialCapabilitySummary,
    ) -> bool:
        return all(
            value == "READY"
            for value in (
                result.authentication_status,
                result.provider_access_status,
                result.normal_model_status,
                result.top_model_status,
            )
        )

    @classmethod
    def _credential_can_be_stored(
        cls,
        result: CredentialCapabilitySummary,
        provider_type: str,
    ) -> bool:
        if provider_type == "OPENAI_COMPATIBLE":
            return (
                result.authentication_status == "READY"
                and result.provider_access_status == "READY"
            )
        return cls._credential_checks_pass(result)

    @staticmethod
    def _primary_error(
        result: CredentialCapabilitySummary,
    ) -> str | None:
        for value in (
            result.authentication_status,
            result.provider_access_status,
            result.normal_model_status,
            result.top_model_status,
            result.structured_output_status,
        ):
            if value not in {"READY", "NOT_CHECKED"}:
                return value
        if result.price_status != "VERIFIED":
            return "PRICE_NOT_VERIFIED"
        if result.budget_status != "READY":
            return "BUDGET_BLOCKED"
        return None

    async def _persist_capability_checks(
        self,
        *,
        provider: str,
        operator_user_id: str,
        trace_id: str,
    ) -> None:
        service = ModelCapabilityService(self.db)
        for profile in self.profiles.definitions():
            if profile.provider.lower() != provider:
                continue
            try:
                await service.check(
                    profile_id=profile.profile_id,
                    profile_version=profile.profile_version,
                    checked_by=operator_user_id,
                    idempotency_key=(
                        f"credential-{trace_id}-{profile.profile_id}"
                    ),
                    network=True,
                )
            except Exception:
                # Credential activation already succeeded. A secondary audit
                # persistence failure must be visible but must not produce a
                # misleading "credential was not stored" response.
                await self.audit(
                    credential_id="profile-bound",
                    provider=provider,
                    operator_user_id=operator_user_id,
                    action="CAPABILITY_CHECKED",
                    status="FAILED",
                    error_code="PROVIDER_ERROR",
                    trace_id=trace_id,
                )
                return

    async def list_public(self) -> list[dict[str, Any]]:
        rows = await self.db["ag_model_credentials"].find({}).sort(
            "updated_at", -1
        ).to_list(length=100)
        items = []
        for row in rows:
            latest_event = await self.db[
                "ag_model_credential_events"
            ].find_one(
                {"credential_id": row["credential_id"]},
                sort=[("created_at", -1), ("_id", -1)],
            )
            error_code = (
                str(latest_event.get("error_code"))
                if latest_event
                and latest_event.get("status")
                in {"FAILED", "DEGRADED", "ERROR", "REJECTED"}
                and latest_event.get("error_code")
                else None
            )
            configured = False
            provider_type = str(
                row.get("provider_type") or "OPENAI_OFFICIAL"
            )
            alias = self._alias(
                str(row["provider"]),
                str(row["credential_id"]),
                provider_type,
            )
            if (
                row.get("status") in {"CONFIGURED", "DEGRADED"}
                and not row.get("lifecycle_operation_id")
                and self.secret_store.available
            ):
                configured = ModelCredentialService(
                    self.secret_store
                ).configured(
                    f"keychain-alias:{alias}"
                )
            items.append(
                {
                    "credential_id": str(row["credential_id"]),
                    "provider": str(row["provider"]),
                    "provider_type": provider_type,
                    "endpoint_profile_id": row.get("endpoint_profile_id"),
                    "endpoint_profile_version": row.get(
                        "endpoint_profile_version"
                    ),
                    "normalized_origin": row.get("normalized_origin"),
                    "auth_scheme": row.get("auth_scheme"),
                    "configured": configured,
                    "status": (
                        str(row["status"])
                        if self.secret_store.available
                        else "DEGRADED"
                    ),
                    "last_verified_at": row.get("last_verified_at"),
                    "last_error_code": error_code,
                    "sanitized_message": (
                        _ERROR_MESSAGES.get(error_code) if error_code else None
                    ),
                    "secret_store_status": self.secret_store_status,
                }
            )
        return items

    async def create(
        self,
        *,
        credential_id: str,
        provider: str,
        secret: str,
        base_url: str | None,
        operator_user_id: str,
        trace_id: str,
        provider_type: str = "OPENAI_OFFICIAL",
        endpoint_profile_id: str | None = None,
        endpoint_profile_version: str | None = None,
    ) -> ModelCredentialMutationResult:
        credential_id = self._clean_id(credential_id)
        provider = provider.strip().lower()
        if provider_type == "OPENAI_COMPATIBLE":
            provider = "openai_compatible"
            if base_url is not None:
                raise ValueError(
                    "compatible credential URL comes only from its Endpoint Profile"
                )
            if not endpoint_profile_id or not endpoint_profile_version:
                raise ValueError(
                    "compatible credential requires an exact Endpoint Profile version"
                )
            endpoint = await CompatibleProviderRegistryService(
                self.db, secret_store=self.secret_store
            ).endpoint(endpoint_profile_id, endpoint_profile_version)
            normalized_origin = endpoint.normalized_origin
            auth_scheme = endpoint.auth_scheme
        elif provider_type == "OPENAI_OFFICIAL":
            if provider != "openai":
                raise ValueError("official credential provider must be openai")
            if (
                endpoint_profile_id is not None
                or endpoint_profile_version is not None
            ):
                raise ValueError(
                    "official credential cannot bind a compatible Endpoint Profile"
                )
            endpoint = None
            normalized_origin = None
            auth_scheme = None
        else:
            raise ValueError("unsupported provider_type")
        if not self.secret_store.available:
            result = CredentialCapabilitySummary(
                provider=provider,
                authentication_status="NOT_CHECKED",
                provider_access_status="NOT_CHECKED",
                normal_model_status="NOT_CHECKED",
                top_model_status="NOT_CHECKED",
                structured_output_status="NOT_CHECKED",
                price_status="NOT_VERIFIED",
                budget_status="BLOCKED",
                checked_at=datetime.now(timezone.utc),
            )
            await self.audit(
                credential_id=credential_id,
                provider=provider,
                operator_user_id=operator_user_id,
                action="CREDENTIAL_CREATED",
                status="FAILED",
                error_code="SECRET_STORE_UNAVAILABLE",
                trace_id=trace_id,
            )
            return self._result(
                credential_id=credential_id,
                provider=provider,
                capability=result,
                stored=False,
                replaced=False,
                error_code="SECRET_STORE_UNAVAILABLE",
                provider_type=provider_type,
                endpoint_profile_id=endpoint_profile_id,
                endpoint_profile_version=endpoint_profile_version,
            )
        existing_query = (
            {
                "$or": [
                    {"credential_id": credential_id},
                    {
                        "provider_type": provider_type,
                        "endpoint_profile_id": endpoint_profile_id,
                        "endpoint_profile_version": endpoint_profile_version,
                        "normalized_origin": normalized_origin,
                        "auth_scheme": auth_scheme,
                    },
                ]
            }
            if provider_type == "OPENAI_COMPATIBLE"
            else {"provider": provider}
        )
        existing = await self.db["ag_model_credentials"].find_one(existing_query)
        if existing and existing.get("status") != "REVOKED":
            raise CredentialLifecycleConflict(
                "credential binding already exists; use replace"
            )
        capability = (
            await self._probe_compatible_secret(
                credential_id=credential_id,
                secret=secret,
                endpoint_profile_id=str(endpoint_profile_id),
                endpoint_profile_version=str(endpoint_profile_version),
            )
            if provider_type == "OPENAI_COMPATIBLE"
            else await self._probe_secret(
                credential_id=credential_id,
                provider=provider,
                secret=secret,
                base_url=base_url,
                operator_user_id=operator_user_id,
                trace_id=trace_id,
            )
        )
        error_code = self._primary_error(capability)
        if not self._credential_can_be_stored(capability, provider_type):
            await self.audit(
                credential_id=credential_id,
                provider=provider,
                operator_user_id=operator_user_id,
                action="AUTHENTICATION_FAILED",
                status="FAILED",
                error_code=error_code,
                trace_id=trace_id,
            )
            return self._result(
                credential_id=credential_id,
                provider=provider,
                capability=capability,
                stored=False,
                replaced=False,
                error_code=error_code,
                provider_type=provider_type,
                endpoint_profile_id=endpoint_profile_id,
                endpoint_profile_version=endpoint_profile_version,
            )
        now = datetime.now(timezone.utc)
        service = PROVIDER_KEYCHAIN_SERVICES[provider]
        account = f"{provider}-{uuid4()}"
        reference = keychain_ref(service=service, account=account)
        alias = self._alias(provider, credential_id, provider_type)
        try:
            self.secret_store.write(
                service=service, account=account, secret=secret
            )
            self.secret_store.write(
                service=KEYCHAIN_ALIAS_SERVICE,
                account=alias,
                secret=reference,
            )
            metadata = ModelCredentialMetadata(
                credential_id=credential_id,
                provider=provider,
                credential_ref=reference,
                provider_type=provider_type,
                endpoint_profile_id=endpoint_profile_id,
                endpoint_profile_version=endpoint_profile_version,
                normalized_origin=normalized_origin,
                auth_scheme=auth_scheme,
                status=(
                    "CONFIGURED"
                    if error_code is None
                    else "DEGRADED"
                ),
                created_by=operator_user_id,
                created_at=now,
                updated_at=now,
                last_verified_at=capability.checked_at,
                schema_version=(
                    "model_credential_metadata_v2"
                    if provider_type == "OPENAI_COMPATIBLE"
                    else "model_credential_metadata_v1"
                ),
            )
            if existing:
                await self.db["ag_model_credentials"].replace_one(
                    existing_query,
                    model_runtime_document(metadata),
                )
            else:
                await self.db["ag_model_credentials"].insert_one(
                    model_runtime_document(metadata)
                )
        except Exception:
            self.secret_store.delete(
                service=KEYCHAIN_ALIAS_SERVICE,
                account=alias,
                missing_ok=True,
            )
            self.secret_store.delete(
                service=service, account=account, missing_ok=True
            )
            await self.audit(
                credential_id=credential_id,
                provider=provider,
                operator_user_id=operator_user_id,
                action="CREDENTIAL_CREATED",
                status="FAILED",
                error_code="SECRET_STORE_ERROR",
                trace_id=trace_id,
            )
            raise SecretStoreError("credential could not be stored")
        await self.audit(
            credential_id=credential_id,
            provider=provider,
            operator_user_id=operator_user_id,
            action="CREDENTIAL_CREATED",
            status="SUCCESS" if error_code is None else "DEGRADED",
            error_code=error_code,
            trace_id=trace_id,
        )
        if provider_type == "OPENAI_OFFICIAL":
            await self._persist_capability_checks(
                provider=provider,
                operator_user_id=operator_user_id,
                trace_id=trace_id,
            )
        return self._result(
            credential_id=credential_id,
            provider=provider,
            capability=capability,
            stored=True,
            replaced=False,
            error_code=error_code,
            provider_type=provider_type,
            endpoint_profile_id=endpoint_profile_id,
            endpoint_profile_version=endpoint_profile_version,
        )

    async def replace(
        self,
        *,
        credential_id: str,
        secret: str,
        base_url: str | None,
        operator_user_id: str,
        trace_id: str,
    ) -> ModelCredentialMutationResult:
        credential_id = self._clean_id(credential_id)
        existing = await self.db["ag_model_credentials"].find_one(
            {"credential_id": credential_id}
        )
        if existing is None or existing.get("status") == "REVOKED":
            raise CredentialLifecycleConflict("active credential not found")
        provider = str(existing["provider"])
        provider_type = str(
            existing.get("provider_type") or "OPENAI_OFFICIAL"
        )
        endpoint_profile_id = existing.get("endpoint_profile_id")
        endpoint_profile_version = existing.get("endpoint_profile_version")
        if provider_type == "OPENAI_COMPATIBLE" and base_url is not None:
            raise ValueError(
                "compatible credential URL comes only from its Endpoint Profile"
            )
        capability = (
            await self._probe_compatible_secret(
                credential_id=credential_id,
                secret=secret,
                endpoint_profile_id=str(endpoint_profile_id),
                endpoint_profile_version=str(endpoint_profile_version),
            )
            if provider_type == "OPENAI_COMPATIBLE"
            else await self._probe_secret(
                credential_id=credential_id,
                provider=provider,
                secret=secret,
                base_url=base_url,
                operator_user_id=operator_user_id,
                trace_id=trace_id,
            )
        )
        error_code = self._primary_error(capability)
        if not self._credential_can_be_stored(capability, provider_type):
            await self.audit(
                credential_id=credential_id,
                provider=provider,
                operator_user_id=operator_user_id,
                action="CREDENTIAL_REPLACED",
                status="FAILED",
                error_code=error_code,
                trace_id=trace_id,
            )
            return self._result(
                credential_id=credential_id,
                provider=provider,
                capability=capability,
                stored=True,
                replaced=False,
                error_code=error_code,
                provider_type=provider_type,
                endpoint_profile_id=endpoint_profile_id,
                endpoint_profile_version=endpoint_profile_version,
            )
        old_ref = str(existing["credential_ref"])
        old_service, old_account = self._parse_direct_ref(old_ref)
        service = PROVIDER_KEYCHAIN_SERVICES[provider]
        new_account = f"{provider}-{uuid4()}"
        new_ref = keychain_ref(service=service, account=new_account)
        alias = self._alias(provider, credential_id, provider_type)
        operation_id = await self._acquire_lifecycle(
            existing, operation="REPLACE"
        )
        previous_alias_target = None
        new_direct_written = False
        alias_switched = False
        try:
            previous_alias_target = self._read_alias_target(alias)
            if previous_alias_target not in {None, old_ref}:
                raise CredentialLifecycleConflict(
                    "credential alias changed concurrently"
                )
            self.secret_store.write(
                service=service, account=new_account, secret=secret
            )
            new_direct_written = True
            self.secret_store.write(
                service=KEYCHAIN_ALIAS_SERVICE,
                account=alias,
                secret=new_ref,
            )
            alias_switched = True
            updated = await self.db["ag_model_credentials"].update_one(
                {
                    "credential_id": credential_id,
                    "credential_ref": old_ref,
                    "status": existing["status"],
                    "lifecycle_operation_id": operation_id,
                },
                {
                    "$set": {
                        "credential_ref": new_ref,
                        "status": (
                            "CONFIGURED"
                            if error_code is None
                            else "DEGRADED"
                        ),
                        "updated_at": datetime.now(timezone.utc),
                        "last_verified_at": capability.checked_at,
                        "lifecycle_operation_id": None,
                        "lifecycle_operation": None,
                        "lifecycle_started_at": None,
                    }
                },
            )
            if updated.matched_count != 1:
                raise CredentialLifecycleConflict(
                    "credential changed concurrently"
                )
        except Exception as operation_error:
            try:
                if alias_switched:
                    self._restore_alias_state(
                        alias=alias,
                        owned_target=new_ref,
                        previous_target=previous_alias_target,
                    )
                if new_direct_written:
                    self.secret_store.delete(
                        service=service,
                        account=new_account,
                        missing_ok=True,
                    )
            finally:
                await self._release_lifecycle(
                    credential_id=credential_id,
                    operation_id=operation_id,
                )
            if isinstance(operation_error, SecretStoreError):
                await self._audit_secret_store_failure(
                    credential_id=credential_id,
                    provider=provider,
                    operator_user_id=operator_user_id,
                    action="CREDENTIAL_REPLACED",
                    trace_id=trace_id,
                )
            raise
        try:
            self.secret_store.delete(
                service=old_service, account=old_account, missing_ok=True
            )
        except SecretStoreError:
            await self._audit_secret_store_failure(
                credential_id=credential_id,
                provider=provider,
                operator_user_id=operator_user_id,
                action="CREDENTIAL_REPLACED",
                trace_id=trace_id,
            )
            # The alias is already removed and Mongo marks the credential
            # REVOKED, so ModelRunner cannot resolve it. Report the remaining
            # direct Keychain cleanup separately instead of claiming that the
            # revocation itself failed.
            return {
                "credential_id": credential_id,
                "provider": provider,
                "configured": False,
                "status": "REVOKED",
                "cleanup_status": "PENDING",
            }
        await self.audit(
            credential_id=credential_id,
            provider=provider,
            operator_user_id=operator_user_id,
            action="CREDENTIAL_REPLACED",
            status="SUCCESS" if error_code is None else "DEGRADED",
            error_code=error_code,
            trace_id=trace_id,
        )
        if provider_type == "OPENAI_OFFICIAL":
            await self._persist_capability_checks(
                provider=provider,
                operator_user_id=operator_user_id,
                trace_id=trace_id,
            )
        return self._result(
            credential_id=credential_id,
            provider=provider,
            capability=capability,
            stored=True,
            replaced=True,
            error_code=error_code,
            provider_type=provider_type,
            endpoint_profile_id=endpoint_profile_id,
            endpoint_profile_version=endpoint_profile_version,
        )

    async def verify(
        self,
        *,
        credential_id: str,
        operator_user_id: str,
        trace_id: str,
    ) -> ModelCredentialMutationResult:
        credential_id = self._clean_id(credential_id)
        existing = await self.db["ag_model_credentials"].find_one(
            {"credential_id": credential_id}
        )
        if existing is None or existing.get("status") == "REVOKED":
            raise CredentialLifecycleConflict("active credential not found")
        provider = str(existing["provider"])
        provider_type = str(
            existing.get("provider_type") or "OPENAI_OFFICIAL"
        )
        endpoint_profile_id = existing.get("endpoint_profile_id")
        endpoint_profile_version = existing.get("endpoint_profile_version")
        try:
            secret = ModelCredentialService(
                self.secret_store
            ).resolve(
                "keychain-alias:"
                f"{self._alias(provider, credential_id, provider_type)}"
            )
            capability = (
                await self._probe_compatible_secret(
                    credential_id=credential_id,
                    secret=secret,
                    endpoint_profile_id=str(endpoint_profile_id),
                    endpoint_profile_version=str(endpoint_profile_version),
                )
                if provider_type == "OPENAI_COMPATIBLE"
                else await self._probe_secret(
                    credential_id=credential_id,
                    provider=provider,
                    secret=secret,
                    base_url=None,
                    operator_user_id=operator_user_id,
                    trace_id=trace_id,
                )
            )
        except (
            CredentialNotConfigured,
            SecretStoreError,
            SecretNotFound,
        ):
            capability = CredentialCapabilitySummary(
                provider=provider,
                authentication_status="NOT_CONFIGURED",
                provider_access_status="NOT_CONFIGURED",
                normal_model_status="NOT_CHECKED",
                top_model_status="NOT_CHECKED",
                structured_output_status="NOT_CHECKED",
                price_status="NOT_VERIFIED",
                budget_status="BLOCKED",
                checked_at=datetime.now(timezone.utc),
            )
        finally:
            secret = None
        error_code = self._primary_error(capability)
        passed = self._credential_can_be_stored(capability, provider_type)
        updated = await self.db["ag_model_credentials"].update_one(
            {
                "credential_id": credential_id,
                "credential_ref": existing["credential_ref"],
                "status": {"$ne": "REVOKED"},
                "lifecycle_operation_id": {"$in": [None]},
            },
            {
                "$set": {
                    "status": (
                        "CONFIGURED"
                        if passed and error_code is None
                        else "DEGRADED"
                    ),
                    "updated_at": datetime.now(timezone.utc),
                    "last_verified_at": capability.checked_at,
                }
            },
        )
        if updated.matched_count != 1:
            raise CredentialLifecycleConflict(
                "credential changed during verification"
            )
        await self.audit(
            credential_id=credential_id,
            provider=provider,
            operator_user_id=operator_user_id,
            action="CAPABILITY_CHECKED",
            status=(
                "SUCCESS"
                if passed and error_code is None
                else "DEGRADED"
                if passed
                else "FAILED"
            ),
            error_code=error_code,
            trace_id=trace_id,
        )
        if passed and provider_type == "OPENAI_OFFICIAL":
            await self._persist_capability_checks(
                provider=provider,
                operator_user_id=operator_user_id,
                trace_id=trace_id,
            )
        return self._result(
            credential_id=credential_id,
            provider=provider,
            capability=capability,
            stored=True,
            replaced=False,
            error_code=error_code,
            provider_type=provider_type,
            endpoint_profile_id=endpoint_profile_id,
            endpoint_profile_version=endpoint_profile_version,
        )

    async def revoke(
        self,
        *,
        credential_id: str,
        operator_user_id: str,
        trace_id: str,
    ) -> dict[str, Any]:
        credential_id = self._clean_id(credential_id)
        existing = await self.db["ag_model_credentials"].find_one(
            {"credential_id": credential_id}
        )
        if existing is None:
            raise CredentialLifecycleNotFound("credential not found")
        provider = str(existing["provider"])
        provider_type = str(
            existing.get("provider_type") or "OPENAI_OFFICIAL"
        )
        was_revoked = existing.get("status") == "REVOKED"
        service, account = self._parse_direct_ref(
            str(existing["credential_ref"])
        )
        direct_ref = str(existing["credential_ref"])
        alias = self._alias(provider, credential_id, provider_type)
        if not was_revoked:
            operation_id = await self._acquire_lifecycle(
                existing, operation="REVOKE"
            )
            alias_target = None
            alias_deleted = False
            try:
                alias_target = self._read_alias_target(alias)
                if alias_target not in {None, direct_ref}:
                    raise CredentialLifecycleConflict(
                        "credential alias changed concurrently"
                    )
                if alias_target == direct_ref:
                    self.secret_store.delete(
                        service=KEYCHAIN_ALIAS_SERVICE,
                        account=alias,
                        missing_ok=True,
                    )
                    alias_deleted = True
                updated = await self.db["ag_model_credentials"].update_one(
                    {
                        "credential_id": credential_id,
                        "credential_ref": direct_ref,
                        "status": existing["status"],
                        "lifecycle_operation_id": operation_id,
                    },
                    {
                        "$set": {
                            "status": "REVOKED",
                            "updated_at": datetime.now(timezone.utc),
                            "lifecycle_operation_id": None,
                            "lifecycle_operation": None,
                            "lifecycle_started_at": None,
                        }
                    },
                )
                if updated.matched_count != 1:
                    raise CredentialLifecycleConflict(
                        "credential changed concurrently"
                    )
                operation_id = None
            except Exception as operation_error:
                try:
                    if alias_deleted:
                        self._restore_alias_state(
                            alias=alias,
                            owned_target=None,
                            previous_target=alias_target,
                        )
                finally:
                    if operation_id is not None:
                        await self._release_lifecycle(
                            credential_id=credential_id,
                            operation_id=operation_id,
                        )
                if isinstance(operation_error, SecretStoreError):
                    await self._audit_secret_store_failure(
                        credential_id=credential_id,
                        provider=provider,
                        operator_user_id=operator_user_id,
                        action="CREDENTIAL_REVOKED",
                        trace_id=trace_id,
                    )
                raise

        try:
            self.secret_store.delete(
                service=service, account=account, missing_ok=True
            )
        except SecretStoreError:
            await self._audit_secret_store_failure(
                credential_id=credential_id,
                provider=provider,
                operator_user_id=operator_user_id,
                action="CREDENTIAL_REVOKED",
                trace_id=trace_id,
            )
            # The runtime alias is gone and the database row is REVOKED. The
            # remaining direct Keychain item is unreachable by ModelRunner and
            # can be retried by repeating this idempotent revoke operation.
            return {
                "credential_id": credential_id,
                "provider": provider,
                "configured": False,
                "status": "REVOKED",
                "cleanup_status": "PENDING",
            }

        await self.audit(
            credential_id=credential_id,
            provider=provider,
            operator_user_id=operator_user_id,
            action="CREDENTIAL_REVOKED",
            status="SUCCESS",
            error_code=None,
            trace_id=trace_id,
        )
        return {
            "credential_id": credential_id,
            "provider": provider,
            "configured": False,
            "status": "REVOKED",
            "cleanup_status": "COMPLETE",
        }

    @staticmethod
    def _parse_direct_ref(reference: str) -> tuple[str, str]:
        from .model_secret_store import parse_keychain_ref

        service, account = parse_keychain_ref(reference)
        if service is None:
            raise SecretStoreError("legacy Keychain reference cannot be managed")
        return service, account

    def _result(
        self,
        *,
        credential_id: str,
        provider: str,
        capability: CredentialCapabilitySummary,
        stored: bool,
        replaced: bool,
        error_code: str | None,
        provider_type: str = "OPENAI_OFFICIAL",
        endpoint_profile_id: str | None = None,
        endpoint_profile_version: str | None = None,
    ) -> ModelCredentialMutationResult:
        fully_ready = (
            self._credential_checks_pass(capability)
            and error_code is None
        )
        return ModelCredentialMutationResult(
            credential_id=credential_id,
            provider=provider,
            provider_type=provider_type,
            endpoint_profile_id=endpoint_profile_id,
            endpoint_profile_version=endpoint_profile_version,
            configured=stored,
            stored=stored,
            replaced=replaced,
            status=(
                "READY"
                if fully_ready
                else "DEGRADED"
                if stored
                else "NOT_CONFIGURED"
            ),
            secret_store_status=self.secret_store_status,
            capability=capability,
            last_error_code=error_code,
            sanitized_message=(
                _ERROR_MESSAGES.get(error_code) if error_code else None
            ),
        )
