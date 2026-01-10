# LLM 模型过滤机制

## 📋 概述

本文档说明 TradingAgents-CN Pro 中 LLM 模型的过滤机制，确保只返回真正可用的模型（有有效 API Key 的模型）。

---

## 🎯 问题背景

### 问题描述

- `GET /api/config/llm` 接口返回所有启用的模型
- 但有些厂家虽然启用（`is_active=true`），但没有配置 API Key
- 这些模型无法使用，不应该在列表中显示

### 示例

```json
{
  "name": "deepseek",
  "display_name": "DeepSeek",
  "is_active": true,
  "extra_config": {
    "has_api_key": false  // ❌ 没有 API Key
  }
}
```

---

## 🔧 解决方案

### 核心函数

**`app/utils/api_key_utils.py`**:

```python
def has_valid_api_key(llm_config, providers_dict: Optional[dict] = None) -> bool:
    """
    判断 LLM 配置是否有有效的 API Key
    
    检查顺序（与 /api/config/llm/providers 接口逻辑一致）：
    1. 检查模型配置中的 api_key
    2. 检查厂家配置中的 api_key（如果提供了 providers_dict）
    3. 检查环境变量中的 api_key
    
    Args:
        llm_config: LLM 配置对象（LLMConfig 或字典）
        providers_dict: 厂家配置字典 {provider_name: LLMProvider}，可选
        
    Returns:
        bool: 是否有有效的 API Key（与 has_api_key 字段逻辑一致）
    """
```

### 过滤逻辑

**`app/routers/config.py` - `GET /api/config/llm`**:

```python
# 🔥 过滤条件：
# 1. 模型必须启用（enabled=True）
# 2. 供应商必须启用（is_active=True）
# 3. 必须有有效的 API Key（模型配置、厂家配置或环境变量中至少有一个）
filtered_configs = [
    llm_config for llm_config in config.llm_configs
    if llm_config.enabled 
    and llm_config.provider in active_provider_names
    and has_valid_api_key(llm_config, providers_dict)
]
```

---

## 📊 API Key 检查顺序

### 1. 模型配置中的 API Key

```python
# system_configs.llm_configs[].api_key
if is_valid_api_key(llm_config.api_key):
    return True
```

### 2. 厂家配置中的 API Key

```python
# llm_providers[].api_key
provider = providers_dict.get(llm_config.provider)
if provider and is_valid_api_key(provider.api_key):
    return True
```

### 3. 环境变量中的 API Key

```python
# 环境变量：{PROVIDER_NAME}_API_KEY
env_key = get_env_api_key_for_provider(llm_config.provider)
if env_key:
    return True
```

---

## 🔍 API Key 有效性判断

**`app/utils/api_key_utils.py` - `is_valid_api_key()`**:

```python
def is_valid_api_key(api_key: Optional[str]) -> bool:
    """
    判断 API Key 是否有效
    
    有效的 API Key 必须满足：
    1. 不能为空
    2. 长度必须 > 10
    3. 不能是占位符（前缀：your_, your-）
    4. 不能是占位符（后缀：_here, -here）
    5. 不能是截断的密钥（包含 '...'）
    """
```

---

## 📍 应用位置

### 1. REST API 接口

**`app/routers/config.py`**:

- `GET /api/config/llm` - 获取所有大模型配置

### 2. 兼容层

**`app/core/config_compat.py`**:

- `ConfigCompat.get_models()` - 获取模型配置列表

### 3. 统一配置

**`app/core/unified_config.py`**:

- `UnifiedConfig.get_llm_configs()` - 从 JSON 文件读取（后备方案）

---

## 🧪 测试

### 测试脚本

```bash
python scripts/test_llm_filter.py
```

### 测试输出

```
📊 步骤 4: 测试模型过滤
   原始模型数量: 32
   - 启用的模型: 26
   - 厂家启用的模型: 24
   - 有 API Key 的模型: 5
   - 过滤后的模型: 5

📊 步骤 5: 过滤后的模型列表
   ✅ qwen-turbo                     (dashscope)
   ✅ qwen-plus-latest               (dashscope)
   ✅ deepseek-chat                  (deepseek)
   ✅ gemini-2.5-pro                 (google)
   ✅ gemini-2.5-flash               (google)
```

---

## 🔗 相关接口

### `/api/config/llm/providers`

返回厂家配置，包含 `has_api_key` 字段：

```json
{
  "name": "dashscope",
  "display_name": "阿里云百炼",
  "is_active": true,
  "extra_config": {
    "has_api_key": true  // ✅ 有 API Key
  }
}
```

### `/api/config/llm`

返回模型配置，已过滤掉没有 API Key 的模型：

```json
[
  {
    "provider": "dashscope",
    "model_name": "qwen-turbo",
    "enabled": true
  }
]
```

---

**最后更新**: 2026-01-10  
**相关文档**: 
- `app/utils/api_key_utils.py`
- `app/routers/config.py`
- `scripts/test_llm_filter.py`

