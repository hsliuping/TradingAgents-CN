"""
工作流 API 接口

提供给外部服务调用的工作流执行接口
支持同步和异步两种执行模式
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel, Field

from app.routers.auth_db import get_current_user
from app.core.response import ok, fail
from app.services.task_analysis_service import get_task_analysis_service
from app.models.analysis import AnalysisTaskType, PyObjectId
from bson import ObjectId

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/workflow", tags=["Workflow API"])


# ========== 请求模型 ==========

class WorkflowExecuteRequest(BaseModel):
    """工作流执行请求"""
    
    # 必填参数
    workflow_id: str = Field(..., description="工作流ID（数据库中的工作流ID或系统预置工作流ID）")
    
    # 股票分析参数
    ticker: Optional[str] = Field(None, description="股票代码（如：000001, AAPL）")
    stock_code: Optional[str] = Field(None, description="股票代码（别名，与ticker二选一）")
    analysis_date: Optional[str] = Field(None, description="分析日期（格式：YYYY-MM-DD，默认今天）")
    market_type: Optional[str] = Field(None, description="市场类型（cn/us/hk，默认自动识别）")
    
    # 分析配置
    research_depth: Optional[str] = Field("快速", description="研究深度（快速/标准/深度）")
    preference_type: Optional[str] = Field("neutral", description="风险偏好（aggressive/neutral/conservative）")
    
    # 模型配置
    quick_analysis_model: Optional[str] = Field(None, description="快速分析模型")
    deep_analysis_model: Optional[str] = Field(None, description="深度分析模型")
    
    # 工作流参数
    lookback_days: Optional[int] = Field(30, description="回溯天数")
    max_debate_rounds: Optional[int] = Field(2, description="最大辩论轮数")
    
    # 自定义参数（传递给工作流的额外参数）
    custom_params: Optional[Dict[str, Any]] = Field(default_factory=dict, description="自定义参数")
    
    # 执行模式
    async_mode: bool = Field(True, description="是否异步执行（True=返回task_id，False=等待结果）")
    timeout: Optional[int] = Field(1800, description="同步模式下的超时时间（秒），默认30分钟")
    
    # 回调配置
    callback_url: Optional[str] = Field(None, description="异步模式下的回调URL（任务完成后POST结果）")
    
    class Config:
        json_schema_extra = {
            "example": {
                "workflow_id": "stock_analysis_workflow",
                "ticker": "000001",
                "analysis_date": "2026-02-19",
                "research_depth": "标准",
                "preference_type": "neutral",
                "async_mode": True
            }
        }


class WorkflowExecuteResponse(BaseModel):
    """工作流执行响应"""
    
    # 异步模式返回
    task_id: Optional[str] = Field(None, description="任务ID（异步模式）")
    status: Optional[str] = Field(None, description="任务状态")
    message: Optional[str] = Field(None, description="提示信息")
    
    # 同步模式返回
    success: Optional[bool] = Field(None, description="执行是否成功（同步模式）")
    result: Optional[Dict[str, Any]] = Field(None, description="执行结果（同步模式）")
    execution_time: Optional[float] = Field(None, description="执行时间（秒）")
    
    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "pending",
                "message": "任务已提交，正在后台执行"
            }
        }


class TaskStatusResponse(BaseModel):
    """任务状态响应"""
    
    task_id: str = Field(..., description="任务ID")
    status: str = Field(..., description="任务状态（pending/running/completed/failed）")
    progress: int = Field(0, description="执行进度（0-100）")
    message: Optional[str] = Field(None, description="当前状态描述")
    
    # 任务信息
    created_at: Optional[datetime] = Field(None, description="创建时间")
    started_at: Optional[datetime] = Field(None, description="开始时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    execution_time: Optional[float] = Field(None, description="执行时间（秒）")
    
    # 结果（仅完成时）
    result: Optional[Dict[str, Any]] = Field(None, description="执行结果")
    error: Optional[str] = Field(None, description="错误信息（失败时）")
    
    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "completed",
                "progress": 100,
                "message": "任务执行完成",
                "execution_time": 125.5,
                "result": {
                    "summary": "分析完成",
                    "recommendation": "建议关注"
                }
            }
        }


# ========== API 端点 ==========

@router.post("/execute", response_model=WorkflowExecuteResponse)
async def execute_workflow(
    request: WorkflowExecuteRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user)  # 支持 JWT Token 和 Session 认证
):
    """
    执行工作流
    
    支持两种模式：
    1. **异步模式**（默认）：立即返回 task_id，通过 /task/{task_id}/status 查询状态
    2. **同步模式**：等待执行完成后返回结果（适合超时时间短的工作流）
    
    认证方式：
    - Header: `Authorization: Bearer <token>`
    - Header: `X-API-Key: <api_key>`
    """
    try:
        user_id = user.get("user_id") or user.get("_id")
        logger.info(f"🎯 [工作流API] 收到执行请求: workflow_id={request.workflow_id}, user={user_id}")

        # 🆕 查询工作流类型，判断 ticker 是否必填
        from app.core.database import get_mongo_db
        from app.models.analysis import AnalysisTaskType
        db = get_mongo_db()
        wf_doc = await db.workflows.find_one(
            {"_id": request.workflow_id},
            {"workflow_type": 1, "input_config": 1}
        )
        workflow_type = wf_doc.get("workflow_type", "stock_analysis") if wf_doc else "stock_analysis"
        input_config = wf_doc.get("input_config") if wf_doc else None

        # 获取股票代码（仅 stock_analysis/etf_analysis 必填）
        ticker = request.ticker or request.stock_code
        TICKER_REQUIRED_TYPES = {"stock_analysis", "etf_analysis"}
        if workflow_type in TICKER_REQUIRED_TYPES and not ticker:
            raise HTTPException(status_code=400, detail=f"工作流类型 {workflow_type} 必须提供 ticker 或 stock_code 参数")

        # 🆕 根据 workflow_type 映射 task_type
        WORKFLOW_TYPE_TO_TASK_TYPE = {
            "stock_analysis": AnalysisTaskType.STOCK_ANALYSIS,
            "etf_analysis": AnalysisTaskType.ETF_ANALYSIS,
            "position_analysis": AnalysisTaskType.POSITION_ANALYSIS,
            "trade_review": AnalysisTaskType.TRADE_REVIEW,
            "general": AnalysisTaskType.STOCK_ANALYSIS,
        }
        task_type = WORKFLOW_TYPE_TO_TASK_TYPE.get(workflow_type, AnalysisTaskType.STOCK_ANALYSIS)

        # 构建任务参数
        task_params = {}
        if ticker:
            task_params["symbol"] = ticker
            task_params["stock_code"] = ticker
        task_params["analysis_date"] = request.analysis_date or datetime.now().strftime("%Y-%m-%d")
        task_params["market_type"] = request.market_type
        task_params["research_depth"] = request.research_depth
        task_params["quick_analysis_model"] = request.quick_analysis_model
        task_params["deep_analysis_model"] = request.deep_analysis_model
        task_params["lookback_days"] = request.lookback_days
        task_params["max_debate_rounds"] = request.max_debate_rounds

        # 🆕 根据 input_config.fields 的 default 值补充缺失参数
        if input_config and isinstance(input_config, dict):
            fields = input_config.get("fields", [])
            for field in fields:
                fname = field.get("name")
                if fname and fname not in task_params and fname not in ("ticker", "symbol", "stock_code"):
                    default_val = field.get("default")
                    if default_val is not None:
                        task_params[fname] = default_val

        # 合并自定义参数
        task_params.update(request.custom_params)

        # 为 general 类型打标记
        if workflow_type == "general":
            task_params["task_category"] = "general"

        # 获取任务服务
        task_service = get_task_analysis_service()

        if request.async_mode:
            # 异步模式：创建任务并返回 task_id
            task = await task_service.create_task(
                user_id=PyObjectId(user_id),
                task_type=task_type,
                task_params=task_params,
                engine_type="workflow",
                preference_type=request.preference_type,
                workflow_id=request.workflow_id
            )

            # 异步执行任务
            asyncio.create_task(task_service.execute_task(task))

            logger.info(f"✅ [工作流API] 异步任务已创建: task_id={task.task_id}")

            return WorkflowExecuteResponse(
                task_id=task.task_id,
                status=task.status,
                message="任务已提交，正在后台执行"
            )
        else:
            # 同步模式：等待执行完成
            task = await task_service.create_task(
                user_id=PyObjectId(user_id),
                task_type=task_type,
                task_params=task_params,
                engine_type="workflow",
                preference_type=request.preference_type,
                workflow_id=request.workflow_id
            )

            logger.info(f"🔄 [工作流API] 同步执行任务: task_id={task.task_id}")

            # 同步执行任务（等待完成）
            try:
                result = await asyncio.wait_for(
                    task_service.execute_task(task),
                    timeout=request.timeout
                )

                # 重新获取任务状态
                task = await task_service.get_task(task.task_id)

                logger.info(f"✅ [工作流API] 同步任务完成: task_id={task.task_id}")

                return WorkflowExecuteResponse(
                    success=True,
                    result=task.result,
                    execution_time=task.execution_time,
                    message="任务执行完成"
                )
            except asyncio.TimeoutError:
                logger.warning(f"⏰ [工作流API] 同步任务超时: task_id={task.task_id}")
                return WorkflowExecuteResponse(
                    success=False,
                    task_id=task.task_id,
                    message=f"任务执行超时（超过{request.timeout}秒），请使用异步模式或通过task_id查询结果"
                )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [工作流API] 执行失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/task/{task_id}/status", response_model=TaskStatusResponse)
async def get_task_status(
    task_id: str,
    user: dict = Depends(get_current_user)
):
    """
    查询任务状态

    用于异步模式下查询任务执行状态和进度
    """
    try:
        user_id = user.get("user_id") or user.get("_id")
        logger.info(f"🔍 [工作流API] 查询任务状态: task_id={task_id}, user={user_id}")

        task_service = get_task_analysis_service()
        task = await task_service.get_task(task_id)

        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")

        # 验证任务所有权
        if str(task.user_id) != str(user_id):
            raise HTTPException(status_code=403, detail="无权访问此任务")

        return TaskStatusResponse(
            task_id=task.task_id,
            status=task.status,
            progress=task.progress,
            message=task.status_message,
            created_at=task.created_at,
            started_at=task.started_at,
            completed_at=task.completed_at,
            execution_time=task.execution_time,
            result=task.result if task.status == "completed" else None,
            error=task.error_message if task.status == "failed" else None
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [工作流API] 查询任务状态失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/task/{task_id}/result")
async def get_task_result(
    task_id: str,
    user: dict = Depends(get_current_user)
):
    """
    获取任务结果

    返回已完成任务的详细结果
    """
    try:
        user_id = user.get("user_id") or user.get("_id")
        logger.info(f"📊 [工作流API] 获取任务结果: task_id={task_id}, user={user_id}")

        task_service = get_task_analysis_service()
        task = await task_service.get_task(task_id)

        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")

        # 验证任务所有权
        if str(task.user_id) != str(user_id):
            raise HTTPException(status_code=403, detail="无权访问此任务")

        if task.status != "completed":
            raise HTTPException(
                status_code=400,
                detail=f"任务尚未完成，当前状态: {task.status}"
            )

        return ok({
            "task_id": task.task_id,
            "status": task.status,
            "result": task.result,
            "execution_time": task.execution_time,
            "completed_at": task.completed_at
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [工作流API] 获取任务结果失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/task/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    user: dict = Depends(get_current_user)
):
    """
    取消任务

    取消正在执行或等待中的任务
    """
    try:
        user_id = user.get("user_id") or user.get("_id")
        logger.info(f"🛑 [工作流API] 取消任务: task_id={task_id}, user={user_id}")

        task_service = get_task_analysis_service()
        task = await task_service.get_task(task_id)

        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")

        # 验证任务所有权
        if str(task.user_id) != str(user_id):
            raise HTTPException(status_code=403, detail="无权访问此任务")

        if task.status in ["completed", "failed", "cancelled"]:
            raise HTTPException(
                status_code=400,
                detail=f"任务已结束，无法取消，当前状态: {task.status}"
            )

        # 更新任务状态为已取消
        await task_service.cancel_task(task_id)

        return ok({
            "task_id": task_id,
            "status": "cancelled",
            "message": "任务已取消"
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [工作流API] 取消任务失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

