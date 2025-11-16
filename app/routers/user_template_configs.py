"""
用户模板配置 API 路由
"""

import logging
from fastapi import APIRouter, Depends, Query
from typing import Optional
from app.services.user_template_config_service import UserTemplateConfigService
from app.models.user_template_config import (
    UserTemplateConfigCreate,
    UserTemplateConfigUpdate
)
from app.core.response import ok, fail

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/user-template-configs", tags=["user-template-configs"])


# 依赖注入：获取服务实例
def get_config_service() -> UserTemplateConfigService:
    """获取配置服务实例"""
    return UserTemplateConfigService()


@router.post("", response_model=dict)
async def create_config(
    user_id: str = Query(...),
    config_data: UserTemplateConfigCreate = None,
    config_service: UserTemplateConfigService = Depends(get_config_service)
):
    """创建用户模板配置"""
    try:
        if not config_data:
            return fail("配置数据不能为空", 400)

        config = await config_service.create_config(user_id, config_data)

        if not config:
            return fail("创建配置失败", 400)

        return ok({
            "config_id": config.id,
            "agent_type": config.agent_type,
            "agent_name": config.agent_name,
            "template_id": config.template_id,
            "is_active": config.is_active,
            "created_at": config.created_at.isoformat()
        })

    except Exception as e:
        logger.error(f"❌ 创建配置异常: {e}")
        return fail(str(e), 500)


@router.get("/{config_id}", response_model=dict)
async def get_config(
    config_id: str,
    config_service: UserTemplateConfigService = Depends(get_config_service)
):
    """获取配置"""
    try:
        config = await config_service.get_config(config_id)

        if not config:
            return fail("配置不存在", 404)

        return ok({
            "id": config.id,
            "user_id": config.user_id,
            "agent_type": config.agent_type,
            "agent_name": config.agent_name,
            "template_id": config.template_id,
            "preference_id": config.preference_id,
            "is_active": config.is_active,
            "created_at": config.created_at.isoformat(),
            "updated_at": config.updated_at.isoformat()
        })

    except Exception as e:
        logger.error(f"❌ 获取配置异常: {e}")
        return fail(str(e), 500)


@router.get("/user/{user_id}", response_model=dict)
async def get_user_configs(
    user_id: str,
    config_service: UserTemplateConfigService = Depends(get_config_service)
):
    """获取用户所有配置"""
    try:
        configs = await config_service.get_user_configs(user_id)

        return ok({
            "configs": [
                {
                    "id": c.id,
                    "agent_type": c.agent_type,
                    "agent_name": c.agent_name,
                    "template_id": c.template_id,
                    "is_active": c.is_active
                }
                for c in configs
            ]
        })

    except Exception as e:
        logger.error(f"❌ 获取用户配置异常: {e}")
        return fail(str(e), 500)


@router.get("/active", response_model=dict)
async def get_active_config(
    user_id: str = Query(...),
    agent_type: str = Query(...),
    agent_name: str = Query(...),
    preference_id: Optional[str] = Query(None),
    config_service: UserTemplateConfigService = Depends(get_config_service)
):
    """获取活跃配置"""
    try:
        config = await config_service.get_active_config(
            user_id,
            agent_type,
            agent_name,
            preference_id
        )

        if not config:
            return fail("未找到活跃配置", 404)

        return ok({
            "id": config.id,
            "template_id": config.template_id,
            "is_active": config.is_active
        })

    except Exception as e:
        logger.error(f"❌ 获取活跃配置异常: {e}")
        return fail(str(e), 500)


@router.put("/{config_id}", response_model=dict)
async def update_config(
    config_id: str,
    update_data: UserTemplateConfigUpdate,
    config_service: UserTemplateConfigService = Depends(get_config_service)
):
    """更新配置"""
    try:
        config = await config_service.update_config(config_id, update_data)

        if not config:
            return fail("更新配置失败", 400)

        return ok({
            "id": config.id,
            "template_id": config.template_id,
            "updated_at": config.updated_at.isoformat()
        })

    except Exception as e:
        logger.error(f"❌ 更新配置异常: {e}")
        return fail(str(e), 500)


@router.get("/effective-template", response_model=dict)
async def get_effective_template(
    user_id: str = Query(...),
    agent_type: str = Query(...),
    agent_name: str = Query(...),
    preference_id: Optional[str] = Query(None),
    config_service: UserTemplateConfigService = Depends(get_config_service)
):
    """获取有效模板（用户优先，系统兜底）"""
    try:
        template = await config_service.get_effective_template(
            user_id,
            agent_type,
            agent_name,
            preference_id
        )

        if not template:
            return fail("未找到有效模板", 404)

        return ok(template)

    except Exception as e:
        logger.error(f"❌ 获取有效模板异常: {e}")
        return fail(str(e), 500)

