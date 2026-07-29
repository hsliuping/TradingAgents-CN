from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.services.alphaguard.decision_model_runner import (
    ExistingProviderDecisionModelRunner,
)
from app.services.alphaguard.execution_mode_safety_gate import (
    ExecutionModeBlockedError,
)
from app.services.alphaguard.execution_outbox_service import (
    ExecutionOutboxService,
)
from app.services.alphaguard.order_intent_factory import OrderIntentFactory
from app.services.alphaguard.production_reprocess_service import (
    ProductionReprocessConflict,
    ProductionReprocessService,
)
from tests.unit.alphaguard._fakes import FakeDB
from tests.unit.alphaguard.pr005_helpers import make_context
from tests.unit.alphaguard.test_evidence_window_v2 import (
    _v1_data,
    _v2_data,
    _with_hash,
)


def reprocess_snapshot():
    payload = _v2_data()
    payload.update(
        run_mode="PRODUCTION_REPROCESS",
        source_trade_date=date(2026, 7, 29),
        evidence_contract_version="evidence-contract-v2",
        reprocess_reason="EVIDENCE_CONTRACT_UPGRADE",
        reprocess_input_hash="9" * 64,
        original_realtime_run=False,
        automated_execution_allowed=False,
    )
    return _with_hash(payload)


def test_reprocess_snapshot_contract_is_non_executable_and_v1_compatible():
    snapshot = reprocess_snapshot()
    assert snapshot.run_mode == "PRODUCTION_REPROCESS"
    assert snapshot.automated_execution_allowed is False

    invalid = _v2_data()
    invalid.update(
        run_mode="PRODUCTION_REPROCESS",
        source_trade_date=date(2026, 7, 29),
        evidence_contract_version="evidence-contract-v2",
        reprocess_reason="EVIDENCE_CONTRACT_UPGRADE",
        reprocess_input_hash="9" * 64,
        original_realtime_run=False,
        automated_execution_allowed=True,
        immutable_hash="0" * 64,
    )
    with pytest.raises(ValidationError, match="incomplete or executable"):
        _with_hash(invalid)


@pytest.mark.asyncio
async def test_v1_realtime_and_v2_reprocess_snapshots_can_coexist():
    db = FakeDB()
    v1 = _with_hash(_v1_data())
    v2 = reprocess_snapshot()

    await db["ag_evidence_snapshots"].insert_one(
        v1.model_dump(mode="python")
    )
    await db["ag_evidence_snapshots"].insert_one(
        v2.model_dump(mode="python")
    )

    rows = await db["ag_evidence_snapshots"].find(
        {"symbol": v1.symbol, "trade_date": v1.trade_date}
    ).to_list(None)
    assert {item["snapshot_id"] for item in rows} == {
        v1.snapshot_id,
        v2.snapshot_id,
    }
    assert {item["schema_version"] for item in rows} == {
        "evidence-snapshot-v1",
        "evidence-snapshot-v2",
    }


@pytest.mark.asyncio
async def test_reprocess_lineage_cannot_create_outbox_or_intent():
    db = FakeDB()
    snapshot = reprocess_snapshot()
    await db["ag_evidence_snapshots"].insert_one(
        snapshot.model_dump(mode="python")
    )
    await db["ag_quant_proposals"].insert_one(
        {
            "proposal_id": "proposal-reprocess",
            "snapshot_id": snapshot.snapshot_id,
        }
    )

    with pytest.raises(ExecutionModeBlockedError, match="PRODUCTION_REPROCESS"):
        await ExecutionOutboxService(db).enqueue(
            event_type="CREATE_QUANT_BENCHMARK_INTENT",
            source_object_id="proposal-reprocess",
            user_id="user-1",
        )
    event = SimpleNamespace(
        event_type="CREATE_QUANT_BENCHMARK_INTENT",
        source_object_id="proposal-reprocess",
    )
    with pytest.raises(ExecutionModeBlockedError, match="PRODUCTION_REPROCESS"):
        await OrderIntentFactory(db).create_from_outbox(event)
    assert db["ag_execution_outbox"].count() == 0
    assert db["ag_order_intents"].count() == 0


@pytest.mark.asyncio
async def test_reprocess_evaluation_is_create_only_and_separate():
    db = FakeDB()
    service = ProductionReprocessService(db)
    snapshot = reprocess_snapshot()
    proposal = SimpleNamespace(
        proposal_id="proposal-reprocess",
        symbol="600519",
        market="CN",
        status="REJECTED",
        action_candidate="WAIT",
    )
    first = await service._save_reprocess_evaluation(
        user_id="user-1",
        snapshot=snapshot,
        proposal=proposal,
    )
    second = await service._save_reprocess_evaluation(
        user_id="user-1",
        snapshot=snapshot,
        proposal=proposal,
    )
    assert first[0] == second[0]
    assert first[1] == "CREATED"
    assert second[1] == "REUSED"
    assert db[service.EVALUATION_COLLECTION].count() == 1
    assert db["ag_eval_subjects"].count() == 0

    db[service.EVALUATION_COLLECTION].documents[0]["result_hash"] = "0" * 64
    with pytest.raises(ProductionReprocessConflict, match="INTEGRITY_CONFLICT"):
        await service._save_reprocess_evaluation(
            user_id="user-1",
            snapshot=snapshot,
            proposal=proposal,
        )


@pytest.mark.asyncio
async def test_model_configuration_audit_never_exposes_credentials(monkeypatch):
    context = make_context()

    def provider(_model):
        return {
            "provider": "openai",
            "backend_url": "https://example.invalid/v1",
            "api_key": "secret-value",
        }

    def config(_model):
        return {"temperature": 0.2, "max_tokens": 1200, "timeout": 30}

    monkeypatch.setattr(
        "app.services.simple_analysis_service."
        "get_provider_and_url_by_model_sync",
        provider,
    )
    monkeypatch.setattr(
        "app.services.simple_analysis_service.get_model_config_sync",
        config,
    )
    status = (
        await ExistingProviderDecisionModelRunner.configuration_status(
            context
        )
    )
    assert status["normal"]["credential_configured"] is True
    assert status["normal"]["model_registry_configured"] is True
    assert status["normal"]["status"] == "CONFIGURED"
    assert status["top"]["structured_output_capability"] is True
    assert "api_key" not in status["normal"]
    assert "secret-value" not in str(status)


@pytest.mark.asyncio
async def test_unregistered_default_model_is_not_reported_as_configured(
    monkeypatch,
):
    context = make_context()

    monkeypatch.setattr(
        "app.services.simple_analysis_service."
        "get_provider_and_url_by_model_sync",
        lambda _model: {
            "provider": "openai",
            "backend_url": "https://example.invalid/v1",
            "api_key": "placeholder-or-stale-value",
        },
    )
    monkeypatch.setattr(
        "app.services.simple_analysis_service.get_model_config_sync",
        lambda _model: {},
    )

    status = (
        await ExistingProviderDecisionModelRunner.configuration_status(
            context
        )
    )
    for item in status.values():
        assert item["model_registry_configured"] is False
        assert item["configuration_source"] == (
            "DEFAULT_FALLBACK_UNREGISTERED"
        )
        assert item["credential_configured"] is False
        assert item["backend_configured"] is False
        assert item["structured_output_capability"] is False
        assert item["status"] == "MODEL_NOT_CONFIGURED"


@pytest.mark.asyncio
async def test_model_validation_stops_before_runner_when_unconfigured(
    monkeypatch,
):
    db = FakeDB()
    service = ProductionReprocessService(db)
    context = make_context()

    async def build(*_args, **_kwargs):
        return context, SimpleNamespace()

    async def status(_context):
        return {
            role: {
                "credential_configured": False,
                "backend_configured": False,
                "status": "MODEL_NOT_CONFIGURED",
            }
            for role in ("normal", "top")
        }

    async def forbidden_create(_context):
        raise AssertionError("unconfigured model runner must not be created")

    monkeypatch.setattr(service.contexts, "build", build)
    monkeypatch.setattr(
        ExistingProviderDecisionModelRunner,
        "configuration_status",
        status,
    )
    monkeypatch.setattr(
        ExistingProviderDecisionModelRunner,
        "create",
        forbidden_create,
    )
    result = await service._model_validation(
        user_id=context.user_id,
        proposals=[context.quant_proposal],
        account={"account_id": "paper-account"},
        call_real_model=True,
        trace_id="trace",
    )
    assert result["status"] == "MODEL_NOT_CONFIGURED"
    assert result["normal"] is None
    assert result["top"] is None
    assert result["consensus"] is None
    assert result["hard_risk"] is None


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "your-api-key",
        "your_openai_api_key_here",
        "replace-me",
        "placeholder",
    ],
)
def test_model_credential_placeholders_are_not_configured(value):
    assert (
        ExistingProviderDecisionModelRunner
        ._credential_looks_configured(value)
        is False
    )


def test_reprocess_identity_and_frontend_mode_mapping_are_stable():
    payload_hash = "a" * 64
    first = ProductionReprocessService._stable_id("snapshot", payload_hash)
    second = ProductionReprocessService._stable_id("snapshot", payload_hash)
    assert first == second

    root = Path(__file__).resolve().parents[3]
    source = (
        root / "frontend/src/views/AlphaGuard/Decisions.vue"
    ).read_text(encoding="utf-8")
    for marker in (
        "ACTUAL_PRODUCTION",
        "PRODUCTION_REPROCESS",
        "RESEARCH_BACKFILL",
        "UI_DEMO",
        "非当时实时决策",
        "禁止自动执行",
    ):
        assert marker in source
