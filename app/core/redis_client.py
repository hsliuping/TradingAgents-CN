"""
Redis客户端配置和连接管理
"""

import redis.asyncio as redis
import logging
from typing import Optional
from .config import settings

logger = logging.getLogger(__name__)

# 全局Redis连接池
redis_pool: Optional[redis.ConnectionPool] = None
redis_client: Optional[redis.Redis] = None


async def init_redis():
    """初始化Redis连接"""
    global redis_pool, redis_client

    try:
        # 创建连接池
        redis_pool = redis.ConnectionPool.from_url(
            settings.REDIS_URL,
            max_connections=settings.REDIS_MAX_CONNECTIONS,  # 使用配置文件中的值
            retry_on_timeout=settings.REDIS_RETRY_ON_TIMEOUT,
            decode_responses=True,
            socket_keepalive=True,  # 启用 TCP keepalive
            socket_keepalive_options={
                1: 60,  # TCP_KEEPIDLE: 60秒后开始发送keepalive探测
                2: 10,  # TCP_KEEPINTVL: 每10秒发送一次探测
                3: 3,   # TCP_KEEPCNT: 最多发送3次探测
            },
            health_check_interval=30,  # 每30秒检查一次连接健康状态
        )

        # 创建Redis客户端
        redis_client = redis.Redis(connection_pool=redis_pool)

        # 测试连接
        await redis_client.ping()
        logger.info(f"✅ Redis连接成功建立 (max_connections={settings.REDIS_MAX_CONNECTIONS})")

    except Exception as e:
        logger.error(f"❌ Redis连接失败: {e}")
        raise


async def close_redis():
    """关闭Redis连接"""
    global redis_pool, redis_client
    
    try:
        if redis_client:
            await redis_client.close()
        if redis_pool:
            await redis_pool.disconnect()
        logger.info("✅ Redis连接已关闭")
    except Exception as e:
        logger.error(f"❌ 关闭Redis连接时出错: {e}")


def get_redis() -> redis.Redis:
    """获取Redis客户端实例"""
    if redis_client is None:
        raise RuntimeError("Redis客户端未初始化")
    return redis_client


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


class RedisService:
    """Redis服务封装类"""
    
    def __init__(self):
        self.redis = get_redis()
    
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
