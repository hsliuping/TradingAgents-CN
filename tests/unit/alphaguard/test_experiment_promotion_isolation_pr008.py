from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.services.alphaguard.challenger_assignment_service import (
    ChallengerAssignmentService,
)
from app.services.alphaguard.champion_comparison_service import (
    ChampionComparisonService,
)
from app.services.alphaguard.champion_promotion_service import (
    ChampionPromotionService,
)
from app.services.alphaguard.champion_resolver import (
    ChampionResolutionError,
    ChampionResolver,
)
from app.services.alphaguard.champion_rollback_service import (
    ChampionRollbackService,
)
from app.services.alphaguard.experiment_risk_review_service import (
    ExperimentRiskReviewService,
)
from app.services.alphaguard.promotion_policy_service import (
    PromotionPolicyService,
)
from tests.unit.alphaguard._fakes import FakeDB
from tests.unit.alphaguard.pr006_helpers import setup_paper
from tests.unit.alphaguard.pr008_helpers import (
    seed_champion_assignment,
    seed_single_variable_experiment,
)
from tradingagents.alphaguard.decision_schemas import ModelExecutionMeta
from tradingagents.alphaguard.experiment_schemas import (
    ChampionComparisonReport,
    ExperimentRiskReview,
    ExperimentRun,
    LeakageAuditReport,
    RobustnessTestReport,
    ShadowRun,
    experiment_hash,
)
from tradingagents.alphaguard.paper_schemas import (
    OrderIntent,
    PAPER_SCHEMA_VERSION,
    paper_canonical_hash,
)
from tradingagents.alphaguard.structured_output import StructuredInvocation


def successful_meta() -> ModelExecutionMeta:
    now = datetime(2026, 7, 1, tzinfo=timezone.utc)
    return ModelExecutionMeta(
        provider="stub",
        model_name="top-stub",
        model_version="top-stub-v1",
        prompt_name="experiment_risk_review",
        prompt_version="experiment_risk_review_v1",
        started_at=now,
        finished_at=now,
        latency_ms=0,
        execution_status="SUCCESS",
        raw_output_hash="a" * 64,
        template_hash="b" * 64,
        context_hash="c" * 64,
        input_hash="d" * 64,
    )


def failed_meta(status: str = "MODEL_FAILED") -> ModelExecutionMeta:
    now = datetime(2026, 7, 1, tzinfo=timezone.utc)
    return ModelExecutionMeta(
        provider="stub",
        model_name="top-stub",
        model_version="top-stub-v1",
        prompt_name="experiment_risk_review",
        prompt_version="experiment_risk_review_v1",
        started_at=now,
        finished_at=now,
        latency_ms=0,
        execution_status=status,
        error_type="PROVIDER_ERROR",
        error_message="redacted failure",
    )


class StubRiskRunner:
    def __init__(self, payload=None, failure_status=None):
        self.payload = payload
        self.failure_status = failure_status

    async def invoke(self, payload, *, trace_id, input_hash):
        if self.failure_status:
            return StructuredInvocation(
                payload=None,
                model_meta=failed_meta(self.failure_status),
                failure_status=self.failure_status,
                error_type="PROVIDER_ERROR",
                error_message="failure",
            )
        return StructuredInvocation(
            payload=self.payload,
            model_meta=successful_meta(),
        )


async def ready_comparison(db, definition):
    payload = {
        "experiment_id": definition.experiment_id,
        "status": "READY",
        "historical_result_ids": ["historical"],
        "out_of_sample_result_ids": ["oos"],
        "robustness_report_ids": ["robust"],
        "shadow_run_ids": ["shadow"],
        "challenger_assignment_ids": ["assignment"],
        "sample_count": 30,
        "paired_sample_count": 20,
        "paired_coverage": Decimal("1"),
        "champion_summary": {"net_return": "0.01"},
        "challenger_summary": {"net_return": "0.02"},
        "value_added_summary": {
            "improved_metrics": ["net_return"],
            "worsened_metrics": ["turnover"],
            "insufficient_metrics": [],
        },
        "return_comparison": {"difference": "0.01"},
        "drawdown_comparison": {"worsening": Decimal("0")},
        "cost_comparison": {"challenger": "0.01"},
        "turnover_comparison": {"challenger": "0.10"},
        "regime_stability_comparison": {"available_segments": ["BULL", "BEAR", "RANGE"]},
        "outlier_dependency_comparison": {"top_trade_contribution_pct": "0.20"},
        "leakage_status": "PASS",
        "robustness_status": "PASS",
        "shadow_consistency_status": "PASS",
        "challenger_consistency_status": "PASS",
        "gate_results": [],
        "promotion_policy_version": "1.0.0",
    }
    payload["report_hash"] = experiment_hash(payload)
    report = ChampionComparisonReport(
        comparison_report_id="comparison-ready",
        created_at=datetime(2026, 7, 10),
        **payload,
    )
    await db["ag_exp_comparison_reports"].insert_one(
        report.model_dump(mode="python")
    )
    return report


async def seed_review_prerequisites(db, definition, report):
    run = ExperimentRun(
        run_id="run-1",
        experiment_id=definition.experiment_id,
        dataset_manifest_id="manifest",
        run_type="HISTORICAL_REPLAY",
        status="COMPLETED",
        champion_version_refs={"component": definition.baseline_version_ref},
        challenger_version_refs={"component": definition.challenger_version_ref},
        code_commit="a" * 40,
        code_tree_hash="b" * 40,
        config_hash="c" * 64,
        environment_hash="d" * 64,
        reproducibility="DETERMINISTIC",
        input_hash="e" * 64,
        result_hash="f" * 64,
        created_by="test",
        created_at=datetime(2026, 7, 1),
    )
    await db["ag_exp_runs"].insert_one(run.model_dump(mode="python"))
    leakage = LeakageAuditReport(
        leakage_audit_id="leak-1",
        run_id=run.run_id,
        status="PASS",
        future_price_leakage=False,
        future_financial_leakage=False,
        future_news_leakage=False,
        evaluation_label_leakage=False,
        split_overlap_leakage=False,
        current_config_leakage=False,
        input_hash="1" * 64,
        created_at=datetime(2026, 7, 2),
    )
    await db["ag_exp_leakage_audits"].insert_one(
        leakage.model_dump(mode="python")
    )
    robustness = RobustnessTestReport(
        robustness_report_id="robust-1",
        run_id=run.run_id,
        status="PASS",
        scenarios=[{"scenario": "BASELINE", "status": "PASS"}],
        cost_stress_result={},
        slippage_stress_result={},
        delayed_entry_result={},
        missing_data_result={},
        regime_segment_result={},
        outlier_dependency_result={},
        input_hash="2" * 64,
        created_at=datetime(2026, 7, 2),
    )
    await db["ag_exp_robustness_reports"].insert_one(
        robustness.model_dump(mode="python")
    )


@pytest.mark.asyncio
async def test_zero_real_samples_are_insufficient_and_block_promotion():
    db = FakeDB()
    registry, definition, baseline, _ = await seed_single_variable_experiment(db)
    report = await ChampionComparisonService(db).create(definition.experiment_id)
    assert report.status == "INSUFFICIENT_DATA"
    assert "historical_samples" in {
        item["rule"] for item in report.gate_results
    }
    await seed_champion_assignment(db, baseline)
    await registry.transition(definition.experiment_id, "EXPERIMENT", reason="test")
    await registry.transition(definition.experiment_id, "BACKTESTED", reason="test")
    await registry.transition(definition.experiment_id, "SHADOW", reason="test")
    await registry.transition(definition.experiment_id, "CHALLENGER", reason="test")
    with pytest.raises((ValueError, LookupError)):
        await ChampionPromotionService(db).create_request(
            definition.experiment_id,
            comparison_report_id=report.comparison_report_id,
            risk_review_id="missing",
            requested_by="admin",
            effective_from_trade_date=date(2026, 7, 2),
        )
    assert db["ag_exp_promotion_requests"].count() == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    [
        "READY_FOR_HUMAN_REVIEW",
        "MORE_VALIDATION_REQUIRED",
        "REJECT",
        "SUSPEND",
    ],
)
async def test_top_experiment_risk_review_structured_statuses(status):
    db = FakeDB()
    _, definition, *_ = await seed_single_variable_experiment(db)
    report = await ready_comparison(db, definition)
    await seed_review_prerequisites(db, definition, report)
    payload = {
        "status": status,
        "leakage_concerns": [],
        "overfitting_concerns": [],
        "sample_concerns": [],
        "regime_concerns": [],
        "execution_concerns": [],
        "rollback_concerns": [],
        "required_followups": [],
        "risk_summary": "fixed structured experiment risk review",
    }
    review = await ExperimentRiskReviewService(
        db, runner=StubRiskRunner(payload)
    ).review(
        definition.experiment_id,
        comparison_report_id=report.comparison_report_id,
    )
    assert review.status == status
    assert review.prompt_version == "experiment_risk_review_v1"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("runner", "expected"),
    [
        (StubRiskRunner(failure_status="MODEL_FAILED"), "MODEL_FAILED"),
        (StubRiskRunner({"status": "BOGUS", "risk_summary": "bad"}), "INVALID_OUTPUT"),
    ],
)
async def test_top_experiment_review_failure_never_authorizes_promotion(
    runner, expected
):
    db = FakeDB()
    _, definition, *_ = await seed_single_variable_experiment(db)
    report = await ready_comparison(db, definition)
    await seed_review_prerequisites(db, definition, report)
    review = await ExperimentRiskReviewService(db, runner=runner).review(
        definition.experiment_id,
        comparison_report_id=report.comparison_report_id,
    )
    assert review.status == expected
    assert review.status != "READY_FOR_HUMAN_REVIEW"


async def promotion_fixture():
    db = FakeDB()
    registry, definition, baseline, challenger = (
        await seed_single_variable_experiment(db)
    )
    await PromotionPolicyService(db).register_builtin()
    assignment = await seed_champion_assignment(db, baseline)
    await db["trading_calendar"].insert_one(
        {"market": "CN", "session_date": "2026-07-15", "is_open": True}
    )
    for target in ("EXPERIMENT", "BACKTESTED", "SHADOW", "CHALLENGER"):
        await registry.transition(definition.experiment_id, target, reason="test")
    report = await ready_comparison(db, definition)
    review = ExperimentRiskReview(
        review_id="review-ready",
        experiment_id=definition.experiment_id,
        comparison_report_id=report.comparison_report_id,
        status="READY_FOR_HUMAN_REVIEW",
        risk_summary="ready for separate human review",
        model_meta=successful_meta(),
        input_hash="4" * 64,
        output_hash="5" * 64,
        created_at=datetime(2026, 7, 10),
    )
    await db["ag_exp_risk_reviews"].insert_one(review.model_dump(mode="python"))
    return db, definition, baseline, challenger, assignment, report, review


@pytest.mark.asyncio
async def test_human_promotion_requires_exact_confirmation_and_commits_saga():
    db, definition, baseline, challenger, assignment, report, review = (
        await promotion_fixture()
    )
    service = ChampionPromotionService(db)
    request = await service.create_request(
        definition.experiment_id,
        comparison_report_id=report.comparison_report_id,
        risk_review_id=review.review_id,
        requested_by="admin",
        effective_from_trade_date=date(2026, 7, 15),
        now=datetime(2026, 7, 10),
    )
    with pytest.raises(ValueError, match="confirmation"):
        await service.approve_request(
            request.promotion_request_id,
            approved_by="admin",
            decision_reason="tested",
            confirmation_text="wrong",
            current_champion_hash=baseline.payload_hash,
            proposed_champion_hash=challenger.payload_hash,
        )
    approval, saga = await service.approve_request(
        request.promotion_request_id,
        approved_by="admin",
        decision_reason="all fixed gates reviewed",
        confirmation_text=request.required_confirmation_text,
        current_champion_hash=baseline.payload_hash,
        proposed_champion_hash=challenger.payload_hash,
    )
    assert approval.approved is True
    assert saga.status == "COMMITTED"
    assert (
        await ChampionResolver(db).resolve_champion(
            component_type=baseline.component_type,
            component_key=baseline.component_key,
            market="CN",
            as_of_trade_date=date(2026, 7, 14),
        )
    ).version_ref == baseline.version_ref
    assert (
        await ChampionResolver(db).resolve_champion(
            component_type=baseline.component_type,
            component_key=baseline.component_key,
            market="CN",
            as_of_trade_date=date(2026, 7, 15),
        )
    ).version_ref == challenger.version_ref
    assert db["ag_exp_promotion_approvals"].count() == 1


@pytest.mark.asyncio
async def test_incomplete_assignment_written_promotion_saga_recovers_once():
    db, definition, baseline, challenger, _, report, review = (
        await promotion_fixture()
    )
    service = ChampionPromotionService(db)
    request = await service.create_request(
        definition.experiment_id,
        comparison_report_id=report.comparison_report_id,
        risk_review_id=review.review_id,
        requested_by="admin",
        effective_from_trade_date=date(2026, 7, 15),
        now=datetime(2026, 7, 10),
    )
    _, committed = await service.approve_request(
        request.promotion_request_id,
        approved_by="admin",
        decision_reason="fixed evidence",
        confirmation_text=request.required_confirmation_text,
        current_champion_hash=baseline.payload_hash,
        proposed_champion_hash=challenger.payload_hash,
    )
    # Simulate a standalone-Mongo process crash after the CAS pointer write
    # but before the request/state/event tail was durably completed.
    saga_document = db["ag_exp_promotion_sagas"].documents[0]
    saga_document["status"] = "ASSIGNMENT_WRITTEN"
    saga_document["committed_at"] = None
    request_document = db["ag_exp_promotion_requests"].documents[0]
    request_document["status"] = "APPROVED"
    definition_document = db["ag_exp_definitions"].documents[0]
    definition_document["status"] = "CHALLENGER"
    counts = await service.recover_incomplete_sagas()
    assert counts == {"committed": 1, "rolled_back": 0, "failed": 0}
    assert db["ag_exp_promotion_sagas"].documents[0]["status"] == "COMMITTED"
    assert db["ag_exp_promotion_requests"].documents[0]["status"] == "APPLIED"
    assert db["ag_exp_definitions"].documents[0]["status"] == "CHAMPION"
    assert (
        await ChampionResolver(db).resolve_champion(
            component_type=baseline.component_type,
            component_key=baseline.component_key,
            market="CN",
            as_of_trade_date=date(2026, 7, 15),
        )
    ).version_ref == challenger.version_ref
    assert await service.recover_incomplete_sagas() == {
        "committed": 0,
        "rolled_back": 0,
        "failed": 0,
    }
    assert committed.promotion_saga_id == saga_document["promotion_saga_id"]


@pytest.mark.asyncio
async def test_champion_hash_change_blocks_approval():
    db, definition, baseline, challenger, assignment, report, review = (
        await promotion_fixture()
    )
    service = ChampionPromotionService(db)
    request = await service.create_request(
        definition.experiment_id,
        comparison_report_id=report.comparison_report_id,
        risk_review_id=review.review_id,
        requested_by="admin",
        effective_from_trade_date=date(2026, 7, 15),
    )
    db["ag_exp_champion_assignments"].documents[0][
        "current_version_ref"
    ] = challenger.version_ref
    with pytest.raises(Exception, match="changed"):
        await service.approve_request(
            request.promotion_request_id,
            approved_by="admin",
            decision_reason="should fail",
            confirmation_text=request.required_confirmation_text,
            current_champion_hash=baseline.payload_hash,
            proposed_champion_hash=challenger.payload_hash,
        )
    assert db["ag_exp_promotion_approvals"].count() == 0


@pytest.mark.asyncio
async def test_resolver_fails_closed_without_assignment_or_uncommitted_saga():
    db = FakeDB()
    _, _, baseline, _ = await seed_single_variable_experiment(db)
    resolver = ChampionResolver(db)
    with pytest.raises(ChampionResolutionError):
        await resolver.resolve_champion(
            component_type=baseline.component_type,
            component_key=baseline.component_key,
            market="CN",
            as_of_trade_date=date(2026, 7, 1),
        )
    assignment = await seed_champion_assignment(db, baseline)
    db["ag_exp_champion_assignments"].documents[0][
        "promotion_saga_id"
    ] = "not-committed"
    with pytest.raises(ChampionResolutionError):
        await resolver.resolve_champion(
            component_type=baseline.component_type,
            component_key=baseline.component_key,
            market="CN",
            as_of_trade_date=date(2026, 7, 1),
        )


@pytest.mark.asyncio
async def test_controlled_rollback_preserves_versions_and_effective_dates():
    db = FakeDB()
    _, _, baseline, challenger = await seed_single_variable_experiment(db)
    assignment = await seed_champion_assignment(
        db,
        challenger,
        previous_version_ref=baseline.version_ref,
    )
    await db["trading_calendar"].insert_one(
        {"market": "CN", "session_date": "2026-07-15", "is_open": True}
    )
    record, saga = await ChampionRollbackService(db).rollback(
        assignment.champion_slot_id,
        requested_by="admin",
        approved_by="admin",
        reason="integrity regression",
        confirmation_text=f"ROLLBACK {assignment.champion_slot_id}",
        current_champion_hash=assignment.assignment_hash,
        effective_from_trade_date=date(2026, 7, 15),
    )
    assert record.status == "COMMITTED"
    assert saga.status == "COMMITTED"
    resolver = ChampionResolver(db)
    assert (
        await resolver.resolve_champion(
            component_type=baseline.component_type,
            component_key=baseline.component_key,
            market="CN",
            as_of_trade_date=date(2026, 7, 14),
        )
    ).version_ref == challenger.version_ref
    assert (
        await resolver.resolve_champion(
            component_type=baseline.component_type,
            component_key=baseline.component_key,
            market="CN",
            as_of_trade_date=date(2026, 7, 15),
        )
    ).version_ref == baseline.version_ref
    assert db["ag_exp_component_versions"].count() == 2


@pytest.mark.asyncio
async def test_challenger_assignment_is_exclusive_and_account_isolated():
    db = FakeDB()
    registry, definition, *_ = await seed_single_variable_experiment(db)
    for target in ("EXPERIMENT", "BACKTESTED", "SHADOW"):
        await registry.transition(definition.experiment_id, target, reason="test")
    await setup_paper(db, user_id="user-1")
    shadow = ShadowRun(
        shadow_run_id="shadow-1",
        experiment_id=definition.experiment_id,
        run_id="run-shadow",
        status="COMPLETED",
        started_at=datetime(2026, 7, 1),
        ended_at=datetime(2026, 7, 10),
        champion_output_count=20,
        challenger_output_count=20,
        paired_output_count=20,
        divergence_count=2,
        integrity_error_count=0,
        min_required_trade_days=20,
        observed_trade_days=20,
        input_hash="6" * 64,
        created_at=datetime(2026, 7, 1),
    )
    await db["ag_exp_shadow_runs"].insert_one(shadow.model_dump(mode="python"))
    service = ChallengerAssignmentService(db)
    assignment = await service.activate(
        definition.experiment_id,
        user_id="user-1",
        activation_trade_date=date(2026, 7, 2),
    )
    assert assignment.status == "ACTIVE"
    assert db["ag_exp_challenger_assignments"].count() == 1
    assert db["ag_candidates"].count() == 0
    reused = await service.activate(
        definition.experiment_id,
        user_id="user-1",
        activation_trade_date=date(2026, 7, 2),
    )
    assert reused.assignment_id == assignment.assignment_id


def test_challenger_intent_requires_full_lineage_and_never_live_execution():
    base = {
        "intent_id": "intent",
        "user_id": "u",
        "account_id": "a",
        "account_type": "PAPER_CHALLENGER",
        "source_type": "CHALLENGER",
        "source_object_id": "output",
        "analysis_id": None,
        "candidate_id": None,
        "snapshot_id": "snapshot",
        "quant_proposal_id": None,
        "plan_id": None,
        "consensus_id": None,
        "risk_decision_id": None,
        "experiment_id": "experiment",
        "assignment_id": "assignment",
        "symbol": "600519",
        "market": "CN",
        "currency": "CNY",
        "original_action": "BUY",
        "side": "BUY",
        "order_type": "LIMIT",
        "quantity": 100,
        "limit_price": Decimal("10"),
        "earliest_execute_at": datetime(2026, 7, 2, 9, 30),
        "expires_at": datetime(2026, 7, 3, 15),
        "execution_policy_version": "paper-execution-policy-v1",
        "matching_engine_version": "matching-engine-v1",
        "fee_policy_version": "paper-fee-policy-v1",
        "account_state_snapshot_id": "state",
        "idempotency_key": "key",
        "created_at": datetime(2026, 7, 1),
        "schema_version": PAPER_SCHEMA_VERSION,
        "benchmark_only": False,
        "consensus_approved": True,
        "hard_risk_approved": True,
        "execution_environment": "PAPER",
        "live_execution_allowed": False,
    }
    base["immutable_hash"] = paper_canonical_hash(
        base, exclude={"intent_id", "immutable_hash", "created_at"}
    )
    intent = OrderIntent.model_validate(base)
    assert intent.live_execution_allowed is False
    bad = dict(base)
    bad["assignment_id"] = None
    bad["immutable_hash"] = paper_canonical_hash(
        bad, exclude={"intent_id", "immutable_hash", "created_at"}
    )
    with pytest.raises(ValidationError):
        OrderIntent.model_validate(bad)
