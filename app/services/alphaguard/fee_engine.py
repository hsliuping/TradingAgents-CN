"""Deterministic Decimal fee calculation from a versioned CN policy."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from tradingagents.alphaguard.paper_schemas import FeeBreakdown, FeePolicy


class FeePolicyError(ValueError):
    pass


class FeeEngine:
    version = "fee-engine-v1"

    @staticmethod
    def calculate(
        *,
        side: str,
        notional: Decimal,
        policy: FeePolicy,
    ) -> FeeBreakdown:
        if side not in {"BUY", "SELL"}:
            raise FeePolicyError("unsupported fee side")
        if notional <= 0:
            raise FeePolicyError("fee notional must be positive")
        required = (
            policy.commission_rate,
            policy.minimum_commission,
            policy.sell_stamp_duty_rate,
            policy.transfer_fee_rate,
            policy.money_quantum,
        )
        if any(value is None for value in required):
            raise FeePolicyError("required CN fee policy field is missing")
        quantum = policy.money_quantum

        def money(value: Decimal) -> Decimal:
            return value.quantize(quantum, rounding=ROUND_HALF_UP)

        commission = money(
            max(notional * policy.commission_rate, policy.minimum_commission)
        )
        stamp = money(
            notional * policy.sell_stamp_duty_rate
            if side == "SELL"
            else Decimal("0")
        )
        transfer = money(notional * policy.transfer_fee_rate)
        regulatory = money(notional * policy.regulatory_fee_rate)
        other = money(notional * policy.other_fee_rate)
        return FeeBreakdown(
            commission=commission,
            stamp_duty=stamp,
            transfer_fee=transfer,
            regulatory_fee=regulatory,
            other_fees=other,
            total_fee=commission + stamp + transfer + regulatory + other,
            fee_policy_version=policy.version,
            calculation_scope=policy.calculation_scope,
        )

    @classmethod
    def conservative_reserve(
        cls,
        *,
        quantity: int,
        price: Decimal,
        policy: FeePolicy,
    ) -> tuple[Decimal, FeeBreakdown]:
        if quantity <= 0 or price <= 0:
            raise FeePolicyError("cash reservation requires positive quantity and price")
        notional = price * quantity
        fees = cls.calculate(side="BUY", notional=notional, policy=policy)
        return notional + fees.total_fee, fees
