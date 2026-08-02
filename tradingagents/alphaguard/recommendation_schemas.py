"""Immutable governed candidate-recommendation contracts for PR-012."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


RECOMMENDATION_SCHEMA_VERSION = "candidate-recommendation-v1"
RECOMMENDATION_DATA_CONTRACT_VERSION = "recommendation-data-contract-v1"
RECOMMENDATION_ELIGIBILITY_SCHEMA_VERSION = "candidate-eligibility-v2"


def _json_default(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, Enum):
        return value.value
    raise TypeError(f"unsupported recommendation hash value: {type(value).__name__}")


def recommendation_hash(value: BaseModel | dict[str, Any], *, exclude: set[str] | None = None) -> str:
    payload = value.model_dump(mode="python") if isinstance(value, BaseModel) else dict(value)
    for key in exclude or set():
        payload.pop(key, None)
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class RecommendationSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        allow_inf_nan=False,
    )


class CandidateRecommendationPolicy(RecommendationSchema):
    policy_id: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    universe_policy_version: str = Field(min_length=1)
    eligibility_policy_version: str = Field(min_length=1)
    supported_markets: list[Literal["CN"]]
    supported_security_types: list[Literal["A_SHARE", "EXCHANGE_TRADED_FUND"]]
    allow_st: bool
    minimum_listing_sessions: int = Field(ge=0)
    minimum_data_history: int = Field(ge=20)
    minimum_average_amount: Decimal = Field(ge=0)
    maximum_zero_volume_sessions: int = Field(ge=0)
    liquidity_lookback_sessions: int = Field(ge=1)
    stale_quote_sessions: int = Field(ge=0)
    factor_weights: dict[str, Decimal]
    risk_penalties: dict[str, Decimal]
    minimum_recommendation_score: Decimal = Field(ge=0, le=100)
    daily_result_limit: int = Field(ge=1, le=100)
    candidate_pool_soft_limit: int = Field(ge=1)
    cooldown_days_rejected: int = Field(ge=0)
    cooldown_days_ignored: int = Field(ge=0)
    recommendation_ttl_days: int = Field(ge=1)
    score_change_breaks_cooldown: Decimal = Field(ge=0, le=100)
    enabled: bool
    config_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime
    schema_version: str = RECOMMENDATION_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_weights(self) -> "CandidateRecommendationPolicy":
        if sum(self.factor_weights.values(), Decimal("0")) != Decimal("1"):
            raise ValueError("candidate recommendation factor weights must total 1")
        if any(value < 0 or value > 1 for value in self.risk_penalties.values()):
            raise ValueError("candidate recommendation risk penalties must be within 0..1")
        return self


class CandidateUniverseManifest(RecommendationSchema):
    manifest_id: str = Field(min_length=1)
    market: Literal["CN"] = "CN"
    universe_date: date
    universe_version: str = Field(min_length=1)
    security_types: list[Literal["A_SHARE", "EXCHANGE_TRADED_FUND"]]
    security_count: int = Field(ge=0)
    ordered_symbols: list[str]
    ordered_security_types: list[str]
    ordered_source_refs: list[str]
    ordered_security_hashes: list[str]
    source_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    universe_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime
    schema_version: str = RECOMMENDATION_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_manifest(self) -> "CandidateUniverseManifest":
        lengths = {
            len(self.ordered_symbols),
            len(self.ordered_security_types),
            len(self.ordered_source_refs),
            len(self.ordered_security_hashes),
        }
        if lengths != {self.security_count}:
            raise ValueError("candidate universe manifest arrays must match security_count")
        if self.ordered_symbols != sorted(set(self.ordered_symbols)):
            raise ValueError("candidate universe symbols must be unique and ordered")
        return self


class CandidateEligibilityResult(RecommendationSchema):
    eligibility_result_id: str = Field(min_length=1)
    recommendation_run_id: str = Field(min_length=1)
    symbol: str = Field(pattern=r"^\d{6}$")
    market: Literal["CN"] = "CN"
    trade_date: date
    security_type: Literal["A_SHARE", "EXCHANGE_TRADED_FUND"]
    eligible: bool
    filter_reason_codes: list[str]
    primary_filter_reason: str | None = None
    required_history_days: int = Field(default=0, ge=0)
    available_history_days: int | None = Field(default=None, ge=0)
    data_version: str = "legacy"
    data_quality_status: Literal["PASS", "WARN", "FAIL", "NOT_AVAILABLE"]
    history_count: int = Field(ge=0)
    average_amount: Decimal | None = Field(default=None, ge=0)
    policy_version: str = Field(min_length=1)
    evidence_refs: list[str]
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime
    schema_version: str = RECOMMENDATION_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_result(self) -> "CandidateEligibilityResult":
        if self.eligible and self.filter_reason_codes:
            raise ValueError("eligible security cannot retain filter reasons")
        if not self.eligible and not self.filter_reason_codes:
            raise ValueError("ineligible security requires filter reasons")
        if self.eligible and self.primary_filter_reason is not None:
            raise ValueError("eligible security cannot retain a primary filter reason")
        if not self.eligible and self.primary_filter_reason not in self.filter_reason_codes:
            raise ValueError("primary filter reason must be one of all filter reasons")
        if (
            self.available_history_days is not None
            and self.available_history_days != self.history_count
        ):
            raise ValueError("available history must match history_count")
        return self


class RecommendationDataQualityReport(RecommendationSchema):
    quality_report_id: str = Field(min_length=1)
    symbol: str = Field(pattern=r"^\d{6}$")
    market: Literal["CN"] = "CN"
    trade_date: date
    status: Literal["PASS", "FAIL"]
    required_history_days: int = Field(ge=20)
    available_history_days: int = Field(ge=0)
    price_adjustment_mode: Literal["QFQ"] = "QFQ"
    price_data_versions: list[str]
    target_quote_ref: str | None = None
    target_quote_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    trading_status_id: str | None = None
    trading_status_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    benchmark_count: int = Field(ge=0)
    benchmark_manifest_ref: str | None = None
    missing_fields: list[str]
    blocking_reasons: list[str]
    data_version: str = Field(min_length=1)
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    immutable_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    checked_at: datetime
    schema_version: str = RECOMMENDATION_DATA_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_quality(self) -> "RecommendationDataQualityReport":
        if self.status == "PASS" and (self.missing_fields or self.blocking_reasons):
            raise ValueError("PASS recommendation data quality cannot list blockers")
        if self.status == "FAIL" and not self.blocking_reasons:
            raise ValueError("FAIL recommendation data quality requires blockers")
        if self.status == "PASS" and self.available_history_days < self.required_history_days:
            raise ValueError("PASS recommendation data quality lacks required history")
        return self


class RecommendationDataCoverage(RecommendationSchema):
    coverage_id: str = Field(min_length=1)
    market: Literal["CN"] = "CN"
    trade_date: date
    universe_manifest_id: str = Field(min_length=1)
    universe_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    universe_count: int = Field(ge=0)
    basic_info_ready_count: int = Field(ge=0)
    target_quote_ready_count: int = Field(ge=0)
    trade_status_ready_count: int = Field(ge=0)
    raw_history_ready_count: int = Field(ge=0)
    adjusted_history_ready_count: int = Field(ge=0)
    benchmark_ready_count: int = Field(ge=0)
    industry_ready_count: int = Field(ge=0)
    data_quality_pass_count: int = Field(ge=0)
    minimum_contract_ready_count: int = Field(ge=0)
    eligible_count: int = Field(ge=0)
    failed_symbol_count: int = Field(ge=0)
    required_history_days: int = Field(ge=20)
    coverage_threshold: Decimal = Field(ge=0, le=1)
    coverage_percentage: Decimal = Field(ge=0, le=1)
    blocking_reason_counts: dict[str, int]
    status: Literal["NOT_READY", "PARTIAL", "READY", "DEGRADED"]
    recommendation_data_ready: bool
    industry_required: bool
    data_version: str = Field(min_length=1)
    source_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    coverage_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    sync_run_id: str | None = None
    sync_started_at: datetime | None = None
    sync_completed_at: datetime | None = None
    sync_duration_ms: int = Field(default=0, ge=0)
    sync_created_count: int = Field(default=0, ge=0)
    sync_reused_count: int = Field(default=0, ge=0)
    sync_retry_count: int = Field(default=0, ge=0)
    sync_resumed_count: int = Field(default=0, ge=0)
    created_at: datetime
    schema_version: str = RECOMMENDATION_DATA_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_coverage(self) -> "RecommendationDataCoverage":
        counts = (
            self.basic_info_ready_count,
            self.target_quote_ready_count,
            self.trade_status_ready_count,
            self.raw_history_ready_count,
            self.adjusted_history_ready_count,
            self.industry_ready_count,
            self.data_quality_pass_count,
            self.minimum_contract_ready_count,
            self.eligible_count,
        )
        if any(value > self.universe_count for value in counts):
            raise ValueError("recommendation coverage count exceeds universe")
        if self.recommendation_data_ready != (
            self.coverage_percentage >= self.coverage_threshold
            and self.benchmark_ready_count >= self.required_history_days
        ):
            raise ValueError("recommendation data readiness does not match coverage gate")
        if self.status == "READY" and self.failed_symbol_count:
            raise ValueError("READY recommendation coverage cannot retain failures")
        return self


class RecommendationFactorEvidence(RecommendationSchema):
    evidence_id: str = Field(min_length=1)
    symbol: str = Field(pattern=r"^\d{6}$")
    market: Literal["CN"] = "CN"
    trade_date: date
    factor_set_version: str = Field(min_length=1)
    factor_definition_versions: dict[str, str]
    factor_code_hashes: dict[str, str]
    normalized_scores: dict[str, Decimal | None]
    group_scores: dict[str, Decimal | None]
    quote_refs: list[str]
    quote_hashes: list[str]
    benchmark_refs: list[str]
    benchmark_hashes: list[str]
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime
    schema_version: str = "recommendation-factor-evidence-v1"


class CandidateRecommendationScoreResult(RecommendationSchema):
    score_result_id: str = Field(min_length=1)
    recommendation_run_id: str = Field(min_length=1)
    symbol: str = Field(pattern=r"^\d{6}$")
    trade_date: date
    recommendation_score: Decimal = Field(ge=0, le=100)
    score_components: dict[str, Decimal]
    risk_penalties: dict[str, Decimal]
    meets_threshold: bool
    minimum_recommendation_score: Decimal = Field(ge=0, le=100)
    evidence_refs: list[str]
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime
    schema_version: str = "candidate-recommendation-score-v1"

    @model_validator(mode="after")
    def validate_score(self) -> "CandidateRecommendationScoreResult":
        expected = self.recommendation_score >= self.minimum_recommendation_score
        if self.meets_threshold != expected:
            raise ValueError("score threshold status is inconsistent")
        return self


class CandidateRecommendationRun(RecommendationSchema):
    recommendation_run_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    trade_date: date
    universe_manifest_id: str = Field(min_length=1)
    universe_version: str = Field(min_length=1)
    policy_id: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    data_version: str = Field(min_length=1)
    total_securities: int = Field(ge=0)
    eligible_securities: int = Field(ge=0)
    scored_securities: int = Field(ge=0)
    recommended_securities: int = Field(ge=0)
    filtered_reason_counts: dict[str, int]
    failed_symbols: list[str]
    status: Literal["SUCCESS", "PARTIAL", "FAILED"]
    model_call_count_before: int = Field(ge=0)
    model_call_count_after: int = Field(ge=0)
    started_at: datetime
    completed_at: datetime
    duration_ms: int = Field(ge=0)
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    schema_version: str = RECOMMENDATION_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_counts(self) -> "CandidateRecommendationRun":
        if not (
            self.recommended_securities
            <= self.scored_securities
            <= self.eligible_securities
            <= self.total_securities
        ):
            raise ValueError("candidate recommendation run counts are inconsistent")
        if self.model_call_count_before != self.model_call_count_after:
            raise ValueError("candidate recommendation run must not call models")
        return self


class CandidateRecommendation(RecommendationSchema):
    recommendation_id: str = Field(min_length=1)
    recommendation_run_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    trade_date: date
    market: Literal["CN"] = "CN"
    symbol: str = Field(pattern=r"^\d{6}$")
    security_name: str = Field(min_length=1)
    security_type: Literal["A_SHARE", "EXCHANGE_TRADED_FUND"]
    policy_id: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    recommendation_score: Decimal = Field(ge=0, le=100)
    score_components: dict[str, Decimal]
    risk_penalties: dict[str, Decimal]
    recommendation_reason_codes: list[str]
    recommendation_reasons: list[str]
    risk_reason_codes: list[str]
    risk_reasons: list[str]
    data_quality_status: str = Field(min_length=1)
    regime_type: str | None = None
    strategy_signal_status: str | None = None
    evidence_refs: list[str]
    factor_result_refs: list[str]
    supersedes_recommendation_id: str | None = None
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    expires_at: datetime
    created_at: datetime
    schema_version: str = RECOMMENDATION_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_score(self) -> "CandidateRecommendation":
        positive = sum(self.score_components.values(), Decimal("0"))
        penalty = sum(self.risk_penalties.values(), Decimal("0"))
        expected = max(Decimal("0"), min(Decimal("100"), positive - penalty))
        if self.recommendation_score != expected.quantize(Decimal("0.01")):
            raise ValueError("recommendation score must equal components minus penalties")
        if not self.recommendation_reasons:
            raise ValueError("candidate recommendation requires explainable reasons")
        return self


class CandidateRecommendationReviewEvent(RecommendationSchema):
    review_event_id: str = Field(min_length=1)
    recommendation_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    action: Literal["ACCEPTED", "REJECTED", "IGNORED", "SUPERSEDED", "EXPIRED"]
    operator_user_id: str = Field(min_length=1)
    candidate_id: str | None = None
    review_note: str | None = Field(default=None, max_length=1000)
    trace_id: str | None = None
    created_at: datetime
    event_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    schema_version: str = RECOMMENDATION_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_accept(self) -> "CandidateRecommendationReviewEvent":
        if self.action == "ACCEPTED" and not self.candidate_id:
            raise ValueError("accepted recommendation requires candidate_id")
        return self


class CandidateRecommendationEvaluation(RecommendationSchema):
    evaluation_id: str = Field(min_length=1)
    recommendation_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    symbol: str = Field(pattern=r"^\d{6}$")
    trade_date: date
    policy_version: str = Field(min_length=1)
    status: Literal["PENDING", "PARTIAL", "CALCULATED", "INSUFFICIENT_DATA"]
    horizon_results: dict[str, dict[str, Any]]
    accepted_into_candidate_pool: bool
    later_strategy_triggered: bool
    later_valid_trade_plan: bool
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime
    updated_at: datetime
    schema_version: str = RECOMMENDATION_SCHEMA_VERSION
