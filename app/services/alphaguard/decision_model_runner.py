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
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import create_llm_by_provider


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

    @classmethod
    async def create(cls, context: DecisionContext):
        from app.services.simple_analysis_service import (
            get_model_config_sync,
            get_provider_and_url_by_model_sync,
        )

        normal_model = (
            context.quant_proposal.model_extra or {}
        ).get("normal_model_version") if context.quant_proposal.model_extra else None
        normal_model = normal_model or DEFAULT_CONFIG["quick_think_llm"]
        top_model = DEFAULT_CONFIG["deep_think_llm"]

        def construct():
            normal_info = get_provider_and_url_by_model_sync(normal_model)
            top_info = get_provider_and_url_by_model_sync(top_model)
            normal_config = get_model_config_sync(normal_model)
            top_config = get_model_config_sync(top_model)
            normal_llm = create_llm_by_provider(
                provider=normal_info["provider"],
                model=normal_model,
                backend_url=normal_info.get("backend_url") or "",
                temperature=float(normal_config.get("temperature", 0.2)),
                max_tokens=int(normal_config.get("max_tokens", 4000)),
                timeout=int(normal_config.get("timeout", 180)),
                api_key=normal_info.get("api_key"),
            )
            top_llm = create_llm_by_provider(
                provider=top_info["provider"],
                model=top_model,
                backend_url=top_info.get("backend_url") or "",
                temperature=float(top_config.get("temperature", 0.1)),
                max_tokens=int(top_config.get("max_tokens", 4000)),
                timeout=int(top_config.get("timeout", 180)),
                api_key=top_info.get("api_key"),
            )
            config = {
                "quick_provider": normal_info["provider"],
                "deep_provider": top_info["provider"],
                "quick_think_llm": normal_model,
                "deep_think_llm": top_model,
            }
            return (
                create_trader(normal_llm, None, config),
                create_risk_manager(top_llm, None, config),
            )

        normal_node, top_node = await asyncio.to_thread(construct)
        return cls(normal_node=normal_node, top_node=top_node)

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
