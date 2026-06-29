from __future__ import annotations

import asyncio
import logging
import re
import uuid
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import ClassVar
from typing import Any

from core.embedded_nanobot.runtime import EmbeddedNanobotRuntime
from core.tools.context import get_current_assistant_thread_context, set_current_assistant_thread_context, set_current_assistant_thread_id, set_current_user_id


logger = logging.getLogger(__name__)

EMBEDDED_NANOBOT_THREAD_COLLECTION = "embedded_nanobot_threads"
EMBEDDED_NANOBOT_MESSAGE_COLLECTION = "embedded_nanobot_thread_messages"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _build_thread_title(value: str | None, limit: int = 28) -> str:
    text = _normalize_text(value)
    if not text:
        return "助手会话"
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def _normalize_thread_context(value: dict[str, Any] | None) -> dict[str, Any]:
    raw = dict(value or {})
    normalized_symbol = str(raw.get("symbol") or raw.get("stock_symbol") or "").strip() or None
    normalized_object_type = str(raw.get("object_type") or "").strip() or None
    normalized_object_key = str(raw.get("object_key") or "").strip() or None
    if not normalized_object_key and normalized_symbol:
        normalized_object_key = normalized_symbol
    if not normalized_object_type and normalized_object_key == normalized_symbol and normalized_symbol:
        normalized_object_type = "stock"
    normalized = {
        "spec_id": str(raw.get("spec_id") or "").strip() or None,
        "spec_name": str(raw.get("spec_name") or "").strip() or None,
        "workshop_session_id": str(raw.get("workshop_session_id") or "").strip() or None,
        "version_id": str(raw.get("version_id") or "").strip() or None,
        "version_status": str(raw.get("version_status") or "").strip() or None,
        "workflow_id": str(raw.get("workflow_id") or "").strip() or None,
        "node_id": str(raw.get("node_id") or "").strip() or None,
        "preference_id": str(raw.get("preference_id") or "").strip() or None,
        "debug_template_id": str(raw.get("debug_template_id") or "").strip() or None,
        "symbol": normalized_symbol,
        "object_type": normalized_object_type,
        "object_key": normalized_object_key,
    }
    return {key: item for key, item in normalized.items() if item is not None}


class EmbeddedNanobotService:
    _runtime_cache: ClassVar[dict[tuple[str, str | None], EmbeddedNanobotRuntime]] = {}
    _runtime_locks: ClassVar[dict[tuple[str, str | None], asyncio.Lock]] = {}

    def __init__(self, db, workspace: str | Path, preferred_model: str | None = None):
        self._db = db
        self._workspace = Path(workspace)
        self._preferred_model = preferred_model

    async def _get_or_create_thread(
        self,
        *,
        user_id: str,
        thread_id: str,
        session_key: str,
        channel: str,
        title_hint: str,
    ) -> dict[str, Any]:
        now = _now_utc()
        thread_doc = {
            "thread_id": thread_id,
            "user_id": user_id,
            "title": _build_thread_title(title_hint),
            "archived": False,
            "message_count": 0,
            "last_user_message": "",
            "current_summary": {
                "abstract": "",
            },
            "session_key": session_key,
            "channel": channel,
            "thread_context": {},
            "created_at": now,
            "updated_at": now,
        }
        await self._db[EMBEDDED_NANOBOT_THREAD_COLLECTION].update_one(
            {"user_id": user_id, "thread_id": thread_id},
            {"$setOnInsert": thread_doc},
            upsert=True,
        )
        return await self._db[EMBEDDED_NANOBOT_THREAD_COLLECTION].find_one({"user_id": user_id, "thread_id": thread_id}) or thread_doc

    async def _append_thread_message(
        self,
        *,
        user_id: str,
        thread_id: str,
        session_key: str,
        role: str,
        content: str,
        channel: str,
        raw_content: str | None = None,
        tools_used: list[str] | None = None,
        stop_reason: str | None = None,
        usage: dict[str, int] | None = None,
        tool_events: list[dict[str, Any]] | None = None,
    ) -> None:
        document = {
            "message_id": f"nanobot_msg_{uuid.uuid4().hex}",
            "thread_id": thread_id,
            "user_id": user_id,
            "session_key": session_key,
            "channel": channel,
            "role": role,
            "content": content,
            "tools_used": tools_used or [],
            "stop_reason": stop_reason,
            "usage": usage or {},
            "tool_events": tool_events or [],
            "created_at": _now_utc(),
        }
        clean_raw_content = str(raw_content or "").strip()
        if clean_raw_content:
            document["raw_content"] = clean_raw_content
        await self._db[EMBEDDED_NANOBOT_MESSAGE_COLLECTION].insert_one(document)

    async def persist_chat_turn(
        self,
        *,
        user_id: str,
        thread_id: str,
        session_key: str,
        channel: str,
        user_content: str,
        user_display_content: str | None = None,
        assistant_content: str,
        tools_used: list[str] | None = None,
        stop_reason: str | None = None,
        usage: dict[str, int] | None = None,
        tool_events: list[dict[str, Any]] | None = None,
        thread_context: dict[str, Any] | None = None,
    ) -> None:
        clean_user_raw_content = str(user_content or "").strip()
        clean_user_content = str(user_display_content or clean_user_raw_content or "").strip()
        clean_assistant_content = str(assistant_content or "").strip()
        clean_thread_id = str(thread_id or session_key or "").strip()
        clean_session_key = str(session_key or clean_thread_id or "").strip()
        clean_channel = str(channel or "embedded").strip() or "embedded"
        clean_thread_context = _normalize_thread_context(thread_context)
        if not user_id or not clean_thread_id:
            return

        inserted_count = 0
        await self._get_or_create_thread(
            user_id=user_id,
            thread_id=clean_thread_id,
            session_key=clean_session_key,
            channel=clean_channel,
            title_hint=clean_user_content,
        )

        if clean_user_content:
            await self._append_thread_message(
                user_id=user_id,
                thread_id=clean_thread_id,
                session_key=clean_session_key,
                role="user",
                content=clean_user_content,
                channel=clean_channel,
                raw_content=clean_user_raw_content if clean_user_raw_content != clean_user_content else None,
            )
            inserted_count += 1

        if clean_assistant_content or tools_used or tool_events or stop_reason:
            await self._append_thread_message(
                user_id=user_id,
                thread_id=clean_thread_id,
                session_key=clean_session_key,
                role="assistant",
                content=clean_assistant_content,
                channel=clean_channel,
                tools_used=tools_used,
                stop_reason=stop_reason,
                usage=usage,
                tool_events=tool_events,
            )
            inserted_count += 1

        updates: dict[str, Any] = {
            "updated_at": _now_utc(),
            "session_key": clean_session_key,
            "channel": clean_channel,
            "archived": False,
        }
        if clean_thread_context:
            updates["thread_context"] = clean_thread_context
        if clean_user_content:
            updates["last_user_message"] = clean_user_content[:200]
            updates["title"] = _build_thread_title(clean_user_content)
        if clean_assistant_content:
            updates["current_summary.abstract"] = clean_assistant_content[:120]

        await self._db[EMBEDDED_NANOBOT_THREAD_COLLECTION].update_one(
            {"user_id": user_id, "thread_id": clean_thread_id},
            {
                "$set": updates,
                "$inc": {"message_count": inserted_count},
            },
        )

    async def update_thread_context(
        self,
        *,
        user_id: str,
        thread_id: str,
        session_key: str,
        channel: str,
        thread_context: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        clean_thread_id = str(thread_id or session_key or "").strip()
        clean_session_key = str(session_key or clean_thread_id or "").strip()
        clean_channel = str(channel or "embedded").strip() or "embedded"
        clean_thread_context = _normalize_thread_context(thread_context)
        if not user_id or not clean_thread_id:
            return None

        existing_thread = await self._get_or_create_thread(
            user_id=user_id,
            thread_id=clean_thread_id,
            session_key=clean_session_key,
            channel=clean_channel,
            title_hint=(clean_thread_context.get("spec_name") or "助手会话"),
        )
        updates: dict[str, Any] = {
            "updated_at": _now_utc(),
            "session_key": clean_session_key,
            "channel": clean_channel,
            "archived": False,
            "thread_context": clean_thread_context,
        }
        if clean_thread_context.get("spec_name") and not existing_thread.get("message_count"):
            updates["title"] = _build_thread_title(clean_thread_context.get("spec_name"))

        await self._db[EMBEDDED_NANOBOT_THREAD_COLLECTION].update_one(
            {"user_id": user_id, "thread_id": clean_thread_id},
            {"$set": updates},
        )
        return await self._db[EMBEDDED_NANOBOT_THREAD_COLLECTION].find_one({"user_id": user_id, "thread_id": clean_thread_id})

    async def list_threads(self, user_id: str, limit: int = 50, archived_only: bool = False) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        query: dict[str, Any] = {"user_id": user_id}
        if archived_only:
            query["archived"] = True
        else:
            query["archived"] = {"$ne": True}
        cursor = self._db[EMBEDDED_NANOBOT_THREAD_COLLECTION].find(query).sort("updated_at", -1).limit(limit)
        async for doc in cursor:
            updated_at = doc.get("updated_at")
            created_at = doc.get("created_at")
            items.append({
                "thread_id": doc.get("thread_id", ""),
                "title": doc.get("title") or "助手会话",
                "session_key": doc.get("session_key") or doc.get("thread_id") or "",
                "channel": doc.get("channel") or "embedded",
                "archived": bool(doc.get("archived", False)),
                "message_count": int(doc.get("message_count", 0)),
                "last_user_message": doc.get("last_user_message", ""),
                "summary": (doc.get("current_summary") or {}).get("abstract", ""),
                "created_at": created_at.isoformat() if isinstance(created_at, datetime) else created_at,
                "updated_at": updated_at.isoformat() if isinstance(updated_at, datetime) else updated_at,
                "thread_context": _normalize_thread_context(doc.get("thread_context") or {}),
            })
        return items

    async def restore_thread(self, user_id: str, thread_id: str) -> dict[str, Any]:
        clean_thread_id = str(thread_id or "").strip()
        if not clean_thread_id:
            return {"restored": False, "thread_id": clean_thread_id}

        thread = await self._db[EMBEDDED_NANOBOT_THREAD_COLLECTION].find_one({
            "user_id": user_id,
            "thread_id": clean_thread_id,
        })
        if not thread:
            return {"restored": False, "thread_id": clean_thread_id}

        if thread.get("archived") is not True:
            return {"restored": True, "thread_id": clean_thread_id, "archived": False}

        restored_thread = await self._db[EMBEDDED_NANOBOT_THREAD_COLLECTION].update_one({
            "user_id": user_id,
            "thread_id": clean_thread_id,
        }, {
            "$set": {
                "archived": False,
                "updated_at": _now_utc(),
            },
        })
        return {
            "restored": restored_thread.modified_count > 0,
            "thread_id": clean_thread_id,
            "archived": False,
        }

    async def get_thread_messages(self, user_id: str, thread_id: str) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        clean_thread_id = str(thread_id or "").strip()
        if not clean_thread_id:
            return None, []

        thread = await self._db[EMBEDDED_NANOBOT_THREAD_COLLECTION].find_one({
            "user_id": user_id,
            "thread_id": clean_thread_id,
        })
        if not thread:
            return None, []

        messages: list[dict[str, Any]] = []
        cursor = self._db[EMBEDDED_NANOBOT_MESSAGE_COLLECTION].find({
            "user_id": user_id,
            "thread_id": clean_thread_id,
        }).sort("created_at", 1)
        async for doc in cursor:
            created_at = doc.get("created_at")
            messages.append({
                "message_id": doc.get("message_id", ""),
                "role": doc.get("role", "assistant"),
                "content": doc.get("content", ""),
                "tools_used": doc.get("tools_used") or [],
                "stop_reason": doc.get("stop_reason"),
                "usage": doc.get("usage") or {},
                "tool_events": doc.get("tool_events") or [],
                "created_at": created_at.isoformat() if isinstance(created_at, datetime) else created_at,
            })

        updated_at = thread.get("updated_at")
        created_at = thread.get("created_at")
        thread_item = {
            "thread_id": thread.get("thread_id", ""),
            "title": thread.get("title") or "助手会话",
            "session_key": thread.get("session_key") or thread.get("thread_id") or "",
            "channel": thread.get("channel") or "embedded",
            "archived": bool(thread.get("archived", False)),
            "message_count": int(thread.get("message_count", 0)),
            "last_user_message": thread.get("last_user_message", ""),
            "summary": (thread.get("current_summary") or {}).get("abstract", ""),
            "created_at": created_at.isoformat() if isinstance(created_at, datetime) else created_at,
            "updated_at": updated_at.isoformat() if isinstance(updated_at, datetime) else updated_at,
            "thread_context": _normalize_thread_context(thread.get("thread_context") or {}),
        }
        return thread_item, messages

    async def delete_thread(self, user_id: str, thread_id: str) -> dict[str, Any]:
        clean_thread_id = str(thread_id or "").strip()
        if not clean_thread_id:
            return {"archived": False, "thread_id": clean_thread_id, "deleted_messages": 0}

        thread = await self._db[EMBEDDED_NANOBOT_THREAD_COLLECTION].find_one({
            "user_id": user_id,
            "thread_id": clean_thread_id,
        })
        if not thread:
            return {"archived": False, "thread_id": clean_thread_id, "deleted_messages": 0}

        if thread.get("archived") is True:
            return {
                "archived": True,
                "thread_id": clean_thread_id,
                "deleted_messages": 0,
            }

        archived_thread = await self._db[EMBEDDED_NANOBOT_THREAD_COLLECTION].update_one({
            "user_id": user_id,
            "thread_id": clean_thread_id,
        }, {
            "$set": {
                "archived": True,
                "updated_at": _now_utc(),
            },
        })
        return {
            "archived": archived_thread.modified_count > 0,
            "thread_id": clean_thread_id,
            "deleted_messages": 0,
        }

    def _cache_key(self) -> tuple[str, str | None]:
        return (str(self._workspace.resolve()), self._preferred_model)

    async def get_runtime(self) -> EmbeddedNanobotRuntime:
        cache_key = self._cache_key()
        cached = self._runtime_cache.get(cache_key)
        if cached is not None:
            return cached

        lock = self._runtime_locks.setdefault(cache_key, asyncio.Lock())
        async with lock:
            cached = self._runtime_cache.get(cache_key)
            if cached is not None:
                return cached
            runtime = await EmbeddedNanobotRuntime.from_database(
                self._db,
                workspace=self._workspace,
                preferred_model=self._preferred_model,
                restrict_to_workspace=False,
            )
            self._runtime_cache[cache_key] = runtime
            return runtime

    async def chat(
        self,
        user_message: str,
        display_message: str | None = None,
        session_key: str = "embedded:default",
        user_id: str | None = None,
        current_thread_id: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        runtime = await self.get_runtime()
        await runtime.sync_tradingagents_capabilities(self._db)
        runtime_kwargs = dict(kwargs)
        thread_context = runtime_kwargs.pop("thread_context", None) or {}

        user_token = set_current_user_id(user_id) if user_id else None
        thread_token = set_current_assistant_thread_id(current_thread_id) if current_thread_id else None
        thread_context_token = set_current_assistant_thread_context(thread_context)
        logger.info(
            "[EmbeddedNanobot][ThreadContext] chat thread_id=%s session_key=%s channel=%s spec_id=%s version_id=%s workshop_session_id=%s spec_name=%s",
            current_thread_id or kwargs.get("chat_id") or session_key,
            session_key,
            kwargs.get("channel") or "embedded",
            thread_context.get("spec_id"),
            thread_context.get("version_id"),
            thread_context.get("workshop_session_id"),
            thread_context.get("spec_name"),
        )
        try:
            result = await runtime.handle_message(
                user_message=user_message,
                session_key=session_key,
                thread_context=thread_context,
                user_id=user_id,
                thread_id=current_thread_id or kwargs.get("chat_id") or session_key,
                **runtime_kwargs,
            )
            if user_id:
                try:
                    # 工具执行期间可能更新了 contextvar 中的 intent context，持久化时必须使用最新上下文
                    latest_thread_context = get_current_assistant_thread_context() or thread_context
                    if latest_thread_context != thread_context:
                        logger.info(
                            "[EmbeddedNanobot][IntentContext] persist updated thread_context thread_id=%s spec_id=%s intent=%s",
                            current_thread_id or kwargs.get("chat_id") or session_key,
                            latest_thread_context.get("spec_id"),
                            latest_thread_context.get("intent"),
                        )
                    await self.persist_chat_turn(
                        user_id=user_id,
                        thread_id=current_thread_id or kwargs.get("chat_id") or session_key,
                        session_key=session_key,
                        channel=str(kwargs.get("channel") or "embedded"),
                        user_content=user_message,
                        user_display_content=display_message,
                        assistant_content=str(result.get("content") or ""),
                        tools_used=result.get("tools_used") or [],
                        stop_reason=result.get("stop_reason"),
                        usage=result.get("usage") or {},
                        tool_events=result.get("tool_events") or [],
                        thread_context=latest_thread_context,
                    )
                except Exception:
                    logger.exception("[EmbeddedNanobot] 写入数据库会话历史失败")
            return result
        finally:
            thread_context_token.var.reset(thread_context_token)
            if thread_token is not None:
                thread_token.var.reset(thread_token)
            if user_token is not None:
                user_token.var.reset(user_token)