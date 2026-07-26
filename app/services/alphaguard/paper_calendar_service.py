"""Persisted CN trading-calendar access with no natural-day fallback."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any


def _session_date(document: dict[str, Any]) -> date | None:
    raw = (
        document.get("session_date")
        or document.get("trade_date")
        or document.get("date")
        or document.get("calendar_date")
    )
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    try:
        return date.fromisoformat(str(raw)[:10])
    except (TypeError, ValueError):
        return None


def _is_open(document: dict[str, Any]) -> bool | None:
    for field in ("is_open", "open", "is_trading_day"):
        if field in document:
            value = document[field]
            if isinstance(value, str):
                normalized = value.strip().upper()
                if normalized in {"1", "TRUE", "Y", "YES", "OPEN"}:
                    return True
                if normalized in {"0", "FALSE", "N", "NO", "CLOSED"}:
                    return False
            return bool(value)
    return None


class TradingCalendarUnavailable(LookupError):
    pass


class PaperTradingCalendarService:
    def __init__(self, db):
        self.collection = db["trading_calendar"]

    async def open_dates(
        self,
        *,
        after: date | None = None,
        on_or_after: date | None = None,
        count: int | None = None,
    ) -> list[date]:
        documents = await self.collection.find(
            {
                "$or": [
                    {"market": "CN"},
                    {"market": "A股"},
                    {"market": {"$exists": False}},
                ]
            }
        ).to_list(length=None)
        sessions: set[date] = set()
        for document in documents:
            session = _session_date(document)
            if session is None or _is_open(document) is not True:
                continue
            if after is not None and session <= after:
                continue
            if on_or_after is not None and session < on_or_after:
                continue
            sessions.add(session)
        result = sorted(sessions)
        return result[:count] if count is not None else result

    async def next_open_date(self, after: date) -> date:
        sessions = await self.open_dates(after=after, count=1)
        if not sessions:
            raise TradingCalendarUnavailable(
                f"no persisted CN open session exists after {after.isoformat()}"
            )
        return sessions[0]

    async def is_open_date(self, value: date) -> bool:
        sessions = await self.open_dates(on_or_after=value)
        return bool(sessions and sessions[0] == value)

    async def execution_window(
        self,
        *,
        earliest_date: date,
        validity_sessions: int,
    ) -> tuple[datetime, datetime]:
        sessions = await self.open_dates(
            on_or_after=earliest_date,
            count=validity_sessions,
        )
        if len(sessions) < validity_sessions:
            raise TradingCalendarUnavailable(
                "persisted CN calendar does not cover the execution validity window"
            )
        earliest = datetime.combine(sessions[0], time(9, 30))
        expires = datetime.combine(sessions[-1], time(15, 0))
        return earliest, expires
