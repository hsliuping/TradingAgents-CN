from __future__ import annotations

import asyncio
import hashlib
import time
from datetime import date, datetime, timedelta
from typing import Any, Dict, List

import requests

from app.models.calendar import CalendarEventRaw, CalendarEventStatus
from app.services.calendar.providers.base import CalendarProvider


class ClsCalendarProvider(CalendarProvider):
    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.get(
            "https://www.cls.cn/",
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
            timeout=10,
        )
        self.headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": "https://www.cls.cn/investKalendar",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Origin": "https://www.cls.cn",
        }
        self.api_url = "https://www.cls.cn/api/calendar/web/list"

    async def fetch_events(self, start: date, end: date) -> List[CalendarEventRaw]:
        return await asyncio.to_thread(self._fetch_range, start, end)

    def _get_sign(self, params: Dict[str, Any], cookie_uu: str = "") -> str:
        timestamp = str(int(time.time() * 1000))
        prefix = "12b6bb84e093532"
        sign_str = prefix + (cookie_uu or "") + "/api/calendar/web" + timestamp
        return hashlib.md5(sign_str.encode("utf-8")).hexdigest()

    def _fetch_range(self, start: date, end: date) -> List[CalendarEventRaw]:
        all_events: List[CalendarEventRaw] = []
        current = start
        while current <= end:
            last_time = int(datetime.combine(current, datetime.min.time()).timestamp() * 1000)
            result = self._get_calendar_data(last_time=last_time)
            events = self._parse_events(result)
            for item in events:
                all_events.append(self._to_event(item))
            time.sleep(1)
            current += timedelta(days=1)
        return all_events

    def _get_calendar_data(
        self, last_time: int | None = None, flag: int = 0, type_: int = 0
    ) -> Dict[str, Any]:
        if last_time is None:
            last_time = int(time.time() * 1000)
        params: Dict[str, Any] = {
            "app": "CailianpressWeb",
            "flag": flag,
            "os": "web",
            "sv": "8.4.6",
            "type": type_,
            "last_time": last_time,
            "rn": str(time.time()),
        }
        params["sign"] = self._get_sign(params)
        try:
            resp = self.session.get(self.api_url, params=params, headers=self.headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            code = data.get("code")
            if code in (0, 200) and data.get("data") is not None:
                return {"success": True, "data": data}
            return {"success": False, "error": data.get("msg") or "", "data": data}
        except Exception as e:
            return {"success": False, "error": str(e), "data": None}

    def _parse_events(self, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not result.get("success") or not result.get("data"):
            return []
        events: List[Dict[str, Any]] = []
        data = result["data"]
        calendar_list = data.get("data") or []
        for day_item in calendar_list:
            day_date = day_item.get("calendar_day") or ""
            week = day_item.get("week") or ""
            items = day_item.get("items") or []
            for item in items:
                event: Dict[str, Any] = {}
                event["date"] = day_date
                event["week"] = week
                event["time"] = item.get("calendar_time") or ""
                event["title"] = item.get("title") or ""
                event["star"] = (item.get("event") or {}).get("star") or 0
                event["country"] = (item.get("event") or {}).get("country") or ""
                event["type"] = item.get("type") or 0
                event["id"] = item.get("id") or 0
                events.append(event)
        return events

    def _to_event(self, item: Dict[str, Any]) -> CalendarEventRaw:
        date_str = str(item.get("date") or "")
        time_str = str(item.get("time") or "09:30")
        try:
            day = datetime.strptime(date_str, "%Y-%m-%d").date()
        except Exception:
            day = date.today()
        try:
            hh, mm = time_str.split(":", 1)
            dt_time = datetime.min.time().replace(hour=int(hh), minute=int(mm))
        except Exception:
            dt_time = datetime.min.time().replace(hour=9, minute=30)
        start_time = datetime.combine(day, dt_time)
        source_event_id = str(item.get("id") or "")
        importance = int(item.get("star") or 0)
        region = str(item.get("country") or "")
        category = "其他"
        tags: List[str] = []
        return CalendarEventRaw(
            source="cls",
            source_event_id=source_event_id,
            title=str(item.get("title") or ""),
            summary=None,
            content=None,
            start_time=start_time,
            end_time=None,
            timezone="Asia/Shanghai",
            region=region,
            category=category,
            importance=importance,
            status=CalendarEventStatus.SCHEDULED,
            tags=tags,
            raw_payload=item,
        )
