"""
统一任务中心 API

提供统一的任务查询接口，支持所有类型的分析任务
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
import logging

from app.models.analysis import AnalysisTaskType, AnalysisStatus
from app.models.user import PyObjectId
from app.services.task_analysis_service import get_task_analysis_service
from app.routers.auth_db import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2/tasks", tags=["unified-task-center"])


# ==================== 响应模型 ====================

class TaskListItem(BaseModel):
    """任务列表项"""
    task_id: str
    task_type: str
    status: str
    progress: int
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    execution_time: float = 0.0
    error_message: Optional[str] = None
    
    # 任务参数（用于显示）
    symbol: Optional[str] = None
    code: Optional[str] = None
    market: Optional[str] = None


class TaskStatistics(BaseModel):
    """任务统计"""
    total: int
    pending: int
    processing: int
    completed: int
    failed: int
    cancelled: int


# ==================== API 端点 ====================

@router.get("/list", summary="获取任务列表")
async def get_task_list(
    task_type: Optional[AnalysisTaskType] = Query(None, description="任务类型过滤"),
    status: Optional[AnalysisStatus] = Query(None, description="状态过滤"),
    limit: Optional[int] = Query(None, description="返回数量（可选，不设置则返回所有）"),
    skip: int = Query(0, ge=0, description="跳过数量"),
    user: dict = Depends(get_current_user)
):
    """获取用户的任务列表

    支持按任务类型和状态过滤

    注意：如果不指定 limit，将返回所有记录，由前端处理分页
    """
    try:
        logger.info(f"🎯 [统一任务中心] 获取任务列表请求")
        logger.info(f"👤 用户信息: {user}")
        logger.info(f"📊 查询参数: task_type={task_type}, status={status}, limit={limit}, skip={skip}")

        user_id = PyObjectId(user["id"])
        logger.info(f"🔄 转换后的user_id: {user_id} (类型: {type(user_id)})")

        service = get_task_analysis_service()

        # 如果没有指定 limit，则返回所有记录
        actual_limit = limit if limit is not None else 999999

        tasks = await service.list_user_tasks(
            user_id=user_id,
            task_type=task_type,
            status=status,
            limit=actual_limit,
            skip=skip
        )
        
        # 转换为列表项格式
        items = []
        for task in tasks:
            # 从任务参数中提取显示信息
            symbol = task.task_params.get("symbol")
            code = task.task_params.get("code")
            market = task.task_params.get("market") or task.task_params.get("market_type")
            
            items.append(TaskListItem(
                task_id=task.task_id,
                task_type=task.task_type,
                status=task.status,
                progress=task.progress,
                created_at=task.created_at.isoformat(),
                started_at=task.started_at.isoformat() if task.started_at else None,
                completed_at=task.completed_at.isoformat() if task.completed_at else None,
                execution_time=task.execution_time,
                error_message=task.error_message,
                symbol=symbol,
                code=code,
                market=market
            ))
        
        return {
            "success": True,
            "data": {
                "tasks": items,
                "total": len(items),
                "limit": limit,
                "skip": skip
            },
            "message": "ok"
        }
        
    except Exception as e:
        logger.error(f"获取任务列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取任务列表失败: {str(e)}")


@router.get("/statistics", summary="获取任务统计")
async def get_task_statistics(
    user: dict = Depends(get_current_user)
):
    """获取用户的任务统计信息"""
    try:
        logger.info(f"🎯 [统一任务中心] 获取任务统计请求")
        logger.info(f"👤 用户信息: {user}")

        user_id = PyObjectId(user["id"])
        logger.info(f"🔄 转换后的user_id: {user_id} (类型: {type(user_id)})")

        service = get_task_analysis_service()

        stats = await service.get_task_statistics(user_id)
        logger.info(f"📊 统计结果: {stats}")
        
        return {
            "success": True,
            "data": TaskStatistics(**stats),
            "message": "ok"
        }
        
    except Exception as e:
        logger.error(f"获取任务统计失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取任务统计失败: {str(e)}")


@router.get("/{task_id}", summary="获取任务详情")
async def get_task_detail(
    task_id: str,
    user: dict = Depends(get_current_user)
):
    """获取任务详情"""
    try:
        user_id = PyObjectId(user["id"])
        service = get_task_analysis_service()

        task = await service.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")

        # 验证权限
        if task.user_id != user_id:
            raise HTTPException(status_code=403, detail="无权访问此任务")
        
        return {
            "success": True,
            "data": task.model_dump(),
            "message": "ok"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取任务详情失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取任务详情失败: {str(e)}")


@router.delete("/{task_id}", summary="取消任务")
async def cancel_task(
    task_id: str,
    user: dict = Depends(get_current_user)
):
    """取消任务"""
    try:
        user_id = PyObjectId(user["id"])
        service = get_task_analysis_service()

        # 验证任务存在和权限
        task = await service.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")

        if task.user_id != user_id:
            raise HTTPException(status_code=403, detail="无权访问此任务")

        # 取消任务
        success = await service.cancel_task(task_id)

        if success:
            return {
                "success": True,
                "message": "任务已取消"
            }
        else:
            return {
                "success": False,
                "message": "任务无法取消（可能已完成或失败）"
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"取消任务失败: {e}")
        raise HTTPException(status_code=500, detail=f"取消任务失败: {str(e)}")


@router.post("/{task_id}/resume", summary="恢复挂起的任务")
async def resume_task(
    task_id: str,
    user: dict = Depends(get_current_user)
):
    """恢复挂起的任务，将任务重新加入队列"""
    try:
        user_id = PyObjectId(user["id"])
        service = get_task_analysis_service()

        # 验证任务存在和权限
        task = await service.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")

        if task.user_id != user_id:
            raise HTTPException(status_code=403, detail="无权访问此任务")

        # 检查任务状态
        if task.status != AnalysisStatus.SUSPENDED:
            raise HTTPException(status_code=400, detail=f"只能恢复挂起状态的任务，当前状态: {task.status}")

        # 恢复任务
        success = await service.resume_task(task_id)

        if success:
            return {
                "success": True,
                "message": "任务已恢复，正在重新排队..."
            }
        else:
            return {
                "success": False,
                "message": "恢复任务失败"
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"恢复任务失败: {e}")
        raise HTTPException(status_code=500, detail=f"恢复任务失败: {str(e)}")

