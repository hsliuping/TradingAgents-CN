from datetime import date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.services.alphaguard.execution_market_snapshot_service import (
    ExecutionMarketSnapshotService,
)
from app.services.alphaguard.paper_account_service import PaperAccountService
from app.services.alphaguard.paper_execution_service import PaperExecutionService
from app.services.alphaguard.paper_order_service import (
    PaperOrderService,
    ReservationError,
)
from app.services.alphaguard.paper_storage import clean_document
from app.services.alphaguard.settlement_service import SettlementService
from tests.unit.alphaguard._fakes import FakeDB
from tests.unit.alphaguard.pr006_helpers import (
    daily_record,
    make_intent,
    setup_paper,
)
from tradingagents.alphaguard.paper_schemas import (
    OrderIntent,
    PaperAccount,
    PaperPosition,
    PositionLot,
)


def run(coro):
    import asyncio

    return asyncio.run(coro)


def test_four_accounts_are_idempotent_isolated_and_not_reset():
    async def scenario():
        db = FakeDB()
        first = await setup_paper(db, user_id="u1")
        assert set(first) == {
            "PAPER_QUANT",
            "PAPER_NORMAL",
            "PAPER_TOP_CONFIRMED",
            "PAPER_CHALLENGER",
        }
        quant = first["PAPER_QUANT"]
        changed = quant.model_copy(
            update={
                "cash_available": Decimal("900000"),
                "updated_at": datetime(2026, 7, 1, 9),
                "account_version": 2,
            }
        )
        await db["ag_paper_accounts"].replace_one(
            {"account_id": quant.account_id},
            changed.model_dump(mode="python"),
        )
        second = await PaperAccountService(db).initialize_user_accounts(
            "u1",
            now=datetime(2026, 7, 1, 10),
        )
        assert second["PAPER_QUANT"].cash_available == Decimal("900000")
        other = await PaperAccountService(db).initialize_user_accounts("u2")
        assert set(item.account_id for item in first.values()).isdisjoint(
            item.account_id for item in other.values()
        )
        assert db["paper_accounts"].count() == 0
        assert db["paper_positions"].count() == 0
        assert db["paper_orders"].count() == 0
        assert db["paper_trades"].count() == 0

    run(scenario())


def test_challenger_intent_is_rejected_by_schema():
    async def scenario():
        db = FakeDB()
        accounts = await setup_paper(db)
        with pytest.raises(ValidationError):
            await make_intent(
                db,
                accounts["PAPER_CHALLENGER"],
                source_type="CHALLENGER",
            )

    run(scenario())


def test_order_intent_hash_tampering_is_rejected():
    async def scenario():
        db = FakeDB()
        account = (await setup_paper(db))["PAPER_QUANT"]
        intent = await make_intent(db, account)
        tampered = intent.model_dump(mode="python")
        tampered["quantity"] = intent.quantity + 100
        with pytest.raises(ValidationError):
            OrderIntent.model_validate(tampered)

    run(scenario())


def test_buy_reservation_is_decimal_idempotent_and_cancel_releases():
    async def scenario():
        db = FakeDB()
        account = (await setup_paper(db))["PAPER_QUANT"]
        intent = await make_intent(db, account)
        service = PaperOrderService(db)
        order = await service.create_from_intent(intent)
        reserved = await service.reserve(order.order_id)
        again = await service.reserve(order.order_id)
        assert reserved == again
        current = await PaperAccountService(db).get_account(account.account_id)
        assert current.cash_available < account.cash_available
        assert current.cash_reserved > 0
        cancelled = await service.cancel(order.order_id, user_id=account.user_id)
        assert cancelled.status == "CANCELLED"
        restored = await PaperAccountService(db).get_account(account.account_id)
        assert restored.cash_available == account.initial_cash
        assert restored.cash_reserved == Decimal("0")
        repeated = await service.cancel(order.order_id, user_id=account.user_id)
        assert repeated.status == "CANCELLED"
        assert (await PaperAccountService(db).get_account(account.account_id)) == restored

    run(scenario())


def test_buy_cash_shortage_rejects_without_negative_cash():
    async def scenario():
        db = FakeDB()
        account = (await setup_paper(db))["PAPER_QUANT"]
        intent = await make_intent(
            db,
            account,
            quantity=200_000,
            limit_price=Decimal("10"),
        )
        service = PaperOrderService(db)
        order = await service.create_from_intent(intent)
        with pytest.raises(ReservationError):
            await service.reserve(order.order_id)
        current = await PaperAccountService(db).get_account(account.account_id)
        assert current.cash_available >= 0
        assert current.cash_reserved >= 0

    run(scenario())


async def _buy_and_settle(db, *, quantity=1000, volume=1_000_000):
    account = (await setup_paper(db))["PAPER_QUANT"]
    intent = await make_intent(db, account, quantity=quantity)
    order_service = PaperOrderService(db)
    order = await order_service.create_reserve_submit(intent)
    snapshot = await ExecutionMarketSnapshotService(db).create_from_daily_record(
        record=daily_record(volume=volume),
        symbol="600519",
        trade_date=date(2026, 7, 2),
        cutoff_at=datetime(2026, 7, 2, 15, 30),
        data_version="fixed-v1",
    )
    fill = await PaperExecutionService(db).match_order(
        order.order_id,
        snapshot.execution_snapshot_id,
        matched_at=datetime(2026, 7, 2, 15, 30),
    )
    assert fill is not None
    settlement = await SettlementService(db).settle_fill(
        fill.fill_id,
        now=datetime(2026, 7, 2, 16),
    )
    return account, intent, fill, settlement


def test_buy_settlement_creates_t1_lot_position_ledger_and_commits():
    async def scenario():
        db = FakeDB()
        original, _, fill, settlement = await _buy_and_settle(db)
        assert settlement.status == "COMMITTED"
        order = await PaperOrderService(db).get_order(fill.order_id)
        assert order.status == "FILLED"
        account = await PaperAccountService(db).get_account(original.account_id)
        assert account.cash_reserved == Decimal("0")
        assert account.cash_available == original.initial_cash + fill.net_cash_effect
        marked_equity = account.cash_available + fill.notional
        assert marked_equity == original.initial_cash - fill.fee_breakdown.total_fee
        raw_lot = clean_document(
            await db["ag_paper_position_lots"].find_one(
                {"source_fill_id": fill.fill_id}
            )
        )
        lot = PositionLot.model_validate(raw_lot)
        assert lot.available_from_date == date(2026, 7, 3)
        position = PaperPosition.model_validate(
            clean_document(
                await db["ag_paper_positions"].find_one(
                    {"account_id": original.account_id, "symbol": "600519"}
                )
            )
        )
        assert position.quantity == fill.quantity
        assert position.available_quantity == 0
        assert db["ag_paper_ledger_entries"].count() == 3
        assert db["paper_accounts"].count() == 0
        assert db["paper_positions"].count() == 0
        assert db["paper_orders"].count() == 0
        assert db["paper_trades"].count() == 0

    run(scenario())


def test_failed_settlement_is_not_filled_and_recovers_exactly_once():
    async def scenario():
        db = FakeDB()
        original = (await setup_paper(db))["PAPER_QUANT"]
        intent = await make_intent(db, original)
        order = await PaperOrderService(db).create_reserve_submit(intent)
        snapshot = await ExecutionMarketSnapshotService(db).create_from_daily_record(
            record=daily_record(),
            symbol="600519",
            trade_date=date(2026, 7, 2),
            cutoff_at=datetime(2026, 7, 2, 15, 30),
            data_version="fixed-v1",
        )
        fill = await PaperExecutionService(db).match_order(
            order.order_id,
            snapshot.execution_snapshot_id,
            matched_at=datetime(2026, 7, 2, 15, 30),
        )
        service = SettlementService(db)
        original_apply_position = service._apply_position
        failed_once = False

        async def fail_position(*args, **kwargs):
            nonlocal failed_once
            if not failed_once:
                failed_once = True
                raise RuntimeError("fixed crash after account stage")
            return await original_apply_position(*args, **kwargs)

        service._apply_position = fail_position
        with pytest.raises(RuntimeError):
            await service.settle_fill(fill.fill_id, now=datetime(2026, 7, 2, 16))
        failed_order = await PaperOrderService(db).get_order(order.order_id)
        assert failed_order.status == "SETTLEMENT_FAILED"
        assert failed_order.filled_quantity == 0
        failed_record = clean_document(
            await db["ag_settlement_records"].find_one({"fill_id": fill.fill_id})
        )
        assert failed_record["status"] == "FAILED"
        account_after_failure = await PaperAccountService(db).get_account(
            original.account_id
        )

        recovered = await service.recover(
            failed_record["settlement_id"],
            now=datetime(2026, 7, 2, 16, 1),
        )
        assert recovered.status == "COMMITTED"
        recovered_order = await PaperOrderService(db).get_order(order.order_id)
        assert recovered_order.status == "FILLED"
        assert recovered_order.filled_quantity == fill.quantity
        account_after_recovery = await PaperAccountService(db).get_account(
            original.account_id
        )
        assert (
            account_after_recovery.cash_available
            + account_after_recovery.cash_reserved
            == account_after_failure.cash_available
            + account_after_failure.cash_reserved
        )
        assert account_after_recovery.cash_reserved == 0
        for field in ("realized_pnl", "total_fees"):
            assert getattr(account_after_recovery, field) == getattr(
                account_after_failure,
                field,
            )
        assert (
            account_after_recovery.applied_settlement_ids.count(
                recovered.settlement_id
            )
            == 1
        )
        assert db["ag_paper_position_lots"].count() == 1
        assert db["ag_paper_ledger_entries"].count() == 3

    run(scenario())


def test_duplicate_matching_and_settlement_do_not_change_assets_twice():
    async def scenario():
        db = FakeDB()
        original, _, fill, first = await _buy_and_settle(db)
        account_after = await PaperAccountService(db).get_account(original.account_id)
        second = await SettlementService(db).settle_fill(fill.fill_id)
        account_repeated = await PaperAccountService(db).get_account(original.account_id)
        assert first.settlement_id == second.settlement_id
        assert account_repeated == account_after
        assert db["ag_paper_position_lots"].count() == 1
        assert db["ag_paper_ledger_entries"].count() == 3
        matched_again = await PaperExecutionService(db).match_order(
            fill.order_id,
            fill.execution_snapshot_id,
            matched_at=datetime(2026, 7, 2, 15, 30),
        )
        assert matched_again.fill_id == fill.fill_id

    run(scenario())


def test_partial_fill_retains_only_remaining_reservation():
    async def scenario():
        db = FakeDB()
        original, _, fill, settlement = await _buy_and_settle(
            db,
            quantity=1000,
            volume=2500,
        )
        assert fill.quantity == 100
        order = await PaperOrderService(db).get_order(fill.order_id)
        assert order.status == "PARTIALLY_FILLED"
        assert order.remaining_quantity == 900
        reservation = await PaperOrderService(db).reservation_for_order(fill.order_id)
        assert reservation.status == "PARTIALLY_CONSUMED"
        account = await PaperAccountService(db).get_account(original.account_id)
        assert account.cash_reserved > 0
        assert account.cash_available >= 0
        marked_equity = account.cash_available + account.cash_reserved + fill.notional
        assert marked_equity == original.initial_cash - fill.fee_breakdown.total_fee

    run(scenario())


def test_t1_roll_is_calendar_based_and_idempotent():
    async def scenario():
        db = FakeDB()
        original, _, fill, _ = await _buy_and_settle(db)
        service = PaperAccountService(db)
        assert await service.roll_lot_availability(date(2026, 7, 2)) == 0
        assert await service.roll_lot_availability(date(2026, 7, 3)) == 1
        assert await service.roll_lot_availability(date(2026, 7, 3)) == 0
        position = PaperPosition.model_validate(
            clean_document(
                await db["ag_paper_positions"].find_one(
                    {"account_id": original.account_id, "symbol": "600519"}
                )
            )
        )
        assert position.available_quantity == fill.quantity

    run(scenario())


def test_sell_reserves_available_lot_and_fifo_settlement_closes_position():
    async def scenario():
        db = FakeDB()
        original, _, buy_fill, _ = await _buy_and_settle(db)
        account_service = PaperAccountService(db)
        await account_service.roll_lot_availability(date(2026, 7, 3))
        account = await account_service.get_account(original.account_id)
        sell_intent = await make_intent(
            db,
            account,
            action="SELL",
            quantity=buy_fill.quantity,
            limit_price=None,
            source_object_id="sell-source",
            earliest=datetime(2026, 7, 6, 9, 30),
            expires=datetime(2026, 7, 10, 15),
        )
        order = await PaperOrderService(db).create_reserve_submit(sell_intent)
        snapshot = await ExecutionMarketSnapshotService(db).create_from_daily_record(
            record=daily_record(
                trade_date=date(2026, 7, 6),
                open_price="10.50",
                high="10.80",
                low="10.20",
                close="10.60",
                limit_up="11.50",
                limit_down="9.50",
            ),
            symbol="600519",
            trade_date=date(2026, 7, 6),
            cutoff_at=datetime(2026, 7, 6, 15, 30),
            data_version="fixed-v1",
        )
        sell_fill = await PaperExecutionService(db).match_order(
            order.order_id,
            snapshot.execution_snapshot_id,
            matched_at=datetime(2026, 7, 6, 15, 30),
        )
        settlement = await SettlementService(db).settle_fill(
            sell_fill.fill_id,
            now=datetime(2026, 7, 6, 16),
        )
        assert settlement.status == "COMMITTED"
        position = PaperPosition.model_validate(
            clean_document(
                await db["ag_paper_positions"].find_one(
                    {"account_id": account.account_id, "symbol": "600519"}
                )
            )
        )
        assert position.quantity == 0
        assert position.total_cost == Decimal("0")
        lot = PositionLot.model_validate(
            clean_document(
                await db["ag_paper_position_lots"].find_one(
                    {"source_fill_id": buy_fill.fill_id}
                )
            )
        )
        assert lot.status == "CLOSED"
        assert lot.remaining_quantity == 0
        updated = await account_service.get_account(account.account_id)
        assert updated.cash_available >= 0
        assert updated.realized_pnl == settlement.realized_pnl

    run(scenario())


def test_sell_cannot_reserve_t1_locked_lot():
    async def scenario():
        db = FakeDB()
        original, _, buy_fill, _ = await _buy_and_settle(db)
        account = await PaperAccountService(db).get_account(original.account_id)
        intent = await make_intent(
            db,
            account,
            action="SELL",
            quantity=buy_fill.quantity,
            limit_price=None,
            source_object_id="same-day-sell",
            earliest=datetime(2026, 7, 2, 9, 30),
        )
        service = PaperOrderService(db)
        order = await service.create_from_intent(intent)
        with pytest.raises(ReservationError):
            await service.reserve(order.order_id)

    run(scenario())


def test_expiry_only_releases_reservation_and_preserves_equity():
    async def scenario():
        db = FakeDB()
        original = (await setup_paper(db))["PAPER_QUANT"]
        intent = await make_intent(
            db,
            original,
            expires=datetime(2026, 7, 2, 15),
        )
        service = PaperOrderService(db)
        order = await service.create_reserve_submit(intent)
        expired = await service.expire(
            order.order_id,
            now=datetime(2026, 7, 3, 9),
        )
        account = await PaperAccountService(db).get_account(original.account_id)
        assert expired.status == "EXPIRED"
        assert account.cash_available == original.initial_cash
        assert account.cash_reserved == Decimal("0")
        assert db["ag_paper_fills"].count() == 0

    run(scenario())
