# 提示词模板变量提示功能

## 📋 概述

在编辑提示词模板时，显示可用的系统变量说明，帮助用户了解可以使用哪些变量。

---

## 🎯 功能位置

### 1. Agent 详情页 - 提示词编辑

**路径**: `工作流管理 → Agent 详情 → 提示词模板 → 编辑`

**文件**: `frontend/src/views/Workflow/AgentDetail.vue`

### 2. 模板管理页 - 模板编辑

**路径**: `设置 → 模板管理 → 编辑模板`

**文件**: `frontend/src/views/Settings/TemplateManagement.vue`

---

## 🎨 界面效果

### 变量说明卡片

```
┌─────────────────────────────────────────────────────────┐
│ ℹ️ 可用变量说明                                          │
├─────────────────────────────────────────────────────────┤
│ 提示词中可以使用以下变量（系统会自动填充）：              │
│                                                          │
│ {ticker} - 股票代码          {company_name} - 公司名称   │
│ {market_name} - 市场名称     {current_date} - 当前日期   │
│ {currency_name} - 货币名称   {currency_symbol} - 货币符号│
│ {tool_names} - 可用工具列表  {start_date} - 开始日期     │
│                                                          │
│ 💡 这些变量会在运行时自动从工作流状态中提取，无需用户手动提供 │
└─────────────────────────────────────────────────────────┘
```

### 编辑表单

```
┌─────────────────────────────────────────────────────────┐
│ 系统提示词                                               │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ 你是{company_name}的分析师...                        │ │
│ │                                                      │ │
│ └─────────────────────────────────────────────────────┘ │
│ 请输入系统提示词，可使用上方的变量，如：你是{company_name}的分析师... │
└─────────────────────────────────────────────────────────┘
```

---

## 📝 可用变量列表

### 基础变量

| 变量 | 说明 | 示例值 |
|------|------|--------|
| `{ticker}` | 股票代码 | `000858.SZ` |
| `{company_name}` | 公司名称（自动获取） | `五粮液` |
| `{market_name}` | 市场名称（自动识别） | `中国A股` |
| `{current_date}` | 当前日期 | `2026-01-09` |

### 货币相关

| 变量 | 说明 | 示例值 |
|------|------|--------|
| `{currency_name}` | 货币名称 | `人民币` |
| `{currency_symbol}` | 货币符号 | `¥` |

### 工具和日期

| 变量 | 说明 | 示例值 |
|------|------|--------|
| `{tool_names}` | 可用工具列表 | `get_stock_fundamentals_unified` |
| `{start_date}` | 开始日期（1年前） | `2025-01-09` |

---

## 🔧 技术实现

### 1. 变量说明组件

```vue
<el-alert
  type="info"
  :closable="false"
  style="margin-bottom: 16px;"
>
  <template #title>
    <div style="display: flex; align-items: center; gap: 8px;">
      <el-icon><InfoFilled /></el-icon>
      <span>可用变量说明</span>
    </div>
  </template>
  <div style="line-height: 1.8; font-size: 13px;">
    <p style="margin: 0 0 8px 0;">提示词中可以使用以下变量（系统会自动填充）：</p>
    <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px;">
      <div><code>{ticker}</code> - 股票代码</div>
      <div><code>{company_name}</code> - 公司名称（自动获取）</div>
      <div><code>{market_name}</code> - 市场名称（自动识别）</div>
      <div><code>{current_date}</code> - 当前日期</div>
      <div><code>{currency_name}</code> - 货币名称</div>
      <div><code>{currency_symbol}</code> - 货币符号</div>
      <div><code>{tool_names}</code> - 可用工具列表</div>
      <div><code>{start_date}</code> - 开始日期（1年前）</div>
    </div>
    <p style="margin: 8px 0 0 0; color: #909399; font-size: 12px;">
      💡 这些变量会在运行时自动从工作流状态中提取，无需用户手动提供
    </p>
  </div>
</el-alert>
```

### 2. 输入框 Placeholder

```vue
<el-input
  v-model="editForm.content.system_prompt"
  type="textarea"
  placeholder="请输入系统提示词，可使用上方的变量，如：你是{company_name}的分析师..."
/>
```

### 3. 导入图标

```typescript
import { InfoFilled } from '@element-plus/icons-vue'
```

---

## 💡 使用示例

### 示例 1: 基本面分析师提示词

```
你是一位专业的基本面分析师 v2.0。

**分析目标**: {company_name}（{ticker}，{market_name}）
**分析日期**: {current_date}

请使用{currency_name}（{currency_symbol}）进行所有金额表述。
```

**渲染后**：
```
你是一位专业的基本面分析师 v2.0。

**分析目标**: 五粮液（000858.SZ，中国A股）
**分析日期**: 2026-01-09

请使用人民币（¥）进行所有金额表述。
```

### 示例 2: 市场分析师提示词

```
你是{company_name}的市场分析师。

分析时间范围：{start_date} 至 {current_date}
可用工具：{tool_names}
```

**渲染后**：
```
你是五粮液的市场分析师。

分析时间范围：2025-01-09 至 2026-01-09
可用工具：get_stock_fundamentals_unified
```

---

## ⚠️ 注意事项

### 1. 变量自动填充

- ✅ 变量由系统在运行时自动填充
- ✅ 从工作流状态（Workflow State）中提取
- ❌ 不需要用户手动提供

### 2. 变量格式

- ✅ 使用花括号 `{variable_name}`
- ❌ 不要使用双花括号 `{{variable_name}}`（那是旧格式）

### 3. 变量可用性

- ✅ 所有 Agent 都可以使用这些基础变量
- ✅ 不同 Agent 可能有额外的专属变量
- ✅ 变量列表会随着系统更新而扩展

---

## 📚 相关文档

- [提示词模板变量系统](../prompts/PROMPT_TEMPLATE_VARIABLES.md)
- [提示词模板状态管理](./PROMPT_TEMPLATE_STATUS.md)
- [Agent 工具配置显示](./AGENT_TOOL_CONFIG_DISPLAY.md)

---

**最后更新**: 2026-01-09  
**版本**: v1.0.1

