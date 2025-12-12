# 技术回顾与合规指南（回测/模拟交易与许可策略）

日期：2025-10-19
作者：TradingAgents-CN 项目组
用途：用于后续技术回顾与对外/对内合规参考

## 背景与目标
- 目标：在现有项目中引入/升级回测与模拟交易能力，同时明确开源引擎许可边界与商业化合规路径。
- 原则：优先成熟开源内核 + 自研数据/特征/市场规则适配；保证可替换性、可复现与可观测。

## 开源引擎与许可总结
- Backtrader：GPLv3（强 Copyleft），并非 MIT。分发包含其代码的衍生作品需开源源代码；仅内部使用或纯 SaaS 不触发网络使用条款（AGPL 才覆盖）。
  - 参考：Backtrader LICENSE https://github.com/mementum/backtrader/blob/master/LICENSE
- vectorbt：Apache-2.0 + Commons Clause（禁止“出售主要价值来自该软件功能”的产品/服务）。不强制你开源，但限制商业销售以其功能为主的产品/服务。
  - 许可说明：https://vectorbt.dev/terms/license/
  - 仓库：https://github.com/polakowo/vectorbt
- Lean（QuantConnect）：Apache-2.0，商业友好，适合构建可交付的闭源产品或对外收费的平台。
  - 官网：https://www.lean.io/
  - LICENSE：https://github.com/QuantConnect/Lean/blob/master/LICENSE
- RQAlpha：仓库 LICENSE 为 Apache-2.0，但官方文档强调“仅限非商业使用，如需商业使用请联系”，实际商业使用前需与米筐确认。
  - LICENSE（Gitee）：https://gitee.com/Ricequant/rqalpha/blob/master/LICENSE
  - README/说明（GitHub）：https://github.com/ricequant/rqalpha

## 商业化与合规策略
- 服务化与“臂长通信”：将回测/模拟内核独立为服务（进程/容器），主平台通过 HTTP/JSON、SSE/WebSocket 或 gRPC/Arrow Flight 调用，避免代码层耦合与 GPL 传染。
- 价值分层：平台的“主要价值”应来自自研数据层、市场约束与风控、执行仿真、报告与前端等；开源内核只是可替换组件。
- 收费设计：对自研能力（数据订阅、风控执行、报表、企业集成、SLA）收费；避免直接把 vectorbt 的能力作为核心付费卖点（Commons Clause 风险）。
- 许可例外与替代：若必须以 vectorbt 的功能收费，建议联系作者申请许可例外或采用 vectorbt PRO；更稳妥路线是改用 Lean（Apache-2.0）。

## 架构建议（服务化边界）
- 数据服务（闭源/开源均可）：统一数据模型与接口，仅通过网络协议对外提供。
  - 示例接口：
    - `GET /data/candles?symbol=...&start=...&end=...&interval=1m|1d&adj=none|forward`
    - `GET /data/calendar?market=CN|HK|US`（交易日与交易时段）
    - `GET /data/corp_actions?symbol=...`（分红、拆分、配股）
    - `GET /data/constraints?market=CN`（`t_plus_one=true`, `price_limit=±10%`, `lot_size=100` 等）
    - `GET /features/{name}?symbol=...&version=...`（Point-in-Time 特征）
    - `GET /stream/ticks?symbol=...`（SSE/WebSocket 推流）
- Backtrader 服务（GPLv3 开源）：撮合/订单/组合/费用滑点/市场规则适配。
  - 示例接口：`POST /session/start`、`POST /order`、`GET /portfolio`、`GET /trades`、`GET /report`、`GET /stream/events`
  - 内部适配器：从数据服务拉取数据，转换为 `PandasData` 或自定义 feed；遵守 GPLv3 源码与声明义务（若分发）。
- vectorbt 服务（Apache-2.0 + Commons Clause）：指标计算、组合回测、参数网格。
  - 示例接口：`POST /run_signals`（传入数据服务 URL 与参数）、`GET /metrics`、`GET /grid-search/result`
  - 商业化边界：禁止将该软件功能作为主要付费价值；需要商业化则改用 Lean 或申请许可例外。
- 主平台：仅调用上述服务的网络接口，不 `import` 其代码；保持可替换性（可切换 Lean/自研内核）。
- 传输建议：
  - 批量历史：`HTTP + Arrow/Parquet` 或 `gRPC/Arrow Flight`（高吞吐、列式、低拷贝）。小规模可 `HTTP + JSON`。
  - 实时/回放：`SSE/WebSocket` 或消息队列（Kafka/RabbitMQ）；统一 `UTC` 与 `timezone` 字段。
  - 版本冻结：`data_version`/`feature_version` 参数，保证可复现与 PIT 一致。

## GPLv3 合规要点（Backtrader 服务）
- 独立性：双仓库/双进程；主平台与数据服务通过网络协议交互，不成为衍生作品。
- 分发义务：若分发该服务的源码/二进制，需附 GPLv3 文本、版权声明、对应源代码与构建指令。
- SaaS 情形：仅在线提供、不分发服务端代码/二进制，一般不触发提供源码义务（AGPL 才覆盖网络使用）。
- 合并分发（Mere Aggregation）：同一安装包/镜像中包含 GPL 服务与闭源主平台，只要是可独立运行的两套程序，闭源部分不受 GPL 约束；仍需对 GPL 服务履行义务。
- 边界控制：避免共享内部对象或私有内存结构；接口文档化与可替换性有助于界定非衍生关系。

## Commons Clause 风险判断（vectorbt）
- 允许：内部研究、免费集成与分发（保留声明）、修改与衍生（遵守声明义务）。
- 限制：不得收费提供“主要价值来自该软件功能”的产品/服务，包括托管/咨询/支持若其主要价值即该软件功能。
- 降险：将 vectorbt 作为非核心、可替换组件；付费项聚焦于自研数据、风控、报告等能力。

## 替代路线
- Lean（Apache-2.0）：作为“对外收费的回测/模拟”核心服务的首选；主平台通过 HTTP/SSE 调用。
- 许可例外或 PRO：向 vectorbt 作者申请商业例外，或采用 vectorbt PRO；评估成本与社区支持。
- 自研轻量内核：实现最小撮合/费用/滑点/市场规则模块，满足个性化与合规需求。

## 快速检查清单（产品与合规）
- 定价与营销：是否围绕“回测/模拟功能”定价与宣传？
- 去除模块后价值：去掉该模块后，客户仍会为平台付费吗？
- 可替换性：能否无痛切换到 Lean/自研内核而不影响主要价值交付？
- 支持内容：支持服务是否主要围绕平台整体与自研组件，而非 vectorbt 的安装/调优/托管？
- 许可文本：是否保留 LICENSE/NOTICE 并清晰标识各组件的许可与边界？

## 下一步落地（建议）
- 在当前项目增加数据服务路由与响应 schema（`app/routers/data.py`）与 SSE 推流接口。
- 起草 Backtrader Gateway（会话管理、订单、撮合、报告、事件 SSE），并附 GPLv3 合规清单与 NOTICE 模板。
- 准备 Lean Gateway 的对应接口规范与最小实现，保证商业化无许可顾虑。
- 在 `docs/tech_reviews` 持续记录决策、接口与合规状态，形成工程与合规双轨的变更历史。

—— 以上为一般性技术与开源许可实践建议，非法律意见；具体结论仍需结合你的分发模式与法务意见。