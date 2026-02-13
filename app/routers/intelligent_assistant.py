"""
智能助手 API 路由
"""

import logging
from fastapi import APIRouter, Depends, HTTPException

from app.routers.auth_db import get_current_user
from app.core.database import get_mongo_db
from app.schemas.intelligent_assistant import ChatRequest, ChatResponse, ConversationResponse
from app.services.intelligent_assistant_service import (
    chat_with_assistant,
    get_assistant_conversation,
    clear_assistant_conversation,
)
from motor.motor_asyncio import AsyncIOMotorDatabase

router = APIRouter(prefix="/api/assistant", tags=["assistant"])
logger = logging.getLogger(__name__)


@router.get("/conversation", response_model=ConversationResponse)
async def get_conversation(
    current_user=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """获取当前用户的智能助手会话历史"""
    user_id = str(current_user["id"])
    messages = await get_assistant_conversation(db, user_id)
    return ConversationResponse(messages=messages)


@router.delete("/conversation")
async def clear_conversation(
    current_user=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """清空当前用户的智能助手会话"""
    user_id = str(current_user["id"])
    await clear_assistant_conversation(db, user_id)
    return {"success": True}


@router.post("/chat", response_model=ChatResponse)
async def assistant_chat(
    request: ChatRequest,
    current_user=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """
    智能助手对话接口
    
    支持自然语言提问，助手会自主选择工具获取数据并生成回答。
    对话将持久化，下次进入可查看历史。
    """
    if not request.message or not request.message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")

    user_id = str(current_user["id"])

    try:
        result = await chat_with_assistant(
            db=db,
            user_message=request.message.strip(),
            user_id=user_id,
            conversation_id=request.conversation_id,
        )
        return ChatResponse(**result)
    except Exception as e:
        logger.exception("[智能助手 API] 处理失败")
        raise HTTPException(status_code=500, detail=str(e))
