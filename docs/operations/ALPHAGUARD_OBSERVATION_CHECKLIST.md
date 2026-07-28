# AlphaGuard 自动模拟运行观察清单

## 使用原则

- 每个交易日按本清单记录真实状态，不自动修改 Champion、因子、策略、Prompt、模型、
  HardRisk、撮合或费用配置。
- `PASS` 必须来自可验证的运行证据；无数据记 `NOT_READY`，过期记 `STALE`，故障记
  `BLOCKING` 或 `DEGRADED`。
- 不因没有交易信号而调参或强制 BUY；WATCH、NO_TRADE、REJECT 和 SUSPEND 都是合法
  业务结果。
- 任何真实交易入口、BrokerAdapter 或 `live_trading_enabled=true` 都是立即阻断项。

## 每日检查

### 1. 服务和 Worker

- [ ] FastAPI `/health/live` 为 200。
- [ ] MongoDB、Redis 和 AlphaGuard 索引健康。
- [ ] API Scheduler 为 HEALTHY，关键任务已注册。
- [ ] queue-worker 进程健康、重启次数无异常。
- [ ] `alphaguard:worker:queue` 心跳值持续变化且 TTL 大于 0。
- [ ] analysis-worker 进程健康、重启次数无异常。
- [ ] `worker:*:heartbeat` 为 active、时间持续变化且 TTL 大于 0。
- [ ] 两套 Worker 连接到同一目标数据库和 Redis DB。
- [ ] 最近日志无重复 Traceback、连接循环失败或未处理任务错误。

### 2. 安全不变量

- [ ] `system_mode=SIM_AUTONOMOUS`。
- [ ] `live_trading_enabled=false`。
- [ ] `live_execution_allowed=false`。
- [ ] FastAPI、queue-worker、analysis-worker 在 `live=true` 时仍拒绝启动。
- [ ] 无券商 SDK、BrokerAdapter、真实订单网络请求或实盘开关 API。

### 3. 数据同步与 DataQuality

- [ ] 交易日历版本、范围、最后同步和下一交易日可解析。
- [ ] 候选与沪深 300 原始/QFQ 日线覆盖完整、版本一致。
- [ ] 财务报告期和真实披露日期完整。
- [ ] 新闻、公告发布时间不晚于快照 cutoff。
- [ ] 市场环境和行业历史映射可按交易日解析。
- [ ] 同步任务无 FAILED/DEAD_LETTER，重试没有覆盖原错误。
- [ ] DataQuality FAIL、缺失率、异常 OHLC 和未来数据数量已记录。
- [ ] EvidenceSnapshot raw_refs 均能唯一解析，哈希验证通过。

### 4. 决策链

- [ ] Candidate 仅来自用户明确选择，不存在全市场自动推荐。
- [ ] QuantProposal 的 WATCH/REJECTED/INSUFFICIENT_DATA 数量和原因正常。
- [ ] Normal 模型 MODEL_FAILED、INVALID_OUTPUT、INSUFFICIENT_DATA 分开统计。
- [ ] TopReview 模型失败和非法输出未回退为 HOLD。
- [ ] Consensus PASS/REVISE/REJECT/INVALID 数量及 lineage 可追踪。
- [ ] HardRisk PASS/REDUCE/REJECT/SUSPEND 的触发规则完整。
- [ ] 所有对象的 user/symbol/market/trade_date/snapshot/version 身份一致。

### 5. Outbox、订单和撮合

- [ ] 仅 RiskDecision PASS/REDUCE 或受控基准链产生对应 outbox。
- [ ] outbox backlog、retry、DEAD_LETTER 数量正常。
- [ ] 无重复 idempotency key、Intent、Order 或 Fill。
- [ ] 未到执行日、停牌、涨跌停和缺行情订单未被错误成交。
- [ ] 部分成交、剩余数量、预留和订单状态一致。
- [ ] PAPER_CHALLENGER 无活动账户、订单或持仓。
- [ ] 人工 paper 集合未被自动链修改。

### 6. 结算、账本和资产守恒

- [ ] Settlement Saga 无长期 PREPARED/中间态/COMPENSATION_REQUIRED。
- [ ] Fill 只结算一次，未 COMMITTED 的订单未标记 FILLED。
- [ ] 现金可用、冻结现金、持仓、lot 和预留均不为负。
- [ ] BUY lot 的 T+1 可用日期来自交易日历。
- [ ] FIFO 消耗、手续费和已实现盈亏与不可变 Fill 一致。
- [ ] 账本借贷变化可解释账户差额。
- [ ] 取消/过期只释放剩余预留，不改变净资产。
- [ ] 账户 reconciliation 通过；冲突已告警而非静默修正。

### 7. 账户估值和评价

- [ ] DailyAccountSnapshot 每个启用账户每个交易日唯一。
- [ ] 缺收盘价时 `valuation_complete=false`，未按 0 静默估值。
- [ ] 总权益、敞口、费用和持仓数量可由账户/持仓/快照复算。
- [ ] 合法决策/执行已登记真实 EvaluationSubject。
- [ ] HorizonLabel 只在真实交易日和 QFQ 数据成熟后计算。
- [ ] 评价样本不足保持 NOT_READY/INSUFFICIENT_DATA。
- [ ] 未来收益或归因没有进入任何决策输入。

### 8. 告警和日报结论

- [ ] 所有 OPEN/ACKNOWLEDGED 告警已按严重度检查。
- [ ] BLOCKING、DEGRADED、NOT_READY、STALE 项目已列出责任域和证据。
- [ ] 当日新增错误与存量错误分开。
- [ ] 记录 worker 心跳、任务积压、数据版本、Snapshot/Proposal/Decision/Order/Fill
  增量和资产核对结果。
- [ ] 未执行任何自动晋升、自动回退或生产参数修改。

## 建议日报格式

```text
trade_date:
code_complete:
runtime_ready:
data_ready:
paper_ready:
evaluation_ready:

blocking:
degraded:
not_ready:
stale:

queue_worker_heartbeat:
analysis_worker_heartbeat:
job_backlog:
data_sync:
data_quality:
model_failures:
invalid_outputs:
consensus:
hard_risk:
outbox:
orders:
settlement:
asset_conservation:
valuation:
evaluation_maturity:
alerts:

changes_performed:
changes_explicitly_not_performed:
evidence_links_or_ids:
```

## 当前首次观察结论（2026-07-27）

- `CODE_COMPLETE=true`、`RUNTIME_READY=true`、`EXPERIMENT_READY=true`。
- FastAPI、MongoDB、Redis、Scheduler、queue-worker、analysis-worker 均 HEALTHY。
- 两个 Worker 心跳真实存在并持续更新；没有写入虚假心跳。
- Champion 5/5 验证通过；Operations integrity 为 PASS。
- `DATA_READY=false`、`PAPER_READY=false`、`EVALUATION_READY=false`。
- 数据、账户、候选、Snapshot、QuantProposal、Order、Fill 和 EvaluationSubject 当前均
  未伪造或强制创建。
- 当前阻断项详见 `ALPHAGUARD_DATA_BRINGUP.md` 和执行状态文档。

## Real Data Activation 观察（2026-07-27 13:25 CST）

- Worker 真实心跳：queue TTL=12、analysis TTL=37，两个容器均 healthy；无虚假心跳。
- `TRADING_CALENDAR=READY`：2557 条，2020-01-01 至 2026-12-31；跨周末
  2026-07-24 → 2026-07-27 的 T+1 已验证。
- 五个用户指定候选的 RAW/QFQ 均为 861 个交易日，最近完整日为 2026-07-24；
  沪深 300 同范围 861 根。
- 财务 66 条、新闻 50 条、公告 2700 条，所有行具有真实时间字段、稳定
  `ref_id`、版本和内容 hash；重复引用为 0。
- 五个标的 2026-07-24 DataQuality 预检查均 PASS。
- `MARKET_CONTEXT=NOT_READY`；行业为 `PARTIAL/CURRENT_ONLY`，不得解释为完整历史。
- 管理员 dry-run 为 `WOULD_CREATE`，尚未进行隐藏密码 execute；因此自动账户、候选、
  Snapshot、QuantProposal 和 EvaluationSubject 仍为 0。
- Champion 在 2026-07-24 正确阻断，在 2026-07-27 可解析 5/5；当前盘中不创建
  2026-07-27 日线快照。
- Outbox、Order、Fill、Reservation、Ledger、Settlement 均为 0；没有重复订单或
  资产变化。
- 安全配置仍为 `SIM_AUTONOMOUS / live_trading_enabled=false`。

## Real Data Activation 完成观察（2026-07-27 20:50 CST）

- queue-worker 与 analysis-worker 容器均 healthy；两个 Redis 心跳均持续推进，analysis
  心跳跨 35 秒观测窗口发生更新。
- 管理员 `alphaguard_admin` 已通过现有认证体系创建并成功登录；密码只保存在本机
  Keychain。
- PAPER_QUANT、PAPER_NORMAL、PAPER_TOP_CONFIRMED 各 100 万元，冻结为 0，
  无仓位/订单/成交/预留/账本，三个 DailyAccountSnapshot 均完整，现金守恒。
- PAPER_CHALLENGER 未创建、未激活。
- 五个指定候选均为 USER_SELECTED/WATCHING，DataQuality 预检 5/5 PASS。
- 300750 的真实 Snapshot
  `8096af28-88aa-4eb1-b51e-dc6b3852debc` 哈希验证通过；共锁定 2207 个证据引用和
  5 个 Champion 版本。
- 21 个 FactorResult 已保存；市场环境为空使 Regime 明确
  `INSUFFICIENT_DATA`，未默认 `RANGE_WEAK`。
- 两个 QuantProposal 分别为 REJECTED/NO_POSITION 和
  INSUFFICIENT_DATA/REGIME_INSUFFICIENT_DATA；未调用模型或订单链。
- 2 个 EvaluationSubject、8 个 PENDING HorizonLabel 已登记，无未来标签计算。
- 真实量化和评价链重复运行后 Factor/Regime/Proposal/Subject 计数不变，评价对象
  `0 created / 2 reused`。
- Outbox、Intent、Order、Fill 均为 0；无重复订单或资产不守恒。
- Operations：CODE_COMPLETE=true、RUNTIME_READY=true、PAPER_READY=true；
  DATA_READY=false（MARKET_CONTEXT、历史行业）、EVALUATION_READY=false（标签未成熟）。
- 三个启动入口在 `live=true` 时均 fail-closed；未修改任何生产交易参数或版本。
- AlphaGuard 精确回归 441 passed；全量收集仍是既有 15 错误，前端仍是既有 34 个
  DefaultRow TS2345，没有新增错误类别。

## Historical Backfill 观察项

- [ ] 只允许 `RESEARCH_BACKFILL / research_only=true / automated_execution_allowed=false`。
- [ ] 研究 Snapshot、Factor、Regime、Proposal、ShadowExecution 只写 `ag_research_*`。
- [ ] 研究 EvaluationSubject 的 lineage 包含 `backfill_run_id` 和 `sample_id`。
- [ ] 财务、新闻和公告均不晚于历史 cutoff；未来行情只在决策冻结后用于标签。
- [ ] MarketContext 使用历史实际 universe，覆盖率和 Provider 失败数量已记录。
- [ ] current-only 行业映射没有回填历史，行业相对收益缺失时为 null。
- [ ] 缺显式涨跌停边界的影子执行为 `INSUFFICIENT_DATA`，没有推算成交。
- [ ] 1D/5D/10D/20D 标签按真实持久化交易日成熟，未来期限保持 PENDING。
- [ ] 同一 run 重复执行不增加 Snapshot、Proposal、Label、Shadow 或 Attribution。
- [ ] 回放前后十个正式交易集合的 count 和 content hash 完全一致。
- [ ] 报告明确标注为历史研究，不是实时生产成绩、实际账户收益或投资建议。

## Historical Backfill 完成观察（2026-07-27 23:43 CST）

- [x] Canonical run `9b921ffa-71a5-578b-85e8-252b2f9cfca9` 为
  `RESEARCH_BACKFILL / research_only=true / automated_execution_allowed=false`。
- [x] 25 个历史 MarketContext 全部 READY；125/125 样本完成，无跳过和失败。
- [x] 财务、新闻、公告和行情严格按历史 cutoff 截断；20D 未成熟的 10 个标签保持
  PENDING 至 2026-07-28。
- [x] current-only 行业映射未回填；1016 个标签的行业相对收益均为 null。
- [x] 4 个 TRIGGERED 因缺显式涨跌停边界返回 `INSUFFICIENT_DATA`；研究成交为 0。
- [x] 幂等复跑不增加 run attempt、Snapshot、Factor、Proposal、Label、Shadow 或
  Attribution，report hash 不变。
- [x] 正式 Outbox/Intent/Order/Fill/Position/Lot/Reservation/Ledger/Settlement 均为 0；
  三账户现金、冻结和权益守恒。
- [x] queue/analysis Worker healthy，真实心跳 TTL>0（最终观测 12/46）；MongoDB/Redis
  healthy。
- [x] `live=true` 下 FastAPI、queue-worker、analysis-worker 均拒绝启动。
- [x] Operations 当前 `DATA_READY=false` 是生产 MarketContext 缺失，不被研究数据掩盖。
- [x] 未修改任何交易参数、Champion 或生产版本；未开始 PR-010。

每日实时观察仍应继续使用前述清单。历史回放的成熟样本不能替代生产数据同步、生产
MarketContext、真实订单结算观察或未来 20 个交易日的实时稳定性观察。
