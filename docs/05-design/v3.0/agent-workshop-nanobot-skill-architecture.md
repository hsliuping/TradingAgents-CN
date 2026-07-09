# Agent 工坊 + Nanobot + Skill 系统架构说明

> 本文档记录当前 Agent 工坊、Embedded Nanobot、Skill 生成系统、工具注册表、Runtime Agent 之间的系统关系，避免后续开发中遗忘上下文、职责边界和关键防漂移机制。

## 1. 总体定位

当前系统不是单一的“聊天生成 Agent”流程，而是由多个协同层组成：

```text
用户 / Agent Studio
    ↓
Embedded Nanobot（对话式编排者）
    ↓
IntentContext（结构化任务上下文 / 外部工作记忆）
    ↓
AgentBuilderFlowController（状态机驱动层）           ← 新增
    ↓
Agent Workshop（规格、版本、缺口、测试、发布治理）
    ↓
Skill Generation（为缺口生成可调用能力）
    ↓
Tool Registry / Capability Index（工具与能力索引）
    ↓
Universal Agent Runtime（真正运行 Agent 并调用工具）
```

核心原则：

1. **Agent Workshop 是治理中心**：负责 Agent 规格、版本、缺口分析、提示词模板、测试评估、发布。
2. **Nanobot 是交互编排者**：负责理解用户意图、调用 Workshop/Skill/Runtime 工具，但不能随意改写真实状态。
3. **IntentContext 是防漂移的结构化上下文**：负责记录当前 Agent、当前意图、阶段、子任务和下一步。
4. **Skill 是能力补齐单元**：用于补齐 Agent 的 blocking gap，不是最终目标。
5. **Runtime Agent 是执行载体**：最终根据配置、提示词和工具绑定执行分析任务。

---

## 2. 主要模块职责

### 2.1 Agent Studio

前端交互入口，用户在这里：

- 创建 Agent
- 选择左侧已有 Agent
- 与 Nanobot 沟通需求
- 查看 Agent 构建/测试/发布状态
- 触发测试、迭代、发布

关键要求：

- 当用户选中某个 Agent 后，后续聊天默认都指向该 Agent。
- 前端需要传递 `thread_context`，至少包含：

```json
{
  "spec_id": "agent_financial_risk_detector",
  "spec_name": "财报风险信号识别器",
  "version_id": "agent_financial_risk_detector_v1",
  "workshop_session_id": "..."
}
```

---

### 2.2 Embedded Nanobot

Nanobot 是对话层和工具编排层，位于：

- `core/embedded_nanobot/runtime.py`
- `app/services/embedded_nanobot_service.py`
- `core/tools/implementations/agent_builder/nanobot_agent_builder_tools.py`

职责：

1. 接收用户自然语言。
2. 读取聊天历史、项目记忆、IntentContext。
3. 选择工具并调用。
4. 将工具结果整理给用户。
5. 在关键工具执行后更新 IntentContext。

Nanobot 不能被视为权威状态源。它可以推理，但最终写数据库前必须经过工具层/Workshop 层校验。

---

### 2.3 IntentContext

IntentContext 是给 Nanobot 增加的“外部结构化工作记忆”，位于：

- `core/embedded_nanobot/intent_context.py`

它存储在：

```text
embedded_nanobot_threads.thread_context.intent
```

并在每轮对话中通过 `contextvars` 注入执行链。

#### 2.3.1 解决的问题

历史问题：

- 用户要求创建“财报风险信号识别器”，多轮沟通后 Nanobot 误生成“巴菲特价值筛选官”。
- 选中某个 Agent 后问“现在什么进度”，Nanobot 返回全局所有 Agent 的进度。
- 为某个 Agent 创建 Skill 后，Nanobot 忘记 Skill 是为哪个 Agent 的哪个缺口创建的。
- 删除失败 Agent 后重建同名 Agent，Nanobot 复用旧记忆中的方案。

IntentContext 的目标：

```text
让 LLM 可以推理，但不能靠猜来决定当前对象。
系统必须显式告诉它：当前在做哪个 Agent，处于什么阶段，下一步是什么。
```

#### 2.3.2 当前字段

```json
{
  "spec_id": "agent_financial_risk_detector",
  "spec_name": "财报风险信号识别器",
  "action": "create_agent | iterate_agent | test_agent | resolve_gap | check_status",
  "stage": "draft_preparing | gap_resolving | building | testing | publishing",
  "intent_summary": "创建一个识别财报风险信号的助手，重点关注商誉减值、应收账款异常和现金流恶化",
  "active_subtask": "为商誉减值缺口创建 Skill",
  "next_action": "Skill 验证完成后，回到父 Agent 重新构建和真数据测试",
  "task_stack": [
    {
      "type": "agent",
      "id": "agent_financial_risk_detector",
      "name": "财报风险信号识别器",
      "status": "testing",
      "parent_id": ""
    },
    {
      "type": "gap",
      "id": "session_xxx:gap_1",
      "name": "商誉减值风险专项评估",
      "status": "completed",
      "parent_id": "agent_financial_risk_detector"
    },
    {
      "type": "skill",
      "id": "get_goodwill_analysis",
      "name": "商誉分析工具",
      "status": "completed",
      "parent_id": "agent_financial_risk_detector"
    }
  ],
  "linked_skills": [
    {
      "skill_id": "get_goodwill_analysis",
      "skill_name": "商誉分析工具",
      "gap": "商誉减值风险专项评估",
      "status": "completed"
    }
  ],
  "agents_discussed": []
}
```

#### 2.3.3 注入到 System Prompt

在 `runtime.py` 中，Nanobot 每轮执行前会注入：

```text
## Current Intent Context
当前焦点 Agent：财报风险信号识别器
当前意图：解决能力缺口
当前阶段：gap_resolving
当前子任务：为商誉减值缺口创建 Skill
下一步动作：回到父 Agent 继续 build/test/iterate

当前任务链：
- [agent] 财报风险信号识别器 status=testing
- [gap] 商誉减值风险专项评估 status=completed ← parent=agent_financial_risk_detector
- [skill] get_goodwill_analysis status=completed ← parent=agent_financial_risk_detector
```

并附加约束：

- 所有写操作必须只操作当前 `spec_id`。
- 如果 LLM 工具参数里的 `agent_id/spec_id` 与当前上下文不一致，拒绝执行。
- 如果当前正在补 Skill，完成后必须回到父 Agent，而不是把 Skill 当最终目标。
- 回答进度时必须包含父 Agent 状态、当前子任务状态、下一步动作。

#### 2.3.4 持久化机制

执行流程：

```text
EmbeddedNanobotService.chat()
    ↓ set_current_assistant_thread_context(thread_context)
Nanobot runtime / tools 执行
    ↓ 工具调用 update_intent_context_in_thread()
contextvar 中 thread_context.intent 被更新
    ↓
EmbeddedNanobotService.persist_chat_turn()
    ↓ 读取 get_current_assistant_thread_context()
    ↓ 持久化最新 thread_context 到 embedded_nanobot_threads
```

关键点：

- 不能只更新当前 turn 的 contextvar。
- 必须在保存聊天时写回 `embedded_nanobot_threads.thread_context`。
- 否则下一轮会丢失当前 Agent/子任务关系。

---

## 3. Agent Workshop

Agent Workshop 是 Agent 生命周期的治理层，主要由：

- `app/services/agent_workshop_service.py`
- MongoDB collections:
  - `agent_workshop_specs`
  - `agent_workshop_versions`
  - `agent_workshop_sessions`
  - `prompt_templates`

组成。

### 3.1 核心实体

#### AgentSpec

表示 Agent 的规格：

- `spec_id`
- `name`
- `primary_goal`
- `domain`
- `input_contract`
- `output_contract`
- `capability_requirements`
- `latest_session_id`

#### AgentVersion

表示某个版本：

- `version_id`
- `spec_id`
- `required_tools`
- `required_capabilities`
- `prompt_template_ref`
- `evaluation_policy`
- `status`

#### WorkshopSession

表示一次工坊会话：

- `session_id`
- `spec_id`
- `current_spec_snapshot`
- `gap_report`
- `tooling_plan`
- `messages`
- `phase`

### 3.2 生命周期

```text
需求澄清
  ↓
create_nanobot_draft / start_session
  ↓
AgentSpec + WorkshopSession
  ↓
analyze_gaps
  ↓
generate_tooling_plan
  ↓
build_version
  ↓
debug_version / run_real_data_test
  ↓
evaluate_version
  ↓
iterate_version 或 publish_version
```

### 3.3 Workshop 与 Runtime 的工具同步

历史问题：

- Workshop 的 `required_tools` 与 Runtime 的 `effective_tools` 不一致。
- Runtime 已绑定 `get_financial_risk_factors`，但 Workshop 测试不使用。

当前原则：

1. build/debug/test 时必须合并：

```text
version.required_tools
+ runtime_config.effective_tools
+ tooling_contract.required_tools
+ gap resolved tools
```

2. 写 Runtime config 时不能单向覆盖已有工具。
3. External Skill 和 builtin tool 都必须进入 Capability Index，供工具选择和缺口分析使用。

---

## 4. Skill 系统

Skill 系统用于补齐 Agent 的能力缺口。

相关模块：

- `app/services/skill_generation_service.py`
- `core/tools/external_skill_loader.py`
- `core/tools/config.py`
- `app/services/capability_index_service.py`

### 4.1 Skill 的定位

Skill 不是 Agent 的替代品，而是 Agent 的能力单元。

例如：

```text
父 Agent：财报风险信号识别器
缺口：商誉减值风险指标计算
Skill：get_goodwill_analysis / goodwill_impairment_risk_metrics
作用：补齐该缺口
完成后：回到父 Agent 重新 build/test/evaluate
```

### 4.2 Skill 生成流程

```text
Workshop gap_report.blocking_gaps
    ↓
resolve_agent_workshop_blocking_gaps
    ↓
SkillGenerationService 创建 skill session
    ↓
生成代码 / 沙箱验证 / 参数 schema / expected output
    ↓
External Skill 注册
    ↓
Capability Index 同步
    ↓
Workshop 重新分析 gap / 重新生成工具计划 / build version
```

### 4.3 Skill 元数据

为了避免 LLM 误判工具角色，Skill 和 Tool 都应包含角色元数据：

```json
{
  "capability_tags": ["goodwill_impairment", "financial_risk"],
  "tool_role_hint": "primary | specialized | supporting | generic | fallback",
  "output_shape": "structured_metrics | report | flags",
  "preferred_for": ["goodwill_impairment"],
  "not_replacement_for": ["accounts_receivable_anomaly"]
}
```

治理要求：

- `get_financial_risk_factors` 这类风险因子工具应作为风险分析 Agent 的主入口。
- `get_balance_sheet_analysis`、`get_cashflow_analysis` 是 supporting，不能替代风险因子工具。
- 如果工具不返回商誉，不应让 LLM 猜它能返回商誉。

---

## 5. Tool Registry 与 Capability Index

### 5.1 Tool Registry

定义 builtin tools 的元数据，位置：

- `core/tools/config.py`

负责描述：

- 工具名称
- 参数
- 使用场景
- 不适用场景
- 返回格式
- 角色元数据

### 5.2 External Skill Loader

负责加载数据库中的 External Skill，注册成可调用工具。

位置：

- `core/tools/external_skill_loader.py`

### 5.3 Capability Index

负责把 builtin tool、external skill、MCP tool 等统一索引，供检索和 gap 分析使用。

位置：

- `app/services/capability_index_service.py`

Capability Index 需要消费并保留：

- `capability_tags`
- `tool_role_hint`
- `output_shape`
- `preferred_for`
- `not_replacement_for`

---

## 6. Runtime Agent

Runtime Agent 是最终执行任务的实例。

相关模块：

- `core/agents/universal.py`
- `core/agents/factory.py`
- `agent_configs`
- `prompt_templates`

执行时依赖：

```text
Agent Config
+ Prompt Template
+ Tool Bindings
+ Runtime state
+ prompt_overrides（调试时）
```

### 6.1 Debug/Test 的关键要求

debug/test 不能只看 `version.required_tools`，还必须合并 Runtime config 的 `effective_tools`。

否则会出现：

```text
Runtime 说已绑定 get_financial_risk_factors
但测试实际不调用它
```

### 6.2 Prompt Template 版本关系

不同 AgentVersion 应该拥有不同的 `debug_template_id / prompt_template_ref.template_id`。

原则：

```text
v1 → template_A
v2 → template_B
```

不能让 v1/v2 共用同一个模板内容，除非明确是同一个版本。

调试时如果传入 `prompt_overrides_json`：

1. Runtime 当轮立即使用 override。
2. 同步写回当前版本绑定的 template。
3. 后续不带 override 时，也应读取最新模板。

---

## 7. 防漂移机制

### 7.1 防 Agent 漂移

问题：

```text
用户正在创建 A，LLM 工具参数却传了 B。
```

解决：

- IntentContext 注入当前 `spec_id`。
- 写操作前校验工具参数中的 `agent_id/spec_id`。
- 不一致时返回 `intent_drift_detected`，拒绝写库。

### 7.2 防名称漂移

问题：

```text
已有 spec_id=agent_financial_risk_detector
LLM 传入 agent_name=巴菲特价值筛选官
```

解决：

- 如果已有 Spec 的 name 非空，则拒绝 LLM 重命名。
- 保留已有 name，并写 warning 日志。

### 7.3 防记忆复用错误

问题：

```text
删除失败 Agent 后，新建同名 Agent，LLM 从 MEMORY.md 复用旧方案。
```

解决：

- 删除 Agent 时，在 MEMORY.md/HISTORY.md 顶部写入“已删除 Agent — 严禁复用”声明。
- Runtime 构建 Prompt 时检测同名删除块，注入 Deleted Agent Warning。

### 7.4 防子任务迷路

问题：

```text
为 Agent 创建 Skill 后，Nanobot 忘记回到父 Agent。
```

解决：

- IntentContext 记录 `task_stack` 和 `linked_skills`。
- Prompt 明确说明 Skill 是为父 Agent 的 gap 服务。
- `next_action` 明确指向回到父 Agent build/test/iterate。

---

## 8. AgentBuilderFlowController（状态机驱动层）

> 这是 IntentContext 的补充层。IntentContext 记录"现在做什么"，FlowController 规定"现在能做什么、不能做什么、下一步去哪"。
>
> 核心文件：`core/embedded_nanobot/agent_builder_flow.py`

### 8.1 解决的问题

在 FlowController 之前，Nanobot 靠分散的规则和工具元数据猜测下一步，导致：

- 自动构建成功后仍然调用 `analyze_agent_workshop_gaps`（重复缺口检查）
- 确认阶段就尝试直接生成
- 测试未通过就尝试发布
- Skill 生成后不知道要回到父 Agent

FlowController 的核心原则：

> **让 Nanobot 在框架内自主行事，而不是随意发挥。**

### 8.2 状态机全图

```text
IDLE ──→ EXPLORING ──→ CAPABILITY_CHECK ──→ DRAFT_PREPARING ──→ CONFIRMATION_PENDING
                                                                         │
                                                                    用户确认
                                                                         │
                                                                         ▼
                                                                    GENERATING
                                                                         │
                                                       ┌──── auto-build 成功 ────┐
                                                       │                         │
                                                READY_TO_BUILD              BUILDING ─────────────────────────────┐
                        │                                                                    │
                   有 blocking gap                                                       无 gap
                        │                                                                    │
                        ▼                                                                    ▼
                  GAP_RESOLVING ──→ BUILDING                                            TESTING
                        │              │                                                    │
                   补齐 Skill     rebuild                                              run test
                        │              │                                                    │
                        └──────────────┘                                                    │
                                                                                            ▼
                                                                                      EVALUATING
                                                                                      │    │    │
                                                                                    pass  │  revise
                                                                                      │    │    │
                                                                                      ▼    │    ▼
                                                                                 PUBLISHING │ ITERATING
                                                                                      │         │
                                                                                      ▼         │
                                                                                 PUBLISHED     │
                                                                                      └─────────┘
                                                                                   回到 BUILDING
```

### 8.3 每个阶段做什么 / 不做什么

| 阶段 | 能做 | 不能做 |
|---|---|---|
| **IDLE** | search_capabilities, inspect_* | analyze_gaps, build, test, publish, generate_confirmed |
| **EXPLORING** | search_capabilities, inspect_* | analyze_gaps, build, test, publish, generate_confirmed, prepare_confirmation |
| **CAPABILITY_CHECK** | search_capabilities, inspect_* | generate_confirmed, analyze_gaps, build, test, publish |
| **DRAFT_PREPARING** | prepare_confirmation, search_capabilities | generate_confirmed, analyze_gaps, build, test, publish |
| **CONFIRMATION_PENDING** | generate_confirmed | analyze_gaps, build, test, publish, iterate |
| **GENERATING** | generate_confirmed (仅一次) | analyze_gaps, build, test, publish |
| **READY_TO_BUILD** | build_version, inspect | analyze_gaps, test, publish, generate_confirmed |
| **BUILDING** | real_data_test, debug, inspect, resolve_gaps | **analyze_gaps**（已内部完成）, **build_version**（已构建）, generate_confirmed |
| **TESTING** | real_data_test, debug, evaluate, iterate | generate_confirmed, build（除非迭代） |
| **EVALUATING** | real_data_test, debug, iterate, publish | generate_confirmed, build, analyze_gaps |
| **GAP_RESOLVING** | resolve_gaps, search_capabilities, inspect | real_data_test, publish, generate_confirmed |
| **ITERATING** | iterate, debug, test | publish, generate_confirmed |
| **PUBLISHING** | publish_version | build, test, iterate, analyze_gaps, resolve_gaps |
| **PUBLISHED** | inspect (只读) | 所有写操作 |

### 8.4 System Prompt 注入格式

每轮对话，当 IntentContext 有 `spec_id` 时，自动注入：

```markdown
## 🔒 Agent Builder 流程约束（必须遵守）

当前阶段：版本已构建：自动构建完成，准备测试
当前 Agent：财报风险信号识别器
用户目标：创建财报风险信号识别 Agent，重点关注商誉、应收、现金流

✅ 当前阶段可以调用的工具：
  - run_agent_workshop_real_data_test
  - debug_agent_workshop_version
  - inspect_agent_workshop_assets

⭐ 推荐下一步：调用 run_agent_workshop_real_data_test

🚫 严禁在当前阶段调用以下工具：
  - ❌ analyze_agent_workshop_gaps
    （缺口分析已在自动构建阶段完成或不需要）
  - ❌ build_agent_workshop_version（已构建过）
  - ❌ generate_confirmed_candidate_agent（已生成过）

📋 阶段约束说明：
  - 🚫 严禁再次调用 analyze_agent_workshop_gaps，这会让用户感觉在重复检查。
  - 如果构建时发现 blocking gap，直接进入 GAP_RESOLVING。
  - 如果无 gap，下一步直接做 run_agent_workshop_real_data_test。
```

### 8.5 实现要点

1. **状态源**：从 `IntentContext.stage` 推导，结合 `has_blocking_gaps` / `evaluation_status` 覆写派生状态
2. **注入时机**：`runtime.py` 的 `handle_message` 中，紧跟 `spec_focus_guidance` 之后
3. **注入条件**：仅当 `thread_context.spec_id` 非空时触发，不影响普通聊天
4. **工具更新**：关键动作（如 `generate_confirmed_candidate_agent`）完成后更新 `IntentContext.stage` 为正确的下一阶段
5. **Gap 分析基础**：`build_version` 对所有 spec（含 nanobot 来源）运行真实 gap 分析，不再用空 `AgentWorkshopGapAnalysis()` 跳过。这保证了 FlowController 的 `BUILDING` 阶段说"gap 已内部完成"有事实基础。

### 8.6 与 IntentContext 的关系

```text
IntentContext:     记录当前事实（谁、做什么、什么阶段、下一步）
FlowController:    定义当前规则（允许什么、禁止什么、只走哪条路径）

两者协作：
  IntentContext.stage = "building"
  FlowController 查表 → 当前阶段 BUILDING
  → 允许: real_data_test, debug
  → 禁止: analyze_gaps, build_version
  → 建议: real_data_test
  → 注入 System Prompt
```

---

## 9. 典型流程示例

### 8.1 创建财报风险信号识别器

```text
用户：我要一个能识别财报风险信号的助手，重点关注商誉减值、应收账款异常和现金流恶化。

Nanobot:
  - IntentContext: action=create_agent, stage=exploring
  - FlowController 注入约束: 允许 search_capabilities / inspect，禁止生成
  - 调用 search_project_capabilities 查可用能力

用户：确认生成。

Nanobot:
  - IntentContext: stage=confirmation_pending
  - FlowController 注入约束: 仅允许 generate_confirmed_candidate_agent
  - 调用 generate_confirmed_candidate_agent
  - 工具层校验 spec_id（防名称漂移）
  - 创建 AgentSpec / AgentVersion / Runtime Config / Prompt Template
  - auto-build 版本（内部已完成 gap 检查）
  - IntentContext: stage=building
  - FlowController 注入约束: 允许 real_data_test / debug
                          🚫 禁止 analyze_gaps（已内部完成）
                          🚫 禁止 build_version（已构建）
```

### 9.2 发现能力缺口并创建 Skill

```text
BUILDING 阶段发现 blocking gaps
  → FlowController: 阶段 → GAP_RESOLVING
  → 允许: resolve_gaps, search_capabilities
  → 禁止: real_data_test, publish

Nanobot 调用 resolve_agent_workshop_blocking_gaps:
  - 创建/复用 get_goodwill_analysis
  - IntentContext:
    task_stack:
      [agent] 财报风险信号识别器
      [gap] 商誉减值风险专项评估
      [skill] get_goodwill_analysis
    linked_skills:
      get_goodwill_analysis → 商誉减值风险专项评估
  - 完成后: FlowController → BUILDING（重建版本）
  - IntentContext: next_action=回到父 Agent 重新构建并真数据测试
```

### 9.3 Skill 完成后回到 Agent

```text
GAP_RESOLVING 完成
  ├─ 自动续建成功 → BUILDING
  │    → FlowController: 推荐 run_agent_workshop_real_data_test
  │
  └─ 自动续建失败 / 仅完成 Skill 绑定 → READY_TO_BUILD
       → FlowController: 推荐 build_agent_workshop_version
       → build 成功后进入 BUILDING → TESTING
```

---

## 10. 日志与排查点

关键日志前缀：

- `[ThreadContext]` — 当前线程上下文
- `[IntentContext]` — 意图更新与校验
- `[FlowCtrl]` — 流程约束注入
- `[SpecFocus]` — Agent 聚焦块注入
- `[Workshop]` — Agent Workshop 操作
- `[BuildVersion]` — 版本构建
- `[SkillGen]` — Skill 生成

排查顺序：

1. 看前端是否传了正确 `thread_context.spec_id/spec_name`。
2. 看 `[EmbeddedNanobot][ThreadContext]` 是否接收到正确上下文。
3. 看 `[EmbeddedNanobot][IntentContext] injecting intent block` 是否注入。
4. 看写操作前是否触发 `[AgentWorkshop][IntentGuard]`。
5. 看 `embedded_nanobot_threads.thread_context.intent` 是否持久化。
6. 看 `task_stack/linked_skills/next_action` 是否存在。

---

## 11. 工程原则

### 11.1 LLM 可以推理，但不能作为状态源

LLM 负责：

- 理解用户表达
- 组织自然语言
- 在允许范围内选择工具

系统负责：

- 保存当前状态（IntentContext）
- 规定操作边界（FlowController）
- 校验操作对象（spec_id 防漂移）
- 管理父子任务关系
- 决定是否允许写库

### 11.2 当前对象必须由系统上下文确定

不要让 LLM 自由选择当前 Agent。

### 11.3 LLM 有自主性，但在框架内

FlowController 定义了 12 个阶段，每个阶段明确允许和禁止的操作。
LLM 在允许的工具范围内自由选择，但不能跳出框架。

**类比**：框架是车道，LLM 是司机。司机可以决定加速减速和变道，但不能开出车道。

### 11.4 缺能力先补 Skill，不要跳过 gap 分析

Agent 有 blocking gap 时，必须先补齐 Skill，再重新构建和测试。
不能跳过 gap 直接做测试。

### 11.5 Skill 不是终点，完成后回到 Agent

Skill 创建完成不代表任务结束。
必须回到父 Agent 重新构建 → 测试 → 评估。

### 11.6 缺口分析只做一次

自动构建阶段内建 gap 检查。
禁止在自动构建成功后重复调用 `analyze_agent_workshop_gaps`。

正确方式：

```text
当前 spec_id 来自 thread_context.intent/spec_id
```

错误方式：

```text
LLM 根据聊天历史猜 agent_name/agent_id
```

### 10.3 Skill 是能力，不是流程终点

如果 Skill 是为 Agent gap 创建的，则完成后必须回到 Agent：

```text
Skill completed → CapabilityIndex sync → Workshop gap recheck → build/test/evaluate Agent
```

### 10.4 工具角色必须显式声明

不能只靠工具名称和 description。

应尽量使用：

```text
capability_tags
tool_role_hint
output_shape
preferred_for
not_replacement_for
```

### 10.5 失败删除后不能复用旧方案

删除 Agent 后，旧方案应视为失效。新建同名 Agent 必须基于当前最新能力重新分析。

---

## 12. 后续建议

1. 将 IntentContext 的更新覆盖更多工具：
   - `build_agent_workshop_version`
   - `run_agent_workshop_real_data_test`
   - `iterate_agent_workshop_version`
   - `publish_agent_workshop_version`

2. 前端 Agent Studio 可视化 IntentContext：
   - 当前意图
   - 当前子任务
   - 下一步动作
   - Agent → Gap → Skill 任务链

3. 为 `intent_drift_detected` 增加前端提示：
   - “检测到 Nanobot 试图操作另一个 Agent，已阻止。”

4. 为每次关键写操作记录 audit event：
   - 操作前 intent context
   - 工具参数
   - 是否通过校验

5. 增加端到端测试：
   - 同一线程先讨论 Agent A，再讨论 Agent B，然后确认生成 A，验证不会生成 B。
   - Agent A gap 创建 Skill 后，验证下一轮状态回答仍然以 Agent A 为父任务。
