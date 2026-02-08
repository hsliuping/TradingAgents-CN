# TradingAgents-CN Pro v2.3 设计文档

## 📋 版本概述

**版本号**: v2.3  
**计划发布**: TBD  
**类型**: 功能增强版本（智能化升级）  
**状态**: 需求设计阶段  
**前置版本**: v2.0（工作流引擎）、v2.1（上下文配置 + 可信度提升）

---

## 🎯 核心目标

v2.3 版本聚焦两个核心方向：

### 方向 A：报告解读系统
解决散户"看不懂分析报告"的痛点，提供通俗化解读和多报告对比分析能力。

### 方向 B：智能助手（Agent 自主编排模式）
解决"固定工作流无法应对临时、探索性需求"的问题，通过 Function Calling 让 Agent 自主选择工具、编排分析步骤。

---

## 📚 设计文档索引

### 1. [报告解读系统设计](./report-interpretation-system.md)

**核心功能**：
- 单报告通俗化解读（大白话解释专业分析）
- 纵向对比（同一股票不同时期的报告对比）
- 横向对比（同行业多只股票的对比分析）
- 组合概览（自选股整体情况摘要）

### 2. [智能助手设计（Agent 自主编排）](./intelligent-assistant-design.md)

**核心功能**：
- 事件驱动的临时分析（热点事件对股票的影响）
- Function Calling 架构（Agent 自主选择工具）
- 与现有工作流引擎的协作（轻问题秒回，重分析转工作流）

### 3. [双方向架构设计](./two-direction-architecture.md)

**核心内容**：
- 方向 A（流程配置灵活化）与方向 B（Agent 自主编排）的互补关系
- 共享工具层设计
- 两种模式的适用场景划分
- 架构全景图

### 4. [工具描述增强规范](./tool-description-enhancement.md)

**核心内容**：
- 现有 `tool_configs` 结构分析
- Function Calling 所需的工具描述字段规范
- 迁移计划（从简单描述到 Function Calling 就绪）

### 5. [Skill 机制评估（v2.3 更新）](./skill-mechanism-reassessment.md)

**核心结论**：
- v2.1 评估结论（核心分析流程不需要 Agent Skill）依然成立
- v2.3 新场景（智能助手）需要 Function Calling，但不需要 Skill 打包机制
- Skill 开放平台留待用户量上来后再考虑

---

## 🗓️ 实施路线图

### 阶段 1：单报告通俗解读（2-3 周）
- [ ] 后端 `ReportInterpretationService`
- [ ] Prompt 模板设计（含合规约束）
- [ ] 前端报告详情页对话框
- [ ] 测试和调优

### 阶段 2：纵向对比（2-3 周）
- [ ] 历史报告检索和关键指标提取
- [ ] 对比分析 Prompt 模板
- [ ] 前端对比展示 UI
- [ ] 测试和调优

### 阶段 3：横向对比（2-3 周）
- [ ] 多股票报告聚合
- [ ] 多维度对比 Prompt 模板
- [ ] 前端对比分析页面
- [ ] 测试和调优

### 阶段 4：工具描述增强（1-2 周）
- [ ] 梳理现有工具列表
- [ ] 补全工具描述（when_to_use、参数、返回值、示例）
- [ ] 验证 Function Calling 可用性

### 阶段 5：智能助手 MVP（3-4 周）
- [ ] 后端 Agent 自主编排引擎
- [ ] 意图解析和工具路由
- [ ] 与现有工作流的桥接
- [ ] 前端对话入口
- [ ] 测试和调优

**预计总工期**: 10-15 周

---

## 🔗 相关文档

### 前置版本
- [v2.0 架构设计](../v2.0/01-architecture-overview.md)
- [v2.0 工作流引擎](../v2.0/03-workflow-engine.md)
- [v2.0 智能体系统](../v2.0/05-agent-system.md)
- [v2.1 工作流上下文配置](../v2.1/workflow-context-configuration.md)
- [v2.1 Agent Skill 评估](../v2.1/agent-skill-technology-assessment.md)

### v2.3 文档
- [报告解读系统设计](./report-interpretation-system.md)
- [智能助手设计](./intelligent-assistant-design.md)
- [双方向架构设计](./two-direction-architecture.md)
- [工具描述增强规范](./tool-description-enhancement.md)
- [Skill 机制评估](./skill-mechanism-reassessment.md)

---

**创建日期**: 2026-02-07  
**最后更新**: 2026-02-07  
**维护者**: TradingAgents-CN Pro Team

