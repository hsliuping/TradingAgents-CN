"""Snapshot-bound TradingAgents research roles with no tools or latest queries."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any, Literal
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.schemas.alphaguard.decision import canonical_hash
from app.schemas.alphaguard.model_runtime import (
    ResearchAgentResult,
)
from tradingagents.alphaguard.decision_schemas import ModelExecutionMeta
from tradingagents.alphaguard.structured_output import invoke_json_object

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


class ResearchAgentOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    status: Literal["SUCCESS", "INSUFFICIENT_DATA"]
    summary: str = Field(min_length=1)
    findings: list[str]
    risks: list[str]
    evidence_refs: list[str]


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
    ) -> list[ResearchAgentResult]:
        profile = await self.profiles.persisted_for_role("RESEARCH_AGENT")
        prompt = await self.prompts.persisted(
            profile.prompt_profile_id,
            self.prompts.definition(profile.prompt_profile_id).prompt_version,
        )
        model = llm or await self.provider_runtime.create_registered(
            profile, db=self.db
        )
        results: list[ResearchAgentResult] = []
        for agent_name, agent_role in RESEARCH_ROLES:
            rendered = prompt.template.format(
                agent_role=agent_role,
                context_json=json.dumps(
                    context.payload, ensure_ascii=False, sort_keys=True
                ),
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
                schema_model=ResearchAgentOutput,
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
                )
            assert run is not None
            status = invocation.failure_status or "SUCCESS"
            summary: dict[str, Any]
            evidence_refs: list[str]
            try:
                parsed = ResearchAgentOutput.model_validate(
                    invocation.payload or {}
                )
                unknown = set(parsed.evidence_refs) - set(context.evidence_refs)
                if unknown:
                    raise ValueError("research references evidence outside Snapshot")
                status = parsed.status
                summary = parsed.model_dump(mode="json")
                evidence_refs = parsed.evidence_refs
            except (ValidationError, ValueError):
                status = "INVALID_OUTPUT"
                summary = {"reason": "STRICT_SCHEMA_OR_EVIDENCE_VALIDATION_FAILED"}
                evidence_refs = []
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
