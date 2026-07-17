"""
AI 工作流架构师 API — v3.0

提供对话式工作流创建（多轮需求沟通）、蓝图确认、自动补全（提示词/Skill）、
迭代优化和沟通记录等端点。

参考: docs/05-design/v3.0/ai-workflow-generation.md §6
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.core.database import get_mongo_db
from app.core.response import ok, fail
from app.services.workflow_generation_service import WorkflowGenerationService

logger = logging.getLogger("webapi")

router = APIRouter(prefix="/api/workflow-generation", tags=["workflow-generation"])


# =============================================================================
# 请求模型
# =============================================================================

class StartSessionRequest(BaseModel):
    """开始工作流创建会话"""
    description: str = Field(..., min_length=2, description="工作流需求描述")
    user_id: str = Field(default="", description="用户 ID")


class RespondRequest(BaseModel):
    """用户回复对话"""
    message: str = Field(..., min_length=1, description="用户回复")


class ConfirmRequest(BaseModel):
    """确认方案并创建"""
    message: str = Field(default="确认", description="确认消息或补充说明")
    workflow_type: Optional[str] = Field(default=None, description="工作流类型")


class OptimizeRequest(BaseModel):
    """提交优化反馈"""
    feedback: str = Field(..., min_length=2, description="优化反馈")


# =============================================================================
# 辅助函数
# =============================================================================

def _get_service(db: AsyncIOMotorDatabase) -> WorkflowGenerationService:
    """创建 WorkflowGenerationService 实例"""
    return WorkflowGenerationService(db=db)


# =============================================================================
# 会话对话 API
# =============================================================================

@router.post("/sessions/start")
async def start_session(
    req: StartSessionRequest,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """开始工作流创建会话：提交需求描述，AI 返回方案草案和缺口分析"""
    try:
        svc = _get_service(db)
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
        result = await svc.respond(session_id, req.message)
        return ok(result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"❌ 会话回复失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_id}/confirm")
async def confirm_and_create(
    session_id: str,
    req: ConfirmRequest,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """确认方案并创建工作流（含自动补全提示词和 Skill）"""
    try:
        svc = _get_service(db)
        result = await svc.confirm_and_create(session_id, req.message, workflow_type=req.workflow_type)
        return ok(result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"❌ 确认创建失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# 迭代优化 API
# =============================================================================

@router.post("/sessions/{session_id}/optimize")
async def optimize_workflow(
    session_id: str,
    req: OptimizeRequest,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """提交优化反馈，AI 生成优化建议"""
    try:
        svc = _get_service(db)
        result = await svc.optimize(session_id, req.feedback)
        return ok(result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"❌ 优化失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_id}/confirm-optimization")
async def confirm_optimization(
    session_id: str,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """确认并应用优化方案"""
    try:
        svc = _get_service(db)
        result = await svc.confirm_optimization(session_id)
        return ok(result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"❌ 确认优化失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_id}/publish")
async def publish_workflow(
    session_id: str,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """发布草稿工作流为正式版本（将 draft 资源激活为 active）"""
    try:
        svc = _get_service(db)
        result = await svc.publish(session_id)
        return ok(result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"❌ 发布失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# 会话管理 API
# =============================================================================

@router.get("/sessions")
async def list_sessions(
    status: Optional[str] = Query(
        None,
        description="按状态筛选，多个用逗号分隔: gathering,completed,optimizing",
    ),
    user_id: Optional[str] = Query(None, description="按用户 ID 筛选"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """列出工作流创建会话"""
    svc = _get_service(db)
    result = await svc.list_sessions(
        status=status, user_id=user_id or "", page=page, page_size=page_size
    )
    return ok(result)


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """获取会话详情"""
    svc = _get_service(db)
    session = await svc.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"会话 {session_id} 不存在")
    return ok(session)


@router.get("/sessions/{session_id}/history")
async def get_session_history(
    session_id: str,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """获取完整沟通记录（含初始创建 + 优化轮次）"""
    svc = _get_service(db)
    result = await svc.get_session_history(session_id)
    if not result.get("sections"):
        raise HTTPException(status_code=404, detail=f"会话 {session_id} 不存在或没有记录")
    return ok(result)


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """删除会话"""
    svc = _get_service(db)
    deleted = await svc.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"会话 {session_id} 不存在")
    return ok({"deleted": True})

