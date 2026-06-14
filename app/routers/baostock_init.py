#!/usr/bin/env python3
"""
BaoStock初始化API路由
提供BaoStock数据初始化的RESTful API接口
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from app.worker.baostock_init_service import BaoStockInitService
from app.worker.baostock_sync_service import BaoStockSyncService
from app.core.singleton import ThreadSafeState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/baostock-init", tags=["BaoStock初始化"])

# 线程安全的全局状态管理
_initialization_status = ThreadSafeState({
    "is_running": False,
    "current_task": None,
    "stats": None,
    "start_time": None,
    "last_update": None
})


class InitializationRequest(BaseModel):
    """初始化请求模型"""
    historical_days: int = Field(default=365, ge=1, le=3650, description="历史数据天数")
    force: bool = Field(default=False, description="是否强制重新初始化")


class InitializationResponse(BaseModel):
    """初始化响应模型"""
    success: bool
    message: str
    task_id: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


@router.get("/status", response_model=Dict[str, Any])
async def get_database_status():
    """获取数据库状态"""
    try:
        service = BaoStockInitService()
        status = await service.check_database_status()
        
        return {
            "success": True,
            "data": status,
            "message": "数据库状态获取成功"
        }
        
    except Exception as e:
        logger.error(f"获取数据库状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取数据库状态失败: {e}")


@router.get("/connection-test", response_model=Dict[str, Any])
async def test_baostock_connection():
    """测试BaoStock连接"""
    try:
        service = BaoStockSyncService()
        connected = await service.provider.test_connection()
        
        return {
            "success": connected,
            "data": {
                "connected": connected,
                "test_time": datetime.now().isoformat()
            },
            "message": "BaoStock连接正常" if connected else "BaoStock连接失败"
        }
        
    except Exception as e:
        logger.error(f"BaoStock连接测试失败: {e}")
        raise HTTPException(status_code=500, detail=f"连接测试失败: {e}")


@router.post("/start-full", response_model=InitializationResponse)
async def start_full_initialization(
    request: InitializationRequest,
    background_tasks: BackgroundTasks
):
    """启动完整初始化"""
    if _initialization_status["is_running"]:
        raise HTTPException(
            status_code=409, 
            detail="初始化任务正在运行中，请等待完成后再试"
        )
    
    try:
        # 生成任务ID
        task_id = f"baostock_full_init_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # 更新状态
        _initialization_status.update({
            "is_running": True,
            "current_task": "full_initialization",
            "stats": None,
            "start_time": datetime.now(),
            "last_update": datetime.now()
        })
        
        # 启动后台任务
        background_tasks.add_task(
            _run_full_initialization_task,
            request.historical_days,
            request.force,
            task_id
        )
        
        return InitializationResponse(
            success=True,
            message="完整初始化任务已启动",
            task_id=task_id,
            data={
                "historical_days": request.historical_days,
                "force": request.force,
                "estimated_duration": "30-60分钟"
            }
        )
        
    except Exception as e:
        _initialization_status["is_running"] = False
        logger.error(f"启动完整初始化失败: {e}")
        raise HTTPException(status_code=500, detail=f"启动初始化失败: {e}")


@router.post("/start-basic", response_model=InitializationResponse)
async def start_basic_initialization(background_tasks: BackgroundTasks):
    """启动基础初始化"""
    if _initialization_status["is_running"]:
        raise HTTPException(
            status_code=409,
            detail="初始化任务正在运行中，请等待完成后再试"
        )
    
    try:
        # 生成任务ID
        task_id = f"baostock_basic_init_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # 更新状态
        _initialization_status.update({
            "is_running": True,
            "current_task": "basic_initialization",
            "stats": None,
            "start_time": datetime.now(),
            "last_update": datetime.now()
        })
        
        # 启动后台任务
        background_tasks.add_task(_run_basic_initialization_task, task_id)
        
        return InitializationResponse(
            success=True,
            message="基础初始化任务已启动",
            task_id=task_id,
            data={
                "estimated_duration": "10-20分钟"
            }
        )
        
    except Exception as e:
        _initialization_status["is_running"] = False
        logger.error(f"启动基础初始化失败: {e}")
        raise HTTPException(status_code=500, detail=f"启动初始化失败: {e}")


@router.get("/initialization-status", response_model=Dict[str, Any])
async def get_initialization_status():
    """获取初始化状态"""
    try:
        status = _initialization_status.snapshot()
        
        # 计算运行时间
        if status["start_time"]:
            if status["is_running"]:
                duration = (datetime.now() - status["start_time"]).total_seconds()
            else:
                duration = (status["last_update"] - status["start_time"]).total_seconds() if status["last_update"] else 0
            status["duration"] = duration
        
        # 格式化统计信息
        if status["stats"]:
            stats = status["stats"]
            status["progress"] = {
                "completed_steps": stats.completed_steps,
                "total_steps": stats.total_steps,
                "current_step": stats.current_step,
                "progress_percent": (stats.completed_steps / stats.total_steps) * 100
            }
            status["data_summary"] = {
                "basic_info_count": stats.basic_info_count,
                "quotes_count": stats.quotes_count,
                "historical_records": stats.historical_records,
                "financial_records": stats.financial_records,
                "error_count": len(stats.errors)
            }
        
        return {
            "success": True,
            "data": status,
            "message": "状态获取成功"
        }
        
    except Exception as e:
        logger.error(f"获取初始化状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取状态失败: {e}")


@router.post("/stop", response_model=Dict[str, Any])
async def stop_initialization():
    """停止初始化任务"""
    if not _initialization_status["is_running"]:
        return {
            "success": True,
            "message": "没有正在运行的初始化任务",
            "data": {"was_running": False}
        }
    
    try:
        # 更新状态
        _initialization_status.update({
            "is_running": False,
            "current_task": None,
            "last_update": datetime.now()
        })
        
        return {
            "success": True,
            "message": "初始化任务已停止",
            "data": {"was_running": True}
        }
        
    except Exception as e:
        logger.error(f"停止初始化任务失败: {e}")
        raise HTTPException(status_code=500, detail=f"停止任务失败: {e}")


async def _run_full_initialization_task(historical_days: int, force: bool, task_id: str):
    """运行完整初始化任务"""
    try:
        logger.info(f"🚀 开始BaoStock完整初始化任务: {task_id}")
        
        service = BaoStockInitService()
        stats = await service.full_initialization(
            historical_days=historical_days,
            force=force
        )
        
        # 更新状态
        _initialization_status.update({
            "is_running": False,
            "stats": stats,
            "last_update": datetime.now()
        })
        
        if stats.completed_steps == stats.total_steps:
            logger.info(f"✅ BaoStock完整初始化任务完成: {task_id}")
        else:
            logger.warning(f"⚠️ BaoStock完整初始化任务部分完成: {task_id}")
        
    except Exception as e:
        logger.error(f"❌ BaoStock完整初始化任务失败: {task_id}, 错误: {e}")
        _initialization_status.update({
            "is_running": False,
            "last_update": datetime.now()
        })


async def _run_basic_initialization_task(task_id: str):
    """运行基础初始化任务"""
    try:
        logger.info(f"🚀 开始BaoStock基础初始化任务: {task_id}")
        
        service = BaoStockInitService()
        stats = await service.basic_initialization()
        
        # 更新状态
        _initialization_status.update({
            "is_running": False,
            "stats": stats,
            "last_update": datetime.now()
        })
        
        if stats.completed_steps == stats.total_steps:
            logger.info(f"✅ BaoStock基础初始化任务完成: {task_id}")
        else:
            logger.warning(f"⚠️ BaoStock基础初始化任务部分完成: {task_id}")
        
    except Exception as e:
        logger.error(f"❌ BaoStock基础初始化任务失败: {task_id}, 错误: {e}")
        _initialization_status.update({
            "is_running": False,
            "last_update": datetime.now()
        })


@router.get("/service-status", response_model=Dict[str, Any])
async def get_service_status():
    """获取BaoStock服务状态"""
    try:
        service = BaoStockSyncService()
        status = await service.check_service_status()
        
        return {
            "success": True,
            "data": status,
            "message": "服务状态获取成功"
        }
        
    except Exception as e:
        logger.error(f"获取服务状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取服务状态失败: {e}")
