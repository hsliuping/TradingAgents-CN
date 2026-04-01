# TradingAgents-CN v3.0 — Agent 工坊与迭代生成系统设计

> 更新时间：2026-04-01
>
> 本文档已按当前实现重写，重点反映现有后端服务、前端工作台和版本化链路的真实结构，而不是保留最初的概念草案。

## 1. 概述

### 1.1 背景

Agent 工坊是 TradingAgents-CN 内部面向“新 Agent 从需求到版本迭代”的工作台。它不是单纯的 Prompt 生成器，也不是 Skill 工坊的包装层，而是把以下几个已有能力组织成一个可持续迭代的闭环：

- 规格澄清与结构化收敛
- 系统已有能力检索与缺口分析
- 工具补齐建议与 Skill 工坊跳转
- AgentVersion 组装
- Prompt 模板生成与发布前审阅
- 沙箱调试、评估、迭代和发布

当前设计的核心目标仍然是：

1. 不直接修改内建 Agent
2. 让新 Agent 先以 Spec 和 Version 形式存在
3. 让版本构建、调试、评估和发布形成完整链路
4. 让“能力缺口”与“实现补齐”在设计阶段显式暴露，而不是等运行期失败后再补洞

### 1.2 与最初版本的主要差异

相较于最初设计，当前实现已经发生了几个重要变化：

1. 前端流程已经从粗粒度的四段式页面，演进为五步工作台：聊需求、看规格、查缺口、生成版本、评估迭代。
2. 缺口分析不再只是静态列出缺失能力，而是先基于能力快照检索，再做合法工具清单约束和后置纠偏。
3. 工具需求草案已经独立成一步，不再和 gap report 混在一起。
4. 版本构建后不只是保存 AgentVersion，还会同步生成 Prompt 模板引用、输出 schema 和评估策略。
5. 发布前已经支持查看和修改版本 Prompt，运行前已经支持 debug。
6. 规格澄清阶段已经引入结构化 IO、可行性状态、完整度评分、待确认问题和拒绝原因，不再只是“LLM 聊天 + 规格快照”。

### 1.3 与受控成长、Skill 工坊的关系

Agent 工坊的职责边界目前比较清晰：

- Agent 工坊：定义新 Agent 的职责、约束、能力边界和版本迭代链路。
- Skill 工坊：为 Agent 工坊识别出来的缺口生成具体工具或能力。
- 受控成长：沉淀运行期经验，作为后续调优输入，不负责定义 Agent 本身。

因此，Agent 工坊是上层编排系统；Skill 工坊是补齐执行层；受控成长是运行反馈层。

### 1.4 配套工程文档

为了避免主设计文档同时承担“产品设计说明”和“接口维护手册”两种职责，当前已拆出一份配套工程文档：

- [Agent 工坊接口与时序说明](agent-workshop-interface-sequence.md)

建议使用方式：

- 看产品目标、设计原则、模块边界时，读本文档。
- 看前后端交互、接口契约、状态流转和持久化写入点时，读配套工程文档。

---

## 2. 核心设计原则

### 2.1 规格驱动，而不是 Prompt 驱动

用户在 Agent 工坊中不是直接写 Prompt，而是先形成结构化 AgentSpec。后续的 Prompt 模板、工具绑定、输出 schema 和评估策略，都从 Spec 推导出来。

### 2.2 先确认规格，再讨论实现

前端工作台已经明确把“看规格”和“查缺口”拆开，避免用户在职责和输出还没讲清楚时，就被工具细节打断。这也是当前实现和旧设计相比最大的流程升级之一。

### 2.3 缺口分析必须受真实能力约束

当前实现已经明确区分：

- 可直接绑定的真实工具
- 可复用但不能直接绑定的能力/模块/Skill
- 真正缺失、需要新建的工具或能力

缺口分析的目标不是“让 LLM 想象一个合理方案”，而是让它在真实能力目录约束下做覆盖判断。

### 2.4 版本构建、调试、评估、发布必须分层

一个可迭代的 Agent 版本至少要有：

1. 规格定义
2. 工具依赖
3. Prompt 模板
4. 输出 schema
5. 评估策略
6. 调试和评估记录

只生成 Prompt 或只生成 AgentMetadata，都不足以形成稳定闭环。

---

## 3. 当前总体架构

### 3.1 工作台视角的五步流程

当前前端工作台以五步展示整个链路：

1. 聊需求
2. 看规格
3. 查缺口
4. 生成版本
5. 评估迭代

它对应的实际后端行为是：

```text
用户描述新 Agent
  -> start_session
  -> requirement clarification 生成首版 AgentSpec
  -> 多轮 respond 继续收敛规格
  -> preview_spec 进入规格确认
  -> analyze_gaps 做能力覆盖和缺口判断
  -> generate_tooling_plan 生成补齐草案
  -> build_version 生成 AgentVersion + Prompt 模板 + 输出 schema + 评估策略
  -> debug_version 先跑沙箱
  -> evaluate_version 形成评分与建议
  -> iterate_version 基于问题发起下一轮
  -> publish_version 正式切到 active
```

### 3.2 后端状态机

后端会话当前仍保留一套较粗粒度的状态：

- gathering
- planning
- gap-analysis
- building
- evaluating
- completed

需要注意：

- 前端五步工作台是用户交互视角
- 后端 stage 是会话生命周期视角

两者不是一一等价映射。例如“看规格”仍可能处于 gathering 或 planning；“评估迭代”会覆盖 evaluating 和 completed 两种会话状态。

### 3.3 主要子系统

当前实现可以拆成六个子系统：

1. 规格澄清器
2. 能力快照与检索层
3. 缺口分析器
4. 工具需求草案生成器
5. 版本构建器
6. 调试评估与发布器

---

## 4. 数据模型

### 4.1 AgentSpec

AgentSpec 表示某个 Agent 的产品定义，而不是可运行版本。当前字段已经明显比最初设计更丰富。

当前关键字段包括：

- spec_id
- name
- domain
- target_users
- primary_goal
- responsibilities
- non_goals
- inputs
- outputs
- success_criteria
- constraints
- preferred_methods
- capability_requirements
- sample_symbols
- status
- source
- owner_user_id
- latest_session_id
- current_version_id
- version_count

当前有两个关键变化：

1. inputs 和 outputs 已支持结构化字段对象，不再只是一维字符串列表。
2. capability_requirements 已作为显式字段存在，用于表达“这个 Agent 到底需要什么能力”，而不仅仅依赖 responsibilities 或 outputs 间接推断。

结构化 IO 字段当前形态为：

```json
{
  "name": "fair_value_range",
  "type": "object",
  "required": true,
  "description": "估值区间及上下界说明"
}
```

同时，为兼容旧数据，系统仍允许 inputs 和 outputs 混用：

- 纯字符串
- 结构化对象
- JSON 字符串形式的对象

### 4.2 AgentWorkshopSession

AgentWorkshopSession 表示一次围绕某个 Spec 的讨论、缺口分析和版本构建过程。当前核心字段包括：

- session_id
- spec_id
- user_id
- stage
- current_round
- messages
- current_spec_snapshot
- pending_questions
- completeness_score
- feasibility_status
- refusal_reason
- gap_report
- tooling_plan
- proposed_version

其中以下字段是当前工作流的关键状态来源：

- pending_questions：当前还缺哪些明确确认
- completeness_score：规格完整度评分
- feasibility_status：当前需求是否可继续推进
- refusal_reason：需求不可行时的拒绝理由

当前 feasibility_status 实际承担三类作用：

1. 前端是否继续推进
2. 用户是否需要补充澄清
3. 当前规格是否已经超出 Agent 工坊支持范围

### 4.3 AgentWorkshopGapAnalysis

缺口分析结果目前已经是一个独立的结构化模型，字段包括：

- existing_tools
- suggested_tools
- suggested_capabilities
- manual_dependencies
- blocking_gaps
- fallback_strategy
- build_recommendations
- notes
- generated_by
- error_message
- raw_response

几个实现层面的约束值得明确写入设计：

1. existing_tools 只允许保留真实可用能力，LLM 幻觉工具会被过滤。
2. suggested_capabilities 是当前主字段，保留 suggested_skills 仅用于兼容旧数据。
3. valuation 规格会额外经过后置纠偏，强制补齐估值方法级能力覆盖，避免 PE/PB/PEG 场景漏掉真实已有工具。
4. 当 LLM 失败时，不再静默回退成宽泛建议，而是保留 error_message 和 raw_response，供页面直接展示。

### 4.4 ToolingPlan

tooling_plan 已经是当前链路中的一个独立对象，不应再被视为 gap analysis 的附属备注。其核心字段包括：

- summary
- missing_capabilities
- draft_tools
- implementation_order
- notes
- generated_by
- error_message
- raw_response

其中 draft_tools 当前已经细化到工具蓝图级别，每项包含：

- tool_id
- tool_name
- capability_description
- priority
- why_needed
- solves_gaps
- fallback_before_ready
- dependencies
- inputs
- outputs
- acceptance_criteria

这一步的职责已经不是“告诉用户缺什么”，而是“把缺口变成可交付的实现草案”。

### 4.5 AgentVersion

AgentVersion 表示某个 Spec 的一个可运行版本。当前关键字段包括：

- version_id
- spec_id
- version
- status
- agent_metadata
- prompt_template_ref
- required_tools
- required_capabilities
- output_schema
- evaluation_policy
- published_from_session_id

几个实现细节需要保留在文档中：

1. required_capabilities 是当前正式字段，required_skills 仅作为兼容 alias。
2. build_version 不只保存版本记录，还会同步生成 prompt_template_ref。
3. publish_version 时会把之前 active 的版本归档，并确保 runtime agent config 同步更新。

### 4.6 AgentEvaluationReport

AgentEvaluationReport 当前用于承载版本调试后的正式评估记录。关键字段包括：

- evaluation_id
- version_id
- evaluation_type
- sample_set_id
- scores
- issues
- recommendations
- details
- decision

当前 evaluation_type 支持：

- sandbox
- benchmark
- production-review

当前设计上，debug_version 和 evaluate_version 是两个相邻但分离的动作：

- debug_version：跑一遍实际执行，拿到 Prompt、工具轨迹和输出原文
- evaluate_version：对结果做评分和问题归纳

---

## 5. 规格澄清设计

### 5.1 输入与输出

规格澄清器当前接收的是“多轮用户消息”，输出的是一个 turn_result，对外最终沉淀为：

- AgentSpec
- ai_message
- pending_questions
- completeness_score
- feasibility_status
- refusal_reason

### 5.2 当前实现要点

当前规格澄清已经不是简单的“根据最近一轮输入重新生成整个 spec”，而是以下混合策略：

1. 使用现有 spec 快照做增量收敛，而不是每轮全部重写。
2. 引入能力快照作为上下文，减少对系统现有能力的误判。
3. 要求 LLM 不要无证据重写稳定字段。
4. 对默认方案、推荐假设和未确认项做后处理，强制回流到 pending_questions。
5. 对 deterministic-tool 这类能力要求做真实性校验，避免规格直接写入不可交付要求。

### 5.3 结构化 IO 保真

当前实现已经修复早期“inputs/outputs 被压平”的问题：

- LLM 返回的结构化字段会保留
- 旧字符串数组仍可兼容
- 前端展示会自动把结构化字段转换成可读标签

这意味着现在的 Spec 已经可以承载更明确的输入输出契约，而不仅仅是标签列表。

### 5.4 完整度与可行性

当前 completeness_score 和 feasibility_status 的设计目标是：

- completeness_score：衡量规格收敛度
- feasibility_status：衡量是否应该继续推进版本生成

当前页面逻辑上主要区分：

- need-clarification：先继续澄清
- not-feasible：当前范围内拒绝推进
- feasible：可以进入缺口分析和版本构建

其中 pending_questions 是推进条件的主要显式输出，而不是隐藏在 ai_message 里的自然语言提醒。

---

## 6. 能力快照与缺口分析设计

### 6.1 能力快照

当前工坊支持单独获取系统能力快照，返回内容包括：

- builtin_data_tools
- builtin_analysis_tools
- external_data_skills
- external_analysis_skills
- external_skill_tool_ids
- valuation_tools
- valuation_skills
- summary_text
- totals

当前 totals 还会额外带上：

- builtin_tools
- external_skills
- indexed_capabilities
- retrieved_capabilities

说明当前实现已经接入 Capability Index，不再只是枚举注册表。

### 6.2 缺口分析流程

当前 analyze_gaps 的实际流程是：

1. 基于当前 Spec 生成 requirement text
2. 收集 capability snapshot
3. 调用 LLM 生成 gap report
4. 过滤 existing_tools 中的幻觉工具
5. 对 valuation 规格做强制纠偏
6. 落库 gap_report，并推动会话 stage 进入 gap-analysis

### 6.3 估值类规格的特殊约束

股票估值分析师仍然是当前最重度支持的试点场景，因此 gap analysis 对 valuation spec 有额外规则：

1. 精确估值区间不能由 LLM 自行估算，必须来自 Skill 或 Tool 结果。
2. gap report 与 fallback report 都会经过估值后置修正。
3. PE/PB/PEG 等方法级能力会被强制映射到真实工具覆盖，避免误报 blocking gaps。
4. tooling plan 的默认蓝图会根据规格动态推导，而不是使用固定老模板。

这部分设计已经是当前实现的重要行为差异，不能再只停留在通用描述层。

---

## 7. 工具需求草案设计

tooling plan 当前位于 gap analysis 和 build version 之间，承担两个作用：

1. 把 suggested_capabilities 变成具体的补齐蓝图
2. 为 Skill 工坊提供跳转参数和最小实现说明

页面上，用户可以在 gap step 中直接查看：

- 缺哪些能力
- 每个 draft tool 的输入输出
- 实现顺序
- 在能力未就绪前的 fallback 方案

当前它并不自动触发 Skill 生成，而是作为：

- 设计确认材料
- 技能工坊的输入草案
- build_version 前的补齐参考

这是当前设计和早期“缺口分析后直接补工具”的一个明显差异。

---

## 8. 版本构建设计

### 8.1 build_version 的当前职责

build_version 当前会同时生成以下内容：

1. version_id 和版本号
2. required_tools
3. required_capabilities
4. output_schema
5. evaluation_policy
6. prompt_template_ref
7. agent_metadata

然后保存为 AgentVersion，并把会话 stage 推到 building。

### 8.2 required_tools 的选择逻辑

当前 required_tools 不是纯粹相信 gap report，而是混合以下来源：

1. gap_report.existing_tools 中已确认的真实工具
2. 领域默认优先工具集
3. valuation spec 的专门工具偏好

其中 valuation spec 会优先包含：

- get_value_factor_bundle_tool
- get_stock_fundamentals_unified
- get_peer_comparison
- calculate_pb_relative_valuation
- calculate_peg_valuation
- get_growth_cashflow_factor_bundle_tool
- get_income_analysis
- get_cashflow_analysis
- get_balance_sheet_analysis
- get_stock_market_data_unified

### 8.3 Prompt 模板

当前 build_version 会自动创建关联 Prompt 模板，后续可通过：

- GET /versions/{version_id}/prompt
- PUT /versions/{version_id}/prompt

进行查看和编辑。

这意味着当前版本构建链路已经明确把“Prompt 审阅”视为工坊的一部分，而不是外部独立操作。

### 8.4 输出 schema 与评估策略

output_schema 和 evaluation_policy 当前已成为 AgentVersion 的正式组成部分，而不是运行时临时拼接字段。页面上也会直接展示：

- output_schema.properties
- evaluation_policy.dimensions

这部分设计仍然可以继续扩展，但作为版本记录已经存在。

---

## 9. 调试、评估、迭代与发布

### 9.1 调试

debug_version 当前支持用户显式指定：

- provider
- model
- temperature
- max_tokens
- backend_url
- api_key
- symbol
- market_type
- analysis_date
- user_goal
- prompt_overrides

返回结果会包含：

- report
- report_length
- output_field
- raw_result
- debug_prompt
- tool_trace
- metadata

因此，当前调试链路已经可以作为“发布前验证”和“问题定位”工具，而不只是一个简单执行按钮。

### 9.2 评估

evaluate_version 当前支持：

- evaluation_type
- sample_set_id
- user_feedback
- benchmark_outputs
- runtime_result

评估完成后：

1. 保存 AgentEvaluationReport
2. 当 decision=pass 且版本仍为 draft 时，自动将版本提升到 testing
3. 将关联 session 推进到 evaluating

### 9.3 迭代

iterate_version 当前会根据：

- 最新评估 issues
- 最新 recommendations
- 用户补充 feedback

自动拼一段新的 iterate_description，再重新 start_session，发起下一轮工坊会话。

这意味着迭代入口已经不是“用户重新描述一遍需求”，而是“从上一轮版本问题中自动生成下一轮起点”。

### 9.4 发布

publish_version 当前已经实现：

1. 仅 testing 状态版本可发布
2. 自动归档同一 Spec 下之前 active 的版本
3. 把当前版本切到 active
4. 同步 runtime agent config
5. 更新 Spec 的 current_version_id 和状态
6. 将关联 session 推进到 completed

当前尚未实现：

- 多人审批流
- 灰度发布策略
- 自动生产反馈回流

---

## 10. API 设计

前缀：/api/agent-workshop

### 10.1 会话相关

- POST /sessions/start
- POST /sessions/{session_id}/respond
- POST /sessions/{session_id}/preview-spec
- POST /sessions/{session_id}/analyze-gaps
- POST /sessions/{session_id}/generate-tooling-plan
- POST /sessions/{session_id}/build-version
- GET /sessions
- GET /sessions/{session_id}
- DELETE /sessions/{session_id}

### 10.2 规格相关

- GET /specs
- GET /specs/{spec_id}
- DELETE /specs/{spec_id}
- GET /specs/{spec_id}/sample-sets

### 10.3 版本相关

- GET /versions
- GET /versions/{version_id}
- POST /versions/{version_id}/publish
- GET /versions/{version_id}/prompt
- PUT /versions/{version_id}/prompt
- POST /versions/{version_id}/debug
- POST /versions/{version_id}/evaluate
- GET /versions/{version_id}/evaluations
- POST /versions/{version_id}/iterate

### 10.4 系统能力

- GET /capability-snapshot

---

## 11. 前端工作台设计

### 11.1 页面分工

当前前端分工和旧文档描述正好相反，已经需要纠正：

1. frontend/src/views/Workflow/AgentWorkshopManager.vue
   - 管理页
   - 展示规格、草稿、历史会话入口
   - 负责进入某个 Agent 的工作台

2. frontend/src/views/Workflow/AgentWorkshop.vue
   - 单 Agent 工作台
   - 负责五步流程：讨论、规格确认、缺口分析、版本构建、评估迭代

### 11.2 当前交互重点

当前前端最重要的设计变化有三点：

1. 单 Agent 单工作台：减少列表管理和工坊操作混杂。
2. 规格确认单独成步：先确认职责、输出和待确认项，再讨论缺口。
3. gap step 同时展示 gap_report 和 tooling_plan：让缺口判断与补齐方案并排可见。

### 11.3 结构化 IO 展示

由于 AgentSpec 的 inputs 和 outputs 已经支持结构化对象，前端会自动将其转换成可读文本展示，并在工具草案生成说明中复用这些输出字段。

这部分已经是当前实现的一部分，后续 UI 只会继续增强，不应再回退到“输出字段只支持字符串”的假设。

---

## 12. 关键实现补充

### 12.1 全量 LLM trace

当前 Agent 工坊会把关键阶段的 LLM 请求、响应和生成结果写入独立日志文件：

- logs/agent_workshop_llm_full.log

这已经成为排查规格收敛、缺口分析和版本调试问题的标准入口。

### 12.2 Capability Index 接入

当前 requirement clarification 和 gap analysis 已经开始使用能力索引召回，而不是完全依赖全量注册表扫描。这会直接影响：

- capability snapshot 的质量
- 缺口分析的候选能力上下文
- 规格中 deterministic-tool 类要求的真实性校验

### 12.3 数值可追溯策略

当前对于涉及数值输出的 Agent，系统会注入数值来源可追溯约束，减少 LLM 直接编造估值区间、打分或结论数值的风险。

### 12.4 估值类专门治理

股票估值分析师仍是当前最成熟的试点场景，相关特殊逻辑包括：

- 估值方法级工具强制映射
- gap report 后置修正
- tooling plan 动态推导
- runtime 估值追踪对 relative/PEG 工具的识别

这部分已经不再是临时试验逻辑，而是当前设计的一部分。

---

## 13. 当前已实现与仍待补齐的内容

### 13.1 已实现

当前已经稳定实现的能力包括：

1. 多轮规格澄清
2. 规格确认与 completeness/pending questions 机制
3. capability snapshot
4. gap analysis
5. tooling plan
6. AgentVersion 构建
7. Prompt 模板查看与更新
8. debug_version
9. evaluate_version
10. iterate_version
11. publish_version

### 13.2 尚未完成

当前仍属于后续扩展的内容包括：

1. 发布审批流
2. 灰度发布
3. 自动生产反馈回流
4. tooling plan 到 Skill 生成的全自动闭环
5. 更细粒度的版本 diff 和变更说明生成

---

## 14. 关键决策

### 14.1 不直接改内建 Agent

内建 Agent 保持稳定，新 Agent 始终先以 Spec 和 Version 的形式进入 testing，再决定是否发布为 active。

### 14.2 规格、缺口、版本、评估分层

当前实现已经验证，只有把这四层分开，工坊才不会在一次会话里把“要做什么”和“怎么实现”搅在一起。

### 14.3 Agent 工坊优先做设计闭环，不优先做自动补齐闭环

当前 Agent 工坊更强调：

- 明确需求
- 识别缺口
- 生成版本
- 调试评估

而不是把所有缺口都自动补齐完再继续。自动补齐仍然由 Skill 工坊承担，这是刻意保留的职责边界。

---

## 15. 预期收益

按当前实现，Agent 工坊已经在系统中提供三种确定性收益：

1. 新 Agent 的规格化生产能力
2. 版本化调试与评估能力
3. 从评估问题自动进入下一轮的迭代能力

对当前系统而言，它已经不只是“新建 Agent 的辅助页面”，而是在逐步形成一套真正的 Agent 生命周期工作台。
