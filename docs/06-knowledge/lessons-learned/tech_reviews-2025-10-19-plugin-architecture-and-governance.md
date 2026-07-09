# 插件体系技术指南与治理

日期：2025-10-19  
项目：TradingAgents-CN  
用途：统一插件架构、接口规范、打包分发、安全治理与许可合规指南

## 1. 目标与原则
- 解耦：数据、策略、内核（回测/模拟）、执行、风控、报告等模块以插件形式按需装配。
- 稳定：明确 `apiVersion` 与兼容矩阵，采用语义化版本与弃用策略。
- 合规：遵循开源许可边界（GPLv3/Commons Clause/Apache-2.0），避免主平台被传染；强化审计与 NOTICE。
- 安全：插件进程隔离、权限控制、资源限额与密钥管理；观测与健康检查。
- 可替换：保持与统一数据标准（Canonical Schema）对齐，支持引擎替换（vectorbt/Backtrader/Lean/自研）。
- 可测：提供一致的测试夹具（fixtures）与合规测试覆盖；黄金样本集回放。

## 2. 插件分类与扩展点（Extension Points）
- DataSource 插件：行情、基本面、企业事件、交易日历、公司行为；统一输出 Canonical Schema。
- Feature/Indicator 插件：因子工程、指标计算（向量化/流式）；支持版本冻结与 PIT。
- Strategy 插件：
  - Vectorized：`run_signals(df, params)` 返回信号与持仓/权重。
  - Event-Driven：`on_start/on_bar/on_order/on_stop`，与撮合/手续费/滑点耦合。
- EngineAdapter 插件：封装回测内核（vectorbt/Backtrader/Lean/RQAlpha），提供统一 `BacktestService/PaperService` 接口。
- Broker/Execution 插件：提交/撤单/查询账户与持仓；支持 Paper/模拟与真实经纪商连接。
- Risk/Compliance 插件：事前/事中检查、限额、风格暴露、集中度、黑白名单；阻断或降级。
- Report/Analytics 插件：绩效报告、归因、风险、可视化；导出（HTML/JSON/Arrow/Parquet）。
- UI/CLI 扩展：前端视图扩展点与命令行子命令（非核心）。

## 3. 统一接口规范（Core Interfaces）
- 基类：`PluginBase`
  - 元数据：`name/type/version/apiVersion/capabilities`。
  - 生命周期：`init(config) -> Ready`、`start()`、`stop()`、`dispose()`。
  - 观测：`health()`、`metrics()`、`events(topic)`（SSE/WebSocket）。
- DataSource：
  - `fetch_candles(full_symbol, start, end, granularity, adjustment)` → OHLCV+meta（UTC）。
  - `fetch_features(name, params, asof)` → 特征帧（含 `feature_version`）。
  - `resolve_symbol(any_code)` → `full_symbol/exchange_mic/vendor_symbols`。
- Strategy.Vectorized：
  - `run_signals(df, params)` → `{signals, positions, weights, meta}`。
- Strategy.EventDriven：
  - `on_start(ctx)`、`on_bar(ctx, bar)`、`on_order(ctx, event)`、`on_stop(ctx)`；`ctx` 含账户、约束与规则。
- EngineAdapter：
  - `run_backtest(strategy, data, rules, fees, slippage)` → `report/artifacts`。
  - `paper.session.start(config)`、`paper.order.submit(order)`、`paper.portfolio.get()`、`paper.stream.events()`。
- Broker/Execution：
  - `submit_order(order)`、`cancel_order(id)`、`get_portfolio()`、`get_positions()`、`stream_events()`。
- Risk：
  - `pre_trade_check(ctx, order)` → `allow|reject|modify` + `reasons`；事中与事后钩子可选。
- Report：
  - `build_report(ctx, artifacts)` → 指标集与导出文件。

## 4. 远程插件（Microservice Plugins）
- 传输：REST/gRPC/Arrow Flight（历史/批量）；SSE/WebSocket（实时/回放）；消息队列（可选）。
- 边界：与主平台保持“臂长关系”；仅以标准协议通信，避免静态链接/代码嵌入，符合 GPLv3 合规。
- 典型端点：
  - `POST /backtest/run`、`GET /backtest/report`、`GET /backtest/stream`
  - `POST /paper/session/start`、`POST /paper/order`、`GET /paper/portfolio`、`GET /paper/stream`
  - `GET /data/candles`、`GET /data/industry`、`GET /meta/symbol/resolve`

## 5. 打包与元数据（Packaging & Manifest）
- 结构：
  - `plugins/<type>/<name>/`
  - `plugin.yaml`（清单）与 `pyproject.toml`（Python 包）或容器镜像描述。
- `plugin.yaml` 字段建议：
  - `name/type/version/apiVersion/entryPoint`
  - `compatibility: { core: ">=0.1.16 <0.2.0", schema: "v1" }`
  - `capabilities: [datasource, strategy.vectorized, engine.adapter]`
  - `permissions: { network: true, filesystem: read, secrets: ["DATA_API_KEY"] }`
  - `dependencies: ["pandas>=2", "pyarrow>=15"]`
  - `license/author/homepage/signature/checksum`
- Python 入口：`entry_points = { 'tradingagents.plugins': ['name=package.module:PluginClass'] }`
- 容器插件：标注镜像与端点，采用健康检查与限额（CPU/Mem/FD/I/O）。

## 6. 版本与兼容策略
- 语义化版本：`MAJOR.MINOR.PATCH`；`apiVersion` 仅在破坏性变更时提升 MAJOR。
- 兼容矩阵：`core_version` 与 `plugin.compatibilityRange`；在文档发布弃用窗口与迁移指南。
- 配置冻结：策略/数据/规则版本字段在报告中固化，确保复现。

## 7. 安全与沙箱
- 进程隔离：插件默认独立进程/容器；主平台通过 IPC/HTTP 交互。
- 权限与密钥：最小权限；密钥由主平台注入，插件只读临时凭据；访问审计。
- 资源限额：CPU/内存/并发/速率限制；防止资源劫持。
- 供应链安全：签名与校验；SBOM；依赖扫描；隔离运行用户。
- 日志与观测：结构化日志、指标、健康探针；异常上报与熔断策略。

## 8. 分发与安装
- 本地注册表：`plugins/registry.json` 记录可用插件与兼容范围。
- 安装方式：
  - Python 包：`pip install tradingagents-plugin-<name>`。
  - 压缩包：解压至 `plugins/<type>/<name>/` 并注册。
  - 容器：拉取镜像并在 `plugins.d` 中声明端点与健康检查。
- 管理：`pluginctl add/list/enable/disable/remove`；校验签名与兼容性。

## 9. 许可与合规（关键）
- Backtrader（GPLv3）：作为独立服务（容器/进程），以 HTTP/SSE 调用；若对外分发该服务，需附 GPLv3 与对应源代码；主平台保持“臂长关系”，不嵌入 GPL 代码。
- vectorbt（Apache-2.0 + Commons Clause）：允许集成与分发插件；禁止销售“主要价值源自其功能”的产品/服务（含托管/支持若主要价值即其功能）。
- Lean（Apache-2.0）：商业友好，适合作为 EngineAdapter 插件；注意与主平台的接口边界与 NOTICE。
- 合规流程：插件清单记录 `license`；发布前进行许可证扫描与 NOTICE 汇总；商业售卖前进行“主要价值”评估与法务确认。

## 10. 测试与观测
- 夹具：统一黄金样本（CN/HK/US 各 50–100 标的），覆盖符号/行业/单位/时区差异。
- 合规测试：接口契约测试（schema 校验）、负载与稳定性、错误注入与恢复。
- 观测：插件级别的指标（吞吐/延迟/错误率）、事件日志与审计报告。

## 11. 实施路径（Phased Plan）
- Phase 0：定义 `PluginBase`、类型接口与 `plugin.yaml` 清单；发布兼容矩阵草案。
- Phase 1：实现插件管理器（注册/加载/生命周期/健康探针/签名校验）。
- Phase 2：产出参考插件：
  - `datasource.tushare`（符号与单位/时区规范化）；
  - `engine.vectorbt`（向量化回测）；
  - `engine.backtrader`（事件驱动 + PaperService）。
- Phase 3：CLI 与配置中心接入；前端插件观测页与 SSE 事件展示。
- Phase 4：风险/报告插件、插件商店与发布流程；完善许可合规自动化。

## 12. 示例：plugin.yaml（片段）
```yaml
name: engine.backtrader
type: engine.adapter
version: 0.1.0
apiVersion: v1
entryPoint: backtrader_adapter.plugin:BacktraderEnginePlugin
compatibility:
  core: ">=0.1.16 <0.2.0"
  schema: "v1"
capabilities:
  - backtest
  - paper
permissions:
  network: true
  filesystem: read
dependencies:
  - backtrader>=1.9
license: GPL-3.0-only
author: Example Team
```

## 13. 路由与事件模型（对齐）
- 控制面：`POST /paper/session/start`、`POST /paper/order`、`GET /paper/portfolio`、`GET /paper/stream`。
- 事件主题：`order.created`、`order.updated`、`trade.filled`、`portfolio.updated`、`risk.alert`；消息格式遵循统一数据标准（UTC、`full_symbol` 等）。

## 14. 落地检查清单（Checklist）
- 发布 `PluginBase` 与类型接口文档；冻结 `apiVersion v1`。
- 完成 `plugin.yaml` 规范与示例；实现签名与校验流程。
- 打通插件管理器基本能力（注册/加载/健康/卸载）。
- 交付三个参考插件（数据源/向量化引擎/事件驱动引擎）。
- 接入统一数据标准与 SSE 事件；报告输出与版本冻结。
- 许可证扫描与 NOTICE 汇总；GPL/Commons Clause 边界检查。

注：本指南与统一数据标准文档配套使用；后续在 `docs/config/` 发布插件清单模板与兼容矩阵，并在 `app/plugins/` 逐步落地管理器与参考插件实现。