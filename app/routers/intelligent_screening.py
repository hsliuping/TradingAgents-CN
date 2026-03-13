"""
智能筛选 API 路由

复用 ChatRequest schema，新增筛选专用的响应模型。
"""

import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_mongo_db
from app.routers.auth_db import get_current_user
from app.services.auth_service import AuthService
from app.schemas.intelligent_assistant import ChatRequest
from app.schemas.intelligent_screening import (
    ScreeningChatResponse,
    ScreeningConversationResponse,
    ScreeningMessageItem,
)
from app.services.intelligent_screening_service import IntelligentScreeningService
from app.services.user_service import UserService

logger = logging.getLogger(__name__)

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
    - 确认/追问：返回 phase="result"，包含 5 只推荐股票
    """
    user_id = str(user.get("_id", user.get("id", "")))
    service = IntelligentScreeningService(db)
    result = await service.chat(user_id, req.message)
    return result


@router.websocket("/ws")
async def websocket_chat(
    websocket: WebSocket,
    token: str = Query(...),
):
    """智能筛选 WebSocket 端点，按阶段与工具调用实时推送进度。"""
    token_data = AuthService.verify_token(token)
    if not token_data:
        await websocket.close(code=1008, reason="Unauthorized")
        return

    user = await user_service.get_user_by_username(token_data.sub)
    if not user or not user.is_active:
        await websocket.close(code=1008, reason="Unauthorized")
        return

    await websocket.accept()
    user_id = str(user.id)
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
            if not message:
                await websocket.send_json({
                    "type": "error",
                    "data": {"message": "消息不能为空"},
                })
                continue

            service = IntelligentScreeningService(db)

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
                result = await service.chat(user_id, message, progress_callback=progress_sender)
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
            is_fallback=m.get("is_fallback"),
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

