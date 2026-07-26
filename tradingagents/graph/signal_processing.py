"""Read-only compatibility projection for AlphaGuard structured decisions.

PR-002 deliberately disables every legacy path that parsed natural-language
decisions, called another LLM, defaulted failures to HOLD, or guessed prices.
"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from tradingagents.alphaguard.decision_schemas import (
    NormalTradePlan,
    TopReviewDecision,
)
from tradingagents.utils.logging_init import get_logger
from tradingagents.utils.tool_logging import log_graph_module

logger = get_logger("default")


class LegacyDecisionAdapter:
    """Project validated objects to the old display/API shape.

    This projection is deliberately marked as non-executable. No automated
    order, future ConsensusEngine, or HardRiskEngine may consume its output.
    """

    compatibility_only = True
    not_for_automated_execution = True

    _ACTION_LABELS = {
        "BUY": "买入",
        "SELL": "卖出",
        "REDUCE": "减仓",
        "HOLD": "持有",
        "WAIT": "等待",
        "NONE": "无操作",
    }
    _BLOCKING_REVIEW_STATUSES = {
        "REJECT",
        "SUSPEND",
        "MODEL_FAILED",
        "INVALID_OUTPUT",
    }
    _BLOCKING_PLAN_STATUSES = {
        "MODEL_FAILED",
        "INVALID_OUTPUT",
        "INSUFFICIENT_DATA",
    }

    def from_structured(
        self,
        normal_trade_plan: NormalTradePlan | dict[str, Any],
        top_review_decision: TopReviewDecision | dict[str, Any],
        stock_symbol: str | None = None,
    ) -> dict[str, Any]:
        try:
            plan = NormalTradePlan.model_validate(normal_trade_plan)
            review = TopReviewDecision.model_validate(top_review_decision)
        except (ValidationError, TypeError, ValueError) as exc:
            return self.invalid_projection(
                stock_symbol=stock_symbol,
                error_type="STRUCTURED_STATE_VALIDATION_ERROR",
                reason=(
                    "旧接口适配被阻断：结构化状态无效 "
                    f"({exc.__class__.__name__})"
                ),
            )

        display_plan = (
            review.adjusted_plan
            if review.status in {"RISK_ADJUST", "MATERIAL_REVISION"}
            and review.adjusted_plan is not None
            else plan
        )
        blocked = (
            plan.status in self._BLOCKING_PLAN_STATUSES
            or review.status in self._BLOCKING_REVIEW_STATUSES
        )
        action = (
            "不可执行"
            if blocked
            else self._ACTION_LABELS.get(display_plan.action, "无操作")
        )

        return {
            "stock_symbol": stock_symbol,
            "status": review.status,
            "normal_status": plan.status,
            "review_status": review.status,
            "action": action,
            "confidence": 0.0 if blocked else display_plan.confidence,
            "risk_score": None,
            # Direct projection only. A missing target remains missing.
            "target_price": None if blocked else display_plan.target_price,
            "reasoning": review.review_reason or display_plan.thesis,
            "normal_trade_plan": plan.model_dump(mode="json"),
            "top_review_decision": review.model_dump(mode="json"),
            "compatibility_only": self.compatibility_only,
            "not_for_automated_execution": self.not_for_automated_execution,
            "automated_execution_allowed": False,
            "authoritative_source": "normal_trade_plan+top_review_decision",
        }

    def invalid_projection(
        self,
        *,
        stock_symbol: str | None,
        error_type: str,
        reason: str,
    ) -> dict[str, Any]:
        return {
            "stock_symbol": stock_symbol,
            "status": "INVALID_OUTPUT",
            "normal_status": "INVALID_OUTPUT",
            "review_status": "INVALID_OUTPUT",
            "action": "不可执行",
            "confidence": 0.0,
            "risk_score": None,
            "target_price": None,
            "reasoning": reason,
            "decision_error": {
                "stage": "LEGACY_DECISION_ADAPTER",
                "status": "INVALID_OUTPUT",
                "error_type": error_type,
                "error_message": reason,
            },
            "compatibility_only": self.compatibility_only,
            "not_for_automated_execution": self.not_for_automated_execution,
            "automated_execution_allowed": False,
            "authoritative_source": "none",
        }


class SignalProcessor:
    """Deprecated facade retained for callers that import this class.

    ``process_signal`` no longer interprets text. New code must call
    ``process_structured`` with the validated graph objects.
    """

    compatibility_only = True
    not_for_automated_execution = True

    def __init__(self, quick_thinking_llm=None):
        # Kept only for source compatibility. It is intentionally never used.
        self.legacy_adapter = LegacyDecisionAdapter()

    @log_graph_module("signal_processing")
    def process_signal(
        self,
        full_signal: str,
        stock_symbol: str | None = None,
    ) -> dict[str, Any]:
        logger.warning(
            "Legacy text decision parsing is disabled for %s; no LLM or regex was used",
            stock_symbol or "unknown",
        )
        return self.legacy_adapter.invalid_projection(
            stock_symbol=stock_symbol,
            error_type="LEGACY_TEXT_PARSING_DISABLED",
            reason=(
                "AlphaGuard 已禁用自然语言交易方向解析；"
                "必须提供 NormalTradePlan 与 TopReviewDecision"
            ),
        )

    @log_graph_module("signal_processing")
    def process_structured(
        self,
        normal_trade_plan: NormalTradePlan | dict[str, Any],
        top_review_decision: TopReviewDecision | dict[str, Any],
        stock_symbol: str | None = None,
    ) -> dict[str, Any]:
        return self.legacy_adapter.from_structured(
            normal_trade_plan,
            top_review_decision,
            stock_symbol,
        )
