"""Agent 断言管理 API（P2.1-12）

提供断言的 CRUD + 启用/禁用 + 生成 + 回归测试端点。
断言是 P2「反思→可执行断言」闭环的机器可执行规则，存于 agent_assertions 集合，
在 manager agent 校验时同步执行。

端点：
  GET    /api/agent-assertions                列表（支持 agent_id/enabled/severity/assertion_type 过滤）
  GET    /api/agent-assertions/{assertion_id} 单条详情
  POST   /api/agent-assertions                创建断言
  PUT    /api/agent-assertions/{assertion_id} 更新断言
  DELETE /api/agent-assertions/{assertion_id} 删除断言
  POST   /api/agent-assertions/{assertion_id}/enable  启用/禁用
  POST   /api/agent-assertions/generate       从失败轨迹生成断言（LLM 离线提炼，默认 enabled=false）
  POST   /api/agent-assertions/regression-test 在历史轨迹上重放断言，返回效果报告
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.core.database import get_mongo_db
from app.core.response import ok, fail
from app.models.agent_assertion import (
    AgentAssertion, AssertionConstraint, AssertionSeverity, AssertionType,
)
from app.routers.auth_db import get_current_user
from app.services.agent_assertion_service import agent_assertion_service

logger = logging.getLogger("webapi")

router = APIRouter(
    prefix="/api/agent-assertions",
    tags=["agent-assertions"],
    dependencies=[Depends(get_current_user)],
)


# ==================== 请求模型 ====================

class AssertionCreate(BaseModel):
    """创建断言请求"""
    target_agent: str
    assertion_type: AssertionType
    target_field: str = "*"
    constraint: Dict[str, Any] = Field(default_factory=dict)
    severity: AssertionSeverity = AssertionSeverity.WARNING
    enabled: bool = False
    description: str = ""
    creator: str = "manual"


class AssertionUpdate(BaseModel):
    """更新断言请求（所有字段可选）"""
    target_field: Optional[str] = None
    constraint: Optional[Dict[str, Any]] = None
    severity: Optional[AssertionSeverity] = None
    enabled: Optional[bool] = None
    description: Optional[str] = None


class AssertionEnable(BaseModel):
    """启用/禁用请求"""
    enabled: bool


class GenerationRequest(BaseModel):
    """断言生成请求"""
    agent_id: Optional[str] = None
    days: int = 30
    limit: int = 100
    min_cluster_size: int = 2
    apply: bool = False  # False=dry-run 仅返回生成的断言；True=写入 DB


class RegressionRequest(BaseModel):
    """回归测试请求"""
    agent_id: Optional[str] = None
    days: int = 30
    limit: int = 200


# ==================== 辅助 ====================

def _to_public_dict(a: AgentAssertion) -> Dict[str, Any]:
    """转换为 JSON 安全 dict（constraint 展开）。"""
    d = a.model_dump(mode="json")
    return d


# ==================== CRUD 端点 ====================

@router.get("")
async def list_assertions(
    agent_id: Optional[str] = Query(None, description="按 agent_id 过滤"),
    enabled: Optional[bool] = Query(None, description="按 enabled 过滤"),
    severity: Optional[str] = Query(None, description="按 severity 过滤 (error/warning)"),
    assertion_type: Optional[str] = Query(None, description="按 assertion_type 过滤"),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """获取断言列表（支持多维过滤）"""
    try:
        assertions = await agent_assertion_service.get_assertions(
            agent_id=agent_id,
            enabled=enabled,
            severity=severity,
            assertion_type=assertion_type,
            limit=limit,
        )
        return ok([_to_public_dict(a) for a in assertions], message=f"共 {len(assertions)} 条断言")
    except Exception as e:
        logger.error(f"获取断言列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{assertion_id}")
async def get_assertion(assertion_id: str):
    """获取单条断言"""
    assertion = await agent_assertion_service.get_assertion(assertion_id)
    if assertion is None:
        raise HTTPException(status_code=404, detail=f"断言不存在: {assertion_id}")
    return ok(_to_public_dict(assertion))


@router.post("")
async def create_assertion_endpoint(body: AssertionCreate):
    """创建断言"""
    try:
        assertion = AgentAssertion(
            target_agent=body.target_agent,
            assertion_type=body.assertion_type,
            target_field=body.target_field,
            constraint=AssertionConstraint(**body.constraint),
            severity=body.severity,
            enabled=body.enabled,
            description=body.description,
            creator=body.creator,
        )
        created = await agent_assertion_service.create_assertion(assertion)
        if created is None:
            return fail("创建断言失败", code=500)
        return ok(_to_public_dict(created), message="断言已创建")
    except Exception as e:
        logger.error(f"创建断言失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{assertion_id}")
async def update_assertion_endpoint(assertion_id: str, body: AssertionUpdate):
    """更新断言字段"""
    update: Dict[str, Any] = {}
    if body.target_field is not None:
        update["target_field"] = body.target_field
    if body.constraint is not None:
        update["constraint"] = AssertionConstraint(**body.constraint).model_dump()
    if body.severity is not None:
        update["severity"] = body.severity
    if body.enabled is not None:
        update["enabled"] = body.enabled
    if body.description is not None:
        update["description"] = body.description

    if not update:
        return fail("未提供任何更新字段", code=400)

    success = await agent_assertion_service.update_assertion(assertion_id, update)
    if not success:
        raise HTTPException(status_code=404, detail=f"断言不存在或更新失败: {assertion_id}")
    return ok(message="断言已更新")


@router.delete("/{assertion_id}")
async def delete_assertion_endpoint(assertion_id: str):
    """删除断言"""
    success = await agent_assertion_service.delete_assertion(assertion_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"断言不存在: {assertion_id}")
    return ok(message="断言已删除")


@router.post("/{assertion_id}/enable")
async def toggle_assertion_endpoint(assertion_id: str, body: AssertionEnable):
    """启用/禁用断言"""
    success = await agent_assertion_service.enable_assertion(assertion_id, body.enabled)
    if not success:
        raise HTTPException(status_code=404, detail=f"断言不存在: {assertion_id}")
    return ok(message=f"断言已{'启用' if body.enabled else '禁用'}")


# ==================== 生成 & 回归测试端点 ====================

@router.post("/generate")
async def generate_assertions_endpoint(body: GenerationRequest):
    """从失败执行轨迹生成可执行断言（LLM 离线提炼）。

    - apply=False（默认）：dry-run，仅返回生成的断言供预览，不写库
    - apply=True：写入 agent_assertions 集合（默认 enabled=false，需人工激活）

    LLM 客户端从系统配置解析，不硬编码 provider。
    生成流程是同步的（含 LLM 调用），通过 asyncio.to_thread 在线程中执行避免阻塞事件循环。
    """
    try:
        from scripts.generate_assertions_from_failures import run_generation_sync
        result = await asyncio.to_thread(
            run_generation_sync,
            agent_id=body.agent_id,
            days=body.days,
            limit=body.limit,
            min_cluster_size=body.min_cluster_size,
            apply=body.apply,
        )
        msg = "生成完成" + ("（已写库，enabled=false 需人工激活）" if body.apply else "（dry-run）")
        return ok(result, message=msg)
    except Exception as e:
        logger.error(f"断言生成失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/regression-test")
async def regression_test_endpoint(body: RegressionRequest):
    """在历史轨迹上重放断言，返回拦截效果报告。

    报告含：各 agent 通过率、各断言命中率、按 system_prompt_hash 分组的违规率
    （评估 prompt 改进效果）、断言违规与 validation_status 的相关性。
    """
    try:
        from scripts.regression_test_assertions import run_regression_sync
        report = await asyncio.to_thread(
            run_regression_sync,
            agent_id=body.agent_id,
            days=body.days,
            limit=body.limit,
        )
        return ok(report, message="回归测试完成")
    except Exception as e:
        logger.error(f"回归测试失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
