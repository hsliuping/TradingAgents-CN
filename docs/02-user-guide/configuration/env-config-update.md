# 环境变量配置更新说明

## 📋 更新概述

本次更新为聚合渠道添加了环境变量配置支持，允许通过 `.env` 文件或系统环境变量配置聚合渠道的 API Key，简化配置流程。

**更新日期**: 2025-01-XX  
**版本**: v1.1.0

## 🎯 更新内容

### 1. .env.example 文件更新

在 `.env.example` 文件中添加了聚合渠道的环境变量配置说明：

```bash
# ==================== 聚合渠道 API 密钥（推荐） ====================

# 🌐 302.AI API 密钥（推荐，国内聚合平台）
AI302_API_KEY=your_302ai_api_key_here

# 🌐 OpenRouter API 密钥（可选，国际聚合平台）
OPENROUTER_API_KEY=your_openrouter_api_key_here

# 🔧 One API / New API（可选，自部署聚合平台）
ONEAPI_API_KEY=your_oneapi_api_key_here
ONEAPI_BASE_URL=http://localhost:3000/v1

NEWAPI_API_KEY=your_newapi_api_key_here
NEWAPI_BASE_URL=http://localhost:3000/v1
```

### 2. 配置服务更新

**文件**: `app/services/config_service.py`

**更新内容**:

1. **扩展环境变量映射表**

在 `_get_env_api_key()` 方法中添加了聚合渠道的环境变量映射：

```python
env_key_mapping = {
    # ... 原有映射
    # 🆕 聚合渠道
    "302ai": "AI302_API_KEY",
    "oneapi": "ONEAPI_API_KEY",
    "newapi": "NEWAPI_API_KEY",
    "custom_aggregator": "CUSTOM_AGGREGATOR_API_KEY"
}
```

2. **增强初始化方法**

更新 `init_aggregator_providers()` 方法，支持从环境变量读取 API Key：

```python
async def init_aggregator_providers(self) -> Dict[str, Any]:
    # 从环境变量获取 API Key
    api_key = self._get_env_api_key(provider_name)
    
    # 如果已存在但没有 API Key，且环境变量中有，则更新
    if not existing.get("api_key") and api_key:
        # 更新 API Key
        # 自动启用
    
    # 创建新配置时，如果有 API Key 则自动启用
    provider_data = {
        "api_key": api_key or "",
        "is_active": bool(api_key),  # 有 API Key 则自动启用
        # ...
    }
```

**特性**:
- ✅ 自动从环境变量读取 API Key
- ✅ 有 API Key 的聚合渠道自动启用
- ✅ 支持更新已存在但未配置 API Key 的聚合渠道
- ✅ 返回详细的统计信息（添加/更新/跳过数量）

### 3. 测试脚本

**文件**: `scripts/test_env_config.py`

**功能**:
- 检查聚合渠道环境变量配置状态
- 测试服务集成（环境变量读取）
- 提供配置建议
- 显示配置统计

**使用方法**:

```bash
python scripts/test_env_config.py
```

**输出示例**:

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

🧪 测试服务集成
============================================================
测试环境变量读取...
✅ 302ai: sk-xxxxxxxx...xxxx
⏭️ openrouter: 未配置
⏭️ oneapi: 未配置
⏭️ newapi: 未配置

✅ 服务集成测试通过

============================================================
📋 测试总结
============================================================

✅ 所有测试通过

下一步:
1. 启动后端服务
2. 调用初始化聚合渠道 API
3. 验证聚合渠道是否自动启用
```

### 4. 文档更新

**更新的文档**:

1. **AGGREGATOR_SUPPORT.md** - 添加环境变量配置章节
2. **AGGREGATOR_QUICKSTART.md** - 更新快速开始流程，优先推荐环境变量配置
3. **ENV_CONFIG_UPDATE.md** - 本文档，说明环境变量配置更新

## 🚀 使用指南

### 快速开始（推荐方式）

**步骤 1：配置环境变量**

编辑 `.env` 文件：

```bash
# 添加 302.AI API Key
AI302_API_KEY=sk-xxxxx
```

**步骤 2：验证配置**

```bash
python scripts/test_env_config.py
```

**步骤 3：初始化聚合渠道**

```bash
# 启动后端服务
python -m uvicorn app.main:app --reload

# 调用初始化 API
curl -X POST http://localhost:8000/api/config/llm/providers/init-aggregators \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**步骤 4：验证结果**

在前端界面查看：
1. 进入 **设置 → 配置管理 → 大模型厂家管理**
2. 找到 **302.AI**
3. 确认状态为 **已启用**
4. 确认显示 "已从环境变量获取 API Key"

### 传统方式（手动配置）

如果不使用环境变量，仍然可以通过前端界面手动配置：

1. 初始化聚合渠道
2. 在厂家列表中找到聚合渠道
3. 点击编辑，填写 API Key
4. 勾选启用，保存

## 📊 对比：环境变量 vs 手动配置

| 特性 | 环境变量配置 | 手动配置 |
|------|-------------|---------|
| **配置方式** | 编辑 .env 文件 | 前端界面操作 |
| **安全性** | ✅ 高（不暴露在界面） | ⚠️ 中（显示在界面） |
| **便捷性** | ✅ 自动读取 | ⚠️ 需手动输入 |
| **团队协作** | ✅ 每人独立配置 | ⚠️ 共享配置 |
| **多环境部署** | ✅ 支持 | ⚠️ 需手动切换 |
| **初始化后状态** | ✅ 自动启用 | ⚠️ 需手动启用 |

**推荐**: 优先使用环境变量配置

## 🔄 迁移指南

### 现有用户

如果你已经手动配置了聚合渠道：

1. **无需任何操作** - 现有配置不受影响
2. **可选迁移** - 如果想使用环境变量：
   - 在 `.env` 文件中添加 API Key
   - 删除数据库中的聚合渠道配置
   - 重新初始化聚合渠道

### 新用户

推荐使用环境变量配置：

1. 复制 `.env.example` 为 `.env`
2. 填写聚合渠道的 API Key
3. 运行测试脚本验证
4. 初始化聚合渠道

## ⚠️ 注意事项

### 1. 环境变量优先级

```
数据库配置 > 环境变量 > 默认值
```

- 如果数据库中已有 API Key，不会被环境变量覆盖
- 只有在数据库中没有 API Key 时，才会从环境变量读取

### 2. 安全性

- ✅ `.env` 文件已在 `.gitignore` 中，不会被提交到 Git
- ✅ 测试脚本会隐藏敏感信息（只显示前后几位）
- ⚠️ 不要在代码中硬编码 API Key

### 3. 占位符过滤

系统会自动过滤占位符：

```python
# 这些值会被视为未配置
"your_302ai_api_key_here"
"your_openrouter_api_key_here"
```

### 4. 更新已存在的配置

初始化方法会智能处理：

- 如果聚合渠道已存在且有 API Key → 跳过
- 如果聚合渠道已存在但没有 API Key，且环境变量中有 → 更新
- 如果聚合渠道不存在 → 创建

## 🧪 测试

### 单元测试

```bash
# 测试环境变量配置
python scripts/test_env_config.py

# 测试聚合渠道支持
python scripts/test_aggregator_support.py
```

### 集成测试

1. 配置环境变量
2. 启动后端服务
3. 调用初始化 API
4. 验证聚合渠道状态
5. 测试模型调用

## 📚 相关文档

- [聚合渠道完整文档](./AGGREGATOR_SUPPORT.md)
- [快速开始指南](./AGGREGATOR_QUICKSTART.md)
- [实现总结](./AGGREGATOR_IMPLEMENTATION_SUMMARY.md)
- [更新日志](./CHANGELOG_AGGREGATOR.md)

## 🎉 总结

本次更新为聚合渠道添加了环境变量配置支持，主要优势：

1. ✅ **更安全** - API Key 不暴露在界面
2. ✅ **更便捷** - 自动读取，无需手动配置
3. ✅ **更灵活** - 支持多环境部署
4. ✅ **更友好** - 提供测试脚本和详细文档

推荐所有用户使用环境变量配置聚合渠道！

