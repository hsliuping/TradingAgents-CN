"""
个人交易计划 API 路由
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Header
from pydantic import BaseModel

from app.services.trading_system_service import get_trading_system_service, TradingSystemService
from app.services.trading_plan_evaluation_service import get_trading_plan_evaluation_service, TradingPlanEvaluationService
from app.models.trading_system import (
    TradingSystem,
    TradingSystemCreate,
    TradingSystemUpdate
)
from app.routers.auth_db import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/trading-systems", tags=["trading-systems"])


# 统一响应格式
class ApiResponse(BaseModel):
    success: bool = True
    data: dict = {}
    message: str = ""


def ok(data=None, message="操作成功"):
    """成功响应"""
    return ApiResponse(success=True, data=data or {}, message=message)


def error(message="操作失败", data=None):
    """错误响应"""
    return ApiResponse(success=False, data=data or {}, message=message)


@router.post("", response_model=ApiResponse)
async def create_trading_system(
    system_data: TradingSystemCreate,
    current_user: dict = Depends(get_current_user),
    service: TradingSystemService = Depends(get_trading_system_service)
):
    """创建交易计划"""
    try:
        user_id = current_user["id"]
        system = service.create_system(user_id, system_data)
        return ok(data={"system": system.dict()}, message="交易计划创建成功")
    except Exception as e:
        logger.error(f"创建交易计划失败: {e}")
        return error(message=f"创建交易计划失败: {str(e)}")


@router.get("", response_model=ApiResponse)
async def list_trading_systems(
    is_active: Optional[bool] = Query(None, description="是否只获取激活的系统"),
    current_user: dict = Depends(get_current_user),
    service: TradingSystemService = Depends(get_trading_system_service)
):
    """获取交易计划列表"""
    try:
        user_id = current_user["id"]
        logger.info(f"开始获取交易计划列表: user_id={user_id}, is_active={is_active}")

        systems = service.list_systems(user_id, is_active=is_active)
        logger.info(f"服务层返回 {len(systems)} 个系统")

        # 转换为字典
        systems_dict = []
        for idx, s in enumerate(systems):
            logger.info(f"序列化第 {idx+1} 个系统: {s.name}")
            try:
                system_dict = s.dict()
                logger.info(f"系统 {s.name} 序列化后的键: {list(system_dict.keys())}")
                systems_dict.append(system_dict)
            except Exception as e:
                logger.error(f"序列化系统 {s.name} 失败: {e}")
                raise

        logger.info(f"成功序列化所有系统")
        return ok(data={
            "systems": systems_dict,
            "total": len(systems_dict)
        })
    except Exception as e:
        logger.error(f"获取交易计划列表失败: {e}", exc_info=True)
        return error(message=f"获取交易计划列表失败: {str(e)}")


@router.get("/active", response_model=ApiResponse)
async def get_active_trading_system(
    current_user: dict = Depends(get_current_user),
    service: TradingSystemService = Depends(get_trading_system_service)
):
    """获取当前激活的交易计划"""
    try:
        user_id = current_user["id"]
        system = service.get_active_system(user_id)
        if not system:
            return ok(data={"system": None}, message="未找到激活的交易计划")
        return ok(data={"system": system.dict()})
    except Exception as e:
        logger.error(f"获取激活交易计划失败: {e}")
        return error(message=f"获取激活交易计划失败: {str(e)}")


@router.get("/{system_id}", response_model=ApiResponse)
async def get_trading_system(
    system_id: str,
    current_user: dict = Depends(get_current_user),
    service: TradingSystemService = Depends(get_trading_system_service)
):
    """获取交易计划详情"""
    try:
        user_id = current_user["id"]
        system = service.get_system(system_id, user_id)
        if not system:
            return error(message="交易计划不存在")
        return ok(data={"system": system.dict()})
    except Exception as e:
        logger.error(f"获取交易计划详情失败: {e}")
        return error(message=f"获取交易计划详情失败: {str(e)}")


@router.put("/{system_id}", response_model=ApiResponse)
async def update_trading_system(
    system_id: str,
    update_data: TradingSystemUpdate,
    current_user: dict = Depends(get_current_user),
    service: TradingSystemService = Depends(get_trading_system_service)
):
    """更新交易计划"""
    try:
        user_id = current_user["id"]
        system = service.update_system(system_id, user_id, update_data)
        if not system:
            return error(message="交易计划不存在")
        return ok(data={"system": system.dict()}, message="交易计划更新成功")
    except Exception as e:
        logger.error(f"更新交易计划失败: {e}")
        return error(message=f"更新交易计划失败: {str(e)}")


@router.delete("/{system_id}", response_model=ApiResponse)
async def delete_trading_system(
    system_id: str,
    current_user: dict = Depends(get_current_user),
    service: TradingSystemService = Depends(get_trading_system_service)
):
    """删除交易计划"""
    try:
        user_id = current_user["id"]
        success = service.delete_system(system_id, user_id)
        if not success:
            return error(message="交易计划不存在或删除失败")
        return ok(message="交易计划删除成功")
    except Exception as e:
        logger.error(f"删除交易计划失败: {e}")
        return error(message=f"删除交易计划失败: {str(e)}")


@router.post("/{system_id}/activate", response_model=ApiResponse)
async def activate_trading_system(
    system_id: str,
    current_user: dict = Depends(get_current_user),
    service: TradingSystemService = Depends(get_trading_system_service)
):
    """激活交易计划"""
    try:
        user_id = current_user["id"]
        system = service.activate_system(system_id, user_id)
        if not system:
            return error(message="交易计划不存在")
        return ok(data={"system": system.dict()}, message="交易计划激活成功")
    except Exception as e:
        logger.error(f"激活交易计划失败: {e}")
        return error(message=f"激活交易计划失败: {str(e)}")


@router.post("/{system_id}/evaluate", response_model=ApiResponse)
async def evaluate_trading_system(
    system_id: str,
    current_user: dict = Depends(get_current_user),
    service: TradingSystemService = Depends(get_trading_system_service),
    evaluation_service: TradingPlanEvaluationService = Depends(get_trading_plan_evaluation_service)
):
    """AI评估交易计划（已保存的计划）"""
    try:
        user_id = current_user["id"]
        
        # 获取交易计划
        system = service.get_system(system_id, user_id)
        if not system:
            return error(message="交易计划不存在")
        
        # 调用AI评估（传入system_id以保存历史记录）
        evaluation_result = await evaluation_service.evaluate_trading_plan(system, user_id, system_id)
        
        return ok(
            data={"evaluation": evaluation_result},
            message="交易计划评估完成"
        )
    except Exception as e:
        logger.error(f"评估交易计划失败: {e}", exc_info=True)
        return error(message=f"评估交易计划失败: {str(e)}")


@router.get("/{system_id}/evaluations", response_model=ApiResponse)
async def get_evaluation_history(
    system_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    current_user: dict = Depends(get_current_user),
    evaluation_service: TradingPlanEvaluationService = Depends(get_trading_plan_evaluation_service)
):
    """获取交易计划评估历史"""
    try:
        user_id = current_user["id"]
        
        history = await evaluation_service.get_evaluation_history(
            system_id=system_id,
            user_id=user_id,
            page=page,
            page_size=page_size
        )
        
        return ok(
            data=history,
            message="获取评估历史成功"
        )
    except Exception as e:
        logger.error(f"获取评估历史失败: {e}", exc_info=True)
        return error(message=f"获取评估历史失败: {str(e)}")


@router.get("/evaluations/{evaluation_id}", response_model=ApiResponse)
async def get_evaluation_detail(
    evaluation_id: str,
    current_user: dict = Depends(get_current_user),
    evaluation_service: TradingPlanEvaluationService = Depends(get_trading_plan_evaluation_service)
):
    """获取评估详情"""
    try:
        user_id = current_user["id"]
        
        detail = await evaluation_service.get_evaluation_detail(evaluation_id, user_id)
        
        if not detail:
            return error(message="评估记录不存在", code=404)
        
        return ok(
            data={"evaluation": detail},
            message="获取评估详情成功"
        )
    except Exception as e:
        logger.error(f"获取评估详情失败: {e}", exc_info=True)
        return error(message=f"获取评估详情失败: {str(e)}")


@router.post("/evaluate-draft", response_model=ApiResponse)
async def evaluate_trading_plan_draft(
    trading_plan_data: TradingSystemCreate,
    current_user: dict = Depends(get_current_user),
    evaluation_service: TradingPlanEvaluationService = Depends(get_trading_plan_evaluation_service)
):
    """AI评估交易计划草稿（未保存的计划）"""
    try:
        user_id = current_user["id"]
        
        # 将创建请求转换为字典（添加user_id以便评估）
        plan_dict = trading_plan_data.dict()
        plan_dict["user_id"] = user_id
        
        # 调用AI评估
        evaluation_result = await evaluation_service.evaluate_trading_plan_data(plan_dict, user_id)
        
        return ok(
            data={"evaluation": evaluation_result},
            message="交易计划评估完成"
        )
    except Exception as e:
        logger.error(f"评估交易计划草稿失败: {e}", exc_info=True)
        return error(message=f"评估交易计划失败: {str(e)}")

