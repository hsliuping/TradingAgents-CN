"""Fail-closed model-context, call-count and daily-cost budgets."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
from typing import Any

from app.schemas.alphaguard.model_runtime import ModelProfile

from .model_runtime_config import load_model_runtime_config


@dataclass(frozen=True)
class BudgetDecision:
    allowed: bool
    status: str
    estimated_input_tokens: int
    estimated_output_tokens: int
    estimated_cost: float | None
    remaining_daily_calls: int
    remaining_daily_cost: float | None
    model_context_window: int
    remaining_context_capacity: int
    context_usage_ratio: float
    context_warning_level: str
    permitted_attempts: int = 1
    reason_code: str | None = None


class ModelBudgetService:
    def __init__(self, db):
        self.db = db
        self.policy = load_model_runtime_config()["budget_policy"]

    @staticmethod
    def estimate_input_tokens(value: str) -> int:
        # Deliberately conservative and deterministic. It is a pre-call safety
        # estimate only; provider-reported usage remains the audited truth.
        return max(1, math.ceil(len(value.encode("utf-8")) / 3))

    async def check(
        self,
        *,
        profile: ModelProfile,
        analysis_id: str,
        snapshot_id: str | None,
        rendered_input: str,
    ) -> BudgetDecision:
        estimated_input = self.estimate_input_tokens(rendered_input)
        estimated_output = profile.max_output_tokens
        now = datetime.now(timezone.utc)
        day_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
        daily_rows = await self.db["ag_model_runs"].find(
            {"created_at": {"$gte": day_start}}
        ).to_list(length=None)
        analysis_rows = [
            row for row in daily_rows if row.get("analysis_id") == analysis_id
        ]
        daily_cost = sum(
            float(row.get("estimated_cost") or 0) for row in daily_rows
        )
        remaining_calls = max(0, self.policy.max_daily_calls - len(daily_rows))
        remaining_cost = max(0.0, self.policy.max_daily_cost - daily_cost)
        remaining_analysis_calls = max(
            0,
            self.policy.max_calls_per_analysis - len(analysis_rows),
        )
        model_context_window = profile.max_input_tokens
        estimated_context_tokens = estimated_input + estimated_output
        remaining_context_capacity = max(
            0, model_context_window - estimated_context_tokens
        )
        context_usage_ratio = estimated_context_tokens / model_context_window
        if context_usage_ratio > 0.95:
            context_warning_level = "OVER_95"
        elif context_usage_ratio > 0.85:
            context_warning_level = "OVER_85"
        elif context_usage_ratio > 0.70:
            context_warning_level = "OVER_70"
        else:
            context_warning_level = "NONE"

        estimated_cost = None
        if (
            profile.input_cost_per_million is not None
            and profile.output_cost_per_million is not None
            and profile.cost_currency == self.policy.currency
        ):
            estimated_cost = (
                estimated_input * profile.input_cost_per_million
                + estimated_output * profile.output_cost_per_million
            ) / 1_000_000

        status = "READY"
        if estimated_context_tokens > model_context_window:
            status = "MODEL_CONTEXT_WINDOW_EXCEEDED"
        elif len(analysis_rows) >= self.policy.max_calls_per_analysis:
            status = "ANALYSIS_CALL_BUDGET_EXCEEDED"
        elif len(daily_rows) >= self.policy.max_daily_calls:
            status = "DAILY_CALL_BUDGET_EXCEEDED"
        elif profile.cost_currency != self.policy.currency:
            status = "BUDGET_CURRENCY_MISMATCH"
        elif estimated_cost is None:
            status = "BUDGET_PRICING_UNAVAILABLE"
        elif daily_cost + estimated_cost > self.policy.max_daily_cost:
            status = "DAILY_COST_BUDGET_EXCEEDED"
        cost_attempts = (
            int(remaining_cost // estimated_cost)
            if estimated_cost and estimated_cost > 0
            else 0
            if estimated_cost is None
            else self.policy.max_calls_per_analysis
        )
        permitted_attempts = (
            min(
                1 + profile.max_retries,
                remaining_calls,
                remaining_analysis_calls,
                cost_attempts,
            )
            if status == "READY"
            else 0
        )
        return BudgetDecision(
            allowed=status == "READY",
            status=status if status == "READY" else "BUDGET_BLOCKED",
            estimated_input_tokens=estimated_input,
            estimated_output_tokens=estimated_output,
            estimated_cost=estimated_cost,
            remaining_daily_calls=remaining_calls,
            remaining_daily_cost=remaining_cost,
            model_context_window=model_context_window,
            remaining_context_capacity=remaining_context_capacity,
            context_usage_ratio=context_usage_ratio,
            context_warning_level=context_warning_level,
            permitted_attempts=max(0, permitted_attempts),
            reason_code=None if status == "READY" else status,
        )

    async def summary(self) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        day_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
        rows = await self.db["ag_model_runs"].find(
            {"created_at": {"$gte": day_start}}
        ).to_list(length=None)
        used_cost = sum(float(row.get("estimated_cost") or 0) for row in rows)
        return {
            "policy_id": self.policy.policy_id,
            "policy_version": self.policy.policy_version,
            "daily_calls": len(rows),
            "max_daily_calls": self.policy.max_daily_calls,
            "daily_cost": used_cost,
            "max_daily_cost": self.policy.max_daily_cost,
            "currency": self.policy.currency,
            "remaining_calls": max(0, self.policy.max_daily_calls - len(rows)),
            "remaining_cost": max(0.0, self.policy.max_daily_cost - used_cost),
        }
