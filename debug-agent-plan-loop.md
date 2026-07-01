# Debug Session: agent-plan-loop

状态：[OPEN]

## 问题

用户在 Nanobot 给出 3 个候选方案后选择了方案 A。预期：Nanobot 应直接按方案 A 调用生成工具创建新 Agent。实际：Nanobot 又重新输出“能力盘点结果出来了——三个核心维度全部有成熟的平台内置工具覆盖……三个候选方案”，回到了方案确认环节。

## 约束

- 在取证前不修改业务逻辑。
- 先基于日志和当前聊天记录验证真实状态。
- 如现有日志不足，再只添加 instrumentation 日志，不直接改逻辑。

## 可证伪假设

1. H1：用户选择方案 A 后，LLM 没有调用 `generate_confirmed_candidate_agent`，而是重复调用了 `propose_agent_build_plans`。
   - 观察点：`[Nanobot][ToolCall]` 日志、tool_events、消息记录。

2. H2：FlowController 在 `PLAN_SELECTION_PENDING` 阶段错误判断 `pending_options` 状态，导致 recommended_next_tool 仍是 `propose_agent_build_plans`，没有切到 `generate_confirmed_candidate_agent`。
   - 观察点：`[EmbeddedNanobot][FlowCtrl]` 和 `[Flow][Guidance]` 日志中的 phase、recommended next。

3. H3：用户“方案 A”的回复没有被解析进 `pending_options` / `selected_plan_id`，导致系统不知道用户已选择方案。
   - 观察点：`IntentMerge`、`PersistPre`、MongoDB thread_context.intent.pending_options。

4. H4：工具 `propose_agent_build_plans` 返回后的 `pending_options` 没有持久化到 MongoDB，下一轮缺少候选方案上下文。
   - 观察点：`MongoWrite`、`DoneEvent`、当前线程 `thread_context.intent`。

5. H5：硬规则或 guidance 中仍存在“能力盘点后生成候选方案”的强约束，在用户选择方案后覆盖了正确执行路径。
   - 观察点：上下文快照 `logs/embedded_nanobot_context/*.json` 中的 system guidance。

## 当前证据

### 15:41 用户确认需求后，系统进入能力盘点

- trace `42922f36-0c7f-4ce4-a6e6-533cb2f347a5`
- 日志显示阶段为 `requirement_confirmation_pending`，但 LLM 调用了 `search_project_capabilities, search_project_capabilities, analyze_agent_workshop_gaps`。
- 该轮结束时 Intent 更新为 `stage=plan_selection_pending`，但 `pending_options=0`。

### 15:44 用户说“好的，可以开始生成agent了”后，没有生成 Agent

- trace `ae4491f4-43d1-4d8f-adae-6bf5133641e6`
- Flow guidance：`phase=plan_selection_pending`，`next=propose_agent_build_plans`。
- 上下文快照显示 intent：
  - `stage=plan_selection_pending`
  - `next_action=调用 propose_agent_build_plans 生成候选方案`
  - `pending_options=[]`
- LLM 没有调用 `generate_confirmed_candidate_agent`，而是输出方案内容。

### 15:46 用户说“方案A吧”后，仍没有生成 Agent

- trace `44d90f7a-9055-4ca6-83c1-236529d02ccd`
- Flow guidance 仍为：`phase=plan_selection_pending`，`next=propose_agent_build_plans`。
- 上下文快照显示本轮输入包含：
  - `好的，可以开始生成agent了。`
  - `方案A吧。`
- 但 intent 中仍然：
  - `pending_options=[]`
  - `next_action=调用 propose_agent_build_plans 生成候选方案`
  - conversation_summary 里有“只有一个方案/直接实现”，但没有结构化候选方案。
- 该轮实际工具调用：`inspect_agent_workshop_assets`、`search_project_capabilities`、`search_project_capabilities`，没有调用 `generate_confirmed_candidate_agent`。

## 假设判定

1. H1 部分成立：用户选择方案 A 后，没有调用 `generate_confirmed_candidate_agent`；但也没有看到 `propose_agent_build_plans` 工具调用，而是 LLM 口头输出了方案/重新查能力。
2. H2 成立：FlowController 在 `plan_selection_pending` 阶段因为 `pending_options=[]`，持续推荐 `propose_agent_build_plans`，即使用户已表达“开始生成/方案A”。
3. H3 成立：用户“方案A”没有被解析成 `selected_plan_id`，因为没有结构化 `pending_options` 可解析。
4. H4 成立：当前流程中没有看到 `propose_agent_build_plans` 真实工具调用和 pending_options 持久化；候选方案是 LLM 口头生成的，未进入结构化状态。
5. H5 成立：system guidance 中明确写着“候选方案尚未生成，先调用 propose_agent_build_plans”，但用户已经选择方案时，仍被该 guidance 覆盖。

## 根因

这是“口头方案”和“结构化方案状态”断裂：

- 能力盘点后，LLM 直接口头给了方案，而没有调用 `propose_agent_build_plans` 生成结构化 `candidate_plans/pending_options`。
- `IntentContext.pending_options` 一直是空。
- 用户后续说“开始生成/方案A”，系统没有结构化选项可匹配。
- FlowController 因为 `pending_options=[]` 认为“候选方案尚未生成”，持续推荐 `propose_agent_build_plans`。
- 所以流程卡在 `plan_selection_pending`，无法进入 `generate_confirmed_candidate_agent`。

## 已实施修复

1. `agent_builder_flow.py`
   - 新增方案选择识别：`方案A/选A/开始生成/按推荐/可以/确认` 等表达。
   - 新增 selected_plan_id 解析：A/第一个/1 → pending_options[0]。
   - 新增 `[PlanSelection][Route]` 日志，记录：pending_options 数量、用户是否正在选择、解析出的 selected_plan_id、next_action。
   - Flow guidance 中区分：
     - pending_options 非空且用户已选 → 推荐 `generate_confirmed_candidate_agent`，禁止重新生成方案/盘点。
     - pending_options 为空但用户已要求生成 → 必须先 `propose_agent_build_plans` 结构化候选方案，禁止口头重复方案。

2. `runtime.py`
   - 新增 `[PlanSelection][Decision]` 入口日志。
   - 新增 `_force_propose_agent_builder_plans`：当阶段为 `plan_selection_pending`、用户已表达选择/生成、但 pending_options 为空时，不再让 LLM 自由发挥，直接强制调用 `propose_agent_build_plans`。
   - 新增 `_repair_agent_builder_plan_selection_if_needed`：如果 LLM 仍未调用 propose/generate 且 pending_options 为空，二次兜底强制结构化方案。

3. `nanobot_agent_builder_tools.py`
   - `propose_agent_build_plans` 写入的 pending_options 现在包含 `recommended` 和 `acknowledged_gaps`。
   - 新增 `[ProposePlans][Output]` 日志，记录 plan_count、recommended、pending_options 数量和 option_ids。

## 验证

- `python -m py_compile core/embedded_nanobot/agent_builder_flow.py core/embedded_nanobot/runtime.py core/tools/implementations/agent_builder/nanobot_agent_builder_tools.py` 通过。
- `scripts/pre_check.py --files ...` 的语法检查通过；仍报告 `nanobot_agent_builder_tools.py` 中已有的 6 类条件 import 风险，不是本次新增改动。

## 后续测试观察点

重启后端后，复现“方案A吧”时应看到：

```text
[PlanSelection][Decision] pending_options=0 user_is_selecting=True selected_plan_id=none recommended_tool=propose_agent_build_plans
[PlanSelection][ForcePropose] pending_options empty; forcing structured plan generation ...
[ProposePlans][Output] plan_count=... recommended=... pending_options=... option_ids=...
[IntentContext][Update] ... stage=plan_selection_pending ... pending_options>0
```

下一轮再说“方案A”时应看到：

```text
[PlanSelection][Decision] pending_options>0 user_is_selecting=True selected_plan_id=direct|complete|quick recommended_tool=generate_confirmed_candidate_agent
[PlanSelection][Route] pending_options>0 user_is_selecting=True selected_plan_id=... 
[Nanobot][ToolCall] ... generate_confirmed_candidate_agent
```

