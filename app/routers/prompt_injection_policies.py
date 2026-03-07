"""
Prompt 注入策略 API

按 Agent + 场景管理上下文注入规则。
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.services.prompt_injection_policy_service import PromptInjectionPolicyService
from app.models.prompt_injection_policy import (
    PromptInjectionPolicyCreate,
    PromptInjectionPolicyUpdate,
)

logger = logging.getLogger("webapi")

router = APIRouter(prefix="/api/v1/prompt-policies", tags=["prompt-policies"])

# 服务实例
def get_service() -> PromptInjectionPolicyService:
    return PromptInjectionPolicyService()


@router.get("", summary="列表查询")
async def list_policies(
    agent_type: Optional[str] = Query(None, description="Agent 类型过滤"),
    agent_name: Optional[str] = Query(None, description="Agent 名称过滤"),
    scope: Optional[str] = Query(None, description="场景过滤: general / industry / stock"),
):
    """
    获取注入策略列表，支持 agent_type / agent_name / scope 过滤
    """
    svc = get_service()
    policies = await svc.list_policies(
        agent_type=agent_type,
        agent_name=agent_name,
        scope=scope,
    )
    return {"policies": policies, "total": len(policies)}


@router.get("/{policy_id}", summary="获取单个策略")
async def get_policy(policy_id: str):
    """获取指定 ID 的策略"""
    svc = get_service()
    policy = await svc.get_policy(policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail=f"策略不存在: {policy_id}")
    return {"policy": policy}


@router.post("", summary="创建策略")
async def create_policy(body: PromptInjectionPolicyCreate):
    """创建新的注入策略"""
    svc = get_service()
    data = body.model_dump()
    policy = await svc.create_policy(data)
    return {"policy": policy}


@router.put("/{policy_id}", summary="更新策略")
async def update_policy(policy_id: str, body: PromptInjectionPolicyUpdate):
    """更新指定策略"""
    svc = get_service()
    data = body.model_dump(exclude_none=True)
    if not data:
        policy = await svc.get_policy(policy_id)
        if not policy:
            raise HTTPException(status_code=404, detail=f"策略不存在: {policy_id}")
        return {"policy": policy}
    policy = await svc.update_policy(policy_id, data)
    if not policy:
        raise HTTPException(status_code=404, detail=f"策略不存在: {policy_id}")
    return {"policy": policy}


@router.delete("/{policy_id}", summary="删除策略")
async def delete_policy(policy_id: str):
    """删除指定策略"""
    svc = get_service()
    ok = await svc.delete_policy(policy_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"策略不存在: {policy_id}")
    return {"success": True, "message": "已删除"}
