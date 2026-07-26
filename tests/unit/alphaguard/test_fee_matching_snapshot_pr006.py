from datetime import date, datetime
from decimal import Decimal

import pytest

from app.services.alphaguard.execution_market_snapshot_service import (
    ExecutionMarketSnapshotService,
    ExecutionSnapshotConflictError,
    ExecutionSnapshotError,
)
from app.services.alphaguard.fee_engine import FeeEngine, FeePolicyError
from app.services.alphaguard.matching_engine import MatchingEngine
from app.services.alphaguard.paper_policy_registry import (
    builtin_execution_policy,
    builtin_fee_policy,
)
from tests.unit.alphaguard._fakes import FakeDB
from tests.unit.alphaguard.pr006_helpers import daily_record
from tradingagents.alphaguard.paper_schemas import PaperOrder


def run(coro):
    import asyncio

    return asyncio.run(coro)


def order(**changes):
    payload = {
        "order_id": "order",
        "intent_id": "intent",
        "account_id": "account",
        "user_id": "user",
        "account_type": "PAPER_QUANT",
        "candidate_id": None,
        "source_type": "QUANT_PROPOSAL",
        "source_object_id": "proposal",
        "risk_decision_id": None,
        "symbol": "600519",
        "market": "CN",
        "currency": "CNY",
        "side": "BUY",
        "original_action": "BUY",
        "order_type": "LIMIT",
        "requested_quantity": 1000,
        "reserved_quantity": 1000,
        "filled_quantity": 0,
        "remaining_quantity": 1000,
        "limit_price": Decimal("10.00"),
        "average_fill_price": None,
        "reserved_cash": Decimal("10010"),
        "total_notional": Decimal("0"),
        "total_fees": Decimal("0"),
        "status": "PENDING",
        "reject_reason": None,
        "trade_date": date(2026, 7, 2),
        "earliest_execute_at": datetime(2026, 7, 2, 9, 30),
        "expires_at": datetime(2026, 7, 8, 15),
        "submitted_at": datetime(2026, 7, 1),
        "last_matched_trade_date": None,
        "filled_at": None,
        "cancelled_at": None,
        "created_at": datetime(2026, 7, 1),
        "updated_at": datetime(2026, 7, 1),
    }
    payload.update(changes)
    return PaperOrder(**payload)


async def snapshot(**changes):
    db = FakeDB()
    record = daily_record()
    record.update(changes)
    return await ExecutionMarketSnapshotService(db).create_from_daily_record(
        record=record,
        symbol="600519",
        trade_date=date(2026, 7, 2),
        cutoff_at=datetime(2026, 7, 2, 15, 30),
        data_version="fixed-v1",
    )


def test_fee_engine_buy_commission_minimum_and_transfer_fee():
    fees = FeeEngine.calculate(
        side="BUY",
        notional=Decimal("1000"),
        policy=builtin_fee_policy(),
    )
    assert fees.commission == Decimal("5.00")
    assert fees.stamp_duty == Decimal("0.00")
    assert fees.transfer_fee == Decimal("0.02")
    assert fees.total_fee == Decimal("5.02")


def test_fee_engine_sell_adds_stamp_duty():
    fees = FeeEngine.calculate(
        side="SELL",
        notional=Decimal("10000"),
        policy=builtin_fee_policy(),
    )
    assert fees.stamp_duty == Decimal("10.00")
    assert fees.total_fee == Decimal("15.20")


def test_fee_engine_decimal_result_is_deterministic():
    first = FeeEngine.calculate(
        side="BUY",
        notional=Decimal("12345.67"),
        policy=builtin_fee_policy(),
    )
    second = FeeEngine.calculate(
        side="BUY",
        notional=Decimal("12345.67"),
        policy=builtin_fee_policy(),
    )
    assert first == second
    assert all(
        isinstance(getattr(first, name), Decimal)
        for name in (
            "commission",
            "stamp_duty",
            "transfer_fee",
            "total_fee",
        )
    )


def test_fee_engine_rejects_zero_notional():
    with pytest.raises(FeePolicyError):
        FeeEngine.calculate(
            side="BUY",
            notional=Decimal("0"),
            policy=builtin_fee_policy(),
        )


def test_execution_snapshot_requires_ohlc():
    with pytest.raises(ExecutionSnapshotError):
        run(snapshot(open=None))


def test_execution_snapshot_rejects_future_data():
    with pytest.raises(ExecutionSnapshotError):
        run(
            ExecutionMarketSnapshotService(FakeDB()).create_from_daily_record(
                record=daily_record(),
                symbol="600519",
                trade_date=date(2026, 7, 2),
                cutoff_at=datetime(2026, 7, 1, 15, 30),
                data_version="fixed-v1",
            )
        )


def test_execution_snapshot_requires_explicit_limit_prices():
    with pytest.raises(ExecutionSnapshotError):
        run(snapshot(limit_up_price=None))


def test_execution_snapshot_uses_existing_tradestatus_semantics():
    async def scenario():
        db = FakeDB()
        service = ExecutionMarketSnapshotService(db)
        trading = daily_record()
        trading.pop("suspended")
        trading["tradestatus"] = 1
        normal = await service.create_from_daily_record(
            record=trading,
            symbol="600519",
            trade_date=date(2026, 7, 2),
            cutoff_at=datetime(2026, 7, 2, 15, 30),
            data_version="trading-v1",
        )
        assert normal.suspended is False

        suspended = daily_record(trade_date=date(2026, 7, 3))
        suspended.pop("suspended")
        suspended["tradestatus"] = 0
        blocked = await service.create_from_daily_record(
            record=suspended,
            symbol="600519",
            trade_date=date(2026, 7, 3),
            cutoff_at=datetime(2026, 7, 3, 15, 30),
            data_version="suspended-v1",
        )
        assert blocked.suspended is True

    run(scenario())


def test_execution_snapshot_hash_is_stable_and_conflicts_fail():
    async def scenario():
        db = FakeDB()
        service = ExecutionMarketSnapshotService(db)
        kwargs = dict(
            record=daily_record(),
            symbol="600519",
            trade_date=date(2026, 7, 2),
            cutoff_at=datetime(2026, 7, 2, 15, 30),
            data_version="fixed-v1",
            now=datetime(2026, 7, 2, 16),
        )
        first = await service.create_from_daily_record(**kwargs)
        second = await service.create_from_daily_record(**kwargs)
        assert first.immutable_hash == second.immutable_hash
        changed = daily_record(close="10.19")
        with pytest.raises(ExecutionSnapshotConflictError):
            await service.create_from_daily_record(**{**kwargs, "record": changed})

    run(scenario())


@pytest.mark.parametrize(
    "open_price,low,expected",
    [
        ("9.90", "9.80", "FULL_FILL"),
        ("10.10", "9.99", "FULL_FILL"),
        ("10.10", "10.01", "NO_FILL"),
    ],
)
def test_buy_limit_matching(open_price, low, expected):
    snap = run(snapshot(open=open_price, low=low, high="10.20", close="10.10"))
    result = MatchingEngine().match(
        order=order(),
        snapshot=snap,
        policy=builtin_execution_policy(),
        valid_reserved_quantity=1000,
        matched_at=datetime(2026, 7, 2, 15, 30),
    )
    assert result.status == expected
    if expected != "NO_FILL":
        assert result.price <= Decimal("10.00")


@pytest.mark.parametrize(
    "open_price,high,expected",
    [
        ("10.10", "10.20", "FULL_FILL"),
        ("9.90", "10.01", "FULL_FILL"),
        ("9.90", "9.99", "NO_FILL"),
    ],
)
def test_sell_limit_matching(open_price, high, expected):
    close = "9.95" if Decimal(high) < Decimal("10.00") else "10.00"
    snap = run(snapshot(open=open_price, high=high, low="9.80", close=close))
    sell = order(
        side="SELL",
        original_action="SELL",
        order_type="LIMIT",
        limit_price=Decimal("10.00"),
        reserved_cash=Decimal("0"),
    )
    result = MatchingEngine().match(
        order=sell,
        snapshot=snap,
        policy=builtin_execution_policy(),
        valid_reserved_quantity=1000,
        matched_at=datetime(2026, 7, 2, 15, 30),
    )
    assert result.status == expected
    if expected != "NO_FILL":
        assert result.price >= Decimal("10.00")


def test_market_open_slippage_directions_and_tick():
    snap = run(snapshot(open="10.00"))
    buy = order(order_type="MARKET_ON_OPEN", limit_price=None)
    sell = order(
        side="SELL",
        original_action="SELL",
        order_type="MARKET_ON_OPEN",
        limit_price=None,
        reserved_cash=Decimal("0"),
    )
    engine = MatchingEngine()
    policy = builtin_execution_policy()
    buy_result = engine.match(
        order=buy,
        snapshot=snap,
        policy=policy,
        valid_reserved_quantity=1000,
        matched_at=datetime(2026, 7, 2, 15, 30),
    )
    sell_result = engine.match(
        order=sell,
        snapshot=snap,
        policy=policy,
        valid_reserved_quantity=1000,
        matched_at=datetime(2026, 7, 2, 15, 30),
    )
    assert buy_result.price == Decimal("10.01")
    assert sell_result.price == Decimal("9.99")


def test_suspension_and_one_price_limits_do_not_fill():
    engine = MatchingEngine()
    policy = builtin_execution_policy()
    suspended = run(snapshot(suspended=True))
    assert engine.match(
        order=order(),
        snapshot=suspended,
        policy=policy,
        valid_reserved_quantity=1000,
        matched_at=datetime(2026, 7, 2, 15, 30),
    ).status == "NO_FILL"
    limit_up = run(
        snapshot(
            open="11.00",
            high="11.00",
            low="11.00",
            close="11.00",
        )
    )
    assert engine.match(
        order=order(limit_price=Decimal("11.00")),
        snapshot=limit_up,
        policy=policy,
        valid_reserved_quantity=1000,
        matched_at=datetime(2026, 7, 2, 15, 30),
    ).status == "NO_FILL"
    limit_down = run(
        snapshot(
            open="9.00",
            high="9.00",
            low="9.00",
            close="9.00",
        )
    )
    sell = order(
        side="SELL",
        original_action="SELL",
        order_type="MARKET_ON_OPEN",
        limit_price=None,
        reserved_cash=Decimal("0"),
    )
    assert engine.match(
        order=sell,
        snapshot=limit_down,
        policy=policy,
        valid_reserved_quantity=1000,
        matched_at=datetime(2026, 7, 2, 15, 30),
    ).status == "NO_FILL"


def test_non_tick_limit_never_produces_non_tick_fill():
    snap = run(snapshot(open="10.20", low="10.00"))
    policy = builtin_execution_policy()
    result = MatchingEngine().match(
        order=order(limit_price=Decimal("10.005")),
        snapshot=snap,
        policy=policy,
        valid_reserved_quantity=1000,
        matched_at=datetime(2026, 7, 2, 15, 30),
    )
    assert result.status == "FULL_FILL"
    assert result.price == Decimal("10.00")
    assert result.price % policy.price_tick == 0


def test_participation_rate_causes_partial_fill_and_buy_lot_rounding():
    snap = run(snapshot(volume=2500))
    result = MatchingEngine().match(
        order=order(),
        snapshot=snap,
        policy=builtin_execution_policy(),
        valid_reserved_quantity=1000,
        matched_at=datetime(2026, 7, 2, 15, 30),
    )
    assert result.status == "PARTIAL_FILL"
    assert result.quantity == 100


def test_order_expiry_and_earliest_date_block_matching():
    snap = run(snapshot())
    engine = MatchingEngine()
    policy = builtin_execution_policy()
    assert engine.match(
        order=order(earliest_execute_at=datetime(2026, 7, 3, 9, 30)),
        snapshot=snap,
        policy=policy,
        valid_reserved_quantity=1000,
        matched_at=datetime(2026, 7, 2, 15, 30),
    ).status == "NO_FILL"
    assert engine.match(
        order=order(expires_at=datetime(2026, 7, 2, 14)),
        snapshot=snap,
        policy=policy,
        valid_reserved_quantity=1000,
        matched_at=datetime(2026, 7, 2, 15, 30),
    ).status == "BLOCKED"
