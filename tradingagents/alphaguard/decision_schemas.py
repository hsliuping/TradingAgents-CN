"""Strict machine-readable decision contracts for AlphaGuard PR-002."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


ExecutionStatus = Literal[
    "SUCCESS",
    "MODEL_FAILED",
    "INVALID_OUTPUT",
    "NOT_RUN",
]
PlanStatus = Literal[
    "PROPOSE_TRADE",
    "NO_TRADE",
    "WAIT",
    "INSUFFICIENT_DATA",
    "MODEL_FAILED",
    "INVALID_OUTPUT",
]
PlanAction = Literal["BUY", "SELL", "REDUCE", "HOLD", "WAIT", "NONE"]
ReviewStatus = Literal[
    "CONFIRM",
    "RISK_ADJUST",
    "MATERIAL_REVISION",
    "REJECT",
    "SUSPEND",
    "MODEL_FAILED",
    "INVALID_OUTPUT",
]


class AlphaGuardSchema(BaseModel):
    """Shared strict settings for machine decision objects."""

    model_config = ConfigDict(
        extra="forbid",
        allow_inf_nan=False,
        str_strip_whitespace=True,
    )


class PriceRange(AlphaGuardSchema):
    lower: float = Field(ge=0)
    upper: float = Field(ge=0)
    currency: str | None = None

    @model_validator(mode="after")
    def validate_bounds(self) -> "PriceRange":
        if self.lower > self.upper:
            raise ValueError("PriceRange.lower must be less than or equal to upper")
        return self


class EvidenceRef(AlphaGuardSchema):
    evidence_id: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    source: str | None = None
    as_of: datetime | None = None


class RuleCondition(AlphaGuardSchema):
    condition_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    expression: str | None = None


class RiskItem(AlphaGuardSchema):
    risk_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = "MEDIUM"
    mitigation: str | None = None


class ModelExecutionMeta(AlphaGuardSchema):
    provider: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    prompt_name: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    started_at: datetime
    finished_at: datetime
    latency_ms: float = Field(ge=0)
    execution_status: ExecutionStatus
    request_id: str | None = None
    trace_id: str | None = None
    error_type: str | None = None
    error_message: str | None = None
    raw_output_hash: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )

    @model_validator(mode="after")
    def validate_timing_and_error(self) -> "ModelExecutionMeta":
        if self.finished_at < self.started_at:
            raise ValueError("finished_at must not precede started_at")
        if self.execution_status == "SUCCESS" and (
            self.error_type is not None or self.error_message is not None
        ):
            raise ValueError("successful executions cannot contain error details")
        if self.execution_status in {"MODEL_FAILED", "INVALID_OUTPUT", "NOT_RUN"}:
            if not self.error_type:
                raise ValueError("non-success executions require error_type")
        return self


class NormalTradePlan(AlphaGuardSchema):
    plan_id: str = Field(min_length=1)
    snapshot_id: str = Field(min_length=1)
    quant_proposal_id: str = Field(min_length=1)

    status: PlanStatus
    action: PlanAction
    confidence: float = Field(ge=0, le=1)
    thesis: str = Field(min_length=1)

    bullish_evidence: list[EvidenceRef]
    bearish_evidence: list[EvidenceRef]

    entry_zone: PriceRange | None
    initial_position_pct: float | None = Field(default=None, ge=0, le=1)
    max_position_pct: float | None = Field(default=None, ge=0, le=1)

    add_conditions: list[RuleCondition]
    stop_conditions: list[RuleCondition]
    reduce_conditions: list[RuleCondition]
    exit_conditions: list[RuleCondition]
    invalidation_conditions: list[RuleCondition]

    target_price: float | None = Field(default=None, gt=0)
    valid_until: datetime | None

    main_risks: list[RiskItem]
    unresolved_questions: list[str]

    model_meta: ModelExecutionMeta

    # PR-003 has not established a real EvidenceSnapshot/QuantProposal yet.
    # These explicit explanations are preferable to silently inventing values.
    entry_zone_not_required_reason: str | None = None
    valid_until_compatibility_reason: str | None = None

    @model_validator(mode="after")
    def validate_plan_semantics(self) -> "NormalTradePlan":
        allowed_actions = {
            "PROPOSE_TRADE": {"BUY", "SELL", "REDUCE"},
            "WAIT": {"WAIT"},
            "NO_TRADE": {"NONE", "HOLD"},
            "INSUFFICIENT_DATA": {"NONE"},
            "MODEL_FAILED": {"NONE"},
            "INVALID_OUTPUT": {"NONE"},
        }
        if self.action not in allowed_actions[self.status]:
            raise ValueError(
                f"action {self.action} is not valid for status {self.status}"
            )

        if (
            self.initial_position_pct is not None
            and self.max_position_pct is not None
            and self.initial_position_pct > self.max_position_pct
        ):
            raise ValueError(
                "initial_position_pct must be less than or equal to max_position_pct"
            )

        if self.status == "PROPOSE_TRADE":
            if self.confidence <= 0:
                raise ValueError("PROPOSE_TRADE requires confidence greater than zero")
            if self.initial_position_pct is None or self.max_position_pct is None:
                raise ValueError(
                    "PROPOSE_TRADE requires initial_position_pct and max_position_pct"
                )
            if not (
                self.stop_conditions
                or self.exit_conditions
                or self.invalidation_conditions
            ):
                raise ValueError(
                    "PROPOSE_TRADE requires a stop, exit, or invalidation condition"
                )
            if self.valid_until is None and not self.valid_until_compatibility_reason:
                raise ValueError(
                    "PROPOSE_TRADE requires valid_until or an explicit compatibility reason"
                )
            if (
                self.action == "BUY"
                and self.entry_zone is None
                and not self.entry_zone_not_required_reason
            ):
                raise ValueError(
                    "BUY requires entry_zone or an explicit omission reason"
                )

        if self.status in {
            "INSUFFICIENT_DATA",
            "MODEL_FAILED",
            "INVALID_OUTPUT",
        }:
            if any(
                value is not None
                for value in (
                    self.entry_zone,
                    self.initial_position_pct,
                    self.max_position_pct,
                    self.target_price,
                    self.valid_until,
                )
            ):
                raise ValueError(
                    f"{self.status} cannot contain executable price or position fields"
                )
        if self.status == "MODEL_FAILED" and self.model_meta.execution_status != "MODEL_FAILED":
            raise ValueError("MODEL_FAILED requires matching model execution metadata")
        if self.status == "INVALID_OUTPUT" and self.model_meta.execution_status != "INVALID_OUTPUT":
            raise ValueError("INVALID_OUTPUT requires matching model execution metadata")

        return self


class TopReviewDecision(AlphaGuardSchema):
    review_id: str = Field(min_length=1)
    snapshot_id: str = Field(min_length=1)
    plan_id: str = Field(min_length=1)

    status: ReviewStatus
    completeness_score: float = Field(ge=0, le=1)
    logic_consistency_score: float = Field(ge=0, le=1)
    risk_control_score: float = Field(ge=0, le=1)

    missing_evidence: list[str]
    logical_conflicts: list[str]
    risk_findings: list[RiskItem]

    adjusted_plan: NormalTradePlan | None
    material_change_fields: list[str]
    review_reason: str = Field(min_length=1)

    model_meta: ModelExecutionMeta

    @model_validator(mode="after")
    def validate_review_semantics(self) -> "TopReviewDecision":
        if self.status == "CONFIRM" and self.adjusted_plan is not None:
            raise ValueError("CONFIRM must not contain adjusted_plan")
        if self.status == "RISK_ADJUST" and self.adjusted_plan is None:
            raise ValueError("RISK_ADJUST requires adjusted_plan")
        if self.status == "MATERIAL_REVISION":
            if self.adjusted_plan is None:
                raise ValueError("MATERIAL_REVISION requires adjusted_plan")
            if not self.material_change_fields:
                raise ValueError(
                    "MATERIAL_REVISION requires material_change_fields"
                )
        if self.status in {
            "REJECT",
            "SUSPEND",
            "MODEL_FAILED",
            "INVALID_OUTPUT",
        } and self.adjusted_plan is not None:
            raise ValueError(f"{self.status} must not contain adjusted_plan")
        if self.status == "MODEL_FAILED" and self.model_meta.execution_status != "MODEL_FAILED":
            raise ValueError("MODEL_FAILED requires matching model execution metadata")
        if self.status == "INVALID_OUTPUT" and self.model_meta.execution_status not in {
            "INVALID_OUTPUT",
            "NOT_RUN",
        }:
            raise ValueError("INVALID_OUTPUT requires matching model execution metadata")
        return self


def validate_review_against_plan(
    review: TopReviewDecision,
    original_plan: NormalTradePlan,
) -> TopReviewDecision:
    """Prevent a top review from independently initiating/reversing a trade."""

    if review.plan_id != original_plan.plan_id:
        raise ValueError("TopReviewDecision.plan_id must reference the original plan")
    if review.snapshot_id != original_plan.snapshot_id:
        raise ValueError(
            "TopReviewDecision.snapshot_id must reference the original snapshot"
        )
    if review.adjusted_plan is None:
        return review

    adjusted = review.adjusted_plan
    if original_plan.status != "PROPOSE_TRADE" and adjusted.status == "PROPOSE_TRADE":
        raise ValueError("top review cannot independently initiate a trade")

    direction = {"BUY": 1, "SELL": -1, "REDUCE": -1}
    original_direction = direction.get(original_plan.action)
    adjusted_direction = direction.get(adjusted.action)
    if (
        original_direction is not None
        and adjusted_direction is not None
        and original_direction != adjusted_direction
    ):
        raise ValueError("top review cannot reverse the original trade direction")

    return review
