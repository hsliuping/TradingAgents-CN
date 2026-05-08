"""Redis 兼容层。

历史调用方仍可从本模块导入接口，但实际连接生命周期统一委托给 app.core.database。
"""

import redis.asyncio as redis
import logging
from typing import Optional

from .database import close_redis_binding, get_redis_client, init_redis_binding

logger = logging.getLogger(__name__)


async def init_redis():
    """初始化Redis连接。"""
    await init_redis_binding()


async def close_redis():
    """关闭Redis连接。"""
    await close_redis_binding()


def get_redis() -> redis.Redis:
    """获取Redis客户端实例。"""
    return get_redis_client()


class RedisKeys:
    """Redis键名常量"""
    
    # 队列相关
    USER_PENDING_QUEUE = "user:{user_id}:pending"
    USER_PROCESSING_SET = "user:{user_id}:processing"
    GLOBAL_PENDING_QUEUE = "global:pending"
    GLOBAL_PROCESSING_SET = "global:processing"
    
    # 任务相关
    TASK_PROGRESS = "task:{task_id}:progress"
    TASK_RESULT = "task:{task_id}:result"
    TASK_LOCK = "task:{task_id}:lock"
    
    # 批次相关
    BATCH_PROGRESS = "batch:{batch_id}:progress"
    BATCH_TASKS = "batch:{batch_id}:tasks"
    BATCH_LOCK = "batch:{batch_id}:lock"
    
    # 用户相关
    USER_SESSION = "session:{session_id}"
    USER_RATE_LIMIT = "rate_limit:{user_id}:{endpoint}"
    USER_DAILY_QUOTA = "quota:{user_id}:{date}"
    
    # 系统相关
    QUEUE_STATS = "queue:stats"
    SYSTEM_CONFIG = "system:config"
    WORKER_HEARTBEAT = "worker:{worker_id}:heartbeat"
    
    # 缓存相关
    SCREENING_CACHE = "screening:{cache_key}"
    ANALYSIS_CACHE = "analysis:{cache_key}"
    
    # 定时任务相关
    SCHEDULER_JOB_PROGRESS = "scheduler:job:{job_id}:progress"
    SCHEDULER_JOB_STATUS = "scheduler:job:{job_id}:status"
    SCHEDULER_JOB_EXECUTION = "scheduler:job:{job_id}:execution"


class RedisService:
    """Redis服务封装类"""

    @property
    def redis(self):
        """延迟获取Redis客户端"""
        try:
            return get_redis_client()
        except RuntimeError:
            raise RuntimeError("Redis客户端未初始化，请确保在应用启动时调用了 init_redis() 或 init_database()")

    async def set_with_ttl(self, key: str, value: str, ttl: int = 3600):
        """设置带TTL的键值"""
        await self.redis.setex(key, ttl, value)

    async def get_json(self, key: str):
        """获取JSON格式的值"""
        import json
        value = await self.redis.get(key)
        if value:
            return json.loads(value)
        return None
    
    async def set_json(self, key: str, value: dict, ttl: int = None):
        """设置JSON格式的值"""
        import json
        json_str = json.dumps(value, ensure_ascii=False)
        if ttl:
            await self.redis.setex(key, ttl, json_str)
        else:
            await self.redis.set(key, json_str)
    
    async def increment_with_ttl(self, key: str, ttl: int = 3600):
        """递增计数器并设置TTL"""
        pipe = self.redis.pipeline()
        pipe.incr(key)
        pipe.expire(key, ttl)
        results = await pipe.execute()
        return results[0]
    
    async def add_to_queue(self, queue_key: str, item: dict):
        """添加项目到队列"""
        import json
        await self.redis.lpush(queue_key, json.dumps(item, ensure_ascii=False))
    
    async def pop_from_queue(self, queue_key: str, timeout: int = 1):
        """从队列弹出项目"""
        import json
        result = await self.redis.brpop(queue_key, timeout=timeout)
        if result:
            return json.loads(result[1])
        return None
    
    async def get_queue_length(self, queue_key: str):
        """获取队列长度"""
        return await self.redis.llen(queue_key)
    
    async def add_to_set(self, set_key: str, value: str):
        """添加到集合"""
        await self.redis.sadd(set_key, value)
    
    async def remove_from_set(self, set_key: str, value: str):
        """从集合移除"""
        await self.redis.srem(set_key, value)
    
    async def is_in_set(self, set_key: str, value: str):
        """检查是否在集合中"""
        return await self.redis.sismember(set_key, value)
    
    async def get_set_size(self, set_key: str):
        """获取集合大小"""
        return await self.redis.scard(set_key)
    
    async def acquire_lock(self, lock_key: str, timeout: int = 30):
        """获取分布式锁"""
        import uuid
        lock_value = str(uuid.uuid4())
        acquired = await self.redis.set(lock_key, lock_value, nx=True, ex=timeout)
        if acquired:
            return lock_value
        return None
    
    async def release_lock(self, lock_key: str, lock_value: str):
        """释放分布式锁"""
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        return await self.redis.eval(lua_script, 1, lock_key, lock_value)


# 全局Redis服务实例
redis_service: Optional[RedisService] = None


def get_redis_service() -> RedisService:
    """获取Redis服务实例"""
    global redis_service
    if redis_service is None:
        redis_service = RedisService()
    return redis_service
