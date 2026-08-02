"""Secret-free, immutable audit records for every formal model call."""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from app.schemas.alphaguard.decision import canonical_hash
from app.schemas.alphaguard.model_runtime import (
    ModelProfile,
    ModelRunRecord,
    PromptProfile,
)
from tradingagents.alphaguard.decision_schemas import ModelExecutionMeta

from .model_runtime_repository import ModelRuntimeRepository
from .model_budget_service import BudgetDecision


def sanitize_model_message(value: Any) -> str:
    text = str(value or "unspecified model runtime error")
    text = re.sub(
        r"(?i)(authorization|api[-_ ]?key|access[-_ ]?token|bearer)"
        r"(\s*[:=]\s*|\s+)[^\s,;]+",
        r"\1=[REDACTED]",
        text,
    )
    text = re.sub(r"\bsk-[A-Za-z0-9_-]{8,}\b", "[REDACTED]", text)
    return text[:500]


class ModelAuditService:
    def __init__(self, db):
        self.repository = ModelRuntimeRepository(db)

    async def record(
        self,
        *,
        analysis_id: str,
        snapshot_id: str | None,
        context_hash: str | None,
        run_mode: str,
        automated_execution_allowed: bool,
        role: str,
        agent_name: str,
        profile: ModelProfile,
        prompt: PromptProfile,
        request_hash: str,
        meta: ModelExecutionMeta,
        response_hash: str | None = None,
        budget: BudgetDecision | None = None,
    ) -> tuple[ModelRunRecord, bool]:
        identity = {
            "analysis_id": analysis_id,
            "snapshot_id": snapshot_id,
            "run_mode": run_mode,
            "role": role,
            "agent_name": agent_name,
            "profile_id": profile.profile_id,
            "profile_version": profile.profile_version,
            "prompt_id": prompt.prompt_id,
            "prompt_version": prompt.prompt_version,
            "request_hash": request_hash,
            "attempt": meta.attempt_number,
        }
        model_run_id = str(
            uuid5(NAMESPACE_URL, f"alphaguard:model-run:{canonical_hash(identity)}")
        )
        remaining_context_capacity = None
        context_usage_ratio = None
        context_warning_level = None
        if budget is not None:
            used_context_tokens = (
                meta.input_tokens + meta.output_tokens
                if meta.input_tokens is not None and meta.output_tokens is not None
                else budget.estimated_input_tokens + budget.estimated_output_tokens
            )
            remaining_context_capacity = max(
                0, budget.model_context_window - used_context_tokens
            )
            context_usage_ratio = used_context_tokens / budget.model_context_window
            if context_usage_ratio > 0.95:
                context_warning_level = "OVER_95"
            elif context_usage_ratio > 0.85:
                context_warning_level = "OVER_85"
            elif context_usage_ratio > 0.70:
                context_warning_level = "OVER_70"
            else:
                context_warning_level = "NONE"
        payload = {
            "model_run_id": model_run_id,
            "analysis_id": analysis_id,
            "snapshot_id": snapshot_id,
            "context_hash": context_hash,
            "run_mode": run_mode,
            "automated_execution_allowed": automated_execution_allowed,
            "role": role,
            "agent_name": agent_name,
            "provider": profile.provider,
            "model_profile_id": profile.profile_id,
            "model_profile_version": profile.profile_version,
            "model_name": profile.model_name,
            "model_version": profile.model_version,
            "prompt_id": prompt.prompt_id,
            "prompt_version": prompt.prompt_version,
            "prompt_hash": prompt.template_hash,
            "request_hash": request_hash,
            "response_hash": response_hash or meta.raw_output_hash,
            "structured_output_status": meta.execution_status,
            "estimated_input_tokens": (
                budget.estimated_input_tokens if budget else None
            ),
            "input_tokens": meta.input_tokens,
            "output_tokens": meta.output_tokens,
            "total_tokens": meta.total_tokens,
            "model_context_window": (
                budget.model_context_window if budget else None
            ),
            "configured_max_output_tokens": (
                budget.estimated_output_tokens if budget else None
            ),
            "remaining_context_capacity": remaining_context_capacity,
            "context_usage_ratio": context_usage_ratio,
            "context_warning_level": context_warning_level,
            "estimated_cost": meta.estimated_cost,
            "cost_currency": meta.cost_currency or "USD",
            "latency_ms": meta.latency_ms,
            "attempt": meta.attempt_number,
            "error_category": meta.error_type,
            "error_code": meta.error_type,
            "sanitized_message": (
                sanitize_model_message(meta.error_message)
                if meta.error_message
                else None
            ),
            "created_at": meta.finished_at or datetime.now(timezone.utc),
        }
        payload["record_hash"] = canonical_hash(
            payload,
            exclude={"record_hash", "created_at"},
        )
        record = ModelRunRecord.model_validate(payload)
        return await self.repository.save_immutable(
            "runs",
            record,
            identity={"model_run_id": model_run_id},
            hash_field="record_hash",
        )
