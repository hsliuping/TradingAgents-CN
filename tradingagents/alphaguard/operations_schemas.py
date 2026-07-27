"""Strict, non-secret operational contracts for AlphaGuard PR-009."""

from __future__ import annotations

from datetime import date, datetime
from hashlib import sha256
import json
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


OPERATIONS_SCHEMA_VERSION = "alphaguard-operations-v1"

_SECRET_KEY = re.compile(
    r"(authorization|api[_-]?key|password|secret|token|credential|cookie)",
    re.IGNORECASE,
)
_SECRET_VALUE = re.compile(
    r"(?i)(bearer\s+[\w.+/=-]+|"
    r"(?:api[_-]?key|password|secret|token)\s*[:=]\s*[^\s,;]+)"
)


def sanitize_operational_value(value: Any) -> Any:
    """Recursively redact credential-shaped keys and values."""

    if isinstance(value, BaseModel):
        return sanitize_operational_value(value.model_dump(mode="python"))
    if isinstance(value, dict):
        return {
            str(key): (
                "[REDACTED]"
                if _SECRET_KEY.search(str(key))
                else sanitize_operational_value(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        return [sanitize_operational_value(item) for item in value]
    if isinstance(value, str):
        return _SECRET_VALUE.sub("[REDACTED]", value)[:1000]
    return value


def operations_hash(value: Any, *, exclude: set[str] | None = None) -> str:
    """Return a deterministic SHA-256 over canonical JSON."""

    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    if isinstance(value, dict) and exclude:
        value = {key: item for key, item in value.items() if key not in exclude}
    normalized = sanitize_operational_value(value)
    encoded = json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


class _FrozenOperationalModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ServiceHealth(_FrozenOperationalModel):
    service_name: str = Field(min_length=1)
    status: Literal[
        "HEALTHY",
        "DEGRADED",
        "UNHEALTHY",
        "NOT_CONFIGURED",
        "UNKNOWN",
    ]
    required: bool
    reachable: bool | None = None
    latency_ms: float | None = Field(default=None, ge=0)
    last_checked_at: datetime
    last_success_at: datetime | None = None
    error_code: str | None = None
    sanitized_message: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    schema_version: str = OPERATIONS_SCHEMA_VERSION

    @field_validator("sanitized_message")
    @classmethod
    def sanitize_message(cls, value: str | None) -> str | None:
        return sanitize_operational_value(value) if value is not None else None

    @field_validator("details")
    @classmethod
    def sanitize_details(cls, value: dict[str, Any]) -> dict[str, Any]:
        return sanitize_operational_value(value)


class DataReadinessStatus(_FrozenOperationalModel):
    component: Literal[
        "TRADING_CALENDAR",
        "QFQ_PRICE_DATA",
        "RAW_PRICE_DATA",
        "FINANCIAL_DATA",
        "NEWS_DATA",
        "ANNOUNCEMENT_DATA",
        "MARKET_CONTEXT",
        "INDUSTRY_HISTORY",
        "MODEL_PROVIDER",
        "CHAMPION_ASSIGNMENTS",
        "EVALUATION_SAMPLES",
        "EXPERIMENT_SAMPLES",
        "CHALLENGER_PIPELINE",
    ]
    status: Literal[
        "READY",
        "PARTIAL",
        "NOT_READY",
        "NOT_CONFIGURED",
        "STALE",
        "ERROR",
    ]
    market: str | None = None
    coverage_start: date | None = None
    coverage_end: date | None = None
    record_count: int | None = Field(default=None, ge=0)
    required_for: list[str] = Field(default_factory=list)
    blocking_reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    last_checked_at: datetime
    schema_version: str = OPERATIONS_SCHEMA_VERSION


class JobHealth(_FrozenOperationalModel):
    job_name: str = Field(min_length=1)
    worker_name: str = Field(min_length=1)
    status: Literal[
        "IDLE",
        "RUNNING",
        "SUCCESS",
        "FAILED",
        "RETRYING",
        "STALE",
        "DISABLED",
        "BLOCKED",
    ]
    last_run_id: str | None = None
    last_started_at: datetime | None = None
    last_finished_at: datetime | None = None
    last_success_at: datetime | None = None
    next_scheduled_at: datetime | None = None
    expected_interval_seconds: int | None = Field(default=None, ge=1)
    lag_seconds: int | None = Field(default=None, ge=0)
    retry_count: int = Field(default=0, ge=0)
    backlog_count: int | None = Field(default=None, ge=0)
    error_code: str | None = None
    sanitized_message: str | None = None
    schema_version: str = OPERATIONS_SCHEMA_VERSION

    @field_validator("sanitized_message")
    @classmethod
    def sanitize_message(cls, value: str | None) -> str | None:
        return sanitize_operational_value(value) if value is not None else None


class OperationalAlert(_FrozenOperationalModel):
    alert_id: str = Field(min_length=1)
    severity: Literal["INFO", "WARNING", "ERROR", "CRITICAL"]
    category: Literal[
        "SECURITY",
        "DATA",
        "MODEL",
        "DECISION",
        "RISK",
        "EXECUTION",
        "ACCOUNT",
        "EVALUATION",
        "EXPERIMENT",
        "INFRASTRUCTURE",
        "INTEGRITY",
    ]
    code: str = Field(min_length=1)
    title: str = Field(min_length=1)
    sanitized_message: str = Field(min_length=1)
    source_module: str = Field(min_length=1)
    source_object_id: str | None = None
    trace_id: str | None = None
    first_seen_at: datetime
    last_seen_at: datetime
    occurrence_count: int = Field(ge=1)
    status: Literal["OPEN", "ACKNOWLEDGED", "RESOLVED"]
    acknowledged_by: str | None = None
    acknowledged_at: datetime | None = None
    resolution_note: str | None = None
    resolved_at: datetime | None = None
    schema_version: str = OPERATIONS_SCHEMA_VERSION

    @field_validator("sanitized_message", "resolution_note")
    @classmethod
    def sanitize_text(cls, value: str | None) -> str | None:
        return sanitize_operational_value(value) if value is not None else None

    @model_validator(mode="after")
    def validate_transition_fields(self) -> "OperationalAlert":
        if self.status == "ACKNOWLEDGED" and not (
            self.acknowledged_by and self.acknowledged_at
        ):
            raise ValueError("ACKNOWLEDGED alert requires actor and timestamp")
        if self.status == "RESOLVED" and not self.resolved_at:
            raise ValueError("RESOLVED alert requires resolved_at")
        return self


class SystemReadinessReport(_FrozenOperationalModel):
    report_id: str = Field(min_length=1)
    generated_at: datetime
    overall_status: Literal[
        "READY_FOR_PAPER",
        "DEGRADED_PAPER",
        "NOT_READY",
        "UNSAFE",
    ]
    system_mode: str
    live_trading_enabled: bool
    live_execution_allowed: Literal[False] = False
    service_health: list[ServiceHealth]
    data_readiness: list[DataReadinessStatus]
    job_health: list[JobHealth]
    blocking_items: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    paper_execution_ready: bool
    evaluation_ready: bool
    experiment_ready: bool
    challenger_ready: bool
    live_ready: Literal[False] = False
    code_commit: str
    build_version: str
    config_hash: str = Field(min_length=64, max_length=64)
    report_hash: str = Field(min_length=64, max_length=64)
    schema_version: str = OPERATIONS_SCHEMA_VERSION

    @model_validator(mode="after")
    def enforce_safety_truth(self) -> "SystemReadinessReport":
        if self.live_trading_enabled and self.overall_status != "UNSAFE":
            raise ValueError("live trading requires UNSAFE readiness status")
        if self.overall_status == "READY_FOR_PAPER" and self.blocking_items:
            raise ValueError("READY_FOR_PAPER cannot contain blocking items")
        return self


class OperationsJobRequest(_FrozenOperationalModel):
    job_request_id: str
    job_name: str
    requested_by: str
    idempotency_key: str
    status: Literal[
        "PENDING",
        "RUNNING",
        "COMPLETED",
        "FAILED",
        "BLOCKED",
    ]
    payload: dict[str, Any] = Field(default_factory=dict)
    attempt_count: int = Field(default=0, ge=0)
    result: dict[str, Any] | None = None
    error_code: str | None = None
    sanitized_message: str | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    schema_version: str = OPERATIONS_SCHEMA_VERSION

    @field_validator("payload", "result")
    @classmethod
    def sanitize_mapping(
        cls, value: dict[str, Any] | None
    ) -> dict[str, Any] | None:
        return sanitize_operational_value(value) if value is not None else None

