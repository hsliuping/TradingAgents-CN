"""Append-only audit events for the automatic paper-trading chain."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import uuid4

from app.services.alphaguard.paper_storage import model_document
from tradingagents.alphaguard.paper_schemas import PaperEvent


class PaperAuditService:
    def __init__(self, db):
        self.collection = db["ag_paper_events"]

    async def record(
        self,
        event_type: str,
        reason: str,
        *,
        user_id: str | None = None,
        account_id: str | None = None,
        account_type: str | None = None,
        intent_id: str | None = None,
        order_id: str | None = None,
        fill_id: str | None = None,
        settlement_id: str | None = None,
        symbol: str | None = None,
        trade_date: date | None = None,
        source_type: str | None = None,
        source_object_id: str | None = None,
        snapshot_id: str | None = None,
        risk_decision_id: str | None = None,
        trace_id: str | None = None,
        now: datetime | None = None,
    ) -> PaperEvent:
        event = PaperEvent(
            event_id=str(uuid4()),
            event_type=event_type,
            user_id=user_id,
            account_id=account_id,
            account_type=account_type,
            intent_id=intent_id,
            order_id=order_id,
            fill_id=fill_id,
            settlement_id=settlement_id,
            symbol=symbol,
            trade_date=trade_date,
            source_type=source_type,
            source_object_id=source_object_id,
            snapshot_id=snapshot_id,
            risk_decision_id=risk_decision_id,
            trace_id=trace_id,
            reason=reason,
            created_at=now or datetime.utcnow(),
        )
        await self.collection.insert_one(model_document(event))
        return event
