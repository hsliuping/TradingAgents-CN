# 分批 Git 提交计划

> 生成时间：2026-06-28  
> 目的：将当前工作区变更拆成多个小提交，便于审核、回滚和定位问题。  
> 说明：本文档只提供提交计划和命令草案，不代表已经执行 `git add` / `git commit`。

---

## 0. 提交前必须先处理的未跟踪项

当前工作区存在两个未跟踪项：

```text
?? nanobot
?? frontend/vite.config.ts.timestamp-1782571912490-cb0aed22094a.mjs
```

建议处理方式：

1. `nanobot/`
   - 看起来是完整外部 Nanobot 项目源码，体积很大。
   - **不建议直接提交**，除非明确要 vendor 进当前仓库。
   - 如仅用于参考，应保持未跟踪或移出仓库目录。

2. `frontend/vite.config.ts.timestamp-1782571912490-cb0aed22094a.mjs`
   - 看起来是 Vite 临时文件。
   - **不建议提交**。
   - 建议删除或加入忽略规则。

---

## 1. 建议拆分为 6 个提交

### Commit 1：Agent / Skill 删除清理与长期记忆一致性

**建议标题：**

```text
fix(agent-workshop): clean deleted agents and imported skills
```

**目的：**

修复删除 Agent / Skill 后，长期记忆、磁盘目录、能力发现仍残留的问题。

**包含内容：**

- 删除 Agent 时清理 mem0 中相关记忆。
- 在 Nanobot MEMORY/HISTORY 中追加删除记录，避免已删除 Agent 被长期记忆误召回。
- 删除导入 Skill 时增强目录匹配逻辑，支持 `skill_import_*` 目录按 `skill_id` / `name` / `SKILL.md` 内容匹配删除。
- 删除已确认废弃的 `skills/skill_import_01ogxx4w/` 目录。

**建议加入文件：**

```powershell
git add app/services/agent_workshop_service.py
git add core/tools/implementations/agent_builder/nanobot_agent_builder_tools.py
git add -u skills/skill_import_01ogxx4w
```

**提交命令草案：**

```powershell
git commit -m "fix(agent-workshop): clean deleted agents and imported skills"
```

**审核重点：**

- 确认 `skills/skill_import_01ogxx4w/` 确实是要删除的《股市真规则》导入 Skill。
- 确认记忆清理不会误删其他 Agent / Skill 的记忆。

---

### Commit 2：Skill 生成队列幂等与 Nanobot 工具修复

**建议标题：**

```text
fix(agent-builder): reuse active skill generation sessions
```

**目的：**

修复异步 Skill 创建时，同一个 gap 被多个入口重复生成的问题；同时修复 prompt template detail 读取为空的问题。

**包含内容：**

- 创建 Skill 前检查 active `skill_creation_sessions`，命中则复用已有会话。
- 覆盖同步 gap resolution 与异步 GapJob worker 两个入口。
- 补充中等相似度去重候选详情，向用户展示候选 Skill 名称、相似度和描述。
- 修复 `get_prompt_template_detail` 读取 Mongo projection 导致内容为空的问题。
- 补强单测中的 projection 模拟。

**建议加入文件：**

```powershell
git add core/tools/implementations/agent_builder/nanobot_agent_builder_tools.py
git add tests/core/tools/implementations/test_nanobot_agent_builder_tools.py
```

**提交命令草案：**

```powershell
git commit -m "fix(agent-builder): reuse active skill generation sessions"
```

**审核重点：**

- 该提交与 Commit 1 都修改了 `nanobot_agent_builder_tools.py`，建议用 `git add -p` 分块暂存，避免两个主题混在一起。
- 确认 active session 匹配条件包含同一 `agent_spec_id` / `workshop_session_id` / `gap_id` 或 `target_capability`。

---

### Commit 3：历史估值数据访问能力

**建议标题：**

```text
feat(skill-runtime): add external valuation history access
```

**目的：**

补齐历史 PE/PB 等估值时间序列数据通路，避免估值分位数 Skill 错把 OHLCV 行情数据当估值数据。

**包含内容：**

- BaoStockProvider 新增历史估值序列获取方法。
- 新增 `get_external_valuation_data` 同步包装入口。
- 在 `project_access` 中导出新 helper 并更新文档。
- 在 `data_access` 文档中明确：历史 PE/PB 不应使用 `get_external_historical_data`，该接口只返回 OHLCV。

**建议加入文件：**

```powershell
git add tradingagents/dataflows/providers/china/baostock.py
git add core/skill_runtime/external_sources.py
git add core/skill_runtime/project_access.py
git add core/skill_runtime/data_access.py
```

**提交命令草案：**

```powershell
git commit -m "feat(skill-runtime): add external valuation history access"
```

**审核重点：**

- BaoStock 字段映射是否统一为平台字段，如 `pe_ttm` / `pb_mrq` / `ps_ttm`。
- 新 helper 的 symbol 标准化、日期格式、空数据返回是否符合现有运行时约定。

---

### Commit 4：Skill 生成管线鲁棒性增强

**建议标题：**

```text
fix(skill-generation): improve failure context and code extraction
```

**目的：**

提升现有 Skill 生成管线的失败诊断能力，减少因上下文截断、Markdown fence 残留、Judge 可见信息不足导致的无效重试。

**包含内容：**

- 放大需求分析、反思、Judge、执行输出等上下文截断上限。
- 反思阶段注入数据访问函数目录，帮助 LLM 识别可用 helper。
- 修复 LLM 输出中 Markdown code fence 残留导致 Python 第一行语法错误的问题。
- 提高 Judge 输出 token 上限与代码/执行结果可见范围。

**建议加入文件：**

```powershell
git add core/tools/external/code_generator.py
git add core/tools/external/iteration_controller.py
git add core/tools/external/output_evaluator.py
git add core/tools/external/requirement_analyzer.py
git add app/services/skill_generation_service.py
```

**提交命令草案：**

```powershell
git commit -m "fix(skill-generation): improve failure context and code extraction"
```

**审核重点：**

- 确认 token 放大是有意为之，当前优先保证生成效果。
- 确认 code fence 清理不会误删正常代码内容。

---

### Commit 5：Agent 工坊与前端交互适配

**建议标题：**

```text
feat(agent-workshop): refine studio and skill management UX
```

**目的：**

提交 Agent Studio / Workshop / Skill 管理相关的前后端适配。

**包含内容：**

- Agent Studio / Workshop Manager 前端视图调整。
- Template Management 与 Sidebar 菜单调整。
- Skills 路由、main 注册、registry、base agent 等适配。
- Nanobot Agent Design Skill 文档更新。

**建议加入文件：**

```powershell
git add app/main.py
git add app/routers/skills.py
git add core/agents/base.py
git add core/tools/registry.py
git add frontend/src/components/Layout/SidebarMenu.vue
git add frontend/src/views/Settings/TemplateManagement.vue
git add frontend/src/views/Workflow/AgentStudio.vue
git add frontend/src/views/Workflow/AgentWorkshopManager.vue
git add skills/nanobot-agent-design/SKILL.md
```

**可选文件：**

`frontend/src/views/Workflow/SkillGeneration.vue` 在 `git status` 中显示修改，但 `git diff --name-status` 没有显示，可能是换行、权限、时间戳或工作区状态差异导致。提交前建议单独检查：

```powershell
git diff -- frontend/src/views/Workflow/SkillGeneration.vue
git status --short frontend/src/views/Workflow/SkillGeneration.vue
```

如确认有实际内容变更，再加入：

```powershell
git add frontend/src/views/Workflow/SkillGeneration.vue
```

**提交命令草案：**

```powershell
git commit -m "feat(agent-workshop): refine studio and skill management UX"
```

**审核重点：**

- 该提交范围偏宽，建议重点看前端显示逻辑与后端注册接口是否匹配。
- 如果部分前端修改与本批主题无关，可继续拆分。

---

### Commit 6：Skill 生成引擎 Agent 化设计文档

**建议标题：**

```text
docs(skill-generation): document agentic engine redesign
```

**目的：**

新增 v3.0 Skill 生成引擎 Agent 化改造设计，作为后续实现依据。

**包含内容：**

- 固定 DAG 管线痛点分析。
- SkillGeneration 专用 Agent Loop 目标架构。
- `run_readonly_query` / `probe_interface` / 单轮 `pipeline_tool` 设计。
- 沙箱 RPC 构建期边界与最终 Skill 依赖约束。
- `failure_summary` 工作记忆。
- in-flight 幂等锁。
- 分阶段实施计划与风险控制。

**建议加入文件：**

```powershell
git add docs/design/v3.0/skill-generation-agentic-engine.md
```

**提交命令草案：**

```powershell
git commit -m "docs(skill-generation): document agentic engine redesign"
```

**审核重点：**

- 确认文档中“不替换 Hermes、采用 SkillGeneration 专用 Agent Loop”的定位是否符合你的最终决策。
- 确认 `pipeline_tool` 单轮边界、沙箱 RPC 不进入最终 Skill、in-flight 幂等锁等约束是否完整。

---

## 2. 推荐实际操作顺序

建议顺序如下：

```text
1. 先处理未跟踪临时文件 / 外部目录
2. Commit 3：历史估值数据访问能力
3. Commit 4：Skill 生成管线鲁棒性增强
4. Commit 2：Skill 生成队列幂等与 Nanobot 工具修复
5. Commit 1：Agent / Skill 删除清理与长期记忆一致性
6. Commit 5：Agent 工坊与前端交互适配
7. Commit 6：设计文档
```

理由：

- 数据访问与生成管线改动较独立，优先提交便于验证。
- `nanobot_agent_builder_tools.py` 与 `agent_workshop_service.py` 改动较大，建议中间提交，方便使用 `git add -p` 精细拆分。
- 文档最后提交，确保文档反映最终代码状态。

---

## 3. 提交前检查命令

每个提交前建议执行：

```powershell
git diff --cached --stat
git diff --cached --name-status
```

提交后建议执行：

```powershell
git status --short
```

如果需要验证相关 Python 文件语法：

```powershell
python -m py_compile `
  core/tools/implementations/agent_builder/nanobot_agent_builder_tools.py `
  core/tools/external/code_generator.py `
  core/tools/external/iteration_controller.py `
  core/tools/external/output_evaluator.py `
  core/tools/external/requirement_analyzer.py `
  tradingagents/dataflows/providers/china/baostock.py
```

如果需要验证相关单测：

```powershell
pytest tests/core/tools/implementations/test_nanobot_agent_builder_tools.py -q
```

---

## 4. 重要提醒

不要直接执行：

```powershell
git add .
```

原因：当前存在 `nanobot/` 外部目录和 Vite 临时文件，直接 `git add .` 容易误提交大量无关内容。

推荐只按上述每个 commit 的路径显式 `git add`。
