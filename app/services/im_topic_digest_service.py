import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services.intelligent_assistant_service import (
    _build_thread_summary_with_llm,
    append_assistant_message,
    create_assistant_thread,
    summarize_assistant_thread,
)

logger = logging.getLogger(__name__)

DIGEST_FALLBACK_TOPIC_TITLE = "外部沟通沉淀"
DIGEST_TOOL_NAME = "im_topic_digest_sync"


class IMTopicDigestService:
    """定期将无主题的外部会话沉淀到研究主题中。"""

    def __init__(self, db):
        self.db = db

    async def run_once(
        self,
        min_messages: int = 6,
        lookback_limit: int = 20,
    ) -> Dict[str, Any]:
        stats = {
            "scanned": 0,
            "digested": 0,
            "skipped": 0,
            "failed": 0,
        }

        cursor = self.db.assistant_threads.find({
            "topic_type": "im_session",
            "archived": {"$ne": True},
            "message_count": {"$gte": max(min_messages, 1)},
        }).sort("updated_at", -1)

        async for session_thread in cursor:
            stats["scanned"] += 1
            try:
                digested = await self._digest_session_thread(
                    session_thread,
                    min_messages=min_messages,
                    lookback_limit=lookback_limit,
                )
                if digested:
                    stats["digested"] += 1
                else:
                    stats["skipped"] += 1
            except Exception as exc:
                stats["failed"] += 1
                logger.exception("[IMTopicDigest] 沉淀外部会话失败: thread=%s err=%s", session_thread.get("thread_id"), exc)

        logger.info("[IMTopicDigest] 完成: %s", stats)
        return stats

    async def _digest_session_thread(
        self,
        session_thread: Dict[str, Any],
        min_messages: int,
        lookback_limit: int,
    ) -> bool:
        user_id = str(session_thread.get("user_id") or "").strip()
        session_key = str(session_thread.get("thread_id") or "").strip()
        if not user_id or not session_key:
            return False

        processed_count = int(session_thread.get("last_digest_message_count") or 0)
        total_count = int(session_thread.get("message_count") or 0)
        unsynced_count = max(total_count - processed_count, 0)
        if unsynced_count < min_messages:
            return False

        messages = await self.db.assistant_thread_messages.find({
            "user_id": user_id,
            "thread_id": session_key,
        }).sort("created_at", 1).skip(processed_count).to_list(length=lookback_limit)
        if len(messages) < min_messages:
            return False

        formatted_messages = [
            {
                "role": doc.get("role", "assistant"),
                "content": doc.get("content", ""),
                "tools_used": doc.get("tools_used") or None,
            }
            for doc in messages
            if (doc.get("content") or "").strip()
        ]
        if len(formatted_messages) < min_messages:
            return False

        summary = await _build_thread_summary_with_llm(self.db, formatted_messages, title="外部会话沉淀")
        summary_text = self._format_digest_message(session_key, formatted_messages, summary)
        target_thread_id = await self._resolve_target_thread_id(user_id, session_key)
        if not target_thread_id:
            return False

        await append_assistant_message(
            self.db,
            user_id=user_id,
            role="assistant",
            content=summary_text,
            conversation_id=target_thread_id,
            tools_used=[DIGEST_TOOL_NAME],
        )
        await summarize_assistant_thread(
            self.db,
            user_id=user_id,
            conversation_id=target_thread_id,
            summary_type="im_digest",
        )

        now = datetime.now(timezone.utc)
        await self.db.assistant_threads.update_one(
            {"user_id": user_id, "thread_id": session_key},
            {
                "$set": {
                    "last_digest_at": now,
                    "last_digest_message_count": total_count,
                    "last_digest_target_thread_id": target_thread_id,
                    "last_digest_summary": summary.get("abstract") or "",
                }
            },
        )
        return True

    async def _resolve_target_thread_id(self, user_id: str, session_key: str) -> Optional[str]:
        session_doc = await self.db.gateway_sessions.find_one(
            {"session_key": session_key},
            {"context.current_topic_id": 1},
        )
        bound_topic_id = ((session_doc or {}).get("context") or {}).get("current_topic_id")
        bound_topic_id = (bound_topic_id or "").strip() or None
        if bound_topic_id:
            topic_doc = await self.db.assistant_threads.find_one({
                "user_id": user_id,
                "thread_id": bound_topic_id,
                "archived": {"$ne": True},
            })
            if topic_doc and topic_doc.get("topic_type") != "im_session":
                return bound_topic_id

        fallback_topic = await create_assistant_thread(
            self.db,
            user_id=user_id,
            title=DIGEST_FALLBACK_TOPIC_TITLE,
            parent_thread_id=None,
        )
        return fallback_topic.get("thread_id")

    def _format_digest_message(
        self,
        session_key: str,
        messages: List[Dict[str, Any]],
        summary: Dict[str, Any],
    ) -> str:
        latest_user = ""
        for message in reversed(messages):
            if message.get("role") == "user" and (message.get("content") or "").strip():
                latest_user = (message.get("content") or "").strip()
                break

        lines = [
            f"【外部沟通沉淀】{datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"来源会话: {session_key}",
        ]
        if latest_user:
            lines.append(f"最近用户问题: {latest_user[:80]}")

        abstract = (summary.get("abstract") or "").strip()
        if abstract:
            lines.extend(["", "摘要:", abstract[:200]])

        confirmed_facts = summary.get("confirmed_facts") or []
        if confirmed_facts:
            lines.append("")
            lines.append("已确认信息:")
            lines.extend(f"- {item}" for item in confirmed_facts[:3])

        open_questions = summary.get("open_questions") or []
        if open_questions:
            lines.append("")
            lines.append("待继续跟进:")
            lines.extend(f"- {item}" for item in open_questions[:3])

        next_actions = summary.get("next_actions") or []
        if next_actions:
            lines.append("")
            lines.append("建议动作:")
            lines.extend(f"- {item}" for item in next_actions[:3])

        return "\n".join(lines)
