from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal

import pytest

from app.schemas.alphaguard import QuantTradeProposal
from app.services.alphaguard.evidence_snapshot_service import (
    calculate_immutable_hash,
)
from app.services.alphaguard.historical_backfill_service import (
    HistoricalBackfillIntegrityConflict,
    HistoricalBackfillService,
)
from app.services.alphaguard.paper_policy_registry import PaperPolicyRegistry
from tests.unit.alphaguard._fakes import FakeDB
from tradingagents.alphaguard.backfill_schemas import (
    HistoricalBackfillRun,
    HistoricalCoverageRecord,
    HistoricalResearchSnapshot,
    backfill_hash,
)
from tradingagents.alphaguard.evidence_schemas import (
    DataQualityReport,
    EvidenceSnapshot,
)


def _open_dates(start: date, count: int) -> list[date]:
    result: list[date] = []
    current = start
    while len(result) < count:
        if current.weekday() < 5:
            result.append(current)
        current += timedelta(days=1)
    return result


async def _seed_calendar_and_qfq(db, sessions: list[date]) -> None:
    for index, session in enumerate(sessions):
        await db["trading_calendar"].insert_one(
            {"market": "CN", "session_date": session.isoformat(), "is_open": True}
        )
        for symbol, base in (("600519", Decimal("10")), ("000300", Decimal("20"))):
            close = base + Decimal(index) / Decimal("10")
            mode = "QFQ" if symbol == "600519" else "INDEX_UNADJUSTED_EQUIVALENT"
            version = "qfq-v1" if symbol == "600519" else "index-raw-v1"
            await db["stock_daily_quotes"].insert_one(
                {
                    "ref_id": f"{symbol}-{session}",
                    "data_ref": f"adjusted:{symbol}:{session}:{version}",
                    "symbol": symbol,
                    "market": "CN",
                    "trade_date": session.isoformat(),
                    "period": "daily",
                    "open": close,
                    "high": close + Decimal("0.30"),
                    "low": close - Decimal("0.20"),
                    "close": close,
                    "adjusted_open": close,
                    "adjusted_high": close + Decimal("0.30"),
                    "adjusted_low": close - Decimal("0.20"),
                    "adjusted_close": close,
                    "price_adjustment_mode": mode,
                    "price_data_version": version,
                    "volume": 1_000_000,
                    "suspended": False,
                }
            )


def _run(decision_date: date) -> HistoricalBackfillRun:
    return HistoricalBackfillRun(
        backfill_run_id="backfill-evaluation-1",
        status="RUNNING",
        user_id="admin-1",
        symbols=["600519"],
        start_trade_date=decision_date,
        end_trade_date=decision_date,
        sampling_method="CUSTOM",
        selected_trade_dates=[decision_date],
        code_commit="commit",
        code_tree_hash="tree",
        config_hash="a" * 64,
        input_hash="b" * 64,
        version_refs={"strategy_set": "strategy-set-v1"},
        total_samples=1,
        created_at=datetime(2026, 7, 27),
        updated_at=datetime(2026, 7, 27),
    )


def _research_snapshot(run: HistoricalBackfillRun) -> HistoricalResearchSnapshot:
    decision_date = run.selected_trade_dates[0]
    quality = DataQualityReport(
        quality_report_id="research-quality-1",
        symbol="600519",
        market="CN",
        trade_date=decision_date,
        status="PASS",
        completeness_score=1,
        freshness_score=1,
        consistency_score=1,
        checked_at=run.created_at,
    )
    payload = {
        "snapshot_id": "research-evidence-1",
        "user_id": run.user_id,
        "symbol": "600519",
        "market": "CN",
        "trade_date": decision_date,
        "price_cutoff_at": datetime.combine(decision_date, time(15)),
        "news_cutoff_at": datetime.combine(decision_date, time(15)),
        "announcement_cutoff_at": datetime.combine(decision_date, time(15)),
        "price_data_version": "qfq-v1",
        "financial_data_version": "financial:none",
        "news_data_version": "news:none",
        "data_quality": quality,
        "raw_refs": {"prices": ["qfq:600519"]},
        "factor_version_set": {"factor": "1.0.0"},
        "strategy_version": "strategy-set-v1",
        "created_at": run.created_at,
        "immutable_hash": "0" * 64,
    }
    draft = EvidenceSnapshot.model_validate(payload)
    payload["immutable_hash"] = calculate_immutable_hash(draft)
    evidence = EvidenceSnapshot.model_validate(payload)
    wrapper = {
        "research_snapshot_id": "research:research-evidence-1",
        "backfill_run_id": run.backfill_run_id,
        "sample_id": "sample-evaluation-1",
        "source_trade_date": decision_date,
        "evidence_snapshot": evidence,
        "created_at": run.created_at,
    }
    wrapper["immutable_hash"] = backfill_hash(wrapper)
    return HistoricalResearchSnapshot.model_validate(wrapper)


def _proposal(decision_date: date, valid_until: date) -> QuantTradeProposal:
    return QuantTradeProposal(
        proposal_id="research-proposal-evaluation-1",
        candidate_id=None,
        user_id="admin-1",
        symbol="600519",
        market="CN",
        trade_date=decision_date,
        snapshot_id="research-evidence-1",
        strategy_id="SWING_TREND_PULLBACK",
        strategy_version="1.0.0",
        regime_result_id="research-regime-1",
        factor_set_version="factor-set-v1",
        status="TRIGGERED",
        action_candidate="BUY",
        entry_zone={"lower": 9.8, "upper": 10.2},
        initial_position_pct=0.05,
        max_position_pct=0.10,
        add_conditions=[],
        reduce_conditions=[],
        exit_conditions=[],
        invalidation_conditions=[],
        valid_until=datetime.combine(valid_until, time(23, 59)),
        expected_holding_days=(5, 20),
        factor_summary={},
        factor_result_ids=[],
        evidence_refs=[],
        risk_flags=[],
        reason_codes=["research"],
        explanation="fixed deterministic research proposal",
        input_hash="d" * 64,
        created_at=datetime.combine(decision_date, time(15)),
    )


@pytest.mark.asyncio
async def test_research_evaluation_generates_mature_labels_without_future_leakage():
    db = FakeDB()
    await PaperPolicyRegistry(db).register_builtins()
    sessions = _open_dates(date(2026, 1, 2), 26)
    await _seed_calendar_and_qfq(db, sessions)
    run = _run(sessions[0])
    snapshot = _research_snapshot(run)
    proposal = _proposal(sessions[0], sessions[5])
    before = await HistoricalBackfillService(db).production_state()

    identifiers = await HistoricalBackfillService(db)._evaluate_proposals(
        run=run,
        sample_id="sample-evaluation-1",
        snapshot=snapshot,
        proposals=[proposal],
        as_of_trade_date=sessions[10],
    )
    await db["ag_research_backfill_runs"].insert_one(
        run.model_dump(mode="python")
    )
    initial_report = await HistoricalBackfillService(db).build_report(
        run.backfill_run_id
    )
    assert initial_report.status == "INSUFFICIENT_DATA"
    await db["ag_research_backfill_samples"].insert_one(
        {
            "backfill_run_id": run.backfill_run_id,
            "sample_id": "sample-evaluation-1",
            "status": "COMPLETED",
            "result_hash": "9" * 64,
        }
    )
    await db["ag_research_coverage"].insert_one(
        {
            "backfill_run_id": run.backfill_run_id,
            "status": "READY",
            "warnings": ["HISTORICAL_INDUSTRY_MAPPING_UNAVAILABLE"],
            "domains": {"MARKET_CONTEXT": {"allowed_for_replay": True}},
        }
    )
    await db["ag_research_factor_results"].insert_one(
        {
            "backfill_run_id": run.backfill_run_id,
            "sample_id": "sample-evaluation-1",
            "factor_result": {
                "result_id": "factor-result-1",
                "factor_id": "MOMENTUM_20D",
                "raw_value": 0.1,
                "normalized_score": 75,
                "direction": "POSITIVE",
            },
        }
    )
    await db["ag_research_regime_results"].insert_one(
        {
            "backfill_run_id": run.backfill_run_id,
            "sample_id": "sample-evaluation-1",
            "regime_result": {"regime": "TREND_UP"},
        }
    )
    await db["ag_research_quant_proposals"].insert_one(
        {
            "backfill_run_id": run.backfill_run_id,
            "sample_id": "sample-evaluation-1",
            "quant_proposal": proposal.model_dump(mode="python"),
        }
    )

    subject = db["ag_eval_subjects"].documents[0]
    labels = db["ag_eval_horizon_labels"].documents
    decision_labels = {
        item["horizon"]: item
        for item in labels
        if item["anchor_type"] == "DECISION_CLOSE"
    }
    assert subject["lineage_ids"]["run_mode"] == "RESEARCH_BACKFILL"
    assert subject["lineage_ids"]["research_only"] == "true"
    assert subject["selected_for_execution"] is False
    assert decision_labels["1D"]["status"] == "CALCULATED"
    assert decision_labels["5D"]["status"] == "CALCULATED"
    assert decision_labels["10D"]["status"] == "CALCULATED"
    assert decision_labels["20D"]["status"] == "PENDING"
    assert decision_labels["20D"]["raw_forward_return"] is None
    assert decision_labels["10D"]["mfe"] is not None
    assert decision_labels["10D"]["mae"] is not None
    assert decision_labels["10D"]["relative_benchmark_return"] is not None
    assert decision_labels["10D"]["relative_industry_return"] is None
    assert "unavailable" in decision_labels["10D"]["industry_unavailable_reason"]
    assert len(identifiers["horizon_label_ids"]) == 8
    assert db["ag_eval_counterfactuals"].count() == 2
    assert db["ag_eval_attributions"].count() == 1
    assert await HistoricalBackfillService(db).production_state() == before
    report = await HistoricalBackfillService(db).build_report(run.backfill_run_id)
    assert report.report_id == initial_report.report_id
    assert db["ag_research_backfill_reports"].count() == 1
    factor = report.factor_summary["MOMENTUM_20D"]
    assert factor["horizon_returns"]["10D"]["sample_count"] == 1
    assert factor["normalized_score_bucket_returns"]["060_080"]["10D"][
        "sample_count"
    ] == 1
    assert report.regime_summary["distribution"] == {"TREND_UP": 1}
    assert report.evaluation_summary["decision_close_horizon_status"][
        "20D:PENDING"
    ] == 1


@pytest.mark.asyncio
async def test_completed_run_refreshes_stale_recovery_report_without_new_attempt():
    db = FakeDB()
    run = _run(date(2026, 1, 2)).model_copy(
        update={"status": "COMPLETED", "completed_samples": 1}
    )
    await db["ag_research_backfill_runs"].insert_one(
        run.model_dump(mode="python")
    )
    stale = await HistoricalBackfillService(db).build_report(run.backfill_run_id)
    assert stale.completed_sample_count == 0
    await db["ag_research_backfill_samples"].insert_one(
        {
            "backfill_run_id": run.backfill_run_id,
            "sample_id": "completed-sample",
            "status": "COMPLETED",
            "result_hash": "8" * 64,
        }
    )

    _, refreshed = await HistoricalBackfillService(db).run(
        backfill_run_id=run.backfill_run_id,
        as_of_trade_date=date(2026, 7, 27),
    )

    assert refreshed.report_id == stale.report_id
    assert refreshed.status == "READY"
    assert refreshed.completed_sample_count == 1
    stored_run = db["ag_research_backfill_runs"].documents[0]
    assert stored_run["attempt_count"] == 0


@pytest.mark.asyncio
async def test_research_snapshot_does_not_overwrite_production_snapshot_and_conflicts():
    db = FakeDB()
    run = _run(date(2026, 1, 2))
    snapshot = _research_snapshot(run)
    await db["ag_evidence_snapshots"].insert_one(
        {"snapshot_id": "production-snapshot", "immutable_hash": "f" * 64}
    )
    service = HistoricalBackfillService(db)
    stored = await service._save_immutable(
        "ag_research_snapshots",
        snapshot,
        identity={"research_snapshot_id": snapshot.research_snapshot_id},
        hash_field="immutable_hash",
    )
    assert stored.research_only is True
    assert db["ag_evidence_snapshots"].count() == 1
    assert db["ag_research_snapshots"].count() == 1

    changed = snapshot.model_copy(update={"immutable_hash": "0" * 64})
    with pytest.raises(HistoricalBackfillIntegrityConflict):
        await service._save_immutable(
            "ag_research_snapshots",
            changed,
            identity={"research_snapshot_id": snapshot.research_snapshot_id},
            hash_field="immutable_hash",
        )


def test_coverage_contract_rejects_blocked_status_without_reasons():
    with pytest.raises(ValueError):
        HistoricalCoverageRecord(
            coverage_id="coverage-1",
            backfill_run_id="run-1",
            sample_id="sample-1",
            symbol="600519",
            trade_date=date(2026, 1, 2),
            status="INSUFFICIENT_DATA",
            replay_allowed=False,
            domains={},
            critical_missing=[],
            input_hash="a" * 64,
            created_at=datetime(2026, 7, 27),
        )
