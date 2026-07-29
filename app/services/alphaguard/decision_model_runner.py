"""Existing provider-adapter bridge for the two structured PR-005 nodes."""

from __future__ import annotations

import asyncio
from typing import Any, Protocol

from app.schemas.alphaguard.decision import DecisionContext, RevisionRequest
from tradingagents.agents.managers.risk_manager import create_risk_manager
from tradingagents.agents.trader.trader import create_trader
from tradingagents.alphaguard.decision_schemas import (
    NormalTradePlan,
    TopReviewDecision,
)


class DecisionModelRunner(Protocol):
    async def run_normal(
        self,
        *,
        context: DecisionContext,
        attempt_number: int,
        trace_id: str | None,
        revision_request: RevisionRequest | None = None,
        original_plan: NormalTradePlan | None = None,
    ) -> NormalTradePlan: ...

    async def run_top(
        self,
        *,
        context: DecisionContext,
        plan: NormalTradePlan,
        risk_policy_summary: dict[str, Any],
        attempt_number: int,
        trace_id: str | None,
    ) -> TopReviewDecision: ...


class ExistingProviderDecisionModelRunner:
    def __init__(self, *, normal_node, top_node):
        self.normal_node = normal_node
        self.top_node = top_node

    @staticmethod
    def configured_models(context: DecisionContext) -> tuple[str, str]:
        from .model_profile_registry import ModelProfileRegistry

        registry = ModelProfileRegistry()
        return (
            registry.for_role("NORMAL_TRADER").model_name,
            registry.for_role("TOP_RISK_REVIEWER").model_name,
        )

    @staticmethod
    def _credential_looks_configured(value: Any) -> bool:
        if not value:
            return False
        normalized = str(value).strip().lower()
        if not normalized:
            return False
        placeholder_markers = (
            "your-api-key",
            "your_api_key",
            "your-openai",
            "your_openai",
            "placeholder",
            "replace-me",
            "replace_me",
            "changeme",
        )
        return not any(marker in normalized for marker in placeholder_markers)

    @classmethod
    async def configuration_status(
        cls, context: DecisionContext
    ) -> dict[str, dict[str, Any]]:
        """Return auditable capability state without exposing credentials."""

        from app.services.simple_analysis_service import (
            get_model_config_sync,
            get_provider_and_url_by_model_sync,
        )

        normal_model, top_model = cls.configured_models(context)

        def inspect() -> dict[str, dict[str, Any]]:
            result: dict[str, dict[str, Any]] = {}
            for role, model_name in (
                ("normal", normal_model),
                ("top", top_model),
            ):
                info = get_provider_and_url_by_model_sync(model_name)
                config = get_model_config_sync(model_name)
                credential = info.get("api_key")
                model_registry_configured = bool(config)
                credential_configured = bool(
                    model_registry_configured
                    and cls._credential_looks_configured(credential)
                )
                backend_configured = bool(
                    model_registry_configured and info.get("backend_url")
                )
                result[role] = {
                    "provider": str(info.get("provider") or "unconfigured"),
                    "model_name": model_name,
                    "model_version": model_name,
                    "model_registry_configured": model_registry_configured,
                    # This label is retained for old audit compatibility only.
                    # ``create`` below permanently rejects this path.
                    "configuration_source": (
                        "REGISTERED_MODEL_CONFIG"
                        if model_registry_configured
                        else "DEFAULT_FALLBACK_UNREGISTERED"
                    ),
                    "credential_configured": credential_configured,
                    "backend_configured": backend_configured,
                    "temperature": float(
                        config.get(
                            "temperature",
                            0.2 if role == "normal" else 0.1,
                        )
                    ),
                    "max_tokens": int(config.get("max_tokens", 4000)),
                    "timeout": int(config.get("timeout", 180)),
                    "prompt_version": (
                        context.normal_prompt_version
                        if role == "normal"
                        else context.top_prompt_version
                    ),
                    "structured_output_capability": backend_configured,
                    "pricing_status": "UNAVAILABLE",
                    "status": (
                        "CONFIGURED"
                        if (
                            model_registry_configured
                            and credential_configured
                            and backend_configured
                        )
                        else "MODEL_NOT_CONFIGURED"
                    ),
                }
            return result

        return await asyncio.to_thread(inspect)

    @classmethod
    async def create(cls, context: DecisionContext):
        raise RuntimeError(
            "legacy default-model construction is disabled; use "
            "ProfiledDecisionModelRunner with persisted exact profiles"
        )

    @staticmethod
    def _base_state(
        context: DecisionContext,
        *,
        attempt_number: int,
        trace_id: str | None,
    ) -> dict[str, Any]:
        return {
            "analysis_id": context.analysis_id,
            "snapshot_id": context.snapshot_id,
            "company_of_interest": context.symbol,
            "trade_date": context.trade_date.isoformat(),
            "market": context.market,
            "legacy_analysis": False,
            "decision_context": context.model_dump(mode="json"),
            "quant_trade_proposal": context.quant_proposal.model_dump(mode="json"),
            "attempt_number": attempt_number,
            "trace_id": trace_id,
            "risk_debate_state": {},
        }

    async def run_normal(
        self,
        *,
        context: DecisionContext,
        attempt_number: int,
        trace_id: str | None,
        revision_request: RevisionRequest | None = None,
        original_plan: NormalTradePlan | None = None,
    ) -> NormalTradePlan:
        state = self._base_state(
            context, attempt_number=attempt_number, trace_id=trace_id
        )
        if revision_request:
            state["revision_request"] = revision_request.model_dump(mode="json")
            state["original_normal_trade_plan"] = original_plan.model_dump(mode="json")
        result = await asyncio.to_thread(self.normal_node, state)
        return NormalTradePlan.model_validate(result["normal_trade_plan"])

    async def run_top(
        self,
        *,
        context: DecisionContext,
        plan: NormalTradePlan,
        risk_policy_summary: dict[str, Any],
        attempt_number: int,
        trace_id: str | None,
    ) -> TopReviewDecision:
        state = self._base_state(
            context, attempt_number=attempt_number, trace_id=trace_id
        )
        state["normal_trade_plan"] = plan.model_dump(mode="json")
        state["risk_policy_summary"] = risk_policy_summary
        result = await asyncio.to_thread(self.top_node, state)
        return TopReviewDecision.model_validate(result["top_review_decision"])
