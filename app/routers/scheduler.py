#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
定时任务管理路由
提供定时任务的查询、暂停、恢复、手动触发等功能
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel

from app.routers.auth_db import get_current_user
from app.services.scheduler_service import get_scheduler_service, SchedulerService
from app.core.response import ok
from tradingagents.utils.logging_manager import get_logger

logger = get_logger(__name__)

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


class RescheduleRequest(BaseModel):
    """修改任务CRON表达式请求"""
    cron: str


@router.put("/jobs/{job_id}/schedule")
async def reschedule_job(
    job_id: str,
    request: RescheduleRequest,
    user: dict = Depends(get_current_user),
    service: SchedulerService = Depends(get_scheduler_service)
):
    """
    修改任务的CRON表达式

    Args:
        job_id: 任务ID
        request: 包含新CRON表达式的请求体

    Returns:
        操作结果
    """
    # 检查管理员权限
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="仅管理员可以修改任务调度")

    try:
        success = await service.reschedule_job(job_id, request.cron)
        if success:
            return ok(message=f"任务 {job_id} 调度已更新为: {request.cron}")
        else:
            raise HTTPException(status_code=400, detail=f"修改任务 {job_id} 调度失败，请检查CRON表达式格式")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"修改任务调度失败: {str(e)}")


@router.post("/jobs/{job_id}/trigger")
async def trigger_job(
    job_id: str,
    user: dict = Depends(get_current_user),
    service: SchedulerService = Depends(get_scheduler_service),
    force: bool = Query(False, description="是否强制执行（跳过交易时间检查等）"),
    incremental: Optional[bool] = Query(None, description="是否增量同步（仅历史数据同步任务有效，None=使用默认值）")
):
    """
    手动触发任务执行

    Args:
        job_id: 任务ID
        force: 是否强制执行（跳过交易时间检查等），默认 False
        incremental: 是否增量同步（仅历史数据同步任务有效），None=使用默认值（增量），False=全量同步

    Returns:
        操作结果
    """
    # 检查管理员权限
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="仅管理员可以手动触发任务")

    try:
        # 为特定任务传递参数
        kwargs = {}
        if force and job_id in ["tushare_quotes_sync", "akshare_quotes_sync"]:
            kwargs["force"] = True
        
        # 🔥 历史数据同步任务支持 incremental 参数
        if incremental is not None and job_id in ["tushare_historical_sync", "akshare_historical_sync"]:
            kwargs["incremental"] = incremental

        success = await service.trigger_job(job_id, kwargs=kwargs, force=force)
        if success:
            message = f"任务 {job_id} 已触发执行"
            if force:
                message += "（强制模式）"
            if incremental is not None and job_id in ["tushare_historical_sync", "akshare_historical_sync"]:
                sync_mode = "增量同步" if incremental else "全量同步"
                message += f"（{sync_mode}）"
            return ok(message=message)
        else:
            raise HTTPException(status_code=400, detail=f"触发任务 {job_id} 失败")
    except HTTPException as e:
        # 🔥 如果是409 Conflict（任务正在运行），直接返回给前端
        if e.status_code == 409:
            raise
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


@router.get("/executions")
async def get_job_executions(
    user: dict = Depends(get_current_user),
    service: SchedulerService = Depends(get_scheduler_service),
    job_id: Optional[str] = Query(None, description="任务ID过滤"),
    status: Optional[str] = Query(None, description="状态过滤（success/failed/missed/running）"),
    is_manual: Optional[bool] = Query(None, description="是否手动触发（true=手动，false=自动，None=全部）"),
    limit: int = Query(50, ge=1, le=200, description="返回数量限制"),
    offset: int = Query(0, ge=0, description="偏移量")
):
    """
    获取任务执行历史

    Args:
        job_id: 任务ID过滤（可选）
        status: 状态过滤（可选）
        is_manual: 是否手动触发（可选）
        limit: 返回数量限制
        offset: 偏移量

    Returns:
        执行历史列表
    """
    try:
        executions = await service.get_job_executions(
            job_id=job_id,
            status=status,
            is_manual=is_manual,
            limit=limit,
            offset=offset
        )
        total = await service.count_job_executions(job_id=job_id, status=status, is_manual=is_manual)
        return ok(data={
            "items": executions,
            "total": total,
            "limit": limit,
            "offset": offset
        }, message=f"获取到 {len(executions)} 条执行记录")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取执行历史失败: {str(e)}")


@router.get("/jobs/{job_id}/executions")
async def get_single_job_executions(
    job_id: str,
    user: dict = Depends(get_current_user),
    service: SchedulerService = Depends(get_scheduler_service),
    status: Optional[str] = Query(None, description="状态过滤（success/failed/missed/running）"),
    is_manual: Optional[bool] = Query(None, description="是否手动触发（true=手动，false=自动，None=全部）"),
    limit: int = Query(50, ge=1, le=200, description="返回数量限制"),
    offset: int = Query(0, ge=0, description="偏移量")
):
    """
    获取指定任务的执行历史

    Args:
        job_id: 任务ID
        status: 状态过滤（可选）
        is_manual: 是否手动触发（可选）
        limit: 返回数量限制
        offset: 偏移量

    Returns:
        执行历史列表
    """
    try:
        executions = await service.get_job_executions(
            job_id=job_id,
            status=status,
            is_manual=is_manual,
            limit=limit,
            offset=offset
        )
        total = await service.count_job_executions(job_id=job_id, status=status, is_manual=is_manual)
        return ok(data={
            "items": executions,
            "total": total,
            "limit": limit,
            "offset": offset
        }, message=f"获取到 {len(executions)} 条执行记录")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取执行历史失败: {str(e)}")


@router.get("/jobs/{job_id}/execution-stats")
async def get_job_execution_stats(
    job_id: str,
    user: dict = Depends(get_current_user),
    service: SchedulerService = Depends(get_scheduler_service)
):
    """
    获取任务执行统计信息

    Args:
        job_id: 任务ID

    Returns:
        统计信息
    """
    try:
        stats = await service.get_job_execution_stats(job_id)
        return ok(data=stats, message="获取统计信息成功")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取统计信息失败: {str(e)}")


@router.get("/suspended-executions")
async def get_suspended_executions(
    user: dict = Depends(get_current_user),
    service: SchedulerService = Depends(get_scheduler_service)
):
    """
    获取所有挂起的任务执行记录（服务重启导致中断的任务）
    
    Returns:
        挂起的任务执行记录列表
    """
    try:
        db = service._get_db()
        
        # 查找所有挂起的任务
        suspended_executions = await db.scheduler_executions.find({
            "status": "suspended"
        }).sort("timestamp", -1).to_list(length=100)
        
        # 转换为前端需要的格式
        executions = []
        for exec_record in suspended_executions:
            executions.append({
                "execution_id": str(exec_record["_id"]),
                "job_id": exec_record.get("job_id"),
                "job_name": exec_record.get("job_name", exec_record.get("job_id")),
                "status": exec_record.get("status"),
                "progress": exec_record.get("progress", 0),
                "message": exec_record.get("progress_message"),
                "current_item": exec_record.get("current_item"),
                "total_items": exec_record.get("total_items"),
                "processed_items": exec_record.get("processed_items"),
                "started_at": exec_record.get("timestamp").isoformat() if exec_record.get("timestamp") else None,
                "updated_at": exec_record.get("updated_at").isoformat() if exec_record.get("updated_at") else None,
                "error_message": exec_record.get("error_message")
            })
        
        return ok(data=executions, message=f"获取到 {len(executions)} 个挂起的任务")
    except Exception as e:
        logger.error(f"❌ 获取挂起任务失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取挂起任务失败: {str(e)}")


@router.post("/executions/{execution_id}/cancel-suspended")
async def cancel_suspended_execution(
    execution_id: str,
    user: dict = Depends(get_current_user),
    service: SchedulerService = Depends(get_scheduler_service)
):
    """
    取消挂起的任务执行记录（用户选择重新开始时使用）
    
    注意：这个端点专门用于取消 suspended 状态的任务
    对于 running 状态的任务，请使用 /executions/{execution_id}/cancel 端点
    
    Args:
        execution_id: 执行记录ID（MongoDB _id）
    
    Returns:
        操作结果
    """
    try:
        db = service._get_db()
        from bson import ObjectId
        
        # 查找挂起的执行记录
        exec_record = await db.scheduler_executions.find_one({"_id": ObjectId(execution_id)})
        if not exec_record:
            raise HTTPException(status_code=404, detail="执行记录不存在")
        
        if exec_record.get("status") != "suspended":
            raise HTTPException(status_code=400, detail=f"任务状态不是挂起状态，当前状态: {exec_record.get('status')}")
        
        job_id = exec_record.get("job_id")
        
        # 🔥 将该任务的所有挂起记录标记为cancelled
        cancelled_result = await db.scheduler_executions.update_many(
            {"job_id": job_id, "status": "suspended"},
            {
                "$set": {
                    "status": "cancelled",
                    "error_message": "用户选择重新开始，已取消挂起任务",
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        logger.info(f"✅ 已取消 {cancelled_result.modified_count} 个挂起任务（用户选择重新开始）")
        return ok(message=f"已取消 {cancelled_result.modified_count} 个挂起任务")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 取消挂起任务失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"取消挂起任务失败: {str(e)}")


@router.post("/executions/{execution_id}/resume")
async def resume_suspended_execution(
    execution_id: str,
    user: dict = Depends(get_current_user),
    service: SchedulerService = Depends(get_scheduler_service)
):
    """
    恢复挂起的任务执行（从上次中断的位置继续执行）
    
    Args:
        execution_id: 执行记录ID（MongoDB _id）
    
    Returns:
        操作结果
    """
    # 检查管理员权限
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="仅管理员可以恢复挂起的任务")
    
    try:
        db = service._get_db()
        from bson import ObjectId
        
        # 查找挂起的执行记录
        exec_record = await db.scheduler_executions.find_one({"_id": ObjectId(execution_id)})
        if not exec_record:
            raise HTTPException(status_code=404, detail="执行记录不存在")
        
        if exec_record.get("status") != "suspended":
            raise HTTPException(status_code=400, detail=f"任务状态不是挂起状态，当前状态: {exec_record.get('status')}")
        
        job_id = exec_record.get("job_id")
        if not job_id:
            raise HTTPException(status_code=400, detail="执行记录中没有任务ID")
        
        # 🔥 查找该任务的所有挂起记录（按timestamp倒序排序）
        all_suspended = await db.scheduler_executions.find({
            "job_id": job_id,
            "status": "suspended"
        }).sort("timestamp", -1).to_list(length=100)
        
        if not all_suspended:
            raise HTTPException(status_code=404, detail="未找到挂起的执行记录")
        
        # 🔥 确保当前要恢复的记录是最新的（第一个）
        latest_suspended_id = str(all_suspended[0]["_id"])
        if latest_suspended_id != execution_id:
            logger.warning(f"⚠️ 用户尝试恢复的不是最新的挂起记录: 请求={execution_id}, 最新={latest_suspended_id}")
            # 使用最新的记录继续执行
            execution_id = latest_suspended_id
            exec_record = all_suspended[0]
        
        # 🔥 详细日志：记录挂起记录的进度信息
        logger.info(f"📊 任务 {job_id} 共有 {len(all_suspended)} 个挂起记录，将恢复最新的记录 {execution_id}")
        logger.info(f"📋 挂起记录详情:")
        logger.info(f"   - execution_id: {execution_id}")
        logger.info(f"   - progress: {exec_record.get('progress', 0)}%")
        logger.info(f"   - processed_items: {exec_record.get('processed_items')}")
        logger.info(f"   - total_items: {exec_record.get('total_items')}")
        logger.info(f"   - current_item: {exec_record.get('current_item')}")
        logger.info(f"   - job_kwargs: {exec_record.get('job_kwargs', {})}")
        
        # 🔥 将除了最新记录外的所有挂起记录标记为cancelled（避免数据污染）
        if len(all_suspended) > 1:
            other_suspended_ids = [ObjectId(str(e["_id"])) for e in all_suspended[1:]]  # 除了第一个之外的所有记录
            cancelled_result = await db.scheduler_executions.update_many(
                {"_id": {"$in": other_suspended_ids}},
                {
                    "$set": {
                        "status": "cancelled",
                        "error_message": "已由更新的挂起记录恢复执行，为避免数据污染已取消",
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            logger.info(f"✅ 已取消 {cancelled_result.modified_count} 个旧的挂起记录，避免数据污染")
        
        # 🔥 从执行记录中读取任务的kwargs（包括incremental参数）
        resume_kwargs = exec_record.get("job_kwargs", {})
        if resume_kwargs:
            logger.info(f"📋 恢复任务 {job_id}，使用保存的参数: {resume_kwargs}")
        else:
            logger.warning(f"⚠️ 执行记录中没有保存的kwargs，使用默认参数")
        
        # 🔥 保存进度信息到kwargs中，供任务函数使用
        processed_items = exec_record.get("processed_items")
        if processed_items is not None:
            resume_kwargs["_resume_from_index"] = processed_items  # 标记从哪个位置继续
            logger.info(f"🔄 将从第 {processed_items} 个位置继续执行（已处理 {processed_items}/{exec_record.get('total_items', '?')}）")
        else:
            logger.warning(f"⚠️ 执行记录中没有 processed_items，将从0开始执行")
        
        # 🔥 先更新执行记录状态为running，并保存execution_id到kwargs中
        # 这样trigger_job可以识别这是恢复操作，复用这个执行记录而不是创建新的
        resume_kwargs["_resume_execution_id"] = execution_id  # 标记这是恢复操作
        
        # 🔥 先更新执行记录状态为running（在触发任务之前更新，确保前端查询时状态已更新）
        # 这样前端调用loadTasks()时，不会再查询到suspended状态的记录
        # 🔥 同时清除取消标记，因为用户主动恢复任务，表示要继续执行
        # 🔥 清除当前执行记录和所有相关执行记录（包括子任务）的取消标记
        update_result = await db.scheduler_executions.update_one(
            {"_id": ObjectId(execution_id)},
            {
                "$set": {
                    "status": "running",
                    "cancel_requested": False,  # 🔥 清除取消标记，用户主动恢复任务
                    "updated_at": datetime.utcnow(),
                    "resumed_at": datetime.utcnow()  # 记录恢复时间
                }
            }
        )
        
        # 🔥 同时清除所有相关执行记录（包括子任务）的取消标记
        # 例如：如果恢复 tushare_financial_sync，也要清除 tushare_financial_sync_tushare 等的取消标记
        related_update_result = await db.scheduler_executions.update_many(
            {
                "job_id": {"$regex": f"^{job_id}(_|$)"},  # 匹配job_id或以其开头的job_id
                "status": {"$in": ["running", "suspended"]}
            },
            {
                "$set": {
                    "cancel_requested": False,  # 🔥 清除所有相关执行记录的取消标记
                    "updated_at": datetime.utcnow()
                }
            }
        )
        if related_update_result.modified_count > 0:
            logger.info(f"✅ 同时清除了 {related_update_result.modified_count} 个相关执行记录的取消标记 "
                      f"(job_id匹配: ^{job_id}(_|$))")
        logger.info(f"✅ 挂起任务 {execution_id} 状态已更新为running，准备恢复执行 (matched={update_result.matched_count}, modified={update_result.modified_count})")
        
        # 🔥 验证更新是否成功
        if update_result.matched_count == 0:
            logger.error(f"❌ 执行记录 {execution_id} 不存在，无法恢复")
            raise HTTPException(status_code=404, detail="执行记录不存在")
        
        # 🔥 再次确认状态已更新
        verify_record = await db.scheduler_executions.find_one({"_id": ObjectId(execution_id)})
        if verify_record and verify_record.get("status") != "running":
            logger.error(f"❌ 执行记录 {execution_id} 状态更新失败，当前状态: {verify_record.get('status')}")
            raise HTTPException(status_code=500, detail=f"状态更新失败，当前状态: {verify_record.get('status')}")
        logger.info(f"✅ 已验证执行记录 {execution_id} 状态已成功更新为running")
        
        # 触发任务继续执行（手动触发，传递保存的参数和execution_id，任务会复用这个执行记录）
        success = await service.trigger_job(job_id, kwargs=resume_kwargs)
        
        if success:
            # 🔥 确保状态仍然是running（trigger_job内部可能会更新状态）
            final_update_result = await db.scheduler_executions.update_one(
                {"_id": ObjectId(execution_id)},
                {
                    "$set": {
                        "status": "running",
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            logger.info(f"✅ 恢复成功后再次确认状态: execution_id={execution_id}, matched={final_update_result.matched_count}, modified={final_update_result.modified_count}")
            
            # 🔥 最终验证：确保状态确实是running
            final_verify = await db.scheduler_executions.find_one({"_id": ObjectId(execution_id)})
            if final_verify:
                final_status = final_verify.get("status")
                logger.info(f"📊 最终状态验证: execution_id={execution_id}, status={final_status}")
                if final_status != "running":
                    logger.warning(f"⚠️ 执行记录 {execution_id} 最终状态不是running，而是: {final_status}")
            else:
                logger.error(f"❌ 执行记录 {execution_id} 在最终验证时不存在")
            
            return ok(message=f"任务 {job_id} 已恢复执行，将从上次进度位置继续")
        else:
            # 如果触发失败，恢复状态为suspended
            await db.scheduler_executions.update_one(
                {"_id": ObjectId(execution_id)},
                {
                    "$set": {
                        "status": "suspended",
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            raise HTTPException(status_code=400, detail=f"触发任务 {job_id} 失败")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 恢复挂起任务失败: {e}")
        raise HTTPException(status_code=500, detail=f"恢复挂起任务失败: {str(e)}")


@router.get("/jobs/{job_id}/progress")
async def get_job_progress(
    job_id: str,
    user: dict = Depends(get_current_user),
    service: SchedulerService = Depends(get_scheduler_service)
):
    """
    获取任务实时进度（从Redis缓存读取，如果Redis不可用则从MongoDB读取）

    Args:
        job_id: 任务ID

    Returns:
        任务进度信息，包括进度百分比、当前项、总项数等
    """
    try:
        import json
        from app.core.redis_client import RedisKeys
        
        # 🔥 尝试从Redis读取实时进度，如果Redis不可用则回退到MongoDB
        try:
            from app.core.database import get_redis_client  # 使用系统统一的Redis客户端
            redis_client = get_redis_client()
            
            # 🔥 先检查MongoDB中是否有新的执行记录（手动触发，且时间戳很新，30秒内）
            # 如果有新的执行记录，优先返回新的执行记录，而不是旧的Redis缓存
            recent_execution = await service.get_latest_execution(job_id)
            if recent_execution:
                execution_time = recent_execution.get("timestamp") or recent_execution.get("scheduled_time")
                if execution_time:
                    # 🔥 检查执行记录是否很新（30秒内）且是手动触发
                    # 需要处理 execution_time 可能是 datetime 对象或字符串的情况
                    try:
                        execution_time_dt = None
                        if isinstance(execution_time, datetime):
                            execution_time_dt = execution_time
                        elif isinstance(execution_time, str):
                            # 如果是字符串，尝试解析为 datetime
                            try:
                                # 尝试使用 datetime.fromisoformat（Python 3.7+）
                                execution_time_dt = datetime.fromisoformat(execution_time.replace('Z', '+00:00'))
                            except (ValueError, AttributeError):
                                # 如果失败，尝试使用 strptime
                                try:
                                    execution_time_dt = datetime.strptime(execution_time, '%Y-%m-%d %H:%M:%S')
                                except ValueError:
                                    # 如果都失败，尝试使用 dateutil（如果可用）
                                    try:
                                        from dateutil import parser
                                        execution_time_dt = parser.parse(execution_time)
                                    except (ImportError, ValueError):
                                        logger.debug(f"⚠️ 无法解析 execution_time 字符串: {execution_time}")
                        
                        if execution_time_dt:
                            # 计算时间差
                            now = datetime.now(execution_time_dt.tzinfo) if execution_time_dt.tzinfo else datetime.now()
                            if execution_time_dt.tzinfo:
                                time_diff = now - execution_time_dt
                            else:
                                time_diff = datetime.now() - execution_time_dt.replace(tzinfo=None)
                            
                            is_recent = time_diff.total_seconds() < 30
                            is_manual = recent_execution.get("is_manual", False)
                            
                            # 🔥 如果是新的手动触发任务（30秒内），优先返回MongoDB中的新记录，而不是旧的Redis缓存
                            if is_recent and is_manual:
                                logger.info(f"🔍 [进度查询] 检测到新的手动触发任务（30秒内），优先返回MongoDB记录: job_id={job_id}, execution_id={recent_execution.get('_id')}")
                                # 跳过Redis缓存，直接返回MongoDB中的新记录
                                started_at = execution_time_dt
                                progress_data = {
                                    "job_id": job_id,
                                    "execution_id": str(recent_execution.get("_id")),
                                    "progress": recent_execution.get("progress", 0),
                                    "status": recent_execution.get("status", "running"),
                                    "message": recent_execution.get("progress_message"),
                                    "current_item": recent_execution.get("current_item"),
                                    "total_items": recent_execution.get("total_items"),
                                    "processed_items": recent_execution.get("processed_items"),
                                    "started_at": started_at.isoformat() if started_at and hasattr(started_at, 'isoformat') else (str(started_at) if started_at else None),
                                    "updated_at": recent_execution.get("updated_at", execution_time)
                                }
                                logger.info(f"🔍 [进度查询] 从MongoDB读取到新任务进度: job_id={job_id}, execution_id={progress_data.get('execution_id')}, progress={progress_data.get('progress')}, status={progress_data.get('status')}")
                                return ok(data=progress_data, message="获取进度成功（新任务，来自数据库）")
                    except Exception as time_check_error:
                        # 时间检查失败，继续使用Redis缓存
                        logger.debug(f"⚠️ 检查执行记录时间失败（继续使用Redis缓存）: {time_check_error}")
            
            # 优先从Redis读取实时进度
            progress_key = RedisKeys.SCHEDULER_JOB_PROGRESS.format(job_id=job_id)
            progress_data_str = await redis_client.get(progress_key)
            
            if progress_data_str:
                progress_data = json.loads(progress_data_str)
                # 🔥 如果Redis中没有execution_id，尝试从MongoDB获取最新的执行记录
                if not progress_data.get("execution_id"):
                    execution = await service.get_latest_execution(job_id)
                    if execution and execution.get("_id"):
                        progress_data["execution_id"] = str(execution.get("_id"))
                logger.info(f"🔍 [进度查询] 从Redis读取到进度: job_id={job_id}, execution_id={progress_data.get('execution_id')}, progress={progress_data.get('progress')}, status={progress_data.get('status')}")
                return ok(data=progress_data, message="获取实时进度成功")
            else:
                logger.info(f"🔍 [进度查询] Redis中没有找到进度数据: job_id={job_id}, key={progress_key}")
        except RuntimeError as redis_error:
            # Redis未初始化，记录日志但继续从MongoDB读取
            logger.debug(f"⚠️ Redis不可用，从MongoDB读取进度: {redis_error}")
        except Exception as redis_error:
            # 其他Redis错误，记录日志但继续从MongoDB读取
            logger.warning(f"⚠️ Redis读取失败，从MongoDB读取进度: {redis_error}")
        
        # 如果Redis中没有或Redis不可用，从MongoDB读取最新的执行记录
        execution = await service.get_latest_execution(job_id)
        if execution:
            started_at = execution.get("timestamp") or execution.get("scheduled_time")
            progress_data = {
                "job_id": job_id,
                "execution_id": str(execution.get("_id")),  # 🔥 添加执行记录ID，用于终止操作
                "progress": execution.get("progress", 0),
                "status": execution.get("status", "unknown"),
                "message": execution.get("progress_message"),
                "current_item": execution.get("current_item"),
                "total_items": execution.get("total_items"),
                "processed_items": execution.get("processed_items"),
                "started_at": started_at.isoformat() if started_at and hasattr(started_at, 'isoformat') else (str(started_at) if started_at else None),
                "updated_at": execution.get("updated_at", execution.get("timestamp"))
            }
            logger.info(f"🔍 [进度查询] 从MongoDB读取到进度: job_id={job_id}, execution_id={progress_data.get('execution_id')}, progress={progress_data.get('progress')}, status={progress_data.get('status')}")
            return ok(data=progress_data, message="获取进度成功（来自数据库）")
        else:
            logger.warning(f"🔍 [进度查询] MongoDB中也没有找到执行记录: job_id={job_id}")
        
        return ok(data={
            "job_id": job_id,
            "progress": 0,
            "status": "unknown",
            "message": "暂无进度信息"
        }, message="暂无进度信息")
        
    except Exception as e:
        logger.error(f"❌ 获取任务进度失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取任务进度失败: {str(e)}")


@router.post("/executions/{execution_id}/cancel")
async def cancel_execution(
    execution_id: str,
    user: dict = Depends(get_current_user),
    service: SchedulerService = Depends(get_scheduler_service)
):
    """
    取消/终止任务执行（统一入口，根据任务状态自动处理）

    对于正在执行的任务（running），设置取消标记（cancel_requested=True）；
    对于挂起的任务（suspended），标记为cancelled状态；
    对于失败的任务（failed），标记为cancelled状态（用户明确终止失败的任务）；
    对于其他已完成状态的任务（success），标记为cancelled状态（用户明确终止已完成的任务）

    Args:
        execution_id: 执行记录ID（MongoDB _id）

    Returns:
        操作结果
    """
    try:
        db = service._get_db()
        from bson import ObjectId
        
        # 查找执行记录
        exec_record = await db.scheduler_executions.find_one({"_id": ObjectId(execution_id)})
        if not exec_record:
            raise HTTPException(status_code=404, detail="执行记录不存在")
        
        status = exec_record.get("status")
        job_id = exec_record.get("job_id")
        
        # 🔥 根据任务状态执行不同的操作
        if status == "running":
            # 正在执行的任务：设置取消标记
            logger.info(f"🛑 用户请求终止任务: execution_id={execution_id}, job_id={job_id}, status={status}")
            success = await service.cancel_job_execution(execution_id)
            if success:
                logger.info(f"✅ 终止任务成功: execution_id={execution_id}")
                return ok(message="已设置取消标记，任务将在下次检查时停止")
            else:
                logger.error(f"❌ 终止任务失败: execution_id={execution_id}")
                raise HTTPException(status_code=400, detail="取消任务失败")
        elif status == "suspended":
            # 挂起的任务：标记为cancelled
            cancelled_result = await db.scheduler_executions.update_many(
                {"job_id": job_id, "status": "suspended"},
                {
                    "$set": {
                        "status": "cancelled",
                        "error_message": "用户选择重新开始，已取消挂起任务",
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            logger.info(f"✅ 已取消 {cancelled_result.modified_count} 个挂起任务")
            return ok(message=f"已取消 {cancelled_result.modified_count} 个挂起任务")
        elif status == "failed":
            # 🔥 失败的任务：标记为cancelled（用户明确终止失败的任务）
            cancelled_result = await db.scheduler_executions.update_one(
                {"_id": ObjectId(execution_id)},
                {
                    "$set": {
                        "status": "cancelled",
                        "error_message": "用户已终止此失败的任务",
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            logger.info(f"✅ 已终止失败的任务: execution_id={execution_id}, job_id={job_id}")
            return ok(message="已终止失败的任务")
        elif status == "success":
            # 🔥 已完成的任务：标记为cancelled（用户明确终止已完成的任务）
            cancelled_result = await db.scheduler_executions.update_one(
                {"_id": ObjectId(execution_id)},
                {
                    "$set": {
                        "status": "cancelled",
                        "error_message": "用户已终止此已完成的任务",
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            logger.info(f"✅ 已终止已完成的任务: execution_id={execution_id}, job_id={job_id}")
            return ok(message="已终止已完成的任务")
        elif status == "cancelled":
            # 已经是取消状态，直接返回成功
            logger.info(f"ℹ️ 任务已经是取消状态: execution_id={execution_id}, job_id={job_id}")
            return ok(message="任务已经是取消状态")
        else:
            # 🔥 其他未知状态：也允许终止，标记为cancelled
            cancelled_result = await db.scheduler_executions.update_one(
                {"_id": ObjectId(execution_id)},
                {
                    "$set": {
                        "status": "cancelled",
                        "error_message": f"用户已终止此任务（原状态: {status}）",
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            logger.info(f"✅ 已终止任务（原状态: {status}）: execution_id={execution_id}, job_id={job_id}")
            return ok(message=f"已终止任务（原状态: {status}）")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 取消任务失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"取消任务失败: {str(e)}")


@router.post("/executions/{execution_id}/mark-failed")
async def mark_execution_failed(
    execution_id: str,
    reason: str = Query("用户手动标记为失败", description="失败原因"),
    user: dict = Depends(get_current_user),
    service: SchedulerService = Depends(get_scheduler_service)
):
    """
    将执行记录标记为失败状态

    用于处理已经退出但数据库中仍为running的任务

    Args:
        execution_id: 执行记录ID（MongoDB _id）
        reason: 失败原因

    Returns:
        操作结果
    """
    try:
        success = await service.mark_execution_as_failed(execution_id, reason)
        if success:
            return ok(message="已标记为失败状态")
        else:
            raise HTTPException(status_code=400, detail="标记失败")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"标记失败: {str(e)}")


@router.delete("/executions/{execution_id}")
async def delete_execution(
    execution_id: str,
    user: dict = Depends(get_current_user),
    service: SchedulerService = Depends(get_scheduler_service)
):
    """
    删除执行记录

    Args:
        execution_id: 执行记录ID（MongoDB _id）

    Returns:
        操作结果
    """
    try:
        success = await service.delete_execution(execution_id)
        if success:
            return ok(message="执行记录已删除")
        else:
            raise HTTPException(status_code=400, detail="删除失败")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除执行记录失败: {str(e)}")


@router.post("/executions/{execution_id}/retry-failed")
async def retry_failed_symbols(
    execution_id: str,
    user: dict = Depends(get_current_user),
    service: SchedulerService = Depends(get_scheduler_service),
    start_date: Optional[str] = Query(None, description="开始日期（可选，默认使用原任务的日期）"),
    end_date: Optional[str] = Query(None, description="结束日期（可选，默认使用原任务的日期）"),
    period: Optional[str] = Query("daily", description="数据周期（daily/weekly/monthly），默认daily")
):
    """
    重试失败的股票（只重试可重试的错误，跳过无数据的错误）
    
    适用于历史数据同步任务（Tushare/AKShare）
    
    Args:
        execution_id: 执行记录ID（MongoDB _id）
        start_date: 开始日期（可选，默认使用原任务的日期）
        end_date: 结束日期（可选，默认使用原任务的日期）
        period: 数据周期（daily/weekly/monthly），默认daily
        
    Returns:
        重试结果统计
    """
    # 检查管理员权限
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="仅管理员可以重试失败的股票")
    
    try:
        from bson import ObjectId
        from app.worker.tushare_sync_service import get_tushare_sync_service
        
        db = service._get_db()
        
        # 查找执行记录
        exec_record = await db.scheduler_executions.find_one({"_id": ObjectId(execution_id)})
        if not exec_record:
            raise HTTPException(status_code=404, detail="执行记录不存在")
        
        job_id = exec_record.get("job_id")
        if not job_id:
            raise HTTPException(status_code=400, detail="执行记录中没有任务ID")
        
        # 🔥 检查任务类型，只支持历史数据同步任务
        supported_jobs = ["tushare_historical_sync", "akshare_historical_sync", "baostock_historical_sync"]
        if job_id not in supported_jobs:
            raise HTTPException(
                status_code=400, 
                detail=f"该任务类型不支持重试失败项，仅支持: {', '.join(supported_jobs)}"
            )
        
        # 🔥 从执行记录中获取错误列表
        # 错误信息可能存储在多个地方：
        # 1. execution 记录的 errors 字段（如果任务完成时保存了）
        # 2. 从 stats 中提取（如果任务有统计信息）
        
        errors = exec_record.get("errors", [])
        
        # 如果没有直接存储 errors，尝试从其他字段提取
        if not errors:
            # 尝试从 progress_message 或其他字段中提取错误信息
            # 这里可能需要根据实际的数据结构来调整
            logger.warning(f"⚠️ 执行记录 {execution_id} 中没有找到错误列表，无法重试")
            raise HTTPException(
                status_code=400, 
                detail="执行记录中没有错误信息，无法重试。请确保任务已完成并记录了错误信息。"
            )
        
        # 🔥 根据任务类型获取对应的同步服务实例
        if job_id == "tushare_historical_sync":
            from app.worker.tushare_sync_service import get_tushare_sync_service
            sync_service = await get_tushare_sync_service()
        elif job_id == "akshare_historical_sync":
            from app.worker.akshare_sync_service import get_akshare_sync_service
            sync_service = await get_akshare_sync_service()
        elif job_id == "baostock_historical_sync":
            from app.worker.baostock_sync_service import get_baostock_sync_service
            sync_service = await get_baostock_sync_service()
        else:
            raise HTTPException(status_code=400, detail=f"不支持的任务类型: {job_id}")
        
        # 🔥 如果没有提供日期，尝试从执行记录中获取
        if not start_date:
            # 可以从 job_kwargs 或其他字段中获取
            job_kwargs = exec_record.get("job_kwargs", {})
            start_date = job_kwargs.get("start_date")
        
        if not end_date:
            job_kwargs = exec_record.get("job_kwargs", {})
            end_date = job_kwargs.get("end_date")
        
        # 🔥 调用重试方法（不同服务可能有不同的接口）
        if job_id == "baostock_historical_sync":
            # BaoStock 使用 days 参数，需要计算天数
            if start_date and end_date:
                from datetime import datetime as dt
                start_dt = dt.strptime(start_date, '%Y-%m-%d')
                end_dt = dt.strptime(end_date, '%Y-%m-%d')
                days = (end_dt - start_dt).days
            else:
                days = 30  # 默认30天
            
            retry_result = await sync_service.retry_failed_symbols(
                errors=errors,
                days=days,
                period=period,
                job_id=f"{job_id}_retry_{execution_id}"
            )
        else:
            # Tushare 和 AKShare 使用 start_date/end_date
            retry_result = await sync_service.retry_failed_symbols(
                errors=errors,
                start_date=start_date,
                end_date=end_date,
                period=period,
                job_id=f"{job_id}_retry_{execution_id}"  # 使用新的job_id，避免冲突
            )
        
        return ok(
            data=retry_result,
            message=f"重试完成: 成功 {retry_result.get('success_count', 0)}/{retry_result.get('total_retried', 0)}, "
                   f"失败 {retry_result.get('error_count', 0)}, "
                   f"无数据 {retry_result.get('no_data_count', 0)}（已跳过）"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 重试失败股票失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"重试失败股票失败: {str(e)}")
