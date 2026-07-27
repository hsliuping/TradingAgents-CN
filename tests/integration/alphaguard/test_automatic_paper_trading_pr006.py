from datetime import date, datetime
from decimal import Decimal

import pytest

from app.schemas.alphaguard.decision import (
    ConsensusDecision,
    RiskDecision,
    canonical_hash,
)
from app.services.alphaguard.execution_outbox_service import ExecutionOutboxService
from app.services.alphaguard.paper_account_service import PaperAccountService
from app.services.alphaguard.paper_storage import clean_document
from app.services.alphaguard.paper_storage import mongo_date
from app.services.alphaguard.paper_task_service import PaperTaskService
from app.services.alphaguard.risk_policy_registry import RiskPolicyRegistry
from tests.unit.alphaguard._fakes import FakeDB
from tests.unit.alphaguard.pr005_helpers import make_context, make_plan
from tests.unit.alphaguard.pr006_helpers import daily_record, setup_paper
from tests.unit.alphaguard.test_outbox_intent_safety_pr006 import (
    snapshot_for_context,
)
from tradingagents.alphaguard.candidate_schemas import CandidateEntry


async def prepare_top_confirmed_source(db):
    accounts = await setup_paper(db)
    await RiskPolicyRegistry(db).register_builtin()
    context = make_context()
    plan = make_plan(context)
    await snapshot_for_context(db, context)
    await db["ag_decision_contexts"].insert_one(context.model_dump(mode="python"))
    consensus = ConsensusDecision(
        consensus_id="consensus-e2e",
        analysis_id=context.analysis_id,
        snapshot_id=context.snapshot_id,
        quant_proposal_id=context.quant_proposal_id,
        plan_id=plan.plan_id,
        review_id="review-e2e",
        status="CONSENSUS_PASS",
        final_plan=plan,
        final_plan_hash=canonical_hash(plan),
        revision_round=0,
        requires_normal_reconfirm=False,
        reasons=["fixed integration approval"],
        validation_errors=[],
        created_at=datetime(2026, 7, 1, 16),
    )
    await db["ag_consensus_decisions"].insert_one(
        consensus.model_dump(mode="python")
    )
    account = accounts["PAPER_TOP_CONFIRMED"]
    risk = RiskDecision(
        risk_decision_id="risk-e2e",
        analysis_id=context.analysis_id,
        consensus_id=consensus.consensus_id,
        snapshot_id=context.snapshot_id,
        quant_proposal_id=context.quant_proposal_id,
        account_id=account.account_id,
        status="PASS",
        action="BUY",
        original_position_pct=0.01,
        approved_position_pct=0.01,
        original_quantity=1000,
        approved_quantity=1000,
        pricing_reference=100,
        earliest_eligible_execute_at=datetime(2026, 7, 2, 9, 30),
        requires_execution_recheck=True,
        triggered_rules=[],
        reasons=["fixed integration approval"],
        risk_policy_version="1.0.0",
        input_hash="1" * 64,
        created_at=datetime(2026, 7, 1, 16),
        order_intent_created=False,
    )
    await db["ag_risk_decisions"].insert_one(risk.model_dump(mode="python"))
    candidate = CandidateEntry(
        candidate_id=context.candidate_id,
        user_id=context.user_id,
        symbol=context.symbol,
        market=context.market,
        sources={"SYSTEM_SCREENED"},
        status="APPROVED",
        added_at=datetime(2026, 7, 1, 8),
        updated_at=datetime(2026, 7, 1, 16),
        active_plan_id=plan.plan_id,
    )
    await db["ag_candidates"].insert_one(candidate.model_dump(mode="python"))
    await ExecutionOutboxService(db).enqueue(
        event_type="CREATE_TOP_CONFIRMED_INTENT",
        source_object_id=risk.risk_decision_id,
        user_id=context.user_id,
        account_id=account.account_id,
        analysis_id=context.analysis_id,
        candidate_id=context.candidate_id,
        now=datetime(2026, 7, 1, 16),
    )
    return account, context


@pytest.mark.asyncio
async def test_risk_to_outbox_order_fill_saga_lot_snapshot_and_candidate():
    db = FakeDB()
    account, context = await prepare_top_confirmed_source(db)
    tasks = PaperTaskService(db)

    outbox_result = await tasks.process_execution_outbox()
    assert outbox_result == {"completed": 1, "failed": 0, "dead_letter": 0}
    assert db["ag_order_intents"].count() == 1
    assert db["ag_paper_orders"].count() == 1
    order_document = clean_document(
        (await db["ag_paper_orders"].find({}).to_list(None))[0]
    )
    assert order_document["status"] == "PENDING"
    candidate = clean_document(
        await db["ag_candidates"].find_one({"candidate_id": context.candidate_id})
    )
    assert str(candidate["status"]) == "ORDER_PENDING"

    execution_record = daily_record(
        trade_date=date(2026, 7, 2),
        open_price="100",
        high="102",
        low="99",
        close="101",
        limit_up="110",
        limit_down="90",
    )
    await db["stock_daily_quotes"].insert_one(execution_record)
    built = await tasks.build_execution_market_snapshots(date(2026, 7, 2))
    assert built == {"created_or_reused": 1, "failed": 0}
    matched = await tasks.match_orders_for_trade_date(date(2026, 7, 2))
    assert matched == {"fills": 1, "no_fill": 0}

    pending_order = clean_document(
        (await db["ag_paper_orders"].find({}).to_list(None))[0]
    )
    assert pending_order["status"] == "SETTLEMENT_PENDING"
    assert db["ag_paper_fills"].count() == 1
    settled = await tasks.settle_pending_fills()
    assert settled == {"committed": 1, "failed": 0}

    order = clean_document((await db["ag_paper_orders"].find({}).to_list(None))[0])
    assert order["status"] == "FILLED"
    assert db["ag_settlement_records"].count() == 1
    assert db["ag_paper_position_lots"].count() == 1
    assert db["ag_paper_ledger_entries"].count() == 3
    position = clean_document(
        await db["ag_paper_positions"].find_one(
            {"account_id": account.account_id, "symbol": context.symbol}
        )
    )
    assert position["quantity"] == 1000
    assert position["available_quantity"] == 0
    candidate = clean_document(
        await db["ag_candidates"].find_one({"candidate_id": context.candidate_id})
    )
    assert str(candidate["status"]) == "POSITION_HELD"

    snapshot_count = await tasks.create_daily_account_snapshots(date(2026, 7, 2))
    assert snapshot_count == 4
    account_snapshot = clean_document(
        await db["ag_paper_account_snapshots"].find_one(
            {
                "account_id": account.account_id,
                "trade_date": mongo_date(date(2026, 7, 2)),
            }
        )
    )
    assert account_snapshot["valuation_complete"] is True
    assert Decimal(str(account_snapshot["total_equity"])) > 0

    before = await PaperAccountService(db).get_account(account.account_id)
    before_ledger = db["ag_paper_ledger_entries"].count()
    before_lots = db["ag_paper_position_lots"].count()
    assert await tasks.process_execution_outbox() == {
        "completed": 0,
        "failed": 0,
        "dead_letter": 0,
    }
    assert await tasks.match_orders_for_trade_date(date(2026, 7, 2)) == {
        "fills": 0,
        "no_fill": 0,
    }
    assert await tasks.settle_pending_fills() == {"committed": 0, "failed": 0}
    await tasks.create_daily_account_snapshots(date(2026, 7, 2))
    after = await PaperAccountService(db).get_account(account.account_id)
    assert after == before
    assert db["ag_paper_ledger_entries"].count() == before_ledger
    assert db["ag_paper_position_lots"].count() == before_lots

    for legacy_collection in (
        "paper_accounts",
        "paper_positions",
        "paper_orders",
        "paper_trades",
    ):
        assert db[legacy_collection].count() == 0


@pytest.mark.asyncio
async def test_benchmark_orders_never_change_main_candidate_state():
    db = FakeDB()
    accounts = await setup_paper(db)
    candidate = CandidateEntry(
        candidate_id="candidate-benchmark",
        user_id="user",
        symbol="600519",
        market="CN",
        sources={"SYSTEM_SCREENED"},
        status="APPROVED",
        added_at=datetime(2026, 7, 1, 8),
        updated_at=datetime(2026, 7, 1, 16),
    )
    await db["ag_candidates"].insert_one(candidate.model_dump(mode="python"))
    from tests.unit.alphaguard.pr006_helpers import make_intent

    intent = await make_intent(
        db,
        accounts["PAPER_QUANT"],
        source_type="QUANT_PROPOSAL",
        candidate_id=candidate.candidate_id,
    )
    order = await PaperTaskService(db).orders.create_reserve_submit(intent)
    await PaperTaskService(db).candidate_sync.sync_order(order)
    stored = clean_document(
        await db["ag_candidates"].find_one({"candidate_id": candidate.candidate_id})
    )
    assert getattr(stored["status"], "value", stored["status"]) == "APPROVED"
