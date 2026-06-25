# TradingAgents-CN v3.0 — Nanobot First 的 Agent 工坊统一设计

> 更新时间：2026-04-02
>
> 本文档用于回答当前系统中的一个结构性问题：为什么 Nanobot 能发现、创建、调用一部分 Agent/Skill 资产，但这些资产没有自然进入 Agent 工坊的规格、版本和治理链路。

## 1. 概述

### 1.1 当前问题

当前系统已经同时具备两条可工作的 Agent 资产链路：

1. Nanobot 轻量链路
2. Agent 工坊规格/版本链路

两条链路都能产生产物，但它们的写入目标不同：

1. Nanobot 更偏向直接写运行时资产，例如 `agent_configs`、`tool_agent_bindings`、`prompt_templates`，并立刻让资产可运行。
2. Agent 工坊更偏向先生成 `agent_specs`、`agent_versions`，在评估与发布之后，再投影到运行时。

这带来三个直接问题：

1. 用户在 Nanobot 中“已经生成了 Agent”，但在 Agent 工坊看不到。
2. 用户在 Agent 工坊里管理的是规格和版本，而不是 Nanobot 已经写入的运行时候选体。
3. 系统内部缺少统一的“权威资产层”，导致可发现、可执行、可治理三者没有完全对齐。

### 1.2 本文档的结论

建议将 Agent 体系统一为：

1. Nanobot 作为默认交互入口和需求收敛入口。
2. Agent 工坊作为统一的资产治理后端，而不是与 Nanobot 并列的一套独立建模流程。
3. 运行时配置作为发布投影层，而不是新的主资产层。

换句话说，目标不是“保留两套平行系统再做少量同步”，而是建立一套 Nanobot First、Workshop Backed、Runtime Projected 的单一资产生命周期。

---

## 2. 现状拆解

### 2.1 Nanobot 当前负责什么

Nanobot 当前已经能做这些事：

1. 侦察项目已有能力、技能、蓝图和运行时 Agent。
2. 在轻量确认后直接生成运行时 Agent 候选。
3. 在发现能力缺口时，进入外部 Skill 生成链路。
4. 直接面向用户执行对话式设计，而不强制进入传统工坊流程。

它的优势是快、交互成本低、接近真实用户表达。

它的结构性短板是：默认写入运行时层，而不是规格/版本层。

### 2.2 Agent 工坊当前负责什么

Agent 工坊当前更像一套显式治理流：

1. 规格澄清
2. 缺口分析
3. 版本构建
4. 调试评估
5. 发布

它的优势是：

1. 有明确的 `agent_specs` 和 `agent_versions` 分层。
2. 有状态流转、评估和发布语义。
3. 前端页面已经围绕 spec/version 生命周期组织。

它的结构性短板是：当前并不是 Nanobot 的默认落点，导致用户在 Nanobot 里做出来的很多东西没有自动进入工坊可见资产。

### 2.3 当前实际写入关系

当前链路可以简化为：

```text
Nanobot 设计对话
  -> 运行时候选写入 agent_configs / prompt_templates / tool_agent_bindings

Agent 工坊规格与版本流
  -> 写入 agent_specs / agent_versions
  -> publish
  -> 投影到 agent_configs
```

这说明现在已经存在单向同步：

1. Agent 工坊发布后会进入运行时。

但缺少反向统一：

1. Nanobot 创建的候选不会自然回流为 spec/version 资产。

---

## 3. 统一设计目标

### 3.1 总体目标

建立一套单一 Agent 资产生命周期：

```text
用户需求
  -> Nanobot 对话澄清
  -> Workshop-backed 规格草案
  -> 版本候选
  -> 调试/评估
  -> 发布
  -> 运行时投影
  -> 运行反馈回流
```

### 3.2 三层职责重新定义

统一后，三层职责应明确如下：

1. Nanobot 层：交互、澄清、侦察、建议、触发生成。
2. Workshop 资产层：Spec、Version、评估、发布、历史沿袭。
3. Runtime 投影层：真正用于 assistant/workflow/agent 执行的配置快照。

关键原则：

1. Spec/Version 是资产真相源。
2. Runtime Config 是执行投影，不是治理真相源。
3. Nanobot Session 是交互过程，不是最终资产本体。

### 3.3 为什么要以 Nanobot 为入口

因为真实用户不会先想“我要创建一个 spec”。

真实用户更接近这些表达：

1. 帮我做一个估值分析 Agent。
2. 这个能力缺口能不能补成可复用 Skill。
3. 这个 Agent 生成的报告会是什么样。
4. 我想基于现有 Agent 改一版。

这些表达天然是对话式的，不是表单式的。Nanobot 已经是最贴近这种交互的入口，因此更适合作为前门。

---

## 4. 目标架构

### 4.1 统一后的核心流转

```text
用户在 Nanobot 中提出需求
  -> Nanobot 先侦察已有 callable agent / skill / tool / workshop 资产
  -> 若已有可直接复用的 Agent，则优先调用或建议复用
  -> 若需要新建或重塑，则创建/更新 Workshop Draft Spec
  -> 规格确认后生成 Version Candidate
  -> 如有缺口，则转 Skill 生成链路补齐能力
  -> 版本通过调试/评估后发布
  -> 发布时同步生成或更新 Runtime Projection
```

### 4.2 统一后的资产模型

建议明确四类对象：

1. 对话线程：Nanobot Session，记录交互上下文。
2. 产品草案：AgentSpec，记录职责、边界、输入输出、能力需求。
3. 可运行版本：AgentVersion，记录版本化的 Prompt、工具、输出 schema、评估结果。
4. 运行时投影：agent_configs + prompt_templates + tool_agent_bindings，用于执行。

其中：

1. Session 可短生命周期。
2. Spec 和 Version 必须长期可追溯。
3. Runtime Projection 可重建，不应成为唯一权威来源。

### 4.3 source 字段语义统一

当前系统里已经存在：

1. `source = nanobot_generated`
2. `source = agent_workshop`

建议后续统一成两套语义：

1. `origin_source`：资产最初由哪里触发产生，例如 `nanobot`、`agent_workshop_ui`、`migration_import`。
2. `lifecycle_stage`：当前所处生命周期阶段，例如 `draft_spec`、`candidate_version`、`published_runtime`。

这样可以避免用单个 `source` 字段同时表达“从哪来”和“现在处于什么阶段”的双重含义。

---

## 5. 关键决策

### 5.1 决策一：Workshop 成为权威资产层

统一后，不再鼓励 Nanobot 直接只写运行时资产并停在那儿。

推荐规则：

1. 任何需要长期复用、可迭代、可治理的 Agent 资产，最终都必须落到 `agent_specs` 和 `agent_versions`。
2. 运行时直写只允许作为临时候选或兼容路径。
3. 对已有的 `nanobot_generated` 运行时资产，提供导入或回填到 Workshop 的能力。

### 5.2 决策二：运行时配置是发布投影

统一后，`agent_configs` 的角色应是：

1. 发布态 Agent 的执行快照。
2. 候选态 Agent 的临时执行载体。

但它不再是用户理解“我有哪些 Agent 资产”的首要列表来源。用户的资产视图应首先来自 Spec/Version 资产。

### 5.3 决策三：Nanobot 先查已有 Agent，再决定生成

对于类似“帮我做一下茅台的估值分析”这类整体任务：

1. 应先查 callable agent 是否已经覆盖。
2. 若已有成熟 Agent，优先复用 Agent，而不是直接拼底层工具。
3. 只有在没有合适 Agent，或用户明确要求重新设计时，才进入新建/改造链路。

这项规则虽然属于运行时决策策略，但它与统一资产流转直接相关，因为它决定系统更像“资产复用平台”还是“每次都重新搭积木的工具平台”。

### 5.4 决策四：Agent 工坊 UI 要从“独立创建页”转向“治理控制台”

统一后，Agent 工坊页面不再应被理解为唯一创建入口，而应被理解为：

1. 当前 Nanobot 线程对应资产的治理面板。
2. 历史 Spec/Version 的审阅、评估、发布、归档面板。
3. 能力缺口与 Skill 补齐的正式交接面板。

也就是说，创建入口在 Nanobot，治理入口在 Workshop。

---

## 6. 分阶段落地方案

### 6.1 Phase 1：先打通最小统一链路

目标：不大改前端交互，先把资产层连起来。

建议实现：

1. 为 Nanobot 新增“创建或更新 Workshop Draft Spec”能力。
2. 为运行时 `nanobot_generated` 候选补充 `spec_id`、`version_id`、`origin_source` 等元数据。
3. 新增“将运行时候选导入为 Workshop 资产”的兼容路径。
4. Agent 工坊列表允许显示 `origin_source = nanobot` 的草案和候选版本。

完成后收益：

1. Nanobot 生成的 Agent 不再天然消失在工坊视野之外。
2. 老的直写运行时路径仍可兼容。

### 6.2 Phase 2：让 Nanobot 默认落 Workshop

目标：把默认创建链路改成 Spec/Version First。

建议实现：

1. Nanobot 在确认生成后，先写 Draft Spec。
2. 再从 Draft Spec 构建 Candidate Version。
3. Candidate Version 需要调试或预览时，再生成临时 Runtime Projection。
4. 发布后将 Projection 升格为正式运行时配置。

完成后收益：

1. 所有可复用 Agent 都有清晰沿袭。
2. 评估、发布、归档不再是 Agent 工坊私有链路，而成为 Nanobot 产物的标准后处理。

### 6.3 Phase 3：统一前端心智模型

目标：让用户不再感知两套系统。

建议实现：

1. Nanobot 中新增“查看当前资产”入口，直接跳转到对应 Spec/Version 页面。
2. Agent 工坊页面支持从 Nanobot 线程上下文打开，而不是只支持“新建 Agent”。
3. Agent 管理页统一展示 built-in、runtime、workshop 三层来源，但要清楚区分其治理能力和展示语义。

### 6.4 Phase 4：完成历史资产迁移

目标：减少历史分裂数据。

建议实现：

1. 识别历史 `nanobot_generated` 运行时 Agent。
2. 按规则回填为 Spec/Version 资产。
3. 对无法完整回填的对象标记为 `imported_runtime_legacy`。
4. 提供人工补齐入口，而不是假装这些资产已经完整版本化。

---

## 7. 对现有代码的直接影响

### 7.1 Nanobot 侧

需要调整的重点：

1. 轻量生成工具不应只停在 `create_or_update_runtime_agent_config`。
2. 要增加 Spec/Version 层写入能力，或者至少增加回填桥接能力。
3. 资源侦察输出里要更明确区分 built-in、runtime、workshop 三层资产。

### 7.2 Agent 工坊服务侧

需要调整的重点：

1. 除了现有 UI 发起路径，还要支持 Nanobot 发起的草案创建和版本构建。
2. 增加从运行时候选导入 Workshop 的服务接口。
3. 发布逻辑继续保留投影到运行时，但元数据语义要更统一。

### 7.3 前端侧

需要调整的重点：

1. Agent 工坊页面文案应从“专门做需求讨论、版本生成和评估迭代”进一步调整为“治理当前 Agent 资产”。
2. 支持从 Nanobot 上下文跳入，不只是一页独立工作台。
3. 增加来源标签，例如 built-in、nanobot、workshop、imported legacy。

---

## 8. 非目标

本方案不主张：

1. 让所有 built-in Python Agent 都被强行转换成 Spec/Version 资产。
2. 取消运行时直写能力的所有兼容路径。
3. 把 Nanobot 会话记录本身当成正式资产模型。
4. 用一次性大迁移替代渐进式统一。

---

## 9. 推荐的下一步实施顺序

建议按下面顺序推进：

1. 先实现 Agent First 运行策略，避免 Nanobot 对已有成熟 Agent 复用不足。
2. 再实现 Nanobot 到 Workshop Draft 的最小桥接。
3. 再补运行时候选回填 Workshop 的兼容导入。
4. 最后收敛前端页面心智和资产总览。

原因很直接：

1. Agent First 先解决用户最明显的行为偏差。
2. Draft Bridge 先解决“做出来但看不到”的治理断层。
3. 历史迁移和 UI 收口属于第二阶段收益，不是当前最先止血点。

---

## 10. 最终结论

Agent 工坊可以，而且应该按 Nanobot 为基础来设计。

但准确说法不是“把工坊做成另一个 Nanobot 聊天页”，而是：

1. Nanobot 负责交互、发现、澄清和触发。
2. Agent 工坊负责资产化、版本化、评估、发布和治理。
3. Runtime 负责执行投影。

只有这样，系统才能同时满足三件事：

1. 用户交互足够自然。
2. 资产生命周期足够清晰。
3. 运行执行入口足够稳定。
