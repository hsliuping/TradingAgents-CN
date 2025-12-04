"""
使用统计 API 路由
"""

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException

from app.routers.auth_db import get_current_user
from app.models.config import UsageRecord, UsageStatistics
from app.services.usage_statistics_service import usage_statistics_service

logger = logging.getLogger("app.routers.usage_statistics")

router = APIRouter(prefix="/api/usage", tags=["使用统计"])


@router.get("/records", summary="获取使用记录")
async def get_usage_records(
    provider: Optional[str] = Query(None, description="供应商"),
    model_name: Optional[str] = Query(None, description="模型名称"),
    start_date: Optional[str] = Query(None, description="开始日期(ISO格式)"),
    end_date: Optional[str] = Query(None, description="结束日期(ISO格式)"),
    limit: int = Query(100, ge=1, le=1000, description="返回记录数"),
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """获取使用记录"""
    try:
        # 解析日期
        start_dt = datetime.fromisoformat(start_date) if start_date else None
        end_dt = datetime.fromisoformat(end_date) if end_date else None

        # 获取记录
        records = await usage_statistics_service.get_usage_records(
            provider=provider,
            model_name=model_name,
            start_date=start_dt,
            end_date=end_dt,
            limit=limit
        )

        return {
            "success": True,
            "message": "获取使用记录成功",
            "data": {
                "records": [record.model_dump() for record in records],
                "total": len(records)
            }
        }
    except Exception as e:
        logger.error(f"获取使用记录失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics", summary="获取使用统计")
async def get_usage_statistics(
    days: int = Query(7, ge=1, le=365, description="统计天数"),
    provider: Optional[str] = Query(None, description="供应商"),
    model_name: Optional[str] = Query(None, description="模型名称"),
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """获取使用统计"""
    try:
        stats = await usage_statistics_service.get_usage_statistics(
            days=days,
            provider=provider,
            model_name=model_name
        )

        return {
            "success": True,
            "message": "获取使用统计成功",
            "data": stats.model_dump()
        }
    except Exception as e:
        logger.error(f"获取使用统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cost/by-provider", summary="按供应商统计成本")
async def get_cost_by_provider(
    days: int = Query(7, ge=1, le=365, description="统计天数"),
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """按供应商统计成本"""
    try:
        cost_data = await usage_statistics_service.get_cost_by_provider(days=days)

        return {
            "success": True,
            "message": "获取成本统计成功",
            "data": cost_data
        }
    except Exception as e:
        logger.error(f"获取成本统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cost/by-model", summary="按模型统计成本")
async def get_cost_by_model(
    days: int = Query(7, ge=1, le=365, description="统计天数"),
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """按模型统计成本"""
    try:
        cost_data = await usage_statistics_service.get_cost_by_model(days=days)

        return {
            "success": True,
            "message": "获取成本统计成功",
            "data": cost_data
        }
    except Exception as e:
        logger.error(f"获取成本统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cost/daily", summary="每日成本统计")
async def get_daily_cost(
    days: int = Query(7, ge=1, le=365, description="统计天数"),
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """每日成本统计"""
    try:
        cost_data = await usage_statistics_service.get_daily_cost(days=days)

        return {
            "success": True,
            "message": "获取每日成本成功",
            "data": cost_data
        }
    except Exception as e:
        logger.error(f"获取每日成本失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/records/old", summary="删除旧记录")
async def delete_old_records(
    days: int = Query(90, ge=30, le=365, description="保留天数"),
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """删除旧记录"""
    try:
        deleted_count = await usage_statistics_service.delete_old_records(days=days)

        return {
            "success": True,
            "message": f"删除旧记录成功",
            "data": {"deleted_count": deleted_count}
        }
    except Exception as e:
        logger.error(f"删除旧记录失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

