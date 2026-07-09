# Agent 详情页面改进说明

## 📋 改进概述

本次改进针对 Agent 详情页面（`AgentDetail.vue`）进行了三个主要优化：

1. ✅ **输入/输出参数显示优化** - 从 JSON 格式改为结构化卡片展示
2. ✅ **提示词模板集成** - 从后台获取并显示 Agent 的提示词模板
3. ✅ **提示词模板编辑** - 支持在线编辑提示词模板

---

## 🎯 问题 1: 输入/输出参数显示问题

### 问题描述
- 原先显示的是原始 JSON 字符串格式
- 不易阅读，用户体验差

### 解决方案
- 添加了 `parsedInputs` 和 `parsedOutputs` 计算属性
- 自动解析 JSON 字符串为对象
- 使用卡片式布局展示参数详情

### 显示内容
每个参数卡片包含：
- **参数名称** - 使用 Tag 标签显示
- **必填/可选** - 红色/灰色标签区分
- **参数描述** - 详细说明
- **参数类型** - 数据类型信息

### 代码示例
```vue
<div class="io-param">
  <div class="param-header">
    <el-tag type="info" size="small">{{ input.name }}</el-tag>
    <el-tag v-if="input.required" type="danger" size="small">必填</el-tag>
  </div>
  <div class="param-desc">{{ input.description }}</div>
  <div class="param-meta">
    <span class="meta-item">类型: {{ input.type }}</span>
  </div>
</div>
```

---

## 🎯 问题 2: 提示词模板获取

### 问题描述
- 原先显示"暂无提示词模板"
- 未从后台获取实际的模板数据

### 解决方案
- 使用 `getTemplatesByAgent(agent.name)` 获取模板列表
- 调用 `TemplatesApi.get(templateId)` 获取完整模板详情（包含 content）
- 优先显示系统模板

### API 调用流程
```typescript
// 1. 根据 agent_name 获取模板列表
const response = await getTemplatesByAgent(agent.value.name)

// 2. 获取第一个模板的 ID
const templateId = response.data[0].id

// 3. 获取完整模板详情
const detailResponse = await TemplatesApi.get(templateId)

// 4. 保存模板数据
promptTemplate.value = detailResponse.data
```

### 显示内容
- **模板元信息** - 模板名称、偏好类型、系统/用户标签
- **系统提示词** - Agent 的核心指令
- **工具指导** - 工具使用说明
- **分析要求** - 分析任务要求
- **输出格式** - 输出格式规范
- **备注** - 额外说明信息

---

## 🎯 问题 3: 提示词模板编辑

### 问题描述
- 原先只能查看，无法编辑
- 缺少提示词模板的管理功能

### 解决方案
- 添加"编辑"按钮切换到编辑模式
- 使用 `el-input` 的 `textarea` 类型编辑各个字段
- 支持系统模板克隆为用户模板后编辑
- 调用 `TemplatesApi.update()` 保存修改

### 编辑流程
```typescript
// 1. 点击编辑按钮
startEditPrompt() {
  // 复制当前模板内容到编辑表单
  editingPrompt.value = { ...promptTemplate.value.content }
  isEditingPrompt.value = true
}

// 2. 保存修改
savePrompt() {
  // 如果是系统模板，先克隆
  if (promptTemplate.value.is_system) {
    await TemplatesApi.clone(templateId, newName)
  }
  
  // 更新模板内容
  await TemplatesApi.update(templateId, updateData)
  
  // 重新加载
  await loadPromptTemplate(agent.value.id)
}
```

### 编辑字段
- ✏️ 系统提示词 (6 行)
- ✏️ 工具指导 (4 行)
- ✏️ 分析要求 (4 行)
- ✏️ 输出格式 (4 行)
- ✏️ 备注 (2 行)

---

## 📁 修改的文件

### 1. `frontend/src/views/Workflow/AgentDetail.vue`
- ✅ 添加输入/输出参数解析逻辑
- ✅ 添加提示词模板加载逻辑
- ✅ 添加提示词模板编辑功能
- ✅ 优化样式和布局

### 2. `frontend/src/api/templates.ts`
- ✅ 添加 `update()` 方法用于更新模板
- ✅ 添加 `getTemplatesByAgent()` 便捷函数

### 3. `frontend/src/router/index.ts`
- ✅ 添加 `AgentDetail` 路由配置

### 4. `frontend/src/views/Workflow/Agents.vue`
- ✅ 修改"查看详情"按钮跳转到详情页面
- ✅ 删除旧的对话框代码

---

## 🎨 样式改进

### 输入/输出参数卡片
```scss
.io-param {
  padding: 12px;
  background: #f5f7fa;
  border-radius: 8px;
  border-left: 3px solid #409eff; // 左侧蓝色边框
}
```

### 提示词编辑器
```scss
.edit-mode {
  :deep(.el-textarea__inner) {
    font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
    font-size: 13px;
    line-height: 1.6;
  }
}
```

---

## 🚀 使用方法

1. **查看 Agent 详情**
   - 在 Agent 列表页点击"查看详情"
   - 自动跳转到 `/workflow/agents/:id` 页面

2. **查看输入/输出参数**
   - 左侧卡片显示结构化的参数信息
   - 包含参数名、类型、描述、是否必填

3. **查看提示词模板**
   - 右侧卡片显示 Agent 的提示词模板
   - 切换 Tab 查看不同部分

4. **编辑提示词模板**
   - 点击"编辑"按钮进入编辑模式
   - 修改各个字段
   - 点击"保存"提交更新
   - 系统模板会自动克隆为用户模板

---

**最后更新**: 2026-01-09  
**版本**: v1.0.1

