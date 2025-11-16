"""
提示词模板 API 路由
"""

import logging
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional, List
from app.services.prompt_template_service import PromptTemplateService
from app.services.analysis_preference_service import AnalysisPreferenceService
from app.services.user_template_config_service import UserTemplateConfigService
from app.models.prompt_template import (
    PromptTemplateCreate,
    PromptTemplateUpdate,
    PromptTemplateResponse
)
from app.core.response import ok, fail

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/templates", tags=["templates"])

# 服务实例
template_service = PromptTemplateService()
preference_service = AnalysisPreferenceService()
config_service = UserTemplateConfigService()


@router.post("", response_model=dict)
async def create_template(
    template_data: PromptTemplateCreate,
    user_id: Optional[str] = Query(None),
    base_template_id: Optional[str] = Query(None)
):
    """创建模板"""
    try:
        # 如果是用户模板，需要获取基础模板版本
        base_version = None
        if base_template_id:
            base_template = await template_service.get_template(base_template_id)
            if base_template:
                base_version = base_template.version

        template = await template_service.create_template(
            template_data,
            user_id=user_id,
            base_template_id=base_template_id,
            base_version=base_version
        )

        if not template:
            return fail("创建模板失败", 400)

        return ok({
            "template_id": template.id,
            "version": template.version,
            "status": template.status,
            "created_at": template.created_at.isoformat()
        })

    except Exception as e:
        logger.error(f"❌ 创建模板异常: {e}")
        return fail(str(e), 500)


@router.get("/{template_id}", response_model=dict)
async def get_template(template_id: str):
    """获取模板"""
    try:
        template = await template_service.get_template(template_id)
        if not template:
            return fail("模板不存在", 404)

        return ok({
            "id": template.id,
            "agent_type": template.agent_type,
            "agent_name": template.agent_name,
            "template_name": template.template_name,
            "preference_type": template.preference_type,
            "content": template.content.model_dump(),
            "is_system": template.is_system,
            "status": template.status,
            "version": template.version,
            "created_at": template.created_at.isoformat(),
            "updated_at": template.updated_at.isoformat()
        })

    except Exception as e:
        logger.error(f"❌ 获取模板异常: {e}")
        return fail(str(e), 500)


@router.put("/{template_id}", response_model=dict)
async def update_template(
    template_id: str,
    update_data: PromptTemplateUpdate,
    user_id: Optional[str] = Query(None)
):
    """更新模板"""
    try:
        template = await template_service.update_template(
            template_id,
            update_data,
            user_id=user_id
        )

        if not template:
            return fail("更新模板失败或无权限", 400)

        return ok({
            "template_id": template.id,
            "version": template.version,
            "status": template.status,
            "updated_at": template.updated_at.isoformat()
        })

    except Exception as e:
        logger.error(f"❌ 更新模板异常: {e}")
        return fail(str(e), 500)


@router.get("/agent/{agent_type}/{agent_name}", response_model=dict)
async def get_agent_templates(
    agent_type: str,
    agent_name: str,
    preference_type: Optional[str] = Query(None)
):
    """获取特定Agent的模板"""
    try:
        # 这里需要实现查询逻辑
        return ok({
            "templates": []
        })

    except Exception as e:
        logger.error(f"❌ 获取Agent模板异常: {e}")
        return fail(str(e), 500)

