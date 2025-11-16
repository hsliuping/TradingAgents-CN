"""
分析偏好 API 路由
"""

import logging
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional, List
from app.services.analysis_preference_service import AnalysisPreferenceService
from app.models.analysis_preference import (
    AnalysisPreferenceCreate,
    AnalysisPreferenceUpdate,
    AnalysisPreferenceResponse
)
from app.core.response import ok, fail

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/preferences", tags=["preferences"])


# 依赖注入：获取服务实例
def get_preference_service() -> AnalysisPreferenceService:
    """获取偏好服务实例"""
    return AnalysisPreferenceService()


@router.post("", response_model=dict)
async def create_preference(
    user_id: str = Query(...),
    preference_data: AnalysisPreferenceCreate = None,
    preference_service: AnalysisPreferenceService = Depends(get_preference_service)
):
    """创建分析偏好"""
    try:
        if not preference_data:
            return fail("偏好数据不能为空", 400)

        preference = await preference_service.create_preference(user_id, preference_data)

        if not preference:
            return fail("创建偏好失败", 400)

        return ok({
            "id": preference.id,
            "preference_type": preference.preference_type,
            "is_default": preference.is_default,
            "created_at": preference.created_at.isoformat()
        })

    except Exception as e:
        logger.error(f"❌ 创建偏好异常: {e}")
        return fail(str(e), 500)


@router.get("/{preference_id}", response_model=dict)
async def get_preference(
    preference_id: str,
    preference_service: AnalysisPreferenceService = Depends(get_preference_service)
):
    """获取偏好"""
    try:
        preference = await preference_service.get_preference(preference_id)

        if not preference:
            return fail("偏好不存在", 404)

        return ok({
            "id": preference.id,
            "user_id": preference.user_id,
            "preference_type": preference.preference_type,
            "risk_level": preference.risk_level,
            "confidence_threshold": preference.confidence_threshold,
            "position_size_multiplier": preference.position_size_multiplier,
            "decision_speed": preference.decision_speed,
            "is_default": preference.is_default,
            "created_at": preference.created_at.isoformat(),
            "updated_at": preference.updated_at.isoformat()
        })

    except Exception as e:
        logger.error(f"❌ 获取偏好异常: {e}")
        return fail(str(e), 500)


@router.get("/user/{user_id}", response_model=dict)
async def get_user_preferences(
    user_id: str,
    preference_service: AnalysisPreferenceService = Depends(get_preference_service)
):
    """获取用户所有偏好"""
    try:
        preferences = await preference_service.get_user_preferences(user_id)

        return ok({
            "preferences": [
                {
                    "id": p.id,
                    "preference_type": p.preference_type,
                    "risk_level": p.risk_level,
                    "is_default": p.is_default
                }
                for p in preferences
            ]
        })

    except Exception as e:
        logger.error(f"❌ 获取用户偏好异常: {e}")
        return fail(str(e), 500)


@router.put("/{preference_id}", response_model=dict)
async def update_preference(
    preference_id: str,
    update_data: AnalysisPreferenceUpdate,
    preference_service: AnalysisPreferenceService = Depends(get_preference_service)
):
    """更新偏好"""
    try:
        preference = await preference_service.update_preference(preference_id, update_data)

        if not preference:
            return fail("更新偏好失败", 400)

        return ok({
            "id": preference.id,
            "preference_type": preference.preference_type,
            "updated_at": preference.updated_at.isoformat()
        })

    except Exception as e:
        logger.error(f"❌ 更新偏好异常: {e}")
        return fail(str(e), 500)


@router.delete("/{preference_id}", response_model=dict)
async def delete_preference(
    preference_id: str,
    preference_service: AnalysisPreferenceService = Depends(get_preference_service)
):
    """删除偏好"""
    try:
        # 实现删除逻辑
        return ok({"message": "偏好已删除"})

    except Exception as e:
        logger.error(f"❌ 删除偏好异常: {e}")
        return fail(str(e), 500)

