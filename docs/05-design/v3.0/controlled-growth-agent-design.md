# TradingAgents-CN v3.0 受控成长 Agent 设计方案

## 📋 文档信息

| 项目 | 内容 |
|------|------|
| 版本 | v3.0 Design Draft |
| 状态 | 方案设计中 |
| 日期 | 2026-03-15 |
| 目标 | 在不重构 v3.0 核心执行层的前提下，优先在流程执行场景中引入“受控成长”的沉淀、复盘和建议式演进能力 |
| 对齐文档 | [智能助手](intelligent-assistant.md)、[助手研究工作台设计](assistant-research-workbench-design.md)、[流程 Agent 能力审计](agent-capability-audit.md)、[v4.0 产品定位与成长边界](../v4.0/product-positioning-and-growth-boundary.md)、[v4.0 自定义 Agent 团队设想](../v4.0/custom-agent-team-role-memory-collaboration.md) |

---

## 1. 设计背景

### 1.1 当前问题

TradingAgents-CN v3.0 已经具备：

- 工作流执行与异步任务体系
- 工作流生成与优化会话
- 分析报告落库与结果持久化
- 交易复盘、持仓分析、投资计划等流程型能力
- 规划分析与工作流生成会话
- 报告、股票关注列表、持仓、复盘、投资计划等业务能力

但这些能力仍主要停留在“这次流程跑完就结束”或“人工再次翻阅可用”的层面，尚未形成真正的成长闭环：

1. 一次流程执行完成后，系统不会自动提取“这次流程里哪些结论值得沉淀”。
2. 一次成功分析或一次失败复盘不会自动转化为后续可复用的模式。
3. 系统没有明确区分“本次任务中间结果”“流程级可复用结论”“长期规则建议”。
4. 研究过程中的经验教训缺少审核流，容易出现错误沉淀或记忆污染。
5. 系统虽有多 Agent / 多工作流能力，但没有“流程内成长建议层”来推动后续优化。

### 1.2 为什么 MVP 不应先放助手页

虽然智能助手已经具备线程、摘要、历史会话等能力，但如果把“成长”先落到助手页，会带来额外复杂度：

1. 助手是开放式场景，输入和目标都不稳定。
2. 助手页天然会混入闲聊、追问、跳题、跨主题引用，记忆边界更难控。
3. 助手 UI 需要额外设计沉淀区、证据入口、撤回入口，前端复杂度高。
4. 助手里很多功能是复合型的，不利于第一阶段验证“哪些成长真的有价值”。

因此，v3.0 第一阶段应坚持：

**先在流程里做受控成长，再决定是否把同样的能力外扩到助手页。**

### 1.3 为什么不能直接照搬开放式自成长

v4.0 文档已经明确，TradingAgents 的方向不是“无边界自成长 Agent 平台”，而是“受控成长的长期投研陪伴系统”。

因此，本设计必须遵守以下边界：

- 不让 Agent 自动扩权
- 不让 Agent 自动改交易规则
- 不让 Agent 自动形成买卖决策
- 不让未经确认的记忆直接变成长期事实
- 不让系统在后台悄悄改工作流、提示词或执行策略

本阶段目标不是“让 Agent 自我进化成更会交易的系统”，而是：

**让系统逐步形成更好的跟踪、复盘、提示和研究承接能力。**

---

## 2. 目标与非目标

### 2.1 核心目标

在 v3.0 内引入一个可上线、可审计、可回滚的“受控成长层”，支持：

1. 流程执行结束后自动提取候选沉淀。
2. 将记忆按边界分类存储，而不是混成聊天记录。
3. 后续同类流程、同一对象流程中按对象与流程类型召回相关记忆。
4. 对高价值结论形成“沉淀建议”，等待用户确认。
5. 基于复盘结果或多次执行结果形成“流程优化建议”，而不是直接改系统。

### 2.2 MVP 范围收缩

v3.0 第一阶段明确只做以下场景：

1. 工作流执行完成后的结果沉淀。
2. 交易复盘完成后的经验沉淀。
3. 工作流优化会话的建议式触发。

第一阶段不把智能助手页面作为主入口，只保留未来复用可能。

### 2.3 非目标

本设计明确不包含：

- 自动生成并上线新 Agent
- 自动修改生产工作流定义
- 自动生成交易指令或仓位建议
- 自动将一次分析结论升级为系统级规则
- 构建通用 Agent 开发平台
- 引入高耦合的外部记忆系统替换现有 Mongo 主存储

---

## 3. 设计原则

### 3.1 受控优先于聪明

宁可少记，也不要错记。宁可多一步确认，也不要把临时判断误沉淀为长期认知。

### 3.2 在现有底座上演进

优先复用现有能力：

- `task_analysis_service` / 统一任务执行体系
- `/api/v1/workflow/execute` 与 `/api/workflows/{workflow_id}/execute`
- 工作流执行结果与报告落库能力
- `workflow_generation_sessions`
- 交易复盘与持仓分析结果
- `workflow_generation_sessions`
- 报告、复盘、持仓、计划等业务对象

### 3.3 成长对象要清晰

系统成长的不是“人格”，而是以下几类资产：

- 用户偏好
- 跟踪对象上下文
- 研究结论与假设
- 复盘经验教训
- 可复用的分析模式

### 3.4 建议式升级而非自动升级

系统可以产出：

- 建议沉淀什么
- 建议后续关注什么
- 建议优化哪个工作流或提示词

但不能直接在未经确认的情况下生效。

### 3.5 先审计基类，再决定是否扩基类

流程内的 Agent 当前已经不是无序状态，而是具备较完整的公共底座：

- `BaseAgent` 提供 LLM 注入、工具加载、提示词初始化、标准化工具调用循环。
- `AgentMetadata` 已声明输入输出、默认工具、`output_field`、`reads_from`、执行顺序等信息。
- `AgentFactory` 已负责注册类创建、数据库驱动 `UniversalAgent` 降级、记忆实例注入。
- `WorkflowBuilder` 已负责节点级工具解析、LLM 选择、Agent 创建与包装。

因此，第一阶段不建议直接“重设基类”。

更合理的顺序是：

1. 先做一次 Agent 基类与元数据能力审计。
2. 明确哪些能力已经存在于 `BaseAgent` / `AgentMetadata` / `AgentFactory`。
3. 识别真正缺失的“成长相关能力声明”和“成长钩子”。
4. 只在基类与元数据层补最小新增字段和钩子，避免大范围破坏现有流程。

换句话说，本项目更适合：

**在现有 Agent 基类之上增加“能力画像层”和“成长钩子层”，而不是推倒重来重设基类。**

---

## 3.6 Agent 能力审计建议

在进入受控成长开发前，建议先输出一份 Agent Capability Matrix，至少覆盖以下维度：

1. `agent_id`
2. Agent 类来源：内建类 / `UniversalAgent` / 遗留适配器
3. 输入依赖：读取哪些状态字段、是否依赖上游报告
4. 输出契约：写入哪个 `output_field`，输出是否稳定结构化
5. 工具能力：默认工具、动态绑定工具、最大工具调用次数
6. 提示词能力：是否支持节点级 / 工作流级模板覆盖
7. 执行模式：纯 LLM / 工具调用 / 组合推理
8. 可沉淀性：哪些输出字段适合进入成长抽取
9. 审核级别：该 Agent 的输出适合自动 pending，还是必须人工确认
10. 优化方向：更适合沉淀记忆、生成模式，还是生成工作流优化建议

建议把审计结果按三类 Agent 分层看：

- 分析师：适合沉淀对象跟踪记忆和检查项
- 复盘/计划类 Agent：适合沉淀经验模式和偏差规则
- 管理者 / 汇总类 Agent：适合生成流程优化建议，而不是直接形成长期事实

---

## 3.7 基类最小改造原则

如果完成能力审计后确认需要扩展基类，建议只做以下最小改动：

### A. 扩展 `AgentMetadata`，不要先重写 `BaseAgent`

优先新增“声明型字段”，例如：

- `growth_role`: `extractor` / `reviewer` / `optimizer` / `none`
- `growth_outputs`: 哪些字段允许进入成长抽取
- `memory_scope_hint`: `object_tracking` / `pattern` / `research_asset`
- `review_level`: `auto_pending` / `manual_required`

这类改动风险低，且对 `UniversalAgent` 也兼容。

### B. 在 `BaseAgent` 中只增加钩子，不改核心执行职责

适合增加的方法：

- `describe_capabilities()`
- `get_growth_artifacts(result, state)`
- `get_review_requirement()`

不建议一开始改动：

- `execute()` 主签名
- 工具调用主循环
- LLM 初始化主路径
- Factory 创建主路径

### C. 将成长逻辑放在 Agent 外层编排

成长提取更适合放在流程结果后处理层，而不是每个 Agent 自己决定是否落库。

原因：

- 降低 Agent 业务复杂度
- 便于统一审计与回滚
- 避免每个 Agent 重复实现成长逻辑

因此，Agent 更适合作为“能力声明源”和“结果产出源”，真正的成长抽取仍应由独立的 `Memory Extractor` / `Growth Suggestion Generator` 完成。

---

## 4. 总体架构

### 4.1 分层架构

```text
┌─────────────────────────────────────────────────────────────┐
│ Layer 1: 现有流程与执行层                                    │
│ - Workflow Execute API                                       │
│ - Unified Task Engine                                        │
│ - 分析报告 / 复盘报告 / 计划评估结果                          │
│ - WorkflowGenerationService                                 │
│ - Tool / Workflow / Report / Review / Portfolio             │
├─────────────────────────────────────────────────────────────┤
│ Layer 2: 受控成长层（本次新增）                               │
│ - Memory Extractor                                          │
│ - Memory Classifier                                         │
│ - Memory Retrieval Router                                   │
│ - Growth Suggestion Generator                               │
│ - Review & Approval Flow                                    │
├─────────────────────────────────────────────────────────────┤
│ Layer 3: 成长资产层                                           │
│ - 用户偏好记忆                                                │
│ - 对象跟踪记忆                                                │
│ - 研究结论/假设卡片                                           │
│ - 复盘经验卡片                                                │
│ - 模式库与改进建议                                            │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 核心闭环

```text
工作流/分析/复盘完成
    ↓
抽取候选沉淀
    ↓
分类到不同边界
    ↓
写入候选区（pending）
    ↓
用户确认 / 系统审核
    ↓
进入正式长期资产
    ↓
后续同类流程按对象召回
    ↓
生成新的沉淀与改进建议
```

---

## 5. 成长边界模型

### 5.1 四层记忆边界

参考 v4.0 设想，v3.0 先落四层：

#### A. 当前任务记忆

用途：仅服务当前会话或当前分析任务。

示例：

- 当前用户提问
- 本次工具结果
- 当前推理中间结论

特点：

- 生命周期短
- 不进入长期记忆

#### B. 流程 / 对象跟踪记忆

用途：围绕单个标的、行业、主题或固定流程形成连续上下文。

示例：

- 宁德时代最近三次关注点
- 用户对银行板块的主要担忧
- 某个主题下待验证的问题列表

特点：

- 按 object 或 workflow 组织
- 可被后续流程召回

#### C. 用户偏好与行为记忆

用途：记录用户的长期偏好，而不是单次情绪。

示例：

- 偏好看估值和风险而非短线题材
- 更关注 A 股与港股
- 习惯先看复盘再做计划

特点：

- 必须有跨会话重复证据
- 不应因一次发言立即写死

#### D. 研究资产与模式记忆

用途：沉淀高价值、可复用的研究结论或方法模式。

示例：

- 某类复盘常见失误模式
- 某行业跟踪模板
- 某类提示词或工作流优化建议

特点：

- 价值高
- 风险也高
- 必须先进入审核态

### 5.2 明确禁止沉淀的内容

以下内容只允许停留在临时上下文：

- 未验证的事实断言
- 模型主观推测
- 明显带时效性的短期新闻判断
- 与金融研究无关的闲聊偏好
- 直接买卖倾向或具体交易动作建议

---

## 6. 现有 3.0 能力复用点

### 6.1 工作流执行结果

当前已有工作流执行入口和统一任务体系，可直接作为成长资产挂载的主入口：

- task 负责承接一次具体执行
- workflow_result 负责承接流程输出
- analysis_report / review_report 负责承接持久化结论

新增受控成长层后，thread 将成为：

- 记忆抽取源
- 对象记忆归属点
- 流程优化建议入口

### 6.1.1 基类与工厂层的现实基础

当前流程 Agent 体系已经具备以下基础：

- [core/agents/base.py](core/agents/base.py) 负责公共初始化、工具加载、提示词准备、标准化工具调用循环。
- [core/agents/config.py](core/agents/config.py) 已有 `AgentMetadata`，声明 `output_field`、`reads_from`、`default_tools`、`execution_order` 等关键信息。
- [core/agents/factory.py](core/agents/factory.py) 已统一处理内建 Agent、数据库驱动 `UniversalAgent`、记忆注入与初始化。
- [core/agents/universal.py](core/agents/universal.py) 已支持数据库配置驱动的通用 Agent。
- [core/workflow/builder.py](core/workflow/builder.py) 已负责 workflow/node 级工具解析、LLM 选择和 Agent 创建。

这意味着：

- 受控成长第一阶段的前置工作，不是重新发明 Agent 框架。
- 真正要补的是“能力画像层”和“成长抽取接口约定”。
- 这层工作更适合做成轻量增量，而不是架构翻修。

### 6.2 工作流生成会话

`workflow_generation_sessions` 已经具备：

- 多轮沟通
- 蓝图生成
- 创建报告
- 优化反馈

这一能力可以直接承接“成长建议”的另一条线：

- 用户在复盘或长期使用中提出的固定需求
- 系统识别出的高频工作流缺口
- 经确认后生成工作流优化建议会话

### 6.3 复盘与计划类结果

交易复盘、计划评估、持仓分析这类结果天然比开放式对话更结构化，更适合作为第一阶段成长抽取源：

- 输入边界清晰
- 输出字段相对稳定
- 失败与偏差更容易结构化归因

---

## 7. 数据模型设计

### 7.1 新增集合概览

建议新增以下集合：

1. `agent_memory_items`
2. `agent_memory_links`
3. `agent_growth_suggestions`
4. `agent_growth_events`

### 7.2 agent_memory_items

用途：统一存储已确认和待确认的记忆条目。

建议字段：

```json
{
  "memory_id": "mem_xxx",
  "user_id": "u_xxx",
  "scope": "user_preference",
  "status": "pending",
    "source_type": "workflow_execution",
    "source_id": "task_xxx",
  "object_type": "stock",
  "object_key": "300750",
    "title": "宁德时代分析流程中反复出现现金流与估值核验项",
    "content": "最近 4 次关于宁德时代的分析流程都把现金流质量与估值区间作为关键校验项。",
  "structured_payload": {
        "memory_type": "workflow_focus",
        "value": ["cashflow", "valuation"],
    "evidence_count": 4
  },
  "confidence": 0.86,
  "evidence_refs": [
        {"type": "analysis_report", "id": "report_1"},
        {"type": "analysis_report", "id": "report_2"}
  ],
  "expires_at": null,
  "confirmed_by": null,
  "confirmed_at": null,
  "created_at": "2026-03-15T10:00:00Z",
  "updated_at": "2026-03-15T10:00:00Z"
}
```

字段说明：

- `scope`: `task_temp` / `object_tracking` / `user_preference` / `research_asset` / `pattern`
- `status`: `pending` / `approved` / `rejected` / `expired`
- `object_type`: `stock` / `sector` / `theme` / `workflow` / `user`
- `structured_payload`: 用于后续精确召回和 UI 展示

索引建议：

- `(user_id, scope, status, updated_at desc)`
- `(user_id, object_type, object_key, status, updated_at desc)`
- `(source_type, source_id)`

### 7.3 agent_memory_links

用途：建立记忆与业务对象、会话、报告之间的关联。

建议字段：

```json
{
  "memory_id": "mem_xxx",
  "user_id": "u_xxx",
  "link_type": "report",
  "link_id": "report_xxx",
  "meta": {
    "symbol": "300750"
  },
  "created_at": "2026-03-15T10:00:00Z"
}
```

### 7.4 agent_growth_suggestions

用途：记录系统产出的“成长建议”，但不直接生效。

建议字段：

```json
{
  "suggestion_id": "gs_xxx",
  "user_id": "u_xxx",
  "suggestion_type": "workflow_optimization",
  "status": "pending",
  "title": "建议为交易复盘增加纪律偏差检查步骤",
  "summary": "最近 6 次复盘里有 4 次提到临盘加仓与计划偏离，建议将纪律偏差检查前置。",
  "source_refs": [
    {"type": "review", "id": "rv_1"},
    {"type": "review", "id": "rv_2"}
  ],
  "suggested_action": {
    "target": "workflow_generation",
    "mode": "start_session",
    "payload": {
      "description": "优化交易复盘工作流，新增纪律偏差检查节点"
    }
  },
  "confidence": 0.78,
  "created_at": "2026-03-15T10:00:00Z",
  "updated_at": "2026-03-15T10:00:00Z"
}
```

### 7.5 agent_growth_events

用途：记录成长相关操作日志，保证可追踪和可回滚。

示例事件：

- 生成候选记忆
- 用户批准记忆
- 用户拒绝记忆
- 生成成长建议
- 触发优化会话

---

## 8. 核心模块设计

### 8.1 Memory Extractor

职责：从流程结果、报告、复盘、计划中抽取候选记忆。

触发时机：

- 工作流执行完成后
- 报告生成完成后
- 复盘完成后

输入：

- workflow_result / creation_report / review_result
- 关联报告/复盘/计划对象

输出：

- 候选记忆列表
- 每条候选记忆的 scope、confidence、evidence_refs

### 8.2 Memory Classifier

职责：决定候选记忆属于哪一层边界。

分类原则：

- 单次事实提醒，不入长期记忆
- 多次重复出现的偏好，可入 `user_preference`
- 与单个标的强相关的连续跟踪，入 `object_tracking`
- 可复用的方法、模式、经验，入 `pattern` 或 `research_asset`

### 8.3 Memory Retrieval Router

职责：在新流程执行前决定注入哪些记忆。

优先级建议：

1. 当前对象的流程跟踪记忆
2. 当前 workflow 的已确认模式
3. 相关研究资产摘要
4. 相关模式记忆

注入上限：

- 严格控制 token
- 优先结构化摘要，不直接注入长文本

### 8.4 Growth Suggestion Generator

职责：基于长期使用中的重复问题生成“改进建议”。

建议类型：

- `memory_promotion`: 某条候选记忆值得确认
- `research_asset_promotion`: 某主题总结值得沉淀成研究卡片
- `workflow_optimization`: 某工作流存在稳定缺口
- `prompt_optimization`: 某类回复经常缺少特定维度
- `watch_rule_suggestion`: 某对象适合增加持续跟踪项

### 8.5 Review & Approval Flow

职责：拦截高风险沉淀，确保成长受控。

审批策略：

- 用户偏好类：可半自动，低风险
- 对象跟踪类：可自动进入 pending，再由用户确认
- 模式类 / 工作流优化类：必须明确确认
- 任何涉及执行权、规则权、交易判断的内容：禁止自动生效

---

## 9. 关键流程设计

### 9.1 流程后记忆沉淀流程

```text
用户完成一次工作流执行
    ↓
系统获取 workflow_result / report
    ↓
Memory Extractor 抽取候选记忆
    ↓
Memory Classifier 分类
    ↓
写入 agent_memory_items(status=pending)
    ↓
前端在流程结果页显示“建议沉淀”列表
    ↓
用户批准 / 拒绝 / 稍后处理
```

### 9.2 复盘后成长建议流程

```text
用户完成交易复盘
    ↓
系统提取事实、偏差、原因、改进点
    ↓
若多次出现相同偏差模式
    ↓
生成 pattern 类候选记忆
    ↓
同步生成 growth suggestion
    ↓
用户可选择“加入长期纪律提醒”或“用于优化复盘流程”
```

### 9.3 流程召回流程

```text
用户再次执行某个 workflow 或同对象流程
    ↓
识别当前对象（股票/行业/计划/复盘）与 workflow_id
    ↓
查询 approved 的 object_tracking / workflow_pattern 记忆
    ↓
查询相关研究资产摘要
    ↓
裁剪后注入流程上下文
    ↓
生成执行上下文或优化提示
```

### 9.4 工作流改进承接流程

```text
系统发现某类任务反复出现同一能力缺口
    ↓
生成 workflow_optimization 建议
    ↓
用户确认
    ↓
调用 WorkflowGenerationService.start_session()
    ↓
进入现有工作流优化会话
```

---

## 10. API 设计

### 10.1 记忆接口

建议新增：

- `GET /api/workflow-growth/memories`
- `GET /api/workflow-growth/memories/pending`
- `POST /api/workflow-growth/memories/{memory_id}/approve`
- `POST /api/workflow-growth/memories/{memory_id}/reject`
- `POST /api/workflow-growth/tasks/{task_id}/extract-memories`
- `POST /api/workflow-growth/reviews/{review_id}/extract-memories`

### 10.2 成长建议接口

建议新增：

- `GET /api/workflow-growth/suggestions`
- `POST /api/workflow-growth/suggestions/{suggestion_id}/accept`
- `POST /api/workflow-growth/suggestions/{suggestion_id}/dismiss`

### 10.3 返回结构建议

```json
{
  "items": [
    {
      "id": "mem_xxx",
      "scope": "object_tracking",
      "status": "pending",
      "title": "宁德时代主题下待验证的问题",
      "summary": "系统建议把当前主题中的 3 个待验证问题沉淀为后续跟踪项",
      "confidence": 0.82,
      "created_at": "2026-03-15T10:00:00Z"
    }
  ],
  "total": 1
}
```

---

## 11. 前端交互设计

### 11.1 流程结果页新增模块

在现有流程执行结果页、复盘结果页或工作流详情页中新增：

1. `建议沉淀`
2. `长期记忆`
3. `成长建议`

### 11.2 交互原则

- 不打断主对话
- 优先做成侧栏或卡片区
- 所有自动沉淀都应可见、可撤回
- 所有建议都应提供来源证据入口

### 11.3 推荐交互形态

#### A. 流程结果页的轻提醒

示例：

- “本次流程提炼出 2 条可沉淀内容”
- “其中 1 条可能适合作为该工作流的长期检查项”

#### B. 工作流详情页的长期资产面板

展示：

- 已确认流程跟踪项
- 待处理沉淀建议
- 相关研究卡片 / 模式卡片

#### C. 复盘页的经验教训卡片

展示：

- 本次复盘新增经验
- 历史高频偏差模式
- 可升级为纪律提醒的建议

---

## 12. 实施分期

### 12.1 Phase 1: MVP（5-8 个工作日）

目标：让系统“会沉淀、能确认、可召回”。

范围：

1. 工作流执行完成后抽取候选记忆
2. 交易复盘完成后抽取候选记忆
2. 新增 `agent_memory_items`
3. 支持 pending/approved/rejected 状态
4. 在流程结果页展示待确认记忆
5. 对 approved 的对象记忆与 workflow_pattern 进行流程注入

不做：

- 助手页接入
- 模式库全量管理
- 自动工作流改写

### 12.2 Phase 2: 增强版（2-3 周）

目标：从“记忆”进化到“成长建议”。

范围：

1. 复盘后提取经验模式
2. 新增 `agent_growth_suggestions`
3. 支持从建议发起工作流优化会话
4. 支持研究资产卡片化沉淀

### 12.3 Phase 3: 角色化成长（3-5 周）

目标：和 v4.0 的角色化 Agent 团队逐步对齐。

范围：

1. 为不同角色定义记忆边界
2. 不同角色只看自己职责相关记忆
3. 形成“跟踪-分析-计划-复盘-沉淀”多角色成长闭环

---

## 13. 风险与控制措施

### 13.1 错误沉淀

风险：把一次错误分析当成长期事实。

控制：

- 高风险条目必须 pending
- 每条记忆必须保留 evidence_refs
- 过期记忆支持失效与撤回

### 13.2 记忆污染

风险：主题记忆、用户偏好、短期情绪混在一起。

控制：

- 强制 scope 分类
- 严格区分 source_type 和 object_key
- 用户偏好类要求重复证据阈值

### 13.3 召回过量

风险：上下文注入过多，反而拉低回复质量。

控制：

- 只注入摘要，不注入大段原文
- 设定固定 token 预算
- 召回优先对象相关记忆

### 13.4 越权成长

风险：系统从“辅助成长”滑向“自动决策”。

控制：

- 不允许成长层直接写交易计划执行规则
- 不允许成长层自动生效 workflow 变更
- 不允许成长层生成买卖执行建议

---

## 14. 与 v4.0 的衔接关系

本方案是 v4.0 的前置工程，而不是 v4.0 的替代品。

它主要解决三件事：

1. 先把“成长资产”这件事落到生产系统里。
2. 先验证哪些记忆和建议对用户真的有价值。
3. 为后续“自定义 Agent 团队 + 角色化记忆边界”打底。

如果 Phase 1 与 Phase 2 跑通，v4.0 就可以在此基础上继续演进：

- 角色化记忆视图
- 角色职责驱动的成长策略
- 更丰富的研究资产编排
- 审核式能力升级

---

## 15. 推荐实施顺序

建议按以下顺序落地：

1. 在工作流执行结果中落地候选记忆抽取
2. 接入 pending/approve/reject 审核流
3. 为流程执行注入 approved 记忆
4. 在复盘场景中增加经验模式抽取
5. 再接工作流优化建议

这个顺序的原因是：

- 风险最小
- 价值最直接
- 复用现有 3.0 基础最多
- 最容易验证真实用户收益

---

## 16. 结论

在 TradingAgents-CN v3.0 中实现“自成长 Agent”是可行的，但正确做法不是做开放式自我进化，而是做一层可审计、可确认、可回滚的“受控成长层”。

v3.0 现有的工作流执行、报告落库、复盘结果、工作流生成等能力，已经足够支撑第一阶段落地。真正需要新增的，不是另一个巨大的 Agent 平台，而是：

- 候选记忆抽取能力
- 记忆边界与存储模型
- 成长建议与审核流
- 受控召回机制

只要把这四件事做好，系统就会开始从“会回答问题”转向“会积累、会提醒、会辅助改进”，并且仍然保持金融场景需要的可信边界。