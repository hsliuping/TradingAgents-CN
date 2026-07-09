# Nanobot Memory 治理与上下文可靠性设计

> 适用版本：v3.0  
> 目标模块：Embedded Nanobot / Agent Workshop / MemoryService / Agent Builder  
> 状态：Draft  
> 核心目标：让 Nanobot 明确区分当前事实、历史经验、废弃记忆和语义候选，避免旧 Agent / 已删除 Agent / 过期方案污染当前新建或迭代流程。

---

## 1. 背景

当前 Nanobot 在 Agent Workshop 新建 Agent 流程中出现了严重的上下文污染问题：

- 用户已经删除旧 Agent，但 Nanobot 仍从历史 Memory 中恢复旧 Agent 的方案、工具绑定和 gap 结论。
- 用户当前是在新建 Agent，但 Nanobot 把旧对话中的阶段状态当成当前流程状态。
- 用户说“方案 A”时，Nanobot 没有基于当前线程最近一次明确选项判断，而是从历史记忆中猜测含义。
- `MEMORY.md`、Mem0、MongoDB、向量库、Redis 等多种存储共同参与上下文构造，但缺少统一的职责边界、生命周期和冲突裁决。

这导致 Agent Builder 不可靠：LLM 会把历史、废弃、候选、缓存和当前事实混在一起。

---

## 2. 问题定义

### 2.1 当前 Memory 管理过粗

当前文件层 Memory 的问题：

- 以自然语言文本追加到文件中。
- 没有结构化事实抽取。
- 没有 `active / deleted / invalidated / superseded` 生命周期。
- 没有作用域隔离，例如 `thread_id / spec_id / version_id`。
- 删除 Agent 后，只能追加“已删除”说明，无法阻止旧内容被召回。
- LLM 需要自行从长文本中判断哪些有效，哪些无效，这不可靠。

### 2.2 多存储职责不清

项目中同时存在：

- MongoDB
- Mem0
- 向量数据库
- Redis
- 文件 Memory

问题不是“存储多”，而是缺少统一规则：

- 谁是权威事实源？
- 谁只是搜索索引？
- 谁只是缓存？
- 哪些内容允许进入 LLM prompt？
- 出现冲突时以谁为准？
- 删除 / 迭代 / 发布时如何同步失效？

### 2.3 Agent Builder 的特殊风险

Agent Builder 是强状态流程，不是普通聊天。

它必须明确知道：

- 当前是否新建 Agent。
- 当前 Agent 是否已删除。
- 当前阶段是需求确认、能力盘点、方案选择还是生成。
- 当前用户选的是哪个方案。
- 当前 gap 报告是否属于当前 Agent。
- 当前工具绑定是否属于当前版本。

这些不能由 LLM 从历史文本中推断，必须由系统状态维护。

---

## 3. 设计目标

### 3.1 核心目标

建立一套 Nanobot Memory Governance 机制，使所有进入 Nanobot prompt 的上下文都具备：

- 明确来源 source
- 明确作用域 scope
- 明确权威等级 authority
- 明确有效性 validity
- 明确生命周期 lifecycle_status
- 可审计的召回日志

### 3.2 非目标

本设计不要求立即引入 Zep / Graphiti。

当前阶段以 MongoDB 为主存储：

- MongoDB：Agent Builder 记忆的唯一事实源和检索源。
- Mem0：可选，仅用于通用对话记忆（用户偏好、分析经验），不参与 Agent Builder 流程状态管理。
- 文件 Memory：退出决策链，仅作审计。

Zep / Graphiti 可作为长期升级方向，但不是 v3.0 必需依赖。

---

## 4. 存储职责边界

### 4.1 总原则

```text
MongoDB = 权威事实源 + Agent Builder 记忆主存储
向量数据库 = 能力 / 文档检索索引
Redis = 短期缓存和运行态
Mem0 = 可选，通用对话记忆（不参与 Agent Builder 流程）
文件 Memory = 审计 / 调试，不参与线上决策
```

### 4.2 存储权责表

| 存储 | 定位 | 可以决定什么 | 不能决定什么 |
|---|---|---|---|
| MongoDB | 权威事实源 + Agent Builder 记忆主存储 | Agent 状态、版本、删除、流程阶段、记忆生命周期、工具绑定、评估结果、历史 lesson | 语义相似度（对 Agent Builder 不需要） |
| Mem0 | 可选，通用对话记忆 | 跨会话用户偏好、分析经验 | 当前资产状态、删除状态、流程阶段、工具绑定有效性 |
| 向量数据库 | 搜索索引 | 工具、Skill、文档、模板的语义相关性 | 业务事实有效性、Agent 当前状态 |
| Redis | 临时缓存 | SSE 状态、任务进度、锁、短期缓存 | 长期事实、最终状态、删除状态 |
| 文件 Memory | 审计 / 调试 | 人工排查线索 | 任何线上决策 |

> **Agent Builder 记忆全部走 MongoDB，不依赖 Mem0。** Mem0 仅保留给通用对话场景（智能助手、分析经验），Agent Builder 不调用 Mem0。

---

## 5. 上下文权威等级

所有进入 Nanobot prompt 的上下文必须标注权威等级。

### 5.1 Authority 等级

| authority | 含义 | 示例 |
|---|---|---|
| `source_of_truth` | 权威事实，冲突时优先 | MongoDB live state、thread_context、IntentContext |
| `runtime_state` | 当前运行态，短期有效 | 当前 SSE job、当前工具执行结果 |
| `advisory` | 建议性上下文 | MongoDB Ledger 中 active reusable lesson |
| `candidate` | 候选信息 | 向量库检索到的工具 / Skill 候选 |
| `audit_only` | 只供排查，不给 LLM 决策 | 文件 MEMORY.md、删除审计记录 |

### 5.2 冲突裁决规则

```text
source_of_truth > runtime_state > advisory > candidate > audit_only
```

当冲突发生时：

- MongoDB live state 优先于任何其他来源。
- 当前 thread_context 优先于历史 Memory。
- 当前工具注册表优先于向量库候选。
- 当前版本 tool binding 优先于历史 lesson。
- 已删除 / invalidated 记忆不能作为 advisory 注入。

### 5.3 Thread Context / Intent Context 也是 Source of Truth

`thread_context` 和 `IntentContext` 不是内存里的临时变量，而是当前流程的权威状态。必须满足：

- 每轮对话结束时持久化到 MongoDB（`embedded_nanobot_threads`）。
- 每轮对话开始时从 MongoDB 读取，不能依赖 contextvar 或进程内存。
- contextvar 只作为同进程内的加速缓存，不可作为跨轮唯一来源。
- 禁止在工具调用链内部通过 contextvar 隐式写入后不复写回持久层。
- 前端必须正确接收并回传 `thread_context`，服务端以服务端持久化为准。

这条规则是避免“跨轮阶段丢失”“intent 被回退”的关键。

---

## 6. Agent Builder Memory Ledger

### 6.1 新增 MongoDB 集合

新增集合：

```text
agent_builder_memory_ledger
```

该集合记录 Agent Builder 相关记忆的结构化生命周期。

### 6.2 字段设计

```json
{
  "memory_id": "abm_xxx",
  "user_id": "user_xxx",
  "thread_id": "thread_xxx",
  "spec_id": "spec_xxx",
  "version_id": "version_xxx",
  "agent_name": "财报风险信号识别器",

  "memory_type": "requirement | decision | gap_report | build_plan | tool_binding | prompt_design | evaluation_lesson | deletion | user_preference",
  "content": "用户确认该 Agent 只关注商誉减值、应收账款异常、现金流恶化，不输出交易建议。",
  "payload": {},

  "lifecycle_status": "active | superseded | invalidated | deleted | expired",
  "valid_from": "2026-06-30T00:00:00+08:00",
  "valid_until": null,
  "invalidated_at": null,
  "invalidated_by": null,
  "invalidated_reason": "",

  "source": "user_message | tool_result | workshop_asset | evaluation | system",
  "authority": "source_of_truth | advisory | candidate | audit_only",
  "reusable": false,
  "confidence": 0.95,

  "mem0_ids": [],
  "vector_ids": [],

  "created_at": "2026-06-30T00:00:00+08:00",
  "updated_at": "2026-06-30T00:00:00+08:00"
}
```

### 6.3 memory_type 语义

| memory_type | 含义 | 默认是否可复用 |
|---|---|---|
| `requirement` | 当前用户需求事实 | 否 |
| `decision` | 用户在当前流程中的选择 | 否 |
| `gap_report` | 当前 Agent 的 gap 结果 | 否 |
| `build_plan` | 基于当前 gap 生成的方案 | 否 |
| `tool_binding` | 某版本工具绑定事实 | 否 |
| `prompt_design` | Prompt 设计事实 | 否 |
| `evaluation_lesson` | 评估后的通用经验 | 可选 |
| `deletion` | 删除审计记录 | 否，audit only |
| `user_preference` | 用户长期偏好 | 是 |

---

## 7. Mem0 使用规范

### 7.1 Mem0 定位

Mem0 只负责语义召回，不负责事实有效性判断。

进入 Mem0 的 Agent Builder 记忆必须携带 metadata：

```json
{
  "scope": "agent_builder_lesson",
  "memory_kind": "evaluation_lesson",
  "ledger_id": "abm_xxx",
  "user_id": "user_xxx",
  "thread_id": "thread_xxx",
  "spec_id": "spec_xxx",
  "version_id": "version_xxx",
  "agent_name": "财报风险信号识别器",
  "lifecycle_status": "active",
  "reusable": "true",
  "valid_from": "2026-06-30T00:00:00+08:00",
  "invalidated_at": ""
}
```

### 7.2 默认召回过滤

所有 Agent Builder 的 Mem0 召回必须默认过滤：

```json
{
  "lifecycle_status": "active"
}
```

如果是新建 Agent，默认禁止召回旧 `spec_id` 的非通用记忆。

允许召回：

```json
{
  "lifecycle_status": "active",
  "reusable": "true",
  "memory_kind": "evaluation_lesson"
}
```

禁止召回：

- 旧 Agent 的 requirement
- 旧 Agent 的 build_plan
- 旧 Agent 的 tool_binding
- 旧 Agent 的 gap_report
- 旧 Agent 的 prompt_design
- `deleted / invalidated / superseded` 记忆

### 7.3 删除策略

删除 Agent 时：

- MongoDB Ledger 保留审计记录，标记为 `deleted / invalidated`。
- Mem0 中对应 `spec_id / version_id / ledger_id` 的向量记忆应物理删除，避免误召回。
- 如果必须保留删除说明，只能存入 MongoDB Ledger，authority = `audit_only`，不进入 Nanobot prompt。

---

## 8. 向量数据库使用规范

### 8.1 定位

向量数据库只作为索引，不作为事实源。

适合索引：

- 工具能力描述
- Skill 文档
- 项目文档
- Prompt 模板
- 外部知识库

### 8.2 使用规则

向量检索结果必须标注：

```json
{
  "source": "vector_index",
  "authority": "candidate",
  "validity": "indexed"
}
```

向量库结果只能说明“可能相关”，不能说明“当前可用”。

工具候选最终必须通过：

- Tool Registry
- MongoDB runtime config
- bindable 状态
- 当前 Agent / 当前版本权限

确认后才能进入方案或生成流程。

### 8.3 防止历史工具绑定污染能力索引

系统能力向量索引（工具描述、Skill 文档）与 Agent 历史绑定必须区分来源：

```json
{
  "source": "system_tool",
  "source": "skill_doc",
  "source": "agent_binding"
}
```

规则：

- 系统能力索引不因 Agent 删除而删除。
- Agent 绑定记录只作为该 Agent / 该版本的上下文，不应泛化为系统能力。
- 新建 Agent 的能力盘点，优先查询 Tool Registry 和系统能力索引，而非历史 Agent 绑定。
- 删除 Agent 时，如果向量库中存在该 Agent 的绑定记录，应将其标记或删除，避免新 Agent 召回时误以为是可用能力。

---

## 9. Redis 使用规范

Redis 只保存短生命周期运行态：

- SSE 连接状态
- 后台任务进度
- 分布式锁
- rate limit
- 临时缓存
- job result cache

Redis 数据必须具备 TTL。

Redis 不能作为以下事实源：

- Agent 是否删除
- Agent 当前版本
- 当前流程阶段
- 当前工具绑定
- 当前 memory 是否有效

如果 Redis 与 MongoDB 冲突，以 MongoDB 为准。

---

## 10. 文件 Memory 处理规范

### 10.1 退出决策链

`MEMORY.md`、`HISTORY.md` 不再直接注入 Agent Builder 的系统 prompt。

文件 Memory 仅用于：

- 人工审计
- debug
- 开发期排查
- 迁移前备份

### 10.2 禁止行为

- 不允许用文件 Memory 判断当前阶段。
- 不允许用文件 Memory 恢复旧 Agent 方案。
- 不允许用文件 Memory 决定工具绑定。
- 不允许将已删除 Agent 的旧内容作为当前需求事实。

---

## 11. Nanobot Context Assembler

### 11.1 新增统一上下文装配器

新增模块建议：

```text
core/embedded_nanobot/context_assembler.py
```

或：

```text
core/embedded_nanobot/agent/context_assembler.py
```

职责：统一收集、过滤、排序并标注进入 Nanobot prompt 的上下文。

### 11.1.1 轻量先行策略

完整 Context Assembler 是长期目标，但第一阶段应立刻落地一个轻量封装：

```text
core/embedded_nanobot/agent/context_injection_policy.py
```

该模块提供：

```python
def build_agent_builder_context_blocks(
    user_message: str,
    thread_context: dict,
    intent_context: dict,
    mode: str = "agent_builder",
) -> list[ContextBlock]:
    ...
```

其职责：

- 决定哪些 block 允许注入当前 prompt。
- 默认排除文件 Memory。
- 对 Mem0 召回强制加 `lifecycle_status=active` 过滤。
- 新建 Agent 时只召回 `reusable=true` 的 lesson。
- 返回每个 block 的 `source / authority / scope / validity`。

这样可以先把散落注入收口到一个地方，后续再演进为完整 Context Assembler。

### 11.2 输入

```json
{
  "user_id": "...",
  "thread_id": "...",
  "user_message": "...",
  "thread_context": {},
  "intent_context": {},
  "tool_selection": {},
  "current_mode": "agent_builder"
}
```

### 11.3 输出

```json
{
  "blocks": [
    {
      "name": "current_thread_state",
      "source": "mongodb",
      "authority": "source_of_truth",
      "scope": "current_thread",
      "validity": "active",
      "content": "..."
    },
    {
      "name": "flow_guidance",
      "source": "flow_controller",
      "authority": "source_of_truth",
      "scope": "current_phase",
      "validity": "active",
      "content": "..."
    },
    {
      "name": "reusable_lessons",
      "source": "mem0",
      "authority": "advisory",
      "scope": "reusable_lesson",
      "validity": "active",
      "content": "..."
    }
  ],
  "audit": {
    "included_memory_ids": [],
    "blocked_memory_ids": [],
    "filters": {}
  }
}
```

### 11.4 装配顺序

```text
1. 当前用户消息
2. 当前线程 thread_context / IntentContext
3. MongoDB live Workshop state
4. Flow Guidance
5. MongoDB Ledger 中 active 的当前 scope 记忆
6. Mem0 active reusable lessons
7. 向量库候选能力
8. Redis 临时任务状态
```

### 11.5 禁止散落注入

以下注入应逐步收敛到 Context Assembler：

- `MEMORY.md` 注入
- project memory guidance
- agent_builder_lesson_guidance
- flow guidance
- intent context block

最终目标：Nanobot prompt 只通过一个统一入口装配上下文。

---

## 12. Agent Builder 流程专用规则

### 12.1 新建 Agent

新建 Agent 时：

允许使用：

- 当前线程用户明确表达的需求
- 当前 thread_context / IntentContext
- active reusable lesson
- 用户偏好
- 项目治理规则
- 当前工具注册表和能力索引

禁止使用：

- 旧 spec_id 的 requirement
- 旧 spec_id 的 build_plan
- 旧 spec_id 的 tool_binding
- 旧 spec_id 的 gap_report
- 旧 spec_id 的 prompt_design
- 已删除 Agent 的任何执行方案
- 文件 Memory 中旧 Agent 的自由文本

如果用户说“方案 A / 方案 B / 确认”等指代不清：

- 只能对应当前线程最近一次 Nanobot 明确给出的选项。
- 如果当前线程没有明确选项，必须追问。
- 禁止从历史 Memory 中猜。

#### 系统 Prompt 硬规则

Agent Builder 的系统 prompt 中必须加入：

```text
关于选项指代的硬规则：
1. 用户提到“方案 A/B/C”“选项 X”“确认”“按这个”等指代性表述时，你只能基于当前线程最近一次你明确给出的选项解释。
2. 如果当前线程没有给出过对应选项，禁止从历史 Memory 或旧 Agent 记录中猜测含义。
3. 无法确定时，必须向用户澄清：“请问你指的是我刚才给出的哪一个方案/选项？”
4. 任何情况下，已删除 Agent 的旧方案、旧工具绑定、旧 gap 结论都不能作为当前选项的依据。
```

### 12.2 修改已有 Agent

修改已有 Agent 时：

- 先查 MongoDB live state。
- 如果 Agent 已删除，不允许恢复旧方案，只能新建。
- 如果版本 active / testing，不允许原地改，必须创建迭代。
- 历史 lesson 只能作为 advisory，不得覆盖当前 live state。

### 12.3 删除 Agent

删除 Agent 时必须触发：

1. Agent Workshop assets 删除或标记删除。
2. Runtime config / tool binding 清理。
3. MongoDB Ledger 中相关记忆标记 `deleted / invalidated`。
4. Mem0 中相关向量记忆物理删除。
5. Redis 相关缓存清理。
6. 文件 Memory 最多追加审计记录，不再参与 prompt。

---

## 13. 日志与可观测性

### 13.1 每次 memory 召回必须记录

日志字段：

```json
{
  "event": "nanobot_memory_recall",
  "thread_id": "...",
  "user_id": "...",
  "mode": "agent_builder",
  "phase": "plan_selection_pending",
  "query_preview": "...",
  "filters": {
    "lifecycle_status": "active",
    "reusable": "true"
  },
  "included": [
    {
      "memory_id": "...",
      "source": "mem0",
      "authority": "advisory",
      "scope": "reusable_lesson",
      "lifecycle_status": "active"
    }
  ],
  "blocked": [
    {
      "memory_id": "...",
      "reason": "deleted_or_invalidated"
    }
  ]
}
```

### 13.2 每次上下文装配必须记录

```json
{
  "event": "nanobot_context_assembled",
  "thread_id": "...",
  "blocks": [
    {
      "name": "flow_guidance",
      "source": "flow_controller",
      "authority": "source_of_truth",
      "chars": 1200
    }
  ],
  "conflict_resolution": []
}
```

---

## 14. 迁移策略

### 14.1 第一阶段：止血

优先完成：

1. Agent Builder 禁止直接注入 `MEMORY.md`。
2. 所有 Agent Builder 记忆走 MongoDB Ledger，不依赖 Mem0。
3. 新建 Agent 禁止召回旧 `spec_id` 的 plan/tool/gap/prompt。
4. 删除 Agent 时清理 MongoDB Ledger 中对应 `spec_id / version_id` 的记忆（标记 invalidated/deleted）。
5. 修改 historical lessons 文案：只能作为反回归教训，不能作为当前需求、阶段或方案。
6. 新增 `context_injection_policy.py` 轻量封装，收口散落注入。
7. 在 Agent Builder 系统 prompt 中加入选项指代硬规则。
8. 把 `thread_context / IntentContext` 持久化治理写进代码，禁止跨轮依赖 contextvar。

本阶段目标：让当前崩溃不再发生。

### 14.2 第二阶段：结构化 Ledger

完成：

1. 新增 `agent_builder_memory_ledger` 集合。
2. 新增 AgentBuilderMemoryService。
3. 写入 requirement / decision / gap / plan / evaluation lesson。
4. 删除 / 迭代 / 发布时更新 lifecycle_status。
5. 召回前先查 MongoDB lifecycle。

### 14.3 第三阶段：统一 Context Assembler

完成：

1. 新增 NanobotContextAssembler。
2. 收敛 runtime / context / memory / flow guidance 的散落注入。
3. 所有 prompt block 都带 `source / authority / scope / validity`。
4. 增加冲突裁决和审计日志。

### 14.4 第四阶段：长期升级

评估引入：

- Zep / Graphiti temporal graph memory
- 更细粒度实体关系：Agent、Version、Tool、Gap、Plan、Evaluation
- valid_at / invalid_at 原生 temporal query

---

## 15. 验收标准

### 15.1 新建 Agent 场景

给定：

- 曾经存在同名 Agent。
- 旧 Agent 已删除。
- 文件 Memory / Mem0 中仍可能存在旧内容。

期望：

- Nanobot 不引用旧 Agent 的方案、工具绑定、gap 报告。
- 用户说“方案 A”时，如果当前线程没有明确方案选项，Nanobot 必须追问。
- 需求确认稿不出现工具候选。
- 用户确认需求后才做 gap 分析。
- 用户选择方案后直接生成，不再重复需求确认。

### 15.2 修改 Agent 场景

给定：

- 当前 Agent 有 active version。
- Mem0 中有历史 lesson。

期望：

- Nanobot 先查 MongoDB live state。
- 历史 lesson 只作为 advisory。
- 不用历史 lesson 覆盖当前工具绑定。

### 15.3 删除 Agent 场景

给定：

- 用户删除 Agent。

期望：

- MongoDB Ledger 标记相关记忆 invalidated / deleted。
- Mem0 中相关 spec/version 记忆被清理。
- Redis 缓存被清理。
- 后续重建同名 Agent 不会召回旧方案。

### 15.4 日志验收

每次 Nanobot 回复前，日志中必须能看到：

- 当前 phase
- 注入了哪些上下文 block
- Mem0 使用了哪些 filters
- 召回了哪些 memory id
- 阻止了哪些 memory id
- 冲突时以哪个 source 为准

### 15.5 自动化测试验收

新增一个回归测试：

```text
Test Case: agent_builder_memory_isolation
```

前置条件：

- 创建 Agent「财报风险信号识别器 v1」。
- 完成需求确认、gap 分析、生成方案。
- 删除该 Agent，并确认清理完成。

操作：

- 新建同名 Agent「财报风险信号识别器」。
- 用户输入："我要一个能识别财报风险信号的助手，重点关注商誉减值、应收账款异常和现金流恶化。"
- 用户输入："确认"
- 用户输入："方案 A"

断言：

- Nanobot 在需求确认阶段不引用旧 Agent 的工具候选。
- Nanobot 在能力盘点阶段生成新的 gap_report。
- 当用户说"方案 A"但当前线程无明确选项时，Nanobot 追问而非执行旧方案。
- 日志中 `nanobot_memory_recall` 事件的 `blocked` 列表必须非空。
- `thread_context.intent.spec_id` 与旧 Agent 不同。

---

## 16. 推荐实施优先级

| 优先级 | 任务 | 说明 |
|---|---|---|
| P0 | 禁止 Agent Builder 直接注入文件 Memory | 立即降低旧 Agent 污染风险 |
| P0 | Agent Builder 记忆全部走 MongoDB Ledger，不依赖 Mem0 | 减少存储依赖，精确过滤 |
| P0 | 删除 Agent 清理 MongoDB Ledger 相关记忆 | 防止同名重建污染 |
| P0 | 新增 `context_injection_policy.py` 轻量封装 | 收口散落注入，先止血 |
| P0 | Agent Builder 系统 prompt 加选项指代硬规则 | 防止模型乱猜 |
| P0 | thread_context / IntentContext 持久化治理 | 防止跨轮状态丢失 |
| P1 | 新增 MongoDB Ledger 集合 | 建立生命周期事实源 |
| P1 | 新增 AgentBuilderMemoryService | 收敛业务规则 |
| P1 | 增加 memory recall 审计日志 | 方便排查 |
| P1 | 轻量 Context Assembler 覆盖 Agent Builder 路径 | 统一主要入口 |
| P2 | 完整 NanobotContextAssembler | 统一所有入口 |
| P2 | 向量库来源标签与清理机制 | 防止历史绑定污染能力索引 |
| P3 | 评估 Zep / Graphiti | 长期 temporal graph memory 升级 |

---

## 17. 结论

Agent Builder 的可靠性不能依赖 LLM 自行理解一大段历史文本。

正确架构应该是：

```text
MongoDB 管事实和生命周期 + Agent Builder 记忆主存储
向量库管能力 / 文档索引
Redis 管短期运行态
Mem0 可选，仅通用对话记忆
文件 Memory 退出决策链
NanobotContextAssembler 统一装配上下文
```

这样 Nanobot 才能明确知道：

- 哪些是当前事实。
- 哪些是历史经验。
- 哪些是废弃内容。
- 哪些只是候选能力。
- 冲突时应该相信谁。

这是 Agent Workshop 可靠进入生产级的前置条件。
