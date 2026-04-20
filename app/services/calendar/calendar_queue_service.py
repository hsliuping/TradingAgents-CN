from __future__ import annotations

import json
import time
import uuid
from typing import Any, Dict, Optional

from redis.asyncio import Redis

from app.core.database import get_redis_client


READY_LIST = "cal:analysis:ready"
TASK_PREFIX = "cal:analysis:task:"
SET_PROCESSING = "cal:analysis:processing"
SET_COMPLETED = "cal:analysis:completed"
SET_FAILED = "cal:analysis:failed"
VISIBILITY_TIMEOUT_PREFIX = "cal:analysis:visibility:"


class CalendarQueueService:
    def __init__(self, redis: Redis):
        self.r = redis
        self.visibility_timeout_seconds = 600

    async def enqueue(self, event_id: str, model_name: Optional[str], requested_by: str) -> str:
        task_id = str(uuid.uuid4())
        key = TASK_PREFIX + task_id
        now = int(time.time())
        payload: Dict[str, Any] = {
            "task_id": task_id,
            "event_id": event_id,
            "requested_by": requested_by,
            "model_name": model_name,
        }
        await self.r.hset(key, "task_id", task_id)
        await self.r.hset(key, "status", "queued")
        await self.r.hset(key, "created_at", str(now))
        await self.r.hset(key, "payload", json.dumps(payload, ensure_ascii=False))
        await self.r.lpush(READY_LIST, task_id)
        return task_id

    async def dequeue(self, worker_id: str) -> Optional[Dict[str, Any]]:
        task_id = await self.r.rpop(READY_LIST)
        if not task_id:
            return None
        key = TASK_PREFIX + task_id
        data = await self.r.hgetall(key)
        if not data:
            return None
        payload = {}
        try:
            payload = json.loads(data.get("payload") or "{}")
        except Exception:
            payload = {}
        await self.r.sadd(SET_PROCESSING, task_id)
        await self.r.hset(key, "status", "processing")
        await self.r.hset(key, "worker_id", worker_id)
        await self.r.hset(key, "started_at", str(int(time.time())))
        timeout_key = VISIBILITY_TIMEOUT_PREFIX + task_id
        await self.r.hset(timeout_key, "task_id", task_id)
        await self.r.hset(timeout_key, "worker_id", worker_id)
        await self.r.hset(
            timeout_key,
            "timeout_at",
            str(int(time.time()) + int(self.visibility_timeout_seconds)),
        )
        await self.r.expire(timeout_key, int(self.visibility_timeout_seconds))
        payload["task_id"] = task_id
        return payload

    async def ack(self, task_id: str, success: bool, error_message: Optional[str] = None) -> None:
        key = TASK_PREFIX + task_id
        await self.r.srem(SET_PROCESSING, task_id)
        await self.r.delete(VISIBILITY_TIMEOUT_PREFIX + task_id)
        status = "completed" if success else "failed"
        mapping: Dict[str, str] = {"status": status, "completed_at": str(int(time.time()))}
        if error_message:
            mapping["error_message"] = error_message
        for field, value in mapping.items():
            await self.r.hset(key, field, value)
        if success:
            await self.r.sadd(SET_COMPLETED, task_id)
        else:
            await self.r.sadd(SET_FAILED, task_id)

    async def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        data = await self.r.hgetall(TASK_PREFIX + task_id)
        if not data:
            return None
        payload = {}
        try:
            payload = json.loads(data.get("payload") or "{}")
        except Exception:
            payload = {}
        payload.update({k: v for k, v in data.items() if k != "payload"})
        return payload


_calendar_queue_service: CalendarQueueService | None = None


def get_calendar_queue_service() -> CalendarQueueService:
    global _calendar_queue_service
    if _calendar_queue_service is None:
        _calendar_queue_service = CalendarQueueService(get_redis_client())
    return _calendar_queue_service
