# Agent 详情页 - 提示词模板选择器

## 📋 功能概述

为 Agent 详情页添加提示词模板选择器，允许用户：
1. 查看所有可用的提示词模板（3个系统模板 + 用户自定义模板）
2. 切换查看不同模板的内容
3. 设置当前生效的模板
4. 编辑模板内容

---

## 🎯 问题背景

每个 Agent 都有 3 个系统提示词模板：
- **aggressive** - 激进型
- **neutral** - 中性型（默认）
- **conservative** - 保守型

原先的实现只显示一个模板，用户无法选择。

---

## ✅ 解决方案

### 1. 模板列表加载

```typescript
// 加载所有可用模板（包括 active 和 draft 状态）
// 注意：不过滤 status，以便显示用户的草稿模板
const response = await TemplatesApi.list({
  agent_name: agent.value.id, // 如 sector_analyst_v2
  skip: 0,
  limit: 20
})

promptTemplates.value = response.data?.items || []
```

**重要说明**：
- 用户克隆的模板默认状态为 `draft`（草稿）
- 如果只查询 `status: 'active'`，用户模板不会显示
- 因此不过滤 status，同时显示 active 和 draft 状态的模板

### 2. 获取当前生效模板

```typescript
// 获取用户设置的当前生效模板
const response = await ApiClient.get('/api/v1/user-template-configs/active', {
  params: {
    user_id: userId,
    agent_name: agent.value.id
  }
})

activeTemplateId.value = response.data?.template_id
```

### 3. 默认模板选择逻辑

```typescript
if (activeTemplateId.value) {
  // 如果用户设置了当前模板，使用用户设置的
  templateIdToShow = activeTemplateId.value
} else {
  // 否则使用系统默认的 neutral 模板
  const neutralTemplate = items.find(t => 
    t.is_system && t.preference_type === 'neutral'
  )
  templateIdToShow = neutralTemplate?.id || items[0]?.id
}
```

### 4. 设置为当前模板

```typescript
const setAsActiveTemplate = async () => {
  const body = {
    agent_type: promptTemplate.value.agent_type,
    agent_name: promptTemplate.value.agent_name,
    template_id: selectedTemplateId.value
  }

  await ApiClient.post('/api/v1/user-template-configs', body, {
    params: { user_id: userId }
  })

  activeTemplateId.value = selectedTemplateId.value
}
```

---

## 🎨 UI 设计

### 模板选择器

```vue
<div class="template-selector">
  <div class="selector-label">选择模板:</div>
  <el-select v-model="selectedTemplateId" @change="handleTemplateChange">
    <el-option
      v-for="template in promptTemplates"
      :key="template.id"
      :label="`${template.template_name} (${template.preference_type})`"
      :value="template.id"
    >
      <div style="display: flex; justify-content: space-between;">
        <span>{{ template.template_name }}</span>
        <div>
          <el-tag>{{ template.preference_type }}</el-tag>
          <el-tag>{{ template.is_system ? '系统' : '用户' }}</el-tag>
          <el-tag v-if="template.status === 'draft'">草稿</el-tag>
          <el-tag v-if="template.id === activeTemplateId">当前生效</el-tag>
        </div>
      </div>
    </el-option>
  </el-select>
  <el-button 
    v-if="selectedTemplateId !== activeTemplateId"
    @click="setAsActiveTemplate"
  >
    设为当前
  </el-button>
</div>
```

### 样式

```scss
.template-selector {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: #f5f7fa;
  border-radius: 8px;
  margin-bottom: 20px;
}
```

---

## 📊 数据流

```
1. 页面加载
   ↓
2. 获取所有可用模板 (TemplatesApi.list)
   ↓
3. 获取用户当前生效模板 ID (user-template-configs/active)
   ↓
4. 确定默认显示的模板
   - 有用户设置 → 使用用户设置
   - 无用户设置 → 使用 neutral 系统模板
   ↓
5. 加载模板详情 (TemplatesApi.get)
   ↓
6. 显示模板内容
```

---

## 🔑 关键点

1. **模板类型**
   - 系统模板：3个（aggressive, neutral, conservative），状态为 `active`
   - 用户模板：用户克隆或创建的自定义模板，默认状态为 `draft`

2. **模板状态**
   - `active`：已激活的模板（系统模板默认为 active）
   - `draft`：草稿模板（用户克隆的模板默认为 draft）
   - **重要**：查询时不过滤 status，否则用户模板不会显示

3. **当前生效模板**
   - 存储在 `user_template_configs` 集合
   - 每个用户每个 Agent 只有一个当前生效模板
   - 未设置时默认使用 neutral 系统模板

4. **模板切换**
   - 切换选择器 → 加载新模板详情
   - 点击"设为当前" → 调用 API 设置当前生效模板

5. **模板编辑**
   - 系统模板不能直接编辑
   - 编辑时自动克隆为用户模板
   - 保存后重新加载模板列表

---

**最后更新**: 2026-01-09  
**版本**: v1.0.1

