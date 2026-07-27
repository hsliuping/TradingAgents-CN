from copy import deepcopy
from datetime import date, datetime, timedelta

import pytest

from app.routers.alphaguard import router
from app.services.alphaguard.data_quality_gate import DataQualityGate
from app.services.alphaguard.evidence_snapshot_service import (
    DataQualityBlockedError,
    EvidenceSnapshotService,
    SnapshotValidationError,
    calculate_immutable_hash,
)
from tradingagents.alphaguard.evidence_schemas import (
    ALPHAGUARD_CODE_VERSION,
    EVIDENCE_SNAPSHOT_SCHEMA_VERSION,
    DataQualityReport,
    EvidenceSnapshot,
)

from tests.unit.alphaguard._fakes import FakeDB


TRADE_DATE = date(2026, 7, 24)
CUTOFF = datetime(2026, 7, 24, 18, 0, 0)


def valid_price(**overrides):
    document = {
        "code": "600519",
        "trade_date": "2026-07-24",
        "open": 100.0,
        "high": 110.0,
        "low": 95.0,
        "close": 105.0,
        "volume": 1000,
        "amount": 105000,
    }
    document.update(overrides)
    return document


def resolved_evidence(price=None, *, include_optional=True):
    result = {"prices": [price or valid_price()]}
    if include_optional:
        result["financials"] = [{"code": "600519", "report_date": "2026-03-31"}]
        result["news"] = [
            {
                "news_id": "news-1",
                "published_at": "2026-07-24T15:00:00",
            }
        ]
    return result


def evaluate(resolved, invalid_refs=None):
    return DataQualityGate().evaluate_documents(
        symbol="600519",
        market="CN",
        trade_date=TRADE_DATE,
        price_cutoff_at=CUTOFF,
        news_cutoff_at=CUTOFF,
        announcement_cutoff_at=CUTOFF,
        resolved=resolved,
        invalid_refs=invalid_refs or [],
    )


def quality(status="PASS"):
    return DataQualityReport(
        quality_report_id="quality-1",
        symbol="600519",
        market="CN",
        trade_date=TRADE_DATE,
        status=status,
        completeness_score=1,
        freshness_score=1,
        consistency_score=1,
        missing_fields=[],
        stale_sources=[],
        anomalies=[],
        blocking_reasons=["blocked"] if status == "FAIL" else [],
        checked_at=CUTOFF,
    )


def snapshot_data(**overrides):
    data = {
        "snapshot_id": "snapshot-1",
        "user_id": "user-1",
        "analysis_id": None,
        "symbol": "600519",
        "market": "CN",
        "trade_date": TRADE_DATE,
        "price_cutoff_at": CUTOFF,
        "news_cutoff_at": CUTOFF,
        "announcement_cutoff_at": CUTOFF,
        "price_data_version": "prices-v1",
        "financial_data_version": "financial-v1",
        "news_data_version": "news-v1",
        "account_snapshot_id": None,
        "market_context_id": None,
        "data_quality": quality().model_dump(mode="python"),
        "raw_refs": {
            "prices": ["market_quotes:600519:2026-07-24"],
            "financials": ["financial_data:600519:2026Q1"],
            "news": ["stock_news:news-1"],
        },
        "factor_version_set": {},
        "strategy_version": None,
        "normal_model_version": None,
        "top_model_version": None,
        "prompt_versions": {
            "normal_trade_plan": "normal_trade_plan_v1",
            "top_review_decision": "top_review_decision_v1",
        },
        "created_at": CUTOFF,
        "schema_version": EVIDENCE_SNAPSHOT_SCHEMA_VERSION,
        "code_version": ALPHAGUARD_CODE_VERSION,
    }
    data.update(overrides)
    data["immutable_hash"] = calculate_immutable_hash(data)
    return data


def create_payload(**overrides):
    payload = {
        "analysis_id": None,
        "symbol": "600519",
        "market": "CN",
        "trade_date": TRADE_DATE,
        "price_cutoff_at": CUTOFF,
        "news_cutoff_at": CUTOFF,
        "announcement_cutoff_at": CUTOFF,
        "price_data_version": "prices-v1",
        "financial_data_version": "financial-v1",
        "news_data_version": "news-v1",
        "account_snapshot_id": None,
        "market_context_id": None,
        "raw_refs": {"prices": ["market_quotes:600519:2026-07-24"]},
        "required_sources": ["prices"],
        "normal_model_version": None,
        "top_model_version": None,
        "prompt_versions": {
            "normal_trade_plan": "normal_trade_plan_v1",
            "top_review_decision": "top_review_decision_v1",
        },
        "factor_version_set": {},
        "strategy_version": None,
    }
    payload.update(overrides)
    return payload


class StubGate:
    def __init__(self, report):
        self.report = report
        self.calls = 0

    async def evaluate(self, **kwargs):
        self.calls += 1
        return self.report


def test_normal_data_passes_quality_gate():
    report = evaluate(resolved_evidence())
    assert report.status == "PASS"
    assert report.blocking_reasons == []


def test_non_blocking_optional_absence_warns():
    report = evaluate(resolved_evidence(include_optional=False))
    assert report.status == "WARN"
    assert "financials" in report.missing_fields


def test_missing_core_price_fails():
    report = evaluate({"prices": [], "financials": [{}], "news": [{}]})
    assert report.status == "FAIL"
    assert report.blocking_reasons


@pytest.mark.parametrize(
    "price",
    [
        valid_price(high=99),
        valid_price(low=106),
        valid_price(volume=-1),
        valid_price(open=0),
    ],
)
def test_invalid_ohlc_or_volume_fails(price):
    report = evaluate(resolved_evidence(price))
    assert report.status == "FAIL"


def test_future_price_or_news_fails():
    price_report = evaluate(
        resolved_evidence(valid_price(trade_date="2026-07-25"))
    )
    news = resolved_evidence()
    news["news"][0]["published_at"] = "2026-07-24T19:00:00"
    news_report = evaluate(news)
    assert price_report.status == "FAIL"
    assert news_report.status == "FAIL"


def test_unresolved_reference_fails():
    report = evaluate(resolved_evidence(), ["stock_news:missing"])
    assert report.status == "FAIL"
    assert any("unresolved reference" in item for item in report.anomalies)


def test_hash_is_stable_and_sensitive_to_content():
    first = snapshot_data()
    same = deepcopy(first)
    assert calculate_immutable_hash(first) == calculate_immutable_hash(same)
    changed = deepcopy(first)
    changed["news_cutoff_at"] = CUTOFF + timedelta(minutes=1)
    assert calculate_immutable_hash(first) != calculate_immutable_hash(changed)


def test_evidence_snapshot_is_frozen_and_tampering_is_detected():
    snapshot = EvidenceSnapshot.model_validate(snapshot_data())
    with pytest.raises(Exception):
        snapshot.snapshot_id = "changed"
    tampered = snapshot.model_dump(mode="python")
    tampered["raw_refs"]["prices"].append("market_quotes:other:2026-07-24")
    assert EvidenceSnapshotService.verify_integrity(tampered) is False


@pytest.mark.asyncio
async def test_legal_snapshot_creation_succeeds():
    db = FakeDB()
    gate = StubGate(quality("PASS"))
    snapshot = await EvidenceSnapshotService(db, gate).create(
        user_id="user-1", payload=create_payload()
    )
    assert snapshot.data_quality.status == "PASS"
    assert EvidenceSnapshotService.verify_integrity(snapshot)


@pytest.mark.asyncio
async def test_snapshot_hash_uses_schema_normalized_reference_order():
    db = FakeDB()
    gate = StubGate(quality("PASS"))
    payload = create_payload(
        raw_refs={
            "prices": [
                "market_quotes:z:2026-07-24",
                "market_quotes:a:2026-07-24",
                "market_quotes:z:2026-07-24",
            ]
        }
    )

    snapshot = await EvidenceSnapshotService(db, gate).create(
        user_id="user-1",
        payload=payload,
    )

    assert snapshot.raw_refs["prices"] == [
        "market_quotes:a:2026-07-24",
        "market_quotes:z:2026-07-24",
    ]
    assert EvidenceSnapshotService.verify_integrity(snapshot)


@pytest.mark.asyncio
async def test_snapshot_hash_is_stable_at_mongodb_datetime_precision():
    db = FakeDB()
    microsecond_report = quality("PASS").model_copy(
        update={"checked_at": CUTOFF.replace(microsecond=123456)}
    )

    snapshot = await EvidenceSnapshotService(
        db,
        StubGate(microsecond_report),
    ).create(
        user_id="user-1",
        payload=create_payload(),
    )

    assert snapshot.created_at.microsecond % 1000 == 0
    assert snapshot.data_quality.checked_at.microsecond == 123000
    assert EvidenceSnapshotService.verify_integrity(snapshot)
    assert db["ag_evidence_snapshots"].count() == 1
    assert db["ag_data_quality_reports"].count() == 1


@pytest.mark.asyncio
async def test_fail_report_is_saved_but_snapshot_is_not_created():
    db = FakeDB()
    gate = StubGate(quality("FAIL"))
    with pytest.raises(DataQualityBlockedError):
        await EvidenceSnapshotService(db, gate).create(
            user_id="user-1", payload=create_payload()
        )
    assert gate.calls == 1
    assert db["ag_data_quality_reports"].count() == 1
    assert db["ag_evidence_snapshots"].count() == 0


def test_snapshot_service_and_router_expose_no_mutation_surface():
    assert not hasattr(EvidenceSnapshotService, "update")
    assert not hasattr(EvidenceSnapshotService, "delete")
    snapshot_paths = [
        (route.path, method)
        for route in router.routes
        if "evidence/snapshots" in route.path
        for method in route.methods
    ]
    assert all(method not in {"PUT", "PATCH", "DELETE"} for _, method in snapshot_paths)


@pytest.mark.asyncio
async def test_missing_snapshot_blocks_analysis():
    service = EvidenceSnapshotService(FakeDB())
    with pytest.raises(SnapshotValidationError):
        await service.validate_for_analysis(
            snapshot_id="missing",
            user_id="user-1",
            symbol="600519",
            market="CN",
        )


@pytest.mark.asyncio
async def test_symbol_mismatch_and_hash_tamper_block_analysis():
    db = FakeDB()
    await db["ag_evidence_snapshots"].insert_one(snapshot_data())
    service = EvidenceSnapshotService(db)
    with pytest.raises(SnapshotValidationError):
        await service.validate_for_analysis(
            snapshot_id="snapshot-1",
            user_id="user-1",
            symbol="000001",
            market="CN",
        )
    db["ag_evidence_snapshots"].documents[0]["news_data_version"] = "tampered"
    with pytest.raises(SnapshotValidationError):
        await service.validate_for_analysis(
            snapshot_id="snapshot-1",
            user_id="user-1",
            symbol="600519",
            market="CN",
        )
