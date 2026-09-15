"""
Skill 生成 API — v3.0 AI 驱动的 Skill 创建

提供需求沟通（多轮对话）、代码生成管线、外部 Skill 管理等端点。
"""

import asyncio
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.core.database import get_mongo_db
from app.core.response import ok, fail
from app.services.capability_index_service import CapabilityIndexService
from app.services.skill_generation_service import SkillGenerationService
from core.tools.external.external_data_source_catalog import (
    EXTERNAL_DATA_SOURCE_CATALOG,
    EXTERNAL_DATA_SOURCE_DOC,
)
from core.tools.external.stock_data_catalog import (
    STOCK_DATA_COLLECTION_CATALOG,
    STOCK_DATA_COLLECTION_DOC,
)

logger = logging.getLogger("webapi")

router = APIRouter(prefix="/api/skill-generation", tags=["skill-generation"])


# =============================================================================
# 请求/响应模型
# =============================================================================

class StartSessionRequest(BaseModel):
    """开始创建会话"""
    description: str = Field(..., min_length=2, description="需求描述")
    user_id: str = Field(default="", description="用户 ID")
    handoff_context: Optional[Dict[str, Any]] = Field(default=None, description="来自上游工坊的交接上下文")
    iterate_skill_id: Optional[str] = Field(default=None, description="迭代模式：要优化的已有 Skill 的 tool_id")
    provider: str = Field(default="deepseek", description="LLM 提供商（回退用）")
    model: Optional[str] = Field(default=None, description="模型名称（回退用）")
    reasoning_model: Optional[str] = Field(default=None, description="需求分析模型（覆盖系统默认的深度推理模型）")
    coding_model: Optional[str] = Field(default=None, description="代码生成模型（覆盖系统默认的编程模型）")


class RespondRequest(BaseModel):
    """回复对话"""
    message: str = Field(..., min_length=1, description="用户回复")


class ConfirmSpecRequest(BaseModel):
    """确认规格"""
    message: str = Field(default="确认", description="确认消息或补充说明")
    codegen_timeout: Optional[int] = Field(default=None, ge=60, le=1800, description="代码生成单次 LLM 调用超时（秒），不传用默认值")


class UpdateStatusRequest(BaseModel):
    """更新 Skill 状态"""
    status: str = Field(..., description="新状态: active / disabled / archived")


class UpdateSkillInfoRequest(BaseModel):
    """更新 Skill 展示名称与功能说明"""
    display_name: str = Field(..., min_length=1, max_length=100, description="展示名称")
    description: str = Field(default="", max_length=2000, description="功能说明")


class TestSkillRequest(BaseModel):
    """测试 Skill"""
    args: Dict[str, Any] = Field(default_factory=dict, description="测试参数")


class OptimizeSkillRequest(BaseModel):
    """优化 Skill"""
    feedback: str = Field(..., min_length=2, description="优化需求描述")


class RepairSessionRequest(BaseModel):
    """基于失败结果修正当前创建会话"""
    feedback: str = Field(..., min_length=2, description="告诉 AI 本轮生成哪里有问题，以及你希望怎么改")
    repair_plan: Optional[str] = Field(default="", description="用户确认通过的修正计划文本")
    codegen_timeout: Optional[int] = Field(default=None, ge=60, le=1800, description="代码生成单次 LLM 调用超时（秒），不传用默认值")


# =============================================================================
# 辅助函数
# =============================================================================

async def _get_service_with_llm(
    db: AsyncIOMotorDatabase,
    provider: str = "deepseek",
    model: Optional[str] = None,
    reasoning_model: Optional[str] = None,
    coding_model: Optional[str] = None,
) -> SkillGenerationService:
    """
    创建 SkillGenerationService：
    - 需求分析：优先 reasoning_model 指定，否则用系统「深度推理大模型」
    - 代码生成：优先 coding_model 指定，否则用系统「编程大模型」
    - 均未配置时回退到 provider/model
    """
    from app.services.intelligent_assistant_service import (
        get_coding_llm_config,
        get_quick_llm_config,
        get_reasoning_llm_config,
    )
    from core.llm import UnifiedLLMClient

    # 需求分析：深度推理大模型
    reasoning_config = None
    if reasoning_model:
        from app.services.intelligent_assistant_service import _get_llm_config_for_model
        reasoning_config = await _get_llm_config_for_model(db, reasoning_model)
    if not reasoning_config:
        reasoning_config = await get_reasoning_llm_config(db)
    reasoning_client = (
        UnifiedLLMClient.from_config(reasoning_config) if reasoning_config else None
    )
    if reasoning_client:
        logger.debug("Skill 需求分析使用深度推理大模型")

    # 需求对话：快速模型（清晰度评估/边界检测/多轮回复），显著降低轮次响应延迟
    quick_config = await get_quick_llm_config(db)
    quick_client = (
        UnifiedLLMClient.from_config(quick_config) if quick_config else None
    )
    if quick_client:
        logger.debug("Skill 需求对话使用快速模型")

    # 代码生成：编程大模型
    coding_config = None
    if coding_model:
        from app.services.intelligent_assistant_service import _get_llm_config_for_model
        coding_config = await _get_llm_config_for_model(db, coding_model)
    if not coding_config:
        coding_config = await get_coding_llm_config(db)
    coding_client = (
        UnifiedLLMClient.from_config(coding_config) if coding_config else None
    )
    if coding_client:
        logger.debug("Skill 代码生成使用编程大模型")

    return SkillGenerationService(
        db=db,
        reasoning_llm_client=reasoning_client,
        coding_llm_client=coding_client,
        quick_llm_client=quick_client,
        provider=provider,
        model=model,
    )


# =============================================================================
# 模型选择 API（开放大模型搜索/选择）
# =============================================================================

@router.get("/models")
async def list_available_models(
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """
    获取 Skill 生成可用的模型列表，用于前端下拉选择
    返回系统配置中的模型，并标注默认的需求分析模型、代码生成模型
    """
    try:
        config_doc = await db.system_configs.find_one(
            {"is_active": True}, sort=[("version", -1)]
        )
        if not config_doc or "llm_configs" not in config_doc:
            return ok({
                "models": [],
                "default_reasoning_model": None,
                "default_coding_model": None,
            })

        default_models = config_doc.get("default_models") or {}
        system_settings = config_doc.get("system_settings") or {}
        reasoning = (
            default_models.get("deep_reasoning_model")
            or system_settings.get("deep_reasoning_model")
        )
        coding = (
            default_models.get("coding_model")
            or system_settings.get("coding_model")
        )

        llm_configs = config_doc.get("llm_configs", [])
        models = [
            {
                "model_name": c.get("model_name"),
                "display_name": c.get("model_display_name") or c.get("model_name"),
                "provider": c.get("provider"),
                "enabled": c.get("enabled", True),
            }
            for c in llm_configs
            if c.get("enabled", True)
        ]
        return ok({
            "models": models,
            "default_reasoning_model": reasoning,
            "default_coding_model": coding,
        })
    except Exception as e:
        logger.error(f"获取模型列表失败: {e}", exc_info=True)
        return ok({"models": [], "default_reasoning_model": None, "default_coding_model": None})


@router.get("/catalog/stock-data")
async def get_stock_data_catalog():
    """获取 Skill 生成器使用的股票数据集合目录。"""
    return ok({
        "collections": STOCK_DATA_COLLECTION_CATALOG,
        "doc": STOCK_DATA_COLLECTION_DOC,
    })


@router.get("/catalog/external-data-sources")
async def get_external_data_source_catalog():
    """获取 Skill 生成器使用的外部接口与数据源目录。"""
    return ok({
        "sources": EXTERNAL_DATA_SOURCE_CATALOG,
        "doc": EXTERNAL_DATA_SOURCE_DOC,
    })


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
        svc = await _get_service_with_llm(
            db,
            provider=req.provider,
            model=req.model,
            reasoning_model=req.reasoning_model,
            coding_model=req.coding_model,
        )
        result = await svc.start_session(
            description=req.description,
            user_id=req.user_id,
            handoff_context=req.handoff_context,
            iterate_skill_id=req.iterate_skill_id,
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
        svc = await _get_service_with_llm(db)
        result = await svc.respond_to_session(session_id, req.message)
        return ok(result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"❌ 会话回复失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_id}/preview-spec")
async def preview_spec(
    session_id: str,
    req: ConfirmSpecRequest,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """预览 Skill 规格（不执行管线），用于规格确认步骤展示"""
    try:
        svc = await _get_service_with_llm(db)
        result = await svc.preview_spec(session_id, req.message)
        if result is None:
            raise HTTPException(status_code=400, detail="规格生成失败，请重新描述需求")
        return ok(result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"❌ 规格预览失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_id}/confirm")
async def confirm_spec(
    session_id: str,
    req: ConfirmSpecRequest,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """确认 Skill 规格并触发代码生成管线"""
    try:
        svc = await _get_service_with_llm(db)
        result = await svc.confirm_spec(session_id, req.message, codegen_timeout=req.codegen_timeout)
        return ok(result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"❌ 规格确认失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_id}/repair")
async def repair_session(
    session_id: str,
    req: RepairSessionRequest,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """当生成/验证失败后，基于失败原因和用户反馈重新修正并生成"""
    try:
        svc = await _get_service_with_llm(db)
        result = await svc.repair_session(
            session_id, req.feedback, req.repair_plan or "",
            codegen_timeout=req.codegen_timeout,
        )
        return ok(result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"❌ 会话修正失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_id}/repair-plan")
async def preview_repair_session(
    session_id: str,
    req: RepairSessionRequest,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """失败后先生成 AI 修正计划，待用户确认后再触发重跑"""
    try:
        svc = await _get_service_with_llm(db)
        result = await svc.preview_repair_session(session_id, req.feedback)
        return ok(result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"❌ 生成修正计划失败: {e}", exc_info=True)
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
    svc = await _get_service_with_llm(db)
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
    svc = await _get_service_with_llm(db)
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
    svc = await _get_service_with_llm(db)
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
    source: Optional[str] = Query(None, description="按来源筛选: agent_studio_auto_gap_resolution/manual_or_other/generated"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """获取 AI 生成的 Skill 列表（分页）"""
    svc = await _get_service_with_llm(db)
    result = await svc.list_skills(
        category=category, status=status, source=source, page=page, page_size=page_size
    )
    return ok(result)


@router.get("/skills/{skill_id}")
async def get_skill(
    skill_id: str,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """获取 Skill 详情"""
    svc = await _get_service_with_llm(db)
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
    svc = await _get_service_with_llm(db)
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
    svc = await _get_service_with_llm(db)
    history = await svc.get_skill_history(skill_id)
    if not history:
        raise HTTPException(status_code=404, detail=f"Skill {skill_id} 不存在")
    return ok(history)


@router.get("/skills/{skill_id}/versions")
async def list_skill_versions(
    skill_id: str,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """查询 Skill 的所有版本（同一系列的所有迭代版本）

    如果 skill_id 是根 Skill，返回 parent_skill_id=skill_id 的所有版本 + 自己
    如果 skill_id 是子版本，先找根，再返回整条版本链

    返回按版本号升序排列，每个版本包含: tool_id, version, display_name, version_note, status, created_at
    """
    # 先查当前 skill，确定根 parent_skill_id
    current = await db["external_skills"].find_one({"tool_id": skill_id})
    if not current:
        raise HTTPException(status_code=404, detail=f"Skill {skill_id} 不存在")

    # 确定 parent_skill_id（根 Skill 的 parent_skill_id 为空，自己就是根）
    parent_skill_id = current.get("parent_skill_id") or skill_id

    # 查询同系列所有版本：根 Skill 自己 + 所有 parent_skill_id 指向根的版本
    cursor = db["external_skills"].find({
        "$or": [
            {"tool_id": parent_skill_id},
            {"parent_skill_id": parent_skill_id},
        ]
    }).sort("version", 1)

    versions = []
    async for doc in cursor:
        doc.pop("_id", None)
        versions.append({
            "tool_id": doc.get("tool_id", ""),
            "version": doc.get("version", 1),
            "display_name": doc.get("display_name", ""),
            "version_note": doc.get("version_note", ""),
            "status": doc.get("status", ""),
            "created_at": doc.get("created_at", ""),
            "final_score": doc.get("final_score"),
            "is_current": doc.get("tool_id") == skill_id,
        })

    return ok({
        "parent_skill_id": parent_skill_id,
        "current_tool_id": skill_id,
        "versions": versions,
        "total": len(versions),
    })


@router.put("/skills/{skill_id}/status")
async def update_skill_status(
    skill_id: str,
    req: UpdateStatusRequest,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """更新 Skill 状态（启用/禁用/归档）"""
    if req.status not in ("active", "disabled", "archived"):
        raise HTTPException(status_code=400, detail="状态必须是 active/disabled/archived")
    svc = await _get_service_with_llm(db)
    updated = await svc.update_skill_status(skill_id, req.status)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Skill {skill_id} 不存在")
    return ok({"tool_id": skill_id, "status": req.status})


@router.put("/skills/{skill_id}/info")
async def update_skill_info(
    skill_id: str,
    req: UpdateSkillInfoRequest,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """更新 Skill 的展示名称与功能说明（参数/代码等已验证契约不可在此修改）"""
    try:
        svc = await _get_service_with_llm(db)
        updated = await svc.update_skill_info(
            skill_id, req.display_name, req.description
        )
        if not updated:
            raise HTTPException(status_code=404, detail=f"Skill {skill_id} 不存在")
        return ok({
            "tool_id": skill_id,
            "display_name": req.display_name.strip(),
            "description": req.description.strip(),
        })
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Skill 说明更新失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/skills/{skill_id}")
async def delete_skill(
    skill_id: str,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """删除 Skill"""
    svc = await _get_service_with_llm(db)
    deleted = await svc.delete_skill(skill_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Skill {skill_id} 不存在")
    # 异步触发能力索引同步，清理幽灵工具
    asyncio.create_task(CapabilityIndexService.refresh_after_change(db))
    return ok({"tool_id": skill_id, "deleted": True})


@router.post("/skills/{skill_id}/test")
async def test_skill(
    skill_id: str,
    req: TestSkillRequest,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """手动测试 Skill（在沙箱中执行）"""
    try:
        svc = await _get_service_with_llm(db)
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
        svc = await _get_service_with_llm(db)
        result = await svc.optimize_skill(skill_id, req.feedback)
        return ok(result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Skill 优化失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
