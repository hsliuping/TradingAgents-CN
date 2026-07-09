# Agent 工坊 + Skill 完整生命周期流程图

## 一、目标

把用户需求稳定地转化为可测试、可发布、可复用的 Agent：

- 不漂移（不会生成错 Agent）
- 不重复（不会反复检查 gap）
- 不缺工具（必须按 execution_plan 调用关键工具）
- 可追溯（Agent → Gap → Skill → Test → Publish 全链路）

---

## 二、主流程（用户视角）

```text
┌──────────────────────────────────────────────────────────────┐
│ 1. 需求讨论                                                  │
│    用户："我要一个能识别财报风险信号的助手..."                │
│    Nanobot：询问目标、维度、输出格式                         │
└───────────────────────────┬──────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ 2. 生成确认                                                  │
│    Nanobot：总结需求 + 候选工具 + 输出字段                   │
│    用户："确认，启动生成"                                    │
└───────────────────────────┬──────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ 3. 版本构建                                                  │
│    自动：                                                    │
│      - 创建 Draft                                            │
│      - 自动 build_version（内部含真实 gap 分析）             │
│      - 生成 Prompt / Runtime Config / Tool Binding           │
└───────────────────────────┬──────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ 4. 真数据测试                                                │
│    Nanobot：选择样本股票，运行 run_agent_workshop_real_data_test
│    系统：LLM 评估报告质量 + 工具调用覆盖率                    │
└───────────────────────────┬──────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ 5. 发布 / 迭代                                               │
│    评估通过 → publish_version                                │
│    评估失败 → iterate_version / resolve_gaps                 │
└──────────────────────────────────────────────────────────────┘
```

---

## 三、内部详细流程（含分支）

### Phase 1: 需求澄清

```text
用户输入
  │
  ▼
Nanobot 调用 search_project_capabilities
  │
  ▼
确认现有工具/Skill 是否足够
  │
  ▼
prepare_agent_generation_confirmation
  │
  ▼
输出确认稿：职责、工具候选、输出字段
```

**当前状态机阶段**：`EXPLORING → CAPABILITY_CHECK → DRAFT_PREPARING → CONFIRMATION_PENDING`

---

### Phase 2: 候选生成与确认

```text
用户确认
  │
  ▼
generate_confirmed_candidate_agent
  │
  ├─ 创建 Runtime Config
  ├─ 创建 Prompt Template
  ├─ 创建 Workshop Draft + session
  ├─ 绑定初始工具
  └─ auto_build_workshop_version
       │
       ├─ 成功（有 version）  → Phase 3b: 真数据测试
       ├─ 因 blocking gap 失败 → Phase 3a: 缺口补齐
       └─ 未生成 version（auto_build 未启用/失败） → READY_TO_BUILD → build_version → Phase 3b
```

**当前状态机阶段**：`CONFIRMATION_PENDING → GENERATING → (READY_TO_BUILD | BUILDING | GAP_RESOLVING)`

---

### Phase 3a: 缺口补齐（只有发现 blocking gap 才走）

```text
发现 blocking gaps
  │
  ▼
Nanobot 向用户解释缺口
  │
  ▼
用户确认
  │
  ▼
resolve_agent_workshop_blocking_gaps（同步路径）
  │
  ├─ 为每个 gap 创建/复用 Skill
  ├─ 自动验证 Skill
  ├─ 自动续建版本（auto_continue_build）
  │
  ├─ 自动续建成功  → BUILDING → Phase 3b
  └─ 仅完成 Skill 绑定 → READY_TO_BUILD → build_version → Phase 3b
```

**当前状态机阶段**：`BUILDING → GAP_RESOLVING → (BUILDING | READY_TO_BUILD)`

**注意**：异步 gap resolution（`start_agent_workshop_gap_resolution`）目前**不在 FlowController 主链路内**，完成后不会自动回到 Agent 构建链路。详见第 8 节。

---

### Phase 3b: 真数据测试与评估

```text
版本已构建
  │
  ▼
run_agent_workshop_real_data_test
  │
  ▼
执行实际样本股票
  │
  ▼
_judge_runtime_result_with_llm（LLM 评估）
  │
  ├─ pass → Phase 4: 发布
  ├─ revise → Phase 3c: 迭代
  └─ reject → Phase 3a/3c: 重新分析缺口或迭代
```

**当前状态机阶段**：`BUILDING → TESTING → EVALUATING → (PUBLISHING | ITERATING | GAP_RESOLVING)`

---

### Phase 3c: 迭代

```text
评估 revise/reject
  │
  ▼
iterate_agent_workshop_version
  │
  ├─ 改写 Prompt / 调整工具 / 调整 execution_plan
  ├─ 重新 build_version
  │
  ▼
回到 Phase 3b 测试
```

**当前状态机阶段**：`ITERATING → BUILDING → TESTING`

---

### Phase 4: 发布

```text
评估 pass
  │
  ▼
publish_version
  │
  ├─ 最终 gap 检查
  ├─ Runtime Config 升级为 active
  ├─ Agent spec 状态变为 published
  │
  ▼
PUBLISHED
```

**当前状态机阶段**：`PUBLISHING → PUBLISHED`

---

## 四、关键分支条件

| 分支 | 判断条件 | 下一状态 |
|---|---|---|
| auto-build 成功 | `workshop_version_result.status == "ok"` 且生成 version | `BUILDING` |
| auto-build 未生成版本 | `auto_build_workshop_version=False` 或失败 | `READY_TO_BUILD` |
| auto-build 发现 blocking gap | build_version 抛 blocking gap 异常 | `GAP_RESOLVING` |
| gap 补齐后自动续建 | `resolve_gaps.auto_continue.status == "completed"` | `BUILDING` |
| gap 补齐后需手动构建 | `resolve_gaps` 成功但 auto_continue 未完成 | `READY_TO_BUILD` |
| 测试通过 | evaluation official_acceptance_decision == "pass" | `PUBLISHING` |
| 测试需修订 | decision == "revise" | `ITERATING` |
| 测试拒绝 | decision == "reject" | `ITERATING` 或 `GAP_RESOLVING` |

---

## 五、子流程 A：能力缺口补齐（同步路径）

```text
入口：BUILDING 阶段发现 blocking gap
  │
  ▼
Step A1: 解释缺口
  - Nanobot 用自然语言告诉用户缺了什么能力
  - 明确每个缺口为什么需要补
  │
  ▼
Step A2: 用户确认
  - 不能自动静默生成 Skill
  - 必须获得用户明确同意
  │
  ▼
Step A3: 调用 resolve_agent_workshop_blocking_gaps
  - 内部遍历每个 blocking gap
  - 对每个 gap：search → dedup → 创建/复用 Skill
  │
  ▼
Step A4: 能力重检 + 版本重建
  ├─ 自动续建成功 → 进入 BUILDING → 直接 Phase 3b
  └─ 只完成 Skill 生成/绑定 → 进入 READY_TO_BUILD → 再 build_version → BUILDING → Phase 3b
```

**FlowController 规则**：

- `GAP_RESOLVING` 阶段允许：`resolve_gaps`, `search_capabilities`, `inspect_*`
- `GAP_RESOLVING` 阶段禁止：`real_data_test`, `publish_version`

---

## 六、子流程 B：真数据测试与评估

```text
入口：BUILDING 阶段无 blocking gap
  │
  ▼
Step B1: 选择测试样本
  - 默认使用 version 自带样本或用户指定股票
  │
  ▼
Step B2: 执行 debug/run
  - UniversalAgent 按 execution_plan 调用工具
  - 产出完整报告
  │
  ▼
Step B3: LLM 评估
  - 多个维度打分
  - 检查：工具调用、输出字段、来源标注、假设说明
  │
  ▼
Step B4: 决策
  - pass → PUBLISHING
  - revise → ITERATING
  - reject → 分析是否需要新能力（GAP_RESOLVING）或直接迭代
```

---

## 七、Skill 独立生命周期

```text
需求分析
  │
  ▼
代码生成（多轮迭代）
  │
  ▼
沙箱验证
  │
  ▼
静态校验
  │
  ▼
注册到 ToolRegistry + CapabilityIndex
  │
  ▼
被 Agent 绑定使用
```

**关键约束**：Skill 不是终点。Skill 生成完成后必须回到父 Agent 的构建/测试链路。

---

## 八、Agent 与 Skill 状态联动时间线

```text
Agent:  需求确认 → Draft → 构建v1 → 测试v1 → revise → 构建v2 → 测试v2 → pass → 发布
          │                      │           │
          │                  发现 gap        │
          │                      │           │
          │               Skill1 生成       │
          │               Skill2 生成       │
          │                      │           │
          │               补齐后重建v2       │
          └──────────────────────┴───────────┘
```

**规则**：

- Skill 必须关联到 Agent 的某个 gap
- Skill 完成后，Agent 必须重新 build/test
- Skill 不能脱离 Agent 独立发布

---

## 九、状态机驱动层（FlowController）

> 详见 [agent-workshop-nanobot-skill-architecture.md](agent-workshop-nanobot-skill-architecture.md#8-agentbuilderflowcontroller状态机驱动层) 第 8 节。

Agent Builder FlowController 是 IntentContext 的补充层：

- **IntentContext**：记录"现在是谁、做什么、什么阶段"
- **FlowController**：规定"现在能调用什么工具、不能调用什么工具、下一步去哪"

### 状态机链路

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
                                                       │                         ▼
                                                       │                    BUILDING
                                                       │                         │
                                                READY_TO_BUILD              无 blocking gap
                                                       │                         │
                                                       │                         ▼
                                         auto-build 失败                       TESTING
                                          (blocking gap)                         │
                                               │                                 ▼
                                               ▼                            EVALUATING
                                         GAP_RESOLVING                       │    │    │
                                               │                           pass  │  revise
                                               ├── 自动续建成功 → BUILDING     │    │    │
                                               └── 需手动构建 → READY_TO_BUILD ▼    │    ▼
                                                                             PUBLISHING │ ITERATING
                                                                                  │         │
                                                                                  ▼         │
                                                                             PUBLISHED     │
                                                                                  └─────────┘
                                                                               回到 BUILDING
```

### Nanobot 行为变化

| 之前（无 FlowController） | 现在（有 FlowController） |
|---|---|
| 靠工具 `when_to_use` 和分散规则猜下一步 | System Prompt 明确注入：允许/禁止/推荐 |
| 自动构建后又调 `analyze_gaps` | 明确禁止：🚫 `analyze_gaps`（已内部完成） |
| 确认阶段可能直接生成 | 明确禁止：只有 `generate_confirmed` 一个合法操作 |
| 测试未通过就尝试发布 | 明确禁止：`publish_version` 只能在 pass 后调用 |
| Skill 完成后不知道下一步 | 明确约束：成功自动续建 → BUILDING；需手动构建 → READY_TO_BUILD；再进入 TESTING |

### 注入格式

每轮 System Prompt 自动注入（仅当 IntentContext 有 spec_id 时）：

```markdown
## 🔒 Agent Builder 流程约束（必须遵守）

当前阶段：版本已构建：自动构建完成，准备测试
✅ 当前阶段可以调用的工具：...
🚫 严禁在当前阶段调用以下工具：...
⭐ 推荐下一步：调用 run_agent_workshop_real_data_test
```

---

## 十、核心状态枚举

| 实体 | 状态 |
|---|---|
| **AgentSpec** | `draft` → `planning` → `testing` → `candidate` → `published` |
| **AgentVersion** | `draft` → `testing` → `active` → `archived` |
| **AgentWorkshopStage** | `gathering` → `planning` → `gap-analysis` → `building` → `evaluating` → `completed` |
| **SkillSession** | `created` → `generating` → `validating` → `completed/failed` |
| **FlowPhase** | `IDLE, EXPLORING, CAPABILITY_CHECK, DRAFT_PREPARING, CONFIRMATION_PENDING, GENERATING, READY_TO_BUILD, BUILDING, TESTING, EVALUATING, ITERATING, PUBLISHING, PUBLISHED` |

**说明**：

- 用户视角 5 个主阶段：需求讨论、生成确认、版本构建、测试评估、发布迭代
- 内部状态机 12 个细粒度阶段：为了卡住每个容易出错的转换节点

---

## 十一、已解决的问题

| # | 问题 | 解决方式 |
|---|---|---|
| 1 | 自动构建后重复 gap 检查 | `build_version` 内嵌真实 gap 分析；`BUILDING` 阶段禁止 `analyze_gaps` |
| 2 | Agent 名称/目标漂移 | `IntentContext` + `_auto_update_intent` + 工具调用前 spec_id 校验 |
| 3 | 删除旧 Agent 后同名重建复用旧方案 | MEMORY.md 写入删除声明；System Prompt 提示旧方案失效 |
| 4 | 多 Agent 对话导致进度返回全局 | `spec_focus` 块 + thread_context.spec_id 过滤 |
| 5 | Workshop 会话丢失导致 gap 检查失败 | 无 session 时基于 spec 重跑 gap 分析 + 工具覆盖检查 |
| 6 | 选中 Agent 后聊天区显示 Workshop 内部消息 | `displayedMessages` 只展示 nanobot 聊天历史 |
| 7 | 内部 worker 会话混入用户列表 | 过滤 `agent-workshop-eval-*` / `agent-workshop-worker-*` 会话 |
| 8 | External Skill 绑定但不调用 | `debug_version` 合并 Runtime `effective_tools` |
| 9 | execution_plan 不注入 Runtime | `UniversalAgent.execute()` 注入执行计划强约束 |
| 10 | prompt_overrides 不生效/不持久化 | 覆盖到模板 + debug 时自动重建模板 |
| 11 | LLM review 缺字段崩溃 | `_require_list_field` lenient 模式 |
| 12 | 工具元数据缺失导致 LLM 误判 | 补全 `capability_tags` / `tool_role_hint` / `not_replacement_for` |
| 13 | auto-build 因 blocking gap 失败不进入 GAP_RESOLVING | `generate_confirmed` 根据错误类型设置 `gap_resolving` |
| 14 | thread_context.intent 跨轮丢失 | schema/service 持久化 `intent` / `has_blocking_gaps` / `evaluation_status` |

---

## 十二、仍待解决的问题

### 问题 1：异步 gap resolution 不在 FlowController 主链路内

**现状**：

- `start_agent_workshop_gap_resolution` 创建后台 job
- worker 轮询处理每个 gap 的 Skill 生成
- 用户通过 `inspect_agent_workshop_gap_resolution` 查询进度
- job 完成后**不会自动更新 IntentContext 或推进 Agent 阶段**

**风险**：

- 用户走异步路径补 gap 后，FlowController 不知道 job 已完成
- Nanobot 可能不知道该回到 `BUILDING` / `READY_TO_BUILD`
- 形成流程旁路

**后续处理方向**：

1. worker 完成全部 gap 后，自动更新 `IntentContext.stage = BUILDING/READY_TO_BUILD`
2. `inspect_agent_workshop_gap_resolution` 返回时附带 `next_action`
3. 或：主链路默认走同步 `resolve_agent_workshop_blocking_gaps`，异步仅作为批量重试后台机制

**优先级**：中。当前主链路（同步）已稳定，异步路径可后续补齐。

---

## 十三、设计优化建议

1. **UI 只展示 5 个用户主阶段**，内部保留 12 阶段状态机
2. **前端读取 `flow_phase` 控制按钮状态**（可选），避免 UI 和后端允许的操作不一致
3. **ITERATING 阶段根据 evaluator evidence 细化推荐** ✅ 已实现
   - `tool_usage` / 缺能力 → `resolve_gaps`
   - `runtime_output` / 运行失败 / 样本异常 → 重跑 `real_data_test`
   - `execution_plan` / `output_coverage` / `reasoning_quality` / `constraint_control` / `numeric_traceability` / `project_memory_binding` → `iterate_version`
4. **后续把异步 gap 纳入 FlowController 管理**

---

## 十四、核心设计原则

```text
1. LLM 负责推理和表达
2. FlowController 负责约束执行路径
3. tool_trace 负责证明真的执行过
4. evaluator 负责验收是否合格
5. Skill 生成完成后必须回到父 Agent
```
