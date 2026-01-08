"""
Cleanup routines extracted from DatabaseService.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict

from app.core.database import get_mongo_db


async def cleanup_old_data(days: int) -> Dict[str, Any]:
    db = get_mongo_db()
    cutoff_date = datetime.utcnow() - timedelta(days=days)

    deleted_count = 0
    cleaned_collections = []

    res = await db.analysis_tasks.delete_many({
        "created_at": {"$lt": cutoff_date},
        "status": {"$in": ["completed", "failed"]},
    })
    if res.deleted_count:
        deleted_count += res.deleted_count
        cleaned_collections.append(f"analysis_tasks: {res.deleted_count}")

    res = await db.user_sessions.delete_many({"created_at": {"$lt": cutoff_date}})
    if res.deleted_count:
        deleted_count += res.deleted_count
        cleaned_collections.append(f"user_sessions: {res.deleted_count}")

    res = await db.login_attempts.delete_many({"timestamp": {"$lt": cutoff_date}})
    if res.deleted_count:
        deleted_count += res.deleted_count
        cleaned_collections.append(f"login_attempts: {res.deleted_count}")

    return {
        "deleted_count": deleted_count,
        "cleaned_collections": cleaned_collections,
        "cutoff_date": cutoff_date.isoformat(),
    }


async def cleanup_analysis_results(days: int) -> Dict[str, Any]:
    db = get_mongo_db()
    cutoff_date = datetime.utcnow() - timedelta(days=days)

    deleted_count = 0
    cleaned_collections = []

    res = await db.analysis_tasks.delete_many({
        "created_at": {"$lt": cutoff_date},
        "status": {"$in": ["completed", "failed"]},
    })
    if res.deleted_count:
        deleted_count += res.deleted_count
        cleaned_collections.append(f"analysis_tasks: {res.deleted_count}")

    res = await db.analysis_results.delete_many({"created_at": {"$lt": cutoff_date}})
    if res.deleted_count:
        deleted_count += res.deleted_count
        cleaned_collections.append(f"analysis_results: {res.deleted_count}")

    return {
        "deleted_count": deleted_count,
        "cleaned_collections": cleaned_collections,
        "cutoff_date": cutoff_date.isoformat(),
    }


async def cleanup_operation_logs(days: int) -> Dict[str, Any]:
    db = get_mongo_db()
    cutoff_date = datetime.utcnow() - timedelta(days=days)

    deleted_count = 0
    cleaned_collections = []

    res = await db.user_sessions.delete_many({"created_at": {"$lt": cutoff_date}})
    if res.deleted_count:
        deleted_count += res.deleted_count
        cleaned_collections.append(f"user_sessions: {res.deleted_count}")

    res = await db.login_attempts.delete_many({"timestamp": {"$lt": cutoff_date}})
    if res.deleted_count:
        deleted_count += res.deleted_count
        cleaned_collections.append(f"login_attempts: {res.deleted_count}")

    res = await db.operation_logs.delete_many({"timestamp": {"$lt": cutoff_date}})
    if res.deleted_count:
        deleted_count += res.deleted_count
        cleaned_collections.append(f"operation_logs: {res.deleted_count}")

    return {
        "deleted_count": deleted_count,
        "cleaned_collections": cleaned_collections,
        "cutoff_date": cutoff_date.isoformat(),
    }

