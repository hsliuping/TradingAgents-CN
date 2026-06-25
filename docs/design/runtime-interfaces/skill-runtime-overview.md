# Skill 运行时同步接口总览

## 1. 为什么单独做同步接口层

Skill 工坊生成出来的代码最终运行在独立 Python 子进程中，执行入口是同步函数，而不是 FastAPI 请求上下文里的异步函数。

因此，生成 Skill 需要一个稳定、低耦合、可被静态校验的同步运行时门面，用来承接以下需求：

1. 访问本地 MongoDB 中已同步的股票数据。
2. 在必要时调用外部数据源的同步 wrapper。
3. 允许侦察层只读查看 schema、字段覆盖率和样本文档。
4. 避免生成代码自行创建数据库连接、臆造 provider 调用路径或直接导入项目内部实现。

这就是 `core.skill_runtime` 存在的核心原因。

## 2. 当前分层

当前同步运行时接口分成两层：

1. `core.skill_runtime.data_access`
面向高频股票分析场景的专用 helper，优先提供“拿来即用”的同步能力。

2. `core.skill_runtime.project_access`
面向通用集合查询、侦察、外部数据源同步 wrapper 的项目公开门面。

此外还有一层元数据目录：

1. `core.skill_runtime.catalog`
描述允许暴露的本地集合、优选 helper、外部数据源市场支持范围。

## 3. 当前调用链路

```text
SkillSpec
  -> ReconnaissanceController
      -> recon_tools
      -> core.skill_runtime.project_access / catalog
  -> CodeGenerator
      -> 注入 LOCAL_DATA_API_DOC / PROJECT_DATA_ACCESS_DOC
  -> StaticValidator
      -> 仅允许导入 data_access / project_access
  -> SandboxRunner
      -> 子进程导入 core.skill_runtime.*
  -> external_skill_loader
      -> 正式注册后仍通过同一套导入路径执行
```

这条链路说明：

1. 侦察层与最终 Skill 共享同一套运行时能力事实。
2. Prompt 约束、静态校验、沙箱执行和正式注册使用的是同一套接口边界。
3. 新增能力时应优先考虑补齐 `skill_runtime`，而不是放开更多底层模块给生成代码直接调用。

## 4. 硬边界

当前运行时同步接口的硬边界如下：

1. 生成 Skill 不允许直接 `import pymongo` 或 `MongoClient`。
2. 生成 Skill 不允许直接导入 `tradingagents.dataflows.interface`。
3. 生成 Skill 不允许直接导入 `tradingagents.dataflows.providers.*`。
4. 生成 Skill 不允许直接导入 `core.skill_runtime.catalog`、`external_sources`、`sync_wrappers` 等内部实现模块作为正式依赖。
5. 生成 Skill 应优先复用已公开 helper，而不是自己重写数据库查询和数据源桥接逻辑。

这些边界一部分由 Prompt 明示，一部分由静态验证器强制执行。

## 5. 与数据库连接层的关系

`skill_runtime` 自己不维护独立数据库配置，而是复用项目统一数据库连接层。

当前 `data_access` 通过 `get_mongo_db_sync()` 获取同步 MongoDB 客户端，这样能保证：

1. 与沙箱/子进程中的同步函数执行模型一致。
2. 避免在普通函数里误用 Motor 异步客户端。
3. 不需要让生成 Skill 自己知道数据库连接字符串或数据库名称。

因此，运行时设计的重点不是“如何让 Skill 连数据库”，而是“如何把数据库访问规范收口成稳定 helper”。

## 6. 扩展原则

后续若要增加新的股票机器人能力，优先顺序应为：

1. 先判断是否属于高频分析能力，如果是，优先补进 `data_access`。
2. 如果属于通用查询或侦察能力，补进 `project_access`。
3. 如果需要开放新的集合，先更新 `catalog`，再更新 `project_access` 文档与白名单。
4. 如果需要新外部数据源桥接，优先通过同步 wrapper 暴露，不要让生成代码直接碰异步 provider。
5. 增加接口后，同步更新本专题目录文档和代码生成 Prompt 注入文档。
