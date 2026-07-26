"""Pure-Python, snapshot-only final admission gate for PR-005."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from app.schemas.alphaguard.decision import (
    ConsensusDecision,
    DecisionContext,
    RiskDecision,
    RiskPolicy,
    RiskRuleResult,
    canonical_hash,
)
from tradingagents.alphaguard.decision_schemas import EvidenceRef, NormalTradePlan

from .evidence_snapshot_service import EvidenceSnapshotService
from .decision_validation import validate_plan_against_context
from .risk_context_resolver import RiskContextResolver
from .snapshot_data_resolver import ResolvedSnapshotData


RULE_VERSION = "1.0.0"
TERMINAL_ORDER_STATUSES = {"filled", "cancelled", "canceled", "rejected", "expired"}
CURRENCY_BY_MARKET = {"CN": "CNY", "HK": "HKD", "US": "USD"}


def _num(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "st", "suspended"}:
        return True
    if text in {"0", "false", "no", "n", "normal", "trading"}:
        return False
    return None


def _evidence(context: DecisionContext, category: str) -> list[EvidenceRef]:
    if category == "account":
        return context.account_evidence
    if category == "portfolio":
        return context.portfolio_evidence
    return context.price_evidence


def _rule(
    rule_id: str,
    status: str,
    reason: str,
    *,
    observed: Any = None,
    threshold: Any = None,
    context: DecisionContext,
    evidence_category: str = "price",
    original_pct: float | None = None,
    adjusted_pct: float | None = None,
    original_qty: int | None = None,
    adjusted_qty: int | None = None,
    now: datetime,
) -> RiskRuleResult:
    return RiskRuleResult(
        rule_id=rule_id,
        rule_version=RULE_VERSION,
        status=status,
        observed_value=observed,
        threshold_value=threshold,
        original_position_pct=original_pct,
        adjusted_position_pct=adjusted_pct,
        original_quantity=original_qty,
        adjusted_quantity=adjusted_qty,
        evidence_refs=_evidence(context, evidence_category),
        reason=reason,
        evaluated_at=now,
    )


class HardRiskEngine:
    """May reduce or block; never imports an order, account-write, or LLM module."""

    def __init__(self):
        self.risk_resolver = RiskContextResolver()

    def evaluate(
        self,
        *,
        data: ResolvedSnapshotData,
        context: DecisionContext,
        consensus: ConsensusDecision,
        policy: RiskPolicy,
        account_id: str | None,
        now: datetime | None = None,
    ) -> RiskDecision:
        now = now or datetime.utcnow()
        rules: list[RiskRuleResult] = []
        plan = consensus.final_plan
        if consensus.status != "CONSENSUS_PASS" or plan is None:
            raise ValueError("HardRisk requires CONSENSUS_PASS with final_plan")
        if plan.action not in {"BUY", "SELL", "REDUCE"}:
            raise ValueError("HardRisk accepts only BUY/SELL/REDUCE")
        risk = self.risk_resolver.resolve(data, account_id=account_id)

        integrity_errors = []
        if policy.snapshot_integrity_required and not EvidenceSnapshotService.verify_integrity(
            data.snapshot
        ):
            integrity_errors.append("snapshot hash mismatch")
        try:
            DecisionContext.model_validate(context.model_dump(mode="python"))
            validate_plan_against_context(
                plan,
                context,
                additional_prompt_versions={context.top_prompt_version},
            )
        except ValueError:
            integrity_errors.append("DecisionContext hash/schema mismatch")
        if canonical_hash(plan) != consensus.final_plan_hash:
            integrity_errors.append("Consensus final_plan_hash mismatch")
        if (
            context.snapshot_id != data.snapshot.snapshot_id
            or context.snapshot_id != consensus.snapshot_id
            or context.quant_proposal_id != consensus.quant_proposal_id
            or plan.snapshot_id != context.snapshot_id
            or plan.quant_proposal_id != context.quant_proposal_id
            or context.user_id != data.snapshot.user_id
            or context.symbol != data.snapshot.symbol
            or context.market != data.snapshot.market
            or context.trade_date != data.snapshot.trade_date
        ):
            integrity_errors.append("decision object identity mismatch")
        if context.data_quality_status != data.snapshot.data_quality.status:
            integrity_errors.append("data quality status mismatch")
        if policy.status != "ACTIVE":
            integrity_errors.append("RiskPolicy is not active")
        if policy.data_quality_fail_blocked and context.data_quality_status == "FAIL":
            integrity_errors.append("DataQuality FAIL")
        rules.append(
            _rule(
                "AG-RISK-INTEGRITY",
                "REJECT" if integrity_errors else "PASS",
                "; ".join(integrity_errors) if integrity_errors else "evidence chain verified",
                observed=integrity_errors,
                threshold="no integrity errors",
                context=context,
                now=now,
            )
        )

        validity_errors = []
        if policy.decision_validity_required:
            for label, value in (
                ("proposal", context.quant_proposal.valid_until),
                ("plan", plan.valid_until),
            ):
                if value is None:
                    validity_errors.append(f"{label} validity missing")
                elif value < now.replace(tzinfo=value.tzinfo):
                    validity_errors.append(f"{label} expired")
        rules.append(
            _rule(
                "AG-RISK-VALIDITY",
                "REJECT" if validity_errors else "PASS",
                "; ".join(validity_errors) if validity_errors else "decision is valid",
                observed=validity_errors,
                threshold="unexpired proposal and plan",
                context=context,
                now=now,
            )
        )

        market_row = dict(risk.latest_price or {})
        market_row.update(risk.instrument or {})
        suspended = _bool(
            market_row.get("suspended")
            if "suspended" in market_row
            else (
                str(market_row.get("tradestatus")) == "0"
                if market_row.get("tradestatus") is not None
                else None
            )
        )
        is_st = _bool(
            market_row.get("is_st", market_row.get("isST"))
        )
        limit_up = _bool(
            market_row.get("at_limit_up", market_row.get("limit_up_hit"))
        )
        limit_down = _bool(
            market_row.get("at_limit_down", market_row.get("limit_down_hit"))
        )
        market_status = "PASS"
        market_reasons = []
        if suspended is None:
            market_status = "SUSPEND"
            market_reasons.append("suspension status missing")
        elif suspended and not (
            policy.allow_buy_when_suspended
            if plan.action == "BUY"
            else policy.allow_sell_when_suspended
        ):
            market_status = "REJECT"
            market_reasons.append("instrument is suspended")
        if plan.action == "BUY":
            if is_st is None:
                market_status = "SUSPEND" if market_status == "PASS" else market_status
                market_reasons.append("ST status missing")
            elif is_st and not policy.st_buy_enabled:
                market_status = "REJECT"
                market_reasons.append("ST buying is disabled")
            if limit_up is None:
                market_status = "SUSPEND" if market_status == "PASS" else market_status
                market_reasons.append("limit-up status missing")
            elif limit_up:
                market_status = "REJECT"
                market_reasons.append("buying at limit-up is blocked")
        else:
            if limit_down is None:
                market_status = "SUSPEND" if market_status == "PASS" else market_status
                market_reasons.append("limit-down status missing")
            elif limit_down:
                market_status = "REJECT"
                market_reasons.append("selling at limit-down is blocked")
        if context.symbol in policy.blocked_symbols:
            market_status = "REJECT"
            market_reasons.append("symbol is on risk-policy blocklist")
        rules.append(
            _rule(
                "AG-RISK-TRADING-STATUS",
                market_status,
                "; ".join(market_reasons) or "snapshot trading state permits review",
                observed={
                    "suspended": suspended,
                    "is_st": is_st,
                    "limit_up": limit_up,
                    "limit_down": limit_down,
                },
                threshold={
                    "st_buy_enabled": policy.st_buy_enabled,
                    "blocked_symbols": policy.blocked_symbols,
                },
                context=context,
                now=now,
            )
        )

        account = risk.account
        account_errors = []
        if account is None:
            account_errors.append("account snapshot missing")
        else:
            account_status = str(account.get("status") or "").upper()
            if account_status not in {"ACTIVE", "ENABLED"}:
                account_errors.append("account active/frozen status missing or blocked")
            if str(account.get("user_id") or "") != context.user_id:
                account_errors.append("account user mismatch")
            if str(account.get("market") or context.market) != context.market:
                account_errors.append("account market mismatch")
            if str(account.get("currency") or CURRENCY_BY_MARKET.get(context.market)) != CURRENCY_BY_MARKET.get(context.market):
                account_errors.append("account currency mismatch")
        rules.append(
            _rule(
                "AG-RISK-ACCOUNT",
                "SUSPEND" if account_errors else "PASS",
                "; ".join(account_errors) if account_errors else "account snapshot is usable",
                observed=account_errors,
                threshold="active matching snapshot account",
                context=context,
                evidence_category="account",
                now=now,
            )
        )

        currency = CURRENCY_BY_MARKET.get(context.market)
        cash = equity = total_exposure = None
        industry_exposure = new_positions = None
        active_orders_verified = False
        if account:
            cash_value = account.get("cash")
            cash = _num(
                cash_value.get(currency) if isinstance(cash_value, dict) else cash_value
            )
            equity_value = account.get("equity")
            equity = _num(
                equity_value.get(currency)
                if isinstance(equity_value, dict)
                else equity_value
            )
            total_exposure = _num(account.get("total_exposure_pct"))
            exposures = account.get("industry_exposure_pct")
            industry = (risk.instrument or {}).get("industry")
            if isinstance(exposures, dict) and industry:
                industry_exposure = _num(exposures.get(industry, 0))
            new_positions = _num(account.get("new_positions_today"))
            active_orders_verified = bool(account.get("active_orders_complete"))

        latest_close = _num((risk.latest_price or {}).get("close"))
        pricing_reference = (
            plan.entry_zone.upper
            if plan.action == "BUY" and plan.entry_zone is not None
            else latest_close
        )
        price_status = "PASS" if pricing_reference and pricing_reference > 0 else "SUSPEND"
        rules.append(
            _rule(
                "AG-RISK-PRICING",
                price_status,
                "conservative snapshot price available"
                if price_status == "PASS"
                else "reliable snapshot price is missing",
                observed=pricing_reference,
                threshold="positive snapshot price",
                context=context,
                now=now,
            )
        )

        target_qty = sum(int(item.get("quantity") or 0) for item in risk.target_positions)
        available_qty = sum(
            int(item.get("available_qty", item.get("available_quantity", 0)) or 0)
            for item in risk.target_positions
        )
        current_position_pct = (
            target_qty * pricing_reference / equity
            if target_qty and pricing_reference and equity and equity > 0
            else 0.0
        )
        original_pct = plan.max_position_pct
        approved_pct = original_pct
        cap_reasons = []
        if plan.action == "BUY":
            if any(
                value is None
                for value in (cash, equity, total_exposure, industry_exposure)
            ):
                cap_reasons.append("cash/equity/exposure/industry snapshot is incomplete")
                approved_pct = None
            else:
                assert equity and equity > 0 and cash is not None
                regime_cap = (
                    context.market_regime.max_total_exposure_pct
                    if context.market_regime.max_total_exposure_pct is not None
                    else policy.max_total_exposure_pct
                )
                total_cap = min(policy.max_total_exposure_pct, regime_cap)
                cash_cap = max(
                    0.0, (cash - policy.min_cash_reserve_pct * equity) / equity
                )
                approved_pct = min(
                    float(original_pct or 0),
                    policy.max_single_position_pct,
                    max(0.0, total_cap - total_exposure + current_position_pct),
                    max(
                        0.0,
                        policy.max_industry_exposure_pct
                        - industry_exposure
                        + current_position_pct,
                    ),
                    cash_cap + current_position_pct,
                )
                if approved_pct < float(original_pct or 0):
                    cap_reasons.append("position reduced by portfolio limits")
        position_status = (
            "SUSPEND"
            if approved_pct is None
            else (
                "REJECT"
                if plan.action == "BUY" and approved_pct <= current_position_pct
                else (
                    "REDUCE"
                    if plan.action == "BUY" and approved_pct < float(original_pct or 0)
                    else "PASS"
                )
            )
        )
        rules.append(
            _rule(
                "AG-RISK-POSITION-LIMITS",
                position_status,
                "; ".join(cap_reasons) or "position limits permit the proposal",
                observed={
                    "current": current_position_pct,
                    "total": total_exposure,
                    "industry": industry_exposure,
                },
                threshold={
                    "single": policy.max_single_position_pct,
                    "total": policy.max_total_exposure_pct,
                    "industry": policy.max_industry_exposure_pct,
                    "cash_reserve": policy.min_cash_reserve_pct,
                },
                context=context,
                evidence_category="portfolio",
                original_pct=original_pct,
                adjusted_pct=approved_pct,
                now=now,
            )
        )

        if plan.action == "BUY":
            daily_status = (
                "SUSPEND"
                if new_positions is None
                else (
                    "REJECT"
                    if new_positions >= policy.max_new_positions_per_day
                    and target_qty == 0
                    else "PASS"
                )
            )
        else:
            daily_status = "NOT_APPLICABLE"
        rules.append(
            _rule(
                "AG-RISK-NEW-POSITIONS",
                daily_status,
                "daily new-position count checked"
                if daily_status == "PASS"
                else (
                    "exit action is exempt"
                    if daily_status == "NOT_APPLICABLE"
                    else "daily new-position count missing or exceeded"
                ),
                observed=new_positions,
                threshold=policy.max_new_positions_per_day,
                context=context,
                evidence_category="account",
                now=now,
            )
        )

        active_same_direction = [
            item
            for item in risk.orders
            if str(item.get("status") or "").lower() not in TERMINAL_ORDER_STATUSES
            and str(item.get("code") or item.get("symbol") or "") == context.symbol
            and str(item.get("side") or "").upper()
            == ("BUY" if plan.action == "BUY" else "SELL")
        ]
        order_status = (
            "SUSPEND"
            if not active_orders_verified
            else ("REJECT" if active_same_direction else "PASS")
        )
        rules.append(
            _rule(
                "AG-RISK-DUPLICATE-ORDER",
                order_status,
                "active-order snapshot incomplete"
                if order_status == "SUSPEND"
                else (
                    "same-direction active order exists"
                    if order_status == "REJECT"
                    else "no duplicate active order"
                ),
                observed=[item.get("order_id") for item in active_same_direction],
                threshold=0,
                context=context,
                evidence_category="portfolio",
                now=now,
            )
        )

        average_amount = _num(
            (risk.latest_price or {}).get("average_amount_20d")
            or (risk.instrument or {}).get("average_amount_20d")
        )
        liquidity_status = "NOT_APPLICABLE"
        if policy.minimum_average_amount_20d is not None:
            liquidity_status = (
                "SUSPEND"
                if average_amount is None
                else (
                    "REJECT"
                    if average_amount < policy.minimum_average_amount_20d
                    else "PASS"
                )
            )
        rules.append(
            _rule(
                "AG-RISK-LIQUIDITY",
                liquidity_status,
                "minimum liquidity threshold is unconfigured"
                if liquidity_status == "NOT_APPLICABLE"
                else "minimum liquidity checked",
                observed=average_amount,
                threshold=policy.minimum_average_amount_20d,
                context=context,
                now=now,
            )
        )

        for rule_id, factor_name, threshold in (
            (
                "AG-RISK-VOLATILITY",
                "VOLATILITY_RISK",
                policy.maximum_volatility_risk_score,
            ),
            (
                "AG-RISK-EVENT",
                "EVENT_RISK",
                policy.maximum_event_risk_score,
            ),
        ):
            observed_score = _num(context.factor_summary.get(factor_name))
            score_status = "NOT_APPLICABLE"
            score_reason = f"{factor_name} threshold is unconfigured"
            if threshold is not None:
                if observed_score is None:
                    score_status = "SUSPEND"
                    score_reason = f"{factor_name} snapshot score is missing"
                elif observed_score > threshold:
                    score_status = "REJECT"
                    score_reason = f"{factor_name} exceeds the policy threshold"
                else:
                    score_status = "PASS"
                    score_reason = f"{factor_name} is within policy threshold"
            rules.append(
                _rule(
                    rule_id,
                    score_status,
                    score_reason,
                    observed=observed_score,
                    threshold=threshold,
                    context=context,
                    now=now,
                )
            )

        calendar_status = "PASS" if risk.next_open_session else "SUSPEND"
        rules.append(
            _rule(
                "AG-RISK-TRADING-CALENDAR",
                calendar_status,
                "next snapshot-referenced open session found"
                if calendar_status == "PASS"
                else "trading calendar missing; natural-day T+1 is forbidden",
                observed=risk.next_open_session,
                threshold="next open session after trade_date",
                context=context,
                now=now,
            )
        )

        original_qty = target_qty if plan.action != "BUY" else None
        approved_qty = None
        quantity_status = "PASS"
        quantity_reason = "quantity is within snapshot risk limits"
        if pricing_reference and equity and equity > 0:
            if plan.action == "BUY" and approved_pct is not None:
                desired_value = max(
                    0.0,
                    approved_pct * equity
                    - current_position_pct * equity,
                )
                approved_qty = int(desired_value // pricing_reference)
                if context.market == "CN":
                    lot = policy.cn_buy_lot_size
                    approved_qty = approved_qty // lot * lot
                # Participation is a hard quantity cap when reliable turnover
                # evidence exists. Missing evidence suspends instead of guessing.
                if average_amount is None:
                    quantity_status = "SUSPEND"
                    quantity_reason = "average_amount_20d missing for participation cap"
                else:
                    participation_qty = int(
                        average_amount
                        * policy.max_order_participation_rate
                        // pricing_reference
                    )
                    if context.market == "CN":
                        participation_qty = (
                            participation_qty
                            // policy.cn_buy_lot_size
                            * policy.cn_buy_lot_size
                        )
                    approved_qty = min(approved_qty, participation_qty)
                if approved_qty <= 0 and quantity_status != "SUSPEND":
                    quantity_status = "REJECT"
                    quantity_reason = "risk-reduced and lot-rounded quantity is zero"
            elif plan.action in {"SELL", "REDUCE"}:
                approved_qty = min(target_qty, available_qty)
                if approved_qty <= 0:
                    quantity_status = "REJECT"
                    quantity_reason = "snapshot T+1 available quantity is zero"
                elif approved_qty < target_qty:
                    quantity_status = "REDUCE"
                    quantity_reason = "approved sell quantity reduced to available_qty"
                if (
                    context.market == "CN"
                    and plan.action == "REDUCE"
                    and approved_qty < target_qty
                    and approved_qty >= policy.cn_buy_lot_size
                ):
                    approved_qty = (
                        approved_qty // policy.cn_buy_lot_size * policy.cn_buy_lot_size
                    )
        else:
            quantity_status = "SUSPEND"
            quantity_reason = "equity or pricing evidence is missing"
        rules.append(
            _rule(
                "AG-RISK-QUANTITY",
                quantity_status,
                quantity_reason,
                observed={
                    "held": target_qty,
                    "available": available_qty,
                    "price": pricing_reference,
                },
                threshold={
                    "cn_lot": policy.cn_buy_lot_size,
                    "participation": policy.max_order_participation_rate,
                },
                context=context,
                evidence_category="portfolio",
                original_qty=original_qty,
                adjusted_qty=approved_qty,
                now=now,
            )
        )

        statuses = {item.status for item in rules}
        if "REJECT" in statuses:
            final_status = "REJECT"
        elif "SUSPEND" in statuses:
            final_status = "SUSPEND"
        elif "REDUCE" in statuses:
            final_status = "REDUCE"
        else:
            final_status = "PASS"
        if final_status in {"REJECT", "SUSPEND"}:
            approved_pct = None
            approved_qty = None

        input_hash = canonical_hash(
            {
                "snapshot_hash": data.snapshot.immutable_hash,
                "resolved_snapshot_input_hash": data.input_hash,
                "context_hash": context.context_hash,
                "consensus_hash": canonical_hash(consensus),
                "policy_hash": policy.config_hash,
                "account_id": account_id,
            }
        )
        identity = f"{context.analysis_id}:{consensus.consensus_id}:{input_hash}"
        reasons = [
            item.reason
            for item in rules
            if item.status in {"REDUCE", "REJECT", "SUSPEND"}
        ] or ["all applicable hard-risk rules passed"]
        return RiskDecision(
            risk_decision_id=str(uuid5(NAMESPACE_URL, identity)),
            analysis_id=context.analysis_id,
            consensus_id=consensus.consensus_id,
            snapshot_id=context.snapshot_id,
            quant_proposal_id=context.quant_proposal_id,
            account_id=account_id,
            status=final_status,
            action=plan.action,
            original_position_pct=original_pct,
            approved_position_pct=approved_pct,
            original_quantity=original_qty,
            approved_quantity=approved_qty,
            pricing_reference=pricing_reference,
            earliest_eligible_execute_at=risk.next_open_session,
            requires_execution_recheck=True,
            triggered_rules=rules,
            reasons=reasons,
            risk_policy_version=f"{policy.risk_policy_id}@{policy.version}",
            input_hash=input_hash,
            created_at=now,
            order_intent_created=False,
        )
