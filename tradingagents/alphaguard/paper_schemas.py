"""Strict automatic paper-trading contracts for AlphaGuard PR-006.

These objects are intentionally separate from the legacy manual paper-trading
collections and API.  Every executable object is permanently paper-only.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from tradingagents.alphaguard.decision_control_schemas import RiskRuleResult


PAPER_SCHEMA_VERSION = "alphaguard-paper-v1"
ACCOUNT_POLICY_VERSION = "paper-account-policy-v1"
EXECUTION_POLICY_VERSION = "paper-execution-policy-v1"
FEE_POLICY_VERSION = "paper-fee-policy-v1"
MATCHING_ENGINE_VERSION = "matching-engine-v1"
SETTLEMENT_SAGA_VERSION = "settlement-saga-v1"

AccountType = Literal[
    "PAPER_QUANT",
    "PAPER_NORMAL",
    "PAPER_TOP_CONFIRMED",
    "PAPER_CHALLENGER",
]
TradeAction = Literal["BUY", "SELL", "REDUCE"]
OrderSide = Literal["BUY", "SELL"]
OrderType = Literal["LIMIT", "MARKET_ON_OPEN"]


def _canonical_value(value: Any, *, exclude: set[str]) -> Any:
    if isinstance(value, BaseModel):
        return _canonical_value(value.model_dump(mode="python"), exclude=exclude)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {
            str(key): _canonical_value(item, exclude=exclude)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            if key not in exclude and key != "_id"
        }
    if isinstance(value, (list, tuple)):
        return [_canonical_value(item, exclude=exclude) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted(_canonical_value(item, exclude=exclude) for item in value)
    return value


def paper_canonical_hash(
    value: Any,
    *,
    exclude: set[str] | None = None,
) -> str:
    payload = json.dumps(
        _canonical_value(value, exclude=exclude or set()),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class PaperSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        allow_inf_nan=False,
        str_strip_whitespace=True,
        json_encoders={Decimal: str},
    )
    execution_environment: Literal["PAPER"] = "PAPER"
    live_execution_allowed: Literal[False] = False


class PaperAccount(PaperSchema):
    account_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    account_type: AccountType
    market: Literal["CN"] = "CN"
    currency: Literal["CNY"] = "CNY"
    status: Literal["ACTIVE", "SUSPENDED", "CLOSED"] = "ACTIVE"
    initial_cash: Decimal = Field(ge=0)
    cash_available: Decimal = Field(ge=0)
    cash_reserved: Decimal = Field(ge=0)
    realized_pnl: Decimal = Decimal("0")
    total_fees: Decimal = Field(default=Decimal("0"), ge=0)
    created_at: datetime
    updated_at: datetime
    account_config_version: str = Field(min_length=1)
    account_version: int = Field(default=1, ge=1)
    applied_reservation_ids: list[str] = Field(default_factory=list)
    released_reservation_ids: list[str] = Field(default_factory=list)
    applied_settlement_ids: list[str] = Field(default_factory=list)
    schema_version: str = PAPER_SCHEMA_VERSION
    execution_environment: Literal["PAPER"] = "PAPER"
    live_execution_allowed: Literal[False] = False

    @model_validator(mode="after")
    def validate_cash(self) -> "PaperAccount":
        if self.updated_at < self.created_at:
            raise ValueError("account updated_at cannot precede created_at")
        for values in (
            self.applied_reservation_ids,
            self.released_reservation_ids,
            self.applied_settlement_ids,
        ):
            if len(values) != len(set(values)):
                raise ValueError("account idempotency markers must be unique")
        return self


class BenchmarkExecutionDecision(PaperSchema):
    benchmark_decision_id: str = Field(min_length=1)
    source_type: Literal["QUANT", "NORMAL"]
    source_object_id: str = Field(min_length=1)
    account_id: str = Field(min_length=1)
    status: Literal["PASS", "REDUCE", "REJECT", "SUSPEND"]
    action: TradeAction
    approved_position_pct: float | None = Field(default=None, ge=0, le=1)
    approved_quantity: int | None = Field(default=None, ge=0)
    rules: list[RiskRuleResult]
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime
    benchmark_only: Literal[True] = True
    consensus_approved: Literal[False] = False
    hard_risk_approved: Literal[False] = False
    execution_environment: Literal["PAPER"] = "PAPER"
    live_execution_allowed: Literal[False] = False
    schema_version: str = PAPER_SCHEMA_VERSION


class OrderIntent(PaperSchema):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        allow_inf_nan=False,
        str_strip_whitespace=True,
        json_encoders={Decimal: str},
    )

    intent_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    account_id: str = Field(min_length=1)
    account_type: AccountType
    source_type: Literal[
        "QUANT_PROPOSAL",
        "NORMAL_PLAN",
        "RISK_DECISION",
        "CHALLENGER",
    ]
    source_object_id: str = Field(min_length=1)
    analysis_id: str | None = None
    candidate_id: str | None = None
    snapshot_id: str = Field(min_length=1)
    quant_proposal_id: str | None = None
    plan_id: str | None = None
    consensus_id: str | None = None
    risk_decision_id: str | None = None
    experiment_id: str | None = None
    assignment_id: str | None = None
    challenger_version_id: str | None = None
    baseline_champion_id: str | None = None
    config_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    run_mode: Literal["PAPER_CHALLENGER"] | None = None
    symbol: str = Field(pattern=r"^\d{6}$")
    market: Literal["CN"] = "CN"
    currency: Literal["CNY"] = "CNY"
    original_action: TradeAction
    side: OrderSide
    order_type: OrderType
    quantity: int = Field(gt=0)
    limit_price: Decimal | None = Field(default=None, gt=0)
    earliest_execute_at: datetime
    expires_at: datetime
    execution_policy_version: str = Field(min_length=1)
    matching_engine_version: str = Field(min_length=1)
    fee_policy_version: str = Field(min_length=1)
    account_state_snapshot_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    immutable_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime
    schema_version: str = PAPER_SCHEMA_VERSION
    benchmark_only: bool
    consensus_approved: bool
    hard_risk_approved: bool
    execution_environment: Literal["PAPER"] = "PAPER"
    live_execution_allowed: Literal[False] = False

    @model_validator(mode="after")
    def validate_intent(self) -> "OrderIntent":
        expected_side = "BUY" if self.original_action == "BUY" else "SELL"
        if self.side != expected_side:
            raise ValueError("OrderIntent side does not match original action")
        if self.order_type == "LIMIT" and self.limit_price is None:
            raise ValueError("LIMIT intent requires a limit price")
        if self.order_type == "MARKET_ON_OPEN" and self.limit_price is not None:
            raise ValueError("MARKET_ON_OPEN intent cannot contain a limit price")
        if self.expires_at < self.earliest_execute_at:
            raise ValueError("intent expires before earliest execution")
        if self.account_type == "PAPER_TOP_CONFIRMED":
            if (
                self.source_type != "RISK_DECISION"
                or self.benchmark_only
                or not self.consensus_approved
                or not self.hard_risk_approved
            ):
                raise ValueError("TOP_CONFIRMED intent requires consensus and hard risk")
        elif self.account_type in {"PAPER_QUANT", "PAPER_NORMAL"}:
            if not self.benchmark_only:
                raise ValueError("quant and normal intents must be benchmark-only")
            if self.consensus_approved or self.hard_risk_approved:
                raise ValueError("benchmark intent cannot claim decision approval")
        elif self.account_type == "PAPER_CHALLENGER":
            if (
                self.source_type != "CHALLENGER"
                or self.benchmark_only
                or not self.consensus_approved
                or not self.hard_risk_approved
                or not self.experiment_id
                or not self.assignment_id
                or not self.challenger_version_id
                or not self.baseline_champion_id
                or not self.config_hash
                or self.run_mode != "PAPER_CHALLENGER"
            ):
                raise ValueError(
                    "PAPER_CHALLENGER intent requires experiment lineage and "
                    "full consensus/hard-risk approval"
                )
        if (
            self.account_type != "PAPER_CHALLENGER"
            and any(
                value is not None
                for value in (
                    self.experiment_id,
                    self.assignment_id,
                    self.challenger_version_id,
                    self.baseline_champion_id,
                    self.config_hash,
                    self.run_mode,
                )
            )
        ):
            raise ValueError(
                "experiment lineage is reserved for PAPER_CHALLENGER"
            )
        hash_excludes = {"intent_id", "immutable_hash", "created_at"}
        # Preserve PR-006 immutable hashes for legacy/non-experiment intents.
        # Challenger hashes bind both lineage fields when present.
        if self.run_mode is None:
            hash_excludes.update(
                {
                    "experiment_id",
                    "assignment_id",
                    "challenger_version_id",
                    "baseline_champion_id",
                    "config_hash",
                    "run_mode",
                }
            )
        expected_hash = paper_canonical_hash(
            self,
            exclude=hash_excludes,
        )
        if expected_hash != self.immutable_hash:
            raise ValueError("OrderIntent immutable_hash mismatch")
        return self


class ExecutionOutboxEvent(PaperSchema):
    outbox_event_id: str = Field(min_length=1)
    event_type: Literal[
        "CREATE_TOP_CONFIRMED_INTENT",
        "CREATE_QUANT_BENCHMARK_INTENT",
        "CREATE_NORMAL_BENCHMARK_INTENT",
        "CREATE_CHALLENGER_INTENT",
    ]
    source_object_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    account_id: str | None = None
    analysis_id: str | None = None
    candidate_id: str | None = None
    snapshot_id: str | None = None
    experiment_id: str | None = None
    assignment_id: str | None = None
    challenger_version_id: str | None = None
    baseline_champion_id: str | None = None
    config_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    run_mode: Literal["PAPER_CHALLENGER"] | None = None
    status: Literal[
        "PENDING",
        "PROCESSING",
        "COMPLETED",
        "FAILED",
        "DEAD_LETTER",
    ] = "PENDING"
    attempt_count: int = Field(default=0, ge=0)
    max_attempts: int = Field(default=5, ge=1)
    next_attempt_at: datetime | None = None
    last_error: str | None = None
    error_history: list[dict[str, Any]] = Field(default_factory=list)
    idempotency_key: str = Field(min_length=1)
    created_at: datetime
    updated_at: datetime
    schema_version: str = PAPER_SCHEMA_VERSION
    execution_environment: Literal["PAPER"] = "PAPER"
    live_execution_allowed: Literal[False] = False

    @model_validator(mode="after")
    def validate_challenger_lineage(self) -> "ExecutionOutboxEvent":
        lineage = (
            self.experiment_id,
            self.assignment_id,
            self.challenger_version_id,
            self.baseline_champion_id,
            self.config_hash,
        )
        if self.event_type == "CREATE_CHALLENGER_INTENT":
            if (
                self.run_mode != "PAPER_CHALLENGER"
                or not self.snapshot_id
                or not all(lineage)
            ):
                raise ValueError("Challenger outbox requires complete experiment lineage")
        elif self.run_mode is not None or any(value is not None for value in lineage):
            raise ValueError("experiment lineage is reserved for Challenger outbox")
        return self


class PaperOrder(PaperSchema):
    order_id: str = Field(min_length=1)
    intent_id: str = Field(min_length=1)
    account_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    account_type: AccountType
    candidate_id: str | None = None
    source_type: str = Field(min_length=1)
    source_object_id: str = Field(min_length=1)
    risk_decision_id: str | None = None
    snapshot_id: str | None = None
    experiment_id: str | None = None
    assignment_id: str | None = None
    challenger_version_id: str | None = None
    baseline_champion_id: str | None = None
    config_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    run_mode: Literal["PAPER_CHALLENGER"] | None = None
    symbol: str = Field(pattern=r"^\d{6}$")
    market: Literal["CN"] = "CN"
    currency: Literal["CNY"] = "CNY"
    side: OrderSide
    original_action: TradeAction
    order_type: OrderType
    requested_quantity: int = Field(gt=0)
    reserved_quantity: int = Field(default=0, ge=0)
    filled_quantity: int = Field(default=0, ge=0)
    remaining_quantity: int = Field(ge=0)
    limit_price: Decimal | None = Field(default=None, gt=0)
    average_fill_price: Decimal | None = Field(default=None, gt=0)
    reserved_cash: Decimal = Field(default=Decimal("0"), ge=0)
    total_notional: Decimal = Field(default=Decimal("0"), ge=0)
    total_fees: Decimal = Field(default=Decimal("0"), ge=0)
    status: Literal[
        "CREATED",
        "RESERVED",
        "SUBMITTED",
        "PENDING",
        "PARTIALLY_FILLED",
        "SETTLEMENT_PENDING",
        "SETTLEMENT_FAILED",
        "FILLED",
        "CANCELLED",
        "REJECTED",
        "EXPIRED",
    ] = "CREATED"
    reject_reason: str | None = None
    trade_date: date
    earliest_execute_at: datetime
    expires_at: datetime
    submitted_at: datetime | None = None
    last_matched_trade_date: date | None = None
    filled_at: datetime | None = None
    cancelled_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    order_version: int = Field(default=1, ge=1)
    schema_version: str = PAPER_SCHEMA_VERSION
    execution_environment: Literal["PAPER"] = "PAPER"
    live_execution_allowed: Literal[False] = False

    @model_validator(mode="after")
    def validate_quantities(self) -> "PaperOrder":
        if self.filled_quantity + self.remaining_quantity != self.requested_quantity:
            raise ValueError("filled plus remaining must equal requested quantity")
        if self.reserved_quantity > self.remaining_quantity:
            raise ValueError("reserved quantity cannot exceed remaining quantity")
        if self.status == "FILLED" and self.remaining_quantity != 0:
            raise ValueError("FILLED order must have no remaining quantity")
        lineage = (
            self.experiment_id,
            self.assignment_id,
            self.challenger_version_id,
            self.baseline_champion_id,
            self.config_hash,
        )
        if self.account_type == "PAPER_CHALLENGER":
            if (
                self.run_mode != "PAPER_CHALLENGER"
                or not self.snapshot_id
                or not all(lineage)
            ):
                raise ValueError("Challenger order requires complete experiment lineage")
        elif self.run_mode is not None or any(value is not None for value in lineage):
            raise ValueError("experiment lineage is reserved for Challenger orders")
        return self


class LotAllocation(PaperSchema):
    lot_id: str = Field(min_length=1)
    reserved_quantity: int = Field(gt=0)
    consumed_quantity: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_consumption(self) -> "LotAllocation":
        if self.consumed_quantity > self.reserved_quantity:
            raise ValueError("lot consumption exceeds reservation")
        return self


class PaperReservation(PaperSchema):
    reservation_id: str = Field(min_length=1)
    order_id: str = Field(min_length=1)
    account_id: str = Field(min_length=1)
    snapshot_id: str | None = None
    experiment_id: str | None = None
    assignment_id: str | None = None
    challenger_version_id: str | None = None
    baseline_champion_id: str | None = None
    config_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    run_mode: Literal["PAPER_CHALLENGER"] | None = None
    reservation_type: Literal["CASH", "POSITION"]
    currency: Literal["CNY"] | None = None
    symbol: str | None = None
    lot_allocations: list[LotAllocation] = Field(default_factory=list)
    reserved_amount: Decimal | None = Field(default=None, ge=0)
    reserved_quantity: int | None = Field(default=None, ge=0)
    consumed_amount: Decimal = Field(default=Decimal("0"), ge=0)
    consumed_quantity: int = Field(default=0, ge=0)
    status: Literal[
        "ACTIVE",
        "PARTIALLY_CONSUMED",
        "CONSUMED",
        "RELEASED",
    ] = "ACTIVE"
    applied_settlement_ids: list[str] = Field(default_factory=list)
    idempotency_key: str = Field(min_length=1)
    created_at: datetime
    updated_at: datetime
    schema_version: str = PAPER_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_reservation(self) -> "PaperReservation":
        if self.reservation_type == "CASH":
            if self.currency != "CNY" or self.reserved_amount is None:
                raise ValueError("cash reservation requires CNY amount")
            if self.symbol is not None or self.lot_allocations:
                raise ValueError("cash reservation cannot allocate lots")
            if self.consumed_amount > self.reserved_amount:
                raise ValueError("cash consumption exceeds reservation")
        else:
            if not self.symbol or self.reserved_quantity is None:
                raise ValueError("position reservation requires symbol and quantity")
            if self.reserved_amount is not None or self.currency is not None:
                raise ValueError("position reservation cannot reserve cash")
            if sum(item.reserved_quantity for item in self.lot_allocations) != self.reserved_quantity:
                raise ValueError("lot allocations do not equal reserved quantity")
            if self.consumed_quantity > self.reserved_quantity:
                raise ValueError("position consumption exceeds reservation")
        lineage = (
            self.experiment_id,
            self.assignment_id,
            self.challenger_version_id,
            self.baseline_champion_id,
            self.config_hash,
        )
        if self.run_mode == "PAPER_CHALLENGER" and (
            not self.snapshot_id or not all(lineage)
        ):
            raise ValueError("Challenger reservation requires complete lineage")
        if self.run_mode is None and any(value is not None for value in lineage):
            raise ValueError("experiment lineage requires PAPER_CHALLENGER run mode")
        return self


class ExecutionMarketSnapshot(PaperSchema):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        allow_inf_nan=False,
        str_strip_whitespace=True,
        json_encoders={Decimal: str},
    )

    execution_snapshot_id: str = Field(min_length=1)
    symbol: str = Field(pattern=r"^\d{6}$")
    market: Literal["CN"] = "CN"
    trade_date: date
    open: Decimal = Field(gt=0)
    high: Decimal = Field(gt=0)
    low: Decimal = Field(gt=0)
    close: Decimal = Field(gt=0)
    prev_close: Decimal | None = Field(default=None, gt=0)
    volume: int = Field(ge=0)
    amount: Decimal | None = Field(default=None, ge=0)
    suspended: bool
    st_status: bool
    limit_up_price: Decimal = Field(gt=0)
    limit_down_price: Decimal = Field(gt=0)
    source_refs: list[str] = Field(min_length=1)
    data_version: str = Field(min_length=1)
    cutoff_at: datetime
    simulation_granularity: Literal["DAILY_OHLCV"] = "DAILY_OHLCV"
    matched_after_market_close: Literal[True] = True
    immutable_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime
    schema_version: str = PAPER_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_snapshot(self) -> "ExecutionMarketSnapshot":
        if self.low > self.high:
            raise ValueError("execution snapshot low exceeds high")
        if not self.low <= self.open <= self.high:
            raise ValueError("open is outside daily range")
        if not self.low <= self.close <= self.high:
            raise ValueError("close is outside daily range")
        if self.limit_down_price > self.limit_up_price:
            raise ValueError("limit price bounds are inverted")
        expected_hash = paper_canonical_hash(
            self,
            exclude={"execution_snapshot_id", "immutable_hash", "created_at"},
        )
        if expected_hash != self.immutable_hash:
            raise ValueError("ExecutionMarketSnapshot immutable_hash mismatch")
        return self


class FeeBreakdown(PaperSchema):
    commission: Decimal = Field(ge=0)
    stamp_duty: Decimal = Field(ge=0)
    transfer_fee: Decimal = Field(ge=0)
    regulatory_fee: Decimal = Field(ge=0)
    other_fees: Decimal = Field(ge=0)
    total_fee: Decimal = Field(ge=0)
    fee_policy_version: str = Field(min_length=1)
    calculation_scope: Literal["ORDER_TRADE_DATE"] = "ORDER_TRADE_DATE"

    @model_validator(mode="after")
    def validate_total(self) -> "FeeBreakdown":
        expected = (
            self.commission
            + self.stamp_duty
            + self.transfer_fee
            + self.regulatory_fee
            + self.other_fees
        )
        if self.total_fee != expected:
            raise ValueError("fee total does not equal fee components")
        return self


class MatchResult(PaperSchema):
    status: Literal["NO_FILL", "PARTIAL_FILL", "FULL_FILL", "BLOCKED"]
    quantity: int = Field(default=0, ge=0)
    price: Decimal | None = Field(default=None, gt=0)
    reason: str = Field(min_length=1)
    pricing_reference: Decimal | None = Field(default=None, gt=0)
    capacity_quantity: int = Field(default=0, ge=0)
    matching_engine_version: str = MATCHING_ENGINE_VERSION

    @model_validator(mode="after")
    def validate_match(self) -> "MatchResult":
        has_fill = self.status in {"PARTIAL_FILL", "FULL_FILL"}
        if has_fill != (self.quantity > 0 and self.price is not None):
            raise ValueError("match result price and quantity do not match status")
        return self


class PaperFill(PaperSchema):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        allow_inf_nan=False,
        str_strip_whitespace=True,
        json_encoders={Decimal: str},
    )

    fill_id: str = Field(min_length=1)
    order_id: str = Field(min_length=1)
    intent_id: str = Field(min_length=1)
    account_id: str = Field(min_length=1)
    snapshot_id: str | None = None
    experiment_id: str | None = None
    assignment_id: str | None = None
    challenger_version_id: str | None = None
    baseline_champion_id: str | None = None
    config_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    run_mode: Literal["PAPER_CHALLENGER"] | None = None
    execution_snapshot_id: str = Field(min_length=1)
    trade_date: date
    execution_time_policy: str = Field(min_length=1)
    symbol: str = Field(pattern=r"^\d{6}$")
    market: Literal["CN"] = "CN"
    side: OrderSide
    quantity: int = Field(gt=0)
    price: Decimal = Field(gt=0)
    notional: Decimal = Field(gt=0)
    fee_breakdown: FeeBreakdown
    net_cash_effect: Decimal
    matching_engine_version: str = Field(min_length=1)
    fee_policy_version: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    immutable_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime
    schema_version: str = PAPER_SCHEMA_VERSION
    execution_environment: Literal["PAPER"] = "PAPER"
    live_execution_allowed: Literal[False] = False

    @model_validator(mode="after")
    def validate_fill(self) -> "PaperFill":
        if self.notional != self.price * self.quantity:
            raise ValueError("fill notional does not equal price times quantity")
        expected_effect = (
            -(self.notional + self.fee_breakdown.total_fee)
            if self.side == "BUY"
            else self.notional - self.fee_breakdown.total_fee
        )
        if self.net_cash_effect != expected_effect:
            raise ValueError("fill net cash effect mismatch")
        hash_excludes = {"fill_id", "immutable_hash", "created_at"}
        lineage = (
            self.experiment_id,
            self.assignment_id,
            self.challenger_version_id,
            self.baseline_champion_id,
            self.config_hash,
        )
        if self.run_mode == "PAPER_CHALLENGER":
            if not self.snapshot_id or not all(lineage):
                raise ValueError("Challenger fill requires complete experiment lineage")
        elif any(value is not None for value in lineage):
            raise ValueError("experiment lineage is reserved for Challenger fills")
        if self.run_mode is None:
            hash_excludes.update(
                {
                    "snapshot_id",
                    "experiment_id",
                    "assignment_id",
                    "challenger_version_id",
                    "baseline_champion_id",
                    "config_hash",
                    "run_mode",
                }
            )
        expected_hash = paper_canonical_hash(
            self,
            exclude=hash_excludes,
        )
        if expected_hash != self.immutable_hash:
            raise ValueError("PaperFill immutable_hash mismatch")
        return self


class PositionLot(PaperSchema):
    lot_id: str = Field(min_length=1)
    account_id: str = Field(min_length=1)
    symbol: str = Field(pattern=r"^\d{6}$")
    market: Literal["CN"] = "CN"
    source_fill_id: str = Field(min_length=1)
    snapshot_id: str | None = None
    experiment_id: str | None = None
    assignment_id: str | None = None
    challenger_version_id: str | None = None
    baseline_champion_id: str | None = None
    config_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    run_mode: Literal["PAPER_CHALLENGER"] | None = None
    acquired_trade_date: date
    original_quantity: int = Field(gt=0)
    remaining_quantity: int = Field(ge=0)
    reserved_quantity: int = Field(default=0, ge=0)
    unit_cost: Decimal = Field(gt=0)
    total_cost: Decimal = Field(ge=0)
    available_from_date: date
    status: Literal["OPEN", "PARTIALLY_CLOSED", "CLOSED"] = "OPEN"
    reservation_allocations: dict[str, int] = Field(default_factory=dict)
    applied_settlement_ids: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    lot_version: int = Field(default=1, ge=1)
    schema_version: str = PAPER_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_lot(self) -> "PositionLot":
        if self.remaining_quantity > self.original_quantity:
            raise ValueError("lot remaining quantity exceeds original")
        if self.reserved_quantity > self.remaining_quantity:
            raise ValueError("lot reserved quantity exceeds remaining")
        if sum(self.reservation_allocations.values()) != self.reserved_quantity:
            raise ValueError("lot reservation allocations do not match reserved quantity")
        if self.status == "CLOSED" and self.remaining_quantity != 0:
            raise ValueError("closed lot must have zero remaining")
        lineage = (
            self.experiment_id,
            self.assignment_id,
            self.challenger_version_id,
            self.baseline_champion_id,
            self.config_hash,
        )
        if self.run_mode == "PAPER_CHALLENGER" and (
            not self.snapshot_id or not all(lineage)
        ):
            raise ValueError("Challenger position lot requires complete lineage")
        if self.run_mode is None and any(value is not None for value in lineage):
            raise ValueError("experiment lineage requires PAPER_CHALLENGER run mode")
        return self


class PaperPosition(PaperSchema):
    position_id: str = Field(min_length=1)
    account_id: str = Field(min_length=1)
    snapshot_id: str | None = None
    snapshot_ids: list[str] = Field(default_factory=list)
    experiment_id: str | None = None
    assignment_id: str | None = None
    challenger_version_id: str | None = None
    baseline_champion_id: str | None = None
    config_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    run_mode: Literal["PAPER_CHALLENGER"] | None = None
    symbol: str = Field(pattern=r"^\d{6}$")
    market: Literal["CN"] = "CN"
    currency: Literal["CNY"] = "CNY"
    quantity: int = Field(ge=0)
    available_quantity: int = Field(ge=0)
    reserved_quantity: int = Field(ge=0)
    average_cost: Decimal = Field(ge=0)
    total_cost: Decimal = Field(ge=0)
    realized_pnl: Decimal = Decimal("0")
    total_fees: Decimal = Field(default=Decimal("0"), ge=0)
    applied_settlement_ids: list[str] = Field(default_factory=list)
    updated_at: datetime
    schema_version: str = PAPER_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_position(self) -> "PaperPosition":
        if self.available_quantity + self.reserved_quantity > self.quantity:
            raise ValueError("position availability and reservation exceed quantity")
        if self.quantity == 0 and self.total_cost != 0:
            raise ValueError("zero position cannot retain cost")
        lineage = (
            self.experiment_id,
            self.assignment_id,
            self.challenger_version_id,
            self.baseline_champion_id,
            self.config_hash,
        )
        if self.run_mode == "PAPER_CHALLENGER":
            if not self.snapshot_id or not all(lineage) or not self.snapshot_ids:
                raise ValueError("Challenger position requires complete lineage")
            if self.snapshot_id not in self.snapshot_ids:
                raise ValueError("position snapshot_id must be in snapshot_ids")
        elif any(value is not None for value in lineage):
            raise ValueError("experiment lineage requires PAPER_CHALLENGER run mode")
        return self


class LedgerEntry(PaperSchema):
    ledger_entry_id: str = Field(min_length=1)
    settlement_id: str = Field(min_length=1)
    fill_id: str = Field(min_length=1)
    account_id: str = Field(min_length=1)
    snapshot_id: str | None = None
    experiment_id: str | None = None
    assignment_id: str | None = None
    challenger_version_id: str | None = None
    baseline_champion_id: str | None = None
    config_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    run_mode: Literal["PAPER_CHALLENGER"] | None = None
    entry_type: Literal[
        "CASH_CHANGE",
        "POSITION_COST_CHANGE",
        "FEE_EXPENSE",
        "REALIZED_PNL",
        "RESERVATION_RELEASE",
    ]
    amount: Decimal
    currency: Literal["CNY"] = "CNY"
    balance_before: Decimal | None = None
    balance_after: Decimal | None = None
    idempotency_key: str = Field(min_length=1)
    created_at: datetime
    schema_version: str = PAPER_SCHEMA_VERSION


class SettlementRecord(PaperSchema):
    settlement_id: str = Field(min_length=1)
    fill_id: str = Field(min_length=1)
    order_id: str = Field(min_length=1)
    account_id: str = Field(min_length=1)
    snapshot_id: str | None = None
    experiment_id: str | None = None
    assignment_id: str | None = None
    challenger_version_id: str | None = None
    baseline_champion_id: str | None = None
    config_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    run_mode: Literal["PAPER_CHALLENGER"] | None = None
    status: Literal[
        "PREPARED",
        "ACCOUNT_APPLIED",
        "POSITION_APPLIED",
        "LEDGER_APPLIED",
        "COMMITTED",
        "FAILED",
        "COMPENSATION_REQUIRED",
    ]
    saga_version: str = SETTLEMENT_SAGA_VERSION
    realized_pnl: Decimal = Decimal("0")
    position_cost: Decimal = Field(default=Decimal("0"), ge=0)
    cash_effect: Decimal = Decimal("0")
    lot_consumptions: list[dict[str, Any]] = Field(default_factory=list)
    acquired_available_from_date: date | None = None
    account_applied: bool = False
    position_applied: bool = False
    ledger_applied: bool = False
    attempt_count: int = Field(default=1, ge=1)
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime
    committed_at: datetime | None = None
    schema_version: str = PAPER_SCHEMA_VERSION


class DailyAccountSnapshot(PaperSchema):
    account_snapshot_id: str = Field(min_length=1)
    account_id: str = Field(min_length=1)
    trade_date: date
    cash_available: Decimal = Field(ge=0)
    cash_reserved: Decimal = Field(ge=0)
    position_market_value: Decimal = Field(ge=0)
    total_equity: Decimal = Field(ge=0)
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    total_fees: Decimal = Field(ge=0)
    gross_exposure_pct: float = Field(ge=0)
    position_count: int = Field(ge=0)
    price_refs: list[str]
    valuation_complete: bool
    missing_price_symbols: list[str]
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime
    schema_version: str = PAPER_SCHEMA_VERSION


class PaperJobRun(PaperSchema):
    job_id: str = Field(min_length=1)
    job_type: str = Field(min_length=1)
    trade_date: date | None = None
    idempotency_key: str = Field(min_length=1)
    status: Literal["PENDING", "RUNNING", "COMPLETED", "FAILED"]
    attempt_count: int = Field(default=1, ge=1)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None
    created_at: datetime
    schema_version: str = PAPER_SCHEMA_VERSION


class PaperEvent(PaperSchema):
    event_id: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    user_id: str | None = None
    account_id: str | None = None
    account_type: str | None = None
    intent_id: str | None = None
    order_id: str | None = None
    fill_id: str | None = None
    settlement_id: str | None = None
    symbol: str | None = None
    trade_date: date | None = None
    source_type: str | None = None
    source_object_id: str | None = None
    snapshot_id: str | None = None
    risk_decision_id: str | None = None
    experiment_id: str | None = None
    assignment_id: str | None = None
    trace_id: str | None = None
    reason: str = Field(min_length=1)
    created_at: datetime
    schema_version: str = PAPER_SCHEMA_VERSION


class AccountPolicy(PaperSchema):
    account_policy_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    market: Literal["CN"]
    currency: Literal["CNY"]
    initial_cash: Decimal = Field(gt=0)
    account_types: list[AccountType]
    config_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class ExecutionPolicy(PaperSchema):
    execution_policy_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    matching_engine_version: str = Field(min_length=1)
    default_buy_order_type: Literal["LIMIT"]
    default_exit_order_type: Literal["MARKET_ON_OPEN"]
    buy_slippage_bps: Decimal = Field(ge=0)
    sell_slippage_bps: Decimal = Field(ge=0)
    max_participation_rate: Decimal = Field(gt=0, le=1)
    daily_fill_per_order_limit: Literal[1] = 1
    simulation_granularity: Literal["DAILY_OHLCV"]
    price_tick: Decimal = Field(gt=0)
    cn_buy_lot_size: int = Field(gt=0)
    st_buy_enabled: bool
    validity_sessions: int = Field(default=5, ge=1)
    config_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class FeePolicy(PaperSchema):
    fee_policy_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    market: Literal["CN"]
    currency: Literal["CNY"]
    commission_rate: Decimal = Field(ge=0)
    minimum_commission: Decimal = Field(ge=0)
    sell_stamp_duty_rate: Decimal = Field(ge=0)
    transfer_fee_rate: Decimal = Field(ge=0)
    regulatory_fee_rate: Decimal = Field(default=Decimal("0"), ge=0)
    other_fee_rate: Decimal = Field(default=Decimal("0"), ge=0)
    calculation_scope: Literal["ORDER_TRADE_DATE"]
    money_quantum: Decimal = Field(gt=0)
    config_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
