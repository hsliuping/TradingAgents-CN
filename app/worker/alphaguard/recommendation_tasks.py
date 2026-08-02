"""Idempotent scheduler entry for model-free candidate recommendation scans."""

from __future__ import annotations

from app.core.database import get_mongo_db
from app.services.alphaguard.candidate_recommendation_service import (
    CandidateRecommendationService,
)


async def scheduled_candidate_recommendation_scan() -> dict[str, int]:
    db = get_mongo_db()
    service = CandidateRecommendationService(db)
    trade_date = await service.resolve_latest_trade_date()
    users = await db["users"].find({"is_active": {"$ne": False}}).to_list(length=None)
    counts = {"created": 0, "reused": 0, "failed": 0}
    for user in users:
        user_id = str(user.get("_id") or user.get("id") or "")
        if not user_id:
            counts["failed"] += 1
            continue
        try:
            _run, created = await service.run(user_id=user_id, trade_date=trade_date)
        except Exception:
            counts["failed"] += 1
        else:
            counts["created" if created else "reused"] += 1
    await service.refresh_evaluations(as_of_trade_date=trade_date)
    return counts
