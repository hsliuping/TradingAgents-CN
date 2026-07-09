# Agent 工具配置显示优化

## 📋 问题背景

原先的工具配置卡片只显示：
- ✅ 中文工具名称（如"统一市场数据"）
- ✅ 工具描述

**缺少的关键信息**：
- ❌ 英文工具 ID（用户编写提示词时需要）
- ❌ 工具参数列表（用户需要知道如何传参）

这导致用户在编写提示词时不知道：
1. 应该使用哪个英文 ID 来调用工具
2. 工具需要哪些参数

---

## ✅ 解决方案

### 1. 显示工具 ID

在工具卡片中添加工具 ID 显示：

```vue
<div class="tool-id">
  <span class="label">工具ID:</span>
  <el-tag size="small" type="info" effect="plain">
    <code>{{ tool.id }}</code>
  </el-tag>
  <el-button size="small" text @click="copyToolId(tool.id)">
    <el-icon><CopyDocument /></el-icon>
  </el-button>
</div>
```

**特性**：
- 使用 `<code>` 标签显示，等宽字体更清晰
- 提供复制按钮，一键复制到剪贴板
- 使用 `el-tag` 包裹，视觉上更突出

### 2. 显示工具参数

在工具卡片中添加参数列表：

```vue
<div v-if="tool.parameters && tool.parameters.length > 0" class="tool-params">
  <span class="label">参数:</span>
  <div class="params-list">
    <el-tag 
      v-for="param in tool.parameters" 
      :key="param.name"
      size="small"
      :type="param.required ? 'warning' : 'info'"
      effect="plain"
    >
      {{ param.name }}
      <span v-if="param.required">*</span>
      <span style="color: #909399;"> : {{ param.type }}</span>
    </el-tag>
  </div>
</div>
```

**特性**：
- 显示参数名称和类型
- 必填参数用 `*` 标记，并使用 `warning` 类型高亮
- 可选参数使用 `info` 类型
- 参数类型用灰色显示，更易区分

### 3. 复制功能

添加复制工具 ID 的函数：

```typescript
const copyToolId = async (toolId: string) => {
  try {
    await navigator.clipboard.writeText(toolId)
    ElMessage.success('工具 ID 已复制到剪贴板')
  } catch (error) {
    ElMessage.error('复制失败，请手动复制')
  }
}
```

---

## 🎨 界面效果

### 优化前

```
┌─────────────────────────────────┐
│ 📈 统一市场数据                  │
│ 获取股票市场数据的统一接口        │
└─────────────────────────────────┘
```

### 优化后

```
┌─────────────────────────────────────────────────┐
│ 📈 统一市场数据                    [默认]        │
│ 获取股票市场数据的统一接口                       │
│                                                 │
│ 工具ID: [get_stock_market_data_unified] 📋      │
│                                                 │
│ 参数:                                           │
│ [ticker*: string] [trade_date: string]          │
└─────────────────────────────────────────────────┘
```

**说明**：
- `[默认]` - 绿色标签，表示默认工具
- `[get_stock_market_data_unified]` - 蓝色标签，可复制
- `📋` - 复制按钮
- `ticker*` - 橙色标签，必填参数
- `trade_date` - 蓝色标签，可选参数

---

## 💡 用户体验改进

### 改进 1: 一目了然

用户可以直接看到：
- ✅ 工具的英文 ID
- ✅ 工具需要哪些参数
- ✅ 哪些参数是必填的

### 改进 2: 快速复制

- 点击复制按钮，工具 ID 自动复制到剪贴板
- 直接粘贴到提示词编辑器中

### 改进 3: 编写提示词更容易

**示例**：

看到工具卡片显示：
```
工具ID: get_stock_market_data_unified
参数: ticker* : string, trade_date : string
```

用户可以直接在提示词中写：
```markdown
调用 `get_stock_market_data_unified` 工具
参数: ticker={ticker}, trade_date={current_date}
```

---

## 🔧 技术实现

### 1. 导入图标

```typescript
import { CopyDocument } from '@element-plus/icons-vue'
```

### 2. 模板修改

在 `frontend/src/views/Workflow/AgentDetail.vue` 的工具卡片中添加：
- 工具 ID 显示区域
- 参数列表显示区域

### 3. 样式添加

```scss
.tool-id {
  margin-top: 8px;
  display: flex;
  align-items: center;
  gap: 4px;
  
  code {
    font-family: 'Consolas', 'Monaco', monospace;
    font-size: 12px;
  }
}

.tool-params {
  margin-top: 8px;
  
  .params-list {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
  }
}
```

---

## 📝 相关文档

- [工具名称 vs 工具 ID](../prompts/TOOL_NAME_VS_TOOL_ID.md)
- [多工具调用指导](../prompts/MULTI_TOOL_GUIDANCE.md)

---

## 🔄 相关改进：提示词变量说明

### 问题

用户在编辑提示词时，不知道有哪些变量可用，也不知道这些变量是如何填充的。

### 解决方案

在提示词模板区域添加"可用变量说明"：

#### 1. 查看模式 - 折叠面板

在查看提示词模板时，添加一个可折叠的"可用变量说明"面板：

```vue
<el-collapse>
  <el-collapse-item name="variables">
    <template #title>
      <div style="display: flex; align-items: center; gap: 6px;">
        <el-icon><InfoFilled /></el-icon>
        <span>可用变量说明</span>
      </div>
    </template>
    <el-descriptions :column="2" border size="small">
      <el-descriptions-item label="ticker">
        股票代码（来自输入参数）
      </el-descriptions-item>
      <el-descriptions-item label="company_name">
        公司名称（系统自动获取）
      </el-descriptions-item>
      <!-- ... 更多变量 -->
    </el-descriptions>
  </el-collapse-item>
</el-collapse>
```

#### 2. 编辑模式 - 提示框

在编辑提示词时，在顶部显示一个醒目的提示框：

```vue
<el-alert type="info" :closable="false">
  <template #title>
    <div style="display: flex; align-items: center; gap: 8px;">
      <el-icon><InfoFilled /></el-icon>
      <span>可用变量说明</span>
    </div>
  </template>
  <div style="line-height: 1.8;">
    <p>提示词中可以使用以下变量（系统会自动填充）：</p>
    <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px;">
      <div><code>{ticker}</code> - 股票代码</div>
      <div><code>{company_name}</code> - 公司名称（自动获取）</div>
      <!-- ... 更多变量 -->
    </div>
  </div>
</el-alert>
```

### 效果

**查看模式**：
```
┌─────────────────────────────────────────┐
│ 📝 提示词模板                            │
│                                         │
│ [选择模板: 第一个市场分析师 v2.0]        │
│                                         │
│ ▶ ℹ️ 可用变量说明                       │
│                                         │
│ [系统提示词] [用户提示词] [工具指导]     │
│ 你是一位专业的市场分析师...              │
└─────────────────────────────────────────┘
```

**编辑模式**：
```
┌─────────────────────────────────────────┐
│ 📝 提示词模板                            │
│                                         │
│ ℹ️ 可用变量说明                         │
│ 提示词中可以使用以下变量（系统会自动填充）│
│ • {ticker} - 股票代码                   │
│ • {company_name} - 公司名称（自动获取） │
│ • {market_name} - 市场名称（自动识别）  │
│ ...                                     │
│                                         │
│ 系统提示词:                              │
│ ┌─────────────────────────────────────┐ │
│ │ 你是{company_name}的分析师...        │ │
│ └─────────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

---

**最后更新**: 2026-01-09
**版本**: v1.0.1

