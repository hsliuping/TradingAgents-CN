from __future__ import annotations

from copy import deepcopy
from datetime import datetime

import pytest

from app.schemas.alphaguard.quant import QuantTradeProposal
from app.services.alphaguard.candidate_pool_service import CandidatePoolService
from app.services.alphaguard.decision_context_builder import (
    DecisionContextBuilder,
    DecisionContextError,
)
from app.services.alphaguard.decision_pipeline import (
    DecisionIntegrityError,
    DecisionPipeline,
)
from app.services.alphaguard.evidence_snapshot_service import (
    calculate_immutable_hash,
)
from app.services.alphaguard.factor_registry import FactorRegistry
from app.services.alphaguard.quant_research_pipeline import QuantResearchPipeline
from app.services.alphaguard.risk_policy_registry import RiskPolicyRegistry
from app.services.alphaguard.strategy_registry import StrategyRegistry
from tests.unit.alphaguard._fakes import FakeDB
from tests.unit.alphaguard.pr005_helpers import make_plan, make_review
from tests.unit.alphaguard.test_quant_pipeline_pr004 import build_pipeline_snapshot
from tradingagents.alphaguard.candidate_schemas import (
    CandidateSource,
    CandidateStatus,
)
from tradingagents.alphaguard.decision_schemas import NormalTradePlan
from tradingagents.alphaguard.evidence_schemas import EvidenceSnapshot


def fixed_clock():
    return datetime(2026, 7, 1, 16)


class FixedModelRunner:
    def __init__(
        self,
        *,
        normal_statuses: list[str] | None = None,
        top_statuses: list[str] | None = None,
    ):
        self.normal_statuses = list(normal_statuses or ["PROPOSE_TRADE"])
        self.top_statuses = list(top_statuses or ["CONFIRM"])
        self.normal_calls = 0
        self.top_calls = 0
        self.first_plan: NormalTradePlan | None = None

    async def run_normal(
        self,
        *,
        context,
        attempt_number,
        trace_id,
        revision_request=None,
        original_plan=None,
    ):
        status = self.normal_statuses[min(self.normal_calls, len(self.normal_statuses) - 1)]
        self.normal_calls += 1
        if revision_request:
            plan = make_plan(
                context,
                status=status,
                revision_round=1,
                original_plan=original_plan,
                revision_request_id=revision_request.revision_request_id,
            )
        else:
            plan = make_plan(context, status=status)
            self.first_plan = plan
        return plan

    async def run_top(
        self,
        *,
        context,
        plan,
        risk_policy_summary,
        attempt_number,
        trace_id,
    ):
        status = self.top_statuses[min(self.top_calls, len(self.top_statuses) - 1)]
        self.top_calls += 1
        return make_review(
            context,
            plan,
            status=status,
            adjusted_plan=plan if status == "MATERIAL_REVISION" else None,
        )


async def _prepare_decision_input(
    db: FakeDB,
    *,
    total_exposure_pct: float = 0.20,
    include_instrument: bool = True,
):
    await FactorRegistry(db).seed_builtins()
    await StrategyRegistry(db).seed_builtins()
    snapshot = await build_pipeline_snapshot(db)
    candidate = await CandidatePoolService(db).upsert_source(
        user_id="user",
        symbol="600519",
        market="CN",
        source=CandidateSource.USER_SELECTED,
        reason="fixed PR-005 input",
    )

    account = {
        "account_id": "account-1",
        "user_id": "user",
        "status": "ACTIVE",
        "market": "CN",
        "currency": "CNY",
        "cash": {"CNY": 800_000},
        "equity": {"CNY": 1_000_000},
        "total_exposure_pct": total_exposure_pct,
        "industry_exposure_pct": {"白酒": 0.05},
        "new_positions_today": 0,
        "active_orders_complete": True,
        "portfolio_empty_verified": True,
        "updated_at": "2026-07-01T14:00:00",
    }
    instrument = {
        "ref_id": "instrument-1",
        "symbol": "600519",
        "market": "CN",
        "industry": "白酒",
        "suspended": False,
        "is_st": False,
        "at_limit_up": False,
        "at_limit_down": False,
        "average_amount_20d": 100_000_000,
        "updated_at": "2026-07-01T14:00:00",
    }
    await db["paper_accounts"].insert_one(account)
    if include_instrument:
        await db["stock_basic_info"].insert_one(instrument)

    raw_refs = deepcopy(snapshot.raw_refs)
    raw_refs["paper_accounts"] = ["paper_accounts:account-1"]
    if include_instrument:
        raw_refs["stock_basic_info"] = ["stock_basic_info:instrument-1"]
    draft = snapshot.model_copy(
        update={"raw_refs": raw_refs, "immutable_hash": "0" * 64}
    )
    snapshot = draft.model_copy(
        update={"immutable_hash": calculate_immutable_hash(draft)}
    )
    await db["ag_evidence_snapshots"].replace_one(
        {"snapshot_id": snapshot.snapshot_id},
        snapshot.model_dump(mode="python"),
    )

    proposals = await QuantResearchPipeline(db).evaluate(
        snapshot.snapshot_id,
        user_id="user",
        candidate_id=candidate.candidate_id,
        trace_id="trace-pr005",
    )
    proposal = next(item for item in proposals if item.status == "TRIGGERED")
    await RiskPolicyRegistry(db).register_builtin()
    return snapshot, candidate, proposal


@pytest.mark.asyncio
async def test_context_builder_is_snapshot_only_deterministic_and_create_only():
    db = FakeDB()
    snapshot, _, proposal = await _prepare_decision_input(db)
    builder = DecisionContextBuilder(db)
    first, first_data = await builder.build(proposal.proposal_id, user_id="user")
    second, second_data = await builder.build(proposal.proposal_id, user_id="user")
    assert first.context_hash == second.context_hash
    assert first.decision_context_id == second.decision_context_id
    assert db["ag_decision_contexts"].count() == 1
    direct_refs = {
        item.evidence_id
        for group in (
            first.price_evidence,
            first.financial_evidence,
            first.news_evidence,
            first.announcement_evidence,
            first.account_evidence,
            first.portfolio_evidence,
        )
        for item in group
    }
    assert direct_refs.issubset(set(first_data.input_refs))
    proposal_refs = {
        item.evidence_id for item in first.quant_proposal.evidence_refs
    }
    assert proposal_refs.issubset(
        set(first.factor_result_ids) | set(first_data.input_refs)
    )
    assert first_data.input_hash == second_data.input_hash

    await db["stock_daily_quotes"].insert_one(
        {
            "ref_id": "future",
            "symbol": "600519",
            "market": "CN",
            "trade_date": "2026-07-02",
            "close": 9999,
        }
    )
    third, _ = await builder.build(proposal.proposal_id, user_id="user")
    assert third.context_hash == first.context_hash
    assert "stock_daily_quotes:future" not in third.evidence_ids()

    stored = await db["ag_evidence_snapshots"].find_one(
        {"snapshot_id": snapshot.snapshot_id}
    )
    stored["raw_refs"]["prices"].append("stock_daily_quotes:future")
    await db["ag_evidence_snapshots"].replace_one(
        {"snapshot_id": snapshot.snapshot_id}, stored
    )
    with pytest.raises(ValueError, match="immutable hash mismatch"):
        await DecisionContextBuilder(db).build(proposal.proposal_id, user_id="user")


@pytest.mark.asyncio
async def test_context_builder_blocks_missing_core_market_state_before_models():
    db = FakeDB()
    _, _, proposal = await _prepare_decision_input(
        db, include_instrument=False
    )
    runner = FixedModelRunner()
    with pytest.raises(
        DecisionContextError, match="instrument_trading_state"
    ):
        await DecisionPipeline(
            db, model_runner=runner, clock=fixed_clock
        ).evaluate_quant_proposal(
            proposal.proposal_id, user_id="user", account_id="account-1"
        )
    assert runner.normal_calls == runner.top_calls == 0
    assert db["ag_decision_contexts"].count() == 0
    assert any(
        item["event_type"] == "DECISION_CONTEXT_INVALID"
        for item in db["ag_decision_events"].documents
    )


@pytest.mark.asyncio
async def test_full_pipeline_approves_without_orders_or_account_mutation_and_reuses():
    db = FakeDB()
    _, candidate, proposal = await _prepare_decision_input(db)
    account_before = deepcopy(db["paper_accounts"].documents)
    runner = FixedModelRunner()
    pipeline = DecisionPipeline(db, model_runner=runner, clock=fixed_clock)
    first = await pipeline.evaluate_quant_proposal(
        proposal.proposal_id,
        user_id="user",
        account_id="account-1",
        trace_id="trace-pr005",
    )
    second = await pipeline.evaluate_quant_proposal(
        proposal.proposal_id,
        user_id="user",
        account_id="account-1",
        trace_id="trace-pr005",
    )
    assert first.terminal_status in {"RISK_PASS", "RISK_REDUCE"}
    assert first.consensus_decision.status == "CONSENSUS_PASS"
    assert first.risk_decision.status in {"PASS", "REDUCE"}
    assert first.risk_decision.order_intent_created is False
    assert second.reused is True
    assert runner.normal_calls == runner.top_calls == 1
    assert db["ag_consensus_decisions"].count() == 1
    assert db["ag_risk_decisions"].count() == 1
    assert db["paper_orders"].count() == 0
    assert db["paper_trades"].count() == 0
    assert db["paper_positions"].count() == 0
    assert db["paper_accounts"].documents == account_before
    updated = await CandidatePoolService(db).get_candidate(
        candidate.candidate_id, "user"
    )
    assert updated.status == CandidateStatus.APPROVED
    statuses = {
        document["event_type"] for document in db["ag_decision_events"].documents
    }
    assert {
        "DECISION_CONTEXT_CREATED",
        "NORMAL_MODEL_COMPLETED",
        "TOP_REVIEW_COMPLETED",
        "CONSENSUS_PASS",
        "HARD_RISK_PASS",
    }.issubset(statuses)


@pytest.mark.asyncio
async def test_consensus_pass_hard_risk_reduce_still_creates_no_order():
    db = FakeDB()
    _, _, proposal = await _prepare_decision_input(
        db, total_exposure_pct=0.58
    )
    result = await DecisionPipeline(
        db, model_runner=FixedModelRunner(), clock=fixed_clock
    ).evaluate_quant_proposal(
        proposal.proposal_id, user_id="user", account_id="account-1"
    )
    assert result.consensus_decision.status == "CONSENSUS_PASS"
    assert result.risk_decision.status == "REDUCE"
    assert result.risk_decision.approved_position_pct < (
        result.risk_decision.original_position_pct
    )
    assert result.risk_decision.action == "BUY"
    assert result.risk_decision.order_intent_created is False
    assert db["paper_orders"].count() == db["paper_trades"].count() == 0


@pytest.mark.asyncio
async def test_non_triggered_proposal_never_calls_models():
    db = FakeDB()
    await _prepare_decision_input(db)
    rejected = next(
        QuantTradeProposal.model_validate(
            {key: value for key, value in document.items() if key != "_id"}
        )
        for document in db["ag_quant_proposals"].documents
        if document["status"] == "REJECTED"
    )
    runner = FixedModelRunner()
    result = await DecisionPipeline(
        db, model_runner=runner, clock=fixed_clock
    ).evaluate_quant_proposal(
        rejected.proposal_id, user_id="user", account_id="account-1"
    )
    assert result.terminal_status == "PROPOSAL_NOT_ELIGIBLE"
    assert runner.normal_calls == runner.top_calls == 0
    assert db["ag_consensus_decisions"].count() == 0
    assert db["ag_risk_decisions"].count() == 0


@pytest.mark.asyncio
async def test_normal_failure_blocks_top_consensus_and_hard_risk():
    db = FakeDB()
    _, _, proposal = await _prepare_decision_input(db)
    runner = FixedModelRunner(normal_statuses=["MODEL_FAILED"])
    result = await DecisionPipeline(
        db, model_runner=runner, clock=fixed_clock
    ).evaluate_quant_proposal(
        proposal.proposal_id, user_id="user", account_id="account-1"
    )
    assert result.terminal_status == "NORMAL_MODEL_FAILED"
    assert runner.normal_calls == 1
    assert runner.top_calls == 0
    assert result.consensus_decision is None
    assert result.risk_decision is None
    assert db["ag_risk_decisions"].count() == 0


@pytest.mark.asyncio
async def test_top_reject_blocks_hard_risk():
    db = FakeDB()
    _, _, proposal = await _prepare_decision_input(db)
    runner = FixedModelRunner(top_statuses=["REJECT"])
    result = await DecisionPipeline(
        db, model_runner=runner, clock=fixed_clock
    ).evaluate_quant_proposal(
        proposal.proposal_id, user_id="user", account_id="account-1"
    )
    assert result.consensus_decision.status == "CONSENSUS_REJECT"
    assert result.risk_decision is None
    assert db["ag_risk_decisions"].count() == 0


@pytest.mark.asyncio
async def test_missing_registered_risk_policy_suspends_after_consensus():
    db = FakeDB()
    _, _, proposal = await _prepare_decision_input(db)
    await db["ag_risk_policies"].delete_many({})
    result = await DecisionPipeline(
        db, model_runner=FixedModelRunner(), clock=fixed_clock
    ).evaluate_quant_proposal(
        proposal.proposal_id, user_id="user", account_id="account-1"
    )
    assert result.consensus_decision.status == "CONSENSUS_PASS"
    assert result.risk_decision.status == "SUSPEND"
    assert result.risk_decision.risk_policy_version == "missing"
    assert result.risk_decision.order_intent_created is False
    assert db["paper_orders"].count() == 0


@pytest.mark.asyncio
async def test_material_revision_returns_once_then_passes():
    db = FakeDB()
    _, _, proposal = await _prepare_decision_input(db)
    runner = FixedModelRunner(
        normal_statuses=["PROPOSE_TRADE", "PROPOSE_TRADE"],
        top_statuses=["MATERIAL_REVISION", "CONFIRM"],
    )
    result = await DecisionPipeline(
        db, model_runner=runner, clock=fixed_clock
    ).evaluate_quant_proposal(
        proposal.proposal_id, user_id="user", account_id="account-1"
    )
    assert result.revision_request.revision_round == 1
    assert result.normal_trade_plan.revision_round == 1
    assert result.consensus_decision.status == "CONSENSUS_PASS"
    assert runner.normal_calls == runner.top_calls == 2
    assert db["ag_revision_requests"].count() == 1


@pytest.mark.asyncio
async def test_second_material_revision_rejects_without_third_normal_call():
    db = FakeDB()
    _, _, proposal = await _prepare_decision_input(db)
    runner = FixedModelRunner(
        normal_statuses=["PROPOSE_TRADE", "PROPOSE_TRADE"],
        top_statuses=["MATERIAL_REVISION", "MATERIAL_REVISION"],
    )
    result = await DecisionPipeline(
        db, model_runner=runner, clock=fixed_clock
    ).evaluate_quant_proposal(
        proposal.proposal_id, user_id="user", account_id="account-1"
    )
    assert result.consensus_decision.status == "CONSENSUS_REJECT"
    assert result.risk_decision is None
    assert runner.normal_calls == runner.top_calls == 2


@pytest.mark.asyncio
async def test_failed_retry_preserves_old_attempt_and_success_objects():
    db = FakeDB()
    _, _, proposal = await _prepare_decision_input(db)
    failed = FixedModelRunner(normal_statuses=["MODEL_FAILED"])
    first = await DecisionPipeline(
        db, model_runner=failed, clock=fixed_clock
    ).evaluate_quant_proposal(
        proposal.proposal_id, user_id="user", account_id="account-1"
    )
    succeeded = FixedModelRunner()
    second = await DecisionPipeline(
        db, model_runner=succeeded, clock=fixed_clock
    ).evaluate_quant_proposal(
        proposal.proposal_id,
        user_id="user",
        account_id="account-1",
        retry_failed=True,
    )
    assert (first.attempt_number, second.attempt_number) == (1, 2)
    assert db["ag_decision_runs"].count() == 2
    report = await db["analysis_reports"].find_one(
        {"analysis_id": second.analysis_id}
    )
    assert len(report["normal_trade_plan_history"]) == 2


@pytest.mark.asyncio
async def test_same_run_identity_with_mutated_proposal_is_rejected():
    db = FakeDB()
    _, _, proposal = await _prepare_decision_input(db)
    pipeline = DecisionPipeline(
        db, model_runner=FixedModelRunner(), clock=fixed_clock
    )
    await pipeline.evaluate_quant_proposal(
        proposal.proposal_id, user_id="user", account_id="account-1"
    )
    stored = await db["ag_quant_proposals"].find_one(
        {"proposal_id": proposal.proposal_id}
    )
    stored["input_hash"] = "f" * 64
    await db["ag_quant_proposals"].replace_one(
        {"proposal_id": proposal.proposal_id}, stored
    )
    with pytest.raises(DecisionIntegrityError, match="conflicting proposal"):
        await pipeline.evaluate_quant_proposal(
            proposal.proposal_id, user_id="user", account_id="account-1"
        )


def test_decision_modules_have_no_execution_dependencies_or_pr006_objects():
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    targets = (
        "app/services/alphaguard/decision_pipeline.py",
        "app/services/alphaguard/hard_risk_engine.py",
        "app/services/alphaguard/consensus_engine.py",
    )
    forbidden = (
        "OrderService",
        "MatchingEngine",
        "OrderIntent",
        "PaperOrder",
        "/paper/order",
        "place_order",
        "freeze_funds",
    )
    for relative in targets:
        source = (root / relative).read_text(encoding="utf-8")
        assert all(token not in source for token in forbidden)
