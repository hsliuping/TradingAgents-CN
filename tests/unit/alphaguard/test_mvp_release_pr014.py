from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

import app.services.alphaguard.mvp_acceptance_service as acceptance_module
from app.services.alphaguard.consistency_service import AlphaGuardConsistencyService
from app.services.alphaguard.daily_run_service import (
    AlphaGuardDailyRunService,
    CallbackStageExecutor,
    DAILY_STAGE_SPECS,
    StageExecutionResult,
)
from app.services.alphaguard.daily_stage_executor import ProductionDailyStageExecutor
from app.services.alphaguard.mvp_acceptance_service import MvpAcceptanceService
from scripts.alphaguard_daily_run import _reject_live_arguments
from tests.unit.alphaguard._fakes import FakeDB
from tradingagents.alphaguard.mongo_indexes import ALPHAGUARD_INDEX_SPECS


TRADE_DATE = date(2026, 8, 3)
INPUT_VERSION = "pr014-test-input"


def test_daily_stage_contract_has_twenty_ordered_explicit_dependencies():
    assert len(DAILY_STAGE_SPECS) == 20
    assert [item.stage_id for item in DAILY_STAGE_SPECS] == [
        "TRADING_CALENDAR",
        "SECURITY_MASTER_SYNC",
        "RAW_QFQ_PRICE_SYNC",
        "BENCHMARK_INDUSTRY_SYNC",
        "TRADING_STATUS_SYNC",
        "DATA_QUALITY",
        "RECOMMENDATION_COVERAGE",
        "FULL_MARKET_RECOMMENDATION",
        "CANDIDATE_SNAPSHOT",
        "FACTOR_REGIME",
        "QUANT_PROPOSAL",
        "MODEL_CHAIN",
        "ORDER_INTENT",
        "T1_ORDER_PROCESSING",
        "MATCHING_SETTLEMENT",
        "EVALUATION",
        "ATTRIBUTION",
        "CHALLENGER",
        "OPERATIONS_SUMMARY",
        "NOTIFICATION",
    ]
    assert DAILY_STAGE_SPECS[0].dependencies == ()
    for previous, current in zip(DAILY_STAGE_SPECS, DAILY_STAGE_SPECS[1:]):
        assert current.dependencies == (previous.stage_id,)


@pytest.mark.asyncio
async def test_daily_run_reuses_identical_input_and_blocks_all_downstream_on_failure():
    db = FakeDB()
    service = AlphaGuardDailyRunService(db, executor=CallbackStageExecutor({}))
    first = await service.run(
        trading_date=TRADE_DATE,
        input_version=INPUT_VERSION,
    )
    repeated = await service.run(
        trading_date=TRADE_DATE,
        input_version=INPUT_VERSION,
    )
    assert first.status == "SUCCESS"
    assert len(first.stages) == 20
    assert repeated.status == "SUCCESS"
    assert len(repeated.stages) == 20
    assert {item.status for item in repeated.stages} == {"REUSED"}
    assert len({item.job_id for item in first.stages}) == 20
    assert len({item.idempotency_key for item in first.stages}) == 20

    failed_db = FakeDB()
    executed = []

    def fail_quality(stage, **_):
        executed.append(stage.stage_id)
        raise RuntimeError("quality fixture failure")

    callbacks = {
        item.stage_id: (
            fail_quality
            if item.stage_id == "DATA_QUALITY"
            else lambda stage, **_: executed.append(stage.stage_id)
        )
        for item in DAILY_STAGE_SPECS
    }
    failed = await AlphaGuardDailyRunService(
        failed_db, executor=CallbackStageExecutor(callbacks)
    ).run(trading_date=TRADE_DATE, input_version="failure-input")
    assert failed.status == "FAILED"
    assert failed.failed_stage_id == "DATA_QUALITY"
    assert executed[-1] == "DATA_QUALITY"
    assert len(failed.stages) == 20
    assert all(
        item.status == "BLOCKED"
        for item in failed.stages[6:]
    )
    assert all(
        item.error_code == "UPSTREAM_NOT_COMPLETED"
        for item in failed.stages[6:]
    )


class RestoringExecutor:
    def __init__(self):
        self.executed = []
        self.restored = []

    async def restore(self, stage, **_):
        self.restored.append(stage.stage_id)

    async def execute(self, stage, **_):
        self.executed.append(stage.stage_id)
        if stage.stage_id == "RAW_QFQ_PRICE_SYNC":
            assert "SECURITY_MASTER_SYNC" in self.restored
        return StageExecutionResult(output_count=1)


@pytest.mark.asyncio
async def test_interruption_resume_and_from_to_restore_dependency_state():
    db = FakeDB()
    first_executor = RestoringExecutor()
    first = AlphaGuardDailyRunService(db, executor=first_executor)
    with pytest.raises(RuntimeError, match="simulated interruption"):
        await first.run(
            trading_date=TRADE_DATE,
            input_version="resume-input",
            to_stage="RAW_QFQ_PRICE_SYNC",
            interrupt_before_stage="RAW_QFQ_PRICE_SYNC",
        )
    assert first_executor.executed == ["TRADING_CALENDAR", "SECURITY_MASTER_SYNC"]

    resumed_executor = RestoringExecutor()
    resumed = await AlphaGuardDailyRunService(
        db, executor=resumed_executor
    ).run(
        trading_date=TRADE_DATE,
        input_version="resume-input",
        resume=True,
        from_stage="RAW_QFQ_PRICE_SYNC",
        to_stage="RAW_QFQ_PRICE_SYNC",
    )
    assert resumed.status == "SUCCESS"
    assert resumed_executor.executed == ["RAW_QFQ_PRICE_SYNC"]
    assert "SECURITY_MASTER_SYNC" in resumed_executor.restored


@pytest.mark.asyncio
async def test_production_executor_rehydrates_candidate_aggregate_after_restart():
    executor = ProductionDailyStageExecutor(FakeDB())
    candidate_stage = next(
        item for item in DAILY_STAGE_SPECS if item.stage_id == "CANDIDATE_SNAPSHOT"
    )
    await executor.restore(
        candidate_stage,
        stage_run=SimpleNamespace(
            result={
                "proposal_count": 4,
                "triggered_count": 2,
                "decision_count": 2,
                "terminal_statuses": ["REJECTED", "RISK_REJECTED"],
            }
        ),
        daily_run_id="restored-run",
    )
    factor = await executor.stage_factor_regime()
    proposal = await executor.stage_quant_proposal()
    model = await executor.stage_model_chain()
    assert factor.output_count == 4
    assert proposal.result == {"proposal_count": 4, "triggered_count": 2}
    assert model.output_count == 2
    assert model.result["terminal_statuses"] == ["REJECTED", "RISK_REJECTED"]


@pytest.mark.asyncio
async def test_non_trading_day_skips_remaining_without_executing_callbacks():
    executed = []

    def calendar(stage, **_):
        executed.append(stage.stage_id)
        return StageExecutionResult(
            status="SKIPPED",
            message="非交易日",
            skip_remaining=True,
        )

    summary = await AlphaGuardDailyRunService(
        FakeDB(), executor=CallbackStageExecutor({"TRADING_CALENDAR": calendar})
    ).run(trading_date=TRADE_DATE, input_version="closed-date")
    assert summary.status == "SUCCESS"
    assert executed == ["TRADING_CALENDAR"]
    assert len(summary.stages) == 20
    assert {item.status for item in summary.stages} == {"SKIPPED"}


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", ["NO_SIGNAL", "MODEL_REJECT", "FULL_FILL"])
async def test_isolated_acceptance_scenarios_do_not_manufacture_production_data(scenario):
    db = FakeDB()

    async def model(stage, **_):
        if scenario == "NO_SIGNAL":
            return StageExecutionResult(
                output_count=0,
                result={"terminal_statuses": [], "model_calls": 0},
            )
        await db["scenario_decisions"].insert_one(
            {"scenario": scenario, "status": "REJECT" if scenario == "MODEL_REJECT" else "PASS"}
        )
        return StageExecutionResult(output_count=1)

    async def order(stage, **_):
        if scenario != "FULL_FILL":
            return StageExecutionResult(output_count=0)
        await db["scenario_order_intents"].insert_one(
            {"intent_id": "isolated-intent", "status": "READY"}
        )
        return StageExecutionResult(output_count=1)

    async def matching(stage, **_):
        if scenario != "FULL_FILL":
            return StageExecutionResult(output_count=0)
        await db["scenario_orders"].insert_one(
            {"order_id": "isolated-order", "status": "FILLED"}
        )
        await db["scenario_fills"].insert_one(
            {"fill_id": "isolated-fill", "status": "COMMITTED"}
        )
        await db["scenario_positions"].insert_one(
            {"position_id": "isolated-position", "quantity": 100}
        )
        return StageExecutionResult(output_count=1)

    callbacks = {
        "MODEL_CHAIN": model,
        "ORDER_INTENT": order,
        "MATCHING_SETTLEMENT": matching,
        "EVALUATION": lambda **_: StageExecutionResult(output_count=1),
    }
    summary = await AlphaGuardDailyRunService(
        db, executor=CallbackStageExecutor(callbacks)
    ).run(trading_date=TRADE_DATE, input_version=f"scenario-{scenario}")
    assert summary.status == "SUCCESS"
    if scenario in {"NO_SIGNAL", "MODEL_REJECT"}:
        assert db["scenario_orders"].count() == 0
        assert db["scenario_fills"].count() == 0
    else:
        assert db["scenario_orders"].count() == 1
        assert db["scenario_fills"].count() == 1
        assert db["scenario_positions"].count() == 1

    restarted = await AlphaGuardDailyRunService(
        db, executor=CallbackStageExecutor(callbacks)
    ).run(trading_date=TRADE_DATE, input_version=f"scenario-{scenario}")
    assert {item.status for item in restarted.stages} == {"REUSED"}
    assert db["scenario_orders"].count() <= 1
    assert db["scenario_fills"].count() <= 1


@pytest.mark.asyncio
async def test_consistency_service_passes_clean_indexed_isolate_and_fails_negative_cash():
    db = FakeDB()
    for collection_name, specs in ALPHAGUARD_INDEX_SPECS.items():
        for spec in specs:
            await db[collection_name].create_index(
                spec["keys"],
                name=spec["name"],
                unique=spec.get("unique", False),
            )
    clean = await AlphaGuardConsistencyService(db).run()
    assert clean["status"] == "PASS"
    assert clean["auto_repair_performed"] is False

    await db["ag_model_validation_evidence_snapshots"].insert_one(
        {"snapshot_id": "validation-snapshot"}
    )
    await db["ag_model_validation_runs"].insert_one(
        {"validation_run_id": "validation-run"}
    )
    await db["ag_model_runs"].insert_one(
        {
            "model_run_id": "valid-model-run",
            "analysis_id": "real-model-validation:validation-run",
            "run_mode": "REAL_MODEL_VALIDATION",
            "snapshot_id": "validation-snapshot",
        }
    )
    valid_model = await AlphaGuardConsistencyService(db).run()
    assert valid_model["status"] == "PASS"

    await db["ag_model_contract_checks"].insert_one(
        {"contract_check_id": "contract-check"}
    )
    await db["ag_model_runs"].insert_one(
        {
            "model_run_id": "valid-contract-check",
            "analysis_id": "model-capability:research-manager:contract-check",
            "run_mode": "MODEL_CAPABILITY_CHECK",
            "snapshot_id": "synthetic-contract-snapshot",
        }
    )
    valid_capability = await AlphaGuardConsistencyService(db).run()
    assert valid_capability["status"] == "PASS"

    await db["ag_model_runs"].insert_one(
        {
            "model_run_id": "orphan-model-run",
            "analysis_id": "real-model-validation:missing-run",
            "run_mode": "REAL_MODEL_VALIDATION",
            "snapshot_id": "missing-snapshot",
        }
    )
    orphan_model = await AlphaGuardConsistencyService(db).run()
    model_check = next(
        item
        for item in orphan_model["checks"]
        if item["check_id"] == "model_call_references"
    )
    assert model_check["count"] == 1
    await db["ag_model_runs"].delete_one({"model_run_id": "orphan-model-run"})

    await db["ag_paper_accounts"].insert_one(
        {
            "account_id": "negative-account",
            "account_type": "PAPER_QUANT",
            "cash_available": -1,
            "cash_reserved": 0,
            "initial_cash": 0,
        }
    )
    failed = await AlphaGuardConsistencyService(db).run()
    assert failed["status"] == "FAIL"
    assert next(
        item for item in failed["checks"] if item["check_id"] == "negative_cash"
    )["count"] == 1


class OperationsStub:
    def __init__(self):
        self.scheduler = SimpleNamespace(get_job=lambda job_id: object())

    async def readiness(self, persist_alerts=False):
        assert persist_alerts is False
        return SimpleNamespace(
            overall_status="READY",
            report_id="readiness-report",
            generated_at=datetime(2026, 8, 3, 18, 40),
            schema_version="alphaguard-operations-v1",
            live_trading_enabled=False,
            recommendation_ready=True,
            paper_execution_ready=True,
            evaluation_ready=True,
            experiment_ready=True,
            challenger_ready=True,
            active_challenger=False,
        )

    async def integrity(self):
        return {"status": "PASS"}


@pytest.mark.asyncio
async def test_mvp_matrix_uses_challenger_facts_and_real_model_evidence(monkeypatch, tmp_path):
    db = FakeDB()
    now = datetime(2026, 8, 3, 18, 30)
    documents = {
        "ag_candidates": {"candidate_id": "candidate", "status": "ACTIVE"},
        "ag_candidate_recommendations": {"recommendation_id": "recommendation", "status": "SUCCESS"},
        "ag_recommendation_data_coverages": {"coverage_id": "coverage", "status": "READY"},
        "ag_evidence_snapshots": {"snapshot_id": "snapshot", "status": "SUCCESS"},
        "ag_factor_results": {"factor_result_id": "factor", "status": "SUCCESS"},
        "ag_regime_results": {"regime_result_id": "regime", "status": "SUCCESS"},
        "ag_quant_proposals": {"proposal_id": "proposal", "status": "TRIGGERED"},
        "ag_model_research_results": {"research_result_id": "research", "status": "SUCCESS"},
        "analysis_reports": {"analysis_id": "analysis", "status": "SUCCESS"},
        "ag_consensus_decisions": {"consensus_id": "consensus", "status": "CONSENSUS_PASS"},
        "ag_risk_decisions": {"risk_decision_id": "risk", "status": "PASS"},
        "ag_paper_orders": {"order_id": "order", "status": "FILLED"},
        "ag_eval_subjects": {"subject_id": "subject", "status": "CALCULATED"},
        "ag_exp_component_versions": {"component_version_id": "component", "status": "ACTIVE"},
    }
    for collection, document in documents.items():
        await db[collection].insert_one({**document, "created_at": now})
    await db["ag_model_runs"].insert_one(
        {
            "model_run_id": "real-top-run",
            "status": "SUCCESS",
            "structured_output_status": "SUCCESS",
            "run_mode": "REAL_MODEL_VALIDATION",
            "created_at": now,
        }
    )
    await db["ag_model_validation_runs"].insert_one(
        {
            "validation_run_id": "level-b-validation",
            "status": "COMPLETED",
            "completed_at": now,
            "normal_result": {"status": "PROPOSE_TRADE"},
            "top_result": {"decision": "RISK_ADJUST"},
            "consensus_result": {"consensus_id": "level-b-consensus"},
            "hard_risk_result": {"risk_decision_id": "level-b-risk"},
            "normal_model_run_id": "level-b-normal",
            "top_model_run_id": "level-b-top",
            "execution_gate_status": "BLOCKED_VALIDATION_MODE",
            "validation_contract_version": "real-model-validation-v1",
        }
    )
    await db["ag_paper_accounts"].insert_one(
        {
            "account_id": "challenger-account",
            "account_type": "PAPER_CHALLENGER",
            "status": "ACTIVE",
            "created_at": now,
        }
    )
    await db["ag_paper_accounts"].insert_one(
        {
            "account_id": "newer-quant-account",
            "account_type": "PAPER_QUANT",
            "status": "ACTIVE",
            "created_at": datetime(2026, 8, 3, 18, 35),
        }
    )
    await db["notifications"].insert_one({"status": "unread"})
    monkeypatch.setattr(
        acceptance_module,
        "list_backups",
        lambda _root: [
            {
                "backup_id": "backup-1",
                "schema_version": "alphaguard-mvp-rc1-backup-v1",
                "path": str(tmp_path),
                "status": "READY",
            }
        ],
    )

    report = await MvpAcceptanceService(
        db,
        operations_service=OperationsStub(),
        backup_root=Path(tmp_path),
    ).report()
    by_id = {item.item_id: item for item in report.items}
    assert len(report.items) >= 24
    assert by_id["paper_challenger"].latest_object_id == "challenger-account"
    assert by_id["normal_model"].latest_object_id == "level-b-normal"
    assert by_id["top_model"].latest_object_id == "level-b-top"
    assert by_id["consensus"].latest_object_id == "level-b-consensus"
    assert by_id["hard_risk"].latest_object_id == "level-b-risk"
    assert by_id["data_consistency"].status == "可用"
    assert report.overall_status == "MVP_PAPER_READY"
    assert report.state_flags["REAL_MODEL_RUNTIME_READY"] is True
    assert report.state_flags["DUAL_MODEL_READY"] is True
    assert report.state_flags["RECOMMENDATION_READY"] is True
    assert report.state_flags["RECOMMENDATION_DATA_READY"] is True
    assert report.state_flags["PAPER_READY"] is True
    assert report.state_flags["EVALUATION_READY"] is True
    assert report.state_flags["EXPERIMENT_READY"] is True
    assert report.state_flags["CHALLENGER_READY"] is True
    assert report.state_flags["ACTIVE_CHALLENGER"] is False
    assert report.state_flags["AUTO_CANDIDATE_ACCEPT"] is False
    assert report.state_flags["LIVE_READY"] is False


@pytest.mark.parametrize("argument", ["--live", "--live=true", "live=true", "--LIVE=TRUE"])
def test_daily_cli_permanently_rejects_live_arguments(argument):
    with pytest.raises(SystemExit, match="拒绝启动"):
        _reject_live_arguments([argument])


def test_operations_chinese_release_contract_and_user_manual_entries_exist():
    root = Path(__file__).resolve().parents[3]
    operations = (
        root / "frontend/src/views/AlphaGuard/Operations.vue"
    ).read_text(encoding="utf-8")
    for phrase in (
        "MVP验收状态",
        "通知状态",
        "备份状态",
        "一致性状态",
        "发生了什么",
        "是否影响核心功能",
        "高级信息",
    ):
        assert phrase in operations

    required = {
        "ALPHAGUARD_DAILY_OPERATIONS.md": (
            "--resume",
            "一键预览",
            "安全关闭",
        ),
        "ALPHAGUARD_BACKUP_RESTORE.md": (
            "manifest_hash",
            "隔离恢复",
            "Secret",
        ),
        "ALPHAGUARD_TROUBLESHOOTING.md": (
            "通知",
            "一致性",
            "不要提供",
        ),
    }
    for filename, phrases in required.items():
        source = (root / "docs/user" / filename).read_text(encoding="utf-8")
        for phrase in phrases:
            assert phrase in source
