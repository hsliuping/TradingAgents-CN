"""
Skill 生成 API — v3.0 AI 驱动的 Skill 创建

提供需求沟通（多轮对话）、代码生成管线、外部 Skill 管理等端点。
"""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.core.database import get_mongo_db
from app.core.response import ok, fail
from app.services.skill_generation_service import SkillGenerationService

logger = logging.getLogger("webapi")

router = APIRouter(prefix="/api/skill-generation", tags=["skill-generation"])


# =============================================================================
# 请求/响应模型
# =============================================================================

class StartSessionRequest(BaseModel):
    """开始创建会话"""
    description: str = Field(..., min_length=2, description="需求描述")
    user_id: str = Field(default="", description="用户 ID")
    provider: str = Field(default="deepseek", description="LLM 提供商")
    model: Optional[str] = Field(default=None, description="模型名称")


class RespondRequest(BaseModel):
    """回复对话"""
    message: str = Field(..., min_length=1, description="用户回复")


class ConfirmSpecRequest(BaseModel):
    """确认规格"""
    message: str = Field(default="确认", description="确认消息或补充说明")


class UpdateStatusRequest(BaseModel):
    """更新 Skill 状态"""
    status: str = Field(..., description="新状态: active / disabled / archived")


class TestSkillRequest(BaseModel):
    """测试 Skill"""
    args: Dict[str, Any] = Field(default_factory=dict, description="测试参数")


class OptimizeSkillRequest(BaseModel):
    """优化 Skill"""
    feedback: str = Field(..., min_length=2, description="优化需求描述")


# =============================================================================
# 辅助函数
# =============================================================================

def _get_service(db: AsyncIOMotorDatabase, provider: str = "deepseek", model: str = None) -> SkillGenerationService:
    """创建 SkillGenerationService 实例"""
    return SkillGenerationService(db=db, provider=provider, model=model)


# =============================================================================
# 需求沟通 API
# =============================================================================

@router.post("/sessions/start")
async def start_session(
    req: StartSessionRequest,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """开始 Skill 创建会话：提交初始需求，AI 返回澄清问题"""
    try:
        svc = _get_service(db, provider=req.provider, model=req.model)
        result = await svc.start_session(
            description=req.description, user_id=req.user_id
        )
        return ok(result)
    except Exception as e:
        logger.error(f"❌ 创建会话失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_id}/respond")
async def respond_to_session(
    session_id: str,
    req: RespondRequest,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """用户回复 AI 的问题，推进对话"""
    try:
        svc = _get_service(db)
        result = await svc.respond_to_session(session_id, req.message)
        return ok(result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"❌ 会话回复失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_id}/confirm")
async def confirm_spec(
    session_id: str,
    req: ConfirmSpecRequest,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """确认 Skill 规格并触发代码生成管线"""
    try:
        svc = _get_service(db)
        result = await svc.confirm_spec(session_id, req.message)
        return ok(result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"❌ 规格确认失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions")
async def list_sessions(
    status: Optional[str] = Query(None, description="按状态筛选，多个用逗号分隔: gathering,confirmed,completed"),
    user_id: Optional[str] = Query(None, description="按用户 ID 筛选"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """列出创建会话（支持按状态筛选，用于查看草稿/未完成会话）"""
    svc = _get_service(db)
    result = await svc.list_sessions(
        status=status, user_id=user_id, page=page, page_size=page_size
    )
    return ok(result)


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """获取创建会话详情"""
    svc = _get_service(db)
    session = await svc.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"会话 {session_id} 不存在")
    return ok(session)


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """删除草稿会话"""
    svc = _get_service(db)
    deleted = await svc.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"会话 {session_id} 不存在")
    return ok({"deleted": True})


# =============================================================================
# 外部 Skill 管理 API
# =============================================================================

@router.get("/skills")
async def list_skills(
    category: Optional[str] = Query(None, description="按分类筛选"),
    status: Optional[str] = Query(None, description="按状态筛选: active/disabled/archived"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """获取 AI 生成的 Skill 列表（分页）"""
    svc = _get_service(db)
    result = await svc.list_skills(
        category=category, status=status, page=page, page_size=page_size
    )
    return ok(result)


@router.get("/skills/{skill_id}")
async def get_skill(
    skill_id: str,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """获取 Skill 详情"""
    svc = _get_service(db)
    skill = await svc.get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill {skill_id} 不存在")
    return ok(skill)


@router.get("/skills/{skill_id}/code")
async def get_skill_code(
    skill_id: str,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """查看 Skill 源代码"""
    svc = _get_service(db)
    code = await svc.get_skill_code(skill_id)
    if code is None:
        raise HTTPException(status_code=404, detail=f"Skill {skill_id} 不存在")
    return ok({"tool_id": skill_id, "code": code})


@router.get("/skills/{skill_id}/history")
async def get_skill_history(
    skill_id: str,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """获取 Skill 完整沟通历史（原始创建 + 所有优化轮次）"""
    svc = _get_service(db)
    history = await svc.get_skill_history(skill_id)
    if not history:
        raise HTTPException(status_code=404, detail=f"Skill {skill_id} 不存在")
    return ok(history)


@router.put("/skills/{skill_id}/status")
async def update_skill_status(
    skill_id: str,
    req: UpdateStatusRequest,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """更新 Skill 状态（启用/禁用/归档）"""
    if req.status not in ("active", "disabled", "archived"):
        raise HTTPException(status_code=400, detail="状态必须是 active/disabled/archived")
    svc = _get_service(db)
    updated = await svc.update_skill_status(skill_id, req.status)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Skill {skill_id} 不存在")
    return ok({"tool_id": skill_id, "status": req.status})


@router.delete("/skills/{skill_id}")
async def delete_skill(
    skill_id: str,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """删除 Skill"""
    svc = _get_service(db)
    deleted = await svc.delete_skill(skill_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Skill {skill_id} 不存在")
    return ok({"tool_id": skill_id, "deleted": True})


@router.post("/skills/{skill_id}/test")
async def test_skill(
    skill_id: str,
    req: TestSkillRequest,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """手动测试 Skill（在沙箱中执行）"""
    try:
        svc = _get_service(db)
        result = await svc.test_skill(skill_id, test_args=req.args or None)
        return ok(result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Skill 测试失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/skills/{skill_id}/optimize")
async def optimize_skill(
    skill_id: str,
    req: OptimizeSkillRequest,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """优化已有 Skill：基于用户反馈重新生成代码"""
    try:
        svc = _get_service(db)
        result = await svc.optimize_skill(skill_id, req.feedback)
        return ok(result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Skill 优化失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
