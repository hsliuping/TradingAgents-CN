"""
使用统计 API 路由
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException

from app.routers.auth_db import get_current_user
from app.models.config import UsageRecord, UsageStatistics
from app.services.usage_statistics_service import usage_statistics_service

logger = logging.getLogger("app.routers.usage_statistics")

router = APIRouter(prefix="/api/usage", tags=["使用统计"], redirect_slashes=False)


# ============================================================================
# /api/usage/stats - KPI 友好的简洁统计端点（v3.0 京东云仪表板用）
# 返回 {used_tokens, quota_tokens, percentage, period_days, reset_at}
# quota_tokens 来源:
#   1. 京东云模式: 环境变量 JDYUN_TOKEN_QUOTA（可选，默认 0 表示不限额）
#   2. 标准版: License 高级功能配额（如未配置则为 0）
# 当 quota_tokens = 0 时不显示配额百分比，仅展示累计用量
# ============================================================================

def _resolve_token_quota() -> int:
    """解析当前用户的 Token 配额上限（0 表示不限额）"""
    # 京东云模式：从环境变量读取
    if os.getenv("JDYUN_MODE", "").strip().lower() in ("true", "1", "yes"):
        return int(os.getenv("JDYUN_TOKEN_QUOTA", "0"))
    # 标准版：默认不限额，可由 License 模块扩展
    return 0


@router.get("/stats", summary="获取 KPI 用量统计")
async def get_usage_stats(
    days: int = Query(7, ge=1, le=365, description="统计天数（默认近 7 天）"),
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    获取 KPI 友好的简洁用量统计

    用于仪表板"API 用量"卡片，返回已用 Token / 配额 / 百分比。
    与 /api/usage/statistics 区别：
    - statistics 返回多维详细统计（by_provider/by_model/by_date）
    - stats 返回单值 KPI（used_tokens/quota_tokens/percentage）

    quota_tokens 来源：
    - 京东云模式：环境变量 JDYUN_TOKEN_QUOTA（默认 0 表示不限额）
    - 标准版：默认不限额，可由 License 模块扩展

    当 quota_tokens = 0 时，percentage = 0，前端仅展示累计用量不显示进度条。
    """
    try:
        # 复用现有 service 拿详细统计
        stats = await usage_statistics_service.get_usage_statistics(days=days)

        used_tokens = stats.total_input_tokens + stats.total_output_tokens
        quota_tokens = _resolve_token_quota()
        percentage = round((used_tokens / quota_tokens) * 100, 2) if quota_tokens > 0 else 0.0

        # 配额重置时间：当前周期结束时间（days 天后）
        reset_at = (datetime.utcnow() + timedelta(days=days)).isoformat() + "Z"

        return {
            "success": True,
            "message": "获取用量统计成功",
            "data": {
                "used_tokens": used_tokens,
                "quota_tokens": quota_tokens,
                "percentage": percentage,
                "period_days": days,
                "reset_at": reset_at,
                "input_tokens": stats.total_input_tokens,
                "output_tokens": stats.total_output_tokens,
                "total_requests": stats.total_requests,
                "currency_breakdown": stats.cost_by_currency,
            }
        }
    except Exception as e:
        logger.error(f"获取 KPI 用量统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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

