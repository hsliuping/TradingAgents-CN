# 修复提示词模板 Active API 路由问题

## 🐛 问题描述

前端调用 `/api/v1/user-template-configs/active` 时报错：

```
'active' is not a valid ObjectId, it must be a 12-byte input or a 24-character hex string
```

## 🔍 问题原因

FastAPI 路由匹配顺序问题：

```python
# 错误的顺序
@router.get("/{config_id}")  # 这个会先匹配
async def get_config(config_id: str): ...

@router.get("/active")  # 永远不会被匹配到
async def get_active_config(): ...
```

当请求 `/api/v1/user-template-configs/active` 时：
1. FastAPI 先匹配到 `/{config_id}` 路由
2. 把 `active` 当作 `config_id` 参数
3. 尝试将 `active` 转换为 ObjectId 失败

## ✅ 解决方案

### 1. 调整路由顺序

将更具体的路由放在前面：

```python
# 正确的顺序
@router.get("/active")  # 具体路由在前
async def get_active_config(): ...

@router.get("/user/{user_id}")  # 具体路由在前
async def get_user_configs(): ...

@router.get("/{config_id}")  # 通配路由在后
async def get_config(config_id: str): ...
```

### 2. 优化 `/active` 端点

**问题**：前端只传递了 `agent_name`，但后端需要 `agent_type`

**解决方案**：
- 将 `agent_type` 改为可选参数
- 如果未提供，从 `agent_name` 推断
- 未找到配置时返回 `null` 而不是 404 错误

```python
@router.get("/active", response_model=dict)
async def get_active_config(
    user_id: str = Query(...),
    agent_name: str = Query(...),
    agent_type: Optional[str] = Query(None),  # 可选
    preference_id: Optional[str] = Query(None),
    config_service: UserTemplateConfigService = Depends(get_config_service)
):
    # 如果没有提供 agent_type，从 agent_name 推断
    if not agent_type:
        if '_v2' in agent_name:
            agent_type = 'analysts_v2'  # 默认值
        else:
            agent_type = 'analysts'
    
    config = await config_service.get_active_config(...)
    
    if not config:
        return ok(None)  # 返回 null 而不是 404
    
    return ok({
        "id": str(config.id),
        "template_id": str(config.template_id),
        "is_active": config.is_active
    })
```

### 3. 前端推断 agent_type

添加辅助函数从 `agent_name` 推断 `agent_type`：

```typescript
const inferAgentType = (agentName: string): string => {
  if (agentName.includes('_v2')) {
    if (agentName.includes('analyst')) return 'analysts_v2'
    if (agentName.includes('researcher')) return 'researchers_v2'
    if (agentName.includes('debator')) return 'debators_v2'
    if (agentName.includes('manager')) return 'managers_v2'
    if (agentName.includes('trader')) return 'trader_v2'
    return 'analysts_v2' // 默认值
  } else {
    // v1.x
    if (agentName.includes('analyst')) return 'analysts'
    if (agentName.includes('researcher')) return 'researchers'
    // ...
    return 'analysts'
  }
}

// 调用 API 时传递 agent_type
const response = await ApiClient.get('/api/v1/user-template-configs/active', {
  params: {
    user_id: userId,
    agent_name: agent.value.id,
    agent_type: inferAgentType(agent.value.id)
  }
})
```

## 📝 修改的文件

1. **app/routers/user_template_configs.py**
   - ✅ 调整路由顺序（`/active` 在 `/{config_id}` 之前）
   - ✅ 将 `agent_type` 改为可选参数
   - ✅ 添加 `agent_type` 推断逻辑
   - ✅ 未找到配置时返回 `null` 而不是 404

2. **frontend/src/views/Workflow/AgentDetail.vue**
   - ✅ 添加 `inferAgentType()` 辅助函数
   - ✅ 调用 API 时传递 `agent_type` 参数
   - ✅ 在 `setAsActiveTemplate()` 中也使用 `agent_type`

## 🎯 FastAPI 路由匹配规则

**重要原则**：
1. FastAPI 按照路由定义的顺序进行匹配
2. 更具体的路由应该放在前面
3. 带路径参数的通配路由应该放在最后

**示例**：
```python
# ✅ 正确
@router.get("/active")      # 具体路径
@router.get("/user/{id}")   # 具体前缀 + 参数
@router.get("/{id}")        # 通配参数

# ❌ 错误
@router.get("/{id}")        # 会匹配所有路径
@router.get("/active")      # 永远不会被匹配到
```

### 4. 修复前端参数传递方式

**问题**：前端调用 `ApiClient.get()` 时参数传递错误

**错误代码**：
```typescript
// ❌ 错误：params 被嵌套在对象中
const response = await ApiClient.get('/api/v1/user-template-configs/active', {
  params: {
    user_id: userId,
    agent_name: agent.value.id
  }
})

// 实际发送的 URL:
// /api/v1/user-template-configs/active?params[user_id]=xxx&params[agent_name]=xxx
```

**正确代码**：
```typescript
// ✅ 正确：直接传递 params 对象
const response = await ApiClient.get('/api/v1/user-template-configs/active', {
  user_id: userId,
  agent_name: agent.value.id,
  agent_type: agentType
})

// 实际发送的 URL:
// /api/v1/user-template-configs/active?user_id=xxx&agent_name=xxx&agent_type=xxx
```

**原因**：
`ApiClient.get()` 的签名是：
```typescript
static async get<T = any>(
  url: string,
  params?: any,           // 第二个参数直接是 params
  config?: RequestConfig  // 第三个参数是 config
)
```

所以第二个参数应该直接是查询参数对象，而不是包含 `params` 键的对象。

## 🧪 测试

测试 API 是否正常工作：

```bash
# 测试获取当前生效模板
curl "http://localhost:8000/api/v1/user-template-configs/active?user_id=xxx&agent_name=sector_analyst_v2&agent_type=analysts_v2"

# 预期返回
{
  "success": true,
  "data": {
    "id": "...",
    "template_id": "...",
    "is_active": true
  }
}

# 或者（未设置时）
{
  "success": true,
  "data": null
}
```

---

**修复日期**: 2026-01-09
**问题类型**:
1. 路由匹配顺序错误
2. 前端参数传递方式错误

**影响范围**: 提示词模板选择功能

