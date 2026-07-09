# Session 时区问题修复

## 🔴 问题描述

### 症状
- 用户登录成功
- 一段时间后自动刷新 token 时返回 401
- 用户被强制退出登录

### 错误日志

```
❌ 验证会话失败: can't compare offset-naive and offset-aware datetimes
❌ Refresh token 的 session 无效
POST /api/auth/refresh - 状态: 401
```

---

## 🔍 根本原因

### 问题 1: 异步/同步混用

**SessionService 使用同步的 MongoDB 操作，但在异步上下文中被调用**

- `SessionService` 使用 `find_one()`, `insert_one()` 等同步方法
- 但在异步路由处理函数中被调用
- 导致 `'_asyncio.Future' object is not subscriptable` 错误

### 问题 2: 时区不一致

**存储和比较时使用了不同的时区**

- `create_session()` 使用 `now_tz()` 存储时间（带时区）
- MongoDB 可能会自动转换或去除时区信息
- `verify_session()` 比较时使用 `now_tz()`（带时区）
- 导致 `can't compare offset-naive and offset-aware datetimes` 错误

---

## ✅ 解决方案

### 修复 1: 使用同步数据库连接

**文件**: `app/services/session_service.py`

```python
def get_session_service(db: Optional[Database] = None) -> SessionService:
    """
    获取 SessionService 单例
    
    注意：SessionService 使用同步的 MongoDB 操作，
    因此需要使用 get_mongo_db_sync() 而不是 get_mongo_db()
    """
    global _session_service

    if _session_service is None:
        if db is None:
            from app.core.database import get_mongo_db_sync
            db = get_mongo_db_sync()  # 🔥 使用同步的数据库连接

        _session_service = SessionService(db)

    return _session_service
```

### 修复 2: 统一使用 UTC 时间（naive datetime）

**原则**: 在 MongoDB 中统一存储 UTC 时间（不带时区信息）

#### 2.1 修改 `create_session()`

```python
# 🔥 使用 UTC 时间（naive datetime）存储到 MongoDB
from datetime import datetime, timezone
now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
expires_at_utc = now_utc + timedelta(seconds=expires_in_seconds)

session_doc = {
    "session_id": session_id,
    "user_id": user_id,
    "created_at": now_utc,
    "expires_at": expires_at_utc,
    "last_activity": now_utc,
    "ip_address": ip_address,
    "user_agent": user_agent
}
```

#### 2.2 修改 `verify_session()`

```python
# 检查是否过期（使用 UTC 时间）
now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
expires_at = session_doc["expires_at"]

if expires_at < now_utc:
    # 会话已过期
    ...
```

#### 2.3 修改 `get_user_sessions()`

```python
# 🔥 使用 UTC 时间查询（与存储时保持一致）
now_utc = datetime.now(timezone.utc).replace(tzinfo=None)

sessions = self.sessions_collection.find({
    "user_id": user_id,
    "expires_at": {"$gt": now_utc}
}).sort("last_activity", -1)
```

#### 2.4 修改 `cleanup_expired_sessions()`

```python
# 🔥 使用 UTC 时间查询
now_utc = datetime.now(timezone.utc).replace(tzinfo=None)

result = self.sessions_collection.delete_many({"expires_at": {"$lt": now_utc}})
```

---

## 🧪 验证修复

### 1. 清除旧的 Session 数据

```javascript
// 在 MongoDB 中清除旧的 session 数据
db.user_sessions.deleteMany({})
```

### 2. 重启后端服务

```bash
# 停止后端
Ctrl+C

# 重新启动
python app/main.py
```

### 3. 测试登录和刷新

1. **登录**
2. **等待 token 自动刷新**（约 50 分钟后）
3. **检查日志**：应该看到 `✅ Token刷新成功`

---

## 📝 最佳实践

### MongoDB 时间存储规范

1. **统一使用 UTC 时间**
   - 存储时：`datetime.now(timezone.utc).replace(tzinfo=None)`
   - 查询时：`datetime.now(timezone.utc).replace(tzinfo=None)`

2. **为什么使用 naive datetime？**
   - MongoDB 会自动处理时区转换
   - 避免时区比较问题
   - 简化代码逻辑

3. **显示时转换为本地时区**
   - 从数据库读取后，使用 `to_config_tz()` 转换为配置的时区
   - 仅在显示给用户时转换

---

**修复日期**: 2026-01-06  
**影响版本**: v1.0.0 - v1.0.1  
**修复版本**: v1.0.2

