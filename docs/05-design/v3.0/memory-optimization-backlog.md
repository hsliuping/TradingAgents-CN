# v3.0 记忆系统优化待办清单

## 📋 文档信息

| 项目 | 内容 |
| ------ | ------ |
| 版本 | v1.0 |
| 状态 | P0 已完成复核，P1/P2 待继续 |
| 日期 | 2026-04-08 |
| 目标 | 将当前版本记忆系统优化方向收敛成可执行的 P0 / P1 / P2 清单，避免继续把精力消耗在旧代码清理上 |
| 关联文档 | [统一记忆层设计 — 基于 mem0 的全系统记忆整合](./unified-memory-layer-mem0.md)、[v3.0 能力与七层记忆对应关系](./memory-capability-layer-mapping.md)、[Nanobot First 的 Agent 工坊统一设计](./nanobot-first-agent-workshop-unification.md)、[v3.0 L5/L6 召回质量优化实施说明](./memory-recall-quality-implementation-plan.md)、[记忆消费闭环验证脚本](../../../scripts/validate_memory_consumption_loops.py) |

---

## 1. 范围结论

当前版本记忆系统优化的重点，不是继续做 legacy 退场，也不是重构 Nanobot 本地 compact，而是把已经接上的七层边界真正变成稳定能力。

当前版本只聚焦四类事情：

1. **补齐 L4 项目长期记忆的最小闭环**
2. **提升 L5/L6 召回质量，而不是只停留在“已接 mem0”**
3. **把成长记忆、智能助手、Skill 生成、股票分析的消费闭环做实**
4. **为 Agent 生成补一层专用的 L6 经验记忆**

当前版本明确不优先：

1. 删除旧版 memory 代码
2. 大规模改名 `memory_state_manager`
3. 让 mem0 替代 Nanobot `MEMORY.md` / `HISTORY.md`
4. 为了“代码整洁”继续扩散式调整旧流程

---

## 2. 优先级总览

| 优先级 | 主题 | 目标 | 当前状态 |
| ------ | ------ | ------ | ------ |
| P0 | L4 + L5/L6 质量 + 消费闭环 | 先让现有主链路真的稳定可用 | 已完成首轮闭环与回归验证 |
| P1 | Agent 生成经验层 + 观测 + 对象扩展 | 提升复用能力与可观测性 | 仍有结构缺口，尚未落地 |
| P2 | 术语收口与后续清理准备 | 降低未来版本改造成本 | 可继续，但不应压过 P1 |

一句话理解：

- **P0 解决“现在能不能稳定用”**
- **P1 解决“后面能不能越用越聪明”**
- **P2 解决“下个版本能不能更轻松继续演进”**

### 2.1 截至 2026-04-08 的复核结论

这次复核之后，当前文档状态应按下面理解：

1. **P0 已基本完成**：L4 最小闭环、L5/L6 召回质量增强、四条消费闭环都已有代码与测试支撑。
2. **P1 尚未完成**：Agent 生成专用 L6 已完成最小闭环，但统一观测面板、更广的跨对象 object 绑定和更早阶段的 lesson 消费仍未补齐。
3. **P2 仍是后续整理项**：术语收口和 legacy 清理准备重要，但不应重新盖过 P1。
4. 当前与记忆直接相关的回归结果为：`50 passed, 42 warnings`，说明 P0 功能面当前是绿的。

---

## 3. P0：当前版本必须完成

## 3.1 P0-1 补齐 L4 项目长期记忆最小闭环

### P0-1 目标

让 L4 不再只是文档概念或按需镜像，而是至少有一条明确可用的“写入 -> 读取 -> 注入”链路。

### P0-1 当前问题

当前文档已经明确：L4 仍然偏弱，尚未成为各条链路统一依赖的稳定层。

### P0-1 建议实现范围

1. 明确 L4 的对象边界，只收项目级、跨线程、稳定、低变化的规则。
2. 先只支持少量高价值对象，例如：
   - 项目规则
   - Agent 工坊治理约束
   - 统一分析输出约束
   - 稳定的研究模板/评审规则
3. 先打通一条最小消费链，优先推荐：
   - Agent 生成
   - 智能助手

### P0-1 不要做的事

1. 不把所有业务配置都塞进 L4。
2. 不把会随单任务频繁变化的状态塞进 L4。
3. 不在当前版本就试图做完整知识图谱化。

### P0-1 完成标准

1. 有明确的 L4 数据定义与元数据约束。
2. 至少 1 条写入链路稳定可用。
3. 至少 1 条读取消费链路稳定可用。
4. 文档里能说清楚哪些对象属于 L4，哪些仍属于业务真相或 L7。

### P0-1 当前落地

当前已补最小 L4 闭环，并已接到两条消费链：

1. 新增 ProjectMemoryService，支持项目级稳定规则的 upsert、list、prompt block 构建
2. 新增 L4 项目长期记忆接口，支持写入、列表查看、prompt block 预览和默认规则 seed
3. 智能助手在原有 mem0 L5/L6 召回前，会先拼入 L4 项目长期记忆块
4. 已补受控验证脚本，验证写入 -> 读取 -> 助手 prompt 注入的最小闭环
5. 已内置并执行首批默认规则 seed，当前默认集覆盖合规禁令、金融边界、复杂操作确认、实时数据优先、回答结构、个股分析模板
6. Agent Builder 治理请求命中时，Nanobot runtime 会前置注入 L4 项目长期记忆块，再叠加 Agent Workshop governance guidance
7. Agent Workshop 在创建版本 Prompt Template 时，也会把 L4 项目长期记忆块写入 system_prompt 和 constraints，让生成出的版本模板本身继承稳定项目规则
8. Agent Workshop 在发布版本前，会校验当前 Prompt Template 是否仍绑定了最新 L4 项目长期记忆；若模板缺失该绑定，则拒绝发布，避免旧模板绕过稳定项目规则
9. Agent Workshop 的 production-review 现在也会检查运行时 debug_prompt.system_prompt 是否真实包含当前 L4 项目长期记忆；若缺失绑定或缺少 prompt 证据，则不能作为正式发布依据
10. 已补 production-review 的脚本级烟测，覆盖“运行时 prompt 含当前 L4”“缺少当前 L4”“缺少 system_prompt 证据”三种受控场景

入口文件：

1. [app/services/project_memory_service.py](../../../app/services/project_memory_service.py)
2. [app/services/project_memory_defaults.py](../../../app/services/project_memory_defaults.py)
3. [scripts/seed_project_memory_defaults.py](../../../scripts/seed_project_memory_defaults.py)
4. [app/routers/memory.py](../../../app/routers/memory.py)
5. [app/services/intelligent_assistant_service.py](../../../app/services/intelligent_assistant_service.py)
6. [scripts/validate_project_memory_l4_loop.py](../../../scripts/validate_project_memory_l4_loop.py)
7. [core/embedded_nanobot/runtime.py](../../../core/embedded_nanobot/runtime.py)
8. [scripts/validate_agent_builder_project_memory_loop.py](../../../scripts/validate_agent_builder_project_memory_loop.py)
9. [app/services/agent_workshop_service.py](../../../app/services/agent_workshop_service.py)
10. [scripts/validate_agent_workshop_prompt_template_project_memory_loop.py](../../../scripts/validate_agent_workshop_prompt_template_project_memory_loop.py)

---

## 3.2 P0-2 提升 L5/L6 召回质量

详细实施见：[v3.0 L5/L6 召回质量优化实施说明](./memory-recall-quality-implementation-plan.md)

### P0-2 目标

把“能召回”优化到“召回结果相关、可控、可解释”。

### P0-2 当前问题

当前主路径已经完成第一轮质量增强，但仍有三类余量：

1. 统一观测指标仍然不足，暂时还不能稳定回答“这次为什么召回得不好”
2. object_key / object_type 对非股票对象的质量验证还不够完整
3. Agent 生成场景还没有专门的 L6 经验层来配合召回质量优化

### P0-2 建议实现范围

1. 建立统一的召回评估样本集：
   - 智能助手问题
   - 股票分析问题
   - Skill 生成同类需求
   - Agent 生成治理问题
2. 固定几类评估指标：
   - 命中率
   - 空召回率
   - 重复率
   - 注入后 prompt 有效长度
   - 输出改善情况
3. 优化排序与过滤：
   - 先 metadata 精确过滤
   - 再语义召回
   - 再做去重和新鲜度排序

### P0-2 不要做的事

1. 不要只看“mem0 返回非空”就判定成功。
2. 不要无控制地增加召回条数。
3. 不要让召回注入把 prompt 挤爆，反而伤害主任务。

### P0-2 完成标准

1. 至少有一套固定的召回评估脚本或样本流程。
2. 能比较优化前后的命中率和输出质量。
3. 主要主链路的召回策略不再是“各写各的经验规则”。

### P0-2 当前落地

当前已完成第一轮召回质量增强，实际代码行为已经不再是“过滤后直接按原顺序截断”：

1. `MemoryService.recall()` 已支持 exact filter 下推、本地 scope / metadata 过滤、统一重排、去重后再截断
2. `MemoryService.recall_formatted()` 已支持 `ranking_profile`、`group_by_scope`、`per_scope_limit`
3. 智能助手、股票分析、Skill 生成已切到 profile 化召回主路径
4. 已补受控评估脚本与测试，覆盖 assistant / analysis / skill_generation 三类 recall profile

---

## 3.3 P0-3 做实消费闭环，而不只是写入闭环

### P0-3 目标

让已经写进 mem0 的记忆真正稳定影响后续推理与输出。

### P0-3 当前问题

现在已经有多条写入链路，但还需要继续确认“谁在真正消费它们”：

1. 智能助手
2. 股票分析
3. 成长记忆 approve 后桥接内容
4. Skill 生成的 `skill_lesson`

### P0-3 建议实现范围

1. 为每条主链路补一套“写入后第二次消费”的受控验证。
2. 把“prompt 中是否真实出现注入内容”作为验收条件之一。
3. 优先验证这些闭环：
   - 助手：用户偏好 / 历史洞察是否影响回答
   - 股票分析：历史分析洞察 / agent 经验是否影响结论
   - 成长记忆：approve 后是否能被后续任务消费
   - Skill 生成：历史失败原因是否影响下一次生成

### P0-3 不要做的事

1. 不要只验证数据库中“有数据”。
2. 不要只验证 API 返回了 recall 结果。
3. 不要跳过 prompt 级和输出级验证。

### P0-3 完成标准

1. 四条主链路至少各有一条受控消费验证。
2. 每条验证都能说明“记忆是否真的进入 prompt”。
3. 至少能识别“写入成功但消费无效”的场景。

### P0-3 当前落地

当前已补一套受控验证脚本与测试，覆盖四条主链路的真实消费注入点：

1. 智能助手：验证 `memory_block` 进入聊天参数并进入 system prompt
2. 股票分析：验证 mem0 分析记忆并入 `inputs["growth_memory_recall"]`
3. 成长记忆：验证 approve 后的 `pattern` 记忆可按 `workflow_id` 被 `build_recall_context()` 再次消费
4. Skill 生成：验证 `skill_lesson` 并入 `controller.run(initial_feedback=...)`

入口文件：

1. [scripts/validate_memory_consumption_loops.py](../../../scripts/validate_memory_consumption_loops.py)
2. [tests/scripts/test_validate_memory_consumption_loops.py](../../../tests/scripts/test_validate_memory_consumption_loops.py)

---

## 4. P1：后续优先推进

## 4.1 P1-1 为 Agent 生成补专用 L6 经验层

### P1-1 目标

让 Agent 生成不再只依赖 L2/L3 会话记忆和 L7 上下文绑定，而是拥有可复用的经验沉淀层。

### P1-1 当前问题

目前 Skill 生成已有 `skill_lesson`，但 Agent 生成还没有等价的经验 scope。现在 Nanobot / Agent Workshop 的失败经验、调试经验、提示词迭代经验，还没有形成下一次生成可直接复用的长期经验。

### P1-1 当前状态

截至本次复核，结论仍然不变，而且已经被代码搜索再次确认：

1. Embedded Nanobot 目前写回 mem0 的主要是 `conversation` scope
2. Agent Workshop / Agent Builder 主链中仍未见 `agent_builder_lesson` 或等价专用 scope 的读写入口
3. 当前已经具备最小可用的 Agent Builder 专用 L6，但还不能说 Agent 生成的经验层已经全面做实

### P1-1 建议实现范围

1. 新增一类 L6 经验对象，例如：
   - `agent_builder_lesson`
   - 或纳入现有 `agent_experience`，但要明确 metadata 区分来源
2. 优先沉淀这些经验：
   - 常见失败原因
   - 提示词迭代有效模式
   - 工具绑定失误
   - 评估阶段高频问题
3. 消费入口优先放在：
   - Agent 生成需求确认阶段
   - 版本构建前
   - 版本迭代前

### P1-1 当前落地

当前这项已经完成第一轮最小闭环，范围比文档初稿更进一步：

1. 已新增专用 scope `agent_builder_lesson`
2. `evaluate_version(...)` 结束后会把 production-review / sandbox 的结构化 lesson 写入 `agent_builder_lesson`
3. 版本迭代前会召回同 spec 的 `agent_builder_lesson`，并注入到 cloned prompt template
4. Embedded Nanobot 命中 `agent_builder_governance` 时，会在 L4 项目长期记忆之后继续注入 L6 historical lessons
5. 已补脚本级和测试级验证，覆盖写入、迭代消费、runtime governance 消费三条链路

当前仍未完成的部分：

1. 需求确认阶段和版本构建前的更早 lesson 消费还没补
2. recall 统一观测指标和 dashboard 还没补
3. 跨更多非股票对象的 object 绑定验证还不够完整

### P1-1 最小落地方案

当前更推荐把这项拆成一个“最小可用、可验证、不会污染现有 L6 语义”的方案，而不是一开始就做大而全经验平台。

#### 方案选择

1. **首选方案**：新增专用 scope `agent_builder_lesson`
2. **次选兼容方案**：若当前版本不希望立即扩 scope，可暂时写入 `agent_experience`，但必须加来源 metadata，明确它属于 Agent Builder / Agent Workshop，而不是投研 Agent 运行经验
3. 当前文档更推荐首选方案，因为它和 `skill_lesson` 的语义最接近，也最不容易和现有股票分析 / workflow runtime 的 `agent_experience` 混淆

#### 最小 metadata 约束

无论最终走专用 scope 还是兼容写入，都建议至少补齐下面这些 metadata：

1. `project_id`：默认 `tradingagents-cn`
2. `source`：固定为 `agent_builder` 或 `agent_workshop`
3. `lesson_type`：例如 `prompt_iteration`、`tool_binding`、`evaluation_failure`、`governance_decision`
4. `object_type`：优先使用 `agent_spec`、`agent_version`、`prompt_template`
5. `object_key`：对应 spec_id / version_id / template_id
6. `spec_id`
7. `version_id`
8. `template_id`
9. `evaluation_type`：例如 `sandbox`、`production-review`
10. `success`：布尔值，用于区分失败教训和成功模式

其中前 5 项应视为最小必填，其余字段可按具体写入点补充。

#### 最小写入点

当前不建议从所有 Nanobot 对话都抽 lesson，而是只在“已经发生结构化判断”的节点写入：

1. **版本构建失败后**：沉淀提示词迭代失败原因、缺失输入、结构化校验失败原因
2. **工具绑定同步失败后**：沉淀 required_tools 缺失、schema 解析失败、工具名映射错误
3. **版本评估结束后**：对 production-review / sandbox 的主要 finding 做结构化归纳
4. **版本最终成功发布后**：只沉淀少量高价值成功模式，例如“哪类模板结构在某类 spec 上稳定通过”

不建议作为首版写入点的内容：

1. 原始长对话
2. 每轮草稿 prompt 全量文本
3. 没有经过评估或反思的临时尝试

#### 最小读取点

消费顺序也应收敛，只放在真正能影响下一次生成决策的位置：

1. **需求确认阶段**：召回同类 spec 的历史高频失败模式，避免重复踩坑
2. **版本构建前**：召回与当前 spec / template 接近的 prompt 结构经验和工具绑定经验
3. **版本迭代前**：把上一轮评估失败的归纳 lesson 重新注入，作为下一轮 build / revise 的约束

首版不建议放的位置：

1. 每次 Nanobot 普通聊天入口
2. 所有助手问答入口
3. 与 Agent 生成无关的分析链路

#### 最小召回策略

为了避免这层经验一接入就污染上下文，首版建议：

1. scope 只查 `agent_builder_lesson`，或只查带 `source=agent_builder|agent_workshop` 的 `agent_experience`
2. metadata 过滤优先级高于语义近似，优先按 `object_type`、`object_key`、`spec_id`、`template_id` 收敛候选集
3. 注入条数控制在 3 到 5 条以内
4. 优先展示“失败教训 + 对应修正动作”，而不是只给抽象结论

#### 最小测试点

这项一旦开始做，至少要同时补三类验证，避免再出现“写进去了但根本没用”的假闭环：

1. **写入测试**：验证 build / evaluate / revise 后是否按预期写入正确 scope 和 metadata
2. **召回测试**：验证当前 spec/version/template 命中时，相关 lesson 会排在泛化经验之前
3. **消费测试**：验证 lesson 真正进入 Agent Builder / Agent Workshop 的 prompt 或 revise 输入，而不是只停留在 recall API 返回值里

#### 最小落地顺序

建议按下面顺序推进，而不是并行铺开：

1. 先补 scope 与 metadata 约束
2. 再只选一个写入点，优先 production-review finding 总结
3. 再只选一个消费点，优先版本迭代前注入
4. 最后补脚本和单测，验证这层经验真的改善下一轮生成

### P1-1 实现任务清单（按文件）

下面这份清单的目标不是覆盖所有远期演进，而是给首批实现一个可以直接动手的拆解顺序。

#### 第一批基础约束

1. [core/memory/models.py](../../../core/memory/models.py)
   - 如果采用首选方案，新增 `MemoryScope.AGENT_BUILDER_LESSON = "agent_builder_lesson"`
   - 若暂不扩 scope，也要在文档里明确“当前版本走 `agent_experience + source metadata` 兼容路径”
2. [app/routers/memory.py](../../../app/routers/memory.py)
   - 将 `agent_builder_lesson` 加入 `ALL_SCOPES`
   - 保证后续列表、搜索、健康检查接口不会把新 scope 视为非法值
3. [core/memory/service.py](../../../core/memory/service.py)
   - 为新 scope 补 `_SCOPE_LABEL` 和 `_DEFAULT_SCOPE_ORDER`
   - 建议补一个 `agent_builder` ranking profile，优先级高于 `conversation`，并允许按 `object_type` / `object_key` / `spec_id` 收敛结果

#### 第二批 Agent Workshop 写入任务

1. [app/services/agent_workshop_service.py](../../../app/services/agent_workshop_service.py)
   - 新增一个统一 helper，建议命名为 `_build_agent_builder_lesson_metadata(...)`
   - 新增一个统一写入 helper，建议命名为 `_store_agent_builder_lesson(...)`
   - helper 至少封装 `source`、`lesson_type`、`object_type`、`object_key`、`spec_id`、`version_id`、`template_id`、`evaluation_type`、`success`
2. [app/services/agent_workshop_service.py](../../../app/services/agent_workshop_service.py)
   - 在 `evaluate_version(...)` 中增加首个正式写入点
   - 首批只沉淀 production-review / sandbox 的结构化 finding、主要 recommendation 和最终 decision
   - 这一点应优先于 build 阶段写入，因为这里最容易拿到“失败原因 + 修正建议”的稳定 lesson
3. [app/services/agent_workshop_service.py](../../../app/services/agent_workshop_service.py)
   - 在 `sync_version_required_tools(...)` 中增加可选写入点
   - 只在 required_tools 缺失、schema/tool 绑定失败或 execution plan 明显不完整时记录 tool-binding 类 lesson
4. [app/services/agent_workshop_service.py](../../../app/services/agent_workshop_service.py)
   - 在 `build_version(...)` 中暂时不要直接全量写入 lesson
   - 首版最多只为“构建失败且有明确结构化原因”的场景预留调用点，避免把半成品 prompt 过程噪声灌进 L6
5. [app/services/agent_workshop_service.py](../../../app/services/agent_workshop_service.py)
   - 在 `_clone_prompt_template_for_iteration(...)` 周边不要直接写 lesson
   - 这里只需要保证 template_id / source_version_id 这类 metadata 可被后续写入 helper 复用

#### 第三批 Agent Workshop 读取任务

1. [app/services/agent_workshop_service.py](../../../app/services/agent_workshop_service.py)
   - 新增读取 helper，建议命名为 `_recall_agent_builder_lessons(...)`
   - 首版读取时只查 `agent_builder_lesson`，或只查 `source=agent_builder|agent_workshop` 的 `agent_experience`
   - 读取参数优先使用 `object_type`、`object_key`、`spec_id`、`template_id`
2. [app/services/agent_workshop_service.py](../../../app/services/agent_workshop_service.py)
   - 在版本迭代前的入口接入该 helper，优先选择 iterate / revise 前的 prompt 组装点
   - 目标不是所有 build 都带 lesson，而是“上一轮已评估失败”的版本下一轮自动带入修正经验
3. [app/services/agent_workshop_service.py](../../../app/services/agent_workshop_service.py)
   - 如果当前版本暂时没有独立 revise helper，就先把读取结果挂到 `build_version(...)` 的 prompt template content 构建链路里
   - 但必须限定只有迭代场景才注入，避免全量 draft 构建都被历史 lesson 污染

#### 第四批 Embedded Nanobot 接入任务

1. [core/embedded_nanobot/runtime.py](../../../core/embedded_nanobot/runtime.py)
   - 新增一个与 `_recall_project_memory_guidance(...)` 平级的 lesson guidance helper，建议命名为 `_recall_agent_builder_lesson_guidance(...)`
   - 仅在 `agent_builder_governance` 命中时启用，不进入普通 Nanobot 对话入口
2. [core/embedded_nanobot/runtime.py](../../../core/embedded_nanobot/runtime.py)
   - 用 `_merge_system_guidance(...)` 把 L6 lesson guidance 叠加到现有 project memory guidance 后面
   - 顺序建议是：L4 项目长期记忆在前，L6 lesson 在后，避免历史经验盖过硬约束

#### 第五批测试与脚本任务

1. [tests/services/test_agent_workshop_service_publish_flow.py](../../../tests/services/test_agent_workshop_service_publish_flow.py)
   - 补写入测试：`evaluate_version(...)` 后是否按预期写入 lesson scope 和 metadata
   - 补读取测试：迭代场景下 recall 结果是否进入 prompt template content 或 revise 输入
   - 补排序测试：当前 version/spec/template 命中时，相关 lesson 是否优先于泛化经验
2. [tests/core/embedded_nanobot/test_runtime_hygiene.py](../../../tests/core/embedded_nanobot/test_runtime_hygiene.py)
   - 补 governance 命中时的 lesson guidance 注入测试
   - 明确验证普通聊天入口不会误注入 Agent Builder lesson
3. [tests/core/tools/implementations/test_nanobot_agent_builder_tools.py](../../../tests/core/tools/implementations/test_nanobot_agent_builder_tools.py)
   - 补当前线程 / 当前 spec 的 Agent Builder 经验读取行为测试
   - 验证与 prompt template 工具链组合时不会破坏现有 thread_context 解析
4. [scripts/validate_agent_builder_project_memory_loop.py](../../../scripts/validate_agent_builder_project_memory_loop.py)
   - 保留现有 L4 验证脚本，不与 L6 混写
5. 建议新增 `scripts/validate_agent_builder_l6_lesson_loop.py`
   - 覆盖“写入 lesson -> 迭代前召回 -> 注入 prompt”最小闭环
6. 建议新增 [tests/scripts/test_validate_agent_builder_l6_lesson_loop.py](../../../tests/scripts/test_validate_agent_builder_l6_lesson_loop.py)
   - 对脚本做受控回归，避免后续只有单测没有端到端闭环验证

#### 第一批建议提交顺序

为了降低一次性改动面，建议按下面顺序拆批实现：

1. 先改 memory scope / router / service 基础约束
2. 再给 `evaluate_version(...)` 增加 lesson 写入 helper
3. 再给迭代入口增加 lesson recall helper
4. 再把 lesson guidance 接到 Embedded Nanobot governance 路径
5. 最后补脚本与测试，把 L6 闭环单独跑绿

### P1-1 完成标准

1. Agent 生成有明确可写可读的经验层。
2. 至少 1 条生成/迭代链路能消费它。
3. 文档中不再只能说“Agent 生成主链路更偏 L2/L3/L7”，而能补上稳定的 L6 角色。
4. 至少 1 组测试能证明 lesson 真正进入构建或迭代输入，而不是只完成存储。

---

## 4.2 P1-2 建立记忆观测面板与关键指标

### P1-2 目标

把“记忆是否工作”从日志感知升级为指标感知。

### P1-2 建议观测项

1. 写入侧：
   - 写入成功率
   - facts_extracted 分布
   - infer 失败比例
2. 召回侧：
   - 召回命中率
   - 空召回率
   - metadata 过滤命中率
   - 平均注入字符数
3. 消费侧：
   - 注入后是否进入 prompt
   - 被消费链路数
   - 召回无效场景数

### P1-2 完成标准

1. 关键指标有统一日志字段或统计入口。
2. 能区分写入失败、召回失败、消费失败三类问题。
3. 后续优化不再只能靠人工翻日志判断。

### P1-2 当前状态

当前仍未完成。现阶段主要依赖脚本验证和零散日志，尚未形成统一指标入口、固定 dashboard 或标准化埋点字段。

---

## 4.3 P1-3 扩展 object_key / object_type 到更多对象

### P1-3 目标

让记忆系统不再只对股票对象效果最好，而是能逐步覆盖更多业务对象。

### P1-3 当前问题

当前 object 绑定对股票最成熟，但在 Agent、Skill、Workflow、Prompt Template 等对象上还不够统一。

### P1-3 建议扩展顺序

1. `stock`
2. `agent_spec`
3. `agent_version`
4. `workflow`
5. `skill`
6. `template`

### P1-3 完成标准

1. 至少补齐 1 到 2 个非股票对象类型。
2. 这些对象的 recall 能基于 object 维度做精确过滤。
3. 文档中能明确这些对象属于 L4 / L5 / L6 中的哪一层，而不是混到 L7。

### P1-3 当前状态

当前属于部分完成：

1. `workflow` / `trade_review` 已经开始进入 object binding 范围
2. `agent_spec` / `agent_version` / `template` 仍未形成统一 object recall 约束
3. 因此这项还不能算完成，只能算“已经离开纯股票单对象阶段”

---

## 5. P2：本版本可做可不做

## 5.1 P2-1 继续收紧术语边界

### P2-1 目标

减少团队讨论时把“状态、资产、记忆”混在一起。

### P2-1 建议内容

1. 在文档和日志里持续强调：
   - `thread_context` 是 L7
   - `memory_state_manager` 是 L7
   - Session / Spec / Version 是资产，不是长期记忆
2. 逐步收紧命名与文档口径。

### P2-1 说明

这项很重要，但不应压过 P0/P1 的功能闭环。

---

## 5.2 P2-2 为下个版本清理做准备，而不是现在就清理

### P2-2 目标

为下个版本删旧代码、切工坊生成 Agent 做准备，但本版本不提前扩散处理。

### P2-2 建议内容

1. 记录仍保留的 legacy memory 面。
2. 标注哪些路径已不影响新流程。
3. 为下个版本保留清理清单，但本版本不强推落地。

---

## 6. 后续推荐顺序

| 顺序 | 任务 | 理由 |
| ------ | ------ | ------ |
| 1 | P1-1 Agent 生成经验层 | 当前最明确的结构缺口，且直接影响工坊复用能力 |
| 2 | P1-2 观测指标 | 没有统一指标，后续 recall 优化很难量化比较 |
| 3 | P1-3 对象扩展 | 为 agent / template / workflow 级 recall 打基础 |
| 4 | P2-1 术语边界 | 防止状态、资产、记忆继续混用 |
| 5 | P2-2 清理准备 | 为下个版本的 legacy 清理保留可执行清单 |

这个顺序的核心是：

- 先优化现在已经在跑的主路径
- 再补结构缺口
- 最后扩展更广的对象能力

---

## 7. 验收口径

当前版本记忆系统优化完成，不以“代码更统一”作为主要标准，而以以下标准判断：

1. 智能助手、股票分析、Skill 生成、成长记忆至少各有一条真实消费闭环。
2. L5/L6 召回质量可被样本或指标证明提升。
3. L4 不再只是概念，而是至少有一条最小可用链路。
4. Agent 生成开始具备专门的长期经验沉淀能力。
5. 团队能清楚区分 L4/L5/L6 与 L7，而不会再把状态层混进记忆系统讨论。

### 7.1 当前复核结果

按上述口径复核，当前状态应表述为：

1. 第 1 条已完成。
2. 第 2 条已完成第一轮，仍缺统一观测指标。
3. 第 3 条已完成。
4. 第 4 条未完成，这正是当前最重要的 P1 缺口。
5. 第 5 条已在文档与实现边界上明显收紧，但仍需持续维护口径。

---

## 8. 一句话版

当前版本记忆系统优化，当前更准确的说法是：

1. L4 最小闭环已经补齐
2. L5/L6 召回质量与消费闭环已经完成首轮落地
3. 下一个最重要的缺口是 Agent 生成专用 L6、统一观测和跨对象扩展
