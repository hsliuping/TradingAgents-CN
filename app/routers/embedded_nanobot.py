from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from starlette.responses import StreamingResponse

from app.core.database import get_mongo_db
from app.routers.auth_db import get_current_user
from app.schemas.embedded_nanobot import EmbeddedNanobotChatRequest, EmbeddedNanobotChatResponse, EmbeddedNanobotThreadArchiveResponse, EmbeddedNanobotThreadContextUpdateRequest, EmbeddedNanobotThreadListResponse, EmbeddedNanobotThreadMessagesResponse, EmbeddedNanobotThreadRestoreResponse
from app.services.embedded_nanobot_service import EmbeddedNanobotService

router = APIRouter(prefix="/api/embedded-nanobot", tags=["embedded-nanobot"])
logger = logging.getLogger(__name__)
WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
NANOBOT_EVENT_LOG_DIR = WORKSPACE_ROOT / "logs" / "embedded_nanobot_events"


def _append_nanobot_event_log(*, chat_id: str, session_key: str, event: str, payload: dict) -> None:
    """将前端流式事件追加写入 ndjson，方便刷新后排查。"""
    try:
        NANOBOT_EVENT_LOG_DIR.mkdir(parents=True, exist_ok=True)
        safe_chat_id = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in str(chat_id or session_key or "default"))[:120]
        log_path = NANOBOT_EVENT_LOG_DIR / f"{safe_chat_id}_{datetime.now().strftime('%Y%m%d')}.ndjson"
        record = {
            "ts": datetime.now().isoformat(timespec="milliseconds"),
            "event": event,
            "chat_id": chat_id,
            "session_key": session_key,
            "payload": payload,
        }
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except Exception as exc:
        logger.debug("[EmbeddedNanobotEventLog] write skipped: %s", exc)


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


@router.get("/threads", response_model=EmbeddedNanobotThreadListResponse)
async def list_embedded_nanobot_threads(
    limit: int = 50,
    archived_only: bool = False,
    current_user=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    user_id = str(current_user["id"])
    service = EmbeddedNanobotService(db=db, workspace=WORKSPACE_ROOT)
    items = await service.list_threads(user_id=user_id, limit=max(1, min(limit, 200)), archived_only=archived_only)
    return EmbeddedNanobotThreadListResponse(items=items, total=len(items))


@router.get("/threads/{thread_id}/messages", response_model=EmbeddedNanobotThreadMessagesResponse)
async def get_embedded_nanobot_thread_messages(
    thread_id: str,
    current_user=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    user_id = str(current_user["id"])
    service = EmbeddedNanobotService(db=db, workspace=WORKSPACE_ROOT)
    thread, messages = await service.get_thread_messages(user_id=user_id, thread_id=thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="会话不存在")
    return EmbeddedNanobotThreadMessagesResponse(thread=thread, messages=messages)


@router.delete("/threads/{thread_id}", response_model=EmbeddedNanobotThreadArchiveResponse)
async def delete_embedded_nanobot_thread(
    thread_id: str,
    current_user=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    user_id = str(current_user["id"])
    service = EmbeddedNanobotService(db=db, workspace=WORKSPACE_ROOT)
    result = await service.delete_thread(user_id=user_id, thread_id=thread_id)
    if not result.get("archived"):
        raise HTTPException(status_code=404, detail="会话不存在")
    return result


@router.post("/threads/{thread_id}/restore", response_model=EmbeddedNanobotThreadRestoreResponse)
async def restore_embedded_nanobot_thread(
    thread_id: str,
    current_user=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    user_id = str(current_user["id"])
    service = EmbeddedNanobotService(db=db, workspace=WORKSPACE_ROOT)
    result = await service.restore_thread(user_id=user_id, thread_id=thread_id)
    if not result.get("restored"):
        raise HTTPException(status_code=404, detail="会话不存在")
    return result


@router.put("/threads/{thread_id}/context", response_model=EmbeddedNanobotThreadMessagesResponse)
async def update_embedded_nanobot_thread_context(
    thread_id: str,
    request: EmbeddedNanobotThreadContextUpdateRequest,
    current_user=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    user_id = str(current_user["id"])
    service = EmbeddedNanobotService(db=db, workspace=WORKSPACE_ROOT)
    thread = await service.update_thread_context(
        user_id=user_id,
        thread_id=thread_id,
        session_key=request.session_key or thread_id,
        channel=request.channel,
        thread_context=request.thread_context.model_dump(exclude_none=True),
    )
    if not thread:
        raise HTTPException(status_code=400, detail="无法更新会话上下文")
    _, messages = await service.get_thread_messages(user_id=user_id, thread_id=thread_id)
    return EmbeddedNanobotThreadMessagesResponse(thread=thread, messages=messages)


@router.get("/status")
async def embedded_nanobot_status(current_user=Depends(get_current_user)):
    return {
        "enabled": True,
        "user_id": str(current_user["id"]),
        "workspace": str(WORKSPACE_ROOT),
    }


@router.post("/chat", response_model=EmbeddedNanobotChatResponse)
async def embedded_nanobot_chat(
    request: EmbeddedNanobotChatRequest,
    current_user=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    message = request.message.strip()
    display_message = str(request.display_message or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="消息不能为空")

    user_id = str(current_user["id"])
    session_key = request.session_key or f"embedded:user:{user_id}"
    chat_id = request.chat_id or session_key

    try:
        service = EmbeddedNanobotService(db=db, workspace=WORKSPACE_ROOT, preferred_model=request.model)
        result = await service.chat(
            user_message=message,
            display_message=display_message,
            session_key=session_key,
            user_id=user_id,
            current_thread_id=chat_id,
            channel=request.channel,
            chat_id=chat_id,
            media=request.media,
            skill_names=request.skill_names,
            thread_context=request.thread_context.model_dump(exclude_none=True) if request.thread_context else {},
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("[EmbeddedNanobot API] 对话失败")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return EmbeddedNanobotChatResponse(
        content=result.get("content", ""),
        session_key=session_key,
        thread_id=chat_id,
        stop_reason=result.get("stop_reason"),
        tools_used=result.get("tools_used", []),
        usage=result.get("usage", {}),
        tool_events=result.get("tool_events", []),
        thread_context=result.get("thread_context"),
    )


@router.post("/chat/stream")
async def embedded_nanobot_chat_stream(
    request: EmbeddedNanobotChatRequest,
    current_user=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    message = request.message.strip()
    display_message = str(request.display_message or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="消息不能为空")

    user_id = str(current_user["id"])
    session_key = request.session_key or f"embedded:user:{user_id}"
    chat_id = request.chat_id or session_key
    service = EmbeddedNanobotService(db=db, workspace=WORKSPACE_ROOT, preferred_model=request.model)

    async def event_stream():
        queue: asyncio.Queue[tuple[str, dict] | None] = asyncio.Queue()

        async def emit(event: str, payload: dict) -> None:
            payload_with_meta = {**payload, "chat_id": chat_id}
            _append_nanobot_event_log(
                chat_id=chat_id,
                session_key=session_key,
                event=event,
                payload=payload_with_meta,
            )
            await queue.put((event, payload_with_meta))

        await emit("started", {"message": "助手已开始处理请求", "session_key": session_key})

        async def on_progress(progress_message: str) -> None:
            await emit("progress", {"message": progress_message, "session_key": session_key})

        async def on_stream(delta: str) -> None:
            if delta:
                await emit("token", {"content": delta, "session_key": session_key})

        async def on_tool_event(tool_event: dict) -> None:
            await emit("tool_event", {**tool_event, "session_key": session_key})

        async def on_step_event(step_event: dict) -> None:
            await emit("step_event", {**step_event, "session_key": session_key})

        async def run_chat() -> None:
            try:
                result = await service.chat(
                    user_message=message,
                    display_message=display_message,
                    session_key=session_key,
                    user_id=user_id,
                    current_thread_id=chat_id,
                    channel=request.channel,
                    chat_id=chat_id,
                    media=request.media,
                    skill_names=request.skill_names,
                    thread_context=request.thread_context.model_dump(exclude_none=True) if request.thread_context else {},
                    on_progress=on_progress,
                    on_stream=on_stream,
                    on_tool_event=on_tool_event,
                    on_step_event=on_step_event,
                )
                await emit("done", {
                    "content": result.get("content", ""),
                    "session_key": session_key,
                    "thread_id": chat_id,
                    "stop_reason": result.get("stop_reason"),
                    "tools_used": result.get("tools_used", []),
                    "usage": result.get("usage", {}),
                    "tool_events": result.get("tool_events", []),
                    "thread_context": result.get("thread_context"),
                })
            except Exception as exc:
                logger.exception("[EmbeddedNanobot API] 流式对话失败")
                await emit("error", {"message": str(exc), "session_key": session_key})
            finally:
                await queue.put(None)

        task = asyncio.create_task(run_chat())
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                event, payload = item
                yield _sse_event(event, payload)
        finally:
            if not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

    import contextlib

    return StreamingResponse(event_stream(), media_type="text/event-stream")
