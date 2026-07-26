from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta

import pytest

from app.services.alphaguard.evidence_snapshot_service import (
    calculate_immutable_hash,
)
from app.services.alphaguard.experiment_dataset_service import (
    ExperimentDatasetService,
)
from app.services.alphaguard.historical_replay_engine import (
    HistoricalReplayEngine,
)
from app.services.alphaguard.leakage_audit_service import LeakageAuditService
from app.services.alphaguard.robustness_test_service import RobustnessTestService
from app.services.alphaguard.shadow_experiment_service import (
    ShadowExperimentService,
)
from app.services.alphaguard.walk_forward_validation import TimeSeriesSplitService
from tests.unit.alphaguard._fakes import FakeDB
from tests.unit.alphaguard.pr007_helpers import make_label
from tests.unit.alphaguard.pr008_helpers import seed_single_variable_experiment
from tests.unit.alphaguard.test_snapshot_resolver_pr004 import stored_snapshot
from tradingagents.alphaguard.evidence_schemas import (
    DataQualityReport,
    EvidenceSnapshot,
)


async def fixed_snapshot(
    db,
    *,
    snapshot_id: str,
    trade_date: date,
    created_at: datetime,
):
    quality = DataQualityReport(
        quality_report_id=f"q-{snapshot_id}",
        symbol="600519",
        market="CN",
        trade_date=trade_date,
        status="PASS",
        completeness_score=1,
        freshness_score=1,
        consistency_score=1,
        checked_at=created_at,
    )
    payload = {
        "snapshot_id": snapshot_id,
        "user_id": "user-1",
        "symbol": "600519",
        "market": "CN",
        "trade_date": trade_date,
        "price_cutoff_at": created_at,
        "news_cutoff_at": created_at,
        "announcement_cutoff_at": created_at,
        "price_data_version": "fixed-v1",
        "financial_data_version": "fixed-v1",
        "news_data_version": "fixed-v1",
        "data_quality": quality.model_dump(mode="python"),
        "raw_refs": {},
        "factor_version_set": {"factor": "1.0.0"},
        "strategy_version": "strategy-set-v1",
        "created_at": created_at,
    }
    draft = EvidenceSnapshot.model_validate(
        {**payload, "immutable_hash": "0" * 64}
    )
    payload = draft.model_dump(mode="python")
    payload["immutable_hash"] = calculate_immutable_hash(draft)
    snapshot = EvidenceSnapshot.model_validate(payload)
    await db["ag_evidence_snapshots"].insert_one(
        snapshot.model_dump(mode="python")
    )
    return snapshot


@pytest.mark.asyncio
async def test_manifest_is_fixed_sorted_hashed_and_not_backfilled():
    db = FakeDB()
    _, definition, *_ = await seed_single_variable_experiment(db)
    one = await fixed_snapshot(
        db,
        snapshot_id="s-2",
        trade_date=date(2026, 7, 2),
        created_at=datetime(2026, 7, 2, 15),
    )
    two = await fixed_snapshot(
        db,
        snapshot_id="s-1",
        trade_date=date(2026, 7, 1),
        created_at=datetime(2026, 7, 1, 15),
    )
    service = ExperimentDatasetService(db)
    manifest = await service.create_manifest(
        experiment_id=definition.experiment_id,
        market="CN",
        snapshot_ids=[one.snapshot_id, two.snapshot_id, one.snapshot_id],
        created_from_cutoff_at=datetime(2026, 7, 3),
        selection_rule="fixed test opportunities",
    )
    assert manifest.snapshot_ids == ["s-1", "s-2"]
    assert manifest.symbols == ["600519"]
    same = await service.create_manifest(
        experiment_id=definition.experiment_id,
        market="CN",
        snapshot_ids=["s-1", "s-2"],
        created_from_cutoff_at=datetime(2026, 7, 3),
        selection_rule="fixed test opportunities",
    )
    assert same.manifest_hash == manifest.manifest_hash
    await fixed_snapshot(
        db,
        snapshot_id="s-3",
        trade_date=date(2026, 7, 3),
        created_at=datetime(2026, 7, 3, 15),
    )
    stored = await service.get(manifest.dataset_manifest_id)
    assert stored.snapshot_ids == ["s-1", "s-2"]


@pytest.mark.asyncio
async def test_manifest_rejects_missing_future_wrong_market_and_tampering():
    db = FakeDB()
    _, definition, *_ = await seed_single_variable_experiment(db)
    service = ExperimentDatasetService(db)
    with pytest.raises(LookupError):
        await service.create_manifest(
            experiment_id=definition.experiment_id,
            market="CN",
            snapshot_ids=["missing"],
            created_from_cutoff_at=datetime(2026, 7, 3),
            selection_rule="fixed",
        )
    await fixed_snapshot(
        db,
        snapshot_id="future",
        trade_date=date(2026, 7, 3),
        created_at=datetime(2026, 7, 3, 15),
    )
    with pytest.raises(ValueError, match="future"):
        await service.create_manifest(
            experiment_id=definition.experiment_id,
            market="CN",
            snapshot_ids=["future"],
            created_from_cutoff_at=datetime(2026, 7, 2),
            selection_rule="fixed",
        )
    with pytest.raises(ValueError, match="mix markets"):
        await service.create_manifest(
            experiment_id=definition.experiment_id,
            market="US",
            snapshot_ids=["future"],
            created_from_cutoff_at=datetime(2026, 7, 4),
            selection_rule="fixed",
        )
    db["ag_evidence_snapshots"].documents[0]["symbol"] = "000001"
    with pytest.raises(ValueError, match="tampered"):
        await service.create_manifest(
            experiment_id=definition.experiment_id,
            market="CN",
            snapshot_ids=["future"],
            created_from_cutoff_at=datetime(2026, 7, 4),
            selection_rule="fixed",
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method",
    [
        "ANCHORED_HOLDOUT",
        "ROLLING_WALK_FORWARD",
        "EXPANDING_WALK_FORWARD",
    ],
)
async def test_time_series_splits_are_ordered_embargoed_and_never_shuffled(method):
    db = FakeDB()
    _, definition, *_ = await seed_single_variable_experiment(db)
    start = date(2026, 1, 1)
    ids = []
    for index in range(75):
        session = start + timedelta(days=index)
        snapshot = await fixed_snapshot(
            db,
            snapshot_id=f"s-{index:03d}",
            trade_date=session,
            created_at=datetime.combine(session, datetime.min.time()).replace(
                hour=15
            ),
        )
        ids.append(snapshot.snapshot_id)
    manifest = await ExperimentDatasetService(db).create_manifest(
        experiment_id=definition.experiment_id,
        market="CN",
        snapshot_ids=ids,
        created_from_cutoff_at=datetime(2026, 4, 1),
        selection_rule="ordered",
    )
    splits = await TimeSeriesSplitService(db).create(
        manifest.dataset_manifest_id,
        method=method,
        train_size=20,
        validation_size=5,
        test_size=5,
        embargo_trading_days=2,
        folds=2,
    )
    assert splits
    assert all(item.train_end < item.test_start for item in splits)
    assert all(item.validation_end < item.test_start for item in splits)
    assert all(item.embargo_trading_days == 20 for item in splits)
    assert [item.fold_number for item in splits] == sorted(
        item.fold_number for item in splits
    )
    assert all(item.purge_overlapping_horizons for item in splits)


def test_time_series_split_reports_insufficient_samples_without_shortening():
    dates = [date(2026, 7, 1) + timedelta(days=value) for value in range(10)]
    windows = TimeSeriesSplitService.build_windows(
        dates,
        method="ANCHORED_HOLDOUT",
        train_size=8,
        validation_size=2,
        test_size=5,
        embargo_trading_days=2,
        folds=1,
    )
    assert windows == []


async def replay_fixture():
    db = FakeDB()
    _, definition, *_ = await seed_single_variable_experiment(db)
    snapshot = await stored_snapshot(db)
    db["stock_daily_quotes"].documents.clear()
    await db["stock_daily_quotes"].insert_one(
        {
            "ref_id": "p0",
            "symbol": "600519",
            "market": "CN",
            "trade_date": "2026-07-01",
            "open": 10,
            "high": 10.5,
            "low": 9.8,
            "close": 10.2,
            "volume": 1_000_000,
            "amount": 10_200_000,
        }
    )
    await db["stock_daily_quotes"].insert_one(
        {
            "ref_id": "p1",
            "symbol": "600519",
            "market": "CN",
            "trade_date": "2026-07-02",
            "close": 99,
        }
    )
    await db["stock_financial_data"].insert_one(
        {
            "ref_id": "f0",
            "symbol": "600519",
            "market": "CN",
            "report_period": "2025-12-31",
            "ann_date": "2026-04-01",
            "revenue": 10,
        }
    )
    await db["stock_financial_data"].insert_one(
        {
            "ref_id": "f1",
            "symbol": "600519",
            "market": "CN",
            "report_period": "2026-03-31",
            "ann_date": "2026-07-02",
            "revenue": 999,
        }
    )
    await db["stock_news"].insert_one(
        {
            "ref_id": "n0",
            "symbol": "600519",
            "market": "CN",
            "publish_time": "2026-07-01T10:00:00",
            "title": "known",
        }
    )
    await db["stock_news"].insert_one(
        {
            "ref_id": "n1",
            "symbol": "600519",
            "market": "CN",
            "publish_time": "2026-07-01T16:00:00",
            "title": "future",
        }
    )
    await db["trading_calendar"].insert_one(
        {
            "ref_id": "c0",
            "market": "CN",
            "session_date": "2026-07-02",
            "is_open": True,
            "as_of": "2026-06-01",
        }
    )
    manifest = await ExperimentDatasetService(db).create_manifest(
        experiment_id=definition.experiment_id,
        market="CN",
        snapshot_ids=[snapshot.snapshot_id],
        created_from_cutoff_at=datetime(2026, 7, 1, 16),
        selection_rule="one fixed opportunity",
    )
    await db["ag_eval_subjects"].insert_one(
        {
            "subject_id": "subject-1",
            "snapshot_id": snapshot.snapshot_id,
            "decision_stage": "QUANT",
            "created_at": datetime(2026, 7, 1, 15, 1),
        }
    )
    await db["ag_eval_horizon_labels"].insert_one(
        make_label("subject-1", "10D").model_dump(mode="python")
    )
    return db, definition, manifest


@pytest.mark.asyncio
async def test_historical_replay_is_deterministic_paired_and_experiment_only():
    db, definition, manifest = await replay_fixture()
    before_production = {
        name: db[name].count()
        for name in (
            "ag_candidates",
            "ag_factor_results",
            "ag_quant_proposals",
            "ag_order_intents",
            "ag_paper_orders",
            "ag_paper_fills",
            "ag_paper_accounts",
        )
    }
    engine = HistoricalReplayEngine(db)
    run1, result1 = await engine.run_historical_replay(
        definition.experiment_id,
        manifest.dataset_manifest_id,
        created_by="test",
        minimum_samples=1,
        now=datetime(2026, 8, 1),
    )
    run2, result2 = await engine.run_historical_replay(
        definition.experiment_id,
        manifest.dataset_manifest_id,
        created_by="test",
        minimum_samples=1,
        now=datetime(2026, 8, 2),
    )
    assert run1.status == "COMPLETED"
    assert run2.run_id == run1.run_id
    assert result2.result_hash == result1.result_hash
    assert result1.paired_metrics["paired_sample_count"] == 1
    assert db["ag_exp_shadow_outputs"].count() == 1
    assert before_production == {
        name: db[name].count() for name in before_production
    }
    output = db["ag_exp_shadow_outputs"].documents[0]
    assert all(not ref.startswith("ag_eval_") for ref in output["decision_input_refs"])
    assert output["evaluation_label_ids"] == ["label-subject-1-10D"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "finding",
    [
        "future_price_leakage",
        "future_financial_leakage",
        "future_news_leakage",
        "evaluation_label_leakage",
        "split_overlap_leakage",
        "current_config_leakage",
    ],
)
async def test_any_future_or_config_leakage_fails_closed(finding):
    db, definition, manifest = await replay_fixture()
    run, _ = await HistoricalReplayEngine(db).run_historical_replay(
        definition.experiment_id,
        manifest.dataset_manifest_id,
        created_by="test",
        minimum_samples=1,
    )
    report = await LeakageAuditService(db).audit(
        run.run_id, explicit_findings={finding: True}
    )
    assert report.status == "FAIL"
    assert getattr(report, finding) is True


@pytest.mark.asyncio
async def test_robustness_keeps_all_stress_scenarios_without_production_mutation():
    db, definition, manifest = await replay_fixture()
    run, _ = await HistoricalReplayEngine(db).run_historical_replay(
        definition.experiment_id,
        manifest.dataset_manifest_id,
        created_by="test",
        minimum_samples=1,
    )
    report = await RobustnessTestService(db).run(run.run_id)
    names = {item["scenario"] for item in report.scenarios}
    assert names == {
        "BASELINE",
        "FEE_1_5X",
        "FEE_2X",
        "SLIPPAGE_1_5X",
        "SLIPPAGE_2X",
        "ENTRY_DELAY_1D",
        "LIQUIDITY_REDUCTION",
        "MISSING_NONCORE_DATA",
        "WITHOUT_BEST_TRADE",
        "WITHOUT_TOP_5_TRADES",
        "REGIME_SEGMENTED",
    }
    assert all(not item["formal_engine_mutated"] for item in report.scenarios)
    assert all(not item["production_account_writes"] for item in report.scenarios)
    assert db["ag_paper_accounts"].count() == 0


@pytest.mark.asyncio
async def test_shadow_uses_same_snapshot_and_has_no_production_side_effects():
    db, definition, manifest = await replay_fixture()
    # Advance the existing fixture through the explicit state machine.
    from app.services.alphaguard.experiment_registry import ExperimentRegistry

    experiment_registry = ExperimentRegistry(db)
    await experiment_registry.transition(
        definition.experiment_id, "EXPERIMENT", reason="test"
    )
    await experiment_registry.transition(
        definition.experiment_id, "BACKTESTED", reason="test"
    )
    protected = (
        "ag_candidates",
        "ag_factor_results",
        "ag_quant_proposals",
        "ag_decision_contexts",
        "ag_consensus_decisions",
        "ag_risk_decisions",
        "ag_execution_outbox",
        "ag_order_intents",
        "ag_paper_orders",
        "ag_paper_fills",
        "ag_paper_accounts",
        "ag_paper_positions",
        "ag_paper_position_lots",
        "ag_paper_ledger_entries",
    )
    before = {name: db[name].count() for name in protected}
    service = ShadowExperimentService(db)
    shadow = await service.start(
        definition.experiment_id,
        dataset_manifest_id=manifest.dataset_manifest_id,
        created_by="test",
    )
    first = await service.process_snapshot(shadow.shadow_run_id, "snapshot")
    second = await service.process_snapshot(shadow.shadow_run_id, "snapshot")
    assert first.result_hash == second.result_hash
    assert first.snapshot_id == "snapshot"
    assert first.champion_output["snapshot_id"] == "snapshot"
    assert first.challenger_output["snapshot_id"] == "snapshot"
    assert db["ag_exp_shadow_outputs"].count() == 1
    assert before == {name: db[name].count() for name in protected}
