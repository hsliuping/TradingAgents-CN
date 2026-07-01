# Agent Builder 意图分类 v2：拓扑感知 + 置信度

## 1. 背景与问题

### 1.1 当前方案（v1）

```
用户消息 → classify_intent（LLM + 简单 prompt）
            ├─ LLM 成功 → 按返回的 intent 路由
            └─ LLM 失败 → _fallback_classify_intent（关键词硬匹配）
```

**Prompt 设计**：写死规则，例如"说'换个'后面的具体内容 → revise"。

**`_is_revise` / `_is_confirm` / `_is_retry` 等 fallback 函数**：纯关键词匹配。

### 1.2 v1 的三个缺陷

| # | 问题 | 根因 |
|---|---|---|
| 1 | "换一个股票再测试"被误判为 `revise`，进入需求分析 | prompt 规则"换个 → revise"无法区分"换数据"和"换设计" |
| 2 | 发布后用户回来聊天，系统不知道该怎么路由 | `evaluate_or_publish → END`，发布后状态丢失 |
| 3 | 用户在当前 Agent 聊天栏说"新建一个XX Agent"，系统茫然 | 缺少 `new_agent` 意图类别 |

本质原因：**LLM 不知道工作流的拓扑结构**，只能靠几条硬编码规则猜意图。

---

## 2. 新方案（v2）：拓扑感知 + 置信度

### 2.1 核心思路

**给 LLM 工作流全景图，让它自己推理。**

```
用户消息
  → classify_intent（LLM）：
      输入：工作流拓扑 + 当前节点 + Agent 状态 + 用户消息
      输出：{intent, confidence, reason}
  → route_after_classify：
      confidence >= 0.7 → 按 intent 路由
      confidence < 0.7  → clarification_needed = True，回到当前 wait 节点
  → wait 节点：
      若 clarification_needed → 输出举例澄清，引导用户表达清楚
```

### 2.2 为什么 LLM 在有限状态机里足够可靠

- 每个节点的可能路径只有 2-4 条（confirmed / revise / retry / cancel 等）
- LLM 不需要在无限空间里推理，只需在有限选项中选一个
- 拓扑提供了充分的上下文约束

---

## 3. LLM 输入：工作流拓扑 + 节点上下文

### 3.1 拓扑描述（classify_intent prompt 固定部分）

```
## Agent 创建工作流（有限状态机）

这是一条 Agent 从需求到发布上线的流水线。

### 节点及其职责

**需求阶段**
- requirement_intake：与用户讨论需求，产出需求草案
- requirement_confirmation：确认需求边界，定义输入输出字段和非目标

**设计阶段**
- capability_search：搜索平台可用的数据源、工具、分析方法
- plan_generation：根据需求 + 可用能力，生成执行方案
- generate_candidate_agent：根据方案生成 Agent 候选版本

**测试阶段**
- build_or_ready：构建 Agent 或标记为就绪
- wait_test_request：等待用户指定测试标的（股票代码或名称）
- real_data_test：使用真实市场数据跑一轮测试

**评估阶段**
- wait_evaluation：等待用户决策——发布、重测、修改还是取消
- evaluate_or_publish：评估测试结果，发布 Agent 上线

**异常处理**
- error_recovery：处理流程中的错误，等待用户决定重试/跳过/取消

### 关键路径（边的语义）

- 所有 wait_* 节点 → END：等待用户输入
- START → classify_intent → route_after_classify → 目标节点
- wait_test_request → real_data_test：用户提供了测试标的
- wait_evaluation → evaluate_or_publish：用户确认发布
- evaluate_or_publish → END：发布/评估完成
- real_data_test → wait_evaluation：测试完成，等待用户决策
```

### 3.2 动态上下文（每次 classify 时注入）

```
## 当前位置
用户当前在节点 [{current_node}]。
阶段：{stage}

## Agent 状态
- 名称：{spec_name}
- 是否已发布：{published_or_not}
- 测试状态：{test_status}
- 上次评估决策：{decision}

## 用户消息
"{msg}"
```

### 3.3 意图类别说明

```
## 可用的用户意图

- confirmed：确认、同意、推进当前流程（如"好的""继续""发布""上线"）
- revise：修改当前 Agent 的需求或设计（如"加一个现金流维度""改输出格式"）
- retry：用不同数据重新测试，Agent 设计不变（如"换一个股票测""用科大讯飞再跑一次"）
- select_option：从多个选项中选择一个（如"B方案""第二个"）
- new_agent：用户想创建一个全新的 Agent，与当前 Agent 无关
  （如"我要做个舆情分析Agent"）
- explore_more：用户还在探讨、提问题，没有给出明确指令
- cancel：取消当前流程、退出
```

### 3.4 置信度指导

```
## 置信度
- 0.9-1.0：意图非常明确，可以直接路由
- 0.7-0.9：有一定把握，可以路由
- 0.5-0.7：不太确定，建议让系统反问用户
- 0.0-0.5：完全不确定，必须反问

不确定时宁可低置信度，不要猜。有限状态机的好处是可能路径就那么几条，
搞不清楚就问，不会出大错。
```

### 3.5 输出格式

```json
{
  "intent": "confirmed|revise|retry|select_option|new_agent|explore_more|cancel",
  "confidence": 0.92,
  "reason": "用户站在 wait_evaluation 节点，Agent 已发布，说'换科大讯飞再测'——换测试数据不改设计，归类为 retry",
  "selected_index": null
}
```

---

## 4. 置信度驱动的澄清机制

### 4.1 路由决策

```python
# route_after_classify 中
confidence = state.get("intent_confidence", 0.0)

if confidence >= 0.7:
    # 正常路由
    route_by_intent(state)
else:
    # 低置信度 → 回到当前 wait 节点，触发澄清
    state["clarification_needed"] = True
    result = current_node  # 留在原地
```

### 4.2 澄清消息举例（各 wait 节点）

**wait_evaluation**：
> 我不太确定你的意思。比如你可以说：
> - "换一个股票再测试一下"——用新标的重新跑测试
> - "发布"——确认上线
> - "加一个现金流分析维度"——修改 Agent 设计
> - "取消"——结束当前流程
> 
> 请说得更具体一点。

**wait_test_request**：
> 请提供你想测试的股票，比如：
> - "测试贵州茅台"——用股票名称
> - "600519"——直接给股票代码

**wait_intake_confirmation / wait_requirement_confirmation**：
> 你可以回复：
> - "确认""好的"——推进下一步
> - "再加一个XX维度"——补充需求
> - "换个方向"——调整需求方向

**error_recovery**：
> 处理出了一些问题。你可以回复：
> - "重试"——再试一次
> - "跳过"——跳过当前步骤
> - "修改需求"——回到需求阶段调整

---

## 5. 发布后状态管理

### 5.1 问题

`evaluate_or_publish` 成功后 → END（硬边），下一次用户输入时 `current_node` 状态未定义。

### 5.2 方案

```python
# node_evaluate_or_publish 中
if pub_result:
    state["official_acceptance_decision"] = "published"
    state["current_node"] = "wait_evaluation"  # ← 关键改动
```

发布后并非结束，而是回到 `wait_evaluation`，Agent 进入"已发布 + 可继续交互"状态。

用户后续消息经过 `classify_intent`，LLM 看到：
- 当前节点 = `wait_evaluation`
- 决策 = `published`
- 自动推理：Agent 已上线，用户说"换股票测" → retry，"改设计" → revise（创建新版本），"新建别的" → new_agent

### 5.3 wait_evaluation 提示语适配

`node_wait_evaluation` 根据 `official_acceptance_decision` 判断：

- 未发布（`decision != "published"`）：展示"发布 / 重测 / 修改 / 取消"
- 已发布（`decision == "published"`）：展示"重测 / 修改（创建新版）/ 取消"

---

## 6. 新建 Agent 识别（new_agent 意图）

### 6.1 场景

用户在当前 Agent 的聊天栏里，说了完全不同的 Agent 需求：

> "我要新建一个舆情分析Agent，它要能跟踪社交媒体的情绪..."

### 6.2 LLM 推理

LLM 拿到：
- 当前 Agent 名称："股票估值分析师"
- 当前 Agent 功能：估值分析
- 用户消息：全新的舆情分析需求

→ `reason: "用户描述的 Agent（舆情分析）与当前 Agent（估值分析）功能完全不同，判定为 new_agent"`  
→ `confidence: 0.95`

### 6.3 路由

```python
# route_after_classify
elif intent == "new_agent":
    state["final_response"] = (
        f"当前是「{spec_name}」的会话。要创建「{提取的新Agent描述}」"
        f"需要回到工坊主页点击「新建Agent」。\n\n"
        f"需求已记录，需要我帮你切换到新 Agent 创建流程吗？"
    )
    result = "end"
```

---

## 7. Fallback 精简

### 7.1 原则

`_fallback_classify_intent` 只在 LLM 调用完全失败时使用。只做最简单的判断，**不试图替代 LLM 做精细推理**。

### 7.2 逻辑

```python
def _fallback_classify_intent(msg: str, current_node: str) -> Dict[str, Any]:
    """仅在 LLM 不可用时兜底。不猜精细意图，猜不出来就 explore_more。"""
    t = msg.strip().lower()
    
    # cancel：明确的取消信号
    if t in ("取消", "算了", "不做了", "结束"):
        return {"intent": "cancel", "confidence": 0.9, "reason": "fallback: 明确取消"}
    
    # confirmed：明确的确认信号
    if t in ("确认", "好的", "可以", "行", "ok", "yes", "对"):
        return {"intent": "confirmed", "confidence": 0.85, "reason": "fallback: 明确确认"}
    
    # select_option：单字母/数字
    if re.fullmatch(r'[a-d1-4]', t):
        return {"intent": "select_option", "confidence": 0.85, "reason": "fallback: 单字母选择"}
    
    # 其他：不猜，返回 explore_more + 低置信度
    return {"intent": "explore_more", "confidence": 0.3, "reason": "fallback: 无法判断"}
```

`_is_revise`、`_is_retry` 等精细函数不再在 `_fallback_classify_intent` 中使用。它们只在 `route_after_classify` 中作为**二次确认信号**（当 LLM 选了某个路径但需要额外验证时），但这超出了当前改动范围。

---

## 8. 实施计划

### 8.1 改动文件

| 文件 | 改动 |
|---|---|
| `agent_builder_nodes.py` | 重写 `node_classify_user_intent` 的 prompt（拓扑 + 上下文 + 置信度）；解析 confidence；`node_evaluate_or_publish` 发布后设 `current_node = "wait_evaluation"`；`node_wait_evaluation` 根据 `official_acceptance_decision` 调整提示语 |
| `agent_builder_conditions.py` | `route_after_classify` 增加 `new_agent` 分支；低置信度 → `clarification_needed`；`_fallback_classify_intent` 精简；`route_start` 确认 `wait_evaluation` 在白名单中 |
| `agent_builder_graph.py` | 无需改动（wait_evaluation 已在白名单中） |
| `agent_builder_state.py` | 新增字段 `intent_confidence: float`、`intent_reason: str`（可选） |

### 8.2 测试要点

| 场景 | 用户输入 | 当前节点 | 预期 intent | 预期置信度 |
|---|---|---|---|---|
| 换股票测试 | "换科大讯飞再测一下" | wait_evaluation | retry | >0.8 |
| 确认发布 | "发布""上线吧" | wait_evaluation | confirmed | >0.9 |
| 修改设计 | "加一个现金流分析" | wait_evaluation | revise | >0.8 |
| 发布后换股票 | "用茅台再跑一次" | wait_evaluation(published) | retry | >0.8 |
| 新建 Agent | "我要做个舆情Agent" | wait_evaluation | new_agent | >0.8 |
| 模糊表达 | "除了估值还想看别的" | wait_evaluation | explore_more | <0.6 |
| 确认需求 | "好的""可以" | wait_intake_confirmation | confirmed | >0.9 |

### 8.3 向后兼容

- 现有线上会话的 `current_node` 如果是 `evaluate_or_publish`，`route_start` 已经在白名单中，会路由到 `classify_intent`，不受影响
- `wait_evaluation` 节点已在 `route_start` 白名单中（确认）
- 新增 `new_agent` 意图不影响现有流程
