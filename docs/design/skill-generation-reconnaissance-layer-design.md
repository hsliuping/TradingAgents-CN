# Skill 生成前置侦察层设计

## 1. 背景与问题定义

配套专题目录：

- [同步运行时接口专题总览](runtime-interfaces/README.md)
- [Skill 运行时同步接口总览](runtime-interfaces/skill-runtime-overview.md)
- [本地数据库访问接口设计](runtime-interfaces/local-data-access-design.md)
- [项目查询接口与暴露治理](runtime-interfaces/project-access-and-governance.md)

当前 Skill 生成管线的核心流程是：需求分析 -> 代码生成 -> 静态验证 -> 沙箱执行 -> 输出评估 -> 迭代修复。

这套流程在以下场景中工作良好：

- 目标明确，数据路径简单
- runtime 公开接口已经足够完整
- Prompt 中已经清晰给出字段、接口和约束

但在估值类 Skill，尤其是 PEG / PB / DCF / 行业相对估值等场景中，当前模式暴露出明显短板：

1. 代码生成器是闭卷式生成
   - 当前 `core/tools/external/code_generator.py` 仅基于 Prompt 注入的文档与上下文生成代码。
   - 生成阶段没有工具调用能力，无法主动查证接口签名、字段口径、集合结构和历史实现。

2. 估值任务高度依赖“事实探索”
   - 例如：`stock_financial_data` 的实际字段覆盖率、`net_income` 与 `net_profit` 的主口径、外部财务接口返回单条摘要还是历史列表、某个 helper 是否真的适合历史增长率计算。
   - 这些问题本质上属于“先探索、再实现”，而不是“直接生成函数”。

3. 当前迭代是“写错后再修”，不是“确认事实后再固化”
   - 生成器只能根据失败反馈重写代码。
   - 如果失败根因来自接口认知错误、字段猜测错误或 runtime 能力缺口，单纯重写代码通常无法稳定收敛。

4. 当前评估器更接近“程序是否可运行”，不是“业务目标是否完成”
   - 例如 PEG 主结果为空但结构完整时，现有评估仍可能给出偏高分。

结论：

当前 Skill 生成系统缺少一个“前置侦察层”，用于在代码生成前，先把本次任务所需的实现事实查清楚并结构化输出，再由代码生成器将其固化为 Skill。

## 2. 设计目标

前置侦察层的目标不是直接生成最终 Skill 代码，而是为代码生成阶段提供经过查证的实现事实。

具体目标：

1. 提升复杂 Skill 的首次生成成功率
2. 减少因字段猜测、接口误解、返回结构误判导致的反复重写
3. 让代码生成器从“闭卷猜实现”升级为“基于事实编译实现”
4. 为 runtime 能力缺口提供明确诊断，反向指导 `core/skill_runtime` 演进
5. 在不放开高风险写权限的前提下，给生成链路增加必要的只读探索能力

非目标：

1. 不在侦察层直接写入 Skill 代码文件
2. 不让侦察层直接修改数据库或项目源码
3. 不让侦察层绕过 `skill_runtime` 公开接口直接决定最终上线实现
4. 不把侦察层做成一个无限权限 Agent

## 3. 核心思路

将当前单阶段“需求分析后直接 codegen”改为双阶段：

1. 侦察阶段（Reconnaissance）
   - 输入：`SkillSpec`
   - 能力：只读检索、受限验证、结构化归纳
   - 输出：`ImplementationFactReport`

2. 固化阶段（Codegen + Validation）
   - 输入：`SkillSpec` + `ImplementationFactReport`
   - 能力：受限代码生成、静态验证、沙箱执行、业务验收、迭代修复
   - 输出：最终 Skill 代码与元数据

本质上：

- 侦察层解决“这次任务应该怎么做”
- 固化层解决“把已确认路径写成稳定 Skill”

## 4. 总体架构

```text
用户需求
  -> RequirementAnalyzer
  -> SkillSpec
  -> ReconnaissanceController
      -> 只读工具集 / 受限验证工具
      -> ImplementationFactReport
  -> CodeGenerator
      -> Prompt = SkillSpec + FactReport + runtime docs
  -> StaticValidator
  -> SandboxRunner
  -> BusinessVerifier
  -> IterationController
  -> Skill 入库 / 快照落盘
```

与当前系统的关系：

- 保留现有 `RequirementAnalyzer`
- 保留现有 `CodeGenerator`
- 保留现有 `StaticValidator`
- 保留现有 `SandboxRunner`
- 保留现有 `IterationController`
- 新增侦察层与业务验收层
- 让 `IterationController` 在第 1 轮前先获取事实报告，并在后续重试中持续复用

## 5. 侦察层的角色定义

侦察层应实现为“只读、可审计、结构化输出”的受限 Agent，而不是自由写代码的全权限 Agent。

### 5.1 输入

- `SkillSpec`
- 当前运行时公开接口文档
- 可选：历史失败反馈、历史同类 Skill 快照、用户指定的数据源偏好

### 5.2 输出

侦察层必须输出结构化事实报告，而不是只输出自然语言长文。建议数据结构如下：

```json
{
  "task_summary": "本次 Skill 要完成的核心能力",
  "recommended_strategy": "推荐实现路径",
  "available_helpers": [
    {
      "module": "core.skill_runtime.data_access",
      "name": "get_stock_valuation_context",
      "reason": "可直接提供现价与估值上下文"
    }
  ],
  "schema_facts": [
    {
      "source": "stock_financial_data",
      "fact": "净利润主字段常见为 net_profit，net_income 为辅口径"
    }
  ],
  "sample_fields": {
    "stock_financial_data": ["symbol", "report_period", "report_type", "net_profit", "net_income", "net_profit_yoy"]
  },
  "blocked_paths": [
    {
      "path": "direct provider import",
      "reason": "违反 runtime 公开接口约束"
    }
  ],
  "runtime_gaps": [
    {
      "gap": "缺少历史财务序列 helper",
      "impact": "PEG 的 CAGR 方案不稳定"
    }
  ],
  "validation_checks": [
    "PEG success 时 peg_value 不可为空",
    "growth_rate 不可为空",
    "validity_status=false 时不能包装成 success"
  ],
  "confidence": 0.86
}
```

### 5.3 不允许的输出形态

- 仅有自然语言总结，无结构化字段
- 直接输出完整 Python 代码替代后续 codegen
- 直接给出未查证的 provider 猜测路径

## 6. 推荐开放的侦察工具

侦察层建议仅开放只读和低风险验证能力。

### 6.1 代码与文档检索工具

用途：定位 runtime helper、provider 签名、已有实现、设计文档。

建议工具：

1. 文件读取
2. 目录浏览
3. 文本搜索
4. 语义搜索

可用于：

- 查看 `core/skill_runtime/*.py`
- 查看 `tradingagents/dataflows/providers/**/*.py`
- 查看 `docs/api/`、`docs/design/`、`docs/analysis/`
- 查找已有 PB / PEG / 财务分析实现

### 6.2 数据契约工具

用途：查看数据库集合的真实字段分布与样本结构。

建议新增工具：

1. `inspect_collection_schema(collection, sample_size=20)`
   - 返回常见字段、字段出现频率、样本记录片段

2. `inspect_symbol_documents(collection, symbol, limit=5)`
   - 返回指定标的的样本数据结构

3. `inspect_field_coverage(collection, fields)`
   - 返回若干候选字段在样本中的覆盖率

这类工具对估值类 Skill 非常关键，因为很多错误来自“字段名看起来像对，实际覆盖率很差”。

### 6.3 运行时契约工具

用途：查证项目内已有 helper 与 provider 的真实签名与返回结构。

建议新增工具：

1. `describe_runtime_helper(module, name)`
   - 返回函数签名、docstring、所在文件位置

2. `describe_provider_method(provider, method)`
   - 返回方法签名和项目内实现位置

3. `find_existing_implementations(query)`
   - 在项目中寻找相近的财务分析、估值、增长率处理逻辑

### 6.4 受限验证工具

用途：用最小范围验证“实现路径是否成立”。

建议新增工具：

1. `probe_runtime_helper(helper_name, args)`
   - 只调用白名单 helper
   - 返回结果结构摘要，而不是完整大量数据

2. `probe_collection_query(collection, filters, projection, limit)`
   - 只允许只读查询

3. `probe_symbol_path(symbol, scenario)`
   - 对典型 symbol 执行受限场景探针，例如“PEG 增长率路径验证”

说明：

- 不建议在侦察层直接放开任意 shell
- 不建议直接放开任意 Python 执行
- 不建议直接放开任意第三方网络请求

## 7. 侦察 Prompt 设计原则

侦察 Agent 的 Prompt 不应要求它“写代码”，而应要求它“查事实、收敛路径、输出结构化结论”。

应明确要求：

1. 优先确认 runtime 公开接口是否足够
2. 如果不够，指出缺口，不要直接建议绕过公开接口成为最终实现
3. 所有关键判断都要附带证据来源
4. 输出必须归纳为结构化字段，供 codegen 消费
5. 不允许把“可能存在”的方法当成已验证事实

建议 Prompt 关注以下问题：

1. 本次任务的主计算路径是什么
2. 当前 runtime 中哪些 helper 可直接复用
3. 哪些字段是主口径，哪些只是候选口径
4. 哪些外部接口可作为侦察依据，但不能作为最终 Skill 直接依赖
5. 如果当前 runtime 能力不足，最小缺口是什么

## 8. CodeGenerator 如何消费事实报告

`CodeGenerator` 不应再只依赖 `SkillSpec + 文档片段`，而应变为：

- `SkillSpec`
- `ImplementationFactReport`
- runtime 公开接口文档
- 失败反馈（重试场景）

Prompt 中应新增一个显式部分：

```text
【已查证实现事实】
- 推荐路径: ...
- 可直接使用的 helper: ...
- 已确认字段: ...
- 禁止路径: ...
- runtime 缺口: ...

请严格基于这些已查证事实生成代码，不要自行猜测新的 provider 路径或字段口径。
```

这样代码生成器的角色从“探索 + 实现”收缩为“基于事实实现”。

## 8.1 当前实现中的数据库访问链路

除了“侦察先于固化”的总体设计原则，当前代码实现还明确规定了生成 Skill 访问数据库的正式路径。

这一部分需要单独写清楚，否则容易误解成“LLM 在生成代码时自己创建 MongoClient 直连数据库”。当前实现并不是这样。

### 8.1.1 生成代码只能通过 skill_runtime 公开接口访问项目数据

当前 Skill 代码生成 Prompt 已明确注入两类运行时文档：

1. `core.skill_runtime.data_access`
2. `core.skill_runtime.project_access`

它们是生成 Skill 在运行时访问项目数据和项目能力的正式公开门面。

约束如下：

1. 若需要本地股票数据库数据，优先使用 `core.skill_runtime.data_access`
2. 若需要通用集合查询、只读 schema 侦察、外部数据源同步 wrapper，则使用 `core.skill_runtime.project_access`
3. 不允许直接导入 `tradingagents.dataflows.interface`
4. 不允许直接导入 `tradingagents.dataflows.providers.*`
5. 不允许直接导入 `core.skill_runtime.catalog`、`external_sources`、`sync_wrappers` 等内部细分模块作为最终 Skill 依赖
6. 不允许自行 `import pymongo` / `MongoClient`
7. 不允许硬编码数据库名或手写新的数据库连接逻辑

换言之，生成 Skill 查询 MongoDB 的正确方式，不是自己建连接，而是调用 skill_runtime 中已经公开并约束好的 helper。

### 8.1.2 代码生成阶段如何获得这些约束

当前 `CodeGenerator` 在系统 Prompt 中会注入：

1. 本地数据访问文档
2. 项目数据访问文档
3. 股票集合目录与数据契约
4. 外部数据源目录

因此，生成器不是在“闭眼猜数据库结构”，而是在已有运行时文档和侦察结论的基础上生成代码。

对估值类与财务类 Skill，生成器当前会优先引导使用如下 helper：

1. `get_stock_basic_info(...)`
2. `get_stock_daily_quotes(...)`
3. `get_market_quotes(...)`
4. `get_latest_stock_price(...)`
5. `get_stock_financial_data(...)`
6. `get_stock_financial_periods(...)`
7. `get_stock_valuation_context(...)`
8. `summarize_industry_valuation(...)`
9. `query_stock_collection(...)`
10. `aggregate_stock_collection(...)`

这意味着“数据库访问能力”本质上已经被收口成一组受控的运行时 API，而不是交由生成代码自由发挥。

### 8.1.3 侦察层如何辅助数据库访问路径选择

当前侦察层的数据库相关工具，职责不是替代最终 Skill 查询数据库，而是帮助确认：

1. 允许访问哪些集合
2. 集合中真实有哪些字段
3. 字段覆盖率是否足够支撑目标实现
4. 某只股票在对应集合中的样本结构是什么

典型侦察能力包括：

1. `list_supported_stock_collections()`
2. `inspect_stock_collection_schema(...)`
3. `inspect_symbol_documents(...)`
4. `inspect_field_coverage(...)`
5. `describe_runtime_helper(...)`
6. `list_runtime_functions(...)`

因此当前链路是：

1. 侦察层确认集合、字段、helper 是否存在
2. 事实报告给出推荐实现路径
3. CodeGenerator 基于事实报告和 skill_runtime 文档生成代码
4. 最终 Skill 通过公开 helper 间接访问数据库

### 8.1.4 静态验证如何强制执行这条规则

当前实现不是只靠 Prompt 约束，还增加了静态验证硬规则。

静态验证器会：

1. 仅允许导入 `core.skill_runtime.data_access`
2. 仅允许导入 `core.skill_runtime.project_access`
3. 拒绝直接导入 `tradingagents.dataflows.providers.*`
4. 拒绝直接导入 `tradingagents.dataflows.interface`
5. 拒绝其他未允许的 `core.*` 模块

因此，哪怕模型在生成代码时尝试绕过公开接口，静态验证阶段也会阻止这类实现进入后续执行和注册环节。

### 8.1.5 沙箱执行与正式注册时的运行方式

当前生成 Skill 不会在主进程内直接 `exec`，而是：

1. 在沙箱子进程中执行验证
2. 通过项目根目录注入 `PYTHONPATH`
3. 在正式启用后，再以独立包装函数方式注册到 `external_skills` 运行链路

这意味着生成代码里对 `core.skill_runtime.*` 的导入，在沙箱验证阶段和正式注册阶段都应保持一致。

因此只要 helper 能在主项目中正常工作，生成 Skill 在运行时就可以通过这些 helper 间接查询真实 MongoDB 数据。

### 8.1.6 当前设计与代码一致性的结论

当前代码实现与本文档在以下方面是一致的：

1. 最终 Skill 不应直接连接 MongoDB
2. 最终 Skill 必须通过 `core.skill_runtime` 公开接口获取数据库数据
3. 侦察层负责确认字段与 helper 事实，而不是直接产出绕过约束的实现
4. 静态验证器会强制阻止越界导入
5. 沙箱执行与正式注册都依赖同一套项目运行时导入路径

当前真正需要持续演进的，不是放宽生成代码的数据库权限，而是持续补齐 `core.skill_runtime.data_access` 与 `core.skill_runtime.project_access` 中的高频 helper。这样复杂 Skill 才能在不绕过设计边界的前提下稳定访问数据库中的股票数据。

## 9. 业务验收层设计

引入侦察层后，仍需新增业务验收层，防止“代码能跑但业务目标未完成”。

### 9.1 原则

不同类型的 Skill 需要不同的完成判定规则。

对估值类 Skill，不应只看：

- 返回结构不为空
- status 是 success
- 函数能执行

还要看核心业务字段是否有效。

### 9.2 估值类验收规则示例

PEG 类：

1. `status == success` 时，`data.peg_value` 不可为空
2. `status == success` 时，`data.growth_rate` 不可为空
3. `status == success` 时，`data.valuation_level` 不可为空
4. 若 `data.validity_status == false`，则不得视为业务完成

PB / PE 相对估值类：

1. 必须返回当前估值指标
2. 必须返回区间或相对判断结果
3. 数据不足时可返回 invalid / error，但不得包装为成功完成

DCF 类：

1. 缺少关键输入时必须显式 invalid
2. 不允许输出 `fair_value = 0` 伪装完成

### 9.3 验收实现方式

建议新增 `BusinessVerifier` 层：

- 输入：`SkillSpec` + `SandboxResult`
- 输出：
  - `passed`
  - `rule_failures`
  - `business_score`

该层与当前 `OutputEvaluator` 并列，而不是完全替代。

建议链路：

1. `StaticValidator` 检查语法与依赖约束
2. `SandboxRunner` 检查可执行性
3. `OutputEvaluator` 检查通用格式与基础质量
4. `BusinessVerifier` 检查业务完成度

最终通过条件应调整为：

- 静态验证通过
- 沙箱执行成功
- 通用评分达标
- 业务验收通过

## 10. 推荐实施方案

### Phase 1：文档与接口收敛

目标：先不改 Agent 工具能力，只定义好数据结构与接入点。

任务：

1. 定义 `ImplementationFactReport` 数据模型
2. 在 `CodeGenerator` Prompt 中预留事实报告区块
3. 定义 `BusinessVerifier` 接口与估值类规则协议

### Phase 2：只读侦察 MVP

目标：先用最小只读工具集跑通侦察层。

建议工具：

1. 文件读取
2. 文本搜索
3. 语义搜索
4. runtime helper 描述
5. 集合 schema 查看

产出：

- 侦察层能输出结构化事实报告
- codegen 能消费事实报告

### Phase 3：受限验证与领域验收

目标：让侦察层能做最小验证，让估值类结果具备业务硬约束。

任务：

1. 增加 helper 探针工具
2. 增加集合样本 / 覆盖率工具
3. 实现 `BusinessVerifier`
4. 为 PEG / PB / DCF 增加首批领域规则

### Phase 4：runtime 能力反哺

目标：把侦察层反复暴露的缺口，固化为正式 runtime helper。

例如：

1. 历史财务序列 helper
2. 增长率计算 helper
3. 行业估值对比 helper
4. 估值场景标准输入 helper 扩充

## 11. 风险与边界

### 11.1 风险：侦察层变成无限权限 Agent

控制方式：

- 默认只开放只读工具
- 探针工具白名单化
- 明确禁止写文件、改代码、写数据库

### 11.2 风险：侦察结果过长，反而污染 Prompt

控制方式：

- 强制结构化输出
- 限制每类字段的最大条数
- 只保留与本次 Skill 直接相关的事实

### 11.3 风险：侦察结论和最终运行时约束冲突

控制方式：

- 在事实报告中区分：
  - 可作为最终实现路径
  - 仅作为侦察证据，不可直接用于最终 Skill

### 11.4 风险：业务验收规则过死，误杀合理降级

控制方式：

- 允许 `invalid` / `error` 明确返回
- 只禁止“主结果未完成却伪装 success”

## 12. 与 nanobot 思路的关系

本方案借鉴 nanobot 的不是其 evaluator，而是其“先探索、再完成”的工作模式。

需要明确：

1. nanobot 的 AgentRunner 更擅长任务求解，而不是 Skill 业务验收
2. nanobot 的 evaluator 主要解决通知门控，不适合作为 Skill 正确性判定器
3. 本方案吸收其工具增强式探索思路，但保持当前系统对 Skill 上线质量的更强约束

因此，本方案不是照搬 nanobot，而是：

- 用 nanobot 风格的侦察能力，增强 Skill 生成前的事实获取
- 用 TradingAgentsCN 自己的静态验证、沙箱、业务验收，保障最终 Skill 质量

## 13. 推荐落地结论

建议将 Skill 生成系统从“单阶段闭卷 codegen”升级为“双阶段：侦察 -> 固化”的体系。

优先级建议：

1. 先定义 `ImplementationFactReport` 与 `BusinessVerifier` 接口
2. 先做只读侦察层 MVP
3. 先接入估值类 Skill（PEG / PB / DCF）做试点
4. 再逐步把反复暴露的缺口固化进 `core/skill_runtime`

这样可以同时解决两个核心问题：

1. 生成器在复杂估值场景中缺少事实支撑
2. 评估器无法稳定识别“业务未完成却结构完整”的假阳性

最终目标不是让生成器拥有更大自由，而是让它在更充分、可查证的事实基础上，产出更稳定、更符合业务目标的 Skill。
