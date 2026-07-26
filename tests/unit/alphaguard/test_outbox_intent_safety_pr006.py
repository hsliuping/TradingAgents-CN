from datetime import date, datetime
from decimal import Decimal

import pytest

from app.schemas.alphaguard.decision import (
    ConsensusDecision,
    RiskDecision,
    canonical_hash,
)
from app.services.alphaguard.benchmark_execution_safety_gate import (
    BenchmarkExecutionSafetyGate,
)
from app.services.alphaguard.evidence_snapshot_service import (
    calculate_immutable_hash,
)
from app.services.alphaguard.execution_outbox_service import (
    ExecutionOutboxService,
)
from app.services.alphaguard.order_intent_factory import (
    OrderIntentConflictError,
    OrderIntentFactory,
    OrderIntentRejected,
    OrderIntentSuspended,
)
from app.services.alphaguard.risk_policy_registry import RiskPolicyRegistry
from tests.unit.alphaguard._fakes import FakeDB
from tests.unit.alphaguard.pr005_helpers import make_context, make_plan
from tests.unit.alphaguard.pr006_helpers import setup_paper
from tradingagents.alphaguard.evidence_schemas import (
    DataQualityReport,
    EvidenceSnapshot,
)


async def snapshot_for_context(db, context, *, include_status=True):
    raw_refs = {"prices": [], "stock_basic_info": []}
    await db["stock_daily_quotes"].insert_one(
        {
            "ref_id": "p1",
            "symbol": context.symbol,
            "market": context.market,
            "trade_date": context.trade_date.isoformat(),
            "open": 100,
            "high": 102,
            "low": 98,
            "close": 100,
            "volume": 1_000_000,
            "amount": 100_000_000,
        }
    )
    raw_refs["prices"].append("stock_daily_quotes:p1")
    instrument = {
        "ref_id": "i1",
        "code": context.symbol,
        "market": context.market,
        "updated_at": datetime(2026, 7, 1, 14),
    }
    if include_status:
        instrument.update(suspended=False, isST=False)
    await db["stock_basic_info"].insert_one(instrument)
    raw_refs["stock_basic_info"].append("stock_basic_info:i1")
    quality = DataQualityReport(
        quality_report_id="q1",
        symbol=context.symbol,
        market=context.market,
        trade_date=context.trade_date,
        status="PASS",
        completeness_score=1,
        freshness_score=1,
        consistency_score=1,
        checked_at=datetime(2026, 7, 1, 15),
    )
    draft = EvidenceSnapshot(
        snapshot_id=context.snapshot_id,
        user_id=context.user_id,
        analysis_id=context.analysis_id,
        symbol=context.symbol,
        market=context.market,
        trade_date=context.trade_date,
        price_cutoff_at=datetime(2026, 7, 1, 15),
        news_cutoff_at=datetime(2026, 7, 1, 15),
        announcement_cutoff_at=datetime(2026, 7, 1, 15),
        price_data_version="fixed",
        financial_data_version="fixed",
        news_data_version="fixed",
        data_quality=quality,
        raw_refs=raw_refs,
        factor_version_set={"FIXED": "1.0.0"},
        strategy_version="strategy-set-v1",
        immutable_hash="0" * 64,
        created_at=datetime(2026, 7, 1, 15),
    )
    snapshot = draft.model_copy(
        update={"immutable_hash": calculate_immutable_hash(draft)}
    )
    await db["ag_evidence_snapshots"].insert_one(
        snapshot.model_dump(mode="python")
    )
    return snapshot


async def processing_event(
    db,
    *,
    event_type,
    source_object_id,
    user_id="user",
    account_id=None,
    analysis_id="analysis-1",
    candidate_id="candidate-1",
):
    service = ExecutionOutboxService(db)
    pending = await service.enqueue(
        event_type=event_type,
        source_object_id=source_object_id,
        user_id=user_id,
        account_id=account_id,
        analysis_id=analysis_id,
        candidate_id=candidate_id,
        now=datetime(2026, 7, 1, 16),
    )
    return await service.mark_processing(pending, now=datetime(2026, 7, 1, 16))


@pytest.mark.asyncio
async def test_outbox_is_db_backed_and_idempotent():
    db = FakeDB()
    service = ExecutionOutboxService(db)
    first = await service.enqueue(
        event_type="CREATE_QUANT_BENCHMARK_INTENT",
        source_object_id="proposal",
        user_id="user",
    )
    second = await service.enqueue(
        event_type="CREATE_QUANT_BENCHMARK_INTENT",
        source_object_id="proposal",
        user_id="user",
    )
    assert first.outbox_event_id == second.outbox_event_id
    assert db["ag_execution_outbox"].count() == 1


@pytest.mark.asyncio
async def test_outbox_failure_preserves_history_and_dead_letters():
    db = FakeDB()
    service = ExecutionOutboxService(db)
    event = await service.enqueue(
        event_type="CREATE_QUANT_BENCHMARK_INTENT",
        source_object_id="proposal",
        user_id="user",
    )
    for attempt in range(event.max_attempts):
        current = await service.mark_processing(event)
        await service.fail(current, ValueError(f"failure-{attempt}"))
        stored = (await db["ag_execution_outbox"].find({}).to_list(None))[0]
        event = type(event).model_validate(
            {key: value for key, value in stored.items() if key != "_id"}
        )
        if event.status != "DEAD_LETTER":
            event = event.model_copy(update={"next_attempt_at": datetime.utcnow()})
            await db["ag_execution_outbox"].update_one(
                {"outbox_event_id": event.outbox_event_id},
                {"$set": {"next_attempt_at": event.next_attempt_at}},
            )
    assert event.status == "DEAD_LETTER"
    assert len(event.error_history) == event.max_attempts


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["PASS", "REDUCE"])
async def test_top_confirmed_intent_only_from_eligible_risk(status):
    db = FakeDB()
    accounts = await setup_paper(db)
    context = make_context()
    plan = make_plan(context)
    await snapshot_for_context(db, context)
    await db["ag_decision_contexts"].insert_one(context.model_dump(mode="python"))
    consensus = ConsensusDecision(
        consensus_id="consensus",
        analysis_id=context.analysis_id,
        snapshot_id=context.snapshot_id,
        quant_proposal_id=context.quant_proposal_id,
        plan_id=plan.plan_id,
        review_id="review",
        status="CONSENSUS_PASS",
        final_plan=plan,
        final_plan_hash=canonical_hash(plan),
        revision_round=0,
        requires_normal_reconfirm=False,
        reasons=["confirmed"],
        validation_errors=[],
        created_at=datetime(2026, 7, 1, 16),
    )
    await db["ag_consensus_decisions"].insert_one(
        consensus.model_dump(mode="python")
    )
    account = accounts["PAPER_TOP_CONFIRMED"]
    risk = RiskDecision(
        risk_decision_id="risk",
        analysis_id=context.analysis_id,
        consensus_id=consensus.consensus_id,
        snapshot_id=context.snapshot_id,
        quant_proposal_id=context.quant_proposal_id,
        account_id=account.account_id,
        status=status,
        action="BUY",
        original_position_pct=0.10,
        approved_position_pct=0.05 if status == "REDUCE" else 0.10,
        original_quantity=1000,
        approved_quantity=500 if status == "REDUCE" else 1000,
        pricing_reference=100,
        earliest_eligible_execute_at=datetime(2026, 7, 2, 9, 30),
        requires_execution_recheck=True,
        triggered_rules=[],
        reasons=["fixed"],
        risk_policy_version="1.0.0",
        input_hash="1" * 64,
        created_at=datetime(2026, 7, 1, 16),
        order_intent_created=False,
    )
    await db["ag_risk_decisions"].insert_one(risk.model_dump(mode="python"))
    event = await processing_event(
        db,
        event_type="CREATE_TOP_CONFIRMED_INTENT",
        source_object_id=risk.risk_decision_id,
        account_id=account.account_id,
    )
    intent = await OrderIntentFactory(db).create_from_outbox(event)
    assert intent.account_type == "PAPER_TOP_CONFIRMED"
    assert intent.quantity == risk.approved_quantity
    assert intent.consensus_approved is True
    assert intent.hard_risk_approved is True
    assert intent.execution_environment == "PAPER"
    assert intent.live_execution_allowed is False


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["REJECT", "SUSPEND"])
async def test_reject_or_suspend_risk_cannot_create_intent(status):
    db = FakeDB()
    account = (await setup_paper(db))["PAPER_TOP_CONFIRMED"]
    risk = RiskDecision(
        risk_decision_id="risk",
        analysis_id="analysis-1",
        consensus_id="consensus",
        snapshot_id="snapshot-1",
        quant_proposal_id="proposal-1",
        account_id=account.account_id,
        status=status,
        action="BUY",
        original_position_pct=0.1,
        approved_position_pct=None,
        original_quantity=1000,
        approved_quantity=None,
        pricing_reference=None,
        earliest_eligible_execute_at=None,
        requires_execution_recheck=True,
        triggered_rules=[],
        reasons=["blocked"],
        risk_policy_version="1.0.0",
        input_hash="1" * 64,
        created_at=datetime(2026, 7, 1),
        order_intent_created=False,
    )
    await db["ag_risk_decisions"].insert_one(risk.model_dump(mode="python"))
    event = await processing_event(
        db,
        event_type="CREATE_TOP_CONFIRMED_INTENT",
        source_object_id="risk",
        account_id=account.account_id,
    )
    with pytest.raises(OrderIntentRejected):
        await OrderIntentFactory(db).create_from_outbox(event)
    assert db["ag_order_intents"].count() == 0


@pytest.mark.asyncio
async def test_quant_triggered_creates_benchmark_intent_but_watch_does_not():
    db = FakeDB()
    await setup_paper(db)
    await RiskPolicyRegistry(db).register_builtin()
    context = make_context()
    await snapshot_for_context(db, context)
    proposal = context.quant_proposal
    await db["ag_quant_proposals"].insert_one(proposal.model_dump(mode="python"))
    event = await processing_event(
        db,
        event_type="CREATE_QUANT_BENCHMARK_INTENT",
        source_object_id=proposal.proposal_id,
    )
    intent = await OrderIntentFactory(db).create_from_outbox(event)
    assert intent.account_type == "PAPER_QUANT"
    assert intent.benchmark_only is True
    assert intent.consensus_approved is False
    assert intent.hard_risk_approved is False

    changed = proposal.model_copy(
        update={
            "entry_zone": proposal.entry_zone.model_copy(update={"upper": 102})
        }
    )
    await db["ag_quant_proposals"].replace_one(
        {"proposal_id": proposal.proposal_id},
        changed.model_dump(mode="python"),
    )
    with pytest.raises(OrderIntentConflictError):
        await OrderIntentFactory(db).create_from_outbox(event)

    watch = proposal.model_copy(
        update={
            "proposal_id": "watch",
            "status": "WATCH",
            "action_candidate": "WAIT",
            "entry_zone": None,
        }
    )
    await db["ag_quant_proposals"].insert_one(watch.model_dump(mode="python"))
    watch_event = await processing_event(
        db,
        event_type="CREATE_QUANT_BENCHMARK_INTENT",
        source_object_id="watch",
    )
    with pytest.raises(OrderIntentRejected):
        await OrderIntentFactory(db).create_from_outbox(watch_event)


@pytest.mark.asyncio
async def test_normal_round_zero_creates_benchmark_but_wait_does_not():
    db = FakeDB()
    await setup_paper(db)
    await RiskPolicyRegistry(db).register_builtin()
    context = make_context()
    await snapshot_for_context(db, context)
    plan = make_plan(context)
    await db["analysis_reports"].insert_one(
        {
            "analysis_id": context.analysis_id,
            "user_id": context.user_id,
            "normal_trade_plan": plan.model_dump(mode="python"),
            "normal_trade_plan_history": [plan.model_dump(mode="python")],
        }
    )
    event = await processing_event(
        db,
        event_type="CREATE_NORMAL_BENCHMARK_INTENT",
        source_object_id=plan.plan_id,
    )
    intent = await OrderIntentFactory(db).create_from_outbox(event)
    assert intent.account_type == "PAPER_NORMAL"
    assert intent.source_type == "NORMAL_PLAN"

    wait = make_plan(context, status="WAIT")
    await db["analysis_reports"].update_one(
        {"analysis_id": context.analysis_id},
        {"$push": {"normal_trade_plan_history": wait.model_dump(mode="python")}},
    )
    wait_event = await processing_event(
        db,
        event_type="CREATE_NORMAL_BENCHMARK_INTENT",
        source_object_id=wait.plan_id,
    )
    with pytest.raises(OrderIntentRejected):
        await OrderIntentFactory(db).create_from_outbox(wait_event)


@pytest.mark.asyncio
async def test_benchmark_missing_trading_status_suspends_instead_of_guessing():
    db = FakeDB()
    await setup_paper(db)
    await RiskPolicyRegistry(db).register_builtin()
    context = make_context()
    await snapshot_for_context(db, context, include_status=False)
    await db["ag_quant_proposals"].insert_one(
        context.quant_proposal.model_dump(mode="python")
    )
    event = await processing_event(
        db,
        event_type="CREATE_QUANT_BENCHMARK_INTENT",
        source_object_id=context.quant_proposal_id,
    )
    with pytest.raises(OrderIntentSuspended):
        await OrderIntentFactory(db).create_from_outbox(event)


@pytest.mark.asyncio
async def test_benchmark_parses_existing_string_status_fields_without_truthiness():
    db = FakeDB()
    await setup_paper(db)
    await RiskPolicyRegistry(db).register_builtin()
    context = make_context()
    await snapshot_for_context(db, context)
    await db["stock_basic_info"].update_one(
        {"ref_id": "i1"},
        {"$set": {"suspended": "0", "isST": "0"}},
    )
    await db["ag_quant_proposals"].insert_one(
        context.quant_proposal.model_dump(mode="python")
    )
    event = await processing_event(
        db,
        event_type="CREATE_QUANT_BENCHMARK_INTENT",
        source_object_id=context.quant_proposal_id,
    )
    intent = await OrderIntentFactory(db).create_from_outbox(event)
    assert intent.account_type == "PAPER_QUANT"


@pytest.mark.asyncio
async def test_benchmark_gate_never_claims_consensus_or_hard_risk():
    db = FakeDB()
    account = (await setup_paper(db))["PAPER_QUANT"]
    decision = BenchmarkExecutionSafetyGate().evaluate(
        source_type="QUANT",
        source_object_id="proposal",
        account=account,
        action="BUY",
        requested_position_pct=0.01,
        requested_quantity=100,
        price=Decimal("10"),
        current_quantity=0,
        available_quantity=0,
        current_position_value=Decimal("0"),
        total_exposure_value=Decimal("0"),
        duplicate_active_order=False,
        execution_date_available=True,
        trading_status_known=True,
        trading_blocked=False,
        max_single_position_pct=0.10,
        max_total_exposure_pct=0.60,
        cn_buy_lot_size=100,
        now=datetime(2026, 7, 1, 16),
    )
    assert decision.benchmark_only is True
    assert decision.consensus_approved is False
    assert decision.hard_risk_approved is False


def test_challenger_has_no_outbox_event_type():
    allowed = set(
        ExecutionOutboxService.__dict__
    )
    # There is no public or internal CREATE_CHALLENGER event in PR-006.
    from tradingagents.alphaguard.paper_schemas import ExecutionOutboxEvent

    with pytest.raises(Exception):
        ExecutionOutboxEvent(
            outbox_event_id="x",
            event_type="CREATE_CHALLENGER_INTENT",
            source_object_id="x",
            user_id="u",
            idempotency_key="x",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
