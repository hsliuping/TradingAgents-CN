# 模型价格信息同步

## 📋 问题描述

从聚合平台（如 OpenRouter）获取模型列表时，API 返回了价格信息，但之前的实现没有解析和使用这些价格信息，导致：
1. ❌ 用户需要手动查询并填写价格
2. ❌ 容易填写错误
3. ❌ 工作量大

## ✅ 解决方案

实现**自动解析价格信息**功能，从 API 响应中提取价格数据并自动填充到模型目录中。

## 🔧 OpenRouter API 价格格式

### API 响应示例

```json
{
  "data": [
    {
      "id": "openai/gpt-4o",
      "name": "GPT-4o",
      "context_length": 128000,
      "pricing": {
        "prompt": "0.0000025",      // USD per token (输入)
        "completion": "0.00001",     // USD per token (输出)
        "image": "0",
        "request": "0"
      },
      "top_provider": {
        "context_length": 128000,
        "max_completion_tokens": 16384
      }
    }
  ]
}
```

### 价格单位说明

- **API 返回单位**：USD per token（每个 token 的美元价格）
- **系统使用单位**：USD per 1K tokens（每 1000 个 token 的美元价格）
- **转换公式**：`price_per_1k = price_per_token × 1000`

### 示例转换

| 模型 | API 返回（per token） | 转换后（per 1K tokens） |
|------|---------------------|----------------------|
| GPT-4o 输入 | 0.0000025 | 0.0025 |
| GPT-4o 输出 | 0.00001 | 0.01 |
| GPT-4o Mini 输入 | 0.00000015 | 0.00015 |
| GPT-4o Mini 输出 | 0.0000006 | 0.0006 |

## 🎯 实现细节

### 后端实现

**文件**：`app/services/config_service.py`

#### 1. 添加价格格式化方法

```python
def _format_models_with_pricing(self, models: list) -> list:
    """
    格式化模型列表，包含价格信息
    
    OpenRouter API 返回的价格单位是 USD per token
    我们需要转换为 USD per 1K tokens
    """
    formatted = []
    for model in models:
        model_id = model.get("id", "")
        model_name = model.get("name", model_id)
        
        # 获取价格信息
        pricing = model.get("pricing", {})
        prompt_price = pricing.get("prompt", "0")  # USD per token
        completion_price = pricing.get("completion", "0")  # USD per token
        
        # 转换为 float 并乘以 1000（转换为 per 1K tokens）
        try:
            input_price_per_1k = float(prompt_price) * 1000 if prompt_price else None
            output_price_per_1k = float(completion_price) * 1000 if completion_price else None
        except (ValueError, TypeError):
            input_price_per_1k = None
            output_price_per_1k = None
        
        # 获取上下文长度
        context_length = model.get("context_length")
        if not context_length:
            # 尝试从 top_provider 获取
            top_provider = model.get("top_provider", {})
            context_length = top_provider.get("context_length")
        
        formatted_model = {
            "id": model_id,
            "name": model_name,
            "context_length": context_length,
            "input_price_per_1k": input_price_per_1k,
            "output_price_per_1k": output_price_per_1k,
        }
        
        formatted.append(formatted_model)
    
    return formatted
```

#### 2. 在获取模型列表时调用

```python
# 过滤：只保留主流大厂的常用模型
filtered_models = self._filter_popular_models(all_models)

# 转换模型格式，包含价格信息
formatted_models = self._format_models_with_pricing(filtered_models)

return {
    "success": True,
    "models": formatted_models,
    "message": f"成功获取 {len(formatted_models)} 个常用模型（已过滤）"
}
```

### 前端实现

**文件**：`frontend/src/views/Settings/components/ModelCatalogManagement.vue`

#### 转换模型格式

```typescript
if (response.success && response.models && response.models.length > 0) {
  // 转换模型格式，包含价格信息
  formData.value.models = response.models.map((model: any) => ({
    name: model.id || model.name,
    display_name: model.name || model.id,
    // 使用 API 返回的价格信息（USD），如果没有则为 null
    input_price_per_1k: model.input_price_per_1k || null,
    output_price_per_1k: model.output_price_per_1k || null,
    context_length: model.context_length || null,
    // OpenRouter 的价格是 USD
    currency: 'USD'
  }))
  
  // 统计有价格信息的模型数量
  const modelsWithPricing = formData.value.models.filter(
    m => m.input_price_per_1k || m.output_price_per_1k
  ).length
  
  ElMessage.success(`成功获取 ${formData.value.models.length} 个模型（${modelsWithPricing} 个包含价格信息）`)
}
```

## 📊 数据流程

```
OpenRouter API
    ↓
返回价格（USD per token）
    ↓
后端解析并转换（USD per 1K tokens）
    ↓
返回给前端
    ↓
前端填充到表格
    ↓
用户可以查看/编辑
    ↓
保存到数据库
```

## 🎁 优势对比

| 特性 | 手动填写 | 自动同步 |
|------|---------|---------|
| 速度 | ❌ 慢 | ✅ 快 |
| 准确性 | ⚠️ 容易出错 | ✅ 准确 |
| 最新性 | ❌ 可能过时 | ✅ 实时 |
| 工作量 | ❌ 大 | ✅ 小 |
| 用户体验 | ❌ 繁琐 | ✅ 便捷 |

## 📝 使用说明

### 1. 从 API 获取模型列表

1. 打开"配置管理" → "模型目录管理"
2. 点击"添加厂家模型目录"
3. 选择聚合平台（如 OpenRouter）
4. 点击"从 API 获取模型列表"
5. 等待获取完成

### 2. 查看价格信息

获取完成后，表格中会自动填充：
- ✅ 模型名称
- ✅ 显示名称
- ✅ 输入价格（USD/1K tokens）
- ✅ 输出价格（USD/1K tokens）
- ✅ 上下文长度
- ✅ 货币单位（USD）

### 3. 编辑价格信息

如果需要调整价格：
1. 直接在表格中编辑
2. 修改输入/输出价格
3. 点击"保存"

### 4. 查看统计信息

前端会显示：
```
成功获取 18 个模型（18 个包含价格信息）
```

后端日志会显示：
```
💰 openai/gpt-4o: 输入=$0.002500/1K, 输出=$0.010000/1K
💰 openai/gpt-4o-mini: 输入=$0.000150/1K, 输出=$0.000600/1K
💰 anthropic/claude-3.5-sonnet: 输入=$0.003000/1K, 输出=$0.015000/1K
```

## 🔍 价格信息来源

### OpenRouter

- **API 端点**：`https://openrouter.ai/api/v1/models`
- **价格单位**：USD per token
- **更新频率**：实时
- **覆盖范围**：所有模型

### 其他聚合平台

#### 302.AI
- 可能需要单独实现价格解析逻辑
- 价格格式可能不同

#### One API / New API
- 通常兼容 OpenAI 格式
- 可能不返回价格信息

## ⚠️ 注意事项

### 1. 价格单位

- OpenRouter 返回的价格是 **USD**
- 如果需要转换为 CNY，需要手动转换或添加汇率转换功能

### 2. 价格更新

- 从 API 获取的价格是实时的
- 保存到数据库后，不会自动更新
- 如果价格变化，需要重新从 API 获取

### 3. 缺失价格

- 某些模型可能没有价格信息
- 这种情况下，价格字段为 `null`
- 用户可以手动填写

### 4. 货币单位

- 系统支持多种货币单位（USD、CNY 等）
- 从 OpenRouter 获取的价格统一使用 USD
- 手动添加的模型可以选择其他货币

## 🔄 未来优化

### 1. 汇率转换

自动将 USD 价格转换为 CNY：
```python
def convert_usd_to_cny(usd_price: float, exchange_rate: float = 7.2) -> float:
    """将 USD 价格转换为 CNY"""
    return usd_price * exchange_rate
```

### 2. 价格历史记录

记录价格变化历史：
- 价格变化时间
- 变化前后的价格
- 变化幅度

### 3. 价格预警

当价格变化超过阈值时发送通知：
- 价格上涨 > 10%
- 价格下降 > 10%

### 4. 批量更新价格

添加"更新所有模型价格"功能：
- 一键更新所有模型的价格
- 保留用户手动修改的价格

## 📚 相关文档

- [聚合平台模型目录智能管理](AGGREGATOR_MODEL_CATALOG.md)
- [模型列表智能过滤](MODEL_FILTERING.md)
- [OpenRouter API 文档](https://openrouter.ai/docs/api-reference/list-available-models)

## 🎉 总结

通过自动解析价格信息功能，用户可以：
- ✅ 快速获取准确的价格信息
- ✅ 避免手动查询和填写
- ✅ 确保价格信息是最新的
- ✅ 提升模型目录管理效率

---

**功能开发日期**：2025-10-12  
**开发人员**：AI Assistant  
**需求提出人**：用户

