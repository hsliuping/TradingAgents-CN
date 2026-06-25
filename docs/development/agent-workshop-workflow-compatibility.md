# Agent 工坊与工作流 Agent 规格一致性改造开发文档

## 1. 背景

当前 Agent 工坊可以通过对话生成 `AgentSpec`，再构建 `AgentVersion`、`PromptTemplate`，发布后写入 `agent_configs`，运行时由 `AgentFactory` 创建 `UniversalAgent` 并加入工作流执行。

但实际对比发现：

1. nanobot 生成层与 Agent 工坊落库层之间缺少统一输出契约。
2. 工坊生成的 Agent 与内建流程 Agent 的规格不完全一致。
3. 工坊生成的提示词虽然写入了 `prompt_templates`，但缺少统一模板规范和发布前校验。
4. 工坊发布到 `agent_configs` 的字段与工作流引擎读取字段存在断层。
5. 新增的报告展示控制字段 `show_in_reports` 未纳入工坊生成链路。

本文件用于记录现状、问题、目标 Schema、改造方案和验收标准，作为后续实现备查。

---

## 2. 现有链路分析

### 2.0 nanobot 在 Agent 工坊中的定位

nanobot 是 Agent 工坊生成新 Agent 的上层构建器，核心价值不是最终运行股票分析工作流，而是用一个通用 Agent Loop 完成“需求理解 → 规格整理 → 能力/工具规划 → 提示词草案生成”的构建任务。

从 nanobot 代码结构看，其能力主要由以下组件提供：

| 组件 | 作用 |
|---|---|
| `nanobot/agent/loop.py` | 接收消息、构建上下文、管理会话、组织一次 Agent turn |
| `nanobot/agent/runner.py` | 执行 LLM + 工具调用循环，产出最终响应 |
| `nanobot/agent/skills.py` | 加载 `SKILL.md`，把专门工作流/规范注入上下文 |
| `nanobot/agent/tools/registry.py` | 管理可用工具注册与发现 |
| `nanobot/session/manager.py` | 管理会话状态与上下文延续 |

推荐职责边界：

```text
nanobot 负责生成/规划结果
AgentWorkshopService 负责把结果规范化、版本化、持久化、发布到运行时
```

这意味着：不能只修 `AgentWorkshopService` 的后处理。必须同时约束 nanobot 侧的生成输出契约，否则 nanobot 仍可能生成缺少 `output_field`、`show_in_reports`、`report_label`、`workflow_stage` 等运行时必需字段的 Agent 草案。

### 2.0.1 nanobot 版本状态

当前集成的 nanobot 版本：

```text
版本：v0.2.2-32-g943191f0
上游：https://github.com/HKUDS/nanobot.git
状态：基本为最新版，落后 origin/main 仅 8 个补丁 commit（MCP 门控、Telegram opt-in、WebUI 修复等，不影响核心接口）
```

近 3 个月（2026.03.25 → 2026.06.25）nanobot 从 v0.1.5 迭代到 v0.2.2，共 1673 个 commit。核心变化：

| 模块 | 关键更新 |
|------|---------|
| Agent 核心 | `/goal` 长期任务、Auto Compact 会话压缩、mid-turn 消息注入、内置 grep/glob、ask_user、SelfTool、插件化工具发现 |
| Memory | Dream 两阶段记忆、git 版本控制、idle auto compact |
| Skills | disabled_skills 配置、update-setup wizard |
| Providers | OpenCode/Mistral/Kimi Coding/Step Plan 等 15+ 新 provider |
| SDK | Python SDK facade、per-session isolation |

**对 Agent 工坊的影响**：核心 Agent Loop、Skills 加载、工具注册接口保持稳定，无破坏性变更。新增的 `/goal`、Auto Compact、SelfTool 等能力对 Agent 工坊有潜在价值，但当前不需要急着升级——先把输出契约补稳。

### 2.0.2 构建器选型评估：nanobot vs Hermes

对 Agent 工坊的构建器选型做了专项评估，结论如下：

**当前阶段：nanobot 更合适。**

| 维度 | nanobot | Hermes |
|------|---------|--------|
| 当前项目已有代码 | 已在仓库中 | 未接入 |
| 接入成本 | 零 | 中高（需部署、对接 API、适配输出） |
| 可控性 | 高，代码在仓库内 | 依赖外部框架 |
| 适合需求整理/规格草案 | 适合 | 适合 |
| 适合 Prompt 生成 | 适合 | 适合 |
| 适合工具规划 | 适合 | 适合 |
| 适合沉淀构建经验 | 一般 | 更强（天然学习循环） |
| 治理风险 | 低 | 中（自学习可能引入不可控变更） |

**核心判断**：当前 Agent 工坊的问题不是"构建器不够聪明"，而是"输出契约不完整"（`show_in_reports` 缺失、`agent_type` 不匹配、`agent_configs` 字段不全）。这些问题不靠换构建器解决，靠补规范和校验解决。

**长期路线**：

```text
阶段 1（当前）：继续 nanobot + 补输出契约 + 发布前校验
阶段 2（近期）：抽象 AgentBuilderProvider 接口，解耦构建器
阶段 3（远期）：等工坊成熟后评估 Hermes，通过 Provider 切换
```

只要现在把 `AgentBuilderProvider` 抽象好，后续迁移到 Hermes 只需换一个 Provider 实现（约几百行代码），用户无感知。

### 2.0.3 当前代码接入状态补充

复核当前分支与 git 历史后，需要修正一个关键判断：**Agent 工坊原来确实存在专门的 Nanobot 交互页面和后端嵌入式 Nanobot 运行时，但当前工作树里这条链路已经不在主分支代码中。**

先理清三个关键分支的关系：

```text
分支关系（从共同祖先 7a0ac1d0 出发）：

7a0ac1d0  feat: 提交 Agent 工坊与因子治理阶段性改动  ← 三方共同祖先
├── v3.0 (HEAD = 0357fffc)
│   └── ... 大量 v3.0 功能迭代 ...
│       └── integration/v3-sync-20260507 (HEAD = cddbd896)  ← 当前分支
│           └── 在 v3.0 之上继续迭代（show_in_reports 等）
│
└── test/agent-workshop-validation (HEAD = e8e8c688)
    └── 12 个 Nanobot 工坊专项提交（独立演进，未合并入 v3.0 或 integration 线）
```

关键结论：

| 维度 | 事实 |
|------|------|
| `test/agent-workshop-validation` 与 `v3.0` 的共同祖先 | `7a0ac1d0`（Agent 工坊与因子治理阶段性改动） |
| `test/agent-workshop-validation` 与 `integration/v3-sync-20260507` 的共同祖先 | 同样是 `7a0ac1d0` |
| `v3.0` 与 `integration/v3-sync-20260507` 的关系 | `integration/v3-sync-20260507` 是 `v3.0` 的延续（v3.0 HEAD `0357fffc` 是其直接祖先） |
| Nanobot 工坊提交是否在 v3.0 或 integration 中 | **否**。12 个提交全部只在 `test/agent-workshop-validation` 上 |
| 是否是"合并丢失" | **不是**。这些提交从未被合并到 v3.0 或 integration 线，属于独立验证分支 |

也就是说：`test/agent-workshop-validation` 和 `v3.0` 从 `7a0ac1d0` 分叉后各自独立演进。`integration/v3-sync-20260507` 是 `v3.0` 的延续，所以也没有这些 Nanobot 工坊提交。

历史提交中可确认的 Nanobot 工坊链路（仅在 `test/agent-workshop-validation` 分支）：

| 历史提交 | 说明 |
|---------|------|
| `237c3fd1` | `feat: 集成 Nanobot 运行时与可复用技能生成链路` |
| `8720bbce` | `feat: 打通 nanobot 与工坊 draft 桥接并修复止盈提醒调度` |
| `736f95b7` | `feat: 打通 Nanobot 与 Agent Workshop 阶段流转` |
| `e8aa1b6f` | `feat: 完成 Agent Workshop 与助手模式主链路` |
| `b2de0286` | `完善 Agent Workshop 记忆治理闭环并精简工坊侧栏` |
| `9f0c236d` | `修复工坊助手会话切换与状态恢复` |
| `e8e8c688` | `修复 Nanobot 展示消息持久化与工作台会话恢复` |

历史链路中存在的关键文件（仅在 `test/agent-workshop-validation` 分支）：

```text
app/routers/embedded_nanobot.py
app/schemas/embedded_nanobot.py
app/services/embedded_nanobot_service.py
core/embedded_nanobot/runtime.py
core/embedded_nanobot/agent/*
frontend/src/api/embeddedNanobot.ts
frontend/src/views/Workflow/NanobotAgentStudio.vue
frontend/src/views/Debug/EmbeddedNanobot.vue
```

历史版本中的调用方式是：

```text
NanobotAgentStudio.vue
  → embeddedNanobotApi.chatStream()
  → /api/embedded-nanobot/chat/stream
  → EmbeddedNanobotService.chat()
  → EmbeddedNanobotRuntime.handle_message()
  → Agent Workshop draft / session bridge
```

当前工作树实际情况：

| 能力 | 当前状态 |
|------|---------|
| `NanobotAgentStudio.vue` | 缺失 |
| `embeddedNanobot.ts` | 缺失 |
| `/api/embedded-nanobot/*` 路由 | 缺失 |
| `EmbeddedNanobotService` | 缺失 |
| `core/embedded_nanobot/*` | 缺失 |
| 主 Agent 工坊 `AgentWorkshop.vue` | 存在，但已退回 `agentWorkshopApi` 直连模式 |
| `AgentWorkshopService` | 存在，主要直接调用 `UnifiedLLMClient` |

当前已确认的直接 LLM 调用点包括：

| 阶段 | 当前实现 | 说明 |
|------|---------|------|
| 需求澄清/规格整理 | `_analyze_requirement_turn()` → `UnifiedLLMClient.achat()` | 直接拼接系统提示词和用户提示词，要求返回 JSON |
| 缺口分析 | `_build_gap_analysis()` / `_build_gap_analysis_prompt()` | 直接构造资源缺口分析 prompt |
| 工具方案 | `_generate_tooling_plan_with_llm()` → `UnifiedLLMClient.achat()` | 直接要求 LLM 返回 tooling plan JSON |
| Prompt 模板 | `_create_prompt_template()` | 后端确定性拼装 `TemplateContent`，不是 nanobot 输出最终模板 |

因此，当前文档中的实现策略应改为：

```text
从 test/agent-workshop-validation 分支 cherry-pick/合并 Nanobot 工坊链路
  ↓
在合并后的 Nanobot 链路上补 AgentBuilderProvider 抽象
  ↓
再补 tradingagents-agent-builder 契约与发布校验
```

这更符合原产品设计，也能避免用户已经熟悉的 Nanobot 交互式工坊体验被替换成普通表单式 LLM 流程。

注意：这不是"分支同步时丢失"，而是 Nanobot 工坊链路作为独立验证分支从未被合并到 v3.0 或 integration 线。合并时需解决与当前分支的差异（如 `show_in_reports`、动态报告展示、运行时字段等近期改造）。

### 2.1 Agent 工坊数据流

当前主链路位于：

- `app/services/agent_workshop_service.py`
- `app/models/agent_workshop.py`
- `app/routers/agent_workshop.py`

核心流程：

```text
用户对话
  ↓
AgentWorkshopSession.current_spec_snapshot
  ↓
build_version(session_id)
  ↓
AgentVersion
  ├─ agent_metadata
  ├─ prompt_template_ref
  ├─ required_tools
  ├─ output_schema
  └─ evaluation_policy
  ↓
evaluate_version(version_id)
  ↓
publish_version(version_id)
  ↓
_ensure_runtime_agent_config(version, spec)
  ↓
agent_configs
  ↓
AgentFactory._try_create_universal_agent()
  ↓
UniversalAgent.execute()
  ↓
state[output_field]
  ↓
WorkflowEngine structured_reports / report_manifest
  ↓
前端报告展示
```

### 2.2 版本构建链路

`AgentWorkshopService.build_version()` 当前负责：

1. 加载 session。
2. 获取 `current_spec_snapshot`。
3. 如果没有 gap_report，则自动生成 gap_report。
4. 生成 `version_id`。
5. 选择 `required_tools`。
6. 构建：
   - `required_capabilities`
   - `output_schema`
   - `evaluation_policy`
   - `prompt_template`
   - `agent_metadata`
7. 保存 `AgentVersion`。

关键方法：

```python
build_version()
_create_prompt_template()
_build_agent_metadata()
```

### 2.3 发布链路

`AgentWorkshopService.publish_version()` 当前负责：

1. 校验版本存在。
2. 要求版本状态必须为 `testing`。
3. 归档同一 spec 下旧 active 版本。
4. 禁用旧 `agent_configs`。
5. 将当前版本状态改为 active。
6. 调用 `_ensure_runtime_agent_config()` 写入 `agent_configs`。
7. 更新 `AgentSpec.current_version_id` 和状态。

关键方法：

```python
publish_version()
_ensure_runtime_agent_config()
```

### 2.4 运行时调用链路

发布后的工坊 Agent 不会生成专有 Python 类，而是走通用运行时：

```text
WorkflowBuilder
  ↓
AgentFactory.create(agent_id)
  ↓
如果注册表中没有该 agent_id
  ↓
AgentFactory._try_create_universal_agent()
  ↓
读取 agent_configs
  ↓
创建 UniversalAgent
  ↓
UniversalAgent.execute()
```

`AgentFactory._try_create_universal_agent()` 目前读取字段：

```text
agent_id
name / agent_name
description
output_field
default_tools / tools
enabled
metadata.source
version_status
runtime_status
```

工坊 Agent 必须满足：

```text
metadata.source = agent_workshop
enabled = true
version_status = active
runtime_status = active
```

否则不会被 `UniversalAgent` 创建。

### 2.5 Prompt 模板加载链路

`UniversalAgent.execute()` 通过基类 `_get_prompt_from_template()` 加载模板：

```text
UniversalAgent.execute()
  ↓
_get_prompt_from_template(agent_type="universal", agent_name=agent_id, prompt_type="system")
_get_prompt_from_template(agent_type="universal", agent_name=agent_id, prompt_type="user")
  ↓
tradingagents.utils.template_client.get_agent_prompt/get_user_prompt
  ↓
TemplateClient.get_effective_template()
  ↓
prompt_templates
```

模板优先级：

1. debug template
2. node-specific template
3. workflow-specific template
4. user config template
5. user preference system template
6. neutral system template
7. fallback prompt

当前工坊 `_create_prompt_template()` 写入：

```python
PromptTemplateCreate(
    agent_type="custom_agent",
    agent_name=version_id,
    ...
    status="draft",
)
```

但运行时 `UniversalAgent` 查的是：

```python
agent_type="universal"
agent_name=agent_id
```

这会导致一个关键不一致：**工坊写入的模板类型是 `custom_agent`，UniversalAgent 运行时读取的是 `universal`。**

除非模板系统另有兼容逻辑，否则工坊生成的 prompt 可能无法被 UniversalAgent 命中，最终会降级到 `UniversalAgent._build_default_system_prompt()` / `_build_default_user_prompt()`。

---

## 3. 当前不一致点

### 3.1 AgentMetadata 不一致

内建 Agent 使用 `core/agents/config.py` 中的 `AgentMetadata` 作为标准规格。

工坊 `_build_agent_metadata()` 当前能生成大部分字段，但缺少或不稳定：

| 字段 | 内建 Agent | 工坊 Agent | 问题 |
|---|---|---|---|
| `id` | 有 | 有 | 一致 |
| `name` | 有 | 有 | 一致 |
| `description` | 有 | 有 | 一致 |
| `category` | 有 | 有 | 一致 |
| `inputs` | 有 | 有 | 一致 |
| `outputs` | 有 | 有 | 一致 |
| `tools` | 有 | 有 | 一致 |
| `default_tools` | 有 | 有 | 一致 |
| `max_tool_calls` | 有 | 固定 4 | 可接受，但需可配置 |
| `license_tier` | 有 | 固定 PRO | 需按产品策略明确 |
| `tags` | 有 | 有 | 一致 |
| `icon` | 有 | 固定 🧪 | 语义弱 |
| `color` | 有 | 固定色 | 语义弱 |
| `requires_tools` | 有 | 有 | 一致 |
| `output_field` | 有 | 有 | 一致，但需规范化 |
| `report_label` | 有 | 有 | 只在 metadata 内，未完整持久化 |
| `node_name` | 有 | 有 | 只在 metadata 内，未完整持久化 |
| `execution_order` | 有 | 固定 50 | 可接受，但需可配置 |
| `workflow_stage` | 有 | 有 | 一致 |
| `show_in_reports` | 有，默认 True | 缺失 | 必须补齐 |
| `depends_on` | 可用 | 缺失 | 后续流程依赖能力无法表达 |
| `growth_role` / `growth_outputs` / `memory_scope_hint` | 可用 | 缺失 | 成长系统无法接入 |

### 3.2 agent_configs 不一致

`_ensure_runtime_agent_config()` 是工坊 Agent 进入运行时的关键入口。

当前写入顶层字段：

```text
agent_id
name
description
category
version
license_tier
inputs
outputs
tags
enabled
runtime_status
version_status
published
config
prompt_template_type
prompt_template_name
default_tools
required_tools
output_field
workflow_stage
metadata
updated_at
created_at
```

但工作流和报告链路还会依赖：

```text
show_in_reports
report_label
node_name
execution_order
icon
description
workflow_stage
metadata.output_field
metadata.report_label
metadata.node_name
metadata.execution_order
metadata.show_in_reports
metadata.icon
metadata.color
```

当前部分字段只存在于 `version.agent_metadata`，未落到 `agent_configs` 顶层或 metadata 中，导致：

1. 阶段聚合器可能拿不到 label/order。
2. 报告 manifest 可能缺少展示信息。
3. 新增 `show_in_reports` 无法生效。
4. 后续自定义流程中 Agent 的可见性、排序和报告名称不可控。

### 3.3 Prompt 模板不一致

当前 `_create_prompt_template()` 创建模板时：

```python
agent_type="custom_agent"
agent_name=version_id
status="draft"
```

但 `UniversalAgent` 查询时：

```python
agent_type="universal"
agent_name=self.agent_id
```

存在三个问题：

1. **agent_type 不匹配**：`custom_agent` vs `universal`。
2. **状态不匹配**：模板创建为 `draft`，运行时只查 `active`。
3. **发布时没有同步模板状态**：`publish_version()` 没有把对应模板激活。

结果：工坊生成的提示词可能没有真正进入运行时。

### 3.4 发布前缺少兼容性校验

当前 `publish_version()` 只校验：

```text
version.status == TESTING
spec exists
```

缺少以下校验：

1. `agent_metadata` 是否满足标准 Schema。
2. `output_field` 是否规范且与 outputs 对齐。
3. `prompt_template_ref` 是否存在。
4. Prompt 模板是否能被 UniversalAgent 命中。
5. `required_tools` 是否都存在且可用。
6. `show_in_reports`、`report_label`、`workflow_stage` 等流程字段是否完整。
7. 生成后的 `agent_configs` 是否满足运行时最小 Schema。

### 3.5 nanobot Skill/Prompt 缺少 TradingAgents-CN 专用构建规范

nanobot 的 `SkillsLoader` 会把 `SKILL.md` 注入上下文，适合承载“如何生成 TradingAgents-CN Agent”的专用规范。

当前 nanobot 内置 skill 里有 `skill-creator`，但它是通用 Skill 创建指南，不是 TradingAgents-CN Agent 运行时契约指南。对 Agent 工坊来说，应该新增或接入一个专用构建规范，例如：

```text
nanobot/skills/tradingagents-agent-builder/SKILL.md
```

这个 Skill 应明确告诉 nanobot：

1. 不只是生成自然语言 Prompt，还要生成可运行 Agent Runtime Contract。
2. 输出字段必须是稳定英文蛇形字段名。
3. `show_in_reports` 默认 `true`。
4. Prompt 模板必须能被 `UniversalAgent` 命中，即 `agent_type=universal`、`agent_name=version_id`。
5. 新 Agent 若要进入股票分析流程，必须声明 `workflow_stage`。
6. 需要展示报告时必须声明 `report_label`、`icon`、`description`。
7. 工具规划只能引用真实可绑定工具或明确标记为缺口。
8. 输出必须是 JSON，不得只输出 Markdown 方案。

缺少这个 Skill/规范时，即便后端做了兜底，仍会出现：

- nanobot 生成的 Agent 草案字段不全。
- Prompt 草案没有包含输出字段约束。
- 工具规划与实际可绑定工具不一致。
- 工坊发布时需要大量猜测和补默认值。
- 新 Agent 在工作流里能跑，但行为不像内建 Agent。

### 3.6 Nanobot 交互式工坊链路在当前分支缺失

当前分支的 `AgentWorkshop.vue` 使用 `agentWorkshopApi.startSession/respond/previewSpec/analyzeGaps/buildVersion` 直连后端 `AgentWorkshopService`。这条链路可以工作，但它不是原来的 Nanobot 交互式工坊体验。

历史分支中曾存在：

```text
NanobotAgentStudio.vue
embeddedNanobotApi.chatStream()
/api/embedded-nanobot/chat/stream
EmbeddedNanobotRuntime.handle_message()
```

并且历史提交已经打通过：

```text
Nanobot 对话
  → 工坊 draft 桥接
  → Agent Workshop 阶段流转
  → 会话恢复与消息持久化
```

当前缺失这条链路是不合理的，极可能是分支同步/合并时没有把 `test/agent-workshop-validation` 中的 Nanobot 工坊改动带入当前 `integration/v3-sync-20260507`。后续实现应优先恢复/合并这部分，而不是另起一套普通 LLM Builder。

### 3.7 构建器调用层缺失

即便恢复历史 Embedded Nanobot 链路，仍需要一个统一构建器抽象层，否则后续继续会出现：

1. Nanobot 交互页、普通工坊页、未来 Hermes 接入各自写一套生成逻辑。
2. 构建输出契约散落在多个服务与页面中，难以统一校验。
3. 用户对话体验和后端发布治理难以解耦。

建议新增构建器抽象层：

```text
app/services/agent_builders/
  base.py                 # AgentBuilderProvider 抽象接口与 DTO
  embedded_nanobot_builder.py  # 封装恢复后的 EmbeddedNanobotRuntime 链路
  llm_builder.py          # 仅作为回退/测试 Provider
  hermes_builder.py       # 预留
```

`AgentWorkshopService` 只负责：会话、版本、PromptTemplate、评估、发布、迁移，不再直接关心底层构建器是 Embedded Nanobot、Hermes 还是普通 LLM 回退。

### 3.8 前端运行时控制字段缺失

当前前端 `agentWorkshop.ts` 和 `AgentWorkshop.vue` 主要展示：

```text
AgentSpec
AgentVersion.agent_metadata
Prompt 内容
调试结果
评估结果
```

但没有把以下运行时控制字段作为明确可编辑/可预览的配置项：

```text
output_field
workflow_stage
report_label
show_in_reports
execution_order
icon
color
max_tool_calls
```

如果这些字段只在后端默认生成，用户在工坊里无法理解“这个 Agent 发布后会出现在流程哪个阶段、报告叫什么、是否展示”。后续前端需要在“生成版本”页增加运行时配置卡片，至少支持预览和高级编辑。

---

## 4. 新需求目标

### 4.1 总目标

建立一套统一规范，保证 Agent 工坊生成的 Agent 与流程内建 Agent 规格一致，使工坊 Agent 能稳定地：

1. 被工作流识别。
2. 被 `AgentFactory` 创建为 `UniversalAgent`。
3. 正确加载工坊生成的 Prompt 模板。
4. 正确调用工具。
5. 正确写入 state 的 `output_field`。
6. 正确进入 `structured_reports` / `report_manifest`。
7. 正确在前端报告中展示。
8. 可被后续阶段 Agent 通过阶段聚合变量引用。

### 4.2 设计原则

1. **单一规范源**：nanobot 构建输出、工坊 Agent、内建 Agent、工作流运行时都遵循同一套 AgentRuntime Schema。
2. **发布即运行**：工坊 Agent 只有满足运行时 Schema 才能发布。
3. **模板可命中**：工坊生成的 Prompt 必须按 UniversalAgent 实际查询方式写入并激活。
4. **展示可控**：通过 `show_in_reports` 控制是否展示，默认展示。
5. **向后兼容**：旧工坊 Agent 可通过迁移/兼容字段继续运行。
6. **校验前置**：构建、评估、发布阶段尽早暴露问题。

---

## 5. nanobot Agent 构建输出契约

Agent 工坊后续应要求 nanobot 生成结果遵守固定 JSON 契约，而不是只生成自然语言方案。推荐契约如下：

```json
{
  "agent_spec": {
    "name": "筹码分布分析师",
    "domain": "stock_analysis",
    "primary_goal": "分析股票筹码分布和持仓成本结构",
    "responsibilities": [],
    "inputs": [],
    "outputs": [
      {
        "name": "chip_report",
        "type": "string",
        "description": "筹码分布分析报告"
      }
    ],
    "constraints": [],
    "success_criteria": []
  },
  "runtime_contract": {
    "category": "analyst",
    "workflow_stage": "analyst",
    "output_field": "chip_report",
    "report_label": "筹码分布分析",
    "node_name": "筹码分布分析师",
    "execution_order": 50,
    "show_in_reports": true,
    "icon": "🧮",
    "color": "#67C23A",
    "requires_tools": true,
    "default_tools": ["get_chip_distribution"],
    "max_tool_calls": 4
  },
  "prompt_contract": {
    "agent_type": "universal",
    "agent_name_strategy": "version_id",
    "template_status_on_build": "draft",
    "template_status_on_publish": "active",
    "system_prompt": "...",
    "user_prompt": "...",
    "tool_guidance": "...",
    "analysis_requirements": "...",
    "output_format": "必须输出 chip_report ...",
    "constraints": "..."
  },
  "tooling_contract": {
    "required_tools": ["get_chip_distribution"],
    "missing_capabilities": [],
    "fallback_strategy": []
  }
}
```

### 5.1 nanobot 输出字段规则

nanobot 生成 `agent_spec.outputs[*].name` 和 `runtime_contract.output_field` 时必须遵守：

```text
只允许小写字母、数字、下划线
必须稳定，不随中文描述变化
推荐后缀：_report / _result / _summary / _assessment / _decision / _plan / _opinion
```

### 5.2 nanobot 报告展示规则

如果生成的 Agent 是分析型 Agent，默认：

```json
{
  "show_in_reports": true
}
```

只有以下场景才允许 `false`：

1. 内部路由 Agent。
2. 数据预处理 Agent。
3. 只做中间判断、不应向用户展示的辅助 Agent。
4. 聚合器内部子步骤。

### 5.3 nanobot Prompt 生成规则

nanobot 生成的 Prompt 必须显式包含：

1. Agent 角色和职责。
2. 当前工作流上下文使用方式。
3. 可用工具和工具选择原则。
4. 输出字段名和格式要求。
5. 禁止伪造数据和数字。
6. 无数据时的降级输出方式。
7. 与下游 Agent 协作的报告边界。

其中 `output_format` 必须直接写明：

```text
最终报告必须写入 output_field 对应内容，例如 chip_report。
```

---

## 6. AgentRuntime Schema 规范

建议新增一个明确的运行时 Schema，例如：

```python
class AgentRuntimeConfig(BaseModel):
    agent_id: str
    name: str
    description: str
    category: str = "analyst"
    version: str = "1.0.0"
    license_tier: str = "free"

    inputs: List[Dict[str, Any]] = []
    outputs: List[Dict[str, Any]] = []

    tools: List[str] = []
    default_tools: List[str] = []
    required_tools: List[str] = []
    max_tool_calls: int = 4
    requires_tools: bool = True

    output_field: str
    report_label: str
    node_name: str
    workflow_stage: str = "analyst"
    execution_order: int = 50
    show_in_reports: bool = True

    prompt_template_type: str = "universal"
    prompt_template_name: str
    prompt_template_id: Optional[str] = None

    enabled: bool = False
    published: bool = False
    version_status: str = "draft"
    runtime_status: str = "disabled"

    tags: List[str] = []
    icon: str = "🤖"
    color: str = "#67C23A"

    metadata: Dict[str, Any] = {}
```

### 6.1 必填字段

发布为 active 前必须具备：

```text
agent_id
name
description
category
inputs
outputs
output_field
report_label
node_name
workflow_stage
execution_order
show_in_reports
prompt_template_type
prompt_template_name
prompt_template_id
enabled
version_status
runtime_status
metadata.source
metadata.spec_id
metadata.version_id
```

### 6.2 推荐字段

```text
default_tools
required_tools
max_tool_calls
requires_tools
icon
color
tags
license_tier
published
metadata.callable_surfaces
metadata.output_field
metadata.report_label
metadata.node_name
metadata.execution_order
metadata.show_in_reports
metadata.workflow_stage
metadata.icon
metadata.color
metadata.prompt_template_type
metadata.prompt_template_name
metadata.template_id
```

### 6.3 字段双写策略

为了兼容当前多个读取方，以下字段建议顶层与 metadata 内双写：

| 字段 | 顶层 | metadata | 原因 |
|---|---|---|---|
| `output_field` | 必须 | 必须 | 引擎、聚合器、兼容读取 |
| `report_label` | 必须 | 必须 | 报告展示与阶段聚合 |
| `node_name` | 必须 | 必须 | 工作流节点展示 |
| `execution_order` | 必须 | 必须 | 报告排序 |
| `workflow_stage` | 必须 | 必须 | 阶段聚合 |
| `show_in_reports` | 必须 | 必须 | 报告展示控制 |
| `icon` | 推荐 | 必须 | 前端 manifest 展示 |
| `color` | 推荐 | 必须 | 前端/管理页展示 |
| `template_id` | 推荐 | 必须 | 模板追踪 |

---

## 7. Prompt 模板规范

### 7.1 模板写入规范

工坊生成的 UniversalAgent Prompt 应写为：

```python
PromptTemplateCreate(
    agent_type="universal",
    agent_name=version_id,
    template_name=f"{spec.name} v{version} 运行模板",
    content=content,
    status="active" 或发布时切换为 active,
)
```

必须保证与 `UniversalAgent.execute()` 查询一致：

```python
_get_prompt_from_template(
    agent_type="universal",
    agent_name=self.agent_id,
)
```

### 7.2 模板生命周期

推荐策略：

```text
build_version
  ↓
创建 prompt_templates，status=draft
  ↓
evaluate_version 通过
  ↓
version.status=testing
  ↓
publish_version
  ↓
将当前 version 关联模板 status=active
  ↓
将同 spec 旧版本模板 status=draft 或 archived
```

如果当前模板系统只支持 `draft/active`，可以先使用：

```text
旧 active 模板 → draft
当前模板 → active
```

后续再扩展 `archived` 状态。

### 7.3 模板内容结构规范

`TemplateContent` 必须包含：

```text
system_prompt
user_prompt
tool_guidance
analysis_requirements
output_format
constraints
```

系统提示词必须包含：

1. 角色定义。
2. 能力边界。
3. 工具使用原则。
4. 数据可追溯要求。
5. 不得伪造数据。
6. 输出字段要求。
7. 与工作流上下文协同方式。

用户提示词必须包含：

1. 当前任务输入。
2. 标的/日期/市场等变量占位。
3. 上游报告引用说明。
4. 期望输出格式。

建议支持这些变量：

```text
{ticker}
{stock_symbol}
{company_of_interest}
{analysis_date}
{trade_date}
{market_type}
{task_description}
{analyst_reports}
{research_reports}
{risk_reports}
{tool_call_summaries}
```

### 7.4 模板发布前校验

发布前必须验证：

1. `template_id` 存在。
2. `agent_type == "universal"`。
3. `agent_name == version_id`。
4. `content.system_prompt` 非空。
5. `content.user_prompt` 非空或可由 fallback 补齐。
6. `content.output_format` 包含 `output_field`。
7. 模板渲染后无关键未替换变量。
8. status 发布后为 `active`。

---

## 8. 构建器抽象层设计

### 8.1 目标

新增 `AgentBuilderProvider`，把“智能生成草案”与“工坊确定性发布”解耦。

```text
AgentWorkshopService
  ├─ 负责会话、版本、模板、评估、发布、迁移
  └─ 调用 AgentBuilderProvider 获取结构化草案

AgentBuilderProvider
  ├─ clarify_requirement()
  ├─ analyze_gaps()
  ├─ plan_tools()
  ├─ generate_prompt_contract()
  └─ iterate_from_evaluation()
```

### 8.2 建议接口

```python
class AgentBuilderProvider(Protocol):
    async def clarify_requirement(
        self,
        messages: list[str],
        existing_spec: AgentSpec | None,
        context: AgentBuilderContext,
    ) -> AgentBuilderDraft: ...

    async def analyze_gaps(
        self,
        spec: AgentSpec,
        capability_snapshot: dict,
        context: AgentBuilderContext,
    ) -> AgentWorkshopGapAnalysis: ...

    async def plan_tools(
        self,
        spec: AgentSpec,
        gap_report: AgentWorkshopGapAnalysis,
        context: AgentBuilderContext,
    ) -> ToolingContract: ...

    async def generate_prompt_contract(
        self,
        spec: AgentSpec,
        runtime_contract: RuntimeContract,
        tooling_contract: ToolingContract,
        context: AgentBuilderContext,
    ) -> PromptContract: ...
```

### 8.3 DTO 边界

Provider 只能返回草案 DTO，不能直接写库：

```text
AgentBuilderDraft
RuntimeContract
PromptContract
ToolingContract
BuilderDiagnostics
```

禁止 Provider 直接操作：

```text
agent_configs
prompt_templates
AgentVersion.status
AgentSpec.status
```

这些必须由 `AgentWorkshopService` 统一校验和落库。

### 8.4 当前迁移策略

第一优先级是从 `test/agent-workshop-validation` 分支 cherry-pick/合并 Nanobot 工坊链路，而不是把当前直连 `UnifiedLLMClient` 流程继续做大。

建议步骤：

```text
1. 从 test/agent-workshop-validation 分支 cherry-pick/合并：
   - app/routers/embedded_nanobot.py
   - app/schemas/embedded_nanobot.py
   - app/services/embedded_nanobot_service.py
   - core/embedded_nanobot/*
   - frontend/src/api/embeddedNanobot.ts
   - frontend/src/views/Workflow/NanobotAgentStudio.vue
   - frontend/src/views/Debug/EmbeddedNanobot.vue

2. 恢复路由注册：
   - app/main.py 注册 embedded_nanobot_router
   - frontend/src/router/index.ts 恢复 /workflow/nanobot-agent-studio 或等价入口

3. 在合并后的链路上新增 EmbeddedNanobotBuilderProvider：
   - 封装 EmbeddedNanobotRuntime.handle_message()
   - 把 Nanobot 输出解析成 AgentBuilderDraft / RuntimeContract / PromptContract / ToolingContract

4. 保留 LLMBuilderProvider 作为兜底：
   - 用于测试、降级或临时绕过 Nanobot
   - 不作为主产品体验
```

迁移完成后的目标形态：

```text
NanobotAgentStudio.vue / AgentWorkshop.vue
  → AgentBuilderProvider
  → EmbeddedNanobotBuilderProvider（默认）
  → AgentWorkshopService 校验、版本化、发布
```

这样既保留原来的 Nanobot 交互体验，又保留后续切换 Hermes 的扩展点。

---

## 9. 代码改造方案

### 9.1 合并 Embedded Nanobot 工坊链路

从 `test/agent-workshop-validation` 分支 cherry-pick/合并以下文件，并解决与当前分支的差异：

```text
app/routers/embedded_nanobot.py
app/schemas/embedded_nanobot.py
app/services/embedded_nanobot_service.py
core/embedded_nanobot/**
frontend/src/api/embeddedNanobot.ts
frontend/src/views/Workflow/NanobotAgentStudio.vue
frontend/src/views/Debug/EmbeddedNanobot.vue
```

同时恢复路由：

```text
app/main.py
  → register_router_with_log(app, embedded_nanobot_router.router, ...)

frontend/src/router/index.ts
  → /debug/embedded-nanobot
  → /workflow/nanobot-agent-studio
```

恢复时要特别检查当前分支已经变更过的：

```text
AgentWorkshopService
AgentWorkshop 模型
前端 AgentWorkshop.vue
路由权限 meta
认证与请求封装
```

不要直接整块覆盖当前文件，避免丢掉当前分支的 `show_in_reports`、动态报告展示、运行时字段等近期改造。

### 9.2 新增构建器目录与 Provider 抽象

建议新增：

```text
app/services/agent_builders/
  __init__.py
  base.py
  embedded_nanobot_builder.py
  llm_builder.py
  hermes_builder.py
```

第一步先做 `EmbeddedNanobotBuilderProvider`，封装恢复后的 `EmbeddedNanobotRuntime.handle_message()`。`LLMBuilderProvider` 只作为回退/测试实现，用于兼容当前 `AgentWorkshopService` 内直接调用 `UnifiedLLMClient` 的逻辑。

`AgentWorkshopService` 保留同名业务方法也可以，但内部应改为调用 provider，避免 Nanobot 页面和普通工坊页面各自维护一套生成逻辑。

### 9.3 新增运行时 Schema / 工具函数

建议新增文件：

```text
app/models/agent_runtime.py
```

或放在：

```text
app/models/agent_workshop.py
```

建议提供：

```python
class AgentRuntimeConfig(BaseModel): ...

def build_runtime_config_from_version(version: AgentVersion, spec: AgentSpec) -> AgentRuntimeConfig: ...

def validate_runtime_config(config: AgentRuntimeConfig) -> List[str]: ...
```

职责：

1. 统一字段默认值。
2. 统一 output_field 规范化。
3. 统一 `agent_configs` 写入结构。
4. 统一发布前校验。

### 9.4 新增 nanobot 专用 Agent 构建 Skill

建议新增：

```text
nanobot/skills/tradingagents-agent-builder/SKILL.md
```

职责：

1. 告诉 nanobot 输出必须包含 `agent_spec`、`runtime_contract`、`prompt_contract`、`tooling_contract`。
2. 约束 `output_field`、`report_label`、`workflow_stage`、`show_in_reports` 等运行时字段。
3. 约束 Prompt 必须按 UniversalAgent 可命中方式生成。
4. 约束工具规划只能引用真实能力清单，缺失能力写入 `missing_capabilities`。
5. 明确输出必须是 JSON，禁止只返回 Markdown 说明。

同时在 Agent 工坊调用 nanobot 或 LLM 生成阶段，将该 Skill 或等价规则注入上下文。

### 9.5 修改 `_build_agent_metadata()`

补齐字段：

```python
show_in_reports=True
```

建议同时补充：

```python
depends_on=[]
growth_role=GrowthRole.NONE
growth_outputs=[output_field]
memory_scope_hint=GrowthMemoryScope.NONE
```

是否接入成长系统可后续再决定，但字段应保持结构一致。

### 9.6 修改 `_create_prompt_template()`

当前：

```python
agent_type="custom_agent"
status="draft"
```

建议改为：

```python
agent_type="universal"
agent_name=version_id
status="draft"
```

并在 `prompt_template_ref` 中保存：

```text
template_id
template_name
agent_type
agent_name
status
```

### 9.7 修改 `publish_version()`

发布前新增：

```python
errors = await self._validate_version_workflow_compatibility(version, spec)
if errors:
    raise ValueError(...)
```

发布过程中新增：

1. 激活当前 prompt template。
2. 归档/降级旧 prompt template。
3. 写入标准化 `agent_configs`。
4. 写入后回读校验。

### 9.8 修改 `_ensure_runtime_agent_config()`

```python
"requires_tools": bool(version.required_tools),
"max_tool_calls": int(version.agent_metadata.get("max_tool_calls") or 4),
"report_label": version.agent_metadata.get("report_label") or f"【{spec.name}】",
"node_name": version.agent_metadata.get("node_name") or spec.name,
"execution_order": int(version.agent_metadata.get("execution_order") or 50),
"show_in_reports": bool(version.agent_metadata.get("show_in_reports", True)),
"icon": version.agent_metadata.get("icon") or "🤖",
"color": version.agent_metadata.get("color") or "#67C23A",
```

补齐 metadata 字段：

```python
"output_field": output_field,
"report_label": report_label,
"node_name": node_name,
"execution_order": execution_order,
"show_in_reports": show_in_reports,
"prompt_template_type": "universal",
"prompt_template_name": version.version_id,
"template_id": version.prompt_template_ref.get("template_id"),
```

### 9.9 修改 `AgentFactory._try_create_universal_agent()`

建议增强日志和校验：

1. 如果 `prompt_template_type` 不是 `universal`，记录 warning。
2. 如果 `output_field` 缺失，拒绝创建或使用规范 fallback。
3. 将 `report_label`、`workflow_stage`、`show_in_reports` 等字段放入 debug 日志，便于排查。

### 9.10 修改 `stage_aggregator`

当前已经支持从 `agent_configs` 聚合工坊 Agent 报告，但建议增加 `show_in_reports` 过滤：

```python
"$or": [
    {"show_in_reports": {"$ne": False}},
    {"metadata.show_in_reports": {"$ne": False}},
]
```

或在遍历时过滤：

```python
show = doc.get("show_in_reports")
if show is None:
    show = (doc.get("metadata") or {}).get("show_in_reports", True)
if not show:
    continue
```

### 9.11 修改前端 Agent 工坊页面

需要让用户在生成/编辑 Agent 时可看到或设置这些控制字段：

```text
output_field
workflow_stage
report_label
show_in_reports
execution_order
icon
color
max_tool_calls
```

默认值：

```text
show_in_reports = true
workflow_stage = analyst 或按 category 推导
execution_order = 50
report_label = 【Agent 名称】
output_field = outputs[0].name + _report 后缀规范化
```

---

## 10. 发布前校验清单

新增 `_validate_version_workflow_compatibility(version, spec)`，至少校验：

### 10.1 Agent 元数据

```text
[ ] agent_metadata.id == version.version_id
[ ] name 非空
[ ] description 非空
[ ] category 非空
[ ] inputs 非空或允许空输入
[ ] outputs 非空
[ ] output_field 非空
[ ] output_field 与 outputs 至少一个字段一致或可追踪
[ ] report_label 非空
[ ] node_name 非空
[ ] workflow_stage in analyst/research/risk/manager/trader
[ ] execution_order 是整数
[ ] show_in_reports 是 bool
```

### 10.2 工具

```text
[ ] required_tools 均存在于 ToolRegistry 或外部工具注册表
[ ] requires_tools=True 时 required_tools 非空
[ ] required_tools 为空时 prompt 明确说明无工具模式
```

### 10.3 Prompt 模板

```text
[ ] prompt_template_ref.template_id 存在
[ ] prompt_templates 中能查到该模板
[ ] agent_type == universal
[ ] agent_name == version.version_id
[ ] content.system_prompt 非空
[ ] content.output_format 非空
[ ] 发布后 status == active
```

### 10.4 运行时配置

```text
[ ] agent_configs upsert 后可回读
[ ] enabled == true
[ ] runtime_status == active
[ ] version_status == active
[ ] metadata.source == agent_workshop
[ ] output_field 写入顶层和 metadata
[ ] show_in_reports 写入顶层和 metadata
[ ] report_label 写入顶层和 metadata
[ ] prompt_template_type == universal
[ ] prompt_template_name == version.version_id
```

---

## 11. 数据迁移建议

对已有工坊 Agent 执行一次兼容迁移：

### 11.1 查询范围

```javascript
db.agent_configs.find({
  "metadata.source": "agent_workshop"
})
```

### 11.2 补齐字段

对每条记录：

```text
show_in_reports = true 如果不存在
report_label = metadata.report_label or "【name】"
node_name = metadata.node_name or name
execution_order = metadata.execution_order or 50
workflow_stage = workflow_stage or metadata.workflow_stage or "analyst"
metadata.output_field = output_field
metadata.report_label = report_label
metadata.node_name = node_name
metadata.execution_order = execution_order
metadata.show_in_reports = show_in_reports
metadata.prompt_template_type = prompt_template_type or "universal"
metadata.prompt_template_name = prompt_template_name or agent_id
```

### 11.3 Prompt 模板迁移

如果已有模板是：

```text
agent_type = custom_agent
agent_name = version_id
```

需要复制或更新为：

```text
agent_type = universal
agent_name = version_id
```

并确保 active 版本的模板状态为：

```text
status = active
```

---

## 12. 验收标准

### 12.1 单元级验收

1. `_build_agent_metadata()` 输出包含 `show_in_reports`。
2. `_ensure_runtime_agent_config()` 写入完整顶层字段和 metadata 字段。
3. `_create_prompt_template()` 生成 `agent_type=universal` 的模板。
4. `publish_version()` 发布后模板为 active。
5. 发布前校验能拦截缺失 output_field、模板不存在、工具不存在等问题。

### 12.2 集成级验收

新建一个工坊 Agent，发布后：

```text
agent_configs 存在 active 记录
AgentFactory 能创建 UniversalAgent
UniversalAgent 能命中工坊生成 prompt_template
WorkflowEngine 执行后 state 中存在 output_field
structured_reports 包含该 output_field
report_manifest 包含 display_name/icon/description
前端报告页出现该 Agent 的独立报告
下游 research_manager 可通过 analyst_reports 看到该报告
```

### 12.3 回归验收

1. 内建 Agent 不受影响。
2. 旧工坊 Agent 经过迁移后可继续运行。
3. `show_in_reports=False` 的 Agent 不进入最终报告展示。
4. `show_in_reports=True` 的 Agent 默认展示。
5. 无 Prompt 模板时仍能 fallback，但发布流程应给出 warning 或阻止发布，取决于最终策略。

---

## 13. 推荐实施顺序

### 阶段 1：合并 Embedded Nanobot 工坊链路

1. 从 `test/agent-workshop-validation` 分支 cherry-pick/合并 `embedded_nanobot` 后端路由、服务、schema、runtime 与前端 `NanobotAgentStudio`。
2. 恢复 `/api/embedded-nanobot/*`、`/debug/embedded-nanobot`、`/workflow/nanobot-agent-studio` 等入口。
3. 确认 Nanobot 对话可以重新驱动 Agent Workshop draft / session / stage 流转。
4. 保留当前 `AgentWorkshop.vue` 直连流程作为兼容入口，但不作为唯一主链路。

### 阶段 2：构建器抽象层落地

1. 新增 `AgentBuilderProvider` 抽象接口和 DTO。
2. 新增 `EmbeddedNanobotBuilderProvider`，封装恢复后的 `EmbeddedNanobotRuntime.handle_message()`。
3. 新增 `LLMBuilderProvider` 作为测试/降级实现，包装当前 `UnifiedLLMClient` 直连逻辑。
4. `AgentWorkshopService` 改为通过 provider 进行需求澄清、缺口分析、工具规划。

### 阶段 3：nanobot 构建契约补齐

1. 新增 `tradingagents-agent-builder` Skill 或等价系统提示词片段。
2. 要求 nanobot 输出 `agent_spec`、`runtime_contract`、`prompt_contract`、`tooling_contract`。
3. Agent 工坊解析并校验 nanobot 输出契约。
4. 对不完整输出给出明确错误，而不是静默兜底。

### 阶段 4：规范与字段补齐

1. 新增 `AgentRuntimeConfig` 或内部构建函数。
2. `_build_agent_metadata()` 补 `show_in_reports`。
3. `_ensure_runtime_agent_config()` 补齐顶层字段和 metadata 字段。
4. `stage_aggregator` 支持 `show_in_reports` 过滤。

### 阶段 5：Prompt 模板链路修复

1. `_create_prompt_template()` 改为 `agent_type=universal`。
2. 发布时激活当前模板。
3. 归档或降级旧模板。
4. 加入模板命中校验。

### 阶段 6：发布前校验

1. 新增 `_validate_version_workflow_compatibility()`。
2. `publish_version()` 调用校验。
3. 错误信息返回给前端。

### 阶段 7：前端配置与可视化

1. 工坊版本预览展示 runtime 字段。
2. 支持编辑 `show_in_reports`、`report_label`、`workflow_stage` 等控制字段。
3. 发布失败时展示具体校验项。

### 阶段 8：迁移与测试

1. 编写迁移脚本补齐旧 agent_configs。
2. 编写 Prompt 模板迁移脚本。
3. 增加集成测试：工坊 Agent → 发布 → 工作流调用 → 报告展示。

---

## 14. 关键风险

1. **Embedded Nanobot 工坊链路未合并**  
   当前分支缺少历史 `embedded_nanobot` 路由、服务、runtime 和 `NanobotAgentStudio` 页面。这些提交存在于 `test/agent-workshop-validation` 独立验证分支，从未被合并到 v3.0 或 integration 线。如果不先合并，后续会把原来的 Nanobot 交互体验替换成普通 LLM 表单流程，偏离原产品设计。

2. **构建器抽象层缺失导致后续迁移成本高**  
   当前 `AgentWorkshopService` 直接拼 prompt 调 LLM。如果不先抽象 Provider，后续接入恢复后的 Embedded Nanobot 或 Hermes 会变成服务层重写。

3. **nanobot 生成契约未强制执行**  
   如果只在 Agent 工坊后处理阶段兜底，nanobot 仍可能生成不符合运行时的 Agent 草案。必须在 nanobot Skill/Prompt 层和后端校验层同时约束。

4. **模板 agent_type 改动影响旧数据**  
   需要兼容 `custom_agent` 旧模板，或提供迁移。

5. **发布时激活模板可能影响调试流程**  
   需明确 draft/testing/active 的模板生命周期。

6. **字段双写带来一致性问题**  
   建议所有写入都通过统一构建函数完成，禁止散落 `$set`。

7. **旧 AgentConfigs 缺字段**  
   必须提供迁移或读取 fallback。

8. **UniversalAgent fallback 掩盖错误**  
   发布阶段应强校验模板可命中，避免运行时悄悄降级。

---

## 15. 后续待实现任务清单

### 阶段 1：合并 Embedded Nanobot 工坊链路 ✅ (2026-06-25 完成)

- [x] 从 `test/agent-workshop-validation` 分支 cherry-pick/合并 Embedded Nanobot 工坊链路。
- [x] 恢复 `/api/embedded-nanobot/*` 后端路由和前端 `NanobotAgentStudio` 入口。
- [ ] 验证 Nanobot 对话能驱动 Agent Workshop draft / session / stage 流转。

> 合并详情：通过 `git merge test/agent-workshop-validation` 完成三方合并（共同祖先 `7a0ac1d0`），共解决 18 个冲突，提交 `de52590b`。关键文件已到位：`app/routers/embedded_nanobot.py`、`app/schemas/embedded_nanobot.py`、`app/services/embedded_nanobot_service.py`、`core/embedded_nanobot/*`、`frontend/src/api/embeddedNanobot.ts`、`frontend/src/views/Workflow/NanobotAgentStudio.vue`、`frontend/src/views/Debug/EmbeddedNanobot.vue`。前端路由 `/debug/embedded-nanobot` 和 `/workflow/nanobot-agent-studio` 已就绪。

### 阶段 2：构建器抽象层落地

- [ ] 新增 `AgentBuilderProvider` 抽象接口和 DTO。
- [ ] 新增 `EmbeddedNanobotBuilderProvider`，封装 `EmbeddedNanobotRuntime.handle_message()`。
- [ ] 新增 `LLMBuilderProvider` 作为测试/降级实现。
- [ ] `AgentWorkshopService` 改为通过 provider 进行需求澄清、缺口分析、工具规划。

### 阶段 3：nanobot 构建契约补齐

- [ ] 新增 nanobot `tradingagents-agent-builder` Skill 或等价生成规范。
- [ ] Agent 工坊解析并校验 nanobot 输出的 `runtime_contract` 和 `prompt_contract`。

### 阶段 4：规范与字段补齐

- [ ] 定义 AgentRuntimeConfig Schema。
- [ ] `_build_agent_metadata()` 补齐 `show_in_reports` 与运行时控制字段。
- [ ] `_ensure_runtime_agent_config()` 使用统一 runtime config 构建。

### 阶段 5：Prompt 模板链路修复

- [ ] `_create_prompt_template()` 改为生成 UniversalAgent 可命中的模板。
- [ ] `publish_version()` 激活当前模板、归档旧模板。

### 阶段 6：发布前校验

- [ ] 新增 `_validate_version_workflow_compatibility()`。

### 阶段 7：前端配置与可视化

- [ ] `stage_aggregator` 按 `show_in_reports` 过滤。
- [ ] 前端 Agent 工坊展示并可编辑报告控制字段。

### 阶段 8：迁移与测试

- [ ] 编写旧数据迁移脚本。
- [ ] 增加端到端测试。
