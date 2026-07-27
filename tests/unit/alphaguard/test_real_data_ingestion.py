from __future__ import annotations

from datetime import date, datetime

import pytest

from app.services.alphaguard.real_data_ingestion_service import (
    CalendarFetchResult,
    CalendarSourceRecord,
    RealDataIngestionService,
    RealDataIntegrityConflict,
)
from app.services.alphaguard.data_quality_gate import DataQualityGate
from tests.unit.alphaguard._fakes import FakeDB


class StubCalendarProvider:
    name = "fixed-provider"

    @staticmethod
    def capability_check():
        return {
            "provider": "fixed-provider",
            "available": True,
            "provider_version": "1.0.0",
        }

    @staticmethod
    def fetch(start, end):
        assert start == date(2026, 7, 24)
        assert end == date(2026, 7, 27)
        records = (
            CalendarSourceRecord(date(2026, 7, 24), True, "CN:2026-07-24"),
            CalendarSourceRecord(date(2026, 7, 25), False, "CN:2026-07-25"),
            CalendarSourceRecord(date(2026, 7, 26), False, "CN:2026-07-26"),
            CalendarSourceRecord(date(2026, 7, 27), True, "CN:2026-07-27"),
        )
        return CalendarFetchResult(
            provider="fixed-provider",
            provider_version="1.0.0",
            records=records,
            raw_response_hash="f" * 64,
        )


@pytest.mark.asyncio
async def test_calendar_sync_is_dry_run_then_idempotent():
    db = FakeDB()
    service = RealDataIngestionService(db)
    kwargs = {
        "start": date(2026, 7, 24),
        "end": date(2026, 7, 27),
        "providers": [StubCalendarProvider()],
        "collected_at": datetime(2026, 7, 27, 12),
    }
    dry = await service.sync_calendar(execute=False, **kwargs)
    assert dry["record_count"] == 4
    assert dry["write"] is False
    assert db["trading_calendar"].documents == []

    created = await service.sync_calendar(execute=True, **kwargs)
    assert created["created"] == 4
    assert created["reused"] == 0
    repeated = await service.sync_calendar(execute=True, **kwargs)
    assert repeated["created"] == 0
    assert repeated["reused"] == 4
    assert len(db["trading_calendar"].documents) == 4
    friday, saturday, _, monday = db["trading_calendar"].documents
    assert friday["is_open"] is True
    assert saturday["is_open"] is False
    assert monday["is_open"] is True
    assert len(friday["content_hash"]) == 64
    assert friday["data_version"].endswith(friday["content_hash"][:16])
    assert repeated["data_version"] == created["data_version"]


@pytest.mark.asyncio
async def test_calendar_sync_rejects_same_identity_different_content():
    db = FakeDB()
    service = RealDataIngestionService(db)
    kwargs = {
        "start": date(2026, 7, 24),
        "end": date(2026, 7, 27),
        "providers": [StubCalendarProvider()],
        "collected_at": datetime(2026, 7, 27, 12),
    }
    await service.sync_calendar(execute=True, **kwargs)
    db["trading_calendar"].documents[0]["content_hash"] = "0" * 64
    with pytest.raises(RealDataIntegrityConflict):
        await service.sync_calendar(execute=True, **kwargs)


@pytest.mark.asyncio
async def test_real_calendar_reference_preserves_namespaced_identity():
    db = FakeDB()
    await RealDataIngestionService(db).sync_calendar(
        start=date(2026, 7, 24),
        end=date(2026, 7, 27),
        providers=[StubCalendarProvider()],
        collected_at=datetime(2026, 7, 27, 12),
        execute=True,
    )

    resolved, invalid = await DataQualityGate().resolve_references(
        db,
        {
            "trading_calendar": [
                "trading_calendar:CN:2026-07-24",
                "trading_calendar:CN:2026-07-27",
            ]
        },
    )

    assert invalid == []
    assert [
        item["calendar_id"] for item in resolved["trading_calendar"]
    ] == ["CN:2026-07-24", "CN:2026-07-27"]
