"""Utilities for updating analysis task status.

Extracted from AnalysisService to reduce file size and improve modularity
without changing external behavior.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Dict, Any

from app.core.database import get_mongo_db
from app.core.redis_client import get_redis_service, RedisKeys
from app.models.analysis import AnalysisStatus, AnalysisResult


async def perform_update_task_status(
    task_id: str,
    status: AnalysisStatus,
    progress: int,
    result: Optional[AnalysisResult] = None,
) -> None:
    """Update a task's status in MongoDB and Redis.

    Mirrors the original logic in AnalysisService._update_task_status.
    """
    db = get_mongo_db()
    redis_service = get_redis_service()

    update_data: Dict[str, Any] = {
        "status": status,
        "progress": progress,
        "updated_at": datetime.utcnow(),
    }

    if status == AnalysisStatus.PROCESSING and "started_at" not in update_data:
        update_data["started_at"] = datetime.utcnow()
    elif status in [AnalysisStatus.COMPLETED, AnalysisStatus.FAILED]:
        update_data["completed_at"] = datetime.utcnow()
        if result:
            update_data["result"] = result.dict()

    await db.analysis_tasks.update_one({"task_id": task_id}, {"$set": update_data})

    progress_key = RedisKeys.TASK_PROGRESS.format(task_id=task_id)
    await redis_service.set_json(
        progress_key,
        {
            "task_id": task_id,
            "status": status,
            "progress": progress,
            "updated_at": datetime.utcnow().isoformat(),
        },
        ttl=3600,
    )


async def perform_update_task_status_with_tracker(
    task_id: str,
    status: AnalysisStatus,
    progress_tracker,  # RedisProgressTracker
    result: Optional[AnalysisResult] = None,
) -> None:
    """Update task status using detailed data from a progress tracker.

    Mirrors the original logic in AnalysisService._update_task_status_with_tracker.
    """
    db = get_mongo_db()
    redis_service = get_redis_service()

    progress_data = progress_tracker.to_dict()

    update_data: Dict[str, Any] = {
        "status": status,
        "progress": progress_data["progress"],
        "current_step": progress_data["current_step"],
        "message": progress_data["message"],
        "updated_at": datetime.utcnow(),
    }

    if status == AnalysisStatus.PROCESSING and "started_at" not in update_data:
        update_data["started_at"] = datetime.utcnow()
    elif status in [AnalysisStatus.COMPLETED, AnalysisStatus.FAILED]:
        update_data["completed_at"] = datetime.utcnow()
        if result:
            update_data["result"] = result.dict()

    await db.analysis_tasks.update_one({"task_id": task_id}, {"$set": update_data})

    progress_key = RedisKeys.TASK_PROGRESS.format(task_id=task_id)
    await redis_service.set_json(
        progress_key,
        {
            "task_id": task_id,
            "status": status.value if hasattr(status, "value") else status,
            "progress": progress_data["progress"],
            "current_step": progress_data["current_step"],
            "message": progress_data["message"],
            "elapsed_time": progress_data["elapsed_time"],
            "remaining_time": progress_data["remaining_time"],
            "steps": progress_data["steps"],
            "updated_at": datetime.utcnow().isoformat(),
        },
        ttl=3600,
    )

