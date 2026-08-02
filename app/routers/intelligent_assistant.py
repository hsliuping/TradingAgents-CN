"""
智能助手 API 路由
"""

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.routers.auth_db import get_current_user
from app.core.database import get_mongo_db
from app.schemas.intelligent_assistant import (
    AssistantThreadAttachReportRequest,
    AssistantThreadAttachReportResponse,
    AssistantThreadItem,
    AssistantThreadListResponse,
    AssistantThreadMessagesResponse,
    AssistantThreadReportSearchResponse,
    ChatRequest,
    ChatResponse,
    ConversationResponse,
    CreateAssistantThreadRequest,
    PlannedAnalysisResponse,
    ThreadDeleteResponse,
    ThreadSummarizeResponse,
    AssistantThreadReportDetailResponse,
)
from app.services.intelligent_assistant_service import (
    chat_with_assistant,
    stream_chat_with_assistant,
    create_assistant_thread,
    delete_assistant_thread,
    get_assistant_conversation,
    get_assistant_thread_messages,
    get_or_create_assistant_thread,
    list_assistant_threads,
    clear_assistant_conversation,
    attach_existing_report_to_thread,
    save_assistant_message,
    search_assistant_attachable_reports,
    serialize_assistant_report_ref,
    summarize_assistant_thread,
    get_assistant_thread_report_detail,
)
from app.services.planned_analysis_service import PlannedAnalysisService
from app.services.planned_analysis_service import stream_planned_analysis_with_assistant
from motor.motor_asyncio import AsyncIOMotorDatabase

router = APIRouter(prefix="/api/assistant", tags=["assistant"])
logger = logging.getLogger(__name__)


def _resolve_requested_model(request: ChatRequest) -> tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    unified_model = (request.model or "").strip() or None
    unified_model_config_id = (request.model_config_id or "").strip() or None
    if unified_model:
        return unified_model, unified_model, unified_model_config_id, unified_model_config_id
    if unified_model_config_id:
        return None, None, unified_model_config_id, unified_model_config_id

    quick_model = (request.quick_model or "").strip() or None
    deep_model = (request.deep_model or "").strip() or None
    quick_model_config_id = (request.quick_model_config_id or "").strip() or None
    deep_model_config_id = (request.deep_model_config_id or "").strip() or None
    fallback_model = deep_model or quick_model
    fallback_config_id = deep_model_config_id or quick_model_config_id
    return (
        quick_model or fallback_model,
        deep_model or fallback_model,
        quick_model_config_id or fallback_config_id,
        deep_model_config_id or fallback_config_id,
    )


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
    try:
        item = await create_assistant_thread(db, user_id, request.title, request.parent_thread_id)
        return AssistantThreadItem(**item)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/threads/{thread_id}", response_model=ThreadDeleteResponse)
async def delete_thread(
    thread_id: str,
    current_user=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """删除指定主题及其子主题"""
    user_id = str(current_user["id"])
    try:
        deleted_ids = await delete_assistant_thread(db, user_id, thread_id)
        return ThreadDeleteResponse(success=True, deleted_thread_ids=deleted_ids)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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


@router.get(
    "/threads/{thread_id}/reports/{ref_type}/{report_key}",
    response_model=AssistantThreadReportDetailResponse,
)
async def get_thread_report_detail(
    thread_id: str,
    ref_type: str,
    report_key: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    try:
        detail = await get_assistant_thread_report_detail(
            db,
            str(current_user["id"]),
            thread_id,
            ref_type,
            report_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"获取关联报告详情失败: {exc}") from exc

    return AssistantThreadReportDetailResponse(detail=detail)


@router.get(
    "/threads/{thread_id}/report-candidates",
    response_model=AssistantThreadReportSearchResponse,
)
async def get_thread_report_candidates(
    thread_id: str,
    ref_type: str = Query("stock_report"),
    keyword: Optional[str] = Query(None),
    limit: int = Query(8, ge=1, le=20),
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    try:
        items = await search_assistant_attachable_reports(
            db,
            str(current_user["id"]),
            thread_id,
            ref_type=ref_type,
            keyword=keyword,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"搜索可关联报告失败: {exc}") from exc

    return AssistantThreadReportSearchResponse(
        items=[serialize_assistant_report_ref(item) for item in items],
        total=len(items),
    )


@router.post(
    "/threads/{thread_id}/report-links",
    response_model=AssistantThreadAttachReportResponse,
)
async def attach_thread_report(
    thread_id: str,
    request: AssistantThreadAttachReportRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    try:
        attached_ref = await attach_existing_report_to_thread(
            db,
            str(current_user["id"]),
            thread_id,
            request.ref_type,
            request.report_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"关联旧报告失败: {exc}") from exc

    return AssistantThreadAttachReportResponse(
        success=True,
        attached_ref=serialize_assistant_report_ref(attached_ref),
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


@router.post("/threads/{thread_id}/summarize", response_model=ThreadSummarizeResponse)
async def summarize_thread(
    thread_id: str,
    current_user=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """手动触发指定主题的摘要更新"""
    user_id = str(current_user["id"])
    summary = await summarize_assistant_thread(db, user_id, thread_id, summary_type="manual")
    return ThreadSummarizeResponse(conversation_id=thread_id, summary=summary)


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
    quick_model, deep_model, quick_model_config_id, deep_model_config_id = _resolve_requested_model(request)

    try:
        result = await chat_with_assistant(
            db=db,
            user_message=request.message.strip(),
            user_id=user_id,
            conversation_id=request.conversation_id,
            model=deep_model or quick_model,
            model_config_id=deep_model_config_id or quick_model_config_id,
            assistant_role=request.assistant_role,
            user_context=request.user_context,
        )
        return ChatResponse(**result)
    except Exception as e:
        logger.exception("[智能助手 API] 处理失败")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/stream")
async def assistant_chat_stream(
    request: ChatRequest,
    current_user=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """
    智能助手流式对话接口 (SSE)

    返回 Server-Sent Events 流，实时推送工具调用进度和回复内容。
    事件类型：tool_started / tool_completed / token / done / error
    """
    if not request.message or not request.message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")

    user_id = str(current_user["id"])
    quick_model, deep_model, quick_model_config_id, deep_model_config_id = _resolve_requested_model(request)

    _HEARTBEAT_INTERVAL = 15  # seconds

    async def event_generator():
        import json as _json
        gen = stream_chat_with_assistant(
            db=db,
            user_message=request.message.strip(),
            user_id=user_id,
            conversation_id=request.conversation_id,
            model=deep_model or quick_model,
            model_config_id=deep_model_config_id or quick_model_config_id,
            assistant_role=request.assistant_role,
            user_context=request.user_context,
        )
        try:
            while True:
                try:
                    chunk = await asyncio.wait_for(
                        gen.__anext__(), timeout=_HEARTBEAT_INTERVAL
                    )
                    yield chunk
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                except StopAsyncIteration:
                    break
        except Exception as e:
            logger.exception("[智能助手 API·流式] 处理失败")
            yield f"event: error\ndata: {_json.dumps({'message': str(e)}, ensure_ascii=False)}\n\n"
        finally:
            await gen.aclose()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


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
    quick_model, deep_model, quick_model_config_id, deep_model_config_id = _resolve_requested_model(request)

    try:
        service = PlannedAnalysisService(
            db,
            preferred_models={
                "model": deep_model or quick_model,
                "model_config_id": deep_model_config_id or quick_model_config_id,
            },
        )
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


@router.post("/planned-analysis/stream")
async def planned_analysis_stream(
    request: ChatRequest,
    current_user=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """规划分析流式接口 (SSE)。"""
    if not request.message or not request.message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")

    user_id = str(current_user["id"])
    quick_model, deep_model, quick_model_config_id, deep_model_config_id = _resolve_requested_model(request)
    _HEARTBEAT_INTERVAL = 15

    async def event_generator():
        import json as _json

        gen = stream_planned_analysis_with_assistant(
            db=db,
            user_message=request.message.strip(),
            user_id=user_id,
            conversation_id=request.conversation_id,
            model=deep_model or quick_model,
            model_config_id=deep_model_config_id or quick_model_config_id,
        )
        try:
            while True:
                try:
                    chunk = await asyncio.wait_for(gen.__anext__(), timeout=_HEARTBEAT_INTERVAL)
                    yield chunk
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                except StopAsyncIteration:
                    break
        except Exception as e:
            logger.exception("[规划分析 API·流式] 处理失败")
            yield f"event: error\ndata: {_json.dumps({'message': str(e)}, ensure_ascii=False)}\n\n"
        finally:
            await gen.aclose()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ============================================================
# v3.5.0 项4：智能助手 HITL（关键操作确认）API
# ============================================================


@router.get("/hitl/pending")
async def list_pending_hitl(
    current_user=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
    conversation_id: Optional[str] = Query(None),
):
    """列出当前用户待确认的关键操作（前端展示用）。"""
    from core.hitl.assistant_hitl import list_pending_for_user

    user_id = str(current_user.id) if hasattr(current_user, "id") else str(current_user.get("_id", ""))
    items = await list_pending_for_user(
        db,
        user_id=user_id,
        conversation_id=conversation_id,
    )
    return {"items": items, "count": len(items)}


@router.post("/hitl/{pending_id}/confirm")
async def confirm_hitl(
    pending_id: str,
    current_user=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """确认执行待确认的关键操作。"""
    from core.hitl.assistant_hitl import confirm_pending

    user_id = str(current_user.id) if hasattr(current_user, "id") else str(current_user.get("_id", ""))
    result = await confirm_pending(db, pending_id=pending_id, user_id=user_id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "确认失败"))
    return result


@router.post("/hitl/{pending_id}/reject")
async def reject_hitl(
    pending_id: str,
    current_user=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """拒绝执行待确认的关键操作。"""
    from core.hitl.assistant_hitl import reject_pending

    user_id = str(current_user.id) if hasattr(current_user, "id") else str(current_user.get("_id", ""))
    result = await reject_pending(db, pending_id=pending_id, user_id=user_id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "拒绝失败"))
    return result
