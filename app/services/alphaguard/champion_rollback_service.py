"""Administrator-only, recoverable Champion rollback.

Rollback changes only the effective pointer for future tasks.  It never deletes
the failed version or rewrites snapshots, decisions, orders, lots, or positions.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import NAMESPACE_URL, uuid4, uuid5

from app.services.alphaguard.champion_resolver import (
    ChampionResolver,
    assignment_hash,
)
from app.services.alphaguard.experiment_audit_service import ExperimentAuditService
from app.services.alphaguard.experiment_repository import (
    ExperimentIntegrityConflict,
    ExperimentRepository,
    experiment_document,
)
from app.services.alphaguard.paper_calendar_service import (
    PaperTradingCalendarService,
)
from tradingagents.alphaguard.experiment_schemas import (
    ChampionAssignment,
    ChampionAssignmentHistory,
    PromotionSaga,
    RollbackRecord,
)


class ChampionRollbackService:
    def __init__(self, db):
        self.db = db
        self.repository = ExperimentRepository(db)
        self.resolver = ChampionResolver(db)
        self.calendar = PaperTradingCalendarService(db)
        self.audit = ExperimentAuditService(db)

    async def rollback(
        self,
        champion_slot_id: str,
        *,
        requested_by: str,
        approved_by: str,
        reason: str,
        confirmation_text: str,
        current_champion_hash: str,
        effective_from_trade_date: date,
        now: datetime | None = None,
    ) -> tuple[RollbackRecord, PromotionSaga]:
        now = now or datetime.utcnow()
        expected_text = f"ROLLBACK {champion_slot_id}"
        if confirmation_text != expected_text:
            raise ValueError("rollback confirmation text mismatch")
        if not await self.calendar.is_open_date(effective_from_trade_date):
            raise ValueError("rollback effective date must be an open trade date")
        raw = await self.repository.get(
            "champion_assignments", {"champion_slot_id": champion_slot_id}
        )
        if raw is None:
            raise LookupError("ChampionAssignment does not exist")
        current = ChampionAssignment.model_validate(raw)
        if current.assignment_hash != current_champion_hash:
            raise ExperimentIntegrityConflict(
                "Champion changed before rollback approval"
            )
        if not current.previous_version_ref:
            raise ValueError("Champion has no previous version to roll back to")
        target = await self.repository.get(
            "component_versions",
            {"version_ref": current.previous_version_ref},
        )
        if target is None:
            raise LookupError("rollback target version no longer exists")
        rollback_id = str(
            uuid5(
                NAMESPACE_URL,
                "alphaguard:rollback:"
                f"{champion_slot_id}:{current.assignment_hash}:"
                f"{effective_from_trade_date.isoformat()}",
            )
        )
        existing = await self.repository.get(
            "rollbacks", {"rollback_id": rollback_id}
        )
        if existing:
            record = RollbackRecord.model_validate(existing)
            saga_raw = await self.repository.get(
                "promotion_sagas", {"rollback_id": rollback_id}
            )
            if saga_raw is None:
                raise ExperimentIntegrityConflict(
                    "RollbackRecord exists without PromotionSaga"
                )
            return record, PromotionSaga.model_validate(saga_raw)
        record = RollbackRecord(
            rollback_id=rollback_id,
            champion_slot_id=champion_slot_id,
            from_version_ref=current.current_version_ref,
            to_version_ref=current.previous_version_ref,
            reason=reason,
            requested_by=str(requested_by),
            approved_by=str(approved_by),
            effective_from_trade_date=effective_from_trade_date,
            status="PREPARED",
            created_at=now,
        )
        await self.db["ag_exp_rollbacks"].insert_one(
            experiment_document(record)
        )
        saga = await self._run_saga(record, current=current, now=now)
        committed = record.model_copy(
            update={
                "promotion_saga_id": saga.promotion_saga_id,
                "status": "COMMITTED",
            }
        )
        await self.db["ag_exp_rollbacks"].replace_one(
            {"rollback_id": rollback_id},
            experiment_document(committed),
        )
        return committed, saga

    async def _save_saga(self, saga: PromotionSaga) -> None:
        await self.db["ag_exp_promotion_sagas"].replace_one(
            {"promotion_saga_id": saga.promotion_saga_id},
            experiment_document(saga),
            upsert=True,
        )

    async def _run_saga(
        self,
        record: RollbackRecord,
        *,
        current: ChampionAssignment,
        now: datetime,
    ) -> PromotionSaga:
        saga_id = str(
            uuid5(NAMESPACE_URL, f"alphaguard:rollback-saga:{record.rollback_id}")
        )
        lock_key = f"promotion:{current.champion_slot_id}"
        saga = PromotionSaga(
            promotion_saga_id=saga_id,
            operation="ROLLBACK",
            rollback_id=record.rollback_id,
            champion_slot_id=current.champion_slot_id,
            status="PREPARED",
            from_version_ref=current.current_version_ref,
            to_version_ref=current.previous_version_ref or "",
            expected_assignment_hash=current.assignment_hash,
            effective_from_trade_date=record.effective_from_trade_date,
            lock_key=lock_key,
            created_by=record.approved_by,
            created_at=now,
            updated_at=now,
        )
        await self._save_saga(saga)
        old = current
        try:
            if await self.db["ag_exp_locks"].find_one({"_id": lock_key}):
                raise ExperimentIntegrityConflict("Champion slot is locked")
            await self.db["ag_exp_locks"].insert_one(
                {
                    "_id": lock_key,
                    "lock_type": "CHAMPION_ROLLBACK",
                    "promotion_saga_id": saga_id,
                    "created_at": now,
                }
            )
            saga = saga.model_copy(update={"status": "LOCK_ACQUIRED"})
            await self._save_saga(saga)
            latest_raw = await self.repository.get(
                "champion_assignments",
                {"champion_slot_id": current.champion_slot_id},
            )
            latest = ChampionAssignment.model_validate(latest_raw)
            if latest.assignment_hash != current.assignment_hash:
                raise ExperimentIntegrityConflict("Champion changed during rollback")
            saga = saga.model_copy(update={"status": "CURRENT_CHAMPION_VERIFIED"})
            await self._save_saga(saga)
            prior_history = ChampionAssignmentHistory(
                history_id=str(uuid4()),
                champion_slot_id=latest.champion_slot_id,
                assignment=latest,
                committed_saga_id=latest.promotion_saga_id,
                recorded_at=datetime.utcnow(),
            )
            await self.repository.insert_once(
                "champion_history",
                prior_history,
                identity={"history_id": prior_history.history_id},
            )
            payload = {
                "champion_slot_id": latest.champion_slot_id,
                "component_type": latest.component_type,
                "component_key": latest.component_key,
                "market": latest.market,
                "current_version_ref": record.to_version_ref,
                "previous_version_ref": latest.current_version_ref,
                "source_experiment_id": None,
                "source_promotion_request_id": None,
                "effective_from_trade_date": record.effective_from_trade_date,
                "assignment_version": latest.assignment_version + 1,
                "status": "ACTIVE",
                "promotion_saga_id": saga_id,
                "updated_by": record.approved_by,
                "updated_at": datetime.utcnow(),
            }
            payload["assignment_hash"] = assignment_hash(payload)
            replacement = ChampionAssignment.model_validate(payload)
            write = await self.db["ag_exp_champion_assignments"].replace_one(
                {
                    "champion_slot_id": latest.champion_slot_id,
                    "assignment_hash": latest.assignment_hash,
                },
                experiment_document(replacement),
            )
            if write.matched_count != 1:
                raise ExperimentIntegrityConflict("rollback pointer CAS failed")
            saga = saga.model_copy(
                update={
                    "status": "ASSIGNMENT_WRITTEN",
                    "written_assignment_hash": replacement.assignment_hash,
                }
            )
            await self._save_saga(saga)
            resolution = await self.resolver.verify_pending_assignment(
                champion_slot_id=replacement.champion_slot_id,
                saga_id=saga_id,
                as_of_trade_date=record.effective_from_trade_date,
            )
            if resolution.version_ref != record.to_version_ref:
                raise ExperimentIntegrityConflict("rollback resolver verification failed")
            saga = saga.model_copy(update={"status": "RESOLVER_VERIFIED"})
            await self._save_saga(saga)
            saga = saga.model_copy(
                update={
                    "status": "COMMITTED",
                    "committed_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                }
            )
            await self._save_saga(saga)
            await self.audit.record(
                "CHAMPION_ROLLED_BACK",
                "human-approved rollback committed for future tasks only",
                promotion_saga_id=saga_id,
                champion_slot_id=record.champion_slot_id,
                baseline_version_ref=record.from_version_ref,
                challenger_version_ref=record.to_version_ref,
                current_champion_version_ref=record.to_version_ref,
                result_hash=replacement.assignment_hash,
            )
            return saga
        except Exception as exc:
            after = await self.repository.get(
                "champion_assignments",
                {"champion_slot_id": current.champion_slot_id},
            )
            terminal = "FAILED"
            if after and after.get("promotion_saga_id") == saga_id:
                await self.db["ag_exp_champion_assignments"].replace_one(
                    {"champion_slot_id": old.champion_slot_id},
                    experiment_document(old),
                )
                terminal = "ROLLED_BACK"
            saga = saga.model_copy(
                update={
                    "status": terminal,
                    "last_error": f"{type(exc).__name__}: {str(exc)[:500]}",
                    "updated_at": datetime.utcnow(),
                }
            )
            await self._save_saga(saga)
            await self.db["ag_exp_rollbacks"].update_one(
                {"rollback_id": record.rollback_id},
                {"$set": {"status": "FAILED", "promotion_saga_id": saga_id}},
            )
            raise
        finally:
            await self.db["ag_exp_locks"].delete_one({"_id": lock_key})
