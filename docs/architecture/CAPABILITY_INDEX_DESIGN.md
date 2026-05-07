# Capability Index 设计

## 背景

当前 Agent 生成与缺口分析流程主要依赖 ToolRegistry 的全量扫描、分类规则和提示词约束来识别“系统已有能力”。

这套方式存在三个问题：

1. 候选能力依赖固定截断和简单关键词匹配，后注册或描述较长的工具容易被遗漏。
2. Tool / MCP / Skill / external skill 的能力描述分散在不同来源中，缺少统一可检索视图。
3. LLM 在缺口分析阶段看到的只是有限的工具名列表，无法稳定理解某个工具到底覆盖哪些指标、边界和返回结构。

因此需要在注册表之上增加一层统一能力索引：

- 注册表：真值源，决定能力是否真实存在、是否可绑定、参数是否可执行。
- 向量库：召回层，按语义检索当前需求最相关的能力候选。
- 规则重排：控制业务域优先级、可绑定性、覆盖面与噪声过滤。
- Gap Analysis / Agent Workshop：基于召回后的候选能力做覆盖分析和缺口判定。

## 目标

1. 将 builtin tools、MCP tools、registry 中已加载的 skills、external_skills 文档统一索引到本地向量库。
2. 统一能力文档结构，使 Tool / MCP / Skill 的检索文本和可绑定信息一致。
3. Agent Workshop 在 requirement clarification 和 gap analysis 阶段优先通过语义检索召回候选能力，而不是全量扫描后硬截断。
4. 最终绑定仍然只依赖注册表中的真实 tool_id，不允许向量检索结果直接决定绑定。
5. 当 skills / external_skills 变化时，能力索引可在启动时同步，并在运行期通过热更新或懒同步刷新。

## 非目标

1. 不让向量库替代 ToolRegistry。
2. 不让 LLM 直接从语义结果中构造不存在的 tool_id。
3. 不在本期把所有 Agent Runtime 的工具选择逻辑全部改成语义检索，仅先接入 Agent Workshop 的规格澄清和缺口分析链路。

## 核心流程

### 1. 规格生成

Agent Workshop 先生成 Agent 规格，包括：

- 角色与职责
- 输入与输出
- 业务边界与非目标
- 成功标准
- preferred_methods

### 2. 能力召回

基于规格文本构造查询，调用 CapabilityIndexService：

- 先从统一能力索引中做语义召回 top-k
- 再结合规则重排，优先保留当前业务域最相关、且可绑定的能力

### 3. 覆盖分析

对召回结果判断：

- 已有能力可直接满足
- 已有能力可组合满足
- 仅能部分满足，需要 Prompt / 模板约束补齐
- 完全缺失，需要生成新 Skill / Tool

### 4. 缺口补齐

如果存在真正缺口，则进入 Skill 工坊生成新能力。新能力保存后：

- 注册到 ToolRegistry
- 同步写入 Capability Index

### 5. 最终绑定

最终 Agent 版本的 required_tools / default_tools 仍以 ToolRegistry 中存在的 tool_id 为准。

## 统一能力文档模型

CapabilityDocument 统一描述一个可检索能力，字段包括：

- capability_id：能力唯一标识
- registry_tool_id：若可绑定，对应注册表 tool_id
- source_type：builtin_tool / mcp_tool / skill / external_skill
- status：active / draft / disabled
- bindable：是否可直接绑定
- fc_enabled：是否允许 function calling
- category：fundamentals / market / technical / mcp / ...
- name / label / description
- when_to_use / when_not_to_use / returns / related_tools
- coverage_terms：从描述中提取的领域关键词，如 pe/pb/peg/peer_comparison
- retrieval_text：写入向量库的统一检索文本
- metadata：保留原始来源补充信息

## 索引策略

### 写入来源

1. ToolRegistry 中的全部 ToolMetadata
2. skills 集合中 enabled 的技能文档
3. external_skills 集合中 active / draft 的技能文档

说明：

- MCP tools 已在 ToolRegistry 中，因此会被统一纳入。
- 对已在 ToolRegistry 中存在的能力，数据库文档只用于补充描述和状态，不重复生成多个逻辑能力。

### 检索文本构成

retrieval_text 由以下字段拼接：

- tool_id / capability_id
- name / label
- description
- when_to_use
- when_not_to_use
- returns
- related_tools
- category / source_type / data_source
- coverage_terms

### 检索与重排

语义检索只负责召回，重排由业务层完成：

1. 优先 bindable=true 的能力
2. 优先与当前 domain 匹配的 category
3. 对 valuation 规格优先 coverage_terms 包含 pe/pb/peg/valuation/peer_comparison 的能力
4. 保留少量 draft / unbindable 能力作为上下文，但不进入最终 legal tool list

## Agent Workshop 接入方式

### Requirement Clarification

基于用户多轮输入构造 query，从 Capability Index 检索候选能力，生成 capability snapshot 作为系统现状上下文。

### Gap Analysis

基于最终 spec 构造 query，从 Capability Index 检索候选能力：

- legal tool list：只包含 bindable=true 的候选工具
- capability context：包含工具摘要、覆盖项、边界说明
- draft / unbindable 能力：仅作为背景参考，不进入 existing_tools 合法枚举

## 同步策略

### 启动同步

应用启动时，在 ToolRegistry、skills、external_skills 完成加载后重建 Capability Index。

### 运行期同步

以下场景触发增量或全量重建：

- 新建/导入 Skill
- Skill 工坊生成并热注册 external_skill
- Agent Workshop 查询前发现 fingerprint 变化

### 新鲜度校验

CapabilityIndexService 维护 fingerprint：

- registry ids + registry metadata 摘要
- enabled skills 摘要
- active/draft external_skills 摘要

若 fingerprint 变化，则在下一次查询前自动重建索引。

## 为什么不是只靠向量库

只靠向量库会有两个问题：

1. 无法保证召回结果真实可执行。
2. 无法直接决定最终绑定和参数注入。

因此必须保留：

- 向量库：相关性召回
- 注册表：真实性与绑定

## 与记忆系统的关系

Capability Index 需要明确区分三层：

1. Knowledge：文档型知识、说明文档、背景材料，解决“系统知道什么”。
2. Memory：Agent 历史经验、任务上下文、用户偏好，解决“系统记住了什么”。
3. Capability Index：系统当前可调用能力的统一检索视图，解决“系统现在能做什么”。

因此本设计不建议把 Capability Index 直接建模为普通 Agent memory，也不建议完全绕开现有向量基础设施单独再造一套向量访问层。

推荐原则：

- 复用现有 EmbeddingManager、VectorStoreManager 和 Qdrant 本地存储能力。
- Capability Index 使用独立 collection 和独立状态管理，不与 AgentMemory 混用。
- AgentMemory 仍只承接历史经验与上下文记忆，不承接系统能力目录。
- Financial knowledge / 文档知识仍由知识系统承接，不直接写入 Capability Index，除非被整理成可绑定或可检索的能力文档。

当前建议的分工是：

- memory collections：按 agent 或场景保存经验记忆。
- capability_registry collection：保存 Tool / MCP / Skill / external skill 的统一能力文档。
- capability_index_state collection：保存能力索引 fingerprint 与同步状态。

这样做的原因是：

1. 复用底层向量能力，避免重复建设 embedding / vector backend / persistence。
2. 避免把“经验记忆”与“系统能力目录”混成同一类检索对象，导致召回语义污染。
3. 让 Capability Index 的刷新、同步、重建策略保持可控，不受 Agent 记忆写入频率影响。
4. 让最终绑定仍然通过注册表闭环，而不是通过记忆结果或文档结果闭环。

结论：Capability Index 应当与现有记忆系统“共享底层向量基础设施”，但不应“并入现有记忆语义层”。

## MVP 实现范围

本期实现：

1. CapabilityDocument / CapabilitySearchHit 数据模型
2. CapabilityIndexService
3. startup 同步
4. Skill / external skill 热更新同步
5. Agent Workshop requirement clarification + gap analysis 接入 Capability Index

本期不做：

1. 全系统所有 Agent Runtime 的工具选择改造
2. 通用工作流引擎的统一 capability retrieval API
3. 前端能力检索管理界面
