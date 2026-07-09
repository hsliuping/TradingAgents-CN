# 模型配置参数修复文档

## 📋 问题描述

在之前的实现中，后端虽然从数据库读取了用户配置的模型名称，但在创建 LLM 实例时，**所有的模型参数都是硬编码的**：

- `max_tokens`: 硬编码为 `2000`
- `temperature`: 硬编码为 `0.1`
- `timeout`: 部分硬编码或动态计算（阿里百炼）
- `retry_times`: 未使用

这导致用户在前端配置的模型参数（如超时时间、温度参数等）**完全没有生效**。

## ✅ 修复方案

### 1. 修改默认超时时间

将默认超时时间从 `60秒` 改为 `180秒`：

**修改的文件：**
- `frontend/src/views/Settings/components/LLMConfigDialog.vue` (第380行)
- `app/models/config.py` (第175行、第344行)

### 2. 修改配置传递流程

#### 2.1 修改 `create_analysis_config` 函数

**文件：** `app/services/simple_analysis_service.py`

**修改内容：**
- 添加两个新参数：`quick_model_config` 和 `deep_model_config`
- 将模型配置参数添加到返回的 config 字典中
- 添加日志输出，方便调试

```python
def create_analysis_config(
    research_depth,
    selected_analysts: list,
    quick_model: str,
    deep_model: str,
    llm_provider: str,
    market_type: str = "A股",
    quick_model_config: dict = None,  # 新增
    deep_model_config: dict = None    # 新增
) -> dict:
    # ... 其他代码 ...
    
    # 添加模型配置参数
    if quick_model_config:
        config["quick_model_config"] = quick_model_config
    
    if deep_model_config:
        config["deep_model_config"] = deep_model_config
    
    return config
```

#### 2.2 修改调用 `create_analysis_config` 的地方

**文件：** `app/services/analysis_service.py`

**修改内容：**
- 在调用 `create_analysis_config` 之前，从数据库读取模型的完整配置
- 将配置参数传递给 `create_analysis_config`

**修改的函数：**
1. `_execute_analysis_sync_with_progress` (第113-165行)
2. `_execute_analysis_sync` (第215-259行)
3. `execute_analysis_task` (第577-620行)

```python
# 从数据库读取模型的完整配置参数
quick_model_config = None
deep_model_config = None
llm_configs = unified_config.get_llm_configs()

for llm_config in llm_configs:
    if llm_config.model_name == quick_model:
        quick_model_config = {
            "max_tokens": llm_config.max_tokens,
            "temperature": llm_config.temperature,
            "timeout": llm_config.timeout,
            "retry_times": llm_config.retry_times,
            "api_base": llm_config.api_base
        }
    
    if llm_config.model_name == deep_model:
        deep_model_config = {
            "max_tokens": llm_config.max_tokens,
            "temperature": llm_config.temperature,
            "timeout": llm_config.timeout,
            "retry_times": llm_config.retry_times,
            "api_base": llm_config.api_base
        }

# 传递给 create_analysis_config
config = create_analysis_config(
    research_depth=task.parameters.research_depth,
    selected_analysts=task.parameters.selected_analysts or ["market", "fundamentals"],
    quick_model=quick_model,
    deep_model=deep_model,
    llm_provider=llm_provider,
    market_type=getattr(task.parameters, 'market_type', "A股"),
    quick_model_config=quick_model_config,  # 传递模型配置
    deep_model_config=deep_model_config     # 传递模型配置
)
```

#### 2.3 修改 TradingAgentsGraph

**文件：** `tradingagents/graph/trading_graph.py`

**修改内容：**
- 在 `__init__` 方法中，从 config 读取模型配置参数
- 使用配置中的参数创建 LLM 实例，而不是硬编码

**修改的供应商：**
1. OpenAI (第69-153行)
2. SiliconFlow (第69-153行)
3. OpenRouter (第69-153行)
4. Ollama (第154-228行)
5. Anthropic (第154-228行)
6. Google (第154-228行)
7. 阿里百炼/DashScope (第229-260行)
8. DeepSeek (第261-304行)
9. Custom OpenAI (第305-345行)
10. 千帆/Qianfan (第346-384行)

**示例代码（阿里百炼）：**

```python
# 从配置中读取模型参数（优先使用用户配置，否则使用默认值）
quick_config = self.config.get("quick_model_config", {})
deep_config = self.config.get("deep_model_config", {})

# 读取快速模型参数
quick_max_tokens = quick_config.get("max_tokens", 4000)
quick_temperature = quick_config.get("temperature", 0.7)
quick_timeout = quick_config.get("timeout", 180)

# 读取深度模型参数
deep_max_tokens = deep_config.get("max_tokens", 4000)
deep_temperature = deep_config.get("temperature", 0.7)
deep_timeout = deep_config.get("timeout", 180)

logger.info(f"🔧 [阿里百炼-快速模型] max_tokens={quick_max_tokens}, temperature={quick_temperature}, timeout={quick_timeout}s")
logger.info(f"🔧 [阿里百炼-深度模型] max_tokens={deep_max_tokens}, temperature={deep_temperature}, timeout={deep_timeout}s")

self.deep_thinking_llm = ChatDashScopeOpenAI(
    model=self.config["deep_think_llm"],
    temperature=deep_temperature,      # 使用用户配置
    max_tokens=deep_max_tokens,        # 使用用户配置
    request_timeout=deep_timeout       # 使用用户配置
)
self.quick_thinking_llm = ChatDashScopeOpenAI(
    model=self.config["quick_think_llm"],
    temperature=quick_temperature,     # 使用用户配置
    max_tokens=quick_max_tokens,       # 使用用户配置
    request_timeout=quick_timeout      # 使用用户配置
)
```

## 📊 修改总结

### 修改的文件列表

1. ✅ `frontend/src/views/Settings/components/LLMConfigDialog.vue` - 默认超时时间改为180秒
2. ✅ `app/models/config.py` - 默认超时时间改为180秒（2处）
3. ✅ `app/services/simple_analysis_service.py` - 添加模型配置参数传递
4. ✅ `app/services/analysis_service.py` - 从数据库读取并传递模型配置（3处）
5. ✅ `tradingagents/graph/trading_graph.py` - 使用配置参数而不是硬编码（10个供应商）

### 影响的供应商

所有 LLM 供应商都已修改，现在都会使用用户配置的参数：

1. ✅ OpenAI
2. ✅ SiliconFlow
3. ✅ OpenRouter
4. ✅ Ollama
5. ✅ Anthropic
6. ✅ Google AI
7. ✅ 阿里百炼 (DashScope)
8. ✅ DeepSeek
9. ✅ Custom OpenAI
10. ✅ 千帆 (Qianfan)

## 🧪 测试验证

运行测试脚本：

```bash
.\.venv\Scripts\python scripts/test_model_config_params.py
```

**测试结果：** ✅ 通过

测试验证了：
- ✅ 模型配置参数正确传递到 `create_analysis_config`
- ✅ 配置中包含 `quick_model_config` 和 `deep_model_config`
- ✅ 参数值与输入一致

## 📝 使用说明

### 用户配置流程

1. 用户在前端"系统设置"页面配置模型参数：
   - 最大Token数 (max_tokens)
   - 温度参数 (temperature)
   - 超时时间 (timeout) - 默认180秒
   - 重试次数 (retry_times)

2. 配置保存到数据库

3. 用户发起分析时：
   - 后端从数据库读取模型配置
   - 将配置参数传递给分析引擎
   - 分析引擎使用用户配置的参数创建 LLM 实例

### 日志验证

在分析日志中，可以看到类似的输出：

```
🔧 [阿里百炼-快速模型] max_tokens=6000, temperature=0.8, timeout=200s
🔧 [阿里百炼-深度模型] max_tokens=8000, temperature=0.5, timeout=300s
✅ [阿里百炼] 已应用用户配置的模型参数
```

## 🎯 修复效果

### 修复前

- ❌ 所有模型使用硬编码参数：`temperature=0.1`, `max_tokens=2000`
- ❌ 用户配置的参数不生效
- ❌ 超时时间默认60秒，可能导致长时间分析超时

### 修复后

- ✅ 所有模型使用用户配置的参数
- ✅ 用户可以自定义每个模型的参数
- ✅ 超时时间默认180秒，更合理
- ✅ 支持所有10个 LLM 供应商

## 🔍 注意事项

1. **默认值**：如果数据库中没有配置，会使用默认值：
   - `max_tokens`: 4000
   - `temperature`: 0.7
   - `timeout`: 180秒
   - `retry_times`: 3

2. **日志输出**：所有供应商都会输出配置参数到日志，方便调试

3. **向后兼容**：如果没有传递模型配置参数，会使用默认值，不会报错

## 📅 修改日期

2025-10-12

