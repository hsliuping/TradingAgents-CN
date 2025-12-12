"""
队列服务的辅助函数（与 Redis 操作相关），便于在主服务中做薄委托。
"""
from __future__ import annotations
import time
from typing import Dict
from redis.asyncio import Redis

from .keys import (
    READY_LIST,
    TASK_PREFIX,
    SET_PROCESSING,
    USER_PROCESSING_PREFIX,
    VISIBILITY_TIMEOUT_PREFIX,
)


async def check_user_concurrent_limit(r: Redis, user_id: str, limit: int) -> bool:
    """检查用户并发限制"""
    user_processing_key = USER_PROCESSING_PREFIX + user_id
    current_count = await r.scard(user_processing_key)
    return current_count < limit


async def check_global_concurrent_limit(r: Redis, limit: int) -> bool:
    """检查全局并发限制（基于处理中集合大小）"""
    current_count = await r.scard(SET_PROCESSING)
    return current_count < limit


async def mark_task_processing(r: Redis, task_id: str, user_id: str) -> None:
    """标记任务为处理中"""
    user_processing_key = USER_PROCESSING_PREFIX + user_id
    await r.sadd(user_processing_key, task_id)
    await r.sadd(SET_PROCESSING, task_id)


async def unmark_task_processing(r: Redis, task_id: str, user_id: str) -> None:
    """取消任务处理中标记"""
    user_processing_key = USER_PROCESSING_PREFIX + user_id
    await r.srem(user_processing_key, task_id)
    await r.srem(SET_PROCESSING, task_id)


async def set_visibility_timeout(r: Redis, task_id: str, worker_id: str, visibility_timeout: int) -> None:
    """设置可见性超时"""
    timeout_key = VISIBILITY_TIMEOUT_PREFIX + task_id
    timeout_data: Dict[str, str] = {
        "task_id": task_id,
        "worker_id": worker_id,
        "timeout_at": str(int(time.time()) + visibility_timeout),
    }
    await r.hset(timeout_key, mapping=timeout_data)
    await r.expire(timeout_key, visibility_timeout)


async def clear_visibility_timeout(r: Redis, task_id: str) -> None:
    """清除可见性超时"""
    timeout_key = VISIBILITY_TIMEOUT_PREFIX + task_id
    await r.delete(timeout_key)

