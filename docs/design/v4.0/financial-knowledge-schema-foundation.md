# TradingAgents v4.0 设计：金融知识 Schema 基础层

## 文档信息

| 项目 | 内容 |
|------|------|
| 版本 | v4.0 Design Draft |
| 状态 | 设计中 |
| 日期 | 2026-03-29 |
| 目标 | 设计一套独立于模型和具体产品流程的金融知识 Schema，作为后续知识内容建设、业务验收、技能生成和智能助手的统一基础 |

---

## 1. 背景

当前仓库已经具备以下能力：

- 文档型金融知识检索：由 core/knowledge/financial_knowledge_manager.py 和 core/knowledge/knowledge_data.py 承接
- 用户偏好和仓库事实记忆：由 /memories 和相关运行时机制承接
- Skill 生成过程事实、评估和验收：由 core/tools/external 下的生成管线承接
- 智能助手的知识注入与记忆拼装：由 app/services/intelligent_assistant_service.py 承接

但当前系统仍然缺少一层更底层的能力：

- 没有统一、稳定、可版本化的金融概念定义
- 没有统一、稳定、可版本化的指标语义定义
- 没有把“什么时候适用某种方法”沉淀为结构化规则
- 没有把“输出应该长什么样”和“如何验收”沉淀为结构化契约
- 没有把知识内容和运行时事实彻底分层

这导致系统虽然有知识、有记忆、有向量检索，但仍然容易出现以下问题：

- 同一金融概念在不同 Prompt、不同 Agent、不同 Skill 中口径不一致
- LLM 在生成和反思阶段对方法适用性产生冲突判断
- business verifier 缺少足够强的、可执行的金融规则来源
- 后续如果要独立建设金融知识内容库，缺少统一 Schema 作为约束

因此，v4.0 先不讨论外部知识底座接入，而是先定义内部统一的金融知识 Schema。

---

## 2. 设计目标

### 2.1 核心目标

这套 Schema 要解决四个核心问题：

1. 定义什么是系统里的“标准金融知识对象”
2. 让知识内容可以独立采集、独立版本化、独立发布
3. 让业务逻辑可以消费结构化知识，而不是只消费文档片段
4. 让 verifier、Skill 生成、智能助手和后续 Agent 系统共享同一套知识语义

### 2.2 非目标

本设计当前不解决以下问题：

- 不直接替代现有文档型 RAG 检索系统
- 不直接替代 MongoDB 中的业务真相源数据
- 不直接实现完整金融知识采集平台
- 不试图一次覆盖全部金融概念
- 不把模型微调作为本阶段主方案

---

## 3. 设计原则

### 3.1 规范知识、记忆、事实三层分离

系统内的信息必须至少拆成三层：

1. 规范知识层
   - 回答“定义是什么、规则是什么、方法什么时候适用”
   - 是版本化、可审阅、可发布的系统资产

2. 记忆层
   - 回答“用户偏好是什么、系统积累了什么经验、某个仓库有哪些注意事项”
   - 是长期经验，不是金融真理源

3. 运行时事实层
   - 回答“这次任务里看到了什么、生成了什么、失败在哪里”
   - 是任务现场产物，不是标准知识

### 3.2 文档和结构化对象并存，但职责不同

- 文档适合承接说明、背景、案例、长文解释
- 结构化对象适合承接概念定义、字段语义、规则、契约、验收条件

未来系统应允许同一个金融主题同时存在：

- 一个结构化对象
- 多个支持性文档
- 多个正反案例
- 多个版本

### 3.3 先定义 Schema，再收集内容

本阶段优先级应是：

1. 先确定对象类型和字段含义
2. 再建立内容采集规范
3. 最后再建设大规模内容库

否则内容会先于规则增长，最终无法治理。

### 3.4 规则必须可执行，不只可阅读

Schema 中的规则定义不能只是自然语言描述，还必须能被程序消费。

至少要满足：

- 可定位作用对象
- 可表达适用条件
- 可表达禁止条件
- 可表达输出要求
- 可表达校验方式

---

## 4. 系统分层定位

建议把未来金融知识基础设施划分为四层：

### 4.1 Layer A：规范 Schema 层

这一层负责定义对象类型、字段、版本和规则表达方式。

输出物包括：

- Schema 类型定义
- 字段说明
- 枚举集合
- 版本规范
- 发布规范

### 4.2 Layer B：知识内容层

这一层负责填充实际金融知识内容，例如：

- PE 的定义
- PB 的定义
- PEG 的定义
- 银行股优先看 PB 的适用规则
- 负利润时 PE 不可直接使用的约束规则

这一层非常适合后续拆成独立项目维护。

### 4.3 Layer C：知识服务层

这一层负责把结构化知识提供给主业务系统消费。

可以提供：

- 按 id 查询
- 按别名查询
- 按标签查询
- 按场景检索适用方法
- 获取 verifier 规则
- 获取输出契约

### 4.4 Layer D：业务消费层

包括但不限于：

- Skill 生成
- business verifier
- 智能助手
- Agent 工坊
- 单股分析
- benchmark 与评估数据集

---

## 5. 核心 Schema 对象

建议首期定义 7 类核心对象。

### 5.1 ConceptDefinition

用于定义金融概念本身。

典型对象：

- PE
- PB
- PEG
- ROE
- 股息率
- 自由现金流
- 破净
- 周期股

建议字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 全局唯一 id，例如 concept.pe |
| name | string | 标准名称 |
| aliases | array[string] | 别名和常见中文表达 |
| category | string | concept 分类，例如 valuation_metric、financial_statement、market_term |
| summary | string | 一句话定义 |
| definition | string | 完整定义 |
| interpretation | string | 如何解释这个概念 |
| common_misunderstandings | array[string] | 常见误解 |
| related_concepts | array[string] | 关联概念 id |
| tags | array[string] | 标签 |
| status | string | draft、active、deprecated |
| version | string | 语义版本号 |
| evidence_refs | array[string] | 证据或参考资料引用 |

### 5.2 MetricDefinition

用于定义“指标”及其计算口径。

典型对象：

- 静态 PE
- TTM PE
- PB
- ROE
- 毛利率
- 净利率
- 股息率

建议字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 全局唯一 id，例如 metric.pe_ttm |
| name | string | 指标名 |
| formula | string | 人类可读公式 |
| machine_formula | object | 机器可消费公式表达 |
| numerator | array[string] | 分子字段 id |
| denominator | array[string] | 分母字段 id |
| unit | string | 单位或倍率 |
| frequency | string | annual、quarterly、ttm、instant |
| preconditions | array[string] | 前置条件 |
| invalid_conditions | array[string] | 无效条件 |
| interpretation_guidelines | array[string] | 解读指南 |
| related_concepts | array[string] | 关联概念 |
| version | string | 版本 |

### 5.3 FieldSemantics

用于定义结构化财务字段、行情字段和派生字段的语义。

典型对象：

- financial.net_profit_parent_company
- financial.book_value_per_share
- market.close_price
- financial.operating_cashflow

建议字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 字段唯一 id |
| name | string | 字段名称 |
| source_system | string | 来源系统，例如 tushare、qmt、internal_financial_cache |
| source_field | string | 来源字段名 |
| semantic_type | string | raw_fact、derived_fact、market_fact |
| definition | string | 字段定义 |
| value_type | string | number、string、boolean、date 等 |
| unit | string | 单位 |
| time_semantics | string | point_in_time、period、ttm |
| null_semantics | string | 缺失值含义 |
| caveats | array[string] | 使用注意事项 |
| aliases | array[string] | 别名 |
| version | string | 版本 |

### 5.4 MethodDefinition

用于定义某一类分析方法。

典型对象：

- valuation.pe_relative
- valuation.pb_relative
- valuation.peg_growth
- dividend.yield_screening

建议字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 方法唯一 id |
| name | string | 方法名 |
| family | string | valuation、quality、growth、income 等 |
| objective | string | 这个方法用来解决什么问题 |
| required_metrics | array[string] | 依赖指标 id |
| required_fields | array[string] | 依赖字段 id |
| steps | array[string] | 分析步骤 |
| assumptions | array[string] | 核心假设 |
| strengths | array[string] | 优势 |
| limitations | array[string] | 局限 |
| common_failure_modes | array[string] | 常见失败模式 |
| output_contract_ids | array[string] | 对应输出契约 |
| verifier_rule_ids | array[string] | 对应验收规则 |
| version | string | 版本 |

### 5.5 ApplicabilityRule

用于定义“什么时候适用 / 不适用某种方法或指标”。

这是当前系统最缺的一层。

典型对象：

- rule.pe_requires_positive_earnings
- rule.pb_preferred_for_banks
- rule.peg_requires_meaningful_growth_rate

建议字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 规则唯一 id |
| target_type | string | metric、method、concept |
| target_id | string | 规则作用对象 id |
| rule_kind | string | required、preferred、forbidden、warning |
| condition_expr | object | 机器可消费条件表达式 |
| human_description | string | 人类可读规则描述 |
| severity | string | info、warning、error |
| rationale | string | 规则原因 |
| examples | array[string] | 示例 |
| exceptions | array[string] | 例外情况 |
| version | string | 版本 |

condition_expr 建议支持最小表达能力，例如：

- field_exists
- field_gt
- field_gte
- field_lt
- field_lte
- industry_in
- industry_not_in
- all_of
- any_of
- not

### 5.6 OutputContract

用于定义某类金融分析结果应该输出什么结构。

典型对象：

- contract.valuation.pe_basic
- contract.valuation.pb_bank
- contract.screening.dividend_quality

建议字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 契约唯一 id |
| name | string | 契约名称 |
| scenario | string | 适用场景 |
| required_fields | array[object] | 必填输出字段定义 |
| optional_fields | array[object] | 可选输出字段定义 |
| narrative_requirements | array[string] | 叙述性要求 |
| prohibited_patterns | array[string] | 不允许出现的模式 |
| example_payload | object | 示例输出 |
| version | string | 版本 |

required_fields 中建议至少包含：

- field_name
- field_type
- description
- nullable
- source_requirement

### 5.7 VerifierRule

用于定义可执行的业务验收规则。

典型对象：

- verifier.valuation.pe_has_positive_earnings_basis
- verifier.valuation.must_include_method_limitations
- verifier.valuation.must_report_comparison_benchmark

建议字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 规则唯一 id |
| scenario | string | skill_generation、assistant_answer、analysis_report 等 |
| target_contract_id | string | 对应输出契约 |
| check_type | string | required_field、formula_consistency、applicability_check、non_empty、enum_check 等 |
| rule_level | string | output、data、reasoning、method |
| blocking | boolean | 是否阻断 |
| params | object | 校验参数 |
| failure_message | string | 失败提示 |
| remediation_hint | string | 修复建议 |
| version | string | 版本 |

---

## 6. 统一元数据规范

所有 Schema 对象建议共享一组基础元数据，以便未来拆成独立知识项目后仍能统一治理。

建议公共字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 全局唯一标识 |
| object_type | string | 对象类型 |
| name | string | 主显示名称 |
| version | string | 当前版本 |
| status | string | draft、active、deprecated |
| owner | string | 责任团队或维护人 |
| review_status | string | unreviewed、reviewing、approved |
| source_refs | array[string] | 来源材料 |
| created_at | string | 创建时间 |
| updated_at | string | 更新时间 |
| effective_from | string | 生效时间 |
| effective_to | string | 失效时间，可为空 |
| locale | string | zh-CN、en-US |

---

## 7. Schema 存储形态建议

### 7.1 首期推荐：文件化 Schema 仓库

建议首期采用文件化存储，每个对象单独成文件，使用 JSON 或 YAML 管理。

推荐目录形态：

```text
financial-knowledge-schema/
  schemas/
    concept/
    metric/
    field/
    method/
    applicability_rule/
    output_contract/
    verifier_rule/
  bundles/
    valuation-core/
    dividend-core/
    quality-core/
  docs/
  tests/
```

这样做的原因：

- 易于代码评审
- 易于版本控制
- 易于单条对象追踪变更
- 易于独立开新项目维护

### 7.2 主仓库内的消费方式

TradingAgents 主仓库不一定需要直接维护大量知识内容，但需要维护：

- Schema 加载器
- Schema 校验器
- Schema 查询接口
- 与 verifier、assistant、skill pipeline 的桥接层

---

## 8. 与当前仓库的集成边界

### 8.1 对 core/knowledge/knowledge_data.py 的影响

当前 knowledge_data.py 适合继续承接说明性文档、工具指南和背景知识。

后续应把其中可结构化的内容逐步抽出到 Schema 内容库，例如：

- PE/PB/ROE 的概念定义
- 分红策略的规则化部分
- 财报字段和报表语义

而文档部分继续保留，用于：

- RAG 检索
- 解释性注入
- 给模型提供背景说明

### 8.2 对 core/knowledge/financial_knowledge_manager.py 的影响

当前管理器适合继续作为“文档知识检索器”。

后续建议新增并行能力，而不是直接替换：

- FinancialKnowledgeManager：负责文档检索
- FinancialSchemaRegistry：负责结构化 schema 对象加载和查询

### 8.3 对 core/tools/external/business_verifier.py 的影响

当前 verifier 的可执行规则类型较少。

后续应改造成：

1. 从 Schema Registry 获取场景相关的 verifier_rule 和 output_contract
2. 把 ApplicabilityRule 作为 method 检查前置条件
3. 把 OutputContract 作为输出结构验收依据
4. 把 VerifierRule 转换为具体执行逻辑

### 8.4 对 Skill 生成链路的影响

Skill 生成后续应不再只依赖文档型知识注入，而要同时注入：

- 方法定义
- 适用规则
- 输出契约
- 验收规则
- 正反案例

### 8.5 对智能助手的影响

智能助手后续可按问题类型路由：

- 解释概念：查 ConceptDefinition
- 查询指标怎么计算：查 MetricDefinition 和 FieldSemantics
- 询问某方法是否适用：查 MethodDefinition 和 ApplicabilityRule
- 需要详细背景：再回退到文档型知识库

---

## 9. 独立项目拆分建议

用户后续提出“可能需要另外做一个项目，专门来收集这个 schema 当中的内容”，这是合理方向。

建议拆成两个职责清晰的部分：

### 9.1 主仓库职责

TradingAgentsCN 主仓库负责：

- 定义和冻结 Schema 标准
- 提供 Schema Loader 和 Registry
- 提供运行时查询与消费接口
- 提供校验器和测试框架
- 决定哪些场景接入哪些 schema 对象

### 9.2 独立内容仓库职责

独立项目负责：

- 按 Schema 标准收集金融知识内容
- 维护对象版本
- 提供审阅、修订、废弃流程
- 维护来源和证据链接
- 输出可发布 bundle

### 9.3 推荐拆分模式

建议采用：

- schema-spec 仓库：只维护 Schema 标准和校验规范
- schema-content 仓库：维护具体金融知识内容
- TradingAgents 主仓库：消费发布后的 bundle

这样可以避免：

- 主业务仓库被大量知识条目淹没
- 运行逻辑和知识内容耦合
- 后续知识内容协作困难

---

## 10. 首批范围建议

不建议首期从“全金融知识”切入，建议先做估值和财务语义核心集。

### 10.1 首批 ConceptDefinition

- PE
- PB
- PEG
- ROE
- 股息率
- 自由现金流
- 市净率破净
- 周期股
- 银行股
- 证券股

### 10.2 首批 MetricDefinition

- pe_static
- pe_ttm
- pb
- roe
- dividend_yield
- free_cash_flow

### 10.3 首批 MethodDefinition

- pe_relative_valuation
- pb_relative_valuation
- peg_growth_valuation
- dividend_yield_screening

### 10.4 首批 ApplicabilityRule

- 净利润小于等于零时禁止直接使用 PE
- 银行、保险、券商优先使用 PB 或 ROE 衍生口径
- PEG 需要有效增长率且增长不可为极端异常值
- 周期股单独提示盈利波动风险

### 10.5 首批 OutputContract

- PE 估值技能输出契约
- PB 估值技能输出契约
- PEG 估值技能输出契约

### 10.6 首批 VerifierRule

- 必须说明使用的估值口径
- 必须说明适用前提是否满足
- 必须输出关键计算依据字段
- 必须说明方法局限性或风险点

---

## 11. 版本治理与发布规范

### 11.1 版本维度

建议至少管理三种版本：

1. Schema 规范版本
2. 内容版本
3. 发布 bundle 版本

例如：

- Schema Spec: 1.0.0
- Content Package: 2026.04
- Bundle: valuation-core@1.0.0

### 11.2 兼容性原则

- 新增字段：向后兼容
- 字段改名：必须走 major version
- 删除字段：必须走废弃期
- 规则语义变化：必须记录变更原因

### 11.3 审阅机制

建议每条核心对象至少经过：

1. 内容编写
2. 业务审阅
3. 技术校验
4. 发布入 bundle

---

## 12. 测试策略

Schema 不只是文档资产，还应当具备测试。

建议至少包含三类测试：

### 12.1 结构测试

- 对象字段完整性
- 枚举值合法性
- 引用对象存在性

### 12.2 规则测试

- ApplicabilityRule 条件表达式可解析
- VerifierRule 参数可执行
- OutputContract 字段定义可映射到验证器

### 12.3 场景测试

用少量标准样本验证：

- 某个 PE 估值案例在规则满足时能通过
- 某个负利润公司案例能被规则阻止错误使用 PE
- 某个银行股案例能正确提示 PB 更优先

---

## 13. 分阶段实施建议

### Phase 1：先出 Schema 规范

本阶段完成：

- 冻结对象类型
- 冻结核心字段
- 冻结版本规范
- 冻结 bundle 结构

### Phase 2：建立独立内容仓库

本阶段完成：

- 建立 schema-content 仓库
- 按首批范围收集内容
- 建立审阅流程
- 建立基础测试

### Phase 3：主仓库消费接入

本阶段完成：

- 新增 FinancialSchemaRegistry
- verifier 接入 VerifierRule 和 OutputContract
- skill generation 接入 MethodDefinition 和 ApplicabilityRule
- assistant 增加结构化知识路由

---

## 14. 最终结论

对于 TradingAgents 来说，金融知识 Schema 不应被视为 Skill 生成的局部补丁，而应被视为系统级基础设施。

它的职责不是替代模型，而是定义模型必须遵守的金融知识边界。

它的职责不是替代记忆，而是为记忆和运行时事实提供统一的金融语义锚点。

它的职责不是替代文档知识库，而是把最关键、最容易冲突、最需要可执行的金融知识沉淀成稳定对象。

因此，推荐路线是：

1. 先在主仓库内冻结 Schema 设计
2. 再拆出独立内容项目维护具体金融知识条目
3. 最后逐步接入 verifier、skill generation、assistant 和评估体系

这条路线比先堆知识文档、再事后治理更稳，也更适合你们后续做成长期基础层。