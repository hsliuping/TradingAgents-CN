# TradingAgents-CN v3.0 — AI 智能工作流架构师设计文档

## 📋 文档信息

| 项目 | 内容 |
|------|------|
| 版本 | v2.0（完整版） |
| 状态 | 设计完成，待确认 |
| 日期 | 2026-02-23 |
| 作者 | TradingAgents-CN Pro Team |
| 前置文档 | [v3.0 Skill 生成系统](skill-generation-system.md)、[v3.0 分层提示词架构](prompt-layered-architecture.md) |

---

## 1. 概述

### 1.1 背景

TradingAgents-CN Pro 已实现自定义工作流编辑器，用户可以手动拖拽节点、连线来构建分析流程。但这要求用户：

- 了解系统中有哪些 Agent（33+）及其能力
- 理解节点类型（start, end, analyst, parallel, merge, debate 等）的含义
- 手动设计流程拓扑结构
- 了解哪些工具/Skill 可用
- 手动配置提示词模板

对于大多数用户来说，这个门槛过高。v1.0 基础版只解决了"生成工作流结构"这一步，而一个**真正可用的工作流**还需要：

1. **Agent 能力适配** — 现有 Agent 的默认能力不一定完全匹配用户场景
2. **工具/Skill 补全** — 用户场景可能需要系统中尚不存在的工具
3. **提示词定制** — 每个 Agent 在该工作流中的分析角度需要定制
4. **持续优化** — 首次生成的方案不一定完美，需要迭代改进

### 1.2 目标

构建一套 **AI 工作流架构师**，实现从需求到可执行工作流的**全链路自动化**：

```
用户自然语言 → 需求理解 → 资源缺口分析 → 自动补全 → 工作流创建 → 迭代优化
                  ↑                                                    ↓
                  └────────────── 用户反馈循环 ─────────────────────────┘
```

**六大能力**：

| # | 能力 | 说明 |
|---|------|------|
| 1 | **需求理解** | 多轮对话理解用户意图，自动拆解分析维度 |
| 2 | **资源缺口分析** | 自动检测需要但缺失的 Agent 能力、工具、Skill |
| 3 | **Agent 能力重塑** | 通过生成工作流专属提示词，让现有 Agent 适配新场景 |
| 4 | **Skill 自动创建** | 自动调用 SkillGenerator 管线创建缺失的工具 |
| 5 | **一键创建** | 同时生成 WorkflowDefinition + 专属提示词 + 工具绑定 |
| 6 | **迭代优化** | 工作流执行后，根据反馈持续改进结构和提示词 |

### 1.3 核心创新点

#### 🧠 Agent 能力重塑（而非创建新 Agent）

系统已支持 **workflow-specific prompt templates**（`prompt_templates` 集合的 `workflow_id` 字段）。这意味着同一个 `market_analyst` 在不同工作流中可以有**完全不同的分析行为**。

```
例子：用户需要"可转债分析流程"
├── 系统没有 "convertible_bond_analyst" → 不需要创建新 Agent
├── AI 选择 market_analyst + fundamentals_analyst
├── 为 market_analyst 生成工作流专属提示词：
│   system_prompt: "你是一个可转债市场分析师，重点关注转股价值、转股溢价率..."
│   tool_guidance: "使用市场数据工具获取可转债的价格和成交量..."
│   analysis_requirements: "1. 转股价值分析 2. 溢价率变化 3. 正股走势关联..."
└── 这样 market_analyst 在此工作流中就变成了"可转债市场分析师"
```

#### 🔧 Skill 自动补全

复用已有的 SkillGenerator 管线：

```
AI 分析缺口 → 调用 SkillGenerator.start_session()
           → 自动确认 spec → 自动生成代码
           → 验证通过 → 绑定到工作流中的 Agent
```

#### 🔄 闭环迭代优化

```
创建工作流 → 用户运行 → 查看结果 → 提出改进意见
    ↑                                    ↓
    └── AI 调整（结构/提示词/工具绑定） ←──┘
```

#### 🏗️ 三层配置模型（节点级工具与提示词精准覆盖）

工具绑定和提示词模板均支持**三层优先级**，实现从粗粒度到精细粒度的按需覆盖：

```
Layer 1: Agent 定义层（agent_configs — 保底默认值）
              ↓ 可被覆盖（workflow_id 维度）
Layer 2: Workflow 层（工作流专属配置）
              ↓ 可被覆盖（workflow_id + node_id 维度）
Layer 3: Node 层（节点专属配置，最高优先级）
```

**解决的核心问题**：当同一个 `market_analyst` 在工作流中出现多次（如「可转债价格分析节点」和「可转债流动性分析节点」），两个节点可以拥有完全不同的工具集和提示词——通过 `workflow_id + node_id` 精确区分，而不是粗粒度的「同一 Agent 同一配置」。

**数据库实现**（`tool_agent_bindings` 集合）：

```json
// 节点级绑定（最高优先级）
{ "agent_id": "market_analyst", "workflow_id": "cb_flow", "node_id": "price_node", "tool_id": "get_cb_price" }

// 工作流级绑定
{ "agent_id": "market_analyst", "workflow_id": "cb_flow", "node_id": null, "tool_id": "get_market_data" }

// Agent 默认绑定（保底）
{ "agent_id": "market_analyst", "workflow_id": null, "node_id": null, "tool_id": "get_stock_market_data_unified" }
```

提示词模板（`prompt_templates` 集合）通过 `workflow_id + node_id + agent_id` 三元组同样实现三层优先级查询。

#### 🤖 UniversalAgent — 数据库驱动的通用 Agent

AI 工作流架构师可以**创建真正全新的 Agent 角色**（不只是给现有 Agent 换提示词），且无需编写任何 Python 代码：

```
用户："帮我创建可转债分析流程"
AI  ："检测到需要「可转债条款分析师」，将创建全新 Agent 定义..."
      → 写入 agent_configs（agent_id, agent_name, output_field, description）
      → 为该节点生成专属提示词（prompt_templates，带 workflow_id + node_id）
      → 运行时 AgentFactory 检测该 agent_id 不在代码注册表
      → 从 agent_configs 加载配置 → 创建 UniversalAgent 实例 → 正常执行
```

`UniversalAgent` 是完全由数据库配置驱动的通用 Agent 类，零硬编码业务逻辑，通过三层优先级动态加载工具和提示词，可替代 80-95% 的专有 Agent 类。

### 1.4 与现有系统的集成

| 现有系统 | 集成方式 |
|---------|---------|
| `WorkflowDefinition` | AI 生成的方案转换为标准 WorkflowDefinition |
| `WorkflowAPI.create()` | 复用现有接口保存到 MongoDB |
| `WorkflowValidator` | 创建前校验工作流结构合法性 |
| `BUILTIN_AGENTS` (33+) | 作为可选资源，AI 可"重塑"其能力 |
| `BUILTIN_TOOLS` (100+) | 作为可选资源 |
| `external_skills` | 作为可选资源 + AI 可自动创建新 Skill |
| `prompt_templates` (workflow_id) | AI 自动生成工作流专属提示词 |
| `tool_agent_bindings` | AI 可为工作流中的 Agent 绑定新工具 |
| `SkillGenerator` 管线 | 复用完整的 Skill 生成能力 |
| 工作流编辑器 | 创建后跳转到编辑器，用户可进一步微调 |

### 1.5 与 Skill 生成系统的对比

| 维度 | Skill 生成 | 工作流架构师 |
|------|-----------|------------|
| **输入** | 单个工具需求 | 完整分析流程需求 |
| **AI 输出** | Python 代码 + 元数据 | 工作流结构 + 提示词 + 工具绑定 |
| **验证方式** | 静态分析 + 沙箱 + Judge | 结构校验 + 用户确认 |
| **迭代方式** | 3 轮自动修复 | 多轮用户反馈优化 |
| **产出物** | 1 个 Skill | 1 个工作流 + N 个提示词 + M 个 Skill |
| **关系** | 独立模块 | **内部可调用 Skill 生成** |

---

## 2. 系统架构总览

### 2.1 完整管线（6 阶段）

```text
用户点击"AI 智能创建"
    │
    ▼
┌──────────────────────────────────────────────────────────────────┐
│  阶段 1: 资源收集（ResourceCollector）                              │
│  ├── 从 BUILTIN_AGENTS 收集所有 Agent（33+）                       │
│  ├── 从 BUILTIN_TOOLS 收集所有工具（100+）                          │
│  ├── 从 MongoDB external_skills 收集外部 Skill                      │
│  ├── 从 MongoDB prompt_templates 收集提示词模板信息                   │
│  └── 汇总为 LLM 可理解的上下文文本（~5000 tokens）                   │
├──────────────────────────────────────────────────────────────────┤
│  阶段 2: 需求沟通 + 方案设计（WorkflowPlanner，1-5 轮对话）           │
│  ├── 第 1 轮: 理解用户目标，输出方案草案（含缺口分析）                 │
│  ├── 第 2 轮: 根据用户反馈调整方案（可选）                            │
│  ├── 第 N 轮: 细节确认（可选，最多 5 轮）                            │
│  └── 输出: WorkflowBlueprint                                      │
│       ├── 工作流结构（nodes + edges）                               │
│       ├── 缺口分析报告（Agent 能力缺口 + 工具缺口）                   │
│       ├── 提示词生成计划（每个 Agent 的专属提示词草案）                 │
│       └── Skill 创建请求列表（需要新建的工具）                        │
├──────────────────────────────────────────────────────────────────┤
│  阶段 3: 方案确认                                                  │
│  ├── 展示方案摘要 + 缺口分析 + 预计创建内容                          │
│  └── 用户选择: "确认创建" / "继续修改" / "取消"                      │
├──────────────────────────────────────────────────────────────────┤
│  阶段 4: 自动补全（SkillOrchestrator + PromptGenerator）            │
│  ├── 4a. Skill 自动创建 — 调用 SkillGenerator 管线                  │
│  │   ├── 自动生成 SkillSpec → 代码生成 → 验证 → 注册                 │
│  │   └── 将新 Skill 绑定到对应 Agent                                │
│  ├── 4b. 提示词自动生成 — 为每个 Agent 生成工作流专属提示词            │
│  │   ├── system_prompt / tool_guidance / analysis_requirements      │
│  │   └── 保存到 prompt_templates（带 workflow_id）                   │
│  └── 4c. 工具绑定 — 为 Agent 绑定新创建的 Skill + 选定的内置工具      │
├──────────────────────────────────────────────────────────────────┤
│  阶段 5: 工作流创建                                                │
│  ├── WorkflowBlueprint → WorkflowDefinition（nodes + edges）       │
│  ├── WorkflowValidator 校验结构合法性                               │
│  ├── 调用 WorkflowAPI.create() 保存到 MongoDB                       │
│  └── 返回 workflow_id，前端跳转到编辑器                              │
├──────────────────────────────────────────────────────────────────┤
│  阶段 6: 迭代优化（运行后反馈）                                      │
│  ├── 用户运行工作流 → 查看分析结果                                   │
│  ├── 用户提出改进意见（如"市场分析不够深入"、"缺少资金面分析"）         │
│  ├── AI 分析反馈 → 调整工作流结构 / 提示词 / 工具绑定                 │
│  └── 循环：修改 → 运行 → 反馈 → 优化                                │
└──────────────────────────────────────────────────────────────────┘
```

### 2.2 模块架构图

```text
┌──────────────────────────────────────────────────────────────────┐
│                        前端 (Vue 3)                               │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Workflow/index.vue                                        │  │
│  │  ├── "AI 智能创建" 按钮                                     │  │
│  │  ├── AI 对话窗口（全屏对话式 UI）                            │  │
│  │  ├── 方案预览（缺口分析 + 结构预览 + 资源清单）               │  │
│  │  └── 创建进度（Skill 生成进度 + 提示词生成进度）              │  │
│  └────────────────────────────────────────────────────────────┘  │
│                          │ HTTP                                   │
├──────────────────────────┼────────────────────────────────────────┤
│                     后端 (FastAPI)                                 │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  app/routers/workflow_generation.py                         │  │
│  │  ├── POST /sessions/start               开始会话            │  │
│  │  ├── POST /sessions/{id}/respond        继续对话            │  │
│  │  ├── POST /sessions/{id}/confirm        确认创建            │  │
│  │  ├── POST /sessions/{id}/optimize       迭代优化            │  │
│  │  ├── GET  /sessions/{id}                获取会话            │  │
│  │  ├── GET  /sessions/{id}/progress       获取创建进度        │  │
│  │  ├── GET  /sessions                     列出会话            │  │
│  │  └── DELETE /sessions/{id}              删除会话            │  │
│  └──────────────────────┬─────────────────────────────────────┘  │
│                          │                                        │
│  ┌──────────────────────┴─────────────────────────────────────┐  │
│  │  app/services/workflow_generation_service.py                │  │
│  │  ├── start_session()          开始 + 资源收集 + 首轮对话     │  │
│  │  ├── respond()                继续对话                      │  │
│  │  ├── confirm_and_create()     确认 → 补全 → 创建            │  │
│  │  ├── optimize()               迭代优化                      │  │
│  │  ├── get_session() / list_sessions() / delete_session()     │  │
│  │  └── get_creation_progress()  创建进度查询                   │  │
│  └──────────────────────┬─────────────────────────────────────┘  │
│                          │                                        │
├──────────────────────────┼────────────────────────────────────────┤
│                     核心层 (core/)                                 │
│  ┌──────────────────────┴─────────────────────────────────────┐  │
│  │  core/workflow/generator/                                   │  │
│  │  ├── workflow_spec.py          数据模型（含缺口分析结构）     │  │
│  │  ├── resource_collector.py     资源收集 + 上下文压缩         │  │
│  │  ├── workflow_planner.py       LLM 规划器（对话 + 方案生成）  │  │
│  │  ├── prompt_generator.py       提示词自动生成器 [NEW]        │  │
│  │  └── skill_orchestrator.py     Skill 编排器 [NEW]           │  │
│  └────────────────────────────────────────────────────────────┘  │
│                          │                                        │
│  ┌──────────────────────┴─────────────────────────────────────┐  │
│  │  复用的现有模块                                              │  │
│  │  ├── core/llm/UnifiedLLMClient         LLM 调用             │  │
│  │  ├── core/agents/config                BUILTIN_AGENTS       │  │
│  │  ├── core/tools/config                 BUILTIN_TOOLS        │  │
│  │  ├── core/tools/external/              SkillGenerator 管线   │  │
│  │  ├── core/workflow/models              WorkflowDefinition   │  │
│  │  ├── core/workflow/validator           WorkflowValidator    │  │
│  │  ├── core/api/workflow_api             WorkflowAPI          │  │
│  │  ├── app/services/skill_generation_service  Skill 生成服务   │  │
│  │  └── app/services/prompt_template_service   提示词模板服务   │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 3. 数据模型设计

### 3.1 文件位置

`core/workflow/generator/workflow_spec.py`

### 3.2 会话状态枚举

```python
class GenerationSessionStatus(str, Enum):
    GATHERING = "gathering"           # 收集需求中（对话进行中）
    PLANNING = "planning"             # AI 正在规划（生成蓝图中）
    BLUEPRINT_READY = "blueprint_ready"  # 蓝图已生成，等待用户确认
    CONFIRMED = "confirmed"           # 用户已确认
    COMPLETING = "completing"         # 自动补全中（创建 Skill + 生成提示词）
    CREATING = "creating"             # 正在创建工作流
    COMPLETED = "completed"           # 创建完成
    OPTIMIZING = "optimizing"         # 迭代优化中
    FAILED = "failed"                 # 失败
```

### 3.3 对话轮次

```python
class ConversationRound(BaseModel):
    round_num: int = 0
    user_message: str = ""
    ai_message: str = ""
    phase: str = "gathering"       # gathering / optimizing（区分创建和优化阶段）
    timestamp: datetime
```

### 3.4 规划节点

```python
class PlannedNode(BaseModel):
    id: str                                # 节点唯一 ID
    type: str                              # start, end, analyst, researcher, trader, risk, manager, parallel, merge, debate, post_processor, condition
    agent_id: Optional[str] = None         # 关联的 Agent ID（来自 BUILTIN_AGENTS）
    label: str = ""                        # 显示标签
    position_x: float = 0                  # 前端渲染位置 X
    position_y: float = 0                  # 前端渲染位置 Y
    config: Dict[str, Any] = {}            # 节点配置
    description: str = ""                  # AI 对该节点的说明（展示给用户）
```

### 3.5 规划边

```python
class PlannedEdge(BaseModel):
    id: str
    source: str                            # 源节点 ID
    target: str                            # 目标节点 ID
    label: Optional[str] = None
    animated: bool = False
```

### 3.6 缺口分析结果 [NEW]

```python
class GapAnalysisResult(BaseModel):
    """缺口分析结果 — AI 自动检测后生成"""

    # Agent 能力缺口（不需要创建新 Agent，通过提示词重塑解决）
    agent_reshaping: List[AgentReshapingPlan] = []

    # 工具/Skill 缺口（需要自动创建新 Skill）
    missing_skills: List[SkillCreationRequest] = []

    # 现有资源可直接使用的
    available_agents: List[Dict[str, str]] = []   # [{id, name, role_in_workflow}]
    available_tools: List[Dict[str, str]] = []    # [{id, name, used_by_agent}]

    # 分析说明
    analysis_summary: str = ""


class AgentReshapingPlan(BaseModel):
    """Agent 能力重塑计划"""
    agent_id: str                      # 选用的现有 Agent（如 market_analyst）
    node_id: str = ""                  # 🆕 对应工作流中的节点 ID（用于三层配置模型的 Node 层）
    original_role: str                 # 原始角色描述
    new_role: str                      # 在本工作流中的新角色（如"可转债市场分析师"）
    prompt_changes: Dict[str, str] = {}  # 需要定制的提示词字段 {system_prompt, tool_guidance, ...}
    additional_tools: List[str] = []   # 需要额外绑定的工具 ID（将创建节点级绑定）


class SkillCreationRequest(BaseModel):
    """Skill 自动创建请求"""
    skill_name: str                    # 期望的 Skill 名称
    skill_description: str             # 功能描述
    target_agent_id: str               # 要绑定到哪个 Agent
    priority: str = "required"         # required / optional
    generated_skill_id: Optional[str] = None  # 创建成功后回填
    status: str = "pending"            # pending / creating / completed / failed
```

### 3.7 工作流蓝图 [ENHANCED]

```python
class WorkflowBlueprint(BaseModel):
    """AI 生成的工作流蓝图 — 包含结构 + 缺口分析 + 补全计划"""

    # 基本信息
    name: str = ""
    description: str = ""
    tags: List[str] = []

    # 工作流结构
    nodes: List[PlannedNode] = []
    edges: List[PlannedEdge] = []
    config: Dict[str, Any] = {}

    # AI 方案说明
    summary: str = ""                      # 方案概述
    rationale: str = ""                    # 设计思路

    # 缺口分析
    gap_analysis: Optional[GapAnalysisResult] = None

    # 提示词生成计划
    prompt_plans: List[Dict[str, Any]] = []  # 每个 Agent 的提示词草案

    # 创建进度跟踪
    creation_progress: Dict[str, Any] = {
        "skills_total": 0,
        "skills_completed": 0,
        "prompts_total": 0,
        "prompts_completed": 0,
        "workflow_created": False,
    }
```

### 3.8 生成会话 [ENHANCED]

```python
class WorkflowGenerationSession(BaseModel):
    session_id: str
    user_id: str = ""
    status: GenerationSessionStatus = GenerationSessionStatus.GATHERING

    # 对话记录
    rounds: List[ConversationRound] = []
    current_round: int = 0

    # AI 生成的蓝图
    blueprint: Optional[WorkflowBlueprint] = None
    blueprint_confirmed: bool = False

    # 创建结果
    workflow_id: Optional[str] = None
    created_prompt_ids: List[str] = []     # 创建的提示词模板 ID
    created_skill_ids: List[str] = []      # 创建的 Skill ID
    error: Optional[str] = None

    # 优化记录
    optimize_rounds: List[ConversationRound] = []  # 优化阶段的对话记录
    optimize_count: int = 0                         # 优化次数

    # 时间
    created_at: datetime
    updated_at: datetime
```

### 3.9 MongoDB 集合

**集合名**: `workflow_generation_sessions`

```json
{
    "session_id": "uuid-string",
    "user_id": "user123",
    "status": "gathering",
    "rounds": [
        {
            "round_num": 1,
            "user_message": "帮我创建一个可转债分析流程",
            "ai_message": "好的，我为您设计了可转债分析流程...\n\n📋 **缺口分析**\n- market_analyst 将重塑为「可转债市场分析师」\n- 需要创建新 Skill「可转债溢价率计算器」\n...",
            "phase": "gathering",
            "timestamp": "2026-02-23T10:00:00Z"
        }
    ],
    "current_round": 1,
    "blueprint": {
        "name": "可转债分析流",
        "nodes": [...],
        "edges": [...],
        "gap_analysis": {
            "agent_reshaping": [
                {
                    "agent_id": "market_analyst",
                    "original_role": "市场分析师",
                    "new_role": "可转债市场分析师",
                    "prompt_changes": {"system_prompt": "你是可转债市场分析师..."},
                    "additional_tools": []
                }
            ],
            "missing_skills": [
                {
                    "skill_name": "convertible_bond_premium_calculator",
                    "skill_description": "计算可转债的溢价率、转股价值等指标",
                    "target_agent_id": "fundamentals_analyst",
                    "priority": "required",
                    "status": "pending"
                }
            ],
            "analysis_summary": "本流程需要 3 个 Agent 能力重塑 + 1 个新 Skill"
        },
        "prompt_plans": [...],
        "creation_progress": {"skills_total": 1, "skills_completed": 0, "prompts_total": 3, "prompts_completed": 0}
    },
    "blueprint_confirmed": false,
    "workflow_id": null,
    "created_prompt_ids": [],
    "created_skill_ids": [],
    "optimize_rounds": [],
    "optimize_count": 0,
    "created_at": "2026-02-23T10:00:00Z",
    "updated_at": "2026-02-23T10:00:00Z"
}
```

---

## 4. 核心模块设计

### 4.1 ResourceCollector — 资源收集器

**文件**: `core/workflow/generator/resource_collector.py`（已创建，需增强）

**职责**: 从代码配置和 MongoDB 收集所有可用资源，构建 LLM 可理解的上下文文本。

**数据来源**:

| 资源类型 | 来源 | 数量级 |
| -------- | ---- | ------ |
| 内置 Agent | `core.agents.config.BUILTIN_AGENTS` | 33+ |
| 数据库 Agent | MongoDB `agent_configs` 集合 | 0-10 |
| 内置工具 | `core.tools.config.BUILTIN_TOOLS` | 100+ |
| 外部 Skill | MongoDB `external_skills` 集合 | 0-50 |
| 提示词模板 | MongoDB `prompt_templates` 集合 | 100+ |
| 节点类型 | 硬编码列表 | 12 |

**核心方法**:

```python
class ResourceCollector:
    def __init__(self, db=None):
        self._db = db

    def collect_all(self) -> Dict[str, Any]:
        """
        收集所有可用资源

        Returns:
            {
                "agents": [{"id", "name", "description", "category", "default_tools", "source"}],
                "tools": [{"id", "name", "description", "category", "source"}],
                "external_skills": [{"id", "name", "description", "category", "source"}],
                "prompt_templates": [{"agent_type", "template_name", "has_workflow_specific"}],
                "node_types": [{"type", "description"}],
                "context_text": "..."   # 汇总的文本描述，直接嵌入 LLM System Prompt
            }
        """
```

**上下文压缩策略**:

为控制 token 消耗，资源信息做如下压缩：

- **Agent**: 只传 `id`, `name`, `description`, `category`（不传完整 tools 列表和 IO 定义）
- **工具**: 只传 `id`, `name`, `description`（不传 parameters schema）
- **外部 Skill**: 只传 `id`, `name`, `description`
- **提示词模板**: 只传摘要信息（哪些 agent 有自定义模板）
- **按 category 分组**，使 LLM 更容易理解结构
- 预计上下文 ~4000-6000 tokens

**生成的 context_text 示例**:

```markdown
## 可用的 Agent（智能体）

### analyst（分析师）
- **market_analyst** (市场分析师): 分析股票价格走势、技术指标、成交量等市场数据
  - 默认提示词: 通用股票市场分析
- **fundamentals_analyst** (基本面分析师): 分析公司财务报表、盈利能力、估值水平
- **news_analyst** (新闻分析师): 分析与股票相关的新闻事件和市场影响
- **social_media_analyst** (社交媒体分析师): 分析社交媒体上的投资者情绪
- **index_analyst** (大盘分析师): 分析大盘指数走势、市场环境、系统性风险
- **sector_analyst** (板块分析师): 分析行业趋势、板块轮动、同业对比
...

### researcher（研究员）
- **bull_researcher** (看多研究员): 从看多角度综合分析报告，寻找投资机会
- **bear_researcher** (看空研究员): 从看空角度综合分析报告，识别潜在风险
...

### manager（管理者）
- **research_manager** (研究经理): 综合看多和看空双方观点，形成最终投资建议
...

## 可用的工具（按类别）
### market_data（市场数据）
- **get_stock_market_data_unified** (统一市场数据): 获取股票行情、K线、成交量等
...

## 用户创建的 Skill
- **xxx_calculator** (某指标计算器): 计算某个特定指标
...

## 可用的工作流节点类型
- **start**: 工作流起始节点，每个工作流必须有且仅有一个
- **end**: 工作流结束节点，每个工作流必须有且仅有一个
- **analyst**: 分析师节点，执行特定分析任务，需要关联 agent_id
- **parallel**: 并行开始节点，之后的多个分支并行执行
- **merge**: 并行合并节点，等待所有并行分支完成
- **debate**: 辩论节点，多个 Agent 进行多轮辩论
- **post_processor**: 后处理节点，对分析结果进行汇总或格式化
...
```

### 4.2 WorkflowPlanner — 工作流规划器 [ENHANCED]

**文件**: `core/workflow/generator/workflow_planner.py`

**职责**: LLM 驱动的工作流规划。通过多轮对话理解需求，生成包含**结构 + 缺口分析 + 提示词评估**的完整蓝图。

**核心方法**:

```python
class WorkflowPlanner:
    def __init__(self, llm_client=None, provider="deepseek", model=None):
        ...

    def chat(
        self,
        session: WorkflowGenerationSession,
        user_message: str,
        resource_context: str,
    ) -> Tuple[WorkflowGenerationSession, str]:
        """
        处理用户消息，推进对话

        对话内容包括：
        - 工作流结构建议
        - 缺口分析（Agent 角色是否需要重塑、工具是否缺失）
        - 提示词评估（哪些 Agent 需要定制提示词）

        Returns:
            (更新后的会话, AI 回复消息)
        """

    def generate_blueprint(
        self,
        session: WorkflowGenerationSession,
        resource_context: str,
    ) -> Tuple[WorkflowGenerationSession, Optional[WorkflowBlueprint]]:
        """
        根据对话历史生成完整的 WorkflowBlueprint（含缺口分析 + 提示词评估）

        在用户确认时调用，要求 LLM 输出结构化 JSON。

        Returns:
            (更新后的会话, WorkflowBlueprint 或 None)
        """

    def generate_optimization(
        self,
        session: WorkflowGenerationSession,
        feedback: str,
        resource_context: str,
    ) -> Tuple[WorkflowGenerationSession, str]:
        """
        根据用户反馈生成优化建议（迭代优化阶段）

        Returns:
            (更新后的会话, AI 优化建议)
        """
```

**LLM Prompt 策略**:

#### System Prompt 结构（对话阶段）

```text
你是一个 AI 工作流架构师，擅长根据用户需求设计多智能体协作分析流程。

## 你的任务

根据用户需求设计完整的分析工作流方案。你需要考虑三个层面：

### 层面 1：工作流结构
设计节点（Agent）和边（连接关系），确定分析流程拓扑。

### 层面 2：Agent 能力评估与提示词定制
对于每个选用的 Agent，评估其**默认提示词**是否足以应对当前流程的需求：
- ✅ 默认足够：Agent 的通用角色与本流程需求吻合，无需定制
- ⚠️ 需要定制：Agent 在本流程中的角色偏离了其默认定位，需要生成工作流专属提示词

例如：
- "标准 A 股分析流" 中的 market_analyst → 默认提示词足够 ✅
- "可转债分析流" 中的 market_analyst → 需要定制为"可转债市场分析师" ⚠️

### 层面 3：工具/Skill 缺口
检查选用的 Agent 是否有足够的工具支持，识别缺失的工具。

## 可用资源

{resource_context}

## 工作流结构规则

1. 必须有且仅有一个 start 节点和一个 end 节点
2. 所有节点必须可达（从 start 出发能到达，且能到达 end）
3. 需要并行执行的分析师应放在 parallel 和 merge 节点之间
4. 需要辩论的角色应使用 debate 节点
5. 每个 analyst/researcher/trader/risk/manager 节点必须指定有效的 agent_id
6. agent_id 必须来自上面列出的可用 Agent
7. 节点 ID 使用小写字母+下划线，如 market_node, parallel_1
8. 节点位置按照从上到下、并行水平排列布局

## 对话规则

第一轮回复必须包含以下三部分：

📊 **方案草案** — 流程结构和步骤
📋 **提示词评估** — 哪些 Agent 用默认提示词，哪些需要定制
🔧 **工具检查** — 是否有缺失的工具需要创建

后续轮次根据用户反馈调整。不要在对话中输出 JSON。
```

#### 对话策略

| 轮次 | AI 行为 |
| ---- | ------- |
| **第 1 轮** | 理解需求 → 输出方案草案 + 提示词评估 + 工具检查 |
| **第 2+ 轮** | 根据反馈调整结构 / 提示词计划 / 工具计划 |
| **确认后** | 系统调用 `generate_blueprint()` 生成完整蓝图 JSON |
| **优化阶段** | 用户运行后反馈 → AI 建议调整方案 |

#### AI 回复示例（第 1 轮）

```text
好的，根据您的需求，我为您设计了以下可转债分析流程：

📊 **方案草案**

**阶段一：并行分析**
├── 市场分析师 → 分析可转债价格走势和交易量
├── 基本面分析师 → 分析正股基本面和转股价值
└── 新闻分析师 → 追踪可转债相关政策和事件

**阶段二：多空辩论**
└── 看多研究员 ⚔️ 看空研究员

**阶段三：综合决策**
├── 研究经理 → 综合评估
├── 交易员 → 制定可转债交易策略
└── 风险管理 → 评估转债特有风险

📋 **提示词评估**
- market_analyst: ⚠️ 需要定制 — 默认提示词面向股票市场，需重塑为「可转债市场分析师」
- fundamentals_analyst: ⚠️ 需要定制 — 需增加转股价值、溢价率等分析维度
- news_analyst: ✅ 默认足够 — 新闻分析通用性强
- bull_researcher / bear_researcher: ✅ 默认足够
- research_manager: ✅ 默认足够
- trader: ⚠️ 需要定制 — 需增加可转债特有的交易策略
- risk_manager: ⚠️ 需要定制 — 需增加转债下修、强赎等风险评估

🔧 **工具检查**
- 现有工具基本满足需求
- 建议创建: 「可转债溢价率计算器」— 计算转股溢价率、纯债溢价率等指标

确认创建还是需要调整？
```

#### Blueprint 生成 Prompt（确认后单独调用）

```text
根据以下对话历史，生成完整的工作流蓝图 JSON。

## 对话历史
{conversation_history}

## 输出要求

请严格按照以下 JSON 格式输出（不要包含其他文本）：

{
    "name": "工作流名称",
    "description": "工作流描述",
    "tags": ["标签1"],
    "nodes": [
        {"id": "start", "type": "start", "label": "开始", "position_x": 400, "position_y": 0},
        {"id": "xxx", "type": "analyst", "agent_id": "market_analyst", "label": "市场分析师", ...},
        {"id": "end", "type": "end", "label": "结束", "position_x": 400, "position_y": 800}
    ],
    "edges": [
        {"id": "e1", "source": "start", "target": "parallel_1"}, ...
    ],
    "config": {"analysis_depth": 3, "debate_rounds": "auto", ...},
    "summary": "方案概述",
    "rationale": "设计思路",

    "gap_analysis": {
        "agent_reshaping": [
            {
                "agent_id": "market_analyst",
                "original_role": "市场分析师",
                "new_role": "可转债市场分析师",
                "prompt_changes": {
                    "system_prompt": "你是一个可转债市场分析师...",
                    "tool_guidance": "使用市场数据工具获取可转债价格...",
                    "analysis_requirements": "1. 转股溢价率趋势 2. 交易量变化...",
                    "output_format": "## 可转债市场分析报告\n..."
                }
            }
        ],
        "agents_using_default": [
            {"agent_id": "news_analyst", "reason": "新闻分析通用性强，默认提示词足够"}
        ],
        "missing_skills": [
            {
                "skill_name": "convertible_bond_premium_calculator",
                "skill_description": "计算可转债的转股溢价率、纯债溢价率",
                "target_agent_id": "fundamentals_analyst",
                "priority": "required"
            }
        ],
        "analysis_summary": "4 个 Agent 需要定制提示词，3 个使用默认，需创建 1 个新 Skill"
    }
}
```

### 4.3 PromptGenerator — 提示词生成器 [NEW]

**文件**: `core/workflow/generator/prompt_generator.py`

**职责**: 根据蓝图中的提示词评估结果，为需要定制的 Agent 生成工作流专属提示词模板，保存到 `prompt_templates` 集合。

```python
class PromptGenerator:
    def __init__(self, db, llm_client=None):
        self._db = db
        self._llm_client = llm_client

    async def generate_prompts(
        self,
        workflow_id: str,
        blueprint: WorkflowBlueprint,
    ) -> List[str]:
        """
        为需要定制提示词的 Agent 批量生成工作流专属提示词

        流程：
        1. 从 blueprint.gap_analysis.agent_reshaping 获取需要定制的 Agent 列表
        2. 跳过 agents_using_default 中的 Agent（使用默认提示词）
        3. 对每个需要定制的 Agent：
           a. 从 blueprint 中获取 prompt_changes 草案
           b. 调用 LLM 扩展为完整的 TemplateContent（6 个字段）
           c. 保存到 prompt_templates 集合（带 workflow_id）
        4. 返回创建的 prompt_template IDs

        关键：TemplateContent 包含
        - system_prompt: 系统提示词（AI 角色定义）
        - user_prompt: 用户提示词模板（支持变量）
        - tool_guidance: 工具使用指导
        - analysis_requirements: 分析要求
        - output_format: 输出格式
        - constraints: 约束条件
        """

    async def _expand_prompt_draft(
        self,
        agent_id: str,
        reshaping_plan: AgentReshapingPlan,
        workflow_context: str,
    ) -> Dict[str, str]:
        """
        将蓝图中的提示词草案扩展为完整的 TemplateContent

        LLM 会参考该 Agent 的默认提示词，在此基础上定制。
        """
```

**提示词保存规则**:

```python
# 保存到 prompt_templates 集合
{
    "agent_type": "analyst",
    "agent_name": "market_analyst",
    "template_name": "可转债市场分析师",
    "workflow_id": "wf_xxx",           # ← 关键：工作流专属
    "preference_type": "workflow",
    "content": {
        "system_prompt": "你是一个可转债市场分析师...",
        "tool_guidance": "...",
        "analysis_requirements": "...",
        "output_format": "...",
        "constraints": "..."
    },
    "is_system": False,
    "created_at": "2026-02-23T10:00:00Z"
}
```

**执行引擎自动加载机制**（已有，无需修改）:

```text
加载优先级: Debug模板 > 工作流专属模板(workflow_id) > 用户模板 > 系统默认模板

当执行引擎运行该工作流时:
1. engine 传入 workflow_id
2. template_client.get_effective_template(agent_name, workflow_id=workflow_id)
3. 发现有 workflow-specific 模板 → 自动使用定制提示词
4. 没有 workflow-specific 模板 → 使用系统默认提示词
```

### 4.4 SkillOrchestrator — Skill 编排器 [NEW]

**文件**: `core/workflow/generator/skill_orchestrator.py`

**职责**: 根据蓝图中的 Skill 缺口，自动调用 SkillGenerator 管线创建缺失的工具。

```python
class SkillOrchestrator:
    def __init__(self, db, skill_generation_service=None):
        self._db = db
        self._skill_service = skill_generation_service

    async def create_missing_skills(
        self,
        blueprint: WorkflowBlueprint,
        user_id: str = "",
    ) -> List[Dict[str, Any]]:
        """
        批量创建蓝图中标记为缺失的 Skill

        流程（对每个 missing_skill）：
        1. 调用 SkillGenerationService.start_session(description)
        2. 自动确认 spec（AI 已在蓝图阶段分析好需求）
        3. 等待代码生成 + 验证
        4. 成功 → 回填 generated_skill_id，绑定到 target_agent_id
        5. 失败 → 标记 status=failed，记录错误，继续下一个

        Returns: [{skill_name, status, skill_id?, error?}]
        """

    async def bind_skills_to_agents(
        self,
        workflow_id: str,
        blueprint: WorkflowBlueprint,
    ) -> int:
        """
        将新创建的 Skill 绑定到对应 Agent（Agent 级别绑定，通过 tool_agent_bindings）

        Returns: 创建的绑定数量
        """

    async def bind_additional_tools_to_nodes(
        self,
        workflow_id: str,
        blueprint: WorkflowBlueprint,
        is_active: bool = False,
    ) -> int:
        """
        🆕 为 agent_reshaping 中的 additional_tools 创建节点级工具绑定

        不同于 bind_skills_to_agents（Agent 级别绑定），此方法创建的是
        workflow_id + node_id + agent_id 三元组的节点级绑定，实现三层配置
        模型的最高优先级层（Node 层）。

        流程：
        1. 遍历 blueprint.gap_analysis.agent_reshaping
        2. 对每个 reshaping_plan 中有 node_id 且 additional_tools 非空的条目：
           调用 BindingManager.bind_tool_for_node(agent_id, tool_id, workflow_id, node_id)
        3. 默认以草稿状态（is_active=False）创建，等待 publish() 时统一激活

        Args:
            is_active: 草稿状态（False）或立即激活（True）

        Returns: 创建的绑定数量
        """
```

**Skill 创建策略**:

| 情况 | 处理方式 |
| ---- | -------- |
| `priority: "required"` | 必须创建成功，失败则整体创建失败 |
| `priority: "optional"` | 创建失败不阻塞，记录到日志 |
| Skill 已存在（同名） | 跳过创建，直接绑定 |
| 创建超时（>60s） | 标记为 failed，用户可稍后手动重试 |

### 4.5 关键设计决策

#### 决策 1: 评估优先，按需生成提示词

**方案**: AI 对每个 Agent 评估默认提示词是否满足当前工作流需求，只为不满足的 Agent 生成工作流专属提示词。

**理由**:
- 避免不必要的提示词创建（大部分通用流程默认提示词就够了）
- 减少 LLM 调用成本
- 保持提示词管理的简洁性
- 用户后续可在提示词管理界面手动调整

**判断标准**（AI 在对话阶段评估）:
- Agent 在本流程中的角色与其默认角色**高度吻合** → 使用默认 ✅
- Agent 需要分析**非其默认领域**的内容 → 需要定制 ⚠️
- Agent 需要**特定的输出格式**或**特殊约束** → 需要定制 ⚠️

#### 决策 2: 对话式多轮沟通

**方案**: 采用 1-5 轮对话，AI 在对话中同步输出结构方案 + 提示词评估 + 工具检查。

**理由**:
- 用户可以在确认前审视 AI 的评估结果
- 用户可以纠正 AI 的判断（"market_analyst 不需要定制"或"news_analyst 也需要定制"）
- 与 Skill 生成系统的交互模式一致

#### 决策 3: 蓝图确认后再执行补全

**方案**: 对话阶段只生成蓝图（计划），用户确认后才执行 Skill 创建和提示词生成。

**理由**:
- Skill 创建涉及代码生成和沙箱执行，耗时较长
- 提示词生成需要额外 LLM 调用
- 避免用户取消后产生无用资源
- 用户可以在确认前修改蓝图中的评估结果

#### 决策 4: 闭环迭代优化

**方案**: 工作流创建完成后，用户可以在运行后提出反馈，AI 基于反馈调整工作流结构、提示词和工具绑定。

**理由**:
- 首次方案很难完美
- 通过运行结果发现问题更直观
- 优化记录纳入会话历史，形成完整的设计演进过程

#### 决策 5: 三层配置模型 — 工具绑定与提示词的精细粒度覆盖

**方案**: `tool_agent_bindings` 集合和 `prompt_templates` 集合均支持三层优先级（节点 > 工作流 > Agent 默认）。AI 架构师在生成蓝图时，在 `agent_reshaping` 中指定 `node_id`，`confirm_and_create()` 时自动为 `additional_tools` 创建节点级绑定。

> 补充说明：三层配置模型解决的是“选哪份模板/绑定配置”的问题；提示词内容在选中模板后的分层组装方式，见 [v3.0 分层提示词架构](prompt-layered-architecture.md)。

**理由**:
- 同一个 Agent 在同一工作流中可能出现多次，每次扮演不同的细分角色
- 节点级绑定避免了"同一 Agent 同一工具集"的粗粒度限制
- 三层优先级设计使配置可以从通用到专用逐层细化，且向下兼容

**三层查询逻辑**（`BindingManager.get_tools_for_node()`）:

```python
# Priority 1: 节点级（workflow_id + node_id + agent_id）  ← 最高优先级
# Priority 2: 工作流级（workflow_id + agent_id，无 node_id）
# Priority 3: Agent 默认（仅 agent_id）                   ← 保底
```

**激活时机**：创建时以草稿状态（`is_active=False`）写入，用户调用 `publish()` 时统一激活，与提示词和 Skill 的草稿发布机制一致。

#### 决策 6: UniversalAgent — AgentFactory 的数据库回落机制

**方案**: `AgentFactory.create()` 当 `agent_id` 不在代码注册表时，自动查询 `agent_configs` 集合，找到配置则创建 `UniversalAgent` 实例（而非抛出错误）。

**理由**:
- AI 架构师生成的新 Agent 角色定义存入 `agent_configs`，但没有对应的 Python 类
- 引入 `UniversalAgent` 后，80-95% 的分析型 Agent（单一职责：拿数据→分析→输出）都可以由 UniversalAgent 承载
- 只有需要复杂内部状态（辩论轮次计数、多步骤条件推理）的 Agent 才需要专有 Python 类

**UniversalAgent 核心特性**:
- `agent_id` 完全动态化，来自 `agent_configs.agent_id`
- 工具加载：调用 `BindingManager.get_tools_for_node()` 实现三层优先级
- 提示词加载：调用 `_get_prompt_from_template()` 实现三层优先级
- 零硬编码业务逻辑，`execute()` 方法完全通用

```python
class UniversalAgent(BaseAgent):
    """完全由数据库配置驱动的通用 Agent"""

    @property
    def agent_id(self) -> str:
        return self._dynamic_agent_id   # 来自 agent_configs.agent_id

    def execute(self, state: Dict) -> Dict:
        # 工具：三层优先级（node > workflow > agent默认）
        tools = BindingManager.get_tools_for_node(
            agent_id=self.agent_id,
            workflow_id=state.get("workflow_id"),
            node_id=state.get("node_id"),
        )
        # 提示词：三层优先级（已有机制，无需改动）
        prompt = self._get_prompt_from_template(state)
        return self.invoke_with_tools(prompt, tools)
```

---

## 5. 服务层设计

### 5.1 WorkflowGenerationService [ENHANCED]

**文件**: `app/services/workflow_generation_service.py`

**职责**: 会话管理、MongoDB 持久化、业务编排。整合 ResourceCollector / WorkflowPlanner / PromptGenerator / SkillOrchestrator 四大模块。

```python
class WorkflowGenerationService:
    def __init__(self, db: AsyncIOMotorDatabase, llm_client=None, provider="deepseek", model=None):
        self._db = db
        self._collector = ResourceCollector(db)
        self._planner = WorkflowPlanner(llm_client=llm_client, provider=provider, model=model)
        self._prompt_gen = PromptGenerator(db, llm_client=llm_client)
        self._skill_orch = SkillOrchestrator(db)

    # ─── 阶段 1-2：对话式需求沟通 ───

    async def start_session(self, description: str, user_id: str = "") -> Dict[str, Any]:
        """
        开始创建会话

        1. 创建 WorkflowGenerationSession
        2. 收集可用资源（ResourceCollector）—— 含 Agent 默认提示词摘要
        3. 调用 WorkflowPlanner.chat() 处理第一轮（返回方案草案 + 提示词评估 + 工具检查）
        4. 保存会话到 MongoDB（workflow_generation_sessions 集合）
        5. 返回 session_id + AI 回复
        """

    async def respond(self, session_id: str, user_message: str) -> Dict[str, Any]:
        """
        用户回复（继续对话）

        1. 从 MongoDB 加载会话
        2. 收集资源上下文
        3. 调用 WorkflowPlanner.chat()（用户可能纠正提示词评估或工具建议）
        4. 更新 MongoDB
        5. 返回 AI 回复
        """

    # ─── 阶段 3-4：确认 → 蓝图生成 → 自动补全 → 创建 ───

    async def confirm_and_create(self, session_id: str, message: str = "确认") -> Dict[str, Any]:
        """
        确认方案并执行完整创建流程

        步骤：
        1. 从 MongoDB 加载会话
        2. 收集资源上下文
        3. 调用 WorkflowPlanner.generate_blueprint() → WorkflowBlueprint JSON
        4. 【自动补全阶段】：
           a. 调用 PromptGenerator.generate_prompts() 为需要定制的 Agent 生成提示词
              （提示词带 workflow_id + node_id，保存到 prompt_templates 集合）
           b. 调用 SkillOrchestrator.create_missing_skills() 创建缺失 Skill
           c. 调用 SkillOrchestrator.bind_skills_to_agents() 绑定新 Skill（Agent 级别）
           d. 🆕 调用 SkillOrchestrator.bind_additional_tools_to_nodes() 为
              agent_reshaping.additional_tools 创建节点级工具绑定（草稿状态）
        5. 将 Blueprint 转换为 WorkflowDefinition
        6. 调用 WorkflowValidator 校验
        7. 调用 WorkflowAPI.create() 保存
        8. 更新会话状态为 completed
        9. 返回 workflow_id + 创建报告（含提示词/Skill 创建结果）

        publish() 时统一激活：
        - 提示词 draft → active（通过 prompt_ids 过滤）
        - Skill draft → active（通过 skill_ids 过滤）
        - Skill 绑定 is_active:false → true（通过 tool_id 过滤）
        - 节点级工具绑定 is_active:false → true（通过 workflow_id 过滤）

        返回示例：
        {
            "status": "completed",
            "workflow_id": "wf_xxx",
            "creation_report": {
                "prompts_created": [{"agent_id": "market_analyst", "template_id": "pt_xxx"}],
                "prompts_default": ["news_analyst", "bull_researcher"],
                "skills_created": [{"name": "xxx_calculator", "skill_id": "sk_xxx", "status": "success"}],
                "skills_failed": []
            }
        }
        """

    # ─── 阶段 6：迭代优化 ───

    async def optimize(self, session_id: str, feedback: str) -> Dict[str, Any]:
        """
        迭代优化已创建的工作流

        用户运行工作流后发现问题，可以回来继续优化。

        步骤：
        1. 从 MongoDB 加载会话（状态必须为 completed 或 optimizing）
        2. 将 feedback 追加到对话历史
        3. 调用 WorkflowPlanner.generate_optimization() 获取优化建议
        4. 返回 AI 建议（用户可继续对话或确认优化）
        """

    async def confirm_optimization(self, session_id: str) -> Dict[str, Any]:
        """
        确认优化方案并应用

        1. 重新生成 Blueprint（基于优化后的对话历史）
        2. 更新/新增提示词
        3. 更新工作流定义
        4. 记录优化历史
        """

    # ─── 会话管理 ───

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话详情（含完整对话历史和创建报告）"""

    async def list_sessions(self, status: str = None, user_id: str = "") -> Dict[str, Any]:
        """列出会话（支持逗号分隔多状态查询，如 'gathering,completed'）"""

    async def delete_session(self, session_id: str) -> bool:
        """删除会话"""

    async def get_session_history(self, session_id: str) -> Dict[str, Any]:
        """
        获取完整沟通记录（含初始创建 + 所有优化轮次）
        参考 SkillGenerationService.get_skill_history() 的分段展示模式
        """
```

### 5.2 Blueprint → WorkflowDefinition 转换

```python
async def _blueprint_to_definition(self, blueprint: WorkflowBlueprint, workflow_id: str) -> WorkflowDefinition:
    """
    将 AI 蓝图转换为标准 WorkflowDefinition

    转换规则：
    - PlannedNode → NodeDefinition（position_x/y → Position(x, y)）
    - PlannedEdge → EdgeDefinition
    - 使用 workflow_id（已提前生成，因为提示词需要引用）
    - 添加 tags: ["ai-generated", "v2"] + blueprint.tags
    - version: "2.0.0"
    """
```

### 5.3 创建流程时序

```text
用户点击"确认创建"
    │
    ▼
generate_blueprint()         ← LLM 调用，生成结构 + 缺口分析
    │
    ├── workflow_id = uuid()  ← 提前生成 ID
    │
    ▼
PromptGenerator.generate_prompts(workflow_id, blueprint)
    │ ← 只处理 agent_reshaping 中的 Agent
    │ ← 跳过 agents_using_default 中的 Agent
    │ ← 保存到 prompt_templates（带 workflow_id）
    │
    ▼
SkillOrchestrator.create_missing_skills(blueprint)
    │ ← 调用 SkillGenerator 管线（代码生成 + 沙箱验证）
    │ ← 成功的 Skill 绑定到目标 Agent
    │
    ▼
_blueprint_to_definition(blueprint, workflow_id)
    │
    ▼
WorkflowValidator.validate()
    │
    ▼
WorkflowAPI.create()          ← 保存到 workflow_definitions 集合
    │
    ▼
返回 workflow_id + creation_report
```

### 5.4 LLM 配置获取

```python
async def _get_llm_client(self) -> UnifiedLLMClient:
    """
    获取 LLM 客户端

    优先级：
    1. 构造函数传入的 llm_client
    2. 从数据库获取 deep_reasoning_model 配置
    3. 回退到 deep_analysis_model
    4. 回退到 from_provider(provider)
    """
```

---

## 6. API 设计 [ENHANCED]

### 6.1 路由前缀

`/api/workflow-generation`

### 6.2 端点列表

| 方法 | 路径 | 说明 |
| ---- | ---- | ---- |
| POST | `/sessions/start` | 开始创建会话 |
| POST | `/sessions/{session_id}/respond` | 用户回复对话 |
| POST | `/sessions/{session_id}/confirm` | 确认方案并创建工作流（含自动补全） |
| POST | `/sessions/{session_id}/optimize` | 提交优化反馈 |
| POST | `/sessions/{session_id}/confirm-optimization` | 确认并应用优化 |
| GET | `/sessions/{session_id}` | 获取会话详情 |
| GET | `/sessions/{session_id}/history` | 获取完整沟通记录（含优化轮次） |
| GET | `/sessions` | 列出会话（支持多状态筛选） |
| DELETE | `/sessions/{session_id}` | 删除会话 |

### 6.3 核心端点详情

#### POST /sessions/start

**请求**:

```json
{
    "description": "我想创建一个可转债分析流程，重点看转股溢价率和正股基本面",
    "user_id": "user123"
}
```

**响应**（AI 回复包含三部分：方案草案 + 提示词评估 + 工具检查）:

```json
{
    "code": 200,
    "data": {
        "session_id": "550e8400-e29b-41d4-a716-446655440000",
        "ai_message": "好的，根据您的需求，我为您设计了以下可转债分析流程：\n\n📊 **方案草案**\n\n**阶段一：并行分析**\n├── 市场分析师 → 分析可转债价格走势和交易量\n├── 基本面分析师 → 分析正股基本面和转股价值\n└── 新闻分析师 → 追踪可转债相关政策和事件\n\n**阶段二：多空辩论**\n└── 看多研究员 ⚔️ 看空研究员\n\n**阶段三：综合决策**\n├── 研究经理 → 综合评估\n├── 交易员 → 制定可转债交易策略\n└── 风险管理 → 评估转债特有风险\n\n📋 **提示词评估**\n- market_analyst: ⚠️ 需要定制 — 默认提示词面向股票市场，需重塑为「可转债市场分析师」\n- fundamentals_analyst: ⚠️ 需要定制 — 需增加转股价值、溢价率等分析维度\n- news_analyst: ✅ 默认足够 — 新闻分析通用性强\n- bull_researcher / bear_researcher: ✅ 默认足够\n- research_manager: ✅ 默认足够\n- trader: ⚠️ 需要定制 — 需增加可转债特有的交易策略\n- risk_manager: ⚠️ 需要定制 — 需增加转债下修、强赎等风险评估\n\n🔧 **工具检查**\n- 现有工具基本满足需求\n- 建议创建:「可转债溢价率计算器」— 计算转股溢价率、纯债溢价率等指标\n\n确认创建还是需要调整？",
        "status": "gathering",
        "current_round": 1
    }
}
```

#### POST /sessions/{session_id}/confirm

**响应（成功）**— 包含创建报告:

```json
{
    "code": 200,
    "data": {
        "status": "completed",
        "session_id": "550e8400-...",
        "workflow_id": "wf_convertible_bond_20260223",
        "blueprint_summary": "可转债分析流 — 3个分析师并行 + 多空辩论 + 综合决策",
        "creation_report": {
            "prompts_created": [
                {"agent_id": "market_analyst", "template_id": "pt_001", "new_role": "可转债市场分析师"},
                {"agent_id": "fundamentals_analyst", "template_id": "pt_002", "new_role": "可转债基本面分析师"},
                {"agent_id": "trader", "template_id": "pt_003", "new_role": "可转债交易策略师"},
                {"agent_id": "risk_manager", "template_id": "pt_004", "new_role": "可转债风险管理师"}
            ],
            "prompts_default": ["news_analyst", "bull_researcher", "bear_researcher", "research_manager"],
            "skills_created": [
                {"name": "convertible_bond_premium_calculator", "skill_id": "sk_001", "status": "success"}
            ],
            "skills_failed": []
        }
    }
}
```

#### POST /sessions/{session_id}/optimize [NEW]

**请求**:

```json
{
    "feedback": "运行后发现可转债的条款分析不够深入，需要增加对转债条款（下修条件、强赎条件、回售条件）的专项分析"
}
```

**响应**:

```json
{
    "code": 200,
    "data": {
        "session_id": "550e8400-...",
        "ai_message": "好的，根据您的反馈，我建议以下优化：\n\n📊 **结构调整**\n新增「条款分析师」节点（使用 fundamentals_analyst），专门分析转债条款\n\n📋 **提示词调整**\n- fundamentals_analyst（条款分析）: ⚠️ 需要新的定制提示词 — 专注于下修、强赎、回售条款分析\n\n🔧 **工具调整**\n- 建议创建:「可转债条款解析器」— 解析转债募集说明书中的关键条款\n\n确认应用优化吗？",
        "status": "optimizing",
        "optimization_round": 1
    }
}
```

#### GET /sessions/{session_id}/history [NEW]

**响应**（分段展示，与 Skill 沟通记录一致）:

```json
{
    "code": 200,
    "data": {
        "sections": [
            {
                "type": "initial_creation",
                "label": "初始创建",
                "created_at": "2026-02-23T10:00:00Z",
                "rounds": [
                    {"round_num": 1, "user_message": "...", "ai_message": "...", "timestamp": "..."},
                    {"round_num": 2, "user_message": "...", "ai_message": "...", "timestamp": "..."}
                ],
                "creation_report": {"prompts_created": [...], "skills_created": [...]}
            },
            {
                "type": "optimization",
                "label": "优化 v2",
                "feedback": "可转债的条款分析不够深入...",
                "created_at": "2026-02-24T14:00:00Z",
                "rounds": [
                    {"round_num": 1, "user_message": "...", "ai_message": "...", "timestamp": "..."}
                ],
                "creation_report": {"prompts_created": [...], "skills_created": [...]}
            }
        ]
    }
}
```

---

## 7. 前端集成设计 [ENHANCED]

### 7.1 入口位置

在 `frontend/src/views/Workflow/index.vue` 的创建对话框中增加 AI 创建入口。

**方案**: 在现有"新建分析流程"对话框中增加 Tab 切换：

```text
┌─────────────────────────────────────────┐
│ 新建分析流程                              │
│                                          │
│  ┌──────────┐  ┌──────────┐             │
│  │ 📋 模板   │  │ 🤖 AI    │             │
│  │   创建    │  │  智能创建  │             │
│  └──────────┘  └──────────┘             │
│                                          │
│ ─── 模板创建（当前已有逻辑）───            │
│                                          │
│  模板选择: [下拉框]                       │
│  名称: [输入框]                           │
│  描述: [文本框]                           │
│                                          │
│         [取消]  [创建并进入编辑]            │
└─────────────────────────────────────────┘
```

点击"AI 智能创建"后切换为**全屏对话界面**（参考智能助手页面风格）：

```text
┌──────────────────────────────────────────────────────────────────┐
│ 🤖 AI 工作流架构师                                     [关闭] X │
│─────────────────────────────────────────────────────────────────│
│                                                                  │
│  ┌─ AI ───────────────────────────────────────────────────────┐ │
│  │ 请描述您想要创建的分析流程，例如：                            │ │
│  │ • "帮我创建一个可转债分析流程"                               │ │
│  │ • "设计一个 ETF 快速选股分析流"                              │ │
│  │ • "创建一个多市场对比分析流程"                               │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌─ 用户 ─────────────────────────────────────────────────────┐ │
│  │ 我想创建一个可转债分析流程，重点看转股溢价率和正股基本面         │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌─ AI ───────────────────────────────────────────────────────┐ │
│  │ 📊 **方案草案**                                             │ │
│  │                                                              │ │
│  │ **阶段一：并行分析**                                         │ │
│  │ ├── 市场分析师 → 可转债价格走势和交易量                       │ │
│  │ ├── 基本面分析师 → 正股基本面和转股价值                       │ │
│  │ └── 新闻分析师 → 可转债政策和事件                            │ │
│  │                                                              │ │
│  │ **阶段二：多空辩论**                                         │ │
│  │ └── 看多研究员 ⚔️ 看空研究员                                 │ │
│  │                                                              │ │
│  │ **阶段三：综合决策**                                         │ │
│  │ ├── 研究经理 → 综合评估                                     │ │
│  │ ├── 交易员 → 可转债交易策略                                  │ │
│  │ └── 风险管理 → 转债特有风险评估                               │ │
│  │                                                              │ │
│  │ 📋 **提示词评估**                                            │ │
│  │ ┌─────────────────────────────────────────────────────────┐ │ │
│  │ │ Agent            │ 评估   │ 说明                        │ │ │
│  │ │ market_analyst   │ ⚠️定制 │ 需重塑为可转债市场分析师      │ │ │
│  │ │ fundamentals...  │ ⚠️定制 │ 需增加转股价值分析维度        │ │ │
│  │ │ news_analyst     │ ✅默认 │ 新闻分析通用性强              │ │ │
│  │ │ trader           │ ⚠️定制 │ 需增加可转债交易策略          │ │ │
│  │ │ risk_manager     │ ⚠️定制 │ 需增加转债下修强赎风险        │ │ │
│  │ └─────────────────────────────────────────────────────────┘ │ │
│  │                                                              │ │
│  │ 🔧 **工具检查**                                              │ │
│  │ • 建议创建:「可转债溢价率计算器」                              │ │
│  │                                                              │ │
│  │ 确认创建还是需要调整？                                       │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌─────────────────────────────────────────────┐ ┌────────────┐ │
│  │ 输入您的需求或修改意见...                      │ │   发送 ➤  │ │
│  └─────────────────────────────────────────────┘ └────────────┘ │
│                                                                  │
│  [← 返回模板创建]                              [✅ 确认创建]     │
└──────────────────────────────────────────────────────────────────┘
```

### 7.2 前端 API 文件

**文件**: `frontend/src/api/workflowGeneration.ts`

```typescript
// 类型定义
interface CreationReport {
    prompts_created: Array<{agent_id: string; template_id: string; new_role: string}>
    prompts_default: string[]
    skills_created: Array<{name: string; skill_id: string; status: string}>
    skills_failed: Array<{name: string; error: string}>
}

interface WGSession {
    session_id: string
    status: 'gathering' | 'creating' | 'completed' | 'optimizing' | 'failed'
    ai_message: string
    current_round: number
    rounds?: ConversationRound[]
    blueprint?: WorkflowBlueprint
    workflow_id?: string
    creation_report?: CreationReport
}

interface HistorySection {
    type: 'initial_creation' | 'optimization'
    label: string
    created_at: string
    feedback?: string
    rounds: ConversationRound[]
    creation_report?: CreationReport
}

// API 函数
export function startSession(description: string, userId?: string): Promise<WGSession>
export function respondToSession(sessionId: string, message: string): Promise<WGSession>
export function confirmSession(sessionId: string, message?: string): Promise<WGSession>
export function optimizeSession(sessionId: string, feedback: string): Promise<WGSession>
export function confirmOptimization(sessionId: string): Promise<WGSession>
export function getSession(sessionId: string): Promise<WGSession>
export function getSessionHistory(sessionId: string): Promise<{sections: HistorySection[]}>
export function listSessions(params?: { status?: string; user_id?: string }): Promise<{sessions: WGSession[], total: number}>
export function deleteSession(sessionId: string): Promise<{deleted: boolean}>
```

### 7.3 交互流程

```text
=== 初次创建 ===
1. 用户点击"新建分析流程" → 弹出创建对话框
2. 用户选择"AI 智能创建" Tab → 切换为全屏对话界面
3. 用户输入需求 → POST /sessions/start
4. 显示 AI 回复（方案草案 + 提示词评估 + 工具检查）
5. 用户可以：
   a. 继续修改 → POST /sessions/{id}/respond
   b. 确认创建 → POST /sessions/{id}/confirm
   c. 关闭（会话自动保存为草稿）
6. 确认后显示创建进度（提示词生成中... Skill 创建中... 工作流保存中...）
7. 创建成功 → 显示创建报告 → 跳转到 /workflow/editor/{workflow_id}

=== 迭代优化 ===
8. 用户运行工作流，发现问题
9. 在工作流列表中点击"AI 优化" → 打开优化对话界面
10. 输入反馈 → POST /sessions/{id}/optimize
11. AI 返回优化建议 → 用户确认 → POST /sessions/{id}/confirm-optimization
12. 优化完成 → 更新工作流定义和提示词
```

### 7.4 确认创建后的进度展示

```text
┌───────────────────────────────────────────┐
│ ⏳ 正在创建工作流...                        │
│                                            │
│  ✅ 蓝图生成完成                            │
│  ⏳ 正在生成提示词 (3/4)                    │
│     ├── ✅ market_analyst 提示词已创建      │
│     ├── ✅ fundamentals_analyst 提示词已创建 │
│     ├── ⏳ trader 提示词生成中...            │
│     └── ⬜ risk_manager 待生成              │
│  ⬜ Skill 创建                             │
│     └── ⬜ 可转债溢价率计算器                │
│  ⬜ 工作流保存                              │
└───────────────────────────────────────────┘
```

### 7.5 草稿恢复

与 Skill 生成系统一致：

- 页面加载时调用 `GET /sessions?status=gathering,optimizing` 获取未完成会话
- 在工作流列表上方显示草稿卡片
- 点击「继续」恢复对话

### 7.6 优化入口

在工作流列表中，AI 创建的工作流（带 `ai-generated` 标签）显示「🤖 AI 优化」按钮：

- 点击后打开对话界面，加载历史对话
- 用户输入优化反馈 → AI 提出修改建议
- 确认后自动应用修改

---

## 8. LLM 模型选择 [ENHANCED]

### 8.1 模型分工

| 用途 | 推荐模型 | 获取方式 | 说明 |
| ---- | -------- | -------- | ---- |
| 需求理解 + 方案设计 | 深度推理模型 | `get_reasoning_llm_config(db)` | 多轮对话、缺口分析、提示词评估 |
| Blueprint JSON 生成 | 编程模型 | `get_coding_llm_config(db)` | 结构化 JSON 输出 |
| 提示词扩展 | 深度推理模型 | `get_reasoning_llm_config(db)` | 将草案扩展为完整 TemplateContent |
| Skill 代码生成 | 编程模型 | `get_coding_llm_config(db)` | 复用 SkillGenerator 管线 |

### 8.2 模型回退链

```text
deep_reasoning_model → deep_analysis_model → quick_analysis_model → from_provider("deepseek")
```

### 8.3 Token 上限建议

| 调用 | max_tokens | 说明 |
| ---- | ---------- | ---- |
| 对话 | 4096 | 方案草案 + 评估结果 |
| Blueprint JSON | 8192 | 完整 JSON 结构 |
| 提示词扩展 | 2048 | 单个 Agent 的 TemplateContent |
| Skill 代码 | 4096 | 复用 SkillGenerator 设置 |

---

## 9. 成本估算 [ENHANCED]

### 9.1 单次创建成本

| 阶段 | 操作 | Token 消耗 | 预估成本（DeepSeek） |
| ---- | ---- | ---------- | -------------------- |
| 对话 | 资源上下文 (System Prompt) | ~4000 tokens | - |
| 对话 | 第 1 轮对话（含评估） | ~2000 tokens (in+out) | ~¥0.03 |
| 对话 | 第 2 轮对话 | ~2500 tokens (in+out) | ~¥0.04 |
| 蓝图 | Blueprint JSON 生成 | ~4000 tokens (in+out) | ~¥0.06 |
| 提示词 | 每个 Agent 提示词扩展 | ~1500 tokens (in+out) | ~¥0.02 |
| Skill | 每个 Skill 创建 | ~5000 tokens (in+out) | ~¥0.05 |

### 9.2 典型场景总成本

| 场景 | 说明 | 预估总成本 |
| ---- | ---- | ---------- |
| 简单创建（默认提示词够用） | 2 轮对话 + Blueprint + 无定制 | ~¥0.10-0.15 |
| 中等创建（4 个 Agent 需定制） | 2 轮对话 + Blueprint + 4 个提示词 | ~¥0.15-0.25 |
| 复杂创建（定制 + 新 Skill） | 3 轮对话 + Blueprint + 4 个提示词 + 1 个 Skill | ~¥0.25-0.40 |
| 迭代优化（每轮） | 1 轮反馈 + 重新生成 Blueprint + 提示词更新 | ~¥0.10-0.20 |

### 9.3 对比参考

| 功能 | 单次成本 | 说明 |
| ---- | -------- | ---- |
| Skill 生成 | ~¥0.02-0.10 | 代码生成 + 沙箱验证 |
| 工作流生成（本方案） | ~¥0.10-0.40 | 结构 + 提示词 + Skill |
| 单次分析任务 | ~¥0.50-2.00 | 多 Agent 执行 |

---

## 10. 文件清单和工作量 [ENHANCED]

### 10.1 需要创建的文件

| 文件 | 行数估算 | 说明 |
| ---- | -------- | ---- |
| `core/workflow/generator/workflow_planner.py` | ~350 行 | 核心 LLM 规划器（含评估 + 优化） |
| `core/workflow/generator/prompt_generator.py` | ~250 行 | 提示词生成器 |
| `core/workflow/generator/skill_orchestrator.py` | ~150 行 | Skill 编排器 |
| `app/services/workflow_generation_service.py` | ~500 行 | 业务服务层（含优化流程） |
| `app/routers/workflow_generation.py` | ~200 行 | API 路由 |
| `frontend/src/api/workflowGeneration.ts` | ~120 行 | 前端 API |

### 10.2 需要修改的文件

| 文件 | 修改内容 |
| ---- | -------- |
| `core/workflow/generator/__init__.py` | 更新导出列表 |
| `core/workflow/generator/workflow_spec.py` | 新增数据模型（GapAnalysisResult, AgentReshapingPlan 等） |
| `core/workflow/generator/resource_collector.py` | 增强资源收集（含提示词摘要、Skill 列表） |
| `frontend/src/views/Workflow/index.vue` | 新增 AI 智能创建入口和全屏对话界面 |
| `app/main.py`（或路由注册处） | 注册新 router |

### 10.3 已创建的文件（设计阶段产物）

| 文件 | 状态 | 需要更新 |
| ---- | ---- | -------- |
| `core/workflow/generator/__init__.py` | ✅ 已创建 | 需更新导出 |
| `core/workflow/generator/workflow_spec.py` | ✅ 已创建 | 需新增模型 |
| `core/workflow/generator/resource_collector.py` | ✅ 已创建 | 需增强 |

### 10.4 总工作量

- **新增代码**: ~1570 行（6 个新文件）
- **修改代码**: ~300 行（5 个现有文件）
- **预计实现时间**: 3-4 小时

---

## 11. 后续扩展方向（不在本版本范围）

> 注：原 v1.0 中的「提示词自动生成」和「多轮迭代」已纳入本版本，不再列为后续扩展。

### 已实现（v2.0 追加）

| 功能 | 实现方式 | 提交 |
| ---- | -------- | ---- |
| **Agent 自动创建** | 通过 `UniversalAgent` + `AgentFactory` 数据库回落机制实现：AI 将新角色定义写入 `agent_configs`，运行时自动创建 `UniversalAgent` 实例，无需任何 Python 代码 | `37e6e11e` |
| **节点级配置精细化** | 三层配置模型（Node > Workflow > Agent 默认）：`tool_agent_bindings` 和 `prompt_templates` 均支持 `workflow_id + node_id` 精确定位 | `37e6e11e` |
| **同一 Agent 多节点不同配置** | `AgentReshapingPlan` 新增 `node_id` 字段，提示词和工具绑定均以节点为粒度区分 | `0c646617` + `37e6e11e` |

### 待规划（后续版本）

| 方向 | 说明 |
| ---- | ---- |
| **可视化预览** | 确认前在对话界面内展示工作流拓扑图预览 |
| **模板推荐** | 根据用户需求自动推荐最接近的现有工作流模板 |
| **执行历史分析** | 分析工作流历史运行数据，AI 自动建议优化方案 |
| **批量工作流生成** | 一次对话生成多个变体工作流（如 A 股版、港股版、美股版） |
| **工作流克隆优化** | 基于已有工作流，通过 AI 对话快速创建变体 |

---

**最后更新**: 2026-02-24
**版本**: v2.1（追加三层配置模型 + UniversalAgent）
**维护者**: TradingAgents-CN Pro Team
