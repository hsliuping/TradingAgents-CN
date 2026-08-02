"""Deterministic matching orchestration; creates immutable fills, not assets."""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

from app.services.alphaguard.fee_engine import FeeEngine
from app.services.alphaguard.matching_engine import MatchingEngine
from app.services.alphaguard.paper_audit_service import PaperAuditService
from app.services.alphaguard.paper_order_service import PaperOrderService
from app.services.alphaguard.paper_policy_registry import PaperPolicyRegistry
from app.services.alphaguard.paper_storage import (
    clean_document,
    model_document,
    mongo_date,
)
from tradingagents.alphaguard.paper_schemas import (
    ExecutionMarketSnapshot,
    PAPER_SCHEMA_VERSION,
    PaperFill,
    paper_canonical_hash,
)


class PaperExecutionService:
    def __init__(self, db):
        self.db = db
        self.fills = db["ag_paper_fills"]
        self.orders = PaperOrderService(db)
        self.policies = PaperPolicyRegistry(db)
        self.matcher = MatchingEngine()
        self.audit = PaperAuditService(db)

    async def match_order(
        self,
        order_id: str,
        execution_snapshot_id: str,
        *,
        matched_at: datetime | None = None,
    ) -> PaperFill | None:
        order = await self.orders.get_order(order_id)
        if order is None:
            raise LookupError("automatic PaperOrder not found")
        raw_snapshot = clean_document(
            await self.db["ag_execution_market_snapshots"].find_one(
                {"execution_snapshot_id": execution_snapshot_id}
            )
        )
        if raw_snapshot is None:
            raise LookupError("ExecutionMarketSnapshot not found")
        snapshot = ExecutionMarketSnapshot.model_validate(raw_snapshot)
        existing = clean_document(
            await self.fills.find_one(
                {
                    "order_id": order_id,
                    "trade_date": mongo_date(snapshot.trade_date),
                }
            )
        )
        if existing:
            return PaperFill.model_validate(existing)
        matched_at = matched_at or datetime.combine(snapshot.trade_date, time(15, 30))
        if order.last_matched_trade_date == snapshot.trade_date:
            return None
        reservation = await self.orders.reservation_for_order(order_id)
        if reservation is None or reservation.status == "RELEASED":
            raise ValueError("order has no active reservation")
        account = await self.orders.accounts.get_account(order.account_id)
        if account is None or account.status != "ACTIVE":
            await self.orders.touch(
                order_id,
                last_matched_trade_date=snapshot.trade_date,
                now=matched_at,
            )
            await self.audit.record(
                "MATCHING_BLOCKED",
                "automatic paper account is not active at execution recheck",
                user_id=order.user_id,
                account_id=order.account_id,
                account_type=order.account_type,
                intent_id=order.intent_id,
                order_id=order.order_id,
                symbol=order.symbol,
                trade_date=snapshot.trade_date,
                now=matched_at,
            )
            return None
        if reservation.reservation_type == "CASH":
            valid_reserved_quantity = order.remaining_quantity
            if account.cash_reserved <= 0:
                valid_reserved_quantity = 0
        else:
            valid_reserved_quantity = (
                reservation.reserved_quantity - reservation.consumed_quantity
            )
        execution_policy = await self.policies.execution_policy()
        result = self.matcher.match(
            order=order,
            snapshot=snapshot,
            policy=execution_policy,
            valid_reserved_quantity=valid_reserved_quantity,
            matched_at=matched_at,
        )
        if result.status in {"NO_FILL", "BLOCKED"}:
            await self.orders.touch(
                order_id,
                last_matched_trade_date=snapshot.trade_date,
                now=matched_at,
            )
            await self.audit.record(
                "MATCHING_BLOCKED" if result.status == "BLOCKED" else "MATCHING_NO_FILL",
                result.reason,
                user_id=order.user_id,
                account_id=order.account_id,
                account_type=order.account_type,
                intent_id=order.intent_id,
                order_id=order.order_id,
                symbol=order.symbol,
                trade_date=snapshot.trade_date,
                now=matched_at,
            )
            return None
        quantity = result.quantity
        assert result.price is not None
        fee_policy = await self.policies.fee_policy()
        fees = FeeEngine.calculate(
            side=order.side,
            notional=result.price * quantity,
            policy=fee_policy,
        )
        if reservation.reservation_type == "CASH":
            available_cash = (
                reservation.reserved_amount - reservation.consumed_amount
            )
            while quantity > 0:
                notional = result.price * quantity
                fees = FeeEngine.calculate(
                    side="BUY",
                    notional=notional,
                    policy=fee_policy,
                )
                if notional + fees.total_fee <= available_cash:
                    break
                quantity -= execution_policy.cn_buy_lot_size
            if quantity <= 0:
                await self.orders.touch(
                    order_id,
                    last_matched_trade_date=snapshot.trade_date,
                    now=matched_at,
                )
                await self.audit.record(
                    "MATCHING_BLOCKED",
                    "cash reservation is insufficient for any lot-rounded fill",
                    user_id=order.user_id,
                    account_id=order.account_id,
                    account_type=order.account_type,
                    intent_id=order.intent_id,
                    order_id=order.order_id,
                    symbol=order.symbol,
                    trade_date=snapshot.trade_date,
                    now=matched_at,
                )
                return None
        notional = result.price * quantity
        net_effect = (
            -(notional + fees.total_fee)
            if order.side == "BUY"
            else notional - fees.total_fee
        )
        key = f"{order.order_id}:{snapshot.trade_date.isoformat()}"
        payload = {
            "fill_id": str(uuid5(NAMESPACE_URL, f"alphaguard:paper-fill:{key}")),
            "order_id": order.order_id,
            "intent_id": order.intent_id,
            "account_id": order.account_id,
            "snapshot_id": order.snapshot_id,
            "experiment_id": order.experiment_id,
            "assignment_id": order.assignment_id,
            "challenger_version_id": order.challenger_version_id,
            "baseline_champion_id": order.baseline_champion_id,
            "config_hash": order.config_hash,
            "run_mode": order.run_mode,
            "execution_snapshot_id": snapshot.execution_snapshot_id,
            "trade_date": snapshot.trade_date,
            "execution_time_policy": "AFTER_MARKET_CLOSE_DAILY_OHLCV_V1",
            "symbol": order.symbol,
            "market": "CN",
            "side": order.side,
            "quantity": quantity,
            "price": result.price,
            "notional": notional,
            "fee_breakdown": fees,
            "net_cash_effect": net_effect,
            "matching_engine_version": self.matcher.version,
            "fee_policy_version": fee_policy.version,
            "idempotency_key": key,
            "created_at": matched_at,
            "schema_version": PAPER_SCHEMA_VERSION,
            "execution_environment": "PAPER",
            "live_execution_allowed": False,
        }
        hash_excludes = {"fill_id", "immutable_hash", "created_at"}
        if payload["run_mode"] is None:
            hash_excludes.update(
                {
                    "snapshot_id",
                    "experiment_id",
                    "assignment_id",
                    "challenger_version_id",
                    "baseline_champion_id",
                    "config_hash",
                    "run_mode",
                }
            )
        payload["immutable_hash"] = paper_canonical_hash(
            payload,
            exclude=hash_excludes,
        )
        fill = PaperFill.model_validate(payload)
        await self.fills.insert_one(model_document(fill))
        await self.orders.transition(
            order.order_id,
            "SETTLEMENT_PENDING",
            now=matched_at,
            last_matched_trade_date=snapshot.trade_date,
        )
        await self.audit.record(
            (
                "MATCHING_FULL_FILL"
                if quantity == order.remaining_quantity
                else "MATCHING_PARTIAL_FILL"
            ),
            "immutable PaperFill created; settlement is still pending",
            user_id=order.user_id,
            account_id=order.account_id,
            account_type=order.account_type,
            intent_id=order.intent_id,
            order_id=order.order_id,
            fill_id=fill.fill_id,
            symbol=order.symbol,
            trade_date=snapshot.trade_date,
            now=matched_at,
        )
        return fill
