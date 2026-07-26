"""Recoverable settlement Saga for standalone MongoDB deployments."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

from app.services.alphaguard.paper_account_service import PaperAccountService
from app.services.alphaguard.paper_audit_service import PaperAuditService
from app.services.alphaguard.paper_calendar_service import (
    PaperTradingCalendarService,
)
from app.services.alphaguard.paper_order_service import PaperOrderService
from app.services.alphaguard.paper_storage import (
    clean_document,
    model_document,
    safe_error_message,
)
from tradingagents.alphaguard.paper_schemas import (
    LedgerEntry,
    PaperAccount,
    PaperFill,
    PaperPosition,
    PaperReservation,
    PositionLot,
    SettlementRecord,
)


class SettlementIntegrityError(RuntimeError):
    pass


class SettlementService:
    """Journaled Saga; safe to retry after any persisted stage."""

    def __init__(self, db):
        self.db = db
        self.records = db["ag_settlement_records"]
        self.ledger = db["ag_paper_ledger_entries"]
        self.lots = db["ag_paper_position_lots"]
        self.positions = db["ag_paper_positions"]
        self.reservations = db["ag_paper_reservations"]
        self.accounts = PaperAccountService(db)
        self.orders = PaperOrderService(db)
        self.calendar = PaperTradingCalendarService(db)
        self.audit = PaperAuditService(db)

    async def settle_fill(
        self,
        fill_id: str,
        *,
        now: datetime | None = None,
    ) -> SettlementRecord:
        now = now or datetime.utcnow()
        fill = await self._fill(fill_id)
        order = await self.orders.get_order(fill.order_id)
        if order is None:
            raise SettlementIntegrityError("settlement order does not exist")
        reservation = await self.orders.reservation_for_order(order.order_id)
        if reservation is None:
            raise SettlementIntegrityError("settlement reservation does not exist")
        record = await self._prepare(fill, order, reservation, now=now)
        if record.status == "COMMITTED":
            await self._finalize_order(record, fill, now=now)
            return record
        await self.audit.record(
            "SETTLEMENT_STARTED",
            f"settlement Saga resumed from {record.status}",
            user_id=order.user_id,
            account_id=order.account_id,
            account_type=order.account_type,
            intent_id=order.intent_id,
            order_id=order.order_id,
            fill_id=fill.fill_id,
            settlement_id=record.settlement_id,
            symbol=order.symbol,
            trade_date=fill.trade_date,
            now=now,
        )
        try:
            if not record.account_applied:
                await self._apply_account(record, fill, reservation, now=now)
                record = await self._advance(
                    record,
                    "ACCOUNT_APPLIED",
                    account_applied=True,
                    now=now,
                )
            if not record.position_applied:
                await self._apply_position(record, fill, reservation, now=now)
                record = await self._advance(
                    record,
                    "POSITION_APPLIED",
                    position_applied=True,
                    now=now,
                )
            if not record.ledger_applied:
                await self._apply_ledger(record, fill, now=now)
                record = await self._advance(
                    record,
                    "LEDGER_APPLIED",
                    ledger_applied=True,
                    now=now,
                )
            record = await self._advance(
                record,
                "COMMITTED",
                committed_at=now,
                now=now,
            )
            await self._finalize_order(record, fill, now=now)
            await self.audit.record(
                "SETTLEMENT_COMMITTED",
                "settlement Saga committed exactly once",
                user_id=order.user_id,
                account_id=order.account_id,
                account_type=order.account_type,
                intent_id=order.intent_id,
                order_id=order.order_id,
                fill_id=fill.fill_id,
                settlement_id=record.settlement_id,
                symbol=order.symbol,
                trade_date=fill.trade_date,
                now=now,
            )
            return record
        except Exception as exc:
            safe_error = safe_error_message(exc)
            await self.records.update_one(
                {"settlement_id": record.settlement_id},
                {
                    "$set": {
                        "status": "FAILED",
                        "last_error": safe_error,
                        "updated_at": now,
                    }
                },
            )
            current_order = await self.orders.get_order(fill.order_id)
            if current_order and current_order.status == "SETTLEMENT_PENDING":
                await self.orders.transition(
                    fill.order_id,
                    "SETTLEMENT_FAILED",
                    now=now,
                )
            await self.audit.record(
                "SETTLEMENT_FAILED",
                safe_error,
                user_id=order.user_id,
                account_id=order.account_id,
                account_type=order.account_type,
                intent_id=order.intent_id,
                order_id=order.order_id,
                fill_id=fill.fill_id,
                settlement_id=record.settlement_id,
                symbol=order.symbol,
                trade_date=fill.trade_date,
                now=now,
            )
            raise

    async def recover(
        self,
        settlement_id: str,
        *,
        now: datetime | None = None,
    ) -> SettlementRecord:
        raw = clean_document(
            await self.records.find_one({"settlement_id": settlement_id})
        )
        if raw is None:
            raise LookupError("SettlementRecord not found")
        record = SettlementRecord.model_validate(raw)
        if record.status == "COMMITTED":
            return record
        fill = await self._fill(record.fill_id)
        order = await self.orders.get_order(record.order_id)
        if order and order.status == "SETTLEMENT_FAILED":
            await self.orders.transition(
                order.order_id,
                "SETTLEMENT_PENDING",
                now=now,
            )
        recovered = await self.settle_fill(record.fill_id, now=now)
        if recovered.status == "COMMITTED":
            await self.audit.record(
                "SETTLEMENT_RECOVERED",
                "failed settlement Saga recovered idempotently",
                account_id=recovered.account_id,
                order_id=recovered.order_id,
                fill_id=recovered.fill_id,
                settlement_id=recovered.settlement_id,
                now=now,
            )
        return recovered

    async def _prepare(
        self,
        fill: PaperFill,
        order,
        reservation: PaperReservation,
        *,
        now: datetime,
    ) -> SettlementRecord:
        existing = clean_document(
            await self.records.find_one({"fill_id": fill.fill_id})
        )
        if existing:
            record = SettlementRecord.model_validate(existing)
            if (
                record.order_id != fill.order_id
                or record.account_id != fill.account_id
            ):
                raise SettlementIntegrityError(
                    "existing settlement has conflicting identity"
                )
            if record.status == "FAILED":
                recovered_status = (
                    "LEDGER_APPLIED"
                    if record.ledger_applied
                    else "POSITION_APPLIED"
                    if record.position_applied
                    else "ACCOUNT_APPLIED"
                    if record.account_applied
                    else "PREPARED"
                )
                await self.records.update_one(
                    {"settlement_id": record.settlement_id},
                    {
                        "$set": {
                            "status": recovered_status,
                            "attempt_count": record.attempt_count + 1,
                            "updated_at": now,
                        }
                    },
                )
                record = SettlementRecord.model_validate(
                    {
                        **record.model_dump(mode="python"),
                        "status": recovered_status,
                        "attempt_count": record.attempt_count + 1,
                        "updated_at": now,
                    }
                )
            return record
        position_cost = Decimal("0")
        consumptions: list[dict] = []
        available_from = None
        if fill.side == "BUY":
            available_from = await self.calendar.next_open_date(fill.trade_date)
            position_cost = fill.notional + fill.fee_breakdown.total_fee
        else:
            remaining = fill.quantity
            for allocation in reservation.lot_allocations:
                raw_lot = clean_document(
                    await self.lots.find_one({"lot_id": allocation.lot_id})
                )
                if raw_lot is None:
                    raise SettlementIntegrityError("settlement lot does not exist")
                lot = PositionLot.model_validate(raw_lot)
                still_reserved = lot.reservation_allocations.get(
                    reservation.reservation_id,
                    0,
                )
                take = min(remaining, still_reserved)
                if take:
                    cost = lot.unit_cost * take
                    consumptions.append(
                        {
                            "lot_id": lot.lot_id,
                            "quantity": take,
                            "cost": cost,
                        }
                    )
                    position_cost += cost
                    remaining -= take
                if remaining == 0:
                    break
            if remaining:
                raise SettlementIntegrityError(
                    "reserved FIFO lots do not cover the fill"
                )
        realized = (
            fill.notional - fill.fee_breakdown.total_fee - position_cost
            if fill.side == "SELL"
            else Decimal("0")
        )
        record = SettlementRecord(
            settlement_id=str(
                uuid5(NAMESPACE_URL, f"alphaguard:settlement:{fill.fill_id}")
            ),
            fill_id=fill.fill_id,
            order_id=fill.order_id,
            account_id=fill.account_id,
            status="PREPARED",
            realized_pnl=realized,
            position_cost=position_cost,
            cash_effect=fill.net_cash_effect,
            lot_consumptions=consumptions,
            acquired_available_from_date=available_from,
            created_at=now,
            updated_at=now,
        )
        await self.records.insert_one(model_document(record))
        return record

    async def _apply_account(
        self,
        record: SettlementRecord,
        fill: PaperFill,
        reservation: PaperReservation,
        *,
        now: datetime,
    ) -> None:
        account = await self.accounts.get_account(fill.account_id)
        if account is None:
            raise SettlementIntegrityError("settlement account does not exist")
        if record.settlement_id not in account.applied_settlement_ids:
            if fill.side == "BUY":
                cost = fill.notional + fill.fee_breakdown.total_fee
                if account.cash_reserved < cost:
                    raise SettlementIntegrityError(
                        "cash reservation cannot cover settlement"
                    )
                cash_available = account.cash_available
                cash_reserved = account.cash_reserved - cost
                realized = account.realized_pnl
            else:
                cash_available = account.cash_available + fill.net_cash_effect
                cash_reserved = account.cash_reserved
                realized = account.realized_pnl + record.realized_pnl
            updated = PaperAccount.model_validate(
                account.model_copy(
                    update={
                        "cash_available": cash_available,
                        "cash_reserved": cash_reserved,
                        "realized_pnl": realized,
                        "total_fees": (
                            account.total_fees + fill.fee_breakdown.total_fee
                        ),
                        "applied_settlement_ids": [
                            *account.applied_settlement_ids,
                            record.settlement_id,
                        ],
                        "updated_at": now,
                        "account_version": account.account_version + 1,
                    }
                ).model_dump(mode="python")
            )
            result = await self.db["ag_paper_accounts"].replace_one(
                {
                    "account_id": account.account_id,
                    "account_version": account.account_version,
                },
                model_document(updated),
            )
            if result.matched_count != 1:
                current = await self.accounts.get_account(account.account_id)
                if (
                    current is None
                    or record.settlement_id not in current.applied_settlement_ids
                ):
                    raise SettlementIntegrityError(
                        "concurrent account settlement conflict"
                    )
        current_reservation = await self.orders.reservation_for_order(fill.order_id)
        if current_reservation is None:
            raise SettlementIntegrityError("settlement reservation disappeared")
        if record.settlement_id in current_reservation.applied_settlement_ids:
            return
        if fill.side == "BUY":
            consumed_amount = (
                current_reservation.consumed_amount
                + fill.notional
                + fill.fee_breakdown.total_fee
            )
            consumed_quantity = current_reservation.consumed_quantity + fill.quantity
            status = (
                "CONSUMED"
                if consumed_amount == current_reservation.reserved_amount
                else "PARTIALLY_CONSUMED"
            )
        else:
            consumed_amount = current_reservation.consumed_amount
            consumed_quantity = current_reservation.consumed_quantity + fill.quantity
            status = (
                "CONSUMED"
                if consumed_quantity == current_reservation.reserved_quantity
                else "PARTIALLY_CONSUMED"
            )
        updated_reservation = PaperReservation.model_validate(
            current_reservation.model_copy(
                update={
                    "consumed_amount": consumed_amount,
                    "consumed_quantity": consumed_quantity,
                    "status": status,
                    "applied_settlement_ids": [
                        *current_reservation.applied_settlement_ids,
                        record.settlement_id,
                    ],
                    "updated_at": now,
                }
            ).model_dump(mode="python")
        )
        await self.reservations.replace_one(
            {"reservation_id": current_reservation.reservation_id},
            model_document(updated_reservation),
        )

    async def _apply_position(
        self,
        record: SettlementRecord,
        fill: PaperFill,
        reservation: PaperReservation,
        *,
        now: datetime,
    ) -> None:
        if fill.side == "BUY":
            raw = clean_document(
                await self.lots.find_one({"source_fill_id": fill.fill_id})
            )
            if raw is None:
                if record.acquired_available_from_date is None:
                    raise SettlementIntegrityError(
                        "BUY settlement lacks next trading date"
                    )
                lot = PositionLot(
                    lot_id=str(uuid5(NAMESPACE_URL, f"alphaguard:lot:{fill.fill_id}")),
                    account_id=fill.account_id,
                    symbol=fill.symbol,
                    market="CN",
                    source_fill_id=fill.fill_id,
                    acquired_trade_date=fill.trade_date,
                    original_quantity=fill.quantity,
                    remaining_quantity=fill.quantity,
                    reserved_quantity=0,
                    unit_cost=record.position_cost / fill.quantity,
                    total_cost=record.position_cost,
                    available_from_date=record.acquired_available_from_date,
                    status="OPEN",
                    applied_settlement_ids=[record.settlement_id],
                    created_at=now,
                    updated_at=now,
                )
                await self.lots.insert_one(model_document(lot))
                await self.audit.record(
                    "POSITION_LOT_CREATED",
                    "BUY settlement created a T+1 FIFO position lot",
                    account_id=fill.account_id,
                    order_id=fill.order_id,
                    fill_id=fill.fill_id,
                    settlement_id=record.settlement_id,
                    symbol=fill.symbol,
                    trade_date=fill.trade_date,
                    now=now,
                )
        else:
            for consumption in record.lot_consumptions:
                raw_lot = clean_document(
                    await self.lots.find_one({"lot_id": consumption["lot_id"]})
                )
                if raw_lot is None:
                    raise SettlementIntegrityError("FIFO lot disappeared")
                lot = PositionLot.model_validate(raw_lot)
                if record.settlement_id in lot.applied_settlement_ids:
                    continue
                quantity = int(consumption["quantity"])
                allocated = lot.reservation_allocations.get(
                    reservation.reservation_id,
                    0,
                )
                if allocated < quantity or lot.remaining_quantity < quantity:
                    raise SettlementIntegrityError(
                        "FIFO lot no longer covers settlement"
                    )
                remaining = lot.remaining_quantity - quantity
                allocations = dict(lot.reservation_allocations)
                left_reserved = allocated - quantity
                if left_reserved:
                    allocations[reservation.reservation_id] = left_reserved
                else:
                    allocations.pop(reservation.reservation_id, None)
                status = (
                    "CLOSED"
                    if remaining == 0
                    else "PARTIALLY_CLOSED"
                    if remaining < lot.original_quantity
                    else "OPEN"
                )
                updated_lot = PositionLot.model_validate(
                    lot.model_copy(
                        update={
                            "remaining_quantity": remaining,
                            "reserved_quantity": lot.reserved_quantity - quantity,
                            "reservation_allocations": allocations,
                            "total_cost": lot.unit_cost * remaining,
                            "status": status,
                            "applied_settlement_ids": [
                                *lot.applied_settlement_ids,
                                record.settlement_id,
                            ],
                            "updated_at": now,
                            "lot_version": lot.lot_version + 1,
                        }
                    ).model_dump(mode="python")
                )
                result = await self.lots.replace_one(
                    {"lot_id": lot.lot_id, "lot_version": lot.lot_version},
                    model_document(updated_lot),
                )
                if result.matched_count != 1:
                    raise SettlementIntegrityError(
                        "concurrent FIFO lot settlement conflict"
                    )
                await self.audit.record(
                    "POSITION_LOT_CONSUMED",
                    "SELL/REDUCE settlement consumed FIFO lot quantity",
                    account_id=fill.account_id,
                    order_id=fill.order_id,
                    fill_id=fill.fill_id,
                    settlement_id=record.settlement_id,
                    symbol=fill.symbol,
                    trade_date=fill.trade_date,
                    now=now,
                )
            current_reservation = await self.orders.reservation_for_order(fill.order_id)
            if current_reservation:
                allocations = []
                for allocation in current_reservation.lot_allocations:
                    raw_lot = clean_document(
                        await self.lots.find_one({"lot_id": allocation.lot_id})
                    )
                    remaining_frozen = 0
                    if raw_lot is not None:
                        remaining_frozen = int(
                            raw_lot.get("reservation_allocations", {}).get(
                                reservation.reservation_id,
                                0,
                            )
                        )
                    allocations.append(
                        allocation.model_copy(
                            update={
                                "consumed_quantity": (
                                    allocation.reserved_quantity
                                    - remaining_frozen
                                )
                            }
                        )
                    )
                updated_reservation = PaperReservation.model_validate(
                    current_reservation.model_copy(
                        update={"lot_allocations": allocations, "updated_at": now}
                    ).model_dump(mode="python")
                )
                await self.reservations.replace_one(
                    {"reservation_id": current_reservation.reservation_id},
                    model_document(updated_reservation),
                )
        position = await self.accounts.rebuild_position(
            fill.account_id,
            fill.symbol,
            as_of_date=fill.trade_date,
            now=now,
        )
        if record.settlement_id not in position.applied_settlement_ids:
            position = PaperPosition.model_validate(
                position.model_copy(
                    update={
                        "realized_pnl": (
                            position.realized_pnl + record.realized_pnl
                        ),
                        "total_fees": (
                            position.total_fees + fill.fee_breakdown.total_fee
                        ),
                        "applied_settlement_ids": [
                            *position.applied_settlement_ids,
                            record.settlement_id,
                        ],
                        "updated_at": now,
                    }
                ).model_dump(mode="python")
            )
            await self.positions.replace_one(
                {
                    "account_id": fill.account_id,
                    "market": "CN",
                    "symbol": fill.symbol,
                },
                model_document(position),
                upsert=True,
            )

    async def _apply_ledger(
        self,
        record: SettlementRecord,
        fill: PaperFill,
        *,
        now: datetime,
    ) -> None:
        specs = [
            ("CASH_CHANGE", fill.net_cash_effect),
            (
                "POSITION_COST_CHANGE",
                record.position_cost if fill.side == "BUY" else -record.position_cost,
            ),
            ("FEE_EXPENSE", -fill.fee_breakdown.total_fee),
        ]
        if fill.side == "SELL":
            specs.append(("REALIZED_PNL", record.realized_pnl))
        for entry_type, amount in specs:
            key = f"{record.settlement_id}:{entry_type}"
            if await self.ledger.find_one({"idempotency_key": key}):
                continue
            entry = LedgerEntry(
                ledger_entry_id=str(
                    uuid5(NAMESPACE_URL, f"alphaguard:ledger:{key}")
                ),
                settlement_id=record.settlement_id,
                fill_id=fill.fill_id,
                account_id=fill.account_id,
                entry_type=entry_type,
                amount=amount,
                currency="CNY",
                balance_before=None,
                balance_after=None,
                idempotency_key=key,
                created_at=now,
            )
            await self.ledger.insert_one(model_document(entry))

    async def _finalize_order(
        self,
        record: SettlementRecord,
        fill: PaperFill,
        *,
        now: datetime,
    ) -> None:
        order = await self.orders.get_order(fill.order_id)
        if order is None:
            raise SettlementIntegrityError("order disappeared during finalization")
        if order.status in {"FILLED", "PARTIALLY_FILLED"} and (
            order.filled_quantity >= fill.quantity
            and order.last_matched_trade_date == fill.trade_date
        ):
            return
        if order.status == "SETTLEMENT_FAILED":
            order = await self.orders.transition(
                order.order_id,
                "SETTLEMENT_PENDING",
                now=now,
            )
        if order.status != "SETTLEMENT_PENDING":
            raise SettlementIntegrityError(
                f"cannot finalize settlement from order status {order.status}"
            )
        new_filled = order.filled_quantity + fill.quantity
        remaining = order.requested_quantity - new_filled
        total_notional = order.total_notional + fill.notional
        average = total_notional / new_filled
        target = "FILLED" if remaining == 0 else "PARTIALLY_FILLED"
        reservation = await self.orders.reservation_for_order(order.order_id)
        remaining_cash = Decimal("0")
        if (
            remaining > 0
            and reservation is not None
            and reservation.reservation_type == "CASH"
        ):
            remaining_cash = (
                reservation.reserved_amount - reservation.consumed_amount
            )
        order = await self.orders.transition(
            order.order_id,
            target,
            now=now,
            filled_quantity=new_filled,
            remaining_quantity=remaining,
            reserved_quantity=remaining,
            average_fill_price=average,
            total_notional=total_notional,
            total_fees=order.total_fees + fill.fee_breakdown.total_fee,
            reserved_cash=remaining_cash,
            filled_at=now if remaining == 0 else None,
        )
        if remaining == 0:
            await self.orders.release_reservation(order.order_id, now=now)
        await self.audit.record(
            (
                "PAPER_ORDER_FILLED"
                if target == "FILLED"
                else "PAPER_ORDER_PARTIALLY_FILLED"
            ),
            "order state advanced only after settlement Saga COMMITTED",
            user_id=order.user_id,
            account_id=order.account_id,
            account_type=order.account_type,
            intent_id=order.intent_id,
            order_id=order.order_id,
            fill_id=fill.fill_id,
            settlement_id=record.settlement_id,
            symbol=order.symbol,
            trade_date=fill.trade_date,
            now=now,
        )

    async def _advance(
        self,
        record: SettlementRecord,
        status: str,
        *,
        now: datetime,
        **changes,
    ) -> SettlementRecord:
        changes.update(status=status, updated_at=now, last_error=None)
        updated = SettlementRecord.model_validate(
            record.model_copy(update=changes).model_dump(mode="python")
        )
        await self.records.replace_one(
            {"settlement_id": record.settlement_id},
            model_document(updated),
        )
        return updated

    async def _fill(self, fill_id: str) -> PaperFill:
        raw = clean_document(
            await self.db["ag_paper_fills"].find_one({"fill_id": fill_id})
        )
        if raw is None:
            raise LookupError("PaperFill not found")
        return PaperFill.model_validate(raw)
