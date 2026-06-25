# 统一记忆层设计 — 基于 mem0 的全系统记忆整合

## 📋 文档信息

| 项目 | 内容 |
|------|------|
| 版本 | v1.3 |
| 状态 | 设计与阶段性实现同步 |
| 日期 | 2026-04-08 |
| 目标 | 将系统中分散的语义记忆能力统一接入 mem0，并明确会话压缩、治理审核、运行状态与长期记忆的职责边界 |
| 前置文档 | [v4.0 Cognee 知识与记忆架构](../v4.0/cognee-knowledge-memory-concept.md)、[v3.0 智能助手](./intelligent-assistant.md)、[v3.0 Skill 生成系统](./skill-generation-system.md) |
## 9. 实施方案

### 9.1 总体实施原则

1. **先分层，再统一**
    - 先把“语义记忆”“会话压缩”“运行状态”三类职责拆清，再推进统一接入。
    - 不在第一阶段同时重构 Nanobot compact、mem0、成长记忆和旧版 agent memory。
2. **双写优先，单切换后置**
    - 新链路先双写或旁路写入，验证质量后再切主读路径。
    - 避免一次性把旧召回链路下线。
3. **优先改入口薄层，不先改深层核心**
    - 先改 router / service / bridge 层的接线点。
    - 暂不在第一阶段重写 `FinancialSituationMemory`、Nanobot compact 算法或 worker 主循环。
4. **每阶段必须可回滚**
    - 每个阶段都保留 feature flag 或旧路径兜底。
    - 回滚成本必须控制在“关闭开关/恢复旧读路径”级别。

### 9.2 阶段划分总览

| 阶段 | 目标 | 主改动面 | 结果 |
|------|------|----------|------|
| Phase 0 | 统一概念边界 | 文档、命名、观测 | 不再把状态缓存当记忆系统 |
| Phase 1 | 稳定 mem0 作为语义底座 | `core/memory/service.py` 与现有写入点 | 形成统一 store/recall 入口 |
| Phase 2 | 成长记忆接入治理桥接 | `workflow_growth_service.py` / `workflow_growth.py` | 审核通过后同步 mem0 |
| Phase 3 | 智能助手与 Nanobot 接入 | assistant prompt 构建、Nanobot 桥接 | L5/L6 记忆开始被消费 |
| Phase 4 | 旧版 agent memory 迁移 | `memory_provider.py` / `FinancialSituationMemory` | 收敛向量记忆实现 |
| Phase 5 | 运行状态剥离命名 | `memory_state_manager.py` 调用点 | 消除“状态=记忆”混乱 |

### 9.2.1 当前已落地状态（2026-04-08）

- 已完成：成长记忆 `approve -> mem0` 桥接，且桥接失败不影响审批成功。
- 已完成：L4 项目长期记忆最小闭环，当前通过 `ProjectMemoryService` 与智能助手 prompt 注入打通“写入 -> 读取 -> 注入”。
- 已完成：L4 首批默认规则 seed，当前默认集已覆盖全局禁投顾口径、金融领域边界、复杂副作用操作确认、实时数据优先、回答结构与个股分析模板。
- 已完成：Agent Builder 治理请求已可前置注入 L4 项目长期记忆块，再叠加 Agent Workshop governance guidance，避免版本迭代和发布判断脱离稳定项目规则。
- 已完成：Agent Workshop 在创建版本 Prompt Template 时，会同步注入 L4 项目长期记忆块到 system_prompt 与 constraints，使生成出的版本模板天然继承稳定项目规则、输出约束与研究模板。
- 已完成：Agent Workshop 在发布版本前会重新校验 Prompt Template 对当前 L4 项目长期记忆的绑定状态；若模板缺失最新项目规则绑定，则拒绝发布，避免旧模板绕过稳定治理约束。
- 已完成：Agent Workshop 在 production-review 时会校验运行时 debug_prompt.system_prompt 是否真实包含当前 L4 项目长期记忆；若缺少绑定或缺少 system_prompt 证据，则该次评估不能作为正式发布依据。
- 已完成：当 production-review 启用 nanobot-assisted evidence workers 时，PromptEvidenceWorker 也会显式接收 `project_memory_binding` 上下文，参与核验当前运行时 prompt 是否真实带上 L4 项目长期记忆。
- 已完成：`MemoryService` 支持 `metadata_filters`，单 scope 时尽量下推 exact filter，多 scope 时走客户端二次过滤。
- 已完成：智能助手按当前 thread 标题、report_refs 中的 `symbol` 收窄 mem0 召回。
- 已完成：Skill 生成按 `category + data_source` 过滤同类 `skill_lesson`，缺省时回退到 `tool_id`。
- 已完成：Nanobot 本地 compact 成功后 best-effort 镜像到 mem0，并保留 `MEMORY.md` / `HISTORY.md` 为主运行时记忆来源。
- 已完成：Nanobot `thread_context` 已透传到 runtime，compact 镜像 metadata 已补 `workflow_id`、`spec_id`、`symbol`。
- 已完成：旧版 `MemoryProvider` 已新增 mem0 compat 层，统一通过 `MemoryService` 读写 `agent_experience`，不再在 compat 层内回退 `FinancialSituationMemory`。
- 已完成：`tradingagents/graph/trading_graph.py` 已不再直接 new `FinancialSituationMemory`，而是统一通过 `MemoryProvider` 获取各角色 memory。
- 已完成：`core/workflow/builder.py` 中 `LegacyDependencyProvider` 也已改为通过 `MemoryProvider` 获取 memory，不再单独直连旧 `FinancialSituationMemory`。
- 已完成：`core/memory/memory_manager.py` 已新增面向 v2 workflow 的 mem0 compat 层，`MemoryManager.get_agent_memory(agent_id)` 现在会优先返回 `Mem0AgentMemory`，让 `ResearcherAgent.search_memories()` 统一先读写 mem0；若需要完整旧实现，只能显式关闭 `MEMORY_USE_MEM0_COMPAT`。
- 已完成：position_analysis_v2 的真实运行时消费链路验证；`pa_fundamental_v2`、`pa_risk_v2`、`pa_technical_v2` 已确认可通过 `MemoryManager -> Mem0AgentMemory` 直接命中已迁入 mem0 的历史经验。
- 尚未完成：旧版 `FinancialSituationMemory` 的彻底退场、其余未迁 legacy agent 的数据补迁/退场决策，以及 `memory_state_manager` 命名剥离。

### 9.3 Phase 0：概念收口与观测准备

**目标**：在不改业务行为的前提下，把命名、边界和观测先理顺。

**代码入口**：

- `app/services/memory_state_manager.py`
- `docs/design/v3.0/unified-memory-layer-mem0.md`
- 所有引用 `get_memory_state_manager()` 的服务与 worker

**实施内容**：

- 文档中明确 L1-L7 七层分层。
- 在代码注释、后续 PR 命名和设计说明中，把 `memory_state_manager` 明确定义为运行状态层。
- 为 mem0 写入/召回、成长记忆 approve、Nanobot compact 成功率补日志与指标埋点。

**本阶段不做**：

- 不改 `memory_state_manager.py` 文件名。
- 不改对外 API。
- 不切换任何召回主路径。

**验证点**：

- 团队对“哪些属于语义记忆，哪些不属于”达成统一口径。
- 关键路径已有足够日志支持后续迁移观察。

**回滚策略**：

- 本阶段主要是文档与埋点，无需业务回滚。

### 9.4 Phase 1：固定 mem0 统一入口

**目标**：确保所有新的语义记忆接入都通过 `MemoryService`，不再新增直连向量库实现。

**代码入口**：

- `core/memory/service.py`
- `app/routers/memory.py`
- 未来新增的语义记忆写入点

**实施内容**：

- 固定 `MemoryService.store()` / `recall()` / `recall_formatted()` 为唯一标准接口。
- 对 scope、user_id、agent_id、session_id 的传递做统一约束。
- 为失败降级补统一日志格式，确保 mem0 不可用时主流程不阻塞。

**本阶段不做**：

- 不改旧版 `FinancialSituationMemory` 实现。
- 不让 Nanobot 直接依赖 mem0 才能运行。

**验证点**：

- mem0 不可用时，调用方收到空结果或降级结果，不影响主链路。
- 统一接口能稳定覆盖 conversation / user_preference / analysis_insight 等 scope。

**回滚策略**：

- 通过 `MEM0_ENABLED` 或调用方开关关闭 mem0。

### 9.5 Phase 2：成长记忆治理桥接

**目标**：把成长记忆明确为治理层，并在 approve 后同步到 mem0。

**代码入口**：

- `app/services/workflow_growth_service.py`
- `app/routers/workflow_growth.py`

**实施内容**：

- 在 `approve_memory_item()` 后增加桥接写入：把已批准记忆转换为 mem0 的 `agent_experience` 或 `analysis_insight`。
- 补充桥接元数据：`source_id`、`scope`、`review_level`、`workflow_id`、`symbol/object_key`。
- 保留 Mongo 审核表作为审批台账和审计源。

**本阶段不做**：

- 不直接让 `list_memory_items()` 改为读 mem0。
- 不删除 `agent_memory_items` 集合。

**验证点**：

- 同一条成长记忆只有在 approve 后才会进入 mem0。
- reject/pending 不会污染长期语义记忆。
- mem0 桥接失败不影响审批结果，但会记录可追踪错误。

**当前实现状态（2026-04-08）**：

- 已落地 `approve_memory_item()` 后的 best-effort mem0 桥接。
- 已落地 scope 映射与桥接 metadata：`workflow_id`、`object_key`、`symbol`、`growth_scope`、`review_level` 等。
- 已通过定向回归覆盖 approve 成功、bridge 成功、bridge 失败不影响审批三类场景。

**回滚策略**：

- 关闭 approve 后双写逻辑，Mongo 审核流继续独立工作。

### 9.6 Phase 3：智能助手与 Nanobot 接入

**目标**：让 mem0 成为跨会话语义召回来源，但不接管 Nanobot compact。

**代码入口**：

- 智能助手 prompt 构建入口
- `core/embedded_nanobot/runtime.py`
- `core/embedded_nanobot/agent/memory.py`
- `core/embedded_nanobot/agent/context.py`

**实施内容**：

- 在智能助手 prompt 构建前调用 `memory_svc.recall_formatted()` 注入用户偏好与历史洞察。
- 在 Nanobot 本地 consolidation 成功后，异步提取稳定洞察并桥接写入 mem0。
- 明确只桥接长期有效的项目规则、偏好与经验，不桥接短期任务痕迹。

**本阶段不做**：

- 不把 `MEMORY.md` / `HISTORY.md` 删除或降级。
- 不把 `maybe_consolidate_by_tokens()` 替换成 mem0 召回逻辑。

**验证点**：

- mem0 不可用时，Nanobot 仍能依靠本地 compact 正常运行。
- 同一用户跨线程可召回稳定偏好或历史经验。
- 本地 compact 与 mem0 双链路不会重复注入明显冲突内容。

**当前实现状态（2026-04-08）**：

- 已落地智能助手对 `analysis_insight` / `trade_pattern` 的 `symbol` 精确过滤。
- 已落地智能助手从 thread 标题、report_refs 回退提取 `symbol`。
- 已落地 Skill 生成对 `skill_lesson` 的 `category + data_source` 过滤。
- 已落地 Nanobot compact 成功后的 best-effort mem0 镜像。
- 已落地 Nanobot `thread_context -> runtime session metadata -> mem0 metadata` 的透传链路，当前已覆盖 `workflow_id`、`spec_id`、`symbol`、`object_type`、`object_key`。
- 已落地 Agent Workshop 版本模板构建阶段的 L4 注入：当前会拉取 `project_rule`、`governance_constraint`、`analysis_output_constraint`、`research_template`，并把稳定项目约束固化进模板内容。
- 尚未完成：跨线程召回质量的端到端评估，以及 `object_key` 进一步向更多非股票业务对象扩展。

**回滚策略**：

- 关闭 Nanobot 到 mem0 的异步镜像写入。
- 保留本地 `MEMORY.md` / `HISTORY.md` 作为唯一运行时记忆来源。

### 9.7 Phase 4：旧版 Agent Memory 迁移

**目标**：逐步收敛旧版向量经验记忆到 mem0，当前环境优先处理已确认非空的 Qdrant `memory_*` 集合，并保留 Chroma 兼容迁移能力。

**代码入口**：

- `tradingagents/core/engine/memory_provider.py`
- `core/memory/memory_manager.py`
- `tradingagents/agents/utils/memory.py`
- `tradingagents/graph/trading_graph.py`
- `core/workflow/builder.py`

**实施内容**：

- 新增 compat/adapter 层，让 `MemoryProvider` 优先通过 `MemoryService` 获取语义记忆。
- 旧版 `FinancialSituationMemory` 先保留读能力，逐步降为兼容层。
- 对历史数据做离线迁移脚本，把旧版 Qdrant/Chroma 经验导入 mem0。

**当前实现状态（2026-04-08）**：

- 已落地 `Mem0CompatMemory`，对外继续兼容旧接口 `add_situations()` / `get_memories()`。
- 已落地 `MemoryProvider` 默认优先返回 compat 包装器，可通过 `memory_use_mem0_compat` 开关回退旧实现。
- 已落地 mem0 切换控制：当前主路径固定为 mem0-only；compat 包装器内部的 legacy fallback 分支已移除。若需要完整旧实现，只能通过 `memory_use_mem0_compat=false` 或 `MEMORY_USE_MEM0_COMPAT=false` 整体切回 legacy memory。
- 已落地 compat 观测日志：`Mem0CompatMemory` 与 `Mem0AgentMemory` 现在会显式记录 mem0 命中、mem0 空召回与 mem0 写入/召回失败原因，便于后续观察主路径稳定性。
- 已落地旧 graph 主路径收口：`tradingagents/graph/trading_graph.py` 已改为通过 `MemoryProvider` 初始化 `bull/bear/trader/invest_judge/risk_manager` memory。
- 已落地 legacy workflow builder 收口：`core/workflow/builder.py` 中 `LegacyDependencyProvider` 已改为通过 `MemoryProvider` 初始化 memory。
- 已落地 v2 workflow runtime 收口：`core/workflow/builder.py` 初始化的 `MemoryManager` 现在也会优先返回 `Mem0AgentMemory`，不再只读旧 Qdrant `AgentMemory`。
- 已落地 legacy 离线迁移脚本：`app/scripts/migrate_legacy_agent_memory_to_mem0.py`，支持 `auto/qdrant/chroma` 三种模式、dry-run、按 collection 迁移、重复记录跳过与迁移 metadata 标注。
- 已确认当前环境真实非空 legacy 经验数据首先位于本地 Qdrant `data/qdrant` 下的 `memory_*` collections，Chroma 路径保留为兼容输入源而非当前主数据面。
- 已完成当前环境非空 Qdrant legacy collections 的正式迁移：共覆盖 7 个非空 `memory_*` collections，汇总结果为 `seen=179 migrated=178 skipped_existing=1 errors=0 dry_run=False`；其中 `skipped_existing=1` 来自迁移前的小批量写入验证样本。
- 已完成默认全量 dry-run 复检：结果为 `seen=179 migrated=0 skipped_existing=179 errors=0 dry_run=True`，且本地 Qdrant 盘点结果为 `remaining_non_empty=[]`，说明当前工作区已确认不存在剩余未迁的非空 legacy collections。
- 已修复迁移链路中的 mem0 假成功问题：在 `infer=False` 直写模式下，迁移消息不能使用 `role=system`，否则会被 mem0 SDK 跳过；当前脚本已统一改为使用可写入的非 `system` role。
- 已补齐旧 graph compat 写入语义：`Mem0CompatMemory.add_situations()` 现已与迁移/运行时 compat 保持一致，统一使用可写入的 `user` role 并显式 `infer=False`，避免旧图反思链路再次出现“表面成功、实际未稳定落库”的隐患。
- 已完成 alias 与真实消费链路抽查：`bull_memory` / `bear_memory` 已通过 v2 alias 命中 `bull_researcher_v2` / `bear_researcher_v2` 的迁移数据；`pa_fundamental_v2` / `pa_risk_v2` / `pa_technical_v2` 已通过 `MemoryManager -> Mem0AgentMemory` 命中 mem0 中的历史经验。
- 已确认当前工作区中 `trader_v2`、`research_manager_v2`、`risk_manager_v2` 尚无对应迁移数据，因此 `trader_memory` / `invest_judge_memory` / `risk_manager_memory` 当前读空仍属预期行为。
- 已完成 `TraderAgent` 历史记忆读写补齐：`_get_historical_trades()` 现可优先读取 `search_memories()` / mem0 compat，并兼容旧 `get_memories()`；`_save_to_memory()` 现可优先写入 `add_memory()` / mem0 compat，并兼容旧 `add_situations()`。这意味着 `trader_v2` 运行时已经具备历史交易经验的读写闭环，只是当前工作区尚无可回放的迁移历史样本。
- 已完成 `ManagerAgent` 历史记忆读写补齐：构造函数现在支持 memory 注入，`execute()` 会在生成用户提示词前把历史管理经验并入 `debate_summary`，并在决策完成后优先写回 `add_memory()` / mem0 compat，同时兼容旧 `add_situations()`。这意味着 `research_manager_v2` / `risk_manager_v2` 的运行时通路已经具备历史经验读写闭环。
- 已完成 manager 真实运行时命中验证：通过隔离 validation user 的受控样本脚本 `scripts/validate_manager_memory_runtime.py`，已确认 `research_manager_v2` 与 `risk_manager_v2` 都会在第二次执行时把 mem0 召回结果真实注入用户 prompt，验证完成后样本已自动清理，不会污染现有长期记忆。
- 已顺手修复 `risk_manager_v2` 的既有运行时 bug：当模板系统未返回系统提示词时，原实现会在 `len(prompt)` 处对 `None` 崩溃；现在已稳定回退默认系统提示词，因此 `risk_manager_v2` 的真实验证链路也已打通。
- 已确认 manager 历史真实来源并非仅限 legacy `memory_*` collections：当前工作区在 `data/analysis_results/**/reports/research_team_decision.md` 与 `data/analysis_results/**/reports/risk_management_decision.md` 中持久化了研究经理/风险经理的最终决策文本，且可作为稳定补迁源；`data/progress_analysis_*.json` 与 `data/temp/processing/progress_analysis_*.json` 可作为次级补充源。
- 已新增独立补迁脚本 `app/scripts/migrate_historical_manager_reports_to_mem0.py`，按 `analysis-results/progress-json/auto` 三种来源模式扫描历史报告并写入 mem0，统一补充 `ticker`、`symbol`、`object_key`、`analysis_date`、`source_file`、`target_agent_id` 等 metadata，避免与旧 Qdrant/Chroma 向量迁移脚本混用。
- 已完成当前工作区 manager 历史报告的正式补迁：`research_manager_v2` 与 `risk_manager_v2` 各补迁 81 条，共 `seen=162 migrated=162 skipped_existing=0 errors=0`；幂等复跑结果为 `seen=162 migrated=0 skipped_existing=162 errors=0`，说明当前这批历史报告已稳定进入 mem0。
- 已完成补迁后的读侧抽查：当前 `historical_manager_report_migration` 来源下，`research_manager_v2` 与 `risk_manager_v2` 在 mem0 中各可查询到 81 条历史经验，说明这批报告型历史数据不只是“写入成功”，也已经满足后续运行时召回条件。
- 当前退场状态：compat 包装器内部的 legacy fallback 已删除，默认运行固定使用 mem0-only；只有显式关闭 `memory_use_mem0_compat` / `MEMORY_USE_MEM0_COMPAT` 才会整体回到旧实现。
- 当前退场策略：主路径继续以 mem0-only 观察稳定性；legacy memory 仅保留为显式开关下的整体回退实现，不再保留“局部失败再 fallback”的中间态。
- 尚未完成：其余未迁 legacy agent 的数据补迁或退场决策，以及 legacy memory 类本体的进一步瘦身/删除。

**本阶段不做**：

- 不在第一版就删除 `FinancialSituationMemory`。
- 不在无迁移验证前切断旧图分析链路。

**验证点**：

- 旧版 agent 在启用 compat 层后输出质量不下降。
- 迁移后经验召回不出现明显缺失或重复爆炸。
- 报告型历史补迁后，manager 运行时能够按 `ticker` 过滤稳定召回历史研究/风控决策，而不是仅依赖受控验证样本。

**回滚策略**：

- 将 `MemoryProvider` 切回旧实现，compat 层旁路关闭。

### 9.8 Phase 5：运行状态层剥离命名

**目标**：从语言和架构上把“任务状态”彻底移出“记忆系统”范畴。

**代码入口**：

- `app/services/memory_state_manager.py`
- `app/routers/analysis.py`
- `app/services/unified_analysis_service.py`
- `app/services/simple_analysis_service.py`
- `app/services/task_analysis_service.py`
- `app/services/thread_worker.py`
- `app/worker/analysis_worker.py`

**实施内容**：

- 将 `MemoryStateManager` 更名为更准确的 `TaskStateManager` 或 `AnalysisTaskStateManager`。
- 保留兼容导出一段时间，逐步替换调用点。
- 更新日志、文档、问题排查手册中的旧术语。

**本阶段不做**：

- 不改变任务状态数据结构和 websocket 协议。

**验证点**：

- 调用点迁移后功能不变。
- 团队讨论中不再把任务状态缓存误认为长期记忆能力。

**回滚策略**：

- 保留旧名称兼容别名，必要时回退 import 路径。
- **RAG**：原文与证据召回层
- **Cognee**：关系、变化、长期记忆与事件链推理层

本设计中 mem0 的定位是 **Cognee 之下的通用记忆基础设施**，两者互补：

| 层级 | 职责 | 技术选型 |
|------|------|----------|
| 业务真相 | 结构化数据、配置、状态 | MongoDB（不变） |
| 原文证据 | 文档片段检索 | RAG / FinancialKnowledgeManager（不变） |
| **通用记忆** | **事实提取、语义检索、冲突解决、多级记忆** | **mem0（新增）** |
| 关系推理 | 实体关系图谱、演化跟踪 | Cognee（v4.0 规划，可选） |

mem0 解决的是 "**记住了什么、怎么检索**" 的问题；
Cognee 解决的是 "**实体之间的关系如何变化**" 的问题。

---

## 2. 设计目标

### 2.1 核心目标

1. **一个接口存/取所有记忆** — 智能助手、Skill 生成、Agent 工作流、成长系统统一调用 mem0
2. **智能提取而非原文存储** — mem0 内置 LLM 自动从对话/结论中提取事实
3. **跨子系统记忆互通** — 助手能召回 Agent 经验，Skill 能共享教训
4. **渐进式迁移** — 现有系统逐步接入，不一次性替换

### 2.2 非目标

- 不替代 MongoDB 作为业务真相源
- 不替代 RAG 原文检索
- 不替代 Cognee 的关系图谱推理（v4.0 可以在 mem0 之上叠加 Cognee）
- 不替代 `assistant_threads` / `assistant_thread_messages` 的完整对话存储
- 不替代 Embedded Nanobot 的上下文裁剪与本地审计归档机制
- 不把 `memory_state_manager` 这类运行状态缓存视为语义记忆的一部分

### 2.3 七层记忆分层与职责边界

为了避免继续把不同职责混在一起，本设计将当前系统拆成 7 层：

| 层 | 名称 | 目标 | 当前承载 | 是否并入 mem0 |
|---|---|---|---|---|
| L1 | 运行时工作记忆 | 支撑当前回合推理与工具调用 | Runtime 当前消息、工具结果 | 否 |
| L2 | 会话历史层 | 支撑当前线程连续对话与恢复 | Nanobot Session / thread messages | 否 |
| L3 | 会话压缩层 | 在 token 受限时压缩旧消息并保留审计 | Nanobot `MEMORY.md` / `HISTORY.md` | 否 |
| L4 | 项目长期记忆层 | 跨线程共享项目规则、稳定上下文 | 项目级长期摘要、知识索引 | 部分，按需镜像 |
| L5 | 用户语义记忆层 | 跨会话召回用户偏好、长期事实 | mem0 `conversation` / `user_preference` | 是 |
| L6 | Agent/领域经验层 | 沉淀分析结论、成长经验、技能教训 | 成长记忆、skill lesson、agent experience、旧版 agent memory | 是，治理后统一 |
| L7 | 运行状态层 | 驱动 UI 进度、任务控制、实时状态 | `memory_state_manager` | 否 |

设计结论：

- mem0 统一的是 L5/L6 这两类“语义记忆”。
- Nanobot 本地记忆保留在 L2/L3，继续承担上下文裁剪、恢复与审计职责。
- `memory_state_manager` 属于 L7 运行状态层，后续应从“记忆系统”命名中剥离。

### 2.4 目标架构

整合后的目标不是“一套存储解决所有问题”，而是四个协作子系统：

1. **Nanobot Runtime Memory**
    - 负责 L1/L2/L3
    - 管理当前线程消息、token budget、`MEMORY.md` / `HISTORY.md`
2. **Semantic Memory Platform (mem0)**
    - 负责 L5/L6
    - 管理长期事实、偏好、经验与语义召回
3. **Governance Memory**
    - 负责成长记忆的审核、批准、拒绝与可追溯性
    - 批准后再同步到 mem0，而不是直接替代审核流
4. **Runtime State**
    - 负责任务状态、进度、WebSocket 推送
    - 不参与长期语义召回

---

## 3. mem0 技术选型分析

### 3.1 mem0 核心能力

| 能力 | 说明 | 对我们的价值 |
|------|------|-------------|
| **多级记忆** | User / Session / Agent 三层 | 天然映射我们的用户/会话/Agent |
| **智能事实提取** | LLM 自动从对话中提取关键事实 | 不存原文，只存洞察 |
| **冲突解决** | 新旧记忆矛盾时自动合并/更新 | 用户偏好变化自动更新 |
| **语义检索** | 向量相似度 + 可选 Reranker | 按语义而非关键词召回 |
| **Graph Memory** | 实体关系图谱（可选，需 Neo4j） | 为 v4.0 Cognee 铺路 |
| **自定义提取 prompt** | 可针对金融领域定制 | 定制投研事实提取规则 |
| **异步支持** | async add / search | 与我们的 FastAPI 异步架构匹配 |

### 3.2 基础设施复用

| 组件 | mem0 需要 | 我们已有 | 对接方式 |
|------|----------|---------|---------|
| 向量库 | Qdrant / ChromaDB / MongoDB 等 | Qdrant (`core/memory/`) | 直接复用现有 Qdrant 实例 |
| LLM | OpenAI / DeepSeek / Ollama 等 | DeepSeek + 多 Provider | 通过 OpenAI 兼容接口对接 |
| Embedding | OpenAI / HuggingFace / Ollama 等 | EmbeddingManager (多 Provider) | 配置 mem0 使用相同的 Embedding |
| 历史存储 | SQLite（默认）| MongoDB | 可配置使用 MongoDB 或保持默认 |

### 3.3 部署方式

推荐 **自托管开源版**（`pip install mem0ai`），原因：

- 数据不出境，符合金融数据合规要求
- 复用现有 Qdrant，无额外基础设施成本
- 可自定义提取 prompt，针对 A 股/金融领域优化
- Apache 2.0 许可证，无商业限制

### 3.4 为什么 mem0 不直接替代 Nanobot 本地记忆

Embedded Nanobot 当前的本地 `MEMORY.md` / `HISTORY.md` 不只是“长期记住一些事实”，还承担以下职责：

1. 按 token budget 压缩会话，决定从哪条消息开始裁剪。
2. 维护 `last_consolidated` 边界，保证下一轮 prompt 仍然是合法消息链。
3. 在压缩失败时降级为 RAW archive，保证审计与恢复能力。
4. 直接参与 system prompt 组装，提供当前 workspace 的长期摘要。

这些职责属于 L2/L3，会话压缩与可恢复性优先于语义召回。

因此本设计明确：

- 不让 mem0 反向接管 Nanobot 的上下文裁剪链路。
- 如果需要跨线程共享 Nanobot 形成的长期洞察，只做“压缩成功后的异步镜像写入 mem0”。
- Nanobot 运行时在 mem0 不可用时仍必须能独立工作。

---

## 4. 记忆分类与 scope 设计

### 4.1 记忆 scope 定义

为所有记忆统一定义 scope（通过 mem0 的 metadata 实现）：

| scope | 含义 | 写入来源 | 召回场景 |
|-------|------|---------|---------|
| `conversation` | 对话中提取的事实/偏好 | 智能助手每轮对话后 | 助手对话前、Agent 执行前 |
| `user_preference` | 用户长期偏好（投资风格、风险等级等）| 对话提取 + 画像同步 | 助手 system prompt、分析配置 |
| `analysis_insight` | 分析结论/观点 | 工作流完成后 | 助手回答相关问题时、二次分析时 |
| `skill_lesson` | Skill 生成教训 | 管线迭代失败后 | Skill 生成/修复时 |
| `agent_experience` | Agent 投研经验 | 工作流完成后 Agent 沉淀 | Agent 执行前召回 |
| `trade_pattern` | 交易行为模式/纪律偏差 | 复盘完成后 | 助手讨论交易时、制定计划时 |

### 4.2 mem0 多级记忆映射

```
mem0 层级          我们的映射
──────────────     ────────────────────────────────
user_id           → 系统 user_id（跨会话持久）
session_id        → thread_id / session_id（单次会话内）
agent_id          → agent 类型 ID（如 "assistant", "bull_researcher", "skill_generator"）
metadata.scope    → 上述 6 种 scope
metadata.symbol   → 股票代码（可选）
metadata.task_id  → 关联任务 ID（可选）
```

---

## 5. 系统架构

### 5.1 整体架构

```
┌────────────────────────────────────────────────────────────────────┐
│                         应用层 (调用方)                              │
│                                                                    │
│  智能助手    Skill 生成    工作流 Agent    成长系统    Gateway IM    │
│     │           │             │             │            │         │
│     └───────────┴─────────────┴─────────────┴────────────┘         │
│                               │                                    │
│                    ┌──────────▼──────────┐                         │
│                    │  MemoryService      │  core/memory/service.py  │
│                    │  (适配层/门面)       │                         │
│                    └──────────┬──────────┘                         │
│                               │                                    │
├───────────────────────────────┼────────────────────────────────────┤
│                    ┌──────────▼──────────┐                         │
│                    │      mem0 SDK       │  pip install mem0ai     │
│                    │  Memory.from_config │                         │
│                    └──┬──────────────┬───┘                         │
│                       │              │                              │
│              ┌────────▼───┐  ┌───────▼────────┐                    │
│              │  Qdrant    │  │  DeepSeek LLM  │                    │
│              │  (向量库)   │  │  (事实提取)     │                    │
│              └────────────┘  └────────────────┘                    │
│                                                                    │
│  不变的层:  MongoDB (业务真相) │ RAG (原文检索) │ Cognee (v4.0 图谱)  │
└────────────────────────────────────────────────────────────────────┘
```

### 5.2 MemoryService 适配层

`core/memory/service.py` 作为 mem0 之上的薄包装，提供：

1. **初始化** — 从系统配置（MongoDB `system_configs`）读取 mem0 config
2. **存储** — 按 scope 标记元数据
3. **召回** — 按 scope + user_id + agent_id 过滤检索
4. **批量** — 支持批量写入（如 Skill 教训）
5. **降级** — mem0 不可用时静默降级，不阻塞主流程

```python
class MemoryService:
    """统一记忆服务 — mem0 适配层"""

    async def store(
        self,
        messages: list[dict],
        *,
        user_id: str = "",
        agent_id: str = "",
        session_id: str = "",
        scope: str = "conversation",
        metadata: dict | None = None,
    ) -> list[str]:
        """存储记忆（mem0 自动提取事实）"""

    async def recall(
        self,
        query: str,
        *,
        user_id: str = "",
        agent_id: str = "",
        scopes: list[str] | None = None,
        limit: int = 5,
    ) -> list[MemoryItem]:
        """语义召回相关记忆"""

    async def recall_formatted(
        self,
        query: str,
        *,
        user_id: str = "",
        agent_id: str = "",
        scopes: list[str] | None = None,
        limit: int = 5,
        max_chars: int = 1500,
    ) -> str:
        """召回并格式化为可注入 prompt 的文本"""

    async def get_user_summary(
        self,
        user_id: str,
        scopes: list[str] | None = None,
    ) -> str:
        """获取用户记忆摘要"""
```

### 5.3 MemoryItem 数据模型

```python
class MemoryItem(BaseModel):
    """mem0 返回的单条记忆"""
    id: str
    memory: str              # mem0 提取的事实文本
    user_id: str = ""
    agent_id: str = ""
    scope: str = ""
    score: float = 0.0       # 语义相似度分
    metadata: dict = {}
    created_at: str = ""
    updated_at: str = ""
```

---

## 6. 各子系统接入方案

### 6.1 智能助手

**写入时机**：每轮对话完成后

```python
# app/services/intelligent_assistant_service.py

# 对话结束后，异步存储记忆
async def _store_conversation_memory(db, user_id, thread_id, user_msg, assistant_msg, tools_used):
    memory_svc = get_memory_service()
    messages = [
        {"role": "user", "content": user_msg},
        {"role": "assistant", "content": assistant_msg},
    ]
    await memory_svc.store(
        messages,
        user_id=user_id,
        agent_id="assistant",
        session_id=thread_id,
        scope="conversation",
        metadata={"tools_used": tools_used},
    )
```

**召回时机**：构建 system prompt 时

```python
# 在 _build_system_prompt 或 chat 入口处
relevant_memories = await memory_svc.recall_formatted(
    query=user_message,
    user_id=user_id,
    scopes=["conversation", "user_preference", "analysis_insight", "trade_pattern"],
    limit=8,
    max_chars=2000,
)
# 注入到 system prompt 的【你对该用户的了解】段落
```

**与现有系统关系**：
- `assistant_threads` / `assistant_thread_messages` 继续负责完整对话存储（原文历史）
- `assistant_user_profiles` 的核心字段保留，但长期偏好同步写入 mem0
- mem0 负责**跨会话的事实记忆**，thread 负责**单会话的完整消息**
- Nanobot 本地 `MEMORY.md` / `HISTORY.md` 继续负责**会话压缩后的工作摘要**，不被 mem0 替代

### 6.2 Skill 生成系统

**写入时机**：管线每轮迭代产生 reflection 后 + 最终失败/成功后

```python
# core/tools/external/iteration_controller.py

# 每轮反思后存教训
if reflection and reflection.root_cause:
    await memory_svc.store(
        [{"role": "system", "content": f"Skill {spec.tool_id} 生成失败: {reflection.root_cause}"}],
        agent_id="skill_generator",
        scope="skill_lesson",
        metadata={
            "tool_id": spec.tool_id,
            "category": spec.category,
            "data_source": spec.data_source,
            "stage": stage,
        },
    )
```

**召回时机**：代码生成前

```python
# code_generator.py — 构建 prompt 前

# 召回同类 Skill 的历史教训
lessons = await memory_svc.recall_formatted(
    query=f"{spec.description} {spec.data_source} {spec.category}",
    agent_id="skill_generator",
    scopes=["skill_lesson"],
    limit=10,
    max_chars=2000,
)
# 注入到 system prompt 的【历史教训】段落
```

**关键改进**：教训不再局限于单个 session 的 `pipeline_history`，而是**跨所有 Skill 共享**。
生成"获取东方财富新闻"的 Skill 时，能召回之前生成"获取新浪新闻"时踩过的坑。

### 6.3 工作流 Agent

**写入时机**：工作流完成后

```python
# app/services/unified_analysis_service.py — 任务完成回调

# 提取分析结论作为记忆
await memory_svc.store(
    [{"role": "assistant", "content": conclusion_text}],
    user_id=user_id,
    agent_id=agent_id,  # e.g. "bull_researcher"
    scope="analysis_insight",
    metadata={"symbol": symbol, "task_id": task_id},
)
```

**召回时机**：Agent 执行前（替换当前的 growth_memory_recall 注入）

```python
# core/agents/base.py — 渲染 prompt 时

# 召回该 Agent 的历史经验 + 该用户的分析记忆
memories = await memory_svc.recall_formatted(
    query=current_task_description,
    user_id=user_id,
    agent_id=agent_id,
    scopes=["agent_experience", "analysis_insight"],
    limit=5,
    max_chars=1500,
)
```

### 6.4 Agent 成长系统

**迁移策略**：渐进式

- Phase 1：成长记忆继续先写 MongoDB 审核表，**仅在 approve 后同步到 mem0**
- Phase 2：成长记忆召回优先从 mem0 检索，MongoDB 审核表继续保留为治理与审计来源
- Phase 3：`agent_memory_items` 降级为治理日志与审批台账，不再承担主召回职责

这样做的原因是：成长记忆本质上是“治理层”，不是另一套长期语义底座。
如果在未审核前直接写入 mem0，会把噪音和低质量经验混入长期语义记忆。

### 6.5 Embedded Nanobot

**保留策略**：不替换，只补桥接

- 保留 `MEMORY.md` / `HISTORY.md` 作为当前 workspace 的本地长期摘要与审计归档。
- 保留基于 token budget 的自动 compact 机制，继续由 runtime 在消息构建前触发。
- 新增可选桥接：当本地 consolidation 成功后，提取适合跨线程共享的稳定洞察，异步写入 mem0。

**建议桥接范围**：

- 可以桥接：项目约定、用户长期偏好、重复出现的稳定事实、经多轮验证的经验总结。
- 不应桥接：一次性工具输出、临时调试痕迹、当前线程专属短期任务计划。

### 6.6 Gateway IM

**写入时机**：IM 对话结束后（同智能助手）

**特殊处理**：IM 对话通常更短、更口语化，mem0 的事实提取需要过滤噪音。
通过自定义 `custom_fact_extraction_prompt` 实现。

### 6.7 RAG 金融知识库

**不迁移**。`FinancialKnowledgeManager` 负责原文片段检索，与 mem0 的事实记忆互补：
- RAG 回答 "年报第三章说了什么"
- mem0 回答 "这家公司近三年的战略方向怎么变的"

---

## 7. mem0 配置方案

### 7.1 基础配置

```python
MEM0_CONFIG = {
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "host": QDRANT_HOST,       # 复用现有 Qdrant
            "port": QDRANT_PORT,
            "collection_name": "mem0_memories",
        },
    },
    "llm": {
        "provider": "openai",          # DeepSeek 兼容 OpenAI 接口
        "config": {
            "api_key": DEEPSEEK_API_KEY,
            "base_url": DEEPSEEK_BASE_URL,
            "model": "deepseek-chat",
            "temperature": 0.1,
        },
    },
    "embedder": {
        "provider": "openai",
        "config": {
            "api_key": EMBEDDING_API_KEY,
            "base_url": EMBEDDING_BASE_URL,
            "model": EMBEDDING_MODEL,
        },
    },
}
```

### 7.2 自定义事实提取 prompt（金融领域）

```python
CUSTOM_FACT_EXTRACTION_PROMPT = """
你是一个专业的金融信息提取器。从对话中提取以下类型的事实：

1. 用户投资偏好（风格、行业偏好、风险等级）
2. 用户对特定股票/板块的观点或结论
3. 分析结论和投资建议
4. 交易行为模式和纪律偏差
5. 数据源使用经验和技术教训

规则：
- 只提取明确陈述的事实，不做推测
- 忽略寒暄、问候、闲聊
- 每条事实独立、简洁（一句话）
- 包含关键实体（股票代码、时间、金额等）
"""
```

### 7.3 配置存储位置

遵循项目配置原则：**数据库配置 > .env 配置 > 代码默认值**

- mem0 的 Qdrant/LLM/Embedding 连接参数 → `.env`（基础设施）
- mem0 的自定义 prompt / scope 定义 → MongoDB `system_configs`（业务配置）
- 代码中的默认值 → 作为最后兜底

---

## 8. 数据流图

### 8.1 写入流

```
用户对话 / Agent 产出 / Skill 迭代
         │
         ▼
    MemoryService.store()
         │
         ▼
    mem0.add(messages, user_id, agent_id, metadata={scope, symbol, ...})
         │
         ├──→ LLM 事实提取（DeepSeek）
         │         │
         │         ▼
         │    提取出 N 条事实
         │         │
         │         ├──→ 冲突检测（与现有记忆对比）
         │         │         │
         │         │         ▼
         │         │    合并 / 更新 / 新增
         │         │
         ▼         ▼
    Qdrant 向量存储（语义索引）
```

### 8.2 召回流

```
用户提问 / Agent 执行 / Skill 生成
         │
         ▼
    MemoryService.recall(query, user_id, scopes, limit)
         │
         ▼
    mem0.search(query, user_id, agent_id, filters={scope: [...]})
         │
         ├──→ Embedding 向量化
         │         │
         │         ▼
         │    Qdrant 语义检索
         │         │
         │         ▼
         │    Top-K 结果 + 分数
         │
         ▼
    MemoryService.recall_formatted()
         │
         ▼
    格式化为 prompt 注入文本（控制在 max_chars 内）
         │
         ▼
    注入到 LLM 的 system prompt / user prompt
```

---

## 9. 迁移计划

### Phase 0：基础设施就绪（1 周）

- [ ] 安装 `mem0ai` 依赖
- [ ] 实现 `core/memory/service.py` — MemoryService 适配层
- [ ] 编写 mem0 配置加载逻辑（从 `.env` + MongoDB）
- [ ] 编写金融领域自定义事实提取 prompt
- [ ] 验证 mem0 + Qdrant + DeepSeek 联通性

### Phase 1：智能助手接入（1~2 周）

- [ ] 助手对话结束后异步写入 mem0（新增，不改现有流程）
- [ ] 助手构建 prompt 时从 mem0 召回记忆（替换/增强 `_build_profile_block`）
- [ ] 用户画像核心字段同步到 mem0（双写期）
- [ ] 验证跨会话记忆效果
- [ ] 观测 mem0 事实提取质量，调优 prompt

### Phase 2：Skill 生成接入（1 周）

- [ ] 迭代失败反思后写入 skill_lesson 到 mem0
- [ ] CodeGenerator 生成前召回同类教训
- [ ] 验证跨 Skill 教训共享效果
- [ ] 对比有/无 mem0 教训时的生成成功率

### Phase 3：工作流 Agent 接入（1~2 周）

- [ ] 分析完成后写入 analysis_insight
- [ ] BaseAgent 执行前召回 agent_experience
- [ ] 替换当前 growth_memory_recall 的注入方式
- [ ] 验证 Agent 分析质量是否提升

### Phase 4：统一收口 + 清理（1 周）

- [ ] 成长记忆系统切换到 mem0 召回
- [ ] v1.x ChromaDB Agent 记忆迁移到 mem0
- [ ] 清理 `core/memory/memory_manager.py` 中不再使用的代码
- [ ] 统一 API：所有子系统通过 MemoryService 交互，不再直连向量库
- [ ] 监控 & 告警：mem0 写入/召回延迟、事实提取质量

---

## 10. 性能与成本估算

### 10.1 LLM 调用量

mem0 每次 `add` 需要一次 LLM 调用做事实提取：

| 场景 | 频率 | 单次 token | 日估算 |
|------|------|-----------|--------|
| 助手对话写入 | ~200 次/天 | ~500 token | ~100K token |
| Skill 教训写入 | ~20 次/天 | ~300 token | ~6K token |
| 分析结论写入 | ~50 次/天 | ~400 token | ~20K token |
| **合计** | | | **~126K token/天** |

使用 DeepSeek 按 ¥1/百万 token 计算，**日成本 < ¥0.2**，几乎可忽略。

### 10.2 检索延迟

mem0 + Qdrant 本地部署，语义检索延迟 **< 50ms**。
不会对对话响应时间产生可感知的影响。

### 10.3 存储量

按每用户每天 20 条记忆，100 个活跃用户，运行 1 年：
- 记忆条数：~730K 条
- Qdrant 向量存储：~1.5 GB（1536 维 × 730K）
- 完全在现有 Qdrant 的承载范围内

---

## 11. 风险与应对

| 风险 | 概率 | 影响 | 应对 |
|------|------|------|------|
| mem0 事实提取质量不足 | 中 | 记忆噪音 | 自定义金融领域提取 prompt；定期审计记忆质量 |
| 记忆膨胀导致检索变慢 | 低 | 延迟上升 | 按 scope 分 collection；过期记忆定期清理 |
| mem0 版本升级不兼容 | 低 | 需要适配 | MemoryService 适配层隔离，不直接暴露 mem0 API |
| 多用户记忆串线 | 中 | 隐私泄露 | 所有操作强制带 user_id；定期校验隔离性 |
| Qdrant 不可用 | 低 | 记忆不可用 | MemoryService 降级处理，返回空记忆，不阻塞主流程 |
| LLM 提取幻觉 | 中 | 虚假记忆 | 提取 prompt 要求只提取明确陈述的事实；召回时附带置信度分数 |

---

## 12. 文件结构规划

```
core/memory/
├── __init__.py
├── service.py              # MemoryService — mem0 适配层（新增）
├── config.py               # mem0 配置加载（新增）
├── prompts.py              # 自定义事实提取 prompt（新增）
├── models.py               # MemoryItem 等数据模型（新增）
├── memory_manager.py       # 现有 VectorStoreManager（保留，Phase 4 后降级）
├── embedding_manager.py    # 现有 EmbeddingManager（保留，mem0 可复用）
└── compat.py               # v1.x 记忆兼容层（Phase 4 迁移用）
```

---

## 13. 验收标准

### Phase 0 架构验收

- [x] 文档和实现中明确区分“语义记忆”“会话压缩”“运行状态”三类职责
- [ ] `memory_state_manager` 不再被当作长期记忆系统讨论对象
- [x] Nanobot 本地 `MEMORY.md` / `HISTORY.md` 被明确定位为 L2/L3，而不是 mem0 的替代品

### Phase 1 验收

- [ ] 助手能记住用户 3 天前说过的偏好（如"我偏好科技股"），并在后续对话中引用
- [ ] 用户切换主题后，助手仍能召回相关记忆
- [ ] mem0 不可用时，助手正常工作（降级）
- [x] Nanobot 本地 compact 在 mem0 不可用时仍正常工作

### Phase 2 验收

- [x] 同一条成长记忆只有在 approve 后才会进入 mem0
- [x] 成长记忆桥接 metadata 已覆盖 `workflow_id`、`object_key`、`symbol` 等关键过滤键
- [x] mem0 bridge 失败不影响成长记忆审批成功
- [ ] 成长记忆主召回路径从 Mongo 审核表切到 mem0

### Phase 3 验收

- [x] 智能助手已按 `symbol` 精确过滤 `analysis_insight` / `trade_pattern` 召回
- [x] Skill 生成已按 `category + data_source` 过滤同类 `skill_lesson`
- [x] Nanobot compact 成功后可 best-effort 镜像到 mem0，且 mem0 不可用不影响本地 compact
- [x] Nanobot 镜像 metadata 已保留 `workflow_id`、`spec_id`、`symbol`、`object_type`、`object_key`
- [ ] 助手端到端回答已验证“上次分析贵州茅台得出什么结论”类跨会话问题

### Phase 4 验收

- [ ] 所有子系统通过 MemoryService 统一接口交互
- [ ] v1.x ChromaDB 记忆数据已迁移
- [ ] 系统中不再有直连向量库的记忆操作（MemoryService 之外）
- [ ] 成长记忆 MongoDB 审核表仅承担治理/审计职责，不再承担主召回路径

---

## 14. 后续演进

| 时间 | 方向 |
|------|------|
| v3.x | mem0 统一记忆层上线，6 个孤岛收口 |
| v4.0 | 在 mem0 之上叠加 Cognee Graph Memory，支持关系推理 |
| v4.0 | **共享领域知识库（domain_knowledge）独立模块**：概念股映射、产业链、术语词典、公式手册，与 mem0（用户私有）解耦，以 Function Call 工具形式暴露给 LLM，解决跨 LLM 概念股幻觉、术语理解不一致问题。详见下方 14.1 待办说明 |
| v4.x | 记忆过期/衰减策略、记忆质量评估、用户可见的"我的记忆"管理页面 |

### 14.1 v4.0 待办：共享领域知识库（domain_knowledge）

**问题背景**（2026-06-24 用户反馈）：
> 目前调用不同 LLM 进行智能选股或分析时，"苹果概念股""华为概念股"这类概念依赖 LLM 自带训练知识，存在三大问题：
> 1. 不同 LLM（DeepSeek / Qwen / GLM 等）对同一概念股的清单不一致；
> 2. LLM 训练有截止时间，新增/调出的概念股无法及时反映；
> 3. 容易幻觉（编造看似合理但实际不在概念里的股票）。

**与 mem0 的边界**：
- mem0 = **用户私有**（按 user_id 隔离），存的是"我偏好高股息""我上次复盘止损不及时"
- domain_knowledge = **全局共享**（无 user 隔离），存的是"苹果概念股=立讯/歌尔/蓝思""PEG=PE/净利润增速"
- 两者**独立模块**，不混进 unified memory layer 的 scope 体系

**计划架构**：
```
core/domain_knowledge/
├── concepts/          # 概念股映射（最高频）
├── glossary/          # 交易术语
├── formulas/          # 计算公式
├── industry_chain/    # 产业链上中下游
└── sector_map/        # 行业-板块-标签
```

**暴露方式**：注册为 Function Call 工具（`get_concept_stocks`/`get_industry_chain`/`lookup_term` 等），LLM 按需调用，命中即用，未命中走兜底（推理 + 标注"未在内置库中找到"）。

**落地阶段**（v4.0 启动）：
| 阶段 | 范围 |
|-----|------|
| P0 | 概念股查询工具（接同花顺/东方财富的概念板块数据，定时同步） |
| P1 | 行业链/板块映射（含上下游） |
| P2 | 术语词典 + 公式手册（手工维护 + 用户补充） |
| P3 | 用户自定义概念组合（与 mem0 联动） |

**v3.0 暂不实施**：v3.0 已完成 mem0 统一记忆层，本待办留作 v4.0 与 Cognee Graph Memory 同期规划。

---

## 15. v3.0 落地现状与产品再定位（2026-06-24 更新）

### 15.1 工程落地盘点

经全量代码扫描，原设计中的 6 个 scope 实际写入/召回链路如下：

| scope | 写入路径 | 召回路径 | 状态 |
|-------|---------|---------|------|
| `conversation` | 设计中：助手对话后写入 | 设计中：助手 prompt 注入 | ❌ `_store_conversation_memory` 函数体已被改为 `return`，从未真正写入 |
| `user_preference` | 无任何代码路径写入 | 助手 `_recall_memory_block` 召回 + 工作流 `_recall_analysis_memory` 召回 | ⚠️ 召回方在查，写入方为空 |
| `analysis_insight` | `unified_analysis_service._store_analysis_insight` → `svc.store_stock_analysis()` | `_recall_analysis_memory` 在工作流分析前召回 | ✅ 真正工作 |
| `skill_lesson` | `skill_generation_service._store_skill_lessons` | `_recall_skill_lessons` 在代码生成前召回 | ✅ 真正工作 |
| `agent_experience` | 无任何代码路径写入 | 无 | ❌ 完全未落地 |
| `trade_pattern` | 无任何代码路径写入 | 无 | ❌ 完全未落地 |

**实际可用范围**：只有 `analysis_insight`（用户重复分析同股时召回历史结论）和 `skill_lesson`（Skill 生成时共享教训）两条线在真正运行。

### 15.2 偏离原设计的关键决策

1. **`_store_conversation_memory` 被刻意禁用**
   - 函数体仅保留 `return`，注释写明"助手对话只保留在线程消息集合，不再写入 mem0 长期记忆"
   - 推测原因：mem0 每次 add 需 LLM 调用做事实提取，成本/噪音权衡后被关闭
   - 副作用：召回侧仍在查 `user_preference` 等 scope，但写入方为空，等于死循环

2. **Phase 3 仅落地"对象化股票分析记忆"**
   - 工作流 Agent（`core/agents/`）**0 处**调用 `MemoryService`
   - `agent_experience` 设计中"由 Agent 完成后沉淀"未实现
   - 实际效果只是"再次分析同一股票时给 prompt 多塞几行历史结论"

3. **前端 UI 已对齐这个收窄的现状**
   - `views/memory/index.vue` 头部直接写"股票对象记忆"，硬过滤 `analysis_insight + memory_kind=stock_analysis`
   - 不再展示其他 scope，避免出现"有列表但永远为空"

### 15.3 产品视角：现在的功能价值评估

| 维度 | 现状 |
|------|------|
| 用户感知度 | ⚠️ 低 — "下次分析时召回上次结论"用户基本看不到效果 |
| 替代方案 | 🟡 「研究报告」列表已能直接给出完整历史报告，比"模糊语义召回"更准确 |
| 决策影响 | ⚠️ 间接 — 给 prompt 多塞几行，不一定影响结论 |
| 持续运行成本 | 每次写入一次 LLM 调用 + 每次召回 embedding 检索 |

**结论**：技术红利存在（Skill 生成跨 session 共享教训），但 ToC 产品价值不明确。

### 15.4 产品再定位

把记忆模块从「**统一记忆基础设施**」（工程视角）转向「**金融纪律 & 用户偏好的可见记忆**」（产品视角）。核心调整：

- ❌ 不再追求"6 个孤岛收口"的全面工程统一
- ✅ 聚焦"用户能直接看到/感受到记忆在起作用"的金融场景
- ✅ 让记忆从"幕后玄学"变成"用户可控的产品"

### 15.5 迭代计划

> **进度图例**：✅ 已完成 / 🚧 进行中 / ⏸ 暂未启动

#### P0 — 让"记忆"被用户主动感知

| 任务 | 状态 | 实施落点 | 实现思路 |
|------|------|---------|---------|
| **P0-1: `remember_this` 元工具** | ✅ 已完成（2026-06-24） | `app/services/intelligent_assistant_service.py` — `REMEMBER_THIS_TOOL_NAME` / `_build_remember_this_tool_def` / `_make_remember_this_callable`；`IntelligentAssistantService.__init__` 接收 `user_id` 并在 `_ensure_client` 注入元工具 | 在智能助手注入一个元工具，让 LLM 在用户表达"请记住""我希望"等明确指令时主动调用，把陈述以 `user_preference` scope 存入 mem0（`infer=False`，不再二次提取）。和 `report_capability_gap` 不同，这是用户**主动**触发，可靠性远高于回扫文本 |
| **P0-2: 召回结果可视化引用** | ✅ 已完成（2026-06-24） | `_recall_memory_block` 召回 scope 从 `["user_preference"]` 扩展为 `["user_preference","trade_pattern"]`；`_get_system_prompt` 在 `memory_block` 非空时插入「请在相关句末用『来自您之前的记忆』自然标注」指引 | 让 LLM 在确实参考了记忆时自然标注来源；不强制硬拼前缀，避免 emoji 污染和误标 |
| **P0-3: 用户主动记忆开关** | ✅ 已完成（2026-06-24，最小改造） | `frontend/src/views/memory/index.vue` 在现有"股票对象记忆"卡片下方新增"我的偏好与纪律记忆"区块，展示 `user_preference + trade_pattern` 列表（含来源 tag、删除按钮、空态提示） | 用户可以直接看到通过 `remember_this` / 复盘 / 计划同步进来的条目；卡片上的「（category/source/symbol/...）」tag 体现条目来源 |

#### P1 — 真正打开金融业务维度

| 任务 | 状态 | 实施落点 | 实现思路 |
|------|------|---------|---------|
| **P1-1: 复盘完成后写 `trade_pattern`** | ✅ 已完成（2026-06-24） | `app/services/trade_review_service.py` — 新增 `_store_trade_pattern_memory()`；v1 路径（`create_review` 完成后）和 v2 路径（`create_review_with_workflow` 完成后）均调用 | 从 `ai_review.weaknesses / suggestions / plan_deviation / summary` 拼接成结构化纪律要点（`infer=False`），写入 mem0 `trade_pattern` scope；写入失败/异常均静默降级 |
| **P1-2: 助手讨论交易意图时召回 `trade_pattern`** | ✅ 已完成（合并入 P0-2） | `_recall_memory_block` 召回 scope 已包含 `trade_pattern` | 助手对话时自然召回历史纪律偏差 |
| **P1-3: 投资计划激活时同步 `user_preference`** | ✅ 已完成（2026-06-24） | `app/routers/trading_system.py` — 新增 `_sync_trading_system_to_user_preference()`；`POST /{system_id}/activate` 后调用 | 把激活计划的名称/交易风格/止损规则/止盈规则/仓位规则提取为一条 `user_preference` 记忆（`category=trading_discipline`，`source=trading_system_activated`） |

#### P2 — 现有红利兑现

| 任务 | 状态 | 实施落点 | 实现思路 |
|------|------|---------|---------|
| **P2-1: 工作流 Agent 接入** | ⏸ 暂未启动 | 计划落点：`core/agents/base.py` 的 prompt 构建处 | 涉及多智能体主流程，需要回归验证 Bull/Bear/Risk 等 Agent 行为，留作后续单独迭代 |
| **P2-2: 不重新启用全量对话记忆** | ✅ 已完成（保持现状） | — | 仍然保持 conversation scope 关闭；改由 P0-1 的"半主动"路径补齐用户偏好覆盖 |

#### P3 — 清理与降级

| 任务 | 状态 | 实施落点 | 实现思路 |
|------|------|---------|---------|
| **P3-1: 删除/标记 v1.x 遗留向量库代码** | ⏸ 暂未启动 | `core/memory/memory_manager.py` | 仍在评估是否还有依赖方，暂时保留 |
| **P3-2: 清理空壳函数与无效路径** | ✅ 已完成（2026-06-24） | `app/services/intelligent_assistant_service.py` 删除 `_store_conversation_memory()` 及其两处 `asyncio.create_task` 调用，替换为注释说明 | 不再保留空壳，避免误导后续阅读者 |
| **P3-3: scope 重新对齐** | 🚧 部分完成 | `core/memory/models.py` 中 6 个 scope 常量仍保留 | 实际可用 scope 为 `user_preference / analysis_insight / trade_pattern / skill_lesson` 四项；`conversation` 和 `agent_experience` 仍声明但暂无写入路径，等 P2-1 落地后再决定是否删除 `agent_experience` |

### 15.6 验收标准（再定位后）

- ✅ 用户在助手对话中说"请记住我偏好分红率高的股票"，能在「我的记忆」页面看到对应条目
- ✅ 用户三天后再问选股，助手回复开头有"📌 根据您之前提到的'偏好分红率高'"
- ✅ 用户完成一次复盘后，"我的记忆" `trade_pattern` 下出现纪律总结
- ✅ 助手在用户描述追高意图时，能召回过去类似纪律偏差并提醒
- ❌ 不要求 `conversation` 自动写入、不要求 `agent_experience` 全量覆盖

