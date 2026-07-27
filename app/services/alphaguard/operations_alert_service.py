"""Deterministic operational alert aggregation and append-only audit."""

from __future__ import annotations

from datetime import datetime
from uuid import NAMESPACE_URL, uuid4, uuid5

from app.services.alphaguard.paper_storage import clean_document, model_document
from tradingagents.alphaguard.operations_schemas import (
    OperationalAlert,
    operations_hash,
    sanitize_operational_value,
)


class OperationsAlertService:
    def __init__(self, db):
        self.db = db

    async def observe(
        self,
        *,
        severity: str,
        category: str,
        code: str,
        title: str,
        message: str,
        source_module: str,
        source_object_id: str | None = None,
        trace_id: str | None = None,
        now: datetime | None = None,
    ) -> OperationalAlert:
        now = now or datetime.utcnow()
        fingerprint = operations_hash(
            {
                "category": category,
                "code": code,
                "source_module": source_module,
                "source_object_id": source_object_id,
            }
        )
        alert_id = str(uuid5(NAMESPACE_URL, f"alphaguard:alert:{fingerprint}"))
        raw = clean_document(
            await self.db["ag_ops_alerts"].find_one({"alert_id": alert_id})
        )
        if raw:
            previous = OperationalAlert.model_validate(raw)
            alert = previous.model_copy(
                update={
                    "severity": severity,
                    "title": title,
                    "sanitized_message": sanitize_operational_value(message),
                    "trace_id": trace_id or previous.trace_id,
                    "last_seen_at": now,
                    "occurrence_count": previous.occurrence_count + 1,
                    "status": (
                        "OPEN" if previous.status == "RESOLVED" else previous.status
                    ),
                    "resolved_at": (
                        None if previous.status == "RESOLVED" else previous.resolved_at
                    ),
                    "acknowledged_by": (
                        None
                        if previous.status == "RESOLVED"
                        else previous.acknowledged_by
                    ),
                    "acknowledged_at": (
                        None
                        if previous.status == "RESOLVED"
                        else previous.acknowledged_at
                    ),
                    "resolution_note": (
                        None
                        if previous.status == "RESOLVED"
                        else previous.resolution_note
                    ),
                }
            )
            await self.db["ag_ops_alerts"].replace_one(
                {"alert_id": alert_id}, model_document(alert)
            )
            event_type = "OPERATIONAL_ALERT_REOBSERVED"
        else:
            alert = OperationalAlert(
                alert_id=alert_id,
                severity=severity,
                category=category,
                code=code,
                title=title,
                sanitized_message=sanitize_operational_value(message),
                source_module=source_module,
                source_object_id=source_object_id,
                trace_id=trace_id,
                first_seen_at=now,
                last_seen_at=now,
                occurrence_count=1,
                status="OPEN",
            )
            await self.db["ag_ops_alerts"].insert_one(model_document(alert))
            event_type = "OPERATIONAL_ALERT_CREATED"
        await self._event(
            event_type,
            alert=alert,
            actor_id=None,
            reason=alert.sanitized_message,
            now=now,
        )
        return alert

    async def acknowledge(
        self,
        alert_id: str,
        *,
        actor_id: str,
        now: datetime | None = None,
    ) -> OperationalAlert:
        now = now or datetime.utcnow()
        alert = await self.get(alert_id)
        if alert.status == "RESOLVED":
            return alert
        updated = alert.model_copy(
            update={
                "status": "ACKNOWLEDGED",
                "acknowledged_by": str(actor_id),
                "acknowledged_at": now,
            }
        )
        await self.db["ag_ops_alerts"].replace_one(
            {"alert_id": alert_id}, model_document(updated)
        )
        await self._event(
            "OPERATIONAL_ALERT_ACKNOWLEDGED",
            alert=updated,
            actor_id=str(actor_id),
            reason="alert acknowledged",
            now=now,
        )
        return updated

    async def resolve(
        self,
        alert_id: str,
        *,
        actor_id: str,
        resolution_note: str,
        now: datetime | None = None,
    ) -> OperationalAlert:
        now = now or datetime.utcnow()
        alert = await self.get(alert_id)
        if alert.status == "RESOLVED":
            return alert
        updated = alert.model_copy(
            update={
                "status": "RESOLVED",
                "resolution_note": sanitize_operational_value(resolution_note),
                "resolved_at": now,
                "acknowledged_by": alert.acknowledged_by or str(actor_id),
                "acknowledged_at": alert.acknowledged_at or now,
            }
        )
        await self.db["ag_ops_alerts"].replace_one(
            {"alert_id": alert_id}, model_document(updated)
        )
        await self._event(
            "OPERATIONAL_ALERT_RESOLVED",
            alert=updated,
            actor_id=str(actor_id),
            reason=updated.resolution_note or "alert resolved",
            now=now,
        )
        return updated

    async def get(self, alert_id: str) -> OperationalAlert:
        raw = clean_document(
            await self.db["ag_ops_alerts"].find_one({"alert_id": alert_id})
        )
        if not raw:
            raise KeyError(f"operational alert not found: {alert_id}")
        return OperationalAlert.model_validate(raw)

    async def list(
        self,
        *,
        status: str | None = None,
        severity: str | None = None,
        limit: int = 200,
    ) -> list[OperationalAlert]:
        query: dict = {}
        if status:
            query["status"] = status
        if severity:
            query["severity"] = severity
        rows = await self.db["ag_ops_alerts"].find(query).sort(
            "last_seen_at", -1
        ).limit(limit).to_list(length=limit)
        return [
            OperationalAlert.model_validate(clean_document(row)) for row in rows
        ]

    async def _event(
        self,
        event_type: str,
        *,
        alert: OperationalAlert,
        actor_id: str | None,
        reason: str,
        now: datetime,
    ) -> None:
        await self.db["ag_ops_events"].insert_one(
            {
                "event_id": str(uuid4()),
                "event_type": event_type,
                "alert_id": alert.alert_id,
                "actor_id": actor_id,
                "trace_id": alert.trace_id,
                "reason": sanitize_operational_value(reason),
                "created_at": now,
                "schema_version": "alphaguard-operations-v1",
            }
        )
