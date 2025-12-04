# 聚合渠道快速开始指南

## 🎯 5 分钟快速配置 302.AI

### 步骤 1：获取 API Key

1. 访问 [302.AI](https://302.ai)
2. 注册/登录账号
3. 进入 **API 管理** 页面
4. 创建新的 API Key
5. 复制 API Key（格式：`sk-xxxxx`）

### 步骤 2：配置环境变量（推荐）

**方式 1：通过 .env 文件（推荐）**

编辑项目根目录的 `.env` 文件，添加：

```bash
# 302.AI API 密钥
AI302_API_KEY=sk-xxxxx  # 替换为你的实际 API Key
```

**方式 2：通过系统环境变量**

```bash
# Windows (PowerShell)
$env:AI302_API_KEY="sk-xxxxx"

# Linux/Mac
export AI302_API_KEY="sk-xxxxx"
```

**优势：**
- ✅ 自动读取，无需手动配置
- ✅ 安全性高，不会暴露在界面
- ✅ 便于团队协作和部署

### 步骤 3：初始化聚合渠道

在系统中初始化聚合渠道配置：

**方式 1：通过前端界面**

1. 登录系统
2. 进入 **设置 → 配置管理 → 大模型厂家管理**
3. 点击 **初始化聚合渠道** 按钮
4. 等待初始化完成

**方式 2：通过 API**

```bash
curl -X POST http://localhost:8000/api/config/llm/providers/init-aggregators \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**初始化结果：**
- ✅ 如果配置了环境变量 `AI302_API_KEY`，系统会自动读取并启用 302.AI
- ⚠️ 如果未配置环境变量，需要手动配置 API Key

### 步骤 4：验证配置（如果使用环境变量）

如果你在步骤 2 中配置了环境变量，初始化后 302.AI 应该已经自动启用。

验证方式：
1. 在厂家列表中找到 **302.AI**
2. 查看状态是否为 **已启用**
3. 查看是否显示 "已从环境变量获取 API Key"

### 步骤 5：手动配置（如果未使用环境变量）

如果未配置环境变量，需要手动配置：

1. 在厂家列表中找到 **302.AI**
2. 点击 **编辑** 按钮
3. 填写 API Key
4. 勾选 **启用**
5. 保存

### 步骤 6：添加模型

在 **模型目录管理** 中为 302.AI 添加模型：

```json
{
  "provider": "302ai",
  "provider_name": "302.AI",
  "models": [
    {
      "name": "openai/gpt-4",
      "display_name": "GPT-4 (via 302.AI)"
    },
    {
      "name": "openai/gpt-3.5-turbo",
      "display_name": "GPT-3.5 Turbo (via 302.AI)"
    },
    {
      "name": "anthropic/claude-3-sonnet",
      "display_name": "Claude 3 Sonnet (via 302.AI)"
    }
  ]
}
```

### 步骤 7：配置大模型

1. 进入 **大模型配置**
2. 点击 **添加配置**
3. 选择厂家：**302.AI**
4. 选择模型：**openai/gpt-4**
5. 保存并启用

### 步骤 8：开始使用

现在可以在分析模块中选择 302.AI 的模型了！

---

## 🔑 环境变量配置详解

### 支持的环境变量

| 环境变量 | 聚合渠道 | 说明 |
|---------|---------|------|
| `AI302_API_KEY` | 302.AI | 302.AI 平台的 API Key |
| `OPENROUTER_API_KEY` | OpenRouter | OpenRouter 平台的 API Key |
| `ONEAPI_API_KEY` | One API | One API 自部署实例的 API Key |
| `NEWAPI_API_KEY` | New API | New API 自部署实例的 API Key |

### .env 文件完整示例

```bash
# ==================== 聚合渠道 API 密钥 ====================

# 302.AI（推荐，国内访问稳定）
AI302_API_KEY=sk-xxxxx

# OpenRouter（可选，国际平台）
OPENROUTER_API_KEY=sk-or-v1-xxxxx

# One API（可选，自部署）
ONEAPI_API_KEY=sk-xxxxx
ONEAPI_BASE_URL=http://localhost:3000/v1

# New API（可选，自部署）
NEWAPI_API_KEY=sk-xxxxx
NEWAPI_BASE_URL=http://localhost:3000/v1
```

### 环境变量的优势

1. **安全性**
   - API Key 不会暴露在前端界面
   - 不会被误提交到 Git 仓库
   - 便于密钥轮换

2. **便捷性**
   - 初始化时自动读取
   - 无需手动配置
   - 支持多环境部署

3. **团队协作**
   - 每个开发者使用自己的 API Key
   - 生产环境使用独立的 API Key
   - 便于权限管理

### 环境变量优先级

系统读取 API Key 的优先级：

```
1. 数据库中的配置（最高优先级）
   ↓
2. 环境变量
   ↓
3. 手动配置（最低优先级）
```

**说明：**
- 如果数据库中已有 API Key，不会被环境变量覆盖
- 初始化时，如果数据库中没有 API Key，会从环境变量读取
- 可以随时在界面中修改 API Key

---

## 📋 常见模型名称

### 302.AI 模型格式

```
{provider}/{model}
```

### OpenAI 系列

```
openai/gpt-4
openai/gpt-4-turbo
openai/gpt-3.5-turbo
openai/gpt-4o
openai/gpt-4o-mini
```

### Anthropic Claude 系列

```
anthropic/claude-3-opus
anthropic/claude-3-sonnet
anthropic/claude-3-haiku
anthropic/claude-3.5-sonnet
```

### Google Gemini 系列

```
google/gemini-pro
google/gemini-1.5-pro
google/gemini-1.5-flash
google/gemini-2.0-flash
```

### DeepSeek 系列

```
deepseek/deepseek-chat
deepseek/deepseek-coder
```

### 通义千问系列

```
qwen/qwen-turbo
qwen/qwen-plus
qwen/qwen-max
```

## 🔧 配置示例

### 完整的 302.AI 配置

```json
{
  "厂家配置": {
    "name": "302ai",
    "display_name": "302.AI",
    "default_base_url": "https://api.302.ai/v1",
    "api_key": "sk-xxxxx",
    "is_active": true,
    "is_aggregator": true
  },
  "模型目录": [
    {
      "name": "openai/gpt-4",
      "display_name": "GPT-4 (via 302.AI)",
      "original_provider": "openai",
      "original_model": "gpt-4"
    }
  ],
  "大模型配置": [
    {
      "provider": "302ai",
      "model_name": "openai/gpt-4",
      "enabled": true
    }
  ]
}
```

## ❓ 常见问题

### Q1: 模型名称格式错误

**问题**：使用 `gpt-4` 而不是 `openai/gpt-4`

**解决**：
- 302.AI 和 OpenRouter 需要使用 `{provider}/{model}` 格式
- One API 通常使用 `{model}` 格式（不需要前缀）

### Q2: API Key 无效

**问题**：提示 API Key 无效

**解决**：
1. 检查 API Key 是否正确复制
2. 确认 API Key 是否已激活
3. 检查 API Key 是否有足够的额度

### Q3: 模型不可用

**问题**：提示模型不存在

**解决**：
1. 确认聚合渠道支持该模型
2. 检查模型名称格式是否正确
3. 查看聚合渠道的模型列表文档

### Q4: 能力等级不准确

**问题**：聚合渠道模型的能力等级与预期不符

**解决**：
- 系统会自动映射到原厂模型的能力配置
- 如需调整，可在大模型配置中手动设置 `capability_level`

## 🎨 高级配置

### 自定义模型能力

如果聚合渠道的模型表现与原厂不同，可以手动配置：

```json
{
  "provider": "302ai",
  "model_name": "openai/gpt-4",
  "capability_level": 4,
  "suitable_roles": ["both"],
  "features": ["tool_calling", "reasoning", "long_context"],
  "recommended_depths": ["标准", "深度", "全面"]
}
```

### 配置多个聚合渠道

可以同时配置多个聚合渠道：

```
302.AI (主要)
  ├─ openai/gpt-4
  ├─ anthropic/claude-3-sonnet
  └─ google/gemini-pro

OpenRouter (备用)
  ├─ openai/gpt-4-turbo
  ├─ anthropic/claude-3-opus
  └─ meta-llama/llama-3-70b
```

### 成本优化策略

1. **快速分析**：使用经济型模型
   ```
   302.AI: openai/gpt-3.5-turbo
   ```

2. **深度分析**：使用高性能模型
   ```
   302.AI: anthropic/claude-3-sonnet
   ```

3. **关键决策**：使用旗舰模型
   ```
   302.AI: openai/gpt-4
   ```

## 📚 相关文档

- [聚合渠道完整文档](./AGGREGATOR_SUPPORT.md)
- [模型能力分级系统](./model-capability-system.md)
- [大模型配置指南](./LLM_CONFIG_GUIDE.md)

## 🆘 获取帮助

如遇问题：

1. 查看 [常见问题](./FAQ.md)
2. 查看聚合渠道官方文档
3. 提交 [Issue](https://github.com/your-repo/issues)

