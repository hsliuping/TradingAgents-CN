"""
模板历史 API 路由
"""

import logging
from fastapi import APIRouter, Depends, Query
from typing import Optional
from app.services.template_history_service import TemplateHistoryService
from app.services.prompt_template_service import PromptTemplateService
from app.models.template_history import TemplateHistoryCreate
from app.core.permissions import require_feature
from app.core.response import ok, fail
from app.routers.auth_db import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/template-history",
    tags=["template-history"],
    dependencies=[Depends(require_feature("prompt_templates"))]
)


# 依赖注入：获取服务实例
def get_history_service() -> TemplateHistoryService:
    """获取历史服务实例"""
    return TemplateHistoryService()


def get_template_service() -> PromptTemplateService:
    """获取模板服务实例"""
    return PromptTemplateService()


async def _has_template_access(
    template_id: str,
    user_id: str,
    template_service: PromptTemplateService
) -> bool:
    template = await template_service.get_template(template_id)
    if not template:
        return False
    return template.is_system or str(template.created_by) == user_id


@router.get("/{history_id}", response_model=dict)
async def get_history(
    history_id: str,
    current_user: dict = Depends(get_current_user),
    template_service: PromptTemplateService = Depends(get_template_service),
    history_service: TemplateHistoryService = Depends(get_history_service)
):
    """获取历史记录"""
    try:
        user_id = str(current_user["id"])
        history = await history_service.get_history(history_id)

        if not history:
            return fail("历史记录不存在", 404)
        if not await _has_template_access(str(history.template_id), user_id, template_service):
            return fail("历史记录不存在或无权访问", 403)

        return ok({
            "id": history.id,
            "template_id": history.template_id,
            "user_id": history.user_id,
            "version": history.version,
            "content": history.content,
            "change_description": history.change_description,
            "change_type": history.change_type,
            "created_at": history.created_at.isoformat()
        })

    except Exception as e:
        logger.error(f"❌ 获取历史记录异常: {e}")
        return fail(str(e), 500)


@router.get("/template/{template_id}", response_model=dict)
async def get_template_history(
    template_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    template_service: PromptTemplateService = Depends(get_template_service),
    history_service: TemplateHistoryService = Depends(get_history_service)
):
    """获取模板的历史记录"""
    try:
        user_id = str(current_user["id"])
        if not await _has_template_access(template_id, user_id, template_service):
            return fail("模板历史不存在或无权访问", 403)

        histories = await history_service.get_template_history(template_id, skip, limit)

        return ok({
            "histories": [
                {
                    "id": h.id,
                    "version": h.version,
                    "change_type": h.change_type,
                    "change_description": h.change_description,
                    "created_at": h.created_at.isoformat()
                }
                for h in histories
            ],
            "total": len(histories)
        })

    except Exception as e:
        logger.error(f"❌ 获取模板历史异常: {e}")
        return fail(str(e), 500)


@router.get("/template/{template_id}/version/{version}", response_model=dict)
async def get_version(
    template_id: str,
    version: int,
    current_user: dict = Depends(get_current_user),
    template_service: PromptTemplateService = Depends(get_template_service),
    history_service: TemplateHistoryService = Depends(get_history_service)
):
    """获取特定版本"""
    try:
        user_id = str(current_user["id"])
        if not await _has_template_access(template_id, user_id, template_service):
            return fail("版本不存在或无权访问", 403)

        history = await history_service.get_version_by_number(template_id, version)

        if not history:
            return fail("版本不存在", 404)

        return ok({
            "id": history.id,
            "template_id": history.template_id,
            "version": history.version,
            "content": history.content,
            "change_type": history.change_type,
            "created_at": history.created_at.isoformat()
        })

    except Exception as e:
        logger.error(f"❌ 获取版本异常: {e}")
        return fail(str(e), 500)


@router.get("/template/{template_id}/compare", response_model=dict)
async def compare_versions(
    template_id: str,
    version1: int = Query(...),
    version2: int = Query(...),
    current_user: dict = Depends(get_current_user),
    template_service: PromptTemplateService = Depends(get_template_service),
    history_service: TemplateHistoryService = Depends(get_history_service)
):
    """对比两个版本"""
    try:
        user_id = str(current_user["id"])
        if not await _has_template_access(template_id, user_id, template_service):
            return fail("版本对比失败或无权访问", 403)

        comparison = await history_service.compare_versions(template_id, version1, version2)

        if not comparison:
            return fail("版本对比失败", 400)

        return ok(comparison)

    except Exception as e:
        logger.error(f"❌ 对比版本异常: {e}")
        return fail(str(e), 500)

