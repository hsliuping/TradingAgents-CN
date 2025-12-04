# Redis 连接泄漏问题分析与修复

## 📋 问题描述

用户报告 Redis 连接池耗尽错误：

```
redis.exceptions.ConnectionError: Too many connections
```

错误发生在 SSE 通知流和任务进度流中，订阅频道时失败，但连接没有被正确释放。

---

## 🔍 全面检查结果

### 1. ✅ 已修复的问题

#### 1.1 `app/routers/notifications.py` - 通知 SSE 流

**问题**：
- 订阅频道失败时，`pubsub` 连接没有被立即关闭
- `finally` 块中的 `unsubscribe` 会失败（因为没有订阅成功）
- 导致连接泄漏

**修复**：
```python
# 修复前
pubsub = r.pubsub()
await pubsub.subscribe(channel)  # 如果这里失败，连接泄漏

# 修复后
pubsub = None
try:
    pubsub = r.pubsub()
    try:
        await pubsub.subscribe(channel)
    except Exception as subscribe_error:
        # 订阅失败时立即关闭 pubsub 连接
        await pubsub.close()
        raise
finally:
    if pubsub:
        # 分步骤关闭：unsubscribe → close → reset
        ...
```

#### 1.2 `app/routers/sse.py` - 任务进度 SSE 流

**问题**：与 `notifications.py` 相同

**修复**：应用相同的修复逻辑

---

### 2. ✅ 无问题的代码

#### 2.1 `app/worker.py` - 发布进度更新

```python
async def publish_progress(task_id: str, message: str, ...):
    r = get_redis_client()
    await r.publish(f"task_progress:{task_id}", json.dumps(progress_data))
```

**分析**：
- ✅ 使用全局 Redis 客户端，不创建新连接
- ✅ `publish` 操作不需要手动释放连接
- ✅ 连接由连接池自动管理

#### 2.2 `app/services/notifications_service.py` - 发布通知

```python
async def create(self, payload: CreateNotificationPayload) -> str:
    r = get_redis_client()
    await r.publish(f"{self.channel_prefix}{payload.user_id}", json.dumps(payload_to_publish))
```

**分析**：
- ✅ 使用全局 Redis 客户端
- ✅ `publish` 操作不需要手动释放连接
- ✅ 异常被捕获并记录，不会影响主流程

#### 2.3 `app/core/redis_client.py` - Redis 服务类

```python
class RedisService:
    async def increment_with_ttl(self, key: str, ttl: int = 3600):
        pipe = self.redis.pipeline()
        pipe.incr(key)
        pipe.expire(key, ttl)
        results = await pipe.execute()
        return results[0]
```

**分析**：
- ✅ `pipeline()` 返回的对象在 `execute()` 后自动释放连接
- ✅ 不需要手动关闭 pipeline
- ✅ 连接由连接池自动管理

#### 2.4 `app/services/queue_service.py` - 队列服务

```python
class QueueService:
    def __init__(self, redis: Redis):
        self.r = redis  # 使用传入的 Redis 客户端
    
    async def enqueue_task(self, ...):
        await self.r.hset(key, mapping=mapping)
        await self.r.lpush(READY_LIST, task_id)
```

**分析**：
- ✅ 使用传入的 Redis 客户端，不创建新连接
- ✅ 所有操作都是基本的 Redis 命令，不需要手动释放连接
- ✅ 连接由连接池自动管理

#### 2.5 `app/worker.py` - Worker 循环

```python
async def worker_loop(stop_event: asyncio.Event):
    r = get_redis_client()
    while not stop_event.is_set():
        item = await r.blpop(READY_LIST, timeout=5)
```

**分析**：
- ✅ 使用全局 Redis 客户端
- ✅ `blpop` 操作不需要手动释放连接
- ✅ 连接由连接池自动管理

---

## 🎯 关键发现

### PubSub 连接的特殊性

**普通 Redis 操作**（如 `get`, `set`, `lpush`, `publish` 等）：
- ✅ 使用连接池中的连接
- ✅ 操作完成后自动归还连接到连接池
- ✅ 不需要手动释放连接

**PubSub 连接**（`r.pubsub()`）：
- ⚠️ 创建一个**独占的连接**，不会自动归还到连接池
- ⚠️ 必须手动调用 `close()` 或 `reset()` 来释放连接
- ⚠️ 如果订阅失败，连接仍然被占用，必须立即关闭

---

## 📊 修复总结

### 修复的文件

1. ✅ `app/routers/notifications.py`
   - 修复通知 SSE 流的 PubSub 连接泄漏
   - 添加订阅失败时的立即清理逻辑
   - 改进 `finally` 块的分步骤关闭逻辑

2. ✅ `app/routers/sse.py`
   - 修复任务进度 SSE 流的 PubSub 连接泄漏
   - 应用相同的修复逻辑
   - 删除未使用的 Redis 客户端变量

### 无需修复的文件

- ✅ `app/worker.py` - 使用全局客户端，无连接泄漏
- ✅ `app/services/notifications_service.py` - 使用全局客户端，无连接泄漏
- ✅ `app/core/redis_client.py` - Pipeline 自动释放连接
- ✅ `app/services/queue_service.py` - 使用传入的客户端，无连接泄漏
- ✅ 其他所有使用 Redis 的地方 - 都是普通操作，无连接泄漏

---

## 🔧 修复模式

### 正确的 PubSub 使用模式

```python
async def sse_generator(user_id: str):
    r = get_redis_client()
    pubsub = None
    channel = f"notifications:{user_id}"

    try:
        # 1. 创建 PubSub 连接
        pubsub = r.pubsub()
        logger.info(f"📡 创建 PubSub 连接: {channel}")

        # 2. 订阅频道（可能失败）
        try:
            await pubsub.subscribe(channel)
            logger.info(f"✅ 订阅频道成功: {channel}")
            yield f"event: connected\ndata: ...\n\n"
        except Exception as subscribe_error:
            # 🔥 订阅失败时立即关闭 pubsub 连接
            logger.error(f"❌ 订阅频道失败: {subscribe_error}")
            await pubsub.close()
            raise

        # 3. 处理消息
        while True:
            msg = await pubsub.get_message(...)
            if msg:
                yield f"event: message\ndata: {msg}\n\n"

    except Exception as e:
        logger.error(f"❌ 连接错误: {e}")
        yield f"event: error\ndata: ...\n\n"
    finally:
        # 4. 确保在所有情况下都释放连接
        if pubsub:
            logger.info(f"🧹 清理 PubSub 连接")

            # 分步骤关闭，确保即使 unsubscribe 失败也能关闭连接
            try:
                await pubsub.unsubscribe(channel)
                logger.debug(f"✅ 已取消订阅频道: {channel}")
            except Exception as e:
                logger.warning(f"⚠️ 取消订阅失败（将继续关闭连接）: {e}")

            try:
                await pubsub.close()
                logger.info(f"✅ PubSub 连接已关闭")
            except Exception as e:
                logger.error(f"❌ 关闭 PubSub 连接失败: {e}")
                # 即使关闭失败，也尝试重置连接
                try:
                    await pubsub.reset()
                    logger.info(f"🔄 PubSub 连接已重置")
                except Exception as reset_error:
                    logger.error(f"❌ 重置 PubSub 连接也失败: {reset_error}")
```

---

## 📈 验证方法

### 1. 查看 Redis 连接池状态

```bash
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/notifications/debug/redis_pool
```

**响应示例**：
```json
{
  "success": true,
  "data": {
    "pool": {
      "max_connections": 200,
      "available_connections": 195,
      "in_use_connections": 5
    },
    "redis_server": {
      "connected_clients": 8
    },
    "pubsub": {
      "active_channels": 2,
      "channels": ["notifications:admin", "task_progress:abc123"]
    }
  }
}
```

### 2. 监控日志

**正常流程**：
```
📡 [SSE] 创建 PubSub 连接: user=admin, channel=notifications:admin
✅ [SSE] 订阅频道成功: notifications:admin
🔌 [SSE] 客户端断开连接: user=admin, 已发送 5 条消息
🧹 [SSE] 清理 PubSub 连接: user=admin
✅ [SSE] 已取消订阅频道: notifications:admin
✅ [SSE] PubSub 连接已关闭: user=admin
```

**订阅失败流程**：
```
📡 [SSE] 创建 PubSub 连接: user=admin, channel=notifications:admin
❌ [SSE] 订阅频道失败: Too many connections
🧹 [SSE] 订阅失败后已关闭 PubSub 连接
❌ [SSE] 连接错误: Too many connections
🧹 [SSE] 清理 PubSub 连接: user=admin
⚠️ [SSE] 取消订阅失败（将继续关闭连接）: ...
✅ [SSE] PubSub 连接已关闭: user=admin
```

---

## 🎉 结论

### 问题根源

**只有 PubSub 连接会导致连接泄漏**，因为：
1. PubSub 连接是独占的，不会自动归还到连接池
2. 订阅失败时，连接仍然被占用
3. 如果没有立即关闭，连接会一直占用，直到连接池耗尽

### 修复效果

- ✅ 订阅失败时 PubSub 连接会被立即关闭
- ✅ 连接池不会因为订阅失败而泄漏
- ✅ 即使 `unsubscribe` 失败，`close` 和 `reset` 仍会执行
- ✅ 调试端点可以查看活跃的 PubSub 频道数量

### 其他 Redis 使用

- ✅ 所有其他 Redis 操作（`publish`, `lpush`, `hset`, `blpop` 等）都是安全的
- ✅ 不需要手动释放连接，连接池会自动管理
- ✅ Pipeline 操作在 `execute()` 后自动释放连接

---

## 📝 提交记录

```
commit 3cb655c
fix: 修复 Redis PubSub 连接泄漏问题

修复内容：
1. app/routers/notifications.py - 修复通知 SSE 流的连接泄漏
2. app/routers/sse.py - 修复任务进度 SSE 流的连接泄漏

技术改进：
- 订阅失败时立即关闭 pubsub 连接
- finally 块中分步骤关闭：unsubscribe → close → reset
- 每一步都有独立的异常处理
- 添加详细的日志记录
```

