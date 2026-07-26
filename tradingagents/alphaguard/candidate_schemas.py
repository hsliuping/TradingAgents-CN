"""Candidate pool contracts and state transitions for AlphaGuard PR-003."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .instruments import Market, normalize_instrument


CANDIDATE_SCHEMA_VERSION = "candidate-entry-v1"
CANDIDATE_EVENT_SCHEMA_VERSION = "candidate-event-v1"


class CandidateSource(str, Enum):
    USER_SELECTED = "USER_SELECTED"
    POSITION_REQUIRED = "POSITION_REQUIRED"
    SYSTEM_SCREENED = "SYSTEM_SCREENED"
    EVENT_TRIGGERED = "EVENT_TRIGGERED"
    EXPERIMENT_ASSIGNED = "EXPERIMENT_ASSIGNED"


class CandidateStatus(str, Enum):
    WATCHING = "WATCHING"
    SIGNAL_DETECTED = "SIGNAL_DETECTED"
    AI_ANALYZING = "AI_ANALYZING"
    PLAN_PROPOSED = "PLAN_PROPOSED"
    TOP_REVIEWING = "TOP_REVIEWING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ORDER_PENDING = "ORDER_PENDING"
    POSITION_HELD = "POSITION_HELD"
    EXIT_REVIEW = "EXIT_REVIEW"
    RISK_ALERT = "RISK_ALERT"
    COOLDOWN = "COOLDOWN"
    REMOVED = "REMOVED"


class CandidateEventType(str, Enum):
    CREATED = "CREATED"
    SOURCE_ADDED = "SOURCE_ADDED"
    SOURCE_REMOVED = "SOURCE_REMOVED"
    STATUS_CHANGED = "STATUS_CHANGED"
    REMOVAL_REQUESTED = "REMOVAL_REQUESTED"
    REMOVAL_BLOCKED = "REMOVAL_BLOCKED"
    MARKED_REMOVED = "MARKED_REMOVED"
    REACTIVATED = "REACTIVATED"
    RECONCILED = "RECONCILED"
    SYNC_FAILED = "SYNC_FAILED"


class CandidateSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CandidateEntry(CandidateSchema):
    candidate_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    market: Market
    name: str | None = None
    sources: set[CandidateSource] = Field(default_factory=set)
    status: CandidateStatus
    priority: int = Field(default=50, ge=0, le=100)
    added_at: datetime
    updated_at: datetime
    next_scan_at: datetime | None = None
    cooldown_until: datetime | None = None
    active_plan_id: str | None = None
    active_order_ids: list[str] = Field(default_factory=list)
    held_account_ids: list[str] = Field(default_factory=list)
    removal_requested: bool = False
    schema_version: str = CANDIDATE_SCHEMA_VERSION

    @model_validator(mode="before")
    @classmethod
    def normalize_identity(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        data = dict(value)
        if data.get("symbol") and data.get("market"):
            market, symbol = normalize_instrument(data["symbol"], data["market"])
            data["market"] = market
            data["symbol"] = symbol
        return data

    @field_validator("active_order_ids", "held_account_ids")
    @classmethod
    def unique_ids(cls, values: list[str]) -> list[str]:
        return sorted({value for value in values if value})

    @model_validator(mode="after")
    def validate_lifecycle(self) -> "CandidateEntry":
        if self.updated_at < self.added_at:
            raise ValueError("updated_at must not precede added_at")
        if self.status == CandidateStatus.REMOVED and (
            self.sources
            or self.active_plan_id
            or self.active_order_ids
            or self.held_account_ids
        ):
            raise ValueError("REMOVED candidate cannot retain monitoring dependencies")
        return self


class CandidateEvent(CandidateSchema):
    event_id: str = Field(min_length=1)
    candidate_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    event_type: CandidateEventType
    previous_status: CandidateStatus | None = None
    new_status: CandidateStatus | None = None
    source_added: CandidateSource | None = None
    source_removed: CandidateSource | None = None
    reason: str = Field(min_length=1)
    trace_id: str | None = None
    created_at: datetime
    schema_version: str = CANDIDATE_EVENT_SCHEMA_VERSION


ALLOWED_CANDIDATE_TRANSITIONS: dict[CandidateStatus, set[CandidateStatus]] = {
    CandidateStatus.WATCHING: {
        CandidateStatus.SIGNAL_DETECTED,
        CandidateStatus.POSITION_HELD,
        CandidateStatus.REMOVED,
    },
    CandidateStatus.SIGNAL_DETECTED: {
        CandidateStatus.AI_ANALYZING,
        CandidateStatus.POSITION_HELD,
        CandidateStatus.REMOVED,
    },
    CandidateStatus.AI_ANALYZING: {
        CandidateStatus.PLAN_PROPOSED,
        CandidateStatus.REJECTED,
        CandidateStatus.COOLDOWN,
        CandidateStatus.POSITION_HELD,
    },
    CandidateStatus.PLAN_PROPOSED: {
        CandidateStatus.TOP_REVIEWING,
        CandidateStatus.POSITION_HELD,
    },
    CandidateStatus.TOP_REVIEWING: {
        CandidateStatus.APPROVED,
        CandidateStatus.REJECTED,
        CandidateStatus.COOLDOWN,
        CandidateStatus.RISK_ALERT,
        CandidateStatus.POSITION_HELD,
    },
    CandidateStatus.APPROVED: {
        CandidateStatus.ORDER_PENDING,
        CandidateStatus.WATCHING,
        CandidateStatus.COOLDOWN,
        CandidateStatus.POSITION_HELD,
    },
    CandidateStatus.REJECTED: {
        CandidateStatus.WATCHING,
        CandidateStatus.COOLDOWN,
        CandidateStatus.REMOVED,
        CandidateStatus.POSITION_HELD,
    },
    CandidateStatus.ORDER_PENDING: {
        CandidateStatus.POSITION_HELD,
        CandidateStatus.APPROVED,
        CandidateStatus.REJECTED,
        CandidateStatus.WATCHING,
        CandidateStatus.COOLDOWN,
    },
    CandidateStatus.POSITION_HELD: {
        CandidateStatus.EXIT_REVIEW,
        CandidateStatus.RISK_ALERT,
        CandidateStatus.WATCHING,
        CandidateStatus.REMOVED,
    },
    CandidateStatus.EXIT_REVIEW: {
        CandidateStatus.POSITION_HELD,
        CandidateStatus.ORDER_PENDING,
        CandidateStatus.WATCHING,
    },
    CandidateStatus.RISK_ALERT: {
        CandidateStatus.EXIT_REVIEW,
        CandidateStatus.COOLDOWN,
        CandidateStatus.WATCHING,
        CandidateStatus.POSITION_HELD,
    },
    CandidateStatus.COOLDOWN: {
        CandidateStatus.WATCHING,
        CandidateStatus.SIGNAL_DETECTED,
        CandidateStatus.POSITION_HELD,
        CandidateStatus.REMOVED,
    },
    CandidateStatus.REMOVED: {CandidateStatus.WATCHING},
}


def validate_candidate_transition(
    previous: CandidateStatus,
    target: CandidateStatus,
    *,
    source_readded: bool = False,
) -> None:
    """Validate every candidate status mutation through one policy."""

    if previous == target:
        return
    if target not in ALLOWED_CANDIDATE_TRANSITIONS.get(previous, set()):
        raise ValueError(f"candidate status transition {previous} -> {target} is not allowed")
    if (
        previous == CandidateStatus.REMOVED
        and target == CandidateStatus.WATCHING
        and not source_readded
    ):
        raise ValueError("REMOVED -> WATCHING requires a source to be re-added")
