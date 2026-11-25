"""
通知服务：持久化 + 列表 + 已读 + SSE 发布
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from bson import ObjectId

from app.core.database import get_mongo_db, get_redis_client
from app.models.notification import (
    NotificationCreate, NotificationOut, NotificationList
)
from app.utils.timezone import now_tz

logger = logging.getLogger("webapi.notifications")


class NotificationsService:
    def __init__(self):
        self.collection = "notifications"
        self.channel_prefix = "notifications:"
        self.retain_days = 90
        self.max_per_user = 1000

    async def _ensure_indexes(self):
        try:
            db = get_mongo_db()
            await db[self.collection].create_index([("user_id", 1), ("created_at", -1)])
            await db[self.collection].create_index([("user_id", 1), ("status", 1)])
        except Exception as e:
            logger.warning(f"创建索引失败(忽略): {e}")

    async def create_and_publish(self, payload: NotificationCreate) -> str:
        await self._ensure_indexes()
        db = get_mongo_db()
        doc = {
            "user_id": payload.user_id,
            "type": payload.type,
            "title": payload.title,
            "content": payload.content,
            "link": payload.link,
            "source": payload.source,
            "severity": payload.severity or "info",
            "status": "unread",
            "created_at": now_tz(),
            "metadata": payload.metadata or {},
        }
        res = await db[self.collection].insert_one(doc)
        doc_id = str(res.inserted_id)

        payload_to_publish = {
            "id": doc_id,
            "type": doc["type"],
            "title": doc["title"],
            "content": doc.get("content"),
            "link": doc.get("link"),
            "source": doc.get("source"),
            "status": doc.get("status", "unread"),
            "created_at": doc["created_at"].isoformat(),
        }

        # 🔥 使用 WebSocket 发送通知
        try:
            from app.routers.websocket_notifications import send_notification_via_websocket
            await send_notification_via_websocket(payload.user_id, payload_to_publish)
            logger.debug(f"✅ [WS] 通知已通过 WebSocket 发送: user={payload.user_id}")
        except Exception as e:
            logger.warning(f"⚠️ [WS] WebSocket 发送失败: {e}")

        # 📣 渠道推送（飞书/钉钉/企微/邮件），fire-and-forget
        try:
            from app.services.channel_notifier import get_channel_notifier
            notifier = get_channel_notifier()
            event_type = payload.type or "system"
            # 将 analysis/alert/skill_gap 映射到渠道事件类型
            _type_map = {
                "analysis": "analysis_complete",
                "alert": "alert",
                "skill_gap": "skill_gap",
                "system": "system",
            }
            channel_event = _type_map.get(event_type, "system")
            import asyncio
            asyncio.ensure_future(
                notifier.dispatch(
                    user_id=payload.user_id,
                    title=payload.title or "通知",
                    content=payload.content or "",
                    event_type=channel_event,
                    metadata=payload.metadata,
                )
            )
        except Exception as e:
            logger.warning(f"⚠️ [Channel] 渠道推送调度失败(忽略): {e}")

        # 清理策略：保留最近N天/最多M条
        try:
            await db[self.collection].delete_many({
                "user_id": payload.user_id,
                "created_at": {"$lt": now_tz() - timedelta(days=self.retain_days)}
            })
            # 超过配额按时间删旧
            count = await db[self.collection].count_documents({"user_id": payload.user_id})
            if count > self.max_per_user:
                skip = count - self.max_per_user
                ids = []
                async for d in db[self.collection].find({"user_id": payload.user_id}, {"_id": 1}).sort("created_at", 1).limit(skip):
                    ids.append(d["_id"])
                if ids:
                    await db[self.collection].delete_many({"_id": {"$in": ids}})
        except Exception as e:
            logger.warning(f"通知清理失败(忽略): {e}")

        return doc_id

    async def unread_count(self, user_id: str) -> int:
        db = get_mongo_db()
        return await db[self.collection].count_documents({"user_id": user_id, "status": "unread"})

    async def list(self, user_id: str, *, status: Optional[str] = None, ntype: Optional[str] = None, page: int = 1, page_size: int = 20) -> NotificationList:
        db = get_mongo_db()
        q: Dict[str, Any] = {"user_id": user_id}
        if status in ("read", "unread"):
            q["status"] = status
        if ntype in ("analysis", "alert", "system"):
            q["type"] = ntype
        total = await db[self.collection].count_documents(q)
        cursor = db[self.collection].find(q).sort("created_at", -1).skip((page-1)*page_size).limit(page_size)
        items: List[NotificationOut] = []
        async for d in cursor:
            items.append(NotificationOut(
                id=str(d.get("_id")),
                type=d.get("type"),
                title=d.get("title"),
                content=d.get("content"),
                link=d.get("link"),
                source=d.get("source"),
                status=d.get("status", "unread"),
                created_at=d.get("created_at") or now_tz(),
            ))
        return NotificationList(items=items, total=total, page=page, page_size=page_size)

    async def mark_read(self, user_id: str, notif_id: str) -> bool:
        db = get_mongo_db()
        try:
            oid = ObjectId(notif_id)
        except Exception:
            return False
        res = await db[self.collection].update_one({"_id": oid, "user_id": user_id}, {"$set": {"status": "read"}})
        return res.modified_count > 0

    async def mark_all_read(self, user_id: str) -> int:
        db = get_mongo_db()
        res = await db[self.collection].update_many({"user_id": user_id, "status": "unread"}, {"$set": {"status": "read"}})
        return res.modified_count


_notifications_service: Optional[NotificationsService] = None


def get_notifications_service() -> NotificationsService:
    global _notifications_service
    if _notifications_service is None:
        _notifications_service = NotificationsService()
    return _notifications_service

