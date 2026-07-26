from datetime import date, datetime

import pytest

from app.services.alphaguard.evidence_snapshot_service import calculate_immutable_hash
from app.services.alphaguard.snapshot_data_resolver import (
    SnapshotDataResolver,
    SnapshotResolutionError,
)
from tests.unit.alphaguard._fakes import FakeDB
from tradingagents.alphaguard.evidence_schemas import DataQualityReport, EvidenceSnapshot


async def stored_snapshot(db, *, versioned=True):
    quality = DataQualityReport(
        quality_report_id="quality",
        symbol="600519",
        market="CN",
        trade_date=date(2026, 7, 1),
        status="PASS",
        completeness_score=1,
        freshness_score=1,
        consistency_score=1,
        checked_at=datetime(2026, 7, 1, 15),
    )
    payload = {
        "snapshot_id": "snapshot",
        "user_id": "user",
        "symbol": "600519",
        "market": "CN",
        "trade_date": date(2026, 7, 1),
        "price_cutoff_at": datetime(2026, 7, 1, 15),
        "news_cutoff_at": datetime(2026, 7, 1, 15),
        "announcement_cutoff_at": datetime(2026, 7, 1, 15),
        "price_data_version": "fixed",
        "financial_data_version": "fixed",
        "news_data_version": "fixed",
        "data_quality": quality.model_dump(mode="python"),
        "raw_refs": {
            "prices": ["stock_daily_quotes:p0", "stock_daily_quotes:p1"],
            "financials": ["stock_financial_data:f0", "stock_financial_data:f1"],
            "news": ["stock_news:n0", "stock_news:n1"],
            "trading_calendar": ["trading_calendar:c0"],
        } if versioned else {},
        "factor_version_set": {"factor": "1.0.0"} if versioned else {},
        "strategy_version": "strategy-set-v1" if versioned else None,
        "created_at": datetime(2026, 7, 1, 15),
    }
    draft = EvidenceSnapshot.model_validate({**payload, "immutable_hash": "0" * 64})
    payload = draft.model_dump(mode="python")
    payload["immutable_hash"] = calculate_immutable_hash(draft)
    snapshot = EvidenceSnapshot.model_validate(payload)
    await db["ag_evidence_snapshots"].insert_one(snapshot.model_dump(mode="python"))
    return snapshot


@pytest.mark.asyncio
async def test_resolver_excludes_future_market_financial_and_news_data():
    db = FakeDB()
    await db["stock_daily_quotes"].insert_one(
        {"ref_id": "p0", "trade_date": "2026-07-01", "close": 10}
    )
    await db["stock_daily_quotes"].insert_one(
        {"ref_id": "p1", "trade_date": "2026-07-02", "close": 99}
    )
    await db["stock_financial_data"].insert_one(
        {
            "ref_id": "f0",
            "report_period": "2025-12-31",
            "ann_date": "2026-04-01",
            "revenue": 10,
        }
    )
    await db["stock_financial_data"].insert_one(
        {
            "ref_id": "f1",
            "report_period": "2026-03-31",
            "ann_date": "2026-07-02",
            "revenue": 999,
        }
    )
    await db["stock_news"].insert_one(
        {"ref_id": "n0", "publish_time": "2026-07-01T10:00:00", "title": "known"}
    )
    await db["stock_news"].insert_one(
        {"ref_id": "n1", "publish_time": "2026-07-01T16:00:00", "title": "future"}
    )
    await db["trading_calendar"].insert_one(
        {
            "ref_id": "c0",
            "session_date": "2026-07-02",
            "is_open": True,
            "as_of": "2026-06-01",
        }
    )
    await stored_snapshot(db)
    resolved = await SnapshotDataResolver(db).resolve("snapshot", user_id="user")
    assert [item["ref_id"] for item in resolved.prices] == ["p0"]
    assert [item["ref_id"] for item in resolved.financials] == ["f0"]
    assert [item["ref_id"] for item in resolved.news] == ["n0"]
    assert [item["ref_id"] for item in resolved.trading_calendar] == ["c0"]
    assert set(resolved.excluded_refs) == {
        "stock_daily_quotes:p1",
        "stock_financial_data:f1",
        "stock_news:n1",
    }


@pytest.mark.asyncio
async def test_resolver_rejects_tampered_snapshot_and_unversioned_legacy_by_default():
    db = FakeDB()
    await stored_snapshot(db, versioned=False)
    with pytest.raises(SnapshotResolutionError, match="legacy unversioned"):
        await SnapshotDataResolver(db).resolve("snapshot", user_id="user")
    compatible = await SnapshotDataResolver(db).resolve(
        "snapshot", user_id="user", allow_legacy_unversioned=True
    )
    assert compatible.snapshot.strategy_version is None
    db["ag_evidence_snapshots"].documents[0]["raw_refs"]["prices"] = [
        "stock_daily_quotes:tampered"
    ]
    with pytest.raises(SnapshotResolutionError, match="hash mismatch"):
        await SnapshotDataResolver(db).resolve(
            "snapshot", user_id="user", allow_legacy_unversioned=True
        )
