"""
Agent 工坊 API - Phase 1
"""

import logging
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.core.database import get_mongo_db
from app.core.response import ok
from app.services.agent_workshop_service import AgentWorkshopService

logger = logging.getLogger("webapi")

router = APIRouter(prefix="/api/agent-workshop", tags=["agent-workshop"])


class StartSessionRequest(BaseModel):
    description: str = Field(..., min_length=2, description="Agent 需求描述")
    user_id: str = Field(default="", description="用户 ID")


class RespondRequest(BaseModel):
    message: str = Field(..., min_length=1, description="用户回复")


class PreviewSpecRequest(BaseModel):
    message: str = Field(default="确认", description="补充说明")


class EvaluateVersionRequest(BaseModel):
    evaluation_type: str = Field(default="sandbox", description="评估类型")
    sample_set_id: Optional[str] = Field(default=None, description="样本集 ID")
    user_feedback: str = Field(default="", description="用户补充反馈")
    benchmark_outputs: List[dict] = Field(default_factory=list, description="样本输出列表")
    runtime_result: Optional[dict] = Field(default=None, description="真实运行结果")


class IterateVersionRequest(BaseModel):
    feedback: str = Field(default="", description="基于评估的迭代反馈")


class ReviewEvaluationArtifactRequest(BaseModel):
    target_path: str = Field(..., min_length=1, description="证据项路径")
    target_title: str = Field(default="", description="证据项标题")
    artifact_type: str = Field(default="", description="证据项类型")
    finding_id: str = Field(default="", description="关联 finding_id")
    worker_name: str = Field(default="", description="关联 worker 名称")
    approved: bool = Field(..., description="是否人工审核通过")
    reason: str = Field(default="", description="审核原因")
    comment: str = Field(default="", description="审核说明")
    reviewer: str = Field(default="", description="审核人")


class DebugVersionLLMRequest(BaseModel):
    provider: str = Field(..., description="LLM 提供商")
    model: str = Field(..., description="模型名称")
    temperature: float = Field(default=0.2, description="温度")
    max_tokens: int = Field(default=4000, description="最大输出 token")
    backend_url: Optional[str] = Field(default=None, description="后端地址")
    api_key: Optional[str] = Field(default=None, description="API Key")


class DebugVersionStockRequest(BaseModel):
    symbol: str = Field(..., description="股票代码")
    market_type: Optional[str] = Field(default="A股", description="市场类型")
    analysis_date: Optional[str] = Field(default=None, description="分析日期")


class DebugVersionRequest(BaseModel):
    llm: DebugVersionLLMRequest
    stock: DebugVersionStockRequest
    user_goal: str = Field(default="", description="本次调试目标")
    prompt_overrides: Optional[dict[str, Any]] = Field(default=None, description="Prompt 覆盖")


def _get_service(db: AsyncIOMotorDatabase) -> AgentWorkshopService:
    return AgentWorkshopService(db=db)


@router.post("/sessions/start")
async def start_session(
    req: StartSessionRequest,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    try:
        svc = _get_service(db)
        result = await svc.start_session(description=req.description, user_id=req.user_id)
        return ok(result)
    except Exception as e:
        logger.error(f"❌ Agent 工坊创建会话失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_id}/respond")
async def respond_to_session(
    session_id: str,
    req: RespondRequest,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    try:
        svc = _get_service(db)
        result = await svc.respond(session_id, req.message)
        return ok(result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Agent 工坊会话回复失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_id}/preview-spec")
async def preview_spec(
    session_id: str,
    req: PreviewSpecRequest,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    try:
        svc = _get_service(db)
        result = await svc.preview_spec(session_id, req.message)
        return ok(result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Agent 工坊规格预览失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_id}/analyze-gaps")
async def analyze_gaps(
    session_id: str,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    try:
        svc = _get_service(db)
        result = await svc.analyze_gaps(session_id)
        return ok(result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Agent 工坊缺口分析失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_id}/build-version")
async def build_version(
    session_id: str,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    try:
        svc = _get_service(db)
        result = await svc.build_version(session_id)
        return ok(result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Agent 工坊生成版本草案失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_id}/generate-tooling-plan")
async def generate_tooling_plan(
    session_id: str,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    try:
        svc = _get_service(db)
        result = await svc.generate_tooling_plan(session_id)
        return ok(result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Agent 工坊生成工具需求草案失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions")
async def list_sessions(
    stage: Optional[str] = Query(None, description="按阶段筛选，多个用逗号分隔"),
    user_id: Optional[str] = Query(None, description="按用户 ID 筛选"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    svc = _get_service(db)
    result = await svc.list_sessions(stage=stage, user_id=user_id, page=page, page_size=page_size)
    return ok(result)


@router.get("/capability-snapshot")
async def get_capability_snapshot(
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    svc = _get_service(db)
    result = await svc.get_capability_snapshot()
    return ok(result)


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
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
    svc = _get_service(db)
    deleted = await svc.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"会话 {session_id} 不存在")
    return ok({"deleted": True})


@router.get("/specs")
async def list_specs(
    status: Optional[str] = Query(None, description="按状态筛选，多个用逗号分隔"),
    user_id: Optional[str] = Query(None, description="按用户 ID 筛选"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    svc = _get_service(db)
    result = await svc.list_specs(status=status, user_id=user_id, page=page, page_size=page_size)
    return ok(result)


@router.get("/specs/{spec_id}")
async def get_spec(
    spec_id: str,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    svc = _get_service(db)
    spec = await svc.get_spec(spec_id)
    if not spec:
        raise HTTPException(status_code=404, detail=f"规格 {spec_id} 不存在")
    return ok(spec)


@router.delete("/specs/{spec_id}")
async def delete_spec(
    spec_id: str,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    svc = _get_service(db)
    result = await svc.delete_spec(spec_id)
    if not result.get("deleted"):
        raise HTTPException(status_code=404, detail=f"规格 {spec_id} 不存在")
    return ok(result)


@router.get("/specs/{spec_id}/sample-sets")
async def list_sample_sets(
    spec_id: str,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    try:
        svc = _get_service(db)
        result = await svc.list_sample_sets(spec_id)
        return ok(result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Agent 工坊样本集获取失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/versions")
async def list_versions(
    spec_id: Optional[str] = Query(None, description="按规格 ID 筛选"),
    status: Optional[str] = Query(None, description="按状态筛选，多个用逗号分隔"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    svc = _get_service(db)
    result = await svc.list_versions(spec_id=spec_id, status=status, page=page, page_size=page_size)
    return ok(result)


@router.get("/versions/{version_id}")
async def get_version(
    version_id: str,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    svc = _get_service(db)
    version = await svc.get_version(version_id)
    if not version:
        raise HTTPException(status_code=404, detail=f"版本 {version_id} 不存在")
    return ok(version)


@router.delete("/versions/{version_id}")
async def delete_version(
    version_id: str,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    svc = _get_service(db)
    result = await svc.delete_version(version_id)
    if not result.get("deleted"):
        raise HTTPException(status_code=404, detail=f"版本 {version_id} 不存在")
    return ok(result)


@router.post("/versions/{version_id}/evaluate")
async def evaluate_version(
    version_id: str,
    req: EvaluateVersionRequest,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    try:
        svc = _get_service(db)
        result = await svc.evaluate_version(
            version_id,
            evaluation_type=req.evaluation_type,
            sample_set_id=req.sample_set_id,
            user_feedback=req.user_feedback,
            benchmark_outputs=req.benchmark_outputs,
            runtime_result=req.runtime_result,
        )
        return ok(result)
    except ValueError as e:
        detail = str(e)
        status_code = 404 if "不存在" in detail else 400
        raise HTTPException(status_code=status_code, detail=detail)
    except Exception as e:
        logger.error(f"❌ Agent 工坊版本评估失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/versions/{version_id}/evaluations")
async def list_evaluations(
    version_id: str,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    svc = _get_service(db)
    result = await svc.list_evaluations(version_id=version_id, page=page, page_size=page_size)
    return ok(result)


@router.post("/evaluations/{evaluation_id}/manual-reviews")
async def review_evaluation_artifact(
    evaluation_id: str,
    req: ReviewEvaluationArtifactRequest,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    try:
        svc = _get_service(db)
        result = await svc.review_evaluation_artifact(
            evaluation_id=evaluation_id,
            target_path=req.target_path,
            target_title=req.target_title,
            artifact_type=req.artifact_type,
            finding_id=req.finding_id,
            worker_name=req.worker_name,
            approved=req.approved,
            reason=req.reason,
            comment=req.comment,
            reviewer=req.reviewer,
        )
        return ok(result)
    except ValueError as e:
        detail = str(e)
        status_code = 404 if "不存在" in detail else 400
        raise HTTPException(status_code=status_code, detail=detail)
    except Exception as e:
        logger.error(f"❌ Agent 工坊评估人工审核失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/versions/{version_id}/iterate")
async def iterate_version(
    version_id: str,
    req: IterateVersionRequest,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    try:
        svc = _get_service(db)
        result = await svc.iterate_version(version_id, feedback=req.feedback)
        return ok(result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Agent 工坊发起迭代失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/versions/{version_id}/publish")
async def publish_version(
    version_id: str,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    try:
        svc = _get_service(db)
        result = await svc.publish_version(version_id)
        return ok(result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Agent 工坊版本发布失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/specs/{spec_id}/rollback")
async def rollback_version(
    spec_id: str,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """一键回滚到上一个 active 版本"""
    try:
        svc = _get_service(db)
        result = await svc.rollback_version(spec_id)
        return ok(result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Agent 版本回滚失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


class UpdateVersionPromptRequest(BaseModel):
    content: dict = Field(..., description="提示词内容（6 字段结构）")
    status: Optional[str] = Field(default=None, description="模板状态: draft, active")


class UpdateVersionMetadataRequest(BaseModel):
    metadata: dict = Field(..., description="要更新的 agent_metadata 字段")


@router.put("/versions/{version_id}/metadata")
async def update_version_metadata(
    version_id: str,
    req: UpdateVersionMetadataRequest,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    try:
        svc = _get_service(db)
        result = await svc.update_version_metadata(version_id, req.metadata)
        return ok(result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Agent 工坊更新版本 metadata 失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/versions/{version_id}/prompt")
async def get_version_prompt(
    version_id: str,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    try:
        svc = _get_service(db)
        result = await svc.get_version_prompt(version_id)
        return ok(result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Agent 工坊获取版本提示词失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/versions/{version_id}/prompt")
async def update_version_prompt(
    version_id: str,
    req: UpdateVersionPromptRequest,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    try:
        svc = _get_service(db)
        result = await svc.update_version_prompt(
            version_id,
            content=req.content,
            status=req.status,
        )
        return ok(result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Agent 工坊更新版本提示词失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/versions/{version_id}/debug")
async def debug_version(
    version_id: str,
    req: DebugVersionRequest,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    try:
        svc = _get_service(db)
        result = await svc.debug_version(
            version_id=version_id,
            llm=req.llm.model_dump(),
            stock=req.stock.model_dump(),
            user_goal=req.user_goal,
            prompt_overrides=req.prompt_overrides or {},
        )
        return ok(result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Agent 工坊版本调试失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))