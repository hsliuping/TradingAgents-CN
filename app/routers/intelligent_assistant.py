"""
智能助手 API 路由
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.routers.auth_db import get_current_user
from app.core.database import get_mongo_db
from app.schemas.intelligent_assistant import (
    AssistantThreadItem,
    AssistantThreadListResponse,
    AssistantThreadMessagesResponse,
    ChatRequest,
    ChatResponse,
    ConversationResponse,
    CreateAssistantThreadRequest,
    PlannedAnalysisResponse,
)
from app.services.intelligent_assistant_service import (
    chat_with_assistant,
    create_assistant_thread,
    get_assistant_conversation,
    get_assistant_thread_messages,
    get_or_create_assistant_thread,
    list_assistant_threads,
    clear_assistant_conversation,
    save_assistant_message,
)
from app.services.planned_analysis_service import PlannedAnalysisService
from motor.motor_asyncio import AsyncIOMotorDatabase

router = APIRouter(prefix="/api/assistant", tags=["assistant"])
logger = logging.getLogger(__name__)


@router.get("/conversation", response_model=ConversationResponse)
async def get_conversation(
    current_user=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
    conversation_id: Optional[str] = Query(None),
):
    """获取当前用户的智能助手会话历史"""
    user_id = str(current_user["id"])
    thread = await get_or_create_assistant_thread(db, user_id, conversation_id)
    messages = await get_assistant_conversation(db, user_id, thread["thread_id"])
    return ConversationResponse(messages=messages, conversation_id=thread["thread_id"])


@router.delete("/conversation")
async def clear_conversation(
    current_user=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
    conversation_id: Optional[str] = Query(None),
):
    """清空当前用户的智能助手会话"""
    user_id = str(current_user["id"])
    await clear_assistant_conversation(db, user_id, conversation_id)
    return {"success": True}


@router.get("/threads", response_model=AssistantThreadListResponse)
async def get_threads(
    current_user=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """获取当前用户的主题会话列表"""
    user_id = str(current_user["id"])
    items = await list_assistant_threads(db, user_id)
    return AssistantThreadListResponse(
        items=[AssistantThreadItem(**item) for item in items],
        total=len(items),
    )


@router.post("/threads", response_model=AssistantThreadItem)
async def create_thread(
    request: CreateAssistantThreadRequest,
    current_user=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """创建主题会话"""
    user_id = str(current_user["id"])
    item = await create_assistant_thread(db, user_id, request.title)
    return AssistantThreadItem(**item)


@router.get("/threads/{thread_id}/messages", response_model=AssistantThreadMessagesResponse)
async def get_thread_messages(
    thread_id: str,
    current_user=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """获取指定主题的消息列表"""
    user_id = str(current_user["id"])
    thread, messages = await get_assistant_thread_messages(db, user_id, thread_id)
    return AssistantThreadMessagesResponse(
        messages=messages,
        conversation_id=thread_id,
        thread=AssistantThreadItem(**thread),
    )


@router.delete("/threads/{thread_id}/messages")
async def clear_thread_messages(
    thread_id: str,
    current_user=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """清空指定主题的消息列表"""
    user_id = str(current_user["id"])
    await clear_assistant_conversation(db, user_id, thread_id)
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


@router.post("/planned-analysis", response_model=PlannedAnalysisResponse)
async def planned_analysis(
    request: ChatRequest,
    current_user=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """
    规划分析接口 — Plan-then-Execute 模式

    支持三级保障：种子流程匹配 → LLM 自主规划 → ReAct 回退。
    返回完整的分析计划、各步骤执行结果和综合回答。
    """
    if not request.message or not request.message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")

    user_id = str(current_user["id"])

    try:
        service = PlannedAnalysisService(db)
        result = await service.analyze(
            question=request.message.strip(),
            user_id=user_id,
            conversation_id=request.conversation_id,
        )

        # 持久化会话（与 ReAct 模式共享会话历史）
        if result.reply:
            try:
                await save_assistant_message(
                    db,
                    user_id=user_id,
                    user_content=request.message.strip(),
                    assistant_content=result.reply,
                    tools_used=result.tools_used or [],
                    conversation_id=request.conversation_id,
                )
            except Exception as e:
                logger.warning("[规划分析 API] 保存会话失败: %s", e)

        thread = await get_or_create_assistant_thread(db, user_id, request.conversation_id)

        return PlannedAnalysisResponse(
            reply=result.reply,
            tools_used=result.tools_used,
            data_refs=result.data_refs,
            conversation_id=thread["thread_id"],
            plan=result.plan.dict() if result.plan else None,
            step_results=[sr.dict() for sr in result.step_results] if result.step_results else None,
            source=result.source.value,
            supplemented=result.supplemented,
        )
    except Exception as e:
        logger.exception("[规划分析 API] 处理失败")
        raise HTTPException(status_code=500, detail=str(e))
