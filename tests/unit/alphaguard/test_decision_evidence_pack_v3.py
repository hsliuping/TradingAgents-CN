from __future__ import annotations

from datetime import date, datetime, timedelta

import pandas as pd
import pytest

from app.services.alphaguard.data_quality_gate import DataQualityGate
from app.services.alphaguard.benchmark_price_window_service import (
    BenchmarkPriceWindowService,
)
from app.services.alphaguard.decision_evidence_pack_service import (
    DecisionEvidencePackConflict,
    DecisionEvidencePackService,
)
from app.services.alphaguard.decision_evidence_provider import (
    DecisionEvidenceFetchResult,
    _financial_record,
)
from app.services.alphaguard.evidence_snapshot_service import (
    EvidenceSnapshotService,
    calculate_immutable_hash,
)
from app.services.alphaguard.real_model_validation_service import (
    RealModelValidationService,
    _rank_deduplicate_samples,
)
from app.services.alphaguard.snapshot_data_resolver import (
    SnapshotDataResolver,
    SnapshotResolutionError,
)
from tests.unit.alphaguard._fakes import FakeDB
from tests.unit.alphaguard.pr005_helpers import make_context
from tests.unit.alphaguard.test_evidence_window_v2 import (
    AS_OF,
    CUTOFF,
    _seed_window,
)
from tradingagents.alphaguard.evidence_schemas import (
    EVIDENCE_SNAPSHOT_SCHEMA_VERSION_V3,
)
from tradingagents.alphaguard.decision_evidence_schemas import (
    DECISION_EVIDENCE_CALCULATION_VERSION,
)
from tradingagents.alphaguard.production_data_schemas import (
    production_data_hash,
)


def _fetch_result(*, revenue: float = 100.0) -> DecisionEvidenceFetchResult:
    published = datetime(2026, 4, 30, 10)
    financial = {
        "source_record_id": "300750:eastmoney-statements:2026-03-31:2026-04-30",
        "symbol": "300750",
        "market": "CN",
        "report_period": date(2026, 3, 31),
        "report_type": "一季报",
        "published_at": published,
        "currency": "CNY",
        "revenue": revenue,
        "net_income": 12.0,
        "net_profit": 11.0,
        "deducted_net_profit": 10.0,
        "gross_margin": 35.0,
        "asset_liability_ratio": 48.0,
        "roe": 9.0,
        "revenue_yoy": 15.0,
        "net_profit_yoy": 12.0,
        "deducted_net_profit_yoy": 10.0,
        "revenue_qoq": 5.0,
        "net_profit_qoq": 4.0,
        "deducted_net_profit_qoq": 3.0,
        "operating_cash_flow": 15.0,
        "investing_cash_flow": -4.0,
        "capital_expenditure": 3.0,
        "free_cash_flow": 12.0,
        "operating_cash_flow_to_net_income": 1.25,
        "provider": "AKShare/Eastmoney",
        "underlying_source": "Eastmoney",
        "data_version": "statement-v1",
        "calculation_versions": {"qoq": "qoq-v1"},
        "source_response_hashes": {"profit": "1" * 64},
    }
    dividend = {
        "source_record_id": "300750:cninfo-dividend:2025-06-20:2024",
        "symbol": "300750",
        "market": "CN",
        "published_at": datetime(2025, 6, 20),
        "dividend_type": "年度分红",
        "cash_dividend_per_ten_shares": 10.0,
        "stock_dividend_per_ten_shares": None,
        "capitalization_per_ten_shares": None,
        "record_date": datetime(2025, 6, 26),
        "ex_dividend_date": datetime(2025, 6, 27),
        "payment_date": datetime(2025, 6, 27),
        "plan_description": "10派10元(含税)",
        "report_period_label": "2024年报",
        "provider": "AKShare/CNInfo",
        "underlying_source": "CNInfo",
        "data_version": "cninfo-v1",
    }
    announcement = {
        "source_record_id": "1225000001",
        "symbol": "300750",
        "market": "CN",
        "title": "2026年第一季度报告",
        "announcement_category": "FINANCIAL_REPORT",
        "published_at": published,
        "evidence_excerpt": "公司披露第一季度经营与财务数据。",
        "attachment_url": "https://static.cninfo.com.cn/report.pdf",
        "attachment_content_hash": "2" * 64,
        "provider": "AKShare/CNInfo",
        "underlying_source": "CNInfo",
        "data_version": "cninfo-v1",
    }
    return DecisionEvidenceFetchResult(
        provider_versions={"akshare": "1.18.78", "pypdf": "6.1.3"},
        financial_records=(financial,),
        dividend_records=(dividend,),
        announcement_records=(announcement,),
        corporate_action_records=(),
        source_statuses={
            "financial_evidence": "READY",
            "cashflow_evidence": "READY",
            "dividend_evidence": "READY",
            "announcement_evidence": "READY",
            "corporate_action_evidence": "READY",
        },
        source_response_hashes={
            "financial_evidence": "3" * 64,
            "cashflow_evidence": "3" * 64,
            "dividend_evidence": "4" * 64,
            "announcement_evidence": "5" * 64,
            "corporate_action_evidence": "5" * 64,
        },
        source_errors={},
    )


@pytest.mark.asyncio
async def test_manifest_is_complete_hash_stable_create_only_and_reused():
    db = FakeDB()
    service = DecisionEvidencePackService(db)
    kwargs = {
        "symbol": "300750",
        "decision_time": datetime(2026, 5, 8, 15),
        "source_trade_date": date(2026, 5, 8),
        "source_snapshot_id": "source-snapshot-v1",
        "execute": True,
        "fetched": _fetch_result(),
        "collected_at": datetime(2026, 8, 2, 10),
    }
    first = await service.build(**kwargs)
    second = await service.build(**kwargs)
    assert first["action"] == "CREATED"
    assert second["action"] == "REUSED"
    assert first["manifest"]["overall_status"] == "COMPLETE"
    assert first["manifest"]["calculation_version"] == (
        DECISION_EVIDENCE_CALCULATION_VERSION
    )
    assert set(first["manifest"]["evidence_completeness_matrix"].values()) == {
        "COMPLETE"
    }
    assert first["manifest"]["manifest_hash"] == second["manifest"]["manifest_hash"]
    assert await db[service.COLLECTION].count_documents({}) == 1
    stored_financial = db[service.FINANCIAL_COLLECTION].documents[0]
    assert isinstance(stored_financial["report_period"], datetime)
    stored_dividend = db[service.DIVIDEND_COLLECTION].documents[0]
    assert "corporate_action_refs" not in stored_dividend
    assert "corporate_action_status" not in stored_dividend


@pytest.mark.asyncio
async def test_same_manifest_identity_with_changed_source_is_conflict():
    db = FakeDB()
    service = DecisionEvidencePackService(db)
    base = {
        "symbol": "300750",
        "decision_time": datetime(2026, 5, 8, 15),
        "source_trade_date": date(2026, 5, 8),
        "source_snapshot_id": "source-snapshot-v1",
        "execute": True,
        "collected_at": datetime(2026, 8, 2, 10),
    }
    await service.build(**base, fetched=_fetch_result(revenue=100.0))
    with pytest.raises(DecisionEvidencePackConflict, match="INTEGRITY_CONFLICT"):
        await service.build(**base, fetched=_fetch_result(revenue=101.0))


def test_statement_normalization_uses_only_published_rows_and_derives_qoq():
    q1 = {
        "SECURITY_CODE": "300750",
        "REPORT_DATE": "2026-03-31",
        "NOTICE_DATE": "2026-04-30",
        "UPDATE_DATE": "2026-04-30",
        "REPORT_TYPE": "一季报",
    }
    annual = {
        "SECURITY_CODE": "300750",
        "REPORT_DATE": "2025-12-31",
        "NOTICE_DATE": "2026-03-10",
        "UPDATE_DATE": "2026-03-10",
        "REPORT_TYPE": "年报",
    }
    q3 = {
        "SECURITY_CODE": "300750",
        "REPORT_DATE": "2025-09-30",
        "NOTICE_DATE": "2025-10-30",
        "UPDATE_DATE": "2025-10-30",
        "REPORT_TYPE": "三季报",
    }
    profit = pd.DataFrame(
        [
            {**q1, "TOTAL_OPERATE_INCOME": 120, "NETPROFIT": 12, "PARENT_NETPROFIT": 12, "DEDUCT_PARENT_NETPROFIT": 11, "OPERATE_INCOME": 100, "OPERATE_COST": 60, "TOTAL_OPERATE_INCOME_YOY": 10, "PARENT_NETPROFIT_YOY": 8},
            {**annual, "TOTAL_OPERATE_INCOME": 400, "NETPROFIT": 40, "PARENT_NETPROFIT": 40, "DEDUCT_PARENT_NETPROFIT": 36, "OPERATE_INCOME": 350, "OPERATE_COST": 210},
            {**q3, "TOTAL_OPERATE_INCOME": 300, "NETPROFIT": 30, "PARENT_NETPROFIT": 30, "DEDUCT_PARENT_NETPROFIT": 27, "OPERATE_INCOME": 260, "OPERATE_COST": 160},
        ]
    )
    balance = pd.DataFrame(
        [
            {**q1, "TOTAL_ASSETS": 500, "TOTAL_LIABILITIES": 250, "TOTAL_PARENT_EQUITY": 200},
            {**annual, "TOTAL_ASSETS": 480, "TOTAL_LIABILITIES": 240, "TOTAL_PARENT_EQUITY": 180},
            {**q3, "TOTAL_ASSETS": 450, "TOTAL_LIABILITIES": 220, "TOTAL_PARENT_EQUITY": 170},
        ]
    )
    cashflow = pd.DataFrame(
        [
            {**q1, "NETCASH_OPERATE": 15, "NETCASH_INVEST": -4, "CONSTRUCT_LONG_ASSET": 3},
            {**annual, "NETCASH_OPERATE": 50, "NETCASH_INVEST": -20, "CONSTRUCT_LONG_ASSET": 12},
            {**q3, "NETCASH_OPERATE": 35, "NETCASH_INVEST": -15, "CONSTRUCT_LONG_ASSET": 8},
        ]
    )
    record = _financial_record(
        symbol="300750",
        decision_time=datetime(2026, 5, 8, 15),
        profit_frame=profit,
        balance_frame=balance,
        cashflow_frame=cashflow,
    )
    assert record is not None
    assert record["report_period"] == date(2026, 3, 31)
    assert record["revenue_qoq"] == 20.0
    assert record["net_profit_qoq"] == 20.0
    assert record["free_cash_flow"] == 12.0
    assert record["asset_liability_ratio"] == 50.0
    assert _financial_record(
        symbol="300750",
        decision_time=datetime(2026, 4, 29, 15),
        profit_frame=profit.iloc[:1],
        balance_frame=balance.iloc[:1],
        cashflow_frame=cashflow.iloc[:1],
    ) is None


def test_data_quality_fails_when_pack_manifest_is_partial():
    cutoff = datetime(2026, 5, 8, 15)
    report = DataQualityGate().evaluate_documents(
        symbol="300750",
        market="CN",
        trade_date=date(2026, 5, 8),
        price_cutoff_at=cutoff,
        news_cutoff_at=cutoff,
        announcement_cutoff_at=cutoff,
        resolved={
            "prices": [
                {
                    "trade_date": cutoff,
                    "open": 1,
                    "high": 2,
                    "low": 1,
                    "close": 2,
                    "volume": 1,
                    "amount": 1,
                }
            ],
            "decision_evidence_pack": [
                {
                    "manifest_hash": "a" * 64,
                    "overall_status": "PARTIAL",
                    "evidence_completeness_matrix": {
                        "financial_evidence": "COMPLETE",
                        "cashflow_evidence": "PARTIAL",
                        "dividend_evidence": "COMPLETE",
                        "announcement_evidence": "COMPLETE",
                    },
                }
            ],
        },
        invalid_refs=[],
        required_source_counts={"decision_evidence_pack": 1},
        expected_manifest_hashes={"decision_evidence_pack": "a" * 64},
    )
    assert report.status == "FAIL"
    assert "required Decision Evidence Pack v3 is incomplete" in report.blocking_reasons


def test_snapshot_hash_includes_decision_evidence_manifest_identity_and_hash():
    base = {
        "snapshot_id": "snapshot-v3",
        "decision_evidence_pack_manifest_id": "manifest-v3",
        "decision_evidence_pack_manifest_hash": "a" * 64,
    }
    assert calculate_immutable_hash(base) != calculate_immutable_hash(
        {**base, "decision_evidence_pack_manifest_hash": "b" * 64}
    )


@pytest.mark.asyncio
async def test_snapshot_v3_resolver_locks_complete_pack_and_rejects_tampering():
    db = FakeDB()
    await _seed_window(db)
    benchmark = (
        await BenchmarkPriceWindowService(db).build(
            as_of_trade_date=AS_OF,
            cutoff_at=CUTOFF,
            execute=True,
        )
    )["manifest"]
    evidence = (
        await DecisionEvidencePackService(db).build(
            symbol="300750",
            decision_time=CUTOFF,
            source_trade_date=AS_OF,
            source_snapshot_id="historical-source-snapshot",
            execute=True,
            fetched=_fetch_result(),
            collected_at=datetime(2026, 8, 2, 10),
        )
    )["manifest"]
    await db["stock_daily_quotes"].insert_one(
        {
            "ref_id": "target-300750",
            "symbol": "300750",
            "market": "CN",
            "trade_date": datetime.combine(AS_OF, datetime.min.time()),
            "open": 250,
            "high": 260,
            "low": 245,
            "close": 255,
            "volume": 100,
            "amount": 25500,
        }
    )
    await db["ag_market_contexts"].insert_one(
        {
            "context_id": "context-current-v3",
            "ref_id": "context-current-v3",
            "market": "CN",
            "trade_date": datetime.combine(AS_OF, datetime.min.time()),
            "content_hash": "4" * 64,
        }
    )
    context_manifest = {
        "manifest_id": "context-window-v3",
        "ref_id": "context-window-v3",
        "market": "CN",
        "as_of_trade_date": AS_OF,
        "required_count": 1,
        "actual_count": 1,
        "ordered_trade_dates": [AS_OF],
        "ordered_context_ids": ["context-current-v3"],
        "ordered_context_hashes": ["4" * 64],
        "context_version": "production-market-context-calculation-v1.1",
        "window_start": AS_OF,
        "window_end": AS_OF,
        "source_hash": "5" * 64,
        "available_at": datetime(2026, 7, 29, 16),
        "created_at": datetime(2026, 8, 2, 10),
    }
    context_manifest["manifest_hash"] = production_data_hash(
        context_manifest,
        exclude={"created_at"},
    )
    context_manifest["schema_version"] = "alphaguard-production-data-v1"
    await db["ag_market_context_window_manifests"].insert_one(context_manifest)

    raw_refs = {
        "prices": ["stock_daily_quotes:target-300750"],
        "benchmark_prices": [
            f"index_daily:{quote_id}"
            for quote_id in benchmark["ordered_quote_ids"]
        ],
        "financials": evidence["financial_evidence"]["source_refs"],
        "cashflow_evidence": evidence["cashflow_evidence"]["source_refs"],
        "dividend_evidence": evidence["dividend_evidence"]["source_refs"],
        "announcements": evidence["announcement_evidence"]["source_refs"],
        "market_context": ["market_context:context-current-v3"],
        "market_context_window": ["market_context_window:context-window-v3"],
        "benchmark_price_window": [
            f"benchmark_price_window:{benchmark['manifest_id']}"
        ],
        "decision_evidence_pack": [
            f"decision_evidence_pack:{evidence['manifest_id']}"
        ],
    }
    snapshot = await EvidenceSnapshotService(
        db=db,
        enable_shadow_hook=False,
    ).create(
        user_id="validation-user",
        payload={
            "symbol": "300750",
            "market": "CN",
            "trade_date": AS_OF,
            "price_cutoff_at": CUTOFF,
            "news_cutoff_at": CUTOFF,
            "announcement_cutoff_at": CUTOFF,
            "price_data_version": "fixed",
            "financial_data_version": "decision-evidence-pack-v3",
            "news_data_version": "fixed",
            "market_context_id": "context-current-v3",
            "market_context_hash": "4" * 64,
            "market_context_window_manifest_id": "context-window-v3",
            "market_context_window_manifest_hash": context_manifest["manifest_hash"],
            "benchmark_price_window_manifest_id": benchmark["manifest_id"],
            "benchmark_price_window_manifest_hash": benchmark["manifest_hash"],
            "decision_evidence_pack_manifest_id": evidence["manifest_id"],
            "decision_evidence_pack_manifest_hash": evidence["manifest_hash"],
            "evidence_completeness_matrix": evidence[
                "evidence_completeness_matrix"
            ],
            "required_benchmark_count": 61,
            "actual_benchmark_count": 61,
            "evidence_contract_status": "COMPLETE",
            "run_mode": "EVIDENCE_CONTRACT_VALIDATION",
            "source_trade_date": AS_OF,
            "evidence_contract_version": "decision-evidence-pack-v3",
            "automated_execution_allowed": False,
            "raw_refs": raw_refs,
            "required_sources": list(raw_refs),
            "schema_version": EVIDENCE_SNAPSHOT_SCHEMA_VERSION_V3,
        },
    )
    resolved = await SnapshotDataResolver(db).resolve(
        snapshot.snapshot_id,
        user_id="validation-user",
        allow_legacy_unversioned=True,
    )
    assert resolved.decision_evidence_pack[0]["manifest_id"] == evidence[
        "manifest_id"
    ]
    assert resolved.financials and resolved.cashflows
    assert resolved.dividends and resolved.announcements

    db["stock_financial_data"].documents[0]["content_hash"] = "f" * 64
    with pytest.raises(
        SnapshotResolutionError,
        match="Decision Evidence Pack source identity/hash mismatch",
    ):
        await SnapshotDataResolver(db).resolve(
            snapshot.snapshot_id,
            user_id="validation-user",
            allow_legacy_unversioned=True,
        )


def test_evidence_ranking_is_complete_then_score_then_stable_and_deduplicated():
    base = make_context().quant_proposal
    duplicate = base.model_copy(
        update={"proposal_id": "duplicate", "symbol": "300750"}
    )
    complete = base.model_copy(
        update={
            "proposal_id": "complete",
            "symbol": "000333",
            "factor_summary": {"TREND": 10.0, "MOMENTUM": 10.0},
        }
    )
    higher_score = duplicate.model_copy(
        update={
            "proposal_id": "higher-score",
            "factor_summary": {"TREND": 90.0, "MOMENTUM": 90.0},
        }
    )
    samples = [
        {"proposal": duplicate, "evidence_completeness_score": 0.5},
        {"proposal": higher_score, "evidence_completeness_score": 0.5},
        {"proposal": complete, "evidence_completeness_score": 1.0},
    ]
    ranked = _rank_deduplicate_samples(samples, limit=3)
    assert [item["proposal"].proposal_id for item in ranked] == [
        "complete",
        "higher-score",
    ]


@pytest.mark.asyncio
async def test_incomplete_preflight_never_calls_or_mutates_models(monkeypatch):
    db = FakeDB()
    service = RealModelValidationService(db)

    async def blocked(**_kwargs):
        return {
            "status": "BLOCKED",
            "blocking_items": ["DECISION_EVIDENCE_PACK_NOT_READY"],
        }

    monkeypatch.setattr(service, "preflight", blocked)
    result = await service.run(
        requested_by="admin",
        idempotency_key="v11-incomplete-pack",
    )
    assert result.failure_code == "DECISION_EVIDENCE_PACK_NOT_READY"
    assert result.model_run_ids == []
    assert await db["ag_model_runs"].count_documents({}) == 0
    assert await db["ag_order_intents"].count_documents({}) == 0


@pytest.mark.asyncio
async def test_validation_audit_api_projects_non_secret_v3_evidence(monkeypatch):
    import app.routers.alphaguard_models as models_router

    db = FakeDB()
    await db["ag_model_validation_runs"].insert_one(
        {
            "validation_run_id": "validation-v11",
            "snapshot_id": "snapshot-v3",
            "created_at": datetime(2026, 8, 2, 10),
        }
    )
    await db["ag_model_validation_evidence_snapshots"].insert_one(
        {
            "snapshot_id": "snapshot-v3",
            "decision_evidence_pack_manifest_id": "manifest-v3",
            "decision_evidence_pack_manifest_hash": "a" * 64,
            "evidence_completeness_matrix": {
                "financial_evidence": "COMPLETE",
                "cashflow_evidence": "COMPLETE",
                "dividend_evidence": "COMPLETE",
                "announcement_evidence": "COMPLETE",
            },
            "actual_benchmark_count": 61,
        }
    )
    monkeypatch.setattr(models_router, "get_mongo_db", lambda: db)
    response = await models_router.model_validation_runs(
        limit=20,
        current_user={"id": "admin", "is_admin": True},
    )
    item = response["data"]["items"][0]
    assert item["decision_evidence_pack_manifest_id"] == "manifest-v3"
    assert item["decision_evidence_status"] == "COMPLETE"
    assert item["benchmark_count"] == 61
    assert "decision_evidence_pack_manifest_hash" not in item
    assert "credential_ref" not in str(item)
