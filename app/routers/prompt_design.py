"""
Prompt 设计助手 API — Phase 3

对话式优化 Agent 的 Prompt（模板 + 注入策略）。
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.core.database import get_mongo_db
from app.routers.auth_db import get_current_user
from app.services.prompt_design_assistant_service import PromptDesignAssistantService

logger = logging.getLogger("webapi")

router = APIRouter(prefix="/api/v1/prompt-design", tags=["prompt-design"])


# ==================== 请求模型 ====================

class ChatRequest(BaseModel):
    """对话请求"""
    session_id: Optional[str] = Field(None, description="会话 ID，新建时留空")
    message: str = Field(..., min_length=1, description="用户消息")
    agent_type: str = Field(..., description="Agent 类型")
    agent_name: str = Field(..., description="Agent 名称")
    analysis_type: str = Field(default="industry", description="分析场景: general/industry/stock")
    industry: Optional[str] = Field(None, description="行业（用于预览）")
    stock_symbol: Optional[str] = Field(None, description="个股（用于预览）")
    workflow_id: Optional[str] = Field(None, description="工作流 ID")
    node_id: Optional[str] = Field(None, description="节点 ID")


class DiffRequest(BaseModel):
    """对比请求"""
    agent_type: str = Field(..., description="Agent 类型")
    agent_name: str = Field(..., description="Agent 名称")
    proposed_template: Optional[dict] = Field(None, description="建议的模板修改")
    proposed_policy: Optional[dict] = Field(None, description="建议的策略修改")
    analysis_type: str = Field(default="industry", description="分析场景: general/industry/stock")
    industry: Optional[str] = Field(None, description="行业（用于预览）")
    stock_symbol: Optional[str] = Field(None, description="个股（用于预览）")
    workflow_id: Optional[str] = Field(None, description="工作流 ID")
    node_id: Optional[str] = Field(None, description="节点 ID")


class ApplyRequest(BaseModel):
    """应用请求"""
    session_id: Optional[str] = Field(None, description="对话会话 ID")
    agent_type: str = Field(..., description="Agent 类型")
    agent_name: str = Field(..., description="Agent 名称")
    proposed_template: Optional[dict] = Field(None, description="建议的模板修改")
    proposed_policy: Optional[dict] = Field(None, description="建议的策略修改")
    analysis_type: str = Field(default="industry", description="分析场景: general/industry/stock")
    industry: Optional[str] = Field(None, description="行业（用于预览）")
    stock_symbol: Optional[str] = Field(None, description="个股（用于预览）")
    workflow_id: Optional[str] = Field(None, description="工作流 ID")
    node_id: Optional[str] = Field(None, description="节点 ID")


class RollbackRequest(BaseModel):
    """回退请求"""
    session_id: str = Field(..., description="对话会话 ID")


# ==================== 端点 ====================

def _get_service(db: AsyncIOMotorDatabase) -> PromptDesignAssistantService:
    return PromptDesignAssistantService(db=db)


@router.post("/chat", summary="对话式 Prompt 优化")
async def chat(
    req: ChatRequest,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
    current_user: dict = Depends(get_current_user),
):
    """
    与 AI 助手对话，描述优化意图，获取修改建议。
    支持多轮对话，session_id 留空时创建新会话。
    """
    try:
        svc = _get_service(db)
        result = await svc.chat(
            session_id=req.session_id or "",
            message=req.message,
            agent_type=req.agent_type,
            agent_name=req.agent_name,
            analysis_type=req.analysis_type,
            industry=req.industry,
            stock_symbol=req.stock_symbol,
            user_id=str(current_user["id"]),
            workflow_id=req.workflow_id,
            node_id=req.node_id,
        )
        return {"success": True, **result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Prompt 设计对话失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stock-industry", summary="根据股票代码查询所属行业")
async def get_stock_industry(
    symbol: str = Query(..., description="股票代码，如 600519"),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """
    根据股票代码从 stock_basic_info 查询所属行业。
    用于引导式流程：用户输入股票后自动获取行业。
    """
    try:
        code = symbol.strip().zfill(6) if symbol.isdigit() else symbol
        doc = await db["stock_basic_info"].find_one(
            {"$or": [{"code": code}, {"symbol": code}]},
            {"_id": 0, "name": 1, "industry": 1, "code": 1}
        )
        if not doc:
            return {"success": False, "industry": None, "name": None, "message": "未找到该股票"}
        return {
            "success": True,
            "industry": doc.get("industry") or None,
            "name": doc.get("name") or code,
            "code": doc.get("code") or code,
        }
    except Exception as e:
        logger.error(f"❌ 查询股票行业失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/industry-profile", summary="检查行业是否已有分析配置")
async def check_industry_profile(
    industry: str = Query(..., description="行业名称"),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """
    检查指定行业是否已有行业分析配置（industry_analysis_profiles）。
    用于引导式流程：有则提示使用，无则提示新建。
    """
    try:
        import re
        profile = await db["industry_analysis_profiles"].find_one(
            {"industry": industry, "is_active": True}
        )
        if not profile:
            # 模糊匹配
            escaped = re.escape(industry)
            profile = await db["industry_analysis_profiles"].find_one(
                {"industry": {"$regex": escaped, "$options": "i"}, "is_active": True}
            )
        if not profile:
            return {
                "success": True,
                "has_profile": False,
                "profile": None,
                "message": f"行业「{industry}」暂无分析配置，可前往创建",
            }
        return {
            "success": True,
            "has_profile": True,
            "profile": {
                "id": str(profile.get("_id", "")),
                "industry": profile.get("industry"),
                "display_name": profile.get("display_name"),
                "analysis_focus": profile.get("analysis_focus", "")[:200],
                "dimension_count": len(profile.get("analysis_dimensions", [])),
            },
            "message": f"行业「{industry}」已有分析配置",
        }
    except Exception as e:
        logger.error(f"❌ 检查行业配置失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/workflows", summary="获取可选分析流程列表")
async def list_prompt_workflows():
    """
    获取可用于提示词优化的分析流程列表。
    """
    try:
        from core.api import WorkflowAPI
        api = WorkflowAPI()
        all_wfs = api.list_all()
        # 只返回有 Agent 节点的流程
        result = []
        for wf in all_wfs:
            nodes = wf.get("nodes", [])
            agent_nodes = [n for n in nodes if n.get("agent_id")]
            if agent_nodes:
                result.append({
                    "id": wf.get("id"),
                    "name": wf.get("name", ""),
                    "description": (wf.get("description", ""))[:150],
                    "agent_count": len(agent_nodes),
                })
        return {"success": True, "workflows": result}
    except Exception as e:
        logger.error(f"❌ 获取流程列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/workflow-nodes", summary="获取分析流程中的提示节点")
async def get_workflow_prompt_nodes(
    workflow_id: str = Query(..., description="工作流 ID，如 v2_stock_analysis"),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """
    获取工作流中所有使用 Agent 的节点（即提示词节点），
    每个节点说明用途，供用户选择是否优化。
    """
    try:
        from core.api import WorkflowAPI
        api = WorkflowAPI()
        wf = api.get(workflow_id)
        if not wf:
            return {"success": False, "nodes": [], "message": "工作流不存在"}
        nodes = []
        for n in wf.get("nodes", []):
            agent_id = n.get("agent_id")
            if not agent_id:
                continue
            nodes.append({
                "node_id": n.get("id"),
                "agent_id": agent_id,
                "label": n.get("label", agent_id),
                "type": n.get("type", ""),
                "focus": n.get("config", {}).get("focus", "") or n.get("config", {}).get("description", ""),
            })
        return {
            "success": True,
            "workflow_name": wf.get("name", ""),
            "nodes": nodes,
        }
    except Exception as e:
        logger.error(f"❌ 获取流程节点失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/diff", summary="修改前后对比")
async def get_diff(
    req: DiffRequest,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
    current_user: dict = Depends(get_current_user),
):
    """
    获取修改前后的 Prompt 对比预览。
    """
    try:
        svc = _get_service(db)
        result = await svc.get_diff(
            agent_type=req.agent_type,
            agent_name=req.agent_name,
            proposed_template=req.proposed_template,
            proposed_policy=req.proposed_policy,
            analysis_type=req.analysis_type,
            industry=req.industry,
            stock_symbol=req.stock_symbol,
            user_id=str(current_user["id"]),
            workflow_id=req.workflow_id,
            node_id=req.node_id,
        )
        return {"success": True, **result}
    except Exception as e:
        logger.error(f"❌ 获取对比失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/apply", summary="确认并应用修改")
async def apply_changes(
    req: ApplyRequest,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
    current_user: dict = Depends(get_current_user),
):
    """将结构化提示词建议真正写入模板或注入策略。"""
    try:
        svc = _get_service(db)
        result = await svc.apply_changes(
            session_id=req.session_id,
            agent_type=req.agent_type,
            agent_name=req.agent_name,
            user_id=str(current_user["id"]),
            proposed_template=req.proposed_template,
            proposed_policy=req.proposed_policy,
            analysis_type=req.analysis_type,
            industry=req.industry,
            stock_symbol=req.stock_symbol,
            workflow_id=req.workflow_id,
            node_id=req.node_id,
        )
        return {"success": True, **result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ 应用 Prompt 修改失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rollback", summary="回退最近一次应用")
async def rollback_changes(
    req: RollbackRequest,
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
    current_user: dict = Depends(get_current_user),
):
    """回退当前会话最近一次已应用的提示词修改。"""
    try:
        svc = _get_service(db)
        result = await svc.rollback_changes(
            session_id=req.session_id,
            user_id=str(current_user["id"]),
        )
        return {"success": True, **result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ 回退 Prompt 修改失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
