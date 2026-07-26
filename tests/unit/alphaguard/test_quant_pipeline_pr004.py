from datetime import date, datetime, timedelta

import pytest

from app.services.alphaguard.candidate_pool_service import CandidatePoolService
from app.services.alphaguard.evidence_snapshot_service import calculate_immutable_hash
from app.services.alphaguard.evidence_snapshot_service import EvidenceSnapshotService
from app.services.alphaguard.factor_registry import FactorRegistry
from app.services.alphaguard.index_service import ensure_alphaguard_indexes
from app.services.alphaguard.quant_research_pipeline import QuantResearchPipeline
from app.services.alphaguard.strategy_registry import StrategyRegistry
from tests.unit.alphaguard._fakes import FakeDB
from tradingagents.alphaguard.candidate_schemas import CandidateSource, CandidateStatus
from tradingagents.alphaguard.evidence_schemas import DataQualityReport, EvidenceSnapshot
from tradingagents.alphaguard.mongo_indexes import ALPHAGUARD_INDEX_SPECS


async def build_pipeline_snapshot(db):
    raw_refs = {
        "prices": [],
        "benchmark_prices": [],
        "financials": [],
        "news": [],
        "market_context": [],
        "trading_calendar": [],
    }
    start = date(2026, 5, 2)
    for index in range(61):
        trade_date = start + timedelta(days=index)
        close = 100 + index
        if index == 60:
            close = 155
        price = {
            "ref_id": f"p{index}",
            "symbol": "600519",
            "market": "CN",
            "trade_date": trade_date.isoformat(),
            "open": close - 1,
            "high": max(close + 1, 161 if index == 60 else close + 1),
            "low": close - 2,
            "close": close,
            "volume": 1_000_000 + index * 10_000,
            "amount": 100_000_000 + index * 2_000_000,
            "turnover_rate": 1 + index / 100,
            "pe_ttm": 10 + index / 10,
            "pb": 1 + index / 100,
            "dv_ttm": 2.0,
        }
        benchmark = {
            "ref_id": f"b{index}",
            "symbol": "000300",
            "market": "CN",
            "trade_date": trade_date.isoformat(),
            "close": 100 + index * 0.5,
        }
        await db["stock_daily_quotes"].insert_one(price)
        await db["stock_daily_quotes"].insert_one(benchmark)
        raw_refs["prices"].append(f"stock_daily_quotes:p{index}")
        raw_refs["benchmark_prices"].append(f"index_daily:b{index}")
    for index, record in enumerate(
        [
            {
                "report_period": "2024-12-31",
                "ann_date": "2025-04-01",
                "revenue": 100,
                "adjusted_net_profit": 10,
                "roe": 12,
                "n_cashflow_act": 12,
                "net_income": 10,
            },
            {
                "report_period": "2025-12-31",
                "ann_date": "2026-04-01",
                "revenue": 130,
                "adjusted_net_profit": 14,
                "roe": 15,
                "n_cashflow_act": 18,
                "net_income": 14,
            },
        ]
    ):
        record["ref_id"] = f"f{index}"
        await db["stock_financial_data"].insert_one(record)
        raw_refs["financials"].append(f"stock_financial_data:f{index}")
    await db["stock_news"].insert_one(
        {
            "ref_id": "n0",
            "publish_time": "2026-07-01T10:00:00",
            "title": "routine company update",
        }
    )
    raw_refs["news"].append("stock_news:n0")
    await db["ag_market_contexts"].insert_one(
        {
            "ref_id": "ctx",
            "context_id": "ctx",
            "market": "CN",
            "trade_date": "2026-07-01",
            "advance_count": 3200,
            "decline_count": 1200,
            "industry_up_ratio": 0.70,
            "amount_ratio20": 1.1,
            "new_high_count": 300,
            "new_low_count": 50,
            "extreme_risk_flag": False,
        }
    )
    raw_refs["market_context"].append("market_context:ctx")
    for index in range(3):
        await db["trading_calendar"].insert_one(
            {
                "ref_id": f"c{index}",
                "session_date": f"2026-07-0{index + 2}",
                "is_open": True,
                "as_of": "2026-06-01",
            }
        )
        raw_refs["trading_calendar"].append(f"trading_calendar:c{index}")

    versions = await FactorRegistry(db).get_version_set(require_registered=False)
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
    draft = EvidenceSnapshot(
        snapshot_id="snapshot-pipeline",
        user_id="user",
        symbol="600519",
        market="CN",
        trade_date=date(2026, 7, 1),
        price_cutoff_at=datetime(2026, 7, 1, 15),
        news_cutoff_at=datetime(2026, 7, 1, 15),
        announcement_cutoff_at=datetime(2026, 7, 1, 15),
        price_data_version="fixed-pr004",
        financial_data_version="fixed-pr004",
        news_data_version="fixed-pr004",
        data_quality=quality,
        raw_refs=raw_refs,
        factor_version_set=versions,
        strategy_version="strategy-set-v1",
        immutable_hash="0" * 64,
        created_at=datetime(2026, 7, 1, 15),
    )
    snapshot = draft.model_copy(
        update={"immutable_hash": calculate_immutable_hash(draft)}
    )
    await db["ag_evidence_snapshots"].insert_one(snapshot.model_dump(mode="python"))
    return snapshot


@pytest.mark.asyncio
async def test_pipeline_persists_reproducible_proposals_and_only_advances_watching_candidate():
    db = FakeDB()
    await FactorRegistry(db).seed_builtins()
    await StrategyRegistry(db).seed_builtins()
    snapshot = await build_pipeline_snapshot(db)
    candidate = await CandidatePoolService(db).upsert_source(
        user_id="user",
        symbol="600519",
        market="CN",
        source=CandidateSource.USER_SELECTED,
        reason="fixed test",
    )
    assert candidate.status == CandidateStatus.WATCHING
    pipeline = QuantResearchPipeline(db)
    first = await pipeline.evaluate(
        snapshot.snapshot_id,
        user_id="user",
        candidate_id=candidate.candidate_id,
        trace_id="trace-fixed",
    )
    second = await pipeline.evaluate(
        snapshot.snapshot_id,
        user_id="user",
        candidate_id=candidate.candidate_id,
        trace_id="trace-fixed",
    )
    assert len(first) == 2
    assert [item.proposal_id for item in first] == [item.proposal_id for item in second]
    swing = next(item for item in first if item.strategy_id == "SWING_TREND_PULLBACK_V1")
    exit_proposal = next(item for item in first if item.strategy_id == "POSITION_EXIT_V1")
    assert (swing.status, swing.action_candidate) == ("TRIGGERED", "BUY")
    assert (exit_proposal.status, exit_proposal.reason_codes) == (
        "REJECTED",
        ["NO_POSITION"],
    )
    assert all(item.automated_execution_allowed is False for item in first)
    assert db["ag_factor_results"].count() == 21
    assert db["ag_regime_results"].count() == 1
    assert db["ag_quant_proposals"].count() == 2
    updated = await CandidatePoolService(db).get_candidate(
        candidate.candidate_id, "user"
    )
    assert updated.status == CandidateStatus.SIGNAL_DETECTED
    assert db["paper_orders"].count() == 0
    assert db["paper_trades"].count() == 0


@pytest.mark.asyncio
async def test_pr004_index_plan_is_idempotent_and_contains_required_uniques():
    db = FakeDB()
    first = await ensure_alphaguard_indexes(db)
    second = await ensure_alphaguard_indexes(db)
    assert any(item.startswith("created ag_factor_results.") for item in first)
    assert all(item.startswith("unchanged ") for item in second)
    assert {
        "ag_factor_definitions",
        "ag_factor_results",
        "ag_regime_results",
        "ag_strategy_definitions",
        "ag_quant_proposals",
    }.issubset(ALPHAGUARD_INDEX_SPECS)
    assert any(
        spec["name"] == "uniq_snapshot_factor_version" and spec["unique"]
        for spec in ALPHAGUARD_INDEX_SPECS["ag_factor_results"]
    )


@pytest.mark.asyncio
async def test_new_formal_snapshot_locks_registered_versions_into_hash():
    db = FakeDB()
    await FactorRegistry(db).seed_builtins()
    await StrategyRegistry(db).seed_builtins()
    versions = await FactorRegistry(db).get_version_set()
    await db["stock_daily_quotes"].insert_one(
        {
            "ref_id": "trade-price",
            "symbol": "600519",
            "market": "CN",
            "trade_date": "2026-07-01",
            "open": 100,
            "high": 102,
            "low": 99,
            "close": 101,
            "volume": 1_000_000,
            "amount": 100_000_000,
            "updated_at": "2026-07-01T14:00:00",
        }
    )
    snapshot = await EvidenceSnapshotService(db=db).create(
        user_id="user",
        payload={
            "symbol": "600519",
            "market": "CN",
            "trade_date": date(2026, 7, 1),
            "price_cutoff_at": datetime(2026, 7, 1, 15),
            "news_cutoff_at": datetime(2026, 7, 1, 15),
            "announcement_cutoff_at": datetime(2026, 7, 1, 15),
            "price_data_version": "fixed",
            "financial_data_version": "fixed",
            "news_data_version": "fixed",
            "raw_refs": {"prices": ["stock_daily_quotes:trade-price"]},
            "required_sources": ["prices"],
            "factor_version_set": versions,
            "strategy_version": "strategy-set-v1",
        },
    )
    assert snapshot.factor_version_set == versions
    assert snapshot.strategy_version == "strategy-set-v1"
    assert EvidenceSnapshotService.verify_integrity(snapshot)


@pytest.mark.asyncio
async def test_formal_snapshot_fails_when_definitions_are_not_registered():
    db = FakeDB()
    versions = await FactorRegistry(db).get_version_set(require_registered=False)
    with pytest.raises(LookupError, match="factor definition not registered"):
        await EvidenceSnapshotService(db=db).create(
            user_id="user",
            payload={
                "symbol": "600519",
                "market": "CN",
                "trade_date": date(2026, 7, 1),
                "price_cutoff_at": datetime(2026, 7, 1, 15),
                "news_cutoff_at": datetime(2026, 7, 1, 15),
                "announcement_cutoff_at": datetime(2026, 7, 1, 15),
                "price_data_version": "fixed",
                "financial_data_version": "fixed",
                "news_data_version": "fixed",
                "raw_refs": {},
                "factor_version_set": versions,
                "strategy_version": "strategy-set-v1",
            },
        )


def test_quant_router_is_authenticated_and_has_no_result_upload_endpoint():
    from app.routers.alphaguard_quant import router
    from app.routers.auth_db import get_current_user

    method_paths = set()
    for route in router.routes:
        method_paths.update((method, route.path) for method in route.methods)
        assert any(
            dependency.call is get_current_user
            for dependency in route.dependant.dependencies
        )
    assert ("POST", "/alphaguard/quant/evaluate/{snapshot_id}") in method_paths
    assert not any(
        method in {"POST", "PUT", "PATCH", "DELETE"}
        and path.endswith(("factors/results", "regimes", "quant-proposals"))
        for method, path in method_paths
    )


@pytest.mark.asyncio
async def test_quant_api_query_smoke_uses_existing_auth_dependency(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    import app.routers.alphaguard_quant as quant_router
    from app.routers.auth_db import get_current_user

    db = FakeDB()
    await FactorRegistry(db).seed_builtins()
    await StrategyRegistry(db).seed_builtins()
    monkeypatch.setattr(quant_router, "get_mongo_db", lambda: db)
    app = FastAPI()
    app.include_router(quant_router.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: {"id": "user"}
    client = TestClient(app)
    factors = client.get("/api/alphaguard/factors/definitions")
    strategies = client.get("/api/alphaguard/strategies/definitions")
    proposals = client.get("/api/alphaguard/quant-proposals")
    assert factors.status_code == strategies.status_code == proposals.status_code == 200
    assert len(factors.json()["data"]["items"]) == 21
    assert len(strategies.json()["data"]["items"]) == 2
    assert proposals.json()["data"]["items"] == []
