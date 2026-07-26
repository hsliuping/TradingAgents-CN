from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.services.alphaguard.horizon_label_service import HorizonLabelService
from app.services.alphaguard.trading_horizon_resolver import TradingHorizonResolver
from tests.unit.alphaguard._fakes import FakeDB
from tests.unit.alphaguard.pr007_helpers import (
    OPEN_DATES,
    make_label,
    make_subject,
    seed_adjusted_prices,
    seed_calendar,
)
from tradingagents.alphaguard.evaluation_schemas import (
    AttributionOverride,
    CounterfactualEvaluation,
    EvaluationSubject,
    HorizonLabel,
)


def test_evaluation_subject_is_frozen_and_validates_position_range():
    subject = make_subject()
    with pytest.raises(ValidationError):
        subject.action = "SELL"
    payload = subject.model_dump(mode="python")
    payload["initial_position_pct"] = Decimal("0.20")
    with pytest.raises(ValidationError, match="cannot exceed"):
        EvaluationSubject.model_validate(payload)


def test_benchmark_safety_cannot_masquerade_as_hard_risk():
    subject = make_subject(
        subject_type="BENCHMARK_DECISION",
        stage="BENCHMARK_SAFETY",
        status="PASS",
    )
    payload = subject.model_dump(mode="python")
    payload["decision_stage"] = "HARD_RISK"
    with pytest.raises(ValidationError, match="cannot masquerade"):
        EvaluationSubject.model_validate(payload)


def test_calculated_label_requires_result_fields():
    payload = make_label("s", "10D").model_dump(mode="python")
    payload["mfe"] = None
    with pytest.raises(ValidationError, match="lacks required"):
        HorizonLabel.model_validate(payload)


def test_non_calculated_label_cannot_hide_returns():
    payload = make_label("s", "10D").model_dump(mode="python")
    payload["status"] = "INSUFFICIENT_DATA"
    with pytest.raises(ValidationError, match="cannot contain return"):
        HorizonLabel.model_validate(payload)


def test_counterfactual_and_override_schemas_have_no_execution_authority():
    fields = CounterfactualEvaluation.model_fields
    assert "order_intent_created" not in fields
    assert "live_execution_allowed" not in fields
    assert "account_id" not in fields
    assert "previous_primary_category" in AttributionOverride.model_fields


@pytest.mark.asyncio
async def test_trading_horizons_use_open_sessions_not_natural_days():
    db = FakeDB()
    await seed_calendar(db)
    resolver = TradingHorizonResolver(db)
    assert await resolver.resolve(date(2026, 7, 1), "1D") == date(2026, 7, 2)
    assert await resolver.resolve(date(2026, 7, 1), "5D") == date(2026, 7, 8)
    assert await resolver.resolve(date(2026, 7, 1), "10D") == date(2026, 7, 15)
    assert await resolver.resolve(date(2026, 7, 1), "20D") == date(2026, 7, 29)
    assert await resolver.resolve(date(2026, 7, 3), "1D") == date(2026, 7, 6)


@pytest.mark.asyncio
async def test_missing_calendar_fails_closed():
    with pytest.raises(LookupError, match="calendar does not cover"):
        await TradingHorizonResolver(FakeDB()).resolve(
            date(2026, 7, 1), "5D"
        )


@pytest.mark.asyncio
async def test_horizon_resolver_handles_holiday_gap_and_cross_year():
    db = FakeDB()
    sessions = [
        date(2026, 12, 30),
        date(2026, 12, 31),
        date(2027, 1, 4),
        date(2027, 1, 5),
        date(2027, 1, 6),
        date(2027, 1, 7),
    ]
    for session in sessions:
        await db["trading_calendar"].insert_one(
            {
                "market": "CN",
                "session_date": session.isoformat(),
                "is_open": True,
            }
        )
    resolver = TradingHorizonResolver(db)
    assert await resolver.resolve(date(2026, 12, 30), "1D") == date(2026, 12, 31)
    assert await resolver.resolve(date(2026, 12, 30), "5D") == date(2027, 1, 7)


@pytest.mark.asyncio
async def test_adjusted_labels_calculate_returns_mfe_mae_and_relative_benchmark():
    db = FakeDB()
    await seed_calendar(db)
    await seed_adjusted_prices(db)
    await seed_adjusted_prices(
        db,
        symbol="000300",
        start_price=Decimal("20"),
        step=Decimal("0.05"),
    )
    labels = await HorizonLabelService(db).calculate_all(
        make_subject(),
        as_of_trade_date=OPEN_DATES[-1],
    )
    decision = next(
        item
        for item in labels
        if item.horizon == "10D" and item.anchor_type == "DECISION_CLOSE"
    )
    planned = next(
        item
        for item in labels
        if item.horizon == "10D" and item.anchor_type == "PLANNED_ENTRY"
    )
    assert decision.status == "CALCULATED"
    assert decision.anchor_price == Decimal("10")
    assert decision.horizon_close_price == Decimal("11.0")
    assert decision.raw_forward_return == Decimal("0.1")
    assert decision.action_aligned_return == Decimal("0.1")
    assert decision.mfe == Decimal("0.12")
    assert decision.mae == Decimal("-0.01")
    assert decision.benchmark_return is not None
    assert decision.benchmark_price_adjustment_mode == "QFQ"
    assert decision.benchmark_data_version == "qfq-fixture-v1"
    assert decision.relative_benchmark_return == (
        decision.raw_forward_return - decision.benchmark_return
    )
    assert decision.industry_benchmark_return is None
    assert "unavailable" in decision.industry_unavailable_reason
    assert planned.entry_zone_touched is True
    assert planned.entry_first_touch_date == date(2026, 7, 2)
    assert decision.price_adjustment_mode == "QFQ"
    assert decision.price_data_version == "qfq-fixture-v1"


@pytest.mark.asyncio
async def test_missing_explicit_adjusted_fields_is_insufficient_not_raw_fallback():
    db = FakeDB()
    await seed_calendar(db)
    for session in OPEN_DATES:
        await db["stock_daily_quotes"].insert_one(
            {
                "symbol": "600519",
                "market": "CN",
                "trade_date": session.isoformat(),
                "period": "daily",
                "open": 10,
                "high": 11,
                "low": 9,
                "close": 10.5,
                "adjustflag": 2,
            }
        )
    labels = await HorizonLabelService(db).calculate_all(
        make_subject(entry_zone=False),
        as_of_trade_date=OPEN_DATES[-1],
    )
    assert {item.status for item in labels} == {"INSUFFICIENT_DATA"}
    assert all(item.raw_forward_return is None for item in labels)


@pytest.mark.asyncio
async def test_adjusted_prices_prevent_corporate_action_false_drop_without_mutation():
    db = FakeDB()
    await seed_calendar(db)
    await seed_adjusted_prices(db, start_price=Decimal("10"), step=Decimal("0.10"))
    for item in db["stock_daily_quotes"].documents:
        # The raw series deliberately contains an apparent ex-dividend split.
        item["close"] = Decimal("5") if str(item["trade_date"]) >= "2026-07-08" else Decimal("10")
        item["open"] = item["close"]
        item["high"] = item["close"]
        item["low"] = item["close"]
    before = [
        {key: value for key, value in item.items() if key != "_id"}
        for item in db["stock_daily_quotes"].documents
    ]
    labels = await HorizonLabelService(db).calculate_all(
        make_subject(entry_zone=False),
        as_of_trade_date=OPEN_DATES[-1],
    )
    label = next(item for item in labels if item.horizon == "10D")
    assert label.status == "CALCULATED"
    assert label.raw_forward_return == Decimal("0.1")
    after = [
        {key: value for key, value in item.items() if key != "_id"}
        for item in db["stock_daily_quotes"].documents
    ]
    assert before == after


@pytest.mark.asyncio
async def test_missing_calendar_produces_invalid_source_not_permanent_pending():
    db = FakeDB()
    await seed_adjusted_prices(db)
    labels = await HorizonLabelService(db).calculate_all(
        make_subject(entry_zone=False),
        as_of_trade_date=OPEN_DATES[-1],
    )
    assert {item.status for item in labels} == {"INVALID_SOURCE"}


@pytest.mark.asyncio
async def test_future_horizon_stays_pending_and_later_matures_once():
    db = FakeDB()
    await seed_calendar(db)
    await seed_adjusted_prices(db)
    subject = make_subject(entry_zone=False)
    service = HorizonLabelService(db)
    pending = await service.calculate_all(
        subject,
        as_of_trade_date=date(2026, 7, 3),
    )
    label = next(item for item in pending if item.horizon == "10D")
    assert label.status == "PENDING"
    mature = await service.calculate_all(
        subject,
        as_of_trade_date=OPEN_DATES[-1],
    )
    label = next(item for item in mature if item.horizon == "10D")
    assert label.status == "CALCULATED"
    assert db["ag_eval_horizon_labels"].count() == 4


@pytest.mark.asyncio
async def test_sell_direction_metric_is_negative_raw_but_not_actual_value_claim():
    db = FakeDB()
    await seed_calendar(db)
    await seed_adjusted_prices(db)
    labels = await HorizonLabelService(db).calculate_all(
        make_subject(action="SELL", entry_zone=False),
        as_of_trade_date=OPEN_DATES[-1],
    )
    label = next(item for item in labels if item.horizon == "5D")
    assert label.raw_forward_return > 0
    assert label.action_aligned_return == -label.raw_forward_return
    assert "avoided_loss" not in type(label).model_fields
