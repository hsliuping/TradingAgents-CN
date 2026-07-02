# Agent Builder 意图分类提示词（完整原文）

> 源文件：`core/embedded_nanobot/workflows/agent_builder_nodes.py`
> 导出时间：2026-07-01

---

## 0. 节点类型映射（`_classify_node_type`）

```python
def _classify_node_type(current_node: str) -> str:
    if current_node in ("wait_intake_confirmation", "wait_requirement_confirmation"):
        return "confirmation"
    if current_node == "wait_plan_selection":
        return "plan_selection"
    if current_node in ("wait_test_request", "wait_evaluation", "evaluate_or_publish"):
        return "test_eval"
    if current_node == "error_recovery":
        return "error"
    return "generic"
```

**没有按 stage 的专有提示词。** 意图分类只按节点类型区分（5 种），不按 stage（`exploring`、`draft_preparing` 等）区分。stage 只是状态标签，不影响提示词。

---

## 0b. 对话历史格式化（`_format_recent_history`）

```python
def _format_recent_history(state: AgentBuilderState, rounds: int = 3) -> str:
    """从 message_history 中取最近 N 轮对话，格式化为 prompt 可用的文本。"""
    history = state.get("message_history", []) or []
    recent = history[-(rounds * 2):]  # 每轮 = agent + user
    if not recent:
        return "（暂无对话历史）"
    lines = []
    for entry in recent:
        role = entry.get("role", "unknown")
        content = str(entry.get("content", ""))[:200]
        label = "Agent" if role == "agent" else "用户" if role == "user" else role
        lines.append(f"[{label}] {content}")
    return "\n".join(lines)
```

---

## 0c. 提示词分发（`_build_classify_prompt`）

```python
def _build_classify_prompt(state: AgentBuilderState, node_type: str) -> str:
    if node_type == "confirmation":
        return _build_confirmation_prompt(state)
    elif node_type == "plan_selection":
        return _build_plan_selection_prompt(state)
    elif node_type == "test_eval":
        return _build_test_eval_prompt(state)
    elif node_type == "error":
        return _build_error_prompt(state)
    else:
        return _build_generic_prompt(state)
```

---

## 1. 确认阶段（`_build_confirmation_prompt`）

**适用节点**：`wait_intake_confirmation`、`wait_requirement_confirmation`

```python
def _build_confirmation_prompt(state: AgentBuilderState) -> str:
    node = state.get("current_node", "")
    pending_q = state.get("pending_question", "") or ""
    msg = state.get("user_message", "") or ""
    spec_name = state.get("spec_name", "") or "未命名"
    recent_history = _format_recent_history(state, rounds=3)

    node_desc = {
        "wait_intake_confirmation": "需求探索阶段，Agent 刚提了需求草案和关键问题",
        "wait_requirement_confirmation": "需求确认阶段，Agent 刚确认了职责边界和输出形态",
    }.get(node, f"等待用户确认（{node}）")

    return f"""你是意图分类器。用户在 Agent 构建流程的需求确认阶段。

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
{{"intent": "confirmed|revise|explore_more|cancel", "confidence": 0.85, "reason": "结合对话历史判断用户意图"}}

只输出 JSON。"""
```

### 动态变量说明

| 变量 | 来源 | 示例 |
|------|------|------|
| `{node_desc}` | 根据 current_node 查表 | "需求探索阶段，Agent 刚提了需求草案和关键问题" |
| `{pending_q}` | `state["pending_question"]` | "你是否已经知道它必须依赖哪些工具或数据来源？" |
| `{spec_name}` | `state["spec_name"]` | "财报风险识别助手" |
| `{recent_history}` | `message_history` 最近 3 轮 | `[Agent] 确认一下...\n[用户] 好的` |

---

## 2. 方案选择阶段（`_build_plan_selection_prompt`）

**适用节点**：`wait_plan_selection`

```python
def _build_plan_selection_prompt(state: AgentBuilderState) -> str:
    msg = state.get("user_message", "") or ""
    pending_options = state.get("pending_options", []) or []
    spec_name = state.get("spec_name", "") or "未命名"
    recent_history = _format_recent_history(state, rounds=3)

    opts_lines = []
    for opt in pending_options:
        idx = opt.get("index", "")
        label = opt.get("name", opt.get("id", ""))
        rec = "（推荐）" if opt.get("recommended") else ""
        opts_lines.append(f"  {idx}. {label}{rec}")
    opts_desc = "\n".join(opts_lines)

    options_json = json.dumps(
        [{"index": o.get("index", ""), "id": o.get("id", "")} for o in pending_options],
        ensure_ascii=False,
    ) if pending_options else "[]"

    return f"""你是意图分类器。用户在 Agent 构建流程的方案选择阶段。

## 当前节点
Agent「{spec_name}」的方案已生成，等待用户选择。

可选方案：
{opts_desc}

方案 index → id 映射：
{options_json}

## 最近 3 轮对话历史
{recent_history}

## 意图类别
- select_option：用户选了某个方案（如"B""方案B""第二个""选A"）→ 输出 selected_index 或 selected_id
- confirmed：用户说"确认""推荐""按默认"→ 使用推荐方案
- revise：用户想修改需求，回到需求阶段
- explore_more：用户问问题但没有选择
- cancel：取消

## 输出格式（严格 JSON）
{{"intent": "select_option", "confidence": 0.95, "reason": "用户说了'B'", "selected_index": 2}}
或 {{"intent": "confirmed", "confidence": 0.9, "reason": "用户说按推荐的来"}}

只输出 JSON。"""
```

### 动态变量说明

| 变量 | 来源 | 示例 |
|------|------|------|
| `{spec_name}` | `state["spec_name"]` | "财报风险识别助手" |
| `{opts_desc}` | `pending_options` 格式化 | `  1. 方案A：等权综合评级（推荐）\n  2. 方案B：自定义权重` |
| `{options_json}` | `pending_options` 的 index→id 映射 | `[{"index": 1, "id": "plan_equal_weight"}, {"index": 2, "id": "plan_custom_weight"}]` |
| `{recent_history}` | `message_history` 最近 3 轮 | - |

---

## 3. 测试/评估阶段（`_build_test_eval_prompt`）

**适用节点**：`wait_test_request`、`wait_evaluation`、`evaluate_or_publish`

```python
def _build_test_eval_prompt(state: AgentBuilderState) -> str:
    current_node = state.get("current_node", "")
    msg = state.get("user_message", "") or ""
    spec_name = state.get("spec_name", "") or "未命名"
    published = "已发布" if state.get("official_acceptance_decision") == "published" else "未发布"
    test_status = state.get("test_result", {}).get("status", "未测试")
    recent_history = _format_recent_history(state, rounds=3)

    # 从历史中提取 Agent 建议的股票代码（不硬编码，LLM 自己判断）
    last_hint = ""
    if current_node == "wait_test_request":
        history = state.get("message_history", []) or []
        for entry in reversed(history):
            if entry.get("role") == "agent":
                content = str(entry.get("content", ""))
                m = re.search(r"\b(00\d{4}|30\d{4}|60\d{4}|68\d{4}|6\d{4})\b", content)
                if m:
                    last_hint = f"\nAgent 最近建议了股票：{content[:120]}"
                    break

    node_context = {
        "wait_test_request": (
            f"Agent「{spec_name}」已就绪，等待用户给出测试标的。{last_hint}\n"
            f"用户可能：直接给代码（如 600519）；确认 Agent 建议的代码；给股票名但没代码；问问题；取消。"
        ),
        "wait_evaluation": (
            f"Agent「{spec_name}」测试已完成（状态={test_status}），发布状态={published}。\n"
            f"用户可能：发布上线；换股票重测（不改设计）；修改 Agent 设计；新建其他 Agent；取消。"
        ),
        "evaluate_or_publish": (
            f"Agent「{spec_name}」正在评估阶段，测试状态={test_status}。\n"
            f"用户可能：重新测试；修改需求；取消。"
        ),
    }.get(current_node, f"Agent「{spec_name}」，节点={current_node}")

    return f"""你是意图分类器。用户在 Agent 构建流程的测试/评估阶段。

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
{{"intent": "confirmed|retry|revise|new_agent|explore_more|cancel", "confidence": 0.85, "reason": "简短推理"}}

**重要**：
- 如果用户消息含有股票代码（如 600519），或确认了 Agent 上一轮建议的代码，额外输出：
  {{"intent": "confirmed", "confidence": 0.95, "reason": "用户给了代码/确认建议代码", "test_symbol": "600519"}}
- 用户在 wait_evaluation 说"发布""上线"→ confirmed
- 不确定时宁可给低置信度

只输出 JSON。"""
```

### 动态变量说明

| 变量 | 来源 | 说明 |
|------|------|------|
| `{node_context}` | 根据 current_node 选择 | 包含 spec_name、test_status、published 状态、Agent 建议的股票提示 |
| `{spec_name}` | `state["spec_name"]` | Agent 名称 |
| `{test_status}` | `state["test_result"]["status"]` | "ok" / "error" / "未测试" |
| `{published}` | `state["official_acceptance_decision"]` | "已发布" / "未发布" |
| `{last_hint}` | 从 message_history 反向搜索 Agent 消息中的股票代码 | 仅 wait_test_request 时非空 |
| `{recent_history}` | `message_history` 最近 3 轮 | - |

---

## 4. 错误恢复阶段（`_build_error_prompt`）

**适用节点**：`error_recovery`

```python
def _build_error_prompt(state: AgentBuilderState) -> str:
    msg = state.get("user_message", "") or ""
    recent_history = _format_recent_history(state, rounds=3)
    errors = state.get("errors", []) or []
    err_lines = []
    for e in errors[-2:]:
        if isinstance(e, dict):
            err_lines.append(f"{e.get('node','?')}: {e.get('error','?')}")
    err_text = "; ".join(err_lines) if err_lines else "未知错误"

    return f"""你是意图分类器。用户在 Agent 构建流程的错误恢复阶段。

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
{{"intent": "confirmed|revise|explore_more|cancel", "confidence": 0.85, "reason": "用户说重试"}}

只输出 JSON。"""
```

### 动态变量说明

| 变量 | 来源 | 说明 |
|------|------|------|
| `{err_text}` | `state["errors"]` 最近 2 条的 node + error | `"generate_candidate_agent: tool_ids参数缺失"` |
| `{recent_history}` | `message_history` 最近 3 轮 | - |

---

## 5. 通用兜底（`_build_generic_prompt`）

**适用节点**：任何未明确分类的节点

```python
def _build_generic_prompt(state: AgentBuilderState) -> str:
    msg = state.get("user_message", "") or ""
    current_node = state.get("current_node", "")
    recent_history = _format_recent_history(state, rounds=3)

    return f"""你是意图分类器。用户当前在 Agent 构建流程中（节点={current_node}）。

## 最近 3 轮对话历史
{recent_history}

## 意图类别
- confirmed：确认推进
- revise：修改需求
- new_agent：创建全新 Agent
- explore_more：探讨/提问
- cancel：取消

## 输出格式（严格 JSON）
{{"intent": "confirmed|revise|new_agent|explore_more|cancel", "confidence": 0.7, "reason": "..."}}

只输出 JSON。"""
```

---

## 6. LLM 调用参数（`node_classify_user_intent` 主函数）

```python
response = await provider.chat_with_retry(
    messages=[
        {"role": "system", "content": classify_prompt},
        {"role": "user", "content": state.get("user_message", "")},
    ],
    model=model,
    temperature=0.1,
)
```

| 参数 | 值 | 说明 |
|------|-----|------|
| system | 上述 5 种 prompt 之一 | 根据 `_classify_node_type` 选择 |
| user | `state["user_message"]` | 当前用户消息 |
| model | 外部传入 | DeepSeek 等 |
| temperature | 0.1 | 极低温度，确保分类稳定 |

---

## 7. 意图类别全集

| 意图 | 含义 | 出现节点类型 |
|------|------|-------------|
| `confirmed` | 用户确认，推进下一步 | 所有类型 |
| `revise` | 修改需求，回到需求阶段 | 所有类型 |
| `explore_more` | 探讨/提问，无明确操作 | 所有类型 |
| `cancel` | 取消/结束 | 所有类型 |
| `select_option` | 选择了某个方案 | plan_selection |
| `retry` | 换数据重测 | test_eval |
| `new_agent` | 创建全新 Agent | test_eval, generic |
