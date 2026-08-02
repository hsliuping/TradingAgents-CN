"""Strict, evaluation-only schemas for AlphaGuard PR-007.

These records are analytical facts.  They never authorize execution and they
must never be written to PR-003--PR-006 production collections.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from tradingagents.alphaguard.decision_schemas import EvidenceRef, PriceRange


EVALUATION_VERSION = "evaluation-v1"
LABEL_CALCULATION_VERSION = "horizon-label-v1"
COUNTERFACTUAL_VERSION = "counterfactual-v1"
ACCOUNT_METRIC_VERSION = "account-metric-v1"
COMPARISON_VERSION = "paired-comparison-v1"
ATTRIBUTION_RULE_VERSION = "attribution-rules-v1"
EVALUATION_SCHEMA_VERSION = "alphaguard-evaluation-v1"


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


def evaluation_hash(value: Any, *, exclude: set[str] | None = None) -> str:
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


class EvaluationSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )


class EvaluationSubject(EvaluationSchema):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )

    subject_id: str = Field(min_length=1)
    subject_type: Literal[
        "QUANT_PROPOSAL",
        "NORMAL_PLAN",
        "TOP_REVIEW",
        "CONSENSUS",
        "RISK_DECISION",
        "BENCHMARK_DECISION",
        "EXECUTION_OUTBOX",
        "ORDER_INTENT",
        "PAPER_ORDER",
        "PAPER_FILL",
        "POSITION_EXIT",
    ]
    source_object_id: str = Field(min_length=1)
    source_object_version: str | None = None
    user_id: str = Field(min_length=1)
    candidate_id: str | None = None
    symbol: str = Field(min_length=1)
    market: str = Field(min_length=1)
    snapshot_id: str = Field(min_length=1)
    analysis_id: str | None = None
    decision_trade_date: date
    decision_cutoff_at: datetime
    action: Literal[
        "BUY",
        "SELL",
        "REDUCE",
        "HOLD",
        "WAIT",
        "REJECT",
        "SUSPEND",
    ]
    decision_stage: Literal[
        "QUANT",
        "NORMAL_MODEL",
        "TOP_MODEL",
        "CONSENSUS",
        "HARD_RISK",
        "BENCHMARK_SAFETY",
        "EXECUTION",
    ]
    decision_status: str = Field(min_length=1)
    selected_for_execution: bool
    actual_execution_exists: bool
    entry_zone: PriceRange | None = None
    initial_position_pct: Decimal | None = Field(default=None, ge=0, le=1)
    max_position_pct: Decimal | None = Field(default=None, ge=0, le=1)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    lineage_ids: dict[str, str] = Field(default_factory=dict)
    evaluation_version: str = EVALUATION_VERSION
    immutable_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime
    schema_version: str = EVALUATION_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_positions(self) -> "EvaluationSubject":
        if (
            self.initial_position_pct is not None
            and self.max_position_pct is not None
            and self.initial_position_pct > self.max_position_pct
        ):
            raise ValueError("initial_position_pct cannot exceed max_position_pct")
        if self.decision_stage == "BENCHMARK_SAFETY" and self.subject_type != "BENCHMARK_DECISION":
            raise ValueError("BENCHMARK_SAFETY must use BENCHMARK_DECISION")
        if self.subject_type == "BENCHMARK_DECISION" and self.decision_stage != "BENCHMARK_SAFETY":
            raise ValueError("Benchmark decision cannot masquerade as HardRisk")
        return self


class HorizonLabel(EvaluationSchema):
    label_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    horizon: Literal["1D", "5D", "10D", "20D"]
    status: Literal[
        "PENDING",
        "CALCULATED",
        "INSUFFICIENT_DATA",
        "INVALID_SOURCE",
    ]
    anchor_type: Literal[
        "DECISION_CLOSE",
        "PLANNED_ENTRY",
        "COUNTERFACTUAL_FILL",
        "ACTUAL_FILL",
    ]
    anchor_date: date
    anchor_price: Decimal | None = Field(default=None, gt=0)
    # Raw PR-006 fill price is retained separately; adjusted price labels must
    # never mix it arithmetically with an adjusted future close.
    execution_anchor_price: Decimal | None = Field(default=None, gt=0)
    horizon_end_date: date | None = None
    horizon_close_price: Decimal | None = Field(default=None, gt=0)
    raw_forward_return: Decimal | None = None
    action_aligned_return: Decimal | None = None
    benchmark_symbol: str | None = None
    benchmark_price_adjustment_mode: str | None = None
    benchmark_data_version: str | None = None
    benchmark_return: Decimal | None = None
    relative_benchmark_return: Decimal | None = None
    industry_id: str | None = None
    industry_price_adjustment_mode: str | None = None
    industry_data_version: str | None = None
    industry_unavailable_reason: str | None = None
    industry_benchmark_return: Decimal | None = None
    relative_industry_return: Decimal | None = None
    mfe: Decimal | None = None
    mae: Decimal | None = None
    entry_zone_touched: bool | None = None
    entry_first_touch_date: date | None = None
    stop_condition_touched: bool | None = None
    stop_first_touch_date: date | None = None
    exit_condition_touched: bool | None = None
    exit_first_touch_date: date | None = None
    data_refs: list[str] = Field(default_factory=list)
    price_adjustment_mode: str = Field(min_length=1)
    price_data_version: str = Field(min_length=1)
    calculation_version: str = LABEL_CALCULATION_VERSION
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    calculated_at: datetime | None = None
    schema_version: str = EVALUATION_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_status_payload(self) -> "HorizonLabel":
        calculated = self.status == "CALCULATED"
        required = (
            self.anchor_price,
            self.horizon_end_date,
            self.horizon_close_price,
            self.raw_forward_return,
            self.mfe,
            self.mae,
            self.calculated_at,
        )
        if calculated and any(value is None for value in required):
            raise ValueError("CALCULATED label lacks required price/result fields")
        if not calculated and any(
            value is not None
            for value in (
                self.raw_forward_return,
                self.action_aligned_return,
                self.benchmark_return,
                self.relative_benchmark_return,
                self.industry_benchmark_return,
                self.relative_industry_return,
                self.mfe,
                self.mae,
            )
        ):
            raise ValueError("non-calculated label cannot contain return results")
        if self.benchmark_return is not None and (
            not self.benchmark_symbol
            or not self.benchmark_price_adjustment_mode
            or not self.benchmark_data_version
        ):
            raise ValueError(
                "benchmark return requires symbol, adjustment mode and data version"
            )
        if self.industry_benchmark_return is not None and (
            not self.industry_id
            or not self.industry_price_adjustment_mode
            or not self.industry_data_version
        ):
            raise ValueError(
                "industry return requires identity, adjustment mode and data version"
            )
        if (
            calculated
            and self.anchor_type == "ACTUAL_FILL"
            and self.execution_anchor_price is None
        ):
            raise ValueError("ACTUAL_FILL label requires the raw execution price")
        return self


class CounterfactualEvaluation(EvaluationSchema):
    counterfactual_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    mode: Literal["SIGNAL_ONLY", "EXECUTABLE_SHADOW", "CONTINUE_HOLDING"]
    source_stage: str = Field(min_length=1)
    comparison_stage: str | None = None
    status: Literal[
        "PENDING",
        "NOT_ELIGIBLE",
        "NO_FILL",
        "PARTIALLY_FILLED",
        "FILLED",
        "CALCULATED",
        "INSUFFICIENT_DATA",
        "FAILED",
    ]
    shadow_account_basis_id: str | None = None
    normalized_notional: Decimal | None = Field(default=None, gt=0)
    hypothetical_intent: dict[str, Any] | None = None
    hypothetical_order: dict[str, Any] | None = None
    hypothetical_fills: list[dict[str, Any]] = Field(default_factory=list)
    gross_pnl: Decimal | None = None
    fees: Decimal | None = Field(default=None, ge=0)
    net_pnl: Decimal | None = None
    return_pct: Decimal | None = None
    max_adverse_excursion: Decimal | None = None
    max_favorable_excursion: Decimal | None = None
    execution_rule_version: str = COUNTERFACTUAL_VERSION
    fee_version: str = Field(min_length=1)
    matching_version: str = Field(min_length=1)
    input_refs: list[str] = Field(default_factory=list)
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime
    schema_version: str = EVALUATION_SCHEMA_VERSION


class AccountPerformanceMetric(EvaluationSchema):
    metric_id: str = Field(min_length=1)
    account_id: str = Field(min_length=1)
    account_type: str = Field(min_length=1)
    market: str = Field(min_length=1)
    period_start: date
    period_end: date
    status: Literal[
        "CALCULATED",
        "INCOMPLETE_VALUATION",
        "INSUFFICIENT_HISTORY",
    ]
    starting_equity: Decimal | None = None
    ending_equity: Decimal | None = None
    total_return: Decimal | None = None
    max_drawdown: Decimal | None = None
    realized_pnl: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    total_fees: Decimal | None = None
    fee_drag_pct: Decimal | None = None
    average_exposure_pct: Decimal | None = None
    turnover: Decimal | None = None
    filled_order_count: int = Field(ge=0)
    trade_count: int = Field(ge=0)
    win_rate: Decimal | None = Field(default=None, ge=0, le=1)
    profit_factor: Decimal | None = Field(default=None, ge=0)
    valuation_complete_days: int = Field(ge=0)
    valuation_incomplete_days: int = Field(ge=0)
    metric_version: str = ACCOUNT_METRIC_VERSION
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    calculated_at: datetime
    schema_version: str = EVALUATION_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_period(self) -> "AccountPerformanceMetric":
        if self.period_end < self.period_start:
            raise ValueError("metric period_end precedes period_start")
        return self


class PairedDecisionComparison(EvaluationSchema):
    comparison_id: str = Field(min_length=1)
    comparison_type: Literal[
        "QUANT_VS_NORMAL",
        "NORMAL_VS_TOP",
        "TOP_VS_HARD_RISK",
        "ORIGINAL_VS_RISK_REDUCED",
        "PLAN_VS_EXECUTION",
    ]
    snapshot_id: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    decision_trade_date: date
    left_subject_id: str = Field(min_length=1)
    right_subject_id: str | None = None
    pairing_status: Literal["PAIRED", "LEFT_ONLY", "RIGHT_ONLY", "NOT_COMPARABLE"]
    comparability_reasons: list[str] = Field(default_factory=list)
    horizon_results: dict[str, dict[str, Any]] = Field(default_factory=dict)
    execution_difference: dict[str, Any] = Field(default_factory=dict)
    risk_difference: dict[str, Any] = Field(default_factory=dict)
    value_added_1d: Decimal | None = None
    value_added_5d: Decimal | None = None
    value_added_10d: Decimal | None = None
    value_added_20d: Decimal | None = None
    comparison_version: str = COMPARISON_VERSION
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    calculated_at: datetime
    schema_version: str = EVALUATION_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_pair(self) -> "PairedDecisionComparison":
        if self.pairing_status == "PAIRED" and self.right_subject_id is None:
            raise ValueError("PAIRED comparison requires right_subject_id")
        if self.pairing_status != "PAIRED" and not self.comparability_reasons:
            raise ValueError("unpaired comparison requires a reason")
        return self


AttributionCategory = Literal[
    "DATA_QUALITY",
    "CANDIDATE_SELECTION",
    "FACTOR_FAILURE",
    "REGIME_MISCLASSIFICATION",
    "STRATEGY_ENTRY",
    "NORMAL_MODEL",
    "TOP_MODEL",
    "CONSENSUS",
    "HARD_RISK",
    "EXECUTION",
    "MARKET_SHOCK",
    "UNKNOWN",
]


class AttributionRecord(EvaluationSchema):
    attribution_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    lineage_ids: dict[str, str] = Field(default_factory=dict)
    status: Literal[
        "PENDING_HORIZON",
        "NOT_REQUIRED",
        "ATTRIBUTED",
        "INSUFFICIENT_EVIDENCE",
    ]
    outcome_class: Literal[
        "SUCCESS",
        "LOSS",
        "MISSED_OPPORTUNITY",
        "AVOIDED_LOSS",
        "NEUTRAL",
        "UNRESOLVED",
    ]
    primary_category: AttributionCategory | None = None
    contributing_categories: list[str] = Field(default_factory=list)
    confidence: Decimal = Field(ge=0, le=1)
    rule_ids: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    explanation_codes: list[str] = Field(default_factory=list)
    machine_explanation: str = Field(min_length=1)
    attribution_rule_version: str = ATTRIBUTION_RULE_VERSION
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    calculated_at: datetime | None = None
    schema_version: str = EVALUATION_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_attribution(self) -> "AttributionRecord":
        if self.status == "ATTRIBUTED" and (
            self.primary_category is None or not self.rule_ids or self.calculated_at is None
        ):
            raise ValueError("ATTRIBUTED record requires category, rule and time")
        return self


class AttributionOverride(EvaluationSchema):
    override_id: str = Field(min_length=1)
    attribution_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    previous_primary_category: str | None = None
    overridden_primary_category: AttributionCategory
    reason: str = Field(min_length=5, max_length=1000)
    created_at: datetime
    schema_version: str = EVALUATION_SCHEMA_VERSION


class EvaluationEvent(EvaluationSchema):
    event_id: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    trace_id: str | None = None
    evaluation_job_id: str | None = None
    subject_id: str | None = None
    source_object_id: str | None = None
    snapshot_id: str | None = None
    analysis_id: str | None = None
    proposal_id: str | None = None
    plan_id: str | None = None
    review_id: str | None = None
    consensus_id: str | None = None
    risk_decision_id: str | None = None
    intent_id: str | None = None
    order_id: str | None = None
    fill_id: str | None = None
    account_id: str | None = None
    user_id: str | None = None
    symbol: str | None = None
    decision_trade_date: date | None = None
    horizon: str | None = None
    evaluation_version: str = EVALUATION_VERSION
    input_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    reason: str = Field(min_length=1, max_length=1000)
    created_at: datetime
    schema_version: str = EVALUATION_SCHEMA_VERSION


class EvaluationRun(EvaluationSchema):
    evaluation_job_id: str = Field(min_length=1)
    as_of_trade_date: date
    user_id: str | None = None
    evaluation_version: str = EVALUATION_VERSION
    idempotency_key: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: Literal["PENDING", "RUNNING", "COMPLETED", "FAILED"]
    attempt_count: int = Field(default=0, ge=0)
    result: dict[str, Any] | None = None
    error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    schema_version: str = EVALUATION_SCHEMA_VERSION


class ModuleEvaluationMetric(EvaluationSchema):
    metric_id: str = Field(min_length=1)
    scope_user_id: str | None = None
    module_type: Literal[
        "FACTOR",
        "REGIME",
        "STRATEGY",
        "NORMAL_MODEL",
        "TOP_MODEL",
        "CONSENSUS",
        "HARD_RISK",
        "BENCHMARK_SAFETY",
        "EXECUTION",
    ]
    group_key: str = Field(min_length=1)
    period_start: date
    period_end: date
    status: Literal["CALCULATED", "INSUFFICIENT_SAMPLE", "NO_DATA"]
    sample_count: int = Field(ge=0)
    comparable_count: int = Field(ge=0)
    metrics: dict[str, Any] = Field(default_factory=dict)
    metric_version: str = "module-metric-v1"
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    calculated_at: datetime
    schema_version: str = EVALUATION_SCHEMA_VERSION


class EvaluationRunResult(EvaluationSchema):
    evaluation_job_id: str
    as_of_trade_date: date
    subjects_created: int = Field(ge=0)
    subjects_reused: int = Field(ge=0)
    labels_calculated: int = Field(ge=0)
    labels_pending: int = Field(ge=0)
    labels_insufficient: int = Field(ge=0)
    counterfactuals_created: int = Field(ge=0)
    account_metrics_created: int = Field(ge=0)
    comparisons_created: int = Field(ge=0)
    attributions_created: int = Field(ge=0)
    write_collections: list[str] = Field(default_factory=list)
    production_writes: Literal[False] = False
    schema_version: str = EVALUATION_SCHEMA_VERSION
