# 架构优化验证测试计划

> 版本：v3.0 | 日期：2026-07-26 | 对应文档：architecture-optimization-reflection.md
>
> 验证对象：阶段一（v3.5.0）项1-4 + 阶段二（v3.6.0）项5-8 + 回归修复7项

---

## 前置条件

- [ ] 后端服务已启动（`.\start_dev.ps1 backend 3.0`）
- [ ] 前端服务已启动（`.\start_dev.ps1 frontend 3.0`）
- [ ] Docker 容器运行中（MongoDB:27019, Redis:6381）
- [ ] 有可用的大模型 API Key 配置

---

## 一、启动验证

启动后端，观察终端输出。

| 检查点 | 预期日志 | 状态 |
|---|---|---|
| HITL 定时清理已注册 | `🔄 HITL 待确认操作过期清理已配置（每 30 分钟）` | [ ] |
| Skill 审核定时清理已注册 | `🔄 Skill 审核过期清理已配置（每 30 分钟）` | [ ] |

---

## 二、项1 + 项5：质量门禁 + 质量指标

### 2.1 验证脚本（推荐）

```powershell
env\Scripts\python.exe scripts\validate_quality_gate.py
env\Scripts\python.exe scripts\validate_quality_metrics.py
```

### 2.2 手动验证

**步骤1：触发一次股票分析**

前端首页 → 输入股票代码（如 000001）→ 点击分析。

**步骤2：查看后端日志**

```powershell
findstr /i "QualityGate" logs\*.log
```

预期看到：
```
[QualityGate] market_analyst 报告质量通过
```

**步骤3：检查 quality_metrics 集合**

连接 MongoDB（端口 27019），执行：
```javascript
db.analysis_quality_metrics.find().sort({created_at:-1}).limit(1).pretty()
```

预期字段：`report_length`, `is_low_quality`, `quality_flags`, `llm_elapsed_seconds`, `llm_tokens_used`, `retry_count`

**步骤4：确认仅 critical 才标记 low_quality**

```javascript
// 应只有 severity=critical 的报告 is_low_quality=true
db.analysis_quality_metrics.find({is_low_quality:true}).forEach(doc => {
  print(doc.quality_flags.severity);
});
```

预期：所有 `is_low_quality=true` 的记录，其 `quality_flags.severity` 都是 `critical`。

### 2.3 验证 checklist

| # | 检查项 | 状态 |
|---|---|---|
| 2.1 | `quality_gate.py` 存在（`core/agents/quality_gate.py`） | [ ] |
| 2.2 | 正常报告通过门禁 | [ ] |
| 2.3 | 质量指标写入 `analysis_quality_metrics` 集合 | [ ] |
| 2.4 | warning 级别不标记 `is_low_quality` | [ ] |

---

## 三、项2：复盘反思提炼

### 3.1 验证脚本（推荐）

```powershell
env\Scripts\python.exe scripts\validate_trade_review_reflection.py
```

### 3.2 手动验证

**步骤1：触发一次交易复盘**

前端 → 交易复盘 → 选择一只股票 → 提交复盘。

**步骤2：查看日志**

```powershell
findstr /i "trade_lesson\|复盘.*反思" logs\*.log
```

预期看到：
```
[trade_review] 已写入 trade_lesson 教训: user=xxx symbol=XXXXXX
```

**步骤3：检查 mem0 记忆**

```javascript
db.mem0_memories.find({"metadata.memory_kind": "trade_lesson"}).sort({created_at:-1}).limit(1).pretty()
```

预期：存在 `metadata.memory_kind="trade_lesson"` 的记录，内容为结构化反思（含 reasoning/improvement/summary 等字段），而非复盘原文。

### 3.3 验证 checklist

| # | 检查项 | 状态 |
|---|---|---|
| 3.1 | `_reflect_trade_review_lesson()` 在 `trade_review_service.py` 中定义 | [ ] |
| 3.2 | 复盘完成主流程中调用了反思方法 | [ ] |
| 3.3 | mem0 中出现 `memory_kind=trade_lesson` 的结构化经验 | [ ] |

---

## 四、项3：研究员反思提炼

### 4.1 验证脚本（推荐）

```powershell
env\Scripts\python.exe scripts\validate_researcher_reflection.py
```

### 4.2 手动验证

**步骤1：触发一次股票分析**（同2.2步骤1）。

**步骤2：查看日志**

```powershell
findstr /i "analysis_lesson" logs\*.log
```

预期看到：
```
[Researcher] 已写入 analysis_lesson 教训: ticker=XXXXXX stance=bull
```

**步骤3：检查 mem0 记忆**

```javascript
db.mem0_memories.find({"metadata.memory_kind": "analysis_lesson"}).sort({created_at:-1}).limit(1).pretty()
```

预期：存在 `metadata.memory_kind="analysis_lesson"` 的记录。

### 4.3 验证 checklist

| # | 检查项 | 状态 |
|---|---|---|
| 4.1 | `_reflect_on_analysis()` 在 `researcher.py` 中定义 | [ ] |
| 4.2 | 研究员报告生成后触发了反思 | [ ] |
| 4.3 | mem0 中出现 `memory_kind=analysis_lesson` 的结构化经验 | [ ] |

---

## 五、项4：智能助手 HITL

### 5.1 验证脚本（推荐）

```powershell
env\Scripts\python.exe scripts\validate_assistant_hitl.py
```

### 5.2 手动验证（非流式路径）

**步骤1：发送关键操作请求**

在前端智能助手对话框，输入以下任一关键操作：
- "帮我分析一下平安银行"
- "删除所有定时配置"

**步骤2：确认暂停行为**

预期：助手不应直接执行，而是返回类似：
```
⚠️ 此操作需要确认：[操作描述]
确认 ID：hitl_xxxxxxxx
```

### 5.3 手动验证（流式路径）

**步骤1：同上，发送关键操作请求**

**步骤2：确认流式输出中也有暂停**

预期：流式输出过程中出现暂停确认消息。

### 5.4 检查数据库

```javascript
db.hitl_pending_operations.find({status:"pending"}).sort({created_at:-1}).limit(1).pretty()
```

预期：存在一条 `status="pending"` 的记录。

### 5.5 curl 确认/拒绝

```powershell
# 查看 pending 列表
curl http://127.0.0.1:8002/api/assistant/hitl/pending

# 确认（替换 {pending_id} 为实际值）
curl -X POST http://127.0.0.1:8002/api/assistant/hitl/{pending_id}/confirm
```

### 5.6 验证 checklist

| # | 检查项 | 状态 |
|---|---|---|
| 5.1 | `core/hitl/` 目录存在 | [ ] |
| 5.2 | 关键操作执行前暂停（非流式） | [ ] |
| 5.3 | 关键操作执行前暂停（流式） | [ ] |
| 5.4 | `hitl_pending_operations` 集合有 pending 记录 | [ ] |
| 5.5 | confirm/reject API 可正常调用 | [ ] |

---

## 六、项6：Skill 生成 HITL（三路径）

### 6.1 验证脚本（推荐）

```powershell
env\Scripts\python.exe scripts\validate_skill_generation_hitl.py
```

### 6.2 路径A：Skill 工坊独立生成失败告警

**步骤1：模拟失败**

Skill 工坊 → 提交一个复杂 spec（故意写可能失败的需求）。

**步骤2：查看日志**

```powershell
findstr /i "skill_iteration_alerts\|IterationAlert" logs\*.log
```

预期看到迭代失败后写入了告警。

**步骤3：检查数据库**

```javascript
db.skill_iteration_alerts.find().sort({created_at:-1}).limit(1).pretty()
```

预期：存在 `status="pending_human_review"` 的记录。

### 6.3 路径B：Agent 工坊自动补齐不自动绑定

**步骤1：触发 Agent 工坊补齐**

Agent 工坊 → 创建新 Agent → 描述需求（故意让系统识别到缺失的 Skill）。

**步骤2：查看审核记录**

```javascript
db.skill_review_queue.find({source_path:"agent_workshop"}).sort({created_at:-1}).limit(1).pretty()
```

预期：存在 `status="pending_review"` 且 `source_path="agent_workshop"` 的记录。

**步骤3：前端确认/拒绝**

前端 Agent 工坊页面 → 查看 SkillReviewCard 组件 → 确认或拒绝。

**步骤4：查看审核结果**

确认后：
```javascript
db.skill_review_queue.find({review_id:"xxx"}).pretty()
```
预期 `status="confirmed_bound"`。

拒绝后：
预期 `status="rejected_unbound"`。

### 6.4 路径C：AI 工作流批量生成不自动绑定

**步骤1：触发工作流生成**

AI 工作流 → 创建新工作流 → 让系统自动生成 Skills。

**步骤2：查看审核记录**

```javascript
db.skill_review_queue.find({source_path:"ai_workflow"}).sort({created_at:-1}).limit(1).pretty()
```

预期：存在 `status="pending_review"` 且 `source_path="ai_workflow"` 的记录。

### 6.5 过期处理验证

**步骤1：手动将一条审核记录标记为过期**

```javascript
db.skill_review_queue.updateOne(
  {review_id:"xxx"},
  {$set:{created_at:new Date(Date.now()-25*3600000).toISOString()}}
)
```

**步骤2：调用 API**

```powershell
curl -X POST http://127.0.0.1:8002/api/agent-workshop/skill-review/{session_id}/{tool_id}/confirm
```

预期返回：`{"status":"expired","message":"该 Skill 审核请求已超过 24 小时..."}`

### 6.6 验证 checklist

| # | 检查项 | 状态 |
|---|---|---|
| 6.1 | `skill_review_service.py` 存在 | [ ] |
| 6.2 | 路径A：`iteration_controller.py` 有 `_write_iteration_alert` | [ ] |
| 6.3 | 路径B：Agent 工坊补齐后 Skill 不自动绑定 | [ ] |
| 6.4 | 路径C：工作流生成后 Skill 不自动绑定 | [ ] |
| 6.5 | 前端 SkillReviewCard 组件可见 | [ ] |
| 6.6 | confirm API 正常工作 | [ ] |
| 6.7 | reject API 正常工作 | [ ] |
| 6.8 | 过期拒绝有正确提示 | [ ] |
| 6.9 | `expire_stale_reviews()` 方法存在 | [ ] |

---

## 七、项7：规划失败修正重试

### 7.1 验证脚本（推荐）

```powershell
env\Scripts\python.exe scripts\validate_planning_recovery.py
```

### 7.2 手动验证

**步骤1：触发一次股票分析**（同2.2步骤1）。

**步骤2：查看日志**

```powershell
findstr /i "planning.*retry\|PlanSource\|plan.*correction" logs\*.log
```

正常情况下规划不会失败，但需确认：
- 代码中 `planner.py` 存在 `_try_llm_plan_with_correction()` 方法
- 规划失败时有降级到 REACT_FALLBACK 的逻辑

### 7.3 代码检查

- `core/agents/planner.py`: 确认 `_try_llm_plan_with_correction` 方法存在
- `app/services/planned_analysis_service.py`: 确认 `plan.source == PlanSource.REACT_FALLBACK` 判断存在

### 7.4 验证 checklist

| # | 检查项 | 状态 |
|---|---|---|
| 7.1 | `planner.py` 有 `_try_llm_plan_with_correction` | [ ] |
| 7.2 | 规划失败后有 3 级降级（种子→LLM规划→修正→ReAct） | [ ] |

---

## 八、项8：辩论反思回流

### 8.1 验证脚本（推荐）

```powershell
env\Scripts\python.exe scripts\validate_debate_reflection.py
```

### 8.2 手动验证

**步骤1：触发一次股票分析**（同2.2步骤1）。

**步骤2：查看日志**

```powershell
findstr /i "debate_lesson\|辩论反思" logs\*.log
```

预期看到：
```
[辩论反思] 已写入 debate_lesson 教训: ticker=XXXXXX type=investment_debate node=research_manager
```

**步骤3：检查 mem0 记忆**

```javascript
db.mem0_memories.find({"metadata.memory_kind":"debate_lesson"}).sort({created_at:-1}).limit(1).pretty()
```

预期：存在 `metadata.memory_kind="debate_lesson"` 和 `metadata.source="debate_reflection"` 的记录。

**步骤4：确认 v2 manager 也触发**

如果分析使用了 `research_manager_v2`，检查日志中是否也触发了辩论反思。

### 8.3 代码检查

- `core/workflow/builder.py`: 确认 `_is_manager_agent()` 使用 `startswith` 前缀匹配（覆盖 `research_manager_v2`）
- `core/agents/researcher.py`: 确认 `_reflect_on_debate()` 方法存在

### 8.4 验证 checklist

| # | 检查项 | 状态 |
|---|---|---|
| 8.1 | `builder.py` 有 `_is_manager_agent()` 前缀匹配 | [ ] |
| 8.2 | manager 节点执行后触发了辩论反思 | [ ] |
| 8.3 | v2 manager 也会触发（通过前缀匹配） | [ ] |
| 8.4 | mem0 中出现 `memory_kind=debate_lesson` 的记录 | [ ] |

---

## 九、反射核心框架验证

### 9.1 代码检查

| # | 检查项 | 预期 | 状态 |
|---|---|---|---|
| 9.1 | `core/agents/reflection_helper.py` 存在 | 含 `run_reflection` / `run_reflection_sync` | [ ] |
| 9.2 | `core/agents/reflection_prompts.py` 存在 | 含三种场景的 system/user prompt | [ ] |
| 9.3 | LLM 超时 30s 降级 | 超时不阻塞，写入 fallback 原文 | [ ] |
| 9.4 | mem0 不可用不阻塞 | 跳过反思，只 log warning | [ ] |

---

## 十、HITL 通用基础设施验证

### 10.1 代码检查

| # | 检查项 | 预期 | 状态 |
|---|---|---|---|
| 10.1 | `core/hitl/checkpoint_store.py` 存在 | `HITLCheckpointService` 类 | [ ] |
| 10.2 | `core/hitl/assistant_hitl.py` 存在 | 含 `CRITICAL_TOOL_IDS` 列表 | [ ] |
| 10.3 | `app/main.py` 有 HITL 清理定时任务 | `hitl_expire_stale` 函数 | [ ] |
| 10.4 | `app/main.py` 有 Skill 审核清理定时任务 | `skill_review_expire_stale` 函数 | [ ] |

---

## 十一、ChromaDB 兼容性验证

### 11.1 代码检查

| # | 检查项 | 预期 | 状态 |
|---|---|---|---|
| 11.1 | `tradingagents/agents/utils/memory.py` 有 MEM0_ENABLED guard | `MEM0_ENABLED=true` 时跳过 ChromaDB 初始化 | [ ] |

---

## 十二、端到端闭环验证

执行一次完整的分析→复盘→查询流程：

1. [ ] **启动服务** → 两条定时任务日志出现
2. [ ] **股票分析** → QualityGate + analysis_lesson + debate_lesson 日志 + analysis_quality_metrics 记录
3. [ ] **交易复盘** → trade_lesson 日志
4. [ ] **智能助手关键操作** → HITL pending 记录
5. [ ] **再次分析同股票** → 召回结果含结构化教训（非原文）

### 端到端日志一次性检查

```powershell
findstr /i "QualityGate\|analysis_lesson\|debate_lesson\|trade_lesson\|辩论反思\|HITL·助手" logs\*.log
```

---

## 附录A：数据库集合清单

| 集合名 | 对应项 | 说明 |
|---|---|---|
| `analysis_quality_metrics` | 项5 | 质量指标数据 |
| `hitl_pending_operations` | 项4 | HITL 待确认操作 |
| `skill_iteration_alerts` | 项6（路径A） | Skill 迭代失败告警 |
| `skill_review_queue` | 项6（路径B/C） | Skill 审核队列 |
| `mem0_memories` | 项2/3/8 | mem0 结构化经验 |

---

## 附录B：验证脚本清单

| 脚本 | 对应项 |
|---|---|
| `scripts\validate_quality_gate.py` | 项1 |
| `scripts\validate_trade_review_reflection.py` | 项2 |
| `scripts\validate_researcher_reflection.py` | 项3 |
| `scripts\validate_assistant_hitl.py` | 项4 |
| `scripts\validate_quality_metrics.py` | 项5 |
| `scripts\validate_skill_generation_hitl.py` | 项6 |
| `scripts\validate_planning_recovery.py` | 项7 |
| `scripts\validate_debate_reflection.py` | 项8 |
| `scripts\validate_reflection_recall_loop.py` | 反思闭环 |
