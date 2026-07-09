# Hermes Agent 替代 nanobot 评估报告

> 评估日期：2026-06-30
> 评估范围：Agent Builder（Agent Workshop）的对话式构建流程
> 对照对象：当前 nanobot 方案（一周内遇到的 8 类问题）

---

## 1. 结论先行

**Hermes 能解决 6/8 类问题，但不解决 2/8 类问题。换 Hermes 意味着：删掉 ~2000 行基础设施代码，保留 ~3000 行业务逻辑代码（工具、状态机、gap 分析）。**

| 问题 | nanobot 现状 | Hermes 方案 | 可删代码？ |
|---|---|---|---|
| contextvar 跨异步回退 → intent 丢失 | 模块级 dict + MongoDB 双重兜底 | SQLite 会话状态，无 contextvar 依赖 | 是 |
| 跨轮上下文丢失 | 手动写 pending_question，工具易遗漏 | 会话历史自动恢复 + FTS5 跨轮搜索 | 是 |
| 旧 Agent 记忆污染新建 | InjectionPolicy 手动过滤 + MEMORY.md 禁止 | memory 工具可 add/replace/remove，Agent 自管理 | 部分 |
| 工具调用后状态未同步 | 每个工具手动更新 intent | Agent loop 内置，工具结果自动追加到历史 | 是 |
| 阶段流转依赖 LLM 自觉 | 手写 FlowController + PhaseRule | 不内置，仍需业务层实现 | 否 |
| 多存储边界混乱 | MongoDB + Redis + Mem0 + 向量 + 文件 | SQLite 统一存储 | 是 |
| 对话摘要机制缺失 | 刚设计，未实现 | 每轮后自动回顾 + 写入 MEMORY.md | 是 |
| 业务逻辑（Agent Builder 流程） | FlowController + 13 个工具 | 需要自定义工具/Skill 实现 | 否 |

---

## 2. 逐问题详细分析

### 2.1 contextvar 跨异步回退

**问题**：Python contextvar 在 LangChain/LLM provider 异步调用链中被静默回退，导致 intent 丢失。

**nanobot 方案**：模块级 `_nanobot_intents_by_thread` dict + MongoDB 持久化，双重兜底。约 150 行代码。

**Hermes 方案**：内置。Hermes 使用 SQLite 存储会话状态，通过 `conversation_id` 加载，不依赖 Python 线程局部变量。`run_conversation()` 自动加载历史。

**结论**：✅ 彻底解决。Hermes 的会话管理是框架级，不依赖 contextvar。

---

### 2.2 跨轮上下文丢失

**问题**：Nanobot 问"选项 A 为主，保留 B 灵活性，你觉得呢"，用户回"可以"，第二轮 LLM 不知道用户在对什么说"可以"。

**nanobot 方案**：手动在 `prepare_agent_requirement_intake` 中写 `pending_question` + `pending_options`，在 `build_flow_guidance_block` 中注入"待确认上下文"块。约 80 行代码，且依赖工具记得写。

**Hermes 方案**：内置。Hermes 的会话记忆（Session Memory）在 SQLite 中存储完整对话历史，包括工具调用结果。当会话恢复时，自动加载历史。同时，每轮对话后 Hermes 会回顾并写入持久记忆（MEMORY.md），形成可检索的摘要。

**结论**：✅ 彻底解决。框架级会话恢复，不需要手动管理 pending 状态。

---

### 2.3 旧 Agent 记忆污染新建

**问题**：用户删除了旧 Agent，但 MEMORY.md 和 Mem0 中仍有旧内容，新建同名 Agent 时被污染。

**nanobot 方案**：InjectionPolicy 禁止 Agent Builder 注入 MEMORY.md + Mem0。MongoDB Ledger 标记删除。约 200 行代码。

**Hermes 方案**：部分解决。Hermes 的 MEMORY.md 是 Agent 自管理（通过 `memory` 工具 add/replace/remove），不是人工维护。但 Hermes 采用的是单 Agent 多项目模式，不是多 Agent 工作坊模式。如果要用 Hermes 做 Agent Builder，需要：
- 每个创建的 Agent 作为一个独立项目/workspace
- 通过 `memory` 工具管理"当前正在构建的 Agent"的记忆
- 旧 Agent 的记忆可以通过 `memory remove` 清理

**关键差异**：Hermes 的"记忆"是指"用户偏好 + 项目事实 + 学到的教训"，不是"旧 Agent 的构建方案"。在 Hermes 模式中，构建 Agent 是一个"任务"，不是"记忆"。任务完成后，Hermes 会自动提炼 Skill，但不是把构建方案当记忆永久保存。

**结论**：✅ 部分解决。Hermes 的 memory 语义更清晰（用户偏好 vs 项目事实 vs 技能），污染风险远低于 MEMORY.md 整段注入。但多 Agent 管理仍需业务层实现。

---

### 2.4 工具调用后状态未同步

**问题**：工具内部更新了 intent，但下一轮 LLM 看不到。

**nanobot 方案**：每个工具手动调用 `update_intent_context_in_thread`，模块级 dict 存储，MongoDB 持久化。

**Hermes 方案**：内置。Hermes 的 agent loop 自动将工具调用结果追加到对话历史（OpenAI 标准 message 格式）。工具执行后，结果作为 `tool` role message 进入历史，下一轮 LLM 自动看到。

```python
# Hermes 内部格式
{"role": "assistant", "content": None, "tool_calls": [...]}
{"role": "tool", "tool_call_id": "...", "content": "{...}"}
{"role": "assistant", "content": "最终回复"}
```

**结论**：✅ 彻底解决。框架级工具结果同步，不需要手动管理。

---

### 2.5 阶段流转依赖 LLM 自觉

**问题**：Agent Builder 有 7 个阶段（idle → exploring → draft_preparing → requirement_confirmation_pending → capability_check → plan_selection_pending → generating），LLM 经常跳过阶段或乱跳。

**nanobot 方案**：手写 FlowController + PhaseRule + FlowPhase 枚举 + 每个阶段的 allowed_tools / forbidden_tools / transitions。约 400 行代码。

**Hermes 方案**：不内置。Hermes 是通用 Agent，没有"Agent Builder 工作流"的概念。阶段流转仍需业务层实现。

**但 Hermes 提供了 Skill 系统**：可以将多步骤流程定义为 Skill，例如：
```markdown
# agent-builder-workflow
1. 需求采集 → prepare_agent_requirement_intake
2. 需求确认 → prepare_agent_generation_confirmation  
3. 能力盘点 → analyze_agent_workshop_gaps
4. 方案生成 → propose_agent_build_plans
5. 方案选择 → 等待用户选择
6. 执行生成 → generate_confirmed_candidate_agent
```

Skill 文件会被注入到系统 prompt 中，引导 Agent 按步骤执行。

**结论**：❌ 不解决。阶段状态机仍需业务层实现。但 Skill 系统可以替代部分 FlowController 的功能（引导流程），且比手写 PhaseRule 更灵活。

---

### 2.6 多存储边界混乱

**问题**：MongoDB、Redis、Mem0、向量库、文件 Memory 五种存储都在向 Nanobot 注入信息，职责不清。

**nanobot 方案**：InjectionPolicy + 存储权责表 + context assembler 设计。约 300 行代码 + 设计文档。

**Hermes 方案**：内置简化。Hermes 使用 SQLite 作为统一存储：
- 会话历史 → SQLite + FTS5
- 持久记忆 → `~/.hermes/memories/MEMORY.md` + `USER.md`
- 技能 → `~/.hermes/skills/*.md`
- 向量搜索 → ChromaDB（可选，用于 episodic memory）

不再有 MongoDB、Redis、Mem0、向量库的五路混战。存储架构清晰简单。

**结论**：✅ 彻底解决。Hermes 用 SQLite 统一存储，不需要五套存储系统。

---

### 2.7 对话摘要机制缺失

**问题**：每轮对话后没有自动生成摘要，下一轮 LLM 只能看到原始对话历史，没有结构化上下文。

**nanobot 方案**：刚设计，未实现。计划在每轮后自动生成摘要并注入下一轮。

**Hermes 方案**：内置。Hermes 的 memory 系统在每轮对话后自动：
1. 回顾对话内容
2. 提取值得保留的信息（偏好、发现、教训）
3. 写入 MEMORY.md（有 2,200 字符限制）
4. 通过 periodic nudge 机制提醒 Agent 定期回顾

同时，Hermes 的 context files 系统（`CONTEXT.md`、`CONVENTIONS.md`）会在每轮 session 开始时作为快照注入系统 prompt。

**结论**：✅ 彻底解决。框架级自动摘要和记忆管理。

---

### 2.8 业务逻辑不可替代

**问题**：Agent Builder 的核心业务逻辑——工具（prepare_agent_requirement_intake、analyze_agent_workshop_gaps 等）、gap 分析、方案生成、Agent 配置写入——这些是 TradingAgentsCN 特有的。

**结论**：❌ 不解决。Hermes 不提供这些业务逻辑。需要作为自定义工具或 Skill 实现。

---

## 3. 迁移成本估算

### 3.1 可删除的代码

| 模块 | 行数 | 说明 |
|---|---|---|
| `core/embedded_nanobot/agent_builder_flow.py` | ~800 | FlowController + PhaseRule + 状态机 |
| `core/embedded_nanobot/intent_context.py` | ~300 | IntentContext + IntentStage |
| `core/embedded_nanobot/agent/context_injection_policy.py` | ~200 | InjectionPolicy |
| `core/embedded_nanobot/agent/context.py` 中的 MEMORY.md 注入 | ~50 | 文件 memory 注入 |
| `core/embedded_nanobot/runtime.py` 中的 session/memory 管理 | ~300 | 会话管理 + 记忆召回 |
| `core/tools/context.py` 中的模块级 intent 存储 | ~100 | contextvar 兜底 |
| `app/services/embedded_nanobot_service.py` 中的 intent 持久化 | ~150 | 意图持久化治理 |
| **合计** | **~1900** | |

### 3.2 需要保留/重写的代码

| 模块 | 行数 | 说明 |
|---|---|---|
| `core/tools/implementations/agent_builder/nanobot_agent_builder_tools.py` 中的工具逻辑 | ~3000 | 13 个 Agent Builder 工具，需适配为 Hermes 工具 |
| `app/services/agent_workshop_service.py` | ~5000 | Agent 工坊核心服务，不变 |
| `app/services/agent_builders/hermes_builder.py` | ~200 | Provider 实现，需重写 |

### 3.3 新增代码

| 模块 | 行数 | 说明 |
|---|---|---|
| Hermes 工具注册（13 个 Agent Builder 工具） | ~300 | 工具函数本身不变，注册方式不同 |
| Hermes Skill 文件（Agent Builder 工作流定义） | ~200 | SKILL.md 格式的流程定义 |
| Hermes 安装/配置 | ~50 | Docker 或本地安装 |
| **合计** | **~550** | |

### 3.4 总成本

```text
删除：~1900 行
新增：~550 行
重写：~300 行（工具注册）
保留：~8000 行（业务逻辑不变）

净减少：~1050 行代码
```

---

## 4. 风险分析

### 4.1 Hermes 本身的风险

| 风险 | 等级 | 缓解 |
|---|---|---|
| Hermes 是新兴项目（2026.02 发布），API 可能不稳定 | 中 | 通过 Provider 抽象隔离，换版本只需改 Provider |
| Hermes 的 memory 系统使用 MEMORY.md（与 nanobot 类似），但管理方式不同 | 低 | Hermes 的 Agent 自管理 + 字符限制，比人工维护可靠 |
| Hermes 默认使用 SQLite，不适合高并发 | 低 | Agent Builder 是单用户对话，不需要高并发 |
| Hermes 的 Skill 系统是 MD 文件，不是 Python 代码 | 中 | 复杂工具仍需 Python 实现，Skill 只是流程引导 |

### 4.2 迁移风险

| 风险 | 等级 | 缓解 |
|---|---|---|
| 工具函数需要适配 Hermes 的工具注册机制 | 低 | 工具函数本身是纯 Python，只需改注册方式 |
| 前端 AgentStudio 需要适配 Hermes 的 SSE 流式格式 | 中 | 在前端 API 层做适配 |
| 从 MongoDB thread_context 迁移到 Hermes session | 中 | 需设计迁移脚本，或保留 MongoDB 做业务状态 |

### 4.3 Hermes 不适合的场景

| 场景 | 原因 |
|---|---|
| 多 Agent 并行工作坊 | Hermes 是单 Agent 多项目模式，不是多 Agent 工作坊 |
| 高并发 Agent 构建 | Hermes 默认单实例，SQLite 不适合高并发 |
| 复杂的发布/版本管理 | 这些是业务逻辑，Hermes 不提供 |

---

## 5. 最终建议

### 5.1 换不换？

**换。** 理由：

1. **6/8 类问题在 Hermes 中是框架级解决的**，不需要自己写基础设施代码。
2. **减少 ~1000 行维护代码**，且这些代码是最容易出 bug 的基础设施层。
3. **Provider 抽象层已建好**，切换成本可控。
4. **业务逻辑（工具、gap 分析、方案生成）完全保留**，不需要重写。

### 5.2 怎么换？

```
阶段 1（1-2 天）：Hermes 安装 + 基础对接
  - 安装 Hermes Agent
  - 实现 HermesBuilderProvider（替换 EmbeddedNanobotBuilderProvider）
  - 注册 13 个 Agent Builder 工具
  - 验证：单轮对话能调用工具

阶段 2（2-3 天）：工作流 Skill 定义
  - 编写 Agent Builder 工作流 SKILL.md
  - 定义 7 阶段流程 + 允许的工具 + 阶段转换条件
  - 验证：完整 7 步流程能走通

阶段 3（1-2 天）：前端适配 + 清理
  - 前端 AgentStudio 适配 Hermes SSE 格式
  - 删除 nanobot 基础设施代码（FlowController、IntentContext、InjectionPolicy 等）
  - 保留 MongoDB 做业务状态（Agent Spec、Version、Config）
  - 验证：完整新建 Agent 流程

总计：4-7 天
```

### 5.3 保留什么？

| 保留 | 原因 |
|---|---|
| MongoDB Agent Spec / Version / Config | 业务数据，与 Agent Loop 无关 |
| 13 个 Agent Builder 工具函数 | 纯业务逻辑，直接复用 |
| 前端 AgentStudio | 只改 API 适配层 |
| 后端 AgentWorkshopService | 核心业务逻辑不变 |
| AgentBuilderProvider 抽象层 | 已建好，直接实现 HermesBuilderProvider |

### 5.4 删除什么？

| 删除 | 原因 |
|---|---|
| FlowController / PhaseRule / FlowPhase | Hermes Skill 替代 |
| IntentContext / IntentStage | Hermes session 替代 |
| InjectionPolicy | Hermes 统一存储，不需要策略 |
| MEMORY.md 注入逻辑 | Hermes 自管理记忆 |
| 模块级 `_nanobot_intents_by_thread` | Hermes SQLite 替代 |
| contextvar 兜底逻辑 | Hermes 无 contextvar 依赖 |
| Mem0 集成 | Hermes 不需要 |