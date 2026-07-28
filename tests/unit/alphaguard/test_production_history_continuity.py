from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

import app.services.alphaguard.production_history_continuity_service as continuity_module
from app.services.alphaguard.historical_market_context_service import (
    HistoricalMarketFetchResult,
)
from app.services.alphaguard.production_history_continuity_service import (
    ProductionHistoryContinuityError,
    ProductionHistoryContinuityService,
)
from app.services.alphaguard.production_data_config import (
    production_market_context_history_policy,
    production_market_context_policy,
)
from app.services.alphaguard.production_market_context_service import (
    ProductionMarketContextConflict,
)
from tests.unit.alphaguard._fakes import FakeDB


def _at_midnight(value: date) -> datetime:
    return datetime.combine(value, datetime.min.time())


async def _seed_calendar_and_benchmark(
    db: FakeDB,
    *,
    start: date,
    count: int,
) -> list[date]:
    dates = [start + timedelta(days=index) for index in range(count)]
    for index, trade_date in enumerate(dates):
        await db["trading_calendar"].insert_one(
            {
                "market": "CN",
                "session_date": _at_midnight(trade_date),
                "is_open": True,
            }
        )
        close = Decimal("4000") + Decimal(index)
        await db["stock_daily_quotes"].insert_one(
            {
                "ref_id": f"index-000300-{trade_date}",
                "source_record_id": f"000300:{trade_date}:daily",
                "symbol": "000300",
                "market": "CN",
                "period": "daily",
                "trade_date": _at_midnight(trade_date),
                "close": close,
                "adjusted_close": close,
                "price_adjustment_mode": "INDEX_UNADJUSTED_EQUIVALENT",
                "price_data_version": "index-history-v1",
                "available_at": _at_midnight(trade_date).replace(hour=15),
                "provider": "fixed-index",
                "provider_version": "1",
                "content_hash": f"{index:064x}",
            }
        )
    return dates


class BatchMarketProvider:
    name = "fixed-history"

    def __init__(self, *, advance_delta: int = 0):
        self.advance_delta = advance_delta
        self.requested_dates: list[date] = []
        self.fetch_count = 0

    @staticmethod
    def capability_check():
        return {
            "provider": "fixed-history",
            "provider_version": "1.0.0",
            "available": True,
        }

    def fetch(self, *, selected_dates, policy, progress=None):
        self.fetch_count += 1
        self.requested_dates = list(selected_dates)
        normalization = policy["market_context"]["normalization_version"]
        sources = {}
        contexts = {}
        for trade_date in selected_dates:
            rows = [
                {
                    "source_record_id": f"fixed:{trade_date}:{index}",
                    "code": f"sh.600{index:03d}",
                    "trade_status": "1",
                    "pct_change": 1 if index < 60 else -1,
                    "amount": Decimal("100"),
                    "close": Decimal("10"),
                    "new_high_20": False,
                    "new_low_20": False,
                }
                for index in range(100)
            ]
            sources[trade_date] = {
                "market": "CN",
                "trade_date": trade_date,
                "provider": "fixed-history",
                "provider_version": "1.0.0",
                "normalization_version": normalization,
                "source_record_count": 100,
                "expected_universe_count": 100,
                "normalized_records": rows,
                "market_amount_window": [
                    {
                        "trade_date": trade_date - timedelta(days=index + 1),
                        "total_amount": Decimal("10000"),
                    }
                    for index in range(20)
                ],
                "sector_records": [
                    {
                        "source_record_id": f"sector:{trade_date}:{index}",
                        "code": f"sh.0000{index}",
                        "pct_change": 1,
                        "response_hash": "a" * 64,
                    }
                    for index in range(10)
                ],
                "source_response_hashes": {
                    "daily": f"{trade_date:%Y%m%d}".ljust(64, "0")
                },
                "underlying_source": "fixed",
                "universe_provider": "fixed",
                "universe_provider_version": "1",
                "content_hash": "b" * 64,
            }
            contexts[trade_date] = {
                "market": "CN",
                "trade_date": trade_date,
                "available_at": _at_midnight(trade_date).replace(hour=15),
                "provider": "fixed-history",
                "provider_version": "1.0.0",
                "data_version": "fixed-history",
                "advance_count": 60 + self.advance_delta,
                "decline_count": 40,
                "unchanged_count": 0,
                "total_amount": Decimal("10000"),
                "amount_ratio20": Decimal("1"),
                "new_high_count": 1,
                "new_low_count": 1,
                "industry_diffusion": Decimal("0.6"),
                "extreme_risk_flag": False,
                "universe_coverage": Decimal("1"),
                "high_low_coverage": Decimal("1"),
                "sector_coverage": Decimal("1"),
                "calculation_status": "READY",
                "missing_fields": [],
                "methodology": {"breadth": "fixed historical universe"},
            }
        return HistoricalMarketFetchResult(
            provider="fixed-history",
            provider_version="1.0.0",
            normalization_version=normalization,
            source_payloads=sources,
            context_payloads=contexts,
            failures=(),
        )


def test_history_policy_is_versioned_without_mutating_current_policy():
    current = production_market_context_policy()
    history = production_market_context_history_policy()

    assert current["normalization_version"] == (
        "alphaguard-production-market-context-v1.1"
    )
    assert history["normalization_version"] == (
        "alphaguard-production-market-context-history-v1.1"
    )
    assert history["response_hash_scope"] == "DAILY_SOURCE_ROW"
    assert history["calculation_version"] == current["calculation_version"]
    assert history["immutable_hash"] != current["immutable_hash"]


@pytest.mark.asyncio
async def test_history_selects_persisted_prior_sessions_and_fetches_once():
    db = FakeDB()
    dates = await _seed_calendar_and_benchmark(
        db,
        start=date(2026, 5, 1),
        count=70,
    )
    provider = BatchMarketProvider()
    result = await ProductionHistoryContinuityService(db).sync(
        through_trade_date=dates[-1],
        prior_session_count=3,
        execute=False,
        provider=provider,
        now=datetime(2026, 7, 28, 20),
    )

    assert provider.fetch_count == 1
    assert provider.requested_dates == dates[-4:-1]
    assert dates[-1] not in provider.requested_dates
    assert result["selected_trade_date_count"] == 3
    assert result["ready_count"] == 3
    assert db["ag_market_context_sources"].documents == []
    assert db["ag_market_contexts"].documents == []


@pytest.mark.asyncio
async def test_history_is_create_only_and_reuses_first_observation_timestamps():
    db = FakeDB()
    dates = await _seed_calendar_and_benchmark(
        db,
        start=date(2026, 5, 1),
        count=70,
    )
    service = ProductionHistoryContinuityService(db)
    first = await service.sync(
        through_trade_date=dates[-1],
        prior_session_count=2,
        execute=True,
        provider=BatchMarketProvider(),
        now=datetime(2026, 7, 28, 20),
    )
    repeated = await service.sync(
        through_trade_date=dates[-1],
        prior_session_count=2,
        execute=True,
        provider=BatchMarketProvider(),
        now=datetime(2026, 7, 29, 20),
    )

    assert first["context_created"] == 2
    assert repeated["context_created"] == 0
    assert repeated["context_reused"] == 2
    assert len(db["ag_market_context_sources"].documents) == 2
    assert len(db["ag_market_contexts"].documents) == 2
    assert {
        item["collected_at"]
        for item in db["ag_market_contexts"].documents
    } == {datetime(2026, 7, 28, 20)}


@pytest.mark.asyncio
async def test_history_same_identity_with_changed_content_conflicts():
    db = FakeDB()
    dates = await _seed_calendar_and_benchmark(
        db,
        start=date(2026, 5, 1),
        count=70,
    )
    service = ProductionHistoryContinuityService(db)
    kwargs = {
        "through_trade_date": dates[-1],
        "prior_session_count": 1,
        "execute": True,
        "now": datetime(2026, 7, 28, 20),
    }
    await service.sync(provider=BatchMarketProvider(), **kwargs)

    with pytest.raises(ProductionMarketContextConflict):
        await service.sync(
            provider=BatchMarketProvider(advance_delta=1),
            **kwargs,
        )


@pytest.mark.asyncio
async def test_history_refuses_incomplete_calendar_window():
    db = FakeDB()
    await db["trading_calendar"].insert_one(
        {
            "market": "CN",
            "session_date": datetime(2026, 7, 28),
            "is_open": True,
        }
    )
    with pytest.raises(
        ProductionHistoryContinuityError,
        match="lacks the required continuous history",
    ):
        await ProductionHistoryContinuityService(db).select_trade_dates(
            through_trade_date=date(2026, 7, 28),
            prior_session_count=120,
        )


@pytest.mark.asyncio
async def test_qfq_audit_reports_version_seam_without_modifying_labels():
    db = FakeDB()
    start = date(2026, 6, 30)
    end = date(2026, 7, 2)
    for trade_date in (start, date(2026, 7, 1), end):
        await db["trading_calendar"].insert_one(
            {
                "market": "CN",
                "session_date": _at_midnight(trade_date),
                "is_open": True,
            }
        )
        await db["stock_daily_quotes"].insert_one(
            {
                "ref_id": f"price-600519-{trade_date}",
                "symbol": "600519",
                "market": "CN",
                "period": "daily",
                "trade_date": _at_midnight(trade_date),
                "price_adjustment_mode": "QFQ",
                "price_data_version": (
                    "qfq-v2" if trade_date == end else "qfq-v1"
                ),
            }
        )
    await db["ag_eval_subjects"].insert_one(
        {
            "subject_id": "subject-1",
            "symbol": "600519",
            "market": "CN",
            "decision_trade_date": _at_midnight(start),
            "lineage_ids": {"backfill_run_id": "canonical"},
        }
    )
    await db["ag_eval_horizon_labels"].insert_one(
        {
            "label_id": "label-1",
            "subject_id": "subject-1",
            "horizon": "20D",
            "anchor_type": "DECISION_CLOSE",
            "horizon_end_date": _at_midnight(end),
            "price_data_version": "unavailable",
            "status": "PENDING",
            "input_hash": "a" * 64,
        }
    )
    terminal = {
        "label_id": "mature-label",
        "subject_id": "subject-1",
        "horizon": "20D",
        "anchor_type": "PLANNED_ENTRY",
        "status": "CALCULATED",
        "input_hash": "b" * 64,
    }
    await db["ag_eval_horizon_labels"].insert_one(terminal)

    result = await ProductionHistoryContinuityService(
        db
    ).audit_pending_20d(backfill_run_id="canonical")

    assert result["pending_label_count"] == 1
    assert result["labels"][0]["safe_resolution"] == (
        "PENDING_VERSION_DISCONTINUITY"
    )
    assert result["labels"][0]["discontinuities"][0]["trade_date"] == end
    assert result["labels"][0]["missing_dates"] == []
    assert (
        await db["ag_eval_horizon_labels"].find_one(
            {"label_id": "mature-label"}
        )
    )["input_hash"] == terminal["input_hash"]


@pytest.mark.asyncio
async def test_regime_verification_uses_locked_version_without_persistence(
    monkeypatch,
):
    db = FakeDB()
    await db["ag_evidence_snapshots"].insert_one(
        {
            "snapshot_id": "snapshot-1",
            "user_id": "user-1",
            "symbol": "600519",
            "market": "CN",
            "trade_date": datetime(2026, 7, 28),
        }
    )
    await db["ag_regime_results"].insert_one(
        {
            "regime_result_id": "regime-result-1",
            "snapshot_id": "snapshot-1",
            "regime_version": "regime:market-regime-v1",
            "calculation_status": "INSUFFICIENT_DATA",
            "input_hash": "a" * 64,
        }
    )
    resolved = SimpleNamespace(
        snapshot=SimpleNamespace(
            snapshot_id="snapshot-1",
            user_id="user-1",
            symbol="600519",
            market_context_id="context-1",
            champion_version_refs={"slot": "locked-version"},
        ),
        benchmark_prices=[{"close": 1}],
    )

    class StubResolver:
        def __init__(self, _db):
            pass

        async def resolve(self, snapshot_id, user_id):
            assert snapshot_id == "snapshot-1"
            assert user_id == "user-1"
            return resolved

    class StubPipeline:
        def __init__(self, _db):
            pass

        async def _locked_champion_inputs(self, refs):
            assert refs == {"slot": "locked-version"}
            return (
                {},
                "factor-set",
                {"regime_version": "regime:market-regime-v1"},
                [],
            )

    monkeypatch.setattr(
        continuity_module,
        "SnapshotDataResolver",
        StubResolver,
    )
    monkeypatch.setattr(
        continuity_module,
        "QuantResearchPipeline",
        StubPipeline,
    )
    monkeypatch.setattr(
        continuity_module,
        "calculate_regime_result",
        lambda data, config: SimpleNamespace(
            regime_result_id="regime-result-1",
            input_hash="a" * 64,
            calculation_status="INSUFFICIENT_DATA",
        ),
    )

    before = list(db["ag_regime_results"].documents)
    result = await ProductionHistoryContinuityService(
        db
    ).verify_locked_regimes(trade_date=date(2026, 7, 28))

    assert result["verified_unchanged_count"] == 1
    assert result["integrity_conflict_count"] == 0
    assert result["missing_result_count"] == 0
    assert db["ag_regime_results"].documents == before
