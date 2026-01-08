# 厂家默认 API 地址 (default_base_url) 使用说明

## 📋 概述

本文档说明了厂家配置中的 `default_base_url` 字段如何被系统使用，以及配置优先级。

## 🎯 功能说明

### 1. 什么是 `default_base_url`？

`default_base_url` 是 `llm_providers` 集合中每个厂家的默认 API 地址。当用户在界面上配置厂家信息时，可以设置这个字段。

**示例**：
```json
{
  "name": "google",
  "display_name": "Google AI",
  "default_base_url": "https://generativelanguage.googleapis.com/v1",
  "api_key": "your_api_key_here"
}
```

### 2. 配置优先级

系统在获取 API 地址时，按照以下优先级：

```
1️⃣ 模型配置的 api_base (system_configs.llm_configs[].api_base)
    ↓ (如果没有)
2️⃣ 厂家配置的 default_base_url (llm_providers.default_base_url)
    ↓ (如果没有)
3️⃣ 硬编码的默认 URL (代码中的默认值)
```

### 3. 使用场景

#### 场景 1：使用厂家默认地址

**配置**：
- 厂家 `google` 的 `default_base_url` = `https://generativelanguage.googleapis.com/v1`
- 模型 `gemini-2.0-flash` 没有配置 `api_base`

**结果**：
- ✅ 使用厂家的 `default_base_url`
- 日志：`✅ [同步查询] 使用厂家 google 的 default_base_url: https://generativelanguage.googleapis.com/v1`

#### 场景 2：使用模型自定义地址

**配置**：
- 厂家 `google` 的 `default_base_url` = `https://generativelanguage.googleapis.com/v1`
- 模型 `gemini-2.0-flash` 配置了 `api_base` = `https://custom-api.google.com/v1`

**结果**：
- ✅ 使用模型的 `api_base`（优先级更高）
- 日志：`✅ [同步查询] 模型 gemini-2.0-flash 使用自定义 API: https://custom-api.google.com/v1`

#### 场景 3：使用硬编码默认值

**配置**：
- 厂家 `google` 没有配置 `default_base_url`
- 模型 `gemini-2.0-flash` 没有配置 `api_base`

**结果**：
- ⚠️ 使用硬编码的默认 URL
- 日志：`⚠️ 使用硬编码的默认 backend_url: https://generativelanguage.googleapis.com/v1`

## 🔧 如何配置

### 方法 1：通过 Web 界面配置

1. 登录系统
2. 进入 **设置** → **厂家管理**
3. 点击要配置的厂家的 **编辑** 按钮
4. 在 **默认API地址** 输入框中填写 API 地址
5. 点击 **更新** 按钮保存

**示例**：
```
厂家名称: Google AI
默认API地址: https://generativelanguage.googleapis.com/v1
API Key: your_google_api_key_here
```

### 方法 2：通过 MongoDB 直接配置

```javascript
// 连接 MongoDB
use trading_agents

// 更新厂家配置
db.llm_providers.updateOne(
  { "name": "google" },
  { 
    "$set": { 
      "default_base_url": "https://generativelanguage.googleapis.com/v1" 
    } 
  }
)
```

### 方法 3：通过 API 配置

```bash
# 更新厂家配置
curl -X PUT "http://localhost:8000/api/config/providers/google" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "default_base_url": "https://generativelanguage.googleapis.com/v1"
  }'
```

## 📊 支持的厂家

以下是系统支持的厂家及其默认 API 地址：

| 厂家名称 | 默认 API 地址 |
|---------|--------------|
| google | https://generativelanguage.googleapis.com/v1 |
| dashscope | https://dashscope.aliyuncs.com/api/v1 |
| openai | https://api.openai.com/v1 |
| deepseek | https://api.deepseek.com |
| anthropic | https://api.anthropic.com |
| openrouter | https://openrouter.ai/api/v1 |
| qianfan | https://qianfan.baidubce.com/v2 |
| 302ai | https://api.302.ai/v1 |

## 🧪 测试方法

### 测试脚本

运行以下脚本测试 `default_base_url` 是否生效：

```bash
python scripts/test_default_base_url.py
```

### 测试步骤

1. 修改厂家的 `default_base_url`
2. 创建分析配置
3. 验证 `backend_url` 是否使用了 `default_base_url`
4. 恢复原始配置

### 预期结果

```
✅ backend_url 正确: https://test-api.google.com/v1
✅ 配置中的 backend_url 正确: https://test-api.google.com/v1
```

## 🔍 调试方法

### 查看日志

启动后端服务时，日志会显示使用的 API 地址：

```bash
.\.venv\Scripts\python -m uvicorn app.main:app --reload
```

**日志示例**：
```
✅ [同步查询] 使用厂家 google 的 default_base_url: https://generativelanguage.googleapis.com/v1
✅ 使用数据库配置的 backend_url: https://generativelanguage.googleapis.com/v1
   来源: 模型 gemini-2.0-flash 的配置或厂家 google 的默认地址
```

### 查看数据库配置

```javascript
// 查看厂家配置
db.llm_providers.find({ "name": "google" }).pretty()

// 查看模型配置
db.system_configs.find({ "is_active": true }).pretty()
```

## ⚠️ 注意事项

1. **配置优先级**：模型配置的 `api_base` 优先级高于厂家的 `default_base_url`
2. **URL 格式**：确保 URL 格式正确，以 `https://` 开头，以 `/v1` 结尾（如果需要）
3. **重启服务**：修改配置后，建议重启后端服务使配置生效
4. **测试验证**：修改配置后，建议运行测试脚本验证配置是否生效

## 🐛 常见问题

### Q1: 修改了 `default_base_url` 但没有生效？

**原因**：可能是模型配置中有 `api_base` 字段，优先级更高。

**解决方法**：
1. 检查模型配置是否有 `api_base` 字段
2. 如果有，删除或修改模型配置的 `api_base`
3. 或者直接在模型配置中设置 `api_base`

### Q2: 如何知道当前使用的是哪个配置？

**方法**：查看日志输出，日志会显示配置来源。

**日志示例**：
```
✅ [同步查询] 模型 gemini-2.0-flash 使用自定义 API: https://custom-api.google.com/v1
✅ [同步查询] 使用厂家 google 的 default_base_url: https://generativelanguage.googleapis.com/v1
⚠️ 使用硬编码的默认 backend_url: https://generativelanguage.googleapis.com/v1
```

### Q3: 如何添加新的厂家？

**方法**：在 Web 界面或通过 API 添加新厂家。

**示例**：
```javascript
db.llm_providers.insertOne({
  "name": "custom_provider",
  "display_name": "自定义厂家",
  "default_base_url": "https://api.custom-provider.com/v1",
  "api_key": "your_api_key_here"
})
```

## 📝 相关文件

- **后端服务**：`app/services/simple_analysis_service.py`
- **配置路由**：`app/routers/config.py`
- **前端组件**：`frontend/src/views/Settings/components/ProviderDialog.vue`
- **测试脚本**：`scripts/test_default_base_url.py`

## 🔗 相关文档

- [API Key 配置优先级](./API_KEY_PRIORITY.md)
- [系统配置说明](./SYSTEM_CONFIG.md)
- [厂家管理说明](./PROVIDER_MANAGEMENT.md)

