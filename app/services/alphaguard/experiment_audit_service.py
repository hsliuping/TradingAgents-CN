"""Append-only PR-008 audit events."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from app.services.alphaguard.experiment_repository import experiment_document
from tradingagents.alphaguard.experiment_schemas import ExperimentEvent


class ExperimentAuditService:
    def __init__(self, db):
        self.collection = db["ag_exp_events"]

    async def record(
        self,
        event_type: str,
        reason: str,
        **identity,
    ) -> ExperimentEvent:
        allowed = set(ExperimentEvent.model_fields) - {
            "event_id",
            "event_type",
            "reason",
            "created_at",
            "schema_version",
        }
        event = ExperimentEvent(
            event_id=str(uuid4()),
            event_type=event_type,
            reason=reason[:1000],
            created_at=datetime.utcnow(),
            **{key: value for key, value in identity.items() if key in allowed},
        )
        await self.collection.insert_one(experiment_document(event))
        return event
