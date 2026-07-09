# v3.0 记忆功能现状与优先级评估

## 文档信息

| 项目 | 内容 |
| ------ | ------ |
| 日期 | 2026-04-09 |
| 状态 | 现状复核 |
| 目的 | 回答“记忆功能是否已经全部实现”以及“下一步是继续补记忆，还是切回 v3.0 主业务功能” |
| 关联文档 | [memory-optimization-backlog.md](./memory-optimization-backlog.md)、[memory-capability-layer-mapping.md](./memory-capability-layer-mapping.md)、[memory-recall-quality-implementation-plan.md](./memory-recall-quality-implementation-plan.md)、[implementation-status-report.md](./implementation-status-report.md) |

---

## 1. 结论先行

### 1.1 记忆功能是不是都实现了

不是。

更准确的表述是：

1. **当前版本最关键的记忆主链已经实现并可验证**。
2. **P0 基本完成，P1 部分完成，P2 大多未开始或只做了口径收紧**。
3. **还没有达到“全系统所有记忆功能点全部完工”的状态**。

### 1.2 下一步应该继续补记忆，还是切回 v3.0 主业务功能

建议：**主节奏切回 v3.0 主要业务功能，记忆转入“保守补强”模式**。

原因很直接：

1. 记忆最容易出假闭环的部分已经做实。
2. 继续深挖记忆，接下来大多是观测面、对象扩展、平台化收口，边际收益开始下降。
3. v3.0 主业务功能还有更直接影响用户价值和交付成熟度的缺口，例如 Agent 工坊发布治理、生产反馈闭环、ETF 产品层成熟度、分层提示词完全落地等。

建议资源分配：

1. **70%~80% 精力切回 v3.0 主业务功能**。
2. **20%~30% 精力保留给记忆的低成本补强和回归维护**。

---

## 2. 当前已完成的记忆主链

下面这些不是“概念上接了”，而是已经有代码、测试或脚本回归支撑。

### 2.1 L4 项目长期记忆最小闭环

已完成：

1. 项目级稳定规则的写入、读取、prompt block 构建。
2. 智能助手消费 L4 项目长期记忆。
3. Agent Builder governance / Agent Workshop 模板链路消费 L4。
4. production-review 与发布前校验模板或运行时 prompt 是否真实绑定了当前 L4。
5. 脚本级验证已覆盖写入 -> 读取 -> prompt 注入。

### 2.2 L5/L6 召回质量增强

已完成：

1. `MemoryService.recall()` 支持 exact filter 下推、本地 metadata 过滤、统一重排、去重后截断。
2. `MemoryService.recall_formatted()` 支持 `ranking_profile`、`group_by_scope`、`per_scope_limit`。
3. assistant / analysis / skill_generation 已切到 profile 化召回主路径。
4. 已有脚本化评估样本，不再只是“mem0 返回非空就算成功”。

### 2.3 四条主链路的消费闭环

已完成：

1. 智能助手消费历史记忆。
2. 股票分析消费分析记忆与成长记忆。
3. 成长记忆 approve 后可被后续 workflow 再消费。
4. Skill 生成消费 `skill_lesson`。

### 2.4 Agent Builder 专用 L6 经验层最小闭环

已完成：

1. 新增 `agent_builder_lesson` scope 与 `agent_builder` ranking profile。
2. Agent Workshop 评估后可写入 `agent_builder_lesson`。
3. 版本迭代前可读取 lesson 并注入 prompt template。
4. runtime governance 路径可读取 lesson 并叠加到 L4 之后。

### 2.5 lesson 消费点前移

已完成：

1. requirement clarification 接入 lesson。
2. gap analysis 接入 lesson。
3. build_version 接入 lesson。
4. sync_version_required_tools 接入 lesson。
5. iteration prompt clone 接入 lesson。
6. runtime governance 接入 lesson。

### 2.6 最小统一观测与脚本化摘要

已完成：

1. Agent Workshop 与 runtime governance 两侧都已记录 lesson recall observation。
2. observation 至少覆盖 `source_stage`、`status(hit/miss/error)`、query/result preview、metadata_filters、user/spec/version 上下文。
3. `validate_agent_workshop_l6_forward_consumption_loop.py` 已校验三段前移消费点的 observation。
4. `validate_agent_workshop_governance_l4_l6_loop.py` 已校验 runtime governance 的 observation。
5. `run_governance_validations.py` 已输出：
   - 每个 validator 的 `details.checks`
   - `details.observation_summary`
   - `details.recall_summary`
   - 顶层 `observation_aggregate`
   - 顶层 `stage_ranking`

---

## 3. 当前还没有全部完成的部分

这些才是“还不能说记忆已经全部做完”的主要原因。

### 3.1 统一观测还不是完整平台能力

当前状态：

1. 已有脚本摘要和 JSON 聚合。
2. 还没有真正的 dashboard、长期趋势面板或统一告警入口。
3. 还不能方便地回答“最近一周哪个 stage 的 miss 在上升”。

结论：

这说明**观测可用，但还不是完整平台化观测**。

### 3.2 跨对象 object recall 仍不完整

当前状态：

1. 股票相关对象和 Agent Workshop 这条线已经开始做 object 绑定。
2. 更广的 `agent_spec` / `agent_version` / `template` / `workflow` 等对象还没有形成统一 recall 约束体系。

结论：

这说明**对象扩展还在早中期，不是完整覆盖**。

### 3.3 不是所有业务链路都稳定依赖同一套记忆层

当前状态：

1. 智能助手、分析、Skill 生成、Agent Workshop 主链已经接入。
2. 但“全系统所有入口”并没有全部统一到同样的 L4/L5/L6 策略。

结论：

这说明**主链已打通，但不是全局统一平台**。

### 3.4 Agent 生成的经验层还没走到“全面成熟”

当前状态：

1. 专用 L6 已存在。
2. 关键消费点已打通。
3. 但还缺更广对象样本、更丰富 lesson 类型和更完整的生产反馈回流。

结论：

这说明**已经从 0 到 1，但还没到 1 到 N**。

### 3.5 文档与代码口径仍有少量滞后

当前状态：

1. 部分旧文档仍保留“Agent Builder 经验层尚未落地”的旧表述。
2. 近期实现主要通过新增状态文档、脚本和 repo memory 做了收口。

结论：

这说明**需要继续收口，但不构成主功能阻塞**。

---

## 4. 哪些记忆工作可以暂时不优先

如果目标是尽快推进 v3.0 产品成熟度，下面这些事情可以先不作为主线：

1. 为所有链路做统一可视化 dashboard。
2. 大规模扩散到所有 object_type / object_key 的 recall 体系。
3. 为了术语整洁继续大规模重命名老 memory 代码。
4. 把 Nanobot 本地 MEMORY/HISTORY 彻底平台化替换掉。
5. 为观测做复杂的指标体系或 BI 报表。

这些不是没价值，而是：

1. 当前主链已经可用。
2. 继续深挖它们的收益，短期低于补业务闭环的收益。

---

## 5. 站在 v3.0 全局视角，当前更值得补的主业务缺口

结合 [implementation-status-report.md](./implementation-status-report.md) 的现状，当前更值得优先推进的是以下几类。

### 5.1 Agent 工坊的发布治理与生产反馈闭环

当前状态：

1. Agent 工坊的规格澄清、缺口分析、版本构建、调试、评估、迭代、发布主链已经实现。
2. 但**发布审批、灰度发布、生产反馈回流**仍未完成。

优先级判断：高。

原因：

1. 这是从“能做出来”到“能正式上线和持续演进”的关键一步。
2. 用户能直接感知这条能力是否成熟。
3. 它和当前已完成的记忆链天然配套，补完后 memory 的价值也更容易真正闭环。

### 5.2 ETF 产品层成熟度

当前状态：

1. ETF 数据同步和基础工作流已接入。
2. 但产品层成熟度仍弱于普通股票主流程。

优先级判断：中高。

原因：

1. 这是明显的产品可见能力差距。
2. 相比继续深挖记忆观测，这类补强更容易带来用户感知价值。

### 5.3 分层提示词架构的完全落地

当前状态：

1. prompt assembly 与 injection policy 已存在。
2. 但与“五层提示词架构”的完整对照仍是部分实现。

优先级判断：中高。

原因：

1. 它直接影响稳定性、可控性和 prompt 维护成本。
2. 这是主业务能力质量的底座，不只是记忆功能的附属问题。

### 5.4 Gateway 的飞书 / 钉钉适配器

当前状态：

1. QQ 已实现。
2. 飞书、钉钉仍未实现。

优先级判断：取决于产品渠道目标。

如果近期重心是扩渠道接入，这个优先级会明显高于继续深挖记忆观测。

---

## 6. 建议的实际决策

### 6.1 推荐路线

建议采用下面的节奏：

1. **把记忆从“主线开发”切到“保守补强 + 回归维护”**。
2. **把主要研发节奏切回 Agent 工坊与 v3.0 主业务成熟度**。

### 6.2 为什么不是继续把记忆做满

因为当前再继续深挖记忆，主要会落在：

1. 更漂亮的观测面
2. 更广的对象覆盖
3. 更完整的平台化统一

这些都重要，但它们更偏“平台完善”，不是当前最紧迫的用户价值缺口。

### 6.3 为什么也不是完全停掉记忆

因为当前记忆主链刚刚做实，完全停掉会有两个风险：

1. 后续业务改动可能把这条闭环悄悄冲坏。
2. Agent 工坊后续补生产反馈闭环时，仍然需要这条经验层做承接。

所以更合理的方式是：

1. **不再把记忆当第一主线继续挖深**。
2. **但保留低成本的脚本回归、口径同步和必要补丁**。

---

## 7. 推荐的下一步顺序

如果只给一个建议顺序，我建议：

1. **先转回 Agent 工坊发布治理 / 生产反馈闭环**。
2. **然后补 ETF 产品层成熟度或分层提示词架构**。
3. **记忆只保留两类工作**：
   - 新业务改动后同步补脚本回归
   - 修正真正影响主链的 recall / observation 问题

### 7.1 可以保留的记忆维护清单

记忆这边后续只保留小步快跑的事项：

1. 新增业务链路若消费 lesson，就补进 governance runner。
2. 若出现 miss / error 样本，再补 observation summary 的可解释性。
3. 继续收口旧文档里的过时口径。

### 7.2 不建议再作为主线展开的记忆事项

1. 单独做大规模 memory dashboard 项目。
2. 先于业务需求做全对象 recall 平台化改造。
3. 先于业务闭环做术语或代码清洁型重构。

---

## 8. 一句话版本

**当前记忆不是“全部做完了”，而是“关键主链已经做实了”；接下来更合理的策略不是继续把记忆当第一主线挖深，而是把主节奏切回 v3.0 业务成熟度，同时保留少量记忆补强与回归维护。**
