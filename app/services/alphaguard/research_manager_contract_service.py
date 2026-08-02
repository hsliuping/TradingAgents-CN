"""One-call, non-executable validation for the research-manager v2 contract."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from pydantic import ValidationError

from app.schemas.alphaguard.decision import canonical_hash
from app.schemas.alphaguard.model_runtime import ResearchManagerContractCheck
from tradingagents.alphaguard.structured_output import (
    invoke_json_object,
    model_output_schema,
    not_run_meta,
)

from .model_audit_service import ModelAuditService
from .model_budget_service import ModelBudgetService
from .model_profile_registry import ModelProfileRegistry
from .model_provider_runtime import ModelProviderRuntime
from .model_runtime_repository import ModelRuntimeRepository
from .prompt_profile_registry import PromptProfileRegistry
from .snapshot_research_runtime import (
    RESEARCH_MANAGER_CONTRACT_ID,
    RESEARCH_MANAGER_CONTRACT_VERSION,
    RESEARCH_MANAGER_SCHEMA_HASH,
    ResearchManagerOutputV2,
    normalized_payload_shape,
    validation_error_projection,
)


CAPABILITY_EVIDENCE_REF = "capability:evidence:immutable"


class ResearchManagerContractService:
    def __init__(self, db, *, provider_runtime=None):
        self.db = db
        self.profiles = ModelProfileRegistry(db)
        self.prompts = PromptProfileRegistry(db)
        self.provider_runtime = provider_runtime or ModelProviderRuntime()
        self.budget = ModelBudgetService(db)
        self.audit = ModelAuditService(db)
        self.repository = ModelRuntimeRepository(db)

    @staticmethod
    def _stable_id(payload: dict[str, Any]) -> str:
        return str(
            uuid5(
                NAMESPACE_URL,
                f"alphaguard:research-manager-contract-check:{canonical_hash(payload)}",
            )
        )

    async def check(
        self,
        *,
        checked_by: str,
        idempotency_key: str,
        llm: Any | None = None,
    ) -> ResearchManagerContractCheck:
        profile = await self.profiles.persisted_for_role("NORMAL_TRADER")
        prompt_definition = self.prompts.definition(
            "alphaguard_research_manager_snapshot",
            RESEARCH_MANAGER_CONTRACT_VERSION,
        )
        prompt = await self.prompts.persisted(
            prompt_definition.prompt_id,
            prompt_definition.prompt_version,
        )
        context_payload = {
            "run_mode": "MODEL_CAPABILITY_CHECK",
            "automated_execution_allowed": False,
            "snapshot_id": "contract-capability-snapshot-v2",
            "context_hash": canonical_hash(
                {
                    "contract_id": RESEARCH_MANAGER_CONTRACT_ID,
                    "contract_version": RESEARCH_MANAGER_CONTRACT_VERSION,
                }
            ),
            "allowed_evidence_refs": [CAPABILITY_EVIDENCE_REF],
        }
        prior_research = [
            {
                "research_result_id": f"capability-{index}",
                "agent_name": agent_name,
                "agent_role": agent_role,
                "status": "SUCCESS",
                "summary": "Synthetic contract-check evidence is complete.",
                "findings": ["The immutable test reference is available."],
                "risks": [],
                "evidence_refs": [CAPABILITY_EVIDENCE_REF],
                "result_hash": canonical_hash(
                    {"index": index, "evidence_ref": CAPABILITY_EVIDENCE_REF}
                ),
            }
            for index, (agent_name, agent_role) in enumerate(
                (
                    ("market_analyst", "MARKET_ANALYST"),
                    ("fundamentals_analyst", "FUNDAMENTALS_ANALYST"),
                    ("news_announcement_analyst", "NEWS_ANNOUNCEMENT_ANALYST"),
                    ("bull_researcher", "BULL_RESEARCHER"),
                    ("bear_researcher", "BEAR_RESEARCHER"),
                ),
                start=1,
            )
        ]
        rendered = prompt.template.format(
            context_json=json.dumps(
                context_payload, ensure_ascii=False, sort_keys=True
            ),
            research_json=json.dumps(
                prior_research, ensure_ascii=False, sort_keys=True
            ),
        )
        identity = {
            "checked_by": checked_by,
            "idempotency_key": idempotency_key,
            "contract_id": RESEARCH_MANAGER_CONTRACT_ID,
            "contract_version": RESEARCH_MANAGER_CONTRACT_VERSION,
            "schema_hash": RESEARCH_MANAGER_SCHEMA_HASH,
            "prompt_hash": prompt.template_hash,
            "profile_hash": profile.config_hash,
            "run_mode": "MODEL_CAPABILITY_CHECK",
        }
        contract_check_id = self._stable_id(identity)
        existing = await self.repository.get(
            "contract_checks", {"contract_check_id": contract_check_id}
        )
        if existing is not None:
            return ResearchManagerContractCheck.model_validate(existing)

        request_hash = canonical_hash(
            {
                "identity": identity,
                "context_hash": context_payload["context_hash"],
                "prior_result_hashes": [
                    item["result_hash"] for item in prior_research
                ],
            }
        )
        analysis_id = f"model-capability:research-manager:{contract_check_id}"
        budget = await self.budget.check(
            profile=profile,
            analysis_id=analysis_id,
            snapshot_id=str(context_payload["snapshot_id"]),
            rendered_input=rendered,
        )
        invocation = None
        run = None
        status = "BUDGET_BLOCKED"
        fields: tuple[str, ...] = ()
        field_types: tuple[str, ...] = ()
        error_fields: tuple[str, ...] = ()
        error_types: tuple[str, ...] = ()
        if not budget.allowed:
            meta = not_run_meta(
                llm=llm or object(),
                provider=profile.provider,
                configured_model_name=profile.model_name,
                prompt_name=prompt.prompt_id,
                prompt_version=prompt.prompt_version,
                error_type=budget.reason_code or "BUDGET_BLOCKED",
                error_message="contract check blocked by configured budget",
                template_hash=prompt.template_hash,
                context_hash=str(context_payload["context_hash"]),
                input_hash=request_hash,
            )
            run, _ = await self.audit.record(
                analysis_id=analysis_id,
                snapshot_id=str(context_payload["snapshot_id"]),
                context_hash=str(context_payload["context_hash"]),
                run_mode="MODEL_CAPABILITY_CHECK",
                automated_execution_allowed=False,
                role="RESEARCH_AGENT",
                agent_name="research_manager_contract_check",
                profile=profile,
                prompt=prompt,
                request_hash=request_hash,
                meta=meta,
                budget=budget,
            )
        else:
            model = llm or await self.provider_runtime.create_registered(
                profile, db=self.db
            )
            schema = model_output_schema(ResearchManagerOutputV2)
            schema["properties"]["evidence_refs"] = {
                "description": "Use only the immutable capability evidence ID.",
                "items": {"enum": [CAPABILITY_EVIDENCE_REF], "type": "string"},
                "title": "Evidence Refs",
                "type": "array",
            }
            invocation = invoke_json_object(
                llm=model,
                messages=[{"role": "system", "content": rendered}],
                schema_model=ResearchManagerOutputV2,
                provider=profile.provider,
                configured_model_name=profile.model_name,
                prompt_name=prompt.prompt_id,
                prompt_version=prompt.prompt_version,
                template_hash=prompt.template_hash,
                context_hash=str(context_payload["context_hash"]),
                input_hash=request_hash,
                structured_output_mode=profile.structured_output_mode,
                model_profile_id=profile.profile_id,
                model_profile_version=profile.profile_version,
                prompt_id=prompt.prompt_id,
                input_cost_per_million=profile.input_cost_per_million,
                output_cost_per_million=profile.output_cost_per_million,
                cost_currency=profile.cost_currency,
                max_retries=0,
                schema_override=schema,
            )
            for meta in invocation.attempt_metas or (invocation.model_meta,):
                run, _ = await self.audit.record(
                    analysis_id=analysis_id,
                    snapshot_id=str(context_payload["snapshot_id"]),
                    context_hash=str(context_payload["context_hash"]),
                    run_mode="MODEL_CAPABILITY_CHECK",
                    automated_execution_allowed=False,
                    role="RESEARCH_AGENT",
                    agent_name="research_manager_contract_check",
                    profile=profile,
                    prompt=prompt,
                    request_hash=request_hash,
                    meta=meta,
                    budget=budget,
                )
            fields, field_types = normalized_payload_shape(invocation.payload)
            if invocation.failure_status is not None:
                status = "MODEL_FAILED"
            else:
                try:
                    parsed = ResearchManagerOutputV2.model_validate(
                        invocation.payload or {}
                    )
                except ValidationError as exc:
                    status = "INVALID_OUTPUT"
                    error_fields, error_types = validation_error_projection(exc)
                else:
                    unknown = set(parsed.evidence_refs) - {CAPABILITY_EVIDENCE_REF}
                    if unknown:
                        status = "INVALID_OUTPUT"
                        error_fields = ("evidence_refs",)
                        error_types = ("unknown_evidence_ref",)
                    else:
                        status = "READY"
        assert run is not None
        meta = invocation.model_meta if invocation is not None else None
        checked_at = datetime.now(timezone.utc)
        payload = {
            "contract_check_id": contract_check_id,
            "contract_id": RESEARCH_MANAGER_CONTRACT_ID,
            "contract_version": RESEARCH_MANAGER_CONTRACT_VERSION,
            "schema_hash": RESEARCH_MANAGER_SCHEMA_HASH,
            "prompt_id": prompt.prompt_id,
            "prompt_version": prompt.prompt_version,
            "prompt_hash": prompt.template_hash,
            "profile_id": profile.profile_id,
            "profile_version": profile.profile_version,
            "status": status,
            "model_run_id": run.model_run_id,
            "request_hash": request_hash,
            "response_hash": run.response_hash,
            "payload_fields": fields,
            "payload_field_types": field_types,
            "validation_error_fields": error_fields,
            "validation_error_types": error_types,
            "input_tokens": meta.input_tokens if meta else None,
            "output_tokens": meta.output_tokens if meta else None,
            "total_tokens": meta.total_tokens if meta else None,
            "latency_ms": meta.latency_ms if meta else 0,
            "checked_by": checked_by,
            "checked_at": checked_at,
            "input_hash": canonical_hash(identity),
        }
        payload["result_hash"] = canonical_hash(
            payload,
            exclude={"result_hash", "checked_at"},
        )
        result = ResearchManagerContractCheck.model_validate(payload)
        saved, _ = await self.repository.save_immutable(
            "contract_checks",
            result,
            identity={"contract_check_id": contract_check_id},
            hash_field="result_hash",
        )
        return saved
