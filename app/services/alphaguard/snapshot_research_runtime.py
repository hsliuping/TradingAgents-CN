"""Snapshot-bound TradingAgents research roles with no tools or latest queries."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Annotated, Any, Literal
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.schemas.alphaguard.decision import canonical_hash
from app.schemas.alphaguard.model_runtime import (
    ResearchAgentResult,
)
from tradingagents.alphaguard.decision_schemas import ModelExecutionMeta
from tradingagents.alphaguard.structured_output import (
    invoke_json_object,
    model_output_schema,
)

from .model_audit_service import ModelAuditService
from .model_budget_service import ModelBudgetService
from .model_profile_registry import ModelProfileRegistry
from .model_provider_runtime import ModelProviderRuntime
from .model_runtime_context import ModelRuntimeContext
from .model_runtime_repository import ModelRuntimeRepository
from .prompt_profile_registry import PromptProfileRegistry


RESEARCH_ROLES = (
    ("market_analyst", "MARKET_ANALYST"),
    ("fundamentals_analyst", "FUNDAMENTALS_ANALYST"),
    ("news_announcement_analyst", "NEWS_ANNOUNCEMENT_ANALYST"),
    ("bull_researcher", "BULL_RESEARCHER"),
    ("bear_researcher", "BEAR_RESEARCHER"),
    ("research_manager", "RESEARCH_MANAGER"),
)

RESEARCH_MANAGER_CONTRACT_ID = "research_manager_output_contract"
RESEARCH_MANAGER_CONTRACT_VERSION = "v2"


class ResearchAgentOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    status: Literal["SUCCESS", "INSUFFICIENT_DATA"]
    summary: str = Field(min_length=1)
    findings: list[str]
    risks: list[str]
    evidence_refs: list[str]


NonEmptyResearchText = Annotated[str, Field(min_length=1)]


class ResearchManagerOutputV2(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    status: Literal["SUCCESS", "INSUFFICIENT_DATA"] = Field(
        description=(
            "Evidence-completeness status only; this is never a trading action."
        )
    )
    summary: NonEmptyResearchText
    findings: list[NonEmptyResearchText]
    risks: list[NonEmptyResearchText]
    evidence_refs: list[NonEmptyResearchText]


RESEARCH_MANAGER_SCHEMA_HASH = canonical_hash(
    model_output_schema(ResearchManagerOutputV2)
)


def _context_bound_research_schema(
    context: ModelRuntimeContext,
    *,
    schema_model: type[BaseModel] = ResearchAgentOutput,
) -> dict[str, Any]:
    schema = model_output_schema(schema_model)
    allowed = sorted(
        context.payload.get("allowed_evidence_refs") or context.evidence_refs
    )
    schema["properties"]["evidence_refs"] = {
        "description": "Citations selected only from immutable Snapshot evidence IDs.",
        "items": {"enum": allowed, "type": "string"},
        "title": "Evidence Refs",
        "type": "array",
    }
    return schema


def validation_error_projection(
    error: ValidationError,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    fields: list[str] = []
    error_types: list[str] = []
    for item in error.errors(include_url=False, include_context=False, include_input=False):
        location = ".".join(str(part) for part in item.get("loc") or ("$",))
        fields.append(location or "$")
        error_types.append(str(item.get("type") or "validation_error"))
    return tuple(fields), tuple(error_types)


def normalized_payload_shape(
    payload: dict[str, Any] | None,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    def type_name(value: Any) -> str:
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, str):
            return "string"
        if isinstance(value, (int, float)):
            return "number"
        if isinstance(value, list):
            return "array"
        if isinstance(value, dict):
            return "object"
        return "unsupported"

    fields = tuple(sorted((payload or {}).keys()))
    return fields, tuple(type_name((payload or {})[field]) for field in fields)


def _manager_research_projection(
    results: list[ResearchAgentResult],
) -> list[dict[str, Any]]:
    projection: list[dict[str, Any]] = []
    for result in results:
        structured = dict(result.structured_summary or {})
        projection.append(
            {
                "research_result_id": result.research_result_id,
                "agent_name": result.agent_name,
                "agent_role": result.agent_role,
                "status": result.status,
                "summary": structured.get("summary") or structured.get("reason"),
                "findings": list(structured.get("findings") or ())[:6],
                "risks": list(structured.get("risks") or ())[:6],
                "evidence_refs": list(result.evidence_refs)[:12],
                "result_hash": result.result_hash,
            }
        )
    return projection


def _failure_meta(
    *,
    profile,
    prompt,
    context_hash: str,
    error_type: str,
    error_message: str,
) -> ModelExecutionMeta:
    now = datetime.now(timezone.utc)
    return ModelExecutionMeta(
        provider=profile.provider,
        model_name=profile.model_name,
        model_version=profile.model_version or profile.model_name,
        prompt_name=prompt.prompt_id,
        prompt_version=prompt.prompt_version,
        started_at=now,
        finished_at=now,
        latency_ms=0,
        execution_status="MODEL_FAILED",
        error_type=error_type,
        error_message=error_message,
        template_hash=prompt.template_hash,
        context_hash=context_hash,
        input_hash=canonical_hash({"context_hash": context_hash}),
        model_profile_id=profile.profile_id,
        model_profile_version=profile.profile_version,
        prompt_id=prompt.prompt_id,
        structured_output_mode=profile.structured_output_mode,
        cost_currency="USD",
    )


class SnapshotResearchRuntime:
    def __init__(self, db, *, provider_runtime=None):
        self.db = db
        self.profiles = ModelProfileRegistry(db)
        self.prompts = PromptProfileRegistry(db)
        self.provider_runtime = provider_runtime or ModelProviderRuntime()
        self.budget = ModelBudgetService(db)
        self.audit = ModelAuditService(db)
        self.repository = ModelRuntimeRepository(db)

    async def _save_result(
        self,
        *,
        analysis_id: str,
        context: ModelRuntimeContext,
        agent_name: str,
        agent_role: str,
        status: str,
        structured_summary: dict[str, Any],
        evidence_refs: list[str],
        model_run_id: str | None,
    ) -> tuple[ResearchAgentResult, bool]:
        identity = {
            "analysis_id": analysis_id,
            "snapshot_id": context.snapshot_id,
            "context_hash": context.context_hash,
            "agent_name": agent_name,
            "agent_role": agent_role,
        }
        result_id = str(
            uuid5(
                NAMESPACE_URL,
                f"alphaguard:research-result:{canonical_hash(identity)}",
            )
        )
        payload = {
            "research_result_id": result_id,
            **identity,
            "status": status,
            "structured_summary": structured_summary,
            "evidence_refs": sorted(set(evidence_refs)),
            "model_run_id": model_run_id,
            "created_at": datetime.now(timezone.utc),
        }
        payload["result_hash"] = canonical_hash(
            payload, exclude={"result_hash", "created_at"}
        )
        result = ResearchAgentResult.model_validate(payload)
        return await self.repository.save_immutable(
            "research_results",
            result,
            identity={"research_result_id": result_id},
            hash_field="result_hash",
        )

    async def run(
        self,
        *,
        analysis_id: str,
        context: ModelRuntimeContext,
        run_mode: str,
        llm: Any | None = None,
        profile_override: Any | None = None,
    ) -> list[ResearchAgentResult]:
        profile = profile_override or await self.profiles.persisted_for_role(
            "RESEARCH_AGENT"
        )
        research_prompt_definition = self.prompts.definition(
            "alphaguard_research_snapshot"
        )
        research_prompt = await self.prompts.persisted(
            research_prompt_definition.prompt_id,
            research_prompt_definition.prompt_version,
        )
        manager_prompt_definition = self.prompts.definition(
            "alphaguard_research_manager_snapshot",
            RESEARCH_MANAGER_CONTRACT_VERSION,
        )
        manager_prompt = await self.prompts.persisted(
            manager_prompt_definition.prompt_id,
            manager_prompt_definition.prompt_version,
        )
        model = llm or await self.provider_runtime.create_registered(
            profile, db=self.db
        )
        results: list[ResearchAgentResult] = []
        for agent_name, agent_role in RESEARCH_ROLES:
            is_manager = agent_name == "research_manager"
            prompt = manager_prompt if is_manager else research_prompt
            schema_model = ResearchManagerOutputV2 if is_manager else ResearchAgentOutput
            output_schema = _context_bound_research_schema(
                context,
                schema_model=schema_model,
            )
            context_json = json.dumps(
                context.payload, ensure_ascii=False, sort_keys=True
            )
            prior_research = _manager_research_projection(results)
            if is_manager:
                rendered = prompt.template.format(
                    context_json=context_json,
                    research_json=json.dumps(
                        prior_research, ensure_ascii=False, sort_keys=True
                    ),
                )
            else:
                rendered = prompt.template.format(
                    agent_role=agent_role,
                    context_json=context_json,
                )
            budget = await self.budget.check(
                profile=profile,
                analysis_id=analysis_id,
                snapshot_id=context.snapshot_id,
                rendered_input=rendered,
            )
            request_hash = canonical_hash(
                {
                    "profile": profile.config_hash,
                    "prompt": prompt.template_hash,
                    "agent_role": agent_role,
                    "context_hash": context.context_hash,
                    "output_contract": (
                        {
                            "contract_id": RESEARCH_MANAGER_CONTRACT_ID,
                            "contract_version": RESEARCH_MANAGER_CONTRACT_VERSION,
                            "schema_hash": RESEARCH_MANAGER_SCHEMA_HASH,
                            "prior_result_hashes": [
                                item.result_hash for item in results
                            ],
                        }
                        if is_manager
                        else {"contract_version": "v1"}
                    ),
                }
            )
            if not budget.allowed:
                meta = _failure_meta(
                    profile=profile,
                    prompt=prompt,
                    context_hash=context.context_hash,
                    error_type=budget.reason_code or "BUDGET_BLOCKED",
                    error_message="model call blocked by configured budget",
                )
                run, _ = await self.audit.record(
                    analysis_id=analysis_id,
                    snapshot_id=context.snapshot_id,
                    context_hash=context.context_hash,
                    run_mode=run_mode,
                    automated_execution_allowed=False,
                    role="RESEARCH_AGENT",
                    agent_name=agent_name,
                    profile=profile,
                    prompt=prompt,
                    request_hash=request_hash,
                    meta=meta,
                    budget=budget,
                )
                result, _ = await self._save_result(
                    analysis_id=analysis_id,
                    context=context,
                    agent_name=agent_name,
                    agent_role=agent_role,
                    status="BUDGET_BLOCKED",
                    structured_summary={"reason": "BUDGET_BLOCKED"},
                    evidence_refs=[],
                    model_run_id=run.model_run_id,
                )
                results.append(result)
                break
            invocation = invoke_json_object(
                llm=model,
                messages=[{"role": "system", "content": rendered}],
                schema_model=schema_model,
                provider=profile.provider,
                configured_model_name=profile.model_name,
                prompt_name=prompt.prompt_id,
                prompt_version=prompt.prompt_version,
                template_hash=prompt.template_hash,
                context_hash=context.context_hash,
                input_hash=request_hash,
                structured_output_mode=profile.structured_output_mode,
                model_profile_id=profile.profile_id,
                model_profile_version=profile.profile_version,
                prompt_id=prompt.prompt_id,
                input_cost_per_million=profile.input_cost_per_million,
                output_cost_per_million=profile.output_cost_per_million,
                cost_currency=profile.cost_currency,
                max_retries=max(0, budget.permitted_attempts - 1),
                retry_backoff_seconds=profile.retry_backoff_seconds,
                schema_override=output_schema,
            )
            run = None
            for meta in invocation.attempt_metas or (invocation.model_meta,):
                run, _ = await self.audit.record(
                    analysis_id=analysis_id,
                    snapshot_id=context.snapshot_id,
                    context_hash=context.context_hash,
                    run_mode=run_mode,
                    automated_execution_allowed=False,
                    role="RESEARCH_AGENT",
                    agent_name=agent_name,
                    profile=profile,
                    prompt=prompt,
                    request_hash=request_hash,
                    meta=meta,
                    budget=budget,
                )
            assert run is not None
            status = invocation.failure_status or "SUCCESS"
            summary: dict[str, Any]
            evidence_refs: list[str]
            if invocation.failure_status is not None:
                summary = {
                    "reason": invocation.error_type or invocation.failure_status,
                }
                evidence_refs = []
            else:
                try:
                    parsed = schema_model.model_validate(invocation.payload or {})
                except ValidationError as exc:
                    status = "INVALID_OUTPUT"
                    fields, error_types = validation_error_projection(exc)
                    summary = {
                        "reason": "STRICT_SCHEMA_VALIDATION_FAILED",
                        "validation_error_fields": list(fields),
                        "validation_error_types": list(error_types),
                    }
                    evidence_refs = []
                else:
                    allowed = set(
                        context.payload.get("allowed_evidence_refs")
                        or context.evidence_refs
                    )
                    unknown = set(parsed.evidence_refs) - allowed
                    if unknown:
                        status = "INVALID_OUTPUT"
                        summary = {
                            "reason": "UNKNOWN_EVIDENCE_REFS",
                            "unknown_evidence_refs": sorted(unknown),
                        }
                        evidence_refs = []
                    else:
                        status = parsed.status
                        summary = parsed.model_dump(mode="json")
                        evidence_refs = parsed.evidence_refs
            result, _ = await self._save_result(
                analysis_id=analysis_id,
                context=context,
                agent_name=agent_name,
                agent_role=agent_role,
                status=status,
                structured_summary=summary,
                evidence_refs=evidence_refs,
                model_run_id=run.model_run_id,
            )
            results.append(result)
            if status not in {"SUCCESS", "INSUFFICIENT_DATA"}:
                break
        return results

    async def disabled_social_result(
        self,
        *,
        analysis_id: str,
        context: ModelRuntimeContext,
    ) -> ResearchAgentResult:
        result, _ = await self._save_result(
            analysis_id=analysis_id,
            context=context,
            agent_name="social_media_analyst",
            agent_role="SOCIAL_MEDIA_ANALYST",
            status="DISABLED_NOT_REQUIRED",
            structured_summary={
                "reason": "no reliable snapshot-bound social source configured"
            },
            evidence_refs=[],
            model_run_id=None,
        )
        return result
