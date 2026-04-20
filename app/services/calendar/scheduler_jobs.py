from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict

from app.core.database import get_mongo_db
from app.services.calendar.calendar_analysis_service import get_calendar_analysis_service
from app.services.calendar.calendar_service import get_calendar_service


async def run_calendar_sync(days_ahead: int) -> Dict[str, Any]:
    svc = get_calendar_service()
    start = date.today()
    end = start + timedelta(days=int(days_ahead))
    return await svc.sync(start, end)


async def run_calendar_preanalyze(days_ahead: int, min_importance: int, max_items: int) -> Dict[str, Any]:
    db = get_mongo_db()
    start = date.today()
    end = start + timedelta(days=int(days_ahead))

    q = {
        "date": {"$gte": start.isoformat(), "$lte": end.isoformat()},
        "importance": {"$gte": int(min_importance)},
    }
    cursor = db.calendar_events.find(q, {"_id": 0, "event_id": 1}).sort([("start_time", 1)]).limit(int(max_items))

    svc = get_calendar_analysis_service()
    enqueued = 0
    async for doc in cursor:
        event_id = doc.get("event_id")
        if not event_id:
            continue
        existing = await db.calendar_ai_analyses.find_one(
            {"event_id": event_id, "status": "completed"},
            projection={"_id": 1},
            sort=[("created_at", -1)],
        )
        if existing:
            continue
        await svc.enqueue_analysis(event_id=event_id, requested_by="system", model_name=None, force_refresh=False)
        enqueued += 1

    await db.calendar_preanalyze_logs.insert_one(
        {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "min_importance": int(min_importance),
            "max_items": int(max_items),
            "enqueued": int(enqueued),
            "created_at": datetime.utcnow(),
        }
    )
    return {"enqueued": int(enqueued)}
