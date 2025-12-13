# 插件化智能体架构 v2.0

**版本**: 2.0.0
**状态**: 🚧 开发中（阶段1、2、3已完成）
**最后更新**: 2025-12-13

---

## 📚 文档索引

| # | 文档 | 状态 | 说明 |
|---|------|------|------|
| 00 | [架构总览](./00-architecture-overview.md) | ✅ | 整体架构、核心组件、数据流 |
| 01 | [工具层设计](./01-tool-layer-design.md) | ✅ | 工具独立化、注册中心、装饰器 |
| 02 | [Agent层设计](./02-agent-layer-design.md) | ✅ | Agent 动态工具绑定、工厂模式 |
| 03 | [工作流层设计](./03-workflow-layer-design.md) | ✅ | Workflow 动态 Agent 组装 |
| 04 | [数据库设计](./04-database-design.md) | ✅ | 6个集合、绑定关系、配置优先级 |
| 05 | [迁移方案](./05-migration-plan.md) | ✅ | 6阶段迁移、风险缓解、回滚方案 |
| 06 | [状态层设计](./06-state-layer-design.md) | ✅ | Agent IO 声明、动态状态生成 |
| 07 | [阶段1完成报告](./07-phase1-completion-report.md) | ✅ | 基础设施准备完成报告 |
| 08 | [使用示例](./08-usage-examples.md) | ✅ | 各组件使用示例代码 |
| 09 | [阶段2完成报告](./09-phase2-completion-report.md) | ✅ | 工具层迁移完成报告 |
| 10 | [阶段3完成报告](./10-phase3-completion-report.md) | ✅ | Agent层迁移完成报告 |

---

## 🎯 核心目标

实现**完全解耦**的插件化架构：

```
Tools（工具）→ 独立定义，可注册到任意 Agent
   ↓
Agents（智能体）→ 独立定义，可注册到任意 Workflow
   ↓
Workflows（工作流）→ 配置化定义，动态执行
   ↓
State（状态）→ 根据 Agent 自动生成
```

---

## 🏗️ 架构层次

### 1. 工具层（Tool Layer）
- **独立工具定义**：每个工具是独立的函数或类
- **装饰器注册**：`@register_tool` 自动注册到 ToolRegistry
- **ToolRegistry**：管理所有工具的元数据和实现
- **ToolLoader**：动态加载工具模块

### 2. Agent层（Agent Layer）
- **Agent元数据**：定义 Agent 的基本信息、输入输出
- **动态工具绑定**：从 BindingManager 获取工具列表
- **AgentFactory**：根据配置创建 Agent 实例
- **AgentRegistry**：管理所有 Agent 的元数据

### 3. 工作流层（Workflow Layer）
- **工作流定义**：JSON/YAML 配置文件
- **动态 Agent 组装**：从 BindingManager 获取 Agent 列表
- **WorkflowBuilder**：根据配置构建 LangGraph
- **WorkflowEngine**：执行工作流

### 4. 状态层（State Layer）
- **Agent IO 定义**：声明输入、输出、依赖字段
- **StateSchemaBuilder**：根据 Agent 列表动态生成状态 Schema
- **StateRegistry**：缓存和管理状态 Schema
- **TypedDict 生成**：自动生成 LangGraph 状态类

---

## 📦 已完成组件（阶段1）

### 核心组件

| 组件 | 文件 | 状态 | 说明 |
|------|------|------|------|
| **BindingManager** | `core/config/binding_manager.py` | ✅ | 管理工具-Agent、Agent-工作流绑定 |
| **ToolRegistry** | `core/tools/registry.py` | ✅ | 工具注册表（增强版） |
| **StateSchemaBuilder** | `core/state/builder.py` | ✅ | 动态状态 Schema 构建器 |
| **StateRegistry** | `core/state/registry.py` | ✅ | 状态注册表 |
| **LegacyToolkitAdapter** | `core/compat/legacy_adapter.py` | ✅ | 旧工具适配器 |

### 数据库集合

| 集合 | 状态 | 说明 |
|------|------|------|
| `tool_configs` | ✅ | 工具配置 |
| `agent_configs` | ✅ | Agent 配置 |
| `workflow_definitions` | ✅ | 工作流定义 |
| `tool_agent_bindings` | ✅ | 工具-Agent 绑定 |
| `agent_workflow_bindings` | ✅ | Agent-工作流 绑定 |
| `agent_io_definitions` | ✅ | Agent IO 定义 |

### 脚本

| 脚本 | 状态 | 说明 |
|------|------|------|
| `scripts/setup/init_plugin_architecture_db.py` | ✅ | 数据库初始化脚本 |

---

## 🚀 迁移进度

```
阶段1: 基础设施准备 ✅ 完成 (2天)
  ├─ 数据库集合初始化 ✅
  ├─ BindingManager 实现 ✅
  ├─ 兼容层创建 ✅
  ├─ ToolRegistry 增强 ✅
  └─ 状态层组件 ✅

阶段2: 工具层迁移 ✅ 完成 (3天)
  ├─ BaseTool 基类和装饰器 ✅
  ├─ ToolLoader 工具加载器 ✅
  ├─ 迁移4个核心统一工具 ✅
  └─ 测试验证（所有测试通过）✅

阶段3: Agent层迁移 ✅ 完成 (3天)
  ├─ 增强 BaseAgent 基类 ✅
  ├─ 增强 AgentFactory 工厂类 ✅
  ├─ 创建示例 Agent (MarketAnalystAgentV2) ✅
  └─ 测试验证（所有测试通过）✅

阶段4: 状态层迁移 ⏳ 待开始 (2天)
  ├─ 迁移 Agent IO 定义
  ├─ 集成 StateSchemaBuilder
  ├─ 更新 WorkflowBuilder
  └─ 验证状态流转

阶段5: 工作流层迁移 ⏳ 待开始 (2天)
  ├─ 更新 WorkflowBuilder
  ├─ 动态 Agent 加载
  ├─ 迁移现有工作流
  └─ 集成测试

阶段6: 清理和优化 ⏳ 待开始 (2天)
  ├─ 删除旧代码
  ├─ 性能优化
  ├─ 文档更新
  └─ 最终测试
```

**总进度**: 16.7% (1/6 阶段完成)

---

## 💡 核心特性

### 1. 完全解耦
- 工具、Agent、工作流独立定义
- 通过配置动态组合
- 无硬编码依赖

### 2. 配置驱动
- 数据库存储配置
- 支持运行时更新
- 配置优先级：数据库 > 代码

### 3. 动态状态
- 根据 Agent 自动生成状态 Schema
- 自动依赖分析
- TypedDict 类型安全

### 4. 向后兼容
- 兼容旧 Toolkit
- 兼容旧 AgentState
- 渐进式迁移

### 5. 高性能
- 单例模式
- 5分钟缓存 TTL
- 按需加载

---

## 📖 快速开始

### 1. 初始化数据库

```bash
.\env\Scripts\activate
python scripts/setup/init_plugin_architecture_db.py
```

### 2. 使用 BindingManager

```python
from core.config import BindingManager

bm = BindingManager()

# 获取 Agent 的工具
tools = bm.get_tools_for_agent("market_analyst")

# 绑定工具到 Agent
bm.bind_tool("market_analyst", "get_yfinance_data", priority=1)
```

### 3. 使用 StateRegistry

```python
from core.state import StateRegistry

registry = StateRegistry()

# 构建状态 Schema
schema = registry.get_or_build(
    workflow_id="position_analysis",
    agent_ids=["pa_technical", "pa_fundamental", "pa_risk", "pa_advisor"]
)

# 获取状态类
state_class = registry.get_state_class("position_analysis")
```

详细示例请参考 [使用示例](./08-usage-examples.md)。

---

## 🔧 技术栈

- **Python 3.10+**
- **LangGraph** - 多智能体工作流框架
- **LangChain** - LLM 应用框架
- **MongoDB** - 配置存储
- **Pydantic** - 数据验证

---

## 📊 统计数据

### 代码量
- **新增文件**: 9个
- **新增代码**: 1,237行
- **修改文件**: 2个

### 组件数量
- **核心组件**: 5个
- **数据库集合**: 6个
- **内置 Agent**: 20+个

---

## 🤝 贡献指南

1. 阅读设计文档
2. 遵循现有代码风格
3. 添加单元测试
4. 更新文档

---

## 📝 许可证

MIT License

---

## 📞 联系方式

如有问题，请查看文档或提交 Issue。

---

**最后更新**: 2025-12-13  
**下一步**: 开始阶段2 - 工具层迁移

