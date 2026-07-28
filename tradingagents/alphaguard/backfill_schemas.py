"""Strict research-only contracts for historical AlphaGuard backfill.

These objects are incapable of authorising production execution.  They live
in ``ag_research_*`` collections and may reference PR-007 analytical objects,
but never PR-006 account or order state.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from tradingagents.alphaguard.evidence_schemas import EvidenceSnapshot


BACKFILL_SCHEMA_VERSION = "alphaguard-historical-backfill-v1"
BACKFILL_RUN_MODE = "RESEARCH_BACKFILL"


def _json_default(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    raise TypeError(f"unsupported canonical value: {type(value).__name__}")


def backfill_hash(value: Any, *, exclude: set[str] | None = None) -> str:
    if isinstance(value, BaseModel):
        payload = value.model_dump(mode="python", exclude=exclude or set())
    elif isinstance(value, dict):
        payload = {
            key: item
            for key, item in value.items()
            if key not in (exclude or set())
        }
    else:
        payload = value
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class BackfillSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )


class HistoricalBackfillRun(BackfillSchema):
    backfill_run_id: str = Field(min_length=1)
    status: Literal[
        "CREATED",
        "RUNNING",
        "COMPLETED",
        "PARTIAL",
        "FAILED",
        "CANCELLED",
    ]
    user_id: str = Field(min_length=1)
    market: Literal["CN"] = "CN"
    symbols: list[str] = Field(min_length=1)
    start_trade_date: date
    end_trade_date: date
    sampling_method: Literal["WEEKLY_LAST_SESSION", "DAILY", "CUSTOM"]
    selected_trade_dates: list[date] = Field(min_length=1)
    run_mode: Literal["RESEARCH_BACKFILL"] = BACKFILL_RUN_MODE
    research_only: Literal[True] = True
    automated_execution_allowed: Literal[False] = False
    code_commit: str = Field(min_length=1)
    code_tree_hash: str = Field(min_length=1)
    config_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    version_refs: dict[str, str]
    total_samples: int = Field(ge=0)
    completed_samples: int = Field(default=0, ge=0)
    skipped_samples: int = Field(default=0, ge=0)
    failed_samples: int = Field(default=0, ge=0)
    attempt_count: int = Field(default=0, ge=0)
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_summary: list[str] = Field(default_factory=list)
    schema_version: str = BACKFILL_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_run(self) -> "HistoricalBackfillRun":
        if self.end_trade_date < self.start_trade_date:
            raise ValueError("backfill end_trade_date precedes start_trade_date")
        if self.selected_trade_dates != sorted(set(self.selected_trade_dates)):
            raise ValueError("selected_trade_dates must be sorted and unique")
        if any(
            item < self.start_trade_date or item > self.end_trade_date
            for item in self.selected_trade_dates
        ):
            raise ValueError("selected trade date lies outside the run range")
        expected = len(self.symbols) * len(self.selected_trade_dates)
        if self.total_samples != expected:
            raise ValueError("total_samples does not match symbols x dates")
        return self


class HistoricalCoverageRecord(BackfillSchema):
    coverage_id: str = Field(min_length=1)
    backfill_run_id: str = Field(min_length=1)
    sample_id: str = Field(min_length=1)
    symbol: str = Field(pattern=r"^\d{6}$")
    market: Literal["CN"] = "CN"
    trade_date: date
    status: Literal["READY", "INSUFFICIENT_DATA", "INVALID_SOURCE"]
    replay_allowed: bool
    domains: dict[str, dict[str, Any]]
    critical_missing: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime
    run_mode: Literal["RESEARCH_BACKFILL"] = BACKFILL_RUN_MODE
    research_only: Literal[True] = True
    automated_execution_allowed: Literal[False] = False
    schema_version: str = BACKFILL_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_coverage(self) -> "HistoricalCoverageRecord":
        if self.replay_allowed != (self.status == "READY"):
            raise ValueError("coverage replay_allowed must match READY status")
        if self.status != "READY" and not self.critical_missing:
            raise ValueError("blocked coverage requires critical_missing reasons")
        return self


class HistoricalMarketContextSource(BackfillSchema):
    source_id: str = Field(min_length=1)
    market: Literal["CN"] = "CN"
    trade_date: date
    provider: str = Field(min_length=1)
    provider_version: str = Field(min_length=1)
    normalization_version: str = Field(min_length=1)
    source_record_count: int = Field(ge=0)
    expected_universe_count: int = Field(ge=0)
    normalized_records: list[dict[str, Any]]
    market_amount_window: list[dict[str, Any]]
    sector_records: list[dict[str, Any]]
    source_response_hashes: dict[str, str]
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    collected_at: datetime
    schema_version: str = BACKFILL_SCHEMA_VERSION


class HistoricalMarketContext(BackfillSchema):
    context_id: str = Field(min_length=1)
    market: Literal["CN"] = "CN"
    trade_date: date
    available_at: datetime
    provider: str = Field(min_length=1)
    provider_version: str = Field(min_length=1)
    data_version: str = Field(min_length=1)
    source_record_id: str = Field(min_length=1)
    source_refs: list[str] = Field(min_length=1)
    advance_count: int | None = Field(default=None, ge=0)
    decline_count: int | None = Field(default=None, ge=0)
    unchanged_count: int | None = Field(default=None, ge=0)
    total_amount: Decimal | None = Field(default=None, ge=0)
    amount_ratio20: Decimal | None = Field(default=None, ge=0)
    new_high_count: int | None = Field(default=None, ge=0)
    new_low_count: int | None = Field(default=None, ge=0)
    industry_diffusion: Decimal | None = Field(default=None, ge=0, le=1)
    extreme_risk_flag: bool | None = None
    universe_coverage: Decimal = Field(ge=0, le=1)
    high_low_coverage: Decimal = Field(ge=0, le=1)
    sector_coverage: Decimal = Field(ge=0, le=1)
    calculation_status: Literal["READY", "INSUFFICIENT_DATA", "INVALID_SOURCE"]
    missing_fields: list[str] = Field(default_factory=list)
    methodology: dict[str, str]
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime
    schema_version: str = BACKFILL_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_context(self) -> "HistoricalMarketContext":
        required = (
            self.advance_count,
            self.decline_count,
            self.industry_diffusion,
        )
        if self.calculation_status == "READY" and any(
            value is None for value in required
        ):
            raise ValueError("READY MarketContext lacks required regime inputs")
        if self.calculation_status != "READY" and not self.missing_fields:
            raise ValueError("non-ready MarketContext requires missing_fields")
        return self


class HistoricalResearchSnapshot(BackfillSchema):
    research_snapshot_id: str = Field(min_length=1)
    backfill_run_id: str = Field(min_length=1)
    sample_id: str = Field(min_length=1)
    source_trade_date: date
    evidence_snapshot: EvidenceSnapshot
    calendar_reference_mode: Literal["PERSISTED_RESEARCH_CONTROL"] = (
        "PERSISTED_RESEARCH_CONTROL"
    )
    version_selection_mode: Literal["LOCKED_AT_BACKFILL_RUN"] = (
        "LOCKED_AT_BACKFILL_RUN"
    )
    run_mode: Literal["RESEARCH_BACKFILL"] = BACKFILL_RUN_MODE
    research_only: Literal[True] = True
    automated_execution_allowed: Literal[False] = False
    immutable_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime
    schema_version: str = BACKFILL_SCHEMA_VERSION


class ResearchShadowExecution(BackfillSchema):
    shadow_execution_id: str = Field(min_length=1)
    backfill_run_id: str = Field(min_length=1)
    sample_id: str = Field(min_length=1)
    proposal_id: str = Field(min_length=1)
    status: Literal[
        "NOT_ELIGIBLE",
        "INSUFFICIENT_DATA",
        "NO_FILL",
        "PARTIALLY_FILLED",
        "FILLED",
        "BLOCKED",
    ]
    action: Literal["BUY", "SELL", "REDUCE", "HOLD", "WAIT"]
    order_payload: dict[str, Any] | None = None
    match_payload: dict[str, Any] | None = None
    fee_payload: dict[str, Any] | None = None
    normalized_notional: Decimal | None = Field(default=None, gt=0)
    gross_return: Decimal | None = None
    net_return: Decimal | None = None
    reason: str = Field(min_length=1)
    matching_version: str = Field(min_length=1)
    fee_version: str = Field(min_length=1)
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    run_mode: Literal["RESEARCH_BACKFILL"] = BACKFILL_RUN_MODE
    research_only: Literal[True] = True
    automated_execution_allowed: Literal[False] = False
    created_at: datetime
    schema_version: str = BACKFILL_SCHEMA_VERSION


class HistoricalBackfillSample(BackfillSchema):
    sample_id: str = Field(min_length=1)
    backfill_run_id: str = Field(min_length=1)
    symbol: str = Field(pattern=r"^\d{6}$")
    market: Literal["CN"] = "CN"
    trade_date: date
    status: Literal[
        "CREATED",
        "RUNNING",
        "COMPLETED",
        "BACKFILL_SKIPPED_INSUFFICIENT_DATA",
        "FAILED",
        "INTEGRITY_CONFLICT",
    ]
    reason: str = Field(min_length=1)
    coverage_id: str | None = None
    research_snapshot_id: str | None = None
    factor_result_ids: list[str] = Field(default_factory=list)
    factor_bundle_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    regime_result_id: str | None = None
    proposal_ids: list[str] = Field(default_factory=list)
    evaluation_subject_ids: list[str] = Field(default_factory=list)
    horizon_label_ids: list[str] = Field(default_factory=list)
    counterfactual_ids: list[str] = Field(default_factory=list)
    attribution_ids: list[str] = Field(default_factory=list)
    shadow_execution_ids: list[str] = Field(default_factory=list)
    model_replay_status: Literal[
        "NOT_REQUESTED",
        "NOT_CONFIGURED",
        "COMPLETED",
        "MODEL_FAILED",
    ] = "NOT_REQUESTED"
    version_refs: dict[str, str]
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    result_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    attempt_count: int = Field(default=0, ge=0)
    error_history: list[dict[str, Any]] = Field(default_factory=list)
    run_mode: Literal["RESEARCH_BACKFILL"] = BACKFILL_RUN_MODE
    research_only: Literal[True] = True
    automated_execution_allowed: Literal[False] = False
    created_at: datetime
    updated_at: datetime
    schema_version: str = BACKFILL_SCHEMA_VERSION


class HistoricalBackfillReport(BackfillSchema):
    report_id: str = Field(min_length=1)
    backfill_run_id: str = Field(min_length=1)
    status: Literal["READY", "PARTIAL", "INSUFFICIENT_DATA", "FAILED"]
    planned_sample_count: int = Field(ge=0)
    completed_sample_count: int = Field(ge=0)
    skipped_sample_count: int = Field(ge=0)
    failed_sample_count: int = Field(ge=0)
    data_summary: dict[str, Any]
    factor_summary: dict[str, Any]
    regime_summary: dict[str, Any]
    strategy_summary: dict[str, Any]
    model_summary: dict[str, Any]
    risk_execution_summary: dict[str, Any]
    evaluation_summary: dict[str, Any]
    caveats: list[str]
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    report_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    run_mode: Literal["RESEARCH_BACKFILL"] = BACKFILL_RUN_MODE
    research_only: Literal[True] = True
    automated_execution_allowed: Literal[False] = False
    created_at: datetime
    schema_version: str = BACKFILL_SCHEMA_VERSION
