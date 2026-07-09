# 聚合渠道支持文档

## 📖 概述

TradingAgents-CN 现已支持聚合渠道（如 302.AI、OpenRouter、One API 等），允许通过单一 API 端点访问多个原厂模型。

## 🎯 什么是聚合渠道？

聚合渠道是提供多个 AI 模型统一访问接口的中转平台，具有以下特点：

- **统一接口**：使用 OpenAI 兼容的 API 格式
- **多模型支持**：一个 API Key 访问多个厂商的模型
- **简化管理**：无需为每个厂商单独配置 API Key
- **成本优化**：部分聚合渠道提供更优惠的价格

### 支持的聚合渠道

| 渠道名称 | 官网 | 特点 |
|---------|------|------|
| **302.AI** | https://302.ai | 国内聚合平台，支持多种国内外模型 |
| **OpenRouter** | https://openrouter.ai | 国际聚合平台，模型种类丰富 |
| **One API** | https://github.com/songquanpeng/one-api | 开源自部署方案 |
| **New API** | https://github.com/Calcium-Ion/new-api | One API 的增强版 |

## 🚀 快速开始

### 方式 1：使用环境变量（推荐）

**步骤 1：配置环境变量**

编辑项目根目录的 `.env` 文件，添加聚合渠道的 API Key：

```bash
# 302.AI（推荐，国内访问稳定）
AI302_API_KEY=sk-xxxxx

# OpenRouter（可选，国际平台）
OPENROUTER_API_KEY=sk-or-v1-xxxxx

# One API（可选，自部署）
ONEAPI_API_KEY=sk-xxxxx
ONEAPI_BASE_URL=http://localhost:3000/v1
```

**步骤 2：初始化聚合渠道**

通过 API 或前端界面初始化：

```bash
# 使用 API
curl -X POST http://localhost:8000/api/config/llm/providers/init-aggregators \
  -H "Authorization: Bearer YOUR_TOKEN"
```

或在前端：
1. 进入 **设置 → 配置管理 → 大模型厂家管理**
2. 点击 **初始化聚合渠道** 按钮

**结果：**
- ✅ 系统会自动读取环境变量中的 API Key
- ✅ 配置了 API Key 的聚合渠道会自动启用
- ✅ 无需手动配置，即可使用

**步骤 3：验证配置**

运行测试脚本验证环境变量配置：

```bash
python scripts/test_env_config.py
```

### 方式 2：手动配置

**步骤 1：初始化聚合渠道配置**

通过 API 或前端界面初始化聚合渠道厂家配置：

```bash
# 使用 API
curl -X POST http://localhost:8000/api/config/llm/providers/init-aggregators \
  -H "Authorization: Bearer YOUR_TOKEN"
```

或在前端：
1. 进入 **设置 → 配置管理 → 大模型厂家管理**
2. 点击 **初始化聚合渠道** 按钮

**步骤 2：手动配置聚合渠道**

1. 在厂家列表中找到聚合渠道（如 302.AI）
2. 点击 **编辑** 按钮
3. 填写以下信息：
   - **API Key**：从聚合渠道平台获取的 API 密钥
   - **Base URL**：API 端点地址（通常已预填）
   - **启用状态**：勾选启用

### 步骤 3：配置模型目录

为聚合渠道添加可用的模型：

1. 进入 **设置 → 配置管理 → 模型目录管理**
2. 找到对应的聚合渠道，点击 **编辑**
3. 添加模型，格式为：`{provider}/{model}`

**示例（302.AI）：**
```json
{
  "provider": "302ai",
  "provider_name": "302.AI",
  "models": [
    {
      "name": "openai/gpt-4",
      "display_name": "GPT-4 (via 302.AI)",
      "original_provider": "openai",
      "original_model": "gpt-4"
    },
    {
      "name": "anthropic/claude-3-sonnet",
      "display_name": "Claude 3 Sonnet (via 302.AI)",
      "original_provider": "anthropic",
      "original_model": "claude-3-sonnet"
    },
    {
      "name": "google/gemini-pro",
      "display_name": "Gemini Pro (via 302.AI)",
      "original_provider": "google",
      "original_model": "gemini-pro"
    }
  ]
}
```

### 步骤 4：添加大模型配置

1. 进入 **设置 → 配置管理 → 大模型配置**
2. 点击 **添加配置**
3. 选择聚合渠道厂家（如 302.AI）
4. 选择或输入模型名称（如 `openai/gpt-4`）
5. 保存配置

## 🔑 环境变量配置

### 支持的环境变量

| 环境变量 | 聚合渠道 | 必需 | 说明 |
|---------|---------|------|------|
| `AI302_API_KEY` | 302.AI | 否 | 302.AI 平台的 API Key |
| `OPENROUTER_API_KEY` | OpenRouter | 否 | OpenRouter 平台的 API Key |
| `ONEAPI_API_KEY` | One API | 否 | One API 自部署实例的 API Key |
| `ONEAPI_BASE_URL` | One API | 否 | One API 自部署实例的 Base URL |
| `NEWAPI_API_KEY` | New API | 否 | New API 自部署实例的 API Key |
| `NEWAPI_BASE_URL` | New API | 否 | New API 自部署实例的 Base URL |

### 配置方法

**方法 1：编辑 .env 文件**

在项目根目录的 `.env` 文件中添加：

```bash
# 302.AI（推荐）
AI302_API_KEY=sk-xxxxx

# OpenRouter（可选）
OPENROUTER_API_KEY=sk-or-v1-xxxxx

# One API（可选）
ONEAPI_API_KEY=sk-xxxxx
ONEAPI_BASE_URL=http://localhost:3000/v1
```

**方法 2：设置系统环境变量**

```bash
# Windows (PowerShell)
$env:AI302_API_KEY="sk-xxxxx"

# Linux/Mac
export AI302_API_KEY="sk-xxxxx"
```

### 环境变量的优势

1. **安全性**
   - API Key 不会暴露在前端界面
   - 不会被误提交到 Git 仓库（.env 已在 .gitignore 中）
   - 便于密钥轮换和管理

2. **便捷性**
   - 初始化时自动读取
   - 无需手动在界面中配置
   - 支持多环境部署（开发/测试/生产）

3. **团队协作**
   - 每个开发者使用自己的 API Key
   - 生产环境使用独立的 API Key
   - 便于权限管理和审计

### 环境变量优先级

系统读取 API Key 的优先级顺序：

```
1. 数据库中的配置（最高优先级）
   ↓
2. 环境变量（.env 文件或系统环境变量）
   ↓
3. 默认值（空字符串）
```

**说明：**
- 如果数据库中已有 API Key，不会被环境变量覆盖
- 初始化聚合渠道时，如果数据库中没有 API Key，会从环境变量读取
- 可以随时在界面中修改 API Key，修改后的值会保存到数据库

### 测试环境变量配置

运行测试脚本验证环境变量是否正确配置：

```bash
python scripts/test_env_config.py
```

输出示例：

```
🔍 聚合渠道环境变量配置检查
============================================================

✅ 302.AI
   变量名: AI302_API_KEY
   值: sk-xxxxxxxx...xxxx
   说明: 302.AI 聚合平台 API Key

⏭️ OpenRouter
   变量名: OPENROUTER_API_KEY
   状态: 未配置
   说明: OpenRouter 聚合平台 API Key

============================================================
📊 配置统计: 1/4 个聚合渠道已配置
============================================================
```

## 🔧 模型名称格式

### 标准格式

大多数聚合渠道使用以下格式：

```
{provider}/{model}
```

**示例：**
- `openai/gpt-4` - OpenAI 的 GPT-4
- `anthropic/claude-3-sonnet` - Anthropic 的 Claude 3 Sonnet
- `google/gemini-pro` - Google 的 Gemini Pro
- `deepseek/deepseek-chat` - DeepSeek 的对话模型

### 特殊情况

某些聚合渠道（如 One API）可能不需要前缀：

```
gpt-4
claude-3-sonnet
```

请参考具体聚合渠道的文档。

## 🎨 能力映射机制

系统会自动将聚合渠道的模型映射到原厂模型的能力配置：

```
openai/gpt-4 → gpt-4 的能力配置
  ├─ 能力等级: 3 (高级)
  ├─ 适用角色: 通用
  ├─ 特性: 工具调用、推理
  └─ 推荐深度: 基础、标准、深度
```

### 映射规则

1. **直接匹配**：优先查找完整模型名（如 `openai/gpt-4`）
2. **前缀解析**：解析 `{provider}/{model}` 格式
3. **原模型查找**：使用原模型名（如 `gpt-4`）查找能力配置
4. **默认配置**：如果都找不到，使用默认配置（能力等级 2）

## 📝 配置示例

### 302.AI 完整配置

```json
{
  "厂家配置": {
    "name": "302ai",
    "display_name": "302.AI",
    "default_base_url": "https://api.302.ai/v1",
    "api_key": "sk-xxxxx",
    "is_active": true,
    "is_aggregator": true,
    "aggregator_type": "openai_compatible",
    "model_name_format": "{provider}/{model}"
  },
  "模型目录": [
    {
      "name": "openai/gpt-4",
      "display_name": "GPT-4 (via 302.AI)",
      "original_provider": "openai",
      "original_model": "gpt-4",
      "input_price_per_1k": 0.03,
      "output_price_per_1k": 0.06,
      "currency": "USD"
    },
    {
      "name": "anthropic/claude-3-sonnet",
      "display_name": "Claude 3 Sonnet (via 302.AI)",
      "original_provider": "anthropic",
      "original_model": "claude-3-sonnet"
    }
  ],
  "大模型配置": [
    {
      "provider": "302ai",
      "model_name": "openai/gpt-4",
      "enabled": true,
      "capability_level": 3,
      "suitable_roles": ["both"],
      "features": ["tool_calling", "reasoning"]
    }
  ]
}
```

### OpenRouter 配置

```json
{
  "厂家配置": {
    "name": "openrouter",
    "display_name": "OpenRouter",
    "default_base_url": "https://openrouter.ai/api/v1",
    "api_key": "sk-or-xxxxx",
    "is_active": true,
    "is_aggregator": true
  },
  "模型示例": [
    "openai/gpt-4-turbo",
    "anthropic/claude-3-opus",
    "google/gemini-pro-1.5",
    "meta-llama/llama-3-70b"
  ]
}
```

### One API（自部署）配置

```json
{
  "厂家配置": {
    "name": "oneapi",
    "display_name": "One API (自部署)",
    "default_base_url": "http://localhost:3000/v1",
    "api_key": "sk-xxxxx",
    "is_active": true,
    "is_aggregator": true,
    "model_name_format": "{model}"
  },
  "模型示例": [
    "gpt-4",
    "claude-3-sonnet",
    "gemini-pro"
  ]
}
```

## 🔍 使用场景

### 场景 1：统一管理多个模型

使用聚合渠道可以通过单一 API Key 访问多个厂商的模型：

```python
# 不使用聚合渠道（需要多个 API Key）
openai_key = "sk-openai-xxxxx"
anthropic_key = "sk-ant-xxxxx"
google_key = "AIza-xxxxx"

# 使用聚合渠道（只需一个 API Key）
aggregator_key = "sk-302ai-xxxxx"
# 可以访问: openai/gpt-4, anthropic/claude-3-sonnet, google/gemini-pro
```

### 场景 2：成本优化

某些聚合渠道提供更优惠的价格：

```
原厂 GPT-4: $0.03/1K input, $0.06/1K output
302.AI GPT-4: $0.025/1K input, $0.05/1K output (示例)
```

### 场景 3：访问受限模型

通过聚合渠道访问在某些地区受限的模型：

```
国内用户 → 302.AI → Claude 3 Sonnet
```

## ⚠️ 注意事项

### 1. 模型名称一致性

确保模型名称格式与聚合渠道要求一致：

- ✅ 正确：`openai/gpt-4`（302.AI、OpenRouter）
- ✅ 正确：`gpt-4`（One API）
- ❌ 错误：混用格式

### 2. API 兼容性

虽然大多数聚合渠道兼容 OpenAI API，但可能存在细微差异：

- 某些参数可能不支持
- 响应格式可能略有不同
- 建议先测试再正式使用

### 3. 定价信息

聚合渠道的定价可能与原厂不同，请：

- 在模型目录中配置正确的价格
- 定期更新价格信息
- 监控实际使用成本

### 4. 能力映射

系统会自动映射能力，但如果聚合渠道的模型表现与原厂不同：

- 可以在大模型配置中手动调整能力等级
- 覆盖自动映射的配置

## 🛠️ API 参考

### 初始化聚合渠道

```http
POST /api/config/llm/providers/init-aggregators
Authorization: Bearer YOUR_TOKEN
```

**响应：**
```json
{
  "success": true,
  "message": "成功添加 4 个聚合渠道，跳过 0 个已存在的",
  "data": {
    "added_count": 4,
    "skipped_count": 0
  }
}
```

### 获取聚合渠道列表

```http
GET /api/config/llm/providers
Authorization: Bearer YOUR_TOKEN
```

**响应中的聚合渠道标识：**
```json
{
  "id": "...",
  "name": "302ai",
  "display_name": "302.AI",
  "is_aggregator": true,
  "aggregator_type": "openai_compatible",
  "model_name_format": "{provider}/{model}"
}
```

## 📚 相关文档

- [模型能力分级系统](./model-capability-system.md)
- [模型目录管理](./MODEL_CATALOG_MANAGEMENT.md)
- [大模型配置指南](./LLM_CONFIG_GUIDE.md)

## 🤝 贡献

如果你使用的聚合渠道不在支持列表中，欢迎提交 PR 添加：

1. 在 `app/constants/model_capabilities.py` 的 `AGGREGATOR_PROVIDERS` 中添加配置
2. 更新本文档
3. 提交 PR

## 📞 支持

如有问题，请：

1. 查看 [常见问题](./FAQ.md)
2. 提交 [Issue](https://github.com/your-repo/issues)
3. 加入社区讨论

