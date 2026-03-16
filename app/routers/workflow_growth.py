"""
工作流成长 API
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.models.agent_growth import GrowthMemoryScope, GrowthMemoryStatus, GrowthSuggestionStatus
from app.routers.auth_db import get_current_user
from app.services.workflow_growth_service import get_workflow_growth_service

router = APIRouter(prefix="/api/workflow-growth", tags=["workflow-growth"])


@router.get("/memories", summary="获取成长记忆列表")
async def list_growth_memories(
    status: Optional[GrowthMemoryStatus] = Query(None, description="状态过滤"),
    scope: Optional[GrowthMemoryScope] = Query(None, description="范围过滤"),
    task_id: Optional[str] = Query(None, description="按任务过滤"),
    limit: int = Query(50, ge=1, le=200, description="返回数量"),
    user: dict = Depends(get_current_user),
):
    service = get_workflow_growth_service()
    items = await service.list_memory_items(
        user_id=str(user["id"]),
        status=status,
        scope=scope,
        task_id=task_id,
        limit=limit,
    )
    return {"success": True, "data": {"items": items, "total": len(items)}, "message": "ok"}


@router.get("/memories/pending", summary="获取待审核成长记忆")
async def list_pending_growth_memories(
    limit: int = Query(50, ge=1, le=200, description="返回数量"),
    user: dict = Depends(get_current_user),
):
    service = get_workflow_growth_service()
    items = await service.list_memory_items(
        user_id=str(user["id"]),
        status=GrowthMemoryStatus.PENDING,
        limit=limit,
    )
    return {"success": True, "data": {"items": items, "total": len(items)}, "message": "ok"}


@router.post("/memories/{memory_id}/approve", summary="批准成长记忆")
async def approve_growth_memory(memory_id: str, user: dict = Depends(get_current_user)):
    service = get_workflow_growth_service()
    success = await service.approve_memory_item(str(user["id"]), memory_id)
    if not success:
        raise HTTPException(status_code=404, detail="成长记忆不存在")
    return {"success": True, "message": "已批准成长记忆"}


@router.post("/memories/{memory_id}/reject", summary="拒绝成长记忆")
async def reject_growth_memory(memory_id: str, user: dict = Depends(get_current_user)):
    service = get_workflow_growth_service()
    success = await service.reject_memory_item(str(user["id"]), memory_id)
    if not success:
        raise HTTPException(status_code=404, detail="成长记忆不存在")
    return {"success": True, "message": "已拒绝成长记忆"}


@router.get("/suggestions", summary="获取成长建议列表")
async def list_growth_suggestions(
    status: Optional[GrowthSuggestionStatus] = Query(None, description="状态过滤"),
    task_id: Optional[str] = Query(None, description="按任务过滤"),
    limit: int = Query(50, ge=1, le=200, description="返回数量"),
    user: dict = Depends(get_current_user),
):
    service = get_workflow_growth_service()
    items = await service.list_suggestions(
        user_id=str(user["id"]),
        status=status,
        task_id=task_id,
        limit=limit,
    )
    return {"success": True, "data": {"items": items, "total": len(items)}, "message": "ok"}


@router.post("/suggestions/{suggestion_id}/accept", summary="接受成长建议")
async def accept_growth_suggestion(suggestion_id: str, user: dict = Depends(get_current_user)):
    service = get_workflow_growth_service()
    result = await service.accept_suggestion(str(user["id"]), suggestion_id)
    if not result:
        raise HTTPException(status_code=404, detail="成长建议不存在")
    return {"success": True, "data": result, "message": "已接受成长建议"}


@router.post("/suggestions/{suggestion_id}/dismiss", summary="忽略成长建议")
async def dismiss_growth_suggestion(suggestion_id: str, user: dict = Depends(get_current_user)):
    service = get_workflow_growth_service()
    success = await service.dismiss_suggestion(str(user["id"]), suggestion_id)
    if not success:
        raise HTTPException(status_code=404, detail="成长建议不存在")
    return {"success": True, "message": "已忽略成长建议"}


@router.get("/tasks/{task_id}", summary="获取任务的成长提取结果")
async def get_task_growth_context(task_id: str, user: dict = Depends(get_current_user)):
    service = get_workflow_growth_service()
    data = await service.get_task_context(str(user["id"]), task_id)
    return {"success": True, "data": data, "message": "ok"}