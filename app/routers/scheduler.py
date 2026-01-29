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

        success = await service.trigger_job(job_id, kwargs=kwargs)
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


@router.post("/executions/{execution_id}/cancel")
async def cancel_suspended_execution(
    execution_id: str,
    user: dict = Depends(get_current_user),
    service: SchedulerService = Depends(get_scheduler_service)
):
    """
    取消挂起的任务执行记录（用户选择重新开始时使用）
    
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
        update_result = await db.scheduler_executions.update_one(
            {"_id": ObjectId(execution_id)},
            {
                "$set": {
                    "status": "running",
                    "updated_at": datetime.utcnow(),
                    "resumed_at": datetime.utcnow()  # 记录恢复时间
                }
            }
        )
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
            
            # 优先从Redis读取实时进度
            progress_key = RedisKeys.SCHEDULER_JOB_PROGRESS.format(job_id=job_id)
            progress_data_str = await redis_client.get(progress_key)
            
            if progress_data_str:
                progress_data = json.loads(progress_data_str)
                return ok(data=progress_data, message="获取实时进度成功")
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
                "progress": execution.get("progress", 0),
                "status": execution.get("status", "unknown"),
                "message": execution.get("progress_message"),
                "current_item": execution.get("current_item"),
                "total_items": execution.get("total_items"),
                "processed_items": execution.get("processed_items"),
                "started_at": started_at.isoformat() if started_at and hasattr(started_at, 'isoformat') else (str(started_at) if started_at else None),
                "updated_at": execution.get("updated_at", execution.get("timestamp"))
            }
            return ok(data=progress_data, message="获取进度成功（来自数据库）")
        
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
    取消/终止任务执行

    对于正在执行的任务，设置取消标记；
    对于已经退出但数据库中仍为running的任务，直接标记为failed

    Args:
        execution_id: 执行记录ID（MongoDB _id）

    Returns:
        操作结果
    """
    try:
        success = await service.cancel_job_execution(execution_id)
        if success:
            return ok(message="已设置取消标记，任务将在下次检查时停止")
        else:
            raise HTTPException(status_code=400, detail="取消任务失败")
    except HTTPException:
        raise
    except Exception as e:
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
