from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

from app.schemas.alphaguard.decision import DecisionContext, canonical_hash
from app.schemas.alphaguard.quant import MarketRegimeResult, QuantTradeProposal
from tradingagents.alphaguard.decision_schemas import (
    EvidenceRef,
    ModelExecutionMeta,
    NormalTradePlan,
    RuleCondition,
    TopReviewDecision,
)


def meta(
    context_hash: str,
    *,
    prompt: str = "normal_trade_plan_quant_v1",
    execution_status: str = "SUCCESS",
):
    now = datetime(2026, 7, 1, tzinfo=timezone.utc)
    return ModelExecutionMeta(
        provider="fixed",
        model_name="fixed-model",
        model_version="fixed-v1",
        prompt_name=(
            "top_review_decision"
            if prompt.startswith("top_")
            else "normal_trade_plan"
        ),
        prompt_version=prompt,
        started_at=now,
        finished_at=now,
        latency_ms=1,
        execution_status=execution_status,
        request_id="request-fixed",
        trace_id="trace-fixed",
        error_type=(
            "PROVIDER_ERROR"
            if execution_status == "MODEL_FAILED"
            else (
                "SCHEMA_VALIDATION_ERROR"
                if execution_status == "INVALID_OUTPUT"
                else None
            )
        ),
        error_message=(
            "fixed model failure"
            if execution_status != "SUCCESS"
            else None
        ),
        raw_output_hash="1" * 64,
        template_hash="2" * 64,
        context_hash=context_hash,
        input_hash="3" * 64,
    )


def make_context(action: str = "BUY") -> DecisionContext:
    evidence = [
        EvidenceRef(
            evidence_id="stock_daily_quotes:p1",
            summary="snapshot close=100",
            source="price",
        )
    ]
    proposal = QuantTradeProposal(
        proposal_id="proposal-1",
        candidate_id="candidate-1",
        user_id="user",
        symbol="600519",
        market="CN",
        trade_date=date(2026, 7, 1),
        snapshot_id="snapshot-1",
        strategy_id=(
            "SWING_TREND_PULLBACK_V1"
            if action == "BUY"
            else "POSITION_EXIT_V1"
        ),
        strategy_version="1.0.0",
        regime_result_id="regime-1",
        factor_set_version="factor-set-v1",
        status="TRIGGERED",
        action_candidate=action,
        entry_zone=(
            {"lower": 99, "upper": 101, "currency": "CNY"}
            if action == "BUY"
            else None
        ),
        initial_position_pct=0.05 if action == "BUY" else 0,
        max_position_pct=0.10 if action == "BUY" else 0,
        add_conditions=[],
        reduce_conditions=[],
        exit_conditions=[
            RuleCondition(condition_id="exit", description="exit")
        ],
        invalidation_conditions=[
            RuleCondition(condition_id="invalid", description="invalid")
        ],
        valid_until=datetime(2030, 7, 3),
        expected_holding_days=(1, 20),
        factor_summary={"TREND": 80},
        factor_result_ids=["factor-1"],
        evidence_refs=evidence,
        risk_flags=[],
        reason_codes=["FIXED"],
        explanation="fixed proposal",
        input_hash="4" * 64,
        created_at=datetime(2026, 7, 1),
        automated_execution_allowed=False,
    )
    regime = MarketRegimeResult(
        regime_result_id="regime-1",
        snapshot_id="snapshot-1",
        trade_date=date(2026, 7, 1),
        calculation_status="CALCULATED",
        regime="TREND_UP",
        confidence=1,
        evidence=["fixed"],
        metrics={"market_breadth": 0.5},
        allowed_strategy_ids=[
            "SWING_TREND_PULLBACK_V1",
            "POSITION_EXIT_V1",
        ],
        allow_new_positions=True,
        max_total_exposure_pct=0.6,
        regime_version="market-regime-v1",
        input_hash="5" * 64,
        calculated_at=datetime(2026, 7, 1),
    )
    payload = {
        "analysis_id": "analysis-1",
        "user_id": "user",
        "candidate_id": "candidate-1",
        "symbol": "600519",
        "market": "CN",
        "trade_date": date(2026, 7, 1),
        "snapshot_id": "snapshot-1",
        "quant_proposal_id": "proposal-1",
        "strategy_id": proposal.strategy_id,
        "strategy_version": "1.0.0",
        "factor_set_version": "factor-set-v1",
        "regime_result_id": "regime-1",
        "quant_proposal": proposal,
        "factor_summary": {"TREND": 80.0},
        "factor_result_ids": ["factor-1"],
        "market_regime": regime,
        "price_evidence": evidence,
        "financial_evidence": [],
        "news_evidence": [],
        "announcement_evidence": [],
        "account_evidence": [
            EvidenceRef(
                evidence_id="paper_accounts:account-1",
                summary="account snapshot",
                source="account",
            )
        ],
        "portfolio_evidence": [],
        "data_quality_status": "PASS",
        "risk_flags": [],
        "missing_evidence": [],
        "normal_prompt_version": "normal_trade_plan_quant_v1",
        "top_prompt_version": "top_review_decision_quant_v1",
        "created_at": datetime(2026, 7, 1),
        "schema_version": "decision-context-v1",
    }
    draft = DecisionContext.model_construct(
        decision_context_id="context-1",
        context_hash="0" * 64,
        **payload,
    )
    payload["context_hash"] = canonical_hash(
        draft,
        exclude={"decision_context_id", "context_hash", "created_at"},
    )
    payload["decision_context_id"] = "context-1"
    return DecisionContext.model_validate(payload)


def make_plan(
    context: DecisionContext,
    *,
    status: str = "PROPOSE_TRADE",
    action: str | None = None,
    revision_round: int = 0,
    original_plan: NormalTradePlan | None = None,
    revision_request_id: str | None = None,
) -> NormalTradePlan:
    action = action or (
        context.quant_proposal.action_candidate
        if status == "PROPOSE_TRADE"
        else ("WAIT" if status == "WAIT" else "NONE")
    )
    trading = status == "PROPOSE_TRADE"
    return NormalTradePlan(
        plan_id=str(uuid4()),
        snapshot_id=context.snapshot_id,
        quant_proposal_id=context.quant_proposal_id,
        analysis_id=context.analysis_id,
        decision_context_id=context.decision_context_id,
        symbol=context.symbol,
        market=context.market,
        trade_date=context.trade_date,
        strategy_id=context.strategy_id,
        strategy_version=context.strategy_version,
        revision_round=revision_round,
        supersedes_plan_id=original_plan.plan_id if original_plan else None,
        revision_request_id=revision_request_id,
        status=status,
        action=action,
        confidence=0.8 if trading else 0,
        thesis="fixed trade thesis" if trading else "fixed non-trade outcome",
        bullish_evidence=context.price_evidence if trading else [],
        bearish_evidence=[],
        entry_zone=(
            context.quant_proposal.entry_zone
            if trading and action == "BUY"
            else None
        ),
        initial_position_pct=(
            context.quant_proposal.initial_position_pct if trading else None
        ),
        max_position_pct=(
            context.quant_proposal.max_position_pct if trading else None
        ),
        add_conditions=[],
        stop_conditions=[],
        reduce_conditions=[],
        exit_conditions=[
            RuleCondition(condition_id="exit", description="exit")
        ]
        if trading
        else [],
        invalidation_conditions=[
            RuleCondition(condition_id="invalid", description="invalid")
        ]
        if trading
        else [],
        target_price=None,
        valid_until=datetime(2030, 7, 3) if trading else None,
        main_risks=[],
        unresolved_questions=[],
        model_meta=meta(
            context.context_hash,
            execution_status=(
                status
                if status in {"MODEL_FAILED", "INVALID_OUTPUT"}
                else "SUCCESS"
            ),
        ),
    )


def make_review(
    context: DecisionContext,
    plan: NormalTradePlan,
    *,
    status: str = "CONFIRM",
    adjusted_plan: NormalTradePlan | None = None,
) -> TopReviewDecision:
    return TopReviewDecision(
        review_id=str(uuid4()),
        snapshot_id=context.snapshot_id,
        plan_id=plan.plan_id,
        analysis_id=context.analysis_id,
        decision_context_id=context.decision_context_id,
        quant_proposal_id=context.quant_proposal_id,
        symbol=context.symbol,
        market=context.market,
        trade_date=context.trade_date,
        strategy_id=context.strategy_id,
        strategy_version=context.strategy_version,
        revision_round=plan.revision_round,
        status=status,
        completeness_score=1,
        logic_consistency_score=1,
        risk_control_score=1,
        missing_evidence=[],
        logical_conflicts=[],
        risk_findings=[],
        adjusted_plan=adjusted_plan,
        material_change_fields=(
            ["entry_zone"] if status == "MATERIAL_REVISION" else []
        ),
        review_reason="fixed review",
        model_meta=meta(
            context.context_hash, prompt="top_review_decision_quant_v1"
        ),
    )
