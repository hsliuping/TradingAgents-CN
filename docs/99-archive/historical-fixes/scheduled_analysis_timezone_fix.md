# 定时分析执行历史时区显示问题修复

## 📋 问题描述

**用户反馈**: 定时分析执行历史中显示的时间不正确

**具体表现**:
- 配置的执行时间: 23:22（北京时间 UTC+8）
- 实际执行时间: 23:22（北京时间 UTC+8）
- 前端显示时间: 15:22（错误！）

**问题截图**:
```
执行时间: 2026/2/10 16:22:00
实际应该: 2026/2/11 00:22:00  (次日凌晨)
```

## 🔍 根本原因

### 1. MongoDB 时间存储机制

MongoDB 存储 datetime 对象时的行为：
- **输入**: Python `datetime` 对象（带时区信息，如 UTC+8）
- **存储**: 自动转换为 **UTC 时间**（去除时区信息）
- **返回**: **Naive datetime**（无时区信息，实际是 UTC 时间）

### 2. 后端代码问题

**存储时**（`app/worker/watchlist_analysis_task.py` 第571行）:
```python
history_doc = {
    "created_at": now_tz(),  # 返回 UTC+8 时间，如 2026-02-10 23:22:00+08:00
    ...
}
await db.scheduled_analysis_history.insert_one(history_doc)
```

**MongoDB 实际存储**:
```
created_at: 2026-02-10T15:22:00.908000  # 自动转换为 UTC 时间（23:22 - 8 = 15:22）
```

**返回给前端时**（修复前的 `app/routers/scheduled_analysis.py`）:
```python
async for doc in cursor:
    doc["id"] = str(doc.pop("_id"))
    history.append(doc)  # ❌ 直接返回，没有添加时区标识
```

**前端收到的数据**:
```json
{
    "created_at": "2026-02-10T15:22:00.908000"  # ❌ 没有时区标识
}
```

### 3. 前端处理逻辑

前端 `frontend/src/utils/datetime.ts` 的处理逻辑：
```typescript
// 如果时间字符串没有时区标识，假定为 UTC+8 时间
if (timeStr.match(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/) && !hasTimezone) {
    timeStr += '+08:00'  // ❌ 错误假设！实际是 UTC 时间
}
```

**结果**:
- 前端收到: `2026-02-10T15:22:00.908000`（无时区标识）
- 前端假设: 这是 UTC+8 时间
- 前端添加: `+08:00` 后缀
- 前端显示: `2026-02-10 15:22:00`（错误！）

**正确流程应该是**:
- 后端返回: `2026-02-10T15:22:00.908000+00:00`（UTC 时间，带时区标识）
- 前端转换: 转换为 UTC+8 → `2026-02-10 23:22:00`（正确！）

## ✅ 解决方案

### 修复后端 API

修改 `app/routers/scheduled_analysis.py` 中的三个接口：

#### 1. `list_configs()` - 获取配置列表

```python
@router.get("/configs")
async def list_configs(user: dict = Depends(get_current_user)):
    """获取用户的所有定时分析配置"""
    db = get_mongo_db()
    user_id = str(user["id"])
    
    cursor = db.scheduled_analysis_configs.find({"user_id": user_id})
    configs = []
    
    async for doc in cursor:
        doc["id"] = str(doc.pop("_id"))
        
        # 🔥 修复时区问题：转换时间字段为带时区标识的 ISO 格式
        from app.utils.timezone import to_config_tz
        from zoneinfo import ZoneInfo
        
        for time_field in ["created_at", "updated_at", "last_run_at"]:
            if time_field in doc and doc[time_field]:
                dt = doc[time_field]
                # MongoDB 返回的是 naive datetime（UTC 时间），需要添加 UTC 时区信息
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=ZoneInfo("UTC"))
                # 转换为配置的时区（UTC+8）
                dt_local = to_config_tz(dt)
                # 转换为 ISO 格式字符串（带时区标识）
                doc[time_field] = dt_local.isoformat()
        
        configs.append(doc)
    
    return ok({"configs": configs})
```

#### 2. `get_config()` - 获取配置详情

```python
@router.get("/configs/{config_id}")
async def get_config(config_id: str, user: dict = Depends(get_current_user)):
    """获取配置详情"""
    # ... 省略验证代码 ...
    
    config["id"] = str(config.pop("_id"))
    
    # 🔥 修复时区问题：转换时间字段为带时区标识的 ISO 格式
    from app.utils.timezone import to_config_tz
    from zoneinfo import ZoneInfo
    
    for time_field in ["created_at", "updated_at", "last_run_at"]:
        if time_field in config and config[time_field]:
            dt = config[time_field]
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=ZoneInfo("UTC"))
            dt_local = to_config_tz(dt)
            config[time_field] = dt_local.isoformat()
    
    return ok({"config": config})
```

#### 3. `get_config_history()` - 获取执行历史

```python
@router.get("/configs/{config_id}/history")
async def get_config_history(...):
    """获取配置的执行历史"""
    # ... 省略验证代码 ...
    
    history = []
    async for doc in cursor:
        doc["id"] = str(doc.pop("_id"))
        
        # 🔥 修复时区问题：MongoDB 存储的是 UTC 时间，需要转换为 UTC+8 并添加时区标识
        if "created_at" in doc and doc["created_at"]:
            from app.utils.timezone import to_config_tz
            created_at = doc["created_at"]
            # MongoDB 返回的是 naive datetime（UTC 时间），需要添加 UTC 时区信息
            if created_at.tzinfo is None:
                from zoneinfo import ZoneInfo
                created_at = created_at.replace(tzinfo=ZoneInfo("UTC"))
            # 转换为配置的时区（UTC+8）
            created_at_local = to_config_tz(created_at)
            # 转换为 ISO 格式字符串（带时区标识）
            doc["created_at"] = created_at_local.isoformat()
        
        history.append(doc)
    
    return ok({"history": history})
```

## 📊 修复效果

### 修复前

**后端返回**:
```json
{
    "created_at": "2026-02-10T15:22:00.908000"
}
```

**前端显示**: `2026/2/10 15:22:00`（错误！）

### 修复后

**后端返回**:
```json
{
    "created_at": "2026-02-10T23:22:00.908000+08:00"
}
```

**前端显示**: `2026/2/10 23:22:00`（正确！）

## 🎯 关键要点

1. **MongoDB 存储机制**: 自动将带时区的 datetime 转换为 UTC 时间存储
2. **MongoDB 返回机制**: 返回 naive datetime（无时区信息），实际是 UTC 时间
3. **后端责任**: 必须在返回前将 UTC 时间转换为本地时区，并添加时区标识
4. **前端假设**: 如果没有时区标识，前端会假设是 UTC+8 时间（这是错误的假设）

## 📝 最佳实践

### 后端 API 返回时间的标准流程

```python
# 1. 从 MongoDB 获取数据
doc = await db.collection.find_one(...)

# 2. 转换时间字段
from app.utils.timezone import to_config_tz
from zoneinfo import ZoneInfo

for time_field in ["created_at", "updated_at", "last_run_at"]:
    if time_field in doc and doc[time_field]:
        dt = doc[time_field]
        # MongoDB 返回的是 naive datetime（UTC 时间）
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo("UTC"))
        # 转换为配置的时区
        dt_local = to_config_tz(dt)
        # 转换为 ISO 格式字符串（带时区标识）
        doc[time_field] = dt_local.isoformat()

# 3. 返回给前端
return ok({"data": doc})
```

## 🔗 相关文件

- `app/routers/scheduled_analysis.py` - 定时分析 API（已修复）
- `app/utils/timezone.py` - 时区工具函数
- `frontend/src/utils/datetime.ts` - 前端时间格式化工具
- `app/worker/watchlist_analysis_task.py` - 执行历史记录创建

---

**修复日期**: 2026-02-10  
**修复人**: AI Assistant  
**影响范围**: 定时分析执行历史显示

