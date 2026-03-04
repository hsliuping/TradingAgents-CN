"""
智能筛选 API 路由

复用 ChatRequest schema，新增筛选专用的响应模型。
"""

import logging

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_mongo_db
from app.routers.auth_db import get_current_user
from app.schemas.intelligent_assistant import ChatRequest
from app.schemas.intelligent_screening import (
    ScreeningChatResponse,
    ScreeningConversationResponse,
    ScreeningMessageItem,
)
from app.services.intelligent_screening_service import IntelligentScreeningService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/screening/intelligent")


@router.post("/chat", response_model=ScreeningChatResponse, summary="智能筛选对话")
async def chat(
    req: ChatRequest,
    user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """
    处理用户的选股对话请求。

    - 新需求：返回 phase="confirmation"，包含需求分析和改进建议
    - 确认/追问：返回 phase="result"，包含 5 只推荐股票
    """
    user_id = str(user.get("_id", user.get("id", "")))
    service = IntelligentScreeningService(db)
    result = await service.chat(user_id, req.message)
    return result


@router.get("/conversation", response_model=ScreeningConversationResponse, summary="获取筛选对话历史")
async def get_conversation(
    user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """获取当前用户的智能筛选对话历史"""
    user_id = str(user.get("_id", user.get("id", "")))
    service = IntelligentScreeningService(db)
    messages = await service.get_conversation(user_id)
    items = []
    for m in messages:
        items.append(ScreeningMessageItem(
            role=m.get("role", ""),
            content=m.get("content", ""),
            tools_used=m.get("tools_used"),
            stocks=m.get("stocks"),
            phase=m.get("phase"),
        ))
    return ScreeningConversationResponse(messages=items)


@router.delete("/conversation", summary="清空筛选对话历史")
async def clear_conversation(
    user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """清空当前用户的智能筛选对话历史"""
    user_id = str(user.get("_id", user.get("id", "")))
    service = IntelligentScreeningService(db)
    await service.clear_conversation(user_id)
    return {"message": "已清空智能筛选对话"}

