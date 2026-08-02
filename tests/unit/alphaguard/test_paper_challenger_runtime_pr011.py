from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi import HTTPException

import app.routers.alphaguard_experiments as experiment_router
from app.schemas.alphaguard.quant import (
    FactorEvidenceBundle,
    FactorResult,
    GroupAggregation,
    MarketRegimeResult,
    QuantTradeProposal,
)
from app.services.alphaguard.challenger_assignment_service import (
    ChallengerAssignmentService,
)
from app.services.alphaguard.attribution_engine import AttributionEngine
from app.services.alphaguard.evaluation_subject_builder import EvaluationSubjectBuilder
from app.services.alphaguard.experiment_task_service import ExperimentTaskService
from app.services.alphaguard.paper_account_service import PaperAccountService
from app.services.alphaguard.paper_challenger_query_service import (
    PaperChallengerQueryService,
)
from app.services.alphaguard.paper_challenger_runtime_service import (
    PaperChallengerRuntimeService,
)
from app.services.alphaguard.paper_challenger_scheduler_service import (
    PaperChallengerSchedulerService,
)
from app.services.alphaguard.operations_service import AlphaGuardOperationsService
from app.services.alphaguard.paper_storage import clean_document
from app.services.alphaguard.paper_task_service import PaperTaskService
from app.services.alphaguard.risk_policy_registry import RiskPolicyRegistry
from app.services.alphaguard.snapshot_data_resolver import ResolvedSnapshotData
from tests.unit.alphaguard._fakes import FakeDB
from tests.unit.alphaguard.pr005_helpers import make_plan, make_review
from tests.unit.alphaguard.pr006_helpers import daily_record, setup_paper
from tests.unit.alphaguard.pr008_helpers import seed_single_variable_experiment
from tests.unit.alphaguard.test_evidence_window_v2 import _v2_data, _with_hash
from tradingagents.alphaguard.decision_schemas import EvidenceRef
from tradingagents.alphaguard.experiment_schemas import ShadowRun, experiment_hash
from tradingagents.alphaguard.mongo_indexes import ALPHAGUARD_INDEX_SPECS


ROOT = Path(__file__).resolve().parents[3]
TRADE_DATE = date(2026, 7, 29)


class StubResolver:
    def __init__(self, resolved):
        self.resolved = resolved

    async def resolve(self, snapshot_id: str, *, user_id: str):
        assert snapshot_id == self.resolved.snapshot.snapshot_id
        assert user_id == self.resolved.snapshot.user_id
        return self.resolved


class StubAdapter:
    def __init__(self, output):
        self.output = output

    def run_pair(self, data, baseline, challenger):
        champion = {**self.output, "component_version_ref": baseline.version_ref}
        challenger_output = {
            **self.output,
            "component_version_ref": challenger.version_ref,
        }
        return champion, challenger_output, {
            "component_paths": ["factor_weights.MOMENTUM_20D"],
            "outputs_equal": False,
        }


class StubModelExecutor:
    def __init__(self, *, normal_status="PROPOSE_TRADE", top_status="CONFIRM"):
        self.normal_status = normal_status
        self.top_status = top_status
        self.prepare_count = 0
        self.normal_count = 0
        self.top_count = 0

    async def prepare(self, *, context, data, run):
        self.prepare_count += 1
        return [
            {
                "research_result_id": f"research:{run.run_id}",
                "status": "SUCCESS",
                "summary": "fixed snapshot research",
            }
        ]

    async def run_normal(self, *, context, revision_request=None, original_plan=None):
        self.normal_count += 1
        return make_plan(context, status=self.normal_status)

    async def run_top(self, *, context, plan, risk_policy_summary):
        self.top_count += 1
        return make_review(context, plan, status=self.top_status)


def _adapter_output(snapshot_id: str) -> dict:
    reference = "stock_daily_quotes:price-1"
    factor = FactorResult(
        result_id="challenger-factor-1",
        factor_id="MOMENTUM_20D",
        factor_version="1.0.0",
        group="TREND",
        symbol="600519",
        market="CN",
        trade_date=TRADE_DATE,
        snapshot_id=snapshot_id,
        raw_value=1,
        normalized_score=80,
        direction="POSITIVE",
        confidence=1,
        missing_reason=None,
        input_refs=[reference],
        input_hash="1" * 64,
        code_hash="2" * 64,
        parameter_hash="3" * 64,
        calculated_at=datetime(2026, 7, 29, 15),
    )
    bundle = FactorEvidenceBundle(
        snapshot_id=snapshot_id,
        factor_set_version="challenger-factor-set-v1",
        results=[factor],
        group_scores={"TREND": 80},
        group_coverage={"TREND": 1},
        group_details={
            "TREND": GroupAggregation(
                valid_factor_count=1,
                total_factor_count=1,
                coverage=1,
                factor_weights={"MOMENTUM_20D": 1},
                missing_factor_ids=[],
                score=80,
            )
        },
        missing_factor_ids=[],
        risk_flags=[],
        input_hash="4" * 64,
        calculated_at=datetime(2026, 7, 29, 15),
    )
    regime = MarketRegimeResult(
        regime_result_id="challenger-regime-1",
        snapshot_id=snapshot_id,
        trade_date=TRADE_DATE,
        calculation_status="CALCULATED",
        regime="TREND_UP",
        confidence=1,
        evidence=[reference],
        metrics={"market_breadth": 0.6},
        allowed_strategy_ids=["SWING_TREND_PULLBACK_V1"],
        allow_new_positions=True,
        max_total_exposure_pct=0.6,
        regime_version="challenger-regime-v1",
        input_hash="5" * 64,
        calculated_at=datetime(2026, 7, 29, 15),
    )
    proposal = QuantTradeProposal(
        proposal_id="challenger-proposal-1",
        candidate_id="candidate-1",
        user_id="user-1",
        symbol="600519",
        market="CN",
        trade_date=TRADE_DATE,
        snapshot_id=snapshot_id,
        strategy_id="SWING_TREND_PULLBACK_V1",
        strategy_version="challenger-strategy-v1",
        regime_result_id=regime.regime_result_id,
        factor_set_version=bundle.factor_set_version,
        status="TRIGGERED",
        action_candidate="BUY",
        entry_zone={"lower": 99, "upper": 101, "currency": "CNY"},
        initial_position_pct=0.05,
        max_position_pct=0.1,
        add_conditions=[],
        reduce_conditions=[],
        exit_conditions=[{"condition_id": "exit", "description": "exit"}],
        invalidation_conditions=[
            {"condition_id": "invalid", "description": "invalid"}
        ],
        valid_until=datetime(2026, 8, 3),
        expected_holding_days=(1, 20),
        factor_summary={"TREND": 80},
        factor_result_ids=[factor.result_id],
        evidence_refs=[
            EvidenceRef(evidence_id=reference, summary="close=100", source="price")
        ],
        risk_flags=[],
        reason_codes=["FIXED_TRIGGER"],
        explanation="deterministic Challenger fixture",
        input_hash="6" * 64,
        created_at=datetime(2026, 7, 29, 15),
        automated_execution_allowed=False,
    )
    payload = {
        "snapshot_id": snapshot_id,
        "factor_bundle": bundle.model_dump(mode="json"),
        "market_regime": regime.model_dump(mode="json"),
        "quant_proposals": [proposal.model_dump(mode="json")],
        "production_writes": False,
    }
    return {**payload, "output_hash": experiment_hash(payload)}


async def _ready_runtime(
    *,
    normal_status="PROPOSE_TRADE",
    top_status="CONFIRM",
    suspended=False,
):
    db = FakeDB()
    accounts = await setup_paper(db, user_id="user-1")
    for session in (
        date(2026, 7, 29),
        date(2026, 7, 30),
        date(2026, 7, 31),
        date(2026, 8, 3),
        date(2026, 8, 4),
        date(2026, 8, 5),
    ):
        await db["trading_calendar"].insert_one(
            {
                "calendar_id": f"CN:{session.isoformat()}",
                "market": "CN",
                "session_date": session.isoformat(),
                "is_open": True,
                "published_at": datetime(2026, 1, 1),
            }
        )
    await RiskPolicyRegistry(db).register_builtin()
    registry, definition, *_ = await seed_single_variable_experiment(
        db, user_id="user-1", validation_only=True
    )
    for target in ("EXPERIMENT", "BACKTESTED", "SHADOW"):
        await registry.transition(definition.experiment_id, target, reason="test")
    shadow = ShadowRun(
        shadow_run_id="shadow-pr011",
        experiment_id=definition.experiment_id,
        run_id="shadow-run-pr011",
        status="COMPLETED",
        started_at=datetime(2026, 7, 1),
        ended_at=datetime(2026, 7, 28),
        champion_output_count=20,
        challenger_output_count=20,
        paired_output_count=20,
        divergence_count=1,
        integrity_error_count=0,
        min_required_trade_days=20,
        observed_trade_days=20,
        input_hash="7" * 64,
        created_at=datetime(2026, 7, 1),
    )
    await db["ag_exp_shadow_runs"].insert_one(shadow.model_dump(mode="python"))
    assignment = await ChallengerAssignmentService(db).activate(
        definition.experiment_id,
        user_id="user-1",
        activation_trade_date=TRADE_DATE,
        now=datetime(2026, 7, 29, 8),
    )
    raw = _v2_data()
    raw["snapshot_id"] = "snapshot-pr011"
    raw["trade_date"] = TRADE_DATE
    raw["user_id"] = "user-1"
    snapshot = _with_hash(raw)
    await db["ag_evidence_snapshots"].insert_one(snapshot.model_dump(mode="python"))
    refs = [
        "stock_daily_quotes:price-1",
        "instrument:600519",
        "trading_status:600519:2026-07-29",
        "trading_calendar:2026-07-30",
    ]
    resolved = ResolvedSnapshotData(
        snapshot=snapshot,
        prices=[
            {
                "_reference": refs[0],
                "symbol": "600519",
                "market": "CN",
                "trade_date": TRADE_DATE,
                "close": 100,
                "average_amount_20d": 100_000_000,
            }
        ],
        instruments=[
            {
                "_reference": refs[1],
                "symbol": "600519",
                "market": "CN",
                "industry": "电池",
                "suspended": suspended,
                "is_st": False,
                "at_limit_up": False,
                "at_limit_down": False,
                "average_amount_20d": 100_000_000,
            }
        ],
        trading_status=[
            {
                "_reference": refs[2],
                "symbol": "600519",
                "market": "CN",
                "trade_date": TRADE_DATE,
                "is_suspended": suspended,
                "is_st": False,
                "upper_limit_price": 110,
                "lower_limit_price": 90,
            }
        ],
        trading_calendar=[
            {
                "_reference": refs[3],
                "market": "CN",
                "session_date": date(2026, 7, 30),
                "is_open": True,
            }
        ],
        input_refs=refs,
        excluded_refs=[],
        input_hash="8" * 64,
    )
    model_executor = StubModelExecutor(
        normal_status=normal_status, top_status=top_status
    )
    runtime = PaperChallengerRuntimeService(
        db,
        model_executor=model_executor,
        snapshot_resolver=StubResolver(resolved),
        component_adapter=StubAdapter(_adapter_output(snapshot.snapshot_id)),
    )
    return db, accounts, definition, assignment, runtime, model_executor


@pytest.mark.asyncio
async def test_fourth_account_initialization_is_idempotent_and_isolated():
    db = FakeDB()
    first = await setup_paper(db, user_id="user-1")
    assert set(first) == {
        "PAPER_QUANT",
        "PAPER_NORMAL",
        "PAPER_TOP_CONFIRMED",
        "PAPER_CHALLENGER",
    }
    assert {item.initial_cash for item in first.values()} == {Decimal("1000000")}
    before = {key: item.cash_available for key, item in first.items()}
    second = await PaperAccountService(db).initialize_user_accounts("user-1")
    assert {key: item.cash_available for key, item in second.items()} == before
    assert db["ag_paper_accounts"].count() == 4


@pytest.mark.asyncio
async def test_challenger_query_filters_legacy_experiments_and_maps_policy_report():
    db, _, definition, _, _, _ = await _ready_runtime()
    await db["ag_exp_definitions"].insert_one(
        {
            "experiment_id": "legacy-pr008",
            "user_id": "user-1",
            "name": "legacy experiment",
            "status": "BACKTESTED",
            "created_at": datetime(2026, 1, 1),
        }
    )
    await db["ag_exp_comparison_reports"].insert_one(
        {
            "comparison_report_id": "comparison-pr011",
            "experiment_id": definition.experiment_id,
            "status": "READY",
            "return_comparison": {
                "champion": Decimal("0.10"),
                "challenger": Decimal("0.12"),
            },
            "drawdown_comparison": {
                "champion": Decimal("-0.08"),
                "challenger": Decimal("-0.06"),
                "worsening": Decimal("-0.02"),
            },
            "cost_comparison": {
                "champion": Decimal("0.003"),
                "challenger": Decimal("0.002"),
            },
            "turnover_comparison": {
                "champion": Decimal("0.30"),
                "challenger": Decimal("0.25"),
            },
            "champion_summary": {"trade_count": 10},
            "challenger_summary": {"trade_count": 8},
            "regime_stability_comparison": {
                "available_segments": ["TREND_UP", "RANGE_WEAK"]
            },
            "outlier_dependency_comparison": {
                "top_trade_contribution_pct": Decimal("0.20"),
                "top_five_trade_contribution_pct": Decimal("0.55"),
            },
            "created_at": datetime(2026, 7, 31),
        }
    )

    query = PaperChallengerQueryService(db)
    listed = await query.list(user_id="user-1")
    assert [item["experiment_id"] for item in listed] == [definition.experiment_id]

    comparison = await query.comparison(definition.experiment_id)
    assert comparison["comparison_report_id"] == "comparison-pr011"
    assert comparison["return_difference"] == Decimal("0.02")
    assert comparison["drawdown_difference"] == Decimal("-0.02")
    assert comparison["return_drawdown_ratio_difference"] == Decimal("0.75")
    assert comparison["trade_count_difference"] == Decimal("-2")
    assert comparison["turnover_difference"] == Decimal("-0.05")
    assert comparison["cost_difference"] == Decimal("-0.001")
    assert comparison["regime_difference"]["available_segments"] == [
        "TREND_UP",
        "RANGE_WEAK",
    ]


@pytest.mark.asyncio
async def test_complete_challenger_chain_outbox_t1_fill_settlement_and_evaluation():
    db, accounts, definition, assignment, runtime, executor = await _ready_runtime()
    baseline = {
        key: (value.cash_available, value.cash_reserved, value.realized_pnl)
        for key, value in accounts.items()
        if key != "PAPER_CHALLENGER"
    }
    run, reused = await runtime.run(
        experiment_id=definition.experiment_id,
        snapshot_id="snapshot-pr011",
        trading_date=TRADE_DATE,
        candidate_id="candidate-1",
        now=datetime(2026, 7, 29, 16),
    )
    assert reused is False
    assert run.status == "COMPLETED"
    assert run.outbox_event_id
    assert executor.prepare_count == executor.normal_count == executor.top_count == 1
    assert db["ag_order_intents"].count() == 0
    assert db["ag_execution_outbox"].count() == 1
    assert db["ag_quant_proposals"].count() == 0
    assert db["analysis_reports"].count() == 0
    assert db["ag_consensus_decisions"].count() == 0
    assert db["ag_risk_decisions"].count() == 0

    repeated, repeated_flag = await runtime.run(
        experiment_id=definition.experiment_id,
        snapshot_id="snapshot-pr011",
        trading_date=TRADE_DATE,
        candidate_id="candidate-1",
        now=datetime(2026, 7, 29, 16),
    )
    assert repeated_flag is True
    assert repeated.result_hash == run.result_hash
    assert executor.prepare_count == executor.normal_count == executor.top_count == 1
    assert db["ag_execution_outbox"].count() == 1

    tasks = PaperTaskService(db)
    assert await tasks.process_execution_outbox() == {
        "completed": 1,
        "failed": 0,
        "dead_letter": 0,
    }
    intent = clean_document(db["ag_order_intents"].documents[0])
    order = clean_document(db["ag_paper_orders"].documents[0])
    reservation = clean_document(db["ag_paper_reservations"].documents[0])
    expected_lineage = {
        "snapshot_id": "snapshot-pr011",
        "experiment_id": definition.experiment_id,
        "assignment_id": assignment.assignment_id,
        "challenger_version_id": assignment.challenger_version_id,
        "baseline_champion_id": assignment.baseline_champion_id,
        "config_hash": assignment.config_hash,
        "run_mode": "PAPER_CHALLENGER",
    }
    outbox = clean_document(db["ag_execution_outbox"].documents[0])
    for item in (outbox, intent, order, reservation):
        assert {key: item.get(key) for key in expected_lineage} == expected_lineage
    assert intent["account_id"] == assignment.account_id
    assert intent["experiment_id"] == definition.experiment_id
    assert order["experiment_id"] == definition.experiment_id
    assert order["earliest_execute_at"].date() == date(2026, 7, 30)

    await db["stock_daily_quotes"].insert_one(
        daily_record(
            trade_date=date(2026, 7, 30),
            open_price="100",
            high="102",
            low="99",
            close="101",
            limit_up="110",
            limit_down="90",
        )
    )
    assert await tasks.build_execution_market_snapshots(date(2026, 7, 30)) == {
        "created_or_reused": 1,
        "failed": 0,
    }
    assert await tasks.match_orders_for_trade_date(date(2026, 7, 30)) == {
        "fills": 1,
        "no_fill": 0,
    }
    assert await tasks.settle_pending_fills() == {"committed": 1, "failed": 0}
    fill = clean_document(db["ag_paper_fills"].documents[0])
    lot = clean_document(db["ag_paper_position_lots"].documents[0])
    settlement = clean_document(db["ag_settlement_records"].documents[0])
    ledgers = [clean_document(item) for item in db["ag_paper_ledger_entries"].documents]
    for item in (fill, lot, settlement, *ledgers):
        assert {key: item.get(key) for key in expected_lineage} == expected_lineage
    assert fill["experiment_id"] == definition.experiment_id
    position = clean_document(
        await db["ag_paper_positions"].find_one(
            {"account_id": assignment.account_id, "symbol": "600519"}
        )
    )
    assert position["quantity"] > 0
    assert position["available_quantity"] == 0
    assert {key: position.get(key) for key in expected_lineage} == expected_lineage
    assert position["snapshot_ids"] == ["snapshot-pr011"]

    subjects, created, _ = await EvaluationSubjectBuilder(db).discover(
        user_id="user-1", decision_trade_date_lte=date(2026, 7, 30)
    )
    challenger_subjects = [
        item
        for item in subjects
        if item.lineage_ids.get("experiment_id") == definition.experiment_id
    ]
    assert created > 0
    assert {item.subject_type for item in challenger_subjects} >= {
        "QUANT_PROPOSAL",
        "NORMAL_PLAN",
        "TOP_REVIEW",
        "CONSENSUS",
        "RISK_DECISION",
        "ORDER_INTENT",
        "PAPER_ORDER",
        "PAPER_FILL",
    }
    for subject in challenger_subjects:
        for key, value in expected_lineage.items():
            if key != "snapshot_id":
                assert subject.lineage_ids[key] == value
    attribution = AttributionEngine(db).evaluate(
        challenger_subjects[0], [], [], []
    )
    assert attribution.lineage_ids == challenger_subjects[0].lineage_ids
    comparison = await PaperChallengerQueryService(db).comparison(
        definition.experiment_id
    )
    assert comparison["promotion_action"] == "MANUAL_REVIEW_ONLY"

    for account_type, before in baseline.items():
        stored = await PaperAccountService(db).get_user_account("user-1", account_type)
        assert stored is not None
        assert (stored.cash_available, stored.cash_reserved, stored.realized_pnl) == before
    assert db["ag_candidates"].count() == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("normal_status", "top_status", "failure"),
    [("WAIT", "CONFIRM", "NORMAL_WAIT"), ("PROPOSE_TRADE", "REJECT", "CONSENSUS_REJECT")],
)
async def test_model_or_consensus_stop_never_creates_challenger_outbox(
    normal_status, top_status, failure
):
    db, _, definition, _, runtime, _ = await _ready_runtime(
        normal_status=normal_status, top_status=top_status
    )
    run, _ = await runtime.run(
        experiment_id=definition.experiment_id,
        snapshot_id="snapshot-pr011",
        trading_date=TRADE_DATE,
        candidate_id="candidate-1",
        now=datetime(2026, 7, 29, 16),
    )
    assert run.status == "BLOCKED"
    assert run.failure_code == failure
    assert db["ag_execution_outbox"].count() == 0
    assert db["ag_order_intents"].count() == 0


@pytest.mark.asyncio
async def test_hard_risk_reject_never_creates_challenger_outbox():
    db, _, definition, _, runtime, _ = await _ready_runtime(suspended=True)
    run, _ = await runtime.run(
        experiment_id=definition.experiment_id,
        snapshot_id="snapshot-pr011",
        trading_date=TRADE_DATE,
        candidate_id="candidate-1",
        now=datetime(2026, 7, 29, 16),
    )
    assert run.status == "BLOCKED"
    assert run.failure_code == "HARD_RISK_REJECT"
    assert db["ag_execution_outbox"].count() == 0


@pytest.mark.asyncio
async def test_failed_run_preserves_completed_stage_audit():
    db, _, definition, _, runtime, executor = await _ready_runtime()
    original_run_normal = executor.run_normal

    async def fail_normal(**_kwargs):
        executor.normal_count += 1
        raise RuntimeError("fixed model failure")

    executor.run_normal = fail_normal
    with pytest.raises(RuntimeError, match="fixed model failure"):
        await runtime.run(
            experiment_id=definition.experiment_id,
            snapshot_id="snapshot-pr011",
            trading_date=TRADE_DATE,
            candidate_id="candidate-1",
            now=datetime(2026, 7, 29, 16),
        )
    stored = clean_document(db["ag_exp_challenger_runs"].documents[0])
    assert stored["status"] == "FAILED"
    assert stored["terminal_stage"] == "RESEARCH_RESULT"
    assert stored["stage_record_ids"]
    assert len(stored["stage_record_ids"]) == db["ag_exp_challenger_objects"].count()
    executor.run_normal = original_run_normal
    recovered, reused = await runtime.run(
        experiment_id=definition.experiment_id,
        snapshot_id="snapshot-pr011",
        trading_date=TRADE_DATE,
        candidate_id="candidate-1",
        retry_failed=True,
        now=datetime(2026, 7, 29, 16, 5),
    )
    assert reused is False
    assert recovered.status == "COMPLETED"
    assert db["ag_exp_challenger_runs"].count() == 1
    assert db["ag_execution_outbox"].count() == 1


@pytest.mark.asyncio
async def test_worker_restart_recovers_only_stale_challenger_tasks():
    db = FakeDB()
    stale_at = datetime(2026, 7, 29, 10)
    await db["ag_exp_task_runs"].insert_one(
        {
            "task_run_id": "stale-challenger",
            "job_type": "PAPER_CHALLENGER",
            "experiment_id": "experiment",
            "idempotency_key": "stale-key",
            "status": "RUNNING",
            "attempt_count": 1,
            "max_attempts": 3,
            "result": {"request": {}},
            "created_at": stale_at,
            "updated_at": stale_at,
        }
    )
    await db["ag_exp_task_runs"].insert_one(
        {
            "task_run_id": "stale-backtest",
            "job_type": "HISTORICAL_REPLAY",
            "experiment_id": "experiment",
            "idempotency_key": "other-key",
            "status": "RUNNING",
            "attempt_count": 1,
            "result": {"request": {}},
            "created_at": stale_at,
            "updated_at": stale_at,
        }
    )
    recovered = await ExperimentTaskService(db)._recover_stale_challenger_tasks(
        job_types={"PAPER_CHALLENGER"},
        now=datetime(2026, 7, 29, 13),
    )
    assert recovered == 1
    challenger = clean_document(db["ag_exp_task_runs"].documents[0])
    backtest = clean_document(db["ag_exp_task_runs"].documents[1])
    assert challenger["status"] == "PENDING"
    assert challenger["attempt_count"] == 2
    assert challenger["error"] == "WORKER_RESTART_RECOVERY"
    assert backtest["status"] == "RUNNING"


@pytest.mark.asyncio
async def test_scheduler_requires_active_assignment_and_candidate_pool_membership():
    empty = FakeDB()
    assert await PaperChallengerSchedulerService(empty).enqueue_for_trade_date(
        TRADE_DATE
    ) == {
        "active_assignments": 0,
        "queued_or_reused": 0,
        "skipped_missing_candidate": 0,
    }
    assert empty["ag_exp_task_runs"].count() == 0

    db, _, definition, _, _, executor = await _ready_runtime()
    skipped = await PaperChallengerSchedulerService(db).enqueue_for_trade_date(
        TRADE_DATE
    )
    assert skipped["skipped_missing_candidate"] == 1
    assert db["ag_exp_task_runs"].count() == 0
    assert executor.prepare_count == executor.normal_count == executor.top_count == 0
    await db["ag_candidates"].insert_one(
        {
            "candidate_id": "candidate-1",
            "user_id": "user-1",
            "symbol": "600519",
            "market": "CN",
            "trade_date": TRADE_DATE,
        }
    )
    service = PaperChallengerSchedulerService(db)
    first = await service.enqueue_for_trade_date(TRADE_DATE)
    second = await service.enqueue_for_trade_date(TRADE_DATE)
    assert first["queued_or_reused"] == second["queued_or_reused"] == 1
    assert db["ag_exp_task_runs"].count() == 1
    task = clean_document(db["ag_exp_task_runs"].documents[0])
    assert task["experiment_id"] == definition.experiment_id
    assert task["job_type"] == "PAPER_CHALLENGER"
    assert executor.prepare_count == executor.normal_count == executor.top_count == 0


@pytest.mark.asyncio
async def test_pause_cancels_new_tasks_and_retirement_is_terminal():
    db, _, definition, assignment, _, _ = await _ready_runtime()
    await db["ag_exp_task_runs"].insert_one(
        {
            "task_run_id": "pending-pr011",
            "job_type": "PAPER_CHALLENGER",
            "experiment_id": definition.experiment_id,
            "status": "PENDING",
        }
    )
    service = ChallengerAssignmentService(db)
    paused = await service.pause(definition.experiment_id, reason="manual pause")
    assert paused.status == "SUSPENDED"
    assert db["ag_exp_task_runs"].documents[0]["error"] == "CHALLENGER_PAUSED"
    await service.retire(definition.experiment_id, reason="manual retire")
    retired = await service.registry.get(definition.experiment_id)
    assert retired.status == "RETIRED"
    with pytest.raises(ValueError, match="SHADOW"):
        await service.activate(
            definition.experiment_id,
            user_id=assignment.user_id,
            activation_trade_date=date(2026, 7, 30),
        )


def test_pr011_api_security_indexes_and_chinese_workflow_contract():
    with pytest.raises(HTTPException) as exc:
        experiment_router._require_admin({"id": "user", "is_admin": False})
    assert exc.value.status_code == 403
    assert "ag_exp_challenger_runs" in ALPHAGUARD_INDEX_SPECS
    assert "ag_exp_challenger_objects" in ALPHAGUARD_INDEX_SPECS
    routes = {(method, route.path) for route in experiment_router.router.routes for method in route.methods}
    for suffix in (
        "", "/{experiment_id}", "/{experiment_id}/backtest",
        "/{experiment_id}/shadow", "/{experiment_id}/activate",
        "/{experiment_id}/pause", "/{experiment_id}/retire",
        "/{experiment_id}/runs", "/{experiment_id}/decisions",
        "/{experiment_id}/orders", "/{experiment_id}/evaluation",
        "/{experiment_id}/comparison",
    ):
        assert any(path == f"/alphaguard/experiments/challengers{suffix}" for _, path in routes)
    assert not any("promote" in path for _, path in routes if "/challengers" in path)
    frontend = (ROOT / "frontend/src/components/paper/AlphaGuardExperimentLab.vue").read_text("utf-8")
    for label in (
        "选择 Champion", "选择变量", "填写变更", "历史回放", "样本外验证",
        "Shadow 观察", "模拟挑战", "查看对比", "人工评审",
        "不会连接券商", "不会自动替换", "提交人工评审",
        "收益回撤比差", "交易次数差", "换手率差", "不同市场状态表现",
    ):
        assert label in frontend
    governance = (
        ROOT / "frontend/src/components/paper/AlphaGuardExperimentGovernance.vue"
    ).read_text("utf-8")
    for label in ("实验治理", "人工审批", "审阅批准", "确认回退"):
        assert label in governance
    operations = (ROOT / "app/services/alphaguard/operations_service.py").read_text("utf-8")
    assert "FULL_CHALLENGER_PIPELINE_NOT_READY" not in operations
    assert '"active_challenger": active_challenger' in operations
    operations_page = (
        ROOT / "frontend/src/views/AlphaGuard/Operations.vue"
    ).read_text("utf-8")
    for label in (
        "挑战者运行",
        "活动挑战者",
        "模拟账户",
        "最近运行",
        "最近成功",
        "最近失败",
        "待执行任务",
        "模型调用量",
        "资源预算",
        "订单 / 成交",
        "评价成熟度",
    ):
        assert label in operations_page


@pytest.mark.asyncio
async def test_challenger_framework_readiness_is_separate_from_model_readiness(
    monkeypatch,
):
    async def model_status(_self, *, admin):
        assert admin is True
        return {
            "status": "NOT_CONFIGURED",
            "profiles": [
                {
                    "role": role,
                    "configured": False,
                    "capability": "UNVERIFIED",
                }
                for role in (
                    "RESEARCH_AGENT",
                    "NORMAL_TRADER",
                    "TOP_RISK_REVIEWER",
                )
            ],
        }

    monkeypatch.setattr(
        "app.services.alphaguard.model_runtime_status_service."
        "ModelRuntimeStatusService.status",
        model_status,
    )
    db = FakeDB()
    await db["ag_paper_accounts"].insert_one(
        {
            "account_type": "PAPER_CHALLENGER",
            "market": "CN",
            "status": "ACTIVE",
        }
    )
    await db["ag_exp_promotion_policies"].insert_one({"policy_id": "policy"})
    await db["ag_exp_component_versions"].insert_one({"version_ref": "version"})

    statuses = await AlphaGuardOperationsService(db).data_readiness()
    by_component = {item.component: item for item in statuses}

    assert by_component["MODEL_PROVIDER"].status == "NOT_CONFIGURED"
    assert by_component["CHALLENGER_PIPELINE"].status == "READY"
    assert by_component["CHALLENGER_PIPELINE"].record_count == 1
