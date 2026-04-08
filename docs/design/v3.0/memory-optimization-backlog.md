# v3.0 记忆系统优化待办清单

## 📋 文档信息

| 项目 | 内容 |
| ------ | ------ |
| 版本 | v1.0 |
| 状态 | 当前版本执行清单 |
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

| 优先级 | 主题 | 目标 |
| ------ | ------ | ------ |
| P0 | L4 + L5/L6 质量 + 消费闭环 | 先让现有主链路真的稳定可用 |
| P1 | Agent 生成经验层 + 观测 + 对象扩展 | 提升复用能力与可观测性 |
| P2 | 术语收口与后续清理准备 | 降低未来版本改造成本 |

一句话理解：

- **P0 解决“现在能不能稳定用”**
- **P1 解决“后面能不能越用越聪明”**
- **P2 解决“下个版本能不能更轻松继续演进”**

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

当前已经接通 mem0 主路径，但还缺：

1. 跨线程召回质量的端到端评估
2. 更细粒度的 metadata 过滤策略
3. object_key 向非股票对象扩展后的质量验证

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

## 4. P1：当前版本建议完成

## 4.1 P1-1 为 Agent 生成补专用 L6 经验层

### P1-1 目标

让 Agent 生成不再只依赖 L2/L3 会话记忆和 L7 上下文绑定，而是拥有可复用的经验沉淀层。

### P1-1 当前问题

目前 Skill 生成已有 `skill_lesson`，但 Agent 生成还没有等价的经验 scope。现在 Nanobot / Agent Workshop 的失败经验、调试经验、提示词迭代经验，还没有形成下一次生成可直接复用的长期经验。

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

### P1-1 完成标准

1. Agent 生成有明确可写可读的经验层。
2. 至少 1 条生成/迭代链路能消费它。
3. 文档中不再只能说“Agent 生成主链路更偏 L2/L3/L7”，而能补上稳定的 L6 角色。

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

## 6. 推荐执行顺序

| 顺序 | 任务 | 理由 |
| ------ | ------ | ------ |
| 1 | P0-2 L5/L6 召回质量 | 这是当前最直接影响输出质量的部分 |
| 2 | P0-3 消费闭环验证 | 先确认记忆真的被用到了 |
| 3 | P0-1 L4 最小闭环 | 补上当前最明显的结构缺口 |
| 4 | P1-1 Agent 生成经验层 | 提升工坊与 Nanobot 的长期复用能力 |
| 5 | P1-2 观测指标 | 让后续优化可量化 |
| 6 | P1-3 对象扩展 | 为跨对象记忆打基础 |

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

---

## 8. 一句话版

当前版本记忆系统优化，先做三件事：

1. 让 L5/L6 召回真正稳定可用
2. 让记忆真正被消费而不是只写入
3. 补齐 L4 和 Agent 生成经验层这两个结构缺口
