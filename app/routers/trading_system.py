"""
个人交易系统 API 路由
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Header
from pydantic import BaseModel

from app.services.trading_system_service import get_trading_system_service, TradingSystemService
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
    """创建交易系统"""
    try:
        user_id = current_user["id"]
        system = service.create_system(user_id, system_data)
        return ok(data={"system": system.dict()}, message="交易系统创建成功")
    except Exception as e:
        logger.error(f"创建交易系统失败: {e}")
        return error(message=f"创建交易系统失败: {str(e)}")


@router.get("", response_model=ApiResponse)
async def list_trading_systems(
    is_active: Optional[bool] = Query(None, description="是否只获取激活的系统"),
    current_user: dict = Depends(get_current_user),
    service: TradingSystemService = Depends(get_trading_system_service)
):
    """获取交易系统列表"""
    try:
        user_id = current_user["id"]
        logger.info(f"开始获取交易系统列表: user_id={user_id}, is_active={is_active}")

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
        logger.error(f"获取交易系统列表失败: {e}", exc_info=True)
        return error(message=f"获取交易系统列表失败: {str(e)}")


@router.get("/active", response_model=ApiResponse)
async def get_active_trading_system(
    current_user: dict = Depends(get_current_user),
    service: TradingSystemService = Depends(get_trading_system_service)
):
    """获取当前激活的交易系统"""
    try:
        user_id = current_user["id"]
        system = service.get_active_system(user_id)
        if not system:
            return ok(data={"system": None}, message="未找到激活的交易系统")
        return ok(data={"system": system.dict()})
    except Exception as e:
        logger.error(f"获取激活交易系统失败: {e}")
        return error(message=f"获取激活交易系统失败: {str(e)}")


@router.get("/{system_id}", response_model=ApiResponse)
async def get_trading_system(
    system_id: str,
    current_user: dict = Depends(get_current_user),
    service: TradingSystemService = Depends(get_trading_system_service)
):
    """获取交易系统详情"""
    try:
        user_id = current_user["id"]
        system = service.get_system(system_id, user_id)
        if not system:
            return error(message="交易系统不存在")
        return ok(data={"system": system.dict()})
    except Exception as e:
        logger.error(f"获取交易系统详情失败: {e}")
        return error(message=f"获取交易系统详情失败: {str(e)}")


@router.put("/{system_id}", response_model=ApiResponse)
async def update_trading_system(
    system_id: str,
    update_data: TradingSystemUpdate,
    current_user: dict = Depends(get_current_user),
    service: TradingSystemService = Depends(get_trading_system_service)
):
    """更新交易系统"""
    try:
        user_id = current_user["id"]
        system = service.update_system(system_id, user_id, update_data)
        if not system:
            return error(message="交易系统不存在")
        return ok(data={"system": system.dict()}, message="交易系统更新成功")
    except Exception as e:
        logger.error(f"更新交易系统失败: {e}")
        return error(message=f"更新交易系统失败: {str(e)}")


@router.delete("/{system_id}", response_model=ApiResponse)
async def delete_trading_system(
    system_id: str,
    current_user: dict = Depends(get_current_user),
    service: TradingSystemService = Depends(get_trading_system_service)
):
    """删除交易系统"""
    try:
        user_id = current_user["id"]
        success = service.delete_system(system_id, user_id)
        if not success:
            return error(message="交易系统不存在或删除失败")
        return ok(message="交易系统删除成功")
    except Exception as e:
        logger.error(f"删除交易系统失败: {e}")
        return error(message=f"删除交易系统失败: {str(e)}")


@router.post("/{system_id}/activate", response_model=ApiResponse)
async def activate_trading_system(
    system_id: str,
    current_user: dict = Depends(get_current_user),
    service: TradingSystemService = Depends(get_trading_system_service)
):
    """激活交易系统"""
    try:
        user_id = current_user["id"]
        system = service.activate_system(system_id, user_id)
        if not system:
            return error(message="交易系统不存在")
        return ok(data={"system": system.dict()}, message="交易系统激活成功")
    except Exception as e:
        logger.error(f"激活交易系统失败: {e}")
        return error(message=f"激活交易系统失败: {str(e)}")

