"""Deterministic PR-004 strategy evaluation; produces proposals, never orders."""

from __future__ import annotations

import statistics
from datetime import datetime, time
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from app.schemas.alphaguard import (
    FactorEvidenceBundle,
    MarketRegimeResult,
    QuantTradeProposal,
    StrategyDefinition,
)
from tradingagents.alphaguard.decision_schemas import EvidenceRef, PriceRange, RuleCondition

from .quant_config import sha256_value
from .snapshot_data_resolver import ResolvedSnapshotData


def _factor_map(bundle: FactorEvidenceBundle):
    return {result.factor_id: result for result in bundle.results}


def _rule(identifier: str, description: str, expression: str) -> RuleCondition:
    return RuleCondition(
        condition_id=identifier,
        description=description,
        expression=expression,
    )


def _next_sessions(data: ResolvedSnapshotData, count: int) -> list[datetime]:
    sessions = []
    for row in data.trading_calendar:
        if row.get("is_open") is False:
            continue
        raw = row.get("session_date") or row.get("trade_date") or row.get("date")
        if not raw:
            continue
        try:
            session = datetime.fromisoformat(str(raw)[:10])
        except ValueError:
            continue
        if session.date() > data.snapshot.trade_date:
            sessions.append(datetime.combine(session.date(), time(15, 0)))
    return sorted(set(sessions))[:count]


def _base_payload(
    definition: StrategyDefinition,
    data: ResolvedSnapshotData,
    bundle: FactorEvidenceBundle,
    regime: MarketRegimeResult,
    *,
    candidate_id: str | None,
    status: str,
    action: str,
    explanation: str,
    reason_codes: list[str],
    input_hash: str,
    entry_zone=None,
    initial_position_pct: float = 0,
    max_position_pct: float = 0,
    add_conditions=None,
    reduce_conditions=None,
    exit_conditions=None,
    invalidation_conditions=None,
    valid_until=None,
    expected_holding_days=None,
    risk_flags=None,
    extra_evidence=None,
) -> QuantTradeProposal:
    factors = _factor_map(bundle)
    evidence = [
        EvidenceRef(
            evidence_id=result.result_id,
            summary=(
                f"{result.factor_id}={result.normalized_score:.2f}"
                if result.normalized_score is not None
                else f"{result.factor_id}=UNKNOWN ({result.missing_reason})"
            ),
            source="ag_factor_results",
            as_of=result.calculated_at,
        )
        for result in bundle.results
    ]
    evidence.extend(extra_evidence or [])
    proposal_id = str(
        uuid5(
            NAMESPACE_URL,
            f"alphaguard:proposal:{data.snapshot.snapshot_id}:{definition.strategy_id}:{definition.strategy_version}:{input_hash}",
        )
    )
    return QuantTradeProposal(
        proposal_id=proposal_id,
        candidate_id=candidate_id,
        user_id=data.snapshot.user_id,
        symbol=data.snapshot.symbol,
        market=data.snapshot.market,
        trade_date=data.snapshot.trade_date,
        snapshot_id=data.snapshot.snapshot_id,
        strategy_id=definition.strategy_id,
        strategy_version=definition.strategy_version,
        regime_result_id=regime.regime_result_id,
        factor_set_version=bundle.factor_set_version,
        status=status,
        action_candidate=action,
        entry_zone=entry_zone,
        initial_position_pct=initial_position_pct,
        max_position_pct=max_position_pct,
        add_conditions=add_conditions or [],
        reduce_conditions=reduce_conditions or [],
        exit_conditions=exit_conditions or [],
        invalidation_conditions=invalidation_conditions or [],
        valid_until=valid_until,
        expected_holding_days=expected_holding_days,
        factor_summary=bundle.group_scores,
        factor_result_ids=[result.result_id for result in factors.values()],
        evidence_refs=evidence,
        risk_flags=sorted(set((risk_flags or []) + bundle.risk_flags)),
        reason_codes=reason_codes,
        explanation=explanation,
        input_hash=input_hash,
        created_at=datetime.utcnow(),
        automated_execution_allowed=False,
    )


class StrategyEngine:
    """Evaluate registered deterministic strategies without importing order code."""

    def evaluate(
        self,
        definition: StrategyDefinition,
        data: ResolvedSnapshotData,
        bundle: FactorEvidenceBundle,
        regime: MarketRegimeResult,
        *,
        candidate_id: str | None = None,
    ) -> QuantTradeProposal:
        input_hash = sha256_value(
            {
                "snapshot_input_hash": data.input_hash,
                "factor_bundle_hash": bundle.input_hash,
                "regime_input_hash": regime.input_hash,
                "strategy_id": definition.strategy_id,
                "strategy_version": definition.strategy_version,
                "code_hash": definition.code_hash,
                "parameter_hash": definition.parameter_hash,
            }
        )
        if definition.strategy_id == "SWING_TREND_PULLBACK_V1":
            return self._swing(
                definition, data, bundle, regime, candidate_id, input_hash
            )
        if definition.strategy_id == "POSITION_EXIT_V1":
            return self._exit(
                definition, data, bundle, regime, candidate_id, input_hash
            )
        raise ValueError(f"unsupported strategy: {definition.strategy_id}")

    def _swing(
        self,
        definition: StrategyDefinition,
        data: ResolvedSnapshotData,
        bundle: FactorEvidenceBundle,
        regime: MarketRegimeResult,
        candidate_id: str | None,
        input_hash: str,
    ) -> QuantTradeProposal:
        if data.snapshot.market not in definition.supported_markets:
            return _base_payload(
                definition,
                data,
                bundle,
                regime,
                candidate_id=candidate_id,
                status="REJECTED",
                action="HOLD",
                explanation="Opening strategy does not support this market.",
                reason_codes=["UNSUPPORTED_MARKET"],
                input_hash=input_hash,
            )
        if regime.calculation_status != "CALCULATED":
            return _base_payload(
                definition,
                data,
                bundle,
                regime,
                candidate_id=candidate_id,
                status="INSUFFICIENT_DATA",
                action="WAIT",
                explanation="Market regime is not calculable from snapshot evidence.",
                reason_codes=["REGIME_INSUFFICIENT_DATA"],
                input_hash=input_hash,
            )
        if (
            not regime.allow_new_positions
            or definition.strategy_id not in regime.allowed_strategy_ids
            or regime.regime not in definition.allowed_regimes
        ):
            return _base_payload(
                definition,
                data,
                bundle,
                regime,
                candidate_id=candidate_id,
                status="REJECTED",
                action="HOLD",
                explanation="Current market regime does not permit this opening strategy.",
                reason_codes=["REGIME_DISALLOWS_NEW_POSITION"],
                input_hash=input_hash,
            )
        missing_groups = [
            group
            for group in definition.required_group_scores
            if bundle.group_scores.get(group) is None
        ]
        if missing_groups:
            return _base_payload(
                definition,
                data,
                bundle,
                regime,
                candidate_id=candidate_id,
                status="INSUFFICIENT_DATA",
                action="WAIT",
                explanation="Required factor groups lack configured coverage.",
                reason_codes=[f"MISSING_GROUP:{group}" for group in missing_groups],
                input_hash=input_hash,
            )
        params = definition.parameters
        checks = {
            "TREND_SCORE": float(bundle.group_scores["TREND"])
            >= params["minimum_trend_score"],
            "MOMENTUM_SCORE": float(bundle.group_scores["MOMENTUM"])
            >= params["minimum_momentum_score"],
            "LIQUIDITY_SCORE": float(bundle.group_scores["LIQUIDITY"])
            >= params["minimum_liquidity_score"],
            "VOLATILITY_RISK": float(bundle.group_scores["VOLATILITY_RISK"])
            <= params["maximum_volatility_risk_score"],
            "EVENT_RISK": float(bundle.group_scores["EVENT_RISK"])
            <= params["maximum_event_risk_score"],
        }
        factor_by_id = _factor_map(bundle)
        raw_checks = {
            "PRICE_ABOVE_MA60": factor_by_id["close_vs_ma60_v1"].raw_value > 0,
            "MA20_SLOPE_POSITIVE": factor_by_id["ma20_slope_5d_v1"].raw_value > 0,
            "MOMENTUM_POSITIVE": factor_by_id["momentum_20d_v1"].raw_value > 0,
            "RELATIVE_STRENGTH_POSITIVE": factor_by_id[
                "relative_strength_hs300_20d_v1"
            ].raw_value
            > 0,
        }
        failed = [code for code, passed in {**checks, **raw_checks}.items() if not passed]
        if failed:
            return _base_payload(
                definition,
                data,
                bundle,
                regime,
                candidate_id=candidate_id,
                status="WATCH",
                action="WAIT",
                explanation="Trend structure remains under observation; prerequisites are incomplete.",
                reason_codes=[f"FAILED:{code}" for code in failed],
                input_hash=input_hash,
            )
        closes = [float(row["close"]) for row in data.prices[-20:]]
        if len(closes) < 20:
            return _base_payload(
                definition,
                data,
                bundle,
                regime,
                candidate_id=candidate_id,
                status="INSUFFICIENT_DATA",
                action="WAIT",
                explanation="Twenty price sessions are required for pullback evaluation.",
                reason_codes=["PRICE_HISTORY_INSUFFICIENT"],
                input_hash=input_hash,
            )
        close = closes[-1]
        high20 = max(closes)
        ma20 = statistics.fmean(closes)
        pullback = 1 - close / high20
        distance = abs(close / ma20 - 1)
        pullback_ok = (
            params["pullback_from_20d_high_min"]
            <= pullback
            <= params["pullback_from_20d_high_max"]
            and distance <= params["maximum_distance_from_ma20"]
        )
        if not pullback_ok:
            return _base_payload(
                definition,
                data,
                bundle,
                regime,
                candidate_id=candidate_id,
                status="WATCH",
                action="WAIT",
                explanation="Trend prerequisites pass, but no configured pullback entry is present.",
                reason_codes=["PULLBACK_NOT_IN_ENTRY_WINDOW"],
                input_hash=input_hash,
            )
        sessions = _next_sessions(data, int(params["valid_trading_sessions"]))
        if len(sessions) < int(params["valid_trading_sessions"]):
            return _base_payload(
                definition,
                data,
                bundle,
                regime,
                candidate_id=candidate_id,
                status="INSUFFICIENT_DATA",
                action="WAIT",
                explanation="A snapshot-referenced trading calendar is required for validity.",
                reason_codes=["TRADING_CALENDAR_INSUFFICIENT"],
                input_hash=input_hash,
            )
        zone = PriceRange(
            lower=round(min(close, ma20) * 0.99, 4),
            upper=round(max(close, ma20) * 1.01, 4),
            currency="CNY",
        )
        return _base_payload(
            definition,
            data,
            bundle,
            regime,
            candidate_id=candidate_id,
            status="TRIGGERED",
            action="BUY",
            explanation="Configured trend, relative strength, risk, liquidity and pullback rules pass.",
            reason_codes=["TREND_PULLBACK_TRIGGERED"],
            input_hash=input_hash,
            entry_zone=zone,
            initial_position_pct=params["initial_position_pct"],
            max_position_pct=params["max_position_pct"],
            add_conditions=[
                _rule("ADD_CONFIRMATION", "Add only after renewed strength.", "close > 20d_high")
            ],
            reduce_conditions=[
                _rule("REDUCE_MA20", "Reduce if support weakens.", "close < MA20")
            ],
            exit_conditions=[
                _rule("EXIT_MA60", "Exit on medium-trend failure.", "close < MA60")
            ],
            invalidation_conditions=[
                _rule("INVALIDATE_EVENT", "Invalidate on blocking event risk.", "event_risk >= 70")
            ],
            valid_until=sessions[-1],
            expected_holding_days=tuple(params["expected_holding_days"]),
        )

    def _exit(
        self,
        definition: StrategyDefinition,
        data: ResolvedSnapshotData,
        bundle: FactorEvidenceBundle,
        regime: MarketRegimeResult,
        candidate_id: str | None,
        input_hash: str,
    ) -> QuantTradeProposal:
        positions = [
            position
            for position in data.positions
            if float(position.get("quantity") or 0) > 0
            and str(position.get("user_id") or data.snapshot.user_id)
            == data.snapshot.user_id
        ]
        if not positions:
            return _base_payload(
                definition,
                data,
                bundle,
                regime,
                candidate_id=candidate_id,
                status="REJECTED",
                action="HOLD",
                explanation="No positive snapshot-referenced position exists.",
                reason_codes=["NO_POSITION"],
                input_hash=input_hash,
            )
        missing_groups = [
            group
            for group in definition.required_group_scores
            if bundle.group_scores.get(group) is None
        ]
        if missing_groups:
            return _base_payload(
                definition,
                data,
                bundle,
                regime,
                candidate_id=candidate_id,
                status="INSUFFICIENT_DATA",
                action="WAIT",
                explanation="Exit evidence is incomplete; no trade result is inferred.",
                reason_codes=[f"MISSING_GROUP:{group}" for group in missing_groups],
                input_hash=input_hash,
            )
        factors = _factor_map(bundle)
        params = definition.parameters
        sell_reasons = []
        reduce_reasons = []
        if factors["close_vs_ma60_v1"].raw_value < 0:
            sell_reasons.append("PRICE_BELOW_MA60")
        if regime.regime == "EXTREME_RISK":
            sell_reasons.append("MARKET_EXTREME_RISK")
        if float(bundle.group_scores["EVENT_RISK"]) >= params["blocking_event_risk_score"]:
            sell_reasons.append("BLOCKING_EVENT_RISK")
        if factors["close_vs_ma20_v1"].raw_value < 0:
            reduce_reasons.append("PRICE_BELOW_MA20")
        if factors["ma20_slope_5d_v1"].raw_value < 0:
            reduce_reasons.append("MA20_SLOPE_NEGATIVE")
        if factors["momentum_20d_v1"].raw_value < 0:
            reduce_reasons.append("MOMENTUM_NEGATIVE")
        if float(bundle.group_scores["VOLATILITY_RISK"]) >= params["elevated_volatility_risk_score"]:
            reduce_reasons.append("ELEVATED_VOLATILITY_RISK")
        if regime.regime == "TREND_DOWN":
            reduce_reasons.append("MARKET_TREND_DOWN")
        available = sum(
            float(position.get("available_qty", position.get("available_quantity", 0)) or 0)
            for position in positions
        )
        quantity = sum(float(position.get("quantity") or 0) for position in positions)
        t1_flag = ["T1_SELLABLE_QUANTITY_ZERO"] if data.snapshot.market == "CN" and available <= 0 else []
        account_evidence = [
            EvidenceRef(
                evidence_id=str(position.get("_reference")),
                summary=(
                    f"quantity={position.get('quantity')}, "
                    f"available_qty={position.get('available_qty', position.get('available_quantity'))}"
                ),
                source="paper_positions_snapshot_ref",
                as_of=None,
            )
            for position in positions
        ]
        if sell_reasons:
            action, reasons = "SELL", sell_reasons
        elif len(reduce_reasons) >= 2:
            action, reasons = "REDUCE", reduce_reasons
        else:
            return _base_payload(
                definition,
                data,
                bundle,
                regime,
                candidate_id=candidate_id,
                status="WATCH",
                action="HOLD",
                explanation="Positive position exists, but configured exit thresholds are not met.",
                reason_codes=["EXIT_NOT_TRIGGERED", *reduce_reasons],
                input_hash=input_hash,
                risk_flags=t1_flag,
                extra_evidence=account_evidence,
            )
        return _base_payload(
            definition,
            data,
            bundle,
            regime,
            candidate_id=candidate_id,
            status="TRIGGERED",
            action=action,
            explanation=(
                f"Snapshot evidence triggers {action}; quantity={quantity:g}, "
                f"snapshot sellable quantity={available:g}. No order is created."
            ),
            reason_codes=reasons,
            input_hash=input_hash,
            initial_position_pct=0,
            max_position_pct=0,
            reduce_conditions=[
                _rule("T1_REFERENCE", "Respect snapshot sellable quantity.", "available_qty > 0")
            ],
            exit_conditions=[
                _rule("EXIT_TRIGGER", "Exit according to triggered deterministic risks.", " OR ".join(reasons))
            ],
            expected_holding_days=tuple(params["expected_holding_days"]),
            risk_flags=t1_flag,
            extra_evidence=account_evidence,
        )
