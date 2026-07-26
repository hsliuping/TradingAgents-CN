"""Idempotent automatic paper-trading tasks for APScheduler/Worker reuse."""

from __future__ import annotations

from datetime import date, datetime, time
from uuid import NAMESPACE_URL, uuid5

from app.services.alphaguard.execution_market_snapshot_service import (
    ExecutionMarketSnapshotService,
)
from app.services.alphaguard.execution_outbox_service import ExecutionOutboxService
from app.services.alphaguard.order_intent_factory import OrderIntentFactory
from app.services.alphaguard.paper_account_service import PaperAccountService
from app.services.alphaguard.paper_candidate_sync_service import (
    PaperCandidateSyncService,
)
from app.services.alphaguard.paper_execution_service import PaperExecutionService
from app.services.alphaguard.paper_order_service import PaperOrderService
from app.services.alphaguard.paper_storage import (
    clean_document,
    model_document,
    safe_error_message,
)
from app.services.alphaguard.settlement_service import SettlementService
from tradingagents.alphaguard.paper_schemas import PaperJobRun


class PaperTaskService:
    def __init__(self, db):
        self.db = db
        self.outbox = ExecutionOutboxService(db)
        self.intents = OrderIntentFactory(db)
        self.orders = PaperOrderService(db)
        self.execution_snapshots = ExecutionMarketSnapshotService(db)
        self.execution = PaperExecutionService(db)
        self.settlement = SettlementService(db)
        self.accounts = PaperAccountService(db)
        self.candidate_sync = PaperCandidateSyncService(db)

    async def process_execution_outbox(self, *, limit: int = 50) -> dict[str, int]:
        counts = {"completed": 0, "failed": 0, "dead_letter": 0}
        for pending in await self.outbox.pending(limit=limit):
            event = await self.outbox.mark_processing(pending)
            if event is None:
                continue
            try:
                intent = await self.intents.create_from_outbox(event)
                order = await self.orders.create_reserve_submit(intent)
                await self.candidate_sync.sync_order(order)
                await self.outbox.complete(event)
                counts["completed"] += 1
            except Exception as exc:
                await self.outbox.fail(event, exc)
                stored = clean_document(
                    await self.db["ag_execution_outbox"].find_one(
                        {"outbox_event_id": event.outbox_event_id}
                    )
                )
                if stored and stored.get("status") == "DEAD_LETTER":
                    counts["dead_letter"] += 1
                else:
                    counts["failed"] += 1
        return counts

    async def create_order_intents(self, *, limit: int = 50) -> dict[str, int]:
        return await self.process_execution_outbox(limit=limit)

    async def submit_paper_orders(self) -> int:
        documents = await self.db["ag_order_intents"].find({}).to_list(length=None)
        submitted = 0
        for raw in documents:
            from tradingagents.alphaguard.paper_schemas import OrderIntent

            intent = OrderIntent.model_validate(clean_document(raw))
            order = await self.orders.create_reserve_submit(intent)
            await self.candidate_sync.sync_order(order)
            if order.status in {"PENDING", "PARTIALLY_FILLED"}:
                submitted += 1
        return submitted

    async def build_execution_market_snapshots(
        self,
        trade_date: date,
        *,
        cutoff_at: datetime | None = None,
    ) -> dict[str, int]:
        cutoff_at = cutoff_at or datetime.combine(trade_date, time(15, 30))
        documents = await self.db["ag_paper_orders"].find(
            {
                "status": {"$in": ["PENDING", "PARTIALLY_FILLED"]},
            }
        ).to_list(length=None)
        created = failed = 0
        for raw in documents:
            from tradingagents.alphaguard.paper_schemas import PaperOrder

            order = PaperOrder.model_validate(clean_document(raw))
            if (
                trade_date < order.earliest_execute_at.date()
                or trade_date > order.expires_at.date()
            ):
                continue
            try:
                await self.execution_snapshots.build_for_trade_date(
                    symbol=order.symbol,
                    trade_date=trade_date,
                    cutoff_at=cutoff_at,
                    data_version=f"stock_daily_quotes:{trade_date.isoformat()}:v1",
                )
                created += 1
            except Exception:
                failed += 1
        return {"created_or_reused": created, "failed": failed}

    async def match_orders_for_trade_date(self, trade_date: date) -> dict[str, int]:
        documents = await self.db["ag_paper_orders"].find(
            {"status": {"$in": ["PENDING", "PARTIALLY_FILLED"]}}
        ).to_list(length=None)
        filled = no_fill = 0
        for raw in documents:
            from tradingagents.alphaguard.paper_schemas import PaperOrder

            order = PaperOrder.model_validate(clean_document(raw))
            snapshot = clean_document(
                await self.db["ag_execution_market_snapshots"].find_one(
                    {
                        "symbol": order.symbol,
                        "market": "CN",
                        "trade_date": trade_date,
                    }
                )
            )
            if snapshot is None:
                continue
            fill = await self.execution.match_order(
                order.order_id,
                snapshot["execution_snapshot_id"],
                matched_at=datetime.combine(trade_date, time(15, 30)),
            )
            if fill is None:
                no_fill += 1
            else:
                filled += 1
        return {"fills": filled, "no_fill": no_fill}

    async def settle_pending_fills(self) -> dict[str, int]:
        raw_fills = await self.db["ag_paper_fills"].find({}).to_list(length=None)
        committed = failed = 0
        for raw in raw_fills:
            fill = clean_document(raw)
            record = clean_document(
                await self.db["ag_settlement_records"].find_one(
                    {"fill_id": fill["fill_id"]}
                )
            )
            if record and record.get("status") == "COMMITTED":
                continue
            try:
                settlement = await self.settlement.settle_fill(fill["fill_id"])
                order = await self.orders.get_order(settlement.order_id)
                if order:
                    await self.candidate_sync.sync_order(order)
                committed += int(settlement.status == "COMMITTED")
            except Exception:
                failed += 1
        return {"committed": committed, "failed": failed}

    async def expire_orders(self, *, now: datetime | None = None) -> int:
        now = now or datetime.utcnow()
        raw_orders = await self.db["ag_paper_orders"].find(
            {
                "status": {
                    "$in": [
                        "CREATED",
                        "RESERVED",
                        "SUBMITTED",
                        "PENDING",
                        "PARTIALLY_FILLED",
                    ]
                }
            }
        ).to_list(length=None)
        expired = 0
        for raw in raw_orders:
            order = await self.orders.expire(
                clean_document(raw)["order_id"],
                now=now,
            )
            if order.status == "EXPIRED":
                expired += 1
                await self.candidate_sync.sync_order(order)
        return expired

    async def release_stale_reservations(self) -> int:
        raw = await self.db["ag_paper_reservations"].find(
            {"status": {"$in": ["ACTIVE", "PARTIALLY_CONSUMED", "CONSUMED"]}}
        ).to_list(length=None)
        released = 0
        for item in raw:
            reservation = clean_document(item)
            order = await self.orders.get_order(reservation["order_id"])
            if order and order.status in {"FILLED", "CANCELLED", "REJECTED", "EXPIRED"}:
                await self.orders.release_reservation(order.order_id)
                released += 1
        return released

    async def roll_position_lot_availability(self, trade_date: date) -> int:
        return await self.accounts.roll_lot_availability(trade_date)

    async def create_daily_account_snapshots(self, trade_date: date) -> int:
        raw_accounts = await self.db["ag_paper_accounts"].find({}).to_list(length=None)
        count = 0
        for raw in raw_accounts:
            await self.accounts.create_daily_snapshot(
                clean_document(raw)["account_id"],
                trade_date,
            )
            count += 1
        return count

    async def reconcile_paper_accounts(self) -> dict[str, int]:
        conflicts = rebuilt = 0
        raw_positions = await self.db["ag_paper_positions"].find({}).to_list(
            length=None
        )
        for raw in raw_positions:
            stored = clean_document(raw)
            rebuilt_position = await self.accounts.rebuild_position(
                stored["account_id"],
                stored["symbol"],
            )
            rebuilt += 1
            comparable = (
                "quantity",
                "available_quantity",
                "reserved_quantity",
                "total_cost",
            )
            if any(stored.get(key) != getattr(rebuilt_position, key) for key in comparable):
                conflicts += 1
        return {"rebuilt": rebuilt, "conflicts": conflicts}

    async def run_once(
        self,
        *,
        job_type: str,
        trade_date: date | None,
        idempotency_key: str,
        operation,
    ):
        existing = clean_document(
            await self.db["ag_paper_job_runs"].find_one(
                {"idempotency_key": idempotency_key}
            )
        )
        if existing and existing.get("status") == "COMPLETED":
            return existing.get("result")
        now = datetime.utcnow()
        run = PaperJobRun(
            job_id=(
                existing.get("job_id")
                if existing
                else str(uuid5(NAMESPACE_URL, f"alphaguard:paper-job:{idempotency_key}"))
            ),
            job_type=job_type,
            trade_date=trade_date,
            idempotency_key=idempotency_key,
            status="RUNNING",
            attempt_count=int(existing.get("attempt_count", 0)) + 1 if existing else 1,
            started_at=now,
            finished_at=None,
            error=None,
            created_at=existing.get("created_at", now) if existing else now,
        )
        await self.db["ag_paper_job_runs"].replace_one(
            {"idempotency_key": idempotency_key},
            model_document(run),
            upsert=True,
        )
        try:
            result = await operation()
        except Exception as exc:
            await self.db["ag_paper_job_runs"].update_one(
                {"idempotency_key": idempotency_key},
                {
                    "$set": {
                        "status": "FAILED",
                        "finished_at": datetime.utcnow(),
                        "error": safe_error_message(exc),
                    }
                },
            )
            raise
        await self.db["ag_paper_job_runs"].update_one(
            {"idempotency_key": idempotency_key},
            {
                "$set": {
                    "status": "COMPLETED",
                    "finished_at": datetime.utcnow(),
                    "error": None,
                    "result": result,
                }
            },
        )
        return result
