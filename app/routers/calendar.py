from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.routers.auth_db import get_current_user
from app.services.calendar.calendar_analysis_service import get_calendar_analysis_service
from app.services.calendar.calendar_queue_service import get_calendar_queue_service
from app.services.calendar.calendar_service import get_calendar_service


router = APIRouter()


def _parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


@router.post("/sync")
async def sync_calendar(
    start: str = Query(...),
    end: str = Query(...),
    user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    svc = get_calendar_service()
    try:
        res = await svc.sync(_parse_date(start), _parse_date(end))
        return {"success": True, "data": res, "message": "ok"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/events")
async def list_events(
    start: str = Query(...),
    end: str = Query(...),
    category: Optional[str] = Query(default=None),
    min_importance: Optional[int] = Query(default=None, ge=1, le=5),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    svc = get_calendar_service()
    try:
        res = await svc.list_events(
            start=_parse_date(start),
            end=_parse_date(end),
            category=category,
            min_importance=min_importance,
            limit=limit,
            offset=offset,
        )
        return {"success": True, "data": res, "message": "ok"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/events/{event_id}")
async def get_event(event_id: str, user: dict = Depends(get_current_user)) -> Dict[str, Any]:
    svc = get_calendar_service()
    doc = await svc.get_event(event_id)
    if not doc:
        raise HTTPException(status_code=404, detail="event not found")
    return {"success": True, "data": doc, "message": "ok"}


@router.post("/events/{event_id}/analyze")
async def analyze_event(
    event_id: str,
    body: Dict[str, Any] | None = None,
    user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    req = body or {}
    model_name = req.get("model_name")
    force_refresh = bool(req.get("force_refresh") or False)
    svc = get_calendar_analysis_service()
    res = await svc.enqueue_analysis(
        event_id=event_id,
        requested_by=user.get("id") or "user",
        model_name=model_name,
        force_refresh=force_refresh,
    )
    return {"success": True, "data": res, "message": "ok"}


@router.get("/analyses/{task_id}")
async def get_analysis(task_id: str, user: dict = Depends(get_current_user)) -> Dict[str, Any]:
    svc = get_calendar_analysis_service()
    doc = await svc.get_analysis_by_task_id(task_id)
    if not doc:
        qsvc = get_calendar_queue_service()
        qt = await qsvc.get_task(task_id)
        if not qt:
            raise HTTPException(status_code=404, detail="task not found")
        return {"success": True, "data": {"task": qt}, "message": "ok"}
    return {"success": True, "data": doc, "message": "ok"}


@router.get("/events/{event_id}/analysis")
async def get_latest_event_analysis(event_id: str, user: dict = Depends(get_current_user)) -> Dict[str, Any]:
    svc = get_calendar_analysis_service()
    doc = await svc.get_latest_analysis_for_event(event_id)
    if not doc:
        raise HTTPException(status_code=404, detail="analysis not found")
    return {"success": True, "data": doc, "message": "ok"}

