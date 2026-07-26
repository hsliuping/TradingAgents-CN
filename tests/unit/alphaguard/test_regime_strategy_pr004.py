from datetime import datetime

import pytest

from app.services.alphaguard.factor_aggregation import aggregate_factors
from app.services.alphaguard.factor_engine import FactorEngine
from app.services.alphaguard.factor_registry import FactorRegistry
from app.services.alphaguard.market_regime_engine import MarketRegimeEngine
from app.services.alphaguard.strategy_engine import StrategyEngine
from app.services.alphaguard.strategy_registry import (
    StrategyRegistry,
    builtin_strategy_definitions,
)
from tests.unit.alphaguard._fakes import FakeDB
from tests.unit.alphaguard.test_factor_engine_pr004 import resolved_data


def trend_context(data):
    data.market_context = [
        {
            "_reference": "market_context:ctx",
            "trade_date": "2026-07-01",
            "advance_count": 3200,
            "decline_count": 1200,
            "industry_up_ratio": 0.70,
            "amount_ratio20": 1.1,
            "new_high_count": 300,
            "new_low_count": 50,
            "extreme_risk_flag": False,
        }
    ]
    data.trading_calendar = [
        {
            "_reference": f"trading_calendar:c{index}",
            "session_date": f"2026-07-0{index + 2}",
            "is_open": True,
            "as_of": "2026-07-01T09:00:00",
        }
        for index in range(3)
    ]
    return data


@pytest.mark.asyncio
async def test_market_regime_calculates_trend_up_from_public_market_evidence():
    db = FakeDB()
    data = trend_context(resolved_data())
    result = await MarketRegimeEngine(db).calculate(data)
    assert result.calculation_status == "CALCULATED"
    assert result.regime == "TREND_UP"
    assert result.allow_new_positions is True
    assert "SWING_TREND_PULLBACK_V1" in result.allowed_strategy_ids
    again = await MarketRegimeEngine(db).calculate(data)
    assert again.regime_result_id == result.regime_result_id


@pytest.mark.asyncio
async def test_missing_market_context_does_not_fabricate_sixth_or_range_regime():
    result = await MarketRegimeEngine(FakeDB()).calculate(resolved_data())
    assert result.calculation_status == "INSUFFICIENT_DATA"
    assert result.regime is None
    assert result.allow_new_positions is False
    assert result.allowed_strategy_ids == ["POSITION_EXIT_V1"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("shape", "advances", "declines", "diffusion", "extreme", "expected"),
    [
        ("up", 3200, 1200, 0.70, False, "TREND_UP"),
        ("up", 2600, 1800, 0.40, False, "RANGE_STRONG"),
        ("flat", 1800, 2600, 0.40, False, "RANGE_WEAK"),
        ("down", 1000, 3000, 0.20, False, "TREND_DOWN"),
        ("up", 3200, 1200, 0.70, True, "EXTREME_RISK"),
    ],
)
async def test_market_regime_is_limited_to_configured_five_states(
    shape, advances, declines, diffusion, extreme, expected
):
    data = trend_context(resolved_data())
    if shape == "flat":
        for row in data.benchmark_prices:
            row["close"] = 100
    elif shape == "down":
        for index, row in enumerate(data.benchmark_prices):
            row["close"] = 161 - index
    data.market_context[-1].update(
        advance_count=advances,
        decline_count=declines,
        industry_up_ratio=diffusion,
        extreme_risk_flag=extreme,
    )
    data.input_hash = {
        "up": "1" * 64,
        "flat": "2" * 64,
        "down": "3" * 64,
    }[shape]
    result = await MarketRegimeEngine(FakeDB()).calculate(data)
    assert result.calculation_status == "CALCULATED"
    assert result.regime == expected


@pytest.mark.asyncio
async def test_invalid_market_counts_return_invalid_input_not_a_regime():
    data = trend_context(resolved_data())
    data.market_context[-1]["advance_count"] = -1
    result = await MarketRegimeEngine(FakeDB()).calculate(data)
    assert result.calculation_status == "INVALID_INPUT"
    assert result.regime is None
    assert result.allow_new_positions is False


@pytest.mark.asyncio
async def test_swing_strategy_triggers_without_target_price_or_order():
    db = FakeDB()
    await FactorRegistry(db).seed_builtins()
    strategies = await StrategyRegistry(db).seed_builtins()
    data = trend_context(resolved_data())
    data.prices[-1]["close"] = 155.0
    results = await FactorEngine(db).calculate_all(data)
    bundle = aggregate_factors(results)
    regime = await MarketRegimeEngine(db).calculate(data)
    definition = next(
        item for item in strategies if item.strategy_id == "SWING_TREND_PULLBACK_V1"
    )
    proposal = StrategyEngine().evaluate(definition, data, bundle, regime)
    assert proposal.status == "TRIGGERED"
    assert proposal.action_candidate == "BUY"
    assert proposal.entry_zone is not None
    assert proposal.valid_until == datetime(2026, 7, 4, 15)
    assert proposal.automated_execution_allowed is False
    assert "target_price" not in type(proposal).model_fields


@pytest.mark.asyncio
async def test_swing_requires_snapshot_calendar_instead_of_natural_day_math():
    db = FakeDB()
    await FactorRegistry(db).seed_builtins()
    definitions = await StrategyRegistry(db).seed_builtins()
    data = trend_context(resolved_data())
    data.prices[-1]["close"] = 155.0
    data.trading_calendar = []
    bundle = aggregate_factors(await FactorEngine(db).calculate_all(data))
    regime = await MarketRegimeEngine(db).calculate(data)
    definition = next(
        item for item in definitions if item.strategy_id == "SWING_TREND_PULLBACK_V1"
    )
    proposal = StrategyEngine().evaluate(definition, data, bundle, regime)
    assert proposal.status == "INSUFFICIENT_DATA"
    assert proposal.valid_until is None
    assert "TRADING_CALENDAR_INSUFFICIENT" in proposal.reason_codes


@pytest.mark.asyncio
async def test_position_exit_rejects_when_snapshot_has_no_positive_position():
    db = FakeDB()
    await FactorRegistry(db).seed_builtins()
    definitions = await StrategyRegistry(db).seed_builtins()
    data = trend_context(resolved_data())
    bundle = aggregate_factors(await FactorEngine(db).calculate_all(data))
    regime = await MarketRegimeEngine(db).calculate(data)
    definition = next(
        item for item in definitions if item.strategy_id == "POSITION_EXIT_V1"
    )
    proposal = StrategyEngine().evaluate(definition, data, bundle, regime)
    assert proposal.status == "REJECTED"
    assert proposal.action_candidate == "HOLD"
    assert proposal.reason_codes == ["NO_POSITION"]


@pytest.mark.asyncio
async def test_position_exit_uses_referenced_position_and_t1_fields_but_creates_no_order():
    db = FakeDB()
    await FactorRegistry(db).seed_builtins()
    definitions = await StrategyRegistry(db).seed_builtins()
    data = trend_context(resolved_data())
    data.news = [
        {
            "_reference": "stock_news:risk",
            "risk_level": "CRITICAL",
            "title": "structured blocking event",
        }
    ]
    data.positions = [
        {
            "_reference": "paper_positions:pos",
            "user_id": "user",
            "code": "600519",
            "market": "CN",
            "quantity": 100,
            "available_qty": 0,
            "updated_at": "2026-07-01T14:00:00",
        }
    ]
    data.input_hash = "d" * 64
    bundle = aggregate_factors(await FactorEngine(db).calculate_all(data))
    regime = await MarketRegimeEngine(db).calculate(data)
    definition = next(
        item for item in definitions if item.strategy_id == "POSITION_EXIT_V1"
    )
    proposal = StrategyEngine().evaluate(definition, data, bundle, regime)
    assert proposal.status == "TRIGGERED"
    assert proposal.action_candidate == "SELL"
    assert "T1_SELLABLE_QUANTITY_ZERO" in proposal.risk_flags
    assert proposal.automated_execution_allowed is False
    assert db["paper_orders"].count() == 0
    assert db["paper_trades"].count() == 0


def test_only_two_pr004_strategies_are_registered():
    assert {item.strategy_id for item in builtin_strategy_definitions()} == {
        "SWING_TREND_PULLBACK_V1",
        "POSITION_EXIT_V1",
    }
