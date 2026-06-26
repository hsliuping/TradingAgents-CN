# Agent Studio & Nanobot 改进方案

> 版本：v1 | 日期：2026-06-26 | 状态：全部实施完成

## 背景

在对 `Agent Studio` 前端 (`AgentStudio.vue`)、Nanobot 运行时 (`runtime.py`)、系统提示词 (`context.py`) 和 SKILL 定义 (`skills/nanobot-agent-design/SKILL.md`) 进行了全面审查后，发现以下问题与改善空间。

---

## 一、缺陷修复（4 项）

### 1. `governance` 状态定义了但从未被使用

**现状：**
- `WorkspacePhase` 类型（`AgentStudio.vue#L864`）包含 `'governance'`
- `workspacePhase` 计算逻辑中从不返回该值
- `workspacePhaseMeta` 的 switch 缺少 `case 'governance'`

**SKILL.md 定义：**
`governance` 对应 "已写入 Workshop Draft/Version，正在进行 gap 分析、工具规划、版本构建" 阶段。允许的操作：
- `create_or_update_agent_workshop_draft`
- `analyze_agent_workshop_gaps`
- `generate_agent_workshop_tooling_plan`
- `build_agent_workshop_version`

**修复方案：**
在 `workspacePhase` 中增加 `governance` 判断条件：
- 当 `latestVersion` 的 status 是 `draft` 时返回 `governance`
- 当存在 gap_report 或 tooling_plan 但还没有版本时返回 `governance`
- 在 `workspacePhaseMeta` 中补充对应的 UI 描述

### 2. `context.py` 工作流程和 SKILL.md 的 8 状态不对齐

**现状：**
`context.py` 的 `_get_identity` 中只有 5 步流程：
> 需求采集 → 方案确认 → 生成 → 测试 → 发布

**SKILL.md 定义（8 状态）：**
> requirement-intake → confirmation → generation → **governance** → testing → **evaluation** → publish-ready → published

缺少 `governance`（版本构建与治理）和 `evaluation`（评估判定）两个关键中间态。

**修复方案：**
将 `_get_identity` 中的 5 步流程扩展为与 SKILL.md 一致的 8 步，详细说明每个阶段的含义和转换条件。

### 3. 修改已有 Agent 的流程没有独立定义

**现状：**
- `context.py` 的工作流程描述偏向"新建 Agent"
- 对"修改已有 Agent"场景缺少专门的行为指引
- SKILL.md 虽有 `iterate_agent_workshop_version` 规则，但系统提示词未体现

**修复方案：**
在 `_get_identity` 中增加"修改已有 Agent"的专门流程描述：
- 先 inspect 当前资产状态
- 不允许原地修改已发布版本
- 使用 `iterate_agent_workshop_version` 创建下一轮迭代

### 4. `evaluation` 不通过后缺少回到 `governance` 的路径

**现状：**
- `workspacePhase` 中 `evaluation` 状态是单向的，没有条件能退出回修正循环
- SKILL.md 定义了 `evaluation → governance`（评估不通过时回治理迭代）

**修复方案：**
`evaluation` 的 `workspacePhaseMeta` 中明确指引用户回到 `governance` 进行迭代修改。

---

## 二、新特性利用（3 项）

### 5. External Skills 创建流程

**现状：**
运行时已注册 5 个 External Skill 创建工具：
- `start_external_skill_generation_session`
- `respond_to_external_skill_generation_session`
- `preview_external_skill_spec`
- `generate_confirmed_external_skill`
- `inspect_external_skill_generation_session`

但 SKILL.md 没有定义触发条件和流程，`context.py` 也没有提到。

**改善方案：**
1. 在 `context.py` 能力描述中增加"创建可复用的 External Skill"
2. 在 SKILL.md 中补充 External Skill 创建的触发条件和流程
3. 当 Agent 创建过程中发现可复用能力缺口时，引导 nanobot 触发 Skill 创建而非写临时脚本

### 6. Callable Agent 前端可见性

**现状：**
- 运行时能智能路由到 callable agent
- 前端传入 skill_names 和 thread_context 但用户看不到
- 已发布的 Agent 在哪里、能否被复用，用户感知不到

**改善方案：**
1. 左侧面板增加"可用 Agent"列表，展示已发布的 callable agent
2. 对话中当 nanobot 调用 callable agent 时显示"正在调用 xxx"
3. 点击已发布 Agent 可查看其配置快照

### 7. 项目记忆和教训的 UI 透明化

**现状：**
- 运行时每次注入 `project_memory_guidance` 和 `agent_builder_lesson_guidance`
- 但用户完全看不到这些约束和参考

**改善方案：**
1. 在右侧面板或对话中展示"当前应用的治理规则"
2. 评估不通过时展示"历史类似问题及解决方式"
3. 提升用户对 nanobot 决策过程的可理解性

---

## 三、实施顺序

| 优先级 | 项目 | 涉及文件 | 复杂度 |
|--------|------|----------|--------|
| P0 | ① governance 状态补全 | AgentStudio.vue | 低 |
| P0 | ② context.py 流程对齐 | context.py | 低 |
| P0 | ③ 修改 Agent 流程说明 | context.py | 低 |
| P0 | ④ evaluation 循环路径 | AgentStudio.vue | 低 |
| P1 | ⑤ External Skills 流程 | context.py + SKILL.md | 中 |
| P2 | ⑥ Callable Agent 可见性 | AgentStudio.vue | 中 |
| P2 | ⑦ 项目记忆 UI 透明化 | AgentStudio.vue | 中 |

---

## 四、受影响文件清单

| 文件 | 改动类型 |
|------|----------|
| `core/embedded_nanobot/agent/context.py` | 修改 `_get_identity` |
| `skills/nanobot-agent-design/SKILL.md` | 补充 External Skills 流程 |
| `frontend/src/views/workflow/AgentStudio.vue` | 补 governance 状态、evaluation 路径、Callable Agent 列表、项目记忆展示 |
