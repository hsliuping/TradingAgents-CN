# Agent Builder 工作流完整参考手册

> 版本：v3.0 | 更新：2026-07-01 | 源文件：`core/embedded_nanobot/workflows/agent_builder_nodes.py`、`agent_builder_conditions.py`

---

## 一、流程图

```
START
  │
  ▼
┌─────────────────────────┐
│ ① 需求探索               │
│ node_requirement_intake  │
│ 工具：prepare_agent_     │
│       requirement_intake │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ ② 等待确认               │
│ node_wait_intake_        │
│ confirmation             │
│ await_user = True        │
└───────────┬─────────────┘
            │ 用户回复
            ▼
       [意图分类]
            │
            ▼
┌─────────────────────────┐
│ ③ 需求确认               │
│ node_requirement_        │
│ confirmation             │
│ 工具：prepare_agent_     │
│       generation_        │
│       confirmation       │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ ④ 等待确认               │
│ node_wait_requirement_   │
│ confirmation             │
│ await_user = True        │
└───────────┬─────────────┘
            │ 用户回复
            ▼
       [意图分类]
            │
            ▼
┌─────────────────────────┐
│ ⑤ 缺口分析               │
│ node_gap_analysis        │
│ 工具：analyze_agent_     │
│       workshop_gaps      │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ ⑥ 方案生成               │
│ node_plan_generation     │
│ 工具：propose_agent_     │
│       build_plans        │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ ⑦ 等待选择               │
│ node_wait_plan_selection │
│ await_user = True        │
└───────────┬─────────────┘
            │ 用户回复
            ▼
       [意图分类]
            │
            ▼
┌─────────────────────────┐
│ ⑧ 生成 Agent             │
│ node_generate_candidate_ │
│ agent                    │
│ 工具：generate_confirmed_│
│       candidate_agent    │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ ⑨ 构建版本（可选）       │
│ node_build_or_ready      │
│ 工具：build_agent_       │
│       workshop_version   │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ ⑩ 等待测试标的           │
│ node_wait_test_request   │
│ await_user = True        │
└───────────┬─────────────┘
            │ 用户给股票代码
            ▼
       [意图分类]
            │
            ▼
┌─────────────────────────┐
│ ⑪ 真数据测试             │
│ node_real_data_test      │
│ 工具：run_agent_workshop_│
│       real_data_test     │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ ⑫ 等待评估               │
│ node_wait_evaluation     │
│ await_user = True        │
└───────────┬─────────────┘
            │ 用户回复
            ▼
       [意图分类]
            │
            ▼
┌─────────────────────────┐
│ ⑬ 评估/发布              │
│ node_evaluate_or_publish │
│ 工具：[publish /         │
│       evaluate]（二选一） │
└───────────┬─────────────┘
            │
            ▼
      [回到 ⑬ 或 END]


任意阶段出错 → Ⓔ 错误恢复 → 用户决定重试/修改/取消
```

---

## 二、节点详表

| # | 节点函数 | 调用 LLM | required_tool_name | include_inspect_tools | stage | awaiting_user |
|---|----------|----------|--------------------|-----------------------|-------|---------------|
| 1 | `node_requirement_intake` | ✅ ReAct | `prepare_agent_requirement_intake` | True | `exploring`/`draft_preparing` | False |
| 2 | `node_wait_intake_confirmation` | ❌ | - | - | `exploring` | True |
| 3 | `node_requirement_confirmation` | ✅ ReAct | `prepare_agent_generation_confirmation` | **False** | `draft_preparing` | False |
| 4 | `node_wait_requirement_confirmation` | ❌ | - | - | `requirement_confirmation_pending` | True |
| 5 | `node_gap_analysis` | ✅ ReAct | `analyze_agent_workshop_gaps` | True | `capability_check` | False |
| 6 | `node_plan_generation` | ✅ ReAct | `propose_agent_build_plans` | True | `plan_selection_pending` | False |
| 7 | `node_wait_plan_selection` | ❌ | - | - | `plan_selection_pending` | True |
| 8 | `node_generate_candidate_agent` | ✅ ReAct | `generate_confirmed_candidate_agent` | True | `generating` | False |
| 9 | `node_build_or_ready` | ⚠️ 条件 | `build_agent_workshop_version` | True | `building`/`skipped` | False |
| 10 | `node_wait_test_request` | ❌ | - | - | `testing` | True |
| 11 | `node_real_data_test` | ✅ ReAct | `run_agent_workshop_real_data_test` | True | `testing` | False |
| 12 | `node_wait_evaluation` | ❌ | - | - | `evaluating` | True |
| 13 | `node_evaluate_or_publish` | ✅ ReAct | **列表**: `[publish..., evaluate...]` | True | `evaluating`→`completed` | True |
| Ⓔ | `node_error_recovery` | ❌ | - | - | 不变 | True |
| - | `node_classify_user_intent` | ✅ 直接 | - | - | 不变 | False |

> `include_inspect_tools=True` 时，ReAct 循环额外注入 `inspect_agent_workshop_assets` 和 `search_project_capabilities` 两个辅助工具。

---

## 三、各节点提示词原文

### 3.1 意图分类提示词（`node_classify_user_intent`）

`node_classify_user_intent` 不调用 `_run_node_llm`，而是直接用 LLM 分类。根据 `current_node` 选择不同的提示词构建函数。

#### 3.1.1 确认阶段（`_build_confirmation_prompt`）

适用节点：`wait_intake_confirmation`、`wait_requirement_confirmation`

```
你是意图分类器。用户在 Agent 构建流程的需求确认阶段。

## 当前节点
{node_desc}
上一条待确认问题：{pending_q}
Agent 名称：{spec_name}

## 最近 3 轮对话历史
{recent_history}

## 意图类别
- confirmed：用户确认，可以推进下一步（如"好的""可以""确认""没问题""就这样"）
- revise：用户要修改/补充需求（如"加一个维度""改输出格式""换个方向"）
- explore_more：探讨/提问，没有明确推进指令
- cancel：取消/结束

## 输出格式（严格 JSON）
{"intent": "confirmed|revise|explore_more|cancel", "confidence": 0.85, "reason": "结合对话历史判断用户意图"}

只输出 JSON。
```

#### 3.1.2 方案选择阶段（`_build_plan_selection_prompt`）

适用节点：`wait_plan_selection`

```
你是意图分类器。用户在 Agent 构建流程的方案选择阶段。

## 当前节点
Agent「{spec_name}」的方案已生成，等待用户选择。

可选方案：
{opts_desc}

方案 index → id 映射：
{options_json}

## 最近 3 轮对话历史
{recent_history}

## 意图类别
- select_option：用户选了某个方案（如"B""方案B""第二个""选A"）
  → 输出 selected_index 或 selected_id
- confirmed：用户说"确认""推荐""按默认"→ 使用推荐方案
- revise：用户想修改需求，回到需求阶段
- explore_more：用户问问题但没有选择
- cancel：取消

## 输出格式（严格 JSON）
{"intent": "select_option", "confidence": 0.95, "reason": "用户说了'B'", "selected_index": 2}
或 {"intent": "confirmed", "confidence": 0.9, "reason": "用户说按推荐的来"}

只输出 JSON。
```

#### 3.1.3 测试/评估阶段（`_build_test_eval_prompt`）

适用节点：`wait_test_request`、`wait_evaluation`、`evaluate_or_publish`

```
你是意图分类器。用户在 Agent 构建流程的测试/评估阶段。

## 当前节点
{node_context}

## 最近 3 轮对话历史
{recent_history}

## 意图类别
- confirmed：用户确认推进（发布/开始测试等）
- retry：换数据重测，Agent 设计不变（如"换科大讯飞再测""用茅台跑一下""重测"）
- revise：修改 Agent 设计（如"加一个现金流维度""改输出格式"）
- new_agent：用户描述的 Agent 与「{spec_name}」完全不同，想创建新 Agent
- explore_more：探讨/提问，无明确操作指令
- cancel：取消/结束

## 关键区分
- "换一只股票测" → retry（只换测试数据，不改 Agent）
- "再加一个维度的分析" → revise（改 Agent 设计）
- "新建一个舆情分析Agent" → new_agent（全新 Agent，和当前无关）

## 输出格式（严格 JSON）
{"intent": "confirmed|retry|revise|new_agent|explore_more|cancel", "confidence": 0.85, "reason": "简短推理"}

**重要**：
- 如果用户消息含有股票代码（如 600519），或确认了 Agent 上一轮建议的代码，额外输出：
  {"intent": "confirmed", "confidence": 0.95, "reason": "用户给了代码/确认建议代码", "test_symbol": "600519"}
- 用户在 wait_evaluation 说"发布""上线"→ confirmed
- 不确定时宁可给低置信度

只输出 JSON。
```

#### 3.1.4 错误恢复阶段（`_build_error_prompt`）

适用节点：`error_recovery`

```
你是意图分类器。用户在 Agent 构建流程的错误恢复阶段。

## 当前节点
处理过程遇到了错误：{err_text}
用户需要决定下一步。

## 最近 3 轮对话历史
{recent_history}

## 意图类别
- confirmed：用户想重试失败步骤（如"重试""再来""retry"）
- revise：用户想修改需求，回到需求阶段
- explore_more：用户问问题但没有明确指令
- cancel：取消/结束

## 输出格式（严格 JSON）
{"intent": "confirmed|revise|explore_more|cancel", "confidence": 0.85, "reason": "用户说重试"}

只输出 JSON。
```

#### 3.1.5 通用兜底（`_build_generic_prompt`）

适用节点：未知节点

```
你是意图分类器。用户当前在 Agent 构建流程中（节点={current_node}）。

## 最近 3 轮对话历史
{recent_history}

## 意图类别
- confirmed：确认推进
- revise：修改需求
- new_agent：创建全新 Agent
- explore_more：探讨/提问
- cancel：取消

## 输出格式（严格 JSON）
{"intent": "confirmed|revise|new_agent|explore_more|cancel", "confidence": 0.7, "reason": "..."}

只输出 JSON。
```

---

### 3.2 `node_requirement_intake`（需求探索）

```
你是 TradingAgentsCN 平台的财经产品专家 + Agent 构建顾问。

当前阶段：需求探索。用户想创建一个分析 Agent。

你的任务：
1. 以财经产品专家身份，根据用户描述给出默认方案草稿（抛砖引玉）
2. 必须调用 prepare_agent_requirement_intake 工具将需求结构化
3. 不要列问卷，一次最多问 1 个关键问题
4. 默认 A 股、结构化 Markdown 报告、只做研究分析、包含风险提示

你必须调用 prepare_agent_requirement_intake 工具。
```

**ReAct 系统提示词**（拼接在业务 prompt 前面）：
```
{业务prompt}

## 重要：你必须使用函数调用（Function Calling）

当前阶段你有一个必须执行的函数：**prepare_agent_requirement_intake**

**操作规则**：
1. 先简要思考用户需求（1-2句话即可，放在回复开头）
2. 然后**立即通过 function_call 调用 prepare_agent_requirement_intake**
3. 不要在文本中描述"Action: 调用 xxx"，而是直接使用 API 的函数调用能力
4. 工具执行完毕后，系统会给你结果，你再基于结果回复用户

**禁止**：只输出文本而不调用函数。如果本轮没有调用 prepare_agent_requirement_intake，系统将自动强制执行。
```

**Step 2 提示词**（工具执行完毕后）：
```
工具已执行完毕。现在请基于工具返回的结构化数据，以财经产品专家的身份给用户专业、友好的回复。不要再次调用工具。
```

---

### 3.3 `node_wait_intake_confirmation`（等待确认）

不调用 LLM。仅设置 `current_node = "wait_intake_confirmation"`、`awaiting_user = True`。

若 `clarification_needed` 为 True，输出澄清文本：
```
抱歉，我没太听明白你的意思。

我们正在确认这个问题：**{pending_q}**

你可以：
- 回复「确认」「可以」按当前方案推进
- 回复你想修改的内容
- 回复「取消」结束
```

---

### 3.4 `node_requirement_confirmation`（需求确认）

```
你是 TradingAgentsCN 平台的财经产品专家。

当前阶段：需求确认。用户已确认基本方向，现在需要确认职责边界和输出形态。

已确认的需求：
- 名称：{spec_name}
- 摘要：{requirement_summary}

你的任务：
1. 调用 prepare_agent_generation_confirmation 生成确认稿
2. 确认稿只包含：职责范围、输出形态、非目标
3. 不要在此阶段展示工具候选、能力盘点、gap 分析、方案
4. 用户确认后，下一步是能力盘点

你必须调用 prepare_agent_generation_confirmation 工具。
```

**ReAct 系统提示词**：
```
{业务prompt}

## 重要：你必须使用函数调用（Function Calling）

当前阶段你有一个必须执行的函数：**prepare_agent_generation_confirmation**

**操作规则**：
1. 先简要思考用户需求（1-2句话即可，放在回复开头）
2. 然后**立即通过 function_call 调用 prepare_agent_generation_confirmation**
3. 不要在文本中描述"Action: 调用 xxx"，而是直接使用 API 的函数调用能力
4. 工具执行完毕后，系统会给你结果，你再基于结果回复用户

**禁止**：只输出文本而不调用函数。如果本轮没有调用 prepare_agent_generation_confirmation，系统将自动强制执行。
```

⚠️ 此节点 `include_inspect_tools=False`，不注入 inspect 辅助工具。

---

### 3.5 `node_wait_requirement_confirmation`（等待确认）

不调用 LLM。仅设置 `current_node = "wait_requirement_confirmation"`、`awaiting_user = True`。

---

### 3.6 `node_gap_analysis`（缺口分析）

```
你是 TradingAgentsCN 平台的财经产品专家。

当前阶段：缺口分析。需要扫描平台现有能力并分析是否满足 Agent 需求。

Agent 信息：
- 名称：{spec_name}
- 需求：{requirement_summary}

你的任务：
1. 调用 analyze_agent_workshop_gaps 做能力扫描和缺口分析
2. 无论是否有 blocking gaps，都进入方案生成
3. 不要在此阶段直接生成方案或Agent

你必须调用 analyze_agent_workshop_gaps 工具。
```

---

### 3.8 `node_plan_generation`（方案生成）

```
你是 TradingAgentsCN 平台的财经产品专家。

当前阶段：方案生成。gap 分析已完成，现在需要生成候选方案。

Agent 信息：
- 名称：{spec_name}
- Gap 报告：{gap_report的前1000字符}

你的任务：
1. 调用 propose_agent_build_plans 工具生成结构化候选方案
2. 用业务语言向用户展示方案选项
3. 用户选择方案后，系统会调用 generate_confirmed_candidate_agent

你必须调用 propose_agent_build_plans 工具。不能口头生成方案。
```

---

### 3.9 `node_wait_plan_selection`（等待选择）

不调用 LLM。仅设置 `current_node = "wait_plan_selection"`、`awaiting_user = True`。

若 `clarification_needed` 为 True，输出选项列表：
```
不太确定你选的是哪个方案。可选方案有：

{option_1_name}
{option_2_name}
...

你可以回复「方案A」「第二个」「选B」等来确认。
```

---

### 3.10 `node_generate_candidate_agent`（生成 Agent）

```
你是 TradingAgentsCN 平台的财经产品专家。

当前阶段：生成 Agent。用户已选择方案，现在需要生成 Agent。

Agent 信息：
- 名称：{spec_name}
- 选择的方案：{selected_plan_id}
- 候选方案：{candidate_plans的前500字符}
- Gap 报告：{gap_report的前500字符}

你的任务：
1. 调用 generate_confirmed_candidate_agent 生成 Agent
2. 报告生成结果（配置、工具绑定、Prompt）
3. 如果是 quick 方案，说明已接受的缺口

你必须调用 generate_confirmed_candidate_agent 工具。
```

---

### 3.11 `node_build_or_ready`（构建版本）

```
你是 TradingAgentsCN 平台的财经产品专家。

当前阶段：构建版本。Agent 已生成，现在需要构建 Workshop 版本。

你的任务：
1. 调用 build_agent_workshop_version 构建版本
2. 报告构建结果

你必须调用 build_agent_workshop_version 工具。
```

**跳过条件**：
- `selected_plan_id == "quick"` → 不调 LLM，直接跳过。
- `build_status == "built"` 且 `version_id` 存在 → 不调 LLM，已在 generate 阶段构建过。
- 无 `workshop_session_id` → 不调 LLM，跳过。

---

### 3.12 `node_wait_test_request`（等待测试标的）

不调用 LLM。仅设置 `current_node = "wait_test_request"`、`awaiting_user = True`。

若 `clarification_needed` 为 True，输出澄清文本。否则输出默认引导：
```
现在可以输入一个 A 股代码来测试 Agent 的效果，例如 600519（贵州茅台）。
```

---

### 3.13 `node_real_data_test`（真数据测试）

```
你是 TradingAgentsCN 平台的财经产品专家。

当前阶段：真数据测试。用户已提供测试标的。

Agent 信息：
- 名称：{spec_name}
- 测试标的：{test_symbol}

你的任务：
1. 调用 run_agent_workshop_real_data_test 进行真数据测试
2. 解读测试结果

你必须调用 run_agent_workshop_real_data_test 工具。
```

---

### 3.14 `node_wait_evaluation`（等待评估）

不调用 LLM。仅设置 `current_node = "wait_evaluation"`、`awaiting_user = True`。

默认输出：
```
测试完成。你可以：
- 回复「发布」上线 Agent
- 换一只股票「重测」
- 回复「再加一个维度」等修改需求
```

若已发布过，输出：
```
Agent 已发布到交易工作流。你可以：
- 输入新需求开始构建另一个 Agent
- 回复「重测」用另一只股票验证
```

---

### 3.15 `node_evaluate_or_publish`（评估/发布）

```
你是 TradingAgentsCN 平台的财经产品专家。

当前阶段：评估与发布。测试已完成，需要评估结果并决定是否发布。

Agent 信息：
- 名称：{spec_name}
- 测试结果：{test_result的前1000字符}

你的任务：
1. 如果测试通过，调用 publish_agent_workshop_version 发布
2. 如果测试有问题，调用 evaluate_agent_workshop_version 评估

你必须调用 publish_agent_workshop_version 或 evaluate_agent_workshop_version 工具。
```

**ReAct 系统提示词**（列表模式）：
```
{业务prompt}

## 重要：你可以使用以下函数调用（Function Calling）

当前阶段你可以使用的函数：**publish_agent_workshop_version、evaluate_agent_workshop_version**

**操作规则**：
1. 先简要思考（1-2句话即可，放在回复开头）
2. 然后根据情况选择调用适当的函数
3. 不要在文本中描述"Action: 调用 xxx"，而是直接使用 API 的函数调用能力
4. 工具执行完毕后，系统会给你结果，你再基于结果回复用户
```

> 注意：required_tool_name 为列表时不强制调用特定工具，LLM 自由选择。也不注入 inspect 辅助工具。

---

### 3.16 `node_error_recovery`（错误恢复）

不调用 LLM。仅设置 `current_node = "error_recovery"`、`awaiting_user = True`。

输出错误摘要：
```
处理过程中遇到了问题：

{error_1_details}
{error_2_details}
...

你可以：
- 回复「重试」重新执行失败的步骤
- 回复「跳过」忽略错误继续
- 回复「修改需求」回到需求阶段
- 回复「取消」结束
```

---

## 四、路由规则

### 4.1 `route_start`（入口路由）

| 条件 | 路由目标 |
|------|---------|
| `current_node` 为空或 `"START"` | `requirement_intake` |
| `current_node` 以 `wait_` 开头、`evaluate_or_publish`、`error_recovery` | `classify_intent` |
| 其他 | 直接返回 `current_node`（继续执行） |

### 4.2 `route_after_classify`（意图路由）

#### 全局规则（优先级最高）

| 意图 | 路由目标 |
|------|---------|
| `cancel`（任意节点） | `end` |
| `new_agent`（任意节点） | `end`（附加创建新 Agent 引导语） |
| `confidence < 0.7`（任意节点） | 回到当前 wait 节点 + `clarification_needed=True` |

#### 按 `current_node` 的路由

**`wait_intake_confirmation`**：
| 意图 | 路由目标 |
|------|---------|
| `confirmed` | `requirement_confirmation` |
| `select_option` | `requirement_confirmation` |
| `revise` | `requirement_intake` |
| `explore_more` | `wait_intake_confirmation`（clarification） |

**`wait_requirement_confirmation`**：
| 意图 | 路由目标 |
|------|---------|
| `confirmed` | `gap_analysis` |
| `select_option` | `gap_analysis` |
| `revise` | `requirement_confirmation` |
| `explore_more` | `wait_requirement_confirmation`（clarification） |

**`wait_plan_selection`**：
| 意图 | 路由目标 |
|------|---------|
| `select_option` | 解析 selected_index/id → `generate_candidate_agent`；失败则 `wait_plan_selection`（clarification） |
| `confirmed` | 使用 recommended_plan_id / 第一个选项 → `generate_candidate_agent`；失败则 `wait_plan_selection`（clarification） |
| `revise` | `requirement_intake` |
| `explore_more` | `wait_plan_selection`（clarification） |

**`wait_test_request`**：
| 条件 | 路由目标 |
|------|---------|
| `test_symbol` 不为空 | `real_data_test` |
| 其他 | `wait_test_request`（clarification） |

**`wait_evaluation`**：
| 意图 | 路由目标 |
|------|---------|
| `confirmed` | `evaluate_or_publish` |
| `select_option` | `evaluate_or_publish` |
| `revise` | `requirement_intake` |
| `retry` | `wait_test_request` |
| `explore_more` | `wait_evaluation`（clarification） |

**`evaluate_or_publish`**：
| 意图 | 路由目标 |
|------|---------|
| `confirmed` | `wait_test_request` |
| `retry` | `wait_test_request` |
| `select_option` | `wait_test_request` |
| `revise` | `requirement_intake` |
| `explore_more` | `evaluate_or_publish`（clarification） |

**`error_recovery`**：
| 意图 | 路由目标 |
|------|---------|
| `confirmed` | `_resolve_error_retry_target(state)` → 失败的节点 / `wait_test_request` |
| `retry` | `_resolve_error_retry_target(state)` → 同上 |
| `select_option` | `_resolve_error_retry_target(state)` → 同上 |
| `revise` | `requirement_intake` |
| `explore_more` | `error_recovery`（clarification） |

**未知节点** → `end`

### 4.3 非 LLM 条件路由（直接跳转，不经意图分类）

| 条件函数 | 源节点 | 路由逻辑 |
|----------|--------|---------|
| `route_after_intake` | `requirement_intake` | cancel → `end`；有 `spec_id` + confirm/route_choice → `requirement_confirmation`；否则 → `wait_intake_confirmation` |
| `route_after_gap_analysis` | `gap_analysis` | 始终 → `plan_generation` |
| `route_after_plan_generation` | `plan_generation` | 始终 → `wait_plan_selection` |
| `route_after_generate` | `generate_candidate_agent` | errors → `error_recovery`；`selected_plan_id=="quick"` → `wait_test_request`；`build_status=="built"` → `wait_test_request`；有 `generated_agent` → `build_or_ready`；否则 → `error_recovery` |
| `route_after_build` | `build_or_ready` | `build_status` in ("built","skipped") → `wait_test_request`；"skipped_no_session" / errors → `error_recovery` |
| `route_after_test` | `real_data_test` | 无 errors → `wait_evaluation`；有 errors → `error_recovery` |

---

## 五、工具清单

### 5.1 核心流程工具

#### `prepare_agent_requirement_intake` — 生成 Agent 需求采集提纲

> 根据用户的初始创建请求，生成 Nanobot 下一轮应该追问的需求采集提纲，避免在需求仍模糊时直接生成 Agent。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `user_request` | `str` | required | 用户原始请求 |
| `target_responsibility` | `str` | "" | 当前已知的单一职责 |
| `desired_output_shape` | `str` | "" | 当前已知的输出形状 |
| `non_goals` | `str` | "" | 明确不做什么，逗号分隔 |
| `preferred_tools` | `str` | "" | 用户已指定或当前已知的偏好工具，逗号分隔 |
| `existing_agent_id` | `str` | "" | 现有 agent_id |
| `recommendation_policy` | `str` | "" | 是否允许输出交易建议/仓位/价格区间 |
| `valuation_method_scope` | `str` | "" | 估值方法边界 |
| `test_strategy` | `str` | "" | 生成后是否允许自动测试 |
| `preview_mode` | `str` | "" | 报告样式预览模式 |
| `report_section_scope` | `str` | "" | 报告章节边界 |

#### `prepare_agent_generation_confirmation` — 生成 Agent 创建确认稿

> 在真正写入数据库前，生成一份精简确认稿，明确职责边界、输出形状、工具绑定和覆盖风险，供用户确认。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `agent_id` | `str` | required | 候选 Agent ID |
| `agent_name` | `str` | required | 候选 Agent 显示名称 |
| `target_responsibility` | `str` | required | 单一职责的一句话描述 |
| `tool_ids` | `str` | required | 拟绑定工具 ID，逗号分隔 |
| `output_field` | `str` | "analysis_report" | 输出字段名 |
| `default_tools` | `str` | "" | 默认工具 ID，逗号分隔 |
| `desired_output_shape` | `str` | "结构化估值报告" | 期望输出形状描述 |
| `non_goals` | `str` | "" | 明确不做什么，逗号分隔 |
| `recommendation_policy` | `str` | "" | 是否允许输出交易建议/仓位/价格区间 |
| `valuation_method_scope` | `str` | "" | 估值方法边界 |
| `test_strategy` | `str` | "" | 生成后是否允许自动测试 |
| `preview_mode` | `str` | "" | 报告样式预览模式 |
| `report_section_scope` | `str` | "" | 报告章节边界 |
| `status` | `str` | "active" | 目标模板状态 |

#### `search_project_capabilities` — 搜索项目能力（保留：仅作 inspect 工具，无独立节点）

> 轻量搜索当前项目里可复用的工具、skills、外部技能和 MCP 能力。当前作为 `node_gap_analysis` 的 inspect 辅助工具注入，也可供智能助手直接调用。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `query` | `str` | required | 能力检索需求 |
| `top_k` | `int` | 8 | 返回结果条数，最大 20 |
| `bindable_only` | `bool` | True | 是否只返回可直接绑定的能力 |
| `source_types` | `str` | "builtin_tool,skill,external_skill,mcp_tool" | 按能力来源过滤 |

#### `analyze_agent_workshop_gaps` — 执行 Agent 工坊缺口分析

> 让 Nanobot 直接触发 Agent 工坊会话的缺口分析阶段，并返回结构化缺口摘要。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `session_id` | `str` | "" | Agent 工坊会话 ID |
| `agent_id` | `str` | "" | 候选 Agent ID |
| `agent_name` | `str` | "" | Agent 显示名称 |
| `target_responsibility` | `str` | "" | 单一职责描述 |
| `tool_ids` | `str` | "" | 候选工具 ID，逗号分隔 |

#### `propose_agent_build_plans` — 基于缺口分析生成候选方案

> 在需求确认后、根据 gap_report 生成 1-3 个 Agent 构建方案（完整版/快速版/缩小需求版），供用户选择。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `gap_report_json` | `str` | required | JSON 字符串，含 blocking_gaps、non_blocking_gaps、suggested_tools |
| `agent_responsibility` | `str` | "" | Agent 职责描述 |
| `agent_output_shape` | `str` | "" | Agent 输出形状描述 |

#### `generate_confirmed_candidate_agent` — 确认方案后生成候选 Agent

> 在用户明确选择方案后，一次性完成配置写入、提示词模板写入、工具绑定和干运行校验。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `agent_id` | `str` | required | 候选 Agent ID |
| `agent_name` | `str` | required | 候选 Agent 显示名称 |
| `target_responsibility` | `str` | required | 单一职责的一句话描述 |
| `tool_ids` | `str` | required | 拟绑定工具 ID，逗号分隔 |
| `system_prompt` | `str` | required | 系统提示词 |
| `user_prompt` | `str` | "" | 用户提示词 |
| `tool_guidance` | `str` | "优先使用已绑定工具获取真实数据..." | 工具使用指导 |
| `analysis_requirements` | `str` | "围绕单一职责完成任务..." | 分析要求 |
| `output_format` | `str` | "请输出结构化结论..." | 输出格式 |
| `constraints` | `str` | "不要超出该 Agent 的单一职责范围。" | 约束条件 |
| `output_field` | `str` | "analysis_report" | 输出字段名 |
| `workflow_stage` | `str` | "analyst" | 工作流阶段 |
| `report_label` | `str` | "" | 报告展示标签 |
| `show_in_reports` | `bool` | True | 是否进入工作流报告列表 |
| `execution_order` | `int` | 50 | 工作流展示/执行顺序 |
| `template_name` | `str` | "" | 模板名称 |
| `default_tools` | `str` | "" | 默认工具 ID |
| `max_tool_calls` | `int` | 5 | 最大工具调用次数 |
| `category` | `str` | "analyst" | Agent 分类 |
| `callable_surfaces` | `str` | "assistant,workflow,agent" | 允许调用入口 |
| `input_mode` | `str` | "standalone" | 输入模式 |
| `enabled` | `bool` | True | 是否启用 |
| `status` | `str` | "active" | 模板状态 |
| `sync_to_workshop_draft` | `bool` | True | 是否同步创建 Agent 工坊 Draft |
| `auto_build_workshop_version` | `bool` | True | 是否自动生成可测试版本 |
| `confirmed` | `bool` | False | 是否已拿到用户明确确认 |
| `allow_overwrite` | `bool` | False | 是否允许覆盖现有配置 |
| `selected_plan_id` | `str` | "" | 用户选择的方案 ID |
| `acknowledged_gaps` | `str` | "" | 已知晓并接受的 blocking gaps |
| `capability_inventory_json` | `str` | "" | 能力盘点 JSON |
| `gap_report_json` | `str` | "" | gap_report JSON |

#### `build_agent_workshop_version` — 生成 Agent 工坊版本草案

> 让 Nanobot 直接触发 Agent 工坊版本草案生成，并返回生成后的版本信息。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `session_id` | `str` | required | Agent 工坊会话 ID |

#### `run_agent_workshop_real_data_test` — 执行 Agent 工坊真数据测试

> 让 Nanobot 对指定 Agent 工坊版本执行一次真实股票样例测试，并自动记录评估结果到 Agent Workshop。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `version_id` | `str` | required | Agent 工坊版本 ID |
| `stock_symbol` | `str` | required | 真实股票代码 |
| `market_type` | `str` | "A股" | 市场类型 |
| `analysis_date` | `str` | "" | 分析日期 YYYY-MM-DD |
| `user_goal` | `str` | "" | 本次测试目标 |
| `user_feedback` | `str` | "" | 本次测试补充反馈 |
| `prompt_overrides_json` | `str` | "" | Prompt 覆盖 JSON |

#### `publish_agent_workshop_version` — 发布 Agent 工坊版本

> 在用户已经手动确认发布后，让 Nanobot 将已通过最新真数据测试评估的 Agent 工坊版本发布为 active。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `version_id` | `str` | required | Agent 工坊版本 ID |

#### `evaluate_agent_workshop_version` — 评估 Agent 工坊版本

> 让 Nanobot 对指定 Agent 工坊版本执行一次显式评估落库，并返回最新评估结果。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `version_id` | `str` | required | Agent 工坊版本 ID |
| `evaluation_type` | `str` | "production-review" | 评估类型 |
| `sample_set_id` | `str` | "" | 样本集 ID |
| `user_feedback` | `str` | "" | 评估补充反馈 |
| `benchmark_outputs_json` | `str` | "" | benchmark 输出数组 JSON |
| `runtime_result_json` | `str` | "" | 真实运行结果 JSON 对象 |

### 5.2 辅助 inspect 工具（注入到 ReAct 循环）

#### `inspect_agent_workshop_assets` — 查看 Agent 工坊资产

> 查看数据库中的 agent_specs 和 agent_versions 摘要，支持按关键词、workshop_session_id 或 spec_id/version_id/agent_id 精确核验。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `keyword` | `str` | "" | 按 spec 名称/目标、version agent_metadata 模糊筛选 |
| `workshop_session_id` | `str` | "" | 按 session_id 精确定位 |
| `spec_id` | `str` | "" | 按 spec_id 精确筛选 |
| `version_id` | `str` | "" | 按 version_id 精确筛选 |
| `agent_id` | `str` | "" | 按运行时 agent_id 精确筛选 |
| `limit` | `int` | 10 | 每类结果返回条数，最大 20 |
| `include_archived` | `bool` | False | 是否包含 archived 状态 |

（`search_project_capabilities` 同上，不再重复。）

### 5.3 其他工具（未被流程直接调用，但注册在 ToolRegistry 中）

| 工具 | 作用 |
|------|------|
| `inspect_runtime_agent_configs` | 查看数据库中的配置式 Agent 运行时定义 |
| `inspect_agent_blueprints` | 查看已注册 Agent 的元数据蓝图 |
| `get_agent_blueprint_details` | 查看单个 Agent 蓝图完整元数据 |
| `inspect_prompt_templates` | 查询数据库中 prompt_templates 模板摘要 |
| `get_prompt_template_detail` | 按 template_id 读取完整模板内容 |
| `get_effective_prompt_template` | 按系统真实优先级解析当前生效模板 |
| `get_current_thread_effective_prompt_template` | 基于当前线程上下文自动推断生效模板 |
| `create_or_update_runtime_agent_config` | 创建或更新运行时 Agent 配置 |
| `create_or_update_agent_workshop_draft` | 把候选 Agent 同步到 Agent 工坊 Draft 资产层 |
| `generate_agent_workshop_tooling_plan` | 触发工具需求草案生成 |
| `debug_agent_workshop_version` | 对版本执行真实股票样例运行（不落库） |
| `iterate_agent_workshop_version` | 基于指定版本发起下一轮迭代 |
| `create_or_update_universal_agent_prompt_template` | 为 UniversalAgent 创建或更新默认提示词模板 |
| `bind_agent_tools_and_validate_candidate` | 写入 tool_agent_bindings 并做干运行校验 |
| `resolve_agent_workshop_blocking_gaps` | 自动为每个 blocking gap 创建 Skill 生成会话 |
| `start_agent_workshop_gap_resolution` | 创建 gap resolution job 并返回 job_id |
| `inspect_agent_workshop_gap_resolution` | 查询 gap resolution job 的当前状态与每个 gap 的进度 |
| `cancel_agent_workshop_gap_resolution` | 将 pending/running 的 job 标记为 cancelled |
| `retry_agent_workshop_gap_resolution_item` | 将某个 gap 重新置为 pending |

---

## 六、`include_inspect_tools` 当前状态

| 节点 | include_inspect_tools | ReAct 可见工具 |
|------|-----------------------|---------------|
| `node_requirement_intake` | **False** | `prepare_agent_requirement_intake`（仅此一个） |
| `node_requirement_confirmation` | **False** | `prepare_agent_generation_confirmation`（仅此一个） |
| ode_gap_analysis\ | **False** | \nalyze_agent_workshop_gaps\（仅此一个） |
| `node_plan_generation` | **False** | `propose_agent_build_plans`（仅此一个） |
| `node_generate_candidate_agent` | **False** | `generate_confirmed_candidate_agent`（仅此一个） |
| `node_build_or_ready` | **False** | `build_agent_workshop_version`（仅此一个） |
| `node_real_data_test` | **False** | `run_agent_workshop_real_data_test`（仅此一个） |
| `node_evaluate_or_publish` | **False** | `publish_agent_workshop_version` + `evaluate_agent_workshop_version`（二选一） |

> 所有节点均不注入 inspect 辅助工具。\nalyze_agent_workshop_gaps\ 内部已做全面的多查询能力扫描，无需额外工具。\search_project_capabilities\ 和 \inspect_agent_workshop_assets\ 仍保留在工具注册表中，供智能助手直接调用。

---

## 七、ReAct 强制调用逻辑

### 何时触发强制调用

1. **LLM 调了别的工具但漏掉 required 工具** → `[MissingRequired]` → 用 `_build_force_call_params` 补调
2. **LLM 完全不调任何工具** → `[NoAction]` → 用 `_build_force_call_params` 强制调
3. **LLM 把工具调用输出为文本**（非 API function_call），从文本中解析到了其他工具但没 required 工具 → 同 1
4. **required 工具被调了但返回 status=error** → `[ToolReturnedError]` → 用默认参数重试一次

### 各工具的强制调用参数（`_build_force_call_params`）

| 工具 | 参数来源 |
|------|---------|
| `prepare_agent_requirement_intake` | `user_request` ← `state["user_message"]` |
| `prepare_agent_generation_confirmation` | `agent_id` ← `spec_id`（或 hash 兜底）；`agent_name` ← `spec_name`；`tool_ids` ← `proposed_plan.preferred_tools`（或 `capability_search_result.existing_tools` 兜底） |
| `analyze_agent_workshop_gaps` | `agent_id` ← hash 兜底；`agent_name` ← `spec_name`；`target_responsibility` ← `requirement_summary` |
| `propose_agent_build_plans` | `gap_report_json` ← `state["gap_report"]`；`agent_responsibility` ← `requirement_summary` |
| `generate_confirmed_candidate_agent` | 从 `original_user_request`、`spec_name`、`requirement_summary`、`candidate_plans[0]` 等重建完整参数 |
| `build_agent_workshop_version` | `session_id` ← `state["workshop_session_id"]` |
| `run_agent_workshop_real_data_test` | `version_id` ← `state["version_id"]`；`stock_symbol` ← `state["test_symbol"]` |

---

## 八、State 关键字段

| 字段 | 类型 | 说明 | 设置节点 |
|------|------|------|---------|
| `current_node` | str | 当前所在节点名 | 各节点 |
| `awaiting_user` | bool | 是否等待用户输入 | wait 节点设为 True |
| `stage` | str | 当前阶段标识 | 各节点 |
| `spec_name` | str | Agent 名称 | intake、confirmation |
| `spec_id` | str | Agent 规格 ID | confirmation |
| `requirement_summary` | str | 需求摘要 | intake |
| `original_user_request` | str | 用户原始请求 | intake |
| `user_message` | str | 当前轮用户消息 | graph 入口 |
| `final_response` | str | LLM 最终回复文本 | LLM 节点 |
| `workshop_session_id` | str | Agent 工坊会话 ID | gap_analysis、generate |
| `version_id` | str | Agent 版本 ID | generate、build |
| `tool_events` | list | 工具调用事件 | LLM 节点 |
| `test_symbol` | str | 测试股票代码 | classify_intent |
| `test_result` | dict | 测试结果 | real_data_test |
| `gap_report` | dict | 缺口分析报告 | gap_analysis |
| `capability_inventory` | dict | 能力清单 | capability_search |
| `candidate_plans` | list | 候选方案 | plan_generation |
| `pending_options` | list | 待选方案 | plan_generation |
| `selected_plan_id` | str | 已选方案 ID | classify_intent |
| `recommended_plan_id` | str | 推荐方案 ID | plan_generation |
| `confirmation_brief` | dict | 确认稿摘要 | requirement_confirmation |
| `generated_agent` | dict | 已生成 Agent 信息 | generate_candidate_agent |
| `build_status` | str | 构建状态 | generate、build_or_ready |
| `errors` | list | 错误列表 | 各节点 |
| `clarification_needed` | bool | 是否需要澄清 | classify_intent |
| `pending_question` | str | 待确认问题 | intake、confirmation |
| `user_intent` | str | 用户意图 | classify_intent |
| `intent_confidence` | float | 意图置信度 | classify_intent |
| `intent_reason` | str | 意图推理 | classify_intent |
| `message_history` | list | 对话历史（最多 20 条） | classify_intent |

---

## 九、源文件索引

| 文件 | 内容 |
|------|------|
| `core/embedded_nanobot/workflows/agent_builder_nodes.py` | 所有节点函数、`_run_node_llm`、`_run_react_loop`、`_strip_tool_call_xml`、`_parse_text_tool_calls`、`_build_force_call_params`、意图分类提示词构建函数 |
| `core/embedded_nanobot/workflows/agent_builder_conditions.py` | `route_start`、`route_after_classify`、`_is_cancel`、`_is_confirm`、`_resolve_plan_selection`、`_resolve_error_retry_target`、`_format_recent_history` |
| `core/embedded_nanobot/workflows/agent_builder_state.py` | `AgentBuilderState`、`new_agent_builder_state` |
| `core/embedded_nanobot/workflows/agent_builder_graph.py` | 图结构定义、节点→条件边映射 |
| `core/embedded_nanobot/workflows/agent_builder_store.py` | Checkpoint 持久化、`_KNOWN_KEYS` 白名单 |
| `core/tools/implementations/agent_builder/nanobot_agent_builder_tools.py` | 全部 30 个工具的定义和实现 |
| `core/embedded_nanobot/agent/tools/registry.py` | `ToolRegistry` 类 |
| `core/embedded_nanobot/runtime.py` | `_run_agent_builder_graph` — graph 与 runtime 的桥接 |
| `app/services/agent_workshop_service.py` | Agent 工坊旧版 Service 层、gap 分析提示词（含"原语"→已改为"Skill"） |
| `app/services/embedded_nanobot_service.py` | `chat` 方法 — SSE 流式入口，路由到 agent_builder_graph |
