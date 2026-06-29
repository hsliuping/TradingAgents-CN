# Agent 工坊 + Skill 完整生命周期流程图（v2 设计稿）

> 状态：设计稿，待用户确认后实现。
>
> 本版本把「确认后自动 gap 分析并阻塞构建」改为「确认前做能力盘点 + 方案选择，确认后按方案实现，测试后再迭代」。

---

## 一、目标

把用户需求稳定地转化为可测试、可发布、可复用的 Agent：

- 不漂移（不会生成错 Agent）
- 不反悔（确认前充分盘点能力，确认后不再推翻）
- 不重复（每个检查只在合适的阶段做一次）
- 不缺工具（必须按 execution_plan 调用关键工具）
- 可追溯（Agent → Gap → Skill → Test → Publish 全链路）

---

## 二、核心设计原则

1. **能力盘点必须发生在用户确认之前**
   - 在 `CONFIRMATION_PENDING` 阶段，用户必须已经清楚：
     - 系统有哪些能力
     - 缺什么能力
     - 用现有的能不能满足需求
     - 各方案的预期效果和风险

2. **用户确认的是「方案」，不是「需求」**
   - 不再只是"确认生成"
   - 而是让用户在多个可行方案中选择：
     - A. 完整方案（补齐缺口）
     - B. 快速方案（现有工具简化版）
     - C. 调整方案（缩小需求范围）

3. **确认后按方案实现，实现中遇到问题再反馈**
   - 不再因为 auto-build 发现 gap 就阻止构建
   - 如果实现过程中发现 Skill 完成不了，进入 ITERATING 向用户反馈

4. **测试评估是发现问题的第一现场**
   - 真数据测试 + LLM 评估产出 evidence
   - 根据 evidence 决定：补齐能力 / 迭代 Prompt / 重跑测试 / 发布

---

## 三、主流程（用户视角 v2）

```text
┌──────────────────────────────────────────────────────────────┐
│ 1. 需求讨论                                                  │
│    用户："我要一个能识别财报风险信号的助手..."                │
│    Nanobot：询问目标、维度、输出格式、样本股票               │
└───────────────────────────┬──────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ 2. 能力盘点                                                  │
│    Nanobot：                                                 │
│      - 扫描现有工具/Skill（search_project_capabilities）     │
│      - 运行真实缺口分析（_build_gap_analysis）               │
│      - 评估用现有工具能否满足需求                            │
└───────────────────────────┬──────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ 3. 方案选择与确认                                            │
│    Nanobot：给出 2-3 个候选方案（动态，非固定 A/B/C）        │
│    用户选方案，也可以质疑 gap 分析结果                       │
└───────────────────────────┬──────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ 4. 按方案实现                                                │
│    - 生成 Agent / Draft / Prompt / Runtime Config            │
│    - 如需补缺口：生成/复用 Skill                             │
│    - 实现中遇到问题 → 向用户反馈 → 调整方案                  │
└───────────────────────────┬──────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ 5. 真数据测试                                                │
│    Nanobot：运行 run_agent_workshop_real_data_test           │
│    系统：LLM 评估报告质量 + 工具调用覆盖率                   │
└───────────────────────────┬──────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ 6. 发布 / 迭代                                               │
│    评估通过 → publish_version                                │
│    评估失败 → 按 evidence 类型选择：                         │
│      - 缺能力 → resolve_gaps（含 Plan B 升级到 A）          │
│      - 输出格式/Prompt 问题 → iterate_version                │
│      - 运行失败/样本异常 → 重跑 real_data_test               │
└──────────────────────────────────────────────────────────────┘
```

---

## 四、内部详细流程（含分支 v2）

### Phase 1: 需求澄清（不变）

```text
用户输入
  │
  ▼
Nanobot 多轮询问
  │
  ▼
整理出明确的职责、维度、输出形态、排除项
```

**状态机阶段**：`EXPLORING`

---

### Phase 2: 能力盘点（新增，关键变化）

```text
需求明确后
  │
  ▼
search_project_capabilities（扫描 CapabilityIndex）
  │
  ▼
_build_gap_analysis(spec)（LLM 驱动的真实缺口分析）
  │
  ▼
生成能力盘点报告（capability_inventory + gap_report）
  │
  ▼
prepare_agent_generation_confirmation
  │
  ▼
输出：多方案确认稿
```

**状态机阶段**：`CAPABILITY_CHECK → DRAFT_PREPARING`

#### 技术要点

1. **`_build_gap_analysis` 在 prepare 阶段不能依赖 session**

   v2 把 gap 分析前移到 prepare 阶段，但此时用户尚未确认方案，Workshop session 还不应该创建。

   **定案：不在 prepare 阶段创建临时 session。**

   原因：

   ```text
   - 避免用户未确认时产生半成品 session / draft 脏数据
   - 避免 Agent Studio 提前出现未确认草稿
   - 避免额外 TTL / 清理任务 / session 状态语义混乱
   ```

   推荐抽出纯 gap 分析入口：

   ```python
   async def analyze_spec_gaps(
       spec: AgentSpec,
       capability_inventory: Optional[CapabilityInventory] = None,
       *,
       context: Optional[dict] = None,
   ) -> AgentWorkshopGapAnalysis:
       ...
   ```

   该入口只依赖：

   ```text
   AgentSpec
   CapabilityIndex / capability_inventory
   LLM gap prompt
   ```

   不依赖：

   ```text
   Workshop session
   version
   database 状态
   ```

   调用关系：

   ```text
   prepare_agent_generation_confirmation
     → 构造临时 AgentSpec（不落库）
     → search_project_capabilities
     → analyze_spec_gaps(spec, capability_inventory)
     → 输出多方案确认稿

   build_version
     → 读取已落库 spec
     → analyze_spec_gaps(spec, current_inventory)
     → 写 gap_report / version metadata
   ```

   持久化发生在用户确认之后：

   ```text
   用户选择方案
     → generate_confirmed_candidate_agent
       → 创建 Workshop session / Draft
       → 写入 selected_plan / capability_inventory / gap_report
       → build_version
   ```

2. **能力盘点分两步**

   ```
   Step 1: search_project_capabilities  → capability_inventory（浅层工具名匹配）
   Step 2: _build_gap_analysis(spec)    → gap_report（LLM 深度分析 blocking/non-blocking）
   ```

   两者互补：
   - capability_inventory 告诉我们有哪些工具
   - gap_report 告诉我们这些工具能不能覆盖 spec 需求

3. **能力盘点结果持久化**

   capability_inventory 和 gap_report 写入 workshop session（即使 session 是临时创建的），后续实现失败再回来时不需要重新盘点。

#### 关键输出

```json
{
  "capability_inventory": {
    "available_tools": [...],
    "available_skills": [...],
    "missing_capabilities": [...]
  },
  "gap_report": {
    "blocking_gaps": [
      {
        "gap_id": "financial_ratio_calculator",
        "description": "...",
        "confidence": "high",
        "why_blocking": "铁律禁止 LLM 自行计算"
      }
    ],
    "non_blocking_gaps": [
      {
        "gap_id": "industry_benchmark_comparison",
        "description": "...",
        "confidence": "medium",
        "impact": "缺少行业对标，但不影响核心风险信号"
      }
    ]
  },
  "candidate_plans": [
    {
      "plan_id": "A",
      "plan_name": "完整方案",
      "description": "补齐所有 blocking gaps，输出完整四色风险评级",
      "required_new_skills": ["financial_ratio_calculator", "risk_signal_aggregator"],
      "estimated_effort": "高",
      "risk": "需要生成新 Skill，可能失败或耗时",
      "recommended": true
    },
    {
      "plan_id": "B",
      "plan_name": "快速方案",
      "description": "用现有工具做简化版，不输出四色评级，只列关键指标",
      "required_new_skills": [],
      "estimated_effort": "低",
      "risk": "功能不完整，缺少聚合评级",
      "recommended": false
    },
    {
      "plan_id": "C",
      "plan_name": "调整方案",
      "description": "把需求缩小到「商誉减值风险识别」一个维度",
      "required_new_skills": [],
      "estimated_effort": "低",
      "risk": "只覆盖一个维度",
      "recommended": false
    }
  ],
  "pending_question": "你希望采用哪个方案？"
}
```

#### 方案数量：动态，不固定 3 个

| 场景 | 方案 |
|---|---|
| 0 个 blocking gap | 只有 **A. 直接生成** |
| 1-2 个 blocking gap | A. 完整版 / B. 快速版 |
| 3+ 个 blocking gap | A. 完整版 / B. 快速版 / C. 缩小需求 |
| 快速版不可行（现有工具覆盖 < 50%） | 不出 B |

#### gap 误判防护

1. gap 需要携带 `confidence`（high / medium / low）
2. Nanobot 在展示 capability_inventory 时允许用户质疑：
   - 用户："你说缺 ratio_calculator，但 get_financial_risk_factors 已经有了比率计算"
   - Nanobot 重新评估并确认 → gap 等级可能降低
3. `confidence=low` 的 blocking gap 不应阻止 Plan B

---

### Phase 3: 方案确认

```text
多方案确认稿
  │
  ▼
用户选择 A/B/C（或质疑 gap 分析结果）
  │
  ├─ 选 A（完整方案） → record selected_plan_id=A, acknowledged_gaps=[...]
  │                     intent.stage=CONFIRMATION_PENDING
  │
  ├─ 选 B（快速方案） → record selected_plan_id=B
  │                     intent.stage=CONFIRMATION_PENDING
  │
  ├─ 选 C（调整方案） → back to EXPLORING（需求重新澄清），不是 CAPABILITY_CHECK
  │                     因为问题不是能力不够，而是需求范围需要调整
  │
  └─ 质疑 gap 分析 → Nanobot 重新评估 → 更新 gap_report → 重新展示方案
```

**状态机阶段**：`CONFIRMATION_PENDING`

**关键规则**：

- `CONFIRMATION_PENDING` 阶段只允许：
  - 用户选择方案
  - 用户质疑 gap（重新评估）
  - 用户要求修改需求（回到 EXPLORING）
- 用户确认后调用 `generate_confirmed_candidate_agent(selected_plan_id=..., acknowledged_gaps=[...])`
- 持久化：`selected_plan_id` 和 `acknowledged_gaps` 写入 `IntentContext` + `thread_context.intent`

---

### Phase 4: 按方案实现

#### 分支 4a：完整方案（plan A）

```text
generate_confirmed_candidate_agent(selected_plan_id=A, acknowledged_gaps=[...])
  │
  ├─ 创建 Draft / Prompt / Runtime Config
  ├─ auto_build_workshop_version
  │    ├─ 记录 gap_report
  │    ├─ 保存 unresolved blocking gaps 到 version.agent_metadata
  │    └─ 构建版本（不阻塞）
  │
  ▼
进入 GAP_RESOLVING：补齐 blocking gaps
  │
  ▼
resolve_agent_workshop_blocking_gaps
  │
  ├─ 生成/复用 Skill
  ├─ 自动续建版本
  │
  ▼
BUILDING → 测试
```

**注意**：Plan A 的 GAP_RESOLVING 发生在 Agent 已生成之后。用户感知："Agent 已经创建了，现在系统在给它补齐 Skill"。比"构建前阻塞"好。

#### 分支 4b：快速方案（plan B）

```text
generate_confirmed_candidate_agent(selected_plan_id=B)
  │
  ├─ 创建 Draft / Prompt / Runtime Config
  │
  ├─ **Plan B 特化 Prompt**：
  │   系统根据 acknowledged_gaps 调整 Prompt 模板：
  │   - 不在 Prompt 中要求 LLM 输出它做不到的输出
  │   - 例如：Plan A prompt 含"输出四色风险评级（🟢🟡🟠🔴）"
  │          Plan B prompt 改为"列出各维度关键指标，标注异常值，不输出综合评级"
  │
  ├─ auto_build_workshop_version
  │    ├─ 记录 gap_report
  │    └─ 构建版本（跳过 blocking gaps）
  │
  ▼
BUILDING → 测试
```

**Plan B 升级到 Plan A 的路径**：

```text
Plan B → 测试 → 评估 → ITERATING
  → 用户说"报告不错，但我想加上四色评级"
  → GAP_RESOLVING → resolve_gaps（补齐当初跳过的 blocking gaps）
  → BUILDING → 测试 → 评估 → pass → PUBLISHING
```

#### 分支 4c：调整方案（plan C）

```text
用户选择 C
  │
  ▼
回到 EXPLORING（需求重新澄清），不是 CAPABILITY_CHECK
  │
  ▼
Nanobot 和用户重新讨论可接受的能力范围
  │
  ▼
需求明确后自然进入 CAPABILITY_CHECK
```

**为什么是 EXPLORING 不是 CAPABILITY_CHECK**：
选 C 说明需求范围太宽，不是能力不够。重新扫描不会改变结果。需要的是缩小需求后再看。

---

### Phase 5: 真数据测试

```text
BUILDING
  │
  ▼
run_agent_workshop_real_data_test
  │
  ▼
自动 evaluate_version
  │
  ├─ pass → PUBLISHING
  ├─ revise/reject → ITERATING
  └─ 运行失败 → ITERATING
```

**状态机阶段**：`BUILDING → TESTING → EVALUATING`

---

### Phase 6: 迭代

```text
EVALUATING
  │
  ▼
根据 evidence 分类（已实现 _derive_iterating_recommendation）
  │
  ├─ tool_usage / 缺能力 → GAP_RESOLVING → resolve_gaps
  │    注：含 Plan B 想升级到 Plan A 的场景
  │
  ├─ runtime_output / 样本异常 → 重跑 real_data_test
  │
  └─ execution_plan / output_coverage / reasoning_quality
      / constraint_control / numeric_traceability / project_memory_binding
      → iterate_version
```

**状态机阶段**：`EVALUATING → ITERATING → (GAP_RESOLVING | TESTING)`

---

## 五、关键 API 改动

### 1. `prepare_agent_generation_confirmation`

**当前输出**：单一确认稿 + 等待用户确认

**v2 输出**：能力盘点 + 多方案 + 等待用户选择

**内部两步**：

```text
Step 1: search_project_capabilities → capability_inventory
Step 2: _build_gap_analysis(spec)   → gap_report
```

```json
{
  "status": "ok",
  "confirmation_required": true,
  "confirmation_type": "plan_selection",
  "capability_inventory": {
    "available_tools": ["..."],
    "available_skills": ["..."],
    "missing_capabilities": ["..."]
  },
  "gap_report": {
    "blocking_gaps": [
      {
        "gap_id": "...",
        "description": "...",
        "confidence": "high",
        "why_blocking": "..."
      }
    ],
    "non_blocking_gaps": [...]
  },
  "candidate_plans": [
    {
      "plan_id": "A",
      "plan_name": "完整方案",
      "description": "...",
      "required_new_skills": ["..."],
      "estimated_effort": "高",
      "risk": "...",
      "recommended": true
    },
    {
      "plan_id": "B",
      "plan_name": "快速方案",
      "description": "...",
      "required_new_skills": [],
      "estimated_effort": "低",
      "risk": "...",
      "recommended": false
    }
  ],
  "recommended_plan_id": "A",
  "pending_question": "你希望采用哪个方案？",
  "suggested_user_reply": "选 A，补齐缺口做完整版",
  "note": "方案数量根据缺口情况动态生成（1-3个）。如果对缺口分析有疑问，可以直接质疑。"
}
```

### 2. `generate_confirmed_candidate_agent`

**当前参数**：`agent_name`, `agent_id`, `responsibility`, ...

**v2 新增参数**：

```json
{
  "selected_plan_id": "A",
  "acknowledged_gaps": ["financial_ratio_calculator", "risk_signal_aggregator"]
}
```

**行为差异**：

| 参数 | Plan A | Plan B |
|---|---|---|
| `selected_plan_id` | `"A"` | `"B"` |
| `acknowledged_gaps` | 列出所有需补齐的 gap | 空或列出已知缺口 |
| Prompt 模板 | 完整版（含四色评级） | 简化版（不要求做不到的输出） |
| 后续 | 自动进入 GAP_RESOLVING | 直接 BUILDING |

### 3. `build_version`

**当前行为**：发现 unresolved blocking gaps 抛异常

**v2 行为**：

```python
unresolved_blocking_gaps = self._find_unresolved_blocking_gaps(...)
if unresolved_blocking_gaps:
    logger.warning(
        f"版本构建完成，存在 {len(unresolved_blocking_gaps)} 个待验证缺口"
    )
    version.agent_metadata["unresolved_blocking_gaps"] = unresolved_blocking_gaps
    version.agent_metadata["build_warnings"] = [
        f"版本已构建，但存在 {len(unresolved_blocking_gaps)} 个待验证缺口"
    ]
    # 不抛异常，继续构建
```

### 4. IntentContext

**新增字段**：

```json
{
  "selected_plan_id": "A",
  "acknowledged_gaps": ["..."],
  "capability_inventory_summary": "..."
}
```

`acknowledged_gaps` 会被 FlowController 用于判断阶段：
- Plan A + acknowledged_gaps 非空 → GAP_RESOLVING
- Plan B + acknowledged_gaps 为空 → BUILDING
- Plan A 且无 unresolved gaps → BUILDING

### 5. Plan B 升级路径（新工具或复用 ITERATING）

Plan B 想升级到 Plan A，走标准 ITERATING 路径：

```text
select_plan: "upgrade_to_A"
→ 记录 acknowledged_gaps（当初跳过的那批）
→ 进入 GAP_RESOLVING
→ resolve_gaps
→ BUILDING
→ 测试
```

不是新概念，是 ITERATING + GAP_RESOLVING 的自然复用。

---

## 六、状态机调整

### 新增/调整阶段

| 阶段 | 说明 | 变化 |
|---|---|---|
| `CAPABILITY_CHECK` | 能力盘点 | 新增为独立阶段，运行真实 gap 分析 |
| `DRAFT_PREPARING` | 准备多方案确认稿 | 输出从单一确认稿改为多方案 |
| `CONFIRMATION_PENDING` | 等待用户选择方案 | 不再只是"确认/否认"，支持质疑 gap |
| `GENERATING` | 按选定方案生成 | 新增 `selected_plan_id` |
| `GAP_RESOLVING` | 补齐缺口 | 从"构建前阻塞"改为"方案 A 的实现步骤 / 测试失败后 / Plan B 升级" |
| `BUILDING` | 版本构建完成 | 允许存在待验证缺口 |
| `ITERATING` | 迭代改进 | 含 Plan B→A 升级、测试失败修复、Prompt 调整 |

### 阶段流转

```text
IDLE
  ↓ 用户表达创建意图
EXPLORING
  ↓ 需求明确
CAPABILITY_CHECK
  ↓ 扫描完成 + 缺口分析完成
DRAFT_PREPARING
  ↓ 多方案稿完成
CONFIRMATION_PENDING
  ├─ 选 A → GENERATING → GAP_RESOLVING → BUILDING
  ├─ 选 B → GENERATING → BUILDING
  ├─ 选 C → EXPLORING（重新沟通需求范围）
  └─ 质疑 gap → 重新评估 → 回到 DRAFT_PREPARING
BUILDING
  ↓
TESTING
  ↓
EVALUATING
  ├─ pass → PUBLISHING
  ├─ 缺能力（含 Plan B 升级）→ ITERATING → GAP_RESOLVING → BUILDING
  ├─ 输出/Prompt 问题 → ITERATING → TESTING
  └─ 运行失败 → ITERATING → TESTING
PUBLISHING
  ↓
PUBLISHED
```

---

## 七、用户对话示例

### 场景：财报风险信号识别器

**Nanobot（能力盘点后）**：

```text
基于你的需求，我做了能力盘点：

✅ 已有能力：
  - get_goodwill_analysis：商誉规模/占比/趋势
  - get_financial_risk_factors：应收周转率/趋势标签
  - get_cashflow_analysis：三类现金流
  - get_risk_event_flags_tool：风险事件标记

❌ 缺少能力：
  - 从原始科目计算风险比率的确定性工具（confidence: high）
  - 把多维度指标聚合为四色评级的工具（confidence: high）

我给你两个方案：

A. 完整方案（推荐）
   补齐两个 External Skill，输出完整四色风险评级。
   需要生成新 Skill，预计多轮验证。

B. 快速方案
   用现有工具做简化版，输出各维度指标但不输出统一四色评级。
   可立即构建和测试。

你希望采用哪个方案？如果有疑问可以直接告诉我。
```

**用户**："选 A，做完整版。"

**Nanobot**：

```text
你选择的是 A 方案（完整版）。
我现在生成 Agent，然后补齐两个 External Skill。
```

---

### 场景：用户选 Plan B 后想升级

**用户**（测试后）："报告挺详细的，但我想要四色评级，能加上吗？"

**Nanobot**：

```text
可以。这需要补齐当初跳过的两个 External Skill（financial_ratio_calculator 和 risk_signal_aggregator）。
我现在进入 GAP_RESOLVING 阶段，补齐后重新构建并测试。
```

---

### 场景：用户质疑 gap 分析

**Nanobot**：

```text
❌ 缺少 financial_ratio_calculator（confidence: medium）
```

**用户**："这个不是 get_financial_risk_factors 已经能算了吗？"

**Nanobot**：

```text
让我重新评估...

确认：get_financial_risk_factors 内部已被标记为 `capability_tags: [financial_risk]`，它可以返回应收周转率指标。
但商誉/净资产比率需要从 get_goodwill_analysis 和 get_balance_sheet_analysis 的交叉字段计算，当前没有任何工具做这个交叉计算。

所以 financial_ratio_calculator 的必要性调整为：
- 应收周转率：已覆盖 ✅
- 商誉/净资产、应收/营收：仍需补充 ⚠️（confidence: high）

更新后的方案...
```

---

## 八、与当前代码的差异

| 差异点 | 当前 | v2 |
|---|---|---|
| gap 分析时机 | build_version 内部 | prepare 阶段 |
| 用户确认内容 | 单一方案 | 动态多方案选择 |
| build_version 对 blocking gaps | 抛异常阻塞 | 记录并继续构建 |
| GAP_RESOLVING 触发 | 构建前阻塞 | 方案 A 的实现步骤 / 测试失败后 / Plan B 升级 |
| 用户感知 | "确认后又缺工具" | "确认前就知道风险和选择" |
| Prompt 模板 | 所有方案一样 | Plan A/B 有差异 |
| gap 误判处理 | 无 | confidence + 用户可质疑 |
| Plan B→A 升级 | 无路径 | ITERATING → GAP_RESOLVING |
| Plan C 回退 | 回 CAPABILITY_CHECK | 回 EXPLORING（需求重定义） |

---

## 九、实现优先级

### P0（必须，第一轮实现）

1. 抽出 `analyze_spec_gaps(spec, capability_inventory)` 纯 gap 分析入口，prepare 阶段不创建临时 session
2. `prepare_agent_generation_confirmation` 内部两步：`search_project_capabilities` + `analyze_spec_gaps`
3. `prepare` 输出多方案（动态数量，含 confidence）
4. `generate_confirmed_candidate_agent` 支持 `selected_plan_id` + `acknowledged_gaps`
5. Plan B 根据 `acknowledged_gaps` 调整 Prompt 模板（不要求做不到的输出）
6. `build_version` 不因 blocking gaps 阻塞，写 metadata
7. `FlowController` 新增 `CAPABILITY_CHECK` / `DRAFT_PREPARING` / 多方案 `CONFIRMATION_PENDING`
8. Plan C 回到 `EXPLORING` 而非 `CAPABILITY_CHECK`

### P1（重要，第二轮实现）

8. 方案 A 自动进入 `GAP_RESOLVING`
9. `IntentContext` 记录 `selected_plan_id` 和 `acknowledged_gaps`
10. 能力盘点结果持久化到 workshop session
11. Plan B 升级到 Plan A 路径（ITERATING → GAP_RESOLVING）
12. 用户质疑 gap 时的重新评估流程

### P2（优化，第三轮实现）

13. 能力盘点报告的可视化（前端展示方案卡片）
14. 根据历史 Skill 成功率自动调整方案推荐
15. 根据现有工具覆盖率决定方案 B 是否可行

---

## 十、待决策问题（已解决的划掉）

1. ~~方案数量：固定 A/B/C 还是动态？~~ → **动态 1-3 个，按 blocking gap 数量决定**
2. ~~默认推荐：是否 always 推荐完整方案？~~ → **动态推荐：gap=0 推荐直接生成，gap>0 推荐完整方案**
3. ~~方案 B 的边界：允许 LLM 自行计算？~~ → **Plan B Prompt 不要求做不到的输出，对应字段缺失标注**
4. ~~方案 C 的实现：回到什么阶段？~~ → **回到 EXPLORING（需求重定义），不是 CAPABILITY_CHECK**

---

## 十一、实现安全边界

v2 允许「先构建、后补齐」来改善用户体验，但必须加安全边界，避免半成品被误认为可发布版本。

### 1. 只有用户确认过的 gap 才允许不阻塞 build

`build_version` 只有在以下条件同时满足时，才允许把 blocking gap 记录为 unresolved 并继续构建：

```text
blocking_gap ∈ acknowledged_gaps
并且 selected_plan_id 明确允许该 gap 进入后续补齐流程
```

否则仍然必须阻塞。

```text
未被用户确认的 blocking gap
  → 不能静默写入 metadata
  → 必须回到能力盘点 / 方案确认阶段
```

这样可以保证：

```text
系统不会在用户不知道的情况下构建一个有关键缺口的版本。
```

### 2. unresolved gaps 禁止发布

带 unresolved gaps 的版本可以存在，但不能发布。

```text
带 unresolved gaps 的版本：
  ✅ 可以保存
  ✅ 可以继续补 Skill
  ✅ 可以内部测试
  ❌ 不能 publish
```

发布前必须满足：

```text
version.agent_metadata.unresolved_blocking_gaps == []
或所有 acknowledged_gaps 都已经被 resolved_tools / linked_skills 覆盖
```

这条规则的含义是：

```text
允许先搭架子，但不允许把半成品发布出去。
```

### 3. Plan B 禁止 LLM 自行计算关键审计指标

Plan B 是「快速简化版」，不是「让 LLM 绕过工具约束」。

如果缺少确定性计算工具，Plan B 只能：

```text
✅ 使用已有工具直接返回的指标
✅ 展示原始数据并标注信息缺口
✅ 明确说明：缺少确定性计算工具，未给出该比率/评级
❌ 不能让 LLM 自行计算关键审计指标
❌ 不能让 LLM 自行打四色风险评级
```

例如缺少 `financial_ratio_calculator` 时：

```text
允许：展示商誉金额、净资产、应收账款、营收等原始数据。
不允许：LLM 自行计算商誉/净资产、应收/营收并作为审计结论。
```

### 4. gap confidence 判定规则

`confidence` 不能随意生成，建议按以下规则判定：

| confidence | 判定依据 |
|---|---|
| `high` | 工具元数据明确标注 `not_replacement_for` 命中，且没有任何工具输出目标字段 |
| `medium` | 有工具语义上可能覆盖，但字段/输出形态/可复核性不确定 |
| `low` | 已有工具大概率覆盖，但能力索引或元数据不完整 |

处理规则：

```text
high confidence blocking gap → 默认进入 Plan A 补齐
medium confidence gap → 允许用户质疑，必要时重评估
low confidence gap → 不应阻止 Plan B，也不应直接强制生成新 Skill
```

### 5. disputed gap 的处理

如果用户质疑 gap，Nanobot 可以重新评估，但不能无限循环。

```text
同一个 gap 最多重评估 1-2 次。
如果仍无法判定，标记为 disputed_gap。
```

`disputed_gap` 由用户选择处理方式：

```text
A. 暂按缺口处理 → 进入 Plan A / GAP_RESOLVING
B. 暂按已有能力处理 → 进入 Plan B / BUILDING
C. 调整需求范围 → 回到 EXPLORING
```

### 6. selected plan 必须持久化到版本资产

`selected_plan_id` 不能只存在于对话上下文，还必须写入 Workshop 资产，方便后续追溯。

建议持久化位置：

```json
{
  "session.builder_contracts.selected_plan": {
    "plan_id": "complete",
    "display_label": "A. 完整方案",
    "acknowledged_gaps": ["financial_ratio_calculator"],
    "created_from_confirmation": true
  },
  "version.agent_metadata.selected_plan_id": "complete",
  "version.agent_metadata.acknowledged_gaps": ["financial_ratio_calculator"],
  "version.agent_metadata.unresolved_blocking_gaps": ["financial_ratio_calculator"]
}
```

这样以后查看 v1/v2 时，可以知道它当初是按哪个方案生成的。

### 7. 内部 plan_id 使用语义 ID，不使用 A/B/C

UI 可以展示 A/B/C，但内部不要长期依赖字母 ID。

建议内部 ID：

| UI 展示 | 内部 `plan_id` | 含义 |
|---|---|---|
| A | `direct` | 无 gap，直接生成 |
| A | `complete` | 完整方案，补齐 gap |
| B | `quick` | 快速方案，现有工具简化版 |
| C | `narrow` | 缩小需求范围 |

这样避免后续代码写出：

```python
if selected_plan_id == "A":
```

应该写：

```python
if selected_plan_id == "complete":
```

---

## 十二、附录：当前流程（v1，供对比）

```text
需求讨论
  ↓
prepare_agent_generation_confirmation（单一确认稿）
  ↓
用户确认
  ↓
generate_confirmed_candidate_agent
  ↓
auto_build_workshop_version
  ↓
内部真实 gap 分析
  ├─ 无 blocking gap → BUILDING → 测试
  └─ 有 blocking gap → 抛异常 → Nanobot 展示"缺口分析结果" → 用户困惑
```

问题：确认后才发现缺口，给用户"出尔反尔"的感觉。

---

## 十三、v2 对比 v1 的优势总结

| 维度 | v1 | v2 |
|---|---|---|
| gap 分析时机 | 构建时 | 确认前 |
| 用户知情权 | 确认后被告知"缺工具" | 确认前看到完整能力清单 |
| 用户选择权 | 无 | A/B/C 动态方案 |
| 构建可靠性 | 缺工具就抛异常 | 记录缺口继续构建 |
| 迭代灵活性 | 单一 revise 路径 | evidence 分三类精确路由 |
| 升级路径 | 无 Plan B→A | ITERATING 内支持 |
| gap 可质疑 | 无 | confidence + 用户质疑流程 |
| 返回认知 | "出尔反尔" | "先盘点再选择，按方案执行" |
