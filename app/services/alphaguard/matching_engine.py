"""Pure deterministic daily-OHLCV matching engine."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR

from tradingagents.alphaguard.paper_schemas import (
    ExecutionMarketSnapshot,
    ExecutionPolicy,
    MatchResult,
    PaperOrder,
)


class MatchingEngine:
    version = "matching-engine-v1"

    @staticmethod
    def _tick(
        value: Decimal,
        tick: Decimal,
        *,
        side: str,
    ) -> Decimal:
        units = value / tick
        rounded = units.to_integral_value(
            rounding=ROUND_CEILING if side == "BUY" else ROUND_FLOOR
        )
        return rounded * tick

    def match(
        self,
        *,
        order: PaperOrder,
        snapshot: ExecutionMarketSnapshot,
        policy: ExecutionPolicy,
        valid_reserved_quantity: int,
        matched_at: datetime,
    ) -> MatchResult:
        if policy.matching_engine_version != self.version:
            return MatchResult(
                status="BLOCKED",
                reason="matching engine version mismatch",
            )
        if order.status not in {"SUBMITTED", "PENDING", "PARTIALLY_FILLED"}:
            return MatchResult(
                status="BLOCKED",
                reason=f"order status {order.status} is not matchable",
            )
        if order.symbol != snapshot.symbol or order.market != snapshot.market:
            return MatchResult(
                status="BLOCKED",
                reason="order and execution snapshot identity mismatch",
            )
        if matched_at.date() != snapshot.trade_date:
            return MatchResult(
                status="BLOCKED",
                reason="matched_at date differs from execution snapshot",
            )
        if matched_at < order.earliest_execute_at:
            return MatchResult(
                status="NO_FILL",
                reason="order has not reached earliest_execute_at",
            )
        if matched_at > order.expires_at:
            return MatchResult(
                status="BLOCKED",
                reason="order has expired",
            )
        if snapshot.suspended:
            return MatchResult(
                status="NO_FILL",
                reason="symbol is suspended on the execution date",
            )
        if order.side == "BUY" and snapshot.st_status and not policy.st_buy_enabled:
            return MatchResult(
                status="NO_FILL",
                reason="ST/risk-warning status blocks simulated BUY",
            )
        if (
            order.side == "BUY"
            and snapshot.open == snapshot.high == snapshot.low == snapshot.limit_up_price
        ):
            return MatchResult(
                status="NO_FILL",
                reason="one-price limit-up blocks simulated BUY",
            )
        if (
            order.side == "SELL"
            and snapshot.open == snapshot.high == snapshot.low == snapshot.limit_down_price
        ):
            return MatchResult(
                status="NO_FILL",
                reason="one-price limit-down blocks simulated SELL",
            )

        base: Decimal | None = None
        if order.order_type == "MARKET_ON_OPEN":
            base = snapshot.open
        elif order.side == "BUY":
            assert order.limit_price is not None
            if snapshot.open <= order.limit_price:
                base = snapshot.open
            elif snapshot.low <= order.limit_price:
                base = order.limit_price
        else:
            assert order.limit_price is not None
            if snapshot.open >= order.limit_price:
                base = snapshot.open
            elif snapshot.high >= order.limit_price:
                base = order.limit_price
        if base is None:
            return MatchResult(
                status="NO_FILL",
                reason="daily OHLCV did not reach the order price",
            )

        bps = (
            policy.buy_slippage_bps
            if order.side == "BUY"
            else policy.sell_slippage_bps
        )
        multiplier = (
            Decimal("1") + bps / Decimal("10000")
            if order.side == "BUY"
            else Decimal("1") - bps / Decimal("10000")
        )
        slipped = base * multiplier
        if order.order_type == "LIMIT":
            assert order.limit_price is not None
            slipped = (
                min(order.limit_price, slipped)
                if order.side == "BUY"
                else max(order.limit_price, slipped)
            )
        price = self._tick(slipped, policy.price_tick, side=order.side)
        if order.order_type == "LIMIT":
            assert order.limit_price is not None
            if order.side == "BUY":
                limit_cap = (
                    order.limit_price / policy.price_tick
                ).to_integral_value(rounding=ROUND_FLOOR) * policy.price_tick
                price = min(price, limit_cap)
            else:
                limit_floor = (
                    order.limit_price / policy.price_tick
                ).to_integral_value(rounding=ROUND_CEILING) * policy.price_tick
                price = max(price, limit_floor)
        price = min(max(price, snapshot.limit_down_price), snapshot.limit_up_price)
        capacity = int(
            (Decimal(snapshot.volume) * policy.max_participation_rate).to_integral_value(
                rounding=ROUND_FLOOR
            )
        )
        if order.side == "BUY":
            capacity = capacity // policy.cn_buy_lot_size * policy.cn_buy_lot_size
        quantity = min(
            order.remaining_quantity,
            max(0, capacity),
            max(0, valid_reserved_quantity),
        )
        if order.side == "BUY":
            quantity = quantity // policy.cn_buy_lot_size * policy.cn_buy_lot_size
        if quantity <= 0:
            return MatchResult(
                status="NO_FILL",
                reason="volume capacity or valid reservation is zero",
                pricing_reference=base,
                capacity_quantity=capacity,
            )
        status = (
            "FULL_FILL"
            if quantity == order.remaining_quantity
            else "PARTIAL_FILL"
        )
        return MatchResult(
            status=status,
            quantity=quantity,
            price=price,
            reason=(
                "order fully matched against deterministic daily OHLCV"
                if status == "FULL_FILL"
                else "order partially matched at participation/reservation limit"
            ),
            pricing_reference=base,
            capacity_quantity=capacity,
            matching_engine_version=self.version,
        )
