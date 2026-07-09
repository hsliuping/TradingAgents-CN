# Agent Builder LangGraph 化重构方案

> 目标：把当前 Nanobot Agent Builder 从「LLM 自主决策 + Prompt 约束」改为「LangGraph 流程编排 + Nanobot 对话执行」。
>
> 核心原则：**流程判断归系统，沟通表达归 LLM，状态推进归图。**

---

## 1. 背景与问题

最近一段时间，Agent Studio / Nanobot 在创建 Agent 的过程中反复出现状态错乱、流程绕开、跨轮上下文丢失的问题。我们已经做过多轮 prompt、FlowController、pending_question、pending_options、日志、fallback 修补，但问题仍然反复出现。

这说明根因不只是某条 prompt 写错，而是当前架构把过多流程控制权交给了 LLM。

当前模式大致是：

```text
用户输入
  ↓
Nanobot LLM 判断意图
  ↓
LLM 自己决定是否调用工具、调用哪个工具、什么时候进入下一阶段
  ↓
工具结果写入部分状态
  ↓
下一轮再由 LLM 基于 prompt 和历史猜测当前阶段
```

这个模式在普通问答里可用，但在 Agent Builder 这种多阶段、多确认、多工具写入的流程中不稳定。

---

## 2. 最近遇到的主要问题

### 2.1 口头生成方案，绕过结构化工具

表现：Nanobot 在能力盘点后直接用自然语言给出「方案一/方案二/方案三」，但没有调用 `propose_agent_build_plans`。

后果：

- `pending_options` 没有写入；
- 用户回复「方案一」「确认」时，系统没有结构化选项可匹配；
- FlowController 继续认为方案尚未生成；
- 流程卡回方案生成或能力盘点阶段。

本质：LLM 以为自己能完成方案表达，但系统需要的是结构化状态写入。

### 2.2 需求确认、能力盘点、方案生成职责混淆

表现：`prepare_agent_generation_confirmation` 曾被错误引导成「能力盘点 + gap 分析 + 方案展示」步骤。

后果：

- 需求确认稿里提前出现工具、gap、方案；
- 后续 `analyze_agent_workshop_gaps` / `propose_agent_build_plans` 被绕过；
- 阶段语义不清，状态机无法判断下一步。

本质：流程语义写在 prompt 中，且不同 prompt 段之间存在冲突。

### 2.3 用户确认后不知道下一步

表现：用户回复「好的，确认」「可以」「按默认的」后，Nanobot 有时说「没有待确认方案」「不知道你在说什么」。

后果：

- 用户体验断裂；
- 需要重新描述需求；
- 系统重复开始新一轮 Agent 设计。

本质：上一轮的待确认问题、确认稿、候选方案没有以稳定的流程状态持久化，LLM 只能从历史对话猜。

### 2.4 方案选择后重复 gap 分析或回退

表现：用户已经选择方案 A / 推荐方案后，Nanobot 又调用 `analyze_agent_workshop_gaps` 或 `build_agent_workshop_version`，甚至重新解释缺口。

后果：

- 已确认方案被覆盖；
- quick plan 的已接受缺口又被当作 blocking gap；
- 生成 Agent 阶段无法稳定进入。

本质：流程状态没有硬性禁止回退，LLM 仍能调用非当前阶段工具。

### 2.5 LLM 调用无关工具查流程

表现：Nanobot 调用 `read_file`、`exec`、`inspect_agent_workshop_assets` 去查项目文档或资产，而不是执行当前阶段必需工具。

后果：

- 上下文变长；
- 结果不确定；
- 进一步污染模型判断。

本质：当前阶段的工具约束只是 prompt 建议，工具列表仍然过宽。

### 2.6 状态持久化与跨轮摘要不足

表现：第一轮已经提出问题，第二轮用户回复确认时，系统未必知道用户确认的是哪个问题。

后果：

- `pending_question` / `pending_options` 丢失或为空；
- `conversation_summary` 不足以恢复结构化状态；
- MongoDB 中 thread_context 有时只剩 `preference_id`。

本质：流程状态没有成为唯一事实源，跨轮依赖 LLM 记忆和前端传递。

---

## 3. 已做过的改进与局限

### 3.1 已做改进

| 改进 | 作用 | 局限 |
|---|---|---|
| `IntentContext` | 记录 action / stage / spec_id / pending_question / pending_options | 状态写入依赖工具是否被调用 |
| `FlowController` | 定义阶段、允许工具、禁止工具、推荐下一步 | 当前只生成 prompt 约束，LLM 可不遵守 |
| `pending_question` 注入 | 解决部分「可以」指代丢失 | 只覆盖工具写入过的问题 |
| `conversation_summary` | 帮助下一轮恢复上下文 | 摘要不是结构化事实源 |
| `propose_agent_build_plans` fallback | 内部 LLM 失败时仍能生成方案 | 前提是该工具被调用 |
| Nanobot event 落盘 | 方便调试前端 step/event 日志 | 不改变流程稳定性 |
| quick plan 跳过 auto-build | 避免已接受缺口被重复阻塞 | 只修复 quick plan 一类问题 |

### 3.2 局限

这些改进本质上仍是在修补「LLM 自主决策」模式：

```text
系统告诉 LLM 应该怎么做
但最终仍由 LLM 决定是否照做
```

只要 LLM 还能：

- 不调指定工具；
- 口头生成结构化方案；
- 调用无关工具；
- 忽略当前阶段；
- 自己判断状态转换；

就还会出现类似问题。

---

## 4. 新方案：Agent Builder LangGraph 化

### 4.1 设计目标

把 Agent Builder 改为类似单股分析流程的图编排模式：

```text
LangGraph / 状态机：决定当前节点、下一节点、是否等待用户、工具结果是否有效
Nanobot LLM：负责沟通、解释、按节点要求调用工具
工具层：负责确定性写入、查询、生成、测试
MongoDB：负责持久化 graph state / thread_context
```

一句话：

> Nanobot 不再是自由 Agent，而是被 Agent Builder Graph 调度的对话执行器。

### 4.2 和现有单股分析流程的关系

现有单股分析流程位于：

```text
core/workflow/
  models.py
  builder.py
  engine.py
  templates/v2_stock_analysis_workflow.py
  templates/position_analysis_workflow_v2.py
```

其模式是：

```text
WorkflowDefinition → NodeDefinition / EdgeDefinition → WorkflowBuilder → LangGraph StateGraph → WorkflowEngine.execute_async()
```

单股分析中：

- 节点是分析师 Agent；
- 边是分析师之间的执行顺序；
- 状态是各类分析报告；
- 执行是一次性任务流。

Agent Builder 中：

- 节点是构建阶段；
- 边是产品流程条件；
- 状态是 Agent 构建上下文；
- 执行是多轮人机交互流，需要等待用户输入。

因此建议：

- **复用 LangGraph 思想和部分状态设计经验；**
- **不直接复用现有 `core/workflow` 分析工作流引擎；**
- 新建专门的 Agent Builder Graph，以避免污染单股分析和持仓分析。

---

## 5. 新架构关系

### 5.1 模块关系

```text
用户
  ↓
Agent Studio UI
  ↓
Embedded Nanobot API / Runtime
  ↓
AgentBuilderGraph（新）
  ↓
阶段节点 / 条件边 / 状态持久化
  ↓
Nanobot LLM（节点内沟通与工具调用）
  ↓
Agent Builder Tools / Agent Workshop Service / MongoDB
```

### 5.2 Nanobot 与 Graph 的分工

| 模块 | 负责 | 不负责 |
|---|---|---|
| Nanobot | 专家沟通、解释工具结果、组织自然语言回复、按节点要求调用工具 | 不决定流程阶段、不决定下一步、不私自跳阶段 |
| AgentBuilderGraph | 当前阶段、必须调用的工具、条件分支、状态推进、等待用户 | 不负责大段自然语言表达 |
| Tools | 需求整理、缺口分析、方案生成、配置写入、测试执行 | 不决定整体流程 |
| MongoDB | graph state、thread_context、事件记录、构建产物 | 不判断业务流程 |

---

## 6. Graph 节点设计

### 6.1 核心节点

| 节点 | 作用 | 必需工具 | 输出状态 | 下一步 |
|---|---|---|---|---|
| `requirement_intake` | 根据用户需求生成默认方案草稿并结构化初步需求 | `prepare_agent_requirement_intake` | `requirement_summary`, `pending_question` | `wait_intake_confirmation` 或 `requirement_confirmation` |
| `wait_intake_confirmation` | 等待用户确认默认方向或补充偏好 | 无 | 用户确认/修改意图 | 确认 → `requirement_confirmation`；修改 → `requirement_intake` |
| `requirement_confirmation` | 生成纯业务确认稿 | `prepare_agent_generation_confirmation` | `spec_id`, `spec_name`, `confirmation_brief`, `pending_question` | `wait_requirement_confirmation` |
| `wait_requirement_confirmation` | 等待用户确认职责边界和输出形态 | 无 | 用户确认/修改意图 | 确认 → `capability_search`；修改 → `requirement_confirmation` |
| `capability_search` | 搜索现有能力 | `search_project_capabilities` | `capability_inventory` | `gap_analysis` |
| `gap_analysis` | 做真实缺口分析 | `analyze_agent_workshop_gaps` | `gap_report` | `plan_generation` |
| `plan_generation` | 生成结构化候选方案 | `propose_agent_build_plans` | `candidate_plans`, `pending_options`, `recommended_plan_id` | `wait_plan_selection` |
| `wait_plan_selection` | 等待用户选择方案 | 无 | `selected_plan_id`, `acknowledged_gaps` | `generate_candidate_agent` 或 `requirement_intake` |
| `generate_candidate_agent` | 生成 Agent 配置、Prompt、绑定、Draft | `generate_confirmed_candidate_agent` | `generated_agent`, `workshop_session_id`, `version_id?` | `build_or_ready_to_test` |
| `build_or_ready_to_test` | 根据方案决定构建版本或跳过 | `build_agent_workshop_version`（可选） | `version_id`, `build_status` | `wait_test_request` 或 `gap_resolution` |
| `wait_test_request` | 等待用户给测试标的或确认测试 | 无 | `test_symbol` | `real_data_test` |
| `real_data_test` | 真数据测试 | `run_agent_workshop_real_data_test` | `test_result`, `evaluation_status` | `evaluate_or_publish` |
| `evaluate_or_publish` | 根据评估结果进入发布或迭代 | `evaluate_agent_workshop_version` / `publish_agent_workshop_version` / `iterate_agent_workshop_version` | `official_acceptance_decision` | `published` / `iterating` / `gap_resolution` |
| `gap_resolution` | 补齐缺口 | `resolve_agent_workshop_blocking_gaps` | `resolved_skills` | `capability_search` 或 `build_or_ready_to_test` |

### 6.2 等待节点原则

所有需要用户输入的地方都显式建模为 `wait_*` 节点：

```text
wait_intake_confirmation
wait_requirement_confirmation
wait_plan_selection
wait_test_request
wait_publish_confirmation
```

等待节点不让 LLM 自己猜下一步，而是由条件函数解析用户输入：

```text
用户回复确认 → true
用户回复修改 → revise
用户回复取消 → cancel
用户回复方案 A/1/推荐 → selected_plan_id
```

---

## 7. 状态模型设计

建议新增：

```text
core/embedded_nanobot/workflows/agent_builder_state.py
```

核心 state：

```python
class AgentBuilderState(TypedDict, total=False):
    thread_id: str
    user_id: str
    user_message: str

    current_node: str
    stage: str
    awaiting_user: bool
    pending_question: str

    spec_id: str
    spec_name: str
    requirement_summary: str
    confirmation_brief: dict

    capability_inventory: dict
    gap_report: dict

    candidate_plans: list[dict]
    pending_options: list[dict]
    recommended_plan_id: str
    selected_plan_id: str
    acknowledged_gaps: list[str]

    generated_agent: dict
    workshop_session_id: str
    version_id: str
    build_status: str

    test_symbol: str
    test_result: dict
    official_acceptance_decision: str

    conversation_summary: str
    tool_events: list[dict]
    final_response: str
    errors: list[dict]
```

状态原则：

1. `stage/current_node` 是唯一阶段事实源；
2. `pending_options` 只能由 `plan_generation` 节点写入；
3. `selected_plan_id` 只能由 `wait_plan_selection` 条件函数写入；
4. `gap_report` 只能由 `gap_analysis` 写入；
5. `generated_agent` 只能由 `generate_candidate_agent` 写入；
6. LLM 不能直接决定这些结构化状态。

---

## 8. 条件边设计

### 8.1 需求探索后

```text
requirement_intake
  ├─ can_proceed=yes → requirement_confirmation
  └─ can_proceed=no  → wait_intake_confirmation
```

### 8.2 用户确认需求后

```text
wait_requirement_confirmation
  ├─ confirm → capability_search
  ├─ revise  → requirement_confirmation
  └─ cancel  → end
```

### 8.3 gap 分析后

```text
gap_analysis
  └─ plan_generation
```

说明：无论是否有 blocking gaps，都进入 `plan_generation`。是否补缺口是方案选择问题，不由 gap 节点直接阻塞。

### 8.4 方案生成后

```text
plan_generation
  └─ wait_plan_selection
```

### 8.5 用户选择方案后

```text
wait_plan_selection
  ├─ direct/quick/complete → generate_candidate_agent
  ├─ narrow → requirement_intake
  └─ unknown → wait_plan_selection
```

### 8.6 生成 Agent 后

```text
generate_candidate_agent
  ├─ selected_plan=quick  → wait_test_request
  ├─ version_built=true   → wait_test_request
  ├─ needs_build=true     → build_or_ready_to_test
  └─ error                → error_recovery
```

### 8.7 测试后

```text
real_data_test
  ├─ pass   → wait_publish_confirmation
  ├─ revise → iterating
  └─ reject → iterating / gap_resolution
```

---

## 9. 与现有系统的集成方式

### 9.1 新增目录

```text
core/embedded_nanobot/workflows/
  __init__.py
  agent_builder_state.py
  agent_builder_graph.py
  agent_builder_nodes.py
  agent_builder_conditions.py
  agent_builder_store.py
```

### 9.2 Runtime 接入

在 `core/embedded_nanobot/runtime.py` 中新增分流：

```python
if channel == "agent_workshop":
    return await self._run_agent_builder_graph(...)
else:
    return await self._run_general_nanobot(...)
```

保留现有 Nanobot 通用聊天能力，不影响普通聊天、文件操作、工具检索。

### 9.3 API 层不大改

现有接口：

```text
POST /api/embedded-nanobot/chat/stream
```

继续使用。只是当 `channel=agent_workshop` 时，后端内部切换到 AgentBuilderGraph。

前端 Agent Studio 不需要大改，仍然接收：

```text
started / progress / step_event / tool_event / token / done / error
```

### 9.4 工具层复用

继续复用当前 12 个左右的 Agent Builder 工具：

```text
prepare_agent_requirement_intake
prepare_agent_generation_confirmation
search_project_capabilities
analyze_agent_workshop_gaps
propose_agent_build_plans
generate_confirmed_candidate_agent
build_agent_workshop_version
run_agent_workshop_real_data_test
evaluate_agent_workshop_version
publish_agent_workshop_version
iterate_agent_workshop_version
resolve_agent_workshop_blocking_gaps
```

但调用时机由 Graph 决定，不再由 LLM 自主决定。

### 9.5 MongoDB 状态存储

新增或复用 collection：

```text
embedded_nanobot_threads
agent_builder_graph_sessions（建议新增）
```

`agent_builder_graph_sessions` 建议字段：

```json
{
  "thread_id": "embedded:agent-studio:...",
  "user_id": "...",
  "current_node": "wait_plan_selection",
  "stage": "plan_selection_pending",
  "state": {},
  "updated_at": "...",
  "created_at": "..."
}
```

---

## 10. LLM 在新架构中的使用方式

LLM 仍然存在，但不再掌握流程控制权。

### 10.1 节点内沟通

例如 `requirement_intake` 节点：

```text
Graph 决定：当前必须完成需求探索
LLM 负责：用财经产品专家身份给出默认方案草稿
Tool 负责：prepare_agent_requirement_intake 写入结构化初始需求
Graph 判断：can_proceed_to_confirmation 是否为 yes
```

### 10.2 工具调用约束

每个节点只暴露当前节点允许的工具：

```text
requirement_confirmation 节点：只暴露 prepare_agent_generation_confirmation
plan_generation 节点：只暴露 propose_agent_build_plans
generate_candidate_agent 节点：只暴露 generate_confirmed_candidate_agent
```

这样 LLM 无法调用 `read_file`、`exec` 或重新 `analyze_gaps` 绕开流程。

### 10.3 工具结果校验

节点执行后，由 Graph 校验：

```text
plan_generation 必须产生 candidate_plans 和 pending_options
否则进入 error_recovery 或 fallback 规则
```

不是由 LLM 说“我已经生成方案”。

---

## 11. 实施计划

### 阶段 1：旁路实现，不替换现有流程

目标：先建 Graph，不接入生产路径。

任务：

1. 新增 `agent_builder_state.py`；
2. 新增 `agent_builder_conditions.py`；
3. 新增 `agent_builder_nodes.py`；
4. 新增 `agent_builder_graph.py`；
5. 用测试脚本跑通：
   - 创建需求；
   - 确认需求；
   - gap 分析；
   - 方案生成；
   - 方案选择；
   - 生成 Agent。

验收：不用前端，只用固定输入跑完整状态转换。

### 阶段 2：接入 Agent Studio 流式事件

目标：Graph 能通过现有 SSE 输出 step/progress/tool_event。

任务：

1. 在 Graph node 中接入现有 `emit_step` / `on_progress` / `on_tool_event`；
2. 将 graph state 写入 MongoDB；
3. 在 `runtime.py` 中增加 `_run_agent_builder_graph`；
4. 增加开关：

```text
AGENT_BUILDER_GRAPH_ENABLED=true/false
```

验收：前端仍能看到原来的步骤日志，刷新后状态可恢复。

### 阶段 3：替换 Agent Studio 创建 Agent 流程

目标：`channel=agent_workshop` 的新建 Agent 流程走 Graph。

任务：

1. Agent Studio 新建 Agent 入口启用 Graph；
2. 保留旧 Nanobot 作为 fallback；
3. 对比日志：
   - 是否还会口头生成方案；
   - 是否还会 pending_options 为空；
   - 是否还会重复 gap 分析；
   - 是否还会调用 read_file / exec 查流程。

验收：完整创建一个 Agent，并进入测试阶段。

### 阶段 4：覆盖测试、发布、迭代

目标：把后半段生命周期也 Graph 化。

任务：

1. 接入 `run_agent_workshop_real_data_test`；
2. 接入 `evaluate_agent_workshop_version`；
3. 接入 `publish_agent_workshop_version`；
4. 接入 `iterate_agent_workshop_version`；
5. 接入 `resolve_agent_workshop_blocking_gaps`。

验收：Agent 从创建到测试、评估、发布/迭代全链路稳定。

---

## 12. 风险与注意事项

### 12.1 不要一次性删除现有 Nanobot 流程

建议先旁路实现，通过开关切换。现有 Nanobot 通用聊天、文件操作、普通工具调用仍然有价值。

### 12.2 等待用户节点必须持久化

所有 `wait_*` 节点必须写入 MongoDB，否则刷新或下一轮会丢状态。

### 12.3 工具返回结构必须稳定

Graph 依赖工具结果判断下一步，因此关键工具必须保证返回字段稳定：

- `prepare_agent_requirement_intake.status`
- `prepare_agent_requirement_intake.can_proceed_to_confirmation`
- `prepare_agent_generation_confirmation.confirmation_brief`
- `analyze_agent_workshop_gaps.gap_report`
- `propose_agent_build_plans.candidate_plans`
- `generate_confirmed_candidate_agent.governance_boundary`

### 12.4 LLM 仍可能表达不佳，但不会破坏流程

Graph 化后，LLM 可能仍然说得不够好，但它不能再：

- 跳阶段；
- 绕工具；
- 口头替代结构化工具；
- 自己推进状态；
- 重跑不该重跑的工具。

---

## 13. 关键实现细节补充

### 13.1 等待节点如何跨 HTTP 请求暂停和恢复

这是 Agent Builder Graph 与单股分析流程最大的不同：单股分析是一次性任务流，Agent Builder 是**多轮人机交互流**。

#### 方案：基于 MongoDB Checkpoint 的暂停/恢复

```text
第 1 轮 HTTP 请求：
  Graph 执行到 wait_requirement_confirmation
  → 序列化当前 state 到 MongoDB
  → 生成 pending_question 文本
  → 通过 SSE 推送给用户
  → 本轮结束，Graph 暂停

第 2 轮 HTTP 请求：
  → 从 MongoDB 加载上次 state
  → 将用户的新消息注入 state.user_message
  → 继续执行条件函数
  → 条件函数返回 confirm → 进入 capability_search
  → Graph 继续执行
```

**实现方式**：不用 LangGraph 内置的 `interrupt`（它依赖进程内内存），而是用自定义的 `checkpoint` 机制：

```python
# agent_builder_store.py

class AgentBuilderGraphStore:
    def save_checkpoint(self, thread_id: str, state: AgentBuilderState, current_node: str):
        """等待节点前保存状态"""
        collection.update_one(
            {"thread_id": thread_id},
            {"$set": {
                "current_node": current_node,
                "state": state,
                "updated_at": datetime.utcnow()
            }},
            upsert=True
        )

    def load_checkpoint(self, thread_id: str) -> AgentBuilderState | None:
        """恢复状态"""
        doc = collection.find_one({"thread_id": thread_id})
        if doc:
            return AgentBuilderState(**doc["state"])
        return None

    def delete_checkpoint(self, thread_id: str):
        """Graph 完成/取消后清理"""
        collection.delete_one({"thread_id": thread_id})
```

**关键约束**：

1. 所有 `wait_*` 节点执行前，必须调用 `save_checkpoint`；
2. 所有非 `wait_*` 节点执行前，先调用 `load_checkpoint` 恢复状态；
3. `wait_*` 节点不调用 LLM，只做条件判断和序列化；
4. 每个 `wait_*` 节点必须写入 `pending_question` 和可选的 `pending_options`；
5. 不能连续两个 `wait_*` 节点（用户必须至少看到一个非 wait 节点）。

**状态恢复流程**：

```python
# runtime.py

async def _run_agent_builder_graph(self, ...):
    store = AgentBuilderGraphStore(db)

    # 尝试恢复已有状态
    state = store.load_checkpoint(thread_id)
    if state:
        state["user_message"] = user_message  # 注入本轮用户输入
    else:
        state = AgentBuilderState(
            thread_id=thread_id,
            user_message=user_message,
            current_node="START"
        )

    graph = build_agent_builder_graph()
    result = await graph.ainvoke(state)

    if result["current_node"].startswith("wait_"):
        store.save_checkpoint(thread_id, result, result["current_node"])
        # 返回 pending_question 给用户
    else:
        store.delete_checkpoint(thread_id)
        # 返回最终结果
```

**刷新/重新打开的处理**：

```text
前端页面刷新 → 重新请求 /api/embedded-nanobot/chat/stream
  → 后端 load_checkpoint
  → 如果 checkpoint 存在且 current_node 是 wait_*
  → 返回 pending_question 文本
  → 前端显示"待确认"状态
```

---

### 13.2 工具失败的错误恢复策略

工具失败有 3 种情况，需要分别处理：

#### 情况 1：工具内部执行异常（网络、超时、数据库）

```text
策略：重试 1 次 → 仍失败 → 进入 error_recovery 节点
```

```python
async def execute_node_tool(node_name, tool_name, state):
    try:
        result = await call_tool(tool_name, state)
        return result
    except TemporaryError:
        try:
            result = await call_tool(tool_name, state)  # 重试
            return result
        except Exception as e:
            state["errors"].append({
                "node": node_name,
                "tool": tool_name,
                "error": str(e),
                "retries": 1
            })
            return {"status": "error", "message": str(e)}
```

#### 情况 2：工具返回 status=error（业务逻辑失败）

```text
策略：不重试，直接进入 error_recovery 节点
```

`error_recovery` 节点的行为：

```text
1. 检查 errors 数组
2. 如果 errors 只有 1 个：
   → 用 LLM 生成友好的错误解释
   → 给用户 3 个选项：
     a. 重试（回到当前节点）
     b. 跳过（进入下一节点，但标记状态为 degraded）
     c. 取消（回到 exploring）
3. 如果 errors 有多个：
   → 建议用户重新开始
   → 回到 exploring
```

#### 情况 3：工具返回成功但关键字段缺失

```text
策略：节点内校验 → 不通过 → fallback 规则
```

每个节点定义必须校验的字段：

```python
NODE_VALIDATION = {
    "plan_generation": {
        "required": ["candidate_plans", "pending_options"],
        "fallback": "_fallback_build_plans"
    },
    "generate_candidate_agent": {
        "required": ["generated_agent", "workshop_session_id"],
        "fallback": None  # 必须重试，不能 fallback
    }
}
```

**关键原则**：

- 不自动回退到上一阶段；
- 不自动跳过当前阶段；
- 所有错误都写入 `state.errors` 日志；
- 错误恢复由 `error_recovery` 节点处理，不是 LLM 自己决定。

---

### 13.3 用户中途改变需求

用户可能在任意阶段说"再加一个维度""换个方向""我想改成…"。

#### 识别规则

```python
# agent_builder_conditions.py

def detect_intent_change(state: AgentBuilderState) -> str:
    """在 wait_* 节点判断用户是否改变需求"""
    user_msg = state["user_message"].strip().lower()

    # 修改需求的关键词
    revise_keywords = [
        "再加", "换个", "改成", "不要", "算了",
        "重新来", "换一个", "补充", "增加维度",
        "也加上", "再增加", "还包括"
    ]

    if any(kw in user_msg for kw in revise_keywords):
        return "revise_requirement"

    return "normal"
```

#### 处理方式

```text
用户在 wait_plan_selection 说"再加一个行业对比维度"
  → 条件函数返回 revise_requirement
  → 回到 requirement_intake 节点
  → 但保留已有 state：
      - spec_id（不重新创建）
      - spec_name（可以追加）
      - capability_inventory（保留）
      - gap_report（标记为 dirty，需要重新分析）
      - generated_agent（标记为 stale）
  → LLM 看到已有 spec_id + 新需求
  → 重新走 intake → confirmation → capability → gap → plan
```

**关键约束**：

1. 不改需求规格书（spec_id 不变）；
2. 重新做能力盘点和 gap 分析；
3. 旧方案标记为 stale 但不删除；
4. 用户也可能从 `wait_test_request` 改需求，同样处理。

---

### 13.4 Graph 和 SSE 流式事件的对接

Agent Studio 前端依赖 SSE 事件流展示步骤。Graph 需要在对应用户可见的节点产生事件。

#### 事件类型映射

```python
# 节点 → 事件 映射

NODE_EVENT_MAP = {
    "requirement_intake": [
        ("step", "需求探索"),
        ("progress", "正在分析需求并生成默认方案"),
        ("tool", "prepare_agent_requirement_intake"),
        ("progress", "需求结构化完成"),
        ("step", "需求探索完成"),
    ],
    "requirement_confirmation": [
        ("step", "需求确认"),
        ("progress", "正在生成确认稿"),
        ("tool", "prepare_agent_generation_confirmation"),
        ("step", "需求确认完成"),
    ],
    "capability_search": [
        ("step", "能力盘点"),
        ("progress", "正在搜索现有能力"),
        ("tool", "search_project_capabilities"),
    ],
    "gap_analysis": [
        ("step", "缺口分析"),
        ("progress", "正在分析能力缺口"),
        ("tool", "analyze_agent_workshop_gaps"),
        ("step", "缺口分析完成"),
    ],
    "plan_generation": [
        ("step", "方案生成"),
        ("progress", "正在生成候选方案"),
        ("tool", "propose_agent_build_plans"),
        ("step", "方案生成完成"),
    ],
    "generate_candidate_agent": [
        ("step", "生成 Agent"),
        ("progress", "正在写入配置和 Prompt"),
        ("tool", "generate_confirmed_candidate_agent"),
        ("step", "Agent 生成完成"),
    ],
    # ... 其他节点
}
```

#### 实现方式

每个节点函数接收一个 `event_callback`：

```python
# agent_builder_nodes.py

async def requirement_intake_node(state, event_callback):
    await event_callback("step", "需求探索")
    await event_callback("progress", "正在分析需求并生成默认方案")

    result = await call_tool("prepare_agent_requirement_intake", state)
    await event_callback("tool", "prepare_agent_requirement_intake", result)

    await event_callback("progress", "需求结构化完成")
    await event_callback("step", "需求探索完成")

    return result
```

#### 在 runtime 中接入

```python
# runtime.py

async def _run_agent_builder_graph(self, ...):
    async def event_callback(event_type, label, payload=None):
        await queue.put({
            "type": event_type,
            "label": label,
            "payload": payload
        })

    # 把 event_callback 注入 state
    state["event_callback"] = event_callback

    graph = build_agent_builder_graph()
    result = await graph.ainvoke(state)

    # SSE 流照常推送
```

#### Token 流式输出

LLM 的 token 流式输出仍然走现有 SSE 通道：

```text
节点内 LLM 调用
  → 每个 token 通过 event_callback("token", token)
  → runtime 推入 SSE 队列
  → 前端实时渲染
```

Graph 本身不控制 token 流，它只是把 LLM 调用封装在节点内。

---

## 14. 最终目标

最终形态：

```text
Agent Builder Graph = 流程大脑
Nanobot = 对话执行器
Agent Builder Tools = 确定性动作
MongoDB = 状态事实源
Agent Studio = UI 展示与用户输入
```

这能把当前最大的不稳定点从：

```text
LLM 是否遵守 prompt
```

转移到：

```text
Graph 条件和工具返回是否正确
```

后者是工程问题，可测试、可日志化、可回归；前者是模型行为问题，难以完全控制。

---

## 15. 推荐结论

建议停止继续修补 prompt，启动 Agent Builder LangGraph 化改造。

优先级：

1. 先实现创建 Agent 前半段：需求 → 确认 → 能力盘点 → 方案 → 生成；
2. 再实现测试/评估/发布；
3. 最后清理旧 FlowController 中只用于 prompt 约束的逻辑。

这个方案与现有单股分析/持仓分析流程理念一致，但更适合 Agent Builder 的多轮交互特点。