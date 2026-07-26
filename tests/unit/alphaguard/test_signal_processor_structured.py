from datetime import datetime, timezone

from tradingagents.alphaguard.decision_schemas import (
    ModelExecutionMeta,
    NormalTradePlan,
    TopReviewDecision,
)
from tradingagents.graph.signal_processing import (
    LegacyDecisionAdapter,
    SignalProcessor,
)


def meta(prompt_name="normal_trade_plan", prompt_version="normal_trade_plan_v1"):
    now = datetime.now(timezone.utc)
    return ModelExecutionMeta(
        provider="test",
        model_name="test-model",
        model_version="test-model-v1",
        prompt_name=prompt_name,
        prompt_version=prompt_version,
        started_at=now,
        finished_at=now,
        latency_ms=1,
        execution_status="SUCCESS",
    )


def no_trade_plan(target_price=None):
    return NormalTradePlan(
        plan_id="plan-1",
        snapshot_id="legacy-analysis:test",
        quant_proposal_id="legacy-quant:none",
        status="NO_TRADE",
        action="NONE",
        confidence=0.6,
        thesis="当前不交易",
        bullish_evidence=[],
        bearish_evidence=[],
        entry_zone=None,
        initial_position_pct=None,
        max_position_pct=None,
        add_conditions=[],
        stop_conditions=[],
        reduce_conditions=[],
        exit_conditions=[],
        invalidation_conditions=[],
        target_price=target_price,
        valid_until=None,
        main_risks=[],
        unresolved_questions=[],
        model_meta=meta(),
    )


def confirm_review():
    return TopReviewDecision(
        review_id="review-1",
        snapshot_id="legacy-analysis:test",
        plan_id="plan-1",
        status="CONFIRM",
        completeness_score=0.8,
        logic_consistency_score=0.8,
        risk_control_score=0.8,
        missing_evidence=[],
        logical_conflicts=[],
        risk_findings=[],
        adjusted_plan=None,
        material_change_fields=[],
        review_reason="确认不交易",
        model_meta=meta("top_review_decision", "top_review_decision_v1"),
    )


def test_empty_text_no_longer_becomes_hold():
    result = SignalProcessor().process_signal("", "000001")
    assert result["status"] == "INVALID_OUTPUT"
    assert result["action"] == "不可执行"
    assert result["action"] != "持有"


def test_random_text_is_not_regex_parsed_as_buy_or_sell():
    result = SignalProcessor().process_signal(
        "The words BUY and SELL appear in an unrelated paragraph.",
        "AAPL",
    )
    assert result["action"] == "不可执行"
    assert result["target_price"] is None


def test_missing_target_price_is_not_generated():
    result = LegacyDecisionAdapter().from_structured(
        no_trade_plan(target_price=None),
        confirm_review(),
        "000001",
    )
    assert result["target_price"] is None


def test_no_fixed_factor_target_price_generation():
    result = LegacyDecisionAdapter().from_structured(
        no_trade_plan(target_price=None),
        confirm_review(),
        "AAPL",
    )
    assert result["target_price"] is None
    assert "current_price" not in result


def test_compatibility_projection_is_explicitly_non_executable():
    result = LegacyDecisionAdapter().from_structured(
        no_trade_plan(),
        confirm_review(),
        "000001",
    )
    assert result["compatibility_only"] is True
    assert result["not_for_automated_execution"] is True
    assert result["automated_execution_allowed"] is False
