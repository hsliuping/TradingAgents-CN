# 线程池 Event Loop 冲突修复

## 📋 问题描述

在使用 `UnifiedThreadPoolSyncService` 执行同步数据任务时，遇到以下错误：

```
Task <Task pending> got Future <Future pending> attached to a different loop
```

### 错误原因

1. **线程池中的异步代码**试图调用 MongoDB 的异步 `bulk_write()` 方法
2. 异步方法创建的 `Task` 和 `Future` 对象绑定到了**主线程的 event loop**
3. 线程池的线程有自己的 event loop，无法处理绑定到主线程 event loop 的 Future
4. 导致 `attached to a different loop` 错误

### 具体场景

- 历史数据同步（`historical_data_service.py`）
- 基础数据同步（`basics_sync_service.py`）
- 多数据源基础数据同步（`multi_source_basics_sync_service.py`）
- 新闻数据同步（`news_data_service.py`）

---

## ✅ 解决方案

### 方案：线程安全的数据库操作工具

创建通用的 `safe_bulk_write()` 函数，自动检测运行环境：

- **在主线程中**：使用异步 MongoDB 客户端（motor）
- **在线程池中**：使用同步 MongoDB 客户端（pymongo）

---

## 🔧 实现细节

### 1. 创建线程安全工具模块

**文件**: `app/utils/thread_safe_db.py`

**核心函数**:

```python
async def safe_bulk_write(
    collection_name: str,
    operations: List,
    ordered: bool = False,
    async_db=None,
    max_retries: int = 3
) -> BulkWriteResult:
    """
    线程安全的 bulk_write 操作
    
    自动检测运行环境：
    - 在主线程中：使用异步 MongoDB 客户端
    - 在线程池中：使用同步 MongoDB 客户端
    """
    in_thread_pool = is_in_thread_pool()
    
    if in_thread_pool:
        # 使用同步客户端
        from app.core.database import get_mongo_db_sync
        sync_db = get_mongo_db_sync()
        sync_collection = sync_db[collection_name]
        result = sync_collection.bulk_write(operations, ordered=ordered)
    else:
        # 使用异步客户端
        async_collection = async_db[collection_name]
        result = await async_collection.bulk_write(operations, ordered=ordered)
    
    return result
```

**辅助函数**:

```python
def is_in_thread_pool() -> bool:
    """检测当前是否在线程池中运行"""
    current_thread = threading.current_thread()
    return not isinstance(current_thread, threading._MainThread)

async def safe_sleep(seconds: float):
    """线程安全的 sleep 操作"""
    if is_in_thread_pool():
        import time
        time.sleep(seconds)
    else:
        await asyncio.sleep(seconds)
```

---

### 2. 修改受影响的服务

#### ✅ `historical_data_service.py`

**修改位置**: 第 240-310 行

**修改内容**:
- 在 `_execute_bulk_write_with_retry()` 方法中检测运行环境
- 线程池中使用同步 `bulk_write()`
- 主线程中使用异步 `bulk_write()`
- `sleep` 操作也根据环境选择同步或异步

#### ✅ `basics_sync_service.py`

**修改位置**: 第 130-166 行

**修改内容**:
- 使用 `safe_bulk_write()` 替代直接调用 `bulk_write()`

#### ✅ `multi_source_basics_sync_service.py`

**修改位置**: 第 98-163 行

**修改内容**:
- 使用 `safe_bulk_write()` 替代直接调用 `bulk_write()`

#### ✅ `news_data_service.py`

**修改位置**: 第 211-230 行（异步方法）

**修改内容**:
- 使用 `safe_bulk_write()` 替代直接调用 `bulk_write()`

**注意**: 第 323 行的同步方法 `save_news_data_sync()` 已经使用同步客户端，无需修改

---

## 🎯 修复效果

**修复前**:
```
❌ 002289 批量写入失败: Task <Task pending> got Future <Future pending> attached to a different loop
✅ 批量写入 200 条，实际保存 0 条
```

**修复后**:
```
🔍 [线程池] 使用同步 bulk_write: 集合=stock_daily_quotes, 操作数=200, ordered=False
✅ 002289 批量保存成功: 操作数=200, 新增=150, 更新=50, 总保存=200
```

---

## 📝 最佳实践

### 1. 在线程池中执行数据库操作

**推荐**:
```python
# 使用线程安全的工具函数
from app.utils.thread_safe_db import safe_bulk_write

result = await safe_bulk_write(
    collection_name="my_collection",
    operations=operations,
    ordered=False,
    async_db=db,
    max_retries=3
)
```

**不推荐**:
```python
# 直接调用异步方法（在线程池中会失败）
result = await collection.bulk_write(operations)
```

### 2. Sleep 操作

**推荐**:
```python
from app.utils.thread_safe_db import safe_sleep

await safe_sleep(5)  # 自动选择 time.sleep 或 asyncio.sleep
```

**不推荐**:
```python
await asyncio.sleep(5)  # 在线程池中会失败
```

---

**修复日期**: 2026-02-06  
**相关文档**: `docs/design/thread_pool_sync_implementation_summary.md`

