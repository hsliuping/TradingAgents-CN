"""
Tushare数据初始化API路由
提供Web界面的数据初始化功能
"""
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel, Field

from app.routers.auth_db import get_current_user
from app.core.database import get_mongo_db
from app.worker.tushare_init_service import get_tushare_init_service
from app.core.response import ok

router = APIRouter(prefix="/api/tushare-init", tags=["Tushare初始化"])


class InitializationRequest(BaseModel):
    """初始化请求模型"""
    historical_days: int = Field(default=365, ge=1, le=3650, description="历史数据天数")
    skip_if_exists: bool = Field(default=True, description="如果数据已存在是否跳过")
    force_update: bool = Field(default=False, description="强制更新已有数据")


class DatabaseStatusResponse(BaseModel):
    """数据库状态响应模型"""
    basic_info_count: int = Field(description="基础信息数量")
    quotes_count: int = Field(description="行情数据数量")
    extended_coverage: float = Field(description="扩展字段覆盖率")
    latest_basic_update: Optional[datetime] = Field(description="基础信息最新更新时间")
    latest_quotes_update: Optional[datetime] = Field(description="行情数据最新更新时间")
    needs_initialization: bool = Field(description="是否需要初始化")


class InitializationStatusResponse(BaseModel):
    """初始化状态响应模型"""
    is_running: bool = Field(description="是否正在运行")
    current_step: Optional[str] = Field(description="当前步骤")
    progress: Optional[str] = Field(description="进度")
    started_at: Optional[datetime] = Field(description="开始时间")
    estimated_completion: Optional[datetime] = Field(description="预计完成时间")


# 全局初始化状态跟踪
_initialization_status = {
    "is_running": False,
    "current_step": None,
    "progress": None,
    "started_at": None,
    "task": None
}


@router.get("/status", response_model=dict)
async def get_database_status(
    current_user: dict = Depends(get_current_user)
):
    """
    获取数据库状态
    检查当前数据库中的数据情况，判断是否需要初始化
    """
    try:
        db = get_mongo_db()
        
        # 检查各集合状态
        basic_count = await db.stock_basic_info.count_documents({})
        quotes_count = await db.market_quotes.count_documents({})
        
        # 检查扩展字段覆盖率
        extended_count = 0
        extended_coverage = 0.0
        if basic_count > 0:
            extended_count = await db.stock_basic_info.count_documents({
                "full_symbol": {"$exists": True},
                "market_info": {"$exists": True}
            })
            extended_coverage = extended_count / basic_count
        
        # 检查最新更新时间
        latest_basic = await db.stock_basic_info.find_one(
            {}, sort=[("updated_at", -1)]
        )
        latest_quotes = await db.market_quotes.find_one(
            {}, sort=[("updated_at", -1)]
        )
        
        # 判断是否需要初始化
        needs_initialization = (
            basic_count == 0 or 
            extended_coverage < 0.5
        )
        
        status = DatabaseStatusResponse(
            basic_info_count=basic_count,
            quotes_count=quotes_count,
            extended_coverage=extended_coverage,
            latest_basic_update=latest_basic.get("updated_at") if latest_basic else None,
            latest_quotes_update=latest_quotes.get("updated_at") if latest_quotes else None,
            needs_initialization=needs_initialization
        )
        
        return ok(data=status,
            message="数据库状态获取成功"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取数据库状态失败: {str(e)}")


@router.get("/initialization-status", response_model=dict)
async def get_initialization_status(
    current_user: dict = Depends(get_current_user)
):
    """
    获取初始化状态
    检查当前是否有初始化任务在运行
    """
    try:
        status = InitializationStatusResponse(
            is_running=_initialization_status["is_running"],
            current_step=_initialization_status["current_step"],
            progress=_initialization_status["progress"],
            started_at=_initialization_status["started_at"],
            estimated_completion=None  # TODO: 可以根据历史数据估算
        )
        
        return ok(data=status,
            message="初始化状态获取成功"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取初始化状态失败: {str(e)}")


@router.post("/start-basic", response_model=dict)
async def start_basic_initialization(
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """
    启动基础信息初始化
    仅同步股票基础信息，适合快速初始化
    """
    if _initialization_status["is_running"]:
        raise HTTPException(status_code=400, detail="初始化任务已在运行中")
    
    try:
        # 启动后台任务
        background_tasks.add_task(_run_basic_initialization)
        
        return ok(data={"message": "基础信息初始化已启动"},
            message="基础信息初始化任务已在后台启动"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动基础信息初始化失败: {str(e)}")


@router.post("/start-full", response_model=dict)
async def start_full_initialization(
    request: InitializationRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """
    启动完整数据初始化
    包括基础信息、历史数据、财务数据、行情数据的完整同步
    """
    if _initialization_status["is_running"]:
        raise HTTPException(status_code=400, detail="初始化任务已在运行中")
    
    try:
        # 启动后台任务
        background_tasks.add_task(
            _run_full_initialization,
            request.historical_days,
            not request.skip_if_exists or request.force_update
        )
        
        return ok(data={
                "message": "完整数据初始化已启动",
                "historical_days": request.historical_days,
                "force_update": not request.skip_if_exists or request.force_update
            },
            message="完整数据初始化任务已在后台启动"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动完整数据初始化失败: {str(e)}")


@router.post("/stop", response_model=dict)
async def stop_initialization(
    current_user: dict = Depends(get_current_user)
):
    """
    停止初始化任务
    尝试取消正在运行的初始化任务
    """
    if not _initialization_status["is_running"]:
        raise HTTPException(status_code=400, detail="没有正在运行的初始化任务")
    
    try:
        # 尝试取消任务
        if _initialization_status["task"]:
            _initialization_status["task"].cancel()
        
        # 重置状态
        _initialization_status.update({
            "is_running": False,
            "current_step": None,
            "progress": None,
            "started_at": None,
            "task": None
        })
        
        return ok(data={"message": "初始化任务已停止"},
            message="初始化任务停止成功"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"停止初始化任务失败: {str(e)}")


async def _run_basic_initialization():
    """运行基础信息初始化（后台任务）"""
    _initialization_status.update({
        "is_running": True,
        "current_step": "基础信息初始化",
        "progress": "0/1",
        "started_at": datetime.utcnow()
    })
    
    try:
        service = await get_tushare_init_service()
        result = await service.sync_service.sync_stock_basic_info(force_update=True)
        
        _initialization_status.update({
            "is_running": False,
            "current_step": "完成",
            "progress": "1/1"
        })
        
    except Exception as e:
        _initialization_status.update({
            "is_running": False,
            "current_step": f"失败: {str(e)}",
            "progress": "错误"
        })


async def _run_full_initialization(historical_days: int, force_update: bool):
    """运行完整数据初始化（后台任务）"""
    _initialization_status.update({
        "is_running": True,
        "current_step": "准备初始化",
        "progress": "0/6",
        "started_at": datetime.utcnow()
    })
    
    try:
        service = await get_tushare_init_service()
        
        # 创建一个任务来跟踪进度
        async def progress_tracker():
            while _initialization_status["is_running"]:
                if hasattr(service, 'stats') and service.stats:
                    _initialization_status.update({
                        "current_step": service.stats.current_step,
                        "progress": f"{service.stats.completed_steps}/{service.stats.total_steps}"
                    })
                await asyncio.sleep(1)
        
        # 启动进度跟踪
        tracker_task = asyncio.create_task(progress_tracker())
        _initialization_status["task"] = tracker_task
        
        # 运行初始化
        result = await service.run_full_initialization(
            historical_days=historical_days,
            skip_if_exists=not force_update
        )
        
        # 停止进度跟踪
        tracker_task.cancel()
        
        _initialization_status.update({
            "is_running": False,
            "current_step": "完成" if result["success"] else "部分完成",
            "progress": result["progress"],
            "task": None
        })
        
    except Exception as e:
        _initialization_status.update({
            "is_running": False,
            "current_step": f"失败: {str(e)}",
            "progress": "错误",
            "task": None
        })
