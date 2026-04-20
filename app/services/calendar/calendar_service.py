from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from app.core.database import get_mongo_db
from app.models.calendar import CalendarEventInDB, CalendarEventRaw
from app.services.calendar.providers.base import CalendarProvider
from app.services.calendar.providers.cls_provider import ClsCalendarProvider


class CalendarService:
    def __init__(self, provider: CalendarProvider | None = None):
        self.provider = provider or ClsCalendarProvider()

    async def sync(self, start: date, end: date) -> Dict[str, Any]:
        db = get_mongo_db()
        events_raw = await self.provider.fetch_events(start, end)
        upserted = 0
        updated = 0
        for raw in events_raw:
            now = datetime.utcnow()
            q = {"source": raw.source, "source_event_id": raw.source_event_id}
            existing = await db.calendar_events.find_one(q, {"event_id": 1})
            event_id = (existing or {}).get("event_id") or str(uuid.uuid4())
            doc = {
                "event_id": event_id,
                "source": raw.source,
                "source_event_id": raw.source_event_id,
                "title": raw.title,
                "summary": raw.summary,
                "content": raw.content,
                "start_time": raw.start_time,
                "end_time": raw.end_time,
                "date": raw.start_time.strftime("%Y-%m-%d"),
                "timezone": raw.timezone,
                "region": raw.region,
                "category": raw.category,
                "importance": raw.importance,
                "status": raw.status.value,
                "tags": raw.tags,
                "raw_payload": raw.raw_payload,
                "updated_at": now,
            }
            res = await db.calendar_events.update_one(
                q,
                {"$set": doc, "$setOnInsert": {"created_at": now}},
                upsert=True,
            )
            if res.upserted_id is not None:
                upserted += 1
            elif res.matched_count:
                updated += 1

        await db.calendar_sync_logs.insert_one(
            {
                "source": getattr(self.provider, "__class__", type(self.provider)).__name__,
                "start": start.isoformat(),
                "end": end.isoformat(),
                "count": len(events_raw),
                "upserted": upserted,
                "updated": updated,
                "created_at": datetime.utcnow(),
            }
        )
        return {"count": len(events_raw), "upserted": upserted, "updated": updated}

    async def list_events(
        self,
        start: date,
        end: date,
        category: Optional[str] = None,
        min_importance: Optional[int] = None,
        limit: int = 200,
        offset: int = 0,
    ) -> Dict[str, Any]:
        db = get_mongo_db()
        q: Dict[str, Any] = {"date": {"$gte": start.isoformat(), "$lte": end.isoformat()}}
        if category:
            q["category"] = category
        if min_importance is not None:
            q["importance"] = {"$gte": int(min_importance)}

        total = await db.calendar_events.count_documents(q)
        cursor = (
            db.calendar_events.find(q, {"_id": 0})
            .sort([("start_time", 1)])
            .skip(int(offset))
            .limit(int(limit))
        )
        items: List[CalendarEventInDB] = []
        async for doc in cursor:
            items.append(CalendarEventInDB(**doc))
        return {"total": int(total), "items": [x.model_dump() for x in items]}

    async def get_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        db = get_mongo_db()
        doc = await db.calendar_events.find_one({"event_id": event_id}, {"_id": 0})
        if not doc:
            return None
        return CalendarEventInDB(**doc).model_dump()


_calendar_service: CalendarService | None = None


def get_calendar_service() -> CalendarService:
    global _calendar_service
    if _calendar_service is None:
        _calendar_service = CalendarService()
    return _calendar_service
