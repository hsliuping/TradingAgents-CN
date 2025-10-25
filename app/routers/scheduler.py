#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
定时任务管理路由
提供定时任务的查询、暂停、恢复、手动触发等功能
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel

from app.routers.auth_db import get_current_user
from app.services.scheduler_service import get_scheduler_service, SchedulerService
from app.core.response import ok

router = APIRouter(prefix="/api/scheduler", tags=["scheduler"])


class JobTriggerRequest(BaseModel):
    """手动触发任务请求"""
    job_id: str
    kwargs: Optional[Dict[str, Any]] = None


class JobUpdateRequest(BaseModel):
    """更新任务请求"""
    job_id: str
    enabled: Optional[bool] = None
    cron: Optional[str] = None


class JobMetadataUpdateRequest(BaseModel):
    """更新任务元数据请求"""
    display_name: Optional[str] = None
    description: Optional[str] = None


@router.get("/jobs")
async def list_jobs(
    user: dict = Depends(get_current_user),
    service: SchedulerService = Depends(get_scheduler_service)
):
    """
    获取所有定时任务列表
    
    Returns:
        任务列表，包含任务ID、名称、状态、下次执行时间等信息
    """
    try:
        jobs = await service.list_jobs()
        return ok(data=jobs, message=f"获取到 {len(jobs)} 个定时任务")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取任务列表失败: {str(e)}")


@router.put("/jobs/{job_id}/metadata")
async def update_job_metadata_route(
    job_id: str,
    request: JobMetadataUpdateRequest,
    user: dict = Depends(get_current_user),
    service: SchedulerService = Depends(get_scheduler_service)
):
    """
    更新任务元数据（触发器名称和备注）

    Args:
        job_id: 任务ID
        request: 更新请求

    Returns:
        操作结果
    """
    # 检查管理员权限
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="仅管理员可以更新任务元数据")

    try:
        success = await service.update_job_metadata(
            job_id,
            display_name=request.display_name,
            description=request.description
        )
        if success:
            return ok(message=f"任务 {job_id} 元数据已更新")
        else:
            raise HTTPException(status_code=400, detail=f"更新任务 {job_id} 元数据失败")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新任务元数据失败: {str(e)}")


@router.get("/jobs/{job_id}")
async def get_job_detail(
    job_id: str,
    user: dict = Depends(get_current_user),
    service: SchedulerService = Depends(get_scheduler_service)
):
    """
    获取任务详情

    Args:
        job_id: 任务ID

    Returns:
        任务详细信息
    """
    try:
        job = await service.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"任务 {job_id} 不存在")
        return ok(data=job, message="获取任务详情成功")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取任务详情失败: {str(e)}")


@router.post("/jobs/{job_id}/pause")
async def pause_job(
    job_id: str,
    user: dict = Depends(get_current_user),
    service: SchedulerService = Depends(get_scheduler_service)
):
    """
    暂停任务
    
    Args:
        job_id: 任务ID
        
    Returns:
        操作结果
    """
    # 检查管理员权限
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="仅管理员可以暂停任务")
    
    try:
        success = await service.pause_job(job_id)
        if success:
            return ok(message=f"任务 {job_id} 已暂停")
        else:
            raise HTTPException(status_code=400, detail=f"暂停任务 {job_id} 失败")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"暂停任务失败: {str(e)}")


@router.post("/jobs/{job_id}/resume")
async def resume_job(
    job_id: str,
    user: dict = Depends(get_current_user),
    service: SchedulerService = Depends(get_scheduler_service)
):
    """
    恢复任务
    
    Args:
        job_id: 任务ID
        
    Returns:
        操作结果
    """
    # 检查管理员权限
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="仅管理员可以恢复任务")
    
    try:
        success = await service.resume_job(job_id)
        if success:
            return ok(message=f"任务 {job_id} 已恢复")
        else:
            raise HTTPException(status_code=400, detail=f"恢复任务 {job_id} 失败")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"恢复任务失败: {str(e)}")


@router.post("/jobs/{job_id}/trigger")
async def trigger_job(
    job_id: str,
    user: dict = Depends(get_current_user),
    service: SchedulerService = Depends(get_scheduler_service)
):
    """
    手动触发任务执行
    
    Args:
        job_id: 任务ID
        
    Returns:
        操作结果
    """
    # 检查管理员权限
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="仅管理员可以手动触发任务")
    
    try:
        success = await service.trigger_job(job_id)
        if success:
            return ok(message=f"任务 {job_id} 已触发执行")
        else:
            raise HTTPException(status_code=400, detail=f"触发任务 {job_id} 失败")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"触发任务失败: {str(e)}")


@router.get("/jobs/{job_id}/history")
async def get_job_history(
    job_id: str,
    limit: int = Query(20, ge=1, le=100, description="返回数量限制"),
    offset: int = Query(0, ge=0, description="偏移量"),
    user: dict = Depends(get_current_user),
    service: SchedulerService = Depends(get_scheduler_service)
):
    """
    获取任务执行历史
    
    Args:
        job_id: 任务ID
        limit: 返回数量限制
        offset: 偏移量
        
    Returns:
        任务执行历史记录
    """
    try:
        history = await service.get_job_history(job_id, limit=limit, offset=offset)
        total = await service.count_job_history(job_id)
        
        return ok(
            data={
                "history": history,
                "total": total,
                "limit": limit,
                "offset": offset
            },
            message=f"获取到 {len(history)} 条执行记录"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取执行历史失败: {str(e)}")


@router.get("/history")
async def get_all_history(
    limit: int = Query(50, ge=1, le=200, description="返回数量限制"),
    offset: int = Query(0, ge=0, description="偏移量"),
    job_id: Optional[str] = Query(None, description="任务ID过滤"),
    status: Optional[str] = Query(None, description="状态过滤: success/failed"),
    user: dict = Depends(get_current_user),
    service: SchedulerService = Depends(get_scheduler_service)
):
    """
    获取所有任务执行历史
    
    Args:
        limit: 返回数量限制
        offset: 偏移量
        job_id: 任务ID过滤
        status: 状态过滤
        
    Returns:
        所有任务执行历史记录
    """
    try:
        history = await service.get_all_history(
            limit=limit,
            offset=offset,
            job_id=job_id,
            status=status
        )
        total = await service.count_all_history(job_id=job_id, status=status)
        
        return ok(
            data={
                "history": history,
                "total": total,
                "limit": limit,
                "offset": offset
            },
            message=f"获取到 {len(history)} 条执行记录"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取执行历史失败: {str(e)}")


@router.get("/stats")
async def get_scheduler_stats(
    user: dict = Depends(get_current_user),
    service: SchedulerService = Depends(get_scheduler_service)
):
    """
    获取调度器统计信息
    
    Returns:
        调度器统计信息，包括任务总数、运行中任务数、暂停任务数等
    """
    try:
        stats = await service.get_stats()
        return ok(data=stats, message="获取统计信息成功")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取统计信息失败: {str(e)}")


@router.get("/health")
async def scheduler_health_check(
    user: dict = Depends(get_current_user),
    service: SchedulerService = Depends(get_scheduler_service)
):
    """
    调度器健康检查
    
    Returns:
        调度器健康状态
    """
    try:
        health = await service.health_check()
        return ok(data=health, message="调度器运行正常")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"健康检查失败: {str(e)}")

