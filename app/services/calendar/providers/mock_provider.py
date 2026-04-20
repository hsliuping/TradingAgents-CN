from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Dict, List

from app.models.calendar import CalendarEventRaw, CalendarEventStatus
from app.services.calendar.providers.base import CalendarProvider


class MockCalendarProvider(CalendarProvider):
    def __init__(self, json_path: Path | None = None):
        if json_path is None:
            json_path = Path(__file__).resolve().parents[4] / "app" / "data" / "calendar_mock.json"
        self.json_path = json_path

    async def fetch_events(self, start: date, end: date) -> List[CalendarEventRaw]:
        items = self._load_items()
        results: List[CalendarEventRaw] = []
        for item in items:
            event = self._to_event(item)
            d = event.start_time.date()
            if start <= d <= end:
                results.append(event)
        results.sort(key=lambda x: x.start_time)
        return results

    def _load_items(self) -> List[Dict[str, Any]]:
        raw = self.json_path.read_text(encoding="utf-8")
        data = json.loads(raw)
        if not isinstance(data, list):
            return []
        return [x for x in data if isinstance(x, dict)]

    def _to_event(self, item: Dict[str, Any]) -> CalendarEventRaw:
        base_day = date.today()
        offset_days = int(item.get("offset_days") or 0)
        day = base_day + timedelta(days=offset_days)
        hhmm = str(item.get("time") or "09:30")
        try:
            hh, mm = hhmm.split(":", 1)
            t = time(int(hh), int(mm))
        except Exception:
            t = time(9, 30)
        start_time = datetime.combine(day, t)
        source_event_id = str(item.get("id") or f"mock-{offset_days}-{item.get('title', '')}")
        return CalendarEventRaw(
            source="mock",
            source_event_id=source_event_id,
            title=str(item.get("title") or ""),
            summary=item.get("summary"),
            content=item.get("content"),
            start_time=start_time,
            end_time=None,
            timezone="Asia/Shanghai",
            region=item.get("region"),
            category=str(item.get("category") or "其他"),
            importance=int(item.get("importance") or 3),
            status=CalendarEventStatus.SCHEDULED,
            tags=list(item.get("tags") or []),
            raw_payload=item,
        )

