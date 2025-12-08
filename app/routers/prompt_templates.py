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


# 依赖注入：获取服务实例
def get_template_service() -> PromptTemplateService:
    """获取模板服务实例"""
    return PromptTemplateService()


def get_preference_service() -> AnalysisPreferenceService:
    """获取偏好服务实例"""
    return AnalysisPreferenceService()


def get_config_service() -> UserTemplateConfigService:
    """获取配置服务实例"""
    return UserTemplateConfigService()


@router.get("", response_model=dict)
async def get_all_templates(
    agent_type: Optional[str] = Query(None),
    agent_name: Optional[str] = Query(None),
    preference_type: Optional[str] = Query(None),
    is_system: Optional[bool] = Query(None),
    status: Optional[str] = Query(None),
    q: Optional[str] = Query(None, description="按模板名称模糊搜索"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=200),
    template_service: PromptTemplateService = Depends(get_template_service)
):
    """获取所有模板（支持过滤）"""
    try:
        # 构建查询条件
        query = {}
        if agent_type:
            query["agent_type"] = agent_type
        if agent_name:
            query["agent_name"] = agent_name
        if preference_type:
            query["preference_type"] = preference_type
        if is_system is not None:
            query["is_system"] = is_system
        if status:
            query["status"] = status

        # 模糊搜索
        if q:
            query["template_name"] = {"$regex": q, "$options": "i"}

        total = await template_service.templates_collection.count_documents(query)
        cursor = template_service.templates_collection.find(query).skip(skip).limit(limit)
        templates = await cursor.to_list(length=None)

        result = []
        for template_doc in templates:
            result.append({
                "id": str(template_doc["_id"]),
                "agent_type": template_doc.get("agent_type"),
                "agent_name": template_doc.get("agent_name"),
                "template_name": template_doc.get("template_name"),
                "preference_type": template_doc.get("preference_type"),
                "is_system": template_doc.get("is_system"),
                "status": template_doc.get("status"),
                "version": template_doc.get("version"),
                "created_at": template_doc.get("created_at").isoformat() if template_doc.get("created_at") else None,
                "updated_at": template_doc.get("updated_at").isoformat() if template_doc.get("updated_at") else None
            })

        return ok({
            "items": result,
            "total": total,
            "skip": skip,
            "limit": limit
        })

    except Exception as e:
        logger.error(f"❌ 获取模板列表异常: {e}")
        return fail(str(e), 500)


@router.post("", response_model=dict)
async def create_template(
    template_data: PromptTemplateCreate,
    user_id: Optional[str] = Query(None),
    base_template_id: Optional[str] = Query(None),
    template_service: PromptTemplateService = Depends(get_template_service)
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
            "template_id": str(template.id),
            "version": template.version,
            "status": template.status,
            "created_at": template.created_at.isoformat()
        })

    except Exception as e:
        logger.error(f"❌ 创建模板异常: {e}")
        return fail(str(e), 500)


@router.get("/{template_id}", response_model=dict)
async def get_template(
    template_id: str,
    template_service: PromptTemplateService = Depends(get_template_service)
):
    """获取模板"""
    try:
        template = await template_service.get_template(template_id)
        if not template:
            return fail("模板不存在", 404)

        return ok({
            "id": str(template.id),
            "agent_type": template.agent_type,
            "agent_name": template.agent_name,
            "template_name": template.template_name,
            "preference_type": template.preference_type,
            "content": template.content.model_dump(),
            "remark": template.remark,
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
    user_id: Optional[str] = Query(None),
    template_service: PromptTemplateService = Depends(get_template_service)
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
            "template_id": str(template.id),
            "version": template.version,
            "status": template.status,
            "updated_at": template.updated_at.isoformat()
        })

    except Exception as e:
        logger.error(f"❌ 更新模板异常: {e}")
        return fail(str(e), 500)


@router.delete("/{template_id}", response_model=dict)
async def delete_template(
    template_id: str,
    user_id: Optional[str] = Query(None),
    template_service: PromptTemplateService = Depends(get_template_service)
):
    """删除用户模板"""
    try:
        success = await template_service.delete_template(template_id, user_id=user_id)
        if not success:
            return fail("删除模板失败或无权限", 400)
        return ok({"deleted": True, "template_id": template_id})
    except Exception as e:
        logger.error(f"❌ 删除模板异常: {e}")
        return fail(str(e), 500)

@router.get("/agent/{agent_type}/{agent_name}", response_model=dict)
async def get_agent_templates(
    agent_type: str,
    agent_name: str,
    preference_type: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    include_system: bool = Query(True, description="是否包含系统模板"),
    include_user: bool = Query(True, description="是否包含用户模板"),
    template_service: PromptTemplateService = Depends(get_template_service),
    config_service: UserTemplateConfigService = Depends(get_config_service)
):
    """获取特定Agent的所有可用模板（系统模板 + 用户模板）"""
    try:
        result = []
        seen_ids = set()  # 去重

        # 基础查询条件
        base_query = {
            "agent_type": agent_type,
            "agent_name": agent_name,
            "status": "active"  # 只返回已启用的模板
        }

        if preference_type:
            base_query["preference_type"] = preference_type

        # 1. 获取系统模板
        if include_system:
            system_query = {**base_query, "is_system": True}
            cursor = template_service.templates_collection.find(system_query)
            system_templates = await cursor.to_list(length=None)
            for template_doc in system_templates:
                template_id = str(template_doc["_id"])
                if template_id not in seen_ids:
                    seen_ids.add(template_id)
                    result.append({
                        "id": template_id,
                        "template_name": template_doc.get("template_name"),
                        "preference_type": template_doc.get("preference_type"),
                        "status": template_doc.get("status"),
                        "version": template_doc.get("version"),
                        "is_system": True,
                        "created_by": None,
                        "created_at": template_doc.get("created_at").isoformat() if template_doc.get("created_at") else None
                    })

        # 2. 获取用户创建的模板
        if include_user and user_id:
            # created_by 字段在数据库中是 ObjectId 类型
            from bson import ObjectId
            try:
                user_object_id = ObjectId(user_id)
            except Exception:
                user_object_id = user_id  # 如果转换失败，使用原始字符串

            user_query = {**base_query, "created_by": user_object_id, "is_system": False}
            cursor = template_service.templates_collection.find(user_query)
            user_templates = await cursor.to_list(length=None)
            for template_doc in user_templates:
                template_id = str(template_doc["_id"])
                if template_id not in seen_ids:
                    seen_ids.add(template_id)
                    result.append({
                        "id": template_id,
                        "template_name": template_doc.get("template_name"),
                        "preference_type": template_doc.get("preference_type"),
                        "status": template_doc.get("status"),
                        "version": template_doc.get("version"),
                        "is_system": False,
                        "created_by": user_id,
                        "created_at": template_doc.get("created_at").isoformat() if template_doc.get("created_at") else None
                    })

        return ok({
            "templates": result,
            "total": len(result)
        })

    except Exception as e:
        logger.error(f"❌ 获取Agent模板异常: {e}")
        return fail(str(e), 500)

