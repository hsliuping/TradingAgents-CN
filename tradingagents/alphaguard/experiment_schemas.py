"""Strict experiment-lab contracts for AlphaGuard PR-008.

The experiment namespace is deliberately isolated from production research,
decision and execution collections.  None of these records authorizes live
execution or an automatic Champion change.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from tradingagents.alphaguard.decision_schemas import ModelExecutionMeta


EXPERIMENT_SCHEMA_VERSION = "alphaguard-experiment-v1"
EXPERIMENT_REGISTRY_VERSION = "experiment-registry-v1"
EXPERIMENT_REPLAY_VERSION = "historical-replay-v1"
EXPERIMENT_METRIC_VERSION = "experiment-metric-v1"
EXPERIMENT_AUDIT_VERSION = "experiment-leakage-audit-v1"
EXPERIMENT_ROBUSTNESS_VERSION = "robustness-suite-v1"
EXPERIMENT_RISK_PROMPT_VERSION = "experiment_risk_review_v1"
PROMOTION_SAGA_VERSION = "promotion-saga-v1"

ExperimentComponentType = Literal[
    "FACTOR_FORMULA",
    "FACTOR_WEIGHT",
    "FACTOR_SET",
    "REGIME_CONFIG",
    "STRATEGY_CONFIG",
    "NORMAL_PROMPT",
    "TOP_PROMPT",
    "MODEL_CONFIG",
    "AGENT_CONFIG",
    "DEBATE_CONFIG",
    "HARD_RISK_CONFIG",
    "MATCHING_CONFIG",
]
ExperimentStatus = Literal[
    "DRAFT",
    "EXPERIMENT",
    "BACKTESTED",
    "SHADOW",
    "CHALLENGER",
    "CHAMPION",
    "DEGRADED",
    "SUSPENDED",
    "RETIRED",
]


def _canonical(value: Any, *, exclude: set[str]) -> Any:
    if isinstance(value, BaseModel):
        return _canonical(value.model_dump(mode="python"), exclude=exclude)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {
            str(key): _canonical(item, exclude=exclude)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            if key not in exclude and key != "_id"
        }
    if isinstance(value, (list, tuple)):
        return [_canonical(item, exclude=exclude) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted(_canonical(item, exclude=exclude) for item in value)
    return value


def experiment_hash(value: Any, *, exclude: set[str] | None = None) -> str:
    encoded = json.dumps(
        _canonical(value, exclude=exclude or set()),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class ExperimentSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        allow_inf_nan=False,
        str_strip_whitespace=True,
        json_encoders={Decimal: str},
    )


class ComponentVersionRecord(ExperimentSchema):
    """Immutable experiment-visible component version.

    The payload is a copy of an already versioned definition/config or a new
    Challenger definition.  It is never treated as a production pointer.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        allow_inf_nan=False,
        str_strip_whitespace=True,
    )

    version_ref: str = Field(min_length=1)
    component_type: ExperimentComponentType
    component_key: str = Field(min_length=1)
    market: str = Field(min_length=1)
    payload: dict[str, Any]
    payload_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    registration_supported: bool = True
    execution_supported: bool
    promotion_eligible: bool
    unsupported_reason: str | None = None
    source: Literal["CURRENT_CONFIG_IMPORT", "EXPERIMENT_VERSION"]
    parent_version_ref: str | None = None
    created_by: str = Field(min_length=1)
    created_at: datetime
    schema_version: str = EXPERIMENT_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_payload(self) -> "ComponentVersionRecord":
        if experiment_hash(self.payload) != self.payload_hash:
            raise ValueError("component version payload_hash mismatch")
        if not self.execution_supported and self.promotion_eligible:
            raise ValueError("non-executable component cannot be promotion eligible")
        if not self.execution_supported and not self.unsupported_reason:
            raise ValueError("non-executable component requires unsupported_reason")
        return self


class ExperimentDefinition(ExperimentSchema):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        allow_inf_nan=False,
        str_strip_whitespace=True,
    )

    experiment_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    hypothesis: str = Field(min_length=1)
    component_type: ExperimentComponentType
    component_key: str = Field(min_length=1)
    market: str = Field(min_length=1)
    baseline_version_ref: str = Field(min_length=1)
    challenger_version_ref: str = Field(min_length=1)
    primary_variable_path: str = Field(min_length=1)
    baseline_value_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    challenger_value_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    secondary_variable_paths: list[str] = Field(default_factory=list)
    experiment_mode: Literal["UNIVARIATE", "MULTIVARIATE"]
    promotion_eligible: bool
    execution_supported: bool
    unsupported_reason: str | None = None
    promotion_policy_version: str = Field(min_length=1)
    expected_improvement: list[str] = Field(default_factory=list)
    expected_risks: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)
    failure_criteria: list[str] = Field(default_factory=list)
    status: ExperimentStatus
    created_by: str = Field(min_length=1)
    created_at: datetime
    updated_at: datetime
    schema_version: str = EXPERIMENT_SCHEMA_VERSION
    immutable_definition_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_definition(self) -> "ExperimentDefinition":
        if self.baseline_version_ref == self.challenger_version_ref:
            raise ValueError("baseline and Challenger version refs must differ")
        if self.baseline_value_hash == self.challenger_value_hash:
            raise ValueError("primary variable must actually change")
        if self.experiment_mode == "UNIVARIATE" and self.secondary_variable_paths:
            raise ValueError("UNIVARIATE experiment cannot contain secondary variables")
        if self.experiment_mode == "MULTIVARIATE" and self.promotion_eligible:
            raise ValueError("MULTIVARIATE experiment cannot be promotion eligible")
        if not self.execution_supported and self.promotion_eligible:
            raise ValueError("unsupported execution cannot be promotion eligible")
        if not self.execution_supported and not self.unsupported_reason:
            raise ValueError("unsupported execution requires an explicit reason")
        if self.updated_at < self.created_at:
            raise ValueError("experiment updated_at precedes created_at")
        return self


class ExperimentVariableChange(ExperimentSchema):
    model_config = ConfigDict(extra="forbid", frozen=True)

    change_id: str = Field(min_length=1)
    experiment_id: str = Field(min_length=1)
    variable_path: str = Field(min_length=1)
    change_type: Literal[
        "PARAMETER",
        "FORMULA",
        "WEIGHT",
        "PROMPT",
        "MODEL",
        "COMPONENT_SET",
    ]
    baseline_value: Any
    challenger_value: Any
    is_primary: bool
    safety_impact: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    baseline_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    challenger_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime
    schema_version: str = EXPERIMENT_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_change(self) -> "ExperimentVariableChange":
        if self.baseline_hash == self.challenger_hash:
            raise ValueError("experiment variable change has identical values")
        if experiment_hash(self.baseline_value) != self.baseline_hash:
            raise ValueError("baseline variable hash mismatch")
        if experiment_hash(self.challenger_value) != self.challenger_hash:
            raise ValueError("Challenger variable hash mismatch")
        return self


class ExperimentDatasetManifest(ExperimentSchema):
    model_config = ConfigDict(extra="forbid", frozen=True)

    dataset_manifest_id: str = Field(min_length=1)
    experiment_id: str = Field(min_length=1)
    market: str = Field(min_length=1)
    symbols: list[str] = Field(min_length=1)
    snapshot_ids: list[str] = Field(min_length=1)
    start_trade_date: date
    end_trade_date: date
    selection_rule: str = Field(min_length=1)
    candidate_source_filters: list[str] = Field(default_factory=list)
    data_quality_filters: list[str] = Field(default_factory=list)
    price_data_versions: list[str] = Field(default_factory=list)
    financial_data_versions: list[str] = Field(default_factory=list)
    factor_input_versions: list[str] = Field(default_factory=list)
    created_from_cutoff_at: datetime
    source_collection_hashes: dict[str, str]
    manifest_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime
    schema_version: str = EXPERIMENT_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_manifest(self) -> "ExperimentDatasetManifest":
        if self.end_trade_date < self.start_trade_date:
            raise ValueError("dataset end date precedes start date")
        if self.snapshot_ids != sorted(set(self.snapshot_ids)):
            raise ValueError("snapshot_ids must be sorted and unique")
        if self.symbols != sorted(set(self.symbols)):
            raise ValueError("symbols must be sorted and unique")
        return self


class TimeSeriesSplitDefinition(ExperimentSchema):
    model_config = ConfigDict(extra="forbid", frozen=True)

    split_id: str = Field(min_length=1)
    dataset_manifest_id: str = Field(min_length=1)
    method: Literal[
        "ANCHORED_HOLDOUT",
        "ROLLING_WALK_FORWARD",
        "EXPANDING_WALK_FORWARD",
    ]
    train_start: date | None = None
    train_end: date | None = None
    validation_start: date | None = None
    validation_end: date | None = None
    test_start: date
    test_end: date
    embargo_trading_days: int = Field(ge=0)
    purge_overlapping_horizons: bool
    fold_number: int = Field(ge=1)
    split_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime
    schema_version: str = EXPERIMENT_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_time_order(self) -> "TimeSeriesSplitDefinition":
        if self.test_end < self.test_start:
            raise ValueError("test end precedes test start")
        if self.train_start and self.train_end and self.train_end < self.train_start:
            raise ValueError("train end precedes train start")
        if (
            self.validation_start
            and self.validation_end
            and self.validation_end < self.validation_start
        ):
            raise ValueError("validation end precedes validation start")
        if self.train_end and self.train_end >= self.test_start:
            raise ValueError("test data must be strictly later than train data")
        if self.validation_end and self.validation_end >= self.test_start:
            raise ValueError("test data must be strictly later than validation data")
        return self


class ExperimentRun(ExperimentSchema):
    run_id: str = Field(min_length=1)
    experiment_id: str = Field(min_length=1)
    dataset_manifest_id: str = Field(min_length=1)
    split_id: str | None = None
    run_type: Literal[
        "HISTORICAL_REPLAY",
        "OUT_OF_SAMPLE",
        "ROBUSTNESS",
        "SHADOW",
        "PAPER_CHALLENGER",
    ]
    status: Literal[
        "CREATED",
        "QUEUED",
        "RUNNING",
        "COMPLETED",
        "FAILED",
        "CANCELLED",
        "INSUFFICIENT_DATA",
        "INTEGRITY_CONFLICT",
    ]
    champion_version_refs: dict[str, str]
    challenger_version_refs: dict[str, str]
    code_commit: str = Field(min_length=1)
    code_tree_hash: str = Field(pattern=r"^[0-9a-f]{40,64}$")
    config_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    environment_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    reproducibility: Literal["DETERMINISTIC", "PROVIDER_BEST_EFFORT"]
    attempt_number: int = Field(default=1, ge=1)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    result_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    error_type: str | None = None
    error_message: str | None = None
    created_by: str = Field(min_length=1)
    created_at: datetime
    schema_version: str = EXPERIMENT_SCHEMA_VERSION


class ExperimentRunResult(ExperimentSchema):
    model_config = ConfigDict(extra="forbid", frozen=True)

    result_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    experiment_id: str = Field(min_length=1)
    sample_count: int = Field(ge=0)
    eligible_sample_count: int = Field(ge=0)
    executed_sample_count: int = Field(ge=0)
    insufficient_sample_count: int = Field(ge=0)
    gross_return: Decimal | None = None
    net_return: Decimal | None = None
    max_drawdown: Decimal | None = None
    return_drawdown_ratio: Decimal | None = None
    trade_count: int = Field(ge=0)
    win_rate: Decimal | None = Field(default=None, ge=0, le=1)
    profit_factor: Decimal | None = Field(default=None, ge=0)
    turnover: Decimal | None = Field(default=None, ge=0)
    fee_drag_pct: Decimal | None = Field(default=None, ge=0)
    average_mfe: Decimal | None = None
    average_mae: Decimal | None = None
    regime_breakdown: dict[str, dict] = Field(default_factory=dict)
    horizon_breakdown: dict[str, dict] = Field(default_factory=dict)
    top_trade_contribution_pct: Decimal | None = None
    top_five_trade_contribution_pct: Decimal | None = None
    champion_metrics: dict[str, Any]
    challenger_metrics: dict[str, Any]
    paired_metrics: dict[str, Any]
    status_flags: list[str] = Field(default_factory=list)
    metric_version: str = EXPERIMENT_METRIC_VERSION
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    result_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    calculated_at: datetime
    schema_version: str = EXPERIMENT_SCHEMA_VERSION


class ExperimentOutputPair(ExperimentSchema):
    """Immutable Champion/Challenger output for one fixed opportunity."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    output_id: str = Field(min_length=1)
    experiment_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    run_type: str = Field(min_length=1)
    snapshot_id: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    market: str = Field(min_length=1)
    trade_date: date
    decision_cutoff_at: datetime
    baseline_version_ref: str = Field(min_length=1)
    challenger_version_ref: str = Field(min_length=1)
    fixed_version_refs: dict[str, str]
    champion_output: dict[str, Any]
    challenger_output: dict[str, Any]
    difference: dict[str, Any]
    comparable: bool
    incomparability_reasons: list[str] = Field(default_factory=list)
    decision_input_refs: list[str] = Field(default_factory=list)
    evaluation_label_ids: list[str] = Field(default_factory=list)
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    result_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime
    schema_version: str = EXPERIMENT_SCHEMA_VERSION


class LeakageAuditReport(ExperimentSchema):
    model_config = ConfigDict(extra="forbid", frozen=True)

    leakage_audit_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    status: Literal["PASS", "FAIL", "INCOMPLETE"]
    future_price_leakage: bool
    future_financial_leakage: bool
    future_news_leakage: bool
    evaluation_label_leakage: bool
    split_overlap_leakage: bool
    current_config_leakage: bool
    violations: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    audit_version: str = EXPERIMENT_AUDIT_VERSION
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime
    schema_version: str = EXPERIMENT_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_status(self) -> "LeakageAuditReport":
        leaked = any(
            (
                self.future_price_leakage,
                self.future_financial_leakage,
                self.future_news_leakage,
                self.evaluation_label_leakage,
                self.split_overlap_leakage,
                self.current_config_leakage,
            )
        )
        if leaked and self.status != "FAIL":
            raise ValueError("any leakage finding requires FAIL")
        if self.status == "FAIL" and not self.violations:
            raise ValueError("FAIL leakage audit requires violations")
        return self


class RobustnessTestReport(ExperimentSchema):
    model_config = ConfigDict(extra="forbid", frozen=True)

    robustness_report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    status: Literal["PASS", "FAIL", "INCOMPLETE"]
    scenarios: list[dict[str, Any]]
    cost_stress_result: dict[str, Any]
    slippage_stress_result: dict[str, Any]
    delayed_entry_result: dict[str, Any]
    missing_data_result: dict[str, Any]
    regime_segment_result: dict[str, Any]
    outlier_dependency_result: dict[str, Any]
    failed_scenarios: list[str] = Field(default_factory=list)
    robustness_version: str = EXPERIMENT_ROBUSTNESS_VERSION
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime
    schema_version: str = EXPERIMENT_SCHEMA_VERSION


class ShadowRun(ExperimentSchema):
    shadow_run_id: str = Field(min_length=1)
    experiment_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    status: Literal[
        "ACTIVE",
        "PAUSED",
        "COMPLETED",
        "FAILED",
        "INSUFFICIENT_DATA",
    ]
    started_at: datetime
    ended_at: datetime | None = None
    champion_output_count: int = Field(ge=0)
    challenger_output_count: int = Field(ge=0)
    paired_output_count: int = Field(ge=0)
    divergence_count: int = Field(ge=0)
    integrity_error_count: int = Field(ge=0)
    min_required_trade_days: int = Field(ge=1)
    observed_trade_days: int = Field(ge=0)
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime
    schema_version: str = EXPERIMENT_SCHEMA_VERSION


class ChallengerAssignment(ExperimentSchema):
    assignment_id: str = Field(min_length=1)
    experiment_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    market: str = Field(min_length=1)
    account_id: str = Field(min_length=1)
    activation_trade_date: date
    deactivation_trade_date: date | None = None
    baseline_account_snapshot_id: str = Field(min_length=1)
    starting_equity: Decimal = Field(gt=0)
    status: Literal["PENDING", "ACTIVE", "CLOSING", "COMPLETED", "SUSPENDED"]
    exclusivity_key: str = Field(min_length=1)
    created_at: datetime
    activated_at: datetime | None = None
    schema_version: str = EXPERIMENT_SCHEMA_VERSION


class ChampionComparisonReport(ExperimentSchema):
    model_config = ConfigDict(extra="forbid", frozen=True)

    comparison_report_id: str = Field(min_length=1)
    experiment_id: str = Field(min_length=1)
    status: Literal["READY", "INSUFFICIENT_DATA", "NOT_COMPARABLE", "FAILED"]
    historical_result_ids: list[str] = Field(default_factory=list)
    out_of_sample_result_ids: list[str] = Field(default_factory=list)
    robustness_report_ids: list[str] = Field(default_factory=list)
    shadow_run_ids: list[str] = Field(default_factory=list)
    challenger_assignment_ids: list[str] = Field(default_factory=list)
    sample_count: int = Field(ge=0)
    paired_sample_count: int = Field(ge=0)
    paired_coverage: Decimal | None = Field(default=None, ge=0, le=1)
    champion_summary: dict[str, Any]
    challenger_summary: dict[str, Any]
    value_added_summary: dict[str, Any]
    return_comparison: dict[str, Any]
    drawdown_comparison: dict[str, Any]
    cost_comparison: dict[str, Any]
    turnover_comparison: dict[str, Any]
    regime_stability_comparison: dict[str, Any]
    outlier_dependency_comparison: dict[str, Any]
    leakage_status: str = Field(min_length=1)
    robustness_status: str = Field(min_length=1)
    shadow_consistency_status: str = Field(min_length=1)
    challenger_consistency_status: str = Field(min_length=1)
    gate_results: list[dict[str, Any]]
    promotion_policy_version: str = Field(min_length=1)
    report_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime
    schema_version: str = EXPERIMENT_SCHEMA_VERSION


class ExperimentRiskReview(ExperimentSchema):
    model_config = ConfigDict(extra="forbid", frozen=True)

    review_id: str = Field(min_length=1)
    experiment_id: str = Field(min_length=1)
    comparison_report_id: str = Field(min_length=1)
    status: Literal[
        "READY_FOR_HUMAN_REVIEW",
        "MORE_VALIDATION_REQUIRED",
        "REJECT",
        "SUSPEND",
        "MODEL_FAILED",
        "INVALID_OUTPUT",
    ]
    leakage_concerns: list[str] = Field(default_factory=list)
    overfitting_concerns: list[str] = Field(default_factory=list)
    sample_concerns: list[str] = Field(default_factory=list)
    regime_concerns: list[str] = Field(default_factory=list)
    execution_concerns: list[str] = Field(default_factory=list)
    rollback_concerns: list[str] = Field(default_factory=list)
    required_followups: list[str] = Field(default_factory=list)
    risk_summary: str = Field(min_length=1)
    model_meta: ModelExecutionMeta
    prompt_version: str = EXPERIMENT_RISK_PROMPT_VERSION
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime
    schema_version: str = EXPERIMENT_SCHEMA_VERSION


class PromotionPolicy(ExperimentSchema):
    model_config = ConfigDict(extra="forbid", frozen=True)

    policy_id: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    required_run_types: list[str]
    minimum_sample_rules: dict[str, int | Decimal | None]
    maximum_integrity_errors: int = Field(ge=0)
    require_leakage_pass: bool
    require_robustness_pass: bool
    require_shadow: bool
    require_paper_challenger: bool
    require_top_risk_review: bool
    require_human_approval: bool
    performance_thresholds: dict[str, Decimal | None]
    risk_thresholds: dict[str, Decimal | int | None]
    stability_thresholds: dict[str, Decimal | int | None]
    created_at: datetime
    immutable_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    schema_version: str = EXPERIMENT_SCHEMA_VERSION


class PromotionRequest(ExperimentSchema):
    promotion_request_id: str = Field(min_length=1)
    experiment_id: str = Field(min_length=1)
    comparison_report_id: str = Field(min_length=1)
    risk_review_id: str = Field(min_length=1)
    requested_by: str = Field(min_length=1)
    requested_at: datetime
    target_champion_slot_id: str = Field(min_length=1)
    current_champion_version_ref: str = Field(min_length=1)
    proposed_champion_version_ref: str = Field(min_length=1)
    current_champion_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    proposed_champion_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    promotion_policy_version: str = Field(min_length=1)
    effective_from_trade_date: date
    policy_check_status: Literal["PASS", "FAIL", "INCOMPLETE"]
    failed_policy_rules: list[str] = Field(default_factory=list)
    required_confirmation_text: str = Field(min_length=1)
    status: Literal[
        "PENDING_APPROVAL",
        "APPROVED",
        "REJECTED",
        "EXPIRED",
        "CANCELLED",
        "APPLIED",
        "FAILED",
    ]
    request_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    schema_version: str = EXPERIMENT_SCHEMA_VERSION


class PromotionApproval(ExperimentSchema):
    model_config = ConfigDict(extra="forbid", frozen=True)

    approval_id: str = Field(min_length=1)
    promotion_request_id: str = Field(min_length=1)
    approved: bool
    approved_by: str = Field(min_length=1)
    decision_reason: str = Field(min_length=3)
    confirmation_text: str = Field(min_length=1)
    current_champion_hash_confirmed: str = Field(pattern=r"^[0-9a-f]{64}$")
    proposed_champion_hash_confirmed: str = Field(pattern=r"^[0-9a-f]{64}$")
    approved_at: datetime
    schema_version: str = EXPERIMENT_SCHEMA_VERSION


class ChampionAssignment(ExperimentSchema):
    champion_slot_id: str = Field(min_length=1)
    component_type: ExperimentComponentType
    component_key: str = Field(min_length=1)
    market: str = Field(min_length=1)
    current_version_ref: str = Field(min_length=1)
    previous_version_ref: str | None = None
    source_experiment_id: str | None = None
    source_promotion_request_id: str | None = None
    effective_from_trade_date: date
    assignment_version: int = Field(ge=1)
    status: Literal["ACTIVE", "DEGRADED", "SUSPENDED"]
    assignment_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    promotion_saga_id: str | None = None
    updated_by: str = Field(min_length=1)
    updated_at: datetime
    schema_version: str = EXPERIMENT_SCHEMA_VERSION


class ChampionAssignmentHistory(ExperimentSchema):
    model_config = ConfigDict(extra="forbid", frozen=True)

    history_id: str = Field(min_length=1)
    champion_slot_id: str = Field(min_length=1)
    assignment: ChampionAssignment
    committed_saga_id: str | None = None
    recorded_at: datetime
    schema_version: str = EXPERIMENT_SCHEMA_VERSION


class ChampionResolution(ExperimentSchema):
    champion_slot_id: str
    component_type: ExperimentComponentType
    component_key: str
    market: str
    as_of_trade_date: date
    version_ref: str
    component_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    assignment_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    assignment_version: int = Field(ge=1)
    effective_from_trade_date: date
    resolved_at: datetime
    schema_version: str = EXPERIMENT_SCHEMA_VERSION


class PromotionSaga(ExperimentSchema):
    promotion_saga_id: str = Field(min_length=1)
    operation: Literal["PROMOTION", "ROLLBACK"]
    promotion_request_id: str | None = None
    rollback_id: str | None = None
    champion_slot_id: str = Field(min_length=1)
    status: Literal[
        "PREPARED",
        "LOCK_ACQUIRED",
        "CURRENT_CHAMPION_VERIFIED",
        "ASSIGNMENT_WRITTEN",
        "RESOLVER_VERIFIED",
        "COMMITTED",
        "ROLLBACK_REQUIRED",
        "ROLLED_BACK",
        "FAILED",
    ]
    from_version_ref: str = Field(min_length=1)
    to_version_ref: str = Field(min_length=1)
    expected_assignment_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    written_assignment_hash: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    effective_from_trade_date: date
    lock_key: str = Field(min_length=1)
    attempt_count: int = Field(default=1, ge=1)
    last_error: str | None = None
    created_by: str = Field(min_length=1)
    created_at: datetime
    updated_at: datetime
    committed_at: datetime | None = None
    saga_version: str = PROMOTION_SAGA_VERSION
    schema_version: str = EXPERIMENT_SCHEMA_VERSION


class RollbackRecord(ExperimentSchema):
    rollback_id: str = Field(min_length=1)
    champion_slot_id: str = Field(min_length=1)
    from_version_ref: str = Field(min_length=1)
    to_version_ref: str = Field(min_length=1)
    reason: str = Field(min_length=3)
    requested_by: str = Field(min_length=1)
    approved_by: str = Field(min_length=1)
    effective_from_trade_date: date
    promotion_saga_id: str | None = None
    status: Literal["PREPARED", "COMMITTED", "FAILED"]
    created_at: datetime
    schema_version: str = EXPERIMENT_SCHEMA_VERSION


class ExperimentEvent(ExperimentSchema):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    trace_id: str | None = None
    experiment_id: str | None = None
    run_id: str | None = None
    dataset_manifest_id: str | None = None
    split_id: str | None = None
    shadow_run_id: str | None = None
    assignment_id: str | None = None
    comparison_report_id: str | None = None
    risk_review_id: str | None = None
    promotion_request_id: str | None = None
    promotion_saga_id: str | None = None
    champion_slot_id: str | None = None
    baseline_version_ref: str | None = None
    challenger_version_ref: str | None = None
    current_champion_version_ref: str | None = None
    user_id: str | None = None
    market: str | None = None
    input_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    result_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    reason: str = Field(min_length=1, max_length=1000)
    created_at: datetime
    schema_version: str = EXPERIMENT_SCHEMA_VERSION


class ExperimentTaskRun(ExperimentSchema):
    task_run_id: str = Field(min_length=1)
    job_type: str = Field(min_length=1)
    experiment_id: str | None = None
    trade_date: date | None = None
    idempotency_key: str = Field(min_length=1)
    status: Literal["PENDING", "RUNNING", "COMPLETED", "FAILED"]
    attempt_count: int = Field(ge=1)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime
    schema_version: str = EXPERIMENT_SCHEMA_VERSION
