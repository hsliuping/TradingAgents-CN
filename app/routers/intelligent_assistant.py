"""
智能助手 API 路由
"""

import asyncio
import contextlib
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
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


# SSE 心跳间隔：必须小于前端 fetchSSE 的 90s 空闲超时
_SSE_HEARTBEAT_INTERVAL = 15


async def sse_stream_with_heartbeat(agen, heartbeat_interval: int = _SSE_HEARTBEAT_INTERVAL):
    """把异步生成器包装成带心跳的 SSE 事件流。

    ⚠️ 关键约束：心跳超时**绝不能取消底层生成器**。

    旧实现 `await asyncio.wait_for(gen.__anext__(), timeout=15)` 在超时取消时
    会把 CancelledError 注入生成器的挂起点，导致第一次超过 15s 的静默就把
    整条流杀死（最小复现实证：超时后第二次 ``__anext__()`` 直接抛
    StopAsyncIteration）。智能助手里长工具执行（估值 Excel：数据装配 +
    最多 3 次 LLM 规格生成，合法耗时 30-180s）正好命中，表现为流被静默掐断
    或前端等待到 90s 空闲超时后报"服务器长时间未响应"。

    正确模式：独立 pump 任务把生成器产出推进队列，``wait_for`` 只作用于
    ``queue.get()``——超时只丢弃一次队列等待，pump 任务与底层生成器
    完全不受影响，随后继续正常产出。

    生成器内部抛出的异常在这里转成 error 事件（与旧实现行为一致）。
    """
    import json as _json

    queue: "asyncio.Queue[object]" = asyncio.Queue()
    sentinel = object()

    async def _pump() -> None:
        try:
            async for chunk in agen:
                await queue.put(chunk)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - 转成 error 事件下发前端
            logger.exception("[智能助手 API·流式] 底层生成器异常")
            await queue.put(
                "event: error\n"
                f"data: {_json.dumps({'message': str(exc)}, ensure_ascii=False)}\n\n"
            )
        finally:
            await queue.put(sentinel)

    pump_task = asyncio.create_task(_pump())
    try:
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=heartbeat_interval)
            except asyncio.TimeoutError:
                # 队列为空（长工具执行等静默期）：只发心跳，pump 继续跑
                yield ": keepalive\n\n"
                continue
            if item is sentinel:
                break
            yield item
    finally:
        # 客户端断开或结束：停泵并关闭底层生成器（触发其内部 finally 清理）
        pump_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await pump_task
        await agen.aclose()


@router.post("/user-manual-index/rebuild")
async def rebuild_user_manual_index(
    current_user=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """重新初始化并重建用户手册向量索引。

    场景：系统启动时 Embedding API Key 未配置/错误导致用户手册索引构建失败
    （使用问答助手的语义检索不可用），用户在配置好 Key 后可调用此接口手动
    重建，无需重启后端。
    """
    from core.knowledge.user_manual_manager import UserManualManager

    manager = UserManualManager(db=db)

    # 1. 若向量后端不可用（启动时初始化失败），先重新初始化
    if not manager.available:
        ok = manager.reinit()
        if not ok:
            raise HTTPException(
                status_code=400,
                detail="向量检索后端重新初始化失败，请检查 Embedding API Key 配置（系统设置 -> LLM/Embedding），配置好后重试",
            )

    # 2. 强制重建索引（忽略签名比对，全量重建）
    result = await asyncio.to_thread(manager.ensure_indexed, True)

    if result.get("error"):
        raise HTTPException(status_code=400, detail=f"用户手册索引重建失败: {result['error']}")

    return {
        "success": True,
        "rebuilt": result.get("rebuilt", False),
        "sections_count": result.get("sections_count", 0),
        "manuals_count": result.get("manuals_count", 0),
        "signature": result.get("signature", ""),
    }


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

    async def event_generator():
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
        async for chunk in sse_stream_with_heartbeat(gen):
            yield chunk

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

    async def event_generator():
        gen = stream_planned_analysis_with_assistant(
            db=db,
            user_message=request.message.strip(),
            user_id=user_id,
            conversation_id=request.conversation_id,
            model=deep_model or quick_model,
            model_config_id=deep_model_config_id or quick_model_config_id,
        )
        async for chunk in sse_stream_with_heartbeat(gen):
            yield chunk

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/deliverables/{filename}")
async def download_assistant_deliverable(
    request: Request,
    filename: str,
    exp: Optional[int] = Query(None),
    sig: Optional[str] = Query(None),
    authorization: Optional[str] = Header(default=None),
):
    """下载智能助手生成的交付物文件（估值测算 / 表格导出 xlsx）。

    鉴权采用双通道：
    1. 签名链接（工具生成文件时附加 ?exp=&sig=，HMAC-SHA256 + 时效）——
       浏览器直接点击 markdown 下载链接的场景（不带 JWT 头）；
    2. 签名缺失/无效时回退 get_current_user（JWT 头 / Session Cookie），
       API 直接调用场景行为与原来一致。

    安全约束：文件名仅允许字母/数字/下划线/点/横线/中文/括号，且必须为
    .xlsx，限定在 data/deliverables 目录内，防路径穿越。
    """
    import re
    from pathlib import Path

    from fastapi.responses import FileResponse

    from core.deliverables.download_links import verify_deliverable_signature

    if not verify_deliverable_signature(filename, exp, sig):
        # 无有效签名 → 必须登录（失败时 get_current_user 抛 401）
        await get_current_user(request, authorization)

    # 允许中文与全角括号（AI 生成文件名含中文标题），禁止路径分隔符
    if (
        not re.fullmatch(r"[A-Za-z0-9_.\-\u4e00-\u9fff（）()]+", filename)
        or ".." in filename
        or not filename.lower().endswith(".xlsx")
    ):
        raise HTTPException(status_code=400, detail="非法的文件名")

    base_dir = (Path.cwd() / "data" / "deliverables").resolve()
    file_path = (base_dir / filename).resolve()
    if base_dir not in file_path.parents or not file_path.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")

    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
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
