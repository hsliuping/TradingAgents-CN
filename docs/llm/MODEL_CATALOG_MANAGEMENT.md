# 模型目录管理指南

## 📖 概述

模型目录是一个集中管理大模型信息的系统，用于在添加大模型配置时提供可选的模型列表。通过模型目录，您可以：

- ✅ 快速选择常用模型，避免输入错误
- ✅ 查看模型的详细信息（价格、上下文长度等）
- ✅ 集中管理和更新模型列表
- ✅ 支持自定义模型

## 🏗️ 架构说明

### 数据存储

模型目录存储在 MongoDB 的 `model_catalog` 集合中：

```javascript
{
  "_id": ObjectId("..."),
  "provider": "dashscope",           // 厂家标识
  "provider_name": "通义千问",        // 厂家显示名称
  "models": [                        // 模型列表
    {
      "name": "qwen-turbo",          // 模型标识名称
      "display_name": "Qwen Turbo - 快速经济",  // 显示名称
      "description": "快速经济的模型",
      "context_length": 8192,        // 上下文长度
      "max_tokens": 2000,            // 最大输出token
      "input_price_per_1k": 0.002,   // 输入价格(每1K tokens)
      "output_price_per_1k": 0.006,  // 输出价格(每1K tokens)
      "currency": "CNY",             // 货币单位
      "is_deprecated": false,        // 是否已废弃
      "release_date": "2024-01-01",  // 发布日期
      "capabilities": ["chat", "function_calling"]  // 能力标签
    }
  ],
  "created_at": ISODate("..."),
  "updated_at": ISODate("...")
}
```

### 与用户配置的关系

**模型目录** 和 **用户配置** 是两个独立的概念：

1. **模型目录**（`model_catalog` 集合）
   - 作用：提供可选的模型列表
   - 位置：独立的集合
   - 用途：在添加配置时作为参考

2. **用户配置**（`system_configs.llm_configs` 字段）
   - 作用：用户实际使用的模型配置
   - 位置：`system_configs` 集合的 `llm_configs` 数组
   - 用途：系统运行时使用的配置

```
┌─────────────────┐
│  模型目录        │  ← 参考数据（可选模型列表）
│  model_catalog  │
└────────┬────────┘
         │ 用户选择
         ↓
┌─────────────────┐
│  用户配置        │  ← 实际配置（包含API密钥等）
│  llm_configs    │
└─────────────────┘
```

## 🚀 初始化模型目录

### 方法 1：使用脚本初始化

```bash
# 在项目根目录执行
python scripts/init_model_catalog.py
```

这会初始化以下厂家的模型目录：
- 通义千问 (dashscope) - 8个模型
- OpenAI - 5个模型
- Google Gemini - 4个模型
- DeepSeek - 2个模型
- Anthropic Claude - 5个模型
- 百度千帆 (qianfan) - 4个模型
- 智谱AI (zhipu) - 3个模型

### 方法 2：通过API初始化

```bash
curl -X POST http://localhost:8000/api/config/model-catalog/init \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 方法 3：通过前端界面

1. 访问：设置 → 系统配置 → 配置管理
2. 点击左侧菜单的"模型目录"
3. 如果目录为空，系统会自动初始化

## 🎨 前端管理界面

### 访问路径

```
设置 → 系统配置 → 配置管理 → 模型目录
```

或直接访问：`http://localhost:3001/settings/config`，然后点击"模型目录"菜单

### 功能说明

#### 1. 查看模型目录

- 显示所有厂家的模型目录
- 查看每个厂家的模型数量
- 查看模型列表预览

#### 2. 添加模型目录

点击"添加厂家模型目录"按钮：

1. 输入厂家标识（如：`dashscope`）
2. 输入厂家名称（如：`通义千问`）
3. 添加模型：
   - 模型名称：如 `qwen-turbo`
   - 显示名称：如 `Qwen Turbo - 快速经济`
4. 点击"保存"

#### 3. 编辑模型目录

点击"编辑"按钮：

- 修改厂家名称
- 添加/删除/修改模型
- 点击"保存"

#### 4. 删除模型目录

点击"删除"按钮，确认后删除整个厂家的模型目录

## 🔧 API 接口

### 获取所有模型目录

```http
GET /api/config/model-catalog
Authorization: Bearer YOUR_TOKEN
```

响应：
```json
[
  {
    "provider": "dashscope",
    "provider_name": "通义千问",
    "models": [...]
  }
]
```

### 获取指定厂家的模型目录

```http
GET /api/config/model-catalog/{provider}
Authorization: Bearer YOUR_TOKEN
```

### 保存模型目录

```http
POST /api/config/model-catalog
Authorization: Bearer YOUR_TOKEN
Content-Type: application/json

{
  "provider": "dashscope",
  "provider_name": "通义千问",
  "models": [
    {
      "name": "qwen-turbo",
      "display_name": "Qwen Turbo - 快速经济",
      "description": "快速经济的模型"
    }
  ]
}
```

### 删除模型目录

```http
DELETE /api/config/model-catalog/{provider}
Authorization: Bearer YOUR_TOKEN
```

## 📝 维护指南

### 添加新模型

当厂家发布新模型时：

1. **通过前端界面**：
   - 进入"模型目录"管理页面
   - 点击对应厂家的"编辑"按钮
   - 点击"添加模型"
   - 填写模型信息
   - 保存

2. **通过API**：
   ```bash
   curl -X POST http://localhost:8000/api/config/model-catalog \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "provider": "dashscope",
       "provider_name": "通义千问",
       "models": [
         {
           "name": "qwen-new-model",
           "display_name": "Qwen New Model - 新模型"
         }
       ]
     }'
   ```

### 标记废弃模型

当模型被废弃时，不要删除，而是标记为废弃：

```json
{
  "name": "old-model",
  "display_name": "Old Model (已废弃)",
  "is_deprecated": true
}
```

### 更新模型信息

定期更新模型的价格、上下文长度等信息：

1. 访问厂家官网查看最新信息
2. 在前端界面编辑对应的模型目录
3. 更新相关字段
4. 保存

## 🎯 使用场景

### 场景 1：添加大模型配置

用户在添加大模型配置时：

1. 选择厂家（如"通义千问"）
2. 模型名称下拉框自动显示该厂家的模型列表
3. 用户可以：
   - 从列表中选择模型
   - 或直接输入自定义模型名称

### 场景 2：查看模型信息

用户可以在模型目录中查看：
- 模型的显示名称
- 模型的描述
- 模型的价格信息
- 模型的能力标签

### 场景 3：批量更新模型

当厂家更新模型列表时：
- 管理员在模型目录中统一更新
- 所有用户在添加配置时都能看到最新的模型列表

## ⚠️ 注意事项

1. **模型目录不影响现有配置**
   - 修改模型目录不会影响已保存的用户配置
   - 用户配置独立存储在 `system_configs.llm_configs` 中

2. **支持自定义模型**
   - 即使模型不在目录中，用户仍可手动输入
   - 模型目录只是提供便利，不是强制约束

3. **定期维护**
   - 建议定期检查厂家官网，更新模型信息
   - 及时标记废弃的模型
   - 添加新发布的模型

4. **备份建议**
   - 在大规模修改前，建议导出配置备份
   - 可以通过 MongoDB 导出 `model_catalog` 集合

## 🔍 故障排查

### 问题 1：模型目录为空

**解决方案**：
```bash
python scripts/init_model_catalog.py
```

### 问题 2：添加配置时看不到模型列表

**可能原因**：
1. 模型目录未初始化
2. 前端缓存问题

**解决方案**：
1. 检查数据库中是否有 `model_catalog` 集合
2. 刷新浏览器页面（Ctrl+F5）
3. 检查浏览器控制台是否有错误

### 问题 3：修改模型目录后前端没有更新

**解决方案**：
1. 刷新浏览器页面
2. 重新打开添加配置对话框

## 📚 相关文档

- [配置管理指南](./CONFIGURATION_GUIDE.md)
- [大模型配置说明](./LLM_CONFIGURATION.md)
- [API 文档](./API_DOCUMENTATION.md)

