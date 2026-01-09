# 调试日志指南

## 📋 概述

本文档说明了系统中关键位置的调试日志，方便追踪 Agent 创建和工具绑定流程。

---

## 🔍 日志追踪流程

### 完整调用链路

```
调试接口 (templates_debug.py)
    ↓
WorkflowEngine (engine.py)
    ↓
GraphBuilder (builder.py)
    ↓
AgentFactory (factory.py)
    ↓
BaseAgent (base.py)
    ↓
Agent 子类 (如 SectorAnalystV2)
```

---

## 📝 日志位置和含义

### 1. 调试接口 (`app/routers/templates_debug.py`)

**位置**: `_debug_v2_agent()` 函数

**日志内容**:
```
✅ [v2.0调试] 从数据库加载 Agent 配置: sector_analyst_v2
   - 启用状态: True
   - 执行配置: {'temperature': 0.7, 'max_iterations': 3}
   - 提示词模板: agent/sector_analyst_v2

✅ [v2.0调试] 从 BindingManager 获取工具: sector_analyst_v2 -> ['get_china_market_overview', 'get_sector_performance']

🔧 [v2.0调试] 创建工作流引擎...
   - Agent ID: sector_analyst_v2
   - 工作流 ID: single_agent_sector_analyst_v2
   - 自定义 LLM: 是

====================================================================================================
📝 [v2.0调试] 开始执行v2.0工作流...
   - 输入参数: ['stock_symbol', 'ticker', 'analysis_date', ...]
   - 股票代码: 000002
   - 分析日期: 2026-01-09
====================================================================================================
```

**作用**: 确认调试接口是否正确加载了 Agent 配置和工具绑定。

---

### 2. GraphBuilder (`core/workflow/builder.py`)

**位置**: `_create_agent_node()` 方法

**日志内容**:
```
================================================================================
[智能体创建] 🚀 开始创建 Agent: sector_analyst_v2
   - 节点 ID: sector_analyst_v2
   - 节点标签: Sector Analyst V2
   - 工作流 ID: single_agent_sector_analyst_v2

[智能体创建] 📋 从数据库加载 Agent 配置: sector_analyst_v2
   - 执行配置: {'temperature': 0.7, 'max_iterations': 3}

[智能体创建] 🔧 从 BindingManager 获取工具 (Agent 级别): sector_analyst_v2 -> ['get_china_market_overview', 'get_sector_performance']

[智能体创建] 🔧 sector_analyst_v2 使用快速分析模型 (quick_think_llm)

[智能体创建] 🤖 LLM 实例: ChatOpenAI
   - 使用自定义 LLM (llm_override)

[智能体创建] 📦 调用 factory.create()...
   - agent_id: sector_analyst_v2
   - config: {'temperature': 0.7, 'max_iterations': 3, ...}
   - llm: ChatOpenAI
   - tool_ids: ['get_china_market_overview', 'get_sector_performance']

[智能体创建] ✅ Agent 实例创建成功: SectorAnalystV2

[智能体创建] 📊 Agent 最终状态:
   - Agent ID: sector_analyst_v2
   - Agent 类型: SectorAnalystV2
   - 是否有 LLM: True
   - 是否有工具: True
   - 工具数量: 2
   - 工具列表: ['get_china_market_overview', 'get_sector_performance']
================================================================================
```

**作用**: 确认 GraphBuilder 是否正确加载配置、获取工具、创建 Agent。

---

### 3. AgentFactory (`core/agents/factory.py`)

**位置**: `create()` 方法

**日志内容**:
```
[AgentFactory] 🏭 开始创建 Agent: sector_analyst_v2
   - config: {'temperature': 0.7, 'max_iterations': 3, ...}
   - llm: ChatOpenAI
   - tool_ids: ['get_china_market_overview', 'get_sector_performance']
   - config_overrides: {}

[AgentFactory] 🔍 检查 Agent 构造函数签名:
   - Agent 类: SectorAnalystV2
   - 支持 llm 参数: True
   - 构造函数参数: ['self', 'config', 'llm', 'tool_ids']

[AgentFactory] ✅ 使用 v2.0 方式创建 Agent: sector_analyst_v2
   - 传递参数: config=True, llm=True, tool_ids=['get_china_market_overview', 'get_sector_performance']

[AgentFactory] ✅ Agent 创建完成: sector_analyst_v2
   - Agent 类型: SectorAnalystV2
   - 是否有 _llm: True
   - 是否有 _tools: True
   - _llm 值: ChatOpenAI
   - _tools 值: [<Tool: get_china_market_overview>, <Tool: get_sector_performance>]
   - 工具数量: 2
   - 工具名称: ['get_china_market_overview', 'get_sector_performance']
```

**作用**: 确认 AgentFactory 是否使用 v2.0 方式创建 Agent，参数是否正确传递。

---

### 4. BaseAgent (`core/agents/base.py`)

**位置**: `__init__()` 方法

**日志内容**:
```
[BaseAgent] 🚀 开始初始化 Agent
   - config: {'temperature': 0.7, 'max_iterations': 3, ...}
   - llm: ChatOpenAI
   - tool_ids: ['get_china_market_overview', 'get_sector_performance']

[BaseAgent] 🔧 开始加载工具: ['get_china_market_overview', 'get_sector_performance']

🔧 [Agent sector_analyst_v2] 开始加载工具: ['get_china_market_overview', 'get_sector_performance']
✅ [Agent sector_analyst_v2] 成功加载工具: get_china_market_overview
✅ [Agent sector_analyst_v2] 成功加载工具: get_sector_performance
🔧 [Agent sector_analyst_v2] 工具加载完成: 2/2 个工具

[BaseAgent] ✅ 工具加载完成，工具数量: 2

[BaseAgent] ✅ Agent 初始化完成
   - Agent ID: sector_analyst_v2
   - _llm: ChatOpenAI
   - _langchain_tools 数量: 2
```

**作用**: 确认 BaseAgent 是否正确接收参数、加载工具。

---

## 🔧 如何使用这些日志

### 1. 检查配置加载

搜索日志中的：
```
从数据库加载 Agent 配置
```

如果看到 `⚠️ 未找到 Agent 配置`，说明数据库中没有该 Agent 的配置。

### 2. 检查工具绑定

搜索日志中的：
```
从 BindingManager 获取工具
```

如果看到 `⚠️ 未找到绑定的工具`，说明数据库中没有工具绑定。

### 3. 检查 Agent 创建方式

搜索日志中的：
```
使用 v2.0 方式创建 Agent
```

如果看到 `⚠️ 使用旧版方式创建 Agent`，说明 Agent 不支持 v2.0 初始化。

### 4. 检查工具加载

搜索日志中的：
```
工具加载完成: X/Y 个工具
```

如果 X < Y，说明有工具加载失败。

---

## 📊 日志示例：成功 vs 失败

### ✅ 成功案例

```
✅ [v2.0调试] 从数据库加载 Agent 配置: sector_analyst_v2
✅ [v2.0调试] 从 BindingManager 获取工具: sector_analyst_v2 -> ['get_china_market_overview', 'get_sector_performance']
[智能体创建] ✅ Agent 实例创建成功: SectorAnalystV2
[智能体创建] 工具数量: 2
```

### ❌ 失败案例

```
⚠️ [v2.0调试] 未找到 Agent 配置，使用默认配置: sector_analyst_v2
⚠️ [v2.0调试] 未找到绑定的工具: sector_analyst_v2
[智能体创建] ⚠️ 未找到任何工具绑定: sector_analyst_v2
[智能体创建] 工具数量: 0  ← 问题！
```

---

**最后更新**: 2026-01-09  
**相关文件**:
- `app/routers/templates_debug.py`
- `core/workflow/builder.py`
- `core/agents/factory.py`
- `core/agents/base.py`

