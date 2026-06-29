# Agent 工坊稳定性改动分批提交计划

本文档用于将当前 Agent 工坊、Nanobot、Skill 生成、标准财务工具相关改动按可审核、可回滚的粒度拆分成多批 Git 提交。本文只提供手动提交建议，不自动执行 `git add` 或 `git commit`。

## 当前工作区概览

已跟踪改动约 37 个文件，另有若干新增文件。

需要特别注意：工作区存在未跟踪目录 `nanobot/`，该目录看起来像完整外部项目源码，不建议随本批业务改动提交。若确实需要引入，应单独作为 vendor/submodule 处理。

---

## 提交 1：稳定 Nanobot 的 Agent 焦点与任务链上下文

### 目的

解决以下问题：

- 选中某个 Agent 后，Nanobot 仍回答全局进度。
- 创建 Agent 过程中意图漂移到其他 Agent。
- Agent → Gap → Skill → 回到 Agent 的链路丢失。
- 删除旧 Agent 后，同名重建时复用旧记忆。

### 建议文件

```powershell
git add `
  core/embedded_nanobot/intent_context.py `
  core/embedded_nanobot/runtime.py `
  core/embedded_nanobot/session/manager.py `
  app/services/embedded_nanobot_service.py `
  core/tools/context.py `
  core/tools/implementations/agent_builder/nanobot_agent_builder_tools.py `
  frontend/src/views/Workflow/AgentStudio.vue `
  core/memory/service.py
```

### 建议提交信息

```text
stabilize nanobot agent intent context

Add structured intent context for Nanobot agent-builder flows so the
current agent, active subtask, linked skills, and next action are
persisted and injected into each turn. This prevents cross-agent drift,
restores selected-agent chat continuity, and marks deleted agent plans
as invalid for same-name rebuilds.
```

### 审核重点

- `core/embedded_nanobot/intent_context.py`：新增结构化上下文模型。
- `core/embedded_nanobot/runtime.py`：System Prompt 注入当前 Agent、任务链、关联 Skill。
- `app/services/embedded_nanobot_service.py`：上下文持久化。
- `core/tools/implementations/agent_builder/nanobot_agent_builder_tools.py`：写操作前的意图漂移校验。
- `frontend/src/views/Workflow/AgentStudio.vue`：切换 Agent 时优先恢复 Nanobot 聊天历史。

### 建议验证

```powershell
python -m pytest "tests/core/tools/implementations/test_nanobot_agent_builder_tools.py" -q
```

当前已验证结果：`64 passed`。

---

## 提交 2：修复 Agent Workshop 生成、调试、评估闭环

### 目的

解决以下问题：

- Workshop `required_tools` 与 Runtime `effective_tools` 不一致。
- External Skill 绑定了但 debug/test 不调用。
- `prompt_overrides` 不生效或未持久化到模板。
- `execution_plan` 没有注入 Runtime，LLM 只写 Prompt 演示式报告。
- LLM review 缺字段导致评估崩溃。
- `feasibility_status` 缺失导致迭代崩溃。
- Prompt Template 丢失时无法 debug。

### 建议文件

```powershell
git add `
  app/services/agent_workshop_service.py `
  app/services/prompt_template_service.py `
  core/agents/universal.py `
  core/agents/base.py `
  core/llm/providers/openai_compat.py `
  tests/services/test_agent_workshop_service_publish_flow.py
```

### 建议提交信息

```text
harden agent workshop runtime execution loop

Align Workshop versions with runtime tool bindings, inject execution
plans into UniversalAgent prompts, persist prompt overrides to version
templates, and make runtime evaluation tolerant of optional review
fields. This turns generated versions into tool-driven execution units
instead of prompt-only report drafts.
```

### 审核重点

- `app/services/agent_workshop_service.py`
  - `tool_selection_policy` 延后到最终 `required_tools` 合并后生成。
  - `debug_version` 合并 Runtime `effective_tools`。
  - 按实际 `tool_ids` 重建 runtime `execution_plan`。
  - Prompt 模板缺失自动重建。
  - LLM JSON / 评估缺字段容错。
- `core/agents/universal.py`
  - 注入 `Agent Workshop Execution Plan（运行时强约束）`。
  - 让 Runtime 明确看到步骤、工具、验收项、降级规则。
- `core/llm/providers/openai_compat.py`
  - 支持 `response_format={"type": "json_object"}` 透传。

### 建议验证

```powershell
python -m pytest "tests/core/tools/implementations/test_nanobot_agent_builder_tools.py" -q
```

补充说明：`tests/services/test_agent_workshop_service_publish_flow.py` 当前仍有既有/环境失败，包括 Qdrant 本地锁、FakeDb 缺 `external_skills`、旧断言与当前工具角色分类不一致等。

---

## 提交 3：完善 Skill 生成与 External Skill 角色元数据

### 目的

解决以下问题：

- External Skill 只有名称/描述，缺少角色和能力边界。
- Agent Builder 无法判断主入口、专项、补充、降级工具。
- Skill 生成 JSON 易被 CoT 干扰。
- Gap 解决和 Skill 生成缺少更稳定的迭代/校验机制。

### 建议文件

```powershell
git add `
  app/services/skill_generation_service.py `
  app/models/capability_index.py `
  app/services/capability_index_service.py `
  core/tools/external_skill_loader.py `
  core/tools/external/iteration_controller.py `
  core/tools/external/recon_tools.py `
  core/tools/external/requirement_analyzer.py `
  core/tools/external/sandbox_runner.py `
  core/tools/external/skill_spec.py `
  core/tools/external/static_validator.py `
  core/tools/registry.py `
  tests/core/tools/test_skill_generation_agentic_engine.py `
  docs/design/v3.0/skill-generation-agentic-engine.md
```

### 建议提交信息

```text
add role metadata for generated external skills

Extend generated External Skills with capability tags, role hints,
output shape, preferred use cases, and non-replacement boundaries.
Propagate this metadata through loading and capability indexing so
Agent Builder can route primary, specialized, supporting, and fallback
tools more reliably.
```

### 审核重点

- `app/services/skill_generation_service.py`：Skill 角色元数据推断与保存。
- `core/tools/external_skill_loader.py`：External Skill 加载时传递角色元数据。
- `app/services/capability_index_service.py`：索引中保留角色元数据。
- `core/tools/external/iteration_controller.py`：Skill 生成迭代控制。

### 建议验证

```powershell
python -m pytest "tests/core/tools/test_skill_generation_agentic_engine.py" -q
python -m pytest "tests/core/tools/implementations/test_nanobot_agent_builder_tools.py" -q
```

---

## 提交 4：新增标准财务数据能力与专用财务分析工具

### 目的

解决以下问题：

- 商誉字段未从 Tushare 标准化链路提取。
- 季报拿不到商誉时 LLM 乱猜。
- 杜邦分析没有专用工具。
- `operate_profit` 字段名映射错误，导致五因子杜邦缺数据。
- 需要更标准的财务数据 API 给 Skill / Agent 复用。

### 建议文件

```powershell
git add `
  core/skill_runtime/__init__.py `
  core/skill_runtime/data_access.py `
  core/skill_runtime/sync_wrappers.py `
  core/skill_runtime/standard_financial_apis.py `
  core/tools/implementations/fundamentals/financial_tools.py `
  core/tools/implementations/fundamentals/standard_financial_tools.py `
  core/tools/implementations/fundamentals/__init__.py `
  core/tools/implementations/__init__.py `
  core/tools/config.py `
  tradingagents/dataflows/providers/china/tushare.py `
  tradingagents/models/stock_data_models.py `
  app/services/data_sources/manager.py `
  tests/core/skill_runtime/test_standard_financial_apis.py
```

### 建议提交信息

```text
add standard financial tools for goodwill and dupont analysis

Expose standardized financial data APIs and add dedicated goodwill and
DuPont analysis tools. Extract goodwill from Tushare balance sheets and
fix operating profit mapping so financial-risk agents can rely on
deterministic data instead of prompting around missing fields.
```

### 审核重点

- `core/tools/implementations/fundamentals/financial_tools.py`
  - `get_goodwill_analysis`
  - `get_dupont_analysis`
  - `get_balance_sheet_analysis` 商誉展示
- `tradingagents/dataflows/providers/china/tushare.py`
  - `goodwill` 提取
  - `operate_profit` 映射修复
- `tradingagents/models/stock_data_models.py`
  - `goodwill` 字段
- `core/tools/config.py`
  - 工具元数据与角色边界

### 建议验证

```powershell
python -m pytest "tests/core/skill_runtime/test_standard_financial_apis.py" -q
python -m pytest "tests/core/tools/implementations/test_nanobot_agent_builder_tools.py" -q
```

---

## 提交 5：补充 Agent 工坊架构文档和能力路线图

### 目的

沉淀当前系统架构，避免后续遗忘：

- Agent 工坊
- Nanobot
- IntentContext
- Skill 生成
- Gap 解决
- Runtime 执行
- Capability Index
- Agent / Skill 商店演进方向

### 建议文件

```powershell
git add `
  docs/design/v3.0/agent-workshop-nanobot-skill-architecture.md `
  docs/design/v3.0/standard-financial-data-capabilities-roadmap.md
```

### 建议提交信息

```text
document agent workshop nanobot skill architecture

Document the relationship between Agent Workshop, Nanobot, IntentContext,
Skill generation, capability indexing, runtime execution, and future
Agent/Skill store reuse patterns.
```

---

## 提交 6：日志与调试可观测性

### 目的

增强 Agent 工坊和 Nanobot 调试时的可观测性。

### 建议文件

```powershell
git add `
  app/core/logging_config.py
```

### 建议提交信息

```text
improve logging for agent workshop diagnostics

Add logging support needed to trace Agent Workshop and Nanobot execution
paths during generated-agent debugging and evaluation.
```

---

## 不建议提交 / 需要单独确认

### `nanobot/`

当前工作区显示：

```text
 ? nanobot
```

该目录很大，像完整外部 Nanobot 项目源码，不建议随本批业务改动提交。

如确实需要引入，应单独处理，例如：

- 作为 Git submodule；
- 作为 vendor 目录单独提交；
- 或加入 `.gitignore`。

---

## 推荐提交顺序

1. Nanobot IntentContext 稳定性
2. Agent Workshop 执行闭环
3. Skill 生成与角色元数据
4. 标准财务工具与数据能力
5. 架构文档
6. 日志可观测性

这样每批都能独立审核，出问题也容易回滚。

---

## 最小验证命令

每批提交前建议至少跑：

```powershell
python -m pytest "tests/core/tools/implementations/test_nanobot_agent_builder_tools.py" -q
```

涉及 Skill 生成时跑：

```powershell
python -m pytest "tests/core/tools/test_skill_generation_agentic_engine.py" -q
```

涉及标准财务工具时跑：

```powershell
python -m pytest "tests/core/skill_runtime/test_standard_financial_apis.py" -q
```

当前已验证：

```text
tests/core/tools/implementations/test_nanobot_agent_builder_tools.py
64 passed
```
