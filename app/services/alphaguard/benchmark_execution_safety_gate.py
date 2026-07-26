"""Pure-Python mechanical safety gate for benchmark paper accounts."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, ROUND_FLOOR
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from tradingagents.alphaguard.decision_control_schemas import RiskRuleResult
from tradingagents.alphaguard.paper_schemas import (
    BenchmarkExecutionDecision,
    PaperAccount,
    paper_canonical_hash,
)


def _rule(
    rule_id: str,
    status: str,
    reason: str,
    *,
    observed: Any,
    threshold: Any,
    original_quantity: int | None = None,
    adjusted_quantity: int | None = None,
    original_position_pct: float | None = None,
    adjusted_position_pct: float | None = None,
    now: datetime,
) -> RiskRuleResult:
    return RiskRuleResult(
        rule_id=rule_id,
        rule_version="benchmark-safety-v1",
        status=status,
        observed_value=observed,
        threshold_value=threshold,
        original_position_pct=original_position_pct,
        adjusted_position_pct=adjusted_position_pct,
        original_quantity=original_quantity,
        adjusted_quantity=adjusted_quantity,
        evidence_refs=[],
        reason=reason,
        evaluated_at=now,
    )


class BenchmarkExecutionSafetyGate:
    """Checks only mechanical execution safety; it is not HardRisk."""

    version = "benchmark-safety-v1"

    def evaluate(
        self,
        *,
        source_type: str,
        source_object_id: str,
        account: PaperAccount,
        action: str,
        requested_position_pct: float | None,
        requested_quantity: int | None,
        price: Decimal | None,
        current_quantity: int,
        available_quantity: int,
        current_position_value: Decimal,
        total_exposure_value: Decimal,
        duplicate_active_order: bool,
        execution_date_available: bool,
        trading_status_known: bool,
        trading_blocked: bool,
        max_single_position_pct: float,
        max_total_exposure_pct: float,
        cn_buy_lot_size: int,
        now: datetime | None = None,
    ) -> BenchmarkExecutionDecision:
        now = now or datetime.utcnow()
        rules: list[RiskRuleResult] = []
        if account.status != "ACTIVE":
            rules.append(
                _rule(
                    "AG-BENCH-ACCOUNT-ACTIVE",
                    "SUSPEND",
                    "automatic paper account is not active",
                    observed=account.status,
                    threshold="ACTIVE",
                    now=now,
                )
            )
        else:
            rules.append(
                _rule(
                    "AG-BENCH-ACCOUNT-ACTIVE",
                    "PASS",
                    "automatic paper account is active",
                    observed=account.status,
                    threshold="ACTIVE",
                    now=now,
                )
            )

        rules.append(
            _rule(
                "AG-BENCH-EXECUTION-DATE",
                "PASS" if execution_date_available else "SUSPEND",
                (
                    "persisted trading session is available"
                    if execution_date_available
                    else "persisted trading calendar is missing"
                ),
                observed=execution_date_available,
                threshold=True,
                now=now,
            )
        )
        trading_status = (
            "REJECT"
            if trading_status_known and trading_blocked
            else "PASS"
            if trading_status_known
            else "SUSPEND"
        )
        rules.append(
            _rule(
                "AG-BENCH-TRADING-STATUS",
                trading_status,
                (
                    "snapshot trading status blocks execution"
                    if trading_status == "REJECT"
                    else "snapshot trading status is usable"
                    if trading_status == "PASS"
                    else "snapshot trading status is missing"
                ),
                observed={
                    "known": trading_status_known,
                    "blocked": trading_blocked,
                },
                threshold={"known": True, "blocked": False},
                now=now,
            )
        )
        rules.append(
            _rule(
                "AG-BENCH-DUPLICATE-ORDER",
                "REJECT" if duplicate_active_order else "PASS",
                (
                    "an active same-direction order already exists"
                    if duplicate_active_order
                    else "no duplicate active order exists"
                ),
                observed=duplicate_active_order,
                threshold=False,
                now=now,
            )
        )
        equity = account.cash_available + account.cash_reserved + total_exposure_value
        approved_qty = max(0, int(requested_quantity or 0))
        approved_pct = requested_position_pct
        if action == "BUY":
            if price is None or price <= 0 or equity <= 0:
                rules.append(
                    _rule(
                        "AG-BENCH-PRICING",
                        "SUSPEND",
                        "BUY requires reliable positive pricing and account equity",
                        observed=price,
                        threshold="positive snapshot price",
                        now=now,
                    )
                )
            else:
                desired_pct = max(0.0, float(requested_position_pct or 0))
                single_room = max(
                    Decimal("0"),
                    Decimal(str(max_single_position_pct)) * equity
                    - current_position_value,
                )
                total_room = max(
                    Decimal("0"),
                    Decimal(str(max_total_exposure_pct)) * equity
                    - total_exposure_value,
                )
                cash_room = account.cash_available
                requested_value = Decimal(str(desired_pct)) * equity
                allowed_value = min(
                    requested_value,
                    single_room,
                    total_room,
                    cash_room,
                )
                calculated = int(
                    (allowed_value / price).to_integral_value(rounding=ROUND_FLOOR)
                )
                calculated = calculated // cn_buy_lot_size * cn_buy_lot_size
                if approved_qty > 0:
                    calculated = min(calculated, approved_qty)
                approved_qty = calculated
                actual_pct = (
                    float((current_position_value + price * approved_qty) / equity)
                    if equity > 0
                    else 0.0
                )
                reduced = actual_pct + 1e-12 < desired_pct
                approved_pct = actual_pct
                rules.extend(
                    [
                        _rule(
                            "AG-BENCH-CASH",
                            "PASS" if approved_qty > 0 else "REJECT",
                            (
                                "cash supports a positive lot-rounded quantity"
                                if approved_qty > 0
                                else "cash and exposure limits reduce quantity to zero"
                            ),
                            observed=str(account.cash_available),
                            threshold=str(price * max(approved_qty, 0)),
                            original_quantity=requested_quantity,
                            adjusted_quantity=approved_qty,
                            now=now,
                        ),
                        _rule(
                            "AG-BENCH-EXPOSURE",
                            "REDUCE" if reduced and approved_qty > 0 else "PASS",
                            (
                                "position reduced to mechanical exposure limits"
                                if reduced and approved_qty > 0
                                else "position is within mechanical exposure limits"
                            ),
                            observed={
                                "single": str(current_position_value),
                                "total": str(total_exposure_value),
                            },
                            threshold={
                                "single_pct": max_single_position_pct,
                                "total_pct": max_total_exposure_pct,
                            },
                            original_position_pct=desired_pct,
                            adjusted_position_pct=actual_pct,
                            now=now,
                        ),
                    ]
                )
        else:
            desired = approved_qty if approved_qty > 0 else available_quantity
            approved_qty = min(desired, max(0, available_quantity), max(0, current_quantity))
            rules.append(
                _rule(
                    "AG-BENCH-SELL-AVAILABILITY",
                    "PASS" if approved_qty > 0 else "REJECT",
                    (
                        "sale quantity is covered by T+1-available lots"
                        if approved_qty > 0
                        else "no T+1-available position can be sold"
                    ),
                    observed={
                        "position": current_quantity,
                        "available": available_quantity,
                    },
                    threshold=desired,
                    original_quantity=desired,
                    adjusted_quantity=approved_qty,
                    now=now,
                )
            )

        statuses = {rule.status for rule in rules}
        if "REJECT" in statuses:
            status = "REJECT"
        elif "SUSPEND" in statuses:
            status = "SUSPEND"
        elif approved_qty <= 0:
            status = "REJECT"
        elif "REDUCE" in statuses:
            status = "REDUCE"
        else:
            status = "PASS"
        payload = {
            "source_type": source_type,
            "source_object_id": source_object_id,
            "account_id": account.account_id,
            "status": status,
            "action": action,
            "approved_position_pct": approved_pct,
            "approved_quantity": approved_qty,
            "rules": rules,
        }
        return BenchmarkExecutionDecision(
            benchmark_decision_id=str(
                uuid5(
                    NAMESPACE_URL,
                    f"alphaguard:benchmark:{source_type}:{source_object_id}:{account.account_id}",
                )
            ),
            **payload,
            input_hash=paper_canonical_hash(payload),
            created_at=now,
        )
