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

    async def _provider_access_probe(
        self, profile
    ) -> tuple[str, str | None, float]:
        """Use a no-generation provider endpoint before any paid schema call."""

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
            if status_code in {401, 403} or "authentication" in text:
                return (
                    "UNAUTHORIZED",
                    "provider authentication failed; details redacted",
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
            capability_prompt_defined = self.prompts.definition(
                "model_capability_prompt"
            )
            capability_prompt = await self.prompts.persisted(
                capability_prompt_defined.prompt_id,
                capability_prompt_defined.prompt_version,
            )
            CapabilityEcho.model_json_schema()
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
                        model = self.provider_runtime.create(profile)
                        request_hash = canonical_hash(
                            {
                                "profile_hash": profile.config_hash,
                                "prompt_hash": capability_prompt.template_hash,
                                "schema": CapabilityEcho.model_json_schema(),
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
                            schema_model=CapabilityEcho,
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
                                    "MODEL_NOT_FOUND",
                                    "STRUCTURED_OUTPUT_UNSUPPORTED",
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
                            CapabilityEcho.model_validate(invocation.payload)
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
