"""
智能助手 API 路由
"""

import logging
from fastapi import APIRouter, Depends, HTTPException

from app.routers.auth_db import get_current_user
from app.core.database import get_mongo_db
from app.schemas.intelligent_assistant import ChatRequest, ChatResponse
from app.services.intelligent_assistant_service import chat_with_assistant
from motor.motor_asyncio import AsyncIOMotorDatabase

router = APIRouter(prefix="/api/assistant", tags=["assistant"])
logger = logging.getLogger(__name__)


@router.post("/chat", response_model=ChatResponse)
async def assistant_chat(
    request: ChatRequest,
    current_user=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """
    智能助手对话接口
    
    支持自然语言提问，助手会自主选择工具获取数据并生成回答。
    """
    if not request.message or not request.message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")

    try:
        result = await chat_with_assistant(
            db=db,
            user_message=request.message.strip(),
            conversation_id=request.conversation_id,
        )
        return ChatResponse(**result)
    except Exception as e:
        logger.exception("[智能助手 API] 处理失败")
        raise HTTPException(status_code=500, detail=str(e))
