"""
Prompt 预览 API

提供组装后的最终 Prompt 预览能力，支持：
- 选择 Agent、分析场景、行业、个股
- 预览各段内容和来源
- 查看能力缺口提醒
"""

import logging
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.prompt_assembly_service import get_prompt_assembly_service

logger = logging.getLogger("webapi")

router = APIRouter(prefix="/api/v1/prompt-preview", tags=["prompt-preview"])


# ==================== 请求/响应模型 ====================

class PromptPreviewRequest(BaseModel):
    """Prompt 预览请求"""
    agent_type: str = Field(..., description="Agent 类型，如 analysts_v2")
    agent_name: str = Field(..., description="Agent 名称，如 market_analyst_v2")
    analysis_type: str = Field(default="general", description="分析类型: general / industry / stock")
    industry: Optional[str] = Field(None, description="行业名称")
    stock_symbol: Optional[str] = Field(None, description="股票代码")
    task_description: str = Field(default="", description="当前任务描述")
    include_capability: bool = Field(default=True, description="是否附带能力块")


class PromptPreviewResponse(BaseModel):
    """Prompt 预览响应"""
    final_prompt: str = Field(..., description="最终 Prompt 全文")
    sections: Dict[str, str] = Field(default_factory=dict, description="各段内容")
    sources: Dict[str, str] = Field(default_factory=dict, description="各段来源说明")
    template_id: str = Field(default="", description="使用的模板 ID")
    profile_used: Dict[str, Any] = Field(default_factory=dict, description="使用的画像信息")
    capability_gaps: List[str] = Field(default_factory=list, description="能力缺口提醒")


class IndustryListResponse(BaseModel):
    """行业列表响应"""
    industries: List[Dict[str, Any]] = Field(default_factory=list, description="行业列表")


class AgentListResponse(BaseModel):
    """Agent 列表响应"""
    agents: List[Dict[str, Any]] = Field(default_factory=list, description="Agent 列表")


# ==================== 端点 ====================

@router.post("/assemble", summary="预览组装后的最终 Prompt", response_model=PromptPreviewResponse)
async def assemble_prompt_preview(request: PromptPreviewRequest):
    """
    预览组装后的最终 Prompt
    
    组装流程：
    1. 根据 agent_type + agent_name 获取基础模板
    2. 根据 analysis_type + industry + stock_symbol 生成分析上下文块
    3. 生成能力边界说明块
    4. 生成任务指令块
    5. 组装最终 Prompt
    """
    try:
        service = get_prompt_assembly_service()
        
        result = service.assemble_prompt(
            agent_type=request.agent_type,
            agent_name=request.agent_name,
            analysis_type=request.analysis_type,
            industry=request.industry,
            stock_symbol=request.stock_symbol,
            task_description=request.task_description,
            include_capability=request.include_capability,
        )
        
        return PromptPreviewResponse(**result)
    
    except Exception as e:
        logger.error(f"❌ Prompt 预览失败: {e}")
        raise HTTPException(status_code=500, detail=f"Prompt 预览失败: {str(e)}")


@router.get("/industries", summary="获取行业列表", response_model=IndustryListResponse)
async def list_industries():
    """
    获取所有行业画像列表，用于前端下拉选择
    """
    try:
        from app.services.analysis_profile_service import AnalysisProfileService
        
        service = AnalysisProfileService()
        profiles = await service.get_industry_profiles(is_active=True)
        
        industries = [
            {
                "industry": p.get("industry", ""),
                "display_name": p.get("display_name", p.get("industry", "")),
                "analysis_focus": p.get("analysis_focus", "")[:100] if p.get("analysis_focus") else "",
            }
            for p in profiles
        ]
        
        return IndustryListResponse(industries=industries)
    
    except Exception as e:
        logger.error(f"❌ 获取行业列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取行业列表失败: {str(e)}")


@router.get("/agents", summary="获取 Agent 列表", response_model=AgentListResponse)
async def list_agents():
    """
    获取所有可用的 Agent 列表，用于前端下拉选择
    
    从 prompt_templates 集合中提取所有唯一的 (agent_type, agent_name) 组合
    """
    try:
        from app.core.database import get_mongo_db
        
        db = get_mongo_db()
        
        # 聚合查询获取唯一的 agent_type + agent_name 组合
        pipeline = [
            {"$match": {"status": "active"}},
            {"$group": {
                "_id": {"agent_type": "$agent_type", "agent_name": "$agent_name"},
                "agent_type": {"$first": "$agent_type"},
                "agent_name": {"$first": "$agent_name"},
                "count": {"$sum": 1},
            }},
            {"$sort": {"agent_type": 1, "agent_name": 1}},
        ]
        
        results = await db.prompt_templates.aggregate(pipeline).to_list(length=100)
        
        agents = [
            {
                "agent_type": r.get("agent_type", ""),
                "agent_name": r.get("agent_name", ""),
                "template_count": r.get("count", 0),
            }
            for r in results
            if r.get("agent_type") and r.get("agent_name")
        ]
        
        return AgentListResponse(agents=agents)
    
    except Exception as e:
        logger.error(f"❌ 获取 Agent 列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取 Agent 列表失败: {str(e)}")


@router.get("/capability-snapshot", summary="获取能力快照")
async def get_capability_snapshot():
    """
    获取当前系统的能力快照，包括：
    - 内置数据源
    - 已启用的 MCP 服务器
    - 活跃的 Skill
    """
    try:
        from app.services.analysis_profile_service import AnalysisProfileService
        from app.core.database import get_mongo_db
        
        db = get_mongo_db()
        service = AnalysisProfileService()
        snapshot = await service._collect_capability_snapshot(db)
        
        return {
            "success": True,
            "snapshot": snapshot,
        }
    
    except Exception as e:
        logger.error(f"❌ 获取能力快照失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取能力快照失败: {str(e)}")