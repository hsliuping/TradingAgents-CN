# TradingAgents v4.0 设计：金融 Schema Bundle 消费接入

## 文档信息

| 项目 | 内容 |
| ---- | ---- |
| 版本 | v4.0 Design Draft |
| 状态 | 设计中 |
| 日期 | 2026-03-29 |
| 目标 | 定义 TradingAgents 主仓库如何消费外部 financial-schema-content 项目发布的 bundle，并给出最小代码接入路径 |

---

## 1. 目标

当前主仓库已经具备：

- 文档型金融知识检索能力
- 智能助手知识注入能力
- Skill 生成与 business verifier 骨架

但对于新的结构化金融知识 Schema，主仓库目前还没有统一的消费入口。

本设计的目标是：

1. 让主仓库可以加载外部 schema-content 项目产出的 bundle
2. 在主仓库内建立统一的 registry 和 service
3. 不立即强耦合到 assistant、verifier、skill generation
4. 为后续逐步接入各条业务链路提供稳定基础

---

## 2. 推荐接入方式

当前阶段推荐采用“静态 bundle 消费”方式，而不是 MCP 远程查询。

原因：

1. 工程复杂度更低
2. 版本锁定更清晰
3. 排障更容易
4. 不引入额外服务依赖

推荐路径：

1. 外部 schema-content 仓库产出 bundle.yaml 和对象文件
2. 主仓库通过 loader 读取 bundle
3. registry 统一管理对象索引
4. service 为业务模块提供查询接口

---

## 3. 当前阶段的接入边界

本次接入只做四件事：

1. 定义结构化对象模型
2. 实现 bundle loader
3. 实现 registry
4. 提供 service 层包装

本次不直接实现：

1. assistant 自动路由到 schema
2. verifier 自动执行 schema rule
3. skill generation 自动注入 schema 对象
4. MCP 远程拉取 schema

---

## 4. 推荐代码位置

### 4.1 core/knowledge

用于放结构化知识的加载和索引能力：

- financial_schema_models.py
- financial_schema_loader.py
- financial_schema_registry.py

职责：

- 定义对象模型
- 读取 YAML bundle 和对象文件
- 建立对象索引
- 提供通用查询能力

### 4.2 app/services

用于放业务侧调用入口：

- schema_bundle_service.py

职责：

- 维护 loader 和 registry 生命周期
- 提供主仓库各业务模块的统一访问入口
- 提供 bundle summary 和按类型查询等能力

---

## 5. 推荐数据流

### 5.1 初始化阶段

```text
bundle.yaml -> FinancialSchemaLoader -> LoadedFinancialSchemaBundle -> FinancialSchemaRegistry -> SchemaBundleService
```

### 5.2 查询阶段

```text
assistant/verifier/skill_service -> SchemaBundleService -> FinancialSchemaRegistry -> FinancialSchemaObject
```

---

## 6. 对外暴露的最小能力

当前阶段建议暴露以下接口：

1. load_bundle(manifest_path)
2. load_bundles(manifest_paths)
3. get_object(object_id)
4. get_objects_by_type(object_type)
5. has_object(object_id)
6. get_bundle_summary(bundle_id)
7. list_bundles()

这些能力已经足够支撑后续接入：

- assistant 查 concept 或 method
- verifier 查 output_contract 和 verifier_rule
- skill generation 查 method、rule、contract

---

## 7. 后续接入顺序建议

### Phase 1：接 registry 和 service

目标：

- 能读 bundle
- 能查对象
- 能查看 bundle 摘要

### Phase 2：接 verifier

目标：

- business verifier 可按场景读取 output_contract 和 verifier_rule

### Phase 3：接 skill generation

目标：

- 生成时注入 method、applicability_rule、output_contract

### Phase 4：接 intelligent assistant

目标：

- 对“概念定义 / 指标怎么计算 / 方法是否适用”类问题优先走 schema registry

### Phase 5：可选 MCP 化

目标：

- 当多个项目都要共享同一套 schema 内容时，再将 schema-content 服务化

---

## 8. 与现有文档知识的关系

主仓库未来应同时存在两套知识入口：

1. FinancialKnowledgeManager
   - 负责文档片段检索
   - 适合背景知识、说明文档、案例文本

2. FinancialSchemaRegistry
   - 负责结构化金融知识对象
   - 适合概念、指标、方法、规则、契约、验收条件

两者不是替代关系，而是互补关系。

---

## 9. 最终结论

当前项目应优先支持“bundle 消费”，而不是直接跳到远程知识服务。

所以本次落地推荐是：

1. 在 core/knowledge 新增 loader、registry、models
2. 在 app/services 新增 schema_bundle_service
3. 保持业务接入延后，但先把基础设施落稳

这条路径最稳，也最适合你们当前阶段逐步把结构化金融知识接回主项目。
