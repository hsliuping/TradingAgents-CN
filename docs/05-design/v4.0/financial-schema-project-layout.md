# TradingAgents v4.0 设计：金融 Schema 独立项目拆分方案

## 文档信息

| 项目 | 内容 |
| ---- | ---- |
| 版本 | v4.0 Design Draft |
| 状态 | 设计中 |
| 日期 | 2026-03-29 |
| 目标 | 为金融知识 Schema 后续独立立项提供项目拆分、目录结构、发布方式和协作边界建议 |

---

## 1. 结论

建议不要把“Schema 规范”和“Schema 内容”继续长期放在同一个业务主仓库里维护。

更适合的拆分方式是三层：

1. schema-spec 仓库
   - 负责定义对象类型、字段、枚举、引用规则、版本兼容规则

2. schema-content 仓库
   - 负责按 schema-spec 约束收集和维护实际金融知识内容

3. TradingAgents 主仓库
   - 负责消费发布后的 schema bundle，并接入 verifier、skill generation、assistant 等业务模块

这样拆分的好处是：

- 规范和内容不会互相污染
- 主仓库不会被大量知识条目拖慢维护
- 内容团队和工程团队可以并行协作
- 未来如果要引入外部知识采集团队，协作边界清晰

---

## 2. 推荐仓库结构

### 2.1 schema-spec 仓库

推荐定位：规范仓库，只管标准，不管海量内容。

推荐目录：

```text
financial-schema-spec/
  README.md
  docs/
    object-model.md
    versioning.md
    review-workflow.md
  schemas/
    common/
      base-object.schema.json
      enums.schema.json
    concept/
      concept-definition.schema.json
    metric/
      metric-definition.schema.json
    field/
      field-semantics.schema.json
    method/
      method-definition.schema.json
    applicability_rule/
      applicability-rule.schema.json
    output_contract/
      output-contract.schema.json
    verifier_rule/
      verifier-rule.schema.json
  examples/
    valuation-core/
  tools/
    validate_bundle.py
    validate_object_refs.py
  tests/
    test_schema_validation.py
```

职责边界：

- 定义对象模型
- 维护 JSON Schema 或等价校验定义
- 提供示例和校验工具
- 提供版本升级说明
- 不直接收集大规模业务内容

### 2.2 schema-content 仓库

推荐定位：内容仓库，只管知识对象内容，不管业务运行逻辑。

推荐目录：

```text
financial-schema-content/
  README.md
  docs/
    authoring-guide.md
    review-checklist.md
    source-citation-policy.md
  bundles/
    valuation-core/
      bundle.yaml
    dividend-core/
      bundle.yaml
    quality-core/
      bundle.yaml
  schemas/
    concept/
    metric/
    field/
    method/
    applicability_rule/
    output_contract/
    verifier_rule/
  sources/
    public/
    licensed/
  tests/
    test_bundle_integrity.py
    test_cross_reference_integrity.py
    fixtures/
```

职责边界：

- 维护具体对象文件
- 管理来源引用和证据
- 管理对象状态和版本
- 打包发布 bundle
- 不承担业务代码、模型编排、在线服务逻辑

### 2.3 TradingAgents 主仓库

推荐定位：消费端仓库。

推荐接入目录：

```text
TradingAgentsCN/
  core/
    knowledge/
      financial_schema_registry.py
      financial_schema_loader.py
      financial_schema_models.py
  app/
    services/
      schema_bundle_service.py
  tests/
    knowledge/
      test_financial_schema_registry.py
```

职责边界：

- 加载 bundle
- 按场景查询 schema 对象
- 对接 verifier、assistant、skill generation
- 不负责大规模内容编辑

---

## 3. 推荐发布方式

建议发布最小单位不是“单文件”，而是 bundle。

例如：

- valuation-core
- dividend-core
- financial-statement-core
- banking-valuation-core

每个 bundle 至少包含：

- 概念定义
- 指标定义
- 方法定义
- 适用性规则
- 输出契约
- 验收规则

这样主仓库接入时可以按功能分批启用，而不是一次吞下全部知识。

---

## 4. 推荐协作流程

### 4.1 schema-spec 流程

1. 提交对象模型变更提案
2. 评估是否影响现有内容兼容性
3. 更新 schema 校验器
4. 发布新 spec 版本

### 4.2 schema-content 流程

1. 新增或修改对象内容
2. 补充来源引用
3. 跑对象结构校验
4. 跑交叉引用校验
5. 跑场景样例测试
6. 生成 bundle 版本

### 4.3 主仓库接入流程

1. 锁定要消费的 bundle 版本
2. 加载 bundle 并建立 registry
3. 为 verifier 或 skill 生成增加查询桥接
4. 用场景用例验证效果

---

## 5. 内容项目的最小可用目录

如果现在就要快速新开一个项目，建议先从下面这个最小目录开始：

```text
financial-schema-content/
  README.md
  bundles/
    valuation-core/
      bundle.yaml
  schemas/
    concept/
      concept.pe.yaml
      concept.pb.yaml
      concept.peg.yaml
    metric/
      metric.pe_ttm.yaml
      metric.pb.yaml
      metric.peg_basic.yaml
    method/
      method.pe_relative_valuation.yaml
      method.pb_relative_valuation.yaml
      method.peg_growth_valuation.yaml
    applicability_rule/
      rule.pe_requires_positive_earnings.yaml
      rule.pb_preferred_for_banks.yaml
      rule.peg_requires_meaningful_growth.yaml
    output_contract/
      contract.valuation.pe_basic.yaml
      contract.valuation.pb_basic.yaml
      contract.valuation.peg_basic.yaml
    verifier_rule/
      verifier.valuation.pe_basic.yaml
      verifier.valuation.pb_basic.yaml
      verifier.valuation.peg_basic.yaml
  tests/
    fixtures/
```

这个结构已经足够支撑第一阶段收集工作。

---

## 6. 版本策略建议

建议同时维护三种版本：

1. spec_version
2. content_version
3. bundle_version

示例：

- spec_version: 1.0.0
- content_version: 2026.04
- bundle_version: valuation-core@1.0.0

主仓库消费时，应显式记录：

- 依赖哪个 spec_version
- 使用哪个 bundle_version

---

## 7. 你们当前阶段的建议决策

结合当前进度，建议这样推进：

1. 先用主仓库里的设计文档冻结 schema 方向
2. 立刻按本文目录新开 schema-content 项目
3. 第一批只收集 valuation-core
4. TradingAgents 主仓库暂时只消费 bundle，不在主仓库中继续堆大量内容条目

---

## 8. 最终建议

如果你们接下来只做一个独立项目，优先级应该是 schema-content，而不是 schema-spec。

原因是：

- 当前对象模型已经初步收敛
- 最紧迫的是开始把内容按统一结构收集起来
- spec 仓库可以稍后再独立拆分

也就是说，短期最务实路线是：

1. 主仓库保留设计文档
2. 新建 financial-schema-content 项目
3. 先做 valuation-core 样例和内容沉淀
4. 后续再把规范工具链上收成独立 schema-spec
