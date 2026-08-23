"""
智能筛选 API 路由

复用 ChatRequest schema，新增筛选专用的响应模型。
"""

import json
import logging
import os
from datetime import datetime

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional

from app.core.database import get_mongo_db
from app.routers.auth_db import get_current_user
from app.routers.websocket_notifications import _authenticate_websocket
from app.services.auth_service import AuthService
from app.schemas.intelligent_assistant import ChatRequest
from app.schemas.intelligent_screening import (
    ScreeningChatResponse,
    ScreeningConversationResponse,
    ScreeningConversationListResponse,
    ScreeningConversationSummary,
    ScreeningMessageItem,
)
from app.services.intelligent_screening_service import IntelligentScreeningService
from app.services.user_service import UserService

logger = logging.getLogger(__name__)

# 配置：是否使用V2版本
USE_V2 = os.environ.get("SCREENING_USE_V2", "true").lower() in ("true", "1", "yes")

# 延迟导入V2服务（避免循环依赖）
def get_screening_service(db: AsyncIOMotorDatabase):
    if USE_V2:
        try:
            from app.services.intelligent_screening_v2 import IntelligentScreeningServiceV2
            logger.info("[智能筛选] 使用V2版本（基于意图理解）")
            return IntelligentScreeningServiceV2(db)
        except Exception as e:
            logger.warning(f"[智能筛选] V2版本加载失败: {e}，回退到V1")

    logger.info("[智能筛选] 使用V1版本（关键词匹配）")
    return IntelligentScreeningService(db)


router = APIRouter(prefix="/api/screening/intelligent")
user_service = UserService()


@router.post("/chat", response_model=ScreeningChatResponse, summary="智能筛选对话")
async def chat(
    req: ChatRequest,
    user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """
    处理用户的选股对话请求。

    - 新需求：返回 phase="confirmation"，包含需求分析和改进建议
    - 确认/追问：返回 phase="result"，包含推荐股票
    """
    user_id = str(user.get("_id", user.get("id", "")))
    service = get_screening_service(db)
    result = await service.chat(user_id, req.message, conversation_id=req.conversation_id)
    return result


@router.websocket("/ws")
async def websocket_chat(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
):
    """智能筛选 WebSocket 端点，按阶段与工具调用实时推送进度。

    认证方式：
    - JWT 模式: ws://.../ws?token=<jwt_token>
    - 京东云模式: ws://.../ws （无需 token，由网关注入 Basic Auth）
    """
    user_id = await _authenticate_websocket(websocket, token)
    if not user_id:
        await websocket.close(code=1008, reason="Unauthorized")
        return

    await websocket.accept()
    db = get_mongo_db()

    await websocket.send_json({
        "type": "connected",
        "data": {
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat(),
            "message": "智能筛选流式连接已建立",
        },
    })

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "data": {"message": "消息格式错误，需为 JSON"},
                })
                continue

            msg_type = payload.get("type")
            if msg_type == "ping":
                await websocket.send_json({
                    "type": "pong",
                    "data": {"timestamp": datetime.utcnow().isoformat()},
                })
                continue

            if msg_type != "chat":
                await websocket.send_json({
                    "type": "error",
                    "data": {"message": "不支持的消息类型"},
                })
                continue

            message = str(payload.get("message") or "").strip()
            conversation_id = payload.get("conversation_id")
            if not message:
                await websocket.send_json({
                    "type": "error",
                    "data": {"message": "消息不能为空"},
                })
                continue

            service = get_screening_service(db)

            async def progress_sender(event: dict):
                await websocket.send_json({"type": "progress", "data": event})

            await websocket.send_json({
                "type": "started",
                "data": {
                    "message": "已收到筛选请求，开始处理",
                    "timestamp": datetime.utcnow().isoformat(),
                },
            })

            try:
                result = await service.chat(
                    user_id,
                    message,
                    conversation_id=conversation_id,
                    progress_callback=progress_sender,
                )
                await websocket.send_json({"type": "final", "data": result})
            except Exception as e:
                logger.exception("[智能筛选WS] 处理失败")
                await websocket.send_json({
                    "type": "error",
                    "data": {
                        "message": f"处理失败：{str(e)}",
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                })
    except WebSocketDisconnect:
        logger.info("[智能筛选WS] 客户端断开: user=%s", user_id)


@router.get("/conversation", response_model=ScreeningConversationResponse, summary="获取筛选对话历史")
async def get_conversation(
    conversation_id: str | None = Query(None),
    user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """获取当前用户的智能筛选对话历史"""
    user_id = str(user.get("_id", user.get("id", "")))
    service = get_screening_service(db)
    resolved_conversation_id, messages = await service.get_conversation(user_id, conversation_id)
    items = []
    for m in messages:
        items.append(ScreeningMessageItem(
            role=m.get("role", ""),
            content=m.get("content", ""),
            tools_used=m.get("tools_used"),
            stocks=m.get("stocks"),
            phase=m.get("phase"),
            is_fallback=m.get("is_fallback"),
        ))
    return ScreeningConversationResponse(conversation_id=resolved_conversation_id, messages=items)


@router.get("/conversations", response_model=ScreeningConversationListResponse, summary="获取筛选历史会话列表")
async def list_conversations(
    user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """获取当前用户的智能筛选历史会话列表"""
    user_id = str(user.get("_id", user.get("id", "")))
    service = get_screening_service(db)
    conversations = await service.list_conversations(user_id)
    items = [ScreeningConversationSummary(**item) for item in conversations]
    return ScreeningConversationListResponse(items=items)


@router.delete("/conversation", summary="清空筛选对话历史")
async def clear_conversation(
    conversation_id: str | None = Query(None),
    user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """清空当前用户的智能筛选对话历史"""
    user_id = str(user.get("_id", user.get("id", "")))
    service = get_screening_service(db)
    await service.clear_conversation(user_id, conversation_id)
    return {"message": "已清空智能筛选对话"}

