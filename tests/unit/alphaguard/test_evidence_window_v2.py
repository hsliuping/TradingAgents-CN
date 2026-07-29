from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.services.alphaguard.benchmark_price_window_service import (
    BenchmarkPriceWindowConflict,
    BenchmarkPriceWindowError,
    BenchmarkPriceWindowService,
)
from app.services.alphaguard.data_quality_gate import DataQualityGate
from app.services.alphaguard.evidence_snapshot_service import (
    EvidenceSnapshotService,
    calculate_immutable_hash,
)
from app.services.alphaguard.snapshot_data_resolver import (
    SnapshotDataResolver,
    SnapshotResolutionError,
)
from tradingagents.alphaguard.evidence_schemas import (
    EVIDENCE_SNAPSHOT_SCHEMA_VERSION,
    EVIDENCE_SNAPSHOT_SCHEMA_VERSION_V2,
    DataQualityReport,
    EvidenceSnapshot,
)
from tradingagents.alphaguard.production_data_schemas import (
    BenchmarkPriceWindowManifest,
    production_data_hash,
)
from tests.unit.alphaguard._fakes import FakeDB


AS_OF = date(2026, 7, 29)
CUTOFF = datetime(2026, 7, 29, 20)


def _dates(count: int = 61) -> list[date]:
    return [AS_OF - timedelta(days=count - index - 1) for index in range(count)]


async def _seed_window(db: FakeDB, *, count: int = 61) -> list[date]:
    dates = _dates(count)
    for index, trade_date in enumerate(dates):
        await db["trading_calendar"].insert_one(
            {
                "calendar_id": f"CN:{trade_date.isoformat()}",
                "market": "CN",
                "session_date": datetime.combine(
                    trade_date, datetime.min.time()
                ),
                "is_open": True,
            }
        )
        version = "normalized-v2" if index >= count - 2 else "legacy-v1"
        await db["stock_daily_quotes"].insert_one(
            {
                "ref_id": f"index-{trade_date.isoformat()}",
                "symbol": "000300",
                "market": "CN",
                "trade_date": datetime.combine(
                    trade_date, datetime.min.time()
                ),
                "period": "daily",
                "close": 100 + index,
                "adjustment_mode": "INDEX_UNADJUSTED_EQUIVALENT",
                "price_adjustment_mode": "INDEX_UNADJUSTED_EQUIVALENT",
                "provider": "baostock",
                "provider_version": "00.9.30",
                "price_data_version": version,
                "data_version": version,
                "available_at": datetime.combine(
                    trade_date, datetime.min.time()
                ).replace(hour=15),
                "collected_at": datetime(2026, 7, 29, 18),
                "content_hash": f"{index + 1:064x}",
            }
        )
    return dates


@pytest.mark.asyncio
async def test_benchmark_manifest_locks_61_ordered_rows_create_only_and_reuses():
    db = FakeDB()
    dates = await _seed_window(db)
    service = BenchmarkPriceWindowService(db)
    preview = await service.build(
        as_of_trade_date=AS_OF,
        cutoff_at=CUTOFF,
        execute=False,
    )
    assert preview["action"] == "WOULD_CREATE"
    assert not db[service.COLLECTION].documents

    created = await service.build(
        as_of_trade_date=AS_OF,
        cutoff_at=CUTOFF,
        execute=True,
    )
    reused = await service.build(
        as_of_trade_date=AS_OF,
        cutoff_at=CUTOFF + timedelta(minutes=1),
        execute=True,
    )
    assert created["action"] == "CREATED"
    assert reused["action"] == "REUSED"
    assert created["manifest"]["ordered_trade_dates"] == [
        item.isoformat() for item in dates
    ]
    assert created["manifest"]["actual_count"] == 61
    assert len(created["manifest"]["price_data_versions"]) == 2
    assert (
        created["manifest"]["manifest_hash"]
        == reused["manifest"]["manifest_hash"]
    )


@pytest.mark.asyncio
async def test_manifest_readiness_uses_source_availability_not_creation_time():
    db = FakeDB()
    await _seed_window(db)
    service = BenchmarkPriceWindowService(db)
    built = await service.build(
        as_of_trade_date=AS_OF,
        cutoff_at=CUTOFF,
        execute=True,
    )
    db[service.COLLECTION].documents[0]["created_at"] = (
        CUTOFF + timedelta(days=1)
    )

    ready = await service.get_ready(
        as_of_trade_date=AS_OF,
        cutoff_at=CUTOFF,
    )

    assert ready.manifest_id == built["manifest"]["manifest_id"]


@pytest.mark.asyncio
async def test_benchmark_manifest_rejects_missing_future_and_version_semantics():
    db = FakeDB()
    await _seed_window(db)
    db["stock_daily_quotes"].documents[-1]["provider"] = "other"
    with pytest.raises(
        BenchmarkPriceWindowError,
        match="provider discontinuity",
    ):
        await BenchmarkPriceWindowService(db).build(
            as_of_trade_date=AS_OF,
            cutoff_at=CUTOFF,
            execute=True,
        )

    db = FakeDB()
    await _seed_window(db, count=60)
    with pytest.raises(
        BenchmarkPriceWindowError,
        match="calendar window is incomplete",
    ):
        await BenchmarkPriceWindowService(db).build(
            as_of_trade_date=AS_OF,
            cutoff_at=CUTOFF,
            execute=True,
        )


@pytest.mark.asyncio
async def test_benchmark_manifest_detects_same_identity_changed_content():
    db = FakeDB()
    await _seed_window(db)
    service = BenchmarkPriceWindowService(db)
    await service.build(
        as_of_trade_date=AS_OF,
        cutoff_at=CUTOFF,
        execute=True,
    )
    db["stock_daily_quotes"].documents[-1]["content_hash"] = "f" * 64
    with pytest.raises(
        BenchmarkPriceWindowConflict,
        match="INTEGRITY_CONFLICT",
    ):
        await service.build(
            as_of_trade_date=AS_OF,
            cutoff_at=CUTOFF,
            execute=True,
        )
    assert len(db[service.COLLECTION].documents) == 1


def _quality() -> DataQualityReport:
    return DataQualityReport(
        quality_report_id="quality-v2",
        symbol="600519",
        market="CN",
        trade_date=AS_OF,
        status="PASS",
        completeness_score=1,
        freshness_score=1,
        consistency_score=1,
        checked_at=CUTOFF,
    )


def _v1_data() -> dict:
    return {
        "snapshot_id": "legacy-snapshot",
        "user_id": "user-1",
        "symbol": "600519",
        "market": "CN",
        "trade_date": AS_OF,
        "price_cutoff_at": CUTOFF,
        "news_cutoff_at": CUTOFF,
        "announcement_cutoff_at": CUTOFF,
        "price_data_version": "price-v1",
        "financial_data_version": "financial-v1",
        "news_data_version": "news-v1",
        "market_context_id": "context-1",
        "data_quality": _quality().model_dump(mode="python"),
        "raw_refs": {
            "prices": ["stock_daily_quotes:price-1"],
            "benchmark_prices": [
                "index_daily:index-1",
                "index_daily:index-2",
            ],
        },
        "created_at": CUTOFF,
        "schema_version": EVIDENCE_SNAPSHOT_SCHEMA_VERSION,
    }


def _v2_data() -> dict:
    benchmark_refs = [
        f"index_daily:index-{index:02d}" for index in range(61)
    ]
    return {
        **_v1_data(),
        "snapshot_id": "snapshot-v2",
        "schema_version": EVIDENCE_SNAPSHOT_SCHEMA_VERSION_V2,
        "market_context_hash": "1" * 64,
        "market_context_window_manifest_id": "context-window-1",
        "market_context_window_manifest_hash": "2" * 64,
        "benchmark_price_window_manifest_id": "benchmark-window-1",
        "benchmark_price_window_manifest_hash": "3" * 64,
        "required_benchmark_count": 61,
        "actual_benchmark_count": 61,
        "evidence_contract_status": "COMPLETE",
        "raw_refs": {
            "prices": ["stock_daily_quotes:price-1"],
            "benchmark_prices": benchmark_refs,
            "market_context_window": [
                "market_context_window:context-window-1"
            ],
            "benchmark_price_window": [
                "benchmark_price_window:benchmark-window-1"
            ],
        },
    }


def _with_hash(data: dict) -> EvidenceSnapshot:
    value = deepcopy(data)
    value["immutable_hash"] = "0" * 64
    normalized = EvidenceSnapshot.model_validate(value)
    value = normalized.model_dump(mode="python")
    value["immutable_hash"] = calculate_immutable_hash(normalized)
    return EvidenceSnapshot.model_validate(value)


def test_snapshot_v1_remains_readable_and_hash_compatible():
    legacy = _with_hash(_v1_data())
    assert legacy.schema_version == EVIDENCE_SNAPSHOT_SCHEMA_VERSION
    assert legacy.required_benchmark_count is None
    assert EvidenceSnapshotService.verify_integrity(legacy)


def test_snapshot_v2_requires_complete_contract_and_hashes_manifest_fields():
    v2 = _with_hash(_v2_data())
    changed = _v2_data()
    changed["benchmark_price_window_manifest_hash"] = "4" * 64
    changed = _with_hash(changed)
    assert v2.immutable_hash != changed.immutable_hash
    assert EvidenceSnapshotService.verify_integrity(v2)

    incomplete = _v2_data()
    incomplete["raw_refs"]["benchmark_prices"].pop()
    incomplete["immutable_hash"] = "0" * 64
    with pytest.raises(ValidationError, match="benchmark raw reference count"):
        EvidenceSnapshot.model_validate(incomplete)


def test_data_quality_cannot_pass_with_two_of_61_benchmark_rows():
    report = DataQualityGate().evaluate_documents(
        symbol="600519",
        market="CN",
        trade_date=AS_OF,
        price_cutoff_at=CUTOFF,
        news_cutoff_at=CUTOFF,
        announcement_cutoff_at=CUTOFF,
        resolved={
            "prices": [
                {
                    "trade_date": AS_OF,
                    "open": 10,
                    "high": 11,
                    "low": 9,
                    "close": 10,
                    "volume": 1,
                    "amount": 10,
                }
            ],
            "benchmark_prices": [{}, {}],
            "financials": [{}],
            "news": [{}],
        },
        invalid_refs=[],
        required_sources=["prices", "benchmark_prices"],
        required_source_counts={"benchmark_prices": 61},
    )
    assert report.status == "FAIL"
    assert "required benchmark_prices evidence count is 2/61" in (
        report.blocking_reasons
    )


def test_manifest_schema_rejects_future_or_unordered_dates():
    dates = _dates()
    payload = {
        "manifest_id": "manifest-1",
        "ref_id": "manifest-1",
        "market": "CN",
        "benchmark_symbol": "000300",
        "as_of_trade_date": AS_OF,
        "required_count": 61,
        "actual_count": 61,
        "adjustment_mode": "INDEX_UNADJUSTED_EQUIVALENT",
        "provider": "baostock",
        "provider_version": "00.9.30",
        "price_data_versions": ["v1"],
        "ordered_price_data_versions": ["v1"] * 61,
        "version_compatibility_policy": "same-provider-v1",
        "version_compatibility_status": "COMPATIBLE",
        "ordered_trade_dates": dates,
        "ordered_quote_ids": [f"quote-{index}" for index in range(61)],
        "ordered_quote_hashes": [f"{index + 1:064x}" for index in range(61)],
        "start_trade_date": dates[0],
        "end_trade_date": dates[-1],
        "source_hash": "a" * 64,
        "manifest_hash": "b" * 64,
        "available_at": CUTOFF,
        "created_at": CUTOFF,
    }
    BenchmarkPriceWindowManifest.model_validate(payload)
    payload["ordered_trade_dates"][-1] = AS_OF + timedelta(days=1)
    payload["end_trade_date"] = AS_OF + timedelta(days=1)
    with pytest.raises(ValidationError, match="as-of trade date"):
        BenchmarkPriceWindowManifest.model_validate(payload)


def test_frontend_distinguishes_legacy_and_complete_evidence_contracts():
    root = Path(__file__).resolve().parents[3]
    candidates = (
        root / "frontend/src/views/AlphaGuard/Candidates.vue"
    ).read_text(encoding="utf-8")
    decisions = (
        root / "frontend/src/views/AlphaGuard/Decisions.vue"
    ).read_text(encoding="utf-8")
    api = (root / "frontend/src/api/alphaguard.ts").read_text(
        encoding="utf-8"
    )
    for source in (candidates, decisions):
        assert "LEGACY_EVIDENCE_INCOMPLETE" in source
        assert "Benchmark Window" in source
        assert "Evidence Contract" in source
    assert "benchmark_price_window_manifest_id" in api
    assert "evidence_contract_status" in api


@pytest.mark.asyncio
async def test_regime_input_resolver_uses_only_locked_quote_ids_and_hashes():
    db = FakeDB()
    await _seed_window(db)
    manifest_result = await BenchmarkPriceWindowService(db).build(
        as_of_trade_date=AS_OF,
        cutoff_at=CUTOFF,
        execute=True,
    )
    manifest = manifest_result["manifest"]
    await db["stock_daily_quotes"].insert_one(
        {
            "ref_id": "price-target",
            "symbol": "600519",
            "market": "CN",
            "trade_date": datetime.combine(AS_OF, datetime.min.time()),
            "period": "daily",
            "open": 10,
            "high": 11,
            "low": 9,
            "close": 10,
            "volume": 100,
            "amount": 1000,
        }
    )
    # This newer-looking row has the same benchmark identity/date shape but is
    # not named by the Manifest and therefore must never enter the resolver.
    await db["stock_daily_quotes"].insert_one(
        {
            "ref_id": "latest-unlocked",
            "symbol": "000300",
            "market": "CN",
            "trade_date": datetime.combine(AS_OF, datetime.min.time()),
            "period": "daily",
            "close": 9999,
            "content_hash": "f" * 64,
        }
    )
    await db["ag_market_contexts"].insert_one(
        {
            "context_id": "context-current",
            "ref_id": "context-current",
            "market": "CN",
            "trade_date": datetime.combine(AS_OF, datetime.min.time()),
            "content_hash": "4" * 64,
        }
    )
    context_manifest_document = {
        "manifest_id": "context-window",
        "ref_id": "context-window",
        "market": "CN",
        "as_of_trade_date": AS_OF,
        "required_count": 1,
        "actual_count": 1,
        "ordered_trade_dates": [AS_OF],
        "ordered_context_ids": ["context-current"],
        "ordered_context_hashes": ["4" * 64],
        "context_version": "production-market-context-calculation-v1.1",
        "window_start": AS_OF,
        "window_end": AS_OF,
        "source_hash": "5" * 64,
        "available_at": datetime(2026, 7, 29, 16),
        "created_at": datetime(2026, 7, 29, 17),
    }
    context_manifest_document["manifest_hash"] = production_data_hash(
        context_manifest_document,
        exclude={"created_at"},
    )
    context_manifest_document["schema_version"] = (
        "alphaguard-production-data-v1"
    )
    await db["ag_market_context_window_manifests"].insert_one(
        context_manifest_document
    )
    snapshot = await EvidenceSnapshotService(
        db=db,
        enable_shadow_hook=False,
    ).create(
        user_id="user-1",
        payload={
            "symbol": "600519",
            "market": "CN",
            "trade_date": AS_OF,
            "price_cutoff_at": CUTOFF,
            "news_cutoff_at": CUTOFF,
            "announcement_cutoff_at": CUTOFF,
            "price_data_version": "fixed",
            "financial_data_version": "fixed",
            "news_data_version": "fixed",
            "market_context_id": "context-current",
            "market_context_hash": "4" * 64,
            "market_context_window_manifest_id": "context-window",
            "market_context_window_manifest_hash": (
                context_manifest_document["manifest_hash"]
            ),
            "benchmark_price_window_manifest_id": manifest["manifest_id"],
            "benchmark_price_window_manifest_hash": manifest["manifest_hash"],
            "required_benchmark_count": 61,
            "actual_benchmark_count": 61,
            "evidence_contract_status": "COMPLETE",
            "raw_refs": {
                "prices": ["stock_daily_quotes:price-target"],
                "benchmark_prices": [
                    f"index_daily:{item}"
                    for item in manifest["ordered_quote_ids"]
                ],
                "market_context": [
                    "market_context:context-current"
                ],
                "market_context_window": [
                    "market_context_window:context-window"
                ],
                "benchmark_price_window": [
                    "benchmark_price_window:"
                    f"{manifest['manifest_id']}"
                ],
            },
            "required_sources": [
                "prices",
                "benchmark_prices",
                "market_context",
                "market_context_window",
                "benchmark_price_window",
            ],
            "schema_version": EVIDENCE_SNAPSHOT_SCHEMA_VERSION_V2,
        },
    )
    resolved = await SnapshotDataResolver(db).resolve(
        snapshot.snapshot_id,
        user_id="user-1",
        allow_legacy_unversioned=True,
    )
    assert len(resolved.benchmark_prices) == 61
    assert all(
        item.get("ref_id") != "latest-unlocked"
        for item in resolved.benchmark_prices
    )

    benchmark_manifest_document = db[
        "ag_benchmark_price_window_manifests"
    ].documents[0]
    original_quote_id = benchmark_manifest_document[
        "ordered_quote_ids"
    ][0]
    benchmark_manifest_document["ordered_quote_ids"][0] = "tampered-quote"
    with pytest.raises(
        SnapshotResolutionError,
        match="benchmark manifest content hash mismatch",
    ):
        await SnapshotDataResolver(db).resolve(
            snapshot.snapshot_id,
            user_id="user-1",
            allow_legacy_unversioned=True,
        )
    benchmark_manifest_document["ordered_quote_ids"][0] = original_quote_id

    context_manifest_document = db[
        "ag_market_context_window_manifests"
    ].documents[0]
    original_context_hash = context_manifest_document[
        "ordered_context_hashes"
    ][0]
    context_manifest_document["ordered_context_hashes"][0] = "7" * 64
    with pytest.raises(
        SnapshotResolutionError,
        match="MarketContext manifest content hash mismatch",
    ):
        await SnapshotDataResolver(db).resolve(
            snapshot.snapshot_id,
            user_id="user-1",
            allow_legacy_unversioned=True,
        )
    context_manifest_document["ordered_context_hashes"][
        0
    ] = original_context_hash

    locked = db["stock_daily_quotes"].documents[0]
    locked["content_hash"] = "e" * 64
    with pytest.raises(SnapshotResolutionError, match="do not match"):
        await SnapshotDataResolver(db).resolve(
            snapshot.snapshot_id,
            user_id="user-1",
            allow_legacy_unversioned=True,
        )
