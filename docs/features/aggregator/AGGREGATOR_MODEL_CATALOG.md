# 聚合平台模型目录智能管理

## 📋 问题描述

对于聚合平台（如 302.AI、OpenRouter），它们支持多个厂家的多个模型。用户在添加模型目录时面临以下问题：

1. ❌ 不知道聚合平台支持哪些模型
2. ❌ 需要手动输入大量模型信息
3. ❌ 容易输入错误的模型名称
4. ❌ 需要查阅聚合平台的文档
5. ❌ 工作量大，耗时长

## ✅ 解决方案

实现**智能模型目录管理**功能，提供三种方式添加模型：

### 1. 🤖 从 API 自动获取（推荐）
- 自动调用聚合平台的 `/v1/models` 端点
- 获取最新的模型列表
- 自动填充到表格中

### 2. 📋 使用预设模板
- 提供常用模型的预设列表
- 一键导入

### 3. ✍️ 手动添加
- 保留手动添加功能
- 适用于特殊情况

## 🎯 功能特性

### 1. 智能识别聚合平台

系统会自动识别当前选择的厂家是否为聚合平台：
- 302.AI
- OpenRouter
- One API
- New API
- 自定义聚合渠道

如果是聚合平台，会显示特殊的功能按钮和提示信息。

### 2. 从 API 获取模型列表

**前提条件**：
- 已配置厂家的 API Key（数据库或环境变量）
- 已配置厂家的 API 基础地址 (`default_base_url`)

**操作步骤**：
1. 选择聚合平台厂家
2. 点击"从 API 获取模型列表"按钮
3. 系统自动调用 `/v1/models` 端点
4. 解析返回的模型列表
5. 自动填充到表格中

**优点**：
- ✅ 自动获取最新的模型列表
- ✅ 准确，不会出错
- ✅ 省时省力

### 3. 使用预设模板

**预设模板包含**：
- 常用的 OpenAI 模型（GPT-4o、GPT-4o Mini、GPT-3.5 Turbo 等）
- 常用的 Anthropic 模型（Claude 3.5 Sonnet、Claude 3 Opus 等）
- 常用的 Google 模型（Gemini 2.0 Flash、Gemini 1.5 Pro 等）
- 包含定价信息和上下文长度

**操作步骤**：
1. 选择聚合平台厂家
2. 点击"使用预设模板"按钮
3. 确认覆盖当前列表
4. 预设模型自动导入

**优点**：
- ✅ 快速导入常用模型
- ✅ 包含完整的定价信息
- ✅ 无需 API Key

### 4. 手动添加

保留原有的手动添加功能，适用于：
- 添加自定义模型
- 添加预设模板中没有的模型
- 微调模型信息

## 🔧 实现细节

### 前端实现

**文件**：`frontend/src/views/Settings/components/ModelCatalogManagement.vue`

#### 1. 智能识别聚合平台

```typescript
// 聚合平台列表
const aggregatorProviders = ['302ai', 'oneapi', 'newapi', 'openrouter', 'custom_aggregator']

// 计算属性：判断当前选择的是否为聚合平台
const isAggregatorProvider = computed(() => {
  return aggregatorProviders.includes(formData.value.provider)
})
```

#### 2. 条件显示特殊功能

```vue
<!-- 聚合平台特殊功能 -->
<template v-if="isAggregatorProvider">
  <el-button
    type="success"
    size="small"
    @click="handleFetchModelsFromAPI"
    :loading="fetchingModels"
  >
    <el-icon><Refresh /></el-icon>
    从 API 获取模型列表
  </el-button>
  <el-button
    type="warning"
    size="small"
    @click="handleUsePresetModels"
  >
    <el-icon><Document /></el-icon>
    使用预设模板
  </el-button>
</template>
```

#### 3. 友好提示

```vue
<el-alert
  v-if="isAggregatorProvider"
  title="💡 提示"
  type="info"
  :closable="false"
>
  聚合平台支持多个厂家的模型。您可以：
  <ul>
    <li>点击"从 API 获取模型列表"自动获取（需要配置 API Key）</li>
    <li>点击"使用预设模板"快速导入常用模型</li>
    <li>点击"手动添加模型"逐个添加</li>
  </ul>
</el-alert>
```

#### 4. 从 API 获取模型

```typescript
const handleFetchModelsFromAPI = async () => {
  // 检查前提条件
  if (!formData.value.provider) {
    ElMessage.warning('请先选择厂家')
    return
  }

  const provider = availableProviders.value.find(p => p.name === formData.value.provider)
  if (!provider?.extra_config?.has_api_key) {
    ElMessage.warning('该厂家未配置 API Key，无法获取模型列表')
    return
  }

  // 调用后端 API
  const response = await configApi.fetchProviderModels(formData.value.provider)
  
  if (response.success && response.models) {
    formData.value.models = response.models.map((model: any) => ({
      name: model.id || model.name,
      display_name: model.name || model.id,
      input_price_per_1k: null,
      output_price_per_1k: null,
      context_length: model.context_length || null,
      currency: 'CNY'
    }))
    
    ElMessage.success(`成功获取 ${formData.value.models.length} 个模型`)
  }
}
```

#### 5. 使用预设模板

```typescript
const getPresetModels = (providerName: string): ModelInfo[] => {
  const presets: Record<string, ModelInfo[]> = {
    '302ai': [
      // OpenAI 模型
      { name: 'gpt-4o', display_name: 'GPT-4o', input_price_per_1k: 0.005, output_price_per_1k: 0.015, context_length: 128000, currency: 'USD' },
      { name: 'gpt-4o-mini', display_name: 'GPT-4o Mini', input_price_per_1k: 0.00015, output_price_per_1k: 0.0006, context_length: 128000, currency: 'USD' },
      // ... 更多模型
    ],
    'openrouter': [
      // OpenRouter 格式的模型名称
      { name: 'openai/gpt-4o', display_name: 'GPT-4o', ... },
      // ... 更多模型
    ]
  }
  
  return presets[providerName] || []
}
```

### 后端实现

**文件**：
- `app/routers/config.py` - API 路由
- `app/services/config_service.py` - 业务逻辑

#### 1. API 端点

```python
@router.post("/llm/providers/{provider_id}/fetch-models", response_model=dict)
async def fetch_provider_models(
    provider_id: str,
    current_user: User = Depends(get_current_user)
):
    """从厂家 API 获取模型列表"""
    result = await config_service.fetch_provider_models(provider_id)
    return result
```

#### 2. 业务逻辑

```python
async def fetch_provider_models(self, provider_id: str) -> dict:
    """从厂家 API 获取模型列表"""
    # 1. 获取厂家信息
    provider_data = await providers_collection.find_one({"_id": ObjectId(provider_id)})
    
    # 2. 获取 API Key（数据库或环境变量）
    api_key = provider_data.get("api_key") or self._get_env_api_key(provider_name)
    
    # 3. 调用 /v1/models 端点
    url = f"{base_url}/v1/models"
    response = requests.get(url, headers={"Authorization": f"Bearer {api_key}"})
    
    # 4. 解析返回结果
    if response.status_code == 200:
        result = response.json()
        return {
            "success": True,
            "models": result["data"]
        }
```

## 📊 使用流程

### 场景 1：使用 API 自动获取（推荐）

1. 打开"配置管理" → "模型目录管理"
2. 点击"添加厂家模型目录"
3. 选择聚合平台（如 302.AI）
4. 点击"从 API 获取模型列表"
5. 等待获取完成
6. 查看并编辑模型信息（如定价）
7. 点击"保存"

### 场景 2：使用预设模板

1. 打开"配置管理" → "模型目录管理"
2. 点击"添加厂家模型目录"
3. 选择聚合平台（如 302.AI）
4. 点击"使用预设模板"
5. 确认导入
6. 查看并编辑模型信息
7. 点击"保存"

### 场景 3：手动添加

1. 打开"配置管理" → "模型目录管理"
2. 点击"添加厂家模型目录"
3. 选择聚合平台（如 302.AI）
4. 点击"手动添加模型"
5. 逐个填写模型信息
6. 点击"保存"

## 🎁 优势对比

| 特性 | 手动添加 | 预设模板 | API 自动获取 |
|------|---------|---------|-------------|
| 速度 | ❌ 慢 | ✅ 快 | ✅ 快 |
| 准确性 | ⚠️ 容易出错 | ✅ 准确 | ✅ 准确 |
| 最新性 | ❌ 可能过时 | ⚠️ 可能过时 | ✅ 最新 |
| 完整性 | ⚠️ 可能遗漏 | ⚠️ 常用模型 | ✅ 全部模型 |
| 定价信息 | ❌ 需手动查询 | ✅ 已包含 | ⚠️ 需手动补充 |
| 前提条件 | ✅ 无 | ✅ 无 | ⚠️ 需 API Key |

## 📝 注意事项

### 1. API Key 要求

从 API 获取模型列表需要配置 API Key：
- 可以在数据库中配置（厂家管理页面）
- 可以在 `.env` 文件中配置（环境变量）

### 2. API 基础地址

需要在厂家配置中设置 `default_base_url`：
- 302.AI: `https://api.302.ai`
- OpenRouter: `https://openrouter.ai/api`

### 3. 定价信息

从 API 获取的模型列表通常不包含定价信息，需要手动补充：
- 可以参考聚合平台的官方文档
- 可以使用预设模板中的定价信息

### 4. 模型名称格式

不同聚合平台的模型名称格式可能不同：
- 302.AI: `gpt-4o`
- OpenRouter: `openai/gpt-4o`

## 📚 相关文档

- [聚合渠道支持文档](AGGREGATOR_SUPPORT.md)
- [模型目录厂家选择优化](MODEL_CATALOG_PROVIDER_SELECT.md)
- [环境变量配置更新说明](ENV_CONFIG_UPDATE.md)

## 🎉 总结

通过智能模型目录管理功能，用户可以：
- ✅ 快速获取聚合平台的模型列表
- ✅ 避免手动输入错误
- ✅ 节省大量时间
- ✅ 保持模型列表最新

这大大提升了聚合平台的使用体验！

---

**功能开发日期**：2025-10-12  
**开发人员**：AI Assistant  
**需求提出人**：用户

