"""Versioned, secret-free contracts for the AlphaGuard model runtime."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


ModelRole = Literal["RESEARCH_AGENT", "NORMAL_TRADER", "TOP_RISK_REVIEWER"]
StructuredOutputMode = Literal["NATIVE_SCHEMA", "TOOL_CALL", "JSON_SCHEMA"]
ProviderType = Literal["OPENAI_OFFICIAL", "OPENAI_COMPATIBLE"]
EndpointApiMode = Literal[
    "OPENAI_CHAT_COMPLETIONS",
    "OPENAI_RESPONSES",
    "AUTO_DETECT",
]
EndpointAuthScheme = Literal["BEARER", "X_API_KEY"]
EndpointState = Literal[
    "DRAFT",
    "URL_VALIDATED",
    "CAPABILITY_CHECKED",
    "READY",
    "DEGRADED",
    "DISABLED",
    "REJECTED",
]
EndpointStructuredOutputMode = Literal[
    "NATIVE_JSON_SCHEMA",
    "TOOL_CALL",
    "JSON_ONLY",
    "UNKNOWN",
]
CapabilityStatus = Literal[
    "UNVERIFIED",
    "READY",
    "NOT_CONFIGURED",
    "UNAUTHORIZED",
    "PROJECT_ACCESS_DENIED",
    "MODEL_NOT_FOUND",
    "STRUCTURED_OUTPUT_UNSUPPORTED",
    "INVALID_OUTPUT",
    "USAGE_UNAVAILABLE",
    "TIMEOUT",
    "RATE_LIMITED",
    "PROVIDER_ERROR",
    "PRICE_NOT_VERIFIED",
    "BUDGET_BLOCKED",
    "UNSUPPORTED",
    "DEGRADED",
    "DISABLED",
]
CredentialStatus = Literal[
    "CONFIGURED",
    "DEGRADED",
    "REVOKED",
]
ModelRunMode = Literal[
    "MODEL_CAPABILITY_CHECK",
    "REAL_MODEL_VALIDATION",
    "PRODUCTION",
    "PRODUCTION_REPROCESS",
    "RESEARCH_REPLAY",
    "DEMO",
]


class _StrictFrozenModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        allow_inf_nan=False,
    )


class ModelProfile(_StrictFrozenModel):
    profile_id: str = Field(min_length=1)
    profile_version: str = Field(min_length=1)
    role: ModelRole
    provider: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    model_version: str | None = None
    base_url: str | None = None
    structured_output_mode: StructuredOutputMode
    temperature: float = Field(ge=0, le=2)
    max_input_tokens: int = Field(gt=0)
    max_output_tokens: int = Field(gt=0)
    timeout_seconds: int = Field(gt=0, le=600)
    max_retries: int = Field(ge=0, le=5)
    retry_backoff_seconds: float = Field(ge=0, le=60)
    credential_ref: str = Field(min_length=1)
    prompt_profile_id: str = Field(min_length=1)
    provider_type: ProviderType = "OPENAI_OFFICIAL"
    endpoint_profile_id: str | None = None
    endpoint_profile_version: str | None = None
    endpoint_model_id: str | None = None
    endpoint_model_version: str | None = None
    credential_id: str | None = None
    price_version_id: str | None = None
    normalized_origin: str | None = None
    auth_scheme: EndpointAuthScheme | None = None
    input_cost_per_million: float | None = Field(default=None, ge=0)
    output_cost_per_million: float | None = Field(default=None, ge=0)
    cost_currency: str = Field(default="USD", min_length=3, max_length=8)
    enabled: bool
    production_allowed: bool
    research_allowed: bool
    capability_status: Literal[
        "UNVERIFIED",
        "NOT_CONFIGURED",
        "DISABLED",
    ] = "UNVERIFIED"
    config_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime
    schema_version: str = "model_profile_v1"

    @model_validator(mode="after")
    def validate_registered_compatible_binding(self) -> "ModelProfile":
        binding = (
            self.endpoint_profile_id,
            self.endpoint_profile_version,
            self.endpoint_model_id,
            self.endpoint_model_version,
            self.credential_id,
            self.price_version_id,
            self.normalized_origin,
            self.auth_scheme,
        )
        if self.provider_type == "OPENAI_COMPATIBLE":
            if not all(binding):
                raise ValueError(
                    "compatible ModelProfile requires an exact endpoint, "
                    "model, credential, price, origin and auth binding"
                )
            if self.provider != "openai_compatible":
                raise ValueError(
                    "compatible ModelProfile provider must be openai_compatible"
                )
        elif any(binding):
            raise ValueError(
                "official ModelProfile cannot carry compatible endpoint binding"
            )
        return self


class ProviderEndpointProfile(_StrictFrozenModel):
    endpoint_profile_id: str = Field(min_length=1, max_length=100)
    profile_version: str = Field(min_length=1, max_length=50)
    provider_type: ProviderType
    display_name: str = Field(min_length=1, max_length=120)
    base_url: str = Field(min_length=1, max_length=2048)
    normalized_origin: str = Field(min_length=1, max_length=512)
    api_mode: EndpointApiMode
    auth_scheme: EndpointAuthScheme
    models_endpoint_enabled: bool
    structured_output_mode: EndpointStructuredOutputMode
    state: EndpointState
    enabled: bool
    validation_allowed: bool
    production_allowed: bool
    resolved_ips: list[str] = Field(default_factory=list, max_length=32)
    url_validation_status: Literal[
        "NOT_CHECKED", "PASS", "REJECTED"
    ] = "NOT_CHECKED"
    last_error_code: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=500)
    data_transmission_confirmed: bool = False
    data_transmission_confirmed_by: str | None = None
    data_transmission_confirmed_at: datetime | None = None
    created_by: str = Field(min_length=1, max_length=200)
    created_at: datetime
    config_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    schema_version: str = "provider_endpoint_profile_v1"

    @model_validator(mode="after")
    def validate_official_endpoint(self) -> "ProviderEndpointProfile":
        if self.provider_type == "OPENAI_OFFICIAL" and (
            self.base_url.rstrip("/") != "https://api.openai.com/v1"
            or self.normalized_origin != "https://api.openai.com"
        ):
            raise ValueError("official OpenAI endpoint URL is system-fixed")
        if self.production_allowed and (
            not self.enabled
            or self.state != "READY"
            or self.url_validation_status != "PASS"
        ):
            raise ValueError("production endpoint must be enabled and READY")
        if self.data_transmission_confirmed and (
            not self.data_transmission_confirmed_by
            or not self.data_transmission_confirmed_at
        ):
            raise ValueError("third-party data transmission confirmation is incomplete")
        return self


class EndpointModelDefinition(_StrictFrozenModel):
    endpoint_model_id: str = Field(min_length=1, max_length=160)
    model_version: str = Field(min_length=1, max_length=50)
    endpoint_profile_id: str = Field(min_length=1, max_length=100)
    endpoint_profile_version: str = Field(min_length=1, max_length=50)
    remote_model_name: str = Field(min_length=1, max_length=200)
    display_name: str = Field(min_length=1, max_length=200)
    role_capabilities: list[ModelRole] = Field(default_factory=list)
    supports_json_schema: bool
    supports_tool_call: bool
    supports_reasoning: bool | None = None
    max_context_tokens: int | None = Field(default=None, gt=0)
    max_output_tokens: int | None = Field(default=None, gt=0)
    discovery_mode: Literal["MODELS_ENDPOINT", "MANUAL"]
    status: Literal[
        "UNVERIFIED",
        "READY",
        "UNSUPPORTED",
        "NOT_FOUND",
        "DISABLED",
    ]
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_by: str = Field(min_length=1, max_length=200)
    created_at: datetime
    schema_version: str = "endpoint_model_definition_v1"


class EndpointPriceVersion(_StrictFrozenModel):
    price_version_id: str = Field(min_length=1, max_length=160)
    price_version: str = Field(min_length=1, max_length=50)
    endpoint_profile_id: str = Field(min_length=1, max_length=100)
    endpoint_profile_version: str = Field(min_length=1, max_length=50)
    endpoint_model_id: str = Field(min_length=1, max_length=160)
    endpoint_model_version: str = Field(min_length=1, max_length=50)
    pricing_mode: Literal["FIXED_PER_1M"] = "FIXED_PER_1M"
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
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_by: str = Field(min_length=1, max_length=200)
    created_at: datetime
    schema_version: str = "endpoint_price_version_v1"

    @model_validator(mode="after")
    def validate_pricing_source(self) -> "EndpointPriceVersion":
        if self.pricing_source == "SELF_HOSTED":
            if (
                self.input_price_per_million != 0
                or self.cached_input_price_per_million != 0
                or self.output_price_per_million != 0
            ):
                raise ValueError(
                    "SELF_HOSTED pricing requires all token prices to be zero"
                )
        elif (
            self.input_price_per_million <= 0
            or self.output_price_per_million <= 0
        ):
            raise ValueError(
                "external provider pricing requires positive input and output prices"
            )
        return self


class ModelProfileAssignment(_StrictFrozenModel):
    assignment_id: str = Field(min_length=1, max_length=160)
    role: Literal["NORMAL_TRADER", "TOP_RISK_REVIEWER"]
    profile_id: str = Field(min_length=1, max_length=100)
    profile_version: str = Field(min_length=1, max_length=50)
    supersedes_assignment_id: str | None = None
    status: Literal["ACTIVE"] = "ACTIVE"
    explicit_same_model_confirmation: bool = False
    assigned_by: str = Field(min_length=1, max_length=200)
    assigned_at: datetime
    assignment_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    schema_version: str = "model_profile_assignment_v1"


class EndpointValidationEvent(_StrictFrozenModel):
    validation_event_id: str = Field(min_length=1, max_length=160)
    endpoint_profile_id: str = Field(min_length=1, max_length=100)
    endpoint_profile_version: str = Field(min_length=1, max_length=50)
    action: str = Field(min_length=1, max_length=100)
    status: str = Field(min_length=1, max_length=100)
    error_code: str | None = Field(default=None, max_length=100)
    operator_user_id: str = Field(min_length=1, max_length=200)
    trace_id: str = Field(min_length=1, max_length=200)
    created_at: datetime
    event_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    schema_version: str = "endpoint_validation_event_v1"


class PromptProfile(_StrictFrozenModel):
    prompt_id: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    role: str = Field(min_length=1)
    template: str = Field(min_length=1)
    template_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    schema_target: str = Field(min_length=1)
    enabled: bool
    created_at: datetime
    schema_version: str = "prompt_profile_v1"


class ModelBudgetPolicy(_StrictFrozenModel):
    policy_id: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    max_input_tokens_per_call: int = Field(gt=0)
    max_output_tokens_per_call: int = Field(gt=0)
    max_calls_per_analysis: int = Field(gt=0)
    max_tokens_per_snapshot: int = Field(gt=0)
    max_daily_calls: int = Field(gt=0)
    max_daily_cost: float = Field(gt=0)
    currency: str = Field(min_length=1)
    policy_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime
    schema_version: str = "model_budget_policy_v1"


class ModelCapabilityCheck(_StrictFrozenModel):
    capability_check_id: str = Field(min_length=1)
    profile_id: str = Field(min_length=1)
    profile_version: str = Field(min_length=1)
    prompt_id: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    run_mode: Literal["MODEL_CAPABILITY_CHECK"] = "MODEL_CAPABILITY_CHECK"
    automated_execution_allowed: Literal[False] = False
    status: CapabilityStatus
    credential_status: Literal["CONFIGURED", "NOT_CONFIGURED"]
    model_registered: bool
    prompt_registered: bool
    schema_serializable: bool
    structured_output_supported: bool | None
    checked_network: bool
    request_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    response_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    latency_ms: float | None = Field(default=None, ge=0)
    error_category: str | None = None
    error_code: str | None = None
    sanitized_message: str | None = None
    validation_error_count: int | None = Field(default=None, ge=1)
    validation_missing_field_count: int | None = Field(default=None, ge=0)
    validation_error_fields: tuple[str, ...] = ()
    validation_error_types: tuple[str, ...] = ()
    checked_by: str
    checked_at: datetime
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    result_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    schema_version: str = "model_capability_check_v1"


class ModelCredentialMetadata(_StrictFrozenModel):
    """Mongo-safe metadata; no Secret or Secret-derived attributes."""

    credential_id: str = Field(min_length=1, max_length=100)
    provider: str = Field(min_length=1, max_length=50)
    credential_ref: str = Field(min_length=1, max_length=300)
    provider_type: ProviderType = "OPENAI_OFFICIAL"
    endpoint_profile_id: str | None = None
    endpoint_profile_version: str | None = None
    normalized_origin: str | None = None
    auth_scheme: EndpointAuthScheme | None = None
    status: CredentialStatus
    created_by: str = Field(min_length=1, max_length=200)
    created_at: datetime
    updated_at: datetime
    last_verified_at: datetime | None = None
    schema_version: str = "model_credential_metadata_v1"

    @model_validator(mode="after")
    def validate_endpoint_binding(self) -> "ModelCredentialMetadata":
        binding = (
            self.endpoint_profile_id,
            self.endpoint_profile_version,
            self.normalized_origin,
            self.auth_scheme,
        )
        if self.provider_type == "OPENAI_COMPATIBLE" and not all(binding):
            raise ValueError("compatible credential requires exact endpoint binding")
        if self.provider_type == "OPENAI_OFFICIAL" and any(binding):
            raise ValueError("official credential cannot bind a compatible endpoint")
        return self


class CredentialCapabilitySummary(_StrictFrozenModel):
    provider: str
    authentication_status: str
    provider_access_status: str
    normal_model_status: str
    top_model_status: str
    structured_output_status: str
    price_status: str
    budget_status: str
    checked_at: datetime


class ModelCredentialMutationResult(_StrictFrozenModel):
    credential_id: str
    provider: str
    provider_type: ProviderType = "OPENAI_OFFICIAL"
    endpoint_profile_id: str | None = None
    endpoint_profile_version: str | None = None
    configured: bool
    stored: bool
    replaced: bool
    status: str
    secret_store_status: str
    capability: CredentialCapabilitySummary
    last_error_code: str | None = None
    sanitized_message: str | None = None


class ModelRunRecord(_StrictFrozenModel):
    model_run_id: str = Field(min_length=1)
    analysis_id: str = Field(min_length=1)
    snapshot_id: str | None = None
    context_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    run_mode: ModelRunMode
    automated_execution_allowed: bool
    role: str = Field(min_length=1)
    agent_name: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model_profile_id: str = Field(min_length=1)
    model_profile_version: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    model_version: str | None = None
    prompt_id: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    prompt_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    request_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    response_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    structured_output_status: str = Field(min_length=1)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    estimated_cost: float | None = Field(default=None, ge=0)
    cost_currency: str
    latency_ms: float = Field(ge=0)
    attempt: int = Field(ge=1)
    error_category: str | None = None
    error_code: str | None = None
    sanitized_message: str | None = None
    created_at: datetime
    record_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    schema_version: str = "model_run_v1"

    @model_validator(mode="after")
    def validate_execution_boundary(self) -> "ModelRunRecord":
        if self.run_mode in {
            "MODEL_CAPABILITY_CHECK",
            "REAL_MODEL_VALIDATION",
            "RESEARCH_REPLAY",
            "DEMO",
        } and self.automated_execution_allowed:
            raise ValueError(f"{self.run_mode} cannot allow automated execution")
        return self


class ResearchAgentResult(_StrictFrozenModel):
    research_result_id: str = Field(min_length=1)
    analysis_id: str = Field(min_length=1)
    snapshot_id: str = Field(min_length=1)
    context_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    agent_name: str = Field(min_length=1)
    agent_role: str = Field(min_length=1)
    status: Literal[
        "SUCCESS",
        "INSUFFICIENT_DATA",
        "MODEL_NOT_CONFIGURED",
        "MODEL_FAILED",
        "INVALID_OUTPUT",
        "DISABLED_NOT_REQUIRED",
        "BUDGET_BLOCKED",
    ]
    structured_summary: dict[str, Any]
    evidence_refs: list[str]
    model_run_id: str | None = None
    result_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime
    schema_version: str = "research_agent_result_v1"


class RealModelValidationRun(_StrictFrozenModel):
    validation_run_id: str = Field(min_length=1)
    run_mode: Literal["REAL_MODEL_VALIDATION"] = "REAL_MODEL_VALIDATION"
    research_only: Literal[True] = True
    automated_execution_allowed: Literal[False] = False
    requested_by: str
    snapshot_id: str | None = None
    quant_proposal_id: str | None = None
    status: Literal[
        "CREATED",
        "NO_ELIGIBLE_SAMPLE",
        "MODEL_NOT_CONFIGURED",
        "RUNNING",
        "COMPLETED",
        "FAILED",
        "INTEGRITY_CONFLICT",
    ]
    research_result_ids: list[str]
    normal_model_run_id: str | None = None
    top_model_run_id: str | None = None
    consensus_status: str | None = None
    hard_risk_status: str | None = None
    execution_gate_status: Literal["BLOCKED_VALIDATION_MODE"]
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    result_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime
    completed_at: datetime | None = None
    schema_version: str = "real_model_validation_v1"
