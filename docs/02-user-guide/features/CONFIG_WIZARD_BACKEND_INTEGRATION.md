# 配置向导与后端 API 集成说明

## 📋 概述

本文档说明配置向导（ConfigWizard）如何与后端 API 集成，以及配置数据的保存流程。

## 🔄 完整流程

### 1. 触发阶段

```
用户登录
  ↓
App.vue onMounted()
  ↓
调用 GET /api/system/config/validate
  ↓
检查 missing_required.length > 0
  ↓ (有缺失)
显示配置向导
```

### 2. 配置收集阶段

用户在配置向导中填写：
- **步骤 1**: MongoDB 和 Redis 连接信息
- **步骤 2**: 大模型提供商、API 密钥、模型名称
- **步骤 3**: 数据源类型、认证信息

### 3. 配置保存阶段

用户点击"完成"后，`handleWizardComplete()` 函数执行：

#### 3.1 保存大模型配置

```typescript
// 步骤 1: 添加大模型厂家
POST /api/config/llm/providers
{
  "provider_key": "deepseek",
  "provider_name": "DeepSeek",
  "api_key": "sk-xxx",
  "base_url": "https://api.deepseek.com",
  "is_active": true
}

// 步骤 2: 添加大模型配置
POST /api/config/llm
{
  "provider": "deepseek",
  "model_name": "deepseek-chat",
  "enabled": true
}

// 步骤 3: 设置为默认大模型
POST /api/config/llm/set-default
{
  "name": "deepseek-chat"
}
```

#### 3.2 保存数据源配置

```typescript
// 步骤 1: 添加数据源配置
POST /api/config/datasource
{
  "name": "tushare",
  "type": "tushare",
  "api_key": "your-token",
  "enabled": true
}

// 步骤 2: 设置为默认数据源
POST /api/config/datasource/set-default
{
  "name": "tushare"
}
```

#### 3.3 数据库配置

**重要说明**：数据库配置（MongoDB、Redis）需要在后端 `.env` 文件中设置。

配置向导收集的数据库信息仅用于：
- 向用户展示默认值
- 提示用户需要在 `.env` 文件中配置

**实际配置位置**：`backend/.env`
```bash
# MongoDB
MONGODB_HOST=localhost
MONGODB_PORT=27017
MONGODB_DATABASE=tradingagents

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
```

## 🎯 后端 API 映射

### 配置验证 API

| 端点 | 方法 | 功能 | 文件 |
|------|------|------|------|
| `/api/system/config/validate` | GET | 验证配置完整性 | `app/routers/system_config.py` |

**响应示例**:
```json
{
  "success": true,
  "data": {
    "success": false,
    "missing_required": [
      {"key": "MONGODB_HOST", "description": "MongoDB 主机地址"}
    ],
    "missing_recommended": [
      {"key": "DEEPSEEK_API_KEY", "description": "DeepSeek API 密钥"}
    ],
    "invalid_configs": [],
    "warnings": []
  },
  "message": "配置验证完成"
}
```

### 大模型配置 API

| 端点 | 方法 | 功能 | 文件 |
|------|------|------|------|
| `/api/config/llm/providers` | POST | 添加大模型厂家 | `app/routers/config.py` |
| `/api/config/llm` | POST | 添加大模型配置 | `app/routers/config.py` |
| `/api/config/llm/set-default` | POST | 设置默认大模型 | `app/routers/config.py` |

### 数据源配置 API

| 端点 | 方法 | 功能 | 文件 |
|------|------|------|------|
| `/api/config/datasource` | POST | 添加数据源配置 | `app/routers/config.py` |
| `/api/config/datasource/set-default` | POST | 设置默认数据源 | `app/routers/config.py` |

## 🔧 实现细节

### 前端实现

**文件**: `frontend/src/App.vue`

```typescript
const handleWizardComplete = async (data: any) => {
  // 1. 保存大模型配置
  if (data.llm?.provider && data.llm?.apiKey) {
    // 添加厂家
    await configApi.addLLMProvider({...})
    // 添加模型配置
    await configApi.updateLLMConfig({...})
    // 设置默认模型
    await configApi.setDefaultLLM(data.llm.modelName)
  }

  // 2. 保存数据源配置
  if (data.datasource?.type) {
    await configApi.addDataSourceConfig({...})
    await configApi.setDefaultDataSource(data.datasource.type)
  }

  // 3. 标记完成
  localStorage.setItem('config_wizard_completed', 'true')
}
```

### 后端实现

**配置验证**: `app/core/startup_validator.py`
- 检查必需配置项（MongoDB、Redis 等）
- 检查推荐配置项（API 密钥等）
- 返回缺失和无效的配置列表

**配置管理**: `app/services/config_service.py`
- 统一配置管理服务
- 支持大模型、数据源、数据库配置
- 配置持久化到 MongoDB

## 🛡️ 错误处理

### 厂家已存在

如果大模型厂家已经存在，会捕获错误并继续：

```typescript
try {
  await configApi.addLLMProvider({...})
} catch (e) {
  // 厂家可能已存在，忽略错误
  console.log('厂家可能已存在:', e)
}
```

### 配置保存失败

如果配置保存失败，会显示警告消息：

```typescript
catch (error) {
  console.error('保存大模型配置失败:', error)
  ElMessage.warning('大模型配置保存失败，请稍后在配置管理中手动配置')
}
```

用户可以稍后在"配置管理"页面手动完成配置。

## 📝 配置数据结构

### 配置向导数据

```typescript
interface WizardData {
  mongodb: {
    host: string      // 默认: localhost
    port: number      // 默认: 27017
    database: string  // 默认: tradingagents
  }
  redis: {
    host: string      // 默认: localhost
    port: number      // 默认: 6379
  }
  llm: {
    provider: string  // deepseek | dashscope | openai | google
    apiKey: string    // API 密钥
    modelName: string // 模型名称
  }
  datasource: {
    type: string      // akshare | tushare | finnhub
    token: string     // Tushare Token
    apiKey: string    // FinnHub API Key
  }
}
```

### 大模型厂家映射

```typescript
const providerMap = {
  deepseek: {
    name: 'DeepSeek',
    base_url: 'https://api.deepseek.com'
  },
  dashscope: {
    name: '通义千问',
    base_url: 'https://dashscope.aliyuncs.com/api/v1'
  },
  openai: {
    name: 'OpenAI',
    base_url: 'https://api.openai.com/v1'
  },
  google: {
    name: 'Google Gemini',
    base_url: 'https://generativelanguage.googleapis.com/v1'
  }
}
```

## 🧪 测试流程

### 1. 清除配置标记

```javascript
localStorage.removeItem('config_wizard_completed');
location.reload();
```

### 2. 填写配置信息

- 选择大模型：DeepSeek
- 输入 API 密钥：sk-xxx
- 选择模型：deepseek-chat
- 选择数据源：AKShare（无需密钥）

### 3. 验证配置保存

**检查大模型配置**:
```bash
curl -X GET http://localhost:8000/api/config/llm \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**检查数据源配置**:
```bash
curl -X GET http://localhost:8000/api/config/datasource \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## 🔍 常见问题

### Q1: 配置向导完成后，配置没有保存？

**检查**:
1. 打开浏览器控制台，查看是否有 API 错误
2. 检查后端日志，确认 API 调用是否成功
3. 确认用户已登录且有权限

### Q2: 数据库配置在哪里设置？

**答案**: 数据库配置需要在后端 `.env` 文件中设置，配置向导只是收集信息用于展示。

### Q3: 如何手动完成配置？

**答案**: 访问"配置管理"页面（`/settings/config`），可以手动添加和修改配置。

## 📚 相关文档

- [配置向导使用说明](./CONFIG_WIZARD.md)
- [配置管理 API](./configuration_analysis.md)
- [统一配置系统](./UNIFIED_CONFIG.md)

## 🎯 下一步优化

1. **添加配置测试**：在保存前测试配置是否有效
2. **批量保存**：将所有配置一次性保存，减少 API 调用
3. **配置回滚**：如果保存失败，提供回滚机制
4. **进度提示**：显示配置保存进度
5. **配置预览**：在保存前预览配置摘要

