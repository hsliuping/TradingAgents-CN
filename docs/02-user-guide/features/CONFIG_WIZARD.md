# 配置向导使用说明

## 📖 概述

配置向导（ConfigWizard）是一个引导式的配置界面，帮助用户在首次使用系统时快速完成必要的配置。

## 🎯 功能特点

- **5步引导流程**：欢迎 → 数据库配置 → 大模型配置 → 数据源配置 → 完成
- **智能触发**：自动检测配置缺失并弹出向导
- **表单验证**：实时验证用户输入
- **动态选项**：根据选择动态显示相关配置项
- **友好提示**：提供获取 API 密钥的帮助链接

## 🚀 触发机制

### 自动触发条件

配置向导会在以下情况下自动显示：

1. **用户已登录**
2. **localStorage 中没有 `config_wizard_completed` 标记**
3. **后端 API `/api/system/config/validate` 返回有缺失的必需配置**

### 触发流程

```
用户登录
  ↓
App.vue onMounted
  ↓
检查 localStorage.getItem('config_wizard_completed')
  ↓ (未完成)
调用 /api/system/config/validate API
  ↓
检查 result.missing_required.length > 0
  ↓ (有缺失)
延迟 1 秒后显示配置向导
```

### 代码实现

<augment_code_snippet path="frontend/src/App.vue" mode="EXCERPT">
````typescript
// 检查是否需要显示配置向导
const checkFirstTimeSetup = async () => {
  try {
    // 检查是否已经完成过配置向导
    const wizardCompleted = localStorage.getItem('config_wizard_completed')
    if (wizardCompleted === 'true') {
      return
    }

    // 验证配置完整性
    const response = await axios.get('/api/system/config/validate')
    if (response.data.success) {
      const result = response.data.data

      // 如果有缺少的必需配置，显示配置向导
      if (!result.success && result.missing_required?.length > 0) {
        // 延迟显示，等待页面加载完成
        setTimeout(() => {
          showConfigWizard.value = true
        }, 1000)
      }
    }
  } catch (error) {
    console.error('检查配置失败:', error)
  }
}
````
</augment_code_snippet>

## 📋 配置步骤

### 步骤 0：欢迎页面

- 显示欢迎信息
- 说明配置向导的作用
- 提供"开始配置"和"跳过向导"按钮

### 步骤 1：数据库配置

配置 MongoDB 和 Redis 连接信息：

**MongoDB**:
- 主机地址（默认：localhost）
- 端口（默认：27017）
- 数据库名（默认：tradingagents）

**Redis**:
- 主机地址（默认：localhost）
- 端口（默认：6379）

> **注意**：数据库配置需要在 `.env` 文件中设置，此处仅用于验证连接。

### 步骤 2：大模型配置

选择并配置大模型 API：

**支持的大模型**:
- DeepSeek（推荐，性价比高）
- 通义千问（推荐，国产稳定）
- OpenAI
- Google Gemini

**配置项**:
- 选择大模型提供商
- 输入 API 密钥
- 选择模型名称（根据提供商动态更新）

**获取 API 密钥**:
- 每个提供商都有对应的帮助链接
- 点击"前往获取"可直接跳转到官网

### 步骤 3：数据源配置

选择股票数据源：

**支持的数据源**:
- **AKShare**（推荐，免费无需密钥）
- **Tushare**（专业A股数据，需要 Token）
- **FinnHub**（美股数据，需要 API Key）

**配置项**:
- 选择默认数据源
- 根据选择输入相应的认证信息

### 步骤 4：完成

- 显示配置摘要
- 提供下一步研究观察
- 点击"完成"关闭向导

## 🔧 手动触发

### 方法 1：清除 localStorage

在浏览器控制台执行：

```javascript
localStorage.removeItem('config_wizard_completed');
location.reload();
```

### 方法 2：修改 App.vue（开发测试）

临时修改 `frontend/src/App.vue`：

```typescript
onMounted(() => {
  // 强制显示配置向导（测试用）
  showConfigWizard.value = true
  
  // checkFirstTimeSetup() // 注释掉原来的检查
})
```

### 方法 3：通过代码触发

在任何组件中：

```typescript
import { ref } from 'vue'

const showConfigWizard = ref(false)

// 显示配置向导
showConfigWizard.value = true
```

## 🎨 组件结构

### 文件位置

```
frontend/src/components/ConfigWizard.vue
```

### Props

```typescript
interface Props {
  modelValue: boolean  // 控制对话框显示/隐藏
}
```

### Emits

```typescript
{
  'update:modelValue': (value: boolean) => void  // 更新显示状态
  'complete': (data: WizardData) => void         // 配置完成回调
}
```

### 数据结构

```typescript
interface WizardData {
  mongodb: {
    host: string
    port: number
    database: string
  }
  redis: {
    host: string
    port: number
  }
  llm: {
    provider: string
    apiKey: string
    modelName: string
  }
  datasource: {
    type: string
    token: string
    apiKey: string
  }
}
```

## 🔑 关键技术点

### 1. 具名插槽位置

**重要**：`<template #footer>` 必须是 `el-dialog` 的直接子元素，不能嵌套在其他元素中。

```vue
<!-- ✅ 正确 -->
<el-dialog>
  <div class="content">...</div>
  <template #footer>...</template>
</el-dialog>

<!-- ❌ 错误 -->
<el-dialog>
  <div class="wrapper">
    <div class="content">...</div>
    <template #footer>...</template>
  </div>
</el-dialog>
```

### 2. 计算属性双向绑定

使用计算属性实现安全的双向绑定：

```typescript
const datasourceType = computed({
  get: () => wizardData.value.datasource.type,
  set: (value: string) => {
    wizardData.value.datasource.type = value
  }
})
```

### 3. 动态选项更新

根据用户选择动态更新可用选项：

```typescript
const availableModels = computed(() => {
  const provider = wizardData.value.llm.provider
  const models: Record<string, Array<{ label: string; value: string }>> = {
    deepseek: [
      { label: 'deepseek-chat', value: 'deepseek-chat' },
      { label: 'deepseek-coder', value: 'deepseek-coder' }
    ],
    // ...
  }
  return models[provider] || []
})
```

## 🐛 常见问题

### Q1: 配置向导没有自动弹出？

**检查清单**:
1. 确认已登录
2. 检查 localStorage 中是否有 `config_wizard_completed` 标记
3. 检查后端 `/api/system/config/validate` API 是否正常
4. 查看浏览器控制台是否有错误

**解决方法**:
```javascript
// 清除标记并刷新
localStorage.removeItem('config_wizard_completed');
location.reload();
```

### Q2: 修改文件后 TypeScript 报错？

**原因**: `components.d.ts` 是自动生成的类型声明文件，删除文件后需要重新生成。

**解决方法**:
```powershell
cd frontend
Remove-Item components.d.ts -Force
npm run dev  # 重启开发服务器
```

### Q3: 配置向导显示但样式错乱？

**检查**:
1. 确认 Element Plus 样式已正确导入
2. 检查 SCSS 变量是否正确配置
3. 查看浏览器控制台是否有 CSS 加载错误

## 📚 相关文档

- [配置管理 API](./CONFIG_WIZARD_USAGE.md)
- [系统配置验证](./PHASE3_WEB_UI_OPTIMIZATION.md)
- [前端开发指南](./FRONTEND_DEVELOPMENT.md)

## 🎯 最佳实践

1. **不要跳过配置向导**：首次使用时完成配置可以避免后续问题
2. **保存 API 密钥**：将 API 密钥保存在安全的地方
3. **定期验证配置**：在"配置管理"页面定期检查配置状态
4. **备份配置**：使用"导出配置"功能定期备份

## 🔌 后端 API 集成

### 配置保存流程

配置向导完成后，会自动调用后端 API 保存配置：

#### 1. 大模型配置保存

```typescript
// 1.1 添加大模型厂家
await configApi.addLLMProvider({
  provider_key: 'deepseek',
  provider_name: 'DeepSeek',
  api_key: 'sk-xxx',
  base_url: 'https://api.deepseek.com',
  is_active: true
})

// 1.2 添加大模型配置
await configApi.updateLLMConfig({
  provider: 'deepseek',
  model_name: 'deepseek-chat',
  enabled: true
})

// 1.3 设置为默认大模型
await configApi.setDefaultLLM('deepseek-chat')
```

**对应后端 API**:
- `POST /api/config/llm/providers` - 添加厂家
- `POST /api/config/llm` - 添加模型配置
- `POST /api/config/llm/set-default` - 设置默认模型

#### 2. 数据源配置保存

```typescript
// 2.1 添加数据源配置
await configApi.addDataSourceConfig({
  name: 'tushare',
  type: 'tushare',
  api_key: 'your-token',
  enabled: true
})

// 2.2 设置为默认数据源
await configApi.setDefaultDataSource('tushare')
```

**对应后端 API**:
- `POST /api/config/datasource` - 添加数据源
- `POST /api/config/datasource/set-default` - 设置默认数据源

#### 3. 数据库配置

**注意**：数据库配置（MongoDB、Redis）需要在后端 `.env` 文件中设置，配置向导只是收集用户输入用于验证连接。

实际配置需要在 `.env` 文件中：
```bash
# MongoDB
MONGODB_HOST=localhost
MONGODB_PORT=27017
MONGODB_DATABASE=tradingagents

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
```

### 配置验证 API

配置向导触发前会调用验证 API：

```typescript
const response = await axios.get('/api/system/config/validate')
```

**响应格式**:
```json
{
  "success": true,
  "data": {
    "success": false,
    "missing_required": [
      {
        "key": "MONGODB_HOST",
        "description": "MongoDB 主机地址"
      }
    ],
    "missing_recommended": [
      {
        "key": "DEEPSEEK_API_KEY",
        "description": "DeepSeek API 密钥"
      }
    ],
    "invalid_configs": [],
    "warnings": []
  },
  "message": "配置验证完成"
}
```

### 错误处理

配置保存过程中的错误会被捕获并提示用户：

- **厂家已存在**：忽略错误，继续保存模型配置
- **模型配置失败**：显示警告，提示用户稍后手动配置
- **数据源配置失败**：显示警告，提示用户稍后手动配置

用户可以在"配置管理"页面手动完成配置。

## 🔄 更新日志

- **2025-10-07**: 完善后端 API 集成，配置向导数据自动保存到后端
- **2025-10-06**: 修复具名插槽位置问题，确保 `<template #footer>` 是 `el-dialog` 的直接子元素
- **2025-10-06**: 添加自动触发机制，基于后端配置验证 API
- **2025-10-06**: 完善文档，添加使用说明和常见问题

