"""Resolve hard-risk inputs exclusively from already resolved snapshot refs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.services.alphaguard.snapshot_data_resolver import ResolvedSnapshotData


@dataclass(frozen=True)
class RiskContext:
    account: dict[str, Any] | None
    target_positions: tuple[dict[str, Any], ...]
    portfolio_positions: tuple[dict[str, Any], ...]
    orders: tuple[dict[str, Any], ...]
    instrument: dict[str, Any] | None
    latest_price: dict[str, Any] | None
    next_open_session: datetime | None


def _date(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


class RiskContextResolver:
    def resolve(
        self,
        data: ResolvedSnapshotData,
        *,
        account_id: str | None,
    ) -> RiskContext:
        accounts = [
            item
            for item in data.accounts
            if account_id is None
            or str(item.get("account_id") or f"manual-paper:{data.snapshot.user_id}")
            == account_id
        ]
        if len(accounts) > 1:
            raise ValueError("account snapshot reference is ambiguous")
        future_sessions = []
        for item in data.trading_calendar:
            is_open = item.get("is_open", item.get("open", False))
            session = _date(
                item.get("session_date")
                or item.get("trade_date")
                or item.get("date")
            )
            if is_open and session and session.date() > data.snapshot.trade_date:
                future_sessions.append(session)
        future_sessions.sort()
        return RiskContext(
            account=accounts[0] if accounts else None,
            target_positions=tuple(data.positions),
            portfolio_positions=tuple(data.portfolio_positions),
            orders=tuple(data.orders),
            instrument=data.instruments[-1] if data.instruments else None,
            latest_price=data.prices[-1] if data.prices else None,
            next_open_session=future_sessions[0] if future_sessions else None,
        )
