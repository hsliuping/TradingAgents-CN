from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.services.alphaguard.model_audit_service import sanitize_model_message
from app.services.alphaguard.model_budget_service import BudgetDecision
from app.services.alphaguard.model_budget_service import ModelBudgetService
from app.services.alphaguard.model_capability_service import (
    ModelCapabilityService,
)
from app.services.alphaguard.model_credential_service import (
    CredentialNotConfigured,
    ModelCredentialService,
)
from app.services.alphaguard.model_profile_registry import (
    ModelProfileRegistry,
)
from app.services.alphaguard.model_runtime_config import (
    load_model_runtime_config,
)
from app.services.alphaguard.model_runtime_context import (
    ModelRuntimeContextError,
    build_model_runtime_context,
)
from app.services.alphaguard.prompt_profile_registry import (
    PromptProfileRegistry,
)
from app.services.alphaguard.real_model_validation_service import (
    RealModelValidationService,
)
from app.services.alphaguard.snapshot_research_runtime import (
    RESEARCH_ROLES,
    SnapshotResearchRuntime,
)
from app.services.alphaguard.decision_model_runner import (
    ExistingProviderDecisionModelRunner,
)
from scripts.init_alphaguard_model_runtime_indexes import MODEL_COLLECTIONS
from tests.unit.alphaguard._fakes import FakeDB
from tests.unit.alphaguard.pr005_helpers import make_context, make_plan
from tests.unit.alphaguard.test_structured_nodes import (
    plan_payload,
    review_payload,
)
from tradingagents.agents.managers.risk_manager import create_risk_manager
from tradingagents.agents.trader.trader import create_trader
from tradingagents.alphaguard.decision_schemas import ModelExecutionMeta
from tradingagents.alphaguard.mongo_indexes import ALPHAGUARD_INDEX_SPECS
from tradingagents.alphaguard.structured_output import invoke_json_object


ROOT = Path(__file__).resolve().parents[3]


class RawResponse:
    response_metadata = {
        "request_id": "req-1",
        "token_usage": {
            "prompt_tokens": 11,
            "completion_tokens": 7,
            "total_tokens": 18,
        },
    }


class StructuredLLM:
    model_name = "registered-model"

    def __init__(self, payload=None, error=None):
        self.payload = payload or {
            "status": "READY",
            "note": "structured output available",
        }
        self.error = error
        self.invocations = 0

    def with_structured_output(self, _schema, *, include_raw=False):
        assert include_raw is True
        return self

    def invoke(self, _messages):
        self.invocations += 1
        if self.error:
            raise self.error
        return {
            "raw": RawResponse(),
            "parsed": self.payload,
            "parsing_error": None,
        }


class UnauthorizedError(RuntimeError):
    status_code = 401


class TransientThenReadyLLM(StructuredLLM):
    def invoke(self, messages):
        self.invocations += 1
        if self.invocations == 1:
            raise TimeoutError("temporary provider timeout")
        return {
            "raw": RawResponse(),
            "parsed": self.payload,
            "parsing_error": None,
        }


class NoStructuredOutputLLM:
    model_name = "unstructured-only"

    def __init__(self):
        self.invocations = 0

    def invoke(self, _messages):
        self.invocations += 1
        return {"status": "READY", "note": "must not be called"}


class ToolResponse:
    tool_calls = [
        {
            "name": "SimpleCapabilitySchema",
            "args": {
                "status": "READY",
                "note": "tool output available",
            },
        }
    ]
    usage_metadata = {
        "input_tokens": 4,
        "output_tokens": 3,
        "total_tokens": 7,
    }


class ToolCallLLM:
    model_name = "tool-model"

    def __init__(self):
        self.invocations = 0
        self.binding = None

    def bind_tools(self, schemas, *, tool_choice):
        self.binding = (schemas, tool_choice)
        return self

    def invoke(self, _messages):
        self.invocations += 1
        return ToolResponse()


class JsonSchemaLLM:
    model_name = "json-model"

    def __init__(self):
        self.messages = None

    def invoke(self, messages):
        self.messages = messages
        return '{"status":"READY","note":"strict json available"}'


@pytest.mark.asyncio
async def test_profile_and_prompt_registries_are_exact_create_only():
    db = FakeDB()
    config = load_model_runtime_config()
    assert {
        item.role for item in config["profiles"]
    } == {"RESEARCH_AGENT", "NORMAL_TRADER", "TOP_RISK_REVIEWER"}
    assert all(item.model_name for item in config["profiles"])
    assert all(item.profile_version == "v1" for item in config["profiles"])
    profiles = ModelProfileRegistry(db)
    prompts = PromptProfileRegistry(db)
    first_profiles = await profiles.seed()
    first_prompts = await prompts.seed()
    second_profiles = await profiles.seed()
    second_prompts = await prompts.seed()
    assert first_profiles == {"created": 3, "reused": 0}
    assert second_profiles == {"created": 0, "reused": 3}
    assert first_prompts["created"] == len(config["prompts"])
    assert second_prompts["reused"] == len(config["prompts"])
    assert profiles.for_role("NORMAL_TRADER").profile_id != (
        profiles.for_role("TOP_RISK_REVIEWER").profile_id
    )
    with pytest.raises(LookupError):
        profiles.definition("unknown-profile", "latest")


@pytest.mark.asyncio
async def test_legacy_default_model_construction_is_disabled():
    with pytest.raises(RuntimeError, match="legacy default-model"):
        await ExistingProviderDecisionModelRunner.create(SimpleNamespace())
    normal, top = ExistingProviderDecisionModelRunner.configured_models(
        SimpleNamespace()
    )
    assert (normal, top) == ("gpt-4o-mini", "o4-mini")


def test_credentials_are_reference_only_and_errors_are_redacted(monkeypatch):
    monkeypatch.delenv("ALPHAGUARD_PR010_MISSING_KEY", raising=False)
    service = ModelCredentialService()
    assert service.configured("env:ALPHAGUARD_PR010_MISSING_KEY") is False
    with pytest.raises(CredentialNotConfigured):
        service.resolve("env:ALPHAGUARD_PR010_MISSING_KEY")
    text = sanitize_model_message(
        "Authorization: Bearer sk-super-secret api_key=hidden-value"
    )
    assert "super-secret" not in text
    assert "hidden-value" not in text


def test_strict_native_schema_audits_tokens_cost_and_401():
    successful = invoke_json_object(
        llm=StructuredLLM(),
        messages=[],
        schema_model=SimpleCapabilitySchema,
        provider="openai",
        configured_model_name="registered-model",
        prompt_name="capability",
        prompt_version="v1",
        structured_output_mode="NATIVE_SCHEMA",
        model_profile_id="profile",
        model_profile_version="v1",
        prompt_id="capability",
        input_cost_per_million=1.0,
        output_cost_per_million=2.0,
    )
    assert successful.failure_status is None
    assert successful.model_meta.input_tokens == 11
    assert successful.model_meta.output_tokens == 7
    assert successful.model_meta.total_tokens == 18
    assert successful.model_meta.estimated_cost == pytest.approx(0.000025)

    failed = invoke_json_object(
        llm=StructuredLLM(error=UnauthorizedError("api_key=secret")),
        messages=[],
        schema_model=SimpleCapabilitySchema,
        provider="openai",
        configured_model_name="registered-model",
        prompt_name="capability",
        prompt_version="v1",
        structured_output_mode="NATIVE_SCHEMA",
    )
    assert failed.failure_status == "MODEL_FAILED"
    assert failed.error_type == "UNAUTHORIZED"
    assert "secret" not in (failed.error_message or "")
    assert len(failed.attempt_metas) == 1

    unsupported_model = NoStructuredOutputLLM()
    unsupported = invoke_json_object(
        llm=unsupported_model,
        messages=[],
        schema_model=SimpleCapabilitySchema,
        provider="openai",
        configured_model_name="unstructured-only",
        prompt_name="capability",
        prompt_version="v1",
        structured_output_mode="NATIVE_SCHEMA",
    )
    assert unsupported.error_type == "STRUCTURED_OUTPUT_UNSUPPORTED"
    assert unsupported_model.invocations == 0


def test_only_transient_errors_retry_and_every_attempt_is_exposed():
    transient = TransientThenReadyLLM()
    result = invoke_json_object(
        llm=transient,
        messages=[],
        schema_model=SimpleCapabilitySchema,
        provider="openai",
        configured_model_name="registered-model",
        prompt_name="capability",
        prompt_version="v1",
        structured_output_mode="NATIVE_SCHEMA",
        max_retries=1,
        retry_backoff_seconds=0,
    )
    assert result.failure_status is None
    assert transient.invocations == 2
    assert [item.attempt_number for item in result.attempt_metas] == [1, 2]
    assert [item.error_type for item in result.attempt_metas] == [
        "TIMEOUT",
        None,
    ]

    unauthorized = StructuredLLM(error=UnauthorizedError("unauthorized"))
    blocked = invoke_json_object(
        llm=unauthorized,
        messages=[],
        schema_model=SimpleCapabilitySchema,
        provider="openai",
        configured_model_name="registered-model",
        prompt_name="capability",
        prompt_version="v1",
        structured_output_mode="NATIVE_SCHEMA",
        max_retries=3,
        retry_backoff_seconds=0,
    )
    assert blocked.error_type == "UNAUTHORIZED"
    assert unauthorized.invocations == 1
    assert len(blocked.attempt_metas) == 1


def test_tool_call_and_json_schema_modes_are_real_and_audited():
    tool_llm = ToolCallLLM()
    tool = invoke_json_object(
        llm=tool_llm,
        messages=[{"role": "system", "content": "capability"}],
        schema_model=SimpleCapabilitySchema,
        provider="test",
        configured_model_name="tool-model",
        prompt_name="capability",
        prompt_version="v1",
        structured_output_mode="TOOL_CALL",
    )
    assert tool.failure_status is None
    assert tool.payload == {
        "status": "READY",
        "note": "tool output available",
    }
    assert tool.model_meta.structured_output_mode == "TOOL_CALL"
    assert tool_llm.binding is not None
    assert tool_llm.invocations == 1

    json_llm = JsonSchemaLLM()
    strict_json = invoke_json_object(
        llm=json_llm,
        messages=[{"role": "system", "content": "capability"}],
        schema_model=SimpleCapabilitySchema,
        provider="test",
        configured_model_name="json-model",
        prompt_name="capability",
        prompt_version="v1",
        structured_output_mode="JSON_SCHEMA",
    )
    assert strict_json.failure_status is None
    assert strict_json.model_meta.structured_output_mode == "JSON_SCHEMA"
    assert "Return exactly one JSON object" in json_llm.messages[0]["content"]
    assert '"status"' in json_llm.messages[0]["content"]


class SimpleCapabilitySchema(SimpleNamespace):
    @classmethod
    def model_json_schema(cls):
        return {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "note": {"type": "string"},
            },
        }


@pytest.mark.asyncio
async def test_missing_credential_capability_is_fail_closed(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    db = FakeDB()
    await ModelProfileRegistry(db).seed()
    await PromptProfileRegistry(db).seed()
    result = await ModelCapabilityService(db).check(
        profile_id="alphaguard_normal_openai",
        profile_version="v1",
        checked_by="admin",
        idempotency_key="missing-credential",
        network=True,
    )
    assert result.status == "NOT_CONFIGURED"
    assert result.credential_status == "NOT_CONFIGURED"
    assert result.checked_network is True
    assert db["ag_model_runs"].count() == 0
    assert "OPENAI_API_KEY" not in str(result.model_dump())


@pytest.mark.asyncio
async def test_validation_is_idempotent_and_never_writes_trade_objects(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    db = FakeDB()
    await ModelProfileRegistry(db).seed()
    await PromptProfileRegistry(db).seed()
    service = RealModelValidationService(db)
    first = await service.run(
        requested_by="admin",
        idempotency_key="validation-no-credential",
    )
    second = await service.run(
        requested_by="admin",
        idempotency_key="validation-no-credential",
    )
    assert first.validation_run_id == second.validation_run_id
    assert first.status == "MODEL_NOT_CONFIGURED"
    assert first.execution_gate_status == "BLOCKED_VALIDATION_MODE"
    assert db["ag_model_validation_runs"].count() == 1
    for collection in (
        "ag_order_intents",
        "ag_execution_outbox",
        "ag_paper_orders",
        "ag_paper_fills",
        "ag_paper_positions",
        "ag_paper_reservations",
        "ag_paper_ledgers",
    ):
        assert db[collection].count() == 0


@pytest.mark.asyncio
async def test_unpriced_profile_is_budget_blocked_without_truncation():
    db = FakeDB()
    profile = ModelProfileRegistry().for_role("NORMAL_TRADER")
    decision = await ModelBudgetService(db).check(
        profile=profile,
        analysis_id="analysis-budget",
        snapshot_id="snapshot-budget",
        rendered_input="complete immutable context",
    )
    assert decision.allowed is False
    assert decision.status == "BUDGET_BLOCKED"
    assert decision.reason_code == "BUDGET_PRICING_UNAVAILABLE"
    assert decision.estimated_cost is None


@pytest.mark.asyncio
async def test_budget_caps_retry_attempts_before_the_analysis_limit():
    db = FakeDB()
    profile = ModelProfileRegistry().for_role("NORMAL_TRADER").model_copy(
        update={
            "input_cost_per_million": 1.0,
            "output_cost_per_million": 1.0,
        }
    )
    for index in range(9):
        await db["ag_model_runs"].insert_one(
            {
                "analysis_id": "analysis-budget-cap",
                "snapshot_id": "snapshot-budget-cap",
                "created_at": datetime.now(timezone.utc),
                "total_tokens": 1,
                "estimated_cost": 0.000001,
                "attempt": index + 1,
            }
        )
    decision = await ModelBudgetService(db).check(
        profile=profile,
        analysis_id="analysis-budget-cap",
        snapshot_id="snapshot-budget-cap",
        rendered_input="complete immutable context",
    )
    assert decision.allowed is True
    assert decision.permitted_attempts == 1


def _runtime_context(schema_version="evidence-snapshot-v2"):
    snapshot = SimpleNamespace(
        snapshot_id="snapshot-v2",
        schema_version=schema_version,
        evidence_contract_status="COMPLETE",
        benchmark_price_window_manifest_id="benchmark-manifest",
        benchmark_price_window_manifest_hash="a" * 64,
        market_context_window_manifest_id="context-manifest",
        market_context_window_manifest_hash="b" * 64,
        required_benchmark_count=61,
        actual_benchmark_count=61,
        market_context_id="market-context",
        market_context_hash="c" * 64,
        immutable_hash="d" * 64,
    )
    context = SimpleNamespace(
        snapshot_id="snapshot-v2",
        model_dump=lambda mode: {"snapshot_id": "snapshot-v2", "value": 1},
    )
    resolved = SimpleNamespace(
        snapshot=snapshot,
        input_hash="e" * 64,
        input_refs=["price:1", "financial:1"],
    )
    return context, resolved


def test_model_context_is_snapshot_v2_only_and_hash_stable():
    context, resolved = _runtime_context()
    first = build_model_runtime_context(context, resolved)
    second = build_model_runtime_context(context, resolved)
    assert first.context_hash == second.context_hash
    assert first.evidence_refs == ("financial:1", "price:1")
    legacy_context, legacy = _runtime_context("evidence-snapshot-v1")
    with pytest.raises(ModelRuntimeContextError, match="Snapshot v2"):
        build_model_runtime_context(legacy_context, legacy)


@pytest.mark.asyncio
async def test_research_agents_share_snapshot_and_never_query_latest(monkeypatch):
    db = FakeDB()
    await ModelProfileRegistry(db).seed()
    await PromptProfileRegistry(db).seed()
    model = StructuredLLM(
        {
            "status": "SUCCESS",
            "summary": "snapshot-bound finding",
            "findings": ["evidence is internally consistent"],
            "risks": [],
            "evidence_refs": ["price:1"],
        }
    )
    runtime = SnapshotResearchRuntime(db)

    async def allowed(**_kwargs):
        return BudgetDecision(
            allowed=True,
            status="READY",
            estimated_input_tokens=10,
            estimated_output_tokens=10,
            estimated_cost=0.001,
            remaining_daily_calls=99,
            remaining_daily_cost=19.999,
            permitted_attempts=2,
        )

    monkeypatch.setattr(runtime.budget, "check", allowed)
    context = SimpleNamespace(
        snapshot_id="snapshot-v2",
        context_hash="f" * 64,
        payload={"snapshot_id": "snapshot-v2"},
        evidence_refs=("price:1",),
    )
    results = await runtime.run(
        analysis_id="analysis-1",
        context=context,
        run_mode="REAL_MODEL_VALIDATION",
        llm=model,
    )
    assert len(results) == len(RESEARCH_ROLES)
    assert model.invocations == len(RESEARCH_ROLES)
    assert {item.snapshot_id for item in results} == {"snapshot-v2"}
    assert {item.context_hash for item in results} == {"f" * 64}
    assert db["stock_daily_quotes"].count() == 0


@pytest.mark.asyncio
async def test_research_retry_attempts_are_each_audited(monkeypatch):
    db = FakeDB()
    await ModelProfileRegistry(db).seed()
    await PromptProfileRegistry(db).seed()
    model = TransientThenReadyLLM(
        {
            "status": "SUCCESS",
            "summary": "snapshot-bound finding",
            "findings": ["evidence is internally consistent"],
            "risks": [],
            "evidence_refs": ["price:1"],
        }
    )
    runtime = SnapshotResearchRuntime(db)

    async def allowed(**_kwargs):
        return BudgetDecision(
            allowed=True,
            status="READY",
            estimated_input_tokens=10,
            estimated_output_tokens=10,
            estimated_cost=0.001,
            remaining_daily_calls=99,
            remaining_daily_cost=19.999,
            permitted_attempts=2,
        )

    monkeypatch.setattr(runtime.budget, "check", allowed)
    monkeypatch.setattr(
        "tradingagents.alphaguard.structured_output.time.sleep",
        lambda _delay: None,
    )
    context = SimpleNamespace(
        snapshot_id="snapshot-v2",
        context_hash="f" * 64,
        payload={"snapshot_id": "snapshot-v2"},
        evidence_refs=("price:1",),
    )
    results = await runtime.run(
        analysis_id="analysis-retry",
        context=context,
        run_mode="REAL_MODEL_VALIDATION",
        llm=model,
    )
    assert len(results) == len(RESEARCH_ROLES)
    assert model.invocations == len(RESEARCH_ROLES) + 1
    assert db["ag_model_runs"].count() == len(RESEARCH_ROLES) + 1
    attempts = sorted(
        (
            item["agent_name"],
            item["attempt"],
            item["structured_output_status"],
        )
        for item in db["ag_model_runs"].documents
    )
    assert ("market_analyst", 1, "MODEL_FAILED") in attempts
    assert ("market_analyst", 2, "SUCCESS") in attempts


def test_normal_and_top_use_the_unified_snapshot_runtime_context_hash():
    context = make_context()
    runtime_hash = "9" * 64
    normal_payload = plan_payload(
        entry_zone={"lower": 99, "upper": 101, "currency": "CNY"},
        initial_position_pct=0.05,
        max_position_pct=0.10,
        valid_until="2030-07-03T00:00:00Z",
    )
    normal_result = create_trader(
        StructuredLLM(normal_payload),
        None,
        {
            "quick_provider": "openai",
            "quick_think_llm": "registered-model",
            "normal_structured_output_mode": "NATIVE_SCHEMA",
        },
    )(
        {
            "analysis_id": context.analysis_id,
            "snapshot_id": context.snapshot_id,
            "market": context.market,
            "decision_context": context.model_dump(mode="json"),
            "quant_trade_proposal": context.quant_proposal.model_dump(mode="json"),
            "model_runtime_context_hash": runtime_hash,
            "tradingagents_research": [],
        }
    )
    assert normal_result["normal_model_meta"]["context_hash"] == runtime_hash

    plan = make_plan(context)
    top_result = create_risk_manager(
        StructuredLLM(review_payload()),
        None,
        {
            "deep_provider": "openai",
            "deep_think_llm": "registered-model",
            "top_structured_output_mode": "NATIVE_SCHEMA",
        },
    )(
        {
            "analysis_id": context.analysis_id,
            "snapshot_id": context.snapshot_id,
            "market": context.market,
            "decision_context": context.model_dump(mode="json"),
            "quant_trade_proposal": context.quant_proposal.model_dump(mode="json"),
            "normal_trade_plan": plan.model_dump(mode="json"),
            "risk_policy_summary": {},
            "risk_debate_state": {},
            "model_runtime_context_hash": runtime_hash,
            "tradingagents_research": [],
        }
    )
    assert top_result["top_model_meta"]["context_hash"] == runtime_hash


def test_model_indexes_frontend_modes_and_secret_boundary():
    assert set(MODEL_COLLECTIONS) == {
        name for name in ALPHAGUARD_INDEX_SPECS if name.startswith("ag_model_")
    }
    assert all(ALPHAGUARD_INDEX_SPECS[name] for name in MODEL_COLLECTIONS)
    operations = (
        ROOT / "frontend/src/views/AlphaGuard/Operations.vue"
    ).read_text(encoding="utf-8")
    decisions = (
        ROOT / "frontend/src/views/AlphaGuard/Decisions.vue"
    ).read_text(encoding="utf-8")
    router = (
        ROOT / "app/routers/alphaguard_models.py"
    ).read_text(encoding="utf-8")
    for marker in (
        "MODEL_CAPABILITY_CHECK",
        "REAL_MODEL_VALIDATION",
        "PRODUCTION",
        "PRODUCTION_REPROCESS",
        "RESEARCH_REPLAY",
        "DEMO",
    ):
        assert marker in (
            ROOT / "tradingagents/alphaguard/model_runtime_schemas.py"
        ).read_text(encoding="utf-8")
    assert "TradingAgents 研究" in decisions
    assert "模型运行" in operations
    assert "credential_ref" not in router
    assert "api_key" not in router.lower()


def test_model_api_is_authenticated_admin_controlled_and_strict(monkeypatch):
    import app.routers.alphaguard_models as models_router
    from app.routers.auth_db import get_current_user

    db = FakeDB()
    monkeypatch.setattr(models_router, "get_mongo_db", lambda: db)
    app = FastAPI()
    app.include_router(models_router.router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "ordinary",
        "is_admin": False,
    }
    client = TestClient(app)
    response = client.get("/api/alphaguard/models/status")
    assert response.status_code == 200
    assert "credential_ref" not in response.text
    assert "api_key" not in response.text.lower()
    blocked = client.post(
        "/api/alphaguard/models/capability-check",
        json={
            "profile_id": "alphaguard_normal_openai",
            "profile_version": "v1",
            "idempotency_key": "fixed-api-key",
            "network": False,
        },
    )
    assert blocked.status_code == 403

    app.dependency_overrides[get_current_user] = lambda: {
        "id": "admin",
        "is_admin": True,
    }
    invalid = client.post(
        "/api/alphaguard/models/capability-check",
        json={
            "profile_id": "alphaguard_normal_openai",
            "profile_version": "v1",
            "idempotency_key": "fixed-api-key",
            "network": False,
            "prompt": "attacker supplied",
        },
    )
    assert invalid.status_code == 422
    wrong_confirmation = client.post(
        "/api/alphaguard/models/validation-run",
        json={
            "idempotency_key": "validation-api-key",
            "confirmation_text": "RUN IT",
        },
    )
    assert wrong_confirmation.status_code == 400
