"""
行业/个股分析配置管理 API

提供 CRUD 操作和 AI 生成功能
"""

import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.analysis_profile_service import AnalysisProfileService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analysis-profiles", tags=["analysis-profiles"])

_service = AnalysisProfileService()


# ── Request / Response Schemas ──

class IndustryProfileCreate(BaseModel):
    industry: str = Field(..., description="行业名称")
    display_name: Optional[str] = Field(None, description="显示名称")
    analysis_dimensions: list = Field(default_factory=list)
    analysis_focus: str = Field("", description="分析重点")
    key_metrics: list = Field(default_factory=list)
    comparable_companies: list = Field(default_factory=list)
    is_active: bool = True


class AIGenerateRequest(BaseModel):
    industry: str = Field(..., description="行业名称，如'银行'、'新能源汽车'")
    user_request: Optional[str] = Field(default="", description="用户的补充要求或本轮修订指令")
    existing_profile: Optional[Dict[str, Any]] = Field(default=None, description="当前草案，用于多轮修订")


# ── 行业配置 CRUD ──

@router.get("/industries")
async def list_industry_profiles(is_active: Optional[bool] = Query(None)):
    """获取所有行业配置列表"""
    profiles = await _service.get_industry_profiles(is_active=is_active)
    return {"success": True, "data": profiles, "total": len(profiles)}


@router.get("/industries/{profile_id}")
async def get_industry_profile(profile_id: str):
    """获取单个行业配置详情"""
    profile = await _service.get_industry_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="行业配置不存在")
    return {"success": True, "data": profile}


@router.post("/industries")
async def create_industry_profile(body: IndustryProfileCreate):
    """创建行业配置"""
    data = body.model_dump()
    if not data.get("display_name"):
        data["display_name"] = f"{data['industry']}行业"
    # 检查是否已存在
    existing = await _service.get_industry_profile_by_name(data["industry"])
    if existing:
        raise HTTPException(status_code=409, detail=f"行业 '{data['industry']}' 的配置已存在，请使用更新接口")
    result = await _service.create_industry_profile(data)
    return {"success": True, "data": result}


@router.put("/industries/{profile_id}")
async def update_industry_profile(profile_id: str, body: IndustryProfileCreate):
    """更新行业配置"""
    data = body.model_dump()
    result = await _service.update_industry_profile(profile_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="行业配置不存在或未修改")
    return {"success": True, "data": result}


@router.delete("/industries/{profile_id}")
async def delete_industry_profile(profile_id: str):
    """删除行业配置"""
    deleted = await _service.delete_industry_profile(profile_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="行业配置不存在")
    return {"success": True, "message": "已删除"}


# ── AI 生成 ──

@router.post("/industries/generate")
async def generate_industry_profile(body: AIGenerateRequest):
    """
    使用 AI 生成行业分析配置

    返回生成的配置（未保存），用户预览后可通过 POST /industries 保存
    """
    try:
        profile = await _service.generate_industry_profile_with_ai(
            body.industry,
            user_request=body.user_request or "",
            existing_profile=body.existing_profile,
        )
        return {"success": True, "data": profile}
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"❌ AI 生成行业配置失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"生成失败: {str(e)}")


# ── 行业列表（来源于 stock_basic_info） ──

@router.get("/industry-list")
async def get_industry_list():
    """
    获取数据库中所有股票的行业列表（来自 stock_basic_info.industry）

    用于前端行业配置时选择匹配的行业名称，确保与实际股票数据对齐
    """
    try:
        from app.core.database import get_mongo_db
        db = get_mongo_db()
        industries = await db.stock_basic_info.distinct("industry")
        # 过滤空值，排序
        industries = sorted([i for i in industries if i and i.strip()])
        return {"success": True, "data": industries, "total": len(industries)}
    except Exception as e:
        logger.error(f"获取行业列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取行业列表失败: {str(e)}")


# ── 个股配置（基础 CRUD） ──

@router.get("/stocks")
async def list_stock_profiles(industry: Optional[str] = Query(None)):
    """获取个股配置列表"""
    profiles = await _service.get_stock_profiles(industry=industry)
    return {"success": True, "data": profiles, "total": len(profiles)}


@router.get("/stocks/{stock_symbol}")
async def get_stock_profile_by_symbol(stock_symbol: str):
    """根据股票代码获取个股配置"""
    profile = await _service.get_stock_profile_by_symbol(stock_symbol)
    if not profile:
        raise HTTPException(status_code=404, detail="个股配置不存在")
    return {"success": True, "data": profile}

