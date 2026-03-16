# TradingAgents-CN v3.0 — Agent 工坊与迭代生成系统设计

## 1. 概述

### 1.1 背景

当前系统已经具备以下能力：

- 运行时 Agent 元数据声明与注册
- 工作流生成会话
- Skill 缺口感知与 Skill 自动生成
- Prompt 模板、预览与设计工作台
- 统一任务中心与报告落库

这些能力已经足够支撑一个更高层的系统：**Agent 工坊**。

Agent 工坊的目标不是在现有任务完成后做结果后处理，而是围绕某个新 Agent 的完整生命周期形成闭环：

1. 定义角色与目标
2. 讨论能力边界与输入输出契约
3. 评估现有工具是否足够
4. 评估是否需要新增 Skill 或数据工具
5. 生成一版 Agent 草案
6. 运行一段时间后进行评估
7. 基于评估结果生成下一版

### 1.2 设计目标

构建一套**不修改原有内建 Agent**、以新 Agent 试点为主的迭代系统，使系统能够支持以下场景：

- 新建一个股票估值分析师，而不是手写硬编码接入
- 由 AI 与用户共同确定 Agent 的职责、边界、输出与约束
- 自动检查现有工具、Skill、Prompt 是否足够支撑该 Agent
- 为该 Agent 生成一版可运行草案
- 通过标准样本与真实运行结果进行评估
- 形成 v1 -> v2 -> v3 的版本迭代链路

### 1.3 与当前“受控成长”的区别

当前受控成长系统解决的是：

- 从任务结果中提炼经验
- 形成候选记忆与成长建议
- 为后续优化提供线索

Agent 工坊解决的是：

- 如何从零定义一个新 Agent
- 如何将角色需求转成能力设计、工具设计、Prompt 设计和评估标准
- 如何让一个 Agent 持续迭代，而不是只沉淀经验

因此，Agent 工坊是上层系统；受控成长可以作为它的输入信号来源之一，但不是主体。

---

## 2. 复用策略

本设计不推翻现有系统，而是在现有能力之上增加“Agent 规格 + 版本 + 评估”三层。

### 2.1 可直接复用的现有能力

| 能力层 | 现有模块 | 复用方式 |
| --- | --- | --- |
| Agent 声明层 | `core/agents/config.py` | 继续复用 `AgentMetadata` 与注册机制，新增版本化来源 |
| 工作流生成 | `app/routers/workflow_generation.py` | 复用对话会话、确认、优化、发布机制 |
| Skill 自动生成 | `app/routers/skill_generation.py` | 复用工具缺口补全管线 |
| Skill 缺口感知 | `app/routers/skill_gaps.py` | 复用缺口报告与“创建 Skill 预填参数”能力 |
| Prompt 模板与设计 | `app/routers/prompt_templates.py`、`app/routers/prompt_design.py`、`app/routers/prompt_preview.py` | 复用模板存储、Prompt 设计、预览与回滚机制 |
| 调试执行 | `app/routers/templates_debug.py` | 复用单 Agent 调试与工作流调试能力 |
| 统一任务中心 | `app/services/task_analysis_service.py` | 复用任务状态、结果落库、报告回写 |
| 报告模板 | `app/routers/report_templates.py` | 复用新 Agent 的输出展示模板 |

### 2.2 需要新增的能力

以下能力目前不存在，必须新增：

1. Agent 规格模型
2. Agent 工坊会话模型
3. Agent 版本构建器
4. Agent 评估器
5. Agent 版本发布与灰度策略

---

## 3. 总体架构

### 3.1 核心思想

Agent 工坊以“规格驱动”代替“硬编码驱动”。

用户并不是直接创建一个 Python 类，而是先创建一个 **AgentSpec**，再通过系统自动生成：

- Agent 元数据
- Prompt 模板
- 工具绑定建议
- Skill 缺口补全任务
- 评估用例
- 版本记录

### 3.2 总流程

```text
用户提出新 Agent 需求
    -> Agent 工坊会话启动
    -> AI 讨论角色、目标、输入输出、边界
    -> 生成 AgentSpec 草案
    -> 评估工具/Skill/Prompt 缺口
    -> 自动补齐缺口或生成待处理项
    -> 生成 AgentVersion 草案
    -> 沙箱调试与标准样本评估
    -> 发布为 draft / testing / active
    -> 真实运行后收集评估结果
    -> 发起下一轮优化会话
```

### 3.3 子系统划分

1. Agent 规格层
2. Agent 构建层
3. Agent 评估层
4. Agent 发布层

---

## 4. 数据模型设计

### 4.1 AgentSpec

`AgentSpec` 表示一个 Agent 的“产品定义”，而不是某一版可执行实现。

建议新增集合：`agent_specs`

```json
{
  "spec_id": "valuation_analyst",
  "name": "股票估值分析师",
  "domain": "stock_analysis",
  "target_users": ["中长期投资者", "基本面研究员"],
  "primary_goal": "输出透明、可解释、可复核的股票估值区间与核心假设",
  "responsibilities": [
    "选择适用估值方法",
    "给出估值区间",
    "披露关键假设",
    "说明失效条件"
  ],
  "non_goals": [
    "不负责短线择时",
    "不负责情绪面判断"
  ],
  "inputs": [
    "stock_symbol",
    "market_type",
    "financial_data",
    "industry_context"
  ],
  "outputs": [
    "valuation_summary",
    "valuation_methods",
    "assumptions",
    "risk_adjustments",
    "fair_value_range",
    "invalid_conditions"
  ],
  "success_criteria": [
    "估值方法选择有依据",
    "核心假设披露完整",
    "结论可解释",
    "结果与用户目标一致"
  ],
  "status": "draft"
}
```

### 4.2 AgentWorkshopSession

`AgentWorkshopSession` 表示一次围绕某个 Spec 的讨论和构建过程。

建议新增集合：`agent_workshop_sessions`

核心字段：

- `session_id`
- `spec_id`
- `stage`: gathering / planning / gap-analysis / building / evaluating / completed
- `messages`
- `current_spec_snapshot`
- `gap_report`
- `proposed_version`

### 4.3 AgentVersion

`AgentVersion` 表示某个 Spec 的一个可运行版本。

建议新增集合：`agent_versions`

关键字段：

```json
{
  "version_id": "valuation_analyst_v1",
  "spec_id": "valuation_analyst",
  "version": 1,
  "status": "testing",
  "agent_metadata": {},
  "prompt_template_ref": {
    "template_id": "tpl_valuation_analyst_v1"
  },
  "required_tools": [
    "get_stock_market_data_unified",
    "get_financials"
  ],
  "required_skills": [],
  "output_schema": {},
  "evaluation_policy": {},
  "published_from_session_id": "aws_001"
}
```

### 4.4 AgentEvaluationReport

`AgentEvaluationReport` 用于记录某一版 Agent 的评估结果。

建议新增集合：`agent_evaluations`

应覆盖三类评估：

1. 规格一致性评估
2. Prompt 质量评估
3. 运行结果评估

核心字段：

- `version_id`
- `evaluation_type`: sandbox / benchmark / production-review
- `sample_set_id`
- `scores`
- `issues`
- `recommendations`
- `decision`: pass / revise / reject

---

## 5. 四大模块设计

### 5.1 规格讨论器

职责：

- 与用户确认 Agent 的角色、目标、边界
- 将自然语言需求收敛为结构化 `AgentSpec`

输入：

- 用户描述
- 现有 Agent 目录
- 当前工具目录
- 现有 Prompt 模板能力快照

输出：

- `AgentSpec` 草案
- 未澄清问题列表

讨论重点：

1. 该 Agent 解决什么问题
2. 不解决什么问题
3. 应输出什么
4. 需要哪些证据
5. 失败定义是什么

### 5.2 资源缺口评估器

职责：

- 判断当前系统能否支撑该 Agent
- 识别工具、Skill、Prompt、报告模板缺口

输出应至少包含：

1. 可复用 Agent 能力
2. 可复用工具清单
3. 缺失工具清单
4. 可通过 Skill 自动补齐的缺口
5. 需要人工新增的数据源或业务逻辑

与现有系统关系：

- Skill 缺口沿用 `skill-gaps`
- Skill 自动补全沿用 `skill-generation`

### 5.3 Agent 版本构建器

职责：

- 基于 `AgentSpec` 生成一版 `AgentVersion`

构建内容包括：

1. `AgentMetadata` 草案
2. Prompt 模板草案
3. 工具绑定草案
4. 输出 Schema
5. 报告模板绑定
6. 评估策略初稿

设计原则：

- 不覆盖原有内建 Agent
- 首版默认为 `draft` 或 `testing`
- 构建产物必须可追溯到某次 workshop session

### 5.4 运行评估器

职责：

- 判断当前版本是否真正达到设计目标

评估维度：

1. 角色对齐
是否输出了该 Agent 应该输出的内容

2. 用户目标对齐
结果是否满足用户在规格中定义的目标

3. Prompt 质量
Prompt 是否漏约束、是否引导偏题、是否存在冗余指令

4. 工具有效性
工具调用是否足够、是否经常缺失必要数据

5. 输出质量
结论是否透明、是否可解释、是否有明确假设与失效条件

---

## 6. 股票估值分析师试点

### 6.1 试点原因

股票估值分析师适合作为 Agent 工坊的第一个试点，原因是：

1. 目标明确
2. 输出结构相对稳定
3. 与现有市场分析、基本面分析存在边界差异
4. 容易定义标准测试样本

### 6.2 规格草案

角色：股票估值分析师

主要目标：

- 给出合理估值区间
- 解释估值方法为什么适用
- 披露关键假设
- 明确哪些条件会使估值失效

非目标：

- 不负责短线买卖点
- 不替代技术分析
- 不直接输出交易建议

推荐输出结构：

1. 估值结论摘要
2. 适用估值方法
3. 核心假设
4. 风险折价或调整项
5. 合理价值区间
6. 敏感性分析
7. 失效条件

### 6.3 工具评估示例

优先检查现有工具是否覆盖：

1. 股票基础行情
2. 财务数据
3. 行业可比信息
4. 历史估值指标

可能缺失的能力：

1. 估值计算 Skill
2. 可比公司筛选 Skill
3. 敏感性分析 Skill

### 6.4 Prompt 约束示例

必须包含：

1. 估值方法选择依据
2. 关键假设列表
3. 假设的敏感性
4. 不确定性来源
5. 估值失效条件

必须避免：

1. 空泛地说“估值合理”但不给区间
2. 只给单点目标价
3. 不解释假设
4. 用情绪判断代替估值逻辑

---

## 7. API 设计建议

建议新增前缀：`/api/agent-workshop`

### 7.1 会话相关

- `POST /api/agent-workshop/sessions/start`
  启动 Agent 工坊会话

- `POST /api/agent-workshop/sessions/{session_id}/respond`
  用户回复，推进规格讨论

- `GET /api/agent-workshop/sessions/{session_id}`
  获取会话详情

### 7.2 规格与版本

- `POST /api/agent-workshop/sessions/{session_id}/preview-spec`
  预览 AgentSpec

- `POST /api/agent-workshop/sessions/{session_id}/analyze-gaps`
  生成资源缺口报告

- `POST /api/agent-workshop/sessions/{session_id}/build-version`
  生成 AgentVersion 草案

- `POST /api/agent-workshop/versions/{version_id}/publish`
  发布版本

### 7.3 评估相关

- `POST /api/agent-workshop/versions/{version_id}/evaluate`
  对某版 Agent 进行评估

- `GET /api/agent-workshop/versions/{version_id}/evaluations`
  获取评估历史

- `POST /api/agent-workshop/versions/{version_id}/iterate`
  基于评估结果发起下一轮迭代

---

## 8. 前端设计建议

建议新增页面：

1. `frontend/src/views/Workflow/AgentWorkshop.vue`
   Agent 工坊首页，展示所有 Spec、版本、状态

2. `frontend/src/views/Workflow/AgentWorkshopCreate.vue`
   创建新 Agent，会话式定义规格

3. `frontend/src/views/Workflow/AgentVersionDetail.vue`
   查看版本详情、Prompt、工具绑定、评估结果

4. `frontend/src/views/Workflow/AgentEvaluation.vue`
   查看测试样本、评分、问题与建议

页面复用策略：

- 会话 UI 复用 WorkflowGeneration / SkillGeneration 的对话流
- Prompt 查看与修改复用 PromptDesignWorkspace
- Skill 缺口处理跳转到 SkillGaps / SkillGenerationCreate

---

## 9. 分阶段实现

### Phase 1: 规格与会话 MVP

目标：先把“讨论 + 结构化规格”跑通。

产出：

- `agent_specs`
- `agent_workshop_sessions`
- 启动/回复/预览规格 API
- 股票估值分析师试点规格

### Phase 2: 缺口分析与版本草案

目标：先能生成一版 AgentVersion 草案，不要求自动发布。

产出：

- 缺口报告
- Prompt 草案
- 工具绑定草案
- Agent 元数据草案

### Phase 3: 评估与迭代

目标：让版本可测试、可评分、可进入下一轮。

产出：

- 标准样本评估
- 运行期评估
- 版本迭代入口

### Phase 4: 灰度发布与生产反馈

目标：让新 Agent 可以在可控范围内上线。

产出：

- draft / testing / active / archived 生命周期
- 发布审批
- 生产反馈回流

---

## 10. 关键决策

### 10.1 不直接修改原有 Agent

原则：

- 内建 Agent 保持稳定
- 新 Agent 一律先以版本草案方式存在
- 经评估通过后再进入 active

### 10.2 先做“独立 Agent 工坊”，再考虑接入主流程

股票估值分析师试点不应直接插入原始单股分析主工作流。

正确方式：

1. 先独立创建
2. 单独调试
3. 单独评估
4. 通过后再决定是否纳入某条工作流

### 10.3 Prompt、工具、Skill、评估必须分层

不要把“生成 Agent”简化为“生成 Prompt”。

一个可迭代 Agent 至少要同时有：

1. 角色规格
2. 工具依赖
3. Prompt 约束
4. 输出 Schema
5. 评估标准

缺任意一层，都无法形成稳定迭代闭环。

---

## 11. 预期收益

引入 Agent 工坊后，系统会获得三种新的能力：

1. Agent 生产能力
不再依赖手工硬编码新增 Agent

2. Agent 评估能力
能系统化判断 Agent 是否达到设计目标

3. Agent 迭代能力
能围绕一个 Agent 形成多版本改进链路

对当前系统而言，这一步比单纯增加“结果后处理成长”更接近真正的 Agent 演化系统。