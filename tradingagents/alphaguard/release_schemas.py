"""Operational release contracts for the AlphaGuard MVP release candidate."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from tradingagents.alphaguard.operations_schemas import sanitize_operational_value


RELEASE_SCHEMA_VERSION = "alphaguard-mvp-release-v1"

DailyStageStatus = Literal[
    "PENDING",
    "RUNNING",
    "SUCCESS",
    "FAILED",
    "BLOCKED",
    "REUSED",
    "SKIPPED",
]
MvpItemStatus = Literal["可用", "降级可用", "未就绪", "已阻断", "不适用"]


class _FrozenReleaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DailyStageRun(_FrozenReleaseModel):
    job_id: str = Field(min_length=1)
    daily_run_id: str = Field(min_length=1)
    stage_id: str = Field(min_length=1)
    stage_name: str = Field(min_length=1)
    trading_date: date
    input_version: str = Field(min_length=1)
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: DailyStageStatus
    started_at: datetime | None = None
    completed_at: datetime | None = None
    retry_count: int = Field(default=0, ge=0)
    reuse_count: int = Field(default=0, ge=0)
    error_code: str | None = None
    sanitized_message: str | None = None
    output_count: int = Field(default=0, ge=0)
    idempotency_key: str = Field(min_length=1)
    dependency_stage_ids: list[str] = Field(default_factory=list)
    result: dict[str, Any] = Field(default_factory=dict)
    schema_version: str = RELEASE_SCHEMA_VERSION
    @field_validator("result")
    @classmethod
    def sanitize_result(cls, value: dict[str, Any]) -> dict[str, Any]:
        return sanitize_operational_value(value)

    @field_validator("sanitized_message")
    @classmethod
    def sanitize_message(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return str(sanitize_operational_value(value))[:1000]


class DailyRunSummary(_FrozenReleaseModel):
    daily_run_id: str = Field(min_length=1)
    trading_date: date
    input_version: str = Field(min_length=1)
    status: Literal["SUCCESS", "FAILED", "BLOCKED", "DRY_RUN", "NOT_FOUND"]
    stages: list[DailyStageRun] = Field(default_factory=list)
    created_count: int = Field(default=0, ge=0)
    reused_count: int = Field(default=0, ge=0)
    failed_stage_id: str | None = None
    blocking_reason: str | None = None
    live_execution_allowed: Literal[False] = False
    schema_version: str = RELEASE_SCHEMA_VERSION


class MvpAcceptanceItem(_FrozenReleaseModel):
    item_id: str = Field(min_length=1)
    item_name: str = Field(min_length=1)
    status: MvpItemStatus
    last_success_at: datetime | None = None
    last_failure_at: datetime | None = None
    latest_object_id: str | None = None
    blocking_reason: str | None = None
    verification_evidence: list[str] = Field(default_factory=list)
    version: str = Field(min_length=1)
    owner_module: str = Field(min_length=1)
    advanced: dict[str, Any] = Field(default_factory=dict)

    @field_validator("advanced")
    @classmethod
    def sanitize_advanced(cls, value: dict[str, Any]) -> dict[str, Any]:
        return sanitize_operational_value(value)


class MvpAcceptanceReport(_FrozenReleaseModel):
    report_id: str = Field(min_length=1)
    generated_at: datetime
    overall_status: Literal["MVP_PAPER_READY", "DEGRADED", "NOT_READY", "BLOCKED"]
    items: list[MvpAcceptanceItem]
    summary: dict[str, int]
    state_flags: dict[str, bool]
    latest_daily_run_id: str | None = None
    latest_backup_id: str | None = None
    consistency_status: Literal["PASS", "WARNING", "FAIL", "NOT_RUN"]
    report_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    schema_version: str = RELEASE_SCHEMA_VERSION
