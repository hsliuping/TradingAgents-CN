from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import List

from app.models.calendar import CalendarEventRaw


class CalendarProvider(ABC):
    @abstractmethod
    async def fetch_events(self, start: date, end: date) -> List[CalendarEventRaw]:
        raise NotImplementedError()

