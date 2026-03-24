"""
mem0 统一记忆层 API

提供记忆健康检查、状态查询、列表浏览、语义搜索和删除管理接口。
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Body, Depends, Query
from app.routers.auth_db import get_current_user
from app.core.database import get_mongo_db
from motor.motor_asyncio import AsyncIOMotorDatabase

router = APIRouter(prefix="/api/memory", tags=["memory"])
logger = logging.getLogger(__name__)

ALL_SCOPES = [
    "conversation", "user_preference", "analysis_insight",
    "skill_lesson", "agent_experience", "trade_pattern",
]


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
    """获取当前用户的记忆统计（按 scope 计数）"""
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

    all_result = await svc.get_all(user_id=user_id, limit=200, page=1)
    total = all_result["total"]
    scope_counts: dict[str, int] = {}
    for item in all_result["items"]:
        s = item.scope or "unknown"
        scope_counts[s] = scope_counts.get(s, 0) + 1

    if total > len(all_result["items"]):
        remaining = await svc.get_all(user_id=user_id, limit=total, page=1)
        scope_counts = {}
        for item in remaining["items"]:
            s = item.scope or "unknown"
            scope_counts[s] = scope_counts.get(s, 0) + 1

    return {
        "success": True,
        "data": {
            "enabled": True,
            "available": True,
            "user_id": user_id,
            "total": total,
            "scopes": scope_counts,
        },
    }


@router.get("/list")
async def memory_list(
    scope: Optional[str] = Query(None, description="按 scope 过滤"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """分页获取当前用户的记忆列表"""
    from core.memory.service import get_memory_service
    user_id = user.get("user_id", "")
    svc = get_memory_service(db)

    scopes = [scope] if scope else None
    result = await svc.get_all(
        user_id=user_id, scopes=scopes, limit=page_size, page=page,
    )
    return {
        "success": True,
        "data": {
            "items": [item.model_dump() for item in result["items"]],
            "total": result["total"],
            "page": page,
            "page_size": page_size,
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
    """语义搜索记忆"""
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


@router.post("/batch-delete")
async def memory_batch_delete(
    memory_ids: List[str] = Body(..., embed=True),
    user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """批量删除记忆"""
    from core.memory.service import get_memory_service
    svc = get_memory_service(db)
    deleted = 0
    for mid in memory_ids[:50]:
        if await svc.delete_memory(mid):
            deleted += 1
    return {"success": True, "data": {"deleted": deleted, "requested": len(memory_ids)}}


@router.delete("/clear-all")
async def memory_delete_all(
    user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """清除当前用户的全部记忆"""
    from core.memory.service import get_memory_service
    user_id = user.get("user_id", "")
    svc = get_memory_service(db)
    count = await svc.delete_all_user_memories(user_id)
    return {"success": True, "data": {"deleted": count}}


@router.delete("/{memory_id}")
async def memory_delete(
    memory_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """删除单条记忆"""
    from core.memory.service import get_memory_service
    svc = get_memory_service(db)
    ok = await svc.delete_memory(memory_id)
    if ok:
        return {"success": True, "message": "记忆已删除"}
    return {"success": False, "message": "删除失败，请稍后重试"}
