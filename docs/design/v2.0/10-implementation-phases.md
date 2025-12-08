# 实施阶段详细计划

## 📋 概述

本文档提供每个实施阶段的详细任务分解和优先级。

---

## 🚀 阶段 1: 基础设施准备 (第 1 周)

### 任务清单

| 优先级 | 任务 | 预估时间 | 依赖 |
|--------|------|----------|------|
| P0 | 创建 core/ 目录结构 | 2h | - |
| P0 | 添加 core/LICENSE | 1h | - |
| P0 | 创建 core/__init__.py | 1h | - |
| P1 | 创建各子模块骨架 | 4h | - |
| P1 | 配置 pyproject.toml | 2h | - |
| P2 | 更新根目录 LICENSE | 1h | - |

### 交付物

```
core/
├── LICENSE
├── __init__.py
├── workflow/
│   └── __init__.py
├── llm/
│   └── __init__.py
├── agents/
│   └── __init__.py
├── prompts/
│   └── __init__.py
└── licensing/
    └── __init__.py
```

---

## 🚀 阶段 2: 统一 LLM 客户端 (第 2-3 周)

### 任务清单

| 优先级 | 任务 | 预估时间 | 依赖 |
|--------|------|----------|------|
| P0 | 定义 LLMConfig, LLMResponse 模型 | 4h | 阶段1 |
| P0 | 实现 BaseAdapter 抽象类 | 4h | - |
| P0 | 实现 OpenAICompatAdapter | 8h | BaseAdapter |
| P0 | 实现 GoogleAdapter | 8h | BaseAdapter |
| P1 | 实现 AnthropicAdapter | 4h | BaseAdapter |
| P0 | 实现 ToolCallNormalizer | 8h | - |
| P0 | 实现 UnifiedLLMClient | 8h | 所有适配器 |
| P1 | 编写单元测试 | 8h | UnifiedLLMClient |
| P2 | 编写集成测试 | 4h | 单元测试 |

### 交付物

```
core/llm/
├── __init__.py
├── models.py           # LLMConfig, LLMResponse, Message, ToolCall
├── unified_client.py   # UnifiedLLMClient
├── tool_normalizer.py  # ToolCallNormalizer
└── providers/
    ├── __init__.py
    ├── base.py         # BaseAdapter
    ├── openai_compat.py
    ├── google.py
    └── anthropic.py
```

---

## 🚀 阶段 3: 智能体基类 (第 4-5 周)

### 任务清单

| 优先级 | 任务 | 预估时间 | 依赖 |
|--------|------|----------|------|
| P0 | 定义 AgentMetadata, AgentConfig 模型 | 4h | 阶段2 |
| P0 | 实现 BaseAgent 抽象类 | 12h | UnifiedLLMClient |
| P0 | 实现 AgentRegistry | 8h | BaseAgent |
| P1 | 实现 AgentFactory | 4h | AgentRegistry |
| P0 | 迁移 MarketAnalyst | 8h | BaseAgent |
| P1 | 迁移 NewsAnalyst | 6h | MarketAnalyst |
| P1 | 迁移 FundamentalsAnalyst | 6h | - |
| P1 | 迁移 SocialAnalyst | 6h | - |
| P2 | 迁移 Researchers | 8h | - |
| P2 | 迁移 Traders | 4h | - |
| P1 | 编写单元测试 | 8h | 所有迁移 |

### 交付物

```
core/agents/
├── __init__.py
├── base.py             # BaseAgent
├── registry.py         # AgentRegistry
├── factory.py          # AgentFactory
├── config.py           # AgentMetadata, AgentConfig
└── builtin/
    ├── __init__.py
    ├── analysts/
    │   ├── market.py
    │   ├── news.py
    │   ├── fundamentals.py
    │   └── social.py
    ├── researchers/
    │   ├── bull.py
    │   └── bear.py
    └── traders/
        └── trader.py
```

---

## 🚀 阶段 4: 工作流引擎 (第 6-8 周)

### 任务清单

| 优先级 | 任务 | 预估时间 | 依赖 |
|--------|------|----------|------|
| P0 | 定义 WorkflowDefinition 模型 | 8h | 阶段3 |
| P0 | 实现 WorkflowBuilder | 16h | AgentRegistry |
| P0 | 实现 WorkflowEngine | 16h | WorkflowBuilder |
| P0 | 实现 WorkflowValidator | 8h | WorkflowDefinition |
| P1 | 实现 WorkflowSerializer | 4h | - |
| P0 | 创建默认工作流模板 | 4h | - |
| P0 | 实现工作流 CRUD API | 12h | WorkflowEngine |
| P0 | 实现工作流执行 API (SSE) | 12h | - |
| P1 | 编写单元测试 | 8h | - |
| P1 | 编写集成测试 | 8h | - |

### 交付物

```
core/workflow/
├── __init__.py
├── models.py           # WorkflowDefinition, NodeDefinition, EdgeDefinition
├── engine.py           # WorkflowEngine
├── builder.py          # WorkflowBuilder
├── validator.py        # WorkflowValidator
├── serializer.py       # WorkflowSerializer
└── templates/
    ├── default.json
    ├── quick_analysis.json
    └── deep_research.json

app/routers/
└── workflow.py         # 工作流 API
```

---

## 🚀 阶段 5: 前端工作流编辑器 (第 9-11 周)

### 任务清单

| 优先级 | 任务 | 预估时间 | 依赖 |
|--------|------|----------|------|
| P0 | 安装 Vue Flow 依赖 | 2h | - |
| P0 | 创建 WorkflowDesigner 页面 | 4h | - |
| P0 | 实现 FlowCanvas 组件 | 16h | - |
| P0 | 实现 NodePalette 组件 | 8h | - |
| P0 | 实现 PropertyPanel 组件 | 12h | - |
| P0 | 实现自定义节点 (8种) | 16h | - |
| P1 | 实现条件边 | 8h | - |
| P0 | 实现工作流保存/加载 | 8h | API |
| P0 | 实现工作流执行 | 8h | API |
| P1 | 实现撤销/重做 | 8h | - |
| P2 | 实现导入/导出 | 4h | - |
| P1 | 添加路由配置 | 2h | - |

### 交付物

```
frontend/src/views/WorkflowDesigner/
├── index.vue
├── components/
│   ├── FlowCanvas.vue
│   ├── NodePalette.vue
│   ├── PropertyPanel.vue
│   ├── Toolbar.vue
│   └── WorkflowList.vue
├── nodes/
│   ├── AnalystNode.vue
│   ├── ResearcherNode.vue
│   ├── TraderNode.vue
│   ├── RiskNode.vue
│   ├── ManagerNode.vue
│   ├── ConditionNode.vue
│   ├── ParallelNode.vue
│   └── MergeNode.vue
├── edges/
│   └── ConditionalEdge.vue
├── composables/
│   ├── useWorkflow.ts
│   ├── useNodeDrag.ts
│   └── useValidation.ts
└── types/
    └── workflow.ts
```

---

## 🚀 阶段 6: 授权系统 (第 12 周)

### 任务清单

| 优先级 | 任务 | 预估时间 | 依赖 |
|--------|------|----------|------|
| P0 | 定义许可证数据模型 | 4h | - |
| P0 | 实现 LicenseManager | 8h | - |
| P0 | 实现 FeatureGate | 8h | LicenseManager |
| P1 | 实现 UsageTracker | 8h | - |
| P0 | 实现许可证 API | 8h | - |
| P0 | 集成到工作流引擎 | 4h | - |
| P1 | 集成到前端 | 4h | - |

### 交付物

```
core/licensing/
├── __init__.py
├── models.py           # License, LicenseFeatures
├── manager.py          # LicenseManager
├── features.py         # FeatureGate
├── validator.py        # LicenseValidator
└── usage_tracker.py    # UsageTracker
```

---

## 📊 总工时估算

| 阶段 | 预估工时 | 人天 (8h/天) |
|------|----------|--------------|
| 阶段 1 | 11h | 1.5 天 |
| 阶段 2 | 56h | 7 天 |
| 阶段 3 | 74h | 9 天 |
| 阶段 4 | 96h | 12 天 |
| 阶段 5 | 96h | 12 天 |
| 阶段 6 | 44h | 5.5 天 |
| **总计** | **377h** | **47 天** |

> 注: 以上为纯开发时间，不含测试、文档、会议等

