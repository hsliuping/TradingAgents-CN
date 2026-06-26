# Agent Studio 自动补 Skill 与 Skill 工坊治理化设计

> 版本：v3.0 设计文档  
> 更新时间：2026-06-26  
> 目标：让用户在 Agent Studio 中创建 Agent 时，系统能自动发现并补齐缺失 Skill；Skill 工坊从“主要创建入口”转向“能力资产管理后台”。

---

## 1. 背景与产品判断

### 1.1 用户真实目标

从用户视角看，用户通常不是为了“创建一个 Skill”而进入系统，而是为了完成更上层的任务：

- 创建一个能分析龙虎榜异动的 Agent。
- 创建一个能做概念股筛选的 Agent。
- 创建一个能生成某类研究报告的 Agent。
- 基于已有 Agent 改出一个新版本。

Skill 对用户来说是中间能力资产，不是最终目标。因此，产品主路径不应要求用户先去 Skill 工坊创建 Skill，再返回 Agent Studio 继续构建 Agent。

### 1.2 推荐产品定位

推荐采用：

```text
Agent Studio 主导创建 Agent
  -> 自动发现能力缺口
  -> 自动或半自动生成缺失 Skill
  -> 继续构建 Agent 版本

Skill 工坊
  -> 查看、测试、启停、优化、删除 Skill
  -> 查看生成历史和失败原因
  -> 保留高级手动创建入口
```

也就是说：

- Agent Studio 是“我要完成一个智能助手”的主入口。
- Skill 工坊是“我有哪些可复用能力”的管理后台。
- Skill 创建可以保留手动入口，但不再是普通用户完成 Agent 创建的必经步骤。

---

## 2. 当前代码现状

### 2.1 Agent Studio 现状

当前 Agent Studio 前端位于：

```text
frontend/src/views/Workflow/AgentStudio.vue
```

已具备的关键能力：

1. 中间聊天区承载用户与 Nanobot 的多轮交互。
2. 通过 `embeddedNanobotApi.chatStream()` 调用嵌入式 Nanobot 流式接口。
3. 前端已能展示工具执行事件：
   - `nanobotToolEvents`
   - `progressSteps`
   - `nanobotProgressHint`
4. 右侧状态栏已能展示：
   - 当前版本状态。
   - 测试进度。
   - 工具事件列表。
   - 版本详情和发布信息。
5. 版本详情区已经支持查看和编辑部分运行时字段：
   - `output_field`
   - `workflow_stage`
   - `report_label`
   - `show_in_reports`
   - `execution_order`

这说明 Agent Studio 已经有承载“正在补齐能力缺口”“正在生成 Skill”“正在注册能力”等进度提示的前端基础。

### 2.2 Embedded Nanobot 现状

后端入口位于：

```text
app/routers/embedded_nanobot.py
app/services/embedded_nanobot_service.py
core/embedded_nanobot/runtime.py
```

当前链路：

```text
AgentStudio.vue
  -> embeddedNanobotApi.chatStream()
  -> /api/embedded-nanobot/chat/stream
  -> EmbeddedNanobotService.chat()
  -> EmbeddedNanobotRuntime.handle_message()
  -> Nanobot 工具选择与执行
```

`EmbeddedNanobotRuntime` 当前已将 Agent Builder 工具和 Skill Creation 工具分组注册：

```text
AGENT_BUILDER_TOOL_IDS
SKILL_CREATION_TOOL_IDS
```

其中 Agent Builder 工具包括：

- `search_project_capabilities`
- `analyze_agent_workshop_gaps`
- `generate_agent_workshop_tooling_plan`
- `build_agent_workshop_version`
- `resolve_agent_workshop_blocking_gaps`

Skill Creation 工具包括：

- `start_external_skill_generation_session`
- `respond_to_external_skill_generation_session`
- `preview_external_skill_spec`
- `generate_confirmed_external_skill`
- `inspect_external_skill_generation_session`

当前说明：

- Nanobot 已经能访问 Agent 构建工具。
- Nanobot 也已经能访问 Skill 生成工具。
- 两条链路已经具备打通基础。

### 2.3 Skill 工坊现状

Skill 工坊前端主要位于：

```text
frontend/src/views/Workflow/SkillGeneration.vue
frontend/src/views/Workflow/SkillGenerationCreate.vue
```

当前 Skill 工坊具备：

1. 未完成草稿列表。
2. 已生成 Skill 列表。
3. Skill 状态筛选。
4. 查看代码。
5. 查看沟通历史。
6. 测试 Skill。
7. 优化 Skill。
8. 启用/禁用 Skill。
9. 删除 Skill。

这已经很接近“能力资产管理后台”的形态。

### 2.4 Skill 生成服务现状

后端 API 位于：

```text
app/routers/skill_generation.py
```

业务服务位于：

```text
app/services/skill_generation_service.py
```

核心能力：

1. `start_session()`：启动需求沟通。
2. `respond_to_session()`：多轮澄清需求。
3. `preview_spec()`：生成 SkillSpec 预览和侦察报告。
4. `confirm_spec()`：确认规格并触发生成管线。
5. `list_skills()` / `get_skill()`：管理已生成 Skill。
6. `test_skill()`：测试 Skill。
7. `optimize_skill()`：优化 Skill。
8. `update_skill_status()`：启停 Skill。
9. `delete_skill()`：删除 Skill。

底层管线封装在：

```text
core/tools/external/*
```

包括：

- 需求分析：`RequirementAnalyzer`
- 侦察：`DefaultReconnaissanceController`
- 迭代控制：`IterationController`
- 静态校验、沙箱执行、输出评估等组件

生成完成后 `_save_skill()` 会：

1. 写入 `external_skills` 集合。
2. 设置 `source = generated`。
3. 写入 `generation_context`。
4. 调用 `register_single_external_skill()` 热注册到工具注册表。
5. 调用 `CapabilityIndexService.ensure_index()` 同步能力索引。

当前补充说明：

- `start_session()` 已支持传入 `handoff_context`，因此 Agent Studio -> SkillGenerationService 的来源透传在接口层面已经有基础。
- 但 `_save_skill()` 目前还没有把 `origin_workshop_session_id`、`origin_spec_id`、`origin_gap_id` 这类反向来源字段写回 `external_skills`。

这说明由 Skill 工坊生成的 Skill 已经可以被系统工具注册表和能力检索系统识别，也可以被 Agent 构建流程复用；但“来源追踪”目前还不完整。

---

## 3. 当前主要问题

### 3.1 用户路径割裂

当前用户在 Agent Studio 创建 Agent 时，如果发现缺 Skill，理想路径应该在当前上下文内解决。

但传统路径容易变成：

```text
Agent Studio 发现缺能力
  -> 用户离开 Agent Studio
  -> 进入 Skill 工坊创建 Skill
  -> 回到 Agent Studio
  -> 重新构建 Agent
```

这会导致：

1. 用户上下文中断。
2. 用户不清楚要创建什么 Skill。
3. Skill 创建后是否已被当前 Agent 复用不直观。
4. 创建 Agent 的主流程变长。

### 3.2 阻塞式自动补全可能等待过久

现有 `resolve_agent_workshop_blocking_gaps` 是阻塞式聚合工具：

```text
读取 blocking_gaps
  -> 并行启动 Skill 生成会话
  -> preview
  -> confirm
  -> 轮询等待 completed / failed / timeout
  -> 返回生成结果
```

优点：

- Nanobot 不需要原生子流程能力。
- 一个工具调用即可完成缺口补齐。
- 实现成本低。

风险：

- 单个 Skill 生成可能需要较长时间。
- 多个缺口并行生成时，用户等待感明显。
- 如果缺口描述不够清楚，自动 respond/preview/confirm 可能把需求收窄错。
- 阻塞等待期间，如果前端只显示“正在执行工具”，用户会觉得卡住。

### 3.3 完全让 Nanobot 自己写 Skill 也有风险

Nanobot 具备 `read_file`、`write_file`、`edit_file`、`exec`、`web_search`、`web_fetch` 等能力，理论上可以自己读取项目代码、写 Python 脚本、执行验证。

但如果完全绕过 SkillGenerationService，会丢失：

1. SkillSpec 规范。
2. 侦察报告。
3. 静态校验。
4. 沙箱执行。
5. Judge 评分。
6. 自动迭代修复。
7. `external_skills` 入库规范。
8. `ToolRegistry` 热注册。
9. `CapabilityIndexService` 能力索引同步。
10. Skill 生成历史与管理记录。

因此不推荐让 Nanobot 直接写 Python 文件后就当作正式 Skill 使用。

### 3.4 把所有管线组件拆给 Nanobot 也不一定更稳

也可以把侦察、校验、沙箱、评分等管线组件都包装成 Nanobot 工具，让 Nanobot 自己控制流程。

但风险包括：

1. 工具数量膨胀，增加上下文 token 压力。
2. 外层 Nanobot LLM 决策 + 内层代码生成/评分 LLM，形成 LLM 级联。
3. 流程更自由，但更难保证每次都走完整质量闭环。
4. 前端进度和后端状态难统一。
5. 对普通用户来说没有明显感知收益。

所以更推荐：Nanobot 负责决策和交互，SkillGenerationService 负责正式生成和质控。

---

## 4. 目标设计

### 4.1 总体原则

```text
Nanobot 负责：理解需求、发现缺口、询问确认、触发补齐、继续构建 Agent
SkillGenerationService 负责：Skill 需求结构化、规格预览、代码生成、验证、评分、入库、注册
Skill 工坊负责：展示、管理、测试、优化、启停、删除、查看历史
```

原则：

1. 用户不需要离开 Agent Studio 才能补 Skill。
2. 正式 Skill 必须进入 `external_skills` 集合并被 Skill 工坊管理。
3. 自动补 Skill 必须显示阶段进度，不能让用户长时间盲等。
4. 缺口补齐必须支持人工确认，避免自动生成错误能力。
5. Skill 工坊继续保留手动创建入口，但定位为高级入口。

### 4.2 推荐架构

```text
用户在 Agent Studio 描述 Agent 需求
  -> Nanobot 调 search_project_capabilities 搜索现有能力
  -> Nanobot 调 analyze_agent_workshop_gaps 分析缺口
  -> 若无 blocking_gaps
      -> build_agent_workshop_version
  -> 若有 blocking_gaps
      -> Nanobot 给用户解释缺口
      -> 用户确认是否自动补 Skill
      -> resolve_agent_workshop_blocking_gaps 或异步补齐工具
      -> SkillGenerationService 生成并注册 Skill
      -> CapabilityIndexService 更新能力索引
      -> Nanobot 重新 search_project_capabilities
      -> build_agent_workshop_version
  -> 用户测试并发布 Agent
```

### 4.3 用户体验流程

#### 场景：创建龙虎榜分析 Agent

```text
用户：我想创建一个能分析涨停龙虎榜异动的 Agent。

系统：我先检查当前项目是否已有相关能力。

系统进度：
- 正在搜索现有工具和 Skill
- 正在分析 Agent 能力缺口

系统：当前缺少【龙虎榜数据查询】能力。
这个能力适合沉淀为可复用 Skill。
是否现在自动创建？创建完成后我会继续生成 Agent。

用户：确认。

系统进度：
- 正在分析 Skill 需求
- 正在生成 Skill 规格
- 正在侦察可用数据源
- 正在生成 Python 实现
- 正在执行沙箱验证
- 正在注册到 Skill 工坊
- 正在重新构建 Agent 版本

系统：已创建 Skill【龙虎榜数据查询】，并绑定到当前 Agent 候选版本 v1。
你可以现在查看测试结果或继续优化。
```

#### 失败恢复流程

Skill 生成失败后，需要完整的恢复路径，不能让用户不知道下一步该做什么。

```text
系统：Skill【龙虎榜数据查询】生成失败。

失败原因：沙箱执行超时（60s），可能是 AKShare 接口响应慢。
建议：1) 重试生成  2) 修改需求描述（例如更换数据源）  3) 改为手动创建并跳转 Skill 工坊

用户点击"重试"：
  -> 重新走完整管线（从需求澄清开始，利用上次的 spec 作为起点）
  -> 连续失败 3 次后，自动建议转手动创建

用户点击"修改需求描述"：
  -> 展示上次的 SkillSpec 预览
  -> 用户可编辑需求描述
  -> 重新走完整管线

用户点击"改为手动创建"：
  -> 跳转到 SkillGenerationCreate.vue
  -> 预填缺口描述和 handoff_context
  -> 用户手动完成创建
```

关键规则：

- 失败信息必须结构化：`{ stage: "sandbox", error: "超时", suggestion: "重试或更换数据源" }`
- 连续失败 3 次后，强制建议转手动创建，不允许无限重试
- 每次重试保留上次的 spec 作为起点，避免完全从头开始
- 失败详情记录到 `agent_workshop_gap_resolution_jobs` 的 gap 条目中

### 4.4 Skill 工坊新定位

Skill 工坊页面不再强调“用户必须从这里创建 Skill”，而应改为：

```text
能力资产中心
```

核心模块：

1. 全部 Skill 列表。
2. 生成中 Skill 列表。
3. 失败 Skill 列表。
4. AI 自动生成 Skill 标识。
5. 来源标识：
   - Agent Studio 自动补齐
   - Skill 工坊手动创建
   - ClawHub 导入
   - 系统内置
6. 被哪些 Agent 使用。
7. 最近测试结果。
8. 最后一次失败原因。
9. 启用/禁用。
10. 优化。
11. 删除。
12. 查看代码与历史。

手动创建按钮保留，但文案调整为：

```text
手动创建 Skill（高级）
```

**手动创建 Skill 如何被 Agent Studio 发现**：

手动创建的 Skill 在 `_save_skill()` 中已调用 `CapabilityIndexService.ensure_index()`，因此 `search_project_capabilities` 可以立即检索到。但需要确保：

1. 手动创建完成后，`CapabilityIndexService` 的索引已更新（当前已支持）。
2. 用户回到 Agent Studio 后，`search_project_capabilities` 能命中新 Skill（当前已支持）。
3. 验收标准中增加一条：手动创建的 Skill 在 Agent Studio 的缺口分析中不再被识别为 blocking gap。

---

## 5. 技术方案

### 5.1 不推荐方案

#### 方案 A：让用户手动跳转 Skill 工坊创建

不推荐。

原因：

1. 割裂 Agent 创建上下文。
2. 用户要理解 Skill 规范，门槛高。
3. 回到 Agent Studio 后是否自动绑定不明确。

#### 方案 B：Nanobot 完全自己写 Python Skill

不推荐作为正式路径。

原因：

1. 容易绕过 `external_skills` 规范。
2. 容易绕过热注册和能力索引。
3. 缺少统一质量控制。
4. Skill 工坊无法完整管理。

#### 方案 C：把所有 Skill 管线组件拆成 Nanobot 工具

暂不推荐。

原因：

1. 工具数量增加，token 成本上升。
2. LLM 级联带来不稳定。
3. 前端进度和后端状态更难治理。
4. 用户感知收益有限。

### 5.2 推荐方案：Nanobot 编排 + SkillGenerationService 生成

推荐路径：

```text
Nanobot
  -> 判断是否需要补 Skill
  -> 向用户解释和确认
  -> 调用聚合工具或异步工具
  -> 读取生成结果
  -> 继续构建 Agent

SkillGenerationService
  -> 负责正式 Skill 生成、验证、评分、入库、注册
```

### 5.3 聚合工具改造建议

当前已有：

```text
resolve_agent_workshop_blocking_gaps
```

建议保留，但需要明确区分“当前实现”和“目标演进”。

当前实现：

```text
resolve_agent_workshop_blocking_gaps
  -> 从 session 或参数读取 blocking gaps
  -> 为每个 gap 启动 SkillGenerationService session
  -> 并行轮询等待 completed / failed / timeout
  -> 一次性返回结果
```

也就是说，它现在是“阻塞式聚合工具”，内部会并行处理多个 gap，但还不是异步 job 模式。

#### 5.3.1 阻塞模式

适用场景：

- 只有 1 个简单缺口。
- 用户明确表示“现在就补齐”。
- 预计生成时间可接受。

行为：

```text
调用后等待 completed / failed / timeout
返回完整结果
```

#### 5.3.2 异步模式（目标态）

新增建议工具：

```text
start_agent_workshop_gap_resolution
inspect_agent_workshop_gap_resolution
```

行为：

```text
start_agent_workshop_gap_resolution
  -> 创建 gap_resolution_job
  -> 后台启动一个或多个 SkillGenerationService session
  -> 立即返回 job_id 和初始状态

inspect_agent_workshop_gap_resolution
  -> 查询 job 当前进度
  -> 返回每个 gap 对应的 skill_session 状态
  -> 返回 completed / failed / timeout 明细
```

优势：

1. 用户不会长时间卡在一个工具调用中。
2. Agent Studio 可以持续展示阶段进度。
3. 失败后可以单独重试某个缺口。
4. 后续可接通知系统。

#### 5.3.3 异步任务的执行载体与生命周期（关键约束）

异步化最大的实现风险不在工具签名，而在“后台任务跑在哪、谁来保活”。Skill 生成是分钟级长任务，必须明确执行载体，否则会出现“`start_*` 返回 job_id，但后台协程随请求结束被取消”的隐性失败。

硬约束：

1. **禁止用请求事件循环里的 `asyncio.create_task` 承载补齐任务。** 在 FastAPI 请求生命周期内创建的协程，会在请求/连接结束时被取消，导致 job 卡在 `running` 永不推进。
2. **优先复用项目已有的后台 worker / 任务队列基础设施**（与定时任务、分析任务同一套承载），而不是为 gap resolution 新造一套并发模型。
3. `start_agent_workshop_gap_resolution` 只负责：写入 `agent_workshop_gap_resolution_jobs`（status=pending）+ 投递后台作业 + 立即返回 `job_id`。
4. 真正的 Skill 生成由 worker 进程消费，进度通过更新 job 文档落库，前端/`inspect_*` 一律以 job 文档为单一事实来源（拉取式），不依赖内存态。
5. worker 重启后应能从 `pending / running` 的 job 文档恢复或安全标记为 `failed`，避免“孤儿 running”。

这样异步模式才真正解决等待问题，而不是把阻塞从“工具调用内”挪到“一个会被回收的协程里”。

### 5.4 建议新增集合（目标态）

如果实现异步模式，建议新增：

```text
agent_workshop_gap_resolution_jobs
```

字段建议：

```json
{
  "job_id": "gap_job_xxx",
  "workshop_session_id": "ws_xxx",
  "spec_id": "spec_xxx",
  "version_id": null,
  "user_id": "user_xxx",
  "status": "pending|running|partial_completed|completed|failed|cancelled|timeout",
  "mode": "auto|manual_confirmed",
  "gaps": [
    {
      "gap_id": "gap_1",
      "description": "龙虎榜数据查询能力",
      "status": "pending|generating|completed|failed|timeout",
      "skill_session_id": "skill_session_xxx",
      "skill_tool_id": "longhubang_query",
      "skill_display_name": "龙虎榜数据查询",
      "pipeline_stage": "code_generation",
      "pipeline_message": "正在生成 Python 实现",
      "error": null,
      "created_at": "...",
      "updated_at": "..."
    }
  ],
  "created_at": "...",
  "updated_at": "..."
}
```

### 5.5 进度事件设计

当前情况：

- Agent Studio 前端已经能显示 `tool_event`、`progress`、`step_event`。
- 现有阻塞式 `resolve_agent_workshop_blocking_gaps` 已经可以通过 Nanobot 的流式工具事件呈现阶段性进度。
- 但由于尚未实现异步 job，下面的 `job_id / gap_id` 负载结构应视为“目标态统一协议”，不是当前稳定接口。

因此后端工具返回或流式事件建议统一成：

```json
{
  "type": "tool_event",
  "name": "resolve_agent_workshop_blocking_gaps",
  "status": "started|progress|completed|failed",
  "title": "补齐 Agent 能力缺口",
  "detail": "正在生成 Skill：龙虎榜数据查询",
  "payload": {
    "job_id": "gap_job_xxx",
    "gap_id": "gap_1",
    "pipeline_stage": "sandbox",
    "pipeline_message": "正在执行沙箱验证"
  }
}
```

前端展示建议：

1. 中间聊天区显示简短进度。
2. 右侧状态栏显示详细工具事件。
3. Skill 生成超过一定时间时，提示“可稍后回来查看，生成完成后会出现在 Skill 工坊”。
4. 生成失败时，展示失败原因和“重试 / 手动调整需求”入口。

### 5.6 Skill 去重策略

两个不同的 Agent 可能都需要同一个能力（比如都需要"龙虎榜数据查询"）。如果 `search_project_capabilities` 因为描述差异导致命中失败，管线会生成两个功能几乎一样的 Skill，造成能力碎片化。

当前状态：

- 这套去重机制目前还没有落地到 `resolve_agent_workshop_blocking_gaps`。
- 因此本节应视为 Phase 2.5 的目标设计，而不是当前已具备能力。

目标去重机制（两段式，先廉价后精确）：

1. 对每个 blocking_gap 的描述，**先用 `CapabilityIndexService` 的能力索引（embedding 检索）做初筛**，而不是一上来就调 LLM。这能复用既有索引、避免 LLM 级联，成本低、可批量。
2. 仅对落在**边界区间（相似度 0.6–0.85）**的候选，再调一次 LLM 做功能相似度复核；高于上界直接判为高匹配、低于下界直接判为新能力，都不需要 LLM。
3. 匹配结果分级（相似度阈值同时供 embedding 初筛与 LLM 复核使用）：
   - **高匹配（相似度 > 0.85）**：提示用户"已有近似 Skill X，是否直接复用？"并提供选项：复用现有 / 创建新版本 / 仍新建。
   - **中匹配（相似度 0.6-0.85）**：列出候选 Skill，让用户确认是复用还是新建。
   - **低匹配（相似度 < 0.6）**：视为新能力，正常进入生成流程。
4. 去重结果记录到 gap_resolution_job 的 `dedup_result` 字段。

**验收**：同一个数据能力（如"龙虎榜数据查询"）不会因不同 Agent 触发而重复生成 Skill。

### 5.7 Skill 版本与 Agent 版本的关系

Skill 后续被优化后，已绑定旧版 Skill 的 Agent 版本会面临行为变化问题。

这里必须区分“当前实现”和“目标策略”。

当前实现：

- Agent 版本通过 `required_tools` 记录 `tool_id`。
- 运行时 external skill 的注册与加载是按 `external_skills` 当前 active 记录生效。
- 因此，当前并不能严格保证“Agent 版本默认冻结绑定时的 Skill 快照”。

这意味着：

- 如果同一个 `tool_id` 对应的 external skill 实现被覆盖或重注册，旧 Agent 版本理论上可能受到影响。
- 当前系统更接近“按逻辑工具名绑定”，而不是“按 Skill 历史版本快照绑定”。

目标策略：

**推荐策略**：未来让 Agent 版本支持冻结绑定时的 Skill 快照。

具体规则：

| 场景 | 行为 |
|------|------|
| Agent v1 绑定 Skill A（当前版本） | 当前实现只保证记录 `tool_id = A`，不保证严格冻结 |
| Skill A 被优化（代码更新） | 目标态不影响 Agent v1；当前实现下需视 external skill 注册方式而定 |
| Agent 升级到 v2 | 用户可选择"更新到最新 Skill"或"保持当前绑定" |
| Skill A 被删除 | 标记为 degraded，Agent 版本仍可运行但提示"依赖 Skill 已不可用" |

目标实现方式：

- 短期：继续通过 `required_tools` 中的 `tool_id` 绑定 Skill，但文档和产品语义都不要宣称“已冻结”。
- 中期：在 `external_skills` 中引入显式历史版本或不可变快照记录。
- 长期：在 Agent 版本中记录 `skill_version_ref` 或等价的快照引用，实现可复现、可回滚、可审计的严格绑定。

### 5.8 用户确认策略

自动补 Skill 不能完全静默执行。建议规则：

`analyze_agent_workshop_gaps` 的 LLM 输出中应包含 `gap_severity` 字段，用于区分缺口严重程度：

| severity | 含义 | 示例 |
|----------|------|------|
| `cosmetic` | 轻量缺口，不影响功能 | 报告格式调整、字段映射 |
| `functional` | 需要新能力，但可降级运行 | 缺少某个数据源，但可用替代方案 |
| `blocking` | 阻塞性缺口，不补齐无法工作 | 没有龙虎榜数据，Agent 核心功能无法实现 |

| 缺口类型 | 行为 |
|----------|------|
| `cosmetic` 缺口 | 可自动处理，生成后提示用户 |
| `functional` 缺口 | 必须用户确认后再生成 |
| `blocking` 缺口 | 必须用户确认，且生成前展示 SkillSpec 预览 |
| 需要联网抓取或依赖第三方接口 | 必须提示数据来源和风险 |
| 可能涉及交易建议、买卖信号、仓位建议 | 拒绝生成或强制加入合规约束 |
| 一次超过 3 个 Skill | 提示分批生成 |

合规约束落地要求：涉及交易建议/买卖信号/仓位建议的判定与拦截，应**复用项目既有的全局非投顾合规校验**，不要在补齐链路里新写一套独立规则，避免口径漂移。

### 5.9 Skill 规范来源

Nanobot 不需要自己记住全部 Skill 规范，规范应来自项目已有系统：

1. `SkillSpec` 模型。
2. `RequirementAnalyzer` 提示词。
3. `DefaultReconnaissanceController` 的侦察规则。
4. `IterationController` 的验证和评分闭环。
5. `SkillGenerationService._save_skill()` 的入库和注册规范。

Nanobot 只需要知道：

```text
正式 Skill 必须通过 SkillGenerationService 生成或注册，不能只写临时 Python 脚本。
```

---

## 6. 前端改造建议

### 6.1 Agent Studio

需要增强：

1. 在聊天中展示“发现能力缺口”的卡片。
2. 卡片中列出：
   - 缺口名称。
   - 为什么当前 Agent 需要它。
   - 是否已有近似能力。
   - 建议生成的 Skill 名称。
   - 预计会创建的输入输出。
3. 提供操作按钮：
   - 自动创建 Skill 并继续。
   - 暂不创建，先生成受限版本。
   - 手动调整需求。
4. 右侧状态栏增加“能力补齐”区块：
   - 当前 job 状态。
   - 每个 gap 的生成状态。
   - 对应 Skill 链接。
5. 生成完成后，在消息中明确说明：
   - 已创建哪个 Skill。
   - 是否已绑定到当前 Agent。
   - 是否需要重新测试。

#### 右侧面板布局设计

Agent Studio 右侧面板当前已有：版本状态、测试进度、工具事件列表、版本详情。如果再加"能力补齐"区块会非常拥挤。

**建议用 Tab 或折叠面板（Collapse）按当前阶段动态显示**：

```text
右侧面板（根据 Agent 创建阶段动态显示）

[版本状态]       ← 始终显示
─────────────────
当前阶段：缺口分析
  [能力缺口]      ← 当前阶段主区块，展开
    - 缺口 1：龙虎榜数据查询 (blocking)
    - 缺口 2：概念股分类映射 (functional)
    [开始补齐] [暂不处理]

─────────────────
当前阶段：能力补齐中
  [补齐进度]      ← 当前阶段主区块，展开
    - Skill A：正在生成 Python 实现 (3/5 轮)
    - Skill B：等待中

─────────────────
当前阶段：测试中
  [测试进度]      ← 当前阶段主区块，展开

[工具事件]       ← 折叠面板，始终可切换
[版本详情]       ← 折叠面板，始终可切换
[发布配置]       ← 折叠面板，始终可切换
```

原则：

- 一次只展开一个主区块，避免信息过载。
- 其他区块用折叠面板组织，用户可手动切换。
- 当前阶段完成后自动切换到下一阶段的主区块。

### 6.2 Skill 工坊

需要调整定位和文案：

1. 页面标题从“AI Skill 工坊”可调整为“Skill 能力中心”。
2. “创建新 Skill”改为“手动创建 Skill”。
3. 新增来源筛选：
   - Agent Studio 自动补齐。
   - 手动创建。
   - ClawHub 导入。
   - 系统内置。
4. 新增使用关系：
   - 被哪些 Agent 使用。
   - 最近一次调用时间。
   - 最近一次失败。
5. 未完成草稿中标注来源：
   - 来自 Agent Studio 的缺口补齐。
   - 来自用户手动创建。
6. 对生成中的 Skill 提供“查看进度”。

#### SkillGenerationCreate.vue 向导页面的去留

当前有两个 Skill 相关的前端页面：

| 页面 | 路由 | 当前定位 |
|------|------|----------|
| `SkillGeneration.vue` | `/workflow/skill-generation` | 列表页 + 草稿管理 |
| `SkillGenerationCreate.vue` | `/workflow/skill-generation/create` | 4 步创建向导 |

**建议**：两者都保留，但定位调整。

| 页面 | 新定位 |
|------|--------|
| `SkillGeneration.vue` | 能力资产中心（列表、管理、测试、启停） |
| `SkillGenerationCreate.vue` | 高级手动创建入口（保留向导式体验） |

`SkillGenerationCreate.vue` 的入口来源：

1. Skill 工坊列表页的"手动创建 Skill"按钮。
2. Agent Studio 失败恢复流程中的"改为手动创建"按钮（预填缺口描述和 `handoff_context`）。
3. 从 Agent Studio 的能力缺口卡片中的"手动调整需求"入口（预填缺口描述）。

改动要点：

- 支持从 URL 参数接收 `gap_description` 和 `handoff_context`，预填到创建向导的第一步。
- 创建完成后，如果来源是 Agent Studio，提示用户"已创建，可返回 Agent Studio 继续构建 Agent"。

---

## 7. 后端改造建议

### 7.1 Agent Builder 工具层

保留并增强：

```text
resolve_agent_workshop_blocking_gaps
```

当前状态：

- 已实现的只有 `resolve_agent_workshop_blocking_gaps`。
- 它当前是同步等待式工具，不是异步 job 工具族。

建议新增：

```text
start_agent_workshop_gap_resolution
inspect_agent_workshop_gap_resolution
cancel_agent_workshop_gap_resolution
retry_agent_workshop_gap_resolution_item
```

其中：

- `start_*` 负责异步启动。
- `inspect_*` 负责 Nanobot 和前端查询状态。
- `cancel_*` 用于用户取消长时间任务。
- `retry_*` 用于单个 gap 失败后重试。

### 7.2 SkillGenerationService

当前状态：

1. `start_session()` 已支持 `handoff_context`，但当前 gap 补齐工具传入的字段还比较少，主要是：
   - `source`
   - `source_spec_id`
   - `source_name`
   - `target_capability`
   - `handoff_intent`
2. `_save_skill()` 当前会入库、热注册、重建能力索引，但还不会写入完整的反向来源字段。

> 归属问题（需在 Phase 2 一并处理）：当前 `resolve_agent_workshop_blocking_gaps` 启动 Skill 会话时硬编码 `user_id="nanobot"`，会导致生成的 Skill 不归属真实用户，进而让 Skill 工坊的来源筛选、权限校验、配额统计全部错位。补 `handoff_context` 时必须**同步透传发起补齐的真实 `user_id`**，而不是留到 Phase 5 再补。

建议增强：

1. `start_session()` 支持更完整的 `handoff_context`：
   - `source = agent_studio_gap`
   - `user_id`（发起补齐的真实用户，替换硬编码的 `nanobot`，用于归属与权限）
   - `workshop_session_id`
   - `spec_id`
   - `version_id`
   - `gap_id`
   - `agent_name`
   - `agent_goal`
2. `_save_skill()` 保存反向来源：
   - `origin_source = agent_studio_auto_gap_resolution`
   - `origin_workshop_session_id`
   - `origin_spec_id`
   - `origin_gap_id`
3. 生成完成后更新 `agent_workshop_gap_resolution_jobs`。
4. 失败时记录结构化失败原因。

### 7.3 CapabilityIndexService

生成 Skill 后必须重新索引，确保后续：

```text
search_project_capabilities
```

可以立即发现新 Skill。

当前 `_save_skill()` 已调用 `CapabilityIndexService.ensure_index()`，但建议补充验收：

1. 新 Skill 入库后能被能力检索搜索到。
2. 新 Skill 能被 Agent 构建工具绑定。
3. 新 Skill 在 Skill 工坊列表可见。

### 7.4 AgentWorkshopService

当前状态：

- `build_agent_workshop_version` 已经会生成 `required_tools`、`required_capabilities`、PromptTemplate、execution_plan，并同步运行时 `agent_configs`。
- 但缺口补齐后生成的 `skill_tool_id` 还没有以结构化来源信息写回当前 Session / Version。

建议在缺口补齐完成后支持：

1. 将生成的 `skill_tool_id` 写入当前 Session 的 `tooling_plan`。
2. 将生成的 `skill_tool_id` 作为 `build_agent_workshop_version` 的候选工具。
3. 在 Version 的 `required_tools` / `required_capabilities` 中记录来源。
4. 在 Version metadata 中记录：

```json
{
  "auto_resolved_gaps": [
    {
      "gap": "龙虎榜数据查询能力",
      "skill_tool_id": "longhubang_query",
      "skill_session_id": "skill_session_xxx"
    }
  ]
}
```

---

## 8. 状态机设计

### 8.1 Agent 创建阶段

当前前端实际已使用的阶段更接近：

```text
requirement-intake
confirmation
generation
governance
testing
evaluation
publish-ready
published
blocked
```

建议未来在 Agent Studio 中进一步扩展为：

```text
requirement-intake
confirmation
gap-analysis
capability-resolution
version-generation
testing
evaluation
publish-ready
published
blocked
```

新增阶段：

```text
capability-resolution
```

表示正在补齐 Skill 或其他能力缺口。

### 8.2 Gap Resolution Job 状态（目标态）

```text
pending
running
partial_completed
completed
failed
timeout
cancelled
```

### 8.3 单个 Gap 状态（目标态）

```text
pending
clarifying
previewing
generating
validating
registering
completed
failed
timeout
cancelled
```

---

## 9. 实施计划

### 9.0 推荐实施顺序

为了降低改造风险，建议按下面的依赖顺序推进，而不是并行铺开：

1. 先完成 `Phase 2`，把现有阻塞式补齐工具做稳，确保最短路径可用。
2. 再完成 `Phase 2.5`，补去重与复用，避免在异步化之前先放大量重复 Skill 进入库。
3. 然后进入 `Phase 3`，把长任务体验从“阻塞式等待”升级到“异步 job + 可查询进度”。
4. 最后再做 `Phase 4` 和 `Phase 5`，分别解决治理体验与版本追溯深度。

推荐原因：

- `Phase 2` 解决的是“能不能用”的问题，是最小闭环。
- `Phase 2.5` 解决的是“会不会越用越乱”的问题，应在规模放大前处理。
- `Phase 3` 解决的是“好不好用”的问题，但依赖前面把流程与字段收敛。
- `Phase 4/5` 更偏治理和资产化，适合在主链路稳定后补齐。

### Phase 1：文档与策略收口

目标：统一产品和技术方向。

内容：

1. 明确 Agent Studio 是主创建入口。
2. 明确 Skill 工坊是能力资产中心。
3. 明确正式 Skill 必须由 SkillGenerationService 入库和注册。
4. 明确自动补齐需要用户确认和进度提示。

### Phase 2：增强现有阻塞式补齐工具

目标：先让现有 `resolve_agent_workshop_blocking_gaps` 可用且体验可接受。

内容：

1. 补充更完整的 `handoff_context`（含真实 `user_id` 透传，替换硬编码 `nanobot`，确保 Skill 归属与权限正确）。
2. 返回更结构化的阶段信息。
3. 限制默认一次最多补 1~3 个缺口。
4. 对需要外部数据源的 Skill 增加用户确认提示。
5. 生成完成后自动重新检索能力并构建版本。

前置依赖：

- `SkillGenerationService.start_session()` 的 `handoff_context` 字段约定先收敛。
- `resolve_agent_workshop_blocking_gaps` 的返回结构先标准化，避免后面异步化时前端协议再改一轮。

建议拆分顺序：

1. 先补 `handoff_context` 字段。
2. 再补结构化返回体和阶段信息。
3. 最后再决定是否默认“自动继续 build_version”，避免在主链路还不稳定时把行为耦合得过深。

本阶段验收：

1. 单个 blocking gap 可稳定完成“启动 Skill 会话 -> 预览 -> 确认生成 -> 等待完成”。
2. 生成完成后，新 Skill 已入库、已热注册、已建立能力索引。
3. 工具返回体中能明确看到每个 gap 的状态、耗时、错误原因。

### Phase 2.5：Skill 去重与复用

目标：在异步化之前先把去重逻辑补上，避免生成大量重复 Skill。

内容：

1. 在 `resolve_agent_workshop_blocking_gaps` 中增加去重检查。
2. 实现 LLM 功能相似度判断。
3. 提供复用 / 新建 / 创建新版本的选项。
4. 在 `Phase 3` 落地前，先把去重结果记录到当前工具返回体或 session 上下文中；等 `gap_resolution_job` 引入后再迁移到 job 文档。
5. 验收：同一个数据能力不会重复生成。

前置依赖：

- `Phase 2` 已经把 gap 描述、Skill session 启动参数和返回结构稳定下来。

本阶段验收：

1. 对明显同义的能力缺口，不会直接重复创建新 Skill。
2. 复用已有 Skill 时，后续 `build_agent_workshop_version` 能消费该结果。
3. 对“低相似度但高风险误判”的场景，系统优先要求用户确认，而不是自动复用。

### Phase 3：实现异步 Gap Resolution Job

目标：解决长时间等待问题。

内容：

1. 新增 `agent_workshop_gap_resolution_jobs` 集合。
2. 新增 `start_agent_workshop_gap_resolution`。
3. 新增 `inspect_agent_workshop_gap_resolution`。
4. Agent Studio 右侧状态栏展示 job 进度。
5. 失败支持单项重试。

前置依赖：

- `Phase 2` 已经把单个 gap 的执行链路做稳定。
- `Phase 2.5` 已经把去重逻辑前置进主流程，避免异步 job 上线后直接并发制造重复 Skill。

建议补充：

1. 明确 `job` 的唯一键与幂等策略，避免重复点击生成多个并行任务。
2. 明确 `start / inspect / cancel / retry` 的状态流转和权限边界。
3. 明确“半成功”补偿机制，例如 Skill 已生成但 job 状态写回失败时如何修复。
4. 明确执行载体（见 §5.3.3）：补齐任务由后台 worker / 任务队列承载，禁止用请求事件循环的 `asyncio.create_task`；`inspect_*` 与前端以 job 文档为单一事实来源，worker 重启需能恢复或安全终结遗留 job。

本阶段验收：

1. 用户关闭页面后再回来，仍可查看正在运行的补齐任务。
2. 同一个 gap resolution 请求重复触发时，不会生成重复 job。
3. 单个 gap 失败时，可以重试该项而不是整批重跑。

### Phase 4：Skill 工坊治理化改造

目标：把 Skill 工坊从创建向导升级为能力资产中心。

内容：

1. 调整页面标题和文案。
2. 增加来源筛选。
3. 增加 Agent 使用关系。
4. 增加生成中/失败状态视图。
5. 增加从 Agent Studio 跳转到 Skill 详情。

前置依赖：

- `Phase 3` 已经提供 job / session / skill 之间的可追踪关系。

本阶段验收：

1. 列表页能看出 Skill 是手动创建还是 Agent Studio 自动补齐。
2. 能从 Skill 详情反查来源 Agent、来源 session、来源 gap。
3. 能从 Agent Studio 跳到对应 Skill 详情页，而不是只能停留在消息文本里。

### Phase 5：版本绑定与可追溯性

目标：让自动补齐的 Skill 可追溯、可审计、可复用。

内容：

1. AgentVersion 记录自动补齐 Skill。
2. Skill 记录来源 Agent/Session/Gap。
3. Skill 工坊可查看“由哪个 Agent 创建”。
4. Agent Studio 可查看“当前 Agent 依赖哪些自动生成 Skill”。

前置依赖：

- `Phase 4` 已经把展示层治理能力补齐。
- 如果要做“严格冻结绑定”，这里还需要单独的数据模型升级，而不是只补展示字段。

建议拆成两个层级：

1. 基础追溯：先补 `origin_*`、`auto_resolved_gaps`、引用关系查询。
2. 严格绑定：后续再补 `skill_version_ref` 或等价快照机制。

### 9.1 当前开发进度（截至 2026-06-27）

已完成：

1. `Phase 2` 主链路可用：
  - `resolve_agent_workshop_blocking_gaps` 已实现真实 `user_id` 透传与结构化返回。
  - 支持补齐后自动续建（能力重检 -> gap 重算 -> tooling_plan -> build_version）。
2. `Phase 2.5` 去重前置：
  - 已实现高相似度复用、边界相似度确认分流，避免明显重复 Skill 生成。
3. `Phase 3` 协议层与执行层均已落地：
  - 控制面工具已就位：`start / inspect / cancel / retry`。
  - worker 可消费 `agent_workshop_gap_resolution_jobs` 并推进状态机（pending -> running -> completed/failed/timeout）。
  - `ThreadWorker` 已接入周期轮询消费。
4. `Phase 3` 并发安全与失败治理已补：
  - 增加 job claim 租约（owner/token/expires_at），防止多 worker 重复消费。
  - 增加自动重试策略（指数退避 + 上限控制 + `next_retry_at`）。
  - 超过上限进入 dead-letter，保留原因与失败上下文。

已验证：

1. 相关单测已覆盖并通过：
  - worker 消费与状态推进。
  - claim 冲突跳过。
  - start -> worker -> inspect 的端到端闭环。
  - 自动重试退避与 dead-letter 收敛。
2. 最近一轮聚焦回归结果：`13 passed, 49 deselected`。

当前仍在推进：

1. 继续观察 Phase 4/5 在真实 Agent Studio 创建链路中的端到端表现。
2. 后续如需要“严格冻结绑定”，再补 `skill_version_ref` 或等价快照机制。

### 9.2 Phase 4/5 推进记录（2026-06-27）

已完成：

1. Skill 工坊治理化基础改造：
   - `SkillGeneration.vue` 页面定位从“AI Skill 工坊”调整为“Skill 能力中心”。
   - 主按钮文案调整为“手动创建 Skill”，弱化创建入口、强化资产管理心智。
   - 列表增加来源筛选：全部来源 / Agent Studio 自动补齐 / 手动或其它创建。
   - 列表增加“来源”列，展示 `origin_source`、来源 Agent、来源 gap。
   - 列表增加“使用关系”列，展示当前 Skill 被哪些 Agent 版本使用。
   - 沟通记录弹窗补充治理与追溯信息。
2. 后端追溯字段与查询能力补齐：
   - `SkillGenerationService.list_skills()` 支持 `source` 查询参数。
   - `SkillGenerationService` 为 Skill 列表和详情补充 `used_by_agents` 反查结果。
   - `skill_generation` 路由透传 `source` 筛选参数。
3. AgentVersion 自动补齐 Skill 记录：
   - `AgentWorkshopService.build_version()` 会收集当前 session 已完成的 gap resolution job。
   - 自动补齐/复用的 `skill_tool_id` 会加入 `required_tools`。
   - 自动补齐明细写入 `agent_metadata.auto_resolved_gaps`、`evaluation_policy.auto_resolved_gaps`、`tooling_contract.auto_resolved_gaps`。
4. Agent Studio 追溯展示：
   - Agent 版本详情的“绑定工具”区块展示“自动补齐 Skill”。
   - 支持从 Agent Studio 跳转到 Skill 能力中心，并通过 `skill_id` 高亮对应 Skill。
5. dead-letter 管理产品化：
   - `AgentWorkshopService` 新增 gap resolution dead-letter 查询能力，返回失败项列表、job 汇总和按 `reason_code` 分组统计。
   - `agent_workshop` 路由新增 `GET /api/agent-workshop/gap-resolution/dead-letters`。
   - `agent_workshop` 路由新增 `POST /api/agent-workshop/gap-resolution/dead-letters/recover`，支持按 job、session、gap_ids、reason_code 或全部匹配项批量恢复。
   - `AgentStudio.vue` 右侧栏增加“补齐异常”告警入口，展示失败原因分组、最近失败项、单项重试、同类恢复和批量恢复。
   - `frontend/src/api/agentWorkshop.ts` 补齐 dead-letter 相关类型与 API 封装。

已验证：

1. 前端类型检查通过：`npm run type-check`。
2. 后端改动文件语法校验通过：`python -m py_compile app/services/agent_workshop_service.py app/services/skill_generation_service.py app/routers/skill_generation.py`。
3. dead-letter 后端新增改动语法校验通过：`python -m py_compile app/services/agent_workshop_service.py app/routers/agent_workshop.py`。

待处理：

1. `tests/core/tools/implementations/test_nanobot_agent_builder_tools.py` 全量回归当前仍有 4 个历史失败，失败点集中在旧的 spec_id 断言、线程模板默认 agent_type、迭代前置评估拦截等，与本次 Phase 4/5 展示和追溯字段改造无直接关系。
2. dead-letter 恢复后仍依赖后台 worker 继续消费 `pending` gap，生产环境需要确认 worker 常驻与告警通知策略。

本阶段验收：

1. 可以从 AgentVersion 追溯到自动补齐生成的 Skill。
2. 可以从 Skill 追溯到来源 Agent / Session / Gap。
3. 文档、前端和后端都不再把“tool_id 绑定”误表述为“已冻结快照”。

---

## 10. 验收标准

### 10.1 Agent Studio 自动补 Skill

1. 用户在 Agent Studio 创建需要新能力的 Agent。
2. 系统能通过缺口分析识别 blocking gap。
3. 系统能向用户解释缺口并请求确认。
4. 用户确认后，系统能创建 Skill 生成任务。
5. 前端能展示生成进度。
6. 生成成功后，新 Skill 出现在 Skill 工坊。
7. 新 Skill 能被 `search_project_capabilities` 搜索到。
8. Agent 版本构建时能绑定新 Skill。
9. Agent 版本详情能看到自动补齐记录。

### 10.2 Skill 工坊治理化

1. Skill 列表能区分来源。
2. 自动补齐生成的 Skill 有来源标识。
3. 能查看 Skill 生成会话或历史。
4. 能测试、禁用、启用、优化、删除 Skill。
5. 能看到 Skill 被哪些 Agent 使用。

### 10.3 用户体验

1. 用户不需要离开 Agent Studio 即可完成缺口补齐。
2. 长任务有可见进度，不是单纯卡住。
3. 失败有明确原因和重试入口。
4. 生成完成后有明确下一步：测试、继续优化、发布。

---

## 11. 关键风险与控制

### 11.1 生成时间过长

控制：

1. 默认异步化。
2. 展示阶段进度。
3. 支持稍后查看。
4. 支持取消。

### 11.2 自动生成错误 Skill

控制：

1. 新增能力必须用户确认。
2. 预览 SkillSpec。
3. 强制走验证和评分。
4. 失败不自动绑定到 Agent。

### 11.3 工具数量过多导致 Nanobot 上下文变重

控制：

1. 不拆大量底层管线组件给 Nanobot。
2. 只暴露少量高层编排工具。
3. 由 SkillGenerationService 内部封装复杂流程。

### 11.4 Skill 被创建但 Agent 没绑定

控制：

1. 补齐完成后强制重新 `search_project_capabilities`。
2. `build_agent_workshop_version` 优先考虑刚生成的 `skill_tool_id`。
3. 在 Version metadata 记录绑定结果。

### 11.5 Skill 工坊和 Agent Studio 数据不一致

控制：

1. Skill 统一写入 `external_skills`。
2. 统一热注册到 `ToolRegistry`。
3. 统一同步到 `CapabilityIndexService`。
4. Agent/Skill 双向记录来源关系。

---

## 12. 最终结论

产品上，最顺的路径是：

```text
用户只管创建 Agent。
系统发现缺 Skill，就在 Agent Studio 内解释、确认、补齐。
Skill 工坊负责管理生成出来的能力资产。
```

技术上，最稳的路径是：

```text
Nanobot 负责交互和编排。
SkillGenerationService 负责正式 Skill 生成、验证、评分、入库和注册。
AgentWorkshopService 负责 Agent 版本构建、测试、发布和治理。
```

不建议让用户手动在两个工坊之间来回切换；也不建议让 Nanobot 绕过 SkillGenerationService 直接写正式 Skill。

推荐先增强现有阻塞式补齐工具，再演进为异步 Gap Resolution Job，最后把 Skill 工坊改造成完整的能力资产中心。
