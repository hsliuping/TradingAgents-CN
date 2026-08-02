"""DB-backed execution outbox; decision code only enqueues these records."""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import NAMESPACE_URL, uuid5

from app.services.alphaguard.paper_audit_service import PaperAuditService
from app.services.alphaguard.paper_storage import (
    clean_document,
    model_document,
    safe_error_message,
)
from tradingagents.alphaguard.paper_schemas import (
    ExecutionOutboxEvent,
    paper_canonical_hash,
)

from .execution_mode_safety_gate import ExecutionModeSafetyGate


class ExecutionOutboxConflictError(ValueError):
    pass


class ExecutionOutboxService:
    def __init__(self, db):
        self.db = db
        self.collection = db["ag_execution_outbox"]
        self.audit = PaperAuditService(db)
        self.execution_mode_gate = ExecutionModeSafetyGate(db)

    async def enqueue(
        self,
        *,
        event_type: str,
        source_object_id: str,
        user_id: str,
        account_id: str | None = None,
        analysis_id: str | None = None,
        candidate_id: str | None = None,
        snapshot_id: str | None = None,
        experiment_id: str | None = None,
        assignment_id: str | None = None,
        challenger_version_id: str | None = None,
        baseline_champion_id: str | None = None,
        config_hash: str | None = None,
        run_mode: str | None = None,
        now: datetime | None = None,
    ) -> ExecutionOutboxEvent:
        now = now or datetime.utcnow()
        await self.execution_mode_gate.assert_outbox_allowed(
            event_type=event_type,
            source_object_id=source_object_id,
        )
        identity_payload = {
            "event_type": event_type,
            "source_object_id": source_object_id,
            "user_id": str(user_id),
            "account_id": account_id,
        }
        lineage_payload = {
            "snapshot_id": snapshot_id,
            "experiment_id": experiment_id,
            "assignment_id": assignment_id,
            "challenger_version_id": challenger_version_id,
            "baseline_champion_id": baseline_champion_id,
            "config_hash": config_hash,
            "run_mode": run_mode,
        }
        if any(value is not None for value in lineage_payload.values()):
            identity_payload.update(lineage_payload)
        idempotency_key = paper_canonical_hash(identity_payload)
        existing = clean_document(
            await self.collection.find_one({"idempotency_key": idempotency_key})
        )
        if existing:
            stored = ExecutionOutboxEvent.model_validate(existing)
            expected = identity_payload
            actual = {
                "event_type": stored.event_type,
                "source_object_id": stored.source_object_id,
                "user_id": stored.user_id,
                "account_id": stored.account_id,
            }
            if any(value is not None for value in lineage_payload.values()):
                actual.update(
                    {key: getattr(stored, key) for key in lineage_payload}
                )
            if actual != expected:
                raise ExecutionOutboxConflictError(
                    "same outbox idempotency key has conflicting content"
                )
            return stored
        event = ExecutionOutboxEvent(
            outbox_event_id=str(
                uuid5(NAMESPACE_URL, f"alphaguard:outbox:{idempotency_key}")
            ),
            event_type=event_type,
            source_object_id=source_object_id,
            user_id=str(user_id),
            account_id=account_id,
            analysis_id=analysis_id,
            candidate_id=candidate_id,
            **lineage_payload,
            status="PENDING",
            attempt_count=0,
            next_attempt_at=now,
            idempotency_key=idempotency_key,
            created_at=now,
            updated_at=now,
        )
        await self.collection.insert_one(model_document(event))
        await self.audit.record(
            "EXECUTION_OUTBOX_CREATED",
            "decision output queued for internal paper execution",
            user_id=str(user_id),
            account_id=account_id,
            source_type=event_type,
            source_object_id=source_object_id,
            now=now,
        )
        return event

    async def pending(self, *, limit: int = 50) -> list[ExecutionOutboxEvent]:
        now = datetime.utcnow()
        raw = await self.collection.find(
            {
                "status": {"$in": ["PENDING", "FAILED"]},
            }
        ).sort([("created_at", 1)]).limit(limit).to_list(length=limit)
        events = []
        for document in raw:
            event = ExecutionOutboxEvent.model_validate(clean_document(document))
            if event.next_attempt_at is None or event.next_attempt_at <= now:
                events.append(event)
        return events

    async def mark_processing(
        self,
        event: ExecutionOutboxEvent,
        *,
        now: datetime | None = None,
    ) -> ExecutionOutboxEvent | None:
        now = now or datetime.utcnow()
        result = await self.collection.update_one(
            {
                "outbox_event_id": event.outbox_event_id,
                "status": {"$in": ["PENDING", "FAILED"]},
                "attempt_count": event.attempt_count,
            },
            {
                "$set": {
                    "status": "PROCESSING",
                    "updated_at": now,
                }
            },
        )
        if result.matched_count != 1:
            return None
        return event.model_copy(update={"status": "PROCESSING", "updated_at": now})

    async def complete(
        self,
        event: ExecutionOutboxEvent,
        *,
        now: datetime | None = None,
    ) -> None:
        now = now or datetime.utcnow()
        await self.collection.update_one(
            {"outbox_event_id": event.outbox_event_id, "status": "PROCESSING"},
            {
                "$set": {
                    "status": "COMPLETED",
                    "next_attempt_at": None,
                    "last_error": None,
                    "updated_at": now,
                }
            },
        )

    async def fail(
        self,
        event: ExecutionOutboxEvent,
        error: Exception,
        *,
        now: datetime | None = None,
    ) -> None:
        now = now or datetime.utcnow()
        attempt = event.attempt_count + 1
        message = safe_error_message(error)
        terminal = attempt >= event.max_attempts
        await self.collection.update_one(
            {"outbox_event_id": event.outbox_event_id},
            {
                "$set": {
                    "status": "DEAD_LETTER" if terminal else "FAILED",
                    "attempt_count": attempt,
                    "next_attempt_at": (
                        None
                        if terminal
                        else now + timedelta(minutes=min(60, 2 ** attempt))
                    ),
                    "last_error": message,
                    "updated_at": now,
                },
                "$push": {
                    "error_history": {
                        "attempt": attempt,
                        "error": message,
                        "at": now,
                    }
                },
            },
        )
        await self.audit.record(
            (
                "EXECUTION_OUTBOX_DEAD_LETTER"
                if terminal
                else "EXECUTION_OUTBOX_RETRIED"
            ),
            message,
            user_id=event.user_id,
            account_id=event.account_id,
            source_type=event.event_type,
            source_object_id=event.source_object_id,
            now=now,
        )
