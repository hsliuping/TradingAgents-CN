# Agent Studio / Nanobot 当前改动提交说明

> 生成时间：2026-06-03
> 用途：用于人工审核当前工作区改动，并在审核后手动执行 `git add` / `git commit`

---

## 1. 当前工作区概览

当前检测到：

- 已修改文件：15 个
- 未跟踪文件：2 个
- 已暂存文件：0 个

工作区文件如下：

### 代码改动

- `app/routers/agent_workshop.py`
- `app/routers/prompt_templates.py`
- `app/services/agent_workshop_service.py`
- `core/agents/factory.py`
- `core/agents/universal.py`
- `core/embedded_nanobot/providers/base.py`
- `core/embedded_nanobot/providers/unified.py`
- `core/embedded_nanobot/runtime.py`
- `core/tools/implementations/agent_builder/__init__.py`
- `core/tools/implementations/agent_builder/nanobot_agent_builder_tools.py`
- `frontend/src/api/agentWorkshop.ts`
- `frontend/src/views/Settings/TemplateAgentSelector.vue`
- `frontend/src/views/Settings/TemplateManagement.vue`
- `frontend/src/views/Workflow/AgentStudio.vue`
- `skills/nanobot-agent-design/SKILL.md`

### 文档改动

- `docs/design/v3.0/agent-studio-skill-auto-completion.md`
- `docs/development/nanobot-context-optimization-plan.md`

---

## 2. 改动主题判断

这批改动的主线比较清晰，核心是：

1. 强化 `Agent Studio` 的可用性与可观测性。
2. 增强 `Nanobot` 在工坊场景下的上下文聚焦能力。
3. 为 `Agent 工坊 blocking gaps -> Skill 补齐` 打通阻塞式自动补齐链路。
4. 改善测试、发布、模板绑定和运行时配置的细节体验。
5. 补充与上述能力对应的设计文档。

如果只看主题，这批改动可以归纳为：

`feat(agent-studio): 强化 Agent 工坊迭代、测试观测与 blocking gap 补齐链路`

---

## 3. 代码改动分析

### 3.1 Agent 工坊后端接口

涉及文件：

- `app/routers/agent_workshop.py`
- `frontend/src/api/agentWorkshop.ts`

主要变化：

- 新增 `PUT /specs/{spec_id}`，支持更新 spec 的 `name` 和 `primary_goal`。
- 新增 `GET /test-progress/{version_id}`，用于前端轮询版本测试进度。
- 前端 API 层同步补充 `updateSpec()` 和 `getTestProgress()`。

价值：

- 支持在 Agent Studio 中直接重命名 Agent。
- 支持测试阶段显示更细粒度的过程进度，而不是只看最终结果。

---

### 3.2 AgentWorkshopService 主链路增强

涉及文件：

- `app/services/agent_workshop_service.py`

主要变化：

- 构建版本时注入 `project_memory_block`，加强版本生成阶段对项目长期记忆的对齐。
- 新增 `update_spec()`，并在改名时同步更新 `agent_configs` 中的 `name`。
- 发布时将 `project_memory_binding` 从硬阻塞改为警告输出，保留发布提示但降低阻断强度。
- 调试/测试流程新增 Mongo 进度写入逻辑，阶段包括：
  - `init`
  - `config`
  - `model`
  - `agent`
  - `analysis`
  - `report`
  - `done`
- 规范化 Nanobot 生成的标识符，去掉末尾 `_vN`，避免与工坊版本号冲突。
- 合并 spec 数据时，优先保护已有中文名称，避免被 LLM 输出的英文 slug 覆盖。
- 运行时 `agent_config` 同步增强：
  - `testing` 状态版本也会同步到运行时
  - workshop 版本的模板绑定会同步回短名 `agent_config`
- 数值追溯规则调整：
  - 若 section 明确带有“估算/公开信息/仅供参考”等免责声明，则高风险数值可降级为 warning，而不是 blocker。

价值：

- 测试链路更可视化。
- Agent 名称、模板绑定和运行时配置一致性更好。
- 工坊版本调试和发布时的规则更接近真实迭代场景。

---

### 3.3 Nanobot Runtime 与工具链增强

涉及文件：

- `core/embedded_nanobot/runtime.py`
- `core/tools/implementations/agent_builder/__init__.py`
- `core/tools/implementations/agent_builder/nanobot_agent_builder_tools.py`
- `skills/nanobot-agent-design/SKILL.md`

主要变化：

- 将 `resolve_agent_workshop_blocking_gaps` 注册进 Agent Builder 工具集。
- Runtime 在线程上下文里存在 `spec_id / version_id / workshop_session_id` 时，显式强化“当前就是这个 Agent”的指引，避免 Nanobot 反复追问“你指的是哪个 Agent”。
- Project Memory 注入时，不再只给通用规则，而是会补一段“当前 Agent 聚焦块”，包含：
  - Agent 名称
  - `spec_id`
  - 目标
  - 领域
  - 当前版本
  - 绑定工具
  - 达标线
- `inspect_agent_workshop_assets()` 额外合并每个版本最新评估结果，减少 Nanobot 依赖陈旧上下文。
- `iterate_agent_workshop_version()` 允许在 `testing` 阶段直接进入迭代，适配“版本配置坏了，先修再测”的流程。
- 新增阻塞式工具 `resolve_agent_workshop_blocking_gaps()`：
  - 从 gap report 中读取 `blocking_gaps`
  - 并行启动多个 Skill 生成 session
  - 等待生成完成
  - 返回新 Skill 信息供后续绑定
- `SKILL.md` 对状态机说明同步更新，允许 `testing -> governance` 的修复回退路径。

价值：

- Nanobot 在 Agent Studio 里的上下文感知更强。
- 工坊缺口补齐开始具备“一个工具打通多 gap”能力。
- 版本生命周期的行为定义更贴近实际使用。

---

### 3.4 LLM Provider 与运行时容错

涉及文件：

- `core/embedded_nanobot/providers/base.py`
- `core/embedded_nanobot/providers/unified.py`
- `core/agents/universal.py`
- `core/agents/factory.py`

主要变化：

- 将 `unterminated string`、`jsondecodeerror` 纳入瞬时错误标记，便于 provider 重试。
- 将统一提供器的 `max_tokens` 下限抬到 `16384`。
- `UniversalAgent` 在工具调用模式下也保留 `_last_llm_debug`，便于调试工具链响应。
- Agent Factory 允许 `testing` 状态的工坊版本进入运行时加载。

价值：

- 测试中版本可直接运行验证。
- 工具调用模式下的调试信息更完整。
- 部分结构化输出异常会被当作瞬时错误处理，减少偶发失败。

---

### 3.5 Agent Studio 前端交互增强

涉及文件：

- `frontend/src/views/Workflow/AgentStudio.vue`

主要变化：

- 顶部新增左右侧栏显隐控制，主布局会根据侧栏显示状态自适应。
- Agent 标题支持双击重命名，并直连后端 `updateSpec()`。
- 聊天消息按 `spec_id` 隔离保存与恢复，切换 Agent 时不再共用同一份对话历史。
- 增强流式事件展示：
  - `onProgress`
  - `onToolEvent`
  - `onStepEvent`
- 测试工具执行时自动轮询 `getTestProgress()`，右侧面板增加测试进度条。
- 调试结果展示增强：
  - 支持复制结构化 JSON
  - 支持展示最新 runtime report 文本
  - 支持展示基础运行元信息
- 新增聊天自动滚动到底部。
- 切换 Agent、重置 Studio、恢复线程消息时，会同步维护每个 Agent 的聊天上下文。

价值：

- 一个 Agent 对应一组相对独立的对话与上下文，减少串台。
- 用户能更清晰看到测试进行到哪一步。
- 版本调试信息更容易查看和复制。

---

### 3.6 模板管理页适配 workshop/universal

涉及文件：

- `frontend/src/views/Settings/TemplateAgentSelector.vue`
- `frontend/src/views/Settings/TemplateManagement.vue`
- `app/routers/prompt_templates.py`

主要变化：

- 模板管理页对工坊自定义 Agent 使用 `universal` 类型。
- `TemplateManagement` 对 `universal` 分类做专门处理：
  - 从 API 返回的 `agent_name` 动态构建候选
  - 仅展示 `spec_nanobot_` 开头的 workshop 模板
  - 默认仅看 `active`
- Prompt Template 路由对 `created_at / updated_at` 做了更稳健的类型处理，不再假设一定是 `datetime`。

价值：

- 工坊模板和普通模板的筛选逻辑更清楚。
- 避免历史数据里时间字段类型不一致导致接口报错。

---

## 4. 文档改动分析

### 4.1 `agent-studio-skill-auto-completion.md`

定位：

- 这是与当前代码主线强相关的设计文档。
- 文档已经按“当前实现 / 目标态 / 分阶段实施”重新整理，可作为后续继续开发的基线。

建议：

- 如果本次提交包含代码主线，建议这份文档一起提交。

### 4.2 `nanobot-context-optimization-plan.md`

定位：

- 这是偏后续优化的规划文档，主题是 Nanobot 上下文 token 优化。
- 它和当前代码有相关性，但不属于已经完全落地的功能变更说明。

建议：

- 如果想保持本次提交聚焦，建议单独成一笔 `docs` 提交。
- 如果你接受“代码 + 设计计划”一起入库，也可以并入，但提交说明里要写清楚这是一份后续优化草案。

---

## 5. 建议的提交拆分

### 方案 A：推荐，拆成 2 次提交

#### 提交 1：功能与代码主线

建议标题：

```text
feat(agent-studio): 强化工坊迭代、测试观测与 blocking gap 补齐链路
```

建议正文：

```text
- 新增 Agent spec 更新接口与测试进度查询接口
- 强化 AgentWorkshopService 的测试进度写入、模板绑定同步和名称保护逻辑
- 允许 testing 版本进入运行时加载，并增强 UniversalAgent 调试信息
- 在 Embedded Nanobot 中增加当前 Agent 聚焦上下文，减少工坊场景下的误判
- 新增 resolve_agent_workshop_blocking_gaps 工具，支持阻塞式补齐 blocking gaps
- 增强 Agent Studio 前端的重命名、侧栏切换、聊天隔离和测试进度展示
- 调整工坊模板管理页与 universal 模板分类逻辑
```

建议纳入文件：

- `app/routers/agent_workshop.py`
- `app/routers/prompt_templates.py`
- `app/services/agent_workshop_service.py`
- `core/agents/factory.py`
- `core/agents/universal.py`
- `core/embedded_nanobot/providers/base.py`
- `core/embedded_nanobot/providers/unified.py`
- `core/embedded_nanobot/runtime.py`
- `core/tools/implementations/agent_builder/__init__.py`
- `core/tools/implementations/agent_builder/nanobot_agent_builder_tools.py`
- `frontend/src/api/agentWorkshop.ts`
- `frontend/src/views/Settings/TemplateAgentSelector.vue`
- `frontend/src/views/Settings/TemplateManagement.vue`
- `frontend/src/views/Workflow/AgentStudio.vue`
- `skills/nanobot-agent-design/SKILL.md`

#### 提交 2：文档

建议标题：

```text
docs(agent-studio): 补充 skill 自动补齐与 nanobot 上下文优化方案
```

建议正文：

```text
- 新增 Agent Studio 自动补 Skill 与 Skill 工坊治理化设计文档
- 新增 Nanobot 上下文 token 优化方案文档
- 明确当前实现、目标态设计与后续实施顺序
```

建议纳入文件：

- `docs/design/v3.0/agent-studio-skill-auto-completion.md`
- `docs/development/nanobot-context-optimization-plan.md`

---

### 方案 B：如果你想一次提交

建议标题：

```text
feat(agent-studio): 强化工坊工作流并补充技能自动补齐设计
```

建议正文：

```text
- 新增 Agent spec 更新与测试进度查询接口
- 增强 AgentWorkshopService 的测试、发布、模板绑定与运行时配置同步逻辑
- 为 Embedded Nanobot 增加当前 Agent 聚焦上下文和 blocking gap 补齐工具
- 强化 Agent Studio 的聊天隔离、重命名、测试进度和调试结果展示
- 调整 universal/workshop 模板筛选与时间字段兼容性处理
- 新增 skill 自动补齐设计文档与 nanobot 上下文优化方案文档
```

---

## 6. 提交前建议重点检查

建议手动确认以下几点：

1. `TemplateAgentSelector.vue`
   - 当前将工坊自定义 Agent 的 `type` 从 `custom_agent` 改成了 `universal`
   - 需确认这和后端模板查询、已有数据分类是否完全一致

2. `TemplateAgentSelector.vue`
   - diff 中出现了若干中文字符串里的额外空格，如“智 能体”“自定义 研究员”
   - 需确认这些是否是有意修改，避免把显示文案瑕疵一并提交

3. `core/embedded_nanobot/providers/unified.py`
   - `max_tokens` 被强制提升到至少 `16384`
   - 需确认这是否符合当前模型配额、成本和响应延迟预期

4. `app/services/agent_workshop_service.py`
   - `project_memory_binding` 从发布 blocker 改成 warning
   - 需确认这符合你对发布门槛的治理要求

5. `core/agents/factory.py`
   - `testing` 版本现在也会被运行时启用
   - 需确认不会影响生产流量、正式工作流或外部展示逻辑

---

## 7. 建议手动验证清单

建议在提交前至少过一遍：

1. Agent Studio 中双击标题重命名 Agent，刷新后确认名称同步生效。
2. 对某个 testing 版本触发测试，确认右侧测试进度条会轮询更新并最终结束。
3. 切换不同 Agent，确认聊天记录按 `spec_id` 隔离恢复，而不是串台。
4. 在 Nanobot 中围绕“当前 Agent”提问，确认不会再反复追问“是哪一个 Agent”。
5. 对存在 `blocking_gaps` 的 session 试跑一次 `resolve_agent_workshop_blocking_gaps`。
6. 在模板管理页切到 `universal` 分类，确认只显示 workshop 模板且筛选正常。

---

## 8. 手动提交示例

### 如果按推荐拆分

```bash
git add app/routers/agent_workshop.py app/routers/prompt_templates.py app/services/agent_workshop_service.py core/agents/factory.py core/agents/universal.py core/embedded_nanobot/providers/base.py core/embedded_nanobot/providers/unified.py core/embedded_nanobot/runtime.py core/tools/implementations/agent_builder/__init__.py core/tools/implementations/agent_builder/nanobot_agent_builder_tools.py frontend/src/api/agentWorkshop.ts frontend/src/views/Settings/TemplateAgentSelector.vue frontend/src/views/Settings/TemplateManagement.vue frontend/src/views/Workflow/AgentStudio.vue skills/nanobot-agent-design/SKILL.md
git commit -m "feat(agent-studio): 强化工坊迭代、测试观测与 blocking gap 补齐链路"

git add docs/design/v3.0/agent-studio-skill-auto-completion.md docs/development/nanobot-context-optimization-plan.md
git commit -m "docs(agent-studio): 补充 skill 自动补齐与 nanobot 上下文优化方案"
```

### 如果一次提交

```bash
git add .
git commit -m "feat(agent-studio): 强化工坊工作流并补充技能自动补齐设计"
```

---

## 9. 结论

当前改动已经具备提交价值，且主题基本聚焦在 Agent Studio / Nanobot / 工坊链路增强上。

我的建议是：

- 优先采用“代码一笔、文档一笔”的两次提交方案。
- 在正式提交前，先人工检查模板分类映射、中文文案空格、`testing` 版本运行时启用范围。
- 如果这些点确认无误，这批改动可以进入手动提交阶段。
