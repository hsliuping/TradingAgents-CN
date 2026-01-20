# LLM 参数传递流程文档

## 📋 概述

本文档详细描述了 v2.0 架构中 LLM（大语言模型）参数的传递流程，包括：
- LLM provider 和 model 的指定方式
- API Key 的获取优先级
- Agent 配置中的执行参数（temperature、max_iterations、timeout）
- 参数如何从分析请求传递到最终的 LLM 实例

## 🎯 核心原则

1. **LLM Provider 和 Model 由分析流程指定**，不在 Agent 配置中
2. **Agent 配置只包含执行参数**：temperature、max_iterations、timeout
3. **API Key 获取优先级**：数据库模型配置 > 数据库厂家配置 > 环境变量
4. **Agent 特定的 temperature**：如果 Agent 配置了 temperature，创建新的 LLM 实例

## 📊 数据流图

```
分析请求
  │
  ├─> quick_analysis_model: "qwen-plus"
  ├─> deep_analysis_model: "qwen3-max"
  └─> selected_analysts: ["market", "fundamentals"]
      │
      ▼
UnifiedAnalysisEngine._execute_via_workflow()
  │
  ├─> 提取 LLM 配置
  │   ├─> quick_think_llm = quick_analysis_model
  │   └─> deep_think_llm = deep_analysis_model
  │
  └─> 构建 legacy_config
      │
      ▼
WorkflowBuilder.__init__(legacy_config)
  │
  └─> LegacyDependencyProvider.__init__(legacy_config)
      │
      ├─> 保存配置: self._config = legacy_config
      │   ├─> quick_think_llm: "qwen-plus"
      │   ├─> deep_think_llm: "qwen3-max"
      │   └─> 其他配置...
      │
      └─> _create_llm_instances()
          │
          ├─> 1. 获取模型名称
          │   ├─> quick_model = self._config.get("quick_think_llm")  # "qwen-plus"
          │   └─> deep_model = self._config.get("deep_think_llm")    # "qwen3-max"
          │
          ├─> 2. 根据模型名称获取配置
          │   └─> get_provider_and_url_by_model_sync(model)
          │       │
          │       ├─> 查询数据库 llm_configs 集合
          │       │   └─> 匹配 model_name = "qwen-plus"
          │       │       ├─> provider: "dashscope"
          │       │       ├─> api_key: "sk-xxx" (模型级别的 key)
          │       │       └─> backend_url: "https://..."
          │       │
          │       ├─> 如果模型配置中没有 api_key
          │       │   └─> 查询 llm_providers 集合
          │       │       └─> 匹配 name = "dashscope"
          │       │           └─> api_key: "sk-yyy" (厂家级别的 key)
          │       │
          │       └─> 如果数据库都没有
          │           └─> 从环境变量获取: DASHSCOPE_API_KEY
          │
          ├─> 3. 创建 LLM 实例
          │   └─> create_llm_by_provider(
          │       provider="dashscope",
          │       model="qwen-plus",
          │       api_key="sk-xxx",  # 优先级：模型 > 厂家 > 环境变量
          │       temperature=0.2,   # 默认值
          │       ...
          │   )
          │
          └─> 4. 保存实例
              ├─> self._quick_llm = ChatDashScopeOpenAI(...)
              └─> self._deep_llm = ChatDashScopeOpenAI(...)
              │
              ▼
WorkflowBuilder._create_agent_node()
  │
  ├─> 1. 从数据库加载 Agent 配置
  │   └─> agent_config_manager.get_agent_config(agent_id)
  │       └─> 返回: {
  │           "config": {
  │               "temperature": 0.2,      # Agent 特定的温度
  │               "max_iterations": 3,
  │               "timeout": 120
  │           }
  │           # ❌ 不包含 llm_provider 和 llm_model
  │       }
  │
  ├─> 2. 构建 AgentConfig
  │   └─> AgentConfig(**{
  │       **default_config.model_dump(),  # 排除 llm_provider/llm_model
  │       **execution_config,              # 只包含执行参数
  │       **node.config
  │   })
  │   └─> 结果: {
  │       "temperature": 0.2,      # ✅ Agent 配置的温度
  │       "max_iterations": 3,
  │       "timeout": 120
  │       # ❌ 不包含 llm_provider 和 llm_model
  │   }
  │
  ├─> 3. 判断使用哪个 LLM（quick 或 deep）
  │   └─> llm_type = "quick" 或 "deep"
  │       (根据 agent_id 判断)
  │
  ├─> 4. 获取 LLM 实例
  │   │
  │   ├─> 情况A: Agent 配置了 temperature
  │   │   └─> self._legacy_provider.get_llm(llm_type, temperature=0.2)
  │   │       │
  │   │       └─> _create_custom_llm(llm_type="quick", temperature=0.2)
  │   │           │
  │   │           ├─> 1. 获取模型名称（从系统配置）
  │   │           │   └─> model = self._config.get("quick_think_llm")  # "qwen-plus"
  │   │           │
  │   │           ├─> 2. 根据模型名称获取配置
  │   │           │   └─> get_provider_and_url_by_model_sync(model)
  │   │           │       └─> 返回: {
  │   │           │           "provider": "dashscope",
  │   │           │           "api_key": "sk-xxx",
  │   │           │           "backend_url": "https://..."
  │   │           │       }
  │   │           │
  │   │           ├─> 3. 创建自定义温度的 LLM
  │   │           │   └─> create_llm_by_provider(
  │   │           │       provider="dashscope",
  │   │           │       model="qwen-plus",
  │   │           │       temperature=0.2,  # ✅ Agent 配置的温度
  │   │           │       api_key="sk-xxx",
  │   │           │       ...
  │   │           │   )
  │   │           │
  │   │           └─> 返回: ChatDashScopeOpenAI(temperature=0.2)
  │   │
  │   └─> 情况B: Agent 没有配置 temperature
  │       └─> self._legacy_provider.get_llm(llm_type)
  │           └─> 返回: self._quick_llm 或 self._deep_llm
  │               (使用默认温度的 LLM 实例)
  │
  └─> 5. 创建 Agent
      └─> factory.create(
          agent_id="trader_v2",
          config=AgentConfig(...),  # 不包含 llm_provider/llm_model
          llm=ChatDashScopeOpenAI(...),  # ✅ 已创建的 LLM 实例
          tool_ids=[...],
          memory=...
      )
      │
      ▼
BaseAgent.__init__()
  │
  ├─> self.config = config  # AgentConfig（不包含 llm_provider/llm_model）
  ├─> self._llm = llm        # ✅ 传入的 LLM 实例
  │
  └─> initialize()
      │
      ├─> 如果 self._llm 已存在
      │   └─> 跳过 _setup_llm()  # ✅ 不尝试从 config 创建 LLM
      │
      └─> 如果 self._llm 为 None（不应该发生）
          └─> _setup_llm()
              └─> 警告：LLM 应该由分析流程传入
```

## 🔑 API Key 获取优先级

### 在 `get_provider_and_url_by_model_sync()` 中：

```
1. 数据库模型配置 (llm_configs 集合)
   └─> 查询条件: model_name = "qwen-plus"
       └─> 返回: api_key (如果存在)

2. 数据库厂家配置 (llm_providers 集合)
   └─> 查询条件: name = "dashscope"
       └─> 返回: api_key (如果存在)

3. 环境变量
   └─> os.getenv("DASHSCOPE_API_KEY")
       └─> 返回: api_key (如果存在)
```

### 在 `_create_custom_llm()` 中：

```
1. 用户显式指定 (self._config.get("quick_api_key"))
   └─> 优先级最高

2. 数据库配置 (从 get_provider_and_url_by_model_sync 返回)
   └─> 优先级中等

3. 环境变量 (在 create_llm_by_provider 中处理)
   └─> 优先级最低
```

## 📝 Agent 配置结构

### ✅ 正确的 Agent 配置（数据库 `agent_configs` 集合）：

```json
{
  "agent_id": "trader_v2",
  "config": {
    "temperature": 0.2,        // ✅ Agent 特定的温度
    "max_iterations": 3,       // ✅ 最大迭代次数
    "timeout": 120             // ✅ 超时时间
  }
  // ❌ 不包含 llm_provider
  // ❌ 不包含 llm_model
}
```

### ❌ 错误的 Agent 配置：

```json
{
  "agent_id": "trader_v2",
  "config": {
    "llm_provider": "deepseek",  // ❌ 不应该存在
    "llm_model": "deepseek-chat", // ❌ 不应该存在
    "temperature": 0.2
  }
}
```

## 🔍 关键代码位置

### 1. 分析请求处理
- **文件**: `app/services/unified_analysis_engine.py`
- **方法**: `_execute_via_workflow()`
- **作用**: 提取 `quick_analysis_model` 和 `deep_analysis_model`，构建 `legacy_config`

### 2. LLM 配置获取
- **文件**: `app/services/simple_analysis_service.py`
- **方法**: `get_provider_and_url_by_model_sync()`
- **作用**: 根据模型名称从数据库获取 provider、url、api_key

### 3. LLM 实例创建
- **文件**: `tradingagents/graph/trading_graph.py`
- **方法**: `create_llm_by_provider()`
- **作用**: 根据 provider 创建对应的 LLM 实例

### 4. Agent 配置过滤
- **文件**: `core/workflow/builder.py`
- **方法**: `_create_agent_node()`
- **作用**: 排除 `llm_provider` 和 `llm_model`，只保留执行参数

### 5. Agent 创建
- **文件**: `core/agents/base.py`
- **方法**: `initialize()`
- **作用**: 如果已传入 `llm`，跳过 `_setup_llm()`

## ⚠️ 常见错误

### 错误1: Agent 配置中包含 `llm_provider`
**现象**: 日志显示 `config: {'llm_provider': 'deepseek', ...}`
**原因**: `AgentConfig` 类有默认值 `llm_provider: str = "deepseek"`
**解决**: 在创建 `AgentConfig` 时排除这些字段

### 错误2: API Key 未正确传递
**现象**: LLM 调用失败，提示 API Key 未设置
**原因**: API Key 获取优先级不正确
**解决**: 确保优先级为：模型配置 > 厂家配置 > 环境变量

### 错误3: Agent 使用了错误的 LLM
**现象**: Agent 使用了默认 LLM 而不是分析流程指定的 LLM
**原因**: `_create_custom_llm()` 中模型名称获取错误
**解决**: 确保从 `self._config.get(f"{llm_type}_think_llm")` 获取模型名称

## 📌 检查清单

在调试 LLM 参数传递问题时，按以下顺序检查：

1. ✅ **分析请求中是否指定了模型**？
   - 检查 `quick_analysis_model` 和 `deep_analysis_model`

2. ✅ **LegacyDependencyProvider 是否正确保存了配置**？
   - 检查日志：`[依赖提供者] 用户传入配置: quick_model=..., deep_model=...`

3. ✅ **API Key 是否正确获取**？
   - 检查日志：`🔑 [API Key] 前3位: sk-`
   - 检查日志：`🔑 [API Key] 来源: 数据库配置/环境变量`

4. ✅ **Agent 配置中是否排除了 `llm_provider` 和 `llm_model`**？
   - 检查日志：`config: {...}` 中不应该有 `llm_provider` 和 `llm_model`

5. ✅ **Agent 是否使用了正确的 LLM 实例**？
   - 检查日志：`🤖 LLM 实例: ChatDashScopeOpenAI`
   - 检查日志：`✅ 成功使用 Agent 配置的温度: 0.2`

## 🔄 更新历史

- **2026-01-20**: 初始版本
  - 添加了完整的参数传递流程
  - 明确了 API Key 获取优先级
  - 说明了 Agent 配置的正确结构
  - 列出了常见错误和解决方案
