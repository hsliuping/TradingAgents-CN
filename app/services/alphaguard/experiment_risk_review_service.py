"""Top-model experiment risk review with no promotion authority."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Protocol
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.services.alphaguard.experiment_audit_service import ExperimentAuditService
from app.services.alphaguard.experiment_registry import ExperimentRegistry
from app.services.alphaguard.experiment_repository import ExperimentRepository
from tradingagents.alphaguard.experiment_schemas import (
    EXPERIMENT_RISK_PROMPT_VERSION,
    ChampionComparisonReport,
    ExperimentRiskReview,
    experiment_hash,
)
from tradingagents.alphaguard.structured_output import (
    StructuredInvocation,
    invoke_json_object,
    not_run_meta,
)


EXPERIMENT_RISK_PROMPT = """You are AlphaGuard's experiment risk reviewer.
You have no authority to promote, modify results, change thresholds, bypass a
leakage failure, or write production configuration. Review all positive,
negative, insufficient and rollback evidence. Return exactly one object that
matches the supplied JSON schema. READY_FOR_HUMAN_REVIEW only means an
administrator may consider a separate promotion request.
"""


class ExperimentRiskReviewBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    status: str
    leakage_concerns: list[str] = Field(default_factory=list)
    overfitting_concerns: list[str] = Field(default_factory=list)
    sample_concerns: list[str] = Field(default_factory=list)
    regime_concerns: list[str] = Field(default_factory=list)
    execution_concerns: list[str] = Field(default_factory=list)
    rollback_concerns: list[str] = Field(default_factory=list)
    required_followups: list[str] = Field(default_factory=list)
    risk_summary: str = Field(min_length=1)


class ExperimentRiskModelRunner(Protocol):
    async def invoke(
        self,
        payload: dict[str, Any],
        *,
        trace_id: str | None,
        input_hash: str,
    ) -> StructuredInvocation: ...


class ExistingTopModelExperimentRiskRunner:
    def __init__(self, *, llm, provider: str, model_name: str):
        self.llm = llm
        self.provider = provider
        self.model_name = model_name

    @classmethod
    async def create(cls) -> "ExistingTopModelExperimentRiskRunner":
        from app.services.simple_analysis_service import (
            get_model_config_sync,
            get_provider_and_url_by_model_sync,
        )
        from tradingagents.default_config import DEFAULT_CONFIG
        from tradingagents.graph.trading_graph import create_llm_by_provider

        model_name = DEFAULT_CONFIG["deep_think_llm"]

        def construct():
            info = get_provider_and_url_by_model_sync(model_name)
            config = get_model_config_sync(model_name)
            llm = create_llm_by_provider(
                provider=info["provider"],
                model=model_name,
                backend_url=info.get("backend_url") or "",
                temperature=float(config.get("temperature", 0.1)),
                max_tokens=int(config.get("max_tokens", 4000)),
                timeout=int(config.get("timeout", 180)),
                api_key=info.get("api_key"),
            )
            return llm, info["provider"]

        llm, provider = await asyncio.to_thread(construct)
        return cls(llm=llm, provider=provider, model_name=model_name)

    async def invoke(
        self,
        payload: dict[str, Any],
        *,
        trace_id: str | None,
        input_hash: str,
    ) -> StructuredInvocation:
        messages = [
            {
                "role": "system",
                "content": EXPERIMENT_RISK_PROMPT,
            },
            {
                "role": "user",
                "content": (
                    "Review this immutable experiment evidence. Do not omit "
                    f"negative results:\n{payload}"
                ),
            },
        ]
        return await asyncio.to_thread(
            invoke_json_object,
            llm=self.llm,
            messages=messages,
            schema_model=ExperimentRiskReviewBody,
            provider=self.provider,
            configured_model_name=self.model_name,
            prompt_name="experiment_risk_review",
            prompt_version=EXPERIMENT_RISK_PROMPT_VERSION,
            trace_id=trace_id,
            template_hash=experiment_hash(EXPERIMENT_RISK_PROMPT),
            context_hash=input_hash,
            input_hash=input_hash,
        )


class ExperimentRiskReviewService:
    def __init__(self, db, *, runner: ExperimentRiskModelRunner | None = None):
        self.db = db
        self.runner = runner
        self.registry = ExperimentRegistry(db)
        self.repository = ExperimentRepository(db)
        self.audit = ExperimentAuditService(db)

    async def review(
        self,
        experiment_id: str,
        *,
        comparison_report_id: str,
        trace_id: str | None = None,
        now: datetime | None = None,
    ) -> ExperimentRiskReview:
        now = now or datetime.utcnow()
        definition = await self.registry.get(experiment_id)
        raw = await self.repository.get(
            "comparison_reports",
            {"comparison_report_id": comparison_report_id},
        )
        if raw is None:
            raise LookupError("ChampionComparisonReport does not exist")
        report = ChampionComparisonReport.model_validate(raw)
        if report.experiment_id != experiment_id:
            raise ValueError("comparison belongs to another experiment")
        if report.status != "READY":
            raise ValueError("only READY comparison can enter top risk review")
        runs = await self.repository.list(
            "runs", {"experiment_id": experiment_id}
        )
        run_ids = [item["run_id"] for item in runs]
        leakage = await self.repository.list(
            "leakage_audits", {"run_id": {"$in": run_ids}}
        )
        robustness = await self.repository.list(
            "robustness_reports", {"run_id": {"$in": run_ids}}
        )
        shadows = await self.repository.list(
            "shadow_runs", {"experiment_id": experiment_id}
        )
        assignments = await self.repository.list(
            "challenger_assignments", {"experiment_id": experiment_id}
        )
        if not leakage or any(item["status"] != "PASS" for item in leakage):
            raise ValueError("leakage audit PASS is required")
        if not robustness:
            raise ValueError("robustness report is required")
        evidence = {
            "experiment": definition.model_dump(mode="json"),
            "comparison": report.model_dump(mode="json"),
            "leakage_audits": leakage,
            "robustness_reports": robustness,
            "shadow_runs": shadows,
            "challenger_assignments": assignments,
            "rollback_plan": {
                "previous_version_ref": definition.baseline_version_ref,
                "delete_historical_objects": False,
                "affects_only_future_tasks": True,
            },
        }
        input_hash = experiment_hash(evidence)
        runner = self.runner
        if runner is None:
            try:
                runner = await ExistingTopModelExperimentRiskRunner.create()
            except Exception as exc:
                meta = not_run_meta(
                    llm=object(),
                    provider="unconfigured",
                    configured_model_name="unconfigured",
                    prompt_name="experiment_risk_review",
                    prompt_version=EXPERIMENT_RISK_PROMPT_VERSION,
                    error_type="PROMPT_CONFIGURATION_ERROR",
                    error_message=str(exc),
                    trace_id=trace_id,
                    template_hash=experiment_hash(EXPERIMENT_RISK_PROMPT),
                    context_hash=input_hash,
                    input_hash=input_hash,
                )
                invocation = StructuredInvocation(
                    payload=None,
                    model_meta=meta,
                    failure_status="MODEL_FAILED",
                    error_type=meta.error_type,
                    error_message=meta.error_message,
                )
            else:
                invocation = await runner.invoke(
                    evidence, trace_id=trace_id, input_hash=input_hash
                )
        else:
            invocation = await runner.invoke(
                evidence, trace_id=trace_id, input_hash=input_hash
            )
        if invocation.failure_status:
            body = {
                "status": invocation.failure_status,
                "leakage_concerns": [],
                "overfitting_concerns": [],
                "sample_concerns": [],
                "regime_concerns": [],
                "execution_concerns": [],
                "rollback_concerns": [],
                "required_followups": [
                    invocation.error_type or "MODEL_EXECUTION_FAILED"
                ],
                "risk_summary": (
                    "Experiment risk review did not complete; promotion is blocked."
                ),
            }
        else:
            try:
                parsed = ExperimentRiskReviewBody.model_validate(
                    invocation.payload
                )
                if parsed.status not in {
                    "READY_FOR_HUMAN_REVIEW",
                    "MORE_VALIDATION_REQUIRED",
                    "REJECT",
                    "SUSPEND",
                }:
                    raise ValueError("invalid experiment risk status")
                body = parsed.model_dump(mode="python")
            except (ValidationError, ValueError):
                body = {
                    "status": "INVALID_OUTPUT",
                    "leakage_concerns": [],
                    "overfitting_concerns": [],
                    "sample_concerns": [],
                    "regime_concerns": [],
                    "execution_concerns": [],
                    "rollback_concerns": [],
                    "required_followups": ["SCHEMA_VALIDATION_ERROR"],
                    "risk_summary": (
                        "Experiment risk review output was invalid; promotion is blocked."
                    ),
                }
                invocation = StructuredInvocation(
                    payload=None,
                    model_meta=invocation.model_meta.model_copy(
                        update={
                            "execution_status": "INVALID_OUTPUT",
                            "error_type": "SCHEMA_VALIDATION_ERROR",
                            "error_message": (
                                "experiment risk review failed schema validation"
                            ),
                        }
                    ),
                    failure_status="INVALID_OUTPUT",
                    error_type="SCHEMA_VALIDATION_ERROR",
                    error_message="schema validation failed",
                )
        output_hash = experiment_hash(body)
        review = ExperimentRiskReview(
            review_id=str(
                uuid5(
                    NAMESPACE_URL,
                    f"alphaguard:experiment-risk-review:"
                    f"{experiment_id}:{comparison_report_id}:{input_hash}:"
                    f"{output_hash}",
                )
            ),
            experiment_id=experiment_id,
            comparison_report_id=comparison_report_id,
            model_meta=invocation.model_meta,
            input_hash=input_hash,
            output_hash=output_hash,
            created_at=now,
            **body,
        )
        stored, created = await self.repository.save_immutable(
            "risk_reviews",
            review,
            identity={"review_id": review.review_id},
            hash_field="output_hash",
        )
        if created:
            await self.audit.record(
                "EXPERIMENT_RISK_REVIEW_CREATED",
                f"top experiment risk review status={stored.status}",
                experiment_id=experiment_id,
                comparison_report_id=comparison_report_id,
                risk_review_id=stored.review_id,
                user_id=definition.user_id,
                market=definition.market,
                input_hash=stored.input_hash,
                result_hash=stored.output_hash,
            )
        return stored
