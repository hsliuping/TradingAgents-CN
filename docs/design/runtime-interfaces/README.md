# 同步运行时接口专题

本专题目录专门用于沉淀 Skill 运行时可调用的同步接口设计、数据库访问暴露方式、沙箱执行约束，以及后续新增能力时的接口治理规则。

这个目录的目标不是重复 API 文档，而是把“生成代码到底允许调用什么、为什么这样暴露、如何继续扩展”这条设计链路单独收口，避免信息散落在 Skill 工坊、侦察层、运行时实现和问题修复文档中。

当前这一轮能力收口先聚焦 A 股本地数据与分析场景，不扩展多市场能力设计，避免在运行时公开接口层过早引入不一致口径。

## 适用范围

本专题主要覆盖以下代码与场景：

- `core.skill_runtime.data_access`
- `core.skill_runtime.project_access`
- `core.skill_runtime.catalog`
- `core.tools.external.code_generator`
- `core.tools.external.static_validator`
- `core.tools.external.sandbox_runner`
- `core.tools.external_skill_loader`

对应使用方包括：

- Skill 工坊代码生成
- Skill 侦察层 schema/字段核验
- 沙箱执行与外部 Skill 热注册
- 后续 embedded nanobot / Agent 工坊接入业务能力时的运行时接口暴露

## 文档索引

1. [skill-runtime-overview.md](skill-runtime-overview.md)
说明同步运行时接口的整体分层、调用链路和约束边界。

2. [local-data-access-design.md](local-data-access-design.md)
说明 `data_access` 如何暴露本地 MongoDB 股票数据 helper，适用哪些高频股票分析场景。

3. [project-access-and-governance.md](project-access-and-governance.md)
说明 `project_access` 的通用查询、侦察接口、静态校验与新增能力的暴露治理规则。

## 当前设计结论

当前系统已经形成一条明确路径：

1. 生成代码不能自己创建数据库连接。
2. 生成代码必须通过 `core.skill_runtime` 的同步公开接口访问项目数据。
3. 侦察层负责确认集合、字段、helper 是否真实存在。
4. 静态验证器负责阻止绕过公开接口的实现。
5. 沙箱执行和正式注册都依赖同一套同步运行时导入路径。

后续若要新增股票机器人能力，应优先扩展本专题目录描述的接口层，而不是让生成代码直接接触新的底层模块。

在当前阶段，这里的“新增能力”默认指 A 股能力增补，例如价格、财务按期记录、新闻、估值与行业分析相关 helper / 查询门面。
