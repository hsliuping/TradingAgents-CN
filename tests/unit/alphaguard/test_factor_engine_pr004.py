from datetime import date, datetime

import pytest

from app.services.alphaguard.factor_aggregation import aggregate_factors
from app.services.alphaguard.factor_engine import FactorEngine
from app.services.alphaguard.factor_registry import (
    DefinitionConflictError,
    FactorRegistry,
    builtin_factor_definitions,
)
from app.services.alphaguard.snapshot_data_resolver import ResolvedSnapshotData
from tests.unit.alphaguard._fakes import FakeDB
from tradingagents.alphaguard.evidence_schemas import DataQualityReport, EvidenceSnapshot


def resolved_data(*, include_financials=True, include_events=True):
    prices = []
    benchmark = []
    for index in range(61):
        prices.append(
            {
                "ref_id": f"p{index}",
                "_reference": f"stock_daily_quotes:p{index}",
                "trade_date": f"2026-05-{index + 1:02d}",
                "open": 100 + index,
                "high": 102 + index,
                "low": 99 + index,
                "close": 101 + index,
                "volume": 1_000_000 + index * 10_000,
                "amount": 100_000_000 + index * 1_000_000,
                "turnover_rate": 1 + index / 100,
                "pe_ttm": 10 + index / 10,
                "pb": 1 + index / 100,
                "dv_ttm": 2.0,
            }
        )
        benchmark.append(
            {
                "ref_id": f"b{index}",
                "_reference": f"index_daily:b{index}",
                "trade_date": f"2026-05-{index + 1:02d}",
                "close": 100 + index * 0.5,
            }
        )
    # Valid ISO dates are not needed by FactorEngine; rows are already resolved.
    financials = (
        [
            {
                "_reference": "stock_financial_data:f0",
                "report_period": "2024-12-31",
                "revenue": 100,
                "adjusted_net_profit": 10,
                "roe": 12,
                "n_cashflow_act": 12,
                "net_income": 10,
            },
            {
                "_reference": "stock_financial_data:f1",
                "report_period": "2025-12-31",
                "revenue": 130,
                "adjusted_net_profit": 14,
                "roe": 15,
                "n_cashflow_act": 18,
                "net_income": 14,
            },
        ]
        if include_financials
        else []
    )
    news = (
        [{"_reference": "stock_news:n0", "title": "routine company update"}]
        if include_events
        else []
    )
    quality = DataQualityReport(
        quality_report_id="quality",
        symbol="600519",
        market="CN",
        trade_date=date(2026, 7, 1),
        status="PASS",
        completeness_score=1,
        freshness_score=1,
        consistency_score=1,
        checked_at=datetime(2026, 7, 1),
    )
    _, definitions, _ = builtin_factor_definitions()
    snapshot = EvidenceSnapshot(
        snapshot_id="snapshot",
        user_id="user",
        symbol="600519",
        market="CN",
        trade_date=date(2026, 7, 1),
        price_cutoff_at=datetime(2026, 7, 1, 15),
        news_cutoff_at=datetime(2026, 7, 1, 15),
        announcement_cutoff_at=datetime(2026, 7, 1, 15),
        price_data_version="fixed-v1",
        financial_data_version="fixed-v1",
        news_data_version="fixed-v1",
        data_quality=quality,
        raw_refs={"prices": ["stock_daily_quotes:p0"]},
        factor_version_set={
            item.factor_id: item.factor_version for item in definitions
        },
        strategy_version="strategy-set-v1",
        immutable_hash="a" * 64,
        created_at=datetime(2026, 7, 1),
    )
    refs = [
        item["_reference"]
        for item in prices + benchmark + financials + news
    ]
    return ResolvedSnapshotData(
        snapshot=snapshot,
        prices=prices,
        benchmark_prices=benchmark,
        financials=financials,
        news=news,
        input_refs=refs,
        excluded_refs=[],
        input_hash="b" * 64,
    )


@pytest.mark.asyncio
async def test_registry_seeds_21_immutable_versioned_factors():
    db = FakeDB()
    registry = FactorRegistry(db)
    seeded = await registry.seed_builtins()
    assert len(seeded) == 21
    assert len(await registry.get_version_set()) == 21
    altered = seeded[0].model_copy(update={"description": "changed"})
    with pytest.raises(DefinitionConflictError):
        await registry.register(altered)


@pytest.mark.asyncio
async def test_all_21_factors_are_deterministic_and_persisted_once():
    db = FakeDB()
    await FactorRegistry(db).seed_builtins()
    engine = FactorEngine(db)
    data = resolved_data()
    first = await engine.calculate_all(data)
    second = await engine.calculate_all(data)
    assert len(first) == 21
    assert [item.result_id for item in first] == [item.result_id for item in second]
    assert db["ag_factor_results"].count() == 21
    assert all(item.normalized_score is not None for item in first)
    assert next(item for item in first if item.factor_id == "revenue_yoy_v1").raw_value == pytest.approx(0.3)
    assert next(item for item in first if item.factor_id == "event_risk_v1").raw_value == 0


@pytest.mark.asyncio
async def test_core_factor_formulas_use_only_fixed_windows():
    db = FakeDB()
    await FactorRegistry(db).seed_builtins()
    results = await FactorEngine(db).calculate_all(resolved_data())
    raw = {item.factor_id: item.raw_value for item in results}
    assert raw["close_vs_ma20_v1"] == pytest.approx(161 / 151.5 - 1)
    assert raw["close_vs_ma60_v1"] == pytest.approx(161 / 131.5 - 1)
    assert raw["ma20_vs_ma60_v1"] == pytest.approx(151.5 / 131.5 - 1)
    assert raw["ma20_slope_5d_v1"] == pytest.approx(151.5 / 146.5 - 1)
    assert raw["momentum_20d_v1"] == pytest.approx(161 / 141 - 1)
    assert raw["momentum_60d_v1"] == pytest.approx(161 / 101 - 1)
    assert raw["relative_strength_hs300_20d_v1"] == pytest.approx(
        (161 / 141 - 1) - (130 / 120 - 1)
    )
    assert raw["volume_confirmation_20d_v1"] == pytest.approx(
        1_600_000 / 1_495_000
    )
    assert raw["adjusted_net_profit_yoy_v1"] == pytest.approx(0.4)
    assert raw["roe_v1"] == pytest.approx(0.15)
    assert raw["operating_cashflow_to_profit_v1"] == pytest.approx(18 / 14)
    assert raw["pe_ttm_percentile_3y_v1"] == 100
    assert raw["pb_percentile_3y_v1"] == 100
    assert raw["dividend_yield_v1"] == pytest.approx(0.02)
    assert raw["atr14_pct_v1"] == pytest.approx(3 / 161)
    assert raw["average_amount20_v1"] == pytest.approx(
        sum(100_000_000 + index * 1_000_000 for index in range(41, 61)) / 20
    )
    assert raw["turnover20_v1"] == pytest.approx(
        sum(1 + index / 100 for index in range(41, 61)) / 20
    )
    assert raw["short_term_excess_return5_v1"] == pytest.approx(
        (161 / 156 - 1) - (130 / 127.5 - 1)
    )


@pytest.mark.asyncio
async def test_missing_data_is_unknown_not_zero_and_reduces_group_coverage():
    db = FakeDB()
    await FactorRegistry(db).seed_builtins()
    results = await FactorEngine(db).calculate_all(
        resolved_data(include_financials=False, include_events=False)
    )
    revenue = next(item for item in results if item.factor_id == "revenue_yoy_v1")
    event = next(item for item in results if item.factor_id == "event_risk_v1")
    assert revenue.raw_value is None and revenue.normalized_score is None
    assert revenue.direction == "UNKNOWN" and revenue.confidence == 0
    assert event.raw_value is None and event.missing_reason
    bundle = aggregate_factors(results)
    assert bundle.group_scores["QUALITY"] is None
    assert bundle.group_scores["EVENT_RISK"] is None
    assert bundle.group_scores["INDUSTRY_STRENGTH"] is None


@pytest.mark.asyncio
async def test_same_factor_identity_with_changed_snapshot_input_fails_closed():
    db = FakeDB()
    await FactorRegistry(db).seed_builtins()
    engine = FactorEngine(db)
    data = resolved_data()
    await engine.calculate_all(data)
    changed = data.model_copy(update={"input_hash": "c" * 64})
    with pytest.raises(DefinitionConflictError):
        await engine.calculate_all(changed)
