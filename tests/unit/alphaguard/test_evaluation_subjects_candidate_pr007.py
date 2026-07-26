from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest

from app.services.alphaguard.candidate_pool_service import CandidatePoolService
from app.services.alphaguard.evaluation_subject_builder import EvaluationSubjectBuilder
from tests.unit.alphaguard._fakes import FakeDB
from tests.unit.alphaguard.pr007_helpers import make_label, make_subject
from tradingagents.alphaguard.candidate_schemas import (
    CandidateEntry,
    CandidateSource,
    CandidateStatus,
)


async def _identity_fixture(db):
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
    await db["ag_decision_contexts"].insert_one(
        {
            "decision_context_id": "context-1",
            "analysis_id": "analysis-1",
            "user_id": "user-1",
            "candidate_id": "candidate-1",
            "symbol": "600519",
            "market": "CN",
            "trade_date": date(2026, 7, 1),
            "snapshot_id": "snapshot-1",
            "quant_proposal_id": "proposal-triggered",
            "created_at": datetime(2026, 7, 1, 15, 1),
        }
    )


@pytest.mark.asyncio
async def test_subject_discovery_covers_all_quant_normal_and_top_statuses():
    db = FakeDB()
    await _identity_fixture(db)
    quant_statuses = [
        ("TRIGGERED", "BUY"),
        ("WATCH", "WAIT"),
        ("REJECTED", "NONE"),
        ("INSUFFICIENT_DATA", "NONE"),
        ("INVALID_INPUT", "NONE"),
    ]
    for status, action in quant_statuses:
        await db["ag_quant_proposals"].insert_one(
            {
                "proposal_id": f"proposal-{status.lower()}",
                "snapshot_id": "snapshot-1",
                "user_id": "user-1",
                "candidate_id": "candidate-1",
                "symbol": "600519",
                "market": "CN",
                "trade_date": date(2026, 7, 1),
                "status": status,
                "action_candidate": action,
                "strategy_id": "strategy-v1",
                "strategy_version": "1.0.0",
                "initial_position_pct": 0.05,
                "max_position_pct": 0.10,
                "evidence_refs": [],
                "created_at": datetime(2026, 7, 1, 15, 1),
            }
        )
    normal_statuses = [
        ("PROPOSE_TRADE", "BUY"),
        ("NO_TRADE", "NONE"),
        ("WAIT", "WAIT"),
        ("INSUFFICIENT_DATA", "NONE"),
        ("MODEL_FAILED", "NONE"),
        ("INVALID_OUTPUT", "NONE"),
    ]
    plans = []
    for status, action in normal_statuses:
        plans.append(
            {
                "plan_id": f"plan-{status.lower()}",
                "snapshot_id": "snapshot-1",
                "quant_proposal_id": "proposal-triggered",
                "analysis_id": "analysis-1",
                "symbol": "600519",
                "market": "CN",
                "trade_date": date(2026, 7, 1),
                "status": status,
                "action": action,
                "initial_position_pct": 0.05 if status == "PROPOSE_TRADE" else None,
                "max_position_pct": 0.1 if status == "PROPOSE_TRADE" else None,
                "bullish_evidence": [],
                "bearish_evidence": [],
                "model_meta": {"model_version": "normal-v1"},
            }
        )
    top_statuses = [
        "CONFIRM",
        "RISK_ADJUST",
        "MATERIAL_REVISION",
        "REJECT",
        "SUSPEND",
        "MODEL_FAILED",
        "INVALID_OUTPUT",
    ]
    reviews = [
        {
            "review_id": f"review-{status.lower()}",
            "snapshot_id": "snapshot-1",
            "plan_id": "plan-propose_trade",
            "status": status,
            "adjusted_plan": (
                plans[0] if status in {"RISK_ADJUST", "MATERIAL_REVISION"} else None
            ),
            "model_meta": {"model_version": "top-v1"},
        }
        for status in top_statuses
    ]
    await db["analysis_reports"].insert_one(
        {
            "analysis_id": "analysis-1",
            "user_id": "user-1",
            "stock_symbol": "600519",
            "analysis_date": date(2026, 7, 1),
            "snapshot_id": "snapshot-1",
            "normal_trade_plan_history": plans,
            "top_review_history": reviews,
        }
    )
    subjects, created, reused = await EvaluationSubjectBuilder(db).discover(
        user_id="user-1"
    )
    assert created == len(subjects)
    assert reused == 0
    assert {
        item.decision_status
        for item in subjects
        if item.subject_type == "QUANT_PROPOSAL"
    } == {item[0] for item in quant_statuses}
    assert {
        item.decision_status
        for item in subjects
        if item.subject_type == "NORMAL_PLAN"
    } == {item[0] for item in normal_statuses}
    assert {
        item.decision_status
        for item in subjects
        if item.subject_type == "TOP_REVIEW"
    } == set(top_statuses)
    second, created, reused = await EvaluationSubjectBuilder(db).discover(
        user_id="user-1"
    )
    assert created == 0
    assert reused == len(second) == len(subjects)


@pytest.mark.asyncio
async def test_benchmark_hard_risk_and_execution_subjects_remain_separate():
    db = FakeDB()
    await _identity_fixture(db)
    await db["ag_quant_proposals"].insert_one(
        {
            "proposal_id": "proposal-triggered",
            "snapshot_id": "snapshot-1",
            "user_id": "user-1",
            "candidate_id": "candidate-1",
            "symbol": "600519",
            "market": "CN",
            "trade_date": date(2026, 7, 1),
            "status": "TRIGGERED",
            "action_candidate": "BUY",
            "strategy_id": "s",
            "strategy_version": "1",
            "initial_position_pct": 0.05,
            "max_position_pct": 0.1,
            "evidence_refs": [],
        }
    )
    await db["ag_paper_accounts"].insert_one(
        {
            "account_id": "account-1",
            "user_id": "user-1",
            "account_type": "PAPER_QUANT",
        }
    )
    await db["ag_benchmark_execution_decisions"].insert_one(
        {
            "benchmark_decision_id": "benchmark-1",
            "source_type": "QUANT",
            "source_object_id": "proposal-triggered",
            "account_id": "account-1",
            "status": "PASS",
            "action": "BUY",
            "approved_position_pct": 0.05,
        }
    )
    await db["ag_risk_decisions"].insert_one(
        {
            "risk_decision_id": "risk-1",
            "analysis_id": "analysis-1",
            "consensus_id": "consensus-1",
            "snapshot_id": "snapshot-1",
            "quant_proposal_id": "proposal-triggered",
            "status": "REDUCE",
            "action": "BUY",
            "approved_position_pct": 0.03,
            "risk_policy_version": "risk-v1",
        }
    )
    await db["ag_order_intents"].insert_one(
        {
            "intent_id": "intent-1",
            "user_id": "user-1",
            "account_id": "account-1",
            "source_object_id": "proposal-triggered",
            "snapshot_id": "snapshot-1",
            "quant_proposal_id": "proposal-triggered",
            "symbol": "600519",
            "market": "CN",
            "original_action": "BUY",
            "limit_price": Decimal("10"),
            "execution_policy_version": "paper-execution-v1",
            "earliest_execute_at": datetime(2026, 7, 2, 9, 30),
        }
    )
    await db["ag_paper_orders"].insert_one(
        {
            "order_id": "order-1",
            "intent_id": "intent-1",
            "user_id": "user-1",
            "account_id": "account-1",
            "source_object_id": "proposal-triggered",
            "symbol": "600519",
            "market": "CN",
            "original_action": "BUY",
            "status": "FILLED",
            "trade_date": date(2026, 7, 2),
            "matching_engine_version": "matching-engine-v1",
        }
    )
    await db["ag_paper_fills"].insert_one(
        {
            "fill_id": "fill-1",
            "order_id": "order-1",
            "intent_id": "intent-1",
            "account_id": "account-1",
            "symbol": "600519",
            "market": "CN",
            "side": "BUY",
            "trade_date": date(2026, 7, 2),
            "price": Decimal("10"),
            "quantity": 100,
            "matching_engine_version": "matching-engine-v1",
        }
    )
    subjects, _, _ = await EvaluationSubjectBuilder(db).discover(user_id="user-1")
    stages = {(item.subject_type, item.decision_stage) for item in subjects}
    assert ("BENCHMARK_DECISION", "BENCHMARK_SAFETY") in stages
    assert ("RISK_DECISION", "HARD_RISK") in stages
    assert ("ORDER_INTENT", "EXECUTION") in stages
    assert ("PAPER_ORDER", "EXECUTION") in stages
    assert ("PAPER_FILL", "EXECUTION") in stages
    quant = next(item for item in subjects if item.subject_type == "QUANT_PROPOSAL")
    assert quant.actual_execution_exists is True


@pytest.mark.asyncio
async def test_pending_evaluation_blocks_candidate_removal_state():
    db = FakeDB()
    candidate = CandidateEntry(
        candidate_id="candidate-1",
        user_id="user-1",
        symbol="600519",
        market="CN",
        sources={CandidateSource.USER_SELECTED},
        status=CandidateStatus.WATCHING,
        priority=50,
        added_at=datetime(2026, 7, 1),
        updated_at=datetime(2026, 7, 1),
    )
    subject = make_subject()
    await db["ag_eval_subjects"].insert_one(subject.model_dump(mode="python"))
    pending = make_label(subject.subject_id, "10D", status="PENDING")
    await db["ag_eval_horizon_labels"].insert_one(
        pending.model_dump(mode="python")
    )
    reasons, _, _ = await CandidatePoolService(db=db)._live_monitoring_reasons(
        candidate,
        set(),
    )
    assert "pending_evaluation" in reasons


@pytest.mark.asyncio
async def test_pending_and_dead_letter_outbox_rows_become_execution_subjects():
    db = FakeDB()
    await _identity_fixture(db)
    await db["ag_quant_proposals"].insert_one(
        {
            "proposal_id": "proposal-triggered",
            "snapshot_id": "snapshot-1",
            "user_id": "user-1",
            "candidate_id": "candidate-1",
            "symbol": "600519",
            "market": "CN",
            "trade_date": date(2026, 7, 1),
            "status": "TRIGGERED",
            "action_candidate": "BUY",
            "strategy_id": "s",
            "strategy_version": "1",
            "initial_position_pct": 0.05,
            "max_position_pct": 0.1,
            "evidence_refs": [],
        }
    )
    for status in ("PENDING", "DEAD_LETTER"):
        await db["ag_execution_outbox"].insert_one(
            {
                "outbox_event_id": f"outbox-{status.lower()}",
                "event_type": "CREATE_QUANT_BENCHMARK_INTENT",
                "source_object_id": "proposal-triggered",
                "user_id": "user-1",
                "account_id": "account-1",
                "candidate_id": "candidate-1",
                "status": status,
                "created_at": datetime(2026, 7, 1, 15, 2),
            }
        )
    subjects, _, _ = await EvaluationSubjectBuilder(db).discover(user_id="user-1")
    statuses = {
        item.decision_status
        for item in subjects
        if item.subject_type == "EXECUTION_OUTBOX"
    }
    assert statuses == {"OUTBOX_PENDING", "OUTBOX_DEAD_LETTER"}
    assert all(
        item.decision_stage == "EXECUTION"
        for item in subjects
        if item.subject_type == "EXECUTION_OUTBOX"
    )
