# 项目查询接口与暴露治理

## 1. 定位

`core.skill_runtime.project_access` 是 Skill 运行时的项目公开门面，承担两类职责：

1. 为生成 Skill 提供通用只读查询与聚合入口。
2. 为侦察层提供 schema、字段覆盖率、样本文档等诊断能力。

当前治理范围先以 A 股本地集合为准，不在这一轮同时放开多市场集合暴露。

它和 `data_access` 的区别在于：

1. `data_access` 偏业务语义 helper。
2. `project_access` 偏通用查询和运行时公共门面。

## 2. 当前公开能力

当前 `project_access` 公开了五类能力：

1. `query_stock_collection(...)`
2. `aggregate_stock_collection(...)`
3. `inspect_stock_collection_schema(...)`
4. `inspect_symbol_documents(...)`
5. `inspect_field_coverage(...)`

此外，它还暴露了外部数据源同步 wrapper：

1. `list_configured_external_sources(...)`
2. `get_external_stock_news(...)`
3. `get_external_historical_data(...)`
4. `get_external_financial_data(...)`
5. `get_external_query_news(...)`

## 3. 为什么需要单独一层 project_access

不是所有能力都适合进入 `data_access`。

一些场景天然更适合由 `project_access` 承担：

1. 工坊侦察阶段查看集合结构。
2. 生成 Skill 在 helper 不足时做通用只读查询。
3. 对外部数据源做同步桥接，避免 Skill 直接碰异步 provider。
4. 对后续 Agent/embedded nanobot 开放受控的项目级公共能力。

## 4. 当前集合暴露策略

当前 `project_access` 通过 `catalog` 里的白名单控制允许查询的集合。

在当前阶段，这份白名单应优先服务 A 股分析型场景，尤其是价格、新闻、财务快照、财务按期记录等核心集合。

这层白名单的作用不是限制开发效率，而是保证：

1. 生成 Skill 不会误读不稳定或不适合公开的集合。
2. 侦察层和正式 Skill 使用同一套能力边界。
3. 后续要收权限时有明确收口点。

因此，任何新增集合暴露都不应直接修改 Prompt，而应按下面顺序进行：

1. 更新 `core.skill_runtime.catalog`
2. 确认 `project_access` 是否需要新增查询/聚合约束
3. 更新 `PROJECT_DATA_ACCESS_DOC`
4. 更新本专题文档

当前已经应纳入这一链路的 A 股集合包括 `stock_financial_periods`，因为它已是基本面多期分析的标准公开口径。

## 5. 静态校验与暴露治理

当前系统不是只靠文档约束，而是通过静态验证器强制执行以下规则：

1. 只允许生成 Skill 导入 `core.skill_runtime.data_access`
2. 只允许生成 Skill 导入 `core.skill_runtime.project_access`
3. 拒绝导入 `tradingagents.dataflows.providers.*`
4. 拒绝导入 `tradingagents.dataflows.interface`
5. 拒绝导入其他未显式允许的 `core.*` 模块

因此，新增公开接口时要特别注意：

1. 只有真正准备长期维护的能力，才应该暴露到这两层。
2. 一旦暴露，就意味着后续生成 Skill 会依赖它。
3. 暴露前要想清楚命名、参数、返回结构和可维护性。

## 6. 新增能力的推荐流程

后续新增新的同步运行时能力，推荐按以下流程处理：

1. 明确需求属于哪类：高频 helper、通用查询、侦察能力、外部源桥接。
2. 如果属于高频股票分析语义，优先加到 `data_access`。
3. 如果属于通用查询或诊断，优先加到 `project_access`。
4. 如果涉及新增集合，先更新 `catalog` 白名单。
5. 更新 `LOCAL_DATA_API_DOC` 或 `PROJECT_DATA_ACCESS_DOC`。
6. 更新本专题目录文档。
7. 如果影响 Skill 工坊 Prompt 或静态校验规则，同步更新相关实现与设计文档。

## 7. 给后续 nanobot / Agent 打通预留的接口策略

这个专题目录不仅服务 Skill 工坊，也是在为后续 embedded nanobot、Agent 工坊接入项目原生能力做准备。

建议未来沿用同一原则：

1. 先暴露同步运行时门面，再让上层 Agent 调用。
2. 不让上层 Agent 直接摸底层数据库和 provider。
3. 新能力先收口到 `skill_runtime` 或同层级的受控门面，再向 Agent 注册。

这样后续新增股票机器人能力时，不需要每次重新设计一套“能不能直接调用底层模块”的边界。
