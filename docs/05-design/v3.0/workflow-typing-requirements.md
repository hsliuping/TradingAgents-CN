# 工作流类型化改造需求文档

| 字段 | 内容 |
|------|------|
| 版本 | v3.0.0 |
| 状态 | 待实现 |
| 优先级 | P0 |
| 创建日期 | 2026-07-11 |
| 关联设计 | [工作流类型化改造技术设计](./workflow-typing-technical-design.md) |

## 一、背景

### 1.1 现状问题

当前 v3.0 的工作流（自定义分析流程）存在三个核心问题：

**问题 1：自定义流程无类型归属**

用户通过流程中心创建的自定义工作流没有明确的"使用场景"分类。一个工作流可以被任何场景调用，但没有清晰的入口和输出归属。这导致：

- 用户创建了一堆流程，不知道哪个流程在哪里能用
- 单股分析、持仓分析、操作复盘等场景都共用一个"全局默认流程"，混乱
- 流程的输出结果没有明确的落地位置

**问题 2：单股研究工作流选择器失效（Bug）**

[SingleAnalysis.vue](file:///c:/TradingAgentsCN/frontend/src/views/Analysis/SingleAnalysis.vue) 第 940 行定义了 `selectedWorkflowId` 状态变量，第 2904 行加载了工作流模板列表，但 `submitAnalysis()`（第 1303 行）构造请求时**不传递 `workflow_id`**。导致用户选择的工作流被忽略，后端总是使用全局默认工作流。

**问题 3：AI 生成的工作流不支持条件分支（Bug）**

[workflow_spec.py](file:///c:/TradingAgentsCN/core/workflow/generator/workflow_spec.py) 的 `PlannedEdge` 模型缺少 `type` 和 `condition` 字段，`_blueprint_to_workflow_dict()` 将所有边硬编码为 `"normal"` 类型。导致 AI 创建的工作流中条件分支不工作（两条路径都会执行，而非二选一）。

### 1.2 后端已完成类型化

后端已基本完成流程类型化改造：

- [default_workflow_provider.py](file:///c:/TradingAgentsCN/core/workflow/default_workflow_provider.py) 已实现 `WORKFLOW_TYPE_DEFAULTS`、`infer_workflow_type()`、`get_active_workflow_id(workflow_type)`、`set_active_workflow_id(workflow_id, workflow_name, workflow_type)` 等完整类型化方法
- [unified_analysis_engine.py](file:///c:/TradingAgentsCN/app/services/unified_analysis_engine.py) 已实现 `_workflow_type_for_task()` 将任务类型映射为 workflow_type
- [workflow_api.py](file:///c:/TradingAgentsCN/core/api/workflow_api.py) 创建/更新时已写入 `workflow_type` 顶层字段并创建索引
- [workflows.py](file:///c:/TradingAgentsCN/app/routers/workflows.py) 的 `WorkflowCreate`/`WorkflowUpdate` 已支持 `workflow_type` 字段

前端未跟上，造成"半成品"状态。

## 二、目标

1. **让自定义流程有明确的类型归属**：创建时选择类型，按类型在对应场景使用，按类型在流程管理页分组展示
2. **修复单股研究工作流选择器 Bug**：用户选择的工作流能真正被使用
3. **修复 AI 生成工作流条件分支 Bug**：AI 创建的流程支持条件分支
4. **让产品闭环**：用户创建自定义流程后，知道在哪里用、结果在哪里看

## 三、流程类型定义

### 3.1 类型清单

| 类型 ID | 类型名称 | 使用场景 | 入口 | 输出 |
|--------|---------|---------|------|------|
| `stock_analysis` | 单股研究流程 | 分析单只股票 | 单股研究页面 | 研究报告列表 |
| `etf_analysis` | ETF 分析流程 | 分析 ETF 基金 | 单股研究页面（ETF） | 研究报告列表 |
| `position_analysis` | 持仓分析流程 | 分析持仓股票健康度 | 持仓分析页面 | 持仓分析报告 |
| `trade_review` | 操作复盘流程 | 复盘交易操作 | 操作复盘页面 | 复盘报告 |
| `portfolio_health` | 组合健康度流程 | 组合整体健康度诊断 | 持仓分析页面 | 持仓分析报告 |
| `general` | 通用研究流程 | 自由研究探索 | 流程中心直接执行 | 独立报告 |

### 3.2 类型与任务映射

| 后端任务类型 (AnalysisTaskType) | workflow_type |
|-------------------------------|---------------|
| STOCK_ANALYSIS | `stock_analysis` |
| ETF_ANALYSIS | `etf_analysis` |
| POSITION_ANALYSIS | `position_analysis` |
| TRADE_REVIEW | `trade_review` |
| PORTFOLIO_HEALTH | `portfolio_health` |
| -（无对应任务类型） | `general` |

## 四、功能需求

### 4.1 创建流程时选择类型（P0）

**需求**：用户通过 AI 创建或手动创建工作流时，第一步必须选择流程类型。

**交互**：
- AI 创建路径（WorkflowGeneration.vue）：在需求描述之前，增加类型选择步骤
- 手动创建路径（Workflow/index.vue 的创建对话框）：在输入名称之前，增加类型选择

**类型选择 UI**：
```
你要创建什么类型的分析流程？
○ 单股研究流程 - 用于分析单只股票，结果在"研究报告"中查看
○ ETF 分析流程 - 用于分析 ETF 基金
○ 持仓分析流程 - 用于分析持仓股票健康度
○ 操作复盘流程 - 用于复盘交易操作
○ 组合健康度流程 - 用于组合整体诊断
○ 通用研究流程 - 自由探索，结果在"流程中心"查看
```

**默认值**：单股研究流程（`stock_analysis`）

### 4.2 流程管理页按类型分组展示（P1）

**需求**：流程管理页面（Workflow/index.vue）按 `workflow_type` 分组展示用户创建的流程。

**展示结构**：
```
我的流程
├── 单股研究流程（3个）
│   ├── 巴菲特式分析 [默认]
│   ├── 成长股分析
│   └── 周期股分析
├── 持仓分析流程（1个）
│   └── 持仓健康度诊断 [默认]
├── 操作复盘流程（1个）
│   └── 交易决策回顾 [默认]
└── 通用研究流程（1个）
    └── 自由探索
```

**默认标记**：每个类型可以设置一个默认流程（已有后端支持），在 UI 上用 `[默认]` 标签标记。

### 4.3 单股研究支持流程选择（P0）

**需求**：单股研究页面提交分析时，将用户选择的 `workflow_id` 传递给后端。

**修复点**：
- [SingleAnalysis.vue](file:///c:/TradingAgentsCN/frontend/src/views/Analysis/SingleAnalysis.vue) 的 `submitAnalysis()` 在请求参数中传递 `workflow_id: selectedWorkflowId.value`
- 前端请求接口 [analysis.ts](file:///c:/TradingAgentsCN/frontend/src/api/analysis.ts) 已支持 `workflow_id` 字段，无需修改

**可选增强**（P2，本次不做）：在单股研究页面增加流程选择器 UI，让用户可见地选择流程。当前先修复传递缺陷，使用默认机制。

### 4.4 流程编辑器显示类型（P1）

**需求**：流程编辑器（Editor.vue）显示当前工作流的类型，并允许修改。

**展示位置**：编辑器顶部或属性面板，显示"流程类型：单股研究流程"，可点击修改。

### 4.5 AI 生成服务设置类型（P0）

**需求**：AI 生成工作流服务（workflow_generation_service.py）在创建工作流时写入 `workflow_type`。

**实现**：
- 从前端接收用户选择的类型
- 在 `_blueprint_to_workflow_dict()` 中设置 `workflow_type`
- 调用 `WorkflowAPI.create()` 时传递

### 4.6 数据模型和模板补全（P0）

**需求**：
- [models.py](file:///c:/TradingAgentsCN/core/workflow/models.py) 的 `WorkflowDefinition` 增加 `workflow_type: Optional[str] = None` 字段
- [v2_stock_analysis_workflow.py](file:///c:/TradingAgentsCN/tradingagents/workflows/v2_stock_analysis_workflow.py) 的 config 补充 `"workflow_type": "stock_analysis"`
- [v2_etf_analysis_workflow.py](file:///c:/TradingAgentsCN/tradingagents/workflows/v2_etf_analysis_workflow.py) 的 config 补充 `"workflow_type": "etf_analysis"`

### 4.7 AI 生成工作流支持条件分支（P0）

**需求**：AI 生成的工作流支持条件分支节点。

**修复点**：
- [workflow_spec.py](file:///c:/TradingAgentsCN/core/workflow/generator/workflow_spec.py) 的 `PlannedEdge` 增加 `type: Optional[str] = "normal"` 和 `condition: Optional[str] = None` 字段
- [workflow_generation_service.py](file:///c:/TradingAgentsCN/app/services/workflow_generation_service.py) 的 `_blueprint_to_workflow_dict()` 中传递 `type` 和 `condition` 字段
- AI 规划器的 System Prompt 中说明条件分支的用法

## 五、非功能需求

1. **向后兼容**：已有的无 `workflow_type` 的工作流，通过 `infer_workflow_type()` 自动推断类型
2. **数据迁移**：不需要数据迁移脚本，`infer_workflow_type()` 会自动处理历史数据
3. **性能**：不影响工作流执行性能

## 六、验收标准

### 6.1 P0 验收

- [ ] 用户通过 AI 创建工作流时，可以选择流程类型
- [ ] 用户通过手动创建工作流时，可以选择流程类型
- [ ] 创建的工作流在数据库中写入正确的 `workflow_type`
- [ ] 单股研究页面提交分析时，`workflow_id` 被正确传递给后端
- [ ] AI 生成的工作流支持条件分支节点（条件分支按预期二选一执行）
- [ ] `WorkflowDefinition` 模型包含 `workflow_type` 字段
- [ ] 系统模板 `v2_stock_analysis_workflow` 和 `v2_etf_analysis_workflow` 的 config 包含 `workflow_type`

### 6.2 P1 验收

- [ ] 流程管理页面按 `workflow_type` 分组展示
- [ ] 每个类型的默认流程有 `[默认]` 标记
- [ ] 流程编辑器显示当前工作流的类型

## 七、关联文档

- [工作流类型化改造技术设计](./workflow-typing-technical-design.md)
- [v4.0 功能取舍](file:///c:/TradingAgentsCN/docs/05-design/v4.0/v3-to-v4-feature-triage.md)
- [v3.x 发布计划](file:///c:/TradingAgentsCN/docs/05-design/v3.0/v3.x-release-plan.md)
