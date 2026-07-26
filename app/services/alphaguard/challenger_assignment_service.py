"""Exclusive PAPER_CHALLENGER assignment lifecycle."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

from app.services.alphaguard.experiment_audit_service import ExperimentAuditService
from app.services.alphaguard.experiment_config import promotion_policy
from app.services.alphaguard.experiment_registry import ExperimentRegistry
from app.services.alphaguard.experiment_repository import (
    ExperimentIntegrityConflict,
    ExperimentRepository,
    experiment_document,
)
from app.services.alphaguard.paper_account_service import PaperAccountService
from app.services.alphaguard.paper_calendar_service import (
    PaperTradingCalendarService,
)
from app.services.alphaguard.paper_storage import clean_document
from tradingagents.alphaguard.experiment_schemas import ChallengerAssignment


OPEN_ORDER_STATUSES = [
    "CREATED",
    "RESERVED",
    "SUBMITTED",
    "PENDING",
    "PARTIALLY_FILLED",
    "SETTLEMENT_PENDING",
    "SETTLEMENT_FAILED",
]


class ChallengerAssignmentService:
    def __init__(self, db):
        self.db = db
        self.registry = ExperimentRegistry(db)
        self.repository = ExperimentRepository(db)
        self.audit = ExperimentAuditService(db)
        self.accounts = PaperAccountService(db)
        self.calendar = PaperTradingCalendarService(db)
        self.policy = promotion_policy()

    async def activate(
        self,
        experiment_id: str,
        *,
        user_id: str,
        activation_trade_date: date,
        now: datetime | None = None,
    ) -> ChallengerAssignment:
        now = now or datetime.utcnow()
        definition = await self.registry.get(experiment_id)
        existing_same = clean_document(
            await self.db["ag_exp_challenger_assignments"].find_one(
                {
                    "experiment_id": experiment_id,
                    "user_id": str(user_id),
                    "status": {"$in": ["ACTIVE", "CLOSING"]},
                }
            )
        )
        if existing_same:
            return ChallengerAssignment.model_validate(existing_same)
        if definition.status != "SHADOW":
            raise ValueError("experiment must be SHADOW before Challenger")
        completed_shadow = clean_document(
            await self.db["ag_exp_shadow_runs"].find_one(
                {"experiment_id": experiment_id, "status": "COMPLETED"},
                sort=[("ended_at", -1)],
            )
        )
        if completed_shadow is None:
            raise ValueError("completed Shadow evidence is required")
        required_days = int(
            self.policy.minimum_sample_rules["shadow_trade_days"]
        )
        if int(completed_shadow["observed_trade_days"]) < required_days:
            raise ValueError("Shadow observation period is insufficient")
        if not await self.calendar.is_open_date(activation_trade_date):
            raise ValueError("activation date is not a persisted CN open date")
        account = await self.accounts.get_user_account(
            str(user_id), "PAPER_CHALLENGER"
        )
        if account is None or account.status != "ACTIVE":
            raise ValueError("active PAPER_CHALLENGER account is required")
        if await self.db["ag_paper_orders"].find(
            {
                "account_id": account.account_id,
                "status": {"$in": OPEN_ORDER_STATUSES},
            }
        ).limit(1).to_list(length=1):
            raise ValueError("Challenger account has unfinished orders")
        if await self.db["ag_paper_reservations"].find(
            {
                "account_id": account.account_id,
                "status": {"$in": ["ACTIVE", "PARTIALLY_CONSUMED"]},
            }
        ).limit(1).to_list(length=1):
            raise ValueError("Challenger account has active reservations")
        if await self.db["ag_paper_positions"].find(
            {"account_id": account.account_id, "quantity": {"$gt": 0}}
        ).limit(1).to_list(length=1):
            raise ValueError("non-empty Challenger account cannot be reassigned")
        exclusivity_key = f"{user_id}:CN"
        existing = clean_document(
            await self.db["ag_exp_challenger_assignments"].find_one(
                {
                    "exclusivity_key": exclusivity_key,
                    "status": {"$in": ["ACTIVE", "CLOSING"]},
                }
            )
        )
        if existing:
            if existing.get("experiment_id") == experiment_id:
                return ChallengerAssignment.model_validate(existing)
            raise ValueError("another ACTIVE/CLOSING Challenger owns this account")
        lock_key = f"challenger:{exclusivity_key}"
        try:
            await self.db["ag_exp_locks"].insert_one(
                {
                    "_id": lock_key,
                    "lock_type": "CHALLENGER_ASSIGNMENT",
                    "experiment_id": experiment_id,
                    "created_at": now,
                }
            )
        except Exception as exc:
            raise ExperimentIntegrityConflict(
                "Challenger assignment lock conflict"
            ) from exc
        try:
            snapshot = await self.accounts.create_daily_snapshot(
                account.account_id, activation_trade_date
            )
            assignment = ChallengerAssignment(
                assignment_id=str(
                    uuid5(
                        NAMESPACE_URL,
                        f"alphaguard:challenger-assignment:"
                        f"{experiment_id}:{exclusivity_key}:"
                        f"{activation_trade_date}",
                    )
                ),
                experiment_id=experiment_id,
                user_id=str(user_id),
                market="CN",
                account_id=account.account_id,
                activation_trade_date=activation_trade_date,
                baseline_account_snapshot_id=snapshot.account_snapshot_id,
                starting_equity=Decimal(snapshot.total_equity),
                status="ACTIVE",
                exclusivity_key=exclusivity_key,
                created_at=now,
                activated_at=now,
            )
            await self.db["ag_exp_challenger_assignments"].insert_one(
                experiment_document(assignment)
            )
            await self.registry.transition(
                experiment_id,
                "CHALLENGER",
                reason="exclusive PAPER_CHALLENGER assignment activated",
            )
        except Exception:
            await self.db["ag_exp_locks"].delete_one({"_id": lock_key})
            raise
        await self.audit.record(
            "CHALLENGER_ACTIVATED",
            "exclusive PAPER_CHALLENGER assignment activated",
            experiment_id=experiment_id,
            assignment_id=assignment.assignment_id,
            user_id=str(user_id),
            market="CN",
        )
        return assignment

    async def deactivate(
        self,
        experiment_id: str,
        *,
        reason: str,
    ) -> ChallengerAssignment:
        raw = clean_document(
            await self.db["ag_exp_challenger_assignments"].find_one(
                {
                    "experiment_id": experiment_id,
                    "status": {"$in": ["ACTIVE", "CLOSING"]},
                }
            )
        )
        if raw is None:
            raise LookupError("active ChallengerAssignment does not exist")
        assignment = ChallengerAssignment.model_validate(raw)
        has_orders = bool(
            await self.db["ag_paper_orders"].find(
                {
                    "account_id": assignment.account_id,
                    "status": {"$in": OPEN_ORDER_STATUSES},
                }
            ).limit(1).to_list(length=1)
        )
        has_positions = bool(
            await self.db["ag_paper_positions"].find(
                {"account_id": assignment.account_id, "quantity": {"$gt": 0}}
            ).limit(1).to_list(length=1)
        )
        now = datetime.utcnow()
        if has_orders or has_positions:
            status = "CLOSING"
            event = "CHALLENGER_CLOSING"
        else:
            status = "COMPLETED"
            event = "CHALLENGER_COMPLETED"
        updated = assignment.model_copy(
            update={
                "status": status,
                "deactivation_trade_date": now.date(),
            }
        )
        await self.db["ag_exp_challenger_assignments"].replace_one(
            {"assignment_id": assignment.assignment_id},
            experiment_document(updated),
        )
        if status == "COMPLETED":
            await self.db["ag_exp_locks"].delete_one(
                {"_id": f"challenger:{assignment.exclusivity_key}"}
            )
            definition = await self.registry.get(experiment_id)
            if definition.status == "CHALLENGER":
                await self.registry.transition(
                    experiment_id,
                    "SHADOW",
                    reason="Challenger assignment completed without forced liquidation",
                )
        await self.audit.record(
            event,
            reason,
            experiment_id=experiment_id,
            assignment_id=assignment.assignment_id,
            user_id=assignment.user_id,
            market=assignment.market,
        )
        return updated

    async def reconcile_closing(self) -> dict[str, int]:
        """Complete only naturally-flat assignments; never force liquidation."""

        closing = await self.db["ag_exp_challenger_assignments"].find(
            {"status": "CLOSING"}
        ).sort("created_at", 1).to_list(length=None)
        counts = {"completed": 0, "still_closing": 0, "failed": 0}
        for raw in closing:
            assignment = ChallengerAssignment.model_validate(
                clean_document(raw)
            )
            try:
                updated = await self.deactivate(
                    assignment.experiment_id,
                    reason=(
                        "Challenger close monitor found no remaining orders "
                        "or positions"
                    ),
                )
                if updated.status == "COMPLETED":
                    counts["completed"] += 1
                else:
                    counts["still_closing"] += 1
            except Exception as exc:
                counts["failed"] += 1
                await self.audit.record(
                    "CHALLENGER_SUSPENDED",
                    f"close monitor failed: {type(exc).__name__}: {str(exc)[:300]}",
                    experiment_id=assignment.experiment_id,
                    assignment_id=assignment.assignment_id,
                    user_id=assignment.user_id,
                    market=assignment.market,
                )
        return counts
