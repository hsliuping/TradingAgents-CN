"""
智能体 API 路由

提供智能体的查询和管理端点
"""

from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
import logging

from app.core.response import ok, fail
from app.routers.auth_db import get_current_user
from app.services.license_service import get_license_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agents", tags=["agents"])


# ==================== 数据模型 ====================

class AgentMetadata(BaseModel):
    """智能体元数据"""
    id: str
    name: str
    description: str
    category: str
    license_tier: str
    inputs: List[str] = []
    outputs: List[str] = []
    icon: str = "📦"
    color: str = "#409EFF"
    tags: List[str] = []
    is_available: Optional[bool] = None
    is_implemented: Optional[bool] = None
    locked_reason: Optional[str] = None


class AgentCategory(BaseModel):
    """智能体类别"""
    id: str
    name: str
    count: int


# ==================== 辅助函数 ====================

async def get_user_license_tier(
    user: dict = Depends(get_current_user),
    x_app_token: Optional[str] = Header(None)
) -> str:
    """
    获取当前用户的许可证级别

    优先使用远程验证的结果，如果没有 app-token 则默认为 free
    """
    if not x_app_token:
        return "free"

    try:
        license_service = get_license_service()
        license_info = await license_service.verify_app_token(x_app_token)
        if license_info.is_valid:
            # 将 license plan 映射到 tier
            plan_to_tier = {
                "free": "free",
                "trial": "pro",  # 试用版也算 pro
                "pro": "pro",
                "enterprise": "enterprise"
            }
            return plan_to_tier.get(license_info.plan, "free")
    except Exception as e:
        logger.warning(f"获取用户许可证失败: {e}")

    return "free"


# ==================== API 端点 ====================

@router.get("")
async def list_all_agents():
    """获取所有智能体"""
    try:
        from core.api import AgentAPI
        api = AgentAPI()
        agents = api.list_all()
        return ok(agents)
    except Exception as e:
        logger.error(f"获取智能体列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/available")
async def list_available_agents(
    user_tier: str = Depends(get_user_license_tier)
):
    """获取当前许可证可用的智能体"""
    try:
        from core.api import AgentAPI
        api = AgentAPI()
        agents = api.list_available_for_tier(user_tier)
        return ok(agents)
    except Exception as e:
        logger.error(f"获取可用智能体失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/categories")
async def get_categories():
    """获取所有类别"""
    try:
        from core.api import AgentAPI
        api = AgentAPI()
        categories = api.get_categories()
        return ok(categories)
    except Exception as e:
        logger.error(f"获取类别失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/category/{category}")
async def list_by_category(category: str):
    """按类别获取智能体"""
    try:
        from core.api import AgentAPI
        api = AgentAPI()
        agents = api.list_by_category(category)
        return ok(agents)
    except Exception as e:
        logger.error(f"按类别获取智能体失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{agent_id}")
async def get_agent(agent_id: str):
    """获取智能体详情"""
    try:
        from core.api import AgentAPI
        api = AgentAPI()
        agent = api.get(agent_id)

        if agent is None:
            raise HTTPException(status_code=404, detail="智能体不存在")

        return ok(agent)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取智能体详情失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

