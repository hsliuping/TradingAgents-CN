# v3.0 能力与七层记忆对应关系

## 📋 文档信息

| 项目 | 内容 |
| ------ | ------ |
| 版本 | v1.0 |
| 状态 | 已整理当前实现映射并完成 2026-04-08 复核 |
| 日期 | 2026-04-08 |
| 目标 | 说明智能助手、Agent 生成、Skill 生成、股票分析四条链路分别落在七层记忆模型的哪几层，以及哪些对象不应被算作记忆 |
| 关联文档 | [统一记忆层设计 — 基于 mem0 的全系统记忆整合](./unified-memory-layer-mem0.md)、[智能助手（分析助理）](./intelligent-assistant.md)、[Skill 自动生成系统](./skill-generation-system.md)、[Agent Workshop 端到端设计与缺口分析](../../architecture/AGENT_WORKSHOP_END_TO_END_DESIGN.md)、[v3.0 记忆系统优化待办清单](./memory-optimization-backlog.md) |

---

## 1. 先给结论

当前 v3.0 的七层记忆不是“每条业务线都把 7 层都实现一遍”，而是按职责拆分：

- **L1-L3** 主要由运行时和 Nanobot 本地记忆承担。
- **L5-L6** 主要由 mem0 统一承担。
- **L7** 是运行状态，不属于语义记忆。
- **L4** 已补最小闭环，并已进入助手与 Agent Workshop 治理链，但仍未成为所有链路统一依赖的稳定层。

因此，这四条能力的真实情况是：

1. **智能助手**：已经稳定使用 **L4 + L5/L6**，并保留自己的会话历史承载 **L2**。
2. **Agent 生成**：主链路更偏 **L2/L3/L7**，但当前 Agent Builder 治理链、Agent Workshop 版本模板构建链、production-review 证据链，以及发布门禁都已开始消费 **L4**，且仍有一部分通过 Nanobot compact 镜像到 **L5**。
3. **Skill 生成**：核心使用 **L6** 的 `skill_lesson`，其余主要是本轮生成过程的 **L1**。
4. **股票分析**：已经较完整地打通 **L5/L6**，并且运行任务状态明确属于 **L7**。

---

## 2. 七层定义基线

以下定义以 [统一记忆层设计](./unified-memory-layer-mem0.md) 为准：

| 层 | 名称 | 作用 | 当前主承载 |
| --- | --- | --- | --- |
| L1 | 运行时工作记忆 | 当前回合推理、工具结果、临时上下文 | Runtime 当前消息、工具调用结果 |
| L2 | 会话历史层 | 当前线程连续对话与恢复 | Nanobot Session、thread messages、助手主题消息 |
| L3 | 会话压缩层 | 长对话压缩、审计归档、低 token 恢复 | Nanobot `MEMORY.md` / `HISTORY.md` |
| L4 | 项目长期记忆层 | 跨线程共享项目规则、稳定上下文 | 项目级长期摘要、知识索引、按需镜像 |
| L5 | 用户语义记忆层 | 用户偏好、跨会话事实召回 | mem0 `conversation` / `user_preference` |
| L6 | Agent/领域经验层 | 分析经验、技能教训、成长记忆 | mem0 `analysis_insight` / `trade_pattern` / `skill_lesson` / `agent_experience` |
| L7 | 运行状态层 | 进度、状态、任务控制、当前绑定关系 | `memory_state_manager`、thread_context、任务状态 |

补充边界：

- mem0 当前统一的是 **L5/L6**，不是全部七层。
- Nanobot 本地 `MEMORY.md` / `HISTORY.md` 仍然是 **L2/L3** 主承载，不是 mem0 的替代品。
- `thread_context`、任务进度、当前选中的 spec/version/template 都更接近 **L7 运行状态/运行绑定**，不应混算为长期记忆。

---

## 3. 四条能力总览映射

| 能力 | L1 | L2 | L3 | L4 | L5 | L6 | L7 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 智能助手 | 有 | 有 | 弱依赖/间接 | 有，最小闭环 | 有 | 有 | 有，但不是记忆 |
| Agent 生成 | 有 | 有 | 有 | 有，治理最小注入 | 有，旁路镜像 | 弱，尚未形成专用经验层 | 很强 |
| Skill 生成 | 有 | 入口若经 Nanobot 则有 | 入口若经 Nanobot 则有 | 未统一 | 基本不用 | 有，核心层 | 少量流程状态 |
| 股票分析 | 有 | 有，取决于入口 | 无统一压缩层 | 未统一 | 有 | 有，核心层 | 很强 |

可以把这张表理解成：

- **助手** 现在已经是唯一同时具备 **L4 + L5/L6** 最小闭环的链路。
- **股票分析** 仍然是目前对 **L5/L6** 使用最成熟的核心分析链路之一。
- **Agent 生成** 目前更像“Nanobot 会话系统 + 资产治理系统”，不是一个以长期语义记忆为主的链路。
- **Skill 生成** 已经有明确的 **L6 skill_lesson**，但没有把完整会话系统内建到自己的管线里。

---

## 4. 智能助手对应关系

## 4.1 对应层

| 层 | 是否使用 | 当前实现方式 |
| --- | --- | --- |
| L1 | 是 | 当前轮消息、工具选择、Prompt 注入块 |
| L2 | 是 | 主题会话、历史消息持久化 |
| L3 | 否，当前不是主实现 | 智能助手本身不靠本地 compact 作为主链路 |
| L4 | 是，最小闭环 | 通过项目长期记忆块注入稳定项目规则和输出约束 |
| L5 | 是 | mem0 召回 `conversation`、`user_preference` |
| L6 | 是 | mem0 召回 `analysis_insight`、`trade_pattern` |
| L7 | 是，但不是记忆 | 线程 ID、主题标题、任务进度、报告引用过滤条件 |

## 4.2 代码证据

智能助手在 prompt 构建前，会先拼入 L4 项目长期记忆块，再从 mem0 召回：

- `project_rule`
- `governance_constraint`
- `analysis_output_constraint`
- `research_template`

以及：

- `conversation`
- `user_preference`
- `analysis_insight`
- `trade_pattern`

对应实现见 [app/services/intelligent_assistant_service.py](../../../app/services/intelligent_assistant_service.py)。

同时，智能助手会把当前轮对话写入 mem0 的 `conversation`，必要时再兜底写入 `analysis_insight`。因此它现在是当前最明确同时使用 **L4 + L5 + L6** 的业务链路。

## 4.3 归类说明

- 助手的“主题会话消息”属于 **L2**，因为它解决的是当前线程连续对话与恢复。
- 助手前置注入的项目规则、治理约束、输出约束属于 **L4**，因为它们跨线程共享、低变化、面向项目长期稳定复用。
- 助手从 mem0 召回的用户偏好和历史洞察属于 **L5/L6**，因为它们已经脱离单线程，能跨会话复用。
- 助手触发分析任务后的进度展示属于 **L7**，不是记忆。

## 4.4 当前结论

智能助手目前可以视为：

- **前台交互靠 L1/L2**
- **稳定项目约束靠 L4**
- **跨会话理解靠 L5/L6**
- **任务编排与进度靠 L7**

这条链路的七层对应关系是比较清晰的。

---

## 5. Agent 生成对应关系

这里的“Agent 生成”指的是 **Nanobot 作为入口的 Agent Workshop / Agent Builder 链路**，而不是单纯的数据库资产落库。

## 5.1 对应层

| 层 | 是否使用 | 当前实现方式 |
| --- | --- | --- |
| L1 | 是 | 当前轮需求理解、工具选择、治理判断、构建动作 |
| L2 | 是 | Nanobot Session、thread messages、线程恢复 |
| L3 | 是 | `MEMORY.md` / `HISTORY.md` 做 compact 与恢复 |
| L4 | 是，治理最小注入 + 模板构建注入 + production-review 校验 + 发布校验 | Agent Builder 请求会前置注入项目规则、治理约束、研究模板；Agent Workshop 版本模板会固化项目规则与输出约束，production-review 与发布前还会校验绑定是否真实成立 |
| L5 | 有，但不是主轴 | Nanobot compact 结果 best-effort 镜像到 mem0 `conversation` |
| L6 | 是，最小闭环已落地 | 已新增 `agent_builder_lesson`，评估后写入，版本迭代前与 runtime governance 路径可读 |
| L7 | 是，且很重 | `thread_context`、spec/version/template/workflow/node 绑定关系 |

## 5.2 代码与设计证据

1. Nanobot runtime 会把 `thread_context`、`spec_id`、`version_id`、`workflow_id` 等上下文绑定进当前会话元数据，见 [core/embedded_nanobot/runtime.py](../../../core/embedded_nanobot/runtime.py) 和 [app/services/embedded_nanobot_service.py](../../../app/services/embedded_nanobot_service.py)。
2. Nanobot 的本地记忆由 [core/embedded_nanobot/agent/memory.py](../../../core/embedded_nanobot/agent/memory.py) 负责，主载体是 `MEMORY.md` 与 `HISTORY.md`，这对应 **L3**。
3. compact 成功后，系统会 best-effort 镜像到 mem0 的 `conversation` scope，并带上 `thread_context`、`symbol`、`object_type`、`object_key` 等 metadata，这说明 Agent 生成链路对 **L5** 有桥接，但不是主读路径。
4. Agent Workshop 设计文档已经明确：Session、Spec、Version、Prompt Template、Runtime Config 是资产与状态对象，Nanobot Thread 只是协作容器，不替代主数据源，见 [docs/architecture/AGENT_WORKSHOP_END_TO_END_DESIGN.md](../../architecture/AGENT_WORKSHOP_END_TO_END_DESIGN.md)。
5. 当前 Agent Builder 治理请求命中时，runtime 会前置注入 L4 项目长期记忆块，作为 Agent Workshop 的稳定规则和治理约束上下文，见 [core/embedded_nanobot/runtime.py](../../../core/embedded_nanobot/runtime.py)。
6. 当前 Agent Workshop 在创建版本 Prompt Template 时，也会把 L4 项目长期记忆块注入生成出的 system_prompt 和 constraints，让稳定项目规则直接固化进版本模板，见 [app/services/agent_workshop_service.py](../../../app/services/agent_workshop_service.py)。
7. 当前 Agent Workshop 在发布版本前，会重新校验 Prompt Template 是否仍绑定当前 L4 项目长期记忆；若模板缺失绑定，则发布被拒绝，见 [app/services/agent_workshop_service.py](../../../app/services/agent_workshop_service.py)。
8. 当前 Agent Workshop 在 production-review 时，会重新校验运行时 debug_prompt.system_prompt 是否真实带上当前 L4 项目长期记忆；若缺少绑定或缺少 prompt 证据，则评估不能作为正式发布依据，见 [app/services/agent_workshop_service.py](../../../app/services/agent_workshop_service.py)。
9. 当前 `agent_builder_lesson` 已进入 [core/memory/models.py](../../../core/memory/models.py)、[core/memory/service.py](../../../core/memory/service.py) 和 [app/routers/memory.py](../../../app/routers/memory.py)，形成专用 scope 与 profile。
10. 当前 [app/services/agent_workshop_service.py](../../../app/services/agent_workshop_service.py) 已在 `evaluate_version(...)` 后写入 `agent_builder_lesson`，并在版本迭代前召回 lesson 注入 cloned prompt template。
11. 当前 [core/embedded_nanobot/runtime.py](../../../core/embedded_nanobot/runtime.py) 在命中 `agent_builder_governance` 时，会在 L4 项目长期记忆之后继续前置注入 L6 historical lessons。
12. 当前已补 [scripts/validate_agent_workshop_governance_l4_l6_loop.py](../../../scripts/validate_agent_workshop_governance_l4_l6_loop.py)，覆盖 Agent Workshop worker -> Embedded Nanobot runtime 的 L4 + L6 组合消费链路。

## 5.3 最重要的边界

这一条链路最容易被误判，必须单独强调：

- `thread_context` **不是 L5/L6 记忆**，它是 **L7 运行状态/绑定上下文**。
- Session / Spec / Version / Prompt Template / Runtime Config **不是七层记忆本身**，它们是 Agent 资产与治理对象。
- Nanobot 的 `MEMORY.md` / `HISTORY.md` 才是 Agent 生成阶段真正持续参与上下文恢复的记忆载体，对应 **L2/L3**。

## 5.4 当前结论

Agent 生成当前最准确的说法不是“已经全面打通七层记忆”，而是：

- **主要依赖 L2/L3 完成连续协作和恢复**
- **已开始用 L4 约束 Agent Builder 治理决策，固化到 Agent Workshop 版本模板，并进入 production-review 与发布门禁**
- **通过 L7 串起资产治理上下文**
- **少量把稳定结果桥接到 L5**
- **已经形成最小专用 L6 Agent 生成经验层**
- **当前仍不能把 conversation 镜像或 thread_context 绑定误写成 L6 落地**

当前剩余缺口更准确地说是：

- **L6 已落地，但仍未扩到需求确认阶段、版本构建前和更广对象样本**
- **统一 recall 观测和 dashboard 仍未补齐**

## 5.5 最小目标态建议

当前已经达到“最小可用 L6”之后，下一步更合理的目标是：

1. 把 lesson 读取点从“版本迭代前 + runtime governance”继续扩到需求确认阶段和版本构建前
2. 把 Agent Builder 对象样本纳入统一 recall 质量评估脚本，而不只停留在消费闭环脚本
3. 继续保持 metadata 优先过滤，避免 `agent_builder_lesson` 污染普通聊天或无关分析入口
4. 统一补上 recall 观测指标，能解释这类 lesson 为什么命中或为什么没有命中
5. 保持这层经验只沉淀少量高价值、可验证的 lesson，而不是退回到存整段对话或全量 prompt

这样做的结果是：

1. Agent 生成链就不再只有 L2/L3 的上下文连续性
2. L6 会开始承担“下次少犯同样错误”的职责
3. 也能和现有 `skill_lesson`、`agent_experience` 形成更清楚的边界

---

## 6. Skill 生成对应关系

## 6.1 对应层

| 层 | 是否使用 | 当前实现方式 |
| --- | --- | --- |
| L1 | 是 | 当轮规格澄清、代码生成、验证、评估、迭代 |
| L2 | 条件性存在 | 若入口经 Nanobot，则会话由 Nanobot 承载 |
| L3 | 条件性存在 | 若入口经 Nanobot，则 compact 由 Nanobot 承载 |
| L4 | 否 | 还没有统一的项目级 Skill 规则记忆层 |
| L5 | 基本没有作为主路径使用 | Skill 生成本身不靠用户对话记忆做核心召回 |
| L6 | 是，核心层 | mem0 `skill_lesson` |
| L7 | 少量 | 当前轮状态、结果对象、迭代轮次 |

## 6.2 代码证据

Skill 生成服务会：

- 在生成前从 mem0 召回 `skill_lesson`
- 生成完成后把迭代失败原因和成功教训写回 `skill_lesson`

对应实现见 [app/services/skill_generation_service.py](../../../app/services/skill_generation_service.py)。

其中召回还会按：

- `category`
- `data_source`
- 缺省时回退 `tool_id`

做 metadata 过滤。这说明 Skill 生成对七层的使用重点非常集中，就是 **L6 领域/技能经验层**。

## 6.3 归类说明

- Skill 的“当前这轮生成-验证-修复”是 **L1**，因为它只是本轮流水线状态。
- Skill 的历史教训是 **L6**，因为它会被后续同类 Skill 复用。
- 如果 Skill 生成入口走 Nanobot，对话和 compact 仍然属于 **L2/L3**，但那是入口外壳，不是 Skill 生成管线本身的核心记忆设计。

## 6.4 当前结论

Skill 生成当前是四条链路里最“单点清晰”的一个：

- **主价值在 L6 `skill_lesson`**
- **L1 负责当轮生成过程**
- **L2/L3 只在经 Nanobot 入口时被复用**

---

## 7. 股票分析对应关系

这里的“股票分析”包括统一分析服务、v2 workflow runtime，以及 legacy graph 已接入的 mem0 compat 主路径。

## 7.1 对应层

| 层 | 是否使用 | 当前实现方式 |
| --- | --- | --- |
| L1 | 是 | 当前分析任务的状态、当前回合 prompt、工具结果 |
| L2 | 有 | 若从助手/会话入口进入，会带入当前线程上下文 |
| L3 | 否 | 股票分析本身没有独立 compact 层 |
| L4 | 否，尚未统一 | 还没有稳定项目级投资规则记忆层 |
| L5 | 是 | `user_preference`，以及部分跨会话分析上下文 |
| L6 | 是，核心层 | `analysis_insight`、`agent_experience`、`trade_pattern`、approve 后桥接的成长记忆 |
| L7 | 是，且很强 | 任务状态、进度推送、运行编排、当前工作流状态 |

## 7.2 代码证据

1. 统一分析服务会按股票代码召回：
   - `analysis_insight`
   - `agent_experience`
   - `user_preference`

   对应实现见 [app/services/unified_analysis_service.py](../../../app/services/unified_analysis_service.py)。

2. 分析完成后，会把分析结论写回 `analysis_insight`，说明股票分析已经稳定把自己的长期输出沉淀到 **L6**。

3. v2 workflow runtime 的 agent 经验通过 [core/memory/memory_manager.py](../../../core/memory/memory_manager.py) 的 `Mem0AgentMemory` 统一读写 `agent_experience`。

4. legacy graph / trading graph 的经验记忆通过 [tradingagents/core/engine/memory_provider.py](../../../tradingagents/core/engine/memory_provider.py) 的 `Mem0CompatMemory` 统一读写 `agent_experience`。

5. 工作流成长记忆在 approve 后会桥接到 mem0，不同类型映射到 `user_preference`、`analysis_insight`、`agent_experience`、`trade_pattern`，对应实现见 [app/services/workflow_growth_service.py](../../../app/services/workflow_growth_service.py)。

## 7.3 归类说明

- 报告文件、数据库中的分析结果是业务真相/产物，不直接等于七层记忆。
- 真正算进七层记忆的，是那些被抽取、沉淀并支持后续召回复用的内容，例如：
  - 用户偏好
  - 历史分析洞察
  - Agent 历史经验
  - 交易模式
- 分析任务进度、WebSocket 推送、任务状态缓存属于 **L7**，不是记忆。

## 7.4 当前结论

股票分析是当前与七层记忆结合最深的一条链路之一：

- **用户侧偏好使用 L5**
- **分析结论与 agent 经验使用 L6**
- **任务调度和进度走 L7**

它已经比较接近 v3.0 希望达成的“语义记忆主路径统一”。

---

## 8. 哪些对象不要再混算成“记忆”

为了后续范围清晰，下面这些对象必须和七层记忆分开描述：

| 对象 | 正确定义 | 对应层 |
| --- | --- | --- |
| `thread_context` | 运行时绑定上下文 | L7 |
| `memory_state_manager` | 任务状态缓存 / 进度分发 | L7 |
| Session / Spec / Version / Prompt Template / Runtime Config | Agent 工坊资产与治理对象 | 不直接属于七层记忆 |
| 报告正文 / Mongo 业务表 / 分析结果文件 | 业务真相与产物 | 不直接属于七层记忆 |
| Nanobot `MEMORY.md` / `HISTORY.md` | 会话压缩与恢复记忆 | L3 |
| mem0 `conversation` / `user_preference` | 用户语义记忆 | L5 |
| mem0 `analysis_insight` / `skill_lesson` / `agent_experience` / `trade_pattern` | 领域经验记忆 | L6 |

---

## 9. 当前缺口与后续整理建议

从这次映射可以看到，v3.0 当前还缺的不是“再造一套记忆系统”，而是把已有七层边界继续收紧：

### 9.1 还没统一好的地方

1. **L4 项目长期记忆层仍然偏弱**
   - 助手与 Agent Workshop 已经开始依赖统一项目规则层，但多数链路仍未统一接入。
   - 现状已经不是“纯按需镜像”，但距离全局稳定平台还有明显差距。

2. **Agent 生成缺少专用的 L6 经验层**
   - 当前更多依赖 L2/L3 会话和 L7 资产绑定。
   - 还没有像 Skill 生成那样清晰的 `agent_builder_lesson` 或等价经验 scope。

3. **不同链路对 L2/L3 的描述口径还不完全统一**
   - 尤其是“助手线程历史”“Nanobot thread”“本地 compact”“业务历史记录”容易混淆。

### 9.2 建议后续文档口径固定为

1. 先说这条链路的主层，不要默认按 L1-L7 全覆盖叙述。
2. 凡是 `thread_context`、任务进度、当前绑定关系，一律先判到 L7，而不是记忆。
3. 凡是可跨会话召回并能服务后续推理的稳定事实，再归到 L5/L6。
4. 凡是报告、配置、Spec、Version、Prompt Template，一律先判定为资产或业务真相，而不是记忆本体。

---

## 10. 一句话版映射

- **智能助手**：L2 负责会话承接，L5/L6 负责跨会话理解，L7 负责任务编排状态。
- **Agent 生成**：L2/L3 负责 Nanobot 持续协作，L4 已进入治理与模板链路，L7 负责工坊上下文绑定，L5 只有镜像桥接，L6 仍未补齐。
- **Skill 生成**：L1 负责当轮生成，L6 的 `skill_lesson` 负责历史教训复用。
- **股票分析**：L5 负责用户偏好，L6 负责分析洞察与 agent 经验，L7 负责任务运行状态。
