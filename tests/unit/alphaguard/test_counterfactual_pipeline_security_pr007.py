from __future__ import annotations

import inspect
from datetime import date, datetime
from decimal import Decimal

import pytest

from app.routers import alphaguard_evaluations
from app.services.alphaguard.counterfactual_evaluation_engine import (
    CounterfactualEvaluationEngine,
)
from app.services.alphaguard.evaluation_pipeline import (
    EVALUATION_WRITE_COLLECTIONS,
    EvaluationPipeline,
)
from app.services.alphaguard.execution_market_snapshot_service import (
    ExecutionMarketSnapshotService,
)
from app.services.alphaguard.matching_engine import MatchingEngine
from app.services.alphaguard.paper_policy_registry import PaperPolicyRegistry
from app.services.alphaguard.paper_storage import clean_document, mongo_date
from tests.unit.alphaguard._fakes import FakeDB
from tests.unit.alphaguard.pr006_helpers import daily_record, setup_paper
from tests.unit.alphaguard.pr007_helpers import (
    OPEN_DATES,
    make_label,
    make_subject,
    seed_adjusted_prices,
    seed_calendar,
)
from tradingagents.alphaguard.paper_schemas import (
    ExecutionMarketSnapshot,
    PaperOrder,
)


@pytest.mark.asyncio
async def test_signal_only_and_executable_shadow_use_eval_collections_only():
    db = FakeDB()
    await setup_paper(db, user_id="user-1")
    await ExecutionMarketSnapshotService(db).create_from_daily_record(
        record=daily_record(trade_date=date(2026, 7, 2)),
        symbol="600519",
        trade_date=date(2026, 7, 2),
        cutoff_at=datetime(2026, 7, 2, 15, 30),
        data_version="execution-v1",
        now=datetime(2026, 7, 2, 15, 31),
    )
    await ExecutionMarketSnapshotService(db).create_from_daily_record(
        record=daily_record(
            trade_date=date(2026, 7, 15),
            open_price="10.40",
            high="10.60",
            low="10.30",
            close="10.50",
        ),
        symbol="600519",
        trade_date=date(2026, 7, 15),
        cutoff_at=datetime(2026, 7, 15, 15, 30),
        data_version="execution-v1",
    )
    subject = make_subject()
    labels = [
        make_label(subject.subject_id, "10D"),
    ]
    production = [
        "ag_order_intents",
        "ag_paper_orders",
        "ag_paper_fills",
        "ag_paper_ledger_entries",
        "ag_settlement_records",
        "ag_paper_positions",
        "ag_paper_position_lots",
    ]
    before = {name: db[name].count() for name in production}
    results = await CounterfactualEvaluationEngine(db).evaluate(subject, labels)
    after = {name: db[name].count() for name in production}
    assert before == after
    assert {item.mode for item in results} == {
        "SIGNAL_ONLY",
        "EXECUTABLE_SHADOW",
    }
    shadow = next(item for item in results if item.mode == "EXECUTABLE_SHADOW")
    assert shadow.status == "FILLED"
    assert shadow.hypothetical_fills[0]["evaluation_only"] is True
    assert shadow.hypothetical_intent["production_collection_write"] is False
    assert db["ag_eval_counterfactuals"].count() == 2


@pytest.mark.asyncio
async def test_shadow_order_not_touched_is_no_fill_without_formal_fill():
    db = FakeDB()
    await setup_paper(db, user_id="user-1")
    await ExecutionMarketSnapshotService(db).create_from_daily_record(
        record=daily_record(
            trade_date=date(2026, 7, 2),
            open_price="11.00",
            high="11.50",
            low="10.50",
            close="11.20",
        ),
        symbol="600519",
        trade_date=date(2026, 7, 2),
        cutoff_at=datetime(2026, 7, 2, 15, 30),
        data_version="execution-v1",
    )
    await ExecutionMarketSnapshotService(db).create_from_daily_record(
        record=daily_record(
            trade_date=date(2026, 7, 15),
            open_price="11.20",
            high="11.50",
            low="10.80",
            close="11.10",
        ),
        symbol="600519",
        trade_date=date(2026, 7, 15),
        cutoff_at=datetime(2026, 7, 15, 15, 30),
        data_version="execution-v1",
    )
    subject = make_subject()
    results = await CounterfactualEvaluationEngine(db).evaluate(
        subject,
        [make_label(subject.subject_id, "10D")],
    )
    shadow = next(item for item in results if item.mode == "EXECUTABLE_SHADOW")
    assert shadow.status == "NO_FILL"
    assert shadow.hypothetical_fills == []
    assert db["ag_paper_fills"].count() == 0


@pytest.mark.asyncio
async def test_shadow_requires_horizon_execution_snapshot_and_does_not_guess():
    db = FakeDB()
    await setup_paper(db, user_id="user-1")
    await ExecutionMarketSnapshotService(db).create_from_daily_record(
        record=daily_record(trade_date=date(2026, 7, 2)),
        symbol="600519",
        trade_date=date(2026, 7, 2),
        cutoff_at=datetime(2026, 7, 2, 15, 30),
        data_version="execution-v1",
    )
    subject = make_subject()
    results = await CounterfactualEvaluationEngine(db).evaluate(
        subject,
        [make_label(subject.subject_id, "10D")],
    )
    shadow = next(item for item in results if item.mode == "EXECUTABLE_SHADOW")
    assert shadow.status == "INSUFFICIENT_DATA"
    assert shadow.hypothetical_fills == []


@pytest.mark.asyncio
async def test_shadow_uses_formal_matching_function_and_supports_multi_day_partials():
    db = FakeDB()
    await setup_paper(db, user_id="user-1")
    snapshot_service = ExecutionMarketSnapshotService(db)
    for trade_date in (date(2026, 7, 2), date(2026, 7, 3), date(2026, 7, 15)):
        await snapshot_service.create_from_daily_record(
            record=daily_record(trade_date=trade_date, volume=5_000),
            symbol="600519",
            trade_date=trade_date,
            cutoff_at=datetime.combine(trade_date, datetime.min.time()).replace(
                hour=15, minute=30
            ),
            data_version="execution-v1",
        )
    subject = make_subject()
    results = await CounterfactualEvaluationEngine(db).evaluate(
        subject,
        [make_label(subject.subject_id, "10D")],
    )
    shadow = next(item for item in results if item.mode == "EXECUTABLE_SHADOW")
    assert shadow.status == "PARTIALLY_FILLED"
    assert len(shadow.hypothetical_fills) == 3
    assert {item["quantity"] for item in shadow.hypothetical_fills} == {200}

    formal_order = PaperOrder.model_validate(shadow.hypothetical_order)
    raw_snapshot = clean_document(
        await db["ag_execution_market_snapshots"].find_one(
            {"trade_date": mongo_date(date(2026, 7, 2))}
        )
    )
    formal_snapshot = ExecutionMarketSnapshot.model_validate(raw_snapshot)
    policy = await PaperPolicyRegistry(db).execution_policy()
    formal = MatchingEngine().match(
        order=formal_order,
        snapshot=formal_snapshot,
        policy=policy,
        valid_reserved_quantity=formal_order.remaining_quantity,
        matched_at=datetime(2026, 7, 2, 15, 0),
    )
    assert shadow.hypothetical_fills[0]["quantity"] == formal.quantity
    assert shadow.hypothetical_fills[0]["price"] == formal.price


@pytest.mark.asyncio
async def test_continue_holding_is_distinct_from_simple_negated_return():
    db = FakeDB()
    subject = make_subject(
        subject_id="exit",
        subject_type="POSITION_EXIT",
        source_object_id="fill-1",
        stage="EXECUTION",
        status="POSITION_EXIT_FILLED",
        action="SELL",
        entry_zone=False,
        actual_execution_exists=True,
        lineage_ids={
            "fill_id": "fill-1",
            "fill_quantity": "100",
            "fill_trade_date": "2026-07-02",
            "fill_price": "10",
        },
    )
    await db["ag_paper_fills"].insert_one(
        {
            "fill_id": "fill-1",
            "fee_breakdown": {"total_fee": Decimal("5")},
            "matching_engine_version": "matching-engine-v1",
            "fee_policy_version": "fee-v1",
        }
    )
    await ExecutionMarketSnapshotService(db).create_from_daily_record(
        record=daily_record(
            trade_date=date(2026, 7, 15),
            open_price="9.10",
            high="9.20",
            low="8.90",
            close="9.00",
            limit_up="9.90",
            limit_down="8.10",
        ),
        symbol="600519",
        trade_date=date(2026, 7, 15),
        cutoff_at=datetime(2026, 7, 15, 15, 30),
        data_version="test-raw-v1",
        now=datetime(2026, 7, 15, 15, 31),
    )
    actual = make_label(
        "exit",
        "10D",
        raw=Decimal("-0.10"),
        aligned=Decimal("0.10"),
    ).model_copy(
        update={
            "anchor_type": "ACTUAL_FILL",
            "anchor_price": Decimal("10"),
            "execution_anchor_price": Decimal("10"),
            "horizon_end_date": date(2026, 7, 15),
            "horizon_close_price": Decimal("9"),
        }
    )
    results = await CounterfactualEvaluationEngine(db).evaluate(subject, [actual])
    holding = next(item for item in results if item.mode == "CONTINUE_HOLDING")
    assert holding.status == "CALCULATED"
    assert holding.gross_pnl == Decimal("100")
    assert holding.net_pnl == Decimal("95")
    assert holding.return_pct == Decimal("0.095")


async def _seed_pipeline_source(db):
    await db["ag_evidence_snapshots"].insert_one(
        {
            "snapshot_id": "snapshot-1",
            "user_id": "user-1",
            "symbol": "600519",
            "market": "CN",
            "trade_date": date(2026, 7, 1),
            "price_cutoff_at": datetime(2026, 7, 1, 15, 0),
            "news_cutoff_at": datetime(2026, 7, 1, 14, 0),
            "announcement_cutoff_at": datetime(2026, 7, 1, 14, 0),
        }
    )
    await db["ag_quant_proposals"].insert_one(
        {
            "proposal_id": "proposal-1",
            "snapshot_id": "snapshot-1",
            "user_id": "user-1",
            "candidate_id": "candidate-1",
            "symbol": "600519",
            "market": "CN",
            "trade_date": date(2026, 7, 1),
            "status": "TRIGGERED",
            "action_candidate": "BUY",
            "strategy_id": "strategy-v1",
            "strategy_version": "1.0.0",
            "entry_zone": {"lower": 9.9, "upper": 10.1},
            "initial_position_pct": 0.05,
            "max_position_pct": 0.1,
            "evidence_refs": [],
            "created_at": datetime(2026, 7, 1, 15, 1),
        }
    )
    await seed_calendar(db)
    await seed_adjusted_prices(db)


@pytest.mark.asyncio
async def test_pipeline_end_to_end_is_idempotent_and_has_no_production_writes():
    db = FakeDB()
    await _seed_pipeline_source(db)
    production = [
        "ag_quant_proposals",
        "ag_evidence_snapshots",
        "ag_candidates",
        "analysis_reports",
        "ag_consensus_decisions",
        "ag_risk_decisions",
        "ag_order_intents",
        "ag_paper_orders",
        "ag_paper_fills",
        "ag_paper_accounts",
        "ag_paper_positions",
        "ag_paper_ledger_entries",
    ]
    before = {
        name: [dict(item) for item in db[name].documents]
        for name in production
    }
    pipeline = EvaluationPipeline(db)
    result = await pipeline.evaluate_trade_date(
        as_of_trade_date=OPEN_DATES[-1],
        user_id="user-1",
    )
    sizes = {
        name: db[name].count()
        for name in EVALUATION_WRITE_COLLECTIONS
    }
    reused = await pipeline.evaluate_trade_date(
        as_of_trade_date=OPEN_DATES[-1],
        user_id="user-1",
    )
    assert result == reused
    assert sizes == {
        name: db[name].count()
        for name in EVALUATION_WRITE_COLLECTIONS
    }
    assert result.subjects_created == 1
    assert result.labels_calculated == 8
    assert result.production_writes is False
    assert all(name.startswith("ag_eval_") for name in result.write_collections)
    assert before == {
        name: [dict(item) for item in db[name].documents]
        for name in production
    }


@pytest.mark.asyncio
async def test_historical_replay_does_not_discover_future_decisions():
    db = FakeDB()
    await _seed_pipeline_source(db)
    await db["ag_quant_proposals"].insert_one(
        {
            "proposal_id": "proposal-future",
            "snapshot_id": "snapshot-future",
            "user_id": "user-1",
            "candidate_id": "candidate-future",
            "symbol": "600519",
            "market": "CN",
            "trade_date": date(2026, 7, 29),
            "status": "WATCH",
            "action_candidate": "WAIT",
            "strategy_id": "strategy-v1",
            "strategy_version": "1.0.0",
            "initial_position_pct": 0,
            "max_position_pct": 0,
            "evidence_refs": [],
        }
    )
    await db["ag_evidence_snapshots"].insert_one(
        {
            "snapshot_id": "snapshot-future",
            "user_id": "user-1",
            "symbol": "600519",
            "market": "CN",
            "trade_date": date(2026, 7, 29),
            "price_cutoff_at": datetime(2026, 7, 29, 15, 0),
        }
    )
    await EvaluationPipeline(db).evaluate_trade_date(
        as_of_trade_date=date(2026, 7, 15),
        user_id="user-1",
    )
    sources = {
        item["source_object_id"] for item in db["ag_eval_subjects"].documents
    }
    assert sources == {"proposal-1"}


@pytest.mark.asyncio
async def test_single_subject_evaluation_is_idempotent_and_eval_only():
    db = FakeDB()
    await _seed_pipeline_source(db)
    pipeline = EvaluationPipeline(db)
    subjects, _, _ = await pipeline.subjects.discover(
        user_id="user-1",
        decision_trade_date_lte=OPEN_DATES[-1],
    )
    first = await pipeline.evaluate_subject(
        subject_id=subjects[0].subject_id,
        as_of_trade_date=OPEN_DATES[-1],
    )
    counts = {
        name: db[name].count()
        for name in EVALUATION_WRITE_COLLECTIONS
        if name != "ag_eval_events"
    }
    second = await pipeline.evaluate_subject(
        subject_id=subjects[0].subject_id,
        as_of_trade_date=OPEN_DATES[-1],
    )
    assert first == second
    assert counts == {
        name: db[name].count()
        for name in EVALUATION_WRITE_COLLECTIONS
        if name != "ag_eval_events"
    }
    assert first["production_writes"] is False


@pytest.mark.asyncio
async def test_run_schedule_is_idempotent_and_large_work_is_background():
    db = FakeDB()
    pipeline = EvaluationPipeline(db)
    first, created = await pipeline.schedule(
        as_of_trade_date=date(2026, 7, 31),
        user_id="user-1",
    )
    second, created_again = await pipeline.schedule(
        as_of_trade_date=date(2026, 7, 31),
        user_id="user-1",
    )
    assert created is True
    assert created_again is False
    assert first.evaluation_job_id == second.evaluation_job_id
    assert db["ag_eval_runs"].count() == 1
    assert first.status == "PENDING"


def test_counterfactual_and_pipeline_do_not_import_production_write_services():
    counterfactual_source = inspect.getsource(
        CounterfactualEvaluationEngine
    )
    pipeline_source = inspect.getsource(EvaluationPipeline)
    forbidden = [
        "OrderIntentFactory",
        "PaperOrderService",
        "SettlementService",
        "DecisionPipeline",
        "ExecutionOutboxService",
    ]
    assert all(name not in counterfactual_source for name in forbidden)
    assert all(name not in pipeline_source for name in forbidden)


def test_production_decision_modules_do_not_import_future_evaluation_services():
    from app.services.alphaguard import (
        decision_context_builder,
        decision_pipeline,
        factor_engine,
        hard_risk_engine,
        strategy_engine,
    )

    modules = [
        factor_engine,
        strategy_engine,
        decision_context_builder,
        decision_pipeline,
        hard_risk_engine,
    ]
    for module in modules:
        source = inspect.getsource(module)
        assert "evaluation_schemas" not in source
        assert "evaluation_repository" not in source
        assert "horizon_label" not in source


def test_evaluation_api_has_no_mutating_machine_fact_or_delete_routes():
    paths = {
        (method, route.path)
        for route in alphaguard_evaluations.router.routes
        for method in route.methods
    }
    assert ("POST", "/alphaguard/evaluations/run") in paths
    assert any(
        method == "POST" and path.endswith("/overrides")
        for method, path in paths
    )
    assert all(method != "DELETE" for method, _ in paths)
    assert all("horizon-label" not in path for method, path in paths if method == "POST")
    assert all("counterfactual" not in path for method, path in paths if method == "POST")
