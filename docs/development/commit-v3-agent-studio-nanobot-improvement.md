# Commit: Agent Studio & Nanobot 工作流改进

> 日期：2026-06-26
> 分支：integration/v3-sync-20260507
> 类型：feat / fix

---

## 改动概要

对 Agent Studio 前端界面和 Nanobot 后端提示词进行了一轮完整审查和改进：
- 修复 4 个状态机缺陷
- 补全 External Skills 创建流程定义
- 新增 Callable Agent 和治理参考的 UI 可视化

---

## 提交命令

```bash
# 第一步：添加所有改动文件
git add core/embedded_nanobot/agent/context.py
git add frontend/src/views/Workflow/AgentStudio.vue
git add skills/nanobot-agent-design/SKILL.md
git add docs/development/agent-studio-nanobot-improvement-plan.md

# 第二步：提交
git commit -m "$(cat <<'EOF'
feat: Agent Studio 状态机完善、Nanobot 工作流对齐与新特性 UI 化

- 补全 `governance` 状态定义与判断逻辑，修复 WorkspacePhase 类型缺失
- 将 context.py 5 步流程扩展为与 SKILL.md 一致的 8 阶段状态机
- 新增"修改已有 Agent"独立工作流程描述
- 修复 evaluation 不通过后缺少回到 governance 迭代路径的问题
- 在 SKILL.md 中补全 External Skills 创建流程（触发条件、工具链、8 步流程）
- 右侧面板新增"可调用 Agent"区域，展示已发布版本
- 右侧面板新增"治理参考"区域，展示 blockers/warnings/阶段提示
EOF
)"
```

---

## 文件变更清单

### 修改的文件

| 文件 | 行变更 | 说明 |
|------|--------|------|
| `core/embedded_nanobot/agent/context.py` | +60 / -12 | 工作流程从 5 步扩展为 8 阶段；新增"修改已有 Agent"章节；能力描述中提示 External Skill 创建 |
| `frontend/src/views/Workflow/AgentStudio.vue` | +245 / ~4000 | governance 状态补全；evaluation 导向改进；新增 callableAgents / governanceReferences 计算属性及模板、样式 |
| `skills/nanobot-agent-design/SKILL.md` | +41 / 0 | 新增 "External Skills Creation Workflow" 完整章节 |

### 新增的文件

| 文件 | 说明 |
|------|------|
| `docs/development/agent-studio-nanobot-improvement-plan.md` | 改进方案文档，记录全部 7 项问题分析与实施方案 |

---

## 改动详情

### 1. `core/embedded_nanobot/agent/context.py` — 系统提示词重建

**之前：** 5 步简化流程（需求采集→方案确认→生成→测试→发布）

**之后：** 与 SKILL.md 完全对齐的 8 阶段流程：
1. 需求采集（requirement-intake）
2. 方案确认（confirmation）
3. 生成（generation）
4. 资产治理（governance）
5. 测试（testing）
6. 评估（evaluation）— 不通过时回到 governance
7. 待发布（publish-ready）— 需手动确认
8. 已发布（published）— 禁止原地修改

每阶段附有对应的工具名称和转换条件。

**新增：**"修改已有 Agent 的工作流程"独立章节，明确核查→迭代→治理→测试→评估→发布的路径。

### 2. `frontend/src/views/Workflow/AgentStudio.vue` — 前端状态机与 UI 增强

**governance 状态补全：**
- `WorkspacePhase` 类型显式加入 `'governance'`
- 判断条件：`latestVersion.status === 'draft'` 或 `gap_report`/`tooling_plan` 存在
- `workspacePhaseMeta` 新增 `case 'governance'` 分支

**evaluation 路径修复：**
- `evaluation` 状态根据 `latestEvaluation.decision` 分两路：
  - `pass` → 提示发布
  - 其他 → 引导回治理阶段迭代

**Callable Agent 可见性：**
- 右侧面板 "高级配置" 和 "后台轨迹" 之间新增 "可调用 Agent" 列表区域
- `callableAgents` 计算属性过滤 `status === 'active'` 的已发布版本

**治理参考 UI：**
- 右侧面板新增 "治理参考" 区域
- `governanceReferences` 计算属性实时展示当前版本评估的 blockers（红色）和 warnings（橙色）
- governance 阶段无评估时显示阶段提示（蓝色）

### 3. `skills/nanobot-agent-design/SKILL.md` — External Skills 流程定义

在 `Reusable Capability Promotion Rule` 章节后新增 **External Skills Creation Workflow** 章节：
- **触发条件**：能力不存在 + 可复用 + 用户同意
- **工具清单**：5 个专用工具及用途
- **8 步工作流**：识别缺口→提议 Skill→确认→启动 session→迭代→预览→生成→返回 Agent 设计
- **与 Agent 创建的关系**：可并行或作为前置，不阻塞 Agent 创建

### 4. `docs/development/agent-studio-nanobot-improvement-plan.md` — 改进文档

完整的改进方案文档，包含：
- 背景说明
- 4 个缺陷修复（P0）和 3 个新特性（P1/P2）
- 实施顺序与优先级
- 受影响文件清单

---

## 未关联的历史改动

以下文件出现在 `git status` 中但非本次会话产生，请自行评估是否需要一并提交：

| 文件 | 说明 |
|------|------|
| `core/tools/implementations/agent_builder/nanobot_agent_builder_tools.py` | 之前已存在的本地修改 |
| `docs/development/agent-studio-redesign-mockup.html` | 上一轮 UI 原型页 |

---

## 审阅要点

1. `context.py` 的提示词内容是否需要进一步精简（当前约 60 行）
2. `AgentStudio.vue` 中 governance 判断条件是否与后端 session 数据对齐
3. SKILL.md 中 External Skills 流程的工具调用参数是否与实际一致
4. Callable Agent 列表只做展示，没有绑定点击后的交互
