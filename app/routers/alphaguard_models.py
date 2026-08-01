"""Authenticated, non-secret PR-010 model runtime API."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from uuid import uuid4

from app.core.database import get_mongo_db
from app.core.response import ok
from app.routers.auth_db import get_current_user
from app.services.alphaguard.model_capability_service import (
    ModelCapabilityService,
)
from app.services.alphaguard.compatible_provider_registry import (
    CompatibleProviderRegistryService,
    ProviderRegistryConflict,
    ProviderRegistryNotReady,
)
from app.services.alphaguard.model_endpoint_security import EndpointSecurityError
from app.services.alphaguard.model_credential_management_service import (
    CredentialLifecycleConflict,
    CredentialLifecycleNotFound,
    ModelCredentialManagementService,
)
from app.services.alphaguard.model_profile_registry import ModelProfileRegistry
from app.services.alphaguard.model_runtime_repository import (
    ModelRuntimeRepository,
)
from app.services.alphaguard.model_runtime_status_service import (
    ModelRuntimeStatusService,
)
from app.services.alphaguard.model_secret_store import SecretStoreError
from app.services.alphaguard.prompt_profile_registry import PromptProfileRegistry
from app.services.alphaguard.real_model_validation_service import (
    RealModelValidationService,
)


router = APIRouter(prefix="/alphaguard/models", tags=["alphaguard-models"])


class _StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CapabilityCheckBody(_StrictBody):
    profile_id: str = Field(min_length=1, max_length=100)
    profile_version: str = Field(min_length=1, max_length=50)
    idempotency_key: str = Field(min_length=8, max_length=200)
    network: bool = False


class ValidationRunBody(_StrictBody):
    idempotency_key: str = Field(min_length=8, max_length=200)
    proposal_id: str | None = Field(default=None, min_length=1, max_length=200)
    user_id: str | None = Field(default=None, min_length=1, max_length=200)
    confirmation_text: str = Field(min_length=1, max_length=100)


class CredentialCreateBody(_StrictBody):
    provider: str = "openai"
    provider_type: Literal[
        "OPENAI_OFFICIAL", "OPENAI_COMPATIBLE"
    ] = "OPENAI_OFFICIAL"
    endpoint_profile_id: str | None = None
    endpoint_profile_version: str | None = None
    api_key: SecretStr
    base_url: str | None = None
    credential_name: str


class CredentialReplaceBody(_StrictBody):
    api_key: SecretStr
    base_url: str | None = None


class EndpointCreateBody(_StrictBody):
    display_name: str = Field(min_length=1, max_length=120)
    provider_type: Literal["OPENAI_COMPATIBLE"] = "OPENAI_COMPATIBLE"
    base_url: str = Field(min_length=1, max_length=2048)
    api_mode: Literal[
        "OPENAI_CHAT_COMPLETIONS",
        "OPENAI_RESPONSES",
        "AUTO_DETECT",
    ]
    auth_scheme: Literal["BEARER", "X_API_KEY"]
    models_endpoint_enabled: bool = True
    structured_output_mode: Literal[
        "NATIVE_JSON_SCHEMA", "TOOL_CALL", "JSON_ONLY", "UNKNOWN"
    ] = "UNKNOWN"
    notes: str | None = Field(default=None, max_length=500)
    endpoint_profile_id: str | None = Field(default=None, max_length=100)
    profile_version: str = Field(default="v1", min_length=1, max_length=50)
    create_new_version: bool = False


class EndpointValidateBody(_StrictBody):
    profile_version: str = Field(min_length=1, max_length=50)
    confirm_data_transmission: bool


class EndpointDisableBody(_StrictBody):
    profile_version: str = Field(min_length=1, max_length=50)


class EndpointModelCreateBody(_StrictBody):
    endpoint_profile_version: str = Field(min_length=1, max_length=50)
    remote_model_name: str = Field(min_length=1, max_length=200)
    display_name: str = Field(min_length=1, max_length=200)
    role_capabilities: list[
        Literal["RESEARCH_AGENT", "NORMAL_TRADER", "TOP_RISK_REVIEWER"]
    ]
    supports_json_schema: bool
    supports_tool_call: bool
    supports_reasoning: bool | None = None
    max_context_tokens: int | None = Field(default=None, gt=0)
    max_output_tokens: int | None = Field(default=None, gt=0)
    endpoint_model_id: str | None = Field(default=None, max_length=160)
    model_version: str = Field(default="v1", min_length=1, max_length=50)


class EndpointModelDiscoveryBody(_StrictBody):
    endpoint_profile_version: str = Field(min_length=1, max_length=50)
    credential_id: str | None = Field(default=None, min_length=1, max_length=100)


class EndpointModelOptionsBody(_StrictBody):
    endpoint_profile_version: str = Field(min_length=1, max_length=50)
    credential_id: str = Field(min_length=1, max_length=100)


class EndpointPriceCreateBody(_StrictBody):
    endpoint_profile_id: str = Field(min_length=1, max_length=100)
    endpoint_profile_version: str = Field(min_length=1, max_length=50)
    endpoint_model_id: str = Field(min_length=1, max_length=160)
    endpoint_model_version: str = Field(min_length=1, max_length=50)
    pricing_source: Literal["PROVIDER_PUBLISHED", "SELF_HOSTED"] = (
        "PROVIDER_PUBLISHED"
    )
    input_price_per_million: Decimal = Field(ge=0)
    cached_input_price_per_million: Decimal | None = Field(default=None, ge=0)
    output_price_per_million: Decimal = Field(ge=0)
    currency: str = Field(min_length=3, max_length=8)
    effective_at: datetime
    source_description: str = Field(min_length=1, max_length=500)
    verified: bool
    price_version_id: str | None = Field(default=None, max_length=160)
    price_version: str = Field(default="v1", min_length=1, max_length=50)


class CompatibleProfileAssignmentBody(_StrictBody):
    role: Literal["NORMAL_TRADER", "TOP_RISK_REVIEWER"]
    profile_id: str = Field(min_length=1, max_length=100)
    profile_version: str = Field(min_length=1, max_length=50)
    endpoint_profile_id: str = Field(min_length=1, max_length=100)
    endpoint_profile_version: str = Field(min_length=1, max_length=50)
    endpoint_model_id: str = Field(min_length=1, max_length=160)
    endpoint_model_version: str = Field(min_length=1, max_length=50)
    credential_id: str = Field(min_length=1, max_length=100)
    price_version_id: str = Field(min_length=1, max_length=160)
    price_version: str = Field(min_length=1, max_length=50)
    prompt_profile_id: str = Field(min_length=1, max_length=100)
    explicit_same_model_confirmation: bool = False


class SimpleDecisionModelConfigBody(_StrictBody):
    endpoint_profile_id: str = Field(min_length=1, max_length=100)
    endpoint_profile_version: str = Field(min_length=1, max_length=50)
    credential_id: str = Field(min_length=1, max_length=100)
    normal_endpoint_model_id: str = Field(min_length=1, max_length=160)
    normal_endpoint_model_version: str = Field(min_length=1, max_length=50)
    top_endpoint_model_id: str = Field(min_length=1, max_length=160)
    top_endpoint_model_version: str = Field(min_length=1, max_length=50)
    explicit_same_model_confirmation: bool = False


def _require_admin(user: dict[str, Any]) -> None:
    if not user.get("is_admin", False):
        raise HTTPException(
            status_code=403,
            detail="仅管理员可以执行模型能力检查或验证运行",
        )


def _actor(user: dict[str, Any]) -> str:
    return str(
        user.get("user_id")
        or user.get("id")
        or user.get("username")
        or "authenticated-user"
    )


def _trace_id(request: Request) -> str:
    # RequestIdMiddleware owns this value. Credential audit must never persist
    # caller-controlled header content because a client could accidentally put
    # sensitive material in X-Request-ID.
    generated = (
        getattr(request.state, "trace_id", None)
        or getattr(request.state, "request_id", None)
    )
    return str(generated)[:200] if generated else str(uuid4())


async def _require_admin_with_audit(
    *,
    user: dict[str, Any],
    service: ModelCredentialManagementService,
    action: str,
    credential_id: str,
    provider: str,
    trace_id: str,
) -> None:
    if user.get("is_admin", False):
        return
    await service.audit(
        credential_id=(credential_id or "unknown")[:100],
        provider=(provider or "unknown")[:50],
        operator_user_id=_actor(user),
        action="PERMISSION_DENIED",
        status="FAILED",
        error_code=f"{action}_ADMIN_REQUIRED",
        trace_id=trace_id,
    )
    raise HTTPException(status_code=403, detail="仅管理员可以管理模型凭证")


@router.get("/profiles", response_model=dict)
async def model_profiles(
    current_user: dict = Depends(get_current_user),
):
    db = get_mongo_db()
    status = await ModelRuntimeStatusService(db).status(
        admin=bool(current_user.get("is_admin", False))
    )
    return ok({"items": status["profiles"], "status": status["status"]})


@router.get("/profiles/{profile_id}", response_model=dict)
async def model_profile(
    profile_id: str,
    profile_version: str = Query(..., min_length=1),
    current_user: dict = Depends(get_current_user),
):
    status = await ModelRuntimeStatusService(get_mongo_db()).status(
        admin=bool(current_user.get("is_admin", False))
    )
    item = next(
        (
            value
            for value in status["profiles"]
            if value["profile_id"] == profile_id
            and value["profile_version"] == profile_version
        ),
        None,
    )
    if item is None:
        raise HTTPException(status_code=404, detail="ModelProfile不存在")
    return ok(item)


@router.get("/status", response_model=dict)
async def model_status(
    current_user: dict = Depends(get_current_user),
):
    return ok(
        await ModelRuntimeStatusService(get_mongo_db()).status(
            admin=bool(current_user.get("is_admin", False))
        )
    )


@router.get("/prompts", response_model=dict)
async def model_prompts(
    current_user: dict = Depends(get_current_user),
):
    prompts = PromptProfileRegistry(get_mongo_db()).definitions()
    return ok(
        {
            "items": [
                {
                    "prompt_id": item.prompt_id,
                    "prompt_version": item.prompt_version,
                    "role": item.role,
                    "schema_target": item.schema_target,
                    "template_hash": item.template_hash,
                    "enabled": item.enabled,
                }
                for item in prompts
            ]
        }
    )


def _provider_http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ProviderRegistryConflict):
        return HTTPException(
            status_code=409,
            detail={
                "error_code": "INTEGRITY_CONFLICT",
                "sanitized_message": str(exc),
            },
        )
    if isinstance(exc, ProviderRegistryNotReady):
        return HTTPException(
            status_code=409,
            detail={
                "error_code": "CONFIGURATION_NOT_READY",
                "sanitized_message": str(exc),
            },
        )
    if isinstance(exc, EndpointSecurityError):
        return HTTPException(
            status_code=400,
            detail={
                "error_code": exc.code,
                "sanitized_message": str(exc),
            },
        )
    return HTTPException(
        status_code=400,
        detail={
            "error_code": "INVALID_CONFIGURATION",
            "sanitized_message": str(exc),
        },
    )


@router.get("/endpoints", response_model=dict)
async def model_endpoints(
    current_user: dict = Depends(get_current_user),
):
    items = await CompatibleProviderRegistryService(
        get_mongo_db()
    ).list_endpoints()
    if not current_user.get("is_admin", False):
        allowed = {
            "endpoint_profile_id",
            "profile_version",
            "provider_type",
            "display_name",
            "state",
            "enabled",
            "url_validation_status",
            "structured_output_mode",
            "production_allowed",
            "system_managed",
        }
        items = [
            {key: value for key, value in item.items() if key in allowed}
            for item in items
        ]
    return ok({"items": items})


@router.post("/endpoints", response_model=dict)
async def create_model_endpoint(
    body: EndpointCreateBody,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    credential_service = ModelCredentialManagementService(get_mongo_db())
    trace_id = _trace_id(request)
    await _require_admin_with_audit(
        user=current_user,
        service=credential_service,
        action="ENDPOINT_CREATE",
        credential_id=body.endpoint_profile_id or "new-compatible-endpoint",
        provider="openai_compatible",
        trace_id=trace_id,
    )
    try:
        endpoint, created = await CompatibleProviderRegistryService(
            get_mongo_db()
        ).register_endpoint(
            display_name=body.display_name,
            base_url=body.base_url,
            api_mode=body.api_mode,
            auth_scheme=body.auth_scheme,
            models_endpoint_enabled=body.models_endpoint_enabled,
            structured_output_mode=body.structured_output_mode,
            notes=body.notes,
            created_by=_actor(current_user),
            endpoint_profile_id=body.endpoint_profile_id,
            profile_version=body.profile_version,
            create_new_version=body.create_new_version,
        )
        return ok(
            {
                "item": endpoint.model_dump(mode="json"),
                "result": "CREATED" if created else "REUSED",
            }
        )
    except (
        ValueError,
        ProviderRegistryConflict,
        ProviderRegistryNotReady,
    ) as exc:
        raise _provider_http_error(exc) from exc


@router.get("/endpoints/{endpoint_profile_id}", response_model=dict)
async def model_endpoint(
    endpoint_profile_id: str,
    profile_version: str = Query(..., min_length=1, max_length=50),
    current_user: dict = Depends(get_current_user),
):
    try:
        endpoint = await CompatibleProviderRegistryService(
            get_mongo_db()
        ).endpoint(endpoint_profile_id, profile_version)
    except ProviderRegistryNotReady as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    item = endpoint.model_dump(mode="json")
    if not current_user.get("is_admin", False):
        item = {
            key: item[key]
            for key in (
                "endpoint_profile_id",
                "profile_version",
                "provider_type",
                "display_name",
                "state",
                "enabled",
                "url_validation_status",
                "structured_output_mode",
                "production_allowed",
            )
        }
    return ok(item)


@router.get(
    "/endpoints/{endpoint_profile_id}/configuration-status",
    response_model=dict,
)
async def endpoint_configuration_status(
    endpoint_profile_id: str,
    profile_version: str = Query(..., min_length=1, max_length=50),
    current_user: dict = Depends(get_current_user),
):
    try:
        status = await CompatibleProviderRegistryService(
            get_mongo_db()
        ).configuration_status(endpoint_profile_id, profile_version)
    except ProviderRegistryNotReady as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not current_user.get("is_admin", False):
        status = {
            "endpoint_profile_id": status["endpoint_profile_id"],
            "endpoint_profile_version": status["endpoint_profile_version"],
            "stage": status["stage"],
            "production_allowed": status["production_allowed"],
            "components": [
                {
                    "key": item["key"],
                    "label": item["label"],
                    "complete": item["complete"],
                    "status": item["status"],
                }
                for item in status["components"]
            ],
            "blocking_items": status["blocking_items"],
        }
    return ok(status)


@router.post("/endpoints/{endpoint_profile_id}/validate", response_model=dict)
async def validate_model_endpoint(
    endpoint_profile_id: str,
    body: EndpointValidateBody,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    credential_service = ModelCredentialManagementService(get_mongo_db())
    trace_id = _trace_id(request)
    await _require_admin_with_audit(
        user=current_user,
        service=credential_service,
        action="ENDPOINT_VALIDATE",
        credential_id=endpoint_profile_id,
        provider="openai_compatible",
        trace_id=trace_id,
    )
    try:
        endpoint = await CompatibleProviderRegistryService(
            get_mongo_db()
        ).validate_endpoint(
            endpoint_profile_id=endpoint_profile_id,
            profile_version=body.profile_version,
            confirm_data_transmission=body.confirm_data_transmission,
            operator_user_id=_actor(current_user),
            trace_id=trace_id,
        )
        return ok(endpoint.model_dump(mode="json"))
    except (ValueError, ProviderRegistryNotReady, ProviderRegistryConflict) as exc:
        raise _provider_http_error(exc) from exc


@router.post("/endpoints/{endpoint_profile_id}/disable", response_model=dict)
async def disable_model_endpoint(
    endpoint_profile_id: str,
    body: EndpointDisableBody,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    credential_service = ModelCredentialManagementService(get_mongo_db())
    trace_id = _trace_id(request)
    await _require_admin_with_audit(
        user=current_user,
        service=credential_service,
        action="ENDPOINT_DISABLE",
        credential_id=endpoint_profile_id,
        provider="openai_compatible",
        trace_id=trace_id,
    )
    try:
        endpoint = await CompatibleProviderRegistryService(
            get_mongo_db()
        ).disable_endpoint(
            endpoint_profile_id=endpoint_profile_id,
            profile_version=body.profile_version,
            operator_user_id=_actor(current_user),
            trace_id=trace_id,
        )
        return ok(endpoint.model_dump(mode="json"))
    except (ProviderRegistryNotReady, ProviderRegistryConflict) as exc:
        raise _provider_http_error(exc) from exc


@router.get("/endpoints/{endpoint_profile_id}/models", response_model=dict)
async def endpoint_models(
    endpoint_profile_id: str,
    profile_version: str | None = Query(default=None, max_length=50),
    current_user: dict = Depends(get_current_user),
):
    items = await CompatibleProviderRegistryService(
        get_mongo_db()
    ).list_models(endpoint_profile_id, profile_version)
    return ok({"items": items})


@router.post("/endpoints/{endpoint_profile_id}/models", response_model=dict)
async def create_endpoint_model(
    endpoint_profile_id: str,
    body: EndpointModelCreateBody,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    credential_service = ModelCredentialManagementService(get_mongo_db())
    trace_id = _trace_id(request)
    await _require_admin_with_audit(
        user=current_user,
        service=credential_service,
        action="ENDPOINT_MODEL_CREATE",
        credential_id=endpoint_profile_id,
        provider="openai_compatible",
        trace_id=trace_id,
    )
    try:
        model, created = await CompatibleProviderRegistryService(
            get_mongo_db()
        ).register_model(
            endpoint_profile_id=endpoint_profile_id,
            endpoint_profile_version=body.endpoint_profile_version,
            remote_model_name=body.remote_model_name,
            display_name=body.display_name,
            role_capabilities=list(body.role_capabilities),
            supports_json_schema=body.supports_json_schema,
            supports_tool_call=body.supports_tool_call,
            supports_reasoning=body.supports_reasoning,
            max_context_tokens=body.max_context_tokens,
            max_output_tokens=body.max_output_tokens,
            created_by=_actor(current_user),
            endpoint_model_id=body.endpoint_model_id,
            model_version=body.model_version,
            status="UNVERIFIED",
        )
        return ok(
            {
                "item": model.model_dump(mode="json"),
                "result": "CREATED" if created else "REUSED",
            }
        )
    except (ValueError, ProviderRegistryNotReady, ProviderRegistryConflict) as exc:
        raise _provider_http_error(exc) from exc


@router.post(
    "/endpoints/{endpoint_profile_id}/models/options", response_model=dict
)
async def endpoint_model_options(
    endpoint_profile_id: str,
    body: EndpointModelOptionsBody,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    credential_service = ModelCredentialManagementService(get_mongo_db())
    trace_id = _trace_id(request)
    await _require_admin_with_audit(
        user=current_user,
        service=credential_service,
        action="ENDPOINT_MODEL_OPTIONS",
        credential_id=body.credential_id,
        provider="openai_compatible",
        trace_id=trace_id,
    )
    try:
        names = await CompatibleProviderRegistryService(
            get_mongo_db(), secret_store=credential_service.secret_store
        ).model_options(
            endpoint_profile_id=endpoint_profile_id,
            endpoint_profile_version=body.endpoint_profile_version,
            credential_id=body.credential_id,
        )
        return ok(
            {
                "items": [
                    {"remote_model_name": name, "display_name": name}
                    for name in names
                ],
                "source": "MODELS_ENDPOINT",
                "status": "READY" if names else "EMPTY",
            }
        )
    except Exception as exc:
        if isinstance(
            exc,
            (
                ValueError,
                ProviderRegistryNotReady,
                ProviderRegistryConflict,
                EndpointSecurityError,
            ),
        ):
            raise _provider_http_error(exc) from exc
        raise HTTPException(
            status_code=502,
            detail=f"provider model options failed: {exc.__class__.__name__}",
        ) from exc


@router.post(
    "/endpoints/{endpoint_profile_id}/models/discover", response_model=dict
)
async def discover_endpoint_models(
    endpoint_profile_id: str,
    body: EndpointModelDiscoveryBody,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    credential_service = ModelCredentialManagementService(get_mongo_db())
    trace_id = _trace_id(request)
    await _require_admin_with_audit(
        user=current_user,
        service=credential_service,
        action="ENDPOINT_MODEL_DISCOVERY",
        credential_id=body.credential_id or endpoint_profile_id,
        provider="openai_compatible",
        trace_id=trace_id,
    )
    try:
        items = await CompatibleProviderRegistryService(
            get_mongo_db(), secret_store=credential_service.secret_store
        ).discover_models(
            endpoint_profile_id=endpoint_profile_id,
            endpoint_profile_version=body.endpoint_profile_version,
            credential_id=body.credential_id,
            operator_user_id=_actor(current_user),
            trace_id=trace_id,
        )
        return ok({"items": [item.model_dump(mode="json") for item in items]})
    except Exception as exc:
        if isinstance(
            exc,
            (
                ValueError,
                ProviderRegistryNotReady,
                ProviderRegistryConflict,
                EndpointSecurityError,
            ),
        ):
            raise _provider_http_error(exc) from exc
        raise HTTPException(
            status_code=502,
            detail=f"provider model discovery failed: {exc.__class__.__name__}",
        ) from exc


@router.get("/prices", response_model=dict)
async def endpoint_prices(
    endpoint_profile_id: str | None = Query(default=None, max_length=100),
    current_user: dict = Depends(get_current_user),
):
    items = await CompatibleProviderRegistryService(
        get_mongo_db()
    ).list_prices(endpoint_profile_id)
    return ok({"items": items})


@router.post("/prices", response_model=dict)
async def create_endpoint_price(
    body: EndpointPriceCreateBody,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    credential_service = ModelCredentialManagementService(get_mongo_db())
    trace_id = _trace_id(request)
    await _require_admin_with_audit(
        user=current_user,
        service=credential_service,
        action="ENDPOINT_PRICE_CREATE",
        credential_id=body.endpoint_profile_id,
        provider="openai_compatible",
        trace_id=trace_id,
    )
    try:
        price, created = await CompatibleProviderRegistryService(
            get_mongo_db()
        ).register_price(
            **body.model_dump(mode="python"),
            created_by=_actor(current_user),
        )
        return ok(
            {
                "item": price.model_dump(mode="json"),
                "result": "CREATED" if created else "REUSED",
            }
        )
    except (ValueError, ProviderRegistryNotReady, ProviderRegistryConflict) as exc:
        raise _provider_http_error(exc) from exc


@router.post("/profiles/compatible", response_model=dict)
async def create_compatible_profile_assignment(
    body: CompatibleProfileAssignmentBody,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    credential_service = ModelCredentialManagementService(get_mongo_db())
    trace_id = _trace_id(request)
    await _require_admin_with_audit(
        user=current_user,
        service=credential_service,
        action="MODEL_PROFILE_ASSIGN",
        credential_id=body.credential_id,
        provider="openai_compatible",
        trace_id=trace_id,
    )
    try:
        profile, assignment = await CompatibleProviderRegistryService(
            get_mongo_db()
        ).register_profile_assignment(
            **body.model_dump(mode="python"),
            assigned_by=_actor(current_user),
        )
        return ok(
            {
                "profile": profile.model_dump(mode="json"),
                "assignment": assignment.model_dump(mode="json"),
            }
        )
    except (ValueError, ProviderRegistryNotReady, ProviderRegistryConflict) as exc:
        raise _provider_http_error(exc) from exc


@router.post("/profiles/decision-models", response_model=dict)
async def configure_decision_models(
    body: SimpleDecisionModelConfigBody,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    credential_service = ModelCredentialManagementService(get_mongo_db())
    await _require_admin_with_audit(
        user=current_user,
        service=credential_service,
        action="DECISION_MODELS_CONFIGURE",
        credential_id=body.credential_id,
        provider="openai_compatible",
        trace_id=_trace_id(request),
    )
    try:
        return ok(
            await CompatibleProviderRegistryService(
                get_mongo_db()
            ).configure_decision_models(
                **body.model_dump(mode="python"),
                assigned_by=_actor(current_user),
            )
        )
    except (ValueError, ProviderRegistryNotReady, ProviderRegistryConflict) as exc:
        raise _provider_http_error(exc) from exc


@router.get("/credentials", response_model=dict)
async def model_credentials(
    current_user: dict = Depends(get_current_user),
):
    # Admin and ordinary users receive the same deliberately non-secret
    # projection. Mutation routes still enforce database-backed is_admin.
    service = ModelCredentialManagementService(get_mongo_db())
    return ok(
        {
            "items": await service.list_public(),
            "secret_store_status": service.secret_store_status,
        }
    )


@router.post("/credentials", response_model=dict)
async def create_model_credential(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    try:
        body = CredentialCreateBody.model_validate(await request.json())
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "INVALID_CREDENTIAL_REQUEST",
                "sanitized_message": "凭证请求格式无效；未保存任何数据",
            },
        ) from exc
    service = ModelCredentialManagementService(get_mongo_db())
    trace_id = _trace_id(request)
    await _require_admin_with_audit(
        user=current_user,
        service=service,
        action="CREDENTIAL_CREATE",
        credential_id=body.credential_name,
        provider=body.provider,
        trace_id=trace_id,
    )
    secret = body.api_key.get_secret_value()
    body.api_key = SecretStr("")
    try:
        result = await service.create(
            credential_id=body.credential_name,
            provider=body.provider,
            secret=secret,
            base_url=body.base_url,
            operator_user_id=_actor(current_user),
            trace_id=trace_id,
            provider_type=body.provider_type,
            endpoint_profile_id=body.endpoint_profile_id,
            endpoint_profile_version=body.endpoint_profile_version,
        )
        return ok(result.model_dump(mode="json"))
    except CredentialLifecycleConflict as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": "CREDENTIAL_BINDING_EXISTS",
                "sanitized_message": str(exc),
            },
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "INVALID_CREDENTIAL_BINDING",
                "sanitized_message": str(exc),
            },
        ) from exc
    except SecretStoreError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "error_code": "SECRET_STORE_UNAVAILABLE",
                "sanitized_message": "安全Secret Store不可用；凭证未保存",
            },
        ) from exc
    finally:
        secret = ""


@router.put("/credentials/{credential_id}", response_model=dict)
async def replace_model_credential(
    credential_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    try:
        body = CredentialReplaceBody.model_validate(await request.json())
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "INVALID_CREDENTIAL_REQUEST",
                "sanitized_message": "凭证请求格式无效；原凭证保持不变",
            },
        ) from exc
    service = ModelCredentialManagementService(get_mongo_db())
    trace_id = _trace_id(request)
    await _require_admin_with_audit(
        user=current_user,
        service=service,
        action="CREDENTIAL_REPLACE",
        credential_id=credential_id,
        provider="unknown",
        trace_id=trace_id,
    )
    secret = body.api_key.get_secret_value()
    body.api_key = SecretStr("")
    try:
        result = await service.replace(
            credential_id=credential_id,
            secret=secret,
            base_url=body.base_url,
            operator_user_id=_actor(current_user),
            trace_id=trace_id,
        )
        return ok(result.model_dump(mode="json"))
    except CredentialLifecycleConflict as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": "CREDENTIAL_NOT_REPLACEABLE",
                "sanitized_message": str(exc),
            },
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "INVALID_CREDENTIAL_BINDING",
                "sanitized_message": str(exc),
            },
        ) from exc
    except SecretStoreError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "error_code": "SECRET_STORE_UNAVAILABLE",
                "sanitized_message": "安全Secret Store操作失败；原凭证保持不变",
            },
        ) from exc
    finally:
        secret = ""


@router.post("/credentials/{credential_id}/verify", response_model=dict)
async def verify_model_credential(
    credential_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    service = ModelCredentialManagementService(get_mongo_db())
    trace_id = _trace_id(request)
    await _require_admin_with_audit(
        user=current_user,
        service=service,
        action="CREDENTIAL_VERIFY",
        credential_id=credential_id,
        provider="unknown",
        trace_id=trace_id,
    )
    try:
        result = await service.verify(
            credential_id=credential_id,
            operator_user_id=_actor(current_user),
            trace_id=trace_id,
        )
        return ok(result.model_dump(mode="json"))
    except CredentialLifecycleConflict as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/credentials/{credential_id}", response_model=dict)
async def revoke_model_credential(
    credential_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    service = ModelCredentialManagementService(get_mongo_db())
    trace_id = _trace_id(request)
    await _require_admin_with_audit(
        user=current_user,
        service=service,
        action="CREDENTIAL_REVOKE",
        credential_id=credential_id,
        provider="unknown",
        trace_id=trace_id,
    )
    try:
        return ok(
            await service.revoke(
                credential_id=credential_id,
                operator_user_id=_actor(current_user),
                trace_id=trace_id,
            )
        )
    except CredentialLifecycleNotFound as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": "CREDENTIAL_NOT_FOUND",
                "sanitized_message": "API 密钥记录不存在",
            },
        ) from exc
    except CredentialLifecycleConflict as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": "CREDENTIAL_LIFECYCLE_CONFLICT",
                "sanitized_message": "API 密钥状态已发生变化，请刷新后重试",
            },
        ) from exc
    except SecretStoreError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "error_code": "SECRET_STORE_UNAVAILABLE",
                "sanitized_message": "安全 Secret Store 操作失败；请稍后重试",
            },
        ) from exc


@router.get("/runs", response_model=dict)
async def model_runs(
    limit: int = Query(default=100, ge=1, le=500),
    run_mode: str | None = None,
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    query = {"run_mode": run_mode} if run_mode else {}
    items = await ModelRuntimeRepository(get_mongo_db()).list(
        "runs", query, sort=("created_at", -1), limit=limit
    )
    return ok({"items": items})


@router.get("/runs/{model_run_id}", response_model=dict)
async def model_run(
    model_run_id: str,
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    item = await ModelRuntimeRepository(get_mongo_db()).get(
        "runs", {"model_run_id": model_run_id}
    )
    if item is None:
        raise HTTPException(status_code=404, detail="模型运行记录不存在")
    return ok(item)


@router.get("/snapshots/{snapshot_id}/runs", response_model=dict)
async def model_snapshot_runs(
    snapshot_id: str,
    current_user: dict = Depends(get_current_user),
):
    db = get_mongo_db()
    snapshot = await db["ag_evidence_snapshots"].find_one(
        {"snapshot_id": snapshot_id}
    )
    if snapshot is None:
        raise HTTPException(status_code=404, detail="EvidenceSnapshot不存在")
    if not current_user.get("is_admin", False):
        owner = str(snapshot.get("user_id") or "")
        if owner != _actor(current_user):
            raise HTTPException(status_code=403, detail="无权查看该模型链")
    repository = ModelRuntimeRepository(db)
    runs = await repository.list(
        "runs",
        {"snapshot_id": snapshot_id},
        sort=("created_at", 1),
        limit=200,
    )
    research = await repository.list(
        "research_results",
        {"snapshot_id": snapshot_id},
        sort=("created_at", 1),
        limit=50,
    )
    return ok({"runs": runs, "research": research})


@router.post("/capability-check", response_model=dict)
async def model_capability_check(
    body: CapabilityCheckBody,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    credential_service = ModelCredentialManagementService(get_mongo_db())
    await _require_admin_with_audit(
        user=current_user,
        service=credential_service,
        action="CAPABILITY_CHECK",
        credential_id="profile-bound",
        provider="unknown",
        trace_id=_trace_id(request),
    )
    result = await ModelCapabilityService(get_mongo_db()).check(
        profile_id=body.profile_id,
        profile_version=body.profile_version,
        checked_by=_actor(current_user),
        idempotency_key=body.idempotency_key,
        network=body.network,
    )
    return ok(
        result.model_dump(
            mode="json",
            exclude={
                "request_hash",
                "response_hash",
            },
        )
    )


@router.post("/validation-run", response_model=dict)
async def model_validation_run(
    body: ValidationRunBody,
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    if body.confirmation_text != "RUN NON-EXECUTABLE MODEL VALIDATION":
        raise HTTPException(status_code=400, detail="验证确认文本不正确")
    result = await RealModelValidationService(get_mongo_db()).run(
        requested_by=_actor(current_user),
        idempotency_key=body.idempotency_key,
        proposal_id=body.proposal_id,
        user_id=body.user_id,
    )
    return ok(result.model_dump(mode="json"))
