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
            "input_tokens": meta.input_tokens,
            "output_tokens": meta.output_tokens,
            "total_tokens": meta.total_tokens,
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
