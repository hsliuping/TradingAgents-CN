# TradingAgents-CN 智能生成系统 — 实现架构文档

## 文档信息

| 项目 | 内容 |
|------|------|
| 版本 | v3.0 |
| 状态 | 实现完成 |
| 日期 | 2026-07-14 |
| 关联文档 | [ai-workflow-generation.md](ai-workflow-generation.md)、[skill-generation-system.md](skill-generation-system.md)、[agent-workshop-full-lifecycle-flow-v2.md](agent-workshop-full-lifecycle-flow-v2.md) |

---

## 1. 系统全景

### 1.1 三大智能生成子系统

TradingAgents-CN v3.0 包含三个智能生成子系统，共享同一套数据源、能力索引和工具注册表：

```
┌─────────────────────────────────────────────────────────────┐
│                    用户自然语言需求                           │
└──────────┬──────────────────┬──────────────────┬────────────┘
           │                  │                  │
           ▼                  ▼                  ▼
   ┌───────────────┐  ┌───────────────┐  ┌───────────────┐
   │  Agent 工坊    │  │  Skill 工坊    │  │ 工作流生成器   │
   │ (智能体生成)   │  │ (工具/Skill    │  │ (流程自动编排) │
   │               │  │  生成)         │  │               │
   └───────┬───────┘  └───────┬───────┘  └───────┬───────┘
           │                  │                  │
           ▼                  ▼                  │
   ┌───────────────┐  ┌───────────────┐          │
   │ MongoDB       │  │ MongoDB       │          │
   │ agent_configs │  │ external_     │          │
   │ agent_specs   │  │ skills        │          │
   │ agent_versions│  │ skill_        │          │
   │               │  │ creation_     │          │
   │               │  │ sessions      │          │
   └───────┬───────┘  └───────┬───────┘          │
           │                  │                  │
           └──────────┬───────┘                  │
                      ▼                          │
              ┌───────────────┐                  │
              │ CapabilityIndex│←─────────────────┘
              │ (ChromaDB)    │  向量搜索: Agent + Skill + Tool
              └───────┬───────┘
                      │
                      ▼
              ┌───────────────┐
              │  ToolRegistry  │  统一工具注册表
              │ (内置+MCP+外部)│
              └───────┬───────┘
                      │
                      ▼
              ┌───────────────┐
              │  LangGraph     │  工作流执行引擎
              │  Runtime       │
              └───────────────┘
```

### 1.2 核心设计原则

| 原则 | 说明 |
|------|------|
| **统一能力索引** | Agent / Skill / Tool 统一存储在 ChromaDB，通过向量语义搜索召回 |
| **4 层反幻觉** | 召回层 → Prompt 层 → 解析层（白名单校验）→ 重试层 |
| **Agent 角色重塑** | 不创建新 Agent，通过生成工作流专属提示词适配场景 |
| **Skill 按需创建** | 只有可用资源无法覆盖时才自动创建新 Skill |
| **草稿隔离** | 自动创建的资源标记为 draft，不污染生产环境 |
| **沙箱安全** | 所有 AI 生成代码在隔离子进程中执行，静态校验 + 沙箱验证 |
| **helper 透传铁律** | 代码生成必须优先使用现有 helper 函数，禁止自行实现等价逻辑 |

---

## 2. Agent 工坊 — 智能体生成

### 2.1 概述

Agent 工坊让用户通过自然语言描述需求，系统自动生成可运行的 AI Agent。生成的 Agent 通过 `UniversalAgent` 通用运行时驱动，无需编写代码。

### 2.2 API 端点

**文件**: [app/routers/agent_workshop.py](file:///c:/TradingAgentsCN/app/routers/agent_workshop.py)

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/agent-workshop/sessions/start` | POST | 创建会话 + 需求分析 |
| `/api/agent-workshop/sessions/{id}/respond` | POST | 多轮对话微调 |
| `/api/agent-workshop/sessions/{id}/preview-spec` | POST | 预览 Agent 规格 |
| `/api/agent-workshop/sessions/{id}/analyze-gaps` | POST | 工具/能力缺口分析 |
| `/api/agent-workshop/sessions/{id}/generate-tooling-plan` | POST | 生成工具需求计划 |
| `/api/agent-workshop/sessions/{id}/build-version` | POST | 生成 Agent 版本草案 |

### 2.3 生成 Pipeline

```
用户描述 "我需要一个可转债溢价率分析助手"
       │
       ▼
阶段 1: start_session
  └── RequirementAnalyzer → 意图分类 + 需求确认
       │
       ▼
阶段 2: respond (多轮对话)
  └── 补充细节: 输入输出、分析维度、报告格式
       │
       ▼
阶段 3: preview_spec
  └── LLM 生成 AgentSpec (目标、职责、输入输出、能力需求)
       │
       ▼
阶段 4: analyze_gaps
  ├── CapabilityIndex 向量搜索 → 召回可用工具
  ├── 匹配现有 builtin_tool / external_skill
  └── 输出: 建议工具列表 + 缺口工具列表 + 回退策略
       │
       ▼
阶段 5: generate_tooling_plan
  └── 为缺口工具生成创建计划 (可触发 Skill 工坊)
       │
       ▼
阶段 6: build_version
  ├── 组装 Agent 配置 (prompt_template + tools + inputs/outputs)
  ├── 静态校验 (导入规则、字段一致性)
  └── 保存到 MongoDB agent_configs (status=draft)
```

**核心服务**: [app/services/agent_workshop_service.py](file:///c:/TradingAgentsCN/app/services/agent_workshop_service.py)

### 2.4 Agent Builder LangGraph 工作流

Agent 生成过程本身也用 LangGraph 编排：

**文件**: [core/embedded_nanobot/workflows/agent_builder_graph.py](file:///c:/TradingAgentsCN/core/embedded_nanobot/workflows/agent_builder_graph.py)

```
节点流程:
  intent_classification → requirement_confirmation → gap_analysis
    → plan_generation → generate_candidate_agent → test → evaluate/publish
```

### 2.5 AgentBuilderState 状态模型

**文件**: [core/embedded_nanobot/workflows/agent_builder_state.py](file:///c:/TradingAgentsCN/core/embedded_nanobot/workflows/agent_builder_state.py)

```
AgentBuilderState
├── user_description: str           # 用户原始描述
├── intent: str                     # 意图分类
├── agent_spec: AgentSpec           # Agent 规格
├── capability_inventory: Dict      # 能力盘点结果
├── gap_report: GapAnalysis         # 缺口分析
├── candidate_plan: Dict            # 候选方案
├── generated_agent: Dict           # 生成的 Agent 配置
├── version_id: str                 # 版本 ID
├── build_status: str               # 构建状态
└── messages: List                  # 对话历史
```

### 2.6 AgentSpec 数据模型

**文件**: [app/models/agent_workshop.py](file:///c:/TradingAgentsCN/app/models/agent_workshop.py)

```python
class AgentSpec:
    agent_id: str                    # 唯一标识
    name: str                        # 显示名称
    description: str                 # 能力描述
    objective: str                   # 目标
    responsibilities: List[str]      # 职责列表
    inputs: List[str]                # 输入字段
    outputs: List[str]               # 输出字段
    output_field: str                # 主输出字段 (LangGraph state key)
    capabilities: List[str]          # 能力需求
    sample_interactions: List[Dict]  # 样本交互
    status: str                      # draft / testing / active / archived
    source: str                      # agent_workshop
    current_version: str             # 当前版本 ID
```

### 2.7 Agent 生命周期

```
draft → testing → active → archived
  ↑                    │
  └─── 重新编辑 ────────┘
```

| 状态 | 说明 |
|------|------|
| `draft` | 初始创建，仅在工坊内可见 |
| `testing` | 测试中，可被工作流引用但不作为默认 |
| `active` | 正式发布，可被工作流生成器发现和使用 |
| `archived` | 归档，不再可用 |

### 2.8 UniversalAgent 通用运行时

**文件**: [core/agents/universal.py](file:///c:/TradingAgentsCN/core/agents/universal.py)

自定义 Agent 不需要编写专门的 Python 类，而是通过 `UniversalAgent` 通用运行时驱动：

```
UniversalAgent.execute(state)
  ├── 从 prompt_templates 加载提示词 (支持 workflow_id + node_id 级别覆盖)
  ├── 从 tool_agent_bindings 加载绑定工具
  ├── 构建 LangChain tools (StructuredTool 包装)
  ├── 调用 LLM (bind_tools)
  ├── 工具调用循环 (max_tool_calls 限制)
  └── 输出写入 state[output_field]
```

### 2.9 MongoDB 集合

| 集合 | 用途 |
|------|------|
| `agent_workshop_sessions` | Agent 工坊会话 |
| `agent_specs` | Agent 规格定义 |
| `agent_versions` | Agent 版本历史 |
| `agent_evaluations` | Agent 评估记录 |
| `agent_configs` | 发布的 Agent 运行配置 (被工作流执行器读取) |
| `agent_workshop_gap_resolution_jobs` | 缺口解决任务 |

---

## 3. Skill 工坊 — 工具/Skill 智能生成

### 3.1 概述

Skill 工坊让用户通过自然语言描述工具需求，系统自动生成可执行的 Python 函数代码。生成的代码经过静态校验、沙箱执行、输出评估和迭代修复，确保质量可靠。

### 3.2 API 端点

**文件**: [app/routers/skill_generation.py](file:///c:/TradingAgentsCN/app/routers/skill_generation.py)

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/skill-generation/sessions/start` | POST | 创建会话 + 需求分析 |
| `/api/skill-generation/sessions/{id}/respond` | POST | 多轮对话 |
| `/api/skill-generation/sessions/{id}/preview-spec` | POST | 预览 Skill 规格 |
| `/api/skill-generation/sessions/{id}/confirm` | POST | 确认并触发代码生成 |
| `/api/skill-generation/sessions/{id}/repair` | POST | 修正失败后重新生成 |
| `/api/skill-generation/sessions/{id}/repair-plan` | POST | 获取修正计划 |

### 3.3 生成 Pipeline

```
用户描述 "获取管理层履历和持股变动"
       │
       ▼
阶段 1: start_session
  └── RequirementAnalyzer → 需求清晰度评估 + 边界检查
       │
       ▼
阶段 2: respond (多轮对话)
  └── 补充: 参数定义、预期输出、验证标准
       │
       ▼
阶段 3: preview_spec
  └── LLM 生成 SkillSpec (tool_id, parameters, validation_checks, test_input)
       │
       ▼
阶段 4: confirm_spec → 触发代码生成管线
  │
  ├── 4a: 侦察层 (ReconnaissanceController)
  │   ├── 规则基线探索: 检查可用数据源、API 能力
  │   ├── LLM 驱动探索: 分析数据结构、字段映射
  │   └── 输出: ImplementationFactReport (可用 API、字段清单、注意事项)
  │
  ├── 4b: 代码生成 (CodeGenerator)
  │   ├── 注入 fact_report + SkillSpec + 编码规范
  │   ├── LLM 生成 Python 函数代码
  │   └── 输出: GeneratedCode
  │
  ├── 4c: 静态校验 (StaticValidator)
  │   ├── 语法检查 (AST 解析)
  │   ├── 安全检查 (禁止模块黑名单)
  │   ├── 依赖检查 (第三方库白名单)
  │   ├── 签名一致性 (参数与 SkillSpec 匹配)
  │   └── 占位代码检查 (禁止 mock/placeholder)
  │
  ├── 4d: 沙箱执行 (SandboxRunner)
  │   ├── 子进程隔离执行
  │   ├── 超时 30 秒
  │   └── 输出: SandboxResult (stdout, stderr, returncode)
  │
  ├── 4e: 输出评估 (OutputEvaluator)
  │   ├── 类型检查 (输出与 expected_output 匹配)
  │   ├── 验证检查 (validation_checks 通过)
  │   └── 输出: EvaluationResult (pass/fail + 原因)
  │
  └── 4f: 迭代修复 (IterationController)
      ├── 失败 → 注入错误信息 → 重新生成 (最多 10 轮)
      ├── 成功 → 保存到 external_skills (status=draft)
      └── 超过上限 → 标记 failed
```

**核心服务**: [app/services/skill_generation_service.py](file:///c:/TradingAgentsCN/app/services/skill_generation_service.py)

### 3.4 SkillSpec 数据模型

**文件**: [core/tools/external/skill_spec.py](file:///c:/TradingAgentsCN/core/tools/external/skill_spec.py)

```python
class SkillSpec:
    tool_id: str                     # 唯一标识 (snake_case)
    display_name: str                # 显示名称
    description: str                 # 功能描述
    parameters: Dict                 # 参数定义 (JSON Schema)
    expected_output: Dict            # 预期输出结构
    validation_checks: List[str]     # 验证规则
    constraints: List[str]           # 约束条件
    test_input: Dict                 # 测试输入
    test_expected: Any               # 测试期望输出
    metadata: Dict                   # 元数据
```

### 3.5 静态校验规则

**文件**: [core/tools/external/static_validator.py](file:///c:/TradingAgentsCN/core/tools/external/static_validator.py)

| 检查项 | 规则 |
|--------|------|
| **语法** | AST 解析通过 |
| **模块黑名单** | 禁止 `os`, `sys`, `subprocess`, `shutil`, `importlib` 等 |
| **内部模块** | 禁止导入 `tradingagents.dataflows.providers/interface`, `hermes_tools`, `sandbox_tools`, `skill_build_tools`, `agent_builder`, `assistant_ops`, `skill_builder` |
| **允许导入** | `core.skill_runtime.data_access/project_access/standard_financial_apis`；`core.tools.implementations` 下的 `fundamentals/market/technical/portfolio/risk/news/social/trade_review/legacy_bridge` 子目录 |
| **第三方库** | 仅允许白名单中的库 (pandas, tushare, akshare, etc.) |
| **签名一致性** | 函数参数与 SkillSpec.parameters 匹配 |
| **占位代码** | 禁止 `pass`, `TODO`, `mock`, `placeholder`, `NotImplemented` |

### 3.6 代码生成编码规范

**文件**: [core/tools/external/code_generator.py](file:///c:/TradingAgentsCN/core/tools/external/code_generator.py)

LLM 生成代码时必须遵守的规则：

- 禁止装饰器 (`@tool`, `@register_tool` 由系统自动添加)
- 限制导入来源 (仅允许 standard_financial_apis 和白名单库)
- 禁止直接导入 `tradingagents.dataflows.*`
- 禁止模拟/占位代码
- 必须优先使用 `standard_financial_apis` 高级封装函数
- 必须使用 helper 透传铁律：直接使用 helper 返回的字段，禁止自行推导或映射字段名

### 3.7 侦察层

**文件**: [core/tools/external/reconnaissance_controller.py](file:///c:/TradingAgentsCN/core/tools/external/reconnaissance_controller.py)

代码生成前的数据探索步骤，产出 `ImplementationFactReport` 供 CodeGenerator 消费：

```
ReconnaissanceController.run(spec)
  ├── 规则基线探索
  │   ├── 检查 standard_financial_apis 可用函数
  │   ├── 检查数据源可用性 (tushare, akshare, baostock)
  │   └── 检查已有工具的输入输出
  ├── LLM 驱动探索
  │   ├── 分析目标 API 的返回结构
  │   ├── 字段映射 (用户需求 → API 字段)
  │   └── 识别数据获取注意事项
  └── 输出: ImplementationFactReport
      ├── available_apis: List[str]     # 可用的 API 函数
      ├── field_mapping: Dict           # 字段映射表
      ├── data_notes: List[str]         # 数据注意事项
      └── recommended_approach: str     # 推荐实现方案
```

### 3.8 迭代控制器

**文件**: [core/tools/external/iteration_controller.py](file:///c:/TradingAgentsCN/core/tools/external/iteration_controller.py)

```
IterationController.run(spec, fact_report)
  │
  ├── 第 1 轮: CodeGenerator → StaticValidator → SandboxRunner → OutputEvaluator
  │   ├── 全部通过 → 返回成功
  │   └── 失败 → 记录错误信息
  │
  ├── 第 2~10 轮: 注入上轮错误信息 → 重新生成 → 校验 → 执行 → 评估
  │   ├── 全部通过 → 返回成功
  │   └── 失败 → 继续迭代
  │
  └── 超过 10 轮 → 返回 failed + 最后一次错误
```

### 3.9 Skill 创建会话

**MongoDB**: `skill_creation_sessions` 集合

```javascript
{
  session_id: "uuid",
  user_id: "user123",
  description: "获取管理层履历和持股变动",
  status: "ANALYZING" | "SPEC_READY" | "GENERATING" | "COMPLETED" | "FAILED",
  spec: SkillSpec,                    // Skill 规格
  fact_report: ImplementationFactReport, // 侦察报告
  generated_code: str,                // 最终生成的代码
  pipeline_stage: str,                // 当前管线阶段
  pipeline_iteration: int,            // 当前迭代轮次
  pipeline_progress: Dict,            // 管线进度
  rounds: List[Dict],                 // 对话历史
  created_at, updated_at
}
```

### 3.10 Skill 运行时加载

**文件**: [core/tools/external_skill_loader.py](file:///c:/TradingAgentsCN/core/tools/external_skill_loader.py)

应用启动时自动加载已发布的 Skill：

```
load_external_skills_to_registry(db)
  ├── 查询 MongoDB external_skills (status=active)
  ├── 对每个 Skill:
  │   ├── 提取 code + parameters + description
  │   ├── 剥离装饰器 (系统自动添加 @register_tool)
  │   ├── 构建沙箱包装函数 (子进程隔离)
  │   └── 注册到 ToolRegistry
  └── 日志: "已加载 N 个外部 Skill"
```

---

## 4. 工作流生成器 — 流程自动编排

### 4.1 概述

工作流生成器让用户通过自然语言描述分析需求，系统自动编排 Agent、定制提示词、补齐工具，生成完整的可执行工作流。

### 4.2 API 端点

**文件**: [app/routers/workflow_generation.py](file:///c:/TradingAgentsCN/app/routers/workflow_generation.py)

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/workflow-generation/sessions/start` | POST | 创建会话 + 生成方案草案 |
| `/api/workflow-generation/sessions/{id}/respond` | POST | 多轮对话 |
| `/api/workflow-generation/sessions/{id}/confirm` | POST | 确认并创建工作流 |
| `/api/workflow-generation/sessions/{id}/optimize` | POST | 迭代优化 |
| `/api/workflow-generation/sessions/{id}/confirm-optimization` | POST | 确认优化 |
| `/api/workflow-generation/sessions/{id}/publish` | POST | 发布工作流 |

### 4.3 生成 Pipeline（6 阶段）

```
阶段 1: start_session     — 创建会话、收集资源、LLM 生成方案草案
阶段 2: chat / respond    — 多轮对话微调方案
阶段 3: confirm_and_create — 确认后执行 4 步自动补全
  ├── 3a: generate_blueprint    — LLM 重新生成结构化蓝图 JSON
  ├── 3b: gap_analysis          — CapabilityIndex 向量匹配工具 + 识别缺口
  ├── 3c: generate_prompts      — 为需定制的 Agent 生成专属提示词
  └── 3d: create_missing_skills — 创建缺失 Skill + 绑定工具
阶段 4: optimize          — 执行后根据反馈迭代优化
阶段 5: publish           — 发布为可用工作流
```

**核心服务**: [app/services/workflow_generation_service.py](file:///c:/TradingAgentsCN/app/services/workflow_generation_service.py)

### 4.4 蓝图生成细节：白名单校验与幻觉重试

**文件**: [core/workflow/generator/workflow_planner.py](file:///c:/TradingAgentsCN/core/workflow/generator/workflow_planner.py)

`generate_blueprint()` 在 LLM 返回蓝图 JSON 后，会立即执行白名单校验和重试：

```
generate_blueprint()
  │
  ├── 第 1 次: _call_llm_for_blueprint() → _parse_blueprint_json()
  │   └── _enforce_agent_whitelist() 校验所有 agent_id
  │       ├── nodes[].agent_id 不在白名单 → 设为 None
  │       └── agent_reshaping[].agent_id 不在白名单 → 记录到 _invalid_agent_ids
  │
  └── 检测到 _invalid_agent_ids 后:
      ├── _build_retry_hint() 构造修正提示
      │   └── "❌ bad_id 不存在 → ✅ 请改为 good_id"
      ├── _hallucination_retry_count += 1
      └── _call_llm_for_blueprint(retry_hint) 重试 1 次
```

`_build_retry_hint()` 生成格式：
```
## ⚠️ 必须修正的 agent_id 幻觉
- ❌ `moat_analysis_analyst` 不存在 → ✅ 请改为 `fundamentals_analyst_v2`
- ❌ `buffett_valuation_analyst` 不存在 → 列表里没有完全等价的 Agent，请从【可用 Agent】中挑选最接近的

**重要**：agent_id 必须严格使用上文【可用的 Agent（智能体）】中列出的 ID
```

### 4.5 4 层反幻觉机制

| 层级 | 位置 | 机制 |
|------|------|------|
| **召回层** | ResourceCollector | CapabilityIndex 向量搜索，只给 LLM 看最相关的 Agent |
| **Prompt 层** | SYSTEM_PROMPT_BLUEPRINT | 规则: "agent_id 必须逐字精确复制，包括 `_v2`/`_v1` 后缀" |
| **解析层** | `_enforce_agent_whitelist` | 代码级白名单校验，非法 ID 直接清空 |
| **重试层** | `_hallucination_retry_count` | 检测到非法 ID 后注入修正建议，重试一次 |

### 4.6 Skill 创建上下文传递

工作流生成器触发 Skill 工坊创建时，通过 `description` 字符串传递完整的人工可读上下文，但**没有使用结构化的 `handoff_context`**。

#### 上下文生成机制

`description` 由 `SkillOrchestrator._build_skill_description(req, blueprint)` 生成：

**文件**: [core/workflow/generator/skill_orchestrator.py](file:///c:/TradingAgentsCN/core/workflow/generator/skill_orchestrator.py)

```
_build_skill_description(req, blueprint)
  ├── ## 工作流背景
  │   └── 来源: blueprint.name + blueprint.summary
  ├── ## 目标 Agent 在本工作流中的角色
  │   └── _find_agent_context() 从 blueprint 中提取:
  │       ├── agent_reshaping: new_role, reshaping_direction, key_focus_areas
  │       └── 节点信息: label, description
  └── ## 需要创建的工具
      └── 来源: req.skill_name + req.skill_description + req.target_agent_id
```

`SkillGenerationService.start_session` 虽然支持 `handoff_context` 参数（包含 `confirmed_data_sources`、`searched_capabilities`、`known_verified_facts` 等字段），但当前 `SkillOrchestrator._create_one_skill` 仅传入 `description` 和 `user_id`，导致结构化的上游上下文字段为空。

实际传入 `description` 的内容示例：

```
## 工作流背景
- 工作流名称: 深度价值投资分析
- 工作流目的: 基于巴菲特价值投资理念...

## 目标 Agent 在本工作流中的角色
- Agent ID: analysis_assistant_6da7a8_v1
- 节点名称: 管理层评估
- 角色定位: 巴菲特管理层评估师
- 定制方向: 评估管理层诚信、资本配置能力...
- 关键分析维度: 管理层诚信记录, 资本配置效率...

## 需要创建的工具
- 工具名称: get_management_info
- 功能描述: 获取管理层履历、持股变动
- 使用场景: 供 analysis_assistant_6da7a8_v1 Agent 在上述工作流中使用
```

**现状**: 自然语言上下文已充分传递；结构化的 `handoff_context` 能力已设计但未启用。

### 4.7 蓝图数据模型

**文件**: [core/workflow/generator/workflow_spec.py](file:///c:/TradingAgentsCN/core/workflow/generator/workflow_spec.py)

```
WorkflowBlueprint
├── name, description, summary, rationale
├── workflow_type: str                 # stock_analysis / etf_analysis / general / ...
├── nodes: List[PlannedNode]           # 节点列表
│   └── PlannedNode {id, type, label, agent_id, description, position, config}
├── edges: List[PlannedEdge]           # 边列表
│   └── PlannedEdge {source, target, type, condition, label, animated}
├── input_config: WorkflowInputConfig  # 输入参数定义
│   └── fields: List[{name, label, type, required, default, group, order}]
├── gap_analysis: GapAnalysisResult
│   ├── agent_reshaping: List[AgentReshapingPlan]
│   │   └── {agent_id, node_id, original_role, new_role,
│   │       reshaping_direction, key_focus_areas, additional_tools}
│   ├── missing_skills: List[SkillCreationRequest]
│   │   └── {skill_name, skill_description, target_agent_id, priority,
│   │       generated_skill_id, status}
│   ├── available_tools, available_agents
│   └── analysis_summary
├── creation_progress: Dict
└── _invalid_agent_ids: Dict[str, str] # 白名单校验记录
```

---

## 5. Agent 定义与管理

### 5.1 Agent 来源

| 来源 | 存储位置 | 管理方式 |
|------|----------|----------|
| 内置 Agent | `BUILTIN_AGENTS` 字典（代码硬编码） | 版本控制，随代码发布 |
| 自定义 Agent | MongoDB `agent_configs` 集合 | Agent 工坊 UI 创建和管理 |

**配置文件**: [core/agents/config.py](file:///c:/TradingAgentsCN/core/agents/config.py)

### 5.2 AgentMetadata 结构

```python
class AgentMetadata:
    agent_id: str                    # 唯一标识 (如 fundamentals_analyst_v2)
    name: str                        # 中文名
    description: str                 # 能力描述
    inputs: List[str]                # 输入字段 (LangGraph state keys)
    outputs: List[str]               # 输出字段
    tools: List[str]                 # 可用工具白名单
    default_tools: List[str]         # 默认绑定工具
    max_tool_calls: int              # 最大工具调用次数
    output_field: str                # 主输出字段名
    report_label: str                # 报告中的中文标签
    workflow_stage: str              # 工作流阶段
    maintenance_status: AgentMaintenanceStatus
```

### 5.3 维护状态过滤

```
AgentMaintenanceStatus
├── MAINTAINED     → 正常使用，可被工作流生成器发现
├── DEPRECATED     → 已废弃 (v1 Agent)，不参与工作流生成
└── UNMAINTAINED   → 不推荐使用，不参与工作流生成
```

### 5.4 v1 → v2 阻止机制

MongoDB `agent_configs` 中可能残留旧版 v1 Agent。系统自动过滤：

- 遍历 `BUILTIN_AGENTS` 中所有 `_v2` Agent，去掉后缀生成 v1 名称阻止列表
- 从 MongoDB 加载自定义 Agent 时，跳过在阻止列表中的 ID

**实现**: [resource_collector.py](file:///c:/TradingAgentsCN/core/workflow/generator/resource_collector.py) `_collect_agents()`

### 5.5 Agent 实例化流程

```
AgentFactory.create(agent_id)
  ├── 从 BUILTIN_AGENTS 查找元数据
  │   └── DEPRECATED → 警告但仍可创建
  ├── 从 AgentRegistry 获取实现类 (内置 Agent)
  └── 找不到 → 从 MongoDB agent_configs 加载 → UniversalAgent (自定义 Agent)
```

**文件**: [core/agents/factory.py](file:///c:/TradingAgentsCN/core/agents/factory.py)

---

## 6. 数据源与工具系统

### 6.1 ToolRegistry 统一工具注册表

**文件**: [core/tools/registry.py](file:///c:/TradingAgentsCN/core/tools/registry.py)

```
ToolRegistry (单例)
  ├── 内置工具: core/tools/implementations/ → @register_tool 自动注册
  ├── 外部 Skill: MongoDB external_skills → ExternalSkillLoader 加载
  ├── MCP 工具: MCP 配置 → 动态发现
  └── 标准函数: register_function() 手动注册
```

**核心方法**:
- `get(tool_id)` → 获取工具元数据
- `get_function(tool_id)` → 获取可调用函数
- `list_all()` → 列出所有工具
- `get_by_category(category)` → 按分类筛选
- `get_langchain_tools(tool_ids)` → 包装为 LangChain StructuredTool

### 6.2 工具元数据

**文件**: [core/tools/config.py](file:///c:/TradingAgentsCN/core/tools/config.py)

```python
class ToolMetadata:
    tool_id: str
    name: str
    description: str
    category: str                    # fundamental / technical / market / ...
    data_source: str                 # tushare / akshare / baostock / ...
    capability_tags: List[str]       # 功能标签 (用于向量搜索匹配)
    tool_role_hint: str              # 角色提示
    output_shape: Dict               # 输出结构
    preferred_for: List[str]         # 推荐使用场景
    is_online: bool                  # 是否需要在线数据源
    parameters: Dict                 # 参数定义 (JSON Schema)
    timeout_tier: str                # 超时分层
```

### 6.3 内置工具分类

| 分类 | 目录 | 典型工具 |
|------|------|----------|
| `fundamental` | `implementations/fundamentals/` | 财务数据获取、估值计算、事件时间线 |
| `technical` | `implementations/technical/` | 技术指标计算、K线形态识别 |
| `market` | `implementations/market/` | 行情数据、资金流向、龙虎榜 |
| `news` | `implementations/news/` | 新闻聚合、舆情分析 |
| `data` | `implementations/data/` | 数据查询、基础数据获取 |

### 6.4 standard_financial_apis

**文件**: [core/skill_runtime/standard_financial_apis.py](file:///c:/TradingAgentsCN/core/skill_runtime/standard_financial_apis.py)

提供给 AI 生成代码复用的高级封装函数库：

| 函数 | 用途 |
|------|------|
| `get_historical_financial_annual_series` | 获取多年年度财务数据序列 |
| `get_business_segment_trend` | 获取业务分部趋势 |
| `get_shareholder_return_metrics` | 获取股东回报指标 |
| `get_company_event_timeline` | 获取公司事件时间线 |

**约束**: AI 生成代码必须优先使用这些封装函数，禁止自行实现等价的数据获取或处理逻辑。

### 6.5 数据源管理

**文件**: [tradingagents/dataflows/data_source_manager.py](file:///c:/TradingAgentsCN/tradingagents/dataflows/data_source_manager.py)

| 数据源 | 类型 | 配置 |
|--------|------|------|
| Tushare | 在线 API | `.env` 中 `TUSHARE_TOKEN` |
| AKShare | 在线 API | 免费公开 |
| BaoStock | 在线 API | `.env` 中 `ENABLE_BAOSTOCK` (默认禁用) |
| MongoDB | 本地存储 | 按版本隔离端口 (v3.0 → 27019) |
| MCP | 外部服务 | MCP 配置文件 |

**优先级策略**: 数据源按优先级排序，高优先级失败时自动降级到低优先级。

### 6.6 MCP 工具

**文件**: [core/tools/mcp/datasource_adapter.py](file:///c:/TradingAgentsCN/core/tools/mcp/datasource_adapter.py)

MCP 工具通过适配器接入：
- 原始响应解析 → 字段映射 → 单位转换 → 写入 MongoDB
- MCP 数据源可通过 MongoDB 参与数据源降级链

---

## 7. CapabilityIndex 统一能力索引

### 7.1 概述

**文件**: [app/services/capability_index_service.py](file:///c:/TradingAgentsCN/app/services/capability_index_service.py)

CapabilityIndex 将所有可复用资源统一索引到 ChromaDB（Qdrant 后端），支持向量语义搜索。三个子系统共享同一个索引。

### 7.2 索引资源类型

| 资源类型 | 来源 | source_type |
|----------|------|-------------|
| 内置工具 | ToolRegistry | `builtin_tool` |
| MCP 工具 | MCP 配置 | `mcp_tool` |
| 外部 Skill | MongoDB `external_skills` | `external_skill` |
| 标准 Skill | MongoDB `skills` | `standard_skill` |
| 内置 Agent | `BUILTIN_AGENTS` | `agent` |
| 自定义 Agent | MongoDB `agent_configs` | `agent` |

### 7.3 CapabilityDocument 结构

```python
class CapabilityDocument:
    capability_id: str        # 唯一 ID
    name: str                 # 显示名称
    label: str                # 中文标签
    description: str          # 功能描述 (向量化文本)
    source_type: str          # 来源类型
    category: str             # 分类
    inputs: List[str]         # 输入字段
    outputs: List[str]        # 输出字段
    output_field: str         # 主输出字段
    bindable: bool            # 是否可绑定到 Agent
```

### 7.4 索引构建与指纹

```
ensure_index()
  ├── _collect_source_documents()
  │   ├── registry 工具 → _merge_tools_documents()
  │   ├── standard skills → _merge_standard_skills_documents()
  │   ├── external skills → _merge_external_skills_documents()
  │   └── agents → _merge_agents_documents()
  │       ├── BUILTIN_AGENTS (MAINTAINED only)
  │       └── MongoDB agent_configs (enabled=True)
  ├── 计算指纹 (SHA1 of payload)
  ├── 与 MongoDB capability_index_state 对比
  │   ├── 指纹匹配 → 跳过构建
  │   └── 指纹不匹配 → 全量重建
  └── 写入 ChromaDB + 更新指纹
```

**主动更新触发点**:

- **Skill 工坊**: 保存新 Skill 后会调用 `CapabilityIndexService().ensure_index()` 并热注册到 ToolRegistry
- **Agent 工坊**: 每次 `_collect_capability_snapshot()` 都会调用 `ensure_index()`，发布版本前也会更新运行时配置
- **工作流生成器**: `_ensure_capability_index()` 在生成会话开始时检查索引

因此发布后 CapabilityIndex 会自动同步，不存在"发布后无法立即发现新资源"的问题。

### 7.5 向量搜索

```python
search_capabilities(query, top_k=8, source_types=None)
  ├── EmbeddingManager.embed(query)         # 查询向量化
  ├── VectorStoreManager.search(query_vec)  # ChromaDB 检索
  └── 过滤: source_types + bindable + categories
```

### 7.6 三个子系统的使用方式

| 子系统 | 搜索场景 | source_types | top_k |
|--------|----------|-------------|-------|
| Agent 工坊 | 缺口分析: 为新 Agent 匹配工具 | `builtin_tool`, `external_skill` | 8 |
| Skill 工坊 | 侦察层: 检查现有工具能力 | `builtin_tool`, `external_skill` | - |
| 工作流生成器 | Agent 过滤: 召回最相关 Agent | `agent` | 8 |
| 工作流生成器 | 工具匹配: 为每个 Agent 匹配工具 | `builtin_tool`, `external_skill` | 8 |

---

## 8. 工作流执行引擎

### 8.1 从蓝图到可执行工作流

```
WorkflowBlueprint (AI 生成)
  │
  ├── confirm_and_create()
  │   ├── 蓝图 → WorkflowDefinition 转换
  │   │   ├── PlannedNode → NodeDefinition
  │   │   ├── PlannedEdge → EdgeDefinition
  │   │   └── input_config 透传
  │   ├── 保存到 MongoDB workflows 集合
  │   └── 创建 tool_agent_bindings
  │
  └── 执行时
      ├── WorkflowEngine.compile(WorkflowDefinition)
      │   ├── StateSchemaBuilder.build_from_agents() → 动态状态 Schema
      │   └── WorkflowBuilder.build() → LangGraph StateGraph
      │       ├── 添加节点函数
      │       ├── _add_edges() → 编译图
      │       └── 工具循环 / 辩论配置 / 消息清理
      │
      └── WorkflowEngine.execute()
          ├── 准备运行时输入
          ├── compiled_graph.stream(stream_mode="updates")
          └── 累积输出结果
```

### 8.2 工作流定义模型

**文件**: [core/workflow/models.py](file:///c:/TradingAgentsCN/core/workflow/models.py)

```
WorkflowDefinition
├── id, name, description
├── workflow_type: str    # stock_analysis / etf_analysis / position_analysis / trade_review / general
├── nodes: List[NodeDefinition]
│   └── {id, type (start/end/analyst/parallel_begin/parallel_end/merge/debate/report),
│        agent_id, label, position, config, condition}
├── edges: List[EdgeDefinition]
│   └── {id, source, target, type (default/conditional), condition, label, animated}
├── input_config: WorkflowInputConfig
│   └── fields: List[{name, label, type, required, default, group, order}]
├── is_default, is_active, version
```

### 8.3 LangGraph 状态管理

**文件**: [core/state/builder.py](file:///c:/TradingAgentsCN/core/state/builder.py)

```
StateSchemaBuilder.build_from_agents(agent_ids)
  ├── 收集所有参与 Agent 的 inputs/outputs
  ├── 合并为统一的 State Schema
  ├── 添加控制字段 (messages, tool_calls, etc.)
  └── 注册到 _KNOWN_KEYS (确保 checkpoint 持久化)
```

**关键约束**: 状态修改只能在节点函数中完成（不能在条件边中），状态字段必须注册在 `_KNOWN_KEYS` 中才能在 checkpoint 加载后存活。

### 8.4 工作流类型与参数

| workflow_type | 用途 | 特有参数 |
|---------------|------|----------|
| `stock_analysis` | 单股研究 | ticker, analysis_date, selected_analysts, max_debate_rounds, research_depth |
| `etf_analysis` | ETF 分析 | ticker, analysis_date, research_depth |
| `position_analysis` | 持仓分析 | position_data, analysis_date |
| `trade_review` | 操作复盘 | trade_records, review_period |
| `general` | 通用研究 | analysis_target, custom_params |

### 8.5 input_config 生成与合并

**文件**: [core/api/workflow_api.py](file:///c:/TradingAgentsCN/core/api/workflow_api.py)

工作流的输入参数表单由 `input_config` 定义，生成策略如下：

| 场景 | 策略 |
|------|------|
| AI 新生成工作流 | LLM 在蓝图生成时自动生成 `input_config` |
| 存量流程无 input_config | API 调用 `_get_default_input_config()` 按 workflow_type 兜底 |
| 存量流程有部分字段 | `_merge_input_config()` 保留已有字段 + 补全缺失字段 |

`_merge_input_config(existing, defaults)` 合并规则：
- 已有字段保留不变
- 缺失字段从默认值追加
- 按 `order` 重新排序

`_get_default_input_config(workflow_type)` 按类型生成默认字段：
- `stock_analysis` / `etf_analysis`: ticker, analysis_date, research_depth, selected_analysts, max_debate_rounds, 模型选择
- `position_analysis` / `trade_review` / `general`: 仅包含主参数和模型选择，不含研究深度/辩论轮数

### 8.6 工作流 ID 解析优先级

执行分析任务时，系统通过 `_resolve_workflow_id()` 决定使用哪个工作流：

```
优先级 1: 任务显式指定的 workflow_id
  ↓ 不存在或无效
优先级 2: 用户为当前 workflow_type 设置的默认工作流（我的分析流）
  ↓ 未配置
优先级 3: 注册表默认配置 (config.workflow_id)
  ↓ 无效
优先级 4: 系统硬编码默认工作流（按 workflow_type 回退）
```

**关键规则**: workflow_id 优先级最高，一旦显式传入则覆盖所有默认配置，确保用户选择的自定义流程被正确调用。

---

## 9. 提示词分层架构

### 9.1 提示词来源优先级

```
节点级提示词 (workflow_id + node_id)
  ↓ fallback
工作流级提示词 (workflow_id)
  ↓ fallback
Agent 默认提示词 (agent_configs.prompt_template)
  ↓ fallback
BUILTIN_AGENTS 中的 description
```

### 9.2 提示词生成

**文件**: [core/workflow/generator/prompt_generator.py](file:///c:/TradingAgentsCN/core/workflow/generator/prompt_generator.py)

工作流生成器为需定制的 Agent 生成专属提示词：

```
generate_prompts(blueprint)
  └── 遍历 gap_analysis.agent_reshaping
      └── _generate_one_prompt(reshaping)
          ├── _fetch_original_prompt(agent_id)  ← 从数据库读取系统默认提示词作为基线
          ├── 构建 LLM Prompt (含 original_prompt, new_role, reshaping_direction, key_focus_areas)
          ├── 调用 LLM 基于原提示词做增量修改（非从零重写）
          └── 保存到 MongoDB prompt_templates
              └── {template_id, agent_id, workflow_id, node_id, content}
```

#### 基线提示词传递机制

`_expand_prompt_from_reshaping()` 调用 `_fetch_original_prompt(agent_id)` 从数据库读取该 Agent 的系统默认提示词（`is_system=True, workflow_id=None`），包含 `system_prompt`、`tool_guidance`、`analysis_requirements`、`output_format`、`constraints` 全部字段。

`EXPAND_PROMPT` 模板中增加 `## 原始提示词（参考基线）` 段落，要求 LLM：
- 在原始提示词的基础上做增量修改，而非从零重写
- 保留原始提示词中的工具使用约定、输出字段约定和核心约束
- 根据定制方向调整分析重点和角色定位
- 根据关键分析维度补充新的分析要求

---

## 10. 工具绑定机制

### 10.1 绑定级别

| 绑定级别 | 集合 | 用途 | 优先级 |
|----------|------|------|--------|
| Agent 级别 | `tool_agent_bindings` | Agent 默认可用工具 | 99 (低) |
| 节点级别 | `tool_agent_bindings` + `workflow_id` + `node_id` | 特定工作流节点的工具 | 10 (高) |

### 10.2 绑定流程

```
Agent 工坊发布 Agent:
  └── agent_configs.default_tools → Agent 级别绑定

工作流生成器创建工作流:
  ├── bind_skills_to_agents() → 新创建 Skill 的 Agent 级别绑定 (priority=99, is_active=False)
  └── bind_additional_tools_to_nodes() → agent_reshaping.additional_tools 的节点级别绑定 (priority=10, is_active=False)

运行时工具加载（严格回退策略）:
  ├── 优先读取节点级别绑定 (workflow_id + node_id + agent_id)
  │   └── 命中则只返回节点级工具（不叠加 Agent 级）
  ├── 其次读取工作流级别绑定 (workflow_id + agent_id, 无 node_id)
  │   └── 命中则只返回工作流级工具
  └── 最后读取 Agent 级别绑定 (agent_id only)
      └── 返回 Agent 默认工具
  （通过 ToolRegistry.get_langchain_tools() 包装为 LangChain StructuredTool）

⚠️ 注意: 绑定是严格互斥的，命中上级绑定后不会叠加下级绑定。例如命中了节点级绑定，就不会再加载 Agent 级绑定。
```

**绑定激活状态**: 新创建的绑定默认 `is_active=False`，需手动激活后才会在运行时生效。

---

## 11. MongoDB 集合一览

### Agent 工坊

| 集合 | 用途 |
|------|------|
| `agent_workshop_sessions` | Agent 工坊会话 |
| `agent_specs` | Agent 规格定义 |
| `agent_versions` | Agent 版本历史 |
| `agent_evaluations` | Agent 评估记录 |
| `agent_configs` | 发布的 Agent 运行配置 |
| `agent_workshop_gap_resolution_jobs` | 缺口解决任务 |

### Skill 工坊

| 集合 | 用途 |
|------|------|
| `skill_creation_sessions` | Skill 创建会话 |
| `external_skills` | AI 生成的 Skill 代码 |

### 工作流生成器

| 集合 | 用途 |
|------|------|
| `workflow_generation_sessions` | 工作流生成会话 |
| `workflows` | 工作流定义 |
| `prompt_templates` | 提示词模板 |
| `tool_agent_bindings` | 工具绑定 |

### 共享

| 集合 | 用途 |
|------|------|
| `skills` | 预定义 Skill |
| `capability_index_state` | 索引指纹 |
| `system_configs` | 系统配置 |

---

## 12. 统一分析引擎

### 12.1 概述

**文件**: [app/services/unified_analysis_engine.py](file:///c:/TradingAgentsCN/app/services/unified_analysis_engine.py)

UnifiedAnalysisEngine 是任务执行的**总入口**，负责根据任务类型和配置自动选择执行引擎。所有分析任务（单股、ETF、持仓、复盘、通用）最终都通过它执行。

### 12.2 执行引擎选择

```
UnifiedAnalysisEngine.execute_task(task)
  ├── 1. 获取流程配置 (AnalysisWorkflowRegistry)
  ├── 2. 验证参数
  ├── 3. _select_engine() 选择引擎
  │   ├── engine_type == "auto" → 使用默认引擎
  │   ├── engine_type == "workflow" → 工作流引擎
  │   ├── engine_type == "legacy" → 旧引擎 TradingAgentsGraph
  │   └── engine_type == "llm" → 直接 LLM 调用
  └── 4. 执行 → 更新任务状态
```

### 12.3 任务类型到工作流类型映射

```python
_workflow_type_for_task(task_type):
    STOCK_ANALYSIS    → "stock_analysis"
    ETF_ANALYSIS      → "etf_analysis"
    POSITION_ANALYSIS → "position_analysis"
    TRADE_REVIEW      → "trade_review"
```

### 12.4 工作流引擎执行路径

`_execute_via_workflow()` 的完整流程：

```
1. _resolve_workflow_id(task, config) — 四级优先级解析
2. 准备 workflow_inputs (参数映射: symbol → ticker)
3. 创建 AgentContext (user_id, preference_id, workflow_id)
4. 构建 legacy_config (LLM 配置, selected_analysts)
5. 调用 WorkflowAPI.execute() → LangGraph 流式执行
6. 累积输出结果
```

### 12.5 LLM 配置获取

`_build_llm_config(quick_model, deep_model)` 从数据库获取完整 LLM 配置：
- 优先级：模型配置 API Key → 厂家配置 API Key → 环境变量
- 支持快速模型和深度模型使用不同 provider

---

## 13. 默认工作流提供者

### 13.1 概述

**文件**: [core/workflow/default_workflow_provider.py](file:///c:/TradingAgentsCN/core/workflow/default_workflow_provider.py)

`DefaultWorkflowProvider` 是单例服务，管理所有系统预置工作流和用户默认工作流的加载与解析。

### 13.2 系统预置工作流

| 工作流 ID | 类型 | 说明 |
|-----------|------|------|
| `v2_stock_analysis` | stock_analysis | 股票分析（默认） |
| `v2_etf_analysis` | etf_analysis | ETF 分析 |
| `position_analysis_v2` | position_analysis | 持仓分析 |
| `trade_review_v2` | trade_review | 操作复盘 |

### 13.3 工作流类型推断

`infer_workflow_type()` 按以下优先级推断工作流类型：

```
1. 显式字段: config.workflow_type 或 config.task_type
2. ID 映射: WORKFLOW_ID_TO_TYPE 硬编码映射
3. 文本匹配: 按 ID/名称/tags 中的关键词推断 (general/etf/position/trade_review)
4. 默认回退: "stock_analysis"
```

### 13.4 活动工作流解析

`get_active_workflow_id(workflow_type)` 按以下优先级查找当前活动工作流：

```
1. 数据库 workflows 中 is_default=True 且 workflow_type 匹配
2. 数据库 system_configs 中对应类型的默认配置（兼容旧版）
3. config/settings.json 中对应类型的默认配置（本地兜底）
4. 系统硬编码默认工作流
```

### 13.5 工作流加载

`load_workflow(workflow_id)` 加载优先级：

```
1. 系统预置工作流 (SYSTEM_WORKFLOWS 字典)
2. 数据库 workflows 集合
3. 文件系统 data/workflows/{id}.json
4. 回退到该类型的系统默认工作流
```

---

## 14. 定时分析系统

### 14.1 概述

**文件**:
- [app/models/scheduled_analysis.py](file:///c:/TradingAgentsCN/app/models/scheduled_analysis.py)
- [app/worker/watchlist_analysis_task.py](file:///c:/TradingAgentsCN/app/worker/watchlist_analysis_task.py)

定时分析系统允许用户配置多个时间段（如开盘前、午盘、收盘后），按 CRON 表达式自动执行分析任务。

### 14.2 ScheduledAnalysisTimeSlot 模型

```python
class ScheduledAnalysisTimeSlot:
    name: str                    # 如 "开盘前分析"
    cron_expression: str         # "0 9 * * 1-5"
    enabled: bool
    group_ids: List[str]         # 要分析的分组
    workflow_id: Optional[str]   # 通用研究流程 ID
    workflow_params: Optional[Dict]  # { analysis_target, custom_params }
```

`workflow_params` 结构示例：
```json
{
    "analysis_target": "分析新能源行业趋势",
    "custom_params": {
        "industry": "新能源",
        "time_range": "近3年"
    }
}
```

### 14.3 定时任务执行

定时触发的通用分析流程：

```
watchlist_analysis_task 触发
  └── _execute_general_workflow_slot(slot)
      ├── 从 slot.workflow_params 读取 analysis_target + custom_params
      ├── 构建任务参数: task_category = "general"
      ├── engine_type = "workflow"
      └── task_service.create_task() → UnifiedAnalysisEngine 执行
```

---

## 15. 通用分析

### 15.1 概述

通用分析（General Analysis）是 v3.0 新增的分析类型，允许用户使用自定义工作流执行任意分析任务，不受股票代码限制。

### 15.2 前端页面

**文件**: [frontend/src/views/Analysis/GeneralAnalysis.vue](file:///c:/TradingAgentsCN/frontend/src/views/Analysis/GeneralAnalysis.vue)

- 路由: `/analysis/general`
- 侧边栏菜单: "通用研究"
- 表单仅包含: 流程选择（general 类型）、分析目标、自定义参数
- 执行后自动跳转到任务中心 (`/tasks/unified`)

### 15.3 任务标记

通用分析任务自动打上 `task_category="general"` 标记，与 single/batch/portfolio 类型任务区分。

### 15.4 结果查看

- 手动执行 → 任务中心 (`/tasks/unified`)
- 定时执行 → 定时分析页面历史按钮 + 任务中心
- 通用分析结果**不会出现**在研究报告中（报告页仅支持 single/batch/portfolio 类型）

---

## 16. 工作流编辑器与调试页面

### 16.1 概述

**文件**:
- [frontend/src/views/Workflow/Editor.vue](file:///c:/TradingAgentsCN/frontend/src/views/Workflow/Editor.vue)
- [frontend/src/views/Workflow/Execute.vue](file:///c:/TradingAgentsCN/frontend/src/views/Workflow/Execute.vue)

工作流编辑器提供可视化流程编辑和调试执行功能。

### 16.2 动态表单渲染

`Execute.vue` 根据 `workflow.input_config.fields` 动态生成执行表单：

```
渲染流程:
  ├── 按 field.group 分组
  ├── 按 field.order 排序
  └── 根据 field.type 渲染对应控件:
      ├── string → el-input
      ├── textarea → textarea
      ├── number → el-input-number
      ├── boolean → el-switch
      ├── date → el-date-picker
      ├── select → el-select
      └── select multiple → el-select (多选)
```

### 16.3 表单提交

执行时根据 `workflow_type` 组装参数：
- `general` 类型: 将表单值放入 `custom_params`
- 其他类型: 直接作为工作流参数传递

### 16.4 编辑器功能

- 只对 `stock_analysis` / `etf_analysis` 类型显示"执行"按钮
- 从 `workflow_type` 或 `config.workflow_type` 读取流程类型
- 默认 `workflow_type` 为 `general`

---

## 17. 工作流管理页面

### 17.1 概述

**文件**: [frontend/src/views/Workflow/index.vue](file:///c:/TradingAgentsCN/frontend/src/views/Workflow/index.vue)

工作流管理页面提供按类型分组展示、设置默认流程等功能。

### 17.2 按类型分组

```
groupedWorkflows:
  ├── stock_analysis  → [工作流1, 工作流2, ...]
  ├── etf_analysis    → [工作流1, ...]
  ├── position_analysis → [...]
  ├── trade_review    → [...]
  └── general         → [...]
```

每个分组显示对应类型的中文标签和 `is_default` 标记。

### 17.3 设为默认

用户可通过工作流卡片下拉菜单选择"设为默认"，后端处理：

```
POST /api/workflows/{id}/set-default
  ├── 推断 workflow_type
  ├── 更新 config/settings.json 中 default_workflows[type]
  ├── 更新数据库 workflows 中同类型 is_default 标记
  └── 同步 system_configs 中 default_workflows 字段
```

每个 workflow_type 只能有一个默认工作流，设置新默认会自动取消旧默认。

---

## 18. 关键文件索引

### Agent 工坊

| 文件 | 职责 |
|------|------|
| [app/routers/agent_workshop.py](file:///c:/TradingAgentsCN/app/routers/agent_workshop.py) | API 路由 |
| [app/services/agent_workshop_service.py](file:///c:/TradingAgentsCN/app/services/agent_workshop_service.py) | 工坊服务编排 |
| [app/models/agent_workshop.py](file:///c:/TradingAgentsCN/app/models/agent_workshop.py) | 数据模型 (AgentSpec, GapAnalysis) |
| [core/embedded_nanobot/workflows/agent_builder_graph.py](file:///c:/TradingAgentsCN/core/embedded_nanobot/workflows/agent_builder_graph.py) | Agent Builder LangGraph |
| [core/embedded_nanobot/workflows/agent_builder_state.py](file:///c:/TradingAgentsCN/core/embedded_nanobot/workflows/agent_builder_state.py) | AgentBuilderState |
| [core/agents/universal.py](file:///c:/TradingAgentsCN/core/agents/universal.py) | UniversalAgent 通用运行时 |
| [core/agents/config.py](file:///c:/TradingAgentsCN/core/agents/config.py) | BUILTIN_AGENTS 注册表 |
| [core/agents/factory.py](file:///c:/TradingAgentsCN/core/agents/factory.py) | Agent 实例化工厂 |

### Skill 工坊

| 文件 | 职责 |
|------|------|
| [app/routers/skill_generation.py](file:///c:/TradingAgentsCN/app/routers/skill_generation.py) | API 路由 |
| [app/services/skill_generation_service.py](file:///c:/TradingAgentsCN/app/services/skill_generation_service.py) | Skill 生成服务 |
| [core/tools/external/skill_spec.py](file:///c:/TradingAgentsCN/core/tools/external/skill_spec.py) | SkillSpec 数据模型 |
| [core/tools/external/code_generator.py](file:///c:/TradingAgentsCN/core/tools/external/code_generator.py) | 代码生成器 |
| [core/tools/external/static_validator.py](file:///c:/TradingAgentsCN/core/tools/external/static_validator.py) | 静态校验器 |
| [core/tools/external/sandbox_runner.py](file:///c:/TradingAgentsCN/core/tools/external/sandbox_runner.py) | 沙箱执行器 |
| [core/tools/external/iteration_controller.py](file:///c:/TradingAgentsCN/core/tools/external/iteration_controller.py) | 迭代控制器 |
| [core/tools/external/reconnaissance_controller.py](file:///c:/TradingAgentsCN/core/tools/external/reconnaissance_controller.py) | 侦察层 |
| [core/tools/external_skill_loader.py](file:///c:/TradingAgentsCN/core/tools/external_skill_loader.py) | Skill 运行时加载 |
| [core/skill_runtime/standard_financial_apis.py](file:///c:/TradingAgentsCN/core/skill_runtime/standard_financial_apis.py) | 标准金融 API 封装 |

### 工作流生成器

| 文件 | 职责 |
|------|------|
| [app/routers/workflow_generation.py](file:///c:/TradingAgentsCN/app/routers/workflow_generation.py) | API 路由 |
| [app/services/workflow_generation_service.py](file:///c:/TradingAgentsCN/app/services/workflow_generation_service.py) | 生成服务编排器 |
| [core/workflow/generator/workflow_planner.py](file:///c:/TradingAgentsCN/core/workflow/generator/workflow_planner.py) | 蓝图生成 + 反幻觉 |
| [core/workflow/generator/resource_collector.py](file:///c:/TradingAgentsCN/core/workflow/generator/resource_collector.py) | 资源收集 + 向量过滤 |
| [core/workflow/generator/skill_orchestrator.py](file:///c:/TradingAgentsCN/core/workflow/generator/skill_orchestrator.py) | Skill 创建 + 绑定 |
| [core/workflow/generator/prompt_generator.py](file:///c:/TradingAgentsCN/core/workflow/generator/prompt_generator.py) | 提示词生成 |
| [core/workflow/generator/workflow_spec.py](file:///c:/TradingAgentsCN/core/workflow/generator/workflow_spec.py) | 蓝图数据模型 |

### 共享基础设施

| 文件 | 职责 |
|------|------|
| [app/services/capability_index_service.py](file:///c:/TradingAgentsCN/app/services/capability_index_service.py) | 统一能力索引 |
| [core/tools/registry.py](file:///c:/TradingAgentsCN/core/tools/registry.py) | 工具注册表 |
| [core/tools/loader.py](file:///c:/TradingAgentsCN/core/tools/loader.py) | 内置工具自动加载 |
| [core/tools/config.py](file:///c:/TradingAgentsCN/core/tools/config.py) | 工具元数据模型 |
| [core/config/binding_manager.py](file:///c:/TradingAgentsCN/core/config/binding_manager.py) | 工具绑定管理 |
| [core/workflow/models.py](file:///c:/TradingAgentsCN/core/workflow/models.py) | 工作流定义模型 |
| [core/workflow/builder.py](file:///c:/TradingAgentsCN/core/workflow/builder.py) | LangGraph 图构建器 |
| [core/workflow/engine.py](file:///c:/TradingAgentsCN/core/workflow/engine.py) | 工作流执行引擎 |
| [core/state/builder.py](file:///c:/TradingAgentsCN/core/state/builder.py) | 状态 Schema 构建器 |
| [tradingagents/dataflows/data_source_manager.py](file:///c:/TradingAgentsCN/tradingagents/dataflows/data_source_manager.py) | 数据源管理 |

### 统一分析引擎

| 文件 | 职责 |
|------|------|
| [app/services/unified_analysis_engine.py](file:///c:/TradingAgentsCN/app/services/unified_analysis_engine.py) | 统一分析引擎 |
| [app/services/workflow_registry.py](file:///c:/TradingAgentsCN/app/services/workflow_registry.py) | 分析工作流注册表 |
| [core/workflow/default_workflow_provider.py](file:///c:/TradingAgentsCN/core/workflow/default_workflow_provider.py) | 默认工作流提供者 |

### 定时分析与通用分析

| 文件 | 职责 |
|------|------|
| [app/models/scheduled_analysis.py](file:///c:/TradingAgentsCN/app/models/scheduled_analysis.py) | 定时分析数据模型 |
| [app/worker/watchlist_analysis_task.py](file:///c:/TradingAgentsCN/app/worker/watchlist_analysis_task.py) | 定时分析任务执行 |
| [frontend/src/views/Workflow/Editor.vue](file:///c:/TradingAgentsCN/frontend/src/views/Workflow/Editor.vue) | 工作流编辑器 |
| [frontend/src/views/Workflow/Execute.vue](file:///c:/TradingAgentsCN/frontend/src/views/Workflow/Execute.vue) | 工作流调试页面 |
| [frontend/src/views/Workflow/index.vue](file:///c:/TradingAgentsCN/frontend/src/views/Workflow/index.vue) | 工作流管理页面 |
| [frontend/src/views/Analysis/GeneralAnalysis.vue](file:///c:/TradingAgentsCN/frontend/src/views/Analysis/GeneralAnalysis.vue) | 通用分析页面 |

### 提示词统一管理

| 文件 | 职责 |
|------|------|
| [app/services/system_prompt_seed_service.py](file:///c:/TradingAgentsCN/app/services/system_prompt_seed_service.py) | 系统默认提示词种子服务（启动时同步到数据库） |
| [app/services/etf_workflow_prompt_template_service.py](file:///c:/TradingAgentsCN/app/services/etf_workflow_prompt_template_service.py) | ETF 工作流专属提示词种子服务 |
| [app/main.py](file:///c:/TradingAgentsCN/app/main.py#L395-L401) | lifespan 中注册启动同步 |
| [core/workflow/generator/resource_collector.py](file:///c:/TradingAgentsCN/core/workflow/generator/resource_collector.py#L285-L326) | ResourceCollector 读取提示词内容预览 |
| [core/workflow/generator/prompt_generator.py](file:///c:/TradingAgentsCN/core/workflow/generator/prompt_generator.py#L265-L300) | PromptGenerator 读取原提示词作为基线 |

---

## 18. 提示词统一管理架构

### 18.1 问题背景

**原设计缺陷**：工作流生成时，`ResourceCollector` 只收集 Agent 元数据（id/name/description）和提示词模板数量统计，不读取提示词实际内容。导致：

1. LLM 在判断"默认提示词够用"（`agents_using_default`）还是"需要重塑"（`agent_reshaping`）时，完全没有原提示词内容作为依据
2. `PromptGenerator._expand_prompt_from_reshaping()` 从零生成新提示词，不参考原 Agent 的 system_prompt，存在风格漂移和约束丢失风险
3. 12 个 Agent 的基线提示词硬编码在代码中（`_build_system_prompt()` 的 fallback），无法统一管理

### 18.2 架构改进

#### 18.2.1 提示词种子服务

**文件**: [app/services/system_prompt_seed_service.py](file:///c:/TradingAgentsCN/app/services/system_prompt_seed_service.py)

将 12 个 Agent 的硬编码 fallback 提示词统一写入数据库 `prompt_templates` 集合：

```
SystemPromptSeedService.ensure_templates_exist()
  └── 遍历 _build_system_prompt_templates() 返回的 12 个模板
      └── _upsert_system_template(template)
          ├── 查询条件: agent_type + agent_name + workflow_id=None + is_system=True
          ├── 不存在 → insert_one（创建新模板）
          ├── 存在但内容变了 → update_one + $inc version
          └── 存在且内容相同 → 跳过
```

**12 个模板清单**：

| agent_type | agent_name | template_name |
|-----------|------------|---------------|
| analysts_v2 | market_analyst_v2 | 系统默认-市场分析师 |
| analysts_v2 | fundamentals_analyst_v2 | 系统默认-基本面分析师 |
| analysts_v2 | chip_distribution_analyst_v2 | 系统默认-筹码分布分析师 |
| researchers_v2 | bull_researcher_v2 | 系统默认-乐观研究员 |
| researchers_v2 | bear_researcher_v2 | 系统默认-审慎研究员 |
| managers_v2 | research_manager_v2 | 系统默认-研究经理 |
| trader_v2 | trader_v2 | 系统默认-研究整合员 |
| debators_v2 | risky_analyst_v2 | 系统默认-激进情景分析师 |
| debators_v2 | safe_analyst_v2 | 系统默认-防御情景分析师 |
| debators_v2 | neutral_analyst_v2 | 系统默认-基准情景分析师 |
| managers_v2 | risk_manager_v2 | 系统默认-风险管理者 |
| post_processors_v2 | report_generator_v2 | 系统默认-报告生成器 |

**排除项**：
- `news_analyst_v2`：fallback 使用动态变量 `{workflow_prompt}`，无法作为静态模板
- `UniversalAgent`：fallback 使用实例属性 `{self._agent_name}` / `{self._agent_description}`，无法作为静态模板

#### 18.2.2 启动时自动同步

**文件**: [app/main.py](file:///c:/TradingAgentsCN/app/main.py#L395-L401)

在 `lifespan` 启动流程中，能力索引同步之后、动态设置之前，调用 `ensure_system_prompt_templates()`：

```python
# 启动期同步系统默认提示词模板
from app.services.system_prompt_seed_service import ensure_system_prompt_templates
await ensure_system_prompt_templates()
```

同步策略与 ETF 工作流提示词种子（`ensure_etf_workflow_prompt_templates()`）一致：
- `remark` 标记为 `system_seed:agent_default_prompts:v1`，便于识别和清理
- 每次启动都执行 upsert 检查，确保代码与数据库保持同步
- 更新模板时自动 `$inc version`

#### 18.2.3 ResourceCollector 读取提示词内容

**文件**: [core/workflow/generator/resource_collector.py](file:///c:/TradingAgentsCN/core/workflow/generator/resource_collector.py#L285-L326)

`_collect_prompt_summaries()` 的聚合管道增加 `$first` 读取 `content.system_prompt` 全文，截取前 800 字作为预览：

```python
pipeline = [
    {"$match": {"status": "active", "is_system": True, "workflow_id": None}},
    {"$group": {
        "_id": {"agent_type": "$agent_type", "agent_name": "$agent_name"},
        "system_prompt_preview": {"$first": "$content.system_prompt"},  # 🆕 读取提示词内容
        # ...原有字段...
    }},
]
```

`_build_context_text()` 在每个 Agent 行后附加 `<提示词预览>` 块：

```
- **market_analyst_v2** (市场分析师 v2): 分析股票价格走势...  [默认提示词: 有1个模板]
  <提示词预览>
  你是一位专业的{market_type}市场分析师，擅长技术分析...
  </提示词预览>
```

**效果**：LLM 在生成蓝图时能看到每个 Agent 的实际提示词内容，从而做出有依据的"复用 vs 优化"判断。

#### 18.2.4 PromptGenerator 基于原提示词生成

**文件**: [core/workflow/generator/prompt_generator.py](file:///c:/TradingAgentsCN/core/workflow/generator/prompt_generator.py#L265-L300)

新增 `_fetch_original_prompt(agent_id)` 方法，从数据库读取该 Agent 的系统默认提示词（含 system_prompt、tool_guidance、analysis_requirements、output_format、constraints 全部字段）。

`EXPAND_PROMPT` 模板增加 `## 原始提示词（参考基线）` 段落，要求 LLM：
- 在原始提示词的基础上做增量修改，而非从零重写
- 保留原始提示词中的工具使用约定、输出字段约定和核心约束
- 根据定制方向调整分析重点和角色定位

#### 18.2.5 Fallback 保留策略

代码中的硬编码 fallback 保留不动，作为最后安全网：
- 正常流程：数据库有种子模板，fallback 不会触发
- 异常流程（数据库不可用）：fallback 保证 Agent 仍能工作
- 后续可逐步移除，但需确保种子同步服务的稳定性

### 18.3 数据流

```
系统启动
  └── ensure_system_prompt_templates()
      └── 12 个 Agent 的基线提示词 → prompt_templates 集合

工作流生成
  ├── ResourceCollector._collect_prompt_summaries()
  │   └── 读取 prompt_templates → system_prompt 前 800 字 → 传给 LLM
  │       └── LLM 基于提示词内容判断: agents_using_default vs agent_reshaping
  │
  └── PromptGenerator._expand_prompt_from_reshaping()
      └── _fetch_original_prompt(agent_id) → 读取完整提示词 → 传给 LLM
          └── LLM 基于原提示词做增量修改 → 保存为 workflow 专属模板
```

---

## 19. input_config 运行时闭环

### 19.1 问题背景

**原设计缺陷**：AI 生成工作流时自动生成 `input_config.fields`，前端 `Execute.vue` 据此动态渲染表单，但后端执行引擎**不读取 `input_config`**，仍然使用硬编码参数。导致：

1. 通用分析（general）等类型的自定义参数无法正确传递到执行引擎
2. `task_type` 硬编码为 `STOCK_ANALYSIS`，不根据 `workflow_type` 映射正确的任务类型
3. `ticker` 强制必填，但 `position_analysis`/`trade_review`/`general` 类型不需要 ticker

### 19.2 架构修复

#### 19.2.1 执行端点修复

**文件**:
- [app/routers/workflows.py](file:///c:/TradingAgentsCN/app/routers/workflows.py#L261-L359) — `/{workflow_id}/execute` 端点
- [app/routers/workflow_api.py](file:///c:/TradingAgentsCN/app/routers/workflow_api.py#L151-L210) — `/execute` 端点

修复内容：

1. **ticker 可选化**：`WorkflowExecuteRequest.ticker` 从 `str = Field(..., min_length=1)` 改为 `Optional[str] = None`
2. **workflow_type 查询**：执行前查询 `db.workflows.find_one({"_id": workflow_id}, {"workflow_type": 1, "input_config": 1})`
3. **ticker 必填校验**：仅 `stock_analysis`/`etf_analysis` 类型强制要求 ticker
4. **task_type 映射**：

```python
WORKFLOW_TYPE_TO_TASK_TYPE = {
    "stock_analysis": AnalysisTaskType.STOCK_ANALYSIS,
    "etf_analysis": AnalysisTaskType.ETF_ANALYSIS,
    "position_analysis": AnalysisTaskType.POSITION_ANALYSIS,
    "trade_review": AnalysisTaskType.TRADE_REVIEW,
    "general": AnalysisTaskType.STOCK_ANALYSIS,  # general 无独立 task_type
}
```

5. **input_config 默认值补充**：遍历 `input_config.fields`，对 `task_params` 中缺失的字段用 `field.default` 补充

#### 19.2.2 执行引擎修复

**文件**: [app/services/unified_analysis_engine.py](file:///c:/TradingAgentsCN/app/services/unified_analysis_engine.py#L521-L543)

`execute_task()` 在准备工作流输入时：

1. **优先读取 input_config**：从数据库查询 `workflow_id` 对应的 `input_config.fields`，遍历字段用 default 值补充 `workflow_inputs` 中缺失的参数
2. **通用兜底**：当 `input_config` 不存在或未定义对应字段时，使用 `setdefault` 补充 `analysis_date`、`research_depth`、`lookback_days`、`max_debate_rounds`

```
execute_task() 参数补充流程:
  ├── 读取 workflow.input_config.fields
  │   └── 遍历 fields → workflow_inputs 缺失的字段用 default 补充
  └── 通用兜底（setdefault）
      ├── analysis_date → 今天
      ├── research_depth → "标准"
      ├── lookback_days → 30
      └── max_debate_rounds → 3
```

### 19.3 修复后的完整数据流

```
前端 Execute.vue
  ├── 根据 input_config.fields 动态渲染表单
  ├── 用户填写参数 → formValues
  └── POST /{workflow_id}/execute { ticker, analysis_date, custom_params, ... }
      ↓
后端执行端点 (workflows.py / workflow_api.py)
  ├── 查询 workflow_type + input_config
  ├── ticker 必填校验（仅 stock_analysis/etf_analysis）
  ├── task_type 映射（workflow_type → AnalysisTaskType）
  ├── 构建 task_params（用户参数 + input_config 默认值 + custom_params）
  └── create_task(task_type, task_params, workflow_id)
      ↓
执行引擎 (unified_analysis_engine.py)
  ├── execute_task()
  ├── workflow_inputs = task.task_params.copy()
  ├── 读取 input_config.fields → 补充缺失参数
  ├── 通用兜底（setdefault）
  └── 执行工作流
```

---

## 20. 待规划：工作流迭代能力

### 20.1 当前局限

当前工作流生成是"一次性"的：用户描述需求 → AI 生成完整工作流 → 发布。无法基于已有工作流做增量修改，例如：

- "在上次那个巴菲特分析流程基础上，加一个护城河分析 Agent"
- "把研究经理的提示词改得更保守一些"
- "这个流程去掉风险辩论环节，简化执行流程"

### 20.2 需要的能力

| 能力 | 说明 |
|------|------|
| 基于现有工作流做增量修改 | 用户选中一个已有工作流，用自然语言描述修改意图，AI 在现有蓝图基础上做增量调整 |
| 修改前后对比 | 展示新增/删除/修改的节点、提示词变化、工具绑定变化 |
| 提示词单独编辑 | 工作流编辑器中直接编辑某个 Agent 的提示词，不需要重新生成 |
| 节点级增删 | 在编辑器中手动添加/删除节点，不需要走 AI 对话 |

### 20.3 技术思路

1. **增量修改入口**：`WorkflowPlanner` 增加 `optimize_blueprint(existing_blueprint, modification_request)` 方法，传入现有蓝图 + 用户修改意图，LLM 输出修改后的完整蓝图
2. **提示词单独编辑**：Editor.vue 中每个节点增加"编辑提示词"入口，直接修改 `prompt_templates` 中对应的 workflow 专属模板
3. **节点级增删**：Editor.vue 已有节点面板，需要增加删除节点和手动添加节点的能力

### 20.4 优先级

P0 — 工作流迭代是产品闭环的最后一块拼图，决定了用户是否愿意长期使用工作流功能。
