from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.services.alphaguard.model_audit_service import (
    ModelAuditService,
    sanitize_model_message,
)
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
from app.services.alphaguard.profiled_decision_model_runner import (
    ProfiledDecisionModelRunner,
)
from app.services.alphaguard.model_runtime_config import (
    load_model_runtime_config,
)
from app.services.alphaguard.model_runtime_context import (
    ModelRuntimeContextError,
    build_model_runtime_context,
)
from app.services.alphaguard.model_runtime_status_service import (
    ModelRuntimeStatusService,
    capability_failure_summary,
    project_capability_check,
)
from app.services.alphaguard.prompt_profile_registry import (
    PromptProfileRegistry,
)
from app.services.alphaguard.real_model_validation_service import (
    SAMPLE_SELECTION_VERSION,
    VALIDATION_CONTRACT_VERSION,
    RealModelValidationService,
    _decision_research_projection,
    _frozen_snapshot_prompt_version,
    _sample_order_key,
)
from app.services.alphaguard.research_manager_contract_service import (
    CAPABILITY_EVIDENCE_REF,
    ResearchManagerContractService,
)
from app.services.alphaguard.snapshot_research_runtime import (
    RESEARCH_ROLES,
    RESEARCH_MANAGER_CONTRACT_ID,
    RESEARCH_MANAGER_CONTRACT_VERSION,
    RESEARCH_MANAGER_SCHEMA_HASH,
    ResearchManagerOutputV2,
    SnapshotResearchRuntime,
    _context_bound_research_schema,
    normalized_payload_shape,
    validation_error_projection,
)
from app.services.alphaguard.decision_model_runner import (
    ExistingProviderDecisionModelRunner,
)
from app.services.alphaguard.consensus_engine import ConsensusEngine
from app.services.alphaguard.decision_validation import (
    validate_plan_against_context,
)
from scripts.init_alphaguard_model_runtime_indexes import MODEL_COLLECTIONS
from tests.unit.alphaguard._fakes import FakeDB
from tests.unit.alphaguard.pr005_helpers import make_context, make_plan
from tests.unit.alphaguard.test_structured_nodes import (
    plan_payload,
    review_payload,
)
from tradingagents.agents.managers.risk_manager import (
    _context_bound_review_schema,
    build_top_review_model_request,
    create_risk_manager,
)
from tradingagents.agents.utils.instrument_utils import build_instrument_context
from tradingagents.agents.trader.trader import (
    _context_bound_plan_schema,
    _validation_failure_detail,
    create_trader,
)
from tradingagents.alphaguard.decision_schemas import (
    ModelExecutionMeta,
    NormalTradePlan,
    TopModelDecisionOutput,
    TopReviewDecision,
)
from tradingagents.alphaguard.mongo_indexes import ALPHAGUARD_INDEX_SPECS
from tradingagents.alphaguard.structured_output import (
    _classify_provider_error,
    invoke_json_object,
    render_structured_input_for_estimation,
)


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
        self.messages = None

    def with_structured_output(self, _schema, *, include_raw=False):
        assert include_raw is True
        return self

    def invoke(self, _messages):
        self.invocations += 1
        self.messages = _messages
        if self.error:
            raise self.error
        return {
            "raw": RawResponse(),
            "parsed": self.payload,
            "parsing_error": None,
        }


class CompatibleMessageEnvelopeLLM(StructuredLLM):
    def invoke(self, _messages):
        self.invocations += 1
        return {
            "raw": RawResponse(),
            "parsed": {
                "content": '{"status":"READY","note":"compatible envelope"}',
                "additional_kwargs": {},
                "response_metadata": {},
                "type": "ai",
                "usage_metadata": {
                    "input_tokens": 11,
                    "output_tokens": 7,
                    "total_tokens": 18,
                },
            },
            "parsing_error": None,
        }


class UnauthorizedError(RuntimeError):
    status_code = 401


class ProviderQuotaError(RuntimeError):
    status_code = 403


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
    assert all(item.profile_version == "v2" for item in config["profiles"])
    assert all(
        item.credential_ref == "keychain-alias:openai-primary"
        for item in config["profiles"]
    )
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
async def test_decision_status_is_independent_from_research_profile():
    db = FakeDB()
    profiles = ModelProfileRegistry(db)
    prompts = PromptProfileRegistry(db)
    await profiles.seed()
    await prompts.seed()
    research = profiles.for_role("RESEARCH_AGENT")
    await db["ag_model_profiles"].delete_one(
        {
            "profile_id": research.profile_id,
            "profile_version": research.profile_version,
        }
    )
    for role in ("NORMAL_TRADER", "TOP_RISK_REVIEWER"):
        profile = profiles.for_role(role)
        await db["ag_model_capability_checks"].insert_one(
            {
                "profile_id": profile.profile_id,
                "profile_version": profile.profile_version,
                "status": "READY",
                "checked_at": datetime.now(timezone.utc),
            }
        )

    service = ModelRuntimeStatusService(db)
    service.credentials = SimpleNamespace(configured=lambda _ref: True)
    result = await service.status(admin=False)

    assert result["status"] == "NOT_CONFIGURED"
    assert result["decision_status"] == "READY"
    assert result["research_status"] == "NOT_CONFIGURED"
    by_role = {item["role"]: item for item in result["profiles"]}
    assert by_role["NORMAL_TRADER"]["configured"] is True
    assert by_role["TOP_RISK_REVIEWER"]["configured"] is True
    assert by_role["RESEARCH_AGENT"]["configured"] is False


def test_capability_checks_use_exact_role_decision_contracts():
    profiles = ModelProfileRegistry()
    normal_prompt, normal_schema = ModelCapabilityService._capability_contract(
        profiles.for_role("NORMAL_TRADER")
    )
    top_prompt, top_schema = ModelCapabilityService._capability_contract(
        profiles.for_role("TOP_RISK_REVIEWER")
    )
    assert normal_prompt == "normal_trade_plan_capability_prompt"
    assert normal_schema is NormalTradePlan
    assert top_prompt == "top_review_capability_prompt"
    assert top_schema is TopModelDecisionOutput


def test_top_model_payload_is_strict_and_has_no_server_identity_fields():
    valid = review_payload()
    decision = TopModelDecisionOutput.model_validate(valid)
    assert decision.status == "CONFIRM"
    assert decision.proposed_changes.model_fields_set == set()

    for forbidden in ("plan_id", "supersedes_plan_id", "unknown_field"):
        with pytest.raises(ValidationError) as captured:
            TopModelDecisionOutput.model_validate(
                {**valid, forbidden: "model-must-not-own-this"}
            )
        assert captured.value.errors(include_input=False)[0]["loc"] == (forbidden,)
        assert captured.value.errors(include_input=False)[0]["type"] == (
            "extra_forbidden"
        )

    with pytest.raises(ValidationError) as captured:
        TopModelDecisionOutput.model_validate(
            {**valid, "proposed_changes": {"plan_id": "forbidden"}}
        )
    assert captured.value.errors(include_input=False)[0]["loc"] == (
        "proposed_changes",
        "plan_id",
    )


def test_top_server_envelope_binds_plan_lineage_and_replays_completely():
    context = make_context()
    plan_payload_data = make_plan(context).model_dump(mode="python")
    plan_payload_data.update(
        revision_round=1,
        supersedes_plan_id="server-owned-original-plan",
        revision_request_id="server-owned-revision-request",
    )
    plan = NormalTradePlan.model_validate(plan_payload_data)
    state = ProfiledDecisionModelRunner._base_state(
        context,
        attempt_number=1,
        trace_id="validation-v13-envelope",
        research_results=[],
        model_runtime_context_hash="8" * 64,
        run_mode="REAL_MODEL_VALIDATION",
    )
    state["normal_trade_plan"] = plan.model_dump(mode="json")
    state["risk_policy_summary"] = {}
    result = create_risk_manager(
        StructuredLLM(review_payload()),
        None,
        {
            "deep_provider": "compatible",
            "deep_think_llm": "top-model",
            "top_structured_output_mode": "NATIVE_SCHEMA",
        },
    )(state)
    review = TopReviewDecision.model_validate(result["top_review_decision"])
    assert review.status == "CONFIRM"
    assert review.plan_id == plan.plan_id
    assert review.supersedes_plan_id == "server-owned-original-plan"
    assert review.validation_run_id == "validation-v13-envelope"
    assert review.schema_version == "top_review_decision_v2"
    assert review.model_payload_schema_version == "top_model_decision_output_v1"
    assert review.model_decision_payload == TopModelDecisionOutput.model_validate(
        review_payload()
    )
    assert review.model_meta.input_hash
    assert review.model_meta.raw_output_hash
    assert review.model_meta.request_id == "req-1"
    assert TopReviewDecision.model_validate(
        review.model_dump(mode="json")
    ) == review


@pytest.mark.parametrize(
    "forbidden_payload",
    [
        {"plan_id": "model-plan"},
        {"supersedes_plan_id": "model-parent"},
        {"unknown_field": "unknown"},
        {"proposed_changes": {"plan_id": "nested-model-plan"}},
    ],
)
def test_top_node_never_strips_or_repairs_forbidden_model_fields(
    forbidden_payload,
):
    context = make_context()
    plan = make_plan(context)
    payload = review_payload()
    payload.update(forbidden_payload)
    state = ProfiledDecisionModelRunner._base_state(
        context,
        attempt_number=1,
        trace_id="validation-v13-forbidden",
        research_results=[],
        model_runtime_context_hash="8" * 64,
        run_mode="REAL_MODEL_VALIDATION",
    )
    state["normal_trade_plan"] = plan.model_dump(mode="json")
    state["risk_policy_summary"] = {}
    result = create_risk_manager(
        StructuredLLM(payload),
        None,
        {
            "deep_provider": "compatible",
            "deep_think_llm": "top-model",
            "top_structured_output_mode": "NATIVE_SCHEMA",
        },
    )(state)

    assert result["top_review_decision"]["status"] == "INVALID_OUTPUT"
    assert result["decision_error"]["error_type"] == "SCHEMA_VALIDATION_ERROR"
    assert "extra_forbidden" in result["decision_error"]["error_message"]
    expected_field = next(iter(forbidden_payload))
    assert expected_field in result["decision_error"]["error_message"]
    review = TopReviewDecision.model_validate(result["top_review_decision"])
    assert expected_field in review.standardized_model_payload
    assert review.standardized_model_payload_hash
    assert review.validation_errors[0].stage == "PYDANTIC_FIELD"
    assert review.validation_errors[0].error_type == "extra_forbidden"
    assert expected_field in review.validation_errors[0].path


def test_top_semantic_failure_keeps_static_rule_without_model_text():
    context = make_context()
    plan = make_plan(context)
    secret_text = "MODEL-OUTPUT-MUST-NOT-BE-PERSISTED"
    payload = review_payload(
        review_reason=secret_text,
        proposed_changes={"confidence": 0.5},
    )
    state = ProfiledDecisionModelRunner._base_state(
        context,
        attempt_number=1,
        trace_id="validation-v13-semantic-error",
        research_results=[],
        model_runtime_context_hash="8" * 64,
        run_mode="REAL_MODEL_VALIDATION",
    )
    state["normal_trade_plan"] = plan.model_dump(mode="json")
    state["risk_policy_summary"] = {}
    result = create_risk_manager(
        StructuredLLM(payload),
        None,
        {
            "deep_provider": "compatible",
            "deep_think_llm": "top-model",
            "top_structured_output_mode": "NATIVE_SCHEMA",
        },
    )(state)
    message = result["decision_error"]["error_message"]
    assert "CONFIRM requires empty proposed_changes" in message
    assert secret_text not in message
    review = TopReviewDecision.model_validate(result["top_review_decision"])
    assert review.standardized_model_payload["review_reason"] == secret_text
    assert review.validation_errors[0].stage == "BUSINESS_SEMANTIC"
    assert review.validation_errors[0].path == "$"
    assert review.validation_errors[0].error_type == "value_error"
    assert (
        review.validation_errors[0].message
        == "Value error, CONFIRM requires empty proposed_changes"
    )


def test_top_standardized_payload_redacts_secret_values_without_field_stripping():
    context = make_context()
    plan = make_plan(context)
    payload = review_payload()
    payload["api_key"] = "sk-" + "x" * 32
    state = ProfiledDecisionModelRunner._base_state(
        context,
        attempt_number=1,
        trace_id="validation-top-redaction",
        research_results=[],
        model_runtime_context_hash="8" * 64,
        run_mode="REAL_MODEL_VALIDATION",
    )
    state["normal_trade_plan"] = plan.model_dump(mode="json")
    state["risk_policy_summary"] = {}

    result = create_risk_manager(
        StructuredLLM(payload),
        None,
        {
            "deep_provider": "compatible",
            "deep_think_llm": "top-model",
            "top_structured_output_mode": "NATIVE_SCHEMA",
        },
    )(state)
    review = TopReviewDecision.model_validate(result["top_review_decision"])

    assert review.status == "INVALID_OUTPUT"
    assert review.standardized_model_payload["api_key"] == "[REDACTED]"
    assert review.validation_errors[0].path == "api_key"
    assert review.validation_errors[0].error_type == "extra_forbidden"
    assert "x" * 16 not in json.dumps(review.model_dump(mode="json"))


def test_top_prompt_schema_and_pydantic_semantics_are_consistent():
    prompt = PromptProfileRegistry().definition("top_risk_review_prompt")
    context = make_context()
    schema = _context_bound_review_schema(context, make_plan(context))
    schema_text = json.dumps(schema, sort_keys=True)

    assert prompt.prompt_version == "alphaguard-top-review-v3"
    assert prompt.schema_target == "TopModelDecisionOutput"
    assert "plan_id" not in schema_text
    assert "supersedes_plan_id" not in schema_text
    prompt_text = " ".join(prompt.template.split())
    for rule in (
        "CONFIRM, REJECT, and SUSPEND require proposed_changes {{}}",
        "RISK_ADJUST requires non-empty proposed_changes",
        "MATERIAL_REVISION requires non-empty proposed_changes",
    ):
        assert rule in prompt_text

    for status in ("CONFIRM", "REJECT", "SUSPEND"):
        assert TopModelDecisionOutput.model_validate(
            review_payload(status=status)
        ).status == status
    assert TopModelDecisionOutput.model_validate(
        review_payload(
            status="RISK_ADJUST",
            proposed_changes={"confidence": 0.5},
        )
    ).status == "RISK_ADJUST"
    assert TopModelDecisionOutput.model_validate(
        review_payload(
            status="MATERIAL_REVISION",
            proposed_changes={"confidence": 0.5},
            material_change_fields=["confidence"],
        )
    ).status == "MATERIAL_REVISION"
    with pytest.raises(
        ValidationError,
        match="material_change_fields must exactly match proposed_changes",
    ):
        TopModelDecisionOutput.model_validate(
            review_payload(
                status="MATERIAL_REVISION",
                proposed_changes={"confidence": 0.5, "max_position_pct": 0.04},
                material_change_fields=["confidence"],
            )
        )


def test_consensus_accepts_only_explicitly_registered_recovery_prompt():
    context = make_context()
    plan = make_plan(context)
    state = ProfiledDecisionModelRunner._base_state(
        context,
        attempt_number=1,
        trace_id="validation-top-prompt-compatibility",
        research_results=[],
        model_runtime_context_hash=plan.model_meta.context_hash,
        run_mode="REAL_MODEL_VALIDATION",
    )
    state["normal_trade_plan"] = plan.model_dump(mode="json")
    state["risk_policy_summary"] = {}
    prompt = PromptProfileRegistry().definition("top_risk_review_prompt")
    result = create_risk_manager(
        StructuredLLM(review_payload()),
        None,
        {
            "deep_provider": "compatible",
            "deep_think_llm": "top-model",
            "top_prompt_version": prompt.prompt_version,
            "top_prompt_template": prompt.template,
            "top_structured_output_mode": "NATIVE_SCHEMA",
        },
    )(state)
    review = TopReviewDecision.model_validate(result["top_review_decision"])
    assert review.model_meta.context_hash == plan.model_meta.context_hash
    assert review.model_meta.prompt_version == prompt.prompt_version
    assert review.model_meta.template_hash
    assert review.model_meta.input_hash
    assert review.model_meta.raw_output_hash
    assert review.model_meta.request_id or review.model_meta.trace_id
    evaluation_time = datetime.combine(
        context.trade_date,
        datetime.min.time(),
        tzinfo=timezone.utc,
    )

    rejected = ConsensusEngine().evaluate(
        context=context,
        plan=plan,
        review=review,
        now=evaluation_time,
    )
    accepted = ConsensusEngine().evaluate(
        context=context,
        plan=plan,
        review=review,
        now=evaluation_time,
        additional_top_prompt_versions={prompt.prompt_version},
    )

    assert rejected.status == "CONSENSUS_INVALID"
    assert rejected.validation_errors == ["model execution metadata is incomplete"]
    assert accepted.status == "CONSENSUS_PASS", accepted.validation_errors
    assert accepted.validation_errors == []


@pytest.mark.asyncio
async def test_top_audit_hashes_link_model_payload_to_server_envelope():
    context = make_context()
    plan = make_plan(context)
    profile = ModelProfileRegistry().for_role("TOP_RISK_REVIEWER")
    prompt = PromptProfileRegistry().definition("top_risk_review_prompt")
    state = ProfiledDecisionModelRunner._base_state(
        context,
        attempt_number=1,
        trace_id="validation-v13-audit",
        research_results=[],
        model_runtime_context_hash="8" * 64,
        run_mode="REAL_MODEL_VALIDATION",
    )
    state["normal_trade_plan"] = plan.model_dump(mode="json")
    state["risk_policy_summary"] = {}
    result = create_risk_manager(
        StructuredLLM(review_payload()),
        None,
        {
            "deep_provider": profile.provider,
            "deep_think_llm": profile.model_name,
            "top_prompt_version": prompt.prompt_version,
            "top_prompt_template": prompt.template,
            "top_structured_output_mode": "NATIVE_SCHEMA",
        },
    )(state)
    review = TopReviewDecision.model_validate(result["top_review_decision"])
    budget = BudgetDecision(
        allowed=True,
        status="READY",
        estimated_input_tokens=10,
        estimated_output_tokens=10,
        estimated_cost=0,
        remaining_daily_calls=99,
        remaining_daily_cost=20,
        model_context_window=32000,
        remaining_context_capacity=31980,
        context_usage_ratio=0.000625,
        context_warning_level="NONE",
    )
    record, created = await ModelAuditService(FakeDB()).record(
        analysis_id=review.analysis_id,
        snapshot_id=review.snapshot_id,
        context_hash=review.model_meta.context_hash,
        run_mode="REAL_MODEL_VALIDATION",
        automated_execution_allowed=False,
        role="TOP_RISK_REVIEWER",
        agent_name="top_risk_reviewer",
        profile=profile,
        prompt=prompt,
        request_hash=review.model_meta.input_hash,
        meta=review.model_meta,
        budget=budget,
    )
    assert created is True
    assert record.analysis_id == review.analysis_id
    assert record.snapshot_id == review.snapshot_id
    assert record.request_hash == review.model_meta.input_hash
    assert record.response_hash == review.model_meta.raw_output_hash
    assert review.standardized_model_payload == review_payload()
    assert review.standardized_model_payload_hash
    assert review.validation_errors == []


def test_research_manager_v2_contract_is_strict_and_hash_stable():
    valid = {
        "status": "SUCCESS",
        "summary": "Evidence synthesis is complete.",
        "findings": ["Snapshot evidence is internally consistent."],
        "risks": [],
        "evidence_refs": ["price:1"],
    }
    assert ResearchManagerOutputV2.model_validate(valid).status == "SUCCESS"
    for invalid in (
        {**valid, "status": "HOLD"},
        {key: value for key, value in valid.items() if key != "risks"},
        {**valid, "findings": "not-an-array"},
        {**valid, "decision": "BUY"},
    ):
        with pytest.raises(ValidationError):
            ResearchManagerOutputV2.model_validate(invalid)
    assert RESEARCH_MANAGER_CONTRACT_ID == "research_manager_output_contract"
    assert RESEARCH_MANAGER_CONTRACT_VERSION == "v2"
    assert len(RESEARCH_MANAGER_SCHEMA_HASH) == 64


def test_research_manager_diagnostics_store_shape_not_payload_values():
    secret_text = "MODEL-CONTENT-MUST-NOT-BE-PERSISTED"
    payload = {"status": "HOLD", "summary": secret_text}
    fields, field_types = normalized_payload_shape(payload)
    assert fields == ("status", "summary")
    assert field_types == ("string", "string")
    with pytest.raises(ValidationError) as captured:
        ResearchManagerOutputV2.model_validate(payload)
    error_fields, error_types = validation_error_projection(captured.value)
    diagnostics = str((fields, field_types, error_fields, error_types))
    assert "status" in error_fields
    assert "literal_error" in error_types
    assert secret_text not in diagnostics


@pytest.mark.asyncio
async def test_research_manager_contract_check_is_real_shape_only_and_reused(
    monkeypatch,
):
    db = FakeDB()
    await ModelProfileRegistry(db).seed()
    await PromptProfileRegistry(db).seed()
    model = StructuredLLM(
        {
            "status": "SUCCESS",
            "summary": "Synthetic evidence is complete.",
            "findings": ["The immutable reference is available."],
            "risks": [],
            "evidence_refs": [CAPABILITY_EVIDENCE_REF],
        }
    )
    service = ResearchManagerContractService(db)

    async def allowed(**_kwargs):
        return BudgetDecision(
            allowed=True,
            status="READY",
            estimated_input_tokens=10,
            estimated_output_tokens=10,
            estimated_cost=0,
            remaining_daily_calls=99,
            remaining_daily_cost=20,
            model_context_window=32000,
            remaining_context_capacity=31980,
            context_usage_ratio=0.000625,
            context_warning_level="NONE",
            permitted_attempts=1,
        )

    monkeypatch.setattr(service.budget, "check", allowed)
    first = await service.check(
        checked_by="admin",
        idempotency_key="manager-contract-v2-check",
        llm=model,
    )
    second = await service.check(
        checked_by="admin",
        idempotency_key="manager-contract-v2-check",
        llm=model,
    )
    assert first == second
    assert first.status == "READY"
    assert first.schema_hash == RESEARCH_MANAGER_SCHEMA_HASH
    assert first.prompt_version == "v2"
    assert first.payload_fields == (
        "evidence_refs",
        "findings",
        "risks",
        "status",
        "summary",
    )
    assert first.validation_error_fields == ()
    assert model.invocations == 1
    assert db["ag_model_contract_checks"].count() == 1
    assert db["ag_model_runs"].count() == 1
    stored = str(db["ag_model_contract_checks"].documents)
    assert "Synthetic evidence is complete" not in stored


@pytest.mark.asyncio
async def test_research_manager_contract_check_records_exact_error_paths(
    monkeypatch,
):
    db = FakeDB()
    await ModelProfileRegistry(db).seed()
    await PromptProfileRegistry(db).seed()
    service = ResearchManagerContractService(db)
    model = StructuredLLM(
        {
            "status": "HOLD",
            "summary": "invalid manager action",
            "findings": [],
            "risks": [],
            "evidence_refs": [CAPABILITY_EVIDENCE_REF],
        }
    )

    async def allowed(**_kwargs):
        return BudgetDecision(
            allowed=True,
            status="READY",
            estimated_input_tokens=10,
            estimated_output_tokens=10,
            estimated_cost=0,
            remaining_daily_calls=99,
            remaining_daily_cost=20,
            model_context_window=32000,
            remaining_context_capacity=31980,
            context_usage_ratio=0.000625,
            context_warning_level="NONE",
            permitted_attempts=1,
        )

    monkeypatch.setattr(service.budget, "check", allowed)
    result = await service.check(
        checked_by="admin",
        idempotency_key="manager-contract-v2-invalid",
        llm=model,
    )
    assert result.status == "INVALID_OUTPUT"
    assert result.validation_error_fields == ("status",)
    assert result.validation_error_types == ("literal_error",)
    assert "invalid manager action" not in str(result.model_dump())


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


@pytest.mark.asyncio
async def test_model_audit_context_capacity_uses_provider_reported_usage():
    db = FakeDB()
    profile = ModelProfileRegistry().for_role("TOP_RISK_REVIEWER")
    prompt = PromptProfileRegistry().definition("top_risk_review_prompt")
    now = datetime.now(timezone.utc)
    meta = ModelExecutionMeta(
        provider=profile.provider,
        model_name=profile.model_name,
        model_version=profile.model_name,
        prompt_name="top_review_decision",
        prompt_version=prompt.prompt_version,
        started_at=now,
        finished_at=now,
        latency_ms=1,
        execution_status="SUCCESS",
        input_tokens=80,
        output_tokens=30,
        total_tokens=110,
        attempt_number=1,
    )
    budget = BudgetDecision(
        allowed=True,
        status="READY",
        estimated_input_tokens=10,
        estimated_output_tokens=10,
        estimated_cost=0,
        remaining_daily_calls=99,
        remaining_daily_cost=20,
        model_context_window=100,
        remaining_context_capacity=80,
        context_usage_ratio=0.2,
        context_warning_level="NONE",
    )
    record, created = await ModelAuditService(db).record(
        analysis_id="analysis-actual-context",
        snapshot_id="snapshot-actual-context",
        context_hash="8" * 64,
        run_mode="REAL_MODEL_VALIDATION",
        automated_execution_allowed=False,
        role="TOP_RISK_REVIEWER",
        agent_name="top_risk_reviewer",
        profile=profile,
        prompt=prompt,
        request_hash="7" * 64,
        meta=meta,
        budget=budget,
    )
    assert created is True
    assert record.estimated_input_tokens == 10
    assert record.input_tokens == 80
    assert record.output_tokens == 30
    assert record.remaining_context_capacity == 0
    assert record.context_usage_ratio == pytest.approx(1.1)
    assert record.context_warning_level == "OVER_95"


def test_native_schema_unwraps_compatible_message_envelope():
    result = invoke_json_object(
        llm=CompatibleMessageEnvelopeLLM(),
        messages=[],
        schema_model=SimpleCapabilitySchema,
        provider="openai-compatible",
        configured_model_name="compatible-model",
        prompt_name="capability",
        prompt_version="v1",
        structured_output_mode="NATIVE_SCHEMA",
    )
    assert result.failure_status is None
    assert result.payload == {
        "status": "READY",
        "note": "compatible envelope",
    }


def test_capability_failure_summary_hides_validation_details():
    assert capability_failure_summary("PROVIDER_ERROR", "ValidationError") == (
        "模型已返回内容，但结构化结果未通过校验。"
    )
    assert capability_failure_summary("INVALID_OUTPUT", "INVALID_OUTPUT") == (
        "模型返回了 JSON，但决策字段不完整或不符合要求；"
        "请改用结构化输出能力更稳定的模型。"
    )
    assert capability_failure_summary(
        "INVALID_OUTPUT", "INVALID_OUTPUT", 7
    ) == (
        "模型返回了 JSON，但有 7 个决策字段缺失或不符合要求；"
        "请改用结构化输出能力更稳定的模型。"
    )

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


def test_newer_successful_credential_verification_marks_old_check_stale():
    checked_at = datetime(2026, 8, 1, 2, 55, tzinfo=timezone.utc)
    original = {
        "status": "UNAUTHORIZED",
        "error_code": "UNAUTHORIZED",
        "checked_at": checked_at,
    }
    projected, stale = project_capability_check(
        original,
        {
            "status": "CONFIGURED",
            # Motor returns UTC-naive values unless tz_aware is enabled.
            "last_verified_at": datetime(2026, 8, 1, 2, 56),
        },
    )

    assert stale is True
    assert projected is not None
    assert projected["status"] == "UNVERIFIED"
    assert projected["error_code"] == "CREDENTIAL_REVERIFIED"
    assert original["status"] == "UNAUTHORIZED"

    failed_verification, failed_stale = project_capability_check(
        original,
        {
            "status": "DEGRADED",
            "last_verified_at": datetime(2026, 8, 1, 2, 57),
        },
    )
    assert failed_stale is False
    assert failed_verification == original

    legacy, legacy_stale = project_capability_check(
        {
            "status": "PROVIDER_ERROR",
            "error_code": "ValidationError",
            "checked_at": checked_at,
        },
        None,
    )
    assert legacy_stale is False
    assert legacy is not None
    assert legacy["status"] == "INVALID_OUTPUT"
    assert legacy["error_code"] == "INVALID_OUTPUT"

    quota_original = {
        "status": "UNAUTHORIZED",
        "error_code": "UNAUTHORIZED",
        "sanitized_message": (
            "403 insufficient_user_quota balance=0.01 precharge=2.00 "
            "request_id=req-sensitive"
        ),
        "checked_at": checked_at,
    }
    quota, quota_stale = project_capability_check(quota_original, None)
    assert quota_stale is False
    assert quota is not None
    assert quota["status"] == "BUDGET_BLOCKED"
    assert quota["error_code"] == "PROVIDER_QUOTA_EXHAUSTED"
    assert quota["sanitized_message"] == "provider quota is exhausted"
    assert quota_original["status"] == "UNAUTHORIZED"
    assert "0.01" not in quota["sanitized_message"]
    assert "req-sensitive" not in quota["sanitized_message"]


@pytest.mark.asyncio
async def test_capability_schema_validation_is_invalid_output_not_provider_error():
    db = FakeDB()
    await ModelProfileRegistry(db).seed()
    await PromptProfileRegistry(db).seed()
    service = ModelCapabilityService(
        db,
        provider_runtime=SimpleNamespace(
            create_registered=AsyncMock(return_value=StructuredLLM())
        ),
    )
    service.credentials = SimpleNamespace(configured=lambda _ref: True)
    service._provider_access_probe = AsyncMock(
        return_value=("READY", None, 1.0)
    )
    service.budget = SimpleNamespace(
        check=AsyncMock(
            return_value=BudgetDecision(
                allowed=True,
                status="READY",
                estimated_input_tokens=10,
                estimated_output_tokens=10,
                estimated_cost=0,
                remaining_daily_calls=10,
                remaining_daily_cost=10,
                model_context_window=32000,
                remaining_context_capacity=31980,
                context_usage_ratio=0.000625,
                context_warning_level="NONE",
                permitted_attempts=1,
            )
        )
    )

    result = await service.check(
        profile_id="alphaguard_normal_openai",
        profile_version="v2",
        checked_by="admin",
        idempotency_key="invalid-capability-contract",
        network=True,
    )

    assert result.status == "INVALID_OUTPUT"
    assert result.error_category == "INVALID_OUTPUT"
    assert result.error_code == "INVALID_OUTPUT"
    assert result.structured_output_supported is False
    assert result.validation_error_count is not None
    assert result.validation_error_count > 0
    assert result.validation_missing_field_count is not None
    assert result.validation_missing_field_count > 0
    assert result.validation_error_fields
    assert "missing" in result.validation_error_types
    serialized = result.model_dump_json()
    assert "structured output available" not in serialized
    assert "validation" not in (result.sanitized_message or "").lower()


@pytest.mark.asyncio
async def test_research_capability_echo_is_not_rejected_for_execution_meta():
    db = FakeDB()
    await ModelProfileRegistry(db).seed()
    await PromptProfileRegistry(db).seed()
    service = ModelCapabilityService(
        db,
        provider_runtime=SimpleNamespace(
            create_registered=AsyncMock(return_value=StructuredLLM())
        ),
    )
    service.credentials = SimpleNamespace(configured=lambda _ref: True)
    service._provider_access_probe = AsyncMock(
        return_value=("READY", None, 1.0)
    )
    service.budget = SimpleNamespace(
        check=AsyncMock(
            return_value=BudgetDecision(
                allowed=True,
                status="READY",
                estimated_input_tokens=10,
                estimated_output_tokens=10,
                estimated_cost=0,
                remaining_daily_calls=10,
                remaining_daily_cost=10,
                model_context_window=32000,
                remaining_context_capacity=31980,
                context_usage_ratio=0.000625,
                context_warning_level="NONE",
                permitted_attempts=1,
            )
        )
    )

    result = await service.check(
        profile_id="alphaguard_research_openai",
        profile_version="v2",
        checked_by="admin",
        idempotency_key="research-capability-echo",
        network=True,
    )

    assert result.status == "USAGE_UNAVAILABLE"
    assert result.structured_output_supported is True
    assert result.validation_error_count is None
    assert result.error_code == "USAGE_UNAVAILABLE"


def test_provider_quota_is_not_auth_failure_and_error_details_are_removed():
    error = ProviderQuotaError(
        "insufficient_user_quota balance=0.01 precharge=2.00 "
        "request_id=req-sensitive"
    )
    assert _classify_provider_error(error) == "PROVIDER_QUOTA_EXHAUSTED"

    result = invoke_json_object(
        llm=StructuredLLM(error=error),
        messages=[],
        schema_model=SimpleCapabilitySchema,
        provider="openai-compatible",
        configured_model_name="registered-model",
        prompt_name="capability",
        prompt_version="v1",
        structured_output_mode="NATIVE_SCHEMA",
        max_retries=3,
    )

    assert result.error_type == "PROVIDER_QUOTA_EXHAUSTED"
    assert result.error_message == "provider quota is exhausted"
    assert len(result.attempt_metas) == 1
    serialized = result.model_meta.model_dump_json()
    assert "balance" not in serialized
    assert "precharge" not in serialized
    assert "req-sensitive" not in serialized


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
    assert first.idempotency_status == "CREATED"
    assert second.idempotency_status == "REUSED"
    assert first.status == "MODEL_NOT_CONFIGURED"
    assert first.execution_gate_status == "NOT_REACHED"
    assert first.execution_gate_invoked is False
    assert first.validation_contract_version == VALIDATION_CONTRACT_VERSION
    assert first.contract_hash is not None
    assert first.sample_selection_version == SAMPLE_SELECTION_VERSION
    assert first.actual_production_decision is False
    assert first.actual_execution is False
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
async def test_v13_identity_does_not_overwrite_immutable_v9_failure(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    db = FakeDB()
    await ModelProfileRegistry(db).seed()
    await PromptProfileRegistry(db).seed()
    old_v9 = {
        "validation_run_id": "2bb79775-cc28-580c-b25d-436da85d7ca1",
        "contract_version": "real-model-historical-evidence-v9",
        "status": "FAILED",
        "failure_code": "RESEARCH_MODEL_PATH_FAILED",
        "snapshot_id": "a3b1f35f-a707-52b0-8016-4e70c812c5bb",
        "result_hash": "9" * 64,
    }
    await db["ag_model_validation_runs"].insert_one(old_v9)
    result = await RealModelValidationService(db).run(
        requested_by="admin",
        idempotency_key="validation-v13-new-identity",
    )
    assert result.validation_run_id != old_v9["validation_run_id"]
    assert result.validation_contract_version == (
        "real-model-historical-decision-evidence-v13"
    )
    stored_old = await db["ag_model_validation_runs"].find_one(
        {"validation_run_id": old_v9["validation_run_id"]}
    )
    assert stored_old["failure_code"] == "RESEARCH_MODEL_PATH_FAILED"
    assert stored_old["result_hash"] == "9" * 64
    assert db["ag_model_validation_runs"].count() == 2


def test_triggered_sample_order_is_stable_without_future_performance():
    base = make_context().quant_proposal
    proposals = [
        base.model_copy(
            update={
                "proposal_id": "proposal-b",
                "symbol": "300750",
                "trade_date": base.trade_date,
            }
        ),
        base.model_copy(
            update={
                "proposal_id": "proposal-a",
                "symbol": "300750",
                "trade_date": base.trade_date,
            }
        ),
        base.model_copy(
            update={
                "proposal_id": "proposal-c",
                "symbol": "000333",
                "trade_date": base.trade_date,
            }
        ),
        base.model_copy(
            update={
                "proposal_id": "proposal-newest",
                "symbol": "601318",
                "trade_date": base.trade_date + timedelta(days=1),
            }
        ),
    ]
    ordered = sorted(proposals, key=_sample_order_key)
    assert [item.proposal_id for item in ordered] == [
        "proposal-c",
        "proposal-a",
        "proposal-b",
        "proposal-newest",
    ]
    assert SAMPLE_SELECTION_VERSION == (
        "evidence-completeness-factor-mean-date-symbol-proposal-v1"
    )


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
async def test_zero_cost_profile_keeps_resource_limits_and_is_budget_ready():
    db = FakeDB()
    profile = ModelProfileRegistry().for_role("NORMAL_TRADER").model_copy(
        update={
            "input_cost_per_million": 0.0,
            "output_cost_per_million": 0.0,
            "cost_currency": "USD",
            "max_retries": 1,
            "timeout_seconds": 37,
        }
    )
    decision = await ModelBudgetService(db).check(
        profile=profile,
        analysis_id="analysis-self-hosted",
        snapshot_id="snapshot-self-hosted",
        rendered_input="complete immutable context",
    )
    assert decision.allowed is True
    assert decision.status == "READY"
    assert decision.reason_code is None
    assert decision.estimated_cost == 0
    assert decision.permitted_attempts == 2
    assert profile.timeout_seconds == 37
    assert profile.max_retries == 1


@pytest.mark.asyncio
async def test_snapshot_token_history_is_audited_but_never_blocks_next_call():
    db = FakeDB()
    profile = ModelProfileRegistry().for_role("TOP_RISK_REVIEWER").model_copy(
        update={
            "input_cost_per_million": 0.0,
            "output_cost_per_million": 0.0,
            "cost_currency": "USD",
            "max_input_tokens": 32000,
            "max_output_tokens": 4000,
        }
    )
    await db["ag_model_runs"].insert_one(
        {
            "analysis_id": "other-analysis",
            "snapshot_id": "snapshot-over-old-cap",
            "created_at": datetime.now(timezone.utc),
            "total_tokens": 103509,
            "estimated_cost": 0,
        }
    )
    decision = await ModelBudgetService(db).check(
        profile=profile,
        analysis_id="analysis-v12",
        snapshot_id="snapshot-over-old-cap",
        rendered_input="complete immutable context",
    )
    assert decision.allowed is True
    assert decision.reason_code is None
    assert decision.model_context_window == 32000


@pytest.mark.asyncio
async def test_new_validation_identity_reuses_context_without_old_call_count():
    db = FakeDB()
    old_analysis_id = "real-model-validation:old-run"
    new_analysis_id = "real-model-validation:new-run"
    for index in range(10):
        await db["ag_model_runs"].insert_one(
            {
                "analysis_id": old_analysis_id,
                "created_at": datetime.now(timezone.utc),
                "estimated_cost": 0,
                "attempt": index + 1,
            }
        )
    profile = ModelProfileRegistry().for_role("TOP_RISK_REVIEWER").model_copy(
        update={
            "input_cost_per_million": 0.0,
            "output_cost_per_million": 0.0,
            "cost_currency": "USD",
            "max_input_tokens": 32000,
            "max_output_tokens": 4000,
        }
    )
    prompt = PromptProfileRegistry().definition("top_risk_review_prompt")
    context = make_context().model_copy(update={"analysis_id": old_analysis_id})
    runner = ProfiledDecisionModelRunner(
        db=db,
        normal_node=None,
        top_node=create_risk_manager(
            StructuredLLM(review_payload()),
            None,
            {
                "deep_provider": profile.provider,
                "deep_think_llm": profile.model_name,
                "top_prompt_version": prompt.prompt_version,
                "top_prompt_template": prompt.template,
                "top_structured_output_mode": "NATIVE_SCHEMA",
                "top_profile_id": profile.profile_id,
                "top_profile_version": profile.profile_version,
                "top_prompt_id": prompt.prompt_id,
            },
        ),
        normal_profile=profile,
        top_profile=profile,
        normal_prompt=prompt,
        top_prompt=prompt,
        revision_prompt=prompt,
        run_mode="REAL_MODEL_VALIDATION",
        automated_execution_allowed=False,
        model_runtime_context_hash="8" * 64,
        model_call_analysis_id=new_analysis_id,
    )

    old_budget = await ModelBudgetService(db).check(
        profile=profile,
        analysis_id=old_analysis_id,
        snapshot_id=context.snapshot_id,
        rendered_input="same immutable context",
    )
    new_budget = await runner._check_budget(
        profile,
        context,
        "same immutable context",
    )

    assert old_budget.reason_code == "ANALYSIS_CALL_BUDGET_EXCEEDED"
    assert new_budget.allowed is True
    assert new_budget.permitted_attempts >= 1


@pytest.mark.asyncio
async def test_validation_top_continuation_disables_network_retry():
    db = FakeDB()
    context = make_context()
    plan = make_plan(context)
    profile = ModelProfileRegistry().for_role("TOP_RISK_REVIEWER").model_copy(
        update={
            "input_cost_per_million": 0.0,
            "output_cost_per_million": 0.0,
            "cost_currency": "USD",
            "max_retries": 1,
        }
    )
    prompt = PromptProfileRegistry().definition("top_risk_review_prompt")
    model = StructuredLLM(error=TimeoutError("single allowed attempt"))
    runner = ProfiledDecisionModelRunner(
        db=db,
        normal_node=None,
        top_node=create_risk_manager(
            model,
            None,
            {
                "deep_provider": profile.provider,
                "deep_think_llm": profile.model_name,
                "top_prompt_version": prompt.prompt_version,
                "top_prompt_template": prompt.template,
                "top_structured_output_mode": "NATIVE_SCHEMA",
                "top_max_retries": profile.max_retries,
                "top_profile_id": profile.profile_id,
                "top_profile_version": profile.profile_version,
                "top_prompt_id": prompt.prompt_id,
            },
        ),
        normal_profile=profile,
        top_profile=profile,
        normal_prompt=prompt,
        top_prompt=prompt,
        revision_prompt=prompt,
        run_mode="REAL_MODEL_VALIDATION",
        automated_execution_allowed=False,
        model_runtime_context_hash=plan.model_meta.context_hash,
        model_call_analysis_id="real-model-validation:one-top-attempt",
        top_attempt_limit=1,
    )

    review = await runner.run_top(
        context=context,
        plan=plan,
        risk_policy_summary={},
        attempt_number=2,
        trace_id="one-top-attempt",
    )

    assert review.status == "MODEL_FAILED"
    assert review.model_meta.error_type == "TIMEOUT"
    assert model.invocations == 1


@pytest.mark.asyncio
async def test_only_actual_model_context_window_blocks_token_admission():
    db = FakeDB()
    profile = ModelProfileRegistry().for_role("TOP_RISK_REVIEWER").model_copy(
        update={
            "input_cost_per_million": 0.0,
            "output_cost_per_million": 0.0,
            "cost_currency": "USD",
            "max_input_tokens": 100,
            "max_output_tokens": 40,
        }
    )
    decision = await ModelBudgetService(db).check(
        profile=profile,
        analysis_id="analysis-context-limit",
        snapshot_id="snapshot-context-limit",
        rendered_input="x" * 200,
    )
    assert decision.allowed is False
    assert decision.reason_code == "MODEL_CONTEXT_WINDOW_EXCEEDED"
    assert decision.estimated_input_tokens + decision.estimated_output_tokens > 100


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("input_bytes", "warning"),
    ((1830, "OVER_70"), (2280, "OVER_85"), (2580, "OVER_95")),
)
async def test_context_thresholds_are_non_blocking_audit_warnings(
    input_bytes,
    warning,
):
    db = FakeDB()
    profile = ModelProfileRegistry().for_role("TOP_RISK_REVIEWER").model_copy(
        update={
            "input_cost_per_million": 0.0,
            "output_cost_per_million": 0.0,
            "cost_currency": "USD",
            "max_input_tokens": 1000,
            "max_output_tokens": 100,
        }
    )
    decision = await ModelBudgetService(db).check(
        profile=profile,
        analysis_id=f"analysis-{warning}",
        snapshot_id="snapshot-context-warning",
        rendered_input="x" * input_bytes,
    )
    assert decision.allowed is True
    assert decision.context_warning_level == warning
    assert decision.remaining_context_capacity >= 0


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
        price_evidence=[SimpleNamespace(evidence_id="price:1")],
        financial_evidence=[SimpleNamespace(evidence_id="financial:1")],
        news_evidence=[],
        announcement_evidence=[],
        account_evidence=[],
        portfolio_evidence=[],
        quant_proposal_id="proposal:1",
        regime_result_id="regime:1",
        factor_result_ids=["factor:1"],
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
    compact = build_model_runtime_context(
        context,
        resolved,
        include_resolved_refs=False,
    )
    assert compact.evidence_refs == first.evidence_refs
    assert compact.payload["resolved_input_ref_count"] == 2
    assert "resolved_input_refs" not in compact.payload
    assert compact.payload["allowed_raw_evidence_refs"] == [
        "financial:1",
        "price:1",
    ]
    assert compact.payload["allowed_derived_evidence_refs"] == [
        "factor:1",
        "proposal:1",
        "regime:1",
    ]
    assert compact.context_hash != first.context_hash
    legacy_context, legacy = _runtime_context("evidence-snapshot-v1")
    with pytest.raises(ModelRuntimeContextError, match="Snapshot v2"):
        build_model_runtime_context(legacy_context, legacy)


def test_validation_snapshot_contract_preserves_historical_champion_refs():
    service_source = (
        ROOT / "app/services/alphaguard/evidence_snapshot_service.py"
    ).read_text(encoding="utf-8")
    validation_source = (
        ROOT / "app/services/alphaguard/real_model_validation_service.py"
    ).read_text(encoding="utf-8")
    assert 'data.get("run_mode") == "EVIDENCE_CONTRACT_VALIDATION"' in service_source
    assert "if has_pr008_registry and not validation_mode" in service_source
    assert '"champion_version_refs": source.champion_version_refs' in validation_source


def test_decision_research_projection_is_bounded_and_keeps_identity():
    result = SimpleNamespace(
        research_result_id="research-1",
        agent_name="market_analyst",
        agent_role="MARKET_ANALYST",
        status="SUCCESS",
        snapshot_id="snapshot-v2",
        context_hash="f" * 64,
        structured_summary={
            "summary": "bounded summary",
            "findings": [f"finding-{index}" for index in range(6)],
            "risks": [f"risk-{index}" for index in range(6)],
        },
        evidence_refs=[f"price:{index}" for index in range(20)],
        result_hash="e" * 64,
    )
    projected = _decision_research_projection(result)
    assert projected["snapshot_id"] == "snapshot-v2"
    assert projected["context_hash"] == "f" * 64
    assert "findings" not in projected
    assert "risks" not in projected
    assert len(projected["evidence_refs"]) == 8


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
            model_context_window=32000,
            remaining_context_capacity=31980,
            context_usage_ratio=0.000625,
            context_warning_level="NONE",
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
    manager_run = next(
        item
        for item in db["ag_model_runs"].documents
        if item["agent_name"] == "research_manager"
    )
    assert manager_run["prompt_id"] == "alphaguard_research_manager_snapshot"
    assert manager_run["prompt_version"] == "v2"
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
            model_context_window=32000,
            remaining_context_capacity=31980,
            context_usage_ratio=0.000625,
            context_warning_level="NONE",
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


def test_pr010_validation_accepts_only_the_explicit_runtime_context_hash():
    context = make_context()
    runtime_hash = "9" * 64
    plan = make_plan(context)
    plan = plan.model_copy(
        update={
            "model_meta": plan.model_meta.model_copy(
                update={"context_hash": runtime_hash}
            )
        }
    )
    validate_plan_against_context(
        plan,
        context,
        model_runtime_context_hash=runtime_hash,
    )
    with pytest.raises(ValueError, match="context_hash mismatch"):
        validate_plan_against_context(plan, context)


def test_real_validation_context_uses_locked_profile_prompt_versions():
    source = (
        ROOT / "app/services/alphaguard/real_model_validation_service.py"
    ).read_text(encoding="utf-8")
    assert '"normal_prompt_version": _frozen_snapshot_prompt_version(' in source
    assert '"top_prompt_version": _frozen_snapshot_prompt_version(' in source
    assert '"normal_prompt_version": NORMAL_QUANT_PROMPT_VERSION' not in source
    assert '"top_prompt_version": TOP_QUANT_PROMPT_VERSION' not in source


def test_frozen_snapshot_prompt_version_preserves_reused_v11_context():
    snapshot = SimpleNamespace(
        prompt_versions={
            "normal": "normal_trade_plan_prompt@alphaguard-normal-quant-v1",
            "top": "top_risk_review_prompt@alphaguard-top-review-v1",
        }
    )
    assert _frozen_snapshot_prompt_version(snapshot, "normal", "new-normal") == (
        "alphaguard-normal-quant-v1"
    )
    assert _frozen_snapshot_prompt_version(snapshot, "top", "new-top") == (
        "alphaguard-top-review-v1"
    )
    assert _frozen_snapshot_prompt_version(snapshot, "missing", "fallback") == (
        "fallback"
    )


def test_real_validation_freezes_model_evaluation_clock_at_snapshot_close():
    context = make_context()
    state = ProfiledDecisionModelRunner._base_state(
        context,
        attempt_number=1,
        trace_id="trace",
        research_results=[],
        model_runtime_context_hash="8" * 64,
        run_mode="REAL_MODEL_VALIDATION",
    )
    assert state["evaluation_clock"] == {
        "mode": "HISTORICAL_SNAPSHOT_CLOSE",
        "as_of_trade_date": context.trade_date.isoformat(),
        "as_of_at": f"{context.trade_date.isoformat()}T15:00:00+08:00",
        "current_wall_clock_allowed": False,
    }
    production = ProfiledDecisionModelRunner._base_state(
        context,
        attempt_number=1,
        trace_id="trace",
        research_results=[],
        model_runtime_context_hash="8" * 64,
        run_mode="PRODUCTION",
    )
    assert "evaluation_clock" not in production


def test_trader_validation_detail_reports_static_root_reason_without_payload():
    context = make_context()
    plan = make_plan(context).model_dump(mode="python")
    secret_payload_text = "MODEL-OUTPUT-MUST-NOT-BE-AUDITED"
    plan.update(
        status="PROPOSE_TRADE",
        action="BUY",
        thesis=secret_payload_text,
        valid_until=None,
        valid_until_compatibility_reason=None,
    )
    with pytest.raises(ValidationError) as captured:
        NormalTradePlan.model_validate(plan)
    detail = _validation_failure_detail(captured.value)
    assert "PROPOSE_TRADE requires valid_until" in detail
    assert secret_payload_text not in detail


def test_normal_trade_plan_machine_schema_exposes_existing_semantic_contract():
    schema = NormalTradePlan.model_json_schema()
    properties = schema["properties"]
    assert "Status/action contract" in properties["status"]["description"]
    assert "at least one" in properties["stop_conditions"]["description"]
    assert "Required for PROPOSE_TRADE" in properties["valid_until"]["description"]


def test_normal_trade_plan_schema_is_bound_to_snapshot_and_proposal():
    context = make_context()
    schema = _context_bound_plan_schema(context)
    properties = schema["properties"]
    assert context.quant_proposal.action_candidate in properties["action"]["enum"]
    assert properties["initial_position_pct"]["anyOf"][0]["maximum"] == (
        context.quant_proposal.initial_position_pct
    )
    assert properties["max_position_pct"]["anyOf"][0]["maximum"] == (
        context.quant_proposal.max_position_pct
    )
    evidence_ids = schema["$defs"]["EvidenceRef"]["properties"]["evidence_id"][
        "enum"
    ]
    assert evidence_ids == sorted(context.evidence_ids())


def test_research_and_top_schemas_are_bound_to_snapshot_evidence():
    context = make_context()
    runtime_context = SimpleNamespace(
        payload={"allowed_evidence_refs": sorted(context.evidence_ids())},
        evidence_refs=tuple(sorted(context.evidence_ids())),
    )
    research_schema = _context_bound_research_schema(runtime_context)
    assert research_schema["properties"]["evidence_refs"]["items"]["enum"] == (
        sorted(context.evidence_ids())
    )
    plan = make_plan(context)
    top_schema = _context_bound_review_schema(context, plan)
    evidence_ids = top_schema["$defs"]["EvidenceRef"]["properties"][
        "evidence_id"
    ]["enum"]
    assert evidence_ids == sorted(context.evidence_ids())
    proposed = top_schema["$defs"]["TopPlanProposedChanges"]["properties"]
    assert proposed["action"]["enum"][0] == plan.action
    assert proposed["max_position_pct"]["anyOf"][0]["maximum"] == (
        plan.max_position_pct
    )
    schema_text = json.dumps(top_schema, sort_keys=True)
    assert "plan_id" not in schema_text
    assert "supersedes_plan_id" not in schema_text


def test_top_preflight_uses_the_exact_node_prompt_messages_and_schema():
    context = make_context()
    plan = make_plan(context)
    prompt = PromptProfileRegistry().definition("top_risk_review_prompt")
    research = [
        {
            "research_result_id": "research-1",
            "snapshot_id": context.snapshot_id,
            "context_hash": "8" * 64,
            "status": "SUCCESS",
        }
    ]
    policy = {"policy_id": "risk-policy-v1", "max_position_pct": 0.10}
    state = ProfiledDecisionModelRunner._base_state(
        context,
        attempt_number=2,
        trace_id="validation-v12",
        research_results=research,
        model_runtime_context_hash="8" * 64,
        run_mode="REAL_MODEL_VALIDATION",
    )
    state["normal_trade_plan"] = plan.model_dump(mode="json")
    state["risk_policy_summary"] = policy
    config = {
        "deep_provider": "compatible",
        "deep_think_llm": "top-model",
        "top_prompt_version": prompt.prompt_version,
        "top_prompt_template": prompt.template,
        "top_structured_output_mode": "NATIVE_SCHEMA",
    }
    expected = build_top_review_model_request(
        context=context,
        normal_plan=plan,
        state=state,
        config=config,
        prompt_version=prompt.prompt_version,
        instrument_context=build_instrument_context(context.symbol),
    )

    rendered = ProfiledDecisionModelRunner.render_top_input(
        context=context,
        plan=plan,
        risk_policy_summary=policy,
        research_results=research,
        model_runtime_context_hash="8" * 64,
        top_prompt_version=prompt.prompt_version,
        top_prompt_template=prompt.template,
        structured_output_mode="NATIVE_SCHEMA",
        run_mode="REAL_MODEL_VALIDATION",
    )
    envelope = json.loads(rendered)
    assert envelope["messages"] == list(expected.messages)
    assert envelope["transport_schema"] == expected.output_schema
    assert "Snapshot-bound decision context" in envelope["messages"][0]["content"]
    assert "Exact model-facing JSON Schema" in envelope["messages"][0]["content"]
    assert prompt.prompt_version == "alphaguard-top-review-v3"
    assert "CONFIRM, REJECT, and SUSPEND require proposed_changes={}" in (
        envelope["messages"][0]["content"]
    )
    assert envelope["messages"][1]["content"] == json.dumps(
        expected.user_payload,
        ensure_ascii=False,
        default=str,
    )

    model = StructuredLLM(review_payload())
    create_risk_manager(model, None, config)(state)
    assert model.messages == list(expected.messages)

    json_schema_rendered = render_structured_input_for_estimation(
        expected.messages,
        schema=expected.output_schema,
        structured_output_mode="JSON_SCHEMA",
    )
    json_schema_envelope = json.loads(json_schema_rendered)
    assert json_schema_envelope["transport_schema"] is None
    assert "Return exactly one JSON object matching this schema" in (
        json_schema_envelope["messages"][0]["content"]
    )


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
    assert "模型与 API" in operations
    model_panel = (
        ROOT / "frontend/src/components/alphaguard/ModelConfigurationPanel.vue"
    ).read_text(encoding="utf-8")
    assert "真实双模型验证" in model_panel
    assert "validationRuns(20)" in model_panel
    assert "执行安全门" in model_panel
    assert "请求哈希" in model_panel
    assert "响应哈希" in model_panel
    assert "credential_ref" not in router
    assert "api_key: SecretStr" in router


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
    assert response.json()["data"]["decision_status"] == "NOT_CONFIGURED"
    assert response.json()["data"]["research_status"] == "NOT_CONFIGURED"
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
