"""Non-trading exact-profile capability checks and model readiness."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import time
from typing import Literal
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.alphaguard.decision import canonical_hash
from app.schemas.alphaguard.model_runtime import ModelCapabilityCheck
from tradingagents.alphaguard.decision_schemas import (
    NormalTradePlan,
    TopReviewDecision,
)
from tradingagents.alphaguard.structured_output import invoke_json_object

from .model_audit_service import ModelAuditService, sanitize_model_message
from .model_budget_service import ModelBudgetService
from .model_credential_service import (
    CredentialNotConfigured,
    ModelCredentialService,
)
from .model_profile_registry import (
    ModelProfileNotRegistered,
    ModelProfileRegistry,
)
from .model_provider_runtime import (
    ModelProviderRuntime,
    UnsupportedModelProvider,
)
from .model_runtime_repository import ModelRuntimeRepository
from .prompt_profile_registry import (
    PromptProfileNotRegistered,
    PromptProfileRegistry,
)


class CapabilityEcho(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    status: Literal["READY"]
    note: str = Field(min_length=1, max_length=200)


class ModelCapabilityService:
    def __init__(self, db, *, provider_runtime=None):
        self.db = db
        self.profiles = ModelProfileRegistry(db)
        self.prompts = PromptProfileRegistry(db)
        self.credentials = ModelCredentialService()
        self.provider_runtime = provider_runtime or ModelProviderRuntime(
            self.credentials
        )
        self.repository = ModelRuntimeRepository(db)
        self.budget = ModelBudgetService(db)
        self.audit = ModelAuditService(db)

    @staticmethod
    def _capability_contract(profile) -> tuple[str, type[BaseModel]]:
        if profile.role == "NORMAL_TRADER":
            return "normal_trade_plan_capability_prompt", NormalTradePlan
        if profile.role == "TOP_RISK_REVIEWER":
            return "top_review_capability_prompt", TopReviewDecision
        return "model_capability_prompt", CapabilityEcho

    async def _provider_access_probe(
        self, profile
    ) -> tuple[str, str | None, float]:
        """Use a no-generation provider endpoint before any paid schema call."""

        if profile.provider_type == "OPENAI_COMPATIBLE":
            from .compatible_provider_registry import (
                CompatibleProviderRegistryService,
            )
            from .model_endpoint_security import (
                EndpointSecurityError,
                build_pinned_client,
                parse_registered_endpoint,
            )

            try:
                endpoint, model, _price, credential = (
                    await CompatibleProviderRegistryService(
                        self.db,
                        secret_store=self.credentials.secret_store,
                    ).resolve_profile_binding(profile)
                )
                secret = self.credentials.resolve(
                    str(credential["credential_ref"])
                )
            except Exception as exc:
                return (
                    "PROVIDER_ERROR",
                    f"compatible profile binding failed: {exc.__class__.__name__}",
                    0.0,
                )

            def compatible_probe() -> None:
                with build_pinned_client(
                    endpoint=parse_registered_endpoint(endpoint.base_url),
                    resolved_ips=endpoint.resolved_ips,
                    timeout_seconds=profile.timeout_seconds,
                    secret=secret,
                    auth_scheme=endpoint.auth_scheme,
                ) as client:
                    if endpoint.models_endpoint_enabled:
                        response = client.get(
                            f"{endpoint.base_url.rstrip('/')}/models"
                        )
                        if 300 <= response.status_code < 400:
                            raise EndpointSecurityError(
                                "REDIRECT_FORBIDDEN",
                                "credential-bearing provider access cannot redirect",
                            )
                        if response.status_code >= 400:
                            error = RuntimeError("provider model access failed")
                            error.status_code = response.status_code
                            raise error
                        payload = response.json()
                        names = {
                            str(item["id"])
                            for item in payload.get("data", [])
                            if isinstance(item, dict)
                            and isinstance(item.get("id"), str)
                        }
                        if model.remote_model_name not in names:
                            error = RuntimeError("registered model was not found")
                            error.status_code = 404
                            raise error
                    # Endpoints without /models are proven by the paid,
                    # schema-specific capability invocation that follows.

            started = time.perf_counter()
            try:
                await asyncio.to_thread(compatible_probe)
                return "READY", None, (time.perf_counter() - started) * 1000
            except Exception as exc:
                latency = (time.perf_counter() - started) * 1000
                text = f"{exc.__class__.__name__} {exc}".lower()
                status_code = getattr(exc, "status_code", None)
                if status_code == 401:
                    return "UNAUTHORIZED", "provider authentication failed", latency
                if status_code == 403:
                    return (
                        "PROJECT_ACCESS_DENIED",
                        "provider project access was denied",
                        latency,
                    )
                if status_code == 404:
                    return "MODEL_NOT_FOUND", "registered model was not found", latency
                if status_code == 429:
                    return "RATE_LIMITED", "provider rate limit reached", latency
                if "timeout" in text:
                    return "TIMEOUT", "provider access probe timed out", latency
                return (
                    "PROVIDER_ERROR",
                    f"provider access probe failed: {exc.__class__.__name__}",
                    latency,
                )

        if profile.provider.lower() != "openai":
            return "READY", None, 0.0

        def probe() -> None:
            from openai import OpenAI

            client = OpenAI(
                api_key=self.credentials.resolve(profile.credential_ref),
                base_url=profile.base_url,
                timeout=profile.timeout_seconds,
                max_retries=0,
            )
            client.models.retrieve(profile.model_name)

        started = time.perf_counter()
        try:
            await asyncio.to_thread(probe)
            return "READY", None, (time.perf_counter() - started) * 1000
        except Exception as exc:
            latency = (time.perf_counter() - started) * 1000
            text = f"{exc.__class__.__name__} {exc}".lower()
            status_code = getattr(exc, "status_code", None)
            if status_code == 401 or "authentication" in text:
                return (
                    "UNAUTHORIZED",
                    "provider authentication failed; details redacted",
                    latency,
                )
            if status_code == 403:
                return (
                    "PROJECT_ACCESS_DENIED",
                    "provider project access was denied",
                    latency,
                )
            if status_code == 404 or "model_not_found" in text:
                return (
                    "MODEL_NOT_FOUND",
                    "registered provider model was not found",
                    latency,
                )
            if status_code == 429 or "rate limit" in text:
                return "RATE_LIMITED", "provider rate limit reached", latency
            if "timeout" in text or "timed out" in text:
                return "TIMEOUT", "provider access probe timed out", latency
            return (
                "PROVIDER_ERROR",
                f"provider access probe failed: {exc.__class__.__name__}",
                latency,
            )

    async def check(
        self,
        *,
        profile_id: str,
        profile_version: str,
        checked_by: str,
        idempotency_key: str,
        network: bool,
    ) -> ModelCapabilityCheck:
        identity = {
            "profile_id": profile_id,
            "profile_version": profile_version,
            "idempotency_key": idempotency_key,
            "network": network,
        }
        capability_check_id = str(
            uuid5(
                NAMESPACE_URL,
                f"alphaguard:model-capability:{canonical_hash(identity)}",
            )
        )
        existing = await self.repository.get(
            "capability_checks",
            {"capability_check_id": capability_check_id},
        )
        if existing is not None:
            return ModelCapabilityCheck.model_validate(existing)

        checked_at = datetime.now(timezone.utc)
        status = "READY"
        credential_status = "NOT_CONFIGURED"
        registered = False
        prompt_registered = False
        schema_serializable = False
        structured_supported: bool | None = None
        request_hash = None
        response_hash = None
        latency_ms = None
        error_category = None
        error_code = None
        message = None
        try:
            profile = await self.profiles.persisted(
                profile_id, profile_version
            )
            registered = True
            prompt_defined = self.prompts.definition(
                profile.prompt_profile_id
            )
            await self.prompts.persisted(
                prompt_defined.prompt_id,
                prompt_defined.prompt_version,
            )
            prompt_registered = True
            capability_prompt_id, capability_schema = self._capability_contract(
                profile
            )
            capability_prompt_defined = self.prompts.definition(capability_prompt_id)
            capability_prompt = await self.prompts.persisted(
                capability_prompt_defined.prompt_id,
                capability_prompt_defined.prompt_version,
            )
            capability_schema.model_json_schema()
            schema_serializable = True
            if not profile.enabled:
                status = "DISABLED"
                raise RuntimeError("profile is disabled")
            credential_status = (
                "CONFIGURED"
                if self.credentials.configured(profile.credential_ref)
                else "NOT_CONFIGURED"
            )
            if credential_status != "CONFIGURED":
                status = "NOT_CONFIGURED"
                raise CredentialNotConfigured(
                    "model credential is not configured"
                )
            if not network:
                status = "UNVERIFIED"
            else:
                request_hash = canonical_hash(
                    {
                        "operation": "PROVIDER_MODEL_ACCESS_PROBE",
                        "profile_hash": profile.config_hash,
                        "model_name": profile.model_name,
                    }
                )
                access_status, access_message, latency_ms = (
                    await self._provider_access_probe(profile)
                )
                if access_status != "READY":
                    status = access_status
                    error_category = access_status
                    error_code = access_status
                    message = access_message
                else:
                    budget = await self.budget.check(
                        profile=profile,
                        analysis_id=f"capability:{capability_check_id}",
                        snapshot_id=None,
                        rendered_input=capability_prompt.template,
                    )
                    if not budget.allowed:
                        status = "DEGRADED"
                        error_category = "BUDGET_BLOCKED"
                        error_code = budget.reason_code or "BUDGET_BLOCKED"
                        message = "capability call blocked by configured budget"
                    else:
                        model = await self.provider_runtime.create_registered(
                            profile, db=self.db
                        )
                        request_hash = canonical_hash(
                            {
                                "profile_hash": profile.config_hash,
                                "prompt_hash": capability_prompt.template_hash,
                                "schema": capability_schema.model_json_schema(),
                            }
                        )
                        invocation = invoke_json_object(
                            llm=model,
                            messages=[
                                {
                                    "role": "system",
                                    "content": capability_prompt.template,
                                }
                            ],
                            schema_model=capability_schema,
                            provider=profile.provider,
                            configured_model_name=profile.model_name,
                            prompt_name=capability_prompt.prompt_id,
                            prompt_version=capability_prompt.prompt_version,
                            template_hash=capability_prompt.template_hash,
                            input_hash=request_hash,
                            structured_output_mode=profile.structured_output_mode,
                            model_profile_id=profile.profile_id,
                            model_profile_version=profile.profile_version,
                            prompt_id=capability_prompt.prompt_id,
                            input_cost_per_million=profile.input_cost_per_million,
                            output_cost_per_million=profile.output_cost_per_million,
                            cost_currency=profile.cost_currency,
                            max_retries=max(
                                0, budget.permitted_attempts - 1
                            ),
                            retry_backoff_seconds=profile.retry_backoff_seconds,
                        )
                        for meta in invocation.attempt_metas or (
                            invocation.model_meta,
                        ):
                            await self.audit.record(
                                analysis_id=f"capability:{capability_check_id}",
                                snapshot_id=None,
                                context_hash=None,
                                run_mode="MODEL_CAPABILITY_CHECK",
                                automated_execution_allowed=False,
                                role=profile.role,
                                agent_name="model_capability_check",
                                profile=profile,
                                prompt=capability_prompt,
                                request_hash=request_hash,
                                meta=meta,
                            )
                        latency_ms = invocation.model_meta.latency_ms
                        response_hash = invocation.model_meta.raw_output_hash
                        structured_supported = (
                            invocation.failure_status is None
                        )
                        if invocation.failure_status:
                            category = invocation.error_type or "PROVIDER_ERROR"
                            status = (
                                category
                                if category
                                in {
                                    "UNAUTHORIZED",
                                    "PROJECT_ACCESS_DENIED",
                                    "MODEL_NOT_FOUND",
                                    "STRUCTURED_OUTPUT_UNSUPPORTED",
                                    "USAGE_UNAVAILABLE",
                                    "TIMEOUT",
                                    "RATE_LIMITED",
                                    "PROVIDER_ERROR",
                                }
                                else "PROVIDER_ERROR"
                            )
                            error_category = category
                            error_code = category
                            message = invocation.error_message
                        else:
                            payload = dict(invocation.payload or {})
                            payload["model_meta"] = invocation.model_meta.model_dump(
                                mode="json"
                            )
                            capability_schema.model_validate(payload)
                            usage = (
                                invocation.model_meta.input_tokens,
                                invocation.model_meta.output_tokens,
                                invocation.model_meta.total_tokens,
                                invocation.model_meta.estimated_cost,
                            )
                            if any(value is None for value in usage):
                                status = "USAGE_UNAVAILABLE"
                                error_category = "USAGE_UNAVAILABLE"
                                error_code = "USAGE_UNAVAILABLE"
                                message = (
                                    "provider response did not expose complete token "
                                    "usage and auditable cost"
                                )
                            else:
                                status = "READY"
        except CredentialNotConfigured as exc:
            status = "NOT_CONFIGURED"
            error_category = error_category or "MODEL_NOT_CONFIGURED"
            error_code = error_code or "CREDENTIAL_NOT_CONFIGURED"
            message = message or str(exc)
        except (
            ModelProfileNotRegistered,
            PromptProfileNotRegistered,
        ) as exc:
            status = "NOT_CONFIGURED"
            error_category = "MODEL_NOT_CONFIGURED"
            error_code = "PROFILE_OR_PROMPT_NOT_REGISTERED"
            message = str(exc)
        except UnsupportedModelProvider as exc:
            status = "UNSUPPORTED"
            error_category = "UNSUPPORTED_PROVIDER"
            error_code = "UNSUPPORTED_PROVIDER"
            message = str(exc)
        except Exception as exc:
            if status not in {"DISABLED", "DEGRADED"}:
                status = "PROVIDER_ERROR"
            error_category = error_category or "PROVIDER_ERROR"
            error_code = error_code or exc.__class__.__name__
            message = message or str(exc)

        input_hash = canonical_hash(
            {
                **identity,
                "profile_registered": registered,
                "prompt_registered": prompt_registered,
            }
        )
        payload = {
            "capability_check_id": capability_check_id,
            "profile_id": profile_id,
            "profile_version": profile_version,
            "prompt_id": (
                profile.prompt_profile_id
                if registered
                else "unregistered"
            ),
            "prompt_version": (
                prompt_defined.prompt_version
                if prompt_registered
                else "unregistered"
            ),
            "status": status,
            "credential_status": credential_status,
            "model_registered": registered,
            "prompt_registered": prompt_registered,
            "schema_serializable": schema_serializable,
            "structured_output_supported": structured_supported,
            "checked_network": network,
            "request_hash": request_hash,
            "response_hash": response_hash,
            "latency_ms": latency_ms,
            "error_category": error_category,
            "error_code": error_code,
            "sanitized_message": (
                sanitize_model_message(message) if message else None
            ),
            "checked_by": checked_by,
            "checked_at": checked_at,
            "input_hash": input_hash,
        }
        payload["result_hash"] = canonical_hash(
            payload, exclude={"result_hash", "checked_at"}
        )
        check = ModelCapabilityCheck.model_validate(payload)
        saved, _ = await self.repository.save_immutable(
            "capability_checks",
            check,
            identity={"capability_check_id": capability_check_id},
            hash_field="result_hash",
        )
        return saved
