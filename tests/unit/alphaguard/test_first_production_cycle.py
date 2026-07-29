from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from app.services.alphaguard.data_quality_gate import DataQualityGate
from app.services.alphaguard.market_context_window_service import (
    MarketContextWindowConflict,
    MarketContextWindowError,
    MarketContextWindowService,
)
from app.services.alphaguard.paper_storage import mongo_date
from tests.unit.alphaguard._fakes import FakeDB


async def _seed_window(db: FakeDB, *, count: int = 3) -> list[date]:
    start = date(2026, 7, 27)
    dates = [start + timedelta(days=index) for index in range(count)]
    for index, trade_date in enumerate(dates):
        await db["trading_calendar"].insert_one(
            {
                "calendar_id": f"CN:{trade_date}",
                "market": "CN",
                "session_date": mongo_date(trade_date),
                "is_open": True,
            }
        )
        await db["ag_market_contexts"].insert_one(
            {
                "context_id": f"context-{index}",
                "ref_id": f"context-{index}",
                "market": "CN",
                "trade_date": mongo_date(trade_date),
                "available_at": datetime.combine(
                    trade_date, datetime.min.time()
                ).replace(hour=15, minute=5),
                "collected_at": datetime.combine(
                    trade_date, datetime.min.time()
                ).replace(hour=15, minute=10),
                "calculation_status": "READY",
                "calculation_version": "production-market-context-calculation-v1.1",
                "content_hash": f"{index + 1:064x}",
            }
        )
    return dates


@pytest.mark.asyncio
async def test_context_window_is_dry_run_first_create_only_and_idempotent():
    db = FakeDB()
    dates = await _seed_window(db)
    cutoff = datetime(2026, 7, 29, 18)
    service = MarketContextWindowService(db)

    preview = await service.build(
        as_of_trade_date=dates[-1],
        cutoff_at=cutoff,
        execute=False,
        prior_session_count=2,
    )
    assert preview["action"] == "WOULD_CREATE"
    assert await db[service.COLLECTION].find_one({}) is None

    created = await service.build(
        as_of_trade_date=dates[-1],
        cutoff_at=cutoff,
        execute=True,
        prior_session_count=2,
    )
    reused = await service.build(
        as_of_trade_date=dates[-1],
        cutoff_at=cutoff + timedelta(minutes=1),
        execute=True,
        prior_session_count=2,
    )
    assert created["action"] == "CREATED"
    assert reused["action"] == "REUSED"
    assert created["manifest"]["manifest_hash"] == reused["manifest"]["manifest_hash"]
    assert reused["manifest"]["ordered_trade_dates"] == [
        item.isoformat() for item in dates
    ]
    assert len(db[service.COLLECTION].documents) == 1


@pytest.mark.asyncio
async def test_context_window_fails_closed_on_gap_or_version_conflict():
    db = FakeDB()
    dates = await _seed_window(db)
    db["ag_market_contexts"].documents.pop(1)
    service = MarketContextWindowService(db)
    with pytest.raises(MarketContextWindowError, match="REGIME_INPUT_NOT_READY"):
        await service.build(
            as_of_trade_date=dates[-1],
            cutoff_at=datetime(2026, 7, 29, 18),
            execute=True,
            prior_session_count=2,
        )
    assert not db[service.COLLECTION].documents


@pytest.mark.asyncio
async def test_context_window_detects_same_identity_changed_content():
    db = FakeDB()
    dates = await _seed_window(db)
    cutoff = datetime(2026, 7, 29, 18)
    service = MarketContextWindowService(db)
    await service.build(
        as_of_trade_date=dates[-1],
        cutoff_at=cutoff,
        execute=True,
        prior_session_count=2,
    )
    db["ag_market_contexts"].documents[-1]["content_hash"] = "f" * 64

    with pytest.raises(MarketContextWindowConflict, match="INTEGRITY_CONFLICT"):
        await service.build(
            as_of_trade_date=dates[-1],
            cutoff_at=cutoff + timedelta(minutes=1),
            execute=True,
            prior_session_count=2,
        )
    assert len(db[service.COLLECTION].documents) == 1


def test_context_window_is_a_blocking_snapshot_requirement():
    report = DataQualityGate().evaluate_documents(
        symbol="600519",
        market="CN",
        trade_date=date(2026, 7, 29),
        price_cutoff_at=datetime(2026, 7, 29, 18),
        news_cutoff_at=datetime(2026, 7, 29, 18),
        announcement_cutoff_at=datetime(2026, 7, 29, 18),
        resolved={},
        invalid_refs=[],
        required_sources=["market_context_window"],
    )
    assert report.status == "FAIL"
    assert (
        "required production MarketContext window is unavailable"
        in report.blocking_reasons
    )
