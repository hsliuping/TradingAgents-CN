"""
mem0 统一记忆层 API

提供记忆健康检查、状态查询、列表浏览、语义搜索和删除管理接口。
"""

import logging
import re
from typing import List, Optional

from fastapi import APIRouter, Body, Depends, Query
from fastapi.responses import JSONResponse
from app.routers.auth_db import get_current_user
from app.core.database import get_mongo_db
from motor.motor_asyncio import AsyncIOMotorDatabase

router = APIRouter(prefix="/api/memory", tags=["memory"])
logger = logging.getLogger(__name__)

ALL_SCOPES = [
    "conversation", "user_preference", "analysis_insight",
    "skill_lesson", "agent_experience", "trade_pattern",
]


def _resolve_user_id(user: dict) -> str:
    return str(user.get("user_id") or user.get("id") or "")


def _build_metadata_filters(
    *,
    object_type: Optional[str] = None,
    symbol: Optional[str] = None,
    market: Optional[str] = None,
    memory_kind: Optional[str] = None,
) -> Optional[dict[str, str]]:
    filters: dict[str, str] = {}
    if object_type:
        filters["object_type"] = object_type.strip().lower()
    if symbol:
        filters["symbol"] = symbol.strip().upper()
    if market:
        filters["market"] = market.strip().lower()
    if memory_kind:
        filters["memory_kind"] = memory_kind.strip().lower()
    return filters or None


@router.get("/health")
async def memory_health(db: AsyncIOMotorDatabase = Depends(get_mongo_db)):
    """mem0 记忆层健康检查"""
    from core.memory.service import get_memory_service
    svc = get_memory_service(db)
    result = await svc.health_check()
    ok = bool(result.get("ok", False))
    return JSONResponse(
        status_code=200 if ok else 503,
        content={
            "success": ok,
            "data": result,
            "message": "" if ok else (result.get("error") or "记忆层不可用"),
        },
    )


@router.get("/stats")
async def memory_stats(
    user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """获取当前用户的记忆统计（按 scope 计数）"""
    from core.memory.service import get_memory_service, _is_mem0_enabled
    user_id = _resolve_user_id(user)
    logger.info("[memory-api] stats request — resolved_user_id=%s", user_id)

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
    object_type: Optional[str] = Query(None, description="按对象类型过滤"),
    symbol: Optional[str] = Query(None, description="按股票代码过滤"),
    market: Optional[str] = Query(None, description="按市场过滤"),
    memory_kind: Optional[str] = Query(None, description="按记忆类型过滤"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """分页获取当前用户的记忆列表"""
    from core.memory.service import get_memory_service
    user_id = _resolve_user_id(user)
    logger.info(
        "[memory-api] list request — resolved_user_id=%s scope=%s page=%d page_size=%d",
        user_id, scope, page, page_size,
    )
    svc = get_memory_service(db)

    scopes = [scope] if scope else None
    metadata_filters = _build_metadata_filters(
        object_type=object_type,
        symbol=symbol,
        market=market,
        memory_kind=memory_kind,
    )
    result = await svc.get_all(
        user_id=user_id,
        scopes=scopes,
        metadata_filters=metadata_filters,
        limit=page_size,
        page=page,
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
    object_type: Optional[str] = Query(None, description="按对象类型过滤"),
    symbol: Optional[str] = Query(None, description="按股票代码过滤"),
    market: Optional[str] = Query(None, description="按市场过滤"),
    memory_kind: Optional[str] = Query(None, description="按记忆类型过滤"),
    limit: int = Query(5, ge=1, le=20),
    user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """语义搜索记忆"""
    from core.memory.service import get_memory_service
    user_id = _resolve_user_id(user)
    logger.info(
        "[memory-api] recall request — resolved_user_id=%s scope=%s limit=%d query=%s",
        user_id, scope, limit, query[:80],
    )
    svc = get_memory_service(db)

    scopes = [scope] if scope else None
    metadata_filters = _build_metadata_filters(
        object_type=object_type,
        symbol=symbol,
        market=market,
        memory_kind=memory_kind,
    )
    items = await svc.recall(
        query=query,
        user_id=user_id,
        scopes=scopes,
        metadata_filters=metadata_filters,
        limit=limit,
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
    user_id = _resolve_user_id(user)
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


# =============================================================================
# 智能助手事实记忆（assistant_memory_facts）
# 与 mem0 对象记忆不同：事实记忆由智能助手从联网工具结果中提取（含数字的
# 短句，≤150字符），存于 assistant_memory_facts 集合，跨会话召回供助手引用。
# 这里提供只读浏览、搜索与删除能力。
# =============================================================================
_FACTS_COLLECTION = "assistant_memory_facts"


def _serialize_fact(doc: dict) -> dict:
    """把事实文档序列化为前端可用 dict（_id -> id）。"""
    out = {"id": str(doc["_id"])}
    out.update({k: v for k, v in doc.items() if k != "_id"})
    return out


@router.get("/assistant-facts")
async def assistant_facts_list(
    q: Optional[str] = Query(None, description="按主题/内容关键词搜索"),
    symbol: Optional[str] = Query(None, description="按股票代码过滤"),
    category: Optional[str] = Query(None, description="按数据类别过滤"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """分页查询智能助手提取的事实记忆（按采集时间倒序）。"""
    query: dict = {}
    if q:
        q = q.strip()
        if q:
            query["$or"] = [
                {"topic": {"$regex": re.escape(q), "$options": "i"}},
                {"content": {"$regex": re.escape(q), "$options": "i"}},
            ]
    if symbol:
        query["symbol"] = symbol.strip()
    if category:
        query["category"] = category.strip()
    total = await db[_FACTS_COLLECTION].count_documents(query)
    cursor = (
        db[_FACTS_COLLECTION]
        .find(query)
        .sort("fetched_at", -1)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    items = [_serialize_fact(doc) async for doc in cursor]
    logger.info("[memory-api] assistant-facts list — page=%d page_size=%d total=%d", page, page_size, total)
    return {
        "success": True,
        "data": {"items": items, "total": total, "page": page, "page_size": page_size},
    }


@router.post("/assistant-facts/batch-delete")
async def assistant_facts_batch_delete(
    fact_ids: List[str] = Body(..., embed=True),
    user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """批量删除事实记忆。"""
    from bson import ObjectId
    ids = [ObjectId(fid) for fid in fact_ids[:100] if ObjectId.is_valid(fid)]
    result = await db[_FACTS_COLLECTION].delete_many({"_id": {"$in": ids}})
    return {
        "success": True,
        "data": {"deleted": result.deleted_count, "requested": len(fact_ids)},
    }


@router.delete("/assistant-facts/{fact_id}")
async def assistant_facts_delete(
    fact_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """删除单条事实记忆。"""
    from bson import ObjectId
    if not ObjectId.is_valid(fact_id):
        return {"success": False, "message": "无效的事实 ID"}
    result = await db[_FACTS_COLLECTION].delete_one({"_id": ObjectId(fact_id)})
    if result.deleted_count:
        return {"success": True, "message": "事实记忆已删除"}
    return {"success": False, "message": "删除失败，请稍后重试"}
