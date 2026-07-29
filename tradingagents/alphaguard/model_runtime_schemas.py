"""Versioned, secret-free contracts for the AlphaGuard model runtime."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


ModelRole = Literal["RESEARCH_AGENT", "NORMAL_TRADER", "TOP_RISK_REVIEWER"]
StructuredOutputMode = Literal["NATIVE_SCHEMA", "TOOL_CALL", "JSON_SCHEMA"]
CapabilityStatus = Literal[
    "UNVERIFIED",
    "READY",
    "NOT_CONFIGURED",
    "UNAUTHORIZED",
    "MODEL_NOT_FOUND",
    "STRUCTURED_OUTPUT_UNSUPPORTED",
    "TIMEOUT",
    "RATE_LIMITED",
    "PROVIDER_ERROR",
    "UNSUPPORTED",
    "DEGRADED",
    "DISABLED",
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
    input_cost_per_million: float | None = Field(default=None, ge=0)
    output_cost_per_million: float | None = Field(default=None, ge=0)
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
    checked_by: str
    checked_at: datetime
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    result_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    schema_version: str = "model_capability_check_v1"


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
