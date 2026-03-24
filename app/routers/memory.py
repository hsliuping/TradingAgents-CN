"""
mem0 统一记忆层 API

提供记忆健康检查、状态查询和用户记忆管理接口。
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from app.routers.auth_db import get_current_user
from app.core.database import get_mongo_db
from motor.motor_asyncio import AsyncIOMotorDatabase

router = APIRouter(prefix="/api/memory", tags=["memory"])
logger = logging.getLogger(__name__)


@router.get("/health")
async def memory_health(db: AsyncIOMotorDatabase = Depends(get_mongo_db)):
    """mem0 记忆层健康检查"""
    from core.memory.service import get_memory_service
    svc = get_memory_service(db)
    result = await svc.health_check()
    return {"success": result.get("ok", False), "data": result}


@router.get("/stats")
async def memory_stats(
    user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """获取当前用户的记忆统计"""
    from core.memory.service import get_memory_service, _is_mem0_enabled
    user_id = user.get("user_id", "")

    if not _is_mem0_enabled():
        return {
            "success": True,
            "data": {"enabled": False, "message": "记忆功能未启用"},
        }

    svc = get_memory_service(db)
    if not svc.available:
        await svc._ensure_init()

    if not svc.available:
        return {
            "success": True,
            "data": {"enabled": True, "available": False, "message": svc._init_error},
        }

    scope_counts = {}
    for scope in ["conversation", "user_preference", "analysis_insight",
                   "skill_lesson", "agent_experience", "trade_pattern"]:
        try:
            items = await svc.recall(
                query="", user_id=user_id, scopes=[scope], limit=1,
            )
            scope_counts[scope] = len(items)
        except Exception:
            scope_counts[scope] = 0

    return {
        "success": True,
        "data": {
            "enabled": True,
            "available": True,
            "user_id": user_id,
            "scopes": scope_counts,
        },
    }


@router.get("/recall")
async def memory_recall(
    query: str = Query(..., min_length=1, description="查询文本"),
    scope: Optional[str] = Query(None, description="限定 scope"),
    limit: int = Query(5, ge=1, le=20),
    user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """手动测试记忆召回"""
    from core.memory.service import get_memory_service
    user_id = user.get("user_id", "")
    svc = get_memory_service(db)

    scopes = [scope] if scope else None
    items = await svc.recall(
        query=query, user_id=user_id, scopes=scopes, limit=limit,
    )
    return {
        "success": True,
        "data": {
            "count": len(items),
            "items": [item.model_dump() for item in items],
        },
    }
