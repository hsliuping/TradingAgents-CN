"""Append-only audit events for deterministic quantitative research."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from app.schemas.alphaguard import QuantAuditEvent


class QuantAuditService:
    def __init__(self, db):
        self.db = db

    async def record(
        self,
        event_type: str,
        *,
        snapshot_id: str | None = None,
        entity_id: str | None = None,
        trace_id: str | None = None,
        details: dict | None = None,
    ) -> QuantAuditEvent:
        event = QuantAuditEvent(
            event_id=str(uuid4()),
            event_type=event_type,
            snapshot_id=snapshot_id,
            entity_id=entity_id,
            trace_id=trace_id,
            details=details or {},
            created_at=datetime.utcnow(),
        )
        await self.db["ag_quant_audit_events"].insert_one(
            event.model_dump(mode="python")
        )
        return event
