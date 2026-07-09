# TradingAgents-CN v3.0 Agent 平台治理层设计

## 文档信息

| 项目 | 内容 |
| ---- | ---- |
| 文档类型 | 设计文档 |
| 版本 | v3.0 |
| 状态 | Draft |
| 日期 | 2026-03-17 |
| 目标 | 补齐 Agent 平台化设计中尚未收口的治理层能力，为后续评估、发布、工坊化演进建立统一约束 |
| 对齐文档 | agent-design-maturity-checklist.md, agent-capability-audit.md, controlled-growth-agent-design.md, agent-workshop-iterative-design.md |

---

## 1. 背景

当前系统已经具备：

1. 稳定的 Agent 执行基座。
2. 协作运行时与统一调用记录。
3. 可操作的调用链调试与回放能力。
4. 较完整的 `AgentMetadata` 声明层。

但这些能力更多解决的是：

- Agent 能不能运行
- Agent 之间怎么协作
- 出问题后怎么排查

而没有完全解决：

- Agent 应该遵守什么统一治理规则
- 哪些 Agent 可以被哪些入口调用
- manager / trader 类 Agent 的输入契约如何标准化
- 审计结论如何约束运行时配置
- 后续评估与发布要建立在哪层统一约束之上

因此，v3.0 下一阶段不应急于继续扩大量新 Agent，而应先补一层平台治理能力。

---

## 2. 目标与非目标

## 2.1 核心目标

建立一层轻量、可渐进接入的 Agent 治理层，统一回答三个问题：

1. 这个 Agent 在平台中的角色和审核级别是什么。
2. 这个 Agent 的输入输出契约是否足够明确，尤其是对上游 state 的依赖。
3. 这个 Agent 的审计、调用面、成长配置是否与运行时一致。

## 2.2 本期目标

本期只做治理层设计，不直接重构主执行链路。

优先补三块：

1. Agent 治理配置规范。
2. manager / trader 输入契约规范。
3. 审计结论与运行时配置联动规范。

## 2.3 非目标

本设计明确不包含：

1. 重写 `BaseAgent`。
2. 替换 `AgentMetadata`。
3. 一次性统一所有历史 Agent 定义。
4. 直接落地完整评估平台或灰度发布平台。
5. 把治理层做成新的复杂总线。

---

## 3. 设计原则

## 3.1 治理层优先是约束层，不是执行层

治理层的职责是：

- 让声明更清晰
- 让配置更一致
- 让后续评估和发布有统一落点

而不是接管 Agent 的执行主循环。

## 3.2 增量接入，不推翻现有 metadata

优先复用现有：

- `AgentMetadata`
- `agent_configs`
- `AgentFactory`
- `WorkflowBuilder`
- 调试台与调用记录

治理层只补平台缺失的“统一规则”。

## 3.3 优先解决 manager / trader 契约问题

真正阻碍平台化的不是 analyst 类 Agent，而是依赖上游 state 的 manager / trader / risk manager。

这些 Agent 能运行，但输入契约仍偏隐式。

因此治理层必须优先把这些依赖显式化。

## 3.4 审计结论必须能落到配置上

如果能力审计只是文档，而不影响运行时配置、审核级别和调试约束，它就只是知识记录，不是平台治理。

---

## 4. 当前平台化缺口

## 4.1 声明层缺口

当前 `AgentMetadata` 已有很多字段，但仍存在以下缺口：

1. 缺少平台视角的成熟度/治理状态字段。
2. 缺少调用面约束的统一治理表达。
3. 对输入契约，尤其是“依赖哪个上游输出字段”表达不够强。

## 4.2 manager / trader 输入契约缺口

例如：

- `research_manager_v2` 依赖 `bull_report`、`bear_report`
- `risk_manager_v2` 依赖 `investment_plan`、多方风险观点
- `trader_v2` 依赖研究经理或风险经理产出

这些依赖虽然能从 metadata、代码和调试台中看出来，但不是平台级结构化契约。

## 4.3 审计联动缺口

当前已经有：

- 能力审计文档
- 成长角色建议
- review_level 建议

但还没有明确规则回答：

1. 审计结论如何写回运行时配置。
2. 新 Agent 如何继承默认治理策略。
3. 数据库驱动 Agent 与内建 Agent 如何统一治理。

---

## 5. 治理层总体方案

建议新增一个概念层：`AgentGovernanceProfile`。

它不替代 `AgentMetadata`，而是作为平台治理补丁层。

### 5.1 三层结构

```text
Layer 1: AgentMetadata
  - 输入输出、默认工具、output_field、reads_from

Layer 2: AgentGovernanceProfile
  - 成熟度、审核要求、调用面、输入契约、成长与发布约束

Layer 3: Runtime Binding
  - AgentFactory / WorkflowBuilder / templates_debug / invocation runtime 读取治理配置执行约束
```

这样做的好处是：

1. 不需要推翻现有 metadata。
2. 可对内建 Agent 和数据库 Agent 使用同一治理层。
3. 后续评估和发布可以直接挂在治理层之上。

---

## 6. 核心模型建议

## 6.1 AgentGovernanceProfile

建议字段：

- `agent_id`
- `maturity_level`: experimental / internal / stable
- `review_level`: auto_pending / manual_required / restricted
- `callable_surfaces`: assistant / workflow / agent / debug-only / internal-only
- `input_mode`: standalone / upstream-dependent / mixed
- `debug_replay_mode`: direct / requires_extra_state / requires_chain_prefill
- `growth_role`: extractor / reviewer / optimizer / none
- `growth_outputs`
- `memory_scope_hint`
- `release_stage`: draft / testing / active / deprecated
- `owner`
- `metadata`

作用：

1. 把“这个 Agent 在平台中的治理属性”从执行类中剥离出来。
2. 为调试台、Factory、Builder、评估和发布提供统一依据。

## 6.2 AgentInputContract

重点解决 manager / trader 输入契约问题。

建议字段：

- `agent_id`
- `required_inputs`
- `optional_inputs`
- `upstream_dependencies`
- `replay_requirements`
- `input_examples`

其中 `upstream_dependencies` 的每一项建议包含：

- `field_name`
- `source_type`: workflow / agent / assistant / manual
- `source_output_field`
- `source_agent_ids`
- `required`
- `notes`

例如研究经理可以表达为：

```json
{
  "agent_id": "research_manager_v2",
  "required_inputs": ["ticker", "analysis_date", "bull_report", "bear_report"],
  "upstream_dependencies": [
    {
      "field_name": "bull_report",
      "source_type": "agent",
      "source_output_field": "bull_report",
      "source_agent_ids": ["bull_researcher_v2"],
      "required": true
    },
    {
      "field_name": "bear_report",
      "source_type": "agent",
      "source_output_field": "bear_report",
      "source_agent_ids": ["bear_researcher_v2"],
      "required": true
    }
  ],
  "replay_requirements": {
    "mode": "requires_chain_prefill"
  }
}
```

## 6.3 AgentAuditSnapshot

不是新执行模型，而是把审计结论结构化沉淀。

建议字段：

- `agent_id`
- `workflow_scopes`
- `execution_mode`
- `growth_value`
- `review_level`
- `recommended_governance`
- `last_reviewed_at`
- `reviewed_by`

作用：

1. 让能力审计从 Markdown 走向结构化资产。
2. 为运行时配置、成长策略和评估门禁提供基础输入。

---

## 7. 与现有模块的关系

## 7.1 与 AgentMetadata 的关系

`AgentMetadata` 继续负责：

1. Agent 自身输入输出声明。
2. 默认工具。
3. `output_field`。
4. `reads_from`。

治理层不替代这些内容，只补平台视角规则。

## 7.2 与 agent_configs 的关系

数据库中的 `agent_configs` 继续作为动态 Agent 的配置来源。

治理层建议以两种方式之一接入：

1. 在 `agent_configs.metadata` 下增加治理字段。
2. 单独建立 `agent_governance_profiles` 集合，并通过 `agent_id` 关联。

优先建议：

- 第一阶段可先走 `agent_configs.metadata` 扩展，降低迁移成本。
- 当治理字段明显增多，再抽为独立集合。

## 7.3 与调试台的关系

调试台已经具备：

1. 识别上游依赖。
2. 自动回填前置 state。
3. 追踪输入来源。

治理层接入后，调试台可以不再只依赖经验逻辑，而是显式读取：

- `input_mode`
- `debug_replay_mode`
- `upstream_dependencies`

这会让 manager / trader 的调试从“能用”升级到“契约驱动”。

## 7.4 与 AgentFactory / WorkflowBuilder 的关系

治理层接入后，可在创建阶段统一做：

1. 调用面检查。
2. 输入模式检查。
3. 审核等级与成长角色注入。

而不是让这些判断散落在不同调用入口。

---

## 8. 第一阶段落地建议

## 8.1 最小可落地步骤

### Step 1

先补治理字段，不动主执行链：

- 在 `AgentMetadata` 或 `agent_configs.metadata` 中补 `maturity_level`、`input_mode`、`debug_replay_mode`、`callable_surfaces`

当前状态（2026-03）：已落地到 `AgentMetadata`。

### Step 2

挑 manager / trader / risk manager 做输入契约试点：

- `research_manager_v2`
- `risk_manager_v2`
- `trader_v2`
- `review_manager_v2`

当前状态（2026-03）：已完成前 3 个试点，并进一步扩展到：

- `bull_researcher_v2`
- `bear_researcher_v2`
- `risky_analyst_v2`
- `safe_analyst_v2`
- `neutral_analyst_v2`

当前试点契约已经直接落在 `AgentInput` 上，核心字段为：

- `source`
- `state_field`
- `producer_hint`

### Step 3

让调试台优先读取输入契约，而不是只依赖 `debug_inputs` 推断

当前状态（2026-03）：已落地。

调试台当前已实现：

1. 优先读取 `input_contract`
2. 展示 `source / state_field / producer_hint`
3. 让调用链来源解析与自动回填共用同一套契约匹配逻辑
4. 结合 `input_mode / debug_replay_mode` 展示治理提示与回放动作文案

### Step 4

把能力审计的结论结构化，形成最小 `AgentAuditSnapshot`

当前状态（2026-03）：尚未落地，仍停留在设计阶段。

## 8.1.1 当前已落地边界

截至 2026-03，平台治理层已经从纯设计推进到“声明层 + 调试台”两处实际落点：

1. `AgentMetadata` 已具备最小治理字段。
2. `AgentInput` 已具备最小输入契约字段。
3. 调试台已能可视化治理字段。
4. 调试台已能消费声明式输入契约。
5. researcher / risk / manager / trader 类 v2 Agent 已进入统一调试入口。

这说明治理层第一阶段已经不再只是文档规划，而是形成了最小可运行闭环。

## 8.1.2 当前未落地边界

以下内容仍属于下一阶段：

1. `AgentGovernanceProfile` 独立存储层。
2. `AgentAuditSnapshot` 结构化持久化。
3. Factory / Builder / runtime 的统一治理门禁。
4. 发布、评估、灰度与回退的治理闭环。

## 8.2 为什么先不碰评估和发布

因为评估与发布必须建立在治理层之上。

如果没有统一的：

- 审核等级
- 输入契约
- 调用面约束
- 成熟度分层

那么后续评估门禁和灰度发布会失去统一依据。

---

## 9. 下一阶段与后续阶段边界

## P1 本文解决

本文解决：

1. Agent 平台治理字段怎么统一。
2. manager / trader 输入契约怎么结构化。
3. 审计结论怎么落到运行时配置。

## P2 后续解决

后续评估层解决：

1. 标准样本评估。
2. 自动 benchmark。
3. 版本差异分析。
4. 发布前门禁。

## P3 再后续解决

再后续的工坊与发布层解决：

1. Spec -> Version 构建。
2. 版本状态流转。
3. 灰度发布。
4. 生命周期闭环。

---

## 10. 最终判断

如果说“Agent 平台化设计还没完全收口”，最核心的缺口不是执行能力，而是治理层。

因此，下一步最合理的方向不是继续补更多调试按钮，也不是重写基类，而是：

1. 把平台治理字段统一下来。
2. 把 manager / trader 的输入契约结构化。
3. 把能力审计结论从文档变成运行时可消费配置。

只有这样，后续评估、发布、工坊化这些平台能力才有可靠基础。
