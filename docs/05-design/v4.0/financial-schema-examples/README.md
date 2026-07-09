# 金融 Schema 样例包

本目录用于提供一组最小可用的金融 Schema 样例，方便后续：

- 新建独立 schema-content 项目时直接复用目录结构
- 作为首批人工采集和审阅模板
- 作为主仓库后续实现 FinancialSchemaRegistry 时的测试样本

当前样例范围只覆盖 valuation-core：

- PE
- PB
- PEG

覆盖对象类型包括：

- concept
- metric
- method
- applicability_rule
- output_contract
- verifier_rule

样例文件均采用 YAML，便于人工维护和代码评审。
