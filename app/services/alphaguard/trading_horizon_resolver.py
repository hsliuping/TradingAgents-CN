"""Resolve evaluation horizons from persisted CN open sessions only."""

from __future__ import annotations

from datetime import date

from app.services.alphaguard.evaluation_policy_registry import evaluation_policy
from app.services.alphaguard.paper_calendar_service import (
    PaperTradingCalendarService,
    TradingCalendarUnavailable,
)


class TradingHorizonResolver:
    def __init__(self, db):
        self.calendar = PaperTradingCalendarService(db)
        self.horizons = evaluation_policy().horizons

    async def resolve_all(self, decision_trade_date: date) -> dict[str, date]:
        maximum = max(self.horizons.values())
        sessions = await self.calendar.open_dates(
            after=decision_trade_date,
            count=maximum,
        )
        if len(sessions) < maximum:
            raise TradingCalendarUnavailable(
                f"calendar does not cover {maximum} sessions after "
                f"{decision_trade_date.isoformat()}"
            )
        return {
            horizon: sessions[offset - 1]
            for horizon, offset in self.horizons.items()
        }

    async def resolve(
        self,
        decision_trade_date: date,
        horizon: str,
    ) -> date:
        if horizon not in self.horizons:
            raise ValueError(f"unsupported evaluation horizon: {horizon}")
        count = self.horizons[horizon]
        sessions = await self.calendar.open_dates(
            after=decision_trade_date,
            count=count,
        )
        if len(sessions) != count:
            raise TradingCalendarUnavailable(
                f"calendar does not cover {horizon} after "
                f"{decision_trade_date.isoformat()}"
            )
        return sessions[-1]
