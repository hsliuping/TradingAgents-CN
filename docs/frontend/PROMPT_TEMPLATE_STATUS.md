# 提示词模板状态管理

## 📋 概述

提示词模板支持两种状态：
- **草稿（draft）** - 未发布的模板，仅用户自己可见
- **已发布（active）** - 正式发布的模板，可以被使用

---

## 🔄 状态流转

### 状态定义

```typescript
type TemplateStatus = 'draft' | 'active'
```

### 状态流转图

```
创建模板
   ↓
[草稿 draft] ──发布──→ [已发布 active]
   ↑                        ↓
   └────────编辑────────────┘
```

---

## 💡 使用场景

### 场景 1: 保存为草稿

**用途**：
- 模板还在编辑中，不想立即发布
- 需要测试或审核后再发布
- 临时保存，避免丢失

**操作**：
1. 点击"编辑"按钮
2. 修改提示词内容
3. 点击"保存为草稿"按钮

**效果**：
- 模板状态为 `draft`
- 显示"草稿"标签（蓝色）
- 不会自动设为当前生效模板

### 场景 2: 直接发布

**用途**：
- 模板已经完成，可以立即使用
- 希望立即生效

**操作**：
1. 点击"编辑"按钮
2. 修改提示词内容
3. 点击"发布"按钮

**效果**：
- 模板状态为 `active`
- 可以设为当前生效模板
- 可以在工作流中使用

### 场景 3: 发布草稿

**用途**：
- 草稿已经完成，准备发布
- 审核通过，可以正式使用

**操作**：
1. 在查看模式下，找到草稿模板
2. 点击"发布"按钮（绿色，带 ✓ 图标）

**效果**：
- 模板状态从 `draft` 变为 `active`
- "草稿"标签消失
- 可以设为当前生效模板

---

## 🎨 界面显示

### 查看模式

**草稿模板**：
```
┌─────────────────────────────────────────┐
│ [市场分析师 v2.0] [neutral] [用户] [草稿] [✓ 发布] │
└─────────────────────────────────────────┘
```

**已发布模板**：
```
┌─────────────────────────────────────────┐
│ [市场分析师 v2.0] [neutral] [用户] [当前生效] │
└─────────────────────────────────────────┘
```

### 编辑模式

```
┌─────────────────────────────────────────┐
│ 📝 提示词模板                  [取消] [保存为草稿] [发布] │
│                                         │
│ 系统提示词:                              │
│ ┌─────────────────────────────────────┐ │
│ │ 你是一位专业的市场分析师...          │ │
│ └─────────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

---

## 🔧 技术实现

### 1. 数据模型

```typescript
// app/models/prompt_template.py
class PromptTemplate(BaseModel):
    status: str = Field(default="active", description="模板状态: draft, active")
```

### 2. 保存提示词（带状态）

```typescript
// frontend/src/views/Workflow/AgentDetail.vue
const savePrompt = async (status: 'draft' | 'active' = 'active') => {
  const updateData = {
    content: {
      system_prompt: editingPrompt.value.system_prompt,
      tool_guidance: editingPrompt.value.tool_guidance,
      analysis_requirements: editingPrompt.value.analysis_requirements,
      output_format: editingPrompt.value.output_format
    },
    remark: editingPrompt.value.remark,
    status: status  // 设置状态
  }

  const updateResponse = await TemplatesApi.update(templateId, updateData)
  
  const statusText = status === 'draft' ? '草稿已保存' : '发布成功'
  ElMessage.success(statusText)
}
```

### 3. 发布草稿

```typescript
const publishTemplate = async () => {
  const updateData = {
    status: 'active'
  }

  const updateResponse = await TemplatesApi.update(promptTemplate.value.id, updateData)
  
  ElMessage.success('发布成功')
  await loadPromptTemplates(agent.value.id)
}
```

### 4. 界面按钮

**编辑模式**：
```vue
<el-button size="small" @click="savePrompt('draft')">
  保存为草稿
</el-button>
<el-button size="small" type="primary" @click="savePrompt('active')">
  发布
</el-button>
```

**查看模式**：
```vue
<el-button
  v-if="promptTemplate.status === 'draft' && !promptTemplate.is_system"
  size="small"
  type="success"
  @click="publishTemplate"
>
  <el-icon><Check /></el-icon> 发布
</el-button>
```

---

## ⚠️ 注意事项

### 1. 系统模板不能修改状态

系统模板始终是 `active` 状态，不能修改为 `draft`。

### 2. 草稿模板不能设为当前生效

只有 `active` 状态的模板才能设为当前生效模板。

### 3. 状态过滤

在加载模板列表时，**不过滤** `draft` 状态的模板，以便用户可以看到自己的草稿：

```typescript
const response = await TemplatesApi.list({
  agent_name: agent.value.id,
  skip: 0,
  limit: 20
  // 不添加 status 过滤
})
```

---

## 📚 相关文档

- [提示词模板变量系统](../prompts/PROMPT_TEMPLATE_VARIABLES.md)
- [Agent 工具配置显示](./AGENT_TOOL_CONFIG_DISPLAY.md)

---

**最后更新**: 2026-01-09  
**版本**: v1.0.1

