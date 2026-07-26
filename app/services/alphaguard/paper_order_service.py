"""Central PaperOrder state machine and idempotent reservation management."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

from app.services.alphaguard.fee_engine import FeeEngine
from app.services.alphaguard.paper_account_service import PaperAccountService
from app.services.alphaguard.paper_audit_service import PaperAuditService
from app.services.alphaguard.paper_policy_registry import PaperPolicyRegistry
from app.services.alphaguard.paper_storage import clean_document, model_document
from tradingagents.alphaguard.paper_schemas import (
    LotAllocation,
    OrderIntent,
    PaperAccount,
    PaperOrder,
    PaperReservation,
    PositionLot,
)


TERMINAL_ORDER_STATUSES = {
    "FILLED",
    "CANCELLED",
    "REJECTED",
    "EXPIRED",
}
ORDER_TRANSITIONS = {
    "CREATED": {"RESERVED", "CANCELLED", "REJECTED", "EXPIRED"},
    "RESERVED": {"SUBMITTED", "CANCELLED", "REJECTED", "EXPIRED"},
    "SUBMITTED": {"PENDING", "CANCELLED", "REJECTED", "EXPIRED"},
    "PENDING": {
        "SETTLEMENT_PENDING",
        "CANCELLED",
        "REJECTED",
        "EXPIRED",
    },
    "PARTIALLY_FILLED": {
        "SETTLEMENT_PENDING",
        "CANCELLED",
        "REJECTED",
        "EXPIRED",
    },
    "SETTLEMENT_PENDING": {
        "PARTIALLY_FILLED",
        "FILLED",
        "SETTLEMENT_FAILED",
    },
    "SETTLEMENT_FAILED": {"SETTLEMENT_PENDING", "REJECTED"},
    "FILLED": set(),
    "CANCELLED": set(),
    "REJECTED": set(),
    "EXPIRED": set(),
}


class PaperOrderStateError(ValueError):
    pass


class ReservationError(ValueError):
    pass


class ReservationConflictError(RuntimeError):
    pass


class PaperOrderService:
    def __init__(self, db):
        self.db = db
        self.orders = db["ag_paper_orders"]
        self.reservations = db["ag_paper_reservations"]
        self.lots = db["ag_paper_position_lots"]
        self.accounts = PaperAccountService(db)
        self.policies = PaperPolicyRegistry(db)
        self.audit = PaperAuditService(db)

    async def get_order(self, order_id: str) -> PaperOrder | None:
        document = clean_document(
            await self.orders.find_one({"order_id": order_id})
        )
        return PaperOrder.model_validate(document) if document else None

    async def create_from_intent(
        self,
        intent: OrderIntent,
        *,
        now: datetime | None = None,
    ) -> PaperOrder:
        existing = clean_document(
            await self.orders.find_one({"intent_id": intent.intent_id})
        )
        if existing:
            return PaperOrder.model_validate(existing)
        current_hash = await self.accounts.account_state_hash(intent.account_id)
        if current_hash != intent.account_state_snapshot_id:
            raise ReservationConflictError(
                "automatic account changed after OrderIntent creation"
            )
        now = now or datetime.utcnow()
        order = PaperOrder(
            order_id=str(
                uuid5(NAMESPACE_URL, f"alphaguard:paper-order:{intent.intent_id}")
            ),
            intent_id=intent.intent_id,
            account_id=intent.account_id,
            user_id=intent.user_id,
            account_type=intent.account_type,
            candidate_id=intent.candidate_id,
            source_type=intent.source_type,
            source_object_id=intent.source_object_id,
            risk_decision_id=intent.risk_decision_id,
            experiment_id=intent.experiment_id,
            assignment_id=intent.assignment_id,
            symbol=intent.symbol,
            market="CN",
            currency="CNY",
            side=intent.side,
            original_action=intent.original_action,
            order_type=intent.order_type,
            requested_quantity=intent.quantity,
            reserved_quantity=0,
            filled_quantity=0,
            remaining_quantity=intent.quantity,
            limit_price=intent.limit_price,
            reserved_cash=Decimal("0"),
            total_notional=Decimal("0"),
            total_fees=Decimal("0"),
            status="CREATED",
            trade_date=intent.earliest_execute_at.date(),
            earliest_execute_at=intent.earliest_execute_at,
            expires_at=intent.expires_at,
            created_at=now,
            updated_at=now,
        )
        await self.orders.insert_one(model_document(order))
        await self.audit.record(
            "PAPER_ORDER_CREATED",
            "PaperOrder created from immutable internal OrderIntent",
            user_id=order.user_id,
            account_id=order.account_id,
            account_type=order.account_type,
            intent_id=order.intent_id,
            order_id=order.order_id,
            symbol=order.symbol,
            trade_date=order.trade_date,
            source_type=order.source_type,
            source_object_id=order.source_object_id,
            risk_decision_id=order.risk_decision_id,
            now=now,
        )
        return order

    async def create_reserve_submit(
        self,
        intent: OrderIntent,
        *,
        now: datetime | None = None,
    ) -> PaperOrder:
        order = await self.create_from_intent(intent, now=now)
        if order.status == "CREATED":
            try:
                order = await self.reserve(order.order_id, now=now)
            except Exception as exc:
                await self.reject(
                    order.order_id,
                    reason=f"reservation failed: {type(exc).__name__}: {str(exc)[:300]}",
                    now=now,
                )
                raise
        if order.status == "RESERVED":
            order = await self.transition(
                order.order_id,
                "SUBMITTED",
                now=now,
                submitted_at=now or datetime.utcnow(),
            )
            await self.audit.record(
                "PAPER_ORDER_SUBMITTED",
                "reserved automatic PaperOrder submitted to paper matcher",
                user_id=order.user_id,
                account_id=order.account_id,
                account_type=order.account_type,
                intent_id=order.intent_id,
                order_id=order.order_id,
                symbol=order.symbol,
                trade_date=order.trade_date,
                now=now,
            )
        if order.status == "SUBMITTED":
            order = await self.transition(order.order_id, "PENDING", now=now)
            await self.audit.record(
                "PAPER_ORDER_PENDING",
                "automatic PaperOrder awaits exact-date execution snapshot",
                user_id=order.user_id,
                account_id=order.account_id,
                account_type=order.account_type,
                intent_id=order.intent_id,
                order_id=order.order_id,
                symbol=order.symbol,
                trade_date=order.trade_date,
                now=now,
            )
        return order

    async def reserve(
        self,
        order_id: str,
        *,
        now: datetime | None = None,
    ) -> PaperOrder:
        order = await self._require_order(order_id)
        if order.status != "CREATED":
            if order.status in {"RESERVED", "SUBMITTED", "PENDING", "PARTIALLY_FILLED"}:
                return order
            raise PaperOrderStateError(f"cannot reserve order in {order.status}")
        account = await self.accounts.get_account(order.account_id)
        if account is None or account.status != "ACTIVE":
            raise ReservationError("automatic paper account is not active")
        now = now or datetime.utcnow()
        if order.side == "BUY":
            if order.limit_price is None:
                raise ReservationError("BUY reservation lacks a reliable limit price")
            fee_policy = await self.policies.fee_policy()
            required, _ = FeeEngine.conservative_reserve(
                quantity=order.remaining_quantity,
                price=order.limit_price,
                policy=fee_policy,
            )
            reservation = await self._cash_reservation(
                order=order,
                account=account,
                amount=required,
                now=now,
            )
            order = await self.transition(
                order_id,
                "RESERVED",
                now=now,
                reserved_quantity=order.remaining_quantity,
                reserved_cash=reservation.reserved_amount,
            )
            event_type = "CASH_RESERVED"
            reason = "BUY cash reserved using limit price and conservative fees"
        else:
            reservation = await self._position_reservation(
                order=order,
                now=now,
            )
            order = await self.transition(
                order_id,
                "RESERVED",
                now=now,
                reserved_quantity=reservation.reserved_quantity,
            )
            event_type = "POSITION_RESERVED"
            reason = "SELL/REDUCE quantity reserved from T+1-available FIFO lots"
        await self.audit.record(
            event_type,
            reason,
            user_id=order.user_id,
            account_id=order.account_id,
            account_type=order.account_type,
            intent_id=order.intent_id,
            order_id=order.order_id,
            symbol=order.symbol,
            trade_date=order.trade_date,
            now=now,
        )
        await self.audit.record(
            "PAPER_ORDER_RESERVED",
            "automatic PaperOrder reservation completed",
            user_id=order.user_id,
            account_id=order.account_id,
            account_type=order.account_type,
            intent_id=order.intent_id,
            order_id=order.order_id,
            symbol=order.symbol,
            trade_date=order.trade_date,
            now=now,
        )
        return order

    async def _cash_reservation(
        self,
        *,
        order: PaperOrder,
        account: PaperAccount,
        amount: Decimal,
        now: datetime,
    ) -> PaperReservation:
        reservation_id = str(
            uuid5(NAMESPACE_URL, f"alphaguard:cash-reservation:{order.order_id}")
        )
        existing = clean_document(
            await self.reservations.find_one(
                {"idempotency_key": f"cash:{order.order_id}"}
            )
        )
        reservation = (
            PaperReservation.model_validate(existing)
            if existing
            else PaperReservation(
                reservation_id=reservation_id,
                order_id=order.order_id,
                account_id=order.account_id,
                reservation_type="CASH",
                currency="CNY",
                reserved_amount=amount,
                reserved_quantity=None,
                idempotency_key=f"cash:{order.order_id}",
                created_at=now,
                updated_at=now,
            )
        )
        if existing and reservation.reserved_amount != amount:
            raise ReservationConflictError("cash reservation content changed")
        if not existing:
            await self.reservations.insert_one(model_document(reservation))
        if reservation.reservation_id in account.applied_reservation_ids:
            return reservation
        if account.cash_available < amount:
            raise ReservationError("automatic paper account has insufficient cash")
        updated = PaperAccount.model_validate(
            account.model_copy(
                update={
                    "cash_available": account.cash_available - amount,
                    "cash_reserved": account.cash_reserved + amount,
                    "applied_reservation_ids": [
                        *account.applied_reservation_ids,
                        reservation.reservation_id,
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
                or reservation.reservation_id not in current.applied_reservation_ids
            ):
                raise ReservationConflictError(
                    "concurrent cash reservation conflict"
                )
        return reservation

    async def _position_reservation(
        self,
        *,
        order: PaperOrder,
        now: datetime,
    ) -> PaperReservation:
        reservation_id = str(
            uuid5(NAMESPACE_URL, f"alphaguard:position-reservation:{order.order_id}")
        )
        existing = clean_document(
            await self.reservations.find_one(
                {"idempotency_key": f"position:{order.order_id}"}
            )
        )
        if existing:
            reservation = PaperReservation.model_validate(existing)
        else:
            raw_lots = await self.lots.find(
                {
                    "account_id": order.account_id,
                    "symbol": order.symbol,
                    "status": {"$in": ["OPEN", "PARTIALLY_CLOSED"]},
                }
            ).sort(
                [("acquired_trade_date", 1), ("created_at", 1), ("lot_id", 1)]
            ).to_list(length=None)
            remaining = order.remaining_quantity
            allocations: list[LotAllocation] = []
            for raw in raw_lots:
                lot = PositionLot.model_validate(clean_document(raw))
                if lot.available_from_date > order.trade_date:
                    continue
                usable = lot.remaining_quantity - lot.reserved_quantity
                take = min(remaining, max(0, usable))
                if take:
                    allocations.append(
                        LotAllocation(lot_id=lot.lot_id, reserved_quantity=take)
                    )
                    remaining -= take
                if remaining == 0:
                    break
            if remaining:
                raise ReservationError(
                    "T+1-available position is insufficient for SELL/REDUCE"
                )
            reservation = PaperReservation(
                reservation_id=reservation_id,
                order_id=order.order_id,
                account_id=order.account_id,
                reservation_type="POSITION",
                symbol=order.symbol,
                lot_allocations=allocations,
                reserved_quantity=order.remaining_quantity,
                idempotency_key=f"position:{order.order_id}",
                created_at=now,
                updated_at=now,
            )
            await self.reservations.insert_one(model_document(reservation))
        for allocation in reservation.lot_allocations:
            raw = clean_document(
                await self.lots.find_one({"lot_id": allocation.lot_id})
            )
            if raw is None:
                raise ReservationConflictError("reserved lot disappeared")
            lot = PositionLot.model_validate(raw)
            if reservation.reservation_id in lot.reservation_allocations:
                if (
                    lot.reservation_allocations[reservation.reservation_id]
                    != allocation.reserved_quantity
                ):
                    raise ReservationConflictError(
                        "same reservation has conflicting lot allocation"
                    )
                continue
            usable = lot.remaining_quantity - lot.reserved_quantity
            if usable < allocation.reserved_quantity:
                raise ReservationConflictError(
                    "concurrent position reservation exhausted a lot"
                )
            allocations = dict(lot.reservation_allocations)
            allocations[reservation.reservation_id] = allocation.reserved_quantity
            updated = PositionLot.model_validate(
                lot.model_copy(
                    update={
                        "reserved_quantity": (
                            lot.reserved_quantity + allocation.reserved_quantity
                        ),
                        "reservation_allocations": allocations,
                        "updated_at": now,
                        "lot_version": lot.lot_version + 1,
                    }
                ).model_dump(mode="python")
            )
            result = await self.lots.replace_one(
                {"lot_id": lot.lot_id, "lot_version": lot.lot_version},
                model_document(updated),
            )
            if result.matched_count != 1:
                raise ReservationConflictError(
                    "concurrent lot reservation conflict"
                )
        await self.accounts.rebuild_position(
            order.account_id,
            order.symbol,
            as_of_date=order.trade_date,
            now=now,
        )
        return reservation

    async def transition(
        self,
        order_id: str,
        target: str,
        *,
        now: datetime | None = None,
        **changes,
    ) -> PaperOrder:
        current = await self._require_order(order_id)
        if current.status == target:
            return current
        if target not in ORDER_TRANSITIONS.get(current.status, set()):
            raise PaperOrderStateError(
                f"order transition {current.status} -> {target} is not allowed"
            )
        now = now or datetime.utcnow()
        changes.update(
            status=target,
            updated_at=now,
            order_version=current.order_version + 1,
        )
        updated = PaperOrder.model_validate(
            current.model_copy(update=changes).model_dump(mode="python")
        )
        result = await self.orders.replace_one(
            {"order_id": order_id, "order_version": current.order_version},
            model_document(updated),
        )
        if result.matched_count != 1:
            latest = await self._require_order(order_id)
            if latest.status == target:
                return latest
            raise PaperOrderStateError("concurrent PaperOrder transition conflict")
        return updated

    async def touch(
        self,
        order_id: str,
        *,
        now: datetime | None = None,
        **changes,
    ) -> PaperOrder:
        current = await self._require_order(order_id)
        if current.status in TERMINAL_ORDER_STATUSES:
            return current
        now = now or datetime.utcnow()
        changes.update(
            updated_at=now,
            order_version=current.order_version + 1,
        )
        updated = PaperOrder.model_validate(
            current.model_copy(update=changes).model_dump(mode="python")
        )
        result = await self.orders.replace_one(
            {"order_id": order_id, "order_version": current.order_version},
            model_document(updated),
        )
        if result.matched_count != 1:
            raise PaperOrderStateError("concurrent PaperOrder update conflict")
        return updated

    async def reject(
        self,
        order_id: str,
        *,
        reason: str,
        now: datetime | None = None,
    ) -> PaperOrder:
        order = await self._require_order(order_id)
        if order.status in TERMINAL_ORDER_STATUSES:
            return order
        if order.status not in {"CREATED", "RESERVED", "SUBMITTED", "PENDING", "PARTIALLY_FILLED"}:
            raise PaperOrderStateError(f"cannot reject order in {order.status}")
        if await self.reservation_for_order(order_id) is not None:
            await self.release_reservation(order_id, now=now)
            order = await self._require_order(order_id)
        order = await self.transition(
            order_id,
            "REJECTED",
            now=now,
            reject_reason=reason[:500],
        )
        await self.audit.record(
            "PAPER_ORDER_REJECTED",
            reason[:500],
            user_id=order.user_id,
            account_id=order.account_id,
            account_type=order.account_type,
            intent_id=order.intent_id,
            order_id=order.order_id,
            symbol=order.symbol,
            trade_date=order.trade_date,
            now=now,
        )
        return order

    async def cancel(
        self,
        order_id: str,
        *,
        user_id: str,
        now: datetime | None = None,
    ) -> PaperOrder:
        order = await self._require_order(order_id)
        if order.user_id != str(user_id):
            raise LookupError("automatic paper order not found")
        if order.status == "CANCELLED":
            return order
        if order.status not in {
            "CREATED",
            "RESERVED",
            "SUBMITTED",
            "PENDING",
            "PARTIALLY_FILLED",
        }:
            raise PaperOrderStateError(f"cannot cancel order in {order.status}")
        await self.release_reservation(order_id, now=now)
        order = await self.transition(
            order_id,
            "CANCELLED",
            now=now,
            cancelled_at=now or datetime.utcnow(),
        )
        await self.audit.record(
            "PAPER_ORDER_CANCELLED",
            "user cancelled the unfilled remainder; completed fills are retained",
            user_id=order.user_id,
            account_id=order.account_id,
            account_type=order.account_type,
            intent_id=order.intent_id,
            order_id=order.order_id,
            symbol=order.symbol,
            trade_date=order.trade_date,
            now=now,
        )
        return order

    async def expire(
        self,
        order_id: str,
        *,
        now: datetime | None = None,
    ) -> PaperOrder:
        now = now or datetime.utcnow()
        order = await self._require_order(order_id)
        if order.status == "EXPIRED":
            return order
        if order.status not in {
            "CREATED",
            "RESERVED",
            "SUBMITTED",
            "PENDING",
            "PARTIALLY_FILLED",
        }:
            return order
        if now <= order.expires_at or order.remaining_quantity <= 0:
            return order
        await self.release_reservation(order_id, now=now)
        order = await self.transition(order_id, "EXPIRED", now=now)
        await self.audit.record(
            "PAPER_ORDER_EXPIRED",
            "persisted execution validity window expired",
            user_id=order.user_id,
            account_id=order.account_id,
            account_type=order.account_type,
            intent_id=order.intent_id,
            order_id=order.order_id,
            symbol=order.symbol,
            trade_date=order.trade_date,
            now=now,
        )
        return order

    async def release_reservation(
        self,
        order_id: str,
        *,
        now: datetime | None = None,
    ) -> PaperReservation | None:
        now = now or datetime.utcnow()
        raw = clean_document(
            await self.reservations.find_one({"order_id": order_id})
        )
        if raw is None:
            return None
        reservation = PaperReservation.model_validate(raw)
        if reservation.status == "RELEASED":
            return reservation
        if reservation.reservation_type == "CASH":
            remaining = reservation.reserved_amount - reservation.consumed_amount
            account = await self.accounts.get_account(reservation.account_id)
            if account is None:
                raise ReservationConflictError("reservation account disappeared")
            if reservation.reservation_id not in account.applied_reservation_ids:
                # Reservation journal was created, but the guarded account move
                # never happened (for example insufficient cash). Nothing is
                # released from balances; the journal is simply closed.
                pass
            elif reservation.reservation_id not in account.released_reservation_ids:
                if account.cash_reserved < remaining:
                    raise ReservationConflictError(
                        "cash_reserved is below the release amount"
                    )
                updated = PaperAccount.model_validate(
                    account.model_copy(
                        update={
                            "cash_reserved": account.cash_reserved - remaining,
                            "cash_available": account.cash_available + remaining,
                            "released_reservation_ids": [
                                *account.released_reservation_ids,
                                reservation.reservation_id,
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
                    raise ReservationConflictError(
                        "concurrent cash release conflict"
                    )
            event_type = "CASH_RELEASED"
        else:
            for allocation in reservation.lot_allocations:
                raw_lot = clean_document(
                    await self.lots.find_one({"lot_id": allocation.lot_id})
                )
                if raw_lot is None:
                    raise ReservationConflictError("reserved lot disappeared")
                lot = PositionLot.model_validate(raw_lot)
                allocated = lot.reservation_allocations.get(
                    reservation.reservation_id,
                    0,
                )
                if allocated == 0:
                    continue
                # The lot allocation map stores only the still-frozen remainder;
                # already consumed quantity was removed during settlement.
                release = allocated
                allocations = dict(lot.reservation_allocations)
                allocations.pop(reservation.reservation_id, None)
                updated = PositionLot.model_validate(
                    lot.model_copy(
                        update={
                            "reserved_quantity": lot.reserved_quantity - release,
                            "reservation_allocations": allocations,
                            "updated_at": now,
                            "lot_version": lot.lot_version + 1,
                        }
                    ).model_dump(mode="python")
                )
                result = await self.lots.replace_one(
                    {"lot_id": lot.lot_id, "lot_version": lot.lot_version},
                    model_document(updated),
                )
                if result.matched_count != 1:
                    raise ReservationConflictError(
                        "concurrent position release conflict"
                    )
            order = await self._require_order(order_id)
            await self.accounts.rebuild_position(
                reservation.account_id,
                order.symbol,
                as_of_date=order.trade_date,
                now=now,
            )
            event_type = "POSITION_RELEASED"
        released = PaperReservation.model_validate(
            reservation.model_copy(
                update={"status": "RELEASED", "updated_at": now}
            ).model_dump(mode="python")
        )
        await self.reservations.replace_one(
            {"reservation_id": reservation.reservation_id},
            model_document(released),
        )
        order = await self._require_order(order_id)
        await self.audit.record(
            event_type,
            "unconsumed automatic order reservation released",
            user_id=order.user_id,
            account_id=order.account_id,
            account_type=order.account_type,
            intent_id=order.intent_id,
            order_id=order.order_id,
            symbol=order.symbol,
            trade_date=order.trade_date,
            now=now,
        )
        return released

    async def reservation_for_order(
        self,
        order_id: str,
    ) -> PaperReservation | None:
        document = clean_document(
            await self.reservations.find_one({"order_id": order_id})
        )
        return PaperReservation.model_validate(document) if document else None

    async def _require_order(self, order_id: str) -> PaperOrder:
        order = await self.get_order(order_id)
        if order is None:
            raise LookupError("automatic PaperOrder not found")
        return order
