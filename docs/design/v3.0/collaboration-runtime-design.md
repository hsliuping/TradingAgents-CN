# TradingAgents-CN v3.0 协作运行时设计

| 项目 | 内容 |
| ------ | ------ |
| 文档类型 | 设计文档 |
| 所属版本 | TradingAgents-CN Pro v3.0 |
| 当前状态 | Draft |
| 目标范围 | Assistant、Workflow、Agent 之间的最小协作运行时 |
| 不包含 | 知识库消息总线、完整 Artifact 平台、长期记忆平台 |

## 1. 背景

TradingAgents-CN 已经具备多处可复用但彼此分散的协作基础：

- Workflow 内部已经有状态字段和 Agent IO 描述能力
- Agent 元数据已经有 output_field、reads_from、depends_on 等定义
- 智能助手已经有线程、报告回写、工具执行上下文
- Agent 工坊已经开始生成 output_schema 和运行时配置
- internal_messages 已经承担内部研究消息与情报沉淀

当前问题不是系统完全没有协作能力，而是缺少一层统一的协作运行时契约，导致不同入口各自传参、各自回写、各自做来源追踪。

这会带来四类问题：

1. 来源不一致
2. 调用结果难统一复用
3. Assistant、Workflow、Agent 之间的调用边界不清晰
4. 后续想补 ArtifactRef、HandoffSpec 时缺少统一承载层

因此，v3.0 需要先补一层最小协作运行时，而不是直接引入更重的总线或知识协议。

## 2. 设计目标

### 2.1 要解决的问题

本设计只解决协作运行时问题，即：

- 谁发起了一次内部调用
- 调用了谁
- 带了什么输入与上下文
- 用什么执行策略运行
- 结果如何返回与记录
- 哪些结果对调用方可见

### 2.2 本期不解决的问题

本设计明确不解决以下问题：

- 不把 internal_messages 改造成运行时编排总线
- 不建设完整的通用 Artifact 仓库
- 不引入跨所有模块的事件总线
- 不在本期统一所有 Workflow 内部字段级编排语义
- 不处理长期记忆与知识检索的全局统一协议

## 3. 现状基础

当前代码中，已经存在可作为运行时底座的几个结构：

### 3.1 Workflow IO 与状态层

- core/state/models.py
- core/state/builder.py

这些文件已经定义了：

- StateFieldDefinition
- AgentIODefinition
- WorkflowStateSchema
- reads_from 依赖关系

这说明 Workflow 内部协作已经有字段级依赖基础。

### 3.2 Agent 元数据层

- core/agents/config.py

这里已经定义了：

- inputs
- outputs
- depends_on
- reads_from
- output_field

这说明 Agent 已经有描述自己输入输出与协作依赖的能力。

### 3.3 Assistant 线程与回写层

- app/services/intelligent_assistant_service.py

这里已经定义了：

- assistant_threads
- assistant_thread_messages
- report_refs
- write_report_back_to_assistant_thread

这说明 Assistant 侧已经有调用结果挂接与会话沉淀机制。

### 3.4 当前验证性实现

当前仓库中已经存在一个验证性质的原型实现：

- core/collaboration_runtime.py
- core/tools/implementations/assistant_ops/agent_executor.py

这个实现的定位是 runtime spike，仅用于验证统一调用信封是否能嵌入 Assistant -> Agent 链路。

后续如果设计与当前 spike 不一致，应以本设计文档为准调整实现，而不是继续围绕 spike 扩散。

## 4. 设计原则

### 4.1 先统一运行时，再扩展数据层

本期优先统一调用请求、来源、策略、结果，不直接扩展到完整 Artifact 平台。

### 4.2 同一语义，同一模型

Assistant -> Agent、Workflow -> Agent、Agent -> Agent 三种内部调用，只允许入口不同，不允许底层契约完全分裂。

### 4.3 internal_messages 与运行时解耦

internal_messages 继续承担研究消息、内部情报、知识沉淀职责，不承担实时调用编排职责。

### 4.4 先最小闭环，再逐步统一

第一阶段只统一最关键的请求与结果结构，不强推所有旧链路一次性迁移。

### 4.5 允许保留现有状态层优势

WorkflowStateSchema 不废弃，协作运行时应与状态层并存，而不是替换状态层。

## 5. 核心模型

### 5.1 InvocationRequest

表示一次内部调用请求，统一承载来源、目标、输入、执行策略。

建议字段：

- invocation_id
- target_type
- target_id
- action
- payload
- provenance
- policy
- metadata
- created_at

说明：

- target_type 先支持 agent、workflow、tool
- action 默认为 execute，后续可扩展 preview、validate、handoff
- payload 保持面向业务的原始输入，不要求本期强制 schema 化

### 5.2 InvocationProvenance

表示一次内部调用的来源上下文。

建议字段：

- source_type
- source_id
- user_id
- session_id
- thread_id
- workflow_id
- step_id
- trigger
- metadata

source_type 建议至少支持：

- external_user
- assistant
- workflow
- agent
- system

作用：

- 区分外部用户输入和内部转发输入
- 为后续审计、回放、调试、权限控制提供基础

### 5.3 InvocationPolicy

表示执行策略。

建议字段：

- idempotency_key
- timeout_seconds
- lane
- allow_partial
- visible_to_caller

说明：

- idempotency_key 用于避免重复执行
- lane 用于控制同一协作域内的并发污染
- visible_to_caller 用于控制是否要把结果同步回当前线程或当前流程

### 5.4 InvocationResult

表示一次内部调用的结果。

建议字段：

- invocation_id
- target_type
- target_id
- status
- started_at
- completed_at
- output_text
- structured_output
- output_field
- artifacts
- error_message
- metadata

说明：

- output_text 面向用户和线程摘要
- structured_output 面向系统复用
- output_field 用于和现有 Agent output_field、Workflow state 对齐

### 5.5 InvocationArtifactRef

本期只保留轻量引用，不建设完整 Artifact 平台。

建议字段：

- ref_type
- artifact_key
- title
- summary
- source_collection
- symbol
- output_field
- metadata

作用：

- 将调用结果以轻量引用方式挂到 Assistant 线程、后续工作流节点或调试面板
- 为 v4.0 的通用 ArtifactRef 演进保留兼容入口

## 6. 三类调用入口

### 6.1 Assistant -> Agent

这是第一优先级入口。

适用场景：

- Assistant 直接调用估值 Agent
- Assistant 直接调用复盘 Agent
- Assistant 直接调用风控 Agent

要求：

- 必须生成 InvocationRequest
- 必须记录 provenance.source_type = assistant
- 必须产生 InvocationResult
- 允许把轻量结果引用挂回 assistant_threads.report_refs

### 6.2 Workflow -> Agent

这是第二优先级入口。

适用场景：

- Workflow 节点内部调用单个 Agent 能力
- 工作流动态插入 Agent 节点

要求：

- provenance.source_type = workflow
- provenance.workflow_id 和 step_id 必须有值
- InvocationResult.output_field 必须能映射回 WorkflowStateSchema
- 结果可直接进入 state，也可保留轻量 invocation 记录

### 6.3 Agent -> Agent

这是第三优先级入口。

适用场景：

- 主 Agent 委托子 Agent 做专项任务
- Manager Agent 调用专业 Agent

要求：

- provenance.source_type = agent
- provenance.source_id = 调用方 agent_id
- 必须走统一权限与可见性判断
- 本期不要求做复杂 ping-pong 会话协商

## 7. 与现有模块的关系

### 7.1 与 WorkflowStateSchema 的关系

协作运行时不替代 WorkflowStateSchema。

二者分工为：

- 协作运行时：描述一次调用行为
- WorkflowStateSchema：描述工作流内部字段状态

换句话说：

- InvocationRequest 解决谁调谁
- WorkflowStateSchema 解决结果写到哪

### 7.2 与 AgentMetadata 的关系

协作运行时不替代 AgentMetadata。

AgentMetadata 继续负责：

- Agent 自身输入输出声明
- 默认 output_field
- reads_from 依赖说明

协作运行时只在调用时读取这些信息，并形成统一调用记录。

### 7.3 与 intelligent_assistant_service 的关系

智能助手继续管理：

- 线程
- 消息
- 报告引用
- 主题上下文

协作运行时只把调用结果转成轻量引用，让 Assistant 决定是否挂接到线程。

### 7.4 与 internal_messages 的关系

保持解耦。

internal_messages 继续承担：

- 研究消息
- 内部情报
- 检索型内容沉淀

协作运行时不依赖 internal_messages 才能完成调用。

## 8. 最小落地方案

### 8.1 Phase 1

先接通 Assistant -> Agent。

实现目标：

- 统一生成 InvocationRequest
- 统一产出 InvocationResult
- 调用记录独立持久化
- 可选挂接 Assistant 线程引用

落点建议：

- core/collaboration_runtime.py
- core/tools/implementations/assistant_ops/agent_executor.py
- app/services/intelligent_assistant_service.py

### 8.2 Phase 2

把 Workflow -> Agent 接入同一模型。

实现目标：

- 在 workflow builder 或 engine 内形成统一调用请求
- 将 InvocationResult.output_field 映射回 state
- 保留调试和追踪能力

落点建议：

- core/workflow/builder.py
- core/workflow/engine.py
- core/state/models.py
- core/state/builder.py

### 8.3 Phase 3

补 Agent -> Agent。

实现目标：

- 统一 provenance.source_type = agent
- 统一权限检查
- 统一结果记录

落点建议：

- core/agents/manager.py
- core/agents/factory.py
- 相关 agent orchestration 入口

### 8.4 实际落地状态（2026-03）

截至 2026-03，本设计已经不再停留在“最小落地方案”，而是形成了一套可直接用于排障和回放的调试闭环。

已完成的运行时接入：

- Assistant -> Agent 已统一记录
- Workflow -> Agent 已统一记录
- Agent -> Agent 已统一记录
- 模板调试台已直接消费上述调用记录

已完成的调试能力：

- 单 Agent 调试
- 完整工作流调试
- 统一调用记录查询
- 按 root 调用链分组展示
- 基于调用链的一键回填调试
- 前置输入来源追踪
- 来源节点与当前节点的 Request/Result 对比
- researcher / risk / manager / trader 类 Agent 的单点调试入口
- 当前 root 调用链锁定

已完成的治理与契约接入：

- 调试台已直接读取 `maturity_level`、`input_mode`、`debug_replay_mode`、`callable_surfaces`
- 调试台已直接读取 `input_contract.source`、`state_field`、`producer_hint`
- 调用链来源追踪与自动回填已优先按声明式契约匹配

这意味着协作运行时已经从“可记录”演进到“可观察、可追踪、可回放”。

## 9. 数据存储建议

建议新增独立集合：

- assistant_agent_invocations
- workflow_agent_invocations
- agent_agent_invocations

建议记录：

- invocation_id
- root_invocation_id
- parent_invocation_id
- user_id
- thread_id
- execution_id
- target_type
- target_id
- request
- result
- status
- created_at
- updated_at

原因：

- 不污染 assistant_threads 主文档
- 可单独做运行时追踪、审计、调试、回放
- Assistant、Workflow、Agent 三条入口可以先分集合落地，减少本期迁移面
- 后续可平滑扩展为 workflow_invocations 或统一 invocations 集合

本期不要求马上统一成全局 invocations 集合，但命名上应为后续扩展留出余地。

### 9.1 当前实际存储字段补充

在当前实现中，三类集合除了基础 request/result 之外，还额外落了以下追踪字段：

- root_invocation_id: 一条调用链的根节点，通常对应 assistant 根调用
- parent_invocation_id: 当前调用的直接上游调用
- execution_id: 本次执行链标识；对于 assistant 发起的单 Agent 工作流，会复用 assistant invocation_id
- workflow_id: 当前工作流标识
- thread_id: 助手线程标识
- step_id: 工作流节点或来源步骤标识

其中最关键的是：

- root_invocation_id 用于把 assistant -> workflow -> agent 聚合成同一条链
- parent_invocation_id 用于恢复直接上下游关系

这是调试台能够实现“按链查看”“锁定当前链”“前置输入来源追踪”的基础。

## 9.2 统一查询视图

当前实现没有强制迁移为全局 `invocations` 集合，而是在调试 API 层做统一归一化。

统一入口：

- `GET /api/templates/debug/invocations`

统一查询来源：

- `assistant_agent_invocations`
- `workflow_agent_invocations`
- `agent_agent_invocations`

统一返回能力：

- 平铺列表查询
- 按 root 调用链分组
- 按目标 Agent、工作流、线程、状态、股票代码筛选
- 按 root_invocation_id 锁定单条调用链

这种做法的优点是：

- 不打断现有存储结构
- 调试台可以快速上线
- 后续若要迁移到统一集合，前端交互和调试模型仍可基本不变

## 9.3 调试台落地设计

调试台复用了已有模板调试页面：

- 前端路由：`/settings/templates/debug`
- 后端路由：`app/routers/templates_debug.py`

当前页面包含三种模式：

- 单 Agent 调试
- 完整工作流调试
- 调用记录

其中单 Agent 调试已从“分析师模板调试”扩展为统一 Agent 调试入口，当前可直接覆盖 analyst、researcher、risk、manager、trader 等 v2 Agent。

其中“调用记录”模式承担了协作运行时的可视化职责，核心交互包括：

1. 查询统一调用记录
2. 按 root 调用链查看 assistant -> workflow -> agent 链路
3. 选中任意节点查看 request/result 详情
4. 查看该节点依赖的前置输入字段来自哪条上游 invocation
5. 点击来源节点继续追溯上游详情
6. 对比来源节点与当前节点的 request/result
7. 一键跳转并回填到单 Agent 调试

## 9.4 manager 类 Agent 的单独调试策略

对研究经理、风险经理、交易员等依赖上游 state 的 Agent，当前调试台采用“手动补齐 + 调用链自动回填”的组合策略。

设计原因：

- 这类 Agent 读取的不是简单 ticker/date，而是上游 Agent 的结构化输出字段
- 仅靠单 Agent 调试入口无法天然还原这些前置输入

当前方案：

- Agent metadata 暴露额外 debug_inputs
- 调试请求支持 `extra_state`
- 前端根据 Agent metadata 动态渲染前置输入框
- 也可以从历史调用链自动回填这些字段

截至 2026-03，该方案已经进一步演进为“声明式输入契约优先”：

- 调试台优先读取 `input_contract`
- 调试台展示 `source / state_field / producer_hint`
- 调用链回填优先按 `state_field` 匹配
- 若声明了 `producer_hint`，则优先匹配指定上游 Agent

这样既保留了“单 Agent 精确回放”的能力，也不强制用户每次都跑完整工作流。

## 9.5 已验证的调用链关系

当前实现已经验证如下 lineage 关系：

- assistant 根调用：
  - `root_invocation_id = self`
  - `parent_invocation_id = None`
- workflow 节点调用：
  - `root_invocation_id = assistant invocation_id`
  - `parent_invocation_id = assistant invocation_id`
- agent 委托调用：
  - `root_invocation_id = assistant invocation_id`
  - `parent_invocation_id = workflow invocation_id`

这套关系保证了：

- 可以追整条链
- 可以恢复直接父子关系
- 可以针对 manager 类 Agent 反向找到 bull_report、bear_report、investment_plan 等输入来源

## 10. 可见性与权限规则

### 10.1 最小权限原则

不是所有 Agent 默认都能被所有入口调用。

建议区分三类：

- assistant_callable
- workflow_callable
- internal_only

这三个能力标签可先放在 agent_config 或 agent metadata 的扩展字段中。

### 10.2 线程可见性

Assistant 线程只挂接可读摘要，不直接写入大体积 structured_output。

原因：

- 避免线程文档膨胀
- 避免前端直接耦合内部结构化结果

### 10.3 工作流可见性

Workflow 可以直接消费 structured_output，但仍建议保留 invocation 摘要，便于后续调试和追踪。

## 11. 与 v4.0 的关系

本设计是 v4.0 统一协作数据层的前置条件，而不是替代方案。

v4.0 可在本设计之上进一步扩展：

- 通用 ArtifactRef
- HandoffSpec
- 统一 Agent Team 协作协议
- 跨流程可复用产物仓库

v3.0 不应直接跳到这些更重的设计，否则会把当前简单调用问题和未来平台化问题混在一起。

## 12. 风险与取舍

### 12.1 风险

- 如果直接沿着当前各链路继续开发，会形成更多入口分裂
- 如果过早做完整 Artifact 平台，会放大设计成本和迁移成本
- 如果把 internal_messages 当运行时总线，会让知识沉淀与实时编排高度耦合

### 12.2 取舍

本设计刻意选择：

- 轻运行时契约
- 重用现有 state 和 metadata
- 轻量结果引用
- 延迟完整 Artifact 平台建设

这是为了在 v3.0 先解决最常见、最真实的协作入口统一问题。

## 13. 验收标准

满足以下条件视为 v3.0 协作运行时第一阶段完成：

1. Assistant -> Agent 已统一走 InvocationRequest 和 InvocationResult
2. 调用来源可追踪到 user_id、thread_id、source_type
3. 调用结果有独立记录，不只存在于线程消息中
4. 线程只保存轻量引用，不保存大体积运行时结果
5. Workflow -> Agent 能在下一阶段无须重做模型即可接入

## 14. 后续实现说明

当前仓库里已经存在最小验证实现，但后续实现必须遵循以下原则：

1. 设计先于扩实现
2. 先统一 Assistant -> Agent，再统一 Workflow -> Agent
3. 所有新增调用入口优先复用统一运行时模型
4. 如当前 spike 与本设计不一致，应回到本设计做收敛
