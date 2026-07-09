# 提示词模板更新权限问题修复

## 🐛 问题描述

**症状**：
用户尝试更新或发布提示词模板时，返回错误：
```json
{
  "success": false,
  "data": null,
  "message": "更新模板失败或无权限",
  "code": 400,
  "timestamp": "2026-01-09T14:20:29.189984+08:00"
}
```

**影响范围**：
- ✅ 编辑提示词后保存
- ✅ 发布草稿模板
- ✅ 修改模板状态

---

## 🔍 根本原因

### 后端权限验证逻辑

```python
# app/services/prompt_template_service.py
async def update_template(
    self,
    template_id: str,
    update_data: PromptTemplateUpdate,
    user_id: Optional[str] = None  # ← 需要 user_id
) -> Optional[PromptTemplate]:
    template = await self.get_template(template_id)
    
    # 验证权限
    if not template.is_system and str(template.created_by) != user_id:
        logger.warning(f"用户 {user_id} 无权修改模板 {template_id}")
        return None  # ← 返回 None，导致 400 错误
```

### 后端 API 定义

```python
# app/routers/prompt_templates.py
@router.put("/{template_id}", response_model=dict)
async def update_template(
    template_id: str,
    update_data: PromptTemplateUpdate,
    user_id: Optional[str] = Query(None),  # ← user_id 作为查询参数
    template_service: PromptTemplateService = Depends(get_template_service)
):
    template = await template_service.update_template(
        template_id,
        update_data,
        user_id=user_id  # ← 传递给 service
    )
    
    if not template:
        return fail("更新模板失败或无权限", 400)  # ← 这里返回 400
```

### 前端 API 调用（修复前）

```typescript
// frontend/src/api/templates.ts
async update(template_id: string, data: any): Promise<ApiResponse<any>> {
  return ApiClient.put(`/api/v1/templates/${template_id}`, data)
  // ❌ 没有传递 user_id 参数
}
```

### 前端调用（修复前）

```typescript
// frontend/src/views/Workflow/AgentDetail.vue
const publishTemplate = async () => {
  const userId = useAuthStore().user?.id  // ← 获取了 userId
  
  const updateData = {
    status: 'active'
  }
  
  const updateResponse = await TemplatesApi.update(promptTemplate.value.id, updateData)
  // ❌ 没有传递 userId
}
```

---

## ✅ 解决方案

### 1. 修改前端 API 函数

```typescript
// frontend/src/api/templates.ts
async update(template_id: string, data: any, user_id?: string): Promise<ApiResponse<any>> {
  const params: Record<string, any> = {}
  if (user_id) params.user_id = user_id
  return ApiClient.put(`/api/v1/templates/${template_id}`, data, { params })
  // ✅ 将 user_id 作为查询参数传递
}
```

### 2. 修改前端调用（发布模板）

```typescript
// frontend/src/views/Workflow/AgentDetail.vue
const publishTemplate = async () => {
  const userId = useAuthStore().user?.id
  
  const updateData = {
    status: 'active'
  }
  
  const updateResponse = await TemplatesApi.update(
    promptTemplate.value.id, 
    updateData, 
    userId  // ✅ 传递 userId
  )
}
```

### 3. 修改前端调用（保存提示词）

```typescript
const savePrompt = async (status: 'draft' | 'active' = 'active') => {
  const userId = useAuthStore().user?.id
  
  // ... 克隆系统模板逻辑 ...
  
  const updateData = {
    content: { ... },
    remark: editingPrompt.value.remark,
    status: status
  }
  
  const updateResponse = await TemplatesApi.update(
    templateId, 
    updateData, 
    userId  // ✅ 传递 userId
  )
}
```

---

## 🔄 请求流程对比

### 修复前

```
前端调用
  ↓
PUT /api/v1/templates/{template_id}
Body: { status: 'active' }
  ↓
后端接收: user_id = None
  ↓
权限验证: str(template.created_by) != None
  ↓
验证失败 → 返回 None
  ↓
返回 400 错误: "更新模板失败或无权限"
```

### 修复后

```
前端调用
  ↓
PUT /api/v1/templates/{template_id}?user_id=xxx
Body: { status: 'active' }
  ↓
后端接收: user_id = 'xxx'
  ↓
权限验证: str(template.created_by) == 'xxx'
  ↓
验证成功 → 更新模板
  ↓
返回 200 成功
```

---

## 📝 测试验证

### 测试场景 1: 发布草稿模板

**操作**：
1. 创建一个草稿模板
2. 点击"发布"按钮

**预期结果**：
- ✅ 状态从 `draft` 变为 `active`
- ✅ 显示"发布成功"消息
- ✅ "草稿"标签消失

### 测试场景 2: 保存为草稿

**操作**：
1. 编辑提示词
2. 点击"保存为草稿"

**预期结果**：
- ✅ 内容保存成功
- ✅ 状态为 `draft`
- ✅ 显示"草稿已保存"消息

### 测试场景 3: 直接发布

**操作**：
1. 编辑提示词
2. 点击"发布"

**预期结果**：
- ✅ 内容保存成功
- ✅ 状态为 `active`
- ✅ 显示"发布成功"消息

---

## ⚠️ 注意事项

### 1. 权限验证逻辑

后端验证规则：
- ✅ 系统模板不允许直接编辑
- ✅ 用户模板只能由创建者编辑
- ✅ `user_id` 必须与 `created_by` 匹配

### 2. 其他使用 `TemplatesApi.update` 的地方

需要检查并修复所有调用 `TemplatesApi.update` 的地方：

**已修复**：
- ✅ `frontend/src/views/Workflow/AgentDetail.vue` - `publishTemplate()`
- ✅ `frontend/src/views/Workflow/AgentDetail.vue` - `savePrompt()`

**已正确实现**：
- ✅ `frontend/src/views/Settings/TemplateManagement.vue` - 已经传递 `user_id`

---

## 📚 相关文档

- [提示词模板状态管理](../frontend/PROMPT_TEMPLATE_STATUS.md)
- [提示词模板变量系统](../prompts/PROMPT_TEMPLATE_VARIABLES.md)

---

**修复日期**: 2026-01-09  
**影响版本**: v1.0.1  
**修复状态**: ✅ 已修复

