"""Append-only PR-005 decision event persistence."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from app.schemas.alphaguard.decision import DecisionContext, DecisionEvent


class DecisionAuditService:
    def __init__(self, db):
        self.db = db

    async def record(
        self,
        event_type: str,
        *,
        context: DecisionContext,
        reason: str,
        plan_id: str | None = None,
        review_id: str | None = None,
        consensus_id: str | None = None,
        risk_decision_id: str | None = None,
        revision_round: int = 0,
        attempt_number: int = 1,
        trace_id: str | None = None,
    ) -> DecisionEvent:
        event = DecisionEvent(
            event_id=str(uuid4()),
            event_type=event_type,
            analysis_id=context.analysis_id,
            user_id=context.user_id,
            candidate_id=context.candidate_id,
            snapshot_id=context.snapshot_id,
            quant_proposal_id=context.quant_proposal_id,
            plan_id=plan_id,
            review_id=review_id,
            consensus_id=consensus_id,
            risk_decision_id=risk_decision_id,
            revision_round=revision_round,
            attempt_number=attempt_number,
            trace_id=trace_id,
            reason=reason[:500],
            created_at=datetime.utcnow(),
        )
        await self.db["ag_decision_events"].insert_one(
            event.model_dump(mode="python")
        )
        return event

    async def record_identity(
        self,
        event_type: str,
        *,
        analysis_id: str,
        user_id: str,
        snapshot_id: str,
        quant_proposal_id: str,
        reason: str,
        candidate_id: str | None = None,
        attempt_number: int = 1,
        trace_id: str | None = None,
    ) -> DecisionEvent:
        event = DecisionEvent(
            event_id=str(uuid4()),
            event_type=event_type,
            analysis_id=analysis_id,
            user_id=user_id,
            candidate_id=candidate_id,
            snapshot_id=snapshot_id,
            quant_proposal_id=quant_proposal_id,
            attempt_number=attempt_number,
            trace_id=trace_id,
            reason=reason[:500],
            created_at=datetime.utcnow(),
        )
        await self.db["ag_decision_events"].insert_one(
            event.model_dump(mode="python")
        )
        return event
