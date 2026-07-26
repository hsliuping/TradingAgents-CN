"""PR-005 immutable context, consensus, and hard-risk contracts."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.alphaguard.quant import MarketRegimeResult, QuantTradeProposal
from tradingagents.alphaguard.decision_schemas import (
    EvidenceRef,
    NormalTradePlan,
    RiskItem,
    TopReviewDecision,
)


DECISION_CONTEXT_SCHEMA_VERSION = "decision-context-v1"
REVISION_REQUEST_SCHEMA_VERSION = "revision-request-v1"
CONSENSUS_SCHEMA_VERSION = "consensus-decision-v1"
RISK_POLICY_SCHEMA_VERSION = "risk-policy-v1"
RISK_RULE_SCHEMA_VERSION = "risk-rule-result-v1"
RISK_DECISION_SCHEMA_VERSION = "risk-decision-v1"
DECISION_EVENT_SCHEMA_VERSION = "decision-event-v1"
DECISION_PIPELINE_VERSION = "decision-pipeline-v1"
CONSENSUS_POLICY_VERSION = "consensus-policy-v1"


class DecisionControlSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        allow_inf_nan=False,
        str_strip_whitespace=True,
    )


def canonical_value(value: Any, *, exclude: set[str] | None = None) -> Any:
    exclude = exclude or set()
    if isinstance(value, BaseModel):
        return canonical_value(value.model_dump(mode="python"), exclude=exclude)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {
            str(key): canonical_value(item, exclude=exclude)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            if key not in exclude and key != "_id"
        }
    if isinstance(value, (list, tuple)):
        return [canonical_value(item, exclude=exclude) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted(canonical_value(item, exclude=exclude) for item in value)
    return value


def canonical_hash(value: Any, *, exclude: set[str] | None = None) -> str:
    payload = json.dumps(
        canonical_value(value, exclude=exclude),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class DecisionContext(DecisionControlSchema):
    model_config = ConfigDict(
        extra="forbid",
        allow_inf_nan=False,
        str_strip_whitespace=True,
        frozen=True,
    )

    decision_context_id: str = Field(min_length=1)
    analysis_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    candidate_id: str | None
    symbol: str = Field(min_length=1)
    market: str = Field(min_length=1)
    trade_date: date
    snapshot_id: str = Field(min_length=1)
    quant_proposal_id: str = Field(min_length=1)
    strategy_id: str = Field(min_length=1)
    strategy_version: str = Field(min_length=1)
    factor_set_version: str = Field(min_length=1)
    regime_result_id: str = Field(min_length=1)
    quant_proposal: QuantTradeProposal
    factor_summary: dict[str, float | None]
    factor_result_ids: list[str]
    market_regime: MarketRegimeResult
    price_evidence: list[EvidenceRef]
    financial_evidence: list[EvidenceRef]
    news_evidence: list[EvidenceRef]
    announcement_evidence: list[EvidenceRef]
    account_evidence: list[EvidenceRef]
    portfolio_evidence: list[EvidenceRef]
    data_quality_status: str
    risk_flags: list[str]
    missing_evidence: list[str]
    normal_prompt_version: str = Field(min_length=1)
    top_prompt_version: str = Field(min_length=1)
    context_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime
    schema_version: str = DECISION_CONTEXT_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_chain(self) -> "DecisionContext":
        proposal = self.quant_proposal
        regime = self.market_regime
        expected = (
            self.user_id,
            self.symbol,
            self.market,
            self.trade_date,
            self.snapshot_id,
            self.quant_proposal_id,
            self.strategy_id,
            self.strategy_version,
            self.factor_set_version,
            self.regime_result_id,
        )
        actual = (
            proposal.user_id,
            proposal.symbol,
            proposal.market,
            proposal.trade_date,
            proposal.snapshot_id,
            proposal.proposal_id,
            proposal.strategy_id,
            proposal.strategy_version,
            proposal.factor_set_version,
            proposal.regime_result_id,
        )
        if actual != expected:
            raise ValueError("DecisionContext and QuantTradeProposal identity mismatch")
        if regime.snapshot_id != self.snapshot_id:
            raise ValueError("DecisionContext and MarketRegimeResult snapshot mismatch")
        if regime.regime_result_id != self.regime_result_id:
            raise ValueError("DecisionContext and MarketRegimeResult identity mismatch")
        if sorted(self.factor_result_ids) != sorted(proposal.factor_result_ids):
            raise ValueError("DecisionContext factor_result_ids mismatch")
        expected_hash = canonical_hash(
            self,
            exclude={"decision_context_id", "context_hash", "created_at"},
        )
        if expected_hash != self.context_hash:
            raise ValueError(
                "DecisionContext context_hash mismatch "
                f"(expected={expected_hash}, actual={self.context_hash})"
            )
        return self

    def evidence_ids(self) -> set[str]:
        groups = (
            self.price_evidence,
            self.financial_evidence,
            self.news_evidence,
            self.announcement_evidence,
            self.account_evidence,
            self.portfolio_evidence,
        )
        direct = {item.evidence_id for group in groups for item in group}
        derived = set(self.factor_result_ids)
        derived.update(
            item.evidence_id for item in self.quant_proposal.evidence_refs
        )
        return direct | derived


class RevisionRequest(DecisionControlSchema):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    revision_request_id: str = Field(min_length=1)
    analysis_id: str = Field(min_length=1)
    snapshot_id: str = Field(min_length=1)
    original_plan_id: str = Field(min_length=1)
    review_id: str = Field(min_length=1)
    revision_round: Literal[1] = 1
    requested_changes: list[str] = Field(min_length=1)
    material_change_fields: list[str] = Field(min_length=1)
    risk_findings: list[RiskItem]
    constraints: list[str] = Field(min_length=1)
    created_at: datetime
    schema_version: str = REVISION_REQUEST_SCHEMA_VERSION


class ConsensusDecision(DecisionControlSchema):
    consensus_id: str = Field(min_length=1)
    analysis_id: str = Field(min_length=1)
    snapshot_id: str = Field(min_length=1)
    quant_proposal_id: str = Field(min_length=1)
    plan_id: str = Field(min_length=1)
    review_id: str = Field(min_length=1)
    status: Literal[
        "CONSENSUS_PASS",
        "CONSENSUS_REVISE",
        "CONSENSUS_REJECT",
        "CONSENSUS_INVALID",
    ]
    final_plan: NormalTradePlan | None
    final_plan_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    revision_round: int = Field(ge=0, le=1)
    requires_normal_reconfirm: bool
    reasons: list[str]
    validation_errors: list[str]
    consensus_policy_version: str = CONSENSUS_POLICY_VERSION
    created_at: datetime
    schema_version: str = CONSENSUS_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_result(self) -> "ConsensusDecision":
        if self.status == "CONSENSUS_PASS":
            if self.final_plan is None or self.final_plan_hash is None:
                raise ValueError("CONSENSUS_PASS requires final plan and hash")
            if canonical_hash(self.final_plan) != self.final_plan_hash:
                raise ValueError("Consensus final_plan_hash mismatch")
        elif self.final_plan is not None or self.final_plan_hash is not None:
            raise ValueError("non-pass consensus cannot expose a final plan")
        if self.requires_normal_reconfirm != (self.status == "CONSENSUS_REVISE"):
            raise ValueError("requires_normal_reconfirm only applies to revise")
        return self


class RiskPolicy(DecisionControlSchema):
    risk_policy_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    status: Literal["ACTIVE", "INACTIVE", "RETIRED"] = "ACTIVE"
    max_single_position_pct: float = Field(ge=0, le=1)
    max_total_exposure_pct: float = Field(ge=0, le=1)
    max_industry_exposure_pct: float = Field(ge=0, le=1)
    max_new_positions_per_day: int = Field(ge=0)
    min_cash_reserve_pct: float = Field(ge=0, le=1)
    max_order_participation_rate: float = Field(gt=0, le=1)
    minimum_average_amount_20d: float | None = Field(default=None, ge=0)
    maximum_volatility_risk_score: float | None = Field(default=None, ge=0, le=100)
    maximum_event_risk_score: float | None = Field(default=None, ge=0, le=100)
    st_buy_enabled: bool
    allow_buy_when_suspended: bool
    allow_sell_when_suspended: bool
    cn_buy_lot_size: int = Field(gt=0)
    allow_cn_sell_odd_lot: bool
    decision_validity_required: bool
    snapshot_integrity_required: bool
    data_quality_fail_blocked: bool
    live_trading_enabled: Literal[False] = False
    blocked_symbols: list[str] = Field(default_factory=list)
    config_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime
    schema_version: str = RISK_POLICY_SCHEMA_VERSION


class RiskRuleResult(DecisionControlSchema):
    rule_id: str = Field(min_length=1)
    rule_version: str = Field(min_length=1)
    status: Literal[
        "PASS",
        "WARN",
        "REDUCE",
        "REJECT",
        "SUSPEND",
        "NOT_APPLICABLE",
    ]
    observed_value: Any | None
    threshold_value: Any | None
    original_position_pct: float | None = Field(default=None, ge=0, le=1)
    adjusted_position_pct: float | None = Field(default=None, ge=0, le=1)
    original_quantity: int | None = Field(default=None, ge=0)
    adjusted_quantity: int | None = Field(default=None, ge=0)
    evidence_refs: list[EvidenceRef]
    reason: str = Field(min_length=1)
    evaluated_at: datetime

    @model_validator(mode="after")
    def cannot_raise_risk(self) -> "RiskRuleResult":
        if (
            self.original_position_pct is not None
            and self.adjusted_position_pct is not None
            and self.adjusted_position_pct > self.original_position_pct
        ):
            raise ValueError("risk rule cannot increase position")
        if (
            self.original_quantity is not None
            and self.adjusted_quantity is not None
            and self.adjusted_quantity > self.original_quantity
        ):
            raise ValueError("risk rule cannot increase quantity")
        return self


class RiskDecision(DecisionControlSchema):
    risk_decision_id: str = Field(min_length=1)
    analysis_id: str = Field(min_length=1)
    consensus_id: str = Field(min_length=1)
    snapshot_id: str = Field(min_length=1)
    quant_proposal_id: str = Field(min_length=1)
    account_id: str | None
    status: Literal["PASS", "REDUCE", "REJECT", "SUSPEND"]
    action: Literal["BUY", "SELL", "REDUCE"]
    original_position_pct: float | None = Field(default=None, ge=0, le=1)
    approved_position_pct: float | None = Field(default=None, ge=0, le=1)
    original_quantity: int | None = Field(default=None, ge=0)
    approved_quantity: int | None = Field(default=None, ge=0)
    pricing_reference: float | None = Field(default=None, gt=0)
    earliest_eligible_execute_at: datetime | None
    requires_execution_recheck: bool
    triggered_rules: list[RiskRuleResult]
    reasons: list[str]
    risk_policy_version: str = Field(min_length=1)
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime
    schema_version: str = RISK_DECISION_SCHEMA_VERSION
    order_intent_created: Literal[False] = False

    @model_validator(mode="after")
    def validate_risk_result(self) -> "RiskDecision":
        if (
            self.original_position_pct is not None
            and self.approved_position_pct is not None
            and self.approved_position_pct > self.original_position_pct
        ):
            raise ValueError("HardRisk cannot increase position")
        if (
            self.original_quantity is not None
            and self.approved_quantity is not None
            and self.approved_quantity > self.original_quantity
            and self.action in {"SELL", "REDUCE"}
        ):
            raise ValueError("HardRisk cannot approve selling more than held")
        return self


class DecisionEvent(DecisionControlSchema):
    event_id: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    analysis_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    candidate_id: str | None = None
    snapshot_id: str = Field(min_length=1)
    quant_proposal_id: str = Field(min_length=1)
    plan_id: str | None = None
    review_id: str | None = None
    consensus_id: str | None = None
    risk_decision_id: str | None = None
    revision_round: int = Field(default=0, ge=0, le=1)
    attempt_number: int = Field(default=1, ge=1)
    trace_id: str | None = None
    reason: str = Field(min_length=1)
    created_at: datetime
    schema_version: str = DECISION_EVENT_SCHEMA_VERSION


class DecisionPipelineResult(DecisionControlSchema):
    analysis_id: str
    decision_run_key: str = Field(pattern=r"^[0-9a-f]{64}$")
    attempt_number: int = Field(ge=1)
    terminal_status: str
    decision_context: DecisionContext | None = None
    normal_trade_plan: NormalTradePlan | None = None
    top_review_decision: TopReviewDecision | None = None
    revision_request: RevisionRequest | None = None
    consensus_decision: ConsensusDecision | None = None
    risk_decision: RiskDecision | None = None
    reused: bool = False
    order_intent_created: Literal[False] = False
