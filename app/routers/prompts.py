"""
自定义提示词管理（Mock 版）
提供模板的查询、更新与重置，使用内存存储。
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from datetime import datetime

from app.routers.auth_db import get_current_user


class PromptTemplate(BaseModel):
    agent: str = Field(..., description="智能体名称，如 fundamentals/news/social")
    system_prompt: str = Field(..., description="System Prompt 模板")
    user_prompt: Optional[str] = Field(None, description="可选的用户提示模板")
    variables: List[str] = Field(default_factory=list, description="可用占位符列表")
    updated_at: datetime = Field(default_factory=datetime.utcnow)


router = APIRouter(prefix="/api/prompts", tags=["prompts"])

# 内存模板
_default_templates: Dict[str, PromptTemplate] = {
    "fundamentals": PromptTemplate(
        agent="fundamentals",
        system_prompt="你是一位专业的股票基本面分析师，必须基于工具数据输出结论。",
        user_prompt=None,
        variables=["{ticker}", "{market}", "{current_date}"],
    ),
    "news": PromptTemplate(
        agent="news",
        system_prompt="你是一位财经新闻分析师，先获取新闻再给出影响评估。",
        user_prompt=None,
        variables=["{ticker}", "{current_date}"],
    ),
}

_templates: Dict[str, PromptTemplate] = dict(_default_templates)


@router.get("/templates")
async def list_templates(user: dict = Depends(get_current_user)) -> Dict[str, Any]:
    return {"success": True, "data": list(_templates.values()), "message": "ok"}


@router.get("/templates/{agent}")
async def get_template(agent: str, user: dict = Depends(get_current_user)) -> Dict[str, Any]:
    tpl = _templates.get(agent)
    if not tpl:
        raise HTTPException(status_code=404, detail="template not found")
    return {"success": True, "data": tpl, "message": "ok"}


@router.put("/templates/{agent}")
async def update_template(
    agent: str,
    payload: PromptTemplate,
    user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    _templates[agent] = payload.model_copy(update={"agent": agent, "updated_at": datetime.utcnow()})
    return {"success": True, "data": _templates[agent], "message": "updated"}


@router.post("/templates/{agent}/reset")
async def reset_template(agent: str, user: dict = Depends(get_current_user)) -> Dict[str, Any]:
    tpl = _default_templates.get(agent)
    if not tpl:
        raise HTTPException(status_code=404, detail="template not found")
    _templates[agent] = tpl.model_copy(update={"updated_at": datetime.utcnow()})
    return {"success": True, "data": _templates[agent], "message": "reset"}
