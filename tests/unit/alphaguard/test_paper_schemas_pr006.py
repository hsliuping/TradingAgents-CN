from datetime import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from tradingagents.alphaguard.paper_schemas import (
    FeeBreakdown,
    PaperAccount,
    PaperReservation,
)


def account(**changes):
    payload = {
        "account_id": "account",
        "user_id": "user",
        "account_type": "PAPER_QUANT",
        "market": "CN",
        "currency": "CNY",
        "status": "ACTIVE",
        "initial_cash": Decimal("1000000"),
        "cash_available": Decimal("1000000"),
        "cash_reserved": Decimal("0"),
        "realized_pnl": Decimal("0"),
        "total_fees": Decimal("0"),
        "created_at": datetime(2026, 7, 1),
        "updated_at": datetime(2026, 7, 1),
        "account_config_version": "1.0.0",
        "execution_environment": "PAPER",
        "live_execution_allowed": False,
    }
    payload.update(changes)
    return PaperAccount(**payload)


def test_account_uses_decimal_and_is_permanently_paper_only():
    value = account()
    assert isinstance(value.cash_available, Decimal)
    assert value.execution_environment == "PAPER"
    assert value.live_execution_allowed is False


@pytest.mark.parametrize(
    "field,value",
    [
        ("market", "HK"),
        ("currency", "USD"),
        ("execution_environment", "LIVE"),
        ("live_execution_allowed", True),
    ],
)
def test_account_rejects_non_cn_or_live_values(field, value):
    with pytest.raises(ValidationError):
        account(**{field: value})


def test_account_rejects_negative_cash():
    with pytest.raises(ValidationError):
        account(cash_available=Decimal("-0.01"))


def test_cash_reservation_requires_amount_and_no_lots():
    with pytest.raises(ValidationError):
        PaperReservation(
            reservation_id="r",
            order_id="o",
            account_id="a",
            reservation_type="CASH",
            currency="CNY",
            reserved_amount=None,
            idempotency_key="key",
            created_at=datetime(2026, 7, 1),
            updated_at=datetime(2026, 7, 1),
        )

def test_position_reservation_allocations_must_sum():
    with pytest.raises(ValidationError):
        PaperReservation(
            reservation_id="r",
            order_id="o",
            account_id="a",
            reservation_type="POSITION",
            symbol="600519",
            reserved_quantity=200,
            lot_allocations=[{"lot_id": "lot", "reserved_quantity": 100}],
            idempotency_key="key",
            created_at=datetime(2026, 7, 1),
            updated_at=datetime(2026, 7, 1),
        )


def test_fee_breakdown_must_equal_components():
    with pytest.raises(ValidationError):
        FeeBreakdown(
            commission=Decimal("5"),
            stamp_duty=Decimal("1"),
            transfer_fee=Decimal("0"),
            regulatory_fee=Decimal("0"),
            other_fees=Decimal("0"),
            total_fee=Decimal("5"),
            fee_policy_version="1",
            calculation_scope="ORDER_TRADE_DATE",
        )
