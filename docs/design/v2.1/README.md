# TradingAgents-CN Pro v2.1 设计文档

## 📋 版本概述

**版本号**: v2.1  
**计划发布**: TBD  
**类型**: 功能增强版本  
**状态**: 需求设计阶段

---

## 🎯 核心目标

v2.1 版本有两个核心目标：

1. **工作流上下文配置系统** - 解决 Agent 配置全局化的问题，支持同一 Agent 在不同工作流和节点中使用不同的配置
2. **分析可信度提升** - 解决 LLM 训练数据过时导致的分析不准确问题，确保分析只基于实时获取的数据

---

## 📚 需求文档

### 1. [工作流上下文配置系统](./workflow-context-configuration.md)

**核心功能**：

1. **统一使用 `agent_id`**：
   - 消除 `agent_name` 和 `agent_id` 的不一致
   - 所有集合统一使用 `agent_id` 作为主键

2. **工作流级别配置**：
   - 同一 Agent 在不同工作流中使用不同的工具
   - 同一 Agent 在不同工作流中使用不同的提示词
   - 同一 Agent 在不同工作流中使用不同的执行参数

3. **节点级别配置**：
   - 同一工作流中多次使用同一 Agent 时，每个节点可以有独立配置

4. **向后兼容**：
   - 现有全局配置继续有效
   - 逐步迁移到新配置系统

**涉及的数据库集合**：

- `tool_agent_bindings`（改进）
- `prompt_templates`（改进）
- `workflow_agent_bindings`（新增）
- `user_template_configs`（改进）

**涉及的代码模块**：

- `core/config/binding_manager.py`
- `core/workflow/builder.py`
- `tradingagents/utils/template_client.py`

### 2. [分析可信度提升方案](./analysis-credibility-enhancement.md)

**优先级**: 高
**状态**: 需求设计阶段

**核心问题**：LLM 训练数据是静态的，但股票分析需要基于最新实时数据。综合分析阶段可能混入 LLM 训练数据中的过时信息。

**解决方案**：

1. **两阶段分析**（推荐）：
   - 阶段1：事实提取 - 从子报告中提取结构化事实
   - 阶段2：基于事实推理 - 只使用提取的事实进行分析

2. **提示词约束**：
   - 添加严格的数据边界声明
   - 注入当前分析日期上下文

3. **结构化输出**：
   - 强制引用数据来源
   - 支持事后校验

**涉及的新增模块**：

- `core/agents/adapters/fact_extractor_v2.py` - 事实提取 Agent
- `core/validation/` - 校验模块

---

## 🗓️ 开发计划

### 阶段 1：需求设计（已完成）

- [x] 需求分析
- [x] 数据库设计
- [x] API 设计
- [x] 迁移方案设计

### 阶段 2：数据库迁移（1 周）

- [ ] 编写迁移脚本
- [ ] 测试迁移脚本
- [ ] 创建新索引
- [ ] 验证数据完整性

### 阶段 3：后端实现（2 周）

- [ ] 更新 `BindingManager`
- [ ] 更新 `GraphBuilder`
- [ ] 更新提示词查询逻辑
- [ ] 编写单元测试
- [ ] 集成测试

### 阶段 4：前端实现（2 周）

- [ ] 工作流编辑器支持节点配置
- [ ] Agent 配置页面支持多级配置
- [ ] 用户界面优化
- [ ] 前端测试

### 阶段 5：测试和文档（1 周）

- [ ] 集成测试
- [ ] 性能测试
- [ ] 文档编写
- [ ] 用户验收测试

**预计总工期**: 6 周

---

## 📊 架构改进

### 当前架构（v2.0）

```
Agent → 全局配置 → 全局工具绑定 → 全局提示词
```

**问题**：
- ❌ 无法根据工作流上下文调整 Agent 行为
- ❌ 同一 Agent 在所有场景中使用相同配置
- ❌ `agent_name` 和 `agent_id` 不一致

### 新架构（v2.1）

```
Agent → 工作流配置 → 节点配置 → 全局配置
         ↓              ↓           ↓
      工作流工具    节点工具    全局工具
      工作流提示词  节点提示词  全局提示词
      工作流参数    节点参数    全局参数
```

**优势**：
- ✅ 支持工作流级别配置
- ✅ 支持节点级别配置
- ✅ 保持向后兼容
- ✅ 统一使用 `agent_id`

---

## 🔄 配置优先级

### 工具绑定优先级

```
1. workflow_id + node_id + agent_id（节点级别）
2. workflow_id + agent_id（工作流级别）
3. agent_id（全局级别）
```

### 提示词优先级

```
1. user_id + workflow_id + node_id + agent_id（用户节点级别）
2. user_id + workflow_id + agent_id（用户工作流级别）
3. user_id + agent_id（用户全局级别）
4. workflow_id + node_id + agent_id（工作流节点级别）
5. workflow_id + agent_id（工作流级别）
6. agent_id（全局级别）
7. 代码默认值
```

---

## 📝 迁移指南

### 数据库迁移

**脚本**: `scripts/migration/migrate_to_v2.1.py`

**步骤**：

1. 备份数据库
2. 运行迁移脚本
3. 验证数据完整性
4. 创建新索引

**向后兼容**：

- `workflow_id = null` 表示全局配置
- `node_id = null` 表示工作流级别配置
- 现有数据自动视为全局配置

### 代码迁移

**影响的模块**：

1. `core/config/binding_manager.py`
   - 新增 `workflow_id` 和 `node_id` 参数
   - 实现优先级查询逻辑

2. `core/workflow/builder.py`
   - 传递 `workflow_id` 和 `node_id` 到 `BindingManager`
   - 加载工作流级别配置

3. `tradingagents/utils/template_client.py`
   - 新增 `get_agent_prompt_v2()` 函数
   - 支持工作流上下文

**向后兼容**：

- 保留旧函数签名
- 新增可选参数
- 默认行为不变

---

## 🧪 测试计划

### 单元测试

- [ ] `BindingManager.get_tools_for_agent()` 优先级测试
- [ ] `BindingManager.get_workflow_agent_config()` 测试
- [ ] `get_agent_prompt_v2()` 优先级测试
- [ ] 数据库迁移脚本测试

### 集成测试

- [ ] 工作流执行测试（不同配置）
- [ ] 多节点工作流测试
- [ ] 用户配置覆盖测试
- [ ] 向后兼容测试

### 性能测试

- [ ] 配置查询性能测试
- [ ] 缓存机制测试
- [ ] 数据库索引优化验证

---

## 📖 相关文档

### v2.0 文档

- [v2.0 架构设计](../v2.0/05-agent-system.md)
- [数据库设计](../v2.0/agents/04-database-design.md)
- [工作流系统](../v2.0/03-workflow-system.md)

### v2.1 文档

- [工作流上下文配置系统](./workflow-context-configuration.md)
- [分析可信度提升方案](./analysis-credibility-enhancement.md)
- [插件平台概念](./plugin-platform-concept.md)
- [架构图](./architecture-diagrams.md)

---

## 🤝 贡献指南

### 开发流程

1. 阅读需求文档
2. 创建功能分支
3. 实现功能
4. 编写测试
5. 提交 PR
6. Code Review
7. 合并到主分支

### 代码规范

- 遵循 PEP 8
- 添加类型注解
- 编写文档字符串
- 添加单元测试

---

**创建日期**: 2026-01-09
**最后更新**: 2026-01-12
**维护者**: TradingAgents-CN Pro Team

