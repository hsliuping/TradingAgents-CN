"""Append-only PR-007 evaluation audit events."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from app.services.alphaguard.paper_storage import model_document
from tradingagents.alphaguard.evaluation_schemas import EvaluationEvent


class EvaluationAuditService:
    def __init__(self, db):
        self.collection = db["ag_eval_events"]

    async def record(self, event_type: str, reason: str, **identity) -> EvaluationEvent:
        allowed = set(EvaluationEvent.model_fields) - {
            "event_id",
            "event_type",
            "reason",
            "created_at",
            "schema_version",
        }
        event = EvaluationEvent(
            event_id=str(uuid4()),
            event_type=event_type,
            reason=reason[:1000],
            created_at=datetime.utcnow(),
            **{key: value for key, value in identity.items() if key in allowed},
        )
        await self.collection.insert_one(model_document(event))
        return event
