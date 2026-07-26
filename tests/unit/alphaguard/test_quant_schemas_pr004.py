from datetime import date, datetime

import pytest
from pydantic import ValidationError

from app.schemas.alphaguard import FactorResult, MarketRegimeResult, QuantTradeProposal


HASH = "a" * 64
NOW = datetime(2026, 7, 26)


def factor_payload(**changes):
    payload = {
        "result_id": "result-1",
        "factor_id": "factor-v1",
        "factor_version": "1.0.0",
        "group": "TREND",
        "symbol": "600519",
        "market": "CN",
        "trade_date": date(2026, 7, 25),
        "snapshot_id": "snapshot-1",
        "raw_value": 0.1,
        "normalized_score": 75,
        "direction": "POSITIVE",
        "confidence": 1,
        "missing_reason": None,
        "input_refs": ["stock_daily_quotes:p1"],
        "input_hash": HASH,
        "code_hash": HASH,
        "parameter_hash": HASH,
        "calculated_at": NOW,
    }
    payload.update(changes)
    return payload


def regime_payload(**changes):
    payload = {
        "regime_result_id": "regime-1",
        "snapshot_id": "snapshot-1",
        "trade_date": date(2026, 7, 25),
        "calculation_status": "CALCULATED",
        "regime": "TREND_UP",
        "confidence": 1,
        "evidence": ["fixed"],
        "metrics": {"breadth": 0.2},
        "allowed_strategy_ids": ["SWING_TREND_PULLBACK_V1", "POSITION_EXIT_V1"],
        "allow_new_positions": True,
        "max_total_exposure_pct": 0.8,
        "regime_version": "market-regime-v1",
        "input_hash": HASH,
        "calculated_at": NOW,
    }
    payload.update(changes)
    return payload


def proposal_payload(**changes):
    payload = {
        "proposal_id": "proposal-1",
        "candidate_id": None,
        "user_id": "user-1",
        "symbol": "600519",
        "market": "CN",
        "trade_date": date(2026, 7, 25),
        "snapshot_id": "snapshot-1",
        "strategy_id": "SWING_TREND_PULLBACK_V1",
        "strategy_version": "1.0.0",
        "regime_result_id": "regime-1",
        "factor_set_version": "factor-set-v1",
        "status": "WATCH",
        "action_candidate": "WAIT",
        "entry_zone": None,
        "initial_position_pct": 0,
        "max_position_pct": 0,
        "add_conditions": [],
        "reduce_conditions": [],
        "exit_conditions": [],
        "invalidation_conditions": [],
        "valid_until": None,
        "expected_holding_days": None,
        "factor_summary": {"TREND": 50},
        "factor_result_ids": [],
        "evidence_refs": [],
        "risk_flags": [],
        "reason_codes": ["WAIT"],
        "explanation": "Deterministic wait.",
        "input_hash": HASH,
        "created_at": NOW,
        "automated_execution_allowed": False,
    }
    payload.update(changes)
    return payload


def test_calculated_factor_schema_accepts_bounded_values():
    assert FactorResult.model_validate(factor_payload()).normalized_score == 75


def test_missing_factor_requires_unknown_null_zero_and_reason():
    result = FactorResult.model_validate(
        factor_payload(
            raw_value=None,
            normalized_score=None,
            direction="UNKNOWN",
            confidence=0,
            missing_reason="missing price window",
        )
    )
    assert result.raw_value is None


@pytest.mark.parametrize(
    "changes",
    [
        {"raw_value": None, "normalized_score": 0, "direction": "UNKNOWN", "confidence": 0, "missing_reason": "x"},
        {"raw_value": None, "normalized_score": None, "direction": "NEUTRAL", "confidence": 0, "missing_reason": "x"},
        {"raw_value": None, "normalized_score": None, "direction": "UNKNOWN", "confidence": 0, "missing_reason": None},
        {"normalized_score": 101},
        {"confidence": 1.1},
    ],
)
def test_missing_or_unbounded_factor_values_are_rejected(changes):
    with pytest.raises(ValidationError):
        FactorResult.model_validate(factor_payload(**changes))


@pytest.mark.parametrize(
    "regime", ["TREND_UP", "RANGE_STRONG", "RANGE_WEAK", "TREND_DOWN", "EXTREME_RISK"]
)
def test_only_five_calculated_regimes_are_valid(regime):
    assert MarketRegimeResult.model_validate(regime_payload(regime=regime)).regime == regime


def test_insufficient_regime_cannot_fake_state_or_allow_opening():
    result = MarketRegimeResult.model_validate(
        regime_payload(
            calculation_status="INSUFFICIENT_DATA",
            regime=None,
            confidence=0,
            allow_new_positions=False,
            max_total_exposure_pct=None,
            allowed_strategy_ids=["POSITION_EXIT_V1"],
        )
    )
    assert result.regime is None
    with pytest.raises(ValidationError):
        MarketRegimeResult.model_validate(
            regime_payload(
                calculation_status="INSUFFICIENT_DATA",
                regime="RANGE_WEAK",
                allow_new_positions=False,
            )
        )


def test_proposal_can_never_enable_automated_execution():
    assert QuantTradeProposal.model_validate(proposal_payload()).automated_execution_allowed is False
    with pytest.raises(ValidationError):
        QuantTradeProposal.model_validate(
            proposal_payload(automated_execution_allowed=True)
        )


def test_triggered_proposal_requires_trade_action_and_position_bounds():
    with pytest.raises(ValidationError):
        QuantTradeProposal.model_validate(
            proposal_payload(status="TRIGGERED", action_candidate="WAIT")
        )
    with pytest.raises(ValidationError):
        QuantTradeProposal.model_validate(
            proposal_payload(initial_position_pct=0.2, max_position_pct=0.1)
        )
