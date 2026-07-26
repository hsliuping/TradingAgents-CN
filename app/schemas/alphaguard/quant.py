"""Strict deterministic research contracts introduced by AlphaGuard PR-004."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from tradingagents.alphaguard.decision_schemas import EvidenceRef, PriceRange, RuleCondition
from tradingagents.alphaguard.instruments import Market, normalize_instrument


FACTOR_SCHEMA_VERSION = "factor-definition-v1"
FACTOR_RESULT_SCHEMA_VERSION = "factor-result-v1"
FACTOR_BUNDLE_SCHEMA_VERSION = "factor-evidence-bundle-v1"
REGIME_SCHEMA_VERSION = "market-regime-result-v1"
STRATEGY_SCHEMA_VERSION = "strategy-definition-v1"
PROPOSAL_SCHEMA_VERSION = "quant-trade-proposal-v1"
AUDIT_SCHEMA_VERSION = "quant-audit-event-v1"

FactorGroup = Literal[
    "TREND",
    "MOMENTUM",
    "QUALITY",
    "VALUATION",
    "LIQUIDITY",
    "VOLATILITY_RISK",
    "EVENT_RISK",
    "INDUSTRY_STRENGTH",
]
FactorDirection = Literal["POSITIVE", "NEUTRAL", "NEGATIVE", "UNKNOWN"]
Regime = Literal[
    "TREND_UP",
    "RANGE_STRONG",
    "RANGE_WEAK",
    "TREND_DOWN",
    "EXTREME_RISK",
]


class QuantSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        allow_inf_nan=False,
        str_strip_whitespace=True,
    )


class FactorDefinition(QuantSchema):
    factor_id: str = Field(min_length=1)
    factor_version: str = Field(min_length=1)
    name: str = Field(min_length=1)
    group: FactorGroup
    description: str = Field(min_length=1)
    formula_description: str = Field(min_length=1)
    required_inputs: list[str] = Field(min_length=1)
    lookback_trading_days: int = Field(ge=0)
    missing_policy: str = Field(min_length=1)
    normalization_method: str = Field(min_length=1)
    score_semantics: str = Field(min_length=1)
    parameters: dict[str, Any]
    code_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    parameter_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: Literal["ACTIVE", "INACTIVE", "RETIRED"]
    created_at: datetime
    schema_version: str = FACTOR_SCHEMA_VERSION


class FactorResult(QuantSchema):
    result_id: str = Field(min_length=1)
    factor_id: str = Field(min_length=1)
    factor_version: str = Field(min_length=1)
    group: FactorGroup
    symbol: str = Field(min_length=1)
    market: Market
    trade_date: date
    snapshot_id: str = Field(min_length=1)
    raw_value: float | None
    normalized_score: float | None = Field(default=None, ge=0, le=100)
    direction: FactorDirection
    confidence: float = Field(ge=0, le=1)
    missing_reason: str | None
    input_refs: list[str]
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    code_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    parameter_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    calculated_at: datetime
    schema_version: str = FACTOR_RESULT_SCHEMA_VERSION

    @model_validator(mode="before")
    @classmethod
    def normalize_identity(cls, value: Any) -> Any:
        if isinstance(value, dict) and value.get("symbol") and value.get("market"):
            data = dict(value)
            data["market"], data["symbol"] = normalize_instrument(
                data["symbol"], data["market"]
            )
            return data
        return value

    @model_validator(mode="after")
    def validate_missing_semantics(self) -> "FactorResult":
        missing = self.raw_value is None
        if missing and (
            self.normalized_score is not None
            or self.direction != "UNKNOWN"
            or self.confidence != 0
            or not self.missing_reason
        ):
            raise ValueError(
                "missing factor data requires null score, UNKNOWN, confidence 0, and reason"
            )
        if not missing and (
            self.normalized_score is None
            or self.direction == "UNKNOWN"
            or self.missing_reason is not None
        ):
            raise ValueError("calculated factor cannot use missing-value semantics")
        return self


class GroupAggregation(QuantSchema):
    valid_factor_count: int = Field(ge=0)
    total_factor_count: int = Field(ge=0)
    coverage: float = Field(ge=0, le=1)
    factor_weights: dict[str, float]
    missing_factor_ids: list[str]
    score: float | None = Field(default=None, ge=0, le=100)


class FactorEvidenceBundle(QuantSchema):
    snapshot_id: str = Field(min_length=1)
    factor_set_version: str = Field(min_length=1)
    results: list[FactorResult]
    group_scores: dict[str, float | None]
    group_coverage: dict[str, float]
    group_details: dict[str, GroupAggregation]
    missing_factor_ids: list[str]
    risk_flags: list[str]
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    calculated_at: datetime
    schema_version: str = FACTOR_BUNDLE_SCHEMA_VERSION

    @field_validator("group_coverage")
    @classmethod
    def valid_coverage(cls, value: dict[str, float]) -> dict[str, float]:
        if any(item < 0 or item > 1 for item in value.values()):
            raise ValueError("group coverage must be between 0 and 1")
        return value


class MarketRegimeResult(QuantSchema):
    regime_result_id: str = Field(min_length=1)
    snapshot_id: str = Field(min_length=1)
    trade_date: date
    calculation_status: Literal["CALCULATED", "INSUFFICIENT_DATA", "INVALID_INPUT"]
    regime: Regime | None
    confidence: float = Field(ge=0, le=1)
    evidence: list[str]
    metrics: dict[str, float | None]
    allowed_strategy_ids: list[str]
    allow_new_positions: bool
    max_total_exposure_pct: float | None = Field(default=None, ge=0, le=1)
    regime_version: str = Field(min_length=1)
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    calculated_at: datetime
    schema_version: str = REGIME_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_status(self) -> "MarketRegimeResult":
        if self.calculation_status == "CALCULATED" and self.regime is None:
            raise ValueError("CALCULATED regime requires a five-state regime value")
        if self.calculation_status != "CALCULATED":
            if self.regime is not None or self.allow_new_positions:
                raise ValueError("non-calculated regime cannot name a regime or allow new positions")
            if "SWING_TREND_PULLBACK_V1" in self.allowed_strategy_ids:
                raise ValueError("insufficient regime cannot allow the opening strategy")
        return self


class StrategyDefinition(QuantSchema):
    strategy_id: str = Field(min_length=1)
    strategy_version: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    status: Literal["DRAFT", "CHAMPION", "INACTIVE", "RETIRED"]
    supported_markets: list[str] = Field(min_length=1)
    allowed_regimes: list[Regime]
    factor_dependencies: dict[str, str]
    required_group_scores: list[str]
    parameters: dict[str, Any]
    code_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    parameter_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    parent_version: str | None
    created_at: datetime
    promoted_at: datetime | None
    schema_version: str = STRATEGY_SCHEMA_VERSION


class QuantTradeProposal(QuantSchema):
    proposal_id: str = Field(min_length=1)
    candidate_id: str | None
    user_id: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    market: Market
    trade_date: date
    snapshot_id: str = Field(min_length=1)
    strategy_id: str = Field(min_length=1)
    strategy_version: str = Field(min_length=1)
    regime_result_id: str = Field(min_length=1)
    factor_set_version: str = Field(min_length=1)
    status: Literal[
        "TRIGGERED", "WATCH", "REJECTED", "INSUFFICIENT_DATA", "INVALID_INPUT"
    ]
    action_candidate: Literal["BUY", "SELL", "REDUCE", "HOLD", "WAIT"]
    entry_zone: PriceRange | None
    initial_position_pct: float = Field(ge=0, le=1)
    max_position_pct: float = Field(ge=0, le=1)
    add_conditions: list[RuleCondition]
    reduce_conditions: list[RuleCondition]
    exit_conditions: list[RuleCondition]
    invalidation_conditions: list[RuleCondition]
    valid_until: datetime | None
    expected_holding_days: tuple[int, int] | None
    factor_summary: dict[str, float | None]
    factor_result_ids: list[str]
    evidence_refs: list[EvidenceRef]
    risk_flags: list[str]
    reason_codes: list[str]
    explanation: str = Field(min_length=1)
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime
    schema_version: str = PROPOSAL_SCHEMA_VERSION
    automated_execution_allowed: Literal[False] = False

    @model_validator(mode="before")
    @classmethod
    def normalize_identity(cls, value: Any) -> Any:
        if isinstance(value, dict) and value.get("symbol") and value.get("market"):
            data = dict(value)
            data["market"], data["symbol"] = normalize_instrument(
                data["symbol"], data["market"]
            )
            return data
        return value

    @model_validator(mode="after")
    def validate_proposal(self) -> "QuantTradeProposal":
        if self.initial_position_pct > self.max_position_pct:
            raise ValueError("initial position cannot exceed maximum position")
        if self.expected_holding_days is not None:
            lower, upper = self.expected_holding_days
            if lower < 0 or lower > upper:
                raise ValueError("invalid expected holding-day range")
        if self.status == "TRIGGERED" and self.action_candidate not in {
            "BUY",
            "SELL",
            "REDUCE",
        }:
            raise ValueError("TRIGGERED proposal requires BUY, SELL, or REDUCE")
        if self.status != "TRIGGERED" and self.action_candidate == "BUY":
            raise ValueError("only TRIGGERED proposals may suggest BUY")
        if self.action_candidate != "BUY" and self.entry_zone is not None:
            raise ValueError("entry_zone is only valid for BUY proposals")
        return self


class QuantAuditEvent(QuantSchema):
    event_id: str = Field(min_length=1)
    event_type: Literal[
        "FACTOR_DEFINITION_REGISTERED",
        "FACTOR_CALCULATED",
        "FACTOR_CALCULATION_FAILED",
        "REGIME_CALCULATED",
        "REGIME_CALCULATION_FAILED",
        "STRATEGY_DEFINITION_REGISTERED",
        "STRATEGY_EVALUATED",
        "STRATEGY_EVALUATION_FAILED",
        "QUANT_PROPOSAL_CREATED",
        "QUANT_INTEGRITY_CONFLICT",
    ]
    snapshot_id: str | None = None
    entity_id: str | None = None
    trace_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    schema_version: str = AUDIT_SCHEMA_VERSION
